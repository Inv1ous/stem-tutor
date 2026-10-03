"""Linking the Almanac page to the tutor: the block put into the page, and its merge rules (run in Node)."""
import json
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "build"))
import almanac_link  # noqa: E402

PAGE = "<html><body><main></main>\n<script>const OBJ = [];</script>\n</body>\n</html>\n"


def test_the_page_is_linked_once_and_the_original_is_kept(tmp_path):
    page = tmp_path / "A-Levels.html"
    page.write_text(PAGE)
    assert almanac_link.link(page)
    html = page.read_text()
    assert html.count("stem-tutor-sync:start") == 1 and '"A-Levels.tutor.js?"' in html
    assert html.index("const OBJ") < html.index("tutorMerge") < html.index("</body>")  # after the page's own script
    assert [p.read_text() for p in (tmp_path / ".backup").iterdir()] == [PAGE]
    assert not almanac_link.link(page)  # already linked: nothing changes
    assert page.read_text() == html


def merged(state, *updates):
    """Run the page's merge in Node on a planner state, one update from the tutor after another."""
    js = (REPO / "build/almanac_link.js").read_text()
    code = (js + f"\nconst S = {json.dumps(state)};\nconst out = {json.dumps(updates)}.map(T => tutorMerge(S, T));"
            "\nconsole.log(JSON.stringify([S, out]));")
    return json.loads(subprocess.run(["node", "-e", code], capture_output=True, text=True, check=True).stdout)


@pytest.mark.skipif(not shutil.which("node"), reason="needs Node to run the page's script")
def test_the_page_takes_what_the_tutor_knows_and_keeps_what_the_learner_entered():
    mine = {"done": {"1-math1": 1}, "rag": {"chem-1": "g"}, "scores": {"chem-P1": 30, "math-P1": ""},
            "wall": {"2026-09-20": 1}, "retro": {"5": {"broke": "my own note", "fix": "mine"}},
            "err": {"Wrong method": 2}, "stage": 2}
    first = {"stamp": "a", "done": {"5-phys1": 1}, "rag": {"chem-1": "r", "phys-2": "a"},
             "scores": {"chem-P1": 22, "math-P1": 60}, "wall": {"2026-09-29": 1}, "err": {"Wrong method": 3},
             "retro": {"5": {"broke": "tutor", "fix": "t"}, "6": {"broke": "b6", "fix": "f6"}}, "stage": 0}
    second = {**first, "stamp": "b", "scores": {"chem-P1": 23, "math-P1": 65}, "err": {"Wrong method": 4},
              "retro": {"6": {"broke": "b6 again", "fix": "f6"}}}
    S, changed = merged(mine, first, first, second)
    assert changed == [True, False, True]  # the same facts are merged once
    assert S["done"] == {"1-math1": 1, "5-phys1": 1}  # ticks are added, never taken away
    assert S["rag"] == {"chem-1": "r", "phys-2": "a"}  # the tutor decides every colour
    assert S["scores"] == {"chem-P1": 30, "math-P1": 65}  # a score the learner typed stays; the tutor's own moves on
    assert S["wall"] == {"2026-09-20": 1, "2026-09-29": 1}
    assert S["err"] == {"Wrong method": 6}  # the learner's 2 and the tutor's 4, not counted twice
    assert S["retro"]["5"] == {"broke": "my own note", "fix": "mine"} and S["retro"]["6"]["broke"] == "b6 again"
    assert S["stage"] == 0


def run_block(tmp_path, typing=False):
    """Run the whole block as the page would, with stand-ins for the page's own state and functions."""
    (tmp_path / "A-Levels.tutor.js").write_text(
        'window.TUTOR_SYNC = {"stamp": "s1", "done": {"5-phys1": 1}, "rag": {"phys-2": "a"}};\n')
    block = (REPO / "build/almanac_link.js").read_text().replace("__FILE__", "A-Levels.tutor.js")
    page = f"""
const fs = require("fs"), vm = require("vm"), calls = [];
global.window = global;
global.S = {{done: {{}}, rag: {{}}, scores: {{}}, wall: {{}}, retro: {{}}, err: {{}}, stage: 2}};
global.save = () => calls.push("save"); global.renderAll = () => calls.push("render"); global.toast = m => calls.push(m);
global.setInterval = (fn, ms) => calls.push("every " + ms);
global.document = {{ activeElement: {{ tagName: "{'TEXTAREA' if typing else 'BODY'}" }}, createElement: () => ({{ remove() {{}} }}),
  head: {{ appendChild(el) {{ vm.runInThisContext(fs.readFileSync({json.dumps(str(tmp_path))} + "/" + el.src.split("?")[0], "utf8")); el.onload(); }} }} }};
"""
    out = subprocess.run(["node", "-e", page + block + "\nconsole.log(JSON.stringify([S, calls]));"],
                         capture_output=True, text=True, check=True).stdout
    return json.loads(out)


@pytest.mark.skipif(not shutil.which("node"), reason="needs Node to run the page's script")
def test_the_page_loads_the_tutors_file_saves_and_redraws(tmp_path):
    S, calls = run_block(tmp_path)
    assert S["done"] == {"5-phys1": 1} and S["rag"] == {"phys-2": "a"} and S["tutor"]["stamp"] == "s1"
    assert calls == ["save", "render", "Updated by STEM Tutor", "every 30000"]  # now, then every half minute
    S, calls = run_block(tmp_path, typing=True)  # never under the learner's hands: it waits for the next turn
    assert S["done"] == {} and calls == ["every 30000"]
