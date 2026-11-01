"""Bound local document history without cutting the current assessment evidence.

The existing HTTP/MLX event APIs do not expose a cheap tokenizer. We therefore
estimate text at one token per three UTF-8 bytes plus message overhead, reserve
2048 tokens for reasoning/output, and reserve 1024 tokens per image. These are
conservative planning estimates, not guarantees about a model's physical window;
image token costs in particular depend on its vision encoder. No runtime/model
settings are increased here. History also has independent pair and byte bounds.
An optional model-specific prompt limit restricts old history only: mandatory
system/schema/current evidence may exceed it while still fitting normal context.
This reduces retained history, without guaranteeing a safe native memory peak.
"""
from __future__ import annotations

import json
import math

DEFAULT_CONTEXT = 8192
RESPONSE_RESERVE = 2048
IMAGE_RESERVE = 1024
MAX_HISTORY_PAIRS = 8
MAX_HISTORY_BYTES = 256 * 1024


class ContextError(ValueError):
    """The complete current request does not fit the local planning budget."""


def _tokens(message: dict) -> int:
    return 16 + math.ceil(len(message.get("content", "").encode("utf-8")) / 3) + (
        IMAGE_RESERVE * len(message.get("images", [])))


def bounded_history(history: list[dict]) -> list[dict]:
    """Keep a contiguous suffix of complete pairs within independent memory bounds."""
    pairs, size = [], 0
    for at in range(len(history) - 2, -1, -2):
        pair = history[at:at + 2]
        if [m.get("role") for m in pair] != ["user", "assistant"]:
            break
        amount = len(json.dumps(pair, ensure_ascii=False).encode("utf-8"))
        if len(pairs) >= MAX_HISTORY_PAIRS or size + amount > MAX_HISTORY_BYTES:
            break
        pairs.append(pair)
        size += amount
    return [message for pair in reversed(pairs) for message in pair]


def select_history(system: str, schema: dict, current: dict, history: list[dict], *,
                   context: int = DEFAULT_CONTEXT,
                   history_prompt_limit: int | None = None) -> list[dict]:
    """Reserve immutable material; an optional prompt target limits only old pairs."""
    required = (_tokens({"content": system}) + _tokens(current)
                + _tokens({"content": json.dumps(schema, ensure_ascii=False)}) + RESPONSE_RESERVE)
    if required > context:
        raise ContextError("The current request is too large for this local model's context budget. "
                           "Shorten the supplied material or choose a model with a larger context; "
                           "the question and mark scheme have not been truncated.")
    allowance = context - required
    if history_prompt_limit is not None:
        allowance = min(allowance, max(0, history_prompt_limit - (required - RESPONSE_RESERVE)))
    selected = bounded_history(history)
    used = sum(_tokens(message) for message in selected)
    while selected and used > allowance:
        used -= _tokens(selected[0]) + _tokens(selected[1])
        selected = selected[2:]
    return selected
