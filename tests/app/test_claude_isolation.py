"""The local-model router preserves the existing Claude client, including direct retries and lifecycle."""
import asyncio
import json
from dataclasses import asdict
from pathlib import Path

import pytest

from tutor_app import ai, tutor_ai


FAKE = str(Path(__file__).with_name("fake_claude.py"))


@pytest.mark.parametrize("model", ["haiku", "sonnet", "opus"])
def test_cloud_stream_schema_speech_and_usage_match_original_client(tmp_path, monkeypatch, model):
    image = tmp_path / "diagram.png"
    image.write_bytes(b"diagram")
    monkeypatch.setenv("FAKE_CLAUDE_MODE", "speech")

    async def scenario(kind, name):
        folder = tmp_path / name
        folder.mkdir()
        log = folder / "argv.jsonl"
        monkeypatch.setenv("FAKE_CLAUDE_LOG", str(log))
        client = kind(tmp_path, model=model, binary=FAKE, speech=True, usage_file=folder / "usage.json")
        chunks = []
        replies = []
        for prompt in ("first", "second"):
            chunks.append([part async for part in client.stream(prompt, image=image, think=True)])
            replies.append(asdict(client.last))
        data, result = await client.one_shot("mark", model=None, schema={"properties": {"feedback": {"type": "string"}}},
                                             system="Examiner brief", speech=True, think=False)
        outcome = (chunks, replies, data, asdict(result), asdict(client.session), client.today())
        await client.close()
        return outcome, log.read_text(), Path(str(log) + ".msgs").read_text(), Path(str(log) + ".prompt").read_text()

    async def go():
        original = await scenario(ai.Claude, "original")
        routed = await scenario(tutor_ai.TutorAI, "routed")
        assert routed == original
        assert [json.loads(line) for line in routed[2].splitlines()] == [["image", "text"], "text"]
        assert routed[0][4] == {"replies": 3, "input_tokens": 36, "cached_tokens": 900, "output_tokens": 60}
        assert all(not reply["performance"] for reply in routed[0][1])
    asyncio.run(go())


@pytest.mark.parametrize("state", ["login", "limit"])
def test_direct_cloud_stream_retries_after_cli_error_like_original(tmp_path, monkeypatch, state):
    async def scenario(kind):
        client = kind(tmp_path, binary=FAKE)
        monkeypatch.setenv("FAKE_CLAUDE_MODE", state)
        first = await client.reply("first")
        monkeypatch.setenv("FAKE_CLAUDE_MODE", "ok")
        second = await client.reply("retry")
        await client.close()
        return first.ok, first.status, second.ok, second.text

    async def go():
        original = await scenario(ai.Claude)
        routed = await scenario(tutor_ai.TutorAI)
        assert routed == original == (False, state, True, "Reply 1: retry")
    asyncio.run(go())


def test_cloud_schema_retry_stays_identical(tmp_path, monkeypatch):
    monkeypatch.setenv("FAKE_CLAUDE_MODE", "ok")

    async def scenario(kind, name):
        log = tmp_path / name
        monkeypatch.setenv("FAKE_CLAUDE_LOG", str(log))
        client = kind(tmp_path, binary=FAKE, model="sonnet")
        data, result = await client.one_shot("mark", schema={"properties": {"verdict": {"type": "string"}}})
        await client.close()
        return data, asdict(result), [json.loads(line) for line in log.read_text().splitlines()]

    async def go():
        original = await scenario(ai.Claude, "original")
        routed = await scenario(tutor_ai.TutorAI, "routed")
        assert routed == original
        assert len(routed[2]) == 2 and "--json-schema" not in routed[2][0] and "--json-schema" in routed[2][1]
    asyncio.run(go())


def test_cloud_only_lifecycle_never_creates_local_client_or_calls_local_hooks(tmp_path, monkeypatch):
    def forbidden(*args, **kwargs):
        raise AssertionError("A cloud-only client must never initialise or invoke local AI.")

    monkeypatch.setattr(tutor_ai, "LocalAI", forbidden)
    monkeypatch.setenv("FAKE_CLAUDE_MODE", "ok")

    async def go():
        client = tutor_ai.TutorAI(tmp_path, binary=FAKE)
        client.on_request = forbidden
        client.on_result = forbidden
        assert client.available
        await client.warm()
        assert (await client.reply("hello")).ok
        data, result = await client.one_shot("mark")
        assert data and result.ok and not result.performance
        await client.reset(warm=False)
        await client.release_local()
        await client.close()
    asyncio.run(go())


def test_releasing_local_client_preserves_live_claude_history_and_usage(tmp_path, monkeypatch):
    monkeypatch.setenv("FAKE_CLAUDE_MODE", "ok")

    async def go():
        client = tutor_ai.TutorAI(tmp_path, binary=FAKE)
        local, closed = client.local, []

        async def close():
            closed.append(True)

        monkeypatch.setattr(local, "close", close)
        assert (await client.reply("first")).text == "Reply 1: first"
        process = client.proc
        await client.release_local()
        assert closed == [True] and client.proc is process and process.returncode is None
        assert client.session.replies == 1
        assert (await client.reply("second")).text == "Reply 2: second"
        assert client.proc is process and client.session.replies == 2
        assert client.local is not local
        await client.close()
    asyncio.run(go())
