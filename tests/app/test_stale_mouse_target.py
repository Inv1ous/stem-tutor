"""Mouse input must not target an answer panel removed before the next layout."""
import asyncio

import pytest

from textual import events

from test_tui import app_for
from tutor_app.panels import Composer, ValuePanel
from tutor_app.screens import SessionScreen


@pytest.mark.parametrize("size", [(80, 24), (83, 51)])
def test_click_during_answer_panel_replacement_does_not_crash(tmp_path, monkeypatch, size):
    app, _ = app_for(tmp_path, monkeypatch)
    app.settings.ai = False

    async def go():
        async with app.run_test(size=size) as pilot:
            app.tutor.start('review', minutes=10)
            app.tutor._present({'id': 'click-check', 'kcs': ['9702-2.1.1'], 'kind': 'short',
                                'difficulty': 3, 'marks': 1, 'stem': 'Explain.',
                                'rubric': [{'point': 'A reason', 'keywords': [['reason']]}]},
                               block='practice', phase='form_check')
            screen = SessionScreen(None)
            await app.push_screen(screen)
            await pilot.pause()
            old = ValuePanel(1, 'short', initial='Earlier answer')
            screen.panel(old)
            await pilot.pause()
            region = old.region
            x, y = region.x + 1, region.y
            assert screen.get_widget_at(x, y)[0] is old
            before_events = list(app.tutor.vault.events())
            with app.batch_update():
                await old.remove()
                assert old.parent is None
                hit, offset = screen.get_widget_and_offset_at(x, y)
                assert hit is old and offset is not None, (hit, offset)
                await app.on_event(events.MouseDown(None, x, y, 0, 0, 1, False, False, False))
            assert list(app.tutor.vault.events()) == before_events
            fresh = ValuePanel(2, 'short', initial='My current draft')
            screen.panel(fresh)
            await pilot.pause()
            composer = fresh.query_one('#value', Composer)
            await pilot.click(composer, offset=(2, 0))
            assert composer.has_focus and composer.text == 'My current draft'
            label = screen.say('Selectable lesson explanation', mirror=None)
            await pilot.pause()
            await pilot.mouse_down(label, offset=(1, 0))
            await pilot.hover(label, offset=(10, 0))
            await pilot.mouse_up(label, offset=(10, 0))
            assert screen.get_selected_text()
            await app.on_event(events.MouseDown(None, size[0] + 2, size[1] + 2,
                                               0, 0, 1, False, False, False))
            assert list(app.tutor.vault.events()) == before_events
            assert app.is_running
            await app.ai.close()
    asyncio.run(go())
