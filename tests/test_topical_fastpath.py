"""Topical preparation keeps source coverage and private answers explicit."""
import importlib.util
from pathlib import Path
import json

import pytest
from library_assets import read_bytes, copy_to_vault, canonical_path

PATH = Path(__file__).parents[1] / 'extraction/topical_fastpath.py'
spec = importlib.util.spec_from_file_location('topical_fastpath', PATH)
fp = importlib.util.module_from_spec(spec)
if PATH.exists():
    spec.loader.exec_module(fp)

SOURCE = 'asset:legacy-5bc3d81eac5b76326e9a0048'


def test_real_sme_compilation_preserves_all_pages_and_33_occurrences():
    assert hasattr(fp, 'analyse_source'), 'topical adapter is missing'
    result = fp.analyse_source(read_bytes(SOURCE), 'P1', SOURCE)
    assert len(result['pages']) == 25
    assert [p['page'] for p in result['pages']] == list(range(1, 26))
    assert len(result['questions']) == 33
    assert len({q['id'] for q in result['questions']}) == 33
    assert all(q['official_qid'] is None for q in result['questions'])
    assert all(q['answer_status'] == 'missing' for q in result['questions'])
    assert result['teaching_approved'] is False
    assert all(q['regions'] for q in result['questions'])


def test_unknown_profile_retains_fragments_and_never_claims_questions():
    assert hasattr(fp, 'analyse_source'), 'topical adapter is missing'
    result = fp.analyse_source(read_bytes(SOURCE), 'UNSUPPORTED', SOURCE)
    assert result['status'] == 'unsegmented'
    assert not result['questions']
    assert len(result['pages']) == 25
    assert result['review_pages']


def test_source_specific_exclusion_is_digest_bound_and_does_not_modify_original():
    assert hasattr(fp, 'analyse_source'), 'topical adapter is missing'
    raw = read_bytes(SOURCE)
    rule = {'source_id': SOURCE, 'source_sha256': fp.sha(raw), 'reason': 'operator-authorized test exclusion'}
    excluded = fp.analyse_source(raw, 'P1', SOURCE, exclusions=[rule])
    assert excluded['status'] == 'excluded'
    assert not excluded['questions'] and len(excluded['pages']) == 25
    assert all(p['status'] == 'excluded' for p in excluded['pages'])
    rule['source_sha256'] = '0' * 64
    with pytest.raises(ValueError, match='exclusion.*digest'):
        fp.analyse_source(raw, 'P1', SOURCE, exclusions=[rule])
    assert read_bytes(SOURCE) == raw


def test_completed_preparation_is_read_only_and_tamper_evident(tmp_path):
    assert hasattr(fp, 'prepare'), 'topical adapter is missing'
    vault = tmp_path / 'vault'; vault.mkdir()
    source = copy_to_vault(canonical_path(SOURCE), vault)
    before = {p.relative_to(vault).as_posix(): p.read_bytes() for p in vault.rglob('*') if p.is_file()}
    output = tmp_path / 'prepared'
    bundle = fp.prepare(vault, source.relative_to(vault).as_posix(), 'P1', output)
    assert fp.verify_bundle(output)['questions'] == 33
    assert bundle['metrics']['model_calls'] == 0
    assert before == {p.relative_to(vault).as_posix(): p.read_bytes() for p in vault.rglob('*') if p.is_file()}
    with pytest.raises(FileExistsError):
        fp.prepare(vault, source.relative_to(vault).as_posix(), 'P1', output)
    target = output / next(iter(bundle['media']))
    target.write_bytes(b'incomplete')
    with pytest.raises(ValueError, match='digest'):
        fp.verify_bundle(output)


def test_registered_mark_scheme_never_becomes_public_question_media(tmp_path):
    source_id = 'asset:legacy-133722f7d8d562b28066e2d0'
    vault = tmp_path / 'vault'; vault.mkdir()
    source = copy_to_vault(canonical_path(source_id), vault)
    bundle = fp.prepare(vault, source.relative_to(vault).as_posix(), '9702', tmp_path / 'private')
    assert bundle['questions'] == []
    assert len(bundle['private_pages']) == 14
    assert all(item['visibility'] == 'private' for item in bundle['media'].values())


def test_registered_answer_folder_with_prefix_is_private():
    source = 'asset:legacy-eb0e75f225d11a20a0cfbc61'
    result = fp.analyse_source(read_bytes(source), '9702', source, source_path=canonical_path(source))
    assert not result['questions']
    assert result['status'] == 'private_answers_only'
    assert len(result['private_pages']) == len(result['pages'])


def test_empty_continuation_page_cannot_silently_qualify():
    import pymupdf
    with pymupdf.open() as doc:
        doc.new_page(width=596, height=842).insert_text((70, 70), 'Exam Questions\n1 questions\nSave My Exams')
        page = doc.new_page(width=596, height=842)
        page.insert_text((82, 70), '1'); page.insert_text((96, 70), 'Solve this question.')
        doc.new_page(width=596, height=842)
        result = fp.analyse_source(doc.tobytes(), 'P1', 'invalid-test-source')
    assert result['status'] == 'needs_review'
    assert 3 in [p['page'] for p in result['review_pages']]


@pytest.mark.parametrize('course', ['P1', 'UNKNOWN'])
def test_numbered_page_ledger_cannot_hide_deleted_content(tmp_path, course):
    vault = tmp_path / 'vault'; vault.mkdir()
    source = copy_to_vault(canonical_path(SOURCE), vault)
    output = tmp_path / 'bundle'
    bundle = fp.prepare(vault, source.relative_to(vault).as_posix(), 'P1', output)
    if course == 'UNKNOWN':
        for page in bundle['pages']:
            page['status'] = 'unsegmented'
    bundle['questions'] = []
    bundle['review_pages'] = []
    bundle['media'] = {}
    raw = json.dumps(bundle).encode()
    (output / 'bundle.json').write_bytes(raw)
    (output / 'COMPLETE').write_text(fp.sha(raw))
    with pytest.raises(ValueError, match='coverage'):
        fp.verify_bundle(output)


OCR_CACHE = Path(__file__).resolve().parents[2] / 'Work/Workers/extraction/ocr-cache'


def test_cached_physics_is_provisional_and_preserves_private_page_stops():
    source = 'asset:legacy-8f2f9994d0b9bb3f82615c58'
    result = fp.analyse_source(read_bytes(source), '9702', source, ocr_cache=OCR_CACHE)
    assert result['profile'] == 'ocr_readwrite_provisional_v1'
    assert result['status'] == 'needs_review'
    assert len(result['questions']) == 341 and len(result['pages']) == 550
    private = {p['page'] for p in result['private_pages']}
    assert 275 in private
    assert not any(r['page'] in private for q in result['questions'] for r in q['regions'])


@pytest.mark.parametrize('course', ['9701', 'UNSUPPORTED'])
def test_ocr_cannot_assign_physics_questions_to_another_course(course):
    source = 'asset:legacy-8f2f9994d0b9bb3f82615c58'
    result = fp.analyse_source(read_bytes(source), course, source, ocr_cache=OCR_CACHE)
    assert result['questions'] == []
    assert any(i.get('reason') == 'ocr_source_course_conflict' for i in result['issues'] if isinstance(i, dict))


def test_cached_paper_headers_are_fragments_until_whole_question_proof_exists():
    source = 'asset:legacy-fc98465053396209207e8eff'
    result = fp.analyse_source(read_bytes(source), '9701', source, ocr_cache=OCR_CACHE)
    assert result['profile'] == 'ocr_crack_provisional_v1'
    assert result['questions'] == [] and result['status'] == 'unsegmented'
    assert result['review_pages'] and result['private_pages']


def test_prepare_rejects_course_conflicting_with_registered_source(tmp_path):
    vault = tmp_path / 'vault'; vault.mkdir()
    source = copy_to_vault(canonical_path(SOURCE), vault)
    with pytest.raises(ValueError, match='course'):
        fp.prepare(vault, source.relative_to(vault).as_posix(), '9701', tmp_path / 'wrong')
