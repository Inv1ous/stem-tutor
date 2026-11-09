"""Source-question tagging, image cleaning and migration run on disposable vaults only."""
import hashlib
import io
import json
from pathlib import Path
import sys

import numpy as np
import pytest
from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'build'))
import clean_question_images as cleaner
import migrate_source_questions as migrate
import source_topics as topics
from tutorlib.asset_library import AssetLibrary, write_asset
from tutorlib.source_questions import SourceQuestions

GRAPH = {'spec': 'P1', 'subtopics': [{'id': 'P1-1', 'title': 'Algebra'}, {'id': 'P1-4', 'title': 'Differentiation'}],
         'kcs': [
             {'id': 'P1-1.2', 'subtopic': 'P1-1', 'title': 'Manipulating surds', 'statement': 'Use and manipulation of surds.',
              'glossary': ['surd', 'rationalise the denominator'], 'guidance': 'rationalise denominators of surds'},
             {'id': 'P1-4.2', 'subtopic': 'P1-4', 'title': 'Differentiating powers of x',
              'statement': 'Differentiate x to the power n, derivative of polynomials.',
              'glossary': ['differentiate', 'derivative', 'gradient function'], 'guidance': 'find dy/dx'}]}


def png(array):
    buffer = io.BytesIO()
    Image.fromarray(array).save(buffer, format='PNG')
    return buffer.getvalue()


def page(kind):
    """1191x1684 answer-page lookalike: frame, marks column rule, ruled lines, optional content."""
    a = np.full((1684, 1191), 255, np.uint8)
    for x in (72, 73, 1047, 1048, 1117, 1118):
        a[72:1583, x] = 149
    a[72:74, 72:1118] = 149
    a[1581:1583, 72:1118] = 149
    def lines(top, bottom):
        for y in range(top, bottom, 40):
            a[y:y + 2, 76:1008] = 170
    def text(y, h=10, x0=100, x1=800):
        for k in range(0, h * 2, 4):
            a[y + k:y + k + 2, x0:x1:3] = 0
    if kind == 'blank':
        text(100, 6, 100, 260)            # "Question 4 continued"
        lines(150, 1540)
    elif kind == 'question_then_lines':
        text(100, 6, 100, 260)
        text(160, 40); text(300, 30)
        lines(700, 1540)
    elif kind == 'table':
        for y in range(300, 700, 40):
            a[y:y + 2, 76:1008] = 170
            text(y + 10, 4, 120, 900)
        text(100, 6, 100, 260)
    elif kind == 'grid':
        for y in range(300, 900, 20):
            a[y, 76:1008] = 170
        for x in range(80, 1008, 20):
            a[300:900, x] = 170
        text(150, 20)
    elif kind == 'embedded':
        text(100, 20)
        lines(260, 700)
        text(760, 20)
        lines(900, 1500)
    return a


# ----------------------------------------------------------------------------- image cleaner

def test_blank_answer_page_is_removed_and_question_page_is_cropped():
    assert cleaner.analyze(page('blank'))['action'] == 'remove'
    d = cleaner.analyze(page('question_then_lines'))
    assert d['action'] == 'crop' and d['pieces'] == [[0, d['pieces'][0][1]]]
    cut = d['pieces'][0][1]
    assert 340 < cut < 700           # keeps every content row (text ends < 360), drops the lines at 700+
    out = cleaner.apply(Image.fromarray(page('question_then_lines')), d)
    assert out.size == (1191, cut)


def test_content_that_looks_ruled_is_kept():
    assert cleaner.analyze(page('table'))['action'] == 'keep'
    assert cleaner.analyze(page('grid'))['action'] == 'keep'
    assert cleaner.analyze(np.full((300, 993), 255, np.uint8))['action'] == 'keep'   # empty strip is never dropped silently


def test_embedded_answer_block_is_collapsed_but_both_parts_survive():
    d = cleaner.analyze(page('embedded'))
    assert d['action'] in ('crop', 'collapse') and len(d['pieces']) >= 2
    out = np.array(cleaner.apply(Image.fromarray(page('embedded')), d).convert('L'))
    assert out.shape[0] < 1684 - 400
    original = page('embedded')
    # second text block rows survive somewhere in the output
    block = original[760:790, 100:800]
    assert any((out[y:y + 30, 100:800] == block).all() for y in range(out.shape[0] - 30))


def test_clean_one_never_alters_original_and_names_output_by_its_hash(tmp_path):
    vault = tmp_path / 'v'
    rel = 'Library/SourcePractice/Media/a.png'
    (vault / rel).parent.mkdir(parents=True)
    raw = png(page('question_then_lines'))
    (vault / rel).write_bytes(raw)
    entry = cleaner.clean_one(vault, rel, tmp_path / 'out')
    assert (vault / rel).read_bytes() == raw and entry['decision'] == 'crop'
    cleaned = (tmp_path / 'out' / entry['cleaned']['file']).read_bytes()
    assert hashlib.sha256(cleaned).hexdigest() + '.png' == entry['cleaned']['file']
    assert entry['original_sha256'] == hashlib.sha256(raw).hexdigest()


def test_item_keeps_an_image_when_all_would_be_removed():
    side = {'images': {'x': {'decision': 'remove', 'cleaned': None}, 'y': {'decision': 'remove', 'cleaned': None}}}
    item = {'id': 'q', 'question_media': ['x', 'y'], 'context_media': []}
    rows = cleaner.resolve(side, item)['question_media']
    assert [r['decision'] for r in rows] == ['keep_last_image'] * 2
    side['images']['y'] = {'decision': 'keep', 'cleaned': None}
    assert [r['original'] for r in cleaner.resolve(side, item)['question_media']] == ['y']


def test_real_library_media_is_cleanable_through_the_shared_helper(tmp_path):
    import library_assets
    records = library_assets._library().records()
    media = sorted(r['path'] for r in records.values() if r['path'].startswith('Library/SourcePractice/Media/'))
    if not media:
        pytest.skip('real Library has no registered source practice media')
    (tmp_path / 'vault').mkdir()
    copied = library_assets.copy_to_vault(media[0], tmp_path / 'vault')
    entry = cleaner.clean_one(tmp_path / 'vault', copied.relative_to(tmp_path / 'vault').as_posix(), tmp_path / 'out', write=False)
    assert entry['decision'] in ('keep', 'crop', 'collapse', 'remove')


# ----------------------------------------------------------------------------- part splitting

def test_split_parts_handles_question_numbers_romans_and_inline():
    pre, parts = topics.split_parts('15. (a) \nWrite sqrt 45 as a surd \n(1)\n(b) \nExpress in form b + c \n(5)\n(Total 6 marks)')
    assert [p['label'] for p in parts] == ['a', 'b'] and 'Total' not in parts[1]['text']
    _, parts = topics.split_parts('1. Given f(x)\n(a) \nFind f\n(b) \n(i) \nSolve this\n(ii) \nHence plot')
    assert [p['label'] for p in parts] == ['a', 'b(i)', 'b(ii)']
    _, parts = topics.split_parts('1. (a) Show that x = 2 (b) Hence find y')
    assert [p['label'] for p in parts] == ['a', 'b']
    assert topics.split_parts('Find the value of (b) in terms of k')[1] == []      # a sentence is not a part list


# ----------------------------------------------------------------------------- tagging + migration on a disposable vault

def seed_vault(tmp_path):
    vault = tmp_path / 'STEM Tutor'
    vault.mkdir()
    items = []
    media_a = 'Library/SourcePractice/Media/' + 'a' * 64 + '.png'
    media_b = 'Library/SourcePractice/Media/' + 'b' * 64 + '.png'
    write_asset(vault, media_a, png(page('question_then_lines')))
    write_asset(vault, media_b, png(page('blank')))

    def item(qid, text, **extra):
        row = {'id': qid, 'canonical_id': qid, 'official_qid': None, 'course': 'P1', 'source': 'P1 Algebra - surds',
               'label': '1', 'part': '', 'kind': 'structured', 'marks': 4, 'question_text': text, 'scheme_text': 'ms',
               'kcs': [], 'bank_id': None, 'source_verified': True, 'mastery_certified': False, 'teaching_approved': False,
               'question_media': [media_a, media_b], 'context_media': [], 'mark_scheme_media': [], 'answer': None,
               'answer_status': 'missing'}
        row.update(extra)
        return row
    items.append(item('P1_known', 'Some words about nothing in particular here', official_qid='P1_known'))
    items.append(item('P1_surds', '1. (a) \nRationalise the denominator of the surd and simplify surds \n(2)\n(b) \n'
                      'Manipulate the surd expression using rationalise denominators \n(2)\n(Total 4 marks)',
                      source='P1_pearson-edexcel-ial_WMA11_2021-01_01'))
    items.append(item('P1_gibberish', 'zzz qqq www', source='P1_pearson-edexcel-ial_WMA11_2021-01_02'))
    manifest = {'schema_version': 1, 'mastery_certified': 0, 'source_verified': True, 'items': items, 'held': []}
    blob = json.dumps(manifest, sort_keys=True).encode()
    release = f'Library/SourcePractice/Releases/{hashlib.sha256(blob).hexdigest()}.json'
    write_asset(vault, release, blob)
    (vault / '.tutor/source_practice').mkdir(parents=True)
    (vault / '.tutor/source_practice/CURRENT').write_text(release)
    (vault / '.tutor/packs').mkdir(parents=True)
    (vault / '.tutor/packs/CURRENT').write_text('v1')
    graph_dir = vault / 'Library/Releases/v1/specs/P1'
    graph_dir.mkdir(parents=True)
    (graph_dir / 'graph.json').write_text(json.dumps(GRAPH))
    (vault / '.tutor/topicals').mkdir(parents=True)
    (vault / '.tutor/topicals/CURRENT').write_text('vt')
    bank = vault / 'Library/Shared/Topicals/Releases/vt'
    bank.mkdir(parents=True)
    (bank / 'bank.json').write_text(json.dumps({'items': [
        {'id': 'topical-P1_known', 'kcs': ['P1-4.2'], 'source': {'qid': 'P1_known'}, 'topical': {'chapters': ['P1-4']}}]}))
    return vault


def build_work(vault, tmp_path):
    mapping = topics.build(vault)
    cleaned = tmp_path / 'work'
    from source_topics import load_release
    _, data = load_release(vault)
    media = media_for = None
    sidecar = cleaner.run(vault, cleaned, courses={'P1'})
    return mapping, sidecar, cleaned


def test_tagging_prefers_reviewed_mapping_then_text_then_refuses(tmp_path):
    vault = seed_vault(tmp_path)
    mapping = topics.build(vault)
    rec = {r['id']: r for r in mapping['items']}
    assert rec['P1_known']['method'] == 'topical_bank' and rec['P1_known']['kcs_required'] == ['P1-4.2']
    assert rec['P1_known']['trust'] == 'reviewed'
    assert rec['P1_surds']['kcs_required'] == ['P1-1.2'] and rec['P1_surds']['status'] == 'mapped'
    assert [p['label'] for p in rec['P1_surds']['parts']] == ['a', 'b']
    assert rec['P1_gibberish']['status'] == 'unmapped' and rec['P1_gibberish']['kcs_required'] == []
    assert rec['P1_gibberish']['reason']
    again = topics.build(vault)
    assert json.dumps(again, sort_keys=True) == json.dumps(mapping, sort_keys=True)   # deterministic


def test_dry_run_writes_nothing_and_apply_registers_immutable_banks(tmp_path):
    vault = seed_vault(tmp_path)
    mapping, sidecar, work = build_work(vault, tmp_path)
    assert sidecar['images'] and {e['decision'] for e in sidecar['images'].values()} == {'crop', 'remove'}
    catalog_before = (vault / 'Library/catalog.json').read_bytes()
    docs = migrate.build_documents(vault, mapping, sidecar)
    report = migrate.plan(vault, docs, sidecar, work)
    assert (vault / 'Library/catalog.json').read_bytes() == catalog_before          # dry run touched nothing
    assert report['courses']['P1']['ready'] == 2 and report['courses']['P1']['held'] == 1
    doc = docs['P1']
    ready = {i['id']: i for i in doc['items']}
    assert ready['P1_gibberish']['held'] and ready['P1_gibberish']['held_reason']
    for i in doc['items']:
        assert i['source_verified'] is True and i['mastery_certified'] is False and i['teaching_approved'] is False
        assert [m['decision'] for m in i['media']['question_media']] == ['crop']      # blank page dropped, question cropped
        assert i['media']['question_media'][0]['path'].startswith('Library/Courses/P1/Questions/SourceVerified/Media/')

    applied = migrate.apply(vault, docs, sidecar, work)
    library = AssetLibrary(vault)
    assert library.read(applied['P1']['reference'])                                 # digest-checked read
    assert library.record(applied['P1']['reference'])['provenance']['release_sha256'] == Path(doc['provenance']['release']).stem
    again = migrate.apply(vault, docs, sidecar, work)                               # idempotent
    assert again['P1']['path'] == applied['P1']['path']
    # originals untouched
    for entry in sidecar['images']:
        assert (vault / entry).is_file()

    reader = SourceQuestions.load(vault)
    assert reader.courses() == ['P1']
    assert {i['id'] for i in reader.items('P1')} == {'P1_known', 'P1_surds'}         # held items hidden by default
    assert {h['id'] for h in reader.held('P1')} == {'P1_gibberish'}
    assert reader.required_kcs('P1_surds') == ['P1-1.2']
    assert reader.part_kcs('P1_surds') == {'a': ['P1-1.2'], 'b': ['P1-1.2']}
    assert [i['id'] for i in reader.items('P1', kc='P1-4.2')] == ['P1_known']
    for image in reader.item('P1_known')['media']['question_media']:
        assert library.read(image['path'])                                           # cleaned image is registered


def test_apply_refuses_to_replace_existing_resources_and_production_vault(tmp_path, monkeypatch, capsys):
    vault = seed_vault(tmp_path)
    mapping, sidecar, work = build_work(vault, tmp_path)
    docs = migrate.build_documents(vault, mapping, sidecar)
    migrate.apply(vault, docs, sidecar, work)
    with pytest.raises(ValueError):
        migrate.write_asset_idempotent(vault, 'Library/Courses/P1/Questions/SourceVerified/Media/' +
                                       next(iter(sidecar['images'].values()))['cleaned']['file']
                                       if next(iter(sidecar['images'].values()))['cleaned'] else 'x', b'different', metadata={})
    (work / 'source_topics.json').parent.mkdir(exist_ok=True)
    (work / 'source_topics.json').write_text(json.dumps(mapping))
    (work / 'image_cleaning.json').write_text(json.dumps(sidecar))
    monkeypatch.setattr(migrate, 'DEFAULT_VAULT', vault)
    assert migrate.main(['--vault', str(vault), '--work', str(work), '--apply']) == 2     # production guard
    assert migrate.main(['--vault', str(vault), '--work', str(work)]) == 0                # dry run


def test_reader_rejects_flags_that_would_grant_mastery():
    doc = {'kind': 'source_verified_questions', 'course': 'P1', 'provenance': {}, 'items': [
        {'id': 'x', 'source_verified': True, 'mastery_certified': True, 'teaching_approved': False}]}
    with pytest.raises(ValueError):
        SourceQuestions.from_document(doc)
