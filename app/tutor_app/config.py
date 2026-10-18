"""Where things live and your settings (stored in the vault, so they travel with your progress)."""
from __future__ import annotations

import json
import os
from dataclasses import asdict, dataclass
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
DEFAULT_VAULT = REPO.parent / "STEM Tutor"
ICLOUD_INBOX = Path.home() / "Library/Mobile Documents/com~apple~CloudDocs/STEM Tutor Inbox"
CLAUDE_STATE = Path.home() / ".claude.json"  # where Claude Code keeps its last reading of the plan's limits
DOWNLOADS = Path.home() / "Downloads"  # where the browser saves the progress file the Almanac exports
THEMES = ("night", "day", "classic")  # the looks (look.py); Classic is the app as it was before themes


def vault_path() -> Path:
    return Path(os.environ.get("STEM_TUTOR_VAULT") or DEFAULT_VAULT)


@dataclass
class Settings:
    ai: bool = True                 # use Claude for asking, explaining differently, judging written answers
    model: str = "haiku"            # haiku is cheapest; sonnet explains better but uses ~3x more of your limit
    own_words_feedback: bool = True  # AI comments on your "in your own words" answers
    open_obsidian: bool = True      # show Now.md in Obsidian when a session starts
    minutes: int = 40               # default session length
    answer_only: bool = False       # sessions and challenges show only the answer box (ctrl+k); the question is in Obsidian
    theme: str = "classic"          # night, day or classic; `tutor look` sets night once Terminal is set up
    tts_enabled: bool = False       # read aloud with Kokoro (tts.py); `tutor tts setup` switches it on
    tts_auto: bool = False          # read explanations, feedback and AI replies as they appear
    tts_voice: str = "bf_emma"      # a Kokoro voice (tts.VOICES)
    tts_speed: float = 1.0          # 0.8 to 1.3
    tts_volume: float = 1.0         # how loud, 0.1 to 1.0 of the voice as recorded (Settings: 10 to 100 %)

    @classmethod
    def load(cls, vault: Path) -> "Settings":
        p = vault / ".tutor" / "app_settings.json"
        try:
            data = json.loads(p.read_text()) if p.exists() else {}
        except (OSError, ValueError):  # a damaged settings file falls back to defaults
            data = {}
        default = cls()
        data = data if isinstance(data, dict) else {}
        for key in ("tts_speed", "tts_volume"):
            if type(data.get(key)) is int:  # 1 written by hand is 1.0
                data[key] = float(data[key])
        good = {k: v for k, v in data.items()
                if k in cls.__dataclass_fields__ and type(v) is type(getattr(default, k))}
        if good.get("theme") not in THEMES:
            good.pop("theme", None)
        if "tts_speed" in good:
            good["tts_speed"] = min(1.3, max(0.8, good["tts_speed"]))
        if "tts_volume" in good:
            good["tts_volume"] = min(1.0, max(0.1, good["tts_volume"]))
        if not good.get("tts_voice", "x").strip():
            good.pop("tts_voice")
        return cls(**good)

    def save(self, vault: Path) -> None:
        from tutorlib.store import write_text
        write_text(vault / ".tutor" / "app_settings.json", json.dumps(asdict(self), indent=1))
