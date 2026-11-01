"""Bounded terminal previews of verified Library figures; full-size originals stay intact."""
from __future__ import annotations

from io import BytesIO
from pathlib import Path
import math
import re

from PIL import Image

from rich.panel import Panel
from rich.color import Color
from rich.style import Style
from rich.text import Text

from tutorlib.asset_library import AssetLibrary


class FigurePixels:
    """Render the actual image's pixels in terminal cells, keeping its aspect ratio."""

    def __init__(self, image):
        self.image = image

    def __rich_console__(self, console, options):
        width = max(1, min(84, options.max_width))
        scale = min(width / self.image.width, 24 / self.image.height)
        width = max(1, round(self.image.width * scale))
        height = max(2, round(self.image.height * scale))
        image = self.image.resize((width, height), Image.Resampling.LANCZOS)
        for y in range(0, height, 2):
            row = Text()
            for x in range(width):
                top = image.getpixel((x, y))
                bottom = image.getpixel((x, min(y + 1, height - 1)))
                row.append('▀', style=Style(color=Color.from_rgb(*top), bgcolor=Color.from_rgb(*bottom)))
            yield row


def figure_preview(vault_root: Path, reference: str) -> Panel | None:
    """Fail closed on absent, corrupt, external or unsupported assets; prose remains usable."""
    try:
        library = AssetLibrary(vault_root)
        record = library.record(reference)
        suffix = Path(record['path']).suffix.lower()
        if suffix not in {'.svg', '.png', '.jpg', '.jpeg'}:
            return None
        data = library.read(reference)
        if len(data) > 5_000_000:
            return None
        if suffix == '.svg':
            from cairosvg.surface import PNGSurface
            from defusedxml.ElementTree import fromstring

            root = fromstring(data)
            viewbox = root.get('viewBox', '').split()
            if len(viewbox) == 4:
                width, height = map(float, viewbox[2:])
            else:
                width, height = [float(re.match(r'[\d.eE+-]+', root.get(key, '0'))[0])
                                 for key in ('width', 'height')]
            if not all(math.isfinite(n) and n > 0 for n in (width, height)):
                return None
            scale = min(480 / width, 320 / height)

            def no_external_resource(url, resource_type):
                raise ValueError('A lesson preview cannot fetch external resources.')

            data = PNGSurface.convert(bytestring=data, output_width=max(1, round(width * scale)),
                                      output_height=max(1, round(height * scale)),
                                      unsafe=False, url_fetcher=no_external_resource)
        with Image.open(BytesIO(data)) as source:
            if source.width * source.height > 8_000_000:
                return None
            source.load()
            image = Image.new('RGB', source.size, 'white')
            rgba = source.convert('RGBA')
            image.paste(rgba, mask=rgba.getchannel('A'))
        return Panel(FigurePixels(image), title='Diagram preview',
                     subtitle='Full size in Obsidian · ctrl+o', padding=0)
    except Exception:  # A failed optional renderer must never break the lesson or open a fallback path.
        return None
