"""Image-only choices retain their printed labels during public presentation."""
import copy
import json
import random
import sys
from datetime import datetime
from pathlib import Path

import pytest

from fixtures import GRAPH, PACK, make_vault
from library_assets import copy_to_vault
from tutorlib import packs, session, store

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "build"))
from validate_pack import validate


@pytest.mark.parametrize("null_options", [False, True])
@pytest.mark.parametrize("stem_template", [False, True], ids=["static", "template"])
def test_generated_image_only_mcq_keeps_printed_key_despite_shuffle_flag(tmp_path, monkeypatch, null_options, stem_template):
    root = make_vault(tmp_path)
    image = copy_to_vault("build/out/Assets/9702/9702-6-1-fig-p05-whole.png", root)
    path = root / ".tutor/packs/v1/specs/9702/packs/9702-2.1.json"
    pack = json.loads(path.read_text())
    item = copy.deepcopy(pack["items"][0])
    item.update(image=image.relative_to(root).as_posix(), stem="Choose the correct printed diagram.",
                hints=["Inspect each diagram.", "Compare their connections.", "Apply the stated rule."],
                explanation="Use the diagram's printed labels.", source={"type": "generated"}, shuffle=True)
    item.pop("options")
    if null_options:
        item["options"] = None
    if stem_template:
        item["stem"] = "Choose the printed diagram after scaling by [[factor]]."
        item["template"] = {"params": {"factor": {"choices": [2, 4]}}}
    pack["items"] = [item]
    monkeypatch.setenv("STEM_TUTOR_VAULT", str(root))
    assert not validate(pack, GRAPH, min_variants=0)
    path.write_text(json.dumps(pack))
    (root / ".tutor/packs/v1/papers.json").write_text('{"papers": []}')
    original = path.read_bytes()
    t = session.Tutor(store.Vault(root), rng=random.Random(0),
                      now=lambda: datetime.fromisoformat("2026-09-29T17:00:00+08:00"))
    t.start("test", 10, ["9702-2.1.1"])

    question = t.next()["items"][0]

    assert question.get("options") is None
    assert question["image"]
    inst = t.session["presented"][str(question["n"])]["inst"]
    assert ("options" in inst) == null_options
    assert inst["answer"] == item["answer"] and inst["distractors"] == item["distractors"]
    assert "[[" not in question["stem"]
    feedback = t.answer(f"{question['n']}{item['answer']}4")["results"][0]
    assert feedback["correct"]
    event = next(e for e in t.vault.events() if e["type"] == "answer")
    assert event["key"].startswith(item["answer"])
    assert path.read_bytes() == original


def test_generated_mcq_with_image_and_textual_choices_still_shuffles_consistently():
    item = copy.deepcopy(PACK["items"][0])
    item["image"] = "diagram-reference-not-read-by-instantiation.png"
    original = copy.deepcopy(item)
    visible_keys = set()
    for seed in range(8):
        inst = packs.instantiate(item, random.Random(seed))
        assert inst["options"][inst["answer"]] == "displacement"
        diagnosed = next(k for k, value in inst["distractors"].items() if value == "m1")
        assert inst["options"][diagnosed] == "distance"
        assert inst["hints"] == original["hints"] and inst["explanation"] == original["explanation"]
        assert item == original
        visible_keys.add(inst["answer"])
    assert len(visible_keys) > 1
