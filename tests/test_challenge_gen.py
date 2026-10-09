import asyncio
import random
import sys
import types
from collections import Counter

import pytest

from tutorlib import challenge_gen as cg

SCOPE = [
    {"id": "9702-2.1.1", "spec": "9702", "subtopic": "9702-2.1", "title": "Equations of motion",
     "statement": "derive and use the equations of uniformly accelerated motion"},
    {"id": "9702-3.1.1", "spec": "9702", "subtopic": "9702-3.1", "title": "Newton's second law",
     "statement": "use F = ma for a constant mass"},
    {"id": "9702-5.1.1", "spec": "9702", "subtopic": "9702-5.1", "title": "Work done by a force",
     "statement": "understand the concept of work, and recall and use W = Fs"},
    {"id": "9702-5.1.2", "spec": "9702", "subtopic": "9702-5.1", "title": "Kinetic energy",
     "statement": "derive and use Ek = 1/2 mv^2"},
]
CFG = {"model": "sonnet", "topics": ["9702-5.1"]}
MCQ = {"n": 1, "level": 5, "kind": "mcq"}
TYPED = {"n": 2, "level": 5, "kind": "typed"}
STEM = ("A 2.0 kg block is pushed 3.0 m from rest along a rough horizontal floor by a horizontal force of 10 N. "
        "The frictional force on it is 4.0 N. What is the kinetic energy of the block at the end?")


def raw_mcq(**kw):
    return {"stem": STEM, "correct": "18 J",
            "wrong": [{"text": "30 J", "mistake": "ignored friction"}, {"text": "12 J", "mistake": "used friction"},
                      {"text": "42 J", "mistake": "added the forces"}],
            "solution": "Resultant force = 10 - 4.0 = 6.0 N, so work done on it = 6.0 x 3.0 = 18 J = kinetic energy.",
            "concepts": ["9702-5.1.1", "9702-5.1.2"], **kw}


def raw_typed(**kw):
    return {"stem": STEM + " Give your answer to 2 significant figures.", "value": 18.0, "unit": "J", "sf": 2,
            "solution": "Resultant force = 6.0 N; work = 6.0 x 3.0 = 18 J.", "concepts": ["9702-5.1.1"], **kw}


# ---------------- to_item ----------------
def test_mcq_becomes_a_grade_ready_item():
    q = cg.to_item(raw_mcq(), MCQ, SCOPE, random.Random(1))
    it = q["item"]
    assert sorted(it["options"]) == ["A", "B", "C", "D"] and it["options"][it["answer"]] == "18 J"
    assert it["kind"] == "mcq" and it["kcs"][0] == "9702-5.1.1" and it["id"].startswith("ch-1-")
    assert len(it["id"]) == len("ch-1-") + 6 and it["stem"] == STEM and it["explanation"]
    assert q["n"] == 1 and q["level"] == 5 and q["kind"] == "mcq" and q["concepts"] == ["9702-5.1.1", "9702-5.1.2"]


def test_typed_becomes_a_numeric_item():
    q = cg.to_item(raw_typed(), TYPED, SCOPE, random.Random(1))
    assert q["item"]["kind"] == "numeric" and q["item"]["answer"] == {"value": 18.0, "unit": "J", "sf": 2}
    assert "options" not in q["item"]


def test_a_typed_stem_without_its_precision_is_told_it():
    q = cg.to_item(raw_typed(stem=STEM), TYPED, SCOPE, random.Random(1))
    assert q["item"]["stem"].endswith("Give your answer in J to 2 significant figures.")


def test_the_correct_letter_is_uniform_over_seeds():
    letters = Counter(cg.to_item(raw_mcq(), MCQ, SCOPE, random.Random(s))["item"]["answer"] for s in range(800))
    assert set(letters) == set("ABCD") and min(letters.values()) > 150


@pytest.mark.parametrize("raw, slot, why", [
    (raw_mcq(stem="Too short?"), MCQ, "stem"),
    (raw_mcq(wrong=[{"text": "30 J"}, {"text": "12 J"}]), MCQ, "3 wrong"),
    (raw_mcq(wrong=[{"text": "30 J"}, {"text": "18  j"}, {"text": "42 J"}]), MCQ, "distinct"),
    (raw_mcq(wrong=[{"text": "30 J"}, {"text": "12 J"}, {"text": "about forty"}]), MCQ, "format"),
    (raw_mcq(correct=""), MCQ, "correct"),
    (raw_mcq(solution="So the answer is option C."), MCQ, "letter"),
    (raw_mcq(solution="(B) is right because 6.0 x 3.0 = 18 J"), MCQ, "letter"),
    (raw_mcq(solution=""), MCQ, "solution"),
    (raw_mcq(concepts=["9702-6.1.1"]), MCQ, "outside"),
    (raw_mcq(concepts=[]), MCQ, "concepts"),
    (raw_mcq(stem=STEM + " Use the graph shown below."), MCQ, "figure"),
    (raw_mcq(stem="Explain why the kinetic energy of a block pushed along a rough floor is less than the work."),
     MCQ, "calculation"),
    (raw_typed(value=float("inf")), TYPED, "value"),
    (raw_typed(value=None), TYPED, "value"),
    (raw_typed(value=True), TYPED, "value"),
    (raw_typed(unit="furlongs fortnight^-1"), TYPED, "unit"),
    (raw_typed(sf=0), TYPED, "s.f."),
    (raw_typed(sf=9), TYPED, "s.f."),
    (raw_typed(value=None, expr="2*x"), TYPED, "value"),  # an expression only on a maths spec that asks for one
])
def test_bad_questions_are_refused_with_a_reason(raw, slot, why):
    with pytest.raises(cg.BadQuestion, match=why):
        cg.to_item(raw, slot, SCOPE, random.Random(0))


def test_basic_maths_is_not_a_syllabus_concept():
    q = cg.to_item(raw_mcq(concepts=["9702-5.1.1", "basic arithmetic/algebra"]), MCQ, SCOPE, random.Random(0))
    assert q["concepts"] == ["9702-5.1.1"]


def test_an_exact_typed_answer_needs_no_figures():
    q = cg.to_item(raw_typed(value=4, unit="", sf=None, exact=True, stem=STEM.replace("What is the kinetic energy",
                   "How many whole metres has it moved")), TYPED, SCOPE, random.Random(0))
    assert q["item"]["answer"] == {"value": 4.0, "exact": True}


def test_expressions_only_on_maths_specs_that_ask_for_them():
    scope = [{"id": "P3.1.1", "spec": "P3", "subtopic": "P3.1", "title": "Partial fractions", "statement": "use them"}]
    raw = {"stem": "Find the derivative of x^3 sin x with respect to x, simplified fully as one expression.",
           "expr": "3x^2 sin x + x^3 cos x", "solution": "Product rule.", "concepts": ["P3.1.1"]}
    q = cg.to_item(raw, TYPED, scope, random.Random(0), cfg={"maths_forms": True})
    assert q["item"]["kind"] == "expression" and q["item"]["answer"] == {"expr": "3x^2 sin x + x^3 cos x"}
    with pytest.raises(cg.BadQuestion):
        cg.to_item(raw, TYPED, scope, random.Random(0), cfg={})
    with pytest.raises(cg.BadQuestion):
        cg.to_item({**raw, "expr": "3x^^2 sin("}, TYPED, scope, random.Random(0), cfg={"maths_forms": True})


# ---------------- agrees ----------------
def test_agrees_marks_the_blind_solve_with_the_real_grader():
    q = cg.to_item(raw_mcq(), MCQ, SCOPE, random.Random(3))
    right = q["item"]["answer"]
    wrong = next(k for k in "ABCD" if k != right)
    assert cg.agrees(q, {"answer": right}) and cg.agrees(q, {"answer": f"({right.lower()})"})
    assert not cg.agrees(q, {"answer": wrong}) and not cg.agrees(q, {"answer": ""}) and not cg.agrees(q, {})


@pytest.mark.parametrize("said, ok", [("18 J", True), ("18.1 J", True), ("17.95", True), ("0.018 kJ", True),
                                      ("18 N", False), ("17 J", False), ("1.8e1 J", True), ("idk", False)])
def test_agrees_on_typed_answers_uses_the_tolerance_and_units(said, ok):
    q = cg.to_item(raw_typed(), TYPED, SCOPE, random.Random(0))
    assert cg.agrees(q, {"answer": said}) is ok


# ---------------- prompts ----------------
def test_generation_prompt_carries_level_scope_rules_and_earlier_stems():
    p = cg.generation_prompt({"n": 1, "level": 9, "kind": "typed"}, SCOPE, CFG, ["A crate slides down a ramp..."])
    assert "9702-5.1.2" in p and "W = Fs" in p and "Extreme" in p and "A crate slides down a ramp" in p
    assert "significant figures" in p and "CAIE 9702" in p and "explain" in p.lower()  # calculation only
    m = cg.generation_prompt(MCQ, SCOPE, CFG, [])
    assert "option letters" in m and "mistake" in m and "significant figures" not in m


def test_a_huge_scope_keeps_full_statements_only_for_the_chosen_chapters():
    big = [{"id": f"9702-1.{i}.{j}", "spec": "9702", "subtopic": f"9702-1.{i}", "title": f"Idea {i}.{j}",
            "statement": "a long syllabus statement " * 8} for i in range(1, 30) for j in range(1, 6)] + SCOPE
    p = cg.generation_prompt(MCQ, big, CFG, [])
    assert "9702-1.3.2" in p and "use W = Fs" in p and p.count("a long syllabus statement") < 20
    assert len(p) < 16000


def test_solve_prompt_is_blind_and_audit_prompt_is_not_anchored():
    q = cg.to_item(raw_mcq(), MCQ, SCOPE, random.Random(0))
    s = cg.solve_prompt(q)
    assert STEM in s and "30 J" in s and "Resultant force" not in s and "ignored friction" not in s
    a = cg.audit_prompt(q, SCOPE)
    assert "Resultant force" in a and "9702-5.1.1" in a and "Impossible" in a and "level 5" not in a.lower()


# ---------------- make_question ----------------
GOOD_AUDIT = {"working": "checked", "solution_correct": True, "concepts": [
    {"idea": "work", "kc": "9702-5.1.1"}, {"idea": "subtraction", "kc": "basic"}], "out_of_scope": [],
    "rated_level": 5, "problems": []}


class FakeAI:
    """Canned replies by which call it is: generate, solve, audit or recheck (the second blind solve). A list is used
    up in order."""

    def __init__(self, gen=None, solve=None, audit=None, refuse=(), recheck=None):
        self.refuse = set(refuse)  # (model, call) pairs the model declines
        self.replies = {"gen": gen or [raw_mcq()], "solve": solve or ["?"], "audit": audit or [GOOD_AUDIT],
                        "recheck": recheck or ["?"]}
        self.calls, self.prompts, self.models, self.schemas = [], [], [], []
        self.live = self.peak = 0

    async def __call__(self, prompt, schema, model, timeout=120):
        which = {id(cg.GENERATE_SCHEMA): "gen", id(cg.GENERATE_MCQ_SCHEMA): "gen", id(cg.SOLVE_SCHEMA): "solve",
                 id(cg.AUDIT_SCHEMA): "audit"}[id(schema)]
        which = "recheck" if which == "solve" and "Take your time" in prompt else which
        self.schemas.append(schema)
        self.calls.append(which)
        self.prompts.append(prompt)
        self.models.append(model)
        self.live += 1
        self.peak = max(self.peak, self.live)
        await asyncio.sleep(0.01)
        self.live -= 1
        if (model, which) in self.refuse:
            raise cg.Refused(f"{model} safeguards flagged this message")
        got = self.replies[which]
        r = got.pop(0) if len(got) > 1 else got[0]
        if which in ("solve", "recheck") and r == "?":  # answer the shown question right: find the correct option's letter
            opts = dict(line.split(") ", 1) for line in prompt.splitlines() if line[:2] in ("A)", "B)", "C)", "D)"))
            return {"working": "w", "answer": next((k for k, v in opts.items() if v == "18 J"), "18 J")}
        return r


def run(ai, slot=MCQ, cfg=CFG, stems=None, log=None):
    log = [] if log is None else log
    return asyncio.run(cg.make_question(ai, slot, SCOPE, cfg, stems or [], log)), log


def test_happy_path_costs_three_calls():
    ai = FakeAI()
    q, log = run(ai)
    assert q and ai.calls == ["gen", "solve", "audit"] and q["rated"] == 5 and q["item"]["kind"] == "mcq"
    assert ai.models == ["sonnet", "opus", "sonnet"] and len(log) == 1 and "accepted" in log[0]


def test_an_mcq_is_asked_for_with_its_options_required():
    ai = FakeAI(gen=[raw_typed()])
    run(ai)
    run(ai, slot=TYPED)
    assert ai.schemas[0] is cg.GENERATE_MCQ_SCHEMA and {"correct", "wrong"} <= set(ai.schemas[0]["required"])
    assert ai.schemas[-3] is cg.GENERATE_SCHEMA


def test_an_opus_question_is_solved_by_sonnet():
    ai = FakeAI()
    run(ai, cfg={**CFG, "model": "opus"})
    assert ai.models == ["opus", "sonnet", "opus"]


def test_a_solver_that_disagrees_sends_the_reason_into_the_next_attempt():
    ai = FakeAI(solve=[{"working": "w", "answer": "Z"}, "?"])
    q, log = run(ai)
    assert q and ai.calls == ["gen", "solve", "gen", "solve", "audit"]
    assert "rejected" in ai.prompts[2].lower() and "solver" in ai.prompts[2].lower() and len(log) == 2


L9 = {"n": 1, "level": 9, "kind": "mcq"}
MISS = {"working": "w", "answer": "Z"}


def test_a_hard_miss_is_kept_only_when_rated_hard_and_a_second_blind_solve_agrees():
    ai = FakeAI(solve=[MISS], audit=[{**GOOD_AUDIT, "rated_level": 9}])
    q, _ = run(ai, slot=L9)
    assert q and ai.calls == ["gen", "solve", "audit", "recheck"] and q["checks"] == ["audit", "recheck"]
    assert ai.models == ["sonnet", "opus", "sonnet", "opus"] and q["solver_missed"]
    assert "Resultant force" not in ai.prompts[3] and "KEY" not in ai.prompts[3]  # blind: no key, no solution


@pytest.mark.parametrize("why, ai, slot", [
    ("rated below 8", FakeAI(solve=[MISS], audit=[{**GOOD_AUDIT, "rated_level": 7}]), {**L9, "level": 8}),
    ("requested below 8", FakeAI(solve=[MISS], audit=[{**GOOD_AUDIT, "rated_level": 8}]), {**L9, "level": 7}),
    ("second solve disagrees", FakeAI(solve=[MISS], audit=[{**GOOD_AUDIT, "rated_level": 9}], recheck=[MISS]), L9),
    ("second solver declined", FakeAI(solve=[MISS], audit=[{**GOOD_AUDIT, "rated_level": 9}],
                                      refuse={("opus", "recheck")}), L9),
])
def test_a_hard_miss_without_independent_confirmation_never_passes(why, ai, slot):
    q, _ = run(ai, slot=slot)
    assert q is None
    assert all(m == "opus" for m, c in zip(ai.models, ai.calls) if c in ("solve", "recheck"))  # never self-checked


def test_a_question_whose_independent_solver_declines_is_not_self_checked():
    ai = FakeAI(refuse={("opus", "solve")})
    q, log = run(ai)
    assert q is None and ("sonnet", "solve") not in set(zip(ai.models, ai.calls))
    assert ai.calls == ["gen", "solve"] * 4 and "no independent check" in log[-1]


def test_a_failed_solve_is_retried_once_and_is_never_a_miss():
    ai = FakeAI(solve=[None, "?"])
    q, _ = run(ai)
    assert q and ai.calls == ["gen", "solve", "solve", "audit"] and q["checks"] == ["solve", "audit"]
    ai = FakeAI(solve=[None], audit=[{**GOOD_AUDIT, "rated_level": 9}])
    q, log = run(ai, slot=L9)  # level 9 allows a miss, but a failure is no miss: the slot gives up
    assert q is None and ai.calls == ["gen", "solve", "solve"] and "AI not responding" in log[-1]


def test_two_failed_calls_end_a_slot():
    ai = FakeAI(gen=[None])
    q, log = run(ai)
    assert q is None and ai.calls == ["gen", "gen"] and "AI not responding" in log[-1]


def test_a_slot_never_makes_more_than_the_call_limit():
    bad = {**GOOD_AUDIT, "problems": ["ambiguous"]}
    ai = FakeAI(audit=[bad], refuse={("sonnet", "audit")})  # 4 calls a try: 4 tries would be 16
    q, log = run(ai)
    assert q is None and len(ai.calls) == cg.MAX_CALLS_PER_QUESTION and "call limit" in log[-1]


def test_a_hard_question_the_audit_cannot_confirm_is_retried():
    bad = {**GOOD_AUDIT, "rated_level": 9, "solution_correct": False}
    ai = FakeAI(solve=[{"answer": "Z"}, "?"], audit=[bad, {**GOOD_AUDIT, "rated_level": 9}])
    q, _ = run(ai, slot={"n": 1, "level": 9, "kind": "mcq"})
    assert q and ai.calls == ["gen", "solve", "audit", "gen", "solve", "audit"]


def test_an_out_of_scope_concept_found_by_the_audit_is_retried():
    ai = FakeAI(audit=[{**GOOD_AUDIT, "out_of_scope": ["simple harmonic motion"]}, GOOD_AUDIT])
    q, _ = run(ai)
    assert q and ai.calls.count("gen") == 2 and "simple harmonic motion" in ai.prompts[3]


def test_an_audit_mapping_to_an_unknown_kc_is_out_of_scope():
    ai = FakeAI(audit=[{**GOOD_AUDIT, "concepts": [{"idea": "shm", "kc": "9702-17.1.1"}]}, GOOD_AUDIT])
    q, _ = run(ai)
    assert q and ai.calls.count("gen") == 2 and "9702-17.1.1" in ai.prompts[3]


def test_a_question_rated_far_too_easy_is_retried():
    ai = FakeAI(audit=[{**GOOD_AUDIT, "rated_level": 2}, GOOD_AUDIT])
    q, log = run(ai)
    assert q and ai.calls.count("gen") == 2 and "easy" in ai.prompts[3] and "too easy" in log[0]


def test_audit_problems_are_retried():
    ai = FakeAI(audit=[{**GOOD_AUDIT, "problems": ["two options are correct"]}, GOOD_AUDIT])
    q, _ = run(ai)
    assert q and "two options are correct" in ai.prompts[3]


def test_a_malformed_question_is_retried_without_spending_a_solve():
    ai = FakeAI(gen=[raw_mcq(correct=""), None, raw_mcq()])
    q, log = run(ai)
    assert q and ai.calls == ["gen", "gen", "gen", "solve", "audit"] and len(log) == 3


def test_all_attempts_fail_then_one_easier_try_then_none():
    ai = FakeAI(gen=[raw_mcq(correct="")])
    q, log = run(ai, slot={"n": 4, "level": 6, "kind": "mcq"})
    assert q is None and ai.calls == ["gen"] * 4 and len(log) == 4
    assert "level 5" in log[-1].lower() or "L5" in log[-1]


def test_the_easier_fallback_can_succeed_and_says_its_level():
    ai = FakeAI(gen=[raw_mcq(correct="")] * 3 + [raw_mcq()], audit=[{**GOOD_AUDIT, "rated_level": 5}])
    q, _ = run(ai, slot={"n": 4, "level": 6, "kind": "mcq"})
    assert q and q["level"] == 5 and q["n"] == 4


def test_a_failing_ai_never_raises():
    async def broken(prompt, schema, model, timeout=120):
        raise RuntimeError("boom")
    q, log = run(broken)
    assert q is None and log


# ---------------- generate_set ----------------
@pytest.fixture
def plan(monkeypatch):
    """challenge.plan_slots, faked here so these tests never depend on the sibling module."""
    from tutorlib import challenge as real
    mod = types.ModuleType("tutorlib.challenge")
    mod.__dict__.update(real.__dict__)  # everything else is the real module (the screen needs LEVELS and more)
    mod.plan_slots = lambda cfg, seed: [{"n": i + 1, "level": 5, "kind": "mcq"} for i in range(cfg["count"])]
    monkeypatch.setitem(sys.modules, "tutorlib.challenge", mod)
    import tutorlib
    monkeypatch.setattr(tutorlib, "challenge", mod, raising=False)


def test_a_set_comes_back_ordered_and_renumbered_with_skips_listed(plan):
    fails = {2, 4}

    async def ask(prompt, schema, model, timeout=120):
        n = int(prompt.split("[slot ")[1].split("]")[0]) if schema is cg.GENERATE_MCQ_SCHEMA else None
        if schema is cg.GENERATE_MCQ_SCHEMA:
            return raw_mcq(stem=STEM + f" (variant {n})") if n not in fails else None
        if schema is cg.SOLVE_SCHEMA:
            opts = dict(line.split(") ", 1) for line in prompt.splitlines() if line[:2] in ("A)", "B)", "C)", "D)"))
            return {"answer": next(k for k, v in opts.items() if v == "18 J")}
        return GOOD_AUDIT

    done = []
    out = asyncio.run(cg.generate_set(ask, {**CFG, "count": 5}, SCOPE, on_progress=lambda *a: done.append(a), seed=1,
                                      parallel=1))
    assert [q["n"] for q in out["questions"]] == [1, 2, 3]
    assert [q["item"]["stem"][-11:] for q in out["questions"]] == ["(variant 1)", "(variant 3)", "(variant 5)"]
    assert [(s["n"], s["level"], s["kind"]) for s in out["skipped"]] == [(2, 5, "mcq"), (4, 5, "mcq")]
    assert all(s["reason"] for s in out["skipped"]) and out["log"]
    assert [d[:2] for d in done] == [(i, 5) for i in range(1, 6)] and all(isinstance(d[2], str) for d in done)


def test_a_set_never_runs_more_than_parallel_at_once(plan):
    ai = FakeAI()
    out = asyncio.run(cg.generate_set(ai, {**CFG, "count": 7}, SCOPE, parallel=2, seed=3))
    assert len(out["questions"]) == 7 and ai.peak == 2 and len(ai.calls) == 21 == out["calls"]


def test_later_questions_are_told_the_stems_already_accepted(plan):
    ai = FakeAI()
    asyncio.run(cg.generate_set(ai, {**CFG, "count": 3}, SCOPE, parallel=1, seed=3))
    gens = [p for p, c in zip(ai.prompts, ai.calls) if c == "gen"]
    assert "pushed 3.0 m" not in gens[0] and "pushed 3.0 m" in gens[2]


def test_a_cancelled_set_stops_and_keeps_what_it_has(plan):
    ai = FakeAI()
    stop = {"now": False}

    def progress(done, total, msg):
        stop["now"] = done >= 2
    out = asyncio.run(cg.generate_set(ai, {**CFG, "count": 6}, SCOPE, on_progress=progress,
                                      cancelled=lambda: stop["now"], parallel=1, seed=0))
    assert len(out["questions"]) == 2 and len(ai.calls) == 6
    assert [s["reason"] for s in out["skipped"]] == ["cancelled"] * 4


# ---------------- a model that declines ----------------
def test_a_declined_generator_hands_the_slot_to_the_other_model():
    ai = FakeAI(refuse={("sonnet", "gen")})
    q, log = run(ai)
    assert q and q["model"] == "opus" and q["checks"] == ["solve", "audit"]
    assert list(zip(ai.calls, ai.models)) == [("gen", "sonnet"), ("gen", "opus"), ("solve", "sonnet"), ("audit", "opus")]
    assert any("sonnet declined" in line for line in log) and sum("try" in line for line in log) == 1


def test_a_declined_audit_is_done_by_the_other_model():
    ai = FakeAI(refuse={("sonnet", "audit")})
    q, _ = run(ai)
    assert q and q["checks"] == ["solve", "audit"] and ai.models[-2:] == ["sonnet", "opus"]


@pytest.mark.parametrize("refuse, calls", [
    ({("sonnet", "audit"), ("opus", "audit")}, ["gen", "solve", "audit", "audit"]),
    ({("sonnet", "gen"), ("opus", "gen")}, ["gen", "gen"]),
])
def test_a_slot_both_models_decline_is_skipped_without_retries(refuse, calls):
    ai = FakeAI(refuse=refuse)
    q, log = run(ai)
    assert q is None and ai.calls == calls and "declined by the models" in log[-1]


def test_a_set_counts_the_fallbacks_for_the_ui(plan):
    ai = FakeAI(refuse={("opus", "gen")})
    out = asyncio.run(cg.generate_set(ai, {**CFG, "model": "opus", "count": 3}, SCOPE, seed=0))
    assert len(out["questions"]) == 3 and all(q["model"] == "sonnet" for q in out["questions"])
    fb = out["fallbacks"]
    assert fb["count"] == 3 and fb["declined"] == {"opus": 3}
    assert fb["note"] == "Opus declined 3 questions; Sonnet wrote them instead."
    quiet = asyncio.run(cg.generate_set(FakeAI(), {**CFG, "count": 1}, SCOPE, seed=0))["fallbacks"]
    assert quiet == {"count": 0, "declined": {}, "note": ""}


def test_the_audit_sees_the_key_as_the_student_will():
    q = cg.to_item(raw_typed(value=60.578, unit="m", sf=3), TYPED, SCOPE, random.Random(0))
    assert "KEY: 60.6 m (unrounded 60.578, kept for marking)" in cg.audit_prompt(q, SCOPE)
    assert "constant" in cg.generation_prompt(TYPED, SCOPE, CFG, [])


# ---------------- difficulty held up at the top ----------------
def test_top_levels_are_described_by_checkable_features_with_a_self_check():
    p8 = cg.generation_prompt({"n": 1, "level": 8, "kind": "typed"}, SCOPE, CFG, [])
    assert "symbolically" in p8 and "conserved quantity" in p8 and "12 minutes" in p8 and "Self-check" in p8
    assert "Self-check" not in cg.generation_prompt({"n": 1, "level": 3, "kind": "typed"}, SCOPE, CFG, [])
    q = cg.to_item(raw_mcq(), MCQ, SCOPE, random.Random(0))
    assert "conserved quantity" in cg.audit_prompt(q, SCOPE)  # the examiner rates by the same features
    assert "Not remarks" in cg.audit_prompt(q, SCOPE)  # a remark in `problems` rejects a sound question


def L8(**kw):
    return {"n": 1, "level": 8, "kind": "mcq", **kw}


def test_at_level_7_and_up_one_level_easier_is_the_limit():
    ai = FakeAI(audit=[{**GOOD_AUDIT, "rated_level": 6}, {**GOOD_AUDIT, "rated_level": 7}])
    q, _ = run(ai, slot=L8())
    assert q and q["rated"] == 7 and ai.calls.count("gen") == 2
    ai = FakeAI(audit=[{**GOOD_AUDIT, "rated_level": 3}])
    q, _ = run(ai, slot={"n": 1, "level": 5, "kind": "mcq"})  # below 7 the band stays two either way
    assert q and q["rated"] == 3 and ai.calls.count("gen") == 1


def test_when_no_try_lands_in_the_band_the_closest_is_kept_before_an_easier_try():
    ai = FakeAI(audit=[{**GOOD_AUDIT, "rated_level": r} for r in (5, 6, 5)])
    q, log = run(ai, slot=L8())
    assert q and q["rated"] == 6 and ai.calls.count("gen") == 3  # no easier try spent
    assert q["level"] == 6 and q["requested"] == 8  # shown as the level it really is
    assert "kept the closest try (rated L6)" in log[-1]


def test_a_far_easier_try_is_kept_only_when_nothing_else_came_through():
    ai = FakeAI(audit=[{**GOOD_AUDIT, "rated_level": 4}] * 3 + [{**GOOD_AUDIT, "rated_level": 7}])
    q, _ = run(ai, slot=L8())
    assert q and q["rated"] == 7 and q["level"] == 7 and q["requested"] == 8 and ai.calls.count("gen") == 4
    ai = FakeAI(audit=[{**GOOD_AUDIT, "rated_level": 4}])
    q, _ = run(ai, slot=L8())
    assert q and q["rated"] == 4 and q["level"] == 4 and ai.calls.count("gen") == 4


# ---------------- topic variety ----------------
TWO = [{"id": f"9702-{c}.{i}", "spec": "9702", "subtopic": f"9702-{c}", "title": f"Idea {c}.{i}", "statement": "s",
        "chosen": True} for c in ("5.1", "5.2") for i in (1, 2, 3)] + [
    {"id": "9702-2.1.1", "spec": "9702", "subtopic": "9702-2.1", "title": "Old", "statement": "s"}]


def test_focus_rotates_through_the_chosen_ideas_before_repeating():
    slots = [{"n": i, "level": 4, "kind": "mcq"} for i in range(1, 4)]
    f = cg.plan_focus(slots, TWO, {}, seed=1)
    assert all(len(v) == 2 for v in f.values()) and len({i for v in f.values() for i in v}) == 6
    assert "9702-2.1.1" not in str(f) and f == cg.plan_focus(slots, TWO, {}, seed=1) != cg.plan_focus(slots, TWO, {}, 2)


def test_focus_at_level_8_spans_chapters():
    for seed in range(20):
        f = cg.plan_focus([{"n": 1, "level": 8, "kind": "typed"}, {"n": 2, "level": 2, "kind": "mcq"}], TWO, {}, seed)
        assert len(f[1]) == 3 and {i[:8] for i in f[1]} == {"9702-5.1", "9702-5.2"} and len(f[2]) == 1


def test_the_focus_is_required_in_the_prompt_and_the_question():
    slot = {**MCQ, "focus": ["9702-5.1.2"]}
    p = cg.generation_prompt(slot, SCOPE, CFG, [])
    assert "REQUIRED" in p and "9702-5.1.2 Kinetic energy" in p
    assert cg.to_item(raw_mcq(), slot, SCOPE, random.Random(0))["focus"] == ["9702-5.1.2"]
    with pytest.raises(cg.BadQuestion, match="focus"):
        cg.to_item(raw_mcq(concepts=["9702-5.1.1"]), slot, SCOPE, random.Random(0))


def test_a_set_gives_each_slot_its_focus(plan):
    out = asyncio.run(cg.generate_set(FakeAI(), {**CFG, "count": 2}, SCOPE, seed=0))
    assert all(q["focus"] and set(q["focus"]) <= {"9702-5.1.1", "9702-5.1.2"} for q in out["questions"])


def test_a_set_stops_when_the_ai_stops_answering(plan):
    calls = []

    async def silent(prompt, schema, model, timeout=120):
        calls.append(model)
        return None
    out = asyncio.run(cg.generate_set(silent, {**CFG, "count": 4}, SCOPE, parallel=1, seed=0))
    assert out["questions"] == [] and out["calls"] == len(calls) == cg.MAX_FAILS_IN_ROW
    assert [s["reason"] for s in out["skipped"]] == ["AI not responding"] * 4


def test_the_call_names_do_not_depend_on_schema_identity():
    import copy
    assert cg.call_name(copy.deepcopy(cg.AUDIT_SCHEMA)) == "audit"
    assert cg.call_name(copy.deepcopy(cg.GENERATE_MCQ_SCHEMA)) == "generate"
    assert cg.call_name(copy.deepcopy(cg.SOLVE_SCHEMA)) == "solve"


# ---------------- time allowed per call ----------------
@pytest.mark.parametrize("model, level, write, check", [
    ("sonnet", 3, 300, 240), ("opus", 5, 420, 240), ("sonnet", 6, 420, 420), ("opus", 7, 600, 420),
    ("sonnet", 8, 600, 600), ("opus", 10, 900, 600)])
def test_calls_get_more_time_at_higher_levels(model, level, write, check):
    assert cg.timeout_for("generate", model, level) == write
    assert cg.timeout_for("solve", model, level) == cg.timeout_for("audit", model, level) == check


def test_each_call_is_given_its_levels_time():
    seen = []
    ai = FakeAI(audit=[{**GOOD_AUDIT, "rated_level": 9}])

    async def timed(prompt, schema, model, timeout=120):
        seen.append((cg.call_name(schema), model, timeout))
        return await ai(prompt, schema, model, timeout)
    asyncio.run(cg.make_question(timed, L9, SCOPE, CFG, [], []))
    assert seen == [("generate", "sonnet", 600), ("solve", "opus", 600), ("audit", "sonnet", 600)]


# ---------------- a refusal, end to end through the app's real wrappers ----------------
REFUSAL = ("API Error: Opus 5's safeguards flagged this message (https://www.anthropic.com/legal/aup). This sometimes "
           "happens with safe, normal conversations. Claude Code can't respond to this message with Opus 5. Try "
           "rephrasing the request in a new session or change your model.")


def test_a_refusal_from_claude_reaches_the_generator_as_a_fallback(tmp_path, plan):
    """A stand-in `claude` that refuses to let Opus write: the real Claude.one_shot and the challenge screen's real
    `ask` must turn its reply into Refused, and the set must count the handover."""
    from types import SimpleNamespace
    from tutor_app import ai
    from tutor_app.challenge_screen import ChallengeScreen
    fake, body = tmp_path / "claude", tmp_path / "claude_body.py"  # a shebang cannot hold the spaces of this folder's path
    fake.write_text(f'#!/bin/sh\nexec "{sys.executable}" "{body}" "$@"\n')
    body.write_text(f"""import json, sys
args = sys.argv[1:]
model, schema = args[args.index("--model") + 1], json.loads(args[args.index("--json-schema") + 1])
prompt, props = sys.stdin.read(), schema["properties"]
if model == "opus" and "stem" in props:
    print(json.dumps({{"type": "result", "is_error": True, "result": {REFUSAL!r}}}))
    sys.exit(1)
if "rated_level" in props:
    data = {GOOD_AUDIT!r}
elif "stem" in props:
    data = {raw_mcq()!r}
else:
    opts = dict(l.split(") ", 1) for l in prompt.splitlines() if l[:2] in ("A)", "B)", "C)", "D)"))
    data = {{"working": "w", "answer": next(k for k, v in opts.items() if v == "18 J")}}
print(json.dumps({{"type": "result", "is_error": False, "result": "ok", "structured_output": data, "usage": {{}}}}))
""")
    fake.chmod(0o755)
    claude = ai.Claude(tmp_path, binary=str(fake))
    data, res = asyncio.run(claude.one_shot("x", schema=cg.GENERATE_SCHEMA, model="opus"))
    assert data is None and not res.ok and res.status == "error" and res.message == REFUSAL  # nothing lost on the way
    screen = SimpleNamespace(app=SimpleNamespace(ai=claude))

    async def ask(prompt, schema, model, timeout=120):
        return await ChallengeScreen.ask(screen, prompt, schema, model, timeout)
    out = asyncio.run(cg.generate_set(ask, {**CFG, "model": "opus", "count": 2}, SCOPE, parallel=1, seed=0))
    assert len(out["questions"]) == 2 and all(q["model"] == "sonnet" for q in out["questions"])
    assert out["fallbacks"]["count"] == 2 and out["fallbacks"]["declined"] == {"opus": 2}
    assert out["calls"] == 8 and not any("failed or timed out" in line for line in out["log"])
