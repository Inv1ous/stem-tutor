"""Reading aloud with Kokoro, on this Mac (no internet once set up, nothing sent anywhere).

The one API the rest of the tutor uses:
  available() / status()               is it set up?
  synthesize(text, out_path, …)        already-spoken English → a WAV file (16-bit mono, 24 kHz)
  ensure_audio(raw_text, …)            chapter text or maths → the cached WAV for it (made if missing): what the
                                       foundry and refine pre-generators call, and what the app looks up first
  Player                               plays one WAV at a time with macOS `afplay`
  Speaker                              what the screens hold: say(text) in the background, stop()
  cli(args)                            `tutor tts setup | say | voices | doctor`

Kokoro (the `kokoro-onnx` package and its two model files, about 337 MB) is installed only when the learner runs
`tutor tts setup` and says yes. Until then every part of this is a quiet no-op.
"""
from __future__ import annotations

import hashlib
import importlib.util
import os
import re
import shutil
import subprocess
import sys
import threading
import time
import wave
from pathlib import Path
from typing import Callable, Protocol, Sequence

from . import config

SAMPLE_RATE = 24000
RELEASE = "https://github.com/thewh1teagle/kokoro-onnx/releases/download/model-files-v1.0/"
MODEL_FILES = {"kokoro-v1.0.onnx": 325_532_387, "voices-v1.0.bin": 28_214_398}  # bytes, as the release lists them
MODEL, VOICES_FILE = list(MODEL_FILES)
PACKAGES = ["kokoro-onnx", "soundfile"]
DEFAULT_VOICE = "bf_emma"
VOICES = {"bf_emma": "Emma (British)", "bf_isabella": "Isabella (British)", "bm_george": "George (British)",
          "bm_lewis": "Lewis (British)", "af_heart": "Heart (American)", "am_michael": "Michael (American)"}
SPEED_RANGE = (0.8, 1.3)
CHUNK_CHARS = 350   # well under Kokoro's 510 phoneme tokens a call
PAUSE_SECONDS = 0.25  # between chunks
AI_SPEECH_LIMIT = 900  # characters of an AI reply read automatically; ctrl+e reads it all
SETUP_HINT = "Read aloud is not set up: in Terminal run  tutor tts setup  (once)."
OFF_HINT = "Read aloud is off: switch it on in Settings (F2 on the menu)."


class TTSUnavailable(RuntimeError):
    """Kokoro is not set up (or could not start): the message says what to do, in plain words."""


class Engine(Protocol):
    """Kokoro's own `create` (kokoro_onnx.Kokoro), or a fake in tests: samples in -1..1 and their sample rate."""

    def create(self, text: str, voice: str, speed: float, lang: str) -> tuple[Sequence[float], int]: ...


# ---------------- where things are ----------------
def model_dir(vault: Path | None = None) -> Path:
    env = os.environ.get("STEM_TUTOR_TTS_DIR")
    return Path(env) if env else Path(vault or config.vault_path()) / ".tutor" / "tts"


def audio_dir(vault: Path | None = None) -> Path:
    """The cache of WAVs by key: the pre-generators write here, the app reads here first."""
    return Path(vault or config.vault_path()) / ".tutor" / "audio"


def __getattr__(name: str):  # MODEL_DIR / AUDIO_DIR: the current vault's (STEM_TUTOR_VAULT, STEM_TUTOR_TTS_DIR)
    if name == "MODEL_DIR":
        return model_dir()
    if name == "AUDIO_DIR":
        return audio_dir()
    raise AttributeError(name)


# ---------------- the text side (tutorlib.speech) ----------------
def _speech():
    try:
        from tutorlib import speech
        return speech
    except ImportError:  # an older content library: plain cleaning, so reading aloud still works
        return _Plain


class _Plain:
    @staticmethod
    def for_tts(text: str) -> str:
        text = re.sub(r"[$`*_#>|\\{}]", " ", text or "")
        return " ".join(text.split())

    @staticmethod
    def audio_key(speech_text: str, voice: str, speed: float) -> str:
        return hashlib.sha1(f"{voice}|{speed:.2f}|{speech_text}".encode()).hexdigest()


def spoken(raw_text: str) -> str:
    """Chapter text or maths as the words Kokoro is given (tutorlib.speech.for_tts)."""
    return _speech().for_tts(raw_text or "").strip()


def key_for(speech_text: str, voice: str, speed: float) -> str:
    return _speech().audio_key(speech_text, voice, speed)


def clip(text: str, limit: int | None) -> str:
    """At most `limit` characters, ending at a sentence end when there is one in the second half."""
    if not limit or len(text) <= limit:
        return text
    cut = text[:limit]
    end = max(cut.rfind(". "), cut.rfind("? "), cut.rfind("! "))
    return cut[:end + 1] if end > limit // 2 else cut.rsplit(" ", 1)[0] + "."


# ---------------- is it set up? ----------------
def installed() -> bool:
    try:
        return importlib.util.find_spec("kokoro_onnx") is not None
    except (ImportError, ValueError):
        return False


def models_present(folder: Path | None = None) -> bool:
    folder = folder or model_dir()
    return all((folder / name).is_file() and (folder / name).stat().st_size == size for name, size in MODEL_FILES.items())


def available(vault: Path | None = None) -> bool:
    """Kokoro can speak: an engine is loaded (or injected), or the package and both model files are here."""
    return _engine is not None or (installed() and models_present(model_dir(vault)))


def status(vault: Path | None = None) -> str:
    if _engine is not None:
        return "ready"
    have_pkg, have_models = installed(), models_present(model_dir(vault))
    if have_pkg and have_models:
        return "ready"
    if not have_pkg and not have_models:
        return "not set up: run  tutor tts setup"
    if not have_models:
        return "model missing: run  tutor tts setup  (it carries on where it stopped)"
    return "kokoro-onnx not installed: run  tutor tts setup"


# ---------------- the engine (loaded once, lazily) ----------------
_engine: Engine | None = None
_engine_lock = threading.Lock()


def set_engine(engine: Engine | None) -> None:
    """Use this engine from now on (tests: a fake; None: load Kokoro again when next needed)."""
    global _engine
    _engine = engine


class _Kokoro:
    def __init__(self, folder: Path) -> None:
        from kokoro_onnx import Kokoro  # imported here: the app starts without it
        self.k = Kokoro(str(folder / MODEL), str(folder / VOICES_FILE))

    def create(self, text: str, voice: str, speed: float, lang: str):
        return self.k.create(text, voice=voice, speed=speed, lang=lang)

    def voices(self) -> list[str]:
        return list(self.k.get_voices())


def engine(vault: Path | None = None) -> Engine:
    global _engine
    with _engine_lock:
        if _engine is None:
            folder = model_dir(vault)
            if not installed() or not models_present(folder):
                raise TTSUnavailable(SETUP_HINT)
            try:
                _engine = _Kokoro(folder)
            except Exception as e:  # noqa: BLE001 - a broken install must say so, not crash the app
                raise TTSUnavailable(f"Kokoro could not start ({type(e).__name__}: {e}). "
                                     "Run  tutor tts setup  again.") from e
        return _engine


def lang_of(voice: str) -> str:
    return "en-gb" if voice[:1] == "b" else "en-us"


# ---------------- making audio ----------------
def chunks(text: str, limit: int = CHUNK_CHARS) -> list[str]:
    """Sentences packed into pieces of at most `limit` characters; a longer sentence splits at commas, then words."""
    out: list[str] = []
    for sentence in re.split(r"(?<=[.!?;:])\s+", " ".join(text.split())):
        pieces = [sentence]
        if len(sentence) > limit:
            pieces = []
            for part in re.split(r"(?<=,)\s+", sentence):
                while len(part) > limit:
                    cut = part.rfind(" ", 0, limit)
                    cut = cut if cut > 0 else limit
                    pieces.append(part[:cut].strip())
                    part = part[cut:].strip()
                pieces.append(part)
        for p in filter(None, pieces):
            if out and len(out[-1]) + 1 + len(p) <= limit:
                out[-1] += " " + p
            else:
                out.append(p)
    return out


def _pcm(samples) -> bytes:
    if hasattr(samples, "astype"):  # numpy, from Kokoro
        import numpy as np
        return (np.clip(samples, -1.0, 1.0) * 32767).astype("<i2").tobytes()
    from array import array
    a = array("h", (int(max(-1.0, min(1.0, float(s))) * 32767) for s in samples))
    if sys.byteorder == "big":
        a.byteswap()
    return a.tobytes()


def synthesize(text: str, out_path: Path, voice: str = DEFAULT_VOICE, speed: float = 1.0,
               vault: Path | None = None) -> Path:
    """Already-spoken English → a WAV (16-bit mono 24 kHz) at `out_path`, written whole or not at all."""
    text = " ".join((text or "").split())
    if not text:
        raise ValueError("nothing to say")
    eng = engine(vault)
    speed = min(SPEED_RANGE[1], max(SPEED_RANGE[0], float(speed)))
    frames, rate = [], SAMPLE_RATE
    for i, piece in enumerate(chunks(text)):
        samples, rate = eng.create(piece, voice=voice, speed=speed, lang=lang_of(voice))
        if i:
            frames.append(b"\0\0" * int(rate * PAUSE_SECONDS))
        frames.append(_pcm(samples))
    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    tmp = out_path.with_name(f".{out_path.name}.{os.getpid()}.{threading.get_ident()}.tmp")
    try:
        with wave.open(str(tmp), "wb") as w:
            w.setnchannels(1)
            w.setsampwidth(2)
            w.setframerate(rate)
            w.writeframes(b"".join(frames))
        os.replace(tmp, out_path)
    finally:
        tmp.unlink(missing_ok=True)
    return out_path


def ensure_audio(raw_text: str, voice: str = DEFAULT_VOICE, speed: float = 1.0,
                 audio_dir: Path | None = None) -> Path | None:
    """The WAV for `raw_text` (chapter text, maths and all): `<audio_dir>/<key>.wav` if it is already there, else
    made now. None when there is nothing to say or Kokoro is not set up. What the pre-generators call."""
    folder = Path(audio_dir) if audio_dir else globals()["audio_dir"]()
    text = spoken(raw_text)
    if not text:
        return None
    path = folder / f"{key_for(text, voice, speed)}.wav"
    if path.is_file():
        return path
    try:
        return synthesize(text, path, voice, speed)
    except TTSUnavailable:
        return None


def join_wavs(paths: Sequence[Path], out_path: Path, pause: float = PAUSE_SECONDS * 2) -> Path:
    """Several WAVs of the same kind (Kokoro's: mono 16-bit 24 kHz) → one, with a short pause between, atomically."""
    frames, params = [], None
    for i, p in enumerate(paths):
        with wave.open(str(p), "rb") as w:
            params = params or w.getparams()
            if i:
                frames.append(b"\0" * params.sampwidth * params.nchannels * int(params.framerate * pause))
            frames.append(w.readframes(w.getnframes()))
    out_path.parent.mkdir(parents=True, exist_ok=True)
    tmp = out_path.with_name(f".{out_path.name}.{os.getpid()}.{threading.get_ident()}.tmp")
    try:
        with wave.open(str(tmp), "wb") as w:
            w.setnchannels(params.nchannels)
            w.setsampwidth(params.sampwidth)
            w.setframerate(params.framerate)
            w.writeframes(b"".join(frames))
        os.replace(tmp, out_path)
    finally:
        tmp.unlink(missing_ok=True)
    return out_path


# ---------------- playing ----------------
class Player:
    """One sound at a time through macOS `afplay` (no extra library). Never raises."""

    def __init__(self, binary: str | None = None, on_missing: Callable[[str], None] | None = None) -> None:
        self.binary = binary or shutil.which("afplay")
        self.on_missing = on_missing
        self.proc: subprocess.Popen | None = None
        self._told = False
        self._lock = threading.Lock()

    @property
    def playing(self) -> bool:
        return self.proc is not None and self.proc.poll() is None

    def play(self, path: Path) -> bool:
        self.stop()
        if not self.binary:
            if not self._told and self.on_missing:
                self._told = True
                self.on_missing("Can't play sound: macOS's afplay was not found.")
            return False
        with self._lock:
            try:
                self.proc = subprocess.Popen([self.binary, str(path)], stdin=subprocess.DEVNULL,
                                             stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            except OSError:
                self.proc = None
                return False
        return True

    def stop(self) -> None:
        with self._lock:
            proc, self.proc = self.proc, None
        if proc is not None and proc.poll() is None:
            try:
                proc.terminate()
                proc.wait(timeout=1)
            except (OSError, subprocess.TimeoutExpired):
                try:
                    proc.kill()
                except OSError:
                    pass

    def wait(self) -> None:
        proc = self.proc
        if proc is not None:
            try:
                proc.wait()
            except (OSError, KeyboardInterrupt):
                self.stop()


class Speaker:
    """What a screen holds: `say(text)` finds or makes the audio in a background thread and plays it, so the screen
    never waits; a newer say() or stop() drops an older line, made or not. `settings()` gives the app's Settings."""

    def __init__(self, vault: Path, settings: Callable[[], object], player: Player | None = None,
                 notify: Callable[[str], None] | None = None) -> None:
        self.vault, self.settings, self.notify = Path(vault), settings, notify
        self.player = player or Player(on_missing=self._say_once)
        self.audio_dir = audio_dir(self.vault)
        self.live_dir = self.audio_dir / "live"  # lines made on the spot (AI replies): the newest LIVE_KEEP kept
        self._gen = 0
        self._pending: tuple[int, list[str], int | None] | None = None
        self._working: int | None = None
        self._cond = threading.Condition()
        self._thread: threading.Thread | None = None
        self._closed = False

    LIVE_KEEP = 200

    def _say_once(self, msg: str) -> None:
        if self.notify:
            self.notify(msg)

    @property
    def enabled(self) -> bool:
        return bool(getattr(self.settings(), "tts_enabled", False))

    def problem(self) -> str | None:
        """None when a line can be read now, else the one-line reason."""
        if not available(self.vault):
            return SETUP_HINT
        if not self.enabled:
            return OFF_HINT
        return None

    @property
    def usable(self) -> bool:
        return self.problem() is None

    @property
    def active(self) -> bool:
        """Reading, or about to (the line is being made)."""
        with self._cond:
            busy = self._pending is not None or self._working == self._gen
        return busy or self.player.playing

    def say(self, raw_text: str | Sequence[str], limit: int | None = None) -> bool:
        """Read `raw_text` (chapter text or maths: it is put into words here). A list is read as one line made of
        its parts, each found or made on its own: the parts the foundry pre-generated (a card's explanation, a
        question's worked answer) play from its files, only the rest is made now. `limit`: at most this many
        characters of a single text (an AI reply read by itself)."""
        parts = [raw_text] if isinstance(raw_text, str) else [p for p in raw_text if isinstance(p, str)]
        if self._closed or not any(p.strip() for p in parts) or not self.usable:
            return False
        with self._cond:  # under the lock: a line already made can't start playing after this
            self._gen += 1
            self._pending = (self._gen, parts, limit)
            self.player.stop()
            self._cond.notify()
            if self._thread is None or not self._thread.is_alive():
                self._thread = threading.Thread(target=self._run, name="tts-speaker", daemon=True)
                self._thread.start()
        return True

    def stop(self) -> None:
        with self._cond:
            self._gen += 1
            self._pending = None
            self.player.stop()

    def close(self) -> None:
        self._closed = True
        self.stop()
        with self._cond:
            self._cond.notify_all()

    def wait_idle(self, timeout: float = 5.0) -> bool:
        """For tests and the command line: True once nothing is waiting to be made."""
        end = time.monotonic() + timeout
        while time.monotonic() < end:
            with self._cond:
                if self._pending is None and self._working is None:
                    return True
            time.sleep(0.01)
        return False

    def _run(self) -> None:
        while True:
            with self._cond:
                while self._pending is None and not self._closed:
                    self._cond.wait()
                if self._closed:
                    return
                gen, raw, limit = self._pending
                self._pending, self._working = None, gen
            try:
                path = self._audio(raw, limit)
            except Exception as e:  # noqa: BLE001 - the reading thread must never die or reach the screen
                path = None
                self._say_once(f"Couldn't read that aloud ({type(e).__name__}).")
            with self._cond:
                self._working = None
                if path is not None and gen == self._gen and not self._closed:
                    self.player.play(path)

    def _audio(self, parts: list[str], limit: int | None) -> Path | None:
        s = self.settings()
        voice = getattr(s, "tts_voice", DEFAULT_VOICE) or DEFAULT_VOICE
        speed = float(getattr(s, "tts_speed", 1.0) or 1.0)
        texts = [t for t in (spoken(p) for p in parts) if t]
        if len(texts) == 1 and limit:
            texts = [clip(texts[0], limit)]
        paths = []
        for text in texts:
            if (path := self._one(text, voice, speed)) is None:
                return None
            paths.append(path)
        if len(paths) <= 1:
            return paths[0] if paths else None
        joined = self.live_dir / f"{key_for(' | '.join(texts), voice, speed)}.wav"
        if not joined.is_file():
            join_wavs(paths, joined)
        return joined

    def _one(self, text: str, voice: str, speed: float) -> Path | None:
        key = key_for(text, voice, speed)
        for folder in (self.audio_dir, self.live_dir):  # the pre-generated line first: it plays at once
            if (folder / f"{key}.wav").is_file():
                return folder / f"{key}.wav"
        try:
            path = synthesize(text, self.live_dir / f"{key}.wav", voice, speed, vault=self.vault)
        except TTSUnavailable as e:
            self._say_once(str(e))
            return None
        self._prune()
        return path

    def _prune(self) -> None:
        try:
            files = sorted(self.live_dir.glob("*.wav"), key=lambda p: p.stat().st_mtime)
            for old in files[:-self.LIVE_KEEP]:
                old.unlink(missing_ok=True)
        except OSError:
            pass


# ---------------- setup and the command line ----------------
def _project_python() -> str:
    venv = config.REPO / ".venv" / "bin" / "python"
    return str(venv) if venv.exists() else sys.executable


def _mb(n: int) -> str:
    return f"{n / 1_000_000:.0f} MB"


def download(url: str, target: Path, size: int, urlopen=None, out: Callable[[str], None] = print) -> bool:
    """`url` → `target`, carrying on from `<target>.part` if an earlier try stopped; checked against `size`."""
    import urllib.error
    import urllib.request
    urlopen = urlopen or urllib.request.urlopen
    part = target.with_name(target.name + ".part")
    have = part.stat().st_size if part.exists() else 0
    if have > size:
        part.unlink()
        have = 0
    req = urllib.request.Request(url, headers={"Range": f"bytes={have}-"} if have else {})
    try:
        with urlopen(req, timeout=60) as resp:
            if have and getattr(resp, "status", 200) != 206:  # the server started again from the beginning
                have = 0
            with open(part, "ab" if have else "wb") as f:
                done, shown = have, -1
                while True:
                    block = resp.read(1 << 20)
                    if not block:
                        break
                    f.write(block)
                    done += len(block)
                    pct = int(100 * done / size)
                    if pct // 5 != shown:
                        shown = pct // 5
                        out(f"  {target.name}: {pct}% ({_mb(done)} of {_mb(size)})")
    except (urllib.error.URLError, OSError, TimeoutError) as e:
        out(f"Couldn't download {target.name} ({getattr(e, 'reason', e)}). Check the internet connection, then run  "
            "tutor tts setup  again: it carries on where it stopped.")
        return False
    got = part.stat().st_size
    if got != size:
        out(f"{target.name} came out {got:,} bytes, not {size:,}. Run  tutor tts setup  again to carry on"
            + (" (the broken file was removed)." if got > size else "."))
        if got > size:
            part.unlink()
        return False
    os.replace(part, target)
    return True


def setup(vault: Path | None = None, ask: Callable[[str], str] = input, run=subprocess.run, urlopen=None,
          out: Callable[[str], None] = print) -> int:
    folder = model_dir(vault)
    todo = {n: s for n, s in MODEL_FILES.items() if not ((folder / n).is_file() and (folder / n).stat().st_size == s)}
    need_pkg = not installed()
    if not todo and not need_pkg:
        out(f"Read aloud is already set up (Kokoro, model in {folder}).")
        _switch_on(vault, out)
        return 0
    out("Read aloud uses Kokoro, a text-to-speech model that runs on this Mac (nothing is sent anywhere).")
    out("Setting it up will:")
    if need_pkg:
        out(f"  1. install the Python packages {' and '.join(PACKAGES)} into the tutor's own .venv "
            "(about 60 MB with onnxruntime)")
    if todo:
        out(f"  {2 if need_pkg else 1}. download the model into {folder}:")
        for name, size in todo.items():
            out(f"       {name}  {_mb(size)}  ({RELEASE}{name})")
        out(f"     {_mb(sum(todo.values()))} in all. A stopped download carries on next time.")
    if ask("Go ahead? [y/N] ").strip().lower() not in ("y", "yes"):
        out("Nothing was installed or downloaded.")
        return 1
    if need_pkg:
        out("Installing " + ", ".join(PACKAGES) + "…")
        try:
            done = run([_project_python(), "-m", "pip", "install", "-q", *PACKAGES])
        except OSError as e:
            out(f"Couldn't run pip ({e}). Nothing else was changed.")
            return 1
        if getattr(done, "returncode", 1) != 0:
            out("Installing the packages failed (see above): check the internet connection, then run  "
                "tutor tts setup  again.")
            return 1
    folder.mkdir(parents=True, exist_ok=True)
    for name, size in todo.items():
        out(f"Downloading {name} ({_mb(size)})…")
        if not download(RELEASE + name, folder / name, size, urlopen=urlopen, out=out):
            return 1
    out("Read aloud is set up. The release publishes no checksums, so each file was checked by its exact size.")
    _switch_on(vault, out)
    out('Try it:  tutor tts say "The integral of x squared from 0 to 1 is one third."')
    return 0


def _switch_on(vault: Path | None, out: Callable[[str], None]) -> None:
    v = Path(vault or config.vault_path())
    if not (v / ".tutor").is_dir():
        return
    s = config.Settings.load(v)
    if not s.tts_enabled:
        s.tts_enabled = True
        s.save(v)
        out("Switched on in Settings (F2 on the menu turns it off, or picks another voice).")


def doctor_rows(vault: Path | None = None) -> list[tuple[bool | None, str, str]]:
    """For `tutor doctor`: optional, so ✗ only when it was half set up."""
    st = status(vault)
    if st == "ready":
        player = shutil.which("afplay")
        return [(bool(player), "Read aloud (Kokoro): ready", "" if player else "macOS's afplay is missing: "
                 "audio can be made but not played.")]
    if st.startswith("not set up"):
        return [(None, "Read aloud (Kokoro): not set up (optional)", "To have explanations read aloud: tutor tts setup")]
    return [(False, f"Read aloud (Kokoro): {st}", "Run: tutor tts setup")]


def cli(args: list[str], vault: Path | None = None) -> int:
    import argparse
    ap = argparse.ArgumentParser(prog="tutor tts", description="Read aloud with Kokoro (local text to speech).")
    ap.add_argument("action", choices=["setup", "say", "voices", "doctor"])
    ap.add_argument("text", nargs="*", help="with say: the words (maths welcome) to read")
    ap.add_argument("--voice", default=None)
    ap.add_argument("--speed", type=float, default=None)
    a = ap.parse_args(args)
    if a.action == "setup":
        return setup(vault)
    if a.action == "doctor":
        rows = doctor_rows(vault)
        for ok, check, fix in rows:
            print(f"{'·' if ok is None else '✓' if ok else '✗'} {check}" + (f"\n   → {fix}" if fix else ""))
        print(f"  model folder: {model_dir(vault)}\n  audio cache: {audio_dir(vault)}")
        return 1 if any(ok is False for ok, _, _ in rows) else 0
    if a.action == "voices":
        print("Voices (set one in Settings, or try with  tutor tts say --voice NAME \"text\"):")
        for name, label in VOICES.items():
            print(f"  {name:<12} {label}")
        if available(vault):
            try:
                eng = engine(vault)
                more = [v for v in getattr(eng, "voices", lambda: [])() if v not in VOICES]
                if more:
                    print("Also in the model: " + ", ".join(more))
            except TTSUnavailable:
                pass
        return 0
    text = " ".join(a.text)
    if not text:
        print('Say what?  tutor tts say "the words to read"')
        return 1
    if not available(vault):
        print(SETUP_HINT)
        return 1
    v = Path(vault or config.vault_path())
    s = config.Settings.load(v) if (v / ".tutor").is_dir() else config.Settings()
    voice, speed = a.voice or s.tts_voice, a.speed or s.tts_speed
    print("Reading: " + spoken(text))
    try:
        path = ensure_audio(text, voice, speed, audio_dir(v) / "live")
    except Exception as e:  # noqa: BLE001
        print(f"Couldn't make the audio ({type(e).__name__}: {e}).")
        return 1
    if path is None:
        print("Nothing to read.")
        return 1
    player = Player(on_missing=print)
    if player.play(path):
        player.wait()
    return 0
