"""CPU-only proofs for the bounded, final-answer-only MLX pilot wrapper."""
from __future__ import annotations

import json
from dataclasses import replace
from pathlib import Path

import pytest

from tutor_app import stem_training as training


class CharacterTokenizer:
    """Transparent offsets make the labelled tokens independently inspectable."""
    def apply_chat_template(self, messages, *, tokenize=False, **kwargs):
        text = '<user>' + messages[0]['content'] + '</user><assistant><think>\n\n</think>\n\n' + messages[1]['content'] + '<eos>'
        return [ord(c) for c in text] if tokenize else text

    def __call__(self, text, *, add_special_tokens=False, return_offsets_mapping=False):
        return {'input_ids': [ord(c) for c in text], 'offset_mapping': [(n, n+1) for n in range(len(text))]}


def example(identifier='a', group='one'):
    return {'id': identifier, 'group': group, 'subject': 'maths', 'task': 'explain',
            'messages': [{'role': 'user', 'content': 'Calculate 1+1.'},
                         {'role': 'assistant', 'content': '{"answer":2}'}],
            'expected': {'answer': 2}, 'provenance': ['authored'], 'checks': {'verified': True}}


def test_final_mask_excludes_prompt_and_empty_reasoning_boundary():
    encoded = training.encode_final_example(example(), CharacterTokenizer())
    assert ''.join(map(chr, encoded.tokens[encoded.offset:])) == '{"answer":2}<eos>'
    assert ''.join(map(chr, encoded.tokens[:encoded.offset])).endswith('</think>\n\n')
    # MLX targets have indices 1..N-1, so the offset is the first labelled target.
    assert encoded.labelled_target_indices[0] == encoded.offset
    assert len(encoded.labelled_target_indices) == len('{"answer":2}<eos>')


def test_mask_uses_assistant_boundary_even_if_question_quotes_think():
    item = example()
    item['messages'][0]['content'] = 'Explain the literal token </think>.'
    encoded = training.encode_final_example(item, CharacterTokenizer())
    assert chr(encoded.tokens[encoded.offset]) == '{'


def test_missing_template_reasoning_boundary_is_rejected():
    class MissingBoundary(CharacterTokenizer):
        def apply_chat_template(self, messages, **kwargs):
            return 'user assistant ' + messages[-1]['content']
    with pytest.raises(ValueError, match='boundary'):
        training.encode_final_example(example(), MissingBoundary())


def test_token_straddling_final_answer_boundary_is_rejected():
    class Straddle(CharacterTokenizer):
        def __call__(self, text, **kwargs):
            result = super().__call__(text, **kwargs)
            start = text.index('{')
            result['offset_mapping'][start] = (start-1, start+1)
            return result
    with pytest.raises(ValueError, match='straddles'):
        training.encode_final_example(example(), Straddle())


@pytest.mark.parametrize('change', [
    lambda x: x['messages'][1].update(content='<think>secret</think>{"answer":2}'),
    lambda x: x['messages'][1].update(reasoning_content='secret'),
    lambda x: x['messages'][1].update(content='{"analysis":"secret","answer":2}'),
    lambda x: x['messages'][1].update(content='not JSON'),
    lambda x: x.update(provenance=[]),
    lambda x: x['messages'][0].update(role='system'),
])
def test_invalid_or_hidden_reasoning_gold_is_rejected(change):
    item = example()
    change(item)
    with pytest.raises(ValueError):
        training.encode_final_example(item, CharacterTokenizer())


def test_preparation_drops_whole_overlength_example_without_truncation():
    short, long = example(), example('b', 'two')
    long['messages'][0]['content'] = 'q' * 600
    result = training.prepare_examples([short, long], CharacterTokenizer(), 512)
    assert len(result.examples) == 1
    assert result.dropped_ids == ['b']
    assert result.original_count == 2
    assert ''.join(map(chr, result.examples[0].tokens)).endswith('{"answer":2}<eos>')


def test_no_remaining_examples_fails_instead_of_empty_training():
    with pytest.raises(ValueError, match='No examples'):
        training.prepare_examples([example()], CharacterTokenizer(), 5)


@pytest.mark.parametrize('kwargs', [
    {'iterations': 101, 'mode': 'pilot'}, {'max_seq_length': 2048, 'mode': 'pilot'},
    {'grad_accumulation': 5, 'mode': 'pilot'}, {'batch_size': 2},
    {'memory_limit_gib': 17}, {'wall_time_seconds': 3601}, {'learning_rate': 0.001},
    {'iterations': 6}, {'max_seq_length': 1024}, {'grad_accumulation': 2},
    {'wall_time_seconds': 0}, {'memory_limit_gib': 0},
])
def test_unsafe_or_out_of_scope_training_settings_fail_before_gpu(kwargs):
    with pytest.raises(ValueError):
        replace(training.TrainingConfig(), **kwargs).validate()


def test_pilot_bounds_and_smoke_defaults_are_accepted():
    training.TrainingConfig().validate()
    training.TrainingConfig(mode='pilot', iterations=100, max_seq_length=1024, grad_accumulation=4).validate()


def test_adapter_parameter_guard_rejects_any_base_or_wrong_layer_tensor():
    allowed = ['model.layers.24.mlp.gate_proj.lora_a', 'model.layers.31.mlp.down_proj.lora_b']
    training.validate_adapter_names(allowed, 32)
    for bad in ['model.layers.24.mlp.gate_proj.linear.weight', 'model.layers.23.mlp.gate_proj.lora_a',
                'model.layers.24.self_attn.q_proj.lora_a']:
        with pytest.raises(ValueError, match='adapter'):
            training.validate_adapter_names(allowed + [bad], 32)


def test_paths_cannot_overwrite_model_data_or_existing_run(tmp_path, monkeypatch):
    monkeypatch.setattr(training, 'SSD_ROOT', tmp_path)
    base, data = tmp_path/'base', tmp_path/'data'
    base.mkdir(); data.mkdir()
    training.validate_paths(base, data, tmp_path/'new-run')
    for adapter in [base, data, base/'adapter', data/'adapter', tmp_path.parent/'escape']:
        with pytest.raises(ValueError):
            training.validate_paths(base, data, adapter)
    run = tmp_path/'existing'; run.mkdir()
    with pytest.raises(ValueError):
        training.validate_paths(base, data, run)


def test_split_leakage_is_rejected_without_reading_sealed_test_content(tmp_path):
    # The manifest is authoritative for test groups; training never opens test.jsonl.
    for name, row in [('train', example()), ('valid', example('v', 'valid'))]:
        (tmp_path/f'{name}.jsonl').write_text(json.dumps(row)+'\n')
    (tmp_path/'manifest.json').write_text(json.dumps({'splits': {'test': {'groups': ['one']}},
        'files': {f'{split}.jsonl': {'sha256': training.sha256_file(tmp_path/f'{split}.jsonl')} for split in ('train', 'valid')}}))
    with pytest.raises(ValueError, match='group'):
        training.load_training_data(tmp_path)


def test_deadline_and_cancel_are_checked_between_safe_steps():
    guard = training.RunGuard(10, clock=lambda: 20.0)
    guard.started = 0.0
    with pytest.raises(training.TrainingStopped, match='wall'):
        guard.check()
    guard = training.RunGuard(10, clock=lambda: 0.0)
    guard.cancelled = 'SIGTERM'
    with pytest.raises(training.TrainingStopped, match='SIGTERM'):
        guard.check()


def test_atomic_receipt_write_replaces_file_with_valid_json(tmp_path):
    path = tmp_path/'receipt.json'
    training.write_json_atomic(path, {'state': 'stopped', 'updates': 3})
    assert json.loads(path.read_text()) == {'state': 'stopped', 'updates': 3}
    assert list(tmp_path.iterdir()) == [path]


class ScalarBackend:
    """CPU implementation of the loop boundary; no MLX/model is instantiated."""
    def __init__(self, losses=None):
        self.losses = iter(losses or [1.0] * 500)
        self.microsteps = 0
        self.updates = 0
        self.saved = []

    def micro_step(self):
        self.microsteps += 1
        return next(self.losses), 3

    def update(self):
        self.updates += 1

    def evaluate(self):
        return 1.0

    def checkpoint(self, update, *, accepted=True, rejected=False):
        self.saved.append(update)

    def accept_checkpoint(self, update):
        pass


def test_iteration_count_means_optimizer_updates_with_accumulation():
    backend = ScalarBackend()
    config = training.TrainingConfig(mode='pilot', iterations=30, grad_accumulation=4)
    receipt = {}
    training.run_updates(config, backend, training.RunGuard(3600), receipt)
    assert backend.microsteps == 120
    assert backend.updates == 30
    assert backend.saved == [0, 25, 30]
    assert receipt['updates_completed'] == 30
    assert receipt['state'] == 'completed'


def test_nonfinite_loss_stops_before_optimizer_mutation_and_saves_finite_state():
    backend = ScalarBackend([1.0, float('nan')])
    receipt = {}
    with pytest.raises(ValueError, match='finite'):
        training.run_updates(training.TrainingConfig(), backend, training.RunGuard(3600), receipt)
    assert backend.updates == 1
    assert backend.saved == [0, 1]
    assert receipt['state'] == 'failed'


def test_cancellation_preserves_initial_checkpoint_and_performs_no_updates():
    guard = training.RunGuard(3600)
    guard.cancelled = 'SIGINT'
    backend = ScalarBackend()
    receipt = {}
    with pytest.raises(training.TrainingStopped):
        training.run_updates(training.TrainingConfig(), backend, guard, receipt)
    assert backend.updates == 0
    assert backend.saved == [0]
    assert receipt['state'] == 'stopped'


def test_cli_defaults_to_preparation_and_rejects_conflicting_actions():
    args = training.build_parser().parse_args(['--base-model', '/base', '--data-dir', '/data', '--adapter-dir', '/new'])
    assert args.execute is False
    with pytest.raises(SystemExit):
        training.build_parser().parse_args(['--base-model', '/base', '--data-dir', '/data', '--adapter-dir', '/new', '--execute', '--prepare-only'])


def test_template_tokenization_requests_plain_ids_on_transformers5():
    class Transformers5Tokenizer(CharacterTokenizer):
        def apply_chat_template(self, messages, *, tokenize=False, return_dict=True, **kwargs):
            value = super().apply_chat_template(messages, tokenize=tokenize, **kwargs)
            return {'input_ids': value} if tokenize and return_dict else value
    result = training.encode_final_example(example(), Transformers5Tokenizer())
    assert chr(result.tokens[result.offset]) == '{'


def test_resource_monitor_stops_on_swap_growth_critical_pressure_or_low_disk():
    normal = {'pressure': 1, 'swap_used_bytes': 100, 'disk_free_bytes': 30*1024**3}
    for changed in ({'pressure': 4}, {'swap_used_bytes': 600*1024**2}, {'disk_free_bytes': 19*1024**3}):
        snapshots = iter([normal, dict(normal, **changed)])
        monitor = training.ResourceMonitor(probe=lambda: next(snapshots), clock=lambda: 0)
        with pytest.raises(training.TrainingStopped):
            monitor.check()


def test_resource_monitor_rejects_warning_pressure_before_model_load():
    with pytest.raises(training.TrainingStopped, match='pressure'):
        training.ResourceMonitor(probe=lambda: {'pressure': 2, 'swap_used_bytes': 0, 'disk_free_bytes': 30*1024**3})


def test_resource_monitor_tolerates_brief_warning_but_stops_sustained_pressure():
    normal = {'pressure': 1, 'swap_used_bytes': 0, 'disk_free_bytes': 30*1024**3}
    snapshots = iter([normal, dict(normal, pressure=2), dict(normal, pressure=2)])
    clock = iter([0, 11])
    monitor = training.ResourceMonitor(probe=lambda: next(snapshots), clock=lambda: next(clock))
    monitor.check()
    with pytest.raises(training.TrainingStopped, match='sustained'):
        monitor.check()


def test_runtime_version_gate_rejects_inference_environment_versions():
    versions = {'mlx': '0.32.3', 'mlx-lm': '0.32.2', 'transformers': '5.20.2'}
    training.validate_runtime_versions(versions)
    with pytest.raises(ValueError, match='version'):
        training.validate_runtime_versions(dict(versions, mlx='0.32.1'))


def test_smoke_uses_at_most_16_training_and_8_development_examples():
    dataset = training.PreparedExamples([training.FinalExample(str(i), [1, 2, 3], 1) for i in range(40)], [], 40)
    selected = training.select_for_run({'train': dataset, 'valid': dataset}, training.TrainingConfig())
    assert len(selected['train'].examples) == 16
    assert len(selected['valid'].examples) == 8
    assert len({e.id for e in selected['train'].examples}) == 16
    repeated = training.select_for_run({'train': dataset, 'valid': dataset}, training.TrainingConfig())
    assert [e.id for e in selected['train'].examples] == [e.id for e in repeated['train'].examples]
    pilot = training.select_for_run({'train': dataset, 'valid': dataset}, training.TrainingConfig(mode='pilot'))
    assert len(pilot['train'].examples) == 40


def pinned_base(tmp_path):
    base = tmp_path/'base'; base.mkdir()
    files = {}
    for name in ['model.safetensors', 'config.json', 'tokenizer.json', 'tokenizer_config.json', 'chat_template.jinja']:
        path = base/name
        path.write_text('fixture '+name)
        files[name] = {'size': path.stat().st_size, 'sha256': training.sha256_file(path)}
    receipt = {'repository': 'mlx-community/Qwen3.5-4B-4bit', 'revision': training.BASE_REVISION,
               'upstream_repository': 'Qwen/Qwen3.5-4B', 'upstream_revision': '851bf6e806efd8d0a36b00ddf55e13ccb7b8cd0a',
               'verified': True, 'files': files}
    path = tmp_path/'base-receipt.json'; path.write_text(json.dumps(receipt))
    return base, path, receipt


def test_execution_requires_verified_pinned_identity_and_file_hashes(tmp_path):
    base, path, receipt = pinned_base(tmp_path)
    assert training.verify_base_receipt(base, path)['revision'] == training.BASE_REVISION
    (base/'config.json').write_text('changed weights configuration')
    with pytest.raises(ValueError, match='hash|size'):
        training.verify_base_receipt(base, path)


def test_base_receipt_rejects_wrong_identity_or_unsafe_file_path(tmp_path):
    base, path, receipt = pinned_base(tmp_path)
    receipt['revision'] = 'other'
    path.write_text(json.dumps(receipt))
    with pytest.raises(ValueError, match='identity'):
        training.verify_base_receipt(base, path)
    receipt['revision'] = training.BASE_REVISION
    receipt['files']['../escape'] = {'size': 0, 'sha256': 'bad'}
    path.write_text(json.dumps(receipt))
    with pytest.raises(ValueError, match='path'):
        training.verify_base_receipt(base, path)


def test_execute_cli_requires_base_receipt_before_optional_dependencies(tmp_path):
    # Missing receipt is rejected before loading tokenizer/model dependencies.
    with pytest.raises(ValueError, match='receipt'):
        training.main(['--base-model', str(tmp_path/'base'), '--data-dir', str(tmp_path/'data'),
                       '--adapter-dir', str(tmp_path/'new'), '--execute'])


def test_training_data_requires_manifest_checksums(tmp_path):
    for name, row in [('train', example()), ('valid', example('v', 'valid'))]:
        (tmp_path/f'{name}.jsonl').write_text(json.dumps(row)+'\n')
    (tmp_path/'manifest.json').write_text(json.dumps({'splits': {'test': {'groups': ['sealed']}}}))
    with pytest.raises(ValueError, match='hash'):
        training.load_training_data(tmp_path)


@pytest.mark.parametrize('active,peak', [(17*1024**3, 17*1024**3), (2*1024**3, 17*1024**3)])
def test_observed_mlx_memory_over_budget_stops_even_when_allocator_hint_did_not(active, peak):
    receipt = {}
    monitor = training.MlxMemoryMonitor(lambda: {'active_bytes': active, 'peak_bytes': peak}, 16*1024**3, receipt)
    with pytest.raises(training.TrainingStopped, match='observed MLX memory'):
        monitor.check('after_forward_backward')
    assert receipt['observed_memory'][-1] == {'phase': 'after_forward_backward', 'active_bytes': active, 'peak_bytes': peak}
    assert receipt['memory_budget_exceeded'] is True


def test_observed_memory_guard_prevents_next_step_and_preserves_pending_checkpoint():
    observations = iter([{'active_bytes': 1, 'peak_bytes': 1}, {'active_bytes': 1, 'peak_bytes': 17*1024**3}])
    receipt = {}
    monitor = training.MlxMemoryMonitor(lambda: next(observations), 16*1024**3, receipt)
    guard = training.RunGuard(3600, resource_check=lambda: monitor.check('before_next_step'))
    backend = ScalarBackend()
    with pytest.raises(training.TrainingStopped, match='observed MLX memory'):
        training.run_updates(training.TrainingConfig(), backend, guard, receipt)
    assert backend.microsteps == 0
    assert backend.updates == 0
    assert receipt['state'] == 'stopped'


def test_final_development_deterioration_is_rejected_and_never_published_successful():
    class DeterioratingBackend(ScalarBackend):
        def __init__(self):
            super().__init__()
            self.validation = iter([1.0, 2.0])
            self.published = []
            self.rejected = []

        def evaluate(self):
            return next(self.validation)

        def checkpoint(self, update, *, accepted=True, rejected=False):
            self.saved.append(update)
            if accepted:
                self.published.append(update)
            if rejected:
                self.rejected.append(update)

    receipt = {}
    backend = DeterioratingBackend()
    with pytest.raises(training.TrainingStopped, match='development loss deteriorated'):
        training.run_updates(training.TrainingConfig(), backend, training.RunGuard(3600), receipt)
    assert backend.updates == 5
    assert backend.published == [0]
    assert backend.rejected == [5]
    assert receipt['state'] == 'stopped'
    assert receipt['checkpoint_eligibility'] == 'rejected'


def test_gradient_checkpointing_covers_every_decoder_class_once():
    class LinearDecoder:
        pass
    class AttentionDecoder:
        pass
    layers = [LinearDecoder(), LinearDecoder(), AttentionDecoder(), AttentionDecoder()]
    calls = []
    receipt = {}
    training.enable_gradient_checkpointing(layers, lambda layer: calls.append(type(layer)), receipt)
    assert calls == [LinearDecoder, AttentionDecoder]
    assert receipt['gradient_checkpointing'] == {'enabled': True, 'decoder_layers': 4,
                                                  'decoder_classes': ['LinearDecoder', 'AttentionDecoder'],
                                                  'implementation': 'mlx_lm.tuner.trainer.grad_checkpoint'}


def test_materialized_accumulation_preserves_sum_and_clears_every_microbatch():
    class DeferredSum:
        def __init__(self, value=None, left=None, right=None):
            self.value, self.left, self.right = value, left, right
            self.materialized = value is not None

        def evaluate(self):
            if not self.materialized:
                self.left.evaluate(); self.right.evaluate()
                self.value = self.left.value + self.right.value
                self.left = self.right = None
                self.materialized = True

    events = []
    def evaluate(value):
        value.evaluate()
        events.append(('evaluated', value.value))
    def clear_cache():
        assert events[-1][0] == 'evaluated'
        events.append(('cleared', None))
    accumulated = None
    for value in [1, 2, 3, 4]:
        accumulated = training.materialize_accumulation(
            accumulated, DeferredSum(value),
            add=lambda left, right: DeferredSum(left=left, right=right),
            evaluate=evaluate, clear_cache=clear_cache)
    assert accumulated.value == 10
    assert accumulated.left is None and accumulated.right is None
    assert events == [('evaluated', 1), ('cleared', None), ('evaluated', 3), ('cleared', None),
                      ('evaluated', 6), ('cleared', None), ('evaluated', 10), ('cleared', None)]


def test_cli_exposes_checkpointing_without_changing_training_semantics():
    args = training.build_parser().parse_args(['--base-model', '/base', '--data-dir', '/data', '--adapter-dir', '/new',
                                              '--mode', 'pilot', '--iterations', '100', '--max-seq-length', '1024',
                                              '--grad-accumulation', '4', '--grad-checkpoint'])
    config = training.TrainingConfig(**{name: getattr(args, name) for name in training.TrainingConfig.__dataclass_fields__})
    config.validate()
    assert config.grad_checkpoint is True
    assert (config.iterations, config.max_seq_length, config.grad_accumulation, config.learning_rate) == (100, 1024, 4, 1e-5)


def test_native_checkpoint_helper_preserves_loss_and_gradients_on_cpu():
    mx = pytest.importorskip('mlx.core', reason='optional isolated MLX runtime CPU proof')
    previous_device = mx.default_device()
    mx.set_default_device(mx.cpu)
    try:
        import mlx.nn as nn
        from mlx.utils import tree_flatten
        from mlx_lm.tuner.trainer import grad_checkpoint

        class Decoder(nn.Module):
            def __init__(self, weight):
                super().__init__()
                self.weight = mx.array(weight, dtype=mx.float32)

            def __call__(self, values):
                return mx.tanh(values @ self.weight)

        class TinyModel(nn.Module):
            def __init__(self):
                super().__init__()
                self.layers = [Decoder([[1., .2], [.3, 1.]]), Decoder([[.5], [.7]])]

            def __call__(self, values):
                for layer in self.layers:
                    values = layer(values)
                return values

        model = TinyModel()
        inputs = mx.array([[1., 2.], [-1., .5]], dtype=mx.float32)
        loss = lambda current: mx.mean(current(inputs)**2)
        before_loss, before_grads = nn.value_and_grad(model, loss)(model)
        mx.eval(before_loss, before_grads)
        receipt = {}
        training.enable_gradient_checkpointing(model.layers, grad_checkpoint, receipt)
        after_loss, after_grads = nn.value_and_grad(model, loss)(model)
        mx.eval(after_loss, after_grads)
        assert mx.default_device() == mx.cpu
        assert float(after_loss.item()) == pytest.approx(float(before_loss.item()), rel=1e-6)
        left, right = dict(tree_flatten(before_grads)), dict(tree_flatten(after_grads))
        assert left.keys() == right.keys()
        assert all(bool(mx.allclose(left[key], right[key], rtol=1e-6).item()) for key in left)
    finally:
        mx.set_default_device(previous_device)
