import importlib.util
from pathlib import Path

from tutor_workers.media_checks import svg_problem


SVG = 'http://www.w3.org/2000/svg'
ROOT = Path(__file__).resolve().parents[1]


def svg(body, *, width='80', height='40', viewbox='0 0 80 40'):
    return (f'<svg xmlns="{SVG}" width="{width}" height="{height}" viewBox="{viewbox}">{body}</svg>'
            .encode())


def test_visible_multicolour_svg_is_accepted():
    data = svg('<rect x="5" y="5" width="25" height="25" fill="red"/>'
               '<circle cx="60" cy="20" r="12" fill="green"/>')
    assert svg_problem(data) is None


def test_blank_svg_that_passed_xml_only_check_is_rejected():
    # This valid, empty SVG previously passed XML/root validation despite teaching nothing.
    assert svg_problem(svg('')) == 'SVG renders as a uniform or transparent image'


def test_external_svg_dependency_is_rejected_before_rendering(monkeypatch):
    import cairosvg
    import pytest
    monkeypatch.setattr(cairosvg, 'svg2png', lambda **kw: pytest.fail('must not fetch loose resources'))
    for content in ('<image href="file:///missing.png"/>', '<style>text {src:url(https://invalid/font)}</style>'):
        assert svg_problem(svg(content)) == 'SVG references an external resource'


def test_missing_or_invalid_viewport_is_rejected():
    assert 'viewport' in svg_problem(f'<svg xmlns="{SVG}"><rect width="20" height="20"/></svg>'.encode())
    assert 'viewport' in svg_problem(svg('<rect width="20" height="20"/>', viewbox='0 0 -1 40'))
    assert 'viewport' in svg_problem(svg('<rect width="20" height="20"/>', width='invalid'))


def test_invalid_xml_and_non_svg_root_are_rejected():
    assert 'XML' in svg_problem(b'<svg')
    assert 'root' in svg_problem(b'<root/>')


def test_render_failure_and_too_small_svgs_are_rejected(monkeypatch):
    import cairosvg

    monkeypatch.setattr(cairosvg, 'svg2png', lambda **kwargs: (_ for _ in ()).throw(RuntimeError('render failed')))
    assert 'cannot be rendered' in svg_problem(svg('<rect width="20" height="20" fill="red"/>'))
    small = svg('<rect width="10" height="10" fill="red"/>', width='10', height='10', viewbox='0 0 10 10')
    assert 'smaller than 16 px' in svg_problem(small)


def test_fully_transparent_svg_is_rejected_after_white_compositing():
    transparent = svg('<rect width="80" height="40" fill="red" opacity="0"/>')
    assert 'uniform or transparent' in svg_problem(transparent)


def test_large_viewport_is_rendered_with_a_bounded_output(monkeypatch):
    import cairosvg

    render = cairosvg.svg2png
    sizes = []

    def bounded_render(**kwargs):
        sizes.append((kwargs['output_width'], kwargs['output_height']))
        return render(**kwargs)

    monkeypatch.setattr(cairosvg, 'svg2png', bounded_render)
    large = svg('<rect width="10000" height="20000" fill="red"/>'
                '<rect x="10000" width="10000" height="20000" fill="blue"/>',
                width='20000', height='20000', viewbox='0 0 20000 20000')
    assert svg_problem(large) is None
    assert sizes and max(sizes[0]) <= 1024


def test_extraction_media_gate_rejects_blank_and_accepts_visible_svg(tmp_path, monkeypatch):
    monkeypatch.syspath_prepend(str(ROOT / 'build'))
    spec = importlib.util.spec_from_file_location('extraction_media_check', ROOT / 'extraction/extract.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    blank = svg('')
    (tmp_path / 'media.svg').write_bytes(blank)
    state = {'candidate': str(tmp_path / 'candidate.json')}
    errors, hashes = module._media(state, {'media': ['media.svg']})
    assert errors == ['candidate media cannot be decoded'] and hashes == []

    (tmp_path / 'media.svg').write_bytes(svg('<rect x="5" y="5" width="25" height="25" fill="red"/>'))
    errors, hashes = module._media(state, {'media': ['media.svg']})
    assert errors == [] and len(hashes) == 1
def test_superseded_diagram_cannot_satisfy_teaching_display(tmp_path):
    import pytest
    from tutorlib.asset_library import AssetLibrary, write_asset
    from test_guided_teach_cards import _foundry
    vault = tmp_path / 'vault'
    vault.mkdir()
    reference = 'Library/Courses/P1/Diagrams/retired.svg'
    write_asset(vault, reference, b'<svg/>', metadata={'kind': 'Diagrams',
        'origins': ['synthetic'], 'teaching_status': 'superseded',
        'superseded_by': 'Library/Courses/P1/Diagrams/reviewed.svg'})
    with pytest.raises(ValueError, match='retired from teaching reuse'):
        _foundry()._verified_display_diagram(AssetLibrary(vault), reference)

