"""A maker retry receives only exact, source-bound independent review findings."""
import json
from pathlib import Path

import pytest

from test_extraction_evidence_sources import prepared as focused_job, selection, native_mcq_partition

FINDING = 'part-a: source MS page 4 accepts the optional (2) locant; preserve methylpropan-1-ol in the rubric.'
PAGE_FINDING = 'circuit: source page 1 reverses the current arrow; qualify the source error before teaching.'


def completed_review_probe(tmp_path, monkeypatch, fault=None):
    from types import SimpleNamespace
    from test_extraction import extraction, reviewed_diagram
    ex = extraction(); path = reviewed_diagram(ex, tmp_path, monkeypatch)
    with ex.state_lock('diagram') as state:
        state['jobs']['review'] = {'provider': 'codex'}
    monkeypatch.setenv('STEM_EXTRACT_CODEX', '/fixture/never-executed')
    monkeypatch.setattr(ex.subprocess, 'Popen', lambda *a, **k: SimpleNamespace(pid=987654321))
    ex.run('diagram', weekly_remaining=90)
    if fault == 'graph-before-dispatch':
        graph = Path(ex.os.environ['STEM_LIBRARY_SPECS']) / '9702/graph.json'
        graph.write_bytes(graph.read_bytes() + b' ')
    elif fault == 'prompt-before-dispatch':
        prompt = ex.job_dir('diagram') / 'review.prompt.txt'
        prompt.write_bytes(prompt.read_bytes() + b' ')
    elif fault == 'frozen-before-dispatch':
        fingerprint = ex.load('diagram')['jobs']['review']['failure_input']
        prompt = ex.job_dir('diagram') / 'review-inputs' / fingerprint / 'review.prompt.txt'
        prompt.write_bytes(prompt.read_bytes() + b' ')
    dispatched = []
    def result(command, **kwargs):
        dispatched.append(command[-1])
        if fault == 'candidate-swap':
            data = json.loads(path.read_text()); data['diagrams'][0]['caption'] = 'Unreviewed replacement'
            path.write_text(json.dumps(data))
        review = {'candidate_sha256': ex.digest(path), 'verdict': 'pending', 'findings': [PAGE_FINDING],
                  'inspected_images': [ex.digest(path.parent / 'circuit.png')]}
        if fault == 'schema':
            review.pop('inspected_images')
        (ex.job_dir('diagram') / 'review.json').write_text(json.dumps(review))
        return SimpleNamespace(returncode=1 if fault == 'provider-exit' else 0, stdout='', stderr='')
    monkeypatch.setattr(ex.worker_timeout, 'run_captured', result)
    ex._worker('diagram', 'review')
    return ex, dispatched


@pytest.mark.parametrize('fault', ['schema', 'provider-exit', 'candidate-swap'])
def test_direct_review_rejects_invalid_completion_or_changed_launch_candidate(tmp_path, monkeypatch, fault):
    ex, _ = completed_review_probe(tmp_path, monkeypatch, fault)
    state = ex.load('diagram')
    monkeypatch.setattr(ex.subprocess, 'Popen', lambda *a, **k: pytest.fail('rejected review launched repair'))
    with pytest.raises(ValueError, match='review feedback.*(attempt|input|candidate|schema|binding)'):
        ex.run('diagram', weekly_remaining=90, retry='extract')
    assert not ex.load('diagram').get('review_repair_history')


def test_direct_feedback_checks_launch_candidate_even_with_completed_output_hash(tmp_path, monkeypatch):
    ex, _ = completed_review_probe(tmp_path, monkeypatch, 'candidate-swap')
    # Independently exercise feedback's launch-input gate, even if a previous
    # completion path recorded success for the replacement candidate.
    with ex.state_lock('diagram') as state:
        state['jobs']['review'].update(exit=0, finished='legacy completion')
    with pytest.raises(ValueError, match='review feedback.*(input|candidate|binding)'):
        ex._review_repair_input(ex.load('diagram'))


@pytest.mark.parametrize('retained', [False, True])
def test_saved_prompt_cannot_rebind_completed_review_graph(tmp_path, monkeypatch, retained):
    ex, dispatched = completed_review_probe(tmp_path, monkeypatch)
    assert len(dispatched) == 1
    prompt = ex.job_dir('diagram') / 'review.prompt.txt'
    assert prompt.read_text() == dispatched[0]
    before, text = prompt.read_text().split('JOB CONTRACT:\n', 1); contract = json.loads(text)
    graph = Path(ex.os.environ['STEM_LIBRARY_SPECS']) / '9702/graph.json'
    graph.write_bytes(graph.read_bytes() + b' ')
    contract['course_graph_sha256'] = ex.digest(graph)
    prompt.write_text(before + 'JOB CONTRACT:\n' + json.dumps(contract))
    if retained:
        with ex.state_lock('diagram') as state:
            state['jobs']['review'] = {'provider': 'codex'}
    monkeypatch.setattr(ex.subprocess, 'Popen', lambda *a, **k: pytest.fail('edited dispatched prompt launched repair'))
    with pytest.raises(ValueError, match='review feedback.*(prompt|contract|graph|binding)'):
        ex.run('diagram', weekly_remaining=90, retry='extract')


def test_worker_dispatches_frozen_review_prompt_and_valid_pending_stays_repairable(tmp_path, monkeypatch):
    ex, dispatched = completed_review_probe(tmp_path, monkeypatch)
    state = ex.load('diagram'); job = state['jobs']['review']
    assert job['exit'] == 0 and job['ok'] is False
    assert job['prompt_sha256'] == ex.hashlib.sha256(dispatched[0].encode()).hexdigest()
    receipt = state['review_attempt_history'][-1]
    assert receipt['prompt_sha256'] == job['prompt_sha256']
    assert receipt['course_graph_sha256'] == ex._course_graph_input('9702')[1]
    assert ex._review_repair_input(state)['findings'] == [PAGE_FINDING]


@pytest.mark.parametrize('fault', ['graph-before-dispatch', 'prompt-before-dispatch', 'frozen-before-dispatch'])
def test_changed_frozen_review_inputs_stop_before_provider_dispatch(tmp_path, monkeypatch, fault):
    ex, dispatched = completed_review_probe(tmp_path, monkeypatch, fault)
    assert dispatched == []
    state = ex.load('diagram')
    assert state['jobs']['review']['exit'] == 1
    assert not state.get('review_attempt_history')


@pytest.mark.parametrize('witness', ['valid', 'missing', 'stale'])
def test_legacy_inserted_prompt_graph_cannot_skip_reviewed_candidate_witness(tmp_path, monkeypatch, witness):
    ex, _ = unfocused_job(tmp_path, monkeypatch, previous=True, legacy_graph=True, witness=witness)
    prompt = ex.job_dir('diagram') / 'review.prompt.txt'
    before, text = prompt.read_text().split('JOB CONTRACT:\n', 1); contract = json.loads(text)
    contract['course_graph_sha256'] = ex._course_graph_input('9702')[1]
    prompt.write_text(before + 'JOB CONTRACT:\n' + json.dumps(contract))
    if witness == 'valid':
        packet = ex._review_repair_input(ex.load('diagram'))
        assert packet['review_authentication']['legacy_graph_witness']['sha256'] == contract['course_graph_sha256']
        return
    with pytest.raises(ValueError, match='review feedback.*graph.*(binding|witness)'):
        ex._review_repair_input(ex.load('diagram'))


def unfocused_job(tmp_path, monkeypatch, kind='diagrams', *, previous=False, verdict='pending',
                  legacy_graph=False, witness='valid'):
    from test_extraction import extraction, reviewed_diagram
    ex = extraction(); path = reviewed_diagram(ex, tmp_path, monkeypatch)
    if kind == 'questions':
        data = json.loads(path.read_text()); record = data['diagrams'].pop()
        record.update(kind='mcq', official_qid='9702_s24_22_q1', part='', prerequisites=[], answer='A',
                      mark_scheme_regions=record['regions'])
        data['questions'] = [record]; path.write_text(json.dumps(data))
    data = json.loads(path.read_text())
    for row in data[kind]:
        row['mapping_evidence'] = {'graph_sha256': ex._course_graph_input('9702')[1]}
    if witness == 'missing':
        data[kind][0].pop('mapping_evidence')
    elif witness == 'stale':
        data[kind][0]['mapping_evidence']['graph_sha256'] = '0' * 64
    elif witness == 'mixed':
        extra = json.loads(json.dumps(data[kind][0])); extra['id'] = 'another-circuit'
        extra['mapping_evidence']['graph_sha256'] = '0' * 64
        data[kind].append(extra)
    path.write_text(json.dumps(data))
    with ex.state_lock('diagram') as state:
        state['scope'] = kind
        state['jobs']['extract'].update(provider='codex', exit=0, output_sha256=ex.digest(path))
        state['jobs']['review'] = {'provider': 'codex'}
    fake = tmp_path / 'fake-page-provider'
    fake.write_text('''#!/usr/bin/env python3
import hashlib,json,os,sys
from pathlib import Path
contract=json.loads(sys.argv[-1].split('JOB CONTRACT:\\n',1)[1])
output=Path(os.environ['EXTRACT_OUTPUT'])
if os.environ['EXTRACT_ROLE']=='review':
    candidate=Path(contract['candidate'])
    data=json.loads(candidate.read_bytes())
    images=[hashlib.sha256((candidate.parent/name).read_bytes()).hexdigest()
        for kind in ('questions','diagrams') for row in data[kind] for name in row['media']]
    verdict=os.environ['EXTRACT_TEST_REVIEW_VERDICT']
    output.write_text(json.dumps({'candidate_sha256':hashlib.sha256(candidate.read_bytes()).hexdigest(),
        'verdict':verdict,'findings':[] if verdict=='pass' else [os.environ['EXTRACT_TEST_FINDING']],
        'inspected_images':images}))
else:
    output.write_bytes(Path(contract['previous_candidate']).read_bytes())
''')
    fake.chmod(0o755)
    monkeypatch.setenv('STEM_EXTRACT_CODEX', str(fake))
    monkeypatch.setenv('EXTRACT_TEST_FINDING', PAGE_FINDING)
    monkeypatch.setenv('EXTRACT_TEST_REVIEW_VERDICT', verdict)
    ex.run('diagram', weekly_remaining=90, wait=True)
    state = ex.load('diagram')
    assert state['jobs']['review']['exit'] == 0
    assert state['jobs']['review']['ok'] is (verdict == 'pass')
    if legacy_graph:
        prompt = ex.job_dir('diagram') / 'review.prompt.txt'
        head, text = prompt.read_text().split('JOB CONTRACT:\n', 1); contract = json.loads(text)
        contract.pop('course_graph_sha256', None)
        prompt.write_text(head + 'JOB CONTRACT:\n' + json.dumps(contract))
        with ex.state_lock('diagram') as current:
            current.pop('review_attempt_history', None)  # Emulate a historical prompt without receipts.
            current['jobs']['review'].pop('prompt_sha256', None)
            current['jobs']['review'].pop('course_graph_sha256', None)
    reviewed_hash = ex.digest(path)
    if previous:
        saved = path.with_suffix('.saved-previous.json'); path.rename(saved)
        data = json.loads(saved.read_text()); data['unrelated_metadata'] = 'Prior unsupported repair'
        path.write_text(json.dumps(data))
        with ex.state_lock('diagram') as state:
            state['previous_candidate'] = str(saved)
            state['jobs']['review'] = {'provider': 'codex'}
            state['jobs']['extract']['output_sha256'] = ex.digest(path)
    return ex, reviewed_hash


@pytest.mark.parametrize('kind', ['diagrams', 'questions'])
@pytest.mark.parametrize('previous', [False, True])
def test_unfocused_retry_forwards_authenticated_page_review_only_to_maker(tmp_path, monkeypatch, kind, previous):
    ex, reviewed_hash = unfocused_job(tmp_path, monkeypatch, kind, previous=previous)
    before = ex.load('diagram'); review_hash = ex.digest(ex.job_dir('diagram') / 'review.json')
    repair_hash = ex.digest(ex.candidate_path(before))
    ex.run('diagram', weekly_remaining=90, wait=True, retry='extract')
    state = ex.load('diagram')
    contract = json.loads((ex.job_dir('diagram') / 'extract.prompt.txt').read_text().split('JOB CONTRACT:\n', 1)[1])
    packet = contract['review_feedback']
    assert packet['findings'] == [PAGE_FINDING]
    assert packet['review_candidate_sha256'] == reviewed_hash
    assert packet['repair_input_candidate_sha256'] == repair_hash
    assert packet['review_sha256'] == review_hash
    saved = json.loads(Path(state['jobs']['extract']['review_feedback']['path']).read_text())
    assert saved['binding']['scope'] == kind and saved['binding']['course'] == '9702'
    assert saved['binding']['selected_item_scope'] is None
    assert saved['binding']['sources'][0]['sha256'] == before['sources'][0]['sha256']
    assert saved['binding']['sources'][0]['selected_page_range'] == {'start': 1, 'end': 1, 'inclusive': True}
    assert saved['binding']['course_graph_sha256'] == ex._course_graph_input('9702')[1]
    assert ex.digest(state['previous_candidate']) == repair_hash
    assert state['reliability_failures'] == before['reliability_failures']
    assert len(state['review_repair_history']) == 1
    blind = ex._prompt(state, 'review')
    assert PAGE_FINDING not in blind
    reviewer = json.loads(blind.split('JOB CONTRACT:\n', 1)[1])
    assert not {'review_feedback', 'pending_findings', 'previous_candidate'}.intersection(reviewer)


@pytest.mark.parametrize('kind', ['diagrams', 'questions'])
@pytest.mark.parametrize('fault', ['finding', 'candidate', 'source-bytes', 'source-inventory',
                                  'pages', 'scope', 'graph', 'prompt-graph', 'diagram-region'])
def test_unfocused_retry_rejects_changed_review_bindings_before_launch(tmp_path, monkeypatch, kind, fault):
    ex, _ = unfocused_job(tmp_path, monkeypatch, kind)
    state = ex.load('diagram'); path = ex.candidate_path(state)
    prompt = ex.job_dir('diagram') / 'review.prompt.txt'
    if fault == 'finding':
        review = ex.job_dir('diagram') / 'review.json'; data = json.loads(review.read_text())
        data['findings'] = ['Unauthenticated replacement']; review.write_text(json.dumps(data))
    elif fault == 'candidate':
        path.write_bytes(path.read_bytes() + b' ')
    elif fault == 'source-bytes':
        source = Path(state['sources'][0]['path']); source.write_bytes(source.read_bytes() + b' ')
    elif fault == 'graph':
        graph = Path(ex.os.environ['STEM_LIBRARY_SPECS']) / '9702/graph.json'
        graph.write_bytes(graph.read_bytes() + b' ')
    elif fault == 'diagram-region':
        # A retained prior review may coexist with an unsupported repair, but its
        # replacement candidate must still remain inside the reviewed page scope.
        previous = path.with_suffix('.reviewed.json'); previous.write_bytes(path.read_bytes())
        data = json.loads(path.read_text()); data[kind][0]['regions'][0]['page'] = 2
        path.write_text(json.dumps(data))
        with ex.state_lock('diagram') as current:
            current['previous_candidate'] = str(previous)
    else:
        head, text = prompt.read_text().split('JOB CONTRACT:\n', 1); contract = json.loads(text)
        if fault == 'source-inventory':
            contract['sources'][0]['sha256'] = '0' * 64
        elif fault == 'pages':
            contract['sources'][0]['selected_page_range']['end'] = 2
        elif fault == 'scope':
            contract['scope'] = 'both'
        else:
            contract['course_graph_sha256'] = '0' * 64
        prompt.write_text(head + 'JOB CONTRACT:\n' + json.dumps(contract))
    state_path = ex.job_dir('diagram') / 'state.json'; before = state_path.read_bytes()
    candidate_before = path.read_bytes()
    monkeypatch.setattr(ex.subprocess, 'Popen', lambda *a, **k: pytest.fail('changed review binding launched worker'))
    with pytest.raises(ValueError, match='review.*(binding|candidate)|reviewed.*candidate|source changed'):
        ex.run('diagram', weekly_remaining=90, retry='extract')
    assert state_path.read_bytes() == before and path.read_bytes() == candidate_before


@pytest.mark.parametrize('previous', [False, True])
def test_legacy_page_prompt_uses_reviewed_candidate_graph_witness(tmp_path, monkeypatch, previous):
    ex, reviewed_hash = unfocused_job(tmp_path, monkeypatch, previous=previous, legacy_graph=True)
    prompt = ex.job_dir('diagram') / 'review.prompt.txt'; prompt_before = prompt.read_bytes()
    ex.run('diagram', weekly_remaining=90, wait=True, retry='extract')
    state = ex.load('diagram')
    packet = json.loads(Path(state['jobs']['extract']['review_feedback']['path']).read_text())
    assert packet['findings'] == [PAGE_FINDING] and packet['review_candidate_sha256'] == reviewed_hash
    assert packet['review_authentication']['legacy_graph_witness'] == {
        'origin': 'reviewed-candidate.mapping_evidence.graph_sha256',
        'sha256': ex._course_graph_input('9702')[1]}
    assert prompt.read_bytes() == prompt_before
    assert Path(packet['files']['review.prompt.txt']['path']).read_bytes() == prompt_before


@pytest.mark.parametrize('witness', ['missing', 'mixed', 'stale'])
def test_legacy_page_prompt_rejects_unproven_reviewed_graph(tmp_path, monkeypatch, witness):
    ex, _ = unfocused_job(tmp_path, monkeypatch, legacy_graph=True, witness=witness)
    state_path = ex.job_dir('diagram') / 'state.json'; before = state_path.read_bytes()
    monkeypatch.setattr(ex.subprocess, 'Popen', lambda *a, **k: pytest.fail('unproven legacy graph launched worker'))
    with pytest.raises(ValueError, match='review feedback.*graph.*(binding|witness)'):
        ex.run('diagram', weekly_remaining=90, retry='extract')
    assert state_path.read_bytes() == before


@pytest.mark.parametrize('fault', ['edited-findings', 'missing-failure-evidence'])
def test_unfocused_prior_review_requires_matching_recorded_failure(tmp_path, monkeypatch, fault):
    ex, _ = unfocused_job(tmp_path, monkeypatch, previous=True)
    if fault == 'edited-findings':
        review = ex.job_dir('diagram') / 'review.json'; data = json.loads(review.read_text())
        data['findings'] = ['Unreviewed replacement']; review.write_text(json.dumps(data))
    else:
        with ex.state_lock('diagram') as state:
            state['reliability_failures']['1']['review'][-1]['failure_input'] = 'invalid'
    state_path = ex.job_dir('diagram') / 'state.json'; before = state_path.read_bytes()
    monkeypatch.setattr(ex.subprocess, 'Popen', lambda *a, **k: pytest.fail('unauthenticated prior finding launched worker'))
    with pytest.raises(ValueError, match='review feedback.*(binding|finding|evidence)'):
        ex.run('diagram', weekly_remaining=90, retry='extract')
    assert state_path.read_bytes() == before


@pytest.mark.parametrize('focused', [False, True])
def test_retained_review_cannot_claim_the_unreviewed_current_candidate(tmp_path, monkeypatch, focused):
    ex, _ = (prepared(tmp_path, monkeypatch, previous=True) if focused
             else unfocused_job(tmp_path, monkeypatch, previous=True))
    name = 'job' if focused else 'diagram'
    review = ex.job_dir(name) / 'review.json'; data = json.loads(review.read_text())
    data['candidate_sha256'] = ex.digest(ex.candidate_path(ex.load(name)))
    review.write_text(json.dumps(data))
    state_path = ex.job_dir(name) / 'state.json'; before = state_path.read_bytes()
    monkeypatch.setattr(ex.subprocess, 'Popen', lambda *a, **k: pytest.fail('forged candidate review launched maker'))
    with pytest.raises(ValueError, match='review feedback.*(input|receipt|candidate|binding)'):
        ex.run(name, weekly_remaining=90, retry='extract')
    assert state_path.read_bytes() == before


@pytest.mark.parametrize('fault', ['missing', 'edited', 'swapped', 'source', 'graph',
                                  'receipt-review', 'receipt-candidate'])
def test_retained_review_requires_exact_historical_input_state(tmp_path, monkeypatch, fault):
    ex, _ = unfocused_job(tmp_path, monkeypatch, previous=True)
    state = ex.load('diagram'); fingerprint = state['reliability_failures']['1']['review'][-1]['failure_input']
    snapshot = ex.job_dir('diagram') / 'review-inputs' / fingerprint / 'state.json'
    assert snapshot.is_file()
    if fault == 'missing':
        snapshot.unlink()
    elif fault == 'edited':
        snapshot.write_bytes(snapshot.read_bytes() + b' ')
    elif fault == 'swapped':
        snapshot.write_bytes((ex.job_dir('diagram') / 'state.json').read_bytes())
    elif fault == 'source':
        source = Path(state['sources'][0]['path']); source.write_bytes(source.read_bytes() + b' ')
    elif fault == 'graph':
        graph = Path(ex.os.environ['STEM_LIBRARY_SPECS']) / '9702/graph.json'
        graph.write_bytes(graph.read_bytes() + b' ')
    else:
        with ex.state_lock('diagram') as current:
            key = 'output_sha256' if fault == 'receipt-review' else 'candidate_sha256'
            current['review_attempt_history'][-1][key] = '0' * 64
    state_path = ex.job_dir('diagram') / 'state.json'; before = state_path.read_bytes()
    monkeypatch.setattr(ex.subprocess, 'Popen', lambda *a, **k: pytest.fail('unbound review input launched maker'))
    with pytest.raises(ValueError, match='review feedback.*(input|receipt|binding)|source changed'):
        ex.run('diagram', weekly_remaining=90, retry='extract')
    assert state_path.read_bytes() == before


def test_legacy_retained_review_uses_recomputed_fingerprint_without_output_receipt(tmp_path, monkeypatch):
    ex, reviewed_hash = unfocused_job(tmp_path, monkeypatch, previous=True, legacy_graph=True)
    with ex.state_lock('diagram') as state:
        state.pop('review_attempt_history', None)
    ex.run('diagram', weekly_remaining=90, wait=True, retry='extract')
    state = ex.load('diagram')
    packet = json.loads(Path(state['jobs']['extract']['review_feedback']['path']).read_text())
    assert packet['review_candidate_sha256'] == reviewed_hash
    assert packet['review_authentication']['review_input_state_sha256']


@pytest.mark.parametrize('kind', ['diagrams', 'questions'])
def test_unfocused_pass_and_consumed_feedback_keep_existing_boundaries(tmp_path, monkeypatch, kind):
    ex, _ = unfocused_job(tmp_path, monkeypatch, kind, verdict='pass')
    ex.run('diagram', weekly_remaining=90, wait=True, retry='extract')
    state = ex.load('diagram')
    assert not state.get('review_repair_history')
    contract = json.loads(ex._prompt(state, 'extract').split('JOB CONTRACT:\n', 1)[1])
    assert 'review_feedback' not in contract
    # Obtain a fresh real pending review for this repaired candidate.
    monkeypatch.setenv('EXTRACT_TEST_REVIEW_VERDICT', 'pending')
    ex.run('diagram', weekly_remaining=90, wait=True)
    ex.run('diagram', weekly_remaining=90, wait=True, retry='extract')
    state_path = ex.job_dir('diagram') / 'state.json'; before = state_path.read_bytes()
    monkeypatch.setattr(ex.subprocess, 'Popen', lambda *a, **k: pytest.fail('consumed page feedback launched again'))
    with pytest.raises(ValueError, match='review feedback.*(used|consumed)'):
        ex.run('diagram', weekly_remaining=90, retry='extract')
    assert state_path.read_bytes() == before


def prepared(tmp_path, monkeypatch, *, previous=False, review_verdict='pending'):
    ex, _, refs = focused_job(tmp_path, monkeypatch)
    state = ex.evidence_sources('job', selection(refs), 'Native originals')
    path = ex.candidate_path(state); data = json.loads(path.read_text()); qp, ms = state['sources']
    for row in data['questions']:
        row.update(complete=True, uncertainty=[])
        row['regions'] = [{'source_id': qp['id'], 'source_sha256': qp['sha256'], 'page': 2, 'box': [0, 0, 1, 1]}]
        row['mark_scheme_regions'] = [{'source_id': ms['id'], 'source_sha256': ms['sha256'], 'page': 4, 'box': [0, 0, 1, 1]}]
        native_mcq_partition(path, row)
    data['source_coverage'] = [{'source_id': s['id'], 'source_sha256': s['sha256'],
        'inspected_pages': s['selected_page_numbers'], 'no_relevant_content': False, 'reason': ''} for s in state['sources']]
    path.write_text(json.dumps(data))
    with ex.state_lock('job') as current:
        current['jobs']['extract'].update(exit=0, finished='saved maker', output_sha256=ex.digest(path))
    fake = tmp_path / 'fake-provider'
    fake.write_text('''#!/usr/bin/env python3
import hashlib,json,os,sys
from pathlib import Path
contract=json.loads(sys.argv[-1].split('JOB CONTRACT:\\n',1)[1])
output=Path(os.environ['EXTRACT_OUTPUT'])
if os.environ['EXTRACT_ROLE']=='review':
    candidate=Path(contract['candidate'])
    data=json.loads(candidate.read_bytes())
    verdict=os.environ['EXTRACT_TEST_REVIEW_VERDICT']
    images=[hashlib.sha256((candidate.parent/name).read_bytes()).hexdigest() for row in data['questions'] for name in row['media']]
    output.write_text(json.dumps({'candidate_sha256':hashlib.sha256(candidate.read_bytes()).hexdigest(),
        'verdict':verdict,'findings':[] if verdict=='pass' else [os.environ['EXTRACT_TEST_FINDING']],'inspected_images':images}))
else:
    output.write_bytes(Path(contract['previous_candidate']).read_bytes())
''')
    fake.chmod(0o755); monkeypatch.setenv('STEM_EXTRACT_CODEX', str(fake)); monkeypatch.setenv('EXTRACT_TEST_FINDING', FINDING)
    monkeypatch.setenv('EXTRACT_TEST_REVIEW_VERDICT', review_verdict)
    ex.run('job', weekly_remaining=90, wait=True)
    reviewed_hash = ex.digest(path)
    if previous:
        saved = path.with_suffix('.saved-previous.json'); path.rename(saved)
        data['unrelated_metadata'] = 'Prior unsupported repair changed other bytes only'
        path.write_text(json.dumps(data))
        with ex.state_lock('job') as current:
            current['previous_candidate'] = str(saved)
            current['jobs']['review'] = {'provider': 'codex'}
            current['jobs']['extract'].update(exit=0, finished='previous unsupported repair', output_sha256=ex.digest(path))
    return ex, reviewed_hash


@pytest.mark.parametrize('previous', [False, True])
def test_retry_hands_exact_bound_review_finding_to_maker_only(tmp_path, monkeypatch, previous):
    ex, reviewed_hash = prepared(tmp_path, monkeypatch, previous=previous)
    state_before = ex.load('job'); review = ex.job_dir('job') / 'review.json'; review_hash = ex.digest(review)
    repair_input_hash = ex.digest(ex.candidate_path(state_before))
    ex.run('job', weekly_remaining=90, wait=True, retry='extract')
    state = ex.load('job')
    contract = json.loads((ex.job_dir('job') / 'extract.prompt.txt').read_text().split('JOB CONTRACT:\n', 1)[1])
    packet = contract['review_feedback']
    assert packet['findings'] == [FINDING]
    assert packet['review_candidate_sha256'] == reviewed_hash
    assert packet['review_sha256'] == review_hash
    assert packet['repair_input_candidate_sha256'] == repair_input_hash
    assert ex.digest(state['previous_candidate']) == repair_input_hash
    assert state['reliability_failures'] == state_before['reliability_failures']
    assert len(state['review_repair_history']) == 1
    metadata = state['jobs']['extract']['review_feedback']
    assert ex.digest(metadata['path']) == metadata['sha256']
    blind = ex._prompt(state, 'review')
    assert FINDING not in blind
    blind_contract = json.loads(blind.split('JOB CONTRACT:\n', 1)[1])
    assert 'review_feedback' not in blind_contract and 'pending_findings' not in blind_contract
    assert 'previous_candidate' not in blind_contract


@pytest.mark.parametrize('fault', ['review-hash', 'source', 'scope', 'graph', 'missing-candidate', 'wrong-previous'])
def test_retry_rejects_stale_review_input_binding_before_any_launch(tmp_path, monkeypatch, fault):
    ex, _ = prepared(tmp_path, monkeypatch, previous=fault == 'wrong-previous')
    review = ex.job_dir('job') / 'review.json'; prompt = ex.job_dir('job') / 'review.prompt.txt'
    if fault == 'review-hash':
        data = json.loads(review.read_text()); data['candidate_sha256'] = '0' * 64; review.write_text(json.dumps(data))
    elif fault == 'missing-candidate':
        ex.candidate_path(ex.load('job')).unlink()
    elif fault == 'wrong-previous':
        wrong = tmp_path / 'wrong-previous.json'; wrong.write_bytes(ex.candidate_path(ex.load('job')).read_bytes())
        with ex.state_lock('job') as current:
            current['previous_candidate'] = str(wrong)
    else:
        before, text = prompt.read_text().split('JOB CONTRACT:\n', 1); contract = json.loads(text)
        if fault == 'source':
            contract['sources'][0]['sha256'] = '0' * 64
        elif fault == 'scope':
            contract['selected_item_scope']['official_qid'] = '9702_s23_22_q99'
        else:
            contract['course_graph_sha256'] = '0' * 64
        prompt.write_text(before + 'JOB CONTRACT:\n' + json.dumps(contract))
    state_path = ex.job_dir('job') / 'state.json'; state_bytes = state_path.read_bytes()
    monkeypatch.setattr(ex.subprocess, 'Popen', lambda *a, **k: pytest.fail('stale review launched another worker'))
    with pytest.raises(ValueError, match='review.*(binding|candidate|feedback)|reviewed.*candidate'):
        ex.run('job', weekly_remaining=90, retry='extract')
    assert state_path.read_bytes() == state_bytes


def test_retry_never_forwards_pass_review_as_repair_feedback(tmp_path, monkeypatch):
    ex, _ = prepared(tmp_path, monkeypatch, review_verdict='pass')
    state = ex.load('job')
    assert state['jobs']['review']['output_sha256'] == ex.digest(ex.job_dir('job') / 'review.json')
    assert state['jobs']['review']['ok'] is True
    ex.run('job', weekly_remaining=90, wait=True, retry='extract')
    contract = json.loads((ex.job_dir('job') / 'extract.prompt.txt').read_text().split('JOB CONTRACT:\n', 1)[1])
    assert 'review_feedback' not in contract
    assert not ex.load('job').get('review_repair_history')


@pytest.mark.parametrize('reformat', [False, True])
def test_retry_cannot_replay_consumed_feedback_after_one_repair_attempt(tmp_path, monkeypatch, reformat):
    ex, _ = prepared(tmp_path, monkeypatch)
    ex.run('job', weekly_remaining=90, wait=True, retry='extract')
    if reformat:
        review = ex.job_dir('job') / 'review.json'
        review.write_bytes(review.read_bytes() + b' ')
    path = ex.job_dir('job') / 'state.json'; before = path.read_bytes()
    monkeypatch.setattr(ex.subprocess, 'Popen', lambda *a, **k: pytest.fail('consumed feedback launched again'))
    with pytest.raises(ValueError, match='review feedback.*(used|consumed)'):
        ex.run('job', weekly_remaining=90, retry='extract')
    assert path.read_bytes() == before


def test_saved_feedback_input_bytes_are_rechecked_without_leaking_to_reviewer(tmp_path, monkeypatch):
    ex, _ = prepared(tmp_path, monkeypatch)
    ex.run('job', weekly_remaining=90, wait=True, retry='extract')
    state = ex.load('job'); metadata = state['jobs']['extract']['review_feedback']
    packet = json.loads(Path(metadata['path']).read_text())
    archived = Path(packet['files']['review.json']['path'])
    archived.write_bytes(archived.read_bytes() + b'changed')
    with pytest.raises(ValueError, match='archived input binding changed'):
        ex._prompt(state, 'extract')
    assert FINDING not in ex._prompt(state, 'review')


@pytest.mark.parametrize('kind', ['diagrams', 'questions'])
def test_unfocused_pending_review_keeps_legacy_retry_without_focused_packet(tmp_path, monkeypatch, kind):
    from types import SimpleNamespace
    from test_extraction import extraction, reviewed_diagram
    ex = extraction(); path = reviewed_diagram(ex, tmp_path, monkeypatch)
    if kind == 'questions':
        data = json.loads(path.read_text()); record = data['diagrams'].pop()
        record.update(kind='mcq', official_qid='9702_s24_22_q1', part='', prerequisites=[], answer='A',
                      mark_scheme_regions=record['regions'])
        data['questions'] = [record]; path.write_text(json.dumps(data))
        with ex.state_lock('diagram') as current:
            current['scope'] = 'questions'
    state = ex.load('diagram')
    review = ex.job_dir('diagram') / 'review.json'
    review.write_text(json.dumps({'candidate_sha256': ex.digest(path), 'verdict': 'pending',
                                  'findings': ['Legacy source detail needs repair'], 'inspected_images': []}))
    (ex.job_dir('diagram') / 'review.prompt.txt').write_text(ex._prompt(state, 'review'))
    monkeypatch.setenv('STEM_EXTRACT_CLAUDE', '/fixture/not-executed-provider')
    monkeypatch.setattr(ex.subprocess, 'Popen', lambda *a, **k: SimpleNamespace(pid=987654321))
    result = ex.run('diagram', weekly_remaining=90, retry='extract')
    assert result['stage'] == 'extracting'
    contract = json.loads((ex.job_dir('diagram') / 'extract.prompt.txt').read_text().split('JOB CONTRACT:\n', 1)[1])
    assert 'review_feedback' not in contract and not result.get('review_repair_history')


@pytest.mark.parametrize('fault', ['edited-findings', 'missing-failure-evidence'])
def test_previous_candidate_feedback_requires_recorded_independent_finding(tmp_path, monkeypatch, fault):
    ex, _ = prepared(tmp_path, monkeypatch, previous=True)
    state = ex.load('job')
    assert state['reliability_failures']['1']['review'][-1]['issues'] == [FINDING]
    if fault == 'edited-findings':
        review = ex.job_dir('job') / 'review.json'; data = json.loads(review.read_text())
        data['findings'] = ['Unreviewed replacement finding.']; review.write_text(json.dumps(data))
    else:
        with ex.state_lock('job') as current:
            current['reliability_failures']['1'].pop('review')
    state_path = ex.job_dir('job') / 'state.json'; before = state_path.read_bytes()
    candidate = ex.candidate_path(ex.load('job')); old_candidate = candidate.read_bytes()
    monkeypatch.setattr(ex.subprocess, 'Popen', lambda *a, **k: pytest.fail('unauthenticated legacy feedback launched'))
    with pytest.raises(ValueError, match='review feedback.*(binding|finding|evidence)'):
        ex.run('job', weekly_remaining=90, retry='extract')
    assert state_path.read_bytes() == before and candidate.read_bytes() == old_candidate


@pytest.mark.parametrize('previous', [False, True])
@pytest.mark.parametrize('change', ['pass', 'delete'])
def test_known_pending_review_cannot_disappear_before_repair(tmp_path, monkeypatch, previous, change):
    ex, _ = prepared(tmp_path, monkeypatch, previous=previous)
    review = ex.job_dir('job') / 'review.json'
    if change == 'delete':
        review.unlink()
    else:
        data = json.loads(review.read_text()); data.update(verdict='pass', findings=[])
        review.write_text(json.dumps(data))
    state_path = ex.job_dir('job') / 'state.json'; before = state_path.read_bytes()
    candidate = ex.candidate_path(ex.load('job')); candidate_before = candidate.read_bytes()
    monkeypatch.setattr(ex.subprocess, 'Popen', lambda *a, **k: pytest.fail('known pending review disappeared before launch'))
    with pytest.raises(ValueError, match='review feedback.*(binding|finding|evidence|missing)'):
        ex.run('job', weekly_remaining=90, retry='extract')
    assert state_path.read_bytes() == before and candidate.read_bytes() == candidate_before


def test_never_reviewed_focused_native_job_keeps_first_maker_retry(tmp_path, monkeypatch):
    from types import SimpleNamespace
    ex, _, refs = focused_job(tmp_path, monkeypatch)
    ex.evidence_sources('job', selection(refs), 'First native evidence')
    assert not (ex.job_dir('job') / 'review.json').exists()
    monkeypatch.setenv('STEM_EXTRACT_CODEX', '/fixture/not-executed-provider')
    monkeypatch.setattr(ex.subprocess, 'Popen', lambda *a, **k: SimpleNamespace(pid=987654321))
    result = ex.run('job', weekly_remaining=90, retry='extract')
    assert result['stage'] == 'extracting' and not result.get('review_repair_history')


@pytest.mark.parametrize('remove_old_file', [False, True])
def test_new_native_scope_ignores_resolved_published_scope_review_history(tmp_path, monkeypatch, remove_old_file):
    from types import SimpleNamespace
    from test_extraction_next_question import prepared as published_job
    ex, vault, _, _, native, _ = published_job(tmp_path, monkeypatch)
    failures = ex.load('multi')['reliability_failures']
    assert failures['1']['review']
    ex.next_question('multi', '9702_s23_22_q2', 'Next question after published pass')
    ex.evidence_sources('multi', [native[0] + '=2', native[1] + '=1,3'], 'First native repair for new scope')
    if remove_old_file:
        (ex.job_dir('multi') / 'review.json').unlink()
    monkeypatch.setenv('STEM_EXTRACT_CODEX', '/fixture/not-executed-provider')
    monkeypatch.setattr(ex.subprocess, 'Popen', lambda *a, **k: SimpleNamespace(pid=987654321))
    result = ex.run('multi', weekly_remaining=90, retry='extract')
    assert result['stage'] == 'extracting' and result['reliability_failures'] == failures
    contract = json.loads((ex.job_dir('multi') / 'extract.prompt.txt').read_text().split('JOB CONTRACT:\n', 1)[1])
    assert 'review_feedback' not in contract and not result.get('review_repair_history')


def test_archived_prior_pass_cannot_hide_a_new_scope_missing_pending_review(tmp_path, monkeypatch):
    from test_extraction_next_question import prepared as published_job
    ex, _, _, _, native, _ = published_job(tmp_path, monkeypatch)
    ex.next_question('multi', '9702_s23_22_q2', 'Next question after published pass')
    ex.evidence_sources('multi', [native[0] + '=2', native[1] + '=1,3'], 'Native evidence')
    with ex.state_lock('multi') as current:
        current['reliability_failures']['1']['review'].append({
            'issues': [FINDING], 'exit_code': 0, 'failure_input': 'f' * 64})
    (ex.job_dir('multi') / 'review.json').unlink()
    path = ex.job_dir('multi') / 'state.json'; before = path.read_bytes()
    monkeypatch.setattr(ex.subprocess, 'Popen', lambda *a, **k: pytest.fail('new pending finding hidden by old pass'))
    with pytest.raises(ValueError, match='review feedback.*missing'):
        ex.run('multi', weekly_remaining=90, retry='extract')
    assert path.read_bytes() == before
