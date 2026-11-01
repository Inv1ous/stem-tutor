"""Native local document transport, with real loopback HTTP and no model calls."""
import asyncio
import json

import pytest

from test_local_runtime import event, models, server
from tutor_app.local_ai import LocalAI

MODEL = "ollama:gemma4:26b-a4b-it-qat"
DOCUMENT = {"blocks": [{"kind": "heading", "text": "Forces"},
                       {"kind": "bullet", "text": "A force changes momentum."}]}
MARKDOWN = "**Forces**\n\n- A force changes momentum."


def test_document_schema_streaming_and_validated_wire_history(models, monkeypatch):
    async def go():
        wire = json.dumps(DOCUMENT)
        # The second event completes one block but leaves the second incomplete.
        boundary = wire.index('},') + 1
        replies = [[event(wire[:8]), event(wire[8:boundary]), event(wire[boundary:], done=True)]]
        async with server(monkeypatch, replies, raw_chat=True, record_preloads=True) as (requests, _):
            client = LocalAI("Tutor brief", document=True)
            chunks = [chunk async for chunk in client.stream("Explain forces.", model=MODEL, think=True)]
            assert chunks == ["**Forces**", "\n\n- A force changes momentum."]
            assert client.last.ok and client.last.text == MARKDOWN
            assert client.last.speech == ""
            assert requests[0]["messages"] == []
            payload = requests[1]
            assert "blocks" in payload["format"]["properties"]
            assert "reply" not in payload["format"]["properties"]
            assert payload["think"] is True
            assert payload["messages"][-1]["content"] == "Explain forces."
            assert "reply string" not in payload["messages"][0]["content"]
            assert json.loads(client._history[(MODEL, True, False)][-1]["content"]) == DOCUMENT
            await client.close()
    asyncio.run(go())


def test_document_speech_does_not_use_legacy_marker(models, monkeypatch):
    async def go():
        doc = {"speech": "A force changes momentum.", "blocks": [{"kind": "paragraph", "text": "Force."}]}
        async with server(monkeypatch, [[event(json.dumps(doc), done=True)]], raw_chat=True) as (requests, _):
            client = LocalAI("Tutor brief", speech=True, document=True)
            output = "".join([p async for p in client.stream("Define force.", model=MODEL)])
            assert output == "Force." and client.last.text == output
            assert client.last.ok and client.last.speech == doc["speech"]
            assert set(requests[0]["format"]["required"]) == {"blocks", "speech"}
            assert "[[SPEECH]]" not in repr(client._history)
            assert json.loads(client._history[(MODEL, False, True)][-1]["content"]) == doc
            await client.close()
    asyncio.run(go())


@pytest.mark.parametrize("wire,reason", [
    ('{"blocks":[]}', "stop"),
    ('{"blocks":[{"kind":"paragraph","text":"Partial"}', "stop"),
    (json.dumps(DOCUMENT), "length"),
])
def test_invalid_and_length_stopped_documents_keep_partial_visible_but_never_history(models, monkeypatch, wire, reason):
    async def go():
        async with server(monkeypatch, [[event(wire, done=True, done_reason=reason)]], raw_chat=True):
            client = LocalAI("Tutor brief", document=True)
            _ = [p async for p in client.stream("Question", model=MODEL)]
            assert not client.last.ok and not client._history
            if reason == "length":
                assert "context" in client.last.message.lower() or "truncat" in client.last.message.lower()
            await client.close()
    asyncio.run(go())


def test_document_cancel_after_one_complete_block_has_no_history(models, monkeypatch):
    async def go():
        async with server(monkeypatch, [[event('{"blocks":[{"kind":"paragraph","text":"Partial."}'), "wait"]],
                          raw_chat=True):
            client = LocalAI("Tutor brief", document=True)
            stream = client.stream("Question", model=MODEL)
            assert await anext(stream) == "Partial."
            await stream.aclose()
            assert not client.last.ok and not client._history
            await client.close()
    asyncio.run(go())


def test_native_mlx_document_format_and_effort_are_preserved(monkeypatch):
    from tutor_app import local_models
    monkeypatch.setattr(local_models, "available_models", lambda: ("mlx:gpt-oss:20b",))
    requests = []
    class Worker:
        _closed = False
        async def events(self, payload, timeout):
            requests.append(payload)
            if not payload["messages"]:
                yield {"done": True, "done_reason": "load"}
            else:
                yield event(json.dumps(DOCUMENT), done=True)
        async def close(self):
            self._closed = True
    async def go():
        client = LocalAI("Tutor brief", document=True)
        client._mlx = Worker()
        async def prepare(deadline):
            pass
        monkeypatch.setattr(client, "_prepare_mlx", prepare)
        out = "".join([p async for p in client.stream("Forces?", model="mlx:gpt-oss:20b", think="medium")])
        assert client.last.ok and out == MARKDOWN
        assert requests[0]["messages"] == [] and requests[1]["think"] == "medium"
        assert "blocks" in requests[1]["format"]["properties"]
        assert client.last.performance["engine_seconds"] is None
        await client.close()
    asyncio.run(go())


def test_document_retry_preloads_each_attempt_and_preserves_native_thinking(models, monkeypatch):
    async def go():
        exhausted = {"message": {"thinking": "Private reasoning"}, "done": True, "done_reason": "length"}
        async with server(monkeypatch, [[exhausted], [event(json.dumps(DOCUMENT), done=True)]],
                          raw_chat=True, record_preloads=True) as (requests, _):
            client = LocalAI("Tutor brief", document=True)
            output = "".join([p async for p in client.stream("Forces?", model=MODEL, think=True)])
            assert client.last.ok and output == MARKDOWN
            assert [bool(request["messages"]) for request in requests] == [False, True, False, True]
            assert requests[1]["think"] is True and requests[3]["think"] is True
            assert client.last.performance["preload_count"] == 2
            assert "Private reasoning" not in repr(client._history)
            assert len(client._history[(MODEL, True, False)]) == 2
            await client.close()
    asyncio.run(go())


def test_document_histories_isolate_models_effort_and_speech(models, monkeypatch):
    async def go():
        doc = json.dumps(DOCUMENT)
        speech_doc = json.dumps({**DOCUMENT, "speech": "Forces."})
        async with server(monkeypatch, [[event(wire, done=True)] for wire in (doc, doc, doc, speech_doc, doc)],
                          raw_chat=True) as (requests, _):
            client = LocalAI("Tutor brief", document=True)
            settings = [(MODEL, False, False), (MODEL, True, False),
                        ("ollama:qwen3.8:27b", "low", False), (MODEL, False, True), (MODEL, False, False)]
            for model, effort, speech in settings:
                client.speech = speech
                _ = [p async for p in client.stream("Question", model=model, think=effort)]
                assert client.last.ok
            assert [len(request["messages"]) for request in requests] == [2, 2, 2, 2, 4]
            assert len(client._history) == 4
            assert json.loads(requests[-1]["messages"][-2]["content"]) == DOCUMENT
            await client.close()
    asyncio.run(go())


def test_document_failure_keeps_prior_valid_turn_and_current_request_out_of_history(models, monkeypatch):
    async def go():
        async with server(monkeypatch, [[event(json.dumps(DOCUMENT), done=True)],
                                       [event('{"blocks":[{"kind":"paragraph","text":"Partial."}', done=True)]],
                          raw_chat=True):
            client = LocalAI("Tutor brief", document=True)
            _ = [p async for p in client.stream("Valid question", model=MODEL)]
            before = list(client._history[(MODEL, False, False)])
            parts = [p async for p in client.stream("Failed question", model=MODEL)]
            assert parts == ["Partial."] and not client.last.ok
            assert client.last.text == "Partial."
            assert client._history[(MODEL, False, False)] == before
            await client.close()
    asyncio.run(go())


def test_document_failure_names_format_without_misdiagnosing_runtime_or_ssd(models, monkeypatch):
    async def go():
        wire = '{"blocks":[{"kind":"unsupported","text":"Bad layout"}]}'
        async with server(monkeypatch, [[event(wire, done=True)]], raw_chat=True):
            client = LocalAI("Tutor brief", document=True)
            assert not [piece async for piece in client.stream("Explain", model=MODEL)]
            assert not client.last.ok and not client._history
            assert "structured" in client.last.message.lower()
            assert "Check Ollama" not in client.last.message
            await client.close()
    asyncio.run(go())
