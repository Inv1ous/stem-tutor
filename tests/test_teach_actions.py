"""The teaching actions the learning AI may request: checked, rendered by the program, withheld while a question is open."""
from __future__ import annotations
from library_assets import read_json as library_json

import json
import hashlib
import io
from pathlib import Path

import pytest

from tutorlib import teach_actions as ta
from tutorlib.asset_library import AssetLibrary, write_asset

ROOT = Path(__file__).resolve().parents[1]
CARD = library_json('build/work/teach/P2-1.json')["P2-1.1"]
NOTES_FIG = "P2-1-notes-techniques-map"
NOTES_PATH = 'Library/Courses/P2/Diagrams/p2-1-notes-techniques-map.png'


@pytest.fixture
def vault(tmp_path):
    """Synthetic figure and provenance in an isolated temporary Library."""
    from PIL import Image
    image = io.BytesIO()
    Image.new('RGB', (3, 2), 'blue').save(image, format='PNG')
    data = image.getvalue()
    meta = {'subtopic': 'P2-1', 'sha256': hashlib.sha256(data).hexdigest(), 'pdf': 'YMA01 c1.1.pdf',
            'page': 2, 'caption': 'Synthetic map', 'why': 'Compare techniques'}
    sidecar = write_asset(tmp_path, 'Library/Courses/P2/Sources/Provenance/map.png.json',
                          json.dumps(meta).encode())
    write_asset(tmp_path, NOTES_PATH, data, metadata={'provenance': {'sidecars': [sidecar]}})
    return tmp_path


def run(vault, actions, blocked=None):
    figs = ta.figures_for(vault, "P2-1")
    return ta.run(actions, card=CARD, kc="P2-1.1", subtopic="P2-1", vault_root=vault, figures=figs, blocked=blocked)


def test_the_ai_is_offered_every_visual_tool_and_the_figures_it_may_name(vault):
    text = ta.catalogue(CARD, ta.figures_for(vault, "P2-1"))
    assert "generated" in text and "notes" in text and "card" in text and "Never write SVG" in text
    assert "p2-1-notes-techniques-map" in text and "graph_sketch" in text  # the real cropped figure is named


def test_a_notes_figure_is_shown_with_its_source_and_page(vault):
    [r] = run(vault, [{"action": "diagram", "source": "notes", "figure": "p2-1-notes-techniques-map"}])
    assert r["kind"] == "card" and r["image"] == NOTES_PATH
    assert "YMA01 c1.1.pdf, p.2" in r["body"]
    assert f"![[{NOTES_PATH}]]" in ta.blocks_for([r])[0]  # Obsidian embed
    assert ta.as_activity(r)["diagram_description"]  # the terminal's text stand-in


def test_a_changed_notes_picture_is_no_longer_offered(vault):
    (vault / NOTES_PATH).write_bytes(b"not the same picture")
    assert ta.figures_for(vault, "P2-1") == []
    [r] = run(vault, [{"action": "diagram", "source": "notes", "figure": "p2-1-notes-techniques-map"}])
    assert r["kind"] == "problem"


def test_missing_card_diagram_does_not_create_broken_embed(tmp_path):
    [r] = run(tmp_path, [{"action": "diagram", "source": "card", "form": 0}])
    assert r['kind'] == 'problem'
    assert 'diagram' in r['text'].lower()
    assert '![[' not in str(r)


def test_available_card_diagram_is_embedded_from_the_vault(tmp_path):
    relative = CARD['diagrams'][0]
    target = tmp_path / relative
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text('<svg/>')
    [r] = run(tmp_path, [{'action': 'diagram', 'source': 'card', 'form': 0}])
    assert r['image'] == relative
    assert f'![[{relative}]]' in ta.blocks_for([r])[0]


def test_a_generated_diagram_is_drawn_from_structured_data_and_explained_in_words(tmp_path):
    [r] = run(tmp_path, [{"action": "diagram", "source": "generated", "type": "case_split", "why": "Odd or even",
                           "params": {"start": "n is an integer", "cases": ["n even", "n odd"], "end": "n² + n is even"}}])
    assert r["kind"] == "card" and r["image"].startswith("Library/Courses/P2/Diagrams/case_split-") and r["body"]
    svg = (tmp_path / r["image"]).read_text()
    assert svg.lstrip().startswith("<?xml") and "n is an integer" in svg
    assert AssetLibrary(tmp_path).read(r['image']) == (tmp_path / r['image']).read_bytes()
    assert not (tmp_path / 'Assets').exists()


def test_generated_diagram_without_course_uses_shared_library(tmp_path):
    relative, error = ta.generate_diagram(tmp_path, 'proof_flow', {'steps': ['Start', 'Finish']})
    assert not error and relative.startswith('Library/Shared/Diagrams/proof_flow-')
    assert AssetLibrary(tmp_path).read(relative).startswith(b'<?xml')
    assert not (tmp_path / 'Assets').exists()


def test_catalogued_card_diagram_resolves_legacy_alias_without_legacy_files(tmp_path):
    canonical = 'Library/Courses/P2/Diagrams/card.svg'
    legacy = CARD['diagrams'][0]
    write_asset(tmp_path, canonical, b'<svg/>', aliases=[legacy])
    [result] = run(tmp_path, [{'action': 'diagram', 'source': 'card', 'form': 0}])
    assert result['image'] == canonical
    assert not (tmp_path / legacy).exists()


def test_generated_library_directory_symlink_is_refused(tmp_path):
    outside = tmp_path / 'outside'
    outside.mkdir()
    (tmp_path / 'Library').symlink_to(outside, target_is_directory=True)
    relative, error = ta.generate_diagram(tmp_path, 'proof_flow', {'steps': ['Start', 'Finish']})
    assert relative is None and error
    assert list(outside.iterdir()) == []


def test_circuit_renderer_registers_svg_bytes_without_saving_legacy_file(tmp_path):
    relative, error = ta.generate_diagram(tmp_path, 'circuit', {'elements': [{'type': 'resistor', 'label': 'R'}]}, course='P2')
    assert not error and relative.startswith('Library/Courses/P2/Diagrams/circuit-')
    assert b'<svg' in AssetLibrary(tmp_path).read(relative)
    assert not (tmp_path / 'Assets').exists()


def test_unmigrated_legacy_assets_get_clear_error_before_new_catalog(tmp_path):
    legacy = tmp_path / 'Assets'
    legacy.mkdir()
    (legacy / 'old.svg').write_text('<svg/>')
    relative, error = ta.generate_diagram(tmp_path, 'proof_flow', {'steps': ['Start', 'Finish']})
    assert relative is None and 'migration is required' in error
    assert not (tmp_path / 'Library').exists()


@pytest.mark.parametrize("req", [
    {"action": "diagram", "source": "generated", "type": "shell", "params": {}},          # not a figure type
    {"action": "diagram", "source": "generated", "type": "wave", "params": {"__import__": "os"}},  # not a setting
    {"action": "diagram", "source": "generated", "type": "wave", "params": "amplitude=2"},        # not data
    {"action": "diagram", "source": "generated", "type": "wave", "params": {"xlabel": "x" * 5000}},  # too big
    {"action": "diagram", "source": "notes", "figure": "../../etc/passwd"},
    {"action": "rm -rf", "path": "/"}, {"action": "explain", "section": "motivate"}, "explain",
])
def test_anything_outside_the_list_is_refused_not_run(tmp_path, req):
    [r] = run(tmp_path, [req])
    assert r["kind"] == "problem" and not list((tmp_path / "Assets").rglob("*")) if (tmp_path / "Assets").exists() else r["kind"] == "problem"


def test_a_bad_expression_in_a_figure_falls_back_to_words(tmp_path):
    [r] = run(tmp_path, [{"action": "diagram", "source": "generated", "type": "function_plot",
                           "params": {"functions": [{"expr": "__import__('os').system('x')", "domain": [0, 1]}]}}])
    assert r["kind"] == "problem" and "words" in r["text"]


def test_explanations_terms_examples_and_checks_come_from_the_card_not_the_ai(vault):
    out = run(vault, [{"action": "explain", "section": "plain_words"}, {"action": "term", "term": "ℤ"},
                      {"action": "example", "form": 0}, {"action": "check", "form": 0}])
    out += run(vault, [{"action": "hint"}, {"action": "question"}])
    assert [r["kind"] for r in out] == ["card", "card", "card", "ui", "ui", "ui"]
    assert out[0]["body"] == CARD["plain_words"].strip() and out[1]["term"] == "Integer"
    assert "**Claim:**" in out[2]["body"] and CARD["forms"][0]["answer"] not in out[3].values()


def test_nothing_that_could_carry_an_answer_is_shown_while_a_question_is_open(vault):
    out = run(vault, [{"action": "explain", "section": "plain_words"}, {"action": "term", "term": "ℤ"},
                      {"action": "example", "form": 0}, {"action": "diagram", "source": "card"}], blocked="Answer the question first.")
    out += run(vault, [{"action": "hint"}, {"action": "note", "text": "my own note"}], blocked="Answer the question first.")
    assert [r["kind"] for r in out] == ["problem"] * 4 + ["ui", "card"]
    assert all(r["text"] == "Answer the question first." for r in out[:4])


def test_at_most_four_actions_run_and_a_note_is_short(vault):
    out = run(vault, [{"action": "note", "text": "x" * 900}] * 7)
    assert len(out) == ta.MAX_ACTIONS and len(out[0]["body"]) == 400



EXPLANATION = ("Take three consecutive integers n-1, n and n+1. Their sum is (n-1)+n+(n+1), and the two outer terms "
               "cancel their 1s, so it is 3n. That is a multiple of 3 whatever n is, which testing a few triples never shows.")


def test_a_tutor_written_explanation_is_labelled_as_its_own_and_says_what_was_checked(vault):
    [r] = run(vault, [{"action": "write", "topic": "Three consecutive integers", "text": EXPLANATION,
                       "checked": ["(n-1)+n+(n+1) = 3n"], "unchecked": 1}])
    assert r["kind"] == "card" and r["title"] == "Tutor-written: Three consecutive integers" and EXPLANATION in r["body"]
    assert "not from your notes or a past paper" in r["body"] and "`(n-1)+n+(n+1) = 3n`" in r["body"]  # a code span
    assert "Other equations, the wording and the reasoning are not machine-checked." in r["body"]
    [r] = run(vault, [{"action": "write", "topic": "Sums", "text": EXPLANATION}])
    assert "are not machine-checked" in r["body"] and "Checked by computer algebra" not in r["body"]


def test_a_write_that_failed_or_came_back_empty_shows_a_plain_problem(vault):
    assert run(vault, [{"action": "write", "topic": "Sums", "problem": "an equation is not true"}])[0]["kind"] == "problem"
    assert run(vault, [{"action": "write", "topic": "Sums", "text": "short"}])[0]["kind"] == "problem"


def test_a_written_explanation_is_held_back_while_a_question_is_open(vault):
    [r] = ta.run([{"action": "write", "topic": "Sums", "text": EXPLANATION}], card=CARD, kc="P2-1.1", subtopic="P2-1",
                 vault_root=vault, figures=[], blocked="Answer first.")
    assert r == {"kind": "problem", "text": "Answer first."}


def test_the_ai_is_told_each_figure_types_settings(vault):
    text = ta.catalogue(CARD, [])
    assert "case_split (cases, end, start)" in text and "proof_flow (steps)" in text


def test_the_older_idea_and_section_form_is_accepted_for_this_idea_only(vault):
    out = run(vault, [{"action": "explain", "section": "P2-1.1|plain_words"}, {"action": "explain", "section": "P2-1.2|plain_words"}])
    assert out[0]["kind"] == "card" and out[1]["kind"] == "problem"
