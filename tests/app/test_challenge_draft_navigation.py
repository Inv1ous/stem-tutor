"""Challenge leave confirmation keeps a typed answer and its editing position."""
import asyncio

import pytest
from textual.document._document import Selection

from test_challenge_screen import fake_generator, open_challenge, set_up, start, typed
from test_tui import app_for, shot
from tutor_app.panels import Composer


@pytest.mark.parametrize("key", ["escape", "ctrl+b", "ctrl+q"])
@pytest.mark.parametrize("size", [(80, 24), (140, 46)])
def test_keep_writing_preserves_challenge_answer_selection_and_focus(tmp_path, monkeypatch, key, size):
    app, _ = app_for(tmp_path, monkeypatch)
    fake_generator(monkeypatch, questions=[typed(1)])

    async def go():
        async with app.run_test(size=size) as pilot:
            await pilot.pause()
            screen = await open_challenge(pilot, app)
            await set_up(pilot, screen, "1 question on 9702-2.1")
            await start(pilot, screen)
            composer = screen.query_one("#value", Composer)
            composer.text = "9.0 m"
            composer.selection = Selection((0, 0), (0, 3))
            composer.focus()
            before_events = list(app.tutor.vault.events())
            await pilot.press(key)
            await pilot.pause()
            assert app.screen.__class__.__name__ == "ConfirmScreen"
            await pilot.press("down", "enter")
            await pilot.pause()
            await shot(pilot, f"challenge-kept-draft-{key.replace('+', '-')}-{size[0]}x{size[1]}")
            assert app.screen is screen and composer.text == "9.0 m" and composer.has_focus
            assert composer.selection == Selection((0, 0), (0, 3))
            assert not screen.set.answers and screen.i == 0 and screen.fb is None
            assert list(app.tutor.vault.events()) == before_events
            await pilot.press("end", "enter")
            await pilot.pause()
            assert screen.fb["response"] == "9.0 m" and screen.fb["correct"]
            assert len(screen.set.answers) == 1
            await app.ai.close()

    asyncio.run(go())
