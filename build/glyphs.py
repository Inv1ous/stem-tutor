"""Unsafe Unicode sub/superscript letters in content: find them, write them as LaTeX instead.

Why: the terminal draws Unicode subscript letters (ₐₑₖₙₚₛₜ…) and superscript letters (ᵃᵇᶜ…) from whatever font has
them, a different font per glyph, so a line like  Eₖ = ½mv²  looks wobbly (uneven baselines and heights). Only the
safe set (digits and + − = ( ) as sub/superscripts, and ⁿ ⁱ) is in every font; app/tutor_app/texmath.py owns that set.
Content must therefore write scripts in LaTeX ($E_k$), which the app draws linearly (E_k) or with safe glyphs (x²),
and Obsidian draws typeset. Never as Unicode letters.

THE RULE (one rule, everywhere): fix_text() turns every run of Unicode sub/superscripts that holds an unsafe glyph
into LaTeX.
  - inside a $…$ / $$…$$ / \\(…\\) span the run becomes _x / _{net} / ^{…} in place:        $Eₖ=…$  →  $E_k=…$
  - in prose the word it belongs to is wrapped in a new span:                              Eₖ  →  $E_k$,  CₙH₂ₙ₊₁OH → $C_nH_{2n+1}OH$
  - lowercase letters written beside a subscript letter belong to it (Vₒuₜ → $V_{out}$, Viₙ → $V_{in}$)
  - a run with no base to hang on (a stray ₙ) becomes plain linear text: _n
  - a string that is a font-mapping accident (three or more words with a run of two or more subscript letters, as
    in "Tₕₑ bₒₙd ₐₙgₗₑₛ") has those letters turned back into ordinary letters: The bond angles
Safe glyphs outside such words (H₂O, m s⁻², 10⁻³) are never touched, so a string without unsafe glyphs comes back
unchanged, byte for byte.

  .venv/bin/python build/glyphs.py [--write] [paths…]     default: packs, notes, teach sources, generator scripts
"""
from __future__ import annotations

import argparse
import io
import json
import re
import sys
import tokenize
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "app"))
from tutor_app.texmath import SCRIPT_GLYPHS, UNSAFE_GLYPHS, linearize  # noqa: E402

DEFAULTS = ["build/out/packs", "build/out/notes", "build/work/teach", "build/work/gen"]
SKIP_KEYS = {"id", "ids", "kc", "kcs", "slug", "key", "uid", "pack", "subject", "code", "topic_id", "syllabus_id"}

_SUBS = "".join(c for c, (k, _) in SCRIPT_GLYPHS.items() if k == "sub")
_SUPS = "".join(c for c, (k, _) in SCRIPT_GLYPHS.items() if k == "super")
_UNSAFE = "".join(sorted(UNSAFE_GLYPHS))
_ALLSCRIPT = _SUBS + _SUPS
_LETTER = "A-Za-zΑ-Ωα-ω"
_SUBCHAIN = re.compile(rf"([^\W\d_]|[)\]])((?:[a-z]*[{re.escape(_SUBS)}]+)+[a-z]*)")  # base, then ₒuₜ-style chain
_SUPRUN = re.compile(rf"([^\s{re.escape(_ALLSCRIPT)}])([{re.escape(_SUPS)}]+)")
_TOKEN = re.compile(rf"[\w{re.escape(_ALLSCRIPT)}′']+")
_GAP = re.compile(rf"(?<![\w])([{_LETTER}]) (?=[{re.escape(_UNSAFE)}])")  # "ν ₑ", a PDF's gap before a subscript
_MATH = re.compile(r"\$\$.+?\$\$|(?<!\\)\\\(.+?\\\)|(?<!\\)\\\[.+?\\\]|(?<!\\)\$(?!\s)(?:\\\$|[^$])+?(?<![\s\\])\$", re.S)
_PRICE = re.compile(r"\$\d[\d.,]*(?:\s|$)")


def _plain(s: str) -> str:
    return "".join(SCRIPT_GLYPHS[c][1] if c in SCRIPT_GLYPHS else c for c in s)


def _latex(kind: str, body: str) -> str:
    mark = "_" if kind == "sub" else "^"
    return mark + (body if len(body) == 1 else "{" + body + "}")


def _hit(s: str) -> bool:
    return any(c in UNSAFE_GLYPHS for c in s)


def _convert(s: str, only_unsafe: bool) -> str:
    """Runs of script characters in s → LaTeX (_x, ^{…}); with only_unsafe, only chains that hold an unsafe glyph."""
    def sub(m: re.Match) -> str:
        chain = m.group(2)
        if only_unsafe and not _hit(chain):
            return m.group(0)
        base = m.group(1)
        return base + _latex("sub", _plain(chain))

    def sup(m: re.Match) -> str:
        return m.group(0) if only_unsafe and not _hit(m.group(2)) else m.group(1) + _latex("super", _plain(m.group(2)))
    return _SUPRUN.sub(sup, _SUBCHAIN.sub(sub, s))


def _garbled(text: str) -> bool:
    words = [w for w in text.split() if re.search(rf"[{re.escape(_UNSAFE)}]{{2,}}", w)]
    return len(words) >= 3


def _prose(seg: str, record: list) -> str:
    def token(m: re.Match) -> str:
        t = m.group(0)
        if not _hit(t):
            return t
        if t[0] in _ALLSCRIPT:  # nothing to hang on: plain linear text
            fixed = linearize(t)
        else:
            fixed = "$" + _convert(t, only_unsafe=False) + "$"
        record.append((t, fixed))
        return fixed
    return _TOKEN.sub(token, _GAP.sub(r"\1", seg))


def _spans(text: str) -> list[tuple[int, int]]:
    return [m.span() for m in _MATH.finditer(text) if not (_PRICE.match(m.group(0)) and not re.search(r"[\\^_{=]", m.group(0)))]


def _fix(text: str, record: list) -> str:
    if not _hit(text):
        return text
    if "\\n" in text or "\\t" in text:  # a pack's text keeps the two characters \ n from its extraction: a line break
        text = text.replace("\\n", "\x01").replace("\\t", "\x02")
        return _fix(text, record).replace("\x01", "\\n").replace("\x02", "\\t")
    if _garbled(text):
        new = "".join(SCRIPT_GLYPHS[c][1] if c in UNSAFE_GLYPHS else c for c in text)
        new = re.sub(rf"(?<=\s)([{re.escape(_SUBS)}]+)(?=[°%\s])", lambda m: _plain(m.group(1)), new)  # ₁₂₀° → 120°
        record.append((text, new))
        return new
    out, at = [], 0
    for a, b in _spans(text) + [(len(text), len(text))]:
        out.append(_prose(text[at:a], record))
        if b > a:
            seg = text[a:b]
            fixed = _convert(seg, only_unsafe=True)
            if fixed != seg:
                record.append((seg, fixed))
            out.append(fixed)
        at = b
    return linearize("".join(out))  # whatever no rule reached is still made linear, never left as a wobbly glyph


def fix_text(text: str) -> str:
    """The text with every unsafe Unicode sub/superscript run written as LaTeX (see the rule at the top)."""
    return _fix(text, []) if isinstance(text, str) else text


def problems(text: str) -> list[str]:
    """One line per unsafe run found in the text, with the suggested replacement: 'Eₖ → $E_k$'."""
    if not isinstance(text, str) or not _hit(text):
        return []
    record: list = []
    _fix(text, record)
    found = [f"unsafe Unicode sub/superscript {a.strip()[:40]!r} (use LaTeX): suggest {b.strip()[:40]!r}" for a, b in record]
    return found or [f"unsafe Unicode sub/superscript glyph {c!r} (use LaTeX)" for c in sorted({c for c in text if c in UNSAFE_GLYPHS})]


def fix_data(data):
    """fix_text over every string value of parsed JSON (keys and id-like fields are never touched). → (new, changed)."""
    n = 0

    def walk(o, key=None):
        nonlocal n
        if isinstance(o, str):
            if key in SKIP_KEYS or (isinstance(key, str) and key.endswith("_id")):
                return o
            new = fix_text(o)
            n += new != o
            return new
        if isinstance(o, list):
            return [walk(x, key) for x in o]
        if isinstance(o, dict):
            return {k: walk(v, k) for k, v in o.items()}
        return o
    return walk(data), n


def data_problems(data, key=None) -> list[str]:
    """problems() over every string value of parsed JSON."""
    if isinstance(data, str):
        return [] if key in SKIP_KEYS else problems(data)
    if isinstance(data, list):
        return [p for x in data for p in data_problems(x, key)]
    if isinstance(data, dict):
        return [p for k, v in data.items() for p in data_problems(v, k)]
    return []


_JSON_STR = re.compile(r'"(?:[^"\\]|\\.)*"')


def _fix_json_text(text: str) -> tuple[str, int]:
    """Rewrite only the string tokens that change, so indent, key order, escapes and the trailing newline stay."""
    n = 0

    def one(m: re.Match) -> str:
        nonlocal n
        tok = m.group(0)
        if not (any(c in tok for c in UNSAFE_GLYPHS) or "\\u" in tok):
            return tok
        if re.match(r"\s*:", text[m.end():m.end() + 8]):
            return tok  # a key
        key = re.search(r'"([^"\\]*)"\s*:\s*\[?\s*$', text[max(0, m.start() - 60):m.start()])
        if key and (key.group(1) in SKIP_KEYS or key.group(1).endswith("_id")):
            return tok
        value = json.loads(tok)
        new = fix_text(value)
        if new == value:
            return tok
        n += 1
        return json.dumps(new, ensure_ascii=tok.isascii() and "\\u" in tok)  # escapes in, escapes out
    return _JSON_STR.sub(one, text), n


def _fix_py_text(text: str) -> tuple[str, int]:
    """String literals of a Python file that hold unsafe glyphs (f-strings are reported, not rewritten)."""
    n = 0
    lines = text.splitlines(keepends=True)
    edits = []
    for tok in tokenize.generate_tokens(io.StringIO(text).readline):
        if tok.type == tokenize.STRING and _hit(tok.string):
            prefix = re.match(r"[A-Za-z]*", tok.string).group(0).lower()
            if "f" in prefix:
                print(f"  not rewritten (f-string) line {tok.start[0]}: {tok.string[:60]}", file=sys.stderr)
                continue
            new = fix_text(tok.string)
            if new != tok.string and tok.start[0] == tok.end[0]:
                edits.append((tok.start, tok.end, new))
    for (r, c0), (_, c1), new in sorted(edits, reverse=True):
        line = lines[r - 1]
        lines[r - 1] = line[:c0] + new + line[c1:]
        n += 1
    return "".join(lines), n


def fix_file_text(path: Path, text: str) -> tuple[str, int]:
    """(new text, strings changed) for one file by its kind: .json, .py or markdown/text."""
    if path.suffix == ".json":
        return _fix_json_text(text)
    if path.suffix == ".py":
        return _fix_py_text(text)
    record: list = []
    new = _fix(text, record)  # a note counts one per repaired run
    return new, len(record) if new != text else 0


def repair_file(path: Path) -> int:
    """fix_file_text on a file, written back only if something changed (formatting kept). → strings changed."""
    text = Path(path).read_text(encoding="utf-8")
    if not (any(c in text for c in UNSAFE_GLYPHS) or "\\u" in text):
        return 0
    new, n = fix_file_text(Path(path), text)
    if n and new != text:
        Path(path).write_text(new, encoding="utf-8")
    return n


def files_under(paths: list[str]):
    for raw in paths:
        p = Path(raw)
        if not p.is_absolute():
            p = ROOT / p if (ROOT / p).exists() else p
        if p.is_file():
            yield p
        elif p.is_dir():
            for f in sorted(p.rglob("*")):
                if f.is_file() and f.suffix in {".json", ".md", ".py", ".txt"} and ".git" not in f.parts:
                    yield f


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--write", action="store_true", help="rewrite files in place (default: list only)")
    ap.add_argument("paths", nargs="*", help=f"files or folders (default {' '.join(DEFAULTS)})")
    args = ap.parse_args(argv)
    total = changed_files = 0
    for f in files_under(args.paths or DEFAULTS):
        try:
            text = f.read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError):
            continue
        if not (any(c in text for c in UNSAFE_GLYPHS) or "\\u" in text):
            continue
        new, n = fix_file_text(f, text)
        if not n:
            continue
        total += n
        changed_files += 1
        print(f"{f.relative_to(ROOT) if f.is_relative_to(ROOT) else f}: {n} string{'s' * (n != 1)}")
        if not args.write:
            for p in problems(text)[:3]:
                print("   ", p)
        else:
            f.write_text(new, encoding="utf-8")
    print(f"{total} strings in {changed_files} files {'rewritten' if args.write else 'would change (dry run: add --write)'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
