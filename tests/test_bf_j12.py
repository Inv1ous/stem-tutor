from __future__ import annotations

import random

import pytest

from fixtures import make_vault
from tutorlib import session, store


@pytest.mark.parametrize("pending", [False, True])
def test_an_interrupted_end_cannot_resume_or_end_twice(tmp_path, monkeypatch, pending):
    """B-079: the logged session end closes even a stale saved session."""
    tutor = session.Tutor(store.Vault(make_vault(tmp_path)), rng=random.Random(0))
    tutor.start("test", focus=["9702-2.1"])
    questions = tutor.next()["items"]
    if not pending:
        for q in questions:
            tutor.answer(f"{q['n']}?")
    sid = tutor.session["id"]
    log = tutor.log

    def interrupted(event: dict) -> dict:
        result = log(event)
        if event["type"] == "session_end":
            raise RuntimeError("interrupted after saving the end event")
        return result

    monkeypatch.setattr(tutor, "log", interrupted)
    with pytest.raises(RuntimeError, match="interrupted"):
        tutor.end()
    restarted = session.Tutor(tutor.vault)
    assert restarted.session is None
    assert restarted.next()["activity"] == "no_session"
    restarted.end()
    assert len([e for e in tutor.vault.events() if e["type"] == "session_end" and e["session"] == sid]) == 1
    assert store.read_json(tutor.session_path) is None
    assert session.Tutor(tutor.vault).session is None
    restarted.start("test", focus=["9702-2.1"])
    assert session.Tutor(tutor.vault).session["id"] == restarted.session["id"]
