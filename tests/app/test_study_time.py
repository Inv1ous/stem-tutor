import asyncio
import time

from test_tui import app_for
from tutor_app.screens import SessionScreen


def run(app, steps, size=(120, 40)):
    async def go():
        async with app.run_test(size=size) as pilot:
            await pilot.pause()
            await steps(pilot)
            await app.ai.close()
    asyncio.run(go())


def tick(app, seconds, step=1.0):
    """Let `seconds` pass in the app's own study clock, a second at a time, as its timer would."""
    t = app._tick_at
    for _ in range(int(seconds / step)):
        t += step
        app._study_tick(now=t)
    return t


def day(app):
    return app.tutor.now().date().isoformat()


def test_time_counts_only_on_a_study_screen_while_the_learner_is_there(tmp_path, monkeypatch):
    app, v = app_for(tmp_path, monkeypatch)

    async def steps(pilot):
        clock = app.tutor.study_clock
        app._last_input = app._tick_at + 10_000  # the learner is pressing keys throughout
        tick(app, 20)
        assert clock.today(day(app)) == 0  # on the menu: nothing counts
        scr = SessionScreen({"mode": "test", "minutes": 40, "focus": ["9702-2.1"]})
        app.push_screen(scr)
        await pilot.pause()
        sid = app.tutor.session["id"]
        tick(app, 30)
        assert 29 <= clock.today(day(app)) <= 31 and 29 <= clock.session(sid) <= 31  # counted for the day and the session
        before = clock.session(sid)
        app._last_input = app._tick_at - app.IDLE_LIMIT - 1  # no key for longer than the limit: away from the screen
        tick(app, 30)
        assert clock.session(sid) == before  # paused while idle
        app._last_input = app._tick_at  # a key: counting again
        tick(app, 10)
        assert 9 <= clock.session(sid) - before <= 11
        app._study_tick(now=app._tick_at + 600)  # a computer that slept: that gap is not counted
        assert clock.session(sid) - before <= 11
    run(app, steps)


def test_a_pop_up_over_the_lesson_still_counts_and_settings_over_the_menu_does_not(tmp_path, monkeypatch):
    app, v = app_for(tmp_path, monkeypatch)

    async def steps(pilot):
        clock = app.tutor.study_clock
        app._last_input = app._tick_at + 10_000
        app.push_screen(SessionScreen({"mode": "test", "minutes": 40, "focus": ["9702-2.1"]}))
        await pilot.pause()
        await pilot.press("ctrl+t")  # the ask pop-up
        await pilot.pause()
        assert app.screen.__class__.__name__ == "AskScreen" and app.studying()
        await pilot.press("escape", "ctrl+b")
        await pilot.pause()
        for _ in range(5):
            if app.screen.__class__.__name__ == "HomeScreen":
                break
            await pilot.press("enter")
            await pilot.pause()
        before = clock.today(day(app))
        app.action_settings()
        await pilot.pause()
        tick(app, 10)
        assert not app.studying() and clock.today(day(app)) == before
    run(app, steps)


def test_the_session_bar_shows_true_time_and_session_time_apart(tmp_path, monkeypatch):
    app, v = app_for(tmp_path, monkeypatch)

    async def steps(pilot):
        scr = SessionScreen({"mode": "test", "minutes": 40, "focus": ["9702-2.1"]})
        app.push_screen(scr)
        await pilot.pause()
        sid = app.tutor.session["id"]
        app.tutor.study_clock.add(day(app), 9 * 60 + 31, sid)  # 9:31 really on the screen
        scr.started = time.monotonic() - (3600 + 4 * 60 + 5)  # but 1:04:05 since it began (the terminal was closed for a while)
        text = scr.bar_text(200).plain
        assert "◷ 1:04:0" in text and " true " in text and "◔ 09:31 session" in text
    run(app, steps)


def test_a_resumed_session_carries_its_session_time_on_and_true_time_includes_the_gap(tmp_path, monkeypatch):
    app, v = app_for(tmp_path, monkeypatch)

    async def steps(pilot):
        scr = SessionScreen({"mode": "test", "minutes": 40, "focus": ["9702-2.1"]})
        app.push_screen(scr)
        await pilot.pause()
        sid = app.tutor.session["id"]
        app.tutor.study_clock.add(day(app), 300, sid)
        app.tutor.study_clock.flush()
        from tutorlib.clock import StudyClock
        from tutorlib import store
        assert StudyClock(store.Vault(v)).session(sid) == 300  # on disk: the terminal can be closed now
    run(app, steps)


def test_the_menu_lists_the_time_studied_today(tmp_path, monkeypatch):
    app, v = app_for(tmp_path, monkeypatch)

    async def steps(pilot):
        app.tutor.study_clock.add(day(app), 72 * 60, "s1")
        app.screen.refresh_home()
        await pilot.pause()
        await pilot.pause()
        menu = app.screen.query_one("#menu")
        first = menu.get_option_at_index(0)
        assert first.id == "time" and first.disabled and "Studied today: 1 h 12 min" in str(first.prompt)  # a line, not a choice
        assert "1 session" in str(first.prompt)
        assert menu.get_option_at_index(menu.highlighted).id != "time"  # the cursor starts on a real choice
        side = str(app.screen.query_one("#stats-text").content if hasattr(app.screen.query_one("#stats-text"), "content")
                   else app.screen.query_one("#stats-text").render())
        assert "Studied today: 1 h 12 min" in side
        await pilot.resize_terminal(80, 24)  # a short window: no room for a line of its own, the one-line summary has it
        await pilot.pause()
        await pilot.pause()
        assert all(menu.get_option_at_index(i).id != "time" for i in range(menu.option_count))
        assert "◔ 1 h 12 min today" in str(app.screen.query_one("#glance").render())
    run(app, steps)


def test_the_summary_shows_session_time_true_time_and_the_day(tmp_path, monkeypatch):
    from textual.widgets import Markdown
    from tutor_app.screens import SummaryScreen
    app, v = app_for(tmp_path, monkeypatch)

    async def steps(pilot):
        app.tutor.study_clock.add(day(app), 95 * 60, "s9")
        app.push_screen(SummaryScreen({"answered": 4, "correct": 3, "accuracy": 0.75, "kcs_learned": [],
                                       "active_seconds": 18 * 60 + 42, "true_seconds": 3600 + 5 * 60 + 9}))
        await pilot.pause()
        source = app.screen.query_one(Markdown).source
        assert "**Session time:** 18:42 on the screen" in source and "**True time:** 1:05:09 from start to finish" in source
        assert "**Studied today:** 1 h 35 min" in source
    run(app, steps)
