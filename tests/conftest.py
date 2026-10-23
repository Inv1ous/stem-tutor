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
    monkeypatch.delenv("TERM_PROGRAM", raising=False)  # run in macOS Terminal, tests must never restyle its tabs


@pytest.fixture(autouse=True)
def _no_worker_checks_in_tests(monkeypatch, tmp_path):
    """The foundry and refine check that a worker really used the library and the web, and that every tool is installed; the
    fake workers of the tests do neither (tests of those checks switch them back on)."""
    monkeypatch.setenv("FOUNDRY_EVIDENCE", "0")
    monkeypatch.setenv("FOUNDRY_PREFLIGHT", "0")
    monkeypatch.setenv("FOUNDRY_CLAUDE_APPS", str(tmp_path / "no-claude-apps"))  # never the app's real Claude Code


@pytest.fixture(autouse=True)
def _options_take_enter_at_once(monkeypatch):
    """A pilot presses ⏎ the instant a question appears; the app waits a moment for a real learner's held ⏎ to pass
    (B-135). Its own test puts the wait back."""
    try:
        from tutor_app import panels
    except ImportError:
        return
    monkeypatch.setattr(panels.Settling, "SETTLE", 0)
