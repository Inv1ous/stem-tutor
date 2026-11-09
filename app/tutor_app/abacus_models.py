"""Models offered through the learner's Abacus.AI RouteLLM API key.

The key is read from $ABACUS_ROUTELLM_API_KEY or the first line of ~/.config/routellm/key; it is never saved in
Settings. Keep saved choices valid even when the key is missing, so a later key restores them.
"""
from __future__ import annotations


ABACUS_MODELS = {
    "abacus:route-llm": "RouteLLM: picks a model per request (Abacus)",
    "abacus:claude-haiku-5-5": "Claude Haiku 5.5 (Abacus)",
    "abacus:claude-sonnet-5-5": "Claude Sonnet 5.5 (Abacus)",
    "abacus:claude-opus-5-5": "Claude Opus 5.5 (Abacus)",
    "abacus:gpt-6.1-sol": "GPT-6.1-Sol (Abacus)",
    "abacus:gpt-6-luna": "GPT-6-Luna (Abacus)",
    "abacus:gemini-3.1-pro-preview": "Gemini 3.1 Pro (Abacus)",
    "abacus:gemini-3.7-flash": "Gemini 3.7 Flash (Abacus)",
    "abacus:grok-4.7": "Grok 4.7 (Abacus)",
    "abacus:deepseek-ai/DeepSeek-V4-Pro-0813": "DeepSeek V4 Pro (Abacus; text only)",
    "abacus:moonshotai/Kimi-K3": "Kimi K3 (Abacus; text only)",
}
TEXT_MODELS = {"abacus:deepseek-ai/DeepSeek-V4-Pro-0813", "abacus:moonshotai/Kimi-K3"}


def is_abacus(model: str | None) -> bool:
    return model in ABACUS_MODELS


def reads_images(model: str | None) -> bool:
    return is_abacus(model) and model not in TEXT_MODELS
