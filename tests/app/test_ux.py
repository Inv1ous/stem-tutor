"""UX fixes found by an audit of every screen at 60x24, 80x24 and 120x40 in Night, Day and Classic."""
from test_qol import _menu, _session, run
from test_tui import app_for
from tutor_app.panels import TickPanel

LONG_POINT = ("B1 uses v^2 = u^2 + 2as with v = 0 at the top of the flight and states the sign convention used "
              "for the acceleration clearly")


def test_a_mark_point_too_long_for_its_row_is_shown_in_full_under_the_list(tmp_path, monkeypatch):
    app, v = app_for(tmp_path, monkeypatch)

    async def steps(pilot):
        scr = await _session(app, pilot)
        scr.panel(TickPanel("Tick every mark point your answer earns (space).",
                            [(LONG_POINT, "0", False), ("A1 11.5 m", "1", False)], [("mine", "Submit my marks ⏎")]))
        await pilot.pause()
        ticks, full = scr.query_one("#ticks"), scr.query_one("#full")
        ticks.highlighted = 0
        await pilot.pause()
        assert full.display and full.region.height >= 2  # wrapped, all of it
        assert "the acceleration clearly" in str(full.render()) and full.region.right <= 80
        await pilot.press("down")
        await pilot.pause()
        assert not full.display  # a point that fits its row is not said twice
    run(app, (80, 24), steps)


LONG_STEM = "\n\n".join(f"({c}) A ball is thrown upwards at 15 m s-1 from a cliff 40 m high. Find part {c}."
                        for c in "abcdefgh")


def test_a_long_question_opens_at_its_top_and_the_log_scrolls_while_typing(tmp_path, monkeypatch):
    app, v = app_for(tmp_path, monkeypatch)

    async def steps(pilot):
        scr = await _session(app, pilot)
        scr.ask_question({**scr.view, "kind": "numeric", "stem": "START " + LONG_STEM + " END"}, "A test check.")
        await pilot.pause()
        await pilot.pause()
        log = scr.query_one("#log")
        card = list(log.query(".entry"))[-1]
        assert card.region.height > log.region.height or card.outer_size.height > log.size.height
        assert log.scroll_y > 0 and card.virtual_region.y == log.scroll_y  # its start is what you read first
        assert app.focused.id == "value"
        await pilot.press("alt+down")
        await pilot.pause()
        assert log.scroll_y > card.virtual_region.y
        await pilot.press("alt+up", "alt+up")
        await pilot.pause()
        assert log.scroll_y < card.virtual_region.y and app.focused.id == "value"
        assert scr.query_one("#value").text == ""  # the keys scrolled, nothing was typed
    run(app, (80, 24), steps)


def test_help_says_how_to_scroll_the_session(tmp_path, monkeypatch):
    app, v = app_for(tmp_path, monkeypatch)

    async def steps(pilot):
        app.action_help()
        await pilot.pause()
        assert "alt+↑" in app.screen.query_one("Markdown").source
    run(app, (100, 30), steps)
