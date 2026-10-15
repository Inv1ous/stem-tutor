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
    (r"$\int_0^1 x^2\,dx$", "∫₀¹ x² dx"), (r"$\sum_{i=1}^n x_i$", "∑_(i=1)^n x_i"), (r"$\prod_{i=1}^{n} a_i$", "∏_(i=1)^n a_i"),
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
    (r"$x_1^2$", "x₁²"), (r"$x_{n+1}$", "x_(n+1)"), (r"$E_k$", "E_k"), (r"$v_y$", "v_y"), (r"$T_{1/2}$", "T½"),
    (r"$\frac{dy}{dx}$", "dy/dx"), (r"$\frac{d^2y}{dx^2}$", "d²y/dx²"), (r"$\frac{mv^2}{r}$", "mv²/r"),
    (r"$\frac{a+b}{c}$", "(a + b)/c"), (r"$\frac{1}{2a}$", "1/(2a)"), (r"$\frac{2}{7}$", "²⁄₇"), (r"$\frac12$", "½"),
    (r"$\frac{\sqrt{3}}{2}$", "√3/2"), (r"$\sqrt[3]{x}$", "∛x"), (r"$\sqrt[n]{x}$", "ⁿ√x"),
    (r"$\frac{\Delta s}{\Delta t}$", "Δs/Δt"), (r"$\frac{5}{\sqrt{3}}$", "5/√3"), (r"$\sqrt[5]{32}$", "⁵√32"),
    (r"$\sqrt{a^2+b^2}$", "√(a² + b²)"),
    # standard state ⦵ as in the pack titles, after any subscript
    (r"$\Delta H^\ominus$", "ΔH⦵"), (r"$\Delta H_r^{\ominus}$", "ΔH_r⦵"), (r"$E^\ominus_{cell}$", "E_cell⦵"),
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
    (r"$\Delta H_r^\ominus=-114\,\text{kJ mol}^{-1}$", "ΔH_r⦵ = −114 kJ mol⁻¹"),
    (r"$x\in\{1,2\}$", "x ∈ {1,2}"), (r"$A\iff B$", "A ⇔ B"), (r"$\mathrm{pH}=-\log_{10}[\ce{H+}]$", "pH = −log₁₀ [H⁺]"),
    (r"$\lim_{x\to0}\frac{\sin x}{x}=1$", "lim[x→0] (sin x)/x = 1"), (r"$\text{rate}=k[A]^2[B]$", "rate = k[A]²[B]"),
    (r"$x\rightarrow 0$", "x → 0"), (r"$f(x)=\begin{cases}x & x\ge0\\-x & x<0\end{cases}$", "f(x) = {x, x≥0; −x, x<0}"),
    (r"$\begin{pmatrix}2&-1\\3&4\end{pmatrix}$", "(2  −1; 3  4)"),
    (r"$\begin{pmatrix}k&k-1\\2&3\end{pmatrix}$", "(k  k − 1; 2  3)"), (r"$20 \le t < 35$", "20 ≤ t < 35"),
    (r"$1, 2, \ldots, n$", "1,2,…,n"), (r"$\SI{3.0e-8}{m}$", "3.0e−8 m"),
    (r"$2.0\times10^{-3}\,\mathrm{mol\,dm^{-3}}$", "2.0 × 10⁻³ mol dm⁻³"), (r"$>5$", ">5"), (r"$\pm 2$", "±2"),
    (r"$E_k=\tfrac12mv^2$", "E_k = ½mv²"), (r"$\text{well-known}$", "well-known"), (r"$|x-1|<2$", "|x − 1| < 2"),
    (r"$1+2+\dots+n$", "1 + 2 + … + n"), (r"$x \ge -3$", "x ≥ −3"), (r"$e^{-\lambda t}$", "e^(−λt)"),
    (r"$M^{q+}$", "M^(q+)"), (r"$(x+)$", "(x+)"),
    (r"$\int x\,dx$", "∫ x dx"), (r"$\sum_{x} P(X=x) = 1$", "∑_x P(X=x) = 1"), (r"$\oint^{b}_{a} f$", "∮_a^b f"),
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
    (r"$\int_0^\pi \sin x\,dx$", "∫₀^π sin x dx"), (r"$\sum_{n=0}^\infty a_n$", "∑_(n=0)^∞ a_n"),  # unbraced \pi, \infty
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
    (r"$\big(x\big)$", "(x)"), (r"$\det A$", "det A"), (r"$\sum\limits_{i=1}^{n} i$", "∑_(i=1)^n i"),
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
    (r"$|\overrightarrow{AB}|=5$", "|→AB| = 5"), (r"$\vec{a}$", "a⃗"), (r"$\vec{F}_{net}$", "F⃗_net"),
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


@pytest.mark.parametrize("tex,want", [  # a condition over a reaction arrow: one line, the arrow spaced like any other
    (r"$A \xrightarrow{\Delta} B$", "A —Δ→ B"), (r"$A \xrightarrow{\text{heat}} B$", "A —heat→ B"),
    (r"$A \xrightarrow[\text{cat}]{\text{heat}} B$", "A —heat, cat→ B"), (r"$A \xleftarrow{x} B$", "A ←x— B"),
    (r"$A \xrightarrow{} B$", "A → B"), (r"$A \xrightleftharpoons{} B$", "A ⇌ B"),
    (r"$A \xrightleftharpoons{K} B$", "A —K⇌ B"), (r"$A \overset{\Delta}{\rightarrow} B$", "A —Δ→ B"),
    (r"$\ce{A ->[heat] B}$", "A —heat→ B"), (r"$\ce{A ->[\Delta] B}$", "A —Δ→ B"),
    (r"$\ce{CaCO3 ->[heat] CaO + CO2}$", "CaCO₃ —heat→ CaO + CO₂"),
    (r"$\ce{CH3CH2OH ->[conc. H2SO4] CH2=CH2 + H2O}$", "CH₃CH₂OH —conc. H₂SO₄→ CH₂=CH₂ + H₂O"),
    (r"$\ce{A ->[Ni][150 ^\circ C] B}$", "A —Ni, 150 °C→ B"),
    (r"$\ce{A <-> B}$", "A ⟷ B"), (r"$\ce{N2 + 3H2 <=>> 2NH3}$", "N₂ + 3H₂ ⇌ 2NH₃"),
    (r"$\overset{a}{b}$", "b^a"), (r"$\underset{x}{\max}$", "max_x"),
])
def test_labelled_arrows_read_in_one_line(tex, want):
    assert to_terminal(tex) == want


@pytest.mark.parametrize("tex,want", [  # a subscript with no Unicode form: a short lowercase label on a capital joins
    (r"$K_c$", "K_c"), (r"$K_w=[\ce{H+}][\ce{OH-}]$", "K_w = [H⁺][OH⁻]"), (r"$E_{cell}$", "E_cell"),
    (r"$K_c=\frac{[C]^c[D]^d}{[A]^a[B]^b}$", "K_c = [C]^c[D]^d/([A]^a[B]^b)"), (r"$F_y=F\sin\theta$", "F_y = F sin θ"),
    (r"$E^{\ominus}_{\text{cell}}$", "E_cell⦵"), (r"$\Delta H_f^\ominus$", "ΔH_f⦵"), (r"$\Delta H_c^{\ominus}$", "ΔH_c⦵"),
    (r"$\Delta G^\ominus=-nFE^\ominus_{cell}$", "ΔG⦵ = −nFE_cell⦵"), (r"$S_\infty=\frac{a}{1-r}$", "S∞ = a/(1 − r)"),
    # otherwise the underscore stays: same case, a capital label, a coordinate (x, y, z), a long word
    (r"$b=\frac{S_{xy}}{S_{xx}}$", "b = S_xy/S_xx"), (r"$v_y$", "v_y"), (r"$N_A$", "N_A"), (r"$T_{\text{K}}$", "T_K"), (r"$\sum S_{products}$", "∑ S_products"),
    (r"$p_{\ce{NH3}}$", "p_NH₃"), (r"$\Delta_f H^\ominus$", "Δ_f H⦵"),
    # either way: a space before the next letter, and no brackets the subscript does not need
    (r"$k_B T$", "k_B T"), (r"$E=\frac{3}{2}k_B T$", "E = ³⁄₂k_B T"), (r"$v_y^2$", "v_y²"),
    (r"$\sqrt{v^2-v_y^2}$", "√(v² − v_y²)"), (r"$\frac{1}{R_T}$", "1/R_T"), (r"$K_c^2$", "K_c²"),
    (r"$K_p=\frac{p_C^2}{p_A p_B}$", "K_p = p_C²/(p_A p_B)"), (r"$^{x}_{y}\mathrm{A}$", "^x_y A"),
])
def test_subscripts_without_a_unicode_form(tex, want):
    assert to_terminal(tex) == want


@pytest.mark.parametrize("tex,want", [  # found by running a typical A-Level paper's maths through
    (r"$\therefore x = 2$", "∴ x = 2"), (r"$x=2 \because y>0$", "x = 2 ∵ y > 0"), (r"$AB \perp CD$", "AB ⊥ CD"),
    (r"$AB \parallel CD$", "AB ∥ CD"), (r"$A \cup B$", "A ∪ B"), (r"$P(A\cap B)$", "P(A ∩ B)"),
    (r"$A \setminus B$", "A ∖ B"),
    (r"$\operatorname{arcosh} x$", "arcosh x"), (r"$\operatorname{Re}(z)$", "Re(z)"), (r"$\sech^2 x$", "sech² x"),
    (r"$\operatorname{arsinh}(x)$", "arsinh(x)"), (r"$\coth x$", "coth x"),
    (r"$z^* = x - iy$", "z* = x − iy"), (r"$zz^{*}=|z|^2$", "zz* = |z|²"),
    (r"$\mathrm{pH}=\mathrm{p}K_a+\log\frac{[\ce{A-}]}{[\ce{HA}]}$", "pH = pK_a + log [A⁻]/[HA]"),
    (r"$K_a=\frac{[\ce{H+}][\ce{A-}]}{[\ce{HA}]}$", "K_a = [H⁺][A⁻]/[HA]"), (r"$\frac{P(A)}{P(B)}$", "P(A)/(P(B))"),
    (r"$\varepsilon = -N\frac{d\Phi}{dt}$", "ε = −N dΦ/dt"), (r"$F=\frac{dp}{dt}$", "F = dp/dt"),
    (r"$\abs{x}+\norm{\mathbf{v}}$", "|x| + ‖𝐯‖"), (r"$\dv{y}{x}$", "dy/dx"), (r"$\pdv{f}{x}$", "∂f/∂x"),
    (r"$\qty{9.81}{m.s^{-2}}$", "9.81 m.s⁻²"), (r"$\unit{kJ\,mol^{-1}}$", "kJ mol⁻¹"), (r"$\pu{-890 kJ mol-1}$", "−890 kJ mol⁻¹"),
    (r"$\boxed{x=2}$", "x = 2"), (r"$x\phantom{0}=1$", "x = 1"), (r"$\textcolor{red}{x}+\color{blue}y$", "x + y"),
    (r"$10\textsuperscript{th}$", "10^(th)"), ("$$\n\\chemfig{H-O-H}\n$$", "H-O-H"), (r"$\chemfig{CH_3-[:30]OH}$", "CH₃-OH"),
])
def test_paper_maths_reads_as_printed(tex, want):
    assert to_terminal(tex) == want


# --- sub/superscripts: only glyphs every terminal font draws are turned into Unicode; the rest are written linearly ---
from pathlib import Path  # noqa: E402

from tutor_app import texmath  # noqa: E402

_REPO = Path(__file__).resolve().parents[2]


@pytest.mark.parametrize("tex,want", [
    (r"$v_{initial}$", "v_initial"), (r"$E_k$", "E_k"), (r"$x_{max}$", "x_max"), (r"$T_{1/2}$", "T½"),
    (r"$x_{1/2}$", "x_(1/2)"), (r"$x_{n+1}$", "x_(n+1)"), (r"$a_{i,j}$", "a_(i,j)"), (r"$\beta_{max}$", "β_max"),
    (r"$^{14}_{6}\mathrm{C}$", "¹⁴₆C"), (r"$10^{-3}$", "10⁻³"), (r"$10^{−3}$", "10⁻³"), (r"$\mathrm{m\,s^{-2}}$", "m s⁻²"),
    (r"$e^{-kt}$", "e^(−kt)"), (r"$x^n$", "xⁿ"), (r"$x^i$", "xⁱ"), (r"$x^{2n}$", "x^(2n)"), (r"$x^a$", "x^a"),
    (r"$2^{n+1}$", "2^(n+1)"), (r"$\mathrm{H_2O}$", "H₂O"), (r"$\ce{Cu^2+}$", "Cu²⁺"), (r"$\ce{SO4^{2-}}$", "SO₄²⁻"),
    (r"$\int_0^1 x^2\,dx$", "∫₀¹ x² dx"), (r"$\sum_{i=1}^{n} i$", "∑_(i=1)^n i"), (r"$\sum_{i=1}^{10} i$", "∑_(i=1)^(10) i"),
    (r"$\lim_{x\to0}f$", "lim[x→0] f"), (r"$\log_{10}x$", "log₁₀ x"), (r"$\log_b x$", "log_b x"),
])
def test_scripts_are_unicode_only_when_every_glyph_is_safe(tex, want):
    assert to_terminal(tex) == want


def test_units_in_plain_text_keep_their_safe_glyphs():
    assert pretty_units("a = 9.8 m s^-2 and 10^-3") == "a = 9.8 m s⁻² and 10⁻³"


def test_raw_unsafe_glyphs_typed_into_text_are_drawn_linearly():
    assert to_terminal("Eₖ and vᵢₙᵢₜᵢₐₗ, Kₚ, xᵃ") == "E_k and v_initial, K_p, x^a"
    assert to_terminal("H₂O, Cu²⁺, m s⁻², xⁿ stay") == "H₂O, Cu²⁺, m s⁻², xⁿ stay"
    assert to_terminal("$Eₖ=\\tfrac12mv^2$") == "E_k = ½mv²"


def test_a_card_never_draws_a_wobbly_glyph():
    out = shown(cards.card("ai", "Tutor", r"The speed $v_{initial}$ and energy $E_k$ with $x_{n+1}$ and $T_{1/2}$."))
    assert "v_initial" in out and "E_k" in out and "x_(n+1)" in out and "T½" in out
    assert not [ch for ch in out if ch in texmath.UNSAFE_GLYPHS]


def _cmaps():
    fonttools = pytest.importorskip("fontTools.ttLib")
    out = {"JuliaMono": set(fonttools.TTFont(_REPO / "app/tutor_app/fonts/JuliaMono-Regular.ttf").getBestCmap())}
    menlo = Path("/System/Library/Fonts/Menlo.ttc")
    if menlo.exists():
        out["Menlo"] = set(fonttools.TTCollection(str(menlo)).fonts[0].getBestCmap())
    sf = Path("/System/Applications/Utilities/Terminal.app/Contents/Resources/Fonts/SF-Mono-Regular.otf")
    if sf.exists():
        out["SF Mono"] = set(fonttools.TTFont(str(sf)).getBestCmap())
    return out


def test_the_safe_set_is_in_the_terminal_fonts_and_the_unsafe_glyphs_are_not_all_of_them():
    fonts = _cmaps()
    for name, cmap in fonts.items():
        if name == "SF Mono":  # draws the superscripts; it has no subscripts at all, so those come from one fallback font
            assert {ord(c) for c in texmath.SAFE_SUP} <= cmap, name
        else:
            assert {ord(c) for c in texmath.SAFE_GLYPHS} <= cmap, name
    if "Menlo" in fonts:  # the very letters that made the text wobble: not in Menlo, so the terminal swaps fonts per glyph
        missing = {c for c in "ₕₖₗₘₙₚₛₜ" if ord(c) not in fonts["Menlo"]}
        assert missing == set("ₕₖₗₘₙₚₛₜ") and missing <= texmath.UNSAFE_GLYPHS


def _strings(obj):
    if isinstance(obj, str):
        yield obj
    elif isinstance(obj, list):
        for x in obj:
            yield from _strings(x)
    elif isinstance(obj, dict):
        for x in obj.values():
            yield from _strings(x)


def test_no_real_content_string_renders_with_an_unsafe_script_glyph():
    import json
    seen: set[str] = set()
    for f in sorted((_REPO / "build/out/packs").rglob("*.json")):
        seen.update(_strings(json.loads(f.read_text(encoding="utf-8"))))
    for f in sorted((_REPO / "build/out/notes").rglob("*.md")):
        seen.update(f.read_text(encoding="utf-8").split("\n\n"))
    bad = [s[:80] for s in seen if any(c in texmath.UNSAFE_GLYPHS for c in to_terminal(s))]
    assert not bad, bad[:5]
