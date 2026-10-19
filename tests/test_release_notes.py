"""The places that say what version this is, and what changed, must agree with the app. Asked by the learner: the update
logs were not updated to show the changes. A release bumps `app/tutor_app/__init__.py`; these fail until every one of
them says the same, so none can be left behind."""
import json
import re
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "app"))
from tutor_app import __version__  # noqa: E402


def test_the_changelog_status_readme_plugin_and_guide_name_the_current_version():
    assert re.search(rf"^## {re.escape(__version__)} — ", (REPO / "CHANGELOG.md").read_text(), re.M), "CHANGELOG.md"
    assert re.search(rf"^## v{re.escape(__version__)} \(", (REPO / "STATUS.md").read_text(), re.M), "STATUS.md"
    assert f"Version **{__version__}**" in (REPO / "README.md").read_text(), "README.md"
    plugin = json.loads((REPO / "plugin/stem-tutor/.claude-plugin/plugin.json").read_text())
    assert plugin["version"] == __version__, "plugin.json"
    guide = (REPO / "build/out/notes/How It Works.md").read_text()
    assert f"_Version {__version__}_" in guide, "How It Works.md (the guide in the vault)"


def test_the_changelog_is_newest_first_and_the_guide_lists_the_current_minor_release():
    versions = re.findall(r"^## (\d+\.\d+\.\d+) — ", (REPO / "CHANGELOG.md").read_text(), re.M)
    key = lambda v: tuple(int(x) for x in v.split("."))  # noqa: E731
    assert versions == sorted(versions, key=key, reverse=True) and versions[0] == __version__
    guide = (REPO / "build/out/notes/How It Works.md").read_text()
    minor = ".".join(__version__.split(".")[:2])
    assert f"[!example] New in {minor}" in guide, "How It Works.md has no 'New in' note for this release line"
