"""Source authority and isolated practice using real PDFs in disposable vaults."""
import copy
import hashlib
import importlib.util
import json
from pathlib import Path
import shutil
import sys

import pytest
from library_assets import copy_to_vault, canonical_path

ROOT = Path(__file__).resolve().parents[1]
PREP = ROOT.parent / 'Work/Preparation'
NATIVE = PREP / 'extraction-fastpath-20261104-v2'
PMT = PREP / 'pmt-topicals-20261104/D1/asset-4b7b93f6b6a352d6e2cabe11-95f0e59af905'
sys.path.insert(0, str(ROOT / 'extraction'))


def module():
    import source_practice as build
    return build


@pytest.fixture(autouse=True)
def isolated_workers(tmp_path, monkeypatch):
    monkeypatch.setattr(module(), 'WORKERS', tmp_path / 'no-workers')


def install(tmp_path, source=NATIVE / '9701_s19_11'):
    vault = tmp_path / 'vault'; vault.mkdir(exist_ok=True)
    bundle = json.loads((source / 'bundle.json').read_bytes())
    refs = ([s['reference'] for s in bundle['sources'].values()] if 'sources' in bundle
            else [bundle['source']['id']])
    for ref in refs:
        copied = copy_to_vault(canonical_path(ref), vault)
        # Preserve the source stable ID as well as its real immutable bytes.
        catalog_path = vault / 'Library/catalog.json'
        catalog = json.loads(catalog_path.read_bytes())
        key = next(k for k, v in catalog['assets'].items() if v['path'] == copied.relative_to(vault).as_posix())
        catalog['assets'][ref.removeprefix('asset:')] = catalog['assets'].pop(key)
        catalog_path.write_text(json.dumps(catalog))
    output = tmp_path / source.name
    shutil.copytree(source, output)
    return vault, output


def reseal(output, mutate):
    bundle = json.loads((output / 'bundle.json').read_bytes()); mutate(bundle)
    data = json.dumps(bundle).encode(); (output / 'bundle.json').write_bytes(data)
    (output / 'COMPLETE').write_text(hashlib.sha256(data).hexdigest())


@pytest.mark.parametrize('paper', ['9701_s19_11', '9701_w21_13', '9702_s19_11', '9702_w25_13'])
def test_real_native_source_replay_and_independent_key(tmp_path, paper):
    vault, output = install(tmp_path, NATIVE / paper)
    result = module().verify(vault, output)
    assert len(result['items']) + len(result['held']) == 40
    assert result['source_verified'] is True and result['mastery_certified'] is False
    assert result['metrics']['model_calls'] == 0
    assert result['key_extractors'] == ['pymupdf_spatial', 'pypdf_serialized']
    assert all(i['id'] == i['canonical_id'] and i['kcs'] == [] for i in result['items'])


@pytest.mark.parametrize('fault', ['answer', 'geometry', 'missing', 'pages', 'source', 'private'])
def test_resealed_native_attacks_fail_source_authority(tmp_path, fault):
    vault, output = install(tmp_path)
    def mutate(b):
        if fault == 'answer': b['questions'][0]['answer'] = 'A'
        elif fault == 'geometry': b['questions'][0]['regions'][0]['box'][1] += .02
        elif fault == 'missing': b['questions'].pop()
        elif fault == 'pages': b['qp_pages'].pop()
        elif fault == 'source': b['sources']['qp']['sha256'] = '0' * 64
        else: b['questions'][0]['question_media'] = b['questions'][0]['mark_scheme_media']
    reseal(output, mutate)
    with pytest.raises(ValueError): module().verify(vault, output)


def test_pmt_full_scheme_association_continuations_and_comments(tmp_path):
    vault, output = install(tmp_path, PMT)
    result = module().verify(vault, output)
    assert len(result['items']) == 6 and not result['held']
    assert result['title'] == 'D1 Algorithms - Bin packing'
    assert [p['role'] for p in result['pages']] == ['questions'] * 3 + ['mark_scheme'] * 4 + ['examiner_comments'] * 2
    items = result['items']
    assert [i['marks'] for i in items] == [9, 9, 8, 11, 9, 9]
    assert all(len(i.get('question_media', [])) == len(i['regions']) for i in items)
    assert all(len(i.get('context_media', [])) == len(i['context_regions']) for i in items)
    assert all([result['media'][name]['region'] for name in i['question_media']] == i['regions'] for i in items)
    assert all([result['media'][name]['region'] for name in i['context_media']] == i['context_regions'] for i in items)
    assert {r['page'] for r in items[1]['mark_scheme_regions']} == {4, 5}
    assert {r['page'] for r in items[3]['mark_scheme_regions']} == {6}
    assert all(r['page'] < 8 for i in items for r in i['mark_scheme_regions'])
    assert all(i['canonical_id'].startswith('occurrence-') and i['official_qid'] is None for i in items)
    assert 'Special case' in items[1]['scheme_text'] and 'or' in items[4]['scheme_text']
    assert all(i['maximum_authority'] == 'printed_question_total' for i in items)


@pytest.mark.parametrize('fault', ['association', 'commentary', 'continuation'])
def test_pmt_source_replay_rejects_resealed_public_tampering(tmp_path, fault):
    vault, output = install(tmp_path, PMT)
    def mutate(b):
        if fault == 'association': b['questions'][0]['label'] = '2'
        elif fault == 'commentary': b['questions'][0]['regions'][0]['page'] = 8
        else: b['questions'][1]['regions'].pop()
    reseal(output, mutate)
    with pytest.raises(ValueError): module().verify(vault, output)


def test_publish_cas_privacy_attempts_and_unchanged_history(tmp_path):
    from tutorlib.source_practice import Collection
    vault, output = install(tmp_path)
    _, written = install(tmp_path, PMT)
    old = vault / '.tutor/events.jsonl'; old.parent.mkdir(); old.write_bytes(b'preserve learner history\n')
    state = vault / '.tutor/state.json'; state.write_bytes(b'{"mastery":42}')
    before = {p: p.read_bytes() for p in (old, state)}
    release = module().publish(vault, [output, written], expected_current=None)
    assert release['mastery_certified'] == 0
    c = Collection(vault)
    assert set(c.courses()) == {'9701', 'D1'}
    q = c.questions('9701')[0]; public = c.question(q['id'])
    assert not {'answer', 'scheme_text', 'mark_scheme_media', 'mark_scheme_regions'} & public.keys()
    with pytest.raises(ValueError): c.feedback('missing')
    attempt = c.submit(q['id'], 'B'); feedback = c.feedback(attempt['attempt_id'])
    assert feedback['answer'] == 'B' and feedback['awarded'] == 1
    w = c.questions('D1')[1]; attempt = c.submit(w['id'], 'My working')
    assert c.feedback(attempt['attempt_id'])['scheme_media']
    for marks in (-1, 10, True, 1.5):
        with pytest.raises(ValueError): c.award(attempt['attempt_id'], marks)
    c.award(attempt['attempt_id'], 4)
    with pytest.raises(ValueError): c.award(attempt['attempt_id'], 5)
    assert before == {p: p.read_bytes() for p in before}
    assert all(p.parent == vault / '.tutor/source_practice/attempts' for p in (vault / '.tutor/source_practice/attempts').iterdir())
    # Runtime is Library-only, even after all authoring inputs disappear.
    shutil.rmtree(output); shutil.rmtree(written)
    assert Collection(vault).question(q['id']) == public
    current = (vault / '.tutor/source_practice/CURRENT').read_text().strip()
    with pytest.raises(ValueError, match='CURRENT'): module().publish(vault, [], expected_current=None)
    assert (vault / '.tutor/source_practice/CURRENT').read_text().strip() == current


def test_guard2_holds_only_owned_question_and_preserves_worker_state(tmp_path, monkeypatch):
    vault, output = install(tmp_path)
    workers = tmp_path / 'workers'; owner = workers / 'owner'; owner.mkdir(parents=True)
    state = owner / 'state.json'
    state.write_text(json.dumps({'reliability_failures': {'1': {'extract': [{}, {}]}},
                                'selected_item_scope': {'official_qid': '9701_s19_11_q1'}}))
    before = state.read_bytes()
    monkeypatch.setattr(module(), 'WORKERS', workers, raising=False)
    result = module().verify(vault, output)
    assert len(result['items']) == 39
    assert result['held'][0]['id'] == '9701_s19_11_q1'
    assert state.read_bytes() == before


def test_duplicate_republication_reuses_identity_and_keeps_original_release(tmp_path):
    vault, output = install(tmp_path)
    first = module().publish(vault, [output, output], expected_current=None)
    assert len(first['new']) == 40 and len(first['reused']) == 40
    before = (vault / first['current']).read_bytes()
    second = module().publish(vault, [output], expected_current=first['current'])
    assert second['new'] == [] and len(second['reused']) == 40
    assert (vault / first['current']).read_bytes() == before


def test_resealed_crop_pixels_and_rubric_swap_fail(tmp_path):
    vault, output = install(tmp_path)
    bundle = json.loads((output / 'bundle.json').read_bytes())
    name = bundle['questions'][0]['question_media'][0]
    from PIL import Image
    path = output / name
    with Image.open(path) as image:
        image.putpixel((0, 0), (0, 0, 0)); image.save(path)
    def mutate(b):
        b['media'][name]['sha256'] = hashlib.sha256(path.read_bytes()).hexdigest()
        b['media'][name]['bytes'] = len(path.read_bytes())
    reseal(output, mutate)
    with pytest.raises(ValueError, match='pixels'): module().verify(vault, output)


def test_private_scheme_path_requires_owned_attempt(tmp_path):
    from tutorlib.source_practice import Collection
    vault, output = install(tmp_path, PMT)
    module().publish(vault, [output], expected_current=None)
    c = Collection(vault); questions = c.questions('D1')
    first = c.submit(questions[0]['id'], 'written work')
    reference = c.feedback(first['attempt_id'])['scheme_media'][0]
    with pytest.raises(ValueError): c.media_path(questions[0]['id'], reference)
    with pytest.raises(ValueError): c.media_path(questions[1]['id'], reference, attempt_id=first['attempt_id'])
    assert c.media_path(questions[0]['id'], reference, attempt_id=first['attempt_id']).is_file()


def test_release_append_retains_page_proof_and_applies_new_guard_hold(tmp_path, monkeypatch):
    from tutorlib.source_practice import Collection
    vault, output = install(tmp_path)
    first = module().publish(vault, [output], expected_current=None)
    original = json.loads((vault / first['current']).read_bytes())
    workers = tmp_path / 'workers'; workers.mkdir()
    (workers / 'state.json').write_text(json.dumps({'reliability_failures': {'1': {'extract': [{}, {}]}},
                                                   'selected_item_scope': {'official_qid': '9701_s19_11_q1'}}))
    monkeypatch.setattr(module(), 'WORKERS', workers)
    second = module().publish(vault, [], expected_current=first['current'])
    latest = json.loads((vault / second['current']).read_bytes())
    assert latest['proofs'] == original['proofs']
    assert len(Collection(vault).questions()) == 39
    assert any(h['id'] == '9701_s19_11_q1' for h in second['held'])


def native_variant(tmp_path, vault, original, *, tail=False, changed=False):
    """Synthetic derivative of a real shared source stays in the disposable vault."""
    import pymupdf
    import fastpath
    from tutorlib.asset_library import AssetLibrary, write_asset
    bundle = json.loads((original / 'bundle.json').read_bytes())
    with pymupdf.open(stream=AssetLibrary(vault).read(bundle['sources']['qp']['reference']), filetype='pdf') as doc:
        if changed:
            region = bundle['questions'][0]['regions'][0]
            page = doc[region['page'] - 1]
            page.insert_text((150, (region['box'][1] + .04) * page.rect.height), 'REVISED SOURCE CONDITION', fontsize=8)
        if tail:
            page = doc.new_page(width=doc[0].rect.width, height=doc[0].rect.height)
            page.insert_text((100, 120), 'Question 40 continued: essential remaining choices and data.', fontsize=10)
        raw = doc.tobytes()
    ref = write_asset(vault, 'Library/Shared/Variants/9701_s19_qp_11.pdf', raw)
    output = tmp_path / 'variant'
    fastpath.prepare(vault, ref, bundle['sources']['ms']['reference'], output)
    return output


def test_unowned_native_continuation_holds_file_with_complete_ledger(tmp_path):
    vault, original = install(tmp_path)
    variant = native_variant(tmp_path, vault, original, tail=True)
    checked = module().verify(vault, variant)
    assert not checked['items']
    assert {q['id'] for q in checked['held']} == {f'9701_s19_11_q{n}' for n in range(1, 41)}
    assert any(e.get('page') == 17 for e in checked['exceptions'])
    assert checked['sources']['qp']['pages'] == 17


def test_canonical_source_conflict_is_held_and_old_release_unchanged(tmp_path):
    from tutorlib.source_practice import Collection
    vault, original = install(tmp_path)
    first = module().publish(vault, [original], expected_current=None)
    old_bytes = (vault / first['current']).read_bytes()
    variant = native_variant(tmp_path, vault, original, changed=True)
    second = module().publish(vault, [variant], expected_current=first['current'])
    assert any(h['id'] == '9701_s19_11_q1' and 'canonical_evidence_conflict' in h['reasons'] for h in second['held'])
    assert '9701_s19_11_q1' not in second['reused']
    assert '9701_s19_11_q1' not in {q['id'] for q in Collection(vault).questions()}
    assert (vault / first['current']).read_bytes() == old_bytes


def test_existing_bank_key_conflict_is_held_and_matching_key_reused(tmp_path):
    from tutorlib.asset_library import write_asset
    from tutorlib.source_practice import Collection
    vault, original = install(tmp_path)
    bank = {'items': [
        {'id': 'original-bank-q1', 'kind': 'mcq', 'source': {'qid': '9701_s19_11_q1'}, 'answer': 'A'},
        {'id': 'original-bank-q2', 'kind': 'mcq', 'source': {'qid': '9701_s19_11_q2'}, 'answer': 'D'}]}
    bank_path = 'Library/Shared/Topicals/Releases/test-bank/bank.json'
    write_asset(vault, bank_path, json.dumps(bank).encode())
    pointer = vault / '.tutor/topicals/CURRENT'; pointer.parent.mkdir(parents=True); pointer.write_text('test-bank')
    before = {p: p.read_bytes() for p in (pointer, vault / bank_path)}
    published = module().publish(vault, [original], expected_current=None)
    assert any(h['id'] == '9701_s19_11_q1' and 'existing_bank_key_conflict' in h['reasons'] for h in published['held'])
    assert '9701_s19_11_q1' not in published['new'] + published['reused']
    assert published['reused'] == ['9701_s19_11_q2']
    assert Collection(vault).question('9701_s19_11_q2')['bank_id'] == 'original-bank-q2'
    assert before == {p: p.read_bytes() for p in before}


@pytest.mark.parametrize('retained', [False, True])
def test_publication_guard_snapshot_filters_incoming_and_retained(tmp_path, monkeypatch, retained):
    from tutorlib.source_practice import Collection
    vault, original = install(tmp_path)
    first = module().publish(vault, [original], expected_current=None) if retained else None
    checked = module().verify(vault, original)
    monkeypatch.setattr(module(), 'verify', lambda *a, **kw: checked)
    monkeypatch.setattr(module(), '_guard_holds', lambda: {'9701_s19_11_q1': ['guard2:new-owner']})
    result = module().publish(vault, [original], expected_current=first['current'] if first else None)
    assert '9701_s19_11_q1' not in {q['id'] for q in Collection(vault).questions()}
    assert any(h['id'] == '9701_s19_11_q1' and h['reasons'] == ['guard2:new-owner'] for h in result['held'])
