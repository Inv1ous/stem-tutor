"""Route the tutor's existing AI interface to Claude or the selected SSD model."""
from __future__ import annotations

import asyncio
import hashlib
import time
from contextlib import aclosing, asynccontextmanager, nullcontext
from pathlib import Path
from typing import AsyncIterator, Callable

from . import codex_models, local_models
from .ai import Claude, Result, VISUAL_BRIEF
from .codex_ai import CodexAI
from .local_ai import LocalAI, LocalError
from .local_reuse import LocalReplies, reply_key
from .local_web import LocalWeb, search_query
from .local_vision import LocalVision, VisionError
from .local_ocr import NativeOCR
from .output_fields import normalise_fields, visual_fields


class TutorAI(Claude):
    """Keep Claude's conversations and usage unchanged; local help has its own client."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._local: LocalAI | None = None
        self._codex: CodexAI | None = None
        self._replies: LocalReplies | None = None
        self._web: LocalWeb | None = None
        self._vision: LocalVision | None = None
        self._ocr: NativeOCR | None = None
        self._observing: dict[str, int] = {}
        self._searching: set[str] = set()
        self.local_web = True
        self.local_vision_model = local_models.DEFAULT_VISION_MODEL
        self.on_result: Callable[[Result], None] = lambda result: None
        self.on_request: Callable[[str], None] = lambda model: None

    @property
    def local(self) -> LocalAI:
        if self._local is None:
            self._local = LocalAI(system=self.system, speech=self.speech)
        self._local.web_enabled = self.local_web
        return self._local

    @property
    def codex(self) -> CodexAI:
        if self._codex is None:
            self._codex = CodexAI(system=self.system, speech=self.speech)
        self._codex.speech = self.speech
        return self._codex

    def progress_for(self, model: str) -> dict:
        if self._observing.get(model):
            return {"phase": "reading_image"}
        if model in self._searching:
            return {"phase": "searching"}
        return self._local.progress_for(model) if self._local is not None and local_models.is_local(model) else {}

    def available_for(self, model: str) -> bool:
        if local_models.is_local(model):
            return model in local_models.available_models()
        if codex_models.is_codex(model):
            return self.codex.available
        return super().available

    @property
    def available(self) -> bool:
        return self.available_for(self.model)

    def problem_for(self, model: str) -> str:
        if local_models.is_local(model):
            return "Connect the external SSD with this local model, or choose another model in Settings."
        if codex_models.is_codex(model):
            return self.codex.message or "ChatGPT is unavailable. Run codex login, then try again."
        return self.message or "AI help is unavailable."

    async def warm(self, model: str | None = None) -> None:
        chosen = model or self.model
        if codex_models.is_codex(chosen):
            return  # Subscription requests start only when the learner asks for an answer.
        if not self.wanted() or getattr(self, "_closed", False):
            return
        if local_models.is_local(chosen):
            if self.available_for(chosen):
                await self.local.warm(chosen)
        else:
            await super().warm()

    async def reset(self, warm: bool = True) -> None:
        if self._vision is not None:
            self._vision.clear()
        if self._ocr is not None:
            await self._ocr.reset()
        if self._replies is not None:
            self._replies.clear()
        if self._local is not None:
            await self._local.reset()
        if self._codex is not None:
            await self._codex.reset()
        # A new idea forgets history but keeps the loaded local model. Screens preload the task they will use.
        await super().reset(warm=warm and not local_models.is_local(self.model) and not codex_models.is_codex(self.model))

    async def close(self) -> None:
        await super().close()
        await self.release_local()
        if self._codex is not None:
            await self._codex.close()
        if self._ocr is not None:
            await self._ocr.close()

    async def release_local(self) -> None:
        """Release local models without restarting Claude or changing its conversations and usage."""
        local, self._local = self._local, None
        if self._vision is not None:
            self._vision.clear()
        if self._ocr is not None:
            await self._ocr.reset()
        if self._replies is not None:
            self._replies.clear()
        if local is not None:
            await local.close()

    @asynccontextmanager
    async def _loading_during(self, model: str, timeout: float = 120):
        """Start an owned preload only when uncached independent work can hide it."""
        local = self.local
        deadline = time.monotonic() + timeout
        loading = None

        def start_loading() -> bool:
            nonlocal loading
            if loading is None and not local._lock.locked():
                loading = asyncio.create_task(local.warm(model, timeout=max(.001, deadline - time.monotonic())))
            return loading is not None

        try:
            yield start_loading
            if loading is not None:
                await loading
        finally:
            if loading is not None:
                loading.cancel()
                await asyncio.gather(loading, return_exceptions=True)

    async def _observe_image(self, image: Path | bytes, model: str, timeout: float = 60):
        helper = self.local_vision_model
        native = helper == local_models.DEFAULT_VISION_MODEL
        if not native and (not local_models.supports_vision(helper) or helper not in local_models.available_models()):
            label = local_models.LOCAL_MODELS.get(helper, helper)
            raise VisionError(f"This text-only model needs its local image helper ({label}). Connect the SSD, "
                              "or choose a model with native vision.")
        local, generation = self.local, self.local._generation
        if native and self._ocr is None:
            self._ocr = NativeOCR()
        if self._vision is None:
            self._vision = LocalVision()
        load_started = False
        async with self._loading_during(model, timeout) if native else nullcontext() as start_loading:
            async def describe_native(*args, **kwargs):
                nonlocal load_started
                load_started = start_loading()  # LocalVision calls this only on an exact observation cache miss.
                return await self._ocr.describe_image(*args, **kwargs)

            self._observing[model] = self._observing.get(model, 0) + 1
            try:
                describe = describe_native if native else local.describe_image
                observed = await self._vision.describe(image, model=helper, describe=describe, timeout=timeout)
            finally:
                self._observing[model] -= 1
                if not self._observing[model]:
                    del self._observing[model]
        if local._generation != generation or self._local is not local or local._closed:
            raise asyncio.CancelledError
        return observed, load_started

    async def prepare_local(self, model: str, image: Path | None = None) -> None:
        """Observe a text model's diagram while the learner reads, then leave its tutor model loaded."""
        if not self.wanted() or getattr(self, "_closed", False):
            return
        if image is not None and not local_models.supports_vision(model):
            try:
                _, load_started = await self._observe_image(image, model)
            except VisionError:
                return  # a requested answer will report the actionable image error
            if load_started:
                return  # native OCR already overlapped the same model's preload
        await self.warm(model=model)

    @staticmethod
    def _with_vision_performance(result: Result, observed) -> None:
        if observed is None or not result.ok:
            return
        result.performance.update(observed.performance)

    async def stream(self, prompt: str, image: Path | None = None, model: str | None = None,
                     think: bool | str | None = None, web_query: str | None = None) -> AsyncIterator[str]:
        chosen = model or self.model
        if codex_models.is_codex(chosen):
            if self._local is not None:
                self.on_request(chosen)
            client = self.codex
            try:
                async with aclosing(client.stream(prompt, image=image, model=chosen,
                                                   think=self.think if think is None else think)) as reply:
                    async for chunk in reply:
                        yield chunk
            finally:
                self.last = client.last
            return
        if not local_models.is_local(chosen):
            if self._local is not None:
                self.on_request(chosen)  # stop a stale local preload only when a local client exists
            async with aclosing(super().stream(prompt, image=image, model=model, think=think)) as reply:
                async for chunk in reply:
                    yield chunk
            return
        started = time.monotonic()
        self.on_request(chosen)
        if not self.available_for(chosen):
            if chosen == "mlx:gpt-oss:20b" and self._local is not None:
                await self._local._release_mlx()
            self.last = Result(ok=False, status="off", message=self.problem_for(chosen))
            return
        local = self.local
        try:
            selected_think = self.think if think is None else think
            effort = local._effort(chosen, selected_think)
            think = selected_think if effort is None else effort
        except LocalError as exc:
            self.last = local._failure(exc)
            return
        local.speech = self.speech
        generation = local._generation
        self.last = Result(ok=False, status="error", message="The local reply was cancelled; try again.")
        observed = None
        if image is not None and not local_models.supports_vision(chosen):
            try:
                observed, _ = await self._observe_image(image, chosen)
                prompt += "\n\n" + observed.context
                image = None
            except VisionError as exc:
                self.last = Result(ok=False, status="error", message=str(exc))
                return
        web, searched = None, 0
        if self.local_web and web_query and (query := search_query(web_query)):
            if self._web is None:
                self._web = LocalWeb()
            self._searching.add(chosen)
            try:
                async with self._loading_during(chosen) as start_loading:
                    start_loading()
                    search_started = time.monotonic()
                    web = await self._web.lookup(query, local._events)
                    searched = time.monotonic() - search_started
                prompt += "\n\n" + web.context
            finally:
                self._searching.discard(chosen)
            if local._generation != generation or self._local is not local or local._closed:
                self.last = Result(ok=False, status="error", message="The local conversation was reset; try again.")
                return
        prepared = time.monotonic() - started
        try:
            async with aclosing(local.stream(prompt, image=image, model=chosen,
                                              think=self.think if think is None else think)) as reply:
                async for chunk in reply:
                    yield chunk
        finally:
            self.last = local.last
        if self.last.ok:
            self._with_vision_performance(self.last, observed)
            self.last.performance["total_seconds"] = max(self.last.performance.get("total_seconds", 0),
                                                        time.monotonic() - started)
            if self.last.performance.get("first_token_seconds") is not None:
                self.last.performance["first_token_seconds"] += prepared
            if web is not None:
                footer = web.footer()
                self.last.text += footer
                if footer:
                    yield footer
                self.last.performance["search_seconds"] = searched
            self.on_result(self.last)

    async def one_shot(self, prompt: str, schema: dict | None = None, model: str | None = None,
                       timeout: float = 120, system: str | None = None,
                       speech: bool = False, think: bool | str = False, image: Path | None = None) -> tuple[dict | None, Result]:
        chosen = model or self.model
        if system and visual_fields(schema) and VISUAL_BRIEF not in system:
            system = f"{system}\n\n{VISUAL_BRIEF}"
        if image is not None and not local_models.is_local(chosen):
            return None, Result(ok=False, status="error", message="Diagram input for this marking request requires a local model.")
        if codex_models.is_codex(chosen):
            if self._local is not None:
                self.on_request(chosen)
            data, result = await self.codex.one_shot(prompt, schema=schema, model=chosen, timeout=timeout,
                                                    system=system, speech=speech, think=think)
            return normalise_fields(data, schema) if result.ok else data, result
        if not local_models.is_local(chosen):
            if self._local is not None:
                self.on_request(chosen)
            data, result = await super().one_shot(prompt, schema=schema, model=model, timeout=timeout,
                                                system=system, speech=speech, think=think)
            return normalise_fields(data, schema) if result.ok else data, result
        self.on_request(chosen)
        if not self.available_for(chosen):
            if chosen == "mlx:gpt-oss:20b" and self._local is not None:
                await self._local._release_mlx()
            return None, Result(ok=False, status="off", message=self.problem_for(chosen))
        local = self.local
        try:
            effort = local_models.thinking_key(chosen, think)
            local._effort(chosen, think)
        except (ValueError, LocalError) as exc:
            return None, local._failure(LocalError(str(exc)))
        local.speech = self.speech
        observed, pixels, image_hash = None, None, None
        started = time.monotonic()
        if image is not None:
            try:
                pixels = image.read_bytes()
                image_hash = hashlib.sha256(pixels).hexdigest()
                if not local_models.supports_vision(chosen):
                    observed, _ = await self._observe_image(pixels, chosen, min(60, timeout))
                    prompt += "\n\n" + observed.context
                    pixels = None
            except (OSError, VisionError) as exc:
                return None, Result(ok=False, status="error", message=str(exc) or "The question image could not be read.")
        remaining = timeout - (time.monotonic() - started)
        if remaining <= 0:
            return None, local._failure(asyncio.TimeoutError())
        async def answer(remaining):
            return await local.one_shot(prompt, schema=schema, model=chosen, timeout=remaining,
                                        system=system, speech=speech, think=think,
                                        **({"image": pixels} if pixels is not None else {}))
        if self._replies is None:
            self._replies = LocalReplies()
        key = reply_key(prompt=prompt, schema=schema, model=chosen, system=system or self.system,
                        speech=bool(speech and self.speech), think=effort, image=image_hash,
                        vision_model=observed.model if observed is not None else None)
        try:
            data, result = await self._replies.run(key, answer, remaining)
        except asyncio.TimeoutError as exc:
            return None, local._failure(exc)
        if result.ok:
            data = normalise_fields(data, schema)
            self._with_vision_performance(result, observed)
            elapsed = time.monotonic() - started
            extra = max(0, elapsed - result.performance.get("total_seconds", 0))
            if result.performance.get("first_token_seconds") is not None:
                result.performance["first_token_seconds"] += extra
            result.performance["total_seconds"] = max(result.performance.get("total_seconds", 0), elapsed)
            self.on_result(result)
        return data, result
