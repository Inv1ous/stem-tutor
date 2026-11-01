from library_assets import read_json as library_json
import asyncio
from copy import deepcopy
import pytest
from test_tui import app_for
from tutor_app.ai import Result
from tutor_app.screens import SessionScreen
from tutor_app import learn_reply
from tutor_app.panels import TickPanel


def test_geometric_review_checks_known_subtraction_forms():
    from tutor_app.guided_review import geometric_subtraction_note
    assert 'sign' in geometric_subtraction_note('S - rS = ar^n - a').lower()
    assert 'valid' in geometric_subtraction_note('rS - S = ar^n - a').lower()
    assert 'valid' in geometric_subtraction_note('S - rS = a - ar^n').lower()
    assert geometric_subtraction_note('I used a different derivation.') is None
    assert geometric_subtraction_note('S - rS = a - ar^n + 1') is None
    assert geometric_subtraction_note('rS - S = ar^n - a - 2') is None
    assert geometric_subtraction_note('2S - rS = a - ar^n') is None
    assert 'valid' in geometric_subtraction_note('Hence $rS − S = ar^{n} − a$.').lower()


@pytest.mark.parametrize('size', [(100, 30), (60, 24)])
@pytest.mark.parametrize('model_name', ['ollama:gemma4:e4b', 'sonnet', 'codex:gpt-5.4'])
@pytest.mark.parametrize('phase', ['form_check', 'term_review', 'faded'])
def test_guided_marking_is_reviewed_before_recording(tmp_path, monkeypatch, size, model_name, phase):
    app, _ = app_for(tmp_path, monkeypatch)
    points = ['Both classes', 'Proof for each']

    async def examiner(*args, **kwargs):
        return {'points': [{'point': p, 'met': True} for p in points], 'feedback': 'Complete.'}, Result()

    async def run():
        async with app.run_test(size=size) as pilot:
            t = app.tutor
            t.start('review', minutes=10)
            item = {'id': 'guided-check', 'kcs': ['9702-2.1.1'], 'kind': 'short', 'difficulty': 3,
                    'marks': 2, 'stem': 'Give two cases.', 'review_answer': 'A sample solution.',
                    'rubric': [{'point': p, 'keywords': [[p]]} for p in points]}
            view = t._present(item, block='practice', phase=phase)
            assert 'A sample solution.' not in str(view)
            screen = SessionScreen(None)
            await app.push_screen(screen)
            await pilot.pause()
            monkeypatch.setattr(app, 'ai_available', lambda mode: True)
            monkeypatch.setattr(app.ai, 'one_shot', examiner)
            app.settings.ai_mark_model = model_name
            data = {'entry': f"{view['n']} = one case", 'your': 'one case'}
            if phase == 'faded':
                assert t.answer(data['entry'])['results'][0]['attempt_confirmation_required']
                assert t.confirm_faded_attempt(view['n'], 'one case')['ok']
            screen.pending_short = (view['n'], data, 2)
            await screen.judge_short(view, data, {'rubric': points}).wait()
            await pilot.pause()
            assert not [e for e in t.vault.events() if e['type'] == 'answer']
            panel = screen.query_one('#panel > *', TickPanel)
            assert 'alternative methods may earn credit' in panel.prompt
            from textual.widgets import Button
            for button in panel.query(Button):
                assert button.region.bottom <= app.size.height
                assert button.region.right <= app.size.width
            assert set(panel.query_one('#ticks').selected) == set()
            assert 'unverified' in panel.prompt.lower()
            assert all('AI suggests met' in row[0] for row in panel.items)
            assert 'A sample solution.' in (t.vault.root / 'Now.md').read_text()
            assert 'one case' in (t.vault.root / 'Now.md').read_text()
            screen.long_marks({'ticked': ['0']})
            assert [e for e in t.vault.events() if e['type'] == 'answer'][-1]['grade']['score'] == 0.5
            marked = (t.vault.root / 'Now.md').read_text()
            if phase in ('form_check', 'faded'):
                assert '✓ Both classes' in marked and '✗ Proof for each' in marked
                recent = t.session['recent'][-1]
                assert '✓ Both classes' in recent['explanation'] and '✗ Proof for each' in recent['explanation']
            await app.ai.close()
    asyncio.run(run())


def test_factor_theorem_review_shows_both_methods_only_after_attempt(tmp_path, monkeypatch):
    import json
    from pathlib import Path
    app, vault = app_for(tmp_path, monkeypatch)
    root = Path(__file__).resolve().parents[2]
    card = library_json('build/work/teach/P2-1.json')['P2-1.1']
    form = next(f for f in card['forms'] if f['name'] == 'Show a parameter using the factor theorem')
    async def run():
        async with app.run_test(size=(100, 30)) as pilot:
            t = app.tutor
            t.start('review', minutes=10)
            item = {'id': 'factor-check', 'kcs': ['9702-2.1.1'], 'kind': 'short', 'difficulty': 3,
                    'marks': len(form['rubric']), 'stem': form['check'], 'review_answer': form['answer'],
                    'rubric': form['rubric']}
            view = t._present(item, block='practice', phase='form_check')
            assert 'Alternatively, substitute' not in str(view)
            screen = SessionScreen(None)
            await app.push_screen(screen)
            await pilot.pause()
            screen.show_guided_review_answer(view['n'], {'your': ''})
            assert 'Alternatively, substitute' not in (vault / 'Now.md').read_text()
            screen.show_guided_review_answer(view['n'], {'your': 'I tried using the factor theorem.'})
            assert form['answer'] in (vault / 'Now.md').read_text()
            await app.ai.close()
    asyncio.run(run())


def test_skipped_guided_check_does_not_reveal_example_answer(tmp_path, monkeypatch):
    app, vault = app_for(tmp_path, monkeypatch)
    async def run():
        async with app.run_test(size=(100, 30)):
            t = app.tutor
            t.start('review', minutes=10)
            item = {'id': 'guided-skip', 'kcs': ['9702-2.1.1'], 'kind': 'short', 'difficulty': 3,
                    'marks': 1, 'stem': 'Show your proof.', 'review_answer': 'PRIVATE SOLUTION',
                    'rubric': [{'point': 'PRIVATE MARK POINT', 'keywords': [['proof']]}]}
            view = t._present(item, block='practice', phase='form_check')
            result = t.answer(f"{view['n']}?")
            assert 'PRIVATE SOLUTION' not in str(result)
            assert 'PRIVATE SOLUTION' not in (vault / 'Now.md').read_text()
            assert 'PRIVATE MARK POINT' not in str(result)
            assert 'PRIVATE MARK POINT' not in (vault / 'Now.md').read_text()
            answer_event = [e for e in t.vault.events() if e['type'] == 'answer'][-1]
            assert 'PRIVATE MARK POINT' not in str(answer_event.get('key'))
            assert 'PRIVATE MARK POINT' not in str(t.session['recent'])
    asyncio.run(run())


def test_guided_form_result_feeds_reviewed_points_into_lesson_history(tmp_path, monkeypatch):
    app, _ = app_for(tmp_path, monkeypatch)
    async def run():
        async with app.run_test(size=(100, 30)):
            t = app.tutor
            t.start('review', minutes=10)
            block = {'kind': 'node', 'kc': '9702-2.1.1', 'i': 0, 'phases': ['done'], 'misses': 0, 'mistakes': []}
            t.session['blocks'] = [block]
            item = {'id': 'guided-feedback', 'kcs': [block['kc']], 'kind': 'short', 'difficulty': 3,
                    'marks': 2, 'stem': 'Explain.', 'form_index': 1,
                    'rubric': [{'point': 'First', 'keywords': [['first']]},
                               {'point': 'Second', 'keywords': [['second']]}]}
            view = t._present(item, block='node', phase='form_check', block_idx=0)
            n = view['n']
            reviewed = '✓ First\n✗ Second'
            result = t.answer(f'{n} = first', judge={n: 0.5}, explanation={n: reviewed})
            assert result['results'][0]['score'] == 0.5
            assert reviewed in block['mistakes'][-1]
            assert reviewed in t.session['recent'][-1]['explanation']
            assert block['fix_form'] == 1
    asyncio.run(run())


@pytest.mark.parametrize(('model_name', 'phase'), [('sonnet', None), ('codex:gpt-5.4', None), ('ollama:gemma4:e4b', None)])
def test_ordinary_marking_keeps_existing_flow(tmp_path, monkeypatch, model_name, phase):
    app, _ = app_for(tmp_path, monkeypatch)
    points = ['First point', 'Second point']

    async def examiner(*args, **kwargs):
        return {'points': [{'point': p, 'met': i == 0} for i, p in enumerate(points)], 'feedback': 'Partial.'}, Result()

    async def run():
        async with app.run_test(size=(100, 30)) as pilot:
            t = app.tutor
            t.start('review', minutes=10)
            item = {'id': 'ordinary', 'kcs': ['9702-2.1.1'], 'kind': 'short', 'difficulty': 3,
                    'marks': 2, 'stem': 'Explain.',
                    'rubric': [{'point': p, 'keywords': [[p]]} for p in points]}
            view = t._present(item, block='practice', phase=phase)
            screen = SessionScreen(None)
            await app.push_screen(screen)
            await pilot.pause()
            monkeypatch.setattr(app, 'ai_available', lambda mode: True)
            monkeypatch.setattr(app.ai, 'one_shot', examiner)
            app.settings.ai_mark_model = model_name
            data = {'entry': f"{view['n']} = answer", 'your': 'answer'}
            screen.pending_short = (view['n'], data, 2)
            await screen.judge_short(view, data, {'rubric': points}).wait()
            await pilot.pause()
            answers = [e for e in t.vault.events() if e['type'] == 'answer']
            assert len(answers) == 1 and answers[-1]['grade']['score'] == 0.5
            await app.ai.close()
    asyncio.run(run())


def test_local_mark_review_remains_usable_in_small_terminal(tmp_path, monkeypatch):
    from textual.containers import VerticalScroll
    from textual.widgets import Button
    app, _ = app_for(tmp_path, monkeypatch)
    points = ['Covers both allowed residue classes, for example n = 3k + 1 and n = 3k + 2.',
              'Shows a factor of 3 in each case and concludes for all allowed integers.']

    async def examiner(*args, **kwargs):
        return {'points': [{'point': p, 'met': i == 0} for i, p in enumerate(points)], 'feedback': 'Partial.'}, Result()

    async def run():
        async with app.run_test(size=(60, 24)) as pilot:
            t = app.tutor
            t.start('review', minutes=10)
            item = {'id': 'small-review', 'kcs': ['9702-2.1.1'], 'kind': 'short', 'difficulty': 3,
                    'marks': 2, 'stem': 'Give two cases.', 'review_answer': 'A worked answer.',
                    'rubric': [{'point': p, 'keywords': [[p]]} for p in points]}
            view = t._present(item, block='practice', phase='form_check')
            screen = SessionScreen(None)
            await app.push_screen(screen)
            await pilot.pause()
            monkeypatch.setattr(app, 'ai_available', lambda mode: True)
            monkeypatch.setattr(app.ai, 'one_shot', examiner)
            app.settings.ai_mark_model = 'ollama:gemma4:e4b'
            data = {'entry': f"{view['n']} = one case", 'your': 'one case'}
            screen.pending_short = (view['n'], data, 2)
            await screen.judge_short(view, data, {'rubric': points}).wait()
            await pilot.pause()
            panel = screen.query_one('#panel > *', TickPanel)
            button = panel.query_one('#self', Button)
            assert button.region.bottom <= app.size.height and button.region.right <= app.size.width
            assert panel.query_one('#ticks').region.height > 0
            log = screen.query_one('#log', VerticalScroll)
            await pilot.press('alt+down')
            await pilot.pause()
            assert log.scroll_y == log.max_scroll_y
            app.save_screenshot(path='/tmp', filename='p2-mark-review-60.svg')
            await pilot.press('down', 'space')
            assert set(panel.query_one('#ticks').selected) == {'1'}
            await app.ai.close()
    asyncio.run(run())


def test_explicit_misconception_is_retaught_and_added_to_profile(tmp_path, monkeypatch):
    app, vault = app_for(tmp_path, monkeypatch)
    card = {'misconceptions': [{'id': 'm1', 'idea': 'Distance and displacement are the same thing.',
                                'temptation': 'Both describe motion.', 'fix': 'Displacement has direction.'}]}
    monkeypatch.setattr(learn_reply, 'published_related_cards', lambda tutor, kc: {kc: card})
    async def run():
        async with app.run_test(size=(120, 40)) as pilot:
            monkeypatch.setattr(app, 'ai_available', lambda mode: True)
            app.push_screen(SessionScreen({'mode': 'test', 'minutes': 10, 'focus': ['9702-2.1']}))
            await pilot.pause()
            app.tutor.session['presented'] = {}
            app.tutor.session['queue'] = {}
            app.screen.kc = '9702-2.1.1'
            app.screen.learn_request('I think distance and displacement are the same thing.')
            await pilot.pause(0.3)
            assert 'Displacement has direction.' in (vault / 'Now.md').read_text()
            assert 'm1' in app.tutor.state['kcs']['9702-2.1.1']['active_misconceptions']
            assert '9702-2.1.1' in app.tutor.state['gaps']
            app.tutor.rebuild()
            assert 'm1' in app.tutor.state['kcs']['9702-2.1.1']['active_misconceptions']
            assert '9702-2.1.1' in app.tutor.state['gaps']
            await app.ai.close()
    asyncio.run(run())


def test_learning_tutor_revisits_recorded_misconception(tmp_path, monkeypatch):
    app, vault = app_for(tmp_path, monkeypatch)
    card = {'misconceptions': [{'id': 'm1', 'idea': 'Distance and displacement are the same thing.',
                                'temptation': 'Both describe motion.', 'fix': 'Displacement has direction.'}]}
    monkeypatch.setattr(learn_reply, 'published_related_cards', lambda tutor, kc: {kc: card})
    async def run():
        async with app.run_test(size=(100, 30)) as pilot:
            monkeypatch.setattr(app, 'ai_available', lambda mode: True)
            app.push_screen(SessionScreen({'mode': 'test', 'minutes': 10, 'focus': ['9702-2.1']}))
            await pilot.pause()
            app.tutor.session['presented'] = {}
            app.tutor.session['queue'] = {}
            app.screen.kc = '9702-2.1.1'
            app.tutor.state['kcs'].setdefault('9702-2.1.1', {})['active_misconceptions'] = ['m1']
            await app.screen.learn_request('What have I misunderstood?').wait()
            assert 'Displacement has direction.' in (vault / 'Now.md').read_text()
            await app.ai.close()
    asyncio.run(run())


def test_learning_misconception_brings_existing_review_forward(tmp_path, monkeypatch):
    from datetime import timedelta
    from tutorlib import model
    app, vault = app_for(tmp_path, monkeypatch)
    kc = '9702-2.1.1'
    card = {'misconceptions': [{'id': 'm1', 'idea': 'Distance and displacement are the same thing.',
                                'temptation': 'Both describe motion.', 'fix': 'Displacement has direction.'}]}
    monkeypatch.setattr(learn_reply, 'published_related_cards', lambda tutor, key: {key: card})
    async def run():
        async with app.run_test(size=(100, 30)) as pilot:
            monkeypatch.setattr(app, 'ai_available', lambda mode: True)
            app.push_screen(SessionScreen({'mode': 'test', 'minutes': 10, 'focus': ['9702-2.1']}))
            await pilot.pause()
            tutor = app.tutor
            tutor.session['presented'] = {}
            tutor.session['queue'] = {}
            app.screen.kc = kc
            tutor.state['kcs'].setdefault(kc, model._new_kc())
            model._review(tutor.state, kc, True, tutor.now(), 'physics')
            tutor.state['kcs'][kc]['fsrs']['due'] = (tutor.now() + timedelta(days=20)).isoformat()
            await app.screen.learn_request('I think distance and displacement are the same thing.').wait()
            assert kc in model.due_kcs(tutor.state, tutor.now() + timedelta(seconds=1))
            await app.ai.close()
    asyncio.run(run())


def test_learning_forms_request_lists_wordings_without_answers(tmp_path, monkeypatch):
    app, vault = app_for(tmp_path, monkeypatch)
    card = {'forms': [{'name': 'Counterexample', 'wordings': ['Disprove'],
                       'example': 'A worked example.', 'check': 'SECRET CHECK', 'answer': 'SECRET ANSWER'}]}
    monkeypatch.setattr(learn_reply, 'published_related_cards', lambda tutor, kc: {kc: card})
    async def run():
        async with app.run_test(size=(120, 40)) as pilot:
            monkeypatch.setattr(app, 'ai_available', lambda mode: True)
            app.push_screen(SessionScreen({'mode': 'test', 'minutes': 10, 'focus': ['9702-2.1']}))
            await pilot.pause()
            app.tutor.session['presented'] = {}
            app.tutor.session['queue'] = {}
            app.screen.kc = '9702-2.1.1'
            app.tutor.session['learn_history'] = {'9702-2.1.1': [
                {'question': str(i), 'reply': 'earlier'} for i in range(4)]}
            app.screen.learn_request('Show question forms')
            await pilot.pause(0.3)
            text = (vault / 'Now.md').read_text()
            assert 'Counterexample' in text and 'Disprove' in text
            assert 'Show example for form 1' in text and 'Try form 1' in text
            assert 'SECRET CHECK' not in text and 'SECRET ANSWER' not in text
            assert app.tutor.session['learn_history']['9702-2.1.1'][-1]['reply'].startswith('- **Counterexample**')
            assert len(app.tutor.session['learn_history']['9702-2.1.1']) == 4
            assert app.tutor.session['learn_history']['9702-2.1.1'][0]['question'] == '1'
            await app.ai.close()
    asyncio.run(run())


def test_learning_diagram_request_uses_lesson_rendering(tmp_path, monkeypatch):
    app, vault = app_for(tmp_path, monkeypatch)
    card = {'diagrams': ['Assets/P2/proof.svg', 'Assets/P2/parity.svg'],
            'diagram_descriptions': ['The cases cover the domain.', 'Parity splits the integers.']}
    monkeypatch.setattr(learn_reply, 'published_related_cards', lambda tutor, kc: {kc: card})
    async def run():
        async with app.run_test(size=(120, 40)) as pilot:
            monkeypatch.setattr(app, 'ai_available', lambda mode: True)
            app.push_screen(SessionScreen({'mode': 'test', 'minutes': 10, 'focus': ['9702-2.1']}))
            await pilot.pause()
            app.tutor.session['presented'] = {}
            app.tutor.session['queue'] = {}
            app.screen.kc = '9702-2.1.1'
            app.screen.learn_request('Show me the diagram')
            await pilot.pause(0.3)
            text = (vault / 'Now.md').read_text()
            assert 'The cases cover the domain.' in text and '![[Assets/P2/proof.svg]]' in text
            assert 'Parity splits the integers.' in text and '![[Assets/P2/parity.svg]]' in text
            exchange = app.tutor.session['learn_history']['9702-2.1.1'][-1]
            assert exchange['question'] == 'Show me the diagram'
            assert 'Parity splits the integers.' in exchange['reply']
            assert 'Assets/P2/' not in exchange['reply']
            await app.ai.close()
    asyncio.run(run())


def test_learning_diagrams_are_withheld_when_skipped_answer_is_guarded(tmp_path, monkeypatch):
    from tutor_app import prompts
    app, vault = app_for(tmp_path, monkeypatch)
    card = {'diagrams': ['Assets/P2/proof.svg'], 'diagram_descriptions': ['A diagram.']}
    monkeypatch.setattr(learn_reply, 'published_related_cards', lambda tutor, kc: {kc: card})
    monkeypatch.setattr(prompts, 'guard_keys', lambda tutor: [('short', 'secret', None)])
    async def run():
        async with app.run_test(size=(120, 40)) as pilot:
            monkeypatch.setattr(app, 'ai_available', lambda mode: True)
            app.push_screen(SessionScreen({'mode': 'test', 'minutes': 10, 'focus': ['9702-2.1']}))
            await pilot.pause()
            app.tutor.session['presented'] = {}
            app.tutor.session['queue'] = {}
            app.screen.kc = '9702-2.1.1'
            app.screen.learn_request('Show me the diagram')
            await pilot.pause(0.3)
            # The ordinary lesson button shares this renderer.
            assert app.screen.show_lesson_diagrams(card) is False
            text = (vault / 'Now.md').read_text()
            assert '![[Assets/P2/proof.svg]]' not in text
            assert 'diagram is withheld' in text.lower()
            await app.ai.close()
    asyncio.run(run())


def test_form_request_is_available_as_safe_context_for_follow_up(tmp_path, monkeypatch):
    app, vault = app_for(tmp_path, monkeypatch)
    card = {'plain_words': 'A counterexample refutes a universal claim.',
            'forms': [{'name': 'Counterexample', 'wordings': ['Disprove'],
                       'check': 'SECRET CHECK', 'answer': 'SECRET ANSWER'}]}
    monkeypatch.setattr(learn_reply, 'published_related_cards', lambda tutor, kc: {kc: card})
    prompts_seen = []

    async def fake(prompt, **kwargs):
        prompts_seen.append(prompt)
        return {'sections': ['9702-2.1.1|plain_words']}, Result()

    async def run():
        async with app.run_test(size=(120, 40)) as pilot:
            monkeypatch.setattr(app.ai, 'one_shot', fake)
            monkeypatch.setattr(app, 'ai_available', lambda mode: True)
            app.push_screen(SessionScreen({'mode': 'test', 'minutes': 10, 'focus': ['9702-2.1']}))
            await pilot.pause()
            app.tutor.session['presented'] = {}
            app.tutor.session['queue'] = {}
            app.screen.kc = '9702-2.1.1'
            app.screen.learn_request('Show question forms')
            await pilot.pause(0.3)
            app.screen.learn_request('Explain the first form')
            await pilot.pause(0.3)
            assert len(prompts_seen) == 1
            assert 'Student: Show question forms' in prompts_seen[0]
            assert 'Counterexample' in prompts_seen[0]
            assert 'SECRET CHECK' not in prompts_seen[0] and 'SECRET ANSWER' not in prompts_seen[0]
            await app.ai.close()
    asyncio.run(run())


def test_learning_tutor_shows_requested_form_example_without_check_answer(tmp_path, monkeypatch):
    app, vault = app_for(tmp_path, monkeypatch)
    card = {'diagrams': ['Assets/P2/example.svg', 'Assets/P2/other.svg'],
            'diagram_descriptions': ['The example figure.', 'Another figure.'],
            'forms': [{'name': 'First form', 'example': 'A distinct worked example.',
                       'diagram': 'Assets/P2/example.svg', 'check': 'PRIVATE CHECK', 'answer': 'PRIVATE ANSWER'}]}
    monkeypatch.setattr(learn_reply, 'published_related_cards', lambda tutor, kc: {kc: card})
    async def run():
        async with app.run_test(size=(100, 30)) as pilot:
            monkeypatch.setattr(app, 'ai_available', lambda mode: True)
            app.push_screen(SessionScreen({'mode': 'test', 'minutes': 10, 'focus': ['9702-2.1']}))
            await pilot.pause()
            app.tutor.session['presented'] = {}
            app.tutor.session['queue'] = {}
            app.screen.kc = '9702-2.1.1'
            await app.screen.learn_request('Show example for form 1').wait()
            text = (vault / 'Now.md').read_text()
            assert 'A distinct worked example.' in text
            assert '![[Assets/P2/example.svg]]' in text and '![[Assets/P2/other.svg]]' not in text
            assert 'PRIVATE ANSWER' not in text and 'PRIVATE CHECK' not in text
            app.tutor.session['skipped_answer_guards'] = {'old': {'kind': 'short', 'key': 'different wording'}}
            before = text.count('A distinct worked example.')
            await app.screen.learn_request('Show example for form 1').wait()
            assert (vault / 'Now.md').read_text().count('A distinct worked example.') == before
            await app.ai.close()
    asyncio.run(run())


def test_learning_tutor_can_practise_requested_form_without_losing_lesson(tmp_path, monkeypatch):
    from tutorlib import session, store
    app, vault = app_for(tmp_path, monkeypatch)
    card = {'forms': [{'name': 'First form', 'example': 'Worked example.', 'check': 'A new check?',
                       'answer': 'PRIVATE ANSWER', 'rubric': [{'point': 'PRIVATE POINT', 'keywords': [['point']]}]}]}
    monkeypatch.setattr(learn_reply, 'published_related_cards', lambda tutor, kc: {kc: card})
    async def run():
        async with app.run_test(size=(100, 30)) as pilot:
            monkeypatch.setattr(app, 'ai_available', lambda mode: True)
            app.push_screen(SessionScreen({'mode': 'test', 'minutes': 10, 'focus': ['9702-2.1']}))
            await pilot.pause()
            tutor = app.tutor
            tutor.session['presented'] = {}
            tutor.session['queue'] = {}
            tutor.session['awaiting'] = {'activity': 'explain', 'text': 'Resume this step.', 'block_idx': None}
            app.screen.kc = '9702-2.1.1'
            await app.screen.learn_request('Try form 1').wait()
            assert app.screen.view['stem'] == 'A new check?'
            assert 'PRIVATE ANSWER' not in (vault / 'Now.md').read_text()
            assert tutor.ai_help(given=False).get('refused')
            assert tutor.next()['activity'] == 'awaiting'
            restored = session.Tutor(store.Vault(vault), now=tutor.now)
            assert restored.next()['items'][0]['stem'] == 'A new check?'
            assert 'PRIVATE ANSWER' not in (vault / 'Now.md').read_text()
            n = app.screen.view['n']
            tutor.answer(f'{n} = some point', judge={n: 1})
            assert tutor.next()['text'] == 'Resume this step.'
            await app.ai.close()
    asyncio.run(run())


def test_skipping_requested_form_keeps_answer_private(tmp_path, monkeypatch):
    app, vault = app_for(tmp_path, monkeypatch)
    card = {'forms': [{'name': 'Form', 'check': 'A new check?', 'answer': 'PRIVATE ANSWER',
                       'rubric': [{'point': 'PRIVATE POINT', 'keywords': [['point']]}]}]}
    monkeypatch.setattr(learn_reply, 'published_related_cards', lambda tutor, kc: {kc: card})
    async def run():
        async with app.run_test(size=(100, 30)) as pilot:
            monkeypatch.setattr(app, 'ai_available', lambda mode: True)
            app.push_screen(SessionScreen({'mode': 'test', 'minutes': 10, 'focus': ['9702-2.1']}))
            await pilot.pause()
            tutor = app.tutor
            tutor.session['presented'] = {}
            tutor.session['queue'] = {}
            app.screen.kc = '9702-2.1.1'
            await app.screen.learn_request('Try form 1').wait()
            n = app.screen.view['n']
            feedback = tutor.answer(f'{n}?')
            assert 'PRIVATE ANSWER' not in str(feedback)
            assert 'PRIVATE POINT' not in (vault / 'Now.md').read_text()
            assert tutor.session['skipped_answer_guards']
            await app.ai.close()
    asyncio.run(run())


def test_learning_tutor_checks_explicit_arithmetic_without_model_output(tmp_path, monkeypatch):
    app, vault = app_for(tmp_path, monkeypatch)
    calls = []
    async def fake(*args, **kwargs):
        calls.append(args)
        return None, Result()
    async def run():
        async with app.run_test(size=(120, 40)) as pilot:
            monkeypatch.setattr(app.ai, 'one_shot', fake)
            monkeypatch.setattr(app, 'ai_available', lambda mode: True)
            app.push_screen(SessionScreen({'mode': 'test', 'minutes': 10, 'focus': ['9702-2.1']}))
            await pilot.pause()
            app.tutor.session['presented'] = {}
            app.tutor.session['queue'] = {}
            app.screen.kc = '9702-2.1.1'
            await app.screen.learn_request('Calculate 2 + 3 * 4').wait()
            assert '14' in (vault / 'Now.md').read_text()
            assert not calls
            assert app.tutor.session['learn_history']['9702-2.1.1'][-1]['reply'].endswith('= 14$')
            await app.screen.learn_request('Check identity: (x+1)^2 = x^2+2*x+1').wait()
            assert 'identity for all real values' in (vault / 'Now.md').read_text()
            assert not calls
            await app.ai.close()
    asyncio.run(run())


def test_guarded_structured_work_is_saved_without_mark_panel(tmp_path, monkeypatch):
    from tutor_app.panels import ContinuePanel
    app, _ = app_for(tmp_path, monkeypatch)
    async def run():
        async with app.run_test(size=(120, 40)) as pilot:
            app.push_screen(SessionScreen({'mode': 'test', 'minutes': 10, 'focus': ['9702-2.1']}))
            await pilot.pause()
            screen = app.screen
            screen.view = {'n': 42, 'kind': 'structured'}
            panels, saved = [], []
            monkeypatch.setattr(screen.tutor, 'scheme', lambda n: {'error': 'Protected answer.'})
            monkeypatch.setattr(screen.tutor, 'save_structured_draft', lambda n, text: saved.append((n, text)) or {'ok': True})
            monkeypatch.setattr(screen, 'panel', lambda panel: panels.append(panel))
            monkeypatch.setattr(screen, 'mark_panel', lambda *a, **k: pytest.fail('must not show marks'))
            screen.long_written({'text': 'My working'})
            assert saved == [(42, 'My working')]
            assert isinstance(panels[-1], ContinuePanel)
            assert {key for key, _ in panels[-1].buttons} == {'leave', 'suspend-for-retry'}
            assert 'without a mark' in panels[-1].prompt
            await app.ai.close()
    asyncio.run(run())


def test_exact_term_lookup_obeys_pending_question_guard(tmp_path, monkeypatch):
    from tutorlib.lesson import term_id
    app, vault = app_for(tmp_path, monkeypatch)
    calls = []
    card = {'terms': [{'term': 'Domain', 'meaning': 'The allowed values.', 'notation': 'none', 'spoken': 'domain'}]}
    monkeypatch.setattr(learn_reply, 'published_related_cards', lambda tutor, kc: {kc: card})
    async def fake(*args, **kwargs):
        calls.append(args)
        return None, Result()
    async def run():
        async with app.run_test(size=(120, 40)) as pilot:
            monkeypatch.setattr(app.ai, 'one_shot', fake)
            monkeypatch.setattr(app, 'ai_available', lambda mode: True)
            app.push_screen(SessionScreen({'mode': 'test', 'minutes': 10, 'focus': ['9702-2.1']}))
            await pilot.pause()
            assert app.tutor.session['presented']
            app.screen.kc = '9702-2.1.1'
            app.screen.learn_request('What does domain mean?')
            await pilot.pause(0.2)
            assert 'The allowed values.' not in (vault / 'Now.md').read_text()
            assert term_id('9702-2.1.1', 'Domain') not in app.tutor.state['terms']
            app.tutor.session['presented'] = {}
            app.tutor.session['queue'] = {}
            app.screen.learn_request('What does domain mean?')
            await pilot.pause(0.2)
            assert 'The allowed values.' in (vault / 'Now.md').read_text()
            assert term_id('9702-2.1.1', 'Domain') in app.tutor.state['terms']
            before = dict(app.tutor.state['terms'][term_id('9702-2.1.1', 'Domain')])
            await app.screen.learn_request('What does domain mean?').wait()
            assert app.tutor.state['terms'][term_id('9702-2.1.1', 'Domain')] == before
            assert not calls
            await app.ai.close()
    asyncio.run(run())


def test_requested_prerequisite_term_enters_review_after_restart(tmp_path, monkeypatch):
    import json
    from tutorlib import lesson, policy, session, store
    app, vault = app_for(tmp_path, monkeypatch)
    path = vault / '.tutor/packs/v1/specs/9702/packs/9702-2.1.json'
    pack = json.loads(path.read_text())
    prior, current = '9702-2.1.1', '9702-2.1.4'
    pack['teach'] = {prior: {'source': 'pack', 'motivate': 'Why', 'establish': 'Idea', 'connect': 'Link',
                              'note': 'Note', 'self_explain': 'Explain', 'terms': [
                                  {'term': 'Displacement', 'meaning': 'Change in position with direction.',
                                   'notation': 's', 'spoken': 'displacement'}]}}
    path.write_text(json.dumps(pack))
    async def run():
        async with app.run_test(size=(100, 30)) as pilot:
            monkeypatch.setattr(app, 'ai_available', lambda mode: True)
            app.push_screen(SessionScreen({'mode': 'test', 'minutes': 10, 'focus': ['9702-2.1']}))
            await pilot.pause()
            app.tutor.session['presented'] = {}
            app.tutor.session['queue'] = {}
            app.screen.kc = current
            await app.screen.learn_request('What is displacement?').wait()
            tid = lesson.term_id(prior, 'Displacement')
            assert tid in app.tutor.state['terms']
            restored = session.Tutor(store.Vault(vault), now=app.tutor.now)
            assert tid in policy.review_terms(restored.state, restored.packs, restored.now())
            await app.ai.close()
    asyncio.run(run())


def test_confident_probe_invites_try_first_for_broad_request(tmp_path, monkeypatch):
    app, vault = app_for(tmp_path, monkeypatch)
    calls = []
    monkeypatch.setattr(learn_reply, 'published_related_cards', lambda tutor, kc: {kc: {'self_explain': 'Which assumption would you check?'}})
    async def fake(*args, **kwargs):
        calls.append(args)
        return None, Result()
    async def run():
        async with app.run_test(size=(120, 40)) as pilot:
            monkeypatch.setattr(app.ai, 'one_shot', fake)
            monkeypatch.setattr(app, 'ai_available', lambda mode: True)
            app.push_screen(SessionScreen({'mode': 'test', 'minutes': 10, 'focus': ['9702-2.1']}))
            await pilot.pause()
            app.tutor.session['presented'] = {}
            app.tutor.session['queue'] = {}
            app.tutor.session['probe'] = {'9702-2.1.1': {'ok': True, 'conf': 3}}
            app.screen.kc = '9702-2.1.1'
            app.screen.learn_request('How should I approach this?')
            await pilot.pause(0.4)
            assert 'Which assumption would you check?' in (vault / 'Now.md').read_text()
            assert not calls
            await app.ai.close()
    asyncio.run(run())


def test_learning_tutor_uses_its_model_and_shows_only_validated_reply(tmp_path, monkeypatch):
    app, vault = app_for(tmp_path, monkeypatch)
    monkeypatch.setattr(learn_reply, 'published_related_cards', lambda tutor, kc: {kc: {'plain_words': 'Look at the assumptions first.'}})
    calls = []
    async def fake(prompt, **kwargs):
        calls.append(kwargs)
        return {'sections': ['9702-2.1.1|plain_words']}, Result()
    async def run():
        async with app.run_test(size=(120, 40)) as pilot:
            monkeypatch.setattr(app.ai, "one_shot", fake)
            monkeypatch.setattr(app, "ai_available", lambda mode: True)
            app.settings.ai_learn_model, app.settings.ai_learn_think = "sonnet", True
            app.push_screen(SessionScreen({"mode": "test", "minutes": 10, "focus": ["9702-2.1"]}))
            await pilot.pause()
            app.tutor.session["presented"] = {}
            app.tutor.session["queue"] = {}
            screen = app.screen
            screen.kc = "9702-2.1.1"
            screen.learn_request("How should I start?")
            await pilot.pause(0.5)
            assert calls and calls[0]["model"] == "sonnet" and calls[0]["think"] is True
            assert "Look at the assumptions" in (vault / "Now.md").read_text()
            await app.ai.close()
    asyncio.run(run())


def test_learning_tutor_offers_remaining_sections_on_request(tmp_path, monkeypatch):
    app, vault = app_for(tmp_path, monkeypatch)
    kc = '9702-2.1.1'
    cards = {kc: {'plain_words': 'Short explanation.', 'establish': 'Detailed explanation.'}}
    monkeypatch.setattr(learn_reply, 'published_related_cards', lambda tutor, current: cards)
    calls = []
    async def fake(prompt, **kwargs):
        calls.append(prompt)
        return {'sections': [kc + '|plain_words', kc + '|establish']}, Result()
    async def run():
        async with app.run_test(size=(120, 40)) as pilot:
            monkeypatch.setattr(app.ai, 'one_shot', fake)
            monkeypatch.setattr(app, 'ai_available', lambda mode: True)
            app.push_screen(SessionScreen({'mode': 'test', 'minutes': 10, 'focus': ['9702-2.1']}))
            await pilot.pause()
            app.tutor.session['presented'] = {}; app.tutor.session['queue'] = {}
            app.screen.kc = kc
            await app.screen.learn_request('Explain this idea').wait()
            text = (vault / 'Now.md').read_text()
            assert 'Short explanation.' in text and 'Detailed explanation.' not in text
            assert 'more detail' in text.lower()
            monkeypatch.setattr(app, 'ai_available', lambda mode: False)
            await app.screen.learn_request('Can you give me more detail?').wait()
            assert 'Detailed explanation.' in (vault / 'Now.md').read_text()
            assert len(calls) == 1
            monkeypatch.setattr(app, 'ai_available', lambda mode: True)
            await app.screen.learn_request('Explain another idea').wait()
            cards[kc]['establish'] = 'Changed detail.'
            await app.screen.learn_request('More detail').wait()
            text = (vault / 'Now.md').read_text()
            assert 'teaching material changed' in text.lower() and 'Changed detail.' not in text
            await app.ai.close()
    asyncio.run(run())


def test_short_first_keeps_plain_explanations_for_all_selected_ideas(tmp_path, monkeypatch):
    app, vault = app_for(tmp_path, monkeypatch)
    kc, related = '9702-2.1.1', '9702-2.1.2'
    cards = {kc: {'plain_words': 'General introduction.'}, related: {
        'plain_words': 'The directly relevant explanation.', 'establish': 'Further worked detail.'}}
    monkeypatch.setattr(learn_reply, 'published_related_cards', lambda tutor, current: cards)
    async def fake(prompt, **kwargs):
        return {'sections': [kc + '|plain_words', related + '|plain_words', related + '|establish']}, Result()
    async def run():
        async with app.run_test(size=(120, 40)) as pilot:
            monkeypatch.setattr(app.ai, 'one_shot', fake)
            monkeypatch.setattr(app, 'ai_available', lambda mode: True)
            app.push_screen(SessionScreen({'mode': 'test', 'minutes': 10, 'focus': ['9702-2.1']}))
            await pilot.pause()
            app.tutor.session['presented'] = {}; app.tutor.session['queue'] = {}
            app.screen.kc = kc
            await app.screen.learn_request('Explain this').wait()
            text = (vault / 'Now.md').read_text()
            assert 'General introduction.' in text and 'The directly relevant explanation.' in text
            assert 'Further worked detail.' not in text
            await app.ai.close()
    asyncio.run(run())


def test_learning_detail_survives_restart_and_waits_for_pending_question(tmp_path, monkeypatch):
    from tutorlib import session, store
    app, vault = app_for(tmp_path, monkeypatch)
    kc = '9702-2.1.1'
    card = {'plain_words': 'First safe explanation.', 'establish': 'Further safe explanation.'}
    monkeypatch.setattr(learn_reply, 'published_related_cards', lambda tutor, current: {kc: card})
    calls = []
    async def fake(prompt, **kwargs):
        calls.append(prompt)
        return {'sections': [kc + '|plain_words', kc + '|establish']}, Result()
    async def run():
        async with app.run_test(size=(120, 40)) as pilot:
            monkeypatch.setattr(app.ai, 'one_shot', fake)
            monkeypatch.setattr(app, 'ai_available', lambda mode: True)
            app.push_screen(SessionScreen({'mode': 'test', 'minutes': 10, 'focus': ['9702-2.1']}))
            await pilot.pause()
            app.tutor.session['presented'] = {}; app.tutor.session['queue'] = {}
            app.screen.kc = kc
            await app.screen.learn_request('Explain this').wait()
            item = {'id': 'queued-detail', 'kcs': [kc], 'kind': 'mcq', 'difficulty': 2, 'marks': 1,
                    'stem': 'Choose.', 'options': {'A': 'First', 'B': 'Second'}, 'answer': 'A'}
            number, queued = app.tutor._number(item, 'practice', 'practice')
            app.tutor.session['queue'] = {number: queued}
            app.tutor._save()
            restored = session.Tutor(store.Vault(vault), now=app.tutor.now)
            assert restored.session.get('learn_detail')
            app.tutor = restored
            assert restored.session.get('queue')
            await app.screen.learn_request('More detail').wait()
            assert restored.session.get('learn_detail') and 'Further safe explanation.' not in (vault / 'Now.md').read_text()
            restored.session['queue'] = {}
            await app.screen.learn_request('More detail').wait()
            assert 'Further safe explanation.' in (vault / 'Now.md').read_text()
            assert not restored.session.get('learn_detail') and len(calls) == 1
            await app.ai.close()
    asyncio.run(run())


def test_learning_detail_stays_withheld_for_skipped_question_after_restart(tmp_path, monkeypatch):
    from tutorlib import session, store
    from tutor_app import prompts
    app, vault = app_for(tmp_path, monkeypatch)
    kc = '9702-2.1.1'
    card = {'plain_words': 'First explanation.', 'establish': 'Further explanation.'}
    monkeypatch.setattr(learn_reply, 'published_related_cards', lambda tutor, current: {kc: card})
    async def fake(prompt, **kwargs):
        return {'sections': [kc + '|plain_words', kc + '|establish']}, Result()
    async def run():
        async with app.run_test(size=(120, 40)) as pilot:
            monkeypatch.setattr(app.ai, 'one_shot', fake)
            monkeypatch.setattr(app, 'ai_available', lambda mode: True)
            app.push_screen(SessionScreen({'mode': 'test', 'minutes': 10, 'focus': ['9702-2.1']}))
            await pilot.pause()
            tutor = app.tutor
            tutor.session['presented'] = {}; tutor.session['queue'] = {}; tutor.session['mode'] = 'lesson'
            app.screen.kc = kc
            await app.screen.learn_request('Explain this').wait()
            item = {'id': 'detail-skip', 'kcs': [kc], 'kind': 'mcq', 'difficulty': 2, 'marks': 1,
                    'stem': 'Choose.', 'options': {'A': 'Secret', 'B': 'Other'}, 'answer': 'A',
                    'explanation': 'Secret explanation.'}
            view = tutor._present(item, block='practice', phase='practice')
            tutor.answer(f"{view['n']}?")
            restored = session.Tutor(store.Vault(vault), now=tutor.now)
            app.tutor = restored
            assert restored.session.get('learn_detail')
            assert prompts.skipped_guards(restored)
            await app.screen.learn_request('More detail').wait()
            text = (vault / 'Now.md').read_text()
            assert 'Further explanation.' not in text and restored.session.get('learn_detail')
            assert 'Learning tutor paused' in text
            retry = restored.retry_skipped()
            assert retry['activity'] == 'questions'
            restored.answer(f"{retry['items'][0]['n']}A3")
            assert not prompts.skipped_guards(restored)
            await app.screen.learn_request('More detail').wait()
            assert 'Further explanation.' in (vault / 'Now.md').read_text()
            await app.ai.close()
    asyncio.run(run())


def test_ungraded_structured_retry_saves_work_without_showing_scheme(tmp_path, monkeypatch):
    app, vault = app_for(tmp_path, monkeypatch)
    async def run():
        async with app.run_test(size=(120, 40)) as pilot:
            app.push_screen(SessionScreen({'mode': 'test', 'minutes': 10, 'focus': ['9702-2.1']}))
            await pilot.pause()
            tutor = app.tutor
            tutor.session['presented'] = {}; tutor.session['queue'] = {}; tutor.session['mode'] = 'lesson'
            item = {'id': 'structured-retry', 'kcs': ['9702-2.1.1'], 'kind': 'structured', 'difficulty': 3,
                    'marks': 1, 'stem': 'Explain.', 'scheme': [{'mark': 'B1', 'point': 'PRIVATE SCHEME'}]}
            view = tutor._present(item, block='practice', phase='practice')
            tutor.answer(f"{view['n']}?")
            from tutorlib import deferred_notes
            deferred_notes.defer(tutor.vault.tutor / 'state' / 'deferred-notes.json', 'draft-test', '9702-2.1',
                                 {'kc': '9702-2.1.1', 'note': 'private'}, tutor.session['skipped_answer_guards'])
            retry = tutor.retry_skipped_ungraded()
            assert retry['activity'] == 'questions'
            app.screen.act = retry
            app.screen.ask_question(retry['items'][0], 'Your attempt will be saved without marking.')
            app.screen.long_written({'text': 'I drew a force diagram.'})
            assert tutor.session['deferred_judgments'][0]['saved_work'] == 'I drew a force diagram.'
            assert 'PRIVATE SCHEME' not in (vault / 'Now.md').read_text()
            assert not tutor.session['skipped_answer_guards']
            await app.ai.close()
    asyncio.run(run())


def test_cancel_ungraded_structured_retry_preserves_guard_and_draft(tmp_path, monkeypatch):
    app, _ = app_for(tmp_path, monkeypatch)
    async def run():
        async with app.run_test(size=(120, 40)) as pilot:
            app.push_screen(SessionScreen({'mode': 'test', 'minutes': 10, 'focus': ['9702-2.1']}))
            await pilot.pause()
            tutor = app.tutor
            tutor.session['presented'] = {}; tutor.session['queue'] = {}; tutor.session['mode'] = 'lesson'
            item = {'id': 'structured-cancel', 'kcs': ['9702-2.1.1'], 'kind': 'structured', 'difficulty': 3,
                    'marks': 1, 'stem': 'Explain.', 'scheme': [{'mark': 'B1', 'point': 'PRIVATE SCHEME'}]}
            view = tutor._present(item, block='practice', phase='practice')
            tutor.answer(f"{view['n']}?")
            retry = tutor.retry_skipped_ungraded()
            app.screen.act = retry
            app.screen.ask_question(retry['items'][0], 'Unmarked.')
            await pilot.pause()
            from textual.widgets import Button, TextArea
            app.screen.query_one('#long', TextArea).load_text('Partial working.')
            app.screen.query_one('#cancel-ungraded', Button).press()
            await pilot.pause()
            assert tutor.session['skipped_answer_guards'] and not tutor.session['presented']
            tutor.end()
            tutor.start('lesson', focus=['9702-2.1'])
            again = tutor.retry_skipped_ungraded()
            assert again['items'][0]['saved_work'] == 'Partial working.'
            await app.ai.close()
    asyncio.run(run())


def test_structured_retry_keeps_editor_after_save_failure(tmp_path, monkeypatch):
    from tutorlib import deferred_notes
    from textual.widgets import TextArea
    app, _ = app_for(tmp_path, monkeypatch)
    async def run():
        async with app.run_test(size=(100, 30)) as pilot:
            app.push_screen(SessionScreen({'mode': 'test', 'minutes': 10, 'focus': ['9702-2.1']}))
            await pilot.pause()
            tutor = app.tutor
            tutor.session['presented'] = {}; tutor.session['queue'] = {}; tutor.session['mode'] = 'lesson'
            item = {'id': 'structured-failure', 'kcs': ['9702-2.1.1'], 'kind': 'structured', 'difficulty': 3,
                    'marks': 1, 'stem': 'Explain.', 'scheme': [{'mark': 'B1', 'point': 'Private'}]}
            view = tutor._present(item, block='practice', phase='practice')
            tutor.answer(f"{view['n']}?")
            retry = tutor.retry_skipped_ungraded()
            app.screen.act = retry; app.screen.ask_question(retry['items'][0], 'Unmarked.')
            original = deferred_notes.resolve
            monkeypatch.setattr(deferred_notes, 'resolve', lambda *args: (_ for _ in ()).throw(OSError('interrupted')))
            app.screen.long_written({'text': 'My working.'})
            await pilot.pause()
            assert app.screen.query_one('#long', TextArea).text == 'My working.'
            monkeypatch.setattr(deferred_notes, 'resolve', original)
            app.screen.long_written({'text': 'My working.'})
            assert tutor.session['deferred_judgments'][0]['saved_work'] == 'My working.'
            assert len([e for e in tutor.vault.events() if e['type'] == 'ungraded_retry']) == 1
            await app.ai.close()
    asyncio.run(run())


def test_ungraded_structured_question_starts_in_view_at_narrow_size(tmp_path, monkeypatch):
    app, _ = app_for(tmp_path, monkeypatch)
    async def run():
        async with app.run_test(size=(60, 20)) as pilot:
            app.push_screen(SessionScreen({'mode': 'test', 'minutes': 10, 'focus': ['9702-2.1']}))
            await pilot.pause()
            tutor = app.tutor
            tutor.session['presented'] = {}; tutor.session['queue'] = {}; tutor.session['mode'] = 'lesson'
            item = {'id': 'structured-layout', 'kcs': ['9702-2.1.1'], 'kind': 'structured', 'difficulty': 3,
                    'marks': 1, 'stem': 'Explain how the forces balance on the object.',
                    'scheme': [{'mark': 'B1', 'point': 'Private'}]}
            view = tutor._present(item, block='practice', phase='practice')
            tutor.answer(f"{view['n']}?")
            retry = tutor.retry_skipped_ungraded()
            app.screen.act = retry
            app.screen.ask_question(retry['items'][0], 'Your attempt will be saved without marking. Prerequisite support is not shown.')
            await pilot.pause()
            log = app.screen.query_one('#log')
            question = next(w for w in log.query('.entry') if w.display)
            assert log.region.y <= question.region.y < log.region.bottom
            for name in ('#submit', '#cancel-ungraded'):
                button = app.screen.query_one(name)
                assert button.region.bottom <= app.size.height
            await app.ai.close()
    asyncio.run(run())


def test_long_question_header_signals_support_below(tmp_path, monkeypatch):
    import html
    import re
    app, _ = app_for(tmp_path, monkeypatch)
    async def run():
        async with app.run_test(size=(60, 20)) as pilot:
            app.push_screen(SessionScreen({'mode': 'test', 'minutes': 10, 'focus': ['9702-2.1']}))
            await pilot.pause()
            view = {'n': 1, 'kind': 'mcq', 'marks': 2, 'stem': 'Long question. ' * 80,
                    'options': {'A': 'First', 'B': 'Second'}, 'support': {'9702-3.1': 'Required fact.'}}
            app.screen.ask_question(view)
            await pilot.pause()
            visible = html.unescape(''.join(re.findall(r'>([^<>]*)</text>', app.export_screenshot()))).replace('\xa0', ' ')
            assert 'support below' in visible.lower()
            for _ in range(20):
                await pilot.press('alt+down')
            await pilot.pause()
            visible = html.unescape(''.join(re.findall(r'>([^<>]*)</text>', app.export_screenshot()))).replace('\xa0', ' ')
            assert 'Required fact.' in visible
            await app.ai.close()
    asyncio.run(run())


def test_learning_tutor_does_not_save_continuation_if_first_section_is_guarded(tmp_path, monkeypatch):
    app, _ = app_for(tmp_path, monkeypatch)
    kc = '9702-2.1.1'
    monkeypatch.setattr(learn_reply, 'published_related_cards', lambda tutor, current: {
        kc: {'plain_words': 'First section.', 'establish': 'Second section.'}})
    async def fake(prompt, **kwargs):
        return {'sections': [kc + '|plain_words', kc + '|establish']}, Result()
    async def run():
        async with app.run_test(size=(120, 40)) as pilot:
            monkeypatch.setattr(app.ai, 'one_shot', fake)
            monkeypatch.setattr(app, 'ai_available', lambda mode: True)
            app.push_screen(SessionScreen({'mode': 'test', 'minutes': 10, 'focus': ['9702-2.1']}))
            await pilot.pause()
            app.tutor.session['presented'] = {}; app.tutor.session['queue'] = {}
            app.screen.kc = kc
            monkeypatch.setattr(app.screen, 'learning_answer_is_guarded', lambda text: bool(text))
            await app.screen.learn_request('Explain this idea').wait()
            assert not app.tutor.session.get('learn_detail')
            await app.ai.close()
    asyncio.run(run())


def test_learning_tutor_withholds_incorrect_calculations(tmp_path, monkeypatch):
    app, vault = app_for(tmp_path, monkeypatch)
    monkeypatch.setattr(learn_reply, 'published_related_cards', lambda tutor, kc: {kc: {'plain_words': 'Look at the assumptions first.'}})
    async def fake(prompt, **kwargs):
        return {"blocks": [{"kind": "equality", "text": "", "left": "2+2", "right": "5"}]}, Result()
    async def run():
        async with app.run_test(size=(120, 40)) as pilot:
            monkeypatch.setattr(app.ai, "one_shot", fake)
            monkeypatch.setattr(app, "ai_available", lambda mode: True)
            app.push_screen(SessionScreen({"mode": "test", "minutes": 10, "focus": ["9702-2.1"]}))
            await pilot.pause()
            app.tutor.session["presented"] = {}
            app.tutor.session["queue"] = {}
            app.screen.kc = "9702-2.1.1"
            app.screen.learn_request("Explain")
            await pilot.pause(0.4)
            text = (vault / "Now.md").read_text()
            assert "2+2" not in text and "could not select" in text
            await app.ai.close()
    asyncio.run(run())


def test_learning_tutor_withholds_unrequested_model_prose(tmp_path, monkeypatch):
    app, vault = app_for(tmp_path, monkeypatch)
    monkeypatch.setattr(learn_reply, 'published_related_cards', lambda tutor, kc: {kc: {'plain_words': 'Safe card.'}})
    async def fake(prompt, **kwargs):
        return {'sections': ['9702-2.1.1|plain_words'], 'text': 'Every odd integer is prime.'}, Result()
    async def run():
        async with app.run_test(size=(120, 40)) as pilot:
            monkeypatch.setattr(app.ai, 'one_shot', fake)
            monkeypatch.setattr(app, 'ai_available', lambda mode: True)
            app.push_screen(SessionScreen({'mode': 'test', 'minutes': 10, 'focus': ['9702-2.1']}))
            await pilot.pause()
            app.tutor.session['presented'] = {}
            app.tutor.session['queue'] = {}
            app.screen.kc = '9702-2.1.1'
            app.screen.learn_request('Explain')
            await pilot.pause(0.4)
            text = (vault / 'Now.md').read_text()
            assert 'Every odd integer is prime.' not in text and 'could not select' in text
            await app.ai.close()
    asyncio.run(run())


def test_learning_tutor_never_calls_model_when_question_is_open(tmp_path, monkeypatch):
    app, _ = app_for(tmp_path, monkeypatch)
    monkeypatch.setattr(learn_reply, 'published_related_cards', lambda tutor, kc: {kc: {'plain_words': 'Start by identifying the domain.'}})
    calls = []
    async def fake(prompt, **kwargs):
        calls.append(prompt)
        return None, Result()
    async def run():
        async with app.run_test(size=(120, 40)) as pilot:
            monkeypatch.setattr(app.ai, "one_shot", fake)
            monkeypatch.setattr(app, "ai_available", lambda mode: True)
            app.push_screen(SessionScreen({"mode": "test", "minutes": 10, "focus": ["9702-2.1"]}))
            await pilot.pause()
            assert app.tutor.session["presented"]
            app.screen.kc = "9702-2.1.1"
            app.screen.learn_request("Give me the answer")
            await pilot.pause(0.3)
            assert not calls
            await app.ai.close()
    asyncio.run(run())


def test_learning_tutor_remembers_previous_exchange_in_same_idea(tmp_path, monkeypatch):
    app, _ = app_for(tmp_path, monkeypatch)
    monkeypatch.setattr(learn_reply, 'published_related_cards', lambda tutor, kc: {kc: {'plain_words': 'Start by identifying the domain.'}})
    prompts = []
    async def fake(prompt, **kwargs):
        prompts.append(prompt)
        return {'sections': ['9702-2.1.1|plain_words']}, Result()
    async def run():
        async with app.run_test(size=(120, 40)) as pilot:
            monkeypatch.setattr(app.ai, "one_shot", fake)
            monkeypatch.setattr(app, "ai_available", lambda mode: True)
            from tutor_app import prompts as tutor_prompts
            monkeypatch.setattr(tutor_prompts, 'learn', lambda *args: 'long context ' * 1000 +
                                ' reviewed: ✓ first point; ✗ second point' + '\n\nLESSON IDEA: profile marker')
            app.push_screen(SessionScreen({"mode": "test", "minutes": 10, "focus": ["9702-2.1"]}))
            await pilot.pause()
            app.tutor.session["presented"] = {}
            app.tutor.session["queue"] = {}
            app.screen.kc = "9702-2.1.1"
            app.screen.learn_request("What should I consider?")
            await pilot.pause(0.3)
            app.screen.learn_request("Why does that matter?")
            await pilot.pause(0.3)
            assert len(prompts) == 2
            assert "What should I consider?" in prompts[1]
            assert "Start by identifying the domain." in prompts[1]
            assert 'profile marker' in prompts[1]
            assert 'reviewed: ✓ first point; ✗ second point' in prompts[1]
            await app.ai.close()
    asyncio.run(run())


def test_learning_reply_is_discarded_if_a_question_opens_during_generation(tmp_path, monkeypatch):
    app, vault = app_for(tmp_path, monkeypatch)
    monkeypatch.setattr(learn_reply, 'published_related_cards', lambda tutor, kc: {kc: {'plain_words': 'STALE RESPONSE'}})
    async def run():
        started, finish = asyncio.Event(), asyncio.Event()
        async def fake(prompt, **kwargs):
            started.set()
            await finish.wait()
            return {'sections': ['9702-2.1.1|plain_words']}, Result()
        async with app.run_test(size=(120, 40)) as pilot:
            monkeypatch.setattr(app.ai, "one_shot", fake)
            monkeypatch.setattr(app, "ai_available", lambda mode: True)
            app.push_screen(SessionScreen({"mode": "test", "minutes": 10, "focus": ["9702-2.1"]}))
            await pilot.pause()
            saved = dict(app.tutor.session["presented"])
            app.tutor.session["presented"] = {}
            app.tutor.session["queue"] = {}
            app.screen.kc = "9702-2.1.1"
            screen = app.screen
            session_before, act_before, kc_before = app.tutor.session, screen.act, screen.kc
            history_before = deepcopy(session_before.get('learn_history', {}))
            events_before = list(app.tutor.vault.events())
            worker = screen.learn_request("Explain")
            await asyncio.wait_for(started.wait(), 2)
            app.tutor.session["presented"] = saved
            finish.set()
            await worker.wait()
            await pilot.pause()
            assert "STALE RESPONSE" not in (vault / "Now.md").read_text()
            assert app.tutor.session is session_before and screen.act is act_before and screen.kc == kc_before
            assert session_before.get('learn_history', {}) == history_before
            assert list(app.tutor.vault.events()) == events_before
            await app.ai.close()
    asyncio.run(run())


def test_learning_reply_is_discarded_after_question_boundary_even_if_closed(tmp_path, monkeypatch):
    app, vault = app_for(tmp_path, monkeypatch)
    monkeypatch.setattr(learn_reply, 'published_related_cards', lambda tutor, kc: {kc: {'plain_words': 'STALE RESPONSE'}})
    async def run():
        started, finish = asyncio.Event(), asyncio.Event()
        async def fake(prompt, **kwargs):
            started.set()
            await finish.wait()
            return {'sections': ['9702-2.1.1|plain_words']}, Result()
        async with app.run_test(size=(120, 40)) as pilot:
            monkeypatch.setattr(app.ai, "one_shot", fake)
            monkeypatch.setattr(app, "ai_available", lambda mode: True)
            app.push_screen(SessionScreen({"mode": "test", "minutes": 10, "focus": ["9702-2.1"]}))
            await pilot.pause()
            app.tutor.session["presented"] = {}
            app.tutor.session["queue"] = {}
            app.screen.kc = "9702-2.1.1"
            screen = app.screen
            session_before, act_before, kc_before = app.tutor.session, screen.act, screen.kc
            history_before = deepcopy(session_before.get('learn_history', {}))
            events_before = list(app.tutor.vault.events())
            worker = screen.learn_request("Explain")
            await asyncio.wait_for(started.wait(), 2)
            app.tutor.session["count"] += 1
            finish.set()
            await worker.wait()
            await pilot.pause()
            assert "STALE RESPONSE" not in (vault / "Now.md").read_text()
            assert app.tutor.session is session_before and screen.act is act_before and screen.kc == kc_before
            assert session_before.get('learn_history', {}) == history_before
            assert list(app.tutor.vault.events()) == events_before
            await app.ai.close()
    asyncio.run(run())


def test_learning_tutor_does_not_run_when_question_is_queued(tmp_path, monkeypatch):
    app, _ = app_for(tmp_path, monkeypatch)
    monkeypatch.setattr(learn_reply, 'published_related_cards', lambda tutor, kc: {kc: {'plain_words': 'Start by identifying the domain.'}})
    calls = []
    async def fake(prompt, **kwargs):
        calls.append(prompt)
        return None, Result()
    async def run():
        async with app.run_test(size=(120, 40)) as pilot:
            monkeypatch.setattr(app.ai, 'one_shot', fake)
            monkeypatch.setattr(app, 'ai_available', lambda mode: True)
            app.push_screen(SessionScreen({'mode': 'test', 'minutes': 10, 'focus': ['9702-2.1']}))
            await pilot.pause()
            app.tutor.session['presented'] = {}
            app.tutor.session['queue'] = {'99': {'item': 'unattempted'}}
            app.screen.kc = '9702-2.1.1'
            app.screen.learn_request('Explain')
            await pilot.pause(0.3)
            assert not calls
            await app.ai.close()
    asyncio.run(run())


def test_learning_reply_is_discarded_if_question_is_queued_during_generation(tmp_path, monkeypatch):
    app, vault = app_for(tmp_path, monkeypatch)
    monkeypatch.setattr(learn_reply, 'published_related_cards', lambda tutor, kc: {kc: {'plain_words': 'STALE RESPONSE'}})
    async def run():
        started, finish = asyncio.Event(), asyncio.Event()
        async def fake(prompt, **kwargs):
            started.set()
            await finish.wait()
            return {'sections': ['9702-2.1.1|plain_words']}, Result()
        async with app.run_test(size=(120, 40)) as pilot:
            monkeypatch.setattr(app.ai, 'one_shot', fake)
            monkeypatch.setattr(app, 'ai_available', lambda mode: True)
            app.push_screen(SessionScreen({'mode': 'test', 'minutes': 10, 'focus': ['9702-2.1']}))
            await pilot.pause()
            app.tutor.session['presented'] = {}
            app.tutor.session['queue'] = {}
            app.screen.kc = '9702-2.1.1'
            screen = app.screen
            session_before, act_before, kc_before = app.tutor.session, screen.act, screen.kc
            history_before = deepcopy(session_before.get('learn_history', {}))
            events_before = list(app.tutor.vault.events())
            worker = screen.learn_request('Explain')
            await asyncio.wait_for(started.wait(), 2)
            app.tutor.session['queue'] = {'99': {'item': 'unattempted'}}
            finish.set()
            await worker.wait()
            await pilot.pause()
            assert 'STALE RESPONSE' not in (vault / 'Now.md').read_text()
            assert app.tutor.session is session_before and screen.act is act_before and screen.kc == kc_before
            assert session_before.get('learn_history', {}) == history_before
            assert list(app.tutor.vault.events()) == events_before
            await app.ai.close()
    asyncio.run(run())


def test_skipped_term_recall_does_not_reveal_its_definition(tmp_path, monkeypatch):
    app, vault = app_for(tmp_path, monkeypatch)
    async def run():
        async with app.run_test(size=(100, 30)):
            tutor = app.tutor
            tutor.start('review', minutes=10)
            item = {'id': 'term-skip', 'term_id': 'term:skip', 'kcs': ['9702-2.1.1'],
                    'kind': 'short', 'difficulty': 2, 'marks': 1, 'stem': 'Define the term.',
                    'rubric': [{'point': 'PRIVATE DEFINITION', 'keywords': [['definition']]}]}
            view = tutor._present(item, block='practice', phase='term_review')
            result = tutor.answer(f"{view['n']}?")
            assert 'PRIVATE DEFINITION' not in str(result)
            assert 'PRIVATE DEFINITION' not in (vault / 'Now.md').read_text()
            event = [e for e in tutor.vault.events() if e['type'] == 'answer'][-1]
            assert 'PRIVATE DEFINITION' not in str(event.get('key'))
            assert 'PRIVATE DEFINITION' not in str(tutor.session['recent'])
    asyncio.run(run())


def test_local_term_mark_requires_confirmation_before_rescheduling(tmp_path, monkeypatch):
    app, vault = app_for(tmp_path, monkeypatch)
    point = 'A term means a result of multiplication.'
    async def examiner(*args, **kwargs):
        return {'points': [{'point': point, 'met': True}], 'feedback': 'Correct.'}, Result()
    async def run():
        async with app.run_test(size=(100, 30)) as pilot:
            tutor = app.tutor
            tutor.start('review', minutes=10)
            tutor.log({'type': 'term_introduced', 'term_id': 'term:product', 'kc': '9702-2.1.1'})
            item = {'id': 'term:product', 'term_id': 'term:product', 'kcs': ['9702-2.1.1'],
                    'kind': 'short', 'difficulty': 2, 'marks': 1, 'stem': 'What is product?',
                    'review_answer': point, 'rubric': [{'point': point, 'keywords': [['multiplication']]}]}
            view = tutor._present(item, block='term_review', phase='term_review')
            assert point not in str(view) and point not in (vault / 'Now.md').read_text()
            screen = SessionScreen(None)
            await app.push_screen(screen)
            await pilot.pause()
            monkeypatch.setattr(app, 'ai_available', lambda mode: True)
            monkeypatch.setattr(app.ai, 'one_shot', examiner)
            app.settings.ai_mark_model = 'ollama:gemma4:e4b'
            data = {'entry': f"{view['n']} = addition", 'your': 'addition'}
            screen.pending_short = (view['n'], data, 1)
            await screen.judge_short(view, data, {'rubric': [point]}).wait()
            await pilot.pause()
            assert tutor.state['terms']['term:product']['reviews'] == 0
            assert point in (vault / 'Now.md').read_text()
            assert screen.query_one('#panel > *', TickPanel)
            screen.long_marks({'ticked': []})
            assert tutor.state['terms']['term:product']['reviews'] == 1
            assert [e for e in tutor.vault.events() if e['type'] == 'answer'][-1]['grade']['score'] == 0
            await app.ai.close()
    asyncio.run(run())


def test_skipped_lesson_probe_does_not_reveal_its_key(tmp_path, monkeypatch):
    app, vault = app_for(tmp_path, monkeypatch)
    async def run():
        async with app.run_test(size=(100, 30)):
            tutor = app.tutor
            tutor.start('review', minutes=10)
            tutor.session['mode'] = 'lesson'
            item = {'id': 'lesson-probe-skip', 'kcs': ['9702-2.1.1'], 'kind': 'mcq',
                    'difficulty': 2, 'marks': 1, 'stem': 'Choose a label.',
                    'options': {'A': 'SOLUTION SECRET', 'B': 'Another label'}, 'answer': 'A',
                    'explanation': 'EXPLANATION SECRET'}
            tutor.session['blocks'] = [{'kind': 'sweep', 'asked': {}, 'res': {}}]
            view = tutor._present(item, block='sweep', phase='sweep', block_idx=0)
            result = tutor.answer(f"{view['n']}?")
            feedback = result['results'][0]
            assert feedback['answer'] == '' and feedback['explanation'] is None
            assert 'EXPLANATION SECRET' not in (vault / 'Now.md').read_text()
            event = [e for e in tutor.vault.events() if e['type'] == 'answer'][-1]
            assert event['key'] == ''
            assert tutor.session['recent'][-1]['answer'] == ''
    asyncio.run(run())


def test_skipped_lesson_probe_stays_hidden_when_answer_log_outlives_session_save(tmp_path, monkeypatch):
    from tutorlib import session, store
    app, vault = app_for(tmp_path, monkeypatch)
    async def run():
        async with app.run_test(size=(100, 30)):
            tutor = app.tutor
            tutor.start('review', minutes=10)
            tutor.session['mode'] = 'lesson'
            item = {'id': 'recover-skip', 'kcs': ['9702-2.1.1'], 'kind': 'mcq',
                    'difficulty': 2, 'marks': 1, 'stem': 'Choose a label.',
                    'options': {'A': 'First', 'B': 'Second'}, 'answer': 'A',
                    'explanation': 'PRIVATE EXPLANATION'}
            tutor.session['blocks'] = [{'kind': 'sweep', 'asked': {}, 'res': {}}]
            view = tutor._present(item, block='sweep', phase='sweep', block_idx=0)
            tutor._save()
            open_state = tutor.session_path.read_bytes()
            tutor.answer(f"{view['n']}?")
            tutor.session_path.write_bytes(open_state)  # interruption after the answer event was committed
            recovered = session.Tutor(store.Vault(vault))
            assert not recovered.session['presented']
            assert recovered.session['recent'][-1]['answer'] == ''
            assert 'PRIVATE EXPLANATION' not in str(recovered.session['thread'])
            assert 'PRIVATE EXPLANATION' not in (vault / 'Now.md').read_text()
    asyncio.run(run())


def test_skipped_past_paper_lesson_question_hides_examiner_explanation(tmp_path, monkeypatch):
    app, vault = app_for(tmp_path, monkeypatch)
    async def run():
        async with app.run_test(size=(100, 30)):
            tutor = app.tutor
            tutor.start('review', minutes=10)
            tutor.session['mode'] = 'lesson'
            item = {'id': 'past-skip', 'kcs': ['9702-2.1.1'], 'kind': 'mcq',
                    'difficulty': 2, 'marks': 1, 'stem': 'Choose a label.',
                    'options': {'A': 'First', 'B': 'Second'}, 'answer': 'A',
                    'tier': 'extra', 'examiner': 'PRIVATE EXAMINER ANSWER'}
            view = tutor._present(item, block='practice', phase='practice')
            result = tutor.answer(f"{view['n']}?")
            assert 'PRIVATE EXAMINER ANSWER' not in str(result)
            assert 'PRIVATE EXAMINER ANSWER' not in (vault / 'Now.md').read_text()
    asyncio.run(run())


def test_spoken_skipped_feedback_never_reads_answer_or_explanation():
    from tutor_app.screens import spoken_feedback
    feedback = {'answer_withheld': True, 'answer': 'PRIVATE ANSWER', 'detail': 'PRIVATE DETAIL',
                'explanation': 'PRIVATE EXPLANATION', 'misconception': {'statement': 'PRIVATE TRAP'}}
    spoken = spoken_feedback(feedback, '?', explanation='PRIVATE OVERRIDE')
    assert spoken == ['Skipped. The answer is withheld.']


def test_skipped_lesson_question_keeps_private_ai_guard_after_restart(tmp_path, monkeypatch):
    from tutorlib import session, store
    from tutor_app import ai, prompts
    app, vault = app_for(tmp_path, monkeypatch)
    async def run():
        async with app.run_test(size=(100, 30)):
            tutor = app.tutor
            tutor.start('review', minutes=10)
            tutor.session['mode'] = 'lesson'
            item = {'id': 'guarded-skip', 'kcs': ['9702-2.1.1'], 'kind': 'mcq',
                    'difficulty': 2, 'marks': 1, 'stem': 'Which one?',
                    'options': {'A': 'A lengthy correct option', 'B': 'A different option'}, 'answer': 'A'}
            view = tutor._present(item, block='practice', phase='practice')
            tutor.answer(f"{view['n']}?")
            guarded = prompts.guard_keys(tutor)
            assert len(guarded) == 1 and ai.leaks('The answer is A.', *guarded[0])
            assert 'the answer is A:' not in prompts.context(tutor)
            recovered = session.Tutor(store.Vault(vault))
            assert ai.leaks('The answer is A.', *prompts.guard_keys(recovered)[0])
            retry = recovered._present(item, block='practice', phase='practice')
            recovered.answer(f"{retry['n']}A3")
            assert prompts.guard_keys(recovered) == []
    asyncio.run(run())


def test_skipped_question_can_be_retried_after_restart_without_reinstantiation(tmp_path, monkeypatch):
    from tutorlib import session, store
    app, vault = app_for(tmp_path, monkeypatch)
    tutor = session.Tutor(store.Vault(vault))
    tutor.start('review', minutes=10)
    tutor.session['mode'] = 'lesson'
    item = {'id': 'retry-skip', 'kcs': ['9702-2.1.1'], 'kind': 'mcq', 'difficulty': 2,
            'marks': 1, 'stem': 'Which?', 'options': {'A': 'Correct', 'B': 'Wrong'}, 'answer': 'A'}
    first = tutor._present(item, block='practice', phase='practice')
    tutor.answer(f"{first['n']}?")
    recovered = session.Tutor(store.Vault(vault))
    activity = recovered.retry_skipped()
    assert activity['activity'] == 'questions'
    assert activity['items'][0]['stem'] == 'Which?'
    assert activity['items'][0]['options'] == item['options']
    assert recovered.session['skipped_answer_guards']
    number = activity['items'][0]['n']
    assert recovered.retry_skipped()['activity'] == 'error'
    recovered.session['mode'] = 'review'
    again = recovered.answer(f'{number}?')
    assert 'Correct' not in str(again)
    assert recovered.session['skipped_answer_guards']
    activity = recovered.retry_skipped()
    recovered.answer(f"{activity['items'][0]['n']}A3")
    assert not recovered.session['skipped_answer_guards']


def test_retry_guided_check_keeps_review_phase_without_mutating_old_block(tmp_path, monkeypatch):
    from tutorlib import session, store
    app, vault = app_for(tmp_path, monkeypatch)
    tutor = session.Tutor(store.Vault(vault))
    tutor.start('review', minutes=10)
    tutor.session['mode'] = 'lesson'
    item = {'id': 'guided-retry', 'kcs': ['9702-2.1.1'], 'kind': 'short', 'difficulty': 2,
            'marks': 1, 'stem': 'Explain why.', 'review_answer': 'A reviewed answer.',
            'rubric': [{'point': 'A reviewed point.', 'keywords': [['point']]}]}
    first = tutor._present(item, block='practice', phase='form_check')
    tutor.answer(f"{first['n']}?")
    retry = tutor.retry_skipped()
    p = tutor.session['presented'][str(retry['items'][0]['n'])]
    assert p['phase'] == 'form_check'
    assert p['block'] == 'skipped_retry' and p['block_idx'] is None
    assert p['inst']['review_answer'] == 'A reviewed answer.'


def test_retry_skipped_preserves_interrupted_lesson_step(tmp_path, monkeypatch):
    from tutorlib import session, store
    app, vault = app_for(tmp_path, monkeypatch)
    tutor = session.Tutor(store.Vault(vault))
    tutor.start('review', minutes=10)
    tutor.session['mode'] = 'lesson'
    item = {'id': 'later-retry', 'kcs': ['9702-2.1.1'], 'kind': 'mcq', 'difficulty': 2,
            'marks': 1, 'stem': 'Which?', 'options': {'A': 'Correct', 'B': 'Wrong'}, 'answer': 'A'}
    first = tutor._present(item, block='practice', phase='practice')
    tutor.answer(f"{first['n']}?")
    waiting = {'activity': 'explain', 'text': 'Lesson step to resume', 'block_idx': None}
    tutor.session['awaiting'] = waiting
    retry = tutor.retry_skipped()
    assert retry['activity'] == 'questions'
    assert tutor.session['awaiting'] == waiting
    tutor = session.Tutor(store.Vault(vault))
    assert tutor.next()['activity'] == 'awaiting'
    tutor.answer(f"{retry['items'][0]['n']}A3")
    assert tutor.next() == waiting
    assert 'Lesson step to resume' in (vault / 'Now.md').read_text()


def test_skipped_feedback_offers_retry_and_resumes_lesson(tmp_path, monkeypatch):
    app, vault = app_for(tmp_path, monkeypatch)
    async def run():
        async with app.run_test(size=(100, 30)) as pilot:
            screen = SessionScreen({'mode': 'autopilot', 'minutes': 50})
            await app.push_screen(screen)
            await pilot.pause()
            tutor = app.tutor
            tutor.session['presented'] = {}
            tutor.session['queue'] = {}
            tutor.session.pop('awaiting', None)
            tutor.session['mode'] = 'lesson'
            item = {'id': 'screen-retry', 'kcs': ['9702-2.1.1'], 'kind': 'mcq', 'difficulty': 2,
                    'marks': 1, 'stem': 'Which?', 'options': {'A': 'Correct', 'B': 'Wrong'}, 'answer': 'A'}
            view = tutor._present(item, block='practice', phase='practice')
            result = tutor.answer(f"{view['n']}?")
            screen.last_fb = result['results'][0]
            screen.next_followup()
            await pilot.pause()
            assert screen.query('#retry-skipped')
            await pilot.click('#retry-skipped')
            await pilot.pause()
            assert screen.act['activity'] == 'questions'
            assert screen.view['stem'] == 'Which?'
            retry = screen.view['n']
            tutor.answer(f'{retry}A3')
            assert not tutor.session['skipped_answer_guards']
            await app.ai.close()
    asyncio.run(run())


def test_retry_shortcut_resumes_interrupted_step_after_feedback(tmp_path, monkeypatch):
    app, vault = app_for(tmp_path, monkeypatch)
    async def run():
        async with app.run_test(size=(100, 30)) as pilot:
            screen = SessionScreen({'mode': 'autopilot', 'minutes': 50})
            await app.push_screen(screen)
            await pilot.pause()
            tutor = app.tutor
            tutor.session['presented'] = {}
            tutor.session['queue'] = {}
            tutor.session['mode'] = 'lesson'
            item = {'id': 'screen-later-retry', 'kcs': ['9702-2.1.1'], 'kind': 'mcq', 'difficulty': 2,
                    'marks': 1, 'stem': 'Which?', 'options': {'A': 'Correct', 'B': 'Wrong'}, 'answer': 'A'}
            view = tutor._present(item, block='practice', phase='practice')
            tutor.answer(f"{view['n']}?")
            tutor.session['awaiting'] = {'activity': 'explain', 'text': 'Lesson step to resume', 'block_idx': None}
            await pilot.press('ctrl+u')
            await pilot.pause()
            n = screen.view['n']
            screen.submit({'entry': f'{n}A3', 'your': 'A'})
            await pilot.pause()
            await pilot.click('#next')
            await pilot.pause()
            assert screen.act['text'] == 'Lesson step to resume'
            assert tutor.session['awaiting']['text'] == 'Lesson step to resume'
            await app.ai.close()
    asyncio.run(run())


def test_ai_stream_withholds_skipped_answer_and_spoken_copy(tmp_path, monkeypatch):
    app, vault = app_for(tmp_path, monkeypatch)
    leak = 'The answer is A.'
    async def stream(*args, **kwargs):
        app.ai.last = Result(text='A helpful thought.', speech=leak)
        yield 'A helpful thought.'
    async def run():
        async with app.run_test(size=(100, 30)) as pilot:
            screen = SessionScreen({'mode': 'autopilot', 'minutes': 50})
            await app.push_screen(screen)
            await pilot.pause()
            tutor = app.tutor
            tutor.session['presented'] = {}
            tutor.session['queue'] = {}
            tutor.session['mode'] = 'lesson'
            item = {'id': 'stream-guard', 'kcs': ['9702-2.1.1'], 'kind': 'mcq',
                    'difficulty': 2, 'marks': 1, 'stem': 'Which?',
                    'options': {'A': 'A long correct choice', 'B': 'Another choice'}, 'answer': 'A'}
            view = tutor._present(item, block='practice', phase='practice')
            tutor.answer(f"{view['n']}?")
            monkeypatch.setattr(app.ai, 'stream', stream)
            spoken = []
            monkeypatch.setattr(screen, 'readable_now', lambda value, **kwargs: spoken.append(value))
            await screen._stream('Explain the idea', False).wait()
            await pilot.pause()
            assert leak not in (vault / 'Now.md').read_text()
            assert 'skipped question' in (vault / 'Now.md').read_text()
            assert all(leak not in str(value) for value in spoken)
            await app.ai.close()
    asyncio.run(run())


def test_ai_stream_withholds_semantic_paraphrase_after_skip(tmp_path, monkeypatch):
    app, vault = app_for(tmp_path, monkeypatch)
    reply = 'An even integer is divisible by two.'
    async def stream(*args, **kwargs):
        app.ai.last = Result(text=reply, speech=reply)
        yield reply
    async def run():
        async with app.run_test(size=(100, 30)) as pilot:
            screen = SessionScreen({'mode': 'autopilot', 'minutes': 50})
            await app.push_screen(screen)
            await pilot.pause()
            app.tutor.session['presented'] = {}
            app.tutor.session['queue'] = {}
            app.tutor.session['skipped_answer_guards'] = {'previous': {'kind': 'short', 'key': 'a multiple of 2'}}
            monkeypatch.setattr(app.ai, 'stream', stream)
            spoken = []
            monkeypatch.setattr(screen, 'readable_now', lambda value, **kwargs: spoken.append(value))
            await screen._stream('Explain the idea', False).wait()
            assert reply not in (vault / 'Now.md').read_text()
            assert all(reply not in str(value) for value in spoken)
            await app.ai.close()
    asyncio.run(run())


def test_standalone_chat_withholds_reply_for_persisted_skipped_question(tmp_path, monkeypatch):
    from tutor_app.screens import ChatScreen
    app, vault = app_for(tmp_path, monkeypatch)
    calls = []
    async def stream(*args, **kwargs):
        calls.append(True)
        app.ai.last = Result(text='A paraphrased answer.', speech='A paraphrased answer.')
        yield 'A paraphrased answer.'
    async def run():
        async with app.run_test(size=(100, 30)) as pilot:
            tutor = app.tutor
            tutor.start('lesson', focus=['9702-2.1'])
            item = {'id': 'chat-skip', 'kcs': ['9702-2.1.1'], 'kind': 'mcq', 'difficulty': 2,
                    'marks': 1, 'stem': 'Which?', 'options': {'A': 'Secret', 'B': 'Other'}, 'answer': 'A'}
            view = tutor._present(item, block='practice', phase='practice')
            tutor.answer(f"{view['n']}?")
            tutor.end()
            monkeypatch.setattr(app, 'ai_available', lambda mode: True)
            monkeypatch.setattr(app.ai, 'stream', stream)
            screen = ChatScreen()
            await app.push_screen(screen)
            await pilot.pause()
            await screen.reply('Explain').wait()
            content = (vault / 'Now.md').read_text()
            assert 'A paraphrased answer.' not in content
            assert 'skipped question' in content and 'ctrl+u' in content
            assert calls == []
            tutor.start('lesson', focus=['9702-2.1'])
            retry = tutor.retry_skipped()
            tutor.answer(f"{retry['items'][0]['n']}A3")
            tutor.end()
            await screen.reply('Explain again').wait()
            assert 'A paraphrased answer.' in (vault / 'Now.md').read_text()
            assert calls == [True]
            await app.ai.close()
    asyncio.run(run())


def test_excluded_saved_judgment_requires_explicit_restore(tmp_path, monkeypatch):
    from textual.widgets import Button
    app, _ = app_for(tmp_path, monkeypatch)
    async def run():
        async with app.run_test(size=(100, 30)) as pilot:
            app.push_screen(SessionScreen({'mode': 'lesson', 'minutes': 10, 'focus': ['9702-2.1']}))
            await pilot.pause()
            screen, tutor = app.screen, app.tutor
            tutor.session['presented'] = {}
            tutor.session['queue'] = {}
            tutor.session['awaiting'] = None
            item = {'id': 'excluded-saved-ui', 'kcs': ['9702-2.1.1'], 'kind': 'short', 'difficulty': 2,
                    'marks': 1, 'stem': 'Explain.', 'rubric': [{'point': 'Point', 'keywords': [['point']]}]}
            _, p = tutor._number(item, 'deferred_judgment', 'practice')
            p['saved_work'] = 'My saved attempt'
            tutor.session['deferred_judgments'] = [p]
            tutor.log({'type': 'topical_exclude', 'identity': item['id'], 'chapter': '9702-2.1',
                       'reason': 'test', 'missing': []})
            screen.advance()
            await pilot.pause()
            screen.query_one('#restore-saved-judgment', Button).press()
            await pilot.pause()
            await pilot.press('down', 'enter')
            await pilot.pause()
            assert tutor.topical_exclusions()
            screen.query_one('#restore-saved-judgment', Button).press()
            await pilot.pause()
            await pilot.press('enter')
            await pilot.pause()
            assert not tutor.topical_exclusions()
            assert screen.view['saved_work'] == 'My saved attempt'
            await app.ai.close()
    asyncio.run(run())


def test_saved_attempts_screen_shows_work_without_private_marking_data(tmp_path, monkeypatch):
    from textual.widgets import Static
    app, _ = app_for(tmp_path, monkeypatch)
    async def run():
        async with app.run_test(size=(100, 30)) as pilot:
            tutor = app.tutor
            tutor.start('lesson', focus=['9702-2.1'])
            item = {'id': 'saved-image-ui', 'kcs': ['9702-2.1.1'], 'kind': 'short', 'difficulty': 2,
                    'marks': 1, 'stem': 'My question', 'image': 'Assets/old.png',
                    'rubric': [{'point': 'PRIVATE RUBRIC', 'keywords': [['private']]}]}
            _, p = tutor._number(item, 'deferred_judgment', 'practice')
            p['saved_work'] = 'My saved working'
            tutor.session['deferred_judgments'] = [p]
            assert tutor.postpone_saved_judgment()['ok']
            tutor.end()
            home = app.screen
            home._start('saved-attempts')
            await pilot.pause()
            assert app.screen.__class__.__name__ == 'SavedAttemptsScreen'
            rendered = '\n'.join(str(w.render()) for w in app.screen.query(Static))
            assert 'My saved working' in rendered and 'PRIVATE RUBRIC' not in rendered
            assert 'image' in rendered.lower() and 'review' in rendered.lower()
            app.save_screenshot(path='/tmp', filename='saved-attempts-screen.svg')
            await app.ai.close()
    asyncio.run(run())


def test_saved_attempts_are_not_shown_while_skipped_answer_is_protected(tmp_path, monkeypatch):
    from tutorlib import deferred_notes
    app, vault = app_for(tmp_path, monkeypatch)
    async def run():
        async with app.run_test(size=(100, 30)) as pilot:
            deferred_notes.hold(vault / '.tutor/state/deferred-notes.json', 'guard',
                                {'kind': 'short', 'key': 'Secret'})
            app.screen._start('saved-attempts')
            await pilot.pause()
            assert app.screen.__class__.__name__ == 'HomeScreen'
            await app.ai.close()
    asyncio.run(run())


def test_unavailable_saved_judgment_can_be_postponed_in_ui(tmp_path, monkeypatch):
    from textual.widgets import Button
    app, _ = app_for(tmp_path, monkeypatch)
    async def run():
        async with app.run_test(size=(100, 30)) as pilot:
            app.push_screen(SessionScreen({'mode': 'lesson', 'minutes': 10, 'focus': ['9702-2.1']}))
            await pilot.pause()
            screen, tutor = app.screen, app.tutor
            tutor.session['presented'] = {}
            tutor.session['queue'] = {}
            tutor.session['awaiting'] = None
            item = {'id': 'postpone-saved-ui', 'kcs': ['9702-2.1.1'], 'kind': 'short', 'difficulty': 2,
                    'marks': 1, 'stem': 'Explain.', 'rubric': [{'point': 'Point', 'keywords': [['point']]}]}
            _, p = tutor._number(item, 'deferred_judgment', 'practice')
            p['saved_work'] = 'My saved attempt'
            tutor.session['deferred_judgments'] = [p]
            tutor.log({'type': 'topical_exclude', 'identity': item['id'], 'chapter': '9702-2.1',
                       'reason': 'test', 'missing': []})
            screen.advance()
            await pilot.pause()
            screen.query_one('#postpone-saved-judgment', Button).press()
            await pilot.pause()
            assert not tutor.session.get('deferred_judgments')
            assert tutor.postponed_judgments()[0]['saved_work'] == 'My saved attempt'
            await app.ai.close()
    asyncio.run(run())


def test_retry_excluded_question_requires_explicit_restore(tmp_path, monkeypatch):
    app, _ = app_for(tmp_path, monkeypatch)
    async def run():
        async with app.run_test(size=(100, 30)) as pilot:
            app.push_screen(SessionScreen({'mode': 'lesson', 'minutes': 10, 'focus': ['9702-2.1']}))
            await pilot.pause()
            tutor = app.tutor
            tutor.session['presented'] = {}
            tutor.session['queue'] = {}
            item = {'id': 'excluded-retry-ui', 'kcs': ['9702-2.1.1'], 'kind': 'mcq', 'difficulty': 2,
                    'marks': 1, 'stem': 'Which?', 'options': {'A': 'Secret', 'B': 'Other'}, 'answer': 'A'}
            shown = tutor._present(item, block='practice', phase='practice')
            tutor.answer(f"{shown['n']}?")
            tutor.log({'type': 'topical_exclude', 'identity': item['id'], 'chapter': '9702-2.1',
                       'reason': 'test', 'missing': []})
            screen = app.screen
            screen.action_retry_skipped()
            await pilot.pause()
            assert app.screen.__class__.__name__ == 'ConfirmScreen'
            await pilot.press('down', 'enter')
            await pilot.pause()
            assert tutor.topical_exclusions()
            screen.action_retry_skipped()
            await pilot.pause()
            await pilot.press('enter')
            await pilot.pause()
            assert not tutor.topical_exclusions()
            assert screen.view['stem'] == 'Which?'
            await app.ai.close()
    asyncio.run(run())


def test_learning_request_withholds_paraphrase_for_guard_from_an_earlier_session(tmp_path, monkeypatch):
    from tutorlib import deferred_notes
    app, vault = app_for(tmp_path, monkeypatch)
    path = vault / '.tutor' / 'state' / 'deferred-notes.json'
    deferred_notes.hold(path, 'earlier', {'kind': 'short', 'key': 'a multiple of 2'})
    card = {'plain_words': 'An even integer is divisible by two.'}
    monkeypatch.setattr(learn_reply, 'published_related_cards', lambda tutor, kc: {kc: card})
    calls = []
    async def select(*args, **kwargs):
        calls.append(True)
        return {'sections': ['9702-2.1.1|plain_words']}, Result()
    async def run():
        async with app.run_test(size=(100, 30)) as pilot:
            monkeypatch.setattr(app, 'ai_available', lambda mode: True)
            monkeypatch.setattr(app.ai, 'one_shot', select)
            app.push_screen(SessionScreen({'mode': 'test', 'minutes': 10, 'focus': ['9702-2.1']}))
            await pilot.pause()
            app.tutor.session['presented'] = {}
            app.tutor.session['queue'] = {}
            app.screen.kc = '9702-2.1.1'
            await app.screen.learn_request('Explain this idea').wait()
            assert 'divisible by two' not in (vault / 'Now.md').read_text()
            assert calls == []
            await app.ai.close()
    asyncio.run(run())


def test_learning_card_selection_does_not_repeat_skipped_answer(tmp_path, monkeypatch):
    app, vault = app_for(tmp_path, monkeypatch)
    card = {'plain_words': 'The answer is A.'}
    monkeypatch.setattr(learn_reply, 'published_related_cards', lambda tutor, kc: {kc: card})
    async def select(*args, **kwargs):
        return {'sections': ['9702-2.1.1|plain_words']}, Result()
    async def run():
        async with app.run_test(size=(100, 30)) as pilot:
            screen = SessionScreen({'mode': 'test', 'minutes': 10, 'focus': ['9702-2.1']})
            app.push_screen(screen)
            await pilot.pause()
            tutor = app.tutor
            tutor.session['presented'] = {}
            tutor.session['queue'] = {}
            tutor.session['mode'] = 'lesson'
            item = {'id': 'learn-guard', 'kcs': ['9702-2.1.1'], 'kind': 'mcq', 'difficulty': 2,
                    'marks': 1, 'stem': 'Which?', 'options': {'A': 'A long correct choice', 'B': 'Another'}, 'answer': 'A'}
            view = tutor._present(item, block='practice', phase='practice')
            tutor.answer(f"{view['n']}?")
            screen.kc = '9702-2.1.1'
            monkeypatch.setattr(app, 'ai_available', lambda mode: True)
            monkeypatch.setattr(app.ai, 'one_shot', select)
            await screen.learn_request('Explain').wait()
            await pilot.pause()
            assert 'The answer is A.' not in (vault / 'Now.md').read_text()
            assert 'skipped question' in (vault / 'Now.md').read_text()
            await app.ai.close()
    asyncio.run(run())


def test_learning_tutor_withholds_paraphrased_skipped_answer(tmp_path, monkeypatch):
    app, vault = app_for(tmp_path, monkeypatch)
    card = {'plain_words': 'An even integer is divisible by two.'}
    monkeypatch.setattr(learn_reply, 'published_related_cards', lambda tutor, kc: {kc: card})
    async def run():
        async with app.run_test(size=(120, 40)) as pilot:
            monkeypatch.setattr(app, 'ai_available', lambda mode: True)
            app.push_screen(SessionScreen({'mode': 'test', 'minutes': 10, 'focus': ['9702-2.1']}))
            await pilot.pause()
            app.tutor.session['presented'] = {}
            app.tutor.session['queue'] = {}
            app.tutor.session['skipped_answer_guards'] = {'previous': {'kind': 'short', 'key': 'a multiple of 2'}}
            app.screen.kc = '9702-2.1.1'
            assert app.screen.learning_answer_is_guarded(card['plain_words'])
            assert 'divisible by two' not in (vault / 'Now.md').read_text()
            await app.ai.close()
    asyncio.run(run())


def test_attempting_a_different_generated_version_keeps_skipped_guard(tmp_path, monkeypatch):
    from tutor_app import prompts, ai
    app, _ = app_for(tmp_path, monkeypatch)
    async def run():
        async with app.run_test(size=(100, 30)):
            tutor = app.tutor
            tutor.start('review', minutes=10)
            tutor.session['mode'] = 'lesson'
            item = {'id': 'template-version', 'kcs': ['9702-2.1.1'], 'kind': 'numeric',
                    'difficulty': 2, 'marks': 1, 'stem': 'Find the value.', 'answer': {'value': 14, 'unit': ''}}
            first = tutor._present(item, block='practice', phase='practice')
            tutor.answer(f"{first['n']}?")
            other = dict(item, answer={'value': 17, 'unit': ''})
            second = tutor._present(other, block='practice', phase='practice')
            tutor.answer(f"{second['n']}?")
            assert len(prompts.guard_keys(tutor)) == 2
            retry = tutor._present(other, block='practice', phase='practice')
            tutor.answer(f"{retry['n']} = 17")
            assert len(prompts.guard_keys(tutor)) == 1
            assert any(ai.leaks('The answer is 14.', *key) for key in prompts.guard_keys(tutor))
    asyncio.run(run())


def test_skipped_form_guards_its_example_answer_as_well_as_rubric(tmp_path, monkeypatch):
    from tutor_app import prompts, ai
    app, _ = app_for(tmp_path, monkeypatch)
    async def run():
        async with app.run_test(size=(100, 30)):
            tutor = app.tutor
            tutor.start('review', minutes=10)
            item = {'id': 'form-guard', 'kcs': ['9702-2.1.1'], 'kind': 'short', 'difficulty': 2,
                    'marks': 1, 'stem': 'Explain.', 'review_answer': 'A distinctive full example answer.',
                    'rubric': [{'point': 'An independently phrased mark point.', 'keywords': [['point']]}]}
            view = tutor._present(item, block='practice', phase='form_check')
            tutor.answer(f"{view['n']}?")
            guards = prompts.guard_keys(tutor)
            assert any(ai.leaks('A distinctive full example answer.', *key) for key in guards)
            assert any(ai.leaks('An independently phrased mark point.', *key) for key in guards)
    asyncio.run(run())


def test_external_explanation_cannot_override_skipped_answer_guard(tmp_path, monkeypatch):
    app, vault = app_for(tmp_path, monkeypatch)
    async def run():
        async with app.run_test(size=(100, 30)):
            tutor = app.tutor
            tutor.start('review', minutes=10)
            item = {'id': 'skip-explanation', 'kcs': ['9702-2.1.1'], 'kind': 'short',
                    'difficulty': 2, 'marks': 1, 'stem': 'Explain.',
                    'rubric': [{'point': 'PRIVATE KEY', 'keywords': [['key']]}]}
            view = tutor._present(item, block='practice', phase='form_check')
            result = tutor.answer(f"{view['n']}?", explanation={view['n']: 'PRIVATE OVERRIDE'})
            assert result['results'][0]['explanation'] is None
            assert 'PRIVATE OVERRIDE' not in (vault / 'Now.md').read_text()
            assert 'PRIVATE OVERRIDE' not in str(tutor.session['recent'])
    asyncio.run(run())


def test_marking_override_cannot_award_credit_for_skipped_guided_check(tmp_path, monkeypatch):
    app, _ = app_for(tmp_path, monkeypatch)
    async def run():
        async with app.run_test(size=(100, 30)):
            tutor = app.tutor
            tutor.start('review', minutes=10)
            item = {'id': 'skip-with-score', 'kcs': ['9702-2.1.1'], 'kind': 'short',
                    'difficulty': 2, 'marks': 1, 'stem': 'Explain.',
                    'rubric': [{'point': 'A private point.', 'keywords': [['point']]}]}
            view = tutor._present(item, block='practice', phase='form_check')
            result = tutor.answer(f"{view['n']}?", judge={view['n']: 1})
            assert not result['results'][0]['correct'] and result['results'][0]['score'] == 0
            event = [e for e in tutor.vault.events() if e['type'] == 'answer'][-1]
            assert not event['grade']['correct'] and event['grade']['score'] == 0
    asyncio.run(run())


def test_skipped_guarded_question_cannot_be_remarked_correct(tmp_path, monkeypatch):
    app, _ = app_for(tmp_path, monkeypatch)
    async def run():
        async with app.run_test(size=(100, 30)):
            tutor = app.tutor
            tutor.start('review', minutes=10)
            item = {'id': 'skip-remark', 'kcs': ['9702-2.1.1'], 'kind': 'short',
                    'difficulty': 2, 'marks': 1, 'stem': 'Explain.',
                    'rubric': [{'point': 'A private point.', 'keywords': [['point']]}]}
            view = tutor._present(item, block='practice', phase='form_check')
            result = tutor.answer(f"{view['n']}?")['results'][0]
            remark = tutor.regrade(result['event'], 'No attempt was supplied.')
            assert not remark['ok']
            assert not any(e['type'] == 'regrade' for e in tutor.vault.events())
    asyncio.run(run())


def test_skipped_short_numeric_answer_is_protected(tmp_path, monkeypatch):
    from tutor_app import prompts, ai
    app, _ = app_for(tmp_path, monkeypatch)
    async def run():
        async with app.run_test(size=(100, 30)):
            tutor = app.tutor
            tutor.start('review', minutes=10)
            item = {'id': 'short-number', 'kcs': ['9702-2.1.1'], 'kind': 'short', 'difficulty': 2,
                    'marks': 1, 'stem': 'State the value.', 'review_answer': '2',
                    'rubric': [{'point': '2', 'keywords': [['2']]}]}
            view = tutor._present(item, block='practice', phase='form_check')
            tutor.answer(f"{view['n']}?")
            assert any(ai.leaks('The answer is 2.', *key) for key in prompts.guard_keys(tutor))
    asyncio.run(run())


def test_local_prime_mark_review_shows_verified_domain_warning(tmp_path, monkeypatch):
    app, vault = app_for(tmp_path, monkeypatch)
    point = 'Gives consecutive primes.'
    async def examiner(*args, **kwargs):
        return {'points': [{'point': point, 'met': True}], 'feedback': 'Correct.'}, Result()
    async def run():
        async with app.run_test(size=(100, 30)) as pilot:
            tutor = app.tutor
            tutor.start('review', minutes=10)
            item = {'id': 'prime-review', 'kcs': ['9702-2.1.1'], 'kind': 'short', 'difficulty': 2,
                    'marks': 1, 'stem': 'Give a triple.', 'review_rule': 'consecutive_primes',
                    'review_answer': 'A worked example.', 'rubric': [{'point': point, 'keywords': [['prime']]}]}
            view = tutor._present(item, block='practice', phase='form_check')
            screen = SessionScreen(None)
            await app.push_screen(screen)
            await pilot.pause()
            monkeypatch.setattr(app, 'ai_available', lambda mode: True)
            monkeypatch.setattr(app.ai, 'one_shot', examiner)
            app.settings.ai_mark_model = 'ollama:gemma4:e4b'
            data = {'entry': f"{view['n']} = primes 1, 2 and 3", 'your': 'primes 1, 2 and 3'}
            screen.pending_short = (view['n'], data, 1)
            await screen.judge_short(view, data, {'rubric': [point]}).wait()
            await pilot.pause()
            assert 'not three consecutive primes' in (vault / 'Now.md').read_text()
            assert not [event for event in tutor.vault.events() if event['type'] == 'answer']
            await app.ai.close()
    asyncio.run(run())


@pytest.mark.parametrize('working,expected', [('S-rS=ar^n-a', 'check the sign'),
                                               ('rS-S=ar^n-a', 'subtraction order is valid')])
def test_geometric_subtraction_note_is_shown_before_local_marks(tmp_path, monkeypatch, working, expected):
    app, vault = app_for(tmp_path, monkeypatch)
    point = 'Show a consistent subtraction.'
    async def examiner(*args, **kwargs):
        return {'points': [{'point': point, 'met': False}], 'feedback': 'Review.'}, Result()
    async def run():
        async with app.run_test(size=(100, 30)) as pilot:
            tutor = app.tutor
            tutor.start('review', minutes=10)
            item = {'id': 'geometric-review', 'kcs': ['9702-2.1.1'], 'kind': 'short', 'difficulty': 2,
                    'marks': 1, 'stem': 'Show the proof.', 'review_rule': 'geometric_subtraction',
                    'review_answer': 'An example.', 'rubric': [{'point': point, 'keywords': [['subtract']]}]}
            view = tutor._present(item, block='practice', phase='form_check')
            screen = SessionScreen(None)
            await app.push_screen(screen)
            await pilot.pause()
            monkeypatch.setattr(app, 'ai_available', lambda mode: True)
            monkeypatch.setattr(app.ai, 'one_shot', examiner)
            app.settings.ai_mark_model = 'ollama:gemma4:e4b'
            data = {'entry': f"{view['n']} = {working}", 'your': working}
            screen.pending_short = (view['n'], data, 1)
            await screen.judge_short(view, data, {'rubric': [point]}).wait()
            assert expected in (vault / 'Now.md').read_text().lower()
            assert not [event for event in tutor.vault.events() if event['type'] == 'answer']
            await app.ai.close()
    asyncio.run(run())


def test_prime_domain_warning_is_available_when_ai_marking_is_off(tmp_path, monkeypatch):
    app, vault = app_for(tmp_path, monkeypatch)
    point = 'Gives consecutive primes.'
    async def run():
        async with app.run_test(size=(100, 30)) as pilot:
            tutor = app.tutor
            tutor.start('review', minutes=10)
            item = {'id': 'prime-self-mark', 'kcs': ['9702-2.1.1'], 'kind': 'short', 'difficulty': 2,
                    'marks': 1, 'stem': 'Give a triple.', 'review_rule': 'consecutive_primes',
                    'review_answer': 'A worked example.', 'rubric': [{'point': point, 'keywords': [['prime']]}]}
            view = tutor._present(item, block='practice', phase='form_check')
            screen = SessionScreen(None)
            await app.push_screen(screen)
            await pilot.pause()
            monkeypatch.setattr(app, 'ai_available', lambda mode: False)
            data = {'entry': f"{view['n']} = primes 1, 2 and 3", 'your': 'primes 1, 2 and 3'}
            screen.pending_short = (view['n'], data, 1)
            await screen.judge_short(view, data, {'rubric': [point]}).wait()
            await pilot.pause()
            assert 'not three consecutive primes' in (vault / 'Now.md').read_text()
            assert not [event for event in tutor.vault.events() if event['type'] == 'answer']
            await app.ai.close()
    asyncio.run(run())


def test_guard_pause_hides_diagram_and_retry_resumes_node(tmp_path, monkeypatch):
    app, vault = app_for(tmp_path, monkeypatch)
    async def run():
        async with app.run_test(size=(100, 30)) as pilot:
            screen = SessionScreen({'mode': 'autopilot', 'minutes': 50})
            await app.push_screen(screen)
            await pilot.pause()
            tutor = app.tutor
            tutor.session['presented'] = {}
            tutor.session['queue'] = {}
            tutor.session.pop('awaiting', None)
            tutor.session['mode'] = 'lesson'
            item = {'id': 'screen-pause', 'kcs': ['9702-2.1.1'], 'kind': 'mcq', 'difficulty': 2,
                    'marks': 1, 'stem': 'Which?', 'options': {'A': 'Secret', 'B': 'Other'}, 'answer': 'A'}
            shown = tutor._present(item, block='practice', phase='practice')
            tutor.answer(f"{shown['n']}?")
            block = {'kind': 'node', 'kc': '9702-2.1.1',
                     'card': {'establish': 'Secret', 'connect': '', 'diagrams': ['Assets/secret.svg']},
                     'i': 0, 'phases': ['fix'], 'misses': 1, 'mistakes': []}
            tutor.session['blocks'] = [block]
            tutor.session['cursor'] = 0
            monkeypatch.setattr('tutor_app.screens.lesson.teach_card', lambda *a: block['card'])
            screen.advance()
            await pilot.pause()
            assert screen.act['part'] == 'guard_pause'
            assert not screen.query('#diagram')
            assert 'Secret' not in (vault / 'Now.md').read_text()
            await pilot.press('ctrl+u')
            await pilot.pause()
            n = screen.view['n']
            screen.submit({'entry': f'{n}A3', 'your': 'A'})
            await pilot.pause()
            await pilot.click('#next')
            await pilot.pause()
            assert screen.act['text'] == 'Secret'
            await app.ai.close()
    asyncio.run(run())


def test_diagram_button_hidden_for_guard_from_another_idea(tmp_path, monkeypatch):
    app, vault = app_for(tmp_path, monkeypatch)
    async def run():
        async with app.run_test(size=(100, 30)) as pilot:
            screen = SessionScreen({'mode': 'autopilot', 'minutes': 50})
            await app.push_screen(screen)
            await pilot.pause()
            tutor = app.tutor
            tutor.session['presented'] = {}
            tutor.session['queue'] = {}
            tutor.session.pop('awaiting', None)
            tutor.session['mode'] = 'lesson'
            item = {'id': 'other-idea-diagram', 'kcs': ['9702-2.1.1'], 'kind': 'mcq', 'difficulty': 2,
                    'marks': 1, 'stem': 'Which?', 'options': {'A': 'Secret', 'B': 'Other'}, 'answer': 'A'}
            shown = tutor._present(item, block='practice', phase='practice')
            tutor.answer(f"{shown['n']}?")
            other = next(k for k in tutor.packs.kcs if k != '9702-2.1.1')
            block = {'kind': 'node', 'kc': other, 'card': {'terms': [{'term': 'Related', 'meaning': 'A fact'}],
                     'diagrams': ['Assets/secret.svg']}, 'i': 0, 'phases': ['terms'], 'misses': 0, 'mistakes': []}
            tutor.session['blocks'] = [block]
            tutor.session['cursor'] = 0
            monkeypatch.setattr('tutor_app.screens.lesson.teach_card', lambda *a: block['card'])
            screen.advance()
            await pilot.pause()
            assert not screen.query('#diagram')
            await app.ai.close()
    asyncio.run(run())


def test_retry_excluded_text_without_restoring_or_marking(tmp_path, monkeypatch):
    from textual.widgets import Button
    app, _ = app_for(tmp_path, monkeypatch)
    async def run():
        async with app.run_test(size=(100, 30)) as pilot:
            app.push_screen(SessionScreen({'mode': 'lesson', 'minutes': 10, 'focus': ['9702-2.1']}))
            await pilot.pause()
            tutor = app.tutor
            tutor.session['presented'] = {}
            tutor.session['queue'] = {}
            tutor.session['awaiting'] = None
            item = {'id': 'ungraded-ui', 'kcs': ['9702-2.1.1'], 'kind': 'mcq', 'difficulty': 2,
                    'marks': 1, 'stem': 'Which?', 'options': {'A': 'Secret', 'B': 'Other'}, 'answer': 'A'}
            shown = tutor._present(item, block='practice', phase='practice')
            tutor.answer(f"{shown['n']}?")
            tutor.log({'type': 'topical_exclude', 'identity': item['id'], 'chapter': '9702-2.1',
                       'reason': 'test', 'missing': []})
            answered = tutor.session['answered']
            screen = app.screen
            screen.action_retry_skipped()
            await pilot.pause()
            assert app.screen.__class__.__name__ == 'ConfirmScreen'
            await pilot.press('down', 'down', 'enter')
            await pilot.pause()
            assert screen.view['stem'] == 'Which?'
            screen.submit({'entry': f"{screen.view['n']}B", 'your': 'B'})
            await pilot.pause()
            assert tutor.session['answered'] == answered
            assert tutor.topical_exclusions()
            assert tutor.session['deferred_judgments'][0]['saved_work'] == 'B'
            screen.advance()
            await pilot.pause()
            assert screen.act['activity'] == 'saved_judgment_unavailable'
            screen.query_one('#postpone-saved-judgment', Button).press()
            await pilot.pause()
            assert tutor.postponed_judgments()[0]['saved_work'] == 'B'
            assert tutor.topical_exclusions()
            await app.ai.close()
    asyncio.run(run())


def test_selected_related_card_excludes_questions_it_discloses(tmp_path, monkeypatch):
    app, _ = app_for(tmp_path, monkeypatch)
    cards = {'9702-2.1.1': {'plain_words': 'The current idea.'},
             '9702-2.1.4': {'establish': 'An example reveals a later answer.',
                            'disclosed_item_ids': ['9702-2.1-i03']}}
    async def fake(*args, **kwargs):
        return {'sections': ['9702-2.1.4|establish']}, Result()
    async def run():
        async with app.run_test(size=(100, 30)) as pilot:
            monkeypatch.setattr(app.ai, 'one_shot', fake)
            monkeypatch.setattr(app, 'ai_available', lambda mode: True)
            monkeypatch.setattr(learn_reply, 'published_related_cards', lambda *args: cards)
            app.push_screen(SessionScreen({'mode': 'lesson', 'minutes': 10, 'focus': ['9702-2.1']}))
            await pilot.pause()
            t = app.tutor
            t.session['presented'] = {}
            t.session['queue'] = {}
            app.screen.kc = '9702-2.1.1'
            await app.screen.learn_request('Explain that related example').wait()
            assert '9702-2.1-i03' in t.session['disclosed_item_ids']
            from tutorlib import session, store
            restarted = session.Tutor(store.Vault(t.vault.root))
            assert '9702-2.1-i03' in restarted.session['disclosed_item_ids']
            await app.ai.close()
    asyncio.run(run())



def test_guided_marking_defers_if_another_question_is_skipped_while_waiting(tmp_path, monkeypatch):
    app, vault = app_for(tmp_path, monkeypatch)
    async def run():
        started, release = asyncio.Event(), asyncio.Event()
        async def examiner(*args, **kwargs):
            started.set()
            await release.wait()
            return {'points': [{'point': 'PRIVATE RUBRIC', 'met': True}], 'feedback': 'PRIVATE SOLUTION'}, Result()
        async with app.run_test(size=(100, 30)) as pilot:
            t = app.tutor
            t.start('review', minutes=10)
            base = {'kcs': ['9702-2.1.1'], 'kind': 'short', 'difficulty': 3, 'marks': 1,
                    'rubric': [{'point': 'PRIVATE RUBRIC', 'keywords': [['private']]}]}
            first = t._present({**base, 'id': 'first', 'stem': 'Explain first.', 'review_answer': 'PRIVATE SOLUTION'},
                               block='practice', phase='form_check')
            screen = SessionScreen(None)
            await app.push_screen(screen)
            await pilot.pause()
            monkeypatch.setattr(app, 'ai_available', lambda mode: True)
            monkeypatch.setattr(app.ai, 'one_shot', examiner)
            app.settings.ai_mark_model = 'sonnet'
            data = {'entry': f"{first['n']} = My working", 'your': 'My working'}
            screen.pending_short = (first['n'], data, 1)
            worker = screen.judge_short(first, data, {'rubric': ['PRIVATE RUBRIC']})
            await started.wait()
            t.one_at_a_time = False  # model a batch open in a shared session
            second = t._present({**base, 'id': 'second', 'stem': 'Explain second.', 'review_answer': 'PRIVATE SOLUTION'},
                                block='practice', phase='form_check')
            assert t.answer(f"{second['n']}?")['results'][0].get('answer_withheld')
            release.set()
            await worker.wait()
            await pilot.pause()
            assert 'PRIVATE SOLUTION' not in (vault / 'Now.md').read_text()
            assert 'PRIVATE RUBRIC' not in (vault / 'Now.md').read_text()
            assert t.session['presented'][str(first['n'])]['saved_work'] == 'My working'
            assert not [e for e in t.vault.events() if e['type'] == 'answer' and e.get('item') == 'first']
            await app.ai.close()
    asyncio.run(run())


def test_unmarked_work_survives_session_end_or_replace_during_model_request(tmp_path, monkeypatch):
    from tutorlib import session, store
    app, vault = app_for(tmp_path, monkeypatch)
    async def run():
        started, release = asyncio.Event(), asyncio.Event()
        async def examiner(*args, **kwargs):
            started.set()
            await release.wait()
            return {'points': [{'point': 'A point', 'met': True}], 'feedback': 'Fine.'}, Result()
        async with app.run_test(size=(100, 30)) as pilot:
            t = app.tutor
            t.start('review', minutes=10)
            item = {'id': 'pending-mark', 'kcs': ['9702-2.1.1'], 'kind': 'short', 'difficulty': 3,
                    'marks': 1, 'stem': 'Explain.', 'review_answer': 'A sample.',
                    'rubric': [{'point': 'A point', 'keywords': [['point']]}]}
            view = t._present(item, block='practice', phase='form_check')
            screen = SessionScreen(None)
            await app.push_screen(screen)
            await pilot.pause()
            monkeypatch.setattr(app, 'ai_available', lambda mode: True)
            monkeypatch.setattr(app.ai, 'one_shot', examiner)
            app.settings.ai_mark_model = 'sonnet'
            data = {'entry': f"{view['n']} = My saved work", 'your': 'My saved work'}
            screen.pending_short = (view['n'], data, 1)
            worker = screen.judge_short(view, data, {'rubric': ['A point']})
            await started.wait()
            assert t.end().get('error')
            assert not t.start('review', minutes=10, replace=True).get('session')
            restored = session.Tutor(store.Vault(vault))
            assert restored.session['presented'][str(view['n'])]['saved_work'] == 'My saved work'
            assert restored.end().get('error')
            release.set()
            await worker.wait()
            screen.long_marks({'ticked': ['0']})
            assert not t.end().get('error')
            await app.ai.close()
    asyncio.run(run())


def test_marking_rechecks_changed_guard_content_not_only_identity(tmp_path, monkeypatch):
    from tutor_app import prompts
    app, vault = app_for(tmp_path, monkeypatch)
    async def run():
        started, release = asyncio.Event(), asyncio.Event()
        guards = {'same-id': {'question': {'answer': 'first'}}}
        async def examiner(*args, **kwargs):
            started.set()
            await release.wait()
            return {'points': [{'point': 'PRIVATE RUBRIC', 'met': True}], 'feedback': 'PRIVATE SOLUTION'}, Result()
        async with app.run_test(size=(100, 30)) as pilot:
            t = app.tutor
            t.start('review', minutes=10)
            item = {'id': 'guard-change', 'kcs': ['9702-2.1.1'], 'kind': 'short', 'difficulty': 3,
                    'marks': 1, 'stem': 'Explain.', 'review_answer': 'PRIVATE SOLUTION',
                    'rubric': [{'point': 'PRIVATE RUBRIC', 'keywords': [['private']]}]}
            view = t._present(item, 'practice', 'form_check')
            screen = SessionScreen(None)
            await app.push_screen(screen)
            await pilot.pause()
            # Guard ownership moved behind the engine's marking interface.
            monkeypatch.setattr(t, 'marking_guards', lambda: guards)
            monkeypatch.setattr(app, 'ai_available', lambda mode: True)
            monkeypatch.setattr(app.ai, 'one_shot', examiner)
            app.settings.ai_mark_model = 'sonnet'
            data = {'entry': f"{view['n']} = Work", 'your': 'Work'}
            screen.pending_short = (view['n'], data, 1)
            worker = screen.judge_short(view, data, {'rubric': ['PRIVATE RUBRIC']})
            await started.wait()
            guards['same-id']['question']['answer'] = 'changed'
            release.set()
            await worker.wait()
            await pilot.pause()
            assert 'PRIVATE SOLUTION' not in (vault / 'Now.md').read_text()
            assert not [e for e in t.vault.events() if e['type'] == 'answer']
            assert t.session['presented'][str(view['n'])]['saved_work'] == 'Work'
            await app.ai.close()
    asyncio.run(run())


def test_marking_detects_persisted_guard_draft_update_under_same_session_id(tmp_path, monkeypatch):
    import copy
    from tutorlib import deferred_notes, session, store
    from tutor_app import prompts
    app, vault = app_for(tmp_path, monkeypatch)
    async def run():
        started, release = asyncio.Event(), asyncio.Event()
        async def examiner(*args, **kwargs):
            started.set()
            await release.wait()
            return {'points': [{'point': 'PRIVATE RUBRIC', 'met': True}], 'feedback': 'PRIVATE SOLUTION'}, Result()
        async with app.run_test(size=(100, 30)) as pilot:
            t = app.tutor
            t.start('review', minutes=10)
            item = {'id': 'persisted-guard-change', 'kcs': ['9702-2.1.1'], 'kind': 'short', 'difficulty': 3,
                    'marks': 1, 'stem': 'Explain.', 'review_answer': 'PRIVATE SOLUTION',
                    'rubric': [{'point': 'PRIVATE RUBRIC', 'keywords': [['private']]}]}
            view = t._present(item, 'practice', 'form_check')
            screen = SessionScreen(None)
            await app.push_screen(screen)
            await pilot.pause()
            path = vault / '.tutor/state/deferred-notes.json'
            guard = {'kind': 'short', 'key': 'secret', 'question': {'inst': {'id': 'guarded'}, 'saved_work': 'draft'}}
            deferred_notes.hold(path, 'guard', guard)
            t.session.setdefault('skipped_answer_guards', {})['guard'] = copy.deepcopy(guard)
            monkeypatch.setattr(app, 'ai_available', lambda mode: True)
            monkeypatch.setattr(app.ai, 'one_shot', examiner)
            app.settings.ai_mark_model = 'sonnet'
            data = {'entry': f"{view['n']} = My work", 'your': 'My work'}
            screen.pending_short = (view['n'], data, 1)
            worker = screen.judge_short(view, data, {'rubric': ['PRIVATE RUBRIC']})
            await started.wait()
            updated = copy.deepcopy(guard)
            updated['question']['saved_work'] = 'revised draft'
            deferred_notes.hold(path, 'guard', updated)
            release.set()
            await worker.wait()
            await pilot.pause()
            assert 'PRIVATE SOLUTION' not in (vault / 'Now.md').read_text()
            assert not [e for e in t.vault.events() if e['type'] == 'answer']
            assert deferred_notes.outstanding(path)['guard']['question']['saved_work'] == 'revised draft'
            assert t.session['presented'][str(view['n'])]['saved_work'] == 'My work'
            await app.ai.close()
    asyncio.run(run())


def test_saved_attempts_screen_shows_retained_draft_without_marking_data(tmp_path, monkeypatch):
    from tutorlib import deferred_notes
    from textual.widgets import Static
    app, vault = app_for(tmp_path, monkeypatch)
    path = vault / '.tutor/state/deferred-notes.json'
    guard = {'kind': 'short', 'key': 'PRIVATE KEY', 'question': {'inst': {'id': 'q'}, 'saved_work': 'First draft'}}
    deferred_notes.hold(path, 'guard', guard)
    changed = {'kind': 'short', 'key': 'PRIVATE KEY', 'question': {'inst': {'id': 'q'}, 'saved_work': 'Second draft'}}
    deferred_notes.hold(path, 'guard', changed)
    deferred_notes.resolve(path, 'guard')
    async def run():
        async with app.run_test(size=(100, 30)) as pilot:
            assert app.screen.query_one('#menu').get_option('saved-attempts')
            app.screen._start('saved-attempts')
            await pilot.pause()
            rendered = '\n'.join(str(w.render()) for w in app.screen.query(Static))
            assert 'First draft' in rendered
            assert 'PRIVATE KEY' not in rendered
            await app.ai.close()
    asyncio.run(run())


def test_invalid_retained_draft_history_does_not_break_home_menu(tmp_path, monkeypatch):
    from tutorlib.store import write_json
    app, vault = app_for(tmp_path, monkeypatch)
    write_json(vault / '.tutor/state/deferred-notes.json', {'entries': [], 'guards': {}, 'draft_history': {'bad': 'not a list'}})
    async def run():
        async with app.run_test(size=(100, 30)) as pilot:
            await pilot.pause()
            assert app.screen.query_one('#menu').get_option('today')
            await app.ai.close()
    asyncio.run(run())


def test_learning_tutor_suggests_relevant_form_without_showing_example_or_check(tmp_path, monkeypatch):
    app, vault = app_for(tmp_path, monkeypatch)
    card = {'forms': [{'name': 'Prove no turning points using a quadratic gradient',
                       'example': 'PRIVATE EXAMPLE', 'check': 'PRIVATE CHECK', 'answer': 'PRIVATE ANSWER'}]}
    monkeypatch.setattr(learn_reply, 'published_related_cards', lambda tutor, kc: {kc: card})
    calls = []
    async def fake(*args, **kwargs):
        calls.append(True)
        return None, Result()
    async def run():
        async with app.run_test(size=(100, 30)) as pilot:
            monkeypatch.setattr(app, 'ai_available', lambda mode: True)
            monkeypatch.setattr(app.ai, 'one_shot', fake)
            app.push_screen(SessionScreen({'mode': 'test', 'minutes': 10, 'focus': ['9702-2.1']}))
            await pilot.pause()
            app.tutor.session['presented'] = {}; app.tutor.session['queue'] = {}
            app.screen.kc = '9702-2.1.1'
            await app.screen.learn_request('How do I prove a cubic curve has no turning points using its quadratic gradient?').wait()
            text = (vault / 'Now.md').read_text()
            assert 'Prove no turning points using a quadratic gradient' in text
            assert 'Show example for form 1' in text
            assert 'PRIVATE' not in text and not calls
            await app.ai.close()
    asyncio.run(run())



def test_positive_pair_domain_warning_is_shown_after_attempt(tmp_path, monkeypatch):
    app, vault = app_for(tmp_path, monkeypatch)
    point = 'Gives positive values.'
    async def examiner(*args, **kwargs):
        return {'points': [{'point': point, 'met': True}], 'feedback': 'Correct.'}, Result()
    async def run():
        async with app.run_test(size=(100, 30)) as pilot:
            t = app.tutor
            t.start('review', minutes=10)
            item = {'id': 'positive-pair', 'kcs': ['9702-2.1.1'], 'kind': 'short', 'difficulty': 2,
                    'marks': 1, 'stem': 'Give positive x and y.', 'review_rule': 'positive_pair',
                    'review_answer': 'A worked answer.', 'rubric': [{'point': point, 'keywords': [['positive']]}]}
            view = t._present(item, 'practice', 'form_check')
            screen = SessionScreen(None)
            await app.push_screen(screen)
            await pilot.pause()
            monkeypatch.setattr(app, 'ai_available', lambda mode: True)
            monkeypatch.setattr(app.ai, 'one_shot', examiner)
            app.settings.ai_mark_model = 'ollama:gemma4:e4b'
            data = {'entry': f"{view['n']} = x=-1 and y=2", 'your': 'x=-1; y=2 (fairly sure)'}
            screen.pending_short = (view['n'], data, 1)
            await screen.judge_short(view, data, {'rubric': [point]}).wait()
            assert 'not positive' in (vault / 'Now.md').read_text()
            assert not [event for event in t.vault.events() if event['type'] == 'answer']
            await app.ai.close()
    asyncio.run(run())


def test_installed_written_faded_question_reaches_review_ui(tmp_path, monkeypatch):
    app, vault = app_for(tmp_path, monkeypatch)
    async def run():
        async with app.run_test(size=(100, 30)) as pilot:
            t = app.tutor
            t.start('lesson', focus=['9702-2.1'])
            kc = '9702-2.1.1'
            pack = t.packs.pack_for_kc(kc)
            pack['worked'] = [{'id': 'written-worked', 'kc': kc, 'problem': 'Example', 'steps': [],
                               'faded': {'id': 'written-faded', 'kind': 'short', 'problem': 'Disprove the claim.',
                                         'review_answer': 'SECRET SOLUTION',
                                         'rubric': [{'point': 'SECRET POINT', 'keywords': [['reason']]}]}}]
            block = {'kind': 'node', 'kc': kc, 'card': {'source': 'pack'}, 'i': 0, 'phases': ['faded']}
            activity = t._step_node(block, 0)
            view = activity['items'][0]
            assert view['stem'] == 'Disprove the claim.' and 'SECRET' not in str(view)
            screen = SessionScreen(None)
            await app.push_screen(screen)
            await pilot.pause()
            screen.show_guided_review_answer(view['n'], {'your': ''})
            assert 'SECRET SOLUTION' not in (vault / 'Now.md').read_text()
            screen.show_guided_review_answer(view['n'], {'your': 'I tried a valid example.'})
            assert 'SECRET SOLUTION' in (vault / 'Now.md').read_text()
            await app.ai.close()
    asyncio.run(run())


def test_written_faded_plain_nonattempt_never_opens_marking_panel(tmp_path, monkeypatch):
    app, vault = app_for(tmp_path, monkeypatch)
    async def run():
        async with app.run_test(size=(100, 30)) as pilot:
            t = app.tutor
            t.start('learn', focus=['9702-2.1.1'])
            item = {'id': 'written-faded', 'kcs': ['9702-2.1.1'], 'kind': 'short', 'difficulty': 3,
                    'marks': 1, 'stem': 'Disprove.', 'review_answer': 'PRIVATE SOLUTION',
                    'rubric': [{'point': 'PRIVATE POINT', 'keywords': [['reason']]}]}
            view = t._present(item, block='learn', phase='faded')
            screen = SessionScreen(None)
            await app.push_screen(screen)
            await pilot.pause()
            screen.view = view
            screen.submit({'entry': f"{view['n']} = I don't know", 'your': "I don't know"})
            await pilot.pause()
            assert not getattr(screen, 'pending_short', None)
            assert 'PRIVATE' not in (vault / 'Now.md').read_text()
            assert t.session['skipped_answer_guards']
            await app.ai.close()
    asyncio.run(run())


def test_written_faded_asks_before_revealing_marking_points(tmp_path, monkeypatch):
    from tutor_app.panels import ContinuePanel
    app, vault = app_for(tmp_path, monkeypatch)
    async def run():
        async with app.run_test(size=(100, 30)) as pilot:
            t = app.tutor
            t.start('learn', focus=['9702-2.1.1'])
            item = {'id': 'written-faded', 'kcs': ['9702-2.1.1'], 'kind': 'short', 'written_faded': True,
                    'difficulty': 3, 'marks': 1, 'stem': 'Explain.', 'review_answer': 'PRIVATE SOLUTION',
                    'rubric': [{'point': 'PRIVATE POINT', 'keywords': [['reason']]}]}
            view = t._present(item, block='learn', phase='faded')
            screen = SessionScreen(None)
            await app.push_screen(screen)
            await pilot.pause()
            screen.view = view
            screen.submit({'entry': f"{view['n']} = a reason", 'your': 'a reason'})
            await pilot.pause()
            panel = screen.query_one('#panel > *', ContinuePanel)
            assert 'attempt' in panel.prompt.lower()
            assert 'PRIVATE' not in (vault / 'Now.md').read_text()
            assert not getattr(screen, 'pending_short', None)
            await app.ai.close()
    asyncio.run(run())


def test_p2_written_pilot_withholds_answer_until_attempt_confirmation(tmp_path, monkeypatch):
    import json
    from pathlib import Path
    from tutorlib.faded import question_item
    from tutor_app.panels import ContinuePanel

    candidate = library_json('build/work/guided/P2-1-written-pilot-candidate.json')
    worked = next(row for row in candidate['worked'] if row['id'] == 'we2')
    app, vault = app_for(tmp_path, monkeypatch)
    async def run():
        async with app.run_test(size=(100, 30)) as pilot:
            t = app.tutor
            t.start('learn', focus=['9702-2.1.1'])
            view = t._present(question_item(worked['faded'], '9702-2.1.1'), block='learn', phase='faded')
            screen = SessionScreen(None)
            await app.push_screen(screen)
            await pilot.pause()
            screen.view = view
            response = '11 is an integer greater than 9. 111 = 37 × 3.'
            screen.submit({'entry': f"{view['n']} = {response}", 'your': response})
            await pilot.pause()
            assert 'attempt' in screen.query_one('#panel > *', ContinuePanel).prompt.lower()
            assert '111' not in (vault / 'Now.md').read_text()
            assert not getattr(screen, 'pending_short', None)
            await app.ai.close()
    asyncio.run(run())


@pytest.mark.parametrize('choice', ['faded-edit', 'faded-skip', 'faded-submit'])
def test_written_faded_confirmation_choices(tmp_path, monkeypatch, choice):
    from types import SimpleNamespace
    from tutor_app.panels import ValuePanel
    app, vault = app_for(tmp_path, monkeypatch)
    async def run():
        async with app.run_test(size=(100, 30)) as pilot:
            t = app.tutor
            t.start('learn', focus=['9702-2.1.1'])
            item = {'id': 'written-faded', 'kcs': ['9702-2.1.1'], 'kind': 'short', 'written_faded': True,
                    'difficulty': 3, 'marks': 1, 'stem': 'Explain.', 'review_answer': 'PRIVATE SOLUTION',
                    'rubric': [{'point': 'PRIVATE POINT', 'keywords': [['reason']]}]}
            view = t._present(item, block='learn', phase='faded')
            screen = SessionScreen(None)
            await app.push_screen(screen)
            await pilot.pause()
            screen.view = view
            monkeypatch.setattr(app, 'ai_available', lambda mode: False)
            screen.submit({'entry': f"{view['n']} = a reason", 'your': 'a reason'})
            await pilot.pause()
            screen.panel_done(SimpleNamespace(panel=screen.showing, data={'button': choice}))
            await pilot.pause()
            if choice == 'faded-edit':
                assert screen.query_one('#panel > *', ValuePanel)
                assert t.session['presented'][str(view['n'])]['saved_work'] == 'a reason'
                assert 'PRIVATE' not in (vault / 'Now.md').read_text()
            elif choice == 'faded-skip':
                assert t.session['skipped_answer_guards']
                assert 'PRIVATE' not in (vault / 'Now.md').read_text()
            else:
                assert screen.query_one('#panel > *', TickPanel)
                assert 'PRIVATE SOLUTION' in (vault / 'Now.md').read_text()
            await app.ai.close()
    asyncio.run(run())


@pytest.mark.parametrize('ai_available', [True, False])
def test_confirmed_written_faded_retry_requires_manual_review(tmp_path, monkeypatch, ai_available):
    app, _ = app_for(tmp_path, monkeypatch)
    async def examiner(*args, **kwargs):
        return {'points': [{'point': 'Reason', 'met': True}], 'feedback': 'Complete.'}, Result()
    async def run():
        async with app.run_test(size=(100, 30)) as pilot:
            t = app.tutor
            t.start('learn', focus=['9702-2.1.1'])
            item = {'id': 'written-faded', 'kcs': ['9702-2.1.1'], 'kind': 'short', 'written_faded': True,
                    'difficulty': 3, 'marks': 1, 'stem': 'Explain.', 'review_answer': 'Solution',
                    'rubric': [{'point': 'Reason', 'keywords': [['reason']]}]}
            n = t._present(item, block='learn', phase='faded')['n']
            t.answer(f'{n}?')
            view = t.retry_skipped()['items'][0]
            n = view['n']
            t.answer(f'{n} = a reason')
            assert t.confirm_faded_attempt(n, 'a reason')['ok']
            pending = t.answer(f'{n} = a reason')['results'][0]
            screen = SessionScreen(None)
            await app.push_screen(screen)
            await pilot.pause()
            monkeypatch.setattr(app, 'ai_available', lambda mode: ai_available)
            monkeypatch.setattr(app.ai, 'one_shot', examiner)
            data = {'entry': f'{n} = a reason', 'your': 'a reason'}
            screen.pending_short = (n, data, 1)
            await screen.judge_short(view, data, pending).wait()
            await pilot.pause()
            assert screen.query_one('#panel > *', TickPanel)
            assert not [e for e in t.vault.events() if e['type'] == 'answer' and e.get('n') == n]
            await app.ai.close()
    asyncio.run(run())


def test_unavailable_written_faded_retry_reopens_saved_draft(tmp_path, monkeypatch):
    from types import SimpleNamespace
    from tutor_app.panels import ValuePanel
    app, vault = app_for(tmp_path, monkeypatch)
    async def run():
        async with app.run_test(size=(100, 30)) as pilot:
            t = app.tutor
            t.start('learn', focus=['9702-2.1.1'])
            item = {'id': 'written-faded', 'kcs': ['9702-2.1.1'], 'kind': 'short', 'written_faded': True,
                    'difficulty': 3, 'marks': 1, 'stem': 'Explain.', 'review_answer': 'PRIVATE SOLUTION',
                    'rubric': [{'point': 'PRIVATE POINT', 'keywords': [['reason']]}]}
            n = t._present(item, block='learn', phase='faded')['n']
            t.answer(f'{n}?')
            view = t.retry_skipped()['items'][0]
            t.session['presented'][str(view['n'])]['ungraded_unavailable'] = True
            screen = SessionScreen(None)
            await app.push_screen(screen)
            await pilot.pause()
            screen.view = view
            screen.submit({'entry': f"{view['n']} = my working", 'your': 'my working'})
            await pilot.pause()
            screen.panel_done(SimpleNamespace(panel=screen.showing, data={'button': 'faded-skip'}))
            await pilot.pause()
            assert next(iter(t.session['skipped_answer_guards'].values()))['question']['saved_work'] == 'my working'
            assert 'PRIVATE' not in (vault / 'Now.md').read_text()
            await app.ai.close()
    asyncio.run(run())


def test_faded_cancel_failure_offers_retry_without_losing_work(tmp_path, monkeypatch):
    from types import SimpleNamespace
    from tutorlib import deferred_notes
    from tutor_app.panels import ContinuePanel
    app, vault = app_for(tmp_path, monkeypatch)
    async def run():
        async with app.run_test(size=(100, 30)) as pilot:
            t = app.tutor
            t.start('learn', focus=['9702-2.1.1'])
            item = {'id': 'f', 'kcs': ['9702-2.1.1'], 'kind': 'short', 'written_faded': True,
                    'difficulty': 3, 'marks': 1, 'stem': 'Explain.', 'review_answer': 'PRIVATE',
                    'rubric': [{'point': 'PRIVATE POINT', 'keywords': [['reason']]}]}
            n = t._present(item, block='learn', phase='faded')['n']
            t.answer(f'{n}?')
            view = t.retry_skipped()['items'][0]
            t.session['presented'][str(view['n'])]['ungraded_unavailable'] = True
            screen = SessionScreen(None)
            await app.push_screen(screen)
            await pilot.pause()
            screen.view = view
            screen.submit({'entry': f"{view['n']} = my work", 'your': 'my work'})
            await pilot.pause()
            real = deferred_notes.cancel_draft
            monkeypatch.setattr(deferred_notes, 'cancel_draft', lambda *args: (_ for _ in ()).throw(OSError('offline')))
            screen.panel_done(SimpleNamespace(panel=screen.showing, data={'button': 'faded-skip'}))
            await pilot.pause()
            panel = screen.query_one('#panel > *', ContinuePanel)
            assert any(key == 'faded-recover' for key, *_ in panel.buttons)
            assert 'PRIVATE' not in (vault / 'Now.md').read_text()
            monkeypatch.setattr(deferred_notes, 'cancel_draft', real)
            screen.panel_done(SimpleNamespace(panel=screen.showing, data={'button': 'faded-recover'}))
            await pilot.pause()
            assert not t.session.get('faded_cancel_intent')
            assert next(iter(t.session['skipped_answer_guards'].values()))['question']['saved_work'] == 'my work'
            await app.ai.close()
    asyncio.run(run())


def test_faded_recovery_panel_explains_conflicting_drafts(tmp_path, monkeypatch):
    from tutor_app.panels import ContinuePanel
    app, _ = app_for(tmp_path, monkeypatch)
    async def run():
        async with app.run_test(size=(100, 30)) as pilot:
            t = app.tutor
            t.start('learn', focus=['9702-2.1.1'])
            t.session['faded_cancel_intent'] = {'operation': 'op', 'conflict_recorded': True}
            screen = SessionScreen(None)
            await app.push_screen(screen)
            await pilot.pause()
            screen.faded_recovery_panel()
            panel = screen.query_one('#panel > *', ContinuePanel)
            assert 'different' in panel.prompt.lower()
            assert 'retry' in panel.prompt.lower()
            await app.ai.close()
    asyncio.run(run())


def test_faded_recovery_button_does_not_apply_to_replaced_session(tmp_path, monkeypatch):
    from types import SimpleNamespace
    app, _ = app_for(tmp_path, monkeypatch)
    async def run():
        async with app.run_test(size=(100, 30)) as pilot:
            t = app.tutor
            t.start('learn', focus=['9702-2.1.1'])
            t.session['faded_cancel_intent'] = {'operation': 'old'}
            screen = SessionScreen(None)
            await app.push_screen(screen)
            await pilot.pause()
            screen.faded_recovery_panel()
            old_panel = screen.showing
            t.session = {**t.session, 'faded_cancel_intent': {'operation': 'new'}}
            called = []
            monkeypatch.setattr(t, 'retry_faded_cancellation', lambda: called.append(True) or {'ok': True})
            screen.panel_done(SimpleNamespace(panel=old_panel, data={'button': 'faded-recover'}))
            assert not called
            await app.ai.close()
    asyncio.run(run())
