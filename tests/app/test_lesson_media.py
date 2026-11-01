"""Preview source pixels only after an integrity-checked, local Library read."""
from tutorlib.asset_library import write_asset
from tutor_app.lesson_media import figure_preview
from io import StringIO
from rich.console import Console


def test_preview_reads_library_alias_and_rejects_changed_bytes(tmp_path):
    data = b'<svg xmlns="http://www.w3.org/2000/svg" width="80" height="40"><rect width="80" height="40" fill="blue"/></svg>'
    write_asset(tmp_path, 'Library/Shared/Diagrams/test.svg', data, aliases=['Assets/test.svg'])
    preview = figure_preview(tmp_path, 'Assets/test.svg')
    assert preview is not None
    console = Console(file=StringIO(), record=True, color_system='truecolor')
    console.print(preview)
    assert '#0000ff' in console.export_html(inline_styles=True), 'Source pixel colours must reach the terminal.'
    (tmp_path / 'Library/Shared/Diagrams/test.svg').write_bytes(data.replace(b'blue', b'red'))
    assert figure_preview(tmp_path, 'Assets/test.svg') is None


def test_preview_cannot_fetch_external_svg_image(tmp_path):
    data = b'<svg xmlns="http://www.w3.org/2000/svg" width="80" height="40"><image href="https://example.invalid/private.png" width="80" height="40"/></svg>'
    write_asset(tmp_path, 'Library/Shared/Diagrams/external.svg', data)
    assert figure_preview(tmp_path, 'Library/Shared/Diagrams/external.svg') is None


def test_unavailable_preview_is_safe_to_skip(tmp_path):
    assert figure_preview(tmp_path, 'Library/Shared/Diagrams/missing.svg') is None
