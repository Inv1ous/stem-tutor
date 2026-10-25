"""The named AI maths corpus keeps semantics when adapting LaTeX to JuliaMono."""
from __future__ import annotations

import pytest

from tutor_app.stem_math import render_math


@pytest.mark.parametrize("expr,want", [
    pytest.param("x_1+x_i+x_n+E_k", "𝑥₁ + 𝑥ᵢ + 𝑥ₙ + 𝐸ₖ", id="mixed-variable-indices"),
    pytest.param("x_{n+1}", "𝑥ₙ₊₁", id="whole-subscript-group"),
    pytest.param("e^{-kt}", "𝑒⁻ᵏᵗ", id="whole-power-group"),
    pytest.param("x_N", "𝑥[index: 𝑁]", id="unsupported-index-label"),
    pytest.param("x^{a+Q}", "(𝑥) to the power (𝑎 + 𝑄)", id="unsupported-power-label"),
    pytest.param("x^{2n}", "𝑥²ⁿ", id="numeric-letter-power"),
    pytest.param(r"\frac{dy}{dx}=3x^2", "d𝑦/d𝑥 = 3𝑥²", id="upright-derivative-d"),
    pytest.param(r"\frac{d^2y}{dx^2}", "d²𝑦/d𝑥²", id="higher-derivative"),
    pytest.param(r"\dv{y}{x}", "d𝑦/d𝑥", id="physics-derivative"),
    pytest.param(r"\pdv{f}{x}", "∂𝑓/∂𝑥", id="partial-derivative"),
    pytest.param(r"\sin x+\ln y", "sin 𝑥 + ln 𝑦", id="upright-function-names"),
    pytest.param(r"\operatorname{Re}(z)", "Re(𝑧)", id="named-operator"),
    pytest.param(r"\operatorname*{argmax}_{x} f(x)", "argmaxₓ 𝑓(𝑥)", id="starred-named-operator"),
    pytest.param(r"\operatorname{argmax}^{Q}x", "(argmax) to the power (𝑄) 𝑥", id="whole-named-operator-power"),
    pytest.param(r"\lim_{x\to0}\frac{\sin x}{x}", "lim[𝑥 → 0] (sin 𝑥)/𝑥", id="function-limit"),
    pytest.param(r"\sin^{Q}x", "(sin) to the power (𝑄) 𝑥", id="whole-function-power-fallback"),
    pytest.param(r"\mathit{x}+\it{y}", "𝑥 + 𝑦", id="italic-alias"),
    pytest.param(r"\mathbf{F}=m\boldsymbol{a}", "𝐅 = 𝑚𝐚", id="bold-vectors"),
    pytest.param(r"\widehat{ABC}", "∠𝐴𝐵𝐶", id="widehat-angle"),
    pytest.param(r"\vec{a+b}", "→(𝑎 + 𝑏)", id="compound-vector-scope"),
    pytest.param(r"\mathbb{R}+\mathcal{L}+\mathfrak{g}+\mathtt{A}", "ℝ + 𝓛 + 𝔤 + 𝙰", id="math-alphabet-aliases"),
    pytest.param(r"\alpha+\beta", "𝛼 + 𝛽", id="greek-variables"),
    pytest.param(r"v=3\,\mathrm{m\,s^{-2}}", "𝑣 = 3 m s⁻²", id="upright-units"),
    pytest.param(r"\SI{3.0e8}{m s^{-1}}", "3.0e8 m s⁻¹", id="quantity-units"),
    pytest.param(r"\text{rate}=k[A]^2", "rate = 𝑘[𝐴]²", id="upright-descriptive-label"),
    pytest.param(r"\mathrm{AB}^{Q}", "(AB) to the power (𝑄)", id="whole-upright-identifier-power"),
    pytest.param(r"\mathrm{m s}^{2}", "(m s)²", id="compound-upright-unit-power"),
    pytest.param(r"\mathrm{a+b}^{2}", "(a + b)²", id="compound-upright-sum-power"),
    pytest.param(r"\ce{H2O + Fe3+}", "H₂O + Fe³⁺", id="chemistry-elements-and-charge"),
    pytest.param(r"^{14}_{6}\mathrm{C}", "¹⁴₆C", id="nuclide"),
    pytest.param(r"\frac{a+b}{c}", "(𝑎 + 𝑏)/𝑐", id="fraction-grouping"),
    pytest.param(r"\frac{1}{2a}", "1/(2𝑎)", id="denominator-grouping"),
    pytest.param(r"a/\frac{b}{c}", "𝑎/(𝑏/𝑐)", id="fraction-as-slash-denominator"),
    pytest.param(r"a/{\frac{b}{c}}", "𝑎/(𝑏/𝑐)", id="grouped-fraction-as-slash-denominator"),
    pytest.param(r"a/\mathrm{\frac{b}{c}}", "𝑎/(b/c)", id="upright-fraction-as-slash-denominator"),
    pytest.param(r"\sqrt{a^2+b^2}", "√(𝑎² + 𝑏²)", id="root-grouping"),
    pytest.param(r"\sqrt{x^Q}", "√((𝑥) to the power (𝑄))", id="root-over-power-fallback"),
    pytest.param(r"\sqrt{\mathrm{a+b}^Q}", "√((a + b) to the power (𝑄))", id="root-over-compound-power-fallback"),
    pytest.param(r"\sqrt[3]{x}", "∛𝑥", id="cube-root"),
    pytest.param(r"\sqrt[Q]{x}", "root[index: 𝑄](𝑥)", id="root-index-fallback"),
    pytest.param(r"\sqrt[a^2]{x}", "root[index: 𝑎²](𝑥)", id="compound-root-index"),
    pytest.param(r"\sum_{i=1}^{n}x_i", "∑[𝑖 = 1 to 𝑛] 𝑥ᵢ", id="sum-bound-separation"),
    pytest.param(r"\int_0^\pi\sin x\,dx", "∫[0 to π] sin 𝑥 d𝑥", id="integral-bounds"),
    pytest.param(r"\int_0^\pi\sin x\,dx=2", "∫[0 to π] sin 𝑥 d𝑥 = 2", id="integral-differential-before-equals"),
    pytest.param(r"\int_0^1 x\,dx≤1", "∫[0 to 1] 𝑥 d𝑥 ≤ 1", id="integral-differential-before-unicode-relation"),
    pytest.param(r"\int_0^1 x\,dx\geq0", "∫[0 to 1] 𝑥 d𝑥 ≥ 0", id="integral-differential-before-relation-macro"),
    pytest.param("dx=2", "𝑑𝑥 = 2", id="ordinary-d-variable-before-equals"),
    pytest.param(r"\int_0^1 x^2 dx", "∫[0 to 1] 𝑥² d𝑥", id="plain-spaced-integral-differential"),
    pytest.param(r"\int x\,d\theta", "∫ 𝑥 d𝜃", id="greek-differential"),
    pytest.param(r"\frac{\partial^2 f}{\partial x^2}", "∂²𝑓/∂𝑥²", id="upright-partial-operator"),
    pytest.param(r"\iint_D f\,dx\,dy", "∬[over 𝐷] 𝑓 d𝑥 d𝑦", id="double-integral-bound-separation"),
    pytest.param(r"\begin{pmatrix}a&b\\c&d\end{pmatrix}", "(𝑎  𝑏; 𝑐  𝑑)", id="matrix-rows-and-columns"),
    pytest.param(r"\begin{aligned}y&=x+1\\z&=2x\end{aligned}", "𝑦 = 𝑥 + 1\n𝑧 = 2𝑥", id="aligned-rows"),
    pytest.param(r"\bot", "⊥", id="bottom-symbol"),
    pytest.param("a*b*c", "𝑎∗𝑏∗𝑐", id="multiplication-preserved"),
    pytest.param(r"25\%", "25%", id="percentage"),
    pytest.param("3.0e-8", "3.0e−8", id="scientific-notation"),
    pytest.param("∂f/∂x+π", "∂𝑓/∂𝑥 + π", id="literal-calculus-symbols"),
    pytest.param(r"\left(0,1\right]", "(0,1]", id="half-open-interval-delimiters"),
    pytest.param(r"\begin{aligned}a&=b&c&=d\end{aligned}", "𝑎 = 𝑏 𝑐 = 𝑑", id="alignment-cell-separation"),
])
def test_common_stem_corpus(expr, want):
    result = render_math(expr)
    assert result == want
    assert not any(char in result for char in "\\^_")


@pytest.mark.parametrize("expr", [
    r"\unknown{x}", r"\frac{x}", r"\sqrt{", "x^{2", "x_", "x^^2",
    r"\begin{unknown}x\end{unknown}", r"\begin{aligned}x&=1\end{matrix}",
    r"\newcommand{\foo}{x}\foo", "x} + {y", "", "$x$", "a&b",
    r"\left(x+1", r"\right)x", r"\left", r"\sqrt{}", r"\frac{}{}",
])
def test_unsupported_or_malformed_math_requests_exact_source_fallback(expr):
    assert render_math(expr) is None


def test_ai_scripts_do_not_change_the_authored_content_renderer():
    from tutor_app.texmath import to_terminal

    assert to_terminal(r"$x_i+e^{-kt}+\mathit{x}$") == "x_i + e^(−kt) + x"
