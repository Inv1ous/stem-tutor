"""Fixed registered CAIE public origins do not grant question/teaching approval."""
import hashlib
import json
from pathlib import Path
import sys

import pymupdf
import pytest
from library_assets import copy_to_vault, read_bytes

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'extraction'))
import caie_written_profile as profile

# Independent frozen pins of the 28 originals inspected for this expansion.
SOURCE_PINS = {'9701_s19_22': ['cc49218fcf765acb5c526754b5a85c3c86ab7f3840a5b137ccd52b4f1d888934', 12], '9701_w19_22': ['9f565167380a5825c5b5eebf2464b2cab0c2a49a90503a8c6871b325f3473e6d', 16], '9701_s20_22': ['630b2d0c535a722c20dd7198a1c10d2811164ae01d5764b0deed2d451e8407ea', 12], '9701_w20_22': ['4c224519910c0384a85e1eadcfd898643a1074fac938696fc9003e29bed40e5e', 16], '9701_s21_22': ['e0beee19067773793525cce6304f38ba0af441b154770b74a29862fd3b3dbe90', 12], '9701_w21_22': ['69e73c0843ae5f54de89a2d30527ef6b07ce307b1b27fb676dcfdaeccd97b792', 12], '9701_s22_22': ['b448d04ca4638853cc80f63e6d594cc185004f0ff66abece3ff6376d90613193', 16], '9701_w22_22': ['ab053120a1017025f0d45a0765a226d8fcde295b758ba24ee1caf916b110c290', 16], '9701_s23_22': ['c1a1c180a1718523abd06f9162af5935e68f0ab790a0d247bf49f2f351786a6d', 16], '9701_w23_22': ['8696ca0cfe71e48f70b783502eb0a804b9241b73a7055742e9a2048af32ff0af', 20], '9701_s24_22': ['02463479abb9dd19ef2bbc8297bf832f083bc6a52b95977119c3a7260d69580c', 16], '9701_w24_22': ['4645f1eb7930632a7feee5c3327c1f89d6fa9b2beb0ce4bace4be03728298ae6', 16], '9701_s25_22': ['dea8f17527e2bd62bcca8be4c885f0bb4fe136ee4b7c3f7049129efc6d73ddd5', 16], '9701_w25_22': ['ef853c40beacdd8bb12bd59eca7015d08d837100c200866d00cb5bd2acc785c9', 16], '9702_s19_22': ['30d62fa91f29c021b2aeb9804be215707d69b4e7f913d6f601bccec73ac48f4d', 16], '9702_w19_22': ['310cbce9d0150976a515fd45855017170320097071207d6bbc988c639bbf955d', 16], '9702_s20_22': ['eb7600b15093c31a43721a22e1be0d50107ef56b82aeca224232882a6fe3d71e', 16], '9702_w20_22': ['e92b3f4f78e2c3e43674906c75298081e0b40dec9ba54eb7b7b66611779690f3', 20], '9702_s21_22': ['fc0839d3d36878a0d85d82fab53e637f901afe79e593eef6c4978a3e851e05c9', 16], '9702_w21_22': ['649bb30eb335b1446b1a477fe8f94c858b01f6e8bbd3ab980c544aede58b425a', 20], '9702_s22_22': ['17041e391fee955573e445dc9ffa67fd4dea8e71c771c1ef68a3dba0d6471565', 16], '9702_w22_22': ['9185f3c875444208de516f356649533227af617f0eeefd3e5934597c254b5220', 16], '9702_s23_22': ['24c8527582d3509aeaee202a0e45be518e38b6ee37c496d71d260cb163ba5cab', 20], '9702_w23_22': ['837fd4b472bb5b4274cb9b12549e4fa574c218452de70b534969f3397cc26a22', 16], '9702_s24_22': ['fe32f083bbe655738ca7765b3f45d7d5dadc7654727a3070f351fea88b963eaf', 16], '9702_w24_22': ['e24057974ae8d3296158da8a8b6de0ad228993fcb708554d6b5e4f2b4114e10e', 16], '9702_s25_22': ['cfd4d5d7d4ec756d6c534abe3b72240d4e12afbdb281622de343700df7cb0cfb', 20], '9702_w25_22': ['3e6384f2d529e7300023b8bb899f97ce50854005c4d5a52db1c9c40e2af3bd85', 16]}
OMITTED = {'9701_s21_22': [12], '9702_s21_22': [16], '9702_w22_22': [16], '9702_s23_22': [20], '9702_w24_22': [16], '9702_s25_22': [20], '9701_w24_22': [15]}
ORIGINAL_BASELINE_DIGESTS = {'9701_s24_22': 'd9b1aa1b17222a162a95c4a6ebab05c7e4b03fde0343979213bc1c2414ee2353', '9702_s24_22': '7422d9ac3bda08d1b5da3792e1159b994058bb76bd5e3645e2eb93e6581e12e2', '9702_s19_22': '437a8c3012b9a611b3ab78040915f855bca51c53c363736b0d8f80a2a82f4129'}


def reference(key, role='qp'):
    course, session, component = key.split('_')
    year = 2000 + int(session[1:])
    return f'Library/Courses/{course}/Sources/PastPapers/{course}/{year}/{session[0]}/{course}_{session}_{role}_{component}.pdf'


def exam(key):
    course, session, component = key.split('_')
    return {'course': course, 'year': 2000 + int(session[1:]), 'series': session[0], 'component': component}


@pytest.mark.parametrize('key', SOURCE_PINS)
def test_all_inspected_originals_have_fixed_authority_or_explicit_omission(key):
    raw = read_bytes(reference(key))
    digest, count = SOURCE_PINS[key]
    assert hashlib.sha256(raw).hexdigest() == digest
    with pymupdf.open(stream=raw, filetype='pdf') as doc:
        assert len(doc) == count
        assert profile._cover(doc, exam(key), 'qp')['exam'] == exam(key)
        assert profile._page_identity(doc, exam(key), 'qp') == []
        layout, _ = profile._public(doc)
        proofs, issues = profile._public_pixel_qualification(
            doc, exam(key), layout, {'reference': reference(key), 'sha256': digest})
        if key in OMITTED:
            assert key not in profile._PUBLIC_RASTER_BASELINES
            assert proofs == []
            assert issues == [{'source': 'qp', 'reason': 'unqualified_public_page_profile'}]
            if key == '9701_w24_22':
                mixed = layout[14]
                assert mixed['role'] == 'public_reference' and mixed['totals'][0]['marks'] == 17
                assert 'Suggest the role of reagent' in doc[14].get_text()
            else:
                assert [p['page'] for p in layout if p['role'] == 'unexplained_public_page'] == OMITTED[key]
        else:
            authority = profile._PUBLIC_RASTER_BASELINES[key]
            assert authority['source_reference'] == reference(key)
            assert authority['source_sha256'] == digest
            assert len(proofs) == len(authority['pages']) == count and not issues
            assert all(p['qualified'] and p['source_origin_match'] for p in proofs)
            for page, expected in zip(layout, authority['pages']):
                if page['role'] in ('cover', 'blank', 'public_reference'):
                    assert 'full' in expected
                if page['totals'] and page['role'] == 'question_or_continuation':
                    assert expected['total'] == page['totals'][0] and 'tail' in expected


def test_authority_is_exactly_the_inspected_finite_set_and_original_three_are_unchanged():
    assert set(profile._PUBLIC_RASTER_BASELINES) == set(SOURCE_PINS) - set(OMITTED)
    for key, digest in ORIGINAL_BASELINE_DIGESTS.items():
        assert hashlib.sha256(profile.canonical_bytes(profile._PUBLIC_RASTER_BASELINES[key])).hexdigest() == digest


def test_uninspected_origin_cannot_borrow_identical_layout():
    key = '9702_s22_22'
    with pymupdf.open(stream=read_bytes(reference(key)), filetype='pdf') as doc:
        layout, _ = profile._public(doc)
        proofs, issues = profile._public_pixel_qualification(
            doc, {**exam(key), 'year': 2026}, layout,
            {'reference': reference(key), 'sha256': SOURCE_PINS[key][0]})
    assert proofs == []
    assert issues == [{'source': 'qp', 'reason': 'unqualified_public_page_profile'}]


@pytest.mark.parametrize('key', ['9701_s19_22', '9701_s20_22', '9702_s22_22'])
def test_new_chemistry_and_physics_public_origins_remain_separate_from_question_approval(tmp_path, key):
    vault = tmp_path / 'vault'; vault.mkdir()
    for role in ('qp', 'ms'):
        copy_to_vault(reference(key, role), vault)
    bundle = profile.analyse(vault, reference(key), reference(key, 'ms'))
    assert bundle['public_pixel_proofs'] and all(p['qualified'] for p in bundle['public_pixel_proofs'])
    assert bundle['teaching_approved'] is False and bundle['mastery_certified'] is False
    if key in ('9701_s19_22', '9701_s20_22'):
        assert all('external_public_reference_unresolved' in q['hold_reasons'] for q in bundle['questions'])
        assert not bundle['paper_complete']


@pytest.mark.parametrize('fault', ['metadata', 'blank', 'post_total', 'margin', 'reference', 'cover', 'page_count'])
def test_new_origin_revisions_and_protected_area_mutations_stay_held(tmp_path, fault):
    from tutorlib.asset_library import write_asset
    key = '9702_s22_22'
    vault = tmp_path / 'vault'; vault.mkdir()
    copy_to_vault(reference(key, 'ms'), vault)
    raw = read_bytes(reference(key))
    with pymupdf.open(stream=raw, filetype='pdf') as doc:
        original_pixels = [p.get_pixmap(dpi=72, alpha=False).samples for p in doc] if fault == 'metadata' else None
        if fault == 'metadata':
            doc.set_metadata({**doc.metadata, 'keywords': 'unqualified metadata-only revision'})
        elif fault == 'page_count':
            doc.new_page(width=596, height=842)
        else:
            page_index, point = {'blank': (2, (100, 300)), 'post_total': (4, (100, 700)),
                                 'margin': (4, (4, 300)), 'reference': (1, (100, 800)),
                                 'cover': (0, (100, 700))}[fault]
            doc[page_index].insert_text(point, 'SECRET extra source content', fontsize=10)
        changed = doc.tobytes()
    assert hashlib.sha256(changed).hexdigest() != SOURCE_PINS[key][0]
    invalid = 'Library/InvalidFixtures/9702_s22_qp_22.pdf'
    write_asset(vault, invalid, changed, metadata={'purpose': 'disposable invalid authority fixture'})
    if original_pixels is not None:
        with pymupdf.open(stream=changed, filetype='pdf') as doc:
            assert original_pixels == [p.get_pixmap(dpi=72, alpha=False).samples for p in doc]
    bundle = profile.analyse(vault, invalid, reference(key, 'ms'))
    expected_reason = 'unqualified_public_page_count' if fault == 'page_count' else 'unqualified_public_page_content'
    assert any(issue['reason'] == expected_reason for issue in bundle['exceptions'])
    assert all(expected_reason in q['hold_reasons'] for q in bundle['questions'])
    assert bundle['paper_complete'] is False
    if fault == 'metadata':
        assert all(p['observed'] == p['expected'] and not p['source_origin_match'] and not p['qualified']
                   for p in bundle['public_pixel_proofs'])
    elif fault != 'page_count':
        field = {'blank': 'full', 'post_total': 'tail', 'margin': 'margin',
                 'reference': 'full', 'cover': 'full'}[fault]
        proof = bundle['public_pixel_proofs'][page_index]
        assert proof['observed'][field] != proof['expected'][field]
        assert proof['observed']['objects'] != proof['expected']['objects']

