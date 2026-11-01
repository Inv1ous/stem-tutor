"""Bugwatch snapshots the actual release and its Library dependencies."""
import hashlib
import json
from pathlib import Path
import sys

import pytest

from library_assets import read_bytes

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'bugwatch'))
import sandbox
from tutorlib.asset_library import AssetLibrary, write_asset


def test_scratch_copy_keeps_registered_plan_exact_and_copies_legacy_media(tmp_path):
    source, target = tmp_path / 'source', tmp_path / 'scratch'
    source.mkdir()
    plan = b'{"source_path":"/outside/planner.html","source_sha256":"abc"}'
    files = {'manifest.json': b'{"specs":["9702"]}', 'plan.json': plan,
             'specs/9702/graph.json': b'{"kcs":[]}',
             'specs/9702/packs/9702-2.1.json': b'{"image":"Assets/mcq/question.png"}'}
    for name, data in files.items():
        write_asset(source, 'Library/Releases/v265/' + name, data)
    media = 'Library/Courses/9702/Questions/Media/question.png'
    write_asset(source, media, b'question', aliases=['Assets/mcq/question.png'])
    review = 'Library/Courses/9702/Questions/Reviews/equivalence.json'
    write_asset(source, review, b'{"format_version":1,"reviews":[]}',
                metadata={'course': '9702', 'kind': 'question_duplicate_review'})
    pointer = source / '.tutor/packs/CURRENT'
    pointer.parent.mkdir(parents=True); pointer.write_text('v265')
    original = {p.relative_to(source): p.read_bytes() for p in source.rglob('*') if p.is_file()}
    result = sandbox.copy_current(source, target)
    assert result['version'] == 'v265'
    reader = AssetLibrary(target)
    assert reader.read('Assets/mcq/question.png') == b'question'
    assert reader.read('Library/Releases/v265/plan.json') == plan
    assert reader.read(review) == b'{"format_version":1,"reviews":[]}'
    assert (target / '.tutor/packs/CURRENT').read_text() == 'v265'
    assert not any(p.is_symlink() for p in target.rglob('*'))
    assert all((source / rel).read_bytes() == data for rel, data in original.items())
    (target / media).write_bytes(b'scratch change')
    assert AssetLibrary(source).read(media) == b'question'


def test_corrupt_source_dependency_is_not_copied_as_valid(tmp_path):
    import pytest
    source, target = tmp_path / 'source', tmp_path / 'scratch'
    source.mkdir()
    reference = 'Library/Releases/v1/manifest.json'
    write_asset(source, reference, b'{}')
    pointer=source/'.tutor/packs/CURRENT'; pointer.parent.mkdir(parents=True); pointer.write_text('v1')
    (source / reference).write_bytes(b'changed')
    with pytest.raises(ValueError, match='digest mismatch'):
        sandbox.copy_current(source, target)


@pytest.mark.parametrize('spelling', ['Assets', 'assets'])
@pytest.mark.parametrize('format', ['json', 'md'])
def test_snapshot_follows_runtime_repository_adapter_without_changing_source(tmp_path, spelling, format):
    source, target = tmp_path / 'source', tmp_path / 'scratch'
    source.mkdir()
    name = 'M1/m1-3-notes-suvat-derivation.png'
    canonical = 'Library/Courses/M1/Diagrams/' + name
    alias = f'build/out/{spelling}/{name}'
    reference = 'stem-tutor/' + alias
    write_asset(source, canonical, read_bytes(canonical), aliases=[alias])
    if format == 'json':
        data = json.dumps({'teach': {'M1-3.1': {'diagram_provenance': [
            {'source': [reference]}]}}}).encode()
    else:
        data = f'![source-derived diagram]({reference})\n'.encode()
    release_file = 'Library/Releases/v1/content.' + format
    write_asset(source, release_file, data)
    pointer = source / '.tutor/packs/CURRENT'
    pointer.parent.mkdir(parents=True)
    pointer.write_text('v1')
    before = {path.relative_to(source): path.read_bytes()
              for path in source.rglob('*') if path.is_file()}

    result = sandbox.copy_current(source, target)

    library = AssetLibrary(target)
    assert result['version'] == 'v1'
    assert library.read(alias) == read_bytes(canonical)
    assert library.read(release_file) == data
    assert {path.relative_to(source): path.read_bytes()
            for path in source.rglob('*') if path.is_file()} == before
    assert not any(path.is_symlink() for path in target.rglob('*'))
    assert (source / canonical).stat().st_ino != (target / canonical).stat().st_ino


@pytest.mark.parametrize('corrupt', [False, True])
def test_snapshot_adapter_requires_declared_alias_and_verified_bytes(tmp_path, corrupt):
    source, target = tmp_path / 'source', tmp_path / 'scratch'
    source.mkdir()
    canonical = 'Library/Courses/M1/Diagrams/M1/m1-3-notes-suvat-derivation.png'
    alias = 'build/out/Assets/M1/m1-3-notes-suvat-derivation.png'
    write_asset(source, canonical, read_bytes(canonical), aliases=[alias] if corrupt else [])
    if corrupt:
        (source / canonical).write_bytes(b'corrupt disposable media')
    write_asset(source, 'Library/Releases/v1/pack.json',
                json.dumps({'image': 'stem-tutor/' + alias}).encode())
    pointer = source / '.tutor/packs/CURRENT'
    pointer.parent.mkdir(parents=True)
    pointer.write_text('v1')
    with pytest.raises(ValueError, match='digest mismatch' if corrupt else 'unknown asset reference'):
        sandbox.copy_current(source, target)


@pytest.mark.parametrize('provenance', [
    'STEM Tutor/Assets/M1/M1-3-at-area.svg',
    'Registered Library asset; origin old figure.svg',
    'Read the registered gradient diagram.svg',
    'Library/Courses/9701/chapter.pdf pp. 7–8',
    'Library/Courses/9701/chapter.pdf, PDF p.311; syllabus.pdf',
    'https://example.invalid/syllabus.pdf',
])
def test_snapshot_preserves_runtime_nonasset_source_provenance(tmp_path, provenance):
    source, target = tmp_path / 'source', tmp_path / 'scratch'
    source.mkdir()
    relative = 'Library/Releases/v1/pack.json'
    data = json.dumps({'teach': {'diagram_provenance': [{'source': provenance}]}}).encode()
    write_asset(source, relative, data)
    pointer = source / '.tutor/packs/CURRENT'
    pointer.parent.mkdir(parents=True)
    pointer.write_text('v1')

    assert sandbox.copy_current(source, target)['assets'] == 1
    assert AssetLibrary(target).read(relative) == data
    assert AssetLibrary(source).read(relative) == data


def test_snapshot_still_copies_explicit_registered_historical_source_alias(tmp_path):
    source, target = tmp_path / 'source', tmp_path / 'scratch'
    source.mkdir()
    canonical = 'Library/Courses/M1/Diagrams/M1/M1-3-at-area.svg'
    reference = 'Historical Figures/area.svg'
    write_asset(source, canonical, read_bytes(canonical), aliases=['sources/library/' + reference])
    write_asset(source, 'Library/Releases/v1/pack.json', json.dumps({'source': reference}).encode())
    pointer = source / '.tutor/packs/CURRENT'
    pointer.parent.mkdir(parents=True)
    pointer.write_text('v1')

    assert sandbox.copy_current(source, target)['assets'] == 2
    assert AssetLibrary(target).read('sources/library/' + reference) == read_bytes(canonical)


def test_snapshot_does_not_treat_a_missing_real_asset_as_citation(tmp_path):
    source = tmp_path / 'source'
    source.mkdir()
    write_asset(source, 'Library/Releases/v1/pack.json',
                b'{"source":"Assets/missing figure.svg"}')
    pointer = source / '.tutor/packs/CURRENT'
    pointer.parent.mkdir(parents=True)
    pointer.write_text('v1')
    with pytest.raises(ValueError, match='unknown asset reference'):
        sandbox.copy_current(source, tmp_path / 'scratch')


@pytest.mark.parametrize('binding', ['review', 'sidecar'])
def test_source_citation_rule_cannot_waive_missing_review_dependencies(tmp_path, binding):
    source = tmp_path / 'source'
    source.mkdir()
    metadata = {'provenance': {'sidecars': ['missing-review.json']}} if binding == 'sidecar' else {}
    data = b'{"review":"Missing review.pdf"}' if binding == 'review' else b'{}'
    write_asset(source, 'Library/Releases/v1/pack.json', data, metadata=metadata)
    pointer = source / '.tutor/packs/CURRENT'
    pointer.parent.mkdir(parents=True)
    pointer.write_text('v1')
    with pytest.raises(ValueError, match='unknown asset reference'):
        sandbox.copy_current(source, tmp_path / 'scratch')
