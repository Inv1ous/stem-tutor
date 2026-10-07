"""Maths and cards as the terminal shows them: no raw LaTeX, no Markdown eating the learner's answer."""
from __future__ import annotations

import pytest
from rich.console import Console

from tutor_app import cards
from tutor_app.texmath import pretty_units, to_terminal


def shown(renderable, width: int = 80) -> str:
    console = Console(width=width, color_system=None, record=True)
    console.print(renderable)
    return console.export_text()


@pytest.mark.parametrize("tex,want", [
    (r"$298\,\mathrm K$", "298 K"), (r"$\text K$", "K"),  # unbraced text commands
    (r"$^{14}_{6}\mathrm{C}$", "¹⁴₆C"), (r"$\ce{^{14}_{6}C}$", "¹⁴₆C"),  # nuclides: mass above, number below
    (r"$^{35}_{17}\mathrm{Cl}^-$", "³⁵₁₇Cl⁻"), (r"$^{40}\mathrm{Ar}$", "⁴⁰Ar"),
    (r"$\mathrm{X}\to{}^{32}\mathrm{P}+{}^{1}_{1}\mathrm{p}$", "X→³²P+¹₁p"),
    (r"$\text{Cu}^{2+}$", "Cu²⁺"), (r"$\text{kJ mol}^{-1}$", "kJ mol⁻¹"),  # no brackets round a text group
    (r"$\int_0^1 x^2\,dx$", "∫₀¹x² dx"), (r"$\sum_{i=1}^n x_i$", "∑ᵢ₌₁ⁿxᵢ"), (r"$\prod_{i=1}^{n} a_i$", "∏ᵢ₌₁ⁿaᵢ"),
    (r"$\binom{n}{r}$", "C(n,r)"),
    (r"$\begin{vmatrix}a&b\\c&d\end{vmatrix}$", "|a b; c d|"),
    (r"$f(x)=\begin{cases}1 & x>0\\0 & x\le0\end{cases}$", "f(x)={1, x>0; 0, x≤0}"),
    (r"$\SI{3.0e8}{m s^{-1}}$", "3.0e8 m s⁻¹"),
    (r"\(x^2\) and \[v^2=u^2\]", "x² and v²=u²"),
])
def test_latex_reaches_the_terminal_readable(tex, want):
    assert to_terminal(tex) == want


def test_dollar_amounts_in_prose_are_not_maths():
    assert to_terminal("It costs $5 and $6 today.") == "It costs $5 and $6 today."


@pytest.mark.parametrize("plain,want", [
    ("a = 2.0 m s^-2", "a = 2.0 m s⁻²"), ("0.10 mol dm^-3.", "0.10 mol dm⁻³."),  # unit at a sentence end
    ("^40Ar and ^35Cl", "⁴⁰Ar and ³⁵Cl"),
])
def test_plain_units_and_isotopes_are_pretty_everywhere(plain, want):
    assert to_terminal(plain) == want


def test_a_decimal_power_is_still_left_as_typed():
    assert pretty_units("m^2.5") == "m^2.5" and pretty_units("cm^-3.") == "cm⁻³."


def test_feedback_shows_the_answer_exactly_as_typed():
    out = shown(cards.feedback({"n": 1, "correct": False, "answer": "6*x**2 - 2*x_1", "detail": "a in m s^-2"},
                               "3*x**2 - 2*x + x_1"))
    assert "3*x**2 - 2*x + x_1" in out and "6*x**2 - 2*x_1" in out
    assert "m s⁻²" in out


def test_feedback_still_makes_units_pretty():
    out = shown(cards.feedback({"n": 1, "correct": True, "answer": "9.8 m s^-2"}, "9.81 m s^-2"))
    assert "9.81 m s⁻²" in out and "9.8 m s⁻²" in out


def test_question_options_show_pretty_units():
    out = shown(cards.question({"n": 1, "kind": "numeric", "stem": "Pick", "options": {"A": "2 m s^-2"}}))
    assert "2 m s⁻²" in out


def test_single_line_breaks_in_a_stem_are_kept():
    out = shown(cards.md("t/s: 1 2 3\nv/m s^-1: 2 4 6\n\nWhich is right?\n\n- one\n- two"))
    lines = [ln.rstrip() for ln in out.splitlines()]
    assert "t/s: 1 2 3" in lines and "v/m s⁻¹: 2 4 6" in lines
    assert any(ln.endswith("one") for ln in lines) and any(ln.endswith("two") for ln in lines)


def test_a_card_with_no_body_is_just_its_title():
    out = shown(cards.card("plan", "What next?", ""))
    assert len(out.strip().splitlines()) == 2
