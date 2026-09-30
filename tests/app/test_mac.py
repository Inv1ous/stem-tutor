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
