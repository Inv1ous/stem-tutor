"""Local marking and question preparation keep the focused diagram without changing cloud calls."""
import asyncio

import pytest

from test_tui import app_for
from tutor_app import ai, local_models, prompts
from tutor_app.screens import ChatScreen, SessionScreen


@pytest.fixture(autouse=True)
def local_without_loading(monkeypatch):
    monkeypatch.setattr(local_models, "available_models", lambda: tuple(local_models.LOCAL_MODELS))


@pytest.mark.parametrize("model,remark_model,remark_think", [
    ("ollama:phi4-mini:3.8b", "ollama:phi4-mini:3.8b", False),
    ("ollama:qwen3.5:9b", "ollama:qwen3.5:9b", True),
    ("haiku", "sonnet", True),
    ("codex:gpt-6-luna", "codex:gpt-6-luna", True),
])
def test_marking_calls_include_focused_image_only_for_local_provider(
        tmp_path, monkeypatch, model, remark_model, remark_think):
    app, vault = app_for(tmp_path, monkeypatch)
    app.settings.ai_mark_model = model
    monkeypatch.setattr(app, "prepare_local_ai", lambda mode: None)
    image = tmp_path / "question.png"
    image.write_bytes(b"diagram fixture")
    monkeypatch.setattr(prompts, "focus_image", lambda tutor: image)

    async def go():
        async with app.run_test() as pilot:
            await pilot.pause()
            screen = SessionScreen({"mode": "test", "minutes": 40, "focus": ["9702-2.1"]})
            app.push_screen(screen)
            await pilot.pause()
            monkeypatch.setattr(app, "ai_available", lambda mode="ask": True)
            calls = []

            async def one_shot(prompt, **kwargs):
                calls.append(kwargs)
                return None, ai.Result(ok=False)
            monkeypatch.setattr(app.ai, "one_shot", one_shot)
            await screen.judge_short(screen.view, {"your": "working", "entry": "1 working"},
                                     {"rubric": ["a point"]}).wait()
            screen.scheme, screen.long_text = [{"i": 0, "mark": "M1", "point": "a point"}], "working"
            await screen.ai_check_long({"ticked": []}).wait()
            screen.last_fb = {"answer": "9 m", "response": "6 m"}
            await screen.remark().wait()
            assert len(calls) == 3
            if local_models.is_local(model):
                assert all(call.get("image") == image for call in calls)
                for call, expected in zip(calls[:2], (["a point"], ["M1 a point"])):
                    schema = call["schema"]["properties"]["points"]
                    assert schema["items"]["properties"]["point"]["enum"] == expected
                    assert schema["minItems"] == schema["maxItems"] == 1
            else:
                assert all("image" not in call for call in calls)
                assert calls[0]["schema"] is prompts.JUDGE and calls[1]["schema"] is prompts.JUDGE
            assert "enum" not in prompts.JUDGE["properties"]["points"]["items"]["properties"]["point"]
            assert calls[-1]["model"] == remark_model and calls[-1]["think"] is remark_think
            assert "diagram fixture" not in (vault / "Now.md").read_text()
            await app.ai.close()
    asyncio.run(go())


def test_new_image_question_prepares_text_only_marking_first_once_and_ignores_stale_views(tmp_path, monkeypatch):
    app, _ = app_for(tmp_path, monkeypatch)
    calls = []
    monkeypatch.setattr(app, "prepare_local_ai", calls.append)
    app.settings.ai_mark_model = app.settings.ai_ask_model = "ollama:phi4-mini:3.8b"

    async def go():
        async with app.run_test() as pilot:
            await pilot.pause()
            screen = SessionScreen({"mode": "test", "minutes": 40, "focus": ["9702-2.1"]})
            app.push_screen(screen)
            await pilot.pause()
            calls.clear()
            view = {**screen.view, "n": 90, "image": "Assets/question.png"}
            screen.ask_question(view)
            await pilot.pause()
            assert calls == ["mark"]
            screen.ask_question(dict(view))
            await pilot.pause()
            assert calls == ["mark"]
            app.settings.ai_mark_model = "ollama:qwen3.5:9b"
            screen.ask_question({**view, "n": 91})
            await pilot.pause()
            assert calls == ["mark", "ask"]
            screen.ask_question({**view, "n": 92})
            screen.ask_question({**view, "n": 93, "image": None})
            await pilot.pause()
            assert calls == ["mark", "ask"]
            app.settings.ai_ask_model = "haiku"
            screen.ask_question({**view, "n": 94})
            await pilot.pause()
            assert calls == ["mark", "ask"]
            await app.ai.close()
    asyncio.run(go())


def test_challenge_local_diagrams_reach_explain_and_non_thinking_remark(tmp_path, monkeypatch):
    import copy
    from test_challenge_screen import fake_generator, open_challenge, set_up, start
    app, _ = app_for(tmp_path, monkeypatch)
    app.settings.ai_mark_model = 'ollama:phi4-mini:3.8b'
    app.settings.ai_explain_model = 'ollama:qwen3.5:4b'
    fake_generator(monkeypatch)
    image=tmp_path/'challenge.png'
    image.write_bytes(b'pixels')
    async def go():
        async with app.run_test(size=(100,35)) as pilot:
            await pilot.pause()
            screen=await open_challenge(pilot,app)
            await set_up(pilot,screen)
            await start(pilot,screen)
            screen.set.questions[screen.i] = copy.deepcopy(screen.set.questions[screen.i])
            screen.set.questions[screen.i]['item']['image']=str(image)
            screen.fb={'answer':'9 m','response':'6 m','correct':False}
            seen=[]
            async def mark(prompt,**kwargs):
                seen.append(kwargs)
                return None,ai.Result(ok=False)
            async def explain(prompt,**kwargs):
                seen.append(kwargs)
                app.ai.last=ai.Result(text='Read the labelled axes.')
                yield app.ai.last.text
            monkeypatch.setattr(app.ai,'one_shot',mark)
            monkeypatch.setattr(app.ai,'stream',explain)
            await screen.remark().wait()
            assert seen[-1]['image']==image and seen[-1]['think'] is False
            await screen.explain().wait()
            assert seen[-1]['image']==image
            await app.ai.close()
    asyncio.run(go())


@pytest.mark.parametrize("model", ["ollama:phi4-mini:3.8b", "ollama:qwen3.5:9b", "haiku", "codex:gpt-6-luna"])
def test_menu_chat_passes_focused_image_only_to_local_models(tmp_path, monkeypatch, model):
    app, _ = app_for(tmp_path, monkeypatch)
    app.settings.ai_ask_model = model
    monkeypatch.setattr(app, "prepare_local_ai", lambda mode: None)
    image = tmp_path / "paused-question.png"
    image.write_bytes(b"paused diagram")
    monkeypatch.setattr(prompts, "focus_image", lambda tutor: image)

    async def go():
        async with app.run_test() as pilot:
            await pilot.pause()
            screen = ChatScreen()
            app.push_screen(screen)
            await pilot.pause()
            monkeypatch.setattr(app, "ai_available", lambda mode="ask": True)
            monkeypatch.setattr(app.tutor, "ai_help", lambda **kwargs: {})
            calls = []

            async def stream(prompt, **kwargs):
                calls.append(kwargs)
                app.ai.last = ai.Result(ok=False, message="Fixture reply")
                if False:
                    yield ""
            monkeypatch.setattr(app.ai, "stream", stream)
            await screen.reply("What does the diagram show?").wait()
            assert len(calls) == 1
            if local_models.is_local(model):
                assert calls[0]["image"] == image
            else:
                assert "image" not in calls[0]
            await app.ai.close()
    asyncio.run(go())
