"""Resizing the window must settle: one footer and one bottom bar per screen, the same layout for the same size, one
clear per narrower size, and no hang when the window is dragged while the app is still starting."""
import asyncio

import pytest
from textual.widgets import Footer

from test_tui import app_for

SIZES = [(60, 20), (80, 24), (120, 40), (200, 60)]


def regions(screen):
    """Every widget's box, so two frames of the same size can be compared cell for cell."""
    out = {}
    for widget in screen.walk_children():
        try:
            out[f"{type(widget).__name__}#{widget.id or ''}"] = tuple(widget.region)
        except Exception:  # a widget on its way out has no region yet
            continue
    return out


def bottom_bars(screen):
    """Bottom-docked widgets other than the footer itself: a second bar under it is the stacked-bar glitch."""
    return [widget for widget in screen.walk_children()
            if not isinstance(widget, Footer) and widget.styles.dock == "bottom"]


def screens(v):
    """Every screen the learner can reach, built the way the app builds it."""
    from tutor_app import challenge_screen as cs, dialogs, practice_screens as ps, screens as sc
    from tutor_app import shortcuts_screen as ss, source_practice_screen as sps
    from tutorlib import shortcuts
    return [
        ("SettingsScreen", lambda: sc.SettingsScreen()),
        ("HelpScreen", lambda: sc.HelpScreen()),
        ("ConfirmScreen", lambda: dialogs.ConfirmScreen("q?", [("a", "A"), ("b", "B")])),
        ("AskScreen", lambda: dialogs.AskScreen()),
        ("PickerScreen", lambda: sc.PickerScreen("lesson")),
        ("SummaryScreen", lambda: dialogs.SummaryScreen({"answered": 1, "correct": 1, "accuracy": 1.0,
                                                         "marks": (1, 1), "kcs_learned": []})),
        ("ChallengeScreen", lambda: cs.ChallengeScreen()),
        ("ShortcutsScreen", lambda: ss.ShortcutsScreen()),
        ("ShortcutRecallScreen", lambda: ss.ShortcutRecallScreen()),
        ("ShortcutSettingsScreen", lambda: ss.ShortcutSettingsScreen(shortcuts.Course(v))),
        ("SourcePracticeScreen", lambda: sps.SourcePracticeScreen()),
        ("ChatScreen", lambda: sc.ChatScreen()),
        ("BlurtScreen", lambda: sc.BlurtScreen("9702-2.1")),
        ("InsightsScreen", lambda: sc.InsightsScreen()),
        ("ProgressScreen", lambda: sc.ProgressScreen()),
        ("SavedAttemptsScreen", lambda: sc.SavedAttemptsScreen()),
        ("PracticeSetupScreen", lambda: ps.PracticeSetupScreen(["9702-2.1"])),
        ("TopicalSetupScreen", lambda: sc.TopicalSetupScreen(["9702-2.1"])),
    ]


def test_every_screen_has_one_footer_and_one_bottom_bar(tmp_path, monkeypatch):
    app, v = app_for(tmp_path, monkeypatch)

    async def go():
        async with app.run_test(size=(120, 40)) as pilot:
            await pilot.pause()
            for name, make in [("HomeScreen", None)] + screens(v):
                if make is not None:
                    app.push_screen(make())
                    await pilot.pause()
                for size in SIZES:
                    await pilot.resize_terminal(*size)
                    await pilot.pause()
                    footers, bars = app.screen.query(Footer), bottom_bars(app.screen)
                    assert len(footers) <= 1, f"{name} at {size} has {len(footers)} footers"
                    assert len(bars) <= 1, f"{name} at {size} has bottom bars {[type(b).__name__ for b in bars]}"
                    assert not (footers and bars), f"{name} at {size} stacks a footer under another bottom bar"
                if make is not None:
                    app.pop_screen()
                    await pilot.pause()
            await app.ai.close()

    asyncio.run(go())


def test_the_same_size_twice_gives_the_same_layout(tmp_path, monkeypatch):
    app, v = app_for(tmp_path, monkeypatch)

    async def go():
        async with app.run_test(size=(120, 40)) as pilot:
            await pilot.pause()
            for name, make in [("HomeScreen", None)] + screens(v):
                if make is not None:
                    app.push_screen(make())
                    await pilot.pause()
                for size in SIZES:
                    await pilot.resize_terminal(*size)
                    await pilot.pause()
                    first = regions(app.screen)
                    await pilot.resize_terminal(*size)
                    await pilot.pause()
                    second = regions(app.screen)
                    assert first == second, f"{name} at {size} moved: " + str(
                        {k: (first.get(k), second.get(k)) for k in set(first) | set(second)
                         if first.get(k) != second.get(k)})
                if make is not None:
                    app.pop_screen()
                    await pilot.pause()
            await app.ai.close()

    asyncio.run(go())


def test_a_narrower_window_clears_once_and_a_wider_one_never(tmp_path, monkeypatch):
    app, v = app_for(tmp_path, monkeypatch)

    async def go():
        async with app.run_test(size=(120, 40)) as pilot:
            await pilot.pause()
            written = []
            write = app._driver.write
            app._driver.write = lambda data: (written.append(data), write(data))[1]
            for size, clears in [((80, 24), 1), ((80, 24), 0), ((120, 40), 0), ((200, 60), 0), ((60, 20), 1)]:
                written.clear()
                await pilot.resize_terminal(*size)
                await pilot.pause(0.15)
                assert len([data for data in written if "\x1b[2J" in data]) == clears, f"{size} cleared wrongly"
            await app.ai.close()

    asyncio.run(go())


def test_resize_during_startup_does_not_hang(tmp_path, monkeypatch):
    app, v = app_for(tmp_path, monkeypatch)

    async def go():
        async with app.run_test(size=(120, 40)) as pilot:
            for size in [(60, 20), (200, 60), (80, 24), (120, 40)]:  # dragged while the engine is still loading
                await pilot.resize_terminal(*size)
            await pilot.pause()
            assert app.screen.__class__.__name__ == "HomeScreen"
            assert len(app.screen.query(Footer)) == 1
            await app.ai.close()

    asyncio.run(asyncio.wait_for(go(), 20))


def test_a_frozen_screen_loop_writes_every_threads_stack_to_the_freeze_log(tmp_path, monkeypatch):
    import time
    from tutor_app.app import TutorApp
    monkeypatch.setattr(TutorApp, "FREEZE_SECONDS", 0.6)
    app, v = app_for(tmp_path, monkeypatch)
    log = v / ".tutor" / "logs" / "freeze.log"

    async def go():
        async with app.run_test(size=(120, 40)) as pilot:
            await asyncio.sleep(1.5)                       # a healthy loop keeps re-arming: nothing is written
            assert "Thread" not in log.read_text()
            time.sleep(1.5)                                # the screen loop stuck, as in a freeze
            await pilot.pause()
            text = log.read_text()
            assert "STEM Tutor started" in text and "Timeout" in text and "test_resize_stability.py" in text
            await app.ai.close()

    asyncio.run(asyncio.wait_for(go(), 20))


def test_a_drag_lays_the_screen_out_a_few_times_not_once_per_signal(tmp_path, monkeypatch):
    """A mouse drag sends a resize signal for every few pixels: hundreds, each a new size. Laying out and drawing the
    whole screen for each one queued minutes of work while the startup workers were still reading the Library (the
    learner's freeze log, 2026-11-09). The window is laid out when it settles, and at most twice a second while it
    is still moving."""
    from textual import events
    from textual.geometry import Size
    from textual.screen import Screen
    from tutor_app.app import TutorApp
    monkeypatch.setattr(TutorApp, "RESIZE_SETTLE", 0.1)
    app, v = app_for(tmp_path, monkeypatch)
    layouts = []
    original = Screen._screen_resized

    def counted(self, size):
        if self is app.screen:
            layouts.append(size)
        return original(self, size)
    monkeypatch.setattr(Screen, "_screen_resized", counted)

    async def go():
        async with app.run_test(size=(120, 40)) as pilot:
            await pilot.pause()
            layouts.clear()
            sizes = [(80 + i % 60, 24 + i % 20) for i in range(150)]   # about 1.5 s of dragging
            began = asyncio.get_running_loop().time()
            for w, h in sizes:
                app.post_message(events.Resize(Size(w, h), Size(w, h)))
                await asyncio.sleep(0.01)
            dragged = asyncio.get_running_loop().time() - began
            await asyncio.sleep(0.3)
            await pilot.pause()
            sizes_laid_out = [s for i, s in enumerate(layouts) if i == 0 or layouts[i - 1] != s]
            most = int(dragged / TutorApp.RESIZE_MAX_WAIT) + 2               # one per half second, and the settled size
            assert 1 <= len(sizes_laid_out) <= most < len(sizes) // 4, f"{len(sizes_laid_out)} sizes laid out in {dragged:.1f} s"
            assert app.size == Size(*sizes[-1]) and layouts[-1] == Size(*sizes[-1])   # it ends at the size it settled on
            assert tuple(app.screen.region.size) == sizes[-1]
            await app.ai.close()

    asyncio.run(asyncio.wait_for(go(), 30))


def slow_engine(monkeypatch, seconds):
    """The engine checks every Library resource it uses; on a cold disk that takes a while."""
    import time
    from tutor_app import app as app_module
    real = app_module.Tutor

    def slow(*args, **kwargs):
        time.sleep(seconds)
        return real(*args, **kwargs)
    monkeypatch.setattr(app_module, "Tutor", slow)
    monkeypatch.setattr(app_module.TutorApp, "LOAD_IN_BACKGROUND", True)


def test_the_loading_screen_stays_responsive_while_the_engine_loads(tmp_path, monkeypatch):
    slow_engine(monkeypatch, 1.5)
    app, v = app_for(tmp_path, monkeypatch)

    async def go():
        async with app.run_test(size=(120, 40)) as pilot:
            await pilot.pause()
            assert not hasattr(app, "tutor")                                # still loading
            await asyncio.wait_for(pilot.resize_terminal(70, 22), 0.5)      # the screen handles a resize meanwhile
            assert app.size == (70, 22) and app.screen.region.size == (70, 22)
            for _ in range(100):
                await asyncio.sleep(0.05)
                if app.screen.__class__.__name__ == "HomeScreen":
                    break
            assert app.screen.__class__.__name__ == "HomeScreen" and hasattr(app, "tutor")
            await app.ai.close()

    asyncio.run(asyncio.wait_for(go(), 20))


def test_quitting_while_the_engine_loads_closes_and_frees_the_vault(tmp_path, monkeypatch):
    from tutorlib import store
    slow_engine(monkeypatch, 1.0)
    app, v = app_for(tmp_path, monkeypatch)

    async def go():
        async with app.run_test(size=(120, 40)) as pilot:
            await pilot.pause()
            assert not hasattr(app, "tutor")
            await pilot.press("ctrl+q")
            await pilot.pause()

    asyncio.run(asyncio.wait_for(go(), 20))
    assert not app._loading.is_alive()                                     # the load finished before the lock went
    assert not hasattr(app, "tutor")                                       # nothing opened after the window closed
    with store.Vault(v).lock(wait_seconds=1):                              # and the next start can open the vault
        pass
