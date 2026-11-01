"""Migration baseline checks use only a synthetic Library in a temporary tree."""
import importlib.util
import json
from pathlib import Path

import pytest


MODULE = Path(__file__).resolve().parents[1] / "build/workspace_audit.py"
spec = importlib.util.spec_from_file_location("workspace_audit", MODULE)
audit = importlib.util.module_from_spec(spec)
spec.loader.exec_module(audit)


def put(root, relative, text):
    path = root / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return path


def test_manifest_hashes_duplicates_and_inventory_leave_content_unchanged(tmp_path):
    first = put(tmp_path, "Vault/Library/Courses/course/Diagrams/figure.svg", "<svg>same</svg>")
    second = put(tmp_path, "build/out/assets/figure.svg", first.read_text())
    put(tmp_path, "code/main.py", "print('study')")
    before = {p: p.read_bytes() for p in tmp_path.rglob("*") if p.is_file()}
    report = audit.audit_workspace(tmp_path)
    assert report["summary"]["files"] == 3
    assert report["summary"]["learning_assets"] == 2
    assert report["duplicates"][0]["paths"] == [str(first.relative_to(tmp_path)), str(second.relative_to(tmp_path))]
    assert report["duplicates"][0]["duplicate_bytes"] == len(first.read_bytes())
    assert before == {p: p.read_bytes() for p in tmp_path.rglob("*") if p.is_file()}


def test_caches_and_worktrees_are_excluded_but_worktree_metadata_remains(tmp_path):
    put(tmp_path, "code/.git/worktrees/topic/gitdir", "/outside/topic/.git\n")
    put(tmp_path, "code/.git/worktrees/topic/HEAD", "ref: refs/heads/topic\n")
    put(tmp_path, "code/.claude/worktrees/topic/secret.py", "not scanned")
    put(tmp_path, "Vault/.tutor/audio/big.wav", "cache")
    put(tmp_path, "code/.venv/hidden.py", "cache")
    put(tmp_path, "Vault/Library/Courses/course/Questions/item.svg", "<svg/>")
    report = audit.audit_workspace(tmp_path)
    assert len(report["files"]) == 1
    assert any(row.get("gitdir") == "/outside/topic/.git" for row in report["worktrees"])
    assert any(row.get("entries", [{}])[0].get("path") == "code/.claude/worktrees/topic" for row in report["worktrees"])
    assert {row["reason"] for row in report["excluded"]} == {"git_metadata", "worktrees", "cache_or_environment"}


def test_symlink_files_and_directories_never_supply_asset_content(tmp_path):
    external = tmp_path.parent / (tmp_path.name + "-outside")
    external.mkdir()
    (external / "secret.svg").write_text("private")
    (tmp_path / "Library").symlink_to(external, target_is_directory=True)
    (tmp_path / "alias.svg").symlink_to(external / "secret.svg")
    report = audit.audit_workspace(tmp_path)
    assert report["files"] == []
    assert {row["path"] for row in report["symlinks"]} == {"Library", "alias.svg"}
    with pytest.raises(ValueError, match="symlink"):
        audit.audit_workspace(tmp_path / "Library")


def test_wikilinks_and_json_references_find_existing_missing_and_ambiguous_assets(tmp_path):
    put(tmp_path, "Vault/Library/Courses/course/Diagrams/plot.svg", "<svg/>")
    put(tmp_path, "Vault/Lessons/lesson.md", "![[Library/Courses/course/Diagrams/plot.svg|600]]\n![[absent.svg]]\n[[note]]")
    put(tmp_path, "Vault/Notes/note.md", "saved")
    put(tmp_path, "build/Library/Courses/course/Diagrams/plot.svg", "different")
    put(tmp_path, "pack.json", json.dumps({"images": ["Library/Courses/course/Diagrams/plot.svg"], "other": "absent.png"}))
    report = audit.audit_workspace(tmp_path)
    statuses = {row["target"]: row["status"] for row in report["references"]}
    assert statuses["Library/Courses/course/Diagrams/plot.svg"] == "ambiguous"
    assert statuses["absent.svg"] == statuses["absent.png"] == "missing"
    assert statuses["note"] == "resolved"
    assert any(row.get("pointer") == "/images/0" for row in report["references"])


def test_collisions_cover_case_and_unicode_normalisation(tmp_path):
    # Use separate directory names so the fixture also works on case-insensitive macOS.
    put(tmp_path, "Library/Courses/course/Diagrams/A/figure.svg", "first")
    report = audit.audit_workspace(tmp_path)
    assert report["path_collisions"] == []
    assert audit._key("Library/Café/A.svg") == audit._key("library/Cafe\u0301/a.SVG")


def test_manifest_reports_real_case_collisions_when_filesystem_supports_them(tmp_path):
    upper = put(tmp_path, "Library/Courses/course/Diagrams/Collision.svg", "first")
    lower = put(tmp_path, "Library/Courses/course/Diagrams/collision.svg", "second")
    if upper.samefile(lower):
        pytest.skip("filesystem aliases case variants; normalisation contract tested separately")
    report = audit.audit_workspace(tmp_path)
    assert [str(upper.relative_to(tmp_path)), str(lower.relative_to(tmp_path))] in report["path_collisions"]


def test_crlf_and_utf8_bom_documents_keep_byte_hashes_and_parse_references(tmp_path):
    put(tmp_path, "Library/Courses/course/Diagrams/a.svg", "<svg/>")
    document = put(tmp_path, "lesson.md", "")
    document.write_bytes(b"\xef\xbb\xbf![[Library/Courses/course/Diagrams/a.svg]]\r\n")
    report = audit.audit_workspace(tmp_path)
    assert report["errors"] == []
    assert report["references"][0]["status"] == "resolved"


def test_outside_and_excluded_refs_are_not_reported_as_missing(tmp_path):
    put(tmp_path, "Vault/Lessons/lesson.md", "![[../../../outside.svg]]\n![[code/.venv/a.svg]]")
    put(tmp_path, "code/.venv/a.svg", "cache")
    report = audit.audit_workspace(tmp_path)
    statuses = {row["target"]: row["status"] for row in report["references"]}
    # One candidate is outside, but a root-relative candidate remains inside.
    assert statuses["../../../outside.svg"] == "outside_root"
    assert statuses["code/.venv/a.svg"] == "excluded"


def test_invalid_json_and_read_errors_are_visible_without_losing_manifest(tmp_path, monkeypatch):
    put(tmp_path, "Library/broken.json", "{")
    put(tmp_path, "Library/denied.svg", "<svg/>")
    original = audit._hash
    def fail_one(path):
        if path.name == "denied.svg":
            raise PermissionError("access denied")
        return original(path)
    monkeypatch.setattr(audit, "_hash", fail_one)
    report = audit.audit_workspace(tmp_path)
    assert len(report["files"]) == 2
    assert {row["operation"] for row in report["errors"]} == {"hash", "references"}


def test_explicit_report_is_atomic_and_refuses_unrelated_data(tmp_path):
    root = tmp_path / "workspace"
    put(root, "Library/Courses/course/Diagrams/a.svg", "<svg/>")
    destination = tmp_path / "report.json"
    assert audit.main(["--root", str(root), "--report", str(destination)]) == 0
    assert json.loads(destination.read_text())["summary"]["files"] == 1
    assert audit.main(["--root", str(root), "--report", str(destination)]) == 0
    assert not list(tmp_path.glob(".report.json.*.tmp"))
    destination.write_text('{"learner": "keep"}')
    with pytest.raises(SystemExit) as exc:
        audit.main(["--root", str(root), "--report", str(destination)])
    assert exc.value.code == 2
    assert destination.read_text() == '{"learner": "keep"}'


def test_cli_stdout_and_error_exit_codes(tmp_path, capsys):
    put(tmp_path, "Library/Courses/course/Questions/broken.json", "{")
    assert audit.main(["--root", str(tmp_path)]) == 1
    assert json.loads(capsys.readouterr().out)["summary"]["errors"] == 1
    with pytest.raises(SystemExit) as exc:
        audit.main(["--root", str(tmp_path / "absent")])
    assert exc.value.code == 2


def test_report_inside_workspace_is_excluded_from_its_own_baseline(tmp_path):
    put(tmp_path, "Library/Courses/course/Diagrams/a.svg", "<svg/>")
    destination = tmp_path / "audit.json"
    assert audit.main(["--root", str(tmp_path), "--report", str(destination)]) == 0
    assert audit.main(["--root", str(tmp_path), "--report", str(destination)]) == 0
    report = json.loads(destination.read_text())
    assert report["summary"]["files"] == 1
    assert {"path": "audit.json", "reason": "audit_report"} in report["excluded"]
