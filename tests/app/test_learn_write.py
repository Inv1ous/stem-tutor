"""A tutor-written explanation goes through the program's one output format (chat_output blocks, normalise_visual) and
its plain equations are checked; the rest is labelled unchecked."""
import pytest
from tutor_app import learn_write
from tutor_app.chat_output import DocumentError

DOC = {"blocks": [
    {"kind": "paragraph", "text": "Short version: add the three numbers and factorise."},
    {"kind": "step", "text": "Let the integers be $n$, $n+1$ and $n+2$."},
    {"kind": "equation", "text": r"n+(n+1)+(n+2)=3n+3=3(n+1)"},
    {"kind": "step", "text": "So the sum is three times an integer."},
    {"kind": "equation", "text": r"\sum_{k=1}^{n} k=\frac{n(n+1)}{2}"}]}


def test_blocks_become_canonical_markdown_and_plain_equations_are_checked():
    out = learn_write.lay_out(DOC)
    assert out["text"].startswith("Short version: add the three numbers and factorise.")
    assert "1. Let the integers be $n$, $n+1$ and $n+2$." in out["text"] and "$$" in out["text"]  # numbering and delimiters: the program's
    assert out["checked"] == ["n+(n+1)+(n+2) = 3n+3", "3n+3 = 3(n+1)"]
    assert out["unchecked"] == 1  # the sum formula is not plain algebra


def test_a_false_equation_stops_the_whole_explanation():
    bad = {"blocks": [{"kind": "paragraph", "text": "A worked line."},
                      {"kind": "equation", "text": "n+(n+1)+(n+2)=3n+2"}]}
    with pytest.raises(ValueError, match="not true"):
        learn_write.lay_out(bad)


@pytest.mark.parametrize("doc", [{"blocks": []}, {"blocks": [{"kind": "poem", "text": "x"}]}, {"text": "plain"}, "plain",
                                 {"blocks": [{"kind": "paragraph", "text": "ok"}], "extra": 1}])
def test_a_reply_that_is_not_a_valid_document_is_refused(doc):
    with pytest.raises(DocumentError):
        learn_write.lay_out(doc)


def test_the_prompt_carries_the_shared_format_rules_and_the_lesson_context():
    text = learn_write.prompt("an example please", "Consecutive integers", "IDEA: proof")
    assert "Use semantic blocks" in text and "IDEA: proof" in text and "never reveal the answer" in text


def test_personal_context_survives_a_long_prepared_card():
    personal = 'Lesson goal: Learn it properly from scratch\nStudent: I confuse distance with displacement.'
    text = learn_write.prompt('Another example?', 'Displacement', 'PREPARED MATERIAL ' * 1000,
                              learner_context=personal)
    assert personal in text


def test_a_line_that_names_a_quantity_is_a_definition_not_an_identity_to_test():
    doc = {"blocks": [{"kind": "paragraph", "text": "Name the sum, then simplify it."},
                      {"kind": "equation", "text": "S=n+(n+1)+(n+2)"}, {"kind": "equation", "text": "S=3n+3"},
                      {"kind": "equation", "text": "n=2k"}]}
    out = learn_write.lay_out(doc)
    assert out["checked"] == [] and out["unchecked"] == 3  # said to be unchecked, not refused
