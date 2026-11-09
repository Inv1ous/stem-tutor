"""A checked blurt brings its recall result into view after the written draft."""
import asyncio

import pytest

from test_tui import app_for, shot


@pytest.mark.parametrize("size", [(80, 24), (140, 46)])
@pytest.mark.parametrize("long", [False, True], ids=["short-draft", "long-draft"])
def test_checked_blurt_recall_result_is_visible(tmp_path, monkeypatch, size, long):
    app, vault = app_for(tmp_path, monkeypatch)
    app.settings.ai = False
    draft = "Displacement is a vector with direction."
    if long:
        draft = "\n".join(f"{number}. {draft}" for number in range(1, 61))

    async def go():
        async with app.run_test(size=size) as pilot:
            await pilot.pause()
            menu = app.screen.query_one("#menu")
            menu.reveal("blurt")
            await pilot.press("enter")
            await pilot.pause()
            await pilot.press("enter")
            await pilot.pause()
            screen = app.screen
            screen.query_one("#blurt").text = draft
            await pilot.press("ctrl+s")
            await pilot.pause()
            suffix = f"{size[0]}x{size[1]}-{'long' if long else 'short'}"
            await shot(pilot, f"blurt-result-{suffix}")
            result = next(card for card in screen.query(".entry")
                          if card.content.card[1].startswith("You recalled"))
            log = screen.query_one("#log")
            assert log.scrollable_content_region.contains_region(result.region)
            events = [event for event in app.tutor.vault.events() if event["type"] == "blurt"]
            assert len(events) == 1
            assert all(line in (vault / "Now.md").read_text() for line in draft.splitlines())
            await pilot.press("escape")
            await pilot.pause()
            assert app.screen.__class__.__name__ == "HomeScreen" and app.is_running
            await app.ai.close()

    asyncio.run(go())
