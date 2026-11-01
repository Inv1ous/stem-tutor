"""Learn counts staged practice questions rather than assumed two-item batches."""
import copy
import json
import random

import pytest

from fixtures import make_vault
from test_session import T0, _answer_all
from tutorlib import session, store


def new_tutor(tmp_path, pool, one_at_a_time):
    root = make_vault(tmp_path)
    path = root / ".tutor/packs/v1/specs/9702/packs/9702-2.1.json"
    pack = json.loads(path.read_text())
    if pool == "template":
        pack["items"] = [pack["items"][1]]
    elif pool == "fixed":
        item = copy.deepcopy(pack["items"][1])
        item.pop("template")
        item["answer"]["value"] = 20
        pack["items"] = [{**copy.deepcopy(item), "id": "fixed-a"}, {**copy.deepcopy(item), "id": "fixed-b"}]
    else:
        pack["items"] = [pack["items"][-1]]  # structured source is not an eligible short-practice kind
    path.write_text(json.dumps(pack))
    tutor = session.Tutor(store.Vault(root), rng=random.Random(1), now=lambda: T0,
                          one_at_a_time=one_at_a_time)
    tutor.start("learn", minutes=30, focus=["9702-2.1.4"])
    return tutor, path, path.read_bytes()


def drive(tutor, restart=False):
    first_staged = None
    restarted = False
    views = []
    for _ in range(50):
        activity = tutor.next()
        kind = activity["activity"]
        if kind == "end":
            return tutor, first_staged, views
        if kind in ("questions", "awaiting"):
            phase = activity.get("phase")
            if phase == "practice":
                views.append(len(activity["items"]))
                if first_staged is None:
                    first_staged = len(tutor.session["presented"]) + len(tutor.session.get("queue", {}))
                if restart and not restarted:
                    previous = tutor.session["blocks"][tutor.session["cursor"]].get("practiced", 0)
                    tutor = session.Tutor(tutor.vault, now=lambda: T0, one_at_a_time=tutor.one_at_a_time)
                    assert tutor.session["blocks"][tutor.session["cursor"]].get("practiced", 0) == previous
                    restarted = True
            _answer_all(tutor, activity, good=True)
        elif kind in ("worked", "walkthrough"):
            tutor.respond({"done": True})
        else:
            tutor.respond({})
    pytest.fail("Public Learn did not terminate within its finite lesson steps")


@pytest.mark.parametrize("one_at_a_time", [False, True])
@pytest.mark.parametrize("restart", [False, True])
def test_single_template_practice_opens_all_three_real_instances(tmp_path, one_at_a_time, restart):
    tutor, path, source = new_tutor(tmp_path, "template", one_at_a_time)
    prefix = {p: p.read_bytes() for p in (tutor.vault.tutor / "events").glob("*.jsonl")}

    tutor, first, _ = drive(tutor, restart)

    answers = [e for e in tutor.vault.events() if e.get("phase") == "practice"]
    assert len(answers) == 3
    assert first == 1
    block = next(b for b in tutor.session["blocks"] if b["kind"] == "learn")
    assert block["practiced"] == 3
    assert all(e["item"] == "9702-2.1-i02" and e["params"] for e in answers)
    assert path.read_bytes() == source
    assert all(p.read_bytes().startswith(data) for p, data in prefix.items())
    assert tutor.state == tutor._fold()


@pytest.mark.parametrize("one_at_a_time", [False, True])
def test_full_two_question_batch_counts_queue_and_only_one_final_slot(tmp_path, one_at_a_time):
    tutor, path, source = new_tutor(tmp_path, "fixed", one_at_a_time)

    tutor, first, sizes = drive(tutor, restart=True)

    assert first == 2
    assert sizes == ([1, 1, 1] if one_at_a_time else [2, 1])
    assert len([e for e in tutor.vault.events() if e.get("phase") == "practice"]) == 3
    block = next(b for b in tutor.session["blocks"] if b["kind"] == "learn")
    assert block["practiced"] == 3
    assert path.read_bytes() == source


@pytest.mark.parametrize("one_at_a_time", [False, True])
def test_no_eligible_practice_kind_terminates_without_counting_unasked_questions(tmp_path, one_at_a_time):
    tutor, path, source = new_tutor(tmp_path, "structured", one_at_a_time)

    tutor, first, sizes = drive(tutor)

    assert first is None and sizes == []
    assert not [e for e in tutor.vault.events() if e.get("phase") == "practice"]
    block = next(b for b in tutor.session["blocks"] if b["kind"] == "learn")
    assert block.get("practiced", 0) == 0
    assert path.read_bytes() == source


@pytest.mark.parametrize("one_at_a_time", [False, True])
def test_interruption_after_staged_practice_save_preserves_count_with_batch_and_queue(tmp_path, monkeypatch,
                                                                                   one_at_a_time):
    tutor, path, source = new_tutor(tmp_path, "fixed", one_at_a_time)
    real_save = tutor._save
    interrupted = False

    def stop_after_staging():
        nonlocal interrupted
        real_save()
        if not interrupted and any(p.get("phase") == "practice" for p in tutor.session["presented"].values()):
            interrupted = True
            raise OSError("interrupted after durable practice staging")

    with monkeypatch.context() as patch:
        patch.setattr(tutor, "_save", stop_after_staging)
        with pytest.raises(OSError, match="interrupted after durable practice staging"):
            drive(tutor)
    prefix = {p: p.read_bytes() for p in (tutor.vault.tutor / "events").glob("*.jsonl")}
    tutor = session.Tutor(tutor.vault, now=lambda: T0, one_at_a_time=one_at_a_time)
    staged = len(tutor.session["presented"]) + len(tutor.session.get("queue", {}))
    saved_count = tutor.session["blocks"][tutor.session["cursor"]].get("practiced", 0)
    assert staged == 2

    tutor, _, _ = drive(tutor)

    assert len([e for e in tutor.vault.events() if e.get("phase") == "practice"]) == 3
    assert saved_count == staged
    assert next(b for b in tutor.session["blocks"] if b["kind"] == "learn")["practiced"] == 3
    assert all(p.read_bytes().startswith(data) for p, data in prefix.items())
    assert path.read_bytes() == source
