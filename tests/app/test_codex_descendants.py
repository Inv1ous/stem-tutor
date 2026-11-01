"""Owned offline CLI groups must not outlive tutoring cleanup."""
import asyncio
import json
import os
from pathlib import Path
import signal
import time
from types import SimpleNamespace

import pytest


def owned_cli(tmp_path):
    heartbeat = tmp_path / "heartbeat"
    record = tmp_path / "processes.json"
    child = """import signal, sys, time
from pathlib import Path
signal.signal(signal.SIGTERM, signal.SIG_IGN)
path = Path(sys.argv[1])
while True:
    path.write_text(str(time.monotonic_ns()))
    time.sleep(.02)
"""
    path = tmp_path / "fake_codex_group.py"
    path.write_text(f"""#!/usr/bin/env python3
import json, os, subprocess, sys, time
from pathlib import Path
sys.stdin.read()
heartbeat = Path({str(heartbeat)!r})
child = subprocess.Popen([sys.executable, '-c', {child!r}, str(heartbeat)],
                         stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
while not heartbeat.exists():
    time.sleep(.005)
Path({str(record)!r}).write_text(json.dumps({{'parent': os.getpid(), 'child': child.pid,
                                           'group': os.getpgid(0)}}))
print(json.dumps({{'type': 'item.completed', 'item': {{'type': 'agent_message',
                                                  'text': 'Offline reply.'}}}}), flush=True)
if os.environ['FAKE_GROUP_ENTRY'] == 'reaped':
    print(json.dumps({{'type': 'turn.completed'}}), flush=True)
else:
    time.sleep(30)
""")
    path.chmod(0o755)
    return path, heartbeat, record


@pytest.mark.skipif(os.name != "posix", reason="POSIX owned process-group cleanup")
@pytest.mark.parametrize("entry", ["alive", "reaped"])
def test_public_cleanup_stops_resistant_descendant_after_leader_exit(tmp_path, monkeypatch, entry):
    from tutor_app import codex_ai

    fake, heartbeat, record = owned_cli(tmp_path)
    monkeypatch.setenv("FAKE_GROUP_ENTRY", entry)
    client = codex_ai.CodexAI("Offline process cleanup", binary=str(fake))
    original_launch, original_signal = asyncio.create_subprocess_exec, os.killpg
    processes, signals = [], []

    async def launch(*args, **kwargs):
        assert kwargs['start_new_session'] is True
        proc = await original_launch(*args, **kwargs)
        processes.append(proc)
        return proc

    def send(group, sig):
        signals.append((group, sig))
        return original_signal(group, sig)

    monkeypatch.setattr(codex_ai.asyncio, "create_subprocess_exec", launch)
    monkeypatch.setattr(codex_ai.os, "killpg", send)

    async def go():
        reply = client.stream("offline", model="codex:gpt-6.1-sol")
        try:
            if entry == "alive":
                assert await anext(reply) == "Offline reply."
                assert processes[0].returncode is None
            else:
                assert [part async for part in reply] == ["Offline reply."]
                assert client.last.ok and processes[0].returncode == 0
            await asyncio.wait_for(client.close(), 5)
            await reply.aclose()
            info = json.loads(record.read_text())
            assert info['parent'] == info['group'] == processes[0].pid
            before = heartbeat.stat().st_mtime_ns
            await asyncio.sleep(.12)
            assert heartbeat.stat().st_mtime_ns == before, "owned descendant is still running"
            assert processes[0].returncode is not None and not client._procs
            sent = list(signals)
            await client.close()
            await client._stop(processes[0])
            assert signals == sent, "completed cleanup must not re-signal a reused group number"
        finally:
            if record.exists():
                info = json.loads(record.read_text())
                try:
                    if os.getpgid(info['child']) == info['group']:
                        original_signal(info['group'], signal.SIGKILL)
                except ProcessLookupError:
                    pass
            for proc in processes:
                if proc.returncode is None:
                    try:
                        original_signal(proc.pid, signal.SIGKILL)
                    except ProcessLookupError:
                        pass
                await asyncio.wait_for(proc.wait(), 3)
            await reply.aclose()
            await client.close()

    asyncio.run(go())


def test_already_reaped_unowned_process_never_signals_a_numeric_group(monkeypatch):
    from tutor_app.codex_ai import CodexAI

    class Reaped:
        pid = 123456789
        returncode = 0

    def forbidden(*args):
        pytest.fail("unowned exited PID must not be signalled")

    monkeypatch.setattr(os, "killpg", forbidden)
    asyncio.run(CodexAI._stop(Reaped()))


@pytest.mark.skipif(os.name != "posix", reason="POSIX owned process-group cleanup")
def test_concurrent_close_reset_and_finalizer_wait_for_owned_cleanup(tmp_path, monkeypatch):
    from tutor_app import codex_ai

    fake, heartbeat, record = owned_cli(tmp_path)
    monkeypatch.setenv("FAKE_GROUP_ENTRY", "alive")
    client = codex_ai.CodexAI("Offline process cleanup", binary=str(fake))
    original_launch, original_signal = asyncio.create_subprocess_exec, os.killpg

    async def go():
        paused, release = asyncio.Event(), asyncio.Event()
        processes, tasks = [], []

        async def launch(*args, **kwargs):
            proc = await original_launch(*args, **kwargs)
            wait, first = proc.wait, True

            async def delayed_wait():
                nonlocal first
                result = await wait()
                if first:
                    first = False
                    paused.set()
                    await release.wait()
                return result

            proc.wait = delayed_wait
            processes.append(proc)
            return proc

        monkeypatch.setattr(codex_ai.asyncio, "create_subprocess_exec", launch)
        reply = client.stream("offline", model="codex:gpt-6.1-sol")
        try:
            assert await anext(reply) == "Offline reply."
            tasks.append(asyncio.create_task(client.close()))
            await asyncio.wait_for(paused.wait(), 3)
            tasks.extend([asyncio.create_task(client.reset()), asyncio.create_task(reply.aclose())])
            await asyncio.sleep(.04)
            assert all(not task.done() for task in tasks), "concurrent cleanup returned before reaping finished"
            release.set()
            await asyncio.wait_for(asyncio.gather(*tasks), 5)
            before = heartbeat.stat().st_mtime_ns
            await asyncio.sleep(.12)
            assert heartbeat.stat().st_mtime_ns == before
            assert not client._procs
        finally:
            release.set()
            await asyncio.gather(*tasks, return_exceptions=True)
            if record.exists():
                info = json.loads(record.read_text())
                try:
                    if os.getpgid(info['child']) == info['group']:
                        original_signal(info['group'], signal.SIGKILL)
                except ProcessLookupError:
                    pass
            for proc in processes:
                if proc.returncode is None:
                    try:
                        original_signal(proc.pid, signal.SIGKILL)
                    except ProcessLookupError:
                        pass
                await asyncio.wait_for(proc.wait(), 3)
            await reply.aclose()
            await client.close()

    asyncio.run(go())


@pytest.mark.skipif(os.name != "posix", reason="POSIX owned process-group cleanup")
@pytest.mark.parametrize("probe", ["reused", "indeterminate"])
def test_reaped_owned_group_with_uncertain_current_pid_refuses_without_signalling(monkeypatch, probe):
    from tutor_app.codex_ai import CodexAI

    class Reaped:
        pid = 123456789
        returncode = 0
        _tutor_owned_group = pid

    def group(pid):
        if probe == "indeterminate":
            raise PermissionError("cannot establish current PID identity")
        return pid

    def forbidden(*args):
        pytest.fail("uncertain reaped group must not be signalled")

    monkeypatch.setattr(os, "getpgid", group)
    monkeypatch.setattr(os, "killpg", forbidden)

    async def go():
        proc = Reaped()
        proc._tutor_group_lock = asyncio.Lock()
        with pytest.raises(PermissionError):
            await CodexAI._stop(proc)

    asyncio.run(go())


@pytest.mark.skipif(os.name != "posix", reason="POSIX owned process-group cleanup")
def test_reaped_leader_with_live_descendant_does_not_hide_group_permission_denial(tmp_path, monkeypatch):
    from tutor_app import codex_ai

    fake, heartbeat, record = owned_cli(tmp_path)
    monkeypatch.setenv("FAKE_GROUP_ENTRY", "reaped")
    client = codex_ai.CodexAI("Offline process cleanup", binary=str(fake))
    original_signal = os.killpg
    denial = PermissionError("owned group still contains a live descendant")

    def denied(group, sig):
        assert sig == signal.SIGKILL
        raise denial

    monkeypatch.setattr(os, "killpg", denied)

    async def go():
        try:
            _ = [part async for part in client.stream("offline", model="codex:gpt-6.1-sol")]
            assert not client.last.ok and client._procs
            proc = next(iter(client._procs))
            assert proc.returncode == 0 and not getattr(proc, "_tutor_group_complete", False)
            with pytest.raises(PermissionError) as error:
                await client.close()
            assert error.value is denial
            info = json.loads(record.read_text())
            assert os.getpgid(info['child']) == info['group'] == proc.pid
            before = heartbeat.stat().st_mtime_ns
            await asyncio.sleep(.08)
            assert heartbeat.stat().st_mtime_ns > before
            monkeypatch.setattr(os, "killpg", original_signal)
            await client.close()
            before = heartbeat.stat().st_mtime_ns
            await asyncio.sleep(.08)
            assert heartbeat.stat().st_mtime_ns == before and not client._procs
        finally:
            monkeypatch.setattr(os, "killpg", original_signal)
            if record.exists():
                info = json.loads(record.read_text())
                try:
                    if os.getpgid(info['child']) == info['group']:
                        original_signal(info['group'], signal.SIGKILL)
                except ProcessLookupError:
                    pass
            # The intentionally denied cleanup may still report a zombie-only group as uncertain.
            await asyncio.gather(client.close(), return_exceptions=True)

    asyncio.run(go())


@pytest.mark.skipif(os.name != "posix", reason="POSIX owned process-group cleanup")
@pytest.mark.parametrize("entry", ["alive", "reaped"])
def test_native_ocr_launcher_cleans_the_same_owned_resistant_group(tmp_path, monkeypatch, entry):
    from tutor_app.local_ocr import NativeOCR

    fake, heartbeat, record = owned_cli(tmp_path)
    monkeypatch.setenv("FAKE_GROUP_ENTRY", entry)
    client = NativeOCR(compiler="unused-offline-compiler")
    original_signal = os.killpg

    async def go():
        task = asyncio.create_task(client._run([str(fake)], time.monotonic() + 5, client._generation, b""))
        try:
            if entry == "alive":
                for _ in range(400):
                    if record.exists():
                        break
                    await asyncio.sleep(.005)
                assert record.exists()
                await asyncio.wait_for(client.close(), 3)
                await asyncio.gather(task, return_exceptions=True)
            else:
                assert b"Offline reply." in await asyncio.wait_for(task, 3)
            before = heartbeat.stat().st_mtime_ns
            await asyncio.sleep(.12)
            assert heartbeat.stat().st_mtime_ns == before
            assert not client._procs
            await client.close()
        finally:
            if record.exists():
                info = json.loads(record.read_text())
                try:
                    if os.getpgid(info['child']) == info['group']:
                        original_signal(info['group'], signal.SIGKILL)
                except ProcessLookupError:
                    pass
            task.cancel()
            await asyncio.gather(task, return_exceptions=True)
            await client.close()

    asyncio.run(go())


@pytest.mark.skipif(os.name != "posix", reason="POSIX process-group existence proof")
@pytest.mark.parametrize("group_state", ["live", "denied", "indeterminate"])
def test_missing_leader_does_not_hide_a_live_or_indeterminate_group(monkeypatch, group_state):
    from tutor_app.codex_ai import CodexAI

    class Process:
        pid = 123456789
        returncode = None

        async def wait(self):
            pytest.fail("unproven cleanup must not be reported as reaped")

    def denied(*args):
        raise PermissionError("group signal denied")

    def missing(pid):
        raise ProcessLookupError("leader gone")

    def group_probe(pid, sig):
        assert (pid, sig) == (-Process.pid, 0)
        if group_state == "denied":
            raise PermissionError("group existence denied")
        if group_state == "indeterminate":
            raise OSError("group existence unavailable")

    monkeypatch.setattr(os, "killpg", denied)
    monkeypatch.setattr(os, "getpgid", missing)
    monkeypatch.setattr(os, "kill", group_probe)

    with pytest.raises(OSError):
        asyncio.run(CodexAI._stop(Process()))


@pytest.mark.skipif(os.name != "posix", reason="POSIX owned process-group cleanup")
@pytest.mark.parametrize("route", ["run", "abandoned-launch"])
def test_native_denied_cleanup_retains_ownership_for_same_client_retry(tmp_path, monkeypatch, route):
    from tutor_app import local_ocr

    fake, heartbeat, record = owned_cli(tmp_path)
    monkeypatch.setenv("FAKE_GROUP_ENTRY", "reaped")
    client = local_ocr.NativeOCR(compiler="unused-offline-compiler")
    original_launch, original_signal = asyncio.create_subprocess_exec, os.killpg
    denial = PermissionError("live owned group cleanup denied")

    def denied(group, sig):
        assert sig == signal.SIGKILL
        raise denial

    monkeypatch.setattr(os, "killpg", denied)

    async def go():
        launched, release = asyncio.Event(), asyncio.Event()
        task = None

        async def delayed(*args, **kwargs):
            proc = await original_launch(*args, **kwargs)
            proc.stdin.close()
            await proc.wait()
            launched.set()
            await release.wait()
            return proc

        try:
            if route == "run":
                with pytest.raises(PermissionError) as error:
                    await client._run([str(fake)], time.monotonic() + 5, client._generation, b"")
                assert error.value is denial
            else:
                monkeypatch.setattr(local_ocr.asyncio, "create_subprocess_exec", delayed)
                task = asyncio.create_task(client._run([str(fake)], time.monotonic() + 5,
                                                       client._generation, b""))
                await asyncio.wait_for(launched.wait(), 3)
                task.cancel()
                with pytest.raises(asyncio.CancelledError):
                    await task
                release.set()
                await asyncio.gather(*tuple(client._starting), return_exceptions=True)
            assert client._procs, "failed cleanup must retain ownership for retry"
            proc = next(iter(client._procs))
            assert not getattr(proc, "_tutor_group_complete", False)
            info = json.loads(record.read_text())
            assert os.getpgid(info['child']) == info['group'] == proc.pid
            monkeypatch.setattr(os, "killpg", original_signal)
            await client.close()
            before = heartbeat.stat().st_mtime_ns
            await asyncio.sleep(.12)
            assert heartbeat.stat().st_mtime_ns == before
            assert not client._procs
        finally:
            release.set()
            monkeypatch.setattr(os, "killpg", original_signal)
            if record.exists():
                info = json.loads(record.read_text())
                try:
                    if os.getpgid(info['child']) == info['group']:
                        original_signal(info['group'], signal.SIGKILL)
                except ProcessLookupError:
                    pass
            if task is not None:
                task.cancel()
                await asyncio.gather(task, return_exceptions=True)
            await asyncio.gather(client.close(), return_exceptions=True)

    asyncio.run(go())


@pytest.mark.skipif(os.name != "posix", reason="POSIX owned process-group cleanup")
@pytest.mark.parametrize("adapter", ["codex", "native"])
def test_close_exposes_owned_cleanup_denial_from_a_late_launch(tmp_path, monkeypatch, adapter):
    from tutor_app import codex_ai, local_ocr

    fake, heartbeat, record = owned_cli(tmp_path)
    monkeypatch.setenv("FAKE_GROUP_ENTRY", "reaped")
    client = (codex_ai.CodexAI("Offline process cleanup", binary=str(fake)) if adapter == "codex"
              else local_ocr.NativeOCR(compiler="unused-offline-compiler"))
    original_launch, original_signal = asyncio.create_subprocess_exec, os.killpg
    denial = PermissionError("late owned group cleanup denied")

    def denied(group, sig):
        assert sig == signal.SIGKILL
        raise denial

    monkeypatch.setattr(os, "killpg", denied)

    async def go():
        launched, release = asyncio.Event(), asyncio.Event()
        task = closing = None

        async def delayed(*args, **kwargs):
            proc = await original_launch(*args, **kwargs)
            proc.stdin.close()
            await proc.wait()
            launched.set()
            await release.wait()
            return proc

        monkeypatch.setattr(asyncio, "create_subprocess_exec", delayed)
        try:
            work = (client.one_shot("offline", model="codex:gpt-6.1-sol", timeout=5)
                    if adapter == "codex" else
                    client._run([str(fake)], time.monotonic() + 5, client._generation, b""))
            task = asyncio.create_task(work)
            await asyncio.wait_for(launched.wait(), 3)
            task.cancel()
            with pytest.raises(asyncio.CancelledError):
                await task
            closing = asyncio.create_task(client.close())
            await asyncio.sleep(.02)
            assert not closing.done()
            release.set()
            with pytest.raises(PermissionError) as error:
                await asyncio.wait_for(closing, 3)
            assert error.value is denial and client._procs
            monkeypatch.setattr(os, "killpg", original_signal)
            await client.close()
            before = heartbeat.stat().st_mtime_ns
            await asyncio.sleep(.12)
            assert heartbeat.stat().st_mtime_ns == before and not client._procs
        finally:
            release.set()
            monkeypatch.setattr(os, "killpg", original_signal)
            if record.exists():
                info = json.loads(record.read_text())
                try:
                    if os.getpgid(info['child']) == info['group']:
                        original_signal(info['group'], signal.SIGKILL)
                except ProcessLookupError:
                    pass
            await asyncio.gather(*(item for item in (task, closing) if item is not None),
                                 return_exceptions=True)
            await asyncio.gather(client.close(), return_exceptions=True)

    asyncio.run(go())


def test_native_completed_nonposix_cancellation_releases_the_reaped_process(monkeypatch):
    from tutor_app import local_ocr
    from tutor_workers import process_groups

    class Process:
        pid = 123456789
        returncode = None
        waits = 0
        signals = []

        async def communicate(self, image):
            return b"offline literal text", None

        def terminate(self):
            self.signals.append("term")

        def kill(self):
            self.signals.append("kill")

        async def wait(self):
            self.waits += 1
            if self.waits == 1:
                raise asyncio.CancelledError
            self.returncode = 0
            return 0

    proc = Process()

    async def launch(*args, **kwargs):
        return proc

    monkeypatch.setattr(process_groups, "os", SimpleNamespace(name="nt"))
    monkeypatch.setattr(local_ocr.asyncio, "create_subprocess_exec", launch)

    async def go():
        client = local_ocr.NativeOCR(compiler="unused-offline-compiler")
        with pytest.raises(asyncio.CancelledError):
            await client._run(["offline fake process"], time.monotonic() + 5, client._generation, b"")
        assert proc.returncode == 0 and proc.waits == 2 and proc.signals == ["term", "kill"]
        assert not client._procs
        await client.close()

    asyncio.run(go())
