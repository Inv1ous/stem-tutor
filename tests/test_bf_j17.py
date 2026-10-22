from __future__ import annotations

from pathlib import Path

import pytest

from fixtures import make_vault
from tutorlib import packs as packs_mod, store, views

SUB = "9702-2.1"
KC = "9702-2.1.1"


@pytest.fixture
def vault_packs(tmp_path):
    vault = store.Vault(make_vault(tmp_path))
    return vault, packs_mod.Packs(vault)


def test_reteaching_with_new_own_words_keeps_the_earlier_insight(vault_packs):
    """B-077 (bug watch): a second nonempty own_words must not erase the first from My Notes."""
    vault, packs = vault_packs
    state = {"kcs": {}, "gaps": []}
    views.notes_update(vault.root, packs, state, SUB,
                        node={"kc": KC, "note": "n", "own_words": "My first insight: displacement has direction."})
    views.notes_update(vault.root, packs, state, SUB,
                        node={"kc": KC, "note": "n", "own_words": "My second insight: slope gives velocity."})
    text = (vault.root / views.notes_rel(packs, SUB)).read_text(encoding="utf-8")
    assert "My first insight" in text
    assert "My second insight" in text


def test_a_concurrent_editor_save_survives_a_notes_refresh(vault_packs, monkeypatch):
    """B-092 (bug watch): a save outside the managed markers during notes_update must not be erased."""
    vault, packs = vault_packs
    state = {"kcs": {}, "gaps": []}
    rel = views.notes_update(vault.root, packs, state, SUB, node={"kc": KC, "note": "n"})
    note = vault.root / rel

    landed = []

    real_read_text = Path.read_text

    def read_then_race(path, *a, **kw):
        text = real_read_text(path, *a, **kw)
        if path == note and not landed:
            landed.append(True)
            with open(note, "a", encoding="utf-8") as f:
                f.write("\n## My latest working\nVelocity is displacement divided by time.\n")
        return text

    monkeypatch.setattr(Path, "read_text", read_then_race)

    views.notes_update(vault.root, packs, state, SUB, node={"kc": KC, "note": "n (reviewed)"})

    final = note.read_text(encoding="utf-8")
    assert "Velocity is displacement divided by time." in final
