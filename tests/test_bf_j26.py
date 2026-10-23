"""Regression checks for Almanac ownership and date imports."""
from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

import pytest

from fixtures import make_vault
from test_session import Clock, T0
from tutorlib import almanac, report, session, store


def export(root: Path, state: dict) -> None:
    folder = root / "Almanac"
    folder.mkdir(exist_ok=True)
    store.write_json(folder / "almanac-progress-test.json", state)


def make_tutor(tmp_path: Path) -> session.Tutor:
    root = make_vault(tmp_path)
    path = next((root / ".tutor/packs").glob("v*/plan.json"))
    plan = store.read_json(path)
    plan.update(papers=[{"code": "9702/22", "short": "AS", "date": None},
                        {"code": "9702/42", "short": "A2", "date": "2028-05-15"}],
                sittings={"A2 (9702)": "2028-05-15"})
    store.write_json(path, plan)
    return session.Tutor(store.Vault(root), now=Clock(T0))


@pytest.mark.skipif(not shutil.which("node"), reason="needs Node to run the page's script")
def test_a_tick_taken_away_and_given_back_counts_as_the_learners(tmp_path):
    """B-047: a redraw between unticking and reticking must relinquish tutor ownership."""
    js = (Path(__file__).resolve().parents[1] / "build/almanac_link.js").read_text()
    page = '''
const S = {done: {"5-phys1": 1, "6-phys1": 1},
           tutor: {stamp: "old", done: {"5-phys1": 1, "6-phys1": 1}}};
let saved;
function save() { saved = JSON.parse(JSON.stringify(S)); }
function setInterval() {}
function requestAnimationFrame(fn) { fn(); }
class MutationObserver { constructor(fn) { globalThis.redraw = fn; } observe() {} }
const document = {body: {}, getElementById: () => null,
                  createElement: () => ({}), head: {appendChild() {}}};
const window = {};
'''
    actions = '''
delete S.done["5-phys1"]; redraw();
S.done["5-phys1"] = 1; redraw(); save();
tutorMerge(S, {stamp: "new", done: {}});
console.log(JSON.stringify({saved, state: S}));
'''
    result = subprocess.run(["node", "-e", page + js + actions], check=True, text=True, capture_output=True)
    states = json.loads(result.stdout)
    tutor = make_tutor(tmp_path)
    for state in states.values():
        export(tutor.vault.root, state)
        assert almanac.ticks(tutor.vault.root) == {"5-phys1"}
        assert tutor.ticks() == {"5-phys1"}


def test_an_impossible_exam_date_does_not_break_todays_plan(tmp_path):
    """B-069: damaged exported dates must not reach countdown calculations."""
    tutor = make_tutor(tmp_path)
    export(tutor.vault.root, {"dates": {"0": "2027-02-30", "1": "2028-02-29",
                                       "2": "0000-01-01", "3": "2027-13-01"}})
    tutor.read_almanac()
    assert report.today_note(tutor)
    assert almanac.exam_dates(tutor.vault.root) == {1: "2028-02-29"}


def test_removing_an_exam_date_restores_the_published_plan(tmp_path):
    """B-085: a running tutor must use the same dates as a newly opened tutor."""
    tutor = make_tutor(tmp_path)
    for dates in ({"0": "2027-05-20", "1": "2028-06-01"},
                  {"1": "2028-06-02"}, {}):
        export(tutor.vault.root, {"dates": dates})
        tutor.read_almanac()
        fresh = session.Tutor(store.Vault(tutor.vault.root), now=Clock(T0))
        assert tutor.packs.plan == fresh.packs.plan
    assert [p["date"] for p in tutor.packs.plan["papers"]] == [None, "2028-05-15"]
    assert tutor.packs.plan["sittings"] == {"A2 (9702)": "2028-05-15"}
