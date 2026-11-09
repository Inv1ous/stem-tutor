"""Manual awards are capabilities for one real attempt and verified private rubric."""
import copy
import json

import pytest

from fixtures import make_vault
from test_whole_rubric import whole
from tutorlib import deferred_notes, session, store


@pytest.fixture
def opened(tmp_path):
    tutor = session.Tutor(store.Vault(make_vault(tmp_path)))
    tutor.start('review', minutes=10)
    item = {**whole(), 'id': 'whole-q', 'stem': 'Draw the graph.', 'difficulty': 3, 'kcs': ['9702-2.1.1']}
    view = tutor._present(item, block='practice', phase=None)
    return tutor, view['n']


def answers(t):
    return [e for e in t.vault.events() if e['type'] == 'answer']


def disclose(t, n, work='My graph rises from the origin.', **kwargs):
    helper = getattr(t, 'whole_rubric', None)
    assert callable(helper), 'missing attempt-gated whole-rubric disclosure'
    return helper(n, work, **kwargs)


def award(t, n, ticket, earned=1, work='My graph rises from the origin.'):
    return t.answer(f'{n} = {work}', manual_awards={n: {'earned_marks': earned, 'ticket': ticket}})


def test_whole_view_and_scheme_hide_rubric_before_real_attempt(opened):
    t, n = opened
    view = t._view(n)
    assert view.get('manual_marking') is True
    assert not any(k in view for k in ('scheme', 'answer', 'point', 'ticket', 'media'))
    assert 'error' in t.scheme(n)
    assert 'unallocated' not in json.dumps(t.scheme(n))


@pytest.mark.parametrize('work', ['', '  ', 'idk', 'skip', "I don't know", 'done on paper', 'on paper'])
def test_whole_attempt_gate(opened, work):
    t, n = opened
    before = copy.deepcopy(t.state)
    out = disclose(t, n, work)
    assert out.get('error') and 'point' not in out and 'ticket' not in out
    assert answers(t) == [] and t.state == before


@pytest.mark.parametrize('confirmation', [False, 'true', 1, None])
def test_whole_paper_confirmation_is_exact_bool(opened, confirmation):
    t, n = opened
    assert disclose(t, n, 'done on paper', paper_attempt=confirmation).get('error')
    assert answers(t) == []


def test_whole_paper_confirmation_and_resume(opened):
    t, n = opened
    out = disclose(t, n, 'done on paper', paper_attempt=True)
    assert out['ticket'] and answers(t) == []
    p = t.session['presented'][str(n)]
    assert p['whole_paper_work'] == 'done on paper'
    resumed = session.Tutor(store.Vault(t.vault.root))
    assert award(resumed, n, out['ticket'], work='done on paper')['results'][0].get('error')
    assert 'error' in resumed.scheme(n)
    fresh = disclose(resumed, n, 'done on paper', paper_attempt=True)
    assert award(resumed, n, fresh['ticket'], work='done on paper')['results'][0]['event']


@pytest.mark.parametrize('earned', [0, 1, 2])
def test_whole_explicit_human_award_0_1_2(opened, earned):
    t, n = opened
    before = copy.deepcopy(t.state)
    out = disclose(t, n)
    assert out['max_marks'] == 2 and out['media'] == [] and answers(t) == [] and t.state == before
    result = award(t, n, out['ticket'], earned)
    assert result['results'][0]['event']
    event = answers(t)[0]
    assert event['grade']['score'] == earned / 2
    assert event['grade']['correct'] is (earned == 2)
    assert event['human_award']['earned_marks'] == earned and event['human_award']['marker'] == 'human'
    assert event['question']['scheme'] == whole()['scheme']
    assert len(answers(t)) == 1
    assert not t.regrade(event['id'], 'model wants full credit')['ok']


@pytest.mark.parametrize('text,kwargs', [
    ('pts=1', {}), ('= my work', {'judge': {1: 1}}), ('?', {'judge': {1: 1}}),
    ('?', {'manual_awards': {1: {'earned_marks': 2, 'ticket': 'bad'}}}),
    ('pts=1', {'manual_awards': {1: {'earned_marks': 2, 'ticket': 'bad'}}}),
])
def test_whole_judge_pts_cannot_award(opened, text, kwargs):
    t, n = opened
    assert n == 1
    out = t.answer(f'{n} {text}', **kwargs)
    assert out['results'][0].get('error') and answers(t) == []


def test_whole_plain_value_pending_bare_idk_preserved(opened):
    t, n = opened
    out = t.answer(f'{n} = actual written attempt')
    assert out['results'][0].get('pending_manual') and answers(t) == []
    assert t.session['presented'][str(n)]['saved_work'] == 'actual written attempt'
    out = t.answer(f'{n}?')
    assert out['results'][0]['event'] and answers(t)[0]['grade']['score'] == 0
    assert out['results'][0].get('answer_withheld')


@pytest.mark.parametrize('change', ['work', 'scheme', 'source', 'session', 'question', 'guard', 'stored', 'cancel', 'reuse'])
def test_manual_award_rechecks_ticket_item_work_media_and_guards(opened, change):
    t, n = opened
    out = disclose(t, n); token = out['ticket']; p = t.session['presented'][str(n)]
    if change == 'work': p['saved_work'] = 'changed'
    if change == 'scheme': p['inst']['scheme'][0]['point'] = 'changed'
    if change == 'source': p['inst']['source'] = {'ref': 'changed'}
    if change == 'session': t.session = copy.deepcopy(t.session)
    if change == 'question': t.session['presented'][str(n)] = copy.deepcopy(p)
    if change == 'guard': t.session['skipped_answer_guards'] = {'other': {'question': {'inst': {}}}}
    if change == 'stored': deferred_notes.hold(t.vault.tutor / 'state/deferred-notes.json', 'other', {'question': {'inst': {}}})
    if change == 'cancel': t.cancel_marking(token)
    if change == 'reuse': assert t.marking_status(token) == 'ok'
    result = award(t, n, token)
    assert result['results'][0].get('error') and answers(t) == []


def test_whole_guard_refuses_disclosure_and_preserves_draft(opened):
    t, n = opened
    t.session['skipped_answer_guards'] = {'other': {'question': {'inst': {'answer': 'secret'}}}}
    out = disclose(t, n)
    assert out.get('error') and 'point' not in out and not t._marking_tickets
    assert t.session['presented'][str(n)]['saved_work'] == 'My graph rises from the origin.'


def test_whole_exact_multiline_work_is_preserved(opened):
    t, n = opened
    work = '  First step, 2 units.\n1 = a labelled point\nFinal step.  '
    out = disclose(t, n, work)
    result = award(t, n, out['ticket'], work=work)
    assert result['results'][0].get('event'), result
    assert answers(t)[0]['response'] == work


def test_whole_legitimate_same_question_skip_retry(opened):
    t, n = opened
    t.answer(f'{n}?')
    retry = t.retry_skipped()
    assert retry.get('items'), retry
    number = retry['items'][0]['n']
    rubric = disclose(t, number)
    assert 'ticket' in rubric, rubric
    assert award(t, number, rubric['ticket'])['results'][0]['event']
    assert not t.marking_guards()
    assert len(answers(t)) == 2


@pytest.mark.parametrize('kwargs', [{'manual_awards': {}}, {'judge': {}}])
def test_whole_idk_with_any_award_override_payload_rejects(opened, kwargs):
    t, n = opened
    result = t.answer(f'{n}?', **kwargs)
    assert result['results'][0].get('error') and answers(t) == []


@pytest.mark.parametrize('field,value', [('marks', 99), ('item', 'other'), ('kcs', ['9702-2.1.4'])])
def test_manual_ticket_binds_recording_metadata(opened, field, value):
    t, n = opened
    rubric = disclose(t, n)
    t.session['presented'][str(n)][field] = value
    assert award(t, n, rubric['ticket'])['results'][0].get('error')
    assert answers(t) == []


@pytest.mark.parametrize('token_kind', ['stale', 'cancelled', 'unknown', 'invalid-award'])
def test_manual_award_on_protected_retry_cannot_defer_or_clear_guards(opened, token_kind):
    """SPEC-1: a failed award is not an instruction to save an ungraded retry."""
    t, first = opened
    t.answer(f'{first}?')
    n = t.retry_skipped()['items'][0]['n']
    work = 'My graph rises from the origin.\nA labelled point, with units.'
    token = disclose(t, n, work)['ticket']
    if token_kind == 'cancelled':
        t.cancel_marking(token)
    elif token_kind == 'unknown':
        token = 'unknown-token'
    other = {'question': {'inst': {'id': 'other-q', 'answer': 'private'}}}
    t.session['skipped_answer_guards']['other'] = copy.deepcopy(other)
    guard_path = t.vault.tutor / 'state/deferred-notes.json'
    deferred_notes.hold(guard_path, 'other', other)
    before_session = copy.deepcopy(t.session)
    before_events = {p: p.read_bytes() for p in (t.vault.tutor / 'events').glob('*.jsonl')}
    before_guards = guard_path.read_bytes()
    result = award(t, n, token, earned=True if token_kind == 'invalid-award' else 1, work=work)
    assert result['results'][0].get('error'), result
    assert t.session == before_session
    assert guard_path.read_bytes() == before_guards
    assert all(p.read_bytes() == data for p, data in before_events.items())
    assert token not in t._marking_tickets


def test_whole_retry_without_manual_award_keeps_ungraded_deferral(opened):
    """The failed-award gate must not widen the ordinary guard policy."""
    t, first = opened
    t.answer(f'{first}?')
    n = t.retry_skipped()['items'][0]['n']
    ident = session._guard_identity(t.session['presented'][str(n)])
    other = {'question': {'inst': {'id': 'other-q', 'answer': 'private'}}}
    t.session['skipped_answer_guards']['other'] = copy.deepcopy(other)
    deferred_notes.hold(t.vault.tutor / 'state/deferred-notes.json', 'other', other)
    work = 'My saved graph attempt.'
    result = t.answer(f'{n} = {work}')['results'][0]
    assert result.get('attempt_saved') is True and result.get('event')
    assert str(n) not in t.session['presented']
    assert ident not in t.session['skipped_answer_guards'] and 'other' in t.session['skipped_answer_guards']
    event = next(e for e in t.vault.events() if e['id'] == result['event'])
    assert event['type'] == 'ungraded_retry' and event['response'] == work
    assert len(answers(t)) == 1  # only the original IDK


def test_unavailable_whole_retry_refuses_disclosure_and_manual_award(opened):
    """SPEC-2: only the existing unavailable-retry save/cancel methods may act."""
    t, first = opened
    t.answer(f'{first}?')
    n = t.retry_skipped_ungraded()['items'][0]['n']
    p = t.session['presented'][str(n)]
    assert p['ungraded_unavailable'] is True
    p['saved_work'] = 'Original saved draft.'
    before = copy.deepcopy(t.session)
    events = list(t.vault.events())
    result = disclose(t, n, 'Different working must use the ungraded save path.')
    assert result.get('error') and not any(k in result for k in ('point', 'media', 'ticket'))
    assert t.session == before and not t._marking_tickets
    result = award(t, n, 'unavailable-ticket', work='Original saved draft.')
    assert result['results'][0].get('error')
    assert t.session == before and list(t.vault.events()) == events
