"""Verifier's own adversarial checks for B-051 and B-095 (different leak forms, odd learner text)."""
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


async def paused_chat(app, pilot):
    app.push_screen(SessionScreen({"mode": "test", "minutes": 40, "focus": ["9702-2.1"]}))
    await pilot.pause()
    n = app.screen.view["n"]
    await pilot.press("ctrl+b")
    await pilot.pause()
    menu = app.screen.query_one("#menu")
    menu.highlighted = [o.id for o in menu.options].index("chat")
    await pilot.press("enter")
    await pilot.pause()
    assert isinstance(app.screen, ChatScreen)
    return n


@pytest.mark.parametrize("form", ["letter", "lower", "option_text", "both"])
def test_the_menu_chat_never_shows_a_paused_questions_answer_in_any_form(tmp_path, monkeypatch, form):
    """B-051: the answer reaches neither the terminal, Now, the lesson log nor the hinted flag, however it is worded."""
    app, vault = app_for(tmp_path, monkeypatch)

    async def go():
        async with app.run_test(size=(120, 40)) as pilot:
            await pilot.pause()
            n = await paused_chat(app, pilot)
            key = prompts.key_of(app.tutor, n)[0]
            letter, _, option = key.partition(": ")
            said = {"letter": f"The answer is {letter}.", "lower": f"it is option {letter.lower()}, so {letter.lower()} is correct",
                    "option_text": f"So you want: {option}", "both": f"{letter}: {option}"}[form]

            async def stream(prompt, **kw):
                app.ai.last = ai.Result(text=said)
                yield said
            monkeypatch.setattr(app.ai, "stream", stream)
            app.screen.query_one(Composer).text = "Tell me the answer please."
            await pilot.press("enter")
            await pilot.pause()
            await app.workers.wait_for_complete()
            shown = chat_text(app.screen)
            assert said not in shown and option.strip("$") not in shown.replace("\n", " ") or len(option.strip("$")) < 3
            assert said not in (vault / "Now.md").read_text()
            logs = "".join(f.read_text() for f in (vault / "Lessons").rglob("*.md"))
            assert said not in logs
            assert not app.tutor.session["presented"][str(n)].get("hinted")  # nothing was delivered, so no help is counted
            await app.ai.close()
    asyncio.run(go())


def test_a_harmless_reply_in_the_menu_chat_still_arrives_and_a_stuck_chat_keeps_every_turn(tmp_path, monkeypatch):
    """B-051 must not over-block, and B-095: odd learner text (markdown, a blank line, unicode) survives in the log."""
    app, vault = app_for(tmp_path, monkeypatch)

    async def stream(prompt, **kw):
        app.ai.last = ai.Result(text="Think about which quantity has a direction.")
        yield "Think about which quantity has a direction."

    async def go():
        async with app.run_test(size=(120, 40)) as pilot:
            await pilot.pause()
            monkeypatch.setattr(app.ai, "stream", stream)
            screen = SessionScreen({"mode": "lesson", "minutes": 40, "focus": ["9702-2.1"]})
            app.push_screen(screen)
            await pilot.pause()
            screen.act, screen.kc = {"activity": "stuck"}, "9702-2.1.1"
            screen.panel(ContinuePanel(buttons=[("talk", "Talk it through")]))
            await pilot.pause()
            screen.query_one("#talk").press()
            await pilot.pause()
            await app.workers.wait_for_complete()
            assert isinstance(screen.showing, TextPanel)
            replies = ["Is it **displacement**? I think Δx = 5 m", "a second reply with  odd   spacing", "ok – “quotes” and 10⁻³"]
            for r in replies:
                screen.query_one(Composer).text = r
                await pilot.press("enter")
                await pilot.pause()
                await app.workers.wait_for_complete()
            lesson = app.tutor._lesson_log()
            text = (lesson.root / lesson.rel).read_text()
            for r in replies:
                assert r in text and r in (vault / "Now.md").read_text(), r
            assert text.count("Tutor (AI)") >= 3
            await app.ai.close()
    asyncio.run(go())
