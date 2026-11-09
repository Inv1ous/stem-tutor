"""Question text must not send the learner to an image the item does not show (2026-11-07 periodic-table restate)."""
import hashlib
import json
from pathlib import Path
import sys

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'build'))
import content_checks
import leak_free_topical_release as release
import topicals
from tutorlib.asset_library import AssetLibrary, write_asset

QUESTION = 'Library/Courses/9701/Questions/Media/9701_m24_12_q1-aaaaaaaaaaaaaaaa.png'
OTHER = 'Library/Courses/9701/Questions/Media/9701_m24_12_q1-bbbbbbbbbbbbbbbb.png'
PRODUCTION = ROOT.parent / 'STEM Tutor'


def item(ident, stem, images=(QUESTION,)):
    return {'id': ident, 'kind': 'mcq', 'stem': stem, 'options': {k: '(in the source picture)' for k in 'ABCD'},
            'answer': 'B', 'image': images[0], 'images': list(images), 'explanation': None}


def test_checker_flags_next_image_text_only_when_no_further_image():
    assert content_checks.dangling_image_problems(item('a', release.OLD_STEM))
    assert not content_checks.dangling_image_problems(item('a', release.OLD_STEM, (QUESTION, OTHER)))
    assert not content_checks.dangling_image_problems(item('a', release.NEW_STEM))
    assert not content_checks.dangling_image_problems(item('a', 'Element E is in Period 3 of the Periodic Table.'))


def test_active_release_has_no_dangling_periodic_table_text():
    pointer = PRODUCTION / '.tutor/topicals/CURRENT'
    if not pointer.is_file():
        pytest.skip('no production vault')
    current = pointer.read_text().strip()  # read-only: the learner vault is never written here
    bank = json.loads(AssetLibrary(PRODUCTION).read(f'Library/Shared/Topicals/Releases/{current}/bank.json'))
    problems = [p for i in bank['items'] for p in content_checks.dangling_image_problems(i)]
    assert problems == []
    assert not [i['id'] for i in bank['items'] if 'periodic-table reference is provided' in (i.get('stem') or '')]


@pytest.fixture
def vault(tmp_path):
    vault = tmp_path / 'STEM Tutor'
    vault.mkdir()
    bank = {'format_version': 1, 'syllabus_versions': {'9701': '2025-2027'},
            'items': [item('topical-9701_m24_12_q1', release.OLD_STEM),
                      item('topical-9701_m24_12_q2', 'Element E is in Period 3 of the Periodic Table.'),
                      item('topical-9701_m24_12_q3', release.OLD_STEM, (QUESTION, OTHER))]}
    write_asset(vault, 'Library/Shared/Topicals/Releases/vold/bank.json',
                json.dumps(bank, ensure_ascii=False, indent=1).encode())
    (vault / '.tutor/topicals').mkdir(parents=True)
    (vault / '.tutor/topicals/CURRENT').write_text('vold\n')
    return vault, bank


def test_restate_changes_only_dangling_stems_and_needs_independent_review(vault, tmp_path, monkeypatch):
    vault, bank = vault
    batch = tmp_path / 'batch'
    result = release.restate(vault, batch, author='claude')
    assert result['changed_items'] == 1
    new = json.loads((batch / 'bank.json').read_text())
    assert new['items'][0] == {**bank['items'][0], 'stem': release.NEW_STEM}
    assert new['items'][1:] == bank['items'][1:]
    proposal = release.verify_restated(vault, batch)
    published = {}
    monkeypatch.setattr(topicals, 'publish', lambda b, v, **kw: published.update(kw) or {'version': 'vnew'})
    digest = release.proposal_digest(proposal)
    for review in ({'reviewer': 'claude', 'accepted': True, 'proposal_sha256': digest},
                   {'reviewer': 'codex', 'accepted': False, 'proposal_sha256': digest},
                   {'reviewer': 'codex', 'accepted': True, 'proposal_sha256': '0' * 64}):
        (tmp_path / 'review.json').write_text(json.dumps(review))
        with pytest.raises(ValueError, match='independent'):
            release.publish_restated(batch, vault, tmp_path / 'review.json')
    (tmp_path / 'review.json').write_text(json.dumps({'reviewer': 'codex', 'accepted': True, 'proposal_sha256': digest}))
    assert release.publish_restated(batch, vault, tmp_path / 'review.json') == {'version': 'vnew'}
    assert published['expected_bank_sha256'] == hashlib.sha256((batch / 'bank.json').read_bytes()).hexdigest()
    report = json.loads((batch / 'report.json').read_text())
    assert report['preparation'] == {'expected_current': 'vold'}
    assert report['display_correction']['review']['reviewer'] == 'codex'


def test_verify_refuses_any_unproposed_change(vault, tmp_path):
    vault, _ = vault
    batch = tmp_path / 'batch'
    release.restate(vault, batch, author='claude')
    proposal = json.loads((batch / 'proposal.json').read_text())
    bank = json.loads((batch / 'bank.json').read_text())
    bank['items'][0]['answer'] = 'C'
    data = json.dumps(bank, ensure_ascii=False, indent=1).encode()
    (batch / 'bank.json').write_bytes(data)
    proposal['candidate_bank_sha256'] = hashlib.sha256(data).hexdigest()
    (batch / 'proposal.json').write_text(json.dumps(proposal))
    with pytest.raises(ValueError, match='unproposed'):
        release.verify_restated(vault, batch)


def test_publish_refuses_a_bank_with_dangling_image_text(vault, tmp_path):
    vault, bank = vault
    batch = tmp_path / 'batch'
    batch.mkdir()
    (batch / 'bank.json').write_text(json.dumps(bank))
    (batch / 'report.json').write_text(json.dumps({'preparation': {'expected_current': 'vold'}}))
    with pytest.raises(ValueError, match='does not show'):
        topicals.publish(batch, vault)


def test_rollback_swaps_current_back_only_from_the_named_release(vault):
    vault, _ = vault
    (vault / '.tutor/topicals/CURRENT').write_text('vnew\n')
    with pytest.raises(ValueError):
        release.rollback(vault, 'vother', 'vold')
    assert release.rollback(vault, 'vnew', 'vold') == {'current': 'vold', 'previous': 'vnew'}
    assert (vault / '.tutor/topicals/CURRENT').read_text().strip() == 'vold'
