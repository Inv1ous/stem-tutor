"""Content checks for rendered teaching media."""
from __future__ import annotations

from io import BytesIO
import math
import re
import xml.etree.ElementTree as ET


_SVG_NS = "http://www.w3.org/2000/svg"
_MAX_RENDER_DIMENSION = 1024
_LENGTH = re.compile(r"^\s*([+]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][+-]?\d+)?)\s*(px|pt|pc|in|cm|mm|%)?\s*$")


def _svg_length(value: str | None) -> float | None:
    if value is None:
        return None
    match = _LENGTH.fullmatch(value)
    if not match:
        return None
    number = float(match.group(1))
    unit = match.group(2) or "px"
    scale = {"px": 1.0, "pt": 96 / 72, "pc": 16.0,
             "in": 96.0, "cm": 96 / 2.54, "mm": 96 / 25.4}
    if unit == "%":
        return None
    result = number * scale[unit]
    return result if math.isfinite(result) and result > 0 else None


def _viewbox(root) -> tuple[float, float] | None:
    value = root.attrib.get("viewBox")
    if value is None:
        return None
    try:
        parts = [float(part) for part in re.split(r"[\s,]+", value.strip())]
    except ValueError:
        return None
    if (len(parts) != 4 or not all(math.isfinite(part) for part in parts)
            or parts[2] <= 0 or parts[3] <= 0):
        return None
    return parts[2], parts[3]


def _render_size(root) -> tuple[int, int] | None:
    viewbox = _viewbox(root)
    if "viewBox" in root.attrib and viewbox is None:
        return None

    raw_width, raw_height = root.attrib.get("width"), root.attrib.get("height")
    width, height = _svg_length(raw_width), _svg_length(raw_height)
    if raw_width is not None and width is None and not (raw_width.strip().endswith("%") and viewbox):
        return None
    if raw_height is not None and height is None and not (raw_height.strip().endswith("%") and viewbox):
        return None

    if width is not None and height is not None:
        ratio = width / height
        long_edge = max(width, height)
    elif viewbox and (width is not None or height is not None):
        vb_width, vb_height = viewbox
        ratio = vb_width / vb_height
        if width is not None:
            long_edge = max(width, width / ratio)
        else:
            long_edge = max(height * ratio, height)
    elif viewbox:
        vb_width, vb_height = viewbox
        ratio = vb_width / vb_height
        long_edge = _MAX_RENDER_DIMENSION
    else:
        return None

    if not math.isfinite(ratio) or ratio <= 0 or not math.isfinite(long_edge) or long_edge <= 0:
        return None
    scale = min(1.0, _MAX_RENDER_DIMENSION / long_edge)
    if ratio >= 1:
        out_width = max(1, round(long_edge * scale))
        out_height = max(1, round(long_edge * scale / ratio))
    else:
        out_height = max(1, round(long_edge * scale))
        out_width = max(1, round(long_edge * scale * ratio))
    return out_width, out_height


def svg_problem(data: bytes) -> str | None:
    """Return why an SVG is not a usable visible diagram, or ``None`` if it is."""
    if not isinstance(data, bytes) or not data:
        return "SVG is empty"
    try:
        root = ET.fromstring(data)
    except (ET.ParseError, ValueError):
        return "SVG XML is invalid"
    if root.tag != f"{{{_SVG_NS}}}svg":
        return "SVG root element is missing or invalid"
    # The registered SVG hash cannot vouch for loose files or remote images/fonts.
    for element in root.iter():
        for name, value in element.attrib.items():
            if name.rsplit('}', 1)[-1] == 'href' and not value.startswith(('#', 'data:image/')):
                return "SVG references an external resource"
        styles = list(element.attrib.values()) + ([element.text or ''] if element.tag.endswith('}style') else [])
        for style in styles:
            if any(not target.strip().strip('\"\'').startswith('#')
                   for target in re.findall(r'url\s*\(([^)]*)\)', style, flags=re.IGNORECASE)):
                return "SVG references an external resource"

    size = _render_size(root)
    if size is None:
        return "SVG viewport is missing or invalid"
    width, height = size
    if width < 16 or height < 16:
        return "SVG viewport is smaller than 16 px"

    try:
        import cairosvg
        from PIL import Image

        rendered = cairosvg.svg2png(bytestring=data, output_width=width, output_height=height)
        with Image.open(BytesIO(rendered)) as image:
            image.load()
            if image.size != size:
                return "SVG rendered dimensions do not match its viewport"
            rgba = image.convert("RGBA")
            background = Image.new("RGB", rgba.size, "white")
            background.paste(rgba.convert("RGB"), mask=rgba.getchannel("A"))
            if background.getcolors(maxcolors=1) is not None:
                return "SVG renders as a uniform or transparent image"
    except Exception as exc:
        return f"SVG cannot be rendered: {type(exc).__name__}"
    return None
