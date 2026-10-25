"""The shared tutor pipeline keeps exact preload, efforts and runtime ownership."""
import asyncio
import json
from contextlib import aclosing

import pytest

from tutor_app import local_ai, local_models
from tutor_app.ai import Result
from tutor_app.tutor_ai import TutorAI

MLX = "mlx:gpt-oss:20b"
OLLAMA = "ollama:gpt-oss:20b"


@pytest.fixture(autouse=True)
def installed(monkeypatch):
    monkeypatch.setattr(local_models, "available_models", lambda: tuple(local_models.LOCAL_MODELS))
    async def never_connect(*args, **kwargs):
        raise AssertionError("Unit tests must not contact Ollama")
    monkeypatch.setattr(local_ai.LocalAI, "_connect", never_connect)


class Worker:
    def __init__(self, order):
        self.order = order
        self._closed = False

    async def events(self, payload, timeout):
        self.order.append(("mlx", payload.copy()))
        if not payload["messages"]:
            yield {"done": True, "done_reason": "load", "message": {"content": ""}}
        else:
            yield {"done": False, "message": {"thinking": "phase"}}
            content = json.dumps({"reply": "Seven."}) if payload.get("format", {}).get("required") == ["reply"] else '{"answer":7}'
            # Chat schema also has optional speech; its reply property determines the envelope.
            if "reply" in payload.get("format", {}).get("properties", {}):
                content = '{"reply":"Seven."}'
            yield {"done": True, "done_reason": "stop", "message": {"content": content}}

    async def close(self):
        self._closed = True
        self.order.append(("close", None))


def transports(monkeypatch, client, *, residents=()):
    from tutor_app import mlx_local
    order, loaded = [], set(residents)
    monkeypatch.setattr(mlx_local, "MLXLocal", lambda: Worker(order))
    async def http(payload, timeout, path="/api/chat", **kwargs):
        order.append(("http", (path, payload.copy(), kwargs)))
        if path == "/api/ps":
            yield {"models": [{"name": name, "model": name} for name in sorted(loaded)]}
        elif payload.get("keep_alive") == 0:
            loaded.discard(payload["model"])
            yield {"done": True, "done_reason": "unload", "message": {"content": ""}}
        elif not payload["messages"]:
            loaded.add(payload["model"])
            yield {"done": True, "done_reason": "load"}
        else:
            yield {"done": True, "message": {"content": '{"answer":7}'}}
    monkeypatch.setattr(client, "_http_events", http, raising=False)
    return order


def test_switch_releases_only_prepared_ollama_before_mlx_and_releases_mlx_before_ollama(monkeypatch):
    async def go():
        client = local_ai.LocalAI("brief")
        order = transports(monkeypatch, client)
        try:
            assert (await client.warm(OLLAMA)).ok
            # Activity state must never become the identity of the model safe to unload.
            client._active_model = "ollama:unrelated:latest"
            data, result = await client.one_shot("mark", model=MLX, think="medium")
            assert data == {"answer": 7} and result.ok
            unloads = [p for kind, value in order if kind == "http" for path, p, _ in [value] if p.get("keep_alive") == 0]
            assert [p["model"] for p in unloads] == ["gpt-oss:20b"]
            assert next(i for i, item in enumerate(order) if item[0] == "mlx") > next(
                i for i, item in enumerate(order) if item[0] == "http" and item[1][1].get("keep_alive") == 0)
            assert (await client.one_shot("back", model=OLLAMA))[1].ok
            close_at = next(i for i, item in enumerate(order) if item[0] == "close")
            assert order[close_at + 1][0] == "http"
        finally:
            await client.close()
    asyncio.run(go())


def test_unrelated_resident_blocks_mlx_without_unloading_it(monkeypatch):
    async def go():
        client = local_ai.LocalAI("brief")
        order = transports(monkeypatch, client, residents=("unrelated:latest",))
        data, result = await client.one_shot("private", model=MLX)
        assert data is None and not result.ok and "Ollama" in result.message
        assert not any(kind == "mlx" for kind, _ in order)
        assert not any(value[1].get("keep_alive") == 0 for kind, value in order if kind == "http")
        await client.close()
    asyncio.run(go())


def test_named_efforts_partition_history_and_legacy_alias_reuses_low(monkeypatch):
    async def go():
        client = local_ai.LocalAI("brief")
        order = transports(monkeypatch, client)
        for effort in (False, "medium", "low", "high"):
            assert "".join([p async for p in client.stream("help", model=MLX, think=effort)]) == "Seven."
            assert client.last.ok
        calls = [p for kind, p in order if kind == "mlx" and p["messages"]]
        assert [p["think"] for p in calls] == ["low", "medium", "low", "high"]
        assert [len(p["messages"]) for p in calls] == [2, 2, 4, 2]
        assert len(client._history) == 3
        assert all(client.last.performance[key] is None for key in (
            "engine_seconds", "load_seconds", "prompt_seconds", "generation_seconds",
            "input_tokens", "output_tokens", "cached_input_tokens", "tokens_per_second"))
        await client.close()
    asyncio.run(go())


@pytest.mark.parametrize("operation", ["stream", "json"])
def test_invalid_effort_fails_before_any_preload_or_generation(monkeypatch, operation):
    async def go():
        client = local_ai.LocalAI("brief")
        order = transports(monkeypatch, client)
        if operation == "stream":
            assert [p async for p in client.stream("private", model=MLX, think="maximum")] == []
            result = client.last
        else:
            _, result = await client.one_shot("private", model=MLX, think="maximum")
        assert not result.ok and not order
        await client.close()
    asyncio.run(go())


def test_reset_stops_active_mlx_work_and_rejects_its_stale_answer(monkeypatch):
    from tutor_app import mlx_local
    async def go():
        client = local_ai.LocalAI("brief")
        order = transports(monkeypatch, client)
        started, release = asyncio.Event(), asyncio.Event()
        class Busy(Worker):
            async def events(self, payload, timeout):
                if payload["messages"]:
                    started.set()
                    await release.wait()
                async for event in super().events(payload, timeout):
                    yield event
        monkeypatch.setattr(mlx_local, "MLXLocal", lambda: Busy(order))
        task = asyncio.create_task(client.one_shot("mark", model=MLX))
        try:
            await started.wait()
            await client.reset()
            assert any(kind == "close" for kind, _ in order)
            assert not client._history and not client._shown and client._mlx is None
            release.set()
            data, result = await task
            assert data is None and not result.ok
        finally:
            release.set()
            await asyncio.gather(task, return_exceptions=True)
            await client.close()
    asyncio.run(go())


def test_tutor_reply_cache_uses_canonical_effort_without_loading_for_cloud(monkeypatch, tmp_path):
    monkeypatch.setenv("PATH", str(tmp_path))
    async def go():
        client = TutorAI(tmp_path, system="brief")
        client.local_web = False
        order = transports(monkeypatch, client.local)
        try:
            answers = []
            for effort in (False, "low", "medium", "high", True):
                answers.append(await client.one_shot("same", model=MLX, think=effort))
            assert all(result.ok and data == {"answer": 7} for data, result in answers)
            assert answers[1][1].performance.get("cached_reply") is True
            assert answers[4][1].performance.get("cached_reply") is True
            assert len([p for kind, p in order if kind == "mlx" and p["messages"]]) == 3
        finally:
            await client.close()
        cloud = TutorAI(tmp_path, system="brief")
        await cloud.warm(model="sonnet")
        assert cloud._local is None
        await cloud.close()
    asyncio.run(go())


def test_failed_unload_ack_blocks_mlx_without_clearing_prepared_identity(monkeypatch):
    async def go():
        client = local_ai.LocalAI("brief")
        order = transports(monkeypatch, client)
        assert (await client.warm(OLLAMA)).ok
        async def failed_unload(payload, timeout, path="/api/chat", **kwargs):
            if path == "/api/ps":
                yield {"models": [{"model": "gpt-oss:20b"}]}
            else:
                yield {"done": True, "done_reason": "stop"}
        monkeypatch.setattr(client, "_http_events", failed_unload)
        data, result = await client.one_shot("private", model=MLX)
        assert data is None and not result.ok
        assert client._prepared_ollama == OLLAMA
        assert "confirm release" in result.message
        assert not any(kind == "mlx" for kind, _ in order)
        await client.close()
    asyncio.run(go())


def test_mlx_offline_residency_check_never_starts_ollama(monkeypatch):
    from tutor_app import mlx_local
    async def go():
        client = local_ai.LocalAI("brief")
        order = []
        monkeypatch.setattr(mlx_local, "MLXLocal", lambda: Worker(order))
        async def offline(*args, **kwargs):
            raise ConnectionRefusedError
        monkeypatch.setattr(asyncio, "open_connection", offline)
        assert (await client.warm(MLX)).ok
        assert len(order) == 1 and order[0][0] == "mlx"
        assert "think" not in order[0][1] and not order[0][1]["messages"]
        await client.close()
    asyncio.run(go())


def test_chat_queue_wait_is_bounded_by_original_deadline(monkeypatch):
    monkeypatch.setattr(local_ai, "CHAT_TIMEOUT", .03)
    async def go():
        client = local_ai.LocalAI("brief")
        order = transports(monkeypatch, client)
        await client._lock.acquire()
        task = asyncio.create_task(anext(client.stream("queued", model=MLX), None))
        try:
            await asyncio.sleep(.07)
            assert task.done(), "A queued chat must expire while the other request still owns the lock"
            assert await task is None
            assert not client.last.ok and "too long" in client.last.message
            assert not order
        finally:
            client._lock.release()
            task.cancel()
            await asyncio.gather(task, return_exceptions=True)
            await client.close()
    asyncio.run(go())


def test_disconnect_at_completion_closes_worker_and_never_commits_reply(monkeypatch):
    from tutor_app import mlx_local
    async def go():
        client = local_ai.LocalAI("brief")
        order = transports(monkeypatch, client)
        class Removed(Worker):
            async def events(self, payload, timeout):
                async for event in super().events(payload, timeout):
                    if payload["messages"] and event.get("done"):
                        monkeypatch.setattr(local_models, "available_models", lambda: ())
                    yield event
        monkeypatch.setattr(mlx_local, "MLXLocal", lambda: Removed(order))
        data, result = await client.one_shot("stale", model=MLX)
        assert data is None and not result.ok
        assert any(kind == "close" for kind, _ in order)
        assert not client._history
        await client.close()
    asyncio.run(go())


def test_unavailable_model_releases_previous_mlx_worker(monkeypatch):
    async def go():
        client = local_ai.LocalAI("brief")
        order = transports(monkeypatch, client)
        try:
            assert (await client.warm(MLX)).ok
            monkeypatch.setattr(local_models, "available_models", lambda: ())
            data, result = await client.one_shot("after unplug", model=MLX)
            assert data is None and not result.ok
            assert any(kind == "close" for kind, _ in order)
        finally:
            await client.close()
    asyncio.run(go())


def test_idle_reset_retains_weights_but_clears_history_and_requires_fresh_load(monkeypatch):
    async def go():
        client = local_ai.LocalAI("brief")
        order = transports(monkeypatch, client)
        try:
            assert (await client.warm(MLX)).ok
            worker = client._mlx
            assert "".join([p async for p in client.stream("first", model=MLX)]) == "Seven."
            assert client._history
            await client.reset()
            assert client._mlx is worker and not worker._closed
            assert not client._history and not client._shown
            assert "".join([p async for p in client.stream("fresh", model=MLX)]) == "Seven."
            assert client._mlx is worker
            calls = [p for kind, p in order if kind == "mlx"]
            assert [bool(p["messages"]) for p in calls] == [False, False, True, False, True]
            assert len(calls[-1]["messages"]) == 2
            assert not any(kind == "close" for kind, _ in order)
        finally:
            await client.close()
        assert worker._closed
    asyncio.run(go())


def test_tutor_reset_clears_cached_reply_while_retaining_idle_mlx_weights(monkeypatch, tmp_path):
    monkeypatch.setenv("PATH", str(tmp_path))
    async def go():
        client = TutorAI(tmp_path, system="brief")
        client.local_web = False
        order = transports(monkeypatch, client.local)
        try:
            first = await client.one_shot("same", model=MLX)
            worker = client.local._mlx
            cached = await client.one_shot("same", model=MLX)
            assert first[1].ok and cached[1].performance.get("cached_reply") is True
            await client.reset(warm=False)
            assert client.local._mlx is worker
            fresh = await client.one_shot("same", model=MLX)
            assert fresh[1].ok and not fresh[1].performance.get("cached_reply")
            assert client.local._mlx is worker
            assert [bool(p["messages"]) for kind, p in order if kind == "mlx"] == [False, True, False, True]
        finally:
            await client.close()
        assert worker._closed
    asyncio.run(go())


def test_prepared_ollama_then_offline_allows_mlx_without_autostart(monkeypatch):
    async def go():
        client = local_ai.LocalAI("brief")
        order = transports(monkeypatch, client)
        try:
            assert (await client.warm(OLLAMA)).ok
            assert client._prepared_ollama == OLLAMA
            monkeypatch.setattr(client, "_http_events", local_ai.LocalAI._http_events.__get__(client))
            async def offline(*args, **kwargs):
                raise ConnectionRefusedError
            monkeypatch.setattr(asyncio, "open_connection", offline)
            assert (await client.warm(MLX)).ok
            assert client._prepared_ollama is None
            assert len([p for kind, p in order if kind == "mlx"]) == 1
        finally:
            await client.close()
    asyncio.run(go())


def test_prepared_ollama_already_unloaded_clears_stale_ownership_without_unload(monkeypatch):
    async def go():
        client = local_ai.LocalAI("brief")
        order = transports(monkeypatch, client)
        client._prepared_ollama = OLLAMA
        try:
            assert (await client.warm(MLX)).ok
            assert client._prepared_ollama is None
            assert not any(value[1].get("keep_alive") == 0 for kind, value in order if kind == "http")
        finally:
            await client.close()
    asyncio.run(go())


def test_uncertain_ollama_connection_failure_does_not_load_mlx(monkeypatch):
    from tutor_app import mlx_local
    async def go():
        client = local_ai.LocalAI("brief")
        order = []
        monkeypatch.setattr(mlx_local, "MLXLocal", lambda: Worker(order))
        async def uncertain(*args, **kwargs):
            raise ConnectionResetError("connection interrupted")
        monkeypatch.setattr(asyncio, "open_connection", uncertain)
        try:
            result = await client.warm(MLX)
            assert not result.ok and not order
        finally:
            await client.close()
    asyncio.run(go())


@pytest.mark.parametrize("failure", ["empty_probe", "invalid_probe", "unload_connection", "resident_after_ack"])
def test_uncertain_or_unreleased_ollama_residency_blocks_mlx(monkeypatch, failure):
    async def go():
        client = local_ai.LocalAI("brief")
        order = transports(monkeypatch, client)
        client._prepared_ollama = OLLAMA
        async def uncertain(payload, timeout, path="/api/chat", **kwargs):
            if path == "/api/ps":
                if failure == "empty_probe":
                    return
                yield {"models": [None] if failure == "invalid_probe" else [{"model": "gpt-oss:20b"}]}
            elif failure == "unload_connection":
                raise ConnectionResetError("unload interrupted")
            else:
                yield {"done": True, "done_reason": "unload"}
        monkeypatch.setattr(client, "_http_events", uncertain)
        try:
            result = await client.warm(MLX)
            assert not result.ok and client._prepared_ollama == OLLAMA
            assert not any(kind == "mlx" for kind, _ in order)
        finally:
            await client.close()
    asyncio.run(go())
