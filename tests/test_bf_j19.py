"""Readable source mathematics survives publication and regeneration."""
from __future__ import annotations

import ast
import json
import os
import runpy
import shutil
import subprocess
import sys
import warnings
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'build'))
from content_checks import debris_problems
from validate_pack import validate
from library_assets import REAL_VAULT, read_json as library_json, copy_to_vault


def pack_for(kc: str) -> dict:
    return library_json(f'build/out/packs/{kc.split("-")[0]}/{kc}.json')


def item_for(kc: str, suffix: str) -> dict:
    return next(it for it in pack_for(kc)['items'] if it['id'] == f'{kc}-{suffix}')


def test_ideal_gas_question_has_readable_numbered_statements_and_choices() -> None:
    """B-056: the encoded PDF font must not become a graded gibberish question."""
    it = item_for('9701-4.1', 'x019')
    assert not debris_problems(it)
    assert it['stem'] == ('Which assumptions are made about ideal gases?\n'
                          '1  Ideal gases contain molecules with no mass.\n'
                          '2  Ideal gases contain molecules with no volume.\n'
                          '3  Ideal gases have no intermolecular forces.')
    assert it['options'] == dict(zip('ABCD', ['1, 2 and 3', '1 and 2 only', '1 and 3 only', '2 and 3 only']))
    assert it['answer'] == 'D'


@pytest.mark.parametrize('kc,suffix,options', [
    ('9702-5.1', 'x059', ['$Fv/4.0$', '$4.0/(Fv)$', '$4.0Fv$', '$4.0F/v$']),
    ('9702-1.3', 'x031', ['$W = XY$', '$W = 2XY$', '$W = X/Y^2$', '$W = Y/X^2$']),
    ('9702-6.1', 'x010', ['$ε/σ$', '$Fx/(AL)$', '$σx/L$', '$F/(Aε)$']),
    ('9702-5.1', 'x043', ['$Y/W$', '$Y/(W+X)$', '$Y/X$', '$Y/(W+X+Y)$']),
])
def test_fraction_options_keep_the_source_numerators_and_denominators(kc: str, suffix: str, options: list[str]) -> None:
    """B-073: division bars and exponents must distinguish the four choices."""
    it = item_for(kc, suffix)
    assert it['options'] == dict(zip('ABCD', options))
    if suffix == 'x010':
        assert '$σ = F/A$' in it['stem'] and '$ε = x/L$' in it['stem']


def test_charge_to_mass_equation_keeps_its_division() -> None:
    """B-073: the charge-to-mass definition must not reverse or flatten the ratio."""
    assert 'r = (charge on particle)/(mass of particle)' in item_for('9702-11.1', 'p01')['stem']


def test_charge_to_mass_equation_survives_regenerating_the_bundle_and_pack(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """B-073: rebuilding p01 must preserve charge divided by mass from its inputs."""
    import bundle

    vault = tmp_path / 'STEM Tutor'
    vault.mkdir()
    scratch = tmp_path / 'stem-tutor'
    generator = tmp_path / 'Work/Preparation/gen/9702-11.1.py'
    for relative in ['build/out/specs/9702/graph.json', 'build/work/mcq/9702.tagged.json',
                     'build/work/mcq/overrides.json', 'build/work/gen/9702-11.1.py']:
        target = scratch / relative if relative.endswith('.json') else generator
        target.parent.mkdir(parents=True, exist_ok=True)
        if relative.endswith('.json'):
            canonical = copy_to_vault(relative, vault)
            target.symlink_to(os.path.relpath(canonical, target.parent))
        else:
            shutil.copyfile(ROOT / relative, target)
    monkeypatch.setattr(bundle, 'ROOT', scratch)
    monkeypatch.setattr(bundle, 'OUT', scratch / 'build/work/bundles')
    # Local library and examiner-report searches are unrelated to the equation.
    monkeypatch.setattr(bundle, '_library_lines', lambda subtopic: [])
    monkeypatch.setattr(bundle.er_excerpts, 'excerpts', lambda *args: [])
    bundle.bundle('9702-11.1')
    runpy.run_path(str(generator))

    rebuilt = json.loads((scratch / 'build/out/packs/9702/9702-11.1.json').read_text())
    question = next(it for it in rebuilt['items'] if it['id'] == '9702-11.1-p01')
    original = item_for('9702-11.1', 'p01')
    assert 'r = (charge on particle)/(mass of particle)' in question['stem']
    assert question == original


@pytest.mark.parametrize('options', [
    ['4.0 Fv', 'Fv 4.0', '4.0Fv', 'v F 4.0'],
    ['W = XY', 'W = 2XY', 'W = Y X', 'W = X Y'],
])
def test_publishing_rejects_options_distinguished_only_by_spacing(options: list[str]) -> None:
    """B-073: a lost fraction bar can leave a distractor identical to the key."""
    it = item_for('9702-5.1', 'x059')
    it['options'] = dict(zip('ABCD', options))
    graph = {'spec': '9702', 'kcs': [{'id': it['kcs'][0], 'subtopic': '9702-5.1'}]}
    pack = {'spec': '9702', 'subtopic': '9702-5.1', 'note': 'test', 'items': [it]}
    assert any(p['rule'] == 'mcq-options' for p in validate(pack, graph, min_variants=0))
    it['options'] = dict(zip('ABCD', ['$Fv/4.0$', '$4.0/(Fv)$', '$4.0Fv$', '$4.0F/v$']))
    assert not any(p['rule'] == 'mcq-options' for p in validate(pack, graph, min_variants=0))
    it['options'] = dict(zip('ABCD', options))
    it['image'] = 'Assets/source.png'
    assert not any(p['rule'] == 'mcq-options' for p in validate(pack, graph, min_variants=0))


def test_binomial_feedback_and_worked_steps_have_intact_math_commands() -> None:
    """B-050: Python/JSON escapes must not eat binomial or fraction commands."""
    pack = pack_for('P2-4')
    assert not debris_problems(pack)
    for n in range(25, 31):
        assert item_for('P2-4', f'i{n}')['explanation'] == r'The coefficient is $\binom{n}{r}a^{n-r}b^r$.'
    assert r'\frac{n}{2}' in pack['worked'][1]['steps'][1]['do']
    assert r'\binom{4}{2}' in pack['worked'][3]['steps'][0]['do']


def test_binomial_generator_does_not_reintroduce_control_characters() -> None:
    """B-050: inspect evaluated literals without regenerating the published pack."""
    tree = ast.parse((ROOT / 'build/work/gen/P2-4.py').read_text())
    strings = [node.value for node in ast.walk(tree) if isinstance(node, ast.Constant) and isinstance(node.value, str)]
    assert not debris_problems(strings)


def test_sequence_generator_uses_english_ordinal_suffixes() -> None:
    """B-054: the sequence generator must spell regular and teen ordinals correctly."""
    generator = ROOT / 'build/work/gen/P2-4.py'
    with warnings.catch_warnings():
        warnings.simplefilter('ignore', SyntaxWarning)
        tree = ast.parse(generator.read_text())
    ordinal = next(node for node in tree.body
                   if isinstance(node, ast.FunctionDef) and node.name == 'ordinal')
    namespace = {}
    exec(compile(ast.unparse(ordinal), '<ordinal>', 'exec'), namespace)

    assert {n: namespace['ordinal'](n) for n in (1, 2, 3, 4, 11, 12, 13, 21)} == {
        1: '1st', 2: '2nd', 3: '3rd', 4: '4th',
        11: '11th', 12: '12th', 13: '13th', 21: '21st',
    }


def test_sequence_generator_writes_an_ordinal_correct_pack_in_tmp_path(tmp_path: Path) -> None:
    """B-054: exercise the real generator without writing to shared build output."""
    generator = ROOT / 'build/work/gen/P2-4.py'
    output_root = tmp_path / 'generated'
    source = generator.read_text()
    original_root = "ROOT=(Path(__file__).resolve().parents[3] / 'stem-tutor')"
    assert original_root in source
    copied = tmp_path / 'P2-4.py'
    copied.write_text(source.replace(original_root, f'ROOT=Path({str(output_root)!r})', 1))

    subprocess.run([sys.executable, str(copied)], check=True, capture_output=True, text=True)

    pack = json.loads((output_root / 'build/out/packs/P2/P2-4.json').read_text())
    item = next(item for item in pack['items'] if item['id'] == 'P2-4-i01')
    assert len(pack['items']) == 36
    assert item['stem'] == 'Find the 3rd term of $u_n=2n^2-3n+1$.'
    assert item['answer']['value'] == 10.0


def test_past_paper_repairs_survive_rebuilding_extras(tmp_path: Path, monkeypatch) -> None:
    """B-056/B-073: the bank overrides must keep repairs on an extras rebuild."""
    from add_past import add
    # This rebuild only reads source figures; its candidate pack is disposable.
    monkeypatch.setenv('STEM_TUTOR_VAULT', str(REAL_VAULT))
    for kc, suffix in [('9701-4.1', 'x019'), ('9702-5.1', 'x059'), ('9702-1.3', 'x031'),
                       ('9702-6.1', 'x010'), ('9702-5.1', 'x043')]:
        original = item_for(kc, suffix)
        qid = original['source']['qid']
        overrides = library_json('build/work/mcq/overrides.json')
        assert qid in overrides
        path = tmp_path / f'{kc}.json'
        path.write_text(json.dumps(pack_for(kc)))
        add(path)
        rebuilt = next(it for it in json.loads(path.read_text())['items'] if it['id'] == original['id'])
        assert rebuilt == original


def test_unmapped_pdf_controls_require_an_image_fallback() -> None:
    """B-056: shifted font text with control glyphs is not safe plain text."""
    from mine_mcq import _glyphs
    assert not _glyphs({'text': '\x15 DQG \x16 RQO\\'})[1]
    assert _glyphs({'text': '2 and 3 only'}) == ('2 and 3 only', True)
