"""Written review evidence uses disposable worker roots and no model calls."""
import copy
import json

import pytest
from test_refine import SUB, _new_state, _written_pack, rf  # noqa: F401


def start(rf):
    pack = _written_pack(rf)
    with _new_state(rf) as st:
        rf.move(st, 'solve')
    rf.cmd_strip(SUB)
    st = rf.load(SUB)
    # Keep the standalone helper tests usable before the strip hook is installed.
    rf._start_written_batch(st, pack)
    return pack, st, rf.written_items(pack)[0]['id']


def finish(rf, st, role, payload):
    metadata = rf._written_launch(st, role)
    path = rf._written_answers(st) if role == 'wsolver' else rf._written_file(SUB, 'decisions')
    path.write_text(json.dumps(payload))
    st['jobs'][role] = {'provider': 'codex', 'model': role, 'started': rf.now(),
                        'finished': rf.now(), 'exit': 0, 'ok': True,
                        'expects': str(path.relative_to(rf.ROOT)), **metadata}
    rf._finish_written_job(st, role)
    with rf.chapter(SUB) as saved:
        saved['jobs'] = copy.deepcopy(st['jobs'])


def reviewed(rf):
    pack, st, ident = start(rf)
    finish(rf, st, 'wsolver', {ident: 'A blind derivation.'})
    rf.write_written_items(SUB)
    finish(rf, st, 'wreviewer', {ident: {'verdict': 'accepted', 'rationale': 'Correct and fair.'}})
    return pack, st, ident


def test_genuine_current_evidence_can_bind(rf):
    pack, st, ident = reviewed(rf)
    assert '1 accepted' in rf._ingest_written(st, pack)
    assert rf.written_review_problems(SUB, pack) == []


@pytest.mark.parametrize('field,value', [('check', 'Another question'), ('answer', 'Another key'),
                                         ('rubric', [{'point': 'Other criterion'}]), ('example', 'Other teaching')])
def test_edit_after_review_cannot_rebind_old_evidence(rf, field, value):
    pack, st, ident = reviewed(rf)
    pack['teach'][f'{SUB}.1']['forms'][0][field] = value
    rf._ingest_written(st, pack)
    assert rf.written_review_problems(SUB, pack)


def test_edit_after_solve_requires_new_blind_round(rf):
    pack, st, ident = start(rf)
    finish(rf, st, 'wsolver', {ident: 'Old proof'})
    pack['teach'][f'{SUB}.1']['forms'][0]['check'] = 'Different stem'
    rf.pack_path(SUB).write_text(json.dumps(pack))
    with pytest.raises(ValueError, match='changed|stale'):
        rf.write_written_items(SUB)


def test_old_or_failed_jobs_are_not_written_proof(rf):
    pack, st, ident = reviewed(rf)
    st['jobs']['wreviewer']['ok'] = False
    assert not rf._written_done(st, 'wreviewer')
    st['jobs']['wreviewer']['ok'] = True
    del st['jobs']['wreviewer']['written_batch']
    assert not rf._written_done(st, 'wreviewer')


def test_mutated_worker_output_is_not_accepted(rf):
    pack, st, ident = reviewed(rf)
    rf._written_file(SUB, 'decisions').write_text(json.dumps({ident: {'verdict': 'accepted', 'rationale': 'Changed'}}))
    assert not rf._written_done(st, 'wreviewer')
    rf._ingest_written(st, pack)
    assert rf.written_review_problems(SUB, pack)


@pytest.mark.parametrize('payload', [None, [], {f'{SUB}.1.form.0.check': ''}, {'unexpected': 'proof'}])
def test_malformed_solver_output_is_retryable(rf, payload):
    pack, st, ident = start(rf)
    finish(rf, st, 'wsolver', payload)
    assert not rf._written_done(st, 'wsolver')


@pytest.mark.parametrize('payload', [None, [], {f'{SUB}.1.form.0.check': 'accepted'},
                                     {f'{SUB}.1.form.0.check': {'verdict': 'accepted', 'rationale': ''}}])
def test_malformed_reviewer_output_is_retryable(rf, payload):
    pack, st, ident = start(rf)
    finish(rf, st, 'wsolver', {ident: 'Proof'})
    rf.write_written_items(SUB)
    finish(rf, st, 'wreviewer', payload)
    assert not rf._written_done(st, 'wreviewer')
    rf._ingest_written(st, pack)
    assert rf.written_review_problems(SUB, pack)


def test_malformed_review_inventory_remains_pending(rf):
    pack, st, ident = start(rf)
    rf._written_file(SUB, 'review').write_text('null')
    assert [it['id'] for it in rf.pending_written(SUB, pack)] == [ident]


def test_changed_form_diagram_requires_review():
    from build.written_review import review_items, fingerprint
    form = {'name': 'N', 'check': 'Q', 'answer': 'A', 'rubric': [{'point': 'P'}], 'diagram': 'Library/A.svg'}
    cards = {'K': {'forms': [form], 'diagrams': ['Library/A.svg']}}
    original = fingerprint(review_items(cards)[0])
    form['diagram'] = 'Library/B.svg'
    cards['K']['diagrams'] = ['Library/B.svg']
    assert fingerprint(review_items(cards)[0]) != original


def test_new_batch_cannot_reuse_finished_jobs_even_in_same_second(rf):
    pack, st, ident = reviewed(rf)
    rf._start_written_batch(st, pack)
    assert not rf._written_done(st, 'wsolver')
    assert not rf._written_done(st, 'wreviewer')
    assert rf._written_jobs(st) == ['wsolver']


def test_recheck_cannot_reuse_solve_outputs(rf):
    pack, st, ident = reviewed(rf)
    with rf.chapter(SUB) as saved:
        rf.move(saved, 'recheck')
    st = rf.load(SUB)
    rf.cmd_strip(SUB, changed=True)
    rf._start_written_batch(st, pack)
    assert not rf._written_done(st, 'wsolver')
    assert not rf._written_done(st, 'wreviewer')


def test_edited_review_inventory_cannot_accept(rf):
    pack, st, ident = reviewed(rf)
    items = json.loads(rf._written_file(SUB, 'items').read_text())
    items[0]['solution'] = 'A different solution'
    rf._written_file(SUB, 'items').write_text(json.dumps(items))
    assert not rf._written_done(st, 'wreviewer')
    rf._ingest_written(st, pack)
    assert rf.written_review_problems(SUB, pack)


def test_manager_rationale_cannot_fabricate_independent_acceptance(rf):
    pack, st, ident = reviewed(rf)
    assert rf.bind_written(SUB, pack, ident,
                           {'verdict': 'accepted', 'rationale': 'Manager says okay'},
                           rf._identity(st, 'wsolver'), 'refine-resolve:Manager')
    assert rf.written_review_problems(SUB, pack)


def test_changed_content_requests_fresh_strip(rf):
    pack, st, ident = reviewed(rf)
    assert not rf._written_needs_strip(st)
    pack['teach'][f'{SUB}.1']['forms'][0]['check'] = 'New question'
    rf.pack_path(SUB).write_text(json.dumps(pack))
    assert rf._written_needs_strip(st)


def test_archived_round_retains_exact_artifacts_and_review_bindings(rf):
    pack, st, ident = reviewed(rf)
    assert '1 accepted' in rf._ingest_written(st, pack)
    paths = [rf._written_file(SUB, kind) for kind in ('batch', 'review', 'items', 'solutions', 'decisions')]
    paths += [rf._written_questions(st), rf._written_answers(st)]
    before = {path.name: path.read_bytes() for path in paths}
    history = rf._archive_written_batch(st)
    assert history is not None
    assert {name: (history / name).read_bytes() for name in before} == before
    old_record = json.loads(before[f'{SUB}.written-review.json'])[ident]
    new_record = json.loads(rf._written_file(SUB, 'review').read_text())[ident]
    assert {key: value for key, value in new_record.items() if key != 'evidence'} == {
        key: value for key, value in old_record.items() if key != 'evidence'}
    assert not rf.written_review_problems(SUB, pack)
    rf._written_questions(st).write_text('[]')  # accepted checks are absent from the next pending inventory
    rf._start_written_batch(st, pack)
    assert {name: (history / name).read_bytes() for name in before} == before
    assert rf._archive_written_batch(st) != history


def test_fresh_acceptance_closes_prior_written_finding(rf):
    pack, st, ident = reviewed(rf)
    st['findings'] = [{'ref': ident, 'rule': 'written review rejected', 'evidence': 'Prior rubric was narrow',
                       'status': 'open'}, {'ref': 'other', 'rule': 'other', 'status': 'open'}]
    assert '1 accepted' in rf._ingest_written(st, pack)
    assert st['findings'][0]['status'] == 'closed'
    assert st['findings'][0]['evidence'] == 'Prior rubric was narrow'
    assert st['findings'][1]['status'] == 'open'


@pytest.mark.parametrize('items', [[None], [{'id': []}], [{'id': 'x'}]])
def test_malformed_batch_inventory_requests_restart(rf, items):
    pack, st, ident = start(rf)
    path = rf._written_file(SUB, 'batch')
    batch = json.loads(path.read_text())
    batch['items'] = items
    path.write_text(json.dumps(batch))
    assert rf._written_needs_strip(st)
    assert not rf._written_done(st, 'wsolver')


def test_launch_and_collect_bind_real_fake_worker_artifacts(rf, tmp_path, monkeypatch):
    from test_refine import finished
    pack, st, ident = start(rf)
    payload = tmp_path / 'solver-payload.json'
    payload.write_text(json.dumps({ident: 'Independent working.'}))
    monkeypatch.setenv('FAKE_COPY', str(payload))
    rf.cmd_run('wsolver', SUB, on='codex')
    assert finished(rf, 'wsolver')['ok']
    st = rf.load(SUB)
    assert rf._done(st, 'wsolver')
    assert st['jobs']['wsolver']['written_batch']
    rf.write_written_items(SUB)
    payload = tmp_path / 'reviewer-payload.json'
    payload.write_text(json.dumps({ident: {'verdict': 'accepted', 'rationale': 'The derivation and rubric agree.'}}))
    monkeypatch.setenv('FAKE_COPY', str(payload))
    rf.cmd_run('wreviewer', SUB, on='codex')
    assert finished(rf, 'wreviewer')['ok']
    st = rf.load(SUB)
    assert rf._done(st, 'wreviewer')
    assert '1 accepted' in rf._ingest_written(st, pack)
    assert not rf.written_review_problems(SUB, pack)


def test_dispatch_rebuilds_legacy_batch_and_preserves_it(rf, monkeypatch):
    pack, st, ident = start(rf)
    batch = rf._written_file(SUB, 'batch')
    old = b'{"legacy": true}'
    batch.write_bytes(old)
    assert rf.todo(st) == ('dispatch',)
    launched = []
    monkeypatch.setattr(rf, 'cmd_run', lambda role, sub, shard=None: launched.append(role))
    rf.cmd_dispatch(SUB)
    assert 'wsolver' in launched
    assert not rf._written_needs_strip(rf.load(SUB))
    copies = list((rf.WORK / 'written-history' / SUB).glob(f'*/{batch.name}'))
    assert any(path.read_bytes() == old for path in copies)


@pytest.mark.parametrize('kind', ['decisions', 'answers', 'questions', 'items', 'batch'])
def test_persisted_approval_requires_unchanged_worker_evidence(rf, kind):
    pack, st, ident = reviewed(rf)
    assert '1 accepted' in rf._ingest_written(st, pack)
    assert not rf.pending_written(SUB, pack)
    path = (rf._written_answers(st) if kind == 'answers' else rf._written_questions(st) if kind == 'questions'
            else rf._written_file(SUB, kind))
    path.write_text('{}')
    assert rf.written_review_problems(SUB, pack)
    assert [item['id'] for item in rf.pending_written(SUB, pack)] == [ident]


def test_approved_unchanged_item_keeps_archived_proof_during_partial_recheck(rf):
    pack, st, first = start(rf)
    other_kc = f'{SUB}.4'
    pack['teach'][other_kc]['forms'] = copy.deepcopy(pack['teach'][f'{SUB}.1']['forms'])
    rf.pack_path(SUB).write_text(json.dumps(pack))
    rf.cmd_strip(SUB)
    st = rf.load(SUB)
    ids = [item['id'] for item in rf.written_items(pack)]
    second = next(ident for ident in ids if ident != first)
    finish(rf, st, 'wsolver', {ident: 'Blind proof' for ident in ids})
    rf.write_written_items(SUB)
    finish(rf, st, 'wreviewer', {first: {'verdict': 'accepted', 'rationale': 'Correct'},
                                second: {'verdict': 'rejected', 'rationale': 'Needs rewording'}})
    assert '1 accepted, 1 rejected' in rf._ingest_written(st, pack)
    # A private answer-key edit changes this check, not the other KC's visible context.
    pack['teach'][other_kc]['forms'][0]['answer'] = 'A corrected private model answer'
    rf.pack_path(SUB).write_text(json.dumps(pack))
    rf.cmd_strip(SUB)
    assert [it['id'] for it in rf.pending_written(SUB, pack)] == [second]
    assert json.loads(rf._written_questions(st).read_text()) == [{'id': second, 'stem': pack['teach'][other_kc]['forms'][0]['check']}]
    # Reusing and replacing canonical evidence for this next worker must not revoke the prior accepted item.
    finish(rf, st, 'wsolver', {second: 'Another blind proof'})
    rf.write_written_items(SUB)
    finish(rf, st, 'wreviewer', {second: {'verdict': 'accepted', 'rationale': 'Now clear and correct'}})
    assert '1 accepted' in rf._ingest_written(st, pack)
    assert not rf.written_review_problems(SUB, pack)
    records = json.loads(rf._written_file(SUB, 'review').read_text())
    assert 'written-history' in records[first]['evidence']['files']['decisions']['path']


def test_content_only_record_without_worker_proof_is_pending(rf):
    from build.written_review import build_records
    pack, st, ident = start(rf)
    record = build_records(rf.written_items(pack), {ident: 'Proof'},
                           {ident: {'verdict': 'accepted', 'rationale': 'Correct'}}, solver='a', reviewer='b')
    rf._written_file(SUB, 'review').write_text(json.dumps(record))
    assert rf.written_review_problems(SUB, pack)
    assert rf.pending_written(SUB, pack)


def test_accepted_record_goes_stale_if_original_decision_becomes_rejected(rf):
    pack, st, ident = reviewed(rf)
    rf._ingest_written(st, pack)
    rf._written_file(SUB, 'decisions').write_text(json.dumps({ident: {'verdict': 'rejected', 'rationale': 'Reconsidered'}}))
    assert rf.written_review_problems(SUB, pack)
    assert rf.pending_written(SUB, pack)


def test_tampered_archived_proof_invalidates_approval(rf):
    pack, st, ident = reviewed(rf)
    rf._ingest_written(st, pack)
    rf._archive_written_batch(st)
    records = json.loads(rf._written_file(SUB, 'review').read_text())
    proof = records[ident]['evidence']['files']['decisions']
    (rf.ROOT / proof['path']).write_text('{}')
    assert rf.written_review_problems(SUB, pack)
    assert rf.pending_written(SUB, pack)


@pytest.mark.parametrize('reference', ['/tmp/elsewhere', '../elsewhere', None])
def test_malformed_durable_proof_is_pending(rf, reference):
    pack, st, ident = reviewed(rf)
    rf._ingest_written(st, pack)
    path = rf._written_file(SUB, 'review')
    records = json.loads(path.read_text())
    records[ident]['evidence']['files']['decisions']['path'] = reference
    path.write_text(json.dumps(records))
    assert rf.written_review_problems(SUB, pack)
    assert rf.pending_written(SUB, pack)


def test_cross_form_review_context_never_enters_blind_solver_payload_or_prompt(rf):
    pack, st, first = start(rf)
    kc = f'{SUB}.1'
    earlier = pack['teach'][kc]['forms'][0]
    earlier['example'] = 'VISIBLE PRIOR CONTEXT reveals target result'
    earlier['answer'] = 'PRIVATE PRIOR KEY'
    target = copy.deepcopy(earlier)
    target.update(name='Target', check='Independent target question',
                  example='CURRENT WORKED ANSWER', answer='PRIVATE CURRENT KEY')
    pack['teach'][kc]['forms'].append(target)
    rf.pack_path(SUB).write_text(json.dumps(pack))
    rf.cmd_strip(SUB)
    st = rf.load(SUB)
    questions = json.loads(rf._written_questions(st).read_text())
    assert questions == [{'id': it['id'], 'stem': it['stem']} for it in rf.pending_written(SUB, pack)]
    payload = json.dumps(questions) + rf.role_prompt('wsolver', SUB)
    for private in ('VISIBLE PRIOR CONTEXT', 'PRIVATE PRIOR KEY', 'PRIVATE CURRENT KEY', 'CURRENT WORKED ANSWER'):
        assert private not in payload
    inventory = rf.written_items(pack)
    assert 'VISIBLE PRIOR CONTEXT' in json.dumps(inventory[-1]['context']['learner_visible_prior'])


def test_written_inventory_loads_one_fresh_catalog_and_resolves_shared_alias_once(rf, tmp_path, monkeypatch):
    pack, _, _ = start(rf)
    kc = f'{SUB}.1'
    ref = 'Library/shared.svg'
    first = tmp_path / 'first.svg'
    second = tmp_path / 'second.svg'
    first.write_text('<svg>first</svg>')
    second.write_text('<svg>second</svg>')
    form = pack['teach'][kc]['forms'][0]
    form['diagram'] = ref
    pack['teach'][kc]['diagrams'] = [ref]
    pack['teach'][kc]['forms'].append(copy.deepcopy(form))
    catalogs, resolutions = [], []
    target = [first]
    def catalog(_):
        catalogs.append(True)
        return {'current': target[0]}
    def resolve(cat, reference):
        resolutions.append(reference)
        return cat['current']
    monkeypatch.setattr(rf.fd, '_diagram_catalog', catalog)
    monkeypatch.setattr(rf.fd, '_catalog_diagram', resolve)
    before = rf.written_items(pack)
    assert len(catalogs) == 1
    assert resolutions == [ref]
    target[0] = second
    after = rf.written_items(pack)
    assert len(catalogs) == 2
    assert resolutions == [ref, ref]
    assert before[0]['context']['current_visible_diagrams'][0]['sha256'] != after[0]['context']['current_visible_diagrams'][0]['sha256']


def test_written_inventory_refreshes_real_catalog_alias_and_rejects_new_tampering(rf, tmp_path, monkeypatch):
    from tutorlib.asset_library import AssetLibrary, write_asset
    pack, _, _ = start(rf)
    vault = tmp_path / 'synthetic-vault'
    vault.mkdir()
    alias = 'Assets/shared.svg'
    one, two = 'Library/one.svg', 'Library/two.svg'
    write_asset(vault, one, b'<svg>one</svg>', aliases=[alias])
    write_asset(vault, two, b'<svg>two</svg>')
    kc = f'{SUB}.1'
    pack['teach'][kc]['diagrams'] = [alias]
    pack['teach'][kc]['forms'][0]['diagram'] = alias
    calls = []
    def catalog(_):
        calls.append(True)
        return AssetLibrary(vault)
    monkeypatch.setattr(rf.fd, '_diagram_catalog', catalog)
    before = rf.written_items(pack)[0]
    catalog_path = vault / 'Library/catalog.json'
    data = json.loads(catalog_path.read_text())
    for entry in data['assets'].values():
        entry['aliases'] = [alias] if entry['path'] == two else []
    catalog_path.write_text(json.dumps(data))
    after = rf.written_items(pack)[0]
    assert before['context']['current_visible_diagrams'][0]['sha256'] != after['context']['current_visible_diagrams'][0]['sha256']
    (vault / two).write_bytes(b'tampered')
    invalid = rf.written_items(pack)[0]
    assert invalid['context']['current_visible_diagrams'][0]['hash_status'] == 'unresolved: ValueError'
    assert len(calls) == 3
