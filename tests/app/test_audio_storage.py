"""Device cache migration preserves existing audio lookup without generation."""
import json

import pytest

from tutor_app import tts


def test_audio_device_marker_reuses_existing_recording(tmp_path, monkeypatch):
    vault = tmp_path / 'STEM Tutor'
    (vault / '.tutor').mkdir(parents=True)
    cache = tmp_path / 'cache'
    monkeypatch.setenv('STEM_TUTOR_CACHE_ROOT', str(cache))
    (vault / '.tutor/storage.json').write_text(json.dumps({
        'audio_cache': {'mode': 'device', 'namespace': 'test-vault'}}))
    recording = cache / 'STEM Tutor/test-vault/audio/existing.wav'
    recording.parent.mkdir(parents=True)
    recording.write_bytes(b'cached audio payload')
    assert tts.audio_dir(vault) / 'existing.wav' == recording
    assert recording.read_bytes() == b'cached audio payload'
    assert not (vault / '.tutor/audio').exists()


def test_legacy_audio_and_unsafe_device_marker(tmp_path):
    vault = tmp_path / 'STEM Tutor'
    assert tts.audio_dir(vault) == vault / '.tutor/audio'
    (vault / '.tutor').mkdir(parents=True)
    (vault / '.tutor/storage.json').write_text(json.dumps({
        'audio_cache': {'mode': 'device', 'namespace': '../other'}}))
    assert tts.audio_dir(vault) == vault / '.tutor/audio'


@pytest.mark.parametrize('content', ['{invalid', '[]', '{"audio_cache": []}',
                                     '{"audio_cache": {"mode": "device", "namespace": null}}'])
def test_damaged_audio_metadata_does_not_prevent_startup(tmp_path, content):
    vault = tmp_path / 'STEM Tutor'
    (vault / '.tutor').mkdir(parents=True)
    (vault / '.tutor/storage.json').write_text(content)
    assert tts.audio_dir(vault) == vault / '.tutor/audio'
