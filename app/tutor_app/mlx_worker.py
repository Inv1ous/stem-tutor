"""Private SSD MLX worker. Standard-library imports keep the tutor environment light.

Run with the SSD Python as ``python -m tutor_app.mlx_worker``. The parent owns
cancellation and termination when a GPU operation cannot observe its deadline.
Only bounded, correlated final-answer events are written to stdout.
"""
from __future__ import annotations

import copy
import gc
import json
import math
import os
import re
import select
import sys
import time
from contextlib import closing, redirect_stdout
from pathlib import Path
from types import SimpleNamespace

from .mlx_harmony import FinalOnlyLogitsProcessor, HarmonyError, HarmonyParser, HarmonyTokens


MODEL = "mlx:gpt-oss:20b"
LIMIT = 4 * 1024 * 1024
MAX_IDLE = 45 * 60
_UNPREPARED = object()


class WorkerError(ValueError):
    """A safe public worker error; never includes native reply or reasoning text."""


class _DiscardDetokenizer:
    """MLX stream_generate needs a decoder; this sink never retains any token."""
    last_segment = ""

    def reset(self):
        pass

    def add_token(self, token):
        pass

    def finalize(self):
        pass


def load_native_runtime(checkpoint: Path):
    """Import and initialize heavy libraries only inside the owned SSD process."""
    import mlx.core as mx
    from mlx_lm import load, stream_generate
    from mlx_lm.models.cache import make_prompt_cache
    from mlx_lm.sample_utils import make_sampler
    from outlines.backends.llguidance import LLGuidanceBackend
    from outlines.models import from_mlxlm

    # The original MXFP4/BF16 checkpoint is loaded as supplied, never converted.
    model, tokenizer = load(str(checkpoint), lazy=False, trust_remote_code=False,
                            tokenizer_config={"trust_remote_code": False, "local_files_only": True})
    backend = LLGuidanceBackend(from_mlxlm(model, tokenizer))

    def header_mask(logits, allowed):
        indices = mx.array(allowed)
        masked = mx.full(logits.shape, -float("inf"), dtype=logits.dtype)
        masked[:, indices] = logits[:, indices]
        return masked

    return SimpleNamespace(model=model, tokenizer=tokenizer, mx=mx, backend=backend,
                           stream_generate=stream_generate, make_sampler=make_sampler,
                           make_prompt_cache=make_prompt_cache, header_mask=header_mask)


def keep_alive_seconds(value=MAX_IDLE) -> float:
    if isinstance(value, str):
        match = re.fullmatch(r"(-?\d+(?:\.\d+)?)\s*(ms|s|m|h)?", value.strip())
        if not match:
            raise WorkerError("MLX received an invalid keep-alive duration.")
        seconds = float(match[1]) * {None: 1, "ms": .001, "s": 1, "m": 60, "h": 3600}[match[2]]
    elif isinstance(value, (int, float)) and not isinstance(value, bool):
        seconds = float(value)
    else:
        raise WorkerError("MLX received an invalid keep-alive duration.")
    if not math.isfinite(seconds):
        raise WorkerError("MLX received an invalid keep-alive duration.")
    return MAX_IDLE if seconds < 0 else min(seconds, MAX_IDLE)


class MLXWorker:
    def __init__(self, checkpoint: Path | None = None, *, loader=load_native_runtime):
        if checkpoint is None:
            from .local_models import MLX_CHECKPOINT
            checkpoint = MLX_CHECKPOINT
        self.checkpoint = Path(checkpoint)
        self._loader, self._runtime = loader, None
        self._prepared_epoch = _UNPREPARED
        self.idle_seconds = MAX_IDLE

    def identity(self, payload: dict) -> dict:
        return {"model": MODEL, "checkpoint": str(self.checkpoint),
                "worker_pid": os.getpid(), "_epoch": payload.get("_epoch")}

    @staticmethod
    def _deadline(payload: dict) -> float:
        deadline = payload.get("_deadline")
        if (isinstance(deadline, bool) or not isinstance(deadline, (int, float))
                or not math.isfinite(deadline) or time.monotonic() >= deadline):
            raise WorkerError("The MLX request deadline expired; try again.")
        return deadline

    def events(self, payload: dict):
        prepared_epoch, self._prepared_epoch = self._prepared_epoch, _UNPREPARED
        if not isinstance(payload, dict) or payload.get("model") != MODEL:
            raise WorkerError("The MLX worker accepts only its registered GPT-OSS checkpoint.")
        deadline = self._deadline(payload)
        messages = payload.get("messages")
        if not isinstance(messages, list) or any(
            not isinstance(item, dict) or item.get("role") not in {"system", "user", "assistant"}
            or not isinstance(item.get("content"), str) or item.get("images") for item in messages
        ):
            raise WorkerError("MLX received unsupported chat messages.")
        if messages and (prepared_epoch is _UNPREPARED or prepared_epoch != payload.get("_epoch")
                         or self._runtime is None):
            raise WorkerError("GPT-OSS requires a fresh empty preload before each question.")
        effort = payload.get("think", "low")
        if not isinstance(effort, str) or effort not in {"low", "medium", "high"}:
            raise WorkerError("GPT-OSS reasoning strength must be Low, Medium, or High.")
        schema = payload.get("format")
        if schema is not None and not isinstance(schema, dict):
            raise WorkerError("MLX requires a JSON object schema.")
        self.idle_seconds = keep_alive_seconds(payload.get("keep_alive", MAX_IDLE))
        if not self.checkpoint.is_dir():
            raise WorkerError("The GPT-OSS checkpoint is unavailable; connect the external SSD.")
        started = time.monotonic_ns()
        loaded = 0
        if self._runtime is None:
            self._runtime = self._loader(self.checkpoint)
            # lazy=False evaluates all weights before this identity can be ready.
            HarmonyTokens.from_tokenizer(self._runtime.tokenizer)
            loaded = time.monotonic_ns() - started
        self._deadline(payload)
        identity = self.identity(payload)
        if not messages:
            self._prepared_epoch = payload.get("_epoch")
            yield {**identity, "done": True, "done_reason": "load",
                   "message": {"role": "assistant", "content": ""},
                   "load_duration": loaded, "total_duration": time.monotonic_ns() - started}
            return
        try:
            for event in self._generate(payload, deadline):
                self._deadline(payload)
                yield {**identity, **event, "load_duration": loaded,
                       "total_duration": time.monotonic_ns() - started}
        except HarmonyError as error:
            raise WorkerError(str(error)) from None

    def _generate(self, payload: dict, deadline: float):
        runtime = self._runtime
        tokenizer = runtime.tokenizer
        tokens = HarmonyTokens.from_tokenizer(tokenizer)
        prompt_text = tokenizer.apply_chat_template(payload["messages"], tokenize=False,
                                                    add_generation_prompt=True,
                                                    reasoning_effort=payload.get("think", "low"))
        if not isinstance(prompt_text, str) or not prompt_text.endswith("<|start|>assistant"):
            raise WorkerError("The GPT-OSS chat template has an unsupported assistant prefix.")
        prompt = tokenizer.encode(prompt_text, add_special_tokens=False)
        parser = HarmonyParser(tokens)
        final_decoder = tokenizer.detokenizer
        # MLX's built-in stream decoder sees every generated token. Give a shallow
        # copy a discard sink so the native loop never stores decoded reasoning.
        stream_tokenizer = copy.copy(tokenizer)
        stream_tokenizer._detokenizer = _DiscardDetokenizer()
        grammar = None
        if payload.get("format") is not None:
            grammar = runtime.backend.get_json_schema_logits_processor(json.dumps(payload["format"]))
        processors = [FinalOnlyLogitsProcessor(
            tokens, grammar, lambda token: tokenizer.decode([token]), skip=len(prompt),
            encode=lambda header: tokenizer.encode(header, add_special_tokens=False),
            mask=runtime.header_mask)]
        options = payload.get("options", {})
        if not isinstance(options, dict):
            raise WorkerError("MLX received invalid generation options.")
        temperature = options.get("temperature", 1.0)
        if (isinstance(temperature, bool) or not isinstance(temperature, (int, float))
                or not math.isfinite(temperature) or temperature < 0):
            raise WorkerError("MLX received an invalid sampling temperature.")
        sampling = {"temp": temperature}
        for key in ("top_p", "top_k", "min_p"):
            if key in options:
                sampling[key] = options[key]

        def progress(processed, total):
            if time.monotonic() >= deadline:
                raise WorkerError("The MLX request deadline expired; try again.")

        yield {"message": {"role": "assistant", "content": ""}, "phase": "prompt"}
        response, thinking_reported, final_bytes = None, False, 0
        with closing(runtime.stream_generate(
            runtime.model, stream_tokenizer, prompt=prompt, max_tokens=-1,
            sampler=runtime.make_sampler(**sampling), logits_processors=processors,
            prompt_cache=runtime.make_prompt_cache(runtime.model), prompt_progress_callback=progress,
        )) as stream:
            for response in stream:
                if time.monotonic() >= deadline:
                    raise WorkerError("The MLX request deadline expired; try again.")
                # Ignore response.text: it comes from the deliberate discard sink.
                token = int(response.token)
                text = tokenizer.decode([token]) if parser.needs_text else ""
                visible = parser.feed(token, text)
                if parser.saw_analysis and not thinking_reported:
                    thinking_reported = True
                    yield {"message": {"role": "assistant", "content": "", "thinking": True},
                           "phase": "thinking"}
                if visible:
                    final_decoder.add_token(token)
                    piece = final_decoder.last_segment
                    final_bytes += len(piece.encode("utf-8"))
                    if final_bytes > LIMIT:
                        raise WorkerError("The MLX final reply exceeded the local reply limit.")
                    if piece:
                        yield {"message": {"role": "assistant", "content": piece}, "phase": "answer"}
        parser.finish()
        if response is None or response.finish_reason != "stop":
            raise WorkerError("GPT-OSS did not complete its final answer; try again.")
        final_decoder.finalize()
        piece = final_decoder.last_segment
        if final_bytes + len(piece.encode("utf-8")) > LIMIT:
            raise WorkerError("The MLX final reply exceeded the local reply limit.")
        if piece:
            yield {"message": {"role": "assistant", "content": piece}, "phase": "answer"}
        # Native generation counts include framing, reasoning and the final EOS.
        # Durations recover MLX's measured intervals from its corresponding TPS.
        metrics = {"prompt_eval_count": response.prompt_tokens,
                   "eval_count": response.generation_tokens, "final_eval_count": parser.final_tokens,
                   "mlx_peak_memory_gb": response.peak_memory}
        if response.prompt_tps > 0:
            metrics["prompt_eval_duration"] = round(response.prompt_tokens / response.prompt_tps * 1e9)
        if response.generation_tps > 0:
            metrics["eval_duration"] = round(response.generation_tokens / response.generation_tps * 1e9)
        # No native cached-token count is supplied. Omit it so the existing
        # decoder retains unknown as unknown without accepting nullable numbers.
        yield {"message": {"role": "assistant", "content": ""}, "done": True,
               "done_reason": response.finish_reason, "finish_reason": response.finish_reason,
               **metrics, "phase": "done"}

    def close(self):
        self._prepared_epoch = _UNPREPARED
        runtime, self._runtime = self._runtime, None
        if runtime is not None:
            mx = runtime.mx
            del runtime
            gc.collect()
            mx.clear_cache()


def read_request(stream):
    line = stream.readline(LIMIT + 1)
    if not line:
        return None
    if len(line) > LIMIT or not line.endswith(b"\n"):
        raise WorkerError("MLX received an oversized or unfinished protocol line.")
    try:
        request = json.loads(line)
    except (ValueError, UnicodeError):
        raise WorkerError("MLX received an unreadable protocol request.") from None
    if (not isinstance(request, dict) or not isinstance(request.get("id"), (str, int))
            or isinstance(request.get("id"), bool) or not isinstance(request.get("payload"), dict)):
        raise WorkerError("MLX received an invalid protocol request.")
    return request


def write_event(stream, request_id, event):
    line = (json.dumps({"id": request_id, "event": event}, ensure_ascii=False,
                       allow_nan=False, separators=(",", ":")) + "\n").encode("utf-8")
    if len(line) > LIMIT:
        raise WorkerError("The MLX response exceeded the protocol line limit.")
    stream.write(line)
    stream.flush()


def main() -> int:
    worker = MLXWorker()
    reader, writer = sys.stdin.buffer, sys.stdout.buffer
    try:
        while True:
            # The owned process exits and releases weights after bounded inactivity.
            if not select.select([reader], [], [], worker.idle_seconds)[0]:
                return 0
            try:
                request = read_request(reader)
            except WorkerError:
                return 2  # No trustworthy correlation ID; parent sees a worker failure.
            if request is None:
                return 0
            payload = request["payload"]
            try:
                # Third-party loader warnings cannot corrupt the private stdout pipe.
                with redirect_stdout(sys.stderr):
                    for event in worker.events(payload):
                        write_event(writer, request["id"], event)
            except Exception as error:
                message = str(error) if isinstance(error, WorkerError) else (
                    "GPT-OSS MLX could not complete the request; check the SSD runtime and try again.")
                write_event(writer, request["id"], {**worker.identity(payload), "error": message, "done": True})
                worker.close()
            if worker.idle_seconds == 0:
                return 0
    finally:
        worker.close()


if __name__ == "__main__":
    raise SystemExit(main())
