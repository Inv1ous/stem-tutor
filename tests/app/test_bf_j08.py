from __future__ import annotations

import asyncio

import pytest
from textual.widgets import Markdown

from test_picker import crowd
from test_tui import app_for
from tutor_app import ai as ai_mod
from tutor_app.panels import TickPanel
from tutor_app.screens import ConfirmScreen, HomeScreen, PickerScreen, SessionScreen, SummaryScreen


@pytest.mark.parametrize("in_flight", [False, True])
def test_leaving_an_unmarked_short_answer_asks_before_losing_it(tmp_path, monkeypatch, in_flight: bool) -> None:
    """B-121: submitted wording and ticks need protection, including during the AI check."""
    app, _ = app_for(tmp_path, monkeypatch)
    app.settings.ai = in_flight

    async def go() -> None:
        release = asyncio.Event()
        started = asyncio.Event()

        async def judge(*args, **kwargs) -> tuple[None, ai_mod.Result]:
            started.set()
            await release.wait()
            return None, ai_mod.Result()

        async with app.run_test(size=(100, 30)) as pilot:
            await pilot.pause()
            monkeypatch.setattr(app.ai, "one_shot", judge)
            t = app.tutor
            t.start("review", minutes=10)
            t._present({"id": "s1", "kcs": ["9702-2.1.1"], "kind": "short", "difficulty": 3,
                        "marks": 2, "stem": "Define displacement.",
                        "rubric": [{"point": "distance", "keywords": [["distance"]]},
                                   {"point": "direction", "keywords": [["direction"]]}]},
                       block="practice", phase=None)
            await app.push_screen(SessionScreen(None))
            await pilot.pause()
            screen = app.screen
            await pilot.press(*"distance moved north", "enter")
            await pilot.pause()
            await pilot.press("3")
            await pilot.pause()
            if in_flight:
                await asyncio.wait_for(started.wait(), 2)
            else:
                ticks = screen.query_one(TickPanel).query_one("#ticks")
                ticks.select("0")
            await pilot.press("ctrl+b")
            await pilot.pause()
            assert isinstance(app.screen, ConfirmScreen)
            assert "lost" in app.screen.question
            await pilot.press("escape")
            await pilot.pause()
            assert app.screen is screen
            release.set()
            await app.workers.wait_for_complete()
            await pilot.pause()
            ticks = screen.query_one(TickPanel).query_one("#ticks")
            if not in_flight:
                assert ticks.selected == ["0"]
            ticks.select("0")
            screen.query_one(TickPanel).query_one("Button").press()
            await pilot.pause()
            answers = [e for e in t.vault.events() if e["type"] == "answer"]
            assert len(answers) == 1 and answers[0]["grade"]["score"] == 0.5
            await pilot.press("ctrl+b")
            await pilot.pause()
            assert isinstance(app.screen, HomeScreen)
    asyncio.run(go())


def test_bracket_keys_move_between_chapter_folders(tmp_path, monkeypatch) -> None:
    """B-053: documented chapter jumps work on the ordinary folder list."""
    app, _ = app_for(tmp_path, monkeypatch)

    async def go() -> None:
        async with app.run_test(size=(100, 30)) as pilot:
            await pilot.pause()
            crowd(app)
            await app.push_screen(PickerScreen("lesson"))
            await pilot.pause()
            await pilot.press("enter")
            await pilot.pause()
            box = app.screen.query_one("#subs")
            for key, expected in [("]", "dir:chem/9701-2"), ("]", "dir:chem/9701-2"),
                                  ("[", "dir:chem/9701-1"), ("[", "dir:chem/9701-1")]:
                await pilot.press(key)
                await pilot.pause()
                assert box.get_option_at_index(box.highlighted).id == expected
    asyncio.run(go())


def test_summary_names_its_twenty_four_hour_review_window(tmp_path, monkeypatch) -> None:
    """B-111: the label describes the rolling cutoff rather than an ambiguous calendar day."""
    app, _ = app_for(tmp_path, monkeypatch)

    async def go() -> None:
        async with app.run_test(size=(100, 30)) as pilot:
            await pilot.pause()
            await app.push_screen(SummaryScreen({"answered": 0, "correct": 0}))
            await pilot.pause()
            text = app.screen.query_one(Markdown).source
            assert "Due for review in the next 24 hours:" in text
            assert "by tomorrow" not in text
    asyncio.run(go())
