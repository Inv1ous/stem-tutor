"""The subtopic identity guard: a teach file or a pack that belongs to another subtopic must never be written.
Found in the Haiku batch: 9701-1.3's pack was replaced by 9701-1.4's, and its teach file held 1.4 cards."""
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "build"))
import teach_cards  # noqa: E402

CARD = {"motivate": "m", "establish": "e", "connect": "c", "note": "n", "self_explain": "s"}


def test_a_pack_for_another_subtopic_is_refused():
    problems = teach_cards.identity_problems("9701-1.3", {"subtopic": "9701-1.4"}, {"9701-1.3.1": CARD})
    assert any("pack says subtopic '9701-1.4'" in p for p in problems)


def test_teach_cards_for_another_subtopic_are_refused():
    problems = teach_cards.identity_problems("9701-1.3", {"subtopic": "9701-1.3"}, {"9701-1.4.1": CARD})
    assert any("'9701-1.4.1' is not a KC of 9701-1.3" in p for p in problems)


def test_the_right_pack_and_cards_pass():
    assert teach_cards.identity_problems("9701-1.3", {"subtopic": "9701-1.3"}, {"9701-1.3.1": CARD}) == []


def test_a_prefix_is_not_enough_for_a_kc(monkeypatch):
    # 9701-1.30.x must not pass for 9701-1.3 just because the text starts with 9701-1.3
    problems = teach_cards.identity_problems("9701-1.3", {"subtopic": "9701-1.3"}, {"9701-1.30.1": CARD})
    assert problems and "not a KC" in problems[0]


def test_merge_writes_nothing_when_the_identity_check_fails(tmp_path, monkeypatch, capsys):
    bundle = tmp_path / "build" / "work" / "teach"
    bundle.mkdir(parents=True)
    packs = tmp_path / "build" / "out" / "packs" / "9701"
    packs.mkdir(parents=True)
    graph = tmp_path / "build" / "out" / "specs" / "9701"
    graph.mkdir(parents=True)
    graph.joinpath("graph.json").write_text(json.dumps({"kcs": [{"id": "9701-1.3.1", "subtopic": "9701-1.3"}]}))
    (bundle / "9701-1.3.json").write_text(json.dumps({"9701-1.4.1": CARD}))  # the wrong teach file
    pack_file = packs / "9701-1.3.json"
    original = json.dumps({"subtopic": "9701-1.3", "spec": "9701", "teach": {"keep": 1}})
    pack_file.write_text(original)
    monkeypatch.setattr(teach_cards, "ROOT", tmp_path)
    code = teach_cards.main("merge", ["9701-1.3"])
    assert code == 1 and "REFUSED" in capsys.readouterr().out
    assert pack_file.read_text() == original  # nothing was written
