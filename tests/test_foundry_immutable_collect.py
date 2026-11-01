"""Legacy collectors must never mutate immutable Library file adapters."""
import json

import pytest
from test_foundry import fdy, SUB, CARD, add_legacy_state


@pytest.mark.parametrize('adapter', [False, True])
@pytest.mark.parametrize('entry', ['merge', 'collect'])
def test_foundry_merge_and_collect_refuse_library_pack_before_any_content_write(fdy, tmp_path, monkeypatch, adapter, entry):
    original = fdy.pack_path(SUB)
    target = tmp_path / 'vault/Library/Courses/9702/pack.json'
    target.parent.mkdir(parents=True)
    target.write_bytes(original.read_bytes())
    path = target
    if adapter:
        path = tmp_path / 'pack-adapter.json'
        path.symlink_to(target)
    monkeypatch.setattr(fdy, 'pack_path', lambda sub: path)
    draft = fdy.ROOT / 'build/work/teach' / f'{SUB}.json'
    draft.parent.mkdir(parents=True, exist_ok=True)
    draft.write_text(json.dumps({f'{SUB}.1': {**CARD, 'note': 'A proposed edit'}}))
    before = target.read_bytes()
    if entry == 'merge':
        with pytest.raises(ValueError, match='Library|immutable'):
            fdy.merge_teach(SUB)
    else:
        add_legacy_state(fdy, [SUB])
        calls = []
        monkeypatch.setattr(fdy, 'restore_extras', lambda *a: calls.append('restore') or {})
        fdy.cmd_collect('drafter', SUB, '-')
        assert calls == []
        assert fdy.load(SUB)['gates']['ok'] is False
        assert 'immutable' in fdy.load(SUB)['gates']['first'][0].lower()
    assert target.read_bytes() == before


@pytest.mark.parametrize('adapter', [False, True])
def test_collector_refuses_library_note_before_restoring_pack(fdy, tmp_path, monkeypatch, adapter):
    pack = json.loads(fdy.pack_path(SUB).read_text())
    source = fdy.note_path(pack, SUB)
    target = tmp_path / 'vault/Library/Courses/9702/note.md'
    target.parent.mkdir(parents=True)
    target.write_bytes(source.read_bytes())
    path = target
    if adapter:
        path = tmp_path / 'note-adapter.md'
        path.symlink_to(target)
    monkeypatch.setattr(fdy, 'note_path', lambda *a: path)
    add_legacy_state(fdy, [SUB])
    before_pack, before_note = fdy.pack_path(SUB).read_bytes(), target.read_bytes()
    calls = []
    monkeypatch.setattr(fdy, 'restore_extras', lambda *a: calls.append('restore') or {})
    fdy.cmd_collect('drafter', SUB, '-')
    assert calls == []
    assert fdy.load(SUB)['gates']['ok'] is False
    assert fdy.pack_path(SUB).read_bytes() == before_pack
    assert target.read_bytes() == before_note


def test_failed_worker_does_not_trigger_mutating_glyph_settlement(fdy, monkeypatch):
    add_legacy_state(fdy, [SUB])
    with fdy.chapter(SUB) as st:
        st['jobs']['drafter'] = {'started': fdy.now(), 'provider': 'codex'}
    calls = []
    monkeypatch.setattr(fdy, 'settle_glyphs', lambda *a, **kw: calls.append('glyphs') or ({'ok': True}, 0))
    fdy.cmd_collect('drafter', SUB, '-', '1')
    assert calls == []
    assert fdy.load(SUB)['jobs']['drafter']['ok'] is False
