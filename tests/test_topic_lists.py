"""Every list of all the topics is grouped and in order. Asked by the learner: they were one bundle, no order, no formatting."""
import sys
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "plugin/stem-tutor/skills/tutor/scripts"))
from tutorlib import model, views  # noqa: E402


def packs_of(tmp_path):
    topics = {"9701-1": {"id": "9701-1", "title": "Atomic structure", "level": "AS", "spec": "9701", "subject": "chem"},
              "9701-10": {"id": "9701-10", "title": "Group 17", "level": "AS", "spec": "9701", "subject": "chem"},
              "9702-1": {"id": "9702-1", "title": "Physical quantities", "level": "AS", "spec": "9702", "subject": "phys"},
              "P1": {"id": "P1", "title": "Pure Mathematics 1", "level": "P1", "spec": "P1", "subject": "math"},
              "M1": {"id": "M1", "title": "Mechanics 1", "level": "M1", "spec": "M1", "subject": "math"}}
    names = {"9701-1": ["Particles", "Isotopes", "Electrons"] + [f"Idea {i}" for i in range(4, 11)], "9701-10": ["Halogens"],
             "9702-1": ["Units"], "P1": ["Algebra", "Quadratics"], "M1": ["Kinematics"]}
    subtopics, kcs = {}, {}
    for topic, titles in names.items():
        for i, title in enumerate(titles, 1):
            sub = f"{topic}.{i}" if topic[0] == "9" else f"{topic}-{i}"
            subtopics[sub] = {"id": sub, "title": title, "topic": topic, "spec": topic.split("-")[0]}
            kcs[f"{sub}.1"] = {"subtopic": sub, "subject": topics[topic]["subject"], "title": title}
    return SimpleNamespace(topics=topics, subtopics=subtopics, kcs=kcs, pack=lambda sub: {"note": ""})


def test_subtopics_are_grouped_into_subjects_and_chapters_in_natural_order(tmp_path):
    groups = views.subtopic_groups(packs_of(tmp_path))
    assert [g["name"] for g in groups] == ["Chemistry 9701", "Physics 9702", "Maths"]
    chem = groups[0]["chapters"]
    assert [c["name"] for c in chem] == ["1. Atomic structure (AS)", "10. Group 17 (AS)"]  # chapter 10 after 1, in syllabus order
    assert chem[0]["subs"][:3] == ["9701-1.1", "9701-1.2", "9701-1.3"] and chem[0]["subs"][-1] == "9701-1.10"
    assert [c["name"] for c in groups[2]["chapters"]] == ["P1  Pure Mathematics 1", "M1  Mechanics 1"]
    only = views.subtopic_groups(packs_of(tmp_path), ["P1-2", "9702-1.1"])
    assert [g["name"] for g in only] == ["Physics 9702", "Maths"] and only[1]["chapters"][0]["subs"] == ["P1-2"]
    assert views.natural("9701-1.2") < views.natural("9701-1.10")


def test_the_vault_home_page_has_a_table_per_subject_with_a_row_per_chapter(tmp_path):
    state = model.new_state()
    text = (tmp_path / views.write_home(tmp_path, packs_of(tmp_path), state,
                                        datetime(2026, 10, 19, 9, 0, tzinfo=timezone.utc))).read_text()
    assert "### Chemistry 9701 · 0/" in text and "### Physics 9702" in text and "### Maths" in text
    assert text.index("### Chemistry 9701") < text.index("### Physics 9702") < text.index("### Maths")
    assert "| **1. Atomic structure (AS)** | | |" in text and "| **P1  Pure Mathematics 1** | | |" in text
    assert text.index("| 9701-1.2 Isotopes") < text.index("| 9701-1.10 Idea 10") < text.index("| **10. Group 17 (AS)**")
    assert text.count("| Subtopic | Progress | Notes |") == 3  # one table for each subject

