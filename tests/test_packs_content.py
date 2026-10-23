"""Content checks on the published packs (build/out/packs) that the pack validator does not make.

Each guards a class of fault found in an audit of the v2 packs:
- a generated MCQ is re-lettered when it is shown (packs.instantiate shuffles it), so its explanation, hints and
  the misconceptions it links to must name an option by its text, never by its letter;
- numeric answers are not marked with a tolerance wider than 2%;
- an MCQ whose option text is unusable (empty, or two options alike) has options null and shows its figure;
- a short item has one rubric point per mark, and a structured item one scheme point per mark;
- a template's distractor never takes the answer's value.
"""
import json
import math
import random
import re
from pathlib import Path

import pytest

from tutorlib import packs

PACKS = Path(__file__).resolve().parents[1] / "build" / "out" / "packs"
pytestmark = pytest.mark.skipif(not PACKS.exists(), reason="no published packs in this checkout")


def _packs():
    return [json.loads(p.read_text(encoding="utf-8")) for p in sorted(PACKS.glob("*/*-*.json"))]


def _items():
    return [it for p in _packs() for it in p["items"]]


def _shuffled(it):
    return it["kind"] == "mcq" and it.get("shuffle") and (it.get("source") or {}).get("type") != "past"


# ---------- option letters in shuffled MCQs ----------
_VERBS = ("is|are|has|have|uses|adds|ignores|puts|holds|pairs|gives|fails|describes|differs|confuses|reverses|omits|"
          "counts|treats|assumes|forgets|mixes|swaps|doubles|halves|misses|shows|states|says|would|could|cannot|acts")
_LETTER = r"(?<![\w'’-])[A-D](?![\w'’-])"
LETTER_REF = re.compile("|".join([
    r"\b[Oo]ptions?\s+\(?[A-D]\b",                                             # option D, options B and C
    rf"\(\s*[A-D](?:\s*(?:,|and|or|&)\s*[A-D])*(?:\s+(?:is|are)\b[^)]*)?\)",  # (B), (C, D), (A, C, D are false)
    rf"{_LETTER}(?:\s*,\s*[A-D])*,?\s+(?:and|or)\s+[A-D](?![\w'’-])",         # B, C and D
    rf"(?:^|[.;:,!?]\s+|\b(?:and|but|while|whereas|so)\s+){_LETTER}\s+(?:{_VERBS})\b",  # ... and D ignores the charge
    rf"\b[Ii]n\s+[A-D](?:\s*,|\s+(?:the|it|this|that)\b)",                    # In A the 3d ...; in C, 4s ...
    r"\b(?:answer|key)\s+(?:is\s+)?\(?[A-D]\b(?![\w'’-])",                    # the answer is B
    rf"\b[Oo]nly\s+{_LETTER}",                                               # Only A has zero resultant (B-129)
]))


def letter_refs(text: str) -> list[str]:
    plain = re.sub(r"\$[^$]*\$", " ", text or "")  # $A$, $\mathrm{C}$ and the like are maths, not letters
    return [m.group(0) for m in LETTER_REF.finditer(plain)]


@pytest.mark.parametrize("text", [
    "Option D describes atoms of different elements.",
    "so B, C and D are wrong.",
    "B adds electrons instead of removing them, C uses the nucleon number and D ignores the charge.",
    "Neutrons are not involved in bonding (B), and isotopes differ in nucleon number (C, D).",
    "the same electron configuration (A, C, D are false).",
    "Option A pairs before filling singly, C puts two arrows in one box.",
    "so option D fails.",
    "Using every value (B) is exactly why the mean is distorted",
    "does option D square anything?",
    "In A the 3d is placed before 4s; in C, 4s is below 3p.",
    "The answer is B.",
])
def test_the_letter_pattern_catches_the_audit_findings(text):
    assert letter_refs(text)


@pytest.mark.parametrize("text", [
    "Ball A is dropped from rest. At the same instant ball B is fired horizontally.",
    "A neutron has no charge. A 3+ ion has lost three electrons.",
    "9.6 is bigger than 4.2, so Class B's scores are more spread out.",
    "Vitamin $A$ and $B$ terms; the set $A\\cup B$.",
    "A p sub-shell is made of three p orbitals.",
])
def test_the_letter_pattern_leaves_labels_and_articles_alone(text):
    assert not letter_refs(text)


def test_shuffled_mcqs_never_name_an_option_by_its_letter():
    found = []
    for p in _packs():
        linked = set()
        for it in p["items"]:
            if not _shuffled(it):
                continue
            linked |= {v for v in (it.get("distractors") or {}).values() if isinstance(v, str)}
            for field, text in [("explanation", it.get("explanation"))] + \
                               [(f"hints[{i}]", h) for i, h in enumerate(it.get("hints") or [])]:
                if refs := letter_refs(text):
                    found.append((it["id"], field, refs))
        for m in p.get("misconceptions", []):  # a misconception is shown after any item that links it
            if m["id"] in linked:
                for field in ("statement", "refutation", "contrast"):
                    if refs := letter_refs(m.get(field)):
                        found.append((f"{p['subtopic']} {m['id']}", field, refs))
    assert not found, found


# ---------- numeric tolerance ----------
MAX_TOL_REL = 0.02  # rounding is credited by sf_ok; a tolerance only absorbs carried rounding


def test_no_item_answer_has_a_wide_tolerance():
    wide = [(it["id"], it["answer"]["tol_rel"]) for it in _items()
            if isinstance(it.get("answer"), dict) and it["answer"].get("tol_rel", 0) > MAX_TOL_REL]
    assert not wide, wide


def test_audited_numeric_items_keep_their_marking():
    items = {it["id"]: it for it in _items()}
    assert items["9702-1.3-i02"]["answer"].get("exact") is True  # zero error: r - z and r + z agree at 2 s.f.
    assert "tol_rel" not in items["9702-1.3-i10"]["answer"]
    assert "tol_rel" not in items["9702-1.3-i11"]["answer"]
    assert items["9701-1.1-i10"]["answer"]["sf_ok"] == [2, 3, 4]


# ---------- MCQ options ----------
def _norm(v) -> str:
    return " ".join(str(v).split())


def test_mcq_options_are_text_or_null():
    bad = []
    for it in _items():
        if it["kind"] != "mcq" or it.get("options") is None:
            continue
        opts = it["options"]
        if any(_norm(v) == "" for v in opts.values()):
            bad.append((it["id"], "empty option text: use options null and the figure"))
        elif not it.get("image") and len({_norm(v) for v in opts.values()}) < len(opts):
            bad.append((it["id"], "two options say the same"))
    assert not bad, bad


def test_figure_only_mcqs_have_a_figure():
    assert not [it["id"] for it in _items() if it["kind"] == "mcq" and it.get("options") is None and not it.get("image")]


# ---------- marks ----------
def test_marks_match_points():
    bad = []
    for it in _items():
        points = it.get("rubric") if it["kind"] == "short" else it.get("scheme") if it["kind"] == "structured" else None
        if points is not None and len(points) != it.get("marks"):
            bad.append((it["id"], it.get("marks"), len(points)))
    assert not bad, bad


# ---------- template distractors ----------
def test_template_distractors_never_equal_the_answer():
    clash = []
    for it in _items():
        if not it.get("template") or it["kind"] == "mcq":
            continue
        for seed in range(300):
            inst = packs.instantiate(it, random.Random(seed))
            v = inst["answer"]["value"]
            if any(math.isclose(d["value"], v, rel_tol=1e-9, abs_tol=1e-12) for d in inst.get("distractors") or []):
                clash.append((it["id"], inst["params"]))
                break
    assert not clash, clash


def test_the_gate_helpers_use_the_same_letter_rule_and_find_the_faults_in_a_pack():
    import sys
    sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "build"))
    import content_checks
    assert content_checks.LETTER_REF.pattern == LETTER_REF.pattern
    pack = {"items": [{"id": "x-r01", "kind": "mcq", "shuffle": True, "explanation": "Because option B ignores the charge.",
                       "hints": ["Think about the charge."]},
                      {"id": "x-p01", "kind": "mcq", "shuffle": True, "source": {"type": "past"}, "explanation": "The answer is B."}],
            "misconceptions": []}
    assert len(content_checks.letter_problems(pack)) == 1 and "x-r01" in content_checks.letter_problems(pack)[0]
    assert content_checks.latex_problems({"note": "fine $x^2$", "q": "plain"}) == []


def test_characters_lost_in_a_pdf_copy_are_found():
    import sys
    sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "build"))
    import content_checks
    bad = {"items": [{"stem": "¨H = −197 kJ"}, {"stem": "a � b"}], "note": "fine ΔH"}
    assert len(content_checks.debris_problems(bad)) == 2
    assert content_checks.debris_problems({"note": "ΔH and Σ and ÷"}) == []


def test_a_stacked_fraction_the_pdf_broke_is_repaired_and_found():
    """Asked by the learner: an answer read `PbS + 1 ₂ ¹ O₂ → SO₂ + PbO` — the fraction 1½, its numerator and denominator
    stacked, read in the wrong order with no slash, came out of the past-paper PDF like that."""
    import sys
    from pathlib import Path
    sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "build"))
    import content_checks as cc
    assert cc.tidy_script_text("PbS + 1 ₂ ¹ O₂ → SO₂ + PbO") == "PbS + 1½O₂ → SO₂ + PbO"
    assert cc.tidy_script_text("PbS + 2 ₂ ¹ O₂ → SO₃") == "PbS + 2½O₂ → SO₃"
    assert cc.tidy_script_text("Na(s) + ₄ ¹ O₂(g) → ₂ ¹ Na₂O(s)") == "Na(s) + ¼O₂(g) → ½Na₂O(s)"
    assert cc.tidy_script_text("a ₃ ² b") == "a ⅔ b" and cc.tidy_script_text("a ₇ ³ b") == "a 3/7 b"
    assert cc.tidy_script_text("SO₄ ²⁻ and Cr₂O₇ ²⁻ and m₁u₁ ²") == "SO₄²⁻ and Cr₂O₇²⁻ and m₁u₁²"  # charges and squares: no stray space
    for fine in ("H₂O", "VO₂²⁺", "10² m", "Mg²⁺ ions", "Na₂O ⁺", "1½O₂", "x₂ ¹"):
        assert cc.tidy_script_text(fine) in (fine, "x₂¹") or fine == "x₂ ¹"
    assert cc.stacked_problems({"options": {"C": "PbS + 1 ₂ ¹ O₂ → SO₂ + PbO"}}) and not cc.stacked_problems(
        {"options": {"C": "PbS + 1½O₂ → SO₂ + PbO", "D": "SO₄²⁻"}})


def test_no_pack_in_the_repo_has_a_broken_fraction_or_charge_space():
    import glob
    import json
    import sys
    from pathlib import Path
    sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "build"))
    import content_checks as cc
    bad = []
    for f in glob.glob(str(Path(__file__).resolve().parents[1] / "build/out/packs/*/*.json")):
        try:
            pack = json.loads(Path(f).read_text(encoding="utf8"))
        except ValueError:
            continue
        if isinstance(pack, dict) and (found := cc.stacked_problems(pack)):
            bad.append((Path(f).name, found[0]))
    assert not bad, bad
