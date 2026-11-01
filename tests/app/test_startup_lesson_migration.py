"""Actual Home startup must preserve registered notes while organising old logs."""
import asyncio
import os
from pathlib import Path

import pytest

import library_assets
from test_tui import app_for
from tutorlib import asset_library


@pytest.mark.parametrize("adapter", ["regular", "symlink"])
def test_home_startup_keeps_immutable_notes_and_learner_originals(tmp_path, monkeypatch, adapter):
    app, vault = app_for(tmp_path, monkeypatch)
    library_assets.install_course(vault, "9702", "9702-2.1")
    old = "Lessons/2026-10-04 1539 Lesson - Startup.md"
    new = "Lessons/2026-10-04/1539 Lesson - Startup.md"
    original = b"# Original lesson\r\nMy working: 12.0 m\r\n"
    (vault / old).parent.mkdir()
    (vault / old).write_bytes(original)
    reference = b"Original [[Lessons/2026-10-04 1539 Lesson - Startup|lesson]].\r\n"
    canonical = "Library/Courses/9702/Notes/startup-reference.md"
    asset_library.write_asset(vault, canonical, reference, aliases=["Read-only reference.md"])
    note = vault / "Read-only reference.md"
    if adapter == "regular":
        note.write_bytes(reference)
    else:
        note.symlink_to(canonical)
    learner = vault / "My notebook.md"
    learner.write_bytes(reference)
    archived = vault / "Archive/Original.md"
    archived.parent.mkdir()
    archived.write_bytes(reference)
    catalog = (vault / "Library/catalog.json").read_bytes()

    async def go():
        async with app.run_test(size=(80, 24)) as pilot:
            await pilot.pause()
            assert type(app.screen).__name__ == "HomeScreen" and app.is_running
            if directory := os.environ.get("B231_CAPTURE"):
                Path(directory).mkdir(parents=True, exist_ok=True)
                app.save_screenshot(f"startup-{adapter}.svg", path=directory)
            assert asset_library.AssetLibrary(vault).read(canonical) == reference
            assert note.read_bytes() == reference and note.is_symlink() == (adapter == "symlink")
            assert archived.read_bytes() == reference
            assert (vault / "Library/catalog.json").read_bytes() == catalog
            assert not (vault / old).exists() and (vault / new).read_bytes() == original
            assert "[[Lessons/2026-10-04/1539 Lesson - Startup|lesson]]" in learner.read_text()
            backup, = (vault / ".tutor/backups").rglob("My notebook.md")
            assert backup.read_bytes() == reference
            await app.ai.close()

    asyncio.run(go())
