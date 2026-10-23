"""Asked by the learner: with answer-only on (F3), Obsidian is where a session is read, and it left things out that the
terminal showed: their own answer, the AI examiner's verdict, notes. Now and the lesson log must say what the terminal
says, card for card, in normal and answer-only view alike."""
import asyncio

from test_challenge_screen import fake_generator, open_challenge, set_up, start
from test_tui import _open_long_and_submit, app_for, drive_lesson
from tutor_app import ai as ai_mod
from tutor_app import cards
from tutor_app.screens import SessionScreen
from tutorlib import views


def _record_cards(monkeypatch, vault):
    """Every card the session screen prints, as Obsidian should have it; after each print, Now must hold every card
    printed since the terminal last cleared its log."""
    said, since_fold, missing = [], [], []
    feedback, question = cards.feedback, cards.question

    def fb_card(fb, your):
        panel = feedback(fb, your)
        panel.words = views.card_block(*views.feedback_card(fb, your))
        return panel

    def q_card(view):
        panel = question(view)
        panel.words = views.question_block(view)
        return panel
    monkeypatch.setattr(cards, "feedback", fb_card)
    monkeypatch.setattr(cards, "question", q_card)
    real_say, real_fold = SessionScreen.say, SessionScreen.fold

    def say(self, renderable, mirror="both"):
        w = real_say(self, renderable, mirror)
        words = getattr(renderable, "words", None)
        if words is None and (c := getattr(renderable, "card", None)) and c[2] not in ("…", "") \
                and not (c[0] == "plan" and not c[2]):  # a reply still coming in; a choice whose options are below
            words = views.card_block(*c)
        if words:
            said.append(words)
            since_fold.append(words)
            now = (vault / "Now.md").read_text()
            missing.extend(w for w in since_fold if w not in now)
        return w

    def fold(self):
        since_fold.clear()
        real_fold(self)
    monkeypatch.setattr(SessionScreen, "say", say)
    monkeypatch.setattr(SessionScreen, "fold", fold)
    return said, missing


def test_every_card_of_a_whole_lesson_is_in_now_and_the_lesson_log_word_for_word(tmp_path, monkeypatch):
    app, vault = app_for(tmp_path, monkeypatch)
    app.settings.answer_only = True
    said, missing = _record_cards(monkeypatch, vault)

    async def go():
        async with app.run_test(size=(120, 40)) as pilot:
            await pilot.pause()
            await pilot.press("down", "enter")  # Learn a topic
            await pilot.pause()
            await pilot.press("enter")  # the only subtopic
            await pilot.pause()
            log = vault / app.tutor.session["log"]
            seen = await drive_lesson(pilot, app)
            assert "summary" in seen
            text = log.read_text()
            assert said and [w for w in said if w not in text] == []
            assert missing == []
            assert "**Your answer:** B (fairly sure)" in text  # what you chose, as the terminal showed it
            await app.ai.close()
    asyncio.run(go())


def test_the_ai_examiners_verdict_and_your_working_are_in_obsidian(tmp_path, monkeypatch):
    app, vault = app_for(tmp_path, monkeypatch)
    app.settings.answer_only = True

    async def go():
        async with app.run_test(size=(100, 30)) as pilot:
            await pilot.pause()
            await _open_long_and_submit(pilot, app, "v equals u plus a t")
            scr = app.screen

            async def examiner(*args, **kwargs):
                return {"points": [{"point": f"{p.get('mark', '')} {p.get('point', '')}", "met": i == 0,
                                    "why": f"reason {i}"} for i, p in enumerate(scr.scheme)],
                        "feedback": "A clear start; finish the last step."}, ai_mod.Result()
            monkeypatch.setattr(app.ai, "one_shot", examiner)
            await scr.ai_check_long({"ticked": []}).wait()
            await pilot.pause()
            for text in ((vault / "Now.md").read_text(), (vault / app.tutor.session["log"]).read_text()):
                assert "v equals u plus a t" in text and "Your working for Q" in text
                assert "AI examiner" in text and "A clear start; finish the last step." in text and "reason 0" in text
            await app.ai.close()
    asyncio.run(go())


def test_an_ai_marked_short_answer_keeps_your_words_and_the_verdict_in_obsidian(tmp_path, monkeypatch):
    app, vault = app_for(tmp_path, monkeypatch)
    points = ["distance", "direction"]

    async def examiner(*args, **kwargs):
        return {"points": [{"point": p, "met": i == 0} for i, p in enumerate(points)],
                "feedback": "Only the distance is there."}, ai_mod.Result()

    async def go():
        async with app.run_test(size=(100, 30)) as pilot:
            await pilot.pause()
            t = app.tutor
            t.start("review", minutes=10)
            item = {"id": "obs-short", "kcs": ["9702-2.1.1"], "kind": "short", "difficulty": 3, "marks": 2,
                    "stem": "Define displacement.", "rubric": [{"point": p, "keywords": [[p]]} for p in points]}
            view = t._present(item, block="practice", phase=None)
            scr = SessionScreen(None)
            await app.push_screen(scr)
            await pilot.pause()
            monkeypatch.setattr(app.ai, "one_shot", examiner)
            await scr.judge_short(view, {"entry": f"{view['n']} = the distance moved", "your": "the distance moved"},
                                  {"rubric": points}).wait()
            await pilot.pause()
            for text in ((vault / "Now.md").read_text(), (vault / t.session["log"]).read_text()):
                assert "**Your answer:** the distance moved" in text
                assert "Only the distance is there." in text and "✓ distance" in text and "✗ direction" in text
            await app.ai.close()
    asyncio.run(go())


def test_a_challenge_question_and_its_verdict_are_in_obsidian(tmp_path, monkeypatch):
    """A Challenge wrote nothing to Obsidian: with answer-only on, its question could not be read anywhere."""
    app, vault = app_for(tmp_path, monkeypatch)
    app.settings.answer_only = True
    fake_generator(monkeypatch)

    async def go():
        async with app.run_test(size=(80, 24)) as pilot:
            await pilot.pause()
            scr = await open_challenge(pilot, app)
            await set_up(pilot, scr)
            await start(pilot, scr)
            now = (vault / "Now.md").read_text()
            assert "How far does it travel" in now and "**B.** 9.0 m" in now and "Q1 of 3" in now
            await pilot.press("a")
            await pilot.pause()
            now, log = (vault / "Now.md").read_text(), (vault / views.lesson_rel(vault, scr.set.log)).read_text()
            for text in (now, log):
                assert "Q1 — Not quite ✗" in text and "**Your answer:** A" in text and "**Answer:** B: 9.0 m" in text
            assert "How far does it travel" in log
            await app.ai.close()
    asyncio.run(go())
