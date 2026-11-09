"""OCR marker preparation from registered PDFs and existing disposable worker aids."""
import importlib.util
import hashlib
import json
from pathlib import Path
import shutil

import pytest
from library_assets import read_bytes

ROOT = Path(__file__).parents[2]
CACHE = ROOT / 'Work/Workers/extraction/ocr-cache'
MODULE = Path(__file__).parents[1] / 'extraction/topical_ocr.py'
spec = importlib.util.spec_from_file_location('topical_ocr', MODULE)
ocr = importlib.util.module_from_spec(spec)
if MODULE.exists():
    spec.loader.exec_module(ocr)

P1 = 'asset:legacy-b47a42bc4290a20b9604d211'
P2 = 'asset:legacy-8f2f9994d0b9bb3f82615c58'
CRACK1 = 'asset:legacy-fc98465053396209207e8eff'
CRACK2 = 'asset:legacy-a17b0a2a2c3378405e7f563e'
EXAM = 'asset:legacy-6fc87cbf2a4250110b70efa4'
SMALL_SHA = 'be884bdfc5ff0ad6897292af2d2a14ec656ea04d0c703ee1df319656381cc26c'

def detect(asset, cache=CACHE, raw=None):
    assert hasattr(ocr, 'find_anchors_from_cache'), 'hash-bound OCR detector is missing'
    return ocr.find_anchors_from_cache(read_bytes(asset) if raw is None else raw, asset, cache)

@pytest.mark.parametrize('asset,page,qid', [(P1,6,'9702_s23_12_q1'), (P2,6,'9702_s23_22_q1'),
                                        (EXAM,3,'9701_s17_21_q1')])
def test_complete_ocr_codes_provide_only_provisional_whole_question_markers(asset,page,qid):
    result=detect(asset)
    found=[a for a in result['anchors'] if a['page']==page]
    assert found[0]['official_qid']==qid
    assert 0 < found[0]['top'] < found[0]['bottom'] < 1
    assert found[0]['part']==''
    assert result['segmentation_status']=='provisional'
    assert result['teaching_approved'] is False
    assert result['validated_ocr_pages']==list(range(1,result['provenance']['total_pages']+1))
    assert any(i['reason']=='unreviewed_ocr' for i in result['issues'])

@pytest.mark.parametrize('asset', [CRACK1,CRACK2])
def test_crack_source_headers_do_not_invent_missing_official_question_numbers(asset):
    result=detect(asset)
    found=[a for a in result['anchors'] if a['page']==4]
    assert found
    assert all(a['official_qid'] is None for a in found)
    assert any(i['reason']=='missing_question_identity' for i in result['issues'])

def test_crack_paper_headers_are_fragments_not_proof_of_whole_question_boundaries():
    result=detect(CRACK2)
    assert result['candidate_unit']=='page_fragment'
    assert all(a['candidate_unit']=='page_fragment' for a in result['anchors'])
    assert any(i['reason']=='source_header_not_whole_question_proof' for i in result['issues'])

@pytest.mark.parametrize('asset,course',[(P2,'9702'),(CRACK2,'9701')])
def test_hash_bound_ocr_profile_exposes_source_course_for_caller_validation(asset,course):
    assert detect(asset)['source_course']==course

@pytest.mark.parametrize('asset,pages', [(P2,[30,275,354]),(P1,[441,686]),
                                      (CRACK1,[11,22,23]),(CRACK2,[6,14,15]),(EXAM,[774,775,992])])
def test_answer_sections_and_declared_answer_page_ranges_never_emit_question_anchors(asset,pages):
    result=detect(asset)
    assert all(result['page_roles'][str(p)]=='answer' for p in pages)
    assert not [a for a in result['anchors'] if a['page'] in pages]

def test_rotated_physics_ocr_boxes_use_original_displayed_pdf_frame():
    first=next(a for a in detect(P2)['anchors'] if a['page']==40)
    assert first['top']==pytest.approx(.1467,abs=.004)
    assert first['evidence_bbox'][1]==pytest.approx(123.48,abs=4)
    assert first['coordinate_system']=='original_pdf_display_top_left'

def test_different_source_bytes_or_unsupported_id_fail_closed():
    result=detect(CRACK2,raw=read_bytes(CRACK2)+b' ')
    assert result['anchors']==[]
    assert any(i['reason']=='unsupported_ocr_source' for i in result['issues'])
    result=ocr.find_anchors_from_cache(read_bytes(CRACK2),'asset:unknown',CACHE)
    assert result['anchors']==[]

@pytest.mark.parametrize('mutation',['missing_page','changed_sidecar','changed_manifest'])
def test_cache_drift_discards_all_anchors_instead_of_using_a_valid_prefix(tmp_path,mutation):
    target=tmp_path/'cache'/SMALL_SHA
    shutil.copytree(CACHE/SMALL_SHA,target)
    if mutation=='missing_page':
        (target/'p0079.json').unlink()
    elif mutation=='changed_sidecar':
        page=json.loads((target/'p0079.json').read_text())
        page['geometry']['page_rotation']=90
        (target/'p0079.json').write_text(json.dumps(page))
    else:
        manifest=json.loads((target/'manifest.json').read_text())
        manifest['total_pages']=78
        (target/'manifest.json').write_text(json.dumps(manifest))
    result=detect(CRACK2,tmp_path/'cache')
    assert result['anchors']==[]
    assert result['validated_ocr_pages']==[]
    assert any(i['reason']=='invalid_ocr_cache' for i in result['issues'])

@pytest.mark.parametrize('mutation',['low_confidence','unmappable_geometry'])
def test_validly_bound_cache_revision_still_checks_anchor_confidence_and_page_geometry(tmp_path,monkeypatch,mutation):
    # Synthetic invalid derivative stays disposable; source PDF bytes are real.
    target=tmp_path/'cache'/SMALL_SHA
    shutil.copytree(CACHE/SMALL_SHA,target)
    data=json.loads((target/'p0004.json').read_text())
    if mutation=='low_confidence':
        next(line for line in data['lines'] if line['text']=='9701/May/June/2023/21')['confidence']=.5
    else:
        data['geometry']['page_rotation']=90
    raw=json.dumps(data).encode()
    (target/'p0004.json').write_bytes(raw)
    manifest=json.loads((target/'manifest.json').read_text())
    manifest['pages']['4']['sha256']=hashlib.sha256(raw).hexdigest()
    raw=json.dumps(manifest).encode()
    (target/'manifest.json').write_bytes(raw)
    source_sha,_,kind,first=ocr._PROFILES[CRACK2]
    monkeypatch.setitem(ocr._PROFILES,CRACK2,(source_sha,hashlib.sha256(raw).hexdigest(),kind,first))
    result=detect(CRACK2,tmp_path/'cache')
    if mutation=='low_confidence':
        assert not [a for a in result['anchors'] if a['page']==4]
        assert any(i['reason']=='low_ocr_anchor_confidence' for i in result['issues'])
        assert result['teaching_approved'] is False
    else:
        assert result['anchors']==[]
        assert result['validated_ocr_pages']==[]
        assert 'geometry' in result['issues'][0]['detail']
