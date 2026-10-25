"""Route the tutor's existing AI interface to Claude or the selected SSD model."""
from __future__ import annotations

from contextlib import aclosing
from pathlib import Path
from typing import AsyncIterator, Callable

from . import local_models
from .ai import Claude, Result
from .local_ai import LocalAI


class TutorAI(Claude):
    """Keep Claude's conversations and usage unchanged; local help has its own client."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._local: LocalAI | None = None
        self.on_result: Callable[[Result], None] = lambda result: None
        self.on_request: Callable[[str], None] = lambda model: None

    @property
    def local(self) -> LocalAI:
        if self._local is None:
            self._local = LocalAI(system=self.system, speech=self.speech)
        return self._local

    def available_for(self, model: str) -> bool:
        if local_models.is_local(model):
            return model in local_models.available_models()
        return super().available

    @property
    def available(self) -> bool:
        return self.available_for(self.model)

    def problem_for(self, model: str) -> str:
        if local_models.is_local(model):
            return "Connect the external SSD with this local model, or choose another model in Settings."
        return self.message or "AI help is unavailable."

    async def warm(self, model: str | None = None) -> None:
        chosen = model or self.model
        if not self.wanted() or getattr(self, "_closed", False):
            return
        if local_models.is_local(chosen):
            if self.available_for(chosen):
                await self.local.warm(chosen)
        else:
            await super().warm()

    async def reset(self, warm: bool = True) -> None:
        if self._local is not None:
            await self._local.reset()
        # A new idea forgets history but keeps the loaded local model. Screens preload the task they will use.
        await super().reset(warm=warm and not local_models.is_local(self.model))

    async def close(self) -> None:
        await super().close()
        await self.release_local()

    async def release_local(self) -> None:
        """Release local models without restarting Claude or changing its conversations and usage."""
        local, self._local = self._local, None
        if local is not None:
            await local.close()

    async def stream(self, prompt: str, image: Path | None = None, model: str | None = None,
                     think: bool | None = None) -> AsyncIterator[str]:
        chosen = model or self.model
        if not local_models.is_local(chosen):
            if self._local is not None:
                self.on_request(chosen)  # stop a stale local preload only when a local client exists
            async with aclosing(super().stream(prompt, image=image, model=model, think=think)) as reply:
                async for chunk in reply:
                    yield chunk
            return
        self.on_request(chosen)
        if not self.available_for(chosen):
            self.last = Result(ok=False, status="off", message=self.problem_for(chosen))
            return
        local = self.local
        local.speech = self.speech
        try:
            async with aclosing(local.stream(prompt, image=image, model=chosen,
                                              think=self.think if think is None else think)) as reply:
                async for chunk in reply:
                    yield chunk
        finally:
            self.last = local.last
        if self.last.ok:
            self.on_result(self.last)

    async def one_shot(self, prompt: str, schema: dict | None = None, model: str | None = None,
                       timeout: float = 120, system: str | None = None,
                       speech: bool = False, think: bool = False) -> tuple[dict | None, Result]:
        chosen = model or self.model
        if not local_models.is_local(chosen):
            if self._local is not None:
                self.on_request(chosen)
            return await super().one_shot(prompt, schema=schema, model=model, timeout=timeout,
                                          system=system, speech=speech, think=think)
        self.on_request(chosen)
        if not self.available_for(chosen):
            return None, Result(ok=False, status="off", message=self.problem_for(chosen))
        local = self.local
        local.speech = self.speech
        data, result = await local.one_shot(prompt, schema=schema, model=chosen, timeout=timeout,
                                           system=system, speech=speech, think=think)
        if result.ok:
            self.on_result(result)
        return data, result
