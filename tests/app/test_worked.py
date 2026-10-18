import asyncio

from test_tui import app_for
from tutor_app.panels import (ChoicePanel, ChoosePanel, ContinuePanel, ReflectPanel, TextPanel, TickPanel, ValuePanel,
                              WorkedPanel)


def test_the_last_step_of_a_worked_example_stays_until_you_continue(tmp_path, monkeypatch):
    """Asked by the learner: when the worked example's answer was revealed it went straight on to the next question, so there
    was no time to read it."""
    app, v = app_for(tmp_path, monkeypatch)

    async def go():
        async with app.run_test(size=(100, 40)) as pilot:
            await pilot.pause()
            await pilot.press("down", "enter", "enter")  # learn -> the only subtopic
            await pilot.pause()
            for _ in range(60):  # walk to the worked example
                scr = app.screen
                panel = next(iter(scr.query("#panel > *")), None) if scr.__class__.__name__ == "SessionScreen" else None
                if isinstance(panel, WorkedPanel):
                    break
                if isinstance(panel, ChoosePanel):
                    await pilot.press("down", "enter")
                elif isinstance(panel, ChoicePanel):
                    await pilot.press("b")
                    await pilot.pause()
                    await pilot.press("3")
                elif isinstance(panel, ValuePanel):
                    await pilot.press(*"42", "enter")
                    await pilot.pause()
                    if panel.query("#conf"):
                        await pilot.press("2")
                elif isinstance(panel, (ContinuePanel, TickPanel)):
                    panel.query("Button").first().press()
                elif isinstance(panel, ReflectPanel):
                    await pilot.press("1")
                elif isinstance(panel, TextPanel):
                    await pilot.press(*"it has a direction", "enter")
                await pilot.pause()
            assert isinstance(panel, WorkedPanel), type(panel)
            scr = app.screen
            total = len(scr.act["steps"])
            for n in range(1, total + 1):
                await pilot.press("enter")
                await pilot.pause()
                await pilot.pause()
            panel = next(iter(scr.query("#panel > *")))
            assert isinstance(panel, ContinuePanel), type(panel)  # waiting: not on to the next question
            assert scr.act["activity"] == "worked"
            assert "last step" in str(panel.query(".hint").first().render())
            aw = app.tutor.session["awaiting"]  # the engine is still waiting on this example, every step revealed
            assert aw["activity"] == "worked" and aw["revealed"] == total
            entries = list(scr.query("#log > .entry"))
            assert all(w.display for w in entries[-total:])  # the example's steps, the last one included, are showing
            await pilot.pause(0.5)  # and still there a moment later
            assert isinstance(next(iter(scr.query("#panel > *"))), ContinuePanel) and scr.act["activity"] == "worked"
            await pilot.press("enter")  # ⏎ is "Continue"
            await pilot.pause()
            await pilot.pause()
            assert scr.act["activity"] != "worked"
            await app.ai.close()
    asyncio.run(go())
