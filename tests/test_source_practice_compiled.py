"""Exact registered Examinent keys and immutable source occurrence boundaries."""
import copy
import hashlib
import json
from pathlib import Path
import shutil
import sys

import pymupdf
import pytest
from library_assets import canonical_path, copy_to_vault

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'extraction'))
import source_practice as build
import topical_fastpath as topical
from tutorlib.asset_library import AssetLibrary, write_asset
from tutorlib.source_practice import Collection

SOURCE = 'asset:legacy-94c51c9bcbba526ad8f64b38'


@pytest.fixture(scope='module')
def source(tmp_path_factory):
    root = tmp_path_factory.mktemp('compiled-source')
    vault = root / 'vault'; vault.mkdir()
    path = copy_to_vault(canonical_path(SOURCE), vault)
    catalog_path = vault / 'Library/catalog.json'
    catalog = json.loads(catalog_path.read_bytes())
    key = next(k for k, v in catalog['assets'].items() if v['path'] == path.relative_to(vault).as_posix())
    catalog['assets'][SOURCE.removeprefix('asset:')] = catalog['assets'].pop(key)
    catalog_path.write_text(json.dumps(catalog))
    library = AssetLibrary(vault)
    raw = library.read(SOURCE)
    fresh = topical.analyse_source(raw, '9701', SOURCE, source_path=library.record(SOURCE)['path'])
    return root, vault, raw, fresh


def compiled(source):
    from caie_compiled_profile import compile_mcq
    return compile_mcq(source[2], copy.deepcopy(source[3]))


def test_exact_real_source_keys_match_identity_and_exclude_unsupported_occurrences(source):
    result = compiled(source)
    assert result['key_rows'] == 1699
    assert len(result['items']) == 1273
    assert len(result['occurrence_exclusions']) == 426
    assert [(q['label'], q['official_qid'], q['answer']) for q in result['items'][:3]] == [
        ('1', '9701_m24_12_q1', 'D'), ('2', '9701_m23_12_q12', 'C'), ('3', '9701_s23_11_q1', 'B')]
    assert all(q['marks'] == 1 and q['kcs'] == [] and q['mastery_certified'] is False
               and int(q['official_qid'].split('_q')[1]) <= 30 for q in result['items'])
    exclusions = {q['label']: q for q in result['occurrence_exclusions']}
    assert exclusions['14']['official_qid'] == '9701_w20_12_q31'
    assert exclusions['14']['reason'] == 'missing_authenticated_shared_response_context'
    assert exclusions['1699']['reason'] == 'public_appendix_contamination'
    assert all(r['page'] < 699 for q in result['items'] for r in q['regions'] + q['context_regions'])
    assert [p['role'] for p in result['pages'][:6]] == ['front_matter'] * 6


def test_private_key_crop_contains_only_its_original_row_in_both_columns(source):
    result = compiled(source)
    with pymupdf.open(stream=source[2], filetype='pdf') as doc:
        for q in result['items']:
            assert len(q['mark_scheme_regions']) == 1
            region = q['mark_scheme_regions'][0]; page = doc[region['page'] - 1]
            box = region['box']
            text = page.get_text(clip=pymupdf.Rect(box[0]*page.rect.width, box[1]*page.rect.height,
                                                  box[2]*page.rect.width, box[3]*page.rect.height))
            import re
            assert re.findall(r'\b[ABCD]\b', text) == [q['answer']]
            assert re.findall(r'9701_[msw]\d{2}_qp_\d{2}', text) == [q['official_qid'].rsplit('_q', 1)[0].replace('_12', '_qp_12').replace('_11', '_qp_11').replace('_13', '_qp_13')]


@pytest.mark.parametrize('fault', ['answer', 'qid', 'missing'])
def test_independent_literal_key_disagreement_or_missing_row_fails_closed(source, monkeypatch, fault):
    import caie_compiled_profile as profile
    original = profile._serialized_rows
    def altered(raw):
        rows = original(raw)
        if fault == 'missing': return rows[1:]
        rows[0] = (rows[0][0], '9701_m24_12_q2' if fault == 'qid' else rows[0][1],
                   'A' if fault == 'answer' else rows[0][2])
        return rows
    monkeypatch.setattr(profile, '_serialized_rows', altered)
    with pytest.raises(ValueError, match='independent compiled key'):
        compiled(source)


def test_question_sn_qid_mismatch_and_unassigned_body_page_fail_closed(source):
    from caie_compiled_profile import compile_mcq
    for fault in ('qid', 'sn', 'review'):
        fresh = copy.deepcopy(source[3])
        if fault == 'qid': fresh['questions'][0]['official_qid'] = '9701_m24_12_q2'
        elif fault == 'sn': fresh['questions'][0]['label'] = '2'
        else: fresh['review_pages'].append({'page': 9, 'reason': 'unanchored'})
        with pytest.raises(ValueError): compile_mcq(source[2], fresh)


def selected_collection(vault, row):
    row = copy.deepcopy(row)
    qid = row['official_qid']
    row.update(id=qid, canonical_id=qid, kcs=[], source_verified=True, mastery_certified=False,
               question_media=[], context_media=[], mark_scheme_media=[], source='original native source',
               title='Original', course='9701')
    manifest = {'schema_version': 1, 'mastery_certified': 0, 'items': [row]}
    raw = json.dumps(manifest).encode(); digest = hashlib.sha256(raw).hexdigest()
    ref = 'Library/SourcePractice/Releases/' + digest + '.json'
    write_asset(vault, ref, raw)
    pointer = vault / '.tutor/source_practice/CURRENT'; pointer.parent.mkdir(parents=True, exist_ok=True)
    pointer.write_text(ref + '\n')
    return Collection(vault), raw


def test_same_key_canonical_reuse_preserves_resource_and_exclusions_do_not_hold_native(source, tmp_path):
    from caie_compiled_profile import reuse_verified
    result = compiled(source); vault = tmp_path / 'vault'; vault.mkdir()
    row = result['items'][0]
    collection, original = selected_collection(vault, row)
    new, reused, held = reuse_verified([row], collection)
    assert new == [] and held == []
    assert reused[0]['canonical_id'] == '9701_m24_12_q1'
    assert reused[0]['occurrence_id'] == row['id']
    assert AssetLibrary(vault).read(collection.release) == original
    excluded = result['occurrence_exclusions'][0]
    assert excluded['official_qid'] and 'id' not in excluded
    other = copy.deepcopy(row); other['answer'] = 'A'
    new, reused, held = reuse_verified([other], collection)
    assert new == [] and reused == [] and held[0]['id'] == row['official_qid']


@pytest.fixture(scope='module')
def prepared(source):
    output = source[0] / 'preparation'
    topical.prepare(source[1], SOURCE, '9701', output, dpi=72)
    return output


def test_full_registered_replay_original_pixels_and_private_appendix(source, prepared, monkeypatch):
    monkeypatch.setattr(build, 'WORKERS', source[0] / 'no-workers')
    result = build.verify(source[1], prepared)
    assert len(result['items']) == 1273 and not result['held']
    assert len(result['occurrence_exclusions']) == 426
    assert result['key_extractors'] == ['pymupdf_spatial', 'pypdf_serialized']
    assert all(q['question_media'] and q['mark_scheme_media'] for q in result['items'])
    for q in result['items']:
        assert all(result['media'][m]['region']['page'] < 699 for m in q['question_media'] + q['context_media'])
        assert all(result['_pixels'][m] for m in q['question_media'] + q['mark_scheme_media'])


@pytest.mark.parametrize('fault', ['question', 'media'])
def test_resealed_public_question_or_media_tampering_rejected(source, prepared, tmp_path, monkeypatch, fault):
    monkeypatch.setattr(build, 'WORKERS', source[0] / 'no-workers')
    output = tmp_path / 'tampered'; shutil.copytree(prepared, output)
    bundle = json.loads((output / 'bundle.json').read_bytes())
    if fault == 'question': bundle['questions'][0]['official_qid'] = '9701_m24_12_q2'
    else:
        name = bundle['questions'][0]['question_media'][0]
        from PIL import Image
        with Image.open(output / name) as image:
            image.putpixel((0, 0), (0, 0, 0)); image.save(output / name)
        data = (output / name).read_bytes()
        bundle['media'][name].update(sha256=hashlib.sha256(data).hexdigest(), bytes=len(data))
    raw = json.dumps(bundle).encode(); (output / 'bundle.json').write_bytes(raw)
    (output / 'COMPLETE').write_text(hashlib.sha256(raw).hexdigest())
    with pytest.raises(ValueError): build.verify(source[1], output)


def test_reuse_keeps_actual_verified_native_media_and_excluded_context_question(source, tmp_path, monkeypatch):
    from caie_compiled_profile import reuse_verified
    from test_source_practice import install
    monkeypatch.setattr(build, 'WORKERS', tmp_path / 'no-workers')
    vault, output = install(tmp_path)
    build.publish(vault, [output], expected_current=None)
    existing = Collection(vault)
    release_bytes = AssetLibrary(vault).read(existing.release)
    original = existing.question('9701_s19_11_q1')
    assert original['question_media']
    result = compiled(source)
    row = next(q for q in result['items'] if q['official_qid'] == '9701_s19_11_q1')
    new, reused, held = reuse_verified([row], existing)
    assert not new and not held and reused[0]['existing_release'] == existing.release
    assert existing.question('9701_s19_11_q1') == original
    assert AssetLibrary(vault).read(existing.release) == release_bytes
    assert any(q['official_qid'] == '9701_s19_11_q31' for q in result['occurrence_exclusions'])
    assert existing.question('9701_s19_11_q31')['source_verified'] is True
