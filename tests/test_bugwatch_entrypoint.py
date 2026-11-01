from pathlib import Path
import subprocess
import sys


ROOT = Path(__file__).resolve().parents[1]


def test_root_bugwatch_command_shows_the_board_from_any_directory(tmp_path):
    result = subprocess.run(
        [sys.executable, str(ROOT / "bugwatch.py"), "--all"],
        cwd=tmp_path,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0
    assert "LATEST ACTIVITY" in result.stdout
    assert "QUALITY OF LIFE" in result.stdout
