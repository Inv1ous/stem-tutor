"""Anki content updates include corrected knowledge-component context."""
import hashlib
import json
from datetime import datetime

from fixtures import make_vault
from test_anki import _notes
from tutorlib import anki, session, store


def test_kc_correction_reexports_same_flashcard_with_current_context(tmp_path):
    root = make_vault(tmp_path)
    now = lambda: datetime.fromisoformat("2026-09-29T17:00:00+08:00")
    tutor = session.Tutor(store.Vault(root), now=now)
    tutor.log({"type": "answer", "item": "introduced-context", "kcs": ["9702-2.1.1", "9702-2.1.4"],
               "subject": "phys", "difficulty": 3, "conf": 3, "hinted": False, "marks": 1,
               "grade": {"correct": True, "score": 1.0, "error": None, "misconception": None}})
    first = anki.export(tutor)
    assert first["cards"] == 1 and anki.export(tutor)["cards"] == 0
    package = root / first["path"]
    original_package = package.read_bytes()
    (old_note,) = _notes(package)
    assert old_note[1].split("\x1f")[2] == "9702-2.1.1"
    events = {p: p.read_bytes() for p in (root / ".tutor/events").glob("*.jsonl")}
    # The disposable fixture's next content revision corrects only the KC association.
    path = root / ".tutor/packs/v1/specs/9702/packs/9702-2.1.json"
    pack = json.loads(path.read_text())
    pack["flashcards"][0]["kc"] = "9702-2.1.4"
    path.write_text(json.dumps(pack))
    tutor = session.Tutor(store.Vault(root), now=now)

    corrected = anki.export(tutor)

    assert corrected["cards"] == 1 and corrected["updated"] == 1
    (new_note,) = _notes(root / corrected["path"])
    assert new_note[0] == old_note[0] == anki.guid("9702-2.1:fc1")
    assert new_note[1].split("\x1f")[:2] == old_note[1].split("\x1f")[:2]
    assert new_note[1].split("\x1f")[2] == "9702-2.1.4"
    assert "9702-2_1_4" in new_note[2] and "9702-2_1_1" not in new_note[2]
    assert package.read_bytes() == original_package
    assert all(p.read_bytes().startswith(content) for p, content in events.items())
    assert anki.export(tutor)["cards"] == 0


def test_older_wording_only_fingerprint_refreshes_once_with_stable_identity(tmp_path):
    root = make_vault(tmp_path)
    tutor = session.Tutor(store.Vault(root))
    tutor.log({"type": "answer", "item": "introduced-context", "kcs": ["9702-2.1.1"],
               "subject": "phys", "difficulty": 3, "conf": 3, "hinted": False, "marks": 1,
               "grade": {"correct": True, "score": 1.0, "error": None, "misconception": None}})
    card = tutor.packs.pack("9702-2.1")["flashcards"][0]
    uid = "9702-2.1:fc1"
    old_hash = hashlib.sha1("\x1f".join(str(card.get(k, "")) for k in ("front", "back", "source")).encode()).hexdigest()[:12]
    tutor.log({"type": "anki_export", "cards": [uid], "path": "Anki/earlier.apkg", "hashes": {uid: old_hash}})
    history = {p: p.read_bytes() for p in (root / ".tutor/events").glob("*.jsonl")}

    refreshed = anki.export(tutor)

    assert refreshed["cards"] == 1 and refreshed["updated"] == 1
    (note,) = _notes(root / refreshed["path"])
    assert note[0] == anki.guid(uid)
    assert tutor.state["anki_exported"] == [uid]
    assert all(p.read_bytes().startswith(content) for p, content in history.items())
    assert anki.export(session.Tutor(store.Vault(root)))["cards"] == 0
