"""Private JSON-lines transport for the tutor's fixed SSD GPT-OSS worker.

Only the owned child imports MLX. No listening socket or shared service is created.
"""
from __future__ import annotations

import asyncio
import json
import os
import time
from pathlib import Path
from typing import AsyncIterator

from . import local_models
from .local_ai import LocalError

MODEL = "mlx:gpt-oss:20b"
_LIMIT = 4 * 1024 * 1024


class MLXLocal:
    def __init__(self):
        self._process: asyncio.subprocess.Process | None = None
        self._starting: asyncio.Task | None = None
        self._lock = asyncio.Lock()
        self._epoch = 0
        self._request = 0
        self._closed = False
        self._readiness: tuple[asyncio.subprocess.Process, int, str] | None = None

    def _check(self, deadline: float, process=None, epoch=None) -> None:
        if self._closed or epoch is not None and epoch != self._epoch:
            raise LocalError("The local MLX worker was closed or replaced; try again.")
        if MODEL not in local_models.available_models():
            raise LocalError("The local MLX model is unavailable. Connect the external SSD containing LocalAI, then try again.")
        if process is not None and (process is not self._process or process.returncode is not None):
            raise LocalError("The local MLX worker stopped or was replaced; try again.")
        if time.monotonic() >= deadline:
            raise asyncio.TimeoutError

    async def _start(self, epoch: int, deadline: float):
        self._check(deadline, epoch=epoch)
        runtime = local_models.ROOT / "tutor-runtime"
        cache = runtime / "cache"
        directories = {"HF_HOME": cache / "huggingface", "HF_HUB_CACHE": cache / "huggingface/hub",
                       "HF_XET_CACHE": cache / "huggingface/xet", "TMPDIR": runtime / "tmp",
                       "PYTHONPYCACHEPREFIX": cache / "pycache", "OUTLINES_CACHE_DIR": cache / "outlines",
                       "XDG_CACHE_HOME": cache}
        # Never recreate a missing mount root through parents=True after an SSD disconnect.
        for directory in sorted({runtime, cache, *directories.values()}, key=lambda path: len(path.parts)):
            directory.mkdir(exist_ok=True)
        self._check(deadline, epoch=epoch)
        app = str(Path(__file__).resolve().parents[1])
        env = {**os.environ, **{name: str(path) for name, path in directories.items()}, "HF_HUB_OFFLINE": "1",
               "PYTHONPATH": os.pathsep.join(filter(None, (app, os.environ.get("PYTHONPATH"))))}
        process = await asyncio.create_subprocess_exec(
            str(local_models.MLX_PYTHON), "-m", "tutor_app.mlx_worker", env=env,
            stdin=asyncio.subprocess.PIPE, stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.DEVNULL, limit=_LIMIT)
        if self._closed or epoch != self._epoch:
            await self._stop(process)
            raise LocalError("The local MLX worker was closed or replaced; try again.")
        self._process = process
        return process

    async def events(self, payload: dict, timeout: float) -> AsyncIterator[dict]:
        deadline = time.monotonic() + timeout
        acquired, completed = False, False
        try:
            if payload.get("model") != MODEL:
                raise LocalError("Choose the registered GPT-OSS MLX model in Settings.")
            self._check(deadline)
            await asyncio.wait_for(self._lock.acquire(), max(.001, deadline - time.monotonic()))
            acquired = True
            self._check(deadline)
            epoch, process = self._epoch, self._process
            readiness, self._readiness = self._readiness, None
            preload = payload.get("messages") == []
            if not preload:
                if process is None or readiness != (process, epoch, str(local_models.MLX_CHECKPOINT)):
                    raise LocalError("The local MLX worker needs a fresh matching preload before answering; try again.")
                self._check(deadline, process, epoch)  # A replacement must receive its own empty load acknowledgement.
            elif process is None or process.returncode is not None:
                self._starting = asyncio.create_task(self._start(epoch, deadline))
                process = await asyncio.wait_for(asyncio.shield(self._starting), max(.001, deadline - time.monotonic()))
            self._check(deadline, process, epoch)
            self._request += 1
            request_id = f"{epoch}:{self._request}"
            request = {"id": request_id, "payload": {**payload, "_epoch": epoch, "_deadline": deadline}}
            data = json.dumps(request, ensure_ascii=False).encode() + b"\n"
            if len(data) > _LIMIT:
                raise LocalError("The local MLX request is too large. Start a fresh chat, then try again.")
            self._check(deadline, process, epoch)
            process.stdin.write(data)
            await asyncio.wait_for(process.stdin.drain(), max(.001, deadline - time.monotonic()))
            while True:
                line = await asyncio.wait_for(process.stdout.readline(), max(.001, deadline - time.monotonic()))
                self._check(deadline, process, epoch)
                if not line or len(line) > _LIMIT or not line.endswith(b"\n"):
                    raise LocalError("The local MLX worker ended or sent an unreadable reply; try again.")
                envelope = json.loads(line)
                event = envelope.get("event") if isinstance(envelope, dict) else None
                if (not isinstance(event, dict) or envelope.get("id") != request_id
                        or event.get("model") != MODEL
                        or event.get("checkpoint") != str(local_models.MLX_CHECKPOINT)
                        or event.get("worker_pid") != process.pid or event.get("_epoch") != epoch):
                    raise LocalError("The local MLX worker returned a stale or mismatched reply; try again.")
                from .local_ai import LocalAI
                event = LocalAI._decode(json.dumps(event).encode())
                if event.get("error"):
                    raise LocalError(f"MLX: {event['error']}")
                if preload and (event.get("done") is not True
                        or event.get("done_reason") != "load"
                        or (event.get("message") or {}).get("content")
                        or (event.get("message") or {}).get("thinking")):
                    raise LocalError("The local MLX worker did not confirm that the model is loaded; try again.")
                if event.get("done"):
                    if event["done"] is not True:
                        raise LocalError("The local MLX worker sent an unreadable completion; try again.")
                    self._check(deadline, process, epoch)
                    if preload:
                        self._readiness = (process, epoch, str(local_models.MLX_CHECKPOINT))
                    completed = True
                yield event
                if completed:
                    return
        except asyncio.TimeoutError:
            raise
        except (ValueError, OSError, asyncio.IncompleteReadError, asyncio.LimitOverrunError) as exc:
            raise LocalError("The local MLX worker stopped or sent an unreadable reply; try again.") from exc
        finally:
            if not completed:
                self._readiness = None
            if not completed and acquired:
                await self.close()
            elif not completed and self._process is not None and MODEL not in local_models.available_models():
                await self.close()
            if acquired:
                self._lock.release()

    @staticmethod
    async def _stop(process) -> None:
        if process.stdin is not None:
            process.stdin.close()
        if process.returncode is not None:
            return
        try:
            process.terminate()
            await asyncio.wait_for(process.wait(), 1)
        except (ProcessLookupError, asyncio.TimeoutError, asyncio.CancelledError):
            try:
                if process.returncode is None:
                    process.kill()
            except ProcessLookupError:
                pass
            await asyncio.shield(process.wait())

    async def close(self) -> None:
        self._readiness = None
        self._closed = True
        self._epoch += 1
        process, self._process = self._process, None
        if process is not None:
            await self._stop(process)
        if self._starting is not None and not self._starting.done():
            # The launch task retains its child and observes the invalidated epoch on return.
            try:
                await asyncio.wait_for(asyncio.shield(self._starting), 1)
            except (LocalError, OSError, asyncio.TimeoutError):
                pass
