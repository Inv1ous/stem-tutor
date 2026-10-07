"""Small fixes to how the app behaves and fits, found by a hunter walking every screen at 60x24 to 120x40."""
import asyncio
import time

from textual.widgets import Button, Input, Select, Switch

from test_tui import app_for
from tutor_app.panels import Composer, ContinuePanel, LongPanel, ReflectPanel


def run(app, size, steps):
    async def go():
        async with app.run_test(size=size) as pilot:
            await pilot.pause()
            await steps(pilot)
            await app.ai.close()
    asyncio.run(go())


def _menu(app, key):
    menu = app.screen.query_one("#menu")
    menu.highlighted = [o.id for o in menu.options].index(key)


async def _session(app, pilot, mode="test"):
    from tutor_app.screens import SessionScreen
    scr = SessionScreen({"mode": mode, "minutes": 40, "focus": ["9702-2.1"]})
    app.push_screen(scr)
    await pilot.pause()
    await pilot.pause()
    return scr


def test_settings_fit_a_small_window_and_save_is_reachable(tmp_path, monkeypatch):
    app, v = app_for(tmp_path, monkeypatch)

    async def steps(pilot):
        app.action_settings()
        await pilot.pause()
        box = app.screen.query_one("#settings")
        save = app.screen.query_one("#save", Button)
        minutes = app.screen.query_one("#minutes", Input)
        assert minutes.region.width >= 4  # the minutes box is on screen, not pushed out by its label
        save.focus()
        await pilot.pause()
        assert box.region.bottom <= 24 and save.region.height and save.region.bottom <= box.region.bottom
        for key in ("ai", "own_words_feedback", "open_obsidian"):
            label = app.screen.query_one(f"#{key}", Switch).parent.query("Static").first()
            assert label.region.right <= box.region.right  # the label wraps inside the box
    run(app, (60, 24), steps)


def test_settings_keep_the_session_length_when_it_is_not_a_number(tmp_path, monkeypatch):
    app, v = app_for(tmp_path, monkeypatch)
    said = []

    async def steps(pilot):
        monkeypatch.setattr(app, "notify", lambda msg, **k: said.append(msg))
        app.settings.minutes = 55
        for typed, kept in (("", 55), ("abc", 55), ("500", 180), ("30", 30)):
            app.action_settings()
            await pilot.pause()
            app.screen.query_one("#minutes", Input).value = typed
            app.screen.query_one("#save", Button).press()
            await pilot.pause()
            assert app.settings.minutes == kept and f"{kept}" in said[-1]
    run(app, (100, 30), steps)


def test_ctrl_q_goes_back_a_screen_and_only_quits_from_the_menu(tmp_path, monkeypatch):
    app, v = app_for(tmp_path, monkeypatch)

    async def steps(pilot):
        for key, quit_key in (("chat", "ctrl+q"), ("insights", "ctrl+c"), ("progress", "ctrl+q")):
            _menu(app, key)
            await pilot.press("enter")
            await pilot.pause()
            assert app.screen.__class__.__name__ != "HomeScreen"
            await pilot.press(quit_key)
            await pilot.pause()
            assert app.screen.__class__.__name__ == "HomeScreen" and app.is_running
        app.action_help()
        await pilot.pause()
        await pilot.press("ctrl+q")
        await pilot.pause()
        assert app.screen.__class__.__name__ == "HomeScreen" and app.is_running
        await pilot.press("ctrl+q")
        await pilot.pause()
        assert not app.is_running
    run(app, (100, 30), steps)


def test_leaving_with_a_typed_answer_asks_first(tmp_path, monkeypatch):
    app, v = app_for(tmp_path, monkeypatch)

    async def steps(pilot):
        scr = await _session(app, pilot, "long")
        assert isinstance(scr.query_one("#panel > *"), LongPanel)
        await pilot.press(*"my working")
        await pilot.press("ctrl+b")
        await pilot.pause()
        assert app.screen.__class__.__name__ == "ConfirmScreen"
        await pilot.press("down", "enter")  # Keep writing
        await pilot.pause()
        assert app.screen is scr and scr.query_one("#long").text == "my working"
        await pilot.press("ctrl+q")
        await pilot.pause()
        assert app.screen.__class__.__name__ == "ConfirmScreen"
        await pilot.press("enter")  # Leave
        await pilot.pause()
        assert app.screen.__class__.__name__ == "HomeScreen"
    run(app, (100, 30), steps)


def test_leaving_with_nothing_typed_goes_straight_back(tmp_path, monkeypatch):
    app, v = app_for(tmp_path, monkeypatch)

    async def steps(pilot):
        await _session(app, pilot)
        await pilot.press("ctrl+b")
        await pilot.pause()
        assert app.screen.__class__.__name__ == "HomeScreen"
    run(app, (100, 30), steps)


def test_esc_on_a_blurt_with_text_asks_first(tmp_path, monkeypatch):
    app, v = app_for(tmp_path, monkeypatch)

    async def steps(pilot):
        _menu(app, "blurt")
        await pilot.press("enter")
        await pilot.pause()
        assert "Pick a subtopic to blurt on" in str(app.screen.query(".hint").first().render())
        await pilot.press("enter")
        await pilot.pause()
        await pilot.press(*"vectors")
        await pilot.press("escape")
        await pilot.pause()
        assert app.screen.__class__.__name__ == "ConfirmScreen"
        await pilot.press("enter")
        await pilot.pause()
        assert app.screen.__class__.__name__ == "HomeScreen"
    run(app, (100, 30), steps)


def test_home_fits_narrow_and_short_windows(tmp_path, monkeypatch):
    app, v = app_for(tmp_path, monkeypatch)

    async def steps(pilot):
        home = app.screen
        for size, narrow, short in (((60, 24), True, True), ((80, 24), True, True), ((100, 30), False, False),
                                    ((120, 40), False, False)):
            await pilot.resize_terminal(*size)
            await pilot.pause()
            assert home.has_class("narrow") == narrow and home.has_class("short") == short
            assert home.query_one("#stats").display == (not narrow)
            menu = home.query_one("#menu")
            assert menu.region.right <= size[0] and menu.max_scroll_y == 0  # every item, Quit included, on screen
    run(app, (120, 40), steps)


def test_home_menu_remembers_where_you_were(tmp_path, monkeypatch):
    app, v = app_for(tmp_path, monkeypatch)

    async def steps(pilot):
        _menu(app, "progress")
        await pilot.press("enter")
        await pilot.pause()
        await pilot.press("escape")
        await pilot.pause()
        menu = app.screen.query_one("#menu")
        assert menu.get_option_at_index(menu.highlighted).id == "progress"
    run(app, (100, 30), steps)


def test_session_footer_shows_menu_and_help_at_60_columns(tmp_path, monkeypatch):
    app, v = app_for(tmp_path, monkeypatch)

    async def steps(pilot):
        assert not app.ENABLE_COMMAND_PALETTE
        scr = await _session(app, pilot)
        keys = {k.description: k for k in scr.query("FooterKey")}
        assert {"Menu", "Help", "Ask", "Hint", "Explain", "Notes"} <= set(keys)
        assert keys["Menu"].region.right <= 60 and keys["Help"].region.right <= 60
        assert keys["Menu"].region.width and keys["Help"].region.width
    run(app, (60, 24), steps)


def test_esc_in_a_session_says_how_to_leave(tmp_path, monkeypatch):
    app, v = app_for(tmp_path, monkeypatch)
    said = []

    async def steps(pilot):
        monkeypatch.setattr(app, "notify", lambda msg, **k: said.append(msg))
        scr = await _session(app, pilot)
        await pilot.press("escape")
        await pilot.pause()
        assert app.screen is scr and any("ctrl+b" in m for m in said)
        await pilot.press("b")  # Confidence still takes Esc to change the answer
        await pilot.pause()
        said.clear()
        await pilot.press("escape")
        await pilot.pause()
        assert not said and scr.query_one("#choices").display
    run(app, (100, 30), steps)


def test_buttons_are_compact_on_a_short_window(tmp_path, monkeypatch):
    app, v = app_for(tmp_path, monkeypatch)

    async def steps(pilot):
        scr = await _session(app, pilot)
        scr.submit({"entry": f"{scr.view['n']}?", "your": "I don't know"})
        await pilot.pause()
        assert {b.region.height for b in scr.query("#panel Button")} == {1}
        assert scr.query_one("#panel").region.height <= 24 * 0.45 + 1
        await pilot.resize_terminal(100, 40)
        await pilot.pause()
        assert {b.region.height for b in scr.query("#panel Button")} == {3} and app.focused.id == "next"
    run(app, (60, 24), steps)


def test_small_wording_fixes(tmp_path, monkeypatch):
    app, v = app_for(tmp_path, monkeypatch)

    async def steps(pilot):
        _menu(app, "test")
        await pilot.press("enter")
        await pilot.pause()
        hint = str(app.screen.query(".hint").first().render())
        assert "Tab to Start" in hint and "⏎ on Start" not in hint
        await pilot.press("escape")
        await pilot.pause()
        scr = await _session(app, pilot)
        assert scr.query_one("#note", Composer).placeholder == "✎ optional note (Tab)"
        bar = scr.bar_text(200).plain
        assert "tok" not in bar and "replies" in bar
        scr.panel(ReflectPanel(remark=True))
        await pilot.pause()
        assert "1–6" in str(scr.query_one("#panel .hint").render())
        scr.panel(ReflectPanel(remark=False))
        await pilot.pause()
        assert "1–5" in str(scr.query_one("#panel .hint").render())
        app.action_help()
        await pilot.pause()
        text = app.screen.query_one("Markdown").source
        assert "ctrl+l" in text and "ctrl+s" in text and "ctrl+j" in text and "scroll" in text
    run(app, (100, 30), steps)


def test_chat_footer_says_back(tmp_path, monkeypatch):
    app, v = app_for(tmp_path, monkeypatch)

    async def steps(pilot):
        _menu(app, "chat")
        await pilot.press("enter")
        await pilot.pause()
        descriptions = [k.description for k in app.screen.query("FooterKey")]
        assert "Back" in descriptions and "Skip" not in descriptions
        await pilot.press("escape")
        await pilot.pause()
        assert app.screen.__class__.__name__ == "HomeScreen"
    run(app, (100, 30), steps)


def test_the_summary_ignores_an_enter_held_down_from_the_last_question(tmp_path, monkeypatch):
    from tutor_app.screens import SummaryScreen
    app, v = app_for(tmp_path, monkeypatch)

    async def steps(pilot):
        app.push_screen(SummaryScreen({"answered": 1, "correct": 1, "accuracy": 1.0}))
        await pilot.pause()
        await pilot.press("enter")
        await pilot.pause()
        assert app.screen.__class__.__name__ == "SummaryScreen"
        assert "tokens" not in app.screen.query_one("Markdown").source  # replies, not jargon
        app.screen.opened = time.monotonic() - 1
        await pilot.press("enter")
        await pilot.pause()
        assert app.screen.__class__.__name__ == "HomeScreen"
    run(app, (100, 30), steps)


def test_insights_in_the_terminal_have_no_obsidian_syntax_and_a_narrow_table(tmp_path, monkeypatch):
    from tutor_app.screens import InsightsScreen
    app, v = app_for(tmp_path, monkeypatch)

    async def steps(pilot):
        app.push_screen(InsightsScreen())
        await pilot.pause()
        text = app.screen._text()
        assert "[!" not in text and "How sure the tutor is" in text
        header = next(line for line in text.splitlines() if line.startswith("| Exam"))
        assert header.count("|") <= 7 and "Built" not in header
    run(app, (80, 24), steps)


def test_esc_still_skips_a_text_panel_and_a_reason_inside_a_session(tmp_path, monkeypatch):
    from tutor_app.panels import TextPanel
    app, v = app_for(tmp_path, monkeypatch)
    skipped, said = [], []
    monkeypatch.setattr(TextPanel, "action_skip", lambda self: skipped.append("text"))
    monkeypatch.setattr(ReflectPanel, "action_skip", lambda self: skipped.append("reflect"))

    async def steps(pilot):
        monkeypatch.setattr(app, "notify", lambda msg, **k: said.append(msg))
        scr = await _session(app, pilot)
        for panel in (TextPanel("In your own words"), ReflectPanel()):
            scr.panel(panel)
            await pilot.pause()
            await pilot.press("escape")
            await pilot.pause()
        assert skipped == ["text", "reflect"] and not said
    run(app, (100, 30), steps)


def test_the_summary_progress_and_insights_screens_show_maths_not_dollars(tmp_path, monkeypatch):
    from tutorlib import profile
    from tutor_app.screens import InsightsScreen, ProgressScreen, SummaryScreen
    monkeypatch.setattr(profile, "advice", lambda p: [r"You mix up $v^2=u^2+2as$ and $s=ut$."])
    app, v = app_for(tmp_path, monkeypatch)

    async def steps(pilot):
        for screen in (ProgressScreen(), SummaryScreen({"answered": 1, "correct": 1, "accuracy": 1.0})):
            app.push_screen(screen)
            await pilot.pause()
            source = "\n".join(m.source for m in app.screen.query("Markdown"))
            assert "$" not in source and "\\" not in source
            if isinstance(screen, ProgressScreen):
                assert "v² = u² + 2as" in source
            app.pop_screen()
            await pilot.pause()
        assert "v² = u² + 2as" in InsightsScreen._for_terminal(r"Misconception: $v^2=u^2+2as$")
    run(app, (100, 30), steps)
