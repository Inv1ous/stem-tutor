"""Asked by the learner: the text size (⌘+ / ⌘−) had to be set again every time the tutor was started."""
import asyncio
import subprocess

from tutor_app import config, mac
from test_tui import app_for


def test_the_font_size_setting_is_kept_and_a_silly_value_is_ignored(tmp_path):
    assert config.Settings().font_size == 0
    v = tmp_path
    for value, kept in ((16, 16), (0, 0), (500, 0), (3, 0), ("big", 0), (13.5, 0)):
        (v / ".tutor").mkdir(exist_ok=True)
        (v / ".tutor/app_settings.json").write_text('{"font_size": %s}' % (value if not isinstance(value, str) else f'"{value}"'))
        assert config.Settings.load(v).font_size == kept, value
    s = config.Settings(font_size=18)
    s.save(v)
    assert config.Settings.load(v).font_size == 18


def test_terminal_is_asked_for_and_given_a_tabs_text_size(monkeypatch):
    calls = []

    def fake_run(args, **kw):
        calls.append((args, kw.get("input", "")))
        return subprocess.CompletedProcess(args, 0, stdout="16\n", stderr="")
    monkeypatch.setattr(mac.subprocess, "run", fake_run)
    monkeypatch.setenv("TERM_PROGRAM", "Apple_Terminal")
    assert mac.terminal_font_size("/dev/ttys009") == 16
    assert mac.terminal_font_size("/dev/ttys009", 18) == 16
    assert calls[0][0] == ["osascript", "-", "/dev/ttys009"] and calls[1][0] == ["osascript", "-", "/dev/ttys009", "18"]
    assert "font size of current settings of t" in calls[0][1]  # the tab's own settings, never the profile's
    monkeypatch.delenv("TERM_PROGRAM")
    assert mac.terminal_font_size("/dev/ttys009") is None and mac.terminal_font_size(None) is None and len(calls) == 2
    monkeypatch.setenv("TERM_PROGRAM", "Apple_Terminal")

    def no_tab(args, **kw):
        return subprocess.CompletedProcess(args, 0, stdout="no tab\n", stderr="")
    monkeypatch.setattr(mac.subprocess, "run", no_tab)
    assert mac.terminal_font_size("/dev/ttys009") is None

    def too_slow(args, **kw):
        raise subprocess.TimeoutExpired(args, 10)
    monkeypatch.setattr(mac.subprocess, "run", too_slow)
    assert mac.terminal_font_size("/dev/ttys009") is None


class FakeTab:
    """One Terminal tab: its size comes from the profile it is switched to, and ⌘+ / ⌘− change only the tab."""
    def __init__(self, profile_size=13):
        self.profile_size, self.size, self.sets = profile_size, profile_size, []

    def font_size(self, tty, set_to=None):
        if set_to:
            self.size = set_to
            self.sets.append(set_to)
        return self.size

    def switch_profile(self):
        self.size = self.profile_size


def test_the_learners_text_size_comes_back_after_the_profile_switch_and_is_remembered(tmp_path, monkeypatch):
    app, v = app_for(tmp_path, monkeypatch)
    tab = FakeTab(13)
    monkeypatch.setattr(mac, "terminal_font_size", tab.font_size)
    app.tty = "/dev/ttys009"
    app.settings.font_size = 17  # chosen last time
    tab.switch_profile()
    app.settle_font_size()
    assert tab.size == 17 and app.font_base == 13  # put back, measured from the profile's own 13
    tab.size = 19  # ⌘+ twice during the session
    app.remember_font_size()
    assert app.settings.font_size == 19 and config.Settings.load(v).font_size == 19
    tab.size = 13  # ⌘0 back to the profile's size: nothing to keep
    app.remember_font_size()
    assert app.settings.font_size == 0 and config.Settings.load(v).font_size == 0
    tab.size = 15
    app.remember_font_size()
    tab.switch_profile()  # the look changed, so the tab got another profile and its size
    app.settle_font_size()
    assert tab.size == 15


def test_a_tab_that_cannot_be_asked_changes_nothing(tmp_path, monkeypatch):
    app, v = app_for(tmp_path, monkeypatch)
    monkeypatch.setattr(mac, "terminal_font_size", lambda tty, set_to=None: None)
    app.settings.font_size = 17
    app.settle_font_size()  # not in Terminal, or Automation refused
    app.tty = "/dev/ttys009"
    app.remember_font_size()
    assert app.settings.font_size == 17 and app.font_base is None  # what was chosen is not thrown away


def test_changing_the_look_sets_the_chosen_text_size_again(tmp_path, monkeypatch):
    from tutor_app import look
    app, v = app_for(tmp_path, monkeypatch)
    tab = FakeTab(13)
    settled = []
    monkeypatch.setattr(mac, "switch_terminal_profile", lambda tty, name: (tab.switch_profile(), ("ok", "Basic"))[1])
    monkeypatch.setattr(app, "settle_font_size", lambda: settled.append(tab.size))

    async def go():
        async with app.run_test(size=(100, 30)) as pilot:
            await pilot.pause()
            app.tty = "/dev/ttys009"
            look.apply(app, "day")
            await app.workers.wait_for_complete()
            await app.ai.close()
    asyncio.run(go())
    assert settled == [13]  # asked after the new profile was on the tab, never before
