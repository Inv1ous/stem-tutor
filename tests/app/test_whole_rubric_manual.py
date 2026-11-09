"""No AI route can score a manual whole rubric; UI confirmation is explicit."""
import asyncio
import time

import pytest
from textual.widgets import Input

from test_tui import app_for
from test_whole_rubric import whole
from tutor_app import panels
from tutor_app.panels import LongPanel, Panel
from tutor_app.screens import SessionScreen


def open_whole(app, automatic=False):
    t = app.tutor
    t.start('review', minutes=10)
    t.session.update(mode='topical', topical_auto_mark=automatic)
    return t._present({**whole(), 'id': 'manual-graph', 'stem': 'Draw the graph.',
                       'kcs': ['9702-2.1.1'], 'difficulty': 3}, block='practice', phase=None)


@pytest.mark.parametrize('size', [(80, 24), (140, 46)])
@pytest.mark.parametrize('earned', [0, 1, 2])
def test_whole_human_panel_requires_blank_then_explicit_integer_confirm(tmp_path, monkeypatch, size, earned):
    cls = getattr(panels, 'WholeRubricPanel', None)
    assert cls is not None, 'missing human integer award panel'
    app, _ = app_for(tmp_path, monkeypatch)
    async def run():
        async with app.run_test(size=size) as pilot:
            view = open_whole(app)
            screen = SessionScreen(None); await app.push_screen(screen); await pilot.pause()
            screen.long_written({'text': 'My graph rises from the origin.'}); await pilot.pause()
            panel = screen.showing
            assert isinstance(panel, cls)
            field = panel.query_one('#whole-award', Input)
            assert field.value == ''
            panel.action_confirm(); await pilot.pause()
            assert not [e for e in app.tutor.vault.events() if e['type'] == 'answer']
            panel.shown = time.monotonic() - 1
            for invalid in ('', '-1', '3', '1.0', 'yes'):
                field.value = invalid; panel.action_confirm(); await pilot.pause()
                assert screen.showing is panel
            field.value = str(earned); panel.action_confirm(); await pilot.pause()
            events = [e for e in app.tutor.vault.events() if e['type'] == 'answer']
            assert len(events) == 1 and events[0]['grade']['score'] == earned / 2
            assert not screen.can_remark()
            await app.ai.close()
    asyncio.run(run())


@pytest.mark.parametrize('automatic', [False, True])
def test_whole_automatic_and_remark_never_call_model_or_award(tmp_path, monkeypatch, automatic):
    app, _ = app_for(tmp_path, monkeypatch)
    async def run():
        async with app.run_test() as pilot:
            open_whole(app, automatic)
            screen = SessionScreen(None); await app.push_screen(screen); await pilot.pause()
            async def forbidden(*args, **kwargs):
                pytest.fail('whole rubric attempted AI inference')
            monkeypatch.setattr(app.ai, 'one_shot', forbidden)
            monkeypatch.setattr(app, 'ai_available', lambda mode: True)
            screen.long_written({'text': 'My graph rises from the origin.'}); await pilot.pause()
            assert type(screen.showing).__name__ == 'WholeRubricPanel'
            await screen.ai_check_long.__wrapped__(screen, {'ticked': ['1']}, automatic=automatic)
            screen.last_fb = {'event': 'old-whole', 'correct': False}
            await screen.remark.__wrapped__(screen)
            assert not [e for e in app.tutor.vault.events() if e['type'] == 'answer']
            await app.ai.close()
    asyncio.run(run())


def test_paper_only_whole_requires_explicit_attempt_confirmation(tmp_path, monkeypatch):
    app, _ = app_for(tmp_path, monkeypatch)
    async def run():
        async with app.run_test() as pilot:
            view = open_whole(app)
            screen = SessionScreen(None); await app.push_screen(screen); await pilot.pause()
            screen.long_written({'text': 'done on paper'}); await pilot.pause()
            assert app.screen is not screen and not app.tutor._marking_tickets
            assert 'attempted' in app.screen.question
            await pilot.press('escape'); await pilot.pause()
            assert app.screen is screen and isinstance(screen.showing, LongPanel)
            screen.long_written({'text': 'done on paper'}); await pilot.pause()
            app.screen.dismiss('attempted'); await pilot.pause()
            assert type(screen.showing).__name__ == 'WholeRubricPanel'
            assert not [e for e in app.tutor.vault.events() if e['type'] == 'answer']
            assert app.tutor.session['presented'][str(view['n'])]['whole_paper_work'] == 'done on paper'
            await app.ai.close()
    asyncio.run(run())


def test_whole_manual_panel_cancel_resume_and_stale_callback(tmp_path, monkeypatch):
    app, _ = app_for(tmp_path, monkeypatch)
    async def run():
        async with app.run_test() as pilot:
            view = open_whole(app)
            screen = SessionScreen(None); await app.push_screen(screen); await pilot.pause()
            work = 'My graph rises from the origin.'
            screen.long_written({'text': work}); await pilot.pause()
            assert type(screen.showing).__name__ == 'WholeRubricPanel'
            old = screen.showing
            screen._apply_panel_done(Panel.Done({'whole_cancel': True}, old)); await pilot.pause()
            assert not app.tutor._marking_tickets and isinstance(screen.showing, LongPanel)
            screen._apply_panel_done(Panel.Done({'whole_award': 2}, old)); await pilot.pause()
            assert not [e for e in app.tutor.vault.events() if e['type'] == 'answer']
            assert app.tutor.session['presented'][str(view['n'])]['saved_work'] == work
            await app.ai.close()
    asyncio.run(run())


def test_whole_raster_subset_private_before_attempt_and_all_pages_render_after(tmp_path, monkeypatch):
    import json
    from PIL import Image
    from test_extraction_whole_rubric import whole_case
    from tutorlib import session, store
    from tutor_app import prompts
    ex, path, q, vault, save = whole_case(tmp_path, monkeypatch)
    Image.new('RGB', (200, 150), 'green').save(path.parent / 'official-ms-2.png')
    Image.new('RGB', (210, 160), 'yellow').save(path.parent / 'other-part-ms.png')
    q['media'] += ['official-ms-2.png', 'other-part-ms.png']
    q['mark_scheme_media'] += ['official-ms-2.png', 'other-part-ms.png']
    q['scheme'][0]['whole_rubric']['media'] += ['official-ms-2.png']
    save()
    checked = ex.check('diagram')
    assert checked['stage'] == 'reviewed', checked['problems']
    ex.register('diagram'); batch = tmp_path / 'multi'; ex.prepare_publication('diagram', batch)
    ex.publish('diagram', batch)
    app, _ = app_for(tmp_path / 'app-config', monkeypatch)
    app.tutor = session.Tutor(store.Vault(vault), one_at_a_time=True)
    app.vault = vault
    async def run():
        async with app.run_test(size=(80, 24)) as pilot:
            app.tutor.start('topical', focus=['9702-2.1'], topical_count=1, topical_types=['structured'], topical_auto_mark=True)
            preloads = []
            monkeypatch.setattr(app, 'prepare_local_ai', lambda *args, **kwargs: preloads.append(args))
            screen = SessionScreen(None); await app.push_screen(screen); await pilot.pause()
            n = screen.view['n']; p = app.tutor.session['presented'][str(n)]
            media = p['inst']['scheme'][0]['whole_rubric']['media']
            before = (vault / 'Now.md').read_text()
            assert all(m not in before for m in media) and q['scheme'][0]['point'] not in prompts.context(app.tutor)
            assert all(m not in prompts.context(app.tutor) for m in media)
            screen.long_written({'text': 'I drew my graph from the data.'}); await pilot.pause()
            now = (vault / 'Now.md').read_text()
            assert all(f'![[{m}]]' in now for m in media)
            assert now.index(media[0]) < now.index(media[1])
            assert 'other-part-ms' not in now
            assert not preloads
            logs = '\n'.join(p.read_text() for p in (vault / 'Lessons').rglob('*.md'))
            assert all(m in logs for m in media) and 'other-part-ms' not in logs
            screen.action_leave(); await pilot.pause()
            assert 'mark choices' in app.screen.question
            await pilot.press('escape'); await pilot.pause()
            await app.ai.close()
    asyncio.run(run())


def test_whole_persisted_human_event_cannot_reach_late_ai_remark(tmp_path, monkeypatch):
    app, vault = app_for(tmp_path, monkeypatch)
    async def run():
        async with app.run_test() as pilot:
            view = open_whole(app)
            n = view['n']; work = 'My graph rises from the origin.'
            out = app.tutor.whole_rubric(n, work)
            fb = app.tutor.answer(f'{n} = {work}', manual_awards={n: {'earned_marks': 1, 'ticket': out['ticket']}})['results'][0]
            from tutorlib.session import Tutor
            from tutorlib.store import Vault
            app.tutor = Tutor(Vault(vault))
            app.tutor._present({**whole(), 'id': 'later-question', 'stem': 'Later graph.', 'kcs': ['9702-2.1.1']}, block='practice', phase=None)
            screen = SessionScreen(None); await app.push_screen(screen); await pilot.pause()
            screen.view = {}; screen.last_fb = fb
            async def forbidden(*args, **kwargs): pytest.fail('persisted whole event reached AI')
            monkeypatch.setattr(app.ai, 'one_shot', forbidden)
            assert not screen.can_remark()
            await screen.remark.__wrapped__(screen)
            assert len([e for e in app.tutor.vault.events() if e['type'] == 'answer']) == 1
            await app.ai.close()
    asyncio.run(run())


@pytest.mark.parametrize('cancel', [False, True])
def test_unavailable_whole_retry_uses_existing_ungraded_save_or_cancel(tmp_path, monkeypatch, cancel):
    """SPEC-2: neither unavailable-retry button may open a private rubric."""
    import copy
    from tutorlib import deferred_notes, session
    app, vault = app_for(tmp_path, monkeypatch)
    async def run():
        async with app.run_test(size=(80, 24)) as pilot:
            first = open_whole(app)['n']
            app.tutor.answer(f'{first}?')
            n = app.tutor.retry_skipped_ungraded()['items'][0]['n']
            screen = SessionScreen(None); await app.push_screen(screen); await pilot.pause()
            assert screen.view['n'] == n and isinstance(screen.showing, LongPanel)
            assert screen.showing.ungraded is True
            p = app.tutor.session['presented'][str(n)]
            ident = session._guard_identity(p)
            guarded_inst = copy.deepcopy(p['inst'])
            events_before = list(app.tutor.vault.events())
            work = 'My graph rises from the origin.\nSecond labelled point, with units.'
            def forbidden(*args, **kwargs):
                pytest.fail('unavailable retry opened a whole rubric')
            monkeypatch.setattr(app.tutor, 'whole_rubric', forbidden)
            screen.long_written({'text': work, **({'button': 'cancel-ungraded'} if cancel else {})})
            await pilot.pause()
            assert str(n) not in app.tutor.session['presented']
            assert not app.tutor._marking_tickets and type(screen.showing).__name__ != 'WholeRubricPanel'
            events = list(app.tutor.vault.events())
            if cancel:
                assert events == events_before
                guard = app.tutor.session['skipped_answer_guards'][ident]
                assert guard['question']['inst'] == guarded_inst and guard['question']['saved_work'] == work
                stored = deferred_notes.outstanding(app.tutor.vault.tutor / 'state/deferred-notes.json')
                assert stored[ident]['question']['saved_work'] == work
            else:
                assert len(events) == len(events_before) + 1
                assert events[-1]['type'] == 'ungraded_retry' and events[-1]['response'] == work
                assert ident not in app.tutor.session['skipped_answer_guards']
            assert not any(e['type'] == 'answer' for e in events[len(events_before):])
            assert guarded_inst['scheme'][0]['point'] not in (vault / 'Now.md').read_text()
            assert all(guarded_inst['scheme'][0]['point'] not in p.read_text() for p in (vault / 'Lessons').rglob('*.md'))
            await app.ai.close()
    asyncio.run(run())
