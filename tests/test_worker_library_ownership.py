"""Physical Library ownership must never depend on spelling or catalog health."""
from pathlib import Path

import pytest

from tutor_workers import candidates
from tutorlib.asset_library import write_asset


def library_case(tmp_path, catalog="valid"):
    vault = tmp_path / "vault"
    vault.mkdir()
    canonical = vault / "Library/Courses/9702/pack.json"
    if catalog == "missing":
        canonical.parent.mkdir(parents=True)
        canonical.write_bytes(b'{"subtopic":"9702-1.1"}')
    else:
        write_asset(vault, canonical.relative_to(vault).as_posix(), b'{"subtopic":"9702-1.1"}')
        if catalog == "damaged":
            (vault / "Library/catalog.json").write_text('{"invalid": true}')
    alternate = vault / "library/Courses/9702/pack.json"
    return canonical, alternate


@pytest.mark.parametrize("catalog", ["valid", "missing", "damaged"])
def test_same_physical_library_alias_is_never_a_writable_worker_directory(tmp_path, catalog):
    canonical, alternate = library_case(tmp_path, catalog)
    if not alternate.exists():
        alternate.parent.mkdir(parents=True)
        alternate.write_bytes(b"Ordinary case-sensitive working data")
        assert not alternate.samefile(canonical)
        assert not candidates.library_backed(alternate)
        assert candidates.writable_flags([alternate.parent]) == ["--add-dir", str(alternate.parent.resolve())]
        return
    assert alternate.samefile(canonical)
    before = canonical.read_bytes()

    with pytest.raises(ValueError, match="immutable"):
        candidates.writable_flags([alternate.parent])
    assert candidates.library_backed(alternate)

    assert canonical.read_bytes() == before


@pytest.mark.parametrize("catalog", ["valid", "missing", "damaged"])
def test_preparation_copies_only_verified_library_aliases_without_retargeting(tmp_path, catalog):
    canonical, alternate = library_case(tmp_path, catalog)
    if not alternate.exists():
        pytest.skip("case-sensitive filesystem; the distinct working-directory path is tested separately")
    adapter = tmp_path / "pack.json"
    adapter.symlink_to(alternate)
    data_root = tmp_path / "data"
    before = canonical.read_bytes()
    if catalog != "valid":
        with pytest.raises(ValueError):
            candidates.prepare(data_root, "refine", "9702-1.1", adapter, tmp_path / "missing-note.md")
        assert not (data_root / "Work/Preparation").exists()
    else:
        result = candidates.prepare(data_root, "refine", "9702-1.1", adapter, tmp_path / "missing-note.md")
        assert result.get("candidate_pack")
        copy = Path(result["candidate_pack"])
        assert copy.read_bytes() == before
        assert not candidates.library_backed(copy)
        assert candidates.writable_flags([copy.parent]) == ["--add-dir", str(copy.parent.resolve())]
    assert adapter.is_symlink() and adapter.samefile(canonical)
    assert canonical.read_bytes() == before


def test_ordinary_work_directory_keeps_its_existing_writable_contract(tmp_path):
    work = tmp_path / "Work/candidate"
    assert not candidates.library_backed(work)
    assert candidates.writable_flags([work, work]) == ["--add-dir", str(work.resolve())]
    assert work.is_dir()


def test_teaching_preparation_uses_a_fresh_work_copy_for_library_case_alias(tmp_path):
    canonical, alternate = library_case(tmp_path)
    if not alternate.exists():
        alternate.parent.mkdir(parents=True)
        alternate.write_bytes(b"Working teaching draft")
        assert candidates.prepare_teach(tmp_path / "data", "refine", "9702-1.1", alternate) == {}
        return
    before = canonical.read_bytes()

    result = candidates.prepare_teach(tmp_path / "data", "refine", "9702-1.1", alternate)

    assert result.get("candidate_teach")
    draft = Path(result["candidate_teach"])
    assert draft.read_bytes() == before and not candidates.library_backed(draft)
    assert candidates.writable_flags([draft.parent]) == ["--add-dir", str(draft.parent.resolve())]
    assert canonical.read_bytes() == before
