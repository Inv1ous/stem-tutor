import json
import random
from datetime import datetime

import pytest

from fixtures import make_vault
from tutorlib import challenge as ch
from tutorlib import model, packs as packs_mod, report, session, store

T0 = datetime.fromisoformat("2026-10-08T15:30:12+08:00")


def kc(i, sub, spec, prereqs=(), subject="phys"):
    return {"id": i, "subtopic": sub, "title": f"Idea {i}", "statement": f"state {i}", "level": "AS",
            "type": "procedural", "prereqs": list(prereqs), "glossary": []}


def graph(spec, subject, subs, kcs):
    return {"spec": spec, "subject": subject, "title": spec, "version": "x", "topics": [],
            "subtopics": [{"id": s, "title": f"Chapter {s}", "topic": s.split(".")[0]} for s in subs], "kcs": kcs}


GRAPHS = {
    "9702": graph("9702", "phys", ["9702-2.1", "9702-3.1", "9702-5.1", "9702-10.1"], [
        kc("9702-2.1.1", "9702-2.1", "9702"), kc("9702-3.1.1", "9702-3.1", "9702"),
        kc("9702-5.1.1", "9702-5.1", "9702", ["P1-1.2"]), kc("9702-5.1.2", "9702-5.1", "9702", ["9702-5.1.1"]),
        kc("9702-10.1.1", "9702-10.1", "9702")]),
    "9701": graph("9701", "chem", ["9701-3.1", "9701-3.2"], [
        kc("9701-3.1.1", "9701-3.1", "9701"), kc("9701-3.2.1", "9701-3.2", "9701")]),
    "P1": graph("P1", "math", ["P1-1", "P1-2"], [
        kc("P1-1.1", "P1-1", "P1"), kc("P1-1.2", "P1-1", "P1", ["P1-1.1"]), kc("P1-2.1", "P1-2", "P1", ["P1-1.2"])]),
    "P2": graph("P2", "math", ["P2-1"], [kc("P2-1.1", "P2-1", "P2", ["P1-2.1"])]),
}
GRAPHS["9702"]["topics"] = [{"id": "9702-5", "title": "Work", "level": "AS"}]


@pytest.fixture
def vault(tmp_path):
    root = make_vault(tmp_path)
    base = root / ".tutor/packs/v1"
    (base / "manifest.json").write_text(json.dumps({"version": "v1", "specs": list(GRAPHS)}))
    for spec, g in GRAPHS.items():
        (base / "specs" / spec / "packs").mkdir(parents=True, exist_ok=True)
        (base / "specs" / spec / "graph.json").write_text(json.dumps(g))
    (base / "specs/9702/packs/9702-5.1.json").write_text(json.dumps({"subtopic": "9702-5.1", "items": []}))
    return store.Vault(root)


@pytest.fixture
def packs(vault):
    return packs_mod.Packs(vault)


# ---------- levels and ramps ----------
def test_levels_cover_one_to_ten_with_text():
    assert [x["level"] for x in ch.LEVELS] == list(range(1, 11))
    assert [x["name"] for x in ch.LEVELS][:2] == ["Warm-up", "Standard"] and ch.LEVELS[9]["name"] == "Impossible"
    assert all(x["blurb"] and x["exam_chance"] for x in ch.LEVELS)


def test_ramps_have_descriptions():
    assert set(ch.RAMPS) == {"steady", "fast-then-slow", "slow-then-fast", "hardest-first", "easiest-first-jump",
                             "wave", "random", "flat"}
    assert all(ch.RAMPS.values())


@pytest.mark.parametrize("shape", sorted(ch.RAMPS))
@pytest.mark.parametrize("n", [1, 2, 3, 7, 10, 30])
@pytest.mark.parametrize("lo,hi", [(1, 10), (4, 8), (6, 6), (9, 10)])
def test_ramp_length_and_bounds(shape, n, lo, hi):
    got = ch.ramp_levels(n, shape, lo, hi)
    assert len(got) == n and all(lo <= x <= hi for x in got)


@pytest.mark.parametrize("n", [2, 3, 10, 30])
def test_ramp_monotone_where_named(n):
    for shape in ("steady", "fast-then-slow", "slow-then-fast"):
        got = ch.ramp_levels(n, shape, 1, 10)
        assert got == sorted(got) and got[0] == 1 and got[-1] == 10
    down = ch.ramp_levels(n, "hardest-first", 2, 9)
    assert down == sorted(down, reverse=True) and down[0] == 9 and down[-1] == 2
    assert ch.ramp_levels(n, "flat", 3, 9) == [9] * n


def test_fast_then_slow_gains_more_early_than_late():
    for n in (9, 12, 20, 30):
        got = ch.ramp_levels(n, "fast-then-slow", 1, 10)
        third = n // 3
        assert got[third] - got[0] > got[-1] - got[-1 - third]
    mirror = ch.ramp_levels(12, "slow-then-fast", 1, 10)
    assert mirror[4] - mirror[0] < mirror[-1] - mirror[-5]


def test_easiest_first_jump_and_wave_and_random():
    got = ch.ramp_levels(8, "easiest-first-jump", 1, 10)
    assert got[0] == 1 and got[1] >= 5 and got[-1] == 10 and got[1:] == sorted(got[1:])
    wave = ch.ramp_levels(12, "wave", 1, 10)
    assert any(b < a for a, b in zip(wave, wave[1:])) and wave[-1] > wave[0]
    a, b = ch.ramp_levels(20, "random", 1, 10, seed=3), ch.ramp_levels(20, "random", 1, 10, seed=3)
    assert a == b and sorted(a) == ch.ramp_levels(20, "steady", 1, 10)


def test_single_question_is_at_hi_and_odd_input_is_safe():
    assert ch.ramp_levels(1, "steady", 4, 8) == [8] and ch.ramp_levels(1, "hardest-first", 4, 8) == [8]
    assert ch.ramp_levels(0, "steady", 4, 8) == []
    assert ch.ramp_levels(3, "nonsense", 9, 2) == ch.ramp_levels(3, "steady", 2, 9)
    assert ch.ramp_levels(2, "steady", -5, 99) == [1, 10]


# ---------- config ----------
def test_default_config_is_already_normal(packs):
    cfg, notes = ch.normalise_config(ch.DEFAULT_CONFIG, packs)
    assert cfg == ch.DEFAULT_CONFIG and notes == []


def test_normalise_clamps_and_explains(packs):
    cfg, notes = ch.normalise_config({"topics": ["9702-5.1", "nope", "9702-5.1"], "count": 99, "lo": 9, "hi": 2,
                                      "typed_share": 1.7, "kinds": "MCQ ", "model": "gpt", "ramp": "Fast Then Slow"}, packs)
    assert cfg["topics"] == ["9702-5.1"] and cfg["count"] == 30 and (cfg["lo"], cfg["hi"]) == (2, 9)
    assert cfg["typed_share"] == 1.0 and cfg["kinds"] == "mcq" and cfg["model"] == "sonnet"
    assert cfg["ramp"] == "fast-then-slow"
    text = " ".join(notes)
    assert "nope" in text and "30" in text and "model" in text and len(notes) >= 5


def test_normalise_range_and_garbage(packs):
    cfg, notes = ch.normalise_config({"lo": 0, "hi": 40, "count": "abc", "typed_share": "x", "colour": "red"}, packs)
    assert (cfg["lo"], cfg["hi"]) == (1, 10) and cfg["count"] == 10 and cfg["typed_share"] == 0.5
    assert "colour" not in cfg and notes
    cfg, _ = ch.normalise_config({"count": 0}, packs)
    assert cfg["count"] == 1


def test_plan_slots_kinds_exact_and_not_clumped():
    for n in (1, 2, 5, 10, 17, 30):
        for share in (0.0, 0.25, 0.5, 0.75, 1.0):
            cfg = {**ch.DEFAULT_CONFIG, "count": n, "typed_share": share}
            slots = ch.plan_slots(cfg)
            want = int(n * share + 0.5)
            assert [s["n"] for s in slots] == list(range(1, n + 1))
            assert sum(s["kind"] == "typed" for s in slots) == want
    half = [s["kind"] for s in ch.plan_slots({**ch.DEFAULT_CONFIG, "count": 10})]
    assert half == ["mcq", "typed"] * 5
    third = [s["kind"] for s in ch.plan_slots({**ch.DEFAULT_CONFIG, "count": 12, "typed_share": 0.25})]
    assert not any(a == b == "typed" for a, b in zip(third, third[1:]))


def test_plan_slots_pure_kinds_and_levels():
    cfg = {**ch.DEFAULT_CONFIG, "count": 6, "kinds": "typed", "typed_share": 0.0, "ramp": "hardest-first", "lo": 3, "hi": 8}
    slots = ch.plan_slots(cfg)
    assert {s["kind"] for s in slots} == {"typed"} and slots[0]["level"] == 8 and slots[-1]["level"] == 3
    assert {s["kind"] for s in ch.plan_slots({**cfg, "kinds": "mcq", "typed_share": 1.0})} == {"mcq"}
    r = {**cfg, "ramp": "random"}
    assert ch.plan_slots(r, seed=1) == ch.plan_slots(r, seed=1)


# ---------- scope ----------
def ids(scope):
    return [k["id"] for k in scope]


def test_scope_includes_earlier_chapters_not_later(packs):
    got = ids(ch.allowed_scope(packs, ["9702-3.1"]))
    assert "9702-2.1.1" in got and "9702-3.1.1" in got
    assert "9702-5.1.1" not in got and "9702-10.1.1" not in got


def test_scope_orders_numerically_not_lexicographically(packs):
    five = ids(ch.allowed_scope(packs, ["9702-5.1"]))
    assert "9702-10.1.1" not in five
    ten = ids(ch.allowed_scope(packs, ["9702-10.1"]))
    assert {"9702-2.1.1", "9702-3.1.1", "9702-5.1.1", "9702-5.1.2", "9702-10.1.1"} <= set(ten)


def test_scope_prereq_closure_crosses_specs(packs):
    got = ids(ch.allowed_scope(packs, ["9702-5.1"]))
    assert "P1-1.2" in got and "P1-1.1" in got  # physics 5.1 needs maths, and what that needs
    assert "P1-2.1" not in got and "9701-3.1.1" not in got


def test_scope_maths_units_are_chaptered_within_a_unit(packs):
    assert ids(ch.allowed_scope(packs, ["P1-1"])) == ["P1-1.1", "P1-1.2"]
    got = ids(ch.allowed_scope(packs, ["P2-1"]))
    assert got == ["P1-1.1", "P1-1.2", "P1-2.1", "P2-1.1"]  # P1 comes in through the stated prereq chain


def test_scope_fields_flags_dedupe_and_unknown(packs):
    scope = ch.allowed_scope(packs, ["9702-5.1", "9702-5.1", "9702-3.1", "bogus"])
    assert len(ids(scope)) == len(set(ids(scope)))
    one = next(k for k in scope if k["id"] == "9702-5.1.1")
    assert {"id", "spec", "subtopic", "title", "statement"} <= set(one) and one["chosen"] is True
    assert next(k for k in scope if k["id"] == "9702-2.1.1")["chosen"] is False
    assert ch.allowed_scope(packs, []) == [] and ch.allowed_scope(packs, ["bogus"]) == []


def test_scope_summary(packs):
    assert ch.scope_summary(packs, ["9702-5.1"]) == "Physics 9702-5.1 plus earlier chapters (6 ideas)"
    assert ch.scope_summary(packs, ["P1-1"]) == "Maths P1-1 (2 ideas)"
    assert ch.scope_summary(packs, []) == "No topics chosen"
    assert ch.scope_summary(packs, ["9701-3.1", "9702-2.1"]).startswith("Chemistry 9701-3.1; Physics 9702-2.1")


def test_topic_choices_sorted_built_and_labelled(packs):
    rows = ch.topic_choices(packs)
    order = [r["id"] for r in rows]
    assert order.index("9702-5.1") < order.index("9702-10.1")
    assert order.index("9701-3.2") < order.index("9702-2.1") < order.index("P1-1")
    five = next(r for r in rows if r["id"] == "9702-5.1")
    assert five == {"id": "9702-5.1", "spec": "9702", "title": "Chapter 9702-5.1", "built": True,
                    "label": "9702-5.1  Chapter 9702-5.1"}
    assert next(r for r in rows if r["id"] == "9702-10.1")["built"] is False


# ---------- plain-English requests ----------
def parse(packs, text):
    return ch.parse_request(text, packs)


def test_parse_the_headline_example(packs):
    r = parse(packs, "10 hard mcq questions on 9702-5.1 with opus")
    assert r["config"] == {"topics": ["9702-5.1"], "model": "opus", "count": 10, "kinds": "mcq"}
    assert r["unclear"] == [] and r["understood"]


def test_parse_ramp_sentence(packs):
    r = parse(packs, "twenty questions, start easy, jump quickly to hard, then slowly to extreme")
    c = r["config"]
    assert c["count"] == 20 and c["ramp"] == "fast-then-slow" and c["lo"] == 1 and c["hi"] == 9
    assert r["unclear"] == []


def test_parse_only_typed_impossible(packs):
    c = parse(packs, "only typed, impossible level")["config"]
    assert c == {"kinds": "typed", "lo": 10, "hi": 10}


def test_parse_level_range_and_hardest_first(packs):
    r = parse(packs, "levels 6 to 9, hardest first")
    assert r["config"] == {"lo": 6, "hi": 9, "ramp": "hardest-first"} and r["unclear"] == []


def test_parse_chapter_resolution(packs):
    assert parse(packs, "chapter 3.1 chemistry")["config"]["topics"] == ["9701-3.1"]
    assert parse(packs, "physics 3.1")["config"]["topics"] == ["9702-3.1"]
    assert parse(packs, "chapter 2.1")["config"]["topics"] == ["9702-2.1"]  # only physics has a 2.1
    none = parse(packs, "chapter 40.1 chemistry")
    assert "topics" not in none["config"] and none["unclear"]


def test_parse_ambiguous_chapter_lists_choices(packs):
    r = parse(packs, "chapter 3.1")
    assert "topics" not in r["config"]
    assert "9701-3.1" in r["unclear"][0] and "9702-3.1" in r["unclear"][0]


def test_parse_whole_chapter_by_number(packs):
    r = parse(packs, "9702-5")
    assert r["config"]["topics"] == ["9702-5.1"]
    assert parse(packs, "p1-2")["config"]["topics"] == ["P1-2"]


@pytest.mark.parametrize("text,expect", [
    ("mix", {"kinds": "mix", "typed_share": 0.5}),
    ("half and half", {"kinds": "mix", "typed_share": 0.5}),
    ("mostly typed", {"kinds": "mix", "typed_share": 0.75}),
    ("mostly multiple choice", {"kinds": "mix", "typed_share": 0.25}),
    ("30% typed", {"kinds": "mix", "typed_share": 0.3}),
    ("only mcq", {"kinds": "mcq"}),
    ("typed answers please", {"kinds": "typed"}),
    ("flat at extreme", {"ramp": "flat", "lo": 9, "hi": 9}),
    ("a wave of difficulty", {"ramp": "wave"}),
    ("random order", {"ramp": "random"}),
    ("easiest first then jump", {"ramp": "easiest-first-jump"}),
    ("slowly at first then a fast climb", {"ramp": "slow-then-fast"}),
    ("steady climb", {"ramp": "steady"}),
    ("up to level 8", {"hi": 8}),
    ("from level 4", {"lo": 4}),
    ("rare in exams", {"lo": 7, "hi": 7}),
    ("from warm-up to beyond", {"lo": 1, "hi": 8}),
    ("level 3", {"lo": 3, "hi": 3}),
    ("use sonnet", {"model": "sonnet"}),
    ("twenty-five questions", {"count": 25}),
    ("thirty questions", {"count": 30}),
    ("7 q", {"count": 7}),
    ("three hard calculation problems", {"count": 3}),
])
def test_parse_phrasings(packs, text, expect):
    r = parse(packs, text)
    assert r["config"] == pytest.approx(expect), r
    assert r["unclear"] == [], r


def test_parse_unclear_and_never_raises(packs):
    r = parse(packs, "make me a sandwich about physics")
    assert r["unclear"] and r["config"] == {}
    both = parse(packs, "opus or sonnet")
    assert both["unclear"] and "model" not in both["config"]
    for junk in ("", "   ", "???", "9702-99.9", "level", "levels 9 to", "-", None, 42):
        out = parse(packs, junk)
        assert set(out) == {"config", "understood", "unclear"}


def test_parse_result_feeds_normalise(packs):
    r = parse(packs, "40 questions on 9702-5.1, levels 9 to 3, opus")
    cfg, notes = ch.normalise_config({**ch.DEFAULT_CONFIG, **r["config"]}, packs)
    assert cfg["count"] == 30 and (cfg["lo"], cfg["hi"]) == (3, 9) and cfg["model"] == "opus" and notes


# ---------- stored sets ----------
def questions(n=4):
    return [{"n": i + 1, "level": 3 + 2 * i, "kind": "mcq" if i % 2 else "typed", "item": {"id": f"c{i}"},
             "solution": "s", "concepts": ["9702-5.1.1"]} for i in range(n)]


@pytest.fixture
def cs(vault):
    return ch.ChallengeSet.new(vault, {**ch.DEFAULT_CONFIG, "topics": ["9702-5.1"], "count": 4}, questions())


def test_set_is_created_lazily_and_round_trips(vault):
    assert not (vault.tutor / "challenge").exists()
    assert ch.ChallengeSet.open_latest_unfinished(vault) is None and ch.ChallengeSet.all(vault) == []
    s = ch.ChallengeSet.new(vault, {"topics": ["9702-5.1"], "count": 4}, questions())
    assert len(s.id) == 15 and s.id[8] == "-" and s.cursor == 0 and s.answers == []
    again = ch.ChallengeSet(vault, s.id)
    assert again.questions == s.questions and again.cfg == s.cfg and again.id == s.id and again.created == s.created
    with pytest.raises(FileNotFoundError):
        ch.ChallengeSet(vault, "19990101-000000")


def test_record_survives_restart_and_moves_cursor(vault, cs):
    cs.record(0, "12.5", {"correct": True, "score": 1.0}, 40, confidence=4)
    cs.record(1, "B", {"correct": False, "score": 0.0}, 25)
    assert cs.cursor == 2
    back = ch.ChallengeSet(vault, cs.id)
    assert back.cursor == 2 and [a["response"] for a in back.answers] == ["12.5", "B"]
    assert back.answers[0]["confidence"] == 4 and back.answers[1]["confidence"] is None
    assert ch.ChallengeSet.open_latest_unfinished(vault).id == cs.id
    with pytest.raises(IndexError):
        cs.record(9, "x", {"correct": True}, 1)


def test_answering_out_of_order_and_again(cs):
    cs.record(2, "a", {"correct": False}, 5)
    assert cs.cursor == 0
    cs.record(2, "b", {"correct": True}, 6)
    assert len(cs.answers) == 1 and cs.answers[0]["response"] == "b"


def test_summary(cs):
    cs.record(0, "1", {"correct": True}, 30)   # level 3
    cs.record(1, "B", {"correct": False}, 20)  # level 5
    cs.record(2, "2", {"correct": True}, 50)   # level 7
    assert cs.summary() == {"answered": 3, "correct": 2, "by_level": {3: [1, 1], 5: [0, 1], 7: [1, 1]},
                            "best_level": 7, "seconds": 100}
    empty = ch.ChallengeSet.new(cs.vault, {}, questions(2)).summary()
    assert empty["answered"] == 0 and empty["best_level"] is None and empty["by_level"] == {}


def test_regrade(vault, cs):
    cs.record(1, "42", {"correct": False, "score": 0.0}, 10)
    cs.regrade(1, "equivalent form")
    back = ch.ChallengeSet(vault, cs.id)
    assert back.answers[0]["grade"]["correct"] is True and back.answers[0]["regraded"] == "equivalent form"
    assert back.summary()["correct"] == 1
    with pytest.raises(ValueError):
        cs.regrade(3, "never answered")
    types = [e["type"] for e in vault.events()]
    assert types == ["challenge", "challenge_regrade"]


def test_all_and_open_latest_unfinished(vault):
    a = ch.ChallengeSet.new(vault, {"topics": ["9702-5.1"]}, questions(2))
    b = ch.ChallengeSet(vault)
    b.id = "29991231-000000"
    b.cfg, b.questions = {"topics": ["9701-3.1"]}, questions(2)
    b._save()
    for i in range(2):
        a.record(i, "x", {"correct": i == 0}, 3)
    rows = ch.ChallengeSet.all(vault)
    assert [r["id"] for r in rows] == [b.id, a.id]
    assert rows[1] == {"id": a.id, "created": a.created, "count": 2, "answered": 2, "correct": 1, "topics": ["9702-5.1"]}
    assert ch.ChallengeSet.open_latest_unfinished(vault).id == b.id
    b.record(0, "x", {"correct": True}, 1)
    b.record(1, "x", {"correct": True}, 1)
    assert ch.ChallengeSet.open_latest_unfinished(vault) is None


def test_damaged_file_is_skipped(vault, cs):
    (vault.tutor / "challenge" / "20000101-000000.json").write_text("{torn")
    assert [r["id"] for r in ch.ChallengeSet.all(vault)] == [cs.id]


def test_saves_are_atomic_and_leave_no_temp_files(vault, cs):
    cs.record(0, "1", {"correct": True}, 1)
    names = sorted(p.name for p in (vault.tutor / "challenge").iterdir())
    assert names == [f"{cs.id}.json"]
    json.loads((vault.tutor / "challenge" / f"{cs.id}.json").read_text())


def test_save_goes_through_store_write_text(monkeypatch, vault, cs):
    calls = []
    real = store.write_text
    monkeypatch.setattr("tutorlib.challenge.write_json", lambda p, d, indent=1: (calls.append(p), real(p, json.dumps(d)))[1])
    cs.record(0, "1", {"correct": True}, 1)
    assert calls == [cs.path]


# ---------- challenge events must not disturb the learner's record ----------
def test_challenge_events_do_not_change_learner_state(vault, cs, packs):
    def fold():
        s = model.new_state()
        for e in vault.events():
            model.apply(s, e)
        s.pop("last_event")
        return s

    before = fold()
    cs.record(0, "1", {"correct": True}, 30, confidence=5)
    cs.record(1, "B", {"correct": False}, 30)
    cs.regrade(1, "fine")
    assert fold() == before
    assert [e["type"] for e in vault.events()] == ["challenge", "challenge", "challenge_regrade"]


def test_challenge_events_do_not_break_sessions_or_reports(vault, cs):
    rnd = random.Random(0)
    t = session.Tutor(vault, rng=rnd, now=lambda: T0)
    cs.record(0, "1", {"correct": True}, 30)
    cs.regrade(0, "why")
    t = session.Tutor(vault, rng=rnd, now=lambda: T0)  # restart on a log that has challenge events
    assert t.rebuild()["events"] == 2
    assert "session" in t.start("autopilot", 20)
    t.end()
    report.mistakes_note(t)
    report.today_note(t)
    report.profile_note(t)


# ---------- ramp phrasings ----------
@pytest.mark.parametrize("text", [
    "start easy, jump to hard fast, end extreme",
    "jump to hard fast then slowly to extreme",
    "quick jump to hard, slow creep to extreme",
])
def test_parse_fast_then_slow_phrasings(packs, text):
    r = parse(packs, text)
    c = r["config"]
    assert c["ramp"] == "fast-then-slow" and c["hi"] == 9 and c["lo"] <= 5, r
    assert r["unclear"] == [], r


def test_parse_start_easy_is_a_low_floor(packs):
    c = parse(packs, "start easy, jump to hard fast, end extreme")["config"]
    assert c["lo"] <= 2 and c["hi"] == 9


@pytest.mark.parametrize("text,expect", [
    ("start with the hardest", {"ramp": "hardest-first"}),
    ("hardest first", {"ramp": "hardest-first"}),
    ("start extreme and get easier", {"ramp": "hardest-first", "hi": 9}),
    ("slow start then ramp up quickly", {"ramp": "slow-then-fast"}),
    ("ease in then jump", {"ramp": "slow-then-fast"}),
    ("gradually harder", {"ramp": "steady"}),
    ("steadily increasing", {"ramp": "steady"}),
    ("ramp up evenly", {"ramp": "steady"}),
    ("all at extreme", {"ramp": "flat", "lo": 9, "hi": 9}),
    ("all the same level", {"ramp": "flat"}),
    ("up and down", {"ramp": "wave"}),
    ("ups and downs", {"ramp": "wave"}),
    ("mixed difficulty", {"ramp": "random"}),
    ("shuffled", {"ramp": "random"}),
    ("build up to impossible", {"ramp": "steady", "hi": 10}),
])
def test_parse_ramp_phrasings(packs, text, expect):
    r = parse(packs, text)
    assert r["config"] == expect, r
    assert r["unclear"] == [], r
