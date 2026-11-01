import random
import json

import pytest

from fixtures import make_vault
from tutorlib import deferred_notes, session, store


@pytest.fixture
def tutor(tmp_path):
    t=session.Tutor(store.Vault(make_vault(tmp_path)),rng=random.Random(0))
    t.session={'id':'marking-session','presented':{'1':{'item':'q1','unassisted':False,
        'inst':{'kind':'short','stem':'x?','answer':'x'}}}}
    t._save()
    return t


def test_begin_marking_persists_attempt_and_pending_state(tutor):
    ticket=tutor.begin_marking(1,'my working')
    question=tutor.session['presented']['1']
    assert question['saved_work']=='my working'
    assert question['pending_saved_mark'] is True
    saved=json.loads(tutor.session_path.read_text())
    assert saved['presented']['1']['saved_work']=='my working'
    assert tutor.marking_status(ticket)=='ok'


def test_marking_status_rejects_replaced_session_or_question(tutor):
    ticket=tutor.begin_marking(1,'attempt')
    tutor.session=dict(tutor.session)
    assert tutor.marking_status(ticket)=='stale'
    ticket=tutor.begin_marking(1,'attempt 2')
    tutor.session['presented']['1']=dict(tutor.session['presented']['1'])
    assert tutor.marking_status(ticket)=='stale'


def test_marking_status_detects_changed_deferred_guards(tutor):
    ticket=tutor.begin_marking(1,'attempt')
    path=tutor.vault.tutor/'state'/'deferred-notes.json'
    deferred_notes.hold(path,'deferred-q',{'question':{'inst':{'stem':'protected'}}})
    assert tutor.marking_status(ticket)=='stored_changed'


def test_new_session_retry_guard_is_protected_during_marking(tutor):
    ticket=tutor.begin_marking(1,'attempt')
    tutor.session['skipped_answer_guards']={'saved-q':{'question':{'inst':{'stem':'secret'}}}}
    assert tutor.marking_status(ticket)=='retry_protected'


def test_removing_existing_guard_is_reported_as_guard_change(tutor):
    tutor.session['skipped_answer_guards']={'saved-q':{'question':{'inst':{'stem':'secret'}}}}
    ticket=tutor.begin_marking(1,'attempt')
    tutor.session['skipped_answer_guards'].clear()
    assert tutor.marking_status(ticket)=='guards_changed'


def test_marking_ticket_is_opaque_single_use(tutor):
    ticket=tutor.begin_marking(1,'attempt')
    assert isinstance(ticket,str) and ticket not in str(tutor.session)
    assert tutor.marking_status(ticket)=='ok'
    assert tutor.marking_status(ticket)=='stale'


def test_cancel_marking_is_idempotent_and_releases_identity_refs(tutor):
    ticket=tutor.begin_marking(1,'attempt')
    assert ticket in tutor._marking_tickets
    assert tutor.cancel_marking(ticket) is None
    assert ticket not in tutor._marking_tickets
    assert tutor.cancel_marking(ticket) is None
    assert tutor.marking_status(ticket)=='stale'


def test_judge_short_ai_exception_cleans_up_marking_ticket(tmp_path,monkeypatch):
    import asyncio
    from test_tui import app_for
    from tutor_app.screens import SessionScreen
    from tutor_app import ai

    app,_=app_for(tmp_path,monkeypatch)
    async def run():
        async with app.run_test() as pilot:
            await pilot.pause()
            t=app.tutor
            t.start('review',minutes=10)
            base={'kcs':['9702-2.1.1'],'kind':'short','difficulty':3,'marks':1,
                  'rubric':[{'point':'A point','keywords':[['point']]}]}
            view=t._present({**base,'id':'marked','stem':'Explain.','review_answer':'A point.'},
                            block='practice',phase='form_check')
            screen=SessionScreen(None); await app.push_screen(screen); await pilot.pause()
            monkeypatch.setattr(app,'ai_available',lambda mode:True)
            app.settings.ai_mark_model='sonnet'
            async def fail(*args,**kwargs): raise RuntimeError('judge failed')
            monkeypatch.setattr(app.ai,'one_shot',fail)
            tickets=[]; original=t.begin_marking
            def capture(*args,**kwargs):
                ticket=original(*args,**kwargs); tickets.append(ticket); return ticket
            monkeypatch.setattr(t,'begin_marking',capture)
            with pytest.raises(Exception,match='judge failed'):
                await screen.judge_short.__wrapped__(screen,view,{'your':'working','entry':f"{view['n']} = working"},
                                                     {'rubric':['A point']})
            assert tickets and tickets[0] not in t._marking_tickets
            assert t.session['presented'][str(view['n'])]['saved_work']=='working'
            await app.ai.close()
    asyncio.run(run())


def test_judge_short_cancellation_cleans_up_marking_ticket(tmp_path,monkeypatch):
    import asyncio
    from test_tui import app_for
    from tutor_app.screens import SessionScreen

    app,_=app_for(tmp_path,monkeypatch)
    async def run():
        started=asyncio.Event()
        async with app.run_test() as pilot:
            await pilot.pause()
            t=app.tutor
            t.start('review',minutes=10)
            base={'kcs':['9702-2.1.1'],'kind':'short','difficulty':3,'marks':1,
                  'rubric':[{'point':'A point','keywords':[['point']]}]}
            view=t._present({**base,'id':'cancelled','stem':'Explain.','review_answer':'A point.'},
                            block='practice',phase='form_check')
            screen=SessionScreen(None); await app.push_screen(screen); await pilot.pause()
            monkeypatch.setattr(app,'ai_available',lambda mode:True)
            app.settings.ai_mark_model='sonnet'
            async def wait_forever(*args,**kwargs):
                started.set(); await asyncio.Event().wait()
            monkeypatch.setattr(app.ai,'one_shot',wait_forever)
            tickets=[]; original=t.begin_marking
            def capture(*args,**kwargs):
                ticket=original(*args,**kwargs); tickets.append(ticket); return ticket
            monkeypatch.setattr(t,'begin_marking',capture)
            worker=asyncio.create_task(screen.judge_short.__wrapped__(
                screen,view,{'your':'working','entry':f"{view['n']} = working"},{'rubric':['A point']}))
            await started.wait()
            worker.cancel()
            try: await worker
            except BaseException: pass
            assert tickets and tickets[0] not in t._marking_tickets
            assert t.session['presented'][str(view['n'])]['saved_work']=='working'
            await app.ai.close()
    asyncio.run(run())
