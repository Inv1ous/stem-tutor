"""The Terminal profiles: the look's colours and the bundled font, in the form Terminal's own exports take."""
import plistlib

import pytest

from tutor_app import look, termprofile


def test_colours_are_converted_as_terminal_stores_them():
    # Solarized Dark's own Terminal profile stores #002b36 as calibrated 0.01592440531 0.1265209168 0.1596960127
    assert termprofile.srgb_to_generic("#002b36") == pytest.approx((0.0159244, 0.1265209, 0.1596960), abs=2e-4)
    assert termprofile.decoded(termprofile.colour("#002b36"))[3] == 1  # calibrated, as that export
    assert termprofile.decoded(termprofile.colour("#16181c", device=True)) == pytest.approx(
        (0x16 / 255, 0x18 / 255, 0x1c / 255, 2))


@pytest.mark.parametrize("name", ["night", "day"])
def test_a_profile_carries_the_look_the_font_and_the_window(name):
    pal = look.PALETTES[name]
    p = plistlib.loads(termprofile.dumps(termprofile.profile(look.TERMINAL_PROFILES[name], pal, termprofile.ANSI[name],
                                                             size=15)))
    assert p["name"] == look.TERMINAL_PROFILES[name] and p["type"] == "Window Settings"
    assert p["ProfileCurrentVersion"] == 2.07  # what a profile exported from a current Terminal carries
    assert termprofile.decoded(p["BackgroundColor"])[:3] == pytest.approx(termprofile.srgb_to_generic(pal["background"]))
    assert termprofile.decoded(p["TextColor"])[:3] == pytest.approx(termprofile.srgb_to_generic(pal["text"]))
    assert termprofile.decoded(p["Font"]) == ("JuliaMono-Regular", 15.0)
    assert (p["columnCount"], p["rowCount"], p["FontHeightSpacing"]) == (140, 46, 1.0)  # bars join, borders meet
    assert len([k for k in p if k.startswith("ANSI")]) == 16 and not p["ShowDimensionsInTitle"]
    archive = plistlib.loads(p["BackgroundColor"])
    assert archive["$archiver"] == "NSKeyedArchiver" and archive["$objects"][2]["$classname"] == "NSColor"


def test_what_is_kept_from_the_study_profile_never_includes_a_command():
    study = {"CommandString": "rm -rf ~", "RunCommandAsShell": True, "CursorType": 2, "ShowTTYNameInTitle": True,
             "FontHeightSpacing": 1.3, "BackgroundAlphaInactive": 0.2}
    p = termprofile.profile("STEM Tutor Night", look.PALETTES["night"], termprofile.ANSI["night"], study=study)
    assert "CommandString" not in p and "RunCommandAsShell" not in p and "BackgroundAlphaInactive" not in p
    assert p["CursorType"] == 2 and p["ShowTTYNameInTitle"] is True and p["FontHeightSpacing"] == 1.0
