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
            await pilot.pause(0.75)  # the summary ignores a ⏎ that arrives with it (key repeat from "Next ⏎")
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
            assert app.screen.__class__.__name__ == "ConfirmScreen"  # "4" is typed in the box: asked before it is lost
            await pilot.press("enter")  # Leave
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
            app.screen.query_one("#q").text = f"What is the answer to question {second}?"
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
            app.screen.query_one("#q").text = "Can I have a hint?"
            await pilot.press("enter")
            await pilot.pause(0.2)
            assert calls == [] and not any(p["hinted"] for p in t.session["presented"].values())
            await app.ai.close()
    asyncio.run(go())


def test_only_help_that_arrives_counts_as_a_hint(tmp_path, monkeypatch):  # B-039
    from tutor_app import ai as ai_mod, prompts
    from tutor_app.screens import SessionScreen
    app, v = app_for(tmp_path, monkeypatch)

    async def go():
        async with app.run_test(size=(120, 40)) as pilot:
            await pilot.pause()
            scr = SessionScreen({"mode": "autopilot", "minutes": 50})  # opens with a pretest: hints are allowed
            app.push_screen(scr)
            await pilot.pause()
            t = app.tutor
            p = t.session["presented"][str(scr.view["n"])]
            key = prompts.key_of(t, scr.view["n"])[0]

            def reply(result, text=""):
                async def fake_stream(prompt):
                    app.ai.last = result
                    for chunk in [text] if text else []:
                        yield chunk
                monkeypatch.setattr(app.ai, "stream", fake_stream)

            async def ask():
                scr.stream("Give me a hint")
                await app.workers.wait_for_complete()
                await pilot.pause()

            reply(ai_mod.Result(ok=False, status="login", message="Sign in first."))
            await ask()
            assert not p["hinted"]  # the AI was signed out: nothing was said, so the answer is still your own
            reply(ai_mod.Result(text=f"The answer is {key}."), f"The answer is {key}.")
            await ask()
            assert not p["hinted"]  # the reply gave the answer away and was withheld: again no help reached you
            reply(ai_mod.Result(text="Think about direction."), "Think about direction.")
            await ask()
            assert p["hinted"]  # a hint you could read counts, whoever gives it
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
            app.screen.query_one("#q").text = "Why is that the answer?"
            await pilot.press("enter")
            await pilot.pause(0.2)
            assert len(calls) == 1 and f"Marked earlier in this session, Q{first}" in calls[0]
            assert "OPEN question" not in calls[0]  # the tutor is told nothing about a question you have not seen
            await app.ai.close()
    asyncio.run(go())


def test_at_half_a_screen_everything_lines_up_and_fits(tmp_path, monkeypatch):
    """Reported by the learner: with the window at half the screen the right side broke up and boxes did not line up.
    The "Ask the tutor" button also took the Ask pop-up's style (they share the id `ask`), 90 columns wide, so it ran
    off the edge; the log's scrollbar sat one column in from the edge; cards and answer boxes ended a column apart."""
    from tutor_app.screens import SessionScreen
    from textual.widgets import Button, Input, OptionList
    app, v = app_for(tmp_path, monkeypatch)

    async def go():
        async with app.run_test(size=(140, 46)) as pilot:
            await pilot.pause()
            scr = SessionScreen({"mode": "test", "minutes": 40, "focus": ["9702-2.1"]})
            app.push_screen(scr)
            await pilot.pause()
            await pilot.resize_terminal(100, 24)  # the window dragged to half the screen, mid-session
            await pilot.pause()
            log = scr.query_one("#log")

            def card_edge():
                return {(e.region.x, e.region.right) for e in log.query(".entry") if e.display}  # not what a question put away

            from tutor_app.panels import Composer
            for kind in (OptionList, Composer):  # a multiple-choice question, then a typed one
                boxes = [w for w in scr.query("#panel OptionList, #panel Input, #panel Composer") if w.display]
                assert any(isinstance(w, kind) for w in boxes)
                assert {(w.region.x, w.region.right) for w in boxes} == card_edge()  # answer boxes end where cards end
                scr.submit({"entry": f"{scr.view['n']}?", "your": "I don't know"})
                await pilot.pause()
                buttons = list(scr.query("#panel Button"))
                assert [b.id for b in buttons] in (["next", "why", "ask"], ["next", "why", "remark", "ask"])
                assert {(b.region.y, b.region.height) for b in buttons} == {(buttons[0].region.y, 1)}  # one row of
                # buttons, one line high: a window 24 rows high keeps its room for the log
                assert all(b.region.width <= max(16, len(str(b.label)) + 4) and b.region.right <= 100 for b in buttons)
                assert len(card_edge()) == 1
                scr.tutor.respond({})
                scr.advance()
                await pilot.pause()
            for _ in range(12):  # the compact panel leaves the log room: fill it until it scrolls
                scr.say("more")
            await pilot.pause()
            assert log.show_vertical_scrollbar and log.vertical_scrollbar.region.right == 100  # flush with the edge
            await app.ai.close()
    asyncio.run(go())


def test_a_resize_clears_what_the_terminal_kept_beyond_the_new_edge(tmp_path, monkeypatch):
    """Reported by the learner, and seen in their Terminal: after the window is made narrower, Terminal keeps what was
    drawn beyond the new right edge and shows it in the strip beside its own scrollbar (old borders, pieces of
    scrollbar, letters). The app can only draw inside the window, so it clears the display, then redraws."""
    app, v = app_for(tmp_path, monkeypatch)

    async def go():
        async with app.run_test(size=(140, 46)) as pilot:
            await pilot.pause()
            written, repaints = [], []
            monkeypatch.setattr(app._driver, "write", written.append)
            monkeypatch.setattr(app.screen, "refresh", lambda *a, **k: repaints.append(1))
            await pilot.resize_terminal(120, 46)
            await pilot.pause()
            r, g, b = app.screen.styles.background.rgb
            assert f"\x1b[48;2;{r};{g};{b}m\x1b[2J\x1b[0m" in written  # cleared in the screen's own colour
            assert repaints  # and everything is drawn again
            await app.ai.close()
    asyncio.run(go())


def test_the_home_screens_side_box_fits_and_scrolls(tmp_path, monkeypatch):
    """With 22 chapters the box of dates and topics ran off the bottom of the window: its bottom edge was gone, and
    the AI line and the version under the topics could not be reached. (A window under 30 rows drops the banner, so
    the test window is made short enough for the fixture's one chapter to overflow the box.)"""
    app, v = app_for(tmp_path, monkeypatch)

    async def go():
        async with app.run_test(size=(100, 17)) as pilot:  # 17: the box lost its blank first row (lines up with the menu)
            await pilot.pause()
            box, home = app.screen.query_one("#stats"), app.screen.query_one("#home")
            assert box.region.bottom <= home.region.bottom  # the whole box, bottom edge included, is on screen
            assert box.max_scroll_y > 0  # and what does not fit can be scrolled to
            await app.ai.close()
    asyncio.run(go())


def test_a_buttons_id_never_borrows_a_layout_style(tmp_path, monkeypatch):
    """Buttons are named for what they do (`ask`, `home`); the same names style the Ask pop-up and the home screen."""
    from tutor_app.panels import ContinuePanel
    from tutor_app.screens import SessionScreen
    from textual.widgets import Button
    app, v = app_for(tmp_path, monkeypatch)

    async def go():
        async with app.run_test(size=(120, 40)) as pilot:
            await pilot.pause()
            scr = SessionScreen({"mode": "test", "minutes": 40, "focus": ["9702-2.1"]})
            app.push_screen(scr)
            await pilot.pause()
            scr.panel(ContinuePanel(buttons=[("home", "Back to menu ⏎"), ("ask", "Ask the tutor (ctrl+t)")]))
            await pilot.pause()
            assert [(b.region.height, b.region.width <= 30) for b in scr.query("#panel Button")] == [(3, True)] * 2
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


def test_home_counts_almanac_ticks_and_follows_you_ahead(tmp_path, monkeypatch):
    """Asked by the learner: the home screen showed the calendar week whatever they had ticked in the Almanac, and
    Today's plan taught ticked objectives again. An export left in Downloads is read when the tutor opens."""
    import json
    from tutor_app import config
    pin_clock(monkeypatch)
    app, v = app_for(tmp_path, monkeypatch)
    plan_file = v / ".tutor/packs/v1/plan.json"
    plan = json.loads(plan_file.read_text())
    plan["weeks"]["6"] = [{"id": "6-phys1", "subject": "phys", "title": "Dynamics", "kcs": [], "type": "NEW"}]
    plan_file.write_text(json.dumps(plan))
    config.DOWNLOADS.mkdir()
    (config.DOWNLOADS / "almanac-progress-2026-09-29.json").write_text(json.dumps({"done": {"5-phys1": 1}}))

    async def go():
        async with app.run_test(size=(120, 40)) as pilot:
            await pilot.pause()
            home = app.screen
            assert not list(config.DOWNLOADS.iterdir())  # the export was moved into the vault
            assert (v / "Almanac/almanac-progress-2026-09-29.json").exists()
            stats = home.stats_text(app.tutor.now(), []).plain
            assert "Almanac week 6" in stats and "Dynamics" in stats and "ahead" in stats
            assert "week 6" in str(home.query_one("#menu").get_option("today").prompt)
            assert "Almanac week 6" in (v / "Today.md").read_text()
            home._start("today")
            await pilot.pause()
            blocks = app.tutor.session["blocks"]
            assert blocks[0].get("claimed") and not [b for b in blocks if b["kind"] == "learn"]
            await app.ai.close()
    asyncio.run(go())


def test_home_says_how_to_make_ticks_count_until_an_export_has_been_read(tmp_path, monkeypatch):
    pin_clock(monkeypatch)
    app, v = app_for(tmp_path, monkeypatch)

    async def go():
        async with app.run_test(size=(120, 40)) as pilot:
            await pilot.pause()
            assert "Export" in app.screen.stats_text(app.tutor.now(), []).plain
            (v / "Almanac").mkdir(exist_ok=True)
            (v / "Almanac/almanac-progress-2026-09-29.json").write_text('{"done": {}}')
            stats = app.screen.stats_text(app.tutor.now(), []).plain
            assert "Ticks read from your export" in stats and "press Export" not in stats
            await app.ai.close()
    asyncio.run(go())


def test_the_tutor_keeps_the_almanacs_file_up_to_date_and_has_no_reply_cap(tmp_path, monkeypatch):
    import json
    pin_clock(monkeypatch)
    app, v = app_for(tmp_path, monkeypatch)
    planner = tmp_path / "A-Levels.html"
    planner.write_text("<html></html>")
    plan_file = v / ".tutor/packs/v1/plan.json"
    plan_file.write_text(json.dumps({**json.loads(plan_file.read_text()), "source_path": str(planner)}))

    async def go():
        async with app.run_test(size=(120, 40)) as pilot:
            await pilot.pause()
            assert '"phys-2"' in (tmp_path / "A-Levels.tutor.js").read_text()  # written as the tutor opens
            app.action_settings()
            await pilot.pause()
            assert app.screen.__class__.__name__ == "SettingsScreen" and not app.screen.query("#cap")
            await app.ai.close()
    asyncio.run(go())


def test_a_question_is_answered_from_memory_on_the_terminal_side_too(tmp_path, monkeypatch):
    """Asked by the learner: the Now page hides the explanation once a question about it is asked, but the terminal
    still showed everything said before, so the answer could simply be read off the screen."""
    from tutor_app.screens import SessionScreen
    app, v = app_for(tmp_path, monkeypatch)

    async def go():
        async with app.run_test(size=(120, 40)) as pilot:
            await pilot.pause()
            app.push_screen(SessionScreen({"mode": "lesson", "focus": ["9702-2.1"], "minutes": 40}))
            panel = None
            for _ in range(30):  # as far as the first question
                await pilot.pause()
                panel = next(iter(app.screen.query("#panel > *")), None)
                if isinstance(panel, (ChoicePanel, ValuePanel)):
                    break
                if isinstance(panel, ChoosePanel):
                    await pilot.press("down", "enter")
                elif isinstance(panel, (ContinuePanel, TickPanel)):
                    panel.query("Button").first().press()
            scr = app.screen
            before = [w for w in scr.query("#log > .entry") if not w.display]
            assert before and len([w for w in scr.query("#log > .entry") if w.display]) <= 2  # the question alone
            await pilot.press("ctrl+l")
            await pilot.pause()
            assert not any(w.display for w in before)  # not while the question is open
            if isinstance(panel, ChoicePanel):
                await pilot.press("b")
                await pilot.pause()
                await pilot.press("3")
            else:
                await pilot.press(*"42", "enter")
                await pilot.pause()
                await pilot.press("2")
            await pilot.pause()
            await pilot.press("ctrl+l")
            await pilot.pause()
            assert all(w.display for w in before)  # after answering, on request
            await app.ai.close()
    asyncio.run(go())


def test_the_ask_box_takes_several_lines_and_sends_on_enter(tmp_path, monkeypatch):
    """Asked by the learner: the input was one short line."""
    from tutor_app.panels import Composer
    from tutor_app.screens import AskScreen
    app, v = app_for(tmp_path, monkeypatch)
    got = []

    async def go():
        async with app.run_test(size=(100, 30)) as pilot:
            await pilot.pause()
            app.push_screen(AskScreen(), got.append)
            await pilot.pause()
            box = app.screen.query_one("#q", Composer)
            short = box.size.height
            await pilot.press(*"why", "ctrl+j", *"is")
            box.insert(" this so " * 40)  # a long question wraps instead of sliding off to the right
            await pilot.pause()
            assert "\n" in box.text and box.size.height > short and box.size.width <= 90
            await pilot.press("enter")
            await pilot.pause()
            await app.ai.close()
    asyncio.run(go())
    assert got and got[0].startswith("why\nis this so")


def test_the_top_bar_goes_whole_onto_a_second_line_when_the_window_is_narrow(tmp_path, monkeypatch):
    """Asked by the learner: when the top bar does not fit, show all of it on at most two lines, broken cleanly."""
    from rich.cells import cell_len
    from tutor_app.screens import SessionScreen
    app, v = app_for(tmp_path, monkeypatch)

    async def go():
        async with app.run_test(size=(140, 40)) as pilot:
            await pilot.pause()
            app.push_screen(SessionScreen({"mode": "lesson", "focus": ["9702-2.1"], "minutes": 40}))
            await pilot.pause()
            scr = app.screen
            wide = scr.bar_text(140).plain
            assert "\n" not in wide and "STEM Tutor" in wide and "replies" in wide and "5h" not in wide
            narrow = scr.bar_text(60).plain.split("\n")
            assert len(narrow) == 2 and "STEM Tutor" in narrow[0] and "Lesson" in narrow[0]
            assert "◷" in narrow[1] and "✓" in narrow[1] and "replies" in narrow[1] and "tok" not in narrow[1]
            assert all(cell_len(line) <= 60 for line in narrow)
            tiny = scr.bar_text(30).plain.split("\n")
            assert len(tiny) == 2 and all(cell_len(line) <= 30 for line in tiny) and tiny[0].endswith("…")
            assert scr.query_one("#bar").region.height == 1
            await pilot.resize_terminal(60, 40)
            await pilot.pause()
            scr.update_bar()
            await pilot.pause()
            assert scr.query_one("#bar").region.height == 2
            await app.ai.close()
    asyncio.run(go())


async def _to_a_wrong_typed_answer(app, pilot) -> list:
    """Answer the test check until a typed answer has been marked wrong; returns the button rows seen on the way."""
    from textual.widgets import Button
    offered = []
    for _ in range(14):
        await pilot.pause()
        panel = next(iter(app.screen.query("#panel > *")), None)
        if isinstance(panel, ChoicePanel):
            await pilot.press("0")  # I don't know
        elif isinstance(panel, ValuePanel):
            await pilot.press(*"42", "space", "m", "enter")
            await pilot.pause()
            await pilot.press("2")
        elif isinstance(panel, ContinuePanel):
            offered.append([b.id for b in panel.query(Button)])
            if "remark" in offered[-1]:
                break
            panel.query_one("#next", Button).press()
    return offered


def test_an_answer_marked_wrong_can_be_re_marked_by_the_ai(tmp_path, monkeypatch):
    """Asked by the learner: an option for the AI to mark an answer the program marked wrong."""
    from textual.widgets import Button
    from tutor_app import ai as ai_mod
    from tutor_app.panels import Composer
    from tutor_app.screens import SessionScreen
    app, v = app_for(tmp_path, monkeypatch)
    asked = []

    async def second_marker(prompt, schema=None, model=None):
        asked.append((prompt, model))
        return {"correct": True, "why": "The same quantity."}, ai_mod.Result()

    async def go():
        async with app.run_test(size=(80, 24)) as pilot:
            await pilot.pause()
            app.push_screen(SessionScreen({"mode": "test", "focus": ["9702-2.1"], "minutes": 30}))
            for _ in range(5):
                await pilot.pause()
            panel = app.screen.query_one(ChoicePanel)
            assert isinstance(panel.query_one("#note"), Composer)  # every box for typing wraps and grows
            await pilot.press("tab", "a", "enter")  # a letter in the note is not a choice; ⏎ goes back to the list
            assert panel._note() == "a" and panel.choice is None and app.focused.id == "choices"
            offered = await _to_a_wrong_typed_answer(app, pilot)
            row = list(app.screen.query("#panel Button"))
            assert offered[0] == ["next", "why", "ask"]  # nothing to re-mark in "I don't know"
            assert offered[-1] == ["next", "why", "remark", "ask"]
            assert all(b.region.right <= app.size.width and b.region.width >= len(str(b.label)) + 2 for b in row)
            assert len({b.region.y for b in row}) == 2  # too many for 80 columns: the last goes to a second row, whole
            await pilot.resize_terminal(120, 40)
            await pilot.pause()
            row = list(app.screen.query("#panel Button"))
            assert len({b.region.y for b in row}) == 1 and app.focused.id == "next"  # and back to one row when it fits
            monkeypatch.setattr(app.ai, "one_shot", second_marker)
            answered, correct = app.tutor.session["answered"], app.tutor.session["correct"]
            app.screen.query_one("#remark", Button).press()
            for _ in range(5):
                await pilot.pause(0.05)
            assert (app.tutor.session["answered"], app.tutor.session["correct"]) == (answered, correct + 1)
            assert "MARK SCHEME ANSWER" in asked[0][0] and "42 m" in asked[0][0] and asked[0][1] == "sonnet"
            assert "remark" not in [b.id for b in app.screen.query("#panel Button")]  # one re-mark an answer
            await app.ai.close()
    asyncio.run(go())


def test_when_the_mark_stands_the_reason_is_asked_after(tmp_path, monkeypatch):
    """From "Why did you miss it?", 6 sends the answer to the AI examiner. If the mark stands, the reason is asked
    again without that option, and the answer cannot be sent a second time."""
    from tutor_app import ai as ai_mod
    from tutor_app.screens import SessionScreen
    app, v = app_for(tmp_path, monkeypatch)

    async def second_marker(prompt, schema=None, model=None):
        return {"correct": False, "why": "42 m is not the distance."}, ai_mod.Result()

    async def go():
        async with app.run_test(size=(100, 30)) as pilot:
            await pilot.pause()
            app.push_screen(SessionScreen({"mode": "test", "focus": ["9702-2.1"], "minutes": 30}))
            await _to_a_wrong_typed_answer(app, pilot)
            scr = app.screen
            monkeypatch.setattr(app.ai, "one_shot", second_marker)
            correct = app.tutor.session["correct"]
            scr.followups = ["reflect"]  # as after a miss outside the quick check
            scr.next_followup()
            await pilot.pause()
            assert scr.query_one("#reflect").option_count == 6
            await pilot.press("6")
            for _ in range(5):
                await pilot.pause(0.05)
            assert app.tutor.session["correct"] == correct and scr.query_one("#reflect").option_count == 5
            await pilot.press("1")
            await pilot.pause()
            assert [b.id for b in scr.query("#panel Button")] == ["next", "why", "ask"]
            assert [e["error"] for e in app.tutor.vault.events() if e["type"] == "tag"] == ["SLIP"]
            await app.ai.close()
    asyncio.run(go())


def test_the_why_did_you_miss_it_step_offers_the_re_mark():
    """That step comes before the buttons: "it was right" has to be sayable there, not after naming a reason."""
    from textual import on
    from textual.app import App
    from tutor_app.panels import Panel, ReflectPanel
    got = []

    class Host(App):
        def compose(self):
            yield ReflectPanel(remark=True)

        @on(Panel.Done)
        def done(self, event):
            got.append(event.data)

    async def go():
        async with Host().run_test() as pilot:
            await pilot.pause()
            assert pilot.app.query_one("#reflect").option_count == 6
            await pilot.press("6")
            await pilot.pause()
    asyncio.run(go())
    assert got == [{"code": None, "remark": True}]


def test_a_teaching_card_that_cannot_be_cached_does_not_end_the_app(tmp_path, monkeypatch):
    from tutor_app import config
    from tutor_app.screens import SessionScreen
    monkeypatch.setattr(config, "ICLOUD_INBOX", tmp_path / "no-inbox")
    app, v = app_for(tmp_path, monkeypatch)
    teach = v / ".tutor" / "cache" / "teach"
    teach.mkdir(parents=True)
    teach.chmod(0o555)  # a vault folder that cannot be written (read-only mount, iCloud lock)

    async def go():
        async with app.run_test(size=(120, 40)) as pilot:
            await pilot.pause()
            scr = SessionScreen({"mode": "autopilot", "minutes": 50})
            app.push_screen(scr)
            await pilot.pause()
            worker = scr._write_cards([next(iter(app.tutor.packs.kcs))])
            await worker.wait()  # raises WorkerFailed if the write error escaped
            await app.ai.close()
    try:
        asyncio.run(go())
    finally:
        teach.chmod(0o755)
