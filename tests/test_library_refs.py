"""Runtime asset aliases use an isolated, catalogued temporary Library."""
import copy
import hashlib
import json
from pathlib import Path
from datetime import datetime

import pytest

from fixtures import make_vault
from tutorlib import packs, store, views
from tutorlib.library_refs import LibraryRefs


OLD = "Assets/course/plot.svg"
CANONICAL = "Library/Courses/course/Diagrams/plot.svg"


@pytest.fixture
def library(tmp_path):
    root = make_vault(tmp_path)
    target = root / CANONICAL
    target.parent.mkdir(parents=True)
    target.write_bytes(b"<svg>figure</svg>")
    catalog = {"format_version": 1, "assets": {"plot": {"path": CANONICAL,
               "sha256": hashlib.sha256(target.read_bytes()).hexdigest(), "aliases": [OLD]}}}
    (root / "Library/catalog.json").write_text(json.dumps(catalog))
    # This fixture's unrelated example paper PDFs are intentionally absent.
    (root / ".tutor/packs/v1/papers.json").write_text('{"papers": []}')
    return root


def test_runtime_copy_maps_explicit_asset_fields_without_changing_answers_or_identity(library):
    original = {"id": OLD, "images": [OLD], "stem": f"Use {OLD}", "answer": OLD,
                "source": {"ref": OLD, "pdf": OLD}, "teach": [{"diagrams": [OLD],
                "plain_words": OLD, "note": "Subjects/course/note.md"}], "scheme": [{"image": OLD}]}
    before = copy.deepcopy(original)
    result = LibraryRefs(library).content(original)
    assert result["images"] == [CANONICAL]
    assert result["source"] == {"ref": OLD, "pdf": CANONICAL}
    assert result["teach"][0]["diagrams"] == [CANONICAL]
    for key in ("id", "stem", "answer", "scheme"):
        assert result[key] == before[key]
    assert result["teach"][0]["plain_words"] == OLD
    assert result["teach"][0]["note"] == "Subjects/course/note.md"
    assert original == before


def test_pack_alias_mapping_keeps_path_bound_terminal_diagram_description(library):
    from tutorlib.lesson import overview_figure

    path = library / '.tutor/packs/v1/specs/9702/packs/9702-2.1.json'
    source = json.loads(path.read_text())
    description = 'A labelled curve rises from the origin to the marked endpoint.'
    source['teach'] = {'9702-2.1.1': {'diagrams': [OLD], 'diagram_descriptions': {OLD: description}}}
    path.write_text(json.dumps(source))
    before = path.read_bytes()
    card = packs.Packs(store.Vault(library)).pack('9702-2.1')['teach']['9702-2.1.1']

    assert card['diagrams'] == [CANONICAL]
    assert overview_figure(card)['diagram_description'] == description
    assert path.read_bytes() == before


def test_alias_description_binding_preserves_order_when_paths_converge(library):
    from tutorlib.card_diagrams import diagram_descriptions

    card = {'diagrams': [CANONICAL, OLD],
            'diagram_descriptions': {OLD: 'Second view.', CANONICAL: 'First view.'}}
    before = copy.deepcopy(card)
    mapped = LibraryRefs(library).content(card)
    assert mapped['diagrams'] == [CANONICAL, CANONICAL]
    assert diagram_descriptions(mapped) == ['First view.', 'Second view.']
    assert card == before


def test_description_maps_without_rewritten_paths_keep_their_shape(library):
    card = {'diagrams': [CANONICAL], 'diagram_descriptions': {CANONICAL: 'Same view.'}}
    assert LibraryRefs(library).content(card) == card


@pytest.mark.parametrize('descriptions', [{OLD: 'View.', 'extra.svg': 'Extra.'}, {OLD: ''}, {}])
def test_alias_normalization_preserves_extra_or_empty_description_maps(library, descriptions):
    from tutorlib.card_diagrams import valid_diagram_descriptions

    card = {'diagrams': [OLD], 'diagram_descriptions': descriptions}
    mapped = LibraryRefs(library).content(card)
    assert mapped['diagrams'] == [CANONICAL]
    assert mapped['diagram_descriptions'] == descriptions
    assert not valid_diagram_descriptions(mapped)


def test_alias_normalization_keeps_existing_canonical_description_binding(library):
    from tutorlib.card_diagrams import diagram_descriptions, valid_diagram_descriptions

    # The source validator requires exact keys; the runtime has always verified
    # declared aliases before the description adapter reads the canonical key.
    card = {'diagrams': [OLD], 'diagram_descriptions': {CANONICAL: 'Canonical view.'}}
    before = copy.deepcopy(card)
    assert not valid_diagram_descriptions(card)
    mapped = LibraryRefs(library).content(card)
    assert mapped == {'diagrams': [CANONICAL], 'diagram_descriptions': card['diagram_descriptions']}
    assert valid_diagram_descriptions(mapped)
    assert diagram_descriptions(mapped) == ['Canonical view.']
    assert card == before


def test_content_verifies_repeated_assets_once_per_load_but_rechecks_next_load(library, monkeypatch):
    from tutorlib.asset_library import AssetLibrary

    reads = []
    original = AssetLibrary.read
    def read(self, reference, **kwargs):
        reads.append(reference)
        return original(self, reference, **kwargs)
    monkeypatch.setattr(AssetLibrary, "read", read)
    refs = LibraryRefs(library)
    rows = [{"images": [OLD], "source": {"pdf": OLD}} for _ in range(12)]
    mapped = refs.content(rows)
    assert all(row["images"] == [CANONICAL] for row in mapped)
    assert reads == [OLD]
    (library / CANONICAL).write_bytes(b"tampered")
    with pytest.raises(ValueError, match="digest mismatch"):
        refs.content(rows)


def test_loaded_pack_uses_canonical_assets_but_published_bytes_remain_unchanged(library):
    path = library / ".tutor/packs/v1/specs/9702/packs/9702-2.1.json"
    content = json.loads(path.read_text())
    content["items"][0]["images"] = [OLD]
    content["teach"] = [{"kc": "9702-2.1.1", "diagrams": [OLD]}]
    path.write_text(json.dumps(content))
    before = path.read_bytes()
    loaded = packs.Packs(store.Vault(library)).pack("9702-2.1")
    assert loaded["items"][0]["images"] == [CANONICAL]
    assert loaded["teach"][0]["diagrams"] == [CANONICAL]
    assert loaded["items"][0]["id"] == content["items"][0]["id"]
    assert path.read_bytes() == before


def test_markdown_rewrites_link_targets_and_preserves_prose_labels_sizes_and_code(library):
    original = f"Use {OLD}. ![[{OLD}#part|640]] [PDF](<{OLD}> \"source\") `![[{OLD}]]`\n```\n![[{OLD}]]\n```"
    result = LibraryRefs(library).markdown(original)
    assert result == (f"Use {OLD}. ![[{CANONICAL}#part|640]] [PDF](<{CANONICAL}> \"source\") "
                      f"`![[{OLD}]]`\n```\n![[{OLD}]]\n```")
    assert LibraryRefs(library).markdown("[[Subjects/course/note|Notes]]") == "[[Subjects/course/note|Notes]]"


@pytest.mark.parametrize("separator", ["|", r"\|"])
@pytest.mark.parametrize("target", [OLD, CANONICAL])
def test_markdown_wiki_alias_in_table_preserves_separator(library, separator, target):
    original = f"| [[{target}{separator}Course notes]] |"
    assert LibraryRefs(library).markdown(original) == f"| [[{CANONICAL}{separator}Course notes]] |"


def test_home_renders_registered_notes_as_extensionless_table_links(library):
    from tutorlib import model
    from tutorlib.asset_library import write_asset

    note = "Library/Courses/9702/Notes/Published/v2/2.1 Diffraction.md"
    write_asset(library, note, b"# Diffraction\n")
    pack_file = library / ".tutor/packs/v1/specs/9702/packs/9702-2.1.json"
    pack = json.loads(pack_file.read_text())
    pack["note"] = note
    pack_file.write_text(json.dumps(pack))
    loaded = packs.Packs(store.Vault(library))
    views.write_home(library, loaded, model.new_state(), datetime(2026, 10, 31))
    assert f"[[{note.removesuffix('.md')}\\|" in (library / "Home.md").read_text()


def test_extensionless_wiki_note_checks_hash_and_preserves_anchor(library):
    from tutorlib.asset_library import write_asset

    note = "Library/Courses/course/Notes/Note.md"
    write_asset(library, note, b"# Note\n", aliases=["Subjects/course/Note.md"])
    target = note.removesuffix(".md")
    refs = LibraryRefs(library)
    assert refs.markdown(r"[[Subjects/course/Note#Section\|Read]]") == f"[[{target}#Section\\|Read]]"
    with pytest.raises(ValueError, match="unknown asset reference"):
        refs.markdown(r"[[Library/Courses/course/Notes/Missing\|Read]]")
    (library / note).write_bytes(b"changed")
    with pytest.raises(ValueError, match="digest mismatch"):
        refs.markdown(f"[[{target}\\|Read]]")


def test_root_aware_rendering_and_write_now_emit_canonical_paths(library):
    view = {"n": 1, "kind": "mcq", "stem": "Read graph.", "images": [OLD]}
    original = copy.deepcopy(view)
    assert CANONICAL in views.question_block(view, vault_root=library)
    assert CANONICAL in views.activity_cards({"activity": "explain", "text": "Graph", "diagram": OLD},
                                            obsidian=True, vault_root=library)[0][2]
    views.write_now(library, "Session", [views.question_block(view)])
    assert CANONICAL in (library / "Now.md").read_text()
    assert OLD not in (library / "Now.md").read_text()
    assert view == original


def test_catalog_present_unknown_asset_never_falls_back_to_existing_legacy_file(library):
    old = library / "Assets/course/unknown.svg"
    old.parent.mkdir(parents=True)
    old.write_text("<svg>legacy</svg>")
    with pytest.raises(ValueError, match="unknown asset reference"):
        LibraryRefs(library).reference("Assets/course/unknown.svg")
    with pytest.raises(ValueError, match="unknown asset reference"):
        views.write_now(library, "Session", ["![[Assets/course/unknown.svg]]"])
    assert not (library / "Now.md").exists()
    with pytest.raises(ValueError, match="unknown asset reference"):
        LibraryRefs(library).content({"images": ["unknown.svg"]})
    assert LibraryRefs(library).markdown("[External](https://example.org/figure.svg)") == "[External](https://example.org/figure.svg)"


def test_markdown_preserves_legacy_internal_targets_that_are_not_safe_asset_paths(library):
    target = "My Notes/Maths/P2 Pure Mathematics 2/1 Proof\\"
    markdown = f"[My proof]({target})"
    assert LibraryRefs(library).markdown(markdown) == markdown
    # An asset-looking path still fails closed when its catalog record is absent.
    with pytest.raises(ValueError, match="unknown asset reference"):
        LibraryRefs(library).markdown("![Missing](Assets/course/missing.svg)")


def test_old_vault_without_catalog_retains_legacy_compatibility(tmp_path):
    root = tmp_path / "STEM Tutor"
    root.mkdir()
    refs = LibraryRefs(root)
    assert refs.content({"images": [OLD]}) == {"images": [OLD]}
    assert refs.markdown(f"![[{OLD}]]") == f"![[{OLD}]]"


def test_digest_checks_are_not_bypassed_by_catalog_cache(library):
    refs = LibraryRefs(library)
    assert refs.reference(OLD) == CANONICAL
    (library / CANONICAL).write_text("changed")
    with pytest.raises(ValueError, match="digest mismatch"):
        LibraryRefs(library).reference(OLD)


def test_new_catalog_version_refreshes_cached_aliases(library):
    catalog = library / "Library/catalog.json"
    data = json.loads(catalog.read_text())
    data["assets"]["plot"]["aliases"].append("Assets/course/new-alias.svg")
    catalog.write_text(json.dumps(data))
    assert LibraryRefs(library).reference("Assets/course/new-alias.svg") == CANONICAL


def test_lesson_output_maps_legacy_event_view_without_rewriting_immutable_event(library):
    view = {"n": 1, "kind": "mcq", "stem": "Read graph.", "images": [OLD]}
    events = library / ".tutor/events"
    events.mkdir()
    event = events / "2026-10.jsonl"
    event.write_text(json.dumps({"id": "original-question", "view": view}) + "\n")
    before = event.read_bytes()
    log = views.LessonLog.create(library, "Lesson", datetime(2026, 10, 30, 12))
    log.question(view)
    saved = (library / log.rel).read_text()
    assert CANONICAL in saved and OLD not in saved
    assert event.read_bytes() == before
    assert view["images"] == [OLD]


def test_session_refresh_uses_runtime_pointer_for_library_releases(library):
    import shutil
    from tutorlib.session import Tutor
    releases = library / 'Library/Releases'
    releases.mkdir()
    (library / '.tutor/packs/v1').rename(releases / 'v1')
    tutor = Tutor(store.Vault(library))
    assert tutor.refresh_content() == []
    shutil.copytree(releases / 'v1', releases / 'v2')
    (library / '.tutor/packs/CURRENT').write_text('v2')
    assert tutor.refresh_content() == []
    assert tutor.packs.root == releases / 'v2'

@pytest.mark.parametrize('citation', [
    'Registered Library asset; origin STEM Tutor/Assets/9701/9701-8.1-rate-gradients.svg',
    'Library/Courses/9701/Sources/chapter.pdf p.12; syllabus statements 13.2.1 and 13.2.2',
    'Library/Courses/9701/Sources/chapter.pdf pp. 7–8',
    'Read the registered gradient diagram.svg',
    'Library/Courses/9701/chapter.pdf, p.18',
    'Library/Courses/9701/chapter.pdf, PDF p.311 (explanation)',
])
def test_source_provenance_is_preserved_even_when_it_ends_with_asset_extension(library, citation):
    assert LibraryRefs(library).content({'source': citation}) == {'source': citation}


def test_missing_actual_source_asset_remains_an_error(library):
    with pytest.raises(ValueError, match='unknown asset reference'):
        LibraryRefs(library).content({'source': 'Library/Courses/9701/Diagrams/missing figure.svg'})


def test_repository_prefixed_build_alias_requires_catalog_verification(library):
    from tutorlib.asset_library import register_asset
    register_asset(library, CANONICAL, aliases=['build/out/assets/course/plot.svg'])
    assert LibraryRefs(library).reference('stem-tutor/build/out/assets/course/plot.svg') == CANONICAL
    with pytest.raises(ValueError, match='unknown asset reference'):
        LibraryRefs(library).reference('stem-tutor/build/out/assets/course/missing.svg')
