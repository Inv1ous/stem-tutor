"""Reading aloud (tts.py): hermetic, with a fake Kokoro engine and a fake player. Nothing is installed, downloaded
or played for real."""
import asyncio
import hashlib
import io
import json
import sys
import threading
import time
import types
import urllib.error
import wave
from pathlib import Path

import pytest

from test_tui import app_for
from tutor_app import ai, config, tts

FAKE = str(Path(__file__).with_name("fake_claude.py"))


# ---------------- fakes ----------------
class FakeEngine:
    def __init__(self, gate: threading.Event | None = None, fail_on: str | None = None):
        self.calls, self.gate, self.fail_on = [], gate, fail_on

    def create(self, text, voice, speed, lang):
        self.calls.append((text, voice, speed, lang))
        if self.gate is not None:
            self.gate.wait(5)
        if self.fail_on and self.fail_on in text:
            raise RuntimeError("engine broke")
        return [0.5, -0.5, 0.0] * 80, 24000


class FakePlayer:
    def __init__(self):
        self.played, self.stops, self._on, self.volumes = [], 0, False, []
        self.volume = None  # the Speaker gives a real player its settings; this one only records what it is told

    @property
    def playing(self):
        return self._on

    def play(self, path, volume=None):
        self.played.append(Path(path))
        self.volumes.append(volume)
        self._on = True
        return True

    def stop(self):
        self.stops += 1
        self._on = False


def _stub_speech():
    """The contract of tutorlib.speech, for when the real module is not there yet."""
    m = types.ModuleType("tutorlib.speech")
    m.for_tts = lambda text: " ".join(str(text).replace("$", " ").replace("^2", " squared").split())
    m.speakable = m.for_tts
    m.speech_gaps = lambda text: []
    m.audio_key = lambda s, voice, speed: hashlib.sha1(f"{voice}|{speed}|{s}".encode()).hexdigest()
    m.script_for_chapter = lambda pack, note: []
    return m


@pytest.fixture(autouse=True)
def hermetic(tmp_path, monkeypatch):
    monkeypatch.setenv("STEM_TUTOR_TTS_DIR", str(tmp_path / "tts-models"))
    try:
        from tutorlib import speech  # noqa: F401
    except ImportError:
        import tutorlib
        stub = _stub_speech()
        monkeypatch.setitem(sys.modules, "tutorlib.speech", stub)
        monkeypatch.setattr(tutorlib, "speech", stub, raising=False)
    monkeypatch.setattr(tts, "installed", lambda: False)  # the real package is never looked for
    tts.set_engine(None)
    yield
    tts.set_engine(None)


def speech_mod():
    from tutorlib import speech
    return speech


def frames(path: Path):
    with wave.open(str(path)) as w:
        return w.getnchannels(), w.getsampwidth(), w.getframerate(), w.getnframes()


# ---------------- making audio ----------------
def test_long_text_is_cut_into_sentence_chunks_under_the_limit():
    text = " ".join(f"Sentence number {i} says something about forces." for i in range(40))
    parts = tts.chunks(text)
    assert len(parts) > 1 and all(len(p) <= tts.CHUNK_CHARS for p in parts)
    assert all(p.endswith(".") for p in parts)  # cut between sentences, never inside one
    assert " ".join(parts) == " ".join(text.split())
    one = "word, " * 200  # one sentence far too long: at commas, then words
    assert all(len(p) <= tts.CHUNK_CHARS for p in tts.chunks(one))


def test_synthesize_writes_one_valid_wav_joining_chunks_with_pauses(tmp_path):
    eng = FakeEngine()
    tts.set_engine(eng)
    text = " ".join(f"This is sentence {i} of a long explanation." for i in range(30))
    out = tts.synthesize(text, tmp_path / "a" / "x.wav", voice="bf_emma", speed=1.0)
    n = len(eng.calls)
    assert n > 1 and all(c[3] == "en-gb" and c[1] == "bf_emma" for c in eng.calls)
    assert frames(out) == (1, 2, 24000, 240 * n + int(24000 * tts.PAUSE_SECONDS) * (n - 1))
    assert [p.name for p in out.parent.iterdir()] == ["x.wav"]  # nothing half-written left beside it


def test_synthesize_writes_all_or_nothing(tmp_path):
    tts.set_engine(FakeEngine(fail_on="sentence 20"))
    text = " ".join(f"This is sentence {i} of a long explanation." for i in range(30))
    with pytest.raises(RuntimeError):
        tts.synthesize(text, tmp_path / "x.wav")
    assert list(tmp_path.iterdir()) == []


def test_speed_is_kept_in_range_and_american_voices_speak_american(tmp_path):
    eng = FakeEngine()
    tts.set_engine(eng)
    tts.synthesize("Hello.", tmp_path / "x.wav", voice="af_heart", speed=3)
    assert eng.calls[0][2:] == (1.3, "en-us")


def test_not_set_up_is_a_plain_message(tmp_path):
    assert not tts.available() and tts.status().startswith("not set up")
    with pytest.raises(tts.TTSUnavailable, match="tutor tts setup"):
        tts.synthesize("Hello.", tmp_path / "x.wav")
    assert tts.ensure_audio("Hello", audio_dir=tmp_path) is None


def test_model_files_without_the_package_say_what_is_missing(tmp_path):
    d = tmp_path / "tts-models"
    d.mkdir()
    assert "not set up" in tts.status()
    for name, size in tts.MODEL_FILES.items():
        with open(d / name, "wb") as f:
            f.truncate(size)
    assert "kokoro-onnx not installed" in tts.status() and not tts.available()


def test_ensure_audio_names_the_file_by_the_shared_key_and_makes_it_once(tmp_path):
    eng = FakeEngine()
    tts.set_engine(eng)
    raw = "The speed is $v^2$ over r."
    path = tts.ensure_audio(raw, "bf_emma", 1.0, tmp_path)
    sp = speech_mod()
    assert path == tmp_path / f"{sp.audio_key(sp.for_tts(raw), 'bf_emma', 1.0)}.wav" and path.is_file()
    assert len(eng.calls) == 1 and eng.calls[0][0] == sp.for_tts(raw).strip()
    assert tts.ensure_audio(raw, "bf_emma", 1.0, tmp_path) == path and len(eng.calls) == 1  # a hit: not made again
    assert tts.ensure_audio(raw, "bm_george", 1.0, tmp_path) != path  # another voice is another file
    assert tts.ensure_audio("   ", "bf_emma", 1.0, tmp_path) is None


def test_pre_generated_audio_is_used_even_before_kokoro_is_set_up(tmp_path):
    sp = speech_mod()
    raw = "Pre-made line."
    pre = tmp_path / f"{sp.audio_key(sp.for_tts(raw), 'bf_emma', 1.0)}.wav"
    pre.write_bytes(b"RIFF")
    assert tts.ensure_audio(raw, "bf_emma", 1.0, tmp_path) == pre


def test_clip_ends_at_a_sentence():
    text = "First sentence here. " * 80
    out = tts.clip(text.strip(), 900)
    assert len(out) <= 900 and out.endswith(".")
    assert tts.clip("short", 900) == "short"


# ---------------- playing ----------------
def test_player_without_afplay_says_so_once_and_never_raises(tmp_path):
    said = []
    p = tts.Player(binary="", on_missing=said.append)
    p.binary = None
    assert p.play(tmp_path / "x.wav") is False and p.play(tmp_path / "x.wav") is False
    assert len(said) == 1 and "afplay" in said[0] and not p.playing
    p.stop()


def test_player_plays_one_thing_at_a_time(tmp_path):
    p = tts.Player(binary="/bin/sleep")
    assert p.play("5") and p.playing
    first = p.proc
    assert p.play("5") and first.poll() is not None  # the first stopped when the second began
    p.stop()
    assert not p.playing


def _speaker(tmp_path, enabled=True, auto=True):
    s = config.Settings(tts_enabled=enabled, tts_auto=auto)
    player = FakePlayer()
    return tts.Speaker(tmp_path / "vault", lambda: s, player=player), player, s


def test_speaker_never_blocks_and_drops_a_stale_line(tmp_path):
    gate = threading.Event()
    eng = FakeEngine(gate=gate)
    tts.set_engine(eng)
    sp, player, _ = _speaker(tmp_path)
    t0 = time.monotonic()
    assert sp.say("First line.") and sp.say("Second line.")
    assert time.monotonic() - t0 < 0.2 and sp.active  # back at once while the line is being made
    gate.set()
    assert sp.wait_idle()
    time.sleep(0.05)
    assert len(player.played) == 1  # only the newest line plays
    assert any("Second line." in c[0] for c in eng.calls)
    sp.close()


def test_speaker_stop_while_making_plays_nothing(tmp_path):
    gate = threading.Event()
    tts.set_engine(FakeEngine(gate=gate))
    sp, player, _ = _speaker(tmp_path)
    sp.say("A line.")
    time.sleep(0.05)
    sp.stop()
    gate.set()
    assert sp.wait_idle()
    time.sleep(0.05)
    assert player.played == [] and not sp.active
    sp.close()


def test_speaker_prefers_the_pre_generated_file(tmp_path):
    eng = FakeEngine()
    tts.set_engine(eng)
    sp, player, s = _speaker(tmp_path)
    speech = speech_mod()
    raw = "Already made by the foundry."
    pre = sp.audio_dir / f"{speech.audio_key(speech.for_tts(raw), s.tts_voice, s.tts_speed)}.wav"
    pre.parent.mkdir(parents=True)
    pre.write_bytes(b"RIFF")
    sp.say(raw)
    assert sp.wait_idle()
    time.sleep(0.05)
    assert player.played == [pre] and eng.calls == []
    sp.say("Something new.")
    assert sp.wait_idle()
    time.sleep(0.05)
    assert player.played[-1].parent == sp.live_dir and len(eng.calls) == 1
    sp.close()


def test_speaker_is_a_no_op_when_off_or_not_set_up(tmp_path):
    sp, player, s = _speaker(tmp_path)
    assert sp.problem() == tts.SETUP_HINT and not sp.say("Hello")
    tts.set_engine(FakeEngine())
    s.tts_enabled = False
    assert sp.problem() == tts.OFF_HINT and not sp.say("Hello") and player.played == []


# ---------------- settings ----------------
def test_settings_keep_the_reading_choices(tmp_path):
    (tmp_path / ".tutor").mkdir()
    config.Settings(tts_enabled=True, tts_auto=True, tts_voice="bm_george", tts_speed=1.2).save(tmp_path)
    s = config.Settings.load(tmp_path)
    assert (s.tts_enabled, s.tts_auto, s.tts_voice, s.tts_speed) == (True, True, "bm_george", 1.2)
    (tmp_path / ".tutor/app_settings.json").write_text(json.dumps({"tts_speed": 1, "tts_voice": ""}))
    assert config.Settings.load(tmp_path).tts_speed == 1.0 and config.Settings.load(tmp_path).tts_voice == "bf_emma"
    (tmp_path / ".tutor/app_settings.json").write_text(json.dumps({"tts_speed": 9.0}))
    assert config.Settings.load(tmp_path).tts_speed == 1.3
    assert config.Settings().tts_enabled is False  # off until set up


# ---------------- setup ----------------
class FakeResponse(io.BytesIO):
    def __init__(self, data, status=200):
        super().__init__(data)
        self.status = status

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


def _vault(tmp_path):
    v = tmp_path / "vault"
    (v / ".tutor").mkdir(parents=True)
    return v


def test_setup_does_nothing_without_a_yes(tmp_path):
    ran, fetched, said = [], [], []
    code = tts.setup(_vault(tmp_path), ask=lambda q: "", run=lambda *a, **k: ran.append(a),
                     urlopen=lambda *a, **k: fetched.append(a), out=said.append)
    text = "\n".join(said)
    assert code == 1 and ran == [] and fetched == [] and "Nothing was installed or downloaded" in text
    assert "kokoro-v1.0.onnx" in text and "326 MB" in text and "voices-v1.0.bin" in text and "28 MB" in text
    assert tts.RELEASE + "kokoro-v1.0.onnx" in text and not (tmp_path / "tts-models").exists()


def test_setup_offline_fails_plainly_and_leaves_no_model(tmp_path, monkeypatch):
    def offline(*a, **k):
        raise urllib.error.URLError("no internet")
    said = []
    ran = []
    code = tts.setup(_vault(tmp_path), ask=lambda q: "y",
                     run=lambda cmd, **k: ran.append(cmd) or types.SimpleNamespace(returncode=0),
                     urlopen=offline, out=said.append)
    assert code == 1 and "internet" in "\n".join(said)
    assert ran and ran[0][1:5] == ["-m", "pip", "install", "-q"] and "kokoro-onnx" in ran[0]
    assert not tts.models_present()


def test_setup_stops_when_pip_fails(tmp_path):
    said, fetched = [], []
    code = tts.setup(_vault(tmp_path), ask=lambda q: "yes", run=lambda cmd, **k: types.SimpleNamespace(returncode=1),
                     urlopen=lambda *a, **k: fetched.append(a), out=said.append)
    assert code == 1 and fetched == [] and "failed" in "\n".join(said)


def test_setup_downloads_resumes_checks_sizes_and_switches_reading_on(tmp_path, monkeypatch):
    monkeypatch.setattr(tts, "MODEL_FILES", {"kokoro-v1.0.onnx": 10, "voices-v1.0.bin": 4})
    monkeypatch.setattr(tts, "installed", lambda: True)  # the package is there: only the model is fetched
    folder = tts.model_dir()
    folder.mkdir(parents=True)
    (folder / "kokoro-v1.0.onnx.part").write_bytes(b"01234")  # an earlier try stopped half way
    asked = []

    def urlopen(req, timeout=0):
        asked.append((req.full_url, req.headers.get("Range")))
        if req.full_url.endswith(".onnx"):
            return FakeResponse(b"56789", status=206)
        return FakeResponse(b"vvvv")
    v = _vault(tmp_path)
    said = []
    assert tts.setup(v, ask=lambda q: "y", run=lambda *a, **k: pytest.fail("pip run"), urlopen=urlopen,
                     out=said.append) == 0
    assert asked == [(tts.RELEASE + "kokoro-v1.0.onnx", "bytes=5-"), (tts.RELEASE + "voices-v1.0.bin", None)]
    assert (folder / "kokoro-v1.0.onnx").read_bytes() == b"0123456789" and tts.models_present()
    assert config.Settings.load(v).tts_enabled is True and tts.status() == "ready"


def test_a_download_of_the_wrong_size_is_not_kept(tmp_path, monkeypatch):
    target = tmp_path / "m.bin"
    said = []
    assert not tts.download("https://example.invalid/m.bin", target, 4, urlopen=lambda r, timeout=0: FakeResponse(b"toolong"), out=said.append)
    assert not target.exists() and not (tmp_path / "m.bin.part").exists() and "not 4" in said[-1]


def test_doctor_row_is_optional_until_set_up(tmp_path):
    (ok, check, fix), = tts.doctor_rows()
    assert ok is None and "not set up" in check and "tutor tts setup" in fix
    tts.set_engine(FakeEngine())
    assert "ready" in tts.doctor_rows()[0][1]


def test_tts_command_line_needs_setup_to_say_anything(tmp_path, capsys):
    from tutor_app.__main__ import main
    assert main(["tts", "say", "hello", "--vault", str(_vault(tmp_path))]) == 1
    assert "tutor tts setup" in capsys.readouterr().out
    assert main(["tts", "voices"]) == 0 and "bf_emma" in capsys.readouterr().out


# ---------------- the AI's spoken version ----------------
@pytest.mark.parametrize("chunks,shown,speech", [
    (["Use $x^2$.\n[[SPE", "ECH]] Use x squared."], "Use $x^2$.", "Use x squared."),
    (["No marker", " at all."], "No marker at all.", ""),
    (["Look:\n```\n[[SPEECH]] said", "\n```"], "Look:", "said"),
    (["Nothing to say.\n[[SPEECH]]"], "Nothing to say.", ""),
    (["[", "[", "S", "PEECH]] all speech"], "", "all speech"),
    (["a [[ b"], "a [[ b", ""),
])
def test_the_speech_marker_is_never_shown(chunks, shown, speech):
    f = ai.SpeechFilter()
    out = "".join(f.feed(c) for c in chunks) + f.finish()
    assert ai.SPEECH_MARK not in out and "[[SPE" not in out
    assert ai.split_speech("".join(chunks)) == (shown, speech)
    assert out.strip().rstrip("`").strip() == shown or out.rstrip() == shown


def _claude(tmp_path, monkeypatch, mode, speech=True):
    monkeypatch.setenv("FAKE_CLAUDE_MODE", mode)
    monkeypatch.setenv("FAKE_CLAUDE_LOG", str(tmp_path / "argv.log"))
    return ai.Claude(tmp_path, binary=FAKE, usage_file=tmp_path / "usage.json", speech=speech)


def _stream(c, prompt="hi"):
    async def go():
        out = [chunk async for chunk in c.stream(prompt)]
        await c.close()
        return out
    return asyncio.run(go())


@pytest.mark.parametrize("mode,speech", [("speech", "Reply 1: use x squared here."), ("ok", ""),
                                         ("speech_fence", "Reply 1, said aloud."), ("speech_empty", "")])
def test_streamed_replies_hide_the_spoken_version_and_keep_it_for_reading(tmp_path, monkeypatch, mode, speech):
    c = _claude(tmp_path, monkeypatch, mode)
    shown = "".join(_stream(c))
    assert ai.SPEECH_MARK not in shown and "[[SPE" not in shown
    assert ai.SPEECH_MARK not in c.last.text and c.last.text.startswith("Reply 1") and "```" not in c.last.text
    assert c.last.speech == speech
    assert c.session.replies == 1 and c.session.cached_tokens == 300 and c.today()["replies"] == 1  # counted as before


def test_the_spoken_version_is_asked_for_only_when_reading_is_on(tmp_path, monkeypatch):
    for on in (False, True):
        c = _claude(tmp_path, monkeypatch, "ok", speech=on)
        _stream(c)
        argv = json.loads((tmp_path / "argv.log").read_text().splitlines()[-1])
        assert (ai.SPEECH_MARK in argv[argv.index("--system-prompt") + 1]) is on


def test_one_shot_comments_carry_a_speech_field_only_when_asked_and_on(tmp_path, monkeypatch):
    schema = {"type": "object", "properties": {"feedback": {"type": "string"}}}
    c = _claude(tmp_path, monkeypatch, "ok", speech=True)
    prompts_sent = lambda: [json.loads(line) for line in (tmp_path / "argv.log.prompt").read_text().splitlines()]  # noqa: E731
    data, res = asyncio.run(c.one_shot("mark this", schema=schema, speech=True))
    assert '"speech"' in prompts_sent()[-1] and res.speech == "Spoken feedback: x squared."
    assert schema["properties"].keys() == {"feedback"}  # the caller's schema is left as it was
    data, res = asyncio.run(c.one_shot("write a teaching card", schema=schema))  # not a comment: no extra field
    assert '"speech"' not in prompts_sent()[-1] and res.speech == ""
    c.speech = False
    asyncio.run(c.one_shot("mark this", schema=schema, speech=True))
    assert '"speech"' not in prompts_sent()[-1]


# ---------------- in the app ----------------
def _tts_app(tmp_path, monkeypatch, mode="ok", enabled=True, auto=False, engine=True):
    app, v = app_for(tmp_path, monkeypatch, mode=mode)
    if engine:
        tts.set_engine(FakeEngine())
    app.settings.tts_enabled, app.settings.tts_auto = enabled, auto
    player = FakePlayer()
    app.speaker.player = player
    return app, v, player


def _run(app, size, steps):
    async def go():
        async with app.run_test(size=size) as pilot:
            await pilot.pause()
            await steps(pilot)
            await app.ai.close()
    asyncio.run(go())


async def _settle(app, pilot):
    for _ in range(50):
        await pilot.pause(0.02)
        if app.speaker.wait_idle(0.01):
            break
    await pilot.pause(0.05)


async def _session(app, pilot):
    from tutor_app.screens import SessionScreen
    scr = SessionScreen({"mode": "test", "minutes": 40, "focus": ["9702-2.1"]})
    app.push_screen(scr)
    await pilot.pause()
    await pilot.pause()
    return scr


@pytest.mark.parametrize("size", [(60, 24), (100, 30)])
def test_ctrl_e_reads_what_is_on_screen_and_again_stops_it(tmp_path, monkeypatch, size):
    app, v, player = _tts_app(tmp_path, monkeypatch)

    async def steps(pilot):
        scr = await _session(app, pilot)
        assert scr.readable.strip() and player.played == []  # a question is never read by itself
        await pilot.press("ctrl+e")
        await _settle(app, pilot)
        assert len(player.played) == 1 and player.playing
        await pilot.press("ctrl+e")
        await pilot.pause()
        assert not player.playing and not app.speaker.active
        await pilot.press("ctrl+e")
        await _settle(app, pilot)
        assert len(player.played) == 2
        scr.submit({"entry": f"{scr.view['n']}?", "your": "I don't know"})  # feedback: not read (auto is off)
        await _settle(app, pilot)
        assert len(player.played) == 2 and not player.playing and "answer" in scr.readable
        assert "read" in [b.id for b in scr.query("#panel Button")]
        for b in scr.query("#panel Button"):
            assert b.region.right <= size[0]
        scr.query_one("#read").press()
        await _settle(app, pilot)
        assert len(player.played) == 3 and player.playing
        await pilot.press("ctrl+b")  # leaving the screen stops it
        await pilot.pause()
        assert not player.playing
    _run(app, size, steps)


def test_feedback_is_read_by_itself_only_with_automatic_reading_on(tmp_path, monkeypatch):
    app, v, player = _tts_app(tmp_path, monkeypatch, auto=True)

    async def steps(pilot):
        scr = await _session(app, pilot)
        await _settle(app, pilot)
        assert player.played == []  # the question was not read
        scr.submit({"entry": f"{scr.view['n']}?", "your": "I don't know"})
        await _settle(app, pilot)
        assert len(player.played) == 1 and player.playing
        await pilot.press("escape")  # Esc stops it, as Next does
        await pilot.pause()
        assert not player.playing
    _run(app, (100, 30), steps)


def test_nothing_is_read_while_the_learner_is_typing(tmp_path, monkeypatch):
    app, v, player = _tts_app(tmp_path, monkeypatch, auto=True)

    async def steps(pilot):
        scr = await _session(app, pilot)
        scr.answer_panel({**scr.view, "kind": "numeric"})
        await pilot.pause()
        await pilot.press("4")
        scr.readable_now("An explanation arriving.", auto=True)
        await _settle(app, pilot)
        assert player.played == [] and scr.readable == "An explanation arriving."
    _run(app, (100, 30), steps)


@pytest.mark.parametrize("engine,enabled,hint", [(False, True, tts.SETUP_HINT), (True, False, tts.OFF_HINT)])
def test_ctrl_e_without_reading_set_up_is_a_one_line_hint(tmp_path, monkeypatch, engine, enabled, hint):
    app, v, player = _tts_app(tmp_path, monkeypatch, enabled=enabled, auto=True, engine=engine)
    said = []

    async def steps(pilot):
        monkeypatch.setattr(app, "notify", lambda msg, **k: said.append(msg))
        scr = await _session(app, pilot)
        scr.submit({"entry": f"{scr.view['n']}?", "your": "I don't know"})
        await pilot.pause()
        assert "read" not in [b.id for b in scr.query("#panel Button")]
        await pilot.press("ctrl+e")
        await _settle(app, pilot)
        assert said == [hint] and player.played == []
    _run(app, (60, 24), steps)


def test_an_ai_reply_is_shown_without_its_spoken_version_and_read_from_it(tmp_path, monkeypatch):
    app, v, player = _tts_app(tmp_path, monkeypatch, mode="speech", auto=True)
    heard = []

    async def steps(pilot):
        assert app.ai.speech  # asked for, since reading is on and set up
        monkeypatch.setattr(app.speaker, "say", lambda text, limit=None: heard.append((text, limit)) or True)
        menu = app.screen.query_one("#menu")
        menu.highlighted = [o.id for o in menu.options].index("chat")
        await pilot.press("enter")
        await pilot.pause()
        await pilot.press(*"why", "enter")
        for _ in range(60):
            await pilot.pause(0.05)
            if heard:
                break
        from test_glyphs import _screen_text
        text = _screen_text(app)
        assert "SPEECH" not in text and "SPE" not in text and "Reply 1" in text
        assert heard == [(["Reply 1: use x squared here."], tts.AI_SPEECH_LIMIT)]
        assert app.ai.session.replies == 1
    _run(app, (100, 30), steps)


def test_the_session_log_never_keeps_the_spoken_version(tmp_path, monkeypatch):
    app, v, player = _tts_app(tmp_path, monkeypatch, mode="speech", auto=True)

    async def steps(pilot):
        scr = await _session(app, pilot)
        scr.submit({"entry": f"{scr.view['n']}?", "your": "I don't know"})
        await pilot.pause()
        scr.stream("why?")
        for _ in range(60):
            await pilot.pause(0.05)
            if app.ai.session.replies:
                break
        await _settle(app, pilot)
        assert "x squared" in scr.readable and "[[" not in scr.readable
    _run(app, (100, 30), steps)
    for f in list((v / "Lessons").rglob("*.md")) + [v / "Now.md"]:
        assert "SPEECH" not in f.read_text()


def test_settings_rows_for_reading_save_and_fit_60_by_24(tmp_path, monkeypatch):
    from textual.widgets import Input, Select, Switch
    app, v, player = _tts_app(tmp_path, monkeypatch, enabled=False)

    async def steps(pilot):
        app.action_settings()
        await pilot.pause()
        scr = app.screen
        box = scr.query_one("#settings")
        for key in ("tts_enabled", "tts_auto"):
            sw = scr.query_one(f"#{key}", Switch)
            label = sw.parent.query("Static").first()
            sw.scroll_visible(animate=False)
            await pilot.pause()
            assert label.region.right <= box.region.right
            sw.value = True
        scr.query_one("#tts_voice", Select).value = "bm_lewis"
        scr.query_one("#tts_speed", Input).value = "1.5"
        scr.query_one("#save").press()
        await pilot.pause()
        s = config.Settings.load(v)
        assert (s.tts_enabled, s.tts_auto, s.tts_voice, s.tts_speed) == (True, True, "bm_lewis", 1.3)
        assert app.ai.speech is True  # replies now carry a spoken version
    _run(app, (60, 24), steps)


def test_help_names_the_read_aloud_key(tmp_path, monkeypatch):
    app, v, player = _tts_app(tmp_path, monkeypatch)

    async def steps(pilot):
        app.action_help()
        await pilot.pause()
        assert "ctrl+e" in app.screen.query_one("Markdown").source
    _run(app, (100, 30), steps)


def test_a_line_in_parts_uses_each_pre_generated_part_and_joins_them(tmp_path):
    eng = FakeEngine()
    tts.set_engine(eng)
    sp, player, s = _speaker(tmp_path)
    explanation = "Since $F = ma$, the force is $2 \\times 3 = 6\\ \\mathrm{N}$."
    pre = tts.ensure_audio(explanation, s.tts_voice, s.tts_speed, sp.audio_dir)  # what the foundry would write
    made = len(eng.calls)
    sp.say(["Correct. The answer is 6 N.", explanation])
    assert sp.wait_idle()
    time.sleep(0.05)
    assert len(eng.calls) == made + 1 and "Correct" in eng.calls[-1][0]  # only the verdict was made now
    (out,) = player.played
    assert out.parent == sp.live_dir and pre.is_file()
    assert frames(out)[3] == 240 + 240 * made + int(24000 * tts.PAUSE_SECONDS * 2)
    sp.close()


def test_the_app_and_the_chapter_script_agree_on_the_key(tmp_path):
    from tutorlib import speech
    if not hasattr(speech, "script_for_chapter") or speech.script_for_chapter({}, "") is None:
        pytest.skip("no chapter script")
    pack = {"teach": {"k1": {"establish": "Work done is $W = Fs$, in joules ($\\mathrm{J}$)."}}}
    lines = speech.script_for_chapter(pack, "")
    if not lines:
        pytest.skip("the stand-in speech module has no chapter script")
    line = next(l for l in lines if l["id"] == "card:k1:establish")
    folder = tmp_path / "audio"
    tts.set_engine(FakeEngine())
    path = tts.ensure_audio(pack["teach"]["k1"]["establish"], "bf_emma", 1.0, folder)
    assert path.name == f"{speech.audio_key(line['text'], 'bf_emma', 1.0)}.wav"


# ---------------- loudness ----------------
def test_the_player_plays_quieter_with_afplays_volume_flag(tmp_path):
    """Asked by the learner: the voice was too loud. `afplay -v` takes 1 as recorded and less as quieter."""
    fake = tmp_path / "afplay"
    out = tmp_path / "argv.txt"
    fake.write_text(f"#!/bin/sh\necho \"$@\" >> {out}\n")
    fake.chmod(0o755)
    p = tts.Player(binary=str(fake), volume=lambda: 0.4)
    assert p.play(tmp_path / "a.wav")
    p.wait()
    assert p.play(tmp_path / "b.wav", volume=0.25)  # a sample at a loudness not saved: it wins over the setting
    p.wait()
    full = tts.Player(binary=str(fake), volume=lambda: 1.0)
    assert full.play(tmp_path / "c.wav")  # as recorded: no flag at all, as before
    full.wait()
    wild = tts.Player(binary=str(fake), volume=lambda: 0.0)
    wild.play(tmp_path / "d.wav")  # never silent by accident: not under 10 %
    wild.wait()
    time.sleep(0.2)
    lines = out.read_text().splitlines()
    assert lines[0].startswith("-v 0.4 ") and lines[1].startswith("-v 0.25 ")
    assert lines[2].startswith(str(tmp_path / "c.wav")[:5]) and "-v" not in lines[2]
    assert lines[3].startswith("-v 0.1 ")


def test_the_loudness_setting_is_saved_clamped_and_read_back(tmp_path):
    (tmp_path / ".tutor").mkdir()
    config.Settings(tts_volume=0.4).save(tmp_path)
    assert config.Settings.load(tmp_path).tts_volume == 0.4
    (tmp_path / ".tutor/app_settings.json").write_text(json.dumps({"tts_volume": 5.0}))
    assert config.Settings.load(tmp_path).tts_volume == 1.0
    (tmp_path / ".tutor/app_settings.json").write_text(json.dumps({"tts_volume": 0.0}))
    assert config.Settings.load(tmp_path).tts_volume == 0.1
    (tmp_path / ".tutor/app_settings.json").write_text(json.dumps({"tts_volume": 1}))
    assert config.Settings.load(tmp_path).tts_volume == 1.0 and config.Settings().tts_volume == 1.0


def test_a_sample_plays_once_at_the_loudness_asked_and_the_next_line_goes_back_to_the_setting(tmp_path):
    tts.set_engine(FakeEngine())
    sp, player, s = _speaker(tmp_path, enabled=False)  # reading aloud is off: the sample still plays
    assert sp.sample(0.3)
    assert sp.wait_idle()
    time.sleep(0.05)
    assert player.volumes == [0.3]
    s.tts_enabled = True
    assert sp.say("A normal line.")
    assert sp.wait_idle()
    time.sleep(0.05)
    assert player.volumes == [0.3, None]  # the real Player then asks the settings
    sp.close()


def test_settings_has_a_loudness_box_and_a_button_to_hear_it_before_saving(tmp_path, monkeypatch):
    from textual.widgets import Input
    app, v, player = _tts_app(tmp_path, monkeypatch, enabled=True)
    heard = []
    monkeypatch.setattr(app.speaker, "sample", lambda volume, *a, **k: heard.append(volume) or True)

    async def steps(pilot):
        app.action_settings()
        await pilot.pause()
        scr = app.screen
        box = scr.query_one("#tts_volume", Input)
        assert box.value == "100"
        box.value = "35"
        scr.query_one("#tts_test").press()
        await pilot.pause()
        assert heard == [0.35] and config.Settings.load(v).tts_volume == 1.0  # heard, not saved yet
        box.value = "abc"
        scr.query_one("#tts_test").press()
        await pilot.pause()
        assert heard == [0.35]  # not a number: nothing played
        box.value = "35"
        scr.query_one("#save").press()
        await pilot.pause()
        assert config.Settings.load(v).tts_volume == 0.35 and app.settings.tts_volume == 0.35
    _run(app, (60, 24), steps)
