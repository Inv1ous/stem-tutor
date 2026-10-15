"""The Shortcuts & Elegant Methods screens: the two menu lines, learning one lesson with practice, recall of a due
card, the filters, settings that persist, the empty state, and the syllabus left byte-for-byte alone."""
import asyncio
import json
from datetime import datetime, timedelta, timezone

from test_tui import app_for
from tutor_app import shortcuts_screen as ss
from tutorlib import shortcuts as sc

LESSON = {
    "id": "SEM-9702-a", "hook": "Long sums slip.", "when": "Uniform acceleration from rest.",
    "idea": "Use $s = \\frac{1}{2}at^2$.", "why": "It follows from the area under the line.",
    "steps": ["Spot it", "Substitute"], "worked": {"question": "q", "long": "l", "short": "s", "saving": "time"},
    "pitfalls": ["Wrong units"], "check": "Is it sensible?",
    "practice": [
        {"kind": "numeric", "stem": "a=2, t=3, from rest. s?", "answer": "9.0", "hints": ["h1", "h2", "h3"],
         "explanation": "s = 9.0 m", "shortcut_use": "step 2"},
        {"kind": "mcq", "stem": "Which?", "options": {"A": "one", "B": "two"}, "answer": "B", "hints": [],
         "explanation": "two"},
        {"kind": "short", "stem": "Say why.", "answer": "area", "hints": [], "explanation": "area"}],
    "recall": [{"q": "What is the formula from rest?", "a": "s = 1/2 a t^2"}]}


def entry(i, score, spec="9702", section="2. Kinematics", title=None):
    return {"id": f"SEM-{spec}-{i}", "spec": spec, "section": section, "topic": "t", "title": title or f"Method {i}",
            "score": score, "origin": "base", "body": f"Body of {i}."}


ENTRIES = [entry("a", 10, title="Constant acceleration"), entry("b", 9), entry("c", 5), entry("d", 6, spec="9701",
           section="Chemistry")]


def publish(v, entries=ENTRIES, lessons=None):
    course = v / ".tutor" / "shortcuts" / "course"
    (course / "lessons").mkdir(parents=True, exist_ok=True)
    for spec in {e["spec"] for e in entries}:
        (course / f"{spec}.json").write_text(json.dumps([e for e in entries if e["spec"] == spec]))
    (course / "lessons" / "9702.json").write_text(json.dumps(lessons if lessons is not None else {"SEM-9702-a": LESSON}))


def run(app, steps, size=(100, 34)):
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


def menu_labels(app):
    m = app.screen.query_one("#menu")
    return {m.get_option_at_index(i).id: str(m.get_option_at_index(i).prompt) for i in range(m.option_count)}


async def open_from_menu(pilot, app, key, name):
    menu = app.screen.query_one("#menu")
    menu.highlighted = [o.id for o in menu.options].index(key)
    await pilot.press("enter")
    assert await wait_for(pilot, lambda: type(app.screen).__name__ == name)
    await pilot.pause(0.1)
    return app.screen


def events(v):
    p = v / ".tutor" / "shortcuts" / "events.jsonl"
    return [json.loads(x) for x in p.read_text().splitlines()] if p.exists() else []


def syllabus_files(v):
    return {str(p.relative_to(v)): p.read_bytes() for p in (v / ".tutor").rglob("*")
            if p.is_file() and "shortcuts" not in p.parts and "packs" not in p.parts and p.name != "ai_usage.json"
            and "lock" not in p.name}


def card(scr):
    return scr.query_one("#card").render().plain if hasattr(scr.query_one("#card").render(), "plain") \
        else str(scr.query_one("#card").render())


def test_menu_shows_both_lines_with_counts(tmp_path, monkeypatch):
    app, v = app_for(tmp_path, monkeypatch)
    publish(v)
    sc.Course(v).record("learn", "SEM-9702-b", 3, now=datetime.now(timezone.utc) - timedelta(days=40))

    async def steps(pilot):
        labels = menu_labels(app)
        assert labels["shortcuts"].endswith("(1 new today)") or "new today" in labels["shortcuts"]
        assert "Shortcut recall (1 due)" in labels["shortcut_recall"]
    run(app, steps)


def test_menu_lines_show_without_content_and_with_a_damaged_settings_file(tmp_path, monkeypatch):
    app, v = app_for(tmp_path, monkeypatch)
    (v / ".tutor" / "shortcuts").mkdir(parents=True)
    (v / ".tutor" / "shortcuts" / "settings.json").write_text("{not json")
    publish(v)

    async def steps(pilot):
        assert {"shortcuts", "shortcut_recall"} <= set(menu_labels(app))
        scr = await open_from_menu(pilot, app, "shortcuts", "ShortcutsScreen")
        assert "Rating 8 to 10" in card(scr)
    run(app, steps)


def test_learn_one_lesson_with_practice_then_a_note_with_no_lesson(tmp_path, monkeypatch):
    app, v = app_for(tmp_path, monkeypatch)
    publish(v)
    before = {}

    async def steps(pilot):
        before.update(syllabus_files(v))
        scr = await open_from_menu(pilot, app, "shortcuts", "ShortcutsScreen")
        assert scr.phase == "start" and "2 shortcuts match" in card(scr)
        await pilot.press("enter")  # Learn 2 new shortcuts
        await pilot.pause(0.1)
        assert scr.phase == "reveal" and "Constant acceleration" in card(scr) and "10/10" in card(scr)
        assert "The pain" in card(scr) and "When to use it" not in card(scr)
        await pilot.press("enter")
        assert "When to use it" in card(scr)
        await pilot.press("left")
        assert "When to use it" not in card(scr)
        for _ in range(7):
            await pilot.press("space")
        text = card(scr)
        for head in ("The idea", "Why it works", "Steps", "Worked example", "Watch out", "Check"):
            assert head in text
        assert "s = ½at²" in text or "at^2" not in text  # the maths went through the terminal renderer
        await pilot.press("enter")
        await pilot.pause(0.1)
        assert scr.phase == "practice" and "a=2, t=3" in card(scr)
        await pilot.press("ctrl+g")
        assert "Hint 1: h1" in card(scr)
        await pilot.press(*"9.05", "enter")
        await pilot.pause(0.1)
        assert scr.phase == "feedback" and "Correct." in card(scr)
        await pilot.press("enter")
        await pilot.pause(0.1)
        assert scr.phase == "practice"
        await pilot.press("b")
        await pilot.pause(0.1)
        assert scr.phase == "feedback" and "Correct." in card(scr)
        await pilot.press("enter")
        await pilot.pause(0.1)
        await pilot.press(*"because area", "enter")
        await pilot.pause(0.1)
        assert scr.phase == "self-mark" and "Answer: area" in card(scr)
        await pilot.press("enter")  # I had it
        await pilot.pause(0.1)
        assert scr.phase == "rate"
        await pilot.press("3")
        await pilot.pause(0.1)
        assert scr.phase == "reveal" and "Method b" in card(scr) and "not written for this one yet" in card(scr)
        assert "Body of b." in card(scr)
        await pilot.press("enter")  # no more cards, no practice: rate
        await pilot.pause(0.1)
        assert scr.phase == "rate"
        await pilot.press("enter")  # the highlighted rating, Good
        await pilot.pause(0.1)
        assert scr.phase == "done" and "learned 2 shortcuts" in card(scr)
    run(app, steps)
    ev = events(v)
    assert [(e["type"], e["id"], e["rating"]) for e in ev] == [
        ("practice", "SEM-9702-a", 2), ("practice", "SEM-9702-a", 3), ("practice", "SEM-9702-a", 3),
        ("learn", "SEM-9702-a", 3), ("learn", "SEM-9702-b", 3)]
    assert [e["mode"] for e in ev if e["type"] == "learn"] == ["lesson", "lesson"]
    assert sc.Course(v).learned_ids() == {"SEM-9702-a", "SEM-9702-b"}
    assert syllabus_files(v) == before


def test_recall_a_due_card_rates_it_and_summarises(tmp_path, monkeypatch):
    app, v = app_for(tmp_path, monkeypatch)
    publish(v)
    sc.Course(v).record("learn", "SEM-9702-a", 3, now=datetime.now(timezone.utc) - timedelta(days=40))
    before = {}

    async def steps(pilot):
        before.update(syllabus_files(v))
        scr = await open_from_menu(pilot, app, "shortcut_recall", "ShortcutRecallScreen")
        assert scr.phase == "question" and "What is the formula from rest?" in card(scr)
        assert "1/1" in str(scr.query_one("#bar").render())
        await pilot.press("enter")
        assert scr.phase == "answer" and "s = 1/2 a t" in card(scr)
        await pilot.press("4")
        await pilot.pause(0.1)
        assert scr.phase == "summary" and "recalled 1 shortcut" in card(scr) and "1 easy" in card(scr)
        assert "Learn more new shortcuts" in str(scr.query_one(".sc-actions").get_option_at_index(0).prompt)
    run(app, steps)
    last = events(v)[-1]
    assert (last["type"], last["id"], last["rating"], last["mode"]) == ("recall", "SEM-9702-a", 4, "recall")
    assert sc.Course(v).due() == []
    assert syllabus_files(v) == before


def test_recall_with_nothing_due_says_so_and_offers_learning(tmp_path, monkeypatch):
    app, v = app_for(tmp_path, monkeypatch)
    publish(v)
    sc.Course(v).record("learn", "SEM-9702-a", 3)

    async def steps(pilot):
        scr = await open_from_menu(pilot, app, "shortcut_recall", "ShortcutRecallScreen")
        t = card(scr)
        assert "Nothing is due" in t and "learned 1 shortcut" in t and "next one is due" in t
        ids = [o.id for o in scr.query_one(".sc-actions").options]
        assert "learn" in ids
        await pilot.press("enter")  # Learn more
        assert await wait_for(pilot, lambda: type(app.screen).__name__ == "ShortcutsScreen")
    run(app, steps)


def test_empty_vault_says_how_to_get_content(tmp_path, monkeypatch):
    app, v = app_for(tmp_path, monkeypatch)

    async def steps(pilot):
        assert "(" not in menu_labels(app)["shortcut_recall"]
        scr = await open_from_menu(pilot, app, "shortcuts", "ShortcutsScreen")
        assert "build/publish.py" in card(scr)
        assert [o.id for o in scr.query_one(".sc-actions").options] == ["settings", "home"]
        await pilot.press("escape")
        scr = await open_from_menu(pilot, app, "shortcut_recall", "ShortcutRecallScreen")
        assert "build/publish.py" in card(scr)
        await pilot.press("s")
        await pilot.pause(0.1)
        assert type(app.screen).__name__ == "ShortcutSettingsScreen"
        assert "build/publish.py" in str(app.screen.query_one("#sc-detail").render())
    run(app, steps)


def test_filters_change_what_appears_and_settings_persist(tmp_path, monkeypatch):
    app, v = app_for(tmp_path, monkeypatch)
    publish(v)

    async def steps(pilot):
        scr = await open_from_menu(pilot, app, "shortcuts", "ShortcutsScreen")
        assert "2 shortcuts match" in card(scr)
        await pilot.press("s")
        await pilot.pause(0.1)
        st = app.screen
        assert type(st).__name__ == "ShortcutSettingsScreen"
        lst = st.query_one("#sc-settings")
        lst.highlighted = [o.id for o in lst.options].index("min_score")
        await pilot.press("enter")
        await pilot.pause(0.1)
        pick = app.screen.query_one("#confirm")
        pick.highlighted = 5  # 5/10
        await pilot.press("enter")
        await pilot.pause(0.1)
        assert st.cfg["min_score"] == 5
        lst.highlighted = [o.id for o in lst.options].index("lessons_only")
        await pilot.press("enter")
        await pilot.pause(0.1)
        assert st.cfg["lessons_only"] is True
        await pilot.press("escape")
        await pilot.pause(0.1)
        assert type(app.screen).__name__ == "ShortcutsScreen"
        assert "1 shortcut matches" in card(app.screen)
        assert "full lessons only: yes" in card(app.screen)
    run(app, steps)
    cfg = sc.load_config(v)
    assert cfg["min_score"] == 5 and cfg["lessons_only"] is True
    # a new Course (the recall queue shares it) sees the same filters
    assert [e["id"] for e in sc.Course(v).entries()] == ["SEM-9702-a"]


def test_helpers_numeric_tolerance_and_missing_lesson_fields():
    assert ss.numeric_ok("9.05", "9.0") and ss.numeric_ok("9.0 m", "9.0") and not ss.numeric_ok("9.5", "9.0")
    assert ss.numeric_ok("abc", "ABC") and not ss.numeric_ok("x", "9.0")
    assert ss.sections_of({"title": "t", "body": "B"}) == [("The idea", ss.Text("B"))]
    odd = {"body": "b", "lesson": {"steps": "one", "worked": "no", "pitfalls": None, "practice": "no"}}
    assert [h for h, _ in ss.sections_of(odd)] == ["The idea", "Steps"]
    assert ss.practice_of(odd) == []
