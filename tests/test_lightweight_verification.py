"""Bounded semantic checks consume replayed sources, never confer authority."""
import copy
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'extraction'))
import lightweight_verification as checks


def item(kind='mcq'):
    # Synthetic valid/invalid protocol inputs are disposable, not learning assets.
    region = {'source_id': 'asset:example', 'source_sha256': '1' * 64,
              'page': 1, 'box': [0, .1, 1, .4]}
    return {'id': 'paper_q2', 'official_qid': 'paper_q2', 'label': '2',
            'kind': kind, 'marks': 1 if kind == 'mcq' else 3,
            'question_text': 'Choose the force in N. A 1 B 2 C 3 D 4',
            'answer': 'B' if kind == 'mcq' else None,
            'scheme_text': 'PRIVATE source guidance', 'regions': [region],
            'context_regions': [], 'mark_scheme_regions': [{**region, 'page': 2}],
            'question_media': ['qp.png'], 'context_media': [],
            'mark_scheme_media': ['ms.png'], 'source_verified': True,
            'mastery_certified': False}


def receipt(packet, **changes):
    value = {'packet_digest': packet['digest'], 'item_id': packet['item_id'],
             'kind': packet['kind'], 'outcome': 'solved', 'answer': 'B',
             'context_complete': True, 'question_number': '2',
             'scheme_question_number': None, 'parts': [],
             'reasons': ['Computed from the supplied question.'], 'proposals': []}
    value.update(changes)
    return value


def attempt(packet, content=None, history=(), model='gpt-6-luna', error=None):
    return checks.record_attempt(packet, content, model=model, effort='medium',
                                 attempt_history=history, error=error)


def test_blind_request_binds_all_evidence_without_answer_leakage():
    original = item(); packet = checks.build_packet(original)
    plan = checks.plan_attempt(packet)
    assert plan['model'] == 'gpt-6-luna'
    assert plan['effort'] == 'low' and plan['think'] is False
    assert plan['images'] == ['qp.png']
    assert 'PRIVATE source guidance' not in plan['prompt']
    assert 'official_answer' not in plan['prompt']
    assert 'blind' in plan['prompt'].lower()
    assert plan['schema']['additionalProperties'] is False
    for mutation in ('answer', 'scheme_text', 'regions', 'question_text', 'mark_scheme_media'):
        changed = copy.deepcopy(original)
        if mutation == 'regions': changed[mutation][0]['box'][1] += .01
        else: changed[mutation] = 'changed'
        assert checks.build_packet(changed)['digest'] != packet['digest']
    original['answer'] = 'D'
    assert packet['binding']['item']['answer'] == 'B'
    packet['binding']['item']['answer'] = 'C'
    with pytest.raises(ValueError, match='binding'):
        checks.plan_attempt(packet)


def test_matching_blind_solution_is_semantic_evidence_only():
    packet = checks.build_packet(item())
    result = checks.evaluate_receipt(packet, attempt(packet, receipt(packet)))
    assert result['status'] == 'checked'
    assert result['source_verified'] is False and result['mastery_certified'] is False
    assert result['teaching_approved'] is False
    assert result['model'] == 'gpt-6-luna' and result['effort'] == 'medium'


@pytest.mark.parametrize('change', [
    {'packet_digest': '0' * 64}, {'item_id': 'other'}, {'unexpected': True},
    {'model': 'gpt-6.1-terra'}, {'context_complete': 'yes'}, {'reasons': []},
    {'question_number': '3'}, {'answer': 'E'}, {'parts': [{'id': 'a'}]},
])
def test_malformed_or_wrong_binding_receipts_fail_closed(change):
    packet = checks.build_packet(item())
    result = checks.evaluate_receipt(packet, attempt(packet, receipt(packet, **change)))
    assert result['status'] != 'checked'


def test_wrong_answer_cannot_be_repaired_by_lucky_stronger_match():
    packet = checks.build_packet(item())
    first = attempt(packet, receipt(packet, answer='A'))
    result = checks.evaluate_receipt(packet, first)
    assert result['status'] == 'escalate'
    assert checks.plan_attempt(packet, [first])['model'] == 'gpt-6.1-sol'
    assert checks.plan_attempt(packet, [first])['effort'] == 'high'
    assert checks.plan_attempt(packet, [first])['think'] is True
    second = attempt(packet, receipt(packet), [first], model='gpt-6.1-sol')
    result = checks.evaluate_receipt(packet, second, [first])
    assert result['status'] == 'hold'
    assert 'official_source_reconciliation_required' in result['reasons']


def test_uncertain_diagram_escalates_and_three_total_valid_receipts():
    packet = checks.build_packet(item())
    first = attempt(packet, receipt(packet, outcome='uncertain', context_complete=False))
    assert checks.evaluate_receipt(packet, first)['status'] == 'escalate'
    second = attempt(packet, receipt(packet, outcome='uncertain'), [first], model='gpt-6.1-sol')
    assert checks.plan_attempt(packet, [first, second])['model'] == 'gpt-6.1-terra'
    third = attempt(packet, receipt(packet), [first, second], model='gpt-6.1-terra')
    assert checks.evaluate_receipt(packet, third, [first, second])['status'] == 'checked'
    assert checks.plan_attempt(packet, [first, second, third]) is None
    with pytest.raises(ValueError, match='three'):
        attempt(packet, receipt(packet), [first, second, third])


def test_tier_history_and_attempt_binding_are_not_model_controlled():
    packet = checks.build_packet(item())
    with pytest.raises(ValueError, match='tier'):
        attempt(packet, receipt(packet), model='gpt-6.1-terra')
    first = attempt(packet, receipt(packet, outcome='uncertain'))
    other = checks.build_packet({**item(), 'question_text': 'different'})
    with pytest.raises(ValueError, match='history'):
        checks.plan_attempt(other, [first])
    with pytest.raises(ValueError, match='history'):
        checks.plan_attempt(packet, [first, first])


def lq():
    row = item('structured')
    row['required_parts'] = [{'id': 'a', 'marks': 1}, {'id': 'b', 'marks': 2}]
    return row


def lq_receipt(packet):
    parts = [{'id': p['id'], 'question_present': True, 'scheme_present': True,
              'values_match': True, 'units_match': True,
              'question_marks': p['marks'], 'scheme_marks': p['marks']}
             for p in packet['required_parts']]
    return receipt(packet, answer=None, scheme_question_number='2', parts=parts)


def test_lq_request_checks_full_private_scope_and_explicit_parts():
    packet = checks.build_packet(lq(), allowed_chapter_ids=['forces', 'vectors'])
    plan = checks.plan_attempt(packet)
    assert plan['images'] == ['qp.png', 'ms.png']
    assert 'PRIVATE source guidance' in plan['prompt']
    assert 'required_parts' in plan['prompt']
    content = lq_receipt(packet)
    content['proposals'] = [{'part_id': 'a', 'chapter_ids': ['forces'],
                             'prerequisite_ids': ['vectors'], 'status': 'unreviewed',
                             'disposition': 'proposed', 'reason': 'Forces use vectors'},
                            {'part_id': 'b', 'chapter_ids': [], 'prerequisite_ids': [],
                             'status': 'unreviewed', 'disposition': 'unresolved', 'reason': 'No supported chapter'}]
    result = checks.evaluate_receipt(packet, attempt(packet, content))
    assert result['status'] == 'checked'
    assert result['proposals'][0]['status'] == 'unreviewed'
    assert result['mapping_status'] == 'unresolved'


@pytest.mark.parametrize('fault', ['missing', 'extra', 'duplicate', 'maximum', 'units', 'values',
                                  'number', 'unknown_chapter', 'certified', 'unknown_part'])
def test_lq_incomplete_association_or_mapping_fails_closed(fault):
    packet = checks.build_packet(lq(), allowed_chapter_ids=['forces'])
    value = lq_receipt(packet)
    if fault == 'missing': value['parts'].pop()
    elif fault == 'extra': value['parts'].append({**value['parts'][0], 'id': 'c'})
    elif fault == 'duplicate': value['parts'][1]['id'] = 'a'
    elif fault == 'maximum': value['parts'][1]['scheme_marks'] = 3
    elif fault == 'units': value['parts'][0]['units_match'] = False
    elif fault == 'values': value['parts'][0]['values_match'] = False
    elif fault == 'number': value['scheme_question_number'] = '3'
    else:
        value['proposals'] = [{'part_id': 'a', 'chapter_ids': ['forces'],
                              'prerequisite_ids': [], 'status': 'unreviewed',
                              'disposition': 'proposed', 'reason': 'Source-supported proposal'}]
        if fault == 'unknown_chapter': value['proposals'][0]['chapter_ids'] = ['invented']
        if fault == 'certified': value['proposals'][0]['status'] = 'certified'
        if fault == 'unknown_part': value['proposals'][0]['part_id'] = 'invented'
    assert checks.evaluate_receipt(packet, attempt(packet, value))['status'] != 'checked'


def test_unknown_lq_part_scope_or_total_holds_and_source_holds_remain_binding():
    packet = checks.build_packet(item('structured'))
    assert checks.evaluate_receipt(packet, attempt(packet, lq_receipt(packet)))['status'] == 'hold'
    row = lq(); row['required_parts'][1]['marks'] = 3
    packet = checks.build_packet(row)
    assert checks.evaluate_receipt(packet, attempt(packet, lq_receipt(packet)))['status'] == 'hold'
    packet = checks.build_packet({**item(), 'hold_reasons': ['existing_quarantine']})
    assert checks.evaluate_receipt(packet, attempt(packet, receipt(packet)))['status'] == 'hold'


def test_replayed_real_private_item_uses_disposable_library(tmp_path, monkeypatch):
    from test_source_practice import install, module
    monkeypatch.setattr(module(), 'WORKERS', tmp_path / 'workers')
    vault, prepared = install(tmp_path)
    real = module().verify(vault, prepared)['items'][0]
    packet = checks.build_packet(real)
    plan = checks.plan_attempt(packet)
    assert real['mark_scheme_media']
    assert plan['images'] == real['context_media'] + real['question_media']
    assert not set(plan['images']) & set(real['mark_scheme_media'])


@pytest.mark.parametrize('fault', ['question_image', 'private_image', 'context_image',
                                  'source_hash', 'overlap', 'not_replayed', 'maximum'])
def test_incomplete_source_scope_cannot_be_rescued_by_confident_model(fault):
    row = item()
    if fault == 'question_image': row['question_media'] = []
    elif fault == 'private_image': row['mark_scheme_media'] = []
    elif fault == 'context_image': row['context_regions'] = copy.deepcopy(row['regions'])
    elif fault == 'source_hash': row['regions'][0].pop('source_sha256')
    elif fault == 'overlap': row['question_media'] = row['mark_scheme_media']
    elif fault == 'maximum': row['marks'] = True
    else: row['source_verified'] = False
    packet = checks.build_packet(row)
    assert checks.evaluate_receipt(packet, attempt(packet, receipt(packet)))['status'] == 'hold'


def test_attempt_content_is_copy_on_read_and_json_resume_preserves_wrong_answer():
    from dataclasses import asdict
    import json
    packet = checks.build_packet(item())
    wrong_content = receipt(packet, answer='A')
    first = attempt(packet, wrong_content)
    second = attempt(packet, receipt(packet), [first], model='gpt-6.1-sol')
    first.content['answer'] = 'B'
    first.content['reasons'].append('erase contradiction')
    wrong_content['answer'] = 'B'
    restored = checks.Attempt(**json.loads(json.dumps(asdict(first))))
    assert restored.content['answer'] == 'A'
    assert restored.content['reasons'] == ['Computed from the supplied question.']
    assert checks.evaluate_receipt(packet, second, [restored])['status'] == 'hold'
    current = second.content; current['answer'] = 'A'
    assert second.content['answer'] == 'B'


@pytest.mark.parametrize('fault', ['question_overlap', 'context_overlap', 'missing_public',
                                  'missing_private', 'missing_context', 'malformed_media'])
def test_planner_blocks_unsafe_source_scope_before_blind_launch(fault):
    row = item()
    if fault == 'question_overlap': row['question_media'] = ['ms.png']
    elif fault == 'context_overlap':
        row['context_regions'] = copy.deepcopy(row['regions']); row['context_media'] = ['ms.png']
    elif fault == 'missing_public': row['question_media'] = []
    elif fault == 'missing_private': row['mark_scheme_media'] = []
    elif fault == 'missing_context': row['context_regions'] = copy.deepcopy(row['regions'])
    else: row['context_media'] = {'private': ['ms.png']}
    packet = checks.build_packet(row)
    with pytest.raises(ValueError, match='blocked'):
        checks.plan_attempt(packet)


def test_written_request_requires_every_part_mapping_or_explicit_unresolved():
    packet = checks.build_packet(lq(), allowed_chapter_ids=['forces'])
    request = checks.plan_attempt(packet)
    assert 'every required part' in request['prompt'].lower()
    assert 'unresolved' in request['prompt'].lower()
    assert {part['id'] for part in packet['required_parts']} == {'a', 'b'}
    content = lq_receipt(packet)
    result = checks.evaluate_receipt(packet, attempt(packet, content))
    assert result['status'] == 'checked'
    assert result['mapping_status'] == 'incomplete'
    assert {p['part_id'] for p in result['proposals']} == {'a', 'b'}
    assert all(p['disposition'] == 'unresolved' for p in result['proposals'])


def test_written_mapping_dispositions_complete_unresolved_and_duplicate():
    packet = checks.build_packet(lq(), allowed_chapter_ids=['forces'])
    content = lq_receipt(packet)
    content['proposals'] = [
        {'part_id': 'a', 'chapter_ids': ['forces'], 'prerequisite_ids': [],
         'status': 'unreviewed', 'disposition': 'proposed', 'reason': 'Force calculation'},
        {'part_id': 'b', 'chapter_ids': [], 'prerequisite_ids': [],
         'status': 'unreviewed', 'disposition': 'unresolved', 'reason': 'Graph has no matching chapter'},
    ]
    result = checks.evaluate_receipt(packet, attempt(packet, content))
    assert result['status'] == 'checked' and result['mapping_status'] == 'unresolved'
    content['proposals'][1] = copy.deepcopy(content['proposals'][0])
    result = checks.evaluate_receipt(packet, attempt(packet, content))
    assert result['mapping_status'] == 'incomplete'
    assert any('duplicate' in reason for reason in result['mapping_reasons'])


def test_empty_allowed_graph_is_explicitly_unresolved_without_hallucination():
    packet = checks.build_packet(lq())
    content = lq_receipt(packet)
    result = checks.evaluate_receipt(packet, attempt(packet, content))
    assert result['status'] == 'checked'
    assert result['mapping_status'] == 'unresolved'
    assert len(result['proposals']) == 2
    assert all(p['chapter_ids'] == p['prerequisite_ids'] == [] for p in result['proposals'])
    assert all(p['status'] == 'unreviewed' and p['disposition'] == 'unresolved' for p in result['proposals'])


@pytest.mark.parametrize('malformed', [float('nan'), float('inf'), float('-inf'), {1, 2}, b'invalid-json'])
def test_noncanonical_provider_payload_is_recorded_and_consumes_all_three_attempts(malformed):
    from dataclasses import asdict
    import json
    packet = checks.build_packet(item())
    history = []
    for number, model in enumerate(checks.MODELS, 1):
        content = receipt(packet, reasons=[malformed])
        envelope = attempt(packet, content, history, model=model)
        restored = checks.Attempt(**json.loads(json.dumps(asdict(envelope), allow_nan=False)))
        assert restored.number == number
        assert isinstance(restored.content['raw_payload_text'], str)
        assert restored.content['raw_payload_text']
        result = checks.evaluate_receipt(packet, restored, history)
        assert result['status'] == ('escalate' if number < 3 else 'hold')
        assert 'invalid_receipt' in result['reasons']
        history.append(restored)
        if number < 3:
            assert checks.plan_attempt(packet, history)['model'] == checks.MODELS[number]
    assert checks.plan_attempt(packet, history) is None
    with pytest.raises(ValueError, match='three'):
        attempt(packet, receipt(packet), history, model='gpt-6.1-terra')


def test_malformed_payload_preserves_bound_wrong_answer_poison_after_resume():
    from dataclasses import asdict
    import json
    packet = checks.build_packet(item())
    first = attempt(packet, receipt(packet, answer='A', reasons=[float('nan')]))
    first = checks.Attempt(**json.loads(json.dumps(asdict(first), allow_nan=False)))
    assert first.content['answer'] == 'A'
    assert 'NaN' in first.content['raw_payload_text']
    first.content['answer'] = 'B'
    second = attempt(packet, receipt(packet), [first], model='gpt-6.1-sol')
    result = checks.evaluate_receipt(packet, second, [first])
    assert result['status'] == 'hold'
    assert 'official_source_reconciliation_required' in result['reasons']


@pytest.mark.parametrize('kind', ['mcq', 'structured', 'written'])
def test_verification_schema_survives_codex_strict_adapter_without_unsupported_keywords(kind):
    from tutor_app.codex_ai import _strict_schema
    packet = checks.build_packet(item() if kind == 'mcq' else {**lq(), 'kind': kind})
    schema = _strict_schema(checks.plan_attempt(packet)['schema'])
    wire_keywords = {'type', 'properties', 'required', 'additionalProperties', 'items', 'enum'}
    def verify(node):
        if isinstance(node, dict):
            if 'type' in node:
                assert set(node) <= wire_keywords
                if node['type'] == 'object':
                    assert node['additionalProperties'] is False
                    assert set(node['required']) == set(node['properties'])
            assert 'uniqueItems' not in node
            for value in node.values(): verify(value)
        elif isinstance(node, list):
            for value in node: verify(value)
    verify(schema)


@pytest.mark.parametrize('fault', ['duplicate_chapter', 'duplicate_prerequisite',
                                  'empty_reason', 'empty_reasons', 'negative_marks'])
def test_wire_simplification_keeps_local_receipt_constraints(fault):
    packet = checks.build_packet(lq(), allowed_chapter_ids=['forces'])
    content = lq_receipt(packet)
    content['proposals'] = [
        {'part_id': part_id, 'chapter_ids': ['forces'], 'prerequisite_ids': [],
         'status': 'unreviewed', 'disposition': 'proposed', 'reason': 'Source supported'}
        for part_id in ('a', 'b')
    ]
    if fault == 'duplicate_chapter': content['proposals'][0]['chapter_ids'] = ['forces', 'forces']
    elif fault == 'duplicate_prerequisite': content['proposals'][0]['prerequisite_ids'] = ['forces', 'forces']
    elif fault == 'empty_reason': content['proposals'][0]['reason'] = ''
    elif fault == 'empty_reasons': content['reasons'] = []
    else: content['parts'][0]['question_marks'] = -1
    assert checks.evaluate_receipt(packet, attempt(packet, content))['status'] != 'checked'


def test_failed_codex_transport_is_terminal_after_persisted_resume_and_later_match(tmp_path, monkeypatch):
    import asyncio
    from dataclasses import asdict
    import json
    from tutor_app.codex_ai import CodexAI
    packet = checks.build_packet(item())
    bad = receipt(packet, answer='A'); bad.pop('reasons')
    monkeypatch.setenv('FAKE_CODEX_LOG', str(tmp_path / 'requests.jsonl'))
    monkeypatch.setenv('FAKE_CODEX_MODE', 'ok')
    monkeypatch.setenv('FAKE_CODEX_REPLY', json.dumps(bad))
    client = CodexAI('Source check', binary=str(Path(__file__).parent / 'app/fake_codex.py'))
    async def go():
        try:
            return await client.one_shot('Blind check', schema=checks._schema(packet), model='codex:gpt-6-luna')
        finally:
            await client.close()
    data, status = asyncio.run(go())
    assert data is None and status.ok is False
    first = checks.record_attempt(packet, data, model='gpt-6-luna', effort='low', error=status.message)
    resumed = checks.Attempt(**json.loads(json.dumps(asdict(first))))
    result = checks.evaluate_receipt(packet, resumed)
    assert result['status'] == 'hold'
    assert 'provider_transport_failure_requires_reconciliation' in result['reasons']
    assert checks.plan_attempt(packet, [resumed]) is None
    second = checks.record_attempt(packet, receipt(packet), model='gpt-6.1-sol', effort='high', attempt_history=[resumed])
    result = checks.evaluate_receipt(packet, second, [resumed])
    assert result['status'] == 'hold'
    assert 'provider_transport_failure_requires_reconciliation' in result['reasons']
    assert checks.plan_attempt(packet, [resumed, second]) is None
    assert len((tmp_path / 'requests.jsonl').read_text().splitlines()) == 1


@pytest.mark.parametrize('state_status,has_error', [('held_provider_infrastructure', False),
                                                  ('ready', True), ('hold', True)])
def test_worker_resume_preserves_durable_provider_hold_without_launch(tmp_path, monkeypatch, state_status, has_error):
    import asyncio
    from dataclasses import asdict
    import importlib.util
    import json
    from types import SimpleNamespace
    root = Path(__file__).resolve().parents[2]
    path = root / 'Work/Workers/extraction/overnight-20261105-10pct/check_current.py'
    # The runner imports its sibling modules (native_nested_parts, prepared_source_packet) by bare name, which only
    # resolves when it is started as a script; loading it by path needs its own directory on sys.path.
    monkeypatch.syspath_prepend(str(path.parent))
    spec = importlib.util.spec_from_file_location('overnight_transport_hold_test_runner', path)
    worker = importlib.util.module_from_spec(spec); spec.loader.exec_module(worker)
    row = item(); packet = checks.build_packet(row)
    r = tmp_path / 'worker'; dest = r / 'semantic-checks' / packet['digest']; dest.mkdir(parents=True)
    entries = []
    if has_error:
        envelope = attempt(packet, None, error='transport lost parsed evidence')
        entries = [{'envelope': asdict(envelope), 'result': {'status': 'escalate'}, 'seconds': 1}]
    state = {'qid': row['id'], 'collection': 'test-release', 'packet_digest': packet['digest'],
             'status': state_status, 'attempts': entries}
    (dest / 'state.json').write_text(json.dumps(state))
    monkeypatch.setattr(worker, 'ROOT', tmp_path)
    monkeypatch.setattr(worker, 'R', r)
    monkeypatch.setattr(worker, 'Collection', lambda _: SimpleNamespace(release='test-release', _items={row['id']: row}))
    def forbidden(*args, **kwargs): raise AssertionError('provider/usage must not be constructed on held resume')
    monkeypatch.setattr(worker, 'CodexAI', forbidden)
    monkeypatch.setattr(worker, 'codex_usage', forbidden)
    asyncio.run(worker.main(row['id']))
    saved = json.loads((dest / 'state.json').read_bytes())
    assert saved['status'] == 'held_provider_infrastructure'
    assert saved['attempts'] == entries
    assert 'provider_transport_failure_requires_reconciliation' in saved['hold_reasons']
