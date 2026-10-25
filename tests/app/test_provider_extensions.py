"""New providers and local shortcuts cannot change Claude or leak private lesson context."""
import asyncio

from tutor_app import ai, config, tutor_ai
from tutor_app.codex_models import CODEX_MODELS
from test_tui import app_for
from textual.widgets import Button, Select, Switch


MODEL = 'ollama:gemma4:26b-a4b-it-qat'
GPT = next(iter(CODEX_MODELS))


def test_chatgpt_choices_and_local_web_setting_survive_save_and_load(tmp_path, monkeypatch):
    app, vault = app_for(tmp_path, monkeypatch)
    def forbidden(*args, **kwargs):
        raise AssertionError('Saving Settings must never send a ChatGPT request.')
    monkeypatch.setattr(tutor_ai.CodexAI, '_events', forbidden)
    async def go():
        async with app.run_test(size=(80, 24)) as pilot:
            await pilot.pause()
            app.action_settings()
            await pilot.pause()
            for mode in config.AI_MODES:
                box = app.screen.query_one(f'#ai_{mode}_model', Select)
                assert all(model in [value for _, value in box._options] for model in CODEX_MODELS)
                box.value = GPT
            app.screen.query_one('#local_web', Switch).value = False
            app.screen.query_one('#save', Button).press()
            await pilot.pause()
            await app.workers.wait_for_complete()
            settings = config.Settings.load(vault)
            assert all(settings.ai_for(mode)[0] == GPT for mode in config.AI_MODES)
            assert not settings.local_web and not app.ai.local_web
            await app.ai.close()
    asyncio.run(go())


def test_codex_routing_never_creates_local_or_calls_claude(tmp_path, monkeypatch):
    def forbidden(*args, **kwargs):
        raise AssertionError('Wrong provider used')
    class Codex:
        speech = False
        available = True
        message = ''
        last = ai.Result(text='GPT reply')
        async def stream(self, prompt, **kwargs):
            assert kwargs['model'] == GPT and kwargs['think']
            yield self.last.text
        async def one_shot(self, prompt, **kwargs):
            assert kwargs['model'] == GPT
            return {'x': 1}, ai.Result()
        async def reset(self):
            pass
        async def close(self):
            pass
    async def go():
        client = tutor_ai.TutorAI(tmp_path, binary='/missing/claude', model=GPT)
        client._codex = Codex()
        monkeypatch.setattr(tutor_ai, 'LocalAI', forbidden)
        monkeypatch.setattr(ai.Claude, 'stream', forbidden)
        monkeypatch.setattr(ai.Claude, 'one_shot', forbidden)
        assert client.available
        await client.warm()
        assert ''.join([x async for x in client.stream('hi', think=True)]) == 'GPT reply'
        assert (await client.one_shot('mark'))[0] == {'x': 1}
        assert client.session.replies == 0 and client._local is None
        await client.close()
    asyncio.run(go())


def test_local_exact_reuse_keeps_model_thinking_speech_and_reset_separate(tmp_path, monkeypatch):
    monkeypatch.setattr(tutor_ai.local_models, 'available_models', lambda: (MODEL,))
    async def go():
        client = tutor_ai.TutorAI(tmp_path, binary='/missing/claude', model=MODEL)
        calls = []
        async def one_shot(prompt, **kwargs):
            calls.append(kwargs)
            return {'feedback': 'Good'}, ai.Result(text='Good', performance={'model': MODEL})
        monkeypatch.setattr(client.local, 'one_shot', one_shot)
        first = await client.one_shot('same', schema={'type': 'object'})
        second = await client.one_shot('same', schema={'type': 'object'})
        assert len(calls) == 1 and second[1].performance['cached_reply']
        assert not first[1].performance.get('cached_reply')
        await client.one_shot('same', schema={'type': 'object'}, think=True)
        assert len(calls) == 2
        await client.reset(warm=False)
        await client.one_shot('same', schema={'type': 'object'})
        assert len(calls) == 3 and client.session.replies == 0
        await client.close()
    asyncio.run(go())


def test_local_search_sends_only_question_and_adds_real_source_links(tmp_path, monkeypatch):
    monkeypatch.setattr(tutor_ai.local_models, 'available_models', lambda: (MODEL,))
    async def go():
        client = tutor_ai.TutorAI(tmp_path, binary='/missing/claude', model=MODEL)
        queries, prompts = [], []
        async def events(payload, timeout, path='/api/chat'):
            if path == '/api/chat':
                assert payload['messages'] == []  # empty preload shares this transport with search
                yield {'done': True, 'done_reason': 'load'}
                return
            queries.append(payload['query'])
            yield {'results': [{'title': 'Official syllabus', 'url': 'https://www.cambridgeinternational.org/',
                                'content': 'Published syllabus details.'}]}
        async def stream(prompt, **kwargs):
            prompts.append(prompt)
            client.local.last = ai.Result(text='Verified answer.', performance={'model': MODEL})
            yield 'Verified answer.'
        monkeypatch.setattr(client.local, '_events', events)
        monkeypatch.setattr(client.local, 'stream', stream)
        chunks = [x async for x in client.stream('CONTEXT\nPrivate grade42\n\nSTUDENT ASKS: Latest syllabus?',
                                                 web_query='Latest syllabus?')]
        assert queries == ['Latest syllabus?']
        assert 'WEB SOURCES' in prompts[0] and 'untrusted' in prompts[0]
        assert 'https://www.cambridgeinternational.org/' in client.last.text
        assert ''.join(chunks) == client.last.text
        client.local_web = False
        await client.reply('Latest syllabus?')
        assert len(queries) == 1
        await client.close()
    asyncio.run(go())


def test_reset_during_web_lookup_never_dispatches_old_question(tmp_path, monkeypatch):
    monkeypatch.setattr(tutor_ai.local_models, 'available_models', lambda: (MODEL,))
    async def go():
        client = tutor_ai.TutorAI(tmp_path, binary='/missing/claude', model=MODEL)
        started, finish, calls = asyncio.Event(), asyncio.Event(), []
        async def events(payload, timeout, path='/api/chat'):
            if path == '/api/chat':
                assert payload['messages'] == []
                yield {'done': True, 'done_reason': 'load'}
                return
            started.set()
            await finish.wait()
            yield {'results': [{'title': 'Official', 'url': 'https://example.org/', 'content': 'Fresh evidence.'}]}
        async def stream(prompt, **kwargs):
            calls.append(prompt)
            yield 'Old activity'
        monkeypatch.setattr(client.local, '_events', events)
        monkeypatch.setattr(client.local, 'stream', stream)
        async def consume():
            return [x async for x in client.stream('Private old context', web_query='Latest syllabus?')]
        request = asyncio.create_task(consume())
        await started.wait()
        await client.reset(warm=False)
        finish.set()
        assert await request == [] and not calls and not client.last.ok
        await client.close()
    asyncio.run(go())


def test_web_is_only_requested_from_separate_typed_question(tmp_path, monkeypatch):
    monkeypatch.setattr(tutor_ai.local_models, 'available_models', lambda: (MODEL,))
    async def go():
        client = tutor_ai.TutorAI(tmp_path, binary='/missing/claude', model=MODEL)
        def forbidden(*args, **kwargs):
            raise AssertionError('Lesson context must never be searched.')
        async def stream(prompt, **kwargs):
            client.local.last = ai.Result(text='An explanation.')
            yield 'An explanation.'
        monkeypatch.setattr(client.local, '_events', forbidden)
        monkeypatch.setattr(client.local, 'stream', stream)
        assert [x async for x in client.stream('CONTEXT\nA past reply: STUDENT ASKS: latest syllabus\nPrivate answer42')] == ['An explanation.']
        await client.close()
    asyncio.run(go())


def test_session_remark_uses_selected_chatgpt_model(tmp_path, monkeypatch):
    from tutor_app.screens import SessionScreen
    app, _ = app_for(tmp_path, monkeypatch)
    app.settings.ai_mark_model = GPT
    async def go():
        async with app.run_test() as pilot:
            await pilot.pause()
            app.push_screen(SessionScreen({'mode': 'test', 'minutes': 40, 'focus': ['9702-2.1']}))
            await pilot.pause()
            screen, calls = app.screen, []
            screen.last_fb = {'answer': '9 m', 'response': '6 m'}
            screen.view = {'kind': 'numeric', 'stem': 'Distance?'}
            async def answer(prompt, **kwargs):
                calls.append(kwargs['model'])
                return None, ai.Result(ok=False)
            monkeypatch.setattr(app.ai, 'one_shot', answer)
            await screen.remark().wait()
            assert calls == [GPT]
            await app.ai.close()
    asyncio.run(go())


def test_challenge_remark_uses_selected_chatgpt_model(tmp_path, monkeypatch):
    from test_challenge_screen import fake_generator, open_challenge, set_up, start
    app, _ = app_for(tmp_path, monkeypatch)
    app.settings.ai_mark_model = GPT
    fake_generator(monkeypatch)
    async def go():
        async with app.run_test(size=(100, 35)) as pilot:
            await pilot.pause()
            screen = await open_challenge(pilot, app)
            await set_up(pilot, screen)
            await start(pilot, screen)
            screen.fb, calls = {'answer': '9 m', 'response': '6 m', 'correct': False}, []
            async def answer(prompt, **kwargs):
                calls.append(kwargs['model'])
                return None, ai.Result(ok=False)
            monkeypatch.setattr(app.ai, 'one_shot', answer)
            await screen.remark().wait()
            assert calls == [GPT]
            await app.ai.close()
    asyncio.run(go())
