"""Concept-map colours follow mastery outside lessons: only node lines of changed subtopics are rewritten, off-thread."""
import random
import time

from fixtures import make_vault
from test_session import T0
from tutorlib import mermaid_refresh, session, store, views

SUB = "9702-2.1"


def _tutor(tmp_path):
    return session.Tutor(store.Vault(make_vault(tmp_path)), rng=random.Random(0), now=lambda: T0)


def _answer(tutor, kc, right: bool):
    tutor.log({"type": "answer", "id": f"a{time.perf_counter_ns()}", "kcs": [kc], "item": "9702-2.1-i01",
               "grade": {"score": 1 if right else 0, "correct": right}, "conf": 3, "hinted": False})


def _node_lines(text):
    return [line for line in text.splitlines() if line.lstrip().startswith("n") and ":::" in line]


def test_refresh_text_rewrites_only_node_classes_and_marks(tmp_path):
    tutor = _tutor(tmp_path)
    old = views.concept_map(tutor.packs, tutor.state, SUB, current="9702-2.1.4")
    text = f"Intro I wrote.\n\n{old}\n\nAfter text.\n"
    titles = mermaid_refresh._Titles(tutor.packs)
    statuses = {SUB: {"9702-2.1.1": "gap", "9702-2.1.4": "secure"}}
    new = mermaid_refresh.refresh_text(text, titles, statuses)
    changed = [(a, b) for a, b in zip(text.splitlines(), new.splitlines()) if a != b]
    assert len(new.splitlines()) == len(text.splitlines())
    assert changed == [(_node_lines(text)[0], '  n0["🔴 Distance, displacement, speed, velocity"]:::gap'),
                       (_node_lines(text)[1], '  n1["✅ suvat"]:::now')]  # the highlighted idea keeps :::now
    assert mermaid_refresh.refresh_text(new, titles, statuses) == new  # idempotent
    assert mermaid_refresh.refresh_text(text, titles, {"9702-9.9": {}}) == text  # other subtopics untouched


def test_answer_outside_a_lesson_recolours_note_and_lesson_maps_in_background(tmp_path):
    tutor = _tutor(tmp_path)
    root = tutor.vault.root
    note = root / views.notes_update(root, tutor.packs, tutor.state, SUB)
    note.write_text(note.read_text() + "\nMy own text ```not mermaid```.\n")
    lesson = root / "Lessons" / "2026-09-28" / "0900 Lesson - Equations of motion.md"
    lesson.parent.mkdir(parents=True)
    lesson.write_text("# Lesson\n\n" + views.concept_map(tutor.packs, tutor.state, SUB) + "\n\nThe end.\n")
    before = {p: p.read_text() for p in (note, lesson)}
    refresher = tutor.enable_map_refresh(background=True)

    t0 = time.perf_counter()
    for _ in range(3):
        _answer(tutor, "9702-2.1.1", right=False)  # practice / topical attempt: no lesson running
    elapsed = time.perf_counter() - t0
    assert refresher.flush(timeout=5)
    assert not refresher.errors
    status = views.kc_status(tutor.state, "9702-2.1.1")
    assert status != "new"
    for path, old in before.items():
        new = path.read_text()
        assert f'{views.STATUS[status]} Distance, displacement, speed, velocity"]:::{views._MAP_CLASS[status]}' in new
        diff = [(a, b) for a, b in zip(old.splitlines(), new.splitlines()) if a != b]
        assert len(new.splitlines()) == len(old.splitlines()) and len(diff) == 1  # only that node line
    assert elapsed < 1.0  # the answer path only diffs statuses; files are written by the worker


def test_unchanged_mastery_writes_nothing_and_rerun_is_idempotent(tmp_path):
    tutor = _tutor(tmp_path)
    root = tutor.vault.root
    note = root / views.notes_update(root, tutor.packs, tutor.state, SUB)
    refresher = tutor.enable_map_refresh(background=False)
    tutor.log({"type": "chapter_started", "chapter": "9702-2"})  # no idea changes status
    assert refresher.written == []
    _answer(tutor, "9702-2.1.4", right=False)
    assert refresher.written == [note.relative_to(root).as_posix()]
    once = note.read_bytes()
    refresher.changed({}, tutor.state)  # same statuses queued again
    assert note.read_bytes() == once


def test_live_lesson_log_and_protected_files_are_not_rewritten(tmp_path):
    tutor = _tutor(tmp_path)
    root = tutor.vault.root
    tutor.start("test", focus=[SUB])
    live = root / views.lesson_rel(root, tutor.session["log"])
    live.parent.mkdir(parents=True, exist_ok=True)
    live.write_text((live.read_text() if live.exists() else "") + views.concept_map(tutor.packs, tutor.state, SUB))
    assert ":::todo" in live.read_text()
    linked = root / "Lessons" / "linked.md"
    linked.write_text(views.concept_map(tutor.packs, tutor.state, SUB))
    (root / "Lessons" / "alias.md").hardlink_to(linked)
    snap = {p: p.read_bytes() for p in (live, linked)}
    refresher = tutor.enable_map_refresh(background=False)
    _answer(tutor, "9702-2.1.1", right=False)
    assert not refresher.errors
    assert all(p.read_bytes() == data for p, data in snap.items())
    assert refresher.written == []  # neither the live log nor the hard-linked copies


def test_snapshot_diff_is_cheap(tmp_path):
    tutor = _tutor(tmp_path)
    state = {"kcs": {f"k{i}": {"n": 0} for i in range(3000)}, "gaps": []}
    t0 = time.perf_counter()
    for _ in range(10):
        mermaid_refresh.changed_kcs(mermaid_refresh.snapshot(state), mermaid_refresh.snapshot(state))
    assert (time.perf_counter() - t0) / 10 < 0.05
