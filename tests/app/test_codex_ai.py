"""Subscription tutoring uses isolated fake Codex subprocesses, never live inference."""
import asyncio
import json
from pathlib import Path

import pytest


MODEL = "codex:gpt-6.1-sol"
FAKE = str(Path(__file__).with_name("fake_codex.py"))


def make(tmp_path, monkeypatch, mode="ok", speech=False):
    from tutor_app.codex_ai import CodexAI
    monkeypatch.setenv("FAKE_CODEX_LOG", str(tmp_path / "requests.jsonl"))
    monkeypatch.setenv("FAKE_CODEX_MODE", mode)
    return CodexAI("Tutor instructions", speech=speech, binary=FAKE)


def requests(tmp_path):
    return [json.loads(s) for s in (tmp_path / "requests.jsonl").read_text().splitlines()]


def test_exec_uses_subscription_and_isolated_tools_with_provider_usage(tmp_path, monkeypatch):
    client = make(tmp_path, monkeypatch, speech=True)
    monkeypatch.setenv("OPENAI_API_KEY", "fake-key-that-must-not-reach-cli")
    monkeypatch.setenv("CODEX_API_KEY", "fake-key-that-must-not-reach-cli")

    async def go():
        chunks = [s async for s in client.stream("Explain force", model=MODEL)]
        await client.close()
        return chunks

    assert "".join(asyncio.run(go())).strip() == "A useful hint."
    assert client.last.ok and client.last.speech == "A useful hint."
    assert client.last.usage["input_tokens"] == 35 and client.last.performance == {}
    row = requests(tmp_path)[0]
    args = row["args"]
    for flag in ("--json", "--ephemeral", "--ignore-user-config", "--ignore-rules", "--skip-git-repo-check"):
        assert flag in args
    assert args[args.index("--sandbox") + 1] == "read-only"
    assert args[args.index("--model") + 1] == "gpt-6.1-sol"
    assert 'forced_login_method="chatgpt"' in args and 'web_search="disabled"' in args
    for feature in ("shell_tool", "apps", "plugins", "hooks", "multi_agent"):
        assert f"features.{feature}=false" in args
    assert not row["api_key_present"] and row["cwd"] != str(tmp_path)
    assert "Tutor instructions" in row["instructions"] and "[[SPEECH]]" in row["instructions"]
    assert not Path(row["cwd"]).exists()


def test_memory_and_images_are_per_model_thinking_and_reset(tmp_path, monkeypatch):
    client = make(tmp_path, monkeypatch)
    image = tmp_path / "diagram.png"
    image.write_bytes(b"diagram")

    async def go():
        for prompt, model, think in (("one", MODEL, False), ("two", MODEL, False),
                                     ("thought", MODEL, True), ("other", "codex:gpt-6-astra", False)):
            _ = [s async for s in client.stream(prompt, image=image, model=model, think=think)]
        await client.reset()
        _ = [s async for s in client.stream("fresh", model=MODEL)]
        await client.close()

    asyncio.run(go())
    rows = requests(tmp_path)
    assert [len(r["prompt"]["messages"]) for r in rows] == [1, 3, 1, 1, 1]
    assert rows[1]["prompt"]["messages"][0]["content"] == "one"
    assert rows[1]["prompt"]["messages"][-1]["content"] == "two"
    assert str(image) in rows[1]["args"] and "--image" not in rows[4]["args"]
    assert 'model_reasoning_effort="low"' in rows[0]["args"]
    assert 'model_reasoning_effort="high"' in rows[2]["args"]


def test_schema_system_and_speech_are_isolated_from_chat_and_original_schema(tmp_path, monkeypatch):
    client = make(tmp_path, monkeypatch, speech=True)
    schema = {"type": "object", "properties": {"feedback": {"type": "string"}}, "required": ["feedback"]}

    async def go():
        data, result = await client.one_shot("Mark", schema=schema, model=MODEL, system="Examiner", speech=True)
        _ = [s async for s in client.stream("Next", model=MODEL)]
        await client.close()
        return data, result

    data, result = asyncio.run(go())
    assert data["feedback"] == "Good." and result.ok and result.speech == "Spoken feedback."
    rows = requests(tmp_path)
    assert rows[0]["instructions"].startswith("Examiner")
    assert rows[0]["schema"]["additionalProperties"] is False
    assert rows[0]["schema"]["properties"]["speech"] == {"type": "string"}
    assert "speech" in rows[0]["schema"]["required"] and "speech" not in schema["properties"]
    assert len(rows[1]["prompt"]["messages"]) == 1


@pytest.mark.parametrize("mode,status", [("login", "login"), ("limit", "limit"),
                                        ("unreadable", "error"), ("unfinished", "error")])
def test_failed_calls_return_actionable_errors_without_success_or_history(tmp_path, monkeypatch, mode, status):
    client = make(tmp_path, monkeypatch, mode=mode)

    async def go():
        _ = [s async for s in client.stream("failed", model=MODEL)]
        result = client.last
        await client.close()
        return result

    result = asyncio.run(go())
    assert not result.ok and result.status == status and result.message
    if mode == "login":
        assert "codex login" in result.message


def test_cancelled_reply_stops_process_and_does_not_commit_memory(tmp_path, monkeypatch):
    client = make(tmp_path, monkeypatch, mode="wait")

    async def go():
        reply = client.stream("cancel", model=MODEL)
        assert (await anext(reply)).strip() == "A useful hint."
        await reply.aclose()
        assert not client.last.ok
        monkeypatch.setenv("FAKE_CODEX_MODE", "ok")
        _ = [s async for s in client.stream("fresh", model=MODEL)]
        await client.close()

    asyncio.run(go())
    assert len(requests(tmp_path)[1]["prompt"]["messages"]) == 1


def test_deadline_covers_busy_client_and_running_process(tmp_path, monkeypatch):
    client = make(tmp_path, monkeypatch, mode="wait")

    async def go():
        data, result = await client.one_shot("timeout", model=MODEL, timeout=0.08)
        assert data is None and not result.ok and "long" in result.message
        await client._lock.acquire()
        try:
            task = asyncio.create_task(client.one_shot("queued", model=MODEL, timeout=0.02))
            done, _ = await asyncio.wait({task}, timeout=0.1)
            assert task in done and not task.result()[1].ok
        finally:
            client._lock.release()
        await client.close()

    asyncio.run(go())


def test_reset_closes_active_reply_and_closed_client_stays_closed(tmp_path, monkeypatch):
    client = make(tmp_path, monkeypatch, mode="wait")

    async def go():
        reply = client.stream("reset", model=MODEL)
        await anext(reply)
        await client.reset()
        _ = [s async for s in reply]
        assert not client.last.ok
        await client.close()
        assert [s async for s in client.stream("closed", model=MODEL)] == []
        assert not client.last.ok

    asyncio.run(go())


def test_unknown_models_and_missing_cli_never_launch_another_provider(tmp_path, monkeypatch):
    from tutor_app.codex_ai import CodexAI
    client = make(tmp_path, monkeypatch)

    async def go():
        data, result = await client.one_shot("bad", model="codex:unknown")
        await client.close()
        assert data is None and not result.ok

    asyncio.run(go())
    assert not (tmp_path / "requests.jsonl").exists()
    assert not CodexAI("brief", binary=str(tmp_path / "missing")).available


def test_cancel_during_launch_retains_and_stops_late_process(tmp_path, monkeypatch):
    from tutor_app import codex_ai
    client = make(tmp_path, monkeypatch)
    original = asyncio.create_subprocess_exec

    async def go():
        launched, release, processes = asyncio.Event(), asyncio.Event(), []

        async def delayed(*args, **kwargs):
            proc = await original(*args, **kwargs)
            processes.append(proc)
            launched.set()
            await release.wait()
            return proc

        monkeypatch.setattr(codex_ai.asyncio, "create_subprocess_exec", delayed)
        task = asyncio.create_task(client.one_shot("cancel", model=MODEL))
        try:
            await asyncio.wait_for(launched.wait(), 1)
            task.cancel()
            with pytest.raises(asyncio.CancelledError):
                await task
            closing = asyncio.create_task(client.close())
            release.set()
            await asyncio.wait_for(closing, 1)
            assert processes[0].returncode is not None
        finally:
            for proc in processes:
                await client._stop(proc)

    asyncio.run(go())


def test_incomplete_schema_data_is_rejected(tmp_path, monkeypatch):
    client = make(tmp_path, monkeypatch)
    monkeypatch.setenv("FAKE_CODEX_REPLY", '{"wrong":"field"}')

    async def go():
        data, result = await client.one_shot("Mark", schema={"properties": {"feedback": {"type": "string"}}}, model=MODEL)
        await client.close()
        return data, result

    data, result = asyncio.run(go())
    assert data is None and not result.ok and "JSON" in result.message


def test_optional_schema_fields_remain_optional_for_challenge_and_marking(tmp_path, monkeypatch):
    client = make(tmp_path, monkeypatch)
    monkeypatch.setenv("FAKE_CODEX_REPLY", '{"feedback":"Good.","why":null,"points":[{"point":"p","met":true,"why":null}]}')
    schema = {"type": "object", "properties": {
        "feedback": {"type": "string"}, "why": {"type": "string"},
        "points": {"type": "array", "items": {"type": "object", "properties": {
            "point": {"type": "string"}, "met": {"type": "boolean"}, "why": {"type": "string"}},
            "required": ["point", "met"]}}}, "required": ["feedback", "points"]}

    async def go():
        data, result = await client.one_shot("Mark", schema=schema, model=MODEL)
        await client.close()
        return data, result

    data, result = asyncio.run(go())
    wire = requests(tmp_path)[0]["schema"]
    assert wire["properties"]["why"]["type"] == ["string", "null"]
    assert wire["properties"]["points"]["items"]["properties"]["why"]["type"] == ["string", "null"]
    assert result.ok and "why" not in data and "why" not in data["points"][0]


@pytest.mark.parametrize("kind", ["stream", "one_shot"])
def test_reset_cancels_preexisting_queued_codex_request_before_launch(tmp_path, monkeypatch, kind):
    from tutor_app.ai import Result
    client = make(tmp_path, monkeypatch)

    async def go():
        previous = client.last = Result(text="Earlier completed answer.")
        await client._lock.acquire()

        async def request():
            if kind == "stream":
                return [part async for part in client.stream("old queued question", model=MODEL)]
            return await client.one_shot("old queued marking", model=MODEL)

        task = asyncio.create_task(request())
        try:
            await asyncio.sleep(0)
            await client.reset()
            client._lock.release()
            with pytest.raises(asyncio.CancelledError):
                await task
            assert client.last is previous and previous.ok
            assert not (tmp_path / "requests.jsonl").exists()
        finally:
            task.cancel()
            await asyncio.gather(task, return_exceptions=True)
            if client._lock.locked():
                client._lock.release()
            await client.close()

    asyncio.run(go())


def test_cancelling_queued_stream_does_not_mutate_active_request_result(tmp_path, monkeypatch):
    from tutor_app.ai import Result
    client = make(tmp_path, monkeypatch)

    async def go():
        active = client.last = Result(text="The active request owns this result.")
        await client._lock.acquire()

        async def request():
            return [part async for part in client.stream("queued", model=MODEL)]

        task = asyncio.create_task(request())
        try:
            await asyncio.sleep(0)
            task.cancel()
            with pytest.raises(asyncio.CancelledError):
                await task
            assert client.last is active and active.ok
        finally:
            client._lock.release()
            await client.close()

    asyncio.run(go())


def test_queued_stream_deadline_cancels_without_launch_or_active_result_mutation(tmp_path, monkeypatch):
    from tutor_app import codex_ai
    from tutor_app.ai import Result
    client = make(tmp_path, monkeypatch)
    original_wait = asyncio.wait_for

    async def short_deadline(awaitable, timeout):
        return await original_wait(awaitable, min(timeout, 0.01))

    monkeypatch.setattr(codex_ai.asyncio, "wait_for", short_deadline)

    async def go():
        active = client.last = Result(text="The active request owns this result.")
        await client._lock.acquire()
        try:
            with pytest.raises(asyncio.CancelledError):
                _ = [part async for part in client.stream("queued until deadline", model=MODEL)]
            assert client.last is active and active.ok
            assert not (tmp_path / "requests.jsonl").exists()
        finally:
            client._lock.release()
            await client.close()

    asyncio.run(go())
