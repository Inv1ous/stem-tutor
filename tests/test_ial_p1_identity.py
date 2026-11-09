"""Identity and provenance structure only; no science or teaching approval."""
import copy
import json

import pytest
from ial_p1_fixtures import QID, QP, MS, source_fixture, regions
from tutorlib import topicals
from tutorlib.asset_library import AssetLibrary


def policy():
    from tutorlib import ial_p1_identity
    return ial_p1_identity


def test_p1_exact_namespace_identity_and_course():
    assert topicals.identity({'source': {'qid': QID, 'part': ''}}) == QID
    assert topicals.official_course({'qid': QID, 'part': ''}) == 'P1'
    first = policy().p1_pilot(QID, '')
    assert [first[k] for k in ('course', 'board', 'unit', 'session', 'component', 'question')] == ['P1', 'Pearson Edexcel', 'WMA11', '2019-01', '01', 1]
    first['qp']['sha256'] = 'bad'
    assert policy().p1_pilot(QID, '')['qp']['sha256'] != 'bad'


@pytest.mark.parametrize('qid,part', [(QID.replace(a, b), '') for a, b in [
    ('P1_', 'P2_'), ('pearson-edexcel-ial', 'pearson-other'), ('WMA11', 'WMA12'),
    ('WMA11', 'WME01'), ('2019-01', '2019-06'), ('2019-01', '2020-01'),
    ('_01_q', '_02_q'), ('q1', 'q3'), ('q1', 'q0'), ('q1', 'q01'),
    ('P1_', 'p1_'), ('WMA11', 'wma11'), ('q1', 'Q1')]] +
    [(QID + ':a', ''), (QID, 'a'), (QID, None), (None, ''), (True, ''), (4, '')])
def test_p1_rejects_each_identity_field_and_noncanonical_part(qid, part):
    assert policy().p1_pilot(qid, part) is None


@pytest.mark.parametrize('qid', ['P1_bad', 'p1_bad', QID + ':a', QID.replace('P1_', '9702_'), QID.replace('WMA11', 'WMA12')])
def test_p1_invalid_namespace_never_falls_back_to_caie_ref(qid):
    assert topicals.identity({'source': {'qid': qid, 'part': '', 'ref': '9702 Jun 2023 P22 Q2(a)'}}) is None


def test_caie_and_unknown_identity_bytes_are_unchanged():
    for source, expected in [({'qid': '9702_s23_qp_22_q02(a)'}, '9702_s23_22_q2:a'),
                             ({'ref': '9702 Jun 2023 P22 Q2(a)'}, '9702_s23_22_q2:a'),
                             ({'qid': None}, None), ({'qid': ''}, None), ({'qid': 'SME_local_q1'}, None)]:
        assert topicals.identity({'source': source}) == expected


def test_p1_source_policy_accepts_exact_pins_without_approving_content(tmp_path):
    lib = source_fixture(tmp_path)
    policy().validate_p1_sources(QID, '', 'P1', regions(lib, QP), regions(lib, MS), lib)


@pytest.mark.parametrize('fault', ['role', 'asset', 'hash', 'corrupt', 'missing', 'course', 'kind', 'path', 'empty', 'object', 'page-bool', 'page-low', 'page-high', 'order', 'nan', 'inf', 'box-bool'])
def test_p1_source_policy_rejects_each_role_hash_metadata_fault(tmp_path, fault):
    lib = source_fixture(tmp_path); q = regions(lib, QP); m = regions(lib, MS)
    if fault == 'role': q, m = m, q
    if fault == 'asset': q[0]['source_id'] = 'asset:unknown'
    if fault == 'hash': q[0]['source_sha256'] = '0' * 64
    if fault == 'corrupt': (tmp_path / lib.record(QP)['path']).write_bytes(b'corrupt')
    if fault == 'missing': (tmp_path / lib.record(QP)['path']).unlink()
    if fault in ('course', 'kind', 'path'):
        path = tmp_path / 'Library/catalog.json'; cat = json.loads(path.read_text())
        cat['assets'][QP[6:]][fault] = {'course': '9702', 'kind': 'Diagrams', 'path': 'Library/wrong.pdf'}[fault]
        path.write_text(json.dumps(cat)); lib = AssetLibrary(tmp_path)
    if fault == 'empty': q = []
    if fault == 'object': q = [None]
    if fault.startswith('page-'): q[0]['page'] = {'page-bool': True, 'page-low': 0, 'page-high': 29}[fault]
    if fault == 'order': q = [{**q[0], 'page': 2}, q[0]]
    if fault in ('nan', 'inf', 'box-bool'): q[0]['box'][0] = {'nan': float('nan'), 'inf': float('inf'), 'box-bool': False}[fault]
    with pytest.raises(ValueError):
        policy().validate_p1_sources(QID, '', 'P1', q, m, lib)
