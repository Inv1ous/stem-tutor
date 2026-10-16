import asyncio
import json

from test_tui import app_for


def _course(vault):
    d = vault / ".tutor" / "shortcuts" / "course"
    d.mkdir(parents=True)
    rows = [{"id": f"SEM-9702-x{i}", "spec": "9702", "section": "1. A", "topic": "", "title": f"T{i}", "score": 9,
             "origin": "base", "body": "b"} for i in range(9)]
    (d / "9702.json").write_text(json.dumps(rows))


def test_menu_lines_wrap_with_a_hanging_indent_and_never_overflow(tmp_path, monkeypatch):
    async def go(width, sub):
        app, v = app_for(tmp_path / sub, monkeypatch)
        _course(v)
        async with app.run_test(size=(width, 40)) as pilot:
            await pilot.pause()
            await pilot.pause()
            menu = app.screen.query_one("#menu")
            room = menu.size.width - 6
            rows = [str(menu.get_option_at_index(i).prompt).split("\n") for i in range(menu.option_count)]
            for lines in rows:
                assert all(len(x) <= room for x in lines), (width, room, lines)
                assert all(x.startswith("   ") for x in lines[1:]), lines  # words under the words, not under the icon
            if width >= 84:  # the usual window: every line of the menu is one line
                assert all(len(lines) == 1 for lines in rows), rows
            labels = [" ".join(x.strip() for x in lines) for lines in rows]
            assert any(label.startswith("↯  Shortcuts") for label in labels)
            await app.ai.close()
    for width in (120, 84, 70, 56):
        asyncio.run(go(width, f"w{width}"))
