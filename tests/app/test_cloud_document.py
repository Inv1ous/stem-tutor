"""Native structured cloud output never exposes protocol or a different final answer."""
import asyncio
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from tutor_app import ai
from tutor_app.codex_ai import CodexAI


DOCUMENT = {"blocks": [{"kind": "heading", "text": "Method"},
                       {"kind": "step", "text": "Use $x^2$."},
                       {"kind": "step", "text": "Check the units."}]}
EXPECTED = "**Method**\n\n1. Use $x^2$.\n\n2. Check the units."


def claude_events(document=DOCUMENT, *, speech=False, final=None):
    document = {**document, **({"speech": "Use x squared. Check the units."} if speech else {})}
    yield {"type": "stream_event", "event": {"type": "message_start", "message": {"id": "m1"}}}
    yield {"type": "stream_event", "event": {"type": "content_block_start", "index": 0,
           "content_block": {"type": "tool_use", "id": "tool1", "name": "StructuredOutput", "input": {}}}}
    yield {"type": "stream_event", "event": {"type": "content_block_delta", "index": 9,
           "delta": {"type": "text_delta", "text": "Protocol narration must stay hidden."}}}
    for part in json.dumps(document):
        yield {"type": "stream_event", "event": {"type": "content_block_delta", "index": 0,
               "delta": {"type": "input_json_delta", "partial_json": part}}}
    yield {"type": "assistant", "message": {"id": "m1", "content": [
        {"type": "tool_use", "id": "tool1", "name": "StructuredOutput", "input": document}]}}
    yield {"type": "stream_event", "event": {"type": "content_block_stop", "index": 0}}
    yield {"type": "result", "subtype": "success", "is_error": False,
           "structured_output": document if final is None else final, "result": "Protocol echo must stay hidden.",
           "usage": {"input_tokens": 3, "output_tokens": 17}}


async def read_claude(tmp_path, events, *, speech=False):
    client = ai.Claude(tmp_path, model="sonnet", document=True, speech=speech)
    reader = asyncio.StreamReader()
    for event in events:
        reader.feed_data((json.dumps(event) + "\n").encode())
    reader.feed_eof()
    parts = []
    chunks = [chunk async for chunk in client._read_document(SimpleNamespace(stdout=reader), parts)]
    return client, chunks


@pytest.mark.parametrize("speech", [False, True])
def test_claude_document_deltas_match_native_final_and_count_actual_usage(tmp_path, speech):
    client, chunks = asyncio.run(read_claude(tmp_path, claude_events(speech=speech), speech=speech))
    assert "".join(chunks) == EXPECTED
    assert client.last.ok and client.last.text == EXPECTED
    assert client.last.speech == ("Use x squared. Check the units." if speech else "")
    assert client.session.replies == 1 and client.session.output_tokens == 17
    assert "Protocol" not in "".join(chunks)


def test_claude_document_rejects_a_final_that_disagrees_with_emitted_blocks(tmp_path):
    from tutor_app.chat_output import DocumentError

    final = {"blocks": [{"kind": "paragraph", "text": "A different answer."}]}
    with pytest.raises(DocumentError):
        asyncio.run(read_claude(tmp_path, claude_events(final=final)))


def test_claude_document_rejects_reused_candidate_indices_across_messages(tmp_path):
    from tutor_app.chat_output import DocumentError

    events = list(claude_events())
    events[-1:-1] = [
        {"type": "stream_event", "event": {"type": "message_start", "message": {"id": "m2"}}},
        {"type": "stream_event", "event": {"type": "content_block_start", "index": 0,
         "content_block": {"type": "tool_use", "id": "tool2", "name": "StructuredOutput", "input": {}}}},
    ]
    with pytest.raises(DocumentError):
        asyncio.run(read_claude(tmp_path, events))


def test_claude_document_accepts_native_final_without_partial_events(tmp_path):
    client, chunks = asyncio.run(read_claude(tmp_path, [list(claude_events())[-1]]))
    assert client.last.ok and "".join(chunks) == EXPECTED


@pytest.mark.parametrize("speech", [False, True])
def test_codex_document_uses_native_schema_and_preserves_model_thinking_auth(tmp_path, monkeypatch, speech):
    from tutor_app.chat_output import document_schema

    log = tmp_path / "codex.jsonl"
    doc = {**DOCUMENT, **({"speech": "Use x squared."} if speech else {})}
    monkeypatch.setenv("FAKE_CODEX_LOG", str(log))
    monkeypatch.setenv("FAKE_CODEX_REPLY", json.dumps(doc))
    monkeypatch.setenv("FAKE_CODEX_MODE", "ok")

    async def go():
        client = CodexAI(ai.SYSTEM, speech=speech, binary=str(Path(__file__).with_name("fake_codex.py")),
                         document=True)
        chunks = [chunk async for chunk in client.stream("Show the method", model="codex:gpt-6.1-sol", think=True)]
        assert client.last.ok and client.last.text == EXPECTED and "".join(chunks) == EXPECTED
        history = next(iter(client._history.values()))
        assert json.loads(history[-1]["content"]) == doc
        await client.close()
    asyncio.run(go())
    record = json.loads(log.read_text().splitlines()[0])
    assert record["schema"] == document_schema(speech)
    assert record["args"][record["args"].index("--model") + 1] == "gpt-6.1-sol"
    assert 'model_reasoning_effort="high"' in record["args"]
    assert 'forced_login_method="chatgpt"' in record["args"]
    assert "[[SPEECH]]" not in record["instructions"]
    assert not record["api_key_present"]


def test_shared_exam_brief_scales_to_the_task_instead_of_a_blanket_word_cap():
    assert "under 120 words" not in ai.SYSTEM
    assert "No headings" not in ai.SYSTEM
    assert "mark points" in ai.SYSTEM and "definitions" in ai.SYSTEM
    assert "OPEN" in ai.SYSTEM


def test_codex_document_unavailable_is_actionable_without_leaking_protocol(tmp_path):
    async def go():
        client = CodexAI(ai.SYSTEM, binary="/missing/codex", document=True)
        chunks = [chunk async for chunk in client.stream("Explain", model="codex:gpt-6.1-sol")]
        assert not chunks and not client.last.ok and client.last.status == "off"
        await client.close()
    asyncio.run(go())


@pytest.mark.parametrize("speech", [False, True])
def test_native_claude_document_subprocess_uses_schema_and_preserves_conversation(tmp_path, monkeypatch, speech):
    log = tmp_path / "claude.jsonl"
    monkeypatch.setenv("FAKE_CLAUDE_LOG", str(log))
    monkeypatch.setenv("FAKE_CLAUDE_MODE", "speech" if speech else "ok")

    async def go():
        client = ai.Claude(tmp_path, model="sonnet", binary=str(Path(__file__).with_name("fake_claude.py")),
                           document=True, speech=speech)
        for turn in (1, 2):
            chunks = [chunk async for chunk in client.stream("Use the product rule", think=False)]
            assert client.last.ok and "".join(chunks) == client.last.text
            assert client.last.text.startswith(f"Reply {turn}:")
            assert ("x squared" in client.last.speech) == speech
        await client.close()
    asyncio.run(go())
    args = json.loads(log.read_text().splitlines()[0])
    assert len(log.read_text().splitlines()) == 1
    assert args[args.index("--model") + 1] == "sonnet"
    assert "alwaysThinkingEnabled" in args[args.index("--settings") + 1]
    assert not json.loads(args[args.index("--settings") + 1])["alwaysThinkingEnabled"]
    schema = json.loads(args[args.index("--json-schema") + 1])
    assert ("speech" in schema["properties"]) == speech
    assert args[args.index("--tools") + 1] == ""
    assert "[[SPEECH]]" not in args[args.index("--system-prompt") + 1]


def test_claude_native_final_compares_the_same_scoped_math_repair_as_streaming(tmp_path):
    document = {"blocks": [{"kind": "equation", "text": "\x0crac{1}{3}"}]}
    client, chunks = asyncio.run(read_claude(tmp_path, claude_events(document)))
    assert client.last.ok
    assert "".join(chunks) == "$$\n\\frac{1}{3}\n$$"


@pytest.mark.parametrize("reason", ["max_tokens", "model_context_window_exceeded"])
@pytest.mark.parametrize("location", ["message_delta", "assistant", "result"])
def test_claude_rejects_explicit_truncation_even_after_a_complete_document(tmp_path, reason, location):
    from tutor_app.chat_output import DocumentError

    async def go():
        client = ai.Claude(tmp_path, model="sonnet", document=True)
        events = list(claude_events())
        if location == "message_delta":
            events.insert(-1, {"type": "stream_event", "event": {"type": "message_delta",
                           "delta": {"stop_reason": reason}}})
        elif location == "assistant":
            next(e for e in events if e["type"] == "assistant")["message"]["stop_reason"] = reason
        else:
            events[-1]["stop_reason"] = reason
        reader = asyncio.StreamReader()
        reader.feed_data(b"".join((json.dumps(e) + "\n").encode() for e in events))
        reader.feed_eof()
        with pytest.raises(DocumentError, match="limit"):
            _ = [part async for part in client._read_document(SimpleNamespace(stdout=reader), [])]
        assert client.session.replies == 1 and client.session.output_tokens == 17
    asyncio.run(go())


def test_claude_truncation_is_failed_current_result_and_starts_a_fresh_conversation(tmp_path, monkeypatch):
    monkeypatch.setenv("FAKE_CLAUDE_STOP_REASON", "max_tokens")

    async def go():
        client = ai.Claude(tmp_path, model="sonnet", document=True,
                           binary=str(Path(__file__).with_name("fake_claude.py")))
        client.wanted = lambda: False
        try:
            chunks = [piece async for piece in client.stream("Truncated answer")]
            assert not client.last.ok and client.last.status == "error"
            assert "limit" in client.last.message and "incomplete" in client.last.message
            assert client.last.text == "".join(chunks) and not client.last.speech
            assert client.session.replies == 1 and not client.procs
            monkeypatch.delenv("FAKE_CLAUDE_STOP_REASON")
            assert (await client.reply("Fresh answer")).text == "Reply 1: Fresh answer"
            assert client.last.ok and client.session.replies == 2
        finally:
            await client.close()
    asyncio.run(go())


def test_codex_document_validation_failure_names_structure_and_retains_no_bad_history(tmp_path, monkeypatch):
    monkeypatch.setenv("FAKE_CODEX_LOG", str(tmp_path / "codex.jsonl"))
    monkeypatch.setenv("FAKE_CODEX_REPLY", json.dumps({"blocks": [{"kind": "wrong", "text": "bad"}]}))
    async def go():
        client = CodexAI(ai.SYSTEM, binary=str(Path(__file__).with_name("fake_codex.py")), document=True)
        assert not [part async for part in client.stream("Explain", model="codex:gpt-6.1-sol")]
        assert not client.last.ok and not client._history
        assert "structured" in client.last.message.lower() and "sign-in" not in client.last.message
        await client.close()
    asyncio.run(go())


@pytest.mark.parametrize("prior_success", [False, True])
def test_claude_document_cancel_after_first_block_keeps_only_current_incomplete_text(tmp_path, monkeypatch,
                                                                                  prior_success):
    monkeypatch.setenv("FAKE_CLAUDE_MODE", "ok")

    async def go():
        client = ai.Claude(tmp_path, model="sonnet", document=True,
                           binary=str(Path(__file__).with_name("fake_claude.py")))
        client.wanted = lambda: False
        try:
            if prior_success:
                assert (await client.reply("Earlier successful answer")).ok
            stream = client.stream("New incomplete answer")
            partial = await anext(stream)
            process = client.proc
            await stream.aclose()
            assert not client.last.ok
            assert client.last.status == "error" and client.last.message
            assert client.last.text == partial == f"Reply {2 if prior_success else 1}: New incomplete answer"
            assert not client.last.speech and not client.last.usage
            assert not client.procs and process.returncode is not None
            assert client.session.replies == int(prior_success)
            assert (await client.reply("Fresh answer")).text == "Reply 1: Fresh answer"
        finally:
            await client.close()

    asyncio.run(go())


@pytest.mark.parametrize("prior_success", [False, True])
def test_claude_document_cancel_before_first_block_replaces_previous_result(tmp_path, monkeypatch, prior_success):
    monkeypatch.setenv("FAKE_CLAUDE_MODE", "ok")

    async def go():
        client = ai.Claude(tmp_path, model="sonnet", document=True,
                           binary=str(Path(__file__).with_name("fake_claude.py")))
        client.wanted = lambda: False
        try:
            if prior_success:
                assert (await client.reply("Earlier successful answer")).ok
            entered = asyncio.Event()
            original = client._read_document

            async def paused_reader(proc, parts):
                entered.set()
                await asyncio.Event().wait()
                async for piece in original(proc, parts):
                    yield piece

            monkeypatch.setattr(client, "_read_document", paused_reader)
            stream = client.stream("New incomplete answer")
            pending = asyncio.create_task(anext(stream))
            await asyncio.wait_for(entered.wait(), 2)
            process = client.proc
            pending.cancel()
            with pytest.raises(asyncio.CancelledError):
                await pending
            await stream.aclose()
            assert not client.last.ok
            assert client.last.status == "error" and client.last.message
            assert client.last.text == "" and not client.last.speech and not client.last.usage
            assert not client.procs and process.returncode is not None
            assert client.session.replies == int(prior_success)
        finally:
            await client.close()

    asyncio.run(go())


def test_cancelling_queued_claude_document_caller_preserves_owned_result(tmp_path, monkeypatch):
    monkeypatch.setenv("FAKE_CLAUDE_MODE", "ok")

    async def go():
        client = ai.Claude(tmp_path, model="sonnet", document=True,
                           binary=str(Path(__file__).with_name("fake_claude.py")))
        client.wanted = lambda: False
        active, queued = client.stream("Owned answer"), client.stream("Queued answer")
        try:
            partial = await anext(active)
            owned_result, process = client.last, client.proc
            started = asyncio.Event()

            async def wait_for_turn():
                started.set()
                return await anext(queued)

            pending = asyncio.create_task(wait_for_turn())
            await started.wait()
            pending.cancel()
            with pytest.raises(asyncio.CancelledError):
                await pending
            await queued.aclose()
            assert client.last is owned_result and client.proc is process
            assert process.returncode is None
            assert partial + "".join([part async for part in active]) == "Reply 1: Owned answer"
            assert client.last.ok and client.last.text == "Reply 1: Owned answer"
            assert client.session.replies == 1
        finally:
            await active.aclose()
            await client.close()

    asyncio.run(go())


@pytest.mark.parametrize("mode, message", [("login", "claude auth login"), ("limit", "10:30pm")])
def test_claude_document_cleanup_preserves_actionable_provider_error(tmp_path, monkeypatch, mode, message):
    monkeypatch.setenv("FAKE_CLAUDE_MODE", mode)

    async def go():
        client = ai.Claude(tmp_path, model="sonnet", document=True,
                           binary=str(Path(__file__).with_name("fake_claude.py")))
        client.wanted = lambda: False
        try:
            assert not [part async for part in client.stream("Explain")]
            assert not client.last.ok and client.last.status == mode
            assert message in client.last.message
            assert not client.last.text and not client.procs
            assert client.session.replies == 0
        finally:
            await client.close()

    asyncio.run(go())


@pytest.mark.parametrize("failure, message", [(asyncio.TimeoutError, "too long"), (ValueError, "structured")])
def test_claude_document_cleanup_preserves_current_partial_and_reader_error(tmp_path, monkeypatch, failure, message):
    monkeypatch.setenv("FAKE_CLAUDE_MODE", "ok")

    async def go():
        client = ai.Claude(tmp_path, model="sonnet", document=True,
                           binary=str(Path(__file__).with_name("fake_claude.py")))
        client.wanted = lambda: False
        original = client._read_document

        async def interrupted_reader(proc, parts):
            reader = original(proc, parts)
            try:
                yield await anext(reader)
                raise failure("Interrupted native response")
            finally:
                await reader.aclose()

        monkeypatch.setattr(client, "_read_document", interrupted_reader)
        try:
            chunks = [part async for part in client.stream("Current partial answer")]
            assert not client.last.ok and client.last.status == "error"
            assert message in client.last.message
            assert client.last.text == "".join(chunks) == "Reply 1: Current partial answer"
            assert not client.procs and client.session.replies == 0
        finally:
            await client.close()

    asyncio.run(go())
