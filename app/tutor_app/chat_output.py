"""Bounded semantic chat documents and their provider-independent Markdown rendering.

The lexer visits each wire character once. Only complete flat blocks are decoded and
rendered; a later protocol error leaves that visible prefix explicitly incomplete.
"""
from __future__ import annotations

import html
import json
import re

from markdown_it import MarkdownIt

from .output_format import _math_escapes, _spans, normalise_visual


_DOCUMENT_LIMIT = 4 * 1024 * 1024
_BLOCK_LIMIT = 256 * 1024
_BLOCKS_LIMIT = 256
_KINDS = ("paragraph", "heading", "bullet", "step", "equation", "code")
_UNSAFE = re.compile(r"[\x00-\x08\x0b-\x1f\x7f-\x9f\ud800-\udfff\u202a-\u202e\u2066-\u2069]")
_MARKDOWN = MarkdownIt("commonmark")
_STEP_WRAPPER = re.compile(r"\A {0,3}(?:[0-9]{1,9}[.)]|Step[ \t]*[0-9]{1,9}:)[ \t]+(?=\S)")


class DocumentError(ValueError):
    """The structured answer is invalid, incomplete or exceeds its storage bounds."""


def document_schema(speech: bool = False) -> dict:
    """Return a fresh shallow schema accepted by each provider's native transport."""
    properties = {
        "blocks": {
            "type": "array", "minItems": 1, "maxItems": _BLOCKS_LIMIT,
            "items": {
                "type": "object", "additionalProperties": False,
                "properties": {
                    "kind": {"type": "string", "enum": list(_KINDS)},
                    "text": {"type": "string", "minLength": 1, "maxLength": _BLOCK_LIMIT},
                },
                "required": ["kind", "text"],
            },
        },
    }
    if speech:
        properties["speech"] = {"type": "string", "maxLength": _DOCUMENT_LIMIT}
    return {"type": "object", "additionalProperties": False, "properties": properties,
            "required": ["blocks", "speech"] if speech else ["blocks"]}


def document_instructions(speech: bool = False) -> str:
    """The shared transport and content rules, independent of a provider's API."""
    example = {"blocks": [
        {"kind": "step", "text": "Substitute the mass and acceleration."},
        {"kind": "equation", "text": r"F=2\times3=6\,\mathrm{N}"},
        {"kind": "code", "text": 'def square(x):\n    return x * x\nrecord = {"reply": "x_1^2"}'},
    ]}
    if speech:
        example["speech"] = "The force is six newtons."
    return (
        "Return exactly one JSON object matching this schema, with no narration or fences:\n"
        + json.dumps(document_schema(speech=speech), ensure_ascii=False)
        + "\nUse semantic blocks: paragraph for one logical idea; heading for a short label; "
        "bullet for one list item; step for one justified numbered step; equation for mathematical "
        "source without outer delimiters; code only for requested literal code, JSON or source notation. "
        "Never use code blocks for mathematical working: use inline LaTeX or equation blocks. "
        "Preserve requested code line breaks and quotes exactly; do not HTML-encode literal code. "
        "The application supplies headings, list markers, step numbering, blank lines, math "
        "delimiters and safe code fences. Do not put those wrappers in block text. "
        "Do not include Step n: labels, introductory filler or repeated explanations in block text. "
        "Use heading blocks for short descriptive labels without mathematics. "
        "Write inline mathematics as $...$ using canonical LaTeX, for example $x e^{-x}$. "
        "Equation blocks contain raw LaTeX without outer dollar signs or other delimiters. "
        "Prose may contain inline emphasis, links, code and mathematics, but cannot contain "
        "nested Markdown blocks, multiple paragraphs or inline bullet glyphs. Use separate "
        "blocks for separate ideas and list items. Put an associated equation immediately after "
        "its step; numbering continues across equations and restarts after other block kinds. "
        "Preserve signs, charges, bounds, indices, units, percentages and literal source. "
        "Use precise task-scaled A-Level explanations: definitions include qualifications; "
        "explanations give causal links and conditions; calculations show formula, substitution, "
        "result, units and requested precision; comparisons use parallel criteria. "
        "Respect supplied assessment evidence and protect answers to OPEN practice questions. "
        "Do not claim an overview is an exhaustive official mark scheme. "
        "The document limit is 4 MiB, with at most 256 blocks and 256 KiB per block. "
        "Escape JSON strings correctly and exclude unsafe controls."
        r' Double each LaTeX backslash in JSON: {"kind":"equation","text":"\\frac{1}{2}"}.'
        + (" Put read-aloud text only in the separate required speech string. "
           "Speech is never visual block content." if speech else " Do not include a speech field.")
        + "\nThis example illustrates block syntax; select only kinds needed by the actual request."
        + "\nExample document:\n" + json.dumps(example, separators=(",", ":"))
    )


def _safe(text: str) -> None:
    # CRLF is conventional literal source; a lone carriage return can overwrite terminal text.
    if _UNSAFE.search(text.replace("\r\n", "\n")):
        raise DocumentError("Unsafe control or Unicode surrogate in document text")


def _repair_math_controls(kind: str, text: str) -> str:
    """Recover only known TeX commands in mathematical source, as visual output does."""
    if kind == "equation":
        return _math_escapes(text)
    if kind == "code":
        return text
    return "".join(_math_escapes(span.source) if span.kind == "math" else span.source
                   for span in _spans(text, partial=False))


def _prose(text: str, *, heading: bool = False) -> str:
    """Validate layout outside the existing protected maths, literals and URL spans."""
    skeleton = []
    for span in _spans(text, partial=False):
        if span.kind == "text":
            skeleton.append(span.source)
        elif span.kind == "literal" and (
                "\n" in span.source or "\r" in span.source
                or any(token.type in {"fence", "code_block", "html_block"}
                       for token in _MARKDOWN.parse(span.source))):
            raise DocumentError("Prose contains a Markdown code or HTML block; use a code block")
        elif span.kind == "literal" and span.source.startswith("`"):
            # The visual scanner holds an unmatched backtick tail as literal for
            # streaming. Markdown displays that tail as prose, so only a real,
            # matched code span can protect its contents from layout validation.
            children = _MARKDOWN.parseInline(span.source)[0].children or []
            matched = len(children) == 1 and children[0].type == "code_inline"
            skeleton.append("PROTECTED" if matched else span.source)
        elif span.kind == "literal" and (link := re.match(
                r"!?\[((?:\\.|[^\]\\\n])*)\]\(", span.source)):
            children = _MARKDOWN.parseInline(span.source)[0].children or []
            if any(child.type in {"link_open", "image"} for child in children):
                # A label is visible prose; only its destination is opaque.
                # This source-label grammar cannot itself contain a nested
                # complete link, so validation does not recurse on nesting.
                _prose(link[1])
                skeleton.append("PROTECTED")
            else:
                skeleton.append(span.source)
        elif span.display:
            raise DocumentError("Display mathematics requires an equation block")
        else:
            if span.kind == "literal":
                _safe(html.unescape(span.source))
            skeleton.append("PROTECTED")
    plain = "".join(skeleton).replace("\r\n", "\n")
    # A quoted glyph names the symbol, without presenting a run of list items.
    visible = re.sub("“•”|‘•’|\"•\"|'•'", "QUOTED_SYMBOL", html.unescape(plain))
    _safe(visible)
    if ("•" in visible or re.search(r"\n[ \t]*\n", plain)
            or re.search(r"(?m)^\s*\|.*\|\s*$", plain)):
        raise DocumentError("Prose must contain one idea without inline bullets or nested blocks")
    # A single numbered heading label remains inline inside the renderer's bold
    # wrapper. Keep its meaningful number while validating every other block rule.
    numbered_heading = (heading and "\n" not in plain
                        and re.match(r"^ {0,3}\d+[.)][ \t]+\S", plain))
    tokens = _MARKDOWN.parse("LABEL " + plain if numbered_heading else plain)
    if any(token.type not in {"paragraph_open", "inline", "paragraph_close"} for token in tokens):
        raise DocumentError("Prose contains nested Markdown structure; use semantic blocks")
    # normalise_visual protects the same spans and retains the established maths fallback.
    return normalise_visual(text.strip()).strip()


def _render(kind: str, text: str, step: int) -> str:
    if kind == "code":
        longest = max((len(match[0]) for match in re.finditer(r"`+", text)), default=0)
        fence = "`" * max(3, longest + 1)
        return fence + "\n" + text + ("" if text.endswith("\n") else "\n") + fence
    if kind == "equation":
        source = text.strip()
        # Delimiters anywhere could close the wrapper and inject prose or lists.
        if re.search(r"(?<!\\)(?:\\\\)*(?:\$|\\[\[\]()])", source):
            raise DocumentError("Equation text must omit outer delimiters")
        return normalise_visual("$$\n" + source + "\n$$").strip()
    prose = _prose(text, heading=kind == "heading")
    if kind == "heading":
        if "\n" in prose:
            raise DocumentError("Heading must be one short label")
        return "**" + prose + "**"
    if kind in {"bullet", "step"}:
        marker = "- " if kind == "bullet" else f"{step}. "
        return marker + prose.replace("\n", "\n" + " " * len(marker))
    return prose


class DocumentDecoder:
    """Incrementally validate a flat document and emit complete canonical blocks.

    ``finish`` is mandatory. A visible prefix alone never establishes successful
    completion. ``document`` and ``wire`` are available only after that check.
    """

    def __init__(self, speech: bool = False):
        self._speech_enabled = speech
        self._state = "start"
        self._top_seen: set[str] = set()
        self._blocks: list[dict] = []
        self._block: dict = {}
        self._key = ""
        self._spoken = ""
        self._pieces: list[str] = []
        self._step = 0
        self._bytes = 0
        self._block_bytes: int | None = None
        self._string: list[str] | None = None
        self._escape = False
        self._failed = False
        self._finished = False
        self._document: dict | None = None
        self._wire: str | None = None

    @property
    def document(self) -> dict:
        if not self._finished:
            raise DocumentError("Document is not finished")
        # A caller must not mutate the validated object used for subsequent history.
        return {"blocks": [dict(block) for block in self._document["blocks"]],
                **({"speech": self._spoken} if self._speech_enabled else {})}

    @property
    def wire(self) -> str:
        if not self._finished:
            raise DocumentError("Document is not finished")
        return self._wire

    def feed(self, chunk: str) -> str:
        if self._failed or self._finished:
            raise DocumentError("Document decoder is already failed or finished")
        try:
            if not isinstance(chunk, str):
                raise DocumentError("Document chunks must be strings")
            try:
                self._bytes += len(chunk.encode("utf-8"))
            except UnicodeEncodeError as exc:
                raise DocumentError("Unsafe Unicode surrogate in document wire") from exc
            if self._bytes > _DOCUMENT_LIMIT:
                raise DocumentError("Document exceeds 4 MiB limit")
            emitted = []
            for char in chunk:
                if self._block_bytes is not None:
                    self._block_bytes += len(char.encode("utf-8"))
                    if self._block_bytes > _BLOCK_LIMIT:
                        raise DocumentError("Block exceeds 256 KiB limit")
                if self._string is not None:
                    self._string.append(char)
                    if self._escape:
                        self._escape = False
                    elif char == "\\":
                        self._escape = True
                    elif char == '"':
                        try:
                            value = json.loads("".join(self._string))
                        except (ValueError, RecursionError) as exc:
                            raise DocumentError("Malformed JSON string") from exc
                        self._string = None
                        if not (self._state == "block_value" and self._key == "text"):
                            _safe(value)
                        self._token("string", value, emitted)
                    elif ord(char) < 32:
                        raise DocumentError("Unescaped control in JSON string")
                elif char == '"':
                    self._string = ['"']
                    self._escape = False
                elif char in "{}[]:,":
                    self._token(char, char, emitted)
                elif char not in " \t\r\n":
                    raise DocumentError("Unexpected character in structured document")
            return "".join(emitted)
        except DocumentError:
            self._failed = True
            raise

    def _token(self, token: str, value: str, emitted: list[str]) -> None:
        state = self._state
        if state == "start" and token == "{":
            self._state = "top_key"
        elif state in {"top_key", "next_top_key"} and token == "string":
            allowed = {"blocks", "speech"} if self._speech_enabled else {"blocks"}
            if value not in allowed or value in self._top_seen:
                raise DocumentError("Unknown or duplicate document field")
            self._top_seen.add(value)
            self._key = value
            self._state = "top_colon"
        elif state == "top_colon" and token == ":":
            self._state = "blocks_start" if self._key == "blocks" else "speech"
        elif state == "speech" and token == "string":
            self._spoken = value
            self._state = "top_end"
        elif state == "blocks_start" and token == "[":
            self._state = "block_start"
        elif state == "block_start" and token == "{":
            if len(self._blocks) >= _BLOCKS_LIMIT:
                raise DocumentError("Document exceeds 256 blocks limit")
            self._block = {}
            self._block_bytes = 1
            self._state = "block_key"
        elif state in {"block_key", "next_block_key"} and token == "string":
            if value not in {"kind", "text"} or value in self._block:
                raise DocumentError("Unknown or duplicate block field")
            self._key = value
            self._state = "block_colon"
        elif state == "block_colon" and token == ":":
            self._state = "block_value"
        elif state == "block_value" and token == "string":
            if self._key == "kind" and value not in _KINDS:
                raise DocumentError("Unknown block kind")
            if self._key == "text" and not value.strip():
                raise DocumentError("Block text must be nonempty")
            self._block[self._key] = value
            self._state = "block_end"
        elif state == "block_end" and token == ",":
            self._state = "next_block_key"
        elif state == "block_end" and token == "}":
            if set(self._block) != {"kind", "text"}:
                raise DocumentError("Block requires kind and text")
            kind, text = self._block["kind"], self._block["text"]
            text = _repair_math_controls(kind, text)
            _safe(text)
            if kind == "step" and "\n" not in text and "\r" not in text:
                # Native E4B emits its own leading number inside semantic steps.
                # Remove one explicit ordinal wrapper only; validate the remainder
                # normally. Restrict recovery to one line so a later numbered
                # item cannot become a CommonMark lazy paragraph continuation.
                text = _STEP_WRAPPER.sub("", text, count=1)
                if _STEP_WRAPPER.match(text):
                    # Reject chained wrappers rather than admitting history that
                    # loses another prefix on replay. No repeated repair loop.
                    raise DocumentError("Step wrapper must not be repeated")
            self._step = self._step + 1 if kind == "step" else self._step if kind == "equation" else 0
            shown = _render(kind, text, self._step)
            emitted.append(("\n\n" if self._pieces else "") + shown)
            self._pieces.append(shown)
            self._blocks.append({"kind": kind, "text": text})
            self._block_bytes = None
            self._state = "array_end"
        elif state == "array_end" and token == ",":
            self._state = "block_start"
        elif state == "array_end" and token == "]":
            self._state = "top_end"
        elif state == "top_end" and token == ",":
            self._state = "next_top_key"
        elif state == "top_end" and token == "}":
            required = {"blocks", "speech"} if self._speech_enabled else {"blocks"}
            if self._top_seen != required or not self._blocks:
                raise DocumentError("Document is missing required fields or blocks")
            self._state = "done"
        else:
            raise DocumentError("Malformed structured document")

    def finish(self) -> tuple[str, str]:
        if self._failed:
            raise DocumentError("Document decoder has failed")
        if self._state != "done" or self._string is not None:
            self._failed = True
            raise DocumentError("Incomplete structured document")
        if not self._finished:
            self._document = {"blocks": self._blocks,
                              **({"speech": self._spoken} if self._speech_enabled else {})}
            self._wire = json.dumps(self._document, ensure_ascii=False, separators=(",", ":"))
            self._finished = True
        return "\n\n".join(self._pieces), self._spoken
