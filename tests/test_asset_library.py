"""Catalog resolution uses isolated vaults and never the learner's Library."""
import hashlib
import json

import pytest

from tutorlib.asset_library import AssetLibrary


@pytest.fixture
def library(tmp_path):
    vault = tmp_path / "STEM Tutor"
    target = vault / "Library/Courses/example/Diagrams/curve.svg"
    target.parent.mkdir(parents=True)
    target.write_bytes(b"<svg>original</svg>")
    catalog = {"format_version": 1, "assets": {"example-curve": {
        "path": target.relative_to(vault).as_posix(),
        "sha256": hashlib.sha256(target.read_bytes()).hexdigest(),
        "aliases": ["Assets/example/old-curve.svg"],
        "course": "example", "kind": "diagram", "provenance": {"source": "test"},
    }}}
    (vault / "Library/catalog.json").write_text(json.dumps(catalog))
    return vault, target, catalog


def save_catalog(vault, catalog):
    (vault / "Library/catalog.json").write_text(json.dumps(catalog))


def test_stable_reference_alias_and_canonical_path_resolve_same_asset(library):
    vault, target, _ = library
    reader = AssetLibrary(vault)
    for reference in ("asset:example-curve", "Assets/example/old-curve.svg",
                      "Library/Courses/example/Diagrams/curve.svg"):
        assert reader.resolve(reference) == target
        assert reader.read(reference) == b"<svg>original</svg>"


def test_undeclared_file_never_resolves_even_inside_library(library):
    vault, target, _ = library
    target.with_name("unlisted.svg").write_bytes(b"unlisted")
    with pytest.raises(ValueError, match="unknown"):
        AssetLibrary(vault).read("Library/Courses/example/Diagrams/unlisted.svg")


def test_alias_reads_canonical_file_not_legacy_file(library):
    vault, _, _ = library
    old = vault / "Assets/example/old-curve.svg"
    old.parent.mkdir(parents=True)
    old.write_bytes(b"stale legacy content")
    assert AssetLibrary(vault).read("Assets/example/old-curve.svg") == b"<svg>original</svg>"


def test_modified_asset_is_rejected(library):
    vault, target, _ = library
    reader = AssetLibrary(vault)
    target.write_bytes(b"changed")
    with pytest.raises(ValueError, match="digest mismatch"):
        reader.resolve("asset:example-curve")


@pytest.mark.parametrize("unsafe", ["Assets/q.svg", "Library/../outside.svg", "/tmp/q.svg",
                                    "Library//q.svg", "Library/./q.svg", "Library\\q.svg"])
def test_catalog_rejects_unsafe_or_nonlibrary_asset_paths(library, unsafe):
    vault, _, catalog = library
    catalog["assets"]["example-curve"]["path"] = unsafe
    save_catalog(vault, catalog)
    with pytest.raises(ValueError):
        AssetLibrary(vault)


def test_colliding_alias_is_rejected(library):
    vault, _, catalog = library
    catalog["assets"]["other"] = dict(catalog["assets"]["example-curve"])
    save_catalog(vault, catalog)
    with pytest.raises(ValueError, match="ambiguous"):
        AssetLibrary(vault)


def test_asset_symlink_outside_library_is_rejected(library, tmp_path):
    vault, target, _ = library
    outside = tmp_path / "outside.svg"
    outside.write_bytes(target.read_bytes())
    target.unlink()
    target.symlink_to(outside)
    with pytest.raises(ValueError, match="unsafe"):
        AssetLibrary(vault).read("asset:example-curve")


def test_catalog_symlink_is_rejected(library, tmp_path):
    vault, _, _ = library
    catalog = vault / "Library/catalog.json"
    outside = tmp_path / "catalog.json"
    outside.write_bytes(catalog.read_bytes())
    catalog.unlink()
    catalog.symlink_to(outside)
    with pytest.raises(ValueError, match="unsafe"):
        AssetLibrary(vault)


def test_symlink_directory_is_rejected_even_when_file_digest_matches(library):
    vault, target, _ = library
    directory = target.parent
    renamed = directory.with_name("RealDiagrams")
    directory.rename(renamed)
    directory.symlink_to(renamed, target_is_directory=True)
    with pytest.raises(ValueError, match="unsafe"):
        AssetLibrary(vault).read("asset:example-curve")


@pytest.mark.parametrize("version", [True, 2, "1"])
def test_unknown_or_invalid_catalog_version_rejected(library, version):
    vault, _, catalog = library
    catalog["format_version"] = version
    save_catalog(vault, catalog)
    with pytest.raises(ValueError, match="format"):
        AssetLibrary(vault)


def test_registration_preserves_all_catalog_metadata_and_merges_aliases(library):
    from tutorlib.asset_library import register_asset
    vault, _, catalog = library
    catalog['publisher'] = {'version': 'retained'}
    catalog['assets']['example-curve']['custom'] = {'review': 'pending'}
    save_catalog(vault, catalog)
    reference = register_asset(vault, 'Library/Courses/example/Diagrams/curve.svg',
                               aliases=['Assets/new.svg'], metadata={'extra': {'source': 'local'}})
    assert reference == 'asset:example-curve'
    saved = json.loads((vault / 'Library/catalog.json').read_text())
    assert saved['publisher'] == catalog['publisher']
    assert saved['assets']['example-curve']['custom'] == {'review': 'pending'}
    assert saved['assets']['example-curve']['extra'] == {'source': 'local'}
    assert AssetLibrary(vault).read('Assets/new.svg') == b'<svg>original</svg>'


def test_registration_rejects_changed_content_or_owned_alias_without_catalog_change(library):
    from tutorlib.asset_library import register_asset, write_asset
    vault, target, _ = library
    before = (vault / 'Library/catalog.json').read_bytes()
    with pytest.raises(ValueError, match='ambiguous'):
        write_asset(vault, 'Library/Shared/other.svg', b'other', aliases=['Assets/example/old-curve.svg'])
    assert (vault / 'Library/catalog.json').read_bytes() == before
    target.write_bytes(b'changed')
    with pytest.raises(ValueError, match='conflicts'):
        register_asset(vault, 'Library/Courses/example/Diagrams/curve.svg')
    assert (vault / 'Library/catalog.json').read_bytes() == before


def test_concurrent_registration_keeps_both_writers(library):
    from concurrent.futures import ThreadPoolExecutor
    from tutorlib.asset_library import write_asset
    vault, _, _ = library
    with ThreadPoolExecutor(max_workers=2) as workers:
        references = list(workers.map(lambda name: write_asset(vault, 'Library/Shared/' + name,
                                                              name.encode()), ['one.svg', 'two.svg']))
    reader = AssetLibrary(vault)
    assert [reader.read(reference) for reference in references] == [b'one.svg', b'two.svg']
    assert len(reader.records()) == 3


def test_write_asset_rejects_symlink_ancestor_without_outside_write(library, tmp_path):
    from tutorlib.asset_library import write_asset
    vault, _, _ = library
    outside = tmp_path / 'outside'
    outside.mkdir()
    (vault / 'Library/Shared').symlink_to(outside, target_is_directory=True)
    with pytest.raises(ValueError):
        write_asset(vault, 'Library/Shared/new.svg', b'never outside')
    assert list(outside.iterdir()) == []


def test_metadata_reads_cannot_change_loaded_catalog(library):
    vault, _, _ = library
    reader = AssetLibrary(vault)
    record = reader.record('asset:example-curve')
    record['aliases'].append('fake')
    records = reader.records()
    records['example-curve']['path'] = 'Library/fake'
    assert reader.record('asset:example-curve')['path'].endswith('curve.svg')
    with pytest.raises(ValueError, match='unknown'):
        reader.read('fake')


def test_default_crop_publishes_catalogued_figure_and_source_sidecar(tmp_path, monkeypatch, capsys):
    import sys
    from pathlib import Path
    from types import SimpleNamespace
    from PIL import Image
    sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'build'))
    import library as producer
    vault = tmp_path / 'STEM Tutor'
    pdf = vault / 'Library/Courses/example/Sources/Library/book.pdf'
    pdf.parent.mkdir(parents=True)
    pdf.write_bytes(b'PDF source fixture')
    monkeypatch.setenv('STEM_TUTOR_VAULT', str(vault))
    monkeypatch.delenv('STEM_LIBRARY_ASSETS', raising=False)
    monkeypatch.delenv('STEM_LIBRARY_ROOT', raising=False)
    assert producer.lib_root() == vault / 'Library'
    assert producer.roots('library') == {'library:example': pdf.parent}
    spec, name, dest = producer._target('example/new-figure')
    assert dest == vault / 'Library/Courses/example/Diagrams/new-figure.png'
    args = SimpleNamespace(page=1, caption='Original figure', subtopic='example-1', kc='example-1.1', why='teaching')
    producer._publish_figure(args, pdf, spec, name, dest, Image.new('RGB', (300, 300), 'white'),
                             {'box': [0, 0, 1, 1], 'dpi': 200})
    relative = dest.relative_to(vault).as_posix()
    reader = AssetLibrary(vault)
    assert reader.read(relative).startswith(b'\x89PNG')
    side = json.loads(reader.read(reader.record(relative)['provenance']['sidecars'][0]))
    assert side['pdf'] == pdf.relative_to(vault).as_posix()
    assert side['subtopic'] == 'example-1'
    assert f'![[{relative}]]' in capsys.readouterr().out
    note = f'![[{relative}]]\n*Figure: Original figure (source: book, p.1)*\n'
    assert producer.figure_problems(note, 'example-1') == []
    assert producer.sidecars_for('example-1')[0]['file'] == str(dest)


def test_path_resolution_normalizes_case_and_unicode_forms(library):
    vault, _, catalog = library
    catalog['assets']['example-curve']['aliases'].append('Assets/Café.svg')
    save_catalog(vault, catalog)
    reader = AssetLibrary(vault)
    assert reader.read('assets/example/OLD-CURVE.SVG') == b'<svg>original</svg>'
    assert reader.read('ASSETS/Cafe\u0301.svg') == b'<svg>original</svg>'


@pytest.mark.parametrize('field', ['path', 'aliases'])
def test_catalog_rejects_normalized_paths_owned_by_different_assets(library, field):
    from tutorlib.asset_library import validate_catalog
    vault, _, catalog = library
    first = catalog['assets']['example-curve']
    second = {'path': 'Library/Shared/other.svg', 'sha256': first['sha256'], 'aliases': []}
    if field == 'path':
        second['path'] = first['path'].upper().replace('LIBRARY/', 'Library/')
    else:
        first['aliases'].append('Assets/Café.svg')
        second['aliases'] = ['ASSETS/Cafe\u0301.svg']
    catalog['assets']['other'] = second
    save_catalog(vault, catalog)
    with pytest.raises(ValueError, match='ambiguous'):
        validate_catalog(catalog)
    with pytest.raises(ValueError, match='ambiguous'):
        AssetLibrary(vault)


def test_registration_rejects_normalized_alias_collision_without_catalog_change(library):
    from tutorlib.asset_library import write_asset
    vault, _, _ = library
    before = (vault / 'Library/catalog.json').read_bytes()
    with pytest.raises(ValueError, match='ambiguous'):
        write_asset(vault, 'Library/Shared/new.svg', b'new', aliases=['assets/EXAMPLE/old-CURVE.svg'])
    assert (vault / 'Library/catalog.json').read_bytes() == before
