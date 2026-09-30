import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "build"))
import publish  # noqa: E402


def test_pruning_keeps_the_two_newest_previous_versions_past_v9(tmp_path):  # B-019
    for n in range(1, 13):
        (tmp_path / f"v{n}").mkdir()
    publish.prune_versions(tmp_path, "v12")
    assert sorted(p.name for p in tmp_path.iterdir()) == ["v10", "v11", "v12"]
