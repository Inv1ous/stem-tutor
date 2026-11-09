"""Loose question media is planned into MCQ/Long/Keys/Reference without touching a real vault."""
import hashlib
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'build'))
import file_unfiled_question_media as unfiled


def seed(tmp_path, name, data=b'image', kind='Questions/Media'):
    vault = tmp_path / 'STEM Tutor'
    relative = f'Library/Courses/9701/Questions/Media/{name}'
    target = vault / relative
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(data)
    digest = hashlib.sha256(data).hexdigest()
    catalog = {'format_version': 1, 'assets': {'loose-' + digest[:8]: {
        'path': relative, 'sha256': digest, 'course': '9701', 'kind': kind}}}
    (vault / 'Library/catalog.json').write_text(json.dumps(catalog))
    return vault, digest


def test_key_name_is_planned_into_keys(tmp_path):
    vault, digest = seed(tmp_path, '9701_m17_12_q01_ms.png')
    report = unfiled.build_plan(vault, references=False)
    assert report['errors'] == []
    assert [m['to'] for m in report['moves']] == [
        f'Library/Courses/9701/Questions/Media/Keys/9701_m17_12_q01_key_{digest[:12]}.png']
    assert report['details']['loose-' + digest[:8]]['role'] == 'key'
    assert report['held'] == []


def test_pinned_image_is_held_not_moved(tmp_path):
    vault, digest = seed(tmp_path, '9701_m17_12_q01_ms-abcdef123456-0123456789abcdef.png')
    report = unfiled.build_plan(vault, references=False)
    assert report['moves'] == []
    assert [(h['id'], h['reason']) for h in report['held']] == [
        ('loose-' + digest[:8], 'validator-pinned legacy name')]
