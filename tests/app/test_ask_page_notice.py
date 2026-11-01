"""Ask states its existing first-image limit for the question actually in focus."""
import asyncio
import copy

import pytest
from textual.widgets import Static

from test_ai_context import _install_image
from test_tui import app_for
from tutor_app import prompts
from tutor_app.panels import Composer
from tutor_app.screens import AskScreen, SessionScreen
from tutorlib.session import _display_answer

PAGES = ['Library/Courses/9702/Questions/Media/ask-first.png',
         'Library/Courses/9702/Questions/Media/ask-second.png']
NOTICE = 'Ask receives the question text and first image only. Read all pages in Obsidian.'


def events(vault):
    return {p.name: p.read_bytes() for p in (vault / '.tutor/events').glob('*.jsonl')}


@pytest.mark.parametrize('size', [(80, 24), (140, 46)])
@pytest.mark.parametrize('context', ['multi', 'single_duplicate', 'no_image', 'recent_multi',
                                   'recent_images_only', 'open_after_multi'])
def test_ask_notice_tracks_actual_focus_and_preserves_composer(tmp_path, monkeypatch, size, context):
    app, vault = app_for(tmp_path, monkeypatch)
    app.settings.ai = False
    sent = []

    async def go():
        async with app.run_test(size=size) as pilot:
            await pilot.pause()
            screen = SessionScreen({'mode': 'test', 'minutes': 40, 'focus': ['9702-2.1.1']})
            app.push_screen(screen)
            await pilot.pause()
            for page, colour in zip(PAGES, ['red', 'blue']):
                _install_image(vault, page, colour)
            number, row = next(iter(app.tutor.session['presented'].items()))
            inst = row['inst']
            if context != 'no_image':
                if context != 'recent_images_only':
                    inst['image'] = PAGES[0]
                inst['images'] = PAGES if context != 'single_duplicate' else [PAGES[0]]
            screen.ask_question(app.tutor._view(int(number)))
            if context in ('recent_multi', 'recent_images_only', 'open_after_multi'):
                entry = (f"{number}{inst['answer']}4" if inst['kind'] == 'mcq' else
                         f"{number} = {_display_answer(inst)} ~4")
                screen.submit({'entry': entry, 'your': 'My answer'})
                assert not app.tutor.session['presented']
                assert 'images' not in app.tutor.session['recent'][-1]
                if context == 'recent_images_only':
                    assert prompts.focus_image(app.tutor) == vault / PAGES[0]
                if context == 'open_after_multi':
                    screen.advance()
                    await pilot.pause()
                    current = next(iter(app.tutor.session['presented'].values()))['inst']
                    current.update(image=PAGES[0], images=[PAGES[0]])
            expected = context in ('multi', 'recent_multi', 'recent_images_only')
            before_session = copy.deepcopy(app.tutor.session)
            before_events = events(vault)
            monkeypatch.setattr(screen, 'stream', lambda prompt, **kwargs: sent.append((prompt, kwargs)))
            screen.action_ask()
            await pilot.pause()
            assert isinstance(app.screen, AskScreen)
            text = ' '.join(str(w.render()) for w in app.screen.query(Static))
            assert (NOTICE in text) == expected
            assert not sent
            composer = app.screen.query_one('#q', Composer)
            assert composer.text == '' and app.focused is composer
            assert app.screen.query_one('#ask').region.contains_region(composer.region)
            assert app.screen.region.contains_region(app.screen.query_one('#ask').region)
            await pilot.press(*'why', 'ctrl+j', *'this page')
            assert composer.text == 'why\nthis page' and app.focused is composer
            await pilot.press('escape')
            await pilot.pause()
            assert app.screen is screen and not sent
            assert app.tutor.session == before_session and events(vault) == before_events
            screen.action_ask()
            await pilot.pause()
            app.screen.query_one('#q', Composer).insert('Explain this step')
            await pilot.press('enter')
            await pilot.pause()
            assert app.screen is screen and len(sent) == 1
            assert 'Explain this step' in sent[0][0]
            assert events(vault) == before_events
            await app.ai.close()
    asyncio.run(go())


@pytest.mark.parametrize('record,history,want,reads', [
    ({'image': PAGES[0], 'images': PAGES, 'event': 'focused'}, [], 2, 0),
    ({'image': PAGES[0]}, [{'id': 'other', 'question': {'images': PAGES}}], 1, 0),
    ({'image': PAGES[0], 'event': 'missing'}, [{'id': 'other', 'question': {'images': PAGES}}], 1, 1),
    ({'image': PAGES[0], 'event': 'focused'}, [
        {'id': 'focused', 'question': {'images': PAGES}},
        {'id': 'newer', 'question': {'images': PAGES + ['third.png']}},
    ], 2, 1),
    ({'image': PAGES[0], 'event': 'focused'}, [{'id': 'focused'}], 1, 1),
    ({'image': PAGES[0], 'event': 'focused'}, [{'id': 'focused', 'question': 'legacy text'}], 1, 1),
    ({'image': None, 'event': 'focused'}, [{'id': 'focused', 'question': {'images': PAGES}}], 2, 1),
])
def test_page_notice_count_uses_only_declared_focus_or_its_exact_event(record, history, want, reads):
    from types import SimpleNamespace
    calls = []

    def events():
        calls.append('read')
        return iter(history)
    tutor = SimpleNamespace(session={'recent': [record]}, vault=SimpleNamespace(events=events))
    before = copy.deepcopy(record)
    assert prompts.focus_page_count(tutor) == want
    assert len(calls) == reads and record == before
