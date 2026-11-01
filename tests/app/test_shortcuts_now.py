"""The visible Shortcuts card is mirrored to Now without changing learner state."""
import asyncio

from test_tui import app_for, pin_clock
from test_shortcuts_screen import open_from_menu, publish


def test_shortcuts_card_is_written_to_now_without_touching_shortcut_state(tmp_path, monkeypatch):
    pin_clock(monkeypatch)
    app, vault = app_for(tmp_path, monkeypatch)
    publish(vault)

    async def steps(pilot):
        await pilot.pause()
        state_files = vault / ".tutor" / "shortcuts"
        before = {p.relative_to(state_files): p.read_bytes() for p in state_files.rglob("*") if p.is_file()}
        screen = await open_from_menu(pilot, app, "shortcuts", "ShortcutsScreen")

        now = (vault / "Now.md").read_text()
        visible = screen.query_one("#card").content.plain
        assert "_Shortcuts · 17:00_" in now
        assert visible in now
        after = {p.relative_to(state_files): p.read_bytes() for p in state_files.rglob("*") if p.is_file()}
        assert after == before

    async def run_app():
        async with app.run_test(size=(100, 30)) as pilot:
            await steps(pilot)
            await app.ai.close()

    asyncio.run(run_app())


def test_shortcuts_card_stays_visible_when_catalog_mirror_fails(tmp_path, monkeypatch):
    from tutorlib import views

    pin_clock(monkeypatch)
    app, vault = app_for(tmp_path, monkeypatch)
    publish(vault)
    state_files = vault / ".tutor" / "shortcuts"

    async def steps(pilot):
        await pilot.pause()
        before = {p.relative_to(state_files): p.read_bytes() for p in state_files.rglob("*") if p.is_file()}

        def unresolved(*args, **kwargs):
            raise ValueError("unresolved Library asset reference")

        monkeypatch.setattr(views, "write_now", unresolved)
        screen = await open_from_menu(pilot, app, "shortcuts", "ShortcutsScreen")

        visible = screen.query_one("#card").content.plain
        assert visible
        assert visible in screen.readable
        after = {p.relative_to(state_files): p.read_bytes() for p in state_files.rglob("*") if p.is_file()}
        assert after == before

    async def run_app():
        async with app.run_test(size=(100, 30)) as pilot:
            await steps(pilot)
            await app.ai.close()

    asyncio.run(run_app())
