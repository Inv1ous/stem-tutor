"""A damaged numeric setting must not prevent the rest of the app settings loading."""
import json

import pytest

from tutor_app.config import Settings


@pytest.mark.parametrize("field", ["tts_speed", "tts_volume", "font_zoom_cell"])
@pytest.mark.parametrize("sign", [-1, 1])
def test_unrepresentable_integer_setting_falls_back_without_rewriting_saved_settings(tmp_path, field, sign):
    settings_file = tmp_path / ".tutor" / "app_settings.json"
    settings_file.parent.mkdir()
    original = json.dumps({field: sign * 10**400, "ai": False, "minutes": 55}).encode()
    settings_file.write_bytes(original)

    loaded = Settings.load(tmp_path)

    assert getattr(loaded, field) == getattr(Settings(), field)
    assert loaded.ai is False and loaded.minutes == 55
    assert settings_file.read_bytes() == original
