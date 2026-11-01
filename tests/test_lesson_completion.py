"""A lesson completion commits once, retaining the learner's own words on retry."""
import copy
import random

import pytest

from fixtures import make_vault
from test_session import T0, _answer_all
from tutorlib import session, store, views


KC = "9702-2.1.1"
WORDS = "My explanation: displacement includes direction; distance does not."


def before_completion(tmp_path):
    tutor = session.Tutor(store.Vault(make_vault(tmp_path)), rng=random.Random(0), now=lambda: T0)
    tutor.start("lesson", minutes=40, focus=[KC])
    for _ in range(40):
        activity = tutor.next()
        kind = activity["activity"]
        if kind == "choose":
            tutor.respond({"choice": "scratch"})
        elif kind == "plan":
            tutor.respond({"teach": activity["default_teach"]})
        elif kind == "own_words":
            tutor.respond({"text": WORDS})
            return tutor
        elif kind in ("questions", "awaiting"):
            _answer_all(tutor, activity, good=True)
        else:
            tutor.respond({})
    pytest.fail("Public lesson did not reach its own-words step")


def finish(tutor):
    for _ in range(20):
        activity = tutor.next()
        if activity["activity"] == "end":
            return
        if activity["activity"] in ("questions", "awaiting"):
            _answer_all(tutor, activity, good=True)
        else:
            tutor.respond({})
    pytest.fail("Public lesson did not finish")


@pytest.mark.parametrize("boundary", ["notes", "before_append", "after_append", "after_log"])
@pytest.mark.parametrize("retry", ["live", "restart"])
def test_completion_failure_retries_exact_node_and_words_with_one_durable_completion(tmp_path, monkeypatch,
                                                                                   boundary, retry):
    tutor = before_completion(tmp_path)
    sid, rel = tutor.session["id"], tutor.session["log"]
    cursor = tutor.session["cursor"]
    prefix = {p: p.read_bytes() for p in (tutor.vault.tutor / "events").glob("*.jsonl")}
    real_notes, real_append, real_log = views.notes_update, tutor.vault.append_event, tutor.log

    def failed_notes(*args, **kwargs):
        if kwargs.get("node") is not None:
            raise OSError("completion persistence unavailable")
        return real_notes(*args, **kwargs)

    def failed_append(event, **kwargs):
        if event["type"] != "node_done":
            return real_append(event, **kwargs)
        if boundary == "after_append":
            real_append(event, **kwargs)
        raise OSError("completion persistence unavailable")

    def failed_log(event):
        result = real_log(event)
        if event["type"] == "node_done":
            raise OSError("completion persistence unavailable")
        return result

    with monkeypatch.context() as patch:
        if boundary == "notes":
            patch.setattr(views, "notes_update", failed_notes)
        elif boundary == "after_log":
            patch.setattr(tutor, "log", failed_log)
        else:
            patch.setattr(tutor.vault, "append_event", failed_append)
        with pytest.raises(OSError, match="completion persistence unavailable"):
            tutor.next()
    assert tutor.session["cursor"] == cursor
    assert tutor.session["blocks"][cursor]["own_words"] == WORDS
    assert WORDS in (tutor.vault.root / rel).read_text()
    if retry == "restart":
        tutor = session.Tutor(tutor.vault, now=lambda: T0)
    finish(tutor)

    completions = [e for e in tutor.vault.events() if e["type"] == "node_done"]
    assert len(completions) == 1 and completions[0]["kc"] == KC
    assert tutor.session["id"] == sid and tutor.session["log"] == rel
    assert tutor.session["kcs_learned"] == [KC]
    assert tutor.state == tutor._fold()
    notes = next((tutor.vault.root / "My Notes").rglob("*.md")).read_text()
    assert notes.count(WORDS) == 1
    assert all(p.read_bytes().startswith(data) for p, data in prefix.items())
    assert tutor.end()["kcs_learned"] == [KC]


def test_ordinary_public_lesson_completion_remains_once_and_keeps_words(tmp_path):
    tutor = before_completion(tmp_path)
    finish(tutor)
    assert tutor.session["kcs_learned"] == [KC]
    assert len([e for e in tutor.vault.events() if e["type"] == "node_done"]) == 1
    assert WORDS in next((tutor.vault.root / "My Notes").rglob("*.md")).read_text()


def test_saved_distinct_blocks_for_same_kc_keep_separate_completion_bindings(tmp_path):
    tutor = before_completion(tmp_path)
    cursor = tutor.session["cursor"]
    second = copy.deepcopy(tutor.session["blocks"][cursor])
    second["own_words"] = "Another explanation from a second node for the same idea."
    tutor.session["blocks"].insert(cursor + 1, second)
    tutor._save()  # preserve a saved lesson containing two distinct node blocks
    tutor = session.Tutor(tutor.vault, now=lambda: T0)

    finish(tutor)

    completions = [e for e in tutor.vault.events() if e["type"] == "node_done"]
    assert len(completions) == 2
    assert [e["node"] for e in completions] == [cursor, cursor + 1]
    assert all(e["kc"] == KC and e["session"] == tutor.session["id"] for e in completions)
    notes = next((tutor.vault.root / "My Notes").rglob("*.md")).read_text()
    assert WORDS in notes and second["own_words"] in notes


def test_repeated_real_note_write_conflicts_keep_completion_pending_until_retry(tmp_path, monkeypatch):
    tutor = before_completion(tmp_path)
    note = tutor.vault.root / views.notes_rel(tutor.packs, "9702-2.1")
    before = note.read_bytes()
    real_write = store.write_text
    attempts = []

    def concurrent_write(path, text, **kwargs):
        if path == note:
            attempts.append(text)
            note.write_text(note.read_text() + f"\nConcurrent learner paragraph {len(attempts)}.\n")
        return real_write(path, text, **kwargs)

    with monkeypatch.context() as patch:
        patch.setattr(store, "write_text", concurrent_write)
        with pytest.raises(OSError, match="changed repeatedly"):
            tutor.next()
    assert len(attempts) == 5
    assert note.read_bytes().startswith(before) and WORDS not in note.read_text()
    assert not any(e["type"] == "node_done" for e in tutor.vault.events())
    finish(tutor)
    assert tutor.session["kcs_learned"] == [KC]
    assert WORDS in note.read_text()
    assert all(f"Concurrent learner paragraph {i}." in note.read_text() for i in range(1, 6))
    assert len([e for e in tutor.vault.events() if e["type"] == "node_done"]) == 1


def test_already_identical_note_is_success_when_compare_writer_reports_no_change(tmp_path, monkeypatch):
    tutor = before_completion(tmp_path)
    block = tutor.session["blocks"][tutor.session["cursor"]]
    node = {"kc": KC, "note": block["card"].get("note", ""), "own_words": block["own_words"],
            "mistakes": block.get("mistakes")}
    rel = views.notes_update(tutor.vault.root, tutor.packs, tutor.state, "9702-2.1", node=node)
    path = tutor.vault.root / rel
    original = path.read_bytes()
    real_write = store.write_text
    unchanged = []

    def write_or_no_change(destination, text, **kwargs):
        if destination == path and text == path.read_text():
            unchanged.append(True)
            return False  # an unchanged note is a successful idempotent binding
        return real_write(destination, text, **kwargs)

    monkeypatch.setattr(store, "write_text", write_or_no_change)
    finish(tutor)
    assert unchanged
    assert path.read_bytes() == original
    assert tutor.session["kcs_learned"] == [KC]
    assert len([e for e in tutor.vault.events() if e["type"] == "node_done"]) == 1
