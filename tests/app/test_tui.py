import asyncio
import os
from pathlib import Path

import pytest

from fixtures import make_vault
from tutor_app.app import TutorApp
from tutor_app.panels import ChoicePanel, ContinuePanel, TickPanel, ValuePanel, TextPanel, WorkedPanel, ChoosePanel

FAKE = str(Path(__file__).with_name("fake_claude.py"))
SHOTS = os.environ.get("TUI_SHOTS")


def app_for(tmp_path, monkeypatch, mode="ok"):
    monkeypatch.setenv("FAKE_CLAUDE_MODE", mode)
    monkeypatch.setenv("STEM_TUTOR_NOW", "2026-09-29T17:00:00+08:00")
    v = make_vault(tmp_path)
    return TutorApp(v, claude_binary=FAKE, open_obsidian=False, seed=1), v


async def shot(pilot, name):
    if SHOTS:
        pilot.app.save_screenshot(path=SHOTS, filename=f"{name}.svg")


async def drive_lesson(pilot, app, max_steps=120):
    """Answer everything with keys: first option / 1 confidence, numbers typed, own words typed."""
    seen = []
    for _ in range(max_steps):
        await pilot.pause()
        scr = app.screen
        if scr.__class__.__name__ == "SummaryScreen":
            seen.append("summary")
            await shot(pilot, "summary")
            await pilot.press("enter")
            await pilot.pause()
            break
        panel = next(iter(scr.query("#panel > *")), None) if scr.__class__.__name__ == "SessionScreen" else None
        if panel is None:
            await pilot.pause(0.05)
            continue
        seen.append(type(panel).__name__)
        if isinstance(panel, ChoosePanel):
            await pilot.press("down", "enter")
        elif isinstance(panel, ChoicePanel):
            await shot(pilot, "mcq-" + str(len(seen)))
            if panel.choice is None:
                await pilot.press("b")
            await pilot.pause()
            await pilot.press("3")
        elif isinstance(panel, ValuePanel):
            await pilot.press(*"42", "enter")
            await pilot.pause()
            if panel.query("#conf"):
                await pilot.press("2")
        elif isinstance(panel, TickPanel):
            await shot(pilot, "tick-" + str(len(seen)))
            panel.query("Button").first().press()
        elif isinstance(panel, WorkedPanel):
            await pilot.press("enter")
        elif isinstance(panel, TextPanel):
            await pilot.press(*"it has a direction", "enter")
        elif isinstance(panel, ContinuePanel):
            panel.query("Button").first().press()
        await pilot.pause()
    return seen


def test_home_menu_and_a_whole_lesson_by_keyboard(tmp_path, monkeypatch):
    app, v = app_for(tmp_path, monkeypatch)

    async def go():
        async with app.run_test(size=(120, 40)) as pilot:
            await pilot.pause()
            await shot(pilot, "home")
            assert app.screen.__class__.__name__ == "HomeScreen"
            await pilot.press("enter")  # Learn a topic
            await pilot.pause()
            assert app.screen.__class__.__name__ == "PickerScreen"
            await pilot.press("enter")  # the only subtopic
            await pilot.pause()
            await shot(pilot, "session-start")
            seen = await drive_lesson(pilot, app)
            assert "summary" in seen and "ChoosePanel" in seen and "TickPanel" in seen
            assert app.screen.__class__.__name__ == "HomeScreen"
    asyncio.run(go())
    assert (v / "Now.md").exists() and list((v / "Lessons").glob("*.md")) and list((v / "My Notes").rglob("*.md"))


def test_chat_streams_an_ai_reply(tmp_path, monkeypatch):
    app, v = app_for(tmp_path, monkeypatch)

    async def go():
        async with app.run_test(size=(120, 40)) as pilot:
            await pilot.pause()
            menu = app.screen.query_one("#menu")
            menu.highlighted = [o.id for o in menu.options].index("chat")
            await pilot.press("enter")
            await pilot.pause()
            await pilot.press(*"why is velocity a vector", "enter")
            for _ in range(40):
                await pilot.pause(0.05)
                if app.ai.session.replies:
                    break
            await shot(pilot, "chat")
            assert app.ai.session.replies == 1 and app.ai.last.text.startswith("Reply 1")
            await app.ai.close()
    asyncio.run(go())


def test_ai_login_needed_is_explained_not_crashing(tmp_path, monkeypatch):
    app, v = app_for(tmp_path, monkeypatch, mode="login")

    async def go():
        async with app.run_test(size=(120, 40)) as pilot:
            await pilot.pause()
            menu = app.screen.query_one("#menu")
            idx = [o.id for o in menu.options].index("chat")
            menu.highlighted = idx
            await pilot.press("enter")
            await pilot.pause()
            await pilot.press(*"what is a vector", "enter")
            for _ in range(40):
                await pilot.pause(0.05)
            await shot(pilot, "chat-login")
            assert app.ai.status == "login" and "claude auth login" in app.ai.message
            assert len(app.screen.query(".entry")) >= 2  # your question + the explanation card
    asyncio.run(go())


def test_long_question_typed_then_self_marked(tmp_path, monkeypatch):
    app, v = app_for(tmp_path, monkeypatch)
    from tutor_app.panels import LongPanel

    async def go():
        async with app.run_test(size=(120, 40)) as pilot:
            await pilot.pause()
            menu = app.screen.query_one("#menu")
            menu.highlighted = [o.id for o in menu.options].index("long")
            await pilot.press("enter")
            await pilot.pause()
            await pilot.press("enter")  # the only subtopic
            await pilot.pause()
            panel = app.screen.query_one("#panel > *")
            assert isinstance(panel, LongPanel)
            await pilot.press(*"v = u + at = 19.6 m/s", "ctrl+s")
            await pilot.pause()
            tick = app.screen.query_one("#panel > *")
            assert isinstance(tick, TickPanel)
            await shot(pilot, "long-scheme")
            await pilot.press("tab")  # to the list
            tick.query_one("#ticks").select_all()
            tick.query("Button").first().press()
            await pilot.pause()
            evs = [e for e in app.tutor.vault.events() if e["type"] == "answer"]
            assert evs and evs[-1]["grade"]["score"] == 1.0
            await app.ai.close()
    asyncio.run(go())


def test_short_answer_self_judged_when_ai_is_off(tmp_path, monkeypatch):
    app, v = app_for(tmp_path, monkeypatch)
    app.settings.ai = False

    async def go():
        async with app.run_test(size=(120, 40)) as pilot:
            await pilot.pause()
            t = app.tutor
            t.start("review", minutes=10)
            item = {"id": "s1", "kcs": ["9702-2.1.1"], "kind": "short", "difficulty": 3, "marks": 2,
                    "stem": "Define displacement.",
                    "rubric": [{"point": "distance", "keywords": [["distance"]]}, {"point": "direction", "keywords": [["direction"]]}]}
            n = t._present(item, block="practice", phase=None)["n"]
            from tutor_app.screens import SessionScreen
            await app.push_screen(SessionScreen(None))
            await pilot.pause()
            await pilot.press(*"how far it moved", "enter")
            await pilot.pause()
            await pilot.press("3")
            await pilot.pause()
            tick = app.screen.query_one("#panel > *")
            assert isinstance(tick, TickPanel)
            tick.query_one("#ticks").select(tick.query_one("#ticks").get_option_at_index(0))
            tick.query("Button").first().press()
            await pilot.pause()
            ev = [e for e in t.vault.events() if e["type"] == "answer"][-1]
            assert ev["grade"]["score"] == 0.5
    asyncio.run(go())
