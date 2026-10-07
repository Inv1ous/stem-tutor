"""UX fixes found by an audit of every screen at 60x24, 80x24 and 120x40 in Night, Day and Classic."""
import pytest

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


def test_the_summary_scrolls_in_a_small_window_and_always_says_how_to_leave(tmp_path, monkeypatch):
    import time
    from tutor_app.screens import SummaryScreen
    app, v = app_for(tmp_path, monkeypatch)

    async def steps(pilot):
        kcs = list(app.tutor.packs.kcs)
        app.push_screen(SummaryScreen({"answered": 12, "correct": 9, "accuracy": 0.75, "kcs_learned": kcs}))
        await pilot.pause()
        box, hint = app.screen.query_one("#summary"), app.screen.query_one("#summary-hint")
        assert box.max_scroll_y > 0 and box.region.bottom <= 24  # what does not fit can be scrolled to
        assert hint.region.height and hint.region.bottom <= box.region.bottom and "⏎" in str(hint.render())
        await pilot.press("down")
        await pilot.pause()
        assert box.scroll_y > 0
        await pilot.press("enter")  # too soon: perhaps held down from the last question, but it is not ignored silently
        await pilot.pause()
        assert app.screen.__class__.__name__ == "SummaryScreen" and "again" in str(hint.render())
        app.screen.opened = time.monotonic() - 1
        await pilot.press("enter")
        await pilot.pause()
        assert app.screen.__class__.__name__ == "HomeScreen"
    run(app, (60, 24), steps)


@pytest.mark.parametrize("name", ["night", "day", "classic"])
def test_a_focused_button_looks_focused_not_broken(tmp_path, monkeypatch, name):
    """Textual's focus style is "b reverse": on a filled button the label becomes a dark chip inside a block. Night
    and Day light the focused button up instead; Classic keeps the look it always had."""
    from tutor_app import look
    app, v = app_for(tmp_path, monkeypatch)
    app.settings.theme = name
    look.use(name)

    async def steps(pilot):
        scr = await _session(app, pilot)
        scr.submit({"entry": f"{scr.view['n']}?", "your": "I don't know"})
        await pilot.pause()
        for compact, size in ((True, (60, 24)), (False, (100, 40))):
            await pilot.resize_terminal(*size)
            await pilot.pause()
            await pilot.pause()
            buttons = list(scr.query("#panel Button"))
            focused, other = buttons[0], buttons[-1]
            assert app.focused is focused and focused.compact == compact == other.compact
            style, tint = str(focused.styles.text_style), focused.styles.background_tint
            if name == "classic":
                assert style == "bold reverse" and tint.a == pytest.approx(0.05, abs=0.01)
            else:
                assert "reverse" not in style and "bold" in style and tint.a >= 0.15
                if compact:  # no border to change: a mark that needs no colour
                    assert "underline" in style
    try:
        run(app, (60, 24), steps)
    finally:
        look.use("classic")


def test_settings_label_the_model_show_an_editable_minutes_box_and_say_how_to_apply(tmp_path, monkeypatch):
    from textual.widgets import Select
    app, v = app_for(tmp_path, monkeypatch)

    async def steps(pilot):
        app.action_settings()
        await pilot.pause()
        scr = app.screen
        model = scr.query_one("#model", Select)
        assert all(label.startswith("Model: ") for label, _ in model._options)
        box, minutes = scr.query_one("#settings"), scr.query_one("#minutes")
        assert minutes.styles.background != box.styles.background  # a box to type in, not loose text
        scr.query_one("#save").focus()
        await pilot.pause()
        hint = scr.query_one("#settings-hint")
        text = str(hint.render())
        assert "Save to apply" in text and "Esc cancels" in text
        assert hint.region.height and hint.region.bottom <= box.region.bottom
    run(app, (60, 24), steps)


def test_esc_in_the_chat_asks_before_losing_a_typed_question(tmp_path, monkeypatch):
    app, v = app_for(tmp_path, monkeypatch)

    async def steps(pilot):
        _menu(app, "chat")
        await pilot.press("enter")
        await pilot.pause()
        chat = app.screen
        await pilot.press(*"why is the sky")
        await pilot.press("escape")
        await pilot.pause()
        assert app.screen.__class__.__name__ == "ConfirmScreen" and "question" in str(app.screen.query_one(".hint").render())
        await pilot.press("down", "enter")  # Keep writing
        await pilot.pause()
        assert app.screen is chat and chat.query_one("#text").text == "why is the sky"
        await pilot.press("ctrl+q")
        await pilot.pause()
        assert app.screen.__class__.__name__ == "ConfirmScreen"
        await pilot.press("enter")  # Leave
        await pilot.pause()
        assert app.screen.__class__.__name__ == "HomeScreen"
        _menu(app, "chat")
        await pilot.press("enter")
        await pilot.pause()
        await pilot.press("escape")  # nothing typed: straight back
        await pilot.pause()
        assert app.screen.__class__.__name__ == "HomeScreen"
    run(app, (100, 30), steps)


def test_the_confidence_step_shows_only_its_own_prompt_and_list(tmp_path, monkeypatch):
    app, v = app_for(tmp_path, monkeypatch)

    async def steps(pilot):
        scr = await _session(app, pilot)
        await pilot.press("b")
        await pilot.pause()
        shown = [w for w in scr.query("#panel .hint, #panel #note") if w.display]
        assert len(shown) == 1 and str(shown[0].render()).startswith("You chose B. How sure")
        conf = scr.query_one("#conf")
        assert conf.region.height == 4 and conf.region.bottom <= 23  # every level on screen, above the footer
        await pilot.press("escape")  # back to change the answer: the question's prompt and the note box return
        await pilot.pause()
        assert all(w.display for w in scr.query("#panel .hint, #panel #note"))
        assert "How sure" not in " ".join(str(h.render()) for h in scr.query("#panel .hint"))
    run(app, (60, 24), steps)


@pytest.mark.parametrize("mode", ["test", "lesson", "long", "blurt"])
def test_every_picker_says_how_to_go_back(tmp_path, monkeypatch, mode):
    from tutor_app.screens import PickerScreen
    app, v = app_for(tmp_path, monkeypatch)

    async def steps(pilot):
        app.push_screen(PickerScreen(mode))
        await pilot.pause()
        assert "Esc to go back" in str(app.screen.query_one(".hint").render())
    run(app, (80, 24), steps)


def test_a_narrow_home_screen_keeps_a_one_line_summary_of_the_side_box(tmp_path, monkeypatch):
    app, v = app_for(tmp_path, monkeypatch)

    async def steps(pilot):
        home = app.screen
        for size, narrow in (((60, 24), True), ((80, 24), True), ((120, 40), False)):
            await pilot.resize_terminal(*size)
            await pilot.pause()
            glance = home.query_one("#glance")
            assert glance.display == narrow
            if narrow:
                text = str(glance.render())
                assert "streak" in text and "due" in text and "✶" in text and "↻" in text
                assert glance.region.height == 1 and glance.region.right <= size[0]
                assert home.query_one("#menu").max_scroll_y == 0  # the menu still fits whole
    run(app, (120, 40), steps)


def test_progress_labels_each_day_of_the_coming_reviews(tmp_path, monkeypatch):
    from datetime import timedelta
    from tutor_app.screens import ProgressScreen
    app, v = app_for(tmp_path, monkeypatch)

    async def steps(pilot):
        app.push_screen(ProgressScreen())
        await pilot.pause()
        source = app.screen.query_one("Markdown").source
        now = app.tutor.now()
        days = " · ".join(["today 0"] + [f"{now + timedelta(days=i):%a} 0" for i in range(1, 7)])
        assert f"Reviews due in the next 7 days: {days}." in source
        assert "Esc to go back" not in source  # the footer says it
    run(app, (100, 30), steps)


def test_a_ticked_box_shows_a_tick_and_ctrl_s_confirms_from_the_list(tmp_path, monkeypatch):
    from tutor_app.panels import Panel
    app, v = app_for(tmp_path, monkeypatch)
    done = []

    async def steps(pilot):
        scr = await _session(app, pilot)
        scr.panel(TickPanel("Tick every point (space), then ctrl+s.", [("A1 one", "0", True), ("B1 two", "1", False)],
                            [("mine", "Submit my marks ⏎"), ("ai", "Ask the AI examiner to check")]))
        await pilot.pause()
        ticks = scr.query_one("#ticks")
        rows = [ticks.render_line(y).text for y in range(2)]
        assert rows[0][1] == "✓" and rows[1][1] == " "  # not an X in both, told apart by colour alone
        assert app.focused is ticks
        await pilot.press("ctrl+s")  # at once: perhaps the second press of ctrl+s that submitted a long answer
        await pilot.pause()
        assert not done
        scr.query_one(TickPanel).shown -= 1
        await pilot.press("down", "space", "ctrl+s")
        await pilot.pause()
        assert done and done[-1] == {"button": "mine", "ticked": ["0", "1"]}
        assert [ticks.render_line(y).text[1] for y in range(2)] == ["✓", "✓"]
    monkeypatch.setattr(Panel, "finish", lambda self, data: done.append(data))
    run(app, (80, 24), steps)


def test_the_test_picker_starts_with_ctrl_s_from_the_list(tmp_path, monkeypatch):
    app, v = app_for(tmp_path, monkeypatch)

    async def steps(pilot):
        _menu(app, "test")
        await pilot.press("enter")
        await pilot.pause()
        assert "ctrl+s" in str(app.screen.query_one(".hint").render())
        await pilot.press("space", "ctrl+s")
        await pilot.pause()
        await pilot.pause()
        assert app.screen.__class__.__name__ == "SessionScreen"
    run(app, (80, 24), steps)


def test_the_session_footer_always_fits_menu_help_ask_and_hint_at_60_columns(tmp_path, monkeypatch):
    from tutor_app.panels import LongPanel

    async def fits(scr, pilot, when, typing=False):
        await pilot.pause()
        keys = {k.description: k for k in scr.query("FooterKey")}
        for name in ("Menu", "Ask", "Hint") + (() if typing else ("Help",)):  # typing, ? is a character
            assert name in keys and keys[name].region.width and keys[name].region.right <= 60, (when, name)
        assert "Earlier" not in keys  # the least needed: Help names ctrl+l

    app, v = app_for(tmp_path, monkeypatch)

    async def steps(pilot):
        scr = await _session(app, pilot)
        await fits(scr, pilot, "question")
        await pilot.press("b")
        await fits(scr, pilot, "confidence")
        scr.panel(LongPanel(1))
        await fits(scr, pilot, "long answer", typing=True)
    run(app, (60, 24), steps)


def _screen_text(app) -> str:
    import html
    import re
    return html.unescape("".join(re.findall(r">([^<>]*)</text>", app.export_screenshot()))).replace("\xa0", " ")


def test_a_checked_blurt_shows_what_you_wrote_before_what_you_recalled(tmp_path, monkeypatch):
    app, v = app_for(tmp_path, monkeypatch)

    async def steps(pilot):
        _menu(app, "blurt")
        await pilot.press("enter")
        await pilot.pause()
        await pilot.press("enter")
        await pilot.pause()
        await pilot.press(*"displacement has direction", "ctrl+s")
        await pilot.pause()
        app.screen.query_one("#log").scroll_home(animate=False)
        await pilot.pause()
        text = _screen_text(app)
        assert "You wrote" in text and "displacement has direction" in text
        assert text.index("You wrote") < text.index("You recalled")
    run(app, (120, 40), steps)


def test_a_hint_asked_for_after_answering_says_the_question_is_already_marked(tmp_path, monkeypatch):
    app, v = app_for(tmp_path, monkeypatch)
    said = []

    async def steps(pilot):
        monkeypatch.setattr(app, "notify", lambda msg, **k: said.append(msg))
        scr = await _session(app, pilot)
        n = scr.view["n"]
        scr.submit({"entry": f"{n}?", "your": "I don't know"})
        await pilot.pause()
        for key in ("h", "ctrl+g"):
            said.clear()
            await pilot.press(key)
            await pilot.pause()
            assert said == [f"No hint needed: Q{n} is already marked."], key
    run(app, (100, 30), steps)


def test_the_choose_step_says_what_it_is_asking(tmp_path, monkeypatch):
    app, v = app_for(tmp_path, monkeypatch)

    async def steps(pilot):
        scr = await _session(app, pilot)
        monkeypatch.setattr(app.tutor, "next", lambda: {"activity": "choose", "question": "How do you want to learn this?",
                                                        "options": {"build": "Build it step by step"}})
        scr.advance()
        await pilot.pause()
        assert str(scr.query_one("#panel .hint").render()) == "Pick how you want to learn this (↑↓ and ⏎)"
    run(app, (100, 30), steps)


def test_help_says_how_to_scroll_the_session(tmp_path, monkeypatch):
    app, v = app_for(tmp_path, monkeypatch)

    async def steps(pilot):
        app.action_help()
        await pilot.pause()
        assert "alt+↑" in app.screen.query_one("Markdown").source
    run(app, (100, 30), steps)
