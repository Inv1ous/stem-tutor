"""Fresh configuration only: real immutable inputs, no native content approval."""
import copy
import json
from pathlib import Path
import shlex

import pytest

import library_assets
from ial_p1_fixtures import QID, QP, MS, source_fixture, regions
from test_extraction import extraction
from tutorlib.asset_library import AssetLibrary, register_asset

SELECTORS = [QP + '=1-3', MS + '=1-8']
ORIGIN = 'fresh_native_p1_v1'
RECORD = 'native-' + QID


def fresh_inputs(tmp_path, monkeypatch):
    """Start without a job, candidate, saved maker or inherited scope."""
    vault = tmp_path / 'vault'; vault.mkdir(parents=True)
    source_fixture(vault)
    base = vault / '.tutor/packs/v1'; base.mkdir(parents=True)
    (base.parent / 'CURRENT').write_text('v1')
    (base / 'manifest.json').write_text(json.dumps({'version': 'v1', 'specs': []}))
    (base / 'papers.json').write_text('{"papers": []}')
    (base / 'plan.json').write_text('{}')
    (vault / '.tutor/config.json').write_text('{"tz":"Asia/Hong_Kong"}')
    library_assets.install_course(vault, 'P1', 'P1-1')
    for path in (vault / 'Library/Releases/v1').rglob('*.json'):
        register_asset(vault, path.relative_to(vault).as_posix())
    monkeypatch.delenv('STEM_LIBRARY_ROOT', raising=False)
    monkeypatch.setenv('STEM_TUTOR_VAULT', str(vault))
    monkeypatch.setenv('STEM_EXTRACT_ROOT', str(tmp_path / 'Work'))
    monkeypatch.setenv('STEM_LIBRARY_CACHE', str(tmp_path / 'reader-cache'))
    monkeypatch.setenv('STEM_LIBRARY_SPECS', str(base / 'specs'))
    return extraction(), vault


def create(ex, name='fresh', **changes):
    options = {'provider': 'codex', 'scope': 'questions', 'official_qid': QID,
               'source_pages': SELECTORS, 'codex_model': 'model-sentinel', 'codex_effort': 'medium',
               'codex_stop_remaining': 32}
    course = changes.pop('course', 'P1'); options.update(changes)
    return ex.create(name, course, **options)


def assert_initial(ex, state):
    assert state['stage'] == 'inventoried' and state['jobs'] == {}
    assert state['requested_sources'] == [QP, MS] and state['requested_pages'] is None
    assert state['initial_native_question'] == {'version': 1, 'official_qid': QID, 'part': '', 'source_pages': SELECTORS, 'job_name': state['name']}
    scope = state['selected_item_scope']
    assert scope['origin'] == ORIGIN and scope['official_qid'] == QID
    assert scope['record_ids'] == [RECORD] and scope['assessed_parts'] == {RECORD: ''}
    assert state['focus_graph_sha256'] == ex._course_graph_input('P1')[1]
    assert [s['id'] for s in state['sources']] == [QP, MS]
    assert [s['selected_page_numbers'] for s in state['sources']] == [[1, 2, 3], list(range(1, 9))]
    assert not Path(state['candidate']).parent.exists()
    assert not (ex.job_dir(state['name']) / 'review.json').exists()
    assert all(key not in state for key in ('focus_history', 'previous_candidate', 'candidate_sha256', 'required_source_occurrences', 'completed_scope_history'))
    assert state['teaching_approved'] is False


def test_fresh_p1_create_api_and_cli_bind_scope_before_any_worker(tmp_path, monkeypatch, capsys):
    ex, _ = fresh_inputs(tmp_path, monkeypatch)
    def deny(*args, **kwargs): raise AssertionError('configuration invoked a worker')
    monkeypatch.setattr(ex, 'worker_command', deny)
    state = create(ex, source_pages=list(reversed(SELECTORS))); assert_initial(ex, state)
    assert state['codex_model'] == 'model-sentinel' and state['codex_stop_remaining'] == 32
    assert ex.main(['new', 'cli', '--course', 'P1', '--scope', 'questions', '--provider', 'codex',
                    '--official-qid', QID, '--source-pages', SELECTORS[0], '--source-pages', SELECTORS[1]]) == 0
    output = json.loads(capsys.readouterr().out); assert_initial(ex, output)


def test_fresh_p1_verifies_without_focus_history_or_maker_output(tmp_path, monkeypatch):
    ex, _ = fresh_inputs(tmp_path, monkeypatch); state = create(ex)
    before = (ex.job_dir('fresh') / 'state.json').read_bytes()
    ex._verify_sources(state)
    assert all(ex._ocr_reader_source(state, source) == source for source in state['sources'])
    assert ex.resume('fresh') == state and ex.inventory('fresh') == state
    assert (ex.job_dir('fresh') / 'state.json').read_bytes() == before
    planned = ex.plan('fresh')
    assert planned['jobs'] == {'extract': {'provider': 'codex'}, 'review': {'provider': 'codex'}}
    for role in ('extract', 'review'):
        contract = json.loads(ex._prompt(planned, role).split('JOB CONTRACT:\n')[1])
        assert contract['initial_native_question'] == state['initial_native_question']
        assert not Path(planned['candidate']).exists()


@pytest.mark.parametrize('change', [
    {'official_qid': None}, {'source_pages': None}, {'source_pages': []}, {'course': '9702'},
    {'scope': 'both'}, {'scope': 'diagrams'}, {'official_qid': QID + ':a'},
    {'official_qid': QID.replace('q1', 'q2')},  # valid identity, wrong Q1 selectors
    {'official_qid': QID.replace('q1', 'q3')}, {'sources': [QP]}, {'pages': '1-8'},
    {'source_pages': SELECTORS[:1]}, {'source_pages': SELECTORS + [QP + '=1']},
    {'source_pages': [SELECTORS[0], SELECTORS[0]]},
    {'source_pages': [QP + '=1-8', MS + '=1-3']},
    {'source_pages': [QP + '=1-8', SELECTORS[1]]},
    {'source_pages': [QP + '=0-3', SELECTORS[1]]},
    {'source_pages': [QP + '=3-1', SELECTORS[1]]},
    {'source_pages': ['sources/papers/ial/WMA11/WMA11_2019_Jan_qp.pdf=1-3', SELECTORS[1]]},
    {'source_pages': [QP + '=1-2', SELECTORS[1]]}, {'source_pages': [QP + '=1-3', MS + '=1-9']},
])
def test_fresh_p1_rejects_each_configuration_fault(tmp_path, monkeypatch, change):
    ex, _ = fresh_inputs(tmp_path, monkeypatch)
    with pytest.raises(ValueError): create(ex, **change)
    assert not (ex.job_dir('fresh') / 'state.json').exists()
    assert not (ex.work_root() / 'Candidates/extraction/fresh').exists()


@pytest.mark.parametrize('fault', ['scope', 'origin', 'marker', 'missing-marker', 'version-bool', 'part', 'record', 'graph', 'pages', 'page-bool', 'status', 'ocr', 'path', 'hash', 'extra', 'requested-pages', 'requested-sources', 'focus-history', 'rebase', 'references', 'completed'])
def test_fresh_p1_rejects_each_binding_fault_before_boundaries(tmp_path, monkeypatch, fault):
    ex, _ = fresh_inputs(tmp_path, monkeypatch); create(ex); state = ex.plan('fresh')
    if fault == 'scope': state['scope'] = 'both'
    if fault == 'origin': state['selected_item_scope']['origin'] = 'repair'
    if fault == 'marker': state['initial_native_question'] = None
    if fault == 'missing-marker': state.pop('initial_native_question')
    if fault == 'version-bool': state['initial_native_question']['version'] = True
    if fault == 'part': state['selected_item_scope']['assessed_parts'][RECORD] = 'a'
    if fault == 'record': state['selected_item_scope']['record_ids'] = ['unknown-old']
    if fault == 'graph': state['focus_graph_sha256'] = '0' * 64
    if fault == 'pages': state['sources'][0]['selected_page_numbers'] = [1, 2, 3, 4]
    if fault == 'page-bool': state['sources'][0]['selected_page_numbers'][0] = True
    if fault == 'status': state['sources'][0]['status'] = 'pending_ocr'
    if fault == 'ocr': state['sources'][0]['ocr'] = {'synthetic': True}
    if fault == 'path': state['sources'][0]['path'] = str(tmp_path / 'other.pdf')
    if fault == 'hash': state['sources'][0]['sha256'] = '0' * 64
    if fault == 'extra': state['sources'].append(copy.deepcopy(state['sources'][0]))
    if fault == 'requested-pages': state['requested_pages'] = '1-8'
    if fault == 'requested-sources': state['requested_sources'].reverse()
    if fault == 'focus-history': state['focus_history'] = []
    if fault == 'rebase': state['source_rebase_history'] = []
    if fault == 'references': state['reference_source_history'] = []
    if fault == 'completed': state['completed_scope_history'] = []
    path = ex.job_dir('fresh') / 'state.json'; path.write_text(json.dumps(state)); before = path.read_bytes()
    def deny(*args, **kwargs): raise AssertionError('invalid binding reached worker/provider')
    monkeypatch.setattr(ex.worker_timeout, 'run_captured', deny)
    monkeypatch.setattr(ex, 'worker_command', deny)
    for call in (lambda: ex._verify_sources(state), lambda: ex._ocr_reader_source(state, state['sources'][0]),
                 lambda: ex._prompt(state, 'extract'), lambda: ex._prompt(state, 'review'),
                 lambda: ex.resume('fresh'), lambda: ex.plan('fresh'),
                 lambda: ex.configure('fresh', 'sentinel', codex_stop_remaining=35),
                 lambda: ex.graph('fresh', kc_id='P1-1.1'),
                 lambda: ex.run('fresh', weekly_remaining=90), lambda: ex._worker('fresh', 'extract')):
        with pytest.raises(ValueError): call()
        assert path.read_bytes() == before
    assert not Path(state['candidate']).parent.exists()


def test_fresh_p1_reader_requires_exact_native_inventory_row(tmp_path, monkeypatch):
    ex, _ = fresh_inputs(tmp_path, monkeypatch); state = create(ex)
    substituted = copy.deepcopy(state['sources'][0])
    substituted['selected_page_numbers'][0] = True
    with pytest.raises(ValueError): ex._ocr_reader_source(state, substituted)


@pytest.mark.parametrize('fault', ['bytes', 'metadata', 'graph'])
def test_fresh_p1_rejects_original_input_drift(tmp_path, monkeypatch, fault):
    ex, vault = fresh_inputs(tmp_path, monkeypatch); state = create(ex)
    if fault == 'bytes': (vault / AssetLibrary(vault).record(QP)['path']).write_bytes(b'corrupt')
    if fault == 'metadata':
        path = vault / 'Library/catalog.json'; data = json.loads(path.read_text()); data['assets'][MS[6:]]['course'] = '9702'; path.write_text(json.dumps(data))
    if fault == 'graph':
        path = vault / 'Library/Releases/v1/specs/P1/graph.json'; path.write_bytes(b'{}')
    with pytest.raises((ValueError, ex.library.Fail)): ex._verify_sources(state)
    with pytest.raises((ValueError, ex.library.Fail)): create(ex, name='invalid-input')
    assert not (ex.job_dir('invalid-input') / 'state.json').exists()


def coverage_sentinel(state):
    row = {'id': RECORD, 'official_qid': QID, 'part': '',
           'regions': [{'source_id': QP, 'source_sha256': state['sources'][0]['sha256'], 'page': 3, 'box': [0, 0, 1, 1]}],
           'mark_scheme_regions': [{'source_id': MS, 'source_sha256': state['sources'][1]['sha256'], 'page': 8, 'box': [0, 0, 1, 1]}]}
    return {'selected_item_scope': copy.deepcopy(state['selected_item_scope']), 'questions': [row], 'diagrams': [],
            'source_coverage': [{'source_id': s['id'], 'source_sha256': s['sha256'], 'inspected_pages': s['selected_page_numbers'], 'no_relevant_content': False, 'reason': ''} for s in state['sources']]}


def test_fresh_p1_first_prompt_and_coverage_are_truthful(tmp_path, monkeypatch):
    ex, _ = fresh_inputs(tmp_path, monkeypatch); create(ex); state = ex.plan('fresh')
    for role in ('extract', 'review'):
        text = ex._prompt(state, role); contract = json.loads(text.split('JOB CONTRACT:\n')[1])
        assert contract['selected_item_scope']['origin'] == ORIGIN
        assert contract['course_graph_sha256'] == state['focus_graph_sha256']
        assert all('selected_page_range' not in s for s in contract['sources'])
        assert 'fresh' in text.lower() and 'initial_native_question' in text
        assert not contract.get('previous_candidate')
        reads = contract['bounded_read_plan']
        assert set(reads) == {QP, MS}
        for source in state['sources']:
            read = reads[source['id']]; pages = source['selected_page_numbers']
            tokens = shlex.split(read['text']); assert tokens[-2:] == ['--pages', f'1-{pages[-1]}']
            assert tokens[-3] == source['id']
            assert [entry['page'] for entry in read['render']] == pages
            assert all(shlex.split(entry['command'])[-2:] == [source['id'], str(entry['page'])] for entry in read['render'])
    data = coverage_sentinel(state); assert ex._coverage(state, data) == []
    for mutate in (lambda d: d['questions'].append(copy.deepcopy(d['questions'][0])),
                   lambda d: d['questions'][0].update(part='a'), lambda d: d['questions'][0].update(official_qid=QID + ':a'),
                   lambda d: d['selected_item_scope'].update(coverage_claim='page-wide'),
                   lambda d: d['source_coverage'].pop(), lambda d: d['source_coverage'][0]['inspected_pages'].reverse(),
                   lambda d: d['source_coverage'][0].update(no_relevant_content=True, reason='sentinel')):
        changed = copy.deepcopy(data); mutate(changed); assert ex._coverage(state, changed)


@pytest.mark.parametrize('ref,page', [(QP, 4), (MS, 9)])
def test_fresh_p1_crop_refuses_unselected_page_before_render_or_write(tmp_path, monkeypatch, ref, page):
    ex, _ = fresh_inputs(tmp_path, monkeypatch); state = create(ex)
    def deny(*args, **kwargs): raise AssertionError('unselected page rendered')
    monkeypatch.setattr(ex.library, 'render', deny)
    with pytest.raises(ValueError, match='selected'): ex.crop('fresh', ref, page, '0,0,1,1', 'crop.png')
    assert not Path(state['candidate']).parent.exists()


def test_fresh_p1_selected_crop_keeps_existing_safe_output_rules(tmp_path, monkeypatch):
    from PIL import Image
    ex, _ = fresh_inputs(tmp_path, monkeypatch); state = create(ex)
    rendered = tmp_path / 'render-sentinel.png'; Image.new('RGB', (10, 10), 'red').save(rendered)
    calls = []
    def render(path, page, dpi): calls.append((path, page, dpi)); return rendered
    monkeypatch.setattr(ex.library, 'render', render)
    cropped = ex.crop('fresh', QP, 3, '0,0,1,1', 'crop.png')
    assert cropped['source_id'] == QP and cropped['page'] == 3 and calls[0][1] == 3
    before = (Path(state['candidate']).parent / 'crop.png').read_bytes()
    for name in ('crop.png', '../outside.png', 'wrong.jpg'):
        with pytest.raises(ValueError): ex.crop('fresh', QP, 3, '0,0,1,1', name)
    assert (Path(state['candidate']).parent / 'crop.png').read_bytes() == before


@pytest.mark.parametrize('stage', ['new', 'planned', 'extracting', 'reviewed', 'registered', 'published', 'pending'])
def test_fresh_p1_existing_jobs_are_unchanged_on_refusal(tmp_path, monkeypatch, stage):
    ex, _ = fresh_inputs(tmp_path, monkeypatch); state = create(ex)
    with ex.state_lock('fresh') as state:
        state['stage'] = stage; state['reliability_failures'] = {'1': {'extract': [{'issues': ['one']}, {'issues': ['two']}]}}
    path = ex.job_dir('fresh') / 'state.json'; before = path.read_bytes()
    with pytest.raises(ValueError, match='exists'): create(ex)
    assert path.read_bytes() == before


@pytest.mark.parametrize('operation', ['focus', 'evidence', 'references', 'next', 'ocr'])
def test_fresh_p1_rebind_apis_are_unchanged_on_refusal(tmp_path, monkeypatch, operation):
    ex, _ = fresh_inputs(tmp_path, monkeypatch); create(ex)
    path = ex.job_dir('fresh') / 'state.json'; before = path.read_bytes()
    actions = {'focus': lambda: ex.focus('fresh', QID, 'sentinel'), 'evidence': lambda: ex.evidence_sources('fresh', SELECTORS, 'sentinel'),
               'references': lambda: ex.reference_sources('fresh', SELECTORS, 'sentinel purpose', 'sentinel'),
               'next': lambda: ex.next_question('fresh', QID, 'sentinel'), 'ocr': lambda: ex.enable_ocr('fresh', QP)}
    with pytest.raises(ValueError): actions[operation]()
    assert path.read_bytes() == before
    assert not (ex.work_root() / 'Preparation').exists()
    assert not (ex.work_root() / 'Candidates').exists()


def test_fresh_p1_orphan_output_is_not_adopted(tmp_path, monkeypatch):
    ex, _ = fresh_inputs(tmp_path, monkeypatch)
    orphan = ex.work_root() / 'Candidates/extraction/fresh/old-media.png'; orphan.parent.mkdir(parents=True); orphan.write_bytes(b'orphan')
    with pytest.raises(ValueError): create(ex)
    assert orphan.read_bytes() == b'orphan' and not (ex.job_dir('fresh') / 'state.json').exists()


def test_fresh_p1_binding_is_lifecycle_neutral_and_guards_are_unchanged(tmp_path, monkeypatch):
    ex, _ = fresh_inputs(tmp_path, monkeypatch); create(ex); state = ex.plan('fresh')
    for stage in ('planned', 'extracting', 'pending', 'reviewing', 'reviewed', 'registered', 'published'):
        candidate = copy.deepcopy(state); candidate['stage'] = stage; ex._verify_sources(candidate)
    with ex.state_lock('fresh') as current:
        current['reliability_failures'] = {'1': {'extract': [{'issues': ['one']}, {'issues': ['two']}]}}
    before = (ex.job_dir('fresh') / 'state.json').read_bytes()
    with pytest.raises(ValueError, match='paused after 2 failures'): ex.run('fresh', retry='extract', weekly_remaining=90)
    assert (ex.job_dir('fresh') / 'state.json').read_bytes() == before
    # Initial configuration is not a candidate or independent review.
    checked = ex.check('fresh'); assert checked['stage'] == 'pending'
    with pytest.raises(ValueError): ex.register('fresh')
    with pytest.raises(ValueError): ex.prepare_publication('fresh', tmp_path / 'batch')
    with pytest.raises(ValueError): ex.publish('fresh', tmp_path / 'batch')
    assert not (tmp_path / 'batch').exists()


@pytest.mark.parametrize('fault', ['retarget', 'named-child-alias', 'candidate-file-alias', 'candidate-hardlink', 'coherent-name-retarget'])
def test_fresh_p1_output_ownership_fails_before_manager_or_worker_effects(tmp_path, monkeypatch, fault):
    ex, _ = fresh_inputs(tmp_path, monkeypatch); create(ex); state = ex.plan('fresh')
    old = ex.work_root() / 'Candidates/extraction/existing-unknown/candidate.json'
    old.parent.mkdir(parents=True); old.write_bytes(b'Preserved unknown candidate bytes.')
    owned = Path(state['candidate'])
    if fault in ('retarget', 'coherent-name-retarget'):
        state['candidate'] = str(old)
        if fault == 'coherent-name-retarget': state['name'] = 'existing-unknown'
    elif fault == 'named-child-alias': owned.parent.symlink_to(old.parent, target_is_directory=True)
    else:
        owned.parent.mkdir()
        if fault == 'candidate-hardlink': owned.hardlink_to(old)
        else: owned.symlink_to(old)
    path = ex.job_dir('fresh') / 'state.json'; path.write_text(json.dumps(state)); before = path.read_bytes()
    old_bytes = old.read_bytes(); entries = sorted(p.name for p in old.parent.iterdir())
    def deny(*args, **kwargs): raise AssertionError('invalid ownership reached a provider or renderer')
    monkeypatch.setattr(ex.worker_timeout, 'run_captured', deny)
    monkeypatch.setattr(ex.library, 'render', deny)
    calls = [lambda: ex._verify_initial_native_question(state), lambda: ex._prompt(state, 'extract'),
             lambda: ex._prompt(state, 'review'), lambda: ex.worker_command(state, 'extract'),
             lambda: ex.resume('fresh'), lambda: ex.plan('fresh'),
             lambda: ex.configure('fresh', 'sentinel', codex_stop_remaining=35),
             lambda: ex.graph('fresh', kc_id='P1-1.1'), lambda: ex.run('fresh', weekly_remaining=90),
             lambda: ex._worker('fresh', 'extract'), lambda: ex.crop('fresh', QP, 3, '0,0,1,1', 'new.png'),
             lambda: ex.check('fresh'), lambda: ex.register('fresh'),
             lambda: ex.prepare_publication('fresh', tmp_path / 'batch'), lambda: ex.publish('fresh', tmp_path / 'batch')]
    for call in calls:
        with pytest.raises(ValueError): call()
        assert path.read_bytes() == before and old.read_bytes() == old_bytes
        assert sorted(p.name for p in old.parent.iterdir()) == entries
    assert not (tmp_path / 'batch').exists() and not (ex.work_root() / 'Preparation').exists()


@pytest.mark.parametrize('adapter', ['work-root', 'candidates-root', 'extraction-parent'])
def test_fresh_p1_parent_adapters_keep_owned_candidate_and_real_same_scope_retry(tmp_path, monkeypatch, adapter):
    """Synthetic schema/fake-provider proof, not native source review or approval."""
    from PIL import Image
    ex, _ = fresh_inputs(tmp_path, monkeypatch)
    actual = tmp_path / 'working-data'; actual.mkdir()
    alias = {'work-root': ex.work_root(), 'candidates-root': ex.work_root() / 'Candidates',
             'extraction-parent': ex.work_root() / 'Candidates/extraction'}[adapter]
    alias.parent.mkdir(parents=True, exist_ok=True); alias.symlink_to(actual, target_is_directory=True)
    initial = create(ex); state = ex.plan('fresh'); candidate = Path(state['candidate']); candidate.parent.mkdir(parents=True)
    data = coverage_sentinel(state)
    Image.new('RGB', (10, 10), 'red').save(candidate.parent / 'prompt.png')
    Image.new('RGB', (10, 10), 'blue').save(candidate.parent / 'rubric.png')
    data['questions'][0].update(complete=True, uncertainty=[], kind='structured',
        stem='Synthetic retry sentinel; no native task claim.', answer='Synthetic answer.', marks=1,
        scheme=[{'point': 'Synthetic schema point; no official rubric claim.'}],
        syllabus=['P1-1'], kcs=['P1-1.1'], prerequisites=[], media=['prompt.png', 'rubric.png'],
        question_media=['prompt.png'], mark_scheme_media=['rubric.png'])
    candidate.write_text(json.dumps(data)); original = candidate.read_bytes()
    with ex.state_lock('fresh') as current:
        current['jobs']['extract'].update(exit=0, finished='synthetic schema sentinel', output_sha256=ex.digest(candidate))
    fake = tmp_path / 'fake-only-provider'
    fake.write_text('''#!/usr/bin/env python3
import hashlib,json,os,sys
from pathlib import Path
contract=json.loads(sys.argv[-1].split('JOB CONTRACT:\\n',1)[1])
output=Path(os.environ['EXTRACT_OUTPUT'])
if os.environ['EXTRACT_ROLE']=='review':
    output.write_text(json.dumps({'candidate_sha256':hashlib.sha256(Path(contract['candidate']).read_bytes()).hexdigest(),
        'verdict':'pending','findings':['Synthetic schema doubt.'],'inspected_images':[]}))
else:
    output.write_bytes(Path(contract['previous_candidate']).read_bytes())
''')
    fake.chmod(0o755); monkeypatch.setenv('STEM_EXTRACT_CODEX', str(fake))
    ex.run('fresh', weekly_remaining=90, wait=True)
    reviewed = ex.load('fresh'); assert len(reviewed['reliability_failures']['1']['review']) == 1
    ex.run('fresh', weekly_remaining=90, wait=True, retry='extract')
    repaired = ex.resume('fresh')
    assert repaired['candidate'] == initial['candidate'] and candidate.read_bytes() == original
    previous = Path(repaired['previous_candidate'])
    assert previous.parent == candidate.parent and previous.name.startswith('candidate.json.') and previous.name.endswith('.previous')
    assert previous.read_bytes() == original and repaired['reliability_failures'] == reviewed['reliability_failures']
    contract = json.loads((ex.job_dir('fresh') / 'extract.prompt.txt').read_text().split('JOB CONTRACT:\n', 1)[1])
    assert contract['review_feedback']['findings'] == ['Synthetic schema doubt.']
    assert contract['initial_native_question'] == initial['initial_native_question']
    assert 'focus_history' not in repaired and repaired['teaching_approved'] is False
