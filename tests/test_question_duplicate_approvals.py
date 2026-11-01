"""Independent immutable approvals of the same pair are idempotent."""
import copy
import hashlib
import json

import pytest

from test_question_duplicates import IMAGE, KC, REVIEW, register, setup_review
from tutorlib import packs, question_duplicates, store
from tutorlib.asset_library import write_asset

SECOND_REVIEW = 'Library/Courses/9702/Questions/Reviews/equivalence-second.json'


def _register_second(root, review):
    write_asset(root, SECOND_REVIEW, json.dumps(review).encode(),
                metadata={'kind': 'question_duplicate_review', 'course': '9702'})


@pytest.mark.parametrize('location', ['same-document', 'independent-resource'])
def test_repeated_valid_approval_keeps_the_reviewed_selection(tmp_path, location):
    root, pack_path, review = setup_review(tmp_path)
    pack_before = pack_path.read_bytes()
    if location == 'same-document':
        review['reviews'].append(copy.deepcopy(review['reviews'][0]))
    register(root, review)
    first_before = (root / REVIEW).read_bytes()
    catalog_before = json.loads((root / 'Library/catalog.json').read_text())['assets']
    if location == 'independent-resource':
        second = copy.deepcopy(review)
        second['reviews'][0]['reviewer'] = 'Second independent source reviewer'
        second['reviews'][0]['evidence'] = 'Independent inspection confirms the same exact source-bound pair.'
        _register_second(root, second)

    content = packs.Packs(store.Vault(root))

    assert [row['id'] for row in content.items_for(KC)] == ['keep']
    assert not content.selection_conflicts and not content.duplicate_reviews.errors
    assert content.aliases_for(content.items_for(KC)[0]) == {'keep', 'drop'}
    assert pack_path.read_bytes() == pack_before and (root / REVIEW).read_bytes() == first_before
    catalog_after = json.loads((root / 'Library/catalog.json').read_text())['assets']
    assert all(catalog_after[key] == value for key, value in catalog_before.items())


def test_opposing_valid_approvals_still_preserve_both_candidates(tmp_path):
    root, pack_path, review = setup_review(tmp_path)
    register(root, review)
    second = copy.deepcopy(review)
    row = second['reviews'][0]
    row['keep'], row['drop'] = row['drop'], row['keep']
    row['reviewer'] = 'Second independent source reviewer'
    _register_second(root, second)
    before = pack_path.read_bytes()

    content = packs.Packs(store.Vault(root))

    assert {row['id'] for row in content.items_for(KC)} == {'keep', 'drop'}
    assert content.selection_conflicts
    assert 'conflicting duplicate review decisions' in content.duplicate_reviews.errors
    assert pack_path.read_bytes() == before


def test_distinct_keeps_for_one_drop_still_fail_closed(tmp_path):
    root, pack_path, review = setup_review(tmp_path)
    pack = json.loads(pack_path.read_text())
    third = copy.deepcopy(pack['items'][0])
    third['id'] = 'other-keep'
    pack['items'].append(third)
    pack_path.write_text(json.dumps(pack))
    register(root, review)
    second = copy.deepcopy(review)
    second['reviews'][0]['keep'] = {'id': third['id'], 'sha256': question_duplicates.fingerprint(third, root)}
    _register_second(root, second)

    content = packs.Packs(store.Vault(root))

    assert {row['id'] for row in content.items_for(KC)} == {'keep', 'drop', 'other-keep'}
    assert content.selection_conflicts
    assert 'conflicting duplicate review decisions' in content.duplicate_reviews.errors


def test_fresh_review_of_revised_source_coexists_with_preserved_old_review(tmp_path):
    root, pack_path, review = setup_review(tmp_path)
    register(root, review)
    old_review = (root / REVIEW).read_bytes()
    old_source = (root / IMAGE).read_bytes()
    old_records = json.loads((root / 'Library/catalog.json').read_text())['assets']
    image_bytes = b'independently reviewed source revision'
    image = write_asset(root, 'Library/Courses/9702/Questions/Media/question-v2.png', image_bytes)
    pack = json.loads(pack_path.read_text())
    pack['items'][1]['image'] = image
    pack['items'][1]['options']['A'] = 'one-half V'
    pack_path.write_text(json.dumps(pack))
    second = copy.deepcopy(review)
    second['reviews'][0]['drop']['sha256'] = question_duplicates.fingerprint(pack['items'][1], root)
    second['reviews'][0]['source'] = {'asset': image, 'sha256': hashlib.sha256(image_bytes).hexdigest()}
    _register_second(root, second)
    new_pack = pack_path.read_bytes()

    content = packs.Packs(store.Vault(root))

    assert [row['id'] for row in content.items_for(KC)] == ['keep']
    assert not content.selection_conflicts
    assert any('stale complete record fingerprint' in error for error in content.duplicate_reviews.errors)
    assert (root / REVIEW).read_bytes() == old_review and (root / IMAGE).read_bytes() == old_source
    records = json.loads((root / 'Library/catalog.json').read_text())['assets']
    assert all(records[key] == value for key, value in old_records.items())
    assert pack_path.read_bytes() == new_pack
