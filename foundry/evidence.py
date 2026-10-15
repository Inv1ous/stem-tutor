"""Proof that a worker used what it was given, not a hope that it did.

Workers (Claude and Codex alike) often skip the learner's PDF library and web search unless something makes them look.
Three things make them look, for the foundry and refine alike:
  - the bundle carries the library's hits for the chapter (build/bundle.py), regenerated before a drafter or scout runs;
  - the worker's prompt says what is there and that it must be used (`prompt_lines`);
  - when the worker finishes, its log is read for real tool use (`from_log`), and a drafter or scout that never opened
    the library (when it has pages for the chapter) or never searched the web (when it may) has not finished (`missing`):
    the pass is retried one tier up, and a pass that keeps failing is given up (see refine.give_up).
`FOUNDRY_EVIDENCE=0` switches the check off (tests).
"""
from __future__ import annotations

import os
import re
import subprocess
import sys
from pathlib import Path

LIBRARY_ROLES = {"drafter", "scout"}  # must open the library when it has pages for the chapter
WEB_ROLES = {"drafter", "scout"}      # must search the web at least once when they are allowed to
HERE = Path(__file__).resolve()
REPO = HERE.parents[1]


def from_log(text: str) -> dict[str, int]:
    """Real tool use found in a worker's log: {"library": n, "web": n}. Claude logs are a stream of JSON events,
    Codex logs show each command as `/bin/zsh -lc '…' in <dir>` and each search as `web search: …`."""
    if text.lstrip().startswith("{"):
        return {"web": len(re.findall(r'"name":"(?:WebSearch|WebFetch)"', text)),
                "library": len(re.findall(r'"command":"[^"]*library\.py', text))}
    return {"web": len(re.findall(r"(?m)^web search:", text)),
            "library": len(re.findall(r"(?m)^/bin/\w+ -lc .*library\.py", text))}


def _library():
    build = str(REPO / "build")
    if build not in sys.path:
        sys.path.insert(0, build)
    import library
    return library


def material() -> tuple[int, int]:
    """(PDFs, folders) in the learner's library; (0, 0) when it is empty or cannot be read."""
    try:
        files = list(_library().pdfs(_library().lib_root()))
        return len(files), len({f.parent for f in files})
    except Exception:  # noqa: BLE001 - a library problem must never stop a worker's result being collected
        return 0, 0


def library_hits(sub: str) -> int:
    try:
        return sum(len(rows) for _, _, rows in _library().hits_for(sub))
    except Exception:  # noqa: BLE001
        return 0


def missing(role: str, sub: str, cfg: dict, log: Path | str | None) -> list[str]:
    """What the worker should have used and did not, as messages for its next attempt. Empty when all is well."""
    if os.environ.get("FOUNDRY_EVIDENCE") == "0" or role not in (LIBRARY_ROLES | WEB_ROLES) or not log:
        return []
    try:
        seen = from_log(Path(log).read_text(errors="ignore"))
    except OSError:
        return []
    out = []
    if role in LIBRARY_ROLES and not seen["library"] and (n := library_hits(sub)):
        out.append(f"the learner's library has {n} pages for this chapter (listed under 'Library hits' in the bundle) and you "
                   "did not open it: run `.venv/bin/python build/library.py for <chapter>` and `text <pdf> --pages a-b`, use "
                   "what helps (paraphrase, cite file and page) and say what you used")
    if role in WEB_ROLES and role in cfg.get("web", []) and not seen["web"]:
        out.append("you may search the web and did not: search at least once for a fact, example or diagram idea the "
                   "library lacks (official exam-board or university sources; paraphrase, never paste)")
    return out


def prompt_lines(role: str, sub: str, cfg: dict) -> list[str]:
    """What the worker is told it has, added to its short prompt."""
    out = []
    if role in (LIBRARY_ROLES | {"refiner", "adjudicator", "fixer"}):
        pdfs, folders = material()
        if pdfs:
            out.append(f"The learner's library has {pdfs} PDFs in {folders} folders. The bundle ends with the pages that match "
                       f"this chapter: open the useful ones (`.venv/bin/python build/library.py text <pdf> --pages a-b`) and use "
                       f"what helps" + (" — you must, the run is not accepted otherwise." if role in LIBRARY_ROLES else "."))
    if role in cfg.get("web", []):
        out.append("You may search the web: use it at least once for what the library lacks" +
                   (" — you must, the run is not accepted otherwise." if role in WEB_ROLES else "."))
    return out


def refresh_bundle(root: Path, py: str, sub: str) -> None:
    """The chapter's bundle, made again so it has the newest link names, diagram hints and library hits."""
    import time
    made = root / "build/work/bundles" / f"{sub}.md"
    if made.exists() and time.time() - made.stat().st_mtime < 1200:
        return
    try:
        subprocess.run([py, str(REPO / "build/bundle.py"), sub], cwd=root, capture_output=True, timeout=300)
    except (OSError, subprocess.TimeoutExpired):
        pass
