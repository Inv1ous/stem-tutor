import random
import sqlite3
import zipfile
from datetime import datetime

from fixtures import make_vault
from tutorlib import anki, session, store

T0 = datetime.fromisoformat("2026-09-29T17:00:00+08:00")


def test_math_delimiters_converted_for_anki():
    assert anki.to_anki("Use $v=u+at$ then\n$$\ns=ut\n$$") == "Use \\(v=u+at\\) then<br>\\[<br>s=ut<br>\\]"


def test_currency_and_bold():
    assert anki.to_anki("costs \\$5, **key**") == "costs $5, <b>key</b>"


def _notes(path):
    with zipfile.ZipFile(path) as z:
        z.extract("collection.anki2", path.parent / "x")
    con = sqlite3.connect(path.parent / "x" / "collection.anki2")
    rows = con.execute("select guid, flds, tags from notes").fetchall()
    con.close()
    return rows


def test_export_only_introduced_kcs_and_only_once(tmp_path):
    t = session.Tutor(store.Vault(make_vault(tmp_path)), rng=random.Random(0), now=lambda: T0)
    assert anki.export(t)["cards"] == 0  # nothing introduced yet
    t.log({"type": "answer", "item": "x", "kcs": ["9702-2.1.1"], "subject": "phys", "difficulty": 3, "conf": 3,
           "hinted": False, "marks": 1, "grade": {"correct": True, "score": 1.0, "error": None, "misconception": None}})
    r = anki.export(t)
    assert r["cards"] == 1 and r["path"].endswith(".apkg")
    rows = _notes(t.vault.root / r["path"])
    assert len(rows) == 1 and "\\(\\vec s\\)" in rows[0][1] and "stem-tutor" in rows[0][2]
    assert anki.export(t)["cards"] == 0
    assert rows[0][0] == anki.guid("9702-2.1:fc1")


def test_second_export_in_the_same_minute_keeps_the_first(tmp_path):  # B-013
    t = session.Tutor(store.Vault(make_vault(tmp_path)), rng=random.Random(0), now=lambda: T0)
    first = t.vault.root / "Anki" / f"STEM Tutor {T0:%Y-%m-%d %H%M}.apkg"
    first.parent.mkdir(parents=True)
    first.write_bytes(b"FIRST BATCH")  # an earlier export this minute
    t.log({"type": "answer", "item": "x", "kcs": ["9702-2.1.1"], "subject": "phys", "difficulty": 3, "conf": 3,
           "hinted": False, "marks": 1, "grade": {"correct": True, "score": 1.0, "error": None, "misconception": None}})
    r = anki.export(t)
    assert r["cards"] == 1 and r["path"] != f"Anki/{first.name}" and first.read_bytes() == b"FIRST BATCH"
    assert len(_notes(t.vault.root / r["path"])) == 1


def test_same_card_id_in_two_packs_exports_both(tmp_path):  # B-028
    import json
    from fixtures import GRAPH, PACK
    root = make_vault(tmp_path)
    spec = root / ".tutor" / "packs" / "v1" / "specs" / "9702"
    graph = json.loads(json.dumps(GRAPH))
    graph["subtopics"].append({"id": "9702-2.2", "title": "Forces", "topic": "9702-2"})
    graph["kcs"].append({**graph["kcs"][0], "id": "9702-2.2.1", "subtopic": "9702-2.2", "prereqs": []})
    (spec / "graph.json").write_text(json.dumps(graph))
    pack = {**PACK, "subtopic": "9702-2.2", "items": [], "worked": [], "misconceptions": [],
            "note": "Subjects/9702 Physics/02 Kinematics/2.2 Forces.md",
            "flashcards": [{"id": "fc1", "kc": "9702-2.2.1", "front": "What is a force?", "back": "A push or pull."}]}
    (spec / "packs" / "9702-2.2.json").write_text(json.dumps(pack))
    t = session.Tutor(store.Vault(root), rng=random.Random(0), now=lambda: T0)
    guids = []
    for kc in ("9702-2.1.1", "9702-2.2.1"):
        t.log({"type": "answer", "item": "x", "kcs": [kc], "subject": "phys", "difficulty": 3, "conf": 3, "hinted": False,
               "marks": 1, "grade": {"correct": True, "score": 1.0, "error": None, "misconception": None}})
        r = anki.export(t)
        assert r["cards"] == 1, kc
        guids += [g for g, _f, _t in _notes(t.vault.root / r["path"])]
    assert len(set(guids)) == 2


def test_inequalities_and_arrows_survive_as_html():  # B-029
    from html.parser import HTMLParser

    class Text(HTMLParser):
        def __init__(self):
            super().__init__()
            self.text = ""

        def handle_data(self, data):
            self.text += data

    for md, want in [("How do you interpret $px^2+qx+r<ax+b$ graphically?", "\\(px^2+qx+r<ax+b\\)"),
                     ("$\\ce{X(g) -> X+(g) + e-}$ & **more**", "\\(\\ce{X(g) -> X+(g) + e-}\\) & more")]:
        p = Text()
        p.feed(anki.to_anki(md))
        p.close()
        assert want in p.text, p.text
