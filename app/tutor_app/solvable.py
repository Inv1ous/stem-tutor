"""The "Can I solve this?" answer, as the screens show it.

Tutor.check_solvable(n) returns a dict. Keys read here (all with .get, so an older shape still renders):
    status          'solvable' | 'adapted' | 'skipped' | 'unverified' | 'topic_pending' (older: 'unavailable')
    message         the sentence to show
    missing         labels of topics or chapters not met yet (older shape: 'topics')
    given           values or equations supplied as hints
    adapted_prompt  which sub-parts to answer, or None
    topic           the topic labels the AI identified, or None
    skipped         True when the question was dropped from the set (the screen moves on)
"""
from __future__ import annotations

from tutorlib.topicals import started_chapters

TITLE = "Can I solve this?"
VERDICTS = {"solvable": "Yes.", "adapted": "Part of it.", "skipped": "Not yet: this one is skipped.",
            "topic_pending": "A topic it needs is still to come.", "unverified": "I can't tell."}
# the card colour: good news in the tutor's voice, anything that needs the learner's attention as a hint
ROLES = {"solvable": "tutor", "adapted": "tutor"}


def _labels(value) -> list[str]:
    if not value:
        return []
    if isinstance(value, str):
        return [value]
    return [str(v) for v in value if str(v).strip()]


def normalise(result) -> dict:
    """The fields the screens use, whatever shape the engine answered in."""
    result = result if isinstance(result, dict) else {}
    status = str(result.get("status") or "unverified")
    if status == "unavailable":  # the older name for "required topics are missing"
        status = "topic_pending"
    missing = result.get("missing")
    if missing is None and status in ("topic_pending", "skipped"):
        missing = result.get("topics")
    skipped = bool(result.get("skipped")) or status == "skipped"
    return {"status": "skipped" if skipped else status, "message": str(result.get("message") or ""),
            "missing": _labels(missing), "given": _labels(result.get("given")),
            "adapted_prompt": (str(result["adapted_prompt"]).strip() or None) if result.get("adapted_prompt") else None,
            "topic": _labels(result.get("topic")) or None, "skipped": skipped}


def card_parts(info: dict) -> tuple[str, str, str]:
    """(role, title, body) for the message card."""
    status = info["status"]
    lines = [VERDICTS.get(status, ""), info["message"] or {"solvable": "You have what this needs.", "adapted": "Part of this question is within reach.",
                                 "skipped": "This question was set aside for now.",
                                 "topic_pending": "A topic this needs has not been covered yet.",
                                 "unverified": "I can't confirm what this question needs."}.get(status, "")]
    if info["topic"]:
        lines.append("Topics this uses: " + ", ".join(info["topic"]) + ".")
    if info["missing"]:
        lines.append("Not covered yet: " + ", ".join(info["missing"]) + ".")
    if info["given"]:
        lines += ["", "Given:"] + [f"- {g}" for g in info["given"]]
    if info["adapted_prompt"]:
        lines += ["", "Answer these parts: see the question above."]
    return ROLES.get(status, "hint"), TITLE, "\n".join(lines).strip()


def challenge_check(topics: list[str], state: dict, packs) -> dict:
    """Challenge questions are written for the chosen topics from the course graph: they can use anything the course
    teaches up to those topics. Report which of the chosen topics have not been started."""
    try:
        begun = started_chapters(state, packs)
    except Exception:  # noqa: BLE001 - an unreadable record only means we cannot say
        return {"status": "unverified", "message": "I can't read your progress to check this one.", "topic": None}
    labels = {t: f"{t} {packs.subtopics.get(t, {}).get('title', '')}".strip() for t in topics}
    pending = [labels[t] for t in topics if t not in begun]
    if not topics:
        return {"status": "unverified", "message": "This set has no recorded topics, so I can't check what it needs.",
                "topic": None}
    if pending:
        return {"status": "topic_pending", "topic": list(labels.values()), "missing": pending,
                "message": "This challenge draws on topics you have not started. It stays open: it is a stretch question "
                           "and counts nothing towards mastery."}
    return {"status": "solvable", "topic": list(labels.values()),
            "message": "Every topic this challenge draws on is one you have started."}
