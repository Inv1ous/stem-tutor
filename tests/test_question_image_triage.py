"""The triage finds page furniture among question images by measurement, groups look-alikes so one verdict covers a
group, remembers verdicts, flags junk in the catalog (reversibly) and never judges answer keys."""
import io
import json
import sys
from pathlib import Path

import pytest
from PIL import Image, ImageDraw

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'build'))
import question_image_triage as triage
import question_media_names as names
from tutorlib.asset_library import AssetLibrary, write_asset

MCQ = 'Library/Courses/9701/Questions/Media/MCQ/'
KEYS = 'Library/Courses/9701/Questions/Media/Keys/'


def png(width, height, lines=(), seed=0):
    image = Image.new('L', (width, height), 255)
    draw = ImageDraw.Draw(image)
    for i, line in enumerate(lines):
        draw.text((20, 15 + 30 * i + seed), line, fill=0)
    out = io.BytesIO()
    image.save(out, 'PNG')
    return out.getvalue()


FOOTER = lambda page: png(900, 100, [f'9.1 PERIODICITY OF THE ELEMENTS IN PERIOD 3      {page}'])
QUESTION = png(900, 420, ['1 Which statement is correct?', 'A one', 'B two', 'C three', 'D four'])


@pytest.fixture
def vault(tmp_path, monkeypatch):
    root = tmp_path / 'STEM Tutor'
    root.mkdir()
    monkeypatch.setattr(triage, 'WORK', tmp_path / 'work')
    monkeypatch.setattr(triage, 'VERDICTS', tmp_path / 'work' / 'image-triage.json')
    for n, data in enumerate([FOOTER(271), FOOTER(272), FOOTER(273), png(900, 100), QUESTION]):
        write_asset(root, f'{MCQ}9701_m23_12_q{n:02d}_mcq_{n:012x}.png', data, metadata={'course': '9701', 'kind': 'Questions/Media'})
    write_asset(root, f'{KEYS}9701_m23_12_q01_key_{9:012x}.png', png(120, 36, ['8     D']), metadata={'course': '9701'})
    return root


def test_measurement_flags_furniture_and_blanks_but_not_a_question(vault):
    assert triage.suspicious(triage.features(FOOTER(271))) == 'short'
    assert triage.suspicious(triage.features(png(900, 300))) == 'blank'
    assert triage.suspicious(triage.features(QUESTION)) is None


def test_scan_groups_lookalikes_and_never_looks_at_keys(vault):
    result = triage.scan(vault)
    assert result['scanned'] == 5 and result['suspects'] == 4          # 3 footers and a blank; the 36 px key is not scanned
    sizes = sorted(len(g['members']) for g in result['groups'].values())
    assert sizes == [1, 3]                                              # the three footers (page numbers differ) are one group
    assert not any('/Keys/' in m['path'] for g in result['groups'].values() for m in g['members'])


def test_a_verdict_is_remembered_so_a_later_scan_does_not_ask_again(vault):
    first = triage.scan(vault)
    key = next(k for k, g in first['groups'].items() if len(g['members']) == 3)
    verdicts = triage.load_verdicts()
    verdicts['groups'][key] = {'signature': first['groups'][key]['signature'], 'height': 100, 'verdict': 'junk', 'why': 'footer'}
    triage.save_verdicts(verdicts)
    later = triage.scan(vault)
    assert later['groups'][key]['verdict'] == 'junk'
    assert triage.check_new(FOOTER(999)) == 'junk'                       # a new crop of the same look is flagged on arrival
    assert triage.check_new(QUESTION) is None


def test_apply_flags_every_member_and_undo_restores_the_catalog(vault):
    first = triage.scan(vault)
    key = next(k for k, g in first['groups'].items() if len(g['members']) == 3)
    triage.save_verdicts({'format_version': 1, 'groups': {key: {'signature': first['groups'][key]['signature'], 'height': 100,
                                                                'verdict': 'junk', 'why': 'footer'}}})
    triage.scan(vault)
    before = (vault / 'Library/catalog.json').read_bytes()
    assert triage.apply(vault, undo=False)['changed'] == 3
    library = AssetLibrary(vault)
    flagged = [r for r in library.records().values() if r.get('junk')]
    assert len(flagged) == 3 and all(f['sha256'] for f in flagged)       # bytes and hashes untouched
    assert triage.apply(vault, undo=False)['changed'] == 0               # idempotent
    assert triage.apply(vault, undo=True)['changed'] == 3
    assert json.loads((vault / 'Library/catalog.json').read_text()) == json.loads(before)


def test_extraction_flags_a_crop_that_looks_like_judged_junk(vault):
    first = triage.scan(vault)
    key = next(k for k, g in first['groups'].items() if len(g['members']) == 3)
    triage.save_verdicts({'format_version': 1, 'groups': {key: {'signature': first['groups'][key]['signature'], 'height': 100,
                                                                'verdict': 'junk', 'why': 'footer'}}})
    legacy = 'Library/SourcePractice/Media/' + 'a' * 64 + '-1111111111111111.png'
    names.store_question_media(vault, FOOTER(500), legacy, course='9701', role='mcq', qid='9701_m23_12_q9')
    assert AssetLibrary(vault).record(legacy)['junk'] is True
    fresh = 'Library/SourcePractice/Media/' + 'b' * 64 + '-2222222222222222.png'
    names.store_question_media(vault, QUESTION[:-1] + b'x', fresh, course='9701', role='mcq', qid='9701_m23_12_q10')
    assert not AssetLibrary(vault).record(fresh).get('junk')
