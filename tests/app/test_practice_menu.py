"""The grouped home menu, the merged Practice flow, the old ids, and the "Can I solve this?" card."""
import asyncio

from textual.widgets import Button, Input, OptionList, SelectionList, Static, Switch

from test_tui import app_for
from test_topical_setup import staged_app
from test_topicals import TARGET, OTHER, THIRD
from tutor_app import home_menu
from tutor_app.screens import HomeScreen, PickerScreen, SessionScreen


def ids(menu):
    return [menu.get_option_at_index(i).id for i in range(menu.option_count)]


def log_text(screen, selector="#log Static"):
    """The words of every card in the log, as the terminal prints them."""
    from io import StringIO
    from rich.console import Console
    out = StringIO()
    console = Console(file=out, width=110, force_terminal=False)
    for widget in screen.query(selector):
        console.print(widget.content)
    return out.getvalue()


def run(app, size, steps):
    async def go():
        async with app.run_test(size=size) as pilot:
            await pilot.pause()
            await app.workers.wait_for_complete()
            await pilot.pause()
            await steps(pilot)
            await app.ai.close()
    asyncio.run(go())


# ---------- grouping ----------
def test_the_menu_opens_on_four_folders_and_each_folder_holds_its_entries(tmp_path, monkeypatch):
    app, _ = app_for(tmp_path, monkeypatch)

    async def steps(pilot):
        home = app.screen
        menu = home.query_one("#menu")
        assert [i for i in ids(menu) if i != "time"] == ["dir:learn", "dir:questions", "dir:profile", "dir:tools"]
        wanted = {"learn": ["today", "learn", "review", "weak", "long", "blurt"],
                  "questions": ["practice", "challenge", "shortcuts", "shortcut_recall"],
                  "profile": ["insights", "progress", "obsidian"],
                  "tools": ["chat", "settings", "help", "quit"]}
        for folder, entries in wanted.items():
            home.open_folder(folder)
            await pilot.pause()
            assert ids(menu) == ["back"] + entries and menu.border_title
        home.open_folder(None)
        # the three older entries are not listed anywhere
        listed = {k for fid, _, es in home_menu.arrange(dict(home._menu_items)) for k in es}
        assert not listed & {"test", "topical", "source-practice"}
    run(app, (100, 40), steps)


def test_enter_opens_a_folder_escape_and_backspace_go_back_and_the_place_is_kept(tmp_path, monkeypatch):
    app, _ = app_for(tmp_path, monkeypatch)

    async def steps(pilot):
        home = app.screen
        menu = home.query_one("#menu")
        await pilot.press("down", "enter")  # Questions
        await pilot.pause()
        assert home.folder == "questions" and ids(menu)[0] == "back"
        await pilot.press("down", "down")  # Practice, Challenge, Shortcuts
        await pilot.press("escape")
        await pilot.pause()
        assert home.folder is None and menu.get_option_at_index(menu.highlighted).id == "dir:questions"
        await pilot.press("enter")
        await pilot.pause()
        assert menu.get_option_at_index(menu.highlighted).id == "shortcuts"  # back where you were in that folder
        await pilot.press("backspace")
        await pilot.pause()
        assert home.folder is None
        await pilot.press("enter")
        await pilot.press("0")  # 0 is back
        await pilot.pause()
        assert home.folder is None
    run(app, (100, 40), steps)


def test_number_keys_choose_the_nth_line_and_the_folder_is_remembered_after_a_session_screen(tmp_path, monkeypatch):
    app, _ = app_for(tmp_path, monkeypatch)

    async def steps(pilot):
        home = app.screen
        menu = home.query_one("#menu")
        await pilot.press("p")  # type-ahead: the line that starts with p
        assert menu.get_option_at_index(menu.highlighted).id == "dir:profile"
        await pilot.press("t")
        assert menu.get_option_at_index(menu.highlighted).id == "dir:tools"
        await pilot.press("4")  # Tools
        await pilot.pause()
        assert home.folder == "tools"
        await pilot.press("1")  # Ask the tutor anything
        await pilot.pause()
        assert app.screen.__class__.__name__ == "ChatScreen"
        app.pop_screen()
        await pilot.pause()
        assert app.screen is home and home.folder == "tools"
        menu = home.query_one("#menu")
        assert menu.get_option_at_index(menu.highlighted).id == "chat"
    run(app, (100, 40), steps)


def test_the_grouped_menu_fits_a_short_window_and_a_narrow_one(tmp_path, monkeypatch):
    app, _ = app_for(tmp_path, monkeypatch)

    async def steps(pilot):
        home = app.screen
        for size in ((60, 20), (80, 24), (100, 28), (140, 40)):
            await pilot.resize_terminal(*size)
            await pilot.pause()
            for folder in (None, "learn", "questions", "profile", "tools"):
                home.open_folder(folder)
                await pilot.pause()
                menu = home.query_one("#menu")
                assert menu.region.right <= size[0] and menu.max_scroll_y == 0, (size, folder)
        home.open_folder(None)
    run(app, (100, 40), steps)


def test_the_old_ids_still_start_what_they_started(tmp_path, monkeypatch):
    app, _ = staged_app(tmp_path, monkeypatch)
    seen = []

    async def steps(pilot):
        home = app.screen
        for key in ("test", "topical"):
            home.activate(key)
            await pilot.pause()
            assert isinstance(app.screen, PickerScreen) and app.screen.mode == key
            app.screen.dismiss(None)
            await pilot.pause()
        home.activate("source-practice")
        await pilot.pause()
        seen.append(app.screen.__class__.__name__)
        app.pop_screen()
        await pilot.pause()
        # an old alias is revealed on the entry that replaced it
        home.query_one("#menu").reveal("test")
        assert home.folder == "questions"
        assert home.query_one("#menu").get_option_at_index(home.query_one("#menu").highlighted).id == "practice"
    run(app, (100, 40), steps)
    assert seen == ["SourcePracticeScreen"]


# ---------- the merged Practice flow ----------
def test_practice_picks_a_whole_course_then_options_then_starts_one_session(tmp_path, monkeypatch):
    app, _ = staged_app(tmp_path, monkeypatch)
    monkeypatch.setattr(SessionScreen, "_start_session", lambda self: None)  # the engine's own start is not under test

    async def steps(pilot):
        home = app.screen
        home.activate("practice")
        await pilot.pause()
        picker = app.screen
        assert isinstance(picker, PickerScreen) and picker.mode == "practice"
        # the course is auto-opened when it is the only one; inside it, "Entire course" ticks everything
        first = picker.query_one("#subs")
        top = ids(first)
        assert any(i.startswith("all:") for i in top) or any(i.startswith("dir:") for i in top)
        if not any(i.startswith("all:") for i in top):
            await pilot.press("enter")
            await pilot.pause()
        picker.query_one("#subs").highlighted = ids(picker.query_one("#subs")).index(
            next(i for i in ids(picker.query_one("#subs")) if i.startswith("all:")))
        await pilot.press("space")
        assert picker.ticked == set(picker.built) and picker.ticked
        await pilot.press("ctrl+s")
        await pilot.pause()
        setup = app.screen
        assert type(setup).__name__ == "PracticeSetupScreen"
        await app.workers.wait_for_complete()
        await pilot.pause()
        assert setup.scope == "course" and setup.course == "9702"
        sources = setup.query_one("#practice-sources", SelectionList)
        assert set(sources.selected) == {"topical", "source_verified"}  # both by default
        setup.query_one("#practice-count", Input).value = "7"
        setup.query_one("#practice-unstarted", Switch).value = True
        await app.workers.wait_for_complete()
        await pilot.pause()
        start = setup.query_one("#practice-start", Button)
        assert not start.disabled
        start.press()
        await pilot.pause()
        session = app.screen
        assert isinstance(session, SessionScreen)
        args = session.start_args
        assert args["mode"] == "practice" and args["scope"] == "course" and args["course"] == "9702"
        assert args["count"] == 7 and args["sources"] == ["topical", "source_verified"]
        assert set(args["focus"]) == set(picker.built) and args["include_unstarted"] is True
        assert args["difficulty"] == "mixed"
    run(app, (100, 40), steps)


def test_practice_needs_a_source_and_a_valid_count(tmp_path, monkeypatch):
    app, _ = staged_app(tmp_path, monkeypatch)

    async def steps(pilot):
        from tutor_app.practice_screens import PracticeSetupScreen
        app.push_screen(PracticeSetupScreen([TARGET, OTHER], "chapters", "9702"))
        await pilot.pause()
        await app.workers.wait_for_complete()
        await pilot.pause()
        setup = app.screen
        start = setup.query_one("#practice-start", Button)
        assert not start.disabled
        for value, ok in (("0", False), ("201", False), ("x", False), ("5", True)):
            setup.query_one("#practice-count", Input).value = value
            await pilot.pause()
            assert start.disabled == (not ok), value
        sources = setup.query_one("#practice-sources", SelectionList)
        sources.deselect_all()
        await pilot.pause()
        assert start.disabled and "source" in str(setup.query_one("#practice-availability").content)
    run(app, (100, 40), steps)


def test_scope_is_course_for_everything_module_for_a_whole_topic_and_chapters_otherwise(tmp_path, monkeypatch):
    app, _ = staged_app(tmp_path, monkeypatch)
    from tutor_app.practice_screens import classify

    async def steps(pilot):
        packs = app.tutor.packs
        every = list(packs.subtopics)
        assert classify(packs, every, every) == ("course", "9702")
        assert classify(packs, [TARGET, OTHER], every) == ("chapters", "9702")
        topic = packs.subtopics[TARGET]["topic"]
        whole_topic = [s for s in every if packs.subtopics[s]["topic"] == topic]
        assert classify(packs, whole_topic, every)[0] in ("module", "course")
        assert classify(packs, [], every) == ("chapters", None)
    run(app, (100, 40), steps)


def test_session_start_options_degrade_to_what_the_engine_accepts(tmp_path, monkeypatch):
    app, _ = app_for(tmp_path, monkeypatch)
    screen = SessionScreen({"mode": "practice", "focus": ["9702-2.1"], "scope": "chapters", "course": "9702",
                            "sources": ["topical"], "count": 3, "difficulty": "mixed"})

    class Old:
        def start(self, mode, minutes, focus, replace=False, *, topical_count=None):
            pass

    class New:
        def start(self, mode, minutes, focus, replace=False, **options):
            pass

    assert screen._start_options(Old()) == {}
    assert screen._start_options(New()) == {"scope": "chapters", "course": "9702", "sources": ["topical"],
                                            "count": 3, "difficulty": "mixed"}


def test_setup_option_names_are_mapped_onto_the_real_engine_start(tmp_path, monkeypatch):
    """include_unstarted/auto_mark are the setup screen's words; the engine's are started_only/topical_auto_mark.
    Dropping them silently would ignore a learner who turns "chapters not yet started" off."""
    import types
    from tutorlib.session import Tutor
    app, _ = app_for(tmp_path, monkeypatch)
    screen = SessionScreen({"mode": "practice", "focus": ["9702-2.1"], "scope": "chapters", "course": "9702",
                            "sources": ["topical", "source_verified"], "count": 5, "difficulty": "mixed",
                            "include_unstarted": False, "auto_mark": True})
    got = screen._start_options(types.SimpleNamespace(start=Tutor.start))
    assert got["started_only"] is True and got["topical_auto_mark"] is True
    assert got["sources"] == ["topical", "source_verified"] and got["count"] == 5
    assert "include_unstarted" not in got and "difficulty" not in got  # engine has no such keywords yet


# ---------- Can I solve this? ----------
def test_solvable_card_shows_given_missing_and_the_adapted_prompt_in_the_question(tmp_path, monkeypatch):
    app, _ = app_for(tmp_path, monkeypatch)

    async def steps(pilot):
        scr = SessionScreen({"mode": "test", "minutes": 20, "focus": ["9702-2.1"]})
        app.push_screen(scr)
        await pilot.pause()
        n = scr.view["n"]
        monkeypatch.setattr(app.tutor, "check_solvable", lambda k: {
            "n": k, "status": "adapted", "message": "You can do parts (a) and (b).", "missing": ["9702-3.1 Dynamics"],
            "given": ["g = 9.81 N per kg", "v = u + at"], "adapted_prompt": "Answer parts (a) and (b) only.",
            "topic": ["Equations of motion"], "skipped": False})
        scr.query_one("#check-solvable", Button).press()
        await app.workers.wait_for_complete()
        await pilot.pause()
        text = log_text(scr)
        assert "You can do parts (a) and (b)." in text
        assert "g = 9.81 N per kg" in text and "Given:" in text
        assert "9702-3.1 Dynamics" in text and "Equations of motion" in text
        assert "Answer parts (a) and (b) only." in text
        assert scr.adapted[str(n)] == "Answer parts (a) and (b) only."
        assert scr.query_one("#check-solvable", Button).disabled is False
    run(app, (100, 40), steps)


def test_solvable_skip_moves_to_the_next_question_and_an_old_shape_still_renders(tmp_path, monkeypatch):
    app, _ = app_for(tmp_path, monkeypatch)

    async def steps(pilot):
        scr = SessionScreen({"mode": "test", "minutes": 20, "focus": ["9702-2.1"]})
        app.push_screen(scr)
        await pilot.pause()
        advanced = []
        monkeypatch.setattr(scr, "advance", lambda: advanced.append(1))
        monkeypatch.setattr(app.tutor, "check_solvable", lambda k: {
            "n": k, "status": "skipped", "topics": ["3.1"], "message": "Skipped for this chapter."})
        scr.action_check_solvable()
        await app.workers.wait_for_complete()
        await pilot.pause()
        assert advanced == [1]
        text = log_text(scr)
        assert "Skipped for this chapter." in text and "3.1" in text
    run(app, (100, 40), steps)


def test_solvable_failure_is_said_not_raised(tmp_path, monkeypatch):
    app, _ = app_for(tmp_path, monkeypatch)

    async def steps(pilot):
        scr = SessionScreen({"mode": "test", "minutes": 20, "focus": ["9702-2.1"]})
        app.push_screen(scr)
        await pilot.pause()

        def boom(k):
            raise RuntimeError("bank unavailable")
        monkeypatch.setattr(app.tutor, "check_solvable", boom)
        scr.action_check_solvable()
        await app.workers.wait_for_complete()
        await pilot.pause()
        assert "bank unavailable" in log_text(scr)
        assert not scr.query_one("#check-solvable", Button).disabled and app.is_running
    run(app, (100, 40), steps)


def test_a_source_verified_question_is_tagged_and_offers_the_check(tmp_path, monkeypatch):
    app, _ = app_for(tmp_path, monkeypatch)

    async def steps(pilot):
        from tutor_app import cards
        view = {"n": 1, "kind": "short", "stem": "Explain.", "marks": 2, "source_verified": True}
        assert cards.no_credit(view) and cards.no_credit({"n": 2, "mastery_credit": False})
        assert not cards.no_credit({"n": 3})
        from io import StringIO
        from rich.console import Console
        stream = StringIO()
        Console(file=stream, width=80, force_terminal=False).print(cards.question(view))
        assert "source-verified" in stream.getvalue() and "no mastery credit" not in stream.getvalue()
        stream = StringIO()
        Console(file=stream, width=80, force_terminal=False).print(cards.question({**view, "adapted_prompt": "Do (a) only."}))
        assert "Do (a) only." in stream.getvalue()
    run(app, (100, 40), steps)


def test_challenge_has_the_check_and_it_reports_unstarted_topics(tmp_path, monkeypatch):
    from tutor_app import solvable
    app, _ = app_for(tmp_path, monkeypatch)

    async def steps(pilot):
        info = solvable.normalise(solvable.challenge_check(["9702-2.1"], {}, app.tutor.packs))
        assert info["status"] == "topic_pending" and info["missing"] and not info["skipped"]
        assert solvable.card_parts(info)[0] == "hint"
        assert solvable.normalise({"status": "unavailable", "topics": ["a"]})["missing"] == ["a"]
        assert solvable.normalise(None)["status"] == "unverified"
    run(app, (100, 40), steps)


def test_the_challenge_screen_offers_the_check_on_each_open_question_only(tmp_path, monkeypatch):
    from test_challenge_screen import fake_generator, open_challenge, set_up, start, choose, wait_for
    from textual.widgets import Button
    app, _ = app_for(tmp_path, monkeypatch)
    fake_generator(monkeypatch)

    async def steps(pilot):
        scr = await open_challenge(pilot, app)
        assert not scr.query_one("#check-solvable", Button).display  # setup: no question yet
        await set_up(pilot, scr)
        await start(pilot, scr)
        button = scr.query_one("#check-solvable", Button)
        assert button.display and "Can I solve this?" in str(button.label)
        before = len(scr.query("#log > .entry"))
        await pilot.press("ctrl+y")
        await pilot.pause()
        assert len(scr.query("#log > .entry")) == before + 1
        text = log_text(scr, "#log > .entry")
        assert "Can I solve this?" in text and "9702-2.1" in text
        button.press()  # the button does the same
        await pilot.pause()
        assert len(scr.query("#log > .entry")) == before + 2
        await pilot.press("b")  # answer it: the check goes away with the question
        await pilot.pause()
        for _ in range(20):
            if not button.display:
                break
            await pilot.pause(0.05)
        assert not button.display
    run(app, (100, 40), steps)


def test_practice_choices_are_remembered_for_the_next_set(tmp_path, monkeypatch):
    from tutor_app.config import Settings
    app, _ = app_for(tmp_path, monkeypatch)

    async def steps(pilot):
        from tutor_app.practice_screens import PracticeSetupScreen
        app.tutor.log({"type": "chapter_started", "chapter": "9702-2.1"})          # so "not started" can be switched off
        first = PracticeSetupScreen(["9702-2.1"])
        app.push_screen(first)
        await pilot.pause()
        assert first.query_one("#practice-marking").value == "manual"            # the first time: the defaults
        first.query_one("#practice-marking").value = "ai"
        first.query_one("#practice-count").value = "7"
        first.query_one("#practice-difficulty").value = "harder"
        first.query_one("#practice-unstarted").value = False
        first.query_one("#practice-sources").deselect("topical")   # (source-only: no bank count needed to start)
        await pilot.pause()
        first.action_start_set()
        await pilot.pause()
        saved = Settings.load(app.vault)                                           # written to the settings file
        assert (saved.practice_auto_mark, saved.practice_count, saved.practice_difficulty) == (True, 7, "harder")
        assert saved.practice_unstarted is False and saved.practice_sources == "source_verified"
        second = PracticeSetupScreen(["9702-2.1"])                                 # the next set starts as the last ended
        app.push_screen(second)
        await pilot.pause()
        assert second.query_one("#practice-marking").value == "ai"
        assert second.query_one("#practice-count").value == "7"
        assert second.query_one("#practice-difficulty").value == "harder"
        assert second.query_one("#practice-unstarted").value is False
        assert list(second.query_one("#practice-sources").selected) == ["source_verified"]
    run(app, (100, 40), steps)
