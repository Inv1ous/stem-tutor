"""The local chat envelope streams its reply without changing literal student content."""
import json

import pytest


def decoder(*, speech=False):
    from tutor_app.local_reply import ReplyDecoder
    return ReplyDecoder(speech=speech)


@pytest.mark.parametrize("speech", [False, True])
def test_chat_schema_names_only_the_explicit_transport_fields(speech):
    from tutor_app.local_reply import chat_schema
    fields = {"reply": {"type": "string"}}
    if speech:
        fields["speech"] = {"type": "string"}
    assert chat_schema(speech) == {
        "type": "object", "properties": fields, "required": list(fields), "additionalProperties": False,
    }


def test_reply_starts_streaming_before_the_envelope_finishes():
    stream = decoder(speech=True)
    assert stream.feed('{"reply":"Velocity ') == "Velocity "
    assert stream.feed('has direction.","speech":"Private spoken ') == "has direction."
    assert stream.feed('version."}') == ""
    assert stream.finish() == ("Velocity has direction.", "Private spoken version.")


LITERAL_REPLY = (
    'Return this JSON: {"reply":"keep me", "speech":"literal data"}.\n\n'
    '```python\nvalue = {"reply": "x_1^2", "path": "C:\\\\temp"}\n```\n'
    'Escaped source: \\n \\u0041 \\frac{1}{2}; quote: "yes"; slash: /; tab:\t; CR:\r.\n'
    'Unicode: 香港 𝑥 🚀; literal marker: [[SPEECH]].'
)


@pytest.mark.parametrize("reply", [
    "", "Plain reply.", LITERAL_REPLY, 'A brace } and { inside a string.',
    'Backslashes: \\ and \\\\; an escaped quote: ".',
])
@pytest.mark.parametrize("speech_first", [False, True])
@pytest.mark.parametrize("ascii_only", [False, True])
def test_every_chunk_boundary_preserves_reply_literals_and_hides_speech(reply, speech_first, ascii_only):
    fields = {"speech": "Spoken version.", "reply": reply} if speech_first else {
        "reply": reply, "speech": "Spoken version.",
    }
    source = json.dumps(fields, ensure_ascii=ascii_only)
    for boundary in range(len(source) + 1):
        stream = decoder(speech=True)
        visible = stream.feed(source[:boundary]) + stream.feed(source[boundary:])
        assert visible == reply
        assert stream.finish() == (reply, "Spoken version.")


def test_one_character_chunks_hold_escapes_and_surrogate_pairs_until_complete():
    stream = decoder()
    assert stream.feed('{"reply":"') == ""
    assert stream.feed("\\") == ""
    assert stream.feed("uD83D") == ""
    assert stream.feed("\\uDE") == ""
    assert stream.feed("80") == "🚀"
    assert stream.feed('"}') == ""
    assert stream.finish() == ("🚀", "")
    source = json.dumps({"reply": LITERAL_REPLY}, ensure_ascii=True)
    stream = decoder()
    assert "".join(stream.feed(char) for char in source) == LITERAL_REPLY
    assert stream.finish() == (LITERAL_REPLY, "")


def test_escaped_transport_keys_and_json_whitespace_are_supported():
    stream = decoder(speech=True)
    assert stream.feed(' \t\r\n{ "spe\\u0065ch" : "Read me", "repl\\u0079" : "Show me" } \n') == "Show me"
    assert stream.finish() == ("Show me", "Read me")


INVALID_ENVELOPES = [
    "", "Plain text", '```json\n{"reply":"Hi"}\n```', 'prefix {"reply":"Hi"}',
    '[]', 'null', '"reply"', '{}', '{"speech":"only"}',
    '{"reply":null}', '{"reply":4}', '{"reply":true}', '{"reply":[]}', '{"reply":{}}',
    '{"reply":"Hi","extra":"ignored"}', '{"reply":"Hi","speech":"not enabled"}',
    '{"reply":"first","reply":"second"}', '{"reply":"first","repl\\u0079":"second"}',
    '{"reply":"Hi"} trailing', '{"reply":"Hi"}{"reply":"again"}',
    '{"reply":"Hi",}', '{"reply" "Hi"}', '{reply:"Hi"}', "{'reply':'Hi'}",
    '{"reply":"bad\\q"}', '{"reply":"bad\\u12xz"}', '{"reply":"raw\nnewline"}',
    '{"reply":"\\uD800"}', '{"reply":"\\uDC00"}', '{"reply":"\\uD800text"}',
    '{"reply":"\\uD800\\u0041"}', '{"reply":"\\uD800\\n"}', '{"reply":"\ud800"}',
    '{"reply":"Hi"//comment\n}', '{"reply":"Hi" /* comment */}',
]


@pytest.mark.parametrize("source", INVALID_ENVELOPES)
def test_invalid_or_ambiguous_transport_is_rejected_without_fallback(source):
    from tutor_app.local_reply import ReplyError
    for boundary in range(len(source) + 1):
        stream = decoder()
        with pytest.raises(ReplyError):
            stream.feed(source[:boundary])
            stream.feed(source[boundary:])
            stream.finish()


@pytest.mark.parametrize("source", [
    '{"reply":"Hi"}', '{"reply":"Hi","speech":null}', '{"reply":"Hi","speech":{}}',
    '{"reply":"Hi","speech":"first","speech":"second"}',
    '{"reply":"Hi","speech":"Spoken","thinking":"private"}',
])
def test_enabled_speech_is_required_string_and_never_admits_hidden_fields(source):
    from tutor_app.local_reply import ReplyError
    stream = decoder(speech=True)
    with pytest.raises(ReplyError):
        stream.feed(source)
        stream.finish()


def test_truncated_envelope_never_becomes_a_successful_reply():
    from tutor_app.local_reply import ReplyError
    source = json.dumps({"reply": 'Literal "quote" and 🚀.', "speech": "Read it."}, ensure_ascii=True)
    for end in range(len(source)):
        stream = decoder(speech=True)
        with pytest.raises(ReplyError):
            stream.feed(source[:end])
            stream.finish()


def test_chat_schema_is_independent_between_requests():
    from tutor_app.local_reply import chat_schema
    schema = chat_schema(True)
    schema["properties"]["reply"]["type"] = "object"
    schema["required"].append("unexpected")
    assert chat_schema(True)["properties"]["reply"] == {"type": "string"}
    assert chat_schema(True)["required"] == ["reply", "speech"]


def test_an_unfinished_reply_cannot_grow_the_transport_buffer_without_limit():
    from tutor_app.local_reply import ReplyError
    stream = decoder()
    with pytest.raises(ReplyError):
        stream.feed('{"reply":"' + "x" * (4 * 1024 * 1024))
