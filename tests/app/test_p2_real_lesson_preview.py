"""Inspect draft P2 lesson content through the real engine in a disposable vault."""
import asyncio
import json
import random
from datetime import datetime, timedelta
from pathlib import Path

from fixtures import make_vault
from library_assets import install_course
from test_tui import FAKE
from tutor_app.app import TutorApp
from tutor_app.screens import SessionScreen
from tutor_app import learn_reply
from tutor_app.ai import Result
from test_p2_guided_pilot import corrected_draft_pack
from tutorlib import lesson, model, session, store
from textual.widgets import Button

ROOT = Path(__file__).resolve().parents[2]


def _stage_p2(vault):
    return install_course(vault, 'P2', 'P2-1')


def test_p2_learning_tutor_uses_real_lesson_card_and_conversation(tmp_path, monkeypatch):
    vault = make_vault(tmp_path)
    pack = _stage_p2(vault)
    app = TutorApp(vault, claude_binary=FAKE, open_obsidian=False, seed=1)
    calls = []

    async def select(prompt, **kwargs):
        calls.append((prompt, kwargs))
        return {'sections': ['P2-1.1|plain_words']}, Result()

    async def run():
        async with app.run_test(size=(100, 30)) as pilot:
            await pilot.pause()  # the engine loads after the first paint
            monkeypatch.setattr(app, 'ai_available', lambda mode: True)
            monkeypatch.setattr(app.ai, 'one_shot', select)
            app.push_screen(SessionScreen({'mode': 'lesson', 'minutes': 40, 'focus': ['P2-1']}))
            await pilot.pause()
            screen, tutor = app.screen, app.tutor
            for _ in range(30):
                act = screen.act
                if act.get('part') == 'plain_words':
                    break
                if act['activity'] == 'choose':
                    tutor.respond({'choice': 'scratch'})
                elif act['activity'] == 'plan':
                    tutor.respond({'teach': act['default_teach']})
                elif act['activity'] == 'questions':
                    q = act['items'][0]
                    answer = tutor.session['presented'][str(q['n'])]['inst']['answer']
                    tutor.answer(f"{q['n']}{answer}3")
                elif act['activity'] == 'explain':
                    tutor.respond({})
                else:
                    raise AssertionError(act)
                screen.advance()
                await pilot.pause()
            assert screen.act.get('part') == 'plain_words' and screen.kc == 'P2-1.1'
            detail = screen.act['detail']
            assert detail not in (vault / 'Now.md').read_text()
            screen.query_one('#detail', Button).press()
            await pilot.pause()
            squash = lambda text: ''.join(text.replace('>', '').split())  # Now re-spaces text with the one output format (and quotes it in a callout), never the words
            missing = [p for p in detail.split('\n\n') if squash(p) not in squash((vault / 'Now.md').read_text())]
            assert not missing, missing
            await screen.learn_request('Why is a general argument needed?').wait()
            await screen.learn_request('Can you explain that another way?').wait()
            assert len(calls) == 2
            assert 'Why is a general argument needed?' in calls[1][0]
            assert corrected_draft_pack()['teach']['P2-1.1']['plain_words'] in (vault / 'Now.md').read_text()
            await app.ai.close()
    asyncio.run(run())


def test_real_p2_lesson_reaches_final_check_from_start(tmp_path):
    vault = make_vault(tmp_path)
    pack = _stage_p2(vault)
    tutor = session.Tutor(store.Vault(vault), rng=random.Random(0),
                          now=lambda: datetime.fromisoformat('2026-09-29T17:00:00+08:00'))
    cards = learn_reply.published_related_cards(tutor, 'P2-1.1')
    assert 'P2-1.1' in cards
    term = cards['P2-1.1']['terms'][0]
    selection = learn_reply.exact_term_selection(f"Define {term['term']}", 'P2-1.1', cards)
    text, problem = learn_reply.render_related_selection(selection, cards)
    assert not problem and term['meaning'] in text
    assert tutor.start('lesson', minutes=40, focus=['P2-1']).get('session')
    seen = []
    form_checks = 0
    exit_checks = 0
    exit_kcs = set()
    for _ in range(500):
        act = tutor.next()
        seen.append((act['activity'], act.get('part')))
        form_checks += act.get('phase') == 'form_check'
        exit_checks += act.get('block') == 'exit' and act['activity'] == 'questions'
        if act['activity'] == 'end':
            break
        if act['activity'] == 'choose':
            tutor.respond({'choice': 'scratch'})
        elif act['activity'] == 'plan':
            tutor.respond({'teach': act['default_teach']})
        elif act['activity'] in ('questions', 'awaiting'):
            for question in act['items']:
                instance = tutor.session['presented'][str(question['n'])]['inst']
                if act.get('block') == 'exit':
                    exit_kcs.update(instance['kcs'])
                n = question['n']
                assert instance['id'] not in {'P2-1-i04', 'P2-1-r01', 'P2-1-i07', 'P2-1-i08',
                                               'P2-1-i09', 'P2-1-i10', 'P2-1-i12', 'P2-1-i14',
                                               'P2-1-i15', 'P2-1-i17'}, \
                    'lesson check repeats a worked example'
                assert not ({'answer', 'rubric', 'explanation', 'distractors'} & question.keys())
                log = next((vault / 'Lessons').rglob('*.md')).read_text()
                question_label = f'> [!question] Q{n} ·'
                assert question_label in log
                assert f'Q{n} — ' not in log
                if question['kind'] == 'mcq':
                    result = tutor.answer(f"{n}{instance['answer']}3")
                elif question['kind'] == 'short':
                    result = tutor.answer(f'{n} = A practice response ~3', judge={n: 1})
                elif question['kind'] == 'numeric':
                    answer = instance['answer']
                    result = tutor.answer(f"{n} = {answer['value']} {answer.get('unit', '')} ~3")
                else:
                    raise AssertionError(f"Unhandled question kind: {question['kind']}")
                assert not any(row.get('error') for row in result.get('results', [])), result
        elif act['activity'] in ('worked', 'walkthrough'):
            for step in range(1, len(act['steps']) + 1):
                assert tutor.respond({'step': step}).get('revealed') == step
            tutor.respond({'done': True})
        elif act['activity'] == 'own_words':
            tutor.respond({'text': 'A proof gives a reason for every permitted case.'})
        elif act['activity'] in ('explain', 'refute', 'stuck'):
            tutor.respond({})
        else:
            raise AssertionError(f'Unexpected lesson activity: {act}')
    assert ('explain', 'terms') in seen
    assert ('explain', 'plain_words') in seen
    assert seen.index(('explain', 'terms')) < seen.index(('explain', 'plain_words'))
    expected_forms = sum(len(card['forms']) for card in corrected_draft_pack()['teach'].values())
    assert sum(part == 'form_example' for _, part in seen) == expected_forms == 36
    assert form_checks == expected_forms
    assert exit_checks > 0
    assert {'P2-1.1', 'P2-1.2', 'P2-1.3'} <= exit_kcs
    assert seen[-1][0] == 'end'
    expected_terms = {lesson.term_id(kc, term['term']) for kc, card in corrected_draft_pack()['teach'].items()
                      for term in card.get('terms', [])}
    assert expected_terms <= set(tutor.state['terms'])
    due = max(datetime.fromisoformat(tutor.state['terms'][tid]['fsrs']['due']) for tid in expected_terms)
    tutor.end()
    tutor.now = lambda: due + timedelta(seconds=1)
    plan = tutor.start('review', minutes=50)
    planned_terms = {tid for block in plan['blocks'] if block['kind'] == 'term_review' for tid in block['terms']}
    assert planned_terms and planned_terms <= expected_terms
    act = tutor.next()
    assert act.get('phase') == 'term_review'
    q = act['items'][0]
    presented = tutor.session['presented'][str(q['n'])]['inst']
    tid, meaning = presented['term_id'], presented['review_answer']
    assert meaning not in str(q)
    tutor.answer(f"{q['n']} = {meaning} ~3", judge={q['n']: 1})
    assert tutor.state['terms'][tid]['reviews'] == 1
    assert tid not in model.due_terms(tutor.state, tutor.now())


def test_radius_line_through_real_p2_engine(tmp_path, monkeypatch):
    monkeypatch.setenv('STEM_TUTOR_NOW', '2026-09-29T17:00:00+08:00')
    vault = make_vault(tmp_path)
    pack = _stage_p2(vault)
    form = next(f for f in pack['teach']['P2-1.1']['forms']
                if f['name'] == 'Show a radius-line equation from a tangent')
    index = pack['teach']['P2-1.1']['forms'].index(form)
    app = TutorApp(vault, claude_binary=FAKE, open_obsidian=False, seed=1)

    async def run():
        async with app.run_test(size=(80, 24)) as pilot:
            await pilot.pause()  # the engine loads after the first paint
            app.push_screen(SessionScreen({'mode': 'lesson', 'minutes': 30, 'focus': ['P2-1']}))
            await pilot.pause()
            screen, tutor = app.screen, app.tutor
            tutor.session['presented'] = {}
            tutor.session['queue'] = {}
            tutor.session['awaiting'] = None
            tutor.session['blocks'] = [{'kind': 'node', 'kc': 'P2-1.1', 'card': pack['teach']['P2-1.1'],
                                         'i': 0, 'phases': [f'form_example:{index}', 'done'],
                                         'misses': 0, 'mistakes': []}]
            tutor.session['cursor'] = 0
            screen.fold()
            screen.advance()
            await pilot.pause()
            assert screen.act['part'] == 'form_example'
            assert screen.act['title'] == form['name']
            now = (vault / 'Now.md').read_text()
            assert all(line in now for line in form['example'].splitlines() if line.strip())
            assert form['answer'] not in now
            app.save_screenshot(path='/tmp', filename='p2-real-radius-80.svg')
            await app.ai.close()
    asyncio.run(run())


def test_quadratic_gradient_example_in_real_p2_lesson(tmp_path, monkeypatch):
    monkeypatch.setenv('STEM_TUTOR_NOW', '2026-09-29T17:00:00+08:00')
    vault = make_vault(tmp_path)
    pack = _stage_p2(vault)
    forms = pack['teach']['P2-1.1']['forms']
    index = next(i for i, f in enumerate(forms) if f['name'] == 'Prove no turning points using a quadratic gradient')
    form = forms[index]
    app = TutorApp(vault, claude_binary=FAKE, open_obsidian=False, seed=1)
    async def run():
        async with app.run_test(size=(80, 24)) as pilot:
            await pilot.pause()  # the engine loads after the first paint
            app.push_screen(SessionScreen({'mode': 'lesson', 'minutes': 30, 'focus': ['P2-1']}))
            await pilot.pause()
            screen, tutor = app.screen, app.tutor
            tutor.session['presented'] = {}
            tutor.session['queue'] = {}
            tutor.session['awaiting'] = None
            tutor.session['blocks'] = [{'kind': 'node', 'kc': 'P2-1.1', 'card': pack['teach']['P2-1.1'],
                                         'i': 0, 'phases': [f'form_example:{index}', 'done'],
                                         'misses': 0, 'mistakes': []}]
            tutor.session['cursor'] = 0
            screen.fold()
            screen.advance()
            await pilot.pause()
            assert screen.act['part'] == 'form_example' and screen.act['title'] == form['name']
            now = (vault / 'Now.md').read_text()
            assert all(line in now for line in form['example'].splitlines() if line.strip())
            assert form['answer'] not in now
            app.save_screenshot(path='/tmp', filename='p2-quadratic-gradient-80.svg')
            await app.ai.close()
    asyncio.run(run())


def test_revised_p2_checks_reteach_and_offer_reviewed_retry_in_real_engine(tmp_path):
    from tutorlib import session, store
    for serial, (kc, name) in enumerate((('P2-1.1', 'Geometric-series proof by cancellation'),
                                         ('P2-1.3', 'Counterexample after widening the domain'))):
        root = tmp_path / str(serial)
        root.mkdir()
        vault = make_vault(root)
        pack = _stage_p2(vault)
        forms = pack['teach'][kc]['forms']
        index = next(i for i, form in enumerate(forms) if form['name'] == name)
        form = forms[index]
        tutor = session.Tutor(store.Vault(vault), rng=random.Random(0))
        tutor.start('lesson', minutes=30, focus=['P2-1'])
        tutor.session['presented'] = {}; tutor.session['queue'] = {}; tutor.session['awaiting'] = None
        block = {'kind': 'node', 'kc': kc, 'card': pack['teach'][kc], 'i': 0,
                 'phases': [f'form_check:{index}', 'done'], 'misses': 0, 'mistakes': []}
        tutor.session['blocks'] = [block]; tutor.session['cursor'] = 0
        first = tutor.next()
        question = first['items'][0]
        assert question['stem'] == form['check'] and form['retry']['answer'] not in str(question)
        tutor.answer(f"{question['n']} = My incomplete attempt", judge={question['n']: 0})
        fix = tutor.next()
        assert fix['part'] == 'fix' and form['example'] in fix['text']
        assert form['retry']['answer'] not in fix['text']
        tutor.respond({})
        retry = tutor.next()['items'][0]
        assert retry['stem'] == form['retry']['check'] and form['retry']['answer'] not in str(retry)
        assert form['retry']['answer'] not in (vault / 'Now.md').read_text()
        if name == 'Counterexample after widening the domain':
            assert tutor.session['presented'][str(retry['n'])]['inst']['review_rule'] == 'positive_pair'
        assert tutor.ai_help(given=False).get('refused')
