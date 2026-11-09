"""Known mathematical gutter prefixes never relax source allocation proofs."""
import copy
import json
from pathlib import Path
import sys

import pytest
from library_assets import canonical_path
from tutorlib.asset_library import AssetLibrary
from test_pmt_complete_profile import staged

ROOT = Path(__file__).resolve().parents[2]
WORKER = ROOT / 'Work/Workers/extraction/overnight-20261105-10pct'
sys.path[:0] = [str(WORKER), str(ROOT / 'stem-tutor/extraction')]
import prepared_source_packet as helper
import prepared_scope
import pmt_complete_profile


@pytest.fixture(scope='module')
def source_rows(tmp_path_factory):
    """Read actual registered triage PDFs only in disposable Library vaults."""
    cases = [
        ('asset:asset-3c6efba593b47d52a29b71d8', 'P2'),
        ('asset:asset-17ba3f8c9420766c2239f6f2', 'P3'),
        ('asset:asset-b13d58e2c20c171ecf4917fc', 'S1'),
        ('asset:asset-c736db05bbfdcdb22dc3efe2', 'S2'),
    ]
    rows = {}
    for reference, course in cases:
        vault = staged(tmp_path_factory.mktemp(course), reference)
        library = AssetLibrary(vault)
        bundle = pmt_complete_profile.analyse(library.read(reference), course, reference,
                                               source_path=canonical_path(reference))
        for row in bundle['questions']:
            rows[row['id']] = row, library
    return rows


@pytest.mark.parametrize('token', [
    'f′′(x),', 'f(x).', 'f–1(x)', 'f–1(x),', 'f(x)', '2f(x)', '|f(x)|,',
    'f(x', '\uf8f4f(x)\uf8f4,', 'f(2x),', 'fg(x)', '\uf8e6f(x)\uf8e6,',
    'P(X', 'Var(X),', 'P(J', 'P(K', 'P(L<', 'P(L', 'P(R', 'P(S', 'P(T',
    'E(X)', 'E(R),',
])
def test_saved_triage_complete_math_prefixes_are_recognized(token):
    # Removing recognition must restore the actual false-positive hold.
    assert helper._known_math_gutter_prefix(token)


@pytest.mark.parametrize('token', [
    '(a)', 'a)', '(i)', '1(a)', '(a)f(x)', '(a', '(a)f(x', 'a)f(x)',
    '1(a)f(x)', '(C)', '(L)', '(R),', '(You', '(£p)', 'interest).',
    '–1(x),', '′(x).', 'unknown(x)', 'foo(x)', 'F(x)', 'p(X)', 'var(X)',
    'f-2(x)', 'f–2(x)', 'f′′′(x)', '||f(x)||', '(f(x))',
])
def test_labels_damaged_functions_and_unknown_prose_are_not_exempt(token):
    assert not helper._known_math_gutter_prefix(token)


@pytest.mark.parametrize('qid,parts', [
    ('occurrence-0270f91eeec1e18dec828459', [('a', 3), ('b', 4)]),
    ('occurrence-2ac283753cded50cc01f7be9', [('a', 3), ('b', 2), ('c', 1), ('d', 3), ('e', 1)]),
    ('occurrence-5e3ab8f4a046a24589f4ba31', [('a', 3), ('b', 3)]),
    ('occurrence-d94e56a0edc6019f424968b9', [('a', 2), ('b', 2), ('c', 3)]),
    ('occurrence-13f65e39135be4708ae25e53', [('a', 5), ('b', 3), ('c', 2), ('d', 3)]),
    ('occurrence-750e8474d99549c78b1ead99', [('a', 2), ('b', 1), ('c', 1), ('d', 4), ('e', 4), ('f', 2)]),
    ('occurrence-2b40b239f479d1a402ce3e2d', [('a', 2), ('b', 3), ('c', 1), ('d', 3)]),
])
def test_actual_function_and_probability_rows_keep_printed_leaf_marks(source_rows, qid, parts):
    row, library = source_rows[qid]
    before = json.dumps(row)
    manifest = helper._pmt_manifest(row, library)
    assert manifest['status'] == 'source_manifest'
    assert manifest['parts'] == [{'id': name, 'marks': marks} for name, marks in parts]
    assert manifest['evidence']['totals']['qp']['value'] == row['marks']
    assert manifest['evidence']['totals']['ms']['literal'] == f"[{row['marks']}]"
    assert manifest['evidence']['whole_maximum'] == row['marks']
    assert json.dumps(row) == before


@pytest.mark.parametrize('token', ['(a', 'a)', '(a)f(x)', '1(a)', 'unknown(x)', '(You', '(C)', '′(x).'])
def test_nonmath_ambiguous_gutter_tokens_still_hold_actual_source(source_rows, monkeypatch, token):
    row, library = source_rows['occurrence-0270f91eeec1e18dec828459']
    original = prepared_scope._words
    def words(page):
        values = copy.deepcopy(original(page))
        for word in values:
            if word['text'] == 'f′′(x),':
                word['text'] = token
        return values
    monkeypatch.setattr(prepared_scope, '_words', words)
    assert helper._pmt_manifest(row, library)['status'] == 'held'


@pytest.mark.parametrize('fault', ['missing_leaf_mark', 'part_sum', 'whole_total', 'digest'])
def test_math_exception_does_not_relax_actual_mark_or_source_proof(source_rows, monkeypatch, fault):
    row, library = source_rows['occurrence-0270f91eeec1e18dec828459']
    row = copy.deepcopy(row)
    if fault == 'whole_total':
        row['printed_total_witness'] = '(Total 8 marks)'
    elif fault == 'digest':
        row['regions'][0]['source_sha256'] = '0' * 64
    else:
        original = prepared_scope._words
        def words(page):
            values = copy.deepcopy(original(page))
            if page.number == 0:
                if fault == 'missing_leaf_mark':
                    values = [word for word in values if word['text'] != '(3)']
                else:
                    for word in values:
                        if word['text'] == '(3)': word['text'] = '(2)'
            return values
        monkeypatch.setattr(prepared_scope, '_words', words)
    assert helper._pmt_manifest(row, library)['status'] == 'held'


def test_actual_font_delimiter_does_not_exempt_neighboring_damaged_inverse(source_rows):
    row, library = source_rows['occurrence-6180ad07944ec9db70cb253d']
    assert helper._pmt_manifest(row, library) == {
        'status': 'held', 'reason': 'pmt_ambiguous_label_like_gutter_token'}


@pytest.mark.parametrize('family', ['pmt', 'caie'])
def test_previously_accepted_packets_match_the_approved_helper_bytes(tmp_path, monkeypatch, family):
    import importlib.util
    import source_practice
    from test_prepared_source_checks import caie_package, pmt_package
    monkeypatch.setattr(source_practice, 'WORKERS', tmp_path / 'no-workers')
    spec = importlib.util.spec_from_file_location(
        'pmt_function_tokens_approved', WORKER / 'pmt-function-tokens/preimages/prepared_source_packet.py')
    approved = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(approved)
    vault, package, replay = (pmt_package if family == 'pmt' else caie_package)(tmp_path)
    row = replay['items'][1] if family == 'pmt' else next(r for r in replay['items'] if r['number'] == 1)
    library = AssetLibrary(vault)
    expected_manifest, expected_packet = approved.prepared_packet(package, replay, row, library)
    manifest, packet = helper.prepared_packet(package, replay, row, library)
    assert expected_manifest['status'] == 'source_manifest'
    assert json.dumps(manifest) == json.dumps(expected_manifest)
    assert json.dumps(packet) == json.dumps(expected_packet)
