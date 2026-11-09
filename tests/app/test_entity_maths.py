"""A model that writes maths as HTML entities must still reach the learner as maths.

Found in a local-model reply about stretching a spring: the integral sign and the digits arrived as
``&#x222B;`` and ``&#x0031;``, so the maths source failed to parse and every span became an
"Unformatted expression" box. Cloud models can do the same, so the repair lives in the shared
visual formatter and the shared document decoder.
"""
import importlib
import inspect
import json

import pytest

from tutor_app import ai, prompts
from tutor_app.chat_output import DocumentDecoder, document_instructions
from tutor_app.output_format import normalise_visual, terminal_visual

INTEGRAL = "$$\n&#x222B;_{x_1}^{x_2} F(x) dx\n$$"
WORK = "$$\n[&#x0031;&#x0032;&#x0036; kx^2&#x0032;&#x0035;]_0^{x} = &#x0031;&#x0032;&#x0036; kx^2\n$$"
INLINE = "The result, $W = &#x0031;&#x0032;&#x0036; kx^2$, represents the elastic potential energy."


def wire(*blocks: dict) -> str:
    return json.dumps({"blocks": list(blocks)})


def decode(source: str) -> tuple[str, str]:
    decoder = DocumentDecoder()
    streamed = decoder.feed(source)
    canonical, _ = decoder.finish()
    assert streamed == canonical  # the stream never shows a different document from the finish
    return canonical, streamed


@pytest.mark.parametrize("source,expected", [
    (INTEGRAL, r"\int_{x_1}^{x_2} F(x) dx"),
    (WORK, "[126 kx^225]_0^{x} = 126 kx^2"),
])
def test_display_entities_decode_to_the_intended_maths(source, expected):
    canonical = normalise_visual(source)
    assert canonical == "$$\n" + expected + "\n$$"
    assert "Unformatted expression" not in canonical
    shown = terminal_visual(source)
    assert "Unformatted expression" not in shown
    assert "&#x" not in shown


def test_inline_entities_decode_inside_the_sentence():
    canonical = normalise_visual(INLINE)
    assert canonical == "The result, $W = 126 kx^2$, represents the elastic potential energy."
    shown = terminal_visual(INLINE)
    assert shown == "The result, 𝑊 = 126𝑘𝑥², represents the elastic potential energy."
    assert "Unformatted expression" not in shown


@pytest.mark.parametrize("source", ["$&int;$", "$&#8747;$", "$&amp;#x222B;$", "$&#x222B;$"])
def test_named_numeric_and_repeated_entities_all_reach_the_same_maths(source):
    assert normalise_visual(source) == "$∫$"
    assert normalise_visual(normalise_visual(source)) == "$∫$"  # stable under a second pass
    assert terminal_visual(source) == "∫"


@pytest.mark.parametrize("source", [
    "`&#x222B;_{x_1}^{x_2}`", "```tex\n&#x222B;_{x_1}^{x_2}\n```", "    &#x222B;_{x_1}^{x_2}\n",
])
def test_code_keeps_entity_bytes_exact(source):
    assert normalise_visual(source) == source
    assert terminal_visual(source) == source


def test_an_entity_naming_a_control_stays_literal_source():
    source = r"Use $\text{&#x202e;abc}$ as source."
    assert normalise_visual(source) == source


def test_genuinely_unknown_macros_keep_their_labelled_fallback():
    display = "$$\n\\unknownmacro{x}\n$$"
    assert "**Unformatted expression:**" in terminal_visual(display)
    assert "\\unknownmacro{x}" in terminal_visual(display)
    inline = terminal_visual(r"Use $\unknownmacro{x}$ here.")
    assert inline == r"Use Unformatted expression: `$\unknownmacro{x}$` here."  # inline, not a mid-sentence box


@pytest.mark.parametrize("source", ["$W = &#x22", "The integral $&#x222B", "$$\n&#x222B;_{x_1}"])
def test_streaming_waits_for_an_unfinished_entity(source):
    for shown in (normalise_visual(source, partial=True), terminal_visual(source, partial=True)):
        assert "Unformatted expression" not in shown and "&#x" not in shown


def test_streaming_holds_a_trailing_entity_outside_maths():
    assert normalise_visual("Value &#x22", partial=True) == "Value "
    assert normalise_visual("Value &#x22") == "Value &#x22"  # complete text keeps the literal source


def test_orphan_comma_and_bare_equation_prefix_are_cleaned():
    assert normalise_visual("$$\n\\unknownmacro{x}\n$$\n\n, represents the energy.").endswith(
        "\n\nrepresents the energy.")
    assert normalise_visual("W =\n\n$$126 kx^2$$") == "$$\nW = 126 kx^2\n$$"


@pytest.mark.parametrize("module", ["tutor_app.codex_ai", "tutor_app.abacus_ai"])
def test_codex_and_abacus_document_path_is_clean(module):
    provider = importlib.import_module(module)
    assert "DocumentDecoder" in inspect.getsource(provider)  # both providers share the one decoder
    source = wire({"kind": "equation", "text": "&#x222B;_{x_1}^{x_2} F(x) dx"},
                  {"kind": "step", "text": INLINE},
                  {"kind": "paragraph", "text": "The work done is $W = &#x0031;&#x0032;&#x0036; kx^2$."})
    canonical, streamed = decode(source)
    assert "Unformatted expression" not in canonical and "&#x" not in canonical
    assert "$$\n" + r"\int_{x_1}^{x_2} F(x) dx" + "\n$$" in canonical
    assert "𝑊 = 126𝑘𝑥²" in terminal_visual(canonical)
    assert streamed == canonical


def test_prompts_forbid_html_entities_in_mathematics():
    rule = "HTML entities (&#x222B;, &int;)"
    assert rule in prompts.MATH_RULE and r"\frac{1}{2}" in prompts.MATH_RULE
    assert rule in document_instructions()
    assert rule in ai.VISUAL_BRIEF
    assert "MATH_RULE" in inspect.getsource(prompts.learn)
