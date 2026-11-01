"""Exercise the checker's documented shell handoff without launching an AI worker."""
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys

from test_foundry import fdy, SUB


REPO = Path(__file__).resolve().parents[1]


def test_checker_cli_supplies_whole_quoted_report_paths(fdy, tmp_path):
    fdy.cmd_add([SUB])
    data = tmp_path / '02 Education/~~ AI Workflow'
    shutil.copytree(fdy.STATE, data / 'foundry/state')
    cwd = tmp_path / 'checker cwd'
    cwd.mkdir()
    result = subprocess.run(
        [sys.executable, str(REPO / 'foundry/foundry.py'), 'prompt', 'checker', SUB],
        cwd=cwd, env={**os.environ, 'FOUNDRY_ROOT': str(data), 'PYTHONDONTWRITEBYTECODE': '1'},
        capture_output=True, text=True,
    )
    assert result.returncode == 0, result.stderr
    command = re.search(r'^Prepare report directory: `([^`]+)`\.$', result.stdout, re.M)
    assert command, result.stdout
    operand = re.search(r'^Report file: .* entire quoted operand: (.+)\.$', result.stdout, re.M)
    assert operand, result.stdout
    before = set(tmp_path.rglob('*'))
    subprocess.run(['/bin/sh', '-c', command[1]], cwd=cwd, check=True)
    subprocess.run(['/bin/sh', '-c', "printf '%s\\n' '{\"findings\": []}' > " + operand[1]],
                   cwd=cwd, check=True)
    assert (data / 'build/work/foundry').is_dir()
    report = data / f'build/work/foundry/{SUB}.check.json'
    assert report.read_text() == '{"findings": []}\n'
    assert list(cwd.iterdir()) == []
    assert set(tmp_path.rglob('*')) - before == {
        data / 'build', data / 'build/work', data / 'build/work/foundry', report,
    }
