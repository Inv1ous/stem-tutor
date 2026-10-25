"""Supported SSD models and their input capabilities, checked afresh when needed."""
from pathlib import Path


ROOT = Path("/Volumes/External SSD TB4/LocalAI")
DEFAULT_VISION_MODEL = "macos:vision"  # literal on-device OCR; no generated graph interpretation
LOCAL_MODELS = {
    "ollama:qwen3.5:9b": "Qwen 3.5 9B (local)",
    "ollama:gemma4:26b-a4b-it-qat": "Gemma 4 26B (local)",
    "ollama:qwen3.8:27b": "Qwen 3.8 27B (local)",
    "ollama:qwen3.5:2b": "Qwen 3.5 2B (local)",
    "ollama:qwen3.5:4b": "Qwen 3.5 4B (local)",
    "ollama:gemma4:e2b": "Gemma 4 E2B (local)",
    "ollama:gemma4:e4b": "Gemma 4 E4B (local)",
    "ollama:ministral-3:3b": "Ministral 3 3B (local)",
    "ollama:phi4-mini:3.8b": "Phi-4-mini 3.8B (local; text only)",
    "ollama:gpt-oss:20b": "GPT-OSS 20B (local; text only)",
    "ollama:granite3.2-vision:2b": "Granite 3.2 Vision 2B (local; image observer)",
    "ollama:deepseek-r1:8b": "DeepSeek R1 0528 8B (local; text only)",
    "ollama:deepseek-r1:14b": "DeepSeek R1 Qwen 14B (local; text only)",
    "ollama:llama3.1:8b": "Llama 3.1 8B (local; text only)",
    "ollama:lfm2.5:8b": "Liquid LFM2.5 8B (local; always thinks)",
    "ollama:maternion/mimo-v2.6:9b-instruct-q4_K_M": "MiMo V2.6 9B (local; community)",
}
TEXT_MODELS = {"ollama:phi4-mini:3.8b", "ollama:gpt-oss:20b", "ollama:deepseek-r1:8b",
               "ollama:deepseek-r1:14b", "ollama:llama3.1:8b", "ollama:lfm2.5:8b"}
# Keep the active model warm through a study session without retaining a large model indefinitely.
KEEP_ALIVE = {
    "ollama:qwen3.5:9b": "30m",
    "ollama:gemma4:26b-a4b-it-qat": "15m",
    "ollama:qwen3.8:27b": "10m",
    **{model: "45m" for model in LOCAL_MODELS if model not in
       ("ollama:qwen3.5:9b", "ollama:gemma4:26b-a4b-it-qat", "ollama:qwen3.8:27b")},
}
# Gemma's default 4096-token window can be consumed entirely by its input and hidden thinking.
CONTEXT_LENGTH = {model: 8192 for model in LOCAL_MODELS if model not in ("ollama:qwen3.5:9b", "ollama:qwen3.8:27b")}
MAX_CONTEXT_LENGTH = {model: 16384 for model in CONTEXT_LENGTH}


def supports_vision(model: str | None) -> bool:
    return model in LOCAL_MODELS and model not in TEXT_MODELS


def supports_thinking(model: str | None) -> bool:
    return model in LOCAL_MODELS and model not in (
        "ollama:phi4-mini:3.8b", "ollama:ministral-3:3b", "ollama:granite3.2-vision:2b", "ollama:llama3.1:8b")


def thinking_value(model: str, extended: bool) -> bool | str | None:
    """The same switch uses only values actually supported by each local model."""
    if always_thinks(model):
        return True  # Preserve native reasoning and request its proper hidden-reasoning parser.
    if not supports_thinking(model):
        return None
    if model == "ollama:gpt-oss:20b":
        return "high" if extended else "low"
    return bool(extended)


def always_thinks(model: str | None) -> bool:
    """Installed reasoning templates without a working off mode."""
    return model in ("ollama:lfm2.5:8b", "ollama:deepseek-r1:8b", "ollama:deepseek-r1:14b")


def is_image_helper(model: str | None) -> bool:
    return model == DEFAULT_VISION_MODEL or supports_vision(model)


def is_local(model: str | None) -> bool:
    return model in LOCAL_MODELS


def available_models() -> tuple[str, ...]:
    """A mounted SSD and each model's manifest are required; no cached mount state."""
    registry = ROOT / "manifests/registry.ollama.ai"
    installed = []
    for model in LOCAL_MODELS:
        name, tag = model.removeprefix("ollama:").rsplit(":", 1)
        path = name if "/" in name else f"library/{name}"
        if (registry / path / tag).is_file():
            installed.append(model)
    return tuple(installed)
