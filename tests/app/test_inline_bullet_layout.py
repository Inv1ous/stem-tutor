"""Recover the reported legacy AI list without interpreting scientific or literal dots."""
from datetime import datetime
from io import StringIO

import pytest
from markdown_it import MarkdownIt
from rich.console import Console
from textual.widgets import Static

from tutor_app import cards, look
from tutor_app.output_format import normalise_visual, terminal_visual
from tutorlib import views


# Frozen verbatim from the user's 111-word screenshot, also reproduced in
# /tmp/stem-format-current/current-user-example.svg before this repair.
INTRO = ("Chemical bonding (9701) examines how atoms form compounds via ionic, covalent, metallic, "
         "hydrogen and van der Waals interactions.")
POINTS = (
    "Ionic bonds arise when an atom transfers one or more electrons to another; its charge, lattice energy "
    "and molar volume depend on ion radius and charge.",
    "Covalent bonds involve shared pairs; non-polar if the electronegativity difference is zero, polar if "
    "it is greater than zero.",
    "Bond order equals the number of shared electrons divided by two; higher order shortens the bond "
    "and increases strength.",
    "Bond length inversely relates to charge density; higher charge leads to shorter bonds.",
    "VSEPR models predict geometry by treating lone pairs as electron-pair regions.",
)
SCREENSHOT = INTRO + " • " + " • ".join(POINTS)
CANONICAL = INTRO + "\n\n- " + "\n\n- ".join(POINTS)


def rendered(panel, width=100):
    console = Console(width=width, record=True, file=StringIO(), color_system=None)
    console.print(panel)
    return console.export_text()


def test_reported_inline_bullets_become_five_loose_markdown_list_items():
    canonical = normalise_visual(SCREENSHOT)
    assert canonical == CANONICAL
    assert normalise_visual(canonical) == canonical
    assert terminal_visual(canonical) == canonical
    tokens = MarkdownIt("commonmark").parse(canonical)
    assert sum(token.type == "list_item_open" for token in tokens) == 5
    assert all(not token.hidden for token in tokens if token.type == "paragraph_open")


@pytest.mark.parametrize("width", [80, 100, 140])
@pytest.mark.parametrize("theme", ["night", "day", "classic"])
def test_reported_list_has_real_blank_rows_and_hanging_items_in_ai_card(monkeypatch, width, theme):
    for name, colour in look.PALETTES[theme].items():
        monkeypatch.setitem(look.C, name, colour)
    panel = cards.ai(SCREENSHOT)
    assert panel.card[2] == CANONICAL
    lines = rendered(panel, width).splitlines()
    starts = [next(i for i, line in enumerate(lines) if point[:25] in line) for point in POINTS]
    for start in starts:
        assert "•" in lines[start]
        assert lines[start - 1].strip("│ ") == ""
    for first, second in zip(starts, starts[1:]):
        assert second >= first + 2
        continuation = lines[first + 1].strip("│")
        if continuation.strip():
            assert len(continuation) - len(continuation.lstrip()) > lines[first].index("•")


def test_character_split_stream_finishes_with_same_card_now_and_log_markdown(tmp_path):
    widget = Static()
    live = cards.Live(widget, every=0)
    accumulated = ""
    for char in SCREENSHOT:
        accumulated += char
        assert live.update(accumulated)
    assert widget.content.card[2] == CANONICAL
    final = cards.ai(accumulated)
    assert final.card[2] == widget.content.card[2]
    block = views.card_block(*final.card)
    views.write_now(tmp_path, "Formatting regression", [block])
    log = views.LessonLog.create(tmp_path, "Formatting regression", datetime(2026, 10, 26))
    log.card(*final.card)
    assert block in (tmp_path / "Now.md").read_text()
    assert block in (tmp_path / log.rel).read_text()
    assert ">\n> - Ionic bonds" in block
    assert ">\n> - VSEPR models" in block


@pytest.mark.parametrize("literal", [
    "$A. • B word. • C word.$",
    "`A. • B word. • C word.`", "```text\nA. • B word. • C word.\n```",
    "    A. • B word. • C word.\n", "https://example.org/A.•B.•C",
    "[A. • B word. • C word.](https://example.org)",
    '"A. • B word. • C word."', "'A. • B word. • C word.'",
    "“A. • B word. • C word.”", "‘A. • B word. • C word.’",
    r"`literal \n and \n\n; A. • B word. • C word.`",
])
def test_protected_or_quoted_bullet_glyphs_are_not_layout_evidence(literal):
    assert normalise_visual(literal) == literal
    assert "\n\n- " not in terminal_visual(literal)


def test_alternate_math_delimiters_keep_dot_source_when_canonicalised():
    assert normalise_visual(r"\(A. • B word. • C word.\)") == "$A. • B word. • C word.$"


@pytest.mark.parametrize("source", [
    "A single boundary. • Ionic bonds transfer electrons.",
    "Dot products: a • b and c • d.",
    "Capital vectors: A • B and C • D.",
    "Hydrates: CuSO4 • 5H2O and CoCl2 • 6H2O.",
    "Example. • B + C. • D + E.",
    "Example. • 2 electrons. • 3 protons.",
    'Example. • First point quotes "A. • B word. • C word." exactly.',
    "Example. • First point.\n\nExample. • Second point.",
    r"Literal glyphs. \• First point. \• Second point.",
    'Quoted glyph "•" means a bullet. Another "•" is literal.',
])
def test_ambiguous_or_scientific_dots_remain_source_text(source):
    assert normalise_visual(source) == source


def test_real_list_recovers_around_protected_math_code_and_quotes():
    source = ('Definitions. • First point uses $a • b$ and `CuSO4 • 5H2O`. '
              '• Second point quotes "A. • B word. • C word." exactly.')
    expected = ('Definitions.\n\n- First point uses $a • b$ and `CuSO4 • 5H2O`.\n\n'
                '- Second point quotes "A. • B word. • C word." exactly.')
    assert normalise_visual(source) == expected
    assert normalise_visual(expected) == expected


def test_typed_learner_list_is_preserved_in_real_card():
    panel = cards.you(SCREENSHOT)
    assert panel.card[2] == SCREENSHOT
    assert rendered(panel, 140).count("•") == 5


def test_legacy_teaching_cache_recovers_display_without_rewriting_saved_or_private_fields(tmp_path):
    from fixtures import make_vault
    from tutorlib import lesson, session, store

    tutor = session.Tutor(store.Vault(make_vault(tmp_path)), ai_visual=normalise_visual)
    kc = "9702-2.1.1"
    cached = {"motivate": "Recall chemical bonding.", "establish": SCREENSHOT, "note": "Check each definition.",
              "working": SCREENSHOT, "speech": SCREENSHOT,
              "options": {"A": SCREENSHOT}, "discover": {"answer": SCREENSHOT}}
    path = tutor.vault.tutor / "cache" / "teach" / f"{kc}.json"
    store.write_json(path, cached)
    original = path.read_bytes()
    loaded = lesson.teach_card(tutor, kc)
    assert loaded["establish"] == CANONICAL
    assert cards.ai(loaded["establish"]).card[2] == CANONICAL
    for field in ("working", "speech", "options", "discover"):
        assert loaded[field] == cached[field]
    assert path.read_bytes() == original


def test_native_sonnet_heading_renders_parenthesised_exponential_without_raw_caret():
    source = "1. Differentiate y = x e^(−x)"
    assert normalise_visual(source) == "1. Differentiate y = x $e^{−x}$"
    panel = cards.ai(source)
    shown = rendered(panel)
    assert "𝑒⁻ˣ" in shown
    assert "^" not in shown
    assert normalise_visual(panel.card[2]) == panel.card[2]


@pytest.mark.parametrize("source,canonical,shown", [
    ("e^(-x)", "$e^{-x}$", "𝑒⁻ˣ"),
    ("x^(a+b)", "$x^{a+b}$", "𝑥ᵃ⁺ᵇ"),
    ("x^(a+Q)", "$x^{a+Q}$", "(𝑥) to the power (𝑎 + 𝑄)"),
    ("x^(2n)", "$x^{2n}$", "𝑥²ⁿ"),
    ("x_(n+1)", "$x_{n+1}$", "𝑥ₙ₊₁"),
])
def test_unambiguous_bare_parenthesised_script_keeps_the_whole_group(source, canonical, shown):
    assert normalise_visual(source) == canonical
    assert normalise_visual(canonical) == canonical
    assert terminal_visual(source) == shown


def test_parenthesised_script_does_not_absorb_adjacent_equation_variables():
    source = "Differentiate y = x e^(−x) + c."
    assert normalise_visual(source) == "Differentiate y = x $e^{−x}$ + c."
    assert terminal_visual(source) == "Differentiate y = x 𝑒⁻ˣ + c."


@pytest.mark.parametrize("source", [
    "`e^(−x)`", "```python\ne^(−x)\n```", "    e^(−x)\n",
    "https://example.org/e^(−x)", "[e^(−x)](https://example.org/e^(−x))",
])
def test_parenthesised_scripts_inside_literal_spans_stay_exact(source):
    assert normalise_visual(source) == source
    assert terminal_visual(source) == source


@pytest.mark.parametrize("source", [
    "e^(−x", "x^()", "x^(a+(b))", "x^(a+b)^2", "x^(a+b)_n", r"e^(\unknown{x})",
])
def test_malformed_or_ambiguous_parenthesised_script_preserves_exact_labelled_source(source):
    canonical = normalise_visual(source)
    assert "Unformatted expression" in canonical
    assert source in canonical
    assert normalise_visual(canonical) == canonical
    assert terminal_visual(source) == canonical
