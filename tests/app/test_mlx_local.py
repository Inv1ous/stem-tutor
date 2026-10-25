"""Owned IPC is exercised with a tiny Python worker; no model imports or GPU work."""
import asyncio
import importlib
import json
import os
import sys
import time

import pytest

from tutor_app import local_models
from tutor_app.local_ai import LocalError

MODEL = "mlx:gpt-oss:20b"
WORKER = '''
import json, os, sys, time
for line in sys.stdin:
    request = json.loads(line)
    payload = request["payload"]
    with open(os.environ["FAKE_REQUESTS"], "a") as log:
        log.write(json.dumps(payload) + "\\n")
    behavior = os.environ.get("FAKE_BEHAVIOR", "good")
    if behavior == "hang":
        time.sleep(60)
    event = {"model": "mlx:gpt-oss:20b", "checkpoint": os.environ["FAKE_CHECKPOINT"],
             "worker_pid": os.getpid(), "_epoch": payload["_epoch"],
             "message": {"role": "assistant", "content": "" if not payload["messages"] else '{"answer":7}'},
             "done": True, "done_reason": "load" if not payload["messages"] else "stop"}
    if behavior == "id": request["id"] = "stale"
    elif behavior == "model": event["model"] = "ollama:gpt-oss:20b"
    elif behavior == "checkpoint": event["checkpoint"] = "/unrelated"
    elif behavior == "pid": event["worker_pid"] += 1
    elif behavior == "epoch": event["_epoch"] -= 1
    elif behavior == "content": event["message"]["content"] = "unexpected answer"
    elif behavior == "oversize": event["message"]["content"] = "x" * (4 * 1024 * 1024)
    elif behavior == "worker_error": event = {**event, "error": "Checkpoint files are missing; reconnect the SSD."}; event.pop("done_reason")
    elif behavior == "crash": sys.exit(3)
    print(json.dumps({"id": request["id"], "event": event}), flush=True)
'''


@pytest.fixture
def fake_worker(monkeypatch, tmp_path):
    script, log = tmp_path / "worker.py", tmp_path / "requests.jsonl"
    script.write_text(WORKER)
    checkpoint = tmp_path / "checkpoint"
    checkpoint.mkdir()
    root = tmp_path / "LocalAI"
    root.mkdir()
    monkeypatch.setattr(local_models, "ROOT", root)
    monkeypatch.setattr(local_models, "MLX_CHECKPOINT", checkpoint, raising=False)
    monkeypatch.setattr(local_models, "MLX_PYTHON", tmp_path / "ssd-python", raising=False)
    monkeypatch.setattr(local_models, "available_models", lambda: (MODEL,))
    real_launch = asyncio.create_subprocess_exec
    processes, commands = [], []
    async def launch(*args, **kwargs):
        commands.append((args, kwargs))
        kwargs["env"] = {**kwargs["env"], "FAKE_REQUESTS": str(log), "FAKE_CHECKPOINT": str(checkpoint)}
        process = await real_launch(sys.executable, "-u", str(script), **kwargs)
        processes.append(process)
        return process
    monkeypatch.setattr(asyncio, "create_subprocess_exec", launch)
    return processes, commands, log


def adapter():
    return importlib.import_module("tutor_app.mlx_local").MLXLocal()


def payload(messages=None):
    return {"model": MODEL, "messages": [] if messages is None else messages, "stream": True}


def test_exact_preload_and_full_messages_reuse_one_owned_worker(fake_worker):
    async def go():
        client = adapter()
        try:
            load = [event async for event in client.events(payload(), 2)]
            assert load[-1]["done_reason"] == "load" and load[-1]["message"]["content"] == ""
            messages = [{"role": "system", "content": "brief"}, {"role": "user", "content": "first"},
                        {"role": "assistant", "content": "previous"}, {"role": "user", "content": "next"}]
            events = [event async for event in client.events(payload(messages), 2)]
            assert events[-1]["message"]["content"] == '{"answer":7}'
            processes, commands, log = fake_worker
            assert len(processes) == 1
            assert commands[0][0] == (str(local_models.MLX_PYTHON), "-m", "tutor_app.mlx_worker")
            assert commands[0][1]["stderr"] is asyncio.subprocess.DEVNULL
            requests = [json.loads(line) for line in log.read_text().splitlines()]
            assert requests[1]["messages"] == messages
            assert requests[0]["_deadline"] <= requests[1]["_deadline"]
        finally:
            await client.close()
            await client.close()
        assert all(p.returncode is not None for p in fake_worker[0])
    asyncio.run(go())


@pytest.mark.parametrize("behavior", ["id", "model", "checkpoint", "pid", "epoch", "content", "oversize", "crash"])
def test_untrusted_or_incomplete_preload_never_becomes_ready(monkeypatch, fake_worker, behavior):
    monkeypatch.setenv("FAKE_BEHAVIOR", behavior)
    async def go():
        client = adapter()
        with pytest.raises(LocalError):
            _ = [event async for event in client.events(payload(), 2)]
        assert all(p.returncode is not None for p in fake_worker[0])
        await client.close()
    asyncio.run(go())


@pytest.mark.parametrize("interruption", ["timeout", "cancel", "close"])
def test_interrupted_gpu_work_terminates_only_owned_worker(monkeypatch, fake_worker, interruption):
    monkeypatch.setenv("FAKE_BEHAVIOR", "hang")
    async def go():
        client = adapter()
        async def consume():
            return [event async for event in client.events(payload(), .15 if interruption == "timeout" else 3)]
        task = asyncio.create_task(consume())
        if interruption == "timeout":
            with pytest.raises(asyncio.TimeoutError):
                await task
        else:
            while not fake_worker[2].exists():
                await asyncio.sleep(.005)
            if interruption == "cancel":
                task.cancel()
                with pytest.raises(asyncio.CancelledError):
                    await task
            else:
                await client.close()
                with pytest.raises(LocalError):
                    await task
        assert all(p.returncode is not None for p in fake_worker[0])
        await client.close()
    asyncio.run(go())


def test_ssd_removal_after_spawn_prevents_prompt(monkeypatch, fake_worker):
    async def go():
        client = adapter()
        _ = [event async for event in client.events(payload(), 2)]
        monkeypatch.setattr(local_models, "available_models", lambda: ())
        with pytest.raises(LocalError):
            _ = [event async for event in client.events(payload([{"role": "user", "content": "private"}]), 2)]
        assert len(fake_worker[2].read_text().splitlines()) == 1
        assert all(p.returncode is not None for p in fake_worker[0])
        await client.close()
    asyncio.run(go())


def test_preload_surfaces_the_workers_actionable_error(monkeypatch, fake_worker):
    monkeypatch.setenv("FAKE_BEHAVIOR", "worker_error")
    async def go():
        client = adapter()
        try:
            with pytest.raises(LocalError, match="Checkpoint files are missing; reconnect the SSD"):
                _ = [event async for event in client.events(payload(), 2)]
        finally:
            await client.close()
    asyncio.run(go())


def test_worker_cache_environment_is_forced_to_ssd_without_changing_parent(monkeypatch, fake_worker):
    names = ("HF_HOME", "HF_HUB_CACHE", "HF_XET_CACHE", "TMPDIR", "PYTHONPYCACHEPREFIX",
             "OUTLINES_CACHE_DIR", "XDG_CACHE_HOME")
    for name in names:
        monkeypatch.setenv(name, "/caller-cache")
    monkeypatch.setenv("HF_HUB_OFFLINE", "0")
    original = dict(os.environ)
    async def go():
        client = adapter()
        runtime = local_models.ROOT / "tutor-runtime"
        assert not runtime.exists()
        try:
            _ = [event async for event in client.events(payload(), 2)]
            child_env = fake_worker[1][0][1]["env"]
            expected = {
                "HF_HOME": runtime / "cache/huggingface",
                "HF_HUB_CACHE": runtime / "cache/huggingface/hub",
                "HF_XET_CACHE": runtime / "cache/huggingface/xet",
                "TMPDIR": runtime / "tmp",
                "PYTHONPYCACHEPREFIX": runtime / "cache/pycache",
                "OUTLINES_CACHE_DIR": runtime / "cache/outlines",
                "XDG_CACHE_HOME": runtime / "cache",
            }
            for name, path in expected.items():
                assert child_env[name] == str(path)
                assert path.is_dir()
            assert child_env["HF_HUB_OFFLINE"] == "1"
            assert dict(os.environ) == original
        finally:
            await client.close()
    asyncio.run(go())


def test_unavailable_ssd_does_not_create_worker_cache_directories(monkeypatch, fake_worker):
    monkeypatch.setattr(local_models, "available_models", lambda: ())
    async def go():
        client = adapter()
        try:
            with pytest.raises(LocalError):
                _ = [event async for event in client.events(payload(), 2)]
            assert not (local_models.ROOT / "tutor-runtime").exists()
            assert not fake_worker[0]
        finally:
            await client.close()
    asyncio.run(go())


def test_generation_without_exact_preload_never_starts_or_writes_worker(fake_worker):
    async def go():
        client = adapter()
        try:
            with pytest.raises(LocalError):
                _ = [event async for event in client.events(payload([{"role": "user", "content": "private question"}]), 2)]
            assert not fake_worker[0] and not fake_worker[1]
            assert not fake_worker[2].exists()
        finally:
            await client.close()
    asyncio.run(go())


def test_dead_preloaded_worker_never_receives_question_in_replacement(fake_worker):
    async def go():
        client = adapter()
        try:
            _ = [event async for event in client.events(payload(), 2)]
            prepared = fake_worker[0][0]
            prepared.terminate()
            await prepared.wait()
            with pytest.raises(LocalError):
                _ = [event async for event in client.events(payload([{"role": "user", "content": "private question"}]), 2)]
            assert len(fake_worker[0]) == 1
            requests = [json.loads(line) for line in fake_worker[2].read_text().splitlines()]
            assert len(requests) == 1 and requests[0]["messages"] == []
        finally:
            await client.close()
    asyncio.run(go())


def test_each_generation_consumes_readiness_and_requires_another_empty_ack(fake_worker):
    async def go():
        client = adapter()
        question = payload([{"role": "user", "content": "first"}])
        try:
            _ = [event async for event in client.events(payload(), 2)]
            answer = [event async for event in client.events(question, 2)]
            assert answer[-1]["message"]["content"] == '{"answer":7}'
            with pytest.raises(LocalError):
                _ = [event async for event in client.events(payload([{"role": "user", "content": "second"}]), 2)]
            requests = [json.loads(line) for line in fake_worker[2].read_text().splitlines()]
            assert [bool(request["messages"]) for request in requests] == [False, True]
        finally:
            await client.close()
    asyncio.run(go())


def test_healthy_worker_accepts_repeated_fresh_preload_generation_pairs(fake_worker):
    async def go():
        client = adapter()
        try:
            for prompt in ("first", "second"):
                load = [event async for event in client.events(payload(), 2)]
                assert load[-1]["done_reason"] == "load"
                answer = [event async for event in client.events(payload([{"role": "user", "content": prompt}]), 2)]
                assert answer[-1]["message"]["content"] == '{"answer":7}'
            assert len(fake_worker[0]) == 1
            requests = [json.loads(line) for line in fake_worker[2].read_text().splitlines()]
            assert [bool(request["messages"]) for request in requests] == [False, True, False, True]
        finally:
            await client.close()
    asyncio.run(go())


@pytest.mark.parametrize("changed", ["epoch", "checkpoint"])
def test_preload_identity_cannot_authorize_a_changed_epoch_or_checkpoint(monkeypatch, fake_worker, changed):
    async def go():
        client = adapter()
        try:
            _ = [event async for event in client.events(payload(), 2)]
            if changed == "epoch":
                client._epoch += 1
            else:
                monkeypatch.setattr(local_models, "MLX_CHECKPOINT", local_models.ROOT / "other-checkpoint")
            with pytest.raises(LocalError):
                _ = [event async for event in client.events(payload([{"role": "user", "content": "private question"}]), 2)]
            assert len(fake_worker[0]) == 1
            assert len(fake_worker[2].read_text().splitlines()) == 1
        finally:
            await client.close()
    asyncio.run(go())
