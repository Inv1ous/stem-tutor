import asyncio

from test_tui import app_for
from tutor_app.panels import (ChoicePanel, ChoosePanel, ContinuePanel, ReflectPanel, TextPanel, TickPanel, ValuePanel,
                              WorkedPanel)


def test_a_chat_question_and_its_reply_are_on_the_now_page(tmp_path, monkeypatch):
    app, v = app_for(tmp_path, monkeypatch)

    async def go():
        async with app.run_test(size=(120, 40)) as pilot:
            await pilot.pause()
            menu = app.screen.query_one("#menu")
            menu.highlighted = [o.id for o in menu.options].index("chat")
            await pilot.press("enter")
            await pilot.pause()
            await pilot.press(*"why is velocity a vector", "enter")
            for _ in range(60):
                await pilot.pause(0.05)
                if app.ai.session.replies:
                    break
            await pilot.pause(0.2)
            now = (v / "Now.md").read_text()
            assert "why is velocity a vector" in now and app.ai.last.text in now  # the page has what the terminal has
            await app.ai.close()
    asyncio.run(go())


def test_an_ai_reply_in_a_lesson_is_on_the_now_page_even_with_answer_only_on(tmp_path, monkeypatch):
    """Asked by the learner: with the question hidden in the terminal (answer-only view) the reply was only in the terminal."""
    app, v = app_for(tmp_path, monkeypatch)

    async def go():
        async with app.run_test(size=(100, 40)) as pilot:
            await pilot.pause()
            app.settings.answer_only = True
            await pilot.press("down", "enter", "enter")  # learn -> the only subtopic
            await pilot.pause()
            for _ in range(60):  # to the first question in the typed-answer box
                panel = next(iter(app.screen.query("#panel > *")), None) if app.screen.__class__.__name__ == "SessionScreen" else None
                if isinstance(panel, ValuePanel):
                    break
                if isinstance(panel, ChoosePanel):
                    await pilot.press("down", "enter")
                elif isinstance(panel, ChoicePanel):
                    await pilot.press("b")
                    await pilot.pause()
                    await pilot.press("3")
                elif isinstance(panel, (ContinuePanel, TickPanel)):
                    panel.query("Button").first().press()
                elif isinstance(panel, ReflectPanel):
                    await pilot.press("1")
                elif isinstance(panel, WorkedPanel):
                    await pilot.press("enter")
                elif isinstance(panel, TextPanel):
                    await pilot.press(*"it has a direction", "enter")
                await pilot.pause()
            assert isinstance(panel, ValuePanel) and app.screen.has_class("answer-only")
            await pilot.press("ctrl+t")  # ask the tutor, as the terminal's hidden log would show it
            await pilot.pause()
            await pilot.press(*"why", "enter")
            for _ in range(80):
                await pilot.pause(0.05)
                if app.ai.session.replies:
                    break
            await pilot.pause(0.3)
            now = (v / "Now.md").read_text()
            assert "> [!quote] You\n> why" in now and app.ai.last.text in now  # the card as the terminal draws it
            await app.ai.close()
    asyncio.run(go())
