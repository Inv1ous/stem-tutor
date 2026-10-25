"""GPT models advertised by this account's Codex catalogue on 2026-10-25.

These IDs use the saved ChatGPT sign-in, not an API key or the ChatGPT website's model picker.
Keep saved choices valid even when the CLI is temporarily missing or signed out.
"""
from __future__ import annotations


CODEX_MODELS = {
    "codex:gpt-6.1-sol": "GPT-6.1-Sol (ChatGPT)",
    "codex:gpt-6-astra": "GPT-6-Astra (ChatGPT)",
    "codex:gpt-6-sol": "GPT-6-Sol (ChatGPT)",
    "codex:gpt-6-luna": "GPT-6-Luna (ChatGPT)",
    "codex:gpt-5.6-sol": "GPT-5.6-Sol (ChatGPT)",
    "codex:gpt-5.6-terra": "GPT-5.6-Terra (ChatGPT)",
    "codex:gpt-5.6-luna": "GPT-5.6-Luna (ChatGPT)",
}


def is_codex(model: str | None) -> bool:
    return model in CODEX_MODELS
