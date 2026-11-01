"""Selected extraction work verifies selected immutable sources independently."""
import pytest

from test_extraction import extraction, make_pdf
from tutorlib import asset_library


def prepared(tmp_path, monkeypatch):
    ex = extraction()
    root = tmp_path / 'vault'
    root.mkdir()
    monkeypatch.delenv('STEM_LIBRARY_ROOT', raising=False)
    monkeypatch.setenv('STEM_TUTOR_VAULT', str(root))
    monkeypatch.setenv('STEM_EXTRACT_ROOT', str(tmp_path / 'Work'))
    monkeypatch.setenv('STEM_LIBRARY_CACHE', str(tmp_path / 'Work/cache'))
    selected = 'Library/Courses/9702/Sources/Library/selected.pdf'
    other = 'Library/Courses/9702/Sources/Library/other.pdf'
    ref = asset_library.write_asset(root, selected, make_pdf(tmp_path / 'one.pdf', ['Selected question']).read_bytes(),
                                    aliases=['physics-selected.pdf'])
    asset_library.write_asset(root, other, make_pdf(tmp_path / 'two.pdf', ['Other question']).read_bytes())
    return ex, root, selected, other, ref


@pytest.mark.parametrize('selector', ['id', 'canonical', 'absolute', 'alias'])
@pytest.mark.parametrize('fault', ['unavailable', 'hash'])
def test_selected_inventory_and_verification_ignore_only_unselected_failures(tmp_path, monkeypatch, selector, fault):
    ex, root, selected, other, ref = prepared(tmp_path, monkeypatch)
    refs = {'id': ref, 'canonical': selected, 'absolute': str(root / selected), 'alias': 'physics-selected.pdf'}
    before = {p: p.read_bytes() for p in (root / selected, root / other, root / 'Library/catalog.json')}
    original = asset_library._read_regular
    reads = []
    def unavailable(vault, relative, *args, **kwargs):
        reads.append(relative)
        if relative == other:
            if fault == 'hash':
                return b'not the registered PDF'
            raise PermissionError('Unselected PDF temporarily unavailable')
        return original(vault, relative, *args, **kwargs)
    monkeypatch.setattr(asset_library, '_read_regular', unavailable)
    ex.create('selected', '9702', provider='codex', sources=[refs[selector]])
    state = ex.inventory('selected')
    assert [source['id'] for source in state['sources']] == [ref]
    assert other not in reads
    reads.clear()
    ex._verify_sources(state)
    assert [path for path in reads if path.endswith('.pdf')] == [selected]
    assert 'Library/catalog.json' in reads  # metadata stays fresh for each operation
    # Selecting all sources still verifies all bytes and surfaces the damage.
    with pytest.raises(ex.library.Fail):
        ex.library.source_files('all', '9702')
    assert all(p.read_bytes() == data for p, data in before.items())


def test_selected_resource_damage_and_frozen_hash_changes_still_fail(tmp_path, monkeypatch):
    ex, root, selected, _, ref = prepared(tmp_path, monkeypatch)
    ex.create('selected', '9702', provider='codex', sources=[ref])
    state = ex.inventory('selected')
    original = asset_library._read_regular
    def wrong_bytes(vault, relative, *args, **kwargs):
        return b'wrong selected bytes' if relative == selected else original(vault, relative, *args, **kwargs)
    with monkeypatch.context() as patch:
        patch.setattr(asset_library, '_read_regular', wrong_bytes)
        with pytest.raises(ex.library.Fail, match='digest mismatch'):
            ex._verify_sources(state)
    state['sources'][0]['sha256'] = '0' * 64
    with pytest.raises(ValueError, match='source changed'):
        ex._verify_sources(state)


def test_wrong_course_selector_does_not_grant_source_access(tmp_path, monkeypatch):
    ex, _, _, _, ref = prepared(tmp_path, monkeypatch)
    ex.create('wrong', '9701', provider='codex', sources=[ref])
    with pytest.raises(ValueError, match='exactly match verified sources for this course'):
        ex.inventory('wrong')


@pytest.mark.parametrize('applicable', [True, False])
def test_exact_shared_source_selector_still_requires_course_applicability(tmp_path, monkeypatch, applicable):
    ex, root, _, _, _ = prepared(tmp_path, monkeypatch)
    relative = 'Library/Shared/Sources/Library/shared.pdf'
    ref = asset_library.write_asset(root, relative, make_pdf(tmp_path / 'shared.pdf', ['Shared source']).read_bytes(),
                                    metadata={'courses': ['9702' if applicable else '9701']})
    files = ex.library.source_files('all', '9702', references={ref})
    assert [path for _, path in files] == ([root / relative] if applicable else [])
    ex.create('shared', '9702', provider='codex', sources=[ref])
    if applicable:
        assert [s['id'] for s in ex.inventory('shared')['sources']] == [ref]
    else:
        with pytest.raises(ValueError, match='exactly match verified sources for this course'):
            ex.inventory('shared')


def test_selected_jobs_remain_bound_when_the_vault_is_accessed_through_a_directory_alias(tmp_path, monkeypatch):
    ex, root, selected, _, ref = prepared(tmp_path, monkeypatch)
    ex.create('selected', '9702', provider='codex', sources=[ref])
    state = ex.inventory('selected')
    alias = root.with_name('vault-alias')
    alias.symlink_to(root, target_is_directory=True)
    assert alias.samefile(root)
    monkeypatch.setenv('STEM_TUTOR_VAULT', str(alias))
    ex._verify_sources(state)
    # Both stable IDs and exact paths through the chosen vault alias work for
    # new jobs, while the frozen source path stays canonical.
    for name, selector in [('id-alias', ref), ('path-alias', str(alias / selected))]:
        ex.create(name, '9702', provider='codex', sources=[selector])
        loaded = ex.inventory(name)
        assert [s['path'] for s in loaded['sources']] == [str(root / selected)]
        ex._verify_sources(loaded)
