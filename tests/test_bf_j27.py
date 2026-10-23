"""The source paper's response choices must survive MCQ mining."""
from __future__ import annotations

import sys
from pathlib import Path

import pymupdf
import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'build'))
import mine_mcq


@pytest.fixture
def mine(tmp_path, monkeypatch):
    monkeypatch.setattr(mine_mcq, 'ROOT', tmp_path)
    monkeypatch.setattr(mine_mcq, 'ASSETS', tmp_path / 'build/out/Assets/mcq')

    def run(code: str, year: int, season: str, variant: str):
        qp = ROOT / f'sources/papers/{code}/{year}/{season}/{code}_{season}{year % 100:02}_qp_{variant}.pdf'
        if not qp.exists():
            pytest.skip('source PDF library is not installed')
        items = mine_mcq.mine_paper(qp, qp.with_name(qp.name.replace('_qp_', '_ms_')), code)
        return qp, {it['q']: it for it in items}, tmp_path
    return run


@pytest.mark.parametrize('year,variant', [(2019, '13'), (2020, '12')])
def test_statement_questions_include_the_response_mapping_from_another_page(mine, year, variant):
    """B-052: the student needs the shared A–D table even when it is on another page."""
    _, items, _ = mine('9701', year, 'w', variant)
    assert items[36]['options'] == {
        'A': '1, 2 and 3 are correct', 'B': '1 and 2 only are correct',
        'C': '2 and 3 only are correct', 'D': '1 only is correct',
    }
    assert items[30]['options'] != items[36]['options']


def test_graph_options_keep_their_right_endpoints(mine):
    """B-117: options B and D extend past the old 40-point right margin."""
    qp, items, root = mine('9702', 2020, 's', '12')
    pix = pymupdf.Pixmap(str(root / 'build/out' / items[19]['image']))
    with pymupdf.open(qp) as doc:
        # Full page width preserves the curves and their final tick labels.
        assert pix.width == doc[11].get_pixmap(dpi=130).width


@pytest.mark.parametrize('year,season,variant,q', [
    (2020, 'w', '12', 26), (2023, 'w', '13', 9),
    (2019, 's', '11', 20), (2020, 's', '12', 11),
    (2020, 'w', '13', 25), (2020, 's', '13', 9),
    (2023, 's', '11', 32),
])
def test_page_end_options_are_complete_above_the_footer(mine, year, season, variant, q):
    """B-118: preserve answer rows, denominators and axis labels below y=770."""
    qp, items, root = mine('9702', year, season, variant)
    pix = pymupdf.Pixmap(str(root / 'build/out' / items[q]['image']))
    with pymupdf.open(qp) as doc:
        # Find the actual question page; page indices vary with the paper layout.
        for page in doc:
            spans = [s for b in page.get_text('dict')['blocks'] for ln in b.get('lines', []) for s in ln['spans']]
            anchor = next((s for s in spans if s['flags'] & 16 and s['bbox'][0] < 60 and s['text'].strip() == str(q)), None)
            if anchor:
                break
        y0 = anchor['bbox'][1] - 4
        footer = min(b[1] for b in page.get_text('blocks') if '© UCLES' in b[4])
        expected = page.get_pixmap(clip=pymupdf.Rect(0, y0, page.rect.width, footer - 2), dpi=130, colorspace=pymupdf.csGRAY)
        assert pix.height == expected.height
        assert (pix.width, pix.height, pix.samples) == (expected.width, expected.height, expected.samples)
