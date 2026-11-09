"""Registration preserves media source roles and admission gates in disposable vaults."""
import hashlib
import json
from pathlib import Path

import pytest
import test_extraction as diagrams
import test_extraction_native_p1_q4 as p1
import test_extraction_native_p2_q1 as p2
from tutorlib.asset_library import AssetLibrary


def reviewed_case(tmp_path, monkeypatch, course, whole=False):
    # These helpers copy digest-checked sources through tests/library_assets.py.
    if course == 'P1':
        return p1.reviewed(tmp_path, monkeypatch, whole=whole)
    ex, path, data, vault, save = p2.p2_case(tmp_path, monkeypatch, whole=whole)
    return ex, vault, path, data, save


def snapshot(root):
    return {p.relative_to(root).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in root.rglob('*') if p.is_file() and p.name != '.lock'}


def assert_sidecar_source(sidecar, regions):
    assert sidecar['regions'] == regions
    for field, key in [('pdf', 'source_id'), ('page', 'page'),
                       ('source_sha256', 'source_sha256'), ('box', 'box')]:
        assert sidecar[field] == regions[0][key]


@pytest.mark.parametrize('course', ['P1', 'P2'])
@pytest.mark.parametrize('whole', [False, True], ids=['flat', 'whole'])
def test_registered_private_media_uses_ms_and_public_media_uses_qp(tmp_path, monkeypatch, course, whole):
    # Removing the flat private-role selection misattributes its immutable sidecar.
    ex, vault, path, data, _ = reviewed_case(tmp_path, monkeypatch, course, whole)
    review_path = ex.job_dir('fresh') / 'review.json'
    originals = {p: p.read_bytes() for p in [path, review_path]}
    lib = AssetLibrary(vault)
    source_bytes = {s['id']: lib.read(s['id']) for s in ex.load('fresh')['sources']}
    image_bytes = {name: (path.parent / name).read_bytes()
                   for row in data['questions'] for name in row['media']}
    assert ex.check('fresh')['stage'] == 'reviewed'
    registered = ex.register('fresh')
    assert registered['stage'] == 'registered'
    assert registered['teaching_approved'] is False
    lib = AssetLibrary(vault)
    for row in data['questions']:
        assert ex._learner_media(row) == row['question_media']
        assert not set(ex._learner_media(row)) & set(row['mark_scheme_media'])
        for local in row['media']:
            reference = registered['registered_media'][local]
            assert lib.read(reference) == image_bytes[local]
            sidecar = json.loads(lib.read(lib.record(reference)['provenance']['sidecars'][0]))
            assert sidecar['record'] == row
            assert sidecar['review'] == json.loads(originals[review_path])
            assert sidecar['sha256'] == hashlib.sha256(image_bytes[local]).hexdigest()
            assert sidecar['teaching_approved'] is False
            expected = row['mark_scheme_regions'] if local in row['mark_scheme_media'] else row['regions']
            assert_sidecar_source(sidecar, expected)
    assert all(p.read_bytes() == value for p, value in originals.items())
    assert all(lib.read(ref) == value for ref, value in source_bytes.items())
    assert not (vault / '.tutor/topicals/CURRENT').exists()


@pytest.mark.parametrize('course', ['P1', 'P2'])
@pytest.mark.parametrize('fault', ['review-digest', 'visual-review', 'source-bytes', 'stripped-fresh'])
def test_registration_retains_evidence_and_fresh_origin_gates(tmp_path, monkeypatch, course, fault):
    # Registration must refuse before any Library writes when admission evidence fails.
    ex, vault, path, data, _ = reviewed_case(tmp_path, monkeypatch, course)
    if fault == 'review-digest':
        data['questions'][0]['stem'] += ' changed without review'
        path.write_text(json.dumps(data))
    elif fault == 'visual-review':
        review_path = ex.job_dir('fresh') / 'review.json'
        review = json.loads(review_path.read_text())
        review['inspected_images'] = []
        review_path.write_text(json.dumps(review))
    elif fault == 'source-bytes':
        source = next(s for s in ex.load('fresh')['sources'] if s['id'] == (p1.MS if course == 'P1' else p2.MS))
        original = vault / AssetLibrary(vault).record(source['id'])['path']
        original.write_bytes(b'disposable corrupt original')
    else:
        with ex.state_lock('fresh') as state:
            state.pop('initial_native_question')
            state.pop('selected_item_scope')
        data.pop('selected_item_scope')
        path.write_text(json.dumps(data))
    before = snapshot(vault)
    with pytest.raises((ValueError, ex.library.Fail)):
        ex.register('fresh')
    assert snapshot(vault) == before
    assert not ex.load('fresh').get('registrations')
    assert not (vault / '.tutor/topicals/CURRENT').exists()


@pytest.mark.parametrize('metadata', ['absent', 'ignored-list', 'ignored-null'])
def test_diagram_keeps_its_regions_with_ignored_question_metadata(tmp_path, monkeypatch, metadata):
    # A question-only private-role branch must not consume accepted diagram extras.
    vault = tmp_path / 'vault'
    vault.mkdir()
    monkeypatch.setenv('STEM_TUTOR_VAULT', str(vault))
    monkeypatch.setenv('STEM_LIBRARY_CACHE', str(tmp_path / 'reader-cache'))
    ex = diagrams.extraction()
    path = diagrams.reviewed_diagram(ex, tmp_path, monkeypatch)
    data = json.loads(path.read_text())
    record = data['diagrams'][0]
    if metadata == 'ignored-list':
        record['mark_scheme_media'] = ['circuit.png']
    elif metadata == 'ignored-null':
        record['mark_scheme_media'] = None
    assert 'mark_scheme_regions' not in record
    path.write_text(json.dumps(data))
    errors, _ = ex._candidate_problems(ex.load('diagram'))
    assert errors == []
    review_path = ex.job_dir('diagram') / 'review.json'
    review = json.loads(review_path.read_text())
    review['candidate_sha256'] = ex.digest(path)
    review_path.write_text(json.dumps(review))
    assert ex.check('diagram')['stage'] == 'reviewed'
    source = Path(ex.load('diagram')['sources'][0]['path'])
    originals = {p: p.read_bytes() for p in [path, review_path, path.parent / 'circuit.png', source]}
    registered = ex.register('diagram')
    assert registered['stage'] == 'registered'
    assert registered['teaching_approved'] is False
    lib = AssetLibrary(vault)
    reference = registered['registered_media']['circuit.png']
    assert '/Diagrams/' in reference
    assert lib.read(reference) == originals[path.parent / 'circuit.png']
    sidecar = json.loads(lib.read(lib.record(reference)['provenance']['sidecars'][0]))
    assert sidecar['record'] == record and sidecar['review'] == review
    assert_sidecar_source(sidecar, record['regions'])
    assert all(p.read_bytes() == value for p, value in originals.items())
    assert not (vault / '.tutor/topicals/CURRENT').exists()
