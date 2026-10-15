"""The "Shortcuts & Elegant Methods" course, the engine half: the learner's settings, which entries they allow, and the
course's own spaced recall (an event log folded into one FSRS card per entry).

All of it lives under <vault>/.tutor/shortcuts/ and is separate from the syllabus: nothing here touches model.py,
state/learner.json or the syllabus events. Entries and lessons are published to .tutor/shortcuts/course/ by build/publish.py.
"""
from __future__ import annotations

import json
import os
import re
import zlib
from datetime import datetime, timezone
from pathlib import Path

from . import deps
from .store import Vault, read_json, write_json

DEFAULT_CONFIG: dict = {"min_score": 8, "max_score": 10, "specs": [], "levels": [], "sections": [], "origins": [],
                        "order": "score", "new_per_day": 5, "lessons_only": False, "recall_scope": "learned"}
ORDERS = ("score", "section")
SCOPES = ("learned", "all")
LEVEL_NAMES = ("AS", "A")
ORIGINS = ("base", "research")
MAX_NEW_PER_DAY = 50
KINDS = ("learn", "recall", "practice")
RATINGS = {1: "Again", 2: "Hard", 3: "Good", 4: "Easy"}


# ---------------- config ----------------
def _int(v, default: int, lo: int, hi: int) -> int:
    if isinstance(v, bool):
        return default
    try:
        n = int(float(v))
    except (TypeError, ValueError, OverflowError):
        return default
    return max(lo, min(hi, n))


def _strings(v, fold=None, allowed=None) -> list[str]:
    items = [v] if isinstance(v, str) else list(v) if isinstance(v, (list, tuple)) else []
    out = []
    for x in items:
        if not isinstance(x, str) or not x.strip():
            continue
        x = fold(x.strip()) if fold else x.strip()
        if (allowed is None or x in allowed) and x not in out:
            out.append(x)
    return out


def normalise_config(d) -> dict:
    """The settings with every key present, of the right type and in range; a bad value falls back to its default."""
    d = d if isinstance(d, dict) else {}
    out = {k: (list(v) if isinstance(v, list) else v) for k, v in DEFAULT_CONFIG.items()}
    lo = _int(d.get("min_score", out["min_score"]), DEFAULT_CONFIG["min_score"], 0, 10)
    hi = _int(d.get("max_score", out["max_score"]), DEFAULT_CONFIG["max_score"], 0, 10)
    out["min_score"], out["max_score"] = sorted((lo, hi))
    out["specs"] = _strings(d.get("specs"))
    out["sections"] = _strings(d.get("sections"))
    out["levels"] = _strings(d.get("levels"), str.upper, LEVEL_NAMES)
    out["origins"] = _strings(d.get("origins"), str.lower, ORIGINS)
    for key, allowed in (("order", ORDERS), ("recall_scope", SCOPES)):
        val = d.get(key)
        val = val.strip().lower() if isinstance(val, str) else None
        out[key] = val if val in allowed else DEFAULT_CONFIG[key]
    out["new_per_day"] = _int(d.get("new_per_day", out["new_per_day"]), DEFAULT_CONFIG["new_per_day"], 0, MAX_NEW_PER_DAY)
    out["lessons_only"] = d["lessons_only"] if isinstance(d.get("lessons_only"), bool) else DEFAULT_CONFIG["lessons_only"]
    return out


def _vault(vault) -> Vault:
    return vault if isinstance(vault, Vault) else Vault(Path(vault))


def _dir(vault: Vault) -> Path:
    return vault.tutor / "shortcuts"


def load_config(vault) -> dict:
    """The saved settings, normalised; a missing or damaged file gives the defaults."""
    try:
        saved = read_json(_dir(_vault(vault)) / "settings.json")
    except (ValueError, OSError):
        saved = None
    return normalise_config(saved)


def save_config(vault, cfg: dict) -> dict:
    """Normalise and store the settings; returns what was stored. A vault that cannot be written just forgets them."""
    cfg = normalise_config(cfg)
    try:
        write_json(_dir(_vault(vault)) / "settings.json", cfg)
    except OSError:
        pass
    return cfg


# ---------------- entries ----------------
def level_of(e: dict) -> str:
    """'A' for an entry in an A Level section ("7. A Level: circular motion ..."), else 'AS' (everything else)."""
    return "A" if re.search(r"\bA Level\b|\(1[2-9]|\(2[0-5]", e["section"]) else "AS"


def _natural(text: str) -> list:
    return [int(p) if p.isdigit() else p for p in re.split(r"(\d+)", text.lower())]


def select(entries: list[dict], cfg: dict | None = None) -> list[dict]:
    """The entries a learner's settings allow, in the order they asked for (best score first, or by section).
    Settings (all optional): `min_score`, `max_score`, `specs`, `sections` (substring match), `levels` ('AS', 'A'),
    `origins`, `order`, `lessons_only` (an entry needs a `lesson`)."""
    cfg = cfg or {}
    lo, hi = int(cfg.get("min_score", 0)), int(cfg.get("max_score", 10))
    specs, origins = set(cfg.get("specs") or []), set(cfg.get("origins") or [])
    words = [w.lower() for w in cfg.get("sections") or []]
    levels = set(cfg.get("levels") or [])
    keep = []
    for e in entries:
        if not lo <= e["score"] <= hi or (specs and e["spec"] not in specs) or (origins and e["origin"] not in origins):
            continue
        if words and not any(w in (e["section"] + " " + e["topic"]).lower() for w in words):
            continue
        if levels and level_of(e) not in levels:
            continue
        if cfg.get("lessons_only") and not e.get("lesson"):
            continue
        keep.append(e)
    if cfg.get("order") == "section":
        return sorted(keep, key=lambda e: (e["spec"], _natural(e["section"]), -e["score"], e["id"]))
    return sorted(keep, key=lambda e: (-e["score"], e["spec"], _natural(e["section"]), e["id"]))


def _read_list(path: Path) -> list:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return []
    return data if isinstance(data, list) else []


def load_entries(vault) -> list[dict]:
    """Every published entry, each with a `lesson` key (the generated lesson, or None)."""
    course = _dir(_vault(vault)) / "course"
    lessons: dict[str, dict] = {}
    for path in sorted((course / "lessons").glob("*.json")):
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        if isinstance(data, dict):
            lessons.update({k: v for k, v in data.items() if isinstance(v, dict)})
    out: dict[str, dict] = {}
    for path in sorted(course.glob("*.json")):
        for e in _read_list(path):
            if isinstance(e, dict) and isinstance(e.get("id"), str) and isinstance(e.get("score"), int):
                e = {"spec": "", "section": "", "topic": "", "title": e["id"], "origin": "base", "body": "", **e}
                out.setdefault(e["id"], {**e, "lesson": lessons.get(e["id"])})
    return list(out.values())


# ---------------- state: the event log folded into FSRS cards ----------------
_SCHED = None


def _fsrs():
    deps.ensure("fsrs")
    import fsrs

    return fsrs


def _scheduler():
    """The same scheduler the syllabus uses (model.py): 0.9 retention, no learning steps, no fuzzing."""
    global _SCHED
    if _SCHED is None:
        _SCHED = _fsrs().Scheduler(desired_retention=0.9, learning_steps=(), relearning_steps=(), enable_fuzzing=False)
    return _SCHED


def _utc(now: datetime | None) -> datetime:
    now = now or datetime.now(timezone.utc)
    return now.replace(tzinfo=timezone.utc) if now.tzinfo is None else now.astimezone(timezone.utc)


def _parse(t) -> datetime | None:
    try:
        return _utc(datetime.fromisoformat(t))
    except (TypeError, ValueError):
        return None


def _fold(events: list[dict]) -> dict:
    fsrs = _fsrs()
    sched, cards, learns = _scheduler(), {}, []
    for e in events:
        when = _parse(e.get("t"))
        kind, eid, rating = e.get("type"), e.get("id"), e.get("rating")
        if when is None or kind not in KINDS or not isinstance(eid, str):
            continue
        if kind == "learn":
            learns.append(e["t"])
        if kind == "practice" or rating not in RATINGS or (kind == "learn" and eid in cards):
            continue
        card = fsrs.Card.from_dict(cards[eid]) if eid in cards else fsrs.Card(card_id=zlib.crc32(eid.encode()))
        card, _ = sched.review_card(card, getattr(fsrs.Rating, RATINGS[rating]), when)
        cards[eid] = card.to_dict()
    return {"cards": cards, "learns": learns}


class Course:
    def __init__(self, vault):
        self.vault = _vault(vault)
        self.cfg = load_config(self.vault)
        self._entries: list[dict] | None = None
        self._state: dict | None = None

    @property
    def _log(self) -> Path:
        return _dir(self.vault) / "events.jsonl"

    @property
    def _cache(self) -> Path:
        return _dir(self.vault) / "state.json"

    # --- entries ---
    def pool(self) -> list[dict]:
        """Every published entry, unfiltered."""
        if self._entries is None:
            self._entries = load_entries(self.vault)
        return self._entries

    def entries(self) -> list[dict]:
        """The entries the settings allow, in the chosen order."""
        return select(self.pool(), self.cfg)

    # --- events and state ---
    def _read_events(self) -> list[dict]:
        out = []
        try:
            lines = self._log.read_bytes().decode("utf-8", "replace").splitlines()
        except OSError:
            return out
        for line in lines:
            try:
                e = json.loads(line)
            except ValueError:
                continue  # a torn line
            if isinstance(e, dict):
                out.append(e)
        return out

    def _size(self) -> int:
        try:
            return self._log.stat().st_size
        except OSError:
            return 0

    def state(self) -> dict:
        """{"cards": {id: fsrs card}, "learns": [times]}: the cache when it has folded the whole log, else a refold."""
        size = self._size()
        if self._state is not None and self._state.get("bytes") == size:
            return self._state
        try:
            cached = read_json(self._cache)
        except (ValueError, OSError):
            cached = None
        if isinstance(cached, dict) and cached.get("bytes") == size and isinstance(cached.get("cards"), dict) \
                and isinstance(cached.get("learns"), list):
            self._state = cached
            return cached
        self._state = {**_fold(self._read_events()), "bytes": size}
        try:
            write_json(self._cache, self._state, indent=None)
        except OSError:
            pass
        return self._state

    def learned_ids(self) -> set[str]:
        return set(self.state()["cards"])

    def record(self, kind: str, entry_id: str, rating: int | None = None, mode: str = "",
               now: datetime | None = None) -> dict:
        """Log one learn / recall / practice and return the event, with `due` (ISO, UTC) once the entry has a card.
        Rating is 1 again, 2 hard, 3 good, 4 easy; a practice is logged but never schedules."""
        if kind not in KINDS:
            raise ValueError(f"unknown kind {kind!r}")
        if rating is not None and rating not in RATINGS:
            raise ValueError(f"rating must be 1 to 4, not {rating!r}")
        if rating is None and kind != "practice":
            raise ValueError(f"a {kind} needs a rating")
        event = {"t": _utc(now).isoformat(timespec="seconds"), "type": kind, "id": entry_id, "rating": rating, "mode": mode}
        self._log.parent.mkdir(parents=True, exist_ok=True)
        with open(self._log, "ab+") as f:
            torn = f.seek(0, os.SEEK_END) > 0 and f.seek(-1, os.SEEK_END) >= 0 and f.read(1) != b"\n"
            f.write((("\n" if torn else "") + json.dumps(event, ensure_ascii=False) + "\n").encode("utf-8"))
        card = self.state()["cards"].get(entry_id)
        return {**event, "due": card["due"] if card else None}

    def _due_at(self, card: dict) -> datetime:
        return _parse(card.get("due")) or datetime.min.replace(tzinfo=timezone.utc)

    # --- queues ---
    def new_today(self, now: datetime | None = None) -> int:
        """Entries learned today, by the learner's local day."""
        tz, today = self.vault.tz, _utc(now).astimezone(self.vault.tz).date()
        return sum(1 for t in self.state()["learns"] if (w := _parse(t)) and w.astimezone(tz).date() == today)

    def next_lessons(self, n: int | None = None, now: datetime | None = None) -> list[dict]:
        """Entries not yet learned that the settings allow, best first: n of them, or what is left of today's
        `new_per_day`."""
        if n is None:
            n = max(0, self.cfg["new_per_day"] - self.new_today(now))
        learned = self.learned_ids()
        return [e for e in self.entries() if e["id"] not in learned][:max(0, n)]

    def due(self, now: datetime | None = None) -> list[str]:
        """Ids of learned entries whose card is due, most overdue first. recall_scope 'learned' keeps to the entries that
        still pass the filters; 'all' also recalls learned entries the filters have since left out."""
        now = _utc(now)
        cards = self.state()["cards"]
        pool = self.entries() if self.cfg["recall_scope"] == "learned" else self.pool()
        due = [(self._due_at(cards[e["id"]]), e["id"]) for e in pool if e["id"] in cards]
        return [i for d, i in sorted(due) if d <= now]

    def recall_cards(self, entry: dict) -> list[dict]:
        """The lesson's flash questions, or a plain one derived from the entry itself."""
        cards = [{"q": c["q"], "a": c["a"]} for c in (entry.get("lesson") or {}).get("recall") or []
                 if isinstance(c, dict) and c.get("q") and c.get("a")]
        return cards or [{"q": f"What is the shortcut for: {entry['title']}?", "a": entry.get("body", "")}]

    def stats(self, now: datetime | None = None) -> dict:
        sel = self.entries()
        learned = self.learned_ids()
        return {"selected": len(sel), "learned": len(learned & {e["id"] for e in self.pool()}),
                "due": len(self.due(now)), "new_today": self.new_today(now),
                "lessons": sum(1 for e in sel if e.get("lesson"))}
