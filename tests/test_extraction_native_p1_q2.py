"""Exact Q2 schema/source availability only; no native content or teaching claim."""
import copy
import json
from pathlib import Path
import shlex

import pytest
from ial_p1_fixtures import QID, QP, MS, source_fixture, regions, p1_case
from test_extraction_native_p1_launch import fresh_inputs, create, SELECTORS
from tutorlib import ial_p1_identity, topicals, packs, store
from tutorlib.asset_library import AssetLibrary

Q2 = 'P1_pearson-edexcel-ial_WMA11_2019-01_01_q2'
Q2_SELECTORS = [QP + '=1,4-5', MS + '=1-7,9-10']
Q2_PAGES = [[1, 4, 5], [1, 2, 3, 4, 5, 6, 7, 9, 10]]


def q2_regions(lib, ref, pages):
    return [{**regions(lib, ref)[0], 'page': page} for page in pages]


def q2_case(tmp_path, monkeypatch, *, whole=False):
    ex, path, q, vault, old_save = p1_case(tmp_path, monkeypatch, whole=whole)
    lib = AssetLibrary(vault)
    q.update(official_qid=Q2, regions=q2_regions(lib, QP, [4, 5]),
             mark_scheme_regions=q2_regions(lib, MS, [9, 10]))
    with ex.state_lock('diagram') as state:
        for source, pages in zip(state['sources'], Q2_PAGES):
            source['selected_page_numbers'] = pages
    def save():
        old_save()
        data = json.loads(path.read_text())
        for row, pages in zip(data['source_coverage'], Q2_PAGES): row['inspected_pages'] = pages
        path.write_text(json.dumps(data))
        review_path = ex.job_dir('diagram') / 'review.json'
        review = json.loads(review_path.read_text()); review['candidate_sha256'] = ex.digest(path)
        review_path.write_text(json.dumps(review))
    save()
    return ex, path, q, vault, save


def test_q2_exact_identity_is_distinct_and_requires_whole_part():
    assert topicals.identity({'source': {'qid': Q2, 'part': ''}}) == Q2
    assert topicals.official_course({'qid': Q2, 'part': ''}) == 'P1'
    descriptor = ial_p1_identity.p1_pilot(Q2, '')
    assert descriptor['question'] == 2
    descriptor['qp']['sha256'] = 'tampered'
    assert ial_p1_identity.p1_pilot(Q2, '')['qp']['sha256'] != 'tampered'
    assert topicals.identity({'source': {'qid': QID, 'part': ''}}) != Q2
    for bad, part in [(Q2, 'a'), (Q2, None), (Q2 + ':a', ''), (Q2.replace('q2', 'q02'), ''),
                      (Q2.replace('q2', 'q3'), ''), (Q2.replace('WMA11', 'WMA12'), ''),
                      (Q2.replace('2019-01', '2019-06'), ''), (Q2.replace('_01_q', '_02_q'), '')]:
        assert ial_p1_identity.p1_pilot(bad, part) is None
        assert topicals.identity({'source': {'qid': bad, 'part': part, 'ref': '9702 Jun 2023 P22 Q2(a)'}}) is None


@pytest.mark.parametrize('context', [[], [1, 2, 3, 4, 5, 6, 7]])
def test_q2_requires_task_continuation_and_guidance_with_only_declared_context(tmp_path, context):
    lib = source_fixture(tmp_path)
    ial_p1_identity.validate_p1_sources(Q2, '', 'P1', q2_regions(lib, QP, [4, 5]),
                                      q2_regions(lib, MS, context + [9, 10]), lib)


@pytest.mark.parametrize('fault', ['q1-pages', 'missing-task', 'missing-continuation', 'extra-qp',
    'missing-table', 'missing-guidance', 'q1-scheme', 'extra-ms', 'role', 'hash', 'course',
    'catalog-course', 'catalog-kind', 'catalog-path', 'catalog-hash', 'bytes', 'missing'])
def test_q2_rejects_same_pdf_transplant_and_source_drift(tmp_path, fault):
    lib = source_fixture(tmp_path); q = q2_regions(lib, QP, [4, 5]); m = q2_regions(lib, MS, [9, 10]); course = 'P1'
    if fault == 'q1-pages': q = q2_regions(lib, QP, [2, 3]); m = q2_regions(lib, MS, [8])
    if fault == 'missing-task': q.pop(0)
    if fault == 'missing-continuation': q.pop()
    if fault == 'extra-qp': q.insert(0, {**q[0], 'page': 1})
    if fault == 'missing-table': m.pop(0)
    if fault == 'missing-guidance': m.pop()
    if fault == 'q1-scheme': m.insert(0, {**m[0], 'page': 8})
    if fault == 'extra-ms': m.append({**m[0], 'page': 11})
    if fault == 'role': q, m = m, q
    if fault == 'hash': q[0]['source_sha256'] = '0' * 64
    if fault == 'course': course = '9702'
    if fault.startswith('catalog-'):
        key = fault.removeprefix('catalog-'); key = 'sha256' if key == 'hash' else key
        path = tmp_path / 'Library/catalog.json'; data = json.loads(path.read_text())
        data['assets'][QP[6:]][key] = {'course': '9702', 'kind': 'Diagrams', 'path': 'Library/wrong.pdf', 'sha256': '0' * 64}[key]
        path.write_text(json.dumps(data)); lib = AssetLibrary(tmp_path)
    if fault == 'bytes': (tmp_path / lib.record(QP)['path']).write_bytes(b'corrupt')
    if fault == 'missing': (tmp_path / lib.record(MS)['path']).unlink()
    with pytest.raises(ValueError): ial_p1_identity.validate_p1_sources(Q2, '', course, q, m, lib)


def test_q2_fresh_api_cli_plan_resume_and_exact_gapped_commands(tmp_path, monkeypatch, capsys):
    ex, _ = fresh_inputs(tmp_path, monkeypatch)
    state = create(ex, official_qid=Q2, source_pages=list(reversed(Q2_SELECTORS)), codex_stop_remaining=40)
    assert state['jobs'] == {} and state['stage'] == 'inventoried'
    assert state['initial_native_question'] == {'version': 1, 'official_qid': Q2, 'part': '', 'source_pages': Q2_SELECTORS, 'job_name': 'fresh'}
    assert state['selected_item_scope']['record_ids'] == ['native-' + Q2]
    assert state['selected_item_scope']['assessed_parts'] == {'native-' + Q2: ''}
    assert state['selected_item_scope']['origin'] == 'fresh_native_p1_v1'
    assert [s['selected_page_numbers'] for s in state['sources']] == Q2_PAGES
    assert state['codex_stop_remaining'] == 40 and not Path(state['candidate']).exists()
    assert not any(k in state for k in ('focus_history', 'previous_candidate', 'completed_scope_history'))
    assert ex.resume('fresh') == state
    state = ex.plan('fresh')
    for role in ('extract', 'review'):
        contract = json.loads(ex._prompt(state, role).split('JOB CONTRACT:\n')[1])
        assert contract['course_graph_sha256'] == state['focus_graph_sha256']
        assert not contract.get('previous_candidate')
        for source, expected_runs in zip(state['sources'], [[[1], [4, 5]], [[1, 2, 3, 4, 5, 6, 7], [9, 10]]]):
            read = contract['bounded_read_plan'][source['id']]
            assert 'text' not in read
            assert [run['pages'] for run in read['text_runs']] == expected_runs
            emitted = []
            for run, expected_selector in zip(read['text_runs'], ['1', '4-5'] if source['id'] == QP else ['1-7', '9-10']):
                tokens = shlex.split(run['command'])
                assert tokens[-4:] == ['text', source['id'], '--pages', expected_selector]
                first, _, last = tokens[-1].partition('-')
                command_pages = list(range(int(first), int(last or first) + 1))
                assert command_pages == run['pages']; emitted += command_pages
            assert emitted == source['selected_page_numbers']
            assert [r['page'] for r in read['render']] == emitted
            assert all(shlex.split(r['command'])[-3:] == ['page', source['id'], str(r['page'])] for r in read['render'])
    assert ex.main(['new', 'q2-cli', '--course', 'P1', '--scope', 'questions', '--provider', 'codex',
                    '--official-qid', Q2, '--source-pages', Q2_SELECTORS[0], '--source-pages', Q2_SELECTORS[1]]) == 0
    assert json.loads(capsys.readouterr().out)['initial_native_question']['source_pages'] == Q2_SELECTORS
    for ref, page in [(QP, 2), (QP, 3), (MS, 8)]:
        with pytest.raises(ValueError, match='outside'): ex.crop('fresh', ref, page, '0,0,1,1', 'excluded.png')
    assert not Path(state['candidate']).exists()


@pytest.mark.parametrize('qid,selectors', [(Q2, SELECTORS), (QID, Q2_SELECTORS),
    (Q2.replace('q2', 'q3'), Q2_SELECTORS), (Q2, [QP + '=1-5', Q2_SELECTORS[1]]),
    (Q2, [Q2_SELECTORS[0], MS + '=1-10']), (Q2, [QP + '=4-5', Q2_SELECTORS[1]]),
    (Q2, [Q2_SELECTORS[0], MS + '=1-7,9'])])
def test_q2_launch_refuses_wrong_identity_or_page_selection(tmp_path, monkeypatch, qid, selectors):
    ex, _ = fresh_inputs(tmp_path, monkeypatch)
    with pytest.raises(ValueError): create(ex, official_qid=qid, source_pages=selectors)
    assert not (ex.job_dir('fresh') / 'state.json').exists()


@pytest.mark.parametrize('whole', [False, True])
def test_q2_reviewed_schema_round_trip_preserves_private_source_and_real_graph(tmp_path, monkeypatch, whole):
    ex, path, q, vault, save = q2_case(tmp_path, monkeypatch, whole=whole)
    checked = ex.check('diagram'); assert checked['stage'] == 'reviewed', checked['problems']
    ex.register('diagram'); batch = tmp_path / 'q2-prepared'; ex.prepare_publication('diagram', batch)
    ex.publish('diagram', batch)
    runtime = packs.Packs(store.Vault(vault)); assert not runtime.topical_errors
    item = runtime.topicals.items[0]
    assert topicals.identity(item) == Q2 and runtime.kcs['P1-1.1']['level'] == 'P1'
    assert item['source']['extraction_regions'] == q['regions']
    assert item['source']['mark_scheme_regions'] == q['mark_scheme_regions']
    if whole:
        private = topicals.whole_rubric_media(item, vault)
        assert private and private[0]['reference'] not in item['images']
    else: assert item['scheme'] == q['scheme']
    # Same immutable PDFs cannot make Q1 regions valid for Q2 at runtime.
    bank = json.loads((batch / 'bank.json').read_text())
    bank['items'][0]['source']['extraction_regions'] = [{**q['regions'][0], 'page': 2}, {**q['regions'][1], 'page': 3}]
    with pytest.raises(ValueError): topicals.validate_bank(bank, runtime, vault)


def test_q1_to_q2_same_pdf_candidate_transplant_remains_pending(tmp_path, monkeypatch):
    ex, _, q, _, save = p1_case(tmp_path, monkeypatch)
    q['official_qid'] = Q2; save()
    checked = ex.check('diagram'); assert checked['stage'] == 'pending'
