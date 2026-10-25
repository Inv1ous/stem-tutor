"""Harmony boundaries keep reasoning out of replies and JSON constraints."""
import importlib
import importlib.util
import re

import pytest


START, END, MESSAGE, CHANNEL, RETURN = 200006, 200007, 200008, 200005, 200002
CONSTRAIN = 200003


def harmony():
    assert importlib.util.find_spec("tutor_app.mlx_harmony") is not None, "Harmony parser is missing"
    return importlib.import_module("tutor_app.mlx_harmony")


def parser():
    module = harmony()
    return module.HarmonyParser(module.HarmonyTokens())


def feed(stream, values):
    return [token for token, text in values if stream.feed(token, text)]


def final_header():
    return [(CHANNEL, ""), (1, "fi"), (2, "nal"), (MESSAGE, "")]


def analysis_header():
    return [(CHANNEL, ""), (1, "anal"), (2, "ysis"), (MESSAGE, "")]


def next_assistant():
    return [(END, ""), (START, ""), (3, "assis"), (4, "tant")]


def test_direct_final_admits_only_body_tokens():
    stream = parser()
    assert feed(stream, final_header() + [(5, '{"reply":"香港"}'), (RETURN, "")]) == [5]
    stream.finish()
    assert stream.final_tokens == 1


def test_unlabelled_message_cannot_export_tokens_or_activate_grammar():
    module = harmony()
    stream = parser()
    with pytest.raises(module.HarmonyError, match="header"):
        stream.feed(MESSAGE)
    assert stream.final_tokens == 0
    calls = []
    gate = module.FinalOnlyLogitsProcessor(
        module.HarmonyTokens(), lambda tokens, logits: calls.append(list(tokens)),
        lambda token: "", skip=2,
    )
    with pytest.raises(module.HarmonyError, match="header"):
        gate([START, 2, MESSAGE], "logits")
    assert calls == []


@pytest.mark.parametrize("header", [
    [(CHANNEL, ""), (1, "final "), (CONSTRAIN, ""), (2, "j"), (3, "son")],
    [(CONSTRAIN, ""), (2, "json"), (CHANNEL, ""), (1, "fi"), (3, "nal")],
    [(CHANNEL, ""), (1, "fi"), (2, "nal j"), (3, "son")],
    [(CHANNEL, ""), (1, "final "), (CONSTRAIN, ""), (2, "J"), (3, "SON")],
    [(CHANNEL, ""), (1, "fi"), (2, "nal J"), (3, "SON")],
])
def test_json_header_metadata_waits_for_complete_final_boundary(header):
    module = harmony()
    stream = parser()
    assert feed(stream, header) == []
    assert not stream.final
    assert stream.feed(MESSAGE) is False
    assert stream.feed(20, '{"reply":"Visible"}') is True
    stream.feed(RETURN)
    stream.finish()
    assert stream.header_size == 0
    calls = []
    texts = {token: text for token, text in header}
    gate = module.FinalOnlyLogitsProcessor(
        module.HarmonyTokens(), lambda tokens, logits: calls.append(list(tokens)) or logits,
        lambda token: texts.get(token, ""), skip=2,
    )
    tokens = [START, 2]
    for token, _ in header:
        tokens.append(token)
        gate(tokens, "logits")
        assert calls == []
    tokens.append(MESSAGE)
    gate(tokens, "logits")
    assert calls == [[]]
    tokens.append(20)
    gate(tokens, "logits")
    assert calls == [[], [20]]


@pytest.mark.parametrize("annotation", ["json", "JSON"])
def test_json_annotation_on_analysis_never_activates_grammar(annotation):
    module = harmony()
    calls = []
    texts = {1: "analysis ", 2: annotation, 3: "assistant", 4: "final"}
    gate = module.FinalOnlyLogitsProcessor(
        module.HarmonyTokens(), lambda tokens, logits: calls.append(list(tokens)) or logits,
        lambda token: texts.get(token, ""), skip=2,
    )
    tokens = [START, 3]
    for token in [CHANNEL, 1, CONSTRAIN, 2, MESSAGE, 10, END, START, 3, CHANNEL, 4]:
        tokens.append(token)
        gate(tokens, "logits")
    assert calls == []
    tokens.append(MESSAGE)
    gate(tokens, "logits")
    assert calls == [[]]
    assert gate.parser.header_size == 0


@pytest.mark.parametrize("header", [
    [(CONSTRAIN, ""), (1, "json"), (MESSAGE, "")],
    [(CHANNEL, ""), (1, "final "), (CONSTRAIN, ""), (MESSAGE, "")],
    [(CHANNEL, ""), (1, "final "), (CONSTRAIN, ""), (2, "json"), (CONSTRAIN, "")],
    [(CHANNEL, ""), (1, "final json extra"), (MESSAGE, "")],
    [(CHANNEL, ""), (1, "analysis final"), (MESSAGE, "")],
    [(CHANNEL, ""), (1, "FINAL JSON"), (MESSAGE, "")],
    [(CHANNEL, ""), (1, "final "), (CONSTRAIN, ""), (2, "x" * 129)],
])
def test_invalid_json_header_metadata_never_becomes_a_final_reply(header):
    stream = parser()
    with pytest.raises(harmony().HarmonyError):
        feed(stream, header)
        stream.finish()
    assert stream.final_tokens == 0


def test_repeated_analysis_headers_discard_reasoning_before_final():
    stream = parser()
    values = analysis_header() + [(8, "private one")] + next_assistant()
    values += analysis_header() + [(9, "private two")] + next_assistant()
    values += final_header() + [(10, '{"reply":"Visible"}'), (RETURN, "")]
    assert feed(stream, values) == [10]
    stream.finish()
    assert stream.saw_analysis
    assert "private" not in repr(vars(stream))
    assert stream.header_size == 0


def test_analysis_does_not_accumulate_hidden_text():
    stream = parser()
    feed(stream, analysis_header())
    for _ in range(10000):
        assert not stream.feed(8, "Never retain this reasoning.")
    assert stream.header_size == 0
    assert "Never retain" not in repr(vars(stream))


@pytest.mark.parametrize("values", [
    [], final_header(), analysis_header() + [(8, "secret"), (RETURN, "")],
    [(CHANNEL, ""), (1, "final"), (RETURN, "")],
    [(CHANNEL, ""), (1, "commentary"), (MESSAGE, "")],
    [(CHANNEL, ""), (1, "final"), (CHANNEL, "")],
    analysis_header() + [(START, "")],
    final_header() + [(8, "answer"), (END, "")],
    [(CHANNEL, ""), (1, "f" * 129)],
])
def test_malformed_or_unfinished_reply_fails_without_repeating_hidden_text(values):
    stream = parser()
    with pytest.raises(harmony().HarmonyError) as caught:
        feed(stream, values)
        stream.finish()
    assert "secret" not in str(caught.value)


def test_other_eos_cannot_turn_analysis_into_success():
    module = harmony()
    stream = module.HarmonyParser(module.HarmonyTokens(eos=frozenset({200002, 199999})))
    feed(stream, analysis_header())
    with pytest.raises(module.HarmonyError):
        stream.feed(199999, "")


def test_token_ids_are_derived_and_checked_against_the_pinned_tokenizer():
    module = harmony()
    mapping = {"<|start|>": START, "<|end|>": END, "<|message|>": MESSAGE,
               "<|channel|>": CHANNEL, "<|return|>": RETURN, "<|constrain|>": CONSTRAIN}

    class Tokenizer:
        eos_token_ids = {RETURN}

        def encode(self, value, *, add_special_tokens):
            assert add_special_tokens is False
            return [mapping[value]]

    assert module.HarmonyTokens.from_tokenizer(Tokenizer()).message == 200008
    mapping["<|message|>"] = 200009
    with pytest.raises(module.HarmonyError, match="tokenizer"):
        module.HarmonyTokens.from_tokenizer(Tokenizer())


def test_schema_gate_starts_at_final_body_and_never_scans_historical_headers():
    module = harmony()
    seen = []

    def grammar(tokens, logits):
        seen.append(list(tokens))
        return "constrained"

    # Historical final headers in the prompt must not activate this turn's grammar.
    prompt = [START, 20, CHANNEL, 21, MESSAGE, 22, RETURN, START, 20]
    text = {1: "analysis", 2: "assistant", 3: "fi", 4: "nal", 9: "secret"}
    gate = module.FinalOnlyLogitsProcessor(module.HarmonyTokens(), grammar,
                                          lambda token: text.get(token, ""), skip=len(prompt))
    tokens = list(prompt)
    assert gate(tokens, "raw") == "raw"
    generated = [CHANNEL, 1, MESSAGE, 9, END, START, 2, CHANNEL, 3, 4, MESSAGE]
    for token in generated:
        tokens.append(token)
        output = gate(tokens, "raw")
    assert output == "constrained"
    assert seen == [[]]
    tokens.append(30)
    gate(tokens, "raw")
    tokens.append(31)
    gate(tokens, "raw")
    assert seen == [[], [30], [30, 31]]
    assert gate.parser is not parser()
    assert "secret" not in repr(vars(gate.parser))


HEADER_WORDS = {"analysis": 1, "assistant": 2, "final": 3, "json": 30, "JSON": 31, " ": 32}
HEADER_SPECIALS = {"<|start|>": START, "<|end|>": END, "<|channel|>": CHANNEL,
                   "<|message|>": MESSAGE, "<|constrain|>": CONSTRAIN, "<|return|>": RETURN}


def encode_header(value):
    pieces = re.findall(r"<\|[a-z]+\|>|analysis|assistant|final|json|JSON| ", value)
    assert "".join(pieces) == value
    return [HEADER_SPECIALS.get(piece, HEADER_WORDS.get(piece)) for piece in pieces]


def constrained_gate(*, grammar=True, skip=0):
    module = harmony()
    masks, grammar_calls = [], []

    def mask(logits, allowed):
        masks.append(set(allowed))
        return {token: logits[token] for token in allowed}

    def processor(tokens, logits):
        grammar_calls.append(list(tokens))
        return "JSON grammar"

    decode = lambda token: next((word for word, value in HEADER_WORDS.items() if value == token), "")
    gate = module.FinalOnlyLogitsProcessor(module.HarmonyTokens(), processor if grammar else None,
                                          decode, skip=skip, encode=encode_header, mask=mask)
    return gate, masks, grammar_calls


def test_header_mask_preserves_channel_choices_and_leaves_analysis_body_unconstrained():
    gate, masks, grammar_calls = constrained_gate()
    scores = {START: 8., END: 7., CHANNEL: 5., MESSAGE: 6., CONSTRAIN: 4.,
              1: 1.25, 2: 2., 3: 9., 10: 99., 20: 100., 30: 2., 31: 3., 32: 4.}
    assert gate([], scores) == {CHANNEL: 5., CONSTRAIN: 4., 32: 4.}
    assert gate([CHANNEL], scores) == {1: 1.25, 3: 9.}
    gate([CHANNEL, 1], scores)
    before = len(masks)
    assert gate([CHANNEL, 1, MESSAGE], scores) is scores
    assert gate([CHANNEL, 1, MESSAGE, 10], scores) is scores
    assert len(masks) == before
    assert grammar_calls == []
    tokens = [CHANNEL, 1, MESSAGE, 10, END]
    assert gate(tokens, scores) == {START: 8.}
    tokens.append(START)
    assert gate(tokens, scores) == {2: 2.}
    tokens.append(2)
    assert gate(tokens, scores) == {CHANNEL: 5., CONSTRAIN: 4., 32: 4.}
    tokens.append(CHANNEL)
    assert gate(tokens, scores) == {1: 1.25, 3: 9.}
    tokens.append(3)
    gate(tokens, scores)
    assert grammar_calls == []
    before = len(masks)
    tokens.append(MESSAGE)
    assert gate(tokens, scores) == "JSON grammar"
    tokens.append(20)
    assert gate(tokens, scores) == "JSON grammar"
    assert grammar_calls == [[], [20]]
    assert len(masks) == before


def test_header_mask_disallows_unbounded_metadata_after_a_valid_final_channel():
    gate, masks, _ = constrained_gate()
    scores = {START: 1., CHANNEL: 1., MESSAGE: 1., CONSTRAIN: 1.,
              1: 1., 2: 1., 3: 1., 30: 1., 31: 1., 32: 1., 99: 1000.}
    gate([CHANNEL], scores)
    output = gate([CHANNEL, 3], scores)
    assert MESSAGE in output and CONSTRAIN in output
    assert 99 not in output
    with pytest.raises(harmony().HarmonyError):
        gate([CHANNEL, 3, 99], scores)


@pytest.mark.parametrize("header", [
    [CHANNEL, 3, 32, CONSTRAIN, 31],
    [CONSTRAIN, 31, CHANNEL, 3],
    [32, CONSTRAIN, 32, 31, 32, CHANNEL, 3],
])
def test_header_mask_allows_documented_json_metadata_without_early_grammar_activation(header):
    gate, masks, grammar_calls = constrained_gate()
    scores = {START: 1., CHANNEL: 1., MESSAGE: 1., CONSTRAIN: 1.,
              1: 1., 2: 1., 3: 1., 30: 1., 31: 1., 32: 1.}
    tokens = []
    for token in header:
        tokens.append(token)
        gate(tokens, scores)
        assert grammar_calls == []
    tokens.append(MESSAGE)
    assert gate(tokens, scores) == "JSON grammar"
    assert grammar_calls == [[]]


def test_header_mask_excludes_historical_headers_and_supports_plain_final_answers():
    historical = [START, 2, CHANNEL, 3, MESSAGE, 20, RETURN, START, 2]
    gate, masks, grammar_calls = constrained_gate(grammar=False, skip=len(historical))
    scores = {START: 1., CHANNEL: 1., MESSAGE: 1., CONSTRAIN: 1.,
              1: 1., 2: 1., 3: 1., 30: 1., 31: 1., 32: 1.}
    assert gate(historical, scores) == {CHANNEL: 1., CONSTRAIN: 1., 32: 1.}
    tokens = historical + [CHANNEL, 3, MESSAGE]
    assert gate(tokens, scores) is scores
    assert gate(tokens + [20], scores) is scores
    assert grammar_calls == []
