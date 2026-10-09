"""The Challenge screen: set up in words or a list, write a set (a fake generator here), answer it one by one."""
import asyncio

import pytest

from test_tui import app_for, shot
from tutor_app import challenge_screen as cs
from tutor_app import look
from tutor_app.panels import ChoicePanel, Composer, ContinuePanel, ValuePanel
from tutorlib import challenge as ch
from tutorlib import store

STEM = ("A car accelerates uniformly from rest at 2.0 m s^-2 for 3.0 s. How far does it travel in that time? "
        "Give your answer in m to 2 significant figures.")


def mcq(n, level=5):
    return {"n": n, "level": level, "kind": "mcq", "concepts": ["9702-2.1.4"], "solution": "s = 1/2 a t^2 = 9.0 m",
            "item": {"id": f"ch-{n}-aaaaaa", "kind": "mcq", "kcs": ["9702-2.1.4"], "stem": STEM,
                     "options": {"A": "6.0 m", "B": "9.0 m", "C": "18 m", "D": "3.0 m"}, "answer": "B",
                     "explanation": "s = 1/2 a t^2 = 9.0 m"}}


def typed(n, level=6):
    return {"n": n, "level": level, "kind": "typed", "concepts": ["9702-2.1.4"], "solution": "s = 1/2 a t^2 = 9.0 m",
            "item": {"id": f"ch-{n}-bbbbbb", "kind": "numeric", "kcs": ["9702-2.1.4"], "stem": STEM,
                     "answer": {"value": 9.0, "unit": "m", "sf": 2}, "explanation": "s = 1/2 a t^2 = 9.0 m"}}


SET = [mcq(1), typed(2), mcq(3)]


def fake_generator(monkeypatch, questions=SET, skipped=(), calls=None):
    async def gen(ask, cfg, scope, on_progress=None, cancelled=lambda: False, parallel=3, seed=None):
        if calls is not None:
            calls.append({"cfg": cfg, "scope": scope, "seed": seed})
        for k in range(1, len(questions) + 1):
            await asyncio.sleep(0)
            on_progress and on_progress(k, len(questions), f"Q{k} ready")
        return {"questions": list(questions), "skipped": list(skipped), "log": []}
    monkeypatch.setattr(cs, "generate_set", gen)


def run(app, size, steps):
    async def go():
        async with app.run_test(size=size) as pilot:
            await pilot.pause()
            await steps(pilot)
            await app.ai.close()
    asyncio.run(go())


async def wait_for(pilot, cond, tries=80):
    for _ in range(tries):
        await pilot.pause(0.02)
        if cond():
            return True
    return False


async def open_challenge(pilot, app):
    menu = app.screen.query_one("#menu")
    menu.highlighted = [o.id for o in menu.options].index("challenge")
    await pilot.press("enter")
    await pilot.pause()
    assert type(app.screen).__name__ == "ChallengeScreen"
    return app.screen


def panel(scr):
    return next(iter(scr.query("#panel > *")), None)


async def choose(pilot, scr, ids):
    """Press ⏎ on the button with this id, wherever the panel put it."""
    p = panel(scr)
    assert isinstance(p, ContinuePanel), p
    p.query_one(f"#{ids}").press()
    await pilot.pause()


def rows(scr):
    lst = scr.query_one("#settings")
    return {lst.get_option_at_index(i).id: str(lst.get_option_at_index(i).prompt) for i in range(lst.option_count)}


async def set_up(pilot, scr, words="3 questions on 9702-2.1, level 4 to 6"):
    scr.query_one("#words", Composer).focus()
    await pilot.press(*words, "enter")
    await pilot.pause()


async def start(pilot, scr):
    lst = scr.query_one("#settings")
    lst.focus()
    lst.highlighted = lst.option_count - 1
    await pilot.press("enter")
    assert await wait_for(pilot, lambda: scr.phase == "question")


# ---------------- config helpers ----------------
def test_the_last_settings_are_remembered_and_never_read_as_a_set(tmp_path):
    from fixtures import make_vault
    from tutorlib import packs as packs_mod
    v = store.Vault(make_vault(tmp_path))
    p = packs_mod.Packs(v)
    assert ch.load_config(v, p) == ch.DEFAULT_CONFIG
    ch.save_config(v, {**ch.DEFAULT_CONFIG, "count": 12, "topics": ["9702-2.1", "9702-99.9"], "model": "opus"})
    got = ch.load_config(v, p)
    assert got["count"] == 12 and got["model"] == "opus" and got["topics"] == ["9702-2.1"]
    assert ch.ChallengeSet.all(v) == []


def test_preview_and_cost_texts():
    slots = ch.plan_slots({**ch.DEFAULT_CONFIG, "count": 4, "lo": 3, "hi": 9})
    assert cs.plan_text(slots) == "Q1 3 · Q2 5 · Q3 7 · Q4 9 (M T M T)"
    assert "About 16 AI calls (4 a question, more when one is retried)" in cs.wait_text({"count": 4, "model": "sonnet"})
    assert "limit" in cs.wait_text({"count": 4, "model": "opus"})
    assert cs.fallback_text({"count": 3}, "opus") == "Opus declined 3 requests; Sonnet did them instead."
    assert cs.fallback_text({"count": 0}, "opus") == "" and cs.fallback_text(None, "opus") == ""


# ---------------- setup ----------------
@pytest.mark.parametrize("size", [(60, 24), (80, 24), (100, 30)])
def test_menu_opens_setup_words_and_list_change_it_and_the_preview_follows(tmp_path, monkeypatch, size):
    app, v = app_for(tmp_path, monkeypatch)

    async def steps(pilot):
        scr = await open_challenge(pilot, app)
        assert scr.phase == "setup" and scr.query_one("#settings").has_focus
        await set_up(pilot, scr, "12 questions on 9702-2.1, start easy, jump fast to hard then slowly to extreme, opus")
        c = scr.cfg
        assert (c["count"], c["topics"], c["model"], c["ramp"]) == (12, ["9702-2.1"], "opus", "fast-then-slow")
        said = str(scr.query_one("#understood").render())
        assert "Understood" in said and "12 questions" in said
        r = rows(scr)
        assert "12" in r["count"] and "Opus" in r["model"] and "9702-2.1" in r["topics"]
        preview = str(scr.query_one("#preview").render())
        assert cs.plan_text(ch.plan_slots(scr.cfg, scr.seed)) in " ".join(preview.split("\n"))
        assert "Equations of motion" not in preview and "idea" in preview  # the scope summary
        await shot(pilot, f"challenge-setup-{size[0]}x{size[1]}")
        # the list: ← → step a value; ⏎ opens a picker
        lst = scr.query_one("#settings")
        lst.focus()
        lst.highlighted = [lst.get_option_at_index(i).id for i in range(lst.option_count)].index("count")
        await pilot.press("left")
        assert scr.cfg["count"] == 11
        await pilot.press("enter")  # the number box
        await pilot.pause()
        await pilot.press("7", "enter")  # the number is selected: typing replaces it
        await pilot.pause()
        assert scr.cfg["count"] == 7 and "7" in rows(scr)["count"]
        lst.highlighted = [lst.get_option_at_index(i).id for i in range(lst.option_count)].index("hi")
        await pilot.press("enter")
        await pilot.pause()
        assert type(app.screen).__name__ == "PickScreen"
        await pilot.press("down", "enter")  # one level harder than now
        await pilot.pause()
        assert scr.cfg["hi"] == 10 and "Impossible" in rows(scr)["hi"]
        assert "Impossible" in str(scr.query_one("#detail").render())
        lst.highlighted = [lst.get_option_at_index(i).id for i in range(lst.option_count)].index("model")
        await pilot.press("right")
        assert scr.cfg["model"] == "sonnet"
        # fits: nothing to the right of the window, the list fully on screen when it has focus
        assert all(w.region.right <= size[0] for w in scr.query("#setup > *") if w.display)
        assert lst.region.bottom <= size[1] - 1
        # remembered: Esc to the menu and back keeps everything
        await pilot.press("escape")
        await pilot.pause()
        assert type(app.screen).__name__ == "HomeScreen"
        scr = await open_challenge(pilot, app)
        assert scr.cfg["count"] == 7 and scr.cfg["model"] == "sonnet" and scr.cfg["hi"] == 10
    run(app, size, steps)


def test_topics_are_picked_from_a_tick_list_with_the_scope_shown(tmp_path, monkeypatch):
    app, v = app_for(tmp_path, monkeypatch)

    async def steps(pilot):
        scr = await open_challenge(pilot, app)
        lst = scr.query_one("#settings")
        lst.highlighted = 0
        await pilot.press("enter")
        await pilot.pause()
        assert type(app.screen).__name__ == "TopicScreen"
        await pilot.press("space")
        await pilot.pause()
        assert "9702-2.1" in str(app.screen.query_one("#scope").render())
        await pilot.press("ctrl+s")
        await pilot.pause()
        assert scr.cfg["topics"] == ["9702-2.1"]
    run(app, (60, 24), steps)


def test_start_needs_a_topic(tmp_path, monkeypatch):
    app, v = app_for(tmp_path, monkeypatch)
    fake_generator(monkeypatch)

    async def steps(pilot):
        scr = await open_challenge(pilot, app)
        lst = scr.query_one("#settings")
        lst.highlighted = lst.option_count - 1
        await pilot.press("enter")
        await pilot.pause()
        assert scr.phase == "setup" and lst.highlighted == 0
    run(app, (80, 24), steps)


# ---------------- a whole set ----------------
@pytest.mark.parametrize("size", [(60, 24), (80, 24), (100, 30)])
def test_a_whole_set_mcq_right_typed_with_unit_then_i_dont_know(tmp_path, monkeypatch, size):
    app, v = app_for(tmp_path, monkeypatch)
    calls = []
    fake_generator(monkeypatch, calls=calls)
    learner = v / ".tutor" / "state" / "learner.json"

    async def steps(pilot):
        before = learner.read_bytes() if learner.exists() else None
        scr = await open_challenge(pilot, app)
        await set_up(pilot, scr)
        await start(pilot, scr)
        assert calls[0]["seed"] == scr.seed or calls[0]["cfg"]["count"] == 3
        assert {k["id"] for k in calls[0]["scope"]} == {"9702-2.1.1", "9702-2.1.4"}
        assert "1/3" in str(scr.query_one("#bar").render()) and "Exam-hard" in str(scr.query_one("#bar").render())
        assert isinstance(panel(scr), ChoicePanel)
        await shot(pilot, f"challenge-q1-{size[0]}x{size[1]}")
        await pilot.press("b")  # right
        await pilot.pause()
        assert scr.fb["correct"] is True
        assert scr.set.summary()["correct"] == 1
        await choose(pilot, scr, "next")
        assert isinstance(panel(scr), ValuePanel)
        await pilot.press(*"9.0 m", "enter")
        await pilot.pause()
        assert scr.set.answers[1]["grade"]["correct"] is True and scr.set.answers[1]["response"] == "9.0 m"
        await shot(pilot, f"challenge-fb-{size[0]}x{size[1]}")
        await choose(pilot, scr, "next")
        await pilot.press("0")  # I don't know
        await pilot.pause()
        assert scr.set.answers[2]["response"] == "don't know" and not scr.set.answers[2]["grade"]["correct"]
        await choose(pilot, scr, "finish")
        assert scr.phase == "summary"
        s = scr.set.summary()
        assert (s["correct"], s["answered"], s["best_level"]) == (2, 3, 6)
        await shot(pilot, f"challenge-summary-{size[0]}x{size[1]}")
        assert all(b.region.right <= size[0] for b in scr.query("Button")), [(b.id, b.region) for b in scr.query("Button")]
        assert (learner.read_bytes() if learner.exists() else None) == before  # the learner's model is untouched
        assert app.tutor.session is None
        await choose(pilot, scr, "home")
        assert type(app.screen).__name__ == "HomeScreen"
    run(app, size, steps)


def test_a_wrong_mcq_and_a_typed_answer_missing_its_unit(tmp_path, monkeypatch):
    app, v = app_for(tmp_path, monkeypatch)
    fake_generator(monkeypatch)

    async def steps(pilot):
        scr = await open_challenge(pilot, app)
        await set_up(pilot, scr)
        await start(pilot, scr)
        await pilot.press("a")
        await pilot.pause()
        assert scr.fb["correct"] is False and scr.fb["answer"] == "B: 9.0 m"
        await choose(pilot, scr, "next")
        await pilot.press(*"7.5 m", "enter")  # wrong value
        await pilot.pause()
        assert scr.fb["correct"] is False and "remark" in [b.id for b in scr.query("Button")]
        assert "why" in [b.id for b in scr.query("Button")]
    run(app, (80, 24), steps)


def test_an_unreadable_typed_answer_stays_open(tmp_path, monkeypatch):
    app, v = app_for(tmp_path, monkeypatch)
    fake_generator(monkeypatch, questions=[typed(1)])

    async def steps(pilot):
        scr = await open_challenge(pilot, app)
        await set_up(pilot, scr, "1 question on 9702-2.1")
        await start(pilot, scr)
        await pilot.press(*"nine metres", "enter")
        await pilot.pause()
        assert scr.set.answers == [] and isinstance(panel(scr), ValuePanel)
    run(app, (80, 24), steps)


def test_remark_by_ai_counts_a_typed_answer_right(tmp_path, monkeypatch):
    app, v = app_for(tmp_path, monkeypatch)
    fake_generator(monkeypatch, questions=[typed(1), mcq(2)])

    async def steps(pilot):
        scr = await open_challenge(pilot, app)
        await set_up(pilot, scr, "2 questions on 9702-2.1")
        await start(pilot, scr)
        await pilot.press(*"9 m", "enter")  # 1 s.f. where 2 were asked: the grader docks it
        await pilot.pause()
        seen = []

        async def one_shot(prompt, schema=None, model=None, timeout=120):
            seen.append((prompt, model))
            return {"correct": True, "why": "900 cm is 9.0 m."}, None
        monkeypatch.setattr(app.ai, "one_shot", one_shot)
        assert scr.fb["correct"] is False and scr.fb["partial"]
        await choose(pilot, scr, "remark")
        assert await wait_for(pilot, lambda: scr.fb.get("remarked"))
        await pilot.pause()
        assert scr.set.answers[0]["grade"]["correct"] is True and scr.set.answers[0]["regraded"]
        assert "9 m" in seen[0][0] and seen[0][1] == "sonnet" and "remark" not in [b.id for b in scr.query("Button")]
    run(app, (80, 24), steps)


def test_explain_streams_an_ai_reply(tmp_path, monkeypatch):
    app, v = app_for(tmp_path, monkeypatch)
    fake_generator(monkeypatch, questions=[mcq(1), mcq(2)])

    async def steps(pilot):
        scr = await open_challenge(pilot, app)
        await set_up(pilot, scr, "2 questions on 9702-2.1")
        await start(pilot, scr)
        await pilot.press("a")
        await pilot.pause()
        await choose(pilot, scr, "why")
        assert await wait_for(pilot, lambda: app.ai.session.replies == 1, tries=200)
    run(app, (80, 24), steps)


def test_leave_mid_set_resumes_and_new_set_puts_it_aside(tmp_path, monkeypatch):
    app, v = app_for(tmp_path, monkeypatch)
    fake_generator(monkeypatch)

    async def steps(pilot):
        scr = await open_challenge(pilot, app)
        await set_up(pilot, scr)
        await start(pilot, scr)
        await pilot.press("b")
        await pilot.pause()
        await choose(pilot, scr, "next")
        await pilot.press("escape")  # nothing typed: straight to the menu, the place kept
        await pilot.pause()
        assert type(app.screen).__name__ == "HomeScreen"
        scr = await open_challenge(pilot, app)
        assert scr.phase == "start" and "1 of 3 done" in str(panel(scr).query_one("#resume").label)
        await choose(pilot, scr, "resume")
        assert scr.phase == "question" and scr.i == 1 and isinstance(panel(scr), ValuePanel)
        await pilot.press("escape")
        await pilot.pause()
        scr = await open_challenge(pilot, app)
        await choose(pilot, scr, "new")
        assert scr.phase == "setup"
        await pilot.press("escape")
        await pilot.pause()
        scr = await open_challenge(pilot, app)
        assert scr.phase == "setup"  # the set put aside is not offered again
    run(app, (60, 24), steps)


def test_a_stopped_set_shows_its_score_once_and_does_not_come_back(tmp_path, monkeypatch):
    app, v = app_for(tmp_path, monkeypatch)
    fake_generator(monkeypatch)

    async def steps(pilot):
        scr = await open_challenge(pilot, app)
        await set_up(pilot, scr)
        await start(pilot, scr)
        await pilot.press("b")
        await pilot.pause()
        await choose(pilot, scr, "stop")
        assert scr.phase == "summary" and scr.set.summary()["answered"] == 1 and scr.set.closed
        await choose(pilot, scr, "home")
        scr = await open_challenge(pilot, app)
        assert scr.phase == "setup"
        assert ch.ChallengeSet.open_latest_unfinished(app.tutor.vault) is None
    run(app, (60, 24), steps)


def test_another_set_after_resuming_uses_that_sets_settings(tmp_path, monkeypatch):
    app, v = app_for(tmp_path, monkeypatch)
    calls = []
    fake_generator(monkeypatch, questions=[mcq(1), mcq(2)], calls=calls)

    async def steps(pilot):
        vault = app.tutor.vault
        ch.ChallengeSet.new(vault, {**ch.DEFAULT_CONFIG, "topics": ["9702-2.1"], "count": 2, "ramp": "wave"},
                            [mcq(1), mcq(2)])
        ch.save_config(vault, {**ch.DEFAULT_CONFIG, "topics": ["9702-2.1"], "count": 5})
        scr = await open_challenge(pilot, app)
        await choose(pilot, scr, "resume")
        for _ in range(2):
            await pilot.press("b")
            await pilot.pause()
            await choose(pilot, scr, panel(scr).buttons[0][0])
        assert scr.phase == "summary"
        await choose(pilot, scr, "again")
        assert await wait_for(pilot, lambda: calls)
        assert calls[0]["cfg"]["count"] == 2 and calls[0]["cfg"]["ramp"] == "wave"
    run(app, (80, 24), steps)


def test_skipped_questions_are_reported_in_one_line(tmp_path, monkeypatch):
    app, v = app_for(tmp_path, monkeypatch)
    fake_generator(monkeypatch, questions=[mcq(1)],
                   skipped=[{"n": 2, "level": 9, "kind": "typed", "reason": "too easy (rated level 5, wanted 9)"}])

    async def steps(pilot):
        scr = await open_challenge(pilot, app)
        await set_up(pilot, scr, "2 questions on 9702-2.1")
        await start(pilot, scr)
        notes = " ".join(text_of(w) for w in scr.query(".entry"))
        assert "1 question could not be made solid enough" in notes and "too easy" in notes
    run(app, (80, 24), steps)


def test_no_questions_out_returns_to_setup_and_says_why(tmp_path, monkeypatch):
    app, v = app_for(tmp_path, monkeypatch)
    fake_generator(monkeypatch, questions=[], skipped=[{"n": 1, "level": 9, "kind": "mcq", "reason": "the AI call failed"}])

    async def steps(pilot):
        scr = await open_challenge(pilot, app)
        await set_up(pilot, scr, "1 question on 9702-2.1")
        lst = scr.query_one("#settings")
        lst.focus()
        lst.highlighted = lst.option_count - 1
        await pilot.press("enter")
        assert await wait_for(pilot, lambda: scr.phase == "setup" and scr.query("#setup-note"))
        assert "No questions came out" in str(scr.query_one("#setup-note").render())
        assert ch.ChallengeSet.all(app.tutor.vault) == []
    run(app, (80, 24), steps)


def test_esc_while_writing_cancels_cleanly_back_to_setup(tmp_path, monkeypatch):
    app, v = app_for(tmp_path, monkeypatch)
    state = {"cancelled": False}

    async def slow(ask, cfg, scope, on_progress=None, cancelled=lambda: False, parallel=3, seed=None):
        try:
            on_progress(0, 3, "")
            await asyncio.sleep(30)
        except asyncio.CancelledError:
            state["cancelled"] = True
            raise
        return {"questions": SET, "skipped": [], "log": []}
    monkeypatch.setattr(cs, "generate_set", slow)

    async def steps(pilot):
        scr = await open_challenge(pilot, app)
        await set_up(pilot, scr)
        lst = scr.query_one("#settings")
        lst.focus()
        lst.highlighted = lst.option_count - 1
        await pilot.press("enter")
        assert await wait_for(pilot, lambda: scr.phase == "generating")
        await shot(pilot, "challenge-generating")
        assert "Writing question 1 of 3" in str(scr.progress.content.renderable)
        await pilot.press("escape")
        assert await wait_for(pilot, lambda: state["cancelled"])
        assert scr.phase == "setup" and "Cancelled" in str(scr.query_one("#setup-note").render())
        assert ch.ChallengeSet.all(app.tutor.vault) == []
    run(app, (80, 24), steps)


def test_the_ask_wrapper_passes_model_and_timeout_and_returns_the_dict(tmp_path, monkeypatch):
    app, v = app_for(tmp_path, monkeypatch)
    seen = []

    async def one_shot(prompt, schema=None, model=None, timeout=120, system=None):
        seen.append((prompt, model, timeout, schema, system))
        return {"ok": 1}, None

    async def old_one_shot(prompt, schema=None, model=None, timeout=120):
        seen.append((prompt, model, timeout, schema, None))
        return {"ok": 1}, None

    async def steps(pilot):
        from tutorlib import challenge_gen
        scr = await open_challenge(pilot, app)
        monkeypatch.setattr(app.ai, "one_shot", one_shot)
        assert await scr.ask("write one", {"type": "object"}, "opus", 600) == {"ok": 1}
        assert seen[-1] == ("write one", "opus", 600, {"type": "object"}, challenge_gen.GEN_SYSTEM)
        monkeypatch.setattr(app.ai, "one_shot", old_one_shot)  # no system parameter: put in front of the prompt
        assert await scr.ask("write one", None, "sonnet", 300) == {"ok": 1}
        assert seen[-1] == (f"{challenge_gen.GEN_SYSTEM}\n\nwrite one", "sonnet", 300, None, None)
    run(app, (80, 24), steps)


def test_no_ai_says_so_plainly_and_does_not_start(tmp_path, monkeypatch):
    app, v = app_for(tmp_path, monkeypatch)
    calls = []
    fake_generator(monkeypatch, calls=calls)

    async def steps(pilot):
        app.ai.status, app.ai.message = "off", "Claude Code is not installed, so AI help is off."
        scr = await open_challenge(pilot, app)
        assert "Claude Code is not installed" in str(scr.query_one("#setup-note").render())
        await set_up(pilot, scr)
        lst = scr.query_one("#settings")
        lst.focus()
        lst.highlighted = lst.option_count - 1
        await pilot.press("enter")
        await pilot.pause()
        assert scr.phase == "setup" and calls == []
    run(app, (60, 24), steps)


@pytest.mark.parametrize("theme", ["classic", "night", "day"])
def test_every_look_draws_each_phase(tmp_path, monkeypatch, theme):
    app, v = app_for(tmp_path, monkeypatch)
    fake_generator(monkeypatch)

    async def steps(pilot):
        look.apply(app, theme)
        await pilot.pause()
        scr = await open_challenge(pilot, app)
        await set_up(pilot, scr)
        await start(pilot, scr)
        await pilot.press("b")
        await pilot.pause()
        await choose(pilot, scr, "stop")
        await shot(pilot, f"challenge-summary-{theme}")
        assert scr.phase == "summary"
    try:
        run(app, (60, 24), steps)
    finally:
        look.use("classic")


def test_a_declined_call_raises_refused_for_the_generator_to_hand_on(tmp_path, monkeypatch):
    from tutor_app import ai as ai_mod
    from tutorlib import challenge_gen
    app, v = app_for(tmp_path, monkeypatch)

    async def one_shot(prompt, schema=None, model=None, timeout=120):
        return None, ai_mod.Result(ok=False, status="error", message="API Error: our safeguards flagged this request")

    async def steps(pilot):
        scr = await open_challenge(pilot, app)
        monkeypatch.setattr(app.ai, "one_shot", one_shot)
        with pytest.raises(challenge_gen.Refused):
            await scr.ask("write one", None, "opus", 600)
    run(app, (80, 24), steps)


def test_a_model_fallback_is_said_in_one_line_and_shown_on_the_question(tmp_path, monkeypatch):
    app, v = app_for(tmp_path, monkeypatch)
    q = {**mcq(1), "model": "sonnet"}

    async def gen(ask, cfg, scope, on_progress=None, cancelled=lambda: False, parallel=3, seed=None):
        return {"questions": [q], "skipped": [], "log": [],
                "fallbacks": {"count": 1, "declined": {"opus": 1}, "note": "Opus declined 1 question; Sonnet wrote it instead."}}
    monkeypatch.setattr(cs, "generate_set", gen)

    async def steps(pilot):
        scr = await open_challenge(pilot, app)
        await set_up(pilot, scr, "1 question on 9702-2.1, opus")
        await start(pilot, scr)
        shown = " ".join(text_of(w) for w in scr.query(".entry"))
        assert "Opus declined 1 question; Sonnet wrote it instead." in shown
        assert "by Sonnet" in str(scr.query(".entry").last().content.title)
    run(app, (80, 24), steps)


# ---------------- review fixes ----------------
def test_damaged_set_files_are_skipped_and_never_crash(tmp_path, monkeypatch):
    import json
    app, v = app_for(tmp_path, monkeypatch)
    folder = v / ".tutor" / "challenge"
    folder.mkdir(parents=True)
    good = {"id": "20261001-000000", "created": "x", "cfg": {"topics": []}, "questions": [mcq(1), mcq(2)],
            "answers": [{"index": 0, "response": "B", "grade": {"correct": True}, "seconds": 3}]}
    bad = {"20261002-000000": {**good, "answers": [{"index": 9, "grade": {"correct": True}}]},  # index out of range
           "20261003-000000": {**good, "answers": {"0": "x"}},  # answers as a dict
           "20261004-000000": {**good, "cfg": ["a"]},  # cfg as a list
           "20261005-000000": [1, 2]}
    (folder / "20261001-000000.json").write_text(json.dumps(good))
    for name, data in bad.items():
        (folder / f"{name}.json").write_text(json.dumps(data))
    (folder / "20261006-000000.json").write_text("{not json")

    async def steps(pilot):
        rows = ch.ChallengeSet.all(app.tutor.vault)
        assert [r["id"] for r in rows] == ["20261002-000000", "20261001-000000"]
        assert rows[0]["answered"] == 0  # the out-of-range answer is dropped, not counted
        scr = await open_challenge(pilot, app)
        assert scr.phase == "start" and scr.set.id == "20261002-000000"
    run(app, (80, 24), steps)


def test_a_long_question_can_be_scrolled_by_keyboard_at_60x24(tmp_path, monkeypatch):
    app, v = app_for(tmp_path, monkeypatch)
    long = typed(1)
    long["item"] = {**long["item"], "stem": " ".join(f"Step {k}: $v^2 = u^2 + 2as$ with $a = {k}.0$ m s$^{{-2}}$."
                                                      for k in range(40)) + " LAST LINE: give your answer in m."}
    fake_generator(monkeypatch, questions=[long])

    async def steps(pilot):
        scr = await open_challenge(pilot, app)
        await set_up(pilot, scr, "1 question on 9702-2.1")
        await start(pilot, scr)
        log = scr.query_one("#log")
        assert log.max_scroll_y > 0 and log.scroll_y == 0
        for _ in range(30):
            await pilot.press("alt+down")  # works while the answer box has the focus
        await pilot.pause()
        assert log.scroll_y == log.max_scroll_y
        await pilot.press("alt+up")
        await pilot.pause()
        assert log.scroll_y < log.max_scroll_y
    run(app, (60, 24), steps)


def test_an_unreadable_answer_keeps_the_clock_and_one_question_card(tmp_path, monkeypatch):
    app, v = app_for(tmp_path, monkeypatch)
    fake_generator(monkeypatch, questions=[typed(1)])

    async def steps(pilot):
        scr = await open_challenge(pilot, app)
        await set_up(pilot, scr, "1 question on 9702-2.1")
        await start(pilot, scr)
        clock, cards_before = scr.clock, len(scr.query("#log > .entry"))
        await pilot.press(*"nine metres", "enter")
        await pilot.pause()
        assert scr.clock == clock and len(scr.query("#log > .entry")) == cards_before
        assert isinstance(panel(scr), ValuePanel) and panel(scr).query_one("#value").has_focus
    run(app, (80, 24), steps)


def test_next_stops_an_explanation_still_arriving(tmp_path, monkeypatch):
    app, v = app_for(tmp_path, monkeypatch)
    fake_generator(monkeypatch, questions=[mcq(1), mcq(2)])
    stopped = []

    async def stream(prompt):
        try:
            yield "Part one"
            await asyncio.sleep(30)
            yield "never"
        except (asyncio.CancelledError, GeneratorExit):
            stopped.append(True)
            raise

    async def steps(pilot):
        scr = await open_challenge(pilot, app)
        await set_up(pilot, scr, "2 questions on 9702-2.1")
        await start(pilot, scr)
        monkeypatch.setattr(app.ai, "stream", stream)
        await pilot.press("a")
        await pilot.pause()
        await choose(pilot, scr, "why")
        await pilot.pause(0.1)
        await choose(pilot, scr, "next")
        assert await wait_for(pilot, lambda: stopped)
        assert scr.i == 1
    run(app, (80, 24), steps)


def test_a_regrade_counts_once_only(tmp_path):
    from fixtures import make_vault
    v = store.Vault(make_vault(tmp_path))
    s = ch.ChallengeSet.new(v, {"topics": []}, [typed(1)])
    s.record(0, "9 m", {"correct": False, "score": 0.5}, 10)
    assert s.regrade(0, "fine") is True and s.regrade(0, "again") is False
    assert sum(e["type"] == "challenge_regrade" for e in v.events()) == 1


@pytest.mark.parametrize("words, want", [
    ("no mcq", {"kinds": "typed"}), ("10 questions without mcqs", {"kinds": "typed", "count": 10}),
    ("level 7 and above", {"lo": 7}), ("7+", {"lo": 7}), ("up to level 6", {"hi": 6})])
def test_parser_edge_cases(tmp_path, words, want):
    from fixtures import make_vault
    from tutorlib import packs as packs_mod
    v = store.Vault(make_vault(tmp_path))
    assert ch.parse_request(words, packs_mod.Packs(v))["config"] == want


# ---------------- live-test fixes ----------------
def text_of(widget, width=100) -> str:
    from rich.console import Console
    con = Console(width=width, record=True, file=open("/dev/null", "w"))
    con.print(widget.content)
    return con.export_text()


def test_a_real_refused_fallback_and_skips_are_said_on_the_first_question_and_the_summary(tmp_path, monkeypatch):
    """The real generator: Opus declines every question it is asked to write; Sonnet writes them."""
    import re
    from tutor_app import ai as ai_mod
    from tutorlib import challenge_gen as cg
    app, v = app_for(tmp_path, monkeypatch)

    async def one_shot(prompt, schema=None, model=None, timeout=120, system=None):
        call = cg.call_name(schema)
        if call == "generate" and model == "opus":
            return None, ai_mod.Result(ok=False, status="error", message="API Error: safeguards flagged this")
        if call == "generate":
            return {"stem": STEM.replace(" Give your answer in m to 2 significant figures.", ""), "correct": "9.0 m",
                    "wrong": [{"text": t, "mistake": "slip"} for t in ("18 m", "6.0 m", "3.0 m")],
                    "solution": "s = 1/2 a t^2 = 0.5 x 2.0 x 9.0 = 9.0 m",
                    "concepts": sorted(set(re.findall(r"9702-\d+\.\d+\.\d+", prompt.split("REQUIRED", 1)[-1]))
                                       if "REQUIRED" in prompt else ["9702-2.1.4"])}, None
        if call == "solve":
            return {"working": "s = 9.0 m", "answer": re.search(r"^([A-D])\) 9\.0 m$", prompt, re.M)[1]}, None
        return {"working": "ok", "solution_correct": True, "concepts": [{"idea": "suvat", "kc": "9702-2.1.4"}],
                "out_of_scope": [], "rated_level": 5, "problems": []}, None

    async def steps(pilot):
        scr = await open_challenge(pilot, app)
        monkeypatch.setattr(app.ai, "one_shot", one_shot)
        await set_up(pilot, scr, "2 questions on 9702-2.1, level 5, multiple choice only, opus")
        lst = scr.query_one("#settings")
        lst.focus()
        lst.highlighted = lst.option_count - 1
        await pilot.press("enter")
        assert await wait_for(pilot, lambda: scr.phase == "question", tries=400)
        card = text_of(scr.query("#log > .entry").last())
        assert "Opus declined 2 questions; Sonnet wrote them instead." in card and "by Sonnet" in card
        assert card.index("declined") < card.index("A car accelerates")  # above the stem
        for _ in range(2):
            await pilot.press("b")
            await pilot.pause()
            await choose(pilot, scr, panel(scr).buttons[0][0])
        assert scr.phase == "summary" and "Opus declined 2 questions" in text_of(scr.query("#log > .entry").last())
    run(app, (80, 24), steps)


def test_skipped_and_calls_notes_show_on_the_first_question_only_and_on_the_summary(tmp_path, monkeypatch):
    app, v = app_for(tmp_path, monkeypatch)

    async def gen(ask, cfg, scope, on_progress=None, cancelled=lambda: False, parallel=3, seed=None):
        return {"questions": [mcq(1), mcq(2)], "skipped": [{"n": 3, "level": 9, "kind": "mcq", "reason": "too easy"}],
                "log": [], "calls": 14}
    monkeypatch.setattr(cs, "generate_set", gen)

    async def steps(pilot):
        scr = await open_challenge(pilot, app)
        await set_up(pilot, scr, "3 questions on 9702-2.1")
        await start(pilot, scr)
        first = text_of(scr.query("#log > .entry").last())
        assert "1 question could not be made solid enough" in first and "14 AI calls" in first
        await pilot.press("b")
        await pilot.pause()
        await choose(pilot, scr, "next")
        assert "solid enough" not in text_of(scr.query("#log > .entry").last())
        await pilot.press("b")
        await pilot.pause()
        await choose(pilot, scr, "finish")
        summary = text_of(scr.query("#log > .entry").last())
        assert "solid enough" in summary and "2 right out of 2" in summary
        assert "\n\n\n" not in summary.split("Highest")[1]  # no padding rows in the by-level lines
    run(app, (80, 24), steps)


@pytest.mark.parametrize("size", [(60, 24), (80, 24)])
def test_feedback_opens_at_its_verdict_with_a_long_solution(tmp_path, monkeypatch, size):
    app, v = app_for(tmp_path, monkeypatch)
    q = typed(1)
    q["solution"] = "\n\n".join(f"Step {k}: work out part {k} of the motion carefully." for k in range(25))
    fake_generator(monkeypatch, questions=[q])

    async def steps(pilot):
        scr = await open_challenge(pilot, app)
        await set_up(pilot, scr, "1 question on 9702-2.1")
        await start(pilot, scr)
        await pilot.press(*"9.0 m", "enter")
        await pilot.pause()
        await pilot.pause()
        log, fb = scr.query_one("#log"), scr.query("#log > .entry").last()
        assert fb.region.y >= log.region.y and fb.region.y < log.region.bottom  # its title row is on screen
        assert text_of(fb).index("Your answer") < text_of(fb).index("Step 0")
        for _ in range(30):
            await pilot.press("alt+down")
        await pilot.pause()
        assert log.scroll_y == log.max_scroll_y > 0
    run(app, size, steps)


def test_setup_words_fit_and_read_well_at_60x24(tmp_path, monkeypatch):
    from rich.cells import cell_len
    app, v = app_for(tmp_path, monkeypatch)

    async def steps(pilot):
        scr = await open_challenge(pilot, app)
        words = scr.query_one("#words")
        assert cell_len(words.placeholder) <= words.content_region.width
        await set_up(pilot, scr, "1 question on 9702-2.1, level 10")
        assert "1 question," in str(scr.query_one("#understood").render()) + ","
        assert "1 questions" not in str(scr.query_one("#understood").render())
        assert "level 10 · Impossible" in rows(scr)["lo"]
        lst = scr.query_one("#settings")
        assert lst.region.bottom <= 23  # Start in view
    run(app, (60, 24), steps)


def test_a_question_rated_below_its_ask_says_so_and_counts_at_its_real_level(tmp_path, monkeypatch):
    app, v = app_for(tmp_path, monkeypatch)
    fake_generator(monkeypatch, questions=[{**mcq(1, level=9), "requested": 10}])

    async def steps(pilot):
        scr = await open_challenge(pilot, app)
        await set_up(pilot, scr, "1 question on 9702-2.1")
        await start(pilot, scr)
        assert "level 9 (asked for 10)" in str(scr.query_one("#bar").render())
        assert "level 9 (asked for 10)" in text_of(scr.query("#log > .entry").last())
        await pilot.press("b")
        await pilot.pause()
        await choose(pilot, scr, "finish")
        assert scr.set.summary()["by_level"] == {9: [1, 1]}
        assert "9 Extreme: 1 of 1" in text_of(scr.query("#log > .entry").last())
    run(app, (100, 30), steps)
