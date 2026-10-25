"""Normalise historical AI prose on consumption while keeping authored content literal."""
import asyncio
import json
from copy import deepcopy

import pytest

from fixtures import make_vault
from test_tui import app_for
from tutor_app.output_format import normalise_visual
from tutorlib import lesson, report, session, store


KC = "9702-2.1.1"
RAW = r"Use \(x^2\)."
CANONICAL = "Use $x^2$."
PROSE = ("motivate", "establish", "connect", "note", "self_explain")


def make_tutor(tmp_path, *, formatted=True):
    tutor = session.Tutor(store.Vault(make_vault(tmp_path)))
    if formatted:
        tutor.ai_visual = normalise_visual
    return tutor


@pytest.mark.parametrize("source", [None, "ai"])
def test_ai_teaching_cache_formats_prose_and_marks_legacy_provenance_without_rewriting_file(tmp_path, source):
    tutor = make_tutor(tmp_path)
    card = {field: RAW for field in PROSE}
    card.update(working=RAW, speech=RAW, options={"A": RAW}, discover={"stem": RAW, "answer": RAW})
    if source:
        card["source"] = source
    path = tutor.vault.tutor / "cache" / "teach" / f"{KC}.json"
    store.write_json(path, card)
    original = path.read_bytes()

    loaded = lesson.teach_card(tutor, KC)

    assert loaded["source"] == "ai"
    assert {field: loaded[field] for field in PROSE} == {field: CANONICAL for field in PROSE}
    assert loaded["working"] == loaded["speech"] == RAW
    assert loaded["options"] == {"A": RAW} and loaded["discover"] == {"stem": RAW, "answer": RAW}
    assert path.read_bytes() == original


def test_standalone_engine_default_preserves_cached_prose(tmp_path):
    tutor = make_tutor(tmp_path, formatted=False)
    store.write_json(tutor.vault.tutor / "cache" / "teach" / f"{KC}.json", {field: RAW for field in PROSE})
    loaded = lesson.teach_card(tutor, KC)
    assert {field: loaded[field] for field in PROSE} == {field: RAW for field in PROSE}
    assert loaded["source"] == "ai"


def test_tutor_accepts_optional_visual_callback_and_leaves_identity_default(tmp_path):
    vault = store.Vault(make_vault(tmp_path))
    default = session.Tutor(vault)
    configured = session.Tutor(vault, ai_visual=normalise_visual)
    assert default.ai_visual(RAW) == RAW
    assert configured.ai_visual(RAW) == CANONICAL


@pytest.mark.parametrize("phase", ["motivate", "establish", "fix", "own_words"])
def test_resumed_ai_node_normalises_a_copy_and_preserves_provenance_for_display(tmp_path, phase):
    tutor = make_tutor(tmp_path)
    source = {field: RAW for field in PROSE}
    source.update(source="ai", speech=RAW, expr=RAW)
    original = deepcopy(source)
    block = {"kind": "node", "kc": KC, "card": source, "phases": [phase], "i": 0}
    tutor.session = {"goal": "quick", "blocks": [block], "thread": []}

    act = tutor._step_node(block, 0)

    assert act["ai_source"] is True
    if phase == "own_words":
        assert act["prompt"] == CANONICAL
    else:
        assert act["text"] == (CANONICAL + "\n\n**How it connects:** " + CANONICAL
                               if phase == "establish" else CANONICAL)
    assert source == original and block["card"] is not source
    assert {field: block["card"][field] for field in PROSE} == {field: CANONICAL for field in PROSE}
    assert block["card"]["speech"] == block["card"]["expr"] == RAW


@pytest.mark.parametrize("source", ["pack", "offline"])
def test_authored_or_offline_resumed_nodes_use_original_prose_and_display(tmp_path, source):
    tutor = make_tutor(tmp_path)
    card = {"source": source, "establish": RAW}
    block = {"kind": "node", "kc": KC, "card": card, "phases": ["establish"], "i": 0}
    tutor.session = {"goal": "quick", "blocks": [block], "thread": []}
    act = tutor._step_node(block, 0)
    assert act["text"] == RAW and not act.get("ai_source")
    assert block["card"] is card


def test_authored_pack_card_is_not_passed_to_ai_normalisation(tmp_path):
    tutor = make_tutor(tmp_path)
    source = {field: RAW for field in PROSE}
    tutor.packs.pack_for_kc(KC).setdefault("teach", {})[KC] = source
    loaded = lesson.teach_card(tutor, KC)
    assert {field: loaded[field] for field in PROSE} == {field: RAW for field in PROSE}
    assert loaded["source"] == "pack"
    assert source == {field: RAW for field in PROSE}


def test_profile_cache_formats_only_text_on_read_and_profile_note_keeps_same_prose(tmp_path):
    tutor = make_tutor(tmp_path)
    cached = {"text": RAW, "at": "2026-10-25T12:00:00+08:00", "speech": RAW, "expr": RAW}
    path = tutor.vault.tutor / "profile_ai.json"
    store.write_json(path, cached)
    original = path.read_bytes()

    assert report.load_ai_summary(tutor) == {**cached, "text": CANONICAL}
    assert CANONICAL in (tutor.vault.root / report.profile_note(tutor)).read_text()
    assert path.read_bytes() == original


def test_standalone_profile_cache_keeps_legacy_text(tmp_path):
    tutor = make_tutor(tmp_path, formatted=False)
    cached = {"text": RAW, "at": "2026-10-25T12:00:00+08:00"}
    store.write_json(tutor.vault.tutor / "profile_ai.json", cached)
    assert report.load_ai_summary(tutor) == cached


def test_terminal_app_wires_visual_callback_for_cached_card_and_profile(tmp_path, monkeypatch):
    app, vault = app_for(tmp_path, monkeypatch)
    store.write_json(vault / ".tutor" / "cache" / "teach" / f"{KC}.json", {field: RAW for field in PROSE})
    store.write_json(vault / ".tutor" / "profile_ai.json", {"text": RAW, "at": "2026-10-25T12:00:00+08:00"})

    async def go():
        async with app.run_test() as pilot:
            await pilot.pause()
            assert lesson.teach_card(app.tutor, KC)["establish"] == CANONICAL
            assert report.load_ai_summary(app.tutor)["text"] == CANONICAL
            await app.ai.close()

    asyncio.run(go())
