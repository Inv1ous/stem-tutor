"""Expand-only Library migration, always in isolated temporary workspaces."""
import hashlib
import json
import os
from pathlib import Path
import sys

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'build'))
import migrate_library as migration
from tutorlib.asset_library import AssetLibrary


@pytest.fixture
def workspace(tmp_path):
    root = tmp_path / 'workspace'
    (root / 'STEM Tutor').mkdir(parents=True)
    (root / 'stem-tutor').mkdir()
    return root


def put(workspace, relative, data=b'original'):
    path = workspace / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)
    return path


def test_plan_is_readonly_and_apply_keeps_originals_with_distinct_versions(workspace):
    old = put(workspace, 'STEM Tutor/Assets/9702/diagram.svg', b'old')
    new = put(workspace, 'stem-tutor/build/out/assets/9702/diagram.svg', b'new')
    report = migration.plan(workspace)
    assert report['errors'] == []
    assert len(report['assets']) == 2
    assert not (workspace / 'STEM Tutor/Library').exists()
    result = migration.apply(report)
    reader = AssetLibrary(workspace / 'STEM Tutor')
    assert reader.read('Assets/9702/diagram.svg') == b'old'
    assert reader.read('build/out/assets/9702/diagram.svg') == b'new'
    assert old.read_bytes() == b'old' and new.read_bytes() == b'new'
    assert result['sources_deleted'] == 0
    assert migration.apply(migration.plan(workspace))['copied'] == 0


def test_hardlinked_sources_keep_both_aliases(workspace):
    old = put(workspace, 'STEM Tutor/Assets/P1/d.svg')
    new = workspace / 'stem-tutor/build/out/assets/P1/d.svg'
    new.parent.mkdir(parents=True)
    os.link(old, new)
    report = migration.plan(workspace)
    assert report['errors'] == []
    assert len(report['assets']) == 1
    aliases = set(next(iter(report['assets'].values()))['aliases'])
    assert {'Assets/P1/d.svg', 'build/out/assets/P1/d.svg'} <= aliases
    assert len(aliases) in (2, 3)  # both spellings on case-insensitive volumes


def test_repeated_identical_collision_variant_merges(workspace):
    put(workspace, 'STEM Tutor/Assets/P1/d.svg', b'old')
    put(workspace, 'stem-tutor/build/out/assets/P1/d.svg', b'new')
    upper = workspace / 'stem-tutor/build/out/Assets'
    lower = workspace / 'stem-tutor/build/out/assets'
    if upper.exists():
        # Case-insensitive filesystems expose one tree under both aliases.
        report = migration.plan(workspace)
        variants = [entry for entry in report['assets'].values() if entry['sha256'] == hashlib.sha256(b'new').hexdigest()]
        assert report['errors'] == [] and len(variants) == 1
        assert set(variants[0]['aliases']) == {'build/out/assets/P1/d.svg', 'build/out/Assets/P1/d.svg'}
    else:
        put(workspace, 'stem-tutor/build/out/Assets/P1/d.svg', b'new')
        report = migration.plan(workspace)
        assert report['errors'] == [] and len(report['assets']) == 2


def test_raw_docx_notes_question_json_topicals_and_provenance_included(workspace):
    put(workspace, 'stem-tutor/sources/library/Physics 9702 AS Topicals/original.docx')
    put(workspace, 'stem-tutor/build/out/notes/Subjects/P1/topic.md')
    put(workspace, 'stem-tutor/build/out/packs/P1/P1-1.json', b'{}')
    put(workspace, 'stem-tutor/build/out/topicals/batch/Assets/topicals/9702_q.png')
    put(workspace, 'stem-tutor/build/out/assets/P1/figure.svg')
    put(workspace, 'stem-tutor/build/out/assets/P1/figure.svg.json', b'{"source":"original"}')
    put(workspace, 'stem-tutor/build/work/random.json', b'{}')
    report = migration.plan(workspace)
    assert report['errors'] == []
    aliases = {alias for entry in report['assets'].values() for alias in entry['aliases']}
    assert 'sources/library/Physics 9702 AS Topicals/original.docx' in aliases
    assert 'build/out/notes/Subjects/P1/topic.md' in aliases
    assert 'build/out/packs/P1/P1-1.json' in aliases
    assert 'build/out/topicals/batch/Assets/topicals/9702_q.png' in aliases
    assert 'build/work/random.json' not in aliases
    figure = next(entry for entry in report['assets'].values() if 'build/out/assets/P1/figure.svg' in entry['aliases'])
    assert figure['provenance']['sidecars'][0].startswith('asset:')
    migration.apply(report)
    reader = AssetLibrary(workspace / 'STEM Tutor')
    assert reader.read(figure['provenance']['sidecars'][0]) == b'{"source":"original"}'


@pytest.mark.parametrize(('folder', 'course'), [('YMA01 pure-1', 'P1'), ('YMA01 statistics-2', 'S2'),
    ('YMA01 decision-1', 'D1'), ('XMA01 mechanics-1', 'M1'), ('YFM01 further-pure-1', 'FP1'),
    ('WMA12', 'P2'), ('YMA01 ambiguous', None)])
def test_course_classification_uses_folder_meaning_not_ambiguous_source_code(folder, course):
    assert migration._course('SaveMyExams/' + folder + '/chapter.pdf') == course


def test_source_symlink_is_reported_and_apply_refuses(workspace, tmp_path):
    outside = tmp_path / 'outside'
    outside.mkdir()
    (outside / 'secret.pdf').write_bytes(b'secret')
    source = workspace / 'stem-tutor/sources/library'
    source.parent.mkdir()
    source.symlink_to(outside, target_is_directory=True)
    report = migration.plan(workspace)
    assert report['errors']
    with pytest.raises(ValueError, match='unresolved'):
        migration.apply(report)
    assert not (workspace / 'STEM Tutor/Library').exists()


def test_destination_ancestor_symlink_rejected_before_copy(workspace, tmp_path):
    put(workspace, 'STEM Tutor/Assets/P1/a.svg')
    report = migration.plan(workspace)
    outside = tmp_path / 'outside'
    outside.mkdir()
    (workspace / 'STEM Tutor/Library').symlink_to(outside, target_is_directory=True)
    with pytest.raises(ValueError):
        migration.apply(report)
    assert list(outside.iterdir()) == []


def test_source_replaced_with_symlink_after_plan_rejected(workspace, tmp_path):
    source = put(workspace, 'STEM Tutor/Assets/P1/a.svg')
    report = migration.plan(workspace)
    outside = tmp_path / 'outside.svg'
    outside.write_bytes(b'original')
    source.unlink()
    source.symlink_to(outside)
    with pytest.raises(ValueError, match='unsafe'):
        migration.apply(report)
    assert not (workspace / 'STEM Tutor/Library').exists()


def test_complete_catalog_preflight_detects_alias_collision_before_any_copy(workspace):
    put(workspace, 'STEM Tutor/Assets/P1/a.svg')
    report = migration.plan(workspace)
    library = workspace / 'STEM Tutor/Library'
    library.mkdir()
    old = {'format_version': 1, 'assets': {'existing': {
        'path': 'Library/Shared/existing.svg', 'sha256': '0' * 64, 'aliases': ['Assets/P1/a.svg']}}}
    (library / 'catalog.json').write_text(json.dumps(old))
    with pytest.raises(ValueError, match='ambiguous'):
        migration.apply(report)
    assert sorted(path.name for path in library.iterdir()) == ['catalog.json']
    assert json.loads((library / 'catalog.json').read_text()) == old


def test_changed_source_detected_in_preflight_before_any_copy(workspace):
    first = put(workspace, 'STEM Tutor/Assets/P1/a.svg')
    put(workspace, 'STEM Tutor/Assets/P1/b.svg')
    report = migration.plan(workspace)
    first.write_bytes(b'changed')
    with pytest.raises(ValueError, match='source changed'):
        migration.apply(report)
    assert not (workspace / 'STEM Tutor/Library').exists()


def test_extra_repository_media_and_sidecars_are_catalogued_as_review_evidence(workspace):
    put(workspace, 'stem-tutor/.superpowers/review/shots/home.svg', b'home')
    put(workspace, 'stem-tutor/bugwatch/codex/shots/9702-output.png', b'output')
    put(workspace, 'stem-tutor/tests/fixtures/P1-example.svg', b'fixture')
    put(workspace, 'stem-tutor/docs/benchmarks/P1-preview.svg', b'preview')
    put(workspace, 'stem-tutor/docs/benchmarks/P1-preview.svg.json', b'{"source":"test"}')
    put(workspace, 'stem-tutor/tests/fixtures/arbitrary.json', b'{}')
    report = migration.plan(workspace)
    assert report['errors'] == []
    assert len(report['assets']) == 5
    for entry in report['assets'].values():
        assert entry['path'].startswith('Library/Shared/ReviewEvidence/')
        assert entry['course'] is None
    preview = next(e for e in report['assets'].values() if 'docs/benchmarks/P1-preview.svg' in e['aliases'])
    assert preview['provenance']['sidecars']
    migration.apply(report)
    reader = AssetLibrary(workspace / 'STEM Tutor')
    assert reader.read('tests/fixtures/P1-example.svg') == b'fixture'
    assert reader.read(preview['provenance']['sidecars'][0]) == b'{"source":"test"}'


def test_generic_media_scan_excludes_caches_dependencies_and_worktrees(workspace):
    for folder in ['.git', '.venv', 'node_modules', '__pycache__', '.cache',
                   '.claude/worktrees/agent', '.bugfix-wt/old']:
        put(workspace, 'stem-tutor/' + folder + '/skip.svg')
    assert migration.plan(workspace)['assets'] == {}


def test_generic_scan_is_additive_preserving_existing_ids_and_metadata(workspace):
    put(workspace, 'STEM Tutor/Assets/P1/a.svg', b'original')
    put(workspace, 'stem-tutor/build/out/assets/P1/a.svg', b'new')
    initial = migration.plan(workspace)
    migration.apply(initial)
    put(workspace, 'stem-tutor/docs/benchmarks/test.svg', b'test evidence')
    expanded = migration.plan(workspace)
    assert expanded['errors'] == []
    assert len(expanded['assets']) == len(initial['assets']) + 1
    for identifier, entry in initial['assets'].items():
        assert expanded['assets'][identifier] == entry
    assert migration.apply(expanded)['copied'] == 1


def test_internal_directory_alias_skipped_with_record_and_external_alias_blocks(workspace, tmp_path):
    target = put(workspace, 'stem-tutor/docs/benchmarks/physical.svg')
    alias = workspace / 'stem-tutor/compat'
    alias.symlink_to(target.parent, target_is_directory=True)
    report = migration.plan(workspace)
    assert report['errors'] == []
    assert len(report['assets']) == 1
    assert any(item['source'] == str(alias) for item in report['excluded'])
    outside = tmp_path / 'outside'
    outside.mkdir()
    (workspace / 'stem-tutor/external').symlink_to(outside, target_is_directory=True)
    assert migration.plan(workspace)['errors']


def test_migration_validation_uses_same_normalized_ownership_rules(workspace):
    from tutorlib.asset_library import validate_catalog
    digest = '0' * 64
    catalog = {'format_version': 1, 'assets': {
        'first': {'path': 'Library/Shared/Café.svg', 'sha256': digest},
        'second': {'path': 'Library/Shared/CAFE\u0301.SVG', 'sha256': digest},
    }}
    for validate in (validate_catalog, migration._validate_catalog):
        with pytest.raises(ValueError, match='ambiguous'):
            validate(catalog)


def test_concurrent_registration_survives_migration_catalog_switch(workspace, monkeypatch):
    from concurrent.futures import ThreadPoolExecutor
    from threading import Event
    from tutorlib.asset_library import register_asset
    put(workspace, 'STEM Tutor/Assets/P1/a.svg', b'planned source')
    new = put(workspace, 'STEM Tutor/Library/Shared/registered.svg', b'concurrent content')
    report = migration.plan(workspace)
    assert report['errors'] == []
    copying = Event()
    registration_started = Event()
    registration_finished = Event()
    original = migration._write

    def pause_copy(root, relative, data, replace=False):
        if relative.endswith('/a.svg'):
            copying.set()
            assert registration_started.wait(5)
            assert not registration_finished.wait(0.1)
        return original(root, relative, data, replace=replace)

    def register_during_copy():
        assert copying.wait(5)
        registration_started.set()
        result = register_asset(workspace / 'STEM Tutor', new.relative_to(workspace / 'STEM Tutor').as_posix())
        registration_finished.set()
        return result

    monkeypatch.setattr(migration, '_write', pause_copy)
    with ThreadPoolExecutor(max_workers=2) as workers:
        applying = workers.submit(migration.apply, report)
        registering = workers.submit(register_during_copy)
        assert applying.result(timeout=10)['sources_deleted'] == 0
        reference = registering.result(timeout=10)
    reader = AssetLibrary(workspace / 'STEM Tutor')
    assert reader.read(reference) == b'concurrent content'
    assert reader.read('Assets/P1/a.svg') == b'planned source'
    assert len(reader.records()) == 2


def test_catalogued_legacy_file_adapter_is_skipped_without_remapping(workspace):
    source = put(workspace, 'stem-tutor/docs/benchmarks/review.svg', b'exact bytes')
    initial = migration.plan(workspace)
    migration.apply(initial)
    reader = AssetLibrary(workspace / 'STEM Tutor')
    canonical = reader.resolve('docs/benchmarks/review.svg')
    before = (workspace / 'STEM Tutor/Library/catalog.json').read_bytes()
    source.unlink()
    source.symlink_to(os.path.relpath(canonical, source.parent))
    rerun = migration.plan(workspace)
    assert rerun['errors'] == []
    assert rerun['assets'] == {}
    assert any(item['reason'] == 'already_library_adapter' and item['alias'] == 'docs/benchmarks/review.svg'
               for item in rerun['excluded'])
    assert (workspace / 'STEM Tutor/Library/catalog.json').read_bytes() == before


@pytest.mark.parametrize('failure', ['unknown', 'wrong-target', 'corrupt-target', 'inexact-alias'])
def test_only_exact_catalog_backed_file_adapters_are_accepted(workspace, tmp_path, failure):
    from tutorlib.asset_library import write_asset
    vault = workspace / 'STEM Tutor'
    canonical = vault / 'Library/Shared/diagram.svg'
    alias = 'docs/diagram.svg'
    write_asset(vault, canonical.relative_to(vault).as_posix(), b'correct', aliases=[alias])
    source = workspace / 'stem-tutor' / alias
    source.parent.mkdir(parents=True)
    target = canonical
    if failure == 'unknown':
        source = source.with_name('unknown.svg')
    elif failure == 'wrong-target':
        target = tmp_path / 'outside.svg'
        target.write_bytes(b'correct')  # even identical bytes cannot authorize a different target
    elif failure == 'corrupt-target':
        canonical.write_bytes(b'changed')
    else:
        source = source.with_name('DIAGRAM.svg')
    source.symlink_to(os.path.relpath(target, source.parent))
    rerun = migration.plan(workspace)
    assert rerun['errors']
    assert not any(item.get('reason') == 'already_library_adapter' for item in rerun['excluded'])


def test_exact_retired_source_marker_does_not_replace_historical_source_entry(workspace):
    source = put(workspace, 'stem-tutor/sources/library/README.md', b'Original source library instructions')
    initial = migration.plan(workspace)
    migration.apply(initial)
    before = (workspace / 'STEM Tutor/Library/catalog.json').read_bytes()
    source.write_bytes(migration.MIGRATION_MARKER)
    rerun = migration.plan(workspace)
    assert rerun['errors'] == [] and rerun['assets'] == {}
    assert any(item['reason'] == 'retired_storage_marker' for item in rerun['excluded'])
    assert (workspace / 'STEM Tutor/Library/catalog.json').read_bytes() == before


def test_shortcut_learning_roots_keep_generated_runtime_and_source_aliases(workspace):
    content = b'[{"spec":"P1","body":"Lesson text"}]'
    put(workspace, 'stem-tutor/build/out/shortcuts/P1.json', content)
    put(workspace, 'STEM Tutor/.tutor/shortcuts/course/P1.json', content)
    put(workspace, 'stem-tutor/build/out/shortcuts/lessons/P1.json', b'[{"lesson":"Guided lesson"}]')
    put(workspace, 'stem-tutor/sources/shortcuts/base/P1.md', b'# Course source')
    put(workspace, 'stem-tutor/sources/shortcuts/research/pure.txt', b'Research notes')
    put(workspace, 'stem-tutor/sources/shortcuts/helper.py', b'not learning content')
    report = migration.plan(workspace)
    assert report['errors'] == []
    assert len(report['assets']) == 4
    generated = next(e for e in report['assets'].values() if 'build/out/shortcuts/P1.json' in e['aliases'])
    assert generated['course'] is None
    assert generated['kind'] == 'Shortcuts/Entries'
    assert generated['path'] == 'Library/Shared/Shortcuts/Entries/P1.json'
    assert '.tutor/shortcuts/course/P1.json' in generated['aliases']
    lesson = next(e for e in report['assets'].values() if 'build/out/shortcuts/lessons/P1.json' in e['aliases'])
    assert lesson['course'] == 'P1' and lesson['kind'] == 'Notes/Shortcuts'
    assert lesson['path'] == 'Library/Courses/P1/Notes/Shortcuts/P1.json'
    assert not any('helper.py' in alias for entry in report['assets'].values() for alias in entry['aliases'])
    migration.apply(report)
    reader = AssetLibrary(workspace / 'STEM Tutor')
    assert reader.read('.tutor/shortcuts/course/P1.json') == content
    assert reader.read('sources/shortcuts/base/P1.md') == b'# Course source'


def test_planner_recognizes_only_exact_migrated_work_directory_adapters(workspace):
    source = put(workspace, 'stem-tutor/build/out/packs/P1/P1-1.json', b'{}')
    migration.apply(migration.plan(workspace))
    old = workspace / 'stem-tutor/build/out'
    target = workspace / 'Work/Candidates'
    target.parent.mkdir()
    old.rename(target)
    old.symlink_to(os.path.relpath(target, old.parent), target_is_directory=True)
    report = migration.plan(workspace)
    assert report['errors'] == []
    assert any(item.get('reason') == 'migrated_work_directory_adapter' for item in report['excluded'])
    reader = AssetLibrary(workspace / 'STEM Tutor')
    assert reader.read('build/out/packs/P1/P1-1.json') == b'{}'


def test_planner_does_not_trust_similarly_named_external_work_adapter(workspace, tmp_path):
    put(workspace, 'STEM Tutor/Assets/P1/d.svg', b'valid')
    migration.apply(migration.plan(workspace))
    outside = tmp_path / 'Candidates'
    outside.mkdir()
    old = workspace / 'stem-tutor/build/out'
    old.parent.mkdir(parents=True)
    old.symlink_to(outside, target_is_directory=True)
    report = migration.plan(workspace)
    assert report['errors']
