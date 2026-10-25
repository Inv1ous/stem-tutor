"""Background work retains the original Claude defaults when cloud models are selected."""
import asyncio

import pytest
from textual.widgets import Button

from test_tui import app_for
from tutor_app import ai, codex_models, local_models, prompts
from tutor_app.screens import InsightsScreen, SessionScreen


@pytest.mark.parametrize("ask,explain,want_model,want_think", [
    ("haiku", "opus", None, False),
    ("sonnet", "haiku", None, False),
    ("opus", "sonnet", None, False),
    ("haiku", "ollama:qwen3.5:9b", "ollama:qwen3.5:9b", True),
    ("ollama:qwen3.5:9b", "sonnet", "sonnet", False),
    ("haiku", "codex:gpt-6.1-sol", "codex:gpt-6.1-sol", True),
    ("codex:gpt-6.1-sol", "sonnet", "sonnet", False),
])
def test_cards_and_profiles_preserve_cloud_defaults(tmp_path, monkeypatch, ask, explain, want_model, want_think):
    app, _ = app_for(tmp_path, monkeypatch)
    app.settings.ai_ask_model = ask
    app.settings.ai_explain_model = explain
    app.settings.ai_explain_think = True
    monkeypatch.setattr(app, "prepare_local_ai", lambda mode: None)

    async def go():
        async with app.run_test(size=(100, 35)) as pilot:
            await pilot.pause()
            seen = []

            async def one_shot(prompt, schema=None, model=None, think=False, **kwargs):
                seen.append((schema, model, think))
                return {"motivate": "Why it matters", "establish": "How it works", "note": "Remember this",
                        "summary": "Keep practising."}, ai.Result()

            monkeypatch.setattr(app.ai, "one_shot", one_shot)
            app.push_screen(SessionScreen({"mode": "test", "minutes": 40, "focus": ["9702-2.1"]}))
            await pilot.pause()
            await app.workers.wait_for_complete()
            seen.clear()
            worker = app.screen._write_cards([next(iter(app.tutor.packs.kcs))])
            await worker.wait()
            assert seen == [(prompts.CARD, want_model, want_think)]
            app.pop_screen()
            app.push_screen(InsightsScreen())
            await pilot.pause()
            seen.clear()
            await app.screen._summarise().wait()
            profile_think = want_think if local_models.is_local(want_model) or codex_models.is_codex(want_model) else False
            assert seen == [(prompts.PROFILE, want_model, profile_think)]
            await app.ai.close()

    asyncio.run(go())


def test_switching_settings_to_cloud_releases_only_the_local_client(tmp_path, monkeypatch):
    app, _ = app_for(tmp_path, monkeypatch)

    async def go():
        async with app.run_test() as pilot:
            await pilot.pause()
            await app.ai.warm()
            proc = app.ai.proc
            assert proc is not None
            closed = []
            started, finish = asyncio.Event(), asyncio.Event()

            class Local:
                async def close(self):
                    started.set()
                    await finish.wait()  # cleanup must survive Settings being dismissed
                    closed.append(True)

                async def reset(self):
                    pass

            app.ai._local = Local()
            app.action_settings()
            await pilot.pause()
            app.screen.query_one("#save", Button).press()
            await pilot.pause()
            await asyncio.wait_for(started.wait(), 1)
            finish.set()
            await app.workers.wait_for_complete()
            assert closed == [True]
            assert app.ai._local is None
            assert app.ai.proc is proc and proc.returncode is None
            await app.ai.close()

    asyncio.run(go())
