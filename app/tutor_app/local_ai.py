"""Ollama tutoring over loopback HTTP, with private histories and cancellable streams.

Only the installed SSD models are accepted. Reply text and speech share the Claude client's parsing; local
performance stays in Result.performance and never contributes to the Claude subscription's counters.
"""
from __future__ import annotations

import asyncio
import base64
import hashlib
import json
import os
import shutil
import time
from contextlib import aclosing, asynccontextmanager
from pathlib import Path
from typing import AsyncIterator

from . import local_models


HOST, PORT = "127.0.0.1", 11434
_LIMIT = 4 * 1024 * 1024


class LocalError(Exception):
    """A local request failed without making a cloud request."""


class LocalAI:
    def __init__(self, system: str, speech: bool = False):
        from .ai import Result
        self.system, self.speech = system, speech
        self.last = Result()
        self._history: dict[tuple[str, bool, bool], list[dict]] = {}
        self._shown: dict[tuple[str, bool, bool], tuple[str, str]] = {}
        self._lock = asyncio.Lock()
        self._service_lock = asyncio.Lock()
        self._writers: set[asyncio.StreamWriter] = set()
        self._owned: asyncio.subprocess.Process | None = None
        self._starting: asyncio.Task | None = None
        self._generation = 0
        self._closed = False
        self.web_enabled = False
        self._progress: dict[str, dict] = {}
        self._active_model: str | None = None
        self._contexts: dict[str, int] = {}

    def progress_for(self, model: str) -> dict:
        """Only public phase and exact API counters; hidden reasoning is never retained or exposed."""
        return dict(self._progress.get(model, {}))

    def _phase(self, model: str | None, phase: str, **values) -> None:
        if local_models.is_local(model):
            self._progress[model] = {**self._progress.get(model, {"started": time.monotonic()}),
                                     "phase": phase, **values}

    def _queued_phase(self, model: str | None) -> None:
        if model != self._active_model and local_models.is_local(model):
            self._progress[model] = {"phase": "queued", "started": time.monotonic()}

    def _started_phase(self, model: str | None) -> None:
        if local_models.is_local(model):
            self._progress[model] = {"phase": "preparing", "started": time.monotonic()}

    def _with_context(self, payload: dict, model: str) -> dict:
        if "think" in payload and isinstance(payload["think"], bool):
            effort = local_models.thinking_value(model, payload["think"])
            if effort is None:
                if payload["think"]:
                    raise LocalError("This local model does not support Think first. Switch it off in Settings, "
                                     "or choose a model that supports thinking.")
                payload = {key: value for key, value in payload.items() if key != "think"}
            else:
                payload = {**payload, "think": effort}
        context = self._contexts.get(model, local_models.CONTEXT_LENGTH.get(model))
        return {**payload, "options": {**payload.get("options", {}), "num_ctx": context}} if context else payload

    @staticmethod
    def _decode(line: bytes) -> dict:
        event = json.loads(line)
        message = event.get("message") if isinstance(event, dict) else None
        if not isinstance(event, dict) or (message is not None and not isinstance(message, dict)):
            raise LocalError("Ollama sent an unreadable reply; try again.")
        if message and not isinstance(message.get("content", ""), str):
            raise LocalError("Ollama sent an unreadable reply; try again.")
        for key in ("total_duration", "load_duration", "prompt_eval_duration", "eval_duration",
                    "prompt_eval_count", "prompt_eval_cached_count", "eval_count"):
            if key in event and (not isinstance(event[key], (int, float)) or event[key] < 0):
                raise LocalError("Ollama sent unreadable performance data; try again.")
        return event

    @staticmethod
    def _check(model: str | None) -> str:
        if not local_models.is_local(model):
            raise LocalError("Choose an installed local model in Settings.")
        if model not in local_models.available_models():
            raise LocalError("The local model is unavailable. Connect the external SSD containing LocalAI, then try again.")
        return model.removeprefix("ollama:")

    async def _connect(self, deadline: float):
        async def connect():
            pair = await asyncio.wait_for(asyncio.open_connection(HOST, PORT, limit=_LIMIT),
                                          max(0.001, deadline - time.monotonic()))
            if self._closed:
                pair[1].close()
                await pair[1].wait_closed()
                raise LocalError("Local AI is closed.")
            return pair
        if self._closed:
            raise LocalError("Local AI is closed.")
        try:
            return await connect()
        except OSError:
            pass
        await asyncio.wait_for(self._service_lock.acquire(), max(0.001, deadline - time.monotonic()))
        try:
            try:
                return await connect()  # another request may have started it meanwhile
            except OSError:
                pass
            if self._closed:
                raise LocalError("Local AI is closed.")
            if self._owned is None or self._owned.returncode is not None:
                binary = shutil.which("ollama")
                if not binary:
                    raise LocalError("Ollama is not installed. Install Ollama, then try the local model again.")
                env = {**os.environ, "OLLAMA_MODELS": str(local_models.ROOT), "OLLAMA_HOST": f"{HOST}:{PORT}",
                       "OLLAMA_NO_CLOUD": os.environ.get("OLLAMA_NO_CLOUD", "0") if self.web_enabled else "1",
                       "OLLAMA_MAX_LOADED_MODELS": "1", "OLLAMA_NUM_PARALLEL": "1"}
                if self._starting is None or self._starting.done():
                    self._starting = asyncio.create_task(self._start_service(binary, env))
                started = await asyncio.wait_for(asyncio.shield(self._starting),
                                                 max(0.001, deadline - time.monotonic()))
                if not started:
                    raise LocalError("Ollama could not start. Open Ollama, then try the local model again.")
                if self._closed:
                    await self._stop_owned()
                    raise LocalError("Local AI is closed.")
            while time.monotonic() < deadline:
                if self._closed:
                    raise LocalError("Local AI is closed.")
                try:
                    return await connect()
                except OSError:
                    if self._closed:
                        raise LocalError("Local AI is closed.")
                    if self._owned.returncode is not None:
                        raise LocalError("Ollama could not start. Open Ollama, then try the local model again.")
                    await asyncio.sleep(min(0.1, max(0, deadline - time.monotonic())))
            raise asyncio.TimeoutError
        finally:
            self._service_lock.release()

    async def _start_service(self, binary: str, env: dict) -> bool:
        """Retain a launch even when its request is cancelled, so close can still stop the resulting child."""
        try:
            self._owned = await asyncio.create_subprocess_exec(
                binary, "serve", env=env, stdout=asyncio.subprocess.DEVNULL, stderr=asyncio.subprocess.DEVNULL)
        except OSError:
            return False
        if self._closed:
            await self._stop_owned()
        return True

    async def _events(self, payload: dict, timeout: float, path: str = "/api/chat") -> AsyncIterator[dict]:
        """Read NDJSON independently of HTTP chunk boundaries; closing this generator closes its socket."""
        deadline = time.monotonic() + timeout
        reader, writer = await self._connect(deadline)
        self._writers.add(writer)

        async def read(awaitable):
            return await asyncio.wait_for(awaitable, max(0.001, deadline - time.monotonic()))

        async def body(headers):
            if "chunked" in headers.get("transfer-encoding", "").lower():
                while True:
                    line = await read(reader.readline())
                    size = int(line.strip().split(b";", 1)[0], 16)
                    if size == 0:
                        return
                    if size > _LIMIT:
                        raise LocalError("Ollama sent an unreadable reply; try again.")
                    yield await read(reader.readexactly(size))
                    if await read(reader.readexactly(2)) != b"\r\n":
                        raise LocalError("Ollama sent an unreadable reply; try again.")
            elif "content-length" in headers:
                remaining = int(headers["content-length"])
                while remaining:
                    piece = await read(reader.read(min(65536, remaining)))
                    if not piece:
                        raise LocalError("Ollama ended the reply early; try again.")
                    remaining -= len(piece)
                    yield piece
            else:
                while piece := await read(reader.read(65536)):
                    yield piece

        try:
            data = json.dumps(payload).encode()
            writer.write((f"POST {path} HTTP/1.1\r\nHost: {HOST}:{PORT}\r\nContent-Type: application/json\r\n"
                          f"Content-Length: {len(data)}\r\nConnection: close\r\n\r\n").encode() + data)
            await read(writer.drain())
            header = (await read(reader.readuntil(b"\r\n\r\n"))).decode("latin-1")
            rows = header.split("\r\n")
            status = int(rows[0].split()[1])
            headers = {key.lower(): value.strip() for key, value in
                       (line.split(":", 1) for line in rows[1:] if ":" in line)}
            pending = b""
            async for piece in body(headers):
                pending += piece
                if len(pending) > _LIMIT:
                    raise LocalError("Ollama sent an unreadable reply; try again.")
                if status != 200:
                    continue
                while b"\n" in pending:
                    line, pending = pending.split(b"\n", 1)
                    if line.strip():
                        yield self._decode(line)
            if status != 200:
                try:
                    message = json.loads(pending).get("error", "")
                except (ValueError, AttributeError):
                    message = ""
                raise LocalError(f"Ollama: {message or f'local request failed (HTTP {status})'}. "
                                 "Check the local model in Ollama, then try again.")
            if pending.strip():
                yield self._decode(pending)
        finally:
            self._writers.discard(writer)
            writer.close()
            try:
                await writer.wait_closed()
            except OSError:
                pass

    async def _chat_events(self, payload: dict, timeout: float, model: str) -> AsyncIterator[dict]:
        """Leave room for the answer after thinking; retry a context-exhausted empty Gemma reply once."""
        started = time.monotonic()
        deadline = started + timeout
        spent: dict[str, int | float] = {}
        counters = ("total_duration", "load_duration", "prompt_eval_duration", "eval_duration",
                    "prompt_eval_count", "prompt_eval_cached_count", "eval_count")
        payload = self._with_context(payload, model)
        for attempt in range(2):
            visible, reasoned, retry = False, False, False
            self._phase(model, "waiting")
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise asyncio.TimeoutError
            async with aclosing(self._events(payload, remaining)) as events:
                async for event in events:
                    message = event.get("message") or {}
                    if message.get("thinking"):
                        reasoned = True
                        self._phase(model, "thinking")
                    if message.get("content"):
                        visible = visible or bool(message["content"].strip())
                        self._phase(model, "generating")
                    if event.get("done") and not visible and reasoned and event.get("done_reason") == "length":
                        context = (payload.get("options") or {}).get("num_ctx", 0)
                        maximum = local_models.MAX_CONTEXT_LENGTH.get(model, 0)
                        if attempt == 0 and context and context < maximum:
                            spent = {key: spent.get(key, 0) + (event.get(key) or 0) for key in counters}
                            self._contexts[model] = min(context * 2, maximum)
                            payload = self._with_context(payload, model)
                            self._phase(model, "preparing")
                            retry = True
                            break
                        raise LocalError("The local AI filled its context while thinking. Start a fresh chat, then try again.")
                    if event.get("done"):
                        event = {**event, **{key: spent.get(key, 0) + (event.get(key) or 0) for key in counters},
                                 "_retry_count": attempt, "_elapsed_seconds": time.monotonic() - started}
                    if isinstance(event.get("eval_count"), int):
                        self._phase(model, self.progress_for(model).get("phase", "waiting"), tokens=event["eval_count"])
                    yield event
            if not retry:
                return

    @staticmethod
    def _performance(event: dict, model: str, first_token: float | None) -> dict:
        def seconds(key):
            return max(0, event.get(key) or 0) / 1_000_000_000
        duration = seconds("eval_duration")
        count = event.get("eval_count") or 0
        return {"model": model, "total_seconds": max(seconds("total_duration"), event.get("_elapsed_seconds") or 0),
                "engine_seconds": seconds("total_duration"), "retry_count": event.get("_retry_count", 0),
                "load_seconds": seconds("load_duration"),
                "prompt_seconds": seconds("prompt_eval_duration"), "generation_seconds": duration,
                "input_tokens": event.get("prompt_eval_count") or 0, "output_tokens": count,
                "cached_input_tokens": event.get("prompt_eval_cached_count") or 0,
                "tokens_per_second": count / duration if duration else 0, "first_token_seconds": first_token}

    @staticmethod
    def _failure(exc: Exception, text: str = ""):
        from .ai import Result
        message = ("The local AI took too long to answer; try again." if isinstance(exc, asyncio.TimeoutError)
                   else str(exc) if isinstance(exc, LocalError)
                   else "The local AI stopped or sent an unreadable reply. Check Ollama and the external SSD, then try again.")
        return Result(ok=False, status="error", message=message, text=text)

    async def stream(self, prompt: str, image: Path | None = None, model: str | None = None,
                     think: bool = False) -> AsyncIterator[str]:
        from .ai import MEDIA, Result, SPEECH_RULE, SpeechFilter, split_speech
        started = time.monotonic()
        generation = self._generation
        self._queued_phase(model)
        async with self._lock:
            if generation != self._generation:
                raise asyncio.CancelledError
            self._active_model = model
            self._started_phase(model)
            parts, first, finished = [], None, False
            self.last = Result(ok=False, status="error", message="The local reply was cancelled; try again.")
            spoken = SpeechFilter()
            try:
                name = self._check(model)
                key = (model, bool(think), self.speech)
                history = self._history.get(key, [])
                user = {"role": "user", "content": prompt}
                image_key = None
                if image is not None:
                    if not local_models.supports_vision(model):
                        raise LocalError("This local model cannot read images. Choose a model with native vision "
                                         "or an available local vision helper.")
                    if image.suffix.lower() not in MEDIA:
                        raise LocalError("The question image format is unsupported. Use PNG, JPEG, GIF or WebP.")
                    try:
                        pixels = image.read_bytes()
                    except OSError as exc:
                        raise LocalError("The question image could not be read. Restore the image file, then retry.") from exc
                    if not pixels:
                        raise LocalError("The question image is empty. Restore the image file, then retry.")
                    image_key = (str(image), hashlib.sha256(pixels).hexdigest())
                    if self._shown.get(key) != image_key:
                        user["images"] = [base64.b64encode(pixels).decode()]
                payload = {"model": name, "stream": True, "think": bool(think), "keep_alive": local_models.KEEP_ALIVE[model],
                           "messages": [{"role": "system", "content": self.system + (SPEECH_RULE if self.speech else "")},
                                        *history, user]}
                async with aclosing(self._chat_events(payload, 300, model)) as events:
                    async for event in events:
                        if event.get("error"):
                            raise LocalError(f"Ollama: {event['error']}")
                        text = (event.get("message") or {}).get("content") or ""
                        if text:
                            if first is None:
                                first = time.monotonic() - started
                            parts.append(text)
                            if visible := spoken.feed(text):
                                yield visible
                        if event.get("done"):
                            self._check(model)  # an SSD removed during inference must not become a successful call
                            if generation != self._generation:
                                raise LocalError("The local conversation was reset; try again.")
                            text, speech = split_speech("".join(parts))
                            if not text.strip():
                                raise LocalError("The local AI returned an empty reply; try again.")
                            performance = self._performance(event, model, first)
                            performance["total_seconds"] = max(performance["total_seconds"], time.monotonic() - started)
                            self.last = Result(text=text, speech=speech, performance=performance)
                            self._history[key] = [*history, user, {"role": "assistant", "content": "".join(parts)}]
                            if "images" in user:
                                self._shown[key] = image_key
                            finished = True
                            self._phase(model, "done")
                            break
                if not finished:
                    raise LocalError("Ollama ended the reply early; try again.")
                if tail := spoken.finish():
                    yield tail
            except (OSError, ValueError, asyncio.IncompleteReadError, asyncio.LimitOverrunError,
                    asyncio.TimeoutError, LocalError) as exc:
                self.last = self._failure(exc, split_speech("".join(parts))[0])
            finally:
                if not finished:
                    # Neither a partial user turn nor its partial assistant reply is committed to memory.
                    self.last.ok = False
                    self._phase(model, "error")
                self._active_model = None

    async def one_shot(self, prompt: str, schema: dict | None = None, model: str | None = None,
                       timeout: float = 120, system: str | None = None,
                       speech: bool = False, think: bool = False, image: bytes | None = None):
        started = time.monotonic()
        try:
            self._check(model)
            async with self._queued(timeout, model) as remaining:
                waited = time.monotonic() - started
                data, result = await self._one_shot(prompt, schema, model, remaining, system, speech, think,
                                                   **({"image": image} if image is not None else {}))
                if result.ok and result.performance:
                    result.performance["total_seconds"] = max(result.performance.get("total_seconds", 0),
                                                               time.monotonic() - started)
                    if result.performance.get("first_token_seconds") is not None:
                        result.performance["first_token_seconds"] += waited
                return data, result
        except (asyncio.TimeoutError, LocalError) as exc:
            return None, self._failure(exc)

    async def describe_image(self, image: bytes, prompt: str, *, schema: dict, model: str,
                             timeout: float, system: str):
        """Extract visible image data without tutor history, speech, thinking or shared reply changes."""
        return await self.one_shot(prompt, schema=schema, model=model, timeout=timeout, system=system,
                                   speech=False, think=False, image=image)

    @asynccontextmanager
    async def _queued(self, timeout: float, model: str | None = None):
        """Keep one inference or preload active; time spent waiting belongs to the caller's deadline."""
        deadline = time.monotonic() + timeout
        generation = self._generation
        self._queued_phase(model)
        try:
            await asyncio.wait_for(self._lock.acquire(), max(0.001, timeout))
        except BaseException:
            if model != self._active_model:
                self._phase(model, "error")
            raise
        if generation != self._generation:
            self._lock.release()
            raise asyncio.CancelledError
        self._active_model = model
        self._started_phase(model)
        try:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise asyncio.TimeoutError
            yield remaining
        finally:
            if self.progress_for(model).get("phase") not in ("done", "error"):
                self._phase(model, "error")
            self._active_model = None
            self._lock.release()

    async def warm(self, model: str, timeout: float = 120):
        """Load the chosen model without generating a reply or changing conversation and performance state."""
        from .ai import Result
        try:
            self._check(model)
            async with self._queued(timeout, model) as remaining:
                name = self._check(model)
                payload = {"model": name, "messages": [], "stream": False, "keep_alive": local_models.KEEP_ALIVE[model]}
                payload = self._with_context(payload, model)
                async with aclosing(self._events(payload, remaining)) as events:
                    async for event in events:
                        if event.get("error"):
                            raise LocalError(f"Ollama: {event['error']}")
                        if event.get("done"):
                            self._check(model)
                            self._phase(model, "done")
                            return Result()
                raise LocalError("Ollama ended the preload early; try again.")
        except (OSError, ValueError, asyncio.IncompleteReadError, asyncio.LimitOverrunError,
                asyncio.TimeoutError, LocalError) as exc:
            return self._failure(exc)

    async def _one_shot(self, prompt: str, schema: dict | None, model: str | None,
                        timeout: float, system: str | None, speech: bool, think: bool, image: bytes | None = None):
        from .ai import Result, SPEECH_FIELD, complete, first_json, json_instruction
        started, first, parts = time.monotonic(), None, []
        try:
            name = self._check(model)
            if speech and self.speech and schema:
                schema = {**schema, "properties": {**schema.get("properties", {}), "speech": {"type": "string"}}}
                prompt += f"\n\n{SPEECH_FIELD}"
            if schema:
                prompt += f"\n\n{json_instruction(schema)}"
            user = {"role": "user", "content": prompt}
            if image is not None:
                if not image:
                    raise LocalError("The question image is empty. Restore the image file, then retry.")
                if not local_models.supports_vision(model):
                    raise LocalError("This local model cannot read images. Choose a model with native vision "
                                     "or an available local vision helper.")
                user["images"] = [base64.b64encode(image).decode()]
            payload = {"model": name, "stream": True, "think": bool(think), "keep_alive": local_models.KEEP_ALIVE[model],
                       "messages": [{"role": "system", "content": system or self.system},
                                    user]}
            if schema:
                payload["format"] = schema
            async with aclosing(self._chat_events(payload, timeout, model)) as events:
                async for event in events:
                    if event.get("error"):
                        raise LocalError(f"Ollama: {event['error']}")
                    text = (event.get("message") or {}).get("content") or ""
                    if text:
                        if first is None:
                            first = time.monotonic() - started
                        parts.append(text)
                    if event.get("done"):
                        self._check(model)
                        text = "".join(parts)
                        data = first_json(text)
                        if data is None or schema and not complete(data, schema):
                            raise LocalError("The local AI returned incomplete JSON; try again.")
                        spoken = data.get("speech", "")
                        result = Result(text=text, speech=spoken.strip() if isinstance(spoken, str) else "",
                                        performance=self._performance(event, model, first))
                        self._phase(model, "done")
                        return data, result
            raise LocalError("Ollama ended the reply early; try again.")
        except (OSError, ValueError, asyncio.IncompleteReadError, asyncio.LimitOverrunError,
                asyncio.TimeoutError, LocalError) as exc:
            return None, self._failure(exc)

    async def reset(self) -> None:
        self._generation += 1
        self._history.clear()
        self._shown.clear()
        for writer in tuple(self._writers):
            writer.close()

    async def close(self) -> None:
        self._closed = True
        await self.reset()
        if self._starting and not self._starting.done():
            try:
                await asyncio.wait_for(asyncio.shield(self._starting), 3)
            except asyncio.TimeoutError:
                pass  # a delayed launch still observes _closed and stops its child when it completes
        await self._stop_owned()

    async def _stop_owned(self) -> None:
        process, self._owned = self._owned, None
        if process and process.returncode is None:
            try:
                process.terminate()
                await asyncio.wait_for(process.wait(), 3)
            except asyncio.CancelledError:
                try:
                    if process.returncode is None:
                        process.kill()
                except ProcessLookupError:
                    pass
                await asyncio.shield(process.wait())
                raise
            except (ProcessLookupError, asyncio.TimeoutError):
                if process.returncode is None:
                    process.kill()
                    await process.wait()
