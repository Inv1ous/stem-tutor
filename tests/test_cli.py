import json
import os
import subprocess
import sys
import time
import zipfile
from pathlib import Path

from fixtures import make_vault

SCRIPT = Path(__file__).resolve().parents[1] / "plugin/stem-tutor/skills/tutor/scripts/tutor.py"


def run(vault, *args, stdin=None, env_extra=None):
    env = {**os.environ, "STEM_TUTOR_VAULT": str(vault), "STEM_TUTOR_NOW": "2026-09-29T17:00:00+08:00", **(env_extra or {})}
    p = subprocess.run([sys.executable, str(SCRIPT), *args], capture_output=True, text=True, env=env, input=stdin)
    assert p.returncode == 0, p.stderr
    return json.loads(p.stdout)


def test_doctor_reports_vault_and_packs(tmp_path):
    v = make_vault(tmp_path)
    out = run(v, "doctor")
    assert out["ok"] and out["packs"] == "v1" and out["kcs"] == 2


def test_doctor_quiet_prints_nothing_without_vault(tmp_path):
    env = {**os.environ, "STEM_TUTOR_VAULT": str(tmp_path / "none"), "STEM_TUTOR_MOUNTS": str(tmp_path / "x/*")}
    p = subprocess.run([sys.executable, str(SCRIPT), "doctor", "--quiet"], capture_output=True, text=True, env=env)
    assert p.returncode == 0 and p.stdout == ""


def test_start_next_answer_end_cycle(tmp_path):
    v = make_vault(tmp_path)
    plan = run(v, "session", "start", "--mode", "autopilot", "--minutes", "50")
    assert plan["blocks"][0]["kind"] == "learn"
    act = run(v, "next")
    q = act["items"][0]
    reply = f"{q['n']}B3" if q["kind"] == "mcq" else f"{q['n']} = 1 ~2"
    fb = run(v, "answer", reply)
    assert fb["results"][0]["n"] == q["n"]
    assert run(v, "hint", str(act["items"][1]["n"]))["level"] == 1 if len(act["items"]) > 1 else True
    end = run(v, "session", "end")
    assert end["answered"] >= 1 and end["note"].startswith("Sessions/")


def test_brief_and_week(tmp_path):
    v = make_vault(tmp_path)
    assert run(v, "brief")["week"] == 5
    out = run(v, "week")
    assert set(out) >= {"today", "profile"}
    assert (v / "Profile.md").exists() and (v / "Today.md").exists()


def test_diagnose_map(tmp_path):
    v = make_vault(tmp_path)
    out = run(v, "diagnose", "map", stdin="displacement is a vector and velocity too")
    assert out["kcs"][0]["kc"] == "9702-2.1.1"


def test_lint_command(tmp_path):
    v = make_vault(tmp_path)
    (v / "n.md").write_text("bad \\(x\\)")
    out = run(v, "lint", str(v / "n.md"))
    assert out["findings"][0]["rule"] == "delimiter"


def test_inbox_waits_for_stable_files(tmp_path):
    v = make_vault(tmp_path)
    (v / "Inbox").mkdir()
    (v / "Inbox" / "7.pdf").write_bytes(b"%PDF-1.4 fake")
    out = run(v, "inbox", env_extra={"STEM_TUTOR_INBOX_SETTLE": "0"})
    assert out["ready"][0]["file"] == "Inbox/7.pdf" and out["ready"][0]["n"] == 7


def test_deps_extracts_wheel(tmp_path, monkeypatch):
    sys.path.insert(0, str(SCRIPT.parent))
    from tutorlib import deps
    wheels = tmp_path / "wheels"
    wheels.mkdir()
    with zipfile.ZipFile(wheels / "fakepkg-1.0-py3-none-any.whl", "w") as z:
        z.writestr("fakepkg/__init__.py", "VALUE = 42\n")
    monkeypatch.setattr(deps, "WHEELS", wheels)
    monkeypatch.setattr(deps, "CACHE", tmp_path / "cache")
    deps.ensure("fakepkg")
    import fakepkg
    assert fakepkg.VALUE == 42


def test_paper_cli(tmp_path):
    v = make_vault(tmp_path)
    assert run(v, "paper", "list")["papers"][0]["id"] == "9702_s23_qp_22"
    assert run(v, "paper", "score", "9702_s23_qp_22", "1a=2/2, 1b=3/3")["percent"] == 100.0


def test_tag_cli_checks_the_answer_and_the_code(tmp_path):
    v = make_vault(tmp_path)
    run(v, "session", "start", "--mode", "autopilot", "--minutes", "50")
    q = run(v, "next")["items"][0]
    ev = run(v, "answer", f"{q['n']}?")["results"][0]["event"]
    assert run(v, "tag", ev, "nonsense")["ok"] is False
    assert run(v, "tag", "nosuchevent", "SLIP")["ok"] is False
    assert run(v, "tag", ev, "recall")["ok"] is True


def test_taught_lists_plan_kcs_up_to_current_week(tmp_path):
    v = make_vault(tmp_path)
    assert run(v, "taught") == {"phys": ["9702-2.1.1", "9702-2.1.4"]}


def test_engine_copied_into_vault_finds_its_own_vault(tmp_path):
    """Remote Cowork runs the engine from the connected folder (device_bash, ~/mnt/<folder>/.tutor/engine)."""
    import shutil
    v = make_vault(tmp_path)
    eng = v / ".tutor" / "engine"
    shutil.copytree(SCRIPT.parent, eng, ignore=shutil.ignore_patterns("__pycache__"))
    env = {k: val for k, val in os.environ.items() if k != "STEM_TUTOR_VAULT"}
    env.update(STEM_TUTOR_MOUNTS=str(tmp_path / "nowhere/*"), STEM_TUTOR_NOW="2026-09-29T17:00:00+08:00")
    p = subprocess.run([sys.executable, str(eng / "tutor.py"), "doctor"], capture_output=True, text=True, env=env, cwd=tmp_path)
    assert p.returncode == 0, p.stderr
    out = json.loads(p.stdout)
    assert out["ok"] and Path(out["vault"]).resolve() == v.resolve()


NO_DELETE = '''
import os, errno
_root = os.path.realpath(os.environ["NO_DELETE_UNDER"])
def _guard(fn):
    def wrapped(path, *a, **k):
        p = os.path.realpath(os.fspath(path) if not isinstance(path, int) else "")
        if p.startswith(_root):
            raise PermissionError(errno.EPERM, "Operation not permitted", os.fspath(path))
        return fn(path, *a, **k)
    return wrapped
os.unlink = _guard(os.unlink); os.remove = _guard(os.remove); os.rmdir = _guard(os.rmdir)
'''


def test_full_session_works_when_deleting_in_the_folder_is_forbidden(tmp_path):
    """Cowork device_bash: rm/unlink in a connected folder fail with EPERM; mv and in-place writes work."""
    v = make_vault(tmp_path)
    shim = tmp_path / "shim"
    shim.mkdir()
    (shim / "sitecustomize.py").write_text(NO_DELETE)
    env = {"PYTHONPATH": str(shim), "NO_DELETE_UNDER": str(v)}
    run(v, "doctor", env_extra=env)
    run(v, "session", "start", "--mode", "test", "--minutes", "30", "--kcs", "9702-2.1", env_extra=env)
    for _ in range(30):
        act = run(v, "next", env_extra=env)
        if act["activity"] == "end":
            break
        if act["activity"] in ("questions", "awaiting"):
            parts = [f"{q['n']}?" for q in act["items"]]
            fb = run(v, "answer", ", ".join(parts), env_extra=env)
            assert all(r.get("event") for r in fb["results"]), fb  # every answer logged
    assert act["activity"] == "end"
    summary = run(v, "session", "end", env_extra=env)
    assert summary["answered"] > 0
    assert run(v, "next", env_extra=env)["activity"] == "no_session"
    run(v, "week", env_extra=env)
    assert not list((v / ".tutor").rglob("*.tmp"))


def test_errors_come_back_as_json_not_tracebacks(tmp_path):
    v = make_vault(tmp_path)
    assert run(v, "kc", "9702-9.9.9")["ok"] is False
    assert run(v, "answer", "1B3")["ok"] is False  # no session
    assert run(v, "inbox", "done", "Inbox/7.pdf")["ok"] is False


def test_answer_reads_entries_from_stdin(tmp_path):
    v = make_vault(tmp_path)
    run(v, "session", "start", "--mode", "test", "--minutes", "30", "--kcs", "9702-2.1")
    act = run(v, "next")
    fb = run(v, "answer", "-", stdin=", ".join(f"{q['n']}?" for q in act["items"]))
    assert len(fb["results"]) == len(act["items"]) and all(r.get("event") for r in fb["results"])


def test_find_maps_subject_words_and_topic_numbers(tmp_path):
    v = make_vault(tmp_path)
    hits = run(v, "find", "physics equations of motion")["matches"]
    assert hits[0].get("subtopic") == "9702-2.1" and hits[0]["has_pack"]
    assert run(v, "find", "physics topic 2")["matches"][0].get("topic") == "9702-2"


def test_engine_refuses_to_run_on_a_copy_of_the_folder(tmp_path):
    import shutil
    v = make_vault(tmp_path)
    copy = tmp_path / "elsewhere" / "STEM Tutor copy"
    shutil.copytree(v, copy)
    shutil.copytree(SCRIPT.parent, copy / ".tutor" / "engine", ignore=shutil.ignore_patterns("__pycache__"))
    env = {k: val for k, val in os.environ.items() if k != "STEM_TUTOR_VAULT"}
    env.update(STEM_TUTOR_MOUNTS=str(tmp_path / "nowhere/*"))
    p = subprocess.run([sys.executable, str(copy / ".tutor/engine/tutor.py"), "doctor"], capture_output=True, text=True, env=env)
    out = json.loads(p.stdout)
    assert out["ok"] is False and "copy" in out["error"]


def test_engine_accepts_a_symlinked_mount(tmp_path):
    import shutil
    real = tmp_path / "real" / "STEM Tutor"
    real.parent.mkdir()
    v = make_vault(tmp_path)
    shutil.copytree(v, real)
    shutil.copytree(SCRIPT.parent, real / ".tutor" / "engine", ignore=shutil.ignore_patterns("__pycache__"))
    link = tmp_path / "home" / "mnt" / "STEM Tutor"
    link.parent.mkdir(parents=True)
    link.symlink_to(real)
    env = {k: val for k, val in os.environ.items() if k != "STEM_TUTOR_VAULT"}
    env.update(STEM_TUTOR_MOUNTS=str(tmp_path / "nowhere/*"))
    p = subprocess.run([sys.executable, str(link / ".tutor/engine/tutor.py"), "doctor"], capture_output=True, text=True, env=env)
    assert json.loads(p.stdout)["ok"] is True


def test_next_after_a_worked_example_moves_on(tmp_path):  # B-020: in chat, `next` means the example is done
    v = make_vault(tmp_path)
    run(v, "session", "start", "--mode", "test", "--minutes", "30", "--kcs", "9702-2.1.4")
    seen = []
    for _ in range(6):
        act = run(v, "next")
        seen.append(act["activity"])
        if act["activity"] == "questions":
            run(v, "answer", ", ".join(f"{q['n']}?" for q in act["items"]))
        if seen[-2:] == ["worked", "worked"] or act["activity"] == "end":
            break
    assert "worked" in seen and seen[seen.index("worked") + 1] != "worked"
