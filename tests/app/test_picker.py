import asyncio

from test_tui import app_for
from tutor_app.screens import PickerScreen


def crowd(app):
    """A syllabus with many subtopics under three topics, so the picker has something to search through."""
    p = app.tutor.packs
    p.topics = {"9701-1": {"id": "9701-1", "title": "Atomic structure", "level": "AS", "spec": "9701", "subject": "chem"},
                "9702-1": {"id": "9702-1", "title": "Physical quantities", "level": "AS", "spec": "9702", "subject": "phys"},
                "P1": {"id": "P1", "title": "Pure Mathematics 1", "level": "P1", "spec": "P1", "subject": "math"}}
    p.subtopics = {}
    p.kcs = {}
    names = {"9701-1": ["Particles", "Isotopes", "Electrons", "Orbitals"] + [f"Chem idea {i}" for i in range(5, 13)],
             "9702-1": ["Units", "Scalars and vectors"], "P1": ["Algebra", "Quadratics"]}
    for topic, titles in names.items():
        for i, title in enumerate(titles, 1):
            sub = f"{topic}.{i}" if topic[0] == "9" else f"{topic}-{i}"
            p.subtopics[sub] = {"id": sub, "title": title, "topic": topic, "spec": topic.split("-")[0]}
            p.kcs[f"{sub}.1"] = {"subtopic": sub, "subject": p.topics[topic]["subject"], "title": title}
    p.pack = lambda sub: True


def rows(screen):
    box = screen.query_one("#subs")
    return [(box.get_option_at_index(i).id, box.get_option_at_index(i).disabled) for i in range(box.option_count)]


def run(app, steps, size=(100, 40), many=True):
    async def go():
        async with app.run_test(size=size) as pilot:
            await pilot.pause()
            if many:
                crowd(app)
            await steps(pilot)
            await app.ai.close()
    asyncio.run(go())


def test_subtopics_are_grouped_under_their_topics_in_natural_order(tmp_path, monkeypatch):
    app, v = app_for(tmp_path, monkeypatch)

    async def steps(pilot):
        app.push_screen(PickerScreen("lesson"))
        await pilot.pause()
        got = rows(app.screen)
        heads = [i for i, d in got if d]
        assert heads == ["h:9701-1", "h:9702-1", "h:P1"]
        chem = [i for i, d in got if not d and i.startswith("9701")]
        assert chem[:3] == ["9701-1.1", "9701-1.2", "9701-1.3"] and chem[-1] == "9701-1.12"  # 1.10 after 1.9, not after 1.1
        assert "16 subtopics" in str(app.screen.query_one("#found").render())
    run(app, steps)


def test_typing_in_the_list_searches_and_escape_clears_before_it_goes_back(tmp_path, monkeypatch):
    app, v = app_for(tmp_path, monkeypatch)

    async def steps(pilot):
        app.push_screen(PickerScreen("lesson"))
        await pilot.pause()
        await pilot.press("v", "e", "c", "t", "o", "r")  # no click first: typing in the list goes to the search box
        await pilot.pause()
        assert app.screen.query_one("#find").value == "vector"
        assert [i for i, d in rows(app.screen) if not d] == ["9702-1.2"]  # words match the title
        assert [i for i, d in rows(app.screen) if d] == ["h:9702-1"]  # only the heading of what is left
        await pilot.press("escape")
        await pilot.pause()
        assert app.screen.__class__.__name__ == "PickerScreen" and app.screen.query_one("#find").value == ""
        assert len([1 for _, d in rows(app.screen) if not d]) == 16
        await pilot.press("p", "1")  # a code finds a whole unit; a subject word finds its topics
        await pilot.pause()
        assert [i for i, d in rows(app.screen) if not d] == ["P1-1", "P1-2"]
        await pilot.press("escape", "c", "h", "e", "m")
        await pilot.pause()
        assert len([1 for i, d in rows(app.screen) if not d]) == 12
        await pilot.press("escape", "n", "o", "p", "e", "x", "x")
        await pilot.pause()
        assert [i for i, d in rows(app.screen)] == ["none"]  # and it says so
        await pilot.press("escape", "escape")
        await pilot.pause()
        assert app.screen.__class__.__name__ == "HomeScreen"
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


def test_square_brackets_jump_between_topics_and_recent_comes_first(tmp_path, monkeypatch):
    app, v = app_for(tmp_path, monkeypatch)

    async def steps(pilot):
        for sub in ("P1-1", "9702-1.1"):
            app.tutor.state["kcs"][f"{sub}.1"] = {"theta": 0.0, "n": 1, "succ_days": [], "fsrs": None,
                                                  "last_review_day": "2026-09-29" if sub == "P1-1" else "2026-09-20"}
        app.push_screen(PickerScreen("lesson"))
        await pilot.pause()
        got = rows(app.screen)
        assert got[0] == ("h:recent", True) and got[1][0] == "recent:P1-1" and got[2][0] == "recent:9702-1.1"  # newest first
        box = app.screen.query_one("#subs")
        await pilot.press("right_square_bracket")
        await pilot.pause()
        assert box.get_option_at_index(box.highlighted).id == "9701-1.1"  # the first of the next topic
        await pilot.press("right_square_bracket", "right_square_bracket")
        await pilot.pause()
        assert box.get_option_at_index(box.highlighted).id == "P1-1"
        await pilot.press("left_square_bracket")
        await pilot.pause()
        assert box.get_option_at_index(box.highlighted).id == "9702-1.1"
    run(app, steps)


def test_a_test_ticks_from_the_filtered_list_and_starts_with_what_is_ticked(tmp_path, monkeypatch):
    app, v = app_for(tmp_path, monkeypatch)
    chosen = []

    async def steps(pilot):
        app.push_screen(PickerScreen("test"), chosen.append)
        await pilot.pause()
        await pilot.press("space")  # the first subtopic
        await pilot.press("p", "1")  # then search P1 and tick all that is shown
        await pilot.pause()
        await pilot.press("ctrl+a")
        await pilot.pause()
        assert "3 ticked" in str(app.screen.query_one("#found").render())
        await pilot.press("escape")  # the ticks stay while the search changes
        await pilot.pause()
        assert "3 ticked" in str(app.screen.query_one("#found").render())
        await pilot.press("ctrl+s")
        await pilot.pause()
        assert chosen == [["9701-1.1", "P1-1", "P1-2"]]
    run(app, steps)


def test_the_start_button_stays_inside_the_window_however_short_it_is(tmp_path, monkeypatch):
    for size in ((100, 40), (80, 24), (60, 20)):
        app, v = app_for(tmp_path / f"h{size[1]}", monkeypatch)

        async def steps(pilot):
            app.push_screen(PickerScreen("test"))
            for _ in range(3):
                await pilot.pause()
            box, go, subs = (app.screen.query_one(x).region for x in ("#picker", "#go", "#subs"))
            assert go.bottom <= box.bottom and subs.height >= 4 and box.bottom <= size[1]
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
