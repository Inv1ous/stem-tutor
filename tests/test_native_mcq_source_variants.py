"""Exact original source variants qualify availability, never teaching approval."""
import hashlib
import io
import json
from pathlib import Path
import sys

import pymupdf
import pytest
from PIL import Image

from library_assets import copy_to_vault
from tutorlib.asset_library import AssetLibrary, write_asset

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'stem-tutor/extraction'))
import fastpath
import source_practice

MARCH = [f'9701_m{year}_12' for year in range(17, 22)]
REFERENCES = [f'9701_m{year}_12' for year in range(22, 25)]
TARGETS = MARCH + REFERENCES + ['9701_s18_11']
# Frozen before the change, from the complete source-derived native bundle.
UNCHANGED = {
    '9701_s17_11': 'a8766a933a879a6c0a7faf9626fade8ab8ec224afce342e74192cbba390b7de8',
    '9701_s17_12': 'ac640fdfe79a1b02c53d2a0d824b5e32d41ef725dd40f0334952c86ab910c5c3',
    '9701_s17_13': '2843d26195a7cf71558a17b9b5469582bb3ca399b787354ef85e33f9a296338e',
    '9701_s18_12': '977b97bd6b50f6c70e905df5ff625b2f652f1ab62cf8c20c66603e0a29e6053a',
    '9701_s18_13': '6bb138213a73125a228afb10497670e088eef2fb1a41b0e2944cf365b4777d52',
    '9701_w17_11': '5cad0a329dfe86a128dae9d56e7c83bfcb18c0f76beade04480cf323253bac77',
    '9701_w17_12': 'f8876620fb6e2c9ff9cb465e3bb25b0b15820348d36eada051b9da47ff1242c7',
    '9701_w18_11': '74c13803a34cb90af9d8cbeee005093c44039afbe3fa75e4efa409ad9b4fe02f',
    '9701_w18_12': 'fd604619ed546dd697842753e57cccb56b8610af9b1f3a0d59392a289d07ed09',
}


@pytest.fixture(scope='module')
def originals(tmp_path_factory):
    vault = tmp_path_factory.mktemp('native-source-variants') / 'vault'
    vault.mkdir()
    manifest = json.loads((ROOT / 'Work/Preparation/source-acquisition/chem-mcq-originals/registration-manifest-all.json').read_bytes())
    pairs = {}
    for row in manifest['registered']:
        copy_to_vault(row['path'], vault)
        pairs.setdefault(row['paper'], {})[row['role']] = row['reference']
    library = AssetLibrary(vault)
    return vault, pairs, library


def analyse(originals, paper, **overrides):
    _, pairs, library = originals
    refs = pairs[paper]
    raw = {role: overrides.get(role, library.read(ref)) for role, ref in refs.items()}
    return fastpath.analyse_pair(raw['qp'], raw['ms'], paper, refs['qp'], refs['ms'])


@pytest.fixture(scope='module', params=TARGETS)
def prepared(request, originals, tmp_path_factory):
    vault, pairs, _ = originals
    output = tmp_path_factory.mktemp(request.param) / 'preparation'
    bundle = fastpath.prepare(vault, pairs[request.param]['qp'], pairs[request.param]['ms'], output, dpi=72)
    return request.param, output, bundle


@pytest.mark.parametrize('paper', TARGETS)
def test_actual_original_variants_have_complete_page_ownership(originals, paper):
    bundle = analyse(originals, paper)
    assert bundle['status'] == 'prepared_unreviewed'
    assert bundle['exceptions'] == []
    assert [q['official_qid'] for q in bundle['questions']] == [f'{paper}_q{i}' for i in range(1, 41)]
    assert len(bundle['ms_pages']) == bundle['sources']['ms']['pages']
    if paper in REFERENCES:
        assert bundle['qp_pages'][-2:] == [
            {'page': 19, 'status': 'reference', 'question_starts': []},
            {'page': 20, 'status': 'reference', 'question_starts': []}]
        for row in bundle['questions']:
            assert row['context_regions'][:2] == [
                {'source_id': bundle['sources']['qp']['reference'], 'source_sha256': bundle['sources']['qp']['sha256'],
                 'page': page, 'box': [0, 0, 1, 1]} for page in (19, 20)]
            assert row['review_reasons'] == ['independent_visual_and_mapping_review_required'] + (
                ['multiple_pages_require_review'] if len(row['regions']) > 1 else [])
    elif paper == '9701_s18_11':
        assert bundle['ms_pages'][-1] == {'page': 4, 'status': 'blank_furniture', 'rows': 0}
    assert all(row['teaching_approved'] is False for row in bundle['questions'])


def test_actual_variants_replay_through_original_two_key_engines(prepared, originals, monkeypatch):
    paper, output, bundle = prepared
    vault, _, library = originals
    monkeypatch.setattr(source_practice, 'WORKERS', output.parent / 'no-workers')
    replay = source_practice.verify(vault, output)
    assert replay['key_extractors'] == ['pymupdf_spatial', 'pypdf_serialized']
    assert replay['source_verified'] is True
    assert replay['exceptions'] == [] and replay['held'] == []
    assert len(replay['items']) == 40
    assert len(replay['page_proofs']) == sum(s['pages'] for s in bundle['sources'].values())
    assert all(row['mastery_certified'] is False and row['teaching_approved'] is False for row in replay['items'])
    if paper in REFERENCES:
        full, _ = fastpath.render_regions(library.read(bundle['sources']['qp']['reference']),
                                         bundle['questions'][0]['context_regions'][:2], dpi=72)
        for row in replay['items']:
            names = row['context_media'][:2]
            assert [replay['_pixels'][name] for name in names] == full
            assert all(bundle['media'][name]['visibility'] == 'public_question' for name in names)
            assert not set(names) & set(row['mark_scheme_media'])
            assert 'Important values, constants and standards' in row['question_text']
            assert 'Periodic Table' in row['question_text']


@pytest.mark.parametrize('paper,digest', UNCHANGED.items())
def test_accepted_non_target_source_bundles_remain_byte_exact(originals, paper, digest):
    raw = json.dumps(analyse(originals, paper), sort_keys=True, separators=(',', ':')).encode()
    assert hashlib.sha256(raw).hexdigest() == digest


def changed_pdf(raw, page_number, old=None, new=None, kind='text'):
    """All malformed inputs are fresh bytes in the disposable test process."""
    with pymupdf.open(stream=raw, filetype='pdf') as doc:
        page = doc[page_number - 1]
        if old is not None:
            boxes = page.search_for(old)
            assert boxes, (page_number, old)
            for box in boxes:
                page.add_redact_annot(box, fill=(1, 1, 1))
            page.apply_redactions()
            page.insert_text((boxes[0].x0, boxes[0].y1 - 2), new, fontsize=10)
        elif kind == 'text':
            page.insert_text((100, 400), 'unrecognized source data')
        elif kind == 'question':
            page.insert_text((.08 * page.rect.width, .5 * page.rect.height), '40', fontsize=12)
        elif kind == 'key':
            page.insert_text((100, 400), '1       A', fontsize=12)
        elif kind == 'image':
            data = io.BytesIO()
            Image.new('RGB', (20, 20), 'red').save(data, format='PNG')
            page.insert_image(pymupdf.Rect(100, 200, 400, 600), stream=data.getvalue())
        elif kind == 'metadata':
            doc.set_metadata({**doc.metadata, 'subject': 'unreviewed resealed source'})
        return doc.tobytes()


@pytest.mark.parametrize('paper', REFERENCES + ['9701_s18_11'])
@pytest.mark.parametrize('kind', ['metadata', 'text', 'image', 'question', 'key'])
def test_whole_pdf_authority_never_transfers_to_resealed_or_added_source_data(originals, paper, kind):
    _, pairs, library = originals
    role, page = ('qp', 19) if paper in REFERENCES else ('ms', 4)
    altered = changed_pdf(library.read(pairs[paper][role]), page, kind=kind)
    bundle = analyse(originals, paper, **{role: altered})
    assert bundle['status'] == 'needs_review'
    assert bundle['exceptions']
    assert not any(row['status'] in ('reference', 'blank_furniture') for row in bundle[role + '_pages'])
    assert not any(r['box'] == [0, 0, 1, 1] for q in bundle['questions'] for r in q['context_regions'])
    if kind == 'question' and role == 'qp':
        assert any(error['reason'] == 'question_number_sequence' for error in bundle['exceptions'])
    if kind == 'key' and role == 'ms':
        assert any(error['reason'] == 'duplicate_or_conflicting_key' for error in bundle['exceptions'])


@pytest.mark.parametrize('paper', MARCH)
@pytest.mark.parametrize('fault', ['year', 'month', 'course', 'component'])
def test_march_identity_is_required_on_every_actual_ms_page(originals, paper, fault):
    _, pairs, library = originals
    raw = library.read(pairs[paper]['ms'])
    year = '20' + paper.split('_')[1][1:]
    old, new = {'year': (year, '2099'), 'month': ('March', 'May'),
                'course': ('9701', '9702'), 'component': ('9701/12', '9701/11')}[fault]
    with pymupdf.open(stream=raw, filetype='pdf') as doc:
        count = len(doc)
    for page in range(1, count + 1):
        altered = changed_pdf(raw, page, old, new)
        with pytest.raises(ValueError, match='content identity does not match'):
            analyse(originals, paper, ms=altered)


@pytest.mark.parametrize('paper', MARCH)
def test_literal_march_does_not_relax_qp_or_ms_cover_role(originals, paper):
    _, pairs, library = originals
    year = '20' + paper.split('_')[1][1:]
    qp = changed_pdf(library.read(pairs[paper]['qp']), 1, 'February/March ' + year, 'March ' + year)
    with pytest.raises(ValueError, match='qp content identity'):
        analyse(originals, paper, qp=qp)
    ms = changed_pdf(library.read(pairs[paper]['ms']), 1, 'MARK SCHEME', 'QUESTION PAPER')
    with pytest.raises(ValueError, match='ms content identity'):
        analyse(originals, paper, ms=ms)
    with pymupdf.open(stream=library.read(pairs[paper]['ms']), filetype='pdf') as doc:
        with pytest.raises(ValueError, match='qp content identity'):
            fastpath._identity(doc, paper, 'qp')


@pytest.mark.parametrize('fault', ['source', 'page_words', 'answer', 'reference_crop', 'reference_missing', 'private_reference'])
def test_resealed_preparation_cannot_rewrite_source_or_full_public_references(originals, tmp_path, monkeypatch, fault):
    vault, pairs, _ = originals
    paper = '9701_m24_12'
    output = tmp_path / 'preparation'
    bundle = fastpath.prepare(vault, pairs[paper]['qp'], pairs[paper]['ms'], output, dpi=72)
    if fault == 'source': bundle['sources']['qp']['sha256'] = '0' * 64
    elif fault == 'page_words': bundle['qp_pages'][-2]['status'] = 'questions'
    elif fault == 'answer': bundle['questions'][0]['answer'] = 'A' if bundle['questions'][0]['answer'] != 'A' else 'B'
    elif fault == 'reference_crop': bundle['questions'][0]['context_regions'][0]['box'][3] = .9
    elif fault == 'reference_missing': bundle['questions'][0]['context_regions'].pop(0)
    else:
        name = bundle['questions'][0]['context_media'][0]
        bundle['media'][name]['visibility'] = 'private_answer'
    raw = json.dumps(bundle).encode()
    (output / 'bundle.json').write_bytes(raw)
    (output / 'COMPLETE').write_text(hashlib.sha256(raw).hexdigest())
    monkeypatch.setattr(source_practice, 'WORKERS', tmp_path / 'no-workers')
    with pytest.raises(ValueError):
        source_practice.verify(vault, output)


@pytest.mark.parametrize('month', ['April/March', 'April / March', 'NotMarch'])
@pytest.mark.parametrize('paper', MARCH)
def test_march_ms_grammar_rejects_other_prefixes(originals, paper, month):
    _, pairs, library = originals
    year = '20' + paper.split('_')[1][1:]
    altered = changed_pdf(library.read(pairs[paper]['ms']), 2, 'March ' + year, month + ' ' + year)
    with pytest.raises(ValueError, match='ms page 2 content identity'):
        analyse(originals, paper, ms=altered)


@pytest.mark.parametrize('paper,role,page,kind', [
    ('9701_m24_12', 'qp', 19, 'metadata'),
    ('9701_m24_12', 'qp', 19, 'text'),
    ('9701_m24_12', 'qp', 20, 'image'),
    ('9701_m24_12', 'qp', 19, 'question'),
    ('9701_s18_11', 'ms', 4, 'metadata'),
    ('9701_s18_11', 'ms', 4, 'text'),
    ('9701_s18_11', 'ms', 4, 'image'),
])
def test_unknown_resealed_source_authority_stays_held_in_original_replay(
        originals, tmp_path, monkeypatch, paper, role, page, kind):
    _, pairs, library = originals
    vault = tmp_path / 'vault'
    vault.mkdir()
    refs = {}
    for source_role, reference in pairs[paper].items():
        path = library.record(reference)['path']
        if source_role == role:
            altered = changed_pdf(library.read(reference), page, kind=kind)
            # Synthetic invalid source bytes exist only in this disposable vault.
            refs[source_role] = write_asset(vault, 'Library/TestInputs/' + Path(path).name, altered)
        else:
            copy_to_vault(path, vault)
            refs[source_role] = reference
    output = tmp_path / 'preparation'
    fastpath.prepare(vault, refs['qp'], refs['ms'], output, dpi=72)
    monkeypatch.setattr(source_practice, 'WORKERS', tmp_path / 'no-workers')
    replay = source_practice.verify(vault, output)
    assert replay['items'] == [] and len(replay['held']) == 40
    assert all(row['reasons'] for row in replay['held'])
    assert replay['exceptions']
