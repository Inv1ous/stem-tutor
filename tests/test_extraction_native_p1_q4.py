"""Portable Q4 structure/source sentinels; synthetic content is never approval."""
import copy
import json
from pathlib import Path
import shlex

import pytest
from ial_p1_fixtures import QID, QP, MS, source_fixture
import test_extraction_native_p1_launch as launch
import test_extraction_native_p1_q3 as q3
from tutorlib import ial_p1_identity as policy, packs, store, topicals
from tutorlib.asset_library import AssetLibrary

Q4 = 'P1_pearson-edexcel-ial_WMA11_2019-01_01_q4'
RID = 'native-' + Q4
SELECTORS = [QP + '=1,8-9', MS + '=1-7,13']
PAGES = [[1, 8, 9], [1, 2, 3, 4, 5, 6, 7, 13]]


def regs(lib, ref, pages):
    return [{'source_id': ref, 'source_sha256': lib.record(ref)['sha256'],
             'page': p, 'box': [0, 0, 1, 1]} for p in pages]


def fresh(tmp_path, monkeypatch):
    ex, vault = launch.fresh_inputs(tmp_path, monkeypatch)
    return ex, vault, launch.create(ex, official_qid=Q4, source_pages=SELECTORS, codex_stop_remaining=40)


def candidate(state, lib):
    return {'selected_item_scope': copy.deepcopy(state['selected_item_scope']), 'diagrams': [],
        'questions': [{'id': RID, 'official_qid': Q4, 'part': '',
            'regions': regs(lib, QP, [8, 9]), 'mark_scheme_regions': regs(lib, MS, [13]),
            'kind': 'structured', 'complete': True, 'uncertainty': [],
            'stem': 'Synthetic Q4 schema sentinel; not native mathematics.',
            'answer': 'Synthetic private answer.', 'marks': 3,
            'scheme': [{'point': 'Synthetic private schema point ' + str(n)} for n in range(3)],
            'syllabus': ['P1-1'], 'kcs': ['P1-1.1'], 'prerequisites': [],
            'media': ['task.png', 'ms.png'], 'question_media': ['task.png'], 'mark_scheme_media': ['ms.png']}],
        'source_coverage': [{'source_id': s['id'], 'source_sha256': s['sha256'],
            'inspected_pages': list(s['selected_page_numbers']), 'no_relevant_content': False,
            'reason': ''} for s in state['sources']]}


def reviewed(tmp_path, monkeypatch, *, whole=False):
    from PIL import Image
    ex, vault, state = fresh(tmp_path, monkeypatch)
    state = ex.plan('fresh'); path = Path(state['candidate']); path.parent.mkdir(parents=True)
    data = candidate(state, AssetLibrary(vault))
    Image.new('RGB', (100, 100), (10, 60, 20)).save(path.parent / 'task.png')
    Image.new('RGB', (100, 100), (80, 30, 120)).save(path.parent / 'ms.png')
    if whole:
        data['questions'][0]['scheme'] = [{'point': 'Synthetic unallocated private rubric.',
            'whole_rubric': {'version': 1, 'max_marks': 3, 'media': ['ms.png']}}]
    def save():
        path.write_text(json.dumps(data))
        (ex.job_dir('fresh') / 'review.json').write_text(json.dumps({
            'candidate_sha256': ex.digest(path), 'verdict': 'pass', 'findings': [],
            'inspected_images': [ex.digest(path.parent / n) for n in ['task.png', 'ms.png']]}))
    with ex.state_lock('fresh') as current:
        current['jobs']['extract']['exit'] = current['jobs']['review']['exit'] = 0
    save()
    return ex, vault, path, data, save


def test_q4_exact_whole_identity_and_independent_descriptor():
    assert policy.p1_identity(Q4, '') == Q4
    assert topicals.identity({'source': {'qid': Q4, 'part': ''}}) == Q4
    assert topicals.official_course({'qid': Q4, 'part': ''}) == 'P1'
    descriptor = policy.p1_question(Q4)
    assert descriptor['question'] == 4 and descriptor['part'] == ''
    assert descriptor.get('assessed_parts', ['']) == ['']
    assert descriptor['qp']['initial_pages'] == [1, 8, 9]
    assert descriptor['ms']['initial_selector'] == '1-7,13'
    descriptor['qp']['sha256'] = 'tampered'
    assert policy.p1_pilot(Q4, '')['qp']['sha256'] != 'tampered'
    for tail in ['q04', 'Q4', 'q4:a', 'q4(a)', 'q5', 'q40', 'q4 ']:
        bad = Q4.rsplit('_', 1)[0] + '_' + tail
        assert policy.p1_question(bad) is None
        assert topicals.identity({'source': {'qid': bad, 'part': '', 'ref': '9702 Jun 2023 P22 Q2(a)'}}) is None
    for part in [None, True, 'a', 'A', '(a)', ' ', 'whole']:
        assert policy.p1_pilot(Q4, part) is None
        assert topicals.identity({'source': {'qid': Q4, 'part': part}}) is None


def test_q4_source_envelope_and_geometry(tmp_path):
    lib = source_fixture(tmp_path); q = regs(lib, QP, [8, 9]); m = regs(lib, MS, [13])
    policy.validate_p1_sources(Q4, '', 'P1', q, m, lib)
    policy.validate_p1_sources(Q4, '', 'P1', q, regs(lib, MS, [1, 3, 6, 7, 13]), lib)
    for ref, allowed, total in [(QP, {8, 9}, 28), (MS, {1, 2, 3, 4, 5, 6, 7, 13}, 29)]:
        for page in set(range(1, total + 1)) - allowed:
            bad = sorted((q if ref == QP else m) + regs(lib, ref, [page]), key=lambda r: r['page'])
            with pytest.raises(ValueError):
                policy.validate_p1_sources(Q4, '', 'P1', bad if ref == QP else q, bad if ref == MS else m, lib)
    for badq, badm in [(q[:1], m), (q[1:], m), (q, []), (q, regs(lib, MS, [1, 6])), (list(reversed(q)), m)]:
        with pytest.raises(ValueError): policy.validate_p1_sources(Q4, '', 'P1', badq, badm, lib)
    for change in [{'page': True}, {'page': 8.0}, {'source_id': MS}, {'source_sha256': '0' * 64},
                   {'box': [0, 0, float('nan'), 1]}, {'box': [0, 0, float('inf'), 1]},
                   {'box': [False, 0, 1, 1]}, {'box': [0, 0, 0, 1]}, {'box': [-1, 0, 1, 1]}]:
        bad = copy.deepcopy(q); bad[0].update(change)
        with pytest.raises(ValueError): policy.validate_p1_sources(Q4, '', 'P1', bad, m, lib)
    with pytest.raises(ValueError): policy.validate_p1_sources(Q4, '', 'P2', q, m, lib)


def test_q4_fresh_api_cli_resume_gapped_plan_and_crop_limits(tmp_path, monkeypatch, capsys):
    ex, _, state = fresh(tmp_path, monkeypatch)
    assert state['jobs'] == {} and not Path(state['candidate']).exists()
    assert state['initial_native_question'] == {'version': 1, 'official_qid': Q4, 'part': '', 'source_pages': SELECTORS, 'job_name': 'fresh'}
    assert state['selected_item_scope']['record_ids'] == [RID]
    assert state['selected_item_scope']['assessed_parts'] == {RID: ''}
    assert [s['selected_page_numbers'] for s in state['sources']] == PAGES
    assert ex.resume('fresh') == state
    state = ex.plan('fresh')
    for role in ('extract', 'review'):
        contract = json.loads(ex._prompt(state, role).split('JOB CONTRACT:\n')[1])
        assert not contract.get('previous_candidate')
        for source, runs in zip(state['sources'], [[[1], [8, 9]], [[1, 2, 3, 4, 5, 6, 7], [13]]]):
            read = contract['bounded_read_plan'][source['id']]
            assert 'text' not in read and [r['pages'] for r in read['text_runs']] == runs
            for row in read['text_runs']:
                tokens = shlex.split(row['command']); assert tokens[-4:-1] == ['text', source['id'], '--pages']
                bounds = tokens[-1].split('-')
                assert list(range(int(bounds[0]), int(bounds[-1]) + 1)) == row['pages']
            assert [r['page'] for r in read['render']] == source['selected_page_numbers']
    assert ex.main(['new', 'q4-cli', '--course', 'P1', '--scope', 'questions', '--provider', 'codex',
                    '--official-qid', Q4, '--source-pages', SELECTORS[1], '--source-pages', SELECTORS[0]]) == 0
    assert json.loads(capsys.readouterr().out)['initial_native_question']['source_pages'] == SELECTORS
    def deny(*args, **kwargs): pytest.fail('excluded crop reached renderer')
    monkeypatch.setattr(ex.library, 'render', deny)
    for ref, page in [(QP, 2), (QP, 7), (MS, 8), (MS, 12)]:
        with pytest.raises(ValueError, match='outside'): ex.crop('fresh', ref, page, '0,0,1,1', 'excluded.png')
    assert not Path(state['candidate']).exists()


def snapshot(root):
    return {p.relative_to(root).as_posix(): __import__('hashlib').sha256(p.read_bytes()).hexdigest() for p in root.rglob('*')
            if p.is_file() and p.name != '.lock'}


@pytest.mark.parametrize('operation', ['material', 'focus'])
def test_q4_source_correct_legacy_focus_requires_fresh_before_effects(tmp_path, monkeypatch, operation):
    ex, _, path, _, _ = reviewed(tmp_path, monkeypatch)
    state = ex.load('fresh'); state.pop('initial_native_question'); state.pop('selected_item_scope')
    state['jobs']['extract'].update(finished='Synthetic saved maker', output_sha256=ex.digest(path))
    statepath = ex.job_dir('fresh') / 'state.json'; statepath.write_text(json.dumps(state))
    before = snapshot(tmp_path)
    with pytest.raises(ValueError, match='fresh'):
        if operation == 'material': ex._question_focus_material(state, Q4)
        else: ex.focus('fresh', Q4, 'Synthetic legacy adoption attempt')
    assert snapshot(tmp_path) == before


@pytest.mark.parametrize('operation', ['problems', 'check', 'review', 'register', 'prepare', 'publish'])
@pytest.mark.parametrize('fault', ['stripped', 'mixed', 'forged-origin', 'q1-config'])
def test_q4_candidate_rows_cannot_inherit_legacy_approval(tmp_path, monkeypatch, operation, fault):
    ex, _, path, data, save = reviewed(tmp_path, monkeypatch)
    state = ex.load('fresh'); state.pop('initial_native_question'); state.pop('selected_item_scope')
    data.pop('selected_item_scope')
    if fault == 'mixed':
        other = copy.deepcopy(data['questions'][0]); other.update(id='legacy-q1', official_qid=QID,
            regions=regs(AssetLibrary(Path(ex.library.learner_vault())), QP, [1]),
            mark_scheme_regions=regs(AssetLibrary(Path(ex.library.learner_vault())), MS, [1]))
        data['questions'].insert(0, other)
        state['sources'][0]['selected_page_numbers'] = [1, 8, 9]
    if fault == 'forged-origin': state['selected_item_scope'] = {'origin': 'fresh_native_p1_v1', 'official_qid': Q4}
    if fault == 'q1-config':
        state['initial_native_question'] = {'version': 1, 'official_qid': QID, 'part': '',
            'source_pages': launch.SELECTORS, 'job_name': 'fresh'}
    save(); statepath = ex.job_dir('fresh') / 'state.json'; statepath.write_text(json.dumps(state))
    before = snapshot(tmp_path)
    def deny(*args, **kwargs): pytest.fail('legacy Q4 reached provider')
    monkeypatch.setattr(ex.worker_timeout, 'run_captured', deny)
    monkeypatch.setattr(ex.subprocess, 'Popen', deny)
    calls = {'problems': lambda: ex._candidate_problems(state), 'check': lambda: ex.check('fresh'),
        'review': lambda: ex.run('fresh', weekly_remaining=75),
        'register': lambda: ex.register('fresh'), 'prepare': lambda: ex.prepare_publication('fresh', tmp_path / 'batch'),
        'publish': lambda: ex.publish('fresh', tmp_path / 'batch')}
    with pytest.raises(ValueError, match='fresh'):
        calls[operation]()
    assert snapshot(tmp_path) == before


def test_q4_legacy_target_guard_precedes_candidate_path_read(tmp_path, monkeypatch):
    ex, _, state = fresh(tmp_path, monkeypatch)
    state.pop('initial_native_question'); state.pop('selected_item_scope')
    def deny(*args, **kwargs): pytest.fail('legacy target read candidate before refusal')
    monkeypatch.setattr(ex, 'candidate_path', deny)
    with pytest.raises(ValueError, match='fresh'): ex._question_focus_material(state, Q4)


def test_q4_next_question_rejects_from_published_q1_without_effects(tmp_path, monkeypatch):
    ex, vault, path, data, save = reviewed(tmp_path, monkeypatch)
    q1 = copy.deepcopy(data['questions'][0]); q1.update(id='legacy-q1', official_qid=QID,
        regions=regs(AssetLibrary(vault), QP, [1]), mark_scheme_regions=regs(AssetLibrary(vault), MS, [1]))
    data['questions'].insert(0, q1); data.pop('selected_item_scope'); save()
    with ex.state_lock('fresh') as state:
        state.pop('initial_native_question'); state.pop('selected_item_scope')
        state['jobs']['extract'].update(finished='Synthetic saved maker', output_sha256=ex.digest(path))
    focused = ex.focus('fresh', QID, 'Synthetic Q1 legacy compatibility')
    current = Path(focused['candidate'])
    (ex.job_dir('fresh') / 'review.json').write_text(json.dumps({'candidate_sha256': ex.digest(current),
        'verdict': 'pass', 'findings': [], 'inspected_images': [ex.digest(current.parent / n) for n in ['task.png', 'ms.png']]}))
    with ex.state_lock('fresh') as state: state['jobs']['review']['exit'] = 0
    ex.register('fresh'); batch = tmp_path / 'q1-batch'; ex.prepare_publication('fresh', batch); ex.publish('fresh', batch)
    before = snapshot(tmp_path)
    with pytest.raises(ValueError, match='fresh'): ex.next_question('fresh', Q4, 'Synthetic next target')
    assert snapshot(tmp_path) == before


@pytest.mark.parametrize('fault', ['missing', 'invalid-json', 'list', 'wrong-questions'])
def test_q4_preflight_preserves_ordinary_malformed_candidate_diagnostics(tmp_path, monkeypatch, fault):
    ex, _, path, _, _ = reviewed(tmp_path, monkeypatch)
    state = ex.load('fresh'); state.pop('initial_native_question'); state.pop('selected_item_scope')
    if fault == 'missing': path.unlink()
    if fault == 'invalid-json': path.write_text('{bad')
    if fault == 'list': path.write_text('[]')
    if fault == 'wrong-questions': path.write_text('{"questions":null,"diagrams":[]}')
    before = snapshot(tmp_path)
    errors, images = ex._candidate_problems(state)
    assert any('candidate unavailable or invalid' in e for e in errors) and images == []
    assert snapshot(tmp_path) == before


@pytest.mark.parametrize('fault', ['version', 'part', 'selector', 'scope', 'graph', 'source', 'page',
                                  'focus-history', 'rebase-history', 'name', 'candidate-path'])
def test_q4_initial_binding_mutations_refuse_all_boundaries_before_effects(tmp_path, monkeypatch, fault):
    ex, _, state = fresh(tmp_path, monkeypatch); state = ex.plan('fresh')
    if fault == 'version': state['initial_native_question']['version'] = True
    if fault == 'part': state['initial_native_question']['part'] = 'a'
    if fault == 'selector': state['initial_native_question']['source_pages'] = [QP + '=1-9', SELECTORS[1]]
    if fault == 'scope': state['selected_item_scope']['record_ids'] = ['wrong']
    if fault == 'graph': state['focus_graph_sha256'] = '0' * 64
    if fault == 'source': state['sources'][0]['sha256'] = '0' * 64
    if fault == 'page': state['sources'][0]['selected_page_numbers'] = [1, 8]
    if fault == 'focus-history': state['focus_history'] = []
    if fault == 'rebase-history': state['source_rebase_history'] = []
    if fault == 'name': state['name'] = 'retarget'
    if fault == 'candidate-path': state['candidate'] = str(tmp_path / 'elsewhere/candidate.json')
    path = ex.job_dir('fresh') / 'state.json'; path.write_text(json.dumps(state)); before = snapshot(tmp_path)
    def deny(*args, **kwargs): pytest.fail('invalid binding reached provider/render')
    monkeypatch.setattr(ex.worker_timeout, 'run_captured', deny); monkeypatch.setattr(ex.library, 'render', deny)
    for call in [lambda: ex.resume('fresh'), lambda: ex.plan('fresh'), lambda: ex._prompt(state, 'extract'),
                 lambda: ex._prompt(state, 'review'), lambda: ex.run('fresh', weekly_remaining=75),
                 lambda: ex.check('fresh'), lambda: ex.register('fresh'),
                 lambda: ex.prepare_publication('fresh', tmp_path / 'batch'), lambda: ex.publish('fresh', tmp_path / 'batch')]:
        with pytest.raises(ValueError): call()
        assert snapshot(tmp_path) == before


@pytest.mark.parametrize('fault', ['retarget', 'named-child-alias', 'candidate-file-alias', 'candidate-hardlink', 'coherent-name-retarget'])
def test_q4_output_ownership_reuses_manager_guards(tmp_path, monkeypatch, fault):
    original = launch.create
    monkeypatch.setattr(launch, 'create', lambda ex, **kw: original(ex, official_qid=Q4, source_pages=SELECTORS, codex_stop_remaining=40, **kw))
    launch.test_fresh_p1_output_ownership_fails_before_manager_or_worker_effects(tmp_path, monkeypatch, fault)


@pytest.mark.parametrize('fault', ['missing-record', 'duplicate', 'wrong-id', 'part', 'extra', 'diagram', 'scope', 'missing-scope', 'context'])
def test_q4_one_whole_record_and_candidate_scope_are_required(tmp_path, monkeypatch, fault):
    ex, _, _, data, save = reviewed(tmp_path, monkeypatch)
    if fault == 'missing-record': data['questions'] = []
    if fault == 'duplicate': data['questions'].append(copy.deepcopy(data['questions'][0]))
    if fault == 'wrong-id': data['questions'][0]['id'] = 'wrong'
    if fault == 'part': data['questions'][0]['part'] = 'a'
    if fault == 'extra': data['questions'].append({**data['questions'][0], 'id': 'extra', 'official_qid': QID})
    if fault == 'diagram': data['diagrams'] = [copy.deepcopy(data['questions'][0])]
    if fault == 'scope': data['selected_item_scope']['record_ids'] = []
    if fault == 'missing-scope': data.pop('selected_item_scope')
    if fault == 'context': data['source_coverage'][1]['inspected_pages'].remove(6)
    save(); checked = ex.check('fresh')
    assert checked['stage'] == 'pending' and checked['problems']
    assert not checked.get('registrations')


@pytest.mark.parametrize('fault', ['bytes', 'catalog-course', 'catalog-kind', 'catalog-path', 'catalog-hash', 'missing'])
def test_q4_original_source_drift_rejected(tmp_path, fault):
    lib = source_fixture(tmp_path); q = regs(lib, QP, [8, 9]); m = regs(lib, MS, [13])
    if fault == 'bytes': (tmp_path / lib.record(QP)['path']).write_bytes(b'corrupt')
    if fault == 'missing': (tmp_path / lib.record(MS)['path']).unlink()
    if fault.startswith('catalog-'):
        path = tmp_path / 'Library/catalog.json'; data = json.loads(path.read_text())
        key = fault.removeprefix('catalog-'); key = 'sha256' if key == 'hash' else key
        data['assets'][QP[6:]][key] = {'course': '9702', 'kind': 'Diagrams', 'path': 'Library/wrong.pdf', 'sha256': '0' * 64}[key]
        path.write_text(json.dumps(data)); lib = AssetLibrary(tmp_path)
    with pytest.raises(ValueError): policy.validate_p1_sources(Q4, '', 'P1', q, m, lib)


@pytest.mark.parametrize('remaining', [None, 0, 39.99, 40, float('nan'), 101])
def test_q4_stop_40_guard_precedes_provider_effects(tmp_path, monkeypatch, remaining):
    ex, _, state = fresh(tmp_path, monkeypatch); ex.plan('fresh')
    before = snapshot(tmp_path)
    def deny(*args, **kwargs): pytest.fail('stop guard reached provider')
    monkeypatch.setattr(ex.subprocess, 'Popen', deny)
    with pytest.raises(ValueError, match='weekly'): ex.run('fresh', weekly_remaining=remaining)
    assert snapshot(tmp_path) == before and not Path(state['candidate']).exists()


@pytest.mark.parametrize('whole', [False, True])
def test_q4_stateless_import_publication_routes_and_private_disclosure(tmp_path, monkeypatch, whole):
    import topicals as importer
    ex, vault, path, data, _ = reviewed(tmp_path, monkeypatch, whole=whole)
    # Install the real graph required by the seed's declared physics revision.
    launch.library_assets.install_course(vault, '9702', '9702-2.1')
    seed = tmp_path / 'seed'; seed.mkdir()
    old = {'id': 'legacy-stable', 'source': {'type': 'past', 'qid': '9702_s24_22_q9'}, 'kind': 'structured',
        'stem': 'Synthetic', 'answer': 'Synthetic', 'marks': 1, 'scheme': [{'point': 'Synthetic'}],
        'kcs': ['9702-2.1.1'], 'topical': {'reviewed': True, 'revision': '2025-2027',
        'chapters': ['9702-2.1'], 'requires': ['9702-2.1'], 'support': {}}}
    (seed / 'bank.json').write_text(json.dumps({'format_version': 1, 'syllabus_versions': {'9702': '2025-2027'}, 'items': [old]}))
    (seed / 'report.json').write_text(json.dumps({'preparation': {'expected_current': None}}))
    first = importer.publish(seed, vault); old_bank = AssetLibrary(vault).read(first['release'] + '/bank.json')
    history = vault / '.tutor/events/preserved.jsonl'; history.parent.mkdir(parents=True, exist_ok=True)
    history.write_bytes(b'{"type":"synthetic-history","correction":"stable"}\n')
    correction = vault / '.tutor/corrections-sentinel.json'; correction.write_bytes(b'{"binding":"stable"}\n')
    preserved = {p: p.read_bytes() for p in [history, correction, path, ex.job_dir('fresh') / 'review.json']}
    assert ex.check('fresh')['stage'] == 'reviewed'
    ex.register('fresh'); batch = tmp_path / 'batch'; ex.prepare_publication('fresh', batch); ex.publish('fresh', batch)
    runtime = packs.Packs(store.Vault(vault)); assert not runtime.topical_errors
    items = runtime.topicals.items; assert items[0] == old and len(items) == 2
    item = items[1]; q = data['questions'][0]
    assert topicals.identity(item) == Q4 and item['source']['part'] == ''
    for key in ('stem', 'answer', 'marks', 'kcs', 'kind'): assert item[key] == q[key]
    assert item['source']['extraction_regions'] == q['regions']
    assert item['source']['mark_scheme_regions'] == q['mark_scheme_regions']
    assert runtime.kcs['P1-1.1']['level'] == 'P1'
    assert all(p.read_bytes() == value for p, value in preserved.items())
    assert AssetLibrary(vault).read(first['release'] + '/bank.json') == old_bank
    # A separate importer/runtime consumes the valid bank after manager state is gone.
    bank = json.loads((batch / 'bank.json').read_text())
    monkeypatch.setenv('STEM_EXTRACT_ROOT', str(tmp_path / 'no-manager-state'))
    topicals.validate_bank(bank, runtime, vault)
    private = topicals.whole_rubric_media(item, vault) if whole else []
    private_names = [m['reference'] for m in private]
    if not whole:
        state = ex.load('fresh') if ex.job_dir('fresh').exists() else None
        # Private registered image can also be located from the immutable catalog.
        private_names = [row['path'] for row in json.loads((vault / 'Library/catalog.json').read_text())['assets'].values()
                         if '/Questions/Media/ms-' in row['path']]
    assert private_names and not set(private_names) & set(item['images'])
    assert {topicals.identity(i) for i in runtime.items_for('P1-1.1') if topicals.identity(i)} >= {Q4}
    for mode in ('review', 'topical', 'long'):
        tutor = q3.ready_tutor(vault)
        started = tutor.start(mode, minutes=30, focus=['P1-1.1'],
            **({'topical_count': 1, 'topical_types': ['structured']} if mode == 'topical' else {}))
        assert started.get('ok') is not False
        if mode == 'review': activity = {'items': [tutor._present(item, block='practice', phase=None)]}
        else:
            activity = tutor.next()
            if activity.get('activity') == 'choose' and activity.get('purpose') == 'goal':
                tutor.respond({'choice': 'gaps'}); activity = tutor.next()
        assert activity.get('items'), activity
        seen = []
        for view in activity['items']:
            pending = tutor.session['presented'][str(view['n'])]
            q3.assert_public_view(view, pending, AssetLibrary(vault), private_names)
            if topicals.identity(pending['inst']) == Q4: seen.append(view['n'])
        assert seen, (mode, activity)
        if mode == 'review' and whole:
            n = seen[0]; assert tutor.whole_rubric(n, '').get('error')
            disclosed = tutor.whole_rubric(n, 'Synthetic saved working.')
            assert disclosed['ticket'] and disclosed['media'] == private_names
            awarded = tutor.answer(f'{n} = Synthetic saved working.',
                manual_awards={n: {'earned_marks': 2, 'ticket': disclosed['ticket']}})
            assert awarded['results'][0].get('event')
            event = [e for e in tutor.vault.events() if e['type'] == 'answer'][-1]
            assert topicals.identity(event['question']) == Q4 and event['human_award']['earned_marks'] == 2
            before = list(tutor.vault.events())
            assert not tutor.regrade(event['id'], 'Unapproved replacement')['ok']
            assert list(tutor.vault.events()) == before
    if whole:
        (vault / AssetLibrary(vault).record(MS)['path']).write_bytes(b'corrupt original')
        with pytest.raises(ValueError): topicals.whole_rubric_media(item, vault)


@pytest.mark.parametrize('fault', ['missing', 'duplicate', 'part', 'source', 'scheme', 'context'])
def test_q4_publication_binding_fails_before_pointer_write(tmp_path, monkeypatch, fault):
    ex, vault, _, _, _ = reviewed(tmp_path, monkeypatch)
    ex.register('fresh'); batch = tmp_path / 'batch'; ex.prepare_publication('fresh', batch)
    bankpath = batch / 'bank.json'; bank = json.loads(bankpath.read_text())
    if fault == 'missing': bank['items'].pop()
    if fault == 'duplicate': bank['items'].append(copy.deepcopy(bank['items'][0]))
    if fault == 'part': bank['items'][0]['source']['part'] = 'a'
    if fault == 'source': bank['items'][0]['source']['extraction_regions'][0]['page'] = 6
    if fault == 'scheme': bank['items'][0]['scheme'][0]['point'] = 'Unreviewed replacement'
    if fault == 'context': bank['items'][0]['kcs'] = ['P1-1.2']
    bankpath.write_text(json.dumps(bank)); before = snapshot(tmp_path)
    prior_state = ex.load('fresh')
    with pytest.raises(ValueError): ex.publish('fresh', batch)
    after = snapshot(tmp_path)
    state_key = (ex.job_dir('fresh') / 'state.json').relative_to(tmp_path).as_posix()
    assert {k: v for k, v in after.items() if k != state_key} == {k: v for k, v in before.items() if k != state_key}
    assert not (vault / '.tutor/topicals/CURRENT').exists()
    current = ex.load('fresh')
    assert {k: v for k, v in current.items() if k != 'history'} == {k: v for k, v in prior_state.items() if k != 'history'}
    assert current['history'][:-1] == prior_state['history']
    assert {k: v for k, v in current['history'][-1].items() if k != 't'} == {'from': 'reviewed', 'to': 'reviewed', 'note': '0 pending findings'}
