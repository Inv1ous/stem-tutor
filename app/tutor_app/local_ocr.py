"""Literal on-device Apple Vision OCR; no image files, LLM descriptions or diagram interpretation."""
from __future__ import annotations

import asyncio
import hashlib
import json
import math
import os
import platform
import shutil
import signal
import sys
import time
from pathlib import Path
from tempfile import TemporaryDirectory

from . import local_models
from .ai import Result


MODEL = "macos:vision"
SOURCE = Path(__file__).with_suffix(".swift")
_CHOOSE_VISION = " Choose a model with native vision, or clarify the image's essential details."


class OCRError(Exception):
    """OCR could not provide literal text; never substitute a guessed description."""


class NativeOCR:
    def __init__(self, compiler: str | None = None):
        self.compiler = compiler or shutil.which("swiftc")
        self._lock = asyncio.Lock()
        self._procs: set[asyncio.subprocess.Process] = set()
        self._starting: set[asyncio.Task] = set()
        self._generation = 0
        self._closed = False

    def _check_epoch(self, generation: int) -> None:
        if self._closed or generation != self._generation:
            raise asyncio.CancelledError

    @staticmethod
    async def _stop(proc) -> None:
        if proc.returncode is not None:
            return
        def send(sig):
            try:
                if os.name == "posix":
                    os.killpg(proc.pid, sig)
                elif sig == signal.SIGTERM:
                    proc.terminate()
                else:
                    proc.kill()
            except ProcessLookupError:
                pass
        try:
            send(signal.SIGTERM)
            await asyncio.wait_for(proc.wait(), .5)
        except asyncio.TimeoutError:
            send(signal.SIGKILL)
            await proc.wait()
        except asyncio.CancelledError:
            send(signal.SIGKILL)
            await asyncio.shield(proc.wait())
            raise

    async def _run(self, args: list[str], deadline: float, generation: int, image: bytes | None = None) -> bytes:
        proc, abandoned = None, False
        async def launch():
            child = await asyncio.create_subprocess_exec(
                *args, stdin=asyncio.subprocess.PIPE, stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.DEVNULL, start_new_session=os.name == "posix")
            self._procs.add(child)
            if abandoned or self._closed or generation != self._generation:
                try:
                    await self._stop(child)
                finally:
                    self._procs.discard(child)
            return child
        starting = asyncio.create_task(launch())
        self._starting.add(starting)
        def forget(task):
            self._starting.discard(task)
            if not task.cancelled():
                task.exception()
        starting.add_done_callback(forget)
        try:
            proc = await asyncio.wait_for(asyncio.shield(starting), max(.001, deadline - time.monotonic()))
            self._check_epoch(generation)
            output, _ = await asyncio.wait_for(proc.communicate(image), max(.001, deadline - time.monotonic()))
            self._check_epoch(generation)
            if proc.returncode or len(output) > 1_048_576:
                raise OCRError("The native OCR helper could not read this image.")
            return output
        finally:
            abandoned = True
            if proc is None and starting.done() and not starting.cancelled() and starting.exception() is None:
                proc = starting.result()
            if proc is not None:
                try:
                    await self._stop(proc)
                finally:
                    self._procs.discard(proc)

    async def _binary(self, deadline: float, generation: int) -> tuple[Path, float]:
        if not local_models.ROOT.is_dir():
            raise OCRError("Connect the LocalAI SSD to use the native OCR helper.")
        source = SOURCE.read_bytes()
        digest = hashlib.sha256(source).hexdigest()
        cache = local_models.ROOT / "tutor-runtime"
        binary = cache / f"vision-ocr-{platform.machine()}-{digest}"
        if binary.is_file() and os.access(binary, os.X_OK):
            return binary, 0
        if not self.compiler or not shutil.which(self.compiler):
            raise OCRError("Native image OCR needs Apple's Swift compiler. Install Xcode Command Line Tools.")
        cache.mkdir(exist_ok=True)
        started = time.monotonic()
        with TemporaryDirectory(dir=cache, prefix=".vision-build-") as folder:
            script, output = Path(folder) / "main.swift", Path(folder) / "vision-ocr"
            script.write_bytes(source)
            try:
                await self._run([self.compiler, str(script), "-O", "-o", str(output)], deadline, generation)
            except OCRError as exc:
                raise OCRError("The native OCR helper could not compile. Check Xcode Command Line Tools.") from exc
            self._check_epoch(generation)
            if not output.is_file():
                raise OCRError("The native OCR helper could not compile. Check Xcode Command Line Tools.")
            output.chmod(0o755)
            os.replace(output, binary)
        return binary, time.monotonic() - started

    @staticmethod
    def _literal(output: bytes) -> dict:
        data = json.loads(output)
        if (not isinstance(data, dict) or not all(type(data.get(key)) is int and data[key] > 0 for key in ("width", "height"))
                or not isinstance(data.get("lines"), list) or not 0 < len(data["lines"]) <= 2048):
            raise OCRError("Native OCR found no readable text in this image.")
        def number(value):
            return type(value) in (int, float) and math.isfinite(value) and 0 <= value <= 1
        for line in data["lines"]:
            if (not isinstance(line, dict) or not isinstance(line.get("text"), str) or not line["text"].strip()
                    or not number(line.get("confidence")) or not isinstance(line.get("box"), dict)
                    or set(line["box"]) != {"x", "y", "width", "height"}
                    or not all(number(value) for value in line["box"].values())):
                raise OCRError("The native OCR helper returned unreadable text positions.")
        return {"transcription": json.dumps({"coordinate_system": "Normalised bottom-left origin; boxes locate text only, "
                                              "not graph points, curves or diagram shapes.", **data}, ensure_ascii=False),
                "diagram": "", "uncertainties": [
                    "OCR can miss or misread mathematical symbols, arrows and option letters, even at high confidence.",
                    "No diagram or graph geometry was interpreted. Do not infer shapes, slopes, intersections or values "
                    "from text or text boxes. If the answer depends on those details, ask for clarification or use native vision."]}

    async def describe_image(self, image: bytes, prompt: str, *, schema: dict, model: str,
                             timeout: float, system: str) -> tuple[dict | None, Result]:
        """Only image bytes reach the helper; supplied AI instructions are intentionally unused."""
        started, generation, acquired = time.monotonic(), self._generation, False
        deadline = started + min(timeout, 60)
        try:
            self._check_epoch(generation)
            if sys.platform != "darwin" or model != MODEL:
                raise OCRError("Native image OCR is available only on macOS.")
            if not isinstance(image, bytes) or not image:
                raise OCRError("The question image is empty or unreadable.")
            await asyncio.wait_for(self._lock.acquire(), max(.001, deadline - time.monotonic()))
            acquired = True
            self._check_epoch(generation)
            binary, compiled = await self._binary(deadline, generation)
            data = self._literal(await self._run([str(binary)], deadline, generation, image))
            return data, Result(performance={"model": MODEL, "total_seconds": time.monotonic() - started,
                                              "load_seconds": compiled})
        except asyncio.TimeoutError:
            return None, Result(ok=False, status="error", message="Native image OCR took too long." + _CHOOSE_VISION)
        except (OSError, ValueError, TypeError, OCRError) as exc:
            message = str(exc) if isinstance(exc, OCRError) else "The native OCR helper could not read this image."
            return None, Result(ok=False, status="error", message=message + _CHOOSE_VISION)
        finally:
            if acquired:
                self._lock.release()

    async def reset(self) -> None:
        self._generation += 1
        await asyncio.gather(*(self._stop(proc) for proc in tuple(self._procs)))

    async def close(self) -> None:
        self._closed = True
        await self.reset()
        if self._starting:
            try:
                await asyncio.wait_for(asyncio.gather(*(asyncio.shield(task) for task in tuple(self._starting)),
                                                     return_exceptions=True), 3)
            except asyncio.TimeoutError:
                pass  # late launches still observe _closed and are terminated by their retained launch task
