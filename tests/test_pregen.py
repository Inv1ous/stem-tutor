"""Pre-generating read-aloud audio: the shared module, the sign hooks of the foundry and refine, and the tts commands.
A fake engine stands in for Kokoro; nothing is installed, downloaded or synthesised, and no real vault is touched."""
import json
import sys
from pathlib import Path

import pytest

from test_foundry import SUB, fdy  # noqa: F401  (fixtures)
from test_refine import rf  # noqa: F401

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "foundry"))
import pregen  # noqa: E402
from tutor_app import tts  # noqa: E402
from tutorlib import speech  # noqa: E402


def distinct(lines, voice="bf_emma", speed=1.0):
    """Lines that need their own file: two identical sentences share one."""
    return len({speech.audio_key(ln["text"], voice, speed) for ln in lines})


class Fake:
    def __init__(self, fail_on=""):
        self.calls, self.fail_on = [], fail_on

    def create(self, text, voice, speed, lang):
        self.calls.append(text)
        if self.fail_on and self.fail_on in text:
            raise RuntimeError("boom")
        return [0.0] * 240, 24000


@pytest.fixture
def chapter(fdy, tmp_path, monkeypatch):  # noqa: F811
    """A small signed chapter in the scratch tree, a scratch vault, a fake engine (set up), and the real engine untouched."""
    path = tmp_path / f"build/out/packs/9702/{SUB}.json"
    pack = json.loads(path.read_text())
    pack["items"][0]["speech"] = "Say this exactly."  # an author's override of the first stem
    path.write_text(json.dumps(pack))
    monkeypatch.setenv("STEM_TUTOR_VAULT", str(tmp_path / "vault"))
    monkeypatch.setenv("FOUNDRY_PREGEN", "1")
    fake = Fake()
    tts.set_engine(fake)
    yield type("C", (), {"fd": fdy, "fake": fake, "audio": tmp_path / "audio", "root": tmp_path})
    tts.set_engine(None)


def test_chapter_lines_read_the_pack_and_the_note(chapter):
    lines = pregen.chapter_lines(SUB)
    ids = [ln["id"] for ln in lines]
    assert f"card:{SUB}.1:motivate" in ids and f"item:{SUB}-i01:hint1" in ids and "note:1" in ids
    assert not [i for i in ids if i.startswith(f"item:{SUB}-i02")]  # drawn at run time: nothing fixed to say
    assert all(ln["text"] and "$" not in ln["text"] for ln in lines)
    assert next(ln for ln in lines if ln["id"] == f"item:{SUB}-i01:stem")["text"].startswith("Say this exactly")


def test_pregenerate_names_files_by_key_and_a_second_run_makes_none(chapter):
    r = pregen.pregenerate(SUB, "bf_emma", 1.0, chapter.audio, log=lambda m: None)
    lines = pregen.chapter_lines(SUB)
    assert r["made"] == distinct(lines) and r["cached"] == len(lines) - distinct(lines) and r["errors"] == 0 and not r["unavailable"]
    for ln in lines:
        assert (chapter.audio / f"{speech.audio_key(ln['text'], 'bf_emma', 1.0)}.wav").is_file()
    again = pregen.pregenerate(SUB, "bf_emma", 1.0, chapter.audio, log=lambda m: None)
    assert again["made"] == 0 and again["cached"] == len(lines)
    other = pregen.pregenerate(SUB, "bm_george", 1.0, chapter.audio, log=lambda m: None)  # another voice: new files
    assert other["made"] == distinct(lines, "bm_george")


def test_the_script_json_lists_id_text_key_and_file(chapter):
    pregen.pregenerate(SUB, "bf_emma", 1.1, chapter.audio, log=lambda m: None)
    data = json.loads((chapter.root / f"build/out/speech/{SUB}.json").read_text())
    assert data["sub"] == SUB and data["voice"] == "bf_emma" and data["speed"] == 1.1
    row = data["lines"][0]
    assert row["key"] == speech.audio_key(row["text"], "bf_emma", 1.1) and row["file"] == row["key"] + ".wav"


def test_a_failing_line_is_counted_not_raised_and_the_rest_are_made(chapter):
    tts.set_engine(Fake(fail_on="Which has a direction"))
    logged = []
    r = pregen.pregenerate(SUB, "bf_emma", 1.0, chapter.audio, log=logged.append)
    assert r["errors"] == 1 and r["made"] == distinct(pregen.chapter_lines(SUB)) - 1
    assert any(f"item:{SUB}-i01:hint1" in m and "boom" in m for m in logged)
    tts.set_engine(Fake())
    assert pregen.pregenerate(SUB, "bf_emma", 1.0, chapter.audio, log=lambda m: None)["made"] == 1  # resumes


def test_limit_leaves_the_rest_for_next_time(chapter):
    r = pregen.pregenerate(SUB, "bf_emma", 1.0, chapter.audio, log=lambda m: None, limit=2)
    assert r["made"] == 2 and r["skipped"] == distinct(pregen.chapter_lines(SUB)) - 2


def test_without_kokoro_only_the_script_is_written(chapter, monkeypatch):
    tts.set_engine(None)
    monkeypatch.setattr(tts, "available", lambda vault=None: False)
    r = pregen.pregenerate(SUB, "bf_emma", 1.0, chapter.audio, log=lambda m: None)
    assert r["unavailable"] and r["made"] == 0 and r["skipped"] == len(pregen.chapter_lines(SUB))
    assert (chapter.root / f"build/out/speech/{SUB}.json").is_file()
    assert not chapter.audio.exists() or not list(chapter.audio.glob("*.wav"))


def test_a_speech_override_is_spoken_verbatim_and_keyed_by_its_text(chapter):
    pregen.pregenerate(SUB, "bf_emma", 1.0, chapter.audio, log=lambda m: None)
    key = speech.audio_key("Say this exactly.", "bf_emma", 1.0)
    assert (chapter.audio / f"{key}.wav").is_file() and "Say this exactly." in chapter.fake.calls


def test_gaps_are_listed_per_line_and_overridden_lines_have_none(chapter, monkeypatch):
    pack = json.loads((chapter.root / f"build/out/packs/9702/{SUB}.json").read_text())
    monkeypatch.setattr(speech, "speech_gaps", lambda t: ["\\weirdcmd"] if "decelerates" in t else [])
    r = pregen.pregenerate(SUB, "bf_emma", 1.0, chapter.audio, log=lambda m: None)
    assert r["gaps"] == [{"id": f"item:{SUB}-i03:stem", "symbols": ["\\weirdcmd"]}] and pack["items"][0]["speech"]
    assert pregen.gaps_report() == {SUB: r["gaps"]}


def test_status_counts_audio_and_missing(chapter):
    assert pregen.status("bf_emma", 1.0, chapter.audio)[0]["audio"] == 0
    pregen.pregenerate(SUB, "bf_emma", 1.0, chapter.audio, log=lambda m: None, limit=3)
    row = pregen.status("bf_emma", 1.0, chapter.audio)[0]
    assert row["sub"] == SUB and 3 <= row["audio"] < row["lines"] and row["missing"] == row["lines"] - row["audio"]


# ---------------- the sign hooks ----------------
def started(monkeypatch):
    calls = []
    monkeypatch.setattr(pregen.subprocess, "Popen", lambda *a, **k: calls.append((a, k)))
    return calls


def sign_ready(mod, sub=SUB):
    with mod.chapter(sub) as st:
        st["stage"] = "sign"


def test_foundry_sign_starts_a_detached_process_when_kokoro_is_ready(chapter, monkeypatch):
    calls = started(monkeypatch)
    fd = chapter.fd
    fd.cmd_add([SUB])
    sign_ready(fd)
    fd.cmd_sign(SUB)
    assert len(calls) == 1
    args, kw = calls[0]
    assert kw["start_new_session"] is True and args[0][-6:-4] == ["run", SUB]
    assert (chapter.root / "foundry/logs").is_dir()
    assert fd.load(SUB)["stage"] == "ready"
    assert any("pre-generating" in h["note"] for h in fd.load(SUB)["history"])


def test_without_kokoro_signing_writes_the_script_and_notes_it_once(chapter, monkeypatch):
    tts.set_engine(None)
    monkeypatch.setattr(tts, "available", lambda vault=None: False)
    calls = started(monkeypatch)
    fd = chapter.fd
    fd.cmd_add([SUB])
    sign_ready(fd)
    fd.cmd_sign(SUB)
    assert not calls and (chapter.root / f"build/out/speech/{SUB}.json").is_file()
    notes = [h["note"] for h in fd.load(SUB)["history"] if h["note"].startswith("speech:")]
    assert notes == ["speech: not set up (run tutor tts setup)"]


def test_a_tts_failure_never_blocks_or_fails_the_sign(chapter, monkeypatch):
    def boom(vault=None):
        raise RuntimeError("tts exploded")
    monkeypatch.setattr(tts, "available", boom)
    fd = chapter.fd
    fd.cmd_add([SUB])
    sign_ready(fd)
    fd.cmd_sign(SUB)
    assert fd.load(SUB)["stage"] == "ready"
    monkeypatch.setattr(tts, "available", lambda vault=None: True)
    monkeypatch.setattr(pregen.subprocess, "Popen", lambda *a, **k: (_ for _ in ()).throw(OSError("no fork")))
    assert pregen.hook(SUB, chapter.root / "foundry/logs") == "error"


def test_the_hook_can_be_switched_off(chapter, monkeypatch):
    monkeypatch.setenv("FOUNDRY_PREGEN", "0")
    calls = started(monkeypatch)
    assert pregen.hook(SUB, chapter.root / "foundry/logs") == "off" and not calls


def test_refine_sign_starts_pregeneration_with_its_own_log(rf, tmp_path, monkeypatch):  # noqa: F811
    monkeypatch.setenv("STEM_TUTOR_VAULT", str(tmp_path / "vault"))
    monkeypatch.setenv("FOUNDRY_PREGEN", "1")
    monkeypatch.setattr(tts, "available", lambda vault=None: True)
    calls = started(monkeypatch)
    rf.cmd_add([SUB])
    with rf.chapter(SUB) as st:
        st["stage"] = "sign"
    rf.cmd_sign(SUB)
    assert len(calls) == 1 and (tmp_path / "refine/logs").is_dir()
    assert any("pre-generating" in h["note"] for h in rf.load(SUB)["history"])


# ---------------- the command line ----------------
def test_tts_status_table(chapter, capsys):
    pregen.pregenerate(SUB, "bf_emma", 1.0, tts.audio_dir(pregen.vault()), log=lambda m: None, limit=2)
    assert pregen.cli(["status"]) == 0
    out = capsys.readouterr().out
    assert "Kokoro: ready" in out and SUB in out and "partial" in out and "1 chapters: 0 with all audio, 1 partial" in out
    tts.set_engine(None)
    pregen.cli(["status"])
    assert "Kokoro: not set up" in capsys.readouterr().out or tts.available()


def test_tts_all_runs_each_chapter_in_turn_with_a_progress_line(chapter, capsys):
    assert pregen.cli(["--all", "--voice", "bm_lewis", "--speed", "1.2"]) == 0
    out = capsys.readouterr().out
    assert f"[1/1] {SUB}:" in out
    n = distinct(pregen.chapter_lines(SUB), "bm_lewis", 1.2)
    assert len(list(tts.audio_dir(pregen.vault()).glob("*.wav"))) == n
    assert pregen.cli([SUB, "--voice", "bm_lewis", "--speed", "1.2"]) == 0
    assert "made 0" in capsys.readouterr().out
    assert pregen.cli(["9702-9.9"]) == 1


def test_foundry_and_refine_commands_reach_the_same_cli(chapter, capsys):
    chapter.fd.main(["tts", "status"])
    assert "Kokoro:" in capsys.readouterr().out
    chapter.fd.main(["tts", SUB])
    assert "made" in capsys.readouterr().out
    with pytest.raises(SystemExit):
        chapter.fd.main(["tts", "9702-9.9"])


def test_coverage_lists_chapters_with_speech_gaps(chapter, monkeypatch, capsys):
    monkeypatch.setattr(speech, "speech_gaps", lambda t: ["\\foo", "U+F0E6"] if "decelerates" in t else [])
    pregen.pregenerate(SUB, "bf_emma", 1.0, chapter.audio, log=lambda m: None)
    assert chapter.fd.coverage()["speech_gaps"][SUB][0]["symbols"] == ["\\foo", "U+F0E6"]
    chapter.fd.cmd_coverage([])
    out = capsys.readouterr().out
    assert "no sensible spoken form" in out and f"item:{SUB}-i03:stem (\\foo U+F0E6)" in out
