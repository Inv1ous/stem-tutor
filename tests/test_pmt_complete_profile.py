"""Complete native-source regions, using immutable registered fixtures in temp vaults."""
import hashlib
import importlib
import importlib.util
import json
from pathlib import Path
import sys

import pymupdf
import pytest
from library_assets import canonical_path, copy_to_vault, read_bytes

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'extraction'))
import source_practice as build

CASES = [
    ('asset:asset-0f507f71116a4a6b0998380f', 'S2', [6, 11],
     ['occurrence-bf2d0c1c72ea47c51b154939', 'occurrence-ecd11140bafb6b0565f0cf8e']),
    ('asset:asset-548a7193599a829723e46a06', 'P4', [7, 11, 12],
     ['occurrence-c3231f9a999f74c86f8b7e3a', 'occurrence-d8474ce074ca66a77804a359']),
    ('asset:asset-46db0dc5b8a905df939a1883', 'M1', [9, 8],
     ['occurrence-16578954e3a4e9b572abe2e2', 'occurrence-46bd9527481d682225abf888']),
]


def profile():
    assert importlib.util.find_spec('pmt_complete_profile') is not None, 'complete PMT source adapter is missing'
    return importlib.import_module('pmt_complete_profile')


def staged(tmp_path, reference):
    vault = tmp_path / 'vault'
    vault.mkdir(exist_ok=True)
    path = copy_to_vault(canonical_path(reference), vault)
    catalog_path = vault / 'Library/catalog.json'
    catalog = json.loads(catalog_path.read_bytes())
    key = next(k for k, v in catalog['assets'].items() if v['path'] == path.relative_to(vault).as_posix())
    catalog['assets'][reference.removeprefix('asset:')] = catalog['assets'].pop(key)
    catalog_path.write_text(json.dumps(catalog))
    return vault


@pytest.fixture(autouse=True)
def no_live_workers(tmp_path, monkeypatch):
    monkeypatch.setattr(build, 'WORKERS', tmp_path / 'no-workers')


@pytest.mark.parametrize('reference,course,marks,old_ids', CASES)
def test_actual_complete_inventory_and_original_occurrence_ids(reference, course, marks, old_ids):
    bundle = profile().analyse(read_bytes(reference), course, reference, source_path=canonical_path(reference))
    assert [q['marks'] for q in bundle['questions']] == marks
    assert [q['id'] for q in bundle['questions'][:len(old_ids)]] == old_ids
    assert bundle['issues'] == []
    for page in bundle['pages']:
        assert page['intervals'][0]['box'][1] == 0
        assert page['intervals'][-1]['box'][3] == 1
        assert all(a['box'][3] == b['box'][1] for a, b in zip(page['intervals'], page['intervals'][1:]))
    if course == 'S2':
        assert [r['page'] for r in bundle['questions'][1]['regions']] == [1, 2]
        assert '(c)' in bundle['questions'][1]['question_text']
        assert 'unlikely' in bundle['questions'][1]['scheme_text']
    if course == 'P4':
        assert bundle['title'].startswith('C4 ')
        assert [r['page'] for r in bundle['questions'][0]['mark_scheme_regions']] == [2, 3]
        assert [r['page'] for r in bundle['questions'][2]['regions']] == [2]
        for question, page, top in [(0, 2, 453.367), (1, 3, 185.655), (2, 3, 490.338)]:
            region = bundle['questions'][question]['mark_scheme_regions'][0]
            assert region['page'] == page and region['box'][1] * 841.92 < top
    if course == 'M1':
        assert 'either order' in bundle['questions'][1]['scheme_text']
        assert all(r['page'] == 2 for q in bundle['questions'] for r in q['mark_scheme_regions'])
        assert any(i['role'] == 'examiner_comments' for i in bundle['pages'][2]['intervals'])


@pytest.mark.parametrize('reference,course,marks,old_ids', CASES)
def test_preparation_replay_complete_pixels_and_fresh_output(tmp_path, reference, course, marks, old_ids):
    vault = staged(tmp_path, reference)
    output = tmp_path / 'Work/Preparation/new'
    profile().prepare(vault, reference, course, output, dpi=72)
    with pytest.raises(FileExistsError):
        profile().prepare(vault, reference, course, output, dpi=72)
    result = build.verify(vault, output)
    assert [q['marks'] for q in result['items']] == marks and result['held'] == []
    assert result['metrics']['page_renders'] == len(result['pages'])
    assert all(q['teaching_approved'] is False for q in result['items'])
    assert all(result['_pixels'][m] for q in result['items'] for m in q['question_media'] + q['mark_scheme_media'])


@pytest.mark.parametrize('fault', ['region', 'missing_continuation', 'total', 'source', 'course', 'ledger', 'dpi', 'pixel'])
def test_resealed_forgery_cannot_change_replayed_source(tmp_path, fault):
    reference, course, _, _ = CASES[0]
    vault = staged(tmp_path, reference)
    output = tmp_path / 'Work/Preparation/new'
    profile().prepare(vault, reference, course, output, dpi=72)
    bundle = json.loads((output / 'bundle.json').read_bytes())
    if fault == 'region': bundle['questions'][0]['regions'][0]['box'][3] = .9
    elif fault == 'missing_continuation': bundle['questions'][1]['regions'].pop()
    elif fault == 'total': bundle['questions'][0]['marks'] = 99
    elif fault == 'source': bundle['source']['sha256'] = '0' * 64
    elif fault == 'course': bundle['course'] = 'P4'
    elif fault == 'ledger': bundle['pages'][0]['intervals'].pop()
    elif fault == 'dpi': bundle['metrics']['dpi'] = 73
    else:
        name = bundle['questions'][0]['question_media'][0]
        (output / name).write_bytes(b'forged pixels')
        bundle['media'][name]['sha256'] = hashlib.sha256(b'forged pixels').hexdigest()
    raw = json.dumps(bundle).encode()
    (output / 'bundle.json').write_bytes(raw)
    (output / 'COMPLETE').write_text(hashlib.sha256(raw).hexdigest())
    with pytest.raises(ValueError): build.verify(vault, output)


@pytest.mark.parametrize('fault', ['missing_total', 'false_total', 'reset', 'report', 'footer', 'continuation_private'])
def test_ambiguous_native_evidence_holds_entire_source(fault):
    reference, course, _, _ = CASES[0]
    with pymupdf.open(stream=read_bytes(reference), filetype='pdf') as doc:
        if fault in {'missing_total', 'false_total'}:
            boxes = doc[0].search_for('(Total 6 marks)')
            for box in boxes: doc[0].add_redact_annot(box, fill=(1, 1, 1))
            doc[0].apply_redactions()
            if fault == 'false_total': doc[0].insert_text((470, 280), '(Total 99 marks)', fontsize=9)
        elif fault == 'reset': doc[2].insert_text((56.7, 500), '1.', fontsize=11)
        elif fault == 'report':
            for box in doc[3].search_for('candidates'): doc[3].add_redact_annot(box)
            doc[3].apply_redactions()
        elif fault == 'footer':
            for box in doc[1].search_for('Edexcel Internal Review'): doc[1].add_redact_annot(box)
            doc[1].apply_redactions()
        else: doc[1].insert_text((100, 130), 'M1 A1', fontsize=11)
        raw = doc.tobytes()
    with pytest.raises(ValueError): profile().analyse(raw, course, reference, source_path=canonical_path(reference))


@pytest.mark.parametrize('kind', ['glyph', 'image', 'vector', 'raster'])
def test_content_crossing_public_private_boundary_is_not_sliced(kind):
    reference, course, _, _ = CASES[1]
    with pymupdf.open(stream=read_bytes(reference), filetype='pdf') as doc:
        page = doc[1]
        # Occupy the entire known whitespace between Q3's total and MS1's tall formula.
        if kind == 'glyph':
            page.insert_text((280, 450), '|', fontsize=65)
        elif kind == 'vector': page.draw_line((280, 390), (280, 480), width=2)
        else:
            from PIL import Image
            import io
            image = Image.new('RGB', (4, 90), 'black' if kind == 'raster' else 'white')
            stream = io.BytesIO(); image.save(stream, format='PNG')
            page.insert_image(pymupdf.Rect(280, 390, 284, 480), stream=stream.getvalue())
        raw = doc.tobytes()
    with pytest.raises(ValueError): profile().analyse(raw, course, reference, source_path=canonical_path(reference))


@pytest.mark.parametrize('color', [(0, 0, 0), (.99, .99, .99)])
def test_raster_proof_is_independent_of_native_object_inventory(color):
    reference = CASES[1][0]
    with pymupdf.open(stream=read_bytes(reference), filetype='pdf') as doc:
        page = doc[1]
        page.draw_line((280, 390), (280, 480), width=2, color=color)
        # Native bounds alone appear empty. The real page raster must still veto.
        with pytest.raises(ValueError, match='raster'):
            profile()._separator(page, [], 410, 450)


@pytest.mark.parametrize('page', [1, 2])
def test_deleting_physical_continuation_cannot_pass_with_old_inventory(page):
    reference, course, _, _ = CASES[page-1]
    with pymupdf.open(stream=read_bytes(reference), filetype='pdf') as doc:
        doc.delete_page(page)
        raw = doc.tobytes()
    with pytest.raises(ValueError):
        profile().analyse(raw, course, reference, source_path=canonical_path(reference))


def test_unknown_report_tail_is_held_even_after_an_authenticated_report():
    reference, course, _, _ = CASES[0]
    with pymupdf.open(stream=read_bytes(reference), filetype='pdf') as doc:
        page = doc.new_page(width=doc[0].rect.width, height=doc[0].rect.height)
        page.insert_text((56.7, 48), 'S2 Modelling', fontsize=11)
        page.insert_text((400, 48), 'PhysicsAndMathsTutor.com', fontsize=9)
        page.insert_text((56.7, 810), 'Edexcel Internal Review', fontsize=10)
        page.insert_text((530, 810), str(len(doc)), fontsize=10)
        page.insert_text((85, 100), 'UNCLASSIFIED PRIVATE MATERIAL', fontsize=10)
        raw = doc.tobytes()
    with pytest.raises(ValueError, match='commentary|tail'):
        profile().analyse(raw, course, reference, source_path=canonical_path(reference))


def test_fresh_preparation_requires_authoring_path(tmp_path):
    reference, course, _, _ = CASES[0]
    vault = staged(tmp_path, reference)
    with pytest.raises(ValueError, match='Preparation'):
        profile().prepare(vault, reference, course, tmp_path / 'arbitrary', dpi=72)


def test_new_private_schemes_keep_runtime_attempt_gate(tmp_path):
    from tutorlib.source_practice import Collection
    reference, course, _, _ = CASES[2]
    vault = staged(tmp_path, reference)
    output = tmp_path / 'Work/Preparation/new'
    profile().prepare(vault, reference, course, output, dpi=72)
    build.publish(vault, [output], expected_current=None)
    collection = Collection(vault)
    question = collection.questions(course)[0]
    public = collection.question(question['id'])
    assert public['question_media'] and not {'scheme_text', 'mark_scheme_media'} & public.keys()
    attempt = collection.submit(question['id'], 'written response')
    private = collection.feedback(attempt['attempt_id'])['scheme_media'][0]
    with pytest.raises(ValueError): collection.media_path(question['id'], private)
    assert collection.media_path(question['id'], private, attempt_id=attempt['attempt_id']).is_file()


def test_report_prose_without_a_proved_boundary_cannot_become_scheme_notes():
    reference, course, _, _ = CASES[0]
    with pymupdf.open(stream=read_bytes(reference), filetype='pdf') as doc:
        doc[2].insert_text((85, 450), 'This question proved difficult for the candidates.', fontsize=10)
        raw = doc.tobytes()
    with pytest.raises(ValueError):
        profile().analyse(raw, course, reference, source_path=canonical_path(reference))


def test_disconnected_unmarked_equation_after_public_total_has_no_public_ownership():
    reference, course, _, _ = CASES[1]
    with pymupdf.open(stream=read_bytes(reference), filetype='pdf') as doc:
        doc[1].insert_text((200, 430), 'x = 123456789', fontsize=10)
        raw = doc.tobytes()
    with pytest.raises(ValueError, match='ownership|total'):
        profile().analyse(raw, course, reference, source_path=canonical_path(reference))


@pytest.mark.parametrize('position', ['header', 'footer'])
def test_unexplained_margin_premise_cannot_be_discarded_as_furniture(position):
    reference, course, _, _ = CASES[0]
    with pymupdf.open(stream=read_bytes(reference), filetype='pdf') as doc:
        doc[0].insert_text((100, 25 if position == 'header' else 835),
                           'ADDITIONAL QUESTION PREMISE: choose x = 123456789', fontsize=8)
        raw = doc.tobytes()
    with pytest.raises(ValueError, match='furniture'):
        profile().analyse(raw, course, reference, source_path=canonical_path(reference))


@pytest.mark.parametrize('position,kind', [('header', 'vector'), ('footer', 'image')])
def test_unexplained_painted_margin_object_is_not_authenticated_furniture(position, kind):
    reference, course, _, _ = CASES[0]
    with pymupdf.open(stream=read_bytes(reference), filetype='pdf') as doc:
        page = doc[0]
        y = 15 if position == 'header' else 825
        if kind == 'vector': page.draw_rect(pymupdf.Rect(100, y, 200, y+8), fill=(0, 0, 0))
        else:
            from PIL import Image
            import io
            stream = io.BytesIO(); Image.new('RGB', (20, 5), 'white').save(stream, format='PNG')
            page.insert_image(pymupdf.Rect(100, y, 200, y+8), stream=stream.getvalue())
        raw = doc.tobytes()
    with pytest.raises(ValueError, match='furniture'):
        profile().analyse(raw, course, reference, source_path=canonical_path(reference))
