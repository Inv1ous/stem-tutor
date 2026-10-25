"""Decoded local replies reject unsafe controls without guessing their intended text."""
import asyncio
import json

import pytest

from test_local_runtime import event, models, server
from tutor_app import ai
from tutor_app.local_ai import LocalAI
from tutor_app.local_reply import ReplyDecoder, ReplyError


# Exact affected excerpts from the 25 October MLX migration candidate, GPT low,
# negative-gradient repeat 0 and acceleration-unit-trap repeat 0 respectively.
CANDIDATE_REPLIES = [
    pytest.param("A slope of \x00dmi\x00bd6 means that as $x$ increases a little, $y$ falls", "",
                 id="candidate-nul-slope"),
    pytest.param("Velocity itself is measured in \x1b[m s\x1b^-1]. When you divide a velocity "
                 "(\x1b[m s\x1b^-1]) by time (\x1b[s]\x1b), the result is \x1b[m s\x1b^-2].",
                 "Because acceleration is how fast velocity changes, you divide velocity by time.",
                 id="candidate-esc-units"),
]


@pytest.mark.parametrize("reply,speech", CANDIDATE_REPLIES)
def test_candidate_controls_are_rejected_before_emission_at_every_wire_split(reply, speech):
    fields = {"speech": speech, "reply": reply} if speech else {"reply": reply}
    wire = json.dumps(fields)
    for boundary in range(len(wire) + 1):
        decoder = ReplyDecoder(speech=bool(speech))
        visible = []
        with pytest.raises(ReplyError):
            for chunk in (wire[:boundary], wire[boundary:]):
                visible.append(decoder.feed(chunk))
            decoder.finish()
        assert "\x00" not in "".join(visible) and "\x1b" not in "".join(visible)
        if speech:
            assert speech not in "".join(visible)
        with pytest.raises(ReplyError):
            decoder.finish()


@pytest.mark.parametrize("code", [*range(8), 11, *range(14, 32), *range(127, 160)])
@pytest.mark.parametrize("ascii_only", [False, True])
def test_reply_rejects_forbidden_c0_del_and_c1_from_both_json_character_paths(code, ascii_only):
    control = chr(code)
    decoder = ReplyDecoder()
    assert decoder.feed('{"reply":"Safe prefix ') == "Safe prefix "
    with pytest.raises(ReplyError):
        decoder.feed(json.dumps(control, ensure_ascii=ascii_only)[1:-1] + '"}')
        decoder.finish()


@pytest.mark.parametrize("reply", [
    "$\x0crac{1}{2}$", "$\x08eta$", "$\rho$", "$\theta$", "a\tb\r\nNext line.",
    '```json\n{"literal": "\\u001b", "other": "\\u0000"}\n```',
])
def test_decoder_preserves_recoverable_math_whitespace_and_printed_literal_escapes(reply):
    wire = json.dumps({"reply": reply})
    decoder = ReplyDecoder()
    assert "".join(decoder.feed(char) for char in wire) == reply
    assert decoder.finish() == (reply, "")


def test_controls_in_separate_speech_never_become_visual_reply_text():
    reply = r'Literal JSON: {"reply":"\u001b"}; code: `\u0000`.'
    speech = "Separate spoken source \x00 \x1b \x9b."
    wire = json.dumps({"speech": speech, "reply": reply})
    decoder = ReplyDecoder(speech=True)
    assert "".join(decoder.feed(char) for char in wire) == reply
    assert decoder.finish() == (reply, speech)


@pytest.mark.parametrize("reply,speech", CANDIDATE_REPLIES)
def test_rejected_candidate_reply_remains_failed_and_never_enters_history(models, monkeypatch, reply, speech):
    fields = {"speech": speech, "reply": reply} if speech else {"reply": reply}
    wire = json.dumps(fields)
    boundary = min(index for index in (wire.find(r"\u0000"), wire.find(r"\u001b")) if index >= 0)

    async def go():
        async with server(monkeypatch, [[event(wire[:boundary]), event(wire[boundary:], done=True)]],
                          raw_chat=True):
            client = LocalAI(ai.SYSTEM, speech=bool(speech))
            try:
                output = "".join([part async for part in client.stream("Explain the idea.",
                                                                     model="ollama:qwen3.8:27b")])
                assert not client.last.ok and not client._history
                assert "reply" in client.last.message.lower()
                assert "\x00" not in output + client.last.text
                assert "\x1b" not in output + client.last.text
                if speech:
                    assert speech not in output
            finally:
                await client.close()
    asyncio.run(go())
