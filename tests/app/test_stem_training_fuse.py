"""CPU proofs for reversible, scoped hybrid fusion; no model or MLX import."""
import copy
import hashlib
import importlib
import json
from pathlib import Path
import struct
import sys
from types import ModuleType, SimpleNamespace

import pytest


def fusion_module():
    return importlib.import_module('tutor_app.stem_training_fuse')


def write_tensors(path, values):
    header, payload = {}, bytearray()
    for name, (dtype, shape, data) in values.items():
        start = len(payload)
        payload.extend(data)
        header[name] = {'dtype': dtype, 'shape': shape, 'data_offsets': [start, len(payload)]}
    encoded = json.dumps(header).encode()
    path.write_bytes(struct.pack('<Q', len(encoded)) + encoded + payload)


def test_only_last_eight_mlp_layers_enter_hybrid_quantization_config():
    fuse = fusion_module()
    names = fuse.EXPECTED_MODULES
    original = {'model_type': 'qwen3_5', 'vision_config': {'hidden_size': 8},
                'quantization': {'bits': 4, 'group_size': 64, 'mode': 'affine'}}
    result = fuse.hybrid_config(original, names)
    assert original['quantization'] == {'bits': 4, 'group_size': 64, 'mode': 'affine'}
    assert len(names) == 24
    assert result['quantization']['bits'] == 4
    assert result['quantization']['group_size'] == 64
    assert all(result['quantization'][name] is False for name in names)
    assert result['quantization_config'] == result['quantization']
    assert result['vision_config'] == original['vision_config']  # Native save removes unused vision metadata.
    for bad in [names[:-1], (*names, names[0]), (*names[:-1], 'language_model.model.layers.23.mlp.gate_proj')]:
        with pytest.raises(ValueError, match='24|scope'):
            fuse.hybrid_config(original, bad)


@pytest.mark.parametrize('quantization', [None, {'bits': 8, 'group_size': 64},
                                        {'bits': 4, 'group_size': 32}, {'bits': 4, 'group_size': 64, 'mode': 'nf4'}])
def test_fusion_does_not_silently_change_base_quantization(quantization):
    fuse = fusion_module()
    with pytest.raises(ValueError, match='affine'):
        fuse.hybrid_config({'quantization': quantization}, fuse.EXPECTED_MODULES)


def test_tensor_inventory_hashes_exact_bf16_bytes_without_numpy(tmp_path):
    fuse = fusion_module()
    path = tmp_path/'model.safetensors'
    write_tensors(path, {'a.weight': ('BF16', [2], b'\x80\x3f\x00\x40'),
                         'b.weight': ('U32', [1], b'\x01\x00\x00\x00')})
    result = fuse.tensor_inventory([path])
    assert result['a.weight'] == {'dtype': 'BF16', 'shape': [2], 'bytes': 4,
                                  'sha256': hashlib.sha256(b'\x80\x3f\x00\x40').hexdigest()}
    assert result['b.weight']['bytes'] == 4
    with pytest.raises(ValueError, match='Duplicate'):
        fuse.tensor_inventory([path, path])


@pytest.mark.parametrize('header', [
    {'x': {'dtype': 'BF16', 'shape': [2], 'data_offsets': [0, 99]}},
    {'x': {'dtype': 'BF16', 'shape': [3], 'data_offsets': [0, 4]}},
    {'x': {'dtype': 'BF16', 'shape': [-1], 'data_offsets': [0, 4]}},
    {'x': {'dtype': 'BF16', 'shape': [2], 'data_offsets': [4, 0]}},
])
def test_invalid_tensor_offsets_and_shapes_are_rejected(tmp_path, header):
    path = tmp_path/'invalid.safetensors'
    encoded = json.dumps(header).encode()
    path.write_bytes(struct.pack('<Q', len(encoded)) + encoded + b'1234')
    with pytest.raises(ValueError, match='tensor'):
        fusion_module().tensor_inventory([path])


def test_hybrid_layout_requires_unchanged_untrained_tensors_and_float_targets():
    fuse = fusion_module()
    before = {'embed.weight': {'dtype': 'U32', 'shape': [1], 'bytes': 4, 'sha256': 'same'}}
    after = copy.deepcopy(before)
    for name in fuse.EXPECTED_MODULES:
        before[name+'.linear.weight'] = {'dtype': 'U32', 'shape': [1, 1], 'bytes': 4, 'sha256': 'old'}
        before[name+'.lora_a'] = {'dtype': 'F32', 'shape': [1], 'bytes': 4, 'sha256': 'adapter'}
        after[name+'.weight'] = {'dtype': 'BF16', 'shape': [1, 8], 'bytes': 16, 'sha256': 'fused'}
    fuse.verify_hybrid_layout(before, after, fuse.EXPECTED_MODULES)
    altered = copy.deepcopy(after)
    altered['embed.weight']['sha256'] = 'changed'
    with pytest.raises(ValueError, match='Untrained'):
        fuse.verify_hybrid_layout(before, altered, fuse.EXPECTED_MODULES)
    altered = copy.deepcopy(after)
    altered[fuse.EXPECTED_MODULES[0]+'.weight']['dtype'] = 'U32'
    with pytest.raises(ValueError, match='floating'):
        fuse.verify_hybrid_layout(before, altered, fuse.EXPECTED_MODULES)
    altered = copy.deepcopy(after)
    altered[fuse.EXPECTED_MODULES[0]+'.weight']['shape'] = [8, 1]
    with pytest.raises(ValueError, match='shape'):
        fuse.verify_hybrid_layout(before, altered, fuse.EXPECTED_MODULES)
    altered = copy.deepcopy(after)
    altered[fuse.EXPECTED_MODULES[0]+'.scales'] = {'dtype': 'BF16'}
    with pytest.raises(ValueError, match='floating'):
        fuse.verify_hybrid_layout(before, altered, fuse.EXPECTED_MODULES)


def fixture_run(tmp_path, monkeypatch):
    from tutor_app import stem_training as training
    fuse = fusion_module()
    monkeypatch.setattr(training, 'SSD_ROOT', tmp_path)
    base, adapter = tmp_path/'base', tmp_path/'adapter'
    base.mkdir(); adapter.mkdir()
    files = {'config.json': '{}', 'tokenizer.json': '{}', 'tokenizer_config.json': '{}',
             'chat_template.jinja': 'template', 'model.safetensors': 'base weights'}
    for name, value in files.items():
        (base/name).write_text(value)
    identity = {'repository': 'mlx-community/Qwen3.5-4B-4bit', 'revision': training.BASE_REVISION,
                'upstream_repository': 'Qwen/Qwen3.5-4B',
                'upstream_revision': '851bf6e806efd8d0a36b00ddf55e13ccb7b8cd0a', 'verified': True,
                'files': {name: {'size': (base/name).stat().st_size, 'sha256': training.sha256_file(base/name)}
                          for name in files}}
    license_path = tmp_path/'LICENSE'
    license_path.write_text('license')
    identity['license'] = {'name': 'Apache-2.0', 'path': str(license_path), 'sha256': training.sha256_file(license_path)}
    receipt = tmp_path/'base-receipt.json'
    receipt.write_text(json.dumps(identity))
    tensor_values = {f'{name}.lora_{part}': ('F32', [1], struct.pack('<f', 1.0))
                     for name in fuse.EXPECTED_MODULES for part in ('a', 'b')}
    write_tensors(adapter/'000025_adapters.safetensors', tensor_values)
    (adapter/'adapters.safetensors').write_bytes((adapter/'000025_adapters.safetensors').read_bytes())
    write_tensors(adapter/'000000_adapters.safetensors', {name: (dtype, shape, b'\0\0\0\0')
                  for name, (dtype, shape, _) in tensor_values.items()})
    (adapter/'adapter_config.json').write_text(json.dumps({'fine_tune_type': 'lora', 'num_layers': 8,
        'lora_parameters': training.LORA_PARAMETERS, 'model': str(base)}))
    record = {'state': 'completed', 'config': {'mode': 'pilot'}, 'base_model': str(base),
              'base_revision': training.BASE_REVISION, 'base_receipt_sha256': training.sha256_file(receipt),
              'accepted_checkpoint': '000025_adapters.safetensors', 'updates_completed': 25,
              'validation_loss': [{'update': 0, 'loss': 1.0}, {'update': 25, 'loss': .8}]}
    (adapter/'training_receipt.json').write_text(json.dumps(record))
    return fuse, base, receipt, adapter, record


def test_preparation_pins_accepted_nonzero_checkpoint_without_loading_mlx(tmp_path, monkeypatch):
    fuse, base, receipt, adapter, _ = fixture_run(tmp_path, monkeypatch)
    before = set(sys.modules)
    result = fuse.prepare_fusion(base, receipt, adapter, tmp_path/'fused')
    assert result['accepted_update'] == 25
    assert result['state'] == 'prepared'
    assert result['source_files']['adapters.safetensors']['sha256'] == result['source_files']['000025_adapters.safetensors']['sha256']
    assert not (tmp_path/'fused').exists()
    assert not any(name == 'mlx' or name.startswith('mlx.') for name in set(sys.modules)-before)


@pytest.mark.parametrize('change', [
    lambda record: record.update(accepted_checkpoint='000000_adapters.safetensors'),
    lambda record: record.update(accepted_checkpoint='../000025_adapters.safetensors'),
    lambda record: record.update(base_revision='other'),
    lambda record: record.update(validation_loss=[{'update': 0, 'loss': 1.0}]),
    lambda record: record.update(config={'mode': 'smoke'}),
])
def test_untrained_or_unaccepted_checkpoint_cannot_be_fused(tmp_path, monkeypatch, change):
    fuse, base, receipt, adapter, record = fixture_run(tmp_path, monkeypatch)
    change(record)
    (adapter/'training_receipt.json').write_text(json.dumps(record))
    with pytest.raises(ValueError):
        fuse.prepare_fusion(base, receipt, adapter, tmp_path/'fused')


def test_canonical_adapter_must_match_selected_checkpoint_and_change_from_initial(tmp_path, monkeypatch):
    fuse, base, receipt, adapter, _ = fixture_run(tmp_path, monkeypatch)
    (adapter/'adapters.safetensors').write_bytes(b'wrong')
    with pytest.raises(ValueError, match='canonical'):
        fuse.prepare_fusion(base, receipt, adapter, tmp_path/'fused')
    (adapter/'adapters.safetensors').write_bytes((adapter/'000025_adapters.safetensors').read_bytes())
    (adapter/'000000_adapters.safetensors').write_bytes((adapter/'adapters.safetensors').read_bytes())
    with pytest.raises(ValueError, match='unchanged'):
        fuse.prepare_fusion(base, receipt, adapter, tmp_path/'fused')


def test_output_is_new_separate_and_on_ssd(tmp_path, monkeypatch):
    fuse, base, receipt, adapter, _ = fixture_run(tmp_path, monkeypatch)
    for output in [base, base/'child', adapter, adapter/'child', tmp_path.parent/'outside']:
        with pytest.raises(ValueError):
            fuse.prepare_fusion(base, receipt, adapter, output)


def test_adapter_symlink_cannot_read_a_checkpoint_outside_its_directory(tmp_path, monkeypatch):
    fuse, base, receipt, adapter, _ = fixture_run(tmp_path, monkeypatch)
    outside = tmp_path/'borrowed.safetensors'
    (adapter/'adapters.safetensors').rename(outside)
    (adapter/'adapters.safetensors').symlink_to(outside)
    with pytest.raises(ValueError, match='source'):
        fuse.prepare_fusion(base, receipt, adapter, tmp_path/'fused')


def test_execution_revalidates_destination_in_a_prepared_plan(tmp_path, monkeypatch):
    import importlib.metadata
    fuse, base, receipt, adapter, _ = fixture_run(tmp_path, monkeypatch)
    plan = fuse.prepare_fusion(base, receipt, adapter, tmp_path/'fused')
    outside = tmp_path.parent/'outside-fusion'
    plan['output'] = str(outside)
    monkeypatch.setattr(importlib.metadata, 'version', lambda name:
                        {'mlx': '0.32.3', 'mlx-lm': '0.32.2', 'transformers': '5.20.2'}[name])
    with pytest.raises(ValueError, match='SSD|external'):
        fuse.run_fusion(plan)
    assert not outside.exists()


def test_generation_assets_are_copied_exactly_and_changes_are_detected(tmp_path):
    fuse = fusion_module()
    base, output = tmp_path/'base', tmp_path/'fused'
    base.mkdir(); output.mkdir()
    for name in ('tokenizer.json', 'tokenizer_config.json', 'chat_template.jinja', 'vocab.json', 'generation_config.json'):
        (base/name).write_text(name+'\n')
    assets = fuse.copy_generation_assets(base, output)
    assert len(assets) == 5
    assert all((base/name).read_bytes() == (output/name).read_bytes() for name in assets)
    (output/'generation_config.json').write_text('changed')
    with pytest.raises(ValueError, match='asset'):
        fuse.verify_generation_assets(output, assets)


def test_generation_assets_are_frozen_in_preparation_even_when_not_in_snapshot_receipt(tmp_path, monkeypatch):
    fuse, base, receipt, adapter, _ = fixture_run(tmp_path, monkeypatch)
    (base/'generation_config.json').write_text('{"eos_token_id": 1}')
    plan = fuse.prepare_fusion(base, receipt, adapter, tmp_path/'fused')
    (base/'generation_config.json').write_text('{"eos_token_id": 2}')
    with pytest.raises(ValueError, match='asset'):
        fuse.verify_sources(plan)


def test_upstream_license_cannot_change_between_preparation_and_fusion(tmp_path, monkeypatch):
    fuse, base, receipt, adapter, _ = fixture_run(tmp_path, monkeypatch)
    plan = fuse.prepare_fusion(base, receipt, adapter, tmp_path/'fused')
    Path(plan['license']['path']).write_text('changed')
    with pytest.raises(ValueError, match='license'):
        fuse.verify_sources(plan)


def test_saved_tokenizer_assets_cannot_add_a_different_token_configuration(tmp_path):
    fuse = fusion_module()
    base, output = tmp_path/'base', tmp_path/'fused'
    base.mkdir(); output.mkdir()
    (base/'tokenizer.json').write_text('{}')
    (output/'added_tokens.json').write_text('{"extra":1}')
    fuse.copy_generation_assets(base, output)
    assert not (output/'added_tokens.json').exists()


def test_native_tokenizer_identity_requires_distinct_reasoning_and_real_stops():
    fuse = fusion_module()
    class Tokenizer:
        eos_token_id = 3
        eos_token_ids = {3, 4}
        chat_template = 'template'
        def get_vocab(self):
            return {'<think>': 1, '</think>': 2, '<stop>': 3}
    result = fuse.tokenizer_identity(Tokenizer())
    assert result['boundaries'] == {'<think>': 1, '</think>': 2}
    assert result['stop_tokens'] == [3, 4]
    class Broken(Tokenizer):
        def get_vocab(self):
            return {'<think>': 1, '</think>': 1}
    with pytest.raises(ValueError, match='identity'):
        fuse.tokenizer_identity(Broken())


def test_system_resource_failure_is_durable_before_importing_mlx(tmp_path, monkeypatch):
    import builtins
    import importlib.metadata
    from tutor_app import stem_training as training
    fuse, base, receipt, adapter, _ = fixture_run(tmp_path, monkeypatch)
    output = tmp_path/'fused'
    plan = fuse.prepare_fusion(base, receipt, adapter, output)
    versions = {'mlx': '0.32.3', 'mlx-lm': '0.32.2', 'transformers': '5.20.2'}
    monkeypatch.setattr(importlib.metadata, 'version', lambda name: versions[name])
    monkeypatch.setattr(training, 'configure_ssd_caches', lambda: None)
    def stopped():
        raise training.TrainingStopped('Not normal')
    monkeypatch.setattr(training, 'ResourceMonitor', stopped)
    original = builtins.__import__
    def no_mlx(name, *args, **kwargs):
        if name == 'mlx' or name.startswith('mlx.') or name == 'mlx_lm' or name.startswith('mlx_lm.'):
            raise AssertionError('MLX imported before system resource check')
        return original(name, *args, **kwargs)
    monkeypatch.setattr(builtins, '__import__', no_mlx)
    with pytest.raises(training.TrainingStopped, match='Not normal'):
        fuse.run_fusion(plan)
    record = json.loads((output/'fusion_receipt.json').read_text())
    assert record['state'] == 'stopped'
    assert 'Not normal' in record['error']


def test_early_stopped_pilot_uses_prior_accepted_checkpoint_not_pending_candidate(tmp_path, monkeypatch):
    fuse, base, receipt, adapter, record = fixture_run(tmp_path, monkeypatch)
    record.update(state='stopped', updates_completed=30, checkpoint_eligibility='rejected',
                  last_checkpoint='000030_rejected_adapters.safetensors')
    (adapter/'training_receipt.json').write_text(json.dumps(record))
    (adapter/'000030_rejected_adapters.safetensors').write_bytes(b'never select this')
    plan = fuse.prepare_fusion(base, receipt, adapter, tmp_path/'fused')
    assert plan['accepted_update'] == 25
    assert '000030_rejected_adapters.safetensors' not in plan['source_files']


def test_prepare_cli_prints_reviewable_receipt_without_creating_model_output(tmp_path, monkeypatch, capsys):
    fuse, base, receipt, adapter, _ = fixture_run(tmp_path, monkeypatch)
    output = tmp_path/'fused'
    assert fuse.main(['--base-model', str(base), '--base-receipt', str(receipt),
                      '--adapter-dir', str(adapter), '--output', str(output)]) == 0
    result = json.loads(capsys.readouterr().out)
    assert result['state'] == 'prepared' and 'source_files' in result
    assert not output.exists()


def test_over_budget_load_stops_before_fusion_and_records_peak(tmp_path, monkeypatch):
    import importlib.metadata
    from tutor_app import stem_training as training
    fuse, base, receipt, adapter, _ = fixture_run(tmp_path, monkeypatch)
    output = tmp_path/'fused'
    plan = fuse.prepare_fusion(base, receipt, adapter, output)
    monkeypatch.setattr(importlib.metadata, 'version', lambda name:
                        {'mlx': '0.32.3', 'mlx-lm': '0.32.2', 'transformers': '5.20.2'}[name])
    monkeypatch.setattr(training, 'configure_ssd_caches', lambda: None)
    original_monitor = training.ResourceMonitor
    monkeypatch.setattr(training, 'ResourceMonitor', lambda: original_monitor(probe=lambda:
                        {'pressure': 1, 'swap_used_bytes': 0, 'disk_free_bytes': 40 * 1024**3}))
    state = {'peak': 0, 'clears': 0}
    mx = ModuleType('mlx.core')
    mx.set_memory_limit = mx.set_cache_limit = mx.eval = lambda *args: None
    mx.reset_peak_memory = lambda: state.update(peak=0)
    mx.get_active_memory = lambda: 2 * 1024**3
    mx.get_peak_memory = lambda: state['peak']
    mx.get_cache_memory = lambda: 0
    mx.clear_cache = lambda: state.update(clears=state['clears'] + 1)
    class Model:
        def parameters(self):
            return {}
        def named_modules(self):
            raise AssertionError('Fusion must not start after a load overrun')
    def load(*args, **kwargs):
        state['peak'] = 17 * 1024**3
        return Model(), None, {}
    packages = {
        'mlx': SimpleNamespace(core=mx, nn=ModuleType('mlx.nn')),
        'mlx.core': mx, 'mlx.nn': ModuleType('mlx.nn'),
        'mlx.utils': SimpleNamespace(tree_flatten=lambda values: list(values.items()), tree_unflatten=lambda values: {}),
        'mlx_lm': SimpleNamespace(load=load),
        'mlx_lm.tuner': ModuleType('mlx_lm.tuner'),
        'mlx_lm.tuner.lora': SimpleNamespace(LoRALinear=type('LoRALinear', (), {})),
        'mlx_lm.utils': SimpleNamespace(save=lambda *args, **kwargs: None),
    }
    for name, value in packages.items():
        monkeypatch.setitem(sys.modules, name, value)
    with pytest.raises(training.TrainingStopped, match='observed MLX memory'):
        fuse.run_fusion(plan)
    record = json.loads((output/'fusion_receipt.json').read_text())
    assert record['state'] == 'stopped'
    assert record['memory_budget_exceeded'] is True
    assert record['peak_memory_bytes'] == 17 * 1024**3
    assert any(sample['phase'] == 'after_adapter_model_load' for sample in record['observed_memory'])
    assert state['clears'] >= 1
