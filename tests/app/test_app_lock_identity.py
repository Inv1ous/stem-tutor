"""App startup respects a separate process's lock on the physical learner vault."""
import asyncio
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

from fixtures import make_vault
from test_tui import FAKE, app_for, shot
from tutor_app.app import TutorApp


@pytest.mark.parametrize("route", ["same", "case", "other"])
def test_startup_refuses_a_locked_physical_vault_but_allows_a_distinct_vault(tmp_path, monkeypatch, route):
    app, vault = app_for(tmp_path, monkeypatch)
    candidate, same = vault, True
    if route == "case":
        candidate = vault.with_name(vault.name.lower())
        if not candidate.exists():  # case-sensitive filesystem: these are independent vaults
            shutil.copytree(vault, candidate)
        same = candidate.samefile(vault)
        app = TutorApp(candidate, claude_binary=FAKE, open_obsidian=False)
    elif route == "other":
        candidate, same = make_vault(tmp_path / "other"), False
        app = TutorApp(candidate, claude_binary=FAKE, open_obsidian=False)
    assert candidate.samefile(vault) is same
    app.settings.ai = False
    messages = []
    exit_app = app.exit

    def record_exit(*args, **kwargs):
        messages.append(kwargs.get("message"))
        exit_app(*args, **kwargs)

    monkeypatch.setattr(app, "exit", record_exit)
    hold = ("import sys\n"
            "sys.path.insert(0, sys.argv[1])\n"
            "from tutorlib import store\n"
            "with store.Vault(sys.argv[2]).lock(wait_seconds=0.1):\n"
            "    print('held', flush=True)\n"
            "    sys.stdin.read()\n")
    child = subprocess.Popen([sys.executable, "-u", "-c", hold, str(Path(__file__).resolve().parents[2] / "src"), str(vault)],
                             stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    try:
        assert child.stdout.readline().strip() == "held"

        async def go():
            async with app.run_test(size=(100, 30)) as pilot:
                await pilot.pause()
                if hasattr(app, "tutor"):
                    await shot(pilot, f"startup-lock-{route}-{'same-physical' if same else 'distinct'}")
                if same:
                    assert not hasattr(app, "tutor")
                    assert any("Another STEM Tutor window is already open" in str(message) for message in messages)
                else:
                    assert app.is_running and app.screen.__class__.__name__ == "HomeScreen"
                    assert not messages
                    await app.ai.close()
                assert child.poll() is None  # refusing/starting the app never releases the other writer's lock

        asyncio.run(go())
    finally:
        child.stdin.close()
        child.wait(timeout=5)
        child.stdout.close()
        child.stderr.close()
