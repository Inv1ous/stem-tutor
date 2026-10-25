"""Explicit starting points for the three AI tasks; saved per-task choices remain authoritative."""
from dataclasses import dataclass

from .codex_models import CODEX_MODELS
from .local_models import LOCAL_MODELS


@dataclass(frozen=True)
class Preset:
    label: str
    description: str
    provider: str
    mark: tuple[str, bool]
    explain: tuple[str, bool]
    ask: tuple[str, bool]

    def ai_for(self, mode: str) -> tuple[str, bool]:
        return getattr(self, mode)

    @property
    def required_models(self) -> tuple[str, ...]:
        return tuple(dict.fromkeys([self.mark[0], self.explain[0], self.ask[0]]))


PRESETS = {
    "claude_fast": Preset("Claude: fast", "Haiku for everyday help, with thinking off.", "claude",
                          ("haiku", False), ("haiku", False), ("haiku", False)),
    "claude_balanced": Preset("Claude: balanced", "Sonnet for demanding explanations, with thinking off.", "claude",
                              ("sonnet", False), ("sonnet", False), ("sonnet", False)),
    "chatgpt_fast": Preset("ChatGPT: fast", "GPT-6-Luna for everyday help, with low reasoning.", "chatgpt",
                           ("codex:gpt-6-luna", False), ("codex:gpt-6-luna", False), ("codex:gpt-6-luna", False)),
    "chatgpt_strong": Preset("ChatGPT: strong", "GPT-6.1-Sol for more demanding help, with low reasoning.", "chatgpt",
                             ("codex:gpt-6.1-sol", False), ("codex:gpt-6.1-sol", False), ("codex:gpt-6.1-sol", False)),
    "local_fast": Preset("Local: fast tutoring",
                         "Gemma 26B marks; Gemma E4B tutors with thinking off. Switching models adds loading time.",
                         "local", ("ollama:gemma4:26b-a4b-it-qat", False), ("ollama:gemma4:e4b", False),
                         ("ollama:gemma4:e4b", False)),
    "local_precise": Preset("Local: careful marking",
                            "Recommended all-round setup: Gemma 26B for every task, thinking off. One model avoids switching.",
                            "local", ("ollama:gemma4:26b-a4b-it-qat", False),
                            ("ollama:gemma4:26b-a4b-it-qat", False), ("ollama:gemma4:26b-a4b-it-qat", False)),
    "local_reasoning": Preset("Local: text reasoning",
                              "Gemma 26B marks; GPT-OSS tutors at low reasoning. Switching adds loading time; OCR cannot read geometry.",
                              "local", ("ollama:gemma4:26b-a4b-it-qat", False), ("ollama:gpt-oss:20b", False),
                              ("ollama:gpt-oss:20b", False)),
    "local_deep": Preset("Local: extended reasoning",
                         "Gemma 26B marks; GPT-OSS tutors at high reasoning. Switching adds loading time; high effort is unbenchmarked.",
                         "local", ("ollama:gemma4:26b-a4b-it-qat", False), ("ollama:gpt-oss:20b", True),
                         ("ollama:gpt-oss:20b", True)),
}


def is_available(name: str, connected: tuple[str, ...]) -> bool:
    preset = PRESETS[name]
    return preset.provider != "local" or all(model in connected for model in preset.required_models)


def available(connected: tuple[str, ...]) -> list[str]:
    return [name for name in PRESETS if is_available(name, connected)]


def matching(choices: dict[str, tuple[str, bool]]) -> str:
    for name, preset in PRESETS.items():
        if all(choices[mode] == preset.ai_for(mode) for mode in ("mark", "explain", "ask")):
            return name
    return "custom"


def model_label(model: str) -> str:
    cloud = {"haiku": "Haiku", "sonnet": "Sonnet", "opus": "Opus"}
    return LOCAL_MODELS.get(model, CODEX_MODELS.get(model, cloud.get(model, model)))
