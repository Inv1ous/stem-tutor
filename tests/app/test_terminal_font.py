"""Asked by the learner: the text size had to be set again every time the tutor was started. Terminal's ⌘+ / ⌘− zoom
turned out to be invisible to AppleScript (it kept reporting the profile's size), so the tutor has its own keys,
⌥+ ⌥− ⌥0, applied on the tab and kept at once, and measures the character cell at the end to catch a ⌘ zoom."""
import asyncio
import subprocess

from tutor_app import config, mac
from test_tui import app_for


def test_the_font_size_settings_are_kept_and_a_silly_value_is_ignored(tmp_path):
    assert config.Settings().font_size == 0 and config.Settings().font_zoom_cell == 0
    v = tmp_path
    for value, kept in ((16, 16), (0, 0), (500, 0), (3, 0), ('"big"', 0), (13.5, 0)):
        (v / ".tutor").mkdir(exist_ok=True)
        (v / ".tutor/app_settings.json").write_text('{"font_size": %s}' % value)
        assert config.Settings.load(v).font_size == kept, value


def test_terminal_is_asked_for_and_given_a_tabs_text_size(monkeypatch):
    calls = []

    def fake_run(args, **kw):
        calls.append((args, kw.get("input", "")))
        return subprocess.CompletedProcess(args, 0, stdout="16\n", stderr="")
    monkeypatch.setattr(mac.subprocess, "run", fake_run)
    monkeypatch.setenv("TERM_PROGRAM", "Apple_Terminal")
    assert mac.terminal_font_size("/dev/ttys009") == 16
    assert mac.terminal_font_size("/dev/ttys009", 18) == 16
    assert calls[1][0] == ["osascript", "-", "/dev/ttys009", "18"]
    assert "font size of current settings of t" in calls[0][1]  # the tab's own settings, never the profile's
    monkeypatch.delenv("TERM_PROGRAM")
    assert mac.terminal_font_size("/dev/ttys009") is None and len(calls) == 2


def test_the_character_cell_is_read_from_terminals_two_answers():
    # measured in the learner's Terminal: 24 rows × 69 columns in a 353 × 503 point text area, then after ⌘+
    assert mac.cell_from(b"\x1b[4;353;503t", b"\x1b[8;24;69t") == (503 / 69, 353 / 24)
    assert mac.cell_from(b"\x1b[4;377;503t", b"\x1b[8;24;69t")[1] > 353 / 24
    assert mac.cell_from(b"", b"\x1b[8;24;69t") is None and mac.cell_from(b"\x1b[4;1;1t", b"\x1b[8;0;0t") is None


class FakeTab:
    """One Terminal tab: the profile brings its size; the tutor's AppleScript sets it."""
    def __init__(self, profile_size=13):
        self.profile_size, self.size = profile_size, profile_size

    def font_size(self, tty, set_to=None):
        if set_to:
            self.size = set_to
        return self.size


def run(app, steps):
    async def go():
        async with app.run_test(size=(100, 30)) as pilot:
            await pilot.pause()
            await steps(pilot)
            await pilot.pause()
            await app.workers.wait_for_complete()
            await app.ai.close()
    asyncio.run(go())


def test_option_keys_change_the_size_on_the_tab_and_keep_it_at_once(tmp_path, monkeypatch):
    app, v = app_for(tmp_path, monkeypatch)
    tab = FakeTab(13)
    monkeypatch.setattr(mac, "terminal_font_size", tab.font_size)
    app.tty = "/dev/ttys009"
    app.settle_font_size()

    async def steps(pilot):
        for key in ("not_equal_to", "alt+equals_sign"):  # ⌥= with Option as itself, and as Meta
            await pilot.press(key)
            await app.workers.wait_for_complete()
        assert tab.size == 15 and config.Settings.load(v).font_size == 15  # saved the moment it changed
        await pilot.press("en_dash")
        await app.workers.wait_for_complete()
        assert tab.size == 14 and config.Settings.load(v).font_size == 14
        await pilot.press("º")  # ⌥0: the look's own size again, and nothing to remember
        await app.workers.wait_for_complete()
        assert tab.size == 13 and config.Settings.load(v).font_size == 0
    run(app, steps)


def test_the_size_chosen_comes_back_after_the_profile_switch(tmp_path, monkeypatch):
    app, v = app_for(tmp_path, monkeypatch)
    tab = FakeTab(13)
    monkeypatch.setattr(mac, "terminal_font_size", tab.font_size)
    app.tty, app.settings.font_size = "/dev/ttys009", 17
    app.settle_font_size()
    assert tab.size == 17 and app.font_base == 13 and app.text_size() == 17


# character heights measured in the learner's Terminal at each size (⌘+ steps land on exactly these): not even steps
HEIGHT = {9: 12.0, 10: 13.7, 11: 14.71, 12: 15.71, 13: 17.67, 14: 18.67, 15: 19.67, 16: 20.67, 17: 21.67, 18: 23.62}


def test_a_cmd_zoom_is_kept_exactly_by_matching_its_character_height_at_the_next_start(tmp_path, monkeypatch):
    app, v = app_for(tmp_path, monkeypatch)
    tab = FakeTab(11)
    monkeypatch.setattr(mac, "terminal_font_size", tab.font_size)
    app.tty, app.settings.font_size = "/dev/ttys009", 13
    app.settle_font_size()
    start = (8.22, HEIGHT[13])
    app.note_zoom(start, start)
    assert config.Settings.load(v).font_zoom_cell == 0  # no zoom: nothing changes
    app.note_zoom(start, (9.22, HEIGHT[15]))  # two ⌘+ from 13 pt: really 15 pt
    s = config.Settings.load(v)
    assert s.font_zoom_cell == HEIGHT[15] and s.font_size in (14, 15)  # a guess: heights do not grow evenly
    from test_tui import FAKE
    from tutor_app.app import TutorApp
    nxt = TutorApp(v, claude_binary=FAKE, open_obsidian=False, seed=1)  # the next start, a new window with no zoom
    tab.size = 11
    nxt.tty = "/dev/ttys009"
    nxt.settle_font_size()
    cell = nxt.match_zoom((8.0, HEIGHT[tab.size]), lambda: (8.0, HEIGHT[tab.size]), settle=0)
    assert tab.size == 15 and cell[1] == HEIGHT[15] and nxt.zoom_kept == 15
    s = config.Settings.load(v)
    assert s.font_size == 15 and s.font_zoom_cell == 0  # matched once, then forgotten
    said = []
    monkeypatch.setattr(nxt, "notify", lambda msg, **kw: said.append(msg))
    run(nxt, lambda pilot: asyncio.sleep(0))
    assert any("kept: 15 pt" in m and "⌥+" in m for m in said)


def test_matching_stops_at_the_nearest_size_when_no_size_has_that_height(tmp_path, monkeypatch):
    app, v = app_for(tmp_path, monkeypatch)
    tab = FakeTab(11)
    monkeypatch.setattr(mac, "terminal_font_size", tab.font_size)
    app.tty = "/dev/ttys009"
    app.settle_font_size()
    app.settings.font_zoom_cell = 17.0  # between 12 (15.71) and 13 (17.67): 13 is nearer
    app.match_zoom((7.2, HEIGHT[11]), lambda: (7.2, HEIGHT[tab.size]), settle=0)
    assert tab.size == 13 and app.settings.font_size == 13 and app.settings.font_zoom_cell == 0


def test_a_window_still_zoomed_with_cmd_keeps_the_height_for_a_fresh_window(tmp_path, monkeypatch):
    """The tutor started again in the window it was zoomed in: no size it sets shows, so nothing is matched yet."""
    app, v = app_for(tmp_path, monkeypatch)
    tab = FakeTab(11)
    monkeypatch.setattr(mac, "terminal_font_size", tab.font_size)
    app.tty, app.settings.font_size, app.settings.font_zoom_cell = "/dev/ttys009", 14, HEIGHT[15]
    app.settle_font_size()
    zoomed = (9.22, HEIGHT[15])  # what the window shows whatever size is set
    assert app.match_zoom(zoomed, lambda: zoomed, settle=0) == zoomed
    assert app.settings.font_zoom_cell == HEIGHT[15] and app.zoom_kept is None and tab.size == 14


def test_sizing_with_option_keys_this_time_means_no_zoom_guess(tmp_path, monkeypatch):
    app, v = app_for(tmp_path, monkeypatch)
    app.tty, app.font_base, app.font_changed = "/dev/ttys009", 11, True
    app.note_zoom((7.2, HEIGHT[11]), (7.2, HEIGHT[14]))
    assert config.Settings.load(v).font_zoom_cell == 0


def test_without_terminal_the_keys_say_where_they_work(tmp_path, monkeypatch):
    app, v = app_for(tmp_path, monkeypatch)
    said = []
    monkeypatch.setattr(app, "notify", lambda msg, **kw: said.append(msg))

    async def steps(pilot):
        await pilot.press("not_equal_to")
    run(app, steps)
    assert any("macOS Terminal" in m for m in said) and config.Settings.load(v).font_size == 0


def test_the_settings_row_sets_the_size(tmp_path, monkeypatch):
    from textual.widgets import Input
    app, v = app_for(tmp_path, monkeypatch)
    tab = FakeTab(13)
    monkeypatch.setattr(mac, "terminal_font_size", tab.font_size)
    app.tty = "/dev/ttys009"
    app.settle_font_size()

    async def steps(pilot):
        await pilot.press("f2")
        await pilot.pause()
        assert app.screen.query_one("#font_size", Input).value == "13"
        app.screen.query_one("#font_size", Input).value = "16"
        app.screen.query_one("#save").press()
        await pilot.pause()
    run(app, steps)
    assert tab.size == 16 and config.Settings.load(v).font_size == 16


def test_the_text_size_row_in_settings_reads_on_one_line_at_every_size(tmp_path, monkeypatch):
    """Reported by the learner: the row's label stood one letter per line, its box having no width of its own."""
    from textual.widgets import Input, Static
    for size in ((80, 24), (100, 30), (140, 46)):
        app, v = app_for(tmp_path / f"{size[0]}", monkeypatch)

        async def steps(pilot, size=size):
            await pilot.press("f2")
            await pilot.pause()
            box = app.screen.query_one("#font_size", Input)
            label = box.parent.query_one(Static)
            assert box.size.width <= 12, size
            assert label.size.height == 1 and label.size.width >= 20, (size, label.size)
        run(app, steps)
