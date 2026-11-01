"""One output format in lesson mode: cards written in advance (the P2 chapter material) and text written by the AI are
laid out by the same normaliser and drawn by the same renderer, in the Terminal and in Obsidian. Representative checks, not a
claim that no formatting error can occur."""
from library_assets import read_json as library_json
import asyncio
import json
import re
from pathlib import Path

import pytest
from rich.console import Console
from test_tui import app_for
from textual.widgets import Static
from tutor_app import learn_reply
from tutor_app.ai import Result
from tutor_app.output_format import normalise_visual, terminal_visual
from tutor_app.screens import SessionScreen

ROOT = Path(__file__).resolve().parents[2]
CARDS = library_json('build/work/teach/P2-1.json')
KC, SUB = "9702-2.1.1", "9702-2.1"


def _fields(card):
    for key in ("plain_words", "establish", "connect", "self_explain", "note"):
        if isinstance(card.get(key), str):
            yield key, card[key]
    for i, t in enumerate(card.get("terms", [])):
        yield f"terms[{i}]", t["meaning"]
    for i, f in enumerate(card.get("forms", [])):
        for key in ("example", "check"):
            if isinstance(f.get(key), str):
                yield f"forms[{i}].{key}", f[key]
    for i, m in enumerate(card.get("misconceptions", [])):
        for key in ("idea", "temptation", "fix"):
            yield f"misconceptions[{i}].{key}", m[key]


def test_the_prepared_p2_material_already_follows_the_output_format():
    """The normaliser may re-space a list, but must not have to change a word, a symbol or a maths delimiter."""
    squash = lambda s: re.sub(r"\s+", "", s)  # noqa: E731
    odd = [(kc, name) for kc, card in CARDS.items() for name, text in _fields(card)
           if squash(normalise_visual(text)) != squash(text)]
    assert odd == []


def _log(screen) -> str:
    console = Console(width=100, record=True, file=open("/dev/null", "w"))
    for w in screen.query("#log .entry"):
        if isinstance(w, Static):
            console.print(w.content)
    return console.export_text()


@pytest.mark.parametrize("mode,italic", [("lesson", True), ("test", False)])
def test_in_a_lesson_a_prepared_card_and_an_ai_reply_are_drawn_the_same_way(tmp_path, monkeypatch, mode, italic):
    app, vault = app_for(tmp_path, monkeypatch)
    card = {"plain_words": "Let $n=2k$; then $n^2+n=2(2k^2+k)$, so $n\\in\\mathbb{Z}$ gives an even result.",
            "diagrams": ["Assets/P2/proof.svg"], "diagram_descriptions": ["The cases cover every integer."]}
    monkeypatch.setattr(learn_reply, "published_related_cards", lambda tutor, kc: {kc: card})

    async def fake_model(prompt, schema=None, **kw):
        if "blocks" in (schema or {}).get("properties", {}):
            return {"blocks": [{"kind": "paragraph", "text": "Take $n=2k+1$."},
                               {"kind": "equation", "text": "(2k+1)^2=4k^2+4k+1"}]}, Result()
        return {"actions": [{"action": "explain", "section": "plain_words"}, {"action": "write", "topic": "Odd case"}]}, Result()

    async def go():
        async with app.run_test(size=(100, 30)) as pilot:
            monkeypatch.setattr(app, "ai_available", lambda mode: True)
            monkeypatch.setattr(app.ai, "one_shot", fake_model)
            app.push_screen(SessionScreen({"mode": mode, "minutes": 10, "focus": [SUB]}))
            await pilot.pause()
            scr, t = app.screen, app.tutor
            t.session["presented"], t.session["queue"] = {}, {}
            scr.kc = KC
            await scr.learn_request("I do not see where to begin with this idea").wait()
            await pilot.pause()
            shown = _log(scr)
            # the AI-written card always uses the AI renderer (italic maths letters); the prepared card does so in a lesson
            assert "𝑛 = 2𝑘 + 1" in shown or "𝑛 = 2𝑘+1" in shown or "Take 𝑛" in shown
            assert "𝑛² + 𝑛 = 2(2𝑘² + 𝑘)" in shown  # the card the AI asked for: the AI renderer in every mode
            scr.say_step({"activity": "explain", "title": "Idea", "text": card["plain_words"]})  # a lesson's own step
            await pilot.pause()
            assert (_log(scr).count("𝑛² + 𝑛 = 2(2𝑘² + 𝑘)") == 2) is italic  # a lesson draws it the same way; other modes as before
            assert "ℤ" in shown and "$" not in shown  # symbols drawn, no raw delimiters left in the terminal
            now = (vault / "Now.md").read_text()
            assert "$n^2+n=2(2k^2+k)$" in now and "$n\\in\\mathbb{Z}$" in now  # Obsidian typesets the LaTeX itself
            assert "> $$\n> (2k+1)^2=4k^2+4k+1\n> $$" in now
            await app.ai.close()
    asyncio.run(go())


def test_what_the_terminal_cannot_draw_keeps_its_meaning_and_obsidian_keeps_the_source():
    shown = terminal_visual(r"Use $\unknownmacro{x}$ and $x^2+1$.")
    assert r"\unknownmacro{x}" in shown and "Unformatted expression" in shown  # the source, not a silent drop
    assert normalise_visual(r"Use $\unknownmacro{x}$").count(r"$\unknownmacro{x}$") == 1  # Obsidian gets it unchanged
    assert "![[Assets/P2/x.svg]]" == normalise_visual("![[Assets/P2/x.svg]]")  # an embed is never altered
    assert "```" in normalise_visual("```python\nx_1 = 2\n```") and "x_1 = 2" in normalise_visual("```python\nx_1 = 2\n```")


def test_units_written_with_a_control_space_render_in_the_terminal():
    """Found in the chemistry trial: a model wrote $-818\\ \\mathrm{kJ\\ mol^{-1}}$ and the terminal fell back to source."""
    shown = terminal_visual(r"$\Delta H = 2632 - 3450 = -818\ \mathrm{kJ\ mol^{-1}}$")
    assert shown == "Δ𝐻 = 2632 − 3450 = −818 kJ mol⁻¹"
