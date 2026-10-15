import importlib
import json
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
FAKE = str(REPO / "tests/fake_shortcut_worker.py")


def entry(n, score, spec="P1"):
    return {"id": f"SEM-{spec}-e{n}", "spec": spec, "section": "1. Algebra", "topic": "", "title": f"Entry {n}",
            "score": score, "origin": "base", "body": f"Body of entry {n}, $x^2$."}


@pytest.fixture
def gen(tmp_path, monkeypatch):
    monkeypatch.setenv("FOUNDRY_ROOT", str(tmp_path))
    monkeypatch.setenv("FOUNDRY_CODEX", FAKE)
    monkeypatch.setenv("FOUNDRY_CLAUDE", FAKE)
    (tmp_path / "usage.json").write_text(json.dumps({"codex": {"seven_day": {"used": 10.0, "resets": None}}}))
    monkeypatch.setenv("FOUNDRY_USAGE_FILE", str(tmp_path / "usage.json"))
    for k in ("FAKE_SG_MODE", "FAKE_SG_COUNT", "FAKE_SG_ONLY", "FAKE_SG_WRONG", "FAKE_ARGV"):
        monkeypatch.delenv(k, raising=False)
    out = tmp_path / "build/out/shortcuts"
    out.mkdir(parents=True)
    rows = [entry(i, s) for i, s in enumerate([10, 9, 9, 8, 7, 3], 1)]
    (out / "P1.json").write_text(json.dumps(rows))
    sys.path.insert(0, str(REPO / "foundry"))
    import shortcuts_gen
    return importlib.reload(shortcuts_gen)


def lessons(gen):
    return json.loads((gen.LESSONS / "P1.json").read_text())


def test_run_writes_best_first_and_skips_below_min_score(gen, capsys):
    assert gen.main(["run", "--spec", "P1", "--batch", "2", "--max-batches", "1"]) == 0
    assert set(lessons(gen)) == {"SEM-P1-e1", "SEM-P1-e2"}
    assert gen.main(["run", "--spec", "P1", "--batch", "2"]) == 0
    assert set(lessons(gen)) == {f"SEM-P1-e{i}" for i in (1, 2, 3, 4)}  # 7/10 and 3/10 are below the default 8
    assert list(gen.LOGS.glob("shortcuts-P1-*.log"))


def test_existing_lessons_survive_and_are_not_redone(gen):
    gen.LESSONS.mkdir(parents=True)
    (gen.LESSONS / "P1.json").write_text(json.dumps({"SEM-P1-e1": {"id": "SEM-P1-e1", "mine": True}, "SEM-P1-old": {"x": 1}}))
    gen.main(["run", "--spec", "P1"])
    got = lessons(gen)
    assert got["SEM-P1-e1"] == {"id": "SEM-P1-e1", "mine": True} and "SEM-P1-old" in got and "SEM-P1-e2" in got


def test_dry_run_launches_nothing(gen, capsys):
    gen.main(["run", "--spec", "P1", "--dry-run"])
    assert "would run" in capsys.readouterr().out and not (gen.LESSONS / "P1.json").exists()


def test_worker_command(gen, monkeypatch, tmp_path):
    monkeypatch.setenv("FAKE_ARGV", str(tmp_path / "argv.json"))
    gen.main(["run", "--spec", "P1", "--max-batches", "1", "--effort", "low"])
    argv = json.loads((tmp_path / "argv.json").read_text())
    assert "--search" not in argv and argv[argv.index("-m") + 1] == "gpt-6-sol"
    assert 'model_reasoning_effort="low"' in argv and "--output-schema" in argv and "workspace-write" in argv
    gen.main(["run", "--spec", "P1", "--max-batches", "1", "--web", "--min-score", "0"])
    assert "--search" in json.loads((tmp_path / "argv.json").read_text())


def test_bad_batch_is_retried_once_one_effort_higher(gen, monkeypatch, tmp_path):
    monkeypatch.setenv("FAKE_SG_MODE", "bad_first")
    monkeypatch.setenv("FAKE_SG_COUNT", str(tmp_path / "count"))
    gen.main(["run", "--spec", "P1", "--batch", "2", "--max-batches", "1"])
    assert set(lessons(gen)) == {"SEM-P1-e1", "SEM-P1-e2"} and (tmp_path / "count").read_text() == "2"
    retry = next(gen.LOGS.glob("*r.log"))
    assert "gpt-6-sol/medium" in retry.read_text() and "gpt-6-sol/low" in next(gen.LOGS.glob("*b1.log")).read_text()


def test_always_bad_is_not_merged(gen, monkeypatch):
    monkeypatch.setenv("FAKE_SG_MODE", "bad")
    gen.main(["run", "--spec", "P1", "--max-batches", "1"])
    assert not (gen.LESSONS / "P1.json").exists()


def test_garbage_output_merges_nothing(gen, monkeypatch):
    monkeypatch.setenv("FAKE_SG_MODE", "garbage")
    gen.main(["run", "--spec", "P1", "--max-batches", "1"])
    assert not (gen.LESSONS / "P1.json").exists()


def test_missing_lesson_stays_pending(gen, monkeypatch):
    monkeypatch.setenv("FAKE_SG_ONLY", "SEM-P1-e1")
    gen.main(["run", "--spec", "P1", "--batch", "2", "--max-batches", "1"])
    assert set(lessons(gen)) == {"SEM-P1-e1"}
    assert [e["id"] for e in gen.pending("P1", 8)][0] == "SEM-P1-e2"


def test_usage_limit_stops_the_run(gen, monkeypatch, capsys):
    monkeypatch.setenv("FAKE_SG_MODE", "limit")
    assert gen.main(["run", "--spec", "P1", "--batch", "1"]) == 1
    assert "usage limit" in capsys.readouterr().out


def test_stops_when_codex_week_is_used(gen, tmp_path, capsys):
    (tmp_path / "usage.json").write_text(json.dumps({"codex": {"seven_day": {"used": 71.0, "resets": None}}}))
    gen.main(["run", "--spec", "P1"])
    assert "stopping" in capsys.readouterr().out and not (gen.LESSONS / "P1.json").exists()
    gen.main(["run", "--spec", "P1", "--stop-codex-week", "90", "--max-batches", "1"])
    assert (gen.LESSONS / "P1.json").exists()


def make(gen, **kw):
    ns = {}
    src = Path(FAKE).read_text().split("if \"exec\" in args:")[0]
    exec(src.replace("args = sys.argv[1:]", "args = []"), ns)
    lesson = ns["lesson"]("SEM-P1-e1", False, 0)
    return lesson


def test_checks_accept_a_good_lesson_and_name_each_fault(gen):
    ok = make(gen)
    assert gen.lesson_problems(ok) == []

    def broken(fn):
        les = json.loads(json.dumps(ok))
        fn(les)
        return gen.lesson_problems(les)
    assert broken(lambda l: l["practice"].pop())
    assert broken(lambda l: l["practice"][0]["hints"].pop())
    assert broken(lambda l: l["practice"][0].update(answer="about 9"))
    assert broken(lambda l: l["practice"][1]["options"].update(D=""))
    assert broken(lambda l: l["practice"][1].update(answer="E"))
    assert broken(lambda l: l["practice"][0]["hints"].__setitem__(2, "The total is 7."))
    assert broken(lambda l: l["practice"][1]["hints"].__setitem__(0, "Option B is wrong."))
    assert broken(lambda l: l.update(recall=l["recall"][:1]))
    assert broken(lambda l: l.update(hook="  "))
    assert broken(lambda l: l.update(steps=["only one"]))
    assert broken(lambda l: l.update(why="lost � character"))
    assert broken(lambda l: l.update(idea="Use $\\foo x$."))
    assert broken(lambda l: l["practice"][0].update(options={"A": "x", "B": "", "C": "", "D": ""}))


def test_numbers_and_give_aways(gen):
    assert gen.number_of("$4.2\\times10^{3}$") == 4200 and gen.number_of("-3") == -3 and gen.number_of("12 m") is None
    assert not gen.gives_away("There are 17 terms.", "7") and gen.gives_away("so it is 7.", "7")


def test_status_counts_bands(gen, capsys):
    gen.main(["run", "--spec", "P1", "--max-batches", "1"])
    capsys.readouterr()
    gen.main(["status"])
    out = capsys.readouterr().out
    assert "P1" in out and "entries    6" in out and "with lesson    6" not in out and "10: 1/1" in out and "<=7: 0/2" in out


def test_verify_marks_mismatches_and_deletes_nothing(gen, monkeypatch):
    gen.main(["run", "--spec", "P1", "--max-batches", "1"])
    assert gen.main(["verify", "--sample", "50"]) == 0
    assert not any(v.get("unverified") for v in lessons(gen).values())
    monkeypatch.setenv("FAKE_SG_WRONG", "1")
    gen.main(["verify", "--sample", "50"])
    got = lessons(gen)
    assert len(got) == 4 and all(v["unverified"] for v in got.values())


def test_a_single_backslash_in_the_workers_json_is_put_back():
    import sys
    from pathlib import Path
    sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "foundry"))
    import shortcuts_gen as g
    assert g.repair({"a": ["$\x0crac12$ and $\ttimes$ and $\x08eta$"]}) == {"a": ["$\\frac12$ and $\\ttimes$ and $\\beta$"]}
