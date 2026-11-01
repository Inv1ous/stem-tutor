"""Leaving an empty search must not strand keyboard navigation in a topic folder."""
import pytest

from test_tui import app_for
from test_picker import ids, run
from tutor_app.screens import PickerScreen


@pytest.mark.parametrize('size', [(80, 24), (100, 30), (140, 46)])
@pytest.mark.parametrize('erase', [False, True])
def test_escape_leaves_folder_when_search_was_focused_but_left_empty(tmp_path, monkeypatch, size, erase):
    app, _ = app_for(tmp_path, monkeypatch)

    async def steps(pilot):
        app.push_screen(PickerScreen('lesson'))
        await pilot.pause()
        await pilot.press('enter')  # Chemistry
        await pilot.pause()
        picker = app.screen
        assert picker.path == ['chem']
        await pilot.press('slash')
        if erase:
            await pilot.press('c', 'backspace')
            assert picker.path == ['chem']  # Backspace still edits Search.
            assert picker.query_one('#find').value == ''
        await pilot.press('escape')
        await pilot.pause()
        assert picker.path == []
        assert ids(picker) == ['dir:chem', 'dir:phys', 'dir:math']
        assert picker.focused.id == 'subs'

    run(app, steps, size=size)
