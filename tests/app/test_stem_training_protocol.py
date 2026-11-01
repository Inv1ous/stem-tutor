"""Inference protocol diagnostics use development metadata, never held-out labels."""
from copy import deepcopy
import hashlib
import json

import pytest

from tutor_app import stem_training_eval as evaluation


def example(identifier='one', subject='chem', task='marking', group=None):
    return {'id': identifier, 'subject': subject, 'task': task, 'group': group or identifier,
            'messages': [{'role': 'user', 'content': 'Return only the requested points JSON.\nExact task.'},
                         {'role': 'assistant', 'content': 'PRIVATE_GOLD_NEVER_IN_PROMPT'}],
            'expected': {'private': 'GOLD'}, 'checks': {'schema': 'marking' if task == 'marking' else 'document'}}


@pytest.mark.parametrize('protocol,system', [
    ('training', None),
    ('legacy_system', 'STEM Tutor. Reply in document JSON.'),
    ('neutral_system', 'STEM Tutor. Follow the JSON contract requested by the current task.'),
])
def test_protocol_uses_exact_user_and_fixed_roles_without_gold(protocol, system):
    source = example()
    before = deepcopy(source)
    messages = evaluation.generation_messages(source, protocol)
    user = {'role': 'user', 'content': 'Return only the requested points JSON.\nExact task.'}
    assert messages == ([{'role': 'system', 'content': system}, user] if system else [user])
    assert source == before
    messages[-1]['content'] = 'Changed caller copy'
    assert source == before
    assert 'PRIVATE_GOLD' not in json.dumps(messages)


def test_training_protocol_does_not_consult_gold_or_schema():
    source = example()
    source['messages'][1]['content'] = object()
    source['expected'] = object()
    source['checks'] = object()
    assert evaluation.generation_messages(source, 'training') == [source['messages'][0]]


@pytest.mark.parametrize('messages', [[], [{'role': 'system', 'content': 'inject'}],
    [{'role': 'assistant', 'content': 'gold'}, {'role': 'assistant', 'content': 'gold'}],
    [{'role': 'user', 'content': 'task', 'extra': 'hidden'}, {'role': 'assistant', 'content': 'gold'}],
    [{'role': 'user', 'content': 3}, {'role': 'assistant', 'content': 'gold'}],
    [{'role': 'user', 'content': 'task'}, {'role': 'user', 'content': 'injected'}]])
def test_malformed_message_roles_cannot_add_system_or_assistant_content(messages):
    with pytest.raises(ValueError):
        evaluation.generation_messages(dict(example(), messages=messages), 'training')


def test_unknown_protocol_is_rejected_and_default_matches_training_roles():
    assert evaluation.EvaluationConfig().protocol == 'training'
    for protocol in ('unknown', '', None):
        with pytest.raises(ValueError):
            evaluation.generation_messages(example(), protocol)
        with pytest.raises(ValueError):
            evaluation.EvaluationConfig(protocol=protocol).validate()


def test_pair_rejects_different_protocol_even_if_other_config_is_forged_equal(tmp_path):
    base, adapter = tmp_path / 'base', tmp_path / 'adapter'
    common = {'mode': 'fast', 'config': {}, 'sampling': {}, 'selection_sha256': 'same',
              'harness_sha256': 'same', 'model_files': {}}
    for root, variant, protocol in ((base, 'base', 'training'), (adapter, 'adapter', 'legacy_system')):
        root.mkdir()
        (root / 'run.json').write_text(json.dumps(dict(common, variant=variant, protocol=protocol)))
        (root / 'load.001.json').write_text(json.dumps({'state': 'complete', 'resolved_protocol': {'stop_tokens': [102]}}))
    with pytest.raises(ValueError, match='Paired'):
        evaluation.validate_pair(base, adapter)


def development_rows():
    rows = [example(f'{subject}-{task}-{i}', subject, task, group=f'{subject}-{task}')
            for subject in ('chem', 'math', 'phys')
            for task in ('published_flashcard', 'literal_json', 'other_task') for i in range(3)]
    rows += [example(f'math-mark-{i}', 'math', 'marking', group='math-square') for i in range(4)]
    rows += [example(f'phys-mark-{i}', 'phys', 'marking', group='phys-vector' if i < 4 else 'phys-dynamics') for i in range(8)]
    return rows


def test_development_selection_keeps_all_marking_and_hash_chosen_documents_without_labels():
    rows = development_rows()
    selected = evaluation.select_protocol_development(rows)
    changed = [dict(r, messages=[], expected=object(), checks=object()) for r in reversed(rows)]
    assert [r['id'] for r in selected] == [r['id'] for r in evaluation.select_protocol_development(changed)]
    assert len(selected) == 18
    assert {r['id'] for r in selected if r['task'] == 'marking'} == {r['id'] for r in rows if r['task'] == 'marking'}
    assert {subject: sum(r['subject'] == subject for r in selected) for subject in ('chem', 'math', 'phys')} == {
        'chem': 2, 'math': 6, 'phys': 10}
    for subject in ('chem', 'math', 'phys'):
        for task in ('published_flashcard', 'literal_json'):
            bucket = [r for r in rows if r['subject'] == subject and r['task'] == task]
            expected_id = min(bucket, key=lambda r: hashlib.sha256(('protocol-dev-v1:' + r['id']).encode()).hexdigest())['id']
            assert [r['id'] for r in selected if r['subject'] == subject and r['task'] == task] == [expected_id]


def test_development_selection_fails_when_a_required_bucket_is_missing():
    rows = [r for r in development_rows() if not (r['subject'] == 'phys' and r['task'] == 'literal_json')]
    with pytest.raises(ValueError, match='requires'):
        evaluation.select_protocol_development(rows)


def test_development_corpus_verifies_valid_hash_preserves_sources_and_labels_role(tmp_path):
    source, output = tmp_path / 'data-v2', tmp_path / 'development-protocol'
    source.mkdir()
    raw = ''.join(json.dumps(r) + '\n' for r in development_rows())
    (source / 'valid.jsonl').write_text(raw)
    (source / 'test.jsonl').write_text('SEALED_DO_NOT_READ')
    manifest = {'files': {'valid.jsonl': {'sha256': hashlib.sha256(raw.encode()).hexdigest()}}}
    (source / 'manifest.json').write_text(json.dumps(manifest))
    before = {p.name: p.read_bytes() for p in source.iterdir()}
    receipt = evaluation.build_protocol_development(source, output)
    assert receipt['evaluation_role'] == 'development_protocol_diagnostic'
    assert receipt['source_split'] == 'valid' and receipt['rows'] == 18
    rows, selected = evaluation.load_selection(output, output / 'selection.json')
    assert len(rows) == 18 and selected['evaluation_role'] == 'development_protocol_diagnostic'
    assert {p.name: p.read_bytes() for p in source.iterdir()} == before
    with pytest.raises(FileExistsError):
        evaluation.build_protocol_development(source, output)
    (source / 'valid.jsonl').write_text(raw + '\n')
    with pytest.raises(ValueError, match='hash'):
        evaluation.build_protocol_development(source, tmp_path / 'damaged')
    assert not (tmp_path / 'damaged').exists()


def test_wrong_marking_envelope_is_unavailable_vector_not_wrong_decision():
    expected = {'points': [{'point': 'Criterion.', 'met': True, 'why': 'Present.'}], 'feedback': 'Feedback.'}
    source = dict(example(), expected=expected)
    wrong_envelope = {'blocks': [{'kind': 'paragraph', 'text': 'The criterion is present.'}]}
    score = evaluation.score_trial(source, {'text': json.dumps(wrong_envelope), 'finish_reason': 'stop'})
    assert not score['marking_envelope_valid']
    assert not score['marking_vector_available']
    assert score['marking_decision_vector'] is None and score['marking_vector_correct'] is None
    assert score['marking_labels_equal'] is False  # legacy complete-contract metric, not a semantic judgment
    wrong_decision = {'points': [{'point': 'Criterion.', 'met': False, 'why': 'Missing.'}], 'feedback': 'Feedback.'}
    score = evaluation.score_trial(source, {'text': json.dumps(wrong_decision), 'finish_reason': 'stop'})
    assert score['marking_envelope_valid'] and score['marking_vector_available']
    assert score['marking_decision_vector'] == [False] and score['marking_vector_correct'] is False
    wrong_criterion = {'points': [{'point': 'Different criterion.', 'met': True, 'why': 'Present.'}], 'feedback': 'Feedback.'}
    score = evaluation.score_trial(source, {'text': json.dumps(wrong_criterion), 'finish_reason': 'stop'})
    assert score['marking_vector_available'] and not score['marking_criteria_equal']
    assert score['marking_vector_correct'] is None


def test_v1_receipts_remain_readable_with_legacy_protocol_classification(tmp_path):
    data, run = tmp_path / 'data', tmp_path / 'run'
    data.mkdir()
    run.mkdir()
    source = example()
    source.update(expected={'points': [{'point': 'Criterion.', 'met': True, 'why': 'Present.'}], 'feedback': 'Good.'})
    raw = json.dumps(source) + '\n'
    (data / 'test.jsonl').write_text(raw)
    (data / 'manifest.json').write_text(json.dumps({'files': {'test.jsonl': {'sha256': hashlib.sha256(raw.encode()).hexdigest()}}}))
    selection = tmp_path / 'selection.json'
    evaluation.freeze_selection(data, selection)
    # An actual v1 selection has no later evaluation_role field.
    original = json.loads(selection.read_text())
    original.pop('evaluation_role')
    selection.write_text(json.dumps(original))
    (run / 'run.json').write_text(json.dumps({'version': 1, 'config': {'identity': evaluation.IDENTITY},
        'selection_sha256': hashlib.sha256(selection.read_bytes()).hexdigest()}))
    evaluation.write_attempt(run, 'one', {'group': 'one', 'subject': 'chem', 'task': 'marking',
        'state': 'complete', 'text': json.dumps(source['expected']), 'finish_reason': 'stop'})
    before = {p.name: p.read_bytes() for p in run.iterdir()}
    report = evaluation.score_run(data, selection, run)
    assert report['protocol'] == 'legacy_system' and report['scores'][0]['marking_vector_correct'] is True
    assert {p.name: p.read_bytes() for p in run.iterdir()} == before


@pytest.mark.parametrize('penalty', [0.0, 1.5])
def test_fast_presence_contrast_changes_only_that_coefficient(penalty):
    config = evaluation.EvaluationConfig(presence_penalty=penalty)
    config.validate()
    assert config.sampling('fast') == {'temperature': .7, 'top_p': .8, 'top_k': 20,
        'presence_penalty': penalty, 'presence_context_size': 1024}


@pytest.mark.parametrize('penalty', [float('nan'), float('inf'), float('-inf'), -1.0, .5, 2.0, True, False, '0', None])
def test_presence_contrast_rejects_nonfinite_or_unplanned_values(penalty):
    with pytest.raises(ValueError):
        evaluation.EvaluationConfig(presence_penalty=penalty).validate()


def test_deep_presence_default_is_preserved_and_fast_alternative_cannot_change_it():
    assert evaluation.EvaluationConfig().sampling('deep') == {'temperature': 1.0, 'top_p': .95, 'top_k': 20,
        'presence_penalty': 1.5, 'presence_context_size': 1024}
    with pytest.raises(ValueError, match='Fast'):
        evaluation.EvaluationConfig(presence_penalty=0.0).sampling('deep')


def test_sampler_mismatch_cannot_be_presented_as_same_sampling_pair(tmp_path):
    from dataclasses import asdict
    base, adapter = tmp_path / 'base', tmp_path / 'adapter'
    common = {'mode': 'fast', 'protocol': 'training', 'selection_sha256': 'same',
              'harness_sha256': 'same', 'model_files': {}}
    for root, variant, penalty in ((base, 'base', 1.5), (adapter, 'adapter', 0.0)):
        root.mkdir()
        config = evaluation.EvaluationConfig(presence_penalty=penalty)
        (root / 'run.json').write_text(json.dumps(dict(common, variant=variant,
            config=asdict(config), sampling=config.sampling('fast'))))
        (root / 'load.001.json').write_text(json.dumps({'state': 'complete', 'resolved_protocol': {'stop_tokens': [102]}}))
    with pytest.raises(ValueError, match='Paired'):
        evaluation.validate_pair(base, adapter)
