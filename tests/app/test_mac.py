from pathlib import Path

import pytest

from tutor_app import mac


def test_ipad_import_never_overwrites_a_pdf(tmp_path):  # B-016
    vault, inbox = tmp_path / "vault", tmp_path / "ipad"
    (vault / "Inbox").mkdir(parents=True)
    inbox.mkdir()
    (vault / "Inbox" / "collision.pdf").write_text("FIRST")
    (vault / "Inbox" / "collision 2.pdf").write_text("KEEP SECOND")
    (inbox / "collision.pdf").write_text("NEW")
    assert mac.import_ipad_inbox(vault, inbox) == ["collision 3.pdf"]
    got = {p.name: p.read_text() for p in (vault / "Inbox").iterdir()}
    assert got == {"collision.pdf": "FIRST", "collision 2.pdf": "KEEP SECOND", "collision 3.pdf": "NEW"}


def test_ipad_import_keeps_every_original_in_imported(tmp_path):
    vault, inbox = tmp_path / "vault", tmp_path / "ipad"
    vault.mkdir()
    inbox.mkdir()
    for text in ("ONE", "TWO"):  # the same file name sent from the iPad twice
        (inbox / "scan.pdf").write_text(text)
        mac.import_ipad_inbox(vault, inbox)
    assert sorted(p.read_text() for p in (inbox / "Imported").iterdir()) == ["ONE", "TWO"]
    assert sorted(p.read_text() for p in (vault / "Inbox").iterdir()) == ["ONE", "TWO"]


def test_tests_never_see_the_real_ipad_inbox():
    from tutor_app import config
    assert "Mobile Documents" not in str(config.ICLOUD_INBOX)


def test_a_vault_opened_from_its_parent_folder_counts_as_known(tmp_path, monkeypatch):
    import json
    parent = tmp_path / "AI Workflow"
    vault = parent / "STEM Tutor"
    vault.mkdir(parents=True)
    cfg = tmp_path / "obsidian.json"
    monkeypatch.setattr(mac, "OBSIDIAN_CONFIG", cfg)
    cfg.write_text(json.dumps({"vaults": {"a": {"path": str(parent)}}}))
    assert mac.obsidian_vault_registered(vault) == "inside"
    cfg.write_text(json.dumps({"vaults": {"a": {"path": str(vault)}}}))
    assert mac.obsidian_vault_registered(vault) == "exact"
    cfg.write_text(json.dumps({"vaults": {"a": {"path": str(tmp_path / "elsewhere")}}}))
    assert not mac.obsidian_vault_registered(vault)


def test_one_unreadable_file_is_skipped_not_the_whole_import(tmp_path):
    vault, inbox = tmp_path / "vault", tmp_path / "ipad"
    vault.mkdir()
    inbox.mkdir()
    (inbox / "a.pdf").write_text("A")
    (inbox / "b.pdf").write_text("B")
    (inbox / "a.pdf").chmod(0)  # e.g. an iCloud file still downloading
    try:
        assert mac.import_ipad_inbox(vault, inbox) == ["b.pdf"]
        assert (inbox / "a.pdf").exists()
    finally:
        (inbox / "a.pdf").chmod(0o644)


def test_a_blocked_inbox_is_reported(tmp_path):
    inbox = tmp_path / "ipad"
    inbox.mkdir()
    assert not mac.inbox_blocked(inbox) and not mac.inbox_blocked(tmp_path / "missing")
    inbox.chmod(0)  # what macOS privacy settings do to iCloud Drive for Terminal
    try:
        assert mac.inbox_blocked(inbox)
    finally:
        inbox.chmod(0o755)


def test_the_terminal_window_is_named_while_the_app_runs(tmp_path, monkeypatch, capsys):
    """Asked by the learner: the Terminal title bar showed only the folder, the command and the window size. A terminal
    is told its title with an escape sequence, and Textual sends none."""
    from fixtures import make_vault
    from tutor_app import __main__ as cli
    from tutor_app.app import TutorApp
    during = []
    monkeypatch.setattr(TutorApp, "run", lambda self: during.append(capsys.readouterr().out))
    assert cli.main(["--vault", str(make_vault(tmp_path))]) == 0
    assert during == ["\x1b]0;STEM Tutor\x07"]  # named before the app takes the screen
    assert capsys.readouterr().out == "\x1b]0;\x07"  # and the title handed back when it ends


def test_almanac_exports_in_downloads_move_into_the_vault(tmp_path):
    """The Almanac's Export button saves into Downloads; the tutor reads ticks from the vault's Almanac folder."""
    vault, downloads = tmp_path / "vault", tmp_path / "Downloads"
    (vault / "Almanac").mkdir(parents=True)
    downloads.mkdir()
    (vault / "Almanac" / "almanac-progress-2026-10-02.json").write_text("OLD")
    (downloads / "almanac-progress-2026-10-02.json").write_text("NEW")
    (downloads / "holiday.json").write_text("not the planner's")
    assert mac.import_almanac_exports(vault, downloads) == ["almanac-progress-2026-10-02 2.json"]
    assert [p.name for p in downloads.iterdir()] == ["holiday.json"]  # only the planner's files are moved
    got = {p.name: p.read_text() for p in (vault / "Almanac").iterdir()}
    assert got == {"almanac-progress-2026-10-02.json": "OLD", "almanac-progress-2026-10-02 2.json": "NEW"}
    assert mac.import_almanac_exports(tmp_path / "new vault", tmp_path / "no such folder") == []


def test_a_blocked_downloads_folder_is_an_error_not_silence(tmp_path):
    downloads = tmp_path / "Downloads"
    downloads.mkdir()
    downloads.chmod(0)  # what macOS privacy settings do to Downloads for Terminal
    try:
        with pytest.raises(OSError):
            mac.import_almanac_exports(tmp_path, downloads)
    finally:
        downloads.chmod(0o755)


def test_tests_never_see_the_real_downloads_folder():
    from tutor_app import config
    assert config.DOWNLOADS != Path.home() / "Downloads"


def test_an_original_that_cannot_be_moved_aside_is_not_imported_again_and_again(tmp_path):
    vault, inbox = tmp_path / "vault", tmp_path / "ipad"
    vault.mkdir()
    (inbox / "Imported").mkdir(parents=True)
    (inbox / "a.pdf").write_text("A")
    inbox.chmod(0o555)  # readable, but the original can't be moved into Imported
    try:
        for _ in range(2):
            assert mac.import_ipad_inbox(vault, inbox) == []
    finally:
        inbox.chmod(0o755)
    assert list((vault / "Inbox").iterdir()) == []  # no "a 2.pdf", "a 3.pdf"… one per launch
    (inbox / "Imported").rmdir()
    (inbox / "Imported").write_text("a file where the folder should be")
    assert mac.import_ipad_inbox(vault, inbox) == [] and list((vault / "Inbox").iterdir()) == []


def _doctor(vault, monkeypatch):
    monkeypatch.setattr(mac, "claude_status", lambda: {"installed": True, "logged_in": True})
    return {check.split(":")[0]: (ok, check, fix) for ok, check, fix in mac.doctor(vault)}


def test_doctor_counts_events_as_the_tutor_reads_them_and_warns_of_damaged_lines(tmp_path, monkeypatch):
    from fixtures import make_vault
    vault = make_vault(tmp_path)
    events = vault / ".tutor/events"
    events.mkdir(parents=True, exist_ok=True)
    (events / "2026-09.jsonl").write_text('{"id": "a", "type": "x"}\n\n{"id": "b", "ty\n')  # a blank and a torn line
    rows = _doctor(vault, monkeypatch)
    ok, check, _ = rows["Content packs"]
    assert ok and check.endswith("; 1 study events recorded")
    assert not rows["Study history"][0] and "1 damaged line skipped (2026-09.jsonl:3)" in rows["Study history"][1]
    (vault / ".tutor/packs/CURRENT").write_text("\n")  # an empty pointer is no published pack
    assert not _doctor(vault, monkeypatch)["Content packs"][0]
    (vault / ".tutor/packs/CURRENT").unlink()
    assert "none published" in _doctor(vault, monkeypatch)["Content packs"][1]


def test_doctor_without_a_tutor_folder_does_not_say_the_tutor_still_runs(tmp_path, capsys, monkeypatch):
    from tutor_app import __main__ as cli
    monkeypatch.setattr(mac, "claude_status", lambda: {"installed": True, "logged_in": True})
    cli.main(["doctor", "--vault", str(tmp_path / "nowhere")])
    out = capsys.readouterr().out
    assert "still runs" not in out and "can't start without its folder" in out


@pytest.mark.parametrize("env,theme,want", [
    ({"TERM_PROGRAM": "Apple_Terminal", "TERM_PROGRAM_VERSION": "470"}, "night", True),
    ({"TERM_PROGRAM": "Apple_Terminal", "TERM_PROGRAM_VERSION": "470.2"}, "day", True),
    ({"TERM_PROGRAM": "Apple_Terminal", "TERM_PROGRAM_VERSION": "464"}, "night", False),  # macOS 15: 256 colours
    ({"TERM_PROGRAM": "Apple_Terminal", "TERM_PROGRAM_VERSION": "470"}, "classic", False),  # as it always was
    ({"TERM_PROGRAM": "Apple_Terminal", "TERM_PROGRAM_VERSION": "470", "COLORTERM": "truecolor"}, "night", False),
    ({"TERM_PROGRAM": "iTerm.app", "TERM_PROGRAM_VERSION": "3.5.0"}, "night", False),
    ({"TERM_PROGRAM": "Apple_Terminal"}, "night", False),
])
def test_full_colour_is_turned_on_only_where_terminal_draws_it(env, theme, want):
    assert mac.wants_truecolor(env, theme) is want


def test_the_app_starts_in_full_colour_in_a_new_terminal_with_a_new_look(tmp_path, monkeypatch):
    import json
    from fixtures import make_vault
    from tutor_app import __main__ as cli
    from tutor_app.app import TutorApp
    vault = make_vault(tmp_path)
    (vault / ".tutor/app_settings.json").write_text(json.dumps({"theme": "night"}))
    monkeypatch.setenv("TERM_PROGRAM", "Apple_Terminal")
    monkeypatch.setenv("TERM_PROGRAM_VERSION", "471")
    monkeypatch.setenv("COLORTERM", "")  # unset, and put back as it was after the test
    monkeypatch.setattr(mac, "switch_terminal_profile", lambda *a, **k: "ok", raising=False)
    seen = []
    monkeypatch.setattr(TutorApp, "run", lambda self: seen.append(__import__("os").environ.get("COLORTERM")))
    cli.main(["--vault", str(vault)])
    assert seen == ["truecolor"]


def test_a_tab_is_switched_by_asking_terminal_and_a_failure_is_only_a_failure(monkeypatch):
    import subprocess
    calls = []

    def fake_run(args, **kw):
        calls.append((args, kw.get("input", ""), kw.get("timeout")))
        return subprocess.CompletedProcess(args, 0, stdout="missing\n", stderr="")
    monkeypatch.setattr(mac.subprocess, "run", fake_run)
    assert mac.switch_terminal_profile("/dev/ttys009", "STEM Tutor Night") == "missing"
    (args, script, timeout), = calls
    assert args == ["osascript", "-", "/dev/ttys009", "STEM Tutor Night"] and timeout and "settings set wanted" in script
    assert mac.switch_terminal_profile(None, "STEM Tutor Night") == "" and len(calls) == 1  # not in Terminal: nothing

    def too_slow(args, **kw):
        raise subprocess.TimeoutExpired(args, 3)
    monkeypatch.setattr(mac.subprocess, "run", too_slow)
    assert mac.switch_terminal_profile("/dev/ttys009", "STEM Tutor Night") == ""
    assert mac.terminal_tty() is None  # tests never run as a macOS Terminal tab (conftest)


@pytest.mark.parametrize("theme,switched", [("night", ("/dev/ttys009", "STEM Tutor Night")), ("classic", None)])
def test_the_app_puts_its_tab_in_the_looks_profile_at_start(tmp_path, monkeypatch, theme, switched):
    import json
    from fixtures import make_vault
    from tutor_app import __main__ as cli
    from tutor_app.app import TutorApp
    vault = make_vault(tmp_path)
    (vault / ".tutor/app_settings.json").write_text(json.dumps({"theme": theme}))
    calls, seen = [], []
    monkeypatch.setattr(mac, "terminal_tty", lambda: "/dev/ttys009")
    monkeypatch.setattr(mac, "switch_terminal_profile", lambda tty, name: calls.append((tty, name)) or "missing")
    monkeypatch.setattr(TutorApp, "run", lambda self: seen.append((self.tty, self.profile_missing)))
    cli.main(["--vault", str(vault)])
    assert calls == ([switched] if switched else [])  # Classic: the tab stays as the launcher left it
    assert seen == [("/dev/ttys009", bool(switched))]
