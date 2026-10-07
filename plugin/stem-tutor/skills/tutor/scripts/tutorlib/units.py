"""Tiny SI unit algebra: parse 'mol dm-3', 'm/s', 'ms⁻²', 'kJ mol^-1' into (factor, dimensions)."""
from __future__ import annotations

import re

# dimension order: m, kg, s, A, K, mol
def _d(m=0, kg=0, s=0, A=0, K=0, mol=0):
    return (m, kg, s, A, K, mol)


BASE = {
    "m": (1.0, _d(m=1)),
    "g": (1e-3, _d(kg=1)),
    "s": (1.0, _d(s=1)),
    "A": (1.0, _d(A=1)),
    "K": (1.0, _d(K=1)),
    "mol": (1.0, _d(mol=1)),
    "N": (1.0, _d(m=1, kg=1, s=-2)),
    "J": (1.0, _d(m=2, kg=1, s=-2)),
    "W": (1.0, _d(m=2, kg=1, s=-3)),
    "Pa": (1.0, _d(m=-1, kg=1, s=-2)),
    "C": (1.0, _d(s=1, A=1)),
    "V": (1.0, _d(m=2, kg=1, s=-3, A=-1)),
    "Ω": (1.0, _d(m=2, kg=1, s=-3, A=-2)),
    "ohm": (1.0, _d(m=2, kg=1, s=-3, A=-2)),
    "F": (1.0, _d(m=-2, kg=-1, s=4, A=2)),
    "T": (1.0, _d(kg=1, s=-2, A=-1)),
    "Wb": (1.0, _d(m=2, kg=1, s=-2, A=-1)),
    "Hz": (1.0, _d(s=-1)),
    "Bq": (1.0, _d(s=-1)),
    "eV": (1.602176634e-19, _d(m=2, kg=1, s=-2)),
    "L": (1e-3, _d(m=3)),
    "l": (1e-3, _d(m=3)),
    "min": (60.0, _d(s=1)),
    "hour": (3600.0, _d(s=1)),
    "atm": (101325.0, _d(m=-1, kg=1, s=-2)),
    "u": (1.66053906660e-27, _d(kg=1)),
    "rad": (1.0, _d()),
    "sr": (1.0, _d()),
    "%": (0.01, _d()),
}
# spelled-out time units a student may type ("35 minutes"): read as the symbol they name
ALIASES = {"percent": "%", "mins": "min", "minute": "min", "minutes": "min", "sec": "s", "secs": "s", "second": "s",
           "seconds": "s", "h": "hour", "hr": "hour", "hrs": "hour", "hours": "hour"}
PREFIX = {"G": 1e9, "M": 1e6, "k": 1e3, "d": 1e-1, "c": 1e-2, "m": 1e-3, "μ": 1e-6, "µ": 1e-6, "u": 1e-6, "n": 1e-9, "p": 1e-12}

SUPERSCRIPT = str.maketrans("⁻⁺⁰¹²³⁴⁵⁶⁷⁸⁹", "-+0123456789")
# a run of letters is tried as every sequence of symbols ("kgms" = kg·m·s) and the readings of each token multiply:
# both grow exponentially, so anything longer than a real unit is refused instead of being worked through
MAX_RUN, MAX_READINGS = 12, 2_000
TOKEN = re.compile(r"^([A-Za-zΩμµ%°]+)\^?\(?([+-]?\d+)?\)?$")


def _symbol(sym: str):
    sym = ALIASES.get(sym, sym)
    if sym in BASE:
        return BASE[sym]
    if len(sym) > 1 and sym[0] in PREFIX and sym[1:] in BASE:
        f, d = BASE[sym[1:]]
        return PREFIX[sym[0]] * f, d
    return None


def _splits(sym: str):
    """Ways to read a run of letters as consecutive unit symbols, e.g. 'ms' -> m·s."""
    if not sym:
        yield []
        return
    for i in range(len(sym), 0, -1):
        head = _symbol(sym[:i])
        if head:
            for rest in _splits(sym[i:]):
                yield [head] + rest


def _normalise(text: str) -> list[tuple[str, int, int]]:
    """(symbol run, exponent, +1 above the line or -1 below it) per token."""
    text = re.sub(r"[{}]", "", text.translate(SUPERSCRIPT))  # LaTeX braces: dm^{-3}
    text = text.replace("·", " ").replace("*", " ").replace(".", " ").strip()
    text = re.sub(r"\bper\s+cent\b", "percent", text, flags=re.I)
    text = re.sub(r"\s*/\s*", " / ", text)
    tokens, sign = [], 1
    for raw in text.split():
        if raw == "/":
            sign = -1
            continue
        m = TOKEN.match(raw)
        if not m:
            raise ValueError(f"unit token {raw!r}")
        tokens.append((m.group(1), sign * int(m.group(2) or 1), sign))
    return tokens


def parse_unit(text: str) -> list[tuple[float, tuple]]:
    """All plausible (factor, dims) readings, standard reading first."""
    if not text or not text.strip():
        return [(1.0, _d())]
    options = [(1.0, _d())]
    for sym, exp, sign in _normalise(text):
        if len(sym) > MAX_RUN:
            raise ValueError(f"unknown unit {sym!r}")
        readings = []
        std = _symbol(sym)
        if std:
            readings.append([(std, exp)])
        for split in _splits(sym):
            if len(split) > 1:
                readings.append([(u, sign) for u in split[:-1]] + [(split[-1], exp)])  # kg/ms2: m is below the line
        if not readings:
            raise ValueError(f"unknown unit {sym!r}")
        if len(options) * len(readings) > MAX_READINGS:
            raise ValueError(f"too many ways to read {text!r}")
        new = []
        for f0, d0 in options:
            for reading in readings:
                f, d = f0, list(d0)
                for (uf, ud), e in reading:
                    f *= uf**e
                    d = [a + b * e for a, b in zip(d, ud)]
                new.append((f, tuple(d)))
        options = new
    return options


_DEGREES = {"deg", "degs", "degree", "degrees"}
_MOLARITY = _d(m=-3, mol=1)


def unit_factor(given: str, expected: str) -> float | None:
    """Multiply a value in `given` units by this to express it in `expected` units."""
    if given.strip().lower() in _DEGREES:
        given = "°"
    if given.strip() == "M":  # molar, read so only where the answer is a concentration: never mega-anything
        try:
            if any(d == _MOLARITY for _f, d in parse_unit(expected)):
                given = "mol dm-3"
        except (ValueError, ArithmeticError):
            pass
    if given.replace(" ", "") == expected.replace(" ", ""):  # the same text: a match even if the symbol is unknown (°C)
        return 1.0
    try:
        for exp_f, exp_d in parse_unit(expected):  # "ms-1" reads as per-millisecond first, then as m s-1
            for f, d in parse_unit(given):
                if d == exp_d:
                    return f / exp_f
    except (ValueError, ArithmeticError):  # unknown symbol, or an exponent like km9999 that overflows
        return None
    return None


# a unit typed without its capitals, or spelled out, is forgiven when the unit as written cannot be the right kind
_BY_CASE: dict[str, list[str]] = {}
for _sym in list(BASE) + [p + b for p in PREFIX for b in BASE]:
    if _sym not in _BY_CASE.setdefault(_sym.lower(), []):
        _BY_CASE[_sym.lower()].append(_sym)
WORDS = {"watt": "W", "joule": "J", "newton": "N", "pascal": "Pa", "volt": "V", "ohm": "Ω", "amp": "A", "ampere": "A",
         "coulomb": "C", "hertz": "Hz", "metre": "m", "meter": "m", "gram": "g", "gramme": "g", "mole": "mol",
         "kelvin": "K", "litre": "L", "liter": "L", "farad": "F", "tesla": "T", "second": "s"}
PREFIX_WORDS = {"giga": "G", "mega": "M", "kilo": "k", "deci": "d", "centi": "c", "milli": "m", "micro": "μ",
                "nano": "n", "pico": "p"}
_WORD = re.compile("^(" + "|".join(PREFIX_WORDS) + ")?(" + "|".join(sorted(WORDS, key=len, reverse=True)) + ")s?$")
_JOINS = {"per", "square", "squared", "cubic", "cubed"}  # words that belong to a unit: never a comment after it


def _respelled(text: str) -> list[str]:
    """Other ways to read a unit as typed: "kw" and "KW" as kW, "kilowatts" as kW, "mw" as mW or MW, "per" as /."""
    options = [""]
    for raw in re.sub(r"\s*/\s*", " / ", text.translate(SUPERSCRIPT)).split():
        m = TOKEN.match(raw)
        sym = m.group(1) if m else ""
        word = _WORD.match(sym.lower()) if sym else None
        names = (["/"] if raw.lower() == "per" else [PREFIX_WORDS.get(word[1], "") + WORDS[word[2]]] if word
                 else _BY_CASE.get(sym.lower(), []) if sym else [])
        options = [f"{o} {n}{raw[len(sym):] if names else ''}".strip() for o in options for n in (names or [raw])][:16]
    return options


def _is_unit(word: str) -> bool:
    """Whether a word after a unit could be part of it (the s of "W s", "per", "squared") and not a comment on it."""
    if word.lower() in _JOINS:
        return True
    for text in [word] + _respelled(word):
        try:
            parse_unit(text)
            return True
        except ValueError:
            pass
    return False


def unit_readings(given: str, expected: str) -> tuple[list[float], bool]:
    """(every factor that could turn a value in `given` units into `expected` units, whether the unit was respelled).

    The unit as written comes first: 1.5 kW for an answer in W is simply the same answer. Words after the unit are
    a comment, not a unit ("200 W of input"), unless they could be part of one ("W s", "W per second"). Only when
    what was written cannot be read as the right kind of unit are capitals forgiven (kw, KW, pa) and spelled-out
    names accepted (kilowatts, joules per second); "mw" may then be mW or MW, and the caller sees which of them
    makes the answer right."""
    words = given.split()
    for k in range(len(words), 0, -1):
        if k < len(words) and _is_unit(words[k]):
            continue
        head = " ".join(words[:k])
        f = unit_factor(head, expected)
        if f is not None:
            return [f], False
        out: list[float] = []
        for text in _respelled(head):
            f = unit_factor(text, expected)
            if f is not None and f not in out:
                out.append(f)
        if out:
            return out, True
    return [], False
