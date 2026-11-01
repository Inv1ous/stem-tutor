import copy
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'build'))
from correction_review import stage_corrections


def test_correction_audit_reports_both_original_and_unplanned_changes():
    from correction_review import audit_corrections
    pack = {'outline': 'A mistaken statement.', 'items': [{'id': 'q1', 'stem': 'Question', 'answer': 'A'}]}
    proposal = {'corrections': [{'selector': ['outline'], 'old': 'mistaken', 'new': 'corrected', 'reason': 'Evidence'}]}
    candidate, note = stage_corrections(pack, 'Original note', proposal)
    candidate['items'][0]['answer'] = 'B'
    def compare(before, after, after_note):
        issues = []
        if before['pack']['outline'] != after['outline']:
            issues.append('outline changed')
        if before['pack']['items'][0]['answer'] != after['items'][0]['answer']:
            issues.append('answer changed')
        return issues
    audit = audit_corrections(pack, 'Original note', proposal, candidate, note, compare)
    assert audit['against_original'] == ['outline changed', 'answer changed']
    assert audit['outside_proposal'] == ['answer changed']
    assert pack['outline'] == 'A mistaken statement.'
    assert pack['items'][0]['answer'] == 'A'


def test_stage_corrections_is_exact_and_does_not_mutate_original():
    pack = {'outline': 'First. Old sentence. Last.', 'items': [{'id': 'q1', 'hints': ['old hint']}]}
    original = copy.deepcopy(pack)
    proposal = {'corrections': [
        {'selector': ['outline'], 'old': 'Old sentence.', 'new': 'Correct sentence.', 'reason': 'source'},
        {'selector': ['items', {'id': 'q1'}, 'hints', 0], 'old': 'old hint', 'new': 'new hint', 'reason': 'source'},
    ], 'note_corrections': [{'old': 'old note', 'new': 'new note', 'reason': 'source'}]}
    candidate, note = stage_corrections(pack, 'old note', proposal)
    assert candidate['outline'] == 'First. Correct sentence. Last.'
    assert candidate['items'][0]['hints'] == ['new hint'] and note == 'new note'
    assert pack == original


def test_stage_corrections_rejects_ambiguous_stale_and_unexplained_changes():
    pack = {'items': [{'id': 'q1', 'hint': 'old'}, {'id': 'q1', 'hint': 'old'}]}
    correction = {'selector': ['items', {'id': 'q1'}, 'hint'], 'old': 'old', 'new': 'new', 'reason': 'source'}
    with pytest.raises(ValueError):
        stage_corrections(pack, '', {'corrections': [correction]})
    pack['items'].pop()
    for change in ({**correction, 'old': 'stale'}, {**correction, 'reason': ''}):
        with pytest.raises(ValueError):
            stage_corrections(pack, '', {'corrections': [change]})


def test_review_fingerprints_bind_original_proposal_and_candidate():
    from correction_review import review_fingerprints
    pack = {'outline': 'old'}
    proposal = {'corrections': [{'selector': ['outline'], 'old': 'old', 'new': 'new', 'reason': 'source'}]}
    candidate, note = stage_corrections(pack, 'note', proposal)
    original = review_fingerprints(pack, 'note', proposal, candidate, note)
    assert original == review_fingerprints({'outline': 'old'}, 'note', proposal, candidate, note)
    changed = review_fingerprints(pack, 'note', proposal, {**candidate, 'extra': 1}, note)
    assert changed['candidate'] != original['candidate']
    assert changed['original'] == original['original'] and changed['proposal'] == original['proposal']
    assert review_fingerprints(pack, 'note!', proposal, candidate, note)['original'] != original['original']


def test_review_evidence_rejects_stale_or_unreviewed_corrections():
    from correction_review import validate_review_evidence, review_fingerprints
    pack = {'outline': 'old'}
    proposal = {'corrections': [{'selector': ['outline'], 'old': 'old', 'new': 'new', 'reason': 'source'}]}
    candidate, note = stage_corrections(pack, 'note', proposal)
    evidence = {'fingerprints': review_fingerprints(pack, 'note', proposal, candidate, note),
                'reviewer': 'independent-reviewer', 'finding': 'Correct according to source', 'verdict': 'accepted'}
    assert validate_review_evidence(pack, 'note', proposal, candidate, note, evidence) == []
    assert validate_review_evidence(pack, 'note', proposal, {**candidate, 'outline': 'other'}, note, evidence)
    assert validate_review_evidence(pack, 'note', proposal, candidate, note, {**evidence, 'verdict': 'pending'})
    assert validate_review_evidence(pack, 'note', proposal, candidate, note, {})


def test_correction_manifest_rejects_unsafe_duplicate_and_missing_sources():
    from correction_review import validate_manifest
    valid = {'corrections': [{'selector': ['outline'], 'old': 'old', 'new': 'new', 'reason': 'source'}],
             'note_corrections': [], 'evidence': [{'source': 'official.pdf', 'pdf_page': 2}]}
    assert validate_manifest(valid) == []
    assert validate_manifest({**valid, 'evidence': []})
    assert validate_manifest({**valid, 'corrections': valid['corrections'] * 2})
    assert validate_manifest({**valid, 'corrections': [{**valid['corrections'][0], 'selector': ['items', {'id': 'q'}, 'answer']}]})
    assert validate_manifest({**valid, 'note_corrections': [
        {'old': 'one sentence', 'new': 'one new', 'reason': 'source'},
        {'old': 'sentence', 'new': 'other', 'reason': 'source'}]})


def test_manifest_rejects_noop_and_multiline_note_replacements():
    from correction_review import validate_manifest
    base = {'corrections': [], 'note_corrections': [{'old': 'old', 'new': 'new', 'reason': 'source'}],
            'evidence': [{'source': 'official.pdf', 'pdf_page': 1}]}
    assert validate_manifest(base) == []
    assert validate_manifest({**base, 'note_corrections': [{'old': 'old', 'new': 'old', 'reason': 'source'}]})
    assert validate_manifest({**base, 'note_corrections': [{'old': 'old\nother', 'new': 'new', 'reason': 'source'}]})


def test_reviewed_correction_audit_rejects_absent_or_unrelated_changes():
    from correction_review import assess_reviewed_candidate, review_fingerprints
    pack = {'outline': 'old', 'items': [{'id': 'q1', 'stem': 'kept'}]}
    proposal = {'corrections': [{'selector': ['outline'], 'old': 'old', 'new': 'new', 'reason': 'source'}],
                'note_corrections': [], 'evidence': [{'source': 'official.pdf', 'pdf_page': 1}]}
    candidate, note = stage_corrections(pack, 'note', proposal)
    evidence = {'fingerprints': review_fingerprints(pack, 'note', proposal, candidate, note),
                'reviewer': 'reviewer', 'finding': 'source checked', 'verdict': 'accepted'}
    def compare(before, after, new_note):
        return [] if before['pack'] == after and before['note'] == new_note else ['changed']
    audit = assess_reviewed_candidate(pack, 'note', proposal, candidate, note, evidence, compare)
    assert audit['against_original'] == ['changed'] and audit['outside_proposal'] == []
    with pytest.raises(ValueError):
        assess_reviewed_candidate(pack, 'note', proposal, pack, note, evidence, compare)
    altered = copy.deepcopy(candidate)
    altered['items'][0]['stem'] = 'removed information'
    altered_evidence = {**evidence, 'fingerprints': review_fingerprints(pack, 'note', proposal, altered, note)}
    assert assess_reviewed_candidate(pack, 'note', proposal, altered, note, altered_evidence, compare)['outside_proposal']


def test_audit_rejects_old_note_text_left_beside_corrected_text():
    from correction_review import assess_reviewed_candidate, review_fingerprints
    pack = {'outline': 'unchanged'}
    proposal = {'corrections': [], 'note_corrections': [{'old': 'old error', 'new': 'new fact', 'reason': 'source'}],
                'evidence': [{'source': 'official.pdf', 'pdf_page': 1}]}
    candidate_note = 'old error\nnew fact'
    evidence = {'fingerprints': review_fingerprints(pack, 'old error', proposal, pack, candidate_note),
                'reviewer': 'reviewer', 'finding': 'checked', 'verdict': 'accepted'}
    with pytest.raises(ValueError):
        assess_reviewed_candidate(pack, 'old error', proposal, pack, candidate_note, evidence,
                                  lambda before, candidate, note: [])


def test_declared_note_addition_must_be_present_once_and_new():
    from correction_review import assess_reviewed_candidate, review_fingerprints, validate_manifest
    pack = {'outline': 'unchanged'}
    proposal = {'note_corrections': [{'old': 'old statement', 'new': 'corrected statement', 'reason': 'source'}],
                'note_addition': 'A new explanatory sentence.',
                'evidence': [{'source': 'paper.pdf', 'pdf_page': 1}]}
    compare = lambda before, candidate, note: []
    def assess(original, result):
        evidence = {'fingerprints': review_fingerprints(pack, original, proposal, pack, result),
                    'reviewer': 'independent', 'finding': 'checked', 'verdict': 'accepted'}
        return assess_reviewed_candidate(pack, original, proposal, pack, result, evidence, compare)
    assert not validate_manifest(proposal)
    assert assess('old statement', 'corrected statement\nA new explanatory sentence.')
    for original, result in [('old statement', 'corrected statement'), ('old statement', 'corrected statement\nA new explanatory sentence.\nA new explanatory sentence.'),
                             ('old statement\nA new explanatory sentence.', 'corrected statement\nA new explanatory sentence.')]:
        with pytest.raises(ValueError):
            assess(original, result)
    assert validate_manifest({**proposal, 'note_addition': ''})
    for hidden in ('<!--\nA new explanatory sentence.\n-->', '```\nA new explanatory sentence.\n```',
                   '~~~python\nA new explanatory sentence.\n~~~', 'prefix A new explanatory sentence.',
                   '%%\nA new explanatory sentence.\n%%', '<style>\nA new explanatory sentence.\n</style>'):
        with pytest.raises(ValueError):
            assess('old statement', 'corrected statement\n' + hidden)


def test_source_fingerprints_reject_missing_changed_and_invalid_pages(tmp_path):
    import pymupdf
    from correction_review import source_fingerprints, verify_source_fingerprints
    source = tmp_path / 'paper.pdf'
    pdf = pymupdf.open()
    pdf.new_page()
    pdf.save(source)
    pdf.close()
    proposal = {'evidence': [{'source': 'paper.pdf', 'pdf_page': 1}]}
    fingerprints = source_fingerprints(proposal, tmp_path)
    assert verify_source_fingerprints(proposal, tmp_path, fingerprints) == []
    assert verify_source_fingerprints({'evidence': [{'source': 'paper.pdf', 'pdf_page': 2}]}, tmp_path, fingerprints)
    source.write_bytes(b'not a PDF')
    assert verify_source_fingerprints(proposal, tmp_path, fingerprints)
    assert verify_source_fingerprints({'evidence': [{'source': '../outside.pdf', 'pdf_page': 1}]}, tmp_path, fingerprints)


def test_source_bound_audit_rejects_changed_or_missing_cited_pdf(tmp_path):
    import pymupdf
    from correction_review import assess_source_bound_candidate, review_fingerprints, source_fingerprints
    source = tmp_path / 'paper.pdf'
    doc = pymupdf.open(); doc.new_page(); doc.save(source); doc.close()
    pack = {'outline': 'old'}
    proposal = {'corrections': [{'selector': ['outline'], 'old': 'old', 'new': 'new', 'reason': 'source'}],
                'evidence': [{'source': 'paper.pdf', 'pdf_page': 1}]}
    candidate, note = stage_corrections(pack, 'note', proposal)
    evidence = {'fingerprints': review_fingerprints(pack, 'note', proposal, candidate, note),
                'sources': source_fingerprints(proposal, tmp_path), 'reviewer': 'reviewer',
                'finding': 'source checked', 'verdict': 'accepted'}
    compare = lambda before, after, new_note: []
    assert assess_source_bound_candidate(pack, 'note', proposal, candidate, note, evidence, compare, tmp_path)
    source.write_bytes(b'modified')
    with pytest.raises(ValueError):
        assess_source_bound_candidate(pack, 'note', proposal, candidate, note, evidence, compare, tmp_path)
    with pytest.raises(ValueError):
        assess_source_bound_candidate(pack, 'note', proposal, candidate, note, {**evidence, 'sources': []}, compare, tmp_path)


def test_source_reader_rejects_oversized_or_nonregular_input(tmp_path):
    import os
    from correction_review import source_fingerprints
    giant = tmp_path / 'huge.pdf'
    with giant.open('wb') as f:
        f.truncate(128 * 1024 * 1024 + 1)
    proposal = {'evidence': [{'source': 'huge.pdf', 'pdf_page': 1}]}
    with pytest.raises(ValueError, match='size'):
        source_fingerprints(proposal, tmp_path)
    fifo = tmp_path / 'fifo.pdf'
    os.mkfifo(fifo)
    with pytest.raises(ValueError, match='regular'):
        source_fingerprints({'evidence': [{'source': 'fifo.pdf', 'pdf_page': 1}]}, tmp_path)


def test_source_reader_rejects_symlink_components(tmp_path):
    import pymupdf
    from correction_review import source_fingerprints
    folder = tmp_path / 'real'; folder.mkdir()
    pdf = pymupdf.open(); pdf.new_page(); pdf.save(folder / 'paper.pdf'); pdf.close()
    (tmp_path / 'linked').symlink_to(folder, target_is_directory=True)
    (tmp_path / 'paper-link.pdf').symlink_to(folder / 'paper.pdf')
    for path in ('linked/paper.pdf', 'paper-link.pdf'):
        with pytest.raises(ValueError):
            source_fingerprints({'evidence': [{'source': path, 'pdf_page': 1}]}, tmp_path)


def test_structured_corrections_require_exact_original_and_candidate():
    from correction_review import assess_reviewed_candidate, review_fingerprints, validate_manifest
    pack = {'items': [{'id': 'P2-1-i15', 'rubric': [{'point': 'old'}]}],
            'worked': [{'id': 'we2', 'faded': {'problem': 'old', 'answer': 1}}]}
    changes = [
        {'selector': ['items', {'id': 'P2-1-i15'}, 'rubric'], 'old': [{'point': 'old'}],
         'new': [{'point': 'new'}], 'reason': 'Allow valid alternatives'},
        {'selector': ['worked', {'id': 'we2'}, 'faded'], 'old': {'problem': 'old', 'answer': 1},
         'new': {'problem': 'new', 'answer': 2}, 'reason': 'Match numeric grading'},
    ]
    proposal = {'corrections': [], 'structured_corrections': changes,
                'evidence': [{'source': 'paper.pdf', 'pdf_page': 1}]}
    assert validate_manifest(proposal) == []
    candidate, note = stage_corrections(pack, 'note', proposal)
    evidence = {'fingerprints': review_fingerprints(pack, 'note', proposal, candidate, note),
                'reviewer': 'reviewer', 'finding': 'checked independently', 'verdict': 'accepted'}
    compare = lambda before, after, new_note: [] if before['pack'] == after else ['changed']
    assert assess_reviewed_candidate(pack, 'note', proposal, candidate, note, evidence, compare)['outside_proposal'] == []
    assert pack['items'][0]['rubric'] == [{'point': 'old'}]
    altered = copy.deepcopy(pack)
    altered['worked'][0]['faded']['answer'] = 9
    with pytest.raises(ValueError):
        stage_corrections(altered, 'note', proposal)
    reverted = copy.deepcopy(candidate)
    reverted['items'][0]['rubric'] = [{'point': 'old'}]
    evidence['fingerprints'] = review_fingerprints(pack, 'note', proposal, reverted, note)
    with pytest.raises(ValueError):
        assess_reviewed_candidate(pack, 'note', proposal, reverted, note, evidence, compare)
    assert validate_manifest({**proposal, 'structured_corrections': changes * 2})
    unsafe = {**changes[0], 'selector': ['items', {'id': 'other'}, 'answer']}
    assert validate_manifest({**proposal, 'structured_corrections': [unsafe]})
    wrong_type = copy.deepcopy(pack)
    wrong_type['worked'][0]['faded']['answer'] = True
    with pytest.raises(ValueError):
        stage_corrections(wrong_type, 'note', proposal)
    wrong_candidate = copy.deepcopy(candidate)
    wrong_candidate['worked'][0]['faded']['answer'] = 2.0
    evidence['fingerprints'] = review_fingerprints(pack, 'note', proposal, wrong_candidate, note)
    with pytest.raises(ValueError):
        assess_reviewed_candidate(pack, 'note', proposal, wrong_candidate, note, evidence, compare)
