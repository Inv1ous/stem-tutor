"""Reversible hybrid fusion for the pinned STEM pilot, never an in-place conversion.

Only the 24 trained MLP linears become floating weights. All other packed tensors
must survive byte-for-byte. BF16 fusion rounding is not live-adapter numerical
identity; logit/answer parity, native import and quality remain separate gates.
Import and preparation are CPU-only. Model loading requires explicit execution.
"""
from __future__ import annotations

import argparse
import copy
import gc
import hashlib
import json
import math
from pathlib import Path
import re
import shutil
import struct

from . import stem_training as training


EXPECTED_MODULES = tuple(f'language_model.model.layers.{layer}.mlp.{projection}'
                         for layer in range(24, 32)
                         for projection in ('gate_proj', 'up_proj', 'down_proj'))
_WIDTHS = {'BOOL': 1, 'I8': 1, 'U8': 1, 'I16': 2, 'U16': 2, 'F16': 2, 'BF16': 2,
           'I32': 4, 'U32': 4, 'F32': 4, 'I64': 8, 'U64': 8, 'F64': 8,
           'F8_E4M3': 1, 'F8_E5M2': 1}
_ASSETS = ('tokenizer*', '*.jinja', 'special_tokens_map.json', 'added_tokens.json', 'vocab.*',
           'merges.txt', '*.tiktoken', 'generation_config.json')


def _validate_scope(names):
    names = tuple(names)
    if len(names) != 24 or set(names) != set(EXPECTED_MODULES):
        raise ValueError('Hybrid fusion requires exactly the 24 authorised MLP modules')


def hybrid_config(config, names):
    _validate_scope(names)
    result = copy.deepcopy(config)
    quantization = result.get('quantization')
    if (not isinstance(quantization, dict) or quantization.get('bits') != 4
            or quantization.get('group_size') != 64 or quantization.get('mode', 'affine') != 'affine'):
        raise ValueError('The pinned affine 4-bit/group-64 base is required')
    quantization.update({name: False for name in names})
    result['quantization_config'] = copy.deepcopy(quantization)
    return result


def tensor_inventory(paths):
    """Hash raw safetensor regions without dtype conversions or full-file loading."""
    result = {}
    for path in paths:
        path = Path(path)
        with path.open('rb') as handle:
            raw_size = handle.read(8)
            if len(raw_size) != 8:
                raise ValueError('Invalid safetensor header')
            header_size, = struct.unpack('<Q', raw_size)
            if not 2 <= header_size <= min(64 * 1024**2, path.stat().st_size - 8):
                raise ValueError('Invalid safetensor header length')
            header = json.loads(handle.read(header_size))
            if not isinstance(header, dict):
                raise ValueError('Invalid safetensor header object')
            offset, available = 8 + header_size, path.stat().st_size - 8 - header_size
            regions = []
            for name, entry in header.items():
                if name == '__metadata__':
                    continue
                if name in result:
                    raise ValueError(f'Duplicate tensor: {name}')
                if not isinstance(entry, dict):
                    raise ValueError('Invalid tensor metadata')
                dtype, shape, span = entry.get('dtype'), entry.get('shape'), entry.get('data_offsets')
                if (dtype not in _WIDTHS or not isinstance(shape, list) or len(shape) > 8
                        or any(type(value) is not int or value < 0 for value in shape)
                        or not isinstance(span, list) or len(span) != 2
                        or any(type(value) is not int for value in span)):
                    raise ValueError('Invalid tensor dtype, shape or offsets')
                start, end = span
                if not 0 <= start <= end <= available or end - start != math.prod(shape) * _WIDTHS[dtype]:
                    raise ValueError('Invalid tensor byte range or shape size')
                regions.append((start, end))
                digest, remaining = hashlib.sha256(), end - start
                handle.seek(offset + start)
                while remaining:
                    block = handle.read(min(1024**2, remaining))
                    if not block:
                        raise ValueError('Truncated tensor data')
                    digest.update(block)
                    remaining -= len(block)
                result[name] = {'dtype': dtype, 'shape': shape, 'bytes': end - start, 'sha256': digest.hexdigest()}
            ordered = sorted(regions)
            if any(left[1] > right[0] for left, right in zip(ordered, ordered[1:])):
                raise ValueError('Overlapping tensor regions')
    if not result:
        raise ValueError('No model tensors found')
    return result


def verify_hybrid_layout(before, after, names):
    _validate_scope(names)
    def target(name):
        return any(name.startswith(module + '.') for module in names)
    untouched = {name: value for name, value in before.items() if not target(name)}
    if untouched != {name: value for name, value in after.items() if not target(name)}:
        raise ValueError('Untrained tensors changed during hybrid fusion')
    for name in names:
        tensors = {key: value for key, value in after.items() if key.startswith(name + '.')}
        if set(tensors) != {name + '.weight'} or tensors[name + '.weight']['dtype'] not in {'BF16', 'F16', 'F32'}:
            raise ValueError(f'Hybrid target must contain one floating weight: {name}')
        packed = before.get(name + '.linear.weight', {})
        shape = packed.get('shape', [])
        if (packed.get('dtype') != 'U32' or len(shape) != 2
                or tensors[name + '.weight']['shape'] != [shape[0], shape[1] * 8]):
            raise ValueError(f'Fused matrix shape differs from the packed 4-bit base: {name}')


def _file_identity(path):
    return {'size': path.stat().st_size, 'sha256': training.sha256_file(path)}


def prepare_fusion(base_model, base_receipt, adapter_dir, output):
    base, receipt_path, adapter, destination = [Path(value).resolve() for value in
                                              (base_model, base_receipt, adapter_dir, output)]
    root = training.SSD_ROOT.resolve()
    if any(not value.is_relative_to(root) for value in (base, receipt_path, adapter, destination)):
        raise ValueError('Fusion inputs and output must remain on the external SSD')
    if not base.is_dir() or not adapter.is_dir() or destination.exists():
        raise ValueError('Source directories must exist and fusion output must be new')
    if any(destination.is_relative_to(source) or source.is_relative_to(destination) for source in (base, adapter)):
        raise ValueError('Fusion output must be separate from both source models')
    base_identity = training.verify_base_receipt(base, receipt_path)
    for name in ('training_receipt.json', 'adapter_config.json', 'adapters.safetensors', '000000_adapters.safetensors'):
        source = adapter / name
        if source.resolve().parent != adapter or not source.is_file():
            raise ValueError('Adapter source files must stay inside their own directory')
    record_path = adapter / 'training_receipt.json'
    record = json.loads(record_path.read_text())
    checkpoint = record.get('accepted_checkpoint', '')
    match = re.fullmatch(r'(\d{6})_adapters\.safetensors', checkpoint)
    if (not match or int(match[1]) == 0 or record.get('state') not in {'completed', 'stopped'}
            or record.get('config', {}).get('mode') != 'pilot'
            or record.get('base_revision') != training.BASE_REVISION
            or record.get('base_receipt_sha256') != training.sha256_file(receipt_path)
            or Path(record.get('base_model', '')).resolve() != base):
        raise ValueError('A nonzero development-accepted pilot checkpoint of this base is required')
    update = int(match[1])
    validation = record.get('validation_loss', [])
    losses = [item.get('loss') for item in validation if item.get('update') == update]
    if (type(record.get('updates_completed')) is not int or update > record['updates_completed']
            or not losses or any(type(loss) not in (float, int) or not math.isfinite(loss) for loss in losses)):
        raise ValueError('The accepted checkpoint has no completed finite development assessment')
    selected, canonical, initial = [adapter / name for name in (checkpoint, 'adapters.safetensors', '000000_adapters.safetensors')]
    if selected.resolve().parent != adapter or not selected.is_file():
        raise ValueError('Accepted adapter source must stay inside its own directory')
    if training.sha256_file(selected) != training.sha256_file(canonical):
        raise ValueError('The canonical adapter differs from its accepted checkpoint')
    if training.sha256_file(initial) == training.sha256_file(canonical):
        raise ValueError('The accepted adapter is unchanged from its untrained initial weights')
    config_path = adapter / 'adapter_config.json'
    config = json.loads(config_path.read_text())
    if (config.get('fine_tune_type') != 'lora' or config.get('num_layers') != 8
            or config.get('lora_parameters') != training.LORA_PARAMETERS
            or Path(config.get('model', '')).resolve() != base):
        raise ValueError('Adapter configuration differs from the authorised pilot scope')
    tensors = tensor_inventory([canonical])
    expected = {f'{module}.lora_{part}' for module in EXPECTED_MODULES for part in ('a', 'b')}
    if set(tensors) != expected:
        raise ValueError('Adapter tensors differ from the authorised 48-tensor scope')
    license_record = base_identity.get('license', {})
    license_path = Path(license_record.get('path', '')).resolve()
    if (not license_path.is_relative_to(root) or not license_path.is_file()
            or training.sha256_file(license_path) != license_record.get('sha256')):
        raise ValueError('The verified upstream license is required')
    return {'state': 'prepared', 'base_model': str(base), 'base_receipt': str(receipt_path),
            'base_receipt_sha256': training.sha256_file(receipt_path), 'base_identity': base_identity,
            'adapter_dir': str(adapter), 'output': str(destination), 'accepted_update': update,
            'source_files': {path.name: _file_identity(path) for path in
                             (record_path, config_path, selected, canonical, initial)},
            'generation_assets': {path.name: _file_identity(path) for path in _asset_paths(base)},
            'license': license_record, 'module_names': list(EXPECTED_MODULES),
            'rounding': 'Only trained linears fuse to their dequantised floating dtype; BF16 rounding can differ from live LoRA.',
            'remaining_gates': ['adapter/fused logit and answer parity', 'native MLX import',
                                'Fast/Deep protocol and latency', 'held-out scientific quality']}


def verify_sources(plan):
    training.verify_base_receipt(plan['base_model'], plan['base_receipt'])
    if training.sha256_file(plan['base_receipt']) != plan['base_receipt_sha256']:
        raise ValueError('Base receipt changed during fusion')
    for name, expected in plan['source_files'].items():
        if _file_identity(Path(plan['adapter_dir']) / name) != expected:
            raise ValueError(f'Adapter source changed during fusion: {name}')
    if {path.name: _file_identity(path) for path in _asset_paths(plan['base_model'])} != plan['generation_assets']:
        raise ValueError('Base generation assets changed during fusion')
    if training.sha256_file(plan['license']['path']) != plan['license']['sha256']:
        raise ValueError('Upstream license changed during fusion')


def _asset_paths(root):
    root = Path(root).resolve()
    paths = sorted({path for pattern in _ASSETS for path in root.glob(pattern) if path.is_file()})
    if any(path.resolve().parent != root for path in paths):
        raise ValueError('Generation assets must be regular files inside the model directory')
    return paths


def copy_generation_assets(base, output):
    base, output = Path(base), Path(output)
    assets = {}
    for source in _asset_paths(base):
        shutil.copyfile(source, output / source.name)
        assets[source.name] = _file_identity(source)
    # save_pretrained can invent additional token-configuration files. Restore
    # the original file set as well as bytes, then prove runtime identity again.
    for generated in _asset_paths(output):
        if generated.name not in assets:
            generated.unlink()
    verify_generation_assets(output, assets)
    return assets


def verify_generation_assets(output, assets):
    if {path.name for path in _asset_paths(output)} != set(assets):
        raise ValueError('Generation asset file set changed')
    for name, expected in assets.items():
        path = Path(output) / name
        if not path.is_file() or _file_identity(path) != expected:
            raise ValueError(f'Generation asset changed: {name}')


def tokenizer_identity(tokenizer):
    vocab = tokenizer.get_vocab()
    boundaries = {name: vocab.get(name) for name in ('<think>', '</think>')}
    stops = set(getattr(tokenizer, 'eos_token_ids', []) or [])
    if isinstance(tokenizer.eos_token_id, int):
        stops.add(tokenizer.eos_token_id)
    if (any(type(value) is not int for value in boundaries.values()) or len(set(boundaries.values())) != 2
            or not stops or any(type(value) is not int for value in stops)):
        raise ValueError('The native reasoning or stop token identity is invalid')
    return {'boundaries': boundaries, 'stop_tokens': sorted(stops),
            'vocab_sha256': hashlib.sha256(json.dumps(vocab, sort_keys=True).encode()).hexdigest(),
            'chat_template_sha256': hashlib.sha256(tokenizer.chat_template.encode()).hexdigest()}


def run_fusion(plan):
    """Explicit GPU operation; the caller must hold exclusive local GPU ownership."""
    import importlib.metadata
    versions = {name: importlib.metadata.version(name) for name in ('mlx', 'mlx-lm', 'transformers')}
    training.validate_runtime_versions(versions)
    fresh = prepare_fusion(plan['base_model'], plan['base_receipt'], plan['adapter_dir'], plan['output'])
    if fresh != plan:
        raise ValueError('Prepared fusion plan differs from current immutable sources')
    destination = Path(plan['output'])
    destination.mkdir(parents=True, exist_ok=False)
    receipt = copy.deepcopy(plan)
    receipt.update(state='running', runtime_versions=versions)
    receipt_path = destination / 'fusion_receipt.json'
    training.write_json_atomic(receipt_path, receipt)
    temporary = destination / '.before.safetensors'
    reloaded = destination / '.reload.safetensors'
    mx = resources = model = tokenizer = modules = replacements = fused = module = loaded_modules = finite = None
    try:
        training.configure_ssd_caches()
        resources = training.ResourceMonitor()
        receipt['initial_resources'] = resources.initial
        import mlx.core as mx
        import mlx.nn as nn
        from mlx.utils import tree_flatten, tree_unflatten
        from mlx_lm import load
        from mlx_lm.tuner.lora import LoRALinear
        from mlx_lm.utils import save
        budget = 14 * 1024**3
        mx.set_memory_limit(int(budget * .875))
        mx.set_cache_limit(256 * 1024**2)
        mx.reset_peak_memory()
        memory = training.MlxMemoryMonitor(lambda: {'active_bytes': mx.get_active_memory(),
                                                   'peak_bytes': mx.get_peak_memory(),
                                                   'cache_bytes': mx.get_cache_memory()}, budget, receipt)
        def check(phase):
            memory.check(phase)
            resources.check()
        with training.RunGuard(600, resource_check=lambda: check('before_next_operation')) as guard:
            guard.check()
            model, tokenizer, config = load(plan['base_model'], adapter_path=plan['adapter_dir'], return_config=True,
                tokenizer_config={'trust_remote_code': False, 'local_files_only': True}, trust_remote_code=False)
            mx.eval(model.parameters())
            check('after_adapter_model_load')
            identity = tokenizer_identity(tokenizer)
            modules = {name: module for name, module in model.named_modules() if isinstance(module, LoRALinear)}
            _validate_scope(modules)
            mx.save_safetensors(str(temporary), dict(tree_flatten(model.parameters())))
            check('after_source_tensor_snapshot')
            before = tensor_inventory([temporary])
            temporary.unlink()
            replacements = []
            for name, module in modules.items():
                guard.check()
                fused = module.fuse(dequantize=True)
                mx.eval(fused.parameters())
                check('after_fused_' + name)
                if isinstance(fused, nn.QuantizedLinear) or not isinstance(fused, nn.Linear):
                    raise ValueError('Native fusion did not return a floating linear layer')
                finite = [mx.all(mx.isfinite(value)) for _, value in tree_flatten(fused.parameters())]
                mx.eval(finite)
                check('after_finite_' + name)
                if not all(bool(value.item()) for value in finite):
                    raise ValueError('Nonfinite fused weight')
                replacements.append((name, fused))
                mx.clear_cache()
            model.update_modules(tree_unflatten(replacements))
            del modules, replacements, fused, module
            guard.check()
            config = hybrid_config(config, EXPECTED_MODULES)
            save(destination, plan['base_model'], model, tokenizer, config, donate_model=False)
            check('after_hybrid_save')
            assets = copy_generation_assets(plan['base_model'], destination)
            saved = tensor_inventory(sorted(destination.glob('model*.safetensors')))
            verify_hybrid_layout(before, saved, EXPECTED_MODULES)
            receipt['untrained_tensors_unchanged'] = True
            receipt['fused_tensor_dtypes'] = {name: saved[name + '.weight']['dtype'] for name in EXPECTED_MODULES}
            receipt['tensor_inventory'] = saved
            receipt['generation_assets'] = assets
            receipt['tokenizer_identity'] = identity
            shutil.copyfile(plan['license']['path'], destination / 'LICENSE')
            training.write_json_atomic(destination / 'source_provenance.json',
                                       {'base': plan['base_identity'], 'adapter_files': plan['source_files'],
                                        'accepted_update': plan['accepted_update'], 'rounding': plan['rounding']})
            model = tokenizer = None
            gc.collect()
            mx.clear_cache()
            guard.check()
            model, tokenizer = load(str(destination), tokenizer_config={'trust_remote_code': False,
                'local_files_only': True}, trust_remote_code=False)
            mx.eval(model.parameters())
            check('after_hybrid_reload')
            if tokenizer_identity(tokenizer) != identity:
                raise ValueError('Reload changed tokenizer, template or stop identity')
            loaded_modules = dict(model.named_modules())
            if any(not isinstance(loaded_modules.get(name), nn.Linear)
                   or isinstance(loaded_modules.get(name), nn.QuantizedLinear) for name in EXPECTED_MODULES):
                raise ValueError('Reload did not preserve the 24 floating linear layers')
            mx.save_safetensors(str(reloaded), dict(tree_flatten(model.parameters())))
            check('after_reload_tensor_snapshot')
            if tensor_inventory([reloaded]) != saved:
                raise ValueError('Reload changed saved tensor values, dtypes or shapes')
            reloaded.unlink()
            verify_generation_assets(destination, assets)
            verify_sources(plan)
            guard.check()
            receipt.update(state='completed', saved_reload_verified=True,
                           output_files={path.name: _file_identity(path) for path in destination.iterdir()
                                         if path.is_file() and path.name != 'fusion_receipt.json'})
    except BaseException as exc:
        receipt.update(state='stopped' if isinstance(exc, training.TrainingStopped) else 'failed',
                       error=type(exc).__name__ + ': ' + str(exc))
        raise
    finally:
        model = tokenizer = modules = replacements = fused = module = loaded_modules = finite = None
        gc.collect()
        if mx is not None:
            mx.clear_cache()
        for path in (temporary, reloaded):
            if path.exists():
                path.unlink()
        receipt['final_resources'] = resources.latest if resources is not None else None
        receipt['peak_memory_bytes'] = mx.get_peak_memory() if mx is not None else None
        training.write_json_atomic(receipt_path, receipt)
    return receipt


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--base-model', type=Path, required=True)
    parser.add_argument('--base-receipt', type=Path, required=True)
    parser.add_argument('--adapter-dir', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--execute', action='store_true', help='Requires exclusive local GPU ownership')
    args = parser.parse_args(argv)
    plan = prepare_fusion(args.base_model, args.base_receipt, args.adapter_dir, args.output)
    result = run_fusion(plan) if args.execute else plan
    summary = {key: result[key] for key in ('state', 'output', 'accepted_update', 'remaining_gates')}
    print(json.dumps(summary if args.execute else plan, indent=2))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
