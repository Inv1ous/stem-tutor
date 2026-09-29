"""Obsidian views the engine writes as you study (no AI needed).

- `Now.md`             what is on screen now, in full (question with figure, or the explanation), plus your notes
- `Lessons/<…>.md`     the whole session, mirrored live (questions appear before you answer, never with the key)
- `My Notes/<…>.md`    concise notes for a subtopic that grow one idea at a time as you learn it, with a progress map
- `Home.md`            dashboard: progress per subtopic, reviews due, recent sessions
"""
from __future__ import annotations

import re
from datetime import datetime
from pathlib import Path

from . import model

STATUS = {"secure": "✅", "learning": "🟡", "gap": "🔴", "new": "⚪"}
_MAP_CLASS = {"secure": "done", "learning": "learning", "gap": "gap", "new": "todo"}


def callout(kind: str, title: str, body: str = "") -> str:
    lines = [f"> [!{kind}] {title}"]
    for line in body.strip("\n").split("\n") if body.strip() else []:
        lines.append(f"> {line}" if line.strip() else ">")
    return "\n".join(lines)


def _write(root: Path, rel: str, text: str) -> str:
    path = root / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
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


def notes_update(root: Path, packs, state: dict, subtopic: str, current: str | None = None,
                 node: dict | None = None) -> str:
    """Refresh the map; when `node` is given ({kc, note, own_words, mistakes}), add or update that idea's section."""
    rel = notes_rel(packs, subtopic)
    path = root / rel
    st = packs.subtopics[subtopic]
    text = path.read_text(encoding="utf-8") if path.exists() else (
        f"---\nsubtopic: {subtopic}\n---\n# {subtopic} {st['title']}\n\n"
        "_These notes grow as you learn. Anything you add outside the grey markers is kept._\n")
    kcs = [k for k, v in packs.kcs.items() if v["subtopic"] == subtopic]
    done = sum(kc_status(state, k) == "secure" for k in kcs)
    text = upsert(text, "map", f"> [!info] Progress: {done}/{len(kcs)} ideas secure\n\n"
                  + concept_map(packs, state, subtopic, current))
    if node:
        kc = node["kc"]
        body = [f"## {STATUS[kc_status(state, kc)]} {packs.kcs[kc]['title']}", "", node.get("note", "").strip(), ""]
        if node.get("own_words"):
            body += [callout("quote", "In your words", node["own_words"]), ""]
        if node.get("mistakes"):
            body += [callout("warning", "Watch out (your mistakes)", "\n".join(f"- {m}" for m in node["mistakes"])), ""]
        order = [k for k in kcs if _block(f"node {k}").search(text)] + [kc]
        prev = next((k for k in reversed(order[:-1]) if kcs.index(k) < kcs.index(kc)), None) if kc in kcs else None
        text = upsert(text, f"node {kc}", "\n".join(body), after=f"node {prev}" if prev else "map")
    return _write(root, rel, text)


def refresh_status(root: Path, packs, state: dict, subtopic: str) -> str | None:
    """Re-mark each idea heading with its current status (reviews change mastery), then redraw the map."""
    path = root / notes_rel(packs, subtopic)
    if not path.exists():
        return None
    text = path.read_text(encoding="utf-8")
    for k in [k for k, v in packs.kcs.items() if v["subtopic"] == subtopic]:
        if m := _block(f"node {k}").search(text):
            block = re.sub(r"^## \S+ ", f"## {STATUS[kc_status(state, k)]} ", m.group(0), count=1, flags=re.M)
            text = text[:m.start()] + block + text[m.end():]
    path.write_text(text, encoding="utf-8")
    return notes_update(root, packs, state, subtopic)


# ---------------- lesson log (live mirror of the session) ----------------
class LessonLog:
    def __init__(self, root: Path, rel: str):
        self.root, self.rel = root, rel

    @classmethod
    def create(cls, root: Path, title: str, now: datetime, header: str = "") -> "LessonLog":
        rel = f"Lessons/{now:%Y-%m-%d %H%M} {_safe(title)}.md"
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
        title = f"Q{fb['n']} — " + ("I don't know" if dont_know else "correct ✓" if fb.get("correct") else "incorrect ✗")
        body = [f"Your answer: {your}", f"Correct answer: {fb.get('answer', '')}"]
        if fb.get("explanation"):
            body += ["", fb["explanation"]]
        mis = fb.get("misconception")
        if mis:
            body += ["", f"**Trap:** {mis.get('statement', '')}", mis.get("refutation", "")]
        self.add(callout(kind, title, "\n".join(body)))


# ---------------- Now.md ----------------
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
             "New here? Read [[How It Works]].", "", "## Your subjects", "",
             "| Subtopic | Progress | Notes |", "|---|---|---|"]
    built = sorted(s for s in packs.subtopics if packs.pack(s))
    for sub in built:
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
