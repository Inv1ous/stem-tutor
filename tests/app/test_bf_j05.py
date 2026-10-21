from __future__ import annotations

import asyncio
import io

import pytest
from rich.console import Console

from test_tui import app_for
from tutor_app import ai, prompts
from tutor_app.panels import Composer, ContinuePanel, TextPanel
from tutor_app.screens import ChatScreen, SessionScreen


def chat_text(screen) -> str:
    console = Console(file=io.StringIO(), record=True, width=120)
    for entry in screen.query("#log .entry"):
        console.print(entry.content)
    return console.export_text()


async def paused_chat(app, pilot, unassisted: bool = True):
    app.push_screen(SessionScreen({"mode": "test", "minutes": 40, "focus": ["9702-2.1"]}))
    await pilot.pause()
    n = app.screen.view["n"]
    p = app.tutor.session["presented"][str(n)]
    assert p["unassisted"]
    p["unassisted"] = unassisted
    await pilot.press("ctrl+b")
    await pilot.pause()
    menu = app.screen.query_one("#menu")
    menu.highlighted = [o.id for o in menu.options].index("chat")
    await pilot.press("enter")
    await pilot.pause()
    assert isinstance(app.screen, ChatScreen)
    return n, p


def test_menu_chat_refuses_help_on_a_paused_no_help_question(tmp_path, monkeypatch):
    """B-051: returning to the menu must not bypass a no-help check."""
    app, vault = app_for(tmp_path, monkeypatch)

    async def go():
        async with app.run_test(size=(120, 40)) as pilot:
            await pilot.pause()
            n, p = await paused_chat(app, pilot)
            answer = f"The answer is {prompts.key_of(app.tutor, n)[0]}."

            async def fake_stream(prompt, **kwargs):
                app.ai.last = ai.Result(text=answer)
                yield answer

            monkeypatch.setattr(app.ai, "stream", fake_stream)
            app.screen.query_one(Composer).text = "Please help me."
            await pilot.press("enter")
            await pilot.pause()
            await app.workers.wait_for_complete()
            assert "No help on this one" in chat_text(app.screen)
            assert answer not in chat_text(app.screen)
            assert answer not in (vault / "Now.md").read_text()
            assert not p["hinted"]
            await app.ai.close()

    asyncio.run(go())


@pytest.mark.parametrize("reply_kind", ["answer", "speech", "hint", "failure"])
def test_menu_chat_guards_answers_and_counts_only_delivered_help(tmp_path, monkeypatch, reply_kind):
    """B-051: paused practice questions retain the answer guard and assistance tracking."""
    app, vault = app_for(tmp_path, monkeypatch)

    async def go():
        async with app.run_test(size=(120, 40)) as pilot:
            await pilot.pause()
            n, p = await paused_chat(app, pilot, unassisted=False)
            answer = f"The answer is {prompts.key_of(app.tutor, n)[0]}."
            assert ai.leaks(answer, *prompts.key_of(app.tutor, n))
            hint = "Think about the units."
            chunk = answer if reply_kind == "answer" else hint
            result = ai.Result(text=chunk, speech=answer if reply_kind == "speech" else "")
            if reply_kind == "failure":
                result = ai.Result(ok=False, status="login", message="Sign in first.")
            streamed = asyncio.Event()
            finish = asyncio.Event()

            async def fake_stream(prompt, **kwargs):
                yield chunk
                streamed.set()
                await finish.wait()
                app.ai.last = result

            monkeypatch.setattr(app.ai, "stream", fake_stream)
            app.screen.query_one(Composer).text = "Please help me."
            await pilot.press("enter")
            await pilot.pause()
            await asyncio.wait_for(streamed.wait(), 5)
            partial = chat_text(app.screen)
            finish.set()
            await app.workers.wait_for_complete()
            await pilot.pause()
            assert chunk not in partial  # no unchecked text flashes on screen
            shown = chat_text(app.screen)
            now = (vault / "Now.md").read_text()
            assert answer not in shown and answer not in now
            assert answer not in app.screen.readable
            assert p["hinted"] is (reply_kind == "hint")
            if reply_kind in ("answer", "speech"):
                assert "Held back" in now
            elif reply_kind == "hint":
                assert hint in shown and hint in now
            else:
                assert "Sign in first." in shown and "Sign in first." in now
            await app.ai.close()

    asyncio.run(go())


def test_stuck_chat_saves_each_learner_reply_with_the_tutors_reply(tmp_path, monkeypatch):
    """B-095: learner turns in a stuck conversation survive in the lesson and Now."""
    app, vault = app_for(tmp_path, monkeypatch)

    async def fake_stream(prompt, **kwargs):
        text = "Which part would you change?"
        app.ai.last = ai.Result(text=text)
        yield text

    async def go():
        async with app.run_test(size=(120, 40)) as pilot:
            await pilot.pause()
            monkeypatch.setattr(app.ai, "stream", fake_stream)
            screen = SessionScreen({"mode": "lesson", "minutes": 40, "focus": ["9702-2.1"]})
            app.push_screen(screen)
            await pilot.pause()
            screen.act = {"activity": "stuck"}
            screen.kc = "9702-2.1.1"
            screen.panel(ContinuePanel(buttons=[("talk", "Talk it through")]))
            await pilot.pause()
            screen.query_one("#talk").press()
            await pilot.pause()
            await app.workers.wait_for_complete()
            assert isinstance(screen.showing, TextPanel)
            replies = ["I forgot to consider direction.", "The direction changes during the lap."]
            for reply in replies:
                screen.query_one(Composer).text = reply
                await pilot.press("enter")
                await pilot.pause()
                await app.workers.wait_for_complete()
            lesson = app.tutor._lesson_log()
            transcript = (lesson.root / lesson.rel).read_text()
            now = (vault / "Now.md").read_text()
            for reply in replies:
                assert f"> [!quote] You\n> {reply}" in transcript
                assert reply in now
                assert transcript.index(reply) < transcript.index("Which part would you change?", transcript.index(reply))
            await app.ai.close()

    asyncio.run(go())

