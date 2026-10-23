from __future__ import annotations

import asyncio
import json
from pathlib import Path

import pytest

from test_tui import app_for
from tutor_app.screens import ChatScreen, SessionScreen


@pytest.mark.parametrize("override", ["string", "dictionary", "missing_stem", "empty_stem"])
def test_a_diagram_question_reads_its_authored_description(tmp_path, monkeypatch, override):
    """B-108: the safe diagram description reaches Ctrl+E without revealing the key."""
    app, vault = app_for(tmp_path, monkeypatch)
    pack = json.loads((Path(__file__).resolve().parents[2] / "build/out/packs/9702/9702-8.3.json").read_text())
    item = next(q for q in pack["items"] if q["id"] == "9702-8.3-r02")
    narration = item["speech"]
    if override != "string":
        item["speech"] = {"explanation": "Private spoken answer.", "hint1": "Private spoken hint."}
        if override != "missing_stem":
            item["speech"]["stem"] = narration if override == "dictionary" else ""
    expected = narration if override in ("string", "dictionary") else item["stem"]

    async def go() -> None:
        async with app.run_test() as pilot:
            await pilot.pause()
            scr = SessionScreen({"mode": "test", "focus": ["9702-2.1"], "minutes": 30})
            app.push_screen(scr)
            await pilot.pause()
            view = app.tutor._present(item, "practice", None)
            scr.ask_question(view)
            await pilot.pause()
            assert scr.readable_parts[0] == expected  # then the choices (B-107)
            assert view["stem"] == item["stem"]
            assert not {"answer", "explanation", "distractors"} & view.keys()
            assert "constructive" not in scr.readable.lower()
            assert "destructive" not in scr.readable.lower()
            fallback = {**view, "speech": ""}
            scr.ask_question(fallback)
            assert scr.readable_parts[0] == item["stem"]
            await app.ai.close()
    asyncio.run(go())


def test_reopening_chat_removes_the_old_conversation_from_now(tmp_path, monkeypatch):
    """B-068: a new empty chat must not display the previous reply in Obsidian."""
    app, vault = app_for(tmp_path, monkeypatch)

    async def go() -> None:
        async with app.run_test() as pilot:
            await pilot.pause()
            app.push_screen(ChatScreen())
            await pilot.pause()
            app.tutor.show("you", "Old question")
            app.tutor.show("ai", "Old reply")
            assert "Old reply" in (vault / "Now.md").read_text()
            await pilot.press("escape")
            await pilot.pause()
            app.push_screen(ChatScreen())
            await pilot.pause()
            now = (vault / "Now.md").read_text()
            assert "Old reply" not in now and "Old question" not in now
            assert "Chat" in now
            await app.ai.close()
    asyncio.run(go())
