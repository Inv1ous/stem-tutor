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


def count_index_builds(monkeypatch):
    """Observe real validation work without replacing its behavior."""
    import tutorlib.asset_library as assets
    calls = []
    original = assets._index
    def build(catalog):
        calls.append(catalog)
        return original(catalog)
    monkeypatch.setattr(assets, '_index', build)
    return calls


def test_catalog_index_reuses_identical_bytes_with_independent_metadata(library, monkeypatch):
    vault, _, catalog = library
    catalog['case'] = 'index-metadata-isolation'
    save_catalog(vault, catalog)
    calls = count_index_builds(monkeypatch)
    first, second = AssetLibrary(vault), AssetLibrary(vault)
    assert len(calls) == 1
    assert first._catalog is not second._catalog
    first._catalog['assets']['example-curve']['provenance']['source'] = 'instance-local'
    metadata = second.record('asset:example-curve')
    metadata['aliases'].append('Assets/fake.svg')
    metadata['provenance']['source'] = 'client-local'
    all_records = second.records()
    all_records['example-curve']['provenance']['source'] = 'other-client'
    third = AssetLibrary(vault)
    assert third.record('asset:example-curve')['provenance'] == {'source': 'test'}
    assert second.record('asset:example-curve')['provenance'] == {'source': 'test'}
    assert third.read('Assets/example/old-curve.svg') == b'<svg>original</svg>'
    with pytest.raises(ValueError, match='unknown'):
        third.read('Assets/fake.svg')
    assert len(calls) == 1


def test_catalog_index_keys_exact_raw_bytes_not_equivalent_json(library, monkeypatch):
    vault, _, catalog = library
    catalog['case'] = 'exact-raw-catalog-key'
    save_catalog(vault, catalog)
    path = vault / 'Library/catalog.json'
    raw = path.read_bytes()
    calls = count_index_builds(monkeypatch)
    AssetLibrary(vault); AssetLibrary(vault)
    assert len(calls) == 1
    path.write_bytes(b'\n' + raw)
    assert AssetLibrary(vault).read('asset:example-curve') == b'<svg>original</svg>'
    assert len(calls) == 2
    path.write_bytes(raw)
    assert AssetLibrary(vault).read('asset:example-curve') == b'<svg>original</svg>'
    assert len(calls) == 2


def test_catalog_index_refreshes_aliases_despite_same_size_and_mtime(library):
    import os
    vault, _, catalog = library
    catalog['case'] = 'same-stat-alias-drift'
    save_catalog(vault, catalog)
    path = vault / 'Library/catalog.json'
    before = path.stat()
    previous = AssetLibrary(vault)
    catalog['assets']['example-curve']['aliases'] = ['Assets/example/new-curve.svg']
    save_catalog(vault, catalog)
    assert path.stat().st_size == before.st_size
    os.utime(path, ns=(before.st_atime_ns, before.st_mtime_ns))
    current = AssetLibrary(vault)
    assert current.read('Assets/example/new-curve.svg') == b'<svg>original</svg>'
    with pytest.raises(ValueError, match='unknown'):
        current.read('Assets/example/old-curve.svg')
    assert previous.read('Assets/example/old-curve.svg') == b'<svg>original</svg>'


@pytest.mark.parametrize('damage', ['json', 'schema', 'alias-collision', 'alias-type'])
def test_catalog_index_never_trusts_a_warmed_path_with_changed_invalid_bytes(library, damage):
    import copy
    vault, _, catalog = library
    catalog['case'] = 'changed-invalid-' + damage
    save_catalog(vault, catalog)
    AssetLibrary(vault); AssetLibrary(vault)
    if damage == 'json':
        (vault / 'Library/catalog.json').write_bytes(b'{malformed')
    else:
        changed = copy.deepcopy(catalog)
        if damage == 'schema':
            changed['format_version'] = True
        elif damage == 'alias-collision':
            changed['assets']['other'] = {'path': 'Library/Shared/other.svg',
                'sha256': catalog['assets']['example-curve']['sha256'],
                'aliases': ['ASSETS/EXAMPLE/old-CURVE.svg']}
        else:
            changed['assets']['example-curve']['aliases'] = 'Assets/invalid.svg'
        save_catalog(vault, changed)
    with pytest.raises(ValueError):
        AssetLibrary(vault)


def test_catalog_index_can_cross_roots_but_never_share_trusted_payloads_or_mutable_maps(library, tmp_path, monkeypatch):
    vault, target, catalog = library
    catalog['case'] = 'cross-root-index-only'
    save_catalog(vault, catalog)
    other = tmp_path / 'other-vault'
    relative = target.relative_to(vault)
    other_target = other / relative
    other_target.parent.mkdir(parents=True)
    other_target.write_bytes(target.read_bytes())
    (other / 'Library/catalog.json').write_bytes((vault / 'Library/catalog.json').read_bytes())
    calls = count_index_builds(monkeypatch)
    first, second = AssetLibrary(vault), AssetLibrary(other)
    assert first.read('asset:example-curve') == second.read('asset:example-curve') == b'<svg>original</svg>'
    assert len(calls) == 1
    # A reader's private dictionaries must not poison another reader or the cache.
    for index in (first._assets, first._references):
        try:
            index.clear()
        except (AttributeError, TypeError):
            pass  # immutable shared indexes are also safe
    assert second.read('asset:example-curve') == b'<svg>original</svg>'
    assert AssetLibrary(vault).read('asset:example-curve') == b'<svg>original</svg>'
    other_target.write_bytes(b'changed payload; catalog untouched')
    with pytest.raises(ValueError, match='digest mismatch'):
        second.read('asset:example-curve')
    with pytest.raises(ValueError, match='digest mismatch'):
        AssetLibrary(other).resolve('asset:example-curve')
    assert AssetLibrary(vault).read('asset:example-curve') == b'<svg>original</svg>'
    assert len(calls) == 1


def test_catalog_index_reuse_is_bounded_and_evicted_bytes_are_revalidated(library, monkeypatch):
    vault, _, catalog = library
    calls = count_index_builds(monkeypatch)
    for version in range(5):
        catalog['case'] = ['bounded-index-working-set', version]
        save_catalog(vault, catalog)
        assert AssetLibrary(vault).read('asset:example-curve') == b'<svg>original</svg>'
    for version in range(1, 5):
        catalog['case'] = ['bounded-index-working-set', version]
        save_catalog(vault, catalog)
        AssetLibrary(vault)
    assert len(calls) == 5
    catalog['case'] = ['bounded-index-working-set', 0]
    save_catalog(vault, catalog)
    assert AssetLibrary(vault).read('asset:example-curve') == b'<svg>original</svg>'
    assert len(calls) == 6


def test_identical_catalog_readers_decode_full_metadata_once_until_requested(library, monkeypatch):
    """Repeated image/proof readers must not decode the full catalog per record."""
    from tutorlib import asset_library as assets
    vault, _, catalog = library
    catalog['case'] = 'lazy-full-metadata-and-immutable-record-cache'
    save_catalog(vault, catalog)
    raw = (vault / 'Library/catalog.json').read_bytes()
    full_decodes = []
    original = assets.json.loads

    def counted(data, *args, **kwargs):
        if data == raw:
            full_decodes.append(True)
        return original(data, *args, **kwargs)

    monkeypatch.setattr(assets.json, 'loads', counted)
    first, second = AssetLibrary(vault), AssetLibrary(vault)
    one = first.record('asset:example-curve')
    one['provenance']['source'] = 'returned-client-copy'
    assert second.record('Assets/example/old-curve.svg')['provenance'] == {'source': 'test'}
    assert first.read('asset:example-curve') == b'<svg>original</svg>'
    assert len(full_decodes) == 1

    # Explicit private-catalog access keeps its historical instance-local view.
    second._catalog['assets']['example-curve']['provenance']['source'] = 'instance-local'
    assert len(full_decodes) == 2
    assert second.record('asset:example-curve')['provenance'] == {'source': 'instance-local'}
    assert first.record('asset:example-curve')['provenance'] == {'source': 'test'}
    all_records = second.records()
    all_records['example-curve']['provenance']['source'] = 'returned-records-copy'
    assert second.record('asset:example-curve')['provenance'] == {'source': 'instance-local'}
    assert len(full_decodes) == 2
