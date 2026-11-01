"""Cosmetic Terminal setup must have a bounded path to the first app screen."""
import subprocess

import pytest
from types import SimpleNamespace

from tutor_app import __main__ as cli, mac


def test_a_stalled_profile_does_not_spend_another_font_timeout_before_the_app(monkeypatch, tmp_path):
    from tutor_app import app as app_module
    clock = [0.0]
    calls, ran = [], []
    monkeypatch.setenv("TERM_PROGRAM", "Apple_Terminal")
    monkeypatch.setattr(mac, "terminal_tty", lambda: "/dev/fake")
    monkeypatch.setattr(cli.time, "monotonic", lambda: clock[0])
    monkeypatch.setattr(cli.time, "sleep", lambda seconds: clock.__setitem__(0, clock[0] + seconds))

    def stalled(args, **kwargs):
        calls.append(kwargs["timeout"])
        clock[0] += kwargs["timeout"]
        raise subprocess.TimeoutExpired(args, kwargs["timeout"])
    monkeypatch.setattr(mac.subprocess, "run", stalled)
    monkeypatch.setattr(mac, "cell_size", lambda: None)

    class FakeApp:
        TITLE, return_code = "Test", 0
        settings = SimpleNamespace(theme="night")
        tty_profile = None
        def __init__(self, vault): pass
        def settle_font_size(self): mac.terminal_font_size(self.tty)
        def match_zoom(self, cell, measure): return cell
        def note_zoom(self, before, after): pass
        def run(self): ran.append(clock[0])
    monkeypatch.setattr(app_module, "TutorApp", FakeApp)
    assert cli.main(["--vault", str(tmp_path)]) == 0
    assert ran and ran[0] <= 2.0
    assert len(calls) == 1  # don't queue a second cosmetic operation after the budget is spent


def test_non_terminal_startup_does_not_sleep_or_measure(monkeypatch, tmp_path):
    from tutor_app import app as app_module
    slept, measured = [], []
    monkeypatch.setattr(cli.time, "sleep", slept.append)
    monkeypatch.setattr(mac, "cell_size", lambda: measured.append(True))
    monkeypatch.setattr(app_module.TutorApp, "run", lambda self: None)
    assert cli.main(["--vault", str(tmp_path)]) == 0
    assert slept == [] and measured == []


def test_double_click_launcher_defers_profile_setup_to_the_bounded_app_path():
    import sys
    from pathlib import Path
    sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "build"))
    import publish
    script = publish.launcher_script()
    assert 'export STEM_TUTOR_STUDY_PROFILE=1' in script
    assert "osascript" not in script


def test_saved_font_zoom_and_launcher_study_profile_survive_bounded_setup(monkeypatch, tmp_path):
    import json
    from tutor_app import app as app_module, config
    (tmp_path / ".tutor").mkdir()
    (tmp_path / ".tutor/app_settings.json").write_text(json.dumps({
        "theme": "night", "font_size": 17, "font_zoom_cell": 19.0,
    }))
    monkeypatch.setenv("STEM_TUTOR_STUDY_PROFILE", "1")
    monkeypatch.setattr(mac, "terminal_tty", lambda: "/dev/fake")
    monkeypatch.setattr(cli.time, "sleep", lambda seconds: None)
    profiles, sizes, tab, seen = [], [], [13], []

    def profile(tty, name):
        profiles.append(name)
        tab[0] = 13
        return "ok", "Study"

    def font(tty, set_to=None):
        if set_to:
            sizes.append(set_to)
            tab[0] = set_to
        return tab[0]
    monkeypatch.setattr(mac, "switch_terminal_profile", profile)
    monkeypatch.setattr(mac, "terminal_font_size", font)
    monkeypatch.setattr(mac, "cell_size", lambda: (8, float(tab[0])))
    monkeypatch.setattr(app_module.TutorApp, "run", lambda self: seen.append(tab[0]))
    assert cli.main(["--vault", str(tmp_path)]) == 0
    assert profiles == ["Study", "STEM Tutor Night", "Study"]
    assert sizes == [17, 18, 19] and seen == [19]
    assert config.Settings.load(tmp_path).font_size == 19
    assert config.Settings.load(tmp_path).font_zoom_cell == 0


def test_geometry_queries_without_replies_return_promptly_and_restore_the_tty(monkeypatch):
    import os
    import pty
    import termios
    import time
    master, slave = pty.openpty()
    before = termios.tcgetattr(slave)
    real_open = os.open
    monkeypatch.setenv("TERM_PROGRAM", "Apple_Terminal")
    monkeypatch.setattr(mac.os, "open", lambda path, *args: os.dup(slave) if path == "/dev/tty" else real_open(path, *args))
    try:
        started = time.monotonic()
        assert mac.cell_size() is None
        assert time.monotonic() - started < 0.75
        after = termios.tcgetattr(slave)
        # Darwin marks pending input while changing line discipline; PENDIN is kernel bookkeeping.
        after[3] &= ~getattr(termios, "PENDIN", 0)
        before[3] &= ~getattr(termios, "PENDIN", 0)
        assert after == before
    finally:
        os.close(slave)
        os.close(master)


@pytest.mark.parametrize("target,budget", [(25.0, 2.0), (13.0, 0.9)])
def test_zoom_matching_keeps_its_target_when_slow_successes_exhaust_the_budget(monkeypatch, tmp_path, target, budget):
    from tutor_app.app import TutorApp
    app = TutorApp(tmp_path)
    app.tty, app.font_base = "/dev/fake", 13
    app.settings.font_zoom_cell = target
    clock, size = [0.0], [13]
    monkeypatch.setenv("TERM_PROGRAM", "Apple_Terminal")
    monkeypatch.setattr(cli.time, "monotonic", lambda: clock[0])
    monkeypatch.setattr(cli.time, "sleep", lambda seconds: clock.__setitem__(0, clock[0] + seconds))

    def slow_success(args, **kwargs):
        delay = min(0.4, kwargs["timeout"])
        clock[0] += delay
        if delay < 0.4:
            raise subprocess.TimeoutExpired(args, kwargs["timeout"])
        size[0] = int(args[-1])
        return subprocess.CompletedProcess(args, 0, stdout=str(size[0]), stderr="")
    monkeypatch.setattr(mac.subprocess, "run", slow_success)
    with mac.terminal_budget(budget):
        app.match_zoom((8.0, 13.0), lambda: (8.0, float(size[0])))
    assert clock[0] <= budget
    assert app.settings.font_zoom_cell == target and app.zoom_kept is None


def test_a_stalled_profile_restore_does_not_hold_the_app_open_after_quitting(monkeypatch, tmp_path):
    from tutor_app import app as app_module
    clock, finished = [0.0], []
    monkeypatch.setenv("TERM_PROGRAM", "Apple_Terminal")
    monkeypatch.setattr(mac, "terminal_tty", lambda: "/dev/fake")
    monkeypatch.setattr(cli.time, "monotonic", lambda: clock[0])
    monkeypatch.setattr(cli.time, "sleep", lambda seconds: clock.__setitem__(0, clock[0] + seconds))
    monkeypatch.setattr(mac, "cell_size", lambda: None)

    def restore_stalls(args, **kwargs):
        if args[-1] == "Basic":
            clock[0] += kwargs["timeout"]
            raise subprocess.TimeoutExpired(args, kwargs["timeout"])
        return subprocess.CompletedProcess(args, 0, stdout="ok\nBasic", stderr="")
    monkeypatch.setattr(mac.subprocess, "run", restore_stalls)

    class FakeApp:
        TITLE, return_code = "Test", 0
        settings = SimpleNamespace(theme="night")
        tty_profile = None
        def __init__(self, vault): pass
        def settle_font_size(self): pass
        def match_zoom(self, cell, measure): return cell
        def note_zoom(self, before, after): pass
        def run(self): finished.append(clock[0])
    monkeypatch.setattr(app_module, "TutorApp", FakeApp)
    assert cli.main(["--vault", str(tmp_path)]) == 0
    assert clock[0] - finished[0] <= 2.0
