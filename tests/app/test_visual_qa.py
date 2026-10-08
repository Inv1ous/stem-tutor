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


@pytest.mark.parametrize("size,short", [((60, 24), True), ((80, 24), True), ((120, 40), False)])
def test_settings_save_is_on_screen_without_scrolling(tmp_path, monkeypatch, size, short):
    from textual.widgets import Button, Switch
    app, v = app_for(tmp_path, monkeypatch)

    async def steps(pilot):
        app.action_settings()
        await pilot.pause()
        scr = app.screen
        assert scr.has_class("short") == short and isinstance(app.focused, Switch)  # nothing scrolled to Save
        save = scr.query_one("#save", Button)
        assert save.compact == short
        box = scr.query_one("#settings")
        assert save.region.height and box.region.contains_region(save.region)
        for y in range(save.region.y, save.region.bottom):  # every row of it drawn: not hidden under the border
            assert scr.get_widget_at(save.region.x + 2, y)[0] is save
        await pilot.resize_terminal(120, 40)
        await pilot.pause()
        assert not scr.has_class("short") and not save.compact
    run(app, size, steps)


@pytest.mark.parametrize("name", ["night", "day", "classic"])
def test_markdown_titles_sit_on_their_box_and_line_up_with_the_text(tmp_path, monkeypatch, palette, name):
    from textual.widgets._markdown import MarkdownH1
    from tutor_app.screens import HelpScreen, InsightsScreen, ProgressScreen, SummaryScreen
    app, v = app_for(tmp_path, monkeypatch)
    app.settings.theme = name
    palette(name)

    async def steps(pilot):
        for screen in (SummaryScreen({"answered": 2, "correct": 1, "accuracy": 0.5}), HelpScreen(), InsightsScreen(),
                       ProgressScreen()):
            app.push_screen(screen)
            await pilot.pause()
            for h1 in screen.query(MarkdownH1):
                assert h1.styles.background.a == 0  # no band of another colour across a pop-up
                # Night and Day: left, like the text under it; Classic as it always was
                assert h1.styles.content_align_horizontal == ("center" if name == "classic" else "left")
            app.pop_screen()
            await pilot.pause()
    run(app, (120, 40), steps)


@pytest.mark.parametrize("name", ["night", "day", "classic"])
def test_a_pop_up_has_no_lighter_halo_round_its_rounded_border(tmp_path, monkeypatch, palette, name):
    from tutor_app.screens import AskScreen, ConfirmScreen, HelpScreen, PickerScreen, SettingsScreen, SummaryScreen
    app, v = app_for(tmp_path, monkeypatch)
    app.settings.theme = name
    palette(name)

    async def steps(pilot):
        for screen, box in ((PickerScreen("lesson"), "#picker"), (AskScreen(), "#ask"),
                            (ConfirmScreen("Sure?", [("y", "Yes")]), "#ask"), (HelpScreen(), "#help"),
                            (SettingsScreen(), "#settings"),
                            (SummaryScreen({"answered": 2, "correct": 1, "accuracy": 0.5}), "#summary")):
            app.push_screen(screen)
            await pilot.pause()
            # the corners outside the round border are drawn in the box's colour: Night and Day give it the window's
            want = app.current_theme.surface if name == "classic" else look.PALETTES[name]["background"]
            assert screen.query_one(box).styles.background.hex.lower() == want.lower(), box
            app.pop_screen()
            await pilot.pause()
    run(app, (100, 30), steps)


@pytest.mark.parametrize("name", ["night", "day", "classic"])
def test_settings_switches_are_readable_and_line_up_when_focused(tmp_path, monkeypatch, palette, name):
    from textual.widgets import Input, Switch
    app, v = app_for(tmp_path, monkeypatch)
    app.settings.theme = name
    app.settings.open_obsidian = False
    palette(name)

    async def steps(pilot):
        app.action_settings()
        await pilot.pause()
        scr = app.screen
        flat = name != "classic"
        assert scr.has_class("flat") == flat
        switches = list(scr.query(Switch))
        assert switches[0].has_focus
        if not flat:
            return  # Classic: as it always was
        p = look.PALETTES[name]
        assert {(s.region.x, s.region.width) for s in switches} == {(switches[0].region.x, 4)}  # focus: no wider
        off = scr.query_one("#open_obsidian", Switch)
        assert not off.value
        slider = off.get_component_rich_style("switch--slider")
        assert slider.color.triplet.hex == p["muted"] and slider.bgcolor.triplet.hex == p["panel"]
        focused = switches[0].get_component_rich_style("switch--slider")
        assert focused.bgcolor.triplet.hex == p["cursor"]  # focus shows on the track, and the label turns blue
        assert switches[0].parent.query_one("Static").styles.color.hex.lower() == p["tutor"]
        assert scr.query_one("#minutes", Input).styles.background.hex.lower() == p["panel"]
    run(app, (120, 40), steps)


def test_a_recalled_idea_in_blurt_results_is_not_an_empty_box(tmp_path, monkeypatch):
    from tutor_app.screens import BlurtScreen
    app, v = app_for(tmp_path, monkeypatch)
    drawn = []
    real = cards.card
    monkeypatch.setattr(cards, "card", lambda kind, title, body="", **kw: drawn.append((kind, title, body))
                        or real(kind, title, body, **kw))

    async def steps(pilot):
        b = BlurtScreen("9702-2.1")
        app.push_screen(b)
        await pilot.pause()
        b.query_one("#blurt").text = "Velocity is rate of change of displacement. v = u + at."
        b.action_submit()
        await pilot.pause()
    run(app, (100, 30), steps)
    ideas = [d for d in drawn if d[1].startswith(("✓", "✗"))]
    assert any(t.startswith("✓") for _, t, _ in ideas) and all(body.strip() for _, _, body in ideas)


def test_the_first_card_has_a_blank_row_under_the_top_bar_in_chat_and_blurt(tmp_path, monkeypatch):
    from textual.widgets import Static
    from tutor_app.screens import BlurtScreen, ChatScreen
    app, v = app_for(tmp_path, monkeypatch)

    async def steps(pilot):
        for screen in (ChatScreen(), BlurtScreen("9702-2.1")):
            app.push_screen(screen)
            await pilot.pause()
            log = screen.query_one("#log")
            if not log.query(".entry"):
                await log.mount(Static(cards.you("hello"), classes="entry"))
                await pilot.pause()
            first = log.query(".entry").first()
            assert first.region.y == screen.query_one("#bar").region.bottom + 1, screen  # as in a session
            app.pop_screen()
            await pilot.pause()
    run(app, (100, 30), steps)


@pytest.mark.parametrize("name", ["night", "day", "classic"])
def test_the_before_you_answer_check_is_calm_in_night_and_day(tmp_path, monkeypatch, palette, name):
    from tutor_app.panels import ValuePanel
    app, v = app_for(tmp_path, monkeypatch)
    app.settings.theme = name
    palette(name)

    async def steps(pilot):
        scr = await _session(app, pilot)
        scr.panel(ValuePanel(2, "numeric", checking=True))
        await pilot.pause()
        want = app.current_theme.warning if name == "classic" else look.PALETTES[name]["muted"]
        assert scr.query_one(".check").styles.color.hex.lower() == want.lower()
    run(app, (100, 30), steps)


async def _session(app, pilot, mode="test"):
    from tutor_app.screens import SessionScreen
    scr = SessionScreen({"mode": mode, "minutes": 40, "focus": ["9702-2.1"]})
    app.push_screen(scr)
    await pilot.pause()
    await pilot.pause()
    return scr


@pytest.mark.parametrize("size,short", [((60, 24), True), ((80, 24), True), ((120, 40), False)])
def test_a_long_answer_submit_button_and_footer_fit_a_small_window(tmp_path, monkeypatch, size, short):
    from textual.widgets import Button
    from tutor_app.panels import LongPanel
    app, v = app_for(tmp_path, monkeypatch)

    async def steps(pilot):
        scr = await _session(app, pilot)
        scr.panel(LongPanel(4, checking=True))
        await pilot.pause()
        await pilot.pause()
        submit = scr.query_one("#submit", Button)
        assert submit.compact == short
        box = scr.query_one("#panel")
        assert submit.region.height and box.region.contains_region(submit.region)
        for y in range(submit.region.y, submit.region.bottom):
            assert scr.get_widget_at(submit.region.x + 2, y)[0] is submit
        assert "ctrl+s" in str(submit.label) and "ctrl+s" in str(scr.query(".hint").first().render())
        for key in scr.query("FooterKey"):  # each key with its word, none cut off at the edge
            assert key.region.width and key.region.right <= size[0], key.description
        await pilot.resize_terminal(100, 40)
        await pilot.pause()
        assert not submit.compact
    run(app, size, steps)


@pytest.mark.parametrize("name", ["night", "day", "classic"])
def test_a_tick_list_shows_an_empty_box_for_each_unticked_row(tmp_path, monkeypatch, palette, name):
    from tutor_app.panels import TickPanel
    app, v = app_for(tmp_path, monkeypatch)
    app.settings.theme = name
    palette(name)

    async def steps(pilot):
        scr = await _session(app, pilot)
        scr.panel(TickPanel("Tick", [("one", "a", True), ("two", "b", False)], [("mark", "Mark")]))
        await pilot.pause()
        ticks = scr.query_one("#ticks")
        rows = [ticks.render_line(y) for y in (0, 1)]
        if name == "classic":
            assert [r.text[:4] for r in rows] == ["▐X▌ "] * 2 and rows[0].text.index("one") == 4  # as it always was
            return
        assert [r.text[:3] for r in rows] == [" ✓ ", " ☐ "] and rows[0].text.index("one") == 4  # where it was
        mark = {s.text: s.style for s in rows[1]}["☐"]
        assert mark.color.triplet.hex == look.PALETTES[name]["muted"]
        ticks.highlighted = 1
        await pilot.press("space")
        await pilot.pause()
        assert ticks.render_line(1).text[:3] == " ✓ "
    run(app, (100, 30), steps)
