"""Question-library organization on disposable vaults: classification, names, duplicates, round trip."""
import hashlib
import json
from pathlib import Path
import sys

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'build'))
import library_assets
import organize_question_library as organize
import question_media_names as names
from tutorlib.asset_library import AssetLibrary, write_asset

SHA = hashlib.sha256(b'x').hexdigest()
MEDIA = 'Library/Courses/{}/Questions/Media/'
FIXTURE_PNG = 'Assets/9701/9701-1-2-fig-hydrogen-isotopes.png'
LEGACY = library_assets.read_bytes(FIXTURE_PNG)


def sha(data):
    return hashlib.sha256(data).hexdigest()


def png(label):
    return b'\x89PNG\r\n\x1a\n' + label.encode()


def sidecar(vault, image, record):
    body = {'record': record, 'sha256': sha((vault / image).read_bytes()), 'course': image.split('/')[2]}
    return write_asset(vault, image + '.json', json.dumps(body).encode(), metadata={'kind': 'Sources/Provenance'})


@pytest.fixture
def vault(tmp_path):
    vault = tmp_path / 'STEM Tutor'
    vault.mkdir()
    base = MEDIA.format('9701')
    write_asset(vault, base + '9701_s25_13_q27.png', LEGACY, aliases=['Assets/mcq/9701_s25_13_q27.png'],
                metadata={'course': '9701', 'kind': 'Questions/Media'})
    question = base + '9701-w25-11-q1-native-c85b58507d1e-1111111111111111.png'
    key = base + '9701-w25-11-q1-native-key-c85b58507d1e-2222222222222222.png'
    for path, label in ((question, 'q'), (key, 'k')):
        write_asset(vault, path, png(label), metadata={'course': '9701', 'kind': 'Questions/Media'})
    record = {'official_qid': '9701_w25_11_q1', 'kind': 'mcq', 'question_media': ['media/9701-w25-11-q1-native.png'],
              'mark_scheme_media': ['media/9701-w25-11-q1-native-key.png']}
    sidecar(vault, question, record)
    sidecar(vault, key, record)
    write_asset(vault, base + 'mystery.png', png('mystery'), metadata={'course': '9701', 'kind': 'Questions/Media'})
    write_asset(vault, base + 'copy-a.png', png('same'), aliases=['Assets/mcq/copy-a.png'], metadata={'course': '9701'})
    write_asset(vault, base + 'copy-b.png', png('same'), aliases=['Assets/mcq/copy-b.png'], metadata={'course': '9701'})
    write_asset(vault, base + 'native-qp-p11-aaaaaaaaaaaa-3333333333333333.png', png('pinned'),
                metadata={'course': '9701', 'kind': 'Questions/Media'})
    sidecar(vault, base + 'native-qp-p11-aaaaaaaaaaaa-3333333333333333.png',
            {'official_qid': '9701_s22_21_q3', 'kind': 'structured', 'question_media': ['media/native-qp-p11.png']})
    topical = 'Library/Courses/9701/Questions/Topicals/v1/Assets/topicals/9701_s19_13_q8-4444444444444444.png'
    write_asset(vault, topical, png('topical'), aliases=['build/out/topicals/v1/Assets/topicals/x.png'],
                metadata={'course': '9701', 'kind': 'Questions/Topicals'})
    write_asset(vault, 'Library/Courses/9701/Questions/Topicals/v1/Assets/topicals/9701-periodic-table-5555555555555555.png',
                png('periodic'), metadata={'course': '9701', 'kind': 'Questions/Topicals'})
    bank = {'items': [{'id': 't', 'kind': 'structured', 'source': {'qid': '9701_s19_13_q8'},
                       'images': ['build/out/topicals/v1/Assets/topicals/x.png']}]}
    write_asset(vault, 'Library/Courses/9701/Questions/Topicals/review-candidates/bank.json', json.dumps(bank).encode())
    verified = 'Library/Courses/P1/Questions/SourceVerified/Media/' + 'a' * 64 + '.png'
    source = 'Library/SourcePractice/Media/' + 'b' * 64 + '-6666666666666666.png'
    scheme = 'Library/SourcePractice/Media/' + 'c' * 64 + '-7777777777777777.png'
    qid = 'P1_pearson-edexcel-ial_WMA11_2019-01_01_q5'
    write_asset(vault, verified, png('verified'), metadata={'course': 'P1', 'kind': 'source_verified_question_media'})
    write_asset(vault, source, png('source'))
    write_asset(vault, scheme, png('scheme'))
    release = {'items': [{'id': qid, 'official_qid': qid, 'course': 'P1', 'kind': 'structured',
                          'question_media': [source], 'context_media': [], 'mark_scheme_media': [scheme]}]}
    write_asset(vault, 'Library/SourcePractice/Releases/' + 'd' * 64 + '.json', json.dumps(release).encode())
    verified_bank = {'items': [{'id': qid, 'official_qid': qid, 'kind': 'structured', 'course': 'P1',
                                'media': {'question_media': [{'path': verified, 'original': source}],
                                          'context_media': [], 'mark_scheme_media': [{'path': scheme, 'original': scheme}]}}]}
    write_asset(vault, 'Library/Courses/P1/Questions/SourceVerified/bank-1.json', json.dumps(verified_bank).encode())
    pack = {'image': 'Assets/mcq/9701_s25_13_q27.png'}
    write_asset(vault, 'Library/Courses/9701/Questions/Packs/9701/9701-1.1.json', json.dumps(pack).encode())
    return vault


def test_canonical_names_are_deterministic_and_collide_on_same_content():
    digest = sha(b'a')
    one = names.canonical_name('9701', 'mcq', digest, qid='9701_m17_12_q1')
    assert one == f'9701_m17_12_q01_mcq_{digest[:12]}.png'
    assert one == names.canonical_name('9701', 'mcq', digest, qid='9701_m17_12_q1', ext='.PNG')
    assert names.canonical_name('9701', 'key', digest, qid='9701_w25_11_q1', part='a').startswith('9701_w25_11_q01a_key_')
    edexcel = names.canonical_name('FP1', 'long', digest, qid='FP1_pearson-edexcel-ial_WFM01_2014-01_01_q4')
    assert edexcel == f'FP1_jan14_wfm01-01_q04_long_{digest[:12]}.png'
    fallback = names.canonical_name('P2', 'ctx', digest, qid=None)
    assert fallback == f'P2_nosrc_ctx_{digest[:12]}.png' and names.is_fallback(fallback)
    assert names.canonical_name('9701', 'mcq', digest, qid='9702_s20_11_q1') == f'9701_nosrc_mcq_{digest[:12]}.png'
    assert names.is_canonical(one) and not names.is_canonical('9701_m17_12_q1-abcdef.png')
    with pytest.raises(ValueError):
        names.canonical_name('9701', 'poster', digest)
    with pytest.raises(ValueError):
        names.canonical_name('9701', 'mcq', 'abc')


def test_classify_uses_strongest_tier_and_reports_conflicts():
    assert names.classify([(1, 'mcq', 'bank')], 'x.png')['role'] == 'mcq'
    assert names.classify([(3, 'mcq', 'path'), (1, 'key', 'sidecar')])['role'] == 'key'
    assert names.classify([(1, 'long', 'a'), (1, 'ctx', 'b')])['role'] == 'long'
    clash = names.classify([(1, 'mcq', 'a'), (1, 'key', 'b')])
    assert clash['role'] is None and clash['conflict']
    assert names.classify([], 'plain.png')['role'] is None
    assert names.classify([], '9701-w25-11-q1-native-key-aaaaaaaaaaaa-bbbbbbbbbbbbbbbb.png')['role'] == 'key'
    assert names.classify([(1, 'long', 'bank')], '9701-periodic-table-2025.png')['role'] == 'ref'
    assert names.classify([(1, 'key', 'sidecar')], 'ms-formula-p7.png')['role'] == 'key'


def test_find_duplicate_is_course_scoped_and_registration_reuses(vault):
    data = png('same')
    found = names.find_duplicate(vault, sha(data), '9701')
    assert found and Path(found['path']).name in ('copy-a.png', 'copy-b.png')
    assert found == names.find_duplicate(vault, sha(data), '9701')
    assert names.find_duplicate(vault, sha(data), 'P1') is None
    before = (vault / 'Library/catalog.json').read_bytes()
    reused = names.register_canonical(vault, data, '9701', 'mcq', qid='9701_s19_11_q1')
    assert reused['reused'] and reused['id'] == found['id']
    assert (vault / 'Library/catalog.json').read_bytes() == before
    fresh = names.register_canonical(vault, png('fresh'), '9701', 'key', qid='9701_s19_11_q1')
    assert not fresh['reused'] and fresh['path'] == (
        f"Library/Courses/9701/Questions/Media/Keys/9701_s19_11_q01_key_{sha(png('fresh'))[:12]}.png")
    assert AssetLibrary(vault).read(fresh['id']) == png('fresh')


def test_decisions_are_evidence_based(vault):
    _, records, decisions, unclassified = organize.decide(vault)
    by_name = {Path(d['path']).name: d for d in decisions.values()}
    assert by_name['9701_s25_13_q27.png']['role'] == 'mcq' and by_name['9701_s25_13_q27.png']['tier'] == 3
    question = by_name['9701-w25-11-q1-native-c85b58507d1e-1111111111111111.png']
    key = by_name['9701-w25-11-q1-native-key-c85b58507d1e-2222222222222222.png']
    assert (question['role'], question['tier']) == ('mcq', 1) and (key['role'], key['tier']) == ('key', 1)
    assert key['name'] == f"9701_w25_11_q01_key_{key['sha256'][:12]}.png"
    assert by_name['9701_s19_13_q8-4444444444444444.png']['role'] == 'long'
    assert by_name['9701-periodic-table-5555555555555555.png']['folder'] == 'Reference'
    assert [Path(u['path']).name for u in unclassified] == ['mystery.png']
    verified = next(d for d in decisions.values() if d['path'].endswith('a' * 64 + '.png'))
    assert (verified['role'], verified['course']) == ('long', 'P1')
    assert verified['name'] == f"P1_jan19_wma11-01_q05_long_{verified['sha256'][:12]}.png"
    scheme = next(d for d in decisions.values() if d['path'].endswith('c' * 64 + '-7777777777777777.png'))
    assert (scheme['role'], scheme['scope']) == ('key', 'sourcepractice')


def test_audit_finds_duplicates_and_references(vault):
    result = organize.audit(vault)
    same = [g for g in result['duplicate_groups'] if g['sha256'] == sha(png('same'))]
    assert len(same) == 1 and same[0]['count'] == 2 and same[0]['images']
    scan = result['reference_scan']
    assert scan['files_by_category'].get('pack') == 1 and scan['files_by_category'].get('topical') >= 1
    assert result['reference_check']['broken_count'] == 0
    assert result['summary']['unclassified'] == 1


def test_plan_is_readonly_with_stable_layout(vault):
    before = {p: p.read_bytes() for p in vault.rglob('*') if p.is_file()}
    decided = organize.decide(vault)
    report = organize.build_plan(vault, decided)
    assert {p: p.read_bytes() for p in vault.rglob('*') if p.is_file()} == before
    assert report['errors'] == []
    targets = {m['to'] for m in report['moves']}
    assert len(targets) == len(report['moves'])
    assert all('/Questions/Media/' in t and Path(t).parent.name in organize.FOLDERS for t in targets)
    assert not any(m['to'].endswith('.png.json') for m in report['moves'])
    assert sorted(Path(h['path']).name for h in report['held']) == [
        '9701-w25-11-q1-native-c85b58507d1e-1111111111111111.png',
        '9701-w25-11-q1-native-key-c85b58507d1e-2222222222222222.png',
        'native-qp-p11-aaaaaaaaaaaa-3333333333333333.png']
    full = organize.build_plan(vault, decided, include_pinned=True)
    sidecars = [m for m in full['moves'] if m['to'].endswith('.png.json')]
    assert len(sidecars) == 3 and full['held'] == [] and full['errors'] == []
    assert all(m['to'].rsplit('/', 1)[0] == next(i['to'] for i in full['moves'] if i['to'] + '.json' == m['to']).rsplit('/', 1)[0]
               for m in sidecars)
    assert not any(m['from'].endswith('mystery.png') for m in report['moves'])
    assert len(report['suffixed_duplicates']) == 1
    source = organize.build_plan(vault, decided, scope='sourcepractice')
    assert all(m['to'].startswith('Library/Courses/P1/Questions/Media/') and Path(m['to']).parent.name in organize.FOLDERS
               for m in source['moves']) and len(source['moves']) == 2
    assert all(m['catalog'] == {'kind': 'Questions/Media', 'course': 'P1'} for m in source['moves'])


def test_page_numbered_canonical_names_are_already_organized(vault):
    """normalize_question_names numbers multi-page questions (_p01, _p02); organize must not strip the page again."""
    base = MEDIA.format('9701')
    paged = {}
    for page in (1, 2):
        data = png(f'page{page}')
        paged[page] = base + f'MCQ/9701_s25_13_q27_p{page:02d}_mcq_{sha(data)[:12]}.png'
        write_asset(vault, paged[page], data, metadata={'course': '9701', 'kind': 'Questions/Media'})
    misplaced = png('page3')
    stray = base + f'Long/9701_s25_13_q27_p03_mcq_{sha(misplaced)[:12]}.png'
    write_asset(vault, stray, misplaced, aliases=['Assets/mcq/p3.png'], metadata={'course': '9701', 'kind': 'Questions/Media'})
    decided = organize.decide(vault)
    report = organize.build_plan(vault, decided)
    assert report['errors'] == []
    moved = {m['from'] for m in report['moves']}
    assert not moved & set(paged.values())
    assert stray in moved  # a page suffix never excuses the wrong folder
    assert len(report['held']) == 3  # validator pins are still held
    full = organize.build_plan(vault, decided, include_pinned=True)
    assert not {m['from'] for m in full['moves']} & set(paged.values())
    assert organize.paged_name_of(paged[2], paged[2].replace('_p02', ''))
    assert not organize.paged_name_of(paged[2].replace('_p02', ''), paged[2])


def test_apply_and_rollback_round_trip_keeps_every_reference(vault, tmp_path):
    library = AssetLibrary(vault)
    records = library.records()
    old_refs = {(identifier, ref): record['sha256'] for identifier, record in records.items()
                for ref in ['asset:' + identifier, record['path'], *record.get('aliases', [])]}
    original = (vault / 'Library/catalog.json').read_bytes()
    decided = organize.decide(vault)
    for scope, name in (('course', 'course.json'), ('sourcepractice', 'source.json')):
        report = organize.build_plan(vault, decided, scope=scope, include_pinned=True)
        assert organize.journalled.apply(report, tmp_path / 'Archive' / name)['status'] == 'complete'
        decided = organize.decide(vault)
    after = AssetLibrary(vault)
    for (identifier, ref), digest in old_refs.items():
        assert after.record(ref) is not None
        assert sha(after.read(ref)) == digest
        assert after.read(ref) == after.read('asset:' + identifier)
    moved = after.records()
    assert set(moved) == set(records)
    assert all(moved[i]['sha256'] == records[i]['sha256'] for i in records)
    assert organize.build_plan(vault, decided, include_pinned=True)['moves'] == []
    assert organize.build_plan(vault, decided, scope='sourcepractice')['moves'] == []
    organize.journalled.rollback(tmp_path / 'Archive/source.json')
    organize.journalled.rollback(tmp_path / 'Archive/course.json')
    assert (vault / 'Library/catalog.json').read_bytes() == original


def test_cli_apply_demands_confirmation_and_verified_plan(vault, tmp_path):
    out = tmp_path / 'out'
    organize.main(['plan', '--vault', str(vault), '--out', str(out)])
    plan = out / 'plan.json'
    assert json.loads(plan.read_text())['reference_check']['broken_count'] == 0
    with pytest.raises(SystemExit, match='--yes'):
        organize.main(['apply', '--plan', str(plan), '--journal', str(tmp_path / 'j.json')])
    unverified = json.loads(plan.read_text())
    del unverified['reference_check']
    (out / 'unverified.json').write_text(json.dumps(unverified))
    with pytest.raises(SystemExit, match='reference-verified'):
        organize.main(['apply', '--plan', str(out / 'unverified.json'), '--journal', str(tmp_path / 'j.json'), '--yes'])
    organize.main(['apply', '--plan', str(plan), '--journal', str(tmp_path / 'j.json'), '--yes'])
    organize.main(['rollback', '--journal', str(tmp_path / 'j.json')])
    assert AssetLibrary(vault).read('Assets/mcq/9701_s25_13_q27.png') == LEGACY



def test_merge_duplicates_aliases_surplus_and_skips_protected_groups(tmp_path):
    import merge_question_duplicates as merge
    vault = tmp_path / 'STEM Tutor'
    vault.mkdir()
    base = MEDIA.format('9701')
    dup = png('dup')
    canonical = base + 'MCQ/' + names.canonical_name('9701', 'mcq', sha(dup), qid='9701_s21_11_q1')
    legacy = base + '9701_s21_11_q1.png'
    write_asset(vault, canonical, dup, metadata={'course': '9701', 'kind': 'Questions/Media'})
    write_asset(vault, legacy, dup, metadata={'course': '9701', 'kind': 'Questions/Media'})
    write_asset(vault, 'Library/Courses/9701/Questions/Packs/9701/9701-1.1.json',
                json.dumps({'image': legacy}).encode())
    pin = png('pin')
    for name in ('native-ms-p2-2ea577632076-6ca5927035237706.png', 'native-ms-p2-4e504fb0420b-6ca5927035237706.png'):
        write_asset(vault, base + name, pin, metadata={'course': '9701', 'kind': 'Questions/Media'})
    learn = png('learn')
    write_asset(vault, base + 'learn-a.png', learn, metadata={'course': '9701'})
    write_asset(vault, base + 'learn-b.png', learn, metadata={'course': '9701'})
    (vault / '.tutor/events').mkdir(parents=True)
    (vault / '.tutor/events/2026-11.jsonl').write_text(json.dumps({'type': 'answer', 'image': base + 'learn-a.png'}) + '\n')
    cross = png('cross')
    write_asset(vault, base + 'cross.png', cross, metadata={'course': '9701'})
    write_asset(vault, MEDIA.format('9702') + 'cross.png', cross, metadata={'course': '9702'})
    groups = merge.find_groups(vault)
    plan = merge.build_plan(vault, groups)
    assert [m['path'] for m in plan['merges']] == [canonical]
    assert plan['moves'] == [{'id': plan['moves'][0]['id'], 'from': legacy, 'sha256': sha(dup),
                              'into': plan['merges'][0]['canonical']}]
    assert sorted(s['reason'] for s in plan['skipped']) == [
        'cross-course group', 'learner event/answer/grade reference', 'validator-pinned image']
    library = AssetLibrary(vault)
    records = library.records()
    plan['reference_check'] = merge.simulate(vault, plan, merge.scan_tokens(library, records), records)
    assert plan['reference_check']['broken_count'] == 0
    original = (vault / 'Library/catalog.json').read_bytes()
    journal = tmp_path / 'Archive/merge.json'
    assert merge.apply(plan, journal)['status'] == 'complete'
    after = AssetLibrary(vault)
    assert after.read(legacy) == dup and after.read('asset:' + plan['merges'][0]['canonical']) == dup
    assert not (vault / legacy).exists() and (journal.parent / 'merge/originals' / plan['moves'][0]['id']).exists()
    assert merge.rollback(journal)['status'] == 'rolled_back'
    assert (vault / 'Library/catalog.json').read_bytes() == original and (vault / legacy).read_bytes() == dup


def test_pinned_image_move_keeps_the_whole_rubric_pin_valid(tmp_path, monkeypatch):
    """A validator pin binds reviewed bytes to the asset; the reviewed name survives as an alias."""
    from test_extraction_whole_rubric import prepared_case
    from tutorlib import packs, store, topicals

    ex, _, vault, batch = prepared_case(tmp_path, monkeypatch)
    ex.publish('diagram', batch)
    item = packs.Packs(store.Vault(vault)).topicals.items[0]
    media = item['scheme'][0]['whole_rubric']['media'][0]
    assert topicals.whole_rubric_media(item, vault)
    library = AssetLibrary(vault)
    identifier = next(i for i, r in library.records().items() if r['path'] == media)
    moved = media.replace('/Questions/Media/', '/Questions/Media/Keys/')
    catalog_path = vault / 'Library/catalog.json'
    catalog = json.loads(catalog_path.read_text())
    catalog['assets'][identifier]['path'] = moved
    catalog['assets'][identifier]['aliases'] = [media]
    catalog_path.write_text(json.dumps(catalog))
    (vault / moved).parent.mkdir(parents=True, exist_ok=True)
    (vault / moved).write_bytes((vault / media).read_bytes())
    (vault / media).unlink()
    assert topicals.whole_rubric_media(item, vault)
    catalog['assets'][identifier]['aliases'] = []
    catalog_path.write_text(json.dumps(catalog))
    with pytest.raises(ValueError):
        topicals.whole_rubric_media(item, vault)


def test_merged_duplicate_keeps_each_reviewed_name_bound_to_its_own_sidecar(tmp_path, monkeypatch):
    """A duplicate merge keeps only the survivor's sidecar; a folded reviewed name is checked against its own."""
    from test_extraction_whole_rubric import prepared_case
    from tutorlib import packs, store, topicals

    ex, _, vault, batch = prepared_case(tmp_path, monkeypatch)
    ex.publish('diagram', batch)
    item = packs.Packs(store.Vault(vault)).topicals.items[0]
    media = item['scheme'][0]['whole_rubric']['media'][0]
    library = AssetLibrary(vault)
    identifier = next(i for i, r in library.records().items() if r['path'] == media)
    own = library.record(media)['provenance']['sidecars']
    assert library.record(own[0])['path'] == media + '.json'
    survivor = write_asset(vault, media.replace('/Media/', '/Media/Keys/') + '.other.json',
                           json.dumps({'course': '9701', 'record': {}}).encode(),
                           metadata={'course': '9701', 'kind': 'Sources/Provenance'})
    moved = media.replace('/Questions/Media/', '/Questions/Media/Keys/')
    catalog_path = vault / 'Library/catalog.json'
    catalog = json.loads(catalog_path.read_text())
    record = catalog['assets'][identifier]
    record.update(path=moved, aliases=[media], provenance={'sidecars': ['asset:' + survivor]})
    catalog_path.write_text(json.dumps(catalog))
    (vault / moved).parent.mkdir(parents=True, exist_ok=True)
    (vault / moved).write_bytes((vault / media).read_bytes())
    (vault / media).unlink()
    assert topicals.whole_rubric_media(item, vault)
    sidecar_id = next(k for k, v in catalog['assets'].items() if v['path'] == media + '.json')
    catalog['assets'][sidecar_id]['course'] = 'P2'  # a sidecar of another course is never followed
    catalog_path.write_text(json.dumps(catalog))
    with pytest.raises(ValueError):  # so the survivor's unrelated sidecar is checked, and fails
        topicals.whole_rubric_media(item, vault)


def test_attestation_pinned_media_is_held_even_when_pins_are_included(vault):
    """A prepared attestation compares its reference string literally, so that image cannot move."""
    base = MEDIA.format('9701')
    pinned = base + 'native-ms-p2-2ea577632076-6ca5927035237706.png'
    write_asset(vault, pinned, png('attested'), metadata={'course': '9701', 'kind': 'Questions/Media'})
    attestation = {'media': {'ctx': {'native-ms-p2.png': {'reference': pinned}}}}
    write_asset(vault, 'Library/Courses/9701/Sources/Provenance/prepared-v1/' + 'e' * 64 + '.json',
                json.dumps(attestation).encode())
    decided = organize.decide(vault)
    plan = organize.build_plan(vault, decided, include_pinned=True)
    assert [h['reason'] for h in plan['held']] == ['prepared attestation pin (immutable reference string)']
    assert not any(m['from'] == pinned for m in plan['moves'])


def test_a_region_cut_from_a_mark_scheme_pdf_is_a_key_not_an_mcq():
    """Keys are sidecars whose region comes from a *_ms_* PDF; they used to fall through to the MCQ path-segment vote."""
    import importlib.util
    from pathlib import Path
    spec = importlib.util.spec_from_file_location("organize", Path(__file__).resolve().parents[1] / "build/organize_question_library.py")
    organize = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(organize)
    assert organize.MARK_SCHEME_PDF.search("/lib/9701/Sources/9701_w25_ms_11.pdf")
    assert not organize.MARK_SCHEME_PDF.search("/lib/9701/Sources/9701_w25_qp_11.pdf")
    assert organize.MARK_SCHEME_PDF.search("/lib/9702/Sources/9702_s20_ms_12.pdf")


def test_cli_apply_accepts_a_clean_normalize_plan(vault, tmp_path):
    out = tmp_path / 'out'
    organize.main(['plan', '--vault', str(vault), '--out', str(out)])
    report = json.loads((out / 'plan.json').read_text())
    report['tool'] = 'normalize_question_names'
    (out / 'normalize.json').write_text(json.dumps(report))
    organize.main(['apply', '--plan', str(out / 'normalize.json'), '--journal', str(tmp_path / 'n.json'), '--yes'])
    organize.main(['rollback', '--journal', str(tmp_path / 'n.json')])
    report['errors'] = [{'x': 1}]
    (out / 'bad.json').write_text(json.dumps(report))
    with pytest.raises(SystemExit, match='clean'):
        organize.main(['apply', '--plan', str(out / 'bad.json'), '--journal', str(tmp_path / 'b.json'), '--yes'])


# ---------- source-practice crops filed under their courses ----------
def test_booklet_questions_get_a_topic_name_not_nosrc():
    digest = sha(b'b')
    name = names.canonical_name('P2', 'long', digest, topic='C2 Algebra: Remainder & Factor Theorems – Questions', label='3')
    assert name == f'P2_c2-algebra-remainder-factor-theorems_q03_long_{digest[:12]}.png' and names.is_canonical(name)
    assert names.canonical_name('D1', 'key', digest, topic='D1 Algorithms - Bin packing', label='12b').startswith(
        'D1_d1-algorithms-bin-packing_q12b_key_')
    assert names.canonical_name('P2', 'long', digest, topic='C2 Algebra', label='Figure') == f'P2_nosrc_long_{digest[:12]}.png'
    paper = names.canonical_name('9701', 'mcq', digest, qid='9701_m17_12_q1', topic='9701_m17_12', label='1')
    assert paper == f'9701_m17_12_q01_mcq_{digest[:12]}.png'          # an exam-paper id always wins


def source_vault(tmp_path):
    vault = tmp_path / 'STEM Tutor'
    vault.mkdir()
    refs = {}
    for label in ('q', 'k', 'cell', 'booklet'):
        refs[label] = f'Library/SourcePractice/Media/{sha(png(label))}-{sha(label.encode())[:16]}.png'
        write_asset(vault, refs[label], png(label), metadata={'kind': 'SourcePractice/Media'})
    chem = {'id': '9701_s19_11_q4', 'official_qid': '9701_s19_11_q4', 'course': '9701', 'kind': 'mcq',
            'question_media': [refs['q']], 'context_media': [], 'mark_scheme_media': [refs['k'], refs['cell']]}
    phys = {'id': '9702_s19_11_q8', 'official_qid': '9702_s19_11_q8', 'course': '9702', 'kind': 'mcq',
            'question_media': [], 'context_media': [], 'mark_scheme_media': [refs['cell']]}
    booklet = {'id': 'occurrence-1', 'official_qid': None, 'course': 'D1', 'kind': 'structured', 'label': '3',
               'source': 'D1 Algorithms - Bin packing', 'question_media': [refs['booklet']], 'context_media': [],
               'mark_scheme_media': []}
    release = json.dumps({'items': [chem, phys, booklet]}).encode()
    write_asset(vault, f'Library/SourcePractice/Releases/{sha(release)}.json', release)
    topical = MEDIA.format('9701') + f'MCQ/9701_s19_11_q04_mcq_{sha(png("topical"))[:12]}.png'
    write_asset(vault, topical, png('topical'), metadata={'course': '9701', 'kind': 'Questions/Media'})
    return vault, refs


def test_source_practice_crops_move_into_course_folders_and_shared_cells_into_shared(tmp_path):
    vault, refs = source_vault(tmp_path)
    decided = organize.decide(vault)
    report = organize.build_plan(vault, decided, scope='sourcepractice')
    assert report['errors'] == [] and decided[3] == []
    to = {m['from']: m['to'] for m in report['moves']}
    assert to[refs['q']] == MEDIA.format('9701') + f'MCQ/9701_s19_11_q04_mcq_{sha(png("q"))[:12]}.png'
    assert to[refs['k']] == MEDIA.format('9701') + f'Keys/9701_s19_11_q04_key_{sha(png("k"))[:12]}.png'
    assert to[refs['booklet']] == MEDIA.format('D1') + f'Long/D1_d1-algorithms-bin-packing_q03_long_{sha(png("booklet"))[:12]}.png'
    assert to[refs['cell']] == f'Library/Shared/Questions/Media/Keys/shared_nosrc_key_{sha(png("cell"))[:12]}.png'
    assert not any(t.startswith('Library/SourcePractice/') for t in to.values())
    repeated = organize.duplicate_questions(decided[2])
    assert [(d['course'], d['question'], d['role'], d['count']) for d in repeated] == [('9701', '9701_s19_11_q04', 'mcq', 2)]


def test_applied_source_practice_moves_keep_release_references_and_file_the_catalog(tmp_path):
    vault, refs = source_vault(tmp_path)
    report = organize.build_plan(vault, organize.decide(vault), scope='sourcepractice')
    original = (vault / 'Library/catalog.json').read_bytes()
    organize.journalled.apply(report, tmp_path / 'Archive/source.json')
    library = AssetLibrary(vault)
    for label, ref in refs.items():
        assert library.read(ref) == png(label)                       # the release's strings still resolve
    assert not list((vault / 'Library/SourcePractice/Media').glob('*.png'))
    record = library.record(refs['q'])
    assert record['path'].startswith(MEDIA.format('9701')) and (record['course'], record['kind']) == ('9701', 'Questions/Media')
    assert 'course' not in library.record(refs['cell']) and library.record(refs['cell'])['kind'] == 'Questions/Media'
    assert organize.build_plan(vault, organize.decide(vault), scope='sourcepractice')['moves'] == []
    organize.journalled.rollback(tmp_path / 'Archive/source.json')
    assert (vault / 'Library/catalog.json').read_bytes() == original


def test_extraction_stores_new_crops_in_the_course_folder(tmp_path):
    vault = tmp_path / 'STEM Tutor'
    vault.mkdir()
    write_asset(vault, MEDIA.format('9702') + 'MCQ/existing.png', png('existing'))
    data = png('fresh')
    legacy = f'Library/SourcePractice/Media/{sha(data)}-1111111111111111.png'
    names.store_question_media(vault, data, legacy, course='9702', role='mcq', qid='9702_w20_12_q7',
                               metadata={'provenance': {'page': 3}})
    library = AssetLibrary(vault)
    record = library.record(legacy)
    assert record['path'] == MEDIA.format('9702') + f'MCQ/9702_w20_12_q07_mcq_{sha(data)[:12]}.png'
    assert (record['course'], record['kind']) == ('9702', 'Questions/Media') and library.read(legacy) == data
    assert not (vault / 'Library/SourcePractice').exists()             # nothing written there any more
    again = f'Library/SourcePractice/Media/{sha(data)}-2222222222222222.png'   # same crop, another binding
    names.store_question_media(vault, data, legacy, course='9702', role='mcq', qid='9702_w20_12_q7',
                               metadata={'provenance': {'page': 3}})
    names.store_question_media(vault, data, again, course='9702', role='mcq', qid='9702_w20_12_q7',
                               metadata={'provenance': {'page': 4}})
    records = AssetLibrary(vault).records()
    assert len(records) == 2 and AssetLibrary(vault).record(again)['path'] == record['path']
    with pytest.raises(ValueError, match='other content'):
        names.store_question_media(vault, png('other'), legacy, course='9702', role='mcq')
