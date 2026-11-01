"""Standalone bounded STEM LoRA pilot; importing this module needs only Python.

Preparation loads a local tokenizer only. MLX/model loading is confined to
``run_training`` and requires explicit ``--execute`` after GPU coordination.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
from pathlib import Path
import re
import signal
import time
from dataclasses import asdict, dataclass
from typing import Any, Callable

SSD_ROOT = Path('/Volumes/External SSD TB4/LocalAI')
RUNTIME_ROOT = SSD_ROOT / 'tutor-runtime/stem-training'
BASE_REVISION = '0e7ffd5c629ef7719d4cbc04069232580bfa9d9c'
LORA_PARAMETERS = {'rank': 8, 'scale': 2.0, 'dropout': 0.0,
                   'keys': ['mlp.gate_proj', 'mlp.up_proj', 'mlp.down_proj']}


@dataclass(frozen=True)
class TrainingConfig:
    mode: str = 'smoke'
    iterations: int = 5  # Optimizer updates, not accumulated microbatches.
    max_seq_length: int = 512
    batch_size: int = 1
    grad_accumulation: int = 1
    learning_rate: float = 1e-5
    memory_limit_gib: float = 14
    wall_time_seconds: float = 3600
    seed: int = 42
    grad_checkpoint: bool = False

    def validate(self):
        if self.mode not in {'smoke', 'pilot'}:
            raise ValueError('mode must be smoke or pilot')
        if not 1 <= self.iterations <= 100:
            raise ValueError('iterations must be 1..100 optimizer updates')
        if self.max_seq_length not in {512, 1024} or self.batch_size != 1:
            raise ValueError('Only sequence lengths 512/1024 and batch size 1 are permitted')
        if not 1 <= self.grad_accumulation <= 4 or self.learning_rate != 1e-5:
            raise ValueError('Pilot requires accumulation 1..4 and learning rate 1e-5')
        if not 0 < self.memory_limit_gib <= 16 or not 0 < self.wall_time_seconds <= 3600:
            raise ValueError('Memory is capped at 16 GiB and wall time at 3600 seconds')
        if self.mode == 'smoke' and (self.iterations, self.max_seq_length, self.grad_accumulation) != (5, 512, 1):
            raise ValueError('smoke requires 5 updates, 512 tokens and accumulation 1')


@dataclass(frozen=True)
class FinalExample:
    id: str
    tokens: list[int]
    offset: int

    @property
    def labelled_target_indices(self):
        return list(range(self.offset, len(self.tokens)))


@dataclass
class PreparedExamples:
    examples: list[FinalExample]
    dropped_ids: list[str]
    original_count: int


def _reject_private(value):
    if isinstance(value, dict):
        if any(str(k).lower() in {'analysis', 'reasoning', 'reasoning_content', 'chain_of_thought'} for k in value):
            raise ValueError('Hidden reasoning is not permitted in training gold')
        for child in value.values():
            _reject_private(child)
    elif isinstance(value, list):
        for child in value:
            _reject_private(child)
    elif isinstance(value, str) and ('<think>' in value or '</think>' in value):
        raise ValueError('Hidden reasoning markup is not permitted in training gold')


def validate_example(row):
    required = {'id', 'group', 'subject', 'task', 'messages', 'expected', 'provenance', 'checks'}
    if not required.issubset(row) or any(not isinstance(row[k], str) or not row[k].strip() for k in ('id', 'group', 'subject', 'task')):
        raise ValueError('Invalid training row metadata')
    messages = row['messages']
    if not isinstance(messages, list) or len(messages) != 2 or [m.get('role') for m in messages] != ['user', 'assistant']:
        raise ValueError('Exactly user and assistant messages are required')
    if any(set(m) != {'role', 'content'} or not isinstance(m['content'], str) or not m['content'] for m in messages):
        raise ValueError('Messages require public content only')
    if not isinstance(row['expected'], dict) or not isinstance(row['provenance'], list) or not row['provenance']:
        raise ValueError('Expected truth and provenance are required')
    if not isinstance(row['checks'], dict) or not row['checks'] or any(v is False for v in row['checks'].values()):
        raise ValueError('Training gold must have passing checks')
    _reject_private(messages[-1])
    _reject_private(json.loads(messages[-1]['content']))


def encode_final_example(row, tokenizer) -> FinalExample:
    """Locate the public final using rendered text and verified token offsets.

    MLX loss target position k predicts input token k. Returning the actual
    first public token index therefore matches default_loss's ``steps>=offset``.
    No token from the prompt or empty reasoning terminator is supervised.
    """
    validate_example(row)
    rendered = tokenizer.apply_chat_template(row['messages'], tokenize=False, add_generation_prompt=False)
    answer = row['messages'][-1]['content']
    answer_start = rendered.rfind(answer)
    if answer_start < 0:
        raise ValueError('Rendered assistant answer differs from training gold')
    prefix = rendered[:answer_start]
    boundary = prefix.rfind('</think>')
    if boundary < 0 or prefix[boundary + len('</think>'):].strip():
        raise ValueError('No unambiguous rendered final-only </think> boundary')
    encoded = tokenizer(rendered, add_special_tokens=False, return_offsets_mapping=True)
    tokens = list(encoded['input_ids'])
    offsets = encoded['offset_mapping']
    # Character and byte tokenizers can have repeated offsets, but no token may
    # span the masked/public seam: otherwise exact final-only loss is impossible.
    if any(start < answer_start < end for start, end in offsets):
        raise ValueError('A token straddles the final-only loss boundary')
    labelled = [i for i, (start, end) in enumerate(offsets) if start >= answer_start and end > start]
    if not labelled or labelled[0] == 0 or len(tokens) != len(offsets):
        raise ValueError('Tokenizer did not provide a valid final answer token offset')
    template_tokens = tokenizer.apply_chat_template(row['messages'], tokenize=True, add_generation_prompt=False, return_dict=False)
    if tokens != list(template_tokens):
        raise ValueError('Rendered tokenizer IDs differ from the native chat template')
    return FinalExample(row['id'], tokens, labelled[0])


def prepare_examples(rows, tokenizer, max_seq_length):
    encoded = [encode_final_example(row, tokenizer) for row in rows]
    kept = [e for e in encoded if len(e.tokens) <= max_seq_length]
    if not kept:
        raise ValueError('No examples remain after dropping overlength sequences')
    return PreparedExamples(kept, [e.id for e in encoded if len(e.tokens) > max_seq_length], len(encoded))


def select_for_run(prepared, config):
    if config.mode != 'smoke':
        return prepared
    import random
    rng = random.Random(config.seed)
    selected = {}
    for split, limit in [('train', 16), ('valid', 8)]:
        source = prepared[split]
        indices = sorted(rng.sample(range(len(source.examples)), min(limit, len(source.examples))))
        selected[split] = PreparedExamples([source.examples[i] for i in indices], source.dropped_ids, source.original_count)
    return selected


def sha256_file(path):
    digest = hashlib.sha256()
    with Path(path).open('rb') as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b''):
            digest.update(block)
    return digest.hexdigest()


def verify_base_receipt(base_model, receipt_path):
    receipt = json.loads(Path(receipt_path).read_text())
    identity = {'repository': 'mlx-community/Qwen3.5-4B-4bit', 'revision': BASE_REVISION,
                'upstream_repository': 'Qwen/Qwen3.5-4B',
                'upstream_revision': '851bf6e806efd8d0a36b00ddf55e13ccb7b8cd0a', 'verified': True}
    if any(receipt.get(key) != value for key, value in identity.items()):
        raise ValueError('Base receipt identity does not match the pinned authorised model')
    files = receipt.get('files', {})
    required = {'model.safetensors', 'config.json', 'tokenizer.json', 'tokenizer_config.json', 'chat_template.jinja'}
    if not required.issubset(files):
        raise ValueError('Base receipt is missing required model/tokenizer hashes')
    base = Path(base_model).resolve()
    for name, expected in files.items():
        path = base/name
        if Path(name).name != name or not path.resolve().is_relative_to(base):
            raise ValueError('Unsafe base receipt file path')
        if path.stat().st_size != expected['size'] or sha256_file(path) != expected['sha256']:
            raise ValueError(f'Base file size/hash differs from verified receipt: {name}')
    return receipt


def load_training_data(data_dir):
    """Read train/development only; test labels remain sealed."""
    data_dir = Path(data_dir)
    manifest = json.loads((data_dir/'manifest.json').read_text())
    rows = {}
    seen_ids, seen_groups = set(), set(manifest.get('splits', {}).get('test', {}).get('groups', []))
    for split in ('train', 'valid'):
        path = data_dir/f'{split}.jsonl'
        expected_hash = manifest.get('files', {}).get(path.name, {}).get('sha256')
        if not isinstance(expected_hash, str) or len(expected_hash) != 64:
            raise ValueError(f'{split} is missing its immutable manifest hash')
        if expected_hash != sha256_file(path):
            raise ValueError(f'{split} does not match immutable manifest hash')
        rows[split] = [json.loads(line) for line in path.read_text().splitlines() if line.strip()]
        groups = set()
        for row in rows[split]:
            validate_example(row)
            if row['id'] in seen_ids or row['group'] in seen_groups:
                raise ValueError('Duplicate id or group leaks across data splits')
            seen_ids.add(row['id'])
            groups.add(row['group'])
        seen_groups.update(groups)
        if not rows[split]:
            raise ValueError(f'{split} dataset is empty')
    return rows, manifest


def validate_paths(base_model, data_dir, adapter_dir):
    base, data, adapter = [Path(p).resolve() for p in (base_model, data_dir, adapter_dir)]
    root = SSD_ROOT.resolve()
    if any(not p.is_relative_to(root) for p in (base, data, adapter)):
        raise ValueError('Models, data and adapters must remain on the external SSD')
    if not base.is_dir() or not data.is_dir():
        raise ValueError('Base model and data directories must exist')
    if adapter.exists() or any(adapter.is_relative_to(p) or p.is_relative_to(adapter) for p in (base, data)):
        raise ValueError('Adapter directory must be new and separate from model/data')


def validate_adapter_names(names, total_layers):
    names = list(names)
    pattern = re.compile(r'(?:.*\.)?layers\.(\d+)\.mlp\.(gate_proj|up_proj|down_proj)\.lora_[ab]$')
    if not names:
        raise ValueError('No trainable adapter parameters')
    for name in names:
        match = pattern.fullmatch(name)
        if not match or not total_layers - 8 <= int(match.group(1)) < total_layers:
            raise ValueError(f'Non-pilot adapter parameter: {name}')


def write_json_atomic(path, value):
    path = Path(path)
    temp = path.with_name(path.name + '.tmp')
    temp.write_text(json.dumps(value, indent=2, sort_keys=True, allow_nan=False) + '\n')
    os.replace(temp, path)


class TrainingStopped(RuntimeError):
    pass


def validate_runtime_versions(versions):
    expected = {'mlx': '0.32.3', 'mlx-lm': '0.32.2', 'transformers': '5.20.2'}
    if any(versions.get(name) != version for name, version in expected.items()):
        raise ValueError(f'Training runtime version mismatch; required {expected}')


def resource_snapshot():
    import shutil
    import subprocess
    pressure = subprocess.check_output(['/usr/sbin/sysctl', '-n', 'kern.memorystatus_vm_pressure_level'], text=True, timeout=3)
    swap = subprocess.check_output(['/usr/sbin/sysctl', '-n', 'vm.swapusage'], text=True, timeout=3)
    match = re.search(r'used\s*=\s*([\d.]+)([MGT])', swap)
    if not match:
        raise ValueError('Cannot read swap usage for resource guard')
    return {'pressure': int(pressure),
            'swap_used_bytes': float(match.group(1)) * 1024 ** {'M': 2, 'G': 3, 'T': 4}[match.group(2)],
            'disk_free_bytes': shutil.disk_usage(SSD_ROOT).free}


class ResourceMonitor:
    def __init__(self, probe=resource_snapshot, clock=time.monotonic):
        self.probe, self.clock = probe, clock
        self.initial = probe()
        self.latest = self.initial
        self.warning_since = None
        if self.initial['pressure'] != 1:
            raise TrainingStopped('Memory pressure must recover to normal before model loading')
        self._check_limits(self.initial)

    def _check_limits(self, snapshot):
        if snapshot['pressure'] >= 4:
            raise TrainingStopped('Critical memory pressure')
        if snapshot['swap_used_bytes'] - self.initial['swap_used_bytes'] > 512 * 1024**2:
            raise TrainingStopped('Additional swap usage exceeded 512 MiB')
        if snapshot['disk_free_bytes'] < 20 * 1024**3:
            raise TrainingStopped('SSD free space fell below 20 GiB')

    def check(self):
        self.latest = self.probe()
        self._check_limits(self.latest)
        if self.latest['pressure'] > 1:
            now = self.clock()
            if self.warning_since is None:
                self.warning_since = now
            elif now - self.warning_since >= 10:
                raise TrainingStopped('Memory pressure warning sustained for 10 seconds')
        else:
            self.warning_since = None


class RunGuard:
    def __init__(self, wall_time_seconds, clock: Callable = time.monotonic, resource_check=None):
        self.clock = clock
        self.started = clock()
        self.wall_time_seconds = wall_time_seconds
        self.cancelled = ''
        self.previous = {}
        self.resource_check = resource_check

    def check(self):
        if self.cancelled:
            raise TrainingStopped(self.cancelled)
        if self.clock() - self.started >= self.wall_time_seconds:
            raise TrainingStopped('wall-time limit reached')
        if self.resource_check is not None:
            self.resource_check()

    def __enter__(self):
        for sig in (signal.SIGINT, signal.SIGTERM):
            self.previous[sig] = signal.signal(sig, lambda signum, frame: setattr(self, 'cancelled', signal.Signals(signum).name))
        return self

    def __exit__(self, *args):
        for sig, handler in self.previous.items():
            signal.signal(sig, handler)


class MlxMemoryMonitor:
    """Observe allocation after safe boundaries; no in-flight kernel hard cap."""
    def __init__(self, probe, budget_bytes, receipt):
        self.probe, self.budget_bytes, self.receipt = probe, budget_bytes, receipt
        receipt['observed_memory'] = []
        receipt['observed_memory_budget_bytes'] = budget_bytes
        receipt['memory_limit_semantics'] = 'MLX allocation guideline plus observed active/peak checks; cannot interrupt an in-flight kernel'

    def check(self, phase):
        observed = self.probe()
        self.receipt['observed_memory'].append({'phase': phase, **observed})
        if max(observed['active_bytes'], observed['peak_bytes']) > self.budget_bytes:
            self.receipt['memory_budget_exceeded'] = True
            raise TrainingStopped(f'observed MLX memory exceeded {self.budget_bytes} byte budget after {phase}')


def configure_ssd_caches():
    import sys
    import tempfile
    for name, child in {'HF_HOME': 'cache/huggingface', 'HF_DATASETS_CACHE': 'cache/datasets',
                        'TRANSFORMERS_CACHE': 'cache/transformers', 'PIP_CACHE_DIR': 'cache/pip',
                        'XDG_CACHE_HOME': 'cache', 'PYTHONPYCACHEPREFIX': 'cache/pycache', 'TMPDIR': 'tmp'}.items():
        path = RUNTIME_ROOT / child
        path.mkdir(parents=True, exist_ok=True)
        os.environ[name] = str(path)
    sys.pycache_prefix = str(RUNTIME_ROOT/'cache/pycache')
    tempfile.tempdir = str(RUNTIME_ROOT/'tmp')
    os.environ['HF_HUB_OFFLINE'] = '1'
    os.environ['TRANSFORMERS_OFFLINE'] = '1'


def enable_gradient_checkpointing(layers, checkpoint_layer, receipt):
    """Use MLX-LM's native helper once per decoder class (it wraps the class)."""
    classes = []
    for layer in layers:
        if type(layer) not in classes:
            checkpoint_layer(layer)
            classes.append(type(layer))
    receipt['gradient_checkpointing'] = {'enabled': True, 'decoder_layers': len(layers),
                                         'decoder_classes': [cls.__name__ for cls in classes],
                                         'implementation': 'mlx_lm.tuner.trainer.grad_checkpoint'}


def materialize_accumulation(accumulated, gradients, *, add, evaluate, clear_cache):
    """Release lazy sum graphs and allocator cache at every microbatch boundary."""
    result = gradients if accumulated is None else add(accumulated, gradients)
    evaluate(result)
    clear_cache()
    return result


def run_updates(config, backend, guard, receipt):
    """Bound optimizer updates explicitly, checkpointing on every exit path."""
    config.validate()
    completed, last_saved = 0, 0
    receipt.update(state='running', updates_completed=0, train_loss=[], validation_loss=[], checkpoint_eligibility='pending')
    backend.checkpoint(0)
    best_validation = math.inf
    rejected = False
    try:
        for update in range(1, config.iterations + 1):
            guard.check()
            if update == 1 or (update - 1) % 25 == 0:
                validation = backend.evaluate()
                if not math.isfinite(validation):
                    raise ValueError('Nonfinite validation loss')
                receipt['validation_loss'].append({'update': completed, 'loss': validation})
                if validation > best_validation:
                    rejected = True
                    receipt['checkpoint_eligibility'] = 'rejected'
                    raise TrainingStopped('development loss deteriorated')
                best_validation = min(best_validation, validation)
                if completed:
                    backend.accept_checkpoint(completed)
            losses, tokens = [], 0
            for _ in range(config.grad_accumulation):
                guard.check()
                loss, count = backend.micro_step()
                if not math.isfinite(loss) or count <= 0:
                    raise ValueError('Nonfinite loss or empty final-answer mask')
                losses.append(loss)
                tokens += count
            guard.check()
            backend.update()  # Backend rejects nonfinite gradients before mutation.
            completed = update
            receipt['updates_completed'] = completed
            receipt['train_loss'].append({'update': update, 'loss': sum(losses)/len(losses), 'tokens': tokens})
            if update % 25 == 0:
                backend.checkpoint(update, accepted=False)
                last_saved = update
        guard.check()
        validation = backend.evaluate()
        if not math.isfinite(validation):
            raise ValueError('Nonfinite final validation loss')
        receipt['validation_loss'].append({'update': completed, 'loss': validation})
        if validation > best_validation:
            rejected = True
            receipt['checkpoint_eligibility'] = 'rejected'
            raise TrainingStopped('development loss deteriorated at final validation')
        receipt['checkpoint_eligibility'] = 'accepted'
        receipt['state'] = 'completed'
    except TrainingStopped as error:
        receipt.update(state='stopped', stop_reason=str(error))
        raise
    except BaseException as error:
        receipt.update(state='failed', stop_reason=f'{type(error).__name__}: {error}')
        raise
    finally:
        if completed != last_saved or rejected:
            backend.checkpoint(completed, accepted=receipt['state'] == 'completed', rejected=rejected)
        elif receipt['state'] == 'completed':
            backend.accept_checkpoint(completed)
        receipt['elapsed_seconds'] = guard.clock() - guard.started


def run_training(base_model, adapter_dir, config, prepared, receipt):
    """GPU entrypoint. Call only after the coordinator grants GPU exclusivity."""
    import importlib.metadata
    versions = {name: importlib.metadata.version(name) for name in ('mlx', 'mlx-lm', 'transformers')}
    validate_runtime_versions(versions)
    resources = ResourceMonitor()
    receipt['runtime_versions'] = versions
    receipt['initial_resources'] = resources.initial
    import numpy as np
    import mlx.core as mx
    import mlx.nn as nn
    import mlx.optimizers as optimizers
    from mlx.utils import tree_flatten, tree_map
    from mlx_lm import load
    from mlx_lm.tuner.utils import linear_to_lora_layers

    budget_bytes = int(config.memory_limit_gib * 1024**3)
    # MLX documents this as a guideline, not a hard allocation ceiling. Leave
    # headroom in that hint and independently observe evaluated active/peak use.
    hint_bytes = int(budget_bytes * 0.875)
    mx.set_memory_limit(hint_bytes)
    mx.set_cache_limit(256 * 1024**2)
    mx.reset_peak_memory()
    memory = MlxMemoryMonitor(lambda: {'active_bytes': mx.get_active_memory(),
                                       'peak_bytes': mx.get_peak_memory(),
                                       'cache_bytes': mx.get_cache_memory()}, budget_bytes, receipt)
    receipt['mlx_allocation_guideline_bytes'] = hint_bytes

    def check_resources():
        resources.check()
        memory.check('before_next_step')

    mx.random.seed(config.seed)
    rng = np.random.default_rng(config.seed)
    adapter_dir = Path(adapter_dir)
    model = None
    backend = None
    with RunGuard(config.wall_time_seconds, resource_check=check_resources) as guard:
        try:
            guard.check()
            model, _ = load(str(base_model), tokenizer_config={'trust_remote_code': False, 'local_files_only': True}, trust_remote_code=False)
            memory.check('after_model_load')
            guard.check()
            model.freeze()
            linear_to_lora_layers(model, num_layers=8, config=LORA_PARAMETERS)
            parameters = dict(tree_flatten(model.trainable_parameters()))
            validate_adapter_names(parameters, len(model.layers))
            if len(parameters) != 48:
                raise ValueError(f'Expected 48 adapter tensors, found {len(parameters)}')
            mx.eval(parameters)
            memory.check('after_adapter_initialisation')
            receipt['trainable_parameters'] = sum(p.size for p in parameters.values())
            receipt['trainable_tensors'] = {name: list(p.shape) for name, p in parameters.items()}
            optimizer = optimizers.Adam(learning_rate=config.learning_rate)
            receipt['gradient_checkpointing'] = {'enabled': False}
            receipt['cache_clear_policy'] = 'every evaluated microbatch, optimizer update and development example'
            if config.grad_checkpoint:
                from mlx_lm.tuner.trainer import grad_checkpoint
                enable_gradient_checkpointing(model.layers, grad_checkpoint, receipt)

            def tensor_hashes():
                return {name: hashlib.sha256(np.asarray(value).tobytes()).hexdigest()
                        for name, value in tree_flatten(model.trainable_parameters())}

            def ensure_finite(values, kind):
                leaves = [value for _, value in tree_flatten(values)]
                checks = [mx.all(mx.isfinite(value)) for value in leaves]
                mx.eval(checks)
                memory.check(f'after_{kind}_finite_check')
                if not all(bool(value.item()) for value in checks):
                    raise ValueError(f'Nonfinite {kind}; retaining last finite adapter checkpoint')

            def loss_fn(current_model, example):
                batch = mx.array([example.tokens], dtype=mx.int32)
                logits = current_model(batch[:, :-1])
                targets = batch[:, 1:]
                # Target index k maps to token index k+1. The first public token
                # is example.offset, which must be included (not skipped).
                mask = mx.arange(1, len(example.tokens)) >= example.offset
                ce = nn.losses.cross_entropy(logits, targets).astype(mx.float32)
                return (ce * mask).sum() / mask.sum()

            loss_and_grad = nn.value_and_grad(model, loss_fn)

            class Backend:
                def __init__(self):
                    self.accumulated = None
                    self.order = []
                    self.initial_hashes = tensor_hashes()
                    receipt['initial_tensor_sha256'] = self.initial_hashes

                def micro_step(self):
                    if not self.order:
                        self.order = rng.permutation(len(prepared['train'].examples)).tolist()
                    example = prepared['train'].examples[self.order.pop()]
                    model.train()
                    loss, gradients = loss_and_grad(model, example)
                    mx.eval(loss, gradients)
                    memory.check('after_forward_backward')
                    ensure_finite(gradients, 'gradients')
                    self.accumulated = materialize_accumulation(
                        self.accumulated, gradients,
                        add=lambda a, b: tree_map(lambda x, y: x+y, a, b),
                        evaluate=mx.eval, clear_cache=mx.clear_cache)
                    memory.check('after_microbatch_accumulation')
                    return float(loss.item()), len(example.tokens) - example.offset

                def update(self):
                    gradients = tree_map(lambda value: value/config.grad_accumulation, self.accumulated)
                    ensure_finite(gradients, 'accumulated gradients')
                    optimizer.update(model, gradients)
                    mx.eval(model.trainable_parameters(), optimizer.state)
                    memory.check('after_optimizer_update')
                    ensure_finite(model.trainable_parameters(), 'adapter parameters')
                    self.accumulated = None
                    mx.clear_cache()

                def evaluate(self):
                    model.eval()
                    total, count = 0.0, 0
                    for example in prepared['valid'].examples:
                        guard.check()
                        value = loss_fn(model, example)
                        mx.eval(value)
                        memory.check('after_development_forward')
                        n = len(example.tokens) - example.offset
                        total += float(value.item()) * n
                        count += n
                        mx.clear_cache()
                    return total/count

                def accept_checkpoint(self, update):
                    memory.check('before_checkpoint_publication')
                    import shutil
                    target = adapter_dir/f'{update:06d}_adapters.safetensors'
                    temporary = adapter_dir/'publish.tmp.safetensors'
                    shutil.copyfile(target, temporary)
                    os.replace(temporary, adapter_dir/'adapters.safetensors')
                    receipt['accepted_checkpoint'] = target.name

                def checkpoint(self, update, *, accepted=True, rejected=False):
                    memory.check('before_checkpoint')
                    weights = dict(tree_flatten(model.trainable_parameters()))
                    validate_adapter_names(weights, len(model.layers))
                    ensure_finite(weights, 'checkpoint parameters')
                    temporary = adapter_dir/'checkpoint.tmp.safetensors'
                    mx.save_safetensors(str(temporary), weights)
                    memory.check('after_checkpoint_serialisation')
                    target = adapter_dir/f'{update:06d}_{"rejected_" if rejected else ""}adapters.safetensors'
                    os.replace(temporary, target)
                    if accepted:
                        self.accept_checkpoint(update)
                    if rejected:
                        receipt['rejected_checkpoint'] = target.name
                    receipt['last_checkpoint'] = target.name
                    receipt['peak_memory_bytes'] = mx.get_peak_memory()
                    write_json_atomic(adapter_dir/'training_receipt.json', receipt)

            backend = Backend()
            run_updates(config, backend, guard, receipt)
            final_hashes = tensor_hashes()
            receipt['final_tensor_sha256'] = final_hashes
            receipt['changed_tensors'] = [name for name in final_hashes if final_hashes[name] != backend.initial_hashes[name]]
            if not receipt['changed_tensors']:
                raise ValueError('No real adapter weight changes detected')
            # Reload only adapter tensors into the same model, avoiding a second
            # base allocation; an independent inference reload is a later gate.
            saved = mx.load(str(adapter_dir/'adapters.safetensors'))
            validate_adapter_names(saved, len(model.layers))
            model.load_weights(list(saved.items()), strict=False)
            mx.eval(model.trainable_parameters())
            memory.check('after_adapter_reload')
            if tensor_hashes() != final_hashes:
                raise ValueError('Saved adapter reload changed trained tensor values')
            receipt['adapter_reload_verified'] = True
        except BaseException as error:
            receipt.update(state='stopped' if isinstance(error, TrainingStopped) else 'failed', stop_reason=f'{type(error).__name__}: {error}')
            raise
        finally:
            receipt['peak_memory_bytes'] = mx.get_peak_memory()
            receipt['final_resources'] = resources.latest
            receipt['elapsed_seconds'] = guard.clock() - guard.started
            write_json_atomic(adapter_dir/'training_receipt.json', receipt)
            del backend, model
            mx.clear_cache()


def build_parser():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--base-model', type=Path, required=True)
    parser.add_argument('--data-dir', type=Path, required=True)
    parser.add_argument('--base-receipt', type=Path, help='Verified pinned snapshot receipt; required for --execute')
    parser.add_argument('--adapter-dir', type=Path, required=True, help='New SSD output directory; never overwritten')
    parser.add_argument('--mode', choices=['smoke', 'pilot'], default='smoke')
    parser.add_argument('--iterations', type=int, default=5, help='Optimizer updates, maximum 100')
    parser.add_argument('--max-seq-length', type=int, default=512)
    parser.add_argument('--grad-accumulation', type=int, default=1)
    parser.add_argument('--batch-size', type=int, default=1)
    parser.add_argument('--learning-rate', type=float, default=1e-5)
    parser.add_argument('--seed', type=int, default=42)
    parser.add_argument('--grad-checkpoint', action='store_true',
                        help='Enable native MLX-LM decoder gradient checkpointing; trades recomputation for lower backward memory')
    parser.add_argument('--memory-limit-gib', type=float, default=14,
                        help='Observed active/peak budget (maximum 16); MLX allocation hint is lower and is not a hard cap')
    parser.add_argument('--wall-time-seconds', type=float, default=3600)
    action = parser.add_mutually_exclusive_group()
    action.add_argument('--execute', action='store_true', help='Load model/train only after external GPU exclusivity is granted')
    action.add_argument('--prepare-only', action='store_true', help='Default: validate/tokenize without loading MLX or weights')
    return parser


def main(argv=None):
    args = build_parser().parse_args(argv)
    config = TrainingConfig(**{name: getattr(args, name) for name in TrainingConfig.__dataclass_fields__})
    config.validate()
    if args.execute and args.base_receipt is None:
        raise ValueError('--execute requires the verified --base-receipt')
    validate_paths(args.base_model, args.data_dir, args.adapter_dir)
    configure_ssd_caches()
    base_identity = verify_base_receipt(args.base_model, args.base_receipt) if args.base_receipt else None
    # This import is CPU-only; do not import mlx_lm just to access a tokenizer.
    from transformers import AutoTokenizer
    tokenizer = AutoTokenizer.from_pretrained(str(args.base_model), trust_remote_code=False, local_files_only=True)
    rows, manifest = load_training_data(args.data_dir)
    prepared = {split: prepare_examples(items, tokenizer, config.max_seq_length) for split, items in rows.items()}
    selected = select_for_run(prepared, config)
    manifest_sha = sha256_file(args.data_dir/'manifest.json')
    receipt = {'state': 'prepared', 'config': asdict(config), 'base_revision': base_identity['revision'] if base_identity else None,
               'base_receipt_sha256': sha256_file(args.base_receipt) if args.base_receipt else None,
               'base_model': str(args.base_model.resolve()), 'data_dir': str(args.data_dir.resolve()),
               'manifest_sha256': manifest_sha, 'lora_parameters': LORA_PARAMETERS, 'num_layers': 8,
               'selected_example_ids': {split: [e.id for e in value.examples] for split, value in selected.items()},
               'loss_mask': 'public final only, after rendered </think> and whitespace',
               'chat_template_sha256': hashlib.sha256(tokenizer.chat_template.encode()).hexdigest(),
               'data_sha256': {f'{split}.jsonl': sha256_file(args.data_dir/f'{split}.jsonl') for split in rows},
               'data_counts': {split: {'original': value.original_count, 'kept': len(value.examples), 'dropped_ids': value.dropped_ids,
                                     'max_tokens': max(len(e.tokens) for e in value.examples),
                                     'min_final_tokens': min(len(e.tokens)-e.offset for e in value.examples)}
                               for split, value in prepared.items()}}
    args.adapter_dir.mkdir(parents=True, exist_ok=False)
    write_json_atomic(args.adapter_dir/'training_receipt.json', receipt)
    write_json_atomic(args.adapter_dir/'adapter_config.json', {'fine_tune_type': 'lora', 'num_layers': 8,
                                                            'lora_parameters': LORA_PARAMETERS, 'model': str(args.base_model)})
    try:
        if args.execute:
            run_training(args.base_model, args.adapter_dir, config, selected, receipt)
    except BaseException as error:
        receipt.update(state='stopped' if isinstance(error, TrainingStopped) else 'failed',
                       stop_reason=f'{type(error).__name__}: {error}')
        raise
    finally:
        if sha256_file(args.data_dir/'manifest.json') != manifest_sha or any(
                sha256_file(args.data_dir/name) != digest for name, digest in receipt['data_sha256'].items()):
            receipt.update(state='failed', stop_reason='Immutable dataset manifest/content changed during run')
        write_json_atomic(args.adapter_dir/'training_receipt.json', receipt)
    print(json.dumps(receipt, indent=2))
    return 0 if receipt['state'] in {'prepared', 'completed'} else 2


if __name__ == '__main__':
    raise SystemExit(main())
