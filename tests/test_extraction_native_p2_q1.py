"""Exact P2 Q1 schema/source sentinels; no mathematical or teaching approval."""
import copy
import importlib.util
import json
from pathlib import Path
import shlex

import pytest
import library_assets
from tutorlib import topicals
from tutorlib.asset_library import AssetLibrary, register_asset
from tutor_workers import collector_question_key as keys

ROOT = Path(__file__).resolve().parents[1]
QID = 'P2_pearson-edexcel-ial_WMA12_2019-06_01_q1'
QP = 'asset:legacy-f10afe0b25e647fb783a2dee'
MS = 'asset:legacy-4da88baf2635cd6489af022d'
PARTS = ['a(i)', 'a(ii)', 'b']
IDS = ['native-' + QID + '-' + suffix for suffix in ('a-i', 'a-ii', 'b')]
SELECTORS = [QP + '=1-2', MS + '=1-7']
PAGES = [[1, 2], [1, 2, 3, 4, 5, 6, 7]]


def extraction():
    spec = importlib.util.spec_from_file_location('p2_extraction_cli', ROOT / 'extraction/extract.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def source_fixture(vault):
    original_library = library_assets._library()
    for ref in (QP, MS):
        original = original_library.record(ref)
        library_assets.copy_to_vault(original['path'], vault)
        path = vault / 'Library/catalog.json'
        data = json.loads(path.read_text())
        old_key = next(k for k, v in data['assets'].items() if v['path'] == original['path'])
        data['assets'].pop(old_key)
        data['assets'][ref[6:]] = original
        path.write_text(json.dumps(data))
    return AssetLibrary(vault)


def regions(lib, ref, pages):
    return [{'source_id': ref, 'source_sha256': lib.record(ref)['sha256'],
             'page': page, 'box': [0, 0, 1, 1]} for page in pages]


def fresh_inputs(tmp_path, monkeypatch, *, with_caie=False):
    vault = tmp_path / 'vault'; vault.mkdir()
    source_fixture(vault)
    base = vault / '.tutor/packs/v1'; base.mkdir(parents=True)
    (base.parent / 'CURRENT').write_text('v1')
    (base / 'manifest.json').write_text('{"version":"v1","specs":[]}')
    (base / 'papers.json').write_text('{"papers":[]}')
    (base / 'plan.json').write_text('{}')
    (vault / '.tutor/config.json').write_text('{"tz":"Asia/Hong_Kong"}')
    library_assets.install_course(vault, 'P2', 'P2-1')
    if with_caie:
        library_assets.install_course(vault, '9702', '9702-2.1')
    for path in (vault / 'Library/Releases/v1').rglob('*.json'):
        register_asset(vault, path.relative_to(vault).as_posix())
    monkeypatch.delenv('STEM_LIBRARY_ROOT', raising=False)
    monkeypatch.setenv('STEM_TUTOR_VAULT', str(vault))
    monkeypatch.setenv('STEM_EXTRACT_ROOT', str(tmp_path / 'Work'))
    monkeypatch.setenv('STEM_LIBRARY_CACHE', str(tmp_path / 'reader-cache'))
    monkeypatch.setenv('STEM_LIBRARY_SPECS', str(vault / '.tutor/packs/v1/specs'))
    return extraction(), vault


def create(ex, name='fresh', **changes):
    options = dict(provider='codex', scope='questions', official_qid=QID,
                   source_pages=SELECTORS, codex_stop_remaining=40)
    course = changes.pop('course', 'P2'); options.update(changes)
    return ex.create(name, course, **options)


def graph_context():
    graph = library_assets.read_json('build/out/specs/P2/graph.json')
    return {'P2': ({r['id'] for r in graph['subtopics']},
                   {r['id']: r['subtopic'] for r in graph['kcs']})}


def test_owned_collector_keeps_caie_and_encoded_byte_contract():
    graphs = {'9702': ({'9702-1', '9702-2'}, {'9702-1.1': '9702-1'})}
    row = dict(official_qid='9702_s24_22_q1', part='a',
               syllabus=['9702-2', '9702-1', '9702-1'], kcs=['9702-1.1', '9702-1.1'])
    assert keys.question_key('9702', row, graphs) == '["9702","9702_s24_22_q1","a",["9702-1","9702-2"],["9702-1.1"]]'
    assert keys.encoded({'汉字': ['β', 1], 'a': True}) == '{"a":true,"汉字":["β",1]}'
    assert keys.question_key('9702', {**row, 'syllabus': ['9702-2']}, graphs) is None
    assert keys.question_key('9702', {**row, 'official_qid': QID}, graphs) is None


@pytest.mark.parametrize('part', PARTS)
def test_exact_nested_part_identity_and_course_survive_public_dispatch(part):
    source = {'qid': QID, 'part': part}
    assert topicals.identity({'source': source}) == QID + ':' + part
    assert topicals.official_course(source) == 'P2'


def test_exact_fresh_p2_launch_binds_three_safe_ids_before_outputs(tmp_path, monkeypatch):
    ex, _ = fresh_inputs(tmp_path, monkeypatch)
    state = create(ex, source_pages=list(reversed(SELECTORS)))
    assert state['selected_item_scope']['record_ids'] == IDS
    assert state['selected_item_scope']['assessed_parts'] == dict(zip(IDS, PARTS))
    assert state['selected_item_scope']['origin'] == 'fresh_native_ial_v1'
    assert state['initial_native_question'] == dict(version=1, official_qid=QID, part='',
                                                   source_pages=SELECTORS, job_name='fresh')
    assert [s['selected_page_numbers'] for s in state['sources']] == PAGES
    assert state['jobs'] == {} and state['stage'] == 'inventoried'
    assert not Path(state['candidate']).parent.exists()


@pytest.mark.parametrize('part', PARTS)
def test_owned_collector_accepts_exact_p2_raw_and_bank_with_original_bytes(tmp_path, part):
    lib = source_fixture(tmp_path)
    q, m = regions(lib, QP, [2]), regions(lib, MS, [7])
    row = dict(official_qid=QID, part=part, syllabus=['P2-1'], kcs=['P2-1.1'],
               regions=q, mark_scheme_regions=m)
    item = dict(kcs=['P2-1.1'], source=dict(qid=QID, part=part,
                extraction_regions=q, mark_scheme_regions=m))
    expected = '["P2","' + QID + '","' + part + '",["P2-1"],["P2-1.1"]]'
    assert keys.question_key('P2', row, graph_context(), lib) == expected
    assert keys.question_key('P2', row, graph_context(), lib, bank_item=item) == expected


def p2_case(tmp_path, monkeypatch, *, whole=False, with_caie=False):
    """Real registered sources/graph, synthetic tasks, private media and review."""
    from PIL import Image
    ex, vault = fresh_inputs(tmp_path, monkeypatch, with_caie=with_caie)
    create(ex); state = ex.plan('fresh'); path = Path(state['candidate'])
    path.parent.mkdir(parents=True)
    lib = AssetLibrary(vault); rows = []
    for index, (part, identifier) in enumerate(zip(PARTS, IDS)):
        prompt, rubric = f'prompt-{index}.png', f'rubric-{index}.png'
        Image.new('RGB', (20, 20), (50 + index * 50, 0, 0)).save(path.parent / prompt)
        Image.new('RGB', (20, 20), (0, 50 + index * 50, 0)).save(path.parent / rubric)
        scheme = [{'point': f'Synthetic schema sentinel for {part}; no official rubric.'}]
        if whole:
            scheme[0]['whole_rubric'] = {'version': 1, 'max_marks': 1, 'media': [rubric]}
        rows.append(dict(id=identifier, official_qid=QID, part=part, kind='structured',
            complete=True, uncertainty=[], stem=f'Synthetic {part} schema sentinel; no native task.',
            answer=f'Synthetic answer {part}.', marks=1, scheme=scheme,
            regions=regions(lib, QP, [2]), mark_scheme_regions=regions(lib, MS, [7]),
            syllabus=['P2-1'], kcs=['P2-1.1'], prerequisites=[],
            media=[prompt, rubric], question_media=[prompt], mark_scheme_media=[rubric]))
    data = dict(questions=rows, diagrams=[], selected_item_scope=state['selected_item_scope'],
                source_coverage=[dict(source_id=s['id'], source_sha256=s['sha256'],
                    inspected_pages=s['selected_page_numbers'], no_relevant_content=False, reason='')
                    for s in state['sources']])
    def save():
        path.write_text(json.dumps(data))
        (ex.job_dir('fresh') / 'review.json').write_text(json.dumps(dict(
            candidate_sha256=ex.digest(path), verdict='pass', findings=[],
            inspected_images=[ex.digest(path.parent / media) for row in rows for media in row['media']])))
    with ex.state_lock('fresh') as current:
        for role in ('extract', 'review'):
            current['jobs'][role]['exit'] = 0
    save()
    return ex, path, data, vault, save


def prepared_case(tmp_path, monkeypatch, *, whole=False):
    ex, path, data, vault, save = p2_case(tmp_path, monkeypatch, whole=whole)
    checked = ex.check('fresh'); assert checked['stage'] == 'reviewed', checked['problems']
    ex.register('fresh'); batch = tmp_path / 'batch'; ex.prepare_publication('fresh', batch)
    return ex, path, data, vault, save, batch


@pytest.mark.parametrize('qid,part', [(QID, p) for p in ['', 'a', 'ai', 'aii', '(a)(i)', 'A(i)', 'a(ii) ', None]] +
    [(QID.replace('q1', 'q2'), 'b'), (QID.replace('P2_', 'P1_'), 'b'),
     (QID.replace('WMA12', 'WMA11'), 'b'), (QID.replace('2019-06', '2019-01'), 'b'),
     (QID.replace('_01_q', '_02_q'), 'b'), (QID.lower(), 'b'), (QID + ':a(i)', 'a(i)')])
def test_malformed_or_unsupported_ial_never_falls_back_to_caie(qid, part):
    source = dict(qid=qid, part=part, ref='9702 Jun 2023 P22 Q2(a)')
    assert topicals.identity({'source': source}) is None
    assert topicals.official_course(source) is None


def test_neutral_descriptors_are_independent_and_p1_adapter_is_unchanged():
    from tutorlib import ial_identity as ial, ial_p1_identity as p1
    first = ial.ial_question(QID); first['part_suffixes']['a(i)'] = 'bad'; first['qp']['sha256'] = 'bad'
    assert ial.ial_question(QID)['part_suffixes']['a(i)'] == 'a-i'
    assert ial.ial_assessed(QID, '') is None and ial.ial_question(QID)['part'] == ''
    for question in (1, 2, 3):
        qid = f'P1_pearson-edexcel-ial_WMA11_2019-01_01_q{question}'
        assert ial.ial_question(qid) == p1.p1_question(qid)
        for part in ('', 'a', 'b', 'a(i)', None):
            assert ial.ial_assessed(qid, part) == p1.p1_pilot(qid, part)
            assert ial.ial_identity(qid, part) == p1.p1_identity(qid, part)
    assert p1.p1_question(QID) is None and p1.p1_pilot(QID, 'a(i)') is None


@pytest.mark.parametrize('fault', ['missing-qp', 'cover-qp', 'extra-qp', 'missing-ms', 'extra-ms',
    'order-ms', 'bool-page', 'float-page', 'negative-page', 'role', 'hash', 'empty', 'not-list',
    'box-bool', 'box-nan', 'box-inf', 'box-order', 'box-outside', 'box-shape', 'course',
    'catalog-course', 'catalog-kind', 'catalog-path', 'catalog-hash', 'bytes', 'missing'])
def test_p2_source_pins_reject_role_page_geometry_catalog_and_byte_drift(tmp_path, fault):
    from tutorlib.ial_identity import validate_ial_sources
    lib = source_fixture(tmp_path); q = regions(lib, QP, [2]); m = regions(lib, MS, [7]); course = 'P2'
    if fault == 'missing-qp': q = []
    if fault == 'cover-qp': q[0]['page'] = 1
    if fault == 'extra-qp': q.append({**q[0], 'page': 3})
    if fault == 'missing-ms': m[0]['page'] = 6
    if fault == 'extra-ms': m.append({**m[0], 'page': 8})
    if fault == 'order-ms': m += regions(lib, MS, [3])
    if fault in ('bool-page', 'float-page', 'negative-page'): q[0]['page'] = {'bool-page': True, 'float-page': 2.0, 'negative-page': -2}[fault]
    if fault == 'role': q, m = m, q
    if fault == 'hash': q[0]['source_sha256'] = '0' * 64
    if fault == 'empty': q = None
    if fault == 'not-list': q = tuple(q)
    if fault.startswith('box-'):
        q[0]['box'] = {'bool': [False, 0, 1, 1], 'nan': [0, 0, float('nan'), 1],
            'inf': [0, 0, float('inf'), 1], 'order': [1, 0, 0, 1], 'outside': [-1, 0, 1, 1],
            'shape': [0, 0, 1]}[fault[4:]]
    if fault == 'course': course = 'P1'
    if fault.startswith('catalog-'):
        key = fault[8:]; key = 'sha256' if key == 'hash' else key
        path = tmp_path / 'Library/catalog.json'; data = json.loads(path.read_text())
        data['assets'][QP[6:]][key] = {'course': 'P1', 'kind': 'Diagrams', 'path': 'Library/wrong.pdf', 'sha256': '0' * 64}[key]
        path.write_text(json.dumps(data)); lib = AssetLibrary(tmp_path)
    if fault == 'bytes': (tmp_path / lib.record(QP)['path']).write_bytes(b'corrupt')
    if fault == 'missing': (tmp_path / lib.record(MS)['path']).unlink()
    with pytest.raises(ValueError): validate_ial_sources(QID, 'a(i)', course, q, m, lib)


@pytest.mark.parametrize('part', PARTS)
def test_each_part_requires_task_and_rubric_page_with_optional_general_context(tmp_path, part):
    from tutorlib.ial_identity import validate_ial_sources
    lib = source_fixture(tmp_path)
    for context in ([], [1, 2, 3, 4, 5, 6]):
        validate_ial_sources(QID, part, 'P2', regions(lib, QP, [2]), regions(lib, MS, context + [7]), lib)


def test_fresh_read_plan_resume_cli_and_crop_boundaries(tmp_path, monkeypatch, capsys):
    ex, vault = fresh_inputs(tmp_path, monkeypatch); state = create(ex)
    before = (ex.job_dir('fresh') / 'state.json').read_bytes()
    assert ex.resume('fresh') == state and ex.inventory('fresh') == state
    assert (ex.job_dir('fresh') / 'state.json').read_bytes() == before
    planned = ex.plan('fresh')
    for role in ('extract', 'review'):
        contract = json.loads(ex._prompt(planned, role).split('JOB CONTRACT:\n')[1])
        assert contract['course_graph_sha256'] == state['focus_graph_sha256']
        assert not contract.get('previous_candidate')
        for ref, pages, selector in zip((QP, MS), PAGES, ('1-2', '1-7')):
            read = contract['bounded_read_plan'][ref]
            assert shlex.split(read['text'])[-4:] == ['text', ref, '--pages', selector]
            assert [r['page'] for r in read['render']] == pages
    assert ex.main(['new', 'cli', '--course', 'P2', '--scope', 'questions', '--provider', 'codex',
        '--official-qid', QID, '--source-pages', SELECTORS[0], '--source-pages', SELECTORS[1]]) == 0
    assert json.loads(capsys.readouterr().out)['selected_item_scope']['record_ids'] == IDS
    def deny(*a, **kw): raise AssertionError('out-of-scope read reached renderer')
    monkeypatch.setattr(ex.library, 'render', deny)
    for ref, page in ((QP, 3), (MS, 8)):
        with pytest.raises(ValueError): ex.crop('fresh', ref, page, '0,0,1,1', 'bad.png')
    assert not Path(state['candidate']).parent.exists()
    facts = ex.graph('fresh', kc_id='P2-1.1')
    assert facts['results'][0]['level'] == 'P2'
    assert facts['results'][0]['subtopic']['id'] == 'P2-1'


@pytest.mark.parametrize('change', [{'official_qid': QID.replace('q1', 'q2')}, {'course': 'P1'},
    {'scope': 'both'}, {'scope': 'diagrams'}, {'official_qid': QID + ':a(i)'},
    {'source_pages': [QP + '=2', SELECTORS[1]]}, {'source_pages': [SELECTORS[0], MS + '=1-8']},
    {'source_pages': [QP + '=1-7', MS + '=1-2']}, {'source_pages': SELECTORS[:1]},
    {'source_pages': [SELECTORS[0], SELECTORS[0]]}, {'sources': [QP]}, {'pages': '1-7'}])
def test_wrong_launch_scope_or_sources_creates_no_state_or_output(tmp_path, monkeypatch, change):
    ex, _ = fresh_inputs(tmp_path, monkeypatch)
    with pytest.raises(ValueError): create(ex, **change)
    assert not (ex.job_dir('fresh') / 'state.json').exists()
    assert not (ex.work_root() / 'Candidates').exists()


@pytest.mark.parametrize('fault', ['parts', 'ids', 'origin', 'marker', 'version', 'graph', 'pages',
    'bool-page', 'path', 'hash', 'status', 'ocr', 'focus', 'rebase', 'references', 'completed'])
def test_initial_binding_rechecked_before_resume_prompt_and_worker(tmp_path, monkeypatch, fault):
    ex, _ = fresh_inputs(tmp_path, monkeypatch); create(ex); state = ex.plan('fresh')
    if fault == 'parts': state['selected_item_scope']['assessed_parts'][IDS[0]] = 'ai'
    if fault == 'ids': state['selected_item_scope']['record_ids'].pop()
    if fault == 'origin': state['selected_item_scope']['origin'] = 'repair'
    if fault == 'marker': state.pop('initial_native_question')
    if fault == 'version': state['initial_native_question']['version'] = True
    if fault == 'graph': state['focus_graph_sha256'] = '0' * 64
    if fault == 'pages': state['sources'][0]['selected_page_numbers'].append(3)
    if fault == 'bool-page': state['sources'][0]['selected_page_numbers'][0] = True
    if fault == 'path': state['sources'][0]['path'] = str(tmp_path / 'other.pdf')
    if fault == 'hash': state['sources'][0]['sha256'] = '0' * 64
    if fault == 'status': state['sources'][0]['status'] = 'pending_ocr'
    if fault == 'ocr': state['sources'][0]['ocr'] = {'synthetic': True}
    history = {'focus': 'focus_history', 'rebase': 'source_rebase_history',
               'references': 'reference_source_history', 'completed': 'completed_scope_history'}
    if fault in history: state[history[fault]] = []
    path = ex.job_dir('fresh') / 'state.json'; path.write_text(json.dumps(state)); before = path.read_bytes()
    def deny(*a, **kw): raise AssertionError('bad binding reached provider')
    monkeypatch.setattr(ex.worker_timeout, 'run_captured', deny)
    for call in (lambda: ex.resume('fresh'), lambda: ex.plan('fresh'), lambda: ex._prompt(state, 'review'),
                 lambda: ex.run('fresh', weekly_remaining=90), lambda: ex._worker('fresh', 'extract')):
        with pytest.raises(ValueError): call()
        assert path.read_bytes() == before
    assert not Path(state['candidate']).parent.exists()


@pytest.mark.parametrize('fault', ['retarget', 'directory-alias', 'file-alias', 'hardlink', 'name'])
def test_managed_output_rejects_aliases_before_every_effect(tmp_path, monkeypatch, fault):
    ex, _ = fresh_inputs(tmp_path, monkeypatch); create(ex); state = ex.plan('fresh')
    old = tmp_path / 'unknown/candidate.json'; old.parent.mkdir(); old.write_bytes(b'Preserve unknown bytes.')
    owned = Path(state['candidate'])
    if fault in ('retarget', 'name'):
        state['candidate'] = str(old)
        if fault == 'name': state['name'] = 'unknown'
    elif fault == 'directory-alias':
        owned.parent.parent.mkdir(parents=True); owned.parent.symlink_to(old.parent, target_is_directory=True)
    else:
        owned.parent.mkdir(parents=True)
        if fault == 'file-alias': owned.symlink_to(old)
        else: owned.hardlink_to(old)
    path = ex.job_dir('fresh') / 'state.json'; path.write_text(json.dumps(state)); before = path.read_bytes()
    def deny(*a, **kw): raise AssertionError('unowned output reached provider/renderer')
    monkeypatch.setattr(ex.worker_timeout, 'run_captured', deny)
    monkeypatch.setattr(ex.library, 'render', deny)
    for call in (lambda: ex.resume('fresh'), lambda: ex.plan('fresh'),
        lambda: ex.configure('fresh', 'sentinel', codex_stop_remaining=40),
        lambda: ex.graph('fresh', kc_id='P2-1.1'), lambda: ex.run('fresh', weekly_remaining=90),
        lambda: ex._worker('fresh', 'extract'), lambda: ex.worker_command(state, 'extract'),
        lambda: ex.crop('fresh', QP, 2, '0,0,1,1', 'new.png'), lambda: ex.check('fresh'),
        lambda: ex.register('fresh'), lambda: ex.prepare_publication('fresh', tmp_path / 'batch'),
        lambda: ex.publish('fresh', tmp_path / 'batch')):
        with pytest.raises(ValueError): call()
        assert path.read_bytes() == before and old.read_bytes() == b'Preserve unknown bytes.'
    assert not (tmp_path / 'batch').exists()


@pytest.mark.parametrize('operation', ['focus', 'evidence', 'references', 'next', 'ocr', 'adopt'])
def test_fresh_p2_cannot_adopt_focus_rebind_or_inherit_approval(tmp_path, monkeypatch, operation):
    ex, _ = fresh_inputs(tmp_path, monkeypatch); state = create(ex)
    path = ex.job_dir('fresh') / 'state.json'; before = path.read_bytes()
    actions = {'focus': lambda: ex.focus('fresh', QID, 'sentinel'),
        'evidence': lambda: ex.evidence_sources('fresh', SELECTORS, 'sentinel'),
        'references': lambda: ex.reference_sources('fresh', SELECTORS, 'sentinel', 'sentinel'),
        'next': lambda: ex.next_question('fresh', QID, 'sentinel'),
        'ocr': lambda: ex.enable_ocr('fresh', QP), 'adopt': lambda: create(ex)}
    with pytest.raises(ValueError): actions[operation]()
    assert path.read_bytes() == before and not Path(state['candidate']).parent.exists()
    assert state['teaching_approved'] is False


@pytest.mark.parametrize('fault', ['missing', 'duplicate', 'part', 'aggregate', 'empty', 'qid', 'id',
    'coverage-order', 'coverage-part', 'coverage-claim', 'mcq', 'page', 'hash', 'media-public'])
def test_candidate_requires_three_exact_source_bound_structured_records(tmp_path, monkeypatch, fault):
    ex, _, data, _, save = p2_case(tmp_path, monkeypatch)
    rows = data['questions']
    if fault == 'missing': rows.pop()
    if fault == 'duplicate': rows.append(copy.deepcopy(rows[0]))
    if fault == 'part': rows[0]['part'] = 'ai'
    if fault == 'aggregate': rows[0]['part'] = 'a'
    if fault == 'empty': rows[0]['part'] = ''
    if fault == 'qid': rows[0]['official_qid'] = QID.replace('q1', 'q2')
    if fault == 'id': rows[0]['id'] = 'native-' + QID + '-a(i)'
    if fault == 'coverage-order': data['source_coverage'][0]['inspected_pages'].reverse()
    if fault == 'coverage-part': data['selected_item_scope']['assessed_parts'][IDS[0]] = 'b'
    if fault == 'coverage-claim': data['selected_item_scope']['coverage_claim'] = 'all paper'
    if fault == 'mcq': rows[0]['kind'] = 'mcq'; rows[0]['answer'] = 'A'
    if fault == 'page': rows[0]['mark_scheme_regions'][0]['page'] = 6
    if fault == 'hash': rows[0]['regions'][0]['source_sha256'] = '0' * 64
    if fault == 'media-public': rows[0]['question_media'].append(rows[0]['mark_scheme_media'][0])
    save()
    checked = ex.check('fresh'); assert checked['stage'] == 'pending', fault
    with pytest.raises(ValueError): ex.register('fresh')


@pytest.mark.parametrize('fault', ['missing', 'duplicate', 'part', 'qid', 'kind', 'stem', 'scheme',
    'source-page', 'source-role', 'source-hash', 'kcs', 'private-public'])
def test_publication_requires_bijection_and_exact_reviewed_content(tmp_path, monkeypatch, fault):
    ex, _, _, vault, _, batch = prepared_case(tmp_path, monkeypatch, whole=True)
    bank = json.loads((batch / 'bank.json').read_text()); rows = bank['items']; item = rows[0]
    if fault == 'missing': rows.pop()
    if fault == 'duplicate': rows.append(copy.deepcopy(item))
    if fault == 'part': item['source']['part'] = 'ai'
    if fault == 'qid': item['source']['qid'] = QID.replace('q1', 'q2')
    if fault == 'kind': item['kind'] = 'mcq'
    if fault == 'stem': item['stem'] = 'unreviewed'
    if fault == 'scheme': item['scheme'][0]['point'] = 'unreviewed'
    if fault == 'source-page': item['source']['extraction_regions'][0]['page'] = 1
    if fault == 'source-role': item['source']['extraction_regions'] = item['source']['mark_scheme_regions']
    if fault == 'source-hash': item['source']['mark_scheme_regions'][0]['source_sha256'] = '0' * 64
    if fault == 'kcs': item['kcs'] = ['P2-2.1']
    if fault == 'private-public': item['images'] += item['scheme'][0]['whole_rubric']['media']
    (batch / 'bank.json').write_text(json.dumps(bank))
    with pytest.raises(ValueError): ex.publish('fresh', batch)
    assert not (vault / '.tutor/topicals/CURRENT').exists()


@pytest.mark.parametrize('whole', [False, True])
def test_disposable_lifecycle_importer_preserves_all_parts_ids_source_and_graph(tmp_path, monkeypatch, whole):
    from tutorlib import packs, store
    ex, path, data, vault, _, batch = prepared_case(tmp_path, monkeypatch, whole=whole)
    before = path.read_bytes(); ex.publish('fresh', batch)
    runtime = packs.Packs(store.Vault(vault)); assert not runtime.topical_errors
    assert len(runtime.topicals.items) == 3
    assert len([k for k in runtime.kcs.values() if k['spec'] == 'P2']) == 19
    assert len([c for c in runtime.subtopics.values() if c['spec'] == 'P2']) == 8
    assert {runtime.kcs[k]['level'] for row in data['questions'] for k in row['kcs']} == {'P2'}
    for item, row in zip(runtime.topicals.items, data['questions']):
        context = ex.hashlib.sha256(json.dumps(row, sort_keys=True).encode()).hexdigest()[:12]
        assert item['id'] == 'extracted-' + QID + '-' + context
        assert topicals.identity(item) == QID + ':' + row['part']
        assert item['source']['extraction_regions'] == row['regions']
        assert item['source']['mark_scheme_regions'] == row['mark_scheme_regions']
        assert not any(ref in item['images'] for ref in item.get('scheme', [{}])[0].get('whole_rubric', {}).get('media', []))
        if whole:
            private = topicals.whole_rubric_media(item, vault)
            assert len(private) == 1 and private[0]['reference'] not in item['images']
        else: assert item['scheme'] == row['scheme']
    assert path.read_bytes() == before
    # Re-publishing without a new source review cannot silently replace history.
    with pytest.raises(ValueError, match='already active'):
        ex.prepare_publication('fresh', tmp_path / 'again')
    assert not (tmp_path / 'again').exists()


@pytest.mark.parametrize('fault', ['level-as', 'level-p1', 'spec', 'parent', 'revision'])
def test_runtime_admits_only_real_p2_levels_parents_and_revision(tmp_path, monkeypatch, fault):
    from tutorlib import packs, store
    ex, _, _, vault, _, batch = prepared_case(tmp_path, monkeypatch)
    ex.publish('fresh', batch); runtime = packs.Packs(store.Vault(vault))
    bank = json.loads((batch / 'bank.json').read_text())
    if fault in ('level-as', 'level-p1'): runtime.kcs['P2-1.1']['level'] = {'level-as': 'AS', 'level-p1': 'P1'}[fault]
    if fault == 'spec': runtime.kcs['P2-1.1']['spec'] = 'P1'
    if fault == 'parent': runtime.kcs['P2-1.1']['subtopic'] = 'P2-2'
    if fault == 'revision': bank['syllabus_versions']['P2'] = 'wrong'
    with pytest.raises(ValueError): topicals.validate_bank(bank, runtime, vault)


@pytest.mark.parametrize('fault', ['part', 'course', 'qid', 'hash', 'page', 'role', 'context', 'bank-kcs', 'no-library'])
def test_owned_keys_fail_closed_for_unbound_or_wrong_p2_context(tmp_path, fault):
    lib = source_fixture(tmp_path); row = dict(official_qid=QID, part='a(i)', syllabus=['P2-1'],
        kcs=['P2-1.1'], regions=regions(lib, QP, [2]), mark_scheme_regions=regions(lib, MS, [7]))
    item = dict(kcs=row['kcs'][:], source=dict(qid=QID, part='a(i)', extraction_regions=copy.deepcopy(row['regions']),
                mark_scheme_regions=copy.deepcopy(row['mark_scheme_regions'])))
    course = 'P2'
    if fault == 'part': row['part'] = 'ai'; item['source']['part'] = 'ai'
    if fault == 'course': course = 'P1'
    if fault == 'qid': row['official_qid'] = QID.replace('q1', 'q2'); item['source']['qid'] = row['official_qid']
    if fault == 'hash': row['regions'][0]['source_sha256'] = '0' * 64; item['source']['extraction_regions'] = row['regions']
    if fault == 'page': row['mark_scheme_regions'][0]['page'] = 6; item['source']['mark_scheme_regions'] = row['mark_scheme_regions']
    if fault == 'role': row['regions'] = row['mark_scheme_regions']; item['source']['extraction_regions'] = row['regions']
    if fault == 'context': row['syllabus'] = ['P2-2']
    if fault == 'bank-kcs': item['kcs'] = ['P2-2.1']
    if fault == 'no-library': lib = None
    if fault != 'bank-kcs': assert keys.question_key(course, row, graph_context(), lib) is None
    assert keys.question_key(course, row, graph_context(), lib, bank_item=item) is None


@pytest.mark.parametrize('mode', ['topical', 'long'])
@pytest.mark.parametrize('whole', [False, True])
def test_normal_topical_and_long_answer_grade_every_part_without_sibling_disclosure(tmp_path, monkeypatch, mode, whole):
    from tutorlib import session, store
    ex, _, data, vault, save = p2_case(tmp_path, monkeypatch, whole=whole)
    # Distinct genuine KCs make the normal Long route select each schema part.
    for index, row in enumerate(data['questions'], 1):
        row['kcs'] = [f'P2-1.{index}']
    save(); ex.register('fresh'); batch = tmp_path / 'batch'
    ex.prepare_publication('fresh', batch); ex.publish('fresh', batch)
    tutor = session.Tutor(store.Vault(vault))
    options = {'topical_count': 3, 'topical_types': ['structured']} if mode == 'topical' else {}
    focus = ['P2-1'] if mode == 'topical' else ['P2-1.1', 'P2-1.2', 'P2-1.3']
    started = tutor.start(mode, focus=focus, **options)
    assert 'error' not in started, started
    bank = json.loads((batch / 'bank.json').read_text())
    by_part = {i['source']['part']: i for i in bank['items']}
    private = {i['source']['part']: i['scheme'][0].get('whole_rubric', {}).get('media', []) for i in bank['items']}
    seen = set(); previous_ticket = None
    for _ in range(20):
        activity = tutor.next()
        if activity['activity'] == 'end': break
        assert activity['activity'] == 'questions', activity
        view = activity['items'][0]; n = view['n']
        pending = tutor.session['presented'][str(n)]
        part = pending['inst']['source']['part']; seen.add(part)
        assert part in PARTS and pending['inst']['id'] == by_part[part]['id']
        assert not any(ref in json.dumps(view) for names in private.values() for ref in names)
        assert 'scheme' not in view and 'answer' not in view
        if whole:
            assert tutor.whole_rubric(n, '')['error']
            work = 'My actual synthetic written attempt for ' + part
            out = tutor.whole_rubric(n, work)
            assert out.get('ticket'), out
            assert out['media'] == private[part]
            assert not any(ref in json.dumps(out) for sibling, names in private.items() if sibling != part for ref in names)
            assert tutor.whole_rubric(n + 100, work).get('error')
            if previous_ticket:
                wrong = tutor.answer(f'{n} = {work}', manual_awards={n: {'earned_marks': 1, 'ticket': previous_ticket}})
                assert wrong['results'][0].get('error'), wrong
            wrong_work = tutor.answer(f'{n} = Changed attempt', manual_awards={n: {'earned_marks': 1, 'ticket': out['ticket']}})
            assert wrong_work['results'][0].get('error'), wrong_work
            out = tutor.whole_rubric(n, work)  # changed work invalidated the prior capability
            assert out.get('ticket'), out
            result = tutor.answer(f'{n} = {work}', manual_awards={n: {'earned_marks': 1, 'ticket': out['ticket']}})
            previous_ticket = out['ticket']
        else:
            result = tutor.answer(f'{n} pts=1')
        feedback = result['results'][0]
        assert not feedback.get('error'), feedback
        event = next(e for e in tutor.vault.events() if e.get('id') == feedback['event'])
        assert event['grade']['score'] == 1
        if whole: assert event['human_award']['marker'] == 'human'
        if seen == set(PARTS): break
    assert seen == set(PARTS)


@pytest.mark.parametrize('fault', ['sibling-private', 'source-bytes', 'source-page', 'source-hash', 'empty-media-source'])
def test_whole_private_part_provenance_and_originals_reverified_on_disclosure(tmp_path, monkeypatch, fault):
    from tutorlib import packs, store
    ex, _, _, vault, _, batch = prepared_case(tmp_path, monkeypatch, whole=True)
    ex.publish('fresh', batch); runtime = packs.Packs(store.Vault(vault))
    first, sibling = copy.deepcopy(runtime.topicals.items[:2])
    if fault == 'sibling-private': first['scheme'][0]['whole_rubric']['media'] = sibling['scheme'][0]['whole_rubric']['media']
    if fault in ('source-bytes', 'empty-media-source'):
        if fault == 'empty-media-source': first['scheme'][0]['whole_rubric']['media'] = []
        lib = AssetLibrary(vault); (vault / lib.record(MS)['path']).write_bytes(b'corrupt source')
    if fault == 'source-page': first['source']['mark_scheme_regions'][0]['page'] = 6
    if fault == 'source-hash': first['source']['extraction_regions'][0]['source_sha256'] = '0' * 64
    with pytest.raises(ValueError): topicals.whole_rubric_media(first, vault)


def test_fresh_stop40_two_failure_hold_and_repair_feedback_keep_three_parts(tmp_path, monkeypatch):
    ex, path, data, _, _ = p2_case(tmp_path, monkeypatch)
    before = path.read_bytes(); initial = ex.load('fresh')
    # Leave only the successful maker; fake reviewer returns bounded source doubt.
    with ex.state_lock('fresh') as current:
        current['jobs']['review'] = {'provider': 'codex'}
        current['jobs']['extract'].update(finished='schema sentinel', output_sha256=ex.digest(path))
    fake = tmp_path / 'fake-only-provider'
    fake.write_text('''#!/usr/bin/env python3
import hashlib,json,os,sys
from pathlib import Path
contract=json.loads(sys.argv[-1].split('JOB CONTRACT:\\n',1)[1])
output=Path(os.environ['EXTRACT_OUTPUT'])
if os.environ['EXTRACT_ROLE']=='review':
 output.write_text(json.dumps({'candidate_sha256':hashlib.sha256(Path(contract['candidate']).read_bytes()).hexdigest(),
 'verdict':'pending','findings':['Synthetic source doubt, preserve all three parts.'],'inspected_images':[]}))
else:
 output.write_bytes(Path(contract['previous_candidate']).read_bytes())
''')
    fake.chmod(0o755); monkeypatch.setenv('STEM_EXTRACT_CODEX', str(fake))
    with pytest.raises(ValueError, match='40.0% launch boundary'):
        ex.run('fresh', weekly_remaining=40, wait=True)
    assert path.read_bytes() == before
    ex.run('fresh', weekly_remaining=90, wait=True)
    reviewed = ex.load('fresh')
    assert len(reviewed['reliability_failures']['1']['review']) == 1
    ex.run('fresh', weekly_remaining=90, wait=True, retry='extract')
    repaired = ex.resume('fresh'); assert path.read_bytes() == before
    assert repaired['selected_item_scope']['record_ids'] == IDS
    assert repaired['selected_item_scope']['assessed_parts'] == dict(zip(IDS, PARTS))
    assert repaired['initial_native_question'] == initial['initial_native_question']
    assert repaired['reliability_failures'] == reviewed['reliability_failures']
    contract = json.loads((ex.job_dir('fresh') / 'extract.prompt.txt').read_text().split('JOB CONTRACT:\n')[1])
    assert contract['review_feedback']['findings'] == ['Synthetic source doubt, preserve all three parts.']
    assert Path(repaired['previous_candidate']).read_bytes() == before
    with ex.state_lock('fresh') as current:
        current['reliability_failures']['1']['extract'] = [{'issues': ['one']}, {'issues': ['two']}]
    state_path = ex.job_dir('fresh') / 'state.json'; state_before = state_path.read_bytes()
    with pytest.raises(ValueError, match='paused after 2 failures'):
        ex.run('fresh', weekly_remaining=90, retry='extract')
    assert state_path.read_bytes() == state_before and path.read_bytes() == before


def test_p2_publication_preserves_preexisting_bank_row_bytes_and_ids(tmp_path, monkeypatch):
    from tutorlib import packs, store
    ex, _, _, vault, _ = p2_case(tmp_path, monkeypatch, with_caie=True)
    runtime = packs.Packs(store.Vault(vault))
    prior = dict(id='preserved-synthetic-caie', kind='structured', marks=1,
        stem='Preserved synthetic schema task.', answer='Preserved synthetic answer.',
        scheme=[{'point': 'Preserved synthetic schema point.'}], kcs=['9702-2.1.1'], images=[],
        source=dict(type='past', qid='9702_s24_22_q99', part='a'),
        topical=dict(reviewed=True, chapters=['9702-2.1'], requires=['9702-2.1'], support={},
                     revision=runtime.syllabus_versions['9702']))
    seed = tmp_path / 'seed'; seed.mkdir()
    (seed / 'bank.json').write_text(json.dumps(dict(format_version=1,
        syllabus_versions={'9702': runtime.syllabus_versions['9702']}, items=[prior])))
    # The real importer owns activation even for this disposable schema bank.
    import topicals as importer
    importer.publish(seed, vault, expected_current=None)
    _, _, active_before = ex._active_topical_bank(vault)
    old_bytes = json.dumps(active_before['items'], sort_keys=True).encode()
    ex.register('fresh'); batch = tmp_path / 'additive'
    prepared = ex.prepare_publication('fresh', batch)
    assert prepared['extraction']['preserved_items'] == 1 and prepared['extraction']['added_items'] == 3
    ex.publish('fresh', batch)
    _, _, active_after = ex._active_topical_bank(vault)
    old = [row for row in active_after['items'] if row['id'] == prior['id']]
    assert json.dumps(old, sort_keys=True).encode() == old_bytes
    assert len(active_after['items']) == 4


def test_owned_identity_and_collector_import_without_source_catalog_or_graph_reads(monkeypatch):
    import importlib
    from tutorlib import ial_identity
    def deny(*a, **kw): raise AssertionError('import attempted source/catalog/graph I/O')
    with monkeypatch.context() as patch:
        for name in ('read', 'record', 'records', 'resolve'):
            patch.setattr(AssetLibrary, name, deny)
        patch.setattr(Path, 'read_bytes', deny); patch.setattr(Path, 'read_text', deny)
        importlib.reload(ial_identity)
        importlib.reload(keys)
    assert keys.context('P2', ['P2-1'], ['P2-1.1'], graph_context()) == [['P2-1'], ['P2-1.1']]


def test_legacy_p2_candidate_cannot_adopt_exact_q1_identity_or_prior_approval(tmp_path, monkeypatch):
    ex, path, data, vault, save = p2_case(tmp_path, monkeypatch)
    # Valid original source pins and even a synthetic pass review cannot turn a
    # legacy manager job into the fresh whole-question contract.
    state = ex.load('fresh'); state.pop('initial_native_question'); state.pop('selected_item_scope')
    data.pop('selected_item_scope'); save()
    state_path = ex.job_dir('fresh') / 'state.json'; state_path.write_text(json.dumps(state))
    before = state_path.read_bytes(); candidate_before = path.read_bytes()
    catalog_before = (vault / 'Library/catalog.json').read_bytes()
    with pytest.raises(ValueError, match='fresh'):
        ex._candidate_problems(state)
    for call in (lambda: ex.check('fresh'), lambda: ex.register('fresh'),
                 lambda: ex.prepare_publication('fresh', tmp_path / 'batch'),
                 lambda: ex.publish('fresh', tmp_path / 'batch')):
        with pytest.raises(ValueError, match='fresh'): call()
        assert state_path.read_bytes() == before and path.read_bytes() == candidate_before
        assert (vault / 'Library/catalog.json').read_bytes() == catalog_before
    assert not (tmp_path / 'batch').exists()


def test_generic_p2_create_and_inventory_remain_available_without_candidate_admission(tmp_path, monkeypatch):
    ex, _ = fresh_inputs(tmp_path, monkeypatch)
    state = ex.create('generic', 'P2', provider='codex', scope='questions', sources=[QP, MS], pages='1-2')
    assert state['stage'] == 'new' and 'initial_native_question' not in state
    state = ex.inventory('generic')
    assert state['stage'] == 'inventoried' and {s['id'] for s in state['sources']} == {QP, MS}
    assert not Path(state['candidate']).exists()


@pytest.mark.parametrize('whole', [False, True])
@pytest.mark.parametrize('fault', ['same-name', 'copied-bytes'])
def test_sibling_private_media_cannot_enter_any_question_prompt_before_effects(tmp_path, monkeypatch, whole, fault):
    ex, path, data, vault, save = p2_case(tmp_path, monkeypatch, whole=whole)
    first, sibling = data['questions'][:2]; private = sibling['mark_scheme_media'][0]
    if fault == 'same-name':
        first['media'][0] = private; first['question_media'][0] = private
    else:
        (path.parent / first['question_media'][0]).write_bytes((path.parent / private).read_bytes())
    save(); before = path.read_bytes(); catalog = (vault / 'Library/catalog.json').read_bytes()
    checked = ex.check('fresh')
    assert checked['stage'] == 'pending', checked['problems']
    for action in (lambda: ex.register('fresh'), lambda: ex.prepare_publication('fresh', tmp_path / 'blocked'),
                   lambda: ex.publish('fresh', tmp_path / 'blocked')):
        with pytest.raises(ValueError): action()
        assert path.read_bytes() == before and (vault / 'Library/catalog.json').read_bytes() == catalog
    assert not (tmp_path / 'blocked').exists() and not (vault / '.tutor/topicals/CURRENT').exists()


def bank_with_sibling_private_public_media(tmp_path, monkeypatch, *, whole, channel, copied):
    """Disposable adversarial bank with actual immutable source/provenance bindings."""
    from tutorlib.asset_library import write_asset
    ex, _, data, vault, _, batch = prepared_case(tmp_path, monkeypatch, whole=whole)
    bank = json.loads((batch / 'bank.json').read_text()); first, sibling = bank['items'][:2]
    rows = data['questions']; state = ex.load('fresh')
    context = ex.hashlib.sha256(json.dumps(rows[1], sort_keys=True).encode()).hexdigest()[:12]
    private = state['registered_records'][context][rows[1]['mark_scheme_media'][0]]
    reference = private
    if copied:
        lib = AssetLibrary(vault); old = first['images'][0]
        content = lib.read(private); digest = ex.hashlib.sha256(content).hexdigest()
        original = json.loads(lib.read(lib.record(old)['provenance']['sidecars'][0]))
        original['sha256'] = digest
        context = ex.hashlib.sha256(json.dumps(rows[0], sort_keys=True).encode()).hexdigest()[:12]
        reference = f'Library/Courses/P2/Questions/Media/prompt-0-{context}-{digest[:16]}.png'
        sidecar = write_asset(vault, reference + '.json', json.dumps(original).encode(),
                             metadata={'course': 'P2', 'kind': 'Sources/Provenance'})
        write_asset(vault, reference, content, metadata={'course': 'P2', 'kind': 'Questions/Media',
                    'provenance': {'sidecars': [sidecar]}})
    if channel == 'image': first['image'] = reference
    else: first['images'] = [reference]
    return ex, vault, bank


@pytest.mark.parametrize('whole', [False, True])
@pytest.mark.parametrize('channel', ['image', 'images'])
@pytest.mark.parametrize('copied', [False, True])
def test_standalone_bank_and_importer_reject_sibling_private_paths_and_exact_bytes(tmp_path, monkeypatch, whole, channel, copied):
    from tutorlib import packs, store
    ex, vault, bank = bank_with_sibling_private_public_media(tmp_path, monkeypatch, whole=whole,
                                                           channel=channel, copied=copied)
    runtime = packs.Packs(store.Vault(vault))
    with pytest.raises(ValueError): topicals.validate_bank(bank, runtime, vault)
    bad = tmp_path / 'bad-import'; bad.mkdir(); (bad / 'bank.json').write_text(json.dumps(bank))
    before = (vault / 'Library/catalog.json').read_bytes()
    import topicals as importer
    with pytest.raises(ValueError): importer.publish(bad, vault, expected_current=None)
    assert (vault / 'Library/catalog.json').read_bytes() == before
    assert not (vault / '.tutor/topicals/CURRENT').exists()


@pytest.mark.parametrize('whole', [False, True])
@pytest.mark.parametrize('shared', ['public-context', 'private-context'])
def test_shared_public_question_or_private_general_context_remains_valid(tmp_path, monkeypatch, whole, shared):
    from tutorlib import packs, store
    ex, _, data, vault, save = p2_case(tmp_path, monkeypatch, whole=whole)
    first, sibling = data['questions'][:2]
    if shared == 'public-context':
        first['question_media'][0] = sibling['question_media'][0]
        first['media'][0] = sibling['question_media'][0]
    else:
        old = first['mark_scheme_media'][0]; common = sibling['mark_scheme_media'][0]
        first['media'][first['media'].index(old)] = common; first['mark_scheme_media'] = [common]
        if whole: first['scheme'][0]['whole_rubric']['media'] = [common]
    save(); checked = ex.check('fresh'); assert checked['stage'] == 'reviewed', checked['problems']
    ex.register('fresh'); batch = tmp_path / 'shared'; ex.prepare_publication('fresh', batch); ex.publish('fresh', batch)
    runtime = packs.Packs(store.Vault(vault)); assert not runtime.topical_errors
    assert len(runtime.topicals.items) == 3


@pytest.mark.parametrize('fault', ['missing-part', 'duplicate-part', 'audit-job', 'audit-candidate',
    'immutable-job', 'immutable-candidate', 'private-inventory', 'no-public-context'])
def test_runtime_group_and_private_inventory_use_immutable_complete_reviewed_context(tmp_path, monkeypatch, fault):
    from tutorlib import packs, store
    from tutorlib.asset_library import write_asset
    ex, _, _, vault, _, batch = prepared_case(tmp_path, monkeypatch, whole=False)
    bank = json.loads((batch / 'bank.json').read_text()); item = bank['items'][0]
    if fault == 'missing-part': bank['items'].pop()
    if fault == 'duplicate-part': bank['items'].append(copy.deepcopy(item))
    if fault == 'audit-job': item['source']['extraction_job'] = 'editable-bank-only'
    if fault == 'audit-candidate': item['source']['candidate_sha256'] = 'f' * 64
    if fault == 'no-public-context': item['images'] = []
    if fault in ('immutable-job', 'immutable-candidate', 'private-inventory'):
        lib = AssetLibrary(vault)
        public_provenance = json.loads(lib.read(lib.record(item['images'][0])['provenance']['sidecars'][0]))
        names = [*item['images'], *public_provenance['private_media'].values()]
        replacements = {}
        for reference in names:
            old_sidecar = lib.record(reference)['provenance']['sidecars'][0]
            value = json.loads(lib.read(old_sidecar))
            if fault == 'immutable-job': value['extraction_job'] = 'different-immutable-job'
            if fault == 'immutable-candidate': value['review']['candidate_sha256'] = 'f' * 64
            if fault == 'private-inventory': value.pop('private_media')
            replacements[reference] = write_asset(vault, lib.record(reference)['path'] + '.different.json',
                json.dumps(value).encode(), metadata={'course': 'P2', 'kind': 'Sources/Provenance'})
        # Synthetic invalid catalog metadata, in this disposable vault only;
        # sidecar contents still pass real catalog hash verification.
        catalog_path = vault / 'Library/catalog.json'; catalog = json.loads(catalog_path.read_text())
        for record in catalog['assets'].values():
            if record['path'] in replacements:
                record['provenance']['sidecars'] = [replacements[record['path']]]
        catalog_path.write_text(json.dumps(catalog))
        if fault == 'immutable-job': item['source']['extraction_job'] = 'different-immutable-job'
        if fault == 'immutable-candidate': item['source']['candidate_sha256'] = 'f' * 64
    runtime = packs.Packs(store.Vault(vault))
    with pytest.raises(ValueError): topicals.validate_bank(bank, runtime, vault)


def test_bank_loader_fails_closed_before_public_copied_private_bytes_reach_items(tmp_path, monkeypatch):
    from tutorlib import packs, store
    from tutorlib.asset_library import write_asset
    _, vault, bank = bank_with_sibling_private_public_media(tmp_path, monkeypatch,
        whole=False, channel='images', copied=True)
    version = 'v-synthetic-private-leak'
    write_asset(vault, f'Library/Shared/Topicals/Releases/{version}/bank.json', json.dumps(bank).encode(),
                metadata={'kind': 'Topicals/Releases', 'version': version})
    pointer = vault / '.tutor/topicals/CURRENT'; pointer.parent.mkdir(parents=True)
    pointer.write_text(version)
    runtime = packs.Packs(store.Vault(vault))
    assert runtime.topical_errors and runtime.topicals.items == []


@pytest.mark.parametrize('fault', [None, 'same-path', 'copied-bytes'])
def test_scope_media_guard_covers_auxiliary_reference_channel_without_source_role_guessing(tmp_path, fault):
    from PIL import Image
    ex = extraction(); candidate = tmp_path / 'candidate.json'
    for name, color in [('public.png', 'red'), ('private.png', 'blue'), ('reference.png', 'green')]:
        Image.new('RGB', (10, 10), color).save(tmp_path / name)
    reference = 'reference.png'
    if fault == 'same-path': reference = 'private.png'
    if fault == 'copied-bytes': (tmp_path / reference).write_bytes((tmp_path / 'private.png').read_bytes())
    records = [dict(kind='structured', question_media=['public.png'], mark_scheme_media=[],
                    reference_media=[reference]),
               dict(kind='structured', question_media=['public.png'], mark_scheme_media=['private.png'])]
    # Reference source permission is checked independently; this guard must
    # cover its learner-public channel once the source checks have passed.
    problems = ex._question_scope_media_problems({'candidate': str(candidate)}, records)
    assert bool(problems) is (fault is not None)


@pytest.mark.parametrize('whole', [False, True])
def test_runtime_primary_only_public_image_retains_complete_group_provenance(tmp_path, monkeypatch, whole):
    from tutorlib import packs, store
    _, _, _, vault, _, batch = prepared_case(tmp_path, monkeypatch, whole=whole)
    bank = json.loads((batch / 'bank.json').read_text())
    for item in bank['items']:
        item['image'] = item['images'][0]; item['images'] = []
    topicals.validate_bank(bank, packs.Packs(store.Vault(vault)), vault)
