"""The local reviewed bank never resets exposure or supplies help to no-hints checks."""
import copy
import json
import random
from datetime import datetime

import pytest

from fixtures import make_vault
from tutorlib import model, packs, session, store, views

TARGET = '9702-2.1'
OTHER = '9702-3.1'
THIRD = '9702-4.1'
KC = TARGET + '.1'


def bank_vault(tmp_path):
    root = make_vault(tmp_path)
    path = root / '.tutor/packs/v1/specs/9702/graph.json'
    graph = json.loads(path.read_text())
    for sub in (OTHER, THIRD):
        graph['subtopics'].append({'id': sub, 'title': sub, 'topic': '9702-2'})
        graph['kcs'].append({'id': sub + '.1', 'subtopic': sub, 'title': sub, 'level': 'AS', 'type': 'conceptual', 'prereqs': []})
    path.write_text(json.dumps(graph))
    return root


def item(**changes):
    result = {'id': 'topical-one', 'kcs': [KC], 'kind': 'mcq', 'difficulty': 3, 'marks': 1,
              'source': {'type': 'past', 'qid': '9702_s23_22_q2', 'ref': 'CAIE 9702 · Jun 2023 · P22 · Q2'},
              'stem': 'Choose the vector.', 'options': {'A': 'distance', 'B': 'displacement', 'C': 'speed', 'D': 'time'},
              'answer': 'B', 'topical': {'reviewed': True, 'requires': [TARGET, OTHER], 'support': {OTHER: 'A reviewed prerequisite fact.'},
                                        'chapters': [TARGET], 'revision': '2025-2027'}}
    result.update(changes)
    return result


def publish(root, items, version='one'):
    base = root / '.tutor/topicals'
    (base / version).mkdir(parents=True)
    (base / version / 'bank.json').write_text(json.dumps({'format_version': 1, 'syllabus_versions': {'9702': '2025-2027'}, 'items': items}))
    (base / 'CURRENT').write_text(version)


def tutor_for(root):
    return session.Tutor(store.Vault(root), rng=random.Random(0), now=lambda: datetime.fromisoformat('2026-10-27T12:00:00+08:00'))


def test_no_bank_preserves_pack_questions(tmp_path):
    p = packs.Packs(store.Vault(make_vault(tmp_path)))
    assert len(p.items_for(KC)) == 2


def test_catalogued_question_media_resolves_legacy_bank_alias_without_changing_bank(tmp_path):
    from tutorlib.asset_library import write_asset
    root = bank_vault(tmp_path)
    (root / '.tutor/packs/v1/papers.json').write_text('{"papers": []}')
    relative = 'Library/Courses/9702/Questions/Media/question.png'
    write_asset(root, relative, b'question bytes', aliases=['Assets/topicals/question.png'])
    publish(root, [item(image='Assets/topicals/question.png')])
    bank_path = root / '.tutor/topicals/one/bank.json'
    before = bank_path.read_bytes()
    p = packs.Packs(store.Vault(root))
    assert not p.topical_errors
    assert p.topicals.items[0]['image'] == relative
    assert p.topicals.items[0]['source']['qid'] == '9702_s23_22_q2'
    assert bank_path.read_bytes() == before
    (root / relative).write_bytes(b'tampered')
    damaged = packs.Packs(store.Vault(root))
    assert damaged.topical_errors and not damaged.topicals.items


def test_catalog_present_rejects_uncatalogued_legacy_question_media(tmp_path):
    from tutorlib.asset_library import write_asset
    root = bank_vault(tmp_path)
    (root / '.tutor/packs/v1/papers.json').write_text('{"papers": []}')
    write_asset(root, 'Library/Courses/9702/Questions/Media/registered.png', b'question')
    legacy = root / 'Assets/topicals/unregistered.png'
    legacy.parent.mkdir(parents=True)
    legacy.write_bytes(b'existing legacy image')
    publish(root, [item(image='Assets/topicals/unregistered.png')])
    p = packs.Packs(store.Vault(root))
    assert not p.topicals.items
    assert 'unknown asset reference' in p.topical_errors[0]


def test_runtime_prefers_registered_canonical_release_and_preserves_legacy_bytes(tmp_path):
    from tutorlib.asset_library import write_asset
    root = bank_vault(tmp_path)
    (root / '.tutor/packs/v1/papers.json').write_text('{"papers": []}')
    publish(root, [item(id='legacy-bank-item')])
    legacy = root / '.tutor/topicals/one/bank.json'
    before = legacy.read_bytes()
    data = {'format_version':1,'syllabus_versions':{'9702':'2025-2027'},'items':[item(id='canonical-bank-item')]}
    relative = 'Library/Shared/Topicals/Releases/one/bank.json'
    write_asset(root, relative, json.dumps(data).encode())
    p = packs.Packs(store.Vault(root))
    assert not p.topical_errors
    assert p.topicals.items[0]['id'] == 'canonical-bank-item'
    assert legacy.read_bytes() == before
    (root / relative).write_bytes(b'corrupt canonical bank')
    broken = packs.Packs(store.Vault(root))
    assert not broken.topicals.items
    assert 'digest mismatch' in broken.topical_errors[0]


def test_migrated_bank_resolves_old_library_relative_source_only_through_declared_alias(tmp_path):
    import hashlib
    from tutorlib.asset_library import write_asset
    root = bank_vault(tmp_path)
    (root / '.tutor/packs/v1/papers.json').write_text('{"papers": []}')
    bare = 'Physics 9702 AS Topicals/question-source.pdf'
    canonical = 'Library/Courses/9702/Sources/Library/Physics 9702 AS Topicals/question-source.pdf'
    data = b'%PDF-1.4 synthetic source'
    write_asset(root, canonical, data, aliases=['sources/library/' + bare])
    original = item(source={'type':'past','qid':'9702_s23_22_q2','ref':'Original question reference',
                           'library':{'file':bare,'page':7,'box':[20,30,40,50]},
                           'mark_scheme':{'file':bare,'page':9},
                           'sha256':hashlib.sha256(data).hexdigest()})
    publish(root, [original])
    bank = root / '.tutor/topicals/one/bank.json'
    before = bank.read_bytes()
    p = packs.Packs(store.Vault(root))
    assert not p.topical_errors
    mapped = p.topicals.items[0]
    assert mapped['source']['library'] == {'file':canonical,'page':7,'box':[20,30,40,50]}
    assert mapped['source']['mark_scheme'] == {'file':canonical,'page':9}
    assert mapped['source']['sha256'] == original['source']['sha256']
    assert mapped['source']['ref'] == 'Original question reference' and mapped['id'] == original['id']
    assert bank.read_bytes() == before
    (root / canonical).write_bytes(b'corrupt source')
    assert 'digest mismatch' in packs.Packs(store.Vault(root)).topical_errors[0]


@pytest.mark.parametrize('source', ['../outside.pdf','Library/missing.pdf','Physics 9702 AS Topicals/unknown.pdf'])
def test_source_provenance_adapter_never_searches_disk_for_unknown_paths(tmp_path, source):
    from tutorlib.asset_library import write_asset
    root = bank_vault(tmp_path)
    (root / '.tutor/packs/v1/papers.json').write_text('{"papers": []}')
    write_asset(root, 'Library/Shared/Sources/registered.pdf', b'%PDF fixture')
    publish(root, [item(source={'type':'past','qid':'9702_s23_22_q2','library':{'file':source,'page':1}})])
    p = packs.Packs(store.Vault(root))
    assert p.topical_errors and not p.topicals.items


def test_local_bank_adds_questions_without_mutating_pack(tmp_path):
    root = bank_vault(tmp_path)
    publish(root, [item()])
    p = packs.Packs(store.Vault(root))
    assert any(i['id'] == 'topical-one' for i in p.items_for(KC))
    assert not any(i['id'] == 'topical-one' for i in p.pack(TARGET)['items'])


def test_canonical_alias_overlay_preserves_existing_id_and_freshness(tmp_path):
    root = bank_vault(tmp_path)
    # This canonical reference already exists as a numeric chapter question.
    imported = item(kcs=[TARGET + '.4'], source={'type': 'past', 'qid': '9702_s23_22_q2', 'part': 'a'})
    publish(root, [imported])
    p = packs.Packs(store.Vault(root))
    found = [i for i in p.items_for(TARGET + '.4') if i.get('topical')]
    assert len(found) == 1 and found[0]['id'] == '9702-2.1-i03'
    assert found[0]['kind'] == 'numeric'  # canonical original is preserved
    s = model.new_state()
    s['items_seen']['9702-2.1-i03'] = '2026-10-27T12:00:00+08:00'
    assert p.select_item(TARGET + '.4', s, .5, random.Random(0), kinds=('numeric',))['id'] != found[0]['id']


@pytest.mark.parametrize('damage', ['json', 'pointer', 'utf8', 'revision', 'unknown', 'unreviewed', 'key', 'path'])
def test_bad_bank_fails_closed_without_breaking_legacy_content(tmp_path, damage):
    root = bank_vault(tmp_path)
    it = item()
    if damage == 'revision': it['topical']['revision'] = '2028-2030'
    if damage == 'unknown': it['topical']['requires'] = ['9702-99.1']
    if damage == 'unreviewed': it['topical']['reviewed'] = False
    if damage == 'key': it['answer'] = 'Z'
    if damage == 'path': it['image'] = '../private.png'
    publish(root, [it])
    if damage == 'json': (root / '.tutor/topicals/one/bank.json').write_text('{')
    if damage == 'pointer': (root / '.tutor/topicals/CURRENT').write_text('../packs/v1')
    if damage == 'utf8': (root / '.tutor/topicals/CURRENT').write_bytes(b'\xff')
    p = packs.Packs(store.Vault(root))
    assert not any(i['id'] == 'topical-one' for i in p.items_for(KC))
    assert p.topical_errors
    assert len(p.items_for(KC)) == 2


def test_support_recomputed_by_serving_chapter_and_counts_as_assistance(tmp_path):
    root = bank_vault(tmp_path)
    publish(root, [item()])
    t = tutor_for(root)
    t.start('review')
    it = next(i for i in t.packs.items_for(KC) if i.get('topical'))
    q = t._present(it, 'practice', None, serving_chapter=TARGET)
    assert q['support'] == {OTHER: 'A reviewed prerequisite fact.'}
    p = t.session['presented'][str(q['n'])]
    assert p['hinted'] and p['kcs'] == [KC]
    t.answer(f"{q['n']}B4")
    assert not t.state['kcs'][KC]['succ_days']
    t.log({'type': 'chapter_started', 'chapter': OTHER})
    q = t._present(it, 'practice', None, serving_chapter=TARGET)
    assert not q.get('support')
    assert not t.session['presented'][str(q['n'])]['hinted']
    assert 'support' not in it  # shared source is untouched


def test_metadata_check_in_unassisted_question_has_no_hint_or_grade(tmp_path):
    root = bank_vault(tmp_path)
    it = item()
    it['topical']['requires'] = [TARGET]
    publish(root, [it])
    t = tutor_for(root)
    t.start('review')
    q = t._present(it, 'exit', None, unassisted=True, serving_chapter=TARGET)
    result = t.check_solvable(q['n'])
    assert result['status'] == 'solvable' and result['topics'] == ['2.1']
    assert not t.session['presented'][str(q['n'])]['hinted']
    assert t.session['answered'] == 0
    assert 'answer' not in result and 'support' not in result
    assert not any(e['type'] == 'answer' for e in t.vault.events())


def test_unassisted_missing_prerequisite_skips_even_with_safe_support(tmp_path):
    root = bank_vault(tmp_path)
    t = tutor_for(root)
    t.start('review')
    t.packs.pack(TARGET)['items'] = []  # no independently eligible replacement exists
    assert t._questions({'kind': 'exit', 'kc': KC}, 0, [item()], unassisted=True) is None
    assert not t.session['presented'] and t.session['answered'] == 0


def test_retry_reports_missing_prerequisite_without_revealing_answer(tmp_path):
    root = bank_vault(tmp_path)
    t = tutor_for(root)
    t.start('lesson', focus=[TARGET])
    t.log({'type': 'chapter_started', 'chapter': OTHER})
    question = t._present(item(), 'exit', None, unassisted=True, serving_chapter=TARGET)
    assert question is not None
    t.answer(f"{question['n']}?")
    # Model a changed progress record: the question is no longer eligible.
    t.state['started_chapters'] = [TARGET]
    retry = t.retry_skipped()
    assert retry['activity'] == 'error'
    assert retry['missing_chapters'] == [OTHER]
    assert 'displacement' not in str(retry)
    assert t.session['skipped_answer_guards']


def test_supported_retry_never_exposes_another_skipped_answer(tmp_path):
    root = bank_vault(tmp_path)
    t = tutor_for(root)
    t.start('lesson', focus=[TARGET])
    t.log({'type': 'chapter_started', 'chapter': OTHER})
    first = {'id': 'guarded-square', 'kcs': [KC], 'kind': 'mcq', 'difficulty': 2, 'marks': 1,
             'stem': 'Which statement is true?', 'options': {'A': 'A square has four sides', 'B': 'Other'}, 'answer': 'A'}
    second = item()
    second['topical']['support'][OTHER] = 'A square has four sides'
    a = t._present(first, 'practice', None)
    t.answer(f"{a['n']}?")
    b = t._present(second, 'practice', None, serving_chapter=TARGET)
    t.answer(f"{b['n']}?")
    t.state['started_chapters'] = [TARGET]
    guarded = next(key for key, g in t.session['skipped_answer_guards'].items()
                   if g['question']['item'] == second['id'])
    result = t.retry_skipped(guard_id=guarded)
    assert result['activity'] == 'error'
    assert 'A square has four sides' not in str(result)
    assert len(t.session['skipped_answer_guards']) == 2
    first_guard = next(key for key, g in t.session['skipped_answer_guards'].items()
                       if g['question']['item'] == first['id'])
    retry_first = t.retry_skipped(guard_id=first_guard)
    assert retry_first['activity'] == 'questions'
    t.answer(f"{retry_first['items'][0]['n']}A3")
    retry_second = t.retry_skipped(guard_id=guarded)
    assert retry_second['activity'] == 'questions'
    assert retry_second['items'][0]['support'][OTHER] == 'A square has four sides'


def test_mutually_guarded_supported_retries_offer_only_ungraded_text_attempt(tmp_path):
    root = bank_vault(tmp_path)
    t = tutor_for(root)
    t.start('lesson', focus=[TARGET])
    t.log({'type': 'chapter_started', 'chapter': OTHER})
    for question in (item(id='guard-a'), item(id='guard-b', source={'type': 'past', 'qid': '9702_s23_22_q3'})):
        view = t._present(question, 'practice', None, serving_chapter=TARGET)
        t.answer(f"{view['n']}?")
    t.state['started_chapters'] = [TARGET]
    assert not t.skipped_retry_available()
    assert t.retry_skipped()['activity'] == 'error'
    candidate = t.ungraded_retry_candidate()
    assert candidate
    retry = t.retry_skipped_ungraded(candidate['guard'])
    assert retry['activity'] == 'questions' and not retry['items'][0].get('support')
    t.answer(f"{retry['items'][0]['n']}B3")
    assert len(t.session['skipped_answer_guards']) == 1
    second = t.retry_skipped()
    assert second['activity'] == 'questions' and second['items'][0]['support']
    t.answer(f"{second['items'][0]['n']}B3")
    assert not t.session['skipped_answer_guards']


def test_unavailable_structured_retry_preserves_written_attempt_without_marking(tmp_path):
    root = bank_vault(tmp_path)
    t = tutor_for(root)
    t.start('lesson', focus=[TARGET])
    q = item(id='structured-guard', kind='structured', stem='Explain your reasoning.',
             scheme=[{'mark': 'B1', 'point': 'An explanation.'}])
    q.pop('options'); q.pop('answer')
    q['topical']['requires'] = [TARGET]; q['topical']['support'] = {}
    view = t._present(q, 'practice', None, serving_chapter=TARGET)
    t.answer(f"{view['n']}?")
    t.log({'type': 'topical_exclude', 'identity': '9702_s23_22_q2', 'chapter': TARGET,
           'missing': [], 'reason': 'Excluded for this chapter.'})
    candidate = t.ungraded_retry_candidate()
    assert candidate and candidate['item'] == 'structured-guard'
    retry = t.retry_skipped_ungraded(candidate['guard'])
    assert retry['activity'] == 'questions'
    n = retry['items'][0]['n']
    for no_work in ('', 'I do not know', 'done on paper'):
        assert not t.save_ungraded_structured(n, no_work)['ok']
    result = t.save_ungraded_structured(n, 'I drew a free-body diagram and resolved the forces.')
    assert result['ok'] and result['attempt_saved']
    assert not t.session['skipped_answer_guards']
    assert t.session['deferred_judgments'][0]['saved_work'].startswith('I drew')
    assert not [e for e in t.vault.events() if e['type'] == 'answer' and e.get('item') == q['id'] and e.get('key')]
    restored = tutor_for(root)
    assert restored.session['deferred_judgments'][0]['saved_work'].startswith('I drew')
    assert restored.restore_topical(identity='9702_s23_22_q2', chapter=TARGET)['ok']
    pending = restored.next()
    assert pending['activity'] == 'questions' and pending['items'][0]['saved_work'].startswith('I drew')
    n = pending['items'][0]['n']
    assert restored.scheme(n)['scheme'][0]['point'] == 'An explanation.'
    marked = restored.answer(f'{n} pts=1')
    assert marked['results'][0]['correct']


def test_structured_ungraded_attempt_recovers_after_event_write(tmp_path, monkeypatch):
    from tutorlib import deferred_notes
    root = bank_vault(tmp_path)
    t = tutor_for(root)
    t.start('lesson', focus=[TARGET])
    q = item(id='structured-recovery', kind='structured', stem='Explain.',
             scheme=[{'mark': 'B1', 'point': 'An explanation.'}])
    q.pop('options'); q.pop('answer')
    q['topical']['requires'] = [TARGET]; q['topical']['support'] = {}
    view = t._present(q, 'practice', None, serving_chapter=TARGET)
    t.answer(f"{view['n']}?")
    retry = t.retry_skipped_ungraded()
    original = deferred_notes.resolve
    def interrupted(*args, **kwargs):
        raise OSError('simulated interruption after event')
    monkeypatch.setattr(deferred_notes, 'resolve', interrupted)
    with pytest.raises(OSError):
        t.save_ungraded_structured(retry['items'][0]['n'], 'I resolved the forces vertically.')
    monkeypatch.setattr(deferred_notes, 'resolve', original)
    recovered = tutor_for(root)
    assert not recovered.session['skipped_answer_guards']
    assert [p['saved_work'] for p in recovered.session['deferred_judgments']] == ['I resolved the forces vertically.']
    again = tutor_for(root)
    assert len(again.session['deferred_judgments']) == 1


def test_structured_attempt_retries_after_guard_store_failure_without_duplicate_event(tmp_path, monkeypatch):
    from tutorlib import deferred_notes
    root = bank_vault(tmp_path)
    t = tutor_for(root)
    t.start('lesson', focus=[TARGET])
    q = item(id='structured-retry-event', kind='structured', stem='Explain.',
             scheme=[{'mark': 'B1', 'point': 'An explanation.'}])
    q.pop('options'); q.pop('answer')
    q['topical']['requires'] = [TARGET]; q['topical']['support'] = {}
    view = t._present(q, 'practice', None, serving_chapter=TARGET)
    t.answer(f"{view['n']}?")
    retry = t.retry_skipped_ungraded(); n = retry['items'][0]['n']
    original = deferred_notes.resolve
    monkeypatch.setattr(deferred_notes, 'resolve', lambda *args: (_ for _ in ()).throw(OSError('interrupted')))
    with pytest.raises(OSError):
        t.save_ungraded_structured(n, 'Working saved once.')
    monkeypatch.setattr(deferred_notes, 'resolve', original)
    with pytest.raises(ValueError):
        t.save_ungraded_structured(n, 'Different working.')
    assert not t.cancel_ungraded_structured(n, 'Draft')['ok']
    result = t.save_ungraded_structured(n, 'Working saved once.')
    assert result['ok'] and result['attempt_saved']
    events = [e for e in t.vault.events() if e['type'] == 'ungraded_retry' and e['item'] == q['id']]
    assert len(events) == 1
    assert len(t.session['deferred_judgments']) == 1


def test_end_recovers_inflight_structured_attempt_before_session_replacement(tmp_path, monkeypatch):
    from tutorlib import deferred_notes
    root = bank_vault(tmp_path)
    t = tutor_for(root); t.start('lesson', focus=[TARGET])
    q = item(id='structured-end-event', kind='structured', stem='Explain.',
             scheme=[{'mark': 'B1', 'point': 'An explanation.'}])
    q.pop('options'); q.pop('answer')
    q['topical']['requires'] = [TARGET]; q['topical']['support'] = {}
    view = t._present(q, 'practice', None, serving_chapter=TARGET); t.answer(f"{view['n']}?")
    retry = t.retry_skipped_ungraded(); n = retry['items'][0]['n']
    original = deferred_notes.resolve
    monkeypatch.setattr(deferred_notes, 'resolve', lambda *args: (_ for _ in ()).throw(OSError('interrupted')))
    with pytest.raises(OSError):
        t.save_ungraded_structured(n, 'Committed working.')
    assert t.end().get('error')
    monkeypatch.setattr(deferred_notes, 'resolve', original)
    assert t.start('lesson', focus=[TARGET], replace=True).get('error')
    assert t.session['deferred_judgments'][0]['saved_work'] == 'Committed working.'
    assert len([e for e in t.vault.events() if e['type'] == 'ungraded_retry']) == 1


def test_structured_attempt_retries_after_final_session_save_failure(tmp_path, monkeypatch):
    root = bank_vault(tmp_path)
    t = tutor_for(root); t.start('lesson', focus=[TARGET])
    q = item(id='structured-final-save', kind='structured', stem='Explain.',
             scheme=[{'mark': 'B1', 'point': 'An explanation.'}])
    q.pop('options'); q.pop('answer')
    q['topical']['requires'] = [TARGET]; q['topical']['support'] = {}
    view = t._present(q, 'practice', None, serving_chapter=TARGET); t.answer(f"{view['n']}?")
    retry = t.retry_skipped_ungraded(); n = retry['items'][0]['n']
    original = t._save
    def interrupted():
        if t.session.get('deferred_judgments') and not t.session.get('presented'):
            raise OSError('final write failed')
        original()
    monkeypatch.setattr(t, '_save', interrupted)
    with pytest.raises(OSError):
        t.save_ungraded_structured(n, 'Original working.')
    assert str(n) in t.session['presented'] and t.session['skipped_answer_guards']
    monkeypatch.setattr(t, '_save', original)
    result = t.save_ungraded_structured(n, 'Original working.')
    assert result['attempt_saved'] and len(t.session['deferred_judgments']) == 1
    assert len([e for e in t.vault.events() if e['type'] == 'ungraded_retry']) == 1


def test_skipping_an_inflight_ungraded_retry_recovers_the_committed_attempt(tmp_path, monkeypatch):
    from tutorlib import deferred_notes
    root = bank_vault(tmp_path)
    t = tutor_for(root); t.start('lesson', focus=[TARGET])
    q = item(id='mcq-inflight'); q['topical']['requires'] = [TARGET]; q['topical']['support'] = {}
    view = t._present(q, 'practice', None, serving_chapter=TARGET); t.answer(f"{view['n']}?")
    retry = t.retry_skipped_ungraded(); n = retry['items'][0]['n']
    original = deferred_notes.resolve
    monkeypatch.setattr(deferred_notes, 'resolve', lambda *args: (_ for _ in ()).throw(OSError('interrupted')))
    with pytest.raises(OSError):
        t.answer(f'{n}B3')
    monkeypatch.setattr(deferred_notes, 'resolve', original)
    result = t.answer(f'{n}?')
    assert result['results'][0]['attempt_saved']
    assert t.session['deferred_judgments'][0]['saved_work'] == 'B'
    assert len([e for e in t.vault.events() if e['type'] == 'ungraded_retry']) == 1
    assert tutor_for(root).session['deferred_judgments'][0]['saved_work'] == 'B'


def test_inflight_ungraded_attempt_cannot_be_suspended_and_renumbered(tmp_path, monkeypatch):
    from tutorlib import deferred_notes
    root = bank_vault(tmp_path)
    t = tutor_for(root); t.start('lesson', focus=[TARGET])
    q = item(id='mcq-suspend-inflight'); q['topical']['requires'] = [TARGET]; q['topical']['support'] = {}
    view = t._present(q, 'practice', None, serving_chapter=TARGET); t.answer(f"{view['n']}?")
    retry = t.retry_skipped_ungraded(); n = retry['items'][0]['n']
    original = deferred_notes.resolve
    monkeypatch.setattr(deferred_notes, 'resolve', lambda *args: (_ for _ in ()).throw(OSError('interrupted')))
    with pytest.raises(OSError):
        t.answer(f'{n}B3')
    monkeypatch.setattr(deferred_notes, 'resolve', original)
    assert not t.suspend_questions_for_retry()['ok']
    assert str(n) in t.session['presented']
    restored = tutor_for(root)
    assert restored.session['deferred_judgments'][0]['saved_work'] == 'B'
    assert len([e for e in restored.vault.events() if e['type'] == 'ungraded_retry']) == 1


def test_cancel_structured_draft_recovers_if_guard_store_write_fails(tmp_path, monkeypatch):
    from tutorlib import deferred_notes
    root = bank_vault(tmp_path)
    t = tutor_for(root)
    t.start('lesson', focus=[TARGET])
    q = item(id='structured-cancel-recovery', kind='structured', stem='Explain.',
             scheme=[{'mark': 'B1', 'point': 'An explanation.'}])
    q.pop('options'); q.pop('answer')
    q['topical']['requires'] = [TARGET]; q['topical']['support'] = {}
    view = t._present(q, 'practice', None, serving_chapter=TARGET)
    t.answer(f"{view['n']}?")
    deferred_notes.defer(t.vault.tutor / 'state' / 'deferred-notes.json', 'note', TARGET,
                         {'kc': KC, 'note': 'private'}, t.session['skipped_answer_guards'])
    t.log({'type': 'topical_exclude', 'identity': '9702_s23_22_q2', 'chapter': TARGET,
           'missing': [], 'reason': 'Excluded for this chapter.'})
    retry = t.retry_skipped_ungraded()
    original = deferred_notes.hold
    monkeypatch.setattr(deferred_notes, 'hold', lambda *args: (_ for _ in ()).throw(OSError('interrupted')))
    with pytest.raises(OSError):
        t.cancel_ungraded_structured(retry['items'][0]['n'], 'Draft working.')
    monkeypatch.setattr(deferred_notes, 'hold', original)
    recovered = tutor_for(root)
    recovered.end()
    recovered.start('lesson', focus=[TARGET])
    again = recovered.retry_skipped_ungraded()
    assert again['items'][0]['saved_work'] == 'Draft working.'


def test_cancel_structured_draft_is_not_lost_if_same_process_replaces_session(tmp_path, monkeypatch):
    from tutorlib import deferred_notes
    root = bank_vault(tmp_path)
    t = tutor_for(root)
    t.start('lesson', focus=[TARGET])
    q = item(id='structured-cancel-same-process', kind='structured', stem='Explain.',
             scheme=[{'mark': 'B1', 'point': 'An explanation.'}])
    q.pop('options'); q.pop('answer')
    q['topical']['requires'] = [TARGET]; q['topical']['support'] = {}
    view = t._present(q, 'practice', None, serving_chapter=TARGET)
    t.answer(f"{view['n']}?")
    retry = t.retry_skipped_ungraded()
    original = deferred_notes.hold
    monkeypatch.setattr(deferred_notes, 'hold', lambda *args: (_ for _ in ()).throw(OSError('interrupted')))
    with pytest.raises(OSError):
        t.cancel_ungraded_structured(retry['items'][0]['n'], 'Draft working.')
    assert t.end().get('error')
    assert t.start('lesson', focus=[TARGET], replace=True).get('error')
    monkeypatch.setattr(deferred_notes, 'hold', original)
    assert 'session' in t.start('lesson', focus=[TARGET], replace=True)
    assert t.retry_skipped_ungraded()['items'][0]['saved_work'] == 'Draft working.'


def test_retry_revalidates_unchanged_question_against_current_reviewed_bank(tmp_path):
    root = bank_vault(tmp_path)
    current = item()
    current['topical']['requires'] = [TARGET]
    current['topical']['support'] = {}
    publish(root, [current])
    t = tutor_for(root)
    t.start('lesson', focus=[TARGET])
    question = t._present(current, 'practice', None, serving_chapter=TARGET)
    t.answer(f"{question['n']}?")
    guard = next(iter(t.session['skipped_answer_guards'].values()))
    guard['question']['inst']['topical']['revision'] = 'obsolete'
    assert t.skipped_retry_available()
    assert guard['question']['inst']['topical']['revision'] == 'obsolete'  # availability does not mutate saved evidence
    other = next(k for k in t.packs.kcs if k not in guard['question']['kcs'])
    block = {'kind': 'node', 'kc': other, 'card': {'terms': [{'term': 'Related', 'meaning': 'Potential answer'}]},
             'i': 0, 'phases': ['terms'], 'misses': 0, 'mistakes': []}
    assert t._step_node(block, 0)['part'] == 'guard_pause'
    retry = t.retry_skipped()
    assert retry['activity'] == 'questions'
    assert retry['items'][0]['stem'] == current['stem']
    assert 'answer' not in retry['items'][0]
    t.answer(f"{retry['items'][0]['n']}B3")
    assert not t.session['skipped_answer_guards']


def test_saved_judgment_revalidates_only_unchanged_text_question(tmp_path):
    root = bank_vault(tmp_path)
    current = item()
    current['topical']['requires'] = [TARGET]
    current['topical']['support'] = {}
    publish(root, [current])
    t = tutor_for(root)
    t.start('lesson', focus=[TARGET])
    _, pending = t._number(current, 'deferred_judgment', 'practice', serving_chapter=TARGET)
    pending['saved_work'] = 'B'
    pending['inst']['topical']['revision'] = 'obsolete'
    t.session['awaiting'] = None
    t.session['deferred_judgments'] = [pending]
    activity = t.next()
    assert activity['activity'] == 'questions'
    assert activity['items'][0]['saved_work'] == 'B'
    assert pending['inst']['topical']['revision'] == 'obsolete'


def test_saved_judgment_does_not_revalidate_changed_question(tmp_path):
    root = bank_vault(tmp_path)
    current = item()
    current['topical']['requires'] = [TARGET]
    current['topical']['support'] = {}
    publish(root, [current])
    t = tutor_for(root)
    t.start('lesson', focus=[TARGET])
    _, pending = t._number(current, 'deferred_judgment', 'practice', serving_chapter=TARGET)
    pending['inst']['topical']['revision'] = 'obsolete'
    pending['inst']['stem'] = 'A changed question.'
    pending['saved_work'] = 'B'
    t.session['awaiting'] = None
    t.session['deferred_judgments'] = [pending]
    assert t.next()['activity'] == 'saved_judgment_unavailable'
    assert t.session['deferred_judgments'][0]['saved_work'] == 'B'


def test_retry_does_not_revalidate_changed_question_content(tmp_path):
    root = bank_vault(tmp_path)
    current = item()
    current['topical']['requires'] = [TARGET]
    current['topical']['support'] = {}
    publish(root, [current])
    t = tutor_for(root)
    t.start('lesson', focus=[TARGET])
    question = t._present(current, 'practice', None, serving_chapter=TARGET)
    t.answer(f"{question['n']}?")
    guard = next(iter(t.session['skipped_answer_guards'].values()))
    guard['question']['inst']['topical']['revision'] = 'obsolete'
    guard['question']['inst']['stem'] = 'A different question.'
    assert not t.skipped_retry_available()
    retry = t.retry_skipped()
    assert retry['activity'] == 'error' and 'needs review' in retry['error']


def test_retry_does_not_treat_legacy_overlay_as_reviewed_question_content(tmp_path):
    root = bank_vault(tmp_path)
    current = item(stem='The reviewed current wording?')
    current['topical']['requires'] = [TARGET]
    current['topical']['support'] = {}
    original = copy.deepcopy(current)
    original['id'] = 'legacy-original'
    original['stem'] = 'Different legacy wording?'
    original.pop('topical')
    path = root / '.tutor/packs/v1/specs/9702/packs/9702-2.1.json'
    pack = json.loads(path.read_text())
    pack['items'].append(original)
    path.write_text(json.dumps(pack))
    publish(root, [current])
    t = tutor_for(root)
    t.start('lesson', focus=[TARGET])
    legacy = next(q for q in t.packs.items_for(KC) if q['id'] == 'legacy-original')
    shown = t._present(legacy, 'practice', None, serving_chapter=TARGET)
    t.answer(f"{shown['n']}?")
    next(iter(t.session['skipped_answer_guards'].values()))['question']['inst']['topical']['revision'] = 'obsolete'
    assert t.retry_skipped()['activity'] == 'error'


@pytest.mark.parametrize('field, value', [('marks', 5), ('command_word', 'Explain'), ('kcs', [OTHER + '.1'])])
def test_retry_does_not_revalidate_changed_assessment_fields(tmp_path, field, value):
    root = bank_vault(tmp_path)
    current = item()
    current['topical']['requires'] = [TARGET]
    current['topical']['support'] = {}
    publish(root, [current])
    t = tutor_for(root)
    t.start('lesson', focus=[TARGET])
    shown = t._present(current, 'practice', None, serving_chapter=TARGET)
    t.answer(f"{shown['n']}?")
    inst = next(iter(t.session['skipped_answer_guards'].values()))['question']['inst']
    inst['topical']['revision'] = 'obsolete'
    inst[field] = value
    assert t.retry_skipped()['activity'] == 'error'


@pytest.mark.parametrize('field, value', [('image', 'Assets/topicals/old.png'),
                                         ('images', ['Assets/topicals/old.png'])])
def test_retry_does_not_revalidate_unpinned_images(tmp_path, field, value):
    root = bank_vault(tmp_path)
    current = item()
    current['topical']['requires'] = [TARGET]
    current['topical']['support'] = {}
    publish(root, [current])
    t = tutor_for(root)
    t.start('lesson', focus=[TARGET])
    shown = t._present(current, 'practice', None, serving_chapter=TARGET)
    t.answer(f"{shown['n']}?")
    inst = next(iter(t.session['skipped_answer_guards'].values()))['question']['inst']
    inst['topical']['revision'] = 'obsolete'
    inst[field] = value
    assert t.retry_skipped()['activity'] == 'error'


def test_learner_exclusion_is_chapter_scoped_replayed_and_explicitly_restorable(tmp_path):
    root = bank_vault(tmp_path)
    t = tutor_for(root)
    t.start('review')
    legacy = item()
    legacy.pop('topical')
    n = t._present(legacy, 'practice', None, serving_chapter=TARGET)['n']
    # A pre-bank open question can acquire reviewed metadata without changing its content.
    t.session['presented'][str(n)]['inst']['topical'] = item()['topical']
    t.session['presented'][str(n)]['inst']['topical']['support'] = {}
    result = t.check_solvable(n)
    assert result['status'] == 'skipped' and result['topics'] == ['3.1']
    assert str(n) not in t.session['presented']
    assert t.session['answered'] == 0 and not t.state['items_seen']
    records = t.topical_exclusions()
    assert records[0]['chapter'] == TARGET and records[0]['missing'] == [OTHER]
    restored = tutor_for(root)
    assert restored.topical_exclusions() == records
    restored.log({'type': 'chapter_started', 'chapter': OTHER})
    assert restored.topical_exclusions() == records
    assert restored.restore_topical(records[0]['identity'], TARGET)['ok']
    assert not tutor_for(root).topical_exclusions()


def test_unknown_check_is_unverified_and_never_excludes(tmp_path):
    root = bank_vault(tmp_path)
    t = tutor_for(root)
    t.start('review')
    legacy = item()
    legacy.pop('topical')
    n = t._present(legacy, 'practice', None)['n']
    # Ordinary questions with known assessed KCs now receive a labelled graph
    # assessment. An unknown mapping must still fail closed and remain open.
    t.session['presented'][str(n)]['inst']['kcs'] = ['9702-unknown']
    assert t.check_solvable(n)['status'] == 'unverified'
    assert str(n) in t.session['presented'] and not t.topical_exclusions()


def test_start_tracks_only_actual_activity_and_legacy_answers(tmp_path):
    root = bank_vault(tmp_path)
    t = tutor_for(root)
    t.start('review', focus=[TARGET, OTHER])
    assert not t.state.get('started_chapters')
    t._present(item(), 'practice', None, serving_chapter=TARGET)
    assert t.state['started_chapters'] == [TARGET]
    # Legacy n>0 is sufficient; an untouched KC dictionary is not.
    t.state['kcs'][OTHER + '.1'] = {'n': 1}
    from tutorlib.topicals import started_chapters
    assert OTHER in started_chapters(t.state, t.packs)
    assert THIRD not in started_chapters(t.state, t.packs)


def test_bank_refresh_does_not_change_open_question(tmp_path):
    root = bank_vault(tmp_path)
    publish(root, [item()])
    t = tutor_for(root)
    t.start('review')
    old = next(i for i in t.packs.items_for(KC) if i.get('topical'))
    q = t._present(old, 'practice', None)
    publish(root, [item(stem='A newly corrected source.')], 'two')
    assert next(i for i in t.packs.items_for(KC) if i.get('topical'))['stem'] == 'A newly corrected source.'
    assert t._view(q['n'])['stem'] == 'Choose the vector.'


def test_all_ordered_images_and_support_render_in_obsidian():
    view = {'n': 1, 'kind': 'structured', 'stem': 'Answer (a) only.', 'marks': 2,
            'image': 'Assets/topicals/a.png', 'images': ['Assets/topicals/a.png', 'Assets/topicals/b.png'],
            'support': {OTHER: 'A reviewed prerequisite fact.'}}
    md = views.question_block(view)
    assert md.count('![[Assets/topicals/a.png]]') == 1
    assert md.index('a.png') < md.index('b.png')
    assert 'A reviewed prerequisite fact.' in md


def test_part_identity_does_not_merge_two_distinct_attempts(tmp_path):
    root = bank_vault(tmp_path)
    a, b = item(id='part-a'), item(id='part-b')
    a['source']['part'], b['source']['part'] = 'b', 'c'
    publish(root, [a, b])
    p = packs.Packs(store.Vault(root))
    assert {'part-a', 'part-b'} <= {i['id'] for i in p.items_for(KC)}


def test_canonical_aliases_keep_each_chapters_assessed_kcs_and_share_exposure(tmp_path):
    root = bank_vault(tmp_path)
    original_path = root / '.tutor/packs/v1/specs/9702/packs/9702-2.1.json'
    source_pack = json.loads(original_path.read_text())
    original = copy.deepcopy(source_pack['items'][2])
    original['id'], original['kcs'] = 'other-chapter-original', [OTHER + '.1']
    (original_path.parent / (OTHER + '.json')).write_text(json.dumps({'subtopic': OTHER, 'items': [original]}))
    imported = item(source={'type': 'past', 'qid': '9702_s23_22_q2', 'part': 'a'})
    imported['topical']['chapters'] = [TARGET, OTHER]
    publish(root, [imported])
    p = packs.Packs(store.Vault(root))
    assert any(i['id'] == 'other-chapter-original' for i in p.items_for(OTHER + '.1'))
    state = model.new_state()
    state['items_seen']['other-chapter-original'] = '2026-10-27T12:00:00+08:00'
    selected = p.select_item(TARGET + '.4', state, .5, random.Random(1), kinds=('numeric',))
    assert selected['id'] != '9702-2.1-i03'  # its canonical alias was recently seen
    state['items_seen'] = {'topical-one': '2026-10-27T12:00:00+08:00'}
    assert p.select_item(TARGET + '.4', state, .3, random.Random(1), kinds=('numeric',))['id'] != '9702-2.1-i03'
    state['items_seen'].clear()
    assert p.select_item(TARGET + '.4', state, .3, random.Random(1), kinds=('numeric',),
                         exclude={'other-chapter-original'})['id'] != '9702-2.1-i03'


def test_serving_chapter_is_focused_kc_not_first_assessed_kc(tmp_path):
    root = bank_vault(tmp_path)
    it = item(kcs=[KC, OTHER + '.1'])
    it['topical']['chapters'] = [TARGET, OTHER]
    it['topical']['support'] = {TARGET: 'Safe prerequisite for the other chapter.'}
    publish(root, [it])
    t = tutor_for(root)
    t.start('review')
    chosen = t.packs.select_item(OTHER + '.1', t.state, .5, random.Random(1))
    q = t._present(chosen, 'practice', None)
    assert q['support'] == {TARGET: 'Safe prerequisite for the other chapter.'}
    assert t.session['presented'][str(q['n'])]['serving_chapter'] == OTHER
    assert t.state['started_chapters'] == [OTHER]


def test_queued_support_rechecked_at_actual_presentation(tmp_path):
    root = bank_vault(tmp_path)
    t = tutor_for(root)
    t.one_at_a_time = True
    t.start('review')
    t._questions({'kind': 'practice', 'kc': KC}, 0, [item(id='first'), item(id='second')])
    first = next(iter(t.session['presented']))
    t.answer(f'{first}B4')
    t.log({'type': 'chapter_started', 'chapter': OTHER})
    next_question = t.next()['items'][0]
    assert not next_question.get('support')
    assert not t.session['presented'][str(next_question['n'])]['hinted']


def test_candidate_validation_checks_assets_before_publication_without_a_current_pointer(tmp_path):
    from tutorlib import topicals
    root = bank_vault(tmp_path)
    p = packs.Packs(store.Vault(root))
    candidate = tmp_path / 'candidate'
    candidate.mkdir()
    source = item(image='Assets/topicals/question.png')
    data = {'format_version': 1, 'syllabus_versions': {'9702': '2025-2027'}, 'items': [source]}
    with pytest.raises(ValueError, match='source image'):
        topicals.validate_bank(data, p, candidate)
    asset = candidate / source['image']
    asset.parent.mkdir(parents=True)
    asset.write_bytes(b'local image bytes')
    topicals.validate_bank(data, p, candidate)


def test_exclusion_replay_closes_attempt_if_interrupted_before_session_save(tmp_path):
    root = bank_vault(tmp_path)
    t = tutor_for(root)
    t.start('review')
    it = item()
    it.pop('topical')
    n = t._present(it, 'practice', None, serving_chapter=TARGET)['n']
    t.log({'type': 'topical_exclude', 'identity': '9702_s23_22_q2', 'chapter': TARGET,
           'missing': [OTHER], 'reason': 'Missing reviewed prerequisites for this serving chapter.'})
    resumed = tutor_for(root)
    assert str(n) not in resumed.session['presented']
    assert resumed.session['answered'] == 0


def test_no_hints_presentation_uses_eligible_alternative_instead_of_ending_block(tmp_path):
    root = bank_vault(tmp_path)
    assisted = item(id='needs-support', difficulty=3)
    independent = item(id='safe-independent', difficulty=5,
                       source={'type': 'past', 'qid': '9702_s23_22_q3'})
    independent['topical']['requires'] = [TARGET]
    independent['topical']['support'] = {}
    publish(root, [assisted, independent])
    t = tutor_for(root)
    t.start('review')
    chosen = t._pick(KC, .5)
    assert chosen['id'] == assisted['id']  # ordinary practice may use reviewed support
    act = t._questions({'kind': 'node', 'kc': KC}, 0, [chosen], unassisted=True)
    assert act is not None
    pending = t.session['presented'][str(act['items'][0]['n'])]
    assert pending['item'] != assisted['id'] and not pending['hinted']


@pytest.mark.parametrize('changes', [{'difficulty': 'hard'}, {'difficulty': True}, {'difficulty': 10}, {'marks': 0}, {'marks': '1'}])
def test_invalid_playable_numbers_are_rejected_before_selection(tmp_path, changes):
    from tutorlib.topicals import validate_bank
    root = bank_vault(tmp_path)
    p = packs.Packs(store.Vault(root))
    data = {'format_version': 1, 'syllabus_versions': {'9702': '2025-2027'}, 'items': [item(**changes)]}
    with pytest.raises(ValueError):
        validate_bank(data, p, root)


@pytest.mark.parametrize('changes', [
    {'kind': 'numeric', 'answer': 'B'},
    {'kind': 'numeric', 'answer': {'value': float('nan')}},
    {'kind': 'numeric', 'answer': {'value': 1, 'unit': []}},
    {'kind': 'expression', 'answer': {'value': 1}},
    {'options': {'B': 'only one option'}},
    {'options': {'A': 1, 'B': 'two', 'C': 'three', 'D': 'four'}},
    {'kind': 'structured', 'marks': 2, 'scheme': [{'point': 'Only one mark point.'}]},
    {'kind': 'short', 'answer': None, 'rubric': [{'point': 'A mark point', 'keywords': 1}]},
])
def test_unmarkable_answer_shapes_are_rejected_before_publication(tmp_path, changes):
    from tutorlib.topicals import validate_bank
    root = bank_vault(tmp_path)
    p = packs.Packs(store.Vault(root))
    data = {'format_version': 1, 'syllabus_versions': {'9702': '2025-2027'}, 'items': [item(**changes)]}
    with pytest.raises(ValueError):
        validate_bank(data, p, root)


def test_no_hints_fallback_reuses_safe_questions_and_can_change_practice_kind(tmp_path):
    root = bank_vault(tmp_path)
    assisted = item(id='supported-number', kind='numeric', answer={'value': 2})
    publish(root, [assisted])
    t = tutor_for(root)
    t.start('review')
    safe_ids = {'9702-2.1-i01', '9702-2.1-i04'}
    t.session['used'] = sorted(safe_ids)
    chosen = t._pick(KC, .5)
    assert chosen['id'] == assisted['id']
    act = t._questions({'kind': 'exit', 'kc': KC}, 0, [chosen], unassisted=True)
    assert act is not None
    pending = t.session['presented'][str(act['items'][0]['n'])]
    assert pending['item'] in safe_ids and not pending['hinted']


@pytest.mark.parametrize('setting', [{'sf_ok': 3}, {'sf_ok': [0]}, {'sf_ok': ['3']}, {'sf': '3'},
                                      {'sf': True}, {'tol_rel': 'wide'}, {'tol_rel': float('inf')},
                                      {'tol_rel': -1}, {'exact': 'yes'}])
@pytest.mark.parametrize('nested', [False, True])
def test_invalid_numeric_precision_settings_fail_before_grading(tmp_path, setting, nested):
    from tutorlib.topicals import validate_bank
    root = bank_vault(tmp_path)
    p = packs.Packs(store.Vault(root))
    answer = {'value': 2, **setting}
    numeric = {'kind': 'numeric', 'answer': answer}
    source = item(**numeric) if not nested else item(kind='structured', scheme=[{'point': 'Find the value.', 'check': numeric}])
    data = {'format_version': 1, 'syllabus_versions': {'9702': '2025-2027'}, 'items': [source]}
    with pytest.raises(ValueError):
        validate_bank(data, p, root)


def test_topical_session_serves_bank_only_in_unbuilt_chapter_without_repeats(tmp_path):
    root = bank_vault(tmp_path)
    mcq = item(id='unbuilt-mcq', kcs=[OTHER + '.1'])
    structured = item(id='unbuilt-written', kcs=[OTHER + '.1'], kind='structured',
                      source={'type': 'past', 'qid': '9702_s23_22_q4'},
                      scheme=[{'mark': 'B1', 'point': 'The reviewed marking point.'}])
    for source in (mcq, structured):
        source['topical'].update(requires=[OTHER], support={}, chapters=[OTHER])
    publish(root, [mcq, structured])
    t = tutor_for(root)
    assert t.packs.pack(OTHER) is None
    t.start('topical', minutes=30, focus=[OTHER])
    seen = []
    kinds = set()
    for _ in range(5):
        act = t.next()
        if act['activity'] == 'end':
            break
        assert act['activity'] == 'questions'
        q = act['items'][0]
        pending = t.session['presented'][str(q['n'])]
        assert pending['inst']['topical']['reviewed']
        seen.append(pending['item'])
        kinds.add(q['kind'])
        t.answer(f"{q['n']}B4" if q['kind'] == 'mcq' else f"{q['n']} pts=0")
    assert set(seen) == {'unbuilt-mcq', 'unbuilt-written'} and len(seen) == 2
    assert kinds == {'mcq', 'structured'} and act['activity'] == 'end'
    assert t.packs.pack(OTHER) is None and not t.session['kcs_learned']


def test_topical_session_obeys_chapter_exclusions_and_prerequisite_policy(tmp_path):
    root = bank_vault(tmp_path)
    a, b = item(id='excluded-bank'), item(id='supported-bank', source={'type': 'past', 'qid': '9702_s23_22_q3'})
    publish(root, [a, b])
    t = tutor_for(root)
    t.log({'type': 'topical_exclude', 'identity': '9702_s23_22_q2', 'chapter': TARGET,
           'missing': [OTHER], 'reason': 'Learner requested chapter exclusion.'})
    t.start('topical', minutes=15, focus=[TARGET])
    act = t.next()
    assert act['activity'] == 'questions'
    pending = t.session['presented'][str(act['items'][0]['n'])]
    assert pending['item'] == b['id'] and pending['hinted']
    assert act['items'][0]['support'] == {OTHER: 'A reviewed prerequisite fact.'}


def test_topical_inventory_requires_membership_in_the_current_bank(tmp_path):
    root = bank_vault(tmp_path)
    pack_path = root / '.tutor/packs/v1/specs/9702/packs/9702-2.1.json'
    pack = json.loads(pack_path.read_text())
    pack['items'].append(item(id='legacy-tag-only', source={'type': 'past', 'qid': '9702_s23_22_q99'}))
    pack_path.write_text(json.dumps(pack))
    publish(root, [item()])
    p = packs.Packs(store.Vault(root))
    assert [i['id'] for i in p.topical_items(TARGET)] == ['topical-one']


@pytest.mark.parametrize('focus', [['9702-99.9'], []])
def test_explicit_unmatched_topical_selection_never_falls_back_to_other_chapters(tmp_path, focus):
    root = bank_vault(tmp_path)
    publish(root, [item()])
    t = tutor_for(root)
    result = t.start('topical', minutes=15, focus=focus)
    assert result['ok'] is False
    assert t.session is None


def test_unassisted_replacement_excludes_disclosed_canonical_alias(tmp_path):
    root = bank_vault(tmp_path)
    imported = item(kcs=[TARGET + '.4'], source={'type': 'past', 'qid': '9702_s23_22_q2', 'part': 'a'})
    imported['topical']['requires'] = [TARGET]
    imported['topical']['support'] = {}
    publish(root, [imported])
    pack_path = root / '.tutor/packs/v1/specs/9702/packs/9702-2.1.json'
    pack = json.loads(pack_path.read_text())
    pack['items'] = [i for i in pack['items'] if i['id'] != '9702-2.1-i02']
    pack_path.write_text(json.dumps(pack))
    t = tutor_for(root)
    t.start('lesson', focus=[TARGET])
    t.packs.items_for(TARGET + '.4')
    unsuitable = item(id='unavailable', kcs=[TARGET + '.4'], _selection_kinds=('numeric',))
    block = {'kind': 'exit', 'kc': TARGET + '.4'}
    t.session['disclosed_item_ids'] = ['topical-one']
    original = next(i for i in t.packs.items_for(TARGET + '.4') if i['id'] == '9702-2.1-i03')
    t.packs._topical_index_version = None
    t.packs._topical_aliases = {}
    assert t._questions(block, 0, [original], unassisted=True) is None
    assert t._questions(block, 0, [unsuitable], unassisted=True) is None
    assert not t.session['presented']
    t.session['disclosed_item_ids'] = []
    activity = t._questions(block, 0, [unsuitable], unassisted=True)
    assert activity and activity['items'][0]['unassisted']
    assert next(iter(t.session['presented'].values()))['item'] == '9702-2.1-i03'


@pytest.mark.parametrize('previous_bank', [False, True])
def test_direct_disclosure_checks_legacy_aliases_without_a_bank(tmp_path, previous_bank):
    root = bank_vault(tmp_path)
    pack_path = root / '.tutor/packs/v1/specs/9702/packs/9702-2.1.json'
    pack = json.loads(pack_path.read_text())
    original = next(i for i in pack['items'] if i['id'] == '9702-2.1-i03')
    alias = copy.deepcopy(original)
    alias['id'] = 'legacy-alias'
    pack['items'].append(alias)
    pack_path.write_text(json.dumps(pack))
    if previous_bank:
        imported = item(kcs=[TARGET + '.4'], source={'type': 'past', 'qid': '9702_s23_22_q2', 'part': 'a'})
        imported['topical']['requires'] = [TARGET]
        imported['topical']['support'] = {}
        publish(root, [imported])
    t = tutor_for(root)
    t.start('lesson', focus=[TARGET])
    if previous_bank:
        t.packs.items_for(TARGET + '.4')
        (root / '.tutor/topicals/CURRENT').unlink()
    t.session['disclosed_item_ids'] = ['legacy-alias']
    assert t._questions({'kind': 'exit', 'kc': TARGET + '.4'}, 0, [original], unassisted=True) is None
    assert not t.session['presented']


def test_topical_practice_skips_disclosed_question_before_charging_time(tmp_path, monkeypatch):
    root = bank_vault(tmp_path)
    first = item()
    first['topical']['requires'] = [TARGET]
    first['topical']['support'] = {}
    second = copy.deepcopy(first)
    second['id'] = 'topical-two'
    second['source']['qid'] = '9702_s23_22_q9'
    second['source']['ref'] = 'CAIE 9702 · Jun 2023 · P22 · Q9'
    publish(root, [first, second])
    t = tutor_for(root)
    t.start('topical', focus=[TARGET], minutes=9)
    t.session['disclosed_item_ids'] = ['topical-one']
    scores = iter([0.1, 0.9])
    monkeypatch.setattr(t.rng, 'random', lambda: next(scores))
    activity = t.next()
    assert activity['activity'] == 'questions'
    presented = next(iter(t.session['presented'].values()))
    assert presented['item'] == 'topical-two'
    assert '9702_s23_22_q2' not in t.session['topical_used']


def test_legacy_alias_scan_runs_once_per_selection(tmp_path, monkeypatch):
    p = packs.Packs(store.Vault(bank_vault(tmp_path)))
    original = p.published
    calls = []
    def published():
        calls.append(1)
        return original()
    monkeypatch.setattr(p, 'published', published)
    items = p.items_for(TARGET + '.4')
    past = next(i for i in items if i['id'] == '9702-2.1-i03')
    monkeypatch.setattr(p, 'items_for', lambda kc: [past, {**past, 'id': 'another-past'}])
    p.select_item(TARGET + '.4', model.new_state(), .5, random.Random(0), exclude={'some-other-id'})
    assert len(calls) <= 1


def test_selection_keeps_aliases_from_candidate_snapshot(tmp_path, monkeypatch):
    p = packs.Packs(store.Vault(bank_vault(tmp_path)))
    past = next(i for i in p.items_for(TARGET + '.4') if i['id'] == '9702-2.1-i03')
    ident = '9702_s23_22_q2:a'
    def original_candidates(kc):
        p._topical_aliases = {ident: {past['id'], 'old-bank-id'}}
        return [past]
    monkeypatch.setattr(p, 'items_for', original_candidates)
    monkeypatch.setattr(p, 'aliases_for', lambda item, legacy_aliases=None: {item['id']})
    assert p.select_item(TARGET + '.4', model.new_state(), .5, random.Random(0), exclude={'old-bank-id'}) is None


def test_excluded_pending_mark_work_survives_restart_and_can_be_restored(tmp_path):
    root = bank_vault(tmp_path)
    t = tutor_for(root)
    t.start('review', minutes=10)
    q = item(id='pending-excluded', kind='short', stem='Explain.',
             rubric=[{'point': 'A point', 'keywords': [['point']]}])
    view = t._present(q, 'practice', 'form_check')
    p = t.session['presented'][str(view['n'])]
    p.update(saved_work='My partial reasoning', pending_saved_mark=True)
    t._save()
    t.log({'type': 'topical_exclude', 'identity': '9702_s23_22_q2', 'chapter': TARGET,
           'reason': 'test', 'missing': []})
    restored = tutor_for(root)
    saved = restored.session.get('deferred_judgments', [])
    assert len(saved) == 1 and saved[0]['saved_work'] == 'My partial reasoning'
    assert restored.next()['activity'] == 'saved_judgment_unavailable'
    again = tutor_for(root)
    assert again.session['deferred_judgments'][0]['saved_work'] == 'My partial reasoning'


def test_solvability_skip_retains_pending_mark_work(tmp_path):
    root = bank_vault(tmp_path)
    t = tutor_for(root)
    t.start('review', minutes=10)
    q = item(id='pending-skip', kind='short', stem='Explain.',
             rubric=[{'point': 'A point', 'keywords': [['point']]}],
             topical={'reviewed': True, 'requires': [TARGET, OTHER], 'support': {OTHER: 'Needed fact.'},
                      'chapters': [TARGET], 'revision': '2025-2027'})
    view = t._present(q, 'practice', 'form_check')
    p = t.session['presented'][str(view['n'])]
    p['inst']['topical']['support'] = {}  # prerequisite metadata changes after presentation
    p.update(saved_work='My partial reasoning', pending_saved_mark=True)
    t._save()
    result = t.check_solvable(view['n'])
    assert result['status'] == 'skipped' and 'working remains saved' in result['message']
    assert t.session['deferred_judgments'][0]['saved_work'] == 'My partial reasoning'
    restored = tutor_for(root)
    assert restored.session['deferred_judgments'][0]['saved_work'] == 'My partial reasoning'


def test_excluded_pending_node_check_restores_remedial_step_after_marking(tmp_path):
    root = bank_vault(tmp_path)
    t = tutor_for(root)
    t.start('review', minutes=10)
    node = {'kind': 'node', 'kc': OTHER + '.1', 'i': 0, 'phases': ['done'], 'misses': 0, 'mistakes': [],
            'card': {'forms': [{'check': 'Original', 'retry': {'check': 'Try again', 'answer': 'Correct',
                     'rubric': [{'point': 'A point', 'keywords': [['point']]}]}}]}}
    t.session['blocks'] = [node]
    t.session['cursor'] = 0
    q = {'id': 'node-pending', 'kcs': [KC, OTHER + '.1'], 'kind': 'short', 'difficulty': 3, 'marks': 1,
         'stem': 'Explain.', 'form_index': 0, 'review_answer': 'Correct',
         'rubric': [{'point': 'A point', 'keywords': [['point']]}]}
    view = t._present(q, 'node', 'form_check', block_idx=0)
    t.session['presented'][str(view['n'])].update(saved_work='My attempt', pending_saved_mark=True)
    t._save()
    t.log({'type': 'topical_exclude', 'identity': q['id'], 'chapter': TARGET, 'reason': 'test', 'missing': []})
    t = tutor_for(root)
    assert t.next()['activity'] == 'saved_judgment_unavailable'
    assert t.restore_topical(q['id'], TARGET)['ok']
    recovered = t.next()['items'][0]
    t.answer(f"{recovered['n']} = My attempt", judge={recovered['n']: 0},
             explanation={recovered['n']: 'Point missed.'})
    assert t.session['blocks'][0]['misses'] == 1
    assert t.session['blocks'][0]['phases'][:2] == ['fix', 'form_retry:0']
