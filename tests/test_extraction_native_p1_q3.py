"""Two-part schema/source sentinels in disposable vaults; no content approval."""
import copy
import json
from pathlib import Path
import random
import shlex

import pytest
from ial_p1_fixtures import QP, MS, source_fixture
import test_extraction_native_p1_launch as launch
from tutorlib import ial_p1_identity as policy, model, packs, session, store, topicals, topical_selection
from tutorlib.asset_library import AssetLibrary

Q3 = 'P1_pearson-edexcel-ial_WMA11_2019-01_01_q3'
SELECTORS = [QP + '=1,6-7', MS + '=1-7,11-12']
PAGES = [[1, 6, 7], [1, 2, 3, 4, 5, 6, 7, 11, 12]]
IDS = ['native-' + Q3 + '-a', 'native-' + Q3 + '-b']


def regs(lib, ref, pages):
    return [{'source_id': ref, 'source_sha256': lib.record(ref)['sha256'],
             'page': p, 'box': [0, 0, 1, 1]} for p in pages]


def fresh(tmp_path, monkeypatch):
    ex, vault = launch.fresh_inputs(tmp_path, monkeypatch)
    state = launch.create(ex, official_qid=Q3, source_pages=SELECTORS, codex_stop_remaining=40)
    return ex, vault, state


def candidate(state, lib):
    return {'selected_item_scope': copy.deepcopy(state['selected_item_scope']), 'diagrams': [],
            'questions': [{'id': rid, 'official_qid': Q3, 'part': part,
                'regions': regs(lib, QP, [6, 7]), 'mark_scheme_regions': regs(lib, MS, [11, 12]),
                'kind': 'structured', 'complete': True, 'uncertainty': [],
                'stem': 'Synthetic part ' + part + ' schema sentinel, not native mathematics.',
                'answer': 'Synthetic private answer ' + part, 'marks': 1,
                'scheme': [{'point': 'Synthetic private scheme ' + part}],
                'syllabus': ['P1-1'], 'kcs': ['P1-1.1'], 'prerequisites': [],
                'media': [part + '-task.png', part + '-ms.png'],
                'question_media': [part + '-task.png'], 'mark_scheme_media': [part + '-ms.png']}
                for rid, part in zip(IDS, ['a', 'b'])],
            'source_coverage': [{'source_id': s['id'], 'source_sha256': s['sha256'],
                'inspected_pages': list(s['selected_page_numbers']), 'no_relevant_content': False,
                'reason': ''} for s in state['sources']]}


def reviewed(tmp_path, monkeypatch, *, whole=False):
    from PIL import Image
    ex, vault, state = fresh(tmp_path, monkeypatch)
    state = ex.plan('fresh'); path = Path(state['candidate']); path.parent.mkdir(parents=True)
    data = candidate(state, AssetLibrary(vault))
    for index, q in enumerate(data['questions']):
        for name in q['media']:
            Image.new('RGB', (100, 100), (index * 80, 60, 120 if '-ms' in name else 0)).save(path.parent / name)
        if whole:
            q['scheme'] = [{'point': 'Synthetic unallocated private rubric ' + q['part'],
                'whole_rubric': {'version': 1, 'max_marks': 1, 'media': q['mark_scheme_media']}}]
    def save():
        path.write_text(json.dumps(data))
        (ex.job_dir('fresh') / 'review.json').write_text(json.dumps({
            'candidate_sha256': ex.digest(path), 'verdict': 'pass', 'findings': [],
            'inspected_images': [ex.digest(path.parent / n) for q in data['questions'] for n in q['media']]}))
    # Synthetic completed process outcomes establish only the test's schema gate.
    with ex.state_lock('fresh') as current:
        current['jobs']['extract']['exit'] = current['jobs']['review']['exit'] = 0
    save()
    return ex, vault, path, data, save


def ready_tutor(vault, seed=0, *, ready=True):
    """Real engine with disposable P1 readiness, without changing graph/content."""
    tutor = session.Tutor(store.Vault(vault), rng=random.Random(seed), one_at_a_time=True)
    if tutor.session:
        tutor.end(abandoned=True)
    tutor.state = model.new_state()
    if ready:
        tutor.log({'type': 'chapter_started', 'chapter': 'P1-1'})
        card = model._fsrs().Card().to_dict()
        card['due'] = '2026-01-01T00:00:00+00:00'
        tutor.state['kcs']['P1-1.1'] = {**model._new_kc(), 'n': 1, 'fsrs': card}
    return tutor


def assert_public_view(view, pending, library, private_media):
    """Question views expose only task media, never a sibling/private rubric."""
    def walk(value):
        if isinstance(value, dict):
            assert not {'answer', 'answers', 'scheme', 'rubric', 'mark_scheme', 'mark_scheme_media'} & value.keys()
            for child in value.values(): walk(child)
        elif isinstance(value, list):
            for child in value: walk(child)
    walk(view)
    actual = view.get('images') or ([view['image']] if view.get('image') else [])
    expected = pending['inst'].get('images') or ([pending['inst']['image']] if pending['inst'].get('image') else [])
    assert actual == expected
    assert not set(actual) & set(private_media)
    for reference in actual: library.read(reference)


@pytest.mark.parametrize('part', ['a', 'b'])
def test_q3_assessed_identity_is_distinct_from_whole_scope(part):
    assert topicals.identity({'source': {'qid': Q3, 'part': part}}) == Q3 + ':' + part
    assert topicals.official_course({'qid': Q3, 'part': part}) == 'P1'
    descriptor = policy.p1_pilot(Q3, part)
    assert descriptor['question'] == 3 and descriptor['part'] == part
    descriptor['qp']['sha256'] = 'changed'
    assert policy.p1_pilot(Q3, part)['qp']['sha256'] != 'changed'
    question = policy.p1_question(Q3)
    assert question['assessed_parts'] == ['a', 'b']
    question['assessed_parts'].pop()
    assert policy.p1_question(Q3)['assessed_parts'] == ['a', 'b']


@pytest.mark.parametrize('part', ['', None, True, 'A', 'B', '(a)', '(b)', ' a ', 'a!', 'a/b', 'ab', 'a1', 'c'])
def test_q3_noncanonical_parts_cannot_fall_back_or_alias(part):
    assert policy.p1_pilot(Q3, part) is None
    assert topicals.identity({'source': {'qid': Q3, 'part': part, 'ref': '9702 Jun 2023 P22 Q2(a)'}}) is None


@pytest.mark.parametrize('tail', ['q03', 'Q3', 'q3:a', 'q3(a)', 'q5', 'q30', 'q3 '])
def test_q3_whole_scope_is_exact(tail):
    qid = Q3.rsplit('_', 1)[0] + '_' + tail
    assert policy.p1_question(qid) is None
    assert topicals.identity({'source': {'qid': qid, 'part': 'a'}}) is None


@pytest.mark.parametrize('part', ['a', 'b'])
def test_q3_source_envelope_accepts_both_required_pages_and_only_declared_context(tmp_path, part):
    lib = source_fixture(tmp_path)
    q, m = regs(lib, QP, [6, 7]), regs(lib, MS, [11, 12])
    policy.validate_p1_sources(Q3, part, 'P1', q, m, lib)
    policy.validate_p1_sources(Q3, part, 'P1', q, regs(lib, MS, [1, 3, 7, 11, 12]), lib)
    for ref, allowed, total in [(QP, {6, 7}, 28), (MS, {1, 2, 3, 4, 5, 6, 7, 11, 12}, 29)]:
        for page in set(range(1, total + 1)) - allowed:
            bad = sorted((q if ref == QP else m) + regs(lib, ref, [page]), key=lambda r: r['page'])
            with pytest.raises(ValueError):
                policy.validate_p1_sources(Q3, part, 'P1', bad if ref == QP else q, bad if ref == MS else m, lib)
    for badq, badm in [(q[:1], m), (q[1:], m), (q, m[:1]), (q, m[1:]),
                         (regs(lib, QP, [4, 5]), regs(lib, MS, [9, 10]))]:
        with pytest.raises(ValueError): policy.validate_p1_sources(Q3, part, 'P1', badq, badm, lib)
    for change in [{'page': True}, {'page': 6.0}, {'source_id': MS}, {'source_sha256': '0' * 64},
                   {'box': [0, 0, float('nan'), 1]}, {'box': [False, 0, 1, 1]}, {'box': [0, 0, 0, 1]}]:
        bad = copy.deepcopy(q); bad[0].update(change)
        with pytest.raises(ValueError): policy.validate_p1_sources(Q3, part, 'P1', bad, m, lib)
    with pytest.raises(ValueError): policy.validate_p1_sources(Q3, part, 'P1', list(reversed(q)), m, lib)


def test_q3_fresh_api_cli_resume_and_gapped_plan(tmp_path, monkeypatch, capsys):
    ex, vault, state = fresh(tmp_path, monkeypatch)
    assert state['jobs'] == {} and not Path(state['candidate']).exists()
    assert state['initial_native_question'] == {'version': 1, 'official_qid': Q3, 'part': '', 'source_pages': SELECTORS, 'job_name': 'fresh'}
    assert state['selected_item_scope']['record_ids'] == IDS
    assert state['selected_item_scope']['assessed_parts'] == dict(zip(IDS, ['a', 'b']))
    assert [s['selected_page_numbers'] for s in state['sources']] == PAGES
    assert ex.resume('fresh') == state
    state = ex.plan('fresh')
    for role in ('extract', 'review'):
        contract = json.loads(ex._prompt(state, role).split('JOB CONTRACT:\n')[1])
        assert not contract.get('previous_candidate')
        for source, runs in zip(state['sources'], [[[1], [6, 7]], [[1, 2, 3, 4, 5, 6, 7], [11, 12]]]):
            read = contract['bounded_read_plan'][source['id']]
            assert 'text' not in read and [r['pages'] for r in read['text_runs']] == runs
            for row in read['text_runs']:
                tokens = shlex.split(row['command']); assert tokens[-4:-1] == ['text', source['id'], '--pages']
                bounds = tokens[-1].split('-')
                assert list(range(int(bounds[0]), int(bounds[-1]) + 1)) == row['pages']
            assert [r['page'] for r in read['render']] == source['selected_page_numbers']
    assert ex.main(['new', 'q3-cli', '--course', 'P1', '--scope', 'questions', '--provider', 'codex',
                    '--official-qid', Q3, '--source-pages', SELECTORS[1], '--source-pages', SELECTORS[0]]) == 0
    assert json.loads(capsys.readouterr().out)['initial_native_question']['source_pages'] == SELECTORS
    before = (ex.job_dir('fresh') / 'state.json').read_bytes()
    for call in [lambda: ex.focus('fresh', Q3, 'sentinel'), lambda: ex.next_question('fresh', Q3, 'sentinel')]:
        with pytest.raises(ValueError): call()
        assert (ex.job_dir('fresh') / 'state.json').read_bytes() == before


@pytest.mark.parametrize('fault', ['missing-a', 'missing-b', 'duplicate', 'swapped', 'aggregate', 'extra', 'diagram', 'scope', 'context'])
def test_q3_all_part_coverage_rejects_candidate_mutations(tmp_path, monkeypatch, fault):
    ex, vault, state = fresh(tmp_path, monkeypatch); data = candidate(state, AssetLibrary(vault))
    assert ex._coverage(state, data) == []
    if fault == 'missing-a': data['questions'].pop(0)
    if fault == 'missing-b': data['questions'].pop()
    if fault == 'duplicate': data['questions'].append(copy.deepcopy(data['questions'][0]))
    if fault == 'swapped': data['questions'][0]['part'] = 'b'; data['questions'][1]['part'] = 'a'
    if fault == 'aggregate': data['questions'][0]['part'] = ''
    if fault == 'extra': data['questions'].append({**data['questions'][0], 'id': 'extra', 'part': 'c'})
    if fault == 'diagram': data['diagrams'] = [copy.deepcopy(data['questions'][0])]
    if fault == 'scope': data['selected_item_scope']['record_ids'].pop()
    if fault == 'context': data['source_coverage'][1]['inspected_pages'].remove(7)
    assert ex._coverage(state, data)


@pytest.mark.parametrize('fault', ['one-record', 'swapped', 'version', 'graph', 'source', 'page'])
def test_q3_binding_mutations_fail_before_any_effect(tmp_path, monkeypatch, fault):
    ex, _, state = fresh(tmp_path, monkeypatch); state = ex.plan('fresh')
    if fault == 'one-record': state['selected_item_scope']['record_ids'].pop()
    if fault == 'swapped': state['selected_item_scope']['assessed_parts'] = dict(zip(IDS, ['b', 'a']))
    if fault == 'version': state['initial_native_question']['version'] = True
    if fault == 'graph': state['focus_graph_sha256'] = '0' * 64
    if fault == 'source': state['sources'][0]['sha256'] = '0' * 64
    if fault == 'page': state['sources'][0]['selected_page_numbers'] = [1, 4, 5]
    path = ex.job_dir('fresh') / 'state.json'; path.write_text(json.dumps(state)); before = path.read_bytes()
    def deny(*args, **kwargs): pytest.fail('invalid binding reached provider/render')
    monkeypatch.setattr(ex.worker_timeout, 'run_captured', deny); monkeypatch.setattr(ex.library, 'render', deny)
    for call in [lambda: ex.resume('fresh'), lambda: ex.plan('fresh'), lambda: ex._prompt(state, 'extract'),
                 lambda: ex._prompt(state, 'review'), lambda: ex.run('fresh', weekly_remaining=75),
                 lambda: ex.check('fresh'), lambda: ex.register('fresh'),
                 lambda: ex.prepare_publication('fresh', tmp_path / 'batch'), lambda: ex.publish('fresh', tmp_path / 'batch')]:
        with pytest.raises(ValueError): call()
        assert path.read_bytes() == before
    assert not Path(state['candidate']).parent.exists() and not (tmp_path / 'batch').exists()


@pytest.mark.parametrize('fault', ['retarget', 'named-child-alias', 'candidate-file-alias', 'candidate-hardlink', 'coherent-name-retarget'])
def test_q3_ownership_reuses_all_manager_guards(tmp_path, monkeypatch, fault):
    original = launch.create
    monkeypatch.setattr(launch, 'create', lambda ex, **kw: original(ex, official_qid=Q3, source_pages=SELECTORS, codex_stop_remaining=40, **kw))
    launch.test_fresh_p1_output_ownership_fails_before_manager_or_worker_effects(tmp_path, monkeypatch, fault)


@pytest.mark.parametrize('whole', [False, True])
def test_q3_both_parts_publish_select_and_route_privately(tmp_path, monkeypatch, whole):
    ex, vault, path, data, save = reviewed(tmp_path, monkeypatch, whole=whole)
    checked = ex.check('fresh'); assert checked['stage'] == 'reviewed', checked['problems']
    candidate_bytes = path.read_bytes(); review_bytes = (ex.job_dir('fresh') / 'review.json').read_bytes()
    ex.register('fresh'); batch = tmp_path / 'batch'; ex.prepare_publication('fresh', batch); ex.publish('fresh', batch)
    runtime = packs.Packs(store.Vault(vault)); assert not runtime.topical_errors
    items = runtime.topicals.items
    assert [topicals.identity(i) for i in items] == [Q3 + ':a', Q3 + ':b']
    assert {topicals.identity(i) for i in runtime.items_for('P1-1.1') if topicals.identity(i)} >= {Q3 + ':a', Q3 + ':b'}
    assert runtime.kcs['P1-1.1']['level'] == 'P1'
    # Real selector state is constructed below; per-record identity/alias sets
    # must stay disjoint even though source inspection pages overlap.
    assert not runtime.aliases_for(items[0]) & runtime.aliases_for(items[1])
    assert {topicals.identity(i) for i in runtime.topical_items('P1-1')} == {Q3 + ':a', Q3 + ':b'}
    for item, q in zip(items, data['questions']):
        assert (item['stem'], item['answer'], item['marks'], item['kcs']) == (q['stem'], q['answer'], q['marks'], q['kcs'])
        assert item['source']['extraction_regions'] == q['regions']
        assert item['source']['mark_scheme_regions'] == q['mark_scheme_regions']
        if whole:
            private = topicals.whole_rubric_media(item, vault)
            assert private and all(m['reference'] not in item['images'] for m in private)
        else: assert item['scheme'] == q['scheme']
    # Publication is read through the real repository bank/asset interfaces.
    state = ex.load('fresh'); lib = AssetLibrary(vault)
    bank = json.loads(lib.read(state['publication']['release'] + '/bank.json'))
    assert bank['items'] == items
    assert {item['source']['extraction_job'] for item in items} == {'fresh'}
    assert {item['source']['candidate_sha256'] for item in items} == {ex.digest(path)}
    private_media = []
    for q in data['questions']:
        context = ex.hashlib.sha256(json.dumps(q, sort_keys=True).encode()).hexdigest()[:12]
        private_media.extend(state['registered_records'][context][name] for name in q['mark_scheme_media'])
    # Each part must appear through normal Topical and Long selection. Separate
    # ready learner states preserve the engine's legitimate no-help/family rules.
    for mode in ('topical', 'long'):
        seen = set()
        for seed in range(3):
            tutor = ready_tutor(vault, seed)
            if mode == 'topical':
                choices = tutor.topical_choices(['P1-1'], ['structured'])
                assert choices['available'] == choices['counts']['structured'] == 2
            started = tutor.start(mode, minutes=30, focus=['P1-1.1'],
                **({'topical_count': 2, 'topical_types': ['structured']} if mode == 'topical' else {}))
            assert started.get('ok') is not False, started
            activity = tutor.next()
            if activity.get('activity') == 'choose' and activity.get('purpose') == 'goal':
                tutor.respond({'choice': 'gaps'}); activity = tutor.next()
            assert activity.get('items'), activity
            for view in activity['items']:
                pending = tutor.session['presented'][str(view['n'])]
                assert_public_view(view, pending, lib, private_media)
                if pending['unassisted']:
                    assert tutor.hint(view['n']).get('refused')
                if topicals.identity(pending['inst']) in (Q3 + ':a', Q3 + ':b'):
                    seen.add(topicals.identity(pending['inst']))
            if seen == {Q3 + ':a', Q3 + ':b'}: break
        assert seen == {Q3 + ':a', Q3 + ':b'}, (mode, seen)
    # Check the clean prerequisite path without pre-populating readiness.
    clean = ready_tutor(vault, ready=False)
    assert not topicals.started_chapters(clean.state, clean.packs)
    for item in items:
        eligibility = topicals.eligibility(item, 'P1-1', clean.state, clean.packs, unassisted=True)
        assert eligibility['missing'] == []  # only the serving chapter is required
    tutor = ready_tutor(vault)
    groups = topical_selection.pools(runtime, tutor.state, ['P1-1'], ['structured'])
    assert topical_selection.counts(groups)['structured'] == 2
    for excluded in ({'used': [Q3 + ':a']}, {'disclosed': runtime.aliases_for(items[0])}):
        remaining = topical_selection.pools(runtime, tutor.state, ['P1-1'], ['structured'], **excluded)
        assert [topicals.identity(i) for i in remaining['P1-1']] == [Q3 + ':b']
    if whole:
        tutor.start('review', minutes=10)
        first = tutor._present(items[0], block='practice', phase=None)['n']
        second = tutor._present(items[1], block='practice', phase=None)['n']
        assert tutor.whole_rubric(first, '').get('error')
        assert tutor.scheme(second).get('error')
        disclosed = tutor.whole_rubric(first, 'Synthetic saved working for a.')
        assert disclosed['ticket']
        assert disclosed['media'] == [m['reference'] for m in topicals.whole_rubric_media(items[0], vault)]
        assert items[1]['answer'] not in json.dumps(disclosed)
        assert tutor.scheme(second).get('error')
        wrong = tutor.answer(f'{second} = Synthetic saved working for a.',
            manual_awards={second: {'earned_marks': 1, 'ticket': disclosed['ticket']}})
        assert wrong['results'][0].get('error')
        # Misuse consumes the one-use capability; obtain a fresh attempted-a ticket.
        disclosed = tutor.whole_rubric(first, 'Synthetic saved working for a.')
        awarded = tutor.answer(f'{first} = Synthetic saved working for a.',
            manual_awards={first: {'earned_marks': 1, 'ticket': disclosed['ticket']}})
        assert awarded['results'][0].get('event'), awarded
        answer = [e for e in tutor.vault.events() if e['type'] == 'answer'][-1]
        assert topicals.identity(answer['question']) == Q3 + ':a'
        assert answer['human_award']['earned_marks'] == 1
        historical = list(tutor.vault.events())
        assert not tutor.regrade(answer['id'], 'Unapproved replacement grade')['ok']
        assert list(tutor.vault.events()) == historical
        assert tutor.scheme(second).get('error')
    assert path.read_bytes() == candidate_bytes and (ex.job_dir('fresh') / 'review.json').read_bytes() == review_bytes


@pytest.mark.parametrize('fault', ['missing', 'duplicate', 'swapped', 'aggregate', 'source', 'scheme', 'context'])
def test_q3_publication_bijection_and_binding_fail_before_pointer_write(tmp_path, monkeypatch, fault):
    ex, vault, _, data, _ = reviewed(tmp_path, monkeypatch)
    ex.register('fresh'); batch = tmp_path / 'batch'; ex.prepare_publication('fresh', batch)
    bankpath = batch / 'bank.json'; bank = json.loads(bankpath.read_text())
    if fault == 'missing': bank['items'].pop()
    if fault == 'duplicate': bank['items'].append(copy.deepcopy(bank['items'][0]))
    if fault == 'swapped':
        bank['items'][0]['source']['part'] = 'b'; bank['items'][1]['source']['part'] = 'a'
    if fault == 'aggregate': bank['items'][0]['source']['part'] = ''
    if fault == 'source': bank['items'][0]['source']['extraction_regions'][0]['page'] = 4
    if fault == 'scheme': bank['items'][0]['scheme'][0]['point'] = 'Unreviewed replacement'
    if fault == 'context': bank['items'][0]['kcs'] = ['P1-1.2']
    bankpath.write_text(json.dumps(bank))
    catalog = (vault / 'Library/catalog.json').read_bytes()
    with pytest.raises(ValueError): ex.publish('fresh', batch)
    assert not (vault / '.tutor/topicals/CURRENT').exists()
    assert (vault / 'Library/catalog.json').read_bytes() == catalog


@pytest.mark.parametrize('fault', ['bytes', 'catalog-course', 'catalog-kind', 'catalog-path', 'catalog-hash', 'missing'])
def test_q3_original_source_drift_rejected(tmp_path, fault):
    lib = source_fixture(tmp_path); q = regs(lib, QP, [6, 7]); m = regs(lib, MS, [11, 12])
    if fault == 'bytes': (tmp_path / lib.record(QP)['path']).write_bytes(b'corrupt')
    if fault == 'missing': (tmp_path / lib.record(MS)['path']).unlink()
    if fault.startswith('catalog-'):
        path = tmp_path / 'Library/catalog.json'; data = json.loads(path.read_text())
        key = fault.removeprefix('catalog-'); key = 'sha256' if key == 'hash' else key
        data['assets'][QP[6:]][key] = {'course': '9702', 'kind': 'Diagrams', 'path': 'Library/wrong.pdf', 'sha256': '0' * 64}[key]
        path.write_text(json.dumps(data)); lib = AssetLibrary(tmp_path)
    for part in ('a', 'b'):
        with pytest.raises(ValueError): policy.validate_p1_sources(Q3, part, 'P1', q, m, lib)


@pytest.mark.parametrize('remaining', [None, 0, 39.99, 40, float('nan'), 101])
def test_q3_stop_40_guard_precedes_provider_effects(tmp_path, monkeypatch, remaining):
    ex, _, state = fresh(tmp_path, monkeypatch); ex.plan('fresh')
    path = ex.job_dir('fresh') / 'state.json'; before = path.read_bytes()
    def deny(*args, **kwargs): pytest.fail('stop guard reached provider')
    monkeypatch.setattr(ex.subprocess, 'Popen', deny)
    with pytest.raises(ValueError, match='weekly'): ex.run('fresh', weekly_remaining=remaining)
    assert path.read_bytes() == before and not Path(state['candidate']).exists()


def test_q3_actual_fake_provider_retry_retains_both_records_and_feedback(tmp_path, monkeypatch):
    ex, vault, path, data, save = reviewed(tmp_path, monkeypatch)
    with ex.state_lock('fresh') as state:
        state['jobs']['extract'].update(finished='Synthetic completed schema maker', output_sha256=ex.digest(path))
        state['jobs']['review'].pop('exit')
    original = path.read_bytes()
    fake = tmp_path / 'fake-only-provider'
    fake.write_text("""#!/usr/bin/env python3
import hashlib,json,os,sys
from pathlib import Path
import random
contract=json.loads(sys.argv[-1].split('JOB CONTRACT:\\n',1)[1])
output=Path(os.environ['EXTRACT_OUTPUT'])
if os.environ['EXTRACT_ROLE']=='review':
    output.write_text(json.dumps({'candidate_sha256':hashlib.sha256(Path(contract['candidate']).read_bytes()).hexdigest(),
        'verdict':'pending','findings':['Synthetic doubt for both-part source review.'],'inspected_images':[]}))
else:
    output.write_bytes(Path(contract['previous_candidate']).read_bytes())
""")
    fake.chmod(0o755); monkeypatch.setenv('STEM_EXTRACT_CODEX', str(fake))
    ex.run('fresh', weekly_remaining=75, wait=True)
    checked = ex.load('fresh'); assert len(checked['reliability_failures']['1']['review']) == 1
    ex.run('fresh', weekly_remaining=75, wait=True, retry='extract')
    repaired = ex.resume('fresh')
    assert path.read_bytes() == original and Path(repaired['previous_candidate']).read_bytes() == original
    assert repaired['selected_item_scope']['assessed_parts'] == dict(zip(IDS, ['a', 'b']))
    assert repaired['codex_stop_remaining'] == 40
    contract = json.loads((ex.job_dir('fresh') / 'extract.prompt.txt').read_text().split('JOB CONTRACT:\n')[1])
    assert contract['review_feedback']['findings'] == ['Synthetic doubt for both-part source review.']
    assert not repaired.get('focus_history') and repaired['teaching_approved'] is False
