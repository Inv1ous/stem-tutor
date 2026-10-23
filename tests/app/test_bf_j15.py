from __future__ import annotations

import asyncio
import json
from pathlib import Path

import pytest

from tutor_app import ai


class Process:
    def __init__(self) -> None:
        self.stdin = self
        self.stdout = asyncio.StreamReader()
        self.returncode = None
        self.messages: list[str] = []

    def write(self, data: bytes) -> None:
        prompt = json.loads(data)["message"]["content"]
        self.messages.append(prompt)
        self.stdout.feed_data((json.dumps({"type": "result", "result": prompt}) + "\n").encode())

    async def drain(self) -> None:
        pass

    def close(self) -> None:
        self.returncode = 0
        self.stdout.feed_eof()

    async def wait(self) -> int:
        return self.returncode

    def kill(self) -> None:
        self.close()


@pytest.mark.parametrize("startup", ["reply", "warm"])
def test_a_new_conversation_forgets_a_process_still_starting(tmp_path: Path, monkeypatch, startup: str) -> None:
    """B-083 (bug watch): reset during startup must not keep the old conversation for the next prompt."""
    async def go() -> None:
        started, release, resetting = asyncio.Event(), asyncio.Event(), asyncio.Event()
        processes: list[Process] = []

        async def start(*args, **kwargs) -> Process:
            proc = Process()
            processes.append(proc)
            if len(processes) == 1:
                started.set()
                await release.wait()
            return proc

        monkeypatch.setattr(asyncio, "create_subprocess_exec", start)
        client = ai.Claude(tmp_path, binary=str(Path(__file__).with_name("fake_claude.py")))

        async def reset() -> None:
            resetting.set()
            await client.reset(warm=False)

        old = asyncio.create_task(client.reply("old session question") if startup == "reply" else client.warm())
        await asyncio.wait_for(started.wait(), 1)
        reset_task = asyncio.create_task(reset())
        await asyncio.wait_for(resetting.wait(), 1)
        release.set()
        try:
            await asyncio.wait_for(asyncio.gather(old, reset_task), 1)
            assert not client.procs, "Reset retained a process that was still starting"
            assert processes[0].returncode is not None
            reply = await asyncio.wait_for(client.reply("new session question"), 1)
            assert reply.ok and reply.text == "new session question"
            assert len(processes) == 2
            assert processes[1].messages == ["new session question"]
        finally:
            await client.close()

    asyncio.run(go())
