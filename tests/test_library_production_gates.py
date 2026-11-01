"""Production gates consume canonical assets without changing evidence identity."""
import hashlib
import json
from pathlib import Path
import sys

import pymupdf
import pytest

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / 'build'))
sys.path.insert(0, str(REPO / 'foundry'))
import correction_review
import foundry
from tutorlib.asset_library import AssetLibrary, write_asset


def pdf_bytes():
    document = pymupdf.open()
    document.new_page()
    result = document.tobytes()
    document.close()
    return result


def test_correction_source_binding_survives_physical_source_relocation(tmp_path, monkeypatch):
    vault = tmp_path / 'STEM Tutor'
    vault.mkdir()
    monkeypatch.setenv('STEM_TUTOR_VAULT', str(vault))
    data = pdf_bytes()
    alias = 'sources/specs/example.pdf'
    canonical = 'Library/Shared/Sources/Specifications/example.pdf'
    write_asset(vault, canonical, data, aliases=[alias])
    legacy = tmp_path / alias
    legacy.parent.mkdir(parents=True)
    legacy.write_bytes(b'legacy must never be used')
    proposal = {'evidence': [{'source': alias, 'pdf_page': 1}]}
    expected = [{'source': alias, 'pdf_page': 1, 'sha256': hashlib.sha256(data).hexdigest()}]
    assert correction_review.source_fingerprints(proposal, tmp_path) == expected
    legacy.unlink()
    assert correction_review.verify_source_fingerprints(proposal, tmp_path, expected) == []
    (vault / canonical).write_bytes(b'tampered')
    with pytest.raises(ValueError, match='digest'):
        correction_review.source_fingerprints(proposal, tmp_path)


def test_correction_catalog_source_read_keeps_existing_byte_limit(tmp_path, monkeypatch):
    vault = tmp_path / 'STEM Tutor'
    vault.mkdir()
    monkeypatch.setenv('STEM_TUTOR_VAULT', str(vault))
    write_asset(vault, 'Library/Shared/source.pdf', pdf_bytes(), aliases=['source.pdf'])
    monkeypatch.setattr(correction_review, 'MAX_SOURCE_BYTES', 10)
    with pytest.raises(ValueError, match='size limit'):
        correction_review.source_fingerprints({'evidence': [{'source': 'source.pdf', 'pdf_page': 1}]}, tmp_path)


def test_default_diagram_gate_accepts_canonical_embed_and_verifies_alias_hash(tmp_path, monkeypatch):
    vault = tmp_path / 'STEM Tutor'
    vault.mkdir()
    monkeypatch.setenv('STEM_TUTOR_VAULT', str(vault))
    monkeypatch.setattr(foundry, 'ROOT', foundry.REPO)
    canonical = 'Library/Courses/P1/Diagrams/example.svg'
    alias = 'Assets/P1/example.svg'
    write_asset(vault, canonical, b'<svg/>', aliases=[alias])
    pack = {'subtopic': 'P1-1', 'diagrams': [{'file': alias}]}
    note = f'![[{canonical}]]'
    assert foundry.diagram_problems(pack, {'kcs': []}, note) == []
    assert foundry.EMBEDDED.findall(note) == [canonical]
    (vault / canonical).write_bytes(b'changed')
    assert any('digest mismatch' in issue for issue in foundry.diagram_problems(pack, {'kcs': []}, note))


def test_guided_diagram_gate_keeps_note_binding_with_canonical_library_root(tmp_path, monkeypatch):
    from test_guided_teach_cards import base_card
    vault = tmp_path / 'STEM Tutor'
    vault.mkdir()
    monkeypatch.setenv('STEM_TUTOR_VAULT', str(vault))
    canonical = 'Library/Courses/P2/Diagrams/proof.svg'
    write_asset(vault, canonical, b'<svg/>')
    card = {**base_card(), 'plain_words': 'An idea.',
        'terms': [{'term': 'Proof', 'meaning': 'Logical argument', 'notation': 'none', 'spoken': 'proof', 'source': 'spec'}],
        'forms': [{'name': 'Direct', 'wordings': ['Prove'], 'example': 'Worked argument', 'check': 'Try another',
                   'answer': 'Valid argument', 'source': 'spec', 'rubric': [{'point': 'Valid argument', 'keywords': [['argument']]}]}],
        'misconceptions': [{'id': 'm1', 'idea': 'Examples prove all cases', 'temptation': 'They show a pattern', 'fix': 'Use a general argument'}],
        'diagrams': [canonical], 'diagram_descriptions': ['General proof flow.']}
    pack = {'subtopic': 'P2-1', 'guided_forms': {'P2-1.1': ['Direct']}, 'teach': {'P2-1.1': card},
            'misconceptions': [{'id': 'm1', 'kc': 'P2-1.1'}]}
    graph = {'kcs': [{'id': 'P2-1.1', 'subtopic': 'P2-1'}]}
    assert foundry.guided_problems(pack, graph, f'![[{canonical}]]', vault / 'Library') == []
    assert any('not embedded' in issue for issue in foundry.guided_problems(pack, graph, '', vault / 'Library'))
    (vault / canonical).write_bytes(b'changed')
    assert any('digest mismatch' in issue for issue in foundry.guided_problems(pack, graph,
                                                    f'![[{canonical}]]', vault / 'Library'))


def test_asset_bounded_read_rejects_invalid_limit_and_preserves_small_bytes(tmp_path):
    vault = tmp_path / 'STEM Tutor'
    vault.mkdir()
    ref = write_asset(vault, 'Library/Shared/small.svg', b'1234')
    reader = AssetLibrary(vault)
    assert reader.read(ref, max_bytes=4) == b'1234'
    with pytest.raises(ValueError, match='size limit'):
        reader.read(ref, max_bytes=3)
    with pytest.raises(ValueError, match='invalid'):
        reader.read(ref, max_bytes=True)


@pytest.mark.parametrize('lesson_display,has_card_reference,blocked', [
    (True, True, True), (True, False, False), (False, True, False)])
def test_card_only_lesson_diagram_reports_catalog_failure_without_changing_legacy_gate(
        monkeypatch, lesson_display, has_card_reference, blocked):
    reference = 'Library/Courses/P1/Diagrams/card-only.svg'
    pack = {'subtopic': 'P1-1', 'teach': {'P1-1.1': {
        'diagrams': [reference] if has_card_reference else [],
        'diagram_descriptions': ['Accessible description'],
        'forms': [{'diagram': reference}] if has_card_reference else []}}}
    def unavailable(_):
        raise ValueError('catalog integrity failure')
    monkeypatch.setattr(foundry, '_diagram_catalog', unavailable)
    issues = foundry.diagram_problems(pack, {'kcs': []}, '', lesson_display=lesson_display)
    assert bool(issues) is blocked
    if blocked:
        assert any('diagram catalog unavailable' in issue for issue in issues)


@pytest.mark.parametrize('use_alias', [False, True])
def test_card_only_lesson_diagram_accepts_verified_canonical_or_alias_and_rejects_tamper(
        tmp_path, monkeypatch, use_alias):
    vault = tmp_path / 'STEM Tutor'
    vault.mkdir()
    monkeypatch.setenv('STEM_TUTOR_VAULT', str(vault))
    monkeypatch.setattr(foundry, 'ROOT', foundry.REPO)
    canonical = 'Library/Courses/P1/Diagrams/card-only.svg'
    alias = 'Assets/P1/card-only.svg'
    write_asset(vault, canonical, b'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 20 20"><rect width="10" height="10"/></svg>',
                aliases=[alias], metadata={'kind': 'diagram', 'generated': True, 'renderer': 'synthetic-test'})
    reference = alias if use_alias else canonical
    pack = {'subtopic': 'P1-1', 'teach': {'P1-1.1': {
        'diagrams': [reference], 'diagram_descriptions': ['Accessible shape'],
        'forms': [{'diagram': reference}]}}}
    original = json.dumps(pack)
    assert foundry.diagram_problems(pack, {'kcs': []}, '', lesson_display=True) == []
    assert json.dumps(pack) == original
    (vault / canonical).write_bytes(b'tampered')
    assert any('digest mismatch' in issue for issue in foundry.diagram_problems(
        pack, {'kcs': []}, '', lesson_display=True))


@pytest.mark.parametrize('case', ['same', 'distinct', 'missing', 'corrupt'])
def test_lesson_diagram_binding_compares_verified_asset_identity(tmp_path, monkeypatch, case):
    vault = tmp_path / 'STEM Tutor'
    vault.mkdir()
    monkeypatch.setenv('STEM_TUTOR_VAULT', str(vault))
    monkeypatch.setattr(foundry, 'ROOT', foundry.REPO)
    canonical = 'Library/Courses/P1/Diagrams/canonical.svg'
    other = 'Library/Courses/P1/Diagrams/distinct.svg'
    alias = 'Assets/P1/canonical.svg'
    data = b'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 20 20"><rect width="10" height="10"/></svg>'
    metadata = {'kind': 'diagram', 'generated': True, 'renderer': 'synthetic-test'}
    write_asset(vault, canonical, data, aliases=[alias], metadata=metadata)
    write_asset(vault, other, data, metadata=metadata)
    requested = 'Assets/P1/missing.svg' if case == 'missing' else alias
    described = other if case == 'distinct' else canonical
    pack = {'subtopic': 'P1-1', 'diagrams': [{'file': requested}],
            'teach': {'P1-1.1': {'diagrams': [described], 'diagram_descriptions': ['Visible shape']}}}
    original = json.dumps(pack)
    if case == 'corrupt':
        (vault / canonical).write_bytes(b'tampered')
    issues = foundry.diagram_problems(pack, {'kcs': []}, '', lesson_display=True)
    assert bool(issues) is (case != 'same')
    assert json.dumps(pack) == original
