"""Repeating Retry while already writing a retry must preserve its draft."""
import asyncio
from copy import deepcopy

from test_tui import app_for, shot
from tutor_app.panels import ChoicePanel, Confidence


def test_retry_shortcut_during_suspended_question_retry_keeps_the_answer(tmp_path, monkeypatch):
    app, _ = app_for(tmp_path, monkeypatch)
    app.settings.ai = False
    notices = []
    notify = app.notify

    def record(message, **kwargs):
        notices.append(message)
        notify(message, **kwargs)

    monkeypatch.setattr(app, "notify", record)

    async def go():
        async with app.run_test(size=(100, 30), notifications=True) as pilot:
            await pilot.pause()
            tutor = app.tutor
            menu = app.screen.query_one("#menu")
            menu.highlighted = [option.id for option in menu.options].index("learn")
            await pilot.press("enter")
            await pilot.pause()
            await pilot.press("enter")
            await pilot.pause()
            screen = app.screen
            await pilot.press("down", "enter")  # find and fill my gaps
            await pilot.pause()
            assert screen.view["kind"] == "mcq" and tutor.session["queue"]
            await pilot.press("0")
            await pilot.pause()
            await pilot.press("ctrl+u")  # queued questions are set aside for this retry
            await pilot.pause()
            assert tutor.session["suspended_for_retry"] and screen.view["kind"] == "mcq"
            panel = screen.query_one(ChoicePanel)
            await pilot.press("b")
            await pilot.pause()
            confidence = panel.query_one(Confidence)
            assert panel.choice == "B" and confidence.has_focus
            before_session = deepcopy(tutor.session)
            before_events = list(tutor.vault.events())
            before_now = (app.vault / "Now.md").read_bytes()
            before_bytes = {path: path.read_bytes() for path in
                            [tutor.session_path, *(tutor.vault.tutor / "events").glob("*.jsonl")]}
            await shot(pilot, "retry-draft-before-retry-shortcut")
            await pilot.press("ctrl+u")
            await pilot.pause()
            await shot(pilot, "retry-draft-after-retry-shortcut")
            assert screen.query_one(ChoicePanel) is panel
            assert panel.choice == "B" and confidence.has_focus
            assert tutor.session == before_session and list(tutor.vault.events()) == before_events
            assert (app.vault / "Now.md").read_bytes() == before_now
            assert all(path.read_bytes() == content for path, content in before_bytes.items())
            assert any("Finish the current activity" in message for message in notices)

            answer = tutor.session["presented"][str(screen.view["n"])]["inst"]["answer"]
            await pilot.press("escape", answer.lower(), "4")
            await pilot.pause()
            assert not tutor.session.get("skipped_answer_guards")
            assert len([event for event in tutor.vault.events() if event["type"] == "answer"]) == 2
            await pilot.press("ctrl+u")  # no active retry: suspended navigation remains available
            await pilot.pause()
            await pilot.click("#resume-suspended")
            await pilot.pause()
            assert not tutor.session.get("suspended_for_retry") and screen.view["kind"] == "numeric"
            await app.ai.close()

    asyncio.run(go())
