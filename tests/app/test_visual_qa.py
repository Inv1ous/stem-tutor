"""Fixes from a visual QA pass over every screen in Night, Day and Classic at 60x24, 80x24 and 120x40."""
import asyncio

import pytest
from rich.text import Text

from test_tui import app_for
from tutor_app import cards, look


@pytest.fixture
def palette():
    yield look.use
    look.use("classic")  # the live palette is shared: leave it as every other test expects


def run(app, size, steps):
    async def go():
        async with app.run_test(size=size) as pilot:
            await pilot.pause()
            await steps(pilot)
            await app.ai.close()
    asyncio.run(go())


@pytest.mark.parametrize("name", ["night", "day"])
def test_a_card_subtitle_is_drawn_in_a_readable_grey_not_the_frame_colour(palette, name):
    palette(name)
    c = cards.card("tutor", "Title", "body", subtitle="second look")
    assert isinstance(c.subtitle, Text) and c.subtitle.plain == "second look"
    assert c.subtitle.style == look.PALETTES[name]["dim"] != look.PALETTES[name]["frame"]


def test_a_classic_card_subtitle_is_unchanged(palette):
    palette("classic")
    c = cards.card("tutor", "Title", "body", subtitle="second look")
    assert c.subtitle == "second look"
    assert cards.card("tutor", "Title", "body").subtitle is None
