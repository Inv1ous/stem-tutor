"""Durability and guard semantics for unpublished lesson notes."""
from tutorlib import deferred_notes


def test_guard_refresh_updates_deferred_note_copies_atomically(tmp_path):
    path = tmp_path / 'guards.json'
    guard = {'kind': 'structured', 'key': 'private', 'question': {'inst': {'id': 'q'}}}
    deferred_notes.hold(path, 'q', guard)
    deferred_notes.defer(path, 'note', 'P2-1', {'kc': 'P2-1.1'}, {'q': guard})
    updated = {'kind': 'structured', 'key': 'private', 'question': {'inst': {'id': 'q'}, 'saved_work': 'My work'}}
    deferred_notes.hold(path, 'q', updated)
    assert deferred_notes.outstanding(path)['q']['question']['saved_work'] == 'My work'
import pytest
from types import SimpleNamespace


def test_deferred_notes_survive_restart_and_wait_for_all_guards(tmp_path):
    path = tmp_path / 'private' / 'notes.json'
    node = {'kc': 'P2-1.1', 'note': 'protected answer', 'own_words': 'my explanation', 'mistakes': ['my error']}
    deferred_notes.defer(path, 'entry-1', 'P2-1', node, {'guard-a': {'question': 1}, 'guard-b': {'question': 2}})
    deferred_notes.resolve(path, 'guard-a')
    assert deferred_notes.ready(path) == []
    deferred_notes.resolve(path, 'guard-b')
    assert deferred_notes.ready(path) == [{'id': 'entry-1', 'subtopic': 'P2-1', 'node': node}]


def test_deferred_notes_are_not_overwritten_by_repeated_idea(tmp_path):
    path = tmp_path / 'private' / 'notes.json'
    for index in (1, 2):
        deferred_notes.defer(path, str(index), 'P2-1', {'kc': 'P2-1.1', 'own_words': str(index)}, {'g': {}})
    deferred_notes.resolve(path, 'g')
    assert [row['node']['own_words'] for row in deferred_notes.ready(path)] == ['1', '2']


def test_repeated_skip_with_new_display_metadata_preserves_same_guard(tmp_path):
    path = tmp_path / 'private' / 'notes.json'
    first = {'key': 'A', 'kind': 'mcq', 'question': {'shown_at': 'first', 'inst': {'stem': 'Same', 'answer': 'A'}}}
    second = {'key': 'A', 'kind': 'mcq', 'question': {'shown_at': 'later', 'inst': {'stem': 'Same', 'answer': 'A'}}}
    deferred_notes.defer(path, 'first', 'P2-1', {'kc': 'P2-1.1'}, {'g': first})
    deferred_notes.defer(path, 'second', 'P2-1', {'kc': 'P2-1.1'}, {'g': second})
    assert deferred_notes.outstanding(path)['g']['question']['inst'] == first['question']['inst']
    deferred_notes.resolve(path, 'g')
    assert len(deferred_notes.ready(path)) == 2


def test_duplicate_identity_is_idempotent_but_cannot_replace_content(tmp_path):
    path = tmp_path / 'notes.json'
    deferred_notes.defer(path, '1', 'P2-1', {'note': 'original'}, {'g': {}})
    deferred_notes.defer(path, '1', 'P2-1', {'note': 'original'}, {'g': {}})
    with pytest.raises(ValueError):
        deferred_notes.defer(path, '1', 'P2-1', {'note': 'replacement'}, {'g': {}})
    deferred_notes.resolve(path, 'g')
    assert deferred_notes.ready(path)[0]['node']['note'] == 'original'


def test_outstanding_guards_can_be_restored_and_ready_records_acknowledged(tmp_path):
    path = tmp_path / 'notes.json'
    question = {'question': {'inst': {'stem': 'Same generated instance', 'params': {'n': 4}}}}
    deferred_notes.defer(path, 'one', 'P2-1', {'kc': 'P2-1.1'}, {'g': question})
    assert deferred_notes.outstanding(path) == {'g': question}
    with pytest.raises(ValueError):
        deferred_notes.acknowledge(path, 'one')
    deferred_notes.resolve(path, 'g')
    assert deferred_notes.outstanding(path) == {}
    deferred_notes.acknowledge(path, 'one')
    deferred_notes.acknowledge(path, 'one')  # recovery can safely repeat an acknowledgement
    assert deferred_notes.ready(path) == []


def test_lesson_completion_defers_note_with_skipped_guard(tmp_path, monkeypatch):
    from tutorlib import lesson
    written = []
    monkeypatch.setattr(lesson.views, 'notes_update', lambda *a, **kw: written.append(kw['node']))
    tutor = lesson.LessonMixin()
    tutor.vault = SimpleNamespace(root=tmp_path, tutor=tmp_path / '.tutor')
    tutor.packs = SimpleNamespace(kcs={'P2-1.1': {'subtopic': 'P2-1'}})
    tutor.state = {}
    tutor.session = {'id': 'session', 'skipped_answer_guards': {'guard': {'key': 'secret answer'}}, 'kcs_learned': []}
    tutor.log = lambda event: None
    block = {'kc': 'P2-1.1', 'card': {'note': 'secret answer'}, 'own_words': 'my words', 'mistakes': ['my error']}
    tutor._node_done(block)
    assert written == []
    path = tutor.vault.tutor / 'state' / 'deferred-notes.json'
    assert deferred_notes.outstanding(path) == tutor.session['skipped_answer_guards']
    deferred_notes.resolve(path, 'guard')
    assert deferred_notes.ready(path)[0]['node'] == {'kc': 'P2-1.1', 'note': 'secret answer',
                                                       'own_words': 'my words', 'mistakes': ['my error']}


def test_new_lesson_restores_deferred_question_guards(tmp_path):
    from fixtures import make_vault
    from tutorlib import session, store
    root = make_vault(tmp_path)
    vault = store.Vault(root)
    question = {'key': 'secret', 'kind': 'short', 'question': {'inst': {'stem': 'Original question'}}}
    deferred_notes.defer(vault.tutor / 'state' / 'deferred-notes.json', 'one', '9702-2.1',
                         {'kc': '9702-2.1.1', 'note': 'secret'}, {'guard': question})
    tutor = session.Tutor(vault)
    tutor.start('lesson', focus=['9702-2.1'])
    assert tutor.session['skipped_answer_guards'] == {'guard': question}
    recovered = session.Tutor(store.Vault(root))
    assert recovered.session['skipped_answer_guards'] == {'guard': question}


def test_new_automatic_session_preserves_guard_for_lesson_notes(tmp_path):
    from fixtures import make_vault
    from tutorlib import session, store, views
    root = make_vault(tmp_path)
    tutor = session.Tutor(store.Vault(root))
    tutor.start('lesson', focus=['9702-2.1'])
    item = {'id': 'automatic-guard', 'kcs': ['9702-2.1.1'], 'kind': 'mcq', 'difficulty': 2,
            'marks': 1, 'stem': 'Which?', 'options': {'A': 'Secret', 'B': 'Other'}, 'answer': 'A'}
    shown = tutor._present(item, block='practice', phase='practice')
    tutor.answer(f"{shown['n']}?")
    tutor.end()
    tutor.start('autopilot', minutes=10)
    tutor._node_done({'kc': '9702-2.1.1', 'card': {'note': 'Secret'}, 'mistakes': []})
    note = root / views.notes_rel(tutor.packs, '9702-2.1')
    assert not note.exists() or 'Secret' not in note.read_text()
    retry = tutor.retry_skipped()
    tutor.answer(f"{retry['items'][0]['n']}A3")
    assert 'Secret' in note.read_text()


def test_attempting_exact_retry_releases_deferred_guard(tmp_path):
    from fixtures import make_vault
    from tutorlib import session, store
    root = make_vault(tmp_path)
    tutor = session.Tutor(store.Vault(root))
    tutor.start('lesson', focus=['9702-2.1'])
    item = {'id': 'guarded-test', 'kcs': ['9702-2.1.1'], 'kind': 'mcq', 'difficulty': 2,
            'marks': 1, 'stem': 'Which?', 'options': {'A': 'Secret', 'B': 'Other'}, 'answer': 'A'}
    shown = tutor._present(item, block='practice', phase='practice')
    tutor.answer(f"{shown['n']}?")
    tutor._node_done({'kc': '9702-2.1.1', 'card': {'note': 'Secret'}, 'mistakes': []})
    path = tutor.vault.tutor / 'state' / 'deferred-notes.json'
    assert deferred_notes.ready(path) == []
    retry = tutor.retry_skipped()
    tutor.answer(f"{retry['items'][0]['n']}A3")
    from tutorlib import views
    note_path = root / views.notes_rel(tutor.packs, '9702-2.1')
    assert 'Secret' in note_path.read_text()
    assert deferred_notes.ready(path) == []


def test_note_publication_replay_does_not_overwrite_later_edits(tmp_path):
    from fixtures import make_vault
    from tutorlib import session, store, views
    root = make_vault(tmp_path)
    tutor = session.Tutor(store.Vault(root))
    entry = {'kc': '9702-2.1.1', 'note': 'Original lesson note', 'own_words': 'My words', 'mistakes': []}
    views.notes_update(root, tutor.packs, tutor.state, '9702-2.1', node=entry, deferred_id='a' * 64)
    path = root / views.notes_rel(tutor.packs, '9702-2.1')
    path.write_text(path.read_text().replace('Original lesson note', 'My later edit'))
    views.notes_update(root, tutor.packs, tutor.state, '9702-2.1', node=entry, deferred_id='a' * 64)
    assert 'My later edit' in path.read_text()
    assert path.read_text().count('My words') == 1


def test_deferred_note_can_be_retried_after_session_end(tmp_path):
    from fixtures import make_vault
    from tutorlib import session, store, views
    root = make_vault(tmp_path)
    tutor = session.Tutor(store.Vault(root))
    tutor.start('lesson', focus=['9702-2.1'])
    item = {'id': 'after-end', 'kcs': ['9702-2.1.1'], 'kind': 'mcq', 'difficulty': 2,
            'marks': 1, 'stem': 'Which?', 'options': {'A': 'Secret', 'B': 'Other'}, 'answer': 'A'}
    q = tutor._present(item, block='practice', phase='practice')
    tutor.answer(f"{q['n']}?")
    tutor._node_done({'kc': '9702-2.1.1', 'card': {'note': 'Secret'}, 'own_words': 'My words', 'mistakes': []})
    tutor.end()
    tutor = session.Tutor(store.Vault(root))
    tutor.start('lesson', focus=['9702-2.1'])
    retry = tutor.retry_skipped()
    assert retry['items'][0]['stem'] == 'Which?'
    tutor.answer(f"{retry['items'][0]['n']}A3")
    note = (root / views.notes_rel(tutor.packs, '9702-2.1')).read_text()
    assert 'Secret' in note and 'My words' in note


def test_interruption_after_note_write_replays_without_losing_edit(tmp_path, monkeypatch):
    from fixtures import make_vault
    from tutorlib import session, store, views
    root = make_vault(tmp_path)
    vault = store.Vault(root)
    path = vault.tutor / 'state' / 'deferred-notes.json'
    entry_id = 'a' * 64
    deferred_notes.defer(path, entry_id, '9702-2.1',
                         {'kc': '9702-2.1.1', 'note': 'Lesson note', 'own_words': 'My words'}, {'g': {}})
    deferred_notes.resolve(path, 'g')
    original = deferred_notes.acknowledge
    monkeypatch.setattr(deferred_notes, 'acknowledge', lambda *args: (_ for _ in ()).throw(OSError('interrupted')))
    with pytest.raises(OSError, match='interrupted'):
        session.Tutor(vault)
    pack = session.Packs(vault)
    note = root / views.notes_rel(pack, '9702-2.1')
    note.write_text(note.read_text().replace('Lesson note', 'My later edit'))
    monkeypatch.setattr(deferred_notes, 'acknowledge', original)
    session.Tutor(store.Vault(root))
    assert 'My later edit' in note.read_text()
    assert note.read_text().count('My words') == 1
    assert deferred_notes.ready(path) == []


def test_two_skipped_questions_keep_note_private_until_both_attempted(tmp_path):
    from fixtures import make_vault
    from tutorlib import session, store, views
    root = make_vault(tmp_path)
    tutor = session.Tutor(store.Vault(root))
    tutor.start('lesson', focus=['9702-2.1'])
    for number in (1, 2):
        item = {'id': f'guarded-{number}', 'kcs': ['9702-2.1.1'], 'kind': 'mcq', 'difficulty': 2,
                'marks': 1, 'stem': f'Question {number}', 'options': {'A': f'Secret {number}', 'B': 'Other'},
                'answer': 'A'}
        shown = tutor._present(item, block='practice', phase='practice')
        tutor.answer(f"{shown['n']}?")
    tutor._node_done({'kc': '9702-2.1.1', 'card': {'note': 'Secret 1 and Secret 2'}, 'mistakes': []})
    note = root / views.notes_rel(tutor.packs, '9702-2.1')
    first = tutor.retry_skipped()
    tutor.answer(f"{first['items'][0]['n']}A3")
    assert not note.exists() or 'Secret' not in note.read_text()
    second = tutor.retry_skipped()
    tutor.answer(f"{second['items'][0]['n']}?")  # a give-up resolves the last guard
    assert 'Secret 1 and Secret 2' in note.read_text()


def test_interruption_after_answer_log_recovers_and_publishes_note(tmp_path, monkeypatch):
    from fixtures import make_vault
    from tutorlib import session, store, views
    root = make_vault(tmp_path)
    tutor = session.Tutor(store.Vault(root))
    tutor.start('lesson', focus=['9702-2.1'])
    item = {'id': 'crash-after-answer', 'kcs': ['9702-2.1.1'], 'kind': 'mcq', 'difficulty': 2,
            'marks': 1, 'stem': 'Which?', 'options': {'A': 'Secret', 'B': 'Other'}, 'answer': 'A'}
    shown = tutor._present(item, block='practice', phase='practice')
    tutor.answer(f"{shown['n']}?")
    tutor._node_done({'kc': '9702-2.1.1', 'card': {'note': 'Secret'}, 'mistakes': []})
    retry = tutor.retry_skipped()
    original = deferred_notes.resolve
    monkeypatch.setattr(deferred_notes, 'resolve', lambda *args: (_ for _ in ()).throw(OSError('interrupted')))
    with pytest.raises(OSError, match='interrupted'):
        tutor.answer(f"{retry['items'][0]['n']}A3")
    monkeypatch.setattr(deferred_notes, 'resolve', original)
    recovered = session.Tutor(store.Vault(root))
    assert 'Secret' in (root / views.notes_rel(recovered.packs, '9702-2.1')).read_text()
    assert not deferred_notes.outstanding(recovered.vault.tutor / 'state' / 'deferred-notes.json')


def test_different_generated_instance_does_not_release_skipped_note(tmp_path):
    from fixtures import make_vault
    from tutorlib import session, store, views
    root = make_vault(tmp_path)
    tutor = session.Tutor(store.Vault(root))
    tutor.start('lesson', focus=['9702-2.1'])
    item = {'id': 'parameterised', 'kcs': ['9702-2.1.1'], 'kind': 'mcq', 'difficulty': 2,
            'marks': 1, 'stem': 'Question for 4', 'options': {'A': 'Secret 4', 'B': 'Other'},
            'answer': 'A', 'params': {'n': 4}}
    shown = tutor._present(item, block='practice', phase='practice')
    tutor.answer(f"{shown['n']}?")
    tutor._node_done({'kc': '9702-2.1.1', 'card': {'note': 'Secret 4'}, 'mistakes': []})
    other = {**item, 'stem': 'Question for 5', 'options': {'A': 'Secret 5', 'B': 'Other'}, 'params': {'n': 5}}
    shown = tutor._present(other, block='practice', phase='practice')
    tutor.answer(f"{shown['n']}A3")
    path = root / views.notes_rel(tutor.packs, '9702-2.1')
    assert not path.exists() or 'Secret 4' not in path.read_text()
    retry = tutor.retry_skipped()
    assert retry['items'][0]['stem'] == 'Question for 4'
    tutor.answer(f"{retry['items'][0]['n']}A3")
    assert 'Secret 4' in path.read_text()


def test_skipped_question_survives_end_before_any_note_exists(tmp_path):
    from fixtures import make_vault
    from tutorlib import session, store
    root = make_vault(tmp_path)
    tutor = session.Tutor(store.Vault(root))
    tutor.start('lesson', focus=['9702-2.1'])
    item = {'id': 'skip-before-note', 'kcs': ['9702-2.1.1'], 'kind': 'mcq', 'difficulty': 2,
            'marks': 1, 'stem': 'Which?', 'options': {'A': 'Secret', 'B': 'Other'}, 'answer': 'A'}
    shown = tutor._present(item, block='practice', phase='practice')
    tutor.answer(f"{shown['n']}?")
    tutor.end()
    tutor = session.Tutor(store.Vault(root))
    tutor.start('lesson', focus=['9702-2.1'])
    retry = tutor.retry_skipped()
    assert retry['items'][0]['stem'] == 'Which?'
    tutor.answer(f"{retry['items'][0]['n']}A3")
    assert not tutor.session['skipped_answer_guards']
    assert not deferred_notes.outstanding(tutor.vault.tutor / 'state' / 'deferred-notes.json')


def test_interruption_after_skip_log_restores_durable_guard(tmp_path, monkeypatch):
    from fixtures import make_vault
    from tutorlib import session, store
    root = make_vault(tmp_path)
    tutor = session.Tutor(store.Vault(root))
    tutor.start('lesson', focus=['9702-2.1'])
    item = {'id': 'skip-crash', 'kcs': ['9702-2.1.1'], 'kind': 'mcq', 'difficulty': 2,
            'marks': 1, 'stem': 'Which?', 'options': {'A': 'Secret', 'B': 'Other'}, 'answer': 'A'}
    shown = tutor._present(item, block='practice', phase='practice')
    original = deferred_notes.hold
    monkeypatch.setattr(deferred_notes, 'hold', lambda *args: (_ for _ in ()).throw(OSError('interrupted')))
    with pytest.raises(OSError, match='interrupted'):
        tutor.answer(f"{shown['n']}?")
    monkeypatch.setattr(deferred_notes, 'hold', original)
    recovered = session.Tutor(store.Vault(root))
    guards = deferred_notes.outstanding(recovered.vault.tutor / 'state' / 'deferred-notes.json')
    assert len(guards) == 1
    recovered.end()
    recovered.start('lesson', focus=['9702-2.1'])
    assert recovered.retry_skipped()['items'][0]['stem'] == 'Which?'


def test_replacing_lesson_retains_skipped_question(tmp_path):
    from fixtures import make_vault
    from tutorlib import session, store
    tutor = session.Tutor(store.Vault(make_vault(tmp_path)))
    tutor.start('lesson', focus=['9702-2.1'])
    item = {'id': 'replace-skip', 'kcs': ['9702-2.1.1'], 'kind': 'mcq', 'difficulty': 2,
            'marks': 1, 'stem': 'Original instance?', 'options': {'A': 'Secret', 'B': 'Other'}, 'answer': 'A'}
    shown = tutor._present(item, block='practice', phase='practice')
    tutor.answer(f"{shown['n']}?")
    tutor.start('lesson', focus=['9702-2.1'], replace=True)
    assert tutor.retry_skipped()['items'][0]['stem'] == 'Original instance?'


def test_skipped_guard_is_available_to_ask_without_a_session(tmp_path):
    from fixtures import make_vault
    from tutor_app import prompts
    from tutorlib import session, store
    tutor = session.Tutor(store.Vault(make_vault(tmp_path)))
    tutor.start('lesson', focus=['9702-2.1'])
    item = {'id': 'standalone-guard', 'kcs': ['9702-2.1.1'], 'kind': 'mcq', 'difficulty': 2,
            'marks': 1, 'stem': 'Which?', 'options': {'A': 'Secret', 'B': 'Other'}, 'answer': 'A'}
    shown = tutor._present(item, block='practice', phase='practice')
    tutor.answer(f"{shown['n']}?")
    tutor.end()
    assert prompts.skipped_guards(tutor)
    assert prompts.guard_keys(tutor)


def test_lesson_does_not_explain_skipped_answer_before_retry(tmp_path):
    from fixtures import make_vault
    from tutorlib import session, store
    root = make_vault(tmp_path)
    tutor = session.Tutor(store.Vault(root))
    tutor.start('lesson', focus=['9702-2.1'])
    item = {'id': 'skip-then-fix', 'kcs': ['9702-2.1.1'], 'kind': 'mcq', 'difficulty': 2,
            'marks': 1, 'stem': 'Which?', 'options': {'A': 'Secret answer', 'B': 'Other'}, 'answer': 'A'}
    shown = tutor._present(item, block='practice', phase='practice')
    tutor.answer(f"{shown['n']}?")
    block = {'kind': 'node', 'kc': '9702-2.1.1', 'card': {'establish': 'Secret answer', 'connect': ''},
             'i': 0, 'phases': ['fix'], 'misses': 1, 'mistakes': []}
    activity = tutor._step_node(block, 0)
    assert 'Secret answer' not in str(activity)
    assert block['i'] == 0
    retry = tutor.retry_skipped()
    assert retry['items'][0]['stem'] == 'Which?'
    tutor.answer(f"{retry['items'][0]['n']}A3")
    resumed = tutor._step_node(block, 0)
    assert resumed['text'] == 'Secret answer'


def test_retry_can_reach_other_guard_when_first_question_is_excluded(tmp_path):
    from fixtures import make_vault
    from tutorlib import session, store
    tutor = session.Tutor(store.Vault(make_vault(tmp_path)))
    tutor.start('lesson', focus=['9702-2.1'])
    for number in (1, 2):
        item = {'id': f'exclusion-{number}', 'kcs': ['9702-2.1.1'], 'kind': 'mcq', 'difficulty': 2,
                'marks': 1, 'stem': f'Question {number}', 'options': {'A': 'Secret', 'B': 'Other'}, 'answer': 'A'}
        shown = tutor._present(item, block='practice', phase='practice')
        tutor.answer(f"{shown['n']}?")
    tutor.log({'type': 'topical_exclude', 'identity': 'exclusion-1', 'chapter': '9702-2.1', 'reason': 'test', 'missing': []})
    retry = tutor.retry_skipped()
    assert retry['items'][0]['stem'] == 'Question 2'
    assert len(tutor.session['skipped_answer_guards']) == 2


def test_all_excluded_retries_offer_explicit_restoration_without_changing_exclusion(tmp_path):
    from fixtures import make_vault
    from tutorlib import session, store
    tutor = session.Tutor(store.Vault(make_vault(tmp_path)))
    tutor.start('lesson', focus=['9702-2.1'])
    item = {'id': 'excluded-retry', 'kcs': ['9702-2.1.1'], 'kind': 'mcq', 'difficulty': 2,
            'marks': 1, 'stem': 'Which?', 'options': {'A': 'Secret', 'B': 'Other'}, 'answer': 'A'}
    shown = tutor._present(item, block='practice', phase='practice')
    tutor.answer(f"{shown['n']}?")
    tutor.log({'type': 'topical_exclude', 'identity': 'excluded-retry', 'chapter': '9702-2.1', 'reason': 'test', 'missing': []})
    result = tutor.retry_skipped()
    assert result['restore_candidate'] == {'identity': 'excluded-retry', 'chapter': '9702-2.1'}
    assert tutor.topical_exclusions()
    assert tutor.restore_topical(**result['restore_candidate'])['ok']
    assert tutor.retry_skipped()['items'][0]['stem'] == 'Which?'


def test_now_hides_existing_lesson_notes_while_skipped_answer_is_protected(tmp_path):
    from fixtures import make_vault
    from tutorlib import session, store, views
    root = make_vault(tmp_path)
    tutor = session.Tutor(store.Vault(root))
    tutor.start('lesson', focus=['9702-2.1'])
    tutor.session['subtopic'] = '9702-2.1'
    notes = root / views.notes_rel(tutor.packs, '9702-2.1')
    notes.parent.mkdir(parents=True, exist_ok=True)
    notes.write_text('Previously learned: Secret answer')
    item = {'id': 'old-note-guard', 'kcs': ['9702-2.1.1'], 'kind': 'mcq', 'difficulty': 2,
            'marks': 1, 'stem': 'Which?', 'options': {'A': 'Secret answer', 'B': 'Other'}, 'answer': 'A'}
    shown = tutor._present(item, block='practice', phase='practice')
    tutor._write_now()
    assert '![[{}]]'.format(views.notes_rel(tutor.packs, '9702-2.1').removesuffix('.md')) not in (root / 'Now.md').read_text()
    tutor.answer(f"{shown['n']}?")
    tutor._write_now()
    assert '![[{}]]'.format(views.notes_rel(tutor.packs, '9702-2.1').removesuffix('.md')) not in (root / 'Now.md').read_text()
    retry = tutor.retry_skipped()
    tutor.answer(f"{retry['items'][0]['n']}A3")
    tutor._write_now()
    assert '![[{}]]'.format(views.notes_rel(tutor.packs, '9702-2.1').removesuffix('.md')) in (root / 'Now.md').read_text()
    assert notes.read_text() == 'Previously learned: Secret answer'


def test_different_idea_does_not_reveal_skipped_answer(tmp_path):
    from fixtures import make_vault
    from tutorlib import session, store
    tutor = session.Tutor(store.Vault(make_vault(tmp_path)))
    tutor.start('lesson', focus=['9702-2.1'])
    item = {'id': 'cross-idea-guard', 'kcs': ['9702-2.1.1'], 'kind': 'mcq', 'difficulty': 2,
            'marks': 1, 'stem': 'Which?', 'options': {'A': 'Secret answer', 'B': 'Other'}, 'answer': 'A'}
    shown = tutor._present(item, block='practice', phase='practice')
    tutor.answer(f"{shown['n']}?")
    other = next(k for k in tutor.packs.kcs if k != '9702-2.1.1')
    block = {'kind': 'node', 'kc': other,
             'card': {'terms': [{'term': 'Related fact', 'meaning': 'Secret answer'}]},
             'i': 0, 'phases': ['terms'], 'misses': 1, 'mistakes': []}
    activity = tutor._step_node(block, 0)
    assert 'Secret answer' not in str(activity)
    assert activity['part'] == 'guard_pause'
    retry = tutor.retry_skipped()
    tutor.answer(f"{retry['items'][0]['n']}A3")
    assert 'Secret answer' in tutor._step_node(block, 0)['text']


def test_hint_for_another_open_question_cannot_reveal_skipped_answer(tmp_path):
    from fixtures import make_vault
    from tutorlib import session, store
    root = make_vault(tmp_path)
    tutor = session.Tutor(store.Vault(root))
    tutor.start('lesson', focus=['9702-2.1'])
    skipped = {'id': 'hint-guard', 'kcs': ['9702-2.1.1'], 'kind': 'mcq', 'difficulty': 2,
               'marks': 1, 'stem': 'Which?', 'options': {'A': 'Secret answer', 'B': 'Other'}, 'answer': 'A'}
    other = {'id': 'hint-other', 'kcs': ['9702-2.1.1'], 'kind': 'mcq', 'difficulty': 2,
             'marks': 1, 'stem': 'Another question?', 'options': {'A': 'Yes', 'B': 'No'},
             'answer': 'A', 'hints': ['Secret answer']}
    shown = tutor._present(skipped, block='practice', phase='practice')
    second = tutor._present(other, block='practice', phase='practice')
    tutor.answer(f"{shown['n']}?")
    result = tutor.hint(second['n'])
    assert result.get('refused') and 'Secret answer' not in str(result)
    assert 'Secret answer' not in (root / 'Now.md').read_text()


def test_scheme_for_another_open_question_cannot_reveal_skipped_answer(tmp_path):
    from fixtures import make_vault
    from tutorlib import session, store
    tutor = session.Tutor(store.Vault(make_vault(tmp_path)))
    tutor.start('lesson', focus=['9702-2.1'])
    skipped = {'id': 'scheme-guard', 'kcs': ['9702-2.1.1'], 'kind': 'mcq', 'difficulty': 2,
               'marks': 1, 'stem': 'Which?', 'options': {'A': 'Secret answer', 'B': 'Other'}, 'answer': 'A'}
    other = {'id': 'scheme-other', 'kcs': ['9702-2.1.1'], 'kind': 'structured', 'difficulty': 2,
             'marks': 1, 'stem': 'Explain.', 'scheme': [{'mark': 'B1', 'point': 'Secret answer'}]}
    shown = tutor._present(skipped, block='practice', phase='practice')
    second = tutor._present(other, block='practice', phase='practice')
    tutor.answer(f"{shown['n']}?")
    assert 'Secret answer' not in str(tutor.scheme(second['n']))


def test_structured_draft_is_retained_in_open_question_across_restart(tmp_path):
    from fixtures import make_vault
    from tutorlib import session, store
    root = make_vault(tmp_path)
    tutor = session.Tutor(store.Vault(root))
    tutor.start('lesson', focus=['9702-2.1'])
    item = {'id': 'draft-work', 'kcs': ['9702-2.1.1'], 'kind': 'structured', 'difficulty': 2,
            'marks': 1, 'stem': 'Explain.', 'scheme': [{'mark': 'B1', 'point': 'A point'}]}
    shown = tutor._present(item, block='practice', phase='practice')
    assert tutor.save_structured_draft(shown['n'], 'My working')['ok']
    restored = session.Tutor(store.Vault(root))
    assert restored._view(shown['n'])['saved_work'] == 'My working'


def test_retry_suspends_open_and_queued_questions_without_losing_work(tmp_path):
    from fixtures import make_vault
    from tutorlib import session, store
    root = make_vault(tmp_path)
    tutor = session.Tutor(store.Vault(root))
    tutor.start('lesson', focus=['9702-2.1'])
    skipped = {'id': 'suspend-guard', 'kcs': ['9702-2.1.1'], 'kind': 'mcq', 'difficulty': 2,
               'marks': 1, 'stem': 'Which?', 'options': {'A': 'Secret answer', 'B': 'Other'}, 'answer': 'A'}
    other = {'id': 'suspend-other', 'kcs': ['9702-2.1.1'], 'kind': 'structured', 'difficulty': 2,
             'marks': 1, 'stem': 'Explain.', 'scheme': [{'mark': 'B1', 'point': 'A point'}]}
    queued = {'id': 'suspend-queue', 'kcs': ['9702-2.1.1'], 'kind': 'mcq', 'difficulty': 2,
              'marks': 1, 'stem': 'Later?', 'options': {'A': 'Yes', 'B': 'No'}, 'answer': 'A'}
    tutor.session['awaiting'] = None
    shown = tutor._present(skipped, block='practice', phase='practice')
    second = tutor._present(other, block='practice', phase='practice')
    n, waiting = tutor._number(queued, 'practice', 'practice')
    tutor.session.setdefault('queue', {})[n] = waiting
    tutor.answer(f"{shown['n']}?")
    tutor.save_structured_draft(second['n'], 'My working')
    assert tutor.suspend_questions_for_retry()['ok']
    restored = session.Tutor(store.Vault(root))
    assert not restored.start('test', focus=['9702-2.1'], replace=True).get('ok', True)
    assert restored.end().get('error')
    assert restored.next()['part'] == 'guard_pause'
    assert not restored.session['presented'] and not restored.session['queue']
    retry = restored.retry_skipped()
    restored.answer(f"{retry['items'][0]['n']}A3")
    resumed = restored.next()
    assert resumed['items'][0]['stem'] == 'Explain.'
    assert resumed['items'][0]['saved_work'] == 'My working'
    assert n in restored.session['queue']


def test_queued_question_waits_until_skipped_answer_is_attempted(tmp_path):
    from fixtures import make_vault
    from tutorlib import session, store
    root = make_vault(tmp_path)
    tutor = session.Tutor(store.Vault(root))
    tutor.start('lesson', focus=['9702-2.1'])
    skipped = {'id': 'queue-guard', 'kcs': ['9702-2.1.1'], 'kind': 'mcq', 'difficulty': 2,
               'marks': 1, 'stem': 'Which?', 'options': {'A': 'Secret answer', 'B': 'Other'}, 'answer': 'A'}
    queued = {'id': 'queue-leak', 'kcs': ['9702-2.1.1'], 'kind': 'mcq', 'difficulty': 2,
              'marks': 1, 'stem': 'Secret answer', 'options': {'A': 'Yes', 'B': 'No'}, 'answer': 'A'}
    shown = tutor._present(skipped, block='practice', phase='practice')
    n, pending = tutor._number(queued, 'practice', 'practice')
    tutor.session.setdefault('queue', {})[n] = pending
    tutor.answer(f"{shown['n']}?")
    activity = tutor.next()
    assert activity['part'] == 'guard_pause' and n in tutor.session['queue']
    tutor = session.Tutor(store.Vault(root))
    assert tutor.next()['part'] == 'guard_pause'
    retry = tutor.retry_skipped()
    tutor.answer(f"{retry['items'][0]['n']}A3")
    resumed = tutor.next()
    assert resumed['items'][0]['stem'] == 'Secret answer'


def test_guard_pause_preserves_prior_activity_across_restart(tmp_path):
    from fixtures import make_vault
    from tutorlib import session, store
    root = make_vault(tmp_path)
    tutor = session.Tutor(store.Vault(root))
    tutor.start('lesson', focus=['9702-2.1'])
    item = {'id': 'awaiting-guard', 'kcs': ['9702-2.1.1'], 'kind': 'mcq', 'difficulty': 2,
            'marks': 1, 'stem': 'Which?', 'options': {'A': 'Secret answer', 'B': 'Other'}, 'answer': 'A'}
    shown = tutor._present(item, block='practice', phase='practice')
    tutor.answer(f"{shown['n']}?")
    tutor.session['awaiting'] = {'activity': 'explain', 'part': 'prior', 'text': 'Secret answer', 'block_idx': None}
    assert tutor.next()['part'] == 'guard_pause'
    tutor = session.Tutor(store.Vault(root))
    retry = tutor.retry_skipped()
    tutor.answer(f"{retry['items'][0]['n']}A3")
    assert tutor.next()['part'] == 'prior'


def test_unavailable_retry_can_return_to_previously_open_question(tmp_path):
    from fixtures import make_vault
    from tutorlib import session, store
    root = make_vault(tmp_path)
    tutor = session.Tutor(store.Vault(root))
    tutor.start('lesson', focus=['9702-2.1'])
    skipped = {'id': 'unavailable-suspend', 'kcs': ['9702-2.1.1'], 'kind': 'mcq', 'difficulty': 2,
               'marks': 1, 'stem': 'Which?', 'options': {'A': 'Secret answer', 'B': 'Other'}, 'answer': 'A'}
    other = {'id': 'return-work', 'kcs': ['9702-2.1.1'], 'kind': 'structured', 'difficulty': 2,
             'marks': 1, 'stem': 'Explain.', 'scheme': [{'mark': 'B1', 'point': 'A point'}]}
    shown = tutor._present(skipped, block='practice', phase='practice')
    second = tutor._present(other, block='practice', phase='practice')
    tutor.answer(f"{shown['n']}?")
    tutor.save_structured_draft(second['n'], 'My working')
    tutor.log({'type': 'topical_exclude', 'identity': skipped['id'], 'chapter': '9702-2.1', 'reason': 'test', 'missing': []})
    assert tutor.suspend_questions_for_retry()['ok']
    assert tutor.retry_skipped()['activity'] == 'error'
    assert tutor.resume_suspended_questions()['ok']
    assert tutor._view(second['n'])['saved_work'] == 'My working'
    assert tutor.session['skipped_answer_guards']
    assert 'scheme' not in tutor.scheme(second['n'])


def test_feedback_for_another_question_does_not_reveal_skipped_answer(tmp_path):
    from fixtures import make_vault
    from tutorlib import session, store
    root = make_vault(tmp_path)
    tutor = session.Tutor(store.Vault(root))
    tutor.start('lesson', focus=['9702-2.1'])
    skipped = {'id': 'feedback-guard', 'kcs': ['9702-2.1.1'], 'kind': 'mcq', 'difficulty': 2,
               'marks': 1, 'stem': 'Which?', 'options': {'A': 'Secret answer', 'B': 'Other'}, 'answer': 'A'}
    other = {'id': 'feedback-other', 'kcs': ['9702-2.1.1'], 'kind': 'mcq', 'difficulty': 2,
             'marks': 1, 'stem': 'Another question?', 'options': {'A': 'Yes', 'B': 'No'},
             'answer': 'A', 'explanation': 'Secret answer'}
    shown = tutor._present(skipped, block='practice', phase='practice')
    second = tutor._present(other, block='practice', phase='practice')
    tutor.answer(f"{shown['n']}?")
    tutor.session['thread'] = []
    result = tutor.answer(f"{second['n']}A3")['results'][0]
    assert result.get('feedback_withheld')
    assert 'Secret answer' not in str(result)
    assert 'Secret answer' not in str(tutor.session['recent'][-1])
    assert 'Secret answer' not in (root / 'Now.md').read_text()
    assert tutor.end().get('error')
    tutor = session.Tutor(store.Vault(root))
    retry = tutor.retry_skipped()
    tutor.answer(f"{retry['items'][0]['n']}A3")
    released = tutor.next()
    assert 'Secret answer' in released['text']


def test_deferred_examiner_explanation_survives_answer_log_interruption(tmp_path, monkeypatch):
    from fixtures import make_vault
    from tutorlib import session, store
    root = make_vault(tmp_path)
    tutor = session.Tutor(store.Vault(root))
    tutor.start('lesson', focus=['9702-2.1'])
    skipped = {'id': 'replay-guard', 'kcs': ['9702-2.1.1'], 'kind': 'mcq', 'difficulty': 2,
               'marks': 1, 'stem': 'Which?', 'options': {'A': 'Secret', 'B': 'Other'}, 'answer': 'A'}
    other = {'id': 'replay-other', 'kcs': ['9702-2.1.1'], 'kind': 'mcq', 'difficulty': 2,
             'marks': 1, 'stem': 'Another?', 'options': {'A': 'Yes', 'B': 'No'}, 'answer': 'A'}
    shown = tutor._present(skipped, block='practice', phase='practice')
    second = tutor._present(other, block='practice', phase='practice')
    tutor.answer(f"{shown['n']}?")
    original = deferred_notes.resolve
    monkeypatch.setattr(deferred_notes, 'resolve', lambda *args: (_ for _ in ()).throw(OSError('interrupted')))
    with pytest.raises(OSError, match='interrupted'):
        tutor.answer(f"{second['n']}A3", explanation={second['n']: 'Examiner explanation'})
    monkeypatch.setattr(deferred_notes, 'resolve', original)
    restored = session.Tutor(store.Vault(root))
    assert restored.session['deferred_feedback'][0]['explanation'] == 'Examiner explanation'


def test_short_rubric_is_withheld_and_work_is_saved_during_guard(tmp_path):
    from fixtures import make_vault
    from tutorlib import session, store
    root = make_vault(tmp_path)
    tutor = session.Tutor(store.Vault(root))
    tutor.start('lesson', focus=['9702-2.1'])
    skipped = {'id': 'short-guard', 'kcs': ['9702-2.1.1'], 'kind': 'mcq', 'difficulty': 2,
               'marks': 1, 'stem': 'Which?', 'options': {'A': 'Secret answer', 'B': 'Other'}, 'answer': 'A'}
    other = {'id': 'short-other', 'kcs': ['9702-2.1.1'], 'kind': 'short', 'difficulty': 2,
             'marks': 1, 'stem': 'Explain.', 'rubric': [{'point': 'Secret answer', 'keywords': [['unrelated']]}]}
    shown = tutor._present(skipped, block='practice', phase='practice')
    second = tutor._present(other, block='practice', phase='practice')
    tutor.answer(f"{shown['n']}?")
    result = tutor.answer(f"{second['n']} = My working")['results'][0]
    assert result.get('needs_retry') and 'Secret answer' not in str(result)
    restored = session.Tutor(store.Vault(root))
    assert restored._view(second['n'])['saved_work'] == 'My working'


def test_retry_feedback_cannot_reveal_another_suspended_question(tmp_path):
    from fixtures import make_vault
    from tutorlib import session, store
    tutor = session.Tutor(store.Vault(make_vault(tmp_path)))
    tutor.start('lesson', focus=['9702-2.1'])
    skipped = {'id': 'retry-feedback', 'kcs': ['9702-2.1.1'], 'kind': 'mcq', 'difficulty': 2,
               'marks': 1, 'stem': 'Which?', 'options': {'A': 'Yes', 'B': 'No'}, 'answer': 'A',
               'explanation': 'The other answer is 42.'}
    other = {'id': 'suspended-secret', 'kcs': ['9702-2.1.1'], 'kind': 'numeric', 'difficulty': 2,
             'marks': 1, 'stem': 'Find the value.', 'answer': {'value': 42, 'unit': ''}}
    shown = tutor._present(skipped, block='practice', phase='practice')
    tutor._present(other, block='practice', phase='practice')
    tutor.answer(f"{shown['n']}?")
    tutor.suspend_questions_for_retry()
    retry = tutor.retry_skipped()
    feedback = tutor.answer(f"{retry['items'][0]['n']}A3")['results'][0]
    assert feedback.get('feedback_withheld') and 'The other answer is 42.' not in str(feedback)


def test_single_skipped_short_question_can_be_attempted_and_marked(tmp_path):
    from fixtures import make_vault
    from tutorlib import session, store
    tutor = session.Tutor(store.Vault(make_vault(tmp_path)))
    tutor.start('lesson', focus=['9702-2.1'])
    item = {'id': 'single-short-retry', 'kcs': ['9702-2.1.1'], 'kind': 'short', 'difficulty': 2,
            'marks': 1, 'stem': 'Explain.', 'rubric': [{'point': 'A valid answer', 'keywords': [['valid']]}]}
    shown = tutor._present(item, block='practice', phase='practice')
    tutor.answer(f"{shown['n']}?")
    retry = tutor.retry_skipped()
    n = retry['items'][0]['n']
    result = tutor.answer(f'{n} = A valid answer', judge={n: 1})['results'][0]
    assert result.get('event') and not result.get('needs_retry')
    assert not tutor.session['skipped_answer_guards']


def test_two_skipped_short_questions_can_be_retried_safely(tmp_path):
    from fixtures import make_vault
    from tutorlib import session, store
    tutor = session.Tutor(store.Vault(make_vault(tmp_path)))
    tutor.start('lesson', focus=['9702-2.1'])
    for ident in ('short-one', 'short-two'):
        item = {'id': ident, 'kcs': ['9702-2.1.1'], 'kind': 'short', 'difficulty': 2,
                'marks': 1, 'stem': 'Explain.', 'rubric': [{'point': ident, 'keywords': [[ident]]}]}
        shown = tutor._present(item, block='practice', phase='practice')
        tutor.answer(f"{shown['n']}?")
    retry = tutor.retry_skipped()
    n = retry['items'][0]['n']
    result = tutor.answer(f'{n} = My attempt', judge={n: 1})['results'][0]
    assert result.get('attempt_saved') and not result.get('needs_retry')
    assert len(tutor.session['skipped_answer_guards']) == 1
    assert tutor.session['deferred_judgments'][0]['saved_work'] == 'My attempt'
    assert tutor.session['answered'] == 2  # the saved attempt has not been graded
    tutor = session.Tutor(store.Vault(tutor.vault.root))
    second = tutor.retry_skipped()
    second_n = second['items'][0]['n']
    tutor.answer(f'{second_n} = My second attempt', judge={second_n: 1})
    deferred = tutor.next()
    assert deferred['items'][0]['saved_work'] == 'My attempt'
    assert tutor.end().get('error')
    assert not tutor.start('test', focus=['9702-2.1'], replace=True).get('ok', True)
    n = deferred['items'][0]['n']
    result = tutor.answer(f'{n} = My attempt', judge={n: 1})['results'][0]
    assert result['correct'] and tutor.session['answered'] == 4


@pytest.mark.parametrize('response', ['I have no idea', '???', 'no', "I can't answer", 'I do not know', 'not sure'])
def test_retry_gives_up_on_obvious_non_attempts(tmp_path, response):
    from fixtures import make_vault
    from tutorlib import session, store
    tutor = session.Tutor(store.Vault(make_vault(tmp_path)))
    tutor.start('lesson', focus=['9702-2.1'])
    for ident in ('nonattempt-one', 'nonattempt-two'):
        item = {'id': ident, 'kcs': ['9702-2.1.1'], 'kind': 'short', 'difficulty': 2,
                'marks': 1, 'stem': 'Explain.', 'rubric': [{'point': ident, 'keywords': [[ident]]}]}
        shown = tutor._present(item, block='practice', phase='practice')
        tutor.answer(f"{shown['n']}?")
    retry = tutor.retry_skipped()
    result = tutor.answer(f"{retry['items'][0]['n']} = {response}")['results'][0]
    assert not result.get('error') and not result.get('attempt_saved')
    assert result['answer'] == 'nonattempt-one' and not result.get('answer_withheld')
    assert len(tutor.session['skipped_answer_guards']) == 1


def test_ungraded_retry_recovers_after_log_interruption(tmp_path, monkeypatch):
    from fixtures import make_vault
    from tutorlib import session, store
    root = make_vault(tmp_path)
    tutor = session.Tutor(store.Vault(root))
    tutor.start('lesson', focus=['9702-2.1'])
    for ident in ('recovery-short-one', 'recovery-short-two'):
        item = {'id': ident, 'kcs': ['9702-2.1.1'], 'kind': 'short', 'difficulty': 2,
                'marks': 1, 'stem': 'Explain.', 'rubric': [{'point': ident, 'keywords': [[ident]]}]}
        shown = tutor._present(item, block='practice', phase='practice')
        tutor.answer(f"{shown['n']}?")
    retry = tutor.retry_skipped()
    original = deferred_notes.resolve
    monkeypatch.setattr(deferred_notes, 'resolve', lambda *args: (_ for _ in ()).throw(OSError('interrupted')))
    with pytest.raises(OSError, match='interrupted'):
        tutor.answer(f"{retry['items'][0]['n']} = My saved attempt")
    monkeypatch.setattr(deferred_notes, 'resolve', original)
    restored = session.Tutor(store.Vault(root))
    assert len(restored.session['skipped_answer_guards']) == 1
    assert [p['saved_work'] for p in restored.session['deferred_judgments']] == ['My saved attempt']
    restored = session.Tutor(store.Vault(root))
    assert len(restored.session['deferred_judgments']) == 1


def test_exclusion_after_reopening_saved_attempt_preserves_it_on_restart(tmp_path):
    from fixtures import make_vault
    from tutorlib import session, store
    root = make_vault(tmp_path)
    tutor = session.Tutor(store.Vault(root))
    tutor.start('lesson', focus=['9702-2.1'])
    item = {'id': 'excluded-saved-attempt', 'kcs': ['9702-2.1.1'], 'kind': 'short', 'difficulty': 2,
            'marks': 1, 'stem': 'Explain.', 'rubric': [{'point': 'A point', 'keywords': [['point']]}]}
    n, p = tutor._number(item, 'deferred_judgment', 'practice')
    p['saved_work'] = 'My original attempt'
    assert tutor._open(n, p)
    tutor.log({'type': 'topical_exclude', 'identity': item['id'], 'chapter': '9702-2.1',
               'reason': 'test', 'missing': []})
    restored = session.Tutor(store.Vault(root))
    assert restored.session['deferred_judgments'][0]['saved_work'] == 'My original attempt'
    assert restored.end().get('error')
    activity = restored.next()
    assert activity['activity'] == 'saved_judgment_unavailable'
    assert activity['restore_candidate'] == {'identity': item['id'], 'chapter': '9702-2.1'}


def test_unavailable_saved_judgment_can_be_postponed_across_sessions(tmp_path):
    from fixtures import make_vault
    from tutorlib import session, store
    root = make_vault(tmp_path)
    tutor = session.Tutor(store.Vault(root))
    tutor.start('lesson', focus=['9702-2.1'])
    item = {'id': 'postpone-unavailable', 'kcs': ['9702-2.1.1'], 'kind': 'short', 'difficulty': 2,
            'marks': 1, 'stem': 'Explain.', 'rubric': [{'point': 'A point', 'keywords': [['point']]}]}
    _, p = tutor._number(item, 'deferred_judgment', 'practice')
    p['saved_work'] = 'My original attempt'
    tutor.session['deferred_judgments'] = [p]
    tutor.log({'type': 'topical_exclude', 'identity': item['id'], 'chapter': '9702-2.1',
               'reason': 'test', 'missing': []})
    assert tutor.next()['activity'] == 'saved_judgment_unavailable'
    assert tutor.postpone_saved_judgment()['ok']
    assert len(tutor.postponed_judgments()) == 1
    assert not tutor.end().get('error')
    restored = session.Tutor(store.Vault(root))
    restored.start('test', focus=['9702-2.1'])
    assert not restored.session.get('deferred_judgments')  # still excluded
    restored.restore_topical(item['id'], '9702-2.1')
    restored.end()
    restored.start('test', focus=['9702-2.1'])
    assert restored.session['deferred_judgments'][0]['saved_work'] == 'My original attempt'
    activity = restored.next()
    n = activity['items'][0]['n']
    result = restored.answer(f'{n} = My original attempt', judge={n: 1})['results'][0]
    assert result['correct'] and not restored.postponed_judgments()


def test_postponement_replay_does_not_remove_an_identical_second_attempt(tmp_path):
    from fixtures import make_vault
    from tutorlib import session, store
    import copy
    root = make_vault(tmp_path)
    tutor = session.Tutor(store.Vault(root))
    tutor.start('lesson', focus=['9702-2.1'])
    item = {'id': 'identical-attempts', 'kcs': ['9702-2.1.1'], 'kind': 'short', 'difficulty': 2,
            'marks': 1, 'stem': 'Explain.', 'rubric': [{'point': 'A point', 'keywords': [['point']]}]}
    _, p = tutor._number(item, 'deferred_judgment', 'practice')
    p['saved_work'] = 'Same working'
    tutor.session['deferred_judgments'] = [copy.deepcopy(p), copy.deepcopy(p)]
    assert tutor.postpone_saved_judgment()['ok']
    restored = session.Tutor(store.Vault(root))
    assert len(restored.session['deferred_judgments']) == 1
    assert len(restored.postponed_judgments()) == 1


def test_postponement_recovers_after_event_log_interruption(tmp_path, monkeypatch):
    from fixtures import make_vault
    from tutorlib import session, store
    root = make_vault(tmp_path)
    tutor = session.Tutor(store.Vault(root))
    tutor.start('lesson', focus=['9702-2.1'])
    item = {'id': 'postpone-interrupted', 'kcs': ['9702-2.1.1'], 'kind': 'short', 'difficulty': 2,
            'marks': 1, 'stem': 'Explain.', 'rubric': [{'point': 'A point', 'keywords': [['point']]}]}
    _, p = tutor._number(item, 'deferred_judgment', 'practice')
    p['saved_work'] = 'My working'
    tutor.session['deferred_judgments'] = [p]
    original = tutor.log
    def interrupted(event):
        result = original(event)
        if event.get('type') == 'postponed_judgment':
            raise OSError('interrupted')
        return result
    monkeypatch.setattr(tutor, 'log', interrupted)
    with pytest.raises(OSError, match='interrupted'):
        tutor.postpone_saved_judgment()
    restored = session.Tutor(store.Vault(root))
    assert not restored.session.get('deferred_judgments')
    assert [x['saved_work'] for x in restored.postponed_judgments()] == ['My working']


def test_failed_postponement_log_does_not_discard_attempt_on_retry(tmp_path, monkeypatch):
    from fixtures import make_vault
    from tutorlib import session, store
    tutor = session.Tutor(store.Vault(make_vault(tmp_path)))
    tutor.start('lesson', focus=['9702-2.1'])
    item = {'id': 'postpone-failed-log', 'kcs': ['9702-2.1.1'], 'kind': 'short', 'difficulty': 2,
            'marks': 1, 'stem': 'Explain.', 'rubric': [{'point': 'A point', 'keywords': [['point']]}]}
    _, p = tutor._number(item, 'deferred_judgment', 'practice')
    p['saved_work'] = 'My working'
    tutor.session['deferred_judgments'] = [p]
    with monkeypatch.context() as patch:
        patch.setattr(tutor, 'log', lambda event: (_ for _ in ()).throw(OSError('not written')))
        with pytest.raises(OSError, match='not written'):
            tutor.postpone_saved_judgment()
    assert tutor.postpone_saved_judgment()['ok']
    assert [x['saved_work'] for x in tutor.postponed_judgments()] == ['My working']


def test_postponement_retry_after_logged_event_does_not_duplicate_archive(tmp_path, monkeypatch):
    from fixtures import make_vault
    from tutorlib import session, store
    tutor = session.Tutor(store.Vault(make_vault(tmp_path)))
    tutor.start('lesson', focus=['9702-2.1'])
    item = {'id': 'postpone-after-log', 'kcs': ['9702-2.1.1'], 'kind': 'short', 'difficulty': 2,
            'marks': 1, 'stem': 'Explain.', 'rubric': [{'point': 'A point', 'keywords': [['point']]}]}
    _, p = tutor._number(item, 'deferred_judgment', 'practice')
    p['saved_work'] = 'My working'
    tutor.session['deferred_judgments'] = [p]
    original = tutor.log
    def interrupted(event):
        result = original(event)
        if event.get('type') == 'postponed_judgment':
            raise OSError('after log')
        return result
    with monkeypatch.context() as patch:
        patch.setattr(tutor, 'log', interrupted)
        with pytest.raises(OSError, match='after log'):
            tutor.postpone_saved_judgment()
    assert tutor.postpone_saved_judgment()['ok']
    assert [x['saved_work'] for x in tutor.postponed_judgments()] == ['My working']


def test_logged_judgment_is_replayed_before_new_exclusion(tmp_path, monkeypatch):
    from fixtures import make_vault
    from tutorlib import session, store
    root = make_vault(tmp_path)
    vault = store.Vault(root)
    tutor = session.Tutor(vault)
    tutor.start('lesson', focus=['9702-2.1'])
    item = {'id': 'judgment-before-exclusion', 'kcs': ['9702-2.1.1'], 'kind': 'short', 'difficulty': 2,
            'marks': 1, 'stem': 'Explain.', 'rubric': [{'point': 'A point', 'keywords': [['point']]}]}
    n, p = tutor._number(item, 'deferred_judgment', 'practice')
    p['saved_work'] = 'My original attempt'
    assert tutor._open(n, p)
    original = tutor.log
    def interrupted(event):
        result = original(event)
        if event.get('type') == 'answer':
            raise OSError('interrupted')
        return result
    monkeypatch.setattr(tutor, 'log', interrupted)
    with pytest.raises(OSError, match='interrupted'):
        tutor.answer(f'{n} = My original attempt', judge={int(n): 1})
    vault.append_event({'type': 'topical_exclude', 'identity': item['id'], 'chapter': '9702-2.1',
                        'reason': 'test', 'missing': []})
    restored = session.Tutor(store.Vault(root))
    assert not restored.session.get('deferred_judgments')
    assert n not in restored.session['presented']
    assert restored.session['answered'] == 1
    assert sum(e.get('type') == 'answer' and e.get('item') == item['id'] for e in vault.events()) == 1
    assert session.Tutor(store.Vault(root)).session['answered'] == 1


def test_postponing_saved_attempt_does_not_record_a_new_skip(tmp_path):
    from fixtures import make_vault
    from tutorlib import session, store
    tutor = session.Tutor(store.Vault(make_vault(tmp_path)))
    tutor.start('lesson', focus=['9702-2.1'])
    item = {'id': 'postponed-saved-attempt', 'kcs': ['9702-2.1.1'], 'kind': 'short', 'difficulty': 2,
            'marks': 1, 'stem': 'Explain.', 'rubric': [{'point': 'A point', 'keywords': [['point']]}]}
    n, p = tutor._number(item, 'deferred_judgment', 'practice')
    p['saved_work'] = 'My original attempt'
    assert tutor._open(n, p)
    before = tutor.session['answered']
    result = tutor.answer(f'{n}?')['results'][0]
    assert result.get('judgment_postponed')
    assert tutor.session['answered'] == before
    assert tutor.session['deferred_judgments'][0]['saved_work'] == 'My original attempt'


def test_unavailable_cross_idea_retry_pauses_other_lessons(tmp_path):
    from fixtures import make_vault
    from tutorlib import session, store
    tutor = session.Tutor(store.Vault(make_vault(tmp_path)))
    tutor.start('lesson', focus=['9702-2.1'])
    item = {'id': 'unavailable-cross-idea', 'kcs': ['9702-2.1.1'], 'kind': 'mcq', 'difficulty': 2,
            'marks': 1, 'stem': 'Which?', 'options': {'A': 'Secret answer', 'B': 'Other'}, 'answer': 'A'}
    shown = tutor._present(item, block='practice', phase='practice')
    tutor.answer(f"{shown['n']}?")
    assert tutor.skipped_retry_available()
    tutor.log({'type': 'topical_exclude', 'identity': 'unavailable-cross-idea', 'chapter': '9702-2.1',
               'reason': 'test', 'missing': []})
    assert not tutor.skipped_retry_available()
    other = next(k for k in tutor.packs.kcs if k != '9702-2.1.1')
    block = {'kind': 'node', 'kc': other, 'card': {'terms': [{'term': 'Related', 'meaning': 'A fact'}]},
             'i': 0, 'phases': ['terms'], 'misses': 0, 'mistakes': []}
    assert tutor._step_node(block, 0)['part'] == 'guard_pause'
    assert tutor.retry_skipped()['restore_candidate']['identity'] == 'unavailable-cross-idea'


def test_unavailable_cross_idea_does_not_disclose_skipped_answer(tmp_path):
    from fixtures import make_vault
    from tutorlib import session, store
    tutor = session.Tutor(store.Vault(make_vault(tmp_path)))
    tutor.start('lesson', focus=['9702-2.1'])
    item = {'id': 'unavailable-answer', 'kcs': ['9702-2.1.1'], 'kind': 'mcq', 'difficulty': 2,
            'marks': 1, 'stem': 'Which?', 'options': {'A': 'Secret answer', 'B': 'Other'}, 'answer': 'A'}
    shown = tutor._present(item, block='practice', phase='practice')
    tutor.answer(f"{shown['n']}?")
    tutor.log({'type': 'topical_exclude', 'identity': item['id'], 'chapter': '9702-2.1',
               'reason': 'test', 'missing': []})
    other = next(k for k in tutor.packs.kcs if k != '9702-2.1.1')
    block = {'kind': 'node', 'kc': other,
             'card': {'terms': [{'term': 'Related', 'meaning': 'Secret answer'}]},
             'i': 0, 'phases': ['terms'], 'misses': 0, 'mistakes': []}
    assert 'Secret answer' not in str(tutor._step_node(block, 0))


def test_cross_idea_pause_and_exact_retry_survive_restart(tmp_path):
    from fixtures import make_vault
    from tutorlib import session, store
    root = make_vault(tmp_path)
    tutor = session.Tutor(store.Vault(root))
    tutor.start('lesson', focus=['9702-2.1'])
    item = {'id': 'cross-idea-restart', 'kcs': ['9702-2.1.1'], 'kind': 'mcq', 'difficulty': 2,
            'marks': 1, 'stem': 'Which?', 'options': {'A': 'Secret answer', 'B': 'Other'}, 'answer': 'A'}
    shown = tutor._present(item, block='practice', phase='practice')
    tutor.answer(f"{shown['n']}?")
    other = next(k for k in tutor.packs.kcs if k != '9702-2.1.1')
    block = {'kind': 'node', 'kc': other,
             'card': {'terms': [{'term': 'Related fact', 'meaning': 'Secret answer'}]},
             'i': 0, 'phases': ['terms'], 'misses': 1, 'mistakes': []}
    tutor.session['blocks'] = [block]
    tutor.session['cursor'] = 0
    assert tutor.next()['part'] == 'guard_pause'
    tutor = session.Tutor(store.Vault(root))
    assert tutor.next()['part'] == 'guard_pause'
    retry = tutor.retry_skipped()
    assert retry['items'][0]['stem'] == 'Which?'
    tutor = session.Tutor(store.Vault(root))
    assert tutor.next()['items'][0]['stem'] == 'Which?'
    tutor.answer(f"{retry['items'][0]['n']}A3")
    assert 'Secret answer' in tutor.next()['text']


def test_excluded_text_question_can_be_attempted_without_marking_or_restoring(tmp_path):
    from fixtures import make_vault
    from tutorlib import session, store
    tutor = session.Tutor(store.Vault(make_vault(tmp_path)))
    tutor.start('lesson', focus=['9702-2.1'])
    item = {'id': 'excluded-text', 'kcs': ['9702-2.1.1'], 'kind': 'mcq', 'difficulty': 2,
            'marks': 1, 'stem': 'Which?', 'options': {'A': 'One', 'B': 'Two'}, 'answer': 'A'}
    shown = tutor._present(item, block='practice', phase='practice')
    tutor.answer(f"{shown['n']}?")
    tutor.log({'type': 'topical_exclude', 'identity': item['id'], 'chapter': '9702-2.1', 'reason': 'test', 'missing': []})
    answered = tutor.session['answered']
    retry = tutor.retry_skipped_ungraded()
    assert retry['activity'] == 'questions'
    result = tutor.answer(f"{retry['items'][0]['n']}B")['results'][0]
    assert result.get('attempt_saved') and 'answer' not in result
    assert tutor.session['answered'] == answered
    assert tutor.topical_exclusions('9702-2.1')
    assert not tutor.session['skipped_answer_guards']
    assert tutor.session['deferred_judgments'][0]['saved_work'] == 'B'


def test_ungraded_unavailable_skip_does_not_record_answer(tmp_path):
    from fixtures import make_vault
    from tutorlib import session, store
    tutor = session.Tutor(store.Vault(make_vault(tmp_path)))
    tutor.start('lesson', focus=['9702-2.1'])
    item = {'id': 'skip-again', 'kcs': ['9702-2.1.1'], 'kind': 'mcq', 'difficulty': 2,
            'marks': 1, 'stem': 'Which?', 'options': {'A': 'One', 'B': 'Two'}, 'answer': 'A'}
    shown = tutor._present(item, block='practice', phase='practice')
    tutor.answer(f"{shown['n']}?")
    tutor.log({'type': 'topical_exclude', 'identity': item['id'], 'chapter': '9702-2.1', 'reason': 'test', 'missing': []})
    answered = tutor.session['answered']
    n = tutor.retry_skipped_ungraded()['items'][0]['n']
    tutor.answer(f'{n}?')
    assert tutor.session['answered'] == answered
    assert tutor.session['skipped_answer_guards']
    assert not tutor.session['presented']


def test_ungraded_retry_can_be_marked_once_after_restoration(tmp_path):
    from fixtures import make_vault
    from tutorlib import session, store
    tutor = session.Tutor(store.Vault(make_vault(tmp_path)))
    tutor.start('lesson', focus=['9702-2.1'])
    item = {'id': 'mark-later', 'kcs': ['9702-2.1.1'], 'kind': 'mcq', 'difficulty': 2,
            'marks': 1, 'stem': 'Which?', 'options': {'A': 'One', 'B': 'Two'}, 'answer': 'A'}
    shown = tutor._present(item, block='practice', phase='practice')
    tutor.answer(f"{shown['n']}?")
    tutor.log({'type': 'topical_exclude', 'identity': item['id'], 'chapter': '9702-2.1', 'reason': 'test', 'missing': []})
    n = tutor.retry_skipped_ungraded()['items'][0]['n']
    tutor.answer(f'{n}B')
    tutor.restore_topical(identity=item['id'], chapter='9702-2.1')
    pending = tutor.next()
    n = pending['items'][0]['n']
    result = tutor.answer(f'{n}B')['results'][0]
    assert not result.get('attempt_saved') and not tutor.session['deferred_judgments']


def test_ungraded_unavailable_retry_recovers_after_interrupted_save(tmp_path, monkeypatch):
    from fixtures import make_vault
    from tutorlib import session, store
    root = make_vault(tmp_path)
    tutor = session.Tutor(store.Vault(root))
    tutor.start('lesson', focus=['9702-2.1'])
    item = {'id': 'ungraded-crash', 'kcs': ['9702-2.1.1'], 'kind': 'mcq', 'difficulty': 2,
            'marks': 1, 'stem': 'Which?', 'options': {'A': 'One', 'B': 'Two'}, 'answer': 'A'}
    shown = tutor._present(item, block='practice', phase='practice')
    tutor.answer(f"{shown['n']}?")
    tutor.log({'type': 'topical_exclude', 'identity': item['id'], 'chapter': '9702-2.1', 'reason': 'test', 'missing': []})
    answered = tutor.session['answered']
    n = tutor.retry_skipped_ungraded()['items'][0]['n']
    original = deferred_notes.resolve
    monkeypatch.setattr(deferred_notes, 'resolve', lambda *args: (_ for _ in ()).throw(OSError('interrupted')))
    with pytest.raises(OSError, match='interrupted'):
        tutor.answer(f'{n}B')
    monkeypatch.setattr(deferred_notes, 'resolve', original)
    restored = session.Tutor(store.Vault(root))
    assert restored.session['answered'] == answered
    assert len(restored.session['deferred_judgments']) == 1
    assert restored.session['deferred_judgments'][0]['saved_work'] == 'B'
    assert not restored.session['skipped_answer_guards']
    assert restored.topical_exclusions('9702-2.1')


def test_targeted_retry_chooses_requested_guard_after_restore(tmp_path):
    from fixtures import make_vault
    from tutorlib import session, store
    tutor = session.Tutor(store.Vault(make_vault(tmp_path)))
    tutor.start('lesson', focus=['9702-2.1'])
    for ident in ('first-guard', 'second-guard'):
        item = {'id': ident, 'kcs': ['9702-2.1.1'], 'kind': 'mcq', 'difficulty': 2,
                'marks': 1, 'stem': ident, 'options': {'A': 'One', 'B': 'Two'}, 'answer': 'A'}
        shown = tutor._present(item, block='practice', phase='practice')
        tutor.answer(f"{shown['n']}?")
    retry = tutor.retry_skipped(identity='second-guard', chapter='9702-2.1')
    assert retry['items'][0]['stem'] == 'second-guard'


def test_targeted_retry_distinguishes_variants_of_same_item(tmp_path):
    from fixtures import make_vault
    from tutorlib import session, store
    tutor = session.Tutor(store.Vault(make_vault(tmp_path)))
    tutor.start('lesson', focus=['9702-2.1'])
    for stem in ('First variant?', 'Second variant?'):
        item = {'id': 'same-item', 'kcs': ['9702-2.1.1'], 'kind': 'mcq', 'difficulty': 2,
                'marks': 1, 'stem': stem, 'options': {'A': 'One', 'B': 'Two'}, 'answer': 'A'}
        shown = tutor._present(item, block='practice', phase='practice')
        tutor.answer(f"{shown['n']}?")
    guard = next(key for key, value in tutor.session['skipped_answer_guards'].items()
                 if value['question']['inst']['stem'] == 'Second variant?')
    retry = tutor.retry_skipped(identity='same-item', chapter='9702-2.1', guard_id=guard)
    assert retry['items'][0]['stem'] == 'Second variant?'


def test_retry_question_excerpt_is_compact_and_marks_truncation():
    from tutorlib.session import _question_excerpt
    assert _question_excerpt('A short\nquestion') == 'A short question'
    excerpt = _question_excerpt('Long question ' * 30)
    assert len(excerpt) <= 90 and excerpt.endswith('…')


def test_guard_draft_compare_update_preserves_external_edit(tmp_path):
    import copy
    from tutorlib import deferred_notes
    path = tmp_path / 'deferred.json'
    original = {'kind': 'short', 'key': 'secret', 'question': {'inst': {'id': 'q'}, 'saved_work': 'old'}}
    deferred_notes.hold(path, 'q', original)
    external = copy.deepcopy(original)
    external['question']['saved_work'] = 'external work'
    deferred_notes.hold(path, 'q', external)
    proposed = copy.deepcopy(original)
    proposed['question']['saved_work'] = 'my work'
    assert deferred_notes.compare_update(path, 'q', original, proposed) == 'conflict'
    assert deferred_notes.outstanding(path)['q'] == external
    assert deferred_notes.compare_update(path, 'q', external, proposed) == 'applied'
    assert deferred_notes.compare_update(path, 'q', external, proposed) == 'already_applied'
    assert deferred_notes.outstanding(path)['q'] == proposed


def test_guard_draft_compare_update_rejects_key_change_and_allows_empty_draft(tmp_path):
    import copy
    from tutorlib import deferred_notes
    path = tmp_path / 'deferred.json'
    original = {'kind': 'short', 'key': 'secret', 'question': {'inst': {'id': 'q'}, 'saved_work': 'work'}}
    deferred_notes.hold(path, 'q', original)
    invalid = copy.deepcopy(original)
    invalid['key'] = 'different'
    with pytest.raises(ValueError):
        deferred_notes.compare_update(path, 'q', original, invalid)
    cleared = copy.deepcopy(original)
    cleared['question']['saved_work'] = ''
    assert deferred_notes.compare_update(path, 'q', original, cleared) == 'applied'
    assert deferred_notes.outstanding(path)['q'] == cleared
    assert deferred_notes.compare_update(path, 'missing', original, cleared) == 'conflict'


def test_guard_draft_compare_update_rejects_malformed_or_type_changed_input(tmp_path):
    import copy
    from tutorlib import deferred_notes
    path = tmp_path / 'deferred.json'
    guard = {'kind': 'short', 'key': 'secret', 'question': {'inst': {'id': 'q', 'marks': 1}, 'saved_work': 'x'}}
    deferred_notes.hold(path, 'q', guard)
    with pytest.raises(ValueError):
        deferred_notes.compare_update(path, 'q', None, guard)
    malformed = copy.deepcopy(guard)
    malformed['question']['saved_work'] = ['not text']
    with pytest.raises(ValueError):
        deferred_notes.compare_update(path, 'q', guard, malformed)
    changed = copy.deepcopy(guard)
    changed['question']['inst']['marks'] = True
    with pytest.raises(ValueError):
        deferred_notes.compare_update(path, 'q', guard, changed)
    assert deferred_notes.outstanding(path)['q'] == guard


def test_guard_store_serializes_read_modify_write_across_writers(tmp_path, monkeypatch):
    import threading
    path = tmp_path / 'guards.json'
    first_read = threading.Event()
    release = threading.Event()
    second_read = threading.Event()
    real_read = deferred_notes._read
    def blocked_read(path_arg):
        data = real_read(path_arg)
        if threading.current_thread().name == 'first':
            first_read.set()
            assert release.wait(3)
        else:
            second_read.set()
        return data
    monkeypatch.setattr(deferred_notes, '_read', blocked_read)
    first = threading.Thread(name='first', target=deferred_notes.hold, args=(path, 'a', {'kind': 'short', 'key': 'a'}))
    second = threading.Thread(name='second', target=deferred_notes.hold, args=(path, 'b', {'kind': 'short', 'key': 'b'}))
    first.start()
    assert first_read.wait(2)
    second.start()
    try:
        assert not second_read.wait(.2)
    finally:
        release.set()
        first.join(3)
        second.join(3)
    assert not first.is_alive() and not second.is_alive()
    assert set(real_read(path)['guards']) == {'a', 'b'}


@pytest.mark.xfail(strict=True, reason='draft operation journal not integrated')
def test_cancel_retry_replays_draft_operation_after_store_write_interruption(tmp_path, monkeypatch):
    from fixtures import make_vault
    from tutorlib import session, store
    root = make_vault(tmp_path)
    tutor = session.Tutor(store.Vault(root))
    tutor.start('lesson', focus=['9702-2.1'])
    item = {'id': 'cancel-replay', 'kcs': ['9702-2.1.1'], 'kind': 'structured', 'difficulty': 2,
            'marks': 1, 'stem': 'Explain.', 'scheme': [{'mark': 'B1', 'point': 'Private'}]}
    shown = tutor._present(item, block='practice', phase='practice')
    tutor.answer(f"{shown['n']}?")
    retry = tutor.retry_skipped_ungraded()
    n = retry['items'][0]['n']
    original = deferred_notes.compare_update
    monkeypatch.setattr(deferred_notes, 'compare_update', lambda *args: (_ for _ in ()).throw(OSError('interrupted')))
    with pytest.raises(OSError, match='interrupted'):
        tutor.cancel_ungraded_structured(n, 'My saved work')
    monkeypatch.setattr(deferred_notes, 'compare_update', original)
    restored = session.Tutor(store.Vault(root))
    guards = deferred_notes.outstanding(root / '.tutor/state/deferred-notes.json')
    assert next(iter(guards.values()))['question']['saved_work'] == 'My saved work'
    assert not restored.session['presented']
    assert restored.retry_skipped_ungraded()['items'][0]['saved_work'] == 'My saved work'


@pytest.mark.xfail(strict=True, reason='draft conflict recovery not integrated')
def test_cancel_retry_preserves_both_drafts_if_store_changes(tmp_path, monkeypatch):
    import copy
    from fixtures import make_vault
    from tutorlib import session, store
    root = make_vault(tmp_path)
    tutor = session.Tutor(store.Vault(root))
    tutor.start('lesson', focus=['9702-2.1'])
    item = {'id': 'cancel-conflict', 'kcs': ['9702-2.1.1'], 'kind': 'structured', 'difficulty': 2,
            'marks': 1, 'stem': 'Explain.', 'scheme': [{'mark': 'B1', 'point': 'Private'}]}
    shown = tutor._present(item, block='practice', phase='practice')
    tutor.answer(f"{shown['n']}?")
    retry = tutor.retry_skipped_ungraded()
    n = retry['items'][0]['n']
    original = deferred_notes.compare_update
    def competing_edit(path, ident, expected, proposed):
        other = copy.deepcopy(expected)
        other['question']['saved_work'] = 'Other work'
        deferred_notes.hold(path, ident, other)
        return original(path, ident, expected, proposed)
    monkeypatch.setattr(deferred_notes, 'compare_update', competing_edit)
    assert not tutor.cancel_ungraded_structured(n, 'My work')['ok']
    monkeypatch.setattr(deferred_notes, 'compare_update', original)
    restored = session.Tutor(store.Vault(root))
    op = restored.session['guard_draft_operation']
    assert op['proposed']['question']['saved_work'] == 'My work'
    assert deferred_notes.outstanding(root / '.tutor/state/deferred-notes.json')[op['guard']]['question']['saved_work'] == 'Other work'
    assert restored.end().get('error')


def test_recovery_retains_both_guard_drafts_when_store_and_session_diverge(tmp_path):
    import copy
    from fixtures import make_vault
    from tutorlib import session, store
    root = make_vault(tmp_path)
    tutor = session.Tutor(store.Vault(root))
    tutor.start('lesson', focus=['9702-2.1'])
    item = {'id': 'divergent-draft', 'kcs': ['9702-2.1.1'], 'kind': 'structured', 'difficulty': 2,
            'marks': 1, 'stem': 'Explain.', 'scheme': [{'mark': 'B1', 'point': 'Private'}]}
    shown = tutor._present(item, 'practice', 'practice')
    tutor.answer(f"{shown['n']}?")
    ident, guard = next(iter(tutor.session['skipped_answer_guards'].items()))
    guard['question']['saved_work'] = 'session draft'
    tutor._save()
    path = root / '.tutor/state/deferred-notes.json'
    newer = copy.deepcopy(guard)
    newer['question']['saved_work'] = 'other draft'
    deferred_notes.hold(path, ident, newer)
    restored = session.Tutor(store.Vault(root))
    assert restored.session['skipped_answer_guards'][ident]['question']['saved_work'] == 'session draft'
    assert 'other draft' in deferred_notes.draft_history(path, ident)
    assert ident in deferred_notes.outstanding(path)


def test_retained_drafts_available_only_for_sole_active_retry(tmp_path):
    import copy
    from fixtures import make_vault
    from tutorlib import session, store
    root = make_vault(tmp_path)
    t = session.Tutor(store.Vault(root))
    t.start('lesson', focus=['9702-2.1'])
    q = {'id': 'draft-retry', 'kcs': ['9702-2.1.1'], 'kind': 'structured', 'difficulty': 2,
         'marks': 1, 'stem': 'Explain.', 'scheme': [{'mark': 'B1', 'point': 'Private scheme'}]}
    shown = t._present(q, 'practice', 'practice')
    t.answer(f"{shown['n']}?")
    ident, guard = next(iter(t.session['skipped_answer_guards'].items()))
    path = root / '.tutor/state/deferred-notes.json'
    draft = copy.deepcopy(guard)
    draft['question']['saved_work'] = 'Earlier work'
    deferred_notes.hold(path, ident, draft)
    deferred_notes.hold(path, ident, guard)
    retry = t.retry_skipped_ungraded()
    n = retry['items'][0]['n']
    assert t.retry_draft_history(n) == ['Earlier work']
    t.session['skipped_answer_guards'][ident]['key'] = 'different protected key'
    assert t.retry_draft_history(n) == []
    t.session['skipped_answer_guards'][ident]['key'] = deferred_notes.outstanding(path)[ident]['key']
    t.session['skipped_answer_guards']['another'] = {'key': 'Other secret'}
    assert t.retry_draft_history(n) == []
    t.session['skipped_answer_guards'].pop('another')
    t.session.setdefault('queue', {})['999'] = {'item': 'other'}
    assert t.retry_draft_history(n) == []


def test_cancel_draft_operation_is_atomic_idempotent_and_rejects_changed_guard(tmp_path):
    path = tmp_path / 'notes.json'
    original = {'key': 'A', 'kind': 'short', 'question': {'inst': {'id': 'q'}, 'saved_work': 'old'}}
    proposed = {'key': 'A', 'kind': 'short', 'question': {'inst': {'id': 'q'}, 'saved_work': 'new'}}
    deferred_notes.hold(path, 'q', original)
    revision = deferred_notes.guard_revision(path, 'q')
    assert deferred_notes.cancel_draft(path, 'operation-1', 'q', original, proposed, revision) == 'applied'
    assert deferred_notes.draft_history(path, 'q') == ['old']
    assert deferred_notes.outstanding(path)['q'] == proposed
    assert deferred_notes.cancel_draft(path, 'operation-1', 'q', original, proposed, revision) == 'already_applied'
    external = {'key': 'A', 'kind': 'short', 'question': {'inst': {'id': 'q'}, 'saved_work': 'external'}}
    deferred_notes.hold(path, 'q', external)
    assert deferred_notes.cancel_draft(path, 'operation-2', 'q', original, proposed, revision) == 'conflict'
    assert deferred_notes.outstanding(path)['q'] == external


def test_cancel_draft_rejects_replay_after_guard_resolution_and_recreation(tmp_path):
    path = tmp_path / 'notes.json'
    old = {'key': 'A', 'kind': 'short', 'question': {'inst': {'id': 'q'}, 'saved_work': 'old'}}
    new = {'key': 'A', 'kind': 'short', 'question': {'inst': {'id': 'q'}, 'saved_work': 'new'}}
    deferred_notes.hold(path, 'q', old)
    revision = deferred_notes.guard_revision(path, 'q')
    assert deferred_notes.cancel_draft(path, 'op', 'q', old, new, revision) == 'applied'
    deferred_notes.resolve(path, 'q')
    deferred_notes.hold(path, 'q', new)
    assert deferred_notes.cancel_draft(path, 'op', 'q', old, new, revision) == 'conflict'


def test_guard_snapshot_returns_guard_and_revision_from_same_store_read(tmp_path):
    path = tmp_path / 'notes.json'
    old = {'key': 'A', 'kind': 'short', 'question': {'inst': {'id': 'q'}, 'saved_work': 'old'}}
    new = {'key': 'A', 'kind': 'short', 'question': {'inst': {'id': 'q'}, 'saved_work': 'new'}}
    deferred_notes.hold(path, 'q', old)
    snapshot = deferred_notes.guard_snapshot(path, 'q')
    assert snapshot['guard'] == old
    deferred_notes.hold(path, 'q', new)
    deferred_notes.hold(path, 'q', old)
    assert deferred_notes.cancel_draft(path, 'op', 'q', snapshot['guard'], new, snapshot['revision']) == 'conflict'


def test_identical_hold_does_not_invalidate_committed_cancellation_replay(tmp_path):
    path = tmp_path / 'notes.json'
    old = {'key': 'A', 'kind': 'short', 'question': {'inst': {'id': 'q'}, 'saved_work': 'old'}}
    new = {'key': 'A', 'kind': 'short', 'question': {'inst': {'id': 'q'}, 'saved_work': 'new'}}
    deferred_notes.hold(path, 'q', old)
    snap = deferred_notes.guard_snapshot(path, 'q')
    assert deferred_notes.cancel_draft(path, 'op', 'q', old, new, snap['revision']) == 'applied'
    deferred_notes.hold(path, 'q', new)
    assert deferred_notes.cancel_draft(path, 'op', 'q', old, new, snap['revision']) == 'already_applied'


def test_cancel_draft_rejects_malformed_history_without_modifying_store(tmp_path):
    import json
    path = tmp_path / 'notes.json'
    old = {'key': 'A', 'kind': 'short', 'question': {'inst': {'id': 'q'}, 'saved_work': 'old'}}
    new = {'key': 'A', 'kind': 'short', 'question': {'inst': {'id': 'q'}, 'saved_work': 'new'}}
    deferred_notes.hold(path, 'q', old)
    snap = deferred_notes.guard_snapshot(path, 'q')
    data = json.loads(path.read_text())
    data['draft_history'] = {'q': [123]}
    path.write_text(json.dumps(data))
    before = path.read_bytes()
    with pytest.raises(ValueError):
        deferred_notes.cancel_draft(path, 'op', 'q', old, new, snap['revision'])
    assert path.read_bytes() == before


def test_draft_conflict_records_both_versions_without_changing_guard(tmp_path):
    path = tmp_path / 'notes.json'
    old = {'key': 'A', 'kind': 'short', 'question': {'inst': {'id': 'q'}, 'saved_work': 'old'}}
    local = {'key': 'A', 'kind': 'short', 'question': {'inst': {'id': 'q'}, 'saved_work': 'local'}}
    remote = {'key': 'A', 'kind': 'short', 'question': {'inst': {'id': 'q'}, 'saved_work': 'remote'}}
    deferred_notes.hold(path, 'q', old)
    generation = deferred_notes.guard_snapshot(path, 'q')['generation']
    deferred_notes.hold(path, 'q', remote)
    assert deferred_notes.record_draft_conflict(path, 'op', 'q', old, local, generation) == 'recorded'
    assert deferred_notes.record_draft_conflict(path, 'op', 'q', old, local, generation) == 'already_recorded'
    assert deferred_notes.outstanding(path)['q'] == remote
    conflict = deferred_notes.read_draft_conflict(path, 'op')
    assert conflict['local']['question']['saved_work'] == 'local'
    assert conflict['stored']['question']['saved_work'] == 'remote'


def test_draft_conflict_does_not_bind_a_recreated_guard(tmp_path):
    path = tmp_path / 'notes.json'
    old = {'key': 'A', 'kind': 'short', 'question': {'inst': {'id': 'q'}, 'saved_work': 'old'}}
    local = {'key': 'A', 'kind': 'short', 'question': {'inst': {'id': 'q'}, 'saved_work': 'local'}}
    deferred_notes.hold(path, 'q', old)
    snapshot = deferred_notes.guard_snapshot(path, 'q')
    deferred_notes.resolve(path, 'q')
    deferred_notes.hold(path, 'q', old)
    assert deferred_notes.record_draft_conflict(path, 'op', 'q', old, local, snapshot['generation']) == 'conflict'


def _skipped_mcq(tutor, ident='give-up', answer='A'):
    item = {'id': ident, 'kcs': ['9702-2.1.1'], 'kind': 'mcq', 'difficulty': 2, 'marks': 1,
            'stem': 'Which?', 'options': {'A': 'Secret', 'B': 'Other'}, 'answer': answer,
            'explanation': 'A is the key.'}
    shown = tutor._present(item, block='practice', phase='practice')
    tutor.answer(f"{shown['n']}?")
    return item


def _skipped_short(tutor, ident):
    item = {'id': ident, 'kcs': ['9702-2.1.1'], 'kind': 'short', 'difficulty': 2, 'marks': 1,
            'stem': 'Explain.', 'rubric': [{'point': ident, 'keywords': [[ident]]}],
            'explanation': f'{ident} is the key.'}
    shown = tutor._present(item, block='practice', phase='practice')
    tutor.answer(f"{shown['n']}?")
    return item


def test_idk_in_a_skipped_retry_gives_up_and_reveals_the_answer(tmp_path):
    from fixtures import make_vault
    from tutorlib import session, store
    tutor = session.Tutor(store.Vault(make_vault(tmp_path)))
    tutor.start('lesson', focus=['9702-2.1'])
    _skipped_mcq(tutor)
    n = tutor.retry_skipped()['items'][0]['n']
    result = tutor.answer(f'{n}?')['results'][0]
    assert not result.get('error')
    assert not result.get('answer_withheld')
    assert result['answer'] == 'A: Secret'
    assert result['explanation'] == 'A is the key.'
    assert not tutor.session['skipped_answer_guards']
    assert not tutor.session['presented']


def test_typed_idk_in_a_skipped_retry_gives_up_instead_of_asking_for_an_attempt(tmp_path):
    from fixtures import make_vault
    from tutorlib import session, store
    tutor = session.Tutor(store.Vault(make_vault(tmp_path)))
    tutor.start('lesson', focus=['9702-2.1'])
    _skipped_short(tutor, 'give-up-one')
    _skipped_short(tutor, 'give-up-two')
    n = tutor.retry_skipped()['items'][0]['n']
    result = tutor.answer(f'{n} = I have no idea')['results'][0]
    assert not result.get('error')
    assert not result.get('answer_withheld')
    assert result['answer'] == 'give-up-one'
    assert result['explanation'] == 'give-up-one is the key.'
    assert len(tutor.session['skipped_answer_guards']) == 1


def _event_bytes(vault):
    folder = vault.tutor / 'events'
    return {p.name: p.read_bytes() for p in sorted(folder.glob('*.jsonl'))}


def test_first_idk_still_withholds_the_answer(tmp_path):
    from fixtures import make_vault
    from tutorlib import session, store
    tutor = session.Tutor(store.Vault(make_vault(tmp_path)))
    tutor.start('lesson', focus=['9702-2.1'])
    item = {'id': 'first-skip', 'kcs': ['9702-2.1.1'], 'kind': 'mcq', 'difficulty': 2, 'marks': 1,
            'stem': 'Which?', 'options': {'A': 'Secret', 'B': 'Other'}, 'answer': 'A',
            'explanation': 'A is the key.'}
    shown = tutor._present(item, block='practice', phase='practice')
    result = tutor.answer(f"{shown['n']}?")['results'][0]
    assert result['answer_withheld'] and result['answer'] == '' and not result.get('explanation')
    assert tutor.session['skipped_answer_guards']


def test_a_real_attempt_in_the_retry_still_marks_and_resolves(tmp_path):
    from fixtures import make_vault
    from tutorlib import session, store
    tutor = session.Tutor(store.Vault(make_vault(tmp_path)))
    tutor.start('lesson', focus=['9702-2.1'])
    _skipped_mcq(tutor)
    n = tutor.retry_skipped()['items'][0]['n']
    result = tutor.answer(f'{n}A3')['results'][0]
    assert result['correct'] and not result.get('answer_withheld')
    assert not tutor.session['skipped_answer_guards']


def test_give_up_resolves_the_guard_and_the_deferred_hold(tmp_path):
    from fixtures import make_vault
    from tutorlib import session, store
    tutor = session.Tutor(store.Vault(make_vault(tmp_path)))
    tutor.start('lesson', focus=['9702-2.1'])
    _skipped_mcq(tutor, 'held-one')
    _skipped_mcq(tutor, 'held-two')
    path = tutor.vault.tutor / 'state' / 'deferred-notes.json'
    tutor._node_done({'kc': '9702-2.1.1', 'card': {'note': 'Secret note'}, 'mistakes': []})
    assert deferred_notes.outstanding(path)
    tutor.answer(f"{tutor.retry_skipped()['items'][0]['n']}?")
    assert len(tutor.session['skipped_answer_guards']) == 1 and deferred_notes.outstanding(path)
    tutor.answer(f"{tutor.retry_skipped()['items'][0]['n']}?")
    assert not tutor.session['skipped_answer_guards']
    assert deferred_notes.outstanding(path) == {}


def test_give_up_releases_feedback_held_for_another_question(tmp_path):
    from fixtures import make_vault
    from tutorlib import session, store
    tutor = session.Tutor(store.Vault(make_vault(tmp_path)))
    tutor.start('lesson', focus=['9702-2.1'])
    _skipped_mcq(tutor, 'held-guard')
    other = {'id': 'held-other', 'kcs': ['9702-2.1.1'], 'kind': 'mcq', 'difficulty': 2, 'marks': 1,
             'stem': 'Which?', 'options': {'A': 'One', 'B': 'Two'}, 'answer': 'A'}
    shown = tutor._present(other, block='practice', phase='practice')
    assert tutor.answer(f"{shown['n']}B")['results'][0].get('feedback_withheld')
    assert tutor.session['deferred_feedback']
    tutor.answer(f"{tutor.retry_skipped()['items'][0]['n']}?")
    assert not tutor.session['skipped_answer_guards']
    released = tutor.next()
    assert released['activity'] == 'explain' and released.get('part') == 'delayed_feedback'
    assert not tutor.session['deferred_feedback']


def test_give_up_leaves_the_other_guard_refusing_the_answer(tmp_path):
    from fixtures import make_vault
    from tutorlib import session, store
    tutor = session.Tutor(store.Vault(make_vault(tmp_path)))
    tutor.start('lesson', focus=['9702-2.1'])
    _skipped_short(tutor, 'keep-one')
    _skipped_short(tutor, 'keep-two')
    tutor.answer(f"{tutor.retry_skipped()['items'][0]['n']}?")
    assert len(tutor.session['skipped_answer_guards']) == 1
    other = {'id': 'keep-other', 'kcs': ['9702-2.1.1'], 'kind': 'mcq', 'difficulty': 2, 'marks': 1,
             'stem': 'Which?', 'options': {'A': 'One', 'B': 'Two'}, 'answer': 'A'}
    shown = tutor._present(other, block='practice', phase='practice')
    assert tutor.hint(shown['n']).get('refused')


def test_ungraded_unavailable_retry_gives_up_on_typed_idk(tmp_path):
    from fixtures import make_vault
    from tutorlib import session, store
    tutor = session.Tutor(store.Vault(make_vault(tmp_path)))
    tutor.start('lesson', focus=['9702-2.1'])
    item = {'id': 'ungraded-give-up', 'kcs': ['9702-2.1.1'], 'kind': 'short', 'difficulty': 2, 'marks': 1,
            'stem': 'Explain.', 'rubric': [{'point': 'A point', 'keywords': [['point']]}]}
    shown = tutor._present(item, block='practice', phase='practice')
    tutor.answer(f"{shown['n']}?")
    tutor.log({'type': 'topical_exclude', 'identity': item['id'], 'chapter': '9702-2.1', 'reason': 'test', 'missing': []})
    answered = tutor.session['answered']
    n = tutor.retry_skipped_ungraded()['items'][0]['n']
    result = tutor.answer(f'{n} = I have no idea')['results'][0]
    assert result.get('gave_up') and not result.get('error')
    assert tutor.session['answered'] == answered
    assert not tutor.session['skipped_answer_guards'] and not tutor.session['presented']
    assert not tutor.session.get('deferred_judgments')


def test_structured_ungraded_retry_gives_up_without_marking(tmp_path):
    from fixtures import make_vault
    from tutorlib import session, store
    tutor = session.Tutor(store.Vault(make_vault(tmp_path)))
    tutor.start('lesson', focus=['9702-2.1'])
    item = {'id': 'structured-give-up', 'kcs': ['9702-2.1.1'], 'kind': 'structured', 'difficulty': 2, 'marks': 2,
            'stem': 'Show your working.',
            'scheme': [{'mark': 'M1', 'point': 'method'}, {'mark': 'A1', 'point': 'answer'}]}
    shown = tutor._present(item, block='practice', phase='practice')
    tutor.answer(f"{shown['n']}?")
    tutor.log({'type': 'topical_exclude', 'identity': item['id'], 'chapter': '9702-2.1', 'reason': 'test', 'missing': []})
    n = tutor.retry_skipped_ungraded()['items'][0]['n']
    answers = len([e for e in tutor.vault.events() if e['type'] == 'answer'])
    result = tutor.save_ungraded_structured(n, "I don't know")
    assert result.get('ok') and result.get('gave_up')
    assert not tutor.session['skipped_answer_guards'] and not tutor.session['presented']
    assert not tutor.session.get('deferred_judgments')
    assert len([e for e in tutor.vault.events() if e['type'] == 'answer']) == answers


def test_give_up_appends_events_without_rewriting_earlier_ones(tmp_path):
    from fixtures import make_vault
    from tutorlib import session, store
    vault = store.Vault(make_vault(tmp_path))
    tutor = session.Tutor(vault)
    tutor.start('lesson', focus=['9702-2.1'])
    _skipped_mcq(tutor)
    before = _event_bytes(vault)
    tutor.answer(f"{tutor.retry_skipped()['items'][0]['n']}?")
    after = _event_bytes(vault)
    assert all(after[name].startswith(data) for name, data in before.items())
    assert sum(map(len, after.values())) > sum(map(len, before.values()))
