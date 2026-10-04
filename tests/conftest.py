import sys
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parents[1] / "plugin/stem-tutor/skills/tutor/scripts"
sys.path.insert(0, str(SCRIPTS))
import sys, pathlib; sys.path.insert(0, str(pathlib.Path(__file__).parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "app"))


import pytest  # noqa: E402


@pytest.fixture(autouse=True)
def _no_real_ipad_inbox(tmp_path, monkeypatch):
    """The app imports from the learner's real iCloud inbox on start; tests must never move those files."""
    try:
        from tutor_app import config
    except ImportError:
        return
    monkeypatch.setattr(config, "ICLOUD_INBOX", tmp_path / "ipad-inbox")
    monkeypatch.setattr(config, "DOWNLOADS", tmp_path / "downloads", raising=False)  # nor their Downloads
    monkeypatch.setattr(config, "CLAUDE_STATE", tmp_path / "no-claude.json", raising=False)  # nor read their Claude limits
