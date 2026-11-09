"""Earlier teaching stays folded until an unresolved skipped question is attempted."""
import asyncio
from copy import deepcopy

from test_tui import app_for, shot
from tutor_app.panels import ChoicePanel, ChoosePanel, ContinuePanel, TextPanel, TickPanel, ValuePanel, WorkedPanel


def test_earlier_does_not_restore_hidden_teaching_after_a_skipped_answer(tmp_path, monkeypatch):
    app, vault = app_for(tmp_path, monkeypatch)
    app.settings.ai = False

    async def go():
        async with app.run_test(size=(100, 30), notifications=True) as pilot:
            await pilot.pause()
            menu = app.screen.query_one("#menu")
            menu.reveal("learn")
            await pilot.press("enter")
            await pilot.pause()
            await pilot.press("enter")
            await pilot.pause()
            screen = app.screen
            for _ in range(50):
                panel = screen.showing
                if isinstance(panel, (ChoicePanel, ValuePanel)):
                    break
                if isinstance(panel, ChoosePanel):
                    await pilot.press("enter")  # learn from scratch
                elif isinstance(panel, (ContinuePanel, TickPanel)):
                    await pilot.click(panel.query("Button").first())
                elif isinstance(panel, WorkedPanel):
                    await pilot.press("enter")
                elif isinstance(panel, TextPanel):
                    panel.query_one("#text").text = "I can explain the idea in my own words."
                    await pilot.press("enter")
                else:
                    raise AssertionError((type(panel).__name__, screen.act))
                await pilot.pause()
            else:
                raise AssertionError("No question reached")
            hidden = [entry for entry in screen.query("#log > .entry") if not entry.display]
            assert hidden
            assert any("Displacement is a vector" in getattr(entry.content, "card", ("", "", ""))[2]
                       for entry in hidden)
            if isinstance(panel, ChoicePanel):
                await pilot.press("0")
            else:
                panel.query_one("#value").text = "?"
                await pilot.press("enter")
            await pilot.pause()
            assert app.tutor.marking_guards() and not app.tutor.session["presented"]
            await shot(pilot, "earlier-skipped-before")
            before_events = list(app.tutor.vault.events())
            before_now = (vault / "Now.md").read_bytes()
            before_guards = deepcopy(app.tutor.marking_guards())
            before_session = deepcopy(app.tutor.session)
            before_bytes = {path: path.read_bytes() for path in
                            [app.tutor.session_path, *(app.tutor.vault.tutor / "events").glob("*.jsonl")]}
            await pilot.press("ctrl+l")
            await pilot.pause()
            await shot(pilot, "earlier-skipped-after")
            assert not any(entry.display for entry in hidden)
            assert list(app.tutor.vault.events()) == before_events and (vault / "Now.md").read_bytes() == before_now
            assert app.tutor.marking_guards() == before_guards
            assert app.tutor.session == before_session
            assert all(path.read_bytes() == content for path, content in before_bytes.items())
            await pilot.press("ctrl+u")
            await pilot.pause()
            retry = screen.view["n"]
            answer = app.tutor.session["presented"][str(retry)]["inst"]["answer"]
            await pilot.press(answer.lower(), "4")
            await pilot.pause()
            assert not app.tutor.marking_guards()
            await pilot.press("ctrl+l")
            await pilot.pause()
            assert all(entry.display for entry in hidden)
            await app.ai.close()

    asyncio.run(go())
