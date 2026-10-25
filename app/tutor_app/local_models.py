"""Supported SSD models and their input capabilities, checked afresh when needed."""
import json
from pathlib import Path


ROOT = Path("/Volumes/External SSD TB4/LocalAI")
MLX_GPT = "mlx:gpt-oss:20b"
MLX_CHECKPOINT = ROOT / "models/openai/gpt-oss-20b"
MLX_PYTHON = ROOT / "tutor-runtime/mlx/.venv/bin/python"
MLX_RECEIPT = ROOT / "tutor-runtime/mlx/gpt-oss-20b.json"
MLX_REVISION = "6cee5e81ee83917806bbde320786a8fb61efebee"
DEFAULT_VISION_MODEL = "macos:vision"  # literal on-device OCR; no generated graph interpretation
LOCAL_MODELS = {
    "ollama:qwen3.5:9b": "Qwen 3.5 9B (local)",
    "ollama:gemma4:26b-a4b-it-qat": "Gemma 4 26B (local GGUF)",
    "ollama:gemma4:26b-tutor-mlx": "Gemma 4 26B (local MLX)",
    "ollama:qwen3.8:27b": "Qwen 3.8 27B (local MLX)",
    "ollama:qwen3.5:2b": "Qwen 3.5 2B (local)",
    "ollama:qwen3.5:4b": "Qwen 3.5 4B (local)",
    "ollama:gemma4:e2b": "Gemma 4 E2B (local)",
    "ollama:gemma4:e4b": "Gemma 4 E4B (local MLX)",
    "ollama:ministral-3:3b": "Ministral 3 3B (local)",
    "ollama:phi4-mini:3.8b": "Phi-4-mini 3.8B (local; text only)",
    "ollama:gpt-oss:20b": "GPT-OSS 20B (local GGUF; text only)",
    MLX_GPT: "GPT-OSS 20B (local MLX; text only)",
    "ollama:granite3.2-vision:2b": "Granite 3.2 Vision 2B (local; image observer)",
    "ollama:deepseek-r1:8b": "DeepSeek R1 0528 8B (local; text only)",
    "ollama:deepseek-r1:14b": "DeepSeek R1 Qwen 14B (local; text only)",
    "ollama:llama3.1:8b": "Llama 3.1 8B (local; text only)",
    "ollama:lfm2.5:8b": "Liquid LFM2.5 8B (local; always thinks)",
    "ollama:maternion/mimo-v2.6:9b-instruct-q4_K_M": "MiMo V2.6 9B (local; community)",
}
TEXT_MODELS = {"ollama:phi4-mini:3.8b", "ollama:gpt-oss:20b", MLX_GPT, "ollama:deepseek-r1:8b",
               "ollama:deepseek-r1:14b", "ollama:llama3.1:8b", "ollama:lfm2.5:8b"}
# Keep the active model warm through a study session without retaining a large model indefinitely.
KEEP_ALIVE = {
    "ollama:qwen3.5:9b": "30m",
    "ollama:gemma4:26b-a4b-it-qat": "15m",
    "ollama:gemma4:26b-tutor-mlx": "15m",
    "ollama:qwen3.8:27b": "10m",
    **{model: "45m" for model in LOCAL_MODELS if model not in
       ("ollama:qwen3.5:9b", "ollama:gemma4:26b-a4b-it-qat", "ollama:gemma4:26b-tutor-mlx", "ollama:qwen3.8:27b")},
}
# Gemma's default 4096-token window can be consumed entirely by its input and hidden thinking.
CONTEXT_LENGTH = {model: 8192 for model in LOCAL_MODELS if model not in ("ollama:qwen3.5:9b", "ollama:qwen3.8:27b")}
MAX_CONTEXT_LENGTH = {model: 16384 for model in CONTEXT_LENGTH}


def supports_vision(model: str | None) -> bool:
    return model in LOCAL_MODELS and model not in TEXT_MODELS


def supports_thinking(model: str | None) -> bool:
    return model in LOCAL_MODELS and model not in (
        "ollama:phi4-mini:3.8b", "ollama:ministral-3:3b", "ollama:granite3.2-vision:2b", "ollama:llama3.1:8b")


def thinking_levels(model: str) -> tuple[str, ...]:
    """Named strengths offered by the model's native runtime."""
    if model in ("ollama:gpt-oss:20b", MLX_GPT):
        return ("low", "medium", "high")
    if model == "ollama:qwen3.8:27b":
        return ("off", "low", "medium", "xhigh")
    return ()


def thinking_value(model: str, extended: bool | str) -> bool | str | None:
    """Validate native strengths; preserve the original boolean choices as aliases."""
    levels = thinking_levels(model)
    if isinstance(extended, str):
        if extended not in levels:
            raise ValueError(f"Unsupported reasoning strength {extended!r} for {model}")
        return False if extended == "off" else extended
    if type(extended) is not bool:
        raise ValueError("Reasoning strength must be a boolean or a supported named level")
    if always_thinks(model):
        return True  # Preserve native reasoning and request its proper hidden-reasoning parser.
    if not supports_thinking(model):
        return None
    if model in ("ollama:gpt-oss:20b", MLX_GPT):
        return "high" if extended else "low"
    if model == "ollama:qwen3.8:27b":
        return "xhigh" if extended else False
    return extended


def thinking_key(model: str, value: bool | str) -> bool | str | None:
    """A single history/cache identity for equivalent legacy and explicit strengths."""
    return thinking_value(model, value)


def always_thinks(model: str | None) -> bool:
    """Installed reasoning templates without a working off mode."""
    return model in ("ollama:lfm2.5:8b", "ollama:deepseek-r1:8b", "ollama:deepseek-r1:14b")


def is_image_helper(model: str | None) -> bool:
    return model == DEFAULT_VISION_MODEL or supports_vision(model)


def is_local(model: str | None) -> bool:
    return model in LOCAL_MODELS


def available_models() -> tuple[str, ...]:
    """A mounted SSD and each model's manifest are required; no cached mount state."""
    registries = (ROOT / "manifests/registry.ollama.ai", ROOT / "manifests-v2/ollama.com")
    installed = []
    for model in LOCAL_MODELS:
        if model == MLX_GPT:
            if _mlx_installed():
                installed.append(model)
            continue
        name, tag = model.removeprefix("ollama:").rsplit(":", 1)
        path = name if "/" in name else f"library/{name}"
        if any((registry / path / tag).is_file() for registry in registries):
            installed.append(model)
    return tuple(installed)


def _safe_basename(name: object) -> bool:
    return isinstance(name, str) and bool(name) and name not in (".", "..") and "/" not in name and "\\" not in name


def _mlx_installed() -> bool:
    """A completed receipt authenticates the checkpoint's files and isolated runtime."""
    # Resolve below ROOT afresh, just like Ollama manifests, so SSD discovery has one source of truth.
    checkpoint = ROOT / "models/openai/gpt-oss-20b"
    python = ROOT / "tutor-runtime/mlx/.venv/bin/python"
    receipt = ROOT / "tutor-runtime/mlx/gpt-oss-20b.json"
    try:
        data = json.loads(receipt.read_text())
        if not python.is_file() or not isinstance(data, dict) or data.get("revision") != MLX_REVISION:
            return False
        runtime, files = data.get("runtime"), data.get("files")
        if not isinstance(runtime, dict) or not all(isinstance(runtime.get(name), str) and runtime[name].strip()
                                                  for name in ("mlx", "mlx-lm", "outlines", "llguidance")):
            return False
        required = {"config.json", "tokenizer.json", "tokenizer_config.json", "model.safetensors.index.json"}
        if not isinstance(files, dict) or not required <= files.keys():
            return False
        for name, size in files.items():
            if not _safe_basename(name) or type(size) is not int or size <= 0:
                return False
            path = checkpoint / name
            if path.resolve().parent != checkpoint.resolve() or not path.is_file() or path.stat().st_size != size:
                return False
        index = json.loads((checkpoint / "model.safetensors.index.json").read_text())
        weights = index.get("weight_map") if isinstance(index, dict) else None
        return isinstance(weights, dict) and bool(weights) and all(
            _safe_basename(name) and name.endswith(".safetensors") and name in files for name in weights.values())
    except (OSError, ValueError):
        return False
