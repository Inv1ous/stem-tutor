"""Quality-of-life fixes from the bug watch's QOL list (bugwatch/codex/QOL.md), app side."""
import asyncio
import threading
import time

from tutor_app import ai, cards, config, mac
from tutor_app.screens import searchable
from test_tui import FAKE, app_for


def test_warming_starts_the_conversation_that_ask_will_use(tmp_path):
    """Q-002: the app chose Ask's model after the client was made, and warm-up still started the old one."""
    async def go():
        a = ai.Claude(tmp_path, model="haiku", binary=FAKE)
        a.model, a.think = "sonnet", True  # what Settings chose for Ask
        await a.warm()
        assert list(a.procs) == [("sonnet", True)]
        await a.close()
    asyncio.run(go())


def test_nothing_is_started_ahead_while_ai_is_switched_off(tmp_path):
    """Q-015: chat and every new idea started a Claude process even with AI off."""
    async def go():
        a = ai.Claude(tmp_path, binary=FAKE)
        a.wanted = lambda: False
        await a.warm()
        await a.reset()
        await asyncio.sleep(0.05)
        assert a.procs == {}
        await a.close()
    asyncio.run(go())


def test_a_streaming_reply_is_redrawn_at_most_a_few_times_a_second():
    """Q-004: every chunk re-parsed the whole reply."""
    drawn = []

    class W:
        def update(self, x):
            drawn.append(x)
    live = cards.Live(W(), every=0.2)
    hits = [live.update("x" * n) for n in range(200)]
    assert hits[0] and sum(hits) == 1 == len(drawn)
    time.sleep(0.21)
    assert live.update("more") and len(drawn) == 2


def test_topic_search_matches_plain_keyboard_spellings():
    """Q-018: "Bronsted" and "Hess's" (straight apostrophe) found nothing."""
    assert "bronsted" in searchable("Brønsted–Lowry acids") and "hess's" in searchable("Hess’s law")
    assert searchable("ΔH") == "δh" and "newton's" in searchable("Newton’s laws")
    assert searchable("Brønsted") == searchable("Bronsted")


def test_feedback_says_how_many_marks_a_part_right_answer_earned():
    """Q-017: 3 of 4 scheme points said only "Not quite"."""
    base = {"n": 1, "correct": False, "answer": "x", "score": 0.75, "marks": 4}
    assert "3 of 4 marks" in cards.feedback(base, "my working").title
    assert "Not quite" in cards.feedback({**base, "score": 0.0}, "x").title
    assert "Not quite" in cards.feedback({**base, "marks": 1, "score": 0.5}, "x").title  # one-mark: nothing to split


def test_a_scanned_question_with_broken_text_points_to_the_picture():
    """Q-009: broken text was shown as the question while a readable scan existed."""
    view = {"n": 1, "kind": "mcq", "stem": "Which graph \x01 shows it?", "image": "Assets/mcq/q.png",
            "garbled": {"stem": True, "options": ["A"]}}
    from rich.console import Console
    console = Console(width=100, record=True)
    console.print(cards.question(view))
    out = console.export_text()
    assert "Which graph □ shows it?" in out and "the picture in Now is exact" in out and "has a figure" not in out


def test_home_appears_before_the_ipad_inbox_is_copied(tmp_path, monkeypatch):
    """Q-005: a big or still-downloading iPad file held the first screen back while it copied."""
    app, v = app_for(tmp_path, monkeypatch)
    release, said = threading.Event(), []
    monkeypatch.setattr(mac, "import_ipad_inbox", lambda vault, inbox: release.wait(5) and ["big.pdf"])

    async def go():
        async with app.run_test(size=(100, 30)) as pilot:
            await pilot.pause()
            assert app.screen.__class__.__name__ == "HomeScreen"  # while the copy is still going
            monkeypatch.setattr(app, "notify", lambda msg, **kw: said.append(msg))
            release.set()
            await app.workers.wait_for_complete()
            await pilot.pause()
            await app.ai.close()
    asyncio.run(go())
    assert any("big.pdf" in m for m in said)


def test_the_side_box_says_how_to_reach_what_does_not_fit(tmp_path, monkeypatch):
    """Q-008: Your topics sat below the side box's edge with no sign it was there."""
    from textual.containers import VerticalScroll
    from textual.widgets import Static
    app, v = app_for(tmp_path, monkeypatch)

    async def go():
        async with app.run_test(size=(140, 46)) as pilot:
            await pilot.pause()
            box = app.screen.query_one("#stats", VerticalScroll)
            app.screen._scroll_cue()
            assert box.border_subtitle == ""  # all of it fits
            app.screen.query_one("#stats-text", Static).update("\n".join(f"chapter {i}" for i in range(120)))
            await pilot.pause()
            app.screen._scroll_cue()
            assert "PgDn" in box.border_subtitle
            await app.ai.close()
    asyncio.run(go())


def test_switching_ai_on_in_settings_starts_the_conversation_ahead(tmp_path, monkeypatch):
    from textual.widgets import Switch
    app, v = app_for(tmp_path, monkeypatch)
    warmed = []

    async def go():
        async with app.run_test(size=(100, 30)) as pilot:
            await pilot.pause()
            app.settings.ai = False
            monkeypatch.setattr(app.ai, "warm", lambda: warmed.append(1) or asyncio.sleep(0))
            await pilot.press("f2")
            await pilot.pause()
            app.screen.query_one("#ai", Switch).value = True
            app.screen.query_one("#save").press()
            await pilot.pause()
            await app.workers.wait_for_complete()
            await app.ai.close()
    asyncio.run(go())
    assert warmed and config.Settings.load(v).ai is True
