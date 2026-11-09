"""Tutoring through the Abacus.AI RouteLLM API (OpenAI-compatible chat completions).

Requests go from this Mac straight to Abacus with the learner's own API key; histories stay in this client. The
key is read when needed and never logged, saved in Settings or shown. Replies arrive whole, as with ChatGPT.
"""
from __future__ import annotations

import asyncio
import base64
import json
import os
from pathlib import Path
import re
import time
import urllib.error
import urllib.request
from typing import AsyncIterator, Sequence

from . import abacus_models
from .ai import MEDIA, Result, SPEECH_FIELD, SPEECH_RULE, SpeechFilter, classify, complete, first_json, \
    json_instruction, split_speech


BASE = os.environ.get("ABACUS_ROUTELLM_BASE_URL", "https://routellm.abacus.ai/v1").rstrip("/")
KEY_FILE = Path.home() / ".config/routellm/key"
KEY_HELP = ("Add your Abacus.AI RouteLLM API key: in Terminal run  mkdir -p ~/.config/routellm && "
            "pbpaste > ~/.config/routellm/key && chmod 600 ~/.config/routellm/key  (with the key copied), then try again.")


TRIES = 3  # one request plus two repairs: a reply that is not the JSON asked for is asked for again, not shown
MAX_TOKENS = 16000  # a long explanation must not be cut off mid-JSON
_BAD_ESCAPE = re.compile(r'\\(?!["\\/bfnrtu])')


class AbacusError(Exception):
    """The selected Abacus request failed; another provider must not take over."""


def api_key() -> str:
    key = os.environ.get("ABACUS_ROUTELLM_API_KEY", "").strip()
    if key:
        return key
    try:
        return KEY_FILE.read_text().splitlines()[0].strip()
    except (OSError, IndexError):
        return ""


def read_json(text: str) -> dict | None:
    """The reply's JSON object, also when a model wrote a LaTeX backslash once (\\frac) where JSON needs two."""
    return first_json(text) or first_json(_BAD_ESCAPE.sub(r"\\\\", text))


def _content(text: str, images: list[str]) -> str | list[dict]:
    if not images:
        return text
    parts: list[dict] = [{"type": "text", "text": text}]
    for path in images:
        data = base64.b64encode(Path(path).read_bytes()).decode()
        parts.append({"type": "image_url", "image_url": {"url": f"data:{MEDIA[Path(path).suffix.lower()]};base64,{data}"}})
    return parts


def _performance(usage: dict, routed: str) -> dict:
    """What the footer under an answer shows about this request: the model Abacus actually ran."""
    return {"cloud": True, "routed": routed, **({"output_tokens": usage["output_tokens"]}
                                                 if isinstance(usage.get("output_tokens"), int) else {})}


class AbacusAI:
    def __init__(self, system: str, speech: bool = False, *, document: bool = False):
        self.system, self.speech, self.document = system, speech, document
        self.status, self.message = "ready", ""
        self.last = Result()
        self._history: dict[tuple, list[dict]] = {}
        self._lock = asyncio.Lock()
        self._generation = 0
        self._closed = False
        self._blocked_until = 0.0

    @property
    def available(self) -> bool:
        if self.status in ("login", "limit") and time.monotonic() >= self._blocked_until:
            self.status, self.message = "ready", ""
        if not api_key():
            self.message = KEY_HELP
            return False
        return not self._closed and self.status == "ready"

    def _check(self, model: str | None) -> str:
        if not abacus_models.is_abacus(model):
            raise AbacusError("Choose an Abacus model in Settings.")
        if not self.available:
            raise AbacusError(self.message or "Abacus tutoring is closed.")
        return str(model).removeprefix("abacus:")

    def _images(self, model: str | None, images: Sequence[Path | str]) -> list[str]:
        paths = []
        for image in images:
            image = Path(image)
            if image.suffix.lower() not in MEDIA or not image.is_file():
                raise AbacusError("A question image is missing or unsupported; mark this answer manually.")
            paths.append(str(image.resolve()))
        if paths and not abacus_models.reads_images(model):
            raise AbacusError("This Abacus model reads text only; choose one that reads images, or mark manually.")
        return paths

    def _failure(self, exc: Exception, text: str = "") -> Result:
        from .chat_output import DocumentError

        message = ("Abacus took too long to answer; try again." if isinstance(exc, asyncio.TimeoutError)
                   else f"Abacus returned an incomplete structured answer; try again. ({exc})"
                   if isinstance(exc, DocumentError)
                   else str(exc) if isinstance(exc, AbacusError)
                   else "Abacus sent an unreadable reply. Check your key and connection, then try again.")
        status = classify(message)
        if status in ("login", "limit"):
            self.status = status
            self._blocked_until = time.monotonic() + 180
            self.message = message
        return Result(ok=False, status=status, message=message, text=text)

    def _post(self, body: dict, timeout: float) -> dict:
        request = urllib.request.Request(BASE + "/chat/completions", data=json.dumps(body).encode(), method="POST",
                                         headers={"Authorization": f"Bearer {api_key()}",
                                                  "Content-Type": "application/json"})
        try:
            with urllib.request.urlopen(request, timeout=timeout) as response:
                return json.loads(response.read())
        except urllib.error.HTTPError as exc:  # the body explains it (bad model, no credits); it never holds the key
            detail = exc.read().decode(errors="replace")[:300]
            if exc.code in (401, 403):
                raise AbacusError("Abacus refused the key (invalid API key). " + KEY_HELP) from None
            if exc.code == 429 or "credit" in detail.lower():
                raise AbacusError("Your Abacus usage limit or credits are used up. Try later.") from None
            raise AbacusError(f"Abacus could not answer (HTTP {exc.code}): {detail}") from None
        except (urllib.error.URLError, TimeoutError) as exc:
            raise AbacusError(f"Abacus is unreachable ({getattr(exc, 'reason', exc)}); check the connection.") from None

    async def _ask(self, messages: list[dict], model: str, system: str, schema: dict | None,
                   deadline: float) -> tuple[str, dict, str, bool]:
        wire = [{"role": "system", "content": system + ("\n\n" + json_instruction(schema) if schema else "")}]
        wire += [{"role": m["role"], "content": _content(m["content"], m.get("images", []))} for m in messages]
        body = {"model": model, "messages": wire, "max_tokens": MAX_TOKENS,
                **({"response_format": {"type": "json_object"}} if schema else {})}
        remaining = max(1.0, deadline - time.monotonic())
        reply = await asyncio.wait_for(asyncio.to_thread(self._post, body, remaining), remaining + 5)
        try:
            text = reply["choices"][0]["message"]["content"] or ""
        except (KeyError, IndexError, TypeError):
            raise AbacusError("Abacus sent an unreadable reply; try again.") from None
        if not isinstance(text, str) or not text.strip():
            raise AbacusError("Abacus ended the reply early; try again.")
        routed = reply.get("model")  # the model RouteLLM actually used for this request
        cut = reply["choices"][0].get("finish_reason") == "length"
        return text, reply.get("usage") or {}, routed if isinstance(routed, str) else "", cut

    async def _json(self, messages: list[dict], model: str, system: str, schema: dict, deadline: float,
                    generation: int) -> tuple[dict, str, dict, str]:
        """Ask until the reply is the complete JSON the schema describes, asking again with what was wrong."""
        problem = ""
        for attempt in range(TRIES):
            text, usage, routed, cut = await self._ask(messages, model, system, schema, deadline)
            if generation != self._generation:
                raise AbacusError("The Abacus conversation was reset; try again.")
            data = read_json(text)
            if data is None:
                problem = ("was cut off before the JSON ended; answer again, more briefly" if cut
                           else "was not a single JSON object")
            elif not complete(data, schema):
                problem = "did not include every required field of the schema"
            else:
                return data, text, usage, routed
            if attempt + 1 == TRIES or deadline - time.monotonic() < 25:
                break
            messages = [*messages, {"role": "assistant", "content": text[:6000]},
                        {"role": "user", "content": f"That reply {problem}. Reply again with ONLY the complete JSON "
                                                    "object that matches the schema, with every LaTeX backslash written twice."}]
        raise AbacusError(f"Abacus returned incomplete JSON ({problem}); try again.")

    async def warm(self) -> None:
        """API models need no speculative request or preloading."""

    async def stream(self, prompt: str, image: Path | None = None, model: str | None = None,
                     think: bool | str = False) -> AsyncIterator[str]:
        acquired, owner, finished, raw = False, False, False, ""
        generation = self._generation
        deadline = time.monotonic() + 300
        try:
            await asyncio.wait_for(self._lock.acquire(), max(0.001, deadline - time.monotonic()))
            acquired = True
            if generation != self._generation:
                raise asyncio.CancelledError
            owner = True
            self.last = Result(ok=False, status="error", message="The Abacus reply was cancelled; try again.")
            name = self._check(model)
            key = (model, self.speech, self.document)
            history = self._history.get(key, [])
            user: dict = {"role": "user", "content": prompt}
            if image is not None:
                user["images"] = self._images(model, [image])
            system = self.system + (SPEECH_RULE if self.speech and not self.document else "")
            schema = decoder = None
            if self.document:
                from .chat_output import DocumentDecoder, document_instructions, document_schema
                decoder, schema = DocumentDecoder(self.speech), document_schema(self.speech)
                system += "\n\n" + document_instructions(self.speech)
            if decoder is not None:
                data, raw, usage, routed = await self._json([*history, user], name, system, schema or {},
                                                            deadline, generation)
                wire = json.dumps(data, ensure_ascii=False)
                if visible := decoder.feed(wire):
                    yield visible
                text, speech = decoder.finish()
            else:
                raw, usage, routed, _ = await self._ask([*history, user], name, system, None, deadline)
                if generation != self._generation:
                    raise AbacusError("The Abacus conversation was reset; try again.")
                speech_filter = SpeechFilter()
                if visible := speech_filter.feed(raw) + speech_filter.finish():
                    yield visible
                text, speech = split_speech(raw)
            self.last = Result(text=text, speech=speech, usage=usage, performance=_performance(usage, routed))
            self._history[key] = [*history, user, {"role": "assistant",
                                                   "content": decoder.wire if decoder is not None else raw}]
            finished = True
        except (OSError, ValueError, asyncio.TimeoutError, AbacusError) as exc:
            if not owner:
                if isinstance(exc, asyncio.TimeoutError):
                    raise asyncio.CancelledError from None
                raise  # a queued caller cannot overwrite the active request's shared result
            self.last = self._failure(exc, split_speech(raw)[0] if raw and not self.document else "")
        finally:
            if owner and not finished:
                self.last.ok = False
            if acquired:
                self._lock.release()

    async def one_shot(self, prompt: str, schema: dict | None = None, model: str | None = None,
                       timeout: float = 120, system: str | None = None, speech: bool = False,
                       think: bool | str = False, images: list[Path] | None = None):
        acquired = False
        generation = self._generation
        deadline = time.monotonic() + timeout
        try:
            await asyncio.wait_for(self._lock.acquire(), max(0.001, deadline - time.monotonic()))
            acquired = True
            if generation != self._generation:
                raise asyncio.CancelledError
            name = self._check(model)
            message: dict = {"role": "user", "content": prompt}
            if paths := self._images(model, images or []):
                message["images"] = paths
            if speech and self.speech and schema:
                props = schema.get("properties", {})
                schema = {**schema, "properties": {**props, "speech": {"type": "string"}},
                          "required": list(dict.fromkeys([*schema.get("required", list(props)), "speech"]))}
                message["content"] += f"\n\n{SPEECH_FIELD}"
            data, text, usage, routed = await self._json([message], name, system or self.system,
                                                         schema or {"type": "object"}, deadline, generation)
            spoken = data.get("speech", "")
            return data, Result(text=text, speech=spoken.strip() if isinstance(spoken, str) else "", usage=usage,
                                performance=_performance(usage, routed))
        except (OSError, ValueError, asyncio.TimeoutError, AbacusError) as exc:
            return None, self._failure(exc)
        finally:
            if acquired:
                self._lock.release()

    async def reset(self) -> None:
        self._generation += 1
        self._history.clear()

    async def close(self) -> None:
        self._closed = True
        await self.reset()
