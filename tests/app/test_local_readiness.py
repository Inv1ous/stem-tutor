"""Every local generation is preceded by an acknowledged matching load under the same queue/deadline."""
import asyncio
import json
import time
from contextlib import asynccontextmanager

import pytest

from tutor_app import local_ai, local_models


@asynccontextmanager
async def readiness_server(monkeypatch, respond):
    requests, tasks = [], set()
    async def handle(reader, writer):
        task = asyncio.current_task()
        tasks.add(task)
        try:
            header = await reader.readuntil(b"\r\n\r\n")
            headers = dict(line.split(b": ", 1) for line in header.split(b"\r\n")[1:] if b": " in line)
            payload = json.loads(await reader.readexactly(int(headers[b"Content-Length"])))
            requests.append(payload)
            events = await respond(payload)
            body = b"".join((json.dumps(event) + "\n").encode() for event in events)
            writer.write(f"HTTP/1.1 200 OK\r\nContent-Length: {len(body)}\r\n\r\n".encode() + body)
            await writer.drain()
        except (asyncio.IncompleteReadError, ConnectionResetError):
            pass  # a guarded/cancelled client may close a connection before sending a request
        finally:
            writer.close()
            await writer.wait_closed()
            tasks.discard(task)
    server = await asyncio.start_server(handle, "127.0.0.1", 0)
    monkeypatch.setattr(local_ai, "PORT", server.sockets[0].getsockname()[1])
    try:
        yield requests
    finally:
        server.close()
        await server.wait_closed()
        for task in tasks:
            task.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)


@pytest.fixture(autouse=True)
def installed(monkeypatch):
    monkeypatch.setattr(local_models, "available_models", lambda: tuple(local_models.LOCAL_MODELS))


def loaded():
    return [{"done": True, "done_reason": "load"}]


# This fixture exercises Ollama's HTTP readiness protocol; the private MLX
# transport has its own identity and mandatory-preload cases in test_mlx_routing.
@pytest.mark.parametrize("model", [model for model in local_models.LOCAL_MODELS if model.startswith("ollama:")])
@pytest.mark.parametrize("operation", ["stream", "json"])
def test_every_supported_model_loads_before_each_generation(monkeypatch, model, operation):
    async def go():
        async def respond(payload):
            if payload["messages"] == []:
                return loaded()
            content = json.dumps({"reply": '{"answer":7}'}) if operation == "stream" else '{"answer":7}'
            return [{"message": {"content": content}, "done": True, "eval_count": 3}]
        async with readiness_server(monkeypatch, respond) as requests:
            client = local_ai.LocalAI("Private tutor brief")
            try:
                for _ in range(2):
                    if operation == "stream":
                        assert "".join([p async for p in client.stream("Private question", model=model)]) == '{"answer":7}'
                        result = client.last
                    else:
                        data, result = await client.one_shot("Private question", model=model,
                                                schema={"type": "object", "required": ["answer"]})
                        assert data == {"answer": 7}
                    assert result.ok
                    assert result.performance["preload_count"] == 1
                    assert result.performance["preload_seconds"] >= 0
                assert len(requests) == 4
                for preflight, generation in (requests[:2], requests[2:]):
                    assert preflight["messages"] == [] and preflight["stream"] is False
                    assert preflight["model"] == generation["model"] == model.removeprefix("ollama:")
                    assert preflight.get("options") == generation.get("options")
                    assert preflight["keep_alive"] == generation["keep_alive"]
                    assert set(preflight) <= {"model", "messages", "stream", "options", "keep_alive"}
            finally:
                await client.close()
    asyncio.run(go())


@pytest.mark.parametrize("ack", [[], [{"done": False}], [{"done": True}],
                                  [{"done": True, "done_reason": "stop"}], [{"error": "load failed"}],
                                  [{"done": "yes", "done_reason": "load"}],
                                  [{"done": True, "done_reason": "load", "message": {"content": "wrong reply"}}]])
def test_missing_or_failed_load_ack_never_sends_prompt(monkeypatch, ack):
    async def go():
        async def respond(payload):
            return ack
        async with readiness_server(monkeypatch, respond) as requests:
            client = local_ai.LocalAI("brief")
            data, result = await client.one_shot("Secret answer", model="ollama:qwen3.5:9b")
            assert data is None and not result.ok
            assert len(requests) == 1 and requests[0]["messages"] == []
            assert not client._history
            await client.close()
    asyncio.run(go())


def test_load_wait_and_generation_share_one_deadline(monkeypatch):
    async def go():
        async def respond(payload):
            await asyncio.sleep(.15)
            return loaded()
        async with readiness_server(monkeypatch, respond) as requests:
            client = local_ai.LocalAI("brief")
            before = time.monotonic()
            data, result = await client.one_shot("mark", model="ollama:qwen3.5:9b", timeout=.03)
            assert data is None and not result.ok and "too long" in result.message
            assert time.monotonic() - before < .12
            assert len(requests) == 1 and requests[0]["messages"] == []
            await client.close()
    asyncio.run(go())


def test_reset_after_preload_prevents_stale_prompt(monkeypatch):
    async def go():
        client = local_ai.LocalAI("brief")
        calls = []
        async def events(payload, timeout):
            calls.append(payload)
            await client.reset()
            yield {"done": True, "done_reason": "load"}
        monkeypatch.setattr(client, "_events", events)
        data, result = await client.one_shot("stale private question", model="ollama:qwen3.5:9b")
        assert data is None and not result.ok
        assert len(calls) == 1 and calls[0]["messages"] == []
        assert not client._history
        await client.close()
    asyncio.run(go())


def test_context_recovery_preloads_larger_window_and_counts_only_generated_tokens(monkeypatch):
    async def go():
        generations = []
        async def respond(payload):
            if not payload["messages"]:
                return loaded()
            generations.append(payload)
            if len(generations) == 1:
                return [{"message": {"thinking": "hidden", "content": ""}, "done": True,
                         "done_reason": "length", "eval_count": 5}]
            return [{"message": {"content": '{"answer":7}'}, "done": True, "eval_count": 3}]
        async with readiness_server(monkeypatch, respond) as requests:
            client = local_ai.LocalAI("brief")
            data, result = await client.one_shot("mark", model="ollama:gemma4:26b-a4b-it-qat", think=True)
            assert data == {"answer": 7} and result.ok
            assert [p["options"]["num_ctx"] for p in requests] == [8192, 8192, 16384, 16384]
            assert [bool(p["messages"]) for p in requests] == [False, True, False, True]
            assert result.performance["preload_count"] == 2 and result.performance["output_tokens"] == 8
            assert "hidden" not in result.text
            await client.close()
    asyncio.run(go())


def test_cancelled_preload_closes_work_and_never_commits_a_turn(monkeypatch):
    async def go():
        client = local_ai.LocalAI("brief")
        started, closed, calls = asyncio.Event(), asyncio.Event(), []
        async def events(payload, timeout):
            calls.append(payload)
            started.set()
            try:
                await asyncio.Event().wait()
                yield
            finally:
                closed.set()
        monkeypatch.setattr(client, "_events", events)
        async def consume():
            return [part async for part in client.stream("Private", model="ollama:qwen3.5:9b")]
        task = asyncio.create_task(consume())
        await started.wait()
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task
        assert closed.is_set() and not client._lock.locked()
        assert not client._history and not client.last.ok
        assert len(calls) == 1 and calls[0]["messages"] == []
        await client.close()
    asyncio.run(go())


def test_drive_removed_during_preload_never_sends_question(monkeypatch):
    async def go():
        client = local_ai.LocalAI("brief")
        calls = []
        async def events(payload, timeout):
            calls.append(payload)
            monkeypatch.setattr(local_models, "available_models", lambda: ())
            yield {"done": True, "done_reason": "load"}
        monkeypatch.setattr(client, "_events", events)
        data, result = await client.one_shot("Private", model="ollama:qwen3.5:9b")
        assert data is None and not result.ok and "SSD" in result.message
        assert len(calls) == 1 and calls[0]["messages"] == []
        await client.close()
    asyncio.run(go())


def test_no_other_local_task_interleaves_between_preload_and_generation(monkeypatch):
    async def go():
        started, release = asyncio.Event(), asyncio.Event()
        async def respond(payload):
            if not payload["messages"]:
                if payload["model"] == "qwen3.5:9b":
                    started.set()
                    await release.wait()
                return loaded()
            return [{"message": {"content": '{"answer":7}'}, "done": True}]
        async with readiness_server(monkeypatch, respond) as requests:
            client = local_ai.LocalAI("brief")
            first = asyncio.create_task(client.one_shot("First", model="ollama:qwen3.5:9b"))
            await started.wait()
            second = asyncio.create_task(client.one_shot("Second", model="ollama:gemma4:26b-a4b-it-qat"))
            await asyncio.sleep(.01)
            assert len(requests) == 1 and not first.done() and not second.done()
            release.set()
            assert all(result.ok for _, result in await asyncio.gather(first, second))
            assert [(p["model"], bool(p["messages"])) for p in requests] == [
                ("qwen3.5:9b", False), ("qwen3.5:9b", True),
                ("gemma4:26b-a4b-it-qat", False), ("gemma4:26b-a4b-it-qat", True)]
            await client.close()
    asyncio.run(go())


@pytest.mark.parametrize("interruption", ["reset", "disconnect", "deadline"])
def test_state_change_while_connecting_never_sends_stale_prompt(monkeypatch, interruption):
    async def go():
        async def respond(payload):
            return loaded() if not payload["messages"] else [
                {"message": {"content": '{"answer":7}'}, "done": True}]
        async with readiness_server(monkeypatch, respond) as requests:
            client = local_ai.LocalAI("brief")
            connect, connections = client._connect, []
            async def interrupted_connect(deadline):
                pair = await connect(deadline)
                connections.append(pair)
                if len(connections) == 2:
                    if interruption == "reset":
                        await client.reset()
                    elif interruption == "disconnect":
                        monkeypatch.setattr(local_models, "available_models", lambda: ())
                    else:
                        await asyncio.sleep(.06)
                return pair
            monkeypatch.setattr(client, "_connect", interrupted_connect)
            data, result = await client.one_shot("Stale private question", model="ollama:qwen3.5:9b", timeout=.04)
            await asyncio.sleep(.01)
            assert data is None and not result.ok
            assert len(requests) == 1 and requests[0]["messages"] == []
            assert not client._writers and not client._lock.locked()
            await client.close()
    asyncio.run(go())
