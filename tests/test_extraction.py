"""Extraction jobs use disposable sources, candidates and fake provider binaries."""
import importlib.util
import json
import sys
from pathlib import Path

import pytest
from test_library import make_pdf

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'build'))
import library


def test_canonical_chapter_sources_are_course_scoped_verified_and_cache_in_work(tmp_path, monkeypatch):
    from tutorlib.asset_library import write_asset
    vault = tmp_path / 'vault'
    vault.mkdir()
    monkeypatch.delenv('STEM_LIBRARY_ROOT', raising=False)
    monkeypatch.setenv('STEM_TUTOR_VAULT', str(vault))
    monkeypatch.setenv('STEM_LIBRARY_CACHE', str(tmp_path / 'Work/cache'))
    refs = []
    for course in ('9702', '9701'):
        pdf = make_pdf(tmp_path / f'{course}.pdf', ['Standing waves node antinode'])
        refs.append(write_asset(vault, f'Library/Courses/{course}/Sources/Library/book.pdf', pdf.read_bytes(),
                                metadata={'course': course, 'kind': 'Sources/Library'}))
    pdf = make_pdf(tmp_path / 'shared.pdf', ['Standing waves node antinode'])
    write_asset(vault, 'Library/Shared/Sources/Library/physics.pdf', pdf.read_bytes(),
                metadata={'courses': ['9702'], 'kind': 'Sources/Library'})
    graph = tmp_path / 'specs/9702/graph.json'
    graph.parent.mkdir(parents=True)
    graph.write_text(json.dumps({'subtopics': [{'id': '9702-1.1'}], 'kcs': [
        {'id': '9702-1.1.1', 'subtopic': '9702-1.1', 'title': 'Standing waves', 'glossary': ['node']}]}))
    monkeypatch.setenv('STEM_LIBRARY_SPECS', str(graph.parent.parent))
    hits = library.hits_for('9702-1.1')
    paths = [r[0] for _, _, rows in hits for r in rows]
    assert len(paths) == 2 and all('/9701/' not in p for p in paths)
    assert not (vault / 'Library/.cache').exists()
    (vault / 'Library/Courses/9702/Sources/Library/book.pdf').write_bytes(b'tampered')
    with pytest.raises(library.Fail, match='digest mismatch'):
        library.hits_for('9702-1.1')


def extraction():
    spec = importlib.util.spec_from_file_location('extraction_cli', ROOT / 'extraction/extract.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_job_inventory_dedups_bytes_preserves_options_and_resumes(tmp_path, monkeypatch):
    ex = extraction()
    monkeypatch.setenv('STEM_EXTRACT_ROOT', str(tmp_path / 'Work'))
    sources = tmp_path / 'sources'
    monkeypatch.setenv('STEM_LIBRARY_ROOT', str(sources))
    first = make_pdf(sources / 'a.pdf', ['9702/12_Summer_2024_Q1 Text question'])
    (sources / 'copy.pdf').write_bytes(first.read_bytes())
    state = ex.create('job1', '9702', provider='codex', scope='questions')
    state = ex.inventory('job1')
    assert state['provider'] == 'codex' and state['scope'] == 'questions'
    assert len(state['sources']) == 1 and len(state['sources'][0]['aliases']) == 2
    plan = ex.plan('job1')
    assert plan['jobs']['extract']['provider'] == 'codex'
    assert plan['jobs']['review']['provider'] == 'codex'
    assert plan['review_independence'] == 'same_family'
    assert ex.load('job1')['sources'] == state['sources']


def test_both_provider_blind_check_and_candidate_pending_boundaries(tmp_path, monkeypatch):
    ex = extraction()
    monkeypatch.setenv('STEM_EXTRACT_ROOT', str(tmp_path / 'Work'))
    monkeypatch.setenv('STEM_LIBRARY_ROOT', str(tmp_path / 'sources'))
    make_pdf(tmp_path / 'sources/book.pdf', ['Question'])
    ex.create('both', '9702', provider='both', scope='both')
    ex.inventory('both')
    state = ex.plan('both')
    assert state['jobs']['extract']['provider'] == 'claude'
    assert state['jobs']['review']['provider'] == 'codex'
    assert state['review_independence'] == 'opposite_family'
    candidate = ex.candidate_path(state)
    candidate.parent.mkdir(parents=True, exist_ok=True)
    candidate.write_text(json.dumps({'questions': [{'id': 'q1', 'complete': False}], 'diagrams': []}))
    checked = ex.check('both')
    assert checked['stage'] == 'pending' and checked['problems']
    assert not checked.get('teaching_approved')
    with pytest.raises(ValueError, match='review'):
        ex.register('both')


def test_selected_worker_really_runs_and_resumes_to_separate_review(tmp_path, monkeypatch):
    ex = extraction()
    monkeypatch.setenv('STEM_EXTRACT_ROOT', str(tmp_path / 'Work'))
    monkeypatch.setenv('STEM_LIBRARY_ROOT', str(tmp_path / 'sources'))
    make_pdf(tmp_path / 'sources/book.pdf', ['Question'])
    fake = tmp_path / 'fake-provider'
    fake.write_text('#!/usr/bin/env python3\nimport os,json,hashlib\nfrom pathlib import Path\np=Path(os.environ["EXTRACT_OUTPUT"])\np.parent.mkdir(parents=True,exist_ok=True)\np.write_text(json.dumps({"questions":[],"diagrams":[],"source_coverage":[{"source_id":s["id"],"source_sha256":s["sha256"],"inspected_pages":list(range(1,s["pages"]+1)),"no_relevant_content":True,"reason":"No relevant content in synthetic source."} for s in json.loads(Path(os.environ["EXTRACT_TEST_STATE"]).read_text())["sources"]]} if os.environ["EXTRACT_ROLE"]=="extract" else {"verdict":"pending","findings":["no extracted content"],"inspected_images":[],"candidate_sha256":hashlib.sha256(Path(json.loads((p.parent/"state.json").read_text())["candidate"]).read_bytes()).hexdigest()}))\n')
    fake.chmod(0o755)
    monkeypatch.setenv('STEM_EXTRACT_CODEX', str(fake))
    ex.create('run', '9702', provider='codex', scope='questions')
    ex.inventory('run')
    ex.plan('run')
    with pytest.raises(ValueError, match='weekly'):
        ex.run('run')
    monkeypatch.setenv('EXTRACT_TEST_STATE', str(ex.job_dir('run') / 'state.json'))
    ex.run('run', weekly_remaining=90, wait=True)
    state = ex.load('run')
    assert state['jobs']['extract']['exit'] == 0
    ex.run('run', weekly_remaining=90, wait=True)
    state = ex.check('run')
    assert state['jobs']['review']['exit'] == 0
    assert state['stage'] == 'pending' and not state.get('teaching_approved')


def complete_coverage(state):
    rows = []
    for source in state['sources']:
        start, end = source.get('selected_pages') or [1, source['pages']]
        rows.append({'source_id': source['id'], 'source_sha256': source['sha256'],
                     'inspected_pages': list(range(start, end + 1)),
                     'no_relevant_content': False, 'reason': ''})
    return rows


def reviewed_diagram(ex, tmp_path, monkeypatch):
    from PIL import Image
    monkeypatch.setenv('STEM_EXTRACT_ROOT', str(tmp_path / 'Work'))
    monkeypatch.setenv('STEM_LIBRARY_ROOT', str(tmp_path / 'sources'))
    make_pdf(tmp_path / 'sources/book.pdf', ['A circuit'])
    graph = tmp_path / 'specs/9702/graph.json'
    graph.parent.mkdir(parents=True)
    graph.write_text(json.dumps({'subtopics': [{'id': '9702-1.1'}], 'kcs': [
        {'id': '9702-1.1.1', 'subtopic': '9702-1.1'}]}))
    monkeypatch.setenv('STEM_LIBRARY_SPECS', str(graph.parent.parent))
    ex.create('diagram', '9702', scope='diagrams')
    ex.inventory('diagram')
    state = ex.plan('diagram')
    path = ex.candidate_path(state)
    path.parent.mkdir(parents=True)
    Image.new('RGB', (200, 150), 'red').save(path.parent / 'circuit.png')
    source = state['sources'][0]
    record = {'id': 'circuit', 'complete': True, 'uncertainty': [],
              'regions': [{'source_id': source['id'], 'source_sha256': source['sha256'], 'page': 1, 'box': [0, 0, 1, 1]}],
              'syllabus': ['9702-1.1'], 'kcs': ['9702-1.1.1'], 'media': ['circuit.png'],
              'caption': 'Circuit', 'purpose': 'Explain current'}
    path.write_text(json.dumps({'questions': [], 'diagrams': [record], 'source_coverage': complete_coverage(state)}))
    with ex.state_lock('diagram') as current:
        current['jobs']['extract']['exit'] = 0
        current['jobs']['review']['exit'] = 0
    (ex.job_dir('diagram') / 'review.json').write_text(json.dumps({
        'candidate_sha256': ex.digest(path), 'verdict': 'pass', 'findings': [],
        'inspected_images': [ex.digest(path.parent / 'circuit.png')]}))
    return path


def test_reviewed_diagram_registers_immutable_provenance_but_not_teaching_approval(tmp_path, monkeypatch):
    from tutorlib.asset_library import AssetLibrary
    ex = extraction()
    path = reviewed_diagram(ex, tmp_path, monkeypatch)
    assert ex.check('diagram')['stage'] == 'reviewed'
    vault = tmp_path / 'vault'
    vault.mkdir()
    monkeypatch.setenv('STEM_TUTOR_VAULT', str(vault))
    result = ex.register('diagram')
    assert result['stage'] == 'registered' and result['teaching_approved'] is False
    catalog = AssetLibrary(vault)
    record = catalog.record(result['registrations'][0])
    assert '/9702/Diagrams/' in record['path']
    assert catalog.read(result['registrations'][0]) == (path.parent / 'circuit.png').read_bytes()
    assert record['provenance']['sidecars']
    from tutorlib.teach_actions import figures_for
    figures = figures_for(vault, '9702-1.1', kc='9702-1.1.1')
    assert len(figures) == 1 and figures[0]['caption'] == 'Circuit'
    assert figures[0]['why'] == 'Explain current'
    assert figures_for(vault, '9701-1.1', kc='9701-1.1.1') == []
    # A post-review pixel change is not covered by the original inspected hash.
    (path.parent / 'circuit.png').write_bytes((path.parent / 'circuit.png').read_bytes() + b'change')
    assert ex.check('diagram')['stage'] == 'pending'
    registered_image = vault / record['path']
    registered_image.write_bytes(registered_image.read_bytes() + b'tampered')
    assert figures_for(vault, '9702-1.1', kc='9702-1.1.1') == []


def test_candidate_course_prefix_is_not_a_validated_syllabus_mapping(tmp_path, monkeypatch):
    ex = extraction()
    path = reviewed_diagram(ex, tmp_path, monkeypatch)
    data = json.loads(path.read_text())
    data['diagrams'][0]['kcs'] = ['9702-99.99.99']
    path.write_text(json.dumps(data))
    review = ex.job_dir('diagram') / 'review.json'
    evidence = json.loads(review.read_text())
    evidence['candidate_sha256'] = ex.digest(path)
    review.write_text(json.dumps(evidence))
    state = ex.check('diagram')
    assert state['stage'] == 'pending' and any('graph' in problem for problem in state['problems'])


def test_existing_shared_ial_sources_have_explicit_math_applicability(tmp_path, monkeypatch):
    from tutorlib.asset_library import write_asset
    vault = tmp_path / 'vault'
    vault.mkdir()
    monkeypatch.delenv('STEM_LIBRARY_ROOT', raising=False)
    monkeypatch.setenv('STEM_TUTOR_VAULT', str(vault))
    pdf = make_pdf(tmp_path / 'spec.pdf', ['Pure Mathematics specification'])
    for name in ('ial-maths-spec.pdf', 'ial-maths-formula-book.pdf', 'unknown.pdf'):
        write_asset(vault, 'Library/Shared/Sources/Specifications/' + name, pdf.read_bytes())
    assert len(library.source_files('all', 'P1')) == 2
    assert library.source_files('all', '9702') == []


@pytest.mark.parametrize('first_part', ['', 'a'])
def test_question_parts_and_all_page_regions_remain_pending_until_complete(tmp_path, monkeypatch, first_part):
    ex = extraction()
    path = reviewed_diagram(ex, tmp_path, monkeypatch)
    state = ex.load('diagram')
    source = state['sources'][0]
    region = {'source_id': source['id'], 'source_sha256': source['sha256'], 'page': 1, 'box': [0, 0, 1, 1]}
    question = {'id': 'q1a', 'official_qid': '9702_s24_12_q1', 'part': first_part, 'kind': 'mcq',
                'complete': True, 'uncertainty': [], 'regions': [region], 'mark_scheme_regions': [region],
                'syllabus': ['9702-1.1'], 'kcs': ['9702-1.1.1'], 'prerequisites': [],
                'answer': 'A', 'media': ['circuit.png']}
    with ex.state_lock('diagram') as current:
        current['scope'] = 'questions'
    def save(records):
        path.write_text(json.dumps({'questions': records, 'diagrams': [], 'source_coverage': complete_coverage(state)}))
        review = ex.job_dir('diagram') / 'review.json'
        data = json.loads(review.read_text())
        data['candidate_sha256'] = ex.digest(path)
        review.write_text(json.dumps(data))
        return ex.check('diagram')
    assert save([question])['stage'] == 'reviewed'
    # Same-context identical copies are not silently dropped; conflicting answers are explicit.
    assert any('duplicate same-context' in issue for issue in save([question, question])['problems'])
    assert any('content conflict' in issue for issue in save([question, {**question, 'answer': 'B'}])['problems'])
    # Independently assessed part b retains its identity even with identical image bytes.
    assert save([question, {**question, 'id': 'q1b', 'part': 'b'}])['stage'] == 'reviewed'
    for invalid in ({'complete': False}, {'uncertainty': ['OCR uncertain']}, {'kind': 'structured'},
                    {'mark_scheme_regions': []}, {'regions': [region, {**region, 'page': 2}]}):
        assert save([{**question, **invalid}])['stage'] == 'pending'


@pytest.mark.parametrize('unknown_identity', [None, '', 'source-local-q1'])
def test_unknown_question_identities_are_not_evidence_of_duplicates(tmp_path, monkeypatch, unknown_identity):
    ex = extraction()
    path = reviewed_diagram(ex, tmp_path, monkeypatch)
    state = ex.load('diagram')
    state['scope'] = 'questions'
    source = state['sources'][0]
    region = {'source_id': source['id'], 'source_sha256': source['sha256'],
              'page': 1, 'box': [0, 0, 1, .4]}
    question = {'id': 'source-local-q1', 'official_qid': unknown_identity, 'part': 'a', 'kind': 'mcq',
                'complete': False, 'uncertainty': ['Official identity unavailable'],
                'regions': [region], 'mark_scheme_regions': [region],
                'syllabus': ['9702-1.1'], 'kcs': ['9702-1.1.1'], 'prerequisites': [],
                'answer': 'A', 'media': ['circuit.png']}
    other = {**question, 'id': 'source-local-q3', 'answer': 'B',
             'regions': [{**region, 'box': [0, .6, 1, 1]}]}
    path.write_text(json.dumps({'questions': [question, other], 'diagrams': [],
                               'source_coverage': complete_coverage(state)}))
    before = path.read_bytes()
    problems, _ = ex._candidate_problems(state)
    assert problems.count('official paper/session/variant/question identity is missing') == 2
    assert 'incomplete or uncertain extraction' in problems
    assert not any('duplicate same-context' in issue or 'content conflict' in issue for issue in problems)
    assert path.read_bytes() == before


@pytest.mark.parametrize('unknown_component', [
    {'part': None}, {'part': 1}, {'part': ['a']}, {'omit_part': True},
    {'kcs': []}, {'syllabus': []}, {'kcs': ['9702-1.1.999']}, {'syllabus': ['9702-9.9']},
])
def test_incomplete_assessed_context_is_not_evidence_of_question_conflict(tmp_path, monkeypatch, unknown_component):
    ex = extraction()
    path = reviewed_diagram(ex, tmp_path, monkeypatch)
    state = ex.load('diagram'); state['scope'] = 'questions'
    source = state['sources'][0]
    region = {'source_id': source['id'], 'source_sha256': source['sha256'],
              'page': 1, 'box': [0, 0, 1, .4]}
    question = {'id': 'source-q1', 'official_qid': '9702_s24_12_q1', 'part': 'a', 'kind': 'mcq',
                'complete': True, 'uncertainty': [], 'regions': [region], 'mark_scheme_regions': [region],
                'syllabus': ['9702-1.1'], 'kcs': ['9702-1.1.1'], 'prerequisites': [],
                'answer': 'A', 'media': ['circuit.png']}
    question.update(unknown_component)
    if question.pop('omit_part', False):
        question.pop('part')
    other = {**question, 'id': 'source-q3', 'answer': 'B',
             'regions': [{**region, 'box': [0, .6, 1, 1]}]}
    path.write_text(json.dumps({'questions': [question, other], 'diagrams': [],
                               'source_coverage': complete_coverage(state)}))
    before = path.read_bytes()
    problems, _ = ex._candidate_problems(state)
    assert any('part identity is missing' in p or 'mapping' in p for p in problems)
    assert not any('duplicate same-context' in p or 'content conflict' in p for p in problems)
    assert path.read_bytes() == before


def test_crop_stays_in_candidates_and_does_not_overwrite(tmp_path, monkeypatch):
    ex = extraction()
    path = reviewed_diagram(ex, tmp_path, monkeypatch)
    source = ex.load('diagram')['sources'][0]
    result = ex.crop('diagram', source['id'], 1, '0,0,1,1', 'media/page.png', 72)
    assert result['source_sha256'] == source['sha256']
    assert (path.parent / result['media']).is_file()
    with pytest.raises(ValueError, match='new PNG'):
        ex.crop('diagram', source['id'], 1, '0,0,1,1', 'media/page.png', 72)
    with pytest.raises(ValueError, match='candidate'):
        ex.crop('diagram', source['id'], 1, '0,0,1,1', '../escape.png', 72)


def test_exact_pdf_and_page_batch_selection_survives_restart(tmp_path, monkeypatch):
    ex = extraction()
    monkeypatch.setenv('STEM_EXTRACT_ROOT', str(tmp_path / 'Work'))
    monkeypatch.setenv('STEM_LIBRARY_ROOT', str(tmp_path / 'sources'))
    one = make_pdf(tmp_path / 'sources/one.pdf', ['one', 'two', 'three'])
    make_pdf(tmp_path / 'sources/other.pdf', ['unselected'])
    ex.create('selected', '9702', sources=[str(one)], pages='2-3')
    state = ex.inventory('selected')
    assert len(state['sources']) == 1
    assert state['sources'][0]['selected_pages'] == [2, 3]
    assert ex.load('selected')['requested_sources'] == [str(one)]


def test_full_course_inventory_requires_small_page_batches_before_paid_launch(tmp_path, monkeypatch):
    ex = extraction()
    monkeypatch.setenv('STEM_EXTRACT_ROOT', str(tmp_path / 'Work'))
    monkeypatch.setenv('STEM_LIBRARY_ROOT', str(tmp_path / 'sources'))
    make_pdf(tmp_path / 'sources/long.pdf', ['Question'] * 101)
    ex.create('too-large', '9702')
    ex.inventory('too-large')
    ex.plan('too-large')
    with pytest.raises(ValueError, match='100 pages'):
        ex.run('too-large', weekly_remaining=90)
    assert not ex.load('too-large')['jobs']['extract'].get('pid')


def test_publication_cannot_drop_a_reviewed_assessed_part(tmp_path, monkeypatch):
    from types import SimpleNamespace
    ex = extraction()
    path = reviewed_diagram(ex, tmp_path, monkeypatch)
    diagram = json.loads(path.read_text())['diagrams'][0]
    questions = [{**diagram, 'id': 'q1' + part, 'official_qid': '9702_s24_12_q1',
                  'part': part, 'kind': 'mcq', 'text': 'Synthetic MCQ fixture sentinel.', 'prerequisites': [], 'answer': 'A',
                  'mark_scheme_regions': diagram['regions']} for part in ('a', 'b')]
    path.write_text(json.dumps({'questions': questions, 'diagrams': [], 'source_coverage': complete_coverage(ex.load('diagram'))}))
    review_path = ex.job_dir('diagram') / 'review.json'
    review = json.loads(review_path.read_text())
    review['candidate_sha256'] = ex.digest(path)
    review_path.write_text(json.dumps(review))
    with ex.state_lock('diagram') as current:
        current['scope'] = 'questions'
    vault = tmp_path / 'vault'
    vault.mkdir()
    monkeypatch.setenv('STEM_TUTOR_VAULT', str(vault))
    state = ex.register('diagram')
    batch = tmp_path / 'batch'
    batch.mkdir()
    (batch / 'bank.json').write_text(json.dumps({'items': [{
        'source': {'qid': questions[1]['official_qid'], 'part': 'b'}, 'answer': 'A',
        'kcs': questions[1]['kcs'], 'image': state['registered_media']['circuit.png'],
        'topical': {'chapters': questions[1]['syllabus']}}]}))
    # The external publication boundary is deliberately not allowed in this test.
    monkeypatch.setitem(sys.modules, 'topicals', SimpleNamespace(publish=lambda *args: {'published': True}))
    with pytest.raises(ValueError, match='exactly.*part|bijection'):
        ex.publish('diagram', batch)
    from tutorlib.teach_actions import figures_for
    assert figures_for(vault, '9702-1.1', kc='9702-1.1.1') == []  # protected question media
    complete = []
    for row in questions:
        context = ex.hashlib.sha256(json.dumps(row, sort_keys=True).encode()).hexdigest()[:12]
        complete.append({'source': {'qid': row['official_qid'], 'part': row['part'],
                                   'extraction_regions': row['regions'],
                                   'mark_scheme_regions': row['mark_scheme_regions'],
                                   'extraction_prerequisites': row['prerequisites']},
                         'answer': row['answer'], 'stem': row['text'], 'kcs': row['kcs'],
                         'image': state['registered_records'][context]['circuit.png'],
                         'topical': {'chapters': row['syllabus'], 'requires': row['syllabus'], 'support': {}}})
    (batch / 'bank.json').write_text(json.dumps({'items': complete}))
    assert ex.publish('diagram', batch) == {'published': True}
    complete[0]['source']['extraction_regions'] = []
    (batch / 'bank.json').write_text(json.dumps({'items': complete}))
    with pytest.raises(ValueError, match='every reviewed mapping'):
        ex.publish('diagram', batch)


@pytest.mark.parametrize('order,primary,accepted', [
    ([0, 1], 0, True),  # primary aliases the first ordered page; it is not a third page
    ([0, 1], None, True),
    ([1, 0], 1, False),
    ([0, 1], 1, False),  # primary must alias the first page
    ([0, 1, 1], 0, False),
    ([0, 0, 1], 0, False),
])
def test_publication_preserves_reviewed_media_order_and_multiplicity(tmp_path, monkeypatch, order, primary, accepted):
    from types import SimpleNamespace
    from PIL import Image
    ex = extraction()
    path = reviewed_diagram(ex, tmp_path, monkeypatch)
    diagram = json.loads(path.read_text())['diagrams'][0]
    Image.new('RGB', (200, 150), 'blue').save(path.parent / 'continuation.png')
    question = {**diagram, 'id': 'ordered-q1', 'official_qid': '9702_s24_12_q1',
                'part': '', 'kind': 'mcq', 'text': 'Synthetic MCQ fixture sentinel.', 'prerequisites': [], 'answer': 'A',
                'regions': [diagram['regions'][0], {**diagram['regions'][0], 'box': [0, .5, 1, 1]}],
                'mark_scheme_regions': diagram['regions'], 'media': ['circuit.png', 'continuation.png']}
    path.write_text(json.dumps({'questions': [question], 'diagrams': [], 'source_coverage': complete_coverage(ex.load('diagram'))}))
    review_path = ex.job_dir('diagram') / 'review.json'
    review = json.loads(review_path.read_text())
    review.update(candidate_sha256=ex.digest(path), inspected_images=[ex.digest(path.parent / name) for name in question['media']])
    review_path.write_text(json.dumps(review))
    with ex.state_lock('diagram') as current:
        current['scope'] = 'questions'
    vault = tmp_path / 'vault'
    vault.mkdir()
    monkeypatch.setenv('STEM_TUTOR_VAULT', str(vault))
    state = ex.register('diagram')
    context = ex.hashlib.sha256(json.dumps(question, sort_keys=True).encode()).hexdigest()[:12]
    pages = [state['registered_records'][context][name] for name in question['media']]
    item = {'source': {'qid': question['official_qid'], 'part': '',
                       'extraction_regions': question['regions'],
                       'mark_scheme_regions': question['mark_scheme_regions'],
                       'extraction_prerequisites': []},
            'answer': 'A', 'stem': question['text'], 'kcs': question['kcs'], 'images': [pages[index] for index in order],
            'topical': {'chapters': question['syllabus'], 'requires': question['syllabus'], 'support': {}}}
    if primary is not None:
        item['image'] = pages[primary]
    batch = tmp_path / 'batch'
    batch.mkdir()
    (batch / 'bank.json').write_text(json.dumps({'items': [item]}))
    monkeypatch.setitem(sys.modules, 'topicals', SimpleNamespace(publish=lambda *args: {'published': True}))
    if accepted:
        assert ex.publish('diagram', batch) == {'published': True}
    else:
        with pytest.raises(ValueError, match='media|page'):
            ex.publish('diagram', batch)


def test_claude_worker_can_read_render_sources_but_only_crop_its_own_candidates(tmp_path, monkeypatch):
    import shlex
    ex = extraction()
    reviewed_diagram(ex, tmp_path, monkeypatch)
    monkeypatch.setenv('STEM_EXTRACT_CLAUDE', '/not-executed/claude')
    state = ex.load('diagram')
    command = ex.worker_command(state, 'extract')
    allowed = command[command.index('--allowedTools') + 1:command.index('--add-dir')]
    for action in ('text', 'figures', 'page'):
        relative = f'.venv/bin/python build/library.py {action}'
        absolute = shlex.join([str(ROOT / '.venv/bin/python'), str(ROOT / 'build/library.py'), action])
        assert f'Bash({relative} *)' in allowed
        assert f'Bash({absolute} *)' in allowed
    assert 'Bash(bin/extract crop diagram *)' in allowed
    assert f'Bash({shlex.join([str(ROOT / "bin/extract"), "crop", "diagram"])} *)' in allowed
    assert not any('build/library.py crop' in rule or 'build/library.py extract' in rule for rule in allowed)
    assert not any('register' in rule or 'publish' in rule or 'bin/extract *)' in rule for rule in allowed)
    assert 'Edit' in command[command.index('--tools') + 1].split(',')
    assert '.venv/bin/python build/library.py text' in command[command.index('-p') + 1]


def test_codex_job_model_choice_is_persisted_without_changing_shared_ladder(tmp_path, monkeypatch):
    ex = extraction()
    monkeypatch.setenv('STEM_EXTRACT_ROOT', str(tmp_path / 'Work'))
    monkeypatch.setenv('STEM_LIBRARY_ROOT', str(tmp_path / 'sources'))
    monkeypatch.setenv('STEM_EXTRACT_CODEX', '/usr/bin/codex')
    make_pdf(tmp_path / 'sources/book.pdf', ['A circuit'])
    original_config = (ROOT / 'foundry/config.json').read_bytes()
    ex.create('sol', '9702', provider='codex', scope='diagrams',
              codex_model='gpt-6.1-sol', codex_effort='low')
    ex.inventory('sol')
    state = ex.plan('sol')
    for role in ('extract', 'review'):
        command = ex.worker_command(state, role)
        assert command[command.index('-m') + 1] == 'gpt-6.1-sol'
        assert 'model_reasoning_effort="low"' in command
    assert ex.load('sol')['codex_model'] == 'gpt-6.1-sol'
    assert (ROOT / 'foundry/config.json').read_bytes() == original_config


def test_worker_contract_names_inclusive_page_range(tmp_path, monkeypatch):
    ex = extraction()
    monkeypatch.setenv('STEM_EXTRACT_ROOT', str(tmp_path / 'Work'))
    monkeypatch.setenv('STEM_LIBRARY_ROOT', str(tmp_path / 'sources'))
    make_pdf(tmp_path / 'sources/book.pdf', ['cover', 'diagram one', 'diagram two', 'end'])
    ex.create('range', '9702', provider='codex', pages='1-4')
    ex.inventory('range')
    state = ex.plan('range')
    contract = json.loads(ex._prompt(state, 'extract').split('JOB CONTRACT:\n')[1])
    assert contract['sources'][0]['selected_page_range'] == {'start': 1, 'end': 4, 'inclusive': True}
    assert 'selected_pages' not in contract['sources'][0]


def test_worker_reader_cache_stays_inside_writable_job_directory(tmp_path, monkeypatch):
    ex = extraction()
    monkeypatch.setenv('STEM_EXTRACT_ROOT', str(tmp_path / 'Work'))
    monkeypatch.setenv('STEM_LIBRARY_ROOT', str(tmp_path / 'sources'))
    monkeypatch.setenv('STEM_LIBRARY_CACHE', str(tmp_path / 'outside-sandbox'))
    make_pdf(tmp_path / 'sources/book.pdf', ['A diagram'])
    fake = tmp_path / 'fake-provider'
    fake.write_text('#!/usr/bin/env python3\nimport os,json\nfrom pathlib import Path\nPath(os.environ["EXTRACT_OUTPUT"]).write_text(json.dumps({"questions":[],"diagrams":[],"observed_cache":os.environ["STEM_LIBRARY_CACHE"]}))\n')
    fake.chmod(0o755)
    monkeypatch.setenv('STEM_EXTRACT_CODEX', str(fake))
    ex.create('cache', '9702', provider='codex')
    ex.inventory('cache')
    state = ex.plan('cache')
    ex.candidate_path(state).parent.mkdir(parents=True)
    ex._worker('cache', 'extract')
    data = json.loads(ex.candidate_path(state).read_text())
    assert data['observed_cache'] == str(ex.job_dir('cache') / 'reader-cache')


def test_worker_timeout_stops_child_and_records_one_failed_attempt(tmp_path, monkeypatch):
    import os
    import signal
    import subprocess
    ex = extraction()
    monkeypatch.setenv('STEM_EXTRACT_ROOT', str(tmp_path / 'Work'))
    monkeypatch.setenv('STEM_LIBRARY_ROOT', str(tmp_path / 'sources'))
    make_pdf(tmp_path / 'sources/book.pdf', ['A diagram'])
    ex.create('timeout', '9702', provider='codex')
    ex.inventory('timeout'); ex.plan('timeout')
    pidfile = tmp_path / 'fake-child.pid'
    child = (
        'import os,signal,time; from pathlib import Path; '
        'signal.signal(signal.SIGTERM,signal.SIG_IGN); '
        f'Path({str(pidfile)!r}).write_text(str(os.getpid())); time.sleep(60)'
    )
    parent = f'import subprocess,sys,time; subprocess.Popen([sys.executable,"-c",{child!r}]); time.sleep(60)'
    monkeypatch.setattr(ex, 'worker_command', lambda *args: [sys.executable, '-c', parent])
    captured = ex.worker_timeout.run_captured
    def short_deadline(command, *, seconds, **kwargs):
        assert seconds == 1800
        return captured(command, seconds=1, **kwargs)
    monkeypatch.setattr(ex.worker_timeout, 'run_captured', short_deadline)
    try:
        ex._worker('timeout', 'extract')
        state = ex.load('timeout')
        assert state['stage'] == 'pending'
        assert state['jobs']['extract']['finished']
        assert state['jobs']['extract']['ok'] is False
        assert len(state['reliability_failures']['1']['extract']) == 1
        assert not state['jobs']['review'].get('started')
        assert pidfile.exists(), 'synthetic child did not start; reproduction is inconclusive'
        status = subprocess.run(['/bin/ps', '-p', pidfile.read_text(), '-o', 'stat='],
                                capture_output=True, text=True).stdout.strip()
        assert not status or status.startswith('Z'), f'child survives extraction timeout: {status}'
    finally:
        if pidfile.exists():
            try:
                os.kill(int(pidfile.read_text()), signal.SIGKILL)
            except ProcessLookupError:
                pass


def test_missing_source_page_coverage_cannot_pass_review(tmp_path, monkeypatch):
    ex = extraction()
    path = reviewed_diagram(ex, tmp_path, monkeypatch)
    data = json.loads(path.read_text())
    data.pop('source_coverage', None)
    path.write_text(json.dumps(data))
    review_path = ex.job_dir('diagram') / 'review.json'
    review = json.loads(review_path.read_text()); review['candidate_sha256'] = ex.digest(path)
    review_path.write_text(json.dumps(review))
    state = ex.check('diagram')
    assert state['stage'] == 'pending'
    assert any('coverage' in issue for issue in state['problems'])


def test_empty_scope_requires_complete_page_coverage_and_explicit_reason(tmp_path, monkeypatch):
    ex = extraction()
    path = reviewed_diagram(ex, tmp_path, monkeypatch)
    state = ex.load('diagram'); source = state['sources'][0]
    coverage = {'source_id': source['id'], 'source_sha256': source['sha256'],
                'inspected_pages': [1], 'no_relevant_content': True,
                'reason': 'The selected source has text only and no teaching figures.'}
    def save(pages):
        coverage['inspected_pages'] = pages
        path.write_text(json.dumps({'questions': [], 'diagrams': [], 'source_coverage': [coverage]}))
        review_path = ex.job_dir('diagram') / 'review.json'
        review = json.loads(review_path.read_text()); review['candidate_sha256'] = ex.digest(path)
        review_path.write_text(json.dumps(review))
    save([1])
    assert ex.check('diagram')['stage'] == 'reviewed'
    save([])
    checked = ex.check('diagram')
    assert checked['stage'] == 'pending'
    assert any('coverage' in issue for issue in checked['problems'])


def test_coverage_rejects_skipped_interior_pages():
    ex = extraction()
    state = {'sources': [{'id': 'source', 'sha256': 'abc', 'pages': 4, 'selected_pages': [1, 4]}]}
    data = {'questions': [], 'diagrams': [], 'source_coverage': [
        {'source_id': 'source', 'source_sha256': 'abc', 'inspected_pages': [1, 4],
         'no_relevant_content': True, 'reason': 'No figures on inspected pages.'}]}
    assert any('every selected page' in issue for issue in ex._coverage(state, data))
    data['source_coverage'][0]['inspected_pages'] = [1, 2, 3, 4]
    assert ex._coverage(state, data) == []


def test_worker_counts_missing_page_coverage_as_failure_before_review(tmp_path, monkeypatch):
    ex = extraction()
    monkeypatch.setenv('STEM_EXTRACT_ROOT', str(tmp_path / 'Work'))
    monkeypatch.setenv('STEM_LIBRARY_ROOT', str(tmp_path / 'sources'))
    make_pdf(tmp_path / 'sources/book.pdf', ['A diagram'])
    fake = tmp_path / 'fake-provider'
    fake.write_text('#!/usr/bin/env python3\nimport os,json\nfrom pathlib import Path\nPath(os.environ["EXTRACT_OUTPUT"]).write_text(json.dumps({"questions":[],"diagrams":[]}))\n')
    fake.chmod(0o755)
    monkeypatch.setenv('STEM_EXTRACT_CODEX', str(fake))
    ex.create('missing-coverage', '9702', provider='codex')
    ex.inventory('missing-coverage')
    state = ex.plan('missing-coverage')
    ex.candidate_path(state).parent.mkdir(parents=True)
    ex._worker('missing-coverage', 'extract')
    result = ex.load('missing-coverage')
    assert result['jobs']['extract']['exit'] != 0
    assert len(result['reliability_failures']['1']['extract']) == 1
    assert not result['jobs']['review'].get('started')


@pytest.mark.parametrize('malformation', ['source-id-list', 'regions-null', 'record-not-object'])
def test_malformed_worker_shapes_finish_pending_and_count_failure(tmp_path, monkeypatch, malformation):
    ex = extraction()
    monkeypatch.setenv('STEM_EXTRACT_ROOT', str(tmp_path / 'Work'))
    monkeypatch.setenv('STEM_LIBRARY_ROOT', str(tmp_path / 'sources'))
    make_pdf(tmp_path / 'sources/book.pdf', ['A diagram'])
    ex.create('malformed', '9702', provider='codex')
    ex.inventory('malformed'); state = ex.plan('malformed')
    coverage = complete_coverage(state)
    data = {'questions': [], 'diagrams': [], 'source_coverage': coverage}
    if malformation == 'source-id-list':
        coverage[0]['source_id'] = []
    elif malformation == 'regions-null':
        data['diagrams'] = [{'regions': None}]
    else:
        data['diagrams'] = ['not an object']
    payload = tmp_path / 'malformed.json'; payload.write_text(json.dumps(data))
    monkeypatch.setenv('EXTRACT_TEST_PAYLOAD', str(payload))
    fake = tmp_path / 'fake-provider'
    fake.write_text('#!/usr/bin/env python3\nimport os,shutil\nshutil.copyfile(os.environ["EXTRACT_TEST_PAYLOAD"],os.environ["EXTRACT_OUTPUT"])\n')
    fake.chmod(0o755); monkeypatch.setenv('STEM_EXTRACT_CODEX', str(fake))
    ex.candidate_path(state).parent.mkdir(parents=True)
    ex._worker('malformed', 'extract')
    result = ex.load('malformed')
    assert result['stage'] == 'pending'
    assert result['jobs']['extract']['finished']
    assert result['jobs']['extract']['exit'] != 0
    assert len(result['reliability_failures']['1']['extract']) == 1
    assert ex.candidate_path(state).read_bytes() == payload.read_bytes()


def test_mark_scheme_source_counts_as_relevant_covered_content():
    ex = extraction()
    state = {'sources': [{'id': name, 'sha256': name + '-sha', 'pages': 1} for name in ('qp', 'ms')]}
    data = {'questions': [{'regions': [{'source_id': 'qp'}], 'mark_scheme_regions': [{'source_id': 'ms'}]}],
            'diagrams': [], 'source_coverage': complete_coverage(state)}
    assert ex._coverage(state, data) == []


@pytest.mark.parametrize('failed_role', ['extract', 'review', 'review-images'])
@pytest.mark.parametrize('poll_count', [0, 3])
def test_two_failed_gate_attempts_block_third_without_counting_check_polls(tmp_path, monkeypatch, failed_role, poll_count):
    actual_role = 'extract' if failed_role == 'extract' else 'review'
    monkeypatch.setenv('EXTRACT_TEST_REVIEW_VERDICT', 'pass' if failed_role == 'review-images' else 'pending')
    ex = extraction()
    candidate = reviewed_diagram(ex, tmp_path, monkeypatch)
    data = json.loads(candidate.read_text())
    if failed_role == 'extract':
        data['diagrams'][0]['complete'] = False
        data['diagrams'][0]['uncertainty'] = ['Unresolved source detail.']
    payload = tmp_path / 'payload.json'; payload.write_text(json.dumps(data))
    monkeypatch.setenv('EXTRACT_TEST_PAYLOAD', str(payload))
    monkeypatch.setenv('EXTRACT_TEST_CANDIDATE', str(candidate))
    fake = tmp_path / 'fake-provider'
    fake.write_text('''#!/usr/bin/env python3
import hashlib,json,os,shutil
from pathlib import Path
p=Path(os.environ['EXTRACT_OUTPUT'])
if os.environ['EXTRACT_ROLE']=='extract':
    shutil.copyfile(os.environ['EXTRACT_TEST_PAYLOAD'],p)
else:
    p.write_text(json.dumps({'candidate_sha256':hashlib.sha256(Path(os.environ['EXTRACT_TEST_CANDIDATE']).read_bytes()).hexdigest(),'verdict':os.environ['EXTRACT_TEST_REVIEW_VERDICT'],'findings':[] if os.environ['EXTRACT_TEST_REVIEW_VERDICT']=='pass' else ['Source finding remains unresolved.'],'inspected_images':[]}))
''')
    fake.chmod(0o755); monkeypatch.setenv('STEM_EXTRACT_CODEX', str(fake))
    with ex.state_lock('diagram') as state:
        state['jobs'] = {'extract': {'provider': 'codex'}, 'review': {'provider': 'codex'}}
    ex.run('diagram', weekly_remaining=90, wait=True)
    if actual_role == 'review':
        ex.run('diagram', weekly_remaining=90, wait=True)
    for _ in range(poll_count):
        ex.check('diagram')
    first_count = len(ex.load('diagram').get('reliability_failures', {}).get('1', {}).get(actual_role, []))
    ex.run('diagram', weekly_remaining=90, wait=True, retry=actual_role)
    if poll_count:
        ex.check('diagram')
    second_count = len(ex.load('diagram').get('reliability_failures', {}).get('1', {}).get(actual_role, []))
    with pytest.raises(ValueError, match='paused after 2 failures'):
        ex.run('diagram', weekly_remaining=90, wait=True, retry=actual_role)
    assert first_count == 1
    assert second_count == 2


def test_stale_review_after_candidate_edit_is_not_a_new_failed_attempt(tmp_path, monkeypatch):
    ex = extraction()
    path = reviewed_diagram(ex, tmp_path, monkeypatch)
    with ex.state_lock('diagram') as state:
        state['jobs']['review'].update(started='attempt-1', finished='attempt-1-finished')
    data = json.loads(path.read_text()); data['diagrams'][0]['caption'] += ' (clarified)'
    path.write_text(json.dumps(data))
    checked = ex.check('diagram')
    assert checked['stage'] == 'pending'
    assert 'review is not bound to current candidate bytes' in checked['problems']
    assert not checked.get('reliability_failures', {}).get('1', {}).get('review')


def test_manual_invalid_edit_does_not_charge_the_prior_extraction_attempt(tmp_path, monkeypatch):
    ex = extraction()
    path = reviewed_diagram(ex, tmp_path, monkeypatch)
    with ex.state_lock('diagram') as state:
        state['jobs']['extract'].update(started='attempt-1', finished='finished-1', output_sha256=ex.digest(path))
    data = json.loads(path.read_text()); data['diagrams'][0]['complete'] = False
    path.write_text(json.dumps(data))
    checked = ex.check('diagram')
    assert checked['stage'] == 'pending'
    assert not checked.get('reliability_failures', {}).get('1', {}).get('extract')


def test_review_launch_checks_candidate_before_paying_another_worker(tmp_path, monkeypatch):
    ex = extraction()
    fake = tmp_path / 'fake-review'
    fake.write_text('#!/bin/sh\nexit 9\n')
    fake.chmod(0o755)
    monkeypatch.setenv('STEM_EXTRACT_CODEX', str(fake))
    path = reviewed_diagram(ex, tmp_path, monkeypatch)
    data = json.loads(path.read_text()); data['diagrams'][0]['complete'] = False
    path.write_text(json.dumps(data))
    with ex.state_lock('diagram') as state:
        state['jobs']['review'] = {'provider': 'codex'}
    with pytest.raises(ValueError, match='candidate validation failed before review'):
        ex.run('diagram', weekly_remaining=90)
    assert not ex.load('diagram')['jobs']['review'].get('started')


def test_valid_empty_scope_review_needs_no_candidate_image_hashes(tmp_path, monkeypatch):
    ex = extraction()
    path = reviewed_diagram(ex, tmp_path, monkeypatch)
    state = ex.load('diagram'); source = state['sources'][0]
    path.write_text(json.dumps({'questions': [], 'diagrams': [], 'source_coverage': [
        {'source_id': source['id'], 'source_sha256': source['sha256'], 'inspected_pages': [1],
         'no_relevant_content': True, 'reason': 'The selected source has no relevant figures.'}]}))
    monkeypatch.setenv('EXTRACT_TEST_CANDIDATE', str(path))
    fake = tmp_path / 'fake-review'
    fake.write_text('''#!/usr/bin/env python3
import hashlib,json,os
from pathlib import Path
Path(os.environ['EXTRACT_OUTPUT']).write_text(json.dumps({'candidate_sha256':hashlib.sha256(Path(os.environ['EXTRACT_TEST_CANDIDATE']).read_bytes()).hexdigest(),'verdict':'pass','findings':[],'inspected_images':[]}))
''')
    fake.chmod(0o755); monkeypatch.setenv('STEM_EXTRACT_CODEX', str(fake))
    with ex.state_lock('diagram') as current:
        current['jobs']['review'] = {'provider': 'codex'}
    ex._worker('diagram', 'review')
    result = ex.check('diagram')
    assert result['stage'] == 'reviewed'
    assert not result.get('reliability_failures', {}).get('1', {}).get('review')


def test_region_order_is_per_source_and_reversed_same_source_still_fails():
    ex = extraction()
    sources = {name: {'sha256': name + '-sha', 'pages': 5, 'selected_pages': [1, 5]} for name in ('notes-a', 'notes-b')}
    def region(source, page):
        return {'source_id': source, 'source_sha256': source + '-sha', 'page': page, 'box': [0, 0, 1, 1]}
    # A real duplicate notes table spans pages 2–3 in each of two source PDFs.
    record = {'regions': [region('notes-a', 2), region('notes-a', 3), region('notes-b', 2), region('notes-b', 3)]}
    assert ex._regions(record, sources) == []
    record['regions'] = [region('notes-a', 3), region('notes-b', 1), region('notes-a', 2)]
    assert 'regions: pages are out of order' in ex._regions(record, sources)


def external_prerequisite_candidate(ex, tmp_path, monkeypatch, prerequisite='P1-1.1', *, declared=True):
    path = reviewed_diagram(ex, tmp_path, monkeypatch)
    state = ex.load('diagram')
    state['scope'] = 'questions'
    data = json.loads(path.read_text())
    question = {**data['diagrams'][0], 'official_qid': '9702_s24_12_q1', 'part': '',
                'kind': 'mcq', 'answer': 'A', 'prerequisites': [prerequisite],
                'mark_scheme_regions': data['diagrams'][0]['regions']}
    data.update(questions=[question], diagrams=[])
    path.write_text(json.dumps(data))
    graph = tmp_path / 'specs/9702/graph.json'
    content = json.loads(graph.read_text())
    content['kcs'][0]['prereqs'] = [prerequisite] if declared else []
    graph.write_text(json.dumps(content))
    target = tmp_path / 'specs/P1/graph.json'
    target.parent.mkdir(parents=True)
    target.write_text(json.dumps({'subtopics': [{'id': 'P1-1'}], 'kcs': [
        {'id': 'P1-1.1', 'subtopic': 'P1-1'}]}))
    return state, target


@pytest.mark.parametrize('prerequisite', ['P1-1', 'P1-1.1'])
def test_declared_external_prerequisite_validates_against_target_graph(tmp_path, monkeypatch, prerequisite):
    ex = extraction()
    state, _ = external_prerequisite_candidate(ex, tmp_path, monkeypatch, prerequisite)
    before = ex.digest(ex.candidate_path(state))
    problems, _ = ex._candidate_problems(state)
    assert 'course graph does not validate prerequisites' not in problems
    assert problems == []
    assert ex.digest(ex.candidate_path(state)) == before
    assert not state.get('teaching_approved')


@pytest.mark.parametrize('case', ['undeclared', 'declared_by_unmapped_KC', 'missing_target',
                                  'unknown_target_ID', 'candidate_local_ID', 'unknown_same_course'])
def test_external_prerequisite_requires_exact_mapped_KC_declaration_and_target(tmp_path, monkeypatch, case):
    ex = extraction()
    prerequisite = {'unknown_target_ID': 'P1-99.1', 'candidate_local_ID': 'source-q1-a',
                    'unknown_same_course': '9702-99.1'}.get(case, 'P1-1.1')
    state, target = external_prerequisite_candidate(ex, tmp_path, monkeypatch, prerequisite,
                                                    declared=case not in ('undeclared', 'declared_by_unmapped_KC'))
    if case == 'missing_target':
        target.unlink()
    if case == 'declared_by_unmapped_KC':
        graph = tmp_path / 'specs/9702/graph.json'
        data = json.loads(graph.read_text())
        data['kcs'].append({'id': '9702-1.1.2', 'subtopic': '9702-1.1', 'prereqs': [prerequisite]})
        graph.write_text(json.dumps(data))
    problems, _ = ex._candidate_problems(state)
    assert 'course graph does not validate prerequisites' in problems


@pytest.mark.parametrize('tampered', [False, True])
def test_external_prerequisite_library_graph_adapter_verifies_registered_hash(tmp_path, monkeypatch, tampered):
    from tutorlib.asset_library import AssetLibrary, write_asset
    ex = extraction()
    state, target = external_prerequisite_candidate(ex, tmp_path, monkeypatch)
    vault = tmp_path / 'vault'
    vault.mkdir()
    ref = write_asset(vault, 'Library/Courses/P1/Specifications/graph.json', target.read_bytes())
    original = AssetLibrary(vault).resolve(ref)
    target.unlink()
    target.symlink_to(original)
    if tampered:
        original.write_text(original.read_text() + ' ')
    problems, _ = ex._candidate_problems(state)
    assert ('course graph does not validate prerequisites' in problems) is tampered
