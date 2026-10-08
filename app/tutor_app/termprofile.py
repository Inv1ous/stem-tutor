"""macOS Terminal profiles for the tutor's window (.terminal files), made from the same palette as the app, so the
window around the app (its edges, cursor and colours) matches the look exactly. Standard library only: a profile is a
property list whose colours and font are small archived objects, written here in the form Terminal itself exports."""
from __future__ import annotations

import plistlib

FONT = "JuliaMono-Regular"  # the PostScript name of the bundled font (app/tutor_app/fonts)
SIZE = 13.0  # used when the learner has no "Study" profile to take the size from
COLUMNS, ROWS = 140, 46  # as the launcher opens the window

ANSI = {  # the 16 colours a shell uses in this window before and after the app (the app draws its own)
    "night": {"Black": "#23262c", "Red": "#ef8088", "Green": "#7cc48a", "Yellow": "#e6bd6c", "Blue": "#73a7f5",
              "Magenta": "#bd8ff2", "Cyan": "#6cc4c4", "White": "#c9ccd2",
              "BrightBlack": "#7b818b", "BrightRed": "#f4a0a6", "BrightGreen": "#9bd4a6", "BrightYellow": "#eccd90",
              "BrightBlue": "#98bff8", "BrightMagenta": "#cfadf5", "BrightCyan": "#93d4d4", "BrightWhite": "#e4e6ea"},
    "day": {"Black": "#1d2025", "Red": "#b2242f", "Green": "#23703a", "Yellow": "#875600", "Blue": "#1f5bb5",
            "Magenta": "#6f2fb0", "Cyan": "#1d6f75", "White": "#6d727b",
            "BrightBlack": "#4a4f58", "BrightRed": "#c8323d", "BrightGreen": "#2b8146", "BrightYellow": "#9a6300",
            "BrightBlue": "#2a6bc9", "BrightMagenta": "#7f3fc2", "BrightCyan": "#23818a", "BrightWhite": "#4a4f58"},
}
# settings worth keeping from the learner's own "Study" profile (how the title bar, cursor and bell behave); never a
# startup command
FROM_STUDY = ("ShowActiveProcessInTitle", "ShowActiveProcessArgumentsInTitle", "ShowCommandKeyInTitle",
              "ShowDimensionsInTitle", "ShowRepresentedURLInTitle", "ShowRepresentedURLPathInTitle",
              "ShowShellCommandInTitle", "ShowTTYNameInTitle", "ShowWindowSettingsNameInTitle", "WindowTitle",
              "CursorType", "CursorBlink", "Bell", "VisualBell", "VisualBellOnlyWhenMuted", "BellBadge", "BellBounce",
              "BellBounceCritical", "shellExitAction", "TerminalType", "useOptionAsMetaKey", "keyMapBoundKeys",
              "ScrollAlternateScreen")
QUIET_TITLE = {key: False for key in FROM_STUDY[:9]}  # only the name the app gives its window: STEM Tutor

# linear sRGB → linear Generic RGB (Apple's calibrated RGB, D65, gamma 1.8), the space Terminal keeps colours in
_TO_GENERIC = ((0.974850, 0.027295, -0.002145), (-0.020000, 1.054209, -0.034209), (0.001691, 0.001564, 0.996745))


def srgb_to_generic(hex_colour: str) -> tuple[float, float, float]:
    def linear(c: float) -> float:
        return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4
    rgb = [linear(int(hex_colour[i:i + 2], 16) / 255) for i in (1, 3, 5)]
    out = (sum(m * c for m, c in zip(row, rgb)) for row in _TO_GENERIC)
    return tuple(min(1.0, max(0.0, v)) ** (1 / 1.8) for v in out)


def _archive(objects: list) -> bytes:
    return plistlib.dumps({"$version": 100000, "$archiver": "NSKeyedArchiver", "$top": {"root": plistlib.UID(1)},
                           "$objects": objects}, fmt=plistlib.FMT_BINARY)


def colour(hex_colour: str, device: bool = False) -> bytes:
    """An archived NSColor. Calibrated (Generic RGB) as Terminal's own exports are; `device` keeps the plain numbers."""
    rgb = tuple(int(hex_colour[i:i + 2], 16) / 255 for i in (1, 3, 5)) if device else srgb_to_generic(hex_colour)
    return _archive(["$null", {"NSRGB": (" ".join(f"{v:.10f}" for v in rgb) + "\x00").encode(),
                               "NSColorSpace": 2 if device else 1, "$class": plistlib.UID(2)},
                     {"$classname": "NSColor", "$classes": ["NSColor", "NSObject"]}])


def font(name: str, size: float) -> bytes:
    """An archived NSFont."""
    return _archive(["$null", {"NSName": plistlib.UID(2), "NSSize": float(size), "NSfFlags": 16,
                               "$class": plistlib.UID(3)}, name,
                     {"$classname": "NSFont", "$classes": ["NSFont", "NSObject"]}])


def profile(name: str, palette: dict, ansi: dict, size: float = SIZE, study: dict | None = None,
            device: bool = False) -> dict:
    """The settings of one profile: the look's colours, the bundled font at the learner's size, a 140×46 window."""
    p = {"name": name, "type": "Window Settings", "ProfileCurrentVersion": 2.07,
         "BackgroundColor": colour(palette["background"], device), "TextColor": colour(palette["text"], device),
         "TextBoldColor": colour(palette["text"], device), "CursorColor": colour(palette["tutor"], device),
         "SelectionColor": colour(palette["selection"], device),
         **{f"ANSI{key}Color": colour(value, device) for key, value in ansi.items()},
         "Font": font(FONT, size), "FontAntialias": True, "FontWidthSpacing": 1.0, "FontHeightSpacing": 1.0,
         "UseBrightBold": False, "BackgroundBlur": 0.0, "BackgroundSettingsForInactiveWindows": False,
         "columnCount": COLUMNS, "rowCount": ROWS, **QUIET_TITLE}
    p.update({key: study[key] for key in FROM_STUDY if study and key in study})
    return p


def dumps(settings: dict) -> bytes:
    return plistlib.dumps(settings, fmt=plistlib.FMT_XML)


def decoded(blob: bytes):
    """What an archived colour or font holds: (r, g, b, colour space) or (font name, size)."""
    objects = plistlib.loads(blob)["$objects"]
    root = objects[1]
    if "NSRGB" in root:
        return (*(float(v) for v in root["NSRGB"].rstrip(b"\x00").split()), root["NSColorSpace"])
    return objects[root["NSName"].data], root["NSSize"]
