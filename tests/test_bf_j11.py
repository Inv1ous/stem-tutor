from __future__ import annotations

import json
import random
from datetime import datetime
from pathlib import Path

import pytest

from fixtures import make_vault
from tutorlib import report, session, store

T0 = datetime.fromisoformat("2026-09-29T17:00:00+08:00")
KC = "9702-2.1.1"


@pytest.fixture
def tutor(tmp_path: Path) -> session.Tutor:
    return session.Tutor(store.Vault(make_vault(tmp_path)), rng=random.Random(0), now=lambda: T0)


def _question(tutor: session.Tutor) -> int:
    item = next(i for i in tutor.packs.items_for(KC) if i["kind"] == "mcq")
    return tutor._present(item, block="practice", phase=None)["n"]


def _planner(tutor: session.Tutor) -> Path:
    planner = tutor.vault.root / "Almanac.html"
    store.write_text(planner, "<html></html>")
    tutor.packs.plan["source_path"] = str(planner)
    return planner.with_suffix(".tutor.js")


def _synced(path: Path) -> dict:
    return json.loads(path.read_text().removeprefix("window.TUTOR_SYNC = ").strip().removesuffix(";"))


def test_a_restart_keeps_the_corrected_grade_when_re_marking_is_interrupted(tutor, monkeypatch):
    """B-063 (bug watch): a durable re-mark must never leave a cache claiming the wrong grade is current."""
    tutor.start("test", focus=[KC])
    n = _question(tutor)
    fb = tutor.answer(f"{n}?")["results"][0]
    assert tutor.state["kcs"][KC]["succ_days"] == []
    log = tutor.log

    def log_then_stop(event: dict) -> dict:
        saved = log(event)
        if event["type"] == "regrade":
            raise RuntimeError("interrupted after logging the re-mark")
        return saved

    monkeypatch.setattr(tutor, "log", log_then_stop)
    with pytest.raises(RuntimeError, match="interrupted"):
        tutor.regrade(fb["event"], "The answer key was wrong")
    restarted = session.Tutor(tutor.vault, now=lambda: T0)
    assert restarted.state["kcs"][KC]["succ_days"] == [T0.date().isoformat()]
    assert restarted.state == restarted._fold()


@pytest.mark.parametrize("elapsed", [0, 11])
def test_the_almanac_shows_completed_answers_even_when_the_learner_pauses(tutor, monkeypatch, elapsed):
    """B-046 (bug watch): the final export has the new counts and only questions still open, within ten seconds too."""
    sync = _planner(tutor)
    tick = [100.0]
    monkeypatch.setattr(session.time, "monotonic", lambda: tick[0])
    tutor.start("test", focus=[KC])
    first, second = _question(tutor), _question(tutor)
    tick[0] += elapsed
    key = tutor.session["presented"][str(first)]["inst"]["answer"]
    tutor.answer(f"{first}{key}3")
    live = _synced(sync)["session"]
    assert (live["answered"], live["correct"]) == (1, 1)
    assert live["now"] == [tutor.packs.kc(KC)["title"]]
    tutor.answer(f"{second}?")
    live = _synced(sync)["session"]
    assert (live["answered"], live["correct"]) == (2, 1)
    assert live["now"] == []


@pytest.mark.parametrize("when", ["latest", "earlier", "ended"])
def test_re_marking_refreshes_the_almanac_counts_and_mistakes(tutor, monkeypatch, when):
    """B-066 (bug watch): a corrected mark reaches the planner after rebuilding state and repairing the session."""
    sync = _planner(tutor)
    monkeypatch.setattr(session.time, "monotonic", lambda: 100.0)
    tutor.start("test", focus=[KC])
    n = _question(tutor)
    fb = tutor.answer(f"{n}?")["results"][0]
    if when == "earlier":
        tutor._last_mark = None
    elif when == "ended":
        tutor.end()
    report.almanac_push(tutor)  # isolate the re-mark from the answer-sync bug
    before = _synced(sync)
    assert before["today"]["right"] == 0 and before["err"] == {"Could not recall": 1}
    assert tutor.regrade(fb["event"], "The answer key was wrong")["ok"]
    sent = _synced(sync)
    assert sent["today"]["right"] == 1 and sent["err"] == {}
    if when != "ended":
        assert (sent["session"]["answered"], sent["session"]["correct"]) == (1, 1)
    assert sent == report.almanac_payload(tutor)


def test_paper_marks_still_reach_the_almanac_after_answer_sync_moves(tutor, monkeypatch):
    """B-046 (bug watch): paper answers bypass session marking, so send their completed result too."""
    sync = _planner(tutor)
    monkeypatch.setattr(session.time, "monotonic", lambda: 100.0)
    tutor.start("test", focus=[KC])
    tutor.paper_score("9702_s23_qp_22", "1a=2/2, 1b=0/3")
    sent = _synced(sync)
    assert (sent["today"]["answers"], sent["today"]["right"]) == (2, 1)
    assert sent == report.almanac_payload(tutor)
