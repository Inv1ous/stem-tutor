"""Source identifiers, official keys, complete crops and atomic local publication."""
import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'build'))
import topicals
from fixtures import make_vault


def _publish_vault(tmp_path):
    from tutorlib.asset_library import write_asset
    vault = make_vault(tmp_path)
    for name in ('9702_s23_qp_22.pdf', '9702_s23_ms_22.pdf'):
        relative = f'Library/Courses/9702/Papers/{name}'
        write_asset(vault, relative, b'synthetic paper', aliases=[f'Papers/9702/{name}'])
    return vault


def test_canonical_refs_match_both_topical_layouts():
    assert topicals.references('7 - (9701/12_Summer_2020_Q3)') == ['9701_s20_12_q3']
    assert topicals.references('2. 9702_w17_qp_23 Q: 1') == ['9702_w17_23_q1']
    assert topicals.references('9701_s23_qp_11  09  B') == []


def test_official_table_keys_reject_conflicts():
    text = '1 9701_s23_qp_11 2 C  50 9701_m24_qp_12 3 A'
    assert topicals.table_keys(text) == {'9701_s23_11_q2': 'C', '9701_m24_12_q3': 'A'}
    with pytest.raises(ValueError, match='conflict'):
        topicals.table_keys(text + '\n3 9701_s23_qp_11 2 D')


def test_crop_ranges_keep_continuation_but_not_next_question():
    ranges = topicals.question_regions([(0, 100, 'q1'), (2, 220, 'q2')], 0, [800, 800, 800])
    assert ranges == [(0, 100, 770), (1, 50, 770), (2, 50, 216)]


def test_atomic_publish_preserves_existing_pointer_on_invalid_bank(tmp_path):
    vault = _publish_vault(tmp_path)
    bank = tmp_path / 'batch'
    bank.mkdir()
    (bank / 'bank.json').write_text(json.dumps({'format_version': 1, 'syllabus_versions': {'9702': '2025-2027'}, 'items': []}))
    result = topicals.publish(bank, vault, allow_unbound_legacy=True)
    pointer = vault / '.tutor/topicals/CURRENT'
    previous = pointer.read_text()
    assert result['items'] == 0
    (bank / 'bank.json').write_text(json.dumps({'format_version': 1, 'syllabus_versions': {'9702': '2025-2027'}, 'items': [
        {'id': 'missing-image', 'image': 'Assets/topicals/missing.png'}]}))
    with pytest.raises(ValueError):
        topicals.publish(bank, vault, allow_unbound_legacy=True)
    assert pointer.read_text() == previous


def test_publish_never_touches_learner_state(tmp_path):
    vault, bank = _publish_vault(tmp_path), tmp_path / 'batch'
    bank.mkdir(); (vault / '.tutor/state').mkdir(parents=True)
    state = vault / '.tutor/state/learner.json'; state.write_bytes(b'{"untouched":true}')
    (bank / 'bank.json').write_text(json.dumps({'format_version': 1, 'syllabus_versions': {'9702': '2025-2027'}, 'items': []}))
    topicals.publish(bank, vault, allow_unbound_legacy=True)
    assert state.read_bytes() == b'{"untouched":true}'


def test_publish_rejects_malformed_item_before_changing_current(tmp_path):
    vault, bank = _publish_vault(tmp_path), tmp_path / 'batch'
    bank.mkdir()
    data = {'format_version': 1, 'syllabus_versions': {'9702': '2025-2027'}, 'items': []}
    (bank / 'bank.json').write_text(json.dumps(data))
    topicals.publish(bank, vault, allow_unbound_legacy=True)
    pointer = vault / '.tutor/topicals/CURRENT'; previous = pointer.read_bytes()
    data['items'] = [{'id': 'no-verified-answer'}]
    (bank / 'bank.json').write_text(json.dumps(data))
    with pytest.raises(ValueError):
        topicals.publish(bank, vault, allow_unbound_legacy=True)
    assert pointer.read_bytes() == previous


def test_publish_rejects_symlink_asset_without_writing_outside_vault(tmp_path):
    from tutorlib.asset_library import write_asset
    vault, bank = _publish_vault(tmp_path), tmp_path / 'batch'
    bank.mkdir(); (bank / 'Assets/topicals').mkdir(parents=True)
    (bank / 'Assets/topicals/q.png').write_bytes(b'question')
    outside = tmp_path / 'outside'; outside.mkdir()
    target = outside / 'q.png'; target.write_bytes(b'outside')
    canonical = 'Library/Courses/9702/Questions/Media/q.png'
    write_asset(vault, canonical, b'question', aliases=['Assets/topicals/q.png'])
    (vault / canonical).unlink()
    (vault / canonical).symlink_to(target)
    data = {'format_version': 1, 'syllabus_versions': {'9702': '2025-2027'}, 'items': [{
        'id':'t1','kind':'mcq','kcs':['9702-2.1.1'],'difficulty':3,'marks':1,
        'source':{'type':'past','qid':'9702_s23_12_q1'},'stem':'Which quantity is a vector?',
        'answer':'A','options':{'A':'velocity','B':'speed','C':'distance','D':'time'},
        'image':'Assets/topicals/q.png',
        'topical':{'reviewed':True,'revision':'2025-2027','requires':['9702-2.1'],
                   'chapters':['9702-2.1'],'support':{}}}]}
    (bank / 'bank.json').write_text(json.dumps(data))
    with pytest.raises(ValueError, match='unsafe|outside|symlink'):
        topicals.publish(bank, vault, allow_unbound_legacy=True)
    assert target.read_bytes() == b'outside'
    assert not (vault / '.tutor/topicals/CURRENT').exists()


def test_image_questions_replace_incomplete_extracted_options():
    assert topicals.source_options({'A': 'one', 'B': '', 'C': 'three', 'D': 'four'}) == {
        letter: '(in the source picture)' for letter in 'ABCD'}
    complete = dict(zip('ABCD', ['one', 'two', 'three', 'four']))
    assert topicals.source_options(complete) == complete


def test_rotated_scan_is_not_cropped_without_physical_review(tmp_path, monkeypatch):
    import pymupdf
    monkeypatch.setattr(topicals, 'LIBRARY', tmp_path)
    folder = tmp_path / 'Physics 9702 AS Topicals'; folder.mkdir()
    path = folder / 'rotated.pdf'
    doc = pymupdf.open(); page = doc.new_page(width=300, height=400)
    page.insert_text((30, 80), '1. 9702_s20_qp_12 Q: 1')
    pix = pymupdf.Pixmap(pymupdf.csGRAY, pymupdf.IRect(0, 0, 200, 80)); pix.clear_with(180)
    page.insert_image(pymupdf.Rect(30, 100, 230, 180), stream=pix.tobytes('png'))
    page.set_rotation(90); doc.save(path); doc.close()
    questions, files = topicals.source_index([path])
    assert questions == {}
    assert files['Physics 9702 AS Topicals/rotated.pdf']['rotation_review_pages'] == [1]


def test_default_source_index_uses_catalogued_course_library_sources(tmp_path, monkeypatch):
    import pymupdf
    from tutorlib.asset_library import write_asset
    vault = tmp_path / 'STEM Tutor'
    vault.mkdir()
    relative = 'Library/Courses/9702/Sources/Library/Physics 9702 AS Topicals/rotated.pdf'
    doc = pymupdf.open()
    page = doc.new_page(width=300, height=400)
    page.insert_text((30, 80), '1. 9702_s20_qp_12 Q: 1')
    page.set_rotation(90)
    data = doc.tobytes()
    doc.close()
    write_asset(vault, relative, data)
    monkeypatch.setattr(topicals, 'LIBRARY', None)
    monkeypatch.setattr(topicals.source_library, 'learner_vault', lambda: vault)
    monkeypatch.delenv('STEM_LIBRARY_ROOT', raising=False)
    questions, sources = topicals.source_index([vault / relative])
    assert questions == {}
    assert sources[relative]['rotation_review_pages'] == [1]
    (vault / relative).write_bytes(b'tampered source')
    with pytest.raises(ValueError, match='digest mismatch'):
        topicals.source_index([vault / relative])


def test_extracted_question_media_uses_only_registered_course_library(tmp_path):
    from tutorlib.asset_library import AssetLibrary
    vault = tmp_path / 'STEM Tutor'
    vault.mkdir()
    relative = topicals.store_question_media(vault, '9702', '9702_s23_12_q1', b'synthetic crop')
    assert relative.startswith('Library/Courses/9702/Questions/Media/')
    assert AssetLibrary(vault).read(relative) == b'synthetic crop'
    assert not (vault / 'Assets').exists()
    assert not (vault / 'build').exists()
    with pytest.raises(ValueError, match='identifier'):
        topicals.store_question_media(vault, '../escape', 'question', b'bytes')


def test_publish_registered_media_changes_only_bank_pointer_and_preserves_input(tmp_path):
    from tutorlib.asset_library import write_asset
    vault = _publish_vault(tmp_path)
    (vault / '.tutor/packs/v1/papers.json').write_text('{"papers": []}')
    relative = 'Library/Courses/9702/Questions/Media/question.png'
    write_asset(vault, relative, b'synthetic crop', aliases=['Assets/topicals/question.png'])
    bank = tmp_path / 'batch'
    bank.mkdir()
    item = {'id':'t1','kind':'mcq','kcs':['9702-2.1.1'],'difficulty':3,'marks':1,
            'source':{'type':'past','qid':'9702_s23_12_q1'},'stem':'Which quantity is a vector?',
            'answer':'A','options':{'A':'velocity','B':'speed','C':'distance','D':'time'},
            'image':'Assets/topicals/question.png',
            'topical':{'reviewed':True,'revision':'2025-2027','requires':['9702-2.1'],
                       'chapters':['9702-2.1'],'support':{}}}
    candidate = bank / 'bank.json'
    candidate.write_text(json.dumps({'format_version':1,'syllabus_versions':{'9702':'2025-2027'},'items':[item]}))
    before = candidate.read_bytes()
    result = topicals.publish(bank, vault, expected_current=None)
    published = json.loads((vault / result['release'] / 'bank.json').read_text())
    assert published['items'][0]['image'] == relative
    assert published['items'][0]['id'] == item['id']
    assert published['items'][0]['answer'] == item['answer']
    assert candidate.read_bytes() == before
    assert not (vault / 'Assets').exists() and not (bank / 'Assets').exists()
    assert not (vault / '.tutor/topicals' / result['version']).exists()
    from tutorlib.asset_library import AssetLibrary
    assert AssetLibrary(vault).read(result['release'] + '/bank.json') == (vault / result['release'] / 'bank.json').read_bytes()


def test_publish_resolves_legacy_source_aliases_and_requires_them(tmp_path):
    from tutorlib.asset_library import write_asset

    def candidate_at(root, missing=False):
        vault = _publish_vault(root)
        image = 'Library/Courses/9702/Questions/Media/question.png'
        write_asset(vault, image, b'synthetic crop', aliases=['Assets/topicals/question.png'])
        source_file = 'Library/Courses/9702/Sources/Library/Physics 9702 AS Topicals/question.pdf'
        mark_file = 'Library/Courses/9702/Sources/Library/Physics 9702 AS Topicals/mark-scheme.pdf'
        write_asset(vault, source_file, b'question PDF', aliases=['sources/library/Physics 9702 AS Topicals/question.pdf'])
        if not missing:
            write_asset(vault, mark_file, b'mark scheme PDF', aliases=['sources/library/Physics 9702 AS Topicals/mark-scheme.pdf'])
        bank = root / 'batch'
        bank.mkdir()
        item = {'id':'topical-9702_s23_12_q1','kind':'mcq','kcs':['9702-2.1.1'],'difficulty':3,'marks':1,
                'source':{'type':'past','qid':'9702_s23_12_q1',
                          'library':{'file':'Physics 9702 AS Topicals/question.pdf','page':1,'box':[20,30,40,50]},
                          'mark_scheme':{'file':'Physics 9702 AS Topicals/mark-scheme.pdf','page':2}},
                'stem':'Which quantity is a vector?','answer':'A',
                'options':{'A':'velocity','B':'speed','C':'distance','D':'time'},
                'image':'Assets/topicals/question.png',
                'topical':{'reviewed':True,'revision':'2025-2027','requires':['9702-2.1'],
                           'chapters':['9702-2.1'],'support':{}}}
        (bank / 'bank.json').write_text(json.dumps({'format_version':1,'syllabus_versions':{'9702':'2025-2027'},'items':[item]}))
        return vault, bank, item, source_file, mark_file

    vault, bank, item, source_file, mark_file = candidate_at(tmp_path / 'valid')
    result = topicals.publish(bank, vault, expected_current=None)
    published = json.loads((vault / result['release'] / 'bank.json').read_text())['items'][0]
    assert published['id'] == item['id'] and published['answer'] == item['answer']
    assert published['source']['library']['file'] == source_file
    assert published['source']['mark_scheme']['file'] == mark_file
    assert published['image'] == 'Library/Courses/9702/Questions/Media/question.png'

    missing_vault, missing_bank, _, _, _ = candidate_at(tmp_path / 'missing', missing=True)
    with pytest.raises(ValueError, match='unknown asset reference'):
        topicals.publish(missing_bank, missing_vault, expected_current=None)
    assert not (missing_vault / '.tutor/topicals/CURRENT').exists()


def test_publish_rejects_stale_preparation_binding_before_release_write(tmp_path):
    from tutorlib.asset_library import write_asset
    vault = _publish_vault(tmp_path)
    write_asset(vault, 'Library/Courses/9702/Questions/Media/setup.png', b'synthetic')
    bank = tmp_path / 'batch'
    bank.mkdir()
    (bank / 'bank.json').write_text(json.dumps({'format_version':1,'syllabus_versions':{'9702':'2025-2027'},'items':[]}))
    (bank / 'report.json').write_text(json.dumps({'previous_version': 'v-prepared-against'}))
    pointer = vault / '.tutor/topicals/CURRENT'
    pointer.parent.mkdir(parents=True, exist_ok=True)
    pointer.write_text('v-newer\n')
    with pytest.raises(ValueError, match='changed during preparation'):
        topicals.publish(bank, vault)
    assert pointer.read_text() == 'v-newer\n'
    assert not list((vault / 'Library/Shared/Topicals/Releases').glob('v*')) if (vault / 'Library/Shared/Topicals/Releases').exists() else True


def test_publish_requires_binding_for_new_batches(tmp_path):
    from tutorlib.asset_library import write_asset
    vault, bank = _publish_vault(tmp_path), tmp_path / 'batch'
    write_asset(vault, 'Library/Courses/9702/Questions/Media/setup.png', b'synthetic')
    bank.mkdir()
    (bank / 'bank.json').write_text(json.dumps({'format_version':1,'syllabus_versions':{'9702':'2025-2027'},'items':[]}))
    with pytest.raises(ValueError, match='no preparation CURRENT binding'):
        topicals.publish(bank, vault)
    assert not (vault / '.tutor/topicals/CURRENT').exists()


def test_topical_release_report_is_registered_with_unchanged_bytes(tmp_path):
    from tutorlib.asset_library import AssetLibrary
    vault = _publish_vault(tmp_path)
    bank = tmp_path / 'batch'
    bank.mkdir()
    (bank / 'bank.json').write_text(json.dumps({'format_version':1,'syllabus_versions':{'9702':'2025-2027'},'items':[]}))
    report = b'{"review":"existing evidence"}\n'
    (bank / 'report.json').write_bytes(report)
    result = topicals.publish(bank, vault, expected_current=None)
    assert AssetLibrary(vault).read(result['release'] + '/report.json') == report
    assert (vault / '.tutor/topicals/CURRENT').read_text().strip() == result['version']
    assert not (vault / '.tutor/topicals' / result['version']).exists()


def test_default_topical_report_location_is_workspace_work(tmp_path, monkeypatch):
    monkeypatch.setattr(topicals, 'ROOT', tmp_path / 'code')
    assert topicals.default_output().parent == tmp_path / 'Work/Topicals'
