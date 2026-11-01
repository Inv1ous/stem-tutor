"""Focused topic labels must stay readable over each theme's cursor background."""
import asyncio

import pytest

from test_tui import app_for
from test_look import contrast
from tutor_app import look
from tutor_app.screens import PickerScreen
from textual.widgets import OptionList


@pytest.mark.parametrize('size', [(80, 24), (100, 30), (140, 46)])
@pytest.mark.parametrize('theme', ['classic', 'night', 'day'])
@pytest.mark.parametrize('state', ['focused', 'blurred', 'hover'])
@pytest.mark.parametrize('folder', [False, True])
def test_focused_and_hovered_topic_names_remain_readable(tmp_path, monkeypatch, theme, folder, size, state):
    app, _ = app_for(tmp_path, monkeypatch)
    app.settings.theme = theme
    look.use(theme)

    async def go():
        async with app.run_test(size=size) as pilot:
            app.push_screen(PickerScreen('test'))
            await pilot.pause()
            picker = app.screen
            if folder:
                picker.path = []
                picker.fill()
                await pilot.pause()
            box = picker.query_one('#subs', OptionList)
            if state == 'blurred':
                picker.query_one('#find').focus()
                await pilot.pause()
            label = 'Physics' if folder else 'Equations of motion'
            y = next(y for y, (index, _) in enumerate(box._lines) if index == box.highlighted)
            if state == 'hover':
                box._mouse_hovering_over = box.highlighted
                box.highlighted = None
            strip = box.render_line(y - box.scroll_offset.y)
            segments = [segment for segment in strip if label in segment.text]
            assert segments, (label, strip)
            for segment in segments:
                fg = segment.style.color.get_truecolor().hex
                bg = segment.style.bgcolor.get_truecolor().hex
                assert contrast(fg, bg) >= 4.5, (theme, label, fg, bg)
            box.highlighted = None
            box._mouse_hovering_over = None
            unselected = box.render_line(y - box.scroll_offset.y)
            names = [segment for segment in unselected if label in segment.text]
            assert names and all(segment.style.color.get_truecolor().hex == look.C['text'] for segment in names)
            await app.ai.close()

    try:
        asyncio.run(go())
    finally:
        look.use('classic')
