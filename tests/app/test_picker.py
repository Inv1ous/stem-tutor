import asyncio

from test_tui import app_for
from tutor_app.screens import PickerScreen


def crowd(app):
    """A syllabus with many subtopics: two Chemistry chapters, one Physics, two Maths modules."""
    p = app.tutor.packs
    p.topics = {"9701-1": {"id": "9701-1", "title": "Atomic structure", "level": "AS", "spec": "9701", "subject": "chem"},
                "9701-2": {"id": "9701-2", "title": "Atoms and moles", "level": "AS", "spec": "9701", "subject": "chem"},
                "9702-1": {"id": "9702-1", "title": "Physical quantities", "level": "AS", "spec": "9702", "subject": "phys"},
                "P1": {"id": "P1", "title": "Pure Mathematics 1", "level": "P1", "spec": "P1", "subject": "math"},
                "M1": {"id": "M1", "title": "Mechanics 1", "level": "M1", "spec": "M1", "subject": "math"}}
    p.subtopics = {}
    p.kcs = {}
    names = {"9701-1": ["Particles", "Isotopes", "Electrons", "Orbitals"] + [f"Chem idea {i}" for i in range(5, 13)],
             "9701-2": ["Moles", "Gases"], "9702-1": ["Units", "Scalars and vectors"],
             "P1": ["Algebra", "Quadratics"], "M1": ["Kinematics", "Forces"]}
    for topic, titles in names.items():
        for i, title in enumerate(titles, 1):
            sub = f"{topic}.{i}" if topic[0] == "9" else f"{topic}-{i}"
            p.subtopics[sub] = {"id": sub, "title": title, "topic": topic, "spec": topic.split("-")[0]}
            p.kcs[f"{sub}.1"] = {"subtopic": sub, "subject": p.topics[topic]["subject"], "title": title}
    p.pack = lambda sub: True


def rows(screen):
    box = screen.query_one("#subs")
    return [(box.get_option_at_index(i).id, box.get_option_at_index(i).disabled) for i in range(box.option_count)]


def ids(screen):
    return [i for i, d in rows(screen) if not d]


def crumb(screen):
    return str(screen.query_one("#found").render())


def run(app, steps, size=(100, 40), many=True):
    async def go():
        async with app.run_test(size=size) as pilot:
            await pilot.pause()
            if many:
                crowd(app)
            await steps(pilot)
            await app.ai.close()
    asyncio.run(go())


def test_the_top_level_is_folders_for_chemistry_physics_and_maths(tmp_path, monkeypatch):
    app, v = app_for(tmp_path, monkeypatch)

    async def steps(pilot):
        app.push_screen(PickerScreen("lesson"))
        await pilot.pause()
        assert ids(app.screen) == ["dir:chem", "dir:phys", "dir:math"]  # and no "recent" group
        assert not any(i == "h:recent" for i, _ in rows(app.screen))
    run(app, steps)


def test_each_subject_opens_into_its_chapters_and_a_chapter_into_its_subtopics(tmp_path, monkeypatch):
    app, v = app_for(tmp_path, monkeypatch)
    chosen = []

    async def steps(pilot):
        app.push_screen(PickerScreen("lesson"), chosen.append)
        await pilot.pause()
        await pilot.press("enter")  # Chemistry
        await pilot.pause()
        assert ids(app.screen) == ["dir:chem/9701-1", "dir:chem/9701-2"] and "Chemistry 9701" in crumb(app.screen)
        await pilot.press("enter")  # 1. Atomic structure
        await pilot.pause()
        got = ids(app.screen)
        assert got[:3] == ["9701-1.1", "9701-1.2", "9701-1.3"] and got[-1] == "9701-1.12" and len(got) == 12  # 1.10 after 1.9
        assert all(not i.startswith("h:") for i, _ in rows(app.screen))  # no sub-headings: it is the chapter's own list
        await pilot.press("escape")  # up to the chapters
        await pilot.pause()
        assert ids(app.screen) == ["dir:chem/9701-1", "dir:chem/9701-2"]
        await pilot.press("left")  # up to the top
        await pilot.pause()
        assert ids(app.screen) == ["dir:chem", "dir:phys", "dir:math"]
        await pilot.press("down", "down", "enter")  # Maths: a folder for each module
        await pilot.pause()
        assert ids(app.screen) == ["dir:math/P1", "dir:math/M1"]
        await pilot.press("down", "enter")  # M1
        await pilot.pause()
        assert ids(app.screen) == ["M1-1", "M1-2"] and "Mechanics" in crumb(app.screen)
        await pilot.press("down", "enter")
        await pilot.pause()
        assert chosen == [["M1-2"]]
    run(app, steps)


def test_escape_goes_up_a_folder_at_a_time_and_then_out(tmp_path, monkeypatch):
    app, v = app_for(tmp_path, monkeypatch)

    async def steps(pilot):
        app.push_screen(PickerScreen("lesson"))
        await pilot.pause()
        await pilot.press("down", "down", "enter", "enter")  # Maths > P1
        await pilot.pause()
        assert ids(app.screen) == ["P1-1", "P1-2"]
        box = app.screen.query_one("#subs")
        await pilot.press("escape")
        await pilot.pause()
        assert ids(app.screen) == ["dir:math/P1", "dir:math/M1"]
        assert box.get_option_at_index(box.highlighted).id == "dir:math/P1"  # back on the folder you came out of
        await pilot.press("escape", "escape")
        await pilot.pause()
        assert app.screen.__class__.__name__ == "HomeScreen"
    run(app, steps)


def test_search_looks_through_every_folder_and_escape_returns_to_where_you_were(tmp_path, monkeypatch):
    app, v = app_for(tmp_path, monkeypatch)

    async def steps(pilot):
        app.push_screen(PickerScreen("lesson"))
        await pilot.pause()
        await pilot.press("enter")  # inside Chemistry
        await pilot.pause()
        await pilot.press("v", "e", "c", "t", "o", "r")  # no click first: typing goes to the search box
        await pilot.pause()
        assert app.screen.query_one("#find").value == "vector"
        assert ids(app.screen) == ["9702-1.2"]  # found in Physics although we were in Chemistry
        assert [i for i, d in rows(app.screen) if d] == ["h:9702-1"]
        await pilot.press("escape")
        await pilot.pause()
        assert app.screen.query_one("#find").value == "" and ids(app.screen) == ["dir:chem/9701-1", "dir:chem/9701-2"]
        await pilot.press("p", "1")  # a code finds a module's subtopics
        await pilot.pause()
        assert ids(app.screen) == ["P1-1", "P1-2"]
        await pilot.press("escape", "c", "h", "e", "m")
        await pilot.pause()
        assert len(ids(app.screen)) == 14
        await pilot.press("escape", "n", "o", "p", "e", "x", "x")
        await pilot.pause()
        assert [i for i, _ in rows(app.screen)] == ["none"]
    run(app, steps)


def test_enter_in_the_search_box_takes_the_first_match(tmp_path, monkeypatch):
    app, v = app_for(tmp_path, monkeypatch)
    chosen = []

    async def steps(pilot):
        app.push_screen(PickerScreen("lesson"), chosen.append)
        await pilot.pause()
        await pilot.press("q", "u", "a", "d", "enter")
        await pilot.pause()
        assert chosen == [["P1-2"]]
    run(app, steps)


def test_only_one_folder_is_opened_for_you_and_escape_leaves(tmp_path, monkeypatch):
    app, v = app_for(tmp_path, monkeypatch)  # the fixture has a single Physics subtopic

    async def steps(pilot):
        app.push_screen(PickerScreen("lesson"))
        await pilot.pause()
        assert ids(app.screen) == ["9702-2.1"]  # nothing to choose between: straight to the subtopic
        await pilot.press("escape")
        await pilot.pause()
        assert app.screen.__class__.__name__ == "HomeScreen"
    run(app, steps, many=False)


def test_a_test_ticks_a_whole_folder_and_starts_with_what_is_ticked(tmp_path, monkeypatch):
    app, v = app_for(tmp_path, monkeypatch)
    chosen = []

    async def steps(pilot):
        app.push_screen(PickerScreen("test"), chosen.append)
        await pilot.pause()
        await pilot.press("down", "down", "space")  # the Maths folder: everything in it
        await pilot.pause()
        assert "4 ticked" in crumb(app.screen)
        await pilot.press("enter", "down", "enter", "space")  # into Maths > M1, un-tick its first subtopic
        await pilot.pause()
        assert "3 ticked" in crumb(app.screen)
        await pilot.press("escape", "escape", "home", "enter", "enter", "ctrl+a")  # Chemistry > 1: tick all shown
        await pilot.pause()
        assert "15 ticked" in crumb(app.screen)
        await pilot.press("ctrl+s")
        await pilot.pause()
        assert len(chosen[0]) == 15 and "M1-1" not in chosen[0] and "9701-1.12" in chosen[0]
    run(app, steps)


def test_the_start_button_stays_inside_the_window_however_short_it_is(tmp_path, monkeypatch):
    for size in ((100, 40), (80, 24), (60, 20)):
        app, v = app_for(tmp_path / f"h{size[1]}", monkeypatch)

        async def steps(pilot):
            app.push_screen(PickerScreen("test"))
            for _ in range(3):
                await pilot.pause()
            box, go, subs = (app.screen.query_one(x).region for x in ("#picker", "#go", "#subs"))
            assert go.bottom <= box.bottom and subs.height >= 3 and box.bottom <= size[1]
        run(app, steps, size)


def test_the_challenge_chapter_list_searches_and_keeps_its_ticks(tmp_path, monkeypatch):
    from tutor_app.challenge_screen import TopicScreen
    app, v = app_for(tmp_path, monkeypatch)
    chosen = []

    async def steps(pilot):
        app.push_screen(TopicScreen([]), chosen.append)
        await pilot.pause()
        box = app.screen.query_one("#subs")
        n = box.option_count
        assert n >= 1
        await pilot.press("space")  # the first chapter is ticked
        await pilot.press("z", "z", "z", "z")  # a search that finds nothing keeps what is ticked
        await pilot.pause()
        assert app.screen.query_one("#subs").option_count == 0
        await pilot.press("escape")
        await pilot.pause()
        assert app.screen.query_one("#subs").option_count == n
        await pilot.press("ctrl+s")
        await pilot.pause()
        assert len(chosen) == 1 and len(chosen[0]) == 1
    run(app, steps, many=False)
