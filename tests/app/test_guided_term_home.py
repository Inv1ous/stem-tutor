import asyncio
from test_tui import app_for
from tutor_app.screens import SessionScreen
from tutorlib import lesson, model


def test_home_offers_review_when_only_terms_are_due(tmp_path, monkeypatch):
    app, _ = app_for(tmp_path, monkeypatch)
    kc = "9702-2.1.1"
    term = {"term": "Velocity", "meaning": "Speed in a stated direction", "notation": "v", "spoken": "velocity"}
    monkeypatch.setattr(lesson, "teach_card", lambda tutor, kc: {"terms": [term]})
    async def run():
        async with app.run_test(size=(120, 40)) as pilot:
            await pilot.pause()
            monkeypatch.setattr(app.tutor.packs, "pack_for_kc", lambda kc: {"teach": {kc: {"terms": [term]}}})
            app.tutor.log({"type": "term_introduced", "term_id": lesson.term_id(kc, "Velocity"), "kc": kc})
            assert not model.due_kcs(app.tutor.state, app.tutor.now())
            home = app.screen
            home.refresh_home()
            await pilot.pause()
            assert any(key == "review" and "(1)" in label for key, label in home._menu_items)
            home._start("review")
            await pilot.pause()
            assert isinstance(app.screen, SessionScreen)
            assert app.screen.view["stem"] == "What does Velocity (v) mean?"
            await app.ai.close()
    asyncio.run(run())
