"""A finished empty chat reply must have a visible completion state."""
import asyncio

import pytest

from test_tui import app_for
from tutor_app import ai as ai_mod


@pytest.mark.parametrize('size', [(80, 24), (140, 46)])
@pytest.mark.parametrize('body', ['', ' \n\t '])
def test_empty_chat_reply_finishes_visibly_and_accepts_retry(tmp_path, monkeypatch, size, body):
    app, vault = app_for(tmp_path, monkeypatch)
    app.settings.ai = False  # every request below is the in-process fake
    monkeypatch.setattr(app, 'ai_available', lambda mode='ask': True)
    started, release = asyncio.Event(), asyncio.Event()
    calls = 0

    async def fake_stream(prompt, **kwargs):
        nonlocal calls
        calls += 1
        if calls == 1:
            started.set()
            await release.wait()
            app.ai.last = ai_mod.Result(text=body)
            if body:
                yield body
        else:
            app.ai.last = ai_mod.Result(text='A real reply.')
            yield 'A real reply.'

    async def run():
        async with app.run_test(size=size) as pilot:
            await pilot.pause()
            monkeypatch.setattr(app.ai, 'stream', fake_stream)
            menu = app.screen.query_one('#menu')
            menu.reveal('chat')
            await pilot.press('enter')
            await pilot.pause()
            screen = app.screen
            spoken, delivered = [], []
            monkeypatch.setattr(screen, 'readable_now', lambda *args, **kwargs: spoken.append(args))
            original_help = app.tutor.ai_help

            def help_spy(*args, **kwargs):
                if kwargs.get('given', True):
                    delivered.append(True)
                return original_help(*args, **kwargs)

            monkeypatch.setattr(app.tutor, 'ai_help', help_spy)
            await pilot.press(*'Why?', 'enter')
            await asyncio.wait_for(started.wait(), 3)
            pending = screen.query('.entry').last()
            assert pending.content.card[:2] == ('ai', 'Tutor (AI)')
            release.set()
            await app.workers.wait_for_complete()
            await pilot.pause()

            status = screen.query('.entry').last()
            assert status.content.card[1] == 'No AI reply'
            assert 'Try asking again' in status.content.card[2]
            assert status.region.bottom <= screen.query_one('#panel').region.y
            assert 'No AI reply' in (vault / 'Now.md').read_text()
            assert not spoken and not delivered
            assert screen.query_one('#text').has_focus
            await pilot.press(*'Retry', 'enter')
            await app.workers.wait_for_complete()
            await pilot.pause()
            assert screen.query('.entry').last().content.card == ('ai', 'Tutor (AI)', 'A real reply.')
            assert len(delivered) == 1 and spoken == [('A real reply.',)]
            await pilot.press('escape')
            await pilot.pause()
            assert app.screen.__class__.__name__ == 'HomeScreen'

    asyncio.run(run())
