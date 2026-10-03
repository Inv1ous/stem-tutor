"""Where things live and your settings (stored in the vault, so they travel with your progress)."""
from __future__ import annotations

import json
import os
from dataclasses import asdict, dataclass
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
DEFAULT_VAULT = REPO.parent / "STEM Tutor"
ICLOUD_INBOX = Path.home() / "Library/Mobile Documents/com~apple~CloudDocs/STEM Tutor Inbox"
DOWNLOADS = Path.home() / "Downloads"  # where the browser saves the progress file the Almanac exports


def vault_path() -> Path:
    return Path(os.environ.get("STEM_TUTOR_VAULT") or DEFAULT_VAULT)


@dataclass
class Settings:
    ai: bool = True                 # use Claude for asking, explaining differently, judging written answers
    model: str = "haiku"            # haiku is cheapest; sonnet explains better but uses ~3x more of your limit
    own_words_feedback: bool = True  # AI comments on your "in your own words" answers
    open_obsidian: bool = True      # show Now.md in Obsidian when a session starts
    minutes: int = 40               # default session length

    @classmethod
    def load(cls, vault: Path) -> "Settings":
        p = vault / ".tutor" / "app_settings.json"
        try:
            data = json.loads(p.read_text()) if p.exists() else {}
        except (OSError, ValueError):  # a damaged settings file falls back to defaults
            data = {}
        default = cls()
        good = {k: v for k, v in (data if isinstance(data, dict) else {}).items()
                if k in cls.__dataclass_fields__ and type(v) is type(getattr(default, k))}
        return cls(**good)

    def save(self, vault: Path) -> None:
        from tutorlib.store import write_text
        write_text(vault / ".tutor" / "app_settings.json", json.dumps(asdict(self), indent=1))
