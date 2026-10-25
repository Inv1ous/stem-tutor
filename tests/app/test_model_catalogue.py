"""Small STEM model choices remain manifest-backed and declare their actual input capabilities."""
from tutor_app import config, local_models

NEW = ('ollama:qwen3.5:2b', 'ollama:qwen3.5:4b', 'ollama:gemma4:e2b', 'ollama:gemma4:e4b',
       'ollama:ministral-3:3b', 'ollama:phi4-mini:3.8b')


def test_small_models_have_routing_residency_and_capability_metadata():
    for model in NEW:
        assert model in local_models.LOCAL_MODELS and model in config.AI_MODELS
        assert local_models.KEEP_ALIVE[model]
    assert not local_models.supports_vision(NEW[-1])
    assert all(local_models.supports_vision(model) for model in NEW[:-1])
    assert not local_models.supports_thinking(NEW[-1])
    assert not local_models.supports_thinking('ollama:ministral-3:3b')
    assert local_models.supports_thinking('ollama:qwen3.5:4b')


def test_installed_manifest_is_required_for_new_choices(tmp_path, monkeypatch):
    monkeypatch.setattr(local_models, 'ROOT', tmp_path)
    model = NEW[0]
    assert model not in local_models.available_models()
    path = tmp_path / 'manifests/registry.ollama.ai/library/qwen3.5/2b'
    path.parent.mkdir(parents=True)
    path.write_text('{"schemaVersion":2}')
    assert local_models.available_models() == (model,)


def test_vision_helper_setting_loads_known_vision_choices_only(tmp_path):
    import json
    folder = tmp_path / '.tutor'
    folder.mkdir()
    for value, expected in [('ollama:qwen3.5:4b', 'ollama:qwen3.5:4b'),
                            ('macos:vision', 'macos:vision'),
                            ('ollama:phi4-mini:3.8b', 'macos:vision'),
                            ('unknown', 'macos:vision')]:
        (folder / 'app_settings.json').write_text(json.dumps({'local_vision_model': value}))
        assert config.Settings.load(tmp_path).local_vision_model == expected


def test_gpt_oss_is_local_text_only_and_maps_the_thinking_switch_to_supported_levels():
    model='ollama:gpt-oss:20b'
    assert model in local_models.LOCAL_MODELS
    assert not local_models.supports_vision(model)
    assert local_models.thinking_value(model, False) == 'low'
    assert local_models.thinking_value(model, True) == 'high'
    assert local_models.thinking_value('ollama:qwen3.5:4b', False) is False
    assert local_models.thinking_value('ollama:phi4-mini:3.8b', False) is None


def test_smaller_deepseek_distills_and_llama_are_text_only_with_verified_controls():
    models = ('ollama:deepseek-r1:8b', 'ollama:deepseek-r1:14b', 'ollama:llama3.1:8b')
    for model in models:
        assert model in local_models.LOCAL_MODELS and model in config.AI_MODELS
        assert not local_models.supports_vision(model)
        assert local_models.KEEP_ALIVE[model] == '45m'
        assert local_models.CONTEXT_LENGTH[model] == 8192
    for model in models[:2]:
        assert local_models.always_thinks(model)
        assert local_models.thinking_value(model, True) is True
        assert local_models.thinking_value(model, False) is True
    assert local_models.thinking_value(models[-1], False) is None
    assert not local_models.supports_thinking(models[-1])


def test_registered_community_model_uses_its_own_manifest_namespace(tmp_path, monkeypatch):
    monkeypatch.setattr(local_models, 'ROOT', tmp_path)
    model = 'ollama:example/stem-model:4b'
    monkeypatch.setitem(local_models.LOCAL_MODELS, model, 'Community fixture')
    path = tmp_path / 'manifests/registry.ollama.ai/example/stem-model/4b'
    path.parent.mkdir(parents=True)
    path.write_text('{"schemaVersion":2}')
    assert local_models.available_models() == (model,)
    path.unlink()
    assert local_models.available_models() == ()


def test_liquid_always_uses_verified_reasoning_mode_and_local_ocr():
    model = 'ollama:lfm2.5:8b'
    assert model in config.AI_MODELS and not local_models.supports_vision(model)
    assert local_models.always_thinks(model)
    assert local_models.thinking_value(model, False) is True
    assert local_models.thinking_value(model, True) is True
    assert not local_models.always_thinks('ollama:gemma4:26b-a4b-it-qat')
    assert not local_models.always_thinks('haiku')


def test_community_mimo_has_verified_native_image_and_boolean_thinking_support():
    model = 'ollama:maternion/mimo-v2.6:9b-instruct-q4_K_M'
    assert model in config.AI_MODELS and local_models.supports_vision(model)
    assert 'community' in local_models.LOCAL_MODELS[model].lower()
    assert local_models.thinking_value(model, False) is False
    assert local_models.thinking_value(model, True) is True
    assert not local_models.always_thinks(model)
    assert local_models.KEEP_ALIVE[model] == '45m' and local_models.CONTEXT_LENGTH[model] == 8192
