"""Quality-of-life fixes from the bug watch's QOL list (bugwatch/codex/QOL.md), engine side."""
import json
import random
import sys
from datetime import date
from pathlib import Path

from fixtures import PACK, make_vault
from test_session import T0, Clock, _drive_lesson
from tutorlib import anki, insights, report, session, store, views

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "build"))
import content_checks  # noqa: E402

RIGHT = {"correct": True, "score": 1.0, "error": None, "misconception": None}


def tutor_at(root, now=T0):
    return session.Tutor(store.Vault(root), rng=random.Random(0), now=Clock(now))


def test_home_links_each_subtopic_to_its_explanation_before_any_notes_exist(tmp_path):
    """Q-006: an unstarted row was plain text, so the subtopic's explanation had to be found in the vault tree."""
    root = make_vault(tmp_path)
    t = tutor_at(root)
    views.write_home(root, t.packs, t.state, T0)
    assert "| 9702-2.1 Equations of motion |" in (root / "Home.md").read_text()  # no note published: plain, as before
    note = root / PACK["note"]
    note.parent.mkdir(parents=True)
    note.write_text("# Equations of motion\n")
    views.write_home(root, t.packs, t.state, T0)
    assert "| [[Subjects/9702 Physics/02 Kinematics/2.1 Equations of motion\\|9702-2.1 Equations of motion]] |" \
        in (root / "Home.md").read_text()


def test_the_mistake_journal_keeps_the_whole_question_folded_under_its_preview(tmp_path):
    """Q-007: a "which statements are correct" question lost its statements and choices in the journal."""
    stem = "Which statements are correct about the two isotopes of chlorine?\n\n1. Different masses.\n2. Same reactions."
    lines = report._full_question(stem, {"A": "1 and 2", "B": "1 only"})
    assert lines[0] == "  > [!question]- The whole question"
    assert "  > 2. Same reactions." in lines and "  > **B** 1 only" in lines and "  >" in lines
    assert report._full_question("What is the speed?", None) == []  # the preview already says it all
    assert report._full_question("(item x)", {"A": "1"}) == []
    root = make_vault(tmp_path)
    t = tutor_at(root)
    t.log({"type": "answer", "item": "9702-2.1-gone", "kcs": ["9702-2.1.1"], "subject": "phys", "difficulty": 3,
           "conf": 3, "hinted": False, "marks": 1, "stem": stem, "response": "B", "key": "A",
           "grade": {"correct": False, "score": 0.0, "error": None, "misconception": None}})
    report.mistakes_note(t)
    text = (root / "Mistakes.md").read_text()
    assert "Question: Which statements are correct about the two isotopes of chlorine?…" in text
    assert "  > [!question]- The whole question" in text and "  > 1. Different masses." in text


def test_weekly_reads_the_event_log_once(tmp_path, monkeypatch):
    """Q-016: the week's report parsed the whole log three times."""
    root = make_vault(tmp_path)
    t = tutor_at(root)
    for _ in range(3):
        t.log({"type": "answer", "item": "x", "kcs": ["9702-2.1.1"], "subject": "phys", "difficulty": 3, "conf": 3,
               "hinted": False, "marks": 1, "grade": RIGHT})
    reads = []
    real = t.vault.events
    monkeypatch.setattr(t.vault, "events", lambda: reads.append(1) or real())
    r = insights.week_report(t, date(2026, 9, 28))
    assert len(reads) == 1 and r["answers"] == 3


def test_a_corrected_flashcard_is_sent_again_under_its_own_guid(tmp_path):
    """Q-019: a card already exported was skipped for ever, so a correction never reached Anki."""
    root = make_vault(tmp_path)
    t = tutor_at(root)
    t.log({"type": "answer", "item": "x", "kcs": ["9702-2.1.1"], "subject": "phys", "difficulty": 3, "conf": 3,
           "hinted": False, "marks": 1, "grade": RIGHT})
    assert anki.export(t)["cards"] == 1 and anki.export(t)["cards"] == 0
    path = root / ".tutor/packs/v1/specs/9702/packs/9702-2.1.json"
    pack = json.loads(path.read_text())
    pack["flashcards"][0]["back"] = "Distance moved in a stated direction (a vector)."
    path.write_text(json.dumps(pack))
    t = tutor_at(root)  # the next start reads the corrected pack
    r = anki.export(t)
    assert r["cards"] == 1 and r["updated"] == 1
    from test_anki import _notes
    (row,) = _notes(root / r["path"])
    assert row[0] == anki.guid("9702-2.1:fc1") and "a vector" in row[1]  # the same note, so Anki updates it
    assert anki.export(t)["cards"] == 0


def test_cards_exported_before_fingerprints_were_kept_are_not_sent_again_unchanged(tmp_path):
    root = make_vault(tmp_path)
    t = tutor_at(root)
    t.log({"type": "answer", "item": "x", "kcs": ["9702-2.1.1"], "subject": "phys", "difficulty": 3, "conf": 3,
           "hinted": False, "marks": 1, "grade": RIGHT})
    t.log({"type": "anki_export", "cards": ["9702-2.1:fc1"], "path": "Anki/old.apkg"})  # an export from before 2.5.19
    assert anki.export(t)["cards"] == 0  # unchanged: not sent again, but its fingerprint is kept from now on
    assert "9702-2.1:fc1" in t.state["anki_hashes"]


def test_the_session_counts_exam_marks_as_well_as_whole_questions(tmp_path):
    """Q-017: 3 of 4 scheme points showed as "Not quite" and the summary as 0% accuracy."""
    t = tutor_at(make_vault(tmp_path))
    t.start("lesson", minutes=40, focus=["9702-2.1"])
    _drive_lesson(t)
    summary = t.end()
    earned, total = summary["marks"]
    assert total >= summary["answered"] > 0 and 0 <= earned <= total


def test_text_the_paper_lost_is_found_and_shown_as_boxes():
    """Q-009: past-paper text with a lost symbol or a shifted font was shown as if it were the question."""
    assert views.garbled("FRQFHQWUDWLRQ \x13 \x13 WLPH") and views.garbled("A tick \x01 here")
    assert not views.garbled("The CONCENTRATION of HCl, measured with TIME") and not views.garbled("ΔH = −92 kJ")
    assert views.unreadable("a \x01 b") == "a □ b"
    assert content_checks.tidy_script_text("In\x03which\x03equilibrium") == "In which equilibrium"  # \x03 is a space


def test_a_scanned_question_with_broken_text_shows_the_scan_first_and_folds_the_text(tmp_path):
    t = tutor_at(make_vault(tmp_path))
    t.session = {"presented": {"1": {"unassisted": False, "inst": {
        "kind": "mcq", "stem": "Which graph shows the change?", "image": "Assets/mcq/q18.png", "marks": 1,
        "options": {"A": "FRQFHQWUDWLRQ", "B": "fine text", "C": "x \x13 y", "D": "also fine"}}}}}
    view = t._view(1)
    assert view["garbled"] == {"stem": False, "options": ["A", "C"]}
    block = views.question_block(view)
    assert block.index("![[Assets/mcq/q18.png]]") < block.index("may be wrong")
    assert "> > [!warning]- The text read from the paper may be wrong" in block and "x □ y" in block
    t.session["presented"]["1"]["inst"]["options"] = {"A": "clean", "B": "text"}
    assert "garbled" not in t._view(1)  # clean text: shown as always


def test_labels_and_table_cells_copied_out_of_a_figure_give_way_to_the_picture(tmp_path):
    """Q-009, reported again by the learner: a past-paper question showed its diagram's labels (force, extension, 00,
    stretching, contraction, rubber, cord, weight) as lines of the question, under a scan that shows them properly."""
    stem = ("A rubber cord hangs from a rigid support. A weight attached to its lower end is gradually\n"
            "increased from zero, and then gradually reduced to zero.\nforce\nextension\n00\nstretching\ncontraction\n"
            "rubber\ncord\nweight\nThe force–extension curve for contraction is below the force–extension curve for "
            "stretching.\nWhat does the shaded area between the curves represent?")
    text, aside = views.figure_text(stem)
    assert "(see the picture)" in text and "stretching\ncontraction" not in text
    assert aside == ["force", "extension", "00", "stretching", "contraction", "rubber", "cord", "weight"]
    assert text.startswith("A rubber cord") and text.endswith("represent?")
    table = "Recorded every 30 s.\ntime / s\ntotal volume of\nhydrogen gas / cm³\n0\n0\n30\n64\nWhat is P – Q?"
    assert views.figure_text(table)[0] == "Recorded every 30 s.\n(see the picture)\nWhat is P – Q?"
    assert views.figure_text("Two lines only.\nreaction X\n2NOBr →2NO + Br₂\nWhich?")[1] == []  # equations and short runs stay
    t = tutor_at(make_vault(tmp_path))
    inst = {"kind": "mcq", "stem": stem, "image": "Assets/mcq/9702_w19_12_q19.png", "marks": 1,
            "options": {"A": "elastic potential energy", "B": "thermal energy"}, "source": {"type": "past", "ref": "P12 Q19"}}
    t.session = {"presented": {"1": {"unassisted": False, "inst": inst}}}
    view = t._view(1)
    assert "(see the picture)" in view["stem"] and view["figure_text"][0] == "force"
    block = views.question_block(view)
    assert "> > [!note]- Text read from the picture" in block and "stretching\n> contraction" not in block
    inst["source"] = {"type": "generated"}  # only past-paper scans: a generated figure's text is the question's own
    assert "figure_text" not in t._view(1)
