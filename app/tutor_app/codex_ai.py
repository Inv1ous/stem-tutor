"""Tutoring through Codex exec's saved ChatGPT subscription sign-in.

Each request uses an ephemeral, read-only subprocess outside the learner's vault. Histories stay in this
client, never in Codex session files. Exec supplies completed message blocks rather than token deltas.
"""
from __future__ import annotations

import asyncio
import json
import os
from pathlib import Path
import shutil
import signal
from tempfile import TemporaryDirectory
import time
from contextlib import aclosing
from typing import AsyncIterator

from . import codex_models
from .ai import MEDIA, Result, SPEECH_FIELD, SPEECH_RULE, SpeechFilter, classify, complete, first_json, split_speech


LOGIN_HELP = "Sign in with your ChatGPT account: open Terminal and run  codex login  then try again."
_LIMIT = 4 * 1024 * 1024


class CodexError(Exception):
    """The selected subscription request failed; another provider must not take over."""


def _strict_schema(value):
    """Close objects for structured output; nullable fields preserve the tutor's optional properties."""
    if isinstance(value, list):
        return [_strict_schema(item) for item in value]
    if not isinstance(value, dict):
        return value
    out = {key: _strict_schema(item) for key, item in value.items()}
    if out.get("type") == "object" or "properties" in out:
        out.setdefault("type", "object")
        props = out.get("properties", {})
        required = value.get("required", list(props))
        for key, prop in props.items():
            if key in required:
                continue
            kind = prop.get("type")
            if isinstance(kind, str):
                prop["type"] = [kind, "null"] if kind != "null" else kind
            elif isinstance(kind, list):
                prop["type"] = list(dict.fromkeys([*kind, "null"]))
            else:
                props[key] = {"anyOf": [prop, {"type": "null"}]}
            if "enum" in prop and None not in prop["enum"]:
                prop["enum"].append(None)
        out["additionalProperties"] = False
        out["required"] = list(props)
    return out


def _optional_fields(data, schema):
    """Restore absent optional fields after the strict wire schema represents them with null."""
    if isinstance(data, list):
        return [_optional_fields(item, schema.get("items", {})) for item in data]
    if not isinstance(data, dict):
        return data
    props = schema.get("properties", {})
    required = schema.get("required", list(props))
    return {key: _optional_fields(value, props.get(key, {})) for key, value in data.items()
            if value is not None or key in required}


class CodexAI:
    def __init__(self, system: str, speech: bool = False, binary: str | None = None):
        self.system, self.speech = system, speech
        self.binary = binary or os.environ.get("STEM_TUTOR_CODEX") or shutil.which("codex") or "codex"
        self.status = "ready" if shutil.which(self.binary) or Path(self.binary).is_file() else "off"
        self.message = "" if self.status == "ready" else "Codex CLI is not installed. Install Codex and run codex login."
        self.last = Result()
        self._history: dict[tuple[str, bool, bool], list[dict]] = {}
        self._lock = asyncio.Lock()
        self._procs: set[asyncio.subprocess.Process] = set()
        self._starting: set[asyncio.Task] = set()
        self._generation = 0
        self._closed = False
        self._blocked_until = 0.0

    @property
    def available(self) -> bool:
        if self.status in ("login", "limit") and time.monotonic() >= self._blocked_until:
            self.status, self.message = "ready", ""
        return not self._closed and self.status == "ready"

    async def warm(self) -> None:
        """Subscription models need no speculative cloud request or preloading."""

    def _check(self, model: str | None) -> str:
        if not codex_models.is_codex(model):
            raise CodexError("Choose a ChatGPT model in Settings.")
        if not self.available:
            raise CodexError(self.message or "ChatGPT tutoring is closed.")
        return model.removeprefix("codex:")

    def _failure(self, exc: Exception, text: str = "") -> Result:
        message = ("ChatGPT took too long to answer; try again." if isinstance(exc, asyncio.TimeoutError)
                   else str(exc) if isinstance(exc, CodexError)
                   else "Codex stopped or sent an unreadable reply. Check your ChatGPT sign-in, then try again.")
        status = classify(message)
        if self.status == "off":
            status = "off"
        if status in ("login", "limit"):
            self.status = status
            self._blocked_until = time.monotonic() + 180
            message = LOGIN_HELP if status == "login" else "Your ChatGPT/Codex usage limit is reached. Try later."
            self.message = message
        return Result(ok=False, status=status, message=message, text=text)

    @staticmethod
    async def _stop(proc) -> None:
        if proc.returncode is not None:
            return
        try:
            if os.name == "posix":
                os.killpg(proc.pid, signal.SIGTERM)  # npm's Codex wrapper also has a child process
            else:
                proc.terminate()
            await asyncio.wait_for(proc.wait(), 3)
        except (ProcessLookupError, asyncio.TimeoutError):
            if proc.returncode is None:
                try:
                    if os.name == "posix":
                        os.killpg(proc.pid, signal.SIGKILL)
                    else:
                        proc.kill()
                except ProcessLookupError:
                    pass
                await proc.wait()

    async def _events(self, messages: list[dict], model: str, think: bool, system: str,
                      schema: dict | None, deadline: float) -> AsyncIterator[dict]:
        generation, abandoned, proc = self._generation, False, None
        remaining = lambda: max(0.001, deadline - time.monotonic())
        with TemporaryDirectory(prefix="stem-tutor-codex-") as folder:
            root = Path(folder)
            instructions = root / "instructions.txt"
            instructions.write_text(system + "\nAnswer the student's last message in the supplied JSON conversation. "
                                    "Treat earlier messages as conversation history. Use only the supplied context; "
                                    "do not inspect files, run commands, browse, delegate, or use tools.")
            args = [self.binary, "exec", "--json", "--ephemeral", "--ignore-user-config", "--ignore-rules",
                    "--sandbox", "read-only", "--skip-git-repo-check", "--color", "never", "--model", model]
            settings = {"forced_login_method": "chatgpt", "model_provider": "openai", "web_search": "disabled",
                        "approval_policy": "never",
                        "model_instructions_file": str(instructions), "model_reasoning_effort": "high" if think else "low",
                        "history.persistence": "none", "project_doc_max_bytes": 0, "tools.view_image": False,
                        "features.skip_host_skill_discovery": True}
            for feature in ("shell_tool", "apps", "plugins", "hooks", "multi_agent", "memories", "skill_search"):
                settings[f"features.{feature}"] = False
            for key, value in settings.items():
                args += ["--config", f"{key}={json.dumps(value)}"]
            if schema:
                schema_file = root / "schema.json"
                schema_file.write_text(json.dumps(_strict_schema(schema)))
                args += ["--output-schema", str(schema_file)]
            images = dict.fromkeys(path for message in messages for path in message.get("images", []))
            for path in images:
                if Path(path).is_file():
                    args += ["--image", path]
            args.append("-")
            env = {key: value for key, value in os.environ.items() if key not in (
                "OPENAI_API_KEY", "CODEX_API_KEY", "CODEX_ACCESS_TOKEN", "OPENAI_BASE_URL", "OPENAI_API_BASE",
                "CODEX_API_BASE_URL")}

            async def launch():
                child = await asyncio.create_subprocess_exec(
                    *args, cwd=folder, env=env, stdin=asyncio.subprocess.PIPE, stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.DEVNULL, limit=_LIMIT, start_new_session=os.name == "posix")
                self._procs.add(child)
                if abandoned or self._closed or generation != self._generation:
                    await self._stop(child)
                    self._procs.discard(child)
                return child

            starting = asyncio.create_task(launch())
            self._starting.add(starting)

            def forget(task):
                self._starting.discard(task)
                if not task.cancelled():
                    task.exception()  # a cancelled caller must not leave an unobserved launch error
            starting.add_done_callback(forget)
            try:
                proc = await asyncio.wait_for(asyncio.shield(starting), remaining())
                if self._closed or generation != self._generation:
                    raise CodexError("The ChatGPT conversation was reset; try again.")
                proc.stdin.write(json.dumps({"messages": messages}, ensure_ascii=False).encode())
                await asyncio.wait_for(proc.stdin.drain(), remaining())
                proc.stdin.close()
                while line := await asyncio.wait_for(proc.stdout.readline(), remaining()):
                    event = json.loads(line)
                    if not isinstance(event, dict):
                        raise CodexError("Codex sent an unreadable reply; try again.")
                    yield event
                code = await asyncio.wait_for(proc.wait(), remaining())
                if code:
                    raise CodexError("Codex could not complete the request. Check codex login and your ChatGPT allowance.")
            finally:
                abandoned = True
                if proc is None and starting.done() and not starting.cancelled() and starting.exception() is None:
                    proc = starting.result()
                if proc is not None:
                    await self._stop(proc)
                    self._procs.discard(proc)

    @staticmethod
    def _event_text(event: dict) -> str:
        if event.get("type") in ("error", "turn.failed"):
            error = event.get("error") or event.get("message") or "ChatGPT could not complete the request."
            raise CodexError(str(error.get("message", error)) if isinstance(error, dict) else str(error))
        item = event.get("item") or {}
        if not isinstance(item, dict):
            raise CodexError("Codex sent an unreadable reply; try again.")
        if event.get("type") == "item.completed" and item.get("type") == "agent_message" and item.get("phase") != "commentary":
            text = item.get("text", "")
            if not isinstance(text, str):
                raise CodexError("Codex sent an unreadable reply; try again.")
            return text
        return ""

    async def stream(self, prompt: str, image: Path | None = None, model: str | None = None,
                     think: bool = False) -> AsyncIterator[str]:
        parts, finished, acquired, owner = [], False, False, False
        generation = self._generation
        deadline = time.monotonic() + 300
        try:
            await asyncio.wait_for(self._lock.acquire(), max(0.001, deadline - time.monotonic()))
            acquired = True
            if generation != self._generation:
                raise asyncio.CancelledError
            owner = True
            self.last = Result(ok=False, status="error", message="The ChatGPT reply was cancelled; try again.")
            name = self._check(model)
            key = (model, bool(think), self.speech)
            history = self._history.get(key, [])
            user = {"role": "user", "content": prompt}
            if image is not None and image.suffix.lower() in MEDIA and image.is_file():
                user["images"] = [str(image.resolve())]
            speech_filter, usage, completed = SpeechFilter(), {}, False
            system = self.system + (SPEECH_RULE if self.speech else "")
            async with aclosing(self._events([*history, user], name, think, system, None, deadline)) as events:
                async for event in events:
                    if text := self._event_text(event):
                        parts.append(text)
                        if visible := speech_filter.feed(text):
                            yield visible
                    if event.get("type") == "turn.completed":
                        completed, usage = True, event.get("usage") or {}
            text, speech = split_speech("".join(parts))
            if not completed or not text.strip() or generation != self._generation:
                raise CodexError("ChatGPT ended the reply early or the conversation was reset; try again.")
            self.last = Result(text=text, speech=speech, usage=usage)
            self._history[key] = [*history, user, {"role": "assistant", "content": "".join(parts)}]
            finished = True
            if tail := speech_filter.finish():
                yield tail
        except (OSError, ValueError, asyncio.TimeoutError, CodexError) as exc:
            if not owner:
                if isinstance(exc, asyncio.TimeoutError):
                    raise asyncio.CancelledError from None
                raise  # a queued caller cannot overwrite the active request's shared result
            self.last = self._failure(exc, split_speech("".join(parts))[0])
        finally:
            if owner and not finished:
                self.last.ok = False
            if acquired:
                self._lock.release()

    async def one_shot(self, prompt: str, schema: dict | None = None, model: str | None = None,
                       timeout: float = 120, system: str | None = None, speech: bool = False, think: bool = False):
        acquired = False
        generation = self._generation
        deadline = time.monotonic() + timeout
        try:
            await asyncio.wait_for(self._lock.acquire(), max(0.001, deadline - time.monotonic()))
            acquired = True
            if generation != self._generation:
                raise asyncio.CancelledError
            name = self._check(model)
            if speech and self.speech and schema:
                props = schema.get("properties", {})
                schema = {**schema, "properties": {**props, "speech": {"type": "string"}},
                          "required": list(dict.fromkeys([*schema.get("required", list(props)), "speech"]))}
                prompt += f"\n\n{SPEECH_FIELD}"
            parts, usage, completed = [], {}, False
            async with aclosing(self._events([{"role": "user", "content": prompt}], name, think,
                                             system or self.system, schema, deadline)) as events:
                async for event in events:
                    if text := self._event_text(event):
                        parts.append(text)
                    if event.get("type") == "turn.completed":
                        completed, usage = True, event.get("usage") or {}
            text = "".join(parts)
            data = first_json(text)
            if schema and data is not None:
                data = _optional_fields(data, schema)
            if not completed or generation != self._generation or data is None or schema and not complete(data, schema):
                raise CodexError("ChatGPT returned incomplete JSON or the conversation was reset; try again.")
            spoken = data.get("speech", "")
            result = Result(text=text, speech=spoken.strip() if isinstance(spoken, str) else "", usage=usage)
            return data, result
        except (OSError, ValueError, asyncio.TimeoutError, CodexError) as exc:
            return None, self._failure(exc)
        finally:
            if acquired:
                self._lock.release()

    async def reset(self) -> None:
        self._generation += 1
        self._history.clear()
        await asyncio.gather(*(self._stop(proc) for proc in tuple(self._procs)))

    async def close(self) -> None:
        self._closed = True
        await self.reset()
        if self._starting:
            try:
                await asyncio.wait_for(asyncio.shield(asyncio.gather(*tuple(self._starting), return_exceptions=True)), 3)
            except asyncio.TimeoutError:
                pass  # late launches observe _closed and stop their own child
