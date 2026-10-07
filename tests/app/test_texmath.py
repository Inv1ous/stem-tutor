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
    (r"$\mathrm{X}\to{}^{32}\mathrm{P}+{}^{1}_{1}\mathrm{p}$", "X → ³²P + ¹₁p"),
    (r"$\text{Cu}^{2+}$", "Cu²⁺"), (r"$\text{kJ mol}^{-1}$", "kJ mol⁻¹"),  # no brackets round a text group
    (r"$\int_0^1 x^2\,dx$", "∫₀¹ x² dx"), (r"$\sum_{i=1}^n x_i$", "∑ᵢ₌₁ⁿ xᵢ"), (r"$\prod_{i=1}^{n} a_i$", "∏ᵢ₌₁ⁿ aᵢ"),
    (r"$\binom{n}{r}$", "C(n,r)"),
    (r"$\begin{vmatrix}a&b\\c&d\end{vmatrix}$", "|a  b; c  d|"),
    (r"$f(x)=\begin{cases}1 & x>0\\0 & x\le0\end{cases}$", "f(x) = {1, x>0; 0, x≤0}"),
    (r"$\SI{3.0e8}{m s^{-1}}$", "3.0e8 m s⁻¹"),
    (r"\(x^2\) and \[v^2=u^2\]", "x² and v² = u²"),
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
    (r"$\frac{a+b}{c}$", "(a + b)/c"), (r"$\frac{1}{2a}$", "1/(2a)"), (r"$\frac{2}{7}$", "²⁄₇"), (r"$\frac12$", "½"),
    (r"$\frac{\sqrt{3}}{2}$", "√3/2"), (r"$\sqrt[3]{x}$", "∛x"), (r"$\sqrt[n]{x}$", "ⁿ√x"),
    (r"$\frac{\Delta s}{\Delta t}$", "Δs/Δt"), (r"$\frac{5}{\sqrt{3}}$", "5/√3"), (r"$\sqrt[5]{32}$", "⁵√32"),
    (r"$\sqrt{a^2+b^2}$", "√(a² + b²)"),
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


@pytest.mark.parametrize("tex,want", [  # spaced like a printed page, with a true minus sign
    (r"$v^2=u^2+2as$", "v² = u² + 2as"), (r"$s = ut + \frac{1}{2}at^2$", "s = ut + ½at²"),
    (r"$y=-3x+2$", "y = −3x + 2"), (r"$5-(-3)=8$", "5 − (−3) = 8"), (r"$\sqrt{b^2-4ac}$", "√(b² − 4ac)"),
    (r"$\frac{dy}{dx}=3x^2-2$", "dy/dx = 3x² − 2"), (r"$x_1^2+x_2^2$", "x₁² + x₂²"),
    (r"$\mathbf{F}=m\mathbf{a}$", "𝐅 = m𝐚"), (r"$\Delta G = \Delta H - T\Delta S$", "ΔG = ΔH − TΔS"),
    (r"$\ce{H+} + \ce{OH-}$", "H⁺ + OH⁻"), (r"$\ce{N2 + 3H2 <=> 2NH3}$", "N₂ + 3H₂ ⇌ 2NH₃"),
    (r"$\ce{Cu^2+ + 2e- -> Cu}$", "Cu²⁺ + 2e⁻ → Cu"), (r"$\ce{CH2=CH2}$", "CH₂=CH₂"),
    (r"$\Delta G^\ominus=\Delta H^\ominus-T\Delta S^\ominus$", "ΔG⦵ = ΔH⦵ − TΔS⦵"),
    (r"$\Delta H_r^\ominus=-114\,\text{kJ mol}^{-1}$", "ΔHᵣ⦵ = −114 kJ mol⁻¹"),
    (r"$x\in\{1,2\}$", "x ∈ {1,2}"), (r"$A\iff B$", "A ⇔ B"), (r"$\mathrm{pH}=-\log_{10}[\ce{H+}]$", "pH = −log₁₀ [H⁺]"),
    (r"$\lim_{x\to0}\frac{\sin x}{x}=1$", "lim[x→0] (sin x)/x = 1"), (r"$\text{rate}=k[A]^2[B]$", "rate = k[A]²[B]"),
    (r"$x\rightarrow 0$", "x → 0"), (r"$f(x)=\begin{cases}x & x\ge0\\-x & x<0\end{cases}$", "f(x) = {x, x≥0; −x, x<0}"),
    (r"$\begin{pmatrix}2&-1\\3&4\end{pmatrix}$", "(2  −1; 3  4)"),
    (r"$\begin{pmatrix}k&k-1\\2&3\end{pmatrix}$", "(k  k − 1; 2  3)"), (r"$20 \le t < 35$", "20 ≤ t < 35"),
    (r"$1, 2, \ldots, n$", "1,2,…,n"), (r"$\SI{3.0e-8}{m}$", "3.0e−8 m"),
    (r"$2.0\times10^{-3}\,\mathrm{mol\,dm^{-3}}$", "2.0 × 10⁻³ mol dm⁻³"), (r"$>5$", ">5"), (r"$\pm 2$", "±2"),
    (r"$E_k=\tfrac12mv^2$", "Eₖ = ½mv²"), (r"$\text{well-known}$", "well-known"), (r"$|x-1|<2$", "|x − 1| < 2"),
    (r"$1+2+\dots+n$", "1 + 2 + … + n"), (r"$x \ge -3$", "x ≥ −3"), (r"$e^{-\lambda t}$", "e^(−λt)"),
    (r"$M^{q+}$", "M^(q+)"), (r"$(x+)$", "(x+)"),
    (r"$\int x\,dx$", "∫ x dx"), (r"$\sum_{x} P(X=x) = 1$", "∑ₓ P(X=x) = 1"), (r"$\oint^{b}_{a} f$", "∮ₐᵇ f"),
    (r"$\int_0^{\pi} \sin x\,dx = 2$", "∫₀^π sin x dx = 2"),
])
def test_maths_is_spaced_like_a_textbook(tex, want):
    assert to_terminal(tex) == want


def test_a_card_title_shows_maths_not_dollars():  # "Trap:" titles quote misconception statements
    out = shown(cards.card("hint", r"Trap: $v^2=u^2+2as$ needs a constant force", ""))
    assert "v² = u² + 2as" in out and "$" not in out


def test_pdf_leftovers_in_content_show_as_symbols_or_nothing():
    assert to_terminal("v = 2 P k") == "v = 2 P k"
    assert to_terminal("length AB  length AC + length CB, r  0") == "length AB ≤ length AC + length CB, r ≥ 0"
    assert to_terminal("Cl O­–") == "Cl O–"


@pytest.mark.parametrize("tex,want", [  # found by an independent review of the new maths format
    (r"$\int_0^\pi \sin x\,dx$", "∫₀^π sin x dx"), (r"$\sum_{n=0}^\infty a_n$", "∑ₙ₌₀^∞ aₙ"),  # unbraced \pi, \infty
    (r"$\ce{Na(g) -> Na+(g) + e-}$", "Na(g) → Na⁺(g) + e⁻"), (r"$\ce{Fe3+(aq)}$", "Fe³⁺(aq)"),  # charge, then state
    (r"$\ce{Mg-(g)}$", "Mg⁻(g)"),
    (r"$e^{x^2}$", "e^(x²)"), (r"$\int_1^{e^2} \frac{1}{x}\,dx$", "∫₁^(e²) 1/x dx"),  # (eˣ)² is another number
    (r"$2\left(x^2+\frac{b}{2}x\right)$", "2(x² + (b/2)x)"), (r"$\frac{d}{dx}e^{x^2}$", "(d/dx)e^(x²)"),  # not b/(2x)
    (r"$\frac{a}{2}(x+1)$", "(a/2)(x + 1)"), (r"$\frac{a}{b} + 1$", "a/b + 1"), (r"$\frac{1}{2}mv^2$", "½mv²"),
    (r"$|-3|=3$", "|−3| = 3"), (r"$|-2x+1|$", "|−2x + 1|"), (r"$|x-1|<2$", "|x − 1| < 2"),  # a bar that opens
    (r"$\text{3-methylpentane}$", "3-methylpentane"), (r"$\text{but-2-ene}$", "but-2-ene"),
    (r"$\text{Hooke's law}$", "Hooke’s law"),
])
def test_review_findings_read_as_printed(tex, want):
    assert to_terminal(tex) == want


@pytest.mark.parametrize("tex,want", [  # found by a second review
    (r"$y=|2|x|-3|$", "y = |2|x| − 3|"), (r"$P(A|B)+|-3|$", "P(A|B) + |−3|"), (r"$|-3|=3$", "|−3| = 3"),
    (r"$\num{3.0e-8}$", "3.0e−8"), (r"$\text{1.6e-19 C}$", "1.6e−19 C"), (r"$\text{(E)-but-2-ene}$", "(E)-but-2-ene"),
    (r"$\int_0^\frac{\pi}{2}\sin x\,dx$", "∫₀^(π/2) sin x dx"), (r"$\int_0^\sqrt{2} x\,dx$", "∫₀^(√2) x dx"),
    (r"$\lim_{\delta x\to0}\frac{\delta y}{\delta x}$", "lim[δx→0] δy/δx"),
    (r"$\displaystyle\frac{a}{b}$", "a/b"), (r"$\lvert x\rvert$", "|x|"), (r"$\Big| x \Big|$", "|x|"),
    (r"$\big(x\big)$", "(x)"), (r"$\det A$", "det A"), (r"$\sum\limits_{i=1}^{n} i$", "∑ᵢ₌₁ⁿ i"),
])
def test_second_review_findings_read_as_printed(tex, want):
    assert to_terminal(tex) == want


@pytest.mark.parametrize("tex,want", [  # brackets and symbols flatlatex has no name for
    (r"$\langle c^2\rangle$", "⟨c²⟩"), (r"$\frac{1}{2}m\langle c^2\rangle=\frac{3}{2}kT$", "½m⟨c²⟩ = ³⁄₂kT"),
    (r"$\lceil x \rceil + \lfloor y \rfloor$", "⌈x⌉ + ⌊y⌋"), (r"$\lfloor 2.7 \rfloor = 2$", "⌊2.7⌋ = 2"),
    (r"$\triangle ABC \sim \triangle DEF$", "△ABC ∼ △DEF"), (r"$A = \varnothing$", "A = ∅"),
    (r"$a \leqslant b$", "a ≤ b"), (r"$a \geqslant b$", "a ≥ b"), (r"$p \land q$", "p ∧ q"), (r"$p \lor q$", "p ∨ q"),
    (r"$A \Longrightarrow B$", "A ⇒ B"), (r"$A \Longleftrightarrow B$", "A ⇔ B"), (r"$a \leftrightarrow b$", "a ⟷ b"),
    (r"$\hat{\imath}+\hat{\jmath}$", "ı̂ + ȷ̂"), (r"$a \bmod n$", "a mod n"), (r"$a \equiv b \pmod{n}$", "a ≡ b (mod n)"),
    (r"$\dagger$", "†"), (r"$5\,\text{\textmu m}$", "5 μm"),
])
def test_brackets_and_symbols_without_a_flatlatex_name(tex, want):
    assert to_terminal(tex) == want


@pytest.mark.parametrize("tex,want", [  # an accent over one letter combines; over several it still reads
    (r"$\overrightarrow{AB}$", "→AB"), (r"$\vec{AB}$", "→AB"), (r"$\overleftarrow{AB}$", "←AB"),
    (r"$\overrightarrow{OA}+\overrightarrow{AB}=\overrightarrow{OB}$", "→OA + →AB = →OB"),
    (r"$|\overrightarrow{AB}|=5$", "|→AB| = 5"), (r"$\vec{a}$", "a⃗"), (r"$\vec{F}_{net}$", "F⃗ₙₑₜ"),
    (r"$\overline{AB}$", "A̅B̅"), (r"$\bar{AB}$", "A̅B̅"), (r"$\overline{x}$", "x̅"), (r"$\bar{x}$", "x̄"),
    (r"$\underline{AB}$", "A̲B̲"), (r"$\underline{a}$", "a̲"), (r"$\bar{z_1}\bar{z_2}$", "z̄₁z̄₂"),
    (r"$\overline{z_1 z_2}$", "z̅₁̅z̅₂̅"), (r"$\hat{\mathbf{n}}$", "𝐧̂"), (r"$\widehat{ABC}=90^\circ$", "∠ABC = 90°"),
    (r"$\hat{ABC}$", "∠ABC"), (r"$\hat{AB}$", "ÂB̂"), (r"$\widetilde{x}$", "x̃"), (r"$\cancel{ab}$", "a̶b̶"),
])
def test_accents_over_one_or_several_letters(tex, want):
    assert to_terminal(tex) == want


@pytest.mark.parametrize("tex,want", [(r"$\overline{1+x}$", "1̅+̅x̅"), (r"$\vec{}$", ""), (r"$2\overrightarrow{AB}$", "2→AB")])
def test_accent_edge_cases(tex, want):
    assert to_terminal(tex) == want
