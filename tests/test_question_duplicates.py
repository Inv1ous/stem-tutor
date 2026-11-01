"""Source-bound duplicate approvals never rewrite or broadly normalize questions."""
import copy
import hashlib
import json

import pytest

from fixtures import make_vault
from tutorlib import packs, store
from tutorlib.asset_library import write_asset
from tutorlib import question_duplicates as duplicates

KC, SUB = '9702-2.1.1', '9702-2.1'
IMAGE = 'Library/Courses/9702/Questions/Media/question.png'
REVIEW = 'Library/Courses/9702/Questions/Reviews/equivalence.json'


def setup_review(tmp_path):
    root = make_vault(tmp_path)
    # The fixture paper references must remain catalog-resolvable too.
    for kind in ('qp', 'ms'):
        name = f'9702_s23_{kind}_22.pdf'
        write_asset(root, 'Library/Courses/9702/Sources/Papers/' + name, b'paper', aliases=['Papers/9702/' + name])
    image_id = write_asset(root, IMAGE, b'reviewed fraction image', aliases=['Assets/mcq/question.png'])
    one = {'id': 'keep', 'kind': 'mcq', 'kcs': [KC], 'marks': 1, 'difficulty': 3,
           'source': {'type': 'past', 'qid': '9702_w24_13_q34'}, 'stem': 'A fixed resistor.',
           'options': {'A': 'V/2', 'B': '2V'}, 'answer': 'B'}
    two = copy.deepcopy(one)
    two.update(id='drop', image='Assets/mcq/question.png', options={'A': 'V 2 1', 'B': '2V'})
    path = root / '.tutor/packs/v1/specs/9702/packs/9702-2.1.json'
    pack = json.loads(path.read_text()); pack['items'] = [one, two]; path.write_text(json.dumps(pack))
    review = {'format_version': 1, 'reviews': [{'verdict': 'equivalent', 'reviewed': True,
              'identity': '9702_w24_13_q34', 'kcs': [KC],
              'keep': {'id': 'keep', 'sha256': duplicates.fingerprint(one, root)},
              'drop': {'id': 'drop', 'sha256': duplicates.fingerprint(two, root)},
              'source': {'asset': image_id, 'sha256': hashlib.sha256(b'reviewed fraction image').hexdigest()},
              'reviewer': 'independent source reviewer', 'evidence': 'Image A is one-half V; OCR V 2 1 means the same; both key B.'}]}
    return root, path, review


def register(root, review):
    write_asset(root, REVIEW, json.dumps(review).encode(), metadata={'kind': 'question_duplicate_review', 'course': '9702'})


def test_matching_source_review_filters_only_explicit_drop_and_preserves_bytes(tmp_path):
    root, path, review = setup_review(tmp_path)
    before = path.read_bytes()
    initial = packs.Packs(store.Vault(root))
    assert len(initial.items_for(KC)) == 2 and initial.selection_conflicts
    register(root, review)
    content = packs.Packs(store.Vault(root))
    assert [i['id'] for i in content.items_for(KC)] == ['keep']
    assert not content.selection_conflicts
    assert content.aliases_for(content.items_for(KC)[0]) == {'keep', 'drop'}
    assert path.read_bytes() == before


@pytest.mark.parametrize('change', ['option', 'source', 'identity', 'context', 'fingerprint', 'verdict', 'evidence', 'missing_keep'])
def test_stale_malformed_or_crosscontext_review_cannot_suppress_conflict(tmp_path, change):
    root, path, review = setup_review(tmp_path)
    row = review['reviews'][0]
    if change == 'option':
        pack = json.loads(path.read_text()); pack['items'][1]['options']['A'] = '3V'; path.write_text(json.dumps(pack))
    elif change == 'source':
        (root / IMAGE).write_bytes(b'stale image')
    elif change == 'identity':
        row['identity'] = '9702_w24_13_q35'
    elif change == 'context':
        row['kcs'] = ['9702-2.1.4']
    elif change == 'fingerprint':
        row['drop']['sha256'] = '0' * 64
    elif change == 'verdict':
        row['verdict'] = 'probably equivalent'
    elif change == 'evidence':
        row['evidence'] = ''
    else:
        row['keep']['id'] = 'absent'
    register(root, review)
    if change == 'source':
        # Restore catalog validation so pack loading succeeds; the source-bound
        # review must independently reject its old source digest.
        catalog = root / 'Library/catalog.json'
        data = json.loads(catalog.read_text())
        for asset in data['assets'].values():
            if asset['path'] == IMAGE:
                asset['sha256'] = hashlib.sha256(b'stale image').hexdigest()
        catalog.write_text(json.dumps(data))
    content = packs.Packs(store.Vault(root))
    assert len(content.items_for(KC)) == 2 and content.selection_conflicts


def test_record_fingerprint_survives_only_declared_asset_rehome(tmp_path):
    root, _, review = setup_review(tmp_path)
    register(root, review)
    before = packs.Packs(store.Vault(root)).items_for(KC)
    assert [i['id'] for i in before] == ['keep']
    catalog = root / 'Library/catalog.json'
    data = json.loads(catalog.read_text())
    new = 'Library/Courses/9702/Questions/Media/rehome.png'
    for asset in data['assets'].values():
        if asset['path'] == IMAGE:
            asset['aliases'].append(IMAGE); asset['path'] = new
    (root / IMAGE).rename(root / new)
    catalog.write_text(json.dumps(data))
    content = packs.Packs(store.Vault(root))
    assert [i['id'] for i in content.items_for(KC)] == ['keep']


def test_unrelated_reviewed_source_does_not_authorize_suppression(tmp_path):
    root, _, review = setup_review(tmp_path)
    unrelated = write_asset(root, 'Library/Courses/9702/Questions/Media/unrelated.png', b'unrelated source')
    review['reviews'][0]['source'] = {'asset': unrelated, 'sha256': hashlib.sha256(b'unrelated source').hexdigest()}
    register(root, review)
    content = packs.Packs(store.Vault(root))
    assert len(content.items_for(KC)) == 2 and content.selection_conflicts
    assert 'not bound' in str(content.duplicate_reviews.errors)


def test_tampered_registered_review_does_not_authorize_suppression(tmp_path):
    root, _, review = setup_review(tmp_path)
    register(root, review)
    content = packs.Packs(store.Vault(root))
    (root / REVIEW).write_text('{}')
    assert len(content.items_for(KC)) == 2 and content.selection_conflicts
    assert content.duplicate_reviews.errors


def test_other_conflict_survives_an_exact_reviewed_pair(tmp_path):
    root, path, review = setup_review(tmp_path)
    pack = json.loads(path.read_text())
    third = copy.deepcopy(pack['items'][0]); third.update(id='different', answer='A')
    pack['items'].append(third); path.write_text(json.dumps(pack))
    register(root, review)
    content = packs.Packs(store.Vault(root))
    assert {i['id'] for i in content.items_for(KC)} == {'keep', 'different'}
    assert content.selection_conflicts[0]['ids'] == ['keep', 'different']


@pytest.mark.parametrize('field', ['id', 'answer', 'options', 'scheme', 'ref', 'stem'])
def test_complete_fingerprint_never_normalizes_protected_content_or_prose(tmp_path, field):
    root, _, _ = setup_review(tmp_path)
    alias, canonical = 'Assets/mcq/question.png', IMAGE
    if field == 'options':
        one, two = {'options': {'A': alias}}, {'options': {'A': canonical}}
    elif field == 'scheme':
        one, two = {'scheme': [{'point': alias}]}, {'scheme': [{'point': canonical}]}
    elif field == 'ref':
        one, two = {'source': {'ref': alias}}, {'source': {'ref': canonical}}
    else:
        one, two = {field: alias}, {field: canonical}
    assert duplicates.fingerprint(one, root) != duplicates.fingerprint(two, root)
