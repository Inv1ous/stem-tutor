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
    assert rows[0][0] == anki.guid("fc1")
