"""Local models stay on the SSD and preserve the tutor's reply and cancellation contracts."""
import asyncio
import base64
import json
import socket
import time
from contextlib import asynccontextmanager

import pytest

from tutor_app import local_ai, local_models


MODEL = "ollama:qwen3.5:9b"


@pytest.fixture
def models(tmp_path, monkeypatch):
    root = tmp_path / "LocalAI"
    library = root / "manifests/registry.ollama.ai/library"
    for name, tag in (("qwen3.5", "9b"), ("gemma4", "26b-a4b-it-qat"), ("qwen3.8", "27b")):
        path = library / name / tag
        path.parent.mkdir(parents=True)
        path.write_text('{"schemaVersion":2}')
    monkeypatch.setattr(local_models, "ROOT", root)
    return root


def event(text="", done=False, **extra):
    return {"model": "qwen3.5:9b", "message": {"role": "assistant", "content": text}, "done": done, **extra}


@asynccontextmanager
async def server(monkeypatch, replies, *, chunked=True, paths=None):
    requests, closed, tasks = [], asyncio.Event(), set()

    async def handle(reader, writer):
        task = asyncio.current_task()
        tasks.add(task)
        try:
            header = await reader.readuntil(b"\r\n\r\n")
            if paths is not None:
                paths.append(header.split(b"\r\n", 1)[0].decode())
            headers = dict(line.split(b": ", 1) for line in header.split(b"\r\n")[1:] if b": " in line)
            payload = json.loads(await reader.readexactly(int(headers[b"Content-Length"])))
            requests.append(payload)
            reply = replies.pop(0)
            if callable(reply):
                reply = reply(payload)
            if isinstance(reply, int):
                body = b'{"error":"model is not installed"}'
                writer.write(f"HTTP/1.1 {reply} Error\r\nContent-Length: {len(body)}\r\n\r\n".encode() + body)
            else:
                writer.write(b"HTTP/1.1 200 OK\r\nContent-Type: application/x-ndjson\r\n" +
                             (b"Transfer-Encoding: chunked\r\n\r\n" if chunked else b"Connection: close\r\n\r\n"))
                for item in reply:
                    if item == "wait":
                        await reader.read()
                        closed.set()
                        return
                    body = (json.dumps(item) + "\n").encode()
                    # Split JSON across HTTP chunks: NDJSON and HTTP boundaries differ.
                    for part in (body[:7], body[7:]):
                        writer.write(f"{len(part):x}\r\n".encode() + part + b"\r\n" if chunked else part)
                        await writer.drain()
                        await asyncio.sleep(0)
                if chunked:
                    writer.write(b"0\r\n\r\n")
            await writer.drain()
        finally:
            writer.close()
            await writer.wait_closed()
            tasks.discard(task)

    srv = await asyncio.start_server(handle, "127.0.0.1", 0)
    monkeypatch.setattr(local_ai, "PORT", srv.sockets[0].getsockname()[1])
    try:
        yield requests, closed
    finally:
        srv.close()
        await srv.wait_closed()
        for task in tasks:
            task.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)


def test_discovery_tracks_ssd_insertion_removal_and_individual_models(models):
    assert local_models.available_models() == (MODEL, "ollama:gemma4:26b-a4b-it-qat", "ollama:qwen3.8:27b")
    (models / "manifests/registry.ollama.ai/library/qwen3.5/9b").unlink()
    assert MODEL not in local_models.available_models()
    models.rename(models.with_name("unplugged"))
    assert local_models.available_models() == ()


def test_stream_speech_and_performance_stay_outside_answer(models, monkeypatch):
    async def go():
        replies = [[event("Think about force. [[SPE"), event("ECH]] Think about force."),
                    event(done=True, total_duration=4_000_000_000, load_duration=1_000_000_000,
                          prompt_eval_count=20, prompt_eval_cached_count=9, prompt_eval_duration=500_000_000,
                          eval_count=10, eval_duration=2_000_000_000)]]
        async with server(monkeypatch, replies) as (requests, _):
            client = local_ai.LocalAI("Tutor brief", speech=True)
            chunks = [chunk async for chunk in client.stream("help", model=MODEL, think=True)]
            result = client.last
            await client.close()
            assert "".join(chunks) == "Think about force. "
            assert result.text == "Think about force." and result.speech == "Think about force."
            assert result.performance["tokens_per_second"] == 5
            assert result.performance["total_seconds"] == 4
            assert result.performance["input_tokens"] == 20 and result.performance["output_tokens"] == 10
            assert result.performance["cached_input_tokens"] == 9
            assert result.performance["first_token_seconds"] >= 0
            assert result.usage == {}
            assert requests[0]["model"] == "qwen3.5:9b" and requests[0]["think"] is True
            assert "Tutor brief" in requests[0]["messages"][0]["content"]
            assert "[[SPEECH]]" in requests[0]["messages"][0]["content"]
    asyncio.run(go())


def test_history_images_and_reset_do_not_cross_models_or_thinking(models, monkeypatch, tmp_path):
    image = tmp_path / "diagram.png"
    image.write_bytes(b"image")

    async def go():
        async with server(monkeypatch, [[event("reply", done=True)]] * 5) as (requests, _):
            client = local_ai.LocalAI("brief")
            for prompt, think in (("first", False), ("second", False), ("thinking", True), ("third", False)):
                async for _ in client.stream(prompt, image=image, model=MODEL, think=think):
                    pass
            await client.reset()
            async for _ in client.stream("fresh", image=image, model=MODEL):
                pass
            await client.close()
            assert requests[0]["messages"][-1]["images"] == [base64.b64encode(b"image").decode()]
            assert len(requests[1]["messages"]) == 4 and "images" not in requests[1]["messages"][-1]
            assert len(requests[2]["messages"]) == 2 and "images" in requests[2]["messages"][-1]
            assert len(requests[3]["messages"]) == 6
            assert len(requests[4]["messages"]) == 2 and "images" in requests[4]["messages"][-1]
    asyncio.run(go())


def test_image_edits_and_returning_to_an_earlier_image_send_current_exact_bytes(models, monkeypatch, tmp_path):
    image, other = tmp_path / "diagram.png", tmp_path / "other.png"
    image.write_bytes(b"original image")
    other.write_bytes(b"original image")

    async def go():
        async with server(monkeypatch, [[event("reply", done=True)]] * 6) as (requests, _):
            client = local_ai.LocalAI("brief")
            for path, contents in ((image, b"original image"), (image, b"original image"),
                                   (image, b"edited image"), (image, b"original image"),
                                   (other, b"original image"), (image, b"original image")):
                path.write_bytes(contents)
                _ = [part async for part in client.stream("describe the current image", image=path, model=MODEL)]
                assert client.last.ok
            await client.close()
            original = [base64.b64encode(b"original image").decode()]
            edited = [base64.b64encode(b"edited image").decode()]
            assert requests[0]["messages"][-1]["images"] == original
            assert "images" not in requests[1]["messages"][-1]
            assert requests[2]["messages"][-1].get("images") == edited
            assert all(requests[index]["messages"][-1].get("images") == original for index in (3, 4, 5))
            assert requests[2]["messages"][1]["images"] == original  # earlier turns retain their actual pixels
    asyncio.run(go())


@pytest.mark.parametrize("problem", ["missing", "empty", "unreadable", "unsupported"])
def test_native_image_failure_never_becomes_a_successful_text_only_request(models, monkeypatch, tmp_path, problem):
    image = tmp_path / ("diagram.svg" if problem == "unsupported" else "diagram.png")
    if problem != "missing":
        image.write_bytes(b"" if problem == "empty" else b"pixels")
    if problem == "unreadable":
        read = type(image).read_bytes
        def unreadable(path):
            if path == image:
                raise OSError("unreadable image")
            return read(path)
        monkeypatch.setattr(type(image), "read_bytes", unreadable)

    async def go():
        async with server(monkeypatch, [[event("text-only fallback", done=True)]]) as (requests, _):
            client = local_ai.LocalAI("brief")
            assert [part async for part in client.stream("read this diagram", image=image, model=MODEL)] == []
            assert not client.last.ok and "image" in client.last.message.lower()
            assert requests == [] and client._history == {}
            await client.close()
    asyncio.run(go())


@pytest.mark.parametrize("operation", ["one_shot", "describe_image"])
def test_empty_image_bytes_never_reach_local_inference(models, monkeypatch, operation):
    async def go():
        async with server(monkeypatch, [[event('{"diagram":"fallback"}', done=True)]]) as (requests, _):
            client = local_ai.LocalAI("brief")
            if operation == "describe_image":
                data, result = await client.describe_image(b"", "read", schema={}, model=MODEL, timeout=1,
                                                            system="transcribe")
            else:
                data, result = await client.one_shot("read", model=MODEL, image=b"")
            assert data is None and not result.ok and "image" in result.message.lower()
            assert requests == []
            await client.close()
    asyncio.run(go())


@pytest.mark.parametrize("operation", ["stream", "one_shot"])
def test_local_performance_includes_waiting_for_model_queue_but_preserves_engine_counters(models, monkeypatch, operation):
    async def go():
        reply = event('{"feedback":"Good."}', done=True, total_duration=2_000_000,
                      eval_count=5, eval_duration=1_000_000)
        async with server(monkeypatch, [[reply]]) as _:
            client = local_ai.LocalAI("brief")
            await client._lock.acquire()
            async def invoke():
                if operation == "stream":
                    _ = [part async for part in client.stream("help", model=MODEL)]
                    return client.last
                return (await client.one_shot("mark", model=MODEL))[1]
            started = time.monotonic()
            task = asyncio.create_task(invoke())
            await asyncio.sleep(.03)
            client._lock.release()
            result = await task
            wall = time.monotonic() - started
            assert result.ok and result.performance["first_token_seconds"] >= .02
            assert result.performance["total_seconds"] >= wall - .005
            assert result.performance["engine_seconds"] == .002
            assert result.performance["tokens_per_second"] == 5000
            await client.close()
    asyncio.run(go())


def test_one_shot_uses_schema_system_and_speech_without_conversation_history(models, monkeypatch):
    schema = {"type": "object", "properties": {"feedback": {"type": "string"}}, "required": ["feedback"]}

    async def go():
        async with server(monkeypatch, [[event('{"feedback":"Good.","speech":"Good."}', done=True)]],
                          chunked=False) as (requests, _):
            client = local_ai.LocalAI("brief", speech=True)
            data, result = await client.one_shot("mark", schema=schema, system="examiner", model=MODEL, speech=True)
            await client.close()
            assert result.ok and data["feedback"] == "Good." and result.speech == "Good."
            assert requests[0]["format"]["properties"]["speech"] == {"type": "string"}
            assert requests[0]["messages"][0]["content"] == "examiner"
            assert len(requests[0]["messages"]) == 2
    asyncio.run(go())


def test_describe_image_sends_exact_bytes_without_history_speech_or_last_mutation(models, monkeypatch):
    schema = {"type": "object", "properties": {"diagram": {"type": "string"}}, "required": ["diagram"]}

    async def go():
        async with server(monkeypatch, [[event("earlier", done=True)],
                                        [event('{"diagram":"axis t / s; labels A B C D"}', done=True)],
                                        [event("later", done=True)]]) as (requests, _):
            client = local_ai.LocalAI("private tutor brief", speech=True)
            _ = [part async for part in client.stream("private earlier question", model=MODEL)]
            previous, history = client.last, list(client._history.values())[0][:]
            data, result = await client.describe_image(b"\x89PNG exact bytes", "read the entire image", schema=schema,
                                                        model=MODEL, timeout=2, system="transcribe visible labels")
            assert result.ok and data["diagram"] == "axis t / s; labels A B C D" and not result.speech
            assert client.last is previous and list(client._history.values())[0] == history
            assert requests[1]["messages"] == [{"role": "system", "content": "transcribe visible labels"},
                {"role": "user", "content": requests[1]["messages"][1]["content"],
                 "images": [base64.b64encode(b"\x89PNG exact bytes").decode()]}]
            assert "read the entire image" in requests[1]["messages"][1]["content"]
            assert "private" not in str(requests[1]) and "speech" not in requests[1]["format"]["properties"]
            assert requests[1]["think"] is False
            _ = [part async for part in client.stream("next", model=MODEL)]
            assert len(requests[2]["messages"]) == 4 and "images" not in requests[2]["messages"][-1]
            await client.close()
    asyncio.run(go())


def test_optional_image_keeps_legacy_one_shot_override_compatible(models, monkeypatch):
    from tutor_app.ai import Result

    async def go():
        client = local_ai.LocalAI("brief")
        async def old_override(prompt, schema, model, timeout, system, speech, think):
            return {"feedback": "Good."}, Result()
        monkeypatch.setattr(client, "_one_shot", old_override)
        data, result = await client.one_shot("mark", model=MODEL)
        assert result.ok and data == {"feedback": "Good."}
        await client.close()
    asyncio.run(go())


def install_model(root, model):
    path = root / "manifests/registry.ollama.ai/library" / model.removeprefix("ollama:").replace(":", "/")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text('{"schemaVersion":2}')


@pytest.mark.parametrize("model", ["ollama:phi4-mini:3.8b", "ollama:ministral-3:3b"])
def test_non_thinking_models_omit_think_from_stream_and_structured_payload(models, monkeypatch, model):
    install_model(models, model)

    async def go():
        async with server(monkeypatch, [[event("reply", done=True)],
                                        [event('{"feedback":"Good."}', done=True)]]) as (requests, _):
            client = local_ai.LocalAI("brief")
            assert [part async for part in client.stream("help", model=model, think=False)] == ["reply"]
            data, result = await client.one_shot("mark", model=model, think=False)
            assert data == {"feedback": "Good."} and result.ok
            assert all("think" not in request and request["options"] == {"num_ctx": 8192} for request in requests)
            await client.close()
    asyncio.run(go())


@pytest.mark.parametrize("model", ["ollama:phi4-mini:3.8b", "ollama:ministral-3:3b"])
@pytest.mark.parametrize("operation", ["stream", "one_shot"])
def test_unsupported_thinking_is_actionable_and_never_silently_disabled(models, monkeypatch, model, operation):
    install_model(models, model)

    async def go():
        async with server(monkeypatch, []) as (requests, _):
            client = local_ai.LocalAI("brief")
            if operation == "stream":
                assert [part async for part in client.stream("help", model=model, think=True)] == []
                result = client.last
            else:
                data, result = await client.one_shot("mark", model=model, think=True)
                assert data is None
            assert not result.ok and "Think first" in result.message and requests == []
            await client.close()
    asyncio.run(go())


def test_describe_image_uses_the_inference_queue_deadline(models, monkeypatch):
    async def go():
        async with server(monkeypatch, []) as (requests, _):
            client = local_ai.LocalAI("brief")
            await client._lock.acquire()
            try:
                data, result = await client.describe_image(b"image", "read", schema={}, model=MODEL, timeout=.01,
                                                            system="transcribe")
                assert data is None and not result.ok and "long" in result.message and requests == []
            finally:
                client._lock.release()
                await client.close()
    asyncio.run(go())


def test_describe_image_never_sends_an_image_to_a_text_only_model(models, monkeypatch):
    model = "ollama:phi4-mini:3.8b"
    install_model(models, model)

    async def go():
        async with server(monkeypatch, []) as (requests, _):
            client = local_ai.LocalAI("brief")
            data, result = await client.describe_image(b"image", "read", schema={}, model=model, timeout=.1,
                                                        system="transcribe")
            assert data is None and not result.ok and "vision" in result.message and requests == []
            await client.close()
    asyncio.run(go())


def test_gpt_oss_uses_named_effort_and_preserves_low_during_context_retry(models, monkeypatch):
    model = "ollama:gpt-oss:20b"
    install_model(models, model)

    async def go():
        exhausted = {"message": {"thinking": "private", "content": ""}, "done": True, "done_reason": "length"}
        async with server(monkeypatch, [[event(done=True)], [exhausted],
                                        [event('{"feedback":"Good."}', done=True)],
                                        [event("reply", done=True)]]) as (requests, _):
            client = local_ai.LocalAI("brief")
            assert (await client.warm(model)).ok
            data, result = await client.one_shot("mark", model=model, think=False)
            assert data == {"feedback": "Good."} and result.ok
            assert [part async for part in client.stream("help", model=model, think=True)] == ["reply"]
            assert "think" not in requests[0] and requests[0]["messages"] == []
            assert [request["think"] for request in requests[1:]] == ["low", "low", "high"]
            assert [request["options"]["num_ctx"] for request in requests[1:3]] == [8192, 16384]
            await client.close()
    asyncio.run(go())


@pytest.mark.parametrize("think", [False, True])
@pytest.mark.parametrize("model", ["ollama:lfm2.5:8b", "ollama:deepseek-r1:8b", "ollama:deepseek-r1:14b"])
def test_reasoning_models_always_request_parsed_thinking_for_stream_and_json(models, monkeypatch, think, model):
    install_model(models, model)

    async def go():
        hidden = {"message": {"thinking": "private reasoning", "content": ""}, "done": False}
        async with server(monkeypatch, [[hidden, event("final reply", done=True)],
                                        [hidden, event('{"feedback":"Good."}', done=True)]]) as (requests, _):
            client = local_ai.LocalAI("brief")
            assert [part async for part in client.stream("help", model=model, think=think)] == ["final reply"]
            assert client.last.ok and "private" not in client.last.text
            data, result = await client.one_shot("mark", model=model, think=think)
            assert data == {"feedback": "Good."} and result.ok and "private" not in result.text
            assert [request["think"] for request in requests] == [True, True]
            await client.close()
    asyncio.run(go())


def test_incomplete_json_is_an_error(models, monkeypatch):
    async def go():
        async with server(monkeypatch, [[event('{"wrong":"field"}', done=True)]]) as _:
            client = local_ai.LocalAI("brief")
            data, result = await client.one_shot("mark", schema={"properties": {"feedback": {"type": "string"}}}, model=MODEL)
            await client.close()
            assert data is None and not result.ok and "JSON" in result.message
    asyncio.run(go())


def test_cancel_closes_socket_and_drops_partial_history(models, monkeypatch):
    async def go():
        async with server(monkeypatch, [[event("partial"), "wait"], [event("fresh", done=True)]]) as (requests, closed):
            client = local_ai.LocalAI("brief")
            stream = client.stream("cancel me", model=MODEL)
            assert await anext(stream) == "partial"
            await stream.aclose()
            await asyncio.wait_for(closed.wait(), 1)
            assert [x async for x in client.stream("next", model=MODEL)] == ["fresh"]
            await client.close()
            assert len(requests[1]["messages"]) == 2
    asyncio.run(go())


def test_failed_http_response_keeps_history_clean(models, monkeypatch):
    async def go():
        async with server(monkeypatch, [404, [event("ok", done=True)]]) as (requests, _):
            client = local_ai.LocalAI("brief")
            assert [x async for x in client.stream("missing", model=MODEL)] == []
            assert not client.last.ok and "installed" in client.last.message
            assert [x async for x in client.stream("next", model=MODEL)] == ["ok"]
            await client.close()
            assert len(requests[1]["messages"]) == 2
    asyncio.run(go())


def test_removed_ssd_never_sends_request(models, monkeypatch):
    models.rename(models.with_name("unplugged"))

    async def go():
        async with server(monkeypatch, []) as (requests, _):
            client = local_ai.LocalAI("brief")
            assert [x async for x in client.stream("help", model=MODEL)] == []
            assert not client.last.ok and "SSD" in client.last.message and requests == []
            await client.close()
    asyncio.run(go())


def test_timeout_closes_request(models, monkeypatch):
    async def go():
        async with server(monkeypatch, [["wait"]]) as (_, closed):
            client = local_ai.LocalAI("brief")
            data, result = await client.one_shot("help", model=MODEL, timeout=0.05)
            assert data is None and not result.ok and "long" in result.message
            await asyncio.wait_for(closed.wait(), 1)
            await client.close()
    asyncio.run(go())


def test_cancelling_a_later_reply_does_not_reuse_previous_result(models, monkeypatch):
    async def go():
        async with server(monkeypatch, [[event("first", done=True)], [event("partial"), "wait"]]) as (_, closed):
            client = local_ai.LocalAI("brief")
            assert [x async for x in client.stream("first", model=MODEL)] == ["first"]
            stream = client.stream("cancel", model=MODEL)
            assert await anext(stream) == "partial"
            await stream.aclose()
            await asyncio.wait_for(closed.wait(), 1)
            assert not client.last.ok and client.last.text != "first"
            await client.close()
    asyncio.run(go())


def test_reset_closes_an_active_reply_and_forgets_history(models, monkeypatch):
    async def go():
        async with server(monkeypatch, [[event("partial"), "wait"], [event("new", done=True)]]) as (requests, closed):
            client = local_ai.LocalAI("brief")
            stream = client.stream("reset", model=MODEL)
            assert await anext(stream) == "partial"
            await client.reset()
            assert [x async for x in stream] == []
            await asyncio.wait_for(closed.wait(), 1)
            assert not client.last.ok
            assert [x async for x in client.stream("new", model=MODEL)] == ["new"]
            assert len(requests[1]["messages"]) == 2
            await client.close()
    asyncio.run(go())


@pytest.mark.parametrize("web,setting,expected_cloud", [(False, "0", "1"), (True, None, "0"), (True, "1", "1")])
def test_owned_service_uses_ssd_loopback_and_stops_on_close(models, monkeypatch, tmp_path, web, setting, expected_cloud):
    log = tmp_path / "service.json"
    binary = tmp_path / "ollama"
    binary.write_text('''#!/usr/bin/env python3
import asyncio, json, os, sys
from pathlib import Path
Path(os.environ["FAKE_OLLAMA_LOG"]).write_text(json.dumps({"args": sys.argv[1:], "models": os.environ["OLLAMA_MODELS"],
    "host": os.environ["OLLAMA_HOST"], "cloud": os.environ["OLLAMA_NO_CLOUD"],
    "loaded": os.environ.get("OLLAMA_MAX_LOADED_MODELS"), "parallel": os.environ.get("OLLAMA_NUM_PARALLEL")}))
async def handle(reader, writer):
    header = await reader.readuntil(b"\\r\\n\\r\\n")
    size = int(next(x.split(b":", 1)[1] for x in header.split(b"\\r\\n") if x.startswith(b"Content-Length:")))
    await reader.readexactly(size)
    body = b'{"message":{"content":"local"},"done":true}\\n'
    writer.write(f"HTTP/1.1 200 OK\\r\\nContent-Length: {len(body)}\\r\\n\\r\\n".encode() + body)
    await writer.drain()
    writer.close()
async def main():
    host, port = os.environ["OLLAMA_HOST"].split(":")
    server = await asyncio.start_server(handle, host, int(port))
    await server.serve_forever()
asyncio.run(main())
''')
    binary.chmod(0o755)
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        port = sock.getsockname()[1]
    monkeypatch.setattr(local_ai, "PORT", port)
    monkeypatch.setattr(local_ai.shutil, "which", lambda _: str(binary))
    monkeypatch.setenv("FAKE_OLLAMA_LOG", str(log))
    if setting is None:
        monkeypatch.delenv("OLLAMA_NO_CLOUD", raising=False)
    else:
        monkeypatch.setenv("OLLAMA_NO_CLOUD", setting)

    async def go():
        client = local_ai.LocalAI("brief")
        client.web_enabled = web
        assert [x async for x in client.stream("start", model=MODEL)] == ["local"]
        process = client._owned
        assert process is not None and process.returncode is None
        await client.close()
        assert process.returncode is not None
    asyncio.run(go())
    assert json.loads(log.read_text()) == {"args": ["serve"], "models": str(models),
                                           "host": f"127.0.0.1:{port}", "cloud": expected_cloud, "loaded": "1", "parallel": "1"}


def test_close_preserves_existing_service(models, monkeypatch):
    async def go():
        async with server(monkeypatch, [[event("one", done=True)], [event("two", done=True)]]) as _:
            first = local_ai.LocalAI("brief")
            assert [x async for x in first.stream("one", model=MODEL)] == ["one"]
            await first.close()
            second = local_ai.LocalAI("brief")
            assert [x async for x in second.stream("two", model=MODEL)] == ["two"]
            await second.close()
    asyncio.run(go())


@pytest.mark.parametrize("reply", [
    [["not an event"]],
    [{"message": 42, "done": True}],
    [event(42, done=True)],
    [event("text", done=True, total_duration="invalid")],
    [event("unfinished")],
    [event("", done=True)],
    [event("text", done=True, prompt_eval_cached_count="invalid")],
])
def test_unreadable_or_unfinished_local_reply_returns_error(models, monkeypatch, reply):
    async def go():
        async with server(monkeypatch, [reply]) as _:
            client = local_ai.LocalAI("brief")
            _ = [x async for x in client.stream("help", model=MODEL)]
            assert not client.last.ok and client.last.message
            await client.close()
    asyncio.run(go())


def test_thinking_text_is_not_part_of_answer_and_zero_timings_are_safe(models, monkeypatch):
    async def go():
        async with server(monkeypatch, [[{"message": {"thinking": "private reasoning"}, "done": False},
                                        event("visible", done=True, eval_count=0, eval_duration=0)]]) as _:
            client = local_ai.LocalAI("brief")
            assert [x async for x in client.stream("help", model=MODEL, think=True)] == ["visible"]
            assert client.last.text == "visible" and client.last.performance["tokens_per_second"] == 0
            await client.close()
    asyncio.run(go())


def test_close_during_service_start_does_not_leave_owned_process(models, monkeypatch, tmp_path):
    binary = tmp_path / "ollama"
    binary.write_text("#!/usr/bin/env python3\nimport time\ntime.sleep(30)\n")
    binary.chmod(0o755)
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        port = sock.getsockname()[1]
    monkeypatch.setattr(local_ai, "PORT", port)
    monkeypatch.setattr(local_ai.shutil, "which", lambda _: str(binary))
    launch = asyncio.create_subprocess_exec

    async def go():
        started, release, processes = asyncio.Event(), asyncio.Event(), []

        async def delayed_launch(*args, **kwargs):
            process = await launch(*args, **kwargs)
            processes.append(process)
            started.set()
            await release.wait()
            return process

        monkeypatch.setattr(local_ai.asyncio, "create_subprocess_exec", delayed_launch)
        client = local_ai.LocalAI("brief")

        async def reply():
            return [x async for x in client.stream("start", model=MODEL)]

        task = asyncio.create_task(reply())
        try:
            await asyncio.wait_for(started.wait(), 1)
            closing = asyncio.create_task(client.close())
            await asyncio.sleep(0)
            release.set()
            await asyncio.wait_for(closing, 1)
            assert await asyncio.wait_for(task, 1) == []
            assert processes[0].returncode is not None
        finally:
            for process in processes:
                if process.returncode is None:
                    process.kill()
                    await process.wait()
    asyncio.run(go())


def test_one_shot_deadline_includes_waiting_for_service_start_lock(models, monkeypatch):
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        port = sock.getsockname()[1]
    monkeypatch.setattr(local_ai, "PORT", port)

    async def go():
        client = local_ai.LocalAI("brief")
        await client._service_lock.acquire()
        task = asyncio.create_task(client.one_shot("help", model=MODEL, timeout=0.02))
        try:
            done, _ = await asyncio.wait({task}, timeout=0.08)
            assert task in done, "The startup lock must not extend a request's deadline."
            data, result = task.result()
            assert data is None and not result.ok and "long" in result.message
        finally:
            client._service_lock.release()
            task.cancel()
            await asyncio.gather(task, return_exceptions=True)
            await client.close()
    asyncio.run(go())


def test_cancel_during_service_launch_keeps_process_owned_until_close(models, monkeypatch, tmp_path):
    binary = tmp_path / "ollama"
    binary.write_text("#!/usr/bin/env python3\nimport time\ntime.sleep(30)\n")
    binary.chmod(0o755)
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        port = sock.getsockname()[1]
    monkeypatch.setattr(local_ai, "PORT", port)
    monkeypatch.setattr(local_ai.shutil, "which", lambda _: str(binary))
    launch = asyncio.create_subprocess_exec

    async def go():
        started, release, processes = asyncio.Event(), asyncio.Event(), []

        async def delayed_launch(*args, **kwargs):
            process = await launch(*args, **kwargs)
            processes.append(process)
            started.set()
            await release.wait()
            return process

        monkeypatch.setattr(local_ai.asyncio, "create_subprocess_exec", delayed_launch)
        client = local_ai.LocalAI("brief")
        task = asyncio.create_task(client.one_shot("start", model=MODEL))
        try:
            await asyncio.wait_for(started.wait(), 1)
            task.cancel()
            with pytest.raises(asyncio.CancelledError):
                await task
            closing = asyncio.create_task(client.close())
            await asyncio.sleep(0)
            release.set()
            await asyncio.wait_for(closing, 1)
            assert processes[0].returncode is not None
        finally:
            for process in processes:
                if process.returncode is None:
                    process.kill()
                    await process.wait()
    asyncio.run(go())


@pytest.mark.parametrize("model,keep_alive", [(MODEL, "30m"), ("ollama:gemma4:26b-a4b-it-qat", "15m"),
                                             ("ollama:qwen3.8:27b", "10m")])
def test_preload_preserves_reply_history_and_sets_model_keepalive(models, monkeypatch, model, keep_alive):
    async def go():
        async with server(monkeypatch, [[event(done=True)], [event("reply", done=True)],
                                        [event('{"feedback":"Good."}', done=True)]]) as (requests, _):
            client = local_ai.LocalAI("brief")
            original = client.last
            result = await client.warm(model)
            assert result.ok and result.text == "" and result.performance == {}
            assert client.last is original
            expected = {"model": model.removeprefix("ollama:"), "messages": [],
                        "stream": False, "keep_alive": keep_alive}
            if model == "ollama:gemma4:26b-a4b-it-qat":
                expected["options"] = {"num_ctx": 8192}
            assert requests[0] == expected
            assert [x async for x in client.stream("help", model=model)] == ["reply"]
            data, result = await client.one_shot("mark", model=model)
            assert data == {"feedback": "Good."} and result.ok
            assert len(requests[1]["messages"]) == 2
            assert all(request["keep_alive"] == keep_alive for request in requests)
            expected_options = {"num_ctx": 8192} if model == "ollama:gemma4:26b-a4b-it-qat" else None
            assert all(request.get("options") == expected_options for request in requests)
            await client.close()
    asyncio.run(go())


def test_one_shot_waits_for_stream_and_preload_uses_same_queue(models, monkeypatch):
    async def go():
        async with server(monkeypatch, [[event("reply"), event(done=True)],
                                        [event('{"feedback":"Good."}', done=True)],
                                        [event(done=True)]]) as (requests, _):
            client = local_ai.LocalAI("brief")
            stream = client.stream("help", model=MODEL)
            assert await anext(stream) == "reply"
            shot = asyncio.create_task(client.one_shot("mark", model=MODEL))
            warm = asyncio.create_task(client.warm(MODEL))
            await asyncio.sleep(0.02)
            assert len(requests) == 1 and not shot.done() and not warm.done()
            assert [x async for x in stream] == []
            data, result = await shot
            assert data == {"feedback": "Good."} and result.ok
            assert (await warm).ok
            assert requests[1]["messages"][-1]["content"] == "mark" and requests[2]["messages"] == []
            await client.close()
    asyncio.run(go())


@pytest.mark.parametrize("operation", ["one_shot", "warm"])
def test_request_deadline_includes_waiting_for_inference_queue(models, monkeypatch, operation):
    async def go():
        async with server(monkeypatch, []) as (requests, _):
            client = local_ai.LocalAI("brief")
            await client._lock.acquire()
            call = client.one_shot("help", model=MODEL, timeout=0.02) if operation == "one_shot" else client.warm(MODEL, timeout=0.02)
            task = asyncio.create_task(call)
            try:
                done, _ = await asyncio.wait({task}, timeout=0.08)
                assert task in done, "The inference queue must not extend a request's deadline."
                result = task.result()[1] if operation == "one_shot" else task.result()
                assert not result.ok and "long" in result.message and requests == []
                assert client._lock.locked()
            finally:
                client._lock.release()
                task.cancel()
                await asyncio.gather(task, return_exceptions=True)
                await client.close()
    asyncio.run(go())


def test_cancel_queued_one_shot_does_not_unlock_an_active_stream(models, monkeypatch):
    async def go():
        async with server(monkeypatch, [[event("reply"), event(done=True)],
                                        [event('{"feedback":"Good."}', done=True)]]) as (requests, _):
            client = local_ai.LocalAI("brief")
            stream = client.stream("help", model=MODEL)
            assert await anext(stream) == "reply"
            task = asyncio.create_task(client.one_shot("cancel", model=MODEL))
            await asyncio.sleep(0.01)
            task.cancel()
            with pytest.raises(asyncio.CancelledError):
                await task
            assert client._lock.locked() and len(requests) == 1
            assert [x async for x in stream] == []
            data, result = await client.one_shot("mark", model=MODEL)
            assert data == {"feedback": "Good."} and result.ok
            await client.close()
    asyncio.run(go())


@pytest.mark.parametrize("operation", ["stream", "one_shot", "describe_image", "warm"])
def test_reset_revokes_previously_queued_work_without_launch_or_result_mutation(models, monkeypatch, operation):
    from tutor_app.ai import Result

    async def go():
        async with server(monkeypatch, [[event('{"feedback":"fresh"}', done=True)]]) as (requests, _):
            client = local_ai.LocalAI("brief")
            previous = client.last = Result(text="active result")
            await client._lock.acquire()
            async def invoke():
                if operation == "stream":
                    return [part async for part in client.stream("old", model=MODEL)]
                if operation == "one_shot":
                    return await client.one_shot("old", model=MODEL)
                if operation == "describe_image":
                    return await client.describe_image(b"old image", "old", schema={}, model=MODEL, timeout=1,
                                                        system="transcribe")
                return await client.warm(MODEL)
            queued = asyncio.create_task(invoke())
            for _ in range(5):
                await asyncio.sleep(0)
            await client.reset()
            client._lock.release()
            try:
                with pytest.raises(asyncio.CancelledError):
                    await queued
                assert requests == [] and client.last is previous
                assert client._active_model is None and not client._lock.locked()
                data, result = await client.one_shot("new", model=MODEL)
                assert data == {"feedback": "fresh"} and result.ok
            finally:
                queued.cancel()
                await asyncio.gather(queued, return_exceptions=True)
                await client.close()
    asyncio.run(go())


def test_cancelled_shutdown_kills_and_reaps_owned_service():
    async def go():
        class Process:
            returncode = None
            reaped = False

            def __init__(self):
                self.waiting, self.exited = asyncio.Event(), asyncio.Event()

            def terminate(self):
                pass  # the service does not exit on its graceful signal

            def kill(self):
                self.returncode = -9
                self.exited.set()

            async def wait(self):
                self.waiting.set()
                await self.exited.wait()
                self.reaped = True
                return self.returncode

        process = Process()
        client = local_ai.LocalAI("brief")
        client._owned = process
        closing = asyncio.create_task(client.close())
        await asyncio.wait_for(process.waiting.wait(), 1)
        closing.cancel()
        with pytest.raises(asyncio.CancelledError):
            await closing
        assert process.returncode == -9 and process.reaped
        assert client._owned is None
    asyncio.run(go())


def test_gemma_thinking_has_context_room_for_the_final_answer(models, monkeypatch):
    model = "ollama:gemma4:26b-a4b-it-qat"

    def answer(payload):
        if payload.get("options", {}).get("num_ctx", 4096) < 8192:
            return [{"message": {"thinking": "Private model reasoning", "content": ""}, "done": True,
                     "done_reason": "length", "prompt_eval_count": 3082, "eval_count": 1014}]
        return [event("Velocity has magnitude and direction.", done=True, eval_count=20)]

    async def go():
        async with server(monkeypatch, [answer]) as (requests, _):
            client = local_ai.LocalAI("brief")
            assert "".join([x async for x in client.stream("Explain velocity", model=model, think=True)]) == "Velocity has magnitude and direction."
            assert client.last.ok and requests[0]["think"] is True
            assert requests[0]["options"] == {"num_ctx": 8192}
            await client.close()
    asyncio.run(go())


@pytest.mark.parametrize("operation", ["stream", "one_shot"])
def test_reasoning_only_context_exhaustion_retries_with_more_room_without_leaking(models, monkeypatch, operation):
    model = "ollama:gemma4:26b-a4b-it-qat"
    exhausted = {"message": {"thinking": "Private model reasoning", "content": ""}, "done": True,
                 "done_reason": "length", "prompt_eval_count": 7000, "eval_count": 1192,
                 "total_duration": 5_000_000_000, "load_duration": 1_000_000_000,
                 "eval_duration": 4_000_000_000, "prompt_eval_cached_count": 100}
    text = '{"feedback":"Good."}' if operation == "one_shot" else "A useful hint."

    async def go():
        async with server(monkeypatch, [[exhausted], [event(text, done=True, eval_count=10,
                                                        total_duration=2_000_000_000, eval_duration=1_000_000_000,
                                                        prompt_eval_count=7000, prompt_eval_cached_count=200)]]) as (requests, _):
            client = local_ai.LocalAI("brief")
            if operation == "stream":
                assert "".join([x async for x in client.stream("Help", model=model, think=True)]) == text
                result = client.last
            else:
                data, result = await client.one_shot("Mark", model=model, think=True)
                assert data == {"feedback": "Good."}
            assert result.ok and "Private model reasoning" not in result.text
            assert result.performance["total_seconds"] == 7
            assert result.performance["load_seconds"] == 1
            assert result.performance["generation_seconds"] == 5
            assert result.performance["input_tokens"] == 14000 and result.performance["output_tokens"] == 1202
            assert result.performance["cached_input_tokens"] == 300 and result.performance["retry_count"] == 1
            assert [request["options"]["num_ctx"] for request in requests] == [8192, 16384]
            assert requests[0]["messages"] == requests[1]["messages"] and all(request["think"] is True for request in requests)
            await client.close()
    asyncio.run(go())


def test_context_retry_is_bounded_and_does_not_commit_reasoning(models, monkeypatch):
    model = "ollama:gemma4:26b-a4b-it-qat"
    exhausted = {"message": {"thinking": "Private model reasoning", "content": ""}, "done": True, "done_reason": "length"}

    async def go():
        async with server(monkeypatch, [[exhausted], [exhausted], [event("New answer", done=True)]]) as (requests, _):
            client = local_ai.LocalAI("brief")
            assert [x async for x in client.stream("Help", model=model, think=True)] == []
            assert not client.last.ok and "context" in client.last.message
            assert [x async for x in client.stream("Next", model=model, think=True)] == ["New answer"]
            assert len(requests) == 3 and len(requests[-1]["messages"]) == 2
            await client.close()
    asyncio.run(go())


def test_progress_reports_hidden_thinking_without_exposing_it(models, monkeypatch):
    async def go():
        async with server(monkeypatch, [[{"message": {"thinking": "Private model reasoning", "content": ""}, "done": False}, "wait"],
                                        [event("Visible"), event(done=True, eval_count=12)]]) as _:
            client = local_ai.LocalAI("brief")

            async def collect():
                return [x async for x in client.stream("Help", model=MODEL, think=True)]

            task = asyncio.create_task(collect())
            for _ in range(100):
                if client.progress_for(MODEL).get("phase") == "thinking":
                    break
                await asyncio.sleep(0.005)
            progress = client.progress_for(MODEL)
            assert progress["phase"] == "thinking" and isinstance(progress["started"], float)
            assert "Private" not in str(progress) and "tokens" not in progress
            progress["phase"] = "wrong"
            assert client.progress_for(MODEL)["phase"] == "thinking"
            task.cancel()
            with pytest.raises(asyncio.CancelledError):
                await task
            assert client.progress_for(MODEL)["phase"] == "error"
            stream = client.stream("Next", model=MODEL)
            assert await anext(stream) == "Visible"
            assert client.progress_for(MODEL)["phase"] == "generating"
            assert [x async for x in stream] == []
            assert client.progress_for(MODEL)["phase"] == "done" and client.progress_for(MODEL)["tokens"] == 12
            await client.close()
    asyncio.run(go())


def test_progress_marks_a_different_model_waiting_in_queue(models, monkeypatch):
    other = "ollama:gemma4:26b-a4b-it-qat"

    async def go():
        async with server(monkeypatch, [[event("Visible"), event(done=True)], [event(done=True)]]) as _:
            client = local_ai.LocalAI("brief")
            stream = client.stream("Help", model=MODEL)
            assert await anext(stream) == "Visible"
            warm = asyncio.create_task(client.warm(other))
            await asyncio.sleep(0.01)
            assert client.progress_for(other)["phase"] == "queued"
            assert client.progress_for(MODEL)["phase"] == "generating"
            assert [x async for x in stream] == []
            assert (await warm).ok
            assert client.progress_for(other)["phase"] == "done"
            await client.close()
    asyncio.run(go())


def test_transport_supports_explicit_local_api_path(monkeypatch):
    async def go():
        paths = []
        async with server(monkeypatch, [[{"results": []}]], paths=paths) as _:
            client = local_ai.LocalAI("brief")
            result = [item async for item in client._events({"query": "synthetic query"}, 1,
                                                           path="/api/experimental/web_search")]
            assert result == [{"results": []}] and paths == ["POST /api/experimental/web_search HTTP/1.1"]
            assert client.progress_for(MODEL) == {}
            await client.close()
    asyncio.run(go())


@pytest.mark.parametrize("operation", ["stream", "one_shot", "warm"])
def test_same_model_queued_request_gets_fresh_progress_when_it_starts(models, monkeypatch, operation):
    async def go():
        client = local_ai.LocalAI("brief")
        preload_started, release = asyncio.Event(), asyncio.Event()
        calls = []

        async def events(payload, timeout):
            calls.append(payload)
            if len(calls) == 1:
                preload_started.set()
                await release.wait()
            yield event('{"feedback":"Good."}' if payload["messages"] else "", done=True)

        monkeypatch.setattr(client, "_events", events)
        preload = asyncio.create_task(client.warm(MODEL))
        await preload_started.wait()
        earlier = client.progress_for(MODEL)
        requested = time.monotonic()

        async def next_request():
            if operation == "stream":
                return [part async for part in client.stream("Help", model=MODEL)]
            if operation == "one_shot":
                return await client.one_shot("Mark", model=MODEL)
            return await client.warm(MODEL)

        next_ = asyncio.create_task(next_request())
        await asyncio.sleep(0.01)
        assert client.progress_for(MODEL) == earlier  # a queued request must not overwrite the active preload
        release.set()
        await preload
        await next_
        assert client.progress_for(MODEL)["started"] >= requested
        assert client.progress_for(MODEL)["phase"] == "done"
        await client.close()
    asyncio.run(go())
