"""Immutable source images for future skipped-question recovery."""
import pytest
import multiprocessing
import os

from tutorlib import saved_figures


def test_capture_rejects_figure_changed_while_reading(tmp_path, monkeypatch):
    import os
    from types import SimpleNamespace
    source = tmp_path / 'figure.png'
    source.write_bytes(b'original')
    original_fstat = os.fstat
    calls = 0

    def changed(fd):
        nonlocal calls
        result = original_fstat(fd)
        calls += 1
        if calls == 2:
            return SimpleNamespace(st_mode=result.st_mode, st_dev=result.st_dev, st_ino=result.st_ino,
                                   st_size=result.st_size, st_mtime_ns=result.st_mtime_ns + 1,
                                   st_ctime_ns=result.st_ctime_ns)
        return result

    monkeypatch.setattr(saved_figures.os, 'fstat', changed)
    with pytest.raises(ValueError, match='changed'):
        saved_figures.capture(tmp_path, 'figure.png')


def test_snapshot_survives_source_replacement(tmp_path):
    from tutorlib.asset_library import write_asset
    source = tmp_path / 'q.png'
    source.write_bytes(b'original figure')
    snapshot = saved_figures.capture(tmp_path, 'q.png')
    source.write_bytes(b'replacement figure')
    assert saved_figures.read(tmp_path, snapshot) == b'original figure'
    revision = 'Library/Courses/course/Questions/revised.png'
    write_asset(tmp_path, revision, source.read_bytes())
    assert saved_figures.capture(tmp_path, revision) != snapshot


def test_first_capture_syncs_created_directory_entries(tmp_path, monkeypatch):
    (tmp_path / 'q.png').write_bytes(b'figure')
    synced = set()
    original_fsync = os.fsync

    def record(fd):
        info = os.fstat(fd)
        synced.add((info.st_dev, info.st_ino))
        return original_fsync(fd)

    monkeypatch.setattr(saved_figures.os, 'fsync', record)
    saved_figures.capture(tmp_path, 'q.png')
    for directory in (tmp_path, tmp_path / 'Library', tmp_path / 'Library/Shared',
                      tmp_path / 'Library/Shared/OriginalFigures'):
        info = directory.stat()
        assert (info.st_dev, info.st_ino) in synced


def test_snapshot_alone_does_not_bind_later_path_based_display(tmp_path, monkeypatch):
    source = tmp_path / 'q.png'
    source.write_bytes(b'original figure')
    read_bytes = saved_figures._bytes

    def replace_after_read(parent, name):
        data = read_bytes(parent, name)
        replacement = tmp_path / 'new.png'
        replacement.write_bytes(b'replacement figure')
        replacement.replace(source)
        return data

    monkeypatch.setattr(saved_figures, '_bytes', replace_after_read)
    snapshot = saved_figures.capture(tmp_path, 'q.png')
    monkeypatch.setattr(saved_figures, '_bytes', read_bytes)
    assert saved_figures.read(tmp_path, snapshot) == b'original figure'
    assert source.read_bytes() == b'replacement figure'


def test_snapshot_detects_tampering(tmp_path):
    source = tmp_path / 'q.png'
    source.write_bytes(b'figure')
    snapshot = saved_figures.capture(tmp_path, 'q.png')
    (tmp_path / snapshot['path']).write_bytes(b'changed')
    with pytest.raises(ValueError, match='digest'):
        saved_figures.read(tmp_path, snapshot)


@pytest.mark.parametrize('path', ['../outside.png', '/tmp/outside.png'])
def test_snapshot_rejects_paths_outside_vault(tmp_path, path):
    with pytest.raises(ValueError):
        saved_figures.capture(tmp_path, path)


def test_snapshot_rejects_symlink_components_even_inside_vault(tmp_path):
    real = tmp_path / 'real'
    real.mkdir()
    (real / 'q.png').write_bytes(b'figure')
    (tmp_path / 'alias').symlink_to(real, target_is_directory=True)
    with pytest.raises((ValueError, OSError)):
        saved_figures.capture(tmp_path, 'alias/q.png')


def _capture_fifo(root, queue):
    try:
        saved_figures.capture(root, 'pipe')
    except (ValueError, OSError):
        queue.put('rejected')


def test_snapshot_rejects_fifo_without_blocking(tmp_path):
    os.mkfifo(tmp_path / 'pipe')
    context = multiprocessing.get_context('spawn')
    queue = context.Queue()
    process = context.Process(target=_capture_fifo, args=(tmp_path, queue))
    process.start()
    process.join(3)
    if process.is_alive():
        process.terminate()
        process.join()
        pytest.fail('capture blocked on FIFO')
    assert queue.get(timeout=1) == 'rejected'


def test_renderable_snapshot_is_png_and_retains_original_bytes(tmp_path):
    from PIL import Image
    source = tmp_path / 'q.png'
    Image.new('RGB', (3, 2), 'blue').save(source)
    original = source.read_bytes()
    snapshot = saved_figures.capture_renderable(tmp_path, 'q.png')
    assert snapshot['path'].startswith('Library/Shared/Snapshots/')
    assert snapshot['path'].endswith('.png')
    source.write_bytes(b'changed')
    assert saved_figures.read_renderable(tmp_path, snapshot) == original
    (tmp_path / snapshot['path']).write_bytes(b'corrupt')
    with pytest.raises(ValueError):
        saved_figures.read_renderable(tmp_path, snapshot)


def test_renderable_snapshot_rejects_invalid_and_other_image_formats(tmp_path):
    from PIL import Image
    source = tmp_path / 'q.png'
    source.write_bytes(b'not a PNG')
    with pytest.raises(ValueError):
        saved_figures.capture_renderable(tmp_path, 'q.png')
    Image.new('RGB', (2, 2)).save(source, format='JPEG')
    with pytest.raises(ValueError):
        saved_figures.capture_renderable(tmp_path, 'q.png')


def test_renderable_capture_reports_missing_image_library(tmp_path, monkeypatch):
    import builtins
    original_import = builtins.__import__
    def unavailable(name, *args, **kwargs):
        if name == 'PIL':
            raise ImportError('not installed')
        return original_import(name, *args, **kwargs)
    monkeypatch.setattr(builtins, '__import__', unavailable)
    with pytest.raises(ValueError, match='validation is unavailable'):
        saved_figures.capture_renderable(tmp_path, 'figure.png')
    assert not (tmp_path / '.tutor').exists()


def test_renderable_multi_page_capture_preserves_order_and_duplicates(tmp_path):
    from PIL import Image
    for name, colour in [('first.png', 'red'), ('second.png', 'blue')]:
        Image.new('RGB', (2, 2), colour).save(tmp_path / name)
    result = saved_figures.capture_pages(tmp_path, ['second.png', 'first.png', 'second.png'])
    assert len(result) == 3
    assert [saved_figures.read_renderable(tmp_path, entry) for entry in result] == [
        (tmp_path / name).read_bytes() for name in ['second.png', 'first.png', 'second.png']]


def test_renderable_multi_page_capture_fails_closed_on_invalid_page(tmp_path):
    from PIL import Image
    Image.new('RGB', (2, 2)).save(tmp_path / 'good.png')
    (tmp_path / 'bad.png').write_bytes(b'invalid')
    with pytest.raises(ValueError):
        saved_figures.capture_pages(tmp_path, ['good.png', 'bad.png'])
    assert not (tmp_path / '.tutor').exists()
    for pages in ([], ['good.png'] * 33, ['good.png', 2], 'good.png'):
        with pytest.raises(ValueError):
            saved_figures.capture_pages(tmp_path, pages)


def test_prepare_question_figures_binds_all_surfaces_without_mutating_source(tmp_path):
    from PIL import Image
    for name, colour in [('a.png', 'red'), ('b.png', 'blue')]:
        Image.new('RGB', (2, 2), colour).save(tmp_path / name)
    source = {'id': 'question', 'image': 'a.png', 'images': ['a.png', 'b.png']}
    prepared = saved_figures.prepare_question(tmp_path, source)
    assert source == {'id': 'question', 'image': 'a.png', 'images': ['a.png', 'b.png']}
    assert prepared['image'] == prepared['images'][0] == prepared['_figure_snapshots'][0]['path']
    assert prepared['images'] == [snapshot['path'] for snapshot in prepared['_figure_snapshots']]
    assert [saved_figures.read_renderable(tmp_path, entry) for entry in prepared['_figure_snapshots']] == [
        (tmp_path / 'a.png').read_bytes(), (tmp_path / 'b.png').read_bytes()]


def test_prepare_question_figures_refuses_inconsistent_primary_image(tmp_path):
    with pytest.raises(ValueError):
        saved_figures.prepare_question(tmp_path, {'image': 'a.png', 'images': ['b.png']})
    assert not (tmp_path / 'Assets').exists()


@pytest.mark.parametrize('images', [0, {}, '', [1]])
def test_prepare_question_figures_rejects_malformed_pages(tmp_path, images):
    with pytest.raises(ValueError):
        saved_figures.prepare_question(tmp_path, {'images': images})


def test_prepare_question_figures_uses_first_page_for_image_only_consumer(tmp_path):
    from PIL import Image
    Image.new('RGB', (2, 2)).save(tmp_path / 'page.png')
    prepared = saved_figures.prepare_question(tmp_path, {'images': ['page.png']})
    assert prepared['image'] == prepared['images'][0]


def test_verify_question_figures_requires_every_original_page_in_order(tmp_path):
    import copy
    from PIL import Image
    for name, colour in [('a.png', 'red'), ('b.png', 'blue')]:
        Image.new('RGB', (2, 2), colour).save(tmp_path / name)
    prepared = saved_figures.prepare_question(tmp_path, {'images': ['a.png', 'b.png']})
    assert saved_figures.verify_question(tmp_path, prepared) == [(tmp_path / 'a.png').read_bytes(), (tmp_path / 'b.png').read_bytes()]
    reordered = copy.deepcopy(prepared)
    reordered['images'].reverse()
    with pytest.raises(ValueError):
        saved_figures.verify_question(tmp_path, reordered)
    missing = copy.deepcopy(prepared)
    missing['_figure_snapshots'].pop()
    with pytest.raises(ValueError):
        saved_figures.verify_question(tmp_path, missing)
    (tmp_path / prepared['images'][1]).write_bytes(b'tampered')
    with pytest.raises(ValueError):
        saved_figures.verify_question(tmp_path, prepared)


def test_verify_question_refuses_unpinned_and_missing_pages(tmp_path):
    with pytest.raises(ValueError):
        saved_figures.verify_question(tmp_path, {'image': 'old.png'})
    with pytest.raises(ValueError):
        saved_figures.verify_question(tmp_path, {'image': 'x', 'images': ['x'], '_figure_snapshots': []})
    assert saved_figures.verify_question(tmp_path, {'stem': 'No diagram'}) == []


def test_verify_question_caps_combined_page_bytes(tmp_path, monkeypatch):
    monkeypatch.setattr(saved_figures, 'MAX_TOTAL_FIGURE_BYTES', 3)
    monkeypatch.setattr(saved_figures, 'read_renderable', lambda root, entry: b'xx')
    question = {'image': 'a', 'images': ['a', 'b'],
                '_figure_snapshots': [{'path': 'a'}, {'path': 'b'}]}
    with pytest.raises(ValueError, match='too large'):
        saved_figures.verify_question(tmp_path, question)


def test_new_renderable_snapshots_are_registered_without_legacy_asset_writes(tmp_path):
    from PIL import Image
    from tutorlib.asset_library import AssetLibrary
    Image.new('RGB', (2, 2)).save(tmp_path / 'source.png')
    snapshot = saved_figures.capture_renderable(tmp_path, 'source.png')
    assert snapshot['path'].startswith('Library/Shared/Snapshots/')
    assert AssetLibrary(tmp_path).read(snapshot['path']) == (tmp_path / 'source.png').read_bytes()
    assert not (tmp_path / 'Assets').exists()


def test_immutable_legacy_snapshot_descriptor_resolves_catalog_alias(tmp_path):
    import hashlib
    from PIL import Image
    from tutorlib.asset_library import write_asset
    Image.new('RGB', (2, 2)).save(tmp_path / 'source.png')
    data = (tmp_path / 'source.png').read_bytes()
    digest = hashlib.sha256(data).hexdigest()
    legacy = f'Assets/tutor-snapshots/{digest}.png'
    descriptor = {'path': legacy, 'sha256': digest}
    canonical = f'Library/Shared/Snapshots/{digest}.png'
    write_asset(tmp_path, canonical, data, aliases=[legacy])
    assert saved_figures.read_renderable(tmp_path, descriptor) == data
    assert descriptor == {'path': legacy, 'sha256': digest}
    assert not (tmp_path / legacy).exists()


def test_old_snapshot_without_catalog_retains_pinned_hash_check(tmp_path):
    import hashlib
    data = b'old pinned bytes'
    digest = hashlib.sha256(data).hexdigest()
    legacy = f'Assets/tutor-snapshots/{digest}.png'
    path = tmp_path / legacy
    path.parent.mkdir(parents=True)
    path.write_bytes(data)
    descriptor = {'path': legacy, 'sha256': digest}
    assert saved_figures.read_renderable(tmp_path, descriptor) == data
    path.write_bytes(b'tampered')
    with pytest.raises(ValueError, match='digest'):
        saved_figures.read_renderable(tmp_path, descriptor)


def test_snapshot_library_symlink_cannot_write_outside_vault(tmp_path):
    from PIL import Image
    outside = tmp_path / 'outside'
    outside.mkdir()
    (tmp_path / 'Library').symlink_to(outside, target_is_directory=True)
    Image.new('RGB', (2, 2)).save(tmp_path / 'source.png')
    with pytest.raises((ValueError, OSError)):
        saved_figures.capture_renderable(tmp_path, 'source.png')
    assert list(outside.iterdir()) == []


def test_catalog_present_never_falls_back_to_uncatalogued_old_snapshot(tmp_path):
    import hashlib
    from tutorlib.asset_library import write_asset
    data = b'old snapshot'
    digest = hashlib.sha256(data).hexdigest()
    legacy = f'Assets/tutor-snapshots/{digest}.png'
    path = tmp_path / legacy
    path.parent.mkdir(parents=True)
    path.write_bytes(data)
    write_asset(tmp_path, 'Library/Shared/Diagrams/other.svg', b'<svg/>')
    with pytest.raises(ValueError, match='unknown asset reference'):
        saved_figures.read_renderable(tmp_path, {'path': legacy, 'sha256': digest})


def test_unmigrated_legacy_assets_do_not_gain_a_partial_snapshot_catalog(tmp_path):
    from PIL import Image
    legacy = tmp_path / 'Assets'
    legacy.mkdir()
    Image.new('RGB', (2, 2)).save(legacy / 'source.png')
    with pytest.raises(ValueError, match='migration is required'):
        saved_figures.capture_renderable(tmp_path, 'Assets/source.png')
    assert not (tmp_path / 'Library').exists()


def test_raw_capture_bytes_are_canonical_registered_assets(tmp_path):
    from tutorlib.asset_library import AssetLibrary
    (tmp_path / 'source.png').write_bytes(b'original opaque bytes')
    descriptor = saved_figures.capture(tmp_path, 'source.png')
    assert descriptor['path'].startswith('Library/Shared/OriginalFigures/')
    assert descriptor['path'].endswith('.bin')
    assert AssetLibrary(tmp_path).read(descriptor['path']) == b'original opaque bytes'
    assert saved_figures.read(tmp_path, descriptor) == b'original opaque bytes'
    assert not (tmp_path / '.tutor/state/saved-figures').exists()


def test_legacy_private_raw_descriptors_remain_readable_with_new_catalog(tmp_path):
    import hashlib
    from tutorlib.asset_library import write_asset
    data = b'old private original bytes'
    digest = hashlib.sha256(data).hexdigest()
    relative = f'.tutor/state/saved-figures/{digest}'
    path = tmp_path / relative
    path.parent.mkdir(parents=True)
    path.write_bytes(data)
    descriptor = {'path': relative, 'sha256': digest}
    assert saved_figures.read(tmp_path, descriptor) == data
    write_asset(tmp_path, 'Library/Shared/Diagrams/new.svg', b'<svg/>')
    assert saved_figures.read(tmp_path, descriptor) == data
    assert descriptor['path'] == relative

