"""Closed-total proof on real Library PDFs and disposable adversarial layouts."""
import copy
import importlib.util
import json
from pathlib import Path
import sys

import pymupdf
import pytest

from library_assets import canonical_path, copy_to_vault
from tutorlib.asset_library import AssetLibrary
from tutorlib.prepared_evidence import source_identity

ROOT = Path(__file__).resolve().parents[2]
EXTRACTION = ROOT / 'stem-tutor/extraction'
sys.path.insert(0, str(EXTRACTION))
import prepared_scope as live

CANDIDATE = ROOT / 'Work/Workers/extraction/overnight-20261105-10pct/native-closed-total-profile/candidate/prepared_scope.py'
CASES = [
    ('asset:legacy-98baa6c729123b257c35b83f', 'asset:legacy-8f595dfd75d8544de277c1cd', 'FP1', 1, (2, 3), 8, 5),
    ('asset:legacy-12a0735b54d9242d58ad4ab8', 'asset:legacy-7481731838e5350bc9defd8a', 'S1', 4, (14, 15), 9, 5),
]


def candidate():
    spec = importlib.util.spec_from_file_location('closed_total_candidate', CANDIDATE)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def locate(q, layouts, sources):
    path = EXTRACTION / 'native_closed_totals.py'
    assert path.is_file(), 'native closed-total proof is not implemented'
    spec = importlib.util.spec_from_file_location('native_closed_totals', path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.located_native_closed_totals(q, layouts, sources)


@pytest.fixture(scope='module')
def originals(tmp_path_factory):
    vault = tmp_path_factory.mktemp('closed-total-library')
    copy_to_vault(live.SPEC_PATH, vault)
    assets = sorted({alias for case in CASES for alias in case[:2]})
    for alias in assets:
        copy_to_vault(canonical_path(alias), vault)
    path = vault / 'Library/catalog.json'
    catalog = json.loads(path.read_text())
    for alias in assets:
        key = next(k for k, v in catalog['assets'].items() if v['path'] == canonical_path(alias))
        catalog['assets'][alias[6:]] = catalog['assets'].pop(key)
    path.write_text(json.dumps(catalog))
    return AssetLibrary(vault)


def context(library, case=CASES[0]):
    qp, ms, course, number, qp_pages, ms_page, maximum = case
    sources, layouts = {}, {}
    for role, asset in [('qp', qp), ('ms', ms)]:
        record = library.record(asset)
        with pymupdf.open(stream=library.read(asset), filetype='pdf') as doc:
            sources[role] = {'asset_id': asset, 'sha256': record['sha256'], 'path': canonical_path(asset),
                             'exam': source_identity(canonical_path(asset), role, course),
                             'pages': len(doc), 'inspection_pages': list(range(1, len(doc) + 1))}
            layouts[role] = live._source_layout(doc, role)
    q = {'number': number}
    for role, field, pages in [('qp', 'question_regions', qp_pages), ('ms', 'scheme_regions', (ms_page,))]:
        q[field] = [{'role': role, 'source_id': sources[role]['asset_id'],
                     'source_sha256': sources[role]['sha256'], 'page': page, 'box': [0, 0, 1, 1]}
                    for page in pages]
    return q, layouts, sources


@pytest.mark.parametrize('case', CASES)
def test_real_literal_owns_exact_native_words_and_candidate_fallback(originals, case):
    q, layouts, sources = context(originals, case)
    found = locate(q, layouts, sources)
    assert len(found) == 1
    assert found[0]['label'] == 'Total 5' and found[0]['value'] == case[-1]
    words = layouts['ms'][case[5] - 1]['words']
    tokens = [w for w in words if live._inside(found[0]['region']['box'], w['box'])]
    assert [w['text'] for w in tokens] == ['Total', '5']
    assert candidate()._whole_assessment(q, layouts, sources)['totals']['ms'] == found[0]
    assert locate(q, layouts, sources) == found


@pytest.mark.parametrize('fault', [
    'missing-Question', 'missing-Number', 'missing-Scheme', 'missing-Marks',
    'duplicate-header', 'reordered-headers', 'wrong-header-height', 'wrong-Notes-column',
    'same-total', 'other-total', 'total-word-in-notes', 'wrapped-total', 'moved-total',
    'inline-prose', 'partial-total', 'later-mark', 'later-allocation', 'footer-mark',
    'overlapping-later-mark', 'tiny-inline-mark', 'wrong-question', 'hidden-next-question', 'hidden-next-numbered-part',
    'offset-next-numbered-part', 'unknown-numbered-part', 'ambiguous-part', 'same-number-after-total', 'missing-row',
    'wrong-start', 'extra-start', 'crop', 'continuation', 'wrong-source', 'wrong-hash', 'wrong-role',
])
def test_adversarial_native_changes_hold(originals, fault):
    q, layouts, sources = context(originals)
    page = layouts['ms'][7]
    words = page['words']
    total = next(w for w in words if w['text'] == 'Total')
    index = words.index(total)
    value = words[index + 1]
    header = next(w for w in words if w['text'] == 'Marks')
    row = page['starts'][0]
    def add(text, x, y, width=.03, height=.015):
        words.append({'text': text, 'box': [x, y, x + width, y + height]})
    if fault.startswith('missing-') and fault != 'missing-row':
        words.remove(next(w for w in words if w['text'] == fault[8:]))
    elif fault == 'duplicate-header':
        words.append(copy.deepcopy(header))
    elif fault == 'reordered-headers':
        scheme = next(w for w in words if w['text'] == 'Scheme')
        scheme['box'], header['box'] = header['box'], scheme['box']
    elif fault == 'wrong-header-height':
        header['box'][1:4:2] = [.18, .195]
    elif fault == 'wrong-Notes-column':
        next(w for w in words if w['text'] == 'Notes')['box'] = [.95, .10, .99, .12]
    elif fault in ('same-total', 'other-total'):
        add('Total', .87, .85)
        add('5' if fault == 'same-total' else '6', .92, .85, .01)
    elif fault == 'total-word-in-notes':
        add('Total', .50, .90)
    elif fault == 'wrapped-total':
        value['box'][1] += .025
        value['box'][3] += .025
    elif fault == 'moved-total':
        for word in (total, value):
            word['box'][0] -= .13
            word['box'][2] -= .13
    elif fault == 'inline-prose':
        add('award', .83, total['box'][1])
    elif fault == 'partial-total':
        value['text'] = '5marks'
    elif fault in ('later-mark', 'later-allocation', 'footer-mark', 'overlapping-later-mark'):
        y = .965 if fault == 'footer-mark' else total['box'][3] + .025
        if fault == 'overlapping-later-mark':
            y = total['box'][3] - .001
        add('(1)' if fault == 'later-allocation' else 'M1', header['box'][0], y)
    elif fault == 'tiny-inline-mark':
        add('M1', .94, total['box'][1] + .001, .01, .002)
    elif fault == 'wrong-question':
        q['number'] = 2
    elif fault in ('hidden-next-question', 'hidden-next-numbered-part', 'unknown-numbered-part', 'ambiguous-part', 'same-number-after-total'):
        text = {'hidden-next-question': '2', 'hidden-next-numbered-part': '2(a)(ii)',
                'unknown-numbered-part': '1(foo)', 'ambiguous-part': '(foo)',
                'same-number-after-total': '1(a)'}[fault]
        add(text, row['box'][0], .965)
    elif fault == 'offset-next-numbered-part':
        add('2(a)(ii)', row['box'][0] - .035, .965, .10)
    elif fault == 'missing-row':
        words[:] = [w for w in words if w['box'] != row['box']]
    elif fault == 'wrong-start':
        row['number'] = 2
    elif fault == 'extra-start':
        page['starts'].append(copy.deepcopy(row))
    elif fault == 'crop':
        q['scheme_regions'][0]['box'] = [0, 0, 1, .94]
    elif fault == 'continuation':
        q['scheme_regions'].append({**q['scheme_regions'][0], 'page': 9})
    elif fault == 'wrong-source':
        q['scheme_regions'][0]['source_id'] = sources['qp']['asset_id']
    elif fault == 'wrong-hash':
        q['scheme_regions'][0]['source_sha256'] = '0' * 64
    elif fault == 'wrong-role':
        q['scheme_regions'][0]['role'] = 'qp'
    assert locate(q, layouts, sources) == []


def test_qp_agreement_is_required_and_cannot_supply_the_ms_value(originals):
    q, layouts, sources = context(originals)
    # The MS helper ignores QP words entirely. Only the caller compares maxima.
    layouts['qp'][2]['words'] = [copy.deepcopy(w) for w in layouts['qp'][2]['words']]
    for w in layouts['qp'][2]['words']:
        if w['text'] == '5':
            w['text'] = '6'
    assert locate(q, layouts, sources)[0]['value'] == 5
    with pytest.raises(ValueError, match='maxima differ'):
        candidate()._whole_assessment(q, layouts, sources)


@pytest.mark.parametrize('case', CASES)
def test_disposable_prepare_replay_retains_complete_source_pixels(originals, tmp_path, case):
    p = candidate()
    q, layouts, sources = context(originals, case)
    request = {'course': case[2],
               'sources': {role: {'asset_id': pin['asset_id'], 'sha256': pin['sha256'], 'inspection_pages': pin['inspection_pages']}
                           for role, pin in sources.items()},
               'questions': [{'number': q['number'], 'assessment_mode': p.WHOLE_ASSESSMENT,
                              'question_regions': q['question_regions'], 'scheme_regions': q['scheme_regions'],
                              'parts': [{'part': '', 'label': '', 'question_media_regions': q['question_regions'],
                                         'scheme_media_regions': q['scheme_regions']}]}]}
    import json
    path = tmp_path / 'request.json'
    path.write_text(json.dumps(request))
    output = tmp_path / 'package'
    descriptor = p.prepare_native(path, output, originals, 'a' * 64)
    assert p.verify_native_package(output, originals, 'a' * 64) == descriptor
    for name, media in descriptor['media'].items():
        r = media['region']
        with pymupdf.open(stream=originals.read(sources[r['role']]['asset_id']), filetype='pdf') as doc:
            expected = doc[r['page'] - 1].get_pixmap(dpi=144, alpha=False).tobytes('png')
        assert (output / name).read_bytes() == expected
        assert media['visibility'] == ('private' if r['role'] == 'ms' else 'public')


@pytest.mark.parametrize('count', [1, 2])
def test_existing_positive_and_conflicting_totals_never_enter_fallback(originals, monkeypatch, count):
    import native_closed_totals
    q, layouts, sources = context(originals)
    page = layouts['ms'][7]
    page['words'] = [w for w in page['words'] if not live._part_marker(w)]
    original = live._located_whole_total(q, layouts, sources, 'ms')
    if count == 2:
        copies = [copy.deepcopy(w) for w in page['words'] if live._inside(original['region']['box'], w['box'])]
        for w in copies:
            w['box'][1] += .05
            w['box'][3] += .05
        page['words'].extend(copies)
    def forbidden(*args):
        raise AssertionError('established authority must never enter new proof')
    monkeypatch.setattr(native_closed_totals, 'located_native_closed_totals', forbidden)
    if count == 1:
        assert candidate()._located_whole_total(q, layouts, sources, 'ms') == original
    else:
        with pytest.raises(ValueError, match='unique independent ms'):
            candidate()._located_whole_total(q, layouts, sources, 'ms')


def test_continued_native_page_cannot_be_the_whole_block(originals):
    q, layouts, sources = context(originals)
    layouts['ms'][7]['words'].append({'text': 'continued', 'box': [.2, .14, .3, .16]})
    assert locate(q, layouts, sources) == []
