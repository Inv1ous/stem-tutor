import sys
from pathlib import Path

import pytest

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


def test_default_load_reads_verified_library_notes_base_before_research(tmp_path, monkeypatch):
    from tutorlib.asset_library import write_asset
    vault = tmp_path / 'STEM Tutor'
    vault.mkdir()
    research = '- **Shared method** `8/10`. research version\n<!-- spec: P2 -->\n- **Extra method** `9/10`. extra'
    base = '- **Shared method** `10/10`. base version'
    # Register research first: catalog insertion order must not change priority.
    write_asset(vault, 'Library/Shared/Sources/Shortcuts/research/pure.md', research.encode(),
                aliases=['sources/shortcuts/research/pure.md'])
    write_asset(vault, 'Library/Courses/pure/Sources/Shortcuts/base/pure.md', base.encode(),
                aliases=['sources/shortcuts/base/pure.md'])
    monkeypatch.setenv('STEM_TUTOR_VAULT', str(vault))
    result = sc.load()
    assert [entry['id'] for entry in result] == ['SEM-pure-shared-method', 'SEM-P2-extra-method']
    assert result[0]['body'] == 'base version' and result[0]['origin'] == 'base'
    assert [entry['spec'] for entry in sc.load('P2')] == ['P2']
    target = vault / 'Library/Courses/pure/Sources/Shortcuts/base/pure.md'
    target.write_text('tampered')
    with pytest.raises(ValueError, match='digest mismatch'):
        sc.load()


def test_explicit_source_path_remains_isolated_parser_fixture(tmp_path):
    source = tmp_path / 'parser-fixture'
    (source / 'base').mkdir(parents=True)
    (source / 'base/P1.md').write_text('- **Method** `9/10`. fixture content')
    assert sc.load(sources=source)[0]['id'] == 'SEM-P1-method'
    assert not (tmp_path / 'Library').exists()


def test_default_load_never_falls_back_to_repository_source_notes(tmp_path, monkeypatch):
    vault = tmp_path / 'STEM Tutor'
    vault.mkdir()
    old = tmp_path / 'code/sources/shortcuts/base'
    old.mkdir(parents=True)
    (old / 'P1.md').write_text('- **Old source** `9/10`. should not load')
    monkeypatch.setattr(sc, 'REPO', tmp_path / 'code')
    monkeypatch.setenv('STEM_TUTOR_VAULT', str(vault))
    with pytest.raises(ValueError):
        sc.load()
