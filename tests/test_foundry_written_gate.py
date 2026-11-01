"""Foundry signing requires the same exact independent written proof as Refine."""
import json

import pytest
from test_foundry import fdy, SUB, add_legacy_state
from test_refine import rf
from test_refine_written_pipeline import reviewed


def written_form():
    return {'name': 'Reason', 'wordings': ['Explain'], 'example': 'Different example',
            'check': 'Explain this result.', 'answer': 'A sound reason.',
            'rubric': [{'point': 'Reason', 'keywords': [['reason']]}],
            'retry': {'check': 'Explain a different result.', 'answer': 'Another reason.',
                      'rubric': [{'point': 'Reason', 'keywords': [['reason']]}]}}


def test_foundry_inventory_requires_guided_checks_and_retries(fdy):
    pack = {'teach': {SUB + '.1': {'forms': [written_form()]}}}
    issues = fdy.written_review_problems(SUB, pack)
    assert issues and '2' in issues[0]


def test_foundry_rejects_content_only_guided_approval(fdy):
    from build.written_review import review_items, build_records
    pack = {'teach': {SUB + '.1': {'forms': [written_form()]}}}
    items = review_items(pack['teach'])
    records = build_records(items, {x['id']: 'Independent reason' for x in items},
                            {x['id']: {'verdict': 'accepted', 'rationale': 'Valid'} for x in items},
                            solver='solver', reviewer='reviewer')
    path = fdy.ROOT / 'build/work/refine' / f'{SUB}.written-review.json'
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(records))
    assert any('durable independent worker evidence' in issue for issue in fdy.written_review_problems(SUB, pack))


def test_foundry_sign_cannot_publish_unreviewed_guided_check(fdy, monkeypatch):
    path = fdy.pack_path(SUB)
    pack = json.loads(path.read_text())
    pack['teach'][SUB + '.1']['forms'] = [written_form()]
    path.write_text(json.dumps(pack))
    add_legacy_state(fdy, [SUB])
    with fdy.chapter(SUB) as state:
        state['stage'] = 'sign'
    calls = []
    monkeypatch.setattr(fdy, 'publish_candidate', lambda *a: calls.append(a))
    with pytest.raises(SystemExit, match='not ready'):
        fdy.cmd_sign(SUB)
    assert calls == [] and fdy.load(SUB)['stage'] == 'sign'
    assert any('written' in x for x in fdy.load(SUB)['gates']['first'])


def test_foundry_accepts_refine_durable_proof_and_rejects_changed_content(rf):
    pack, state, ident = reviewed(rf)
    rf._ingest_written(state, pack)
    fdy = rf.fd
    assert fdy.written_review_problems(SUB, pack) == []
    pack['teach'][SUB + '.1']['forms'][0]['check'] = 'Changed after independent review'
    assert fdy.written_review_problems(SUB, pack)


def test_foundry_review_inventory_uses_one_fresh_catalog_per_gate_and_detects_tamper(fdy, tmp_path, monkeypatch):
    from tutorlib.asset_library import AssetLibrary, write_asset
    vault = tmp_path / 'synthetic-vault'
    vault.mkdir()
    one, two = 'Library/one.svg', 'Library/two.svg'
    alias = 'Assets/one.svg'
    write_asset(vault, one, b'<svg>one</svg>', aliases=[alias])
    write_asset(vault, two, b'<svg>two</svg>')
    form = written_form()
    form['diagram'] = alias
    pack = {'teach': {SUB + '.1': {'forms': [form], 'diagrams': [alias, two]}}}
    catalogs = []
    def catalog(_):
        catalogs.append(True)
        return AssetLibrary(vault)
    monkeypatch.setattr(fdy, '_diagram_catalog', catalog)
    import written_review
    extracted = []
    def inspect(items, records, **kwargs):
        extracted.append(items)
        return []
    monkeypatch.setattr(written_review, 'independent_record_problems', inspect)
    path = fdy.LOCATIONS.work('refine') / f'{SUB}.written-review.json'
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text('{}')
    fdy.written_review_problems(SUB, pack)
    assert len(catalogs) == 1
    before = extracted[-1][0]
    data_path = vault / 'Library/catalog.json'
    data = json.loads(data_path.read_text())
    for entry in data['assets'].values():
        entry['aliases'] = [alias] if entry['path'] == two else []
    data_path.write_text(json.dumps(data))
    fdy.written_review_problems(SUB, pack)
    assert len(catalogs) == 2
    assert extracted[-1][0] != before
    (vault / two).write_bytes(b'tampered')
    fdy.written_review_problems(SUB, pack)
    assert len(catalogs) == 3
    assert 'unresolved: ValueError' in json.dumps(extracted[-1])


def test_authoring_collection_defers_absent_written_records_but_sign_stays_strict(fdy):
    path = fdy.pack_path(SUB)
    pack = json.loads(path.read_text())
    pack['teach'][SUB + '.1']['forms'] = [written_form()]
    path.write_text(json.dumps(pack))
    add_legacy_state(fdy, [SUB])
    with fdy.chapter(SUB) as state:
        state['stage'] = 'draft'
        state['jobs']['drafter'] = {'started': fdy.now(), 'provider': 'codex'}
    fdy.cmd_collect('drafter', SUB, '-')
    assert fdy.load(SUB)['stage'] == 'solve'
    assert fdy.load(SUB)['jobs']['drafter']['ok'] is True
    assert not fdy.gates(SUB)['ok']


def test_authoring_collection_still_blocks_malformed_written_inventory(fdy):
    path = fdy.pack_path(SUB)
    pack = json.loads(path.read_text())
    form = written_form()
    del form['answer']
    pack['teach'][SUB + '.1']['forms'] = [form]
    path.write_text(json.dumps(pack))
    add_legacy_state(fdy, [SUB])
    with fdy.chapter(SUB) as state:
        state['stage'] = 'draft'
        state['jobs']['drafter'] = {'started': fdy.now(), 'provider': 'codex'}
    fdy.cmd_collect('drafter', SUB, '-')
    assert fdy.load(SUB)['stage'] == 'draft'
    assert not fdy.load(SUB)['jobs']['drafter']['ok']


def test_authoring_collection_does_not_defer_invalid_present_review(fdy):
    path = fdy.pack_path(SUB)
    pack = json.loads(path.read_text())
    pack['teach'][SUB + '.1']['forms'] = [written_form()]
    path.write_text(json.dumps(pack))
    evidence = fdy.LOCATIONS.work('refine') / f'{SUB}.written-review.json'
    evidence.parent.mkdir(parents=True, exist_ok=True)
    evidence.write_text(json.dumps({SUB + '.1.form.0.check': {'verdict': 'rejected'}}))
    add_legacy_state(fdy, [SUB])
    with fdy.chapter(SUB) as state:
        state['stage'] = 'draft'
        state['jobs']['drafter'] = {'started': fdy.now(), 'provider': 'codex'}
    fdy.cmd_collect('drafter', SUB, '-')
    assert fdy.load(SUB)['stage'] == 'draft'
    assert not fdy.load(SUB)['jobs']['drafter']['ok']
