"""Home topic metrics and wrapped names fit the actual sidebox width."""
import asyncio
from copy import deepcopy

import pytest
from rich.cells import cell_len
from rich.console import Console

from test_tui import app_for, shot


def topic_lines(lines):
    start = next(i for i, line in enumerate(lines) if "9702-2.1" in line)
    end = next((i for i in range(start + 1, len(lines)) if not lines[i].strip()), len(lines))
    return lines[start:end]


@pytest.mark.parametrize("size", [(80, 24), (84, 30), (100, 30), (120, 30)])
@pytest.mark.parametrize("resize", [False, True], ids=["startup", "resized"])
def test_home_topics_fit_the_sidebar_without_orphaning_names_or_counts(tmp_path, monkeypatch, size, resize):
    app, _ = app_for(tmp_path, monkeypatch)
    app.settings.ai = False

    async def go():
        async with app.run_test(size=(140, 46) if resize else size) as pilot:
            await pilot.pause()
            home = app.screen
            menu = home.query_one("#menu")
            menu.highlighted = [option.id for option in menu.options].index("learn")
            menu.focus()
            state, events = deepcopy(app.tutor.state), list(app.tutor.vault.events())
            if resize:
                await pilot.resize_terminal(*size)
            await pilot.pause(0.3)
            await shot(pilot, f"home-topic-fit-{size[0]}x{size[1]}-{'resized' if resize else 'startup'}")
            assert menu.has_focus and menu.get_option_at_index(menu.highlighted).id == "learn"
            stats = home.query_one("#stats")
            if size[0] == 80:
                assert not stats.display and home.query_one("#glance").display
                assert "0 due" in home.query_one("#glance").content.plain
            else:
                text = home.query_one("#stats-text")
                width = text.content_region.width
                raw = topic_lines(text.content.plain.splitlines())
                rendered = topic_lines([line.plain for line in text.content.wrap(Console(), width)])
                assert all(cell_len(line) <= width for line in raw)
                assert all(line.startswith("  ") for line in rendered)
                assert "Equations of motion" in " ".join(line.strip() for line in rendered)
                assert "0/2" in " ".join(raw) and "░" * 6 in " ".join(raw)
                assert text.content.plain.partition("Your topics\n")[2].count("0/2") == 3
                if size[0] == 120:
                    assert raw == ["  9702-2.1  ░░░░░░ 0/2   Equations of motion"]
                await pilot.press("tab", "pagedown")
                await pilot.pause()
                assert stats.has_focus
                before_scroll = stats.scroll_y
                home._draw_stats()
                await pilot.pause()
                assert stats.has_focus and stats.scroll_y == before_scroll
            assert app.tutor.state == state and list(app.tutor.vault.events()) == events
            await app.ai.close()

    asyncio.run(go())
