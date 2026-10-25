"""Bounded, exact reuse of successful structured local replies within one tutor session."""
from __future__ import annotations

import asyncio
import copy
import hashlib
import json
import time
from collections import OrderedDict


def reply_key(**settings) -> str:
    """Every input affecting an answer belongs in this key; prompts are not retained in the index."""
    return hashlib.sha256(json.dumps(settings, sort_keys=True, ensure_ascii=False).encode()).hexdigest()


class LocalReplies:
    def __init__(self, clock=time.monotonic):
        self._clock = clock
        self._entries = OrderedDict()
        self._lock = asyncio.Lock()
        self._generation = 0

    def clear(self) -> None:
        self._generation += 1
        self._entries.clear()

    async def run(self, key, answer, timeout):
        """Coalesce queued duplicate work and include waiting time in the original deadline."""
        deadline = self._clock() + timeout
        generation = self._generation
        await asyncio.wait_for(self._lock.acquire(), max(.001, timeout))
        try:
            if generation != self._generation:
                raise asyncio.CancelledError
            now = self._clock()
            if key in self._entries:
                at, data, result = self._entries[key]
                if now - at < 600:
                    self._entries.move_to_end(key)
                    data, result = copy.deepcopy((data, result))
                    result.performance = {"model": result.performance.get("model"), "cached_reply": True,
                                          "total_seconds": 0, "first_token_seconds": 0}
                    return data, result
                del self._entries[key]
            remaining = deadline - now
            if remaining <= 0:
                raise asyncio.TimeoutError
            data, result = await answer(remaining)
            if data is not None and result.ok and generation == self._generation and len(result.text) <= 65536:
                self._entries[key] = (self._clock(), *copy.deepcopy((data, result)))
                while len(self._entries) > 32:
                    self._entries.popitem(last=False)
            return data, result
        finally:
            self._lock.release()
