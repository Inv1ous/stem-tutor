"""Dataset regressions: source fidelity, truth labels and split leakage."""
import hashlib
import json
from pathlib import Path

import pytest

from tutor_app import stem_training_data as data
from tutor_app.chat_output import DocumentDecoder


def public_pack(tmp_path):
    root = tmp_path / "vault" / ".tutor" / "packs"
    published = root / "v1"
    (published / "specs" / "9702" / "packs").mkdir(parents=True)
    (root / "CURRENT").write_text("v1")
    source = published / "specs" / "9702" / "packs" / "9702-2.1.json"
    source.write_text(json.dumps({"spec": "9702", "version": 3, "subtopic": "9702-2.1",
        "flashcards": [
            {"id": "fc1", "kc": "9702-2.1.1", "front": "Define acceleration.",
             "back": "Rate of change of velocity with time."},
            {"id": "fc2", "kc": "9702-2.1.2", "front": "State the formula.",
             "back": r"$v=u+at$"},
            {"id": "bad", "kc": "9702-2.1.3", "front": "Bad card", "back": ""}],
        "worked": [{"id": "we1", "kc": "9702-2.1.1", "problem": "Find acceleration.",
                    "steps": [{"do": r"$a=(v-u)/t$", "why": "Use the definition."}]}]}))
    private = tmp_path / "vault" / ".tutor" / "learner.json"
    private.write_text('{"private": "NEVER_INCLUDE_LEARNER_SECRET"}')
    return tmp_path / "vault", source


def rows_at(output):
    return {split: [json.loads(line) for line in (output / f"{split}.jsonl").read_text().splitlines()]
            for split in ("train", "valid", "test")}


def test_public_source_exact_provenance_and_reproducible_manifest(tmp_path):
    vault, source = public_pack(tmp_path)
    first = data.build_dataset(vault, tmp_path / "first", seed=23)
    second = data.build_dataset(vault / ".tutor/packs/CURRENT", tmp_path / "second", seed=23)
    assert first == second
    corpus = rows_at(tmp_path / "first")
    for split, rows in corpus.items():
        raw = (tmp_path / "first" / f"{split}.jsonl").read_bytes()
        assert first["files"][f"{split}.jsonl"]["sha256"] == hashlib.sha256(raw).hexdigest()
        assert first["files"][f"{split}.jsonl"]["rows"] == len(rows)
    rows = sum(corpus.values(), [])
    public = [r for r in rows if r["task"] == "published_flashcard"]
    assert any(r["expected"]["blocks"] == [{"kind": "paragraph", "text": "Rate of change of velocity with time."}] for r in public)
    assert any(r["expected"]["blocks"] == [{"kind": "equation", "text": "v=u+at"}] for r in public)
    provenance = public[0]["provenance"][0]
    assert provenance["sha256"] == hashlib.sha256(source.read_bytes()).hexdigest()
    assert provenance["pack_version"] == "v1" and provenance["content_version"] == 3
    assert provenance["spec"] == "9702" and provenance["kc"].startswith("9702-2.1.")
    assert "NEVER_INCLUDE_LEARNER_SECRET" not in json.dumps(rows)
    assert first["discard_reasons"]["empty_or_unsupported_source"] == 1


def test_split_families_and_augmented_kcs_never_leak(tmp_path):
    vault, _ = public_pack(tmp_path)
    data.build_dataset(vault, tmp_path / "data")
    corpus = rows_at(tmp_path / "data")
    groups = {split: {r["group"] for r in rows} for split, rows in corpus.items()}
    assert groups["train"].isdisjoint(groups["valid"] | groups["test"])
    assert groups["valid"].isdisjoint(groups["test"])
    locations = {}
    for split, rows in corpus.items():
        for row in rows:
            assert row["id"] not in locations
            locations[row["id"]] = split
            assert json.loads(row["messages"][1]["content"]) == row["expected"]
            assert row["checks"]["validated"] is True
    public = [(split, r) for split, rows in corpus.items() for r in rows if r["task"].startswith("published_")]
    assert len({split for split, _ in public}) == 1  # whole subtopic held together


def test_all_document_gold_decodes_and_code_preserves_real_newlines(tmp_path):
    vault, _ = public_pack(tmp_path)
    data.build_dataset(vault, tmp_path / "data")
    rows = sum(rows_at(tmp_path / "data").values(), [])
    code = []
    for row in rows:
        if "blocks" not in row["expected"]:
            continue
        decoder = DocumentDecoder(speech="speech" in row["expected"])
        decoder.feed(row["messages"][1]["content"])
        decoder.finish()
        assert decoder.document == row["expected"]
        code.extend(b["text"] for b in row["expected"]["blocks"] if b["kind"] == "code")
    assert 'def square(x):\n    return x * x\nrecord = {"reply": "x_1^2"}' in code
    assert all("\\n" not in source for source in code)


def test_verified_calculations_units_and_curated_negative_marking(tmp_path):
    vault, _ = public_pack(tmp_path)
    data.build_dataset(vault, tmp_path / "data")
    rows = sum(rows_at(tmp_path / "data").values(), [])
    force = next(r for r in rows if r["task"] == "force_calculation" and r["checks"]["inputs"] == {"mass": 2, "acceleration": 3})
    assert force["expected"]["blocks"][-1]["text"] == r"F=2\times3=6\,\mathrm{N}"
    negatives = [r for r in rows if r["task"] == "marking" and r["subject"] == "chem"]
    assert any([p["met"] for p in r["expected"]["points"]] == [False, False] for r in negatives)
    assert any([p["met"] for p in r["expected"]["points"]] == [True, False] for r in negatives)
    assert all("points" in r["messages"][0]["content"] and "feedback" in r["messages"][0]["content"] for r in negatives)
    assert {r["subject"] for r in rows} == {"chem", "phys", "math"}
    assert len(rows) >= 200


def test_open_hint_does_not_reveal_answer(tmp_path):
    vault, _ = public_pack(tmp_path)
    data.build_dataset(vault, tmp_path / "data")
    rows = sum(rows_at(tmp_path / "data").values(), [])
    hints = [r for r in rows if r["task"] == "open_hint"]
    assert hints
    for row in hints:
        assert "OPEN" in row["messages"][0]["content"]
        assert len(row["expected"]["blocks"]) == 1
        assert "?" in row["expected"]["blocks"][0]["text"]
        assert row["checks"]["open_answer_protected"] is True


def test_invalid_pack_path_does_not_write_synthetic_only_corpus(tmp_path):
    with pytest.raises(ValueError, match="published pack"):
        data.build_dataset(tmp_path / "missing", tmp_path / "data")
    assert not (tmp_path / "data").exists()


def test_speech_is_separate_and_same_content_group(tmp_path):
    vault, _ = public_pack(tmp_path)
    data.build_dataset(vault, tmp_path / "data")
    rows = sum(rows_at(tmp_path / "data").values(), [])
    spoken = [r for r in rows if "speech" in r["expected"]]
    assert spoken
    row = next(r for r in spoken if r["task"] == "published_flashcard")
    assert row["expected"]["speech"] == "Rate of change of velocity with time."
    assert row["expected"]["blocks"] == [{"kind": "paragraph", "text": "Rate of change of velocity with time."}]
    assert any(r["group"] == row["group"] and "speech" not in r["expected"] for r in rows)


def test_identical_public_answers_in_different_subtopics_stay_in_one_split(tmp_path):
    vault, source = public_pack(tmp_path)
    copy = json.loads(source.read_text())
    copy["subtopic"] = "9702-3.1"
    copy["flashcards"] = [{"id": "same", "kc": "9702-3.1.1", "front": "Define acceleration another way.",
                           "back": "Rate of change of velocity with time."}]
    copy["worked"] = []
    source.with_name("9702-3.1.json").write_text(json.dumps(copy))
    data.build_dataset(vault, tmp_path / "data")
    public = [r for rows in rows_at(tmp_path / "data").values() for r in rows if r["task"].startswith("published_")]
    assert len({r["group"] for r in public}) == 1


def test_published_tree_cannot_be_used_as_output(tmp_path):
    vault, source = public_pack(tmp_path)
    before = source.read_bytes()
    with pytest.raises(ValueError, match="published pack tree"):
        data.build_dataset(vault, source.parent / "generated")
    assert source.read_bytes() == before


def test_curated_marking_holds_out_concept_families(tmp_path):
    vault, _ = public_pack(tmp_path)
    data.build_dataset(vault, tmp_path / "data")
    corpus = rows_at(tmp_path / "data")
    assert any(r["task"] == "marking" for r in corpus["test"])
    assert any(r["task"] == "marking" for r in corpus["valid"])


def test_accepts_public_packs_facade_root(tmp_path):
    from types import SimpleNamespace
    vault, source = public_pack(tmp_path)
    published = source.parents[3]
    manifest = data.build_dataset(SimpleNamespace(root=published), tmp_path / "data")
    assert manifest["pack_version"] == "v1"


def test_same_question_with_different_authored_answers_is_not_a_holdout(tmp_path):
    vault, source = public_pack(tmp_path)
    copy = json.loads(source.read_text())
    copy["subtopic"] = "9702-3.1"
    copy["flashcards"] = [{"id": "same-question", "kc": "9702-3.1.1", "front": "Define acceleration.",
                           "back": "Change in velocity per unit time."}]
    copy["worked"] = []
    source.with_name("9702-3.1.json").write_text(json.dumps(copy))
    data.build_dataset(vault, tmp_path / "data")
    public = [r for rows in rows_at(tmp_path / "data").values() for r in rows if r["task"].startswith("published_")]
    assert len({r["group"] for r in public}) == 1


def test_direct_recall_has_official_truth_without_answer_in_prompt(tmp_path):
    vault, _ = public_pack(tmp_path)
    data.build_dataset(vault, tmp_path / "data")
    corpus = rows_at(tmp_path / "data")
    for split in corpus:
        direct = [r for r in corpus[split] if r["task"] == "direct_recall"]
        assert {r["subject"] for r in direct} == {"chem", "phys", "math"}
        for row in direct:
            assert row["checks"]["source_free"] is True
            assert row["provenance"][0]["url"].startswith("https://")
            assert row["provenance"][0]["claim"]
            assert all(b["text"] not in row["messages"][0]["content"] for b in row["expected"]["blocks"])
            assert "published_answer" not in row["messages"][0]["content"]
    direct = [r for rows in corpus.values() for r in rows if r["task"] == "direct_recall"]
    atomic = next(r for r in direct if r["provenance"][0]["fact_id"] == "chem_atomic_number")
    assert atomic["expected"]["blocks"] == [{"kind": "paragraph", "text": "The atomic number counts the protons in an atomic nucleus."}]
    assert "\"blocks\"" not in atomic["messages"][0]["content"]


def test_format_challenge_freezes_18_rows_and_roundtrips_gold(tmp_path):
    from tutor_app.stem_training_eval import load_selection, score_trial
    vault, _ = public_pack(tmp_path)
    training = tmp_path / "training"
    data.build_dataset(vault, training)
    before = {p.name: p.read_bytes() for p in training.iterdir()}
    output = tmp_path / "challenge"
    manifest = data.build_format_challenge(training, output)
    assert {p.name: p.read_bytes() for p in training.iterdir()} == before
    assert not (output / "train.jsonl").exists() and not (output / "valid.jsonl").exists()
    rows, selection = load_selection(output, output / "selection.json")
    assert selection["rows"] == 18
    assert manifest["files"]["test.jsonl"]["rows"] == 18
    assert all(sum(r["subject"] == subject for r in rows) == 6 for subject in ("chem", "phys", "math"))
    assert len({r["id"] for r in rows}) == len({r["group"] for r in rows}) == 18
    assert all(r["checks"]["novel_question"] for r in rows)
    assert all(not r["checks"]["exact_training_gold_overlap"] for r in rows)
    for row in rows:
        score = score_trial(row, {"finish_reason": "stop", "text": row["messages"][1]["content"]})
        assert score["raw_contract_valid"] and score["exact_document_match"]
        if row["task"] == "format_literal_source":
            assert score["literal_code_equal"]
            source = row["expected"]["blocks"][0]["text"]
            assert "\n" in source and "%" in source and any(c in source for c in ("£", "$"))
    assert sum("speech" in r["expected"] for r in rows) == 3
    assert sum(r["checks"].get("open_answer_protected", False) for r in rows) == 3
    assert sum(r["checks"]["schema"] == "marking" for r in rows) == 3


def test_format_challenge_refuses_to_overwrite_a_frozen_output(tmp_path):
    vault, _ = public_pack(tmp_path)
    data.build_dataset(vault, tmp_path / "training")
    output = tmp_path / "challenge"
    data.build_format_challenge(tmp_path / "training", output)
    before = (output / "selection.json").read_bytes()
    with pytest.raises(FileExistsError, match="frozen"):
        data.build_format_challenge(tmp_path / "training", output)
    assert (output / "selection.json").read_bytes() == before
