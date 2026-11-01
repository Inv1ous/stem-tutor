"""Paper discovery and crop publication use an isolated canonical Library."""
import json
from pathlib import Path
import sys

import pymupdf
import pytest

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / 'build'))
import er_excerpts
import library
import mine_mcq
from tutorlib.asset_library import AssetLibrary, write_asset


def pdf_bytes(text, *, question=False):
    document = pymupdf.open()
    page = document.new_page()
    if question:
        page.insert_text((40, 70), '1', fontname='hebo', fontsize=12)
        page.insert_text((75, 70), 'Read the source diagram and select the correct answer.', fontsize=12)
        for index, option in enumerate(['A First choice', 'B Second choice', 'C Third choice', 'D Fourth choice']):
            page.insert_text((75, 105 + index * 25), option, fontsize=12)
        page.draw_line((75, 220), (200, 220))
    else:
        page.insert_text((50, 70), text, fontsize=12)
    result = document.tobytes()
    document.close()
    return result


@pytest.fixture
def paper_library(tmp_path, monkeypatch):
    vault = tmp_path / 'STEM Tutor'
    vault.mkdir()
    monkeypatch.setenv('STEM_TUTOR_VAULT', str(vault))
    monkeypatch.delenv('STEM_LIBRARY_ROOT', raising=False)
    monkeypatch.setattr(mine_mcq, 'PAPERS', None)
    monkeypatch.setattr(mine_mcq, 'ASSETS', None)
    monkeypatch.setattr(er_excerpts, 'PAPERS', None)
    return vault


def add_paper(vault, filename, content, extra='original'):
    relative = f'Library/Courses/9702/Sources/PastPapers/{extra}/{filename}'
    write_asset(vault, relative, content, metadata={'course': '9702', 'kind': 'Sources/PastPapers'})
    return vault / relative


def test_default_miner_keeps_official_basename_key_and_catalogues_crop(paper_library):
    vault = paper_library
    qp = add_paper(vault, '9702_s23_qp_12.pdf', pdf_bytes('', question=True))
    ms = add_paper(vault, '9702_s23_ms_12.pdf', pdf_bytes('1\nA\n1'))
    sources = mine_mcq.paper_sources('9702')
    assert sources[qp.name] == qp and sources[ms.name] == ms
    items = mine_mcq.mine_paper(qp, ms, '9702')
    assert len(items) == 1
    item = items[0]
    assert item['id'] == '9702_s23_12_q1'
    assert item['answer'] == 'A'
    assert item['ref'] == 'CAIE 9702 · Jun 2023 · P12 · Q1'
    assert item['image'].startswith('Library/Courses/9702/Questions/Media/9702_s23_12_q1-')
    catalog = AssetLibrary(vault)
    assert catalog.read(item['image']).startswith(b'\x89PNG')
    record = catalog.record(item['image'])
    assert record['provenance']['source'] == qp.relative_to(vault).as_posix()
    assert record['provenance']['mark_scheme'] == ms.relative_to(vault).as_posix()
    assert record['provenance']['page'] == 1
    assert mine_mcq.mine_paper(qp, ms, '9702')[0]['image'] == item['image']


def test_default_discovery_never_falls_back_to_legacy_papers(paper_library, tmp_path, monkeypatch):
    fake_repo = tmp_path / 'repo'
    legacy = fake_repo / 'sources/papers/9702/9702_s23_qp_12.pdf'
    legacy.parent.mkdir(parents=True)
    legacy.write_bytes(pdf_bytes('', question=True))
    monkeypatch.setattr(mine_mcq, 'ROOT', fake_repo)
    monkeypatch.setattr(er_excerpts, 'ROOT', fake_repo)
    assert mine_mcq.paper_sources('9702') == {}
    assert er_excerpts.split('9702') == []


def test_source_discovery_rejects_differing_duplicate_official_papers(paper_library):
    vault = paper_library
    add_paper(vault, '9702_s23_qp_12.pdf', pdf_bytes('first'), 'first')
    add_paper(vault, '9702_s23_qp_12.pdf', pdf_bytes('different'), 'second')
    with pytest.raises(ValueError, match='ambiguous source paper'):
        mine_mcq.paper_sources('9702')


def test_examiner_report_parser_reads_canonical_source_and_preserves_references(paper_library):
    report = ('Paper 9702/12\nGeneral comments\nComments on specific questions\nQuestion 1\n'
              'Candidates should explain the source diagram and use the correct physical quantity.')
    add_paper(paper_library, '9702_s23_er.pdf', pdf_bytes(report))
    rows = er_excerpts.split('9702')
    assert rows[0]['ref'] == 'ER 9702 s23 P12 general'
    question = next(row for row in rows if row['q'] == '1')
    assert question['ref'] == 'ER 9702 s23 P12 Q1'
    assert 'correct physical quantity' in question['text']


def test_explicit_source_override_is_isolated_and_preserves_parser(paper_library, monkeypatch):
    isolated = paper_library / 'Library/FixtureSources'
    paper = isolated / '9702/9702_s23_qp_12.pdf'
    paper.parent.mkdir(parents=True)
    paper.write_bytes(pdf_bytes('fixture'))
    monkeypatch.setattr(mine_mcq, 'PAPERS', isolated)
    assert mine_mcq.paper_sources('9702') == {paper.name: paper}


def test_spec_extractor_main_uses_catalog_alias_resolver_without_legacy_paths(tmp_path, monkeypatch):
    import extract_spec
    requested = []
    monkeypatch.setattr(extract_spec, 'RAW', tmp_path / 'Work/RawSpecs')
    monkeypatch.setattr(extract_spec.library, 'resolve', lambda alias: requested.append(alias) or Path('/catalog') / Path(alias).name)
    monkeypatch.setattr(extract_spec, 'caie', lambda path, code: {'spec': code, 'source': path.name, 'topics': []})
    monkeypatch.setattr(extract_spec, 'ial', lambda path: {'spec': 'IAL-maths', 'source': path.name, 'units': []})
    assert extract_spec.main() == 0
    assert requested == ['sources/specs/9701-2025-2027.pdf', 'sources/specs/9702-2025-2027.pdf',
                         'sources/specs/9701-2028-2030.pdf', 'sources/specs/9702-2028-2030.pdf',
                         'sources/specs/ial-maths-spec.pdf']
    assert len(list((tmp_path / 'Work/RawSpecs').glob('*.json'))) == 5
