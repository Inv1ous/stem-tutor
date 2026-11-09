"""The home menu's folders: which entries live where, and the old ids that still start something.

Pure data and two small helpers, so the grouping can be tested without a screen.
"""
from __future__ import annotations

# (folder id, title, glyph, entry ids in order). An entry missing from the current menu (e.g. "saved-attempts" when
# there is nothing saved) is skipped; a folder left empty is not shown.
FOLDERS: tuple[tuple[str, str, str, tuple[str, ...]], ...] = (
    ("learn", "Learn & revise", "◆", ("today", "learn", "review", "weak", "long", "blurt")),
    ("questions", "Questions", "◎", ("practice", "challenge", "shortcuts", "shortcut_recall")),
    ("profile", "Profile & progress", "◉", ("insights", "saved-attempts", "progress", "obsidian")),
    ("tools", "Tools", "≡", ("chat", "settings", "help", "quit")),
)

# Ids that start the merged Practice flow's older relatives. They are not in the menu any more but keep working
# (an open session, an old script or test may still ask for them).
ALIASES = {"test": "practice", "topical": "practice", "source-practice": "practice"}

# Entries that begin something new and therefore ask first when a session is already open (B-104).
STARTS_SESSION = frozenset(("today", "learn", "review", "weak", "test", "long", "blurt", "practice", "topical"))


def folder_of(key: str) -> str | None:
    """The folder an entry lives in; an old alias lives where its replacement does."""
    key = ALIASES.get(key, key)
    return next((fid for fid, _, _, entries in FOLDERS if key in entries), None)


def folder_title(folder: str) -> str:
    return next((title for fid, title, _, _ in FOLDERS if fid == folder), folder)


def arrange(leaves: dict[str, str]) -> list[tuple[str, str, list[str]]]:
    """[(folder id, title, [entry ids present])] for the folders that have anything in them."""
    out = []
    for fid, title, _, entries in FOLDERS:
        present = [e for e in entries if e in leaves]
        if present:
            out.append((fid, title, present))
    return out
