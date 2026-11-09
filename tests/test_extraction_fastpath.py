"""Real source-backed mechanical preparation; no production learner writes."""
import importlib.util
from pathlib import Path
import sys

import pytest

from library_assets import read_bytes, copy_to_vault, canonical_path

MODULE = Path(__file__).parents[1] / 'extraction/fastpath.py'
spec = importlib.util.spec_from_file_location('extraction_fastpath', MODULE)
fp = importlib.util.module_from_spec(spec)
if MODULE.exists():
    spec.loader.exec_module(fp)

QP = 'asset:legacy-33e899eb7277075af5175a4b'
MS = 'asset:legacy-f34238051329383b94e62f54'
PHYSICS_MS = 'asset:legacy-e4979d636c635185ceb28fb9'


def test_real_paper_has_40_stable_questions_and_official_key_rows():
    assert hasattr(fp, 'analyse_pair'), 'mechanical native adapter is missing'
    result = fp.analyse_pair(read_bytes(QP), read_bytes(MS), '9701_s20_12', QP, MS)
    assert result['paper'] == '9701_s20_12'
    assert [r['official_qid'] for r in result['questions']] == [f'9701_s20_12_q{n}' for n in range(1, 41)]
    assert ''.join(r['answer'] for r in result['questions'][:10]) == 'BCCADDBCAB'
    assert all(r['mark_scheme_regions'] and r['regions'] for r in result['questions'])
    assert len(result['qp_pages']) == 16 and len(result['ms_pages']) == 3
    assert {r['page'] for r in result['qp_pages']} == set(range(1, 17))
    assert all(r['status'] for r in result['qp_pages'] + result['ms_pages'])
    assert result['status'] == 'prepared_unreviewed'
    assert result['teaching_approved'] is False


def test_wrong_paper_key_rejected_before_join():
    assert hasattr(fp, 'analyse_pair'), 'mechanical native adapter is missing'
    with pytest.raises(ValueError, match='identity'):
        fp.analyse_pair(read_bytes(QP), read_bytes(PHYSICS_MS), '9701_s20_12', QP, PHYSICS_MS)


def test_shared_section_b_context_preserved_and_explicitly_flagged():
    assert hasattr(fp, 'analyse_pair'), 'mechanical native adapter is missing'
    result = fp.analyse_pair(read_bytes(QP), read_bytes(MS), '9701_s20_12', QP, MS)
    for row in result['questions'][30:]:
        assert row['context_regions']
        assert 'shared_context_requires_review' in row['review_reasons']


def test_bundle_is_fresh_only_and_tamper_evident(tmp_path):
    assert hasattr(fp, 'prepare'), 'mechanical native adapter is missing'
    vault = tmp_path / 'vault'
    vault.mkdir()
    qp_path = copy_to_vault(canonical_path(QP), vault)
    ms_path = copy_to_vault(canonical_path(MS), vault)
    before = {p: p.read_bytes() for p in [qp_path, ms_path, vault / 'Library/catalog.json']}
    output = tmp_path / 'preparation' / 'one'
    result = fp.prepare(vault, qp_path.relative_to(vault).as_posix(), ms_path.relative_to(vault).as_posix(), output)
    assert result['status'] == 'prepared_unreviewed'
    assert fp.verify_bundle(output)['questions'] == 40
    assert not (vault / '.tutor').exists()
    assert before == {p: p.read_bytes() for p in before}
    with pytest.raises((ValueError, FileExistsError), match='exists'):
        fp.prepare(vault, qp_path.relative_to(vault).as_posix(), ms_path.relative_to(vault).as_posix(), output)
    public = set(result['public_media'])
    private = set(result['private_media'])
    assert public and private and not public & private
    target = output / next(iter(public))
    target.write_bytes(b'partial interrupted output')
    with pytest.raises(ValueError, match='digest'):
        fp.verify_bundle(output)


def test_incomplete_directory_is_not_a_completed_bundle(tmp_path):
    assert hasattr(fp, 'verify_bundle'), 'mechanical native adapter is missing'
    with pytest.raises(ValueError, match='complete'):
        fp.verify_bundle(tmp_path)


def test_missing_question_anchor_is_not_silently_ignored():
    import pymupdf
    with pymupdf.open(stream=read_bytes(QP), filetype='pdf') as doc:
        # Invalid source derivative stays disposable and never enters Library.
        page = doc[1]
        word = next(w for w in page.get_text('words') if w[4] == '1' and 45 < w[0] < 55)
        page.add_redact_annot(pymupdf.Rect(word[:4]))
        page.apply_redactions()
        invalid = doc.tobytes()
    result = fp.analyse_pair(invalid, read_bytes(MS), '9701_s20_12', QP, MS)
    assert result['status'] == 'needs_review' and result['questions'] == []
    assert any(e['reason'] == 'question_number_sequence' and 1 in e['missing'] for e in result['exceptions'])


def test_missing_official_answer_never_becomes_a_guessed_key():
    import pymupdf
    with pymupdf.open(stream=read_bytes(MS), filetype='pdf') as doc:
        page = doc[1]
        word = next(w for w in page.get_text('words') if w[4] == 'B' and w[1] < 110)
        page.add_redact_annot(pymupdf.Rect(word[:4]))
        page.apply_redactions()
        invalid = doc.tobytes()
    result = fp.analyse_pair(read_bytes(QP), invalid, '9701_s20_12', QP, MS)
    assert result['status'] == 'needs_review' and result['questions'] == []
    assert any(e['reason'] == 'missing_official_keys' and 1 in e['questions'] for e in result['exceptions'])


def test_page_cache_changes_work_count_without_changing_image_bytes():
    raw = read_bytes(QP)
    bundle = fp.analyse_pair(raw, read_bytes(MS), '9701_s20_12', QP, MS)
    regions = [r for q in bundle['questions'][:10] for r in q['regions']]
    baseline, old_count = fp.render_regions(raw, regions, reuse_pages=False)
    candidate, new_count = fp.render_regions(raw, regions, reuse_pages=True)
    assert candidate == baseline
    assert old_count == len(regions) and new_count == len({r['page'] for r in regions}) < old_count


def test_correct_cover_cannot_hide_another_papers_official_keys():
    import pymupdf
    with pymupdf.open(stream=read_bytes(MS), filetype='pdf') as correct, pymupdf.open(stream=read_bytes(PHYSICS_MS), filetype='pdf') as wrong:
        mixed = pymupdf.open()
        mixed.insert_pdf(correct, from_page=0, to_page=0)
        mixed.insert_pdf(wrong, from_page=1)
        invalid = mixed.tobytes()
        mixed.close()
    with pytest.raises(ValueError, match='identity'):
        fp.analyse_pair(read_bytes(QP), invalid, '9701_s20_12', QP, MS)


def test_image_body_with_native_numbers_is_flagged_for_page_review():
    import pymupdf
    with pymupdf.open(stream=read_bytes(QP), filetype='pdf') as doc:
        page = doc[1]
        anchors = [w for w in page.get_text('words') if w[4] in ['1', '2', '3', '4'] and 45 < w[0] < 55]
        image, rect = page.get_pixmap(dpi=144).tobytes('png'), page.rect
        doc.delete_page(1)
        page = doc.new_page(pno=1, width=rect.width, height=rect.height)
        page.insert_image(rect, stream=image)
        for word in anchors:
            page.insert_text((word[0], word[3] - 2), word[4], fontsize=11)
        invalid = doc.tobytes()
    result = fp.analyse_pair(invalid, read_bytes(MS), '9701_s20_12', QP, MS)
    assert result['status'] == 'needs_review'
    assert result['qp_pages'][1]['status'] == 'image_body_needs_review'
    assert any(e.get('page') == 2 for e in result['exceptions'])


def _installed_pair(tmp_path):
    vault = tmp_path / 'vault'
    vault.mkdir()
    qp = copy_to_vault(canonical_path(QP), vault)
    ms = copy_to_vault(canonical_path(MS), vault)
    return vault, qp.relative_to(vault).as_posix(), ms.relative_to(vault).as_posix()


def test_directory_adapter_retarget_cannot_redirect_writes_into_library(tmp_path, monkeypatch):
    vault, qp, ms = _installed_pair(tmp_path)
    allowed = tmp_path / 'preparation'
    allowed.mkdir()
    adapter = tmp_path / 'adapter'
    adapter.symlink_to(allowed, target_is_directory=True)
    original = fp.analyse_pair
    def retarget(*args, **kwargs):
        result = original(*args, **kwargs)
        adapter.unlink()
        adapter.symlink_to(vault / 'Library', target_is_directory=True)
        return result
    monkeypatch.setattr(fp, 'analyse_pair', retarget)
    fp.prepare(vault, qp, ms, adapter / 'output')
    assert not (vault / 'Library/output').exists()
    assert (allowed / 'output/COMPLETE').is_file()


def test_verification_rejects_media_parent_symlink(tmp_path):
    vault, qp, ms = _installed_pair(tmp_path)
    output = tmp_path / 'output'
    fp.prepare(vault, qp, ms, output)
    external = tmp_path / 'moved-qp'
    (output / 'qp').rename(external)
    (output / 'qp').symlink_to(external, target_is_directory=True)
    with pytest.raises(ValueError, match='symlink'):
        fp.verify_bundle(output)


def test_hash_valid_manifest_cannot_omit_its_question_images(tmp_path):
    import json
    vault, qp, ms = _installed_pair(tmp_path)
    output = tmp_path / 'output'
    bundle = fp.prepare(vault, qp, ms, output)
    bundle['media'] = {}
    raw = json.dumps(bundle).encode()
    (output / 'bundle.json').write_bytes(raw)
    (output / 'COMPLETE').write_text(fp.sha(raw))
    with pytest.raises(ValueError, match='media'):
        fp.verify_bundle(output)
