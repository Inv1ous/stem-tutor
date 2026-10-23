"""Chapter text -> plain spoken British English, for local text-to-speech (Kokoro).

Kokoro reads plain words well and garbles maths, so everything that is spoken is first turned into
words here.  Everything in this module is a pure function: no I/O, no AI, no clock, no randomness.
The same text always gives the same words, and the words give the same audio-cache key.

Public surface
--------------
speakable(text)             Markdown-ish chapter text (prose, ``$..$`` / ``$$..$$`` maths, ``\\ce{}``,
                            unicode maths, units, lists, callouts, wiki links) -> the spoken form.
                            The result never holds a backslash, brace, caret, underscore or dollar
                            sign, and a non-empty result always ends with a full stop (or ? or !).
speech_gaps(text)           The symbols / commands that had no natural spoken form (the output used a
                            fallback for them).  A content gate requires this to be empty, or the item
                            to carry a ``speech`` override.
for_tts(text)               speakable(text) followed by the PRONOUNCE word list.  This is what is sent
                            to the synthesiser.
audio_key(text, voice, speed)   The audio cache key (see its docstring); shared by the app and the
                            foundry / refine pre-generator.
script_for_chapter(pack, note_text)   The chapter's speakable lines for pre-generation.
speak_math(tex)             Just the maths -> words part (no ``$`` delimiters), for tests and tools.
note_paragraphs(note_text)  The raw paragraphs of a note that script_for_chapter speaks.

Style
-----
British spoken style: "x squared", "x cubed", "x to the n", "ten to the minus three", "to the power
of ..." only for exponents that are not a plain integer / one or two symbols; "metres", "litres",
"per" for unit denominators, "square metre" / "cubic decimetre" for a lone area / volume unit.
Single variables are spoken as the bare letter ("x", "E k"); chemical formulas are spelled letter by
letter with a capital for every letter ("C U S O four") so that "Co" and "CO" are not confused with a
lower-case letter the synthesiser might read as a word.

Known limits (documented, not hidden)
-------------------------------------
* Which words Kokoro mispronounces is not verified here, so PRONOUNCE is empty.
* A lone lower-case "a" (the variable) is spoken as "a" and a synthesiser may read it as the article.
* Tables are dropped; code blocks are dropped; embeds and images are dropped.
"""
from __future__ import annotations

import functools
import hashlib
import re
import threading
import unicodedata

__all__ = [
    "speakable", "speech_gaps", "for_tts", "audio_key", "script_for_chapter", "speak_math",
    "note_paragraphs", "PRONOUNCE",
]

# --------------------------------------------------------------------------------------------------
# Pronunciation hook
# --------------------------------------------------------------------------------------------------

#: Words the synthesiser mispronounces: {"word as spoken by speakable()": "respelling Kokoro reads right"}.
#: Matching is whole-word and case-insensitive.  Deliberately empty: add an entry only when a word is
#: *known* to be read wrongly (listen to it first).  for_tts() applies it after speakable().
PRONOUNCE: dict[str, str] = {}

# --------------------------------------------------------------------------------------------------
# Gap collection (thread-local so concurrent callers do not mix their reports)
# --------------------------------------------------------------------------------------------------

_TLS = threading.local()


def _gap(what: str) -> None:
    g = getattr(_TLS, "gaps", None)
    if g is not None:
        g.append(what)


# --------------------------------------------------------------------------------------------------
# Numbers
# --------------------------------------------------------------------------------------------------

_ONES = ("zero one two three four five six seven eight nine ten eleven twelve thirteen fourteen fifteen "
         "sixteen seventeen eighteen nineteen").split()
_TENS = "_ _ twenty thirty forty fifty sixty seventy eighty ninety".split()
_SCALES = ((10 ** 12, "trillion"), (10 ** 9, "billion"), (10 ** 6, "million"), (1000, "thousand"))
_ORD = {1: "first", 2: "second", 3: "third", 4: "fourth", 5: "fifth", 6: "sixth", 7: "seventh", 8: "eighth",
        9: "ninth", 10: "tenth", 11: "eleventh", 12: "twelfth"}
_FRAC_DEN = {2: ("half", "halves"), 3: ("third", "thirds"), 4: ("quarter", "quarters"), 5: ("fifth", "fifths"),
             6: ("sixth", "sixths"), 7: ("seventh", "sevenths"), 8: ("eighth", "eighths"),
             9: ("ninth", "ninths"), 10: ("tenth", "tenths")}


def int_words(n: int) -> str:
    """A whole number in British words: 123 -> 'one hundred and twenty three'."""
    if n < 0:
        return "minus " + int_words(-n)
    if n < 20:
        return _ONES[n]
    if n < 100:
        t, o = divmod(n, 10)
        return _TENS[t] + (" " + _ONES[o] if o else "")
    if n < 1000:
        h, r = divmod(n, 100)
        return _ONES[h] + " hundred" + (" and " + int_words(r) if r else "")
    for v, name in _SCALES:
        if n >= v:
            q, r = divmod(n, v)
            return int_words(q) + " " + name + ((" and " if r < 100 else " ") + int_words(r) if r else "")
    return str(n)  # pragma: no cover


def _digits(s: str) -> str:
    return " ".join(_ONES[int(c)] for c in s if c.isdigit())


def number_words(s: str) -> str:
    """'9.8' -> 'nine point eight'; '3.0' -> 'three point zero'; '1,000' -> 'one thousand'."""
    s = s.replace(",", "").replace(" ", "").replace(" ", "").replace(" ", "")
    if "." in s:
        head, _, tail = s.partition(".")
        if "." in tail:  # 11.1.1 (a section number): read every part
            return " point ".join(number_words(p or "0") for p in s.split("."))
        return (number_words(head) if head else "zero") + " point " + _digits(tail)
    if not s.isdigit():
        return s
    if len(s) > 1 and s[0] == "0":
        return _digits(s)
    if len(s) > 15:
        return _digits(s)
    return int_words(int(s))


def year_words(n: int) -> str:
    """1999 -> 'nineteen ninety nine', 2005 -> 'two thousand and five', 1905 -> 'nineteen oh five'."""
    if 2000 <= n <= 2009:
        return int_words(n)
    a, b = divmod(n, 100)
    if b == 0:
        return int_words(a) + " hundred"
    return int_words(a) + " " + ("oh " + _ONES[b] if b < 10 else int_words(b))


def _is_one(s: str) -> bool:
    return s.strip().lstrip("+") == "1"


def fraction_words(a: int, b: int) -> str | None:
    """3/4 -> 'three quarters'; 1/2 -> 'one half'.  None when it should be read 'a over b'."""
    if b in _FRAC_DEN and 0 < a < b + 1 and a <= 20:
        sing, plur = _FRAC_DEN[b]
        return f"{int_words(a)} {sing if a == 1 else plur}"
    return None


# --------------------------------------------------------------------------------------------------
# Chemical elements
# --------------------------------------------------------------------------------------------------

_EL_TEXT = (
    "H hydrogen He helium Li lithium Be beryllium B boron C carbon N nitrogen O oxygen F fluorine Ne neon "
    "Na sodium Mg magnesium Al aluminium Si silicon P phosphorus S sulfur Cl chlorine Ar argon K potassium "
    "Ca calcium Sc scandium Ti titanium V vanadium Cr chromium Mn manganese Fe iron Co cobalt Ni nickel "
    "Cu copper Zn zinc Ga gallium Ge germanium As arsenic Se selenium Br bromine Kr krypton Rb rubidium "
    "Sr strontium Y yttrium Zr zirconium Nb niobium Mo molybdenum Tc technetium Ru ruthenium Rh rhodium "
    "Pd palladium Ag silver Cd cadmium In indium Sn tin Sb antimony Te tellurium I iodine Xe xenon "
    "Cs caesium Ba barium La lanthanum Ce cerium Pr praseodymium Nd neodymium Pm promethium Sm samarium "
    "Eu europium Gd gadolinium Tb terbium Dy dysprosium Ho holmium Er erbium Tm thulium Yb ytterbium "
    "Lu lutetium Hf hafnium Ta tantalum W tungsten Re rhenium Os osmium Ir iridium Pt platinum Au gold "
    "Hg mercury Tl thallium Pb lead Bi bismuth Po polonium At astatine Rn radon Fr francium Ra radium "
    "Ac actinium Th thorium Pa protactinium U uranium Np neptunium Pu plutonium Am americium Cm curium "
    "Bk berkelium Cf californium Es einsteinium Fm fermium Md mendelevium No nobelium Lr lawrencium "
    "Rf rutherfordium Db dubnium Sg seaborgium Bh bohrium Hs hassium Mt meitnerium Ds darmstadtium "
    "Rg roentgenium Cn copernicium Nh nihonium Fl flerovium Mc moscovium Lv livermorium Ts tennessine "
    "Og oganesson").split()
ELEMENT_NAME = {_EL_TEXT[i]: _EL_TEXT[i + 1] for i in range(0, len(_EL_TEXT), 2)}
ATOMIC_NUMBER = {sym: i + 1 for i, sym in enumerate(_EL_TEXT[0::2])}
# anions named as -ide when they stand alone with a minus charge
_ANION = {"F": "fluoride", "Cl": "chloride", "Br": "bromide", "I": "iodide", "O": "oxide", "S": "sulfide",
          "N": "nitride", "H": "hydride", "P": "phosphide"}

# --------------------------------------------------------------------------------------------------
# Greek and symbols
# --------------------------------------------------------------------------------------------------


def _greek_table() -> dict[str, str]:
    out: dict[str, str] = {}
    for cp in list(range(0x391, 0x3AA)) + list(range(0x3B1, 0x3CA)):
        ch = chr(cp)
        name = unicodedata.name(ch, "")
        if "LETTER" not in name:
            continue
        word = name.split("LETTER ", 1)[1].lower().replace("lamda", "lambda").replace("final sigma", "sigma")
        out[ch] = word
    out["ϑ"], out["ϕ"], out["ϵ"], out["ϖ"], out["ϱ"], out["ς"] = "theta", "phi", "epsilon", "pi", "rho", "sigma"
    out["µ"] = "mu"  # micro sign
    out["Ω"] = "omega"  # ohm sign
    return out


GREEK_CHAR = _greek_table()
_GREEK_CMD = {
    "alpha", "beta", "gamma", "delta", "epsilon", "zeta", "eta", "theta", "iota", "kappa", "lambda", "mu", "nu",
    "xi", "omicron", "pi", "rho", "sigma", "tau", "upsilon", "phi", "chi", "psi", "omega",
}
_GREEK_NAME = {
    **{c: c for c in _GREEK_CMD},
    **{c.capitalize(): c for c in _GREEK_CMD}, "varepsilon": "epsilon", "vartheta": "theta", "varphi": "phi",
    "varpi": "pi", "varrho": "rho", "varsigma": "sigma", "varkappa": "kappa",
}

_REL = {  # relations and operators: LaTeX command / unicode char -> words
    "=": "equals", "<": "is less than", ">": "is greater than", "≠": "is not equal to", "≤": "is less than or equal to",
    "≥": "is greater than or equal to", "≈": "is approximately", "≡": "is identical to", "∝": "is proportional to",
    "≪": "is much less than", "≫": "is much greater than", "≃": "is approximately", "≅": "is congruent to",
    "∼": "is approximately", "∈": "is in", "∉": "is not in", "⊂": "is a subset of", "⊆": "is a subset of",
    "⊥": "is perpendicular to", "∥": "is parallel to", "⇒": "implies", "⇔": "if and only if", "⟹": "implies",
    "⟺": "if and only if", "⇐": "is implied by", "∴": "therefore", "∵": "because",
}
_CMD_REL = {
    "ne": "≠", "neq": "≠", "le": "≤", "leq": "≤", "leqslant": "≤", "ge": "≥", "geq": "≥", "geqslant": "≥",
    "approx": "≈", "equiv": "≡", "propto": "∝", "ll": "≪", "gg": "≫", "simeq": "≃", "cong": "≅",
    "in": "∈", "notin": "∉", "subset": "⊂", "subseteq": "⊆", "perp": "⊥", "parallel": "∥",
    "Rightarrow": "⇒", "Leftrightarrow": "⇔", "iff": "⇔", "implies": "⟹", "Longrightarrow": "⇒",
    "Longleftrightarrow": "⇔", "Leftarrow": "⇐", "therefore": "∴", "because": "∵", "lt": "<", "gt": ">",
}
_CMD_WORDS = {  # other commands with a fixed reading
    "times": "times", "div": "divided by", "pm": "plus or minus", "mp": "minus or plus", "ast": "times",
    "star": "star", "infty": "infinity", "partial": "partial", "nabla": "nabla", "cap": "intersection",
    "cup": "union", "emptyset": "the empty set", "varnothing": "the empty set", "forall": "for all",
    "exists": "there exists", "neg": "not", "lnot": "not", "land": "and", "lor": "or", "wedge": "and",
    "vee": "or", "angle": "angle", "ldots": "and so on", "cdots": "and so on", "dots": "and so on",
    "vdots": "and so on", "ddots": "and so on", "dotsc": "and so on", "dotsb": "and so on",
    "prime": "prime", "degree": "degrees", "hbar": "h bar", "ell": "l", "aleph": "aleph", "oplus": "circle plus",
    "otimes": "circle times", "dagger": "dagger", "ddagger": "double dagger", "bullet": "dot",
    "top": "top", "mathrm": "", "Re": "the real part of", "Im": "the imaginary part of", "wp": "p",
    "langle": "open angle bracket", "rangle": "close angle bracket", "lceil": "ceiling", "rceil": "end ceiling",
    "lfloor": "floor", "rfloor": "end floor", "setminus": "minus", "smallsetminus": "minus", "triangle": "triangle",
    "square": "square", "Box": "square", "checkmark": "tick", "surd": "the square root of",
    "to": "to", "rightarrow": "gives", "longrightarrow": "yields", "leftarrow": "comes from",
    "longleftarrow": "comes from", "leftrightarrow": "goes both ways", "longleftrightarrow": "goes both ways",
    "rightleftharpoons": "is in equilibrium with", "leftrightharpoons": "is in equilibrium with",
    "uparrow": "up", "downarrow": "down", "mapsto": "maps to", "gets": "comes from", "vert": "bar",
    "lvert": "bar", "rvert": "bar", "Vert": "double bar", "lVert": "double bar", "rVert": "double bar",
    "mid": "given", "colon": "colon", "AA": "angstrom", "ohm": "ohms", "perthousand": "per mille",
    "textperthousand": "per mille", "textdegree": "degrees", "imath": "i", "jmath": "j", "ominus": "standard",
    "circ": "degrees", "varDelta": "delta", "gtrless": "is greater or less than", "lessgtr": "is less or greater than", "oint": "the contour integral of",
}
_CMD_WORDS.update({k: v for k, v in {  # symbols a chapter may use that have a plain reading (anything else is a reported gap)
    "backslash": "backslash", "circlearrowright": "clockwise", "circlearrowleft": "anticlockwise",
    "curvearrowright": "curving right", "curvearrowleft": "curving left", "circlearrowleft_": "anticlockwise",
    "Rightarrow": "implies", "Leftarrow": "is implied by", "Leftrightarrow": "if and only if", "implies": "implies",
    "iff": "if and only if", "impliedby": "is implied by", "nearrow": "up and to the right", "searrow": "down and to the right",
    "nwarrow": "up and to the left", "swarrow": "down and to the left", "Uparrow": "up", "Downarrow": "down",
    "updownarrow": "up and down", "hookrightarrow": "gives", "twoheadrightarrow": "gives", "rightharpoonup": "harpoon right",
    "leftharpoonup": "harpoon left", "uparrow_": "up", "therefore": "therefore", "because": "because",
    "propto": "is proportional to", "sim": "is about", "simeq": "is about equal to", "cong": "is congruent to",
    "approx": "is approximately", "equiv": "is equivalent to", "doteq": "is equal to", "neq": "is not equal to",
    "ne": "is not equal to", "ll": "is much less than", "gg": "is much greater than", "parallel": "is parallel to",
    "perp": "is perpendicular to", "in": "in", "notin": "not in", "subset": "is a subset of", "subseteq": "is a subset of",
    "supset": "is a superset of", "supseteq": "is a superset of", "sqcup": "union", "sqcap": "intersection",
    "bigcirc": "circle", "circledast": "circle star", "odot": "circle dot", "cdot": "times", "centerdot": "dot",
    "diamond": "diamond", "lozenge": "diamond", "blacksquare": "square", "blacktriangle": "triangle",
    "bigstar": "star", "spadesuit": "spade", "heartsuit": "heart", "dag": "dagger", "ddag": "double dagger",
    "S": "section", "P": "paragraph", "copyright": "copyright", "pounds": "pounds", "euro": "euros", "mho": "mhos",
    "wr": "wreath", "amalg": "coproduct", "lbrace": "open brace", "rbrace": "close brace", "lbrack": "open bracket",
    "rbrack": "close bracket", "backslash_": "backslash", "natural": "natural", "flat": "flat", "sharp": "sharp",
    "male": "male", "female": "female", "sun": "the sun", "earth": "the earth", "oplus_": "circle plus",
    "overset": "", "underset": "", "stackrel": "", "phantom": "", "hphantom": "", "vphantom": "", "mathstrut": "",
}.items() if k not in _CMD_WORDS})
_UNI_WORDS = {  # single unicode characters in prose (those not already covered by the tables above)
    "±": "plus or minus", "∓": "minus or plus", "×": "times", "÷": "divided by", "√": "the square root of",
    "∛": "the cube root of", "∜": "the fourth root of", "∞": "infinity", "∑": "the sum of", "∏": "the product of",
    "∫": "the integral of", "∮": "the contour integral of", "∂": "partial", "∇": "nabla", "∩": "intersection",
    "∪": "union", "∅": "the empty set", "∀": "for all", "∃": "there exists", "→": "gives", "⟶": "yields",
    "←": "comes from", "↔": "goes both ways", "⇌": "is in equilibrium with", "⇋": "is in equilibrium with",
    "↑": "up", "↓": "down", "⟷": "goes both ways", "°": "degrees", "′": "prime", "″": "double prime",
    "‴": "triple prime", "‰": "per mille", "‱": "per ten thousand", "§": "section", "¶": "paragraph",
    "©": "copyright", "®": "registered", "™": "trademark", "†": "dagger", "‡": "double dagger", "№": "number",
    "ℓ": "l", "ℏ": "h bar", "ℝ": "the real numbers", "ℕ": "the natural numbers", "ℤ": "the integers",
    "ℚ": "the rational numbers", "ℂ": "the complex numbers", "∠": "angle", "△": "triangle", "□": "square",
    "⊖": "standard", "⦵": "standard", "○": "", "●": "", "•": "", "◦": "", "▪": "", "■": "",
    "✓": "tick", "✔": "tick", "✗": "cross", "✘": "cross", "✅": "tick", "❌": "cross", "⏎": "", "⌘": "command",
    "…": ",", "—": ",", "―": ",", "·": ",", "›": ",", "»": ",", "«": ",", "−": "minus", "꞊": "equals",
    "–": ",", "‐": " ", "‑": " ", "£": "pounds", "€": "euros", "¥": "yen", "¢": "cents", "½": "one half",
    "⅓": "one third", "⅔": "two thirds", "¼": "one quarter", "¾": "three quarters", "⅕": "one fifth",
    "⅖": "two fifths", "⅗": "three fifths", "⅘": "four fifths", "⅙": "one sixth", "⅚": "five sixths",
    "⅛": "one eighth", "⅜": "three eighths", "⅝": "five eighths", "⅞": "seven eighths",
    "⟨": "open angle bracket", "⟩": "close angle bracket", "⌈": "ceiling", "⌉": "end ceiling", "⌊": "floor",
    "⌋": "end floor", "∖": "minus", "⊕": "circle plus", "⊗": "circle times", "∘": "composed with",
    "⋅": "times", "∙": "times", "∗": "times", "∣": "such that", "ⁿ": "", "ª": "", "º": "degrees", "¹": "",
    "…": ",",
}
_UNI_WORDS.update({k: v for k, v in _REL.items() if k not in "=<>"})

_SUP_CH = "⁰¹²³⁴⁵⁶⁷⁸⁹⁺⁻⁼⁽⁾ⁿⁱ"
_SUP_AS = "0123456789+-=()ni"
_SUB_CH = "₀₁₂₃₄₅₆₇₈₉₊₋₌₍₎ₐₑₒₓₔₕₖₗₘₙₚₛₜ"
_SUB_AS = "0123456789+-=()aeoxəhklmnpst"
_SUP_MAP = dict(zip(_SUP_CH, _SUP_AS))
_SUB_MAP = dict(zip(_SUB_CH, _SUB_AS))
_SUP_LET = dict(zip("ᵃᵇᶜᵈᵉᶠᵍʰʲᵏˡᵐᵒᵖʳˢᵗᵘᵛʷˣʸᶻ", "abcdefghjklmoprstuvwxyz"))
_SUB_LET = dict(zip("ᵢⱼᵣᵤᵥ", "ijruv"))
_RE_SUPLET = re.compile("[" + _SUP_CH + "".join(_SUP_LET) + "]*[" + "".join(_SUP_LET) + "][" + _SUP_CH + "".join(_SUP_LET) + "]*")
_RE_SUBLET = re.compile("[" + _SUB_CH + "".join(_SUB_LET) + "]*[ₐₑₒₓₔₕₖₗₘₙₚₛₜᵢⱼᵣᵤᵥ][" + _SUB_CH + "".join(_SUB_LET) + "]*")
_RE_SUPRUN = re.compile("[" + _SUP_CH + "]+")
_RE_SUBRUN = re.compile("[" + _SUB_CH + "]+")

# --------------------------------------------------------------------------------------------------
# Units
# --------------------------------------------------------------------------------------------------

# symbol -> (singular, plural, takes an SI prefix)
_UNIT_BASE: dict[str, tuple[str, str, bool]] = {
    "m": ("metre", "metres", True), "g": ("gram", "grams", True), "s": ("second", "seconds", True),
    "A": ("ampere", "amperes", True), "K": ("kelvin", "kelvin", False), "mol": ("mole", "moles", True),
    "cd": ("candela", "candela", False), "N": ("newton", "newtons", True), "J": ("joule", "joules", True),
    "W": ("watt", "watts", True), "Pa": ("pascal", "pascals", True), "C": ("coulomb", "coulombs", True),
    "V": ("volt", "volts", True), "Ω": ("ohm", "ohms", True), "F": ("farad", "farads", True),
    "T": ("tesla", "tesla", True), "Wb": ("weber", "webers", True), "H": ("henry", "henries", True),
    "Hz": ("hertz", "hertz", True), "Bq": ("becquerel", "becquerels", True),
    "eV": ("electronvolt", "electronvolts", True), "L": ("litre", "litres", True), "S": ("siemens", "siemens", True),
    "Gy": ("gray", "grays", True), "Sv": ("sievert", "sieverts", True), "lm": ("lumen", "lumens", False),
    "lx": ("lux", "lux", False), "cal": ("calorie", "calories", True), "bar": ("bar", "bars", True),
    "Wh": ("watt hour", "watt hours", True), "rad": ("radian", "radians", True), "sr": ("steradian", "steradians", False),
    "u": ("atomic mass unit", "atomic mass units", False), "amu": ("atomic mass unit", "atomic mass units", False),
    "Da": ("dalton", "daltons", True),
    "min": ("minute", "minutes", False), "h": ("hour", "hours", False), "atm": ("atmosphere", "atmospheres", False),
    "Å": ("angstrom", "angstroms", False), "M": ("molar", "molar", False), "dB": ("decibel", "decibels", False),
    "ppm": ("part per million", "parts per million", False), "rpm": ("revolution per minute", "revolutions per minute", False),
    "mmHg": ("millimetre of mercury", "millimetres of mercury", False), "kWh": ("kilowatt hour", "kilowatt hours", False),
    "ly": ("light year", "light years", False), "AU": ("astronomical unit", "astronomical units", False),
    "pc": ("parsec", "parsecs", False), "°": ("degree", "degrees", False), "°C": ("degree Celsius", "degrees Celsius", False),
    "°F": ("degree Fahrenheit", "degrees Fahrenheit", False), "%": ("percent", "percent", False),
    "‰": ("per mille", "per mille", False), "torr": ("torr", "torr", False),
}
_PREFIX = {"Y": "yotta", "Z": "zetta", "E": "exa", "P": "peta", "T": "tera", "G": "giga", "M": "mega", "k": "kilo",
           "h": "hecto", "d": "deci", "c": "centi", "m": "milli", "μ": "micro", "µ": "micro", "n": "nano",
           "p": "pico", "f": "femto"}
_PREFIX_ONLY = {"d": {"m", "L", "g"}, "c": {"m", "L", "g"}, "h": {"Pa"}, "T": {"Hz", "eV", "Pa", "J", "W", "m"},
                "P": {"Pa", "J", "W", "m"}, "E": {"J", "eV"}, "Y": {"J"}, "Z": {"J"}}
_TIMEISH = {"s", "min", "h"}  # "per second squared", not "per square second"
_SINGLE_SAFE = {"m", "s", "g", "N", "J", "W", "V", "A", "K", "L", "kg", "Hz", "Pa", "mol"}  # a lone symbol that is a unit
_ONE_LETTER_PLAIN = {"m", "s", "g", "A", "K", "N", "J", "W", "V", "C", "F", "T", "L", "H", "M", "u", "h", "S"}


@functools.lru_cache(maxsize=4096)
def unit_lookup(sym: str) -> tuple[str, str] | None:
    """Spoken (singular, plural) of a unit symbol incl. SI prefixes: 'kJ' -> ('kilojoule', 'kilojoules')."""
    sym = sym.replace("µ", "μ")
    hit = _UNIT_BASE.get(sym)
    if hit:
        return hit[0], hit[1]
    if len(sym) >= 2:
        for plen in (2, 1):
            pre, base = sym[:plen], sym[plen:]
            if pre in _PREFIX and base in _UNIT_BASE and _UNIT_BASE[base][2]:
                allowed = _PREFIX_ONLY.get(pre)
                if allowed is not None and base not in allowed:
                    continue
                if pre == "h" and base != "Pa":
                    continue
                name = _PREFIX[pre]
                return name + _UNIT_BASE[base][0], name + _UNIT_BASE[base][1]
    return None


def _exp_ordinal(e: int) -> str:
    if 4 <= e <= 12:
        return "to the " + _ORD[e]
    return "to the power of " + int_words(e)


def units_words(run: list[tuple[str, int]], plural: bool = True) -> str:
    """A run of (symbol, exponent) -> words.  Negative exponents are denominators ("per").

    [('m',1),('s',-2)] -> 'metres per second squared' (plural=True), 'metre per second squared' (False);
    [('N',1),('m',-2)] -> 'newtons per square metre'; [('m',2)] -> 'square metres'.
    """
    num = [(s, e) for s, e in run if e > 0]
    den = [(s, -e) for s, e in run if e < 0]
    parts: list[str] = []
    for idx, (sym, e) in enumerate(num):
        names = unit_lookup(sym)
        if names is None:
            _gap("unit " + sym)
            parts.append(sym)
            continue
        last = idx == len(num) - 1
        name = names[1] if (plural and last) else names[0]
        if e == 1:
            parts.append(name)
        elif e == 2:
            parts.append(("square " + name) if len(num) == 1 else name + " squared")
        elif e == 3:
            parts.append(("cubic " + name) if len(num) == 1 else name + " cubed")
        else:
            parts.append(name + " " + _exp_ordinal(e))
    for sym, e in den:
        names = unit_lookup(sym)
        if names is None:
            _gap("unit " + sym)
            parts.append("per " + sym)
            continue
        name = names[0]
        timeish = sym in _TIMEISH
        if e == 1:
            parts.append("per " + name)
        elif e == 2:
            parts.append(f"per {name} squared" if timeish else f"per square {name}")
        elif e == 3:
            parts.append(f"per {name} cubed" if timeish else f"per cubic {name}")
        else:
            parts.append(f"per {name} {_exp_ordinal(e)}")
    return " ".join(parts)


# --------------------------------------------------------------------------------------------------
# Control-character repair and small text helpers
# --------------------------------------------------------------------------------------------------

# A JSON string "\\theta" written as "\theta" arrives as TAB + "heta"; put the backslash back.
_CTRL_FIX = [
    (re.compile("\x09(?=imes|heta|ext\\{|an\\b|au\\b|ilde|o\\b|riangle|op\\b|extrm|extit|extbf|herefore)"), r"\\t"),
    (re.compile("\x0c(?=rac|orall)"), r"\\f"),
    (re.compile("\x08(?=eta|ar\\b|ar\\{|egin|inom|oldsymbol|ullet|ecause|ig)"), r"\\b"),
    (re.compile("\x07(?=lpha|pprox|ngle)"), r"\\a"),
    (re.compile("\x0b(?=ec\\b|ec\\{|ee|arepsilon|artheta|arphi|arrho|dots|ert)"), r"\\v"),
    (re.compile("\x0d(?=ho\\b|ightarrow|ightleftharpoons|ceil|floor|angle|ightarrow)"), r"\\r"),
]
_RE_CTRL = re.compile("[\x00-\x08\x0b\x0c\x0e-\x1f\x7f-\x9f]")


def _repair(text: str) -> str:
    for pat, rep in _CTRL_FIX:
        text = pat.sub(rep, text)
    text = _RE_CTRL.sub(" ", text)  # PDF extraction leaves control characters where spaces were
    return text.replace("\u2126", "\u03a9").replace("\u00b5", "\u03bc").replace("\u2206", "\u0394")


# --------------------------------------------------------------------------------------------------
# LaTeX parser
# --------------------------------------------------------------------------------------------------

_TOK = re.compile(r"\\[A-Za-z]+\*?|\\.|\d+(?:\.\d+)?|\.\d+|[A-Za-z]|\s+|[^\sA-Za-z\d\\]", re.S)
_DROP_SIZING = re.compile(r"\\(?:left|right|bigl|bigr|Bigl|Bigr|biggl|biggr|Biggl|Biggr|bigm|Bigm|big|Big|bigg|Bigg)"
                          r"(?![A-Za-z])\s*\.?")
_RE_THIN_THOUSANDS = re.compile(r"(?<=\d)(?:\\,|\{,\}|\\ |~)(?=\d{3}(?!\d))")
_STYLE_CMDS = {"displaystyle", "textstyle", "scriptstyle", "scriptscriptstyle", "limits", "nolimits", "Large", "large",
               "small", "normalsize", "footnotesize", "tiny", "huge", "Huge", "boldmath", "nonumber", "notag",
               "hline", "relax", "strut", "protect", "mathstrut", "allowbreak", "centering", "hfill", "vfill", "cr",
               "newline", "noindent", "smash", "ensuremath"}
_SPACE_CMDS = {",", ";", ":", "!", " ", ">", "quad", "qquad", "enspace", "thinspace", "medspace", "thickspace",
               "negthinspace", "hspace", "vspace", "mspace"}
_ACCENTS = {"vec": "vec", "overrightarrow": "vec", "overrightharpoon": "vec", "hat": "hat", "widehat": "hat",
            "bar": "bar", "overline": "bar", "underline": "under", "dot": "dot", "ddot": "ddot", "tilde": "tilde",
            "widetilde": "tilde", "check": "check", "breve": "breve", "acute": "acute", "grave": "grave",
            "mathring": "ring", "underbrace": "under", "overbrace": "bar", "overleftarrow": "vec"}
_TEXT_CMDS = {"text", "textrm", "mbox", "textit", "textbf", "textsf", "texttt", "textnormal", "hbox", "emph",
              "textsc", "mathrm", "mathit", "mathsf", "mathtt", "operatorname", "mathnormal", "rm", "pu"}
_BOLD_CMDS = {"mathbf", "boldsymbol", "bm", "bf", "mathbfit", "pmb"}
_BIGOPS = {"int": "integral", "iint": "double integral", "iiint": "triple integral", "oint": "contour integral",
           "sum": "sum", "prod": "product", "coprod": "coproduct", "bigcup": "union", "bigcap": "intersection",
           "lim": "limit", "limsup": "limit superior", "liminf": "limit inferior", "bigoplus": "sum",
           "bigotimes": "product", "bigvee": "or", "bigwedge": "and", "max": "maximum", "min": "minimum",
           "sup": "supremum", "inf": "infimum", "argmax": "argument that maximises", "argmin": "argument that minimises"}
_FUNCS = {
    "sin": "sine", "cos": "cosine", "tan": "tangent", "sec": "secant", "csc": "cosecant", "cosec": "cosecant",
    "cot": "cotangent", "sinh": "hyperbolic sine", "cosh": "hyperbolic cosine", "tanh": "hyperbolic tangent",
    "sech": "hyperbolic secant", "csch": "hyperbolic cosecant", "coth": "hyperbolic cotangent",
    "arcsin": "inverse sine", "arccos": "inverse cosine", "arctan": "inverse tangent", "arcsec": "inverse secant",
    "arccsc": "inverse cosecant", "arccot": "inverse cotangent", "arsinh": "inverse hyperbolic sine",
    "arcosh": "inverse hyperbolic cosine", "artanh": "inverse hyperbolic tangent", "arcsinh": "inverse hyperbolic sine",
    "arccosh": "inverse hyperbolic cosine", "arctanh": "inverse hyperbolic tangent",
    "log": "log", "ln": "natural log", "lg": "log to the base ten", "exp": "exponential",
    "det": "the determinant", "gcd": "the highest common factor", "lcm": "the lowest common multiple",
    "arg": "the argument", "dim": "the dimension", "ker": "the kernel", "Pr": "the probability", "deg": "the degree",
    "mod": "mod", "bmod": "mod", "hom": "hom", "tr": "the trace", "rank": "the rank",
}
_OF_FUNCS = {"log", "ln", "lg", "exp", "det", "gcd", "lcm", "arg", "dim", "ker", "Pr", "deg", "tr", "rank"}
_TRIG = {"sin", "cos", "tan", "sec", "csc", "cosec", "cot", "sinh", "cosh", "tanh", "sech", "csch", "coth"}
_FUNC_LETTERS = set("fghFGHPQRpq")
_OPERATORNAMES = {"Var": "the variance of", "Cov": "the covariance of", "E": "the expected value of",
                  "Corr": "the correlation of", "SD": "the standard deviation of", "sd": "the standard deviation of",
                  "Bin": "binomial", "Po": "Poisson", "Geo": "geometric", "arcsin": "inverse sine",
                  "arccos": "inverse cosine", "arctan": "inverse tangent", "sgn": "the sign of", "cosec": "cosecant",
                  "rank": "the rank of", "tr": "the trace of", "diag": "diagonal", "Re": "the real part of",
                  "Im": "the imaginary part of", "sech": "hyperbolic secant", "cosech": "hyperbolic cosecant",
                  "arsinh": "inverse hyperbolic sine", "arcosh": "inverse hyperbolic cosine",
                  "artanh": "inverse hyperbolic tangent", "d": "d", "Pr": "the probability of"}


_BARE_FUNCS = ("arcsin", "arccos", "arctan", "sinh", "cosh", "tanh", "sin", "cos", "tan", "sec", "csc", "cot", "log",
               "ln", "exp", "lim", "det")
_TRIG_BARE = {"sin", "cos", "tan", "sec", "csc", "cot", "sinh", "cosh", "tanh"}


class _Parser:
    """LaTeX -> a small tree of tuples.  Never raises; unknown input becomes ('cmd', name) / ('op', ch)."""

    def __init__(self, src: str):
        src = _DROP_SIZING.sub(" ", src)
        src = _RE_THIN_THOUSANDS.sub("", src)
        src = _RE_SUPRUN.sub(lambda m: "^{" + "".join(_SUP_MAP[c] for c in m.group()) + "}", src)
        src = _RE_SUBRUN.sub(lambda m: "_{" + "".join(_SUB_MAP[c] for c in m.group()) + "}", src)
        self.t = [m.group() for m in _TOK.finditer(src)]
        self.i = 0

    # -- token plumbing -----------------------------------------------------------------------------
    def _ws(self) -> None:
        while self.i < len(self.t) and self.t[self.i].isspace():
            self.i += 1

    def peek(self) -> str | None:
        self._ws()
        return self.t[self.i] if self.i < len(self.t) else None

    def take(self) -> str | None:
        self._ws()
        if self.i >= len(self.t):
            return None
        self.i += 1
        return self.t[self.i - 1]

    def raw_group(self) -> str:
        """Everything inside the next {...} (or the next single token), spaces kept."""
        self._ws()
        if self.i >= len(self.t):
            return ""
        if self.t[self.i] != "{":
            self.i += 1
            return self.t[self.i - 1]
        depth, j, out = 0, self.i, []
        while j < len(self.t):
            tok = self.t[j]
            if tok == "{":
                depth += 1
                if depth > 1:
                    out.append(tok)
            elif tok == "}":
                depth -= 1
                if depth == 0:
                    j += 1
                    break
                out.append(tok)
            else:
                out.append(tok)
            j += 1
        self.i = j
        return "".join(out)

    # -- grammar ------------------------------------------------------------------------------------
    def row(self, closers: tuple[str, ...] = ()) -> list:
        nodes: list = []
        while True:
            t = self.peek()
            if t is None or t in closers:
                break
            if t == "}":  # an unmatched brace at this level: ignore it
                self.take()
                continue
            n = self.item()
            if n is not None:
                nodes.append(n)
        return _pair_bars(nodes)

    def item(self):
        before = self.i
        if self.peek() in ("^", "_"):
            base = ("empty",)
        else:
            base = self.atom()
            if self.i == before:  # always make progress
                self.take()
                return None
        sub = sup = None
        primes = 0
        while True:
            t = self.peek()
            if t == "'":
                self.take()
                primes += 1
            elif t == "^":
                self.take()
                arg = self.script_arg()
                sup = arg if sup is None else sup + arg
            elif t == "_":
                self.take()
                arg = self.script_arg()
                sub = arg if sub is None else sub + arg
            else:
                break
        if primes:
            sup = [("prime", primes)] + (sup or [])
        if base == ("group", []):
            base = ("empty",)
        if base is None:
            if sub is None and sup is None:
                return None
            base = ("empty",)
        if sub is None and sup is None:
            return base
        return ("script", base, sub, sup)

    def script_arg(self) -> list:
        t = self.peek()
        if t is None:
            return []
        if t == "{":
            self.take()
            r = self.row(closers=("}",))
            if self.peek() == "}":
                self.take()
            return r
        # a single token; a multi-digit number takes only its first digit (TeX)
        self._ws()
        tok = self.t[self.i]
        if re.fullmatch(r"\d+(?:\.\d+)?", tok) and len(tok) > 1:
            self.t[self.i:self.i + 1] = [tok[0], tok[1:]]
        before = self.i
        a = self.atom_noscript()
        if self.i == before:
            self.take()
            return []
        return [a] if a is not None else []

    def atom_noscript(self):
        return self.atom()

    def atom(self):
        t = self.take()
        if t is None:
            return None
        if t == "{":
            r = self.row(closers=("}",))
            if self.peek() == "}":
                self.take()
            return ("group", r)
        if t in ("(", "["):
            return self.paren(t)
        if t[0] == "\\":
            return self.command(t[1:])
        if re.fullmatch(r"\d+(?:\.\d+)?|\.\d+", t):
            return ("num", t)
        if t.isascii() and t.isalpha():
            fn = self.bare_function(t)
            if fn is not None:
                return fn
            return ("var", t)
        if len(t) == 1 and t.isalpha():
            return ("var", t)  # unicode letter: handled when spoken
        if t == "&":
            return ("sep",)
        if t == "~":
            return None
        if t == "$":
            return None
        return ("op", t)

    def bare_function(self, first: str):
        """sin, cos, ln ... written as plain letters: consume them and return a function node."""
        letters = [first]
        j = self.i
        while j < len(self.t) and len(self.t[j]) == 1 and self.t[j].isascii() and self.t[j].isalpha():
            letters.append(self.t[j])
            j += 1
        word = "".join(letters)
        for name in _BARE_FUNCS:
            if word.startswith(name):
                rest = len(word) - len(name)
                if rest == 0 or (name in _TRIG_BARE and rest <= 1) or (name in ("ln", "log") and rest <= 1):
                    self.i += len(name) - 1
                    return ("big", name) if name == "lim" else ("func", name)
        return None

    def paren(self, opener: str):
        save = self.i
        inner = self.row(closers=(")", "]", "}"))
        closer = self.peek()
        if closer in (")", "]"):
            self.take()
            return ("paren", opener, closer, inner)
        self.i = save
        return ("op", opener)

    def arg(self) -> list:
        """One argument of a command: a {group} or a single token (TeX style, \\frac12)."""
        t = self.peek()
        if t is None:
            return []
        if t == "{":
            self.take()
            r = self.row(closers=("}",))
            if self.peek() == "}":
                self.take()
            return r
        self._ws()
        tok = self.t[self.i]
        if re.fullmatch(r"\d+(?:\.\d+)?", tok) and len(tok) > 1:
            self.t[self.i:self.i + 1] = [tok[0], tok[1:]]
        n = self.atom()
        return [n] if n is not None else []

    def command(self, name: str):
        if name in _SPACE_CMDS:
            if name in ("quad", "qquad"):
                return ("sep",)
            if name in ("hspace", "vspace", "mspace"):
                self.raw_group()
            return None
        if name in _STYLE_CMDS:
            return None
        if len(name) == 1 and not name.isalpha():
            return self.escaped(name)
        if name in ("frac", "dfrac", "tfrac", "cfrac"):
            a = self.arg()
            b = self.arg()
            return ("frac", a, b)
        if name == "choose":
            return ("op", "choose")
        if name in ("binom", "dbinom", "tbinom"):
            a = self.arg()
            b = self.arg()
            return ("binom", a, b)
        if name == "sqrt":
            idx = None
            if self.peek() == "[":
                self.take()
                idx = self.row(closers=("]",))
                if self.peek() == "]":
                    self.take()
            return ("sqrt", idx, self.arg())
        if name in ("root",):
            idx = self.arg()
            return ("sqrt", idx, self.arg())
        if name == "ce":
            return ("ce", self.raw_group())
        if name in _TEXT_CMDS:
            return ("text" if name in ("text", "textrm", "mbox", "textit", "textbf", "textsf", "texttt",
                                       "textnormal", "hbox", "emph", "textsc") else "mathrm", self.raw_group())
        if name in _BOLD_CMDS:
            return ("bold", self.arg())
        if name in ("mathbb", "mathcal", "mathscr", "mathfrak", "mathbbm"):
            return ("bb" if name in ("mathbb", "mathbbm") else "group", self.raw_group() if name in ("mathbb", "mathbbm") else self.arg())
        if name in _ACCENTS:
            return ("acc", _ACCENTS[name], self.arg())
        if name in ("textcolor", "colorbox", "fcolorbox"):
            self.raw_group()
            return ("group", self.arg())
        if name in ("color",):
            self.raw_group()
            return None
        if name in ("boxed", "cancel", "bcancel", "xcancel", "sout", "phantom", "vphantom", "hphantom", "underset"):
            r = self.arg()
            if name in ("phantom", "vphantom", "hphantom"):
                return None
            if name == "underset":
                return ("group", self.arg())
            return ("group", r)
        if name in ("overset", "stackrel"):
            over = self.arg()
            base = self.arg()
            return ("overset", over, base)
        if name in ("xrightarrow", "xleftarrow", "xrightleftharpoons"):
            if self.peek() == "[":
                self.take()
                self.row(closers=("]",))
                if self.peek() == "]":
                    self.take()
            over = self.arg()
            return ("xarrow", name, over)
        if name in ("label", "tag", "eqref", "ref", "vphantom", "hphantom"):
            self.raw_group()
            return None
        if name in ("pmod",):
            return ("pmod", self.arg())
        if name == "begin":
            return self.environment()
        if name == "end":
            self.raw_group()
            return None
        if name == "not":
            return ("not",)
        if name in _BIGOPS:
            return ("big", name)
        if name in _FUNCS:
            return ("func", name)
        if name in ("over", "atop"):
            return ("op", "/")
        if name in ("\\",):
            return ("nl",)
        return ("cmd", name)

    def escaped(self, ch: str):
        if ch == "\\":
            return ("nl",)
        if ch in "{":
            return self.braceset()
        if ch in "}":
            return ("op", "}")
        if ch == "|":
            return ("op", "||")
        if ch in "%&#$_":
            return ("op", "%") if ch == "%" else (None if ch in "#_$" else ("op", "and"))
        return ("op", ch)

    def braceset(self):
        save = self.i
        inner = self.row(closers=("\\}",))
        if self.peek() == "\\}":
            self.take()
            return ("set", inner)
        self.i = save
        return ("op", "{")

    def environment(self):
        name = self.raw_group().strip()
        base = name.rstrip("*")
        if base in ("array", "alignedat", "subarray"):
            if self.peek() == "{":
                self.raw_group()
        rows: list[list[list]] = [[]]
        while True:
            cell = self.row(closers=("&", "\\\\", "\\end"))
            rows[-1].append(cell)
            t = self.peek()
            if t == "&":
                self.take()
            elif t == "\\\\":
                self.take()
                rows.append([])
            else:
                if t == "\\end":
                    self.take()
                    self.raw_group()
                break
        if rows and all(not any(c for c in r) for r in rows[-1:]) and len(rows) > 1:
            rows.pop()
        return ("env", base, rows)


def _pair_bars(nodes: list) -> list:
    """Pair |x| into ('abs', ...) / ||x|| into ('norm', ...); a lone | stays an operator ('given')."""
    for kind, tag in (("|", "abs"), ("||", "norm")):
        idx = [i for i, n in enumerate(nodes) if n == ("op", kind)]
        if len(idx) >= 2 and len(idx) % 2 == 0:
            out, last = [], 0
            for a, b in zip(idx[0::2], idx[1::2]):
                out.extend(nodes[last:a])
                out.append((tag, nodes[a + 1:b]))
                last = b + 1
            out.extend(nodes[last:])
            nodes = out
    return nodes


# --------------------------------------------------------------------------------------------------
# Units inside maths
# --------------------------------------------------------------------------------------------------

_RE_UNIT_TOK = re.compile(r"\\[A-Za-z]+|\\.|\d+|[A-Za-zÅΩ%°μµ]+|\s+|[^\sA-Za-z\d\\]")


def _parse_units_latex(raw: str) -> list[tuple[str, int]] | None:
    """The unit expression in a \\mathrm{...} body: 'kJ\\,mol^{-1}' -> [('kJ',1),('mol',-1)]; None if it is not one."""
    toks = [m.group() for m in _RE_UNIT_TOK.finditer(raw.replace("\\mathrm", "").replace("\\text", ""))]
    pos = 0
    run: list[tuple[str, int]] = []
    denominator = False
    paren_den = False

    def skip_ws():
        nonlocal pos
        while pos < len(toks) and (toks[pos].isspace() or toks[pos] in ("\\,", "\\ ", "\\;", "\\!", "\\:", "~", "{", "}")):
            pos += 1

    def read_exp() -> int | None:
        nonlocal pos
        if pos < len(toks) and toks[pos] == "^":
            pos += 1
            skip_open = pos < len(toks) and toks[pos] == "{"
            if skip_open:
                pos += 1
            sign = 1
            if pos < len(toks) and toks[pos] in ("-", "−", "–"):
                sign, pos = -1, pos + 1
            elif pos < len(toks) and toks[pos] == "+":
                pos += 1
            if pos < len(toks) and toks[pos].isdigit():
                v = int(toks[pos])
                pos += 1
                if skip_open and pos < len(toks) and toks[pos] == "}":
                    pos += 1
                return sign * v
            return None
        return 0

    while True:
        skip_ws()
        if pos >= len(toks):
            break
        t = toks[pos]
        if t in ("\\cdot", "·", ".", "\\times"):
            pos += 1
            continue
        if t == "/":
            denominator = True
            pos += 1
            continue
        if t == "(" and denominator:
            paren_den = True
            pos += 1
            continue
        if t == ")" and paren_den:
            paren_den = False
            denominator = False
            pos += 1
            continue
        if t == "^" and pos + 1 < len(toks) and toks[pos + 1] == "\\circ":  # ^\circ C
            pos += 2
            skip_ws()
            sym = "°"
            if pos < len(toks) and toks[pos] in ("C", "F"):
                sym += toks[pos]
                pos += 1
            run.append((sym, 1))
            continue
        if t == "\\mu" or t == "\\Omega" or t == "\\%" or t == "\\circ" or t == "\\AA" or t == "\\angstrom":
            sym = {"\\mu": "μ", "\\Omega": "Ω", "\\%": "%", "\\circ": "°", "\\AA": "Å", "\\angstrom": "Å"}[t]
            pos += 1
            if sym == "μ" and pos < len(toks) and toks[pos].isalpha():
                sym += toks[pos]
                pos += 1
            elif sym == "°" and pos < len(toks) and toks[pos] in ("C", "F"):
                sym += toks[pos]
                pos += 1
        elif re.fullmatch(r"[A-Za-zÅΩ%°μµ]+", t):
            sym = t
            pos += 1
            while pos < len(toks) and toks[pos] == "_":  # no subscripts in units
                return None
        else:
            return None
        if unit_lookup(sym) is None:
            return None
        e = read_exp()
        if e is None:
            return None
        e = e if e != 0 else 1
        if denominator:
            run.append((sym, -abs(e)))
        else:
            run.append((sym, e))
    return run or None


def _unit_node_run(nd) -> list[tuple[str, int]] | None:
    """The unit run held by a ('mathrm'|'text', raw) node or a script of one, else None."""
    if nd[0] in ("mathrm", "text"):
        raw = nd[1]
        if nd[0] == "text" and not raw.strip():
            return None
        return _parse_units_latex(raw)
    if nd[0] == "script" and nd[1][0] in ("mathrm", "text") and nd[2] is None and nd[3] is not None:
        base = _parse_units_latex(nd[1][1])
        e = _row_int(nd[3])
        if base is None or e is None:
            return None
        s, e0 = base[-1]
        return base[:-1] + [(s, e0 * e)]
    return None


def _row_int(row) -> int | None:
    """A row that is just a (signed) whole number -> int."""
    if not row:
        return None
    sign = 1
    r = list(row)
    if r[0] in (("op", "-"), ("op", "−"), ("op", "–")):
        sign, r = -1, r[1:]
    elif r[0] == ("op", "+"):
        r = r[1:]
    if len(r) == 1 and r[0][0] == "num" and r[0][1].isdigit():
        return sign * int(r[0][1])
    if len(r) == 1 and r[0][0] == "group":
        return _row_int(r[0][1])
    return None


def _numlike(nd) -> bool:
    if nd is None:
        return False
    if nd[0] == "num":
        return True
    if nd[0] == "script" and nd[1][0] == "num":
        return True
    if nd[0] == "script" and nd[1][0] == "empty":
        return False
    if nd[0] in ("frac", "paren") and nd[0] == "frac":
        return True
    if nd[0] == "group" and nd[1]:
        return _numlike(nd[1][-1])
    return False


def _merge_units(nodes: list) -> list:
    out: list = []
    i = 0
    n = len(nodes)
    while i < n:
        nd = nodes[i]
        run = _unit_node_run(nd)
        if run in ([("C", 1)], [("F", 1)]) and out and out[-1][0] == "script" and out[-1][3] == [("cmd", "circ")]:
            out.append(("degunit", out.pop(), "Celsius" if run[0][0] == "C" else "Fahrenheit"))
            i += 1
            continue
        if run is None and nd[0] == "cmd" and nd[1] == "Omega" and out and _numlike(out[-1]):
            run = [("Ω", 1)]
        if run is None and nd == ("op", "%") and out and _numlike(out[-1]):
            run = [("%", 1)]
        prefix = None
        if run is None and nd == ("cmd", "mu") and i + 1 < n and out and _numlike(out[-1]):
            nxt = _unit_node_run(nodes[i + 1])
            if nxt is not None and unit_lookup("μ" + nxt[0][0]) is not None and nxt[0][1] == 1 \
                    or (nxt is not None and nxt and unit_lookup("μ" + nxt[0][0])):
                run = [("μ" + nxt[0][0], nxt[0][1])] + nxt[1:]
                i += 1
        if run is None:
            out.append(nd)
            i += 1
            continue
        prev_num = bool(out) and (_numlike(out[-1]) or (out[-1][0] == "script" and out[-1][1][0] == "empty"
                                                       and out[-1][3] is not None and out[-1][3][:1] == [("cmd", "circ")]))
        ok = prev_num or any(e != 1 for _, e in run) or len(run) >= 2 or (len(run) == 1 and (
            len(run[0][0]) >= 2 or run[0][0] in _SINGLE_SAFE))
        if prev_num and out[-1][0] == "script" and out[-1][1][0] == "empty":
            ok = True
        if not ok:
            out.append(nd)
            i += 1
            continue
        j = i + 1
        while j < n:
            more = _unit_node_run(nodes[j])
            if more is None:
                if nodes[j] == ("op", "/") and j + 1 < n:
                    den = _unit_node_run(nodes[j + 1])
                    if den is not None:
                        run = run + [(s, -abs(e)) for s, e in den]
                        j += 2
                        continue
                break
            run = run + more
            j += 1
        out.append(("units", run))
        i = j
    return out


# --------------------------------------------------------------------------------------------------
# Subscript / text helpers
# --------------------------------------------------------------------------------------------------

_SUB_WORDS = {  # subscripts spoken as a word (otherwise: short ones spelled letter by letter)
    "initial": "initial", "final": "final", "max": "max", "min": "min", "total": "total", "cell": "cell",
    "atom": "atom", "sol": "sol", "hyd": "hyd", "lat": "lattice", "vap": "vaporisation", "fus": "fusion",
    "comb": "combustion", "neut": "neutralisation", "sub": "sublimation", "rms": "r m s", "avg": "average",
    "ave": "average", "eff": "effective", "net": "net", "air": "air", "water": "water", "in": "in", "out": "out",
    "eq": "e q", "sp": "s p", "stab": "stab", "diss": "diss", "ox": "ox", "red": "red", "rev": "rev",
    "obs": "obs", "calc": "calc", "exp": "exp", "ref": "ref", "tot": "total", "crit": "critical",
    "centre": "centre", "grav": "grav", "kin": "kinetic", "pot": "potential", "mean": "mean", "half": "half",
    "mix": "mix", "rel": "relative", "var": "var",
}


def _sub_text(s: str) -> str:
    low = s.lower()
    if low in _SUB_WORDS and (len(s) > 2 or low in ("in",)):
        return _SUB_WORDS[low]
    if s.isdigit():
        return number_words(s)
    if s.isalpha() and len(s) <= 3:
        return " ".join(s)
    return s


# --------------------------------------------------------------------------------------------------
# Speaker: tree -> words
# --------------------------------------------------------------------------------------------------


def _tidy(s: str) -> str:
    s = re.sub(r"\s+", " ", s).strip()
    s = re.sub(r"\s+([,.;:])", r"\1", s)
    s = re.sub(r",(?:\s*,)+", ",", s)
    return s.strip(" ,")


def _is_simple(row: list) -> bool:
    """A row that reads as one short unit: a number / letter / symbol, optionally negated."""
    r = [n for n in row if n[0] != "sep"]
    if r and r[0] in (("op", "-"), ("op", "−"), ("op", "+")):
        r = r[1:]
    if not r:
        return False
    if len(r) == 1:
        n = r[0]
        if n[0] in ("num", "var", "units"):
            return True
        if n[0] == "cmd" and (n[1] in _GREEK_NAME or n[1] in ("infty", "pi")):
            return True
        if n[0] == "mathrm" and len(n[1]) <= 2:
            return True
        if n[0] == "script":
            return _is_simple([n[1]]) and (n[2] is None or _is_simple(n[2])) and (n[3] is None or _is_simple(n[3]))
        if n[0] == "group":
            return _is_simple(n[1])
        if n[0] in ("acc", "ce", "text"):
            return n[0] == "acc" and len(n[2]) == 1
        return False
    # kt, nx, 2n: up to three plain letters / one number then letters
    if len(r) <= 3 and all(n[0] in ("var",) or (n[0] == "cmd" and n[1] in _GREEK_NAME) or n[0] == "num" for n in r):
        return True
    return False


class _Say:
    """Speak a tree.  One instance per top-level expression (it keeps small bits of state)."""

    def __init__(self) -> None:
        self.in_int = 0
        self.lim = False
        self.in_set = False
        self.in_prob = False

    # -- rows ---------------------------------------------------------------------------------------
    def row(self, nodes: list) -> str:
        nodes = _merge_units(nodes)
        out: list[str] = []
        i, n = 0, len(nodes)
        last_lone_num_paren = False
        while i < n:
            nd = nodes[i]
            tag = nd[0]
            prev = nodes[i - 1] if i else None
            nxt = nodes[i + 1] if i + 1 < n else None
            was_lone = False
            # nuclide: ^{14}_{6}C
            if tag == "script" and nd[1][0] == "empty" and nd[3] and nxt is not None:
                took = self.nuclide(nd, nodes, i)
                if took:
                    out.append(took[0])
                    i = took[1]
                    last_lone_num_paren = False
                    continue
            if tag == "script" and nd[1][0] == "empty" and nd[3] == [("cmd", "circ")] and prev is not None:
                out.append("degrees")
                if nxt is not None and nxt[0] in ("mathrm", "var") and nxt[1] in ("C", "F"):
                    out.append("Celsius" if nxt[1] == "C" else "Fahrenheit")
                    i += 1
                i += 1
                continue
            if tag == "num":
                # simple fractions 3/4
                if nxt == ("op", "/") and i + 2 < n and nodes[i + 2][0] == "num" and nd[1].isdigit() \
                        and nodes[i + 2][1].isdigit():
                    fw = fraction_words(int(nd[1]), int(nodes[i + 2][1]))
                    if fw and not (prev and prev[0] == "num"):
                        out.append(fw)
                        i += 3
                        continue
                out.append(number_words(nd[1]))
            elif tag == "var":
                out.append(self.var(nd[1], nodes, i))
            elif tag == "mathrm" and nd[1] == "d" and self.in_int > 0 and nxt is not None and (
                    nxt[0] == "var" or (nxt[0] == "script" and nxt[1][0] == "var")
                    or (nxt[0] == "cmd" and nxt[1] in _GREEK_NAME)):
                self.in_int -= 1
                out.append(", d")
            elif tag == "degunit":
                out.append(self.node(nd[1], prev, nxt) if nd[1][1][0] != "empty" else "degrees")
                out.append(nd[2])
            elif tag == "units":
                plural = not (prev is not None and prev[0] == "num" and _is_one(prev[1]))
                out.append(units_words(nd[1], plural))
            elif tag == "op":
                w = self.op(nd[1], prev, nxt, nodes, i)
                if w == "\0skip":
                    i += 2
                    continue
                if w:
                    out.append(w)
            elif tag == "sep" or tag == "nl":
                out.append(",")
            elif tag == "paren":
                lone = self.lone_paren_number(nd)
                if lone and last_lone_num_paren:
                    out.append("times")
                w = self.paren(nd, prev, nxt)
                out.append(w)
                was_lone = lone
            elif tag == "big":
                out.append(self.big(nd[1], None, None))
            elif tag == "func":
                out.append(self.func(nd[1], None, None, nxt))
            else:
                out.append(self.node(nd, prev, nxt))
            last_lone_num_paren = was_lone
            i += 1
        return _tidy(" ".join(x for x in out if x))

    def lone_paren_number(self, nd) -> bool:
        return nd[0] == "paren" and len(nd[3]) == 1 and nd[3][0][0] == "num"

    # -- single nodes -------------------------------------------------------------------------------
    def var(self, ch: str, nodes: list, i: int) -> str:
        if not ch.isascii():
            return self.char_words(ch)
        if ch == "d" and self.in_int > 0 and i + 1 < len(nodes) and (
                nodes[i + 1][0] in ("var",) or (nodes[i + 1][0] == "script" and nodes[i + 1][1][0] == "var")
                or (nodes[i + 1][0] == "cmd" and nodes[i + 1][1] in _GREEK_NAME)):
            self.in_int -= 1
            return ", d"
        return ch

    def char_words(self, ch: str) -> str:
        if ch in GREEK_CHAR:
            return GREEK_CHAR[ch]
        if ch in _UNI_WORDS:
            return _UNI_WORDS[ch]
        if ch in _REL:
            return _REL[ch]
        if ch.isalpha():
            _gap(ch)
            return unicodedata.name(ch, "").lower().split(" letter ")[-1] or ""
        return _fallback_char(ch)

    def op(self, ch: str, prev, nxt, nodes: list, i: int) -> str:
        if ch == "+":
            return "plus"
        if ch in "-−–":
            return "minus"
        if ch == "=":
            return "equals"
        if ch == "<":
            return "is less than"
        if ch == ">":
            return "is greater than"
        if ch == ",":
            return ","
        if ch == ";":
            return ","
        if ch == ":":
            if prev is not None and nxt is not None:
                return "to"
            return ","
        if ch == "!":
            return "factorial"
        if ch == "/":
            return "over"
        if ch in "*∗":
            return "times"
        if ch == ".":
            return "" if nxt is None or prev is None else "point"
        if ch == "|":
            return "such that" if self.in_set else "given"
        if ch == "||":
            return "double bar"
        if ch == "%":
            return "percent"
        if ch == "'":
            return "prime"
        if ch == "(":
            return "open bracket"
        if ch == ")":
            return "close bracket"
        if ch == "[":
            return "open square bracket"
        if ch == "]":
            return "close square bracket"
        if ch == "{":
            return "open brace"
        if ch == "}":
            return ""
        if ch == "and":
            return "and"
        if ch == "choose":
            return "choose"
        if ch == "?":
            return "question mark"
        if ch == "@":
            return "at"
        if ch == "`":
            return ""
        if ch == "±":
            return "plus or minus"
        if ch == "×":
            return "times"
        if ch == "÷":
            return "divided by"
        if ch == "·" or ch == "⋅":
            return "times"
        if ch in "°":
            return "degrees"
        if ch == "→":
            return self.arrow(prev, nxt)
        if ch in ("⇌", "⇋"):
            return "is in equilibrium with"
        if ch in _REL:
            return _REL[ch]
        if ch in _UNI_WORDS:
            return _UNI_WORDS[ch]
        if ch in GREEK_CHAR:
            return GREEK_CHAR[ch]
        return _fallback_char(ch)

    def arrow(self, prev, nxt) -> str:
        if self.lim:
            return "tends to"
        if prev is not None and prev[0] == "var" and nxt is not None and (
                nxt[0] in ("num",) or nxt == ("cmd", "infty") or nxt in (("op", "-"), ("op", "+"))):
            return "tends to"
        return "gives"

    def node(self, nd, prev, nxt) -> str:
        tag = nd[0]
        if tag == "group":
            return self.row(nd[1])
        if tag == "cmd":
            return self.cmd(nd[1], prev, nxt)
        if tag == "frac":
            return self.frac(nd[1], nd[2])
        if tag == "binom":
            a, b = self.row(nd[1]), self.row(nd[2])
            if _is_simple(nd[1]) and _is_simple(nd[2]):
                return f"{a} choose {b}"
            return f"the binomial coefficient, {a}, over, {b},"
        if tag == "sqrt":
            return self.sqrt(nd[1], nd[2])
        if tag == "script":
            return self.script(nd, prev, nxt)
        if tag == "paren":
            return self.paren(nd, prev, nxt)
        if tag == "abs":
            inner = self.row(nd[1])
            return f"the modulus of {inner}" if _is_simple(nd[1]) else f"the modulus of, {inner}, end modulus,"
        if tag == "norm":
            inner = self.row(nd[1])
            return f"the magnitude of {inner}" if _is_simple(nd[1]) else f"the magnitude of, {inner}, end magnitude,"
        if tag == "set":
            keep, self.in_set = self.in_set, True
            inner = self.row(nd[1])
            self.in_set = keep
            return f"the set {inner}," if inner else "the empty set"
        if tag == "acc":
            return self.accent(nd[1], nd[2])
        if tag == "bold":
            inner = self.row(nd[1])
            if inner in ("i", "j", "k"):
                return inner
            if inner in ("0",) or inner == "zero":
                return "the zero vector"
            return "vector " + inner
        if tag == "bb":
            return {"R": "the real numbers", "N": "the natural numbers", "Z": "the integers",
                    "Q": "the rational numbers", "C": "the complex numbers", "P": "the probability",
                    "E": "the expected value"}.get(nd[1].strip(), nd[1].strip())
        if tag == "ce":
            return chem_words(nd[1])
        if tag == "text":
            return text_words(nd[1])
        if tag == "mathrm":
            return self.mathrm(nd[1], prev, nxt)
        if tag == "env":
            return self.environment(nd[1], nd[2])
        if tag == "big":
            return self.big(nd[1], None, None)
        if tag == "func":
            return self.func(nd[1], None, None, nxt)
        if tag == "units":
            return units_words(nd[1])
        if tag == "pmod":
            return "mod " + self.row(nd[1])
        if tag == "overset":
            return self.row(nd[2])
        if tag == "xarrow":
            label = self.row(nd[2])
            if nd[1] == "xrightleftharpoons":
                return f"is in equilibrium with, {label}," if label else "is in equilibrium with"
            if nd[1] == "xleftarrow":
                return f"comes from, {label}," if label else "comes from"
            return f"yields, with {label}," if label else "yields"
        if tag == "not":
            return "not"
        if tag == "prime":
            return "prime" if nd[1] == 1 else ("double prime" if nd[1] == 2 else "triple prime")
        if tag == "empty":
            return ""
        if tag == "sep":
            return ","
        if tag == "nl":
            return ","
        if tag == "op":
            return self.op(nd[1], prev, nxt, [], 0)
        if tag == "num":
            return number_words(nd[1])
        if tag == "var":
            return self.var(nd[1], [], 0)
        _gap(f"node {tag}")  # pragma: no cover
        return ""

    # -- commands -----------------------------------------------------------------------------------
    def cmd(self, name: str, prev, nxt) -> str:
        if name in ("Sigma", "Pi") and nxt is not None and nxt[0] not in ("op", "sep"):
            return "the sum of" if name == "Sigma" else "the product of"
        if name in _GREEK_NAME:
            return _GREEK_NAME[name]
        if name in _CMD_REL:
            return self.op(_CMD_REL[name], prev, nxt, [], 0) if _CMD_REL[name] in "=<>" else _REL[_CMD_REL[name]]
        if name in ("to", "rightarrow") and prev is not None:
            return self.arrow(prev, nxt)
        if name == "cdot":
            return self.cdot(prev, nxt)
        if name == "circ":
            return "degrees"
        if name == "sim":
            if prev is not None and prev[0] == "var" and prev[1].isupper():
                return "is distributed as"
            return "is approximately"
        if name in ("Sigma", "Pi") and nxt is not None and nxt[0] not in ("op",):
            return "the sum of" if name == "Sigma" else "the product of"
        if name in ("ldots", "cdots", "dots", "dotsc", "dotsb", "vdots", "ddots"):
            return ", and so on,"
        if name in _CMD_WORDS:
            return _CMD_WORDS[name]
        if name in ("AA",):
            return "angstrom"
        _gap("\\" + name)
        return _camel_words(name)

    def cdot(self, prev, nxt) -> str:
        def vecish(n) -> bool:
            if n is None:
                return False
            if n[0] in ("bold", "acc") and (n[0] == "bold" or n[1] == "vec"):
                return True
            if n[0] == "script":
                return vecish(n[1])
            return False
        if vecish(prev) or vecish(nxt):
            return "dot"
        return "times"

    # -- composite nodes ----------------------------------------------------------------------------
    def frac(self, a: list, b: list) -> str:
        # derivatives: dy/dx, d^2y/dx^2, partial f / partial x
        d = self.derivative(a, b)
        if d:
            return d
        if len(a) == 1 and len(b) == 1 and a[0][0] == "num" and b[0][0] == "num" and a[0][1].isdigit() and b[0][1].isdigit():
            fw = fraction_words(int(a[0][1]), int(b[0][1]))
            if fw:
                return fw
        na, nb = self.row(a), self.row(b)
        if not na:
            return nb
        if _is_simple(a) and _is_simple(b):
            return f"{na} over {nb}"
        if _is_simple(a):
            return f"{na} over, {nb},"
        if _is_simple(b):
            return f"{na}, all over {nb}"
        return f"{na}, all over, {nb},"

    def derivative(self, a: list, b: list) -> str | None:
        def head(row):
            if not row:
                return None
            f = row[0]
            if f in (("var", "d"), ("mathrm", "d")):
                return "d", 1, row[1:]
            if f == ("cmd", "partial"):
                return "partial", 1, row[1:]
            if f[0] == "script" and f[1] in (("var", "d"), ("mathrm", "d"), ("cmd", "partial")) and f[2] is None:
                e = _row_int(f[3] or [])
                return ("partial" if f[1] == ("cmd", "partial") else "d"), e or 1, row[1:]
            return None
        ha, hb = head(a), head(b)
        if ha is None or hb is None or ha[0] != hb[0]:
            return None
        word = ha[0]
        rest_a = self.row(ha[2])
        top = word if ha[1] == 1 else f"{word} {int_words(ha[1])}"
        # denominator: d x, d x squared, partial x partial y
        bot = word + (" " + self.row(hb[2]) if hb[2] else "")
        if hb[1] != 1:  # \partial^2 x style (rare)
            bot = f"{word} {int_words(hb[1])}" + (" " + self.row(hb[2]) if hb[2] else "")
        return _tidy(f"{top} {rest_a} by {bot}") if rest_a else _tidy(f"{top} by {bot}")

    def sqrt(self, idx, rad: list) -> str:
        inner = self.row(rad)
        if idx is None or (len(idx) == 1 and idx[0] == ("num", "2")):
            kind = "the square root of"
        elif len(idx) == 1 and idx[0] == ("num", "3"):
            kind = "the cube root of"
        elif len(idx) == 1 and idx[0][0] == "num" and idx[0][1].isdigit() and 4 <= int(idx[0][1]) <= 12:
            kind = f"the {_ORD[int(idx[0][1])]} root of"
        else:
            kind = f"the {self.row(idx)} th root of"
        if _is_simple(rad):
            return f"{kind} {inner}"
        return f"{kind} {inner}, end root,"

    def accent(self, kind: str, row: list) -> str:
        inner = self.row(row)
        if not inner:
            return ""
        simple = len(row) == 1
        if kind == "vec":
            return f"vector {inner}"
        if kind == "hat":
            return f"{inner} hat"
        if kind == "bar":
            return f"{inner} bar"
        if kind == "dot":
            return f"{inner} dot"
        if kind == "ddot":
            return f"{inner} double dot"
        if kind == "tilde":
            return f"{inner} tilde"
        if kind == "under":
            return f"{inner} underlined" if not simple else inner
        return inner

    def mathrm(self, raw: str, prev, nxt) -> str:
        return mathrm_words(raw, self, prev, nxt)

    # -- parentheses --------------------------------------------------------------------------------
    def paren(self, nd, prev, nxt) -> str:
        _, o, c, inner = nd
        # concentration [H+]
        if o == "[" and c == "]" and inner and all(_conc_node(x) for x in inner):
            words = self.row(inner)
            if words in _NOBLE_CORE:
                return f"the {_NOBLE_CORE[words]} core"
            if words not in ("O", "H"):
                return "the concentration of " + words
        body = self.row(inner)
        if o == "(" and c == ")" and prev is not None and prev[0] in ("var", "script", "mathrm", "paren") \
                and not (prev[0] == "var" and prev[1] in _FUNC_LETTERS) \
                and (body in ("s", "l", "g", "a q") or body.replace(" ", "") == "aq"):
            return _STATE_ONE["aq" if "q" in body else body]
        if o == "(" and c == ")" and prev is not None:
            # a function call f(x), P(A)
            fl = None
            if prev[0] == "var" and prev[1] in _FUNC_LETTERS:
                fl = prev[1]
            if prev[0] == "script" and prev[1][0] == "var" and prev[1][1] in _FUNC_LETTERS and (
                    prev[3] is None or prev[3][0][0] == "prime"):
                fl = prev[1][1]
            if fl is not None:
                if prev[0] == "var" and prev[1] == "P":
                    saved = self.in_prob
                    self.in_prob = True
                    body = self.row(inner)
                    self.in_prob = saved
                return ("of " + body) if _is_simple(inner) or self.in_call_ok(inner) else f"of open bracket {body} close bracket"
            if prev[0] == "func":
                return "of " + body if _is_simple(inner) else f"of open bracket {body} close bracket"
            if prev[0] == "script" and prev[1][0] == "func":
                return "of " + body if _is_simple(inner) else f"of open bracket {body} close bracket"
        if o == "(" and c == ")" and len(inner) == 1 and inner[0][0] == "num" and (
                prev is None or prev[0] in ("op", "paren", "sep")) and not (prev and prev[0] == "op" and prev[1] in ("^", "_")):
            return body
        if o == "(" and c == ")" and (prev is None or (prev[0] == "op" and prev[1] in "=+-,:" )) \
                and len(inner) == 1 and inner[0][0] in ("var",) and not _next_is_script(nxt):
            return body
        oword = "open bracket" if o == "(" else "open square bracket"
        cword = "close bracket" if c == ")" else "close square bracket"
        if o == "[" and c == ")":
            oword, cword = "open square bracket", "close bracket"
        if not body:
            return f"{oword} {cword}"
        return f"{oword} {body} {cword}"

    def in_call_ok(self, inner: list) -> bool:
        """P(A ∩ B), P(A ∪ B), f(x, y): speak the argument without brackets when it is short and unambiguous."""
        return len(inner) <= 3 and not any(n[0] in ("op",) and n[1] in "+-=" for n in inner)

    # -- scripts ------------------------------------------------------------------------------------
    def script(self, nd, prev, nxt) -> str:
        _, base, sub, sup = nd
        bt = base[0]
        if bt == "big":
            return self.big(base[1], sub, sup)
        if bt == "func":
            return self.func(base[1], sub, sup, nxt)
        if bt == "empty":
            return self.empty_base(sub, sup)
        # charge / degree / standard / prime / star / dagger on a base
        if sup is not None:
            special = self.sup_special(base, sub, sup, prev)
            if special is not None:
                return special
        b = self.node_base(base, prev, nxt)
        out = b
        if sub is not None:
            out += " " + self.sub_words(sub)
        if sup is not None:
            out += self.sup_words(sup, base)
        return out

    def node_base(self, base, prev, nxt) -> str:
        if base[0] == "var":
            return self.var(base[1], [], 0)
        return self.node(base, prev, nxt)

    def sub_words(self, sub: list) -> str:
        sub = [n for n in sub if n[0] != "sep"]
        if not sub:
            return ""
        if all(n[0] == "var" for n in sub) and len(sub) >= 2 and all(n[1].isascii() for n in sub):
            return _sub_text("".join(n[1] for n in sub))
        if len(sub) == 1 and sub[0][0] in ("mathrm", "text"):
            raw = sub[0][1].strip()
            if raw and raw.replace("_", "").isalnum():
                return _sub_text(raw)
            return self.row(sub)
        if len(sub) == 1 and sub[0] in (("cmd", "perp"), ("cmd", "parallel"), ("cmd", "infty")):
            return {"perp": "perpendicular", "parallel": "parallel", "infty": "infinity"}[sub[0][1]]
        if len(sub) == 1 and sub[0][0] == "var":
            return self.row(sub)
        if _is_simple(sub) or (len(sub) == 3 and sub[1] == ("op", "/") and sub[0][0] == "num" and sub[2][0] == "num"):
            return self.row(sub)
        if len(sub) == 1 and sub[0][0] == "group":
            return self.sub_words(sub[0][1])
        return "sub " + self.row(sub) + ","

    def sup_words(self, sup: list, base) -> str:
        sup = [n for n in sup if n[0] != "sep"]
        if sup == [("num", "2")]:
            return " squared"
        if sup == [("num", "3")]:
            return " cubed"
        ten = base == ("num", "10") or (base[0] == "group" and base[1] == [("num", "10")])
        if len(sup) == 1 and sup[0][0] == "num" and sup[0][1].isdigit() and not ten:
            v = int(sup[0][1])
            if 4 <= v <= 12:
                return " to the " + _ORD[v]
            return " to the power of " + number_words(sup[0][1])
        if _is_simple(sup):
            return " to the " + self.row(sup)
        return " to the power of " + self.row(sup) + ","

    def sup_special(self, base, sub, sup: list, prev) -> str | None:
        sup = [n for n in sup if n[0] != "sep"]
        low = self.sub_words(sub) if sub is not None else ""
        pre = self.node_base(base, prev, None) + ((" " + low) if low else "")
        if self.lim and base[0] == "num" and sup in ([("op", "+")], [("op", "-")], [("op", "−")]):
            return pre + (" from above" if sup[0][1] == "+" else " from below")
        if sup == [("cmd", "circ")] or sup == [("op", "°")]:
            letter = base[1] if base[0] == "var" else (base[1] if base[0] == "mathrm" else "")
            if base[0] == "var" and base[1].isupper() or (base[0] == "mathrm" and base[1] in ("E", "H", "S", "G", "K")):
                return pre + " standard"
            if base[0] in ("num", "var", "paren", "group", "frac") or base[0] == "cmd":
                return pre + " degrees"
            return pre + " degrees"
        if sup in ([("cmd", "ominus")], [("op", "⊖")], [("op", "⦵")]) or sup == [("cmd", "varominus")]:
            return pre + " standard"
        if sup and sup[0][0] == "prime":
            n = sup[0][1]
            more = self.row(sup[1:]) if len(sup) > 1 else ""
            return pre + (" prime" if n == 1 else (" double prime" if n == 2 else " triple prime")) + ((" " + more) if more else "")
        if sup == [("cmd", "prime")]:
            return pre + " prime"
        if sup == [("op", "*")] or sup == [("op", "∗")]:
            return pre + " star"
        if sup == [("cmd", "dagger")]:
            return pre + " dagger"
        if sup == [("cmd", "bullet")]:
            return pre + " radical"
        if sup == [("var", "T")] and base[0] in ("var", "paren") and (base[0] == "paren" or base[1].isupper()):
            return pre + " transpose"
        # ion charge: H+, Cu2+, SO4 2-
        ch = _charge_of(sup)
        if ch is not None and base[0] == "cmd" and base[1] in _GREEK_NAME:
            return f"{_GREEK_NAME[base[1]]} {charge_words(*ch)}"
        if ch is not None and base[0] in ("var", "mathrm", "ce", "text") and (
                base[0] != "var" or base[1].isupper() or base[1] in ("e",)):
            sym = base[1] if base[0] in ("var", "mathrm", "text") else ""
            if sym and (sym in ELEMENT_NAME or (len(sym) <= 3 and sym.isalpha())):
                return ion_words(sym, ch, sub)
        return None

    def empty_base(self, sub, sup) -> str:
        # an exponent / subscript with nothing to attach to: read it plainly
        parts = []
        if sup is not None:
            parts.append(self.row(sup))
        if sub is not None:
            parts.append(self.row(sub))
        return " ".join(p for p in parts if p)

    def nuclide(self, nd, nodes: list, i: int):
        """^{14}_{6}C  ->  'carbon fourteen, atomic number six'."""
        _, base, sub, sup = nd
        mass = _row_int(sup)
        z = _row_int(sub) if sub is not None else None
        nxt = nodes[i + 1]
        sym = None
        used = 1
        charge_tail = ""
        if nxt[0] == "script" and nxt[1][0] in ("mathrm", "var") and nxt[2] is None and nxt[3] is not None \
                and _charge_of(nxt[3]) is not None:
            charge_tail = " " + charge_words(*_charge_of(nxt[3]))
            nxt = nxt[1]
        if nxt[0] in ("mathrm", "var", "ce"):
            s = nxt[1].strip() if nxt[0] != "var" else nxt[1]
            if nxt[0] == "var" and i + 2 < len(nodes) and nodes[i + 2][0] == "var" and nodes[i + 2][1].islower() \
                    and (s + nodes[i + 2][1]) in ELEMENT_NAME:
                s += nodes[i + 2][1]
                used = 2
            sym = s
        elif nxt[0] == "cmd" and nxt[1] in _GREEK_NAME:
            sym = nxt[1]
        if mass is None or sym is None:
            return None
        if nxt[0] == "cmd":
            word = {"alpha": "an alpha particle", "beta": "a beta particle", "gamma": "a gamma ray"}.get(sym)
            return (word, i + 1 + used) if word else None
        if sym in ELEMENT_NAME:
            name = ELEMENT_NAME[sym]
            out = f"{name} {mass_words(mass)}{charge_tail}"
            if z is not None:
                out += f", atomic number {int_words(z)},"
            return (out, i + 1 + used)
        if sym == "e" and mass == 0:
            return ("an electron" if z == -1 else ("a positron" if z in (1, -1, None) and z != -1 else "an electron"), i + 2)
        if sym == "n" and mass == 1:
            return ("a neutron", i + 2)
        if sym == "p" and mass == 1:
            return ("a proton", i + 2)
        return None

    # -- operators with limits ----------------------------------------------------------------------
    def big(self, name: str, sub, sup) -> str:
        head = {"int": "the integral", "iint": "the double integral", "iiint": "the triple integral",
                "oint": "the contour integral", "sum": "the sum", "prod": "the product", "coprod": "the coproduct",
                "bigcup": "the union", "bigcap": "the intersection", "lim": "the limit", "limsup": "the limit superior",
                "liminf": "the limit inferior", "max": "the maximum", "min": "the minimum", "sup": "the supremum",
                "inf": "the infimum", "bigoplus": "the sum", "bigotimes": "the product", "bigvee": "the union",
                "bigwedge": "the intersection", "argmax": "the argument that maximises",
                "argmin": "the argument that minimises"}[name]
        if name in ("int", "iint", "iiint", "oint"):
            self.in_int += {"iint": 2, "iiint": 3}.get(name, 1)
        if name == "lim":
            if sub is None:
                return head + " of"
            keep, self.lim = self.lim, True
            body = self.row(sub)
            self.lim = keep
            body = re.sub(r"\b(zero|[a-z0-9 ]+?) (plus|minus)$", lambda m: m.group(0), body)
            return f"{head} as {body} of"
        if name in ("max", "min", "sup", "inf", "argmax", "argmin"):
            if sub is None:
                return head + " of"
            return f"{head} over {self.row(sub)} of"
        text = head
        if sub is not None and sup is not None:
            lo = self.row(sub)
            hi = self.row(sup)
            if any(n == ("op", "=") for n in sub):
                text += f" from {lo} to {hi}"
            else:
                text += f" from {lo} to {hi}"
        elif sub is not None:
            lo = self.row(sub)
            text += (f" from {lo}" if any(n == ("op", "=") for n in sub) else f" over {lo}")
        elif sup is not None:
            text += f" up to {self.row(sup)}"
        return text + " of"

    def func(self, name: str, sub, sup, nxt) -> str:
        word = _FUNCS.get(name, name)
        if name in ("log",) and sub is not None:
            base = self.row(sub)
            word = f"log to the base {base}"
            sub = None
        if name in ("sin", "cos", "tan", "sec", "csc", "cosec", "cot", "sinh", "cosh", "tanh") and sup is not None:
            inv = _row_int(sup)
            if inv == -1:
                word = "inverse " + word
                sup = None
        if sup is not None:
            word += self.sup_words(sup, ("func", name))
        if name in _OF_FUNCS and nxt is not None and nxt[0] != "paren":
            word += " of"
        if name in ("det", "gcd", "lcm", "Pr", "tr", "rank", "arg", "dim", "ker", "deg") and nxt is not None \
                and nxt[0] != "paren" and not word.endswith(" of"):
            word += " of"
        return word

    # -- environments -------------------------------------------------------------------------------
    def environment(self, name: str, rows: list) -> str:
        rows = [r for r in rows if r and any(c for c in r)]
        if not rows:
            return ""
        if name in ("pmatrix", "bmatrix", "matrix", "Bmatrix", "vmatrix", "Vmatrix", "smallmatrix", "array"):
            nrows, ncols = len(rows), max(len(r) for r in rows)
            cells = [[self.row(c) for c in r] for r in rows]
            kind = {"vmatrix": "determinant", "Vmatrix": "norm"}.get(name, "matrix")
            if kind == "matrix" and ncols == 1 and nrows > 1:
                return f"the column vector {', '.join(c[0] for c in cells)},"
            if kind == "matrix" and nrows == 1 and ncols > 1:
                return f"the row vector {', '.join(cells[0])},"
            if kind == "matrix" and nrows == 1 and ncols == 1:
                return f"the one by one matrix {cells[0][0]},"
            ords = ["first", "second", "third", "fourth", "fifth", "sixth", "seventh", "eighth"]
            parts = []
            for idx, r in enumerate(cells):
                label = ords[idx] if idx < len(ords) else f"row {idx + 1}"
                parts.append(f"{label} row {', '.join(r)}")
            if len(parts) > 1:
                joined = ", ".join(parts[:-1]) + ", and " + parts[-1]
            else:
                joined = parts[0]
            size = f"{int_words(nrows)} by {int_words(ncols)}"
            if kind == "determinant":
                return f"the {size} determinant with {joined},"
            return f"the {size} matrix with {joined},"
        if name in ("cases",):
            parts = []
            for r in rows:
                parts.append(" ".join(self.row(c) for c in r if c))
            return "cases, " + ", or, ".join(parts) + ","
        # aligned / align / gather / split / equation / eqnarray ...
        parts = []
        for r in rows:
            line = " ".join(self.row(c) for c in r if c)
            if line:
                parts.append(line)
        return ", ".join(parts)


_NOBLE_CORE = {"A R": "argon", "N E": "neon", "H E": "helium", "K R": "krypton", "X E": "xenon", "R N": "radon",
               "argon": "argon", "neon": "neon", "helium": "helium", "krypton": "krypton", "xenon": "xenon",
               "radon": "radon"}


def _conc_node(x) -> bool:
    """A node that can stand inside [ ] for a concentration: [HA], [A^-], [\\ce{H+}], [\\mathrm{OH^-}]."""
    if x[0] == "ce":
        return True
    if x[0] == "mathrm":
        return bool(re.match(r"[A-Z(]", x[1].strip()))
    if x[0] == "var":
        return x[1].isupper()
    if x[0] == "script":
        return _conc_node(x[1]) and (x[2] is None or all(n[0] in ("num", "var", "op") for n in x[2]))
    if x[0] == "group":
        return all(_conc_node(n) for n in x[1]) and bool(x[1])
    return False


def _next_is_script(nxt) -> bool:
    return nxt is not None and nxt[0] == "script"


def _camel_words(name: str) -> str:
    return re.sub(r"(?<=[a-z])(?=[A-Z])", " ", name).lower()


def _fallback_char(ch: str) -> str:
    """A character with no table entry: its unicode name if known (reported), nothing for junk."""
    cat = unicodedata.category(ch)
    if cat in ("Mn", "Me", "Cf", "Cc", "Zs", "Zl", "Zp"):
        return ""
    if ch in "\\{}^_$":
        return ""
    o = ord(ch)
    if o in range(0xF0E6, 0xF0E9) or o in range(0xF0F6, 0xF0F9) or o in range(0xF8EB, 0xF8FF):
        return ""  # Symbol-font pieces of a tall bracket: the bracket itself is spoken elsewhere
    if o == 0xF0DE:
        return "implies"  # Symbol-font double arrow
    if cat == "Co" or cat == "Cn" or cat == "Cs":
        _gap(f"U+{ord(ch):04X}")
        return ""
    name = unicodedata.name(ch, "")
    if cat in ("So", "Sk") and ord(ch) >= 0x1F000 or cat == "So" and 0x2600 <= ord(ch) <= 0x27BF:
        return ""  # decorative symbols and emoji are not spoken
    if name:
        _gap(ch)
        return name.lower().replace("-", " ")
    _gap(f"U+{ord(ch):04X}")
    return ""


def _charge_of(sup: list) -> tuple[int, str] | None:
    """A superscript that is a charge: [+] [-] [2,+] [3,-] -> (magnitude, '+'|'-')."""
    s = [n for n in sup if n[0] != "sep"]
    if len(s) == 1 and s[0] in (("op", "+"), ("op", "-"), ("op", "−")):
        return (1, "+" if s[0][1] == "+" else "-")
    if len(s) == 2 and s[0][0] == "num" and s[0][1].isdigit() and s[1] in (("op", "+"), ("op", "-"), ("op", "−")):
        return (int(s[0][1]), "+" if s[1][1] == "+" else "-")
    return None


def mass_words(m: int) -> str:
    """Mass number: 14 -> 'fourteen'; 235 -> 'two three five' (three digits are read digit by digit)."""
    return _digits(str(m)) if m >= 100 else int_words(m)


def charge_words(mag: int, sign: str) -> str:
    word = "plus" if sign == "+" else "minus"
    return word if mag == 1 else f"{int_words(mag)} {word}"


def ion_words(sym: str, ch: tuple[int, str], sub=None) -> str:
    mag, sign = ch
    if sign == "-" and sym in _ANION and mag == (2 if sym in ("O", "S") else 1):
        return _ANION[sym]
    if sym in ELEMENT_NAME and sym not in ("H",) and sym.lower() != "e":
        name = ELEMENT_NAME[sym]
    else:
        name = _spell_symbols(sym)
    return f"{name} {charge_words(mag, sign)}"


def _spell_symbols(sym: str) -> str:
    return " ".join(c.upper() if c.isalpha() else c for c in sym)


# --------------------------------------------------------------------------------------------------
# \mathrm{..} and \text{..} contents
# --------------------------------------------------------------------------------------------------

_RE_FORMULA = re.compile(r"(?:[A-Z][a-z]?\d*|\((?:[A-Z][a-z]?\d*)+\)\d*|\[(?:[A-Z][a-z]?\d*|\((?:[A-Z][a-z]?\d*)+\)\d*)+\]\d*)+")


def _all_elements(formula: str) -> bool:
    return all(sym in ELEMENT_NAME for sym in re.findall(r"[A-Z][a-z]?", formula))


def mathrm_words(raw: str, say: "_Say | None", prev, nxt=None) -> str:
    raw = raw.strip()
    if not raw:
        return ""
    # a unit with a number before it is merged earlier; here: names, symbols, formulas
    run = _parse_units_latex(raw)
    if run is not None and (len(run) > 1 or len(run[0][0]) >= 2 or run[0][0] in _SINGLE_SAFE or _numlike(prev)):
        plural = not (prev is not None and prev[0] == "num" and _is_one(prev[1]))
        return units_words(run, plural)
    flat = raw.replace("\\,", "").replace("\\ ", "").replace("{", "").replace("}", "")
    flat = re.sub(r"_(\w)", r"\1", flat)
    flat = re.sub(r"\^(\w+)([+-])?", lambda m: "^{" + m.group(1) + (m.group(2) or "") + "}" if m.group(2) else "^" + m.group(1), flat)
    if re.fullmatch(r"\^?\{?[A-Za-z0-9+\-^]+\}?", flat) and _RE_FORMULA.fullmatch(re.sub(r"\^\{?[0-9]*[+-]\}?", "", flat)) \
            and _all_elements(flat) and (re.search(r"\d|\^|[+-]", flat) or flat in ELEMENT_NAME):
        return chem_words(flat)
    if raw in _OPERATORNAMES:
        w = _OPERATORNAMES[raw]
        return w if (nxt is not None and nxt[0] in ("paren", "var", "script", "num")) else w.replace(" of", "").replace("the ", "")
    if re.fullmatch(r"[A-Za-z]", raw):
        return raw
    if raw.isalpha():
        low = raw.lower()
        return low if raw[0].isupper() and not raw.isupper() else _spaced_if_caps(raw)
    return text_words(raw)


def _spaced_if_caps(w: str) -> str:
    return " ".join(w) if w.isupper() and 2 <= len(w) <= 4 else w


def text_words(raw: str) -> str:
    """The inside of \\text{...}: a unit, a state, or plain words."""
    raw = raw.strip()
    if not raw:
        return ""
    run = _parse_units_latex(raw)
    if run is not None and (len(run) > 1 or len(run[0][0]) >= 2 or run[0][0] in _SINGLE_SAFE):
        return units_words(run)
    return prose_words(raw.replace("\\,", " ").replace("\\ ", " ").replace("~", " "))


# --------------------------------------------------------------------------------------------------
# Chemistry
# --------------------------------------------------------------------------------------------------

_STATE_WORD = {"s": "solid", "l": "liquid", "g": "gas", "aq": "aqueous", "cr": "crystalline", "conc": "concentrated",
               "dil": "dilute", "sol": "solution", "alc": "alcoholic", "ppt": "precipitate", "am": "amorphous",
               "graphite": "graphite", "diamond": "diamond", "excess": "in excess", "mol": "molten",
               "ethanol": "in ethanol", "ether": "in ether"}
_CE_ARROWS = (("<=>>", "is in equilibrium with"), ("<<=>", "is in equilibrium with"), ("<=>", "is in equilibrium with"),
              ("<->", "is in resonance with"), ("-->", "yields"), ("->", "yields"), ("<-", "comes from"),
              ("=>", "yields"))


def _states(text: str) -> str:
    parts = [p.strip() for p in text.split(",")]
    return ", ".join(_STATE_WORD.get(p, p) for p in parts if p)


def _formula_words(f: str) -> str:
    """A formula (no coefficient, no charge): 'CH3CO2H' -> 'C H three C O two H'."""
    out: list[str] = []
    i = 0
    while i < len(f):
        c = f[i]
        if c.isupper():
            sym = c
            if i + 1 < len(f) and f[i + 1].islower():
                sym += f[i + 1]
                i += 1
            out.append(" ".join(ch.upper() for ch in sym))
        elif c.isdigit():
            j = i
            while j < len(f) and f[j].isdigit():
                j += 1
            out.append(int_words(int(f[i:j])))
            i = j - 1
        elif c == "(":
            out.append("open bracket")
        elif c == ")":
            out.append("close bracket")
        elif c == "[":
            out.append("open square bracket")
        elif c == "]":
            out.append("close square bracket")
        elif c == "-" or c == "–":
            out.append("")
        elif c == "+":
            out.append("plus")
        elif c in "'′":
            out.append("prime")
        elif c == "=":
            out.append("double bond")
        elif c == "#":
            out.append("triple bond")
        elif c in ".·*∙•":
            out.append("dot")
        elif c.islower():
            out.append(c)  # a stray lower-case letter (e.g. a ligand abbreviation)
        elif c not in ", ":
            _gap(c)
        i += 1
    return " ".join(x for x in out if x)


_RE_CE_CHARGE = re.compile(r"\^\{?\s*(\d*|[A-Za-z]|\([^()]*\))\s*([+\-−]|\\bullet|\\cdot|\\circ|•)\s*\}?\s*$")
_RE_CE_ISO = re.compile(r"^\^\{?(\d+)\}?(?:_\{?(-?\d+)\}?)?\s*(.*)$")


def _species_words(tok: str) -> str:
    """One species: '2NO', 'Cu^2+', 'SO4^{2-}', 'H2O(l)', 'e-', '^{14}_{6}C', 'CuSO4.5H2O', '1/2O2'."""
    tok = tok.strip()
    if not tok:
        return ""
    mcore = re.fullmatch(r"\[(He|Ne|Ar|Kr|Xe|Rn)\]", tok)
    if mcore:
        return "the " + ELEMENT_NAME[mcore.group(1)] + " core"
    # trailing state(s): H2O(l), Ag+(aq), C(s, graphite)
    state = ""
    m = re.search(r"\(\s*(s|l|g|aq|cr|conc|dil|sol|alc|ppt|am|mol|[a-z]+(?:\s*,\s*[a-z]+)*)\s*\)\s*$", tok)
    if m and m.start() > 0 and (m.group(1) in _STATE_WORD or "," in m.group(1)):
        state = _states(m.group(1))
        tok = tok[:m.start()]
    for ch, w in _VULGAR.items():
        if tok.startswith(ch):
            return _join(w, _species_words(tok[1:]), "") if len(tok) > 1 else w
    # leading coefficient: 2, 0.5, 1/2, \frac{1}{2}
    coef = ""
    mc = re.match(r"^(\\frac\{(\d+)\}\{(\d+)\}|(\d+)\s*/\s*(\d+)|\d+(?:\.\d+)?)\s*", tok)
    if mc:
        rest = tok[mc.end():]
        if rest and not rest[0].isdigit():
            a = mc.group(2) or mc.group(4)
            b = mc.group(3) or mc.group(5)
            if a and b:
                coef = fraction_words(int(a), int(b)) or f"{int_words(int(a))} over {int_words(int(b))}"
            else:
                coef = number_words(mc.group(1))
            tok = rest
    # electron
    if tok in ("e-", "e^-", "e^{-}", "e−", "e⁻"):
        if coef:
            return (coef + " electrons" if coef not in ("one",) else "an electron") + (" " + state if state else "")
        return "an electron"
    # nuclide / isotope prefix
    mi = _RE_CE_ISO.match(tok)
    if mi:
        mass, z, rest = int(mi.group(1)), mi.group(2), mi.group(3).strip()
        mm = re.match(r"([A-Z][a-z]?)$", rest)
        if mm and mm.group(1) in ELEMENT_NAME:
            out = f"{ELEMENT_NAME[mm.group(1)]} {mass_words(mass)}"
            if z is not None:
                out += f", atomic number {int_words(int(z))},"
            return _join(coef, out, state)
        if rest in ("e", "n", "p", "\\alpha", "α", "\\beta", "β", "\\gamma", "γ"):
            word = {"e": "an electron" if z == "-1" else "a positron", "n": "a neutron", "p": "a proton",
                    "\\alpha": "an alpha particle", "α": "an alpha particle", "\\beta": "a beta particle",
                    "β": "a beta particle", "\\gamma": "a gamma ray", "γ": "a gamma ray"}[rest]
            return _join(coef, word, state)
    # charge
    charge = ""
    mch = _RE_CE_CHARGE.search(tok)
    if mch and mch.start() > 0:
        sign = mch.group(2)
        if sign in ("+", "-", "−") and mch.group(1).startswith("("):
            charge = f"{speak_math(mch.group(1))} {'plus' if sign == '+' else 'minus'}"
        elif sign in ("+", "-", "−") and mch.group(1).isalpha():
            charge = f"{mch.group(1)} {'plus' if sign == '+' else 'minus'}"
        elif sign in ("+", "-", "−"):
            charge = charge_words(int(mch.group(1) or 1), "+" if sign == "+" else "-")
        else:
            charge = "radical"
        tok = tok[:mch.start()]
    else:
        mch = re.search(r"(?<=[A-Za-z\d)\]])(\d*)([+\-−])$", tok)
        if mch and tok != mch.group():
            charge = charge_words(int(mch.group(1) or 1), "+" if mch.group(2) == "+" else "-")
            tok = tok[:mch.start()]
        elif tok.endswith("•") or tok.endswith("·") and len(tok) > 1:
            charge = "radical"
            tok = tok[:-1]
    core = tok.replace("\\ ", "").strip()
    # a lone element: its name (cation: 'copper two plus', anion: 'chloride')
    if core in ELEMENT_NAME and not state.startswith("zz"):
        if charge:
            mag_sign = _parse_charge_words(charge)
            if mag_sign:
                return _join(coef, ion_words(core, mag_sign), state)
            return _join(coef, f"{ELEMENT_NAME[core]} {charge}", state)
        return _join(coef, ELEMENT_NAME[core] if len(core) == 2 or core not in "HCNOFPSKIVWUBY" else core, state)
    body = _formula_words(core)
    if charge:
        body = f"{body} {charge}"
    return _join(coef, body, state)


_VULGAR = {"½": "one half", "¼": "one quarter", "¾": "three quarters", "⅓": "one third", "⅔": "two thirds"}


def _parse_charge_words(w: str) -> tuple[int, str] | None:
    if w == "plus":
        return (1, "+")
    if w == "minus":
        return (1, "-")
    m = re.fullmatch(r"([a-z]+) (plus|minus)", w)
    if m:
        for n in range(2, 9):
            if int_words(n) == m.group(1):
                return (n, "+" if m.group(2) == "plus" else "-")
    return None


def _join(*parts: str) -> str:
    return " ".join(p for p in parts if p)


@functools.lru_cache(maxsize=4096)
def chem_words(body: str) -> str:
    """The inside of \\ce{...}: '2NO + O2 -> 2NO2' -> 'two N O plus O two yields two N O two'."""
    s = body.strip()
    s = s.replace("\\,", " ").replace("\\ ", " ").replace("~", " ")
    s = re.sub(r"\\(?:mathrm|text|ce)\s*\{([^{}]*)\}", r"\1", s)
    s = re.sub(r"(?<=[A-Za-z)\]])_\{([^{}]*)\}", r"\1", s)
    s = re.sub(r"(?<=[A-Za-z)\]])_([A-Za-z0-9])", r"\1", s)
    # arrows with labels: ->[text][text]
    pieces: list[str] = []
    pos = 0
    arrow_re = re.compile(r"(<=>>|<<=>|<=>|<->|-->|->|<-|=>)(?:\[([^\]]*)\])?(?:\[([^\]]*)\])?")
    segments: list[tuple[str, str | None]] = []
    for m in arrow_re.finditer(s):
        # an arrow needs a species or space on its left (not the '-' of a bond like C-C>)
        segments.append((s[pos:m.start()], None))
        word = dict(_CE_ARROWS)[m.group(1)]
        labels = [x for x in (m.group(2), m.group(3)) if x and x.strip()]
        if labels:
            lab = ", ".join(_label_words(x) for x in labels)
            word = f"{word}, with {lab},"
        segments.append((word, "arrow"))
        pos = m.end()
    segments.append((s[pos:], None))
    for text, kind in segments:
        if kind == "arrow":
            pieces.append(text)
            continue
        pieces.append(_ce_side(text))
    return _tidy(" ".join(p for p in pieces if p))


def _label_words(x: str) -> str:
    x = x.strip()
    if x in ("\\Delta", "Delta", "Δ"):
        return "heat"
    x = re.sub(r"\\(?:text|mathrm)\s*\{([^{}]*)\}", r"\1", x)
    if re.fullmatch(r"[A-Za-z ]+", x) and not re.fullmatch(r"[A-Z][A-Za-z]*\d.*", x):
        return x.lower() if x.islower() or not x.isupper() else _spell_symbols(x)
    return chem_words(x) if re.search(r"[A-Z]", x) else prose_words(x)


def _ce_side(text: str) -> str:
    text = text.strip()
    if not text:
        return ""
    # a state with a note, "(s, graphite)", is one token
    text = re.sub(r"\([^()]*,[^()]*\)", lambda mm: mm.group().replace(" ", "\x00"), text)
    # protect ^{...} and _{...} groups from whitespace splitting, then split on spaces
    toks: list[str] = []
    cur: list[str] = []
    depth = 0
    for ch in text:
        if ch in "{([" and ch == "{":
            depth += 1
        elif ch == "}":
            depth = max(0, depth - 1)
        if ch.isspace() and depth == 0:
            if cur:
                toks.append("".join(cur))
                cur = []
        else:
            cur.append(ch)
    if cur:
        toks.append("".join(cur))
    toks = [t.replace("\x00", " ") for t in toks]
    out: list[str] = []
    k = 0
    while k < len(toks):
        t = toks[k]
        if t == "+":
            out.append("plus")
        elif t in ("-", "−", "–"):
            out.append("minus")
        elif t == "=":
            out.append("equals")
        elif t in ("<", ">", "≈", "≠"):
            out.append({"<": "is less than", ">": "is greater than", "≈": "is approximately", "≠": "is not equal to"}[t])
        elif t in ("v", "^", "\\uparrow", "\\downarrow"):
            out.append({"v": "precipitate", "^": "gas given off"}.get(t, "up" if t == "\\uparrow" else "down"))
        elif re.fullmatch(r"\((s|l|g|aq|cr|conc|dil|sol|alc|ppt|am|mol)\)", t) or (
                t.startswith("(") and t.endswith(")") and "," in t and all(p.strip() in _STATE_WORD or p.strip().isalpha()
                                                                           for p in t[1:-1].split(","))):
            out.append(_states(t[1:-1]))
        elif t.startswith("\\") and t.strip("\\") in ("Delta",):
            out.append("heat")
        else:
            out.append(_species_words(_sup_unicode_to_ascii(t)))
        k += 1
    return " ".join(x for x in out if x)


def _sup_unicode_to_ascii(t: str) -> str:
    t = _RE_SUPRUN.sub(lambda m: "^{" + "".join(_SUP_MAP[c] for c in m.group()) + "}", t)
    t = _RE_SUBRUN.sub(lambda m: "".join(_SUB_MAP[c] for c in m.group()), t)
    t = re.sub(r"\{\}", "", t)
    t = t.replace("\\bullet", "•").replace("\\cdot", "·")
    return t


# --------------------------------------------------------------------------------------------------
# Public maths entry point
# --------------------------------------------------------------------------------------------------


@functools.lru_cache(maxsize=8192)
def _speak_math_cached(tex: str) -> tuple[str, tuple[str, ...]]:
    prev = getattr(_TLS, "gaps", None)
    _TLS.gaps = []
    try:
        try:
            tree = _Parser(_repair(tex)).row()
            words = _Say().row(tree)
        except RecursionError:  # pragma: no cover - absurdly nested input
            _gap("deeply nested maths")
            words = ""
        gaps = tuple(_TLS.gaps)
    finally:
        _TLS.gaps = prev
    return words, gaps


def speak_math(tex: str) -> str:
    """LaTeX maths (without the dollar signs) -> spoken words.  Never raises."""
    words, gaps = _speak_math_cached(tex)
    for g in gaps:
        _gap(g)
    return words


# --------------------------------------------------------------------------------------------------
# Prose
# --------------------------------------------------------------------------------------------------

_ABBREV = [  # (regex, replacement); applied to prose before anything else
    (re.compile(r"\bi\.\s?e\.,?", re.I), "that is,"),
    (re.compile(r"\be\.\s?g\.,?", re.I), "for example,"),
    (re.compile(r"\bs\.\s?f\.(?=\W|$)", re.I), "significant figures"),
    (re.compile(r"\bd\.\s?p\.(?=\W|$)"), "decimal places"),
    (re.compile(r"\bs\.\s?f\b(?!\.)"), "significant figures"),
    (re.compile(r"\bcf\.?(?=\s)"), "compare"),
    (re.compile(r"\betc\.(?=\s+[A-Z]|\s*$)"), "and so on."),
    (re.compile(r"\betc\.?"), "and so on"),
    (re.compile(r"\bvs\.?(?=\s)"), "versus"),
    (re.compile(r"\bviz\.?"), "namely"),
    (re.compile(r"\bapprox\.(?=\s)"), "approximately"),
    (re.compile(r"\bca\.(?=\s)"), "about"),
    (re.compile(r"\bFig\.\s?(?=\d)"), "figure "),
    (re.compile(r"\bFigs\.\s?(?=\d)"), "figures "),
    (re.compile(r"\beqn?s?\.\s?(?=\d)", re.I), "equation "),
    (re.compile(r"\bNo\.\s?(?=\d)"), "number "),
    (re.compile(r"\bp\.d\.(?=\W|$)"), "potential difference"),
    (re.compile(r"\be\.m\.f\.?"), "E M F"),
    (re.compile(r"\br\.m\.s\.?"), "R M S"),
    (re.compile(r"\ba\.c\.(?=\W|$)"), "A C"),
    (re.compile(r"\bd\.c\.(?=\W|$)"), "D C"),
    (re.compile(r"\bp\.m\."), "P M"),
    (re.compile(r"\ba\.m\."), "A M"),
    (re.compile(r"\bw\.r\.t\.?"), "with respect to"),
    (re.compile(r"\bi\.\s?r\.?(?=\W|$)"), "I R"),
    (re.compile(r"\bQ\.?E\.?D\.?"), "Q E D"),
    (re.compile(r"\bR\.?T\.?P\.?(?=\W|$)"), "R T P"),
    (re.compile(r"\bS\.?T\.?P\.?(?=\W|$)"), "S T P"),
    (re.compile(r"\bAr\b(?=\s*(?:=|of\b|values?\b))"), "A r"),
    (re.compile(r"\bMr\b(?!\.)"), "M r"),
    (re.compile(r"\bpH\b"), "p H"),
    (re.compile(r"\bpOH\b"), "p O H"),
    (re.compile(r"\bp(K[a-z]{1,2})\b"), lambda m: "p " + " ".join(m.group(1))),
    (re.compile(r"\b(K)(c|p|a|b|w|sp|stab|d|f)\b"), lambda m: "K " + " ".join(m.group(2))),
    (re.compile(r"\bE(cell|ocell)\b"), lambda m: "E cell"),
    (re.compile(r"\bsin\b(?=\s?[\d(α-ωΑ-Ωa-z⁻²]|\s*$)"), "sine"),
    (re.compile(r"\bcos\b(?=\s?[\d(α-ωΑ-Ωa-z⁻²]|\s*$)"), "cosine"),
    (re.compile(r"\btan\b(?=\s?[\d(α-ωΑ-Ωa-z⁻²]|\s*$)"), "tangent"),
    (re.compile(r"\b(NO|SO)x\b"), lambda m: " ".join(m.group(1)) + " x"),
    (re.compile(r"\bCAIE\b"), "C A I E"),
    (re.compile(r"\bIAL\b"), "I A L"),
    (re.compile(r"\bHPLC\b"), "H P L C"),
]
_ACRONYM_OK = {"NOT", "AND", "OR", "ALL", "ONLY", "NEVER", "ALWAYS", "ANY", "THE", "FOR", "ARE", "ONE", "TWO",
               "YES", "WHY", "HOW", "WHAT", "WITH", "FROM", "THAT", "THIS", "NASA", "OK", "IF", "TO",
               "OF", "IN", "ON", "AT", "BY", "AS", "IS", "IT", "BE", "OR", "DO", "GO", "UP", "US", "WE", "AM",
               "AN", "HE", "ME", "MY", "A", "I", "AS"}
_NON_ELEMENT_WORDS = {"He", "No", "As", "Be", "In", "At", "Am", "Ho", "Os", "Re"}

_LONE_UNITS = {"Hz", "kHz", "MHz", "GHz", "Pa", "kPa", "MPa", "GPa", "hPa", "eV", "keV", "MeV", "GeV", "TeV", "kg", "mg",
               "μg", "mol", "mmol", "kJ", "MJ", "mJ", "cm", "mm", "km", "nm", "pm", "μm", "ms", "μs", "ns", "mA", "μA",
               "kW", "MW", "mW", "kV", "mV", "μF", "nF", "pF", "kΩ", "MΩ", "mL", "μL", "dm", "kN", "mN", "kBq", "MBq",
               "Wb", "Bq", "dB", "rpm", "ppm"}
_RE_URLISH = re.compile(r"https?://\S+")
_RE_SIGN_BEFORE = r"(?P<sign>(?:(?<=[\s(\[=,;:/])|(?<=^))[+−–\-](?=\d|\.\d))?"
_RE_NUM = (r"(?P<n>\d{1,3}(?:,\d{3})+(?![\d])|\d{1,3}(?: \d{3})+(?![\d])|\d+(?:\.\d+)+|\d+(?:·\d+)?|\.\d+)")
_RE_TIMES10 = (r"(?P<mul>\s*[×x]\s*10(?P<e>[⁻⁺−]?[⁰¹²³⁴⁵⁶⁷⁸⁹]+|\^\{?[-−+]?\d+\}?|\^\([-−+]?\d+\)))")
_RE_NUMBER = re.compile(r"(?<![\w.\u00B2\u00B3\u00B9\u2070-\u209F])(?<!\S·)" + _RE_SIGN_BEFORE + _RE_NUM + r"(?:" + _RE_TIMES10 + r")?")
_RE_SUPEXP = re.compile(r"([⁻⁺−]?)([⁰¹²³⁴⁵⁶⁷⁸⁹]+)")
_UNIT_SYM_RE = re.compile(r"[A-Za-zμµΩÅ°%‰]+")
_RE_EXP_AFTER = re.compile(r"^(?:\^\{?\s*([-−+]?)(\d+)\s*\}?|\^\(\s*([-−+]?)(\d+)\s*\))")
_RE_ASCII_EXP_OK = {"cm", "dm", "mm", "km", "nm", "pm", "μm", "m"}
_JOIN_PAIRS = {("N", "m"), ("N", "s"), ("kg", "m"), ("W", "h"), ("kW", "h"), ("MW", "h"), ("A", "s"), ("A", "h"),
               ("V", "m"), ("J", "s")}
_COMMON_SPLIT = {"kJ", "J", "mol", "K", "kg", "g", "m", "s", "dm", "cm", "N", "W", "V", "A", "Pa", "kPa", "Hz", "C",
                 "L", "eV", "mm", "km"}


def _sup_to_int(sign: str, digits: str) -> int:
    v = int("".join(_SUP_MAP[c] for c in digits))
    return -v if sign in ("⁻", "−", "-") else v


def _unit_symbol_at(s: str, i: int, allow_ascii_exp: bool = True):
    """One unit symbol with its exponent starting at s[i]: (sym, exp, end) or None."""
    m = _UNIT_SYM_RE.match(s, i)
    if not m:
        return None
    word = m.group()
    end = m.end()
    cands = [word]
    # a glued pair: kJmol, kgm
    for cut in range(1, len(word)):
        a, b = word[:cut], word[cut:]
        if a in _COMMON_SPLIT and b in _COMMON_SPLIT and unit_lookup(a) and unit_lookup(b) and (len(a) > 1 or len(b) > 1):
            cands.append(a)
    sym = None
    for c in cands:
        if unit_lookup(c) is not None and (len(c) >= 2 or c in _ONE_LETTER_PLAIN or c in ("°", "%", "Ω", "Å", "‰")):
            sym = c
            break
    if sym is None:
        return None
    end = i + len(sym)
    if sym != word and not (word[len(sym):] and unit_lookup(word[len(sym):])):
        return None
    exp = 1
    rest = s[end:]
    me = _RE_SUPEXP.match(rest)
    if me:
        exp = _sup_to_int(me.group(1), me.group(2))
        end += me.end()
    else:
        mx = _RE_EXP_AFTER.match(rest)
        if mx:
            exp = int((mx.group(1) or mx.group(3) or "") .replace("−", "-") + (mx.group(2) or mx.group(4)) or 1)
            end += mx.end()
        elif allow_ascii_exp:
            ma = re.match(r"(-?\d)(?![\d.])", rest)
            if ma and sym in _RE_ASCII_EXP_OK and (ma.group(1).startswith("-") or len(sym) >= 2):
                exp = int(ma.group(1))
                end += ma.end()
    return sym, exp, end


def _units_after(s: str, i: int):
    """The unit expression after a number at s[i:] (one optional space allowed): ([(sym, exp)...], end) or None."""
    j = i
    if j < len(s) and s[j] in " \u00a0\u2009\u202f":
        j += 1
    first = _unit_symbol_at(s, j)
    if first is None:
        return None
    run = [(first[0], first[1])]
    end = first[2]
    # degree sign then C/F: 25 °C or 25°C
    if first[0] == "°" and end < len(s) and s[end] in "CF" and not (end + 1 < len(s) and s[end + 1].isalpha()):
        run = [("°" + s[end], 1)]
        end += 1
    denominator = False
    prev_sym, prev_exp = run[-1]
    while True:
        k = end
        sep = ""
        if k < len(s) and s[k] in "·⋅.":
            if s[k] == "." and not (k + 1 < len(s) and s[k + 1].isalpha()):
                break
            sep, k = "dot", k + 1
        elif k < len(s) and s[k] == "/":
            sep, k = "div", k + 1
            denominator = True
        elif k < len(s) and s[k] in " \u00a0\u2009\u202f":
            sep, k = "space", k + 1
        else:
            break
        paren = False
        if k < len(s) and s[k] == "(" and denominator:
            paren, k = True, k + 1
        nxt = _unit_symbol_at(s, k)
        if nxt is None:
            break
        sym, exp, e2 = nxt
        if sep == "space" and not (exp != 1 or prev_exp != 1 or (prev_sym, sym) in _JOIN_PAIRS):
            break
        if sep == "space" and sym in ("u", "h", "M", "S") and exp == 1 and prev_exp == 1 and (prev_sym, sym) not in _JOIN_PAIRS:
            break
        run.append((sym, -abs(exp) if denominator else exp))
        end = e2
        prev_sym, prev_exp = sym, exp
        if paren:
            while end < len(s) and s[end] != ")":
                more = _unit_symbol_at(s, end + (1 if s[end] in " ·" else 0))
                if more is None:
                    break
                run.append((more[0], -abs(more[1])))
                end = more[2]
            if end < len(s) and s[end] == ")":
                end += 1
            denominator = False
    # the symbol run must stop at a word boundary
    if end < len(s) and (s[end].isalnum() or s[end] in "_" ) and not s[end].isspace():
        return None
    if end < len(s) and s[end] in "₀₁₂₃₄₅₆₇₈₉⁺⁻(":
        return None
    if i < len(s) and s[i] not in " \u00a0\u2009\u202f" and len(run) == 1 and run[0][0] in ("H", "C", "F", "S", "M", "T", "L", "u", "h"):
        return None
    return run, end


def _number_phrase(m: "re.Match[str]", s: str) -> tuple[str, int]:
    """Words for a number match (sign, ×10^n, unit run) and where the consumed text ends."""
    n = m.group("n")
    sign = m.group("sign")
    n_clean = n.replace("·", ".")
    words = number_words(n_clean)
    value_is_one = n_clean in ("1",)
    if sign:
        words = ("minus " if sign in "−–-" else "plus ") + words
    end = m.end()
    mul = m.group("mul")
    if mul:
        e = m.group("e")
        if e[0] in "⁻⁺−⁰¹²³⁴⁵⁶⁷⁸⁹":
            sg = e[0] if e[0] in "⁻⁺−" else ""
            digits = e[1:] if sg else e
            ev = _sup_to_int(sg, digits)
        else:
            mm = re.search(r"([-−+]?)(\d+)", e)
            ev = int(("-" if mm.group(1) in ("-", "−") else "") + mm.group(2))
        words += " times ten to the " + ("minus " + int_words(-ev) if ev < 0 else int_words(ev))
        value_is_one = False
    me = None if mul else _RE_SUPEXP.match(s, end)
    if me and not sign and n_clean.replace(".", "").isdigit():
        exp_tex = ("-" if me.group(1) in ("⁻", "−") else "") + "".join(_SUP_MAP[c] for c in me.group(2))
        return speak_math(n_clean + "^{" + exp_tex + "}"), me.end()
    orbital = bool(n_clean.isdigit() and 1 <= int(n_clean) <= 7 and re.match(r"[spdf](?![A-Za-z])", s[end:end + 2]))
    got = None if orbital else _units_after(s, end)
    if got is not None:
        run, uend = got
        words += " " + units_words(run, plural=not value_is_one)
        end = uend
    return words, end


_RE_RANGE_TAIL = re.compile(r"[–\-−]" + _RE_NUM)


def _convert_numbers(s: str) -> str:
    out: list[str] = []
    pos = 0
    for m in _RE_NUMBER.finditer(s):
        if m.start() < pos:
            continue
        # skip when the digits are glued to letters on the right (H2O, x2): treated elsewhere
        words, end = _number_phrase(m, s)
        # a range: 3–5 (no spaces) -> three to five, sharing the unit
        mr = _RE_RANGE_TAIL.match(s, end)
        if mr and not m.group("mul"):
            m2 = _RE_NUMBER.match(s, end + 1)
            if m2 and m2.start() == end + 1 and not m2.group("sign"):
                # first number without its unit, second with it
                first_words = words
                w2, end2 = _number_phrase(m2, s)
                # when the unit followed the first number, keep it on the first only if there is one
                first_unit = _units_after(s, m.end())
                if first_unit is None:
                    words = first_words + " to " + w2
                    end = end2
        out.append(s[pos:m.start()])
        # a number glued to a following letter (2x, 3A handled above): keep a space
        nxt = s[end:end + 1]
        out.append(" " + words + (" " if nxt.isalpha() else ""))
        pos = end
    out.append(s[pos:])
    return "".join(out)


_RE_BARE_START = re.compile(r"(?<![\w.])(?=[A-Za-zμΩÅ°])")


def _convert_bare_units(s: str) -> str:
    """Unit expressions with an exponent but no number in front: 'kJ mol⁻¹', 'v / m s⁻¹', 'dm³'."""
    out: list[str] = []
    pos = 0
    n = len(s)
    i = 0
    while i < n:
        c = s[i]
        if (c.isalpha() or c in "μΩÅ") and (i == 0 or not (s[i - 1].isalnum() or s[i - 1] in "_.")):
            j = i
            while j < n and (s[j].isalpha() or s[j] in "μΩÅ"):
                j += 1
            near_exp = j < n and (s[j] in "⁻⁰¹²³⁴⁵⁶⁷⁸⁹^" or (
                s[j] == " " and re.match(r"[A-Za-zμΩ]+(?:[⁻⁰¹²³⁴⁵⁶⁷⁸⁹]|\^)", s[j + 1:j + 8])))
            if near_exp:
                got = _units_after_strict(s, i)
                if got is not None:
                    run, end = got
                    if any(e < 0 for _, e in run) or any(len(sym) >= 2 and abs(e) != 1 for sym, e in run):
                        pre = s[pos:i]
                        m = re.search(r"\s/\s$", pre)
                        if m:
                            pre = pre[:m.start()] + " in "
                        out.append(pre + " " + units_words(run, plural=True) + " ")
                        pos = i = end
                        continue
            i = max(j, i + 1)
            continue
        i += 1
    out.append(s[pos:])
    return "".join(out)


def _units_after_strict(s: str, i: int):
    """The unit run that starts exactly at s[i] (no leading space): (run, end) or None."""
    got = _units_after(" " + s[i:], 0)
    if got is None:
        return None
    run, end = got
    return run, i + end - 1


_MONTHS = {"jan": "January", "feb": "February", "mar": "March", "apr": "April", "may": "May", "jun": "June", "jul": "July",
           "aug": "August", "sep": "September", "sept": "September", "oct": "October", "nov": "November", "dec": "December"}
_MONTH_RE = ("January|February|March|April|May|June|July|August|September|October|November|December"
             "|Jan|Feb|Mar|Apr|Jun|Jul|Aug|Sept|Sep|Oct|Nov|Dec")
# a four-digit 1900-2099 is read as a year only after a month name, 'in', 'since' or 'during'
_RE_WORD_PREFIX = re.compile(r"\b((?i:in|since|during)|" + _MONTH_RE + r")\.?\s+(19[0-9]{2}|20[0-9]{2})\b(?![\d.,]*\s*[°%])")
_RE_UNIT_WORD_AFTER = re.compile(r"\s*([A-Za-zμΩ]+)\b")
_RE_ORDINAL = re.compile(r"\b(\d+)(st|nd|rd|th)\b")


def _ordinal_words(n: int) -> str:
    if n in _ORD:
        return _ORD[n]
    base = int_words(n)
    if n % 100 in range(11, 14):
        return base + "th"
    tail = {1: "first", 2: "second", 3: "third"}.get(n % 10)
    if n % 10 in (1, 2, 3) and n >= 20:
        head = int_words(n - n % 10)
        return head + " " + tail
    if base.endswith("y"):
        return base[:-1] + "ieth"
    return base + "th"


# Greek letters in prose and the chars treated as "standard state" marks
_STD = "⦵⊖ø○°⁰ᵒ"
_RE_DELTA = re.compile(r"^([ΔδΣ∆])([A-Za-z])([a-z]{0,6})?(?:[(\[]([^()]*)[)\]])?([" + _STD + r"]|\^\\circ|\^o)?$")
_RE_E_STD = re.compile(r"^([EGHSK])([" + _STD + r"])$")
_DELTA_SUB = {"f": "f", "c": "c", "r": "r", "atom": "atomisation", "sol": "solution", "hyd": "hydration",
              "lat": "lattice", "vap": "vaporisation", "fus": "fusion", "neut": "neutralisation", "comb": "combustion"}
_RE_NUCLIDE_U = re.compile(r"^([⁰¹²³⁴⁵⁶⁷⁸⁹]+)([₀₁₂₃₄₅₆₇₈₉]*)([A-Z][a-z]?)$")
_RE_FORMULA_TOKEN = re.compile(r"^[0-9]*(?:[A-Z][a-z]?[0-9₀-₉]*|\((?:[A-Z][a-z]?[0-9₀-₉]*)+\)[0-9₀-₉]*"
                               r"|\[(?:[A-Z][a-z]?[0-9₀-₉]*|\((?:[A-Z][a-z]?[0-9₀-₉]*)+\)[0-9₀-₉]*)+\][0-9₀-₉]*)+"
                               r"(?:[·.∙*][0-9]*(?:[A-Z][a-z]?[0-9₀-₉]*|\((?:[A-Z][a-z]?[0-9₀-₉]*)+\)[0-9₀-₉]*)+)*"
                               r"(?:[⁰¹²³⁴⁵⁶⁷⁸⁹]*[⁺⁻]|\^\{?\d*[+-]\}?|[+-])?(?:\((?:s|l|g|aq)\))?[•·]?$")
_RE_SUB_OR_CHARGE = re.compile(r"[₀-₉⁺⁻]|\^")
_RE_FORMULA_STRICT = re.compile(r"^[0-9]*(?:[A-Z][a-z]?[0-9]*|\([A-Za-z0-9]+\)[0-9]*)+(?:\([a-z]+\))?$")


_MOLECULES = {"H2", "N2", "O2", "F2", "Cl2", "Br2", "I2", "O3", "P4", "S8", "H3", "C60"}


def _formula_like(core: str) -> bool:
    """Does a prose token read as a chemical formula (so spell it out)?"""
    if not core or not core[0].isalnum() and core[0] not in "([":
        return False
    if re.fullmatch(r"[A-Z][a-z]?\d+", core) and core not in _MOLECULES:
        return False  # S1, P2, M1: a label, not a formula
    if not _RE_FORMULA_TOKEN.match(core):
        return False
    letters = re.findall(r"[A-Z][a-z]?", core)
    if not letters or not all((x in ELEMENT_NAME or (x in ("R", "X") and len(letters) >= 2)) for x in letters):
        return False
    has_sub = bool(re.search(r"[₀-₉]|\d", core)) or bool(re.search(r"[⁺⁻]", core)) or "^" in core or core.endswith("•")
    if not has_sub and core[-1:] in ("+", "-") and len(core) >= 2:
        base = core[:-1]
        has_sub = (len(re.findall(r"[A-Z][a-z]?", base)) >= 2 or base in ("H", "F", "I", "Li", "Na", "K", "Cl", "Br", "OH")
                   or (len(base) == 2 and base in ELEMENT_NAME)) and base[:1].isupper()
    if has_sub:
        # a bare number followed by one capital letter (2 N) is not a formula
        return bool(re.search(r"[A-Z]", core)) and not re.fullmatch(r"\d+[A-Z]", core)
    if len(letters) >= 2 and core.isalpha() and core not in _ACRONYM_OK and core not in ("Hi", "Cos", "Nano") \
            and (len(core) <= 4 or any(c.islower() for c in core)):
        return True  # HCl, NaOH, NaCl, CO
    return False


def _unicode_formula_to_ascii(core: str) -> str:
    t = _RE_SUPRUN.sub(lambda m: "^{" + "".join(_SUP_MAP[c] for c in m.group()) + "}", core)
    t = _RE_SUBRUN.sub(lambda m: "".join(_SUB_MAP[c] for c in m.group()), t)
    return t


def _greek_words(s: str) -> str:
    return "".join((" " + GREEK_CHAR[c] + " ") if c in GREEK_CHAR else c for c in s)


def _delta_words(core: str) -> str | None:
    m = _RE_DELTA.match(core)
    if not m:
        return None
    d, letter, sub, paren, std = m.groups()
    word = "delta" if d in "Δδ∆" else "sigma"
    out = f"{word} {letter}"
    if sub:
        out += " " + _DELTA_SUB.get(sub, " ".join(sub) if len(sub) <= 2 else sub)
    if paren:
        out += " of " + prose_words(paren)
    if std:
        out += " standard"
    return out


def _core_words(core: str) -> str | None:
    """Words for one whitespace-free prose token (punctuation already peeled), or None to leave it."""
    if not core:
        return ""
    mst = re.search(r"\((s|l|g|aq)\)$", core)
    if mst and len(core) > mst.end() - mst.start():
        base = _core_words(core[:mst.start()])
        if base is not None:
            return base + " " + _STATE_ONE[mst.group(1)]
    if re.search(r"[–−\-]", core) and re.search(r"[A-Za-z₀-₉⁰¹²³⁴⁵⁶⁷⁸⁹]", core) and core[0] not in "–−-" and core[-1] not in "–−-" \
            and re.search(r"[₀-₉⁰¹²³⁴⁵⁶⁷⁸⁹⁺⁻]|[A-Z][a-z]?[–−]", core):
        pieces = re.split(r"[–−\-]+", core)
        if len(pieces) >= 2 and all(pieces):
            return " ".join((_core_words(x) or x) for x in pieces)
    d = _delta_words(core)
    if d:
        return d
    if _RE_E_STD.match(core) or (len(core) == 2 and core[0] in "EGHSK" and core[1] in _STD):
        return core[0] + " standard"
    mn = _RE_NUCLIDE_U.match(core)
    if mn:
        sym = mn.group(3)
        if sym in ELEMENT_NAME:
            mass = int("".join(_SUP_MAP[c] for c in mn.group(1)))
            z = "".join(_SUB_MAP[c] for c in mn.group(2))
            out = f"{ELEMENT_NAME[sym]} {mass_words(mass)}"
            if z:
                out += f", atomic number {int_words(int(z))},"
            return out
    if core in ("e⁻", "e−"):
        return "an electron"
    if core in ("β⁺", "β⁻", "β−", "e⁺"):
        return {"β⁺": "beta plus", "β⁻": "beta minus", "β−": "beta minus", "e⁺": "a positron"}[core]
    if "^" in core or "_" in core:
        w = speak_math(core)
        if w:
            return w
    if _formula_like(core) and core not in _NON_ELEMENT_WORDS:
        ascii_f = _unicode_formula_to_ascii(core)
        return chem_words(ascii_f)
    for sepch, sepw in (("=", "equals"), ("+", "plus")):
        if sepch in core and not core.startswith(sepch) and len(core) > 2:
            pieces = [x for x in core.split(sepch)]
            if len(pieces) >= 2 and all(not x or _formula_like(x) for x in pieces) and any(_formula_like(x) for x in pieces):
                return (" " + sepw + " ").join(chem_words(_unicode_formula_to_ascii(x)) if x else "" for x in pieces).strip()
    ma = re.fullmatch(r"([A-Za-z]{1,4})(\d{1,2})", core)
    if ma:
        letters = ma.group(1)
        lw = " ".join(letters) if (len(letters) <= 3 and (letters.isupper() or len(letters) == 1 or len(letters) <= 2)) else letters
        return lw + " " + number_words(ma.group(2))
    if core in _LONE_UNITS:
        return units_words([(core, 1)], True)
    # lone element symbols (Cl, Na): the element's name, unless it could be an English word or a unit
    if re.fullmatch(r"[A-Z][a-z]", core) and core in ELEMENT_NAME and core not in _NON_ELEMENT_WORDS \
            and core not in ("Pa", "Cd", "Ar", "Mn", "Sn", "Sr", "Mt", "Rf", "Hf", "Nb", "Db", "Cf", "Tm", "Fm", "Md"):
        return ELEMENT_NAME[core]
    mw = re.fullmatch(r"(\(?)([A-Za-z]{3,})(\)?)([⁰¹²³⁴⁵⁶⁷⁸⁹⁻⁺ⁿ]+)", core)
    if mw and not _formula_like(core):
        tail = speak_math("x" + mw.group(4))
        tail = tail[1:] if tail.startswith("x") else " " + tail
        return mw.group(2) + tail
    if re.search(r"[⁰¹²³⁴⁵⁶⁷⁸⁹₀-₉⁺⁻ⁿⁱ]", core):
        tex = core
        w = speak_math(tex)
        if w:
            return w
    # greek letters inside a word: β-decay, γ-rays, α
    if any(c in GREEK_CHAR for c in core):
        return _greek_words(core).replace("-", " ")
    # all-capital acronyms: NMR, UV, IR -> spelled
    if core.isalpha() and core.isupper() and 2 <= len(core) <= 3 and core not in _ACRONYM_OK:
        return " ".join(core)
    return None


def _peel(tok: str) -> tuple[str, str, str]:
    m = re.match(r"^([\"'“‘«]*)(.*?)([\"'”’».,;:!?…]*)$", tok, re.S)
    if not m:
        return "", tok, ""
    lead, core, trail = m.group(1), m.group(2), m.group(3)
    # brackets: peel only the ones that are unbalanced inside the token
    while core and core[0] in "([{" and core.count("(") + core.count("[") + core.count("{") > core.count(")") + core.count("]") + core.count("}"):
        lead += core[0]
        core = core[1:]
    while core and core[-1] in ")]}" and core.count(")") + core.count("]") + core.count("}") > core.count("(") + core.count("[") + core.count("{"):
        trail = core[-1] + trail
        core = core[:-1]
    return lead, core, trail


def _tokens_pass(s: str) -> str:
    parts = re.split(r"(\s+)", s)
    out: list[str] = []
    for part in parts:
        if not part or part.isspace():
            out.append(part)
            continue
        if re.search(r"[\U000F0000-\U000FFFFF]", part):  # maths placeholders split a token: Cl$^-$
            pieces = re.split(r"([\U000F0000-\U000FFFFF])", part)
            out.append("".join(p if (not p or ord(p[0]) >= 0xF0000) else _one_token(p) for p in pieces))
            continue
        out.append(_one_token(part))
    return "".join(out)


def _one_token(part: str) -> str:
    mc = re.fullmatch(r"\[([A-Za-z][^\[\]\s]*)\]([.,;:!?]*)", part)
    if mc and mc.group(1) in ("He", "Ne", "Ar", "Kr", "Xe", "Rn"):
        return "the " + ELEMENT_NAME[mc.group(1)] + " core" + mc.group(2)
    if mc and mc.group(1) in ("O", "H"):
        return part
    if mc:
        inner = _core_words(mc.group(1))
        return "the concentration of " + (inner if inner is not None else mc.group(1)) + mc.group(2)
    lead, core, trail = _peel(part)
    if core == "" and (lead or trail):
        return part
    w = _core_words(core)
    return lead + (w if w is not None else core) + trail


_RE_PAREN_LABEL = re.compile(r"(?:(?<=^)|(?<=[\s.]))((?:\(\s*(?:[a-h]|i{1,3}|iv|v|vi{1,3}|ix|x|\d{1,2})\s*\))+)(?=\s|$)")
_RE_STATE = re.compile(r"\(\s*(s|l|g|aq)\s*\)")
_STATE_ONE = {"s": "solid", "l": "liquid", "g": "gas", "aq": "aqueous"}


def _symbols_pass(s: str) -> str:
    s = re.sub(r"[ \t]+", " ", s)
    s = re.sub(r"\s*(?:-->|->|=>)\s*", " gives ", s)  # an ASCII reaction arrow, spoken as → is: never "is greater than" (B-113)
    s = s.replace("“", "").replace("”", "").replace("‘", "").replace("’", "'").replace('"', "")
    s = re.sub(r"(?<![A-Za-z])([A-Za-z])'(?![A-Za-z])", r"\1 prime ", s)
    s = re.sub(r"(?<![A-Za-z])'|'(?![A-Za-z])", " ", s)
    # states left over after formulas
    s = _RE_STATE.sub(lambda m: " " + _STATE_ONE[m.group(1)] + " ", s)
    # labels (a) (ii)
    s = _RE_PAREN_LABEL.sub(lambda m: " part " + " ".join(re.findall(r"[a-z0-9]+", m.group(1))) + ", ", s)
    # function-style x(t), f(x)
    s = re.sub(r"(?<=[A-Za-z])\(([^()]{1,12})\)", lambda m: " of " + m.group(1) + " ", s)
    # remaining parentheses: a pause either side
    s = re.sub(r"\(\s*", ", ", s)
    s = re.sub(r"\s*\)", ", ", s)
    s = re.sub(r"\[\s*", ", ", s)
    s = re.sub(r"\s*\]", ", ", s)
    # words
    s = s.replace("≥", " is greater than or equal to ").replace("≤", " is less than or equal to ")
    s = re.sub(r"(?<=\w)\s*/\s*(?=\w)", " or ", s)
    s = re.sub(r"\s=\s|(?<=\w)=(?=\w)|\s=(?=\w)|(?<=\w)=\s", " equals ", s)
    s = s.replace("=", " equals ")
    s = re.sub(r"(?<=\S)\s*\+\s*(?=\S)", " plus ", s)
    s = re.sub(r"(?<![\w)])\+(?=\w)", " plus ", s)
    s = s.replace("+", " plus ")
    s = re.sub(r"(?<=[\w\U000F0000-\U000FFFFF\)])\s?−\s?(?=[\w\U000F0000-\U000FFFFF\(])", " minus ", s)
    s = re.sub(r"(?<=[\w\U000F0000-\U000FFFFF])–(?=[\w\U000F0000-\U000FFFFF])", " ", s)
    s = re.sub(r"\s[–−-]\s", " , ", s)
    s = re.sub(r"(?<=[A-Za-z\U000F0000-\U000FFFFF])-(?=[A-Za-z0-9\U000F0000-\U000FFFFF])", " ", s)
    s = re.sub(r"(?<=[0-9A-Za-z\U000F0000-\U000FFFFF])-(?=[A-Za-z])", " ", s)
    s = re.sub(r"(?<![\w\U000F0000-\U000FFFFF])[–−-](?=\w)", " minus ", s)
    s = s.replace("–", " ").replace("-", " ")
    s = re.sub(r"\s:\s", " ", s)
    s = re.sub(r"(?<=\w):(?=\w)", " to ", s)
    out = []
    for ch in s:
        if ch in _UNI_WORDS:
            w = _UNI_WORDS[ch]
            out.append(" " + w + " " if w != "," else ", ")
        elif ch in GREEK_CHAR:
            out.append(" " + GREEK_CHAR[ch] + " ")
        elif ch in _REL:
            out.append(" " + _REL[ch] + " ")
        elif ch.isascii():
            out.append(ch)
        else:
            cat = unicodedata.category(ch)
            if ch.isalpha() or cat == "Nd":
                out.append(ch)
            elif ch in _SUP_MAP:
                out.append(" " + number_words(_SUP_MAP[ch]) + " " if _SUP_MAP[ch].isdigit() else "")
            elif ch in _SUB_MAP:
                out.append(" " + number_words(_SUB_MAP[ch]) + " " if _SUB_MAP[ch].isdigit() else "")
            elif ch in "\u00a0\u2009\u202f\u200a\u2002\u2003":
                out.append(" ")
            elif ch in "\U000F0000\u0301":
                out.append(ch)
            elif ord(ch) >= 0xF0000:
                out.append(ch)  # a placeholder: left alone
            else:
                w = _fallback_char(ch)
                out.append(" " + w + " " if w else " ")
    s = "".join(out)
    s = re.sub(r"[*~`<>|#@\\{}^_$]", lambda m: {"<": " is less than ", ">": " is greater than ", "@": " at "}.get(m.group(), " "), s)
    s = s.replace("&", " and ").replace("%", " percent ")
    return s


def _plain_year(m: "re.Match[str]", s: str = "") -> str:
    nxt = _RE_UNIT_WORD_AFTER.match(s, m.end())
    if nxt and unit_lookup(nxt.group(1)) is not None:  # '2000 kg' is a quantity, not a year
        return m.group()
    w = m.group(1)
    w = _MONTHS.get(w.lower(), w) if w.lower() in _MONTHS and w.lower() != "may" else w
    return w + " " + year_words(int(m.group(2)))


@functools.lru_cache(maxsize=16384)
def _prose_cached(s: str) -> str:
    return _prose_impl(s)


def prose_words(s: str) -> str:
    """Prose (no markdown, no $ maths) -> words.  Used for text and inside \\text{}."""
    return _prose_cached(s)


def _script_letters(m: "re.Match[str]") -> str:
    """A run of Unicode superscript (or subscript) characters holding letters, as words."""
    run, sup = m.group(), m.group()[0] in _SUP_MAP or m.group()[0] in _SUP_LET
    out = []
    for ch in run:
        a = _SUP_MAP.get(ch) or _SUP_LET.get(ch) if sup else _SUB_MAP.get(ch) or _SUB_LET.get(ch)
        a = a or ch
        out.append({"-": "minus", "+": "plus", "=": "equals", "(": "", ")": ""}.get(a) if not a.isalnum() else
                   (number_words(a) if a.isdigit() else a))
    words = " ".join(w for w in out if w)
    return (" to the " if sup else " sub ") + words + " "


def _prose_impl(s: str) -> str:
    s = _repair(s)
    s = _RE_SUPLET.sub(_script_letters, s)
    s = _RE_SUBLET.sub(_script_letters, s)
    s = s.replace("’", "'").replace("∆", "Δ").replace("µ", "μ").replace("Ω", "Ω").replace("‒", "–")
    s = s.replace("\u00a0", " ").replace("\u2009", " ").replace("\u202f", " ").replace("\u200a", " ")
    s = s.replace("\u00ad", "").replace("\u200b", "").replace("\ufeff", "")
    s = re.sub(r"([⁰¹²³⁴⁵⁶⁷⁸⁹]+)[ \u00a0]([₀-₉]+)(?![A-Z₀-₉])", lambda m: " " + (fraction_words(int("".join(_SUP_MAP[c] for c in m.group(1))), int("".join(_SUB_MAP[c] for c in m.group(2)))) or "") + " ", s)
    s = re.sub(r"(?<=[A-Za-z)\]₀-₉])[ \u00a0]+(?=[₀-₉]|[⁰¹²³⁴⁵⁶⁷⁸⁹]*[⁺⁻])", "", s)
    s = re.sub(r"(?<=[⁰¹²³⁴⁵⁶⁷⁸⁹])[ \u00a0]+(?=[₀-₉]+[A-Z])", "", s)
    s = _RE_URLISH.sub(" ", s)
    s = re.sub(r"\(\s*(?:ER|CAIE|IAL|Edexcel|Examiner)\b[^()]*\)", " ", s)
    s = re.sub(r"\b97(?:01|02|09)\b|\b9231\b", lambda m: _digits(m.group()), s)
    for pat, rep in _ABBREV:
        s = pat.sub(rep, s)
    # electrons before numbers: 2e⁻ -> two electrons
    s = re.sub(r"(?<![A-Za-z])(\d*)\s?e[⁻−](?![A-Za-z⁰¹²³⁴⁵⁶⁷⁸⁹])", lambda m: (" " + (number_words(m.group(1)) + " electrons " if m.group(1) and m.group(1) != "1" else "an electron ")), s)
    s = _RE_WORD_PREFIX.sub(lambda m: _plain_year(m, s), s)
    s = _RE_ORDINAL.sub(lambda m: _ordinal_words(int(m.group(1))), s)
    s = re.sub(r"(?<=\d):(?=\d)", " to ", s)
    s = re.sub(r"([£€])\s?(\d[\d,]*(?:\.\d+)?)", lambda m: m.group(2) + {"£": " pounds", "€": " euros"}[m.group(1)], s)
    s = re.sub(r"(?<![\d/.])(\d{1,2})/(\d{1,2})(?![\d/])", lambda m: (" " + _frac_or_over(int(m.group(1)), int(m.group(2))) + " "), s)
    s = re.sub(r"(?<=\d)\s*/\s*(?=\d)", lambda m: "\0/\0", s)
    s = re.sub(r"\(\s*([^()]*\d[^()]*?)\s*\)(?=\s?[A-Za-zμΩ°%])", lambda m: (" " + m.group(1) + " ") if (re.fullmatch(r"[\d.,\s±×x⁻⁺⁰¹²³⁴⁵⁶⁷⁸⁹−-]+", m.group(1)) and _units_after(s, m.end()) is not None) else m.group(0), s)
    s = _convert_numbers(s)
    s = _convert_bare_units(s)
    s = re.sub(r"\b(\w+)\0/\0(\w+)\b", lambda m: _slash_fraction(m.group(1), m.group(2)), s)
    s = s.replace("\0/\0", " over ")
    s = _tokens_pass(s)
    s = _symbols_pass(s)
    return s


def _frac_or_over(a: int, b: int) -> str:
    return (fraction_words(a, b) if a < b else None) or f"{int_words(a)} over {int_words(b)}"


def _slash_fraction(a: str, b: str) -> str:
    return f"{a} over {b}"


def _split_punct(s: str) -> str:
    return s


# --------------------------------------------------------------------------------------------------
# Markdown structure
# --------------------------------------------------------------------------------------------------

_PH0 = 0xF0000  # placeholders for maths spans: one private-use character each
_RE_MATH = re.compile(r"\$\$(.+?)\$\$|\\\[(.+?)\\\]|\\\((.+?)\\\)"
                      r"|(?<![\\$])\$(?![\s$])((?:\\.|[^$\\\n]|\n(?!\s*\n))+?)(?<![\s\\])\$(?!\d)", re.S)
_RE_FENCE = re.compile(r"^\s*(```|~~~)")
_RE_BULLET = re.compile(r"^\s*(?:[-*+•●○]|\d{1,3}[.)])\s+(?:\[[ xX]\]\s+)?")
_RE_CALLOUT = re.compile(r"^\s*>\s*\[!(\w[\w-]*)\][+-]?\s*(.*)$")
_RE_BLOCKID = re.compile(r"\s\^[A-Za-z0-9-]+\s*$")
_RE_EMBED = re.compile(r"!\[\[[^\]]*\]\]")
_RE_IMG = re.compile(r"!\[[^\]]*\]\([^)]*\)")
_RE_WIKI = re.compile(r"\[\[([^\]|]*?)(?:\|([^\]]*))?\]\]")
_RE_MDLINK = re.compile(r"\[([^\]]+)\]\((?:[^)]*)\)")
_RE_FRONT = re.compile(r"\A---\s*\n.*?\n---\s*\n", re.S)
_RE_COMMENT = re.compile(r"%%.*?%%|<!--.*?-->", re.S)
_RE_TAG = re.compile(r"(?<![\w/])#[A-Za-z][\w/-]*")
_RE_HTML = re.compile(r"</?[A-Za-z][^>]*>")
_RE_HR = re.compile(r"^\s*(?:-{3,}|\*{3,}|_{3,}|={3,})\s*$")
_RE_TABLE_ROW = re.compile(r"^\s*\|.*\|\s*$")
_RE_TABLE_SEP = re.compile(r"^\s*\|?\s*:?-{2,}:?\s*(?:\|\s*:?-{2,}:?\s*)*\|?\s*$")


def _wiki(m: "re.Match[str]") -> str:
    target, alias = m.group(1), m.group(2)
    if alias:
        return alias
    t = target.split("#")[-1] if "#" in target else target
    t = t.split("/")[-1]
    t = re.sub(r"^\d+(?:\.\d+)*\s+", "", t)
    return t


def _mask_math(text: str) -> tuple[str, list[tuple[str, bool, str]]]:
    spans: list[tuple[str, bool, str]] = []

    def sub(m: "re.Match[str]") -> str:
        display = m.group(1) is not None or m.group(2) is not None
        body = re.sub(r"\[\[([A-Za-z_]\w*)(?::[^\]]*)?\]\]", r" \\text{\1} ", next(g for g in m.groups() if g is not None))
        spans.append((body, display, m.group(0)))
        return chr(_PH0 + len(spans) - 1)

    return _RE_MATH.sub(sub, text), spans


def _unmask(text: str, spans: list[tuple[str, bool, str]]) -> str:
    def sub(m: "re.Match[str]") -> str:
        body, display, _orig = spans[ord(m.group()) - _PH0]
        words = speak_math(body.strip().rstrip(".,;"))
        return (", " + words + ", ") if (display and words) else (" " + words + " ")

    return re.sub(r"[\U000F0000-\U000FFFFF]", sub, text) if spans else text


def _strip_emphasis(line: str) -> str:
    line = re.sub(r"\*\*\*(.+?)\*\*\*", r"\1", line)
    line = re.sub(r"\*\*(.+?)\*\*", r"\1", line)
    line = re.sub(r"__(.+?)__", r"\1", line)
    line = re.sub(r"(?<![\w*])\*(?=\S)([^*\n]+?)(?<=\S)\*(?![\w*])", r"\1", line)
    line = re.sub(r"(?<![\w_])_(?=\S)([^_\n]+?)(?<=\S)_(?![\w_])", r"\1", line)
    line = re.sub(r"~~(.+?)~~", r"\1", line)
    line = re.sub(r"==(.+?)==", r"\1", line)
    line = re.sub(r"`([^`]*)`", r"\1", line)
    return line


def _blocks(text: str, skip_links: bool = False, tables: bool = False) -> list[str]:
    """Markdown-ish text -> a list of raw paragraph strings (maths still as $..$ spans).

    With skip_links the "Links" section (navigation to other notes) is left out."""
    text = _RE_FRONT.sub("", text.replace("\r\n", "\n").replace("\r", "\n"), count=1)
    text = _RE_COMMENT.sub("", text)
    text = _RE_EMBED.sub("", text)
    text = _RE_IMG.sub("", text)
    text = re.sub(r"```.*?```|~~~.*?~~~", "\n", text, flags=re.S)
    text = _RE_HTML.sub(" ", text)
    paras: list[str] = []
    cur: list[str] = []
    in_fence = False
    in_links = False

    def flush():
        nonlocal cur
        if cur:
            paras.append(_join_lines(cur))
        cur = []

    for raw in text.split("\n"):
        if _RE_FENCE.match(raw):
            in_fence = not in_fence
            flush()
            continue
        if in_fence:
            continue
        line = raw.rstrip()
        if not line.strip():
            flush()
            continue
        if _RE_HR.match(line) and not _RE_BULLET.match(line + " x"):
            flush()
            continue
        if _RE_TABLE_ROW.match(line) or _RE_TABLE_SEP.match(line) and "|" in line:
            flush()
            if tables and not _RE_TABLE_SEP.match(line):  # a question's table is its data: read each row (B-128)
                cells = [c.strip() for c in line.strip().strip("|").split("|")]
                if any(cells):
                    paras.append(", ".join(c for c in cells if c) + ".")
            continue
        mc = _RE_CALLOUT.match(line)
        if mc:
            flush()
            title = mc.group(2).strip()
            if title:
                paras.append(title)
            continue
        line = re.sub(r"^\s*(?:>\s?)+", "", line)
        if not line.strip():
            flush()
            continue
        hm = re.match(r"^\s*#{1,6}\s+(.*)$", line)
        if hm:
            flush()
            in_links = skip_links and hm.group(1).strip().lower() in ("links", "related", "see also")
            if not in_links:
                paras.append(hm.group(1).strip())
            continue
        if in_links:
            continue
        if _RE_BULLET.match(line):
            flush()
            cur.append(_RE_BULLET.sub("", line, count=1))
            flush()
            continue
        cur.append(line.strip())
    flush()
    return [p for p in (x.strip() for x in paras) if p]


def _join_lines(lines: list[str]) -> str:
    out = lines[0]
    for ln in lines[1:]:
        if re.search(r"[.!?:;,]$", out) or ln[:1].islower() or out[-1:] in "-–—":
            out += " " + ln
        elif re.match(r"^[•●○▪■◦]\s*$", ln) or re.match(r"^[•●○▪■◦]\s*$", out):
            out += " " + ln
        elif ln[:1].isupper() or ln[:1].isdigit() or not ln[:1].isalpha():
            out += ". " + ln
        else:
            out += " " + ln
    return out


def _end_punct(s: str) -> str:
    s = s.rstrip(" ,;:")
    if s and s[-1] not in ".?!":
        s += "."
    return s


def _finish(s: str) -> str:
    """The final clean-up shared by speakable() and the author's `speech` overrides."""
    s = _RE_CTRL.sub(" ", s)
    s = re.sub(r"[\\{}^_$\U000F0000-\U000FFFFF]", " ", s)
    s = s.replace(";", ",").replace(":", ",")
    s = re.sub(r"\s+", " ", s)
    s = re.sub(r",(?=[A-Za-z0-9])", ", ", s)
    s = re.sub(r"\s+([,.?!])", r"\1", s)
    s = re.sub(r",\s*([.?!])", r"\1", s)
    s = re.sub(r"([,.?!])(?:\s*[,.])+", lambda m: m.group(1) if m.group(1) in ".?!" else m.group(1), s)
    s = re.sub(r"(?<![A-Za-z0-9])([,.]\s*)+(?=[A-Za-z0-9])", "", s) if s[:1] in ",." else s
    s = re.sub(r"\.\s*,", ".", s)
    s = re.sub(r"^[\s,.]+", "", s).strip()
    # sentences: capitalise nothing, but make sure every full stop is followed by a space
    s = re.sub(r"\.(?=[A-Za-z])", ". ", s)
    return _end_punct(s) if s else ""


def _paragraph(p: str, spans: list) -> str:
    masked = _RE_WIKI.sub(_wiki, p)
    masked = _RE_MDLINK.sub(r"\1", masked)
    masked = re.sub(r"\[\^[^\]]*\]", "", masked)
    masked = _RE_BLOCKID.sub("", masked)
    masked = _RE_TAG.sub(" ", masked)
    masked = _strip_emphasis(masked)
    masked = re.sub(r"^\s*(?:\d{1,3}[.)])\s+", "", masked)
    words = prose_words(masked)
    return _finish(_unmask(words, spans))


@functools.lru_cache(maxsize=32768)
def _convert(text: str) -> tuple[str, tuple[str, ...]]:
    prev = getattr(_TLS, "gaps", None)
    _TLS.gaps = []
    try:
        pieces = []
        # between numbers or single-letter quantities a spaced dash is subtraction (131 - 53 = 78): the true minus
        # sign, read "minus" further on; elsewhere it stays a dash, a pause (B-112)
        text = re.sub(r"(?:(?<=\d)|(?<=\))|(?<=\b[A-Za-z]))\s[-–]\s(?=\d|\(|[A-Za-z]\b)", " − ", text)
        paras, spans = _blocks_masked(_repair(text), tables=True)  # a note's own tables are left out (note_paragraphs)
        for p in paras:
            w = _paragraph(p, spans)
            if w:
                pieces.append(w)
        result = " ".join(pieces)
        gaps = tuple(dict.fromkeys(_TLS.gaps))
    finally:
        _TLS.gaps = prev
    return _verify(result, gaps)


def _verify(result: str, gaps: tuple[str, ...]) -> tuple[str, tuple[str, ...]]:
    """Last line of defence: nothing LaTeX-like may survive."""
    if re.search(r"[\\{}^_$]", result):
        gaps = gaps + tuple(dict.fromkeys("raw " + c for c in re.findall(r"[\\{}^_$]", result)))
        result = re.sub(r"[\\{}^_$]", " ", result)
        result = re.sub(r"\s+", " ", result).strip()
    return result, gaps


def speakable(text: str) -> str:
    """Chapter text -> the plain spoken English for it (see the module docstring).

    Deterministic and total: any string gives a string (empty when there is nothing to say).  A non-empty
    result ends with a full stop (or ? / !), holds no backslash, brace, caret, underscore or dollar sign,
    and no digits are left as digits except inside words that merely contain them.
    """
    if not isinstance(text, str) or not text.strip():
        return ""
    result, gaps = _convert(text)
    for g in gaps:  # make the report visible to a speech_gaps() wrapper on this thread too
        _gap(g)
    return result


def speech_gaps(text: str) -> list[str]:
    """Symbols / commands in `text` that had no natural spoken form (a fallback was used), in order of first use.

    Each entry is the offending command ("\\foo"), the character, "U+F0E6"-style code for unnamed junk, or
    "unit xyz".  A gate requires the list empty (or the item to carry a `speech` override).
    """
    if not isinstance(text, str) or not text.strip():
        return []
    _, gaps = _convert(text)
    return list(gaps)


def for_tts(text: str) -> str:
    """speakable(text) with the PRONOUNCE respellings applied: the string to hand to the synthesiser."""
    out = speakable(text)
    return _pronounce(out)


_A_ARTICLE_NEXT = re.compile(r"\s+(?!(?:to|and|or|is|was|has|at|in|on|from|then|equals|plus|minus|gives|by|of)\b)[a-z]")


def _letter_a(out: str) -> str:
    """A capital A that names something (option A, point A, A to B, "the answer is A,") is the letter, said "ay"; one
    that starts a noun ("A charge") is the article and stays (B-116)."""
    def say(m: "re.Match[str]") -> str:
        return m.group(0) if _A_ARTICLE_NEXT.match(out, m.end()) else "ay"
    return re.sub(r"(?<![A-Za-z'])A(?![A-Za-z'])", say, out)


def _pronounce(out: str) -> str:
    out = _letter_a(out)
    if not PRONOUNCE or not out:
        return out
    for word, respell in PRONOUNCE.items():
        out = re.sub(r"(?<![A-Za-z])" + re.escape(word) + r"(?![A-Za-z])", respell, out, flags=re.I)
    return out


# --------------------------------------------------------------------------------------------------
# Cache key
# --------------------------------------------------------------------------------------------------


def audio_key(speech_text: str, voice: str, speed: float) -> str:
    """The stable cache key of one spoken line: hex sha1 of ``"{text}\\n{voice}\\n{speed:.2f}"`` (UTF-8).

    * ``text`` is the line to speak after whitespace normalisation: runs of whitespace become one space,
      leading / trailing whitespace is removed (nothing else: case and punctuation are kept, so a changed
      word changes the key).  Pass the string you give to the synthesiser (``for_tts(...)`` output).
    * ``voice`` is the voice id exactly as given to the synthesiser, e.g. ``"bf_emma"``.
    * ``speed`` is formatted with two decimals, so 1, 1.0 and 1.001 -> ``"1.00"``.

    The app (to find audio) and the foundry / refine pre-generator (to name files, ``<key>.wav`` or
    similar) must both call this function and nothing else.  Do not change it: every cached file would
    stop matching.
    """
    norm = " ".join(str(speech_text).split())
    blob = f"{norm}\n{voice}\n{float(speed):.2f}".encode("utf-8")
    return hashlib.sha1(blob).hexdigest()


# --------------------------------------------------------------------------------------------------
# Chapter script
# --------------------------------------------------------------------------------------------------

_CARD_FIELDS = ("motivate", "establish", "connect", "note", "self_explain", "discover")


def _blocks_masked(text: str, skip_links: bool = False, tables: bool = False):
    """Mask the maths first (a display block may span lines), then split into paragraphs."""
    text = _RE_FRONT.sub("", text.replace("\r\n", "\n").replace("\r", "\n"), count=1)
    text = re.sub(r"```.*?```|~~~.*?~~~", "\n", text, flags=re.S)
    masked, spans = _mask_math(text)
    return _blocks(masked, skip_links=skip_links, tables=tables), spans


def note_paragraphs(note_text: str) -> list[str]:
    """The paragraphs of a note that are spoken: front matter, tables, code, embeds and the Links section are left out."""
    paras, spans = _blocks_masked(_repair(note_text or ""), skip_links=True)
    return [re.sub(r"[\U000F0000-\U000FFFFF]", lambda m: spans[ord(m.group()) - _PH0][2], p) for p in paras]


def _has_placeholder(*vals) -> bool:
    """A [[variable]] slot: the numbers are drawn at run time, so nothing fixed can be pre-generated."""
    for v in vals:
        if isinstance(v, str):
            if "[[" in v:
                return True
        elif isinstance(v, (list, tuple)) and _has_placeholder(*v):
            return True
    return False


def _flat_strings(o) -> list[str]:
    if isinstance(o, str):
        return [o]
    if isinstance(o, (list, tuple)):
        return [s for x in o for s in _flat_strings(x)]
    if isinstance(o, dict):
        return [s for x in o.values() for s in _flat_strings(x)]
    return []


def _line(where: str, text: str, override: str | None = None) -> dict | None:
    if override is not None and isinstance(override, str) and override.strip():
        spoken = _pronounce(_finish(override))
    else:
        spoken = for_tts(text)
    return {"id": where, "text": spoken} if spoken else None


def script_for_chapter(pack: dict, note_text: str) -> list[dict]:
    """The spoken lines of one chapter, for pre-generating audio: [{"id": ..., "text": ...}, ...].

    ``text`` is for_tts() of the source string (what to hand to the synthesiser); the caller adds the
    voice and speed and calls audio_key(text, voice, speed).  Ids, in this order:

    * ``card:<kc>:<field>`` for each teach card (motivate, establish, connect, note, self_explain, discover).
    * ``item:<id>:stem``, ``item:<id>:explanation``, ``item:<id>:hint1`` .. ``hintN`` for each question.
      Options, rubrics, tables and answers are not spoken.
    * ``note:<n>`` for each paragraph / list item / heading of the note (n counts spoken paragraphs from 1).

    Templated items (those with a ``template`` or a ``[[variable]]`` slot) are skipped entirely: their
    numbers are drawn at run time, so there is nothing fixed to pre-generate.

    Override: a teach card may hold ``speech`` = {field: text}; an item may hold ``speech`` = text (the
    stem) or {"stem" | "explanation" | "hint1": text}.  An override is spoken verbatim after the same
    final clean-up (no maths conversion), so an author can fix a hard case by writing the words.
    """
    lines: list[dict] = []
    pack = pack or {}
    teach = pack.get("teach") or {}
    for kc, card in teach.items():
        if not isinstance(card, dict):
            continue
        over = card.get("speech") if isinstance(card.get("speech"), dict) else {}
        for field in _CARD_FIELDS:
            val = card.get(field)
            if isinstance(val, dict):  # a structured discover card: speak its strings in order
                val = " ".join(_flat_strings(val))
            ov = over.get(field) if isinstance(over, dict) else None
            if (isinstance(val, str) and val.strip()) or ov:
                ln = _line(f"card:{kc}:{field}", val if isinstance(val, str) else "", ov)
                if ln:
                    lines.append(ln)
    for it in pack.get("items") or []:
        if not isinstance(it, dict) or not it.get("id"):
            continue
        if it.get("template") or _has_placeholder(it.get("stem"), it.get("explanation"), it.get("hints")):
            continue
        iid = it["id"]
        sp = it.get("speech")
        over = sp if isinstance(sp, dict) else ({"stem": sp} if isinstance(sp, str) else {})
        parts = [("stem", it.get("stem")), ("explanation", it.get("explanation"))]
        parts += [(f"hint{n}", h) for n, h in enumerate(it.get("hints") or [], 1)]
        for name, val in parts:
            ov = over.get(name)
            if (isinstance(val, str) and val.strip()) or ov:
                ln = _line(f"item:{iid}:{name}", val if isinstance(val, str) else "", ov)
                if ln:
                    lines.append(ln)
    n = 0
    for para in note_paragraphs(note_text):
        ln = _line(f"note:{n + 1}", para)
        if ln:
            n += 1
            ln["id"] = f"note:{n}"
            lines.append(ln)
    return lines
