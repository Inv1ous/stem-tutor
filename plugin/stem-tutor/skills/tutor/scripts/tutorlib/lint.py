"""Obsidian render linter: catches the markdown/LaTeX/Mermaid mistakes that make a note render as raw text.

Targets Obsidian 1.14 (MathJax 4, `$`/`$$` delimiters only; Mermaid 11). Each finding:
{"line": n, "rule": id, "message": text}.
"""
from __future__ import annotations

import re
from pathlib import Path

FENCE = re.compile(r"^\s*((?:>\s*)*)(```|~~~)\s*([\w-]*)")
CALLOUT = re.compile(r"^\s*>")
UNSUPPORTED = re.compile(r"\\(SI|si|qty|unit|num|ang|chemfig|usepackage|documentclass|tikz|begin\{tikzpicture\})\b")
MERMAID_TYPES = {"graph", "flowchart", "sequenceDiagram", "classDiagram", "stateDiagram", "stateDiagram-v2",
                 "erDiagram", "gantt", "pie", "mindmap", "timeline", "xychart-beta", "quadrantChart", "journey",
                 "gitGraph", "block-beta", "sankey-beta"}
LABEL = re.compile(r"\w+\s*(\[\[?|\(\(?|\{\{?|>)([^\]\)\}]*?(?:\([^\)]*\))?[^\]\)\}]*)(\]\]?|\)\)?|\}\}?)")
EMBED = re.compile(r"!\[\[([^\]|#]+)|!\[[^\]]*\]\(([^)\s]+)\)")


def _strip_prefix(line: str) -> tuple[str, str]:
    m = re.match(r"^(\s*(?:>\s?)*)", line)
    assert m  # the pattern can match the empty string, so it always matches
    return m.group(1), line[m.end():]


def _braces_ok(math: str) -> bool:
    depth = 0
    for ch in re.sub(r"\\[{}]", "", math):
        depth += ch == "{"
        depth -= ch == "}"
        if depth < 0:
            return False
    return depth == 0


def _check_math(math: str, n: int, out: list) -> None:
    if not _braces_ok(math):
        out.append({"line": n, "rule": "braces", "message": "unbalanced { } in math"})
    m = UNSUPPORTED.search(math)
    if m:
        out.append({"line": n, "rule": "unsupported-macro",
                    "message": f"\\{m.group(1)} is not available in Obsidian MathJax; use plain LaTeX or an SVG asset"})


def _mermaid(lines: list[str], start: int, out: list) -> None:
    body = [l for l in lines if l.strip()]
    if not body:
        return
    kind = body[0].split()[0]
    if kind not in MERMAID_TYPES:
        out.append({"line": start, "rule": "mermaid-type", "message": f"unknown Mermaid diagram type {kind!r}"})
        return
    if kind not in ("graph", "flowchart"):
        return
    for i, l in enumerate(lines, start + 1):
        for m in LABEL.finditer(l):
            label = m.group(2)
            if label and not label.startswith('"') and re.search(r"[()\[\]{}]", label):
                out.append({"line": i, "rule": "mermaid-label", "message": f'quote labels with brackets: ["{label}"]'})
        if re.search(r"(-->|---|==>|-\.->)\s*end\b|\bend\s*(-->|---|==>)", l):
            out.append({"line": i, "rule": "mermaid-reserved", "message": "'end' is reserved; rename the node"})


def lint(md: str, vault_root: Path | None = None) -> list[dict]:
    out: list[dict] = []
    lines = md.split("\n")
    fence = None  # (lang, start, buffer)
    display = None  # (start line, prefixed, buffer)
    prev_callout = before_callout = False
    for n, raw in enumerate(lines, 1):
        fm = FENCE.match(raw)
        if fence:
            if fm and fm.group(2) == fence[3]:
                if fence[0] == "mermaid":
                    _mermaid(fence[2], fence[1], out)
                fence = None
            else:
                fence[2].append(_strip_prefix(raw)[1])
            continue
        if fm and display is None:
            fence = (fm.group(3), n, [], fm.group(2))
            continue
        prefix, text = _strip_prefix(raw)
        is_callout = ">" in prefix
        stripped = text.strip()
        if display is not None:
            if display[1] and not is_callout:
                out.append({"line": n, "rule": "callout-math", "message": "every line of $$ inside a callout needs '> '"})
            if stripped.endswith("$$"):
                _check_math("\n".join(display[2] + [stripped[:-2]]), display[0], out)
                closing_line = n
                display_start, display_prefixed = display[0], display[1]
                display = None
                nxt = lines[closing_line] if closing_line < len(lines) else ""
                if not display_prefixed and before_callout and CALLOUT.match(nxt):
                    out.append({"line": display_start, "rule": "callout-math",
                                "message": "$$ block splits a callout; prefix its lines with '> '"})
            else:
                display[2].append(stripped)
            prev_callout = is_callout
            continue
        if stripped.startswith("$$") and not (len(stripped) > 4 and stripped.endswith("$$")):
            display = (n, is_callout, [stripped[2:]])
            before_callout = prev_callout
            prev_callout = is_callout
            continue
        prev_callout = is_callout
        line = re.sub(r"`[^`]*`", "", text).replace("\\$", "")
        segments = []
        one_line_display = re.findall(r"\$\$(.+?)\$\$", line)
        segments += one_line_display
        line = re.sub(r"\$\$(.+?)\$\$", "", line)
        if line.count("$") % 2:
            out.append({"line": n, "rule": "unbalanced-dollar", "message": "odd number of $ (escape currency as \\$)"})
        else:
            for m in re.finditer(r"\$([^$]*)\$", line):
                seg = m.group(1)
                if seg != seg.strip():
                    out.append({"line": n, "rule": "inline-space", "message": "no space right after opening or before closing $"})
                segments.append(seg)
                if stripped.startswith("|") and "|" in seg:
                    out.append({"line": n, "rule": "table-pipe", "message": "| inside math breaks tables; use \\lvert \\rvert or \\vert"})
        prose = re.sub(r"\$[^$]*\$", "", line)
        if re.search(r"\\[\(\)\[\]]", prose):
            out.append({"line": n, "rule": "delimiter", "message": "Obsidian ignores \\( \\) and \\[ \\]; use $...$ and $$...$$"})
        for seg in segments:
            _check_math(seg, n, out)
        for tag in re.findall(r"<svg\b[^>]*>", text):
            if "viewbox" not in tag.lower():
                out.append({"line": n, "rule": "svg-viewbox", "message": "inline <svg> needs a viewBox to scale"})
        if vault_root is not None:
            for m in EMBED.finditer(text):
                target = (m.group(1) or m.group(2)).strip()
                if not target.startswith("http") and not (Path(vault_root) / target).exists():
                    out.append({"line": n, "rule": "missing-embed", "message": f"embedded file not found: {target}"})
    if fence:
        out.append({"line": fence[1], "rule": "fence", "message": "code fence never closed"})
    if display:
        out.append({"line": display[0], "rule": "unbalanced-dollar", "message": "$$ block never closed"})
    return out
