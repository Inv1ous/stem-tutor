import asyncio

from tutor_app.panels import TextPanel, ContinuePanel, ChoosePanel, TickPanel, ChoicePanel, ValuePanel
from tutor_app.screens import SessionScreen
from test_tui import app_for


def test_own_words_escape_requires_choice_before_discarding_draft(tmp_path, monkeypatch):
    app, _ = app_for(tmp_path, monkeypatch)

    async def go():
        async with app.run_test(size=(120, 40)) as pilot:
            await pilot.pause()
            app.tutor.start('lesson', minutes=10, focus=['9702-2.1'])
            app.push_screen(SessionScreen(None))
            await pilot.pause(.1)
            screen = app.screen
            for _ in range(100):
                await pilot.pause(.02)
                if screen.act.get('activity') == 'own_words':
                    break
                panel = screen.showing
                if isinstance(panel, ChoosePanel):
                    await pilot.press('down', 'enter')
                elif isinstance(panel, TickPanel):
                    panel.query('Button').first().press()
                elif isinstance(panel, ContinuePanel):
                    panel.query('Button').first().press()
                elif isinstance(panel, ChoicePanel):
                    await pilot.press('b', '3')
                elif isinstance(panel, ValuePanel):
                    await pilot.press(*'1', 'enter')
                    await pilot.press('2')
            assert screen.act.get('activity') == 'own_words'
            assert isinstance(screen.showing, TextPanel)
            composer = screen.showing.query_one('#text')
            composer.focus()
            await pilot.press(*'draft explanation')
            await pilot.press('escape')
            await pilot.pause()
            assert app.screen.__class__.__name__ == 'ConfirmScreen'
            assert screen.act.get('activity') == 'own_words'
            await pilot.press('down', 'enter')  # Keep writing
            await pilot.pause()
            assert app.screen is screen
            assert screen.act.get('activity') == 'own_words'
            assert screen.showing.query_one('#text').text == 'draft explanation'
            await pilot.press('escape')
            await pilot.pause()
            assert app.screen.__class__.__name__ == 'ConfirmScreen'
            await pilot.press('enter')  # Discard and skip
            await pilot.pause()
            assert app.screen is screen
            assert screen.act.get('activity') != 'own_words'

    asyncio.run(go())
