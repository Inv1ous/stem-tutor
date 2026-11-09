"""Reviewed private rasters survive publication without becoming public prompts."""
import copy
import json

import pytest

from test_extraction_structured import structured_case
from test_whole_rubric import whole
from tutorlib import packs, session, store, topicals


def whole_case(tmp_path, monkeypatch):
    ex, path, q, vault, save = structured_case(tmp_path, monkeypatch)
    q.update(marks=2, scheme=whole(media=['official-ms.png'])['scheme'])
    save()
    return ex, path, q, vault, save


def prepared_case(tmp_path, monkeypatch):
    ex, path, q, vault, save = whole_case(tmp_path, monkeypatch)
    ex.register('diagram')
    batch = tmp_path / 'prepared'
    ex.prepare_publication('diagram', batch)
    return ex, q, vault, batch


def test_reviewed_whole_rubric_round_trip(tmp_path, monkeypatch):
    ex, q, vault, batch = prepared_case(tmp_path, monkeypatch)
    bank = json.loads((batch / 'bank.json').read_text())
    item = bank['items'][0]
    assert item['marks'] == 2 and item['source']['part'] == q['part']
    assert item['source']['mark_scheme_regions'] == q['mark_scheme_regions']
    assert item['kcs'] == q['kcs']
    media = item['scheme'][0]['whole_rubric']['media']
    assert len(media) == 1 and media[0].startswith('Library/Courses/9702/Questions/Media/')
    assert not set(media) & set(item['images'])
    before = list((vault / '.tutor/events').glob('*'))
    ex.publish('diagram', batch)
    runtime = packs.Packs(store.Vault(vault))
    assert not runtime.topical_errors
    assert list((vault / '.tutor/events').glob('*')) == before
    assert topicals.whole_rubric(runtime.items_for('9702-2.1.1')[-1]) is not None


@pytest.mark.parametrize('mutate', [
    lambda i: i['scheme'][0].update(point='unreviewed'),
    lambda i: i['scheme'][0]['whole_rubric'].update(version=2),
    lambda i: i['scheme'][0]['whole_rubric'].update(max_marks=1),
    lambda i: i['scheme'][0]['whole_rubric'].update(media=[]),
    lambda i: i['scheme'][0]['whole_rubric'].update(media=i['images']),
    lambda i: i['scheme'][0].pop('whole_rubric'),
])
def test_whole_publication_rejects_each_tamper(tmp_path, monkeypatch, mutate):
    ex, _, vault, batch = prepared_case(tmp_path, monkeypatch)
    bank = json.loads((batch / 'bank.json').read_text()); mutate(bank['items'][0])
    (batch / 'bank.json').write_text(json.dumps(bank))
    with pytest.raises(ValueError):
        ex.publish('diagram', batch)
    assert not (vault / '.tutor/topicals/CURRENT').exists()


@pytest.mark.parametrize('media', [['circuit.png'], ['missing.png'], ['../outside.png']])
def test_whole_candidate_media_must_be_reviewed_private_ms(tmp_path, monkeypatch, media):
    ex, _, q, _, save = whole_case(tmp_path, monkeypatch)
    q['scheme'][0]['whole_rubric']['media'] = media; save()
    assert ex.check('diagram')['stage'] == 'pending'


def test_runtime_rejects_wrong_private_bytes_and_public_overlap(tmp_path, monkeypatch):
    ex, _, vault, batch = prepared_case(tmp_path, monkeypatch)
    ex.publish('diagram', batch)
    runtime = packs.Packs(store.Vault(vault)); item = runtime.topicals.items[0]
    media = item['scheme'][0]['whole_rubric']['media'][0]
    item['images'].append(media)
    with pytest.raises(ValueError):
        topicals.whole_rubric_media(item, vault)
    item['images'].pop()
    (vault / media).write_bytes(b'corrupt')
    with pytest.raises(ValueError):
        topicals.whole_rubric_media(item, vault)


@pytest.mark.parametrize('mode', ['topical', 'long'])
def test_source_bound_whole_end_to_end_and_durable_human_provenance(tmp_path, monkeypatch, mode):
    from tutorlib import views
    from tutorlib.asset_library import AssetLibrary
    ex, _, vault, batch = prepared_case(tmp_path, monkeypatch)
    ex.publish('diagram', batch)
    t = session.Tutor(store.Vault(vault))
    t.start(mode, focus=['9702-2.1'])
    view = t.next()['items'][0]
    assert view.get('manual_marking') is True
    n = view['n']; work = 'My graph rises from the origin.'
    prefix = {p: p.read_bytes() for p in (vault / '.tutor/events').glob('*.jsonl')}
    assert 'unallocated' not in (vault / 'Now.md').read_text()
    assert 'official-ms' not in (vault / 'Now.md').read_text()
    out = t.whole_rubric(n, work)
    assert 'ticket' in out, out
    body = views.whole_rubric_block(out, vault_root=vault)
    assert out['point'] in body and f"![[{out['media'][0]}]]" in body
    t.show('tutor', body, 'Official rubric')
    assert out['media'][0] in (vault / 'Now.md').read_text()
    fb = t.answer(f'{n} = {work}', manual_awards={n: {'earned_marks': 1, 'ticket': out['ticket']}})['results'][0]
    event = next(e for e in t.vault.events() if e.get('id') == fb['event'])
    assert event['grade']['score'] == .5 and event['human_award']['marker'] == 'human'
    for path, before in prefix.items():
        assert path.read_bytes().startswith(before)
    resumed = session.Tutor(store.Vault(vault))
    event_before = {p: p.read_bytes() for p in prefix}
    assert not resumed.regrade(event['id'], 'AI wants full credit')['ok']
    assert all(p.read_bytes() == data for p, data in event_before.items())


def test_whole_publication_is_additive_and_binds_exact_private_scheme(tmp_path, monkeypatch):
    from test_extraction_structured import batch_for
    from tutorlib.asset_library import AssetLibrary
    import topicals as importer
    ex, _, q, vault, _ = whole_case(tmp_path, monkeypatch)
    seed, bank, _ = batch_for(ex, q, tmp_path)
    old = bank['items'][0]
    old.update(id='existing-legacy', marks=1, scheme=[{'point': 'old immutable point'}])
    old['source']['qid'] = '9702_s23_22_q2'
    (seed / 'bank.json').write_text(json.dumps(bank))
    first = importer.publish(seed, vault)
    old_bytes = AssetLibrary(vault).read(first['release'] + '/bank.json')
    batch = tmp_path / 'additive'
    ex.prepare_publication('diagram', batch)
    assert json.loads((batch / 'bank.json').read_text())['items'][0] == old
    ex.publish('diagram', batch)
    assert AssetLibrary(vault).read(first['release'] + '/bank.json') == old_bytes


@pytest.mark.parametrize('damage', ['missing', 'corrupt', 'source', 'purpose'])
def test_whole_raster_missing_corrupt_or_partial_declines_all_disclosure(tmp_path, monkeypatch, damage):
    from tutorlib.asset_library import AssetLibrary
    ex, _, vault, batch = prepared_case(tmp_path, monkeypatch)
    ex.publish('diagram', batch)
    t = session.Tutor(store.Vault(vault)); t.start('topical', focus=['9702-2.1'])
    n = t.next()['items'][0]['n']; p = t.session['presented'][str(n)]
    media = p['inst']['scheme'][0]['whole_rubric']['media'][0]
    if damage == 'missing': (vault / media).unlink()
    if damage == 'corrupt': (vault / media).write_bytes(b'corrupt')
    if damage == 'source': p['inst']['source']['qid'] = '9701_s24_22_q1'
    if damage == 'purpose':
        catalog_path = vault / 'Library/catalog.json'; catalog = json.loads(catalog_path.read_text())
        next(r for r in catalog['assets'].values() if r['path'] == media)['kind'] = 'Diagrams'
        catalog_path.write_text(json.dumps(catalog))
    out = t.whole_rubric(n, 'My real graph attempt')
    assert out.get('error') and not any(k in out for k in ('point', 'media', 'ticket'))
    assert not t._marking_tickets and p['saved_work'] == 'My real graph attempt'
    assert 'official-ms' not in (vault / 'Now.md').read_text()


def test_manual_award_revalidates_raster_after_disclosure(tmp_path, monkeypatch):
    ex, _, vault, batch = prepared_case(tmp_path, monkeypatch)
    ex.publish('diagram', batch)
    t = session.Tutor(store.Vault(vault)); t.start('topical', focus=['9702-2.1'])
    n = t.next()['items'][0]['n']; work = 'My real graph attempt'
    out = t.whole_rubric(n, work)
    (vault / out['media'][0]).write_bytes(b'changed after disclosure')
    result = t.answer(f'{n} = {work}', manual_awards={n: {'earned_marks': 2, 'ticket': out['ticket']}})
    assert result['results'][0].get('error')
    assert not [e for e in t.vault.events() if e['type'] == 'answer']


def test_whole_private_registration_provenance_uses_mark_scheme_regions(tmp_path, monkeypatch):
    from tutorlib.asset_library import AssetLibrary
    ex, q, vault, batch = prepared_case(tmp_path, monkeypatch)
    item = json.loads((batch / 'bank.json').read_text())['items'][0]
    reference = item['scheme'][0]['whole_rubric']['media'][0]
    library = AssetLibrary(vault)
    sidecar = library.record(reference)['provenance']['sidecars'][0]
    provenance = json.loads(library.read(sidecar))
    assert provenance['regions'] == q['mark_scheme_regions']
    assert provenance['source_sha256'] == q['mark_scheme_regions'][0]['source_sha256']
