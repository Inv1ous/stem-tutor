"""`tutor look`, run against a pretend Terminal: backup first, fonts, profiles only if missing, never touching the
learner's own profiles, then the Night look; `--undo` goes back. No real Terminal, fonts folder or preferences."""
import plistlib
import subprocess

import pytest

from fixtures import make_vault
from tutor_app import config, look, setup_look, termprofile


class FakeTerminal:
    def __init__(self, export_fails: str = "", have: dict | None = None):
        self.prefs = {"Window Settings": {"Basic": {}, "Study": {"Font": termprofile.font("Menlo-Regular", 15),
                                                                 "CommandString": "echo hi", "CursorType": 2}},
                      "Default Window Settings": "Basic", "Startup Window Settings": "Basic"}
        self.prefs["Window Settings"].update(have or {})
        self.export_fails, self.opened, self.calls = export_fails, [], []

    def run(self, args, **kw):
        self.calls.append(args)
        if args[:2] == ["defaults", "export"]:
            if self.export_fails:
                return subprocess.CompletedProcess(args, 1, "", self.export_fails)
            with open(args[3], "wb") as f:
                f.write(plistlib.dumps(self.prefs, fmt=plistlib.FMT_BINARY))
        elif args[0] == "open":  # Terminal adds the profile in the file
            p = plistlib.loads(open(args[1], "rb").read())
            self.opened.append(p)
            self.prefs["Window Settings"][p["name"]] = p
        elif args[0] == "osascript":
            return subprocess.CompletedProcess(args, 0, "true\n" if args[2] in self.prefs["Window Settings"] else "false\n", "")
        return subprocess.CompletedProcess(args, 0, "", "")


@pytest.fixture
def mac_like(tmp_path, monkeypatch):
    monkeypatch.setattr(setup_look, "IS_MAC", True)
    monkeypatch.setattr(setup_look, "FONT_DIR", tmp_path / "Fonts")
    monkeypatch.setattr(setup_look.time, "sleep", lambda s: None)
    yield
    look.use("classic")


def _install(vault, monkeypatch, term, **kw):
    monkeypatch.setattr(setup_look.subprocess, "run", term.run)
    said = []
    code = setup_look.install(vault, out=said.append, **kw)
    return code, "\n".join(said)


def test_look_backs_up_installs_and_switches_to_night(tmp_path, monkeypatch, mac_like):
    vault, term = make_vault(tmp_path), FakeTerminal()
    code, said = _install(vault, monkeypatch, term)
    assert code == 0, said
    backup = next((vault / ".tutor/backups").glob("terminal-*.plist"))
    assert plistlib.loads(backup.read_bytes())["Window Settings"]["Study"]["CursorType"] == 2  # the state before
    assert term.calls[0][:2] == ["defaults", "export"]  # the backup came first
    assert sorted(f.name for f in (tmp_path / "Fonts").iterdir()) == sorted(setup_look.FONTS)
    assert [p["name"] for p in term.opened] == ["STEM Tutor Night", "STEM Tutor Day"]
    night = term.opened[0]
    assert termprofile.decoded(night["Font"]) == ("JuliaMono-Regular", 15.0)  # the size the learner reads at
    assert "CommandString" not in night and night["CursorType"] == 2
    assert config.Settings.load(vault).theme == "night"
    assert "s = ut + ½at²" in said and "Cu²⁺ + 2e⁻ → Cu" in said and "band" in said
    assert term.prefs["Default Window Settings"] == "Basic"  # nothing else changed


def test_running_it_again_adds_nothing(tmp_path, monkeypatch, mac_like):
    vault, term = make_vault(tmp_path), FakeTerminal()
    _install(vault, monkeypatch, term)
    term.opened.clear()
    code, said = _install(vault, monkeypatch, term)
    assert code == 0 and term.opened == [] and said.count("already set up") == 2


def test_nothing_changes_when_the_backup_fails(tmp_path, monkeypatch, mac_like):
    vault, term = make_vault(tmp_path), FakeTerminal(export_fails="Could not write domain")
    code, said = _install(vault, monkeypatch, term)
    assert code == 1 and "nothing was changed" in said
    assert not (tmp_path / "Fonts").exists() and term.opened == [] and config.Settings.load(vault).theme == "classic"


def test_a_different_profile_of_the_same_name_is_never_replaced(tmp_path, monkeypatch, mac_like):
    old = termprofile.profile("STEM Tutor Night", look.PALETTES["night"], termprofile.ANSI["night"], size=11)
    vault, term = make_vault(tmp_path), FakeTerminal(have={"STEM Tutor Night": old})
    code, said = _install(vault, monkeypatch, term)
    assert code == 1 and "Delete it in Terminal › Settings › Profiles" in said
    assert [p["name"] for p in term.opened] == ["STEM Tutor Day"]
    assert term.prefs["Window Settings"]["STEM Tutor Night"] is old


def test_a_font_of_your_own_is_kept(tmp_path, monkeypatch, mac_like):
    (tmp_path / "Fonts").mkdir()
    (tmp_path / "Fonts" / "JuliaMono-Regular.ttf").write_bytes(b"an older JuliaMono")
    code, said = _install(make_vault(tmp_path), monkeypatch, FakeTerminal())
    assert (tmp_path / "Fonts" / "JuliaMono-Regular.ttf").read_bytes() == b"an older JuliaMono"
    assert "Kept your own JuliaMono-Regular.ttf" in said


def test_not_on_a_mac_it_does_nothing(tmp_path, monkeypatch):
    monkeypatch.setattr(setup_look, "IS_MAC", False)
    said = []
    assert setup_look.install(make_vault(tmp_path), out=said.append) == 1 and "on the Mac" in said[0]


def test_undo_goes_back_to_classic_and_says_how_to_remove_the_rest(tmp_path, monkeypatch, mac_like):
    vault, term = make_vault(tmp_path), FakeTerminal()
    _install(vault, monkeypatch, term)
    said = []
    assert setup_look.undo(vault, out=said.append) == 0
    text = "\n".join(said)
    assert config.Settings.load(vault).theme == "classic" and "close this window" in text
    first = sorted((vault / ".tutor/backups").glob("terminal-*.plist"))[0]
    assert f"defaults import com.apple.Terminal '{first}'" in text and "git checkout v1.6.1" in text


@pytest.mark.parametrize("theme,installed,version,want", [
    ("night", True, "471", {"Look": None, "Font": True, "Terminal profiles": True, "Colours": True}),
    ("night", False, "471", {"Look": None, "Font": False, "Terminal profiles": False, "Colours": True}),
    ("classic", False, "460", {"Look": None, "Font": None, "Terminal profiles": None, "Colours": None}),
])
def test_doctor_checks_the_look_only_where_it_matters(tmp_path, monkeypatch, mac_like, theme, installed, version, want):
    import json
    vault, term = make_vault(tmp_path), FakeTerminal()
    (vault / ".tutor/app_settings.json").write_text(json.dumps({"theme": theme}))
    if installed:
        _install(vault, monkeypatch, term)
        config.Settings(theme=theme).save(vault)

    def export_to_stdout(args, **kw):
        if args == ["defaults", "export", "com.apple.Terminal", "-"]:
            return subprocess.CompletedProcess(args, 0, plistlib.dumps(term.prefs).decode(), "")
        return term.run(args, **kw)
    monkeypatch.setattr(setup_look.subprocess, "run", export_to_stdout)
    monkeypatch.setenv("TERM_PROGRAM", "Apple_Terminal")
    monkeypatch.setenv("TERM_PROGRAM_VERSION", version)
    rows = {check.split(":")[0]: ok for ok, check, fix in setup_look.doctor_rows(vault)}
    assert rows == want


def test_doctor_marks_advice_apart_from_problems(tmp_path, monkeypatch, capsys):
    from tutor_app import __main__ as cli, mac
    monkeypatch.setattr(mac, "doctor", lambda vault: [(True, "Tutor folder: x", ""), (None, "Look: Classic", "optional")])
    cli.main(["doctor", "--vault", str(tmp_path)])
    out = capsys.readouterr().out
    assert "✓ Tutor folder" in out and "· Look: Classic" in out and "All good" in out
