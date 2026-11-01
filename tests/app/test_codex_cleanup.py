"""Offline process cleanup controls for Codex's rapid-exit race."""
import asyncio
import json
import os
from pathlib import Path
import signal

import pytest


@pytest.mark.skipif(os.name != "posix", reason="POSIX process-group cleanup")
@pytest.mark.parametrize("phase", ["term", "kill"])
@pytest.mark.parametrize("exists", [False, True])
def test_group_denial_requires_a_fresh_missing_process_probe(monkeypatch, phase, exists):
    from tutor_app.codex_ai import CodexAI

    class Process:
        pid = 123456789
        returncode = None
        waits = 0

        async def wait(self):
            self.waits += 1
            if phase == "kill" and self.waits == 1:
                raise asyncio.TimeoutError
            self.returncode = 0
            return 0

    denied = PermissionError("group signal denied")
    signals, probes = [], []

    def send(pid, sig):
        signals.append((pid, sig))
        if phase == "term" or sig == signal.SIGKILL:
            raise denied

    def group(pid):
        probes.append(pid)
        if not exists:
            raise ProcessLookupError("owned child has exited")
        return pid

    monkeypatch.setattr(os, "killpg", send)
    monkeypatch.setattr(os, "getpgid", group)

    async def go():
        proc = Process()
        if exists:
            with pytest.raises(PermissionError) as error:
                await CodexAI._stop(proc)
            assert error.value is denied and proc.returncode is None
        else:
            await CodexAI._stop(proc)
            assert proc.returncode == 0
        if not exists:
            assert probes == [proc.pid]
        assert [sig for _, sig in signals] == ([signal.SIGTERM] if phase == "term"
                                               else [signal.SIGTERM, signal.SIGKILL])

    asyncio.run(go())


@pytest.mark.skipif(os.name != "posix", reason="POSIX process-group cleanup")
@pytest.mark.parametrize("timeout", [False, True])
def test_ordinary_group_termination_still_escalates_and_reaps(monkeypatch, timeout):
    from tutor_app.codex_ai import CodexAI

    class Process:
        pid = 123456789
        returncode = None
        waits = 0

        async def wait(self):
            self.waits += 1
            if timeout and self.waits == 1:
                raise asyncio.TimeoutError
            self.returncode = 0
            return 0

    signals = []
    monkeypatch.setattr(os, "killpg", lambda pid, sig: signals.append((pid, sig)))

    async def go():
        proc = Process()
        await CodexAI._stop(proc)
        await CodexAI._stop(proc)
        assert proc.returncode == 0
        assert [sig for _, sig in signals] == ([signal.SIGTERM, signal.SIGKILL] if timeout
                                               else [signal.SIGTERM])

    asyncio.run(go())


@pytest.mark.skipif(os.name != "posix", reason="POSIX process-group exit race")
def test_unreadable_reply_reaps_confirmed_exited_child_and_close_is_idempotent(tmp_path, monkeypatch):
    from tutor_app import codex_ai

    fake = str(Path(__file__).with_name("fake_codex.py"))
    monkeypatch.setenv("FAKE_CODEX_LOG", str(tmp_path / "requests.jsonl"))
    monkeypatch.setenv("FAKE_CODEX_MODE", "unreadable")
    client = codex_ai.CodexAI("Tutor instructions", binary=fake)
    original = asyncio.create_subprocess_exec
    processes = []

    class StaleStatus:
        """Expose a stale asyncio status after the actual offline child has exited."""
        def __init__(self, proc):
            self.proc, self.pid, self.stdin = proc, proc.pid, proc.stdin
            self.stdout = self
            self.returncode = None

        async def readline(self):
            line = await self.proc.stdout.readline()
            if line == b"not JSON\n":
                await self.proc.wait()
            return line

        async def wait(self):
            self.returncode = await self.proc.wait()
            return self.returncode

    async def launch(*args, **kwargs):
        proc = StaleStatus(await original(*args, **kwargs))
        processes.append(proc)
        return proc

    def denied(pid, sig):
        assert any(proc.pid == pid and proc.proc.returncode is not None for proc in processes)
        raise PermissionError("exited process group")

    monkeypatch.setattr(codex_ai.asyncio, "create_subprocess_exec", launch)
    monkeypatch.setattr(codex_ai.os, "killpg", denied)

    async def go():
        assert [s async for s in client.stream("failed", model="codex:gpt-6.1-sol")] == []
        assert not client.last.ok and client.last.status == "error" and client.last.message
        await client.close()
        await client.close()
        assert not client._procs and not client._history
        assert len(processes) == 1 and processes[0].returncode == 1

    asyncio.run(go())


def test_actual_rapid_exit_replies_leave_no_pending_child_or_history(tmp_path, monkeypatch):
    from tutor_app.codex_ai import CodexAI

    fake = str(Path(__file__).with_name("fake_codex.py"))
    log = tmp_path / "requests.jsonl"
    monkeypatch.setenv("FAKE_CODEX_LOG", str(log))
    monkeypatch.setenv("FAKE_CODEX_MODE", "unreadable")
    client = CodexAI("Tutor instructions", binary=fake)
    original_stop, cleanup_errors = client._stop, []

    def probe(call):
        try:
            return {"result": call()}
        except OSError as error:
            return {"exception": type(error).__name__, "errno": error.errno, "message": str(error)}

    async def observed_stop(proc):
        try:
            await original_stop(proc)
        except BaseException as error:
            cleanup_errors.append({"exception": type(error).__name__, "message": str(error),
                                   "pid": proc.pid, "returncode": proc.returncode,
                                   "owned_group": getattr(proc, "_tutor_owned_group", None),
                                   "completed": getattr(proc, "_tutor_group_complete", False),
                                   "pid_probe": probe(lambda: os.getpgid(proc.pid)),
                                   "group_probe": probe(lambda: os.kill(-proc.pid, 0))})
            raise

    monkeypatch.setattr(client, "_stop", observed_stop)

    async def go():
        try:
            for _ in range(12):
                assert [s async for s in client.stream("failed", model="codex:gpt-6.1-sol")] == []
                assert not client.last.ok and client.last.message
                assert not client._procs and not client._history, json.dumps(cleanup_errors)
            await client.close()
            await client.close()
        finally:
            await asyncio.gather(client.close(), return_exceptions=True)

    asyncio.run(go())
    assert len([json.loads(line) for line in log.read_text().splitlines()]) == 12
