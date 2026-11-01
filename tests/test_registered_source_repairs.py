"""Synthetic repair records establish gate mechanics, never content approval."""
import json
import copy
import hashlib

import pytest
from tutorlib.asset_library import AssetLibrary, write_asset
from tutor_workers.source_repairs import overlay


def setup(tmp_path, binding=True):
    vault = tmp_path / 'vault'
    vault.mkdir()
    image = 'Library/Courses/S/Questions/image.png'
    write_asset(vault, image, b'synthetic image')
    digest = AssetLibrary(vault).record(image)['sha256']
    repair = {'sub': 'S-1', 'item': 'q', 'selector': ['items', {'id': 'q'}, 'stem'],
              'old': '2\x01 3', 'new': '2 × 3', 'image_reference': image, 'image_sha256': digest}
    proposal = 'Library/Courses/S/Questions/proposal.json'
    review = 'Library/Courses/S/Questions/review.json'
    proposal_bytes = json.dumps({'corrections': [repair]}).encode()
    write_asset(vault, proposal, proposal_bytes)
    write_asset(vault, review, json.dumps({'reviewer': 'independent', 'decisions': [
        {'item': 'q', 'accepted': True, 'image_sha256': digest}], 'rejected_corrections': [],
        **({'proposal_sha256': hashlib.sha256(proposal_bytes).hexdigest()} if binding else {})}).encode())
    write_asset(vault, 'Library/Courses/S/Questions/repair.json', json.dumps({
        'format_version': 1, 'subtopic': 'S-1', 'question_ids': {'q': 'official-q1'}, 'batches': [
            {'proposal': proposal, 'review': review, 'author': 'author'}]}).encode(),
        metadata={'kind': 'source_repair', 'subtopic': 'S-1'})
    original = {'subtopic': 'S-1', 'items': [{'id': 'q', 'stem': repair['old'], 'answer': 'A', 'image': image}]}
    current = copy.deepcopy(original)
    current['items'][0]['stem'] = repair['new']
    return vault, original, current, review


def test_registered_repair_preserves_original_and_unrelated_fields(tmp_path):
    vault, original, current, _ = setup(tmp_path)
    before = copy.deepcopy(original)
    current['items'][0]['answer'] = 'B'
    staged, count = overlay(original, current, AssetLibrary(vault))
    assert count == 1 and staged['items'][0]['stem'] == current['items'][0]['stem']
    assert staged['items'][0]['answer'] == 'A' and original == before
    assert overlay(staged, current, AssetLibrary(vault))[1] == 0


def test_changed_review_or_unreviewed_text_cannot_waive_no_loss(tmp_path):
    vault, original, current, review = setup(tmp_path)
    current['items'][0]['stem'] = 'unreviewed change'
    assert overlay(original, current, AssetLibrary(vault))[1] == 0
    (vault / review).write_text('{}')
    with pytest.raises(ValueError, match='digest'):
        overlay(original, current, AssetLibrary(vault))


def test_refine_uses_registered_repairs_without_replacing_snapshot(tmp_path, monkeypatch):
    import sys
    from pathlib import Path
    monkeypatch.syspath_prepend(str(Path(__file__).resolve().parents[1] / 'refine'))
    import refine
    vault, original, current, _ = setup(tmp_path)
    monkeypatch.setenv('STEM_TUTOR_VAULT', str(vault))
    staged, count = refine.reviewed_source_baseline(original, current)
    assert count == 1 and staged['items'][0]['stem'] == current['items'][0]['stem']
    assert original['items'][0]['stem'] == '2\x01 3'


def test_review_without_exact_proposal_binding_cannot_waive_text(tmp_path):
    vault, original, current, _ = setup(tmp_path, binding=False)
    with pytest.raises(ValueError, match='proposal'):
        overlay(original, current, AssetLibrary(vault))


def test_conflicting_review_decisions_fail_closed(tmp_path):
    from tutorlib.asset_library import write_asset
    vault, original, current, review = setup(tmp_path)
    reviewed = json.loads((vault / review).read_bytes())
    reviewed['decisions'].insert(0, {**reviewed['decisions'][0], 'accepted': False})
    # Use a fresh immutable resource; never overwrite the reviewed bytes.
    replacement = review.replace('review.json', 'ambiguous-review.json')
    write_asset(vault, replacement, json.dumps(reviewed).encode())
    original_manifest = 'Library/Courses/S/Questions/repair.json'
    manifest = json.loads((vault / original_manifest).read_bytes())
    manifest['batches'][0]['review'] = replacement
    from tutorlib.asset_library import register_asset
    register_asset(vault, original_manifest, metadata={'repair_status': 'superseded'})
    write_asset(vault, original_manifest.replace('repair.json', 'ambiguous-repair.json'),
                json.dumps(manifest).encode(), metadata={'kind': 'source_repair', 'subtopic': 'S-1'})
    with pytest.raises(ValueError, match='duplicate.*decision'):
        overlay(original, current, AssetLibrary(vault))


def test_missing_item_is_left_to_normal_no_loss_gate(tmp_path):
    vault, original, current, _ = setup(tmp_path)
    current['items'] = []
    staged, count = overlay(original, current, AssetLibrary(vault))
    assert staged == original and count == 0


def test_superseded_repair_is_preserved_but_no_longer_applied(tmp_path):
    from tutorlib.asset_library import register_asset
    vault, original, current, _ = setup(tmp_path)
    reference = 'Library/Courses/S/Questions/repair.json'
    before = (vault / reference).read_bytes()
    register_asset(vault, reference, metadata={'repair_status': 'superseded'})
    assert overlay(original, current, AssetLibrary(vault))[1] == 0
    assert (vault / reference).read_bytes() == before


def test_foundry_rebuild_keeps_source_repair_and_stable_identity(tmp_path, monkeypatch):
    from build import add_past
    vault, _, _, _ = setup(tmp_path)
    monkeypatch.setenv('STEM_TUTOR_VAULT', str(vault))
    monkeypatch.setattr(add_past, 'IMAGES', None)
    work = tmp_path / 'work'
    work.mkdir()
    (work / 'S.tagged.json').write_text(json.dumps([{'id': 'official-q1', 'ref': 'Exam',
        'kcs': ['S-1.1'], 'stem': '2\x01 3', 'options': {'A': '6', 'B': '5'},
        'answer': 'A', 'image': 'Library/Courses/S/Questions/image.png'}]))
    pack = tmp_path / 'pack.json'
    pack.write_text(json.dumps({'spec': 'S', 'subtopic': 'S-1', 'items': []}))
    add_past.add(pack, work=work)
    item = json.loads(pack.read_text())['items'][0]
    assert item['stem'] == '2 × 3' and item['answer'] == 'A'
    add_past.add(pack, work=work)
    assert json.loads(pack.read_text())['items'][0] == item

@pytest.mark.parametrize('bank_stem, expected', [('2\x01 3', '2 × 3'), ('2 × 3', '2 × 3'), ('different valid text', None)])
def test_foundry_rebuild_requires_reviewed_old_or_new_value(tmp_path, monkeypatch, bank_stem, expected):
    from build import add_past
    vault, _, _, _ = setup(tmp_path)
    monkeypatch.setenv('STEM_TUTOR_VAULT', str(vault))
    monkeypatch.setattr(add_past, 'IMAGES', None)
    work = tmp_path / 'work'
    work.mkdir()
    (work / 'S.tagged.json').write_text(json.dumps([{'id': 'official-q1', 'ref': 'Exam',
        'kcs': ['S-1.1'], 'stem': bank_stem, 'options': {'A': '6', 'B': '5'},
        'answer': 'A', 'image': 'Library/Courses/S/Questions/image.png'}]))
    pack = tmp_path / 'pack.json'
    original = json.dumps({'spec': 'S', 'subtopic': 'S-1', 'items': []})
    pack.write_text(original)
    if expected is None:
        with pytest.raises(ValueError, match='reviewed.*value'):
            add_past.add(pack, work=work)
        assert pack.read_text() == original
    else:
        add_past.add(pack, work=work)
        assert json.loads(pack.read_text())['items'][0]['stem'] == expected
