"""Canonical AI prose and protected, bounded mathematical spans for both displays."""
from __future__ import annotations

import functools
import json
import re
from dataclasses import dataclass

from markdown_it import MarkdownIt


_MARKDOWN = MarkdownIt("commonmark")
_PENDING_LIMIT = 2048
_UNSAFE_CONTROL = re.compile(r"[\x00-\x08\x0b-\x1f\x7f-\x9f]")
_URL = re.compile(r"(?:[A-Za-z][A-Za-z0-9+.-]*://|mailto:)[^\s<>`]+")
_FILE = re.compile(r"(?:[\w~.-]+/)*[\w-]+(?:_[\w-]+)*\.[A-Za-z][A-Za-z0-9]{0,8}\b")
_BARE_SCRIPT = re.compile(
    r"(?<![\w])(?:[A-Za-zΑ-Ωα-ω](?:(?:[_^](?:\{[^{}\n]+\}|[-+]?[A-Za-z0-9]+))|[₀-₉₊₋₌₍₎⁰¹²³⁴-⁹⁺⁻⁼⁽⁾ⁿⁱᵢₙₖ])+)(?!\w)")
_COMMAND = re.compile(r"\\[A-Za-z]+")
_ARITY = {"frac": 2, "dfrac": 2, "tfrac": 2, "dv": 2, "pdv": 2, "SI": 2, "qty": 2,
          **dict.fromkeys(("sqrt", "ce", "mathrm", "text", "mathbf", "mathit", "mathbb", "mathcal",
                           "boldsymbol", "vec", "hat", "bar", "overline", "underline", "unit", "num", "si", "pu"), 1)}


@dataclass(frozen=True)
class _Span:
    kind: str
    source: str
    body: str = ""
    display: bool = False


def _escaped(text: str, at: int) -> bool:
    i = at - 1
    while i >= 0 and text[i] == "\\":
        i -= 1
    return (at - i - 1) % 2 == 1


def _literal_ranges(text: str) -> dict[int, int]:
    """Protect Markdown code and links before looking for mathematical delimiters."""
    # Markdown normalises CR/LF only; str.splitlines would also split a JSON-decoded formfeed.
    offsets = [0, *(match.end() for match in re.finditer(r"\r\n?|\n", text))]
    if offsets[-1] != len(text):
        offsets.append(len(text))
    ranges = {offsets[t.map[0]]: offsets[min(t.map[1], len(offsets) - 1)]
              for t in _MARKDOWN.parse(text) if t.type in ("fence", "code_block", "html_block") and t.map}
    for match in re.finditer(r"(?m)^ {0,3}\[[^\]\n]+\]:[^\n]*(?:\n|$)", text):
        ranges[match.start()] = match.end()
    for match in re.finditer(r"!?\[(?:\\.|[^\]\\\n])*\]\(", text):
        end = _group_end(text, match.end() - 1, "(", ")")
        if end is not None:
            ranges[match.start()] = end
    return ranges


def _group_end(text: str, at: int, opening: str = "{", closing: str = "}") -> int | None:
    if at >= len(text) or text[at] != opening:
        return None
    depth = 0
    for i in range(at, len(text)):
        if _escaped(text, i):
            continue
        if text[i] == opening:
            depth += 1
        elif text[i] == closing:
            depth -= 1
            if not depth:
                return i + 1
    return None


def _bare_end(text: str, at: int) -> tuple[int, bool]:
    command = _COMMAND.match(text, at)
    assert command
    name, end = command.group()[1:], command.end()
    if name == "sqrt" and text[end:end + 1] == "[":
        option = _group_end(text, end, "[", "]")
        if option is None:
            return len(text), False
        end = option
    for _ in range(_ARITY.get(name, 0)):
        start = end
        while start < len(text) and text[start] in " \t":
            start += 1
        group = _group_end(text, start)
        if group is None:
            return (len(text) if text[start:start + 1] == "{" else max(end, start)), False
        end = group
    return end, True


def _price(text: str, start: int, end: int, delimiter: str) -> bool:
    if delimiter != "$" or not text[start + 1:start + 2].isdigit():
        return False
    body = text[start + 1:end if end >= 0 else len(text)].split("\n", 1)[0]
    explicit = bool(re.search(r"[\\_^={}]", body))
    if end >= 0 and text[end + 1:end + 2].isdigit() and not explicit:
        return True  # $5 and $6, $5-$6
    if explicit:
        return False
    return end < 0 or bool(re.search(r"\d\s+[A-Za-z]{2,}", body))


def _well_formed(body: str) -> bool:
    depth = 0
    for token in re.finditer(r"\\(?:[A-Za-z]+|.)|[{}_^]", body):
        value = token.group()
        if value == "{":
            depth += 1
        elif value == "}":
            depth -= 1
            if depth < 0:
                return False
        elif value in ("_", "^") and not re.match(r"\s*[^}\s_^]", body[token.end():]):
            return False
    return depth == 0


def _math_escapes(body: str) -> str:
    """Recover known TeX commands decoded as JSON controls inside maths, never inside code."""
    from .stem_math import is_known_command
    prefixes = {"\x08": "b", "\x0c": "f", "\r": "r", "\t": "t"}

    def restore(match):
        name = prefixes[match[0][0]] + match[1]
        command = "\\" + name
        return command if is_known_command(name) else match[0]

    return re.sub(r"[\x08\x0c\r\t]([A-Za-z]+)", restore, body)


def _spans(text: str, partial: bool):
    code = _literal_ranges(text)
    i, plain = 0, 0
    while i < len(text):
        span, end = None, i
        if i in code:
            end = code[i]
            span = _Span("literal", text[i:end])
        elif text[i] == "`" and not _escaped(text, i):
            run = re.match(r"`+", text[i:]).group()
            match = re.search(r"(?<!`)" + re.escape(run) + r"(?!`)", text[i + len(run):])
            end = i + len(run) + match.end() if match else len(text)
            span = _Span("literal", text[i:end])
        elif (url := _URL.match(text, i)):
            end = url.end()
            span = _Span("literal", text[i:end])
        elif (file := _FILE.match(text, i)):
            end = file.end()
            span = _Span("literal", text[i:end])
        elif text[i:i + 2] == "](" and not _escaped(text, i):
            end = _group_end(text, i + 1, "(", ")") or len(text)
            span = _Span("literal", text[i:end])
        elif text[i:i + 2] in (r"\$", r"\%") and not _escaped(text, i):
            end = i + 2
            span = _Span("literal", text[i:end] if text[i + 1] == "$" else "%")
        elif (text[i] == "$" or text[i:i + 2] in (r"\(", r"\[")) and not _escaped(text, i):
            opener = "$$" if text[i:i + 2] == "$$" else text[i:i + 2] if text[i] == "\\" else "$"
            closer = {"$": "$", "$$": "$$", r"\(": r"\)", r"\[": r"\]"}[opener]
            display = opener in ("$$", r"\[")
            start = i + len(opener)
            close = text.find(closer, start)
            while close >= 0 and _escaped(text, close):
                close = text.find(closer, close + len(closer))
            paragraph = re.search(r"\n\s*\n", text[start:]) if not display else None
            boundary = start + paragraph.start() if paragraph else len(text)
            # A closing dollar inside a literal region cannot close this expression.
            boundaries = [pos for pos in code if start <= pos < boundary]
            literal = re.search(r"(?<!\\)`|(?:[A-Za-z][A-Za-z0-9+.-]*://|mailto:)", text[start:boundary])
            if literal:
                boundaries.append(start + literal.start())
            if boundaries:
                boundary = min(boundary, *boundaries)
            if close >= boundary:
                close = -1
            if _price(text, i, close, opener):
                i += 1
                continue
            if close >= 0:
                end = close + len(closer)
                body = _math_escapes(text[start:close]).strip()
                span = _Span("math" if _well_formed(body) else "fallback", text[i:end], body, display)
            else:
                end = boundary
                pending = partial and end == len(text) and end - i <= _PENDING_LIMIT
                span = _Span("pending" if pending else "fallback", text[i:end])
        elif text[i] == "\\" and not _escaped(text, i) and _COMMAND.match(text, i):
            paragraph = re.search(r"\n\s*\n", text[i:])
            boundary = i + paragraph.start() if paragraph else len(text)
            end, complete = _bare_end(text[:boundary], i)
            if partial and end == len(text) and end - i <= _PENDING_LIMIT:
                span = _Span("pending", text[i:end])
            else:
                span = _Span("math" if complete else "fallback", text[i:end], text[i:end])
        elif (script := _BARE_SCRIPT.match(text, i)):
            end = script.end()
            span = _Span("math", text[i:end], text[i:end])
        elif partial and i == len(text) - 1 and text[i] == "\\":
            end, span = i + 1, _Span("pending", text[i:])
        if span is None:
            i += 1
            continue
        if i > plain:
            yield _Span("text", text[plain:i])
        yield span
        i = plain = max(i + 1, end)
    if plain < len(text):
        yield _Span("text", text[plain:])


def _fallback(source: str) -> str:
    runs = [len(m.group()) for m in re.finditer(r"`+", source)]
    fence = "`" * max(3, max(runs, default=0) + 1)
    return f"**Unformatted expression:**\n\n{fence}text\n{source}\n{fence}\n\n"


def _control_fallback(source: str) -> str:
    """Keep the original source recoverable without putting its controls in terminal text."""
    return "**Unformatted source (JSON-escaped):**\n\n```json\n" + json.dumps(source, ensure_ascii=True) + "\n```\n\n"


def _prose(text: str) -> str:
    text = text.replace("\r\n", "\n")
    text = re.sub(r"(?m)^ {0,3}#{1,6}\s+(.+?)\s*#*\s*$", r"**\1**", text)
    text = re.sub(r"(?m)^( {0,3})[+*•]\s+", r"\1- ", text)
    text = re.sub(r"(?m)^( {0,3})(\d+)\)\s+", r"\1\2. ", text)
    text = re.sub(r"(?m)(?<=\S)\n(?=(?:- |\d+\. ))", "\n\n", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    paragraphs = text.split("\n\n")
    for index, paragraph in enumerate(paragraphs):
        if len(paragraph.split()) <= 50 or re.match(r"\s*(?:[-*>]|\d+[.)])\s", paragraph):
            continue
        sentences = re.split(r"(?<=[.!?]) +(?=[A-Z])", paragraph)
        blocks, current = [], ""
        for sentence in sentences:
            if current and len((current + " " + sentence).split()) > 50:
                blocks.append(current)
                current = ""
            current += (" " if current else "") + sentence
        if current:
            blocks.append(current)
        paragraphs[index] = "\n\n".join(blocks)
    return "\n\n".join(paragraphs)


def _canonical(span: _Span) -> str:
    if span.kind == "pending":
        return ""
    if span.kind == "fallback":
        return _fallback(span.source)
    if span.kind == "math":
        return "$$\n" + span.body + "\n$$" if span.display else "$" + span.body + "$"
    return span.source


@functools.lru_cache(maxsize=256)
def normalise_visual(text: str, *, partial: bool = False) -> str:
    """Canonicalise only AI visual text; code and mathematical source remain recoverable."""
    text = text or ""
    if _UNSAFE_CONTROL.search(text):
        # Preserve source before layout/strip can erase a control; known maths repairs stay scoped.
        for span in _spans(text, partial):
            source = _math_escapes(span.source) if span.kind == "math" else span.source
            if span.kind != "pending" and _UNSAFE_CONTROL.search(source.replace("\r\n", "\n")):
                return _control_fallback(text)
    marker = "STEMOPAQUESPAN"
    while marker in text:
        marker += "X"
    opaque, skeleton = {}, []
    for span in _spans(text, partial):
        if span.kind == "text":
            skeleton.append(span.source)
        elif span.kind != "pending":
            key = marker + str(len(opaque)) + "END"
            opaque[key] = _canonical(span)
            skeleton.append(key)
    result = _prose("".join(skeleton))
    for key, value in opaque.items():
        if value.endswith("\n"):
            # Keep protected code exact while normalising the gap outside its closing fence.
            trailing = len(value) - len(value.rstrip("\n"))
            result = re.sub(re.escape(key) + r"\n+", key + "\n" * max(0, 2 - trailing), result)
        result = result.replace(key, value)
    return _control_fallback(text) if _UNSAFE_CONTROL.search(result.replace("\r\n", "\n")) else result


@functools.lru_cache(maxsize=256)
def terminal_visual(text: str, *, partial: bool = False) -> str:
    """Render recognised maths as Markdown-safe terminal text, keeping literal regions intact."""
    from .stem_math import render_math

    canonical = normalise_visual(text, partial=partial)
    if _UNSAFE_CONTROL.search(canonical.replace("\r\n", "\n")):
        return _control_fallback(text)
    out = []
    for span in _spans(canonical, partial):
        if span.kind == "math":
            shown = render_math(span.body)
            if shown is None:
                out.append(_fallback(span.source))
            else:
                # Markdown must not interpret multiplication, subscripts or brackets as its own syntax.
                shown = re.sub(r"([\\`*_\[\]<>])", r"\\\1", shown)
                shown = shown.replace("\n", "  \n")
                out.append("\n\n" + shown + "\n\n" if span.display else shown)
        else:
            out.append(_canonical(span))
    result = "".join(out).replace("\r\n", "\n")
    return _control_fallback(text) if _UNSAFE_CONTROL.search(result) else result
