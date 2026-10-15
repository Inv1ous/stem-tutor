#!/usr/bin/env python3
"""Pre-generate the read-aloud audio of signed chapters (shared by the foundry and refine).

Every line a chapter can say (teaching cards, question stems, explanations and hints, note paragraphs) is turned into
spoken English by tutorlib.speech and, when Kokoro is set up, into a WAV in the learner's audio cache
(<vault>/.tutor/audio/<key>.wav, key = tutorlib.speech.audio_key(text, voice, speed)). The tutor app looks lines up by
the same key, so a pre-generated line plays at once. Costs only local CPU, never an allowance.

  pregen.py tts <subtopic…|--all> [--voice V] [--speed S]   make the audio now (--all: every built chapter, in turn)
  pregen.py tts status                                      per chapter: lines, with audio, missing, gaps
  pregen.py run <subtopic>                                  what the sign hook runs in the background

The script of each chapter is always written to build/out/speech/<sub>.json, even when Kokoro is not set up, so it can be
read and its gaps (maths with no sensible spoken form) seen. Gaps are shown, never a gate: add a `speech` field.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Callable

REPO = Path(__file__).resolve().parents[1]
for _p in (REPO / "plugin/stem-tutor/skills/tutor/scripts", REPO / "app"):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

DEFAULT_VOICE, DEFAULT_SPEED = "bf_emma", 1.0
NOT_SET_UP = "speech: not set up (run tutor tts setup)"


def root() -> Path:
    return Path(os.environ.get("FOUNDRY_ROOT", REPO))


def _tts():
    from tutor_app import tts
    return tts


def _speech():
    from tutorlib import speech
    return speech


def vault() -> Path:
    """The vault the app reads (the one a sign publishes into)."""
    return Path(os.environ.get("STEM_TUTOR_VAULT") or root().parent / "STEM Tutor")


def settings(v: Path | None = None) -> tuple[str, float]:
    """Voice and speed from the learner's app settings (bf_emma / 1.0 when there are none)."""
    v = v or vault()
    try:
        if (v / ".tutor").is_dir():
            from tutor_app import config
            s = config.Settings.load(v)
            return s.tts_voice or DEFAULT_VOICE, float(s.tts_speed or DEFAULT_SPEED)
    except Exception:  # noqa: BLE001 - unreadable settings: the defaults
        pass
    return DEFAULT_VOICE, DEFAULT_SPEED


def audio_dir(v: Path | None = None) -> Path:
    return _tts().audio_dir(v or vault())


def spec_of(sub: str) -> str:
    return sub.split("-", 1)[0]


def pack_path(sub: str) -> Path:
    return root() / "build/out/packs" / spec_of(sub) / f"{sub}.json"


def script_path(sub: str) -> Path:
    return root() / "build/out/speech" / f"{sub}.json"


def built() -> list[str]:
    """Every chapter that has a pack, in natural order."""
    import re
    subs = [p.stem for p in (root() / "build/out/packs").glob("*/*.json") if p.stem != "HOLD"]
    return sorted(subs, key=lambda s: [int(x) if x.isdigit() else x for x in re.split(r"(\d+)", s)])


# ---------------- the chapter's lines ----------------
def _read(sub: str) -> tuple[dict, str]:
    pack = json.loads(pack_path(sub).read_text(encoding="utf-8"))
    note = root() / "build/out/notes" / (pack.get("note") or "")
    return pack, note.read_text(encoding="utf-8") if pack.get("note") and note.is_file() else ""


def chapter_lines(sub: str) -> list[dict]:
    """The spoken lines of a signed chapter: [{"id", "text"}] (tutorlib.speech.script_for_chapter)."""
    pack, note = _read(sub)
    return _speech().script_for_chapter(pack, note)


def _sources(pack: dict, note: str) -> tuple[dict[str, str], set[str]]:
    """id -> the written source of each line (to find its gaps), and the ids an author gave a `speech` override."""
    sp = _speech()
    src: dict[str, str] = {}
    over: set[str] = set()
    for kc, card in (pack.get("teach") or {}).items():
        if not isinstance(card, dict):
            continue
        ov = card.get("speech") if isinstance(card.get("speech"), dict) else {}
        for field in sp._CARD_FIELDS:
            val = card.get(field)
            if isinstance(val, dict):
                val = " ".join(sp._flat_strings(val))
            if isinstance(val, str):
                src[f"card:{kc}:{field}"] = val
            if ov.get(field):
                over.add(f"card:{kc}:{field}")
    for it in pack.get("items") or []:
        if not isinstance(it, dict) or not it.get("id"):
            continue
        iid, s = it["id"], it.get("speech")
        ov = s if isinstance(s, dict) else ({"stem": s} if isinstance(s, str) else {})
        parts = [("stem", it.get("stem")), ("explanation", it.get("explanation"))]
        parts += [(f"hint{n}", h) for n, h in enumerate(it.get("hints") or [], 1)]
        for name, val in parts:
            if isinstance(val, str):
                src[f"item:{iid}:{name}"] = val
            if ov.get(name):
                over.add(f"item:{iid}:{name}")
    n = 0
    for para in sp.note_paragraphs(note):
        if sp.for_tts(para):
            n += 1
            src[f"note:{n}"] = para
    return src, over


def line_gaps(sub: str, lines: list[dict] | None = None) -> dict[str, list[str]]:
    """id -> symbols with no natural spoken form, for the lines that have some (an override has none)."""
    pack, note = _read(sub)
    src, over = _sources(pack, note)
    ids = {ln["id"] for ln in (lines if lines is not None else _speech().script_for_chapter(pack, note))}
    out = {}
    for lid in ids:
        if lid in over or lid not in src:
            continue
        gaps = _speech().speech_gaps(src[lid])
        if gaps:
            out[lid] = gaps
    return out


def _key(text: str, voice: str, speed: float) -> str:
    return _speech().audio_key(text, voice, speed)


def write_script(sub: str, voice: str, speed: float, lines: list[dict], gaps: dict[str, list[str]]) -> Path:
    rows = [{"id": ln["id"], "text": ln["text"], "key": (k := _key(ln["text"], voice, speed)), "file": f"{k}.wav",
             **({"gaps": gaps[ln["id"]]} if ln["id"] in gaps else {})} for ln in lines]
    path = script_path(sub)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps({"sub": sub, "voice": voice, "speed": speed, "lines": rows}, ensure_ascii=False, indent=1),
                   encoding="utf-8")
    tmp.replace(path)
    return path


def script(sub: str, voice: str, speed: float, fresh: bool = False) -> dict:
    """The chapter's stored script, rebuilt when missing or older than the pack and the note (or `fresh`)."""
    path = script_path(sub)
    if not fresh and path.is_file():
        pack = pack_path(sub)
        stamps = [pack.stat().st_mtime]
        try:
            note = root() / "build/out/notes" / json.loads(pack.read_text(encoding="utf-8")).get("note", "")
            stamps.append(note.stat().st_mtime) if note.is_file() else None
            if path.stat().st_mtime >= max(stamps):
                data = json.loads(path.read_text(encoding="utf-8"))
                for row in data["lines"]:  # same lines, keys for this voice and speed
                    row["key"] = _key(row["text"], voice, speed)
                    row["file"] = f"{row['key']}.wav"
                return data
        except (OSError, ValueError, KeyError):
            pass
    lines = chapter_lines(sub)
    write_script(sub, voice, speed, lines, line_gaps(sub, lines))
    return json.loads(path.read_text(encoding="utf-8"))


# ---------------- making the audio ----------------
def pregenerate(sub: str, voice: str = DEFAULT_VOICE, speed: float = DEFAULT_SPEED, audio_dir: Path | None = None,
                log: Callable[[str], None] = print, limit: int | None = None) -> dict:
    """One chapter's audio. Resumable: a line whose file exists is left alone. A line that fails is logged and counted
    in "errors", never raised. `limit`: make at most this many new files. The script JSON is written first and always,
    whether or not Kokoro is set up."""
    tts = _tts()
    folder = Path(audio_dir) if audio_dir else tts.audio_dir(vault())
    lines = chapter_lines(sub)
    gaps = line_gaps(sub, lines)
    write_script(sub, voice, speed, lines, gaps)
    res = {"made": 0, "cached": 0, "skipped": 0, "errors": 0,
           "gaps": [{"id": i, "symbols": g} for i, g in gaps.items()], "unavailable": False}
    if not tts.available():
        res["unavailable"] = True
        res["skipped"] = len(lines)
        log(f"{sub}: {len(lines)} lines written to {script_path(sub).relative_to(root())}; {NOT_SET_UP[8:]}")
        return res
    seen: set[str] = set()
    for ln in lines:
        key = _key(ln["text"], voice, speed)
        path = folder / f"{key}.wav"
        if key in seen or path.is_file():
            res["cached"] += 1
        elif limit is not None and res["made"] >= limit:
            res["skipped"] += 1
        else:
            try:
                tts.synthesize(ln["text"], path, voice, speed)
                res["made"] += 1
            except Exception as e:  # noqa: BLE001 - one bad line must not stop the chapter
                res["errors"] += 1
                log(f"{sub}: {ln['id']} failed ({type(e).__name__}: {e})")
        seen.add(key)
    return res


def summary(sub: str, r: dict) -> str:
    if r["unavailable"]:
        return f"{sub}: {r['skipped']} lines, Kokoro not set up (script written, no audio)"
    return (f"{sub}: {r['made'] + r['cached'] + r['skipped'] + r['errors']} lines, made {r['made']}, "
            f"already there {r['cached']}" + (f", left {r['skipped']}" if r["skipped"] else "")
            + (f", {r['errors']} failed" if r["errors"] else "") + (f", {len(r['gaps'])} with gaps" if r["gaps"] else ""))


# ---------------- what there is ----------------
def status(voice: str | None = None, speed: float | None = None, audio_dir: Path | None = None) -> list[dict]:
    """Per built chapter: lines, with audio, missing, gaps (the ids and their first symbols)."""
    v_voice, v_speed = settings()
    voice, speed = voice or v_voice, speed if speed is not None else v_speed
    folder = Path(audio_dir) if audio_dir else _tts().audio_dir(vault())
    rows = []
    for sub in built():
        try:
            data = script(sub, voice, speed)
        except Exception as e:  # noqa: BLE001 - one unreadable chapter must not hide the rest
            rows.append({"sub": sub, "lines": 0, "audio": 0, "missing": 0, "gaps": [], "error": f"{type(e).__name__}: {e}"})
            continue
        have = sum((folder / r["file"]).is_file() for r in data["lines"])
        rows.append({"sub": sub, "lines": len(data["lines"]), "audio": have, "missing": len(data["lines"]) - have,
                     "gaps": [{"id": r["id"], "symbols": r["gaps"]} for r in data["lines"] if r.get("gaps")]})
    return rows


def gaps_report() -> dict[str, list[dict]]:
    """chapter -> its gaps, from the scripts already written (fast: nothing is computed). `tts status` refreshes them."""
    out = {}
    for sub in built():
        try:
            data = json.loads(script_path(sub).read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        g = [{"id": r["id"], "symbols": r["gaps"]} for r in data.get("lines", []) if r.get("gaps")]
        if g:
            out[sub] = g
    return out


def gap_lines(report: dict[str, list[dict]], few: int = 3) -> list[str]:
    """Printable lines for the board / coverage: chapter, how many lines, the first ids and symbols."""
    rows = []
    for sub, g in report.items():
        head = "; ".join(f"{x['id']} ({' '.join(x['symbols'][:3])})" for x in g[:few])
        rows.append(f"  {sub}: {len(g)} line{'s' if len(g) != 1 else ''}: {head}" + (" …" if len(g) > few else ""))
    return rows


def print_gaps(out: Callable[[str], None] = print) -> None:
    rep = gaps_report()
    if rep:
        out(f"\nRead aloud: lines with maths that has no sensible spoken form ({len(rep)} chapters; not a gate: add a "
            "`speech` field with the words to say; `tts status` refreshes this):")
        for row in gap_lines(rep):
            out(row)


# ---------------- the sign hook ----------------
def hook(sub: str, logs: Path, note: Callable[[str], None] | None = None, system: str = "foundry") -> str:
    """After a chapter is signed and published: write its script, and when Kokoro is set up start the audio in a detached
    process (log in `logs`). Never raises, never waits. Returns what it did, in one word: off, script, started, error."""
    if os.environ.get("FOUNDRY_PREGEN", "1") != "1":
        return "off"
    try:
        tts = _tts()
        voice, speed = settings()
        if not tts.available(vault()):
            lines = chapter_lines(sub)
            write_script(sub, voice, speed, lines, line_gaps(sub, lines))
            what, result = NOT_SET_UP, "script"
        else:
            logs.mkdir(parents=True, exist_ok=True)
            log = logs / f"{sub}.speech.{datetime.now():%m%d-%H%M%S}.log"
            with open(log, "ab") as f:
                subprocess.Popen([sys.executable if not (REPO / ".venv/bin/python").exists() else str(REPO / ".venv/bin/python"),
                                  str(Path(__file__).resolve()), "run", sub, "--voice", voice, "--speed", str(speed)],
                                 cwd=REPO, start_new_session=True, stdin=subprocess.DEVNULL, stdout=f, stderr=f,
                                 env={**os.environ, "FOUNDRY_ROOT": str(root())})
            what, result = f"speech: pre-generating in the background (log {log.relative_to(root())})", "started"
        if note:
            note(what)
        print(f"{sub}: {what}")
        return result
    except (Exception, SystemExit) as e:  # noqa: BLE001 - reading aloud must never stop a sign-off
        try:
            if note:
                note(f"speech: skipped ({type(e).__name__}: {e})")
        except (Exception, SystemExit):  # noqa: BLE001
            pass
        return "error"


# ---------------- command line ----------------
def _flag(args: list[str], name: str) -> str | None:
    return args[args.index(name) + 1] if name in args and args.index(name) + 1 < len(args) else None


def cli(args: list[str], out: Callable[[str], None] = print) -> int:
    tts = _tts()
    v_voice, v_speed = settings()
    voice = _flag(args, "--voice") or v_voice
    try:
        speed = float(_flag(args, "--speed") or v_speed)
    except ValueError:
        out("--speed is a number, 0.8 to 1.3")
        return 2
    drop = {x for x in ("--voice", "--speed") if x in args}
    rest = [a for i, a in enumerate(args) if a not in drop and not (i and args[i - 1] in drop)]
    ready = tts.available(vault())
    if rest[:1] == ["status"]:
        rows = status(voice, speed)
        out(f"Kokoro: {'ready' if ready else 'not set up (run tutor tts setup)'}   voice {voice}, speed {speed:g}   "
            f"audio {tts.audio_dir(vault())}")
        out(f"{'CHAPTER':<11} {'LINES':>5} {'AUDIO':>6} {'MISSING':>8} {'GAPS':>5}  STATE")
        for r in rows:
            state = ("error: " + r["error"] if r.get("error") else "all audio" if r["lines"] and not r["missing"]
                     else "none" if not r["audio"] else "partial")
            out(f"{r['sub']:<11} {r['lines']:>5} {r['audio']:>6} {r['missing']:>8} {len(r['gaps']):>5}  {state}")
        full = sum(1 for r in rows if r["lines"] and not r["missing"])
        part = sum(1 for r in rows if r["audio"] and r["missing"])
        none = sum(1 for r in rows if r["lines"] and not r["audio"])
        out(f"\n{len(rows)} chapters: {full} with all audio, {part} partial, {none} none; "
            f"{sum(1 for r in rows if r['gaps'])} with gaps")
        for row in gap_lines({r["sub"]: r["gaps"] for r in rows if r["gaps"]}):
            out(row)
        return 0
    subs = built() if "--all" in rest else [a for a in rest if not a.startswith("-")]
    if not subs:
        out("usage: tts <subtopic…|--all> [--voice V] [--speed S]  |  tts status")
        return 2
    unknown = [s for s in subs if not pack_path(s).is_file()]
    if unknown:
        out(f"no built chapter: {' '.join(unknown)}")
        return 1
    if not ready:
        out("Kokoro is not set up (run  tutor tts setup ): writing the scripts only, no audio.")
    elif len(subs) > 1:
        out(f"{len(subs)} chapters, one after another. This takes a while and costs only local CPU (no allowance); "
            "stop it any time, it carries on where it stopped.")
    failed = 0
    for i, sub in enumerate(subs, 1):
        t = time.monotonic()
        try:
            r = pregenerate(sub, voice, speed, tts.audio_dir(vault()), log=out)
        except Exception as e:  # noqa: BLE001
            out(f"{sub}: failed ({type(e).__name__}: {e})")
            failed += 1
            continue
        failed += r["errors"]
        out(f"[{i}/{len(subs)}] {summary(sub, r)} ({time.monotonic() - t:.0f}s)")
    return 1 if failed else 0


def _one_at_a_time():
    """Wait for our turn: several chapters signed close together must not run Kokoro side by side (each one takes a
    whole core, and twenty at once starved every other job). The lock is dropped when the process ends."""
    import fcntl
    path = root() / "foundry" / "pregen.lock"
    path.parent.mkdir(parents=True, exist_ok=True)
    handle = open(path, "a")  # kept open for the life of the process
    fcntl.flock(handle, fcntl.LOCK_EX)
    _LOCKS.append(handle)


_LOCKS: list = []


def main(argv: list[str]) -> int:
    if argv[:1] == ["run"] and len(argv) > 1:  # the detached job: quiet unless it breaks
        voice, speed = settings()
        _one_at_a_time()
        r = pregenerate(argv[1], _flag(argv, "--voice") or voice, float(_flag(argv, "--speed") or speed))
        print(summary(argv[1], r))
        return 0
    if argv[:1] == ["tts"]:
        argv = argv[1:]
    if not argv or argv[0] in ("-h", "--help"):
        print(__doc__)
        return 0
    return cli(argv)


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
