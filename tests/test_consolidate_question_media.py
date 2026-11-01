"""Media storage changes preserve exact identities and bytes in disposable vaults."""
import hashlib
import json
from pathlib import Path
import sys

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'build'))
import consolidate_question_media as media
from tutorlib.asset_library import AssetLibrary, write_asset


def seed(tmp_path):
    vault = tmp_path / 'STEM Tutor'
    vault.mkdir()
    old = 'Library/Courses/9702/Questions/Media/mcq/9702/plot.png'
    second = 'Library/Courses/9702/Questions/Media/topicals/plot.png'
    first_id = write_asset(vault, old, b'first', aliases=['Assets/mcq/plot.png'],
                           metadata={'course': '9702', 'provenance': {'page': 3}})
    second_id = write_asset(vault, second, b'second', aliases=['Assets/topicals/plot.png'])
    return vault, old, second, first_id, second_id


def test_plan_is_readonly_and_collision_safe(tmp_path):
    vault, old, second, _, _ = seed(tmp_path)
    before = (vault / 'Library/catalog.json').read_bytes()
    report = media.plan(vault)
    assert report['errors'] == [] and len(report['moves']) == 2
    assert len({m['to'] for m in report['moves']}) == 2
    assert all(len(Path(m['to']).parts) == 6 for m in report['moves'])
    assert (vault / 'Library/catalog.json').read_bytes() == before
    assert (vault / old).exists() and (vault / second).exists()


def test_apply_keeps_ids_provenance_aliases_and_history(tmp_path):
    vault, old, second, first_id, second_id = seed(tmp_path)
    history = vault / '.tutor/events.jsonl'
    history.parent.mkdir(); history.write_bytes(b'{"image":"' + old.encode() + b'"}\n')
    before_history = history.read_bytes()
    journal = tmp_path / 'Archive/media.json'
    result = media.apply(media.plan(vault), journal)
    reader = AssetLibrary(vault)
    assert result['status'] == 'complete'
    for reference in (old, first_id, 'Assets/mcq/plot.png'):
        assert reader.read(reference) == b'first'
    assert reader.read(second_id) == reader.read(second) == b'second'
    assert reader.record(first_id)['provenance'] == {'page': 3}
    assert history.read_bytes() == before_history
    assert not (vault / old).exists() and not (vault / second).exists()
    assert media.plan(vault)['moves'] == []
    assert media.apply(media.plan(vault), journal)['status'] == 'complete'


def test_rollback_restores_exact_catalog_and_paths(tmp_path):
    vault, old, second, _, _ = seed(tmp_path)
    original = (vault / 'Library/catalog.json').read_bytes()
    journal = tmp_path / 'Archive/media.json'
    media.apply(media.plan(vault), journal)
    media.rollback(journal)
    assert (vault / 'Library/catalog.json').read_bytes() == original
    assert (vault / old).read_bytes() == b'first'
    assert (vault / second).read_bytes() == b'second'


def test_stale_plan_and_corrupt_assets_fail_before_switch(tmp_path):
    vault, old, _, _, _ = seed(tmp_path)
    report = media.plan(vault)
    (vault / old).write_bytes(b'changed')
    with pytest.raises(ValueError, match='digest|changed'):
        media.apply(report, tmp_path / 'Archive/media.json')
    assert AssetLibrary(vault).record(old)['path'] == old


def test_restart_after_catalog_switch_completes_cleanup(tmp_path, monkeypatch):
    vault, old, _, first_id, _ = seed(tmp_path)
    journal = tmp_path / 'Archive/media.json'
    real_cleanup = media._cleanup
    monkeypatch.setattr(media, '_cleanup', lambda *args: (_ for _ in ()).throw(RuntimeError('interrupted')))
    report = media.plan(vault)
    with pytest.raises(RuntimeError, match='interrupted'):
        media.apply(report, journal)
    assert AssetLibrary(vault).read(first_id) == b'first'
    monkeypatch.setattr(media, '_cleanup', real_cleanup)
    assert media.apply(report, journal)['status'] == 'complete'
    assert not (vault / old).exists()


def test_symlink_destination_is_rejected(tmp_path):
    vault, _, _, _, _ = seed(tmp_path)
    report = media.plan(vault)
    outside = tmp_path / 'outside'; outside.write_bytes(b'first')
    target = vault / report['moves'][0]['to']; target.symlink_to(outside)
    with pytest.raises(ValueError, match='symlink|unsafe|exists'):
        media.apply(report, tmp_path / 'Archive/media.json')
    assert outside.read_bytes() == b'first'


def test_restart_in_catalog_switch_window_uses_saved_plan(tmp_path, monkeypatch):
    vault, old, _, _, _ = seed(tmp_path)
    journal = tmp_path / 'Archive/media.json'
    original_json = media._json
    def interrupt(path, data):
        if data.get('status') == 'committed':
            raise RuntimeError('switch interrupted')
        original_json(path, data)
    monkeypatch.setattr(media, '_json', interrupt)
    with pytest.raises(RuntimeError, match='switch interrupted'):
        media.apply(media.plan(vault), journal)
    monkeypatch.setattr(media, '_json', original_json)
    assert media.apply(media.plan(vault), journal)['status'] == 'complete'
    assert not (vault / old).exists()


def test_rollback_refuses_concurrent_catalog_work(tmp_path):
    vault, _, _, _, _ = seed(tmp_path)
    journal = tmp_path / 'Archive/media.json'
    media.apply(media.plan(vault), journal)
    write_asset(vault, 'Library/Courses/P1/Diagrams/new.svg', b'new')
    with pytest.raises(ValueError, match='discard other work'):
        media.rollback(journal)
    assert AssetLibrary(vault).read('Library/Courses/P1/Diagrams/new.svg') == b'new'


def test_rollback_restarts_after_restoring_catalog(tmp_path, monkeypatch):
    vault, old, _, first_id, _ = seed(tmp_path)
    journal = tmp_path / 'Archive/media.json'
    report = media.plan(vault); media.apply(report, journal)
    real_unlink = media.os.unlink
    target = Path(report['moves'][0]['to']).name
    def interrupted(name, *args, **kwargs):
        if name == target:
            raise RuntimeError('rollback cleanup interrupted')
        return real_unlink(name, *args, **kwargs)
    monkeypatch.setattr(media.os, 'unlink', interrupted)
    with pytest.raises(RuntimeError, match='rollback cleanup interrupted'):
        media.rollback(journal)
    monkeypatch.setattr(media.os, 'unlink', real_unlink)
    assert media.rollback(journal)['status'] == 'rolled_back'
    assert AssetLibrary(vault).read(first_id) == b'first'
    assert AssetLibrary(vault).record(first_id)['path'] == old
