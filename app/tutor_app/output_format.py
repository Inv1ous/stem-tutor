"""Canonical AI prose and protected, bounded mathematical spans for both displays."""
from __future__ import annotations

import functools
import html
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
_BARE_GROUP_SCRIPT = re.compile(r"(?<!\w)[A-Za-zΑ-Ωα-ω][_^]\(")
_COMMAND = re.compile(r"\\[A-Za-z]+")
_ARITY = {"frac": 2, "dfrac": 2, "tfrac": 2, "dv": 2, "pdv": 2, "SI": 2, "qty": 2,
          **dict.fromkeys(("sqrt", "ce", "mathrm", "text", "mathbf", "mathit", "mathbb", "mathcal",
                           "texttt", "textrm", "textsf", "textbf", "textit", "textnormal", "mathsf", "mathtt",
                           "boldsymbol", "vec", "hat", "bar", "overline", "underline", "unit", "num", "si", "pu"), 1)}
_ARGUMENT_COMMANDS = frozenset(_ARITY)
_ARGUMENT_END = re.compile(r"\s*(?:\}|$)")
_SCRIPT_VALUE = re.compile(r"\s*[^}\s_^]")
# A model sometimes writes maths as HTML character references (&#x222B; &#8747; &int;). Decode them
# before the maths is scanned, but never a reference that only names a control or format character.
_ENTITY = re.compile(r"&(?:#[0-9]{1,7}|#[xX][0-9A-Fa-f]{1,6}|[A-Za-z][A-Za-z0-9]{1,31});")
_ENTITY_TAIL = re.compile(r"&(?:#[0-9]{0,7}|#[xX][0-9A-Fa-f]{0,6}|[A-Za-z][A-Za-z0-9]{0,31})\Z")
_ENTITY_PASSES = 3
_FORMAT = re.compile(r"[\x00-\x08\x0b-\x1f\x7f-\x9f\u200b-\u200f\u202a-\u202e\u2066-\u2069"
                     r"\ud800-\udfff\ufff9-\ufffb]")
_SCRIPTED_SYMBOL = re.compile(r"([∫∑∏∮])(?=[_^])")
_SYMBOL_COMMAND = {"∫": r"\int", "∑": r"\sum", "∏": r"\prod", "∮": r"\oint"}


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
        elif value in ("_", "^") and not _SCRIPT_VALUE.match(body, token.end()):
            return False
        elif value[1:] in _ARGUMENT_COMMANDS and _ARGUMENT_END.match(body, token.end()):
            # A command immediately before its group's end has no argument.
            # Preserve this definite source error in both displays; valid TeX
            # unsupported only by the terminal must still reach MathJax.
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


def _math_symbols(body: str) -> str:
    """Attach a decoded big operator's scripts to the command the renderer understands."""
    return _SCRIPTED_SYMBOL.sub(lambda match: _SYMBOL_COMMAND[match[1]], body)


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
                body = _math_symbols(_math_escapes(text[start:close])).strip()
                span = _Span("math" if _well_formed(body) else "fallback", text[i:end], body, display)
            else:
                end = boundary
                pending = partial and end == len(text) and end - i <= _PENDING_LIMIT
                span = _Span("pending" if pending else "fallback", text[i:end], display=display)
        elif text[i] == "\\" and not _escaped(text, i) and _COMMAND.match(text, i):
            paragraph = re.search(r"\n\s*\n", text[i:])
            boundary = i + paragraph.start() if paragraph else len(text)
            end, complete = _bare_end(text[:boundary], i)
            if partial and end == len(text) and end - i <= _PENDING_LIMIT:
                span = _Span("pending", text[i:end])
            else:
                span = _Span("math" if complete and _well_formed(text[i:end]) else "fallback",
                             text[i:end], _math_symbols(text[i:end]))
        elif (script := _BARE_GROUP_SCRIPT.match(text, i)):
            from .stem_math import render_math

            close = _group_end(text, script.end() - 1, "(", ")")
            if close is None:
                newline = text.find("\n", script.end())
                end = newline if newline >= 0 else len(text)
                pending = partial and end == len(text) and end - i <= _PENDING_LIMIT
                span = _Span("pending" if pending else "fallback", text[i:end])
            else:
                end = close
                group = text[script.end():close - 1]
                body = _math_symbols(text[i:i + 2] + "{" + group + "}")
                valid = bool(group.strip()) and not any(ch in group for ch in "()\n")
                if text[end:end + 1] in ("_", "^"):
                    # A chained script needs a larger grammar; retain its complete source.
                    tail = re.match(r"\S+", text[end:])
                    end += len(tail[0])
                    valid = False
                valid = valid and _well_formed(group) and render_math(body) is not None
                span = _Span("math" if valid else "fallback", text[i:end], body)
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


def _fallback(source: str, display: bool = True) -> str:
    """Keep unparseable source recoverable: a box for display maths, inline for a phrase."""
    if not display and "\n" not in source and "\r" not in source:
        runs = [len(m.group()) for m in re.finditer(r"`+", source)]
        fence = "`" * (max(runs, default=0) + 1)
        return f"Unformatted expression: {fence}{source}{fence}"
    runs = [len(m.group()) for m in re.finditer(r"`+", source)]
    fence = "`" * max(3, max(runs, default=0) + 1)
    return f"**Unformatted expression:**\n\n{fence}text\n{source}\n{fence}\n\n"


def _control_fallback(source: str) -> str:
    """Keep the original source recoverable without putting its controls in terminal text."""
    return "**Unformatted source (JSON-escaped):**\n\n```json\n" + json.dumps(source, ensure_ascii=True) + "\n```\n\n"


def _unquoted_prose(text: str) -> str:
    """Mask quoted examples without changing source offsets."""
    return re.sub(
        r'''(?<![\w\\])(?:"(?:\\.|[^"\\])*"|'(?:\\.|[^'\\])*'|"[^"]*"|“[^”]*”|‘[^']*'|‘[^’]*’)''',
        lambda match: " " * len(match[0]), text)


def _protected_ranges(text: str) -> dict[int, int]:
    """Code, link and quoted source whose bytes a model's entity text must not rewrite."""
    ranges = dict(_literal_ranges(text))
    i = 0
    while i < len(text):
        if i in ranges:
            i = ranges[i]
            continue
        if text[i] == "`" and not _escaped(text, i):
            run = re.match(r"`+", text[i:]).group()
            match = re.search(r"(?<!`)" + re.escape(run) + r"(?!`)", text[i + len(run):])
            end = i + len(run) + match.end() if match else len(text)
            ranges[i] = end
            i = end
            continue
        i += 1
    masked = _unquoted_prose(text)
    quoted, start = [], None
    for i, (source, shown) in enumerate(zip(text, masked)):
        if source != shown and start is None:
            start = i
        elif source == shown and start is not None:
            quoted.append((start, i))
            start = None
    if start is not None:
        quoted.append((start, len(text)))
    for begin, end in quoted:
        if not any(begin < stop and other < end for other, stop in ranges.items()):
            ranges[begin] = end
    return ranges


def _unescape(text: str) -> str:
    """Decode character references until stable, keeping any that only name a control."""
    def one(match):
        ref = match[0]
        numeric = re.fullmatch(r"&#(?:[xX]([0-9A-Fa-f]{1,6})|([0-9]{1,7}));", ref)
        if numeric:
            code = int(numeric[1], 16) if numeric[1] else int(numeric[2])
            if code > 0x10FFFF or _FORMAT.match(chr(code)):
                return ref
        value = html.unescape(ref)
        return ref if _FORMAT.search(value) else value

    for _ in range(_ENTITY_PASSES):
        decoded = _ENTITY.sub(one, text)
        if decoded == text:
            break
        text = decoded
    return text


def _decode_entities(text: str, *, partial: bool = False) -> str:
    """Decode a model's HTML entities outside protected source before maths is scanned.

    ``&lt;script&gt;`` becomes terminal text only; a reference naming a control or format
    character stays literal so the existing unsafe-control path still sees the source.
    """
    code = _protected_ranges(text)
    pieces, plain = [], 0
    for start in sorted(code):
        end = code[start]
        if start > plain:
            pieces.append(_unescape(text[plain:start]))
        pieces.append(text[start:end])
        plain = max(plain, end)
    if plain < len(text):
        tail = text[plain:]
        if partial:
            # A reference still arriving must wait rather than render as a fallback box.
            tail = _ENTITY_TAIL.sub("", tail)
        pieces.append(_unescape(tail))
    return "".join(pieces)


def _inline_bullets(text: str) -> str:
    """Recover a legacy prose list only with repeated sentence-level list evidence.

    Maths, code and links have already been replaced by opaque spans. Quotes are
    excluded from this recovery too, so a literal bullet example is not evidence.
    """
    paragraphs = re.split(r"(\n[ \t]*\n)", text)
    for index, paragraph in enumerate(paragraphs):
        if "•" not in paragraph:
            continue
        visible = _unquoted_prose(paragraph)
        boundaries = list(re.finditer(
            r"(?<=[.!?:])[ \t]+•[ \t]+(?=[A-Z][A-Za-z-]*[ \t]+[a-z])", visible))
        if len(boundaries) < 2:
            continue
        for boundary in reversed(boundaries):
            paragraph = paragraph[:boundary.start()] + "\n\n- " + paragraph[boundary.end():]
        paragraphs[index] = paragraph
    return "".join(paragraphs)


def _labelled_steps(text: str) -> str:
    """Separate a strong run of consecutive Step n: instructions without rewriting it.

    Literals and maths are already opaque. Ordinary references, quotations and
    existing list/quote structure are not evidence of a new instruction sequence.
    """
    if not re.search(r"(?i)step[ \t]", text):
        return text
    paragraphs = re.split(r"(\n[ \t]*\n)", text)
    label = re.compile(r"(?i)(?<![\w\\])(?:\*\*|__)?Step[ \t]+([1-9][0-9]{0,2})[ \t]*:(?:\*\*|__)?[ \t]+(?=\S)")
    for index in range(0, len(paragraphs), 2):
        paragraph = paragraphs[index]
        if re.match(r"[ \t]*(?:[-*>]|[0-9]+[.)])[ \t]", paragraph):
            continue
        matches = list(label.finditer(_unquoted_prose(paragraph)))
        if len(matches) < 2:
            continue
        numbers = [int(match[1]) for match in matches]
        if numbers != list(range(numbers[0], numbers[0] + len(numbers))):
            continue
        # Every label needs its own instruction boundary. A later ordinal
        # embedded in "compare with Step 2:" remains an ordinary reference.
        separated, previous_end = True, 0
        for label_index, match in enumerate(matches):
            before = paragraph[previous_end:match.start()]
            punctuation = ('.', '!', '?', ':') if label_index == 0 else ('.', '!', '?')
            if ((label_index and not before.strip())
                    or before.strip() and not (before.rstrip().endswith(punctuation)
                                               or re.search(r"\n[ \t]*$", before))):
                separated = False
                break
            previous_end = match.end()
        if not separated:
            continue
        pieces, at = [], 0
        for match in matches:
            if match.start() > at:
                pieces.append(paragraph[at:match.start()].rstrip())
            at = match.start()
        pieces.append(paragraph[at:])
        paragraphs[index] = "\n\n".join(piece for piece in pieces if piece)
    return ''.join(paragraphs)


def _orphan_punctuation(text: str, keys: frozenset[str]) -> str:
    """Drop a comma or stray punctuation left where a block expression was removed."""
    lead = "|".join(map(re.escape, sorted(keys, key=len, reverse=True)))
    pattern = re.compile(r"(?m)(\A|\n\n" + ("|" + lead if lead else "")
                         + r")[ \t]*[,;:][ \t]*(?=\S|\n)")
    return pattern.sub(r"\1", text)


def _prose(text: str, keys: frozenset[str] = frozenset()) -> str:
    text = _labelled_steps(_inline_bullets(text.replace("\r\n", "\n")))
    text = _orphan_punctuation(text, keys)
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
    # A single author-supplied prose newline is meaningful in both adapters.
    # Code/math/link spans are opaque here; whitespace inside them stays exact.
    spaced = "\n\n".join(paragraphs)

    def hard_break(match):
        at = match.start()
        if match[0] == "\n" and spaced[at - 1] == "\\" and not _escaped(spaced, at - 1):
            return match[0]  # This is already a CommonMark backslash hard break.
        return "  \n"

    return re.sub(r"(?<=\S)[ \t]*\n(?=[^\n])", hard_break, spaced)


def _canonical(span: _Span) -> str:
    if span.kind == "pending":
        return ""
    if span.kind == "fallback":
        return _fallback(span.source, span.display)
    if span.kind == "math":
        return "$$\n" + span.body + "\n$$" if span.display else "$" + span.body + "$"
    return span.source


def _join_equation_prefixes(skeleton: str, opaque: dict[str, str]) -> str:
    """Fold a bare ``W =`` line into the display equation it introduces."""
    for key, value in list(opaque.items()):
        if not value.startswith("$$\n"):
            continue
        pattern = re.compile(r"(?m)^([A-Za-z][A-Za-z0-9_]{0,15})[ \t]*=[ \t]*\n+"
                             + re.escape(key) + r"(?!\w)")
        match = pattern.search(skeleton)
        if not match or re.match(re.escape(match[1]) + r"[ \t]*=", value[3:]):
            continue
        opaque[key] = "$$\n" + match[1] + " = " + value[3:]
        skeleton = skeleton[:match.start()] + key + skeleton[match.end():]
    return skeleton


@functools.lru_cache(maxsize=256)
def normalise_visual(text: str, *, partial: bool = False) -> str:
    """Canonicalise only AI visual text; code and mathematical source remain recoverable."""
    original = text = text or ""
    text = _decode_entities(text, partial=partial)
    if _UNSAFE_CONTROL.search(text):
        # Preserve source before layout/strip can erase a control; known maths repairs stay scoped.
        for span in _spans(text, partial):
            source = _math_escapes(span.source) if span.kind == "math" else span.source
            if span.kind != "pending" and _UNSAFE_CONTROL.search(source.replace("\r\n", "\n")):
                return _control_fallback(original)
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
    result = _prose(_join_equation_prefixes("".join(skeleton), opaque),
                    frozenset(key for key, value in opaque.items() if "\n" in value))
    for key, value in opaque.items():
        if value.endswith("\n"):
            # Keep protected code exact while normalising the gap outside its closing fence.
            trailing = len(value) - len(value.rstrip("\n"))
            result = re.sub(re.escape(key) + r"[ \t]*\n+", key + "\n" * max(0, 2 - trailing), result)
        result = result.replace(key, value)
    return _control_fallback(original) if _UNSAFE_CONTROL.search(result.replace("\r\n", "\n")) else result


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
                out.append(_fallback(span.source, span.display))
            else:
                # Markdown must not interpret multiplication, subscripts or brackets as its own syntax.
                shown = re.sub(r"([\\`*_\[\]<>])", r"\\\1", shown)
                shown = shown.replace("\n", "  \n")
                out.append("\n\n" + shown + "\n\n" if span.display else shown)
        else:
            out.append(_canonical(span))
    result = "".join(out).replace("\r\n", "\n")
    return _control_fallback(text) if _UNSAFE_CONTROL.search(result) else result
