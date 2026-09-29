"""Where things live and your settings (stored in the vault, so they travel with your progress)."""
from __future__ import annotations

import json
import os
from dataclasses import asdict, dataclass
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
DEFAULT_VAULT = REPO.parent / "STEM Tutor"
ICLOUD_INBOX = Path.home() / "Library/Mobile Documents/com~apple~CloudDocs/STEM Tutor Inbox"


def vault_path() -> Path:
    return Path(os.environ.get("STEM_TUTOR_VAULT") or DEFAULT_VAULT)


@dataclass
class Settings:
    ai: bool = True                 # use Claude for asking, explaining differently, judging written answers
    model: str = "haiku"            # haiku is cheapest; sonnet explains better but uses ~3x more of your limit
    daily_cap: int = 80             # most AI replies per day (protects your Claude usage limit)
    own_words_feedback: bool = True  # AI comments on your "in your own words" answers
    open_obsidian: bool = True      # show Now.md in Obsidian when a session starts
    minutes: int = 40               # default session length

    @classmethod
    def load(cls, vault: Path) -> "Settings":
        p = vault / ".tutor" / "app_settings.json"
        data = json.loads(p.read_text()) if p.exists() else {}
        return cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__})

    def save(self, vault: Path) -> None:
        p = vault / ".tutor" / "app_settings.json"
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(json.dumps(asdict(self), indent=1))
