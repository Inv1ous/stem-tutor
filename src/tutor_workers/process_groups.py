"""Cleanup for the app's explicitly owned asynchronous subprocess groups."""
import asyncio
import os
import signal


def own_process_group(proc):
    """Call immediately after launching this Process with start_new_session=True."""
    if os.name == "posix":
        proc._tutor_owned_group = proc.pid
        proc._tutor_group_lock = asyncio.Lock()


def process_group_stopped(proc):
    """Whether cancellation finished the owned group or non-POSIX single process."""
    return (getattr(proc, "_tutor_group_complete", False)
            or os.name != "posix" and proc.returncode is not None)


async def stop_process_group(proc, *, grace):
    group = getattr(proc, "_tutor_owned_group", None)
    lock = getattr(proc, "_tutor_group_lock", None)
    owned = group == proc.pid and lock is not None

    def send(sig):
        try:
            if os.name == "posix":
                os.killpg(proc.pid, sig)
            elif sig == signal.SIGTERM:
                proc.terminate()
            else:
                proc.kill()
        except ProcessLookupError:
            pass
        except PermissionError:
            # A missing leader alone does not prove that its descendants are gone.
            if os.name == "posix":
                try:
                    os.getpgid(proc.pid)
                except ProcessLookupError:
                    try:
                        os.kill(-proc.pid, 0)
                    except ProcessLookupError:
                        return
            raise

    async def finish():
        if owned and proc.returncode is not None:
            # An existing PID after this Process was reaped is no longer our leader.
            try:
                os.getpgid(proc.pid)
            except ProcessLookupError:
                pass
            else:
                raise PermissionError("Cannot establish ownership of the reaped process group.")
        if owned or proc.returncode is None:
            send(signal.SIGKILL)
        await proc.wait()
        if owned:
            proc._tutor_group_complete = True

    async def cleanup():
        if owned and getattr(proc, "_tutor_group_complete", False):
            return
        if proc.returncode is not None:
            if not owned:
                return
        else:
            try:
                send(signal.SIGTERM)
                await asyncio.wait_for(proc.wait(), grace)
            except asyncio.TimeoutError:
                pass
            except asyncio.CancelledError:
                await asyncio.shield(finish())
                raise
        await finish()

    if owned:
        async with lock:
            await cleanup()
    else:
        await cleanup()
