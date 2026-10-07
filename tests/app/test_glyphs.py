"""Every character the tutor draws is in the bundled font, one cell wide, and never turns into a colour emoji
(which macOS Terminal draws two cells wide over its neighbour)."""
import ast
import asyncio
import hashlib
import html
import json
import re
import struct
import unicodedata
from pathlib import Path

import pytest

from test_tui import app_for
from tutor_app.texmath import to_terminal

REPO = Path(__file__).resolve().parents[2]
APP = REPO / "app" / "tutor_app"
FONTS = APP / "fonts"
# Unicode 16.0 emoji-data.txt, property Emoji, its non-ASCII part below U+10000 (everything from U+1F000 is emoji)
EMOJI = ("00A9 00AE 203C 2049 2122 2139 2194-2199 21A9-21AA 231A-231B 2328 23CF 23E9-23F3 23F8-23FA 24C2 25AA-25AB "
         "25B6 25C0 25FB-25FE 2600-2604 260E 2611 2614-2615 2618 261D 2620 2622-2623 2626 262A 262E-262F 2638-263A "
         "2640 2642 2648-2653 265F-2660 2663 2665-2666 2668 267B 267E-267F 2692-2697 2699 269B-269C 26A0-26A1 26A7 "
         "26AA-26AB 26B0-26B1 26BD-26BE 26C4-26C5 26C8 26CE-26CF 26D1 26D3-26D4 26E9-26EA 26F0-26F5 26F7-26FA 26FD "
         "2702 2705 2708-270D 270F 2712 2714 2716 271D 2721 2728 2733-2734 2744 2747 274C 274E 2753-2755 2757 "
         "2763-2764 2795-2797 27A1 27B0 27BF 2934-2935 2B05-2B07 2B1B-2B1C 2B50 2B55 3030 303D 3297 3299")


def _ranges(spec: str) -> set[int]:
    out = set()
    for part in spec.split():
        a, _, b = part.partition("-")
        out.update(range(int(a, 16), int(b or a, 16) + 1))
    return out


EMOJI_CODES = _ranges(EMOJI)


def font_chars(path: Path) -> set[int]:
    """The characters a TrueType font draws (its cmap: format 12, or format 4)."""
    data = path.read_bytes()
    tables = {data[12 + 16 * i:16 + 16 * i]: struct.unpack(">I", data[20 + 16 * i:24 + 16 * i])[0]
              for i in range(struct.unpack(">H", data[4:6])[0])}
    cmap = tables[b"cmap"]
    subtables = {struct.unpack(">HH", data[cmap + 4 + 8 * i:cmap + 8 + 8 * i]):
                 cmap + struct.unpack(">I", data[cmap + 8 + 8 * i:cmap + 12 + 8 * i])[0]
                 for i in range(struct.unpack(">H", data[cmap + 2:cmap + 4])[0])}
    chars: set[int] = set()
    for key in ((3, 10), (0, 4), (0, 6)):
        if key in subtables and struct.unpack(">H", data[subtables[key]:subtables[key] + 2])[0] == 12:
            at = subtables[key]
            for g in range(struct.unpack(">I", data[at + 12:at + 16])[0]):
                start, end, glyph = struct.unpack(">III", data[at + 16 + 12 * g:at + 28 + 12 * g])
                chars.update(c for c in range(start, end + 1) if glyph + c - start)
            return chars
    at = subtables[(3, 1)]  # format 4
    segs = struct.unpack(">H", data[at + 6:at + 8])[0] // 2
    ends = struct.unpack(f">{segs}H", data[at + 14:at + 14 + 2 * segs])
    starts = struct.unpack(f">{segs}H", data[at + 16 + 2 * segs:at + 16 + 4 * segs])
    deltas = struct.unpack(f">{segs}h", data[at + 16 + 4 * segs:at + 16 + 6 * segs])
    offsets_at = at + 16 + 6 * segs
    for i in range(segs):
        for c in range(starts[i], ends[i] + 1):
            ro = struct.unpack(">H", data[offsets_at + 2 * i:offsets_at + 2 * i + 2])[0]
            if ro == 0:
                glyph = (c + deltas[i]) & 0xFFFF
            else:
                at_glyph = offsets_at + 2 * i + ro + 2 * (c - starts[i])
                glyph = struct.unpack(">H", data[at_glyph:at_glyph + 2])[0]
                glyph = (glyph + deltas[i]) & 0xFFFF if glyph else 0
            if glyph and c != 0xFFFF:
                chars.add(c)
    return chars


COVERED = font_chars(FONTS / "JuliaMono-Regular.ttf")


def problems(text: str, maths: bool = False) -> set[str]:
    """Maths tables (texmath) may hold its private markers, and symbols such as ↔ that are emoji only when a font
    lacks them: JuliaMono draws them as text."""
    bad = set()
    for ch in set(text):
        c = ord(ch)
        if c < 0x80 or (maths and 0xE000 <= c <= 0xF8FF):
            continue
        why = ("emoji" if c >= 0x1F000 or (c in EMOJI_CODES and not maths) or c == 0xFE0F else
               "two cells wide" if unicodedata.east_asian_width(ch) in "WF" else
               "a double-line box (drawn badly by Terminal)" if 0x2550 <= c <= 0x256C else
               "not in JuliaMono" if c not in COVERED else None)
        if why:
            bad.add(f"U+{c:04X} {ch} {why}")
    return bad


def test_the_bundled_font_is_the_pinned_release_with_its_licence():
    want = {"JuliaMono-Regular.ttf": "40a07da0d1601215eb6b89312eb44128a3e2f36675d3e1f518264bd391fc7023",
            "JuliaMono-Bold.ttf": "a886d817cbd02fb7b646c3eb722de572bf6819ad223d66d64dbef33207964fea",
            "JuliaMono-RegularItalic.ttf": "35260252fa576b3e2ae6cda538475e6fa78a053eade7784518b53f0a5dbaa526"}
    for name, digest in want.items():
        assert hashlib.sha256((FONTS / name).read_bytes()).hexdigest() == digest, name
    assert "SIL Open Font License" in (FONTS / "OFL.txt").read_text()
    assert len(COVERED) > 10000 and {ord(c) for c in "θΔ∑∫√≤≥⇌⦵−×₁²⁺𝐅╭─╮│╰╯█░▁▔"} <= COVERED


def _ui_strings(path: Path):
    tree = ast.parse(path.read_text(encoding="utf-8"))
    docstrings = {id(node.body[0].value) for node in ast.walk(tree)
                  if isinstance(node, (ast.Module, ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef))
                  and node.body and isinstance(node.body[0], ast.Expr) and isinstance(node.body[0].value, ast.Constant)}
    for node in ast.walk(tree):
        if isinstance(node, ast.Constant) and isinstance(node.value, str) and id(node) not in docstrings:
            yield node.value


@pytest.mark.parametrize("path", sorted(APP.glob("*.py")), ids=lambda p: p.name)
def test_every_character_in_the_app_is_in_the_font_one_cell_wide_and_no_emoji(path):
    found = set()
    for s in _ui_strings(path):
        found |= problems(s, maths=path.name == "texmath.py")
    assert not found, sorted(found)


def _screen_text(app) -> str:
    return html.unescape("".join(re.findall(r">([^<>]*)</text>", app.export_screenshot()))).replace("\xa0", " ")


def test_every_screen_draws_only_characters_of_the_font(tmp_path, monkeypatch):
    from tutor_app.screens import HelpScreen, InsightsScreen, ProgressScreen, SessionScreen, SettingsScreen
    app, v = app_for(tmp_path, monkeypatch)

    async def go():
        async with app.run_test(size=(120, 40)) as pilot:
            await pilot.pause()
            seen = {"home": _screen_text(app)}
            for name, screen in (("settings", SettingsScreen()), ("help", HelpScreen()), ("insights", InsightsScreen()),
                                 ("progress", ProgressScreen()), ("session", SessionScreen({"mode": "autopilot",
                                                                                              "minutes": 50}))):
                app.push_screen(screen)
                await pilot.pause()
                await pilot.pause()
                seen[name] = _screen_text(app)
                app.pop_screen()
                await pilot.pause()
            await app.ai.close()
            return seen
    for name, text in asyncio.run(go()).items():
        assert not problems(text), (name, sorted(problems(text)))


def _pack_strings():
    for p in sorted((REPO / "build" / "out" / "packs").rglob("*.json")):
        stack = [json.loads(p.read_text(encoding="utf-8"))]
        while stack:
            x = stack.pop()
            if isinstance(x, str):
                yield p.name, x
            elif isinstance(x, dict):
                stack.extend(x.values())
            elif isinstance(x, list):
                stack.extend(x)


@pytest.mark.skipif(not (REPO / "build" / "out" / "packs").exists(), reason="no published packs in this checkout")
def test_all_published_content_shows_in_the_font_without_raw_latex():
    found = {}
    for name, s in _pack_strings():
        if not ("$" in s or "\\(" in s):
            continue
        out = to_terminal(s)
        bad = problems(out) | ({"a backslash"} if "\\" in out else set())
        if bad:
            found.setdefault(name, set()).update(bad)
    assert not found, {k: sorted(v) for k, v in found.items()}
