"""Extraction graph reads are bounded, authoritative and entirely read-only."""
import copy
import hashlib
import json
import os
import shlex
import subprocess

import pytest

from test_extraction import extraction
from tutorlib.asset_library import write_asset


@pytest.fixture
def graph_job(tmp_path, monkeypatch):
    ex = extraction()
    monkeypatch.setenv("STEM_EXTRACT_ROOT", str(tmp_path / "Work"))
    monkeypatch.setenv("STEM_LIBRARY_SPECS", str(tmp_path / "specs"))
    graph = {"spec": "9702", "version": "test", "subtopics": [
        {"id": "9702-1.1", "title": "Waves"}], "kcs": [
        {"id": "9702-1.1.2", "subtopic": "9702-1.1", "title": "Standing waves",
         "statement": "Relate wave speed and frequency.", "guidance": "Use nodes and phase.",
         "prereqs": ["9702-1.1.1", "P1-1.1", "P1-99.1"]},
        {"id": "9702-1.1.1", "subtopic": "9702-1.1", "title": "Travelling waves",
         "statement": "Describe wave speed.", "prereqs": []}]}
    path = tmp_path / "specs/9702/graph.json"
    path.parent.mkdir(parents=True)
    path.write_text(json.dumps(graph))
    target = tmp_path / "specs/P1/graph.json"
    target.parent.mkdir()
    target.write_text(json.dumps({"spec": "P1", "subtopics": [{"id": "P1-1", "title": "Algebra"}],
                                 "kcs": [{"id": "P1-1.1", "subtopic": "P1-1", "title": "Indices"},
                                         {"id": "P1-1.2", "subtopic": "P1-1", "title": "Unrelated target"}]}))
    ex.create("lookup", "9702", provider="codex")
    return ex, path, target, graph


def snapshot(root):
    return {path: path.read_bytes() for path in root.rglob("*") if path.is_file()}


def test_exact_lookup_returns_source_bound_current_kc_and_only_declared_targets(graph_job, tmp_path):
    ex, path, target, graph = graph_job
    before = snapshot(tmp_path)

    result = ex.graph("lookup", kc_id="9702-1.1.2")

    assert result["course"] == "9702"
    assert result["graph_sha256"] == hashlib.sha256(path.read_bytes()).hexdigest()
    row, = result["results"]
    assert {key: row[key] for key in ("id", "title", "statement", "guidance")} == {
        key: graph["kcs"][0][key] for key in ("id", "title", "statement", "guidance")}
    assert row["subtopic"] == graph["subtopics"][0]
    assert [(entry["id"], entry["valid"]) for entry in row["prereqs"]] == [
        ("9702-1.1.1", True), ("P1-1.1", True), ("P1-99.1", False)]
    assert "unknown" in row["prereqs"][-1]["reason"].lower()
    assert result["target_graph_sha256"] == {"P1": hashlib.sha256(target.read_bytes()).hexdigest()}
    assert "P1-1.2" not in json.dumps(result)
    assert snapshot(tmp_path) == before


def test_query_is_literal_all_terms_ordered_and_bounded(graph_job):
    ex, path, _, graph = graph_job
    graph["kcs"] = [{"id": f"9702-1.1.{index}", "subtopic": "9702-1.1", "title": "Shared Wave Token"}
                    for index in reversed(range(30))]
    path.write_text(json.dumps(graph))
    result = ex.graph("lookup", query="WAVE shared")
    assert result["matched"] == 30 and result["limit"] == 8
    assert [row["id"] for row in result["results"]] == sorted(row["id"] for row in graph["kcs"])[:8]
    assert len(ex.graph("lookup", query="shared", limit=20)["results"]) == 20
    assert ex.graph("lookup", query="shared.*")["results"] == []
    assert ex.graph("lookup", query="shared absent")["results"] == []


@pytest.mark.parametrize("limit", [0, -1, 21, True])
def test_invalid_result_limits_are_refused(graph_job, limit):
    ex, _, _, _ = graph_job
    with pytest.raises(ValueError, match="limit"):
        ex.graph("lookup", query="waves", limit=limit)


@pytest.mark.parametrize("options", [{}, {"query": " "}, {"kc_id": "P1-1.1"},
                                    {"kc_id": "9702-99.1"}, {"kc_id": "9702-1.1.1", "query": "wave"}])
def test_exact_current_course_or_nonempty_query_is_required(graph_job, options):
    ex, _, _, _ = graph_job
    with pytest.raises(ValueError):
        ex.graph("lookup", **options)


def test_foreign_rows_cannot_enter_current_course_results(graph_job):
    ex, path, _, graph = graph_job
    graph["kcs"].append({"id": "9701-1.1.1", "subtopic": "9702-1.1", "title": "wave"})
    path.write_text(json.dumps(graph))
    with pytest.raises(ValueError, match="course"):
        ex.graph("lookup", query="wave")


@pytest.mark.parametrize("missing", [False, True])
def test_declared_target_graph_failure_is_visible_without_hiding_current_kc(graph_job, missing):
    ex, _, target, _ = graph_job
    if missing:
        target.unlink()
    else:
        target.write_text("not JSON")
    row, = ex.graph("lookup", kc_id="9702-1.1.2")["results"]
    external = [entry for entry in row["prereqs"] if entry["id"].startswith("P1-")]
    assert external and all(not entry["valid"] and "unavailable" in entry["reason"] for entry in external)


def test_registered_graph_alias_verifies_hash_and_uses_exact_parsed_bytes(graph_job, tmp_path, monkeypatch):
    from tutorlib.asset_library import AssetLibrary
    ex, path, _, graph = graph_job
    vault = tmp_path / "vault"
    vault.mkdir()
    relative = "Library/Courses/9702/Specifications/graph.json"
    data = path.read_bytes()
    write_asset(vault, relative, data)
    path.unlink()
    path.symlink_to(vault / relative)
    before = snapshot(tmp_path)
    result = ex.graph("lookup", kc_id="9702-1.1.1")
    assert result["graph_sha256"] == hashlib.sha256(data).hexdigest()
    assert snapshot(tmp_path) == before
    original_read = AssetLibrary.read

    def mutate_after_verified_read(self, reference, **kwargs):
        payload = original_read(self, reference, **kwargs)
        if reference == relative:
            changed = copy.deepcopy(graph)
            changed["kcs"][1]["title"] = "Changed after read"
            (vault / relative).write_text(json.dumps(changed))
        return payload

    with monkeypatch.context() as patch:
        patch.setattr(AssetLibrary, "read", mutate_after_verified_read)
        result = ex.graph("lookup", kc_id="9702-1.1.1")
    assert result["graph_sha256"] == hashlib.sha256(data).hexdigest()
    assert result["results"][0]["title"] == "Travelling waves"
    with pytest.raises(ValueError, match="digest"):
        ex.graph("lookup", kc_id="9702-1.1.1")


def test_graph_library_case_alias_preserves_actual_filesystem_identity(graph_job, tmp_path):
    from tutor_workers import candidates
    ex, path, _, graph = graph_job
    vault = tmp_path / "vault"
    vault.mkdir()
    relative = "Library/Courses/9702/Specifications/graph.json"
    write_asset(vault, relative, path.read_bytes())
    alternate = vault / relative.replace("Library/", "library/", 1)
    same_library = alternate.exists()
    if not same_library:
        alternate.parent.mkdir(parents=True)
        alternate.write_text(json.dumps(graph))
    path.unlink()
    path.symlink_to(alternate)
    assert ex.graph("lookup", kc_id="9702-1.1.1")["results"]
    changed = copy.deepcopy(graph)
    changed["kcs"][1]["title"] = "Tampered registered graph"
    (vault / relative).write_text(json.dumps(changed))
    if same_library:
        with pytest.raises(ValueError, match="digest"):
            candidates.verified(path)
        with pytest.raises(ValueError, match="digest"):
            ex.graph("lookup", kc_id="9702-1.1.1")
    else:
        assert ex.graph("lookup", kc_id="9702-1.1.1")["results"][0]["title"] == "Travelling waves"


def test_graph_reads_and_serialized_output_have_explicit_size_caps(graph_job):
    ex, path, _, graph = graph_job
    graph["kcs"][0]["guidance"] = "x" * 25_000
    path.write_text(json.dumps(graph))
    with pytest.raises(ValueError, match="narrow"):
        ex.graph("lookup", kc_id="9702-1.1.2")
    path.write_bytes(b"x" * 2_000_001)
    with pytest.raises(ValueError, match="size"):
        ex.graph("lookup", query="wave")


def test_cli_success_and_missing_graph_diagnostic_leave_job_unchanged(graph_job, tmp_path, capsys):
    ex, path, _, _ = graph_job
    before = snapshot(tmp_path)
    assert ex.main(["graph", "lookup", "--id", "9702-1.1.1"]) == 0
    assert json.loads(capsys.readouterr().out)["results"][0]["id"] == "9702-1.1.1"
    assert snapshot(tmp_path) == before
    path.unlink()
    state = ex.job_dir("lookup") / "state.json"
    state_bytes = state.read_bytes()
    assert ex.main(["graph", "lookup", "--query", "wave"]) == 1
    assert "graph" in capsys.readouterr().err.lower()
    assert state.read_bytes() == state_bytes


def test_real_cli_reads_the_same_job_graph_without_writing_files(graph_job, tmp_path):
    ex, path, _, _ = graph_job
    before = snapshot(tmp_path)
    result = subprocess.run([str(ex.REPO / "bin/extract"), "graph", "lookup", "--id", "9702-1.1.1"],
                            capture_output=True, text=True, timeout=5, env=dict(os.environ))
    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout)["graph_sha256"] == hashlib.sha256(path.read_bytes()).hexdigest()
    assert snapshot(tmp_path) == before


@pytest.mark.parametrize("role", ["extract", "review"])
def test_worker_contract_and_claude_permission_are_read_only_and_job_scoped(graph_job, monkeypatch, role):
    ex, _, _, _ = graph_job
    state = ex.load("lookup")
    state.update(jobs={role: {"provider": "claude"}}, review_independence="same_family")
    monkeypatch.setenv("STEM_EXTRACT_CLAUDE", "/not-executed/claude")
    contract = json.loads(ex._prompt(state, role).split("JOB CONTRACT:\n", 1)[1])
    command = contract["source_read_commands"]["course_graph"]
    relative = "bin/extract graph lookup"
    absolute = shlex.join([str(ex.REPO / "bin/extract"), "graph", "lookup"])
    assert command["relative"] == relative and command["absolute"] == absolute
    assert command["max_results"] == 20 and command["default_results"] == 8
    worker = ex.worker_command(state, role)
    allowed = worker[worker.index("--allowedTools") + 1:worker.index("--add-dir")]
    assert f"Bash({relative} *)" in allowed and f"Bash({absolute} *)" in allowed
    assert not any(rule.startswith("Bash(bin/extract graph *)") for rule in allowed)
