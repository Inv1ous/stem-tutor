"""A subtopic keeps ONE personal note: later sessions add to it, never start a second file or a stray folder."""
import random
from types import SimpleNamespace

from fixtures import make_vault
from test_session import T0
from tutorlib import session, store, views

SUB = "9702-2.1"


def _fake_packs(note, root=None):
    return SimpleNamespace(
        pack=lambda sub: {"note": note} if note is not None else {},
        subtopics={"9701-5.1": {"spec": "9701", "topic": "9701-5", "title": "Enthalpy change, ΔH"},
                   "9701-1.3": {"spec": "9701", "topic": "9701-1", "title": "Electrons"}},
        topics={"9701-5": {"title": "Chemical energetics"}, "9701-1": {"title": "Atomic structure"}},
        vault_root=root, _packs={})


def test_published_library_note_mirrors_course_chapter_folders_not_bare_spec():
    # root cause of the stray `My Notes/9701/Chemical energetics/9701-5.1 ….md`: a pack note published into the Library
    note = "Library/Courses/9701/Notes/Published/v271/Subjects/9701 Chemistry/05 Chemical energetics/5.1 Enthalpy change, ΔH.md"
    assert views.notes_rel(_fake_packs(note), "9701-5.1") == \
        "My Notes/9701 Chemistry/05 Chemical energetics/5.1 Enthalpy change, ΔH.md"


def test_note_without_reference_still_uses_course_and_numbered_chapter(tmp_path):
    (tmp_path / "My Notes" / "9701 Chemistry").mkdir(parents=True)
    rel = views.notes_rel(_fake_packs(None, tmp_path), "9701-5.1")
    assert rel == "My Notes/9701 Chemistry/05 Chemical energetics/5.1 Enthalpy change, ΔH.md"
    assert not rel.startswith("My Notes/9701/")


def _tutor(tmp_path):
    return session.Tutor(store.Vault(make_vault(tmp_path)), rng=random.Random(0), now=lambda: T0)


def _sess(sid, log="Lessons/2026-09-29/1700 Lesson - Equations of motion.md"):
    return {"id": sid, "started": T0.isoformat(), "mode": "learn", "log": log}


def test_second_session_appends_to_existing_note_idempotently(tmp_path):
    tutor = _tutor(tmp_path)
    root = tutor.vault.root
    node = {"kc": "9702-2.1.1", "note": "Displacement is a vector.", "own_words": "It has direction.", "mistakes": []}
    rel = views.notes_update(root, tutor.packs, tutor.state, SUB, node=node, session=_sess("aaaa1111"))
    note = root / rel
    note.write_text(note.read_text() + "\nMy own paragraph stays.\n")  # a learner edit outside the markers

    node2 = {"kc": "9702-2.1.4", "note": "suvat needs uniform a.", "own_words": None, "mistakes": ["used s=vt"]}
    for _ in range(2):  # the same session written twice must not duplicate anything
        assert views.notes_update(root, tutor.packs, tutor.state, SUB, node=node2, session=_sess("bbbb2222")) == rel
    text = note.read_text()
    assert [p.name for p in note.parent.glob("*.md")] == [note.name]  # one file only
    assert text.count("<!-- stem-tutor:session bbbb2222 -->") == 1
    assert text.count("<!-- stem-tutor:session aaaa1111 -->") == 1
    assert text.count("<!-- stem-tutor:node 9702-2.1.4 -->") == 1
    assert "My own paragraph stays." in text and "It has direction." in text
    assert text.count("## Session 2026-09-29 17:00") == 2
    # newest session last, and the ideas covered are merged, not repeated
    assert text.index("session aaaa1111") < text.index("session bbbb2222")
    views.notes_update(root, tutor.packs, tutor.state, SUB, current="9702-2.1.1", session=_sess("bbbb2222"))
    block = views._block("session bbbb2222").search(note.read_text()).group(0)
    assert "- Ideas: suvat · Distance, displacement, speed, velocity" in block
    assert block.count("suvat") == 1
    assert "[[Lessons/2026-09-29/1700 Lesson - Equations of motion\\|lesson log]]" in block


def test_existing_note_elsewhere_in_my_notes_is_reused_and_linked(tmp_path):
    tutor = _tutor(tmp_path)
    root = tutor.vault.root
    moved = root / "My Notes" / "Physics notes" / "kinematics.md"
    moved.parent.mkdir(parents=True)
    moved.write_text(f"---\nsubtopic: {SUB}\n---\n# mine\n\nKeep me.\n")
    rel = views.notes_update(root, tutor.packs, tutor.state, SUB, session=_sess("cccc3333"))
    assert rel == "My Notes/Physics notes/kinematics.md"
    assert not (root / views.notes_rel(tutor.packs, SUB)).exists()  # no second file
    assert "Keep me." in moved.read_text() and "session cccc3333" in moved.read_text()
    views.write_home(root, tutor.packs, tutor.state, T0, [])
    assert "[[My Notes/Physics notes/kinematics\\|My notes]]" in (root / "Home.md").read_text()


def test_learning_sessions_add_to_the_single_existing_note(tmp_path):
    from test_session import _drive_lesson
    tutor = _tutor(tmp_path)
    root = tutor.vault.root
    first = views.notes_update(root, tutor.packs, tutor.state, SUB)
    sids = []
    for _ in range(2):  # two lessons on the same subtopic
        tutor.start("lesson", minutes=40, focus=[SUB])
        sids.append(tutor.session["id"])
        _drive_lesson(tutor)
        if tutor.session is not None:
            tutor.end()
    assert len(set(sids)) == 2
    text = (root / first).read_text()
    assert sorted(p.relative_to(root).as_posix() for p in (root / "My Notes").rglob("*.md")) == [first]
    for sid in sids:
        assert text.count(f"<!-- stem-tutor:session {sid} -->") == 1
    assert text.index(f"session {sids[0]}") < text.index(f"session {sids[1]}")
    assert text.count("<!-- stem-tutor:node 9702-2.1.1 -->") == 1
