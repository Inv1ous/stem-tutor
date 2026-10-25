"""The three models installed on the learner's external SSD, checked afresh when needed."""
from pathlib import Path


ROOT = Path("/Volumes/External SSD TB4/LocalAI")
LOCAL_MODELS = {
    "ollama:qwen3.5:9b": "Qwen 3.5 9B (local)",
    "ollama:gemma4:26b-a4b-it-qat": "Gemma 4 26B (local)",
    "ollama:qwen3.8:27b": "Qwen 3.8 27B (local)",
}
# Keep the active model warm through a study session without retaining a large model indefinitely.
KEEP_ALIVE = {
    "ollama:qwen3.5:9b": "30m",
    "ollama:gemma4:26b-a4b-it-qat": "15m",
    "ollama:qwen3.8:27b": "10m",
}


def is_local(model: str | None) -> bool:
    return model in LOCAL_MODELS


def available_models() -> tuple[str, ...]:
    """A mounted SSD and each model's manifest are required; no cached mount state."""
    library = ROOT / "manifests/registry.ollama.ai/library"
    return tuple(model for model in LOCAL_MODELS
                 if (library / model.removeprefix("ollama:").replace(":", "/")).is_file())
