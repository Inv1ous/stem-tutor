"""Clock rollback must not turn future history into the last28calendar days."""
import copy
from datetime import timedelta

import pytest

from test_fixed_batch_uniqueness import KC, _setup
from tutorlib import profile, session, store


@pytest.mark.parametrize("offset, expected, streak", [(1, 0, 0), (0, 1, 1), (-27, 1, 0), (-28, 0, 0)])
def test_public_completed_study_day_uses_current_last28_window_without_rewriting_history(
        tmp_path, offset, expected, streak):
    tutor, clock, source = _setup(tmp_path)
    report_time = clock[0]
    clock[0] += timedelta(days=offset)
    tutor.start("test", 20, focus=[KC])
    question, = tutor.next()["items"]
    tutor.answer(f"{question['n']}?")
    tutor.end()
    clock[0] = report_time
    assert tutor.state["study_days"] == [(report_time + timedelta(days=offset)).date().isoformat()]
    before = copy.deepcopy(tutor.state)
    source_bytes = source.read_bytes()
    history = {path: path.read_bytes() for path in tutor.vault.tutor.glob("events/*.jsonl")}

    habits = profile.summary(tutor.state, tutor.packs, report_time)["habits"]

    assert habits["last_28"] == expected
    assert habits["streak"] == streak
    assert tutor.state == before
    restarted = session.Tutor(store.Vault(tutor.vault.root), now=lambda: report_time)
    restarted.rebuild()
    assert profile.summary(restarted.state, restarted.packs, report_time)["habits"] == habits
    assert restarted.state == before
    assert source.read_bytes() == source_bytes
    assert all(path.read_bytes() == data for path, data in history.items())
