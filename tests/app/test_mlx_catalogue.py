"""An SSD installation is offered only after its complete receipt is verified."""
import json

import pytest

from tutor_app import config, local_models


GPT = "mlx:gpt-oss:20b"
GEMMA = "ollama:gemma4:26b-tutor-mlx"
REVISION = "6cee5e81ee83917806bbde320786a8fb61efebee"


@pytest.fixture
def installation(tmp_path, monkeypatch):
    checkpoint = tmp_path / "models/openai/gpt-oss-20b"
    runtime = tmp_path / "tutor-runtime/mlx/.venv/bin/python"
    receipt = tmp_path / "tutor-runtime/mlx/gpt-oss-20b.json"
    monkeypatch.setattr(local_models, "ROOT", tmp_path)
    monkeypatch.setattr(local_models, "MLX_CHECKPOINT", checkpoint, raising=False)
    monkeypatch.setattr(local_models, "MLX_PYTHON", runtime, raising=False)
    monkeypatch.setattr(local_models, "MLX_RECEIPT", receipt, raising=False)
    checkpoint.mkdir(parents=True)
    runtime.parent.mkdir(parents=True)
    runtime.write_text("isolated runtime")
    files = {"config.json": "{}", "tokenizer.json": "{}", "tokenizer_config.json": "{}",
             "model.safetensors.index.json": json.dumps({"weight_map": {"layer": "model-00001-of-00001.safetensors"}}),
             "model-00001-of-00001.safetensors": "verified weights"}
    for name, content in files.items():
        (checkpoint / name).write_text(content)
    data = {"revision": REVISION, "files": {name: len(value.encode()) for name, value in files.items()},
            "runtime": {"mlx": "0.32.2", "mlx-lm": "0.32.2", "outlines": "1.3.3", "llguidance": "1.9.1"}}
    receipt.write_text(json.dumps(data))
    return checkpoint, runtime, receipt, data


def test_verified_mlx_installations_appear_and_keep_capabilities(installation):
    checkpoint, _, receipt, _ = installation
    assert GPT in local_models.available_models()
    assert GPT in config.AI_MODELS and GEMMA in config.AI_MODELS
    assert not local_models.supports_vision(GPT) and local_models.supports_vision(GEMMA)
    assert local_models.KEEP_ALIVE[GEMMA] == "15m"
    assert local_models.CONTEXT_LENGTH[GPT] == 8192
    receipt.unlink()
    assert GPT not in local_models.available_models()


@pytest.mark.parametrize("broken", ["runtime", "revision", "config", "tokenizer", "index", "shard", "size",
                                    "unsafe_receipt", "unsafe_index", "runtime_metadata"])
def test_partial_or_unsafe_mlx_installation_is_hidden(installation, broken):
    checkpoint, runtime, receipt, data = installation
    if broken == "runtime":
        runtime.unlink()
    elif broken == "revision":
        data["revision"] = "another revision"
    elif broken in ("config", "tokenizer", "index", "shard"):
        name = {"config": "config.json", "tokenizer": "tokenizer.json", "index": "model.safetensors.index.json",
                "shard": "model-00001-of-00001.safetensors"}[broken]
        (checkpoint / name).unlink()
    elif broken == "size":
        (checkpoint / "config.json").write_text("changed")
    elif broken == "unsafe_receipt":
        data["files"]["../outside.safetensors"] = 1
    elif broken == "unsafe_index":
        path = checkpoint / "model.safetensors.index.json"
        path.write_text(json.dumps({"weight_map": {"layer": "../outside.safetensors"}}))
        data["files"][path.name] = path.stat().st_size
    else:
        data["runtime"].pop("mlx-lm")
    receipt.write_text(json.dumps(data))
    assert GPT not in local_models.available_models()


def test_original_models_and_native_gemma_have_independent_manifest_choices(installation):
    checkpoint, _, _, _ = installation
    registry = checkpoint.parents[2] / "manifests/registry.ollama.ai/library"
    for folder, tag in (("gemma4", "26b-a4b-it-qat"), ("gemma4", "26b-tutor-mlx"), ("gpt-oss", "20b")):
        path = registry / folder / tag
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("{}")
    assert {GPT, GEMMA, "ollama:gpt-oss:20b", "ollama:gemma4:26b-a4b-it-qat"} <= set(local_models.available_models())


def test_native_v2_manifest_hotplug_keeps_original_legacy_choice(tmp_path, monkeypatch):
    monkeypatch.setattr(local_models, "ROOT", tmp_path)
    legacy = tmp_path / "manifests/registry.ollama.ai/library/gemma4/26b-a4b-it-qat"
    native = tmp_path / "manifests-v2/ollama.com/library/gemma4/26b-tutor-mlx"
    legacy.parent.mkdir(parents=True)
    legacy.write_text("{}")
    assert local_models.available_models() == ("ollama:gemma4:26b-a4b-it-qat",)
    native.parent.mkdir(parents=True)
    native.write_text("{}")
    assert local_models.available_models() == ("ollama:gemma4:26b-a4b-it-qat", GEMMA)
    native.unlink()
    assert local_models.available_models() == ("ollama:gemma4:26b-a4b-it-qat",)
