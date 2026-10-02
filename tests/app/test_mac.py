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
