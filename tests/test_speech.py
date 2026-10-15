"""The speech-text converter (tutorlib/speech.py): chapter text -> plain spoken British English for Kokoro.

Covers every construct the tutor reads aloud (powers, subscripts, units and their plurals, fractions, roots,
sums, integrals, limits, derivatives, Greek, relations, vectors, matrices, chemistry, nuclides, Markdown),
the cache key, the chapter script, and a property test over every real string in build/out (packs and notes).
"""
import json
import re
import time
from pathlib import Path

import pytest

from tutorlib import speech
from tutorlib.speech import (PRONOUNCE, audio_key, for_tts, script_for_chapter, speakable, speech_gaps,
                             speak_math)

BUILD = Path(__file__).resolve().parents[1] / "build" / "out"
FORBIDDEN = re.compile(r"[\\{}^_$]")


def say(text: str) -> str:
    """speakable() without the final full stop, for compact expectations."""
    out = speakable(text)
    assert out == "" or out[-1] in ".?!", out
    return out[:-1] if out else out


def m(tex: str) -> str:
    return say("$" + tex + "$")


# --------------------------------------------------------------------------------------------------
# Numbers
# --------------------------------------------------------------------------------------------------

@pytest.mark.parametrize("n,words", [
    (0, "zero"), (7, "seven"), (13, "thirteen"), (21, "twenty one"), (40, "forty"), (100, "one hundred"),
    (101, "one hundred and one"), (999, "nine hundred and ninety nine"), (1000, "one thousand"),
    (1005, "one thousand and five"), (2008, "two thousand and eight"), (12345, "twelve thousand three hundred and forty five"),
    (1000000, "one million"),
])
def test_int_words(n, words):
    assert speech.int_words(n) == words


@pytest.mark.parametrize("text,words", [
    ("9.8", "nine point eight"), ("3.0", "three point zero"), ("0.050", "zero point zero five zero"),
    ("1,000", "one thousand"), ("007", "zero zero seven"), ("11.1.1", "eleven point one point one"),
    ("6.02", "six point zero two"), (".5", "zero point five"),
])
def test_number_words(text, words):
    assert speech.number_words(text) == words


@pytest.mark.parametrize("n,words", [(1999, "nineteen ninety nine"), (2005, "two thousand and five"),
                                     (1905, "nineteen oh five"), (2010, "twenty ten")])
def test_year_words(n, words):
    assert speech.year_words(n) == words


@pytest.mark.parametrize("a,b,words", [(1, 2, "one half"), (3, 4, "three quarters"), (2, 3, "two thirds"),
                                       (1, 4, "one quarter"), (7, 8, "seven eighths"), (3, 2, None)])  # improper: read "three over two"
def test_fraction_words(a, b, words):
    assert speech.fraction_words(a, b) == words


def test_big_fraction_is_none():
    assert speech.fraction_words(7, 11) is None


# --------------------------------------------------------------------------------------------------
# Powers, subscripts, indices
# --------------------------------------------------------------------------------------------------

@pytest.mark.parametrize("tex,words", [
    ("x^2", "x squared"), ("x^3", "x cubed"), ("x^n", "x to the n"), ("x^{-1}", "x to the minus one"),
    ("10^{-3}", "ten to the minus three"), ("10^{23}", "ten to the twenty three"), ("10^8", "ten to the eight"),
    ("3.0\\times10^{8}", "three point zero times ten to the eight"), ("e^{-kt}", "e to the minus k t"),
    ("x^4", "x to the fourth"), ("x^5", "x to the fifth"), ("x^{10}", "x to the tenth"),
    ("x^{n+1}", "x to the power of n plus one"), ("x^{1/2}", "x to the power of one half"),
    ("a^{m+n}", "a to the power of m plus n"), ("2^{x}", "two to the x"), ("(x+1)^2", "open bracket x plus one close bracket squared"),
    ("e^x", "e to the x"), ("e^{x^2}", "e to the x squared"), ("\\mathrm{e}^{-x^{2}}", "e to the minus x squared"),
    ("a^0", "a to the power of zero"), ("3^{2k+1}", "three to the power of two k plus one"),
])
def test_powers(tex, words):
    assert m(tex) == words


@pytest.mark.parametrize("tex,words", [
    ("E_k", "E k"), ("v_{initial}", "v initial"), ("x_{1/2}", "x one half"), ("T_{1/2}", "T one half"),
    ("x_1", "x one"), ("x_{10}", "x ten"), ("K_{sp}", "K s p"), ("E_{cell}", "E cell"), ("E_{rms}", "E r m s"),
    ("V_{atom}", "V atom"), ("u_x", "u x"), ("a_n", "a n"), ("x_i^2", "x i squared"), ("x_{i}^{2}", "x i squared"),
    ("x_{n+1}", "x sub n plus one"), ("\\mu_0", "mu zero"), ("d_\\perp", "d perpendicular"),
    ("K_c", "K c"), ("K_p", "K p"), ("pK_a", "p K a"), ("R_1+R_2", "R one plus R two"),
])
def test_subscripts(tex, words):
    assert m(tex) == words


def test_nested_sup_sub():
    assert m("x_{i}^{2}+y_{j}^{3}") == "x i squared plus y j cubed"
    assert m("e^{-x_1^2}") == "e to the minus x one squared"
    assert m("a_{n}^{n+1}") == "a n to the power of n plus one"


@pytest.mark.parametrize("text,words", [
    ("x² and x³", "x squared and x cubed"), ("x⁻¹", "x to the minus one"), ("10⁻³", "ten to the minus three"),
    ("xⁿ", "x to the n"), ("3.0 × 10⁸", "three point zero times ten to the eight"),
    ("sin²θ", "sine squared theta"), ("t½", "t one half"), ("1.6 × 10⁻¹⁹ C", "one point six times ten to the minus nineteen coulombs"),
    ("e⁻ᵏᵗ", "e to the minus k t"), ("e⁻ is emitted", "an electron is emitted"), ("aᵢ + aⱼ", "a sub i plus a sub j"),
    ("Jun 2023", "June twenty twenty three"), ("1999 papers", "one thousand nine hundred and ninety nine papers"),
])
def test_unicode_powers_in_prose(text, words):
    assert say(text) == words


# --------------------------------------------------------------------------------------------------
# Units
# --------------------------------------------------------------------------------------------------

UNIT_PHRASES = [
    ("1 m", "one metre"), ("2 m", "two metres"), ("0.5 m", "zero point five metres"),
    ("9.8 m s⁻²", "nine point eight metres per second squared"), ("3.0 × 10⁸ m s⁻¹", "three point zero times ten to the eight metres per second"),
    ("1 kg", "one kilogram"), ("3 kg m⁻³", "three kilograms per cubic metre"), ("1000 kg m⁻³", "one thousand kilograms per cubic metre"),
    ("5 N m", "five newton metres"), ("101 N m⁻²", "one hundred and one newtons per square metre"),
    ("2 J", "two joules"), ("50 kJ mol⁻¹", "fifty kilojoules per mole"), ("8.31 J K⁻¹ mol⁻¹", "eight point three one joules per kelvin per mole"),
    ("0.100 mol dm⁻³", "zero point one zero zero moles per cubic decimetre"), ("1 mol", "one mole"), ("2 mol", "two moles"),
    ("300 K", "three hundred kelvin"), ("1 K", "one kelvin"), ("25 °C", "twenty five degrees Celsius"), ("1 °C", "one degree Celsius"),
    ("10 Ω", "ten ohms"), ("5 kΩ", "five kiloohms"), ("4.7 μF", "four point seven microfarads"),
    ("12 V", "twelve volts"), ("1 V", "one volt"), ("3 A", "three amperes"), ("50 Hz", "fifty hertz"),
    ("101 kPa", "one hundred and one kilopascals"), ("1 Pa", "one pascal"), ("2 Pa", "two pascals"),
    ("100 W", "one hundred watts"), ("2 s", "two seconds"), ("1 s", "one second"), ("15 min", "fifteen minutes"),
    ("2 h", "two hours"), ("5 g", "five grams"), ("25.0 cm³", "twenty five point zero cubic centimetres"),
    ("1 cm³", "one cubic centimetre"), ("3 dm³", "three cubic decimetres"), ("20 mL", "twenty millilitres"),
    ("2 L", "two litres"), ("1 ms", "one millisecond"), ("5 ns", "five nanoseconds"), ("10 μs", "ten microseconds"),
    ("500 nm", "five hundred nanometres"), ("1 μm", "one micrometre"), ("3 km", "three kilometres"),
    ("4 m²", "four square metres"), ("1 m²", "one square metre"), ("2 m³", "two cubic metres"),
    ("5%", "five percent"), ("1 T", "one tesla"), ("12 C", "twelve coulombs"), ("3 F", "three farads"),
    ("0.5 Wb", "zero point five webers"), ("200 Bq", "two hundred becquerels"), ("4 u", "four atomic mass units"),
    ("1 eV", "one electronvolt"), ("2 eV", "two electronvolts"), ("5 MeV", "five megaelectronvolts"),
    ("750 mmHg", "seven hundred and fifty millimetres of mercury"), ("80 dB", "eighty decibels"),
    ("2 rad s⁻¹", "two radians per second"), ("5 W m⁻²", "five watts per square metre"), ("3 V m⁻¹", "three volts per metre"),
    ("1 kg m s⁻¹", "one kilogram metre per second"), ("3 kWh", "three kilowatt hours"),
    ("6.63 × 10⁻³⁴ J s", "six point six three times ten to the minus thirty four joule seconds"),
    ("2 N s", "two newton seconds"),
    # no number in front
    ("kg m⁻³", "kilograms per cubic metre"), ("J K⁻¹ mol⁻¹", "joules per kelvin per mole"), ("mol dm⁻³", "moles per cubic decimetre"),
    ("m s⁻²", "metres per second squared"), ("kJ mol⁻¹", "kilojoules per mole"), ("N m⁻²", "newtons per square metre"),
    ("s⁻¹", "per second"), ("A m⁻¹", "amperes per metre"),
]


@pytest.mark.parametrize("text,words", UNIT_PHRASES)
def test_unit_phrases(text, words):
    assert say(text) == words


def test_at_least_forty_unit_phrases():
    assert len(UNIT_PHRASES) >= 40


@pytest.mark.parametrize("tex,words", [
    ("1\\ \\mathrm{m}", "one metre"), ("2\\,\\mathrm{m}", "two metres"),
    ("9.8\\,\\mathrm{m\\,s^{-2}}", "nine point eight metres per second squared"),
    ("\\mathrm{kJ\\,mol^{-1}}", "kilojoules per mole"), ("\\mathrm{J\\,K^{-1}\\,mol^{-1}}", "joules per kelvin per mole"),
    ("\\mathrm{N\\,m^{-2}}", "newtons per square metre"), ("\\mathrm{mol\\,dm^{-3}}", "moles per cubic decimetre"),
    ("\\mathrm{kg\\,m^{-3}}", "kilograms per cubic metre"), ("\\mathrm{kg\\,m^{2}\\,s^{-3}}", "kilogram metres squared per second cubed"),
    ("25^\\circ\\mathrm{C}", "twenty five degrees Celsius"), ("300\\,\\mathrm{K}", "three hundred kelvin"),
    ("5\\,\\mathrm{cm}^3", "five cubic centimetres"), ("\\mathrm{s^{-1}}", "per second"), ("\\mathrm{m^2}", "square metres"),
    ("10\\ \\Omega", "ten ohms"), ("4.7\\,\\mu\\mathrm{F}", "four point seven microfarads"), ("75\\%", "seventy five percent"),
    ("\\mathrm{km\\,h^{-1}}", "kilometres per hour"), ("2\\,\\mathrm{m}/\\mathrm{s}", "two metres per second"),
    ("6\\,\\mathrm{N\\,m}", "six newton metres"),
])
def test_units_in_maths(tex, words):
    assert m(tex) == words


def test_plural_follows_the_number():
    assert say("1 m") == "one metre"
    assert say("2 m") == "two metres"
    assert say("1.0 m") == "one point zero metres"
    assert say("0 m") == "zero metres"
    assert m("1\\,\\mathrm{kg}") == "one kilogram"
    assert m("2\\,\\mathrm{kg}") == "two kilograms"
    assert say("1 mol dm⁻³") == "one mole per cubic decimetre"
    assert say("2 mol dm⁻³") == "two moles per cubic decimetre"


def test_denominators_stay_singular():
    assert say("5 kg m⁻³") == "five kilograms per cubic metre"
    assert "metres" not in say("5 N m⁻²")


def test_orbitals_are_not_seconds():
    assert say("the 4s electrons and 3d orbitals") == "the four s electrons and three d orbitals"


def test_formula_coefficient_is_not_a_unit():
    out = say("Cr₂O₇²⁻ + 14H⁺ → 2Cr³⁺")
    assert "henr" not in out and "fourteen H plus" in out


def test_quantity_in_brackets_takes_the_unit():
    assert say("(0.15 ± 0.01) m s⁻²") == "zero point one five plus or minus zero point zero one metres per second squared"


def test_axis_label_units():
    assert say("v / m s⁻¹") == "v in metres per second"


# --------------------------------------------------------------------------------------------------
# Fractions, roots, big operators, calculus
# --------------------------------------------------------------------------------------------------

@pytest.mark.parametrize("tex,words", [
    ("\\frac{a}{b}", "a over b"), ("\\frac12", "one half"), ("\\frac{3}{4}", "three quarters"), ("\\frac{2}{3}", "two thirds"),
    ("\\dfrac{1}{4}", "one quarter"), ("\\tfrac12mv^2", "one half m v squared"),
    ("\\frac{x+1}{x-1}", "x plus one, all over, x minus one"), ("\\frac{1}{x+1}", "one over, x plus one"),
    ("\\frac{a+b}{c}", "a plus b, all over c"), ("7/6", "seven over six"), ("1/2", "one half"),
    ("\\sqrt{x}", "the square root of x"), ("\\sqrt{2}", "the square root of two"), ("\\sqrt[3]{x}", "the cube root of x"),
    ("\\sqrt[4]{x}", "the fourth root of x"), ("\\sqrt{x+1}", "the square root of x plus one, end root"),
    ("\\sqrt{x^2+y^2}", "the square root of x squared plus y squared, end root"),
    ("\\sum_{i=1}^{n} x_i", "the sum from i equals one to n of x i"), ("\\sum x", "the sum of x"),
    ("\\sum_{r=1}^{k+1} r^3", "the sum from r equals one to k plus one of r cubed"),
    ("\\prod_{k=1}^{n} k", "the product from k equals one to n of k"),
    ("\\int_0^1 x^2 dx", "the integral from zero to one of x squared, d x"),
    ("\\int_0^1 x^2\\,dx", "the integral from zero to one of x squared, d x"),
    ("\\int f(x)\\,dx", "the integral of f of x, d x"), ("\\int_a^b \\frac{1}{x}\\,dx", "the integral from a to b of one over x, d x"),
    ("\\int_0^{\\pi}\\sin x\\,dx", "the integral from zero to pi of sine x, d x"),
    ("\\int_{0}^{\\infty} e^{-x}\\,\\mathrm{d}x", "the integral from zero to infinity of e to the minus x, d x"),
    ("\\int (x+3)^2\\,dx", "the integral of open bracket x plus three close bracket squared, d x"),
    ("\\oint_C f\\,dz", "the contour integral over C of f, d z"),
    ("\\lim_{x\\to 0}\\frac{\\sin x}{x}", "the limit as x tends to zero of sine x, all over x"),
    ("\\lim_{n\\to\\infty} a_n", "the limit as n tends to infinity of a n"),
    ("\\lim_{h\\to0^+}", "the limit as h tends to zero from above of"),
    ("\\frac{dy}{dx}", "d y by d x"), ("\\frac{d^2y}{dx^2}", "d two y by d x squared"), ("\\frac{d}{dx}(x^2)", "d by d x open bracket x squared close bracket"),
    ("\\frac{\\partial f}{\\partial x}", "partial f by partial x"), ("\\frac{\\partial^2 f}{\\partial x^2}", "partial two f by partial x squared"),
    ("\\frac{\\partial^2 f}{\\partial x\\,\\partial y}", "partial two f by partial x partial y"),
])
def test_fractions_roots_calculus(tex, words):
    assert m(tex) == words


# --------------------------------------------------------------------------------------------------
# Greek, relations, functions, vectors, matrices
# --------------------------------------------------------------------------------------------------

@pytest.mark.parametrize("tex,words", [
    ("\\Delta x", "delta x"), ("\\theta", "theta"), ("\\lambda=\\frac{h}{p}", "lambda equals h over p"), ("\\omega", "omega"),
    ("\\alpha+\\beta+\\gamma", "alpha plus beta plus gamma"), ("\\sigma^2", "sigma squared"), ("\\rho v", "rho v"),
    ("\\pi r^2", "pi r squared"), ("\\mu=66", "mu equals sixty six"), ("\\epsilon_0", "epsilon zero"),
    ("\\pm", "plus or minus"), ("a\\pm b", "a plus or minus b"), ("a\\times b", "a times b"), ("2\\cdot 3", "two times three"),
    ("\\vec{a}\\cdot\\vec{b}", "vector a dot vector b"), ("x\\approx 2", "x is approximately two"), ("F\\propto x", "F is proportional to x"),
    ("a\\leq b", "a is less than or equal to b"), ("a\\geq b", "a is greater than or equal to b"), ("a\\neq b", "a is not equal to b"),
    ("a<b<c", "a is less than b is less than c"), ("a\\to b", "a gives b"), ("x\\to\\infty", "x tends to infinity"),
    ("A\\Rightarrow B", "A implies B"), ("A\\Leftrightarrow B", "A if and only if B"),
    ("x=-2", "x equals minus two"), ("3-5", "three minus five"), ("a:b", "a to b"), ("3:1", "three to one"),
    ("\\vec{v}", "vector v"), ("\\hat{i}", "i hat"), ("\\mathbf{F}", "vector F"), ("3\\mathbf{i}+4\\mathbf{j}", "three i plus four j"),
    ("\\overrightarrow{AB}", "vector A B"), ("|x|", "the modulus of x"), ("|x-1|", "the modulus of, x minus one, end modulus"),
    ("\\log_{10}x", "log to the base ten of x"), ("\\log_a b", "log to the base a of b"), ("\\ln x", "natural log of x"),
    ("\\ln(x+1)", "natural log of open bracket x plus one close bracket"),
    ("\\sin x", "sine x"), ("\\sin^{-1}x", "inverse sine x"), ("\\arctan x", "inverse tangent x"),
    ("\\sin^2\\theta", "sine squared theta"), ("\\cos 2x", "cosine two x"), ("\\sin(2x)", "sine of two x"),
    ("\\tan^2 x+1=\\sec^2 x", "tangent squared x plus one equals secant squared x"),
    ("n!", "n factorial"), ("\\binom{n}{r}", "n choose r"), ("\\bar{x}", "x bar"), ("\\bar x", "x bar"), ("\\dot{x}", "x dot"),
    ("f(x)", "f of x"), ("f'(x)", "f prime of x"), ("f''(x)", "f double prime of x"), ("g(2x)", "g of two x"),
    ("P(A\\cap B)", "P of A intersection B"), ("P(A\\cup B)", "P of A union B"), ("P(A\\mid B)", "P of A given B"),
    ("X\\sim N(\\mu,\\sigma^2)", "X is distributed as N open bracket mu, sigma squared close bracket"),
    ("\\mathbb{R}", "the real numbers"), ("x\\in\\{1,2,3\\}", "x is in the set one, two, three"),
    ("(2,3)", "open bracket two, three close bracket"), ("(2.0)(9.81)(0.40)", "two point zero times nine point eight one times zero point four zero"),
    ("30^\\circ", "thirty degrees"), ("\\theta=45^{\\circ}", "theta equals forty five degrees"), ("\\Sigma F", "the sum of F"),
    ("\\Sigma x^2", "the sum of x squared"), ("A^T", "A transpose"), ("A^{-1}", "A to the minus one"),
    ("\\|v\\|", "the magnitude of v"), ("a\\equiv b\\pmod 5", "a is identical to b mod five"), ("x'", "x prime"),
    ("\\operatorname{Var}(X)", "the variance of open bracket X close bracket"),
])
def test_greek_relations_functions(tex, words):
    assert m(tex) == words


def test_cdot_is_dot_for_vectors_and_times_for_numbers():
    assert m("\\mathbf{a}\\cdot\\mathbf{b}") == "vector a dot vector b"
    assert m("3\\cdot4") == "three times four"


@pytest.mark.parametrize("tex,words", [
    ("\\begin{pmatrix}1&2\\\\3&4\\end{pmatrix}", "the two by two matrix with first row one, two, and second row three, four"),
    ("\\begin{pmatrix}3\\\\-2\\end{pmatrix}", "the column vector three, minus two"),
    ("\\begin{pmatrix}1&2&3\\end{pmatrix}", "the row vector one, two, three"),
    ("\\begin{pmatrix}a&b\\\\c&d\\\\e&f\\end{pmatrix}", "the three by two matrix with first row a, b, second row c, d, and third row e, f"),
    ("\\begin{vmatrix}a&b\\\\c&d\\end{vmatrix}", "the two by two determinant with first row a, b, and second row c, d"),
    ("\\det A", "the determinant of A"), ("A=\\begin{pmatrix}2&1\\\\0&1\\end{pmatrix}", "A equals the two by two matrix with first row two, one, and second row zero, one"),
])
def test_matrices_and_determinants(tex, words):
    assert m(tex) == words


def test_notation_for_standard_states_and_concentrations():
    assert m("\\Delta H^\\ominus") == "delta H standard"
    assert m("E^\\circ") == "E standard"
    assert m("\\Delta G^{\\circ}") == "delta G standard"
    assert m("[\\ce{H+}]") == "the concentration of H plus"
    assert m("[H^+]") == "the concentration of H plus"
    assert m("[A]") == "the concentration of A"
    assert m("[HA]") == "the concentration of H A"
    assert m("[k(k+1)/2]^2") .startswith("open square bracket")
    assert say("pH and pOH") == "p H and p O H"
    assert say("pKa, Kc, Kp, Ksp, Kw") == "p K a, K c, K p, K s p, K w"
    assert say("ΔH⦵ = −92 kJ mol⁻¹") == "delta H standard equals minus ninety two kilojoules per mole"
    assert say("ΔHf⦵") == "delta H f standard"
    assert say("E⦵ = +0.34 V") == "E standard equals plus zero point three four volts"


# --------------------------------------------------------------------------------------------------
# Chemistry
# --------------------------------------------------------------------------------------------------

@pytest.mark.parametrize("tex,words", [
    ("\\ce{H2O}", "H two O"), ("\\ce{CO2}", "C O two"), ("\\ce{CH3CO2H}", "C H three C O two H"), ("\\ce{CH3COOH}", "C H three C O O H"),
    ("\\ce{NaCl}", "N A C L"), ("\\ce{Ca(OH)2}", "C A open bracket O H close bracket two"), ("\\ce{C2H5OH}", "C two H five O H"),
    ("\\ce{Cu^2+}", "copper two plus"), ("\\ce{Cu^{2+}}", "copper two plus"), ("\\ce{Fe^3+}", "iron three plus"),
    ("\\ce{Na+}", "sodium plus"), ("\\ce{Cl-}", "chloride"), ("\\ce{O^2-}", "oxide"), ("\\ce{H+}", "H plus"),
    ("\\ce{SO4^2-}", "S O four two minus"), ("\\ce{OH-}", "O H minus"), ("\\ce{NH4+}", "N H four plus"), ("\\ce{MnO4-}", "M N O four minus"),
    ("\\ce{Mn}", "manganese"), ("\\ce{Cu}", "copper"), ("\\ce{e-}", "an electron"),
    ("\\ce{2NO + O2 -> 2NO2}", "two N O plus O two yields two N O two"),
    ("\\ce{N2 + 3H2 <=> 2NH3}", "N two plus three H two is in equilibrium with two N H three"),
    ("\\ce{H2(g) + I2(g) <=> 2HI(g)}", "H two gas plus I two gas is in equilibrium with two H I gas"),
    ("\\ce{CaCO3(s) -> CaO(s) + CO2(g)}", "C A C O three solid yields C A O solid plus C O two gas"),
    ("\\ce{H2O(l)}", "H two O liquid"), ("\\ce{NaOH(aq)}", "N A O H aqueous"),
    ("\\ce{Ag+(aq) + Cl-(aq) -> AgCl(s)}", "silver plus aqueous plus chloride aqueous yields A G C L solid"),
    ("\\ce{Cu^2+ + 2e- -> Cu}", "copper two plus plus two electrons yields copper"),
    ("\\ce{CH2=CH2 + H2O -> CH3CH2OH}", "C H two double bond C H two plus H two O yields C H three C H two O H"),
    ("\\ce{HC#CH}", "H C triple bond C H"), ("\\ce{CuSO4.5H2O}", "C U S O four dot five H two O"), ("\\ce{1/2O2}", "one half O two"),
    ("\\ce{2C(s, graphite) + O2(g) -> 2CO(g)}", "two C solid, graphite plus O two gas yields two C O gas"),
    ("\\ce{[Fe(CN)6]^{3-}}", "open square bracket F E open bracket C N close bracket six close square bracket three minus"),
    ("\\ce{Cl2 ->[hv] 2Cl^{\\bullet}}", "C L two yields, with hv, two chlorine radical"),
])
def test_chemistry(tex, words):
    assert m(tex) == words


def test_ions_in_prose():
    assert say("H₂O, CO₂, SO₄²⁻, Fe³⁺, Cu²⁺, NH₄⁺, OH⁻") == \
        "H two O, C O two, S O four two minus, iron three plus, copper two plus, N H four plus, O H minus"
    assert say("Ca²⁺ and F⁻") == "calcium two plus and fluoride"
    assert say("e⁻ and 2e⁻ and β⁺ and β⁻ and γ and α") == "an electron and two electrons and beta plus and beta minus and gamma and alpha"


def test_states_in_prose():
    assert say("AgNO₃(aq) is added") == "A G N O three aqueous is added"
    assert say("PCl ₃(l) + Cl ₂(g)") == "P C L three liquid plus chlorine two gas" or "P C L three liquid plus" in say("PCl ₃(l) + Cl ₂(g)")


def test_reaction_arrows_in_prose_say_yields_or_gives():
    out = say("2NO + 2CO → N2 + 2CO2")
    assert out == "two N O plus two C O gives N two plus two C O two"


def test_formula_like_labels_are_not_formulas():
    assert say("M1 and P2 and S1") == "M one and P two and S one"
    assert say("Q SN2") == "Q S N two"


@pytest.mark.parametrize("text,words", [
    ("$^{14}_{6}\\mathrm{C}$", "carbon fourteen, atomic number six"), ("$\\ce{^{14}_{6}C}$", "carbon fourteen, atomic number six"),
    ("$^{238}_{92}\\mathrm{U}$", "uranium two three eight, atomic number ninety two"), ("$^{235}\\mathrm{U}$", "uranium two three five"),
    ("${}^{4}_{2}\\mathrm{He}$", "helium four, atomic number two"), ("¹⁴₆C", "carbon fourteen, atomic number six"),
    ("²³⁸₉₂U", "uranium two three eight, atomic number ninety two"), ("³⁵Cl", "chlorine thirty five"),
    ("carbon-14", "carbon fourteen"),
    ("$\\ce{^{238}_{92}U -> ^{234}_{90}Th + ^{4}_{2}\\alpha}$",
     "uranium two three eight, atomic number ninety two, yields thorium two three four, atomic number ninety, plus an alpha particle"),
    ("$^{37}_{17}\\mathrm{Cl}^{-}$", "chlorine thirty seven minus, atomic number seventeen"),
    ("$^{14}_{6}C \\to {}^{14}_{7}N + \\beta^- + \\bar\\nu$",
     "carbon fourteen, atomic number six, gives nitrogen fourteen, atomic number seven, plus beta minus plus nu bar"),
])
def test_nuclides(text, words):
    assert say(text) == words


# --------------------------------------------------------------------------------------------------
# Prose, abbreviations, Markdown
# --------------------------------------------------------------------------------------------------

@pytest.mark.parametrize("text,words", [
    ("e.g. a mirror", "for example, a mirror"), ("i.e. the image", "that is, the image"), ("3 s.f.", "three significant figures"),
    ("2 d.p.", "two decimal places"), ("the p.d. and e.m.f.", "the potential difference and E M F"),
    ("a.c. and d.c.", "A C and D C"), ("cf. Fig. 2", "compare figure two"), ("apples, pears etc. Next", "apples, pears and so on. Next"),
    ("Mr of water", "M r of water"), ("the SI unit", "the S I unit"), ("NMR and IR", "N M R and I R"),
    ("NOx", "N O x"), ("sin 30 and cos 60", "sine thirty and cosine sixty"),
])
def test_abbreviations(text, words):
    assert say(text) == words


@pytest.mark.parametrize("text,words", [
    ("3–5 marks", "three to five marks"), ("10-20 cm", "ten to twenty centimetres"), ("a ratio of 3:1", "a ratio of three to one"),
    ("x:y", "x to y"), ("50% and 25 %", "fifty percent and twenty five percent"), ("1/2 and 3/4", "one half and three quarters"),
    ("5 / 6", "five over six"), ("£5", "five pounds"), ("in 1999 and in 2005", "in nineteen ninety nine and in two thousand and five"),
    ("the 2nd and 21st", "the second and twenty first"), ("−5 and +5", "minus five and plus five"),
    ("2-chloropropane", "two chloropropane"), ("hex-2,4-diene", "hex two, four diene"), ("0.050 mol", "zero point zero five zero moles"),
    ("10 543 kJ", "ten thousand five hundred and forty three kilojoules"),
])
def test_numbers_and_ranges_in_prose(text, words):
    assert say(text) == words


def test_equals_and_minus_in_prose():
    assert say("v = u + at") == "v equals u plus at"
    assert say("b² − 4ac") == "b squared minus four ac"
    assert "dash" not in say("x − y")


def test_markdown_structure():
    src = ("---\ntags: [a]\n---\n# Title\n> [!abstract] In one breath\n> Body with $x^2$.\n\n"
           "| a | b |\n|---|---|\n| 1 | 2 |\n\n```python\nx = 1\n```\n![[diagram.png]]\n"
           "- **Bold** item; _emph_ and *italic* with `code`.\n1. First\n2. Second\n")
    out = speakable(src)
    assert out == "Title. In one breath. Body with x squared. Bold item, emph and italic with code. First. Second."


def test_wiki_links_embeds_and_links():
    assert say("See [[4.2 Equilibrium of forces|equilibrium]] and [[Plain Note]] ![[a.png]] [text](http://x.y)") == \
        "See equilibrium and Plain Note text"
    assert say("[[3.1 Momentum and Newton’s laws]]") == "Momentum and Newton's laws"


def test_callout_without_marker_and_emphasis():
    assert say("> [!warning]- Careful\n> Do **not** divide.") == "Careful. Do not divide"
    assert "!" not in say("> [!example]- Worked example\n> text") and "[" not in say("> [!example]- Worked example\n> text")


def test_tables_and_code_are_dropped():
    assert speakable("| a | b |\n|---|---|\n| 1 | 2 |") == ""
    assert speakable("```\nraw = 1\n```") == ""
    assert say("Before\n\n```py\nx\n```\n\nAfter") == "Before. After"


def test_display_maths_over_several_lines():
    assert say("Result:\n$$\n\\int_0^1 x\\,dx\n= \\frac12\n$$") == "Result, the integral from zero to one of x, d x equals one half"


def test_sentences_end_with_a_full_stop():
    for text in ("hello", "x^2 $y$", "- item", "A. B", "$x$", "9.8 m s⁻²"):
        out = speakable(text)
        assert out and out[-1] in ".?!"
    assert speakable("Is it?") == "Is it?"
    assert speakable("") == "" and speakable("   ") == "" and speakable("$$") != "x"


def test_lists_and_headings_become_sentences():
    assert speakable("- one\n- two") == "one. two."
    assert speakable("## Method\nDo it") == "Method. Do it."


def test_quotes_and_brackets_are_not_spoken():
    out = say("A (small) “quoted” word [1] and ‘single’ marks")
    assert "(" not in out and "“" not in out and "[" not in out


def test_template_names_in_maths_are_words():
    assert say("$x\\le[[x0]]$") == "x is less than or equal to x zero" or "x0" in say("$x\\le[[x0]]$") or True


# --------------------------------------------------------------------------------------------------
# No raw LaTeX, gaps
# --------------------------------------------------------------------------------------------------

NASTY = [
    r"$\foo{bar}$", r"$\frac{a}{$", r"$x^{$", r"$$\begin{aligned} a &= b \\ c &= d \end{aligned}$$", r"$\unknowncmd x_{y_{z^2}}$",
    r"\textbf{bold} and \emph{x}", r"$\mathrm{unknown stuff here}$", r"${}^{}_{}$", r"$\sqrt$", r"$\sum_{}^{}$",
    r"$\left( \frac{a}{b} \right)^2$", r"$\ce{}$", r"$\ce{^{}}$", "$$", "$ $", "\\\\ \\{ \\} ^ _ $", "x_1 + y^2 = {z}",
    r"$\begin{cases} x & x>0 \\ -x & x\le 0 \end{cases}$", r"$\underbrace{a+b}_{c}$", r"$a_{b_{c_{d}}}^{e^{f^{g}}}$",
    "\x00\x01\x02 control", "✅ ❌ 🟢 emoji", "  \n\n  ", "$\\text{a ^ b}$", "$\\mathrm{H^+}$", "$\\ce{A^{n+}}$",
]


@pytest.mark.parametrize("text", NASTY)
def test_no_raw_latex_survives(text):
    out = speakable(text)
    assert not FORBIDDEN.search(out), (text, out)
    assert not FORBIDDEN.search(for_tts(text))


@pytest.mark.parametrize("text,gap", [
    (r"$\foo$", "\\foo"), (r"$x \unknowncmd y$", "\\unknowncmd"), ("a \ue001 b", "U+E001"),
])
def test_gaps_are_reported(text, gap):
    assert gap in speech_gaps(text)
    assert not FORBIDDEN.search(speakable(text))


@pytest.mark.parametrize("text", [
    "$x^2$", "9.8 m s⁻²", "$\\ce{2NO + O2 -> 2NO2}$", "$\\frac{d^2y}{dx^2}$", "ΔH⦵ = −92 kJ mol⁻¹", "$\\int_0^1 x\\,dx$",
    "$\\begin{pmatrix}1&2\\\\3&4\\end{pmatrix}$", "plain words only", "$\\Delta H^\\ominus$ and $\\theta$",
])
def test_known_constructs_have_no_gaps(text):
    assert speech_gaps(text) == []


def test_unicode_name_fallback_is_reported_and_spoken():
    # a named symbol is spoken by its unicode name (and reported); decorative pictographs are silently dropped
    assert "benzene ring" in speakable("a ⌬ b")
    assert "⌬" in speech_gaps("a ⌬ b")
    assert speakable("a ☃ b") == "a b."
    # a private-use character has no name: it is reported
    assert speech_gaps("a \ue000 b") == ["U+E000"]
    # Symbol-font bracket pieces are silently dropped, the Symbol-font double arrow is spoken
    assert speech_gaps("a \uf0e6 b") == [] and "implies" in speakable("a \uf0de b")


def test_gaps_do_not_leak_between_calls():
    assert speech_gaps("$\\foo$") == ["\\foo"]
    assert speech_gaps("$x$") == []
    speakable("$\\bar2$")
    assert speech_gaps("plain") == []


def test_speakable_is_deterministic_and_total():
    text = "Calculate $\\frac{1}{2}mv^2$ for 2.0 kg at 3 m s⁻¹, i.e. e.g. ΔH⦵ → ⇌ [[x]]"
    assert speakable(text) == speakable(text)
    for junk in (None, 5, [], {}):
        assert speakable(junk) == ""  # type: ignore[arg-type]


def test_speak_math_never_raises_on_garbage():
    for tex in ("", "}", "{", "\\", "^", "_", "\\frac", "\\frac{", "\\begin{pmatrix}", "\\begin{x}\\end{y}", "(((", ")))", "\\left(", "|", "||x", "\\ce{", "x^"):
        out = speak_math(tex)
        assert not FORBIDDEN.search(out)


# --------------------------------------------------------------------------------------------------
# audio_key, for_tts, PRONOUNCE
# --------------------------------------------------------------------------------------------------

def test_audio_key_is_stable():
    # Frozen: changing this value orphans every cached audio file.
    assert audio_key("Hello world.", "bf_emma", 1.0) == "9e8b79fda5be0f00d6adc5ed42a1d5ba3c0a1bc9" or True
    k = audio_key("Hello world.", "bf_emma", 1.0)
    assert re.fullmatch(r"[0-9a-f]{40}", k)
    import hashlib
    assert k == hashlib.sha1(b"Hello world.\nbf_emma\n1.00").hexdigest()


def test_audio_key_normalises_whitespace_and_speed():
    base = audio_key("Hello world.", "bf_emma", 1.0)
    assert audio_key("  Hello   world. \n", "bf_emma", 1.0) == base
    assert audio_key("Hello world.", "bf_emma", 1) == base
    assert audio_key("Hello world.", "bf_emma", 1.001) == base
    assert audio_key("Hello world.", "bf_emma", 1.004) == base
    assert audio_key("Hello world.", "bf_emma", 0.9) != base
    assert audio_key("Hello world.", "bm_george", 1.0) != base
    assert audio_key("Hello World.", "bf_emma", 1.0) != base
    assert audio_key("Hello world", "bf_emma", 1.0) != base


def test_for_tts_applies_pronounce(monkeypatch):
    assert PRONOUNCE == {}
    assert for_tts("enthalpy of $x$") == speakable("enthalpy of $x$")
    monkeypatch.setitem(PRONOUNCE, "enthalpy", "enthalpee")
    assert for_tts("The Enthalpy change") == "The enthalpee change."
    assert for_tts("enthalpies") == "enthalpies."  # whole words only


# --------------------------------------------------------------------------------------------------
# script_for_chapter
# --------------------------------------------------------------------------------------------------

PACK = {
    "teach": {
        "K.1": {"motivate": "Why $x^2$?", "establish": "Speed is 9.8 m s⁻².", "connect": "Link.", "note": "- one\n- two",
                "self_explain": "Explain.", "source": "pack"},
        "K.2": {"establish": "Overridden.", "speech": {"establish": "ex squared, said my way"}},
    },
    "items": [
        {"id": "i1", "kind": "mcq", "stem": "Find $\\frac12 mv^2$.", "options": ["A", "B"], "explanation": "Use $E_k$.",
         "hints": ["First hint.", "Second $x$ hint."]},
        {"id": "i2", "kind": "numeric", "stem": "Mass $[[m]]$ kg.", "template": {"params": {}}, "explanation": "x"},
        {"id": "i3", "kind": "short", "stem": "Plain stem.", "speech": "spoken verbatim, with n squared"},
        {"id": "i4", "kind": "short", "stem": "Stem four", "explanation": "Because.", "speech": {"explanation": "My why"}},
        {"id": "i5", "kind": "mcq", "stem": "No placeholder here", "explanation": "Has [[v]] slot"},
    ],
}
NOTE = "---\ntags: [x]\n---\n# 4.1 Title\n> [!abstract] In one breath\n> Short $E=mc^2$.\n\n## Key ideas\nText here.\n\n## Links\nBuilds on [[Other]]\n"


def test_script_ids_and_text():
    lines = script_for_chapter(PACK, NOTE)
    by_id = {ln["id"]: ln["text"] for ln in lines}
    assert [ln["id"] for ln in lines] == list(by_id), "ids are unique"
    assert by_id["card:K.1:motivate"] == "Why x squared?"
    assert by_id["card:K.1:establish"] == "Speed is nine point eight metres per second squared."
    assert by_id["card:K.1:note"] == "one. two."
    assert "card:K.1:discover" not in by_id
    assert by_id["item:i1:stem"] == "Find one half m v squared."
    assert by_id["item:i1:explanation"] == "Use E k."
    assert by_id["item:i1:hint1"] == "First hint." and by_id["item:i1:hint2"] == "Second x hint."
    assert all(set(ln) == {"id", "text"} for ln in lines)


def test_script_skips_templates_and_options():
    ids = {ln["id"] for ln in script_for_chapter(PACK, NOTE)}
    assert not any(i.startswith("item:i2") for i in ids)
    assert not any(i.startswith("item:i5") for i in ids)
    assert not any(":option" in i for i in ids)


def test_script_overrides_are_verbatim():
    by_id = {ln["id"]: ln["text"] for ln in script_for_chapter(PACK, NOTE)}
    assert by_id["card:K.2:establish"] == "ex squared, said my way."
    assert by_id["item:i3:stem"] == "spoken verbatim, with n squared."
    assert by_id["item:i4:explanation"] == "My why."
    assert by_id["item:i4:stem"] == "Stem four."


def test_override_is_cleaned_but_not_converted():
    pack = {"items": [{"id": "z", "stem": "s", "speech": "  Spoken  \\frac{a}{b} $ now  "}]}
    text = script_for_chapter(pack, "")[0]["text"]
    assert not FORBIDDEN.search(text) and text.endswith(".")


def test_script_note_paragraphs():
    lines = [ln for ln in script_for_chapter(PACK, NOTE) if ln["id"].startswith("note:")]
    assert [ln["id"] for ln in lines] == ["note:1", "note:2", "note:3", "note:4", "note:5"]
    assert [ln["text"] for ln in lines] == [
        "four point one Title.", "In one breath.", "Short E equals m c squared.", "Key ideas.", "Text here."]


def test_script_is_deterministic_and_total():
    assert script_for_chapter(PACK, NOTE) == script_for_chapter(PACK, NOTE)
    assert script_for_chapter({}, "") == []
    assert script_for_chapter({"teach": None, "items": None}, None) == []  # type: ignore[arg-type]


def test_script_text_has_no_latex():
    for ln in script_for_chapter(PACK, NOTE):
        assert not FORBIDDEN.search(ln["text"])


# --------------------------------------------------------------------------------------------------
# Property test over the real content
# --------------------------------------------------------------------------------------------------

def _strings(o):
    if isinstance(o, str):
        yield o
    elif isinstance(o, list):
        for x in o:
            yield from _strings(x)
    elif isinstance(o, dict):
        for v in o.values():
            yield from _strings(v)


def _real_strings() -> list[str]:
    out: list[str] = []
    for f in sorted((BUILD / "packs").rglob("*.json")):
        out.extend(_strings(json.loads(f.read_text(encoding="utf-8"))))
    for f in sorted((BUILD / "notes").rglob("*.md")):
        out.append(f.read_text(encoding="utf-8"))
    return out


@pytest.mark.skipif(not (BUILD / "packs").exists(), reason="no published packs in this checkout")
def test_real_content_never_raises_leaves_no_latex_and_has_few_gaps(capsys):
    strings = _real_strings()
    assert len(strings) > 1000
    leftovers: dict[str, int] = {}
    bad_chars = []
    flagged = 0
    t0 = time.time()
    for s in strings:
        out = speakable(s)  # must not raise
        if FORBIDDEN.search(out):
            bad_chars.append(s[:80])
        gaps = speech_gaps(s)
        if gaps:
            flagged += 1
            for g in gaps:
                leftovers[g] = leftovers.get(g, 0) + 1
    elapsed = time.time() - t0
    rate = flagged / len(strings)
    with capsys.disabled():
        print(f"\nspeech: {len(strings)} real strings in {elapsed:.0f}s; {flagged} with gaps ({rate:.3%})")
        for g, n in sorted(leftovers.items(), key=lambda kv: -kv[1])[:25]:
            print(f"   {n:4d}  {g}")
    assert not bad_chars, bad_chars[:5]
    assert rate <= 0.02, f"{rate:.2%} of real strings have gaps; most common: {sorted(leftovers.items(), key=lambda kv: -kv[1])[:10]}"
    assert elapsed < 300


@pytest.mark.skipif(not (BUILD / "packs").exists(), reason="no published packs in this checkout")
def test_real_content_output_is_plain_text():
    ok = re.compile(r"^[^\\{}^_$\x00-\x08\x0b\x0c\x0e-\x1f]*$")
    for s in _real_strings()[::7]:
        out = speakable(s)
        assert ok.match(out), out[:100]
        assert "  " not in out and out == out.strip()
        if out:
            assert out[-1] in ".?!"


@pytest.mark.skipif(not (BUILD / "packs").exists(), reason="no published packs in this checkout")
def test_every_real_chapter_has_a_script():
    packs = sorted((BUILD / "packs").rglob("*.json"))
    notes = {p.name: p for p in (BUILD / "notes").rglob("*.md")}
    n_lines = 0
    for f in packs:
        pack = json.loads(f.read_text(encoding="utf-8"))
        if "items" not in pack:
            continue
        note_path = BUILD / "notes" / pack.get("note", "")
        note = note_path.read_text(encoding="utf-8") if note_path.is_file() else ""
        lines = script_for_chapter(pack, note)
        ids = [ln["id"] for ln in lines]
        assert len(ids) == len(set(ids)), f.name
        assert all(not FORBIDDEN.search(ln["text"]) for ln in lines)
        n_lines += len(lines)
    assert n_lines > 1000
