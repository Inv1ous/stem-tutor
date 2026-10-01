import asyncio
import os
from pathlib import Path

import pytest

from fixtures import make_vault
from tutor_app.app import TutorApp
from tutor_app.panels import ChoicePanel, ContinuePanel, TickPanel, ValuePanel, TextPanel, WorkedPanel, ChoosePanel, ReflectPanel

FAKE = str(Path(__file__).with_name("fake_claude.py"))
SHOTS = os.environ.get("TUI_SHOTS")


def app_for(tmp_path, monkeypatch, mode="ok"):
    monkeypatch.setenv("FAKE_CLAUDE_MODE", mode)
    monkeypatch.setenv("STEM_TUTOR_NOW", "2026-09-29T17:00:00+08:00")
    v = make_vault(tmp_path)
    return TutorApp(v, claude_binary=FAKE, open_obsidian=False, seed=1), v


async def shot(pilot, name):
    if SHOTS:
        pilot.app.save_screenshot(path=SHOTS, filename=f"{name}.svg")


async def drive_lesson(pilot, app, max_steps=120):
    """Answer everything with keys: first option / 1 confidence, numbers typed, own words typed."""
    seen = []
    for _ in range(max_steps):
        await pilot.pause()
        scr = app.screen
        if scr.__class__.__name__ == "SummaryScreen":
            seen.append("summary")
            await shot(pilot, "summary")
            await pilot.press("enter")
            await pilot.pause()
            break
        panel = next(iter(scr.query("#panel > *")), None) if scr.__class__.__name__ == "SessionScreen" else None
        if panel is None:
            await pilot.pause(0.05)
            continue
        seen.append(type(panel).__name__)
        if isinstance(panel, ChoosePanel):
            await pilot.press("down", "enter")
        elif isinstance(panel, ChoicePanel):
            await shot(pilot, "mcq-" + str(len(seen)))
            if panel.choice is None:
                await pilot.press("b")
            await pilot.pause()
            await pilot.press("3")
        elif isinstance(panel, ValuePanel):
            await pilot.press(*"42", "enter")
            await pilot.pause()
            if panel.query("#conf"):
                await pilot.press("2")
        elif isinstance(panel, TickPanel):
            await shot(pilot, "tick-" + str(len(seen)))
            panel.query("Button").first().press()
        elif isinstance(panel, ReflectPanel):
            await pilot.press("1")
        elif isinstance(panel, WorkedPanel):
            await pilot.press("enter")
        elif isinstance(panel, TextPanel):
            await pilot.press(*"it has a direction", "enter")
        elif isinstance(panel, ContinuePanel):
            panel.query("Button").first().press()
        await pilot.pause()
    return seen


def test_home_menu_and_a_whole_lesson_by_keyboard(tmp_path, monkeypatch):
    app, v = app_for(tmp_path, monkeypatch)

    async def go():
        async with app.run_test(size=(120, 40)) as pilot:
            await pilot.pause()
            await shot(pilot, "home")
            assert app.screen.__class__.__name__ == "HomeScreen"
            await pilot.press("down", "enter")  # Learn a topic (after Today's plan)
            await pilot.pause()
            assert app.screen.__class__.__name__ == "PickerScreen"
            await pilot.press("enter")  # the only subtopic
            await pilot.pause()
            await shot(pilot, "session-start")
            seen = await drive_lesson(pilot, app)
            assert "summary" in seen and "ChoosePanel" in seen and "TickPanel" in seen
            assert app.screen.__class__.__name__ == "HomeScreen"
    asyncio.run(go())
    assert (v / "Now.md").exists() and list((v / "Lessons").glob("*.md")) and list((v / "My Notes").rglob("*.md"))


def test_chat_streams_an_ai_reply(tmp_path, monkeypatch):
    app, v = app_for(tmp_path, monkeypatch)

    async def go():
        async with app.run_test(size=(120, 40)) as pilot:
            await pilot.pause()
            menu = app.screen.query_one("#menu")
            menu.highlighted = [o.id for o in menu.options].index("chat")
            await pilot.press("enter")
            await pilot.pause()
            await pilot.press(*"why is velocity a vector", "enter")
            for _ in range(40):
                await pilot.pause(0.05)
                if app.ai.session.replies:
                    break
            await shot(pilot, "chat")
            assert app.ai.session.replies == 1 and app.ai.last.text.startswith("Reply 1")
            await app.ai.close()
    asyncio.run(go())


def test_ai_login_needed_is_explained_not_crashing(tmp_path, monkeypatch):
    app, v = app_for(tmp_path, monkeypatch, mode="login")

    async def go():
        async with app.run_test(size=(120, 40)) as pilot:
            await pilot.pause()
            menu = app.screen.query_one("#menu")
            idx = [o.id for o in menu.options].index("chat")
            menu.highlighted = idx
            await pilot.press("enter")
            await pilot.pause()
            await pilot.press(*"what is a vector", "enter")
            for _ in range(40):
                await pilot.pause(0.05)
            await shot(pilot, "chat-login")
            assert app.ai.status == "login" and "claude auth login" in app.ai.message
            assert len(app.screen.query(".entry")) >= 2  # your question + the explanation card
    asyncio.run(go())


def test_long_question_typed_then_self_marked(tmp_path, monkeypatch):
    app, v = app_for(tmp_path, monkeypatch)
    from tutor_app.panels import LongPanel

    async def go():
        async with app.run_test(size=(120, 40)) as pilot:
            await pilot.pause()
            menu = app.screen.query_one("#menu")
            menu.highlighted = [o.id for o in menu.options].index("long")
            await pilot.press("enter")
            await pilot.pause()
            await pilot.press("enter")  # the only subtopic
            await pilot.pause()
            panel = app.screen.query_one("#panel > *")
            assert isinstance(panel, LongPanel)
            await pilot.press(*"v = u + at = 19.6 m/s", "ctrl+s")
            await pilot.pause()
            tick = app.screen.query_one("#panel > *")
            assert isinstance(tick, TickPanel)
            await shot(pilot, "long-scheme")
            await pilot.press("tab")  # to the list
            tick.query_one("#ticks").select_all()
            tick.query("Button").first().press()
            await pilot.pause()
            evs = [e for e in app.tutor.vault.events() if e["type"] == "answer"]
            assert evs and evs[-1]["grade"]["score"] == 1.0
            await app.ai.close()
    asyncio.run(go())


def test_short_answer_self_judged_when_ai_is_off(tmp_path, monkeypatch):
    app, v = app_for(tmp_path, monkeypatch)
    app.settings.ai = False

    async def go():
        async with app.run_test(size=(120, 40)) as pilot:
            await pilot.pause()
            t = app.tutor
            t.start("review", minutes=10)
            item = {"id": "s1", "kcs": ["9702-2.1.1"], "kind": "short", "difficulty": 3, "marks": 2,
                    "stem": "Define displacement.",
                    "rubric": [{"point": "distance", "keywords": [["distance"]]}, {"point": "direction", "keywords": [["direction"]]}]}
            n = t._present(item, block="practice", phase=None)["n"]
            from tutor_app.screens import SessionScreen
            await app.push_screen(SessionScreen(None))
            await pilot.pause()
            await pilot.press(*"how far it moved", "enter")
            await pilot.pause()
            await pilot.press("3")
            await pilot.pause()
            tick = app.screen.query_one("#panel > *")
            assert isinstance(tick, TickPanel)
            tick.query_one("#ticks").select(tick.query_one("#ticks").get_option_at_index(0))
            tick.query("Button").first().press()
            await pilot.pause()
            ev = [e for e in t.vault.events() if e["type"] == "answer"][-1]
            assert ev["grade"]["score"] == 0.5
    asyncio.run(go())


def _menu(app, key):
    menu = app.screen.query_one("#menu")
    menu.highlighted = [o.id for o in menu.options].index(key)


def test_ctrl_keys_work_while_typing_and_ctrl_q_returns_to_menu(tmp_path, monkeypatch):
    app, v = app_for(tmp_path, monkeypatch)

    async def go():
        async with app.run_test(size=(120, 40)) as pilot:
            await pilot.pause()
            await pilot.press("down", "enter", "enter")  # learn -> the only subtopic
            await pilot.pause()
            for _ in range(20):  # walk to the first typed-answer panel
                panel = next(iter(app.screen.query("#panel > *")), None)
                if isinstance(panel, ValuePanel):
                    break
                if isinstance(panel, ChoosePanel):
                    await pilot.press("enter")
                elif isinstance(panel, ChoicePanel):
                    await pilot.press("b"); await pilot.pause(); await pilot.press("3")
                elif isinstance(panel, (ContinuePanel, TickPanel)):
                    panel.query("Button").first().press()
                elif isinstance(panel, ReflectPanel):
                    await pilot.press("1")
                elif isinstance(panel, WorkedPanel):
                    await pilot.press("enter")
                elif isinstance(panel, TextPanel):
                    await pilot.press(*"words", "enter")
                await pilot.pause()
            assert isinstance(panel, ValuePanel)
            await pilot.press("4", "ctrl+t")
            await pilot.pause()
            assert app.screen.__class__.__name__ == "AskScreen"
            await pilot.press("escape")
            await pilot.pause()
            await pilot.press("ctrl+q")
            await pilot.pause()
            assert app.screen.__class__.__name__ == "HomeScreen" and app.is_running
            await app.ai.close()
    asyncio.run(go())


def test_blurt_shows_what_you_remembered(tmp_path, monkeypatch):
    app, v = app_for(tmp_path, monkeypatch)

    async def go():
        async with app.run_test(size=(120, 40)) as pilot:
            await pilot.pause()
            _menu(app, "blurt")
            await pilot.press("enter")
            await pilot.pause()
            await pilot.press("enter")  # the only subtopic
            await pilot.pause()
            assert app.screen.__class__.__name__ == "BlurtScreen"
            await pilot.press(*"displacement is a vector with direction", "ctrl+s")
            await pilot.pause()
            await shot(pilot, "blurt")
            assert any(e["type"] == "blurt" for e in app.tutor.vault.events())
            assert len(app.screen.query(".entry")) >= 3
    asyncio.run(go())


def test_starting_something_new_asks_before_abandoning(tmp_path, monkeypatch):
    app, v = app_for(tmp_path, monkeypatch)

    async def go():
        async with app.run_test(size=(120, 40)) as pilot:
            await pilot.pause()
            app.tutor.start("test", minutes=20, focus=["9702-2.1"])
            act = app.tutor.next()
            q = act["items"][0]
            app.tutor.answer(f"{q['n']}?")
            app.screen.refresh_home()
            _menu(app, "learn")
            await pilot.press("enter")
            await pilot.pause()
            assert app.screen.__class__.__name__ == "ConfirmScreen"
    asyncio.run(go())


async def _open_long_and_submit(pilot, app, text):
    menu = app.screen.query_one("#menu")
    menu.highlighted = [o.id for o in menu.options].index("long")
    await pilot.press("enter")
    await pilot.pause()
    await pilot.press("enter")  # the only subtopic
    await pilot.pause()
    await pilot.press(*text, "ctrl+s")
    await pilot.pause()
    return app.screen.query_one("#panel > *")


def test_long_answer_working_is_saved_in_the_lesson_log(tmp_path, monkeypatch):  # B-015
    app, v = app_for(tmp_path, monkeypatch)

    async def go():
        async with app.run_test(size=(120, 40)) as pilot:
            await pilot.pause()
            await _open_long_and_submit(pilot, app, "MY SUBMITTED WORK v = u + at")
            log = app.tutor._lesson_log()
            assert log and "MY SUBMITTED WORK v = u + at" in (v / log.rel).read_text()
            await app.ai.close()
    asyncio.run(go())


def test_failed_ai_marking_gives_the_tick_list_back(tmp_path, monkeypatch):  # B-014
    app, v = app_for(tmp_path, monkeypatch)
    from tutor_app import ai as ai_mod

    async def no_ai(*a, **k):
        return None, ai_mod.Result(ok=False, status="login", message="Sign in to use AI.")

    async def go():
        async with app.run_test(size=(120, 40)) as pilot:
            await pilot.pause()
            tick = await _open_long_and_submit(pilot, app, "my working")
            assert isinstance(tick, TickPanel)
            monkeypatch.setattr(app.ai, "one_shot", no_ai)
            ticks = tick.query_one("#ticks")
            first = ticks.get_option_at_index(0).value
            ticks.select(first)
            next(b for b in tick.query("Button") if b.id == "ai").press()
            for _ in range(20):
                await pilot.pause(0.05)
                panel = app.screen.query_one("#panel > *")
                if isinstance(panel, TickPanel) and panel is not tick:
                    break
            assert isinstance(panel, TickPanel) and panel.query_one("#ticks").selected == [first]
            panel.query("Button").first().press()
            await pilot.pause()
            evs = [e for e in app.tutor.vault.events() if e["type"] == "answer"]
            assert evs and 0 < evs[-1]["grade"]["score"] < 1
            await app.ai.close()
    asyncio.run(go())


def test_ai_replies_are_guarded_for_every_open_question(tmp_path, monkeypatch):  # B-031
    from tutor_app import ai as ai_mod, config, prompts
    from tutor_app.screens import SessionScreen
    from textual.widgets import Input
    monkeypatch.setattr(config, "ICLOUD_INBOX", tmp_path / "no-inbox")
    app, v = app_for(tmp_path, monkeypatch)

    async def go():
        async with app.run_test(size=(120, 40)) as pilot:
            await pilot.pause()
            scr = SessionScreen({"mode": "autopilot", "minutes": 50})
            app.push_screen(scr)
            await pilot.pause()
            t = app.tutor
            other = next(i for i in t.packs.items_for("9702-2.1.1") if i["kind"] == "mcq"
                         and str(scr.view and scr.view.get("item")) != i["id"])
            second = t._present(other, block="practice", phase=None)["n"]
            key, kind, answer = prompts.key_of(t, second)
            leak = f"The answer is {key}."
            assert ai_mod.leaks(leak, key, kind, answer)
            scr.submit({"entry": f"{scr.view['n']}?", "your": "I don't know"})  # answer the one on screen
            await pilot.pause()

            async def fake_stream(prompt):
                app.ai.last = ai_mod.Result(text=leak)
                yield leak
            monkeypatch.setattr(app.ai, "stream", fake_stream)
            scr.action_ask()
            await pilot.pause()
            app.screen.query_one("#q", Input).value = f"What is the answer to question {second}?"
            await pilot.press("enter")
            await pilot.pause(0.2)
            assert str(second) in t.session["presented"]
            assert leak not in (v / t.session["log"]).read_text()
            await app.ai.close()
    asyncio.run(go())


def test_asking_the_ai_is_refused_during_a_no_help_check(tmp_path, monkeypatch):  # B-033
    from tutor_app.screens import SessionScreen
    from textual.widgets import Input
    app, v = app_for(tmp_path, monkeypatch)
    calls = []

    async def fake_stream(prompt):
        calls.append(prompt)
        yield "Think about the units."

    async def go():
        async with app.run_test(size=(120, 40)) as pilot:
            await pilot.pause()
            scr = SessionScreen({"mode": "autopilot", "minutes": 50})
            app.push_screen(scr)
            await pilot.pause()
            t = app.tutor
            for n in list(t.session["presented"]):
                t.session["presented"][n]["unassisted"] = True  # an exit ticket
            monkeypatch.setattr(app.ai, "stream", fake_stream)
            scr.action_ask()
            await pilot.pause()
            app.screen.query_one("#q", Input).value = "Can I have a hint?"
            await pilot.press("enter")
            await pilot.pause(0.2)
            assert calls == [] and not any(p["hinted"] for p in t.session["presented"].values())
            await app.ai.close()
    asyncio.run(go())


def test_a_marked_answer_can_be_asked_about_before_the_next_no_help_question(tmp_path, monkeypatch):
    """Reported by the learner: in a test check the questions come two at a time; after the first was marked, asking
    about it was refused ("answer it first") because the second, not yet on screen, was still open."""
    from tutor_app.screens import SessionScreen
    from textual.widgets import Input
    app, v = app_for(tmp_path, monkeypatch)
    calls = []

    async def fake_stream(prompt):
        calls.append(prompt)
        yield "Because velocity has a direction."

    async def go():
        async with app.run_test(size=(120, 40)) as pilot:
            await pilot.pause()
            scr = SessionScreen({"mode": "test", "minutes": 40, "focus": ["9702-2.1"]})
            app.push_screen(scr)
            await pilot.pause()
            t = app.tutor
            first = scr.view["n"]
            assert t.session["presented"][str(first)]["unassisted"]  # a no-help check: one question per idea
            scr.submit({"entry": f"{first}?", "your": "I don't know"})
            await pilot.pause()
            monkeypatch.setattr(app.ai, "stream", fake_stream)
            scr.action_ask()
            await pilot.pause()
            app.screen.query_one("#q", Input).value = "Why is that the answer?"
            await pilot.press("enter")
            await pilot.pause(0.2)
            assert len(calls) == 1 and f"Just marked: Q{first}" in calls[0]
            assert "OPEN question" not in calls[0]  # the tutor is told nothing about a question you have not seen
            await app.ai.close()
    asyncio.run(go())


def test_the_menu_picks_up_chapters_published_while_the_app_is_open(tmp_path, monkeypatch):
    import copy, json, shutil
    from fixtures import GRAPH, PACK
    app, v = app_for(tmp_path, monkeypatch)
    graph = copy.deepcopy(GRAPH)
    graph["subtopics"].append({"id": "9702-2.2", "title": "Forces", "topic": "9702-2"})
    (v / ".tutor/packs/v1/specs/9702/graph.json").write_text(json.dumps(graph))

    async def go():
        async with app.run_test(size=(120, 40)) as pilot:
            await pilot.pause()
            packs = v / ".tutor" / "packs"
            shutil.copytree(packs / "v1", packs / "v2")  # the foundry signs a chapter and publishes it
            (packs / "v2/specs/9702/packs/9702-2.2.json").write_text(
                json.dumps({**copy.deepcopy(PACK), "subtopic": "9702-2.2", "items": [], "worked": []}))
            (packs / "CURRENT").write_text("v2")
            seen = []
            monkeypatch.setattr(app, "notify", lambda msg, **k: seen.append(msg))
            app.screen.refresh_home()
            assert app.tutor.packs.root.name == "v2" and any("Forces" in m for m in seen)
            await app.ai.close()
    asyncio.run(go())


def test_app_starts_when_macos_blocks_the_ipad_inbox(tmp_path, monkeypatch):
    from tutor_app import config
    inbox = tmp_path / "blocked-inbox"
    inbox.mkdir()
    (inbox / "work.pdf").write_text("X")
    inbox.chmod(0)
    monkeypatch.setattr(config, "ICLOUD_INBOX", inbox)
    app, v = app_for(tmp_path, monkeypatch)
    said = []
    monkeypatch.setattr(app, "notify", lambda msg, **kw: said.append(msg))

    async def go():
        async with app.run_test(size=(120, 40)) as pilot:
            await pilot.pause()
            assert app.screen.__class__.__name__ == "HomeScreen"
            assert any("iCloud Drive" in m for m in said)
            await app.ai.close()
    try:
        asyncio.run(go())
    finally:
        inbox.chmod(0o755)


def pin_clock(monkeypatch, iso="2026-09-29T17:00:00+08:00"):  # Almanac week 5; the app's clock ignores STEM_TUTOR_NOW
    from datetime import datetime
    from tutorlib import store
    monkeypatch.setattr(store.Vault, "now", lambda self: datetime.fromisoformat(iso))


def test_the_home_screen_shows_this_weeks_almanac_plan_and_starts_it(tmp_path, monkeypatch):
    pin_clock(monkeypatch)
    app, v = app_for(tmp_path, monkeypatch)

    async def go():
        async with app.run_test(size=(120, 40)) as pilot:
            await pilot.pause()
            home = app.screen
            stats = home.stats_text(app.tutor.now(), []).plain
            assert "Almanac week 5" in stats and "Kinematics" in stats and "ready" in stats
            assert "changed" not in stats
            today = (v / "Today.md").read_text()  # the plan is in Obsidian before any session
            assert "Almanac week 5" in today and f"Suggested {app.settings.minutes}-minute session" in today
            menu = home.query_one("#menu")
            assert menu.get_option_at_index(0).id == "today"
            home._start("today")
            await pilot.pause()
            assert app.screen.__class__.__name__ == "SessionScreen"
            assert app.tutor.session["mode"] == "autopilot" and "Today" in app.tutor.session["log"]
            await app.ai.close()
    asyncio.run(go())


def test_todays_plan_says_why_when_nothing_is_planned(tmp_path, monkeypatch):
    pin_clock(monkeypatch)
    from tutorlib import policy
    app, v = app_for(tmp_path, monkeypatch)
    said = []

    async def go():
        async with app.run_test(size=(120, 40)) as pilot:
            await pilot.pause()
            monkeypatch.setattr(policy, "plan_session", lambda *a, **k: [])
            monkeypatch.setattr(app, "notify", lambda msg, **kw: said.append(msg))
            app.screen._start("today")
            await pilot.pause()
            assert app.screen.__class__.__name__ == "HomeScreen" and any("Almanac" in m for m in said)
            await app.ai.close()
    asyncio.run(go())


def test_the_home_screen_says_when_the_almanac_changed_since_the_plan_was_built(tmp_path, monkeypatch):
    pin_clock(monkeypatch)
    import fixtures
    alm = tmp_path / "A-Levels.html"
    alm.write_text("<script>edited since</script>")
    monkeypatch.setattr(fixtures, "PLAN", {**fixtures.PLAN, "source_path": str(alm), "source_sha256": "0" * 64})
    app, v = app_for(tmp_path, monkeypatch)

    async def go():
        async with app.run_test(size=(120, 40)) as pilot:
            await pilot.pause()
            assert "Almanac has changed" in app.screen.stats_text(app.tutor.now(), []).plain
            await app.ai.close()
    asyncio.run(go())


def test_insights_screen_and_ai_summary(tmp_path, monkeypatch):
    import json
    pin_clock(monkeypatch)
    app, v = app_for(tmp_path, monkeypatch)

    async def go():
        async with app.run_test(size=(120, 40)) as pilot:
            await pilot.pause()
            menu = app.screen.query_one("#menu")
            ids = [menu.get_option_at_index(i).id for i in range(menu.option_count)]
            assert "insights" in ids and "weak" in ids
            app.screen._start("insights")
            await pilot.pause()
            assert app.screen.__class__.__name__ == "InsightsScreen"
            await pilot.press("a")
            saved = v / ".tutor" / "profile_ai.json"
            for _ in range(60):
                await pilot.pause(0.05)
                if saved.exists():
                    break
            assert "Going well" in json.loads(saved.read_text())["text"]
            assert "## AI summary" in (v / "Profile.md").read_text()
            await app.ai.close()
    asyncio.run(go())


def test_fix_my_weak_spots_says_so_when_there_are_none_and_starts_when_there_are(tmp_path, monkeypatch):
    pin_clock(monkeypatch)
    app, v = app_for(tmp_path, monkeypatch)
    said = []

    async def go():
        async with app.run_test(size=(120, 40)) as pilot:
            await pilot.pause()
            monkeypatch.setattr(app, "notify", lambda msg, **kw: said.append(msg))
            app.screen._start("weak")
            await pilot.pause()
            assert app.screen.__class__.__name__ == "HomeScreen" and any("No weak spots" in m for m in said)
            app.tutor.log({"type": "gaps", "add": ["9702-2.1.4"]})
            app.screen._start("weak")
            await pilot.pause()
            assert app.screen.__class__.__name__ == "SessionScreen" and app.tutor.session["mode"] == "weak"
            assert "Weak spots" in app.tutor.session["log"]
            await app.ai.close()
    asyncio.run(go())


def test_the_week_in_review_is_written_once_in_a_new_week(tmp_path, monkeypatch):
    from datetime import datetime
    from tutorlib import store
    pin_clock(monkeypatch, "2026-10-06T09:00:00+08:00")  # Tuesday of the week after
    app, v = app_for(tmp_path, monkeypatch)
    store.Vault(v).append_event({"type": "answer", "session": "s0", "item": "9702-2.1-i01", "kcs": ["9702-2.1.1"],
                                 "subject": "phys", "difficulty": 2, "conf": 3, "hinted": False, "seconds": 30,
                                 "marks": 1, "grade": {"correct": True, "score": 1.0, "error": None,
                                                       "misconception": None}, "credit": [], "pos": 0,
                                 "block": "review", "phase": None, "params": None, "response": "B"},
                                now=datetime.fromisoformat("2026-09-30T18:00:00+08:00"))
    said = []
    monkeypatch.setattr(app, "notify", lambda msg, **kw: said.append(msg))

    async def go():
        async with app.run_test(size=(120, 40)) as pilot:
            await pilot.pause()
            assert (v / "Weekly" / "2026-W40.md").exists() and any("week in review" in m for m in said)
            assert app.screen._week_in_review() is None  # only once
            await app.ai.close()
    asyncio.run(go())
