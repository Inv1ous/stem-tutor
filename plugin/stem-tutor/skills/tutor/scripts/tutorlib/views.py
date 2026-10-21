"""Obsidian views the engine writes as you study (no AI needed).

- `Now.md`             what is on screen now, in full (question with figure, or the explanation), plus your notes
- `Lessons/<day>/<…>.md`  the whole session, mirrored live (questions appear before you answer, never with the key);
                       one folder for each day: `Lessons/2026-10-21/0939 Lesson - Electronegativity and bonding.md`
- `My Notes/<…>.md`    concise notes for a subtopic that grow one idea at a time as you learn it, with a progress map
- `Home.md`            dashboard: progress per subtopic, reviews due, recent sessions
"""
from __future__ import annotations

import re
from datetime import datetime
from pathlib import Path

from . import model
from .store import edit_text, write_text

STATUS = {"secure": "✅", "learning": "🟡", "gap": "🔴", "new": "⚪"}
_MAP_CLASS = {"secure": "done", "learning": "learning", "gap": "gap", "new": "todo"}


def callout(kind: str, title: str, body: str = "") -> str:
    lines = [f"> [!{kind}] {title}"]
    for line in body.strip("\n").split("\n") if body.strip() else []:
        lines.append(f"> {line}" if line.strip() else ">")
    return "\n".join(lines)


def _write(root: Path, rel: str, text: str) -> str:
    write_text(root / rel, text)
    return rel


def _safe(name: str) -> str:
    return re.sub(r'[\\/:*?"<>|#^\[\]]', "-", name).strip()


# ---------------- where notes live ----------------
def notes_rel(packs, subtopic: str) -> str:
    """My Notes mirrors the Subjects/ reference tree: My Notes/9702 Physics/02 Kinematics/2.1 Equations of motion.md"""
    pack = packs.pack(subtopic) or {}
    note = pack.get("note") or ""
    if note.startswith("Subjects/"):
        return "My Notes/" + note.split("/", 1)[1]
    st = packs.subtopics[subtopic]
    topic = packs.topics.get(st.get("topic", ""), {})
    return f"My Notes/{_safe(st['spec'])}/{_safe(topic.get('title', st.get('topic', '')))}/{_safe(subtopic + ' ' + st['title'])}.md"


def kc_status(state: dict, kc: str) -> str:
    k = state["kcs"].get(kc)
    if kc in state.get("gaps", []):
        return "gap"
    if not k or not k.get("n"):
        return "new"
    return "secure" if model.is_mastered(k) else "learning"


# ---------------- My Notes (progressive) ----------------
def _block(key: str) -> re.Pattern:
    return re.compile(rf"<!-- stem-tutor:{re.escape(key)} -->\n.*?<!-- /stem-tutor:{re.escape(key)} -->\n?", re.S)


def upsert(text: str, key: str, body: str, after: str | None = None) -> str:
    """Replace the managed block `key` (anything you write outside managed blocks is kept), or add it."""
    block = f"<!-- stem-tutor:{key} -->\n{body.rstrip()}\n<!-- /stem-tutor:{key} -->\n"
    pat = _block(key)
    if pat.search(text):
        return pat.sub(lambda _: block, text, count=1)
    if after and (m := _block(after).search(text)):
        return text[:m.end()] + "\n" + block + text[m.end():]
    return text.rstrip("\n") + "\n\n" + block


def concept_map(packs, state: dict, subtopic: str, current: str | None = None) -> str:
    kcs = [k for k, v in packs.kcs.items() if v["subtopic"] == subtopic]
    ids = {k: f"n{i}" for i, k in enumerate(kcs)}
    lines = ["```mermaid", "graph TD"]
    for k in kcs:
        label = packs.kcs[k]["title"].replace('"', "'")
        cls = "now" if k == current else _MAP_CLASS[kc_status(state, k)]
        lines.append(f'  {ids[k]}["{STATUS[kc_status(state, k)]} {label}"]:::{cls}')
    for k in kcs:
        for pre in packs.kcs[k].get("prereqs", []):
            if pre in ids:
                lines.append(f"  {ids[pre]} --> {ids[k]}")
    lines += ["  classDef done fill:#a6e3a1,stroke:#40a02b,color:#1e1e2e",
              "  classDef learning fill:#f9e2af,stroke:#df8e1d,color:#1e1e2e",
              "  classDef gap fill:#f38ba8,stroke:#d20f39,color:#1e1e2e",
              "  classDef todo fill:#cdd6f4,stroke:#7f849c,color:#1e1e2e",
              "  classDef now fill:#89b4fa,stroke:#1e66f5,color:#1e1e2e,stroke-width:3px", "```"]
    return "\n".join(lines)


def _merge_words(earlier: str, new: str | None) -> str:
    """Your earlier words, then what you wrote this time; a paragraph you wrote before is not added twice."""
    paragraphs = lambda t: [p.strip() for p in re.split(r"\n[ \t]*\n", t or "") if p.strip()]  # noqa: E731
    seen = {" ".join(p.split()) for p in paragraphs(earlier)}
    added = [p for p in paragraphs(new) if " ".join(p.split()) not in seen]
    return earlier + "\n\n" + "\n\n".join(added) if added else earlier


def notes_update(root: Path, packs, state: dict, subtopic: str, current: str | None = None,
                 node: dict | None = None) -> str:
    """Refresh the map; when `node` is given ({kc, note, own_words, mistakes}), add or update that idea's section."""
    rel = notes_rel(packs, subtopic)
    st = packs.subtopics[subtopic]
    kcs = [k for k, v in packs.kcs.items() if v["subtopic"] == subtopic]
    done = sum(kc_status(state, k) == "secure" for k in kcs)

    def edit(text: str | None) -> str:
        if text is None:
            text = (f"---\nsubtopic: {subtopic}\n---\n# {subtopic} {st['title']}\n\n"
                    "_These notes grow as you learn. Anything you add outside the grey markers is kept._\n")
        text = upsert(text, "map", f"> [!info] Progress: {done}/{len(kcs)} ideas secure\n\n"
                      + concept_map(packs, state, subtopic, current))
        if node:
            kc, new = node["kc"], node
            if (old := _block(f"node {kc}").search(text)):  # re-taught: keep what you wrote before, merge mistakes
                prev = old.group(0)
                # a blank line inside the callout is a bare ">", so paragraphs after the first are kept too
                if (w := re.search(r"> \[!quote\] In your words\n((?:>(?: .*)?\n?)+)", prev)):
                    earlier = "\n".join(l[2:] for l in w.group(1).rstrip("\n").split("\n"))
                    new = {**new, "own_words": _merge_words(earlier, new.get("own_words"))}
                if (m := re.search(r"> \[!warning\] Watch out \(your mistakes\)\n((?:> - .*\n?)+)", prev)):
                    earlier = [l[4:] for l in m.group(1).rstrip("\n").split("\n")]
                    new = {**new, "mistakes": list(dict.fromkeys(earlier + list(new.get("mistakes") or [])))}
            body = [f"## {STATUS[kc_status(state, kc)]} {packs.kcs[kc]['title']}", "", new.get("note", "").strip(), ""]
            if new.get("own_words"):
                body += [callout("quote", "In your words", new["own_words"]), ""]
            if new.get("mistakes"):
                body += [callout("warning", "Watch out (your mistakes)", "\n".join(f"- {m}" for m in new["mistakes"])), ""]
            order = [k for k in kcs if _block(f"node {k}").search(text)] + [kc]
            prev = next((k for k in reversed(order[:-1]) if kcs.index(k) < kcs.index(kc)), None) if kc in kcs else None
            text = upsert(text, f"node {kc}", "\n".join(body), after=f"node {prev}" if prev else "map")
        return text

    # the learner may save this page in Obsidian at any moment: the edit is redone on their save, never over it
    edit_text(root / rel, edit)
    return rel


def refresh_status(root: Path, packs, state: dict, subtopic: str) -> str | None:
    """Re-mark each idea heading with its current status (reviews change mastery), then redraw the map."""
    path = root / notes_rel(packs, subtopic)
    if not path.exists():
        return None

    def remark(text: str | None) -> str | None:
        if text is None:  # deleted meanwhile: nothing to remark
            return None
        for k in [k for k, v in packs.kcs.items() if v["subtopic"] == subtopic]:
            if m := _block(f"node {k}").search(text):
                block = re.sub(r"^## \S+ ", f"## {STATUS[kc_status(state, k)]} ", m.group(0), count=1, flags=re.M)
                text = text[:m.start()] + block + text[m.end():]
        return text

    edit_text(path, remark)
    return notes_update(root, packs, state, subtopic)


# ---------------- lesson log (live mirror of the session) ----------------
_FLAT_LESSON = re.compile(r"^(\d{4}-\d{2}-\d{2}) (\d{4} .+\.md)$")  # Lessons/2026-10-04 1539 Lesson - Stress and strain.md


def lesson_rel(root: Path, rel: str) -> str:
    """Where a lesson log is now. Logs began life in one flat list (`Lessons/2026-10-04 1539 …`) and now sit in a folder for
    their day (`Lessons/2026-10-04/1539 …`): a session saved before the move still finds its log after it."""
    if (root / rel).exists():
        return rel
    m = _FLAT_LESSON.match(Path(rel).name)
    if m and Path(rel).parent.name == "Lessons":
        moved = f"Lessons/{m[1]}/{m[2]}"
        if (root / moved).exists():
            return moved
    return rel


def organise_lessons(root: Path) -> list[tuple[str, str]]:
    """Move the old flat lesson logs into a folder for each day, and point the links to them at the new places. Never
    overwrites: a log whose new name is taken stays where it is. Returns [(old path, new path)] of what moved; the list is
    also kept in `.tutor/backups/lessons-moved-<date>.txt`, so a move can be undone."""
    folder = root / "Lessons"
    moved: list[tuple[str, str]] = []
    for f in sorted(folder.glob("*.md")) if folder.is_dir() else []:
        m = _FLAT_LESSON.match(f.name)
        if not m:
            continue
        target = folder / m[1] / m[2]
        if target.exists():
            continue
        target.parent.mkdir(parents=True, exist_ok=True)
        f.rename(target)
        moved.append((f.relative_to(root).as_posix(), target.relative_to(root).as_posix()))
    if not moved:
        return moved
    names = {old.removesuffix(".md"): new.removesuffix(".md") for old, new in moved}
    for note in root.rglob("*.md"):  # the notes that link to a log: Home.md, and any a learner wrote
        if any(p.startswith(".") for p in note.relative_to(root).parts) or note.relative_to(root).parts[0] == "Lessons":
            continue
        try:
            text = note.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue
        if "[[Lessons/" not in text:
            continue
        fixed = re.sub(r"\[\[(Lessons/[^\]|#\\]+)", lambda m: "[[" + names.get(m[1], m[1]), text)
        if fixed != text:
            write_text(note, fixed)
    log = root / ".tutor" / "backups" / f"lessons-moved-{datetime.now():%Y-%m-%d-%H%M%S}.txt"
    write_text(log, "\n".join(f"{old} -> {new}" for old, new in moved) + "\n")
    return moved


def recent_lessons(root: Path) -> list[str]:
    """Every lesson log, newest first, as paths from the vault's top (flat or in a day's folder)."""
    folder = root / "Lessons"
    return sorted((f.relative_to(root).as_posix() for f in folder.rglob("*.md")), key=lambda r: _sort_key(r),
                  reverse=True) if folder.is_dir() else []


def _sort_key(rel: str) -> str:
    """Date and time first, whether the log is `Lessons/2026-10-04 1539 name.md` or `Lessons/2026-10-04/1539 name.md`."""
    p = Path(rel)
    return f"{p.parent.name} {p.name}" if _FLAT_DAY.match(p.parent.name) else p.name


_FLAT_DAY = re.compile(r"^\d{4}-\d{2}-\d{2}$")


class LessonLog:
    def __init__(self, root: Path, rel: str):
        self.root, self.rel = root, rel

    @classmethod
    def create(cls, root: Path, title: str, now: datetime, header: str = "", name: str | None = None) -> "LessonLog":
        # the file is named after `name` (the title by default), cut short: a name over 255 bytes cannot be saved
        short = _safe(name or title).encode()[:120].decode(errors="ignore").strip()
        stem, k = f"Lessons/{now:%Y-%m-%d}/{now:%H%M} {short}", 1
        rel = f"{stem}.md"
        while (root / rel).exists():  # the same lesson restarted within the minute: never overwrite the first log
            k += 1
            rel = f"{stem} ({k}).md"
        log = cls(root, rel)
        _write(root, rel, f"# {title}\n_{now:%A %d %B %Y, %H:%M}_\n\n{header}".rstrip() + "\n")
        return log

    def add(self, md: str) -> None:
        path = self.root / self.rel
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "a", encoding="utf-8") as f:
            f.write("\n" + md.rstrip() + "\n")

    def tutor(self, md: str, title: str = "Tutor") -> None:
        self.add(callout("abstract", title, md))

    def you(self, text: str) -> None:
        self.add(callout("quote", "You", text))

    def question(self, view: dict, label: str = "") -> None:
        body = [view.get("stem", "")]
        if view.get("image"):
            body += ["", f"![[{view['image']}]]"]
        if view.get("options"):
            body += [""] + [f"**{k}.** {v}" for k, v in view["options"].items()]
        tags = " · ".join(t for t in (view.get("kind", "").upper(), view.get("source"), label,
                                      "no hints" if view.get("unassisted") else "") if t)
        self.add(callout("question", f"Q{view['n']} · {tags}", "\n".join(body)))

    def answer(self, fb: dict, your: str) -> None:
        dont_know = your.strip() in ("?", "don't know")
        kind = "question" if dont_know else ("success" if fb.get("correct") else "failure")
        title = f"Q{fb['n']} — " + ("I don't know" if dont_know else "correct ✓" if fb.get("correct") else
                                    "right value, a mark lost ✗" if fb.get("partial") else "incorrect ✗")
        body = [f"Your answer: {your}", f"Correct answer: {fb.get('answer', '')}"]
        if fb.get("detail"):
            body.append(f"Exam point: {fb['detail']}")
        if fb.get("explanation"):
            body += ["", fb["explanation"]]
        mis = fb.get("misconception")
        if mis:
            body += ["", f"**Trap:** {mis.get('statement', '')}", mis.get("refutation", "")]
        self.add(callout(kind, title, "\n".join(body)))


# ---------------- Now.md ----------------
def natural(text: str) -> list:
    """Sort key that puts 9701-1.2 before 9701-1.10 (a plain sort puts 1.10 right after 1.1)."""
    return [int(x) if x.isdigit() else x for x in re.split(r"(\d+)", str(text))]


SUBJECT_NAMES = {"chem": "Chemistry 9701", "phys": "Physics 9702", "math": "Maths"}


def chapter_name(packs, tid: str) -> str:
    """"3. Chemical bonding (AS)" for a Chemistry or Physics topic, "P1  Pure Mathematics 1" for a Maths module."""
    topic = packs.topics.get(tid, {})
    if topic.get("subject") in ("chem", "phys"):
        return f"{tid.split('-')[-1]}. {topic.get('title', tid)}" + (f" ({topic['level']})" if topic.get("level") else "")
    return f"{tid}  {topic.get('title', '')}".strip()


def subtopic_groups(packs, subs=None) -> list[dict]:
    """Subtopics as they should be listed: Chemistry, Physics, Maths; under each its chapters (Maths: modules) in syllabus
    order, and each chapter's subtopics in natural order. [{"subject", "name", "chapters": [{"id", "name", "subs"}]}].
    `subs`: only these (default: every subtopic that has a question pack)."""
    subs = list(subs) if subs is not None else [s for s in packs.subtopics if packs.pack(s)]
    order = {tid: i for i, tid in enumerate(packs.topics)}
    by_chapter: dict[str, list[str]] = {}
    for sub in sorted(subs, key=lambda x: (order.get(packs.subtopics.get(x, {}).get("topic", ""), 99), natural(x))):
        by_chapter.setdefault(packs.subtopics.get(sub, {}).get("topic", ""), []).append(sub)
    out: dict[str, dict] = {}
    for tid, chapter in by_chapter.items():
        subject = packs.topics.get(tid, {}).get("subject", "math")
        group = out.setdefault(subject, {"subject": subject, "name": SUBJECT_NAMES.get(subject, subject), "chapters": []})
        group["chapters"].append({"id": tid, "name": chapter_name(packs, tid), "subs": chapter})
    return [out[k] for k in ("chem", "phys", "math") if k in out] + [v for k, v in out.items() if k not in SUBJECT_NAMES]


def write_now(root: Path, header: str, blocks: list[str], notes: str | None = None) -> str:
    parts = ["# Now", f"_{header}_", ""] + [b.rstrip() + "\n" for b in blocks if b]
    if notes:
        parts += ["---", "## Your notes so far", "", f"![[{notes.removesuffix('.md')}]]", ""]
    return _write(root, "Now.md", "\n".join(parts))


def question_block(view: dict) -> str:
    body = [view.get("stem", "")]
    if view.get("image"):
        body += ["", f"![[{view['image']}]]"]
    if view.get("options"):
        body += [""] + [f"**{k}.** {v}" for k, v in view["options"].items()]
    tags = " · ".join(t for t in (view.get("kind", "").upper(), view.get("source"),
                                  f"{view.get('marks', 1)} mark" + ("s" if view.get("marks", 1) != 1 else ""),
                                  "no hints" if view.get("unassisted") else "") if t)
    return callout("question", f"Q{view['n']} · {tags}", "\n".join(body))


# ---------------- Home.md ----------------
def write_home(root: Path, packs, state: dict, now: datetime, recent: list[str] | None = None) -> str:
    due = model.due_kcs(state, now)
    lines = ["# STEM Tutor", f"_Updated {now:%d %b %Y %H:%M}_", "",
             f"**Reviews due:** {len(due)} · **Ideas secure:** "
             f"{sum(kc_status(state, k) == 'secure' for k in state['kcs'])}", "",
             "Start the tutor: double-click **Start Tutor.command** in this folder, or type `tutor` in Terminal. "
             "New here? Read [[How It Works]].", "", "## Your subjects"]
    for group in subtopic_groups(packs):  # a table for each subject, a bold row for each chapter, subtopics in order
        sec_all = [kc_status(state, k) == "secure" for k, v in packs.kcs.items()
                   if packs.subtopics.get(v["subtopic"], {}).get("topic") in {c["id"] for c in group["chapters"]}]
        lines += ["", f"### {group['name']} · {sum(sec_all)}/{len(sec_all)} ideas secure", "",
                  "| Subtopic | Progress | Notes |", "|---|---|---|"]
        for chapter in group["chapters"]:
            lines.append(f"| **{chapter['name']}** | | |")
            for sub in chapter["subs"]:
                kcs = [k for k, v in packs.kcs.items() if v["subtopic"] == sub]
                secure = sum(kc_status(state, k) == "secure" for k in kcs)
                started = sum(kc_status(state, k) != "new" for k in kcs)
                bar = "█" * round(8 * secure / max(1, len(kcs))) + "░" * (8 - round(8 * secure / max(1, len(kcs))))
                link = notes_rel(packs, sub).removesuffix(".md")
                notes = f"[[{link}\\|My notes]]" if (root / notes_rel(packs, sub)).exists() else "–"
                lines.append(f"| {sub} {packs.subtopics[sub]['title']} | `{bar}` {secure}/{len(kcs)}"
                             f"{' (started)' if started and not secure else ''} | {notes} |")
    if recent:
        lines += ["", "## Recent lessons", ""] + [f"- [[{r.removesuffix('.md')}]]" for r in recent[:8]]
    return _write(root, "Home.md", "\n".join(lines) + "\n")
