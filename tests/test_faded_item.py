import pytest

from tutorlib.faded import question_item


def test_legacy_faded_answer_kinds_are_preserved():
    numeric = {'id': 'n', 'problem': 'Calculate.', 'answer': {'value': 4, 'unit': ''}}
    expression = {'id': 'e', 'problem': 'Simplify.', 'answer': {'expr': 'x+1'}}
    assert question_item(numeric, 'K')['kind'] == 'numeric'
    assert question_item(expression, 'K')['kind'] == 'expression'
    assert question_item(numeric, 'K')['marks'] == 2


def test_written_faded_check_retains_rubric_and_model_answer():
    faded = {'id': 'w', 'kind': 'short', 'problem': 'Disprove the claim.',
             'review_answer': 'Eleven is allowed; 111 = 3 × 37.',
             'rubric': [{'point': 'Uses an admissible value', 'keywords': [['11']]},
                        {'point': 'Factors the output', 'keywords': [['3'], ['37']]}]}
    item = question_item(faded, 'K')
    assert item['kind'] == 'short'
    assert item['stem'] == faded['problem']
    assert item['review_answer'] == faded['review_answer']
    assert item['rubric'] == faded['rubric']
    assert item['marks'] == 2


@pytest.mark.parametrize('change', [
    {'kind': 'other'}, {'answer': {'value': 111}}, {'rubric': []}, {'review_answer': ''},
])
def test_written_faded_rejects_ambiguous_or_incomplete_shapes(change):
    faded = {'id': 'w', 'kind': 'short', 'problem': 'Disprove.', 'review_answer': 'Solution.',
             'rubric': [{'point': 'Reason', 'keywords': [['reason']]}]}
    faded.update(change)
    with pytest.raises(ValueError):
        question_item(faded, 'K')


def test_pack_validator_blocks_written_faded_until_all_release_paths_are_safe():
    import sys
    from pathlib import Path
    sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'build'))
    from build.validate_pack import validate
    faded = {'id': 'w', 'kind': 'short', 'problem': 'Disprove.', 'review_answer': 'Solution.',
             'rubric': [{'point': 'Reason', 'keywords': [['reason']]}]}
    pack = {'spec': 'X', 'subtopic': 'S', 'note': 'note.md', 'items': [],
            'worked': [{'id': 'we', 'kc': 'K', 'steps': [], 'faded': faded}]}
    graph = {'spec': 'X', 'kcs': [{'id': 'K', 'subtopic': 'S'}]}
    assert [e for e in validate(pack, graph, min_variants=0) if e['where'] == 'worked we.faded']
    faded['review_answer'] = ''
    assert [e for e in validate(pack, graph, min_variants=0) if e['where'] == 'worked we.faded']


def test_written_faded_public_question_and_skip_do_not_expose_solution(tmp_path):
    from fixtures import make_vault
    from tutorlib import session, store
    root = make_vault(tmp_path)
    tutor = session.Tutor(store.Vault(root))
    tutor.start('lesson', focus=['9702-2.1'])
    faded = {'id': 'we2f', 'kind': 'short', 'problem': 'Disprove.', 'review_answer': 'SECRET SOLUTION',
             'rubric': [{'point': 'SECRET POINT', 'keywords': [['secret']]}]}
    shown = tutor._present(question_item(faded, '9702-2.1.1'), block='node', phase='faded')
    assert 'SECRET' not in str(shown)
    result = tutor.answer(f"{shown['n']}?")
    assert 'SECRET' not in str(result)
    tutor = session.Tutor(store.Vault(root))
    retry = tutor.retry_skipped()
    assert retry['items'][0]['stem'] == 'Disprove.'
    assert 'SECRET' not in str(retry)


def test_skipped_written_faded_in_learn_mode_remains_guarded_after_restart(tmp_path):
    from fixtures import make_vault
    from tutorlib import session, store
    root = make_vault(tmp_path)
    tutor = session.Tutor(store.Vault(root))
    tutor.start('learn', focus=['9702-2.1.1'])
    faded = {'id': 'we2f', 'kind': 'short', 'problem': 'Disprove.', 'review_answer': 'SECRET SOLUTION',
             'rubric': [{'point': 'SECRET POINT', 'keywords': [['secret']]}]}
    shown = tutor._present(question_item(faded, '9702-2.1.1'), block='learn', phase='faded')
    result = tutor.answer(f"{shown['n']}?", judge={shown['n']: 1})
    assert 'SECRET' not in str(result)
    assert tutor.session['skipped_answer_guards']
    event = list(tutor.vault.events())[-1]
    assert not event['grade']['correct']
    assert 'SECRET' not in str(event)
    assert 'SECRET' not in (root / 'Now.md').read_text()
    tutor = session.Tutor(store.Vault(root))
    retry = tutor.retry_skipped()
    assert retry['items'][0]['stem'] == 'Disprove.'
    assert 'SECRET' not in str(retry)


@pytest.mark.parametrize('response', ["I don't know", 'I do not know', 'not sure', 'skip',
                                      'I have no clue', 'I am unsure', 'I cannot answer'])
def test_plain_language_nonattempt_keeps_written_faded_answer_private(tmp_path, response):
    from fixtures import make_vault
    from tutorlib import session, store
    tutor = session.Tutor(store.Vault(make_vault(tmp_path)))
    tutor.start('learn', focus=['9702-2.1.1'])
    faded = {'id': 'we2f', 'kind': 'short', 'problem': 'Disprove.', 'review_answer': 'SECRET SOLUTION',
             'rubric': [{'point': 'SECRET POINT', 'keywords': [['secret']]}]}
    shown = tutor._present(question_item(faded, '9702-2.1.1'), block='learn', phase='faded')
    result = tutor.answer(f"{shown['n']} = {response}")
    assert 'SECRET' not in str(result)
    assert not result['results'][0].get('pending_judgement')
    assert tutor.session['skipped_answer_guards']


def test_no_can_be_a_written_answer_not_a_skip(tmp_path):
    from fixtures import make_vault
    from tutorlib import session, store
    tutor = session.Tutor(store.Vault(make_vault(tmp_path)))
    tutor.start('learn', focus=['9702-2.1.1'])
    faded = {'id': 'f', 'kind': 'short', 'problem': 'Is the claim true?', 'review_answer': 'No.',
             'rubric': [{'point': 'No', 'keywords': [['no']]}]}
    shown = tutor._present(question_item(faded, '9702-2.1.1'), block='learn', phase='faded')
    result = tutor.answer(f"{shown['n']} = no")['results'][0]
    assert result.get('attempt_confirmation_required')
    assert tutor.session['presented'][str(shown['n'])]['saved_work'] == 'no'


def test_unconfirmed_written_faded_answer_withholds_rubric(tmp_path):
    from fixtures import make_vault
    from tutorlib import session, store
    tutor = session.Tutor(store.Vault(make_vault(tmp_path)))
    tutor.start('learn', focus=['9702-2.1.1'])
    faded = {'id': 'f', 'kind': 'short', 'problem': 'Disprove.', 'review_answer': 'SECRET SOLUTION',
             'rubric': [{'point': 'SECRET POINT', 'keywords': [['reason']]}]}
    shown = tutor._present(question_item(faded, '9702-2.1.1'), block='learn', phase='faded')
    result = tutor.answer(f"{shown['n']} = I have no idea what to do here")
    assert 'SECRET' not in str(result)
    assert result['results'][0].get('attempt_confirmation_required')
    assert str(shown['n']) in tutor.session['presented']


def test_explicit_confirmation_binds_exact_saved_faded_work(tmp_path):
    from fixtures import make_vault
    from tutorlib import session, store
    tutor = session.Tutor(store.Vault(make_vault(tmp_path)))
    tutor.start('learn', focus=['9702-2.1.1'])
    faded = {'id': 'f', 'kind': 'short', 'problem': 'Disprove.', 'review_answer': 'Solution',
             'rubric': [{'point': 'Reason', 'keywords': [['reason']]}]}
    shown = tutor._present(question_item(faded, '9702-2.1.1'), block='learn', phase='faded')
    n = shown['n']
    assert tutor.answer(f'{n} = a reason')['results'][0]['attempt_confirmation_required']
    assert not tutor.confirm_faded_attempt(n, 'different work')['ok']
    assert tutor.confirm_faded_attempt(n, 'a reason')['ok']
    assert tutor.answer(f'{n} = a reason')['results'][0]['pending_judgement']


def test_faded_confirmation_does_not_survive_new_durable_guard(tmp_path):
    from fixtures import make_vault
    from tutorlib import deferred_notes, session, store
    tutor = session.Tutor(store.Vault(make_vault(tmp_path)))
    tutor.start('learn', focus=['9702-2.1.1'])
    faded = {'id': 'f', 'kind': 'short', 'problem': 'Disprove.', 'review_answer': 'SECRET SOLUTION',
             'rubric': [{'point': 'SECRET POINT', 'keywords': [['reason']]}]}
    n = tutor._present(question_item(faded, '9702-2.1.1'), block='learn', phase='faded')['n']
    tutor.answer(f'{n} = a reason')
    assert tutor.confirm_faded_attempt(n, 'a reason')['ok']
    deferred_notes.hold(tutor.vault.tutor / 'state' / 'deferred-notes.json', 'other',
                        {'key': 'SECRET POINT', 'kind': 'short', 'question': {'inst': {'id': 'other'}}})
    result = tutor.answer(f'{n} = a reason')
    assert 'SECRET' not in str(result)
    assert not result['results'][0].get('pending_judgement')


def test_skipped_written_faded_retry_cannot_bypass_attempt_confirmation(tmp_path):
    from fixtures import make_vault
    from tutorlib import session, store
    tutor = session.Tutor(store.Vault(make_vault(tmp_path)))
    tutor.start('learn', focus=['9702-2.1.1'])
    f = {'id': 'f', 'kind': 'short', 'problem': 'Disprove.', 'review_answer': 'SECRET SOLUTION',
         'rubric': [{'point': 'SECRET POINT', 'keywords': [['reason']]}]}
    n = tutor._present(question_item(f, '9702-2.1.1'), block='learn', phase='faded')['n']
    tutor.answer(f'{n}?')
    retry = tutor.retry_skipped()['items'][0]['n']
    result = tutor.answer(f'{retry} = I have no idea at all')
    assert 'SECRET' not in str(result)
    assert not result['results'][0].get('pending_judgement')


def test_written_faded_confirmation_blocks_other_open_question(tmp_path):
    from fixtures import make_vault
    from tutorlib import session, store
    tutor = session.Tutor(store.Vault(make_vault(tmp_path)))
    tutor.start('learn', focus=['9702-2.1.1'])
    f = {'id': 'f', 'kind': 'short', 'problem': 'Explain.', 'review_answer': 'SECRET',
         'rubric': [{'point': 'SECRET POINT', 'keywords': [['reason']]}]}
    n = tutor._present(question_item(f, '9702-2.1.1'), block='learn', phase='faded')['n']
    tutor.answer(f'{n} = a reason')
    assert tutor.confirm_faded_attempt(n, 'a reason')['ok']
    other = {'id': 'other', 'kcs': ['9702-2.1.1'], 'kind': 'mcq', 'difficulty': 2, 'marks': 1,
             'stem': 'Which?', 'options': {'A': 'SECRET', 'B': 'Other'}, 'answer': 'A'}
    tutor._present(other, block='practice', phase='practice')
    assert not tutor.confirm_faded_attempt(n, 'a reason')['ok']
    result = tutor.answer(f'{n} = a reason')
    assert 'SECRET' not in str(result)
    assert not result['results'][0].get('pending_judgement')


def test_written_faded_retry_can_be_confirmed_and_marked(tmp_path):
    from fixtures import make_vault
    from tutorlib import session, store
    tutor = session.Tutor(store.Vault(make_vault(tmp_path)))
    tutor.start('learn', focus=['9702-2.1.1'])
    f = {'id': 'f', 'kind': 'short', 'problem': 'Disprove.', 'review_answer': 'Solution',
         'rubric': [{'point': 'Reason', 'keywords': [['reason']]}]}
    n = tutor._present(question_item(f, '9702-2.1.1'), block='learn', phase='faded')['n']
    tutor.answer(f'{n}?')
    retry = tutor.retry_skipped()['items'][0]['n']
    tutor.answer(f'{retry} = a reason')
    assert tutor.confirm_faded_attempt(retry, 'a reason')['ok']
    assert tutor.answer(f'{retry} = a reason')['results'][0]['pending_judgement']
    tutor.answer(f'{retry} = a reason', judge={retry: 1})
    assert not tutor.session['skipped_answer_guards']


def test_written_faded_retry_with_other_guard_can_save_attempt_without_revealing_answers(tmp_path):
    from fixtures import make_vault
    from tutorlib import session, store
    tutor = session.Tutor(store.Vault(make_vault(tmp_path)))
    tutor.start('learn', focus=['9702-2.1.1'])
    f = {'id': 'f', 'kind': 'short', 'problem': 'Explain.', 'review_answer': 'SECRET',
         'rubric': [{'point': 'SECRET POINT', 'keywords': [['reason']]}]}
    n = tutor._present(question_item(f, '9702-2.1.1'), block='learn', phase='faded')['n']
    tutor.answer(f'{n}?')
    other = {'id': 'other', 'kcs': ['9702-2.1.1'], 'kind': 'mcq', 'difficulty': 2, 'marks': 1,
             'stem': 'Which?', 'options': {'A': 'SECRET', 'B': 'Other'}, 'answer': 'A'}
    n2 = tutor._present(other, block='node', phase='form_check')['n']
    tutor.answer(f'{n2}?')
    retry = tutor.retry_skipped(guard_id=next(k for k,v in tutor.session['skipped_answer_guards'].items()
                                                if v['question']['item'] == 'f'))['items'][0]['n']
    tutor.answer(f'{retry} = a reason')
    assert tutor.confirm_faded_attempt(retry, 'a reason')['ok']
    result = tutor.answer(f'{retry} = a reason')
    assert 'SECRET' not in str(result)
    assert result['results'][0]['attempt_saved']


def test_unavailable_faded_retry_does_not_discard_saved_draft_on_skip(tmp_path):
    from fixtures import make_vault
    from tutorlib import session, store
    tutor = session.Tutor(store.Vault(make_vault(tmp_path)))
    tutor.start('learn', focus=['9702-2.1.1'])
    f = {'id': 'f', 'kind': 'short', 'problem': 'Explain.', 'review_answer': 'SECRET',
         'rubric': [{'point': 'Reason', 'keywords': [['reason']]}]}
    n = tutor._present(question_item(f, '9702-2.1.1'), block='learn', phase='faded')['n']
    tutor.answer(f'{n}?')
    retry = tutor.retry_skipped()['items'][0]['n']
    tutor.session['presented'][str(retry)]['ungraded_unavailable'] = True
    tutor.answer(f'{retry} = my working')
    assert tutor.answer(f'{retry}?')['results'][0]['retry_cancelled']
    assert next(iter(tutor.session['skipped_answer_guards'].values()))['question']['saved_work'] == 'my working'


def test_confirmed_no_in_written_faded_retry_can_be_deferred(tmp_path):
    from fixtures import make_vault
    from tutorlib import session, store
    tutor = session.Tutor(store.Vault(make_vault(tmp_path)))
    tutor.start('learn', focus=['9702-2.1.1'])
    f = {'id': 'f', 'kind': 'short', 'problem': 'Is the claim true?', 'review_answer': 'No.',
         'rubric': [{'point': 'No', 'keywords': [['no']]}]}
    n = tutor._present(question_item(f, '9702-2.1.1'), block='learn', phase='faded')['n']
    tutor.answer(f'{n}?')
    other = {'id': 'other', 'kcs': ['9702-2.1.1'], 'kind': 'mcq', 'difficulty': 2, 'marks': 1,
             'stem': 'Which?', 'options': {'A': 'SECRET', 'B': 'Other'}, 'answer': 'A'}
    n2 = tutor._present(other, block='node', phase='form_check')['n']
    tutor.answer(f'{n2}?')
    retry = tutor.retry_skipped(guard_id=next(k for k,v in tutor.session['skipped_answer_guards'].items()
                                                if v['question']['item'] == 'f'))['items'][0]['n']
    tutor.answer(f'{retry} = no')
    assert tutor.confirm_faded_attempt(retry, 'no')['ok']
    assert tutor.answer(f'{retry} = no')['results'][0]['attempt_saved']


def test_unavailable_faded_retry_can_skip_without_losing_draft(tmp_path):
    from fixtures import make_vault
    from tutorlib import session, store
    root = make_vault(tmp_path)
    tutor = session.Tutor(store.Vault(root))
    tutor.start('learn', focus=['9702-2.1.1'])
    f = {'id': 'f', 'kind': 'short', 'problem': 'Explain.', 'review_answer': 'SECRET',
         'rubric': [{'point': 'Reason', 'keywords': [['reason']]}]}
    n = tutor._present(question_item(f, '9702-2.1.1'), block='learn', phase='faded')['n']
    tutor.answer(f'{n}?')
    retry = tutor.retry_skipped()['items'][0]['n']
    tutor.session['presented'][str(retry)]['ungraded_unavailable'] = True
    tutor.answer(f'{retry} = I have no idea at all')
    result = tutor.answer(f'{retry}?')
    assert result['results'][0].get('retry_cancelled')
    tutor = session.Tutor(store.Vault(root))
    guard = next(iter(tutor.session['skipped_answer_guards'].values()))
    assert guard['question']['saved_work'] == 'I have no idea at all'


def test_failed_faded_cancellation_survives_exclusion_and_restart(tmp_path, monkeypatch):
    from fixtures import make_vault
    from tutorlib import deferred_notes, session, store
    root = make_vault(tmp_path)
    tutor = session.Tutor(store.Vault(root))
    tutor.start('learn', focus=['9702-2.1.1'])
    f = {'id': 'f', 'kind': 'short', 'problem': 'Explain.', 'review_answer': 'SECRET',
         'rubric': [{'point': 'Reason', 'keywords': [['reason']]}]}
    n = tutor._present(question_item(f, '9702-2.1.1'), block='learn', phase='faded')['n']
    tutor.answer(f'{n}?')
    retry = tutor.retry_skipped()['items'][0]['n']
    tutor.session['presented'][str(retry)]['ungraded_unavailable'] = True
    tutor.answer(f'{retry} = my saved working')
    tutor.log({'type': 'topical_exclude', 'identity': 'f', 'chapter': '9702-2.1', 'reason': 'test', 'missing': []})
    real = deferred_notes.cancel_draft
    monkeypatch.setattr(deferred_notes, 'cancel_draft', lambda *args: (_ for _ in ()).throw(OSError('offline')))
    assert tutor.answer(f'{retry}?')['results'][0]['error']
    monkeypatch.setattr(session.topicals, 'eligibility', lambda *args: {'status': 'unavailable', 'missing': ['9702-2.2']})
    assert tutor.check_solvable(retry)['status'] == 'unverified'
    assert str(retry) in tutor.session['presented']
    restarted = session.Tutor(store.Vault(root))
    assert str(retry) in restarted.session['presented']
    assert restarted.session['presented'][str(retry)]['saved_work'] == 'my saved working'
    monkeypatch.setattr(deferred_notes, 'cancel_draft', real)
    recovered = session.Tutor(store.Vault(root))
    assert not recovered.session.get('faded_cancel_intent')
    assert next(iter(recovered.session['skipped_answer_guards'].values()))['question']['saved_work'] == 'my saved working'


def test_transient_faded_cancellation_failure_can_retry_without_restart(tmp_path, monkeypatch):
    from fixtures import make_vault
    from tutorlib import deferred_notes, session, store
    tutor = session.Tutor(store.Vault(make_vault(tmp_path)))
    tutor.start('learn', focus=['9702-2.1.1'])
    f = {'id': 'f', 'kind': 'short', 'problem': 'Explain.', 'review_answer': 'SECRET',
         'rubric': [{'point': 'Reason', 'keywords': [['reason']]}]}
    n = tutor._present(question_item(f, '9702-2.1.1'), block='learn', phase='faded')['n']
    tutor.answer(f'{n}?')
    retry = tutor.retry_skipped()['items'][0]['n']
    tutor.session['presented'][str(retry)]['ungraded_unavailable'] = True
    tutor.answer(f'{retry} = my working')
    real = deferred_notes.cancel_draft
    monkeypatch.setattr(deferred_notes, 'cancel_draft', lambda *args: (_ for _ in ()).throw(OSError('offline')))
    assert tutor.answer(f'{retry}?')['results'][0]['error']
    monkeypatch.setattr(deferred_notes, 'cancel_draft', real)
    assert tutor.retry_faded_cancellation()['ok']
    assert not tutor.session.get('faded_cancel_intent')
    assert next(iter(tutor.session['skipped_answer_guards'].values()))['question']['saved_work'] == 'my working'


def test_cancellation_recovery_does_not_overwrite_changed_guard_metadata(tmp_path, monkeypatch):
    from fixtures import make_vault
    from tutorlib import deferred_notes, session, store
    tutor = session.Tutor(store.Vault(make_vault(tmp_path)))
    tutor.start('learn', focus=['9702-2.1.1'])
    f = {'id': 'f', 'kind': 'short', 'problem': 'Explain.', 'review_answer': 'SECRET',
         'rubric': [{'point': 'Reason', 'keywords': [['reason']]}]}
    n = tutor._present(question_item(f, '9702-2.1.1'), block='learn', phase='faded')['n']
    tutor.answer(f'{n}?')
    retry = tutor.retry_skipped()['items'][0]['n']
    tutor.session['presented'][str(retry)]['ungraded_unavailable'] = True
    tutor.answer(f'{retry} = my working')
    real = deferred_notes.cancel_draft
    monkeypatch.setattr(deferred_notes, 'cancel_draft', lambda *args: (_ for _ in ()).throw(OSError('offline')))
    tutor.answer(f'{retry}?')
    guard = next(iter(tutor.session['skipped_answer_guards'].values()))
    guard['key'] = 'different protected answer'
    monkeypatch.setattr(deferred_notes, 'cancel_draft', real)
    assert not tutor.retry_faded_cancellation()['ok']
    assert guard['key'] == 'different protected answer'
    assert str(retry) in tutor.session['presented']


def test_cancellation_refuses_mismatched_guard_metadata_before_recording_intent(tmp_path):
    from fixtures import make_vault
    from tutorlib import session, store
    tutor = session.Tutor(store.Vault(make_vault(tmp_path)))
    tutor.start('learn', focus=['9702-2.1.1'])
    f = {'id': 'f', 'kind': 'short', 'problem': 'Explain.', 'review_answer': 'SECRET',
         'rubric': [{'point': 'Reason', 'keywords': [['reason']]}]}
    n = tutor._present(question_item(f, '9702-2.1.1'), block='learn', phase='faded')['n']
    tutor.answer(f'{n}?')
    retry = tutor.retry_skipped()['items'][0]['n']
    tutor.session['presented'][str(retry)]['ungraded_unavailable'] = True
    tutor.answer(f'{retry} = my working')
    guard = next(iter(tutor.session['skipped_answer_guards'].values()))
    guard['key'] = 'different protected answer'
    result = tutor.answer(f'{retry}?')
    assert result['results'][0]['error']
    assert not tutor.session.get('faded_cancel_intent')
    assert guard['key'] == 'different protected answer'
    assert tutor.session['presented'][str(retry)]['saved_work'] == 'my working'


def test_faded_cancellation_archives_competing_draft_without_resolving_guard(tmp_path, monkeypatch):
    from fixtures import make_vault
    from tutorlib import deferred_notes, session, store
    tutor = session.Tutor(store.Vault(make_vault(tmp_path)))
    tutor.start('learn', focus=['9702-2.1.1'])
    f = {'id': 'f', 'kind': 'short', 'problem': 'Explain.', 'review_answer': 'SECRET',
         'rubric': [{'point': 'Reason', 'keywords': [['reason']]}]}
    n = tutor._present(question_item(f, '9702-2.1.1'), block='learn', phase='faded')['n']
    tutor.answer(f'{n}?')
    retry = tutor.retry_skipped()['items'][0]['n']
    tutor.session['presented'][str(retry)]['ungraded_unavailable'] = True
    tutor.answer(f'{retry} = local draft')
    real = deferred_notes.cancel_draft
    def competing(path, operation, ident, expected, proposed, revision):
        import copy
        other = copy.deepcopy(expected)
        other['question']['saved_work'] = 'other draft'
        deferred_notes.hold(path, ident, other)
        return real(path, operation, ident, expected, proposed, revision)
    monkeypatch.setattr(deferred_notes, 'cancel_draft', competing)
    assert tutor.answer(f'{retry}?')['results'][0]['error']
    op = tutor.session['faded_cancel_intent']['operation']
    record = deferred_notes.read_draft_conflict(tutor.vault.tutor / 'state' / 'deferred-notes.json', op)
    assert record['local']['question']['saved_work'] == 'local draft'
    assert record['stored']['question']['saved_work'] == 'other draft'
    assert str(retry) in tutor.session['presented']


def test_faded_cancellation_does_not_overwrite_third_session_draft(tmp_path):
    from fixtures import make_vault
    from tutorlib import session, store
    tutor = session.Tutor(store.Vault(make_vault(tmp_path)))
    tutor.start('learn', focus=['9702-2.1.1'])
    f = {'id': 'f', 'kind': 'short', 'problem': 'Explain.', 'review_answer': 'SECRET',
         'rubric': [{'point': 'Reason', 'keywords': [['reason']]}]}
    n = tutor._present(question_item(f, '9702-2.1.1'), block='learn', phase='faded')['n']
    tutor.answer(f'{n}?')
    retry = tutor.retry_skipped()['items'][0]['n']
    tutor.session['presented'][str(retry)]['ungraded_unavailable'] = True
    tutor.answer(f'{retry} = local draft')
    guard = next(iter(tutor.session['skipped_answer_guards'].values()))
    guard['question']['saved_work'] = 'another session draft'
    result = tutor.answer(f'{retry}?')['results'][0]
    assert result.get('error')
    assert guard['question']['saved_work'] == 'another session draft'
    assert tutor.session['presented'][str(retry)]['saved_work'] == 'local draft'


def test_recovery_preserves_session_draft_changed_after_intent(tmp_path, monkeypatch):
    from fixtures import make_vault
    from tutorlib import deferred_notes, session, store
    tutor = session.Tutor(store.Vault(make_vault(tmp_path)))
    tutor.start('learn', focus=['9702-2.1.1'])
    f = {'id': 'f', 'kind': 'short', 'problem': 'Explain.', 'review_answer': 'SECRET',
         'rubric': [{'point': 'Reason', 'keywords': [['reason']]}]}
    n = tutor._present(question_item(f, '9702-2.1.1'), block='learn', phase='faded')['n']
    tutor.answer(f'{n}?')
    retry = tutor.retry_skipped()['items'][0]['n']
    tutor.session['presented'][str(retry)]['ungraded_unavailable'] = True
    tutor.answer(f'{retry} = local draft')
    real = deferred_notes.cancel_draft
    monkeypatch.setattr(deferred_notes, 'cancel_draft', lambda *args: (_ for _ in ()).throw(OSError('offline')))
    tutor.answer(f'{retry}?')
    guard = next(iter(tutor.session['skipped_answer_guards'].values()))
    guard['question']['saved_work'] = 'another draft'
    monkeypatch.setattr(deferred_notes, 'cancel_draft', real)
    assert not tutor.retry_faded_cancellation()['ok']
    assert guard['question']['saved_work'] == 'another draft'
    assert tutor.session['presented'][str(retry)]['saved_work'] == 'local draft'


def test_conflict_drafts_are_available_only_when_no_other_work_is_protected(tmp_path, monkeypatch):
    from fixtures import make_vault
    from tutorlib import deferred_notes, session, store
    tutor = session.Tutor(store.Vault(make_vault(tmp_path)))
    tutor.start('learn', focus=['9702-2.1.1'])
    f = {'id': 'f', 'kind': 'short', 'problem': 'Explain.', 'review_answer': 'SECRET',
         'rubric': [{'point': 'Reason', 'keywords': [['reason']]}]}
    n = tutor._present(question_item(f, '9702-2.1.1'), block='learn', phase='faded')['n']
    tutor.answer(f'{n}?')
    retry = tutor.retry_skipped()['items'][0]['n']
    tutor.session['presented'][str(retry)]['ungraded_unavailable'] = True
    tutor.answer(f'{retry} = local draft')
    real = deferred_notes.cancel_draft
    def competing(path, operation, ident, expected, proposed, revision):
        import copy
        other = copy.deepcopy(expected)
        other['question']['saved_work'] = 'other draft'
        deferred_notes.hold(path, ident, other)
        return real(path, operation, ident, expected, proposed, revision)
    monkeypatch.setattr(deferred_notes, 'cancel_draft', competing)
    tutor.answer(f'{retry}?')
    drafts = tutor.faded_conflict_drafts()
    assert drafts['local'] == 'local draft' and drafts['stored'] == 'other draft'
    guard = next(iter(tutor.session['skipped_answer_guards'].values()))
    old_guard = __import__('copy').deepcopy(guard)
    guard['key'] = 'a different protected answer'
    assert tutor.faded_conflict_drafts() is None
    guard.clear()
    guard.update(old_guard)
    deferred_notes.hold(tutor.vault.tutor / 'state' / 'deferred-notes.json', 'other',
                        {'key': 'SECRET', 'kind': 'mcq', 'question': {'inst': {'id': 'other'}}})
    assert tutor.faded_conflict_drafts() is None
    deferred_notes.resolve(tutor.vault.tutor / 'state' / 'deferred-notes.json', 'other')
    tutor.session.setdefault('queue', {})['extra'] = {'item': 'other'}
    assert tutor.faded_conflict_drafts() is None


@pytest.mark.parametrize('choice,expected', [('local', 'local draft'), ('stored', 'other draft')])
def test_faded_conflict_choice_preserves_archive_and_selected_draft(tmp_path, monkeypatch, choice, expected):
    import copy
    from fixtures import make_vault
    from tutorlib import deferred_notes, session, store
    tutor = session.Tutor(store.Vault(make_vault(tmp_path)))
    tutor.start('learn', focus=['9702-2.1.1'])
    f = {'id': 'f', 'kind': 'short', 'problem': 'Explain.', 'review_answer': 'SECRET',
         'rubric': [{'point': 'Reason', 'keywords': [['reason']]}]}
    n = tutor._present(question_item(f, '9702-2.1.1'), block='learn', phase='faded')['n']
    tutor.answer(f'{n}?')
    retry = tutor.retry_skipped()['items'][0]['n']
    tutor.session['presented'][str(retry)]['ungraded_unavailable'] = True
    tutor.answer(f'{retry} = local draft')
    real = deferred_notes.cancel_draft
    def competing(path, operation, ident, old, proposed, revision):
        other = copy.deepcopy(old)
        other['question']['saved_work'] = 'other draft'
        deferred_notes.hold(path, ident, other)
        return real(path, operation, ident, old, proposed, revision)
    monkeypatch.setattr(deferred_notes, 'cancel_draft', competing)
    tutor.answer(f'{retry}?')
    original_op = tutor.session['faded_cancel_intent']['operation']
    monkeypatch.setattr(deferred_notes, 'cancel_draft', real)
    assert not tutor.choose_faded_conflict_draft(choice, 'stale-operation')['ok']
    assert tutor.choose_faded_conflict_draft(choice, original_op)['ok']
    assert not tutor.session.get('faded_cancel_intent')
    assert next(iter(tutor.session['skipped_answer_guards'].values()))['question']['saved_work'] == expected
    archive = deferred_notes.read_draft_conflict(tutor.vault.tutor / 'state' / 'deferred-notes.json', original_op)
    assert archive['local']['question']['saved_work'] == 'local draft'
    assert archive['stored']['question']['saved_work'] == 'other draft'
    assert {'local draft', 'other draft'} <= set(next(iter(tutor.retained_drafts().values())))


def test_faded_conflict_choice_replays_after_store_write_interruption(tmp_path, monkeypatch):
    import copy
    from fixtures import make_vault
    from tutorlib import deferred_notes, session, store
    root = make_vault(tmp_path)
    tutor = session.Tutor(store.Vault(root))
    tutor.start('learn', focus=['9702-2.1.1'])
    f = {'id': 'f', 'kind': 'short', 'problem': 'Explain.', 'review_answer': 'SECRET',
         'rubric': [{'point': 'Reason', 'keywords': [['reason']]}]}
    n = tutor._present(question_item(f, '9702-2.1.1'), block='learn', phase='faded')['n']
    tutor.answer(f'{n}?')
    retry = tutor.retry_skipped()['items'][0]['n']
    tutor.session['presented'][str(retry)]['ungraded_unavailable'] = True
    tutor.answer(f'{retry} = local draft')
    real = deferred_notes.cancel_draft
    def competing(path, operation, ident, old, proposed, revision):
        other = copy.deepcopy(old)
        other['question']['saved_work'] = 'other draft'
        deferred_notes.hold(path, ident, other)
        return real(path, operation, ident, old, proposed, revision)
    monkeypatch.setattr(deferred_notes, 'cancel_draft', competing)
    tutor.answer(f'{retry}?')
    def interrupted(*args):
        assert real(*args) == 'applied'
        raise OSError('interrupted after store write')
    monkeypatch.setattr(deferred_notes, 'cancel_draft', interrupted)
    op = tutor.session['faded_cancel_intent']['operation']
    assert not tutor.choose_faded_conflict_draft('local', op)['ok']
    monkeypatch.setattr(deferred_notes, 'cancel_draft', real)
    recovered = session.Tutor(store.Vault(root))
    assert not recovered.session.get('faded_cancel_intent')
    assert next(iter(recovered.session['skipped_answer_guards'].values()))['question']['saved_work'] == 'local draft'
    assert {'local draft', 'other draft'} <= set(next(iter(recovered.retained_drafts().values())))


def test_faded_conflict_refreshes_after_later_store_edit(tmp_path, monkeypatch):
    import copy
    from fixtures import make_vault
    from tutorlib import deferred_notes, session, store
    tutor = session.Tutor(store.Vault(make_vault(tmp_path)))
    tutor.start('learn', focus=['9702-2.1.1'])
    f = {'id': 'f', 'kind': 'short', 'problem': 'Explain.', 'review_answer': 'SECRET',
         'rubric': [{'point': 'Reason', 'keywords': [['reason']]}]}
    n = tutor._present(question_item(f, '9702-2.1.1'), block='learn', phase='faded')['n']
    tutor.answer(f'{n}?')
    retry = tutor.retry_skipped()['items'][0]['n']
    tutor.session['presented'][str(retry)]['ungraded_unavailable'] = True
    tutor.answer(f'{retry} = local draft')
    real = deferred_notes.cancel_draft
    def competing(path, operation, ident, old, proposed, revision):
        other = copy.deepcopy(old)
        other['question']['saved_work'] = 'other draft'
        deferred_notes.hold(path, ident, other)
        return real(path, operation, ident, old, proposed, revision)
    monkeypatch.setattr(deferred_notes, 'cancel_draft', competing)
    tutor.answer(f'{retry}?')
    op = tutor.session['faded_cancel_intent']
    original_op, ident = op['operation'], op['ident']
    path = tutor.vault.tutor / 'state' / 'deferred-notes.json'
    latest = copy.deepcopy(deferred_notes.guard_snapshot(path, ident)['guard'])
    latest['question']['saved_work'] = 'latest draft'
    deferred_notes.hold(path, ident, latest)
    monkeypatch.setattr(deferred_notes, 'cancel_draft', real)
    assert not tutor.retry_faded_cancellation()['ok']
    assert tutor.session['faded_cancel_intent']['operation'] != original_op
    assert tutor.faded_conflict_drafts() == {'local': 'local draft', 'stored': 'latest draft'}
    assert not tutor.choose_faded_conflict_draft('local', original_op)['ok']
    assert tutor.choose_faded_conflict_draft('local', tutor.session['faded_cancel_intent']['operation'])['ok']
    assert {'local draft', 'other draft', 'latest draft'} <= set(next(iter(tutor.retained_drafts().values())))


def test_faded_recovery_does_not_overwrite_write_after_commit(tmp_path, monkeypatch):
    import copy
    from fixtures import make_vault
    from tutorlib import deferred_notes, session, store
    root = make_vault(tmp_path)
    tutor = session.Tutor(store.Vault(root))
    tutor.start('learn', focus=['9702-2.1.1'])
    f = {'id': 'f', 'kind': 'short', 'problem': 'Explain.', 'review_answer': 'SECRET',
         'rubric': [{'point': 'Reason', 'keywords': [['reason']]}]}
    n = tutor._present(question_item(f, '9702-2.1.1'), block='learn', phase='faded')['n']
    tutor.answer(f'{n}?')
    retry = tutor.retry_skipped()['items'][0]['n']
    tutor.session['presented'][str(retry)]['ungraded_unavailable'] = True
    tutor.answer(f'{retry} = local draft')
    real = deferred_notes.cancel_draft
    def competing_after_commit(path, operation, ident, old, proposed, revision):
        status = real(path, operation, ident, old, proposed, revision)
        if status == 'applied':
            newer = copy.deepcopy(proposed)
            newer['question']['saved_work'] = 'newer draft'
            deferred_notes.hold(path, ident, newer)
        return status
    monkeypatch.setattr(deferred_notes, 'cancel_draft', competing_after_commit)
    tutor.answer(f'{retry}?')
    ident = next(iter(tutor.session['skipped_answer_guards']))
    monkeypatch.setattr(deferred_notes, 'cancel_draft', real)
    recovered = session.Tutor(store.Vault(root))
    path = tutor.vault.tutor / 'state' / 'deferred-notes.json'
    assert deferred_notes.guard_snapshot(path, ident)['guard']['question']['saved_work'] == 'newer draft'
    assert recovered.retry_skipped()['activity'] == 'error'
    assert recovered.retry_skipped_ungraded()['activity'] == 'error'
