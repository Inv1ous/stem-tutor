"""Provider-neutral visual text preserves literals and never treats unfinished maths as prose."""
import json
from io import StringIO

import pytest
from markdown_it import MarkdownIt
from rich.console import Console


def normalise(text, **kwargs):
    from tutor_app.output_format import normalise_visual
    return normalise_visual(text, **kwargs)


def terminal(text, **kwargs):
    from tutor_app.output_format import terminal_visual
    return terminal_visual(text, **kwargs)


@pytest.mark.parametrize("source,want", [
    (r"Use \(x_i^2\).", "Use $x_i^2$."),
    (r"\[x^2=4\]", "$$\nx^2=4\n$$"),
    ("$ x^2 $", "$x^2$"),
    ("$$x^2=4$$", "$$\nx^2=4\n$$"),
    ("Use x_1 and x^2.", "Use $x_1$ and $x^2$."),
    (r"Use \frac{1}{2} here.", r"Use $\frac{1}{2}$ here."),
    ("## Method\n\n• First.\n• Second.", "**Method**\n\n- First.\n\n- Second."),
])
def test_canonical_visual_text(source, want):
    assert normalise(source) == want
    assert normalise(want) == want


@pytest.mark.parametrize("literal", [
    "`x_1^2 and $5`", "```python\nx_1^2\ncost='$5'\n```", "    x_1^2\n",
    "https://example.org/x_1?q=$5", r"\$5 and \$6", "It costs $5 and $6 today.",
    "It costs $5-$6.", "The price is $5.", "Yield is 95%.", "a_file_name.py",
])
def test_literals_and_currency_are_unchanged(literal):
    assert normalise(literal) == literal
    assert terminal(literal) == literal


@pytest.mark.parametrize("left,right", [("$", "$"), ("$$", "$$"), (r"\(", r"\)"), (r"\[", r"\]")])
def test_each_stream_prefix_holds_unfinished_math_but_keeps_prose(left, right):
    reply = "Method: " + left + r"x_i^2+\frac{1}{2}" + right + " is useful."
    for n in range(1, len(reply) + 1):
        prefix = reply[:n]
        out = terminal(prefix, partial=True)
        assert "\\frac" not in out and "x_i" not in out
        assert "$" not in out and "\\(" not in out and "\\[" not in out
        if n >= len("Method: "):
            assert out.startswith("Method: ")
    assert "𝑥ᵢ²" in terminal(reply)


def test_pending_math_cannot_hide_following_paragraph():
    source = "First $x^2\n\nNext paragraph stays visible."
    shown = terminal(source, partial=True)
    assert "Unformatted expression" in shown
    assert "Next paragraph stays visible." in shown


def test_pending_math_has_a_bounded_buffer():
    shown = terminal("Start $" + "x" * 2049, partial=True)
    assert "Unformatted expression" in shown and "x" * 2049 in shown


def test_final_unclosed_math_has_an_exact_labelled_fallback():
    source = r"$x_i+\frac{1}{2}"
    out = normalise(source)
    assert "Unformatted expression" in out and source in out
    assert normalise(out) == out


def test_terminal_only_fallback_keeps_valid_obsidian_math():
    source = r"$\unknown{x}$"
    assert normalise(source) == source
    assert "Unformatted expression" in terminal(source)
    assert source in terminal(source)


def test_math_is_protected_from_markdown_eating_multiplication():
    from tutor_app import cards
    c = Console(width=80, record=True, file=StringIO(), color_system=None)
    c.print(cards.ai("Multiply: $a*b*c$."))
    shown = c.export_text()
    assert "𝑎" in shown and "𝑏" in shown and "𝑐" in shown
    assert sum(shown.count(sign) for sign in ("*", "×", "·", "∗")) == 2


def test_literal_code_does_not_use_the_legacy_unit_prettifier():
    from tutor_app import cards
    c = Console(width=80, record=True, file=StringIO(), color_system=None)
    c.print(cards.ai("`x_1^2`\n\n```\nx_1^2\n```"))
    shown = c.export_text()
    assert shown.count("x_1^2") == 2
    assert "x_1²" not in shown


def test_a_list_after_math_still_has_a_logical_gap():
    assert normalise("Use $x^2$\n- First\n- Second") == "Use $x^2$\n\n- First\n\n- Second"


@pytest.mark.parametrize("source", [r"$\frac{x}{y$", "$x^$", "$x_{n$", r"\(x} + y\)"])
def test_malformed_closed_math_is_labelled_in_both_displays(source):
    assert "Unformatted expression" in normalise(source)
    assert source in normalise(source)
    assert source in terminal(source)


def test_a_long_prose_paragraph_is_split_only_between_complete_sentences():
    sentence = "This explanation gives one complete idea with a useful mathematical meaning."
    source = " ".join([sentence] * 8)
    shown = normalise(source)
    assert "\n\n" in shown
    assert shown.replace("\n\n", " ") == source
    assert all(len(p.split()) <= 50 for p in shown.split("\n\n"))


def test_aligned_math_rows_remain_separate_after_markdown():
    from tutor_app import cards
    c = Console(width=100, record=True, file=StringIO(), color_system=None)
    c.print(cards.ai(r"$$\begin{aligned}y&=x+1\\z&=2x\end{aligned}$$"))
    lines = c.export_text().splitlines()
    assert any("𝑦 = 𝑥 + 1" in line and "𝑧" not in line for line in lines)
    assert any("𝑧 = 2𝑥" in line and "𝑦" not in line for line in lines)


@pytest.mark.parametrize("link", ["[link](ftp://example.com/x_1^2)", "[link](../x_1^2)",
                                 "![image](images/x_1^2.png)", "[ref]: ../x_1^2\n"])
def test_all_link_destinations_remain_literal(link):
    assert normalise(link) == link
    assert terminal(link) == link


def test_an_unclosed_bare_command_keeps_its_whole_argument_together():
    source = r"Use \frac{x"
    assert terminal(source, partial=True) == "Use "
    assert r"\frac{x" in normalise(source)
    assert "Unformatted expression" in normalise(source)


def test_a_math_closer_inside_code_does_not_capture_the_literal_code():
    source = "Use $x + `cost=$5` + y$ here."
    result = normalise(source)
    assert "`cost=$5`" in result
    assert "Unformatted expression" in result
    assert "`cost=$5`" in terminal(source)


@pytest.mark.parametrize("source", ["1. First step.\n2. Second step.", "- First point.\n- Second point."])
def test_terminal_ai_list_items_have_a_visible_blank_row(source):
    from tutor_app import cards
    c = Console(width=80, record=True, file=StringIO(), color_system=None)
    c.print(cards.ai(source))
    lines = c.export_text().splitlines()
    first = next(i for i, line in enumerate(lines) if "First" in line)
    second = next(i for i, line in enumerate(lines) if "Second" in line)
    assert second == first + 2
    assert lines[first + 1].strip("│ ") == ""


@pytest.mark.parametrize("source,literal", [
    ("Use $x + `cost=$5` + y$ here.", "`cost=$5`"),
    ("Use $x + [link](relative/$5) + y$ here.", "[link](relative/$5)"),
])
def test_fallback_adjacent_to_literals_remains_idempotent_and_preserves_signs(source, literal):
    canonical = normalise(source)
    assert literal in canonical
    assert normalise(canonical) == canonical
    shown = terminal(source)
    assert literal in shown and "+ y" in shown
    assert "− y" not in shown


def test_a_bare_pending_macro_stops_before_the_next_paragraph():
    shown = terminal("Use \\frac{x\n\nNext paragraph.", partial=True)
    assert "Next paragraph." in shown and "Unformatted expression" in shown


def test_ai_explicit_line_breaks_do_not_merge_formulas_or_instructions():
    from tutor_app import cards
    c = Console(width=100, record=True, file=StringIO(), color_system=None)
    c.print(cards.ai("Given:\n$x=3$\n$v=2$\n\nCheck the units."))
    lines = c.export_text().splitlines()
    assert any("𝑥 = 3" in line and "𝑣" not in line for line in lines)
    assert any("𝑣 = 2" in line and "𝑥" not in line for line in lines)


def test_fallback_before_a_paragraph_keeps_final_card_and_note_text_identical():
    from tutor_app import cards
    source = "Use \\frac{x\n\nNext paragraph."
    canonical = normalise(source)
    assert normalise(canonical) == canonical
    assert cards.ai(canonical).card[2] == canonical


@pytest.mark.parametrize("decoded,want", [
    ("$" + "\x0c" + "rac{1}{2}$", r"$\frac{1}{2}$"),
    ("$" + "\t" + "ext{mass}$", r"$\text{mass}$"),
    ("$" + "\t" + "heta$", r"$\theta$"),
    ("$" + "\r" + "ho$", r"$\rho$"),
    ("$" + "\x08" + "eta$", r"$\beta$"),
])
def test_known_json_escape_typos_are_repaired_only_inside_explicit_math(decoded, want):
    assert normalise(decoded) == want
    assert "Unformatted expression" not in terminal(decoded)


@pytest.mark.parametrize("literal", ["`$\text{x}$`", "```python\nprint('$\text{x}$')\n```", "a\tb", "$x\ty$"])
def test_control_character_repair_does_not_change_literal_code_or_ordinary_whitespace(literal):
    assert normalise(literal) == literal


@pytest.mark.parametrize("code", ["    $\text{x}$\n", "```python\nprint('$\text{x}$')\n```\n"])
def test_a_json_formfeed_before_code_does_not_shift_markdown_source_ranges(code):
    source = "$\x0crac{1}{2}$\n\n" + code
    canonical = normalise(source)
    assert canonical.startswith(r"$\frac{1}{2}$")
    assert canonical.endswith(code)
    assert terminal(source).endswith(code)


@pytest.mark.parametrize("decoded,want", [("$\tan \theta$", r"$\tan \theta$"),
                                        ("$x\to y$", r"$x\to y$"),
                                        ("$\boxed{x^2}$", r"$\boxed{x^2}$")])
def test_json_math_escape_repair_uses_the_same_supported_commands_as_the_renderer(decoded, want):
    assert normalise(decoded) == want
    assert terminal(decoded) == terminal(want)


@pytest.mark.parametrize("control", ["\x00", "\x08", "\x0b", "\x0c", "\r", "\x1b", "\x1f", "\x7f", "\x85", "\x9b", "\x9f"])
@pytest.mark.parametrize("context", ["Prose: {}", "$x{}+1$", "`literal {}`", "```json\n{{\"value\": \"{}\"}}\n```", "$\\frac{{x{}"])
def test_residual_controls_use_a_labelled_json_source_fallback_without_terminal_controls(control, context):
    source = context.format(control)
    shown = terminal(source)
    assert "Unformatted source" in shown and "JSON-escaped" in shown
    assert not any(ord(ch) < 32 and ch not in "\n\t" or 127 <= ord(ch) <= 159 for ch in shown)
    blocks = [token for token in MarkdownIt("commonmark").parse(shown) if token.type == "fence"]
    assert len(blocks) == 1 and blocks[0].info == "json"
    assert json.loads(blocks[0].content) == source
    assert blocks[0].content.isascii()


def test_control_fallback_preserves_original_source_before_layout_and_math_normalisation():
    source = "## Original\n\n• Keep $ x^2 $ and 香港.\n\n```text\n\\u001b is printed; \x1b is a byte.\n```"
    shown = terminal(source)
    blocks = [token for token in MarkdownIt("commonmark").parse(shown) if token.type == "fence"]
    assert len(blocks) == 1
    assert json.loads(blocks[0].content) == source


@pytest.mark.parametrize("source", ["$\x0cx$", "$x\x0c$", "$\r x$", "$x\x85$", "## Title\x0c"])
def test_controls_trimmed_by_math_or_layout_still_preserve_the_original_source(source):
    shown = terminal(source)
    blocks = [token for token in MarkdownIt("commonmark").parse(shown) if token.type == "fence"]
    assert "JSON-escaped" in shown and len(blocks) == 1
    assert json.loads(blocks[0].content) == source


@pytest.mark.parametrize("source", [r"`code \u0000 \u001b`", '```json\n{"value":"\\u001b"}\n```'])
def test_control_safety_does_not_rewrite_printable_canonical_literal_source(source):
    assert normalise(source) == source


@pytest.mark.parametrize("source", [
    "$x\x0c$", "$\x0cx$", "## Title\x0c", "$x\x85$", "$x\r$",
    "`code \x00 \x1b`", "```text\n$\x0crac{1}{2}$\n```", "$\\frac{x\x1b",
])
def test_canonical_control_fallback_survives_cards_and_repeated_normalisation(source):
    from tutor_app import cards
    canonical = normalise(source)
    card = cards.ai(source)
    assert "JSON-escaped" in canonical
    assert normalise(canonical) == terminal(canonical) == card.card[2] == canonical
    blocks = [token for token in MarkdownIt("commonmark").parse(canonical) if token.type == "fence"]
    assert len(blocks) == 1 and blocks[0].info == "json"
    assert json.loads(blocks[0].content) == source
    console = Console(width=100, record=True, file=StringIO(), color_system=None)
    console.print(card)
    shown = console.export_text()
    assert "JSON-escaped" in shown
    assert not any(ord(ch) < 32 and ch not in "\n\t" or 127 <= ord(ch) <= 159 for ch in shown)


@pytest.mark.parametrize("source,canonical,shown", [
    ("First.\r\nSecond.\r\n", "First.\nSecond.\n", "First.\nSecond.\n"),
    ("```text\r\nx_1^2\r\n```", "```text\r\nx_1^2\r\n```", "```text\nx_1^2\n```"),
    ("`literal\r\ncode`", "`literal\r\ncode`", "`literal\ncode`"),
    ("$x\r\n+1$", "$x\r\n+1$", "𝑥 + 1"),
])
def test_valid_crlf_keeps_existing_canonical_layout_and_safe_terminal_line_endings(source, canonical, shown):
    assert normalise(source) == canonical
    assert normalise(canonical) == canonical
    assert terminal(canonical) == shown


def test_known_formfeed_math_repair_happens_before_the_terminal_control_guard():
    source = "The fraction is $\x0crac{1}{2}$."
    assert terminal(source) == "The fraction is ½."


def test_printed_control_escapes_and_ordinary_math_keep_their_terminal_rendering():
    source = r'Literal `\u001b` and `\u0000`; $x^2$ and $\frac{1}{2}$.'
    assert terminal(source) == r'Literal `\u001b` and `\u0000`; 𝑥² and ½.'
