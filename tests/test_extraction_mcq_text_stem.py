"""Reviewed literal MCQ text crosses publication without rewriting its evidence."""
import json
from pathlib import Path

import pytest
from PIL import Image

from test_extraction_mcq_media_privacy import direct_prepared, prepared


LITERAL_TEXT = '  Which quantity is a vector?\nA displacement\nB distance\nC speed\nD time\n'


def test_text_only_native_mcq_reaches_runtime_with_exact_text_and_ordered_public_media(tmp_path, monkeypatch):
    from tutorlib import packs, session, store, views

    ex, vault, path, q, save = prepared(tmp_path, monkeypatch, with_reference=True)
    q.pop('stem')
    q['text'] = LITERAL_TEXT
    Image.new('RGB', (20, 20), 'yellow').save(path.parent / 'question2.png')
    q['media'].insert(1, 'question2.png')
    q['question_media'].append('question2.png')
    q['media_regions']['question2.png'] = {**q['regions'][0], 'box': [0, .1, 1, 1]}
    save()
    review = ex.job_dir('multi') / 'review.json'
    sources = [Path(source['path']) for source in ex.load('multi')['sources']]
    frozen = {p: p.read_bytes() for p in [path, review, *sources]}
    events = vault / '.tutor/events/preserved.jsonl'
    event_bytes = events.read_bytes()
    registered = ex.register('multi')
    mapping = next(iter(registered['registered_records'].values()))
    batch = tmp_path / 'batch'
    ex.prepare_publication('multi', batch)
    item = json.loads((batch / 'bank.json').read_text())['items'][0]
    public = [mapping[name] for name in ['question.png', 'question2.png', 'reference.png']]
    assert item['stem'] == LITERAL_TEXT
    assert item['images'] == public
    assert item['source']['qid'] == '9702_s23_22_q1'
    assert item['source']['extraction_regions'] == q['regions']
    assert item['source']['mark_scheme_regions'] == q['mark_scheme_regions']
    assert item['source']['extraction_prerequisites'] == []
    assert item['source']['candidate_sha256'] == ex.digest(path)
    assert item['kind'] == 'mcq' and item['marks'] == 1 and item['difficulty'] == 3
    assert item['kcs'] == ['9702-2.1.1']
    assert item['options'] == {'A': 'displacement', 'B': 'distance', 'C': 'speed', 'D': 'time'}
    ex.publish('multi', batch)
    runtime = packs.Packs(store.Vault(vault))
    assert not runtime.topical_errors
    assert runtime.topicals.items[0]['stem'] == LITERAL_TEXT
    tutor = session.Tutor(store.Vault(vault))
    assert 'error' not in tutor.start('topical', focus=['9702-2.1'], topical_count=1, topical_types=['mcq'])
    view = tutor.next()['items'][0]
    assert 'Which quantity is a vector?' in view['stem']
    assert view['images'] == public
    assert 'answer' not in view
    assert mapping['scheme.png'] not in json.dumps(view)
    assert mapping['scheme.png'] not in views.question_block(view, vault_root=vault)
    assert {p: p.read_bytes() for p in frozen} == frozen
    assert events.read_bytes() == event_bytes


def test_explicit_reviewed_mcq_stem_takes_precedence_over_different_text(tmp_path, monkeypatch):
    ex, _, _, q, save = prepared(tmp_path, monkeypatch)
    q.update(stem='  Exact reviewed task.\n', text=LITERAL_TEXT)
    save()
    ex.register('multi')
    batch = tmp_path / 'explicit'
    ex.prepare_publication('multi', batch)
    assert json.loads((batch / 'bank.json').read_text())['items'][0]['stem'] == '  Exact reviewed task.\n'
    ex.publish('multi', batch)


@pytest.mark.parametrize('native', ['focused', 'direct'])
@pytest.mark.parametrize('fields', [
    {}, {'text': ''}, {'text': ' \n\t'}, {'text': None}, {'text': 7}, {'text': []}, {'text': {}},
    {'stem': '', 'text': LITERAL_TEXT}, {'stem': ' \n', 'text': LITERAL_TEXT},
    {'stem': None, 'text': LITERAL_TEXT}, {'stem': 7, 'text': LITERAL_TEXT},
    {'stem': [], 'text': LITERAL_TEXT}, {'stem': {}, 'text': LITERAL_TEXT},
])
def test_native_mcq_rejects_missing_or_invalid_selected_text_before_review(tmp_path, monkeypatch, fields, native):
    import capabilities
    monkeypatch.setattr(capabilities, 'preflight', lambda: pytest.fail('invalid MCQ reached provider preflight'))
    fixture = prepared if native == 'focused' else direct_prepared
    name = 'multi' if native == 'focused' else 'direct'
    ex, _, path, q, save = fixture(tmp_path, monkeypatch)
    q.pop('stem', None)
    q.pop('text', None)
    q.update(fields)
    save()
    frozen = path.read_bytes()
    problems, _ = ex._candidate_problems(ex.load(name))
    assert any('MCQ' in problem and ('stem' in problem or 'text' in problem) for problem in problems), problems
    with pytest.raises(ValueError, match='candidate validation failed before review:.*(stem|text)'):
        ex.run(name, weekly_remaining=89, retry='review')
    checked = ex.check(name)
    assert checked['stage'] == 'pending', checked['problems']
    with pytest.raises(ValueError, match='validation.*registration'):
        ex.register(name)
    assert path.read_bytes() == frozen


@pytest.mark.parametrize('text_only', [False, True])
def test_mcq_publication_rejects_prepared_stem_replaced_after_review(tmp_path, monkeypatch, text_only):
    ex, vault, _, q, save = prepared(tmp_path, monkeypatch)
    q['text'] = LITERAL_TEXT
    if text_only:
        q.pop('stem')
    save()
    ex.register('multi')
    batch = tmp_path / 'tampered'
    ex.prepare_publication('multi', batch)
    bank = json.loads((batch / 'bank.json').read_text())
    bank['items'][0]['stem'] = 'Unreviewed replacement question.'
    (batch / 'bank.json').write_text(json.dumps(bank))
    with pytest.raises(ValueError, match='reviewed.*stem'):
        ex.publish('multi', batch)
    assert not (vault / '.tutor/topicals/CURRENT').exists()


@pytest.mark.parametrize('native', ['focused', 'direct'])
@pytest.mark.parametrize('fields, expected', [
    ({'text': LITERAL_TEXT}, LITERAL_TEXT),
    ({'stem': '  Exact reviewed task.\n', 'text': LITERAL_TEXT}, '  Exact reviewed task.\n'),
    ({'stem': LITERAL_TEXT, 'text': None}, LITERAL_TEXT),
])
def test_native_mcq_valid_selected_text_passes_preflight_unchanged(tmp_path, monkeypatch, native, fields, expected):
    fixture = prepared if native == 'focused' else direct_prepared
    name = 'multi' if native == 'focused' else 'direct'
    ex, _, path, q, save = fixture(tmp_path, monkeypatch)
    q.pop('stem', None)
    q.pop('text', None)
    q.update(fields)
    save()
    frozen = path.read_bytes()
    assert ex._candidate_problems(ex.load(name))[0] == []
    checked = ex.check(name)
    assert checked['stage'] == 'reviewed', checked['problems']
    ex.register(name)
    batch = tmp_path / 'valid'
    ex.prepare_publication(name, batch)
    assert json.loads((batch / 'bank.json').read_text())['items'][0]['stem'] == expected
    assert path.read_bytes() == frozen


def test_legacy_unfocused_media_only_mcq_keeps_registration_compatibility(tmp_path, monkeypatch):
    from test_extraction_structured import structured_case
    ex, path, q, _, save = structured_case(tmp_path, monkeypatch)
    q.update(kind='mcq', answer='A', media=['circuit.png'])
    for key in ('stem', 'text', 'question_media', 'mark_scheme_media'):
        q.pop(key, None)
    save()
    frozen = path.read_bytes()
    assert ex._candidate_problems(ex.load('diagram'))[0] == []
    assert ex.check('diagram')['stage'] == 'reviewed'
    ex.register('diagram')
    assert path.read_bytes() == frozen
    with pytest.raises(ValueError, match='MCQ text'):
        ex.prepare_publication('diagram', tmp_path / 'legacy-invalid-publication')
