"""Authoring a Physics pack must retain the official paper variant."""
import ast
from pathlib import Path

import pytest


@pytest.mark.parametrize('paper', ['11', '12', '13'])
def test_potential_difference_generator_keeps_full_paper_variant(paper):
    generator = Path(__file__).resolve().parents[1] / 'build/work/gen/9702-9.2.py'
    tree = ast.parse(generator.read_text())
    function = next(node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name == 'past')
    namespace = {'P': [], 'S': '9702-9.2', 'K': lambda n: f'9702-9.2.{n}'}
    exec(compile(ast.Module(body=[function], type_ignores=[]), str(generator), 'exec'), namespace)
    namespace['past'](f'9702_w23_{paper}_q31', 'A', 1, 'Question', ['1', '2', '3', '4'], 'Explanation')
    assert namespace['P'][0]['source']['ref'] == f'CAIE 9702 · Nov 2023 · P{paper} · Q31'
