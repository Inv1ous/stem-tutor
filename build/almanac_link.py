"""Link the Almanac planner to the tutor: put the sync script into the planner page (run again to update it).

The tutor writes `<planner>.tutor.js` beside the planner (tutorlib/report.py, `almanac_push`). The block added here
loads that file when the page opens and every half minute after, and merges it into the planner's own state
(build/almanac_link.js). A copy of the page as it was is kept in `.backup/` beside it first.

  python build/almanac_link.py [path to the planner]     then: python build/plan.py && python build/publish.py
"""
from __future__ import annotations

import shutil
import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
START, END = "<!-- stem-tutor-sync:start -->", "<!-- stem-tutor-sync:end -->"


def block(page: Path) -> str:
    js = (ROOT / "build/almanac_link.js").read_text(encoding="utf-8").replace("__FILE__", page.with_suffix(".tutor.js").name)
    return f"{START}\n<script>\n{js}</script>\n{END}"


def link(page: Path) -> bool:
    """Put the block into the page, or bring an older one up to date. Returns whether the page changed."""
    html = page.read_text(encoding="utf-8")
    if START in html:
        new = html[:html.index(START)] + block(page) + html[html.index(END) + len(END):]
    else:
        at = html.rindex("</body>")
        new = html[:at] + block(page) + "\n" + html[at:]
    if new == html:
        return False
    backup = page.parent / ".backup" / f"{page.stem}.{date.today()}{page.suffix}"
    if not backup.exists():  # the first copy of the day is the page as the learner had it
        backup.parent.mkdir(exist_ok=True)
        shutil.copy2(page, backup)
    page.write_text(new, encoding="utf-8")
    return True


if __name__ == "__main__":
    import plan
    target = Path(sys.argv[1]) if len(sys.argv) > 1 else plan.ALMANAC
    print(f"{target}: " + ("linked to the tutor" if link(target) else "already linked"))
