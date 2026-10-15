import json
from datetime import datetime, timedelta, timezone

import pytest

from tutorlib import shortcuts as sc
from tutorlib import store

UTC = timezone.utc
T0 = datetime(2026, 10, 8, 4, 0, tzinfo=UTC)  # 12:00 in Hong Kong


def entry(i, spec="9702", section="1. Kinematics", score=9, origin="base", topic="", lesson=None):
    return {"id": f"SEM-{spec}-{i}", "spec": spec, "section": section, "topic": topic, "title": f"Title {i}",
            "score": score, "origin": origin, "body": f"body {i}", "lesson": lesson}


ENTRIES = [entry("a", score=10), entry("b", score=9), entry("c", score=8, section="7. A Level: circular motion"),
           entry("d", spec="P1", score=10, section="2. Quadratics", origin="research"), entry("e", score=5),
           entry("f", spec="M1", score=9, section="10. Moments"), entry("g", spec="M1", score=9, section="2. Forces")]


@pytest.fixture
def vault(tmp_path):
    return store.Vault(tmp_path / "vault")


def publish(vault, entries=ENTRIES, lessons=None):
    course = vault.tutor / "shortcuts/course"
    (course / "lessons").mkdir(parents=True, exist_ok=True)
    by = {}
    for e in entries:
        by.setdefault(e["spec"], []).append({k: v for k, v in e.items() if k != "lesson"})
    for spec, rows in by.items():
        (course / f"{spec}.json").write_text(json.dumps(rows))
    (course / "lessons/all.json").write_text(json.dumps(lessons or {}))


def ids(es):
    return [e["id"].split("-", 2)[2] for e in es]


# ---------------- config ----------------
def test_defaults_when_missing_or_damaged(vault):
    assert sc.load_config(vault) == sc.DEFAULT_CONFIG
    p = vault.tutor / "shortcuts/settings.json"
    p.parent.mkdir(parents=True)
    for bad in ("{not json", "[1, 2]", "", "null"):
        p.write_text(bad)
        assert sc.load_config(vault) == sc.DEFAULT_CONFIG


def test_normalise_types_and_clamps():
    d = sc.normalise_config({"min_score": "7", "max_score": 99, "specs": "9702", "levels": ["as", "x", "A", "A"],
                             "sections": [1, " Energy ", ""], "origins": ["BASE", "web"], "order": "Section",
                             "new_per_day": -3, "lessons_only": "yes", "recall_scope": "everything", "junk": 1})
    assert d == {"min_score": 7, "max_score": 10, "specs": ["9702"], "levels": ["AS", "A"], "sections": ["Energy"],
                 "origins": ["base"], "order": "section", "new_per_day": 0, "lessons_only": False,
                 "recall_scope": "learned"}


def test_min_max_swapped_clamped_and_bad_types_default():
    assert sc.normalise_config({"min_score": 10, "max_score": 3})["min_score"] == 3
    assert (lambda c: (c["min_score"], c["max_score"]))(sc.normalise_config({"min_score": -4, "max_score": 12})) == (0, 10)
    d = sc.normalise_config({"min_score": True, "max_score": None, "new_per_day": "many", "specs": 5, "order": 3})
    assert d == sc.DEFAULT_CONFIG
    assert sc.normalise_config(None) == sc.DEFAULT_CONFIG
    assert sc.normalise_config({"new_per_day": 999})["new_per_day"] == sc.MAX_NEW_PER_DAY


def test_default_config_is_not_shared():
    sc.normalise_config({})["specs"].append("x")
    assert sc.DEFAULT_CONFIG["specs"] == []


def test_save_and_load_round_trip(vault):
    saved = sc.save_config(vault, {"min_score": 6, "specs": ["P1"], "order": "section", "bogus": 1})
    assert saved["min_score"] == 6 and "bogus" not in saved
    assert sc.load_config(vault) == saved
    assert json.loads((vault.tutor / "shortcuts/settings.json").read_text()) == saved


# ---------------- filters and ordering ----------------
def test_select_filters():
    f = lambda **c: ids(sc.select(ENTRIES, {**sc.DEFAULT_CONFIG, "min_score": 0, **c}))
    assert f() == ["a", "d", "b", "g", "f", "c", "e"]
    assert f(min_score=9, max_score=9) == ["b", "g", "f"]
    assert f(specs=["P1"]) == ["d"]
    assert f(origins=["research"]) == ["d"]
    assert f(levels=["A"]) == ["c"]
    assert "c" not in f(levels=["AS"])
    assert f(sections=["MOMENT", "quadr"]) == ["d", "f"]
    assert f(sections=["nothing"]) == []


def test_select_matches_topic_too():
    es = [entry("t", topic="suvat"), entry("u")]
    assert ids(sc.select(es, {"sections": ["suvat"]})) == ["t"]


def test_ordering_by_score_then_section_and_by_section():
    by_score = ids(sc.select(ENTRIES, {"min_score": 0, "order": "score"}))
    assert by_score == ["a", "d", "b", "g", "f", "c", "e"]  # 10s, 9s (spec, then section 2 before 10), 8, 5
    by_section = ids(sc.select(ENTRIES, {"min_score": 0, "order": "section"}))
    assert by_section == ["a", "b", "e", "c", "g", "f", "d"]  # spec, then section number, then score


def test_lessons_only():
    es = [entry("x", lesson={"id": "x"}), entry("y")]
    assert ids(sc.select(es, {"lessons_only": True})) == ["x"]
    assert ids(sc.select(es, {})) == ["x", "y"]


def test_level_of():
    assert sc.level_of({"section": "7. A Level: circular motion"}) == "A"
    assert sc.level_of({"section": "13. Series (13.1)"}) == "A"
    assert sc.level_of({"section": "1. Kinematics"}) == "AS"


# ---------------- loading ----------------
def test_load_entries_attaches_lessons_and_skips_damage(vault):
    publish(vault, ENTRIES, {"SEM-9702-a": {"id": "SEM-9702-a", "hook": "h"}})
    course = vault.tutor / "shortcuts/course"
    (course / "broken.json").write_text("{nope")
    (course / "notlist.json").write_text('{"a": 1}')
    got = {e["id"]: e for e in sc.load_entries(vault)}
    assert len(got) == len(ENTRIES)
    assert got["SEM-9702-a"]["lesson"]["hook"] == "h" and got["SEM-9702-b"]["lesson"] is None


def test_load_entries_empty_vault(vault):
    assert sc.load_entries(vault) == []
    assert sc.Course(vault).stats() == {"selected": 0, "learned": 0, "due": 0, "new_today": 0, "lessons": 0}


def test_course_entries_and_pool(vault):
    publish(vault)
    sc.save_config(vault, {"min_score": 9})
    c = sc.Course(vault)
    assert len(c.pool()) == len(ENTRIES) and ids(c.entries()) == ["a", "d", "b", "g", "f"]
    assert sc.Course(vault.root).cfg["min_score"] == 9  # a plain path works too


# ---------------- learning, recall, state ----------------
def test_new_per_day_budget_counts_todays_learns_in_local_day(vault):
    publish(vault)
    sc.save_config(vault, {"min_score": 0, "new_per_day": 3})
    c = sc.Course(vault)
    assert ids(c.next_lessons(now=T0)) == ["a", "d", "b"]
    c.record("learn", "SEM-9702-a", 3, now=T0)
    assert ids(c.next_lessons(now=T0)) == ["d", "b"]  # a is learned, and 2 of today's 3 are left
    c.record("learn", "SEM-P1-d", 3, now=T0)
    c.record("learn", "SEM-9702-b", 3, now=T0)
    assert c.next_lessons(now=T0) == [] and c.new_today(T0) == 3
    assert ids(c.next_lessons(2, now=T0)) == ["g", "f"]  # an explicit n ignores the budget
    # Hong Kong: 2026-10-08 23:00 local is still the same day, 00:30 the next is a fresh budget
    assert c.new_today(datetime(2026, 10, 8, 15, 0, tzinfo=UTC)) == 3
    assert c.new_today(datetime(2026, 10, 8, 16, 30, tzinfo=UTC)) == 0
    assert len(c.next_lessons(now=datetime(2026, 10, 8, 16, 30, tzinfo=UTC))) == 3


def test_local_day_follows_the_vaults_timezone(tmp_path):
    v = store.Vault(tmp_path / "v")
    (v.tutor).mkdir(parents=True)
    (v.tutor / "config.json").write_text('{"tz": "America/New_York"}')
    v = store.Vault(v.root)
    publish(v)
    c = sc.Course(v)
    c.record("learn", "SEM-9702-a", 3, now=datetime(2026, 10, 8, 3, 0, tzinfo=UTC))  # 23:00 on the 7th in New York
    assert c.new_today(datetime(2026, 10, 8, 3, 30, tzinfo=UTC)) == 1
    assert c.new_today(datetime(2026, 10, 8, 5, 0, tzinfo=UTC)) == 0  # 01:00 on the 8th


def test_practice_does_not_schedule_or_use_budget(vault):
    publish(vault)
    c = sc.Course(vault)
    c.record("practice", "SEM-9702-a", None, "lesson", now=T0)
    c.record("practice", "SEM-9702-a", 4, now=T0)
    assert c.learned_ids() == set() and c.due(T0 + timedelta(days=99)) == [] and c.new_today(T0) == 0
    assert len((vault.tutor / "shortcuts/events.jsonl").read_text().splitlines()) == 2


def test_due_after_again_versus_easy(vault):
    publish(vault)
    sc.save_config(vault, {"min_score": 0})
    c = sc.Course(vault)
    c.record("learn", "SEM-9702-a", 1, now=T0)
    c.record("learn", "SEM-9702-b", 4, now=T0)
    assert c.due(T0) == []
    due_a = datetime.fromisoformat(c.state()["cards"]["SEM-9702-a"]["due"])
    due_b = datetime.fromisoformat(c.state()["cards"]["SEM-9702-b"]["due"])
    assert due_a < due_b and (due_b - due_a) >= timedelta(days=2)
    assert c.due(due_a + timedelta(seconds=1)) == ["SEM-9702-a"]
    assert c.due(due_b + timedelta(seconds=1)) == ["SEM-9702-a", "SEM-9702-b"]  # most overdue first
    ev = c.record("recall", "SEM-9702-a", 3, now=due_a + timedelta(hours=1))
    assert ev["due"] and datetime.fromisoformat(ev["due"]) > due_a
    assert "SEM-9702-a" not in c.due(due_a + timedelta(hours=2))


def test_recall_without_learn_creates_the_card_and_second_learn_does_not_reschedule(vault):
    publish(vault)
    c = sc.Course(vault)
    c.record("recall", "SEM-9702-a", 3, now=T0)
    assert "SEM-9702-a" in c.learned_ids()
    c.record("learn", "SEM-9702-b", 3, now=T0)
    before = c.state()["cards"]["SEM-9702-b"]
    c.record("learn", "SEM-9702-b", 1, now=T0 + timedelta(minutes=5))
    assert c.state()["cards"]["SEM-9702-b"] == before


def test_recall_scope_learned_vs_all(vault):
    publish(vault)
    sc.save_config(vault, {"min_score": 0})
    c = sc.Course(vault)
    c.record("learn", "SEM-9702-a", 1, now=T0)
    c.record("learn", "SEM-9702-e", 1, now=T0)  # score 5
    later = T0 + timedelta(days=30)
    assert sorted(c.due(later)) == ["SEM-9702-a", "SEM-9702-e"]
    sc.save_config(vault, {"min_score": 9, "recall_scope": "learned"})
    assert sc.Course(vault).due(later) == ["SEM-9702-a"]  # e no longer passes the filters
    sc.save_config(vault, {"min_score": 9, "recall_scope": "all"})
    assert sorted(sc.Course(vault).due(later)) == ["SEM-9702-a", "SEM-9702-e"]
    assert sc.Course(vault).next_lessons(10, later) != []  # unlearned ones still come from the filters


def test_due_ignores_entries_no_longer_published(vault):
    publish(vault)
    c = sc.Course(vault)
    c.record("learn", "SEM-9702-gone", 1, now=T0)
    assert c.due(T0 + timedelta(days=30)) == [] and c.stats(T0)["learned"] == 0


def test_validation(vault):
    c = sc.Course(vault)
    with pytest.raises(ValueError):
        c.record("peek", "x", 3)
    with pytest.raises(ValueError):
        c.record("learn", "x", 7)
    with pytest.raises(ValueError):
        c.record("learn", "x", None)
    assert not (vault.tutor / "shortcuts/events.jsonl").exists()


def test_refold_when_the_log_is_ahead_of_the_cache(vault):
    publish(vault)
    c = sc.Course(vault)
    c.record("learn", "SEM-9702-a", 3, now=T0)
    assert json.loads((vault.tutor / "shortcuts/state.json").read_text())["cards"].keys() == {"SEM-9702-a"}
    # another process appends behind the cache's back
    other = sc.Course(vault)
    other.record("learn", "SEM-9702-b", 3, now=T0)
    assert c.learned_ids() == {"SEM-9702-a", "SEM-9702-b"}
    # the log is ahead of a fresh Course's cache too
    with open(vault.tutor / "shortcuts/events.jsonl", "a") as f:
        f.write(json.dumps({"t": T0.isoformat(), "type": "learn", "id": "SEM-9702-d", "rating": 3}) + "\n")
    assert "SEM-9702-d" in sc.Course(vault).learned_ids()
    # a cache that lies is overruled by the log being the source of truth
    st = vault.tutor / "shortcuts/state.json"
    st.write_text(json.dumps({"bytes": 0, "cards": {"zzz": {}}, "learns": []}))
    assert sc.Course(vault).learned_ids() == {"SEM-9702-a", "SEM-9702-b", "SEM-9702-d"}


def test_cache_matches_a_fresh_fold_and_is_used(vault, monkeypatch):
    publish(vault)
    c = sc.Course(vault)
    for i, r in (("a", 3), ("b", 1), ("d", 4)):
        c.record("learn", f"SEM-{'P1' if i == 'd' else '9702'}-{i}", r, now=T0)
    cached = sc.Course(vault).state()
    monkeypatch.setattr(sc, "_fold", lambda events: pytest.fail("refolded though the cache is current"))
    assert sc.Course(vault).state()["cards"] == cached["cards"]
    monkeypatch.undo()
    (vault.tutor / "shortcuts/state.json").unlink()
    assert sc.Course(vault).state()["cards"] == cached["cards"]


@pytest.mark.parametrize("junk", ["{not json", "[]", '{"bytes": "x"}', '{"bytes": 5, "cards": 1, "learns": []}', ""])
def test_corrupt_state_file_is_refolded(vault, junk):
    publish(vault)
    c = sc.Course(vault)
    c.record("learn", "SEM-9702-a", 3, now=T0)
    (vault.tutor / "shortcuts/state.json").write_text(junk)
    fresh = sc.Course(vault)
    assert fresh.learned_ids() == {"SEM-9702-a"}
    assert "SEM-9702-a" in json.loads((vault.tutor / "shortcuts/state.json").read_text())["cards"]


def test_torn_and_bad_log_lines_are_skipped_and_the_next_append_is_not_glued(vault):
    publish(vault)
    log = vault.tutor / "shortcuts/events.jsonl"
    log.parent.mkdir(parents=True, exist_ok=True)
    good = json.dumps({"t": T0.isoformat(), "type": "learn", "id": "SEM-9702-a", "rating": 3})
    log.write_text(good + "\nnot json\n" + json.dumps({"type": "learn", "id": "SEM-9702-b", "rating": 3}) + "\n"
                   + json.dumps({"t": T0.isoformat(), "type": "learn", "id": "SEM-9702-c", "rating": 9}) + "\n"
                   + '{"t": "2026-10-0')  # torn tail
    c = sc.Course(vault)
    assert c.learned_ids() == {"SEM-9702-a"}
    c.record("learn", "SEM-9702-d", 3, now=T0)
    assert sc.Course(vault).learned_ids() == {"SEM-9702-a", "SEM-9702-d"}


def test_naive_now_is_taken_as_utc(vault):
    publish(vault)
    c = sc.Course(vault)
    c.record("learn", "SEM-9702-a", 3, now=datetime(2026, 10, 8, 4, 0))
    assert c.new_today(datetime(2026, 10, 8, 5, 0)) == 1


# ---------------- recall cards and stats ----------------
def test_recall_cards_from_lesson_or_derived():
    lesson = {"recall": [{"q": "Q1", "a": "A1"}, {"q": "", "a": "x"}, "junk", {"q": "Q2", "a": "A2"}]}
    assert sc.Course.recall_cards(None, entry("x", lesson=lesson)) == [{"q": "Q1", "a": "A1"}, {"q": "Q2", "a": "A2"}]
    plain = sc.Course.recall_cards(None, entry("y"))
    assert plain == [{"q": "What is the shortcut for: Title y?", "a": "body y"}]
    assert sc.Course.recall_cards(None, entry("z", lesson={"recall": []})) == [
        {"q": "What is the shortcut for: Title z?", "a": "body z"}]


def test_stats(vault):
    publish(vault, ENTRIES, {"SEM-9702-a": {"id": "SEM-9702-a"}, "SEM-9702-b": {"id": "SEM-9702-b"}})
    sc.save_config(vault, {"min_score": 9})
    c = sc.Course(vault)
    c.record("learn", "SEM-9702-a", 1, now=T0)
    c.record("learn", "SEM-9702-e", 3, now=T0)
    assert c.stats(T0) == {"selected": 5, "learned": 2, "due": 0, "new_today": 2, "lessons": 2}
    assert c.stats(T0 + timedelta(days=60))["due"] == 1  # e is outside the filters


# ---------------- separation from the syllabus ----------------
def test_syllabus_files_are_never_touched(vault):
    publish(vault)
    (vault.tutor / "state").mkdir(parents=True)
    (vault.tutor / "events").mkdir()
    snapshots = {vault.tutor / "state/learner.json": '{"kcs": {}}', vault.tutor / "events/2026-10.jsonl": '{"a": 1}\n'}
    for p, text in snapshots.items():
        p.write_text(text)
    c = sc.Course(vault)
    sc.save_config(vault, {"min_score": 0})
    c.record("learn", "SEM-9702-a", 3, now=T0)
    c.record("recall", "SEM-9702-a", 1, now=T0 + timedelta(days=9))
    c.due(T0)
    c.stats(T0)
    assert {p: p.read_text() for p in snapshots} == snapshots
    assert sorted(p.name for p in (vault.tutor / "state").iterdir()) == ["learner.json"]
    assert sorted(p.name for p in (vault.tutor / "events").iterdir()) == ["2026-10.jsonl"]
    assert "model" not in sc.__dict__
