"""Floating accumulation must not move an exact 15% bias across its policy threshold."""
import copy
from datetime import timedelta

import pytest

from fixtures import make_vault
from test_v110 import T0, answer
from tutorlib import model, session, store


def events(total, right, confidence):
    return [answer(correct=n < right, conf=confidence, ts=T0 + timedelta(minutes=n))
            for n in range(total)]


def folded(total, right, confidence=4):
    state = model.new_state()
    for event in events(total, right, confidence):
        model.apply(state, event)
    return state


@pytest.mark.parametrize("total", [40, 60, 80, 100, 120, 200])
def test_equivalent_exact_fifteen_percent_histories_keep_training_off(total):
    state = folded(total, total * 4 // 5)
    assert model.calibration(state)["bias"] == pytest.approx(0.15)
    assert model.knobs(state)["confidence_training"] is False


@pytest.mark.parametrize("confidence, right, enabled", [
    (4, 47, True), (4, 48, False), (4, 49, False),
    (1, 23, False), (1, 24, False), (1, 25, True),
])
def test_real_bias_below_and_above_both_threshold_sides_keeps_its_policy(confidence, right, enabled):
    assert model.knobs(folded(60, right, confidence))["confidence_training"] is enabled


def test_threshold_query_preserves_recorded_floats_history_and_replay(tmp_path):
    tutor = session.Tutor(store.Vault(make_vault(tmp_path)), now=lambda: T0)
    for event in events(60, 48, 4):
        tutor.log(event)
    state = copy.deepcopy(tutor.state)
    history = {p: p.read_bytes() for p in (tutor.vault.tutor / "events").glob("*.jsonl")}
    cache = tutor.state_path.read_bytes()
    assert tutor.state["traits"]["calibration"]["sum_conf"] > 57.0

    assert model.knobs(tutor.state)["confidence_training"] is False

    assert tutor.state == state
    restarted = session.Tutor(tutor.vault, now=lambda: T0)
    assert restarted.state == state == restarted._fold()
    assert model.knobs(restarted.state)["confidence_training"] is False
    assert tutor.state_path.read_bytes() == cache
    assert all(p.read_bytes() == data for p, data in history.items())
