"""Question-leak pruning on a disposable vault: gate rules, classes, referenced-not-deleted, journal + rollback, hook."""
import hashlib
import importlib.util
import io
import json
from pathlib import Path
import sys

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'build'))
import library_assets
import prune_question_leaks as prune
import question_leak_gate as gate
from tutorlib.asset_library import AssetLibrary, write_asset

LIB = 'Library/Courses/{}/Questions/Media/{}/'
G_STRIP = 'Library/Courses/9702/Questions/Media/Long/9702_w19_22_q02_p01_long_c71a71af2f9b.png'
G_STRIP_2 = 'Library/Courses/9701/Questions/Media/MCQ/9701_w25_11_q08_p02_mcq_6fe1ad13c1e7.png'  # shc-of-water row
CONSTANTS = 'Library/Courses/9701/Questions/Media/Long/9701_s23_22_q02_p04_long_7e242826b069.png'
PERIODIC = 'Library/Courses/9701/Questions/Media/Reference/9701_s22_22_q06_ref_1c3600c66fae.png'
# The confirmed leaks were removed from course question media on 2026-11-07; their exact bytes stay
# registered as gate regression evidence and are installed at their original paths in the test vault.
EVIDENCE = 'Library/Shared/ReviewEvidence/question-leaks/'
LEAKS = (G_STRIP, G_STRIP_2, CONSTANTS, PERIODIC)


def source(path):
    return EVIDENCE + path.rsplit('/', 1)[1] if path in LEAKS else path
MCQ = 'Library/Courses/9701/Questions/Media/MCQ/9701_s19_11_q21_p02_mcq_b656410d05b6.png'
KEY_ROW = 'Library/Courses/9701/Questions/Media/Keys/9701_s25_11_q02_key_d429d8b97056.png'
needs_ocr = pytest.mark.skipif(gate._binary() is None, reason='Apple Vision OCR unavailable')


def sha(data):
    return hashlib.sha256(data).hexdigest()


def blank(width, height):
    from PIL import Image
    out = io.BytesIO()
    Image.new('RGB', (width, height), 'white').save(out, format='PNG')
    return out.getvalue()


@pytest.fixture
def vault(tmp_path):
    vault = tmp_path / 'STEM Tutor'
    vault.mkdir()
    for path in (G_STRIP, G_STRIP_2, CONSTANTS, PERIODIC, MCQ, KEY_ROW):
        course = path.split('/')[2]
        write_asset(vault, path, library_assets.read_bytes(source(path)), metadata={'course': course, 'kind': 'Questions/Media'})
    # Cited by an immutable topical release: a real leak, but an item still shows it.
    bank = {'items': [{'id': '9701_s23_22_q2_e_iii', 'kind': 'structured', 'source': {'qid': '9701_s23_22_q2'},
                       'images': [CONSTANTS]},
                      {'id': '9701_s19_11_q21', 'kind': 'mcq', 'source': {'qid': '9701_s19_11_q21'}, 'images': [MCQ]}]}
    write_asset(vault, 'Library/Shared/Topicals/Releases/v1/bank.json', json.dumps(bank).encode())
    # A learner event cites the second g strip: preservation boundary.
    events = vault / '.tutor/events.jsonl'
    events.parent.mkdir(parents=True)
    events.write_text(json.dumps({'image': G_STRIP_2}) + '\n')
    return vault


def test_text_rules_separate_reference_matter_from_questions():
    assert gate.text_verdict('acceleration of free fall\ng=9.81 ms-2')[0] == 'delete'
    assert gate.text_verdict('15\nImportant values, constants and standards\nmolar gas constant R = 8.31')[0] == 'delete'
    assert gate.text_verdict('Formulae\nuniformly accelerated motion\ns = ut + 1/2 at2')[0] == 'delete'
    question = ('9 The resultant force on a raindrop is given by F = mg - kv where g is the acceleration of free fall.\n'
                'Which graph shows the variation of F with time?')
    assert gate.text_verdict(question) is None
    assert gate.text_verdict('Use the Periodic Table to explain the trend. [2]') is None
    assert gate.text_verdict('2(a)(i) Li+ AND S2- M1 giant M2 strong forces') is None


def test_small_blank_and_errors_are_review_never_delete(tmp_path):
    features = {'width': 1111, 'height': 55, 'ink': 0.01, 'dhash': '0' * 16, 'aspect': 20.2}
    assert gate.decide(features, '')['action'] == 'review'
    assert gate.decide({**features, 'height': 900, 'aspect': 1.2, 'ink': 0.0}, '')['reason'] == 'near-blank image'
    assert gate.decide({**features, 'height': 900, 'aspect': 1.2}, None)['action'] == 'review'
    broken = tmp_path / 'broken.png'
    broken.write_bytes(b'not an image')
    verdict = gate.classify(broken)
    assert verdict['action'] == 'review' and 'gate error' in verdict['reason']
    assert gate.classify(tmp_path / 'missing.png')['action'] == 'review'


def strip(width, height, borders, ink_box=True):
    from PIL import Image, ImageDraw
    image = Image.new('L', (width, height), 255)
    draw = ImageDraw.Draw(image)
    for x in borders:
        draw.line([(x, 0), (x, height - 1)], fill=0, width=2)
    if ink_box:
        draw.rectangle([200, 15, 230, 40], fill=0)
    out = io.BytesIO()
    image.save(out, format='PNG')
    return out.getvalue()


def test_boxed_key_rows_are_kept_but_data_rows_and_unread_strips_are_not(tmp_path):
    key_row, data_row, loose = tmp_path / 'key.png', tmp_path / 'data.png', tmp_path / 'loose.png'
    key_row.write_bytes(strip(1110, 56, (2, 140, 990, 1105)))   # number | letter | marks
    data_row.write_bytes(strip(1005, 53, (2, 400, 1000)))       # name | value (data-sheet constant row)
    loose.write_bytes(strip(1110, 56, ()))                      # unboxed fragment
    features = {p.name: gate.measure(p) for p in (key_row, data_row, loose)}
    assert features['key.png']['rules'] == 4 and gate.is_table_row(features['key.png'])
    assert not gate.is_table_row(features['data.png']) and not gate.is_table_row(features['loose.png'])
    assert gate.decide(features['key.png'], '')['action'] == 'keep'
    assert gate.decide(features['key.png'], None)['action'] == 'review'  # OCR did not run: unchecked
    assert gate.decide(features['data.png'], '')['action'] == 'review'
    assert gate.decide(features['loose.png'], '')['action'] == 'review'
    # Reference matter is decided by its text first, boxed or not.
    assert gate.decide(features['key.png'], 'specific heat capacity of water c = 4.18')['action'] == 'delete'
    real = gate.measure(io.BytesIO(library_assets.read_bytes(KEY_ROW)))
    assert gate.is_table_row(real) and gate.decide(real, '')['action'] == 'keep'


def test_near_duplicate_of_confirmed_leak_is_deleted_without_ocr():
    from PIL import Image
    image = Image.open(io.BytesIO(library_assets.read_bytes(source(G_STRIP))))
    features = {'width': image.width, 'height': image.height, 'ink': 0.05, 'dhash': gate.dhash(image),
                'aspect': round(image.width / image.height, 3)}
    signature = {'dhash': features['dhash'], 'aspect': features['aspect'], 'sha256': 'f' * 64, 'reason': 'g strip'}
    assert gate.decide(features, None, signatures=[signature])['action'] == 'delete'


@needs_ocr
def test_gate_reads_real_leaks_and_keeps_questions(vault):
    verdicts = gate.classify_many([vault / p for p in (G_STRIP, CONSTANTS, PERIODIC, MCQ)], signatures=[])
    actions = {Path(k).name: v['action'] for k, v in verdicts.items()}
    assert actions[Path(G_STRIP).name] == 'delete'
    assert actions[Path(CONSTANTS).name] == 'delete'
    assert actions[Path(PERIODIC).name] == 'delete'  # printed sideways: read by rotated OCR
    assert actions[Path(MCQ).name] == 'keep'


@needs_ocr
def test_plan_classes_and_referenced_leaks_are_kept(vault, tmp_path):
    before = (vault / 'Library/catalog.json').read_bytes()
    plan = prune.build_plan(vault, cache_path=tmp_path / 'ocr.json')
    assert (vault / 'Library/catalog.json').read_bytes() == before  # plan is read-only
    by_path = {e['path']: e for e in plan['entries']}
    assert by_path[G_STRIP]['class'] == 'LEAK_UNREFERENCED'
    assert by_path[PERIODIC]['class'] == 'LEAK_UNREFERENCED'
    assert by_path[CONSTANTS]['class'] == 'LEAK_REFERENCED'
    assert by_path[CONSTANTS]['items'][0]['item'] == '9701_s23_22_q2_e_iii'
    assert by_path[G_STRIP_2]['class'] == 'LEAK_REFERENCED'
    assert 'learner event/answer/grade reference' in by_path[G_STRIP_2]['holds']
    assert KEY_ROW not in by_path and MCQ not in by_path and plan['kept'] == 2  # boxed key row: kept (gate v2)
    assert {d['path'] for d in plan['deletes']} == {G_STRIP, PERIODIC}
    assert prune.simulate(vault, plan)['broken_count'] == 0
    review = prune.review_file(plan)
    assert {r['path'] for r in review['items']} == {CONSTANTS, G_STRIP_2}


@needs_ocr
def test_apply_deletes_journals_and_rollback_restores_catalog(vault, tmp_path):
    plan = prune.build_plan(vault, cache_path=tmp_path / 'ocr.json')
    plan['reference_check'] = prune.simulate(vault, plan)
    before = (vault / 'Library/catalog.json').read_bytes()
    journal, backup = tmp_path / 'work/journal.json', tmp_path / 'work/catalog.before-prune.json'
    result = prune.apply(plan, journal, backup=backup)
    assert result['status'] == 'complete' and result['deleted'] == 2 and result['bytes_freed'] > 0
    assert not (vault / G_STRIP).exists() and not (vault / PERIODIC).exists()
    assert (vault / CONSTANTS).exists() and (vault / G_STRIP_2).exists() and (vault / KEY_ROW).exists()
    assert backup.read_bytes() == before
    records = AssetLibrary(vault).records()
    assert G_STRIP not in {r['path'] for r in records.values()}
    saved = json.loads(journal.read_text())
    assert saved['status'] == 'complete' and not saved['bytes_restorable']
    assert {(m['path'], m['sha256']) for m in saved['manifest']} == {(d['path'], d['sha256']) for d in plan['deletes']}
    assert 'catalog_before' not in saved  # a hash manifest and the backup path, not bytes
    assert prune.apply(plan, journal, backup=backup)['status'] == 'complete'  # idempotent resume
    undone = prune.rollback(journal)
    assert undone['status'] == 'rolled_back' and undone['bytes_missing'] == 2
    assert (vault / 'Library/catalog.json').read_bytes() == before


def test_apply_refuses_stale_or_unverified_plans(vault, tmp_path):
    plan = {'tool': prune.TOOL, 'errors': [], 'vault': str(vault), 'catalog_sha256': '0' * 64, 'deletes': [],
            'reference_check': {'broken_count': 0}}
    with pytest.raises(ValueError, match='catalog changed'):
        prune.apply(plan, tmp_path / 'j.json', backup=tmp_path / 'b.json')
    with pytest.raises(ValueError, match='reference-verified'):
        prune.apply({**plan, 'reference_check': {'broken_count': 1}}, tmp_path / 'j.json', backup=tmp_path / 'b.json')
    with pytest.raises(ValueError, match='outside the learner vault'):
        prune.apply(plan, vault / 'j.json', backup=tmp_path / 'b.json')


@needs_ocr
def test_extraction_hook_blocks_question_leaks_and_flags_the_rest(tmp_path):
    spec = importlib.util.spec_from_file_location('extraction_cli', ROOT / 'extraction/extract.py')
    extract = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(extract)
    candidate = tmp_path / 'candidate'
    (candidate / 'media').mkdir(parents=True)
    for name, path in (('leak.png', G_STRIP), ('q.png', MCQ), ('ms-leak.png', CONSTANTS)):
        (candidate / 'media' / name).write_bytes(library_assets.read_bytes(source(path)))
    (candidate / 'media/tiny.png').write_bytes(blank(150, 40))
    state = {'candidate': str(candidate / 'candidate.json')}
    record = {'id': 'r1', 'media': ['media/leak.png', 'media/q.png', 'media/tiny.png', 'media/ms-leak.png'],
              'mark_scheme_media': ['media/ms-leak.png']}
    errors = extract._leak_gate_problems(state, record)
    assert len(errors) == 1 and 'media/leak.png' in errors[0] and 'data-sheet leak' in errors[0]
    flags = state['media_gate']
    assert flags['media/tiny.png']['action'] == 'review' and not flags['media/tiny.png']['blocking']
    assert flags['media/ms-leak.png']['action'] == 'delete' and not flags['media/ms-leak.png']['blocking']
    assert 'media/q.png' not in flags


def test_extraction_hook_fails_safe(tmp_path, monkeypatch):
    spec = importlib.util.spec_from_file_location('extraction_cli', ROOT / 'extraction/extract.py')
    extract = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(extract)
    monkeypatch.setattr(gate, 'classify_many', lambda *a, **k: (_ for _ in ()).throw(RuntimeError('boom')))
    state = {'candidate': str(tmp_path / 'candidate.json')}
    assert extract._leak_gate_problems(state, {'id': 'r', 'media': ['media/a.png']}) == []
    assert state['media_gate']['media/a.png']['action'] == 'review'
