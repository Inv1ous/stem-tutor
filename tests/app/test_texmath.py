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


@pytest.mark.parametrize("tex,want", [
    # chemistry: a lone element's number and sign is a charge; a sign at the end of a species too
    (r"$\ce{Fe3+}$", "Fe³⁺"), (r"$\ce{Cu2+}$", "Cu²⁺"), (r"$\ce{H+}$", "H⁺"), (r"$\ce{OH-}$", "OH⁻"),
    (r"$\ce{e-}$", "e⁻"), (r"$\ce{NO3-}$", "NO₃⁻"), (r"$\ce{VO2+}$", "VO₂⁺"),
    (r"$\ce{[Fe(CN)6]^{3-}}$", "[Fe(CN)₆]³⁻"), (r"$\ce{[Fe(CN)6]3-}$", "[Fe(CN)₆]³⁻"),
    (r"$\ce{CH3-CH3}$", "CH₃-CH₃"), (r"$\ce{CH2=CH2}$", "CH₂=CH₂"), (r"$\ce{CuSO4.5H2O}$", "CuSO₄·5H₂O"),
    # sub- and superscripts together, and fractions with only the brackets they need
    (r"$x_1^2$", "x₁²"), (r"$x_{n+1}$", "xₙ₊₁"), (r"$E_k$", "Eₖ"), (r"$v_y$", "v_y"), (r"$T_{1/2}$", "T½"),
    (r"$\frac{dy}{dx}$", "dy/dx"), (r"$\frac{d^2y}{dx^2}$", "d²y/dx²"), (r"$\frac{mv^2}{r}$", "mv²/r"),
    (r"$\frac{a+b}{c}$", "(a+b)/c"), (r"$\frac{1}{2a}$", "1/(2a)"), (r"$\frac{2}{7}$", "²⁄₇"), (r"$\frac12$", "½"),
    (r"$\frac{\sqrt{3}}{2}$", "√3/2"), (r"$\sqrt[3]{x}$", "∛x"), (r"$\sqrt[n]{x}$", "ⁿ√x"),
    (r"$\frac{\Delta s}{\Delta t}$", "Δs/Δt"), (r"$\frac{5}{\sqrt{3}}$", "5/√3"), (r"$\sqrt[5]{32}$", "⁵√32"),
    (r"$\sqrt{a^2+b^2}$", "√(a²+b²)"),
    # standard state ⦵ as in the pack titles, after any subscript
    (r"$\Delta H^\ominus$", "ΔH⦵"), (r"$\Delta H_r^{\ominus}$", "ΔHᵣ⦵"), (r"$E^\ominus_{cell}$", "E_cell⦵"),
    # bold vectors, braces, function names without stray spaces, primes
    (r"$\mathbf{F}$", "𝐅"), (r"$\boldsymbol{a}$", "𝐚"), (r"$\{1,2\}$", "{1,2}"),
    (r"$\ln x$", "ln x"), (r"$\log_{10} x$", "log₁₀ x"), (r"$\sin(x)$", "sin(x)"), (r"$\sin^2\theta$", "sin² θ"),
    (r"$\lim_{x\to 0} \frac{\sin x}{x}$", "lim[x→0] (sin x)/x"), (r"$f'(x)$", "f′(x)"), (r"$f''(x)$", "f″(x)"),
])
def test_maths_reads_as_printed(tex, want):
    assert to_terminal(tex) == want


@pytest.mark.parametrize("tex,has", [
    (r"$x \rightarrow 0$", "→"), (r"$x \leftarrow y$", "←"), (r"$\ce{N2 + 3H2 <=> 2NH3}$", "⇌"),
    (r"$a \rightleftharpoons b$", "⇌"), (r"$A \iff B$", "⇔"), (r"$A \implies B$", "⇒"),
    (r"$\text{rate}=k[A]^2[B]$", "k[A]²[B]"),
])
def test_no_command_is_mangled_or_left_raw(tex, has):
    out = to_terminal(tex)
    assert has in out and "\\" not in out and "arrow" not in out and "harpoons" not in out


def test_the_flatlatex_internals_we_refine_still_exist():
    import flatlatex
    for name in ("_converter__indexed", "_converter__is_complex_expr", "_converter__latexfun_frac",
                 "_converter__latexfun_sqrt", "_converter__cmds"):
        assert hasattr(flatlatex.converter(), name), name
