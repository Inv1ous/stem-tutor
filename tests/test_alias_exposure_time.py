"""Canonical exposure aliases use the latest instant, including DST offsets."""
import copy
import json
import random
from datetime import datetime

import pytest

from test_fixed_batch_uniqueness import KC, OTHER_KC, _setup
from tutorlib import model, session, store


@pytest.mark.parametrize("zone, first, second, report_time, expected", [
    ("America/New_York", "2026-11-01T01:30:00-04:00", "2026-11-01T01:15:00-05:00",
     "2026-11-08T01:45:00-05:00", "fresh-independent"),
    ("Asia/Hong_Kong", "2026-11-01T13:30:00+08:00", "2026-11-01T14:15:00+08:00",
     "2026-11-08T14:00:00+08:00", "fresh-independent"),
    ("America/New_York", "2026-11-01T01:30:00-04:00", "2026-11-01T01:45:00-04:00",
     "2026-11-08T01:45:00-05:00", "9702-2.1-i01"),
])
def test_public_alias_exposures_preserve_seven_day_freshness_by_instant(
        tmp_path, zone, first, second, report_time, expected):
    original, _, source = _setup(tmp_path, aliases=True)
    root = original.vault.root
    (root / ".tutor/config.json").write_text(json.dumps({"tz": zone}))
    content = json.loads(source.read_text())
    content["items"][0]["difficulty"] = 1
    alternative = copy.deepcopy(content["items"][0])
    alternative.update(id="fresh-independent", source={"type": "past", "qid": "9702_s23_12_q2"}, difficulty=5)
    content["items"].append(alternative)
    source.write_text(json.dumps(content))
    clock = [datetime.fromisoformat(first)]
    tutor = session.Tutor(store.Vault(root), rng=random.Random(0), now=lambda: clock[0])
    for kc, when, ident in ((KC, first, "9702-2.1-i01"), (OTHER_KC, second, "9702-2.1-i51")):
        clock[0] = datetime.fromisoformat(when).astimezone(tutor.vault.tz)
        tutor.start("test", 20, focus=[kc])
        question, = tutor.next()["items"]
        assert tutor.session["presented"][str(question["n"])]["item"] == ident
        tutor.answer(f"{question['n']}?")
        tutor.end()
    assert tutor.state["items_seen"] == {"9702-2.1-i01": first, "9702-2.1-i51": second}
    clock[0] = datetime.fromisoformat(report_time).astimezone(tutor.vault.tz)
    before = copy.deepcopy(tutor.state)
    source_bytes = source.read_bytes()
    history = {path: path.read_bytes() for path in tutor.vault.tutor.glob("events/*.jsonl")}
    target = model.p_correct(tutor.state["kcs"][KC]["theta"], 1)

    selected = tutor.packs.select_item(KC, tutor.state, target, random.Random(0), clock[0])

    assert selected["id"] == expected
    assert tutor.state == before
    restarted = session.Tutor(store.Vault(root), now=lambda: clock[0])
    restarted.rebuild()
    assert restarted.packs.select_item(KC, restarted.state, target, random.Random(0), clock[0])["id"] == expected
    assert restarted.state == before
    assert source.read_bytes() == source_bytes
    assert all(path.read_bytes() == data for path, data in history.items())
