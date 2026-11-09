"""Keep the mastery colours of concept maps current, outside lessons too.

`views.concept_map` draws a subtopic's ideas as a Mermaid graph whose node classes (`:::done`, `:::learning`,
`:::gap`, `:::todo`) and status marks colour each idea by mastery. Maps sit in My Notes and in lesson logs. When an
event changes any idea's status (practice, review, topical or solvability attempts, regrades), the Tutor hands the
changed subtopics to a `MermaidRefresher`, which rewrites only the node lines of the maps of those subtopics, off the
keypress path. Other text, edges, labels, `classDef` styles and the highlighted `:::now` class are never touched, and
running it again changes nothing.
"""
from __future__ import annotations

import re
import threading
from pathlib import Path
from typing import Callable

from . import views
from .store import edit_text

_FENCE = re.compile(r"^```mermaid[ \t]*\n(.*?)^```[ \t]*$", re.M | re.S)
_NODE = re.compile(r'^(?P<pre>[ \t]*n\d+\[")(?P<mark>\S+) (?P<label>.*)(?P<mid>"\]:::)(?P<cls>\w+)(?P<end>[ \t]*)$', re.M)
_MARKS = set(views.STATUS.values())


def snapshot(state: dict) -> dict[str, str]:
    """{kc: status} for every idea with any history (all others are 'new')."""
    return {k: views.kc_status(state, k) for k in set(state.get("kcs", {})) | set(state.get("gaps", []))}


def changed_kcs(before: dict[str, str], after: dict[str, str]) -> set[str]:
    return {k for k in set(before) | set(after) if before.get(k, "new") != after.get(k, "new")}


class _Titles:
    """label -> {(subtopic, kc)}: which ideas a drawn node can be (labels are titles with " written as ')."""

    def __init__(self, packs):
        self.by_label: dict[str, set[tuple[str, str]]] = {}
        for kc, v in packs.kcs.items():
            self.by_label.setdefault(v["title"].replace('"', "'"), set()).add((v["subtopic"], kc))

    def block_subtopic(self, labels: list[str]) -> str | None:
        """The one subtopic every node of a map belongs to, or None (not a concept map)."""
        common: set[str] | None = None
        for label in labels:
            subs = {s for s, _ in self.by_label.get(label, ())}
            common = subs if common is None else common & subs
            if not common:
                return None
        return next(iter(common)) if common and len(common) == 1 else None


def refresh_text(text: str, titles: _Titles, statuses: dict[str, dict[str, str]]) -> str:
    """Recolour the nodes of every concept map in `text` whose subtopic is in `statuses` ({subtopic: {kc: status}})."""
    def block(m: re.Match) -> str:
        body = m.group(1)
        nodes = list(_NODE.finditer(body))
        if not nodes or any(n["mark"] not in _MARKS for n in nodes):
            return m.group(0)
        sub = titles.block_subtopic([n["label"] for n in nodes])
        if sub not in statuses:
            return m.group(0)
        wanted = statuses[sub]
        kc_of = {label: kc for label, pairs in titles.by_label.items() for s, kc in pairs if s == sub}

        def node(n: re.Match) -> str:
            status = wanted.get(kc_of.get(n["label"], ""), "new")
            cls = n["cls"] if n["cls"] == "now" else views._MAP_CLASS[status]
            return f'{n["pre"]}{views.STATUS[status]} {n["label"]}{n["mid"]}{cls}{n["end"]}'

        new_body = _NODE.sub(node, body)
        return m.group(0) if new_body == body else m.group(0).replace(body, new_body, 1)

    return _FENCE.sub(block, text)


class MermaidRefresher:
    """Coalesces changed subtopics and redraws their map colours in a worker thread (or inline: background=False)."""

    def __init__(self, root: Path, packs, background: bool = True,
                 active_log: Callable[[], str | None] | None = None):
        self.root, self.packs, self.background = Path(root), packs, background
        self.active_log = active_log or (lambda: None)  # the live lesson log is appended to: never rewritten
        self._pending: dict[str, dict[str, str]] = {}
        self._cv = threading.Condition()
        self._thread: threading.Thread | None = None
        self._busy = False
        self._titles: _Titles | None = None
        self._lessons: dict[str, tuple[tuple[int, int], set[str]]] = {}  # rel -> ((mtime, size), subtopics)
        self.errors: list[str] = []
        self.written: list[str] = []

    # ---- called on the engine's thread ----
    def changed(self, before: dict[str, str], state: dict) -> set[str]:
        """Queue the subtopics whose ideas changed status between `before` and `state`. Cheap: a dict diff."""
        kcs = changed_kcs(before, snapshot(state))
        subs = {self.packs.kcs[k]["subtopic"] for k in kcs if k in self.packs.kcs}
        if not subs:
            return subs
        work = {s: {k: views.kc_status(state, k) for k, v in self.packs.kcs.items() if v["subtopic"] == s}
                for s in subs}  # statuses are taken now: the worker never reads live state
        with self._cv:
            self._pending.update(work)
            if not self.background:
                pass
            elif self._thread is None or not self._thread.is_alive():
                self._thread = threading.Thread(target=self._run, name="mermaid-refresh", daemon=True)
                self._thread.start()
            else:
                self._cv.notify()
        if not self.background:
            self._drain()
        return subs

    def flush(self, timeout: float = 5.0) -> bool:
        """Wait until queued maps are written (tests, app exit). True when nothing is left."""
        with self._cv:
            return self._cv.wait_for(lambda: not self._pending and not self._busy, timeout=timeout)

    # ---- worker ----
    def _run(self) -> None:
        while True:
            with self._cv:
                if not self._cv.wait_for(lambda: bool(self._pending), timeout=2.0):
                    self._thread = None
                    self._cv.notify_all()
                    return
            self._drain()

    def _drain(self) -> None:
        with self._cv:
            work, self._pending = self._pending, {}
            self._busy = True
        try:
            if work:
                self._refresh(work)
        except Exception as exc:  # noqa: BLE001 - a cosmetic redraw must never break studying
            self.errors.append(str(exc))
        finally:
            with self._cv:
                self._busy = False
                self._cv.notify_all()

    def _refresh(self, work: dict[str, dict[str, str]]) -> None:
        if self._titles is None:
            self._titles = _Titles(self.packs)
        titles = self._titles
        targets: list[Path] = []
        for sub in work:
            try:
                rel = views.note_location(self.root, self.packs, sub)
            except Exception:  # noqa: BLE001 - an unbuilt chapter has no note
                continue
            if (self.root / rel).is_file():
                targets.append(self.root / rel)
        active = self.active_log()
        for rel, subs in self._lesson_index(titles).items():
            if subs & set(work) and rel != active:
                targets.append(self.root / rel)
        for path in dict.fromkeys(targets):
            if not self._writable(path):
                continue

            def edit(text: str | None) -> str | None:
                if text is None:
                    return None
                new = refresh_text(text, titles, work)
                return new if new != text else None

            try:
                with views.NOTE_LOCK:
                    if edit_text(path, edit):
                        self.written.append(path.relative_to(self.root).as_posix())
            except OSError as exc:
                self.errors.append(f"{path.name}: {exc}")

    def _lesson_index(self, titles: _Titles) -> dict[str, set[str]]:
        """Lesson logs with concept maps, re-read only when a log changed since it was last indexed."""
        folder = self.root / "Lessons"
        seen: dict[str, tuple[tuple[int, int], set[str]]] = {}
        if folder.is_dir():
            for p in folder.rglob("*.md"):
                try:
                    st = p.stat()
                except OSError:
                    continue
                rel, sig = p.relative_to(self.root).as_posix(), (st.st_mtime_ns, st.st_size)
                old = self._lessons.get(rel)
                if old and old[0] == sig:
                    seen[rel] = old
                    continue
                try:
                    text = p.read_text(encoding="utf-8")
                except (OSError, UnicodeDecodeError):
                    continue
                subs = set()
                for m in _FENCE.finditer(text):
                    labels = [n["label"] for n in _NODE.finditer(m.group(1))]
                    if labels and (s := titles.block_subtopic(labels)):
                        subs.add(s)
                seen[rel] = (sig, subs)
        self._lessons = seen
        return {rel: subs for rel, (_, subs) in seen.items() if subs}

    def _writable(self, path: Path) -> bool:
        """Only plain personal views: no file adapters, links, Library or Archive copies."""
        try:
            if path.is_symlink() or not path.is_file() or path.stat().st_nlink > 1:
                return False
            resolved, root = path.resolve(), self.root.resolve()
            rel = resolved.relative_to(root)
            return rel.parts[0] in ("My Notes", "Lessons") and views.library_location(path) is None
        except (OSError, ValueError):
            return False
