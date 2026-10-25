"""Approved STEM formatting at the real card, streaming and Obsidian boundaries."""
import asyncio
import json
from io import StringIO

import pytest
from rich.console import Console
from rich.cells import cell_len
from textual.widgets import Static

from tutor_app import ai, cards, local_models, look
from tutor_app.panels import Composer
from tutorlib import views


VISUAL = "Use \\(x_i^2\\).\n\nCheck `x_1^2 * y`."
CANONICAL = "Use $x_i^2$.\n\nCheck `x_1^2 * y`."
SPEECH = r"Read \\(x_i^2\\) exactly: $5, 50%."
STUDENT = r"My try: \(x_i^2\), x_1, 3*x**2; $5."


def rendered(renderable, width=100):
    console = Console(width=width, record=True, file=StringIO())
    console.print(renderable)
    return console.export_text()


def transcript(screen, width=100):
    return "\n".join(rendered(entry.content, width) for entry in screen.query(".entry, .local-progress")
                     if entry.display)


def ai_card(screen):
    return next(entry.content for entry in reversed(list(screen.query(".entry")))
                if getattr(entry.content, "card", (None,))[0] == "ai")


@pytest.mark.parametrize("size", [(80, 24), (100, 30), (140, 46)])
@pytest.mark.parametrize("theme", ["night", "day", "classic"])
def test_ai_card_protects_literal_code_and_math_through_rich_at_supported_sizes(monkeypatch, size, theme):
    for name, colour in look.PALETTES[theme].items():
        monkeypatch.setitem(look.C, name, colour)
    source = (VISUAL + "\n\nMultiply $a*b*c$.\n\n```python\nx_1^2 * y\n```"
              "\n\nCost $5 and $10; 50%.")
    panel = cards.ai(source)
    text = rendered(panel, size[0])

    assert panel.card[2].startswith(CANONICAL)
    assert "𝑥ᵢ²" in text
    assert text.count("x_1^2 * y") == 2  # inline and fenced code both survive unchanged
    assert "Cost $5 and $10; 50%." in text
    multiply = text[text.index("Multiply"):text.index("x_1^2 * y", text.index("Multiply"))]
    assert all(variable in multiply for variable in "𝑎𝑏𝑐")
    assert sum(multiply.count(operator) for operator in "*×⋅·∗") == 2
    assert r"\(" not in text and r"\)" not in text
    assert max(map(cell_len, text.splitlines())) <= size[0]


def test_typed_student_notation_is_literal_in_its_real_card():
    panel = cards.you(STUDENT)
    assert panel.card == ("you", "You", STUDENT)
    assert STUDENT in rendered(panel, 140)


@pytest.mark.parametrize("opening,closing", [("$", "$"), ("$$", "$$"), (r"\(", r"\)"), (r"\[", r"\]")])
def test_live_card_never_exposes_an_unfinished_math_delimiter_at_any_character_boundary(opening, closing):
    widget = Static()
    live = cards.Live(widget, every=0)
    source = f"Visible start. {opening}x_i^2{closing}. Full tail."

    for end in range(len("Visible start."), len(source) + 1):
        assert live.update(source[:end])
        text = rendered(widget.content)
        assert "Visible start." in text
        assert "$" not in text and "\\" not in text, (opening, end, text)
        assert "x_i" not in text and "^2" not in text, (opening, end, text)
    assert "𝑥ᵢ²" in text and "Full tail." in text


@pytest.mark.parametrize("route", ["chat", "session"])
def test_final_ai_card_now_and_session_log_share_canonical_text_and_leave_speech_and_student_text_alone(
        tmp_path, monkeypatch, route):
    from test_tui import app_for
    from tutor_app.screens import ChatScreen, SessionScreen

    app, vault = app_for(tmp_path, monkeypatch)

    async def answer(prompt, **kwargs):
        yield VISUAL[:11]
        yield VISUAL[11:]
        app.ai.last = ai.Result(text=VISUAL, speech=SPEECH)

    async def go():
        async with app.run_test(size=(100, 30)) as pilot:
            await pilot.pause()
            monkeypatch.setattr(app.ai, "stream", answer)
            if route == "chat":
                app.push_screen(ChatScreen())
                await pilot.pause()
                screen = app.screen
                box = screen.query_one("#panel Composer", Composer)
            else:
                screen = SessionScreen({"mode": "test", "focus": ["9702-2.1"], "minutes": 40})
                app.push_screen(screen)
                await pilot.pause()
                for question in app.tutor.session["presented"].values():
                    question["unassisted"] = False  # an ordinary question allows a formatting-only tutor nudge
                await pilot.press("ctrl+t")
                await pilot.pause()
                box = app.screen.query_one("#q", Composer)
            box.load_text(STUDENT)
            await pilot.press("enter")
            await app.workers.wait_for_complete()
            await pilot.pause()

            panel = ai_card(screen)
            assert panel.card == ("ai", "Tutor (AI)", CANONICAL)
            text = rendered(panel)
            assert "𝑥ᵢ²" in text and "x_1^2 * y" in text
            assert screen.readable == SPEECH
            assert app.ai.last.speech == SPEECH
            student_panel = next(entry.content for entry in screen.query(".entry")
                                 if getattr(entry.content, "card", (None,))[0] == "you"
                                 and entry.content.card[2] == STUDENT)
            assert STUDENT in rendered(student_panel, 140)

            expected = views.card_block("ai", "Tutor (AI)", CANONICAL)
            notes = [(vault / "Now.md").read_text()]
            if route == "session":
                notes.append((vault / views.lesson_rel(vault, app.tutor.session["log"])).read_text())
            for note in notes:
                assert expected in note
                assert STUDENT in note
                assert SPEECH not in note
            await app.ai.close()

    asyncio.run(go())


@pytest.fixture
def local_without_runtime(monkeypatch):
    from tutor_app.local_ai import LocalAI

    model = "ollama:qwen3.5:9b"

    async def warm(self, selected, timeout=120):
        return ai.Result()

    monkeypatch.setattr(LocalAI, "warm", warm)
    monkeypatch.setattr(local_models, "available_models", lambda: (model,))
    return model


@pytest.mark.parametrize("outcome", ["complete", "cancel", "error"])
def test_local_stream_buffers_split_math_with_progress_and_finishes_or_stops_cleanly(
        tmp_path, monkeypatch, local_without_runtime, outcome):
    from test_tui import app_for
    from tutor_app.screens import ChatScreen

    app, vault = app_for(tmp_path, monkeypatch)
    app.settings.ai_ask_model = local_without_runtime

    async def go():
        async with app.run_test(size=(80, 24)) as pilot:
            await pilot.pause()
            app.push_screen(ChatScreen())
            await pilot.pause()
            screen = app.screen
            reached, advance = asyncio.Queue(), asyncio.Queue()
            monkeypatch.setattr(app.ai, "progress_for", lambda model: {"phase": "generating"})

            async def answer(prompt, **kwargs):
                for piece in ("Visible start. \\", "(x_i^2", "\\). Full tail."):
                    yield piece
                    reached.put_nowait(None)
                    await advance.get()
                app.ai.last = (ai.Result(text=r"Visible start. \(x_i^2\). Full tail.", speech=SPEECH)
                               if outcome == "complete" else
                               ai.Result(ok=False, status="error", message="The test reply stopped."))

            monkeypatch.setattr(app.ai, "stream", answer)
            worker = screen.reply("Explain an index")
            for stage in range(2 if outcome == "cancel" else 3):
                await asyncio.wait_for(reached.get(), 2)
                await pilot.pause(0.22)  # the local progress timer redraws the pending card
                text = transcript(screen, 80)
                assert "Visible start." in text
                assert "Generating reply" in text
                assert "$" not in text and "\\" not in text
                assert "x_i" not in text and "^2" not in text
                assert "Visible start." not in (vault / "Now.md").read_text()
                if stage < (1 if outcome == "cancel" else 2):
                    advance.put_nowait(None)

            if outcome == "cancel":
                worker.cancel()
                await pilot.pause(0.25)
                assert "cancelled" in transcript(screen, 80).lower()
            else:
                advance.put_nowait(None)
                await worker.wait()
                await pilot.pause()
                if outcome == "complete":
                    panel = ai_card(screen)
                    assert panel.card[2] == "Visible start. $x_i^2$. Full tail."
                    assert "𝑥ᵢ²" in rendered(panel, 80) and "Full tail." in rendered(panel, 80)
                    assert views.card_block(*panel.card) in (vault / "Now.md").read_text()
                    assert screen.readable == SPEECH
                else:
                    assert "The test reply stopped." in transcript(screen, 80)
                    assert "AI paused" in (vault / "Now.md").read_text()
            assert "Generating reply" not in transcript(screen, 80)
            assert "\\" not in transcript(screen, 80)
            await app.ai.close()

    asyncio.run(go())


def test_existing_ai_teaching_and_profile_caches_are_canonical_when_consumed_without_rewriting_files(
        tmp_path, monkeypatch):
    from test_tui import app_for
    from tutorlib import lesson, report

    app, vault = app_for(tmp_path, monkeypatch)
    app.settings.ai = False
    card = {field: VISUAL for field in ("motivate", "establish", "connect", "note", "self_explain")}
    card.update(source="ai", machine={"expr": r"\(x_i^2\)"})
    summary = {"text": VISUAL, "at": "2026-10-24T11:00:00+08:00"}
    card_path = vault / ".tutor/cache/teach/9702-2.1.1.json"
    card_path.parent.mkdir(parents=True)
    card_bytes = json.dumps(card).encode()
    card_path.write_bytes(card_bytes)
    summary_path = vault / ".tutor/profile_ai.json"
    summary_bytes = json.dumps(summary).encode()
    summary_path.write_bytes(summary_bytes)

    async def go():
        async with app.run_test(size=(100, 30)) as pilot:
            await pilot.pause()
            consumed = lesson.teach_card(app.tutor, "9702-2.1.1")
            assert consumed == {**card, **dict.fromkeys(("motivate", "establish", "connect", "note", "self_explain"),
                                                      CANONICAL)}
            assert report.load_ai_summary(app.tutor) == {**summary, "text": CANONICAL}
            report.profile_note(app.tutor)
            assert "> Use $x_i^2$." in (vault / "Profile.md").read_text()
            assert card_path.read_bytes() == card_bytes and summary_path.read_bytes() == summary_bytes
            await app.ai.close()

    asyncio.run(go())


def test_resuming_an_ai_teaching_card_normalises_before_terminal_and_notes_diverge(tmp_path, monkeypatch):
    from test_tui import app_for
    from tutor_app.screens import SessionScreen

    app, vault = app_for(tmp_path, monkeypatch)
    app.settings.ai = False

    async def go():
        async with app.run_test(size=(100, 30)) as pilot:
            await pilot.pause()
            tutor = app.tutor
            tutor.start("lesson", minutes=10, focus=["9702-2.1"])
            tutor.session["blocks"] = [{"kind": "node", "kc": "9702-2.1.1", "i": 0,
                                        "phases": ["motivate"], "method": "explain", "misses": 0,
                                        "mistakes": [], "card": {"source": "ai", "motivate": VISUAL}}]
            tutor.session["cursor"] = 0
            tutor.session.pop("awaiting", None)
            tutor.session["presented"] = {}
            screen = SessionScreen(None)
            app.push_screen(screen)
            await pilot.pause()

            assert screen.act["text"] == CANONICAL
            panel = next(entry.content for entry in screen.query(".entry")
                         if getattr(entry.content, "card", (None, None, None))[2] == CANONICAL)
            assert "𝑥ᵢ²" in rendered(panel)
            expected = views.card_block(*panel.card)
            for path in (vault / "Now.md", vault / views.lesson_rel(vault, tutor.session["log"])):
                assert expected in path.read_text()
            await app.ai.close()

    asyncio.run(go())
