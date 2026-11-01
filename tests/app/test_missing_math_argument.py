"""A reproduced model font command must not become a MathJax error in notes."""
import json

import pytest

from tutor_app.chat_output import DocumentDecoder
from tutor_app.output_format import normalise_visual, terminal_visual


@pytest.mark.parametrize("source", [
    r"$\texttt$", r"$\mathrm$", r"$\frac$", r"${\mathbf}$", r"$\sqrt$", r"\texttt",
])
def test_missing_required_command_argument_is_literal_in_both_displays(source):
    canonical = normalise_visual(source)
    assert "Unformatted expression" in canonical
    assert source in canonical
    assert normalise_visual(canonical) == canonical
    assert source in terminal_visual(canonical)


def test_real_font_command_failure_is_canonical_before_terminal_and_notes_diverge():
    source = r"The function creates $\texttt${record} outside its body."
    code = 'record = {"reply": "x_1^2", "cost": "$5", "rate": "50%"}'
    wire = json.dumps({"blocks": [{"kind": "code", "text": code},
                                  {"kind": "paragraph", "text": source}]})
    decoder = DocumentDecoder()
    decoder.feed(wire)
    canonical, _ = decoder.finish()
    assert "Unformatted expression" in canonical
    assert r"$\texttt$" in canonical
    assert code in canonical
    assert code in terminal_visual(canonical)
    assert decoder.document["blocks"][1]["text"] == source


@pytest.mark.parametrize("source", [
    r"$\texttt{record}$", r"$\mathrm{N}$", r"$\frac{1}{2}$", r"$\sqrt{x}$",
    r"$\mathrm N$", r"$\texttt{}$", r"\texttt{record}",
    r"`$\texttt$`", "```tex\n$\\mathrm$\n```", "The price is $5 and the rate is 50%.",
])
def test_valid_arguments_and_literal_sources_keep_their_existing_contract(source):
    assert "Unformatted expression" not in normalise_visual(source)
