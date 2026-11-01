"""Held-out evaluation must not reward formatting as scientific correctness."""
import importlib
import json
from pathlib import Path
import subprocess
import sys
from types import ModuleType

import pytest


@pytest.fixture
def evaluation():
    try:
        return importlib.import_module('tutor_app.stem_training_eval')
    except ModuleNotFoundError as exc:
        if exc.name != 'tutor_app.stem_training_eval':
            raise
        pytest.fail('The paired evaluation harness does not exist yet')


def row(identifier='a', subject='chem', task='direct_recall', group=None, expected=None, **checks):
    expected = expected or {'blocks': [{'kind': 'paragraph', 'text': 'A correct definition.'}]}
    return {'id': identifier, 'group': group or identifier, 'subject': subject, 'task': task,
            'messages': [{'role': 'user', 'content': 'A question.'},
                         {'role': 'assistant', 'content': json.dumps(expected)}],
            'expected': expected, 'checks': {'schema': 'document', **checks}, 'provenance': [{'kind': 'synthetic'}]}


def successful_load(path, stop=102):
    (path / 'load.001.json').write_text(json.dumps({'state': 'complete', 'resolved_protocol': {
        'open_think': 100, 'close_think': 101, 'stop_tokens': [stop]}}))


def test_selection_is_stable_and_never_depends_on_labels(evaluation):
    rows = [row(f'{subject}-{i}', subject, 'rare' if i < 2 else 'common', group=f'g-{subject}-{i//2}')
            for subject in ('chem', 'math', 'phys') for i in range(8)]
    selected = evaluation.select_rows(rows, per_subject=3, seed=42)
    changed = [dict(r, expected={'answer': 'DIFFERENT'}, messages=[]) for r in reversed(rows)]
    assert [r['id'] for r in selected] == [r['id'] for r in evaluation.select_rows(changed, per_subject=3, seed=42)]
    assert len(selected) == 9
    assert all(sum(r['subject'] == s for r in selected) == 3 for s in ('chem', 'math', 'phys'))
    assert all(any(r['subject'] == s and r['task'] == 'rare' for r in selected) for s in ('chem', 'math', 'phys'))


def test_selection_rejects_duplicate_ids_and_invalid_subjects(evaluation):
    with pytest.raises(ValueError, match='Duplicate'):
        evaluation.select_rows([row(), row()])
    with pytest.raises(ValueError, match='subject'):
        evaluation.select_rows([row(subject='history')])


def test_selection_receipt_freezes_hashes_and_group_counts(evaluation, tmp_path):
    data = tmp_path / 'data'
    data.mkdir()
    rows = [row('a', group='one'), row('b', group='one'), row('c', subject='math')]
    raw = ''.join(json.dumps(r) + '\n' for r in rows)
    (data / 'test.jsonl').write_text(raw)
    import hashlib
    (data / 'manifest.json').write_text(json.dumps({'files': {'test.jsonl': {'sha256': hashlib.sha256(raw.encode()).hexdigest()}}}))
    output = tmp_path / 'selection.json'
    receipt = evaluation.freeze_selection(data, output, per_subject=40)
    assert receipt['rows'] == 3 and receipt['groups'] == 2
    assert receipt['by_subject']['chem'] == {'rows': 2, 'groups': 1}
    assert evaluation.load_selection(data, output)[0] == sorted(rows, key=lambda r: receipt['ids'].index(r['id']))
    with pytest.raises(FileExistsError):
        evaluation.freeze_selection(data, output)
    (data / 'test.jsonl').write_text(raw + '\n')
    with pytest.raises(ValueError, match='hash'):
        evaluation.load_selection(data, output)


@pytest.mark.parametrize('text', ['```json\n{"blocks":[{"kind":"paragraph","text":"Good."}]}\n```',
    '{"blocks":[{"kind":"paragraph","text":"Good."}],"reply":"other"}',
    '{"blocks":[],"blocks":[{"kind":"paragraph","text":"Good."}]}'])
def test_raw_format_never_strips_fences_or_duplicate_keys(evaluation, text):
    score = evaluation.score_trial(row(), {'text': text, 'finish_reason': 'stop'})
    assert score['delivered'] and not score['raw_contract_valid']
    assert score['science_status'] == 'manual_review_required'


def test_correct_json_is_not_scientific_accuracy(evaluation):
    text = json.dumps({'blocks': [{'kind': 'paragraph', 'text': 'An ionic bond consists of shared electrons.'}]})
    score = evaluation.score_trial(row(), {'text': text, 'finish_reason': 'stop'})
    assert score['raw_contract_valid']
    assert score['science_status'] == 'manual_review_required'
    assert 'scientific_accuracy' not in score
    assert not score['exact_document_match']


def test_repairs_are_reported_separately_from_raw_format(evaluation):
    text = json.dumps({'blocks': [{'kind': 'step', 'text': '1. Substitute the values.'}]})
    score = evaluation.score_trial(row(), {'text': text, 'finish_reason': 'stop'})
    assert score['host_contract_valid'] and score['repaired']
    assert not score['raw_contract_valid']


def test_literal_code_is_compared_exactly_without_execution(evaluation, tmp_path):
    code = f'from pathlib import Path\nPath({str(tmp_path / "bad")!r}).write_text("bad")'
    gold = {'blocks': [{'kind': 'code', 'text': code}]}
    source = row(expected=gold, source_fidelity=True)
    good = evaluation.score_trial(source, {'text': json.dumps(gold), 'finish_reason': 'stop'})
    assert good['literal_code_equal'] is True and good['source_copy_exact'] is True
    damaged = {'blocks': [{'kind': 'code', 'text': code.replace('\n', '\\n')}]}
    bad = evaluation.score_trial(source, {'text': json.dumps(damaged), 'finish_reason': 'stop'})
    assert bad['literal_code_equal'] is False and not (tmp_path / 'bad').exists()


def test_source_copy_is_not_source_free_knowledge(evaluation):
    source = row(source_fidelity=True, scientific_truth='published_source_not_independently_rederived')
    score = evaluation.score_trial(source, {'text': json.dumps(source['expected']), 'finish_reason': 'stop'})
    assert score['source_copy_exact'] is True
    assert score['science_status'] == 'manual_review_required'
    assert score['evidence_category'] == 'source_copy'


def test_marking_scores_only_strict_ordered_boolean_labels(evaluation):
    expected = {'points': [{'point': 'criterion1', 'met': True, 'why': 'Present.'},
                           {'point': 'criterion2', 'met': False, 'why': 'Absent.'}], 'feedback': 'Feedback.'}
    source = row(task='marking', expected=expected, schema='marking', labels=[True, False])
    score = evaluation.score_trial(source, {'text': json.dumps(expected), 'finish_reason': 'stop'})
    assert score['marking_labels_equal'] is True and score['raw_contract_valid']
    wrong = dict(expected, points=[dict(expected['points'][0], met=1), expected['points'][1]])
    assert not evaluation.score_trial(source, {'text': json.dumps(wrong), 'finish_reason': 'stop'})['raw_contract_valid']
    swapped = dict(expected, points=list(reversed(expected['points'])))
    assert not evaluation.score_trial(source, {'text': json.dumps(swapped), 'finish_reason': 'stop'})['marking_labels_equal']


def test_truncated_json_never_counts_as_delivered_or_valid(evaluation):
    score = evaluation.score_trial(row(), {'text': json.dumps(row()['expected']), 'finish_reason': 'length'})
    assert not score['delivered'] and not score['raw_contract_valid']


def test_thought_tokens_are_counted_without_keeping_or_decoding_them(evaluation):
    final = evaluation.VisibleTokens(thinking=True, open_token=100, close_token=101, stop_tokens={102})
    for token in (100, 999, 998, 101, 7, 8, 102):
        final.feed(token)
    assert final.reasoning_tokens == 2 and final.tokens == [7, 8]
    assert '999' not in repr(vars(final)) and '998' not in repr(vars(final))


def test_fast_mode_can_still_hide_unexpected_reasoning(evaluation):
    final = evaluation.VisibleTokens(thinking=False, open_token=100, close_token=101, stop_tokens={102})
    for token in (100, 999, 101, 7):
        final.feed(token)
    assert final.reasoning_tokens == 1 and final.tokens == [7]


def test_pair_contract_and_retry_files_preserve_failed_attempts(evaluation, tmp_path):
    config = evaluation.EvaluationConfig()
    assert config.sampling('fast') == {'temperature': .7, 'top_p': .8, 'top_k': 20, 'presence_penalty': 1.5, 'presence_context_size': 1024}
    assert config.sampling('deep')['temperature'] == 1.0
    assert config.sampling('deep')['top_p'] == .95
    path = evaluation.write_attempt(tmp_path, 'abc', {'state': 'error', 'text': '', 'error': 'TimeoutError'})
    later = evaluation.write_attempt(tmp_path, 'abc', {'state': 'complete', 'text': '{}'})
    assert path != later and json.loads(path.read_text())['error'] == 'TimeoutError'


@pytest.mark.parametrize('preloaded_mlx', [False, True])
def test_generation_import_is_cpu_safe(monkeypatch, preloaded_mlx):
    proof = """
import importlib
import importlib.abc
import sys

attempts = []
class BlockMLX(importlib.abc.MetaPathFinder):
    def find_spec(self, fullname, path=None, target=None):
        if fullname.split('.')[0] in {'mlx', 'mlx_lm'}:
            attempts.append(fullname)
            raise AssertionError(f'Evaluator import attempted {fullname}')

sys.meta_path.insert(0, BlockMLX())
sys.path.insert(0, sys.argv[1])
before = set(sys.modules)
module = importlib.import_module('tutor_app.stem_training_eval')
importlib.reload(module)
assert not attempts, attempts
assert not {name for name in set(sys.modules) - before
            if name.split('.')[0] in {'mlx', 'mlx_lm'}}
"""
    previous_core = sys.modules.get('mlx.core')
    with monkeypatch.context() as isolated:
        if preloaded_mlx:
            isolated.setitem(sys.modules, 'mlx.core', ModuleType('mlx.core'))
        parent_core = sys.modules.get('mlx.core')
        result = subprocess.run(
            [sys.executable, '-I', '-S', '-c', proof, str(Path(__file__).resolve().parents[2] / 'app')],
            capture_output=True, text=True, timeout=30)
        assert result.returncode == 0, result.stdout + result.stderr
        assert sys.modules.get('mlx.core') is parent_core
    assert sys.modules.get('mlx.core') is previous_core


def test_retry_uses_latest_outcome_and_includes_length_failures(evaluation):
    failures = [{'id': 'a', 'attempt': 1, 'state': 'error'},
                {'id': 'b', 'attempt': 1, 'state': 'complete', 'finish_reason': 'length', 'text': '{}'},
                {'id': 'c', 'attempt': 1, 'state': 'complete', 'finish_reason': 'stop', 'text': '{}'},
                {'id': 'a', 'attempt': 2, 'state': 'complete', 'finish_reason': 'stop', 'text': '{}'}]
    assert not evaluation.needs_trial('a', failures, retry_failed=True)
    assert evaluation.needs_trial('b', failures, retry_failed=True)
    assert not evaluation.needs_trial('b', failures, retry_failed=False)
    assert not evaluation.needs_trial('c', failures, retry_failed=True)
    assert evaluation.needs_trial('d', failures)


def test_comparison_refuses_mismatched_modes_sampling_and_inputs(evaluation, tmp_path):
    base, candidate = tmp_path / 'base', tmp_path / 'candidate'
    base.mkdir()
    candidate.mkdir()
    common = {'mode': 'fast', 'config': {'seed': 42}, 'sampling': {'temperature': .7},
              'selection_sha256': 'selection', 'model_files': {'weights': 'sha'}, 'harness_sha256': 'code'}
    (base / 'run.json').write_text(json.dumps(dict(common, variant='base')))
    (candidate / 'run.json').write_text(json.dumps(dict(common, variant='adapter')))
    successful_load(base)
    successful_load(candidate)
    evaluation.validate_pair(base, candidate)
    for key, value in [('mode', 'deep'), ('sampling', {}), ('model_files', {}), ('harness_sha256', 'other')]:
        (candidate / 'run.json').write_text(json.dumps(dict(common, variant='adapter', **{key: value})))
        with pytest.raises(ValueError, match='Paired'):
            evaluation.validate_pair(base, candidate)


def test_generation_configuration_rejects_unbounded_or_renamed_policy(evaluation):
    for changes in ({'max_tokens': 99999}, {'deadline_seconds': 9999}, {'memory_limit_gib': 16},
                    {'memory_limit_gib': .5}, {'identity': 'different'}):
        with pytest.raises(ValueError):
            evaluation.EvaluationConfig(**changes).validate()


def test_selection_cannot_be_tampered_to_choose_different_questions(evaluation, tmp_path):
    import hashlib
    data = tmp_path / 'data'
    data.mkdir()
    raw = ''.join(json.dumps(row(str(i))) + '\n' for i in range(5))
    (data / 'test.jsonl').write_text(raw)
    (data / 'manifest.json').write_text(json.dumps({'files': {'test.jsonl': {'sha256': hashlib.sha256(raw.encode()).hexdigest()}}}))
    selection = tmp_path / 'selection.json'
    receipt = evaluation.freeze_selection(data, selection, per_subject=2)
    receipt['ids'].reverse()
    selection.write_text(json.dumps(receipt))
    with pytest.raises(ValueError, match='policy|ids'):
        evaluation.load_selection(data, selection)


def test_paired_scores_keep_failures_and_do_not_choose_best_retry(evaluation, tmp_path):
    import hashlib
    data = tmp_path / 'data'
    data.mkdir()
    source = row()
    raw = json.dumps(source) + '\n'
    (data / 'test.jsonl').write_text(raw)
    (data / 'manifest.json').write_text(json.dumps({'files': {'test.jsonl': {'sha256': hashlib.sha256(raw.encode()).hexdigest()}}}))
    selection = tmp_path / 'selection.json'
    evaluation.freeze_selection(data, selection)
    base, adapter = tmp_path / 'base', tmp_path / 'adapter'
    common = {'mode': 'fast', 'config': {'seed': 42}, 'sampling': {},
              'selection_sha256': hashlib.sha256(selection.read_bytes()).hexdigest(),
              'model_files': {'weights': 'sha'}, 'harness_sha256': 'code'}
    trial = {'state': 'complete', 'variant': 'base', 'mode': 'fast', 'subject': 'chem', 'task': 'direct_recall',
             'group': 'a', 'text': json.dumps(source['expected']), 'finish_reason': 'stop', 'prompt_sha256': 'same', 'seconds': 4}
    for path, variant in ((base, 'base'), (adapter, 'adapter')):
        path.mkdir()
        (path / 'run.json').write_text(json.dumps(dict(common, variant=variant)))
        successful_load(path)
        evaluation.write_attempt(path, 'a', dict(trial, variant=variant))
    evaluation.write_attempt(adapter, 'a', dict(trial, variant='adapter', state='error', error='TimeoutError', text=''))
    report = evaluation.compare_runs(data, selection, base, adapter)
    assert len(report['candidate']['scores']) == 2
    assert report['pairs'][0]['baseline']['delivered']
    assert not report['pairs'][0]['candidate']['delivered']
    assert report['pairs'][0]['candidate']['attempt'] == 2


def test_visible_tokens_never_retain_unfinished_thoughts(evaluation):
    final = evaluation.VisibleTokens(thinking=True, open_token=100, close_token=101, stop_tokens={102})
    for token in (991, 992, 102):
        final.feed(token)
    assert final.reasoning_tokens == 2 and final.tokens == []


def test_model_identity_tracks_generation_config_and_auxiliary_tokenizer_files(evaluation, tmp_path):
    model = tmp_path / 'model'
    model.mkdir()
    for name in ('model.safetensors', 'config.json', 'tokenizer.json', 'vocab.json', 'merges.txt',
                 'special_tokens_map.json', 'added_tokens.json', 'generation_config.json'):
        (model / name).write_text('{}')
    first = evaluation._model_hashes(model)
    (model / 'generation_config.json').write_text('{"eos_token_id":2}')
    assert first != evaluation._model_hashes(model)
    assert {'vocab.json', 'merges.txt', 'special_tokens_map.json', 'added_tokens.json'} <= first.keys()


def test_fused_pair_rejects_tokenizer_template_and_stop_changes(evaluation, tmp_path):
    base, fused = tmp_path / 'base', tmp_path / 'fused'
    base.mkdir()
    fused.mkdir()
    assets = {'tokenizer.json': {'sha256': 'A'}, 'chat_template.jinja': {'sha256': 'B'},
              'generation_config.json': {'sha256': 'C'}, 'model.safetensors': {'sha256': 'WEIGHTS'}}
    common = {'mode': 'fast', 'config': {}, 'sampling': {}, 'selection_sha256': 'same',
              'harness_sha256': 'same', 'model_files': assets}
    (base / 'run.json').write_text(json.dumps(dict(common, variant='base')))
    fused_assets = dict(assets, **{'model.safetensors': {'sha256': 'FUSED'}})
    (fused / 'run.json').write_text(json.dumps(dict(common, variant='fused', model_files=fused_assets)))
    successful_load(base)
    successful_load(fused)
    evaluation.validate_pair(base, fused)
    for name in ('tokenizer.json', 'chat_template.jinja', 'generation_config.json'):
        damaged = dict(fused_assets, **{name: {'sha256': 'OTHER'}})
        (fused / 'run.json').write_text(json.dumps(dict(common, variant='fused', model_files=damaged)))
        with pytest.raises(ValueError, match='Paired'):
            evaluation.validate_pair(base, fused)
    (fused / 'run.json').write_text(json.dumps(dict(common, variant='fused', model_files=fused_assets)))
    successful_load(fused, stop=103)
    with pytest.raises(ValueError, match='Paired resolved'):
        evaluation.validate_pair(base, fused)


def test_interrupted_starts_are_scored_and_retry_number_is_preserved(evaluation, tmp_path):
    import hashlib
    data = tmp_path / 'data'
    data.mkdir()
    source = row()
    raw = json.dumps(source) + '\n'
    (data / 'test.jsonl').write_text(raw)
    (data / 'manifest.json').write_text(json.dumps({'files': {'test.jsonl': {'sha256': hashlib.sha256(raw.encode()).hexdigest()}}}))
    selection = tmp_path / 'selection.json'
    evaluation.freeze_selection(data, selection)
    output = tmp_path / 'output'
    output.mkdir()
    (output / 'run.json').write_text(json.dumps({'selection_sha256': hashlib.sha256(selection.read_bytes()).hexdigest()}))
    metadata = {'group': 'a', 'subject': 'chem', 'task': 'direct_recall', 'prompt_sha256': 'same'}
    start = evaluation.start_attempt(output, 'a', metadata)
    assert json.loads(start.read_text())['attempt'] == 1
    scores = evaluation.score_run(data, selection, output)['scores']
    assert len(scores) == 1 and scores[0]['state'] == 'interrupted'
    assert scores[0]['attempt'] == 1 and not scores[0]['delivered']
    assert evaluation.needs_trial('a', evaluation.read_attempts(output))
    second = evaluation.start_attempt(output, 'a', metadata)
    assert json.loads(second.read_text())['attempt'] == 2
    evaluation.write_attempt(output, 'a', dict(metadata, state='complete', finish_reason='stop',
                              text=json.dumps(source['expected'])), attempt=2)
    scores = evaluation.score_run(data, selection, output)['scores']
    assert [(s['attempt'], s['state']) for s in scores] == [(1, 'interrupted'), (2, 'complete')]
    assert not evaluation.needs_trial('a', evaluation.read_attempts(output))


@pytest.mark.parametrize('peak_gib,invalid_boundary,error_type,penalty', [
    (17, False, MemoryError, 1.5), (1, True, ValueError, 1.5), (1, False, None, 0.0)])
def test_generation_load_guards_cleanup_and_resolved_sampling(evaluation, tmp_path, monkeypatch,
                                                             peak_gib, invalid_boundary, error_type, penalty):
    """Stub only the external GPU boundary; run real receipt/guard/cleanup code."""
    import hashlib
    import types
    from tutor_app import stem_training
    data, model, output = [tmp_path / name for name in ('data', 'model', 'output')]
    data.mkdir()
    model.mkdir()
    (model / 'model.safetensors').write_bytes(b'weights')
    (model / 'tokenizer.json').write_text('{}')
    raw = json.dumps(row()) + '\n'
    (data / 'test.jsonl').write_text(raw)
    (data / 'manifest.json').write_text(json.dumps({'files': {'test.jsonl': {'sha256': hashlib.sha256(raw.encode()).hexdigest()}}}))
    selection = tmp_path / 'selection.json'
    evaluation.freeze_selection(data, selection)
    monkeypatch.setattr(stem_training, 'SSD_ROOT', tmp_path)
    monkeypatch.setattr(stem_training, 'configure_ssd_caches', lambda: None)
    class Resources:
        latest = {'pressure': 1}
        def check(self):
            pass
    monkeypatch.setattr(stem_training, 'ResourceMonitor', Resources)
    events, state = [], {'peak': 0}
    mlx, core, lm, sampling = [types.ModuleType(name) for name in ('mlx', 'mlx.core', 'mlx_lm', 'mlx_lm.sample_utils')]
    mlx.core = core
    core.set_memory_limit = lambda value: None
    core.eval = lambda value: None
    core.get_active_memory = lambda: 1024**3
    core.get_peak_memory = lambda: state['peak']
    core.random = types.SimpleNamespace(seed=lambda value: None)
    def reset():
        events.append('reset')
        state['peak'] = 0
    core.reset_peak_memory = reset
    core.clear_cache = lambda: events.append('cleanup')
    class Model:
        def eval(self):
            pass
        def parameters(self):
            return []
    class Tokenizer:
        eos_token_ids, eos_token_id = {102}, 102
        def convert_tokens_to_ids(self, value):
            return 100 if invalid_boundary or value == '<think>' else 101
        def apply_chat_template(self, *args, **kwargs):
            return 'prompt'
        def decode(self, *args, **kwargs):
            return '{}'
    def load(*args, **kwargs):
        events.append('load')
        state['peak'] = peak_gib * 1024**3
        return Model(), Tokenizer()
    lm.load = load
    def stream(*args, **kwargs):
        events.append('generate')
        yield types.SimpleNamespace(token=7, finish_reason='stop')
    lm.stream_generate = stream
    processor_calls = []
    sampling.make_sampler = lambda **kwargs: None
    def processors(**kwargs):
        processor_calls.append(kwargs)
        return None
    sampling.make_logits_processors = processors
    for module in (mlx, core, lm, sampling):
        monkeypatch.setitem(sys.modules, module.__name__, module)
    config = evaluation.EvaluationConfig(presence_penalty=penalty)
    if error_type:
        with pytest.raises(error_type):
            evaluation.run_generation(data, selection, model, None, output, 'base', 'fast', config)
        assert events == ['reset', 'load', 'cleanup']
        assert not processor_calls
    else:
        evaluation.run_generation(data, selection, model, None, output, 'base', 'fast', config)
        assert events == ['reset', 'load', 'cleanup', 'reset', 'generate', 'cleanup']
        assert processor_calls == [{'presence_penalty': 0.0, 'presence_context_size': 1024}]
        run = json.loads((output / 'run.json').read_text())
        assert run['config']['presence_penalty'] == run['sampling']['presence_penalty'] == 0.0
        assert evaluation.read_attempts(output)[0]['state'] == 'complete'
    receipts = list(output.glob('load.*.json'))
    assert len(receipts) == 1
    receipt = json.loads(receipts[0].read_text())
    assert receipt['peak_bytes'] == peak_gib * 1024**3
    if error_type:
        assert receipt['state'] == 'error' and receipt['error'].startswith(error_type.__name__)
    else:
        assert receipt['state'] == 'complete'

