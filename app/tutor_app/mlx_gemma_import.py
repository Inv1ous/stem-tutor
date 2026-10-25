"""Lossless Ollama 0.40.11 repair for the tutor-owned Gemma MLX alias.

The importer preserves packed affine bytes but drops per-module precision and
uses expert names the native runner cannot load. Fuse each expert's gate/up
slabs, rename the down bank, and restore the source's explicit int8 metadata.
No model library, numeric conversion, inference, or checkpoint write is used.
"""
from __future__ import annotations

import argparse
import copy
from dataclasses import dataclass
import hashlib
import json
import math
import os
from pathlib import Path
import re
import struct
import sys
import tempfile
from typing import BinaryIO


ROOT = Path("/Volumes/External SSD TB4/LocalAI")
ALIAS = Path("manifests-v2/ollama.com/library/gemma4/26b-tutor-mlx")
SOURCE = Path("LMStudioModels/lmstudio-community/gemma-4-26B-A4B-it-QAT-MLX-4bit")
CONFIG_SHA256 = "29910322dd085f45c8f95c6c0f1611b20f722d6f6c8394321b34817e98a972fa"
TENSOR_MEDIA = "application/vnd.ollama.image.tensor"
CHUNK_SIZE = 1024 * 1024
HEADER_LIMIT = 16 * 1024 * 1024
JSON_LIMIT = 4 * 1024 * 1024


@dataclass
class _Blob:
    path: Path
    header: dict
    start: int
    size: int
    name: str
    keys: tuple[str, str, str]


@dataclass
class _Plan:
    name: str
    header: dict
    segments: list[tuple[Path, int, int]]


def _unique_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"Duplicate JSON key: {key}")
        result[key] = value
    return result


def _json(raw: bytes) -> dict:
    try:
        result = json.loads(raw, object_pairs_hook=_unique_object)
    except (UnicodeError, json.JSONDecodeError) as exc:
        raise ValueError("Invalid import JSON") from exc
    if not isinstance(result, dict):
        raise ValueError("Import JSON must be an object")
    return result


def _read_json(path: Path) -> tuple[bytes, dict]:
    with path.open("rb") as stream:
        raw = stream.read(JSON_LIMIT + 1)
    if len(raw) > JSON_LIMIT:
        raise ValueError("Import JSON is too large")
    return raw, _json(raw)


def _inside(root: Path, relative: Path) -> Path:
    path = root / relative
    if relative.is_absolute() or ".." in relative.parts or not path.resolve().is_relative_to(root):
        raise ValueError("Unsafe import path")
    current = root
    for part in relative.parts:
        current = current / part
        if current.is_symlink():
            raise ValueError("Symlink import paths are unsupported")
    return path


def _alias(root: Path):
    """Permit only the final, fixed v2 alias to link to a verified manifest blob."""
    target = _inside(root, ALIAS.parent) / ALIAS.name
    link = os.readlink(target) if target.is_symlink() else None
    if link is None:
        original, manifest = _read_json(_inside(root, ALIAS))
    else:
        # Normalize the alias's relative '..' segments without following any
        # additional symlink. Only this final alias may itself be a link.
        destination = Path(os.path.abspath(target.parent / link))
        if (destination.parent != root / "blobs"
                or not re.fullmatch(r"sha256-[0-9a-f]{64}", destination.name)):
            raise ValueError("Native alias must point to a content-addressed manifest blob")
        destination = _inside(root, destination.relative_to(root))
        original, manifest = _read_json(destination)
        if hashlib.sha256(original).hexdigest() != destination.name[7:]:
            raise ValueError("Native alias manifest digest does not match its blob name")
    return target, original, manifest, link


def _check_alias(root: Path, original: bytes, link: str | None):
    _, current, _, current_link = _alias(root)
    if current != original or current_link != link:
        raise ValueError("The alias changed during adaptation; original manifest retained")


def _positive(value) -> bool:
    return type(value) is int and value > 0


def _inspect(path: Path) -> _Blob:
    size = path.stat().st_size
    with path.open("rb") as stream:
        prefix = stream.read(8)
        if len(prefix) != 8:
            raise ValueError("Truncated safetensors prefix")
        length = struct.unpack("<Q", prefix)[0]
        if length > HEADER_LIMIT or length < 2 or length + 8 > size:
            raise ValueError("Unsupported safetensors header length")
        header = _json(stream.read(length))
    metadata = header.get("__metadata__")
    if (not isinstance(metadata, dict) or metadata.get("group_size") != "64"
            or metadata.get("quant_type") not in ("int4", "int8")
            or set(metadata) != {"group_size", "quant_type"}
            or any(not isinstance(value, str) for value in metadata.values())):
        raise ValueError("Expected affine int4/int8 group-64 metadata")
    names = [name for name in header if name != "__metadata__" and name.endswith(".weight")]
    if len(names) != 1:
        raise ValueError("Expected one packed weight in each imported blob")
    name = names[0]
    native = (name, name + ".scale", name + ".bias")
    source = (name, name.removesuffix(".weight") + ".scales", name.removesuffix(".weight") + ".biases")
    keys = native if set(header) == {"__metadata__", *native} else source
    if set(header) != {"__metadata__", *keys}:
        raise ValueError("Incomplete or unsupported packed tensor companions")
    intervals = []
    for key, dtype, itemsize in zip(keys, ("U32", "BF16", "BF16"), (4, 2, 2)):
        info = header[key]
        if not isinstance(info, dict):
            raise ValueError("Invalid tensor header")
        shape, offsets = info.get("shape"), info.get("data_offsets")
        if (info.get("dtype") != dtype or not isinstance(shape, list) or len(shape) not in (2, 3)
                or not all(_positive(dim) for dim in shape) or not isinstance(offsets, list)
                or len(offsets) != 2 or any(type(value) is not int for value in offsets)
                or offsets[0] < 0 or offsets[1] - offsets[0] != math.prod(shape) * itemsize):
            raise ValueError("Unsupported packed tensor shape, dtype, or offsets")
        intervals.append(tuple(offsets))
    cursor = 0
    for start, end in sorted(intervals):
        if start != cursor:
            raise ValueError("Overlapping or noncontiguous packed tensor data")
        cursor = end
    if cursor != size - 8 - length:
        raise ValueError("Packed tensor data length disagrees with its header")
    if header[keys[1]]["shape"] != header[keys[2]]["shape"]:
        raise ValueError("Scale and affine-bias shapes differ")
    return _Blob(path, header, length + 8, size, name, keys)


def _packed(blob: _Blob, bits: int, shape: list[int] | None = None):
    weight = blob.header[blob.keys[0]]["shape"]
    scale = blob.header[blob.keys[1]]["shape"]
    if (shape is not None and weight != shape) or weight[:-1] != scale[:-1] or weight[-1] * (32 // bits) != scale[-1] * 64:
        raise ValueError(f"Packed shape does not match {bits}-bit group-64 data: {blob.name}")
    if bits == 4 and blob.header["__metadata__"]["quant_type"] != "int4":
        raise ValueError("Expert banks must retain int4 precision")


def _fused_plan(gate: _Blob, up: _Blob, name: str) -> _Plan:
    _packed(gate, 4)
    _packed(up, 4)
    if (len(gate.header[gate.name]["shape"]) != 3 or gate.header["__metadata__"] != up.header["__metadata__"]
            or any(gate.header[g]["shape"] != up.header[u]["shape"] for g, u in zip(gate.keys, up.keys))):
        raise ValueError("Incompatible expert banks")
    header = {"__metadata__": copy.deepcopy(gate.header["__metadata__"])}
    segments, cursor = [], 0
    for gkey, ukey, suffix in zip(gate.keys, up.keys, ("", ".scale", ".bias")):
        info = copy.deepcopy(gate.header[gkey])
        shape = info["shape"]
        experts = shape[0]
        length = info["data_offsets"][1] - info["data_offsets"][0]
        slab = length // experts
        info["shape"] = [experts, shape[1] * 2, shape[2]]
        info["data_offsets"] = [cursor, cursor + length * 2]
        header[name + suffix] = info
        cursor += length * 2
        # Concatenate gate E then up E independently for all three components.
        for expert in range(experts):
            for blob, key in ((gate, gkey), (up, ukey)):
                segments.append((blob.path, blob.start + blob.header[key]["data_offsets"][0] + expert * slab, slab))
    return _Plan(name, header, segments)


def _rewrite_plan(blob: _Blob, *, name: str | None = None, quant_type: str | None = None) -> _Plan:
    target = name or blob.name
    bits = 8 if quant_type == "int8" else 4
    _packed(blob, bits)
    header = {"__metadata__": copy.deepcopy(blob.header["__metadata__"])}
    if quant_type is not None:
        if quant_type != "int8":
            raise ValueError("Only source-declared int8 metadata repair is supported")
        header["__metadata__"]["quant_type"] = quant_type
    for key, suffix in zip(blob.keys, ("", ".scale", ".bias")):
        header[target + suffix] = copy.deepcopy(blob.header[key])
    return _Plan(target, header, [(blob.path, blob.start, blob.size - blob.start)])


def _copy_range(source: BinaryIO, output: BinaryIO, offset: int, length: int, digest):
    source.seek(offset)
    while length:
        block = source.read(min(CHUNK_SIZE, length))
        if not block:
            raise ValueError("Packed source changed or was truncated during import")
        output.write(block)
        digest.update(block)
        length -= len(block)


def _write_plan(plan: _Plan, output: Path) -> dict:
    raw = json.dumps(plan.header, separators=(",", ":"), sort_keys=True).encode()
    raw += b" " * (-len(raw) % 8)
    prefix = struct.pack("<Q", len(raw)) + raw
    digest = hashlib.sha256(prefix)
    opened = {}
    created = False
    try:
        with output.open("xb") as stream:
            created = True
            stream.write(prefix)
            for path, offset, length in plan.segments:
                if path not in opened:
                    opened[path] = path.open("rb")
                _copy_range(opened[path], stream, offset, length, digest)
            stream.flush()
            os.fsync(stream.fileno())
        return {"mediaType": TENSOR_MEDIA, "digest": "sha256:" + digest.hexdigest(),
                "size": len(prefix) + sum(length for _, _, length in plan.segments), "name": plan.name}
    except BaseException:
        if created:
            output.unlink(missing_ok=True)
        raise
    finally:
        for stream in opened.values():
            stream.close()


def fuse_expert_blobs(gate: Path, up: Path, output: Path, *, name: str) -> dict:
    """Stream a fused packed bank; each expert retains gate-before-up ordering."""
    return _write_plan(_fused_plan(_inspect(gate), _inspect(up), name), output)


def rewrite_blob(source: Path, output: Path, *, name: str | None = None, quant_type: str | None = None) -> dict:
    """Rewrite only a packed blob's header, retaining its full payload verbatim."""
    return _write_plan(_rewrite_plan(_inspect(source), name=name, quant_type=quant_type), output)


def _config(root: Path, *, known_checkpoint=False) -> tuple[bytes, dict]:
    raw, config = _read_json(_inside(root, SOURCE / "config.json"))
    text = config.get("text_config", {})
    if (config.get("model_type") != "gemma4" or config.get("architectures") != ["Gemma4ForConditionalGeneration"]
            or text.get("num_hidden_layers") != 30 or text.get("num_experts") != 128
            or text.get("enable_moe_block") is not True):
        raise ValueError("Expected the 30-layer, 128-expert Gemma checkpoint")
    if any(not _positive(text.get(key)) or text[key] % 64 for key in
           ("hidden_size", "intermediate_size", "moe_intermediate_size")):
        raise ValueError("Unsupported Gemma packed dimensions")
    if known_checkpoint and hashlib.sha256(raw).hexdigest() != CONFIG_SHA256:
        raise ValueError("The CLI supports only the verified Gemma 26B checkpoint config")
    expected = {"bits": 4, "group_size": 64, "mode": "affine"}
    for layer in range(30):
        for projection in ("mlp.gate_proj", "mlp.up_proj", "mlp.down_proj", "router.proj"):
            expected[f"language_model.model.layers.{layer}.{projection}"] = {"bits": 8, "group_size": 64}
    if config.get("quantization") != expected or config.get("quantization_config") != expected:
        raise ValueError("Source quantization declarations disagree or contain unsupported overrides")
    return raw, text


def _entry_path(root: Path, entry: dict) -> Path:
    if not isinstance(entry, dict) or not re.fullmatch(r"sha256:[0-9a-f]{64}", str(entry.get("digest", ""))):
        raise ValueError("Invalid content-addressed manifest digest")
    if not _positive(entry.get("size")):
        raise ValueError("Invalid manifest blob size")
    path = _inside(root, Path("blobs") / entry["digest"].replace(":", "-"))
    if not path.is_file() or path.stat().st_size != entry["size"]:
        raise ValueError("Manifest blob is missing or has an incorrect size")
    return path


def _prepare(root: Path):
    config_raw, text = _config(root)
    target, original, manifest, link = _alias(root)
    if (manifest.get("schemaVersion") != 2 or manifest.get("runner") != "mlx"
            or manifest.get("format") != "safetensors" or not isinstance(manifest.get("layers"), list)):
        raise ValueError("Expected the native Ollama MLX safetensors manifest")
    _entry_path(root, manifest.get("config"))
    entries, paths = {}, {}
    for entry in manifest["layers"]:
        path = _entry_path(root, entry)
        name = entry.get("name")
        if name is not None:
            if (not isinstance(name, str) or not re.fullmatch(r"[A-Za-z0-9_][A-Za-z0-9_.-]*", name)
                    or ".." in name or name in entries):
                raise ValueError("Unsafe or duplicate manifest layer name")
            entries[name], paths[name] = entry, path
        elif entry.get("mediaType") == TENSOR_MEDIA:
            raise ValueError("Tensor manifest layers require names")
    config_entry = entries.get("config.json")
    if (config_entry is None or config_entry["digest"] != "sha256:" + hashlib.sha256(config_raw).hexdigest()
            or paths["config.json"].read_bytes() != config_raw):
        raise ValueError("Imported config differs from the original source checkpoint")
    _inside(root, Path("tutor-runtime/mlx"))
    hidden, dense, expert = (text[key] for key in ("hidden_size", "intermediate_size", "moe_intermediate_size"))
    old_names, new_names, replacements, skipped = set(), set(), {}, set()
    plans = []
    adapted = not any(".experts.switch_glu." in name for name in entries)

    def bank(name, shape, bits):
        if name not in entries or entries[name].get("mediaType") != TENSOR_MEDIA:
            raise ValueError(f"Missing packed manifest tensor: {name}")
        blob = _inspect(paths[name])
        if blob.name != name:
            raise ValueError("Manifest tensor name disagrees with blob header")
        _packed(blob, bits, shape)
        if _hash_file(paths[name]) != entries[name]["digest"][7:]:
            raise ValueError(f"Packed input blob digest does not match the manifest: {name}")
        return blob

    for layer in range(30):
        prefix = f"language_model.model.layers.{layer}"
        old = [prefix + f".experts.switch_glu.{projection}.weight" for projection in
               ("gate_proj", "up_proj", "down_proj")]
        fused, down = (prefix + f".experts.{projection}.weight" for projection in ("gate_up_proj", "down_proj"))
        old_names.update(old)
        new_names.update((fused, down))
        if adapted:
            bank(fused, [128, expert * 2, hidden // 8], 4)
            bank(down, [128, hidden, expert // 8], 4)
        else:
            if fused in entries or down in entries:
                raise ValueError("Mixed original and adapted expert layouts")
            gate = bank(old[0], [128, expert, hidden // 8], 4)
            up = bank(old[1], [128, expert, hidden // 8], 4)
            down_blob = bank(old[2], [128, hidden, expert // 8], 4)
            replacements[old[0]] = len(plans)
            plans.append(_fused_plan(gate, up, fused))
            skipped.add(old[1])
            replacements[old[2]] = len(plans)
            plans.append(_rewrite_plan(down_blob, name=down))
        for projection, shape in (("mlp.gate_proj", [dense, hidden // 4]),
                                  ("mlp.up_proj", [dense, hidden // 4]),
                                  ("mlp.down_proj", [hidden, dense // 4]),
                                  ("router.proj", [128, hidden // 4])):
            name = prefix + "." + projection + ".weight"
            blob = bank(name, shape, 8)
            if adapted:
                if blob.header["__metadata__"]["quant_type"] != "int8":
                    raise ValueError("Adapted experts have incomplete int8 metadata repairs")
            else:
                if blob.header["__metadata__"]["quant_type"] != "int4":
                    raise ValueError("Partially repaired metadata requires explicit inspection")
                replacements[name] = len(plans)
                plans.append(_rewrite_plan(blob, quant_type="int8"))
    actual_experts = {name for name in entries if ".experts.switch_glu." in name or name in new_names}
    if actual_experts != (new_names if adapted else old_names):
        raise ValueError("Unexpected or incomplete expert layout")
    return target, original, manifest, plans, replacements, skipped, adapted, link


def _hash_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        while block := stream.read(CHUNK_SIZE):
            digest.update(block)
    return digest.hexdigest()


def _sync_directory(path: Path):
    descriptor = os.open(path, os.O_RDONLY)
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def _atomic_file(path: Path, data: bytes, *, replace=False):
    descriptor, temporary = tempfile.mkstemp(prefix=".gemma-import-", dir=path.parent)
    temporary = Path(temporary)
    try:
        with os.fdopen(descriptor, "wb") as stream:
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
        if replace:
            os.replace(temporary, path)
        else:
            os.link(temporary, path)
        if not replace:
            _sync_directory(path.parent)
    finally:
        temporary.unlink(missing_ok=True)


def _atomic_symlink(path: Path, destination: str):
    descriptor, temporary = tempfile.mkstemp(prefix=".gemma-import-", dir=path.parent)
    os.close(descriptor)
    temporary = Path(temporary)
    try:
        temporary.unlink()
        temporary.symlink_to(destination)
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def adapt_gemma(root: Path, *, apply=False) -> dict:
    """Validate the fixed alias; default to a zero-write dry run.

    Packed dimensions are derived from the source config for testable byte-level
    transformations. All affected input blobs are SHA-verified with bounded
    reads before any write; passthrough layers retain their original entries.
    The command line additionally pins the verified 26B config.
    """
    root = Path(root).resolve(strict=True)
    target, original, manifest, plans, replacements, skipped, adapted, original_link = _prepare(root)
    result = {"status": "already-adapted" if adapted else "dry-run", "alias": str(target),
              "new_blobs": len(plans), "expert_banks": 90, "int8_overrides": 120,
              "source_config_sha256": hashlib.sha256((_inside(root, SOURCE / "config.json")).read_bytes()).hexdigest()}
    if adapted or not apply:
        return result
    backup_dir = _inside(root, Path("tutor-runtime/mlx"))
    backup = _inside(root, Path("tutor-runtime/mlx") /
                     ("gemma4-26b-tutor-mlx." + hashlib.sha256(original).hexdigest() + ".manifest.json"))
    if backup.exists() and backup.read_bytes() != original:
        raise ValueError("Existing manifest backup differs from the original alias")
    backup_link, link_record = None, None
    if original_link is not None:
        backup_link = _inside(root, backup.relative_to(root).with_suffix(".link.json"))
        link_record = json.dumps({"alias": str(ALIAS), "target": original_link,
                                  "manifest_digest": "sha256:" + hashlib.sha256(original).hexdigest()},
                                 sort_keys=True).encode()
        if backup_link.exists() and backup_link.read_bytes() != link_record:
            raise ValueError("Existing alias backup differs from the original link")
    created, temporary, descriptors = [], [], []
    committed, publishing, publication_raw, publication_link = False, False, None, None
    try:
        # Build every blob before publishing any manifest. Never overwrite a blob.
        for plan in plans:
            handle, path = tempfile.mkstemp(prefix=".gemma-import-", dir=root / "blobs")
            os.close(handle)
            path = Path(path)
            path.unlink()
            temporary.append(path)
            entry = _write_plan(plan, path)
            destination = _inside(root, Path("blobs") / entry["digest"].replace(":", "-"))
            if destination.exists():
                if destination.stat().st_size != entry["size"] or _hash_file(destination) != entry["digest"][7:]:
                    raise ValueError("Existing content-addressed output blob is corrupt")
            else:
                os.link(path, destination)
                created.append(destination)
            path.unlink()
            descriptors.append(entry)
        _sync_directory(root / "blobs")
        _check_alias(root, original, original_link)
        updated = copy.deepcopy(manifest)
        updated["layers"] = [dict(entry, **descriptors[replacements[entry.get("name")]])
                             if entry.get("name") in replacements else entry
                             for entry in manifest["layers"] if entry.get("name") not in skipped]
        backup_dir.mkdir(parents=True, exist_ok=True)
        if not backup.exists():
            _atomic_file(backup, original)
        if backup_link is not None and not backup_link.exists():
            _atomic_file(backup_link, link_record)
        publication_raw = json.dumps(updated, separators=(",", ":")).encode()
        if original_link is not None:
            digest = hashlib.sha256(publication_raw).hexdigest()
            manifest_blob = _inside(root, Path("blobs") / ("sha256-" + digest))
            if manifest_blob.exists():
                if manifest_blob.read_bytes() != publication_raw:
                    raise ValueError("Existing content-addressed manifest blob is corrupt")
            else:
                _atomic_file(manifest_blob, publication_raw)
                created.append(manifest_blob)
            publication_link = os.path.relpath(manifest_blob, target.parent)
        _check_alias(root, original, original_link)
        publishing = True
        if original_link is None:
            _atomic_file(target, publication_raw, replace=True)
        else:
            _atomic_symlink(target, publication_link)
        # After rename, these blobs are live even if directory fsync fails.
        committed = True
        _sync_directory(target.parent)
        result.update(status="applied", backup=str(backup))
        if backup_link is not None:
            result.update(backup_link=str(backup_link), manifest_blob=str(manifest_blob))
        return result
    finally:
        if publishing and not committed:
            # A rename may commit and then raise before returning to this caller.
            # Inspect the published state; retain blobs whenever it is uncertain.
            try:
                current_link = os.readlink(target) if target.is_symlink() else None
                committed = current_link == publication_link and target.read_bytes() == publication_raw
            except BaseException:
                committed = True
        for path in temporary:
            path.unlink(missing_ok=True)
        if not committed:
            for path in created:
                path.unlink(missing_ok=True)


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=ROOT, help="SSD LocalAI root")
    parser.add_argument("--apply", action="store_true", help="write new blobs and atomically replace only the tutor alias")
    options = parser.parse_args(argv)
    try:
        root = options.root.resolve(strict=True)
        _config(root, known_checkpoint=True)
        result = adapt_gemma(root, apply=options.apply)
    except (OSError, ValueError, KeyError, TypeError) as exc:
        print(f"Gemma import adaptation failed: {exc}", file=sys.stderr)
        return 1
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
