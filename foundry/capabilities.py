"""Is everything the workers are meant to use actually there? Run by `foundry doctor`, `refine doctor` and at the start of
every `step`, so a missing tool stops the run with a plain message instead of silently producing chapters without
diagrams, figures or library use.

check() returns [(ok, what, how to fix, level)] with level "hard" (workers cannot do their job without it: the step
refuses to start workers) or "soft" (reported only)."""
from __future__ import annotations

import importlib.util
import json
import os
import shutil
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]


def _has(binary: str) -> bool:
    return bool(binary) and (Path(binary).exists() or shutil.which(binary) is not None)


def check(cfg: dict | None = None, root: Path | None = None) -> list[tuple[bool, str, str, str]]:
    cfg = cfg or json.loads((REPO / "foundry/config.json").read_text())
    rows: list[tuple[bool, str, str, str]] = []
    for tool in ("pdftotext", "pdftoppm", "pdfinfo"):
        rows.append((shutil.which(tool) is not None or Path("/opt/homebrew/bin", tool).exists(), f"poppler `{tool}` (library search, figures)",
                     "brew install poppler", "hard"))
    rows.append((importlib.util.find_spec("matplotlib") is not None, "matplotlib (renders the SVG diagrams)",
                 ".venv/bin/python -m pip install matplotlib", "hard"))
    rows.append((importlib.util.find_spec("PIL") is not None, "Pillow (trims cropped figures)",
                 ".venv/bin/python -m pip install pillow", "soft"))
    codex = os.environ.get("FOUNDRY_CODEX") or shutil.which("codex") or "/Applications/ChatGPT.app/Contents/Resources/codex-cli/bin/codex"
    claude = os.environ.get("FOUNDRY_CLAUDE") or shutil.which("claude") or ""
    rows.append((_has(codex), "the Codex command", "install the ChatGPT app (it bundles codex)", "soft"))
    rows.append((_has(claude), "the Claude command", "install Claude Code", "soft"))
    rows.append((_has(codex) or _has(claude), "at least one allowance to run workers on", "install Codex or Claude Code", "hard"))
    web = cfg.get("web", [])
    rows.append((bool(web), f"web search switched on for roles ({', '.join(web) or 'none'})", "add a \"web\" list to the config", "soft"))
    build = str(REPO / "build")
    if build not in sys.path:
        sys.path.insert(0, build)
    try:
        import bundle
        has_sections = all(hasattr(bundle, n) for n in ("_link_lines", "_diagram_lines", "_library_lines"))
    except Exception:  # noqa: BLE001
        has_sections = False
    rows.append((has_sections, "bundles carry link names, diagram hints and library hits", "build/bundle.py is out of date", "hard"))
    try:
        import library
        files = list(library.pdfs(library.lib_root()))
        rows.append((True, f"sources library readable ({len(files)} PDFs)", "", "soft"))
        if not files:
            rows.append((False, "the sources library has PDFs", "drop PDFs into sources/library/<any folder>", "soft"))
    except Exception as e:  # noqa: BLE001
        rows.append((False, f"sources library readable ({type(e).__name__})", "see build/library.py", "hard"))
    for mod, why in (("content_checks", "option-letter and LaTeX checks"), ("glyphs", "sub/superscript repair"),
                     ("diagram_hints", "diagram hints")):
        rows.append((importlib.util.find_spec(mod) is not None or (REPO / "build" / f"{mod}.py").exists(), f"{why} ({mod}.py)", "restore build/" + mod + ".py", "hard"))
    try:
        sys.path.insert(0, str(REPO / "plugin/stem-tutor/skills/tutor/scripts"))
        from tutorlib import speech  # noqa: F401
        rows.append((True, "spoken-maths converter (tutorlib.speech)", "", "soft"))
    except Exception as e:  # noqa: BLE001
        rows.append((False, f"spoken-maths converter ({type(e).__name__})", "see tutorlib/speech.py", "soft"))
    try:
        sys.path.insert(0, str(REPO / "app"))
        from tutor_app import tts
        rows.append((True, "Kokoro read-aloud: " + tts.status(), "tutor tts setup (audio is only made once it is set up)", "soft"))
    except Exception:  # noqa: BLE001
        rows.append((False, "Kokoro read-aloud module", "see app/tutor_app/tts.py", "soft"))
    return rows


def report(rows=None) -> tuple[str, bool]:
    """(plain text, no hard failures)."""
    rows = rows if rows is not None else check()
    lines = [f"{'ok ' if ok else ('NO ' if level == 'hard' else 'no ')} {what}" + ("" if ok or not fix else f"   → {fix}") for ok, what, fix, level in rows]
    return "\n".join(lines), all(ok or level != "hard" for ok, _, _, level in rows)


def preflight() -> str | None:
    """None when every hard requirement is met, else the plain message `step` prints before refusing to start workers."""
    if os.environ.get("FOUNDRY_PREFLIGHT") == "0":
        return None
    text, ok = report()
    return None if ok else "not starting workers: something they need is missing.\n" + "\n".join(l for l in text.splitlines() if l.startswith("NO "))
