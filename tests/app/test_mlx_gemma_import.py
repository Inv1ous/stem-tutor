"""Lossless native Gemma import repair, exercised only in temporary directories."""
import copy
import hashlib
import importlib
import json
import math
from pathlib import Path
import struct

import pytest


ALIAS = Path("manifests-v2/ollama.com/library/gemma4/26b-tutor-mlx")
SOURCE = Path("LMStudioModels/lmstudio-community/gemma-4-26B-A4B-it-QAT-MLX-4bit")
P = "language_model.model.layers.0"


def adapter():
    # Missing implementation is an ordinary assertion during the first RED run.
    spec = importlib.util.find_spec("tutor_app.mlx_gemma_import")
    assert spec is not None, "Gemma's packed expert import adapter is missing"
    return importlib.import_module("tutor_app.mlx_gemma_import")


def pack(path, name, shape, *, tag=1, quant_type="int4", source_suffixes=False):
    """Create actual safetensors with distinct expert slabs and companion bytes."""
    path.parent.mkdir(parents=True, exist_ok=True)
    scale_shape = [*shape[:-1], shape[-1] // (8 if quant_type == "int4" else 16)]
    tensors = [(name, "U32", shape, 4, tag),
               (name.removesuffix(".weight") + ".scales" if source_suffixes else name + ".scale",
                "BF16", scale_shape, 2, tag + 20),
               (name.removesuffix(".weight") + ".biases" if source_suffixes else name + ".bias",
                "BF16", scale_shape, 2, tag + 40)]
    header = {"__metadata__": {"quant_type": "int4", "group_size": "64"}}
    payload = bytearray()
    parts = {}
    for key, dtype, dims, itemsize, marker in tensors:
        slab = math.prod(dims[1:]) * itemsize if len(dims) == 3 else math.prod(dims) * itemsize
        data = b"".join(bytes([(marker + expert) % 256]) * slab
                        for expert in range(dims[0] if len(dims) == 3 else 1))
        header[key] = {"dtype": dtype, "shape": dims, "data_offsets": [len(payload), len(payload) + len(data)]}
        parts[key] = data
        payload.extend(data)
    save(path, header, payload)
    return header, parts


def save(path, header, payload):
    raw = json.dumps(header, separators=(",", ":")).encode()
    raw += b" " * (-len(raw) % 8)
    path.write_bytes(struct.pack("<Q", len(raw)) + raw + payload)


def unpack(path):
    raw = path.read_bytes()
    length = struct.unpack("<Q", raw[:8])[0]
    header, data = json.loads(raw[8:8 + length]), raw[8 + length:]
    return header, {name: data[info["data_offsets"][0]:info["data_offsets"][1]]
                    for name, info in header.items() if name != "__metadata__"}, data


def descriptor(path, name=None, media="application/vnd.ollama.image.tensor"):
    data = path.read_bytes()
    result = {"mediaType": media, "digest": "sha256:" + hashlib.sha256(data).hexdigest(), "size": len(data)}
    if name is not None:
        result["name"] = name
    return result


def install_blob(root, path, name=None, media="application/vnd.ollama.image.tensor"):
    entry = descriptor(path, name, media)
    destination = root / "blobs" / entry["digest"].replace(":", "-")
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_bytes(path.read_bytes())
    return entry


def snapshot(root):
    return {str(path.relative_to(root)): hashlib.sha256(path.read_bytes()).hexdigest()
            for path in root.rglob("*") if path.is_file()}


@pytest.mark.parametrize("source_suffixes", [False, True])
def test_fusion_interleaves_each_experts_packed_weight_scale_and_bias(tmp_path, source_suffixes):
    # Concatenating whole gate/up banks mixes experts; only expert-wise fusion is valid.
    mod = adapter()
    gate, up, output = (tmp_path / name for name in ("gate", "up", "fused"))
    pack(gate, P + ".experts.switch_glu.gate_proj.weight", [2, 2, 8], tag=1,
         source_suffixes=source_suffixes)
    pack(up, P + ".experts.switch_glu.up_proj.weight", [2, 2, 8], tag=7,
         source_suffixes=source_suffixes)
    original = snapshot(tmp_path)
    name = P + ".experts.gate_up_proj.weight"
    result = mod.fuse_expert_blobs(gate, up, output, name=name)
    header, parts, _ = unpack(output)
    assert header[name]["shape"] == [2, 4, 8]
    assert header[name + ".scale"]["shape"] == [2, 4, 1]
    assert header[name + ".bias"]["shape"] == [2, 4, 1]
    assert parts[name] == b"\x01" * 64 + b"\x07" * 64 + b"\x02" * 64 + b"\x08" * 64
    assert parts[name + ".scale"] == b"\x15" * 4 + b"\x1b" * 4 + b"\x16" * 4 + b"\x1c" * 4
    assert parts[name + ".bias"] == b"\x29" * 4 + b"\x2f" * 4 + b"\x2a" * 4 + b"\x30" * 4
    assert header["__metadata__"] == {"quant_type": "int4", "group_size": "64"}
    assert result == descriptor(output, name)
    assert {key: value for key, value in snapshot(tmp_path).items() if key != "fused"} == original


def test_down_projection_renames_headers_without_changing_any_payload_byte(tmp_path):
    mod = adapter()
    source, output = tmp_path / "down", tmp_path / "renamed"
    old = P + ".experts.switch_glu.down_proj.weight"
    pack(source, old, [2, 64, 8])
    before = unpack(source)
    name = P + ".experts.down_proj.weight"
    result = mod.rewrite_blob(source, output, name=name)
    header, parts, payload = unpack(output)
    assert set(parts) == {name, name + ".scale", name + ".bias"}
    assert payload == before[2]
    for suffix in ("", ".scale", ".bias"):
        assert header[name + suffix] == before[0][old + suffix]
    assert result == descriptor(output, name)


def test_int8_metadata_repair_preserves_tensor_headers_and_payload(tmp_path):
    # Runtime metadata wins over shape inference; leaving int4 loads wrong precision.
    mod = adapter()
    source, output = tmp_path / "dense", tmp_path / "int8"
    name = P + ".mlp.gate_proj.weight"
    pack(source, name, [3, 16], quant_type="int8")
    before = unpack(source)
    result = mod.rewrite_blob(source, output, quant_type="int8")
    header, _, payload = unpack(output)
    assert header.pop("__metadata__") == {"quant_type": "int8", "group_size": "64"}
    assert header == {key: value for key, value in before[0].items() if key != "__metadata__"}
    assert payload == before[2]
    assert result == descriptor(output, name)


@pytest.fixture
def installation(tmp_path):
    root = tmp_path / "ssd"
    source = root / SOURCE
    source.mkdir(parents=True)
    quant = {"bits": 4, "group_size": 64, "mode": "affine"}
    for layer in range(30):
        for projection in ("mlp.gate_proj", "mlp.up_proj", "mlp.down_proj", "router.proj"):
            quant[f"language_model.model.layers.{layer}.{projection}"] = {"bits": 8, "group_size": 64}
    config = {"model_type": "gemma4", "architectures": ["Gemma4ForConditionalGeneration"],
              "text_config": {"num_hidden_layers": 30, "num_experts": 128, "hidden_size": 64,
                              "intermediate_size": 64, "moe_intermediate_size": 64, "enable_moe_block": True},
              "quantization": quant, "quantization_config": copy.deepcopy(quant)}
    (source / "config.json").write_text(json.dumps(config))
    (source / "unchanged.safetensors").write_bytes(b"original checkpoint")
    work = tmp_path / "tensor"
    layers = []
    for layer in range(30):
        prefix = f"language_model.model.layers.{layer}"
        for projection, tag in (("gate_proj", 1), ("up_proj", 7), ("down_proj", 11)):
            name = prefix + f".experts.switch_glu.{projection}.weight"
            pack(work, name, [128, 64, 8], tag=tag)
            layers.append(install_blob(root, work, name))
        for projection in ("mlp.gate_proj", "mlp.up_proj", "mlp.down_proj", "router.proj"):
            name = prefix + "." + projection + ".weight"
            pack(work, name, [128 if projection == "router.proj" else 64, 16], quant_type="int8")
            layers.append(install_blob(root, work, name))
    layers.append(install_blob(root, source / "config.json", "config.json", "application/vnd.ollama.image.json"))
    work.write_bytes(b"unchanged config")
    config_entry = install_blob(root, work, media="application/vnd.docker.container.image.v1+json")
    work.write_bytes(b"unchanged tokenizer")
    layers.append(install_blob(root, work, "tokenizer.json", "application/vnd.ollama.image.json"))
    manifest = {"schemaVersion": 2, "mediaType": "application/vnd.docker.distribution.manifest.v2+json",
                "runner": "mlx", "format": "safetensors", "config": config_entry, "layers": layers}
    target = root / ALIAS
    target.parent.mkdir(parents=True)
    target.write_text(json.dumps(manifest))
    (target.parent / "original").write_bytes(target.read_bytes())
    return root, target, manifest


def test_dry_run_validates_complete_plan_without_creating_any_output(installation):
    mod = adapter()
    root, target, _ = installation
    before = snapshot(root)
    result = mod.adapt_gemma(root)
    assert result["status"] == "dry-run"
    assert result["new_blobs"] == 180
    assert result["expert_banks"] == 90
    assert result["int8_overrides"] == 120
    assert snapshot(root) == before


def test_apply_changes_only_fixed_alias_after_blobs_and_preserves_originals(installation):
    mod = adapter()
    root, target, original = installation
    before = snapshot(root)
    old_manifest = target.read_bytes()
    result = mod.adapt_gemma(root, apply=True)
    updated = json.loads(target.read_text())
    assert result["status"] == "applied"
    assert updated["config"] == original["config"]
    assert len(updated["layers"]) == len(original["layers"]) - 30
    entries = {entry.get("name"): entry for entry in updated["layers"]}
    assert not any("switch_glu" in str(entry) for entry in updated["layers"])
    for layer in range(30):
        prefix = f"language_model.model.layers.{layer}"
        for suffix in ("experts.gate_up_proj.weight", "experts.down_proj.weight", "mlp.gate_proj.weight",
                       "mlp.up_proj.weight", "mlp.down_proj.weight", "router.proj.weight"):
            entry = entries[prefix + "." + suffix]
            path = root / "blobs" / entry["digest"].replace(":", "-")
            assert descriptor(path, entry["name"]) == entry
            header = unpack(path)[0]
            assert entry["name"] in header
            assert header["__metadata__"]["quant_type"] == ("int4" if suffix.startswith("experts") else "int8")
    for entry in original["layers"][-2:]:
        assert entries[entry["name"]] == entry
    after = snapshot(root)
    assert all(after[name] == value for name, value in before.items() if name != str(ALIAS))
    backups = list((root / "tutor-runtime/mlx").glob("*.manifest.json"))
    assert len(backups) == 1 and backups[0].read_bytes() == old_manifest
    result = mod.adapt_gemma(root, apply=True)
    assert result["status"] == "already-adapted"
    assert snapshot(root) == after


@pytest.mark.parametrize("broken", ["digest", "name", "duplicate", "shape", "metadata", "config", "symlink"])
def test_validation_failure_creates_no_files_or_directories(installation, tmp_path, broken):
    mod = adapter()
    root, target, manifest = installation
    if broken == "digest":
        manifest["layers"][0]["digest"] = "sha256:../../outside"
    elif broken == "name":
        manifest["layers"][-1]["name"] = "../outside.json"
    elif broken == "duplicate":
        manifest["layers"].append(manifest["layers"][0])
    elif broken in ("shape", "metadata"):
        entry = manifest["layers"][0]
        path = root / "blobs" / entry["digest"].replace(":", "-")
        header, _, payload = unpack(path)
        if broken == "shape":
            header[entry["name"]]["shape"][-1] = 7
        else:
            header["__metadata__"]["quant_type"] = "nvfp4"
        save(path, header, payload)
        entry["size"] = path.stat().st_size
    elif broken == "config":
        path = root / SOURCE / "config.json"
        config = json.loads(path.read_text())
        config["quantization_config"]["bits"] = 8
        path.write_text(json.dumps(config))
    else:
        outside = tmp_path / "outside"
        outside.mkdir()
        (root / "tutor-runtime").symlink_to(outside, target_is_directory=True)
    target.write_text(json.dumps(manifest))
    before = snapshot(root)
    dirs = {str(path.relative_to(root)) for path in root.rglob("*") if path.is_dir()}
    with pytest.raises(ValueError):
        mod.adapt_gemma(root, apply=True)
    assert snapshot(root) == before
    assert {str(path.relative_to(root)) for path in root.rglob("*") if path.is_dir()} == dirs


def test_blob_write_failure_never_replaces_alias_or_retains_partial_blobs(installation, monkeypatch):
    mod = adapter()
    root, target, _ = installation
    before = snapshot(root)
    original = mod._copy_range
    calls = 0

    def fail_copy(*args, **kwargs):
        nonlocal calls
        calls += 1
        if calls == 4:
            raise OSError("injected disk failure")
        return original(*args, **kwargs)

    monkeypatch.setattr(mod, "_copy_range", fail_copy)
    with pytest.raises(OSError, match="injected disk failure"):
        mod.adapt_gemma(root, apply=True)
    assert snapshot(root) == before


def test_fusion_rejects_incompatible_or_overlapping_banks_before_output(tmp_path):
    mod = adapter()
    gate, up, output = (tmp_path / name for name in ("gate", "up", "fused"))
    pack(gate, P + ".experts.switch_glu.gate_proj.weight", [2, 2, 8])
    pack(up, P + ".experts.switch_glu.up_proj.weight", [3, 2, 8])
    with pytest.raises(ValueError):
        mod.fuse_expert_blobs(gate, up, output, name=P + ".experts.gate_up_proj.weight")
    assert not output.exists()
    header, _, payload = unpack(gate)
    header[P + ".experts.switch_glu.gate_proj.weight.scale"]["data_offsets"] = [0, 8]
    save(gate, header, payload)
    with pytest.raises(ValueError):
        mod.fuse_expert_blobs(gate, gate, output, name=P + ".experts.gate_up_proj.weight")
    assert not output.exists()


def test_copy_remains_bounded_and_copies_only_the_selected_range(tmp_path, monkeypatch):
    # A read of an entire checkpoint would fail this guard before allocating it.
    import io
    mod = adapter()
    monkeypatch.setattr(mod, "CHUNK_SIZE", 7)

    class BoundedInput(io.BytesIO):
        def read(self, size=-1):
            if size < 0 or size > 7:
                raise AssertionError("unbounded packed-weight read")
            return super().read(size)

    source = BoundedInput(b"prefix" + bytes(range(40)) + b"suffix")
    output, digest = io.BytesIO(), hashlib.sha256()
    mod._copy_range(source, output, 6, 40, digest)
    assert output.getvalue() == bytes(range(40))
    assert digest.hexdigest() == hashlib.sha256(bytes(range(40))).hexdigest()


def test_manifest_sync_failure_after_replace_keeps_all_referenced_blobs(installation, monkeypatch):
    mod = adapter()
    root, target, _ = installation
    original = mod._sync_directory

    def fail_manifest_sync(path):
        if path == target.parent:
            raise OSError("manifest directory sync failed")
        original(path)

    monkeypatch.setattr(mod, "_sync_directory", fail_manifest_sync)
    with pytest.raises(OSError, match="manifest directory sync failed"):
        mod.adapt_gemma(root, apply=True)
    manifest = json.loads(target.read_text())
    for entry in manifest["layers"]:
        path = root / "blobs" / entry["digest"].replace(":", "-")
        assert path.is_file(), "published manifest must never reference a deleted output blob"
        assert path.stat().st_size == entry["size"]


def test_cli_rejects_unverified_checkpoint_without_any_output(installation, capsys):
    mod = adapter()
    root, _, _ = installation
    before = snapshot(root)
    assert mod.main(["--root", str(root), "--apply"]) == 1
    assert "verified Gemma 26B checkpoint" in capsys.readouterr().err
    assert snapshot(root) == before


def test_manifest_replace_failure_preserves_alias_and_rollback_backup(installation, monkeypatch):
    mod = adapter()
    root, target, _ = installation
    before = snapshot(root)
    original_bytes = target.read_bytes()
    original_replace = mod.os.replace

    def fail_replace(source, destination):
        if destination == target:
            raise OSError("injected manifest replace failure")
        return original_replace(source, destination)

    monkeypatch.setattr(mod.os, "replace", fail_replace)
    with pytest.raises(OSError, match="injected manifest replace failure"):
        mod.adapt_gemma(root, apply=True)
    after = snapshot(root)
    assert all(after[name] == value for name, value in before.items())
    assert set(after) - set(before) == {str(path.relative_to(root)) for path in
                                      (root / "tutor-runtime/mlx").glob("*.manifest.json")}
    assert next((root / "tutor-runtime/mlx").glob("*.manifest.json")).read_bytes() == original_bytes
    assert not list(root.rglob(".gemma-import-*"))


def test_unsupported_per_tensor_quant_override_is_rejected_before_any_output(tmp_path):
    mod = adapter()
    source, output = tmp_path / "dense", tmp_path / "int8"
    name = P + ".mlp.gate_proj.weight"
    pack(source, name, [3, 16], quant_type="int8")
    header, _, payload = unpack(source)
    header["__metadata__"][name + ".quant_type"] = "int4"
    save(source, header, payload)
    with pytest.raises(ValueError):
        mod.rewrite_blob(source, output, quant_type="int8")
    assert not output.exists()


@pytest.fixture
def native_installation(installation):
    """Ollama v2 aliases are relative links to immutable manifest blobs."""
    root, target, manifest = installation
    raw = target.read_bytes()
    manifest_blob = root / "blobs" / ("sha256-" + hashlib.sha256(raw).hexdigest())
    manifest_blob.write_bytes(raw)
    target.unlink()
    relative = "../../../../blobs/" + manifest_blob.name
    target.symlink_to(relative)
    other = target.parent / "original"
    other.unlink()
    other.symlink_to(relative)
    return root, target, manifest, manifest_blob, relative


def test_native_alias_dry_run_and_apply_publish_immutable_manifest_blob(native_installation):
    import os
    mod = adapter()
    root, target, original, old_blob, old_link = native_installation
    before = snapshot(root)
    original_bytes = old_blob.read_bytes()
    assert mod.adapt_gemma(root)["status"] == "dry-run"
    assert snapshot(root) == before
    assert os.readlink(target) == old_link
    result = mod.adapt_gemma(root, apply=True)
    assert result["status"] == "applied"
    assert target.is_symlink()
    new_blob = target.resolve()
    assert new_blob.parent == root / "blobs"
    assert new_blob.name == "sha256-" + hashlib.sha256(new_blob.read_bytes()).hexdigest()
    assert new_blob != old_blob
    assert len(json.loads(new_blob.read_bytes())["layers"]) == len(original["layers"]) - 30
    assert old_blob.read_bytes() == original_bytes
    assert os.readlink(target.parent / "original") == old_link
    assert (target.parent / "original").read_bytes() == original_bytes
    assert Path(result["backup"]).read_bytes() == original_bytes
    backup_link = json.loads(Path(result["backup_link"]).read_text())
    assert backup_link == {"alias": str(ALIAS), "target": old_link,
                           "manifest_digest": "sha256:" + hashlib.sha256(original_bytes).hexdigest()}
    after, after_link = snapshot(root), os.readlink(target)
    assert mod.adapt_gemma(root, apply=True)["status"] == "already-adapted"
    assert snapshot(root) == after and os.readlink(target) == after_link


@pytest.mark.parametrize("bad_link", ["outside", "not_digest", "wrong_hash", "blob_symlink"])
def test_native_alias_rejects_unverified_or_outside_manifest_links(native_installation, tmp_path, bad_link):
    mod = adapter()
    root, target, _, old_blob, _ = native_installation
    raw = old_blob.read_bytes()
    if bad_link == "outside":
        destination = tmp_path / old_blob.name
        destination.write_bytes(raw)
    elif bad_link == "not_digest":
        destination = root / "blobs/not-a-digest"
        destination.write_bytes(raw)
    elif bad_link == "wrong_hash":
        destination = root / "blobs" / ("sha256-" + "0" * 64)
        destination.write_bytes(raw)
    else:
        destination = root / "blobs" / ("sha256-" + "1" * 64)
        destination.symlink_to(old_blob)
    target.unlink()
    target.symlink_to(destination)
    before = snapshot(root)
    with pytest.raises(ValueError):
        mod.adapt_gemma(root, apply=True)
    assert snapshot(root) == before


def test_native_alias_retargeted_during_copy_is_never_replaced(native_installation, monkeypatch):
    import os
    mod = adapter()
    root, target, _, old_blob, _ = native_installation
    before = snapshot(root)
    original_copy = mod._copy_range
    changed = False

    def retarget_alias(*args, **kwargs):
        nonlocal changed
        if not changed:
            target.unlink()
            target.symlink_to(old_blob)  # Same bytes, different link identity.
            changed = True
        return original_copy(*args, **kwargs)

    monkeypatch.setattr(mod, "_copy_range", retarget_alias)
    with pytest.raises(ValueError, match="alias changed"):
        mod.adapt_gemma(root, apply=True)
    assert snapshot(root) == before
    assert os.readlink(target) == str(old_blob)


def test_native_alias_replace_failure_preserves_shared_manifest(native_installation, monkeypatch):
    import os
    mod = adapter()
    root, target, _, old_blob, old_link = native_installation
    before = snapshot(root)
    original_replace = mod.os.replace

    def fail_replace(source, destination):
        if destination == target:
            raise OSError("native alias replace failed")
        return original_replace(source, destination)

    monkeypatch.setattr(mod.os, "replace", fail_replace)
    with pytest.raises(OSError, match="native alias replace failed"):
        mod.adapt_gemma(root, apply=True)
    after = snapshot(root)
    assert all(after[name] == value for name, value in before.items())
    assert os.readlink(target) == old_link
    assert old_blob.read_bytes() == target.read_bytes()
    assert all(name.startswith("tutor-runtime/mlx/") for name in set(after) - set(before))
    assert not list(root.rglob(".gemma-import-*"))


def test_same_size_source_payload_corruption_is_rejected_before_any_write(installation):
    mod = adapter()
    root, target, manifest = installation
    entry = manifest["layers"][0]
    path = root / "blobs" / entry["digest"].replace(":", "-")
    raw = bytearray(path.read_bytes())
    raw[-1] ^= 1
    path.write_bytes(raw)
    before = snapshot(root)
    with pytest.raises(ValueError, match="digest"):
        mod.adapt_gemma(root, apply=True)
    assert snapshot(root) == before
    assert not (root / "tutor-runtime").exists()


@pytest.mark.parametrize("failure", [OSError, KeyboardInterrupt])
def test_exception_immediately_after_native_alias_publish_keeps_live_blobs(native_installation, monkeypatch, failure):
    mod = adapter()
    root, target, _, _, _ = native_installation
    # Replace itself is real; the wrapper simulates failure before the caller regains control.
    original_replace = mod.os.replace

    def replace_then_raise(source, destination):
        result = original_replace(source, destination)
        if destination == target:
            raise failure("failure immediately after native alias publication")
        return result

    monkeypatch.setattr(mod.os, "replace", replace_then_raise)
    with pytest.raises(failure, match="immediately after native alias publication"):
        mod.adapt_gemma(root, apply=True)
    assert target.is_symlink()
    published = json.loads(target.read_bytes())
    for entry in published["layers"]:
        path = root / "blobs" / entry["digest"].replace(":", "-")
        assert path.is_file(), "published alias must retain its new weight blobs after an interrupted return"
        assert path.stat().st_size == entry["size"]
