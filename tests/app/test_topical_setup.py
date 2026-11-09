"""Native topical set setup preserves topic ticks, editing and session boundaries."""
import asyncio
from copy import deepcopy
import json
import os

import pytest
from rich.cells import cell_len
from textual.widgets import Button, Input, SelectionList, Static

from test_tui import app_for
from test_topicals import TARGET, OTHER, THIRD
from test_topical_selection import mixed_bank
from tutor_app import look
from tutor_app.screens import PickerScreen, SessionScreen


def staged_app(tmp_path, monkeypatch):
    app, root = app_for(tmp_path, monkeypatch)
    app.settings.ai = False
    path = root / '.tutor/packs/v1/specs/9702/graph.json'
    graph = json.loads(path.read_text())
    for chapter in (OTHER, THIRD):
        topic = chapter.rsplit('.', 1)[0]
        graph['topics'].append({'id': topic, 'title': f'Chapter {topic}', 'level': 'AS'})
        graph['subtopics'].append({'id': chapter, 'title': f'Topic {chapter}', 'topic': topic})
        graph['kcs'].append({'id': chapter + '.1', 'subtopic': chapter, 'title': f'Idea {chapter}',
                             'level': 'AS', 'type': 'conceptual', 'prereqs': []})
    path.write_text(json.dumps(graph))
    mixed_bank(root)
    return app, root


def test_topical_picker_keeps_cross_folder_ticks_and_native_search_editing(tmp_path, monkeypatch):
    app, _ = staged_app(tmp_path, monkeypatch)
    chosen = []

    async def go():
        async with app.run_test(size=(80, 24)) as pilot:
            picker = PickerScreen('topical')
            await app.push_screen(picker, chosen.append)
            await pilot.pause()
            await pilot.press('space')  # First chapter folder.
            assert picker.ticked == {TARGET}
            await pilot.press('down', 'enter', 'space')  # Another chapter's leaf.
            assert picker.ticked == {TARGET, OTHER}
            await pilot.press('slash', *THIRD, 'ctrl+a', 'x')
            await pilot.pause()
            assert picker.query_one('#find', Input).value == 'x' + THIRD
            assert picker.ticked == {TARGET, OTHER}
            await pilot.press('home', 'ctrl+d')
            assert picker.query_one('#find', Input).value == THIRD
            await pilot.press('down', 'space')
            assert picker.ticked == {TARGET, OTHER, THIRD}
            await pilot.press('escape', 'ctrl+s')
            await pilot.pause()
            assert len(chosen) == 1 and set(chosen[0]) == {TARGET, OTHER, THIRD}
            assert app.tutor.session is None and not list(app.tutor.vault.events())
            await app.ai.close()
    asyncio.run(go())


@pytest.mark.parametrize('theme,size', [('classic', (80, 24)), ('day', (60, 20)), ('night', (100, 30))])
def test_setup_filters_count_starts_real_session_and_controls_survive_resize(tmp_path, monkeypatch, theme, size):
    from tutor_app.screens import TopicalSetupScreen
    monkeypatch.setenv('TERM', 'xterm-256color')
    monkeypatch.setenv('COLORTERM', 'truecolor')
    app, root = staged_app(tmp_path, monkeypatch)
    app.settings.theme = theme
    look.use(theme)

    async def go():
        async with app.run_test(size=size) as pilot:
            home = app.screen
            home._start('topical')
            await pilot.pause()
            picker = app.screen
            await pilot.press('ctrl+a', 'ctrl+s')
            await pilot.pause()
            setup = app.screen
            assert isinstance(setup, TopicalSetupScreen)
            assert set(setup.selected_topics) == {TARGET, OTHER, THIRD}
            types = setup.query_one('#topical-types', SelectionList)
            types.deselect_all()
            types.select('structured')
            setup.query_one('#topical-count', Input).value = '4'
            await pilot.pause()
            assert '1' in str(setup.query_one('#topical-availability', Static).content)
            start = setup.query_one('#topical-start', Button)
            assert not start.disabled and '1' in str(start.label)
            assert app.tutor.session is None
            types.focus()
            await pilot.press('end')
            await pilot.pause()
            assert setup.get_widget_at(types.content_region.x + 1, types.content_region.y + 4)[0] is types
            shots = os.environ.get('TOPICAL_SHOTS')
            if shots:
                app.save_screenshot(path=shots, filename=f'{theme}-{size[0]}x{size[1]}-setup.svg')
            await pilot.resize_terminal(60, 20)
            await pilot.pause()
            start.scroll_visible(animate=False)
            await pilot.pause()
            assert setup.region.contains_region(start.region)
            assert setup.get_widget_at(start.region.x + 1, start.region.y)[0] is start
            label = str(types.get_option('structured').prompt)
            assert cell_len(label) + 4 <= types.content_region.width
            availability = setup.query_one('#topical-availability', Static)
            assert setup.get_widget_at(availability.region.x + 1, availability.region.bottom - 1)[0] is availability
            if shots:
                app.save_screenshot(path=shots, filename=f'{theme}-60x20-resized.svg')
            start.press()
            await pilot.pause()
            assert isinstance(app.screen, SessionScreen)
            block = app.tutor.session['blocks'][0]
            assert block['question_count'] == 4 and block['question_types'] == ['structured']
            assert len(block['question_queue']) == 1
            assert app.screen.view['kind'] == 'structured'
            assert {e['type'] for e in app.tutor.vault.events()} == {'session_start', 'chapter_started'}
            assert '1' in (root / 'Now.md').read_text()
            await app.ai.close()
    try:
        asyncio.run(go())
    finally:
        look.use('classic')


def test_change_topics_and_cancel_preserve_type_count_draft_without_starting_session(tmp_path, monkeypatch):
    from tutor_app.screens import TopicalSetupScreen
    app, root = staged_app(tmp_path, monkeypatch)

    async def go():
        async with app.run_test(size=(80, 24)) as pilot:
            setup = TopicalSetupScreen([TARGET, OTHER])
            await app.push_screen(setup)
            await pilot.pause()
            setup.query_one('#topical-count', Input).value = '3'
            types = setup.query_one('#topical-types', SelectionList)
            types.deselect_all()
            types.select('mcq')
            await pilot.pause()
            before = deepcopy(app.tutor.state), list(app.tutor.vault.events())
            setup.query_one('#topical-topics', Button).press()
            await pilot.pause()
            picker = app.screen
            assert isinstance(picker, PickerScreen) and picker.ticked == {TARGET, OTHER}
            await pilot.press('ctrl+d', 'end', 'space', 'ctrl+s')
            await pilot.pause()
            assert app.screen is setup and setup.selected_topics == [THIRD]
            assert setup.query_one('#topical-count', Input).value == '3'
            assert types.selected == ['mcq']
            setup.query_one('#topical-topics', Button).press()
            await pilot.pause()
            await pilot.press('escape')
            await pilot.pause()
            assert app.screen is setup and setup.selected_topics == [THIRD]
            await pilot.press('escape')
            await pilot.pause()
            assert app.screen.__class__.__name__ == 'HomeScreen'
            assert app.tutor.session is None
            assert (app.tutor.state, list(app.tutor.vault.events())) == before
            await app.ai.close()
    asyncio.run(go())


@pytest.mark.parametrize('count,selected', [('', ['mcq']), ('0', ['mcq']), ('201', ['mcq']),
                                           ('1.5', ['mcq']), ('3', []), ('3', ['definition'])])
def test_setup_invalid_count_empty_types_and_unavailable_categories_cannot_start(
        tmp_path, monkeypatch, count, selected):
    from tutor_app.screens import TopicalSetupScreen
    app, _ = staged_app(tmp_path, monkeypatch)

    async def go():
        async with app.run_test(size=(80, 24)) as pilot:
            setup = TopicalSetupScreen([TARGET])
            await app.push_screen(setup)
            await pilot.pause()
            types = setup.query_one('#topical-types', SelectionList)
            types.deselect_all()
            for value in selected:
                types.select(value)
            setup.query_one('#topical-count', Input).value = count
            await pilot.pause()
            assert setup.query_one('#topical-start', Button).disabled
            await pilot.press('ctrl+s')
            assert app.screen is setup and app.tutor.session is None
            assert not list(app.tutor.vault.events())
            assert str(setup.query_one('#topical-availability', Static).content)
            await app.ai.close()
    asyncio.run(go())
