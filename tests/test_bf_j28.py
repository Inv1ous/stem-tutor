from __future__ import annotations

import random
from datetime import datetime, timedelta

import pytest

from fixtures import make_vault
from tutorlib import report, session, store


@pytest.fixture
def tutor(tmp_path, monkeypatch):
    monkeypatch.setattr(report, "almanac_push", lambda tutor: None)
    return session.Tutor(store.Vault(make_vault(tmp_path)), rng=random.Random(0),
                         now=lambda: datetime.fromisoformat("2026-09-29T17:00:00+08:00"))


def missed_answer(tutor, diagnosis: str | None) -> dict:
    tutor.start("review", minutes=10)
    item = next(i for i in tutor.packs.items_for("9702-2.1.1") if i["kind"] == "mcq")
    if diagnosis == "NOTATION":
        item = next(i for i in tutor.packs.items_for("9702-2.1.4") if i["kind"] == "numeric")
    n = tutor._present(item, block="practice", phase=None)["n"]
    inst = tutor.session["presented"][str(n)]["inst"]
    if diagnosis == "NOTATION":
        entry = f"{n} = {inst['answer']['value'] / 1000:.3g} m ~3"
    elif diagnosis == "RECALL":
        entry = f"{n}?"
    else:
        option = next(k for k in inst["options"] if k != inst["answer"]
                      and (k in inst.get("distractors", {})) == (diagnosis == "CONCEPT"))
        entry = f"{n}{option}3"
    feedback = tutor.answer(entry)["results"][0]
    answer = next(e for e in tutor.vault.events() if e["id"] == feedback["event"])
    assert answer["grade"]["error"] == diagnosis
    return answer


@pytest.mark.parametrize("code, label", [("SLIP", "careless slips"), ("TIME", "Ran out of time"),
                                         ("STRATEGY", "Wrong method")])
@pytest.mark.parametrize("diagnosis", ["NOTATION", "CONCEPT", "RECALL"])
def test_mistake_journal_uses_the_learners_latest_reason(tutor, diagnosis, code, label):
    """B-084: the journal must honour the reason the learner corrected."""
    answer = missed_answer(tutor, diagnosis)
    assert tutor.tag(answer["id"], "MISREAD")["ok"]
    assert tutor.tag(answer["id"], code)["ok"]
    text = (tutor.vault.root / report.mistakes_note(tutor)).read_text()
    assert f"- **29 Sep** · {label}" in text
    assert next(e for e in tutor.vault.events() if e["id"] == answer["id"])["grade"] == answer["grade"]
    assert tutor.regrade(answer["id"], "accepted on review")["ok"]
    assert "No mistakes yet." in (tutor.vault.root / report.mistakes_note(tutor)).read_text()


@pytest.mark.parametrize("diagnosis", [None, "NOTATION"])
def test_weekly_retrospective_uses_the_learners_latest_reason_and_advice(tutor, diagnosis):
    """B-105: the weekly cause and advice must agree with the tagged profile count."""
    answer = missed_answer(tutor, diagnosis)
    before = report.almanac_payload(tutor)
    # A correction next week still belongs to the week of the answer.
    later = tutor.now() + timedelta(days=7)
    tutor.now = lambda: later
    assert tutor.tag(answer["id"], "SLIP")["ok"]
    assert tutor.tag(answer["id"], "MISREAD")["ok"]
    payload = report.almanac_payload(tutor)
    assert payload["err"] == {"Misread the question": 1}
    assert "Most misses: Misread the question ×1." in payload["retro"]["5"]["broke"]
    assert payload["retro"]["5"]["fix"] == report.ADVICE["Misread the question"]
    assert payload["stamp"] != before["stamp"]
    assert tutor.regrade(answer["id"], "accepted on review")["ok"]
    assert "Most misses:" not in report.almanac_payload(tutor)["retro"]["5"]["broke"]
