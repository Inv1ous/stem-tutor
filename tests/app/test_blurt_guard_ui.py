"""Protected blurt feedback must leave the learner's editor available."""
import asyncio
from copy import deepcopy

import pytest
from textual.widgets import Button, TextArea

from test_blurt_guards import SECRET_NOTE, SUBTOPIC, skipped_tutor
from test_tui import FAKE, shot
from tutor_app.app import TutorApp
from tutor_app.screens import BlurtScreen


@pytest.mark.parametrize("ended", [False, True])
def test_protected_blurt_keeps_draft_and_has_no_feedback_side_effects(tmp_path, monkeypatch, ended):
    tutor = skipped_tutor(tmp_path)
    if ended:
        tutor.end(abandoned=True)
    app = TutorApp(tutor.vault.root, claude_binary=FAKE, open_obsidian=False, seed=1)
    app.settings.ai = False
    notices = []
    notify = app.notify

    def record(message, **kwargs):
        notices.append(message)
        notify(message, **kwargs)

    monkeypatch.setattr(app, "notify", record)

    async def go():
        async with app.run_test(size=(80, 24), notifications=True) as pilot:
            screen = BlurtScreen(SUBTOPIC)
            app.push_screen(screen)
            await pilot.pause()
            editor = screen.query_one("#blurt", TextArea)
            editor.text = "I recall nothing yet."
            before_events = list(app.tutor.vault.events())
            before_now = (app.vault / "Now.md").read_bytes()
            guards = deepcopy(app.tutor.marking_guards())
            await pilot.press("ctrl+s")
            await pilot.pause()
            await shot(pilot, f"guarded-blurt-{'ended' if ended else 'live'}")
            assert app.screen is screen and editor.text == "I recall nothing yet." and editor.has_focus
            assert not getattr(screen, "checked", False)
            assert not screen.query_one("#check", Button).disabled
            assert len(screen.query(".entry")) == 1
            assert SECRET_NOTE not in str(screen.query(".entry").first().content.card)
            assert any("protected" in notice and "Retry" in notice for notice in notices)
            assert list(app.tutor.vault.events()) == before_events
            assert (app.vault / "Now.md").read_bytes() == before_now
            assert app.tutor.marking_guards() == guards
            await pilot.press("ctrl+s")  # a second attempt still leaves an editable draft
            await pilot.pause()
            assert not screen.query_one("#check", Button).disabled
            assert list(app.tutor.vault.events()) == before_events
            await app.ai.close()

    asyncio.run(go())
