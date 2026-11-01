"""Whitespace glyph positions must not flip real official question scripts."""
import re
import pymupdf

from build import mine_mcq
from library_assets import copy_to_vault


def mine_source(tmp_path, monkeypatch, year, season, paper):
    vault = tmp_path / 'vault'
    vault.mkdir()
    prefix = f'Library/Courses/9701/Sources/PastPapers/9701/{year}/{season}/9701_{season}{year % 100:02}'
    qp = copy_to_vault(f'{prefix}_qp_{paper}.pdf', vault)
    ms = copy_to_vault(f'{prefix}_ms_{paper}.pdf', vault)
    monkeypatch.setattr(mine_mcq, 'ASSETS', tmp_path / 'crops')
    return {item['q']: item for item in mine_mcq.mine_paper(qp, ms, '9701')}


def test_body_baseline_space_before_raised_iodide_charge_does_not_make_it_a_subscript(tmp_path, monkeypatch):
    item = mine_source(tmp_path, monkeypatch, 2023, 's', '13')[2]
    assert 'wI⁻' in item['stem']
    assert 'I₋' not in item['stem']
    assert 'Mn²⁺' in item['stem'] and 'H₂O' in item['stem']
    assert item['figure'] and item['image']  # Retain the original source table.


def test_lower_trailing_space_does_not_raise_magnesium_chloride_subscript(tmp_path, monkeypatch):
    item = mine_source(tmp_path, monkeypatch, 2022, 'w', '12')[20]
    assert re.findall(r'MgCl\s*([₂²])\(aq\)', item['stem']) == ['₂', '₂']
    assert item['figure'] and item['image']


def test_isolated_raised_charges_keep_their_only_normal_size_whitespace_anchor(tmp_path):
    vault = tmp_path / 'vault'
    vault.mkdir()
    qp = copy_to_vault('Library/Courses/9701/Sources/PastPapers/9701/2022/w/9701_w22_qp_12.pdf', vault)
    with pymupdf.open(qp) as document:
        page = document[1]
        lines = [line for block in mine_mcq._text_blocks(page, clip=page.rect)
                 for line in block.get('lines', [])]
        charges = [mine_mcq._line_text(line)[0] for line in lines
                   if ''.join(span['text'] for span in line['spans']).strip() in ('–', '2+')]
    assert charges == ['⁻', '²⁺']
