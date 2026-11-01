"""Manual paper marks admit only finite arithmetic and one count per assessed KC."""
import json
import math

import pytest

from fixtures import make_vault
from test_session import T0
from tutorlib import session, store


PAPER = "9702_s23_qp_22"
HUGE = "9" * 400
FINITE = "9" * 308


def file_bytes(root):
    return {p.relative_to(root): p.read_bytes() for p in root.rglob("*") if p.is_file()}


@pytest.mark.parametrize("text", [f"1a={HUGE}/{HUGE}", f"1a=1/{HUGE}",
                                  f"1a=2/2,1b={HUGE}/{HUGE}", f"1a=2/2,9z=0/{HUGE}",
                                  f"1a={HUGE}/{HUGE},1a=2/2",
                                  f"1a={FINITE}/{FINITE},1b={FINITE}/{FINITE}",
                                  f"1a=1/{FINITE},1b=1/{FINITE}"],
                         ids=["infinite-row", "infinite-denominator", "later-infinite-row",
                              "unknown-infinite-row", "overwritten-infinite-row", "score-sum-overflow",
                              "denominator-sum-overflow"])
def test_nonfinite_paper_rows_and_aggregates_refuse_before_any_event(tmp_path, text):
    root = make_vault(tmp_path)
    tutor = session.Tutor(store.Vault(root), now=lambda: T0)
    before = file_bytes(root)
    state = json.loads(json.dumps(tutor.state))

    result = tutor.paper_score(PAPER, text)

    assert result.get("ok") is False and result.get("error")
    assert not list(tutor.vault.events())
    assert tutor.state == state
    assert file_bytes(root) == before
    assert not tutor.paper_list()[0]["done"]


def test_large_finite_paper_ratio_does_not_overflow_percentage(tmp_path):
    tutor = session.Tutor(store.Vault(make_vault(tmp_path)), now=lambda: T0)

    result = tutor.paper_score(PAPER, f"1a={FINITE}/{FINITE}")

    assert result["percent"] == 100.0
    assert math.isfinite(result["score"]) and math.isfinite(result["max"])
    json.dumps(list(tutor.vault.events()), allow_nan=False)
    json.dumps(tutor.state, allow_nan=False)
    restarted = session.Tutor(tutor.vault, now=lambda: T0)
    assert restarted.state == restarted._fold() == tutor.state


@pytest.mark.parametrize("text,score,maximum,percent", [("1a=2/2,1b=1/3", 3, 5, 5.0),
                                                       ("1a=0.5/2.5", .5, 2.5, .8),
                                                       ("1a=0/2", 0, 2, 0.0),
                                                       ("1a=0/2,1a=2/2", 2, 2, 3.3),
                                                       ("1a=1/2,9z=2/2", 1, 2, 1.7)])
def test_ordinary_manual_fractions_preserve_result_and_replay(tmp_path, text, score, maximum, percent):
    tutor = session.Tutor(store.Vault(make_vault(tmp_path)), now=lambda: T0)
    tutor.vault.append_event({"type": "note", "text": "Original learner history"}, now=T0)
    prefix = {p: p.read_bytes() for p in (tutor.vault.tutor / "events").glob("*.jsonl")}

    result = tutor.paper_score(PAPER, text)

    assert (result["score"], result["max"], result["percent"]) == (score, maximum, percent)
    assert result["partial"] is True
    assert all(p.read_bytes().startswith(data) for p, data in prefix.items())
    restarted = session.Tutor(tutor.vault, now=lambda: T0)
    assert restarted.state == restarted._fold() == tutor.state


@pytest.mark.parametrize("kcs,unique", [(["9702-2.1.1", "9702-2.1.1"], ["9702-2.1.1"]),
                                      (["9702-2.1.4", "9702-2.1.1", "9702-2.1.4", "9702-2.1.1"],
                                       ["9702-2.1.4", "9702-2.1.1"])])
def test_new_manual_paper_answer_counts_each_kc_once_without_revising_metadata_or_history(tmp_path, kcs, unique):
    root = make_vault(tmp_path)
    source = root / ".tutor/packs/v1/papers.json"
    papers = json.loads(source.read_text())
    papers["papers"][0]["questions"][0]["kcs"] = kcs
    source.write_text(json.dumps(papers))
    metadata = source.read_bytes()
    vault = store.Vault(root)
    prior = vault.append_event({"type": "answer", "item": "older-paper-answer", "kcs": kcs,
                                "difficulty": 4, "subject": "phys", "marks": 2,
                                "grade": {"correct": True, "score": 1.0, "error": None}}, now=T0)
    prefix = {p: p.read_bytes() for p in (vault.tutor / "events").glob("*.jsonl")}
    tutor = session.Tutor(vault, now=lambda: T0)
    before = {kc: tutor.state["kcs"][kc]["n"] for kc in unique}

    result = tutor.paper_score(PAPER, "1a=2/2")

    answer, = [e for e in vault.events() if e.get("session") == result["session"] and e["type"] == "answer"]
    assert answer["kcs"] == unique
    assert all(tutor.state["kcs"][kc]["n"] == count + 1 for kc, count in before.items())
    assert tutor.packs.papers[0]["questions"][0]["kcs"] == kcs
    assert source.read_bytes() == metadata
    assert next(e for e in vault.events() if e["id"] == prior["id"]) == prior
    assert all(p.read_bytes().startswith(data) for p, data in prefix.items())
    restarted = session.Tutor(vault, now=lambda: T0)
    assert restarted.state == restarted._fold() == tutor.state
