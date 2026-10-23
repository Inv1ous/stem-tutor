"""The last P1 findings of the bug watch, fixed by hand (B-098, B-104, B-107, B-135)."""

import asyncio
from copy import deepcopy
from types import SimpleNamespace

import pytest
from textual.app import App

from test_tui import app_for
from tutor_app import ai
from tutor_app import panels
from tutor_app.panels import ChoicePanel, TickPanel
from tutor_app.screens import SessionScreen


@pytest.mark.parametrize("long", [False, True])
@pytest.mark.parametrize("rows", ["duplicate", "missing", "extra", "reordered", "not_boolean", "non_object", "valid"])
def test_an_examiner_reply_that_does_not_line_up_with_the_mark_points_never_awards_a_mark(tmp_path, monkeypatch, long, rows):
    """B-098: malformed examiner rows must leave marks for the learner to award."""
    app, _ = app_for(tmp_path, monkeypatch)
    points = ["distance", "direction"]
    requested = [" " + p for p in points] if long else points
    verdicts = [{"point": p, "met": i == 0} for i, p in enumerate(requested)]
    verdicts = {"duplicate": [verdicts[0], verdicts[0]], "missing": verdicts[:1],
                "extra": verdicts + verdicts[:1], "reordered": verdicts[::-1],
                "not_boolean": [{"point": p, "met": "false"} for p in requested],
                "non_object": [requested[0], verdicts[1]], "valid": verdicts}[rows]

    async def examiner(*args, **kwargs):
        return {"points": verdicts, "feedback": "Checked."}, ai.Result()

    async def go():
        async with app.run_test(size=(100, 30)) as pilot:
            await pilot.pause()
            t = app.tutor
            t.start("review", minutes=10)
            item = {"id": "j07-short", "kcs": ["9702-2.1.1"], "kind": "short", "difficulty": 3,
                    "marks": 2, "stem": "Define displacement.",
                    "rubric": [{"point": p, "keywords": [[p]]} for p in points]}
            view = t._present(item, block="practice", phase=None)
            scr = SessionScreen(None)
            await app.push_screen(scr)
            await pilot.pause()
            monkeypatch.setattr(app.ai, "one_shot", examiner)
            if long:
                scr.scheme = [{"i": i, "mark": "", "point": p} for i, p in enumerate(points)]
                scr.long_text = "distance"
                await scr.ai_check_long({"ticked": []}).wait()
                await pilot.pause()
                selected = scr.query_one(TickPanel).query_one("#ticks").selected
                assert set(selected) == ({"0"} if rows == "valid" else set())
                await scr.ai_check_long({"ticked": ["1"]}).wait()
                await pilot.pause()
                selected = scr.query_one(TickPanel).query_one("#ticks").selected
                assert set(selected) == ({"0"} if rows == "valid" else {"1"})  # the examiner's ticks (J06), or yours kept
            else:
                await scr.judge_short(view, {"entry": f"{view['n']} = distance", "your": "distance"},
                                      {"rubric": points}).wait()
                await pilot.pause()
                answers = [e for e in t.vault.events() if e["type"] == "answer"]
                if rows == "valid":
                    assert answers[-1]["grade"]["score"] == 0.5
                else:
                    assert not answers
                    assert isinstance(scr.query_one("#panel > *"), TickPanel)
    asyncio.run(go())


def test_starting_another_lesson_offers_to_resume_one_not_yet_answered(tmp_path, monkeypatch):
    """B-104: a lesson at its plan can be resumed before any answer is graded."""
    app, _ = app_for(tmp_path, monkeypatch)

    async def go():
        async with app.run_test(size=(100, 30)) as pilot:
            await pilot.pause()
            await pilot.press("down", "enter")
            await pilot.pause()
            await pilot.press("enter")
            await pilot.pause()
            await pilot.press("enter")  # start from scratch
            await pilot.pause()
            old = deepcopy(app.tutor.session)
            assert old["answered"] == 0
            assert old["goal"] == "scratch" and old["awaiting"]["activity"] == "plan"
            await pilot.press("ctrl+q")
            await pilot.pause()
            menu = app.screen.query_one("#menu")
            menu.highlighted = [o.id for o in menu.options].index("learn")
            await pilot.press("enter")
            await pilot.pause()
            assert app.screen.__class__.__name__ == "ConfirmScreen"
            await pilot.press("enter")  # resume
            await pilot.pause()
            resumed = {k: v for k, v in app.tutor.session.items() if k != "thread"}  # Now adds "Welcome back"
            assert resumed == {k: v for k, v in old.items() if k != "thread"}
    asyncio.run(go())


def test_read_aloud_reads_every_choice_of_a_multiple_choice_question_but_not_its_key(tmp_path, monkeypatch):
    """B-107: the spoken question includes the same choices the learner can select."""
    app, _ = app_for(tmp_path, monkeypatch)

    async def go():
        async with app.run_test(size=(100, 30)) as pilot:
            await pilot.pause()
            scr = SessionScreen({"mode": "test", "focus": ["9702-2.1"], "minutes": 20})
            await app.push_screen(scr)
            await pilot.pause()
            spoken = []
            monkeypatch.setattr(app, "speaker", SimpleNamespace(
                active=False, usable=True, stop=lambda: None, problem=lambda: None,
                say=lambda parts: spoken.append(parts), close=app.speaker.close))
            view = {"n": 1, "kind": "mcq", "stem": "Which speed?", "options": {
                "A": "$2$ m/s", "B": "$4$ m/s", "C": "$6$ m/s", "D": "$8$ m/s"},
                "answer": "SECRET KEY"}
            scr.ask_question(view)
            await pilot.pause()
            assert scr.readable_parts == [view["stem"]] + [f"Option {k}: {v}" for k, v in view["options"].items()]
            assert "SECRET KEY" not in scr.readable
            assert not spoken


def test_a_held_enter_after_next_never_answers_the_new_question(monkeypatch):
    """B-135: Next, then the same ⏎ repeating, chose option A and confidence 1 for a question not yet read."""
    monkeypatch.setattr(panels.Settling, "SETTLE", 0.4)
    done = []

    class One(App):
        def compose(self):
            yield ChoicePanel(2, {"A": "one", "B": "two", "C": "three", "D": "four"})

        def on_panel_done(self, event):
            done.append(event.data)

    async def go():
        app = One()
        async with app.run_test(size=(80, 24)) as pilot:
            await pilot.press("enter", "enter")
            await pilot.pause()
            assert not done and app.query_one(ChoicePanel).choice is None
            await pilot.pause(0.5)
            await pilot.press("enter")  # a deliberate ⏎ once the options have been seen
            await pilot.pause()
            assert app.query_one(ChoicePanel).choice == "A"
            await pilot.press("enter")  # the same press repeating reaches the confidence list
            await pilot.pause()
            assert not done
            await pilot.press("3")  # a number key is always meant
            await pilot.pause()
            assert done and done[0]["entry"] == "2A3"
    asyncio.run(go())
