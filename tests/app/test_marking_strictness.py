"""AI marking policy reaches every examiner without changing deterministic grades or history."""
import asyncio
from copy import deepcopy
import json
import os

import pytest
from textual.widgets import Button, Select, Static

import library_assets
from test_tui import app_for
from tutor_app import ai, config, local_models, look, prompts, tutor_ai
from tutor_app.screens import SessionScreen

LEVELS = ('auto', 'lenient', 'balanced', 'strict')
ICE = next(item for item in library_assets.read_json(
    'Library/Releases/v274/specs/9701/packs/9701-4.2.json')['items'] if item['id'] == '9701-4.2-i15')
STEM = ICE['stem']
POINT = ICE['rubric'][0]['point']
ANSWER = ('Ice has strong hydrogen bonds between molecules that take high amounts of heat energy to overcome.\n\n'
          'Other simple molecular structures either have permanent dipole attraction and/or london dispersion '
          'forces which are weaker than hydrogen bonds.')


@pytest.mark.parametrize('saved,want', [({}, 'auto'), *[({'marking_strictness': s}, s) for s in LEVELS],
                                      *[({'marking_strictness': s}, 'auto')
                                        for s in ('unknown', '', 'STRICT', False, 3, None, [], {})]])
def test_saved_strictness_validation_and_roundtrip_preserves_other_settings(tmp_path, saved, want):
    path = tmp_path / '.tutor/app_settings.json'
    path.parent.mkdir()
    original = json.dumps({'minutes': 55, 'ai_mark_model': 'sonnet', **saved}).encode()
    path.write_bytes(original)
    loaded = config.Settings.load(tmp_path)
    assert loaded.marking_strictness == want
    assert loaded.minutes == 55 and loaded.ai_for('mark') == ('sonnet', False)
    assert path.read_bytes() == original
    loaded.save(tmp_path)
    assert config.Settings.load(tmp_path).marking_strictness == want


@pytest.mark.parametrize('mode,want', [('lesson', 'balanced'), ('learn', 'balanced'), ('review', 'balanced'),
                                     ('autopilot', 'balanced'), ('', 'balanced'), ('unknown', 'balanced'),
                                     ('test', 'strict'), ('long', 'strict'), ('topical', 'strict'),
                                     ('challenge', 'strict')])
def test_auto_is_deterministic_by_study_purpose_and_explicit_levels_override(mode, want):
    from tutor_app import marking_policy
    assert marking_policy.resolve('auto', mode) == want
    assert marking_policy.resolve('invalid', mode) == want
    for level in LEVELS[1:]:
        assert marking_policy.resolve(level, mode) == level


@pytest.mark.parametrize('level', LEVELS)
@pytest.mark.parametrize('builder', ['judge', 'remark'])
def test_policy_requests_full_answer_evidence_and_equivalence_without_extra_requirements(level, builder):
    if builder == 'judge':
        prompt = prompts.judge(STEM, [POINT], ANSWER, strictness=level, mode='review')
        assert f'1. {POINT}' in prompt
        assert 'copying its text exactly' in prompt
    else:
        prompt = prompts.remark({'kind': 'short', 'stem': STEM}, {'response': ANSWER, 'answer': POINT},
                               strictness=level, mode='review')
    effective = 'balanced' if level == 'auto' else level
    assert f'AI MARKING STRICTNESS: {effective.title()}' in prompt
    assert ANSWER in prompt
    assert 'Read the entire student answer, including every paragraph' in prompt
    assert 'Accept equivalent correct wording' in prompt
    assert 'Do not add requirements beyond the question and supplied mark points' in prompt
    assert 'Do not infer an unstated mechanism' in prompt
    assert 'confidence' in prompt
    assert 'Do not be generous' not in prompt


@pytest.mark.parametrize('theme,size,save', [('classic', (80, 24), True), ('day', (60, 24), True),
                                          ('night', (100, 30), False)])
def test_settings_strictness_help_keyboard_save_cancel_and_preset_independence(
        tmp_path, monkeypatch, theme, size, save):
    monkeypatch.setenv('TERM', 'xterm-256color')
    monkeypatch.setenv('COLORTERM', 'truecolor')
    app, vault = app_for(tmp_path, monkeypatch)
    app.settings.theme = theme
    look.use(theme)
    app.settings.save(vault)
    before = (vault / '.tutor/app_settings.json').read_bytes()

    async def go():
        async with app.run_test(size=size) as pilot:
            app.action_settings()
            await pilot.pause()
            screen = app.screen
            selector = screen.query_one('#marking_strictness', Select)
            help_text = screen.query_one('#marking-strictness-help', Static)
            assert selector.value == 'auto'
            assert {value for _, value in selector._options} == set(LEVELS)
            assert 'Balanced' in str(help_text.content) and 'Strict' in str(help_text.content)
            evidence = os.environ.get('MARKING_SHOTS')
            if evidence:
                help_text.scroll_visible(animate=False)
                await pilot.pause()
                app.save_screenshot(path=evidence, filename=f'{theme}-{size[0]}-auto.svg')
            selector.focus()
            await pilot.press('enter', 'down', 'enter')
            await pilot.pause()
            assert selector.value == 'lenient'
            assert 'core idea' in str(help_text.content)
            screen.query_one('#ai_preset', Select).value = 'claude_balanced'
            screen.query_one('#apply-preset', Button).press()
            await pilot.pause()
            assert selector.value == 'lenient'
            assert app.settings.marking_strictness == 'auto'
            selector.scroll_visible(animate=False)
            await pilot.pause()
            assert selector.parent.content_region.contains_region(selector.region)
            help_text.scroll_visible(animate=False)
            await pilot.pause()
            assert screen.get_widget_at(help_text.region.x + 1, help_text.region.bottom - 1)[0] is help_text
            save_button = screen.query_one('#save', Button)
            assert screen.get_widget_at(save_button.region.x + 1, save_button.region.y)[0] is save_button
            if evidence:
                app.save_screenshot(path=evidence, filename=f'{theme}-{size[0]}-lenient.svg')
            if save:
                screen.query_one('#save', Button).press()
            else:
                await pilot.press('escape')
            await pilot.pause()
            await app.workers.wait_for_complete()
            expected = 'lenient' if save else 'auto'
            assert app.settings.marking_strictness == config.Settings.load(vault).marking_strictness == expected
            if not save:
                assert (vault / '.tutor/app_settings.json').read_bytes() == before
            await app.ai.close()
    try:
        asyncio.run(go())
    finally:
        look.use('classic')


@pytest.mark.parametrize('level', LEVELS)
@pytest.mark.parametrize('outcome', ['credit', 'missing-comparison', 'invalid-point'])
def test_short_worker_sends_whole_ice_answer_and_keeps_scoring_and_manual_fallback(
        tmp_path, monkeypatch, level, outcome):
    from tutor_app.panels import TickPanel
    app, vault = app_for(tmp_path, monkeypatch)
    library_assets.install_course(vault, '9701', '9701-4.2')
    app.settings.marking_strictness = level
    app.settings.ai_mark_model = 'codex:gpt-6.1-terra'
    app.settings.confirm_ai_marks = False
    submitted = ANSWER if outcome != 'missing-comparison' else ANSWER.split('\n\n')[0]
    seen = []

    async def marker(prompt, **kwargs):
        seen.append((prompt, kwargs))
        # Scripted verdicts test delivery and scoring, not live scientific judgement.
        return {'points': [{'point': 'wrong rubric identity' if outcome == 'invalid-point' else POINT,
                            'met': outcome == 'credit', 'why': 'Scripted evidence.'}],
                'feedback': 'Scripted feedback.'}, ai.Result()

    async def go():
        async with app.run_test(size=(80, 24)) as pilot:
            tutor = app.tutor
            tutor.start('review', minutes=10)
            view = tutor._present(deepcopy(ICE), block='practice', phase='practice')
            screen = SessionScreen(None)
            await app.push_screen(screen)
            await pilot.pause()
            monkeypatch.setattr(app, 'ai_available', lambda mode: True)
            monkeypatch.setattr(app.ai, 'one_shot', marker)
            data = {'entry': f"{view['n']} = {submitted}", 'your': submitted}
            screen.pending_short = (view['n'], data, 1)
            original = deepcopy(tutor.session['presented'][str(view['n'])]['inst'])
            before = list(tutor.vault.events())
            await screen.judge_short(view, data, {'rubric': [POINT]}).wait()
            await pilot.pause()
            effective = 'balanced' if level == 'auto' else level
            assert len(seen) == 1 and submitted in seen[0][0]
            assert f'AI MARKING STRICTNESS: {effective.title()}' in seen[0][0]
            assert seen[0][1]['model'] == 'codex:gpt-6.1-terra'
            events = list(tutor.vault.events())
            assert events[:len(before)] == before
            answers = [e for e in events[len(before):] if e['type'] == 'answer']
            if outcome == 'invalid-point':
                assert not answers
                assert screen.query_one('#panel > *', TickPanel)
                assert tutor.session['presented'][str(view['n'])]['inst'] == original
            else:
                assert len(answers) == 1
                assert answers[0]['grade']['score'] == (1 if outcome == 'credit' else 0)
                # The engine's existing compact response normalises newlines; displayed working stays exact.
                assert answers[0]['response'].endswith(submitted.split('\n\n')[-1])
                assert screen.last_fb['your'] == submitted
                assert not screen.query('#panel > TickPanel')
            await app.ai.close()
    asyncio.run(go())


@pytest.mark.parametrize('level,mode,effective', [('auto', 'test', 'Strict'), ('auto', 'review', 'Balanced'),
                                               ('lenient', 'test', 'Lenient')])
def test_long_check_and_session_remark_use_saved_policy(tmp_path, monkeypatch, level, mode, effective):
    app, _ = app_for(tmp_path, monkeypatch)
    app.settings.marking_strictness = level
    app.settings.ai_mark_model = 'sonnet'

    async def go():
        async with app.run_test(size=(100, 30)) as pilot:
            # The tiny fixture has no due review queue; keep a real open question, then set its study purpose.
            screen = SessionScreen({'mode': 'test', 'minutes': 40, 'focus': ['9702-2.1']})
            await app.push_screen(screen)
            await pilot.pause()
            app.tutor.session['mode'] = mode
            screen.view = {'n': 1, 'stem': STEM, 'kind': 'short'}
            screen.scheme, screen.long_text = [{'i': 1, 'mark': '[1]', 'point': POINT}], ANSWER
            seen = []
            before = list(app.tutor.vault.events())

            async def marker(prompt, **kwargs):
                seen.append((prompt, kwargs))
                return None, ai.Result(ok=False, message='Scripted unavailable')

            monkeypatch.setattr(app.ai, 'one_shot', marker)
            await screen.ai_check_long({'ticked': ['1']}).wait()
            screen.last_fb = {'answer': POINT, 'response': ANSWER}
            await screen.remark().wait()
            assert len(seen) == 2
            for prompt, kwargs in seen:
                assert f'AI MARKING STRICTNESS: {effective}' in prompt and ANSWER in prompt
                assert kwargs['model'] == 'sonnet'
            assert list(app.tutor.vault.events()) == before
            await app.ai.close()
    asyncio.run(go())


@pytest.mark.parametrize('level,effective', [('auto', 'Strict'), ('lenient', 'Lenient')])
def test_challenge_remark_uses_challenge_auto_context_or_explicit_override(tmp_path, monkeypatch, level, effective):
    from test_challenge_screen import fake_generator, open_challenge, set_up, start
    app, _ = app_for(tmp_path, monkeypatch)
    app.settings.marking_strictness = level
    app.settings.ai_mark_model = 'codex:gpt-6.1-terra'
    fake_generator(monkeypatch)

    async def go():
        async with app.run_test(size=(100, 35)) as pilot:
            screen = await open_challenge(pilot, app)
            await set_up(pilot, screen)
            await start(pilot, screen)
            screen.fb = {'answer': '9 m', 'response': '6 m', 'correct': False}
            seen = []

            async def marker(prompt, **kwargs):
                seen.append(prompt)
                return None, ai.Result(ok=False)

            monkeypatch.setattr(app.ai, 'one_shot', marker)
            await screen.remark().wait()
            assert len(seen) == 1 and f'AI MARKING STRICTNESS: {effective}' in seen[0]
            assert screen.fb['correct'] is False
            await app.ai.close()
    asyncio.run(go())


@pytest.mark.parametrize('model', config.AI_MODELS)
def test_every_model_route_receives_policy_without_changing_rubric_and_local_cache_isolates_levels(
        tmp_path, monkeypatch, model):
    monkeypatch.setattr(local_models, 'available_models', lambda: tuple(local_models.LOCAL_MODELS))

    async def go():
        client = tutor_ai.TutorAI(tmp_path, binary='/missing/claude')
        seen = []
        source = {'points': [{'point': POINT, 'met': True, 'why': 'Weaker London dispersion forces.'}],
                  'feedback': 'Both ideas stated.'}
        original = deepcopy(source)

        async def answer(prompt, **kwargs):
            seen.append((prompt, kwargs))
            return source, ai.Result()

        if model in ('haiku', 'sonnet', 'opus'):
            async def claude_answer(self, prompt, **kwargs):
                return await answer(prompt, **kwargs)
            monkeypatch.setattr(ai.Claude, 'one_shot', claude_answer)
        elif model.startswith('codex:'):
            monkeypatch.setattr(client.codex, 'one_shot', answer)
        elif model.startswith('abacus:'):
            monkeypatch.setattr(client.abacus, 'one_shot', answer)
        else:
            monkeypatch.setattr(client.local, 'one_shot', answer)
        schema = prompts.local_judge_schema([POINT]) if local_models.is_local(model) else prompts.JUDGE
        for level in LEVELS:
            prompt = prompts.judge(STEM, [POINT], ANSWER, strictness=level, mode='review')
            data, result = await client.one_shot(prompt, schema=schema, model=model)
            assert ai.matches_points(data, [POINT]) and data['points'] == original['points']
            assert not result.performance.get('cached_reply')
            assert seen[-1][0] == prompt and seen[-1][1]['model'] == model
        assert len(seen) == len(LEVELS) and source == original
        if local_models.is_local(model):
            data, result = await client.one_shot(prompt, schema=schema, model=model)
            assert len(seen) == len(LEVELS) and result.performance['cached_reply']
        await client.close()
    asyncio.run(go())
