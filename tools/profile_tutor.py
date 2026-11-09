#!/usr/bin/env python3
"""Time the tutor's boot and key interactions on a SCRATCH copy of the learner's vault.

    .venv/bin/python tools/profile_tutor.py [--source "<real vault>"] [--scratch DIR] [--cprofile boot|session]
                                            [--steps N] [--json out.json]

The learner's real vault is only ever READ: `.tutor` state, events and settings are copied to a temp dir, the
huge `Library` is symlinked, and STEM_TUTOR_VAULT points at the copy.  Writes by the app land in the copy.
At the end the profiler verifies that nothing under the real vault changed.
"""
from __future__ import annotations

import argparse
import asyncio
import cProfile
import io
import json
import os
import pstats
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "src"), str(ROOT / "app")]
DEFAULT_SOURCE = ROOT.parent / "STEM Tutor"
SKIP_TUTOR = {"engine", "engine.before-topicals-0ff055d56cd7", "tts", "audio", "backups"}
SKIP_ROOT = {"Library", ".tutor", ".DS_Store"}


def build_scratch(source: Path, scratch: Path) -> Path:
    """A disposable vault: learner state and notes copied, Library symlinked (read-only use)."""
    if scratch.exists():
        shutil.rmtree(scratch)
    scratch.mkdir(parents=True)
    # The catalog refuses a symlinked Library, so clone it (APFS copy-on-write: seconds, no extra disk, source untouched).
    cloned = subprocess.run(["cp", "-cR", str(source / "Library"), str(scratch / "Library")], capture_output=True)
    if cloned.returncode:
        shutil.rmtree(scratch / "Library", ignore_errors=True)
        shutil.copytree(source / "Library", scratch / "Library", symlinks=True)
    for entry in source.iterdir():
        if entry.name in SKIP_ROOT:
            continue
        dest = scratch / entry.name
        if entry.is_symlink():
            dest.symlink_to(os.readlink(entry))  # relative links (How It Works.md -> Library/...) resolve in scratch
        elif entry.is_dir():
            shutil.copytree(entry, dest, symlinks=True)
        else:
            shutil.copy2(entry, dest)
    tutor = scratch / ".tutor"
    tutor.mkdir()
    for entry in (source / ".tutor").iterdir():
        if entry.name in SKIP_TUTOR:
            continue
        dest = tutor / entry.name
        if entry.is_symlink():
            dest.symlink_to(os.readlink(entry))
        elif entry.is_dir():
            shutil.copytree(entry, dest, symlinks=True)
        else:
            shutil.copy2(entry, dest)
    return scratch


def snapshot(root: Path) -> dict[str, tuple[int, int]]:
    """(mtime_ns, size) of every file in the real vault outside Library bulk, to prove nothing was written."""
    out = {}
    for base, dirs, files in os.walk(root):
        dirs[:] = [d for d in dirs if d not in ("tts", "Library")]
        for name in files:
            p = os.path.join(base, name)
            try:
                st = os.lstat(p)
            except OSError:
                continue
            out[p] = (st.st_mtime_ns, st.st_size)
    return out


class Lag:
    """Event-loop stall monitor: how long the UI thread was blocked."""

    def __init__(self):
        self.max = 0.0
        self.total = 0.0
        self.stalls = []
        self._task = None

    async def _run(self):
        last = time.perf_counter()
        while True:
            await asyncio.sleep(0.005)
            now = time.perf_counter()
            late = now - last - 0.005
            if late > 0.03:
                self.stalls.append(round(late, 3))
                self.total += late
            self.max = max(self.max, late)
            last = now

    def start(self):
        self._task = asyncio.ensure_future(self._run())

    def reset(self):
        self.max, self.total, self.stalls = 0.0, 0.0, []

    def stop(self):
        if self._task:
            self._task.cancel()


TRACED = [
    "tutorlib.packs:Packs.__init__", "tutorlib.packs:Packs.pack", "tutorlib.topicals:Bank.refresh",
    "tutorlib.session:Tutor.__init__", "tutorlib.session:Tutor._fold", "tutorlib.session:Tutor._recover",
    "tutorlib.session:Tutor.answer", "tutorlib.session:Tutor.start", "tutorlib.session:Tutor.next",
    "tutorlib.session:Tutor._save", "tutorlib.session:Tutor.log", "tutorlib.session:Tutor._sync_almanac",
    "tutorlib.store:write_json", "tutorlib.store:Vault.events", "tutorlib.store:Vault.conflict_copies",
    "tutorlib.report:today_note", "tutorlib.report:week_note", "tutorlib.report:almanac_push",
    "tutorlib.views:write_home", "tutorlib.views:organise_lessons", "tutorlib.policy:plan_session",
    "tutorlib.question_duplicates:Reviews.__init__", "tutorlib.question_duplicates:fingerprint",
    "tutorlib.library_refs:LibraryRefs.content", "tutorlib.asset_library:AssetLibrary.__init__",
    "tutor_app.display_inventory:get_inventory", "tutor_app.screens:HomeScreen.on_mount",
    "tutor_app.screens:HomeScreen.refresh_home", "tutor_app.screens:HomeScreen._refresh_home",
    "tutor_app.screens:HomeScreen._week_in_review", "tutor_app.screens:HomeScreen._draw_stats",
    "tutor_app.screens:HomeScreen._shortcut_lines", "tutor_app.screens:SessionScreen.on_mount",
    "tutor_app.screens:SessionScreen.update_bar", "tutor_app.screens:PickerScreen.on_mount",
    "tutor_app.screens:SettingsScreen.on_mount", "tutor_app.screens:SettingsScreen._refresh_models",
    "tutor_app.app:TutorApp._open_tutor", "tutor_app.app:TutorApp.claude_note",
]
TRACE: dict[str, list] = {}


def install_trace(extra=()):
    """Wrap functions so their inclusive wall time and call counts are reported with --trace."""
    import functools, importlib
    for target in [*TRACED, *extra]:
        mod_name, _, qual = target.partition(":")
        try:
            mod = importlib.import_module(mod_name)
            owner, _, attr = qual.rpartition(".")
            holder = getattr(mod, owner) if owner else mod
            fn = holder.__dict__[attr] if owner else getattr(mod, attr)
        except (ImportError, AttributeError, KeyError):
            continue
        if asyncio.iscoroutinefunction(fn):
            continue
        entry = TRACE.setdefault(target, [0, 0.0])

        def make(fn=fn, entry=entry):
            @functools.wraps(fn)
            def wrapper(*a, **k):
                t = time.perf_counter()
                try:
                    return fn(*a, **k)
                finally:
                    entry[0] += 1
                    entry[1] += time.perf_counter() - t
            return wrapper
        setattr(holder, attr, make())


def print_trace(results):
    rows = sorted(TRACE.items(), key=lambda kv: -kv[1][1])
    print("trace (inclusive wall time, calls):")
    for name, (calls, total) in rows:
        if calls:
            print(f"  {name:<56} {calls:6d} x  {total * 1000:9.1f} ms")
    results["trace"] = {k: {"calls": c, "s": round(t, 4)} for k, (c, t) in TRACE.items() if c}


def stage(results: dict, name: str, seconds: float, **extra):
    results[name] = {"s": round(seconds, 4), **extra}
    print(f"  {name:<46} {seconds * 1000:9.1f} ms" + (f"   {extra}" if extra else ""), flush=True)


def engine_boot(vault_path: Path, results: dict) -> None:
    """The engine alone (what Tutor() does before any UI exists), stage by stage."""
    from tutorlib import packs, store
    from tutorlib.session import Tutor
    from tutor_app import config

    t = time.perf_counter(); config.Settings.load(vault_path); stage(results, "engine: Settings.load", time.perf_counter() - t)
    v = store.Vault(vault_path)
    t = time.perf_counter(); n = sum(1 for _ in v.events()); stage(results, "engine: vault.events() full fold input", time.perf_counter() - t, events=n)
    t = time.perf_counter(); v.last_event_id(); stage(results, "engine: vault.last_event_id()", time.perf_counter() - t)
    t = time.perf_counter(); v.conflict_copies(); stage(results, "engine: vault.conflict_copies()", time.perf_counter() - t)
    t = time.perf_counter(); p = packs.Packs(v); stage(results, "engine: Packs()", time.perf_counter() - t, subtopics=len(p.subtopics))
    t = time.perf_counter()
    for sub in p.subtopics:
        p.pack(sub)
    stage(results, "engine: packs.pack(every chapter)", time.perf_counter() - t)
    t = time.perf_counter(); Tutor(v, one_at_a_time=True); stage(results, "engine: Tutor() total", time.perf_counter() - t)


async def ui_boot(vault_path: Path, results: dict, steps: int, want_cprofile: str | None) -> None:
    from tutor_app.app import TutorApp
    from tutor_app import screens

    prof = cProfile.Profile() if want_cprofile == "boot" else None
    t0 = time.perf_counter()
    app = TutorApp(vault_path, claude_binary="/nonexistent/claude", open_obsidian=False, seed=1)
    app.settings.ai = False
    stage(results, "ui: TutorApp() construct", time.perf_counter() - t0)
    lag = Lag()
    t_run = time.perf_counter()
    if prof:
        prof.enable()
    async with app.run_test(size=(120, 40)) as pilot:
        lag.start()
        t_in = time.perf_counter()
        while not isinstance(app.screen, screens.HomeScreen):
            await asyncio.sleep(0.005)
            if time.perf_counter() - t_in > 120:
                raise SystemExit("Home never appeared")
        stage(results, "ui: first Home screen current", time.perf_counter() - t_run)
        await pilot.pause()
        stage(results, "ui: Home settled (pilot.pause)", time.perf_counter() - t_run)
        deadline = time.perf_counter() + 30
        while app.workers and any(not w.is_finished for w in app.workers) and time.perf_counter() < deadline:
            await asyncio.sleep(0.02)
        stage(results, "ui: boot incl. background workers", time.perf_counter() - t_run, loop_stall_max=round(lag.max, 3),
              loop_stall_total=round(lag.total, 3))
        if prof:
            prof.disable()
            dump(prof, "boot")
        results["boot_stalls"] = list(lag.stalls)

        # ---- keys on Home ----
        times = []
        lag.reset()
        hprof = cProfile.Profile() if want_cprofile == "home" else None
        if hprof:
            hprof.enable()
        for key in (["down", "down", "up", "down", "down", "up", "up", "down"] * 10)[:steps]:
            t = time.perf_counter(); await pilot.press(key); times.append(time.perf_counter() - t)
        if hprof:
            hprof.disable(); dump(hprof, "home")
        stage(results, "home: key press (mean of %d)" % len(times), sum(times) / len(times), worst=round(max(times), 4),
              loop_stall_max=round(lag.max, 3))
        # idle timers: how much event-loop time passes with nothing pressed
        lag.reset(); t = time.perf_counter(); await asyncio.sleep(5.0)
        stage(results, "home: idle 5 s (stall total shows timer cost)", time.perf_counter() - t - 5.0,
              loop_stall_total=round(lag.total, 3), loop_stall_max=round(lag.max, 3))

        # ---- open / close Settings and Help ----
        for key, cls in (("f2", "SettingsScreen"), ("question_mark", "HelpScreen")):
            t = time.perf_counter(); await pilot.press(key); await pilot.pause()
            ok = app.screen.__class__.__name__ == cls
            stage(results, f"home: open {cls}", time.perf_counter() - t, opened=ok)
            if cls == "SettingsScreen":
                lag.reset(); await asyncio.sleep(3.0)
                stage(results, "settings: idle 3 s stall total", lag.total, loop_stall_max=round(lag.max, 3))
            t = time.perf_counter(); await pilot.press("escape"); await pilot.pause()
            stage(results, f"{cls}: close", time.perf_counter() - t, now=app.screen.__class__.__name__)

        # ---- picker -> lesson session ----
        await open_session(app, pilot, results, lag, steps, want_cprofile)
        lag.stop()
        await app.ai.close()


def dump(prof: cProfile.Profile, label: str, n: int = 30) -> None:
    out = io.StringIO()
    pstats.Stats(prof, stream=out).sort_stats("cumulative").print_stats(n)
    path = Path(tempfile.gettempdir()) / f"profile_tutor_{label}.txt"
    path.write_text(out.getvalue())
    prof.dump_stats(str(path.with_suffix(".prof")))  # open with: python -m pstats <file>
    print(f"  cProfile ({label}) written to {path}")


async def open_session(app, pilot, results, lag, steps, want_cprofile):
    from tutor_app.panels import ChoicePanel, ContinuePanel, TickPanel, ValuePanel, TextPanel, WorkedPanel, ChoosePanel, ReflectPanel
    # "Learn a topic" is the 3rd selectable line after "Studied today" and "Today's plan"
    t = time.perf_counter()
    await pilot.press("home")
    app.screen.query_one("#menu").reveal("learn")  # the menu is folders now: open the one holding it
    await pilot.press("enter"); await pilot.pause()
    stage(results, "home: open Learn picker", time.perf_counter() - t, now=app.screen.__class__.__name__)
    t = time.perf_counter()
    for ch in "ener":
        await pilot.press(ch)
    stage(results, "picker: type 4 filter keys", time.perf_counter() - t)
    t = time.perf_counter(); await pilot.press("enter"); await pilot.pause()
    t_start = t
    prof = cProfile.Profile() if want_cprofile == "session" else None
    if prof:
        prof.enable()
    deadline = time.perf_counter() + 40
    while app.screen.__class__.__name__ != "SessionScreen" and time.perf_counter() < deadline:
        await pilot.press("enter") if app.screen.__class__.__name__ == "PickerScreen" else None
        await pilot.pause(0.02)
    stage(results, "picker->SessionScreen mounted", time.perf_counter() - t_start, now=app.screen.__class__.__name__)
    if app.screen.__class__.__name__ != "SessionScreen":
        return
    answers, lat = 0, []
    lag.reset()
    for _ in range(steps * 8):
        scr = app.screen
        if scr.__class__.__name__ == "SummaryScreen":
            break
        panel = next(iter(scr.query("#panel > *")), None) if scr.__class__.__name__ == "SessionScreen" else None
        if panel is None:
            await pilot.pause(0.02)
            continue
        t = time.perf_counter()
        if isinstance(panel, ChoosePanel):
            await pilot.press("down", "enter")
        elif isinstance(panel, ChoicePanel):
            if panel.choice is None:
                await pilot.press("b")
            await pilot.press("3")
        elif isinstance(panel, ValuePanel):
            await pilot.press(*"42", "enter")
            if panel.query("#conf"):
                await pilot.press("2")
        elif isinstance(panel, TickPanel):
            panel.query("Button").first().press()
        elif isinstance(panel, ReflectPanel):
            await pilot.press("1")
        elif isinstance(panel, (WorkedPanel,)):
            await pilot.press("enter")
        elif isinstance(panel, TextPanel):
            await pilot.press(*"it has a direction", "enter")
        elif isinstance(panel, ContinuePanel):
            panel.query("Button").first().press()
        await pilot.pause()
        lat.append(time.perf_counter() - t)
        answers += 1
        if answers >= steps:
            break
    if prof:
        prof.disable(); dump(prof, "session")
    if lat:
        stage(results, "session: panel action+settle (mean of %d)" % len(lat), sum(lat) / len(lat), worst=round(max(lat), 3),
              loop_stall_max=round(lag.max, 3), loop_stall_total=round(lag.total, 3))
    results["session_stalls"] = list(lag.stalls)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--source", type=Path, default=DEFAULT_SOURCE)
    ap.add_argument("--scratch", type=Path, default=Path(tempfile.gettempdir()) / "stem-tutor-profile-vault")
    ap.add_argument("--cprofile", choices=["boot", "home", "session"])
    ap.add_argument("--steps", type=int, default=8)
    ap.add_argument("--json", type=Path)
    ap.add_argument("--skip-ui", action="store_true")
    ap.add_argument("--trace", action="store_true", help="wall time of the key engine/app functions")
    args = ap.parse_args()
    source = args.source.resolve()
    if args.scratch.resolve() == source or source in args.scratch.resolve().parents:
        raise SystemExit("scratch vault must be outside the real vault")
    before = snapshot(source)
    scratch = build_scratch(source, args.scratch)
    os.environ["STEM_TUTOR_VAULT"] = str(scratch)
    os.environ.pop("TERM_PROGRAM", None)  # never restyle a real Terminal tab
    from tutor_app import config
    config.ICLOUD_INBOX = scratch / "_no-ipad-inbox"
    config.DOWNLOADS = scratch / "_no-downloads"
    config.CLAUDE_STATE = scratch / "_no-claude.json"
    print(f"scratch vault: {scratch}")
    results: dict = {}
    if args.trace:
        install_trace()
    print("engine:")
    engine_boot(scratch, results)
    if not args.skip_ui:
        print("ui:")
        asyncio.run(ui_boot(scratch, results, args.steps, args.cprofile))
    if args.trace:
        print_trace(results)
    after = snapshot(source)
    changed = [p for p in set(before) | set(after) if before.get(p) != after.get(p)]
    # the real app may be open meanwhile; report rather than fail
    print("real vault untouched by profiler" if not changed else f"NOTE: {len(changed)} real-vault files changed during run "
          f"(app open elsewhere?): {changed[:5]}")
    results["real_vault_changed"] = changed[:20]
    if args.json:
        args.json.write_text(json.dumps(results, indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main())
