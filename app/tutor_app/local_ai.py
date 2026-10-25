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
CHAT_TIMEOUT = 300


class LocalError(Exception):
    """A local request failed without making a cloud request."""


class LocalAI:
    def __init__(self, system: str, speech: bool = False):
        from .ai import Result
        self.system, self.speech = system, speech
        self.last = Result()
        self._history: dict[tuple[str, bool | str | None, bool], list[dict]] = {}
        self._shown: dict[tuple[str, bool | str | None, bool], tuple[str, str]] = {}
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
        self._mlx = None
        self._prepared_ollama: str | None = None

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
        if "think" in payload:
            effort = self._effort(model, payload["think"])
            payload = {key: value for key, value in payload.items() if key != "think"}
            if effort is not None:
                payload["think"] = effort
        context = self._contexts.get(model, local_models.CONTEXT_LENGTH.get(model))
        return {**payload, "options": {**payload.get("options", {}), "num_ctx": context}} if context else payload

    @staticmethod
    def _effort(model: str, value: bool | str):
        try:
            effort = local_models.thinking_value(model, value)
        except ValueError as exc:
            raise LocalError(str(exc)) from exc
        if effort is None and value is not False:
            raise LocalError("This local model does not support Think first. Switch it off in Settings, "
                             "or choose a model that supports thinking.")
        return effort

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
        """Only the registered GPT payload enters the private MLX runtime."""
        deadline, generation = time.monotonic() + timeout, self._generation
        model = payload.get("model", "")
        if model == "mlx:gpt-oss:20b":
            self._check(model)
            await self._prepare_mlx(deadline)
            self._ready(model, generation, deadline)
            if self._mlx is None or self._mlx._closed:
                from .mlx_local import MLXLocal
                self._mlx = MLXLocal()
            worker, completed = self._mlx, False
            try:
                async with aclosing(worker.events(payload, deadline - time.monotonic())) as events:
                    async for event in events:
                        self._ready(model, generation, deadline)
                        if self._mlx is not worker:
                            raise LocalError("The local MLX worker was replaced; try again.")
                        completed = event.get("done") is True
                        yield event
            finally:
                if not completed and self._mlx is worker:
                    await self._release_mlx()
            return
        if model.startswith("mlx:"):
            raise LocalError("Choose the registered GPT-OSS MLX model in Settings.")
        if local_models.is_local("ollama:" + model):
            await self._release_mlx()
            self._ready("ollama:" + model, generation, deadline)
        async with aclosing(self._http_events(payload, deadline - time.monotonic(), path)) as events:
            async for event in events:
                yield event

    def _ready(self, model: str, generation: int, deadline: float) -> None:
        self._check(model)
        if generation != self._generation or self._closed:
            raise LocalError("The local conversation was reset; try again.")
        if time.monotonic() >= deadline:
            raise asyncio.TimeoutError

    async def _release_mlx(self) -> None:
        worker, self._mlx = self._mlx, None
        if worker is not None:
            await worker.close()

    async def _ollama_residency(self, deadline: float) -> set[str] | None:
        """None means connection refused; an empty set is a verified empty scheduler."""
        loaded = None
        try:
            async with aclosing(self._http_events({}, deadline - time.monotonic(), "/api/ps",
                                                  method="GET", start_service=False)) as events:
                async for event in events:
                    models = event.get("models")
                    if not isinstance(models, list):
                        raise LocalError("Could not check Ollama's loaded models. Close loaded Ollama models, then retry.")
                    loaded = set()
                    for model in models:
                        name = (model.get("model") or model.get("name")) if isinstance(model, dict) else None
                        if not isinstance(name, str) or not name:
                            raise LocalError("Could not check Ollama's loaded models. Close loaded Ollama models, then retry.")
                        loaded.add(name)
        except ConnectionRefusedError:
            return None  # A stopped server has no scheduler residency; never start it just to check MLX safety.
        if loaded is None:
            raise LocalError("Ollama did not report its loaded models. Close loaded Ollama models, then retry.")
        return loaded

    async def _prepare_mlx(self, deadline: float) -> None:
        """Release only this client's acknowledged Ollama load; never evict another app's model."""
        loaded = await self._ollama_residency(deadline)
        if not loaded:
            self._prepared_ollama = None  # The server stopped or the previously prepared model expired.
            return
        model = self._prepared_ollama
        if model is None or loaded != {model.removeprefix("ollama:")}:
            raise LocalError("Another model is still loaded in Ollama. Stop it in the app that loaded it, "
                             "then retry GPT-OSS MLX so both large runtimes do not share memory.")
        acknowledged = False
        request = {"model": model.removeprefix("ollama:"), "messages": [],
                   "stream": False, "keep_alive": 0}
        async with aclosing(self._http_events(request, deadline - time.monotonic(), start_service=False)) as events:
            async for event in events:
                message = event.get("message") or {}
                if (event.get("done") is True and event.get("done_reason") == "unload"
                        and not message.get("content") and not message.get("thinking") and not event.get("error")):
                    acknowledged = True
        if not acknowledged:
            raise LocalError("Ollama did not confirm release of the tutor's local model. "
                             "Stop that model in Ollama, then try GPT-OSS MLX again.")
        if await self._ollama_residency(deadline):
            raise LocalError("A model is still loaded in Ollama. Stop it in the app that loaded it, "
                             "then retry GPT-OSS MLX so both large runtimes do not share memory.")
        self._prepared_ollama = None

    async def _http_events(self, payload: dict, timeout: float, path: str = "/api/chat", *,
                           method: str = "POST", start_service: bool = True) -> AsyncIterator[dict]:
        """Read NDJSON independently of HTTP chunk boundaries; closing this generator closes its socket."""
        deadline = time.monotonic() + timeout
        generation = self._generation
        if start_service:
            reader, writer = await self._connect(deadline)
        else:
            reader, writer = await asyncio.wait_for(asyncio.open_connection(HOST, PORT, limit=_LIMIT),
                                                    max(.001, deadline - time.monotonic()))
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
            data = json.dumps(payload).encode() if method == "POST" else b""
            if generation != self._generation or self._closed:
                raise LocalError("The local conversation was reset; try again.")
            selected = "ollama:" + payload.get("model", "")
            if local_models.is_local(selected):
                self._check(selected)
            if time.monotonic() >= deadline:
                raise asyncio.TimeoutError
            writer.write((f"{method} {path} HTTP/1.1\r\nHost: {HOST}:{PORT}\r\nContent-Type: application/json\r\n"
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

    async def _preload(self, payload: dict, timeout: float, model: str) -> float:
        """Require scheduler readiness without a prompt; the caller already owns the inference lock."""
        started, generation = time.monotonic(), self._generation
        deadline = started + timeout
        request = {"model": payload["model"], "messages": [], "stream": False,
                   "keep_alive": payload["keep_alive"]}
        if "options" in payload:
            request["options"] = payload["options"]
        self._phase(model, "loading")
        async with aclosing(self._events(request, timeout)) as events:
            async for event in events:
                if event.get("error"):
                    raise LocalError(f"Ollama: {event['error']}")
                if event.get("done"):
                    message = event.get("message") or {}
                    if (event["done"] is not True or event.get("done_reason") != "load"
                            or message.get("content") or message.get("thinking")):
                        raise LocalError("Ollama did not confirm that the local model is loaded. Try again.")
                    self._ready(model, generation, deadline)
                    if model.startswith("ollama:"):
                        self._prepared_ollama = model
                    return time.monotonic() - started
        raise LocalError("Ollama ended the preload without confirming readiness; try again.")

    async def _chat_events(self, payload: dict, timeout: float, model: str) -> AsyncIterator[dict]:
        """Leave room for the answer after thinking; retry a context-exhausted empty Gemma reply once."""
        started = time.monotonic()
        deadline = started + timeout
        generation, preload_seconds = self._generation, 0
        thinking_started, thinking_seconds = None, 0.0
        spent: dict[str, int | float] = {}
        counters = ("total_duration", "load_duration", "prompt_eval_duration", "eval_duration",
                    "prompt_eval_count", "prompt_eval_cached_count", "eval_count")
        payload = self._with_context(payload, model)
        for attempt in range(2):
            visible, reasoned, retry = False, False, False
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise asyncio.TimeoutError
            preload_seconds += await self._preload(payload, remaining, model)
            if generation != self._generation or self._closed:
                raise LocalError("The local conversation was reset; try again.")
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise asyncio.TimeoutError
            self._phase(model, "waiting")
            async with aclosing(self._events(payload, remaining)) as events:
                async for event in events:
                    self._ready(model, generation, deadline)
                    message = event.get("message") or {}
                    if message.get("thinking"):
                        if thinking_started is None:
                            thinking_started = time.monotonic()
                        reasoned = True
                        self._phase(model, "thinking")
                    if message.get("content"):
                        if thinking_started is not None:
                            thinking_seconds += time.monotonic() - thinking_started
                            thinking_started = None
                        visible = visible or bool(message["content"].strip())
                        self._phase(model, "generating")
                    if event.get("done") and thinking_started is not None:
                        thinking_seconds += time.monotonic() - thinking_started
                        thinking_started = None
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
                        values = {key: spent.get(key, 0) + (event.get(key) or 0) for key in counters
                                  if not model.startswith("mlx:") or key in event or key in spent}
                        event = {**event, **values,
                                 "_retry_count": attempt, "_elapsed_seconds": time.monotonic() - started,
                                 "_preload_seconds": preload_seconds, "_preload_count": attempt + 1,
                                 "_thinking_seconds": thinking_seconds}
                    if isinstance(event.get("eval_count"), int):
                        self._phase(model, self.progress_for(model).get("phase", "waiting"), tokens=event["eval_count"])
                    yield event
            if not retry:
                return

    @staticmethod
    def _performance(event: dict, model: str, first_token: float | None) -> dict:
        unknown = model.startswith("mlx:")
        def number(key):
            return event.get(key) if unknown else event.get(key) or 0
        def seconds(key):
            value = number(key)
            return max(0, value) / 1_000_000_000 if value is not None else None
        duration, count = seconds("eval_duration"), number("eval_count")
        speed = count / duration if duration and count is not None else None if unknown else 0
        return {"model": model, "total_seconds": max(seconds("total_duration") or 0, event.get("_elapsed_seconds") or 0),
                "engine_seconds": seconds("total_duration"), "retry_count": event.get("_retry_count", 0),
                "preload_seconds": event.get("_preload_seconds", 0), "preload_count": event.get("_preload_count", 0),
                "load_seconds": seconds("load_duration"),
                "thinking_seconds": max(0, event.get("_thinking_seconds") or 0),
                "prompt_seconds": seconds("prompt_eval_duration"), "generation_seconds": duration,
                "input_tokens": number("prompt_eval_count"), "output_tokens": count,
                "cached_input_tokens": number("prompt_eval_cached_count"),
                "tokens_per_second": speed, "first_token_seconds": first_token}

    @staticmethod
    def _failure(exc: Exception, text: str = ""):
        from .ai import Result
        message = ("The local AI took too long to answer; try again." if isinstance(exc, asyncio.TimeoutError)
                   else str(exc) if isinstance(exc, LocalError)
                   else "The local AI stopped or sent an unreadable reply. Check Ollama and the external SSD, then try again.")
        return Result(ok=False, status="error", message=message, text=text)

    async def stream(self, prompt: str, image: Path | None = None, model: str | None = None,
                     think: bool | str = False) -> AsyncIterator[str]:
        started = time.monotonic()
        try:
            async with self._queued(CHAT_TIMEOUT, model) as remaining:
                waited = time.monotonic() - started
                async with aclosing(self._stream(prompt, image, model, think, remaining)) as reply:
                    async for part in reply:
                        yield part
                if self.last.ok and self.last.performance:
                    self.last.performance["total_seconds"] = max(self.last.performance.get("total_seconds", 0),
                                                                 time.monotonic() - started)
                    if self.last.performance.get("first_token_seconds") is not None:
                        self.last.performance["first_token_seconds"] += waited
        except (LocalError, asyncio.TimeoutError) as exc:
            if model == "mlx:gpt-oss:20b":
                await self._release_mlx()
            self.last = self._failure(exc)

    async def _stream(self, prompt: str, image: Path | None, model: str | None,
                      think: bool | str, timeout: float) -> AsyncIterator[str]:
        from .ai import MEDIA, Result, SPEECH_MARK, json_instruction
        from .local_chat import chat_system
        from .local_reply import ReplyDecoder, chat_schema
        started = time.monotonic()
        generation = self._generation
        parts, first, finished = [], None, False
        self.last = Result(ok=False, status="error", message="The local reply was cancelled; try again.")
        decoder = ReplyDecoder(speech=self.speech)
        try:
            name = self._check(model)
            key = (model, self._effort(model, think), self.speech)
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
            schema = chat_schema(self.speech)
            system = chat_system(self.system, speech=self.speech) + "\n\n" + json_instruction(schema)
            payload = {"model": name, "stream": True, "think": think, "format": schema,
                       "keep_alive": local_models.KEEP_ALIVE[model],
                       "messages": [{"role": "system", "content": system},
                                    *history, user]}
            async with aclosing(self._chat_events(payload, timeout, model)) as events:
                async for event in events:
                    if event.get("error"):
                        raise LocalError(f"Ollama: {event['error']}")
                    text = (event.get("message") or {}).get("content") or ""
                    if text:
                        if visible := decoder.feed(text):
                            if first is None:
                                first = time.monotonic() - started
                            parts.append(visible)
                            yield visible
                    if event.get("done"):
                        self._check(model)  # an SSD removed during inference must not become a successful call
                        if generation != self._generation:
                            raise LocalError("The local conversation was reset; try again.")
                        text, speech = decoder.finish()
                        if speech:
                            text = text.rstrip()  # preserve the existing spoken-reply result contract
                        if not text.strip():
                            raise LocalError("The local AI returned an empty reply; try again.")
                        performance = self._performance(event, model, first)
                        performance["total_seconds"] = max(performance["total_seconds"], time.monotonic() - started)
                        self.last = Result(text=text, speech=speech.strip(), performance=performance)
                        history_text = text + (f"\n{SPEECH_MARK} {speech}" if speech else "")
                        self._history[key] = [*history, user, {"role": "assistant", "content": history_text}]
                        if "images" in user:
                            self._shown[key] = image_key
                        finished = True
                        self._phase(model, "done")
                        break
            if not finished:
                raise LocalError("Ollama ended the reply early; try again.")
        except (OSError, ValueError, asyncio.IncompleteReadError, asyncio.LimitOverrunError,
                asyncio.TimeoutError, LocalError) as exc:
            self.last = self._failure(exc, "".join(parts))
            if isinstance(exc, asyncio.TimeoutError) and self.progress_for(model).get("phase") == "thinking":
                self.last.message = ("The local model was still thinking when the chat time limit expired. "
                                     "Think first can take minutes on this Mac. Switch it off for routine "
                                     "questions, or choose a faster model.")
        finally:
            if not finished:
                # Neither a partial user turn nor its partial assistant reply is committed to memory.
                self.last.ok = False
                self._phase(model, "error")
                if model == "mlx:gpt-oss:20b":
                    await self._release_mlx()

    async def one_shot(self, prompt: str, schema: dict | None = None, model: str | None = None,
                       timeout: float = 120, system: str | None = None,
                       speech: bool = False, think: bool | str = False, image: bytes | None = None):
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
            if model == "mlx:gpt-oss:20b":
                await self._release_mlx()
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
                await self._preload(payload, remaining, model)
                self._phase(model, "done")
                return Result()
        except (OSError, ValueError, asyncio.IncompleteReadError, asyncio.LimitOverrunError,
                asyncio.TimeoutError, LocalError) as exc:
            if model == "mlx:gpt-oss:20b":
                await self._release_mlx()
            return self._failure(exc)

    async def _one_shot(self, prompt: str, schema: dict | None, model: str | None,
                        timeout: float, system: str | None, speech: bool, think: bool | str, image: bytes | None = None):
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
            payload = {"model": name, "stream": True, "think": think, "keep_alive": local_models.KEEP_ALIVE[model],
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
        native_lock = getattr(self._mlx, "_lock", None)
        active_native = self._active_model == "mlx:gpt-oss:20b" and self._lock.locked()
        if self._closed or active_native or native_lock is not None and native_lock.locked():
            await self._release_mlx()

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
