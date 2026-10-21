"""Asked by the learner: the Lessons folder was one long flat list; each day gets its own folder."""
import sys
from datetime import datetime
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "plugin/stem-tutor/skills/tutor/scripts"))
from tutorlib import views  # noqa: E402


def test_a_new_lesson_log_goes_in_its_days_folder(tmp_path):
    log = views.LessonLog.create(tmp_path, "Lesson - Stress and strain", datetime(2026, 10, 21, 9, 39), name="Lesson - Stress and strain")
    assert log.rel == "Lessons/2026-10-21/0939 Lesson - Stress and strain.md" and (tmp_path / log.rel).exists()
    again = views.LessonLog.create(tmp_path, "x", datetime(2026, 10, 21, 9, 39), name="Lesson - Stress and strain")
    assert again.rel.endswith("0939 Lesson - Stress and strain (2).md")  # restarted within the minute: the first log is kept
    other = views.LessonLog.create(tmp_path, "x", datetime(2026, 10, 22, 9, 39), name="Lesson - Stress and strain")
    assert other.rel == "Lessons/2026-10-22/0939 Lesson - Stress and strain.md"


def flat(tmp_path, *names):
    (tmp_path / "Lessons").mkdir(exist_ok=True)
    for n in names:
        (tmp_path / "Lessons" / n).write_text(f"# {n}\n")


def test_old_flat_logs_move_into_day_folders_and_their_links_follow(tmp_path):
    flat(tmp_path, "2026-10-04 1539 Lesson - Stress and strain.md", "2026-10-04 1812 Review - review.md",
         "2026-10-16 0949 Autopilot - Today's plan.md", "notes.md")
    (tmp_path / "Home.md").write_text("- [[Lessons/2026-10-04 1539 Lesson - Stress and strain]]\n"
                                      "- [[Lessons/2026-10-16 0949 Autopilot - Today's plan|the plan]]\n- [[My Notes/x]]\n")
    moved = views.organise_lessons(tmp_path)
    assert sorted(new for _, new in moved) == ["Lessons/2026-10-04/1539 Lesson - Stress and strain.md",
                                               "Lessons/2026-10-04/1812 Review - review.md",
                                               "Lessons/2026-10-16/0949 Autopilot - Today's plan.md"]
    assert (tmp_path / "Lessons/notes.md").exists() and not (tmp_path / "Lessons/2026-10-04 1812 Review - review.md").exists()
    assert (tmp_path / "Home.md").read_text() == ("- [[Lessons/2026-10-04/1539 Lesson - Stress and strain]]\n"
                                                  "- [[Lessons/2026-10-16/0949 Autopilot - Today's plan|the plan]]\n- [[My Notes/x]]\n")
    undo, = (tmp_path / ".tutor/backups").glob("lessons-moved-*.txt")  # what moved is written down, so it can be undone
    assert "Lessons/2026-10-04 1539 Lesson - Stress and strain.md -> Lessons/2026-10-04/1539 Lesson - Stress and strain.md" in undo.read_text()
    assert views.organise_lessons(tmp_path) == []  # once is enough


def test_the_move_never_overwrites_and_leaves_other_files_alone(tmp_path):
    flat(tmp_path, "2026-10-04 1539 Lesson - A.md")
    taken = tmp_path / "Lessons/2026-10-04/1539 Lesson - A.md"
    taken.parent.mkdir()
    taken.write_text("already here")
    assert views.organise_lessons(tmp_path) == [] and taken.read_text() == "already here"
    assert (tmp_path / "Lessons/2026-10-04 1539 Lesson - A.md").exists()
    assert views.organise_lessons(tmp_path / "nowhere") == []  # no Lessons folder: nothing to do


def test_a_session_saved_before_the_move_finds_its_log_after_it(tmp_path):
    flat(tmp_path, "2026-10-04 1539 Lesson - A.md")
    old = "Lessons/2026-10-04 1539 Lesson - A.md"
    assert views.lesson_rel(tmp_path, old) == old
    views.organise_lessons(tmp_path)
    assert views.lesson_rel(tmp_path, old) == "Lessons/2026-10-04/1539 Lesson - A.md"
    assert views.lesson_rel(tmp_path, "Lessons/2026-10-09 0900 missing.md") == "Lessons/2026-10-09 0900 missing.md"


def test_recent_lessons_are_newest_first_whether_flat_or_in_a_day_folder(tmp_path):
    flat(tmp_path, "2026-10-04 1539 Lesson - A.md", "2026-10-16 0949 Lesson - C.md")
    for rel in ("Lessons/2026-10-16/1412 Lesson - D.md", "Lessons/2026-10-04/1800 Lesson - B.md", "Lessons/2026-10-21/0939 Lesson - E.md"):
        (tmp_path / rel).parent.mkdir(parents=True, exist_ok=True)
        (tmp_path / rel).write_text("x")
    assert views.recent_lessons(tmp_path) == [
        "Lessons/2026-10-21/0939 Lesson - E.md", "Lessons/2026-10-16/1412 Lesson - D.md", "Lessons/2026-10-16 0949 Lesson - C.md",
        "Lessons/2026-10-04/1800 Lesson - B.md", "Lessons/2026-10-04 1539 Lesson - A.md"]
    assert views.recent_lessons(tmp_path / "nowhere") == []
