"""Synchronous bridge from the engine's topic identification to the app's one-shot AI.

`Tutor.check_solvable` runs on a worker thread and calls `tutor.topic_ai(request)` synchronously; the app's AI
clients are async and live on the app's event loop, so the call is handed to that loop and waited for here.
"""
from __future__ import annotations

import asyncio
import threading
from pathlib import Path

from . import abacus_models, codex_models, local_models


class TopicAI:
    """`Tutor.topic_ai`: one image-aware one-shot call, answered as the JSON object the engine validates."""

    def __init__(self, ai, loop: asyncio.AbstractEventLoop, model: str | None = None, timeout: float = 90):
        self.ai, self.loop, self.model, self.timeout = ai, loop, model, timeout

    @staticmethod
    def _reads_images(model: str | None) -> bool:
        """Claude's one-shot route is text-only; local models read images natively or through the local helper."""
        return local_models.is_local(model) or codex_models.is_codex(model) or abacus_models.reads_images(model)

    def model_for(self, images: list[Path]) -> str | None:
        """The configured model when it can read the images, else the vision-capable local or ChatGPT model."""
        chosen = self.model or getattr(self.ai, 'model', None)
        if not images or self._reads_images(chosen):
            return chosen
        helper = local_models.DEFAULT_VISION_MODEL
        if helper in local_models.available_models():
            return helper
        for name in local_models.available_models():
            if local_models.supports_vision(name):
                return name
        for name in codex_models.CODEX_MODELS:
            if self.ai.available_for(name):
                return name
        return None

    def __call__(self, request: dict):
        images = [Path(p) for p in request.get('images') or []]
        model = self.model_for(images)
        if model is None or not self.ai.available_for(model):
            return None
        if threading.current_thread() is threading.main_thread():
            return None  # the app's own loop cannot be waited on from its thread: never deadlock the UI
        if images and not codex_models.is_codex(model) and not abacus_models.is_abacus(model):
            images = images[:1]  # the local route reads one image per call
        coro = self.ai.one_shot(request['prompt'], schema=request.get('schema'), model=model,
                                timeout=self.timeout, system=request.get('system'),
                                images=images or None)
        try:
            data, result = asyncio.run_coroutine_threadsafe(coro, self.loop).result(self.timeout + 15)
        except Exception:  # noqa: BLE001 - an unavailable AI is reported by the engine, never raised at the learner
            return None
        return data if result.ok else None
