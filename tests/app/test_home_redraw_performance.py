"""Cosmetic home redraws must not authenticate question banks on the UI thread."""
import asyncio
from contextlib import contextmanager

from test_tui import app_for


def test_home_ram_timer_and_resize_reuse_display_readiness(tmp_path, monkeypatch):
    app, _ = app_for(tmp_path, monkeypatch)
    app.settings.usage_display = 'both'

    async def go():
        async with app.run_test(size=(120, 40)) as pilot:
            await pilot.pause()
            home = app.screen
            assert home.__class__.__name__ == 'HomeScreen'
            authentications = []
            original = app.tutor.packs.topicals.request

            @contextmanager
            def tracked():
                with original() as outer:
                    if outer:
                        authentications.append(True)
                    yield outer
            monkeypatch.setattr(app.tutor.packs.topicals, 'request', tracked)
            home._draw_stats()
            assert authentications == []
            await pilot.resize_terminal(100, 32)
            await pilot.pause(2.1)  # Exercise the real saved-setting RAM timer.
            assert authentications == []
            home.refresh_home()
            await app.workers.wait_for_complete()  # a forced recheck reads the bank in the background
            await pilot.pause()
            assert authentications == [True]
            await app.ai.close()
    asyncio.run(go())


def test_long_question_picker_uses_display_inventory_without_admission_work(tmp_path, monkeypatch):
    from tutor_app.screens import PickerScreen
    app, _ = app_for(tmp_path, monkeypatch)

    async def go():
        async with app.run_test(size=(120, 40)) as pilot:
            await pilot.pause()
            authentications = []
            original = app.tutor.packs.topicals.request
            @contextmanager
            def tracked():
                with original() as outer:
                    if outer:
                        authentications.append(True)
                    yield outer
            monkeypatch.setattr(app.tutor.packs.topicals, 'request', tracked)
            await app.push_screen(PickerScreen('long'))
            await pilot.pause()
            assert authentications == []
            assert app.screen.built == ['9702-2.1']
            await app.ai.close()
    asyncio.run(go())


def test_startup_lays_out_acknowledgement_before_loading_engine(tmp_path, monkeypatch):
    from tutor_app import app as app_module
    from textual.widgets import Static
    app, _ = app_for(tmp_path, monkeypatch)
    original = app_module.Tutor
    observed = []
    def checked(*args, **kwargs):
        status = app.query_one('#startup-status', Static)
        observed.append(status.region.width)
        assert status.region.width > 0  # First layout has completed before synchronous I/O.
        return original(*args, **kwargs)
    monkeypatch.setattr(app_module, 'Tutor', checked)
    async def go():
        async with app.run_test(size=(120, 40)) as pilot:
            await pilot.pause()
            assert app.screen.__class__.__name__ == 'HomeScreen'
            assert observed
            await app.ai.close()
    asyncio.run(go())


def test_home_recomputes_learning_display_but_reauthenticates_only_changed_resources(tmp_path, monkeypatch):
    app, root = app_for(tmp_path, monkeypatch)
    async def go():
        async with app.run_test(size=(120, 40)) as pilot:
            await pilot.pause()
            authentications = []
            original = app.tutor.packs.topicals.request
            @contextmanager
            def tracked():
                with original() as outer:
                    if outer:
                        authentications.append(True)
                    yield outer
            monkeypatch.setattr(app.tutor.packs.topicals, 'request', tracked)
            app.action_settings()
            await pilot.pause()
            await pilot.press('escape')
            await pilot.pause()
            assert authentications == []
            app.action_settings()
            await pilot.pause()
            app.tutor.state['gaps'].append('9702-2.1.1')
            await pilot.press('escape')
            await pilot.pause()
            assert authentications == []
            assert app.screen._weak_spot_count == 1
            app.action_settings()
            await pilot.pause()
            pointer = root / '.tutor/topicals/CURRENT'
            pointer.parent.mkdir(parents=True, exist_ok=True)
            pointer.write_text('a-new-unavailable-bank')
            await pilot.press('escape')
            await pilot.pause()
            await app.workers.wait_for_complete()  # the changed bank is read in the background, never on the key press
            await pilot.pause()
            assert authentications == [True]
            await app.ai.close()
    asyncio.run(go())


def test_new_mode_does_not_rebuild_hidden_home_before_showing_picker(tmp_path, monkeypatch):
    from textual.widgets import OptionList
    app, _ = app_for(tmp_path, monkeypatch)
    async def go():
        async with app.run_test(size=(120, 40)) as pilot:
            await pilot.pause()
            home = app.screen
            app.tutor.start('test', focus=list(app.tutor.packs.kcs))
            home.refresh_home()
            menu = home.query_one('#menu', OptionList)
            menu.reveal('long')
            await pilot.press('enter')
            await pilot.pause()
            assert app.screen.__class__.__name__ == 'ConfirmScreen'
            authentications = []
            original = app.tutor.packs.topicals.request
            @contextmanager
            def tracked():
                with original() as outer:
                    if outer:
                        authentications.append(True)
                    yield outer
            monkeypatch.setattr(app.tutor.packs.topicals, 'request', tracked)
            app.screen.query_one('#confirm', OptionList).highlighted = 1
            await pilot.press('enter')
            await pilot.pause()
            assert app.screen.__class__.__name__ == 'PickerScreen'
            assert app.tutor.session is None
            assert authentications == []
            await app.ai.close()
    asyncio.run(go())
