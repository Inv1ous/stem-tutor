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
