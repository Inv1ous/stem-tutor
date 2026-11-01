"""Valid Obsidian fold controls must not discard earlier authored note content."""
from datetime import datetime

import pytest

from fixtures import make_vault
from tutorlib import session, store, views


@pytest.mark.parametrize("fold", ["", "-", "+"])
@pytest.mark.parametrize("new_words", [None, "My latest explanation."])
def test_reteaching_keeps_words_and_mistakes_after_callout_fold_edit(tmp_path, fold, new_words):
    tutor = session.Tutor(store.Vault(make_vault(tmp_path)),
                          now=lambda: datetime.fromisoformat("2026-09-29T17:00:00+08:00"))
    tutor.start("lesson", focus=["9702-2.1"])
    first = {"kc": "9702-2.1.1", "card": {"note": "Tutor note."},
             "own_words": "My older authored explanation.\n\nMy second paragraph.",
             "mistakes": ["My earlier error."]}
    tutor._node_done(first)
    note = tutor.vault.root / views.notes_rel(tutor.packs, "9702-2.1")
    # A normal external Obsidian edit makes these generated callouts foldable.
    text = note.read_text().replace("> [!quote] In your words", f"> [!quote]{fold} In your words")
    text = text.replace("> [!warning] Watch out", f"> [!warning]{fold} Watch out")
    outside = "\n## My additional working\nKeep this learner-authored paragraph.\n"
    note.write_text(text + outside)
    historical = {p: p.read_bytes() for p in (tutor.vault.tutor / "events").glob("*.jsonl")}

    tutor._node_done({**first, "card": {"note": "Revised tutor note."}, "own_words": new_words,
                      "mistakes": ["My latest error."]})

    updated = note.read_text()
    assert "My older authored explanation." in updated
    assert "My second paragraph." in updated
    assert "My earlier error." in updated and "My latest error." in updated
    assert outside in updated
    assert new_words is None or new_words in updated
    assert all(p.read_bytes().startswith(content) for p, content in historical.items())
