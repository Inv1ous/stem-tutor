"""Real immutable PDF witnesses; synthetic mutations stay in disposable copies."""
import copy
import hashlib
import importlib
import json
from pathlib import Path
import sys

import pymupdf
import pytest

from library_assets import canonical_path, copy_to_vault
from tutorlib.asset_library import AssetLibrary
from tutorlib.prepared_evidence import canonical_qid, source_identity

sys.path.insert(0, str(Path(__file__).parents[1] / 'extraction'))
import prepared_scope as p

# Expected literals and scopes are independently inspected original PDF cells.
CASES = [('asset:asset-c604179c435ea13eb5f838a4',
  'asset:asset-ee7cb73bf845153e8be0fcbb',
  'FP1',
  4,
  (10, 11, 12, 13),
  (9,),
  '9',
  9,
  9),
 ('asset:asset-c604179c435ea13eb5f838a4',
  'asset:asset-ee7cb73bf845153e8be0fcbb',
  'FP1',
  8,
  (26, 27, 28, 29),
  (13,),
  '12',
  12,
  13),
 ('asset:legacy-b4ded3106fd9a4b7b49c3fc4',
  'asset:legacy-9f8ffeb2f347cef85608c2ab',
  'FP1',
  1,
  (2, 3),
  (7,),
  'Total 6',
  6,
  7),
 ('asset:legacy-b4ded3106fd9a4b7b49c3fc4',
  'asset:legacy-9f8ffeb2f347cef85608c2ab',
  'FP1',
  9,
  (24, 25, 26, 27, 28),
  (19, 20, 21, 22, 23),
  'Total 13',
  13,
  21),
 ('asset:asset-4e5a5295cd30d9ed1290f5e9',
  'asset:asset-6e7b518f2aa55cec027e6ecd',
  'FP2',
  7,
  (20, 21, 22, 23),
  (14, 15, 16),
  'Total 15',
  15,
  16),
 ('asset:asset-4e5a5295cd30d9ed1290f5e9',
  'asset:asset-6e7b518f2aa55cec027e6ecd',
  'FP2',
  8,
  (24, 25, 26, 27, 28),
  (17, 18),
  'Total 12',
  12,
  18),
 ('asset:asset-bd5e073ee4b4188f8a243860',
  'asset:asset-4d1b0d5cc25e1285f7ed51a6',
  'FP2',
  3,
  (6, 7, 8, 9),
  (9,),
  'Total 8',
  8,
  9),
 ('asset:asset-bd5e073ee4b4188f8a243860',
  'asset:asset-4d1b0d5cc25e1285f7ed51a6',
  'FP2',
  10,
  (32, 33, 34, 35, 36),
  (20, 21, 22),
  'Total 9',
  9,
  20),
 ('asset:asset-0d6a4c24b6d879d3d3170a8f',
  'asset:asset-59f19191b2717f09767ede44',
  'FP3',
  1,
  (2, 3),
  (7, 8),
  'Total 6',
  6,
  7),
 ('asset:asset-0d6a4c24b6d879d3d3170a8f',
  'asset:asset-59f19191b2717f09767ede44',
  'FP3',
  9,
  (28, 29, 30, 31, 32),
  (25, 26, 27, 28, 29, 30),
  'Total 12',
  12,
  27),
 ('asset:legacy-588c402174d45ced558dd2bb',
  'asset:legacy-4ce94e02c3f15bd9c63f9eb9',
  'M1',
  1,
  (2, 3),
  (7,),
  '(5)',
  5,
  7),
 ('asset:legacy-588c402174d45ced558dd2bb',
  'asset:legacy-4ce94e02c3f15bd9c63f9eb9',
  'M1',
  8,
  (24, 25, 26, 27, 28),
  (14, 15),
  '(16)',
  16,
  14),
 ('asset:legacy-a5bea009ac2587c695284c32',
  'asset:legacy-b8eb86f28682d04dc11b7821',
  'P1',
  3,
  (6, 7),
  (11, 12),
  'Total 6',
  6,
  12),
 ('asset:legacy-a5bea009ac2587c695284c32',
  'asset:legacy-b8eb86f28682d04dc11b7821',
  'P1',
  11,
  (30, 31, 32),
  (24, 25, 26),
  'Total 6',
  6,
  24),
 ('asset:legacy-9fb9fbf6f2a55cf7310f0a9c',
  'asset:legacy-1509dacca820b65b180258bd',
  'P2',
  6,
  (12, 13, 14, 15),
  (13, 14),
  '(8 marks)',
  8,
  13),
 ('asset:legacy-9fb9fbf6f2a55cf7310f0a9c',
  'asset:legacy-1509dacca820b65b180258bd',
  'P2',
  10,
  (26, 27, 28),
  (19, 20),
  '(10 marks)',
  10,
  19),
 ('asset:legacy-67e546fca76795bb30240ddd',
  'asset:legacy-8e6575af321ef6ba74e054b8',
  'P3',
  1,
  (2, 3, 4, 5),
  (7, 8),
  'Total 8',
  8,
  8),
 ('asset:legacy-67e546fca76795bb30240ddd',
  'asset:legacy-8e6575af321ef6ba74e054b8',
  'P3',
  10,
  (30, 31, 32),
  (28, 29, 30, 31, 32),
  'Total 10',
  10,
  30),
 ('asset:legacy-c91e874f11b9ba037b608c70',
  'asset:legacy-d0a7a0e10e4edc6553f7ff5b',
  'P4',
  1,
  (2, 3, 4, 5),
  (7, 8),
  'Total 9',
  9,
  7),
 ('asset:legacy-c91e874f11b9ba037b608c70',
  'asset:legacy-d0a7a0e10e4edc6553f7ff5b',
  'P4',
  8,
  (28, 29, 30, 31, 32),
  (20, 21, 22, 23),
  'Total 12',
  12,
  20),
 ('asset:legacy-04aaf0841d0d6ab25481fa5e',
  'asset:legacy-14762d0a69adc80a47698145',
  'S1',
  1,
  (2, 3),
  (6,),
  'Total 9',
  9,
  6),
 ('asset:legacy-04aaf0841d0d6ab25481fa5e',
  'asset:legacy-14762d0a69adc80a47698145',
  'S1',
  7,
  (20, 21, 22, 23, 24),
  (12, 13),
  'Total 13',
  13,
  12),
 ('asset:legacy-21ec9972897bf8bf1ded353d',
  'asset:legacy-6ebd40e121b2ba7666c543ae',
  'S2',
  1,
  (2, 3),
  (6,),
  '[11 marks]',
  11,
  6),
 ('asset:legacy-21ec9972897bf8bf1ded353d',
  'asset:legacy-6ebd40e121b2ba7666c543ae',
  'S2',
  4,
  (10, 11, 12, 13),
  (9,),
  '[13 marks]',
  13,
  9)]

# Additional physically inspected cells in the same source pairs.
CASES += [('asset:legacy-b4ded3106fd9a4b7b49c3fc4',
  'asset:legacy-9f8ffeb2f347cef85608c2ab',
  'FP1',
  2,
  (4, 5, 6, 7),
  (8, 9),
  'Total 9',
  9,
  9),
 ('asset:legacy-b4ded3106fd9a4b7b49c3fc4',
  'asset:legacy-9f8ffeb2f347cef85608c2ab',
  'FP1',
  3,
  (8, 9),
  (10,),
  'Total 7',
  7,
  10),
 ('asset:legacy-b4ded3106fd9a4b7b49c3fc4',
  'asset:legacy-9f8ffeb2f347cef85608c2ab',
  'FP1',
  4,
  (10, 11),
  (11, 12),
  'Total 8',
  8,
  12),
 ('asset:legacy-b4ded3106fd9a4b7b49c3fc4',
  'asset:legacy-9f8ffeb2f347cef85608c2ab',
  'FP1',
  5,
  (12, 13, 14, 15),
  (13, 14),
  'Total 9',
  9,
  14),
 ('asset:legacy-b4ded3106fd9a4b7b49c3fc4',
  'asset:legacy-9f8ffeb2f347cef85608c2ab',
  'FP1',
  6,
  (16, 17, 18, 19),
  (15,),
  'Total 9',
  9,
  15),
 ('asset:legacy-b4ded3106fd9a4b7b49c3fc4',
  'asset:legacy-9f8ffeb2f347cef85608c2ab',
  'FP1',
  7,
  (20, 21),
  (16,),
  'Total 8',
  8,
  16),
 ('asset:legacy-588c402174d45ced558dd2bb',
  'asset:legacy-4ce94e02c3f15bd9c63f9eb9',
  'M1',
  2,
  (4, 5),
  (8,),
  '(6)',
  6,
  8),
 ('asset:legacy-588c402174d45ced558dd2bb',
  'asset:legacy-4ce94e02c3f15bd9c63f9eb9',
  'M1',
  3,
  (6, 7, 8, 9),
  (9,),
  '(13)',
  13,
  9),
 ('asset:legacy-588c402174d45ced558dd2bb',
  'asset:legacy-4ce94e02c3f15bd9c63f9eb9',
  'M1',
  4,
  (10, 11, 12, 13),
  (10,),
  '(8)',
  8,
  10),
 ('asset:legacy-588c402174d45ced558dd2bb',
  'asset:legacy-4ce94e02c3f15bd9c63f9eb9',
  'M1',
  5,
  (14, 15),
  (11,),
  '(6)',
  6,
  11),
 ('asset:legacy-588c402174d45ced558dd2bb',
  'asset:legacy-4ce94e02c3f15bd9c63f9eb9',
  'M1',
  6,
  (16, 17, 18, 19),
  (12,),
  '(9)',
  9,
  12),
 ('asset:legacy-588c402174d45ced558dd2bb',
  'asset:legacy-4ce94e02c3f15bd9c63f9eb9',
  'M1',
  7,
  (20, 21, 22, 23),
  (13,),
  '(12)',
  12,
  13),
 ('asset:legacy-a5bea009ac2587c695284c32',
  'asset:legacy-b8eb86f28682d04dc11b7821',
  'P1',
  4,
  (8, 9),
  (13,),
  'Total 6',
  6,
  13),
 ('asset:legacy-a5bea009ac2587c695284c32',
  'asset:legacy-b8eb86f28682d04dc11b7821',
  'P1',
  5,
  (10, 11, 12, 13),
  (14,),
  'Total 7',
  7,
  14),
 ('asset:legacy-a5bea009ac2587c695284c32',
  'asset:legacy-b8eb86f28682d04dc11b7821',
  'P1',
  8,
  (20, 21),
  (18, 19),
  'Total 7',
  7,
  18),
 ('asset:legacy-a5bea009ac2587c695284c32',
  'asset:legacy-b8eb86f28682d04dc11b7821',
  'P1',
  9,
  (22, 23, 24, 25),
  (20, 21),
  'Total 9',
  9,
  20),
 ('asset:legacy-a5bea009ac2587c695284c32',
  'asset:legacy-b8eb86f28682d04dc11b7821',
  'P1',
  10,
  (26, 27, 28, 29),
  (22, 23),
  'Total 10',
  10,
  22),
 ('asset:legacy-9fb9fbf6f2a55cf7310f0a9c',
  'asset:legacy-1509dacca820b65b180258bd',
  'P2',
  9,
  (22, 23, 24, 25),
  (18,),
  '(7 marks)',
  7,
  18),
 ('asset:legacy-67e546fca76795bb30240ddd',
  'asset:legacy-8e6575af321ef6ba74e054b8',
  'P3',
  2,
  (6, 7),
  (9,),
  'Total 7',
  7,
  9),
 ('asset:legacy-67e546fca76795bb30240ddd',
  'asset:legacy-8e6575af321ef6ba74e054b8',
  'P3',
  3,
  (8, 9),
  (10, 11, 12),
  'Total 5',
  5,
  11),
 ('asset:legacy-67e546fca76795bb30240ddd',
  'asset:legacy-8e6575af321ef6ba74e054b8',
  'P3',
  4,
  (10, 11),
  (13, 14),
  'Total 5',
  5,
  14),
 ('asset:legacy-67e546fca76795bb30240ddd',
  'asset:legacy-8e6575af321ef6ba74e054b8',
  'P3',
  5,
  (12, 13),
  (15,),
  'Total 4',
  4,
  15),
 ('asset:legacy-67e546fca76795bb30240ddd',
  'asset:legacy-8e6575af321ef6ba74e054b8',
  'P3',
  7,
  (18, 19, 20, 21),
  (18, 19),
  'Total 9',
  9,
  19),
 ('asset:legacy-67e546fca76795bb30240ddd',
  'asset:legacy-8e6575af321ef6ba74e054b8',
  'P3',
  8,
  (22, 23, 24, 25),
  (20, 21, 22),
  'Total 8',
  8,
  22),
 ('asset:legacy-67e546fca76795bb30240ddd',
  'asset:legacy-8e6575af321ef6ba74e054b8',
  'P3',
  9,
  (26, 27, 28, 29),
  (23, 24, 25, 26, 27),
  'Total 11',
  11,
  26),
 ('asset:legacy-c91e874f11b9ba037b608c70',
  'asset:legacy-d0a7a0e10e4edc6553f7ff5b',
  'P4',
  2,
  (6, 7, 8, 9),
  (9, 10),
  'Total 10',
  10,
  9),
 ('asset:legacy-c91e874f11b9ba037b608c70',
  'asset:legacy-d0a7a0e10e4edc6553f7ff5b',
  'P4',
  3,
  (10, 11, 12, 13),
  (11, 12),
  'Total 11',
  11,
  11),
 ('asset:legacy-c91e874f11b9ba037b608c70',
  'asset:legacy-d0a7a0e10e4edc6553f7ff5b',
  'P4',
  4,
  (14, 15, 16, 17),
  (13, 14),
  'Total 10',
  10,
  13),
 ('asset:legacy-c91e874f11b9ba037b608c70',
  'asset:legacy-d0a7a0e10e4edc6553f7ff5b',
  'P4',
  5,
  (18, 19, 20, 21),
  (15, 16),
  'Total 10',
  10,
  15),
 ('asset:legacy-04aaf0841d0d6ab25481fa5e',
  'asset:legacy-14762d0a69adc80a47698145',
  'S1',
  2,
  (4, 5),
  (7,),
  'Total 7',
  7,
  7),
 ('asset:legacy-04aaf0841d0d6ab25481fa5e',
  'asset:legacy-14762d0a69adc80a47698145',
  'S1',
  3,
  (6, 7, 8, 9),
  (8,),
  'Total 14',
  14,
  8),
 ('asset:legacy-04aaf0841d0d6ab25481fa5e',
  'asset:legacy-14762d0a69adc80a47698145',
  'S1',
  4,
  (10, 11),
  (9,),
  'Total 4',
  4,
  9),
 ('asset:legacy-21ec9972897bf8bf1ded353d',
  'asset:legacy-6ebd40e121b2ba7666c543ae',
  'S2',
  2,
  (4, 5),
  (7,),
  '[4 marks]',
  4,
  7),
 ('asset:legacy-21ec9972897bf8bf1ded353d',
  'asset:legacy-6ebd40e121b2ba7666c543ae',
  'S2',
  3,
  (6, 7, 8, 9),
  (8,),
  '[9 marks]',
  9,
  8),
 ('asset:asset-c604179c435ea13eb5f838a4',
  'asset:asset-ee7cb73bf845153e8be0fcbb',
  'FP1',
  5,
  (14, 15, 16, 17),
  (10,),
  '8',
  8,
  10),
 ('asset:asset-c604179c435ea13eb5f838a4',
  'asset:asset-ee7cb73bf845153e8be0fcbb',
  'FP1',
  6,
  (18, 19, 20, 21),
  (11,),
  '8',
  8,
  11),
 ('asset:asset-bd5e073ee4b4188f8a243860',
  'asset:asset-4d1b0d5cc25e1285f7ed51a6',
  'FP2',
  4,
  (10, 11),
  (10, 11),
  'Total 9',
  9,
  10),
 ('asset:asset-bd5e073ee4b4188f8a243860',
  'asset:asset-4d1b0d5cc25e1285f7ed51a6',
  'FP2',
  7,
  (20, 21, 22, 23),
  (15,),
  'Total 7',
  7,
  15),
 ('asset:asset-bd5e073ee4b4188f8a243860',
  'asset:asset-4d1b0d5cc25e1285f7ed51a6',
  'FP2',
  8,
  (24, 25, 26, 27),
  (16, 17),
  'Total 10',
  10,
  16),
 ('asset:asset-0d6a4c24b6d879d3d3170a8f',
  'asset:asset-59f19191b2717f09767ede44',
  'FP3',
  2,
  (4, 5),
  (9, 10),
  'Total 7',
  7,
  9),
 ('asset:asset-0d6a4c24b6d879d3d3170a8f',
  'asset:asset-59f19191b2717f09767ede44',
  'FP3',
  3,
  (6, 7, 8, 9),
  (11, 12),
  'Total 10',
  10,
  11),
 ('asset:asset-0d6a4c24b6d879d3d3170a8f',
  'asset:asset-59f19191b2717f09767ede44',
  'FP3',
  4,
  (10, 11),
  (13, 14),
  'Total 5',
  5,
  13),
 ('asset:asset-0d6a4c24b6d879d3d3170a8f',
  'asset:asset-59f19191b2717f09767ede44',
  'FP3',
  5,
  (12, 13, 14, 15),
  (15, 16),
  'Total 9',
  9,
  15),
 ('asset:asset-0d6a4c24b6d879d3d3170a8f',
  'asset:asset-59f19191b2717f09767ede44',
  'FP3',
  6,
  (16, 17, 18, 19),
  (17,),
  'Total 7',
  7,
  17),
 ('asset:asset-0d6a4c24b6d879d3d3170a8f',
  'asset:asset-59f19191b2717f09767ede44',
  'FP3',
  7,
  (20, 21, 22, 23),
  (18, 19, 20),
  'Total 9',
  9,
  18),
 ('asset:asset-0d6a4c24b6d879d3d3170a8f',
  'asset:asset-59f19191b2717f09767ede44',
  'FP3',
  8,
  (24, 25, 26, 27),
  (21, 22, 23, 24),
  'Total 10',
  10,
  23)]


@pytest.fixture(scope='module')
def originals(tmp_path_factory):
    vault = tmp_path_factory.mktemp('native-ms-maximum')
    assets = sorted({a for case in CASES for a in case[:2]})
    for asset in assets:
        copy_to_vault(canonical_path(asset), vault)
    catalog_path = vault / 'Library/catalog.json'
    catalog = json.loads(catalog_path.read_text())
    for asset in assets:
        key = next(k for k, v in catalog['assets'].items() if v['path'] == canonical_path(asset))
        catalog['assets'][asset[6:]] = catalog['assets'].pop(key)
    catalog_path.write_text(json.dumps(catalog))
    lib = AssetLibrary(vault)
    data = {}
    for qp, ms, course, *_ in CASES:
        if (qp, ms) in data:
            continue
        sources, docs, layouts = {}, {}, {}
        for role, asset in [('qp', qp), ('ms', ms)]:
            record = lib.record(asset)
            raw = lib.read(asset)
            docs[role] = pymupdf.open(stream=raw, filetype='pdf')
            sources[role] = {'asset_id': asset, 'sha256': hashlib.sha256(raw).hexdigest(),
                'path': record['path'], 'exam': source_identity(record['path'], role, course),
                'pages': len(docs[role]), 'inspection_pages': list(range(1, len(docs[role])+1))}
            layouts[role] = p._source_layout(docs[role], role)
        covers = p._paired_covers(docs['qp'], docs['ms'], sources['qp']['exam'], sources['ms']['exam'])
        for role in sources:
            sources[role]['cover'] = covers[role]
            sources[role]['issues'] = p._source_issues(docs[role], sources[role]['inspection_pages'], sources[role]['exam'])
            assert sources[role]['issues'] == []
        data[(qp, ms)] = sources, docs, layouts
    yield data
    for _, docs, _ in data.values():
        for doc in docs.values():
            doc.close()


def question(case, sources):
    _, _, _, number, qp_pages, ms_pages, *_ = case
    def regions(role, pages):
        return [{'role': role, 'source_id': sources[role]['asset_id'],
            'source_sha256': sources[role]['sha256'], 'page': page, 'box': [0, 0, 1, 1]} for page in pages]
    return {'number': number, 'question_regions': regions('qp', qp_pages),
            'scheme_regions': regions('ms', ms_pages)}


@pytest.mark.parametrize('case', CASES, ids=[f'{c[2]}-{c[3]}-{c[0][-6:]}' for c in CASES])
def test_original_literal_maximum_passes_complete_whole_sequence(originals, case):
    sources, docs, layouts = originals[tuple(case[:2])]
    q = question(case, sources)
    scope = p._whole_question_scope(q, layouts, sources)
    whole = p._whole_assessment(q, layouts, sources)
    maximum = whole['totals']['ms']
    assert (maximum['label'], maximum['value'], maximum['region']['page']) == case[-3:]
    assert maximum['value'] == whole['totals']['qp']['value']
    assert p._region_text(docs['ms'], [maximum['region']]) == maximum['label']
    q['assessment_mode'] = p.WHOLE_ASSESSMENT
    q['parts'] = [{'part': '', 'question_media_regions': scope['qp'], 'scheme_media_regions': scope['ms']}]
    witness = p._question_witness(q, docs, sources, scope)
    assert witness
    from tutorlib.prepared_evidence import validate_whole_question
    q['witness'] = witness
    q['whole_assessment'] = whole
    q['parts'][0]['scheme_media'] = ['test-only-disposable-media']
    validate_whole_question(q, sources)
    forged = copy.deepcopy(q)
    forged['whole_assessment']['totals']['ms']['value'] += 1
    with pytest.raises(ValueError, match='maximum differs'):
        validate_whole_question(forged, sources)


@pytest.mark.parametrize('literal,value', [('(5)', 5), ('(16)', 16)])
def test_exact_parenthesized_ms_literal_has_neutral_positive_syntax_only(literal, value):
    from tutorlib.prepared_evidence import _whole_total
    assert _whole_total(literal, 'ms', 1) == value
    with pytest.raises(ValueError):
        _whole_total(literal, 'qp', 1)


def locate(q, layouts, sources):
    return importlib.import_module('native_ms_maximum_witnesses').located_native_ms_maxima(q, layouts, sources)


@pytest.mark.parametrize('case', CASES)
@pytest.mark.parametrize('fault', ['literal', 'box', 'body', 'duplicate-total'])
def test_native_word_mutations_cannot_reuse_registered_authority(originals, case, fault):
    sources, _, layouts = originals[tuple(case[:2])]
    q = question(case, sources)
    changed = copy.deepcopy(layouts)
    maximum = locate(q, layouts, sources)[0]
    page = changed['ms'][maximum['region']['page']-1]
    box = maximum['region']['box']
    token = next(w for w in page['words'] if box[0] <= w['box'][0] and box[1] <= w['box'][1]
                 and w['box'][2] <= box[2] and w['box'][3] <= box[3])
    if fault == 'literal':
        token['text'] = '75'
    elif fault == 'box':
        token['box'][0] += .00001
    elif fault == 'body':
        page['words'][0]['text'] += ' altered'
    else:
        page['words'].append(copy.deepcopy(token))
    assert locate(q, changed, sources) == []


@pytest.mark.parametrize('role', ['qp', 'ms'])
@pytest.mark.parametrize('fault', ['source-sha', 'source-id', 'source-path', 'source-pages', 'source-exam',
    'region-sha', 'region-id', 'region-role', 'clipped-region', 'missing-region', 'extra-region', 'wrong-page'])
def test_source_pair_and_full_scope_are_exact_authority(originals, role, fault):
    case = CASES[3]  # All continuation pages, alternatives, paper total and footer.
    sources, _, layouts = originals[tuple(case[:2])]
    sources = copy.deepcopy(sources)
    q = question(case, sources)
    regions = q['question_regions' if role == 'qp' else 'scheme_regions']
    if fault == 'source-sha': sources[role]['sha256'] = '0' * 64
    elif fault == 'source-id': sources[role]['asset_id'] += '-unknown'
    elif fault == 'source-path': sources[role]['path'] = sources['ms' if role == 'qp' else 'qp']['path']
    elif fault == 'source-pages': sources[role]['pages'] -= 1
    elif fault == 'source-exam': sources[role]['exam']['session'] = '2024-01'
    elif fault == 'region-sha': regions[0]['source_sha256'] = '0' * 64
    elif fault == 'region-id': regions[0]['source_id'] += '-unknown'
    elif fault == 'region-role': regions[0]['role'] = 'reference'
    elif fault == 'clipped-region': regions[0]['box'][3] = .9
    elif fault == 'missing-region': regions.pop()
    elif fault == 'extra-region': regions.append(copy.deepcopy(regions[-1]))
    elif fault == 'wrong-page': regions[-1]['page'] += 1
    assert locate(q, layouts, sources) == []


@pytest.mark.parametrize('fault', ['number', 'unknown-qid', 'missing-private-page', 'extra-alternative', 'wrong-start', 'text-only'])
def test_unknown_question_or_modified_complete_private_layout_stays_held(originals, fault):
    case = CASES[9]  # Wrapped Total 12, repeated alternatives, following notes/diagram.
    sources, _, layouts = originals[tuple(case[:2])]
    q = question(case, sources)
    layouts = copy.deepcopy(layouts)
    if fault == 'number': q['number'] += 1
    elif fault == 'unknown-qid': q['qid'] = 'not-the-original-question'
    elif fault == 'missing-private-page': layouts['ms'].pop(case[5][-2]-1)
    elif fault == 'extra-alternative':
        page = layouts['ms'][case[5][1]-1]
        page['words'].extend(copy.deepcopy(page['words']))
    elif fault == 'wrong-start': layouts['ms'][case[5][0]-1]['starts'][0]['number'] += 1
    elif fault == 'text-only': layouts['ms'][case[5][0]-1]['text'] += ' forged'
    assert locate(q, layouts, sources) == []


def test_qp_maximum_never_supplies_the_ms_value_and_conflict_stays_held(originals):
    case = CASES[10]  # M1 printed (5).
    sources, _, layouts = originals[tuple(case[:2])]
    q = question(case, sources)
    layouts = copy.deepcopy(layouts)
    qp_total = p._located_whole_total(q, layouts, sources, 'qp')
    page = layouts['qp'][qp_total['region']['page']-1]
    box = qp_total['region']['box']
    word = next(w for w in page['words'] if w['text'] == '5' and box[0] <= w['box'][0]
                and box[1] <= w['box'][1] and w['box'][2] <= box[2] and w['box'][3] <= box[3])
    word['text'] = '6'
    assert locate(q, layouts, sources)[0]['value'] == 5
    with pytest.raises(p.PendingEvidence, match='maxima differ'):
        p._whole_assessment(q, layouts, sources)


def test_parenthesized_parts_without_registered_whole_authority_remain_held(originals):
    case = CASES[10]
    sources, _, layouts = originals[tuple(case[:2])]
    q = question(case, sources)
    sources = copy.deepcopy(sources)
    sources['ms']['sha256'] = '1' * 64
    with pytest.raises(p.PendingEvidence, match='unique independent ms'):
        p._located_whole_total(q, layouts, sources, 'ms')
    # A part-only native page with a valid pair still fails the body pin.
    changed = copy.deepcopy(layouts)
    page = changed['ms'][case[-1]-1]
    page['words'] = [w for w in page['words'] if w['text'] != '(5)']
    with pytest.raises(p.PendingEvidence, match='unique independent ms'):
        p._located_whole_total(q, changed, originals[tuple(case[:2])][0], 'ms')


@pytest.mark.parametrize('count', [1, 2])
def test_existing_positive_or_conflicting_candidates_never_enter_new_fallback(originals, monkeypatch, count):
    case = CASES[6]  # Original Total 8; Notes overlap was the original hold.
    sources, _, layouts = originals[tuple(case[:2])]
    q = question(case, sources)
    changed = copy.deepcopy(layouts)
    page = changed['ms'][case[-1]-1]
    page['words'] = [w for w in page['words'] if w['text'] not in ('Notes', 'Notes:')]
    if count == 2:
        total = p._located_whole_total(q, changed, sources, 'ms')
        box = total['region']['box']
        duplicate = copy.deepcopy([w for w in page['words'] if box[0] <= w['box'][0]
            and box[1] <= w['box'][1] and w['box'][2] <= box[2] and w['box'][3] <= box[3]])
        for word in duplicate:
            word['box'][1] += .025
            word['box'][3] += .025
        page['words'].extend(duplicate)
    def forbidden(*args):
        raise AssertionError('fallback must not override any established candidate')
    monkeypatch.setattr(importlib.import_module('native_ms_maximum_witnesses'), 'located_native_ms_maxima', forbidden)
    if count == 1:
        assert p._located_whole_total(q, changed, sources, 'ms')['label'] == 'Total 8'
    else:
        with pytest.raises(p.PendingEvidence, match='unique independent ms'):
            p._located_whole_total(q, changed, sources, 'ms')


HELD_CASES = [('asset:legacy-a5bea009ac2587c695284c32',
  'asset:legacy-b8eb86f28682d04dc11b7821',
  'P1',
  6,
  (14, 15, 16, 17),
  (15, 16, 17)),
 ('asset:legacy-67e546fca76795bb30240ddd',
  'asset:legacy-8e6575af321ef6ba74e054b8',
  'P3',
  6,
  (14, 15, 16, 17),
  (16, 17)),
 ('asset:legacy-04aaf0841d0d6ab25481fa5e',
  'asset:legacy-14762d0a69adc80a47698145',
  'S1',
  5,
  (12, 13, 14, 15),
  (10, 11))]


@pytest.mark.parametrize('case', HELD_CASES)
def test_actual_merged_scopes_and_absent_whole_total_remain_held(originals, case):
    sources, _, layouts = originals[tuple(case[:2])]
    q = question(case, sources)
    # Existing scope recognition alone is insufficient to bless either total.
    p._whole_question_scope(q, layouts, sources)
    assert locate(q, layouts, sources) == []
    with pytest.raises(p.PendingEvidence, match='unique independent ms'):
        p._whole_assessment(q, layouts, sources)


@pytest.mark.parametrize('literal', ['(0)', '(-5)', '(05)', '(5.0)', '(5) prose', '[5]', 'M1A1'])
def test_neutral_parenthesized_grammar_does_not_expand_other_ms_syntax(literal):
    from tutorlib.prepared_evidence import _whole_total
    with pytest.raises(ValueError):
        _whole_total(literal, 'ms', 1)


def test_existing_additional_positive_proof_never_enters_new_fallback(monkeypatch):
    from test_native_ms_whole_totals import table
    def forbidden(*args):
        raise AssertionError('source profile must not replace an established additional proof')
    monkeypatch.setattr(importlib.import_module('native_ms_maximum_witnesses'), 'located_native_ms_maxima', forbidden)
    with table(total='[6 marks]') as doc:
        q = {'number': 1, 'scheme_regions': [{'role': 'ms', 'page': 1, 'box': [0, 0, 1, 1]}]}
        result = p._located_whole_total(q, {'ms': p._source_layout(doc, 'ms')}, {}, 'ms')
        assert (result['label'], result['value']) == ('[6 marks]', 6)
