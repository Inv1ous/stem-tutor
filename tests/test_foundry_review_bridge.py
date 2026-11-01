"""Proof handoff only: worker dispatch remains a separate controller responsibility."""
import json
import pytest
from test_refine import rf, SUB
from test_refine_written_pipeline import reviewed


def test_handoff_archives_exact_proof_without_changing_refine_state(rf, tmp_path):
    from tutor_workers.written_handoff import freeze_source, import_proof
    pack, state, ident = reviewed(rf)
    rf._ingest_written(state, pack)
    source = rf.pack_path(SUB)
    items = rf.written_items(pack)
    binding = freeze_source([source], items)
    records = json.loads(rf._written_file(SUB, 'review').read_text())
    original = (rf.STATE / f'{SUB}.json').read_bytes()
    target = rf.WORK / 'handoff' / 'review.json'
    result = import_proof(binding=binding, source_paths=[source], items=items,
                          records=records, source_root=rf.ROOT, source_work=rf.WORK,
                          source_blind=rf.BLIND, target=target, expected_target=None,
                          root=rf.ROOT, work=rf.WORK, blind=rf.BLIND)
    assert rf._written_record_problems(items, result) == []
    assert result[ident]['solver'] == records[ident]['solver']
    assert result[ident]['evidence']['files'] != records[ident]['evidence']['files']
    assert (rf.STATE / f'{SUB}.json').read_bytes() == original
    assert json.loads(target.read_text()) == result


def test_changed_source_refuses_handoff_before_any_output(rf):
    from tutor_workers.written_handoff import freeze_source, import_proof
    pack, state, ident = reviewed(rf)
    rf._ingest_written(state, pack)
    source = rf.pack_path(SUB)
    items = rf.written_items(pack)
    binding = freeze_source([source], items)
    source.write_text(source.read_text() + ' ')
    target = rf.WORK / 'handoff' / 'review.json'
    with pytest.raises(ValueError, match='source changed'):
        import_proof(binding=binding, source_paths=[source], items=items,
                     records=json.loads(rf._written_file(SUB, 'review').read_text()),
                     source_root=rf.ROOT, source_work=rf.WORK, source_blind=rf.BLIND,
                     target=target, expected_target=None, root=rf.ROOT, work=rf.WORK, blind=rf.BLIND)
    assert not target.exists()


@pytest.mark.parametrize('change', ['inventory', 'proof', 'target'])
def test_handoff_rejects_stale_inventory_tampered_proof_and_concurrent_merge(rf, change):
    from tutor_workers.written_handoff import freeze_source, import_proof
    pack, state, ident = reviewed(rf)
    rf._ingest_written(state, pack)
    source = rf.pack_path(SUB)
    items = rf.written_items(pack)
    binding = freeze_source([source], items)
    records = json.loads(rf._written_file(SUB, 'review').read_text())
    target = rf.WORK / 'handoff' / 'review.json'
    if change == 'inventory':
        items[0]['stem'] += ' changed image hash'
    elif change == 'proof':
        (rf.ROOT / records[ident]['evidence']['files']['answers']['path']).write_text('{}')
    else:
        target.parent.mkdir(parents=True)
        target.write_text('{"prior": {}}')
    prior = target.read_bytes() if target.exists() else None
    with pytest.raises(ValueError):
        import_proof(binding=binding, source_paths=[source], items=items, records=records,
                     source_root=rf.ROOT, source_work=rf.WORK, source_blind=rf.BLIND,
                     target=target, expected_target=None, root=rf.ROOT, work=rf.WORK, blind=rf.BLIND)
    assert (target.read_bytes() if target.exists() else None) == prior


@pytest.mark.parametrize('attack', ['lock', 'target', 'parent', 'extra'])
def test_handoff_rejects_symlinks_and_unvalidated_extra_records(rf, tmp_path, attack):
    from tutor_workers.written_handoff import freeze_source, import_proof
    pack, state, ident = reviewed(rf)
    rf._ingest_written(state, pack)
    source = rf.pack_path(SUB)
    items = rf.written_items(pack)
    binding = freeze_source([source], items)
    records = json.loads(rf._written_file(SUB, 'review').read_text())
    target = rf.WORK / 'handoff' / 'review.json'
    external = tmp_path / 'outside'
    external.mkdir()
    if attack == 'parent':
        target.parent.symlink_to(external, target_is_directory=True)
    else:
        target.parent.mkdir()
    if attack == 'lock':
        target.with_suffix('.json.lock').symlink_to(external / 'victim')
    elif attack == 'target':
        target.symlink_to(external / 'victim')
    elif attack == 'extra':
        records['unvalidated-extra'] = {'evidence': {'files': {'bad': {'path': '../outside', 'sha256': 'fake'}}}}
    with pytest.raises((ValueError, OSError)):
        import_proof(binding=binding, source_paths=[source], items=items, records=records,
                     source_root=rf.ROOT, source_work=rf.WORK, source_blind=rf.BLIND,
                     target=target, expected_target=None, root=rf.ROOT, work=rf.WORK, blind=rf.BLIND)
    assert list(external.iterdir()) == []
    if attack == 'extra':
        assert list(target.parent.iterdir()) == []


@pytest.mark.parametrize('catalog_health', ['valid', 'missing', 'damaged'])
def test_public_handoff_never_mutates_physical_library_through_case_alias(rf, catalog_health):
    from tutor_workers.written_handoff import freeze_source, import_proof
    from tutorlib.asset_library import write_asset
    pack, state, ident = reviewed(rf)
    rf._ingest_written(state, pack)
    source = rf.pack_path(SUB)
    items = rf.written_items(pack)
    binding = freeze_source([source], items)
    records = json.loads(rf._written_file(SUB, 'review').read_text())
    relative = 'Library/Shared/Evidence/review.json'
    write_asset(rf.ROOT, relative, b'{}')
    catalog = rf.ROOT / 'Library/catalog.json'
    if catalog_health == 'missing':
        catalog.unlink()
    elif catalog_health == 'damaged':
        catalog.write_text('{"invalid":true}')
    original_state = (rf.STATE / f'{SUB}.json').read_bytes()
    before = {path.relative_to(rf.ROOT): path.read_bytes()
              for path in (rf.ROOT / 'Library').rglob('*') if path.is_file()}
    target = rf.ROOT / 'library/Shared/Evidence/review.json'
    same_library = target.exists()
    if not same_library:
        target.parent.mkdir(parents=True)

    def handoff():
        return import_proof(binding=binding, source_paths=[source], items=items, records=records,
                            source_root=rf.ROOT, source_work=rf.WORK, source_blind=rf.BLIND,
                            target=target, expected_target=b'{}' if same_library else None,
                            root=rf.ROOT, work=target.parent, blind=rf.BLIND)

    if same_library:
        with pytest.raises(ValueError, match='evidence directory'):
            handoff()
    else:
        assert ident in handoff()  # a physically distinct lowercase working directory remains writable
    assert {path.relative_to(rf.ROOT): path.read_bytes()
            for path in (rf.ROOT / 'Library').rglob('*') if path.is_file()} == before
    assert (rf.STATE / f'{SUB}.json').read_bytes() == original_state
