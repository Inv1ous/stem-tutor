import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "plugin/stem-tutor/skills/tutor/scripts"))
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(Path(__file__).parent))
sys.path.insert(0, str(ROOT / "app"))


import pytest  # noqa: E402


@pytest.fixture(autouse=True)
def _no_real_tutor_vault(tmp_path, monkeypatch):
    """Default every test process to disposable learner state and Library copies."""
    monkeypatch.setenv("STEM_TUTOR_VAULT", str(tmp_path / "STEM Tutor"))


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
    # Tests must explicitly supply a fake provider instead of discovering an installed paid CLI.
    monkeypatch.setenv("STEM_EXTRACT_CODEX", str(tmp_path / "no-extraction-codex"))
    monkeypatch.setenv("STEM_EXTRACT_CLAUDE", str(tmp_path / "no-extraction-claude"))


@pytest.fixture(autouse=True)
def _options_take_enter_at_once(monkeypatch):
    """A pilot presses ⏎ the instant a question appears; the app waits a moment for a real learner's held ⏎ to pass
    (B-135). Its own test puts the wait back."""
    try:
        from tutor_app import panels
    except ImportError:
        return
    monkeypatch.setattr(panels.Settling, "SETTLE", 0)


@pytest.fixture(autouse=True)
def _resize_lays_out_at_once(monkeypatch):
    """A pilot resizes and checks the layout straight away; the app waits for a dragged window to settle first. Its own
    test (test_resize_stability) puts the wait back."""
    try:
        from tutor_app.app import TutorApp
    except ImportError:
        return
    monkeypatch.setattr(TutorApp, "RESIZE_SETTLE", 0)


@pytest.fixture(autouse=True)
def _engine_loads_before_the_first_pause(monkeypatch):
    """The app builds its engine on a thread so the loading screen stays responsive; a pilot expects the menu after its
    first pause. Its own test (test_resize_stability) loads in the background again."""
    try:
        from tutor_app.app import TutorApp
    except ImportError:
        return
    monkeypatch.setattr(TutorApp, "LOAD_IN_BACKGROUND", False)
