import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "build"))
import shortcuts as sc  # noqa: E402

NOTE = """---
title: x
---
# Heading

## Ranked index
| a | b |
**Not an entry** `9/10`. skipped

## 1. Kinematics
### suvat
- **Pick the suvat** `10/10`. Choose the equation
  without the unknown.
  | case | use |
  |---|---|
  | no t | v2 |
**Energy first.** `9/10` Use $mgh$ before forces. [src: Tom]
- **Energy first** `8/10`. Second one with the same title.
- **No score here** just prose
continues here.

## 7. A Level: circular motion
**Centripetal** `7/10` body
"""


def test_parse_layouts_tables_src_duplicates_and_skips():
    es = sc.parse_note(NOTE, "9702")
    assert [e["title"] for e in es] == ["Pick the suvat", "Energy first", "Energy first", "Centripetal"]
    a, b, c, d = es
    assert a["id"] == "SEM-9702-pick-the-suvat" and a["score"] == 10 and a["topic"] == "suvat"
    assert a["section"] == "1. Kinematics" and a["origin"] == "base"
    assert a["body"].startswith("Choose the equation\n  without") and "| no t | v2 |" in a["body"]
    assert b["source"] == "Tom" and b["body"] == "Use $mgh$ before forces." and "[src" not in b["body"]
    assert c["id"] == b["id"] + "-2" and c["score"] == 8
    assert "continues here" in c["body"]  # a line that is no entry continues the last one
    assert d["section"].startswith("7. A Level") and sc.level_of(d) == "A" and sc.level_of(a) == "AS"


def test_select_is_the_engine_one():
    from tutorlib import shortcuts
    assert sc.select is shortcuts.select and sc.level_of is shortcuts.level_of
    es = sc.parse_note(NOTE, "9702")
    assert [e["score"] for e in sc.select(es, {"min_score": 9})] == [10, 9]


def test_a_spec_marker_switches_the_spec_for_the_entries_after_it():
    import sys
    from pathlib import Path
    sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "build"))
    import shortcuts
    text = "<!-- spec: P1 -->\n## 1. A\n- **One.** `9/10` text\n<!-- spec: P2 -->\n## 1. B\n- **Two.** `8/10` more\n"
    got = shortcuts.parse_note(text, "pure", "research")
    assert [(e["spec"], e["title"]) for e in got] == [("P1", "One"), ("P2", "Two")]
