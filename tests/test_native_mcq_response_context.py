"""Positive response semantics use actual registered sources in disposable vaults."""
import copy
from dataclasses import asdict
import hashlib
import json
from pathlib import Path
import shutil
import sys

import pymupdf
import pytest
from library_assets import canonical_path, copy_to_vault
from tutorlib.asset_library import AssetLibrary

ROOT = Path(__file__).resolve().parents[2]
WORKER = ROOT / 'Work/Workers/extraction/overnight-20261105-10pct'
sys.path[:0] = [str(WORKER), str(ROOT / 'stem-tutor/extraction')]
import prepared_source_packet as helper
import lightweight_verification as check
import source_practice
import native_mcq_response_context as response

INVENTORY = json.loads((WORKER / 'native-mcq-context-inventory.json').read_bytes())
PREPARATIONS = [p for p in INVENTORY['preparations'] if p['target_count']]


@pytest.fixture(scope='module')
def source_packages(tmp_path_factory):
    root = tmp_path_factory.mktemp('native-response-context')
    vault = root / 'vault'
    vault.mkdir()
    packages = {}
    with pytest.MonkeyPatch.context() as patch:
        patch.setattr(source_practice, 'WORKERS', root / 'no-workers')
        for prep in PREPARATIONS:
            for source in prep['sources'].values():
                copy_to_vault(canonical_path(source['reference']), vault)
            package = root / prep['paper']
            shutil.copytree(ROOT / prep['package'], package)
            replay = helper.verify_prepared(vault, package, source_practice.verify)
            packages[prep['paper']] = (package, replay)
    return vault, packages


def test_all_65_fresh_candidates_gain_only_source_response_proof(source_packages):
    vault, packages = source_packages
    seen = set()
    contexts = set()
    for prep in PREPARATIONS:
        package, replay = packages[prep['paper']]
        for target in prep['targets']:
            row = next(r for r in replay['items'] if r['id'] == target['qid'])
            before = copy.deepcopy(row)
            manifest, packet = helper.prepared_packet(package, replay, row, AssetLibrary(vault))
            assert manifest['status'] == 'source_manifest', (row['id'], manifest)
            assert packet == check.build_packet(row)
            assert row == before
            proof = manifest['evidence']['response_context']
            assert proof['qid'] == row['id']
            assert proof['source_sha256'] == prep['sources']['qp']['sha256']
            assert proof['scope']['question_numbers'] == list(range(31, 41))
            assert proof['status'] == 'source_response_context'
            assert proof['model_calls'] == 0
            assert row['review_reasons'] == target['review_reasons']
            for context in proof['contexts']:
                contexts.add((proof['source_sha256'], context['region']['page']))
            seen.add(row['id'])
    assert len(seen) == 65 and len(contexts) == 19


def sample(source_packages, paper='9701_s17_11'):
    vault, packages = source_packages
    package, replay = packages[paper]
    qid = next(p for p in PREPARATIONS if p['paper'] == paper)['targets'][0]['qid']
    row = next(r for r in replay['items'] if r['id'] == qid)
    raw = AssetLibrary(vault).read(replay['sources']['qp']['reference'])
    return vault, package, replay, row, raw


def rewrite_page(doc, page_number, before, after, *, count=1):
    """Substitute actual native PDF operators, without a test-only word adapter."""
    page = doc[page_number - 1]
    streams = page.get_contents()
    assert len(streams) == 1
    raw = doc.xref_stream(streams[0])
    assert raw.count(before) >= count
    doc.update_stream(streams[0], raw.replace(before, after, count))


def substituted_document(raw, mutate):
    with pymupdf.open(stream=raw, filetype='pdf') as doc:
        mutate(doc)
        result = doc.tobytes()
    return pymupdf.open(stream=result, filetype='pdf')


@pytest.mark.parametrize('fault', ['body_predicate', 'bottom_rule', 'header_letter', 'body_column', 'outer_edge', 'top_rule'])
def test_context_crop_never_guesses_missing_native_content(source_packages, fault):
    _, _, _, row, raw = sample(source_packages)
    region = copy.deepcopy(row['context_regions'][0])
    with pymupdf.open(stream=raw, filetype='pdf') as doc:
        page = doc[region['page'] - 1]
        if fault == 'body_predicate': region['box'][3] = 234 / page.rect.height
        elif fault == 'bottom_rule': region['box'][3] = 258 / page.rect.height
        elif fault == 'header_letter': region['box'][0] = 130 / page.rect.width
        elif fault == 'body_column': region['box'][2] = 379 / page.rect.width
        elif fault == 'outer_edge': region['box'][0] = 72 / page.rect.width
        else: region['box'][1] = 190 / page.rect.height
        with pytest.raises(ValueError):
            response._context(page, region)


@pytest.mark.parametrize(('before', 'after'), [
    (b'(only are )Tj', b'( are )Tj'),
    (b'( and )Tj', b'( or )Tj'),
    (b'(only are )Tj', b'(only is )Tj'),
    (b'(only are )Tj', b'(only are 1 )Tj'),
    (b'(only are )Tj', b'()Tj'),
    (b'[(A B )-5.5 (C D )]TJ', b'[(A B )-5.5 (C A )]TJ'),
    (b'[(A B )-5.5 (C D )]TJ', b'[(A B )-5.5 (C )]TJ'),
    (b'70.68 632.36 0.48 -51.6 re f', b''),
    (b'173.46 652.7 0.48 -19.86 re f', b''),
    (b'70.68 581.24 102.78 -0.48 re f', b''),
    (b'70.68 632.84 308.76 -0.48 re f', b''),
    (b'379.44 632.84 102.3 -0.48 re f', b''),
])
def test_real_native_word_and_rule_substitutions_are_structurally_rejected(source_packages, before, after):
    _, _, _, row, raw = sample(source_packages)
    page = row['context_regions'][0]['page']
    with substituted_document(raw, lambda doc: rewrite_page(doc, page, before, after)) as doc:
        with pytest.raises(ValueError):
            response._prove_document(doc, row)


def test_complete_changed_cell_is_read_and_conflicting_repeat_holds(source_packages):
    _, _, _, row, raw = sample(source_packages)
    region = row['context_regions'][0]
    before = b'(1)Tj /TT1 1 Tf 0.0001 Tc 0.0009 Tw 0.558 0 Td ( only )Tj'
    after = before.replace(b'(1)', b'(3)', 1)
    with substituted_document(raw, lambda d: rewrite_page(d, region['page'], before, after)) as doc:
        proof = response._context(doc[region['page'] - 1], region)
        assert proof['column_map']['D'] == [3]
        assert proof['columns'][-1]['literal'] == '3 only is correct'
        with pytest.raises(ValueError, match='repeat_maps_conflict'):
            response._prove_document(doc, row)


def test_native_header_swap_derives_actual_correspondence_everywhere(source_packages):
    _, _, _, row, raw = sample(source_packages)
    def mutate(doc):
        for region in row['context_regions']:
            rewrite_page(doc, region['page'], b'[(A B )-5.5 (C D )]TJ', b'[(B A )-5.5 (C D )]TJ')
    with substituted_document(raw, mutate) as doc:
        proof = response._prove_document(doc, row)
        for context in proof['contexts']:
            assert [c['letter'] for c in context['columns']] == list('BACD')
            assert context['column_map']['B'] == [1, 2, 3]
            assert context['column_map']['A'] == [1, 2]


@pytest.mark.parametrize('which', ['second', 'third'])
@pytest.mark.parametrize('fault', ['conflict', 'incomplete'])
def test_each_applicable_repeat_is_mandatory_not_a_first_or_majority_vote(source_packages, which, fault):
    _, _, _, row, raw = sample(source_packages, '9701_w18_11')
    region = row['context_regions'][1 if which == 'second' else 2]
    def mutate(doc):
        page = doc[region['page'] - 1]
        if fault == 'conflict':
            streams = page.get_contents()
            assert len(streams) == 1
            text = doc.xref_stream(streams[0])
            import re
            swapped, count = re.subn(rb'\[\(A B \)([-\d.]+) \(C D \)\]TJ',
                                     rb'[(B A )\1 (C D )]TJ', text)
            assert count == 1
            doc.update_stream(streams[0], swapped)
        else:
            page.insert_text((110, 145), 'unexpected', fontsize=8)
    with substituted_document(raw, mutate) as doc:
        with pytest.raises(ValueError):
            response._prove_document(doc, row)


@pytest.mark.parametrize('fault', ['duplicate_header', 'straddling_word', 'unknown_fill', 'thin_crossing',
                                  'image', 'extra_grid', 'no_rules', 'invisible_text', 'clip_rules'])
def test_ambiguous_or_overlaid_real_native_grid_is_not_positive_proof(source_packages, fault):
    _, _, _, row, raw = sample(source_packages)
    region = row['context_regions'][0]
    def mutate(doc):
        page = doc[region['page'] - 1]
        if fault == 'duplicate_header': page.insert_text((120, 205), 'A', fontsize=11)
        elif fault == 'straddling_word': page.insert_text((170, 250), 'crossing', fontsize=11)
        elif fault == 'unknown_fill': page.draw_rect(pymupdf.Rect(100, 235, 140, 245), fill=(1, 1, 1), color=None)
        elif fault == 'thin_crossing': page.draw_rect(pymupdf.Rect(100, 235, 140, 235.48), fill=(0, 0, 0), color=None)
        elif fault == 'image':
            pix = pymupdf.Pixmap(pymupdf.csRGB, pymupdf.IRect(0, 0, 2, 2))
            pix.clear_with(255)
            page.insert_image(pymupdf.Rect(100, 235, 140, 245), pixmap=pix)
        elif fault == 'invisible_text': page.insert_text((100, 250), 'only', fontsize=8, render_mode=3)
        else:
            streams = page.get_contents()
            text = doc.xref_stream(streams[0])
            if fault == 'no_rules':
                import re
                # Remove every filled rule, leaving native words untouched.
                text = re.sub(rb'(?:-?\d+(?:\.\d+)? ){3}-?\d+(?:\.\d+)? re f', b'', text)
            elif fault == 'clip_rules':
                text = b'q 0 0 595 600 re W n ' + text + b' Q'
            else:
                start = text.index(b'[(A B )-5.5 (C D )]TJ')
                # Duplicate the rule geometry as genuine native filled rules.
                first = text.index(b'ET 70.68 653.18', start) + 3
                last = text.index(b' BT 0 Tc 10.9755', first)
                fragment = text[first:last]
                text += b' q 1 0 0 1 0 100 cm ' + fragment + b' Q'
            doc.update_stream(streams[0], text)
    with substituted_document(raw, mutate) as doc:
        with pytest.raises(ValueError):
            response._prove_document(doc, row)


@pytest.mark.parametrize('fault', ['missing_repeat', 'foreign_region', 'foreign_hash', 'q1', 'q30',
                                  'multiple_pages', 'substantive_flag', 'unknown_flag', 'duplicate_flag'])
def test_scope_flags_and_origins_cannot_be_overridden_by_a_valid_table(source_packages, fault):
    vault, _, replay, original, _ = sample(source_packages)
    replay = copy.deepcopy(replay)
    row = next(r for r in replay['items'] if r['id'] == original['id'])
    if fault == 'missing_repeat': row['context_regions'].pop()
    elif fault == 'foreign_region': row['context_regions'][0]['source_id'] = PREPARATIONS[1]['sources']['qp']['reference']
    elif fault == 'foreign_hash': row['context_regions'][0]['source_sha256'] = '0' * 64
    elif fault in ('q1', 'q30'):
        row['id'] = row['canonical_id'] = row['official_qid'] = row['source'] + '_' + fault
        row['label'] = fault[1:]
    elif fault == 'multiple_pages': row['regions'].append(copy.deepcopy(row['regions'][0]))
    elif fault == 'duplicate_flag': row['review_reasons'].append(row['review_reasons'][0])
    else: row['review_reasons'].append(fault)
    before = copy.deepcopy(row)
    proof = response.derive(row, AssetLibrary(vault), replay, dpi=72)
    assert proof['status'] == 'held' and row == before


def test_unknown_source_pin_never_turns_survey_into_authorization(source_packages, monkeypatch):
    vault, _, replay, row, _ = sample(source_packages)
    monkeypatch.setitem(response.AUTHORITIES, row['source'],
                        (replay['sources']['qp']['reference'], '0' * 64))
    assert response.derive(row, AssetLibrary(vault), replay, dpi=72)['status'] == 'held'


@pytest.mark.parametrize('paper', [p['paper'] for p in PREPARATIONS])
def test_real_shared_table_cannot_clear_a_multiple_page_question(source_packages, paper):
    vault, packages = source_packages
    package, replay = packages[paper]
    row = next(r for r in replay['items'] if 'multiple_pages_require_review' in r['review_reasons']
               and 'shared_context_requires_review' in r['review_reasons'])
    before = copy.deepcopy(row)
    manifest, packet = helper.prepared_packet(package, replay, row, AssetLibrary(vault))
    assert manifest['status'] == 'held' and packet is None and row == before


def test_current_guard_excludes_shared_candidate_before_response_proof(source_packages, monkeypatch):
    vault, package, original_replay, row, _ = sample(source_packages)
    monkeypatch.setattr(source_practice, '_guard_holds', lambda: {row['id']: ['guard2:disposable-shared-proof']})
    replay = helper.verify_prepared(vault, package, source_practice.verify)
    assert row['id'] not in {r['id'] for r in replay['items']}
    assert {'id': row['id'], 'reasons': ['guard2:disposable-shared-proof']} in replay['held']
    assert all(h in replay['held'] for h in original_replay['held'])
    with pytest.raises(ValueError, match='absent'):
        helper.prepared_packet(package, replay, row, AssetLibrary(vault))


@pytest.mark.parametrize('extra', ['multiple_pages_require_review', 'unknown_source_review',
                                 'source_segmentation_incomplete', {'unknown': 'flag'}])
def test_shared_branch_cannot_waive_any_extra_or_malformed_flag(source_packages, extra):
    vault, package, replay, original, _ = sample(source_packages)
    replay = copy.deepcopy(replay)
    row = next(r for r in replay['items'] if r['id'] == original['id'])
    row['review_reasons'].append(extra)
    manifest, packet = helper.prepared_packet(package, replay, row, AssetLibrary(vault))
    assert manifest['status'] == 'held' and packet is None
    assert 'response_context' not in manifest.get('evidence', {})


@pytest.mark.parametrize('fault', ['moved_boundary', 'unattached_preface', 'no_numbered_statement'])
def test_section_b_and_actual_statement_scope_are_required(source_packages, fault):
    _, _, _, row, raw = sample(source_packages)
    def mutate(doc):
        if fault == 'moved_boundary':
            rewrite_page(doc, row['context_regions'][0]['page'], b'(Section B )Tj', b'(Section A )Tj')
        elif fault == 'unattached_preface':
            doc[2].insert_text((100, 100), 'The responses A to D', fontsize=10)
        else:
            region = row['regions'][0]
            page = doc[region['page'] - 1]
            clip = response._region_rect(page, region)
            word = next(w for w in page.get_text('words') if w[4] == '1'
                        and 65 < w[0] < 89 and response._contains(clip, w))
            page.add_redact_annot(pymupdf.Rect(word[:4]), fill=None)
            page.apply_redactions(images=0, graphics=0)
    with substituted_document(raw, mutate) as doc:
        with pytest.raises(ValueError):
            response._prove_document(doc, row)


def test_repeat_cannot_vanish_by_losing_its_preface_phrase_and_attachment(source_packages):
    _, _, _, original, raw = sample(source_packages)
    row = copy.deepcopy(original)
    missing = row['context_regions'].pop()
    def mutate(doc):
        page = doc[missing['page'] - 1]
        streams = page.get_contents()
        text = doc.xref_stream(streams[0])
        # Alter the broad phrase itself; its intact A-D grid remains native.
        assert b'(The respons)' in text
        doc.update_stream(streams[0], text.replace(b'(The respons)', b'(The nonsense)', 1))
    with substituted_document(raw, mutate) as doc:
        with pytest.raises(ValueError, match='native_response_header'):
            response._prove_document(doc, row)


def test_foreign_registered_paper_native_table_does_not_establish_scope(source_packages):
    _, _, _, row, _ = sample(source_packages)
    _, _, _, _, foreign = sample(source_packages, '9701_s17_12')
    with pymupdf.open(stream=foreign, filetype='pdf') as doc:
        with pytest.raises(ValueError, match='identity'):
            response._prove_document(doc, row)


@pytest.mark.parametrize('fault', ['clip', 'pixels'])
def test_resealed_context_cannot_replace_fresh_full_source_pixels(source_packages, tmp_path, fault):
    vault, original, _, row, _ = sample(source_packages)
    package = tmp_path / 'resealed'
    shutil.copytree(original, package)
    bundle = json.loads((package / 'bundle.json').read_bytes())
    question = next(r for r in bundle['questions'] if r['id'] == row['id'])
    if fault == 'clip': question['context_regions'][0]['box'][3] -= .01
    else:
        name = question['context_media'][0]
        path = package / name
        with pymupdf.open(path) as image:
            pix = image[0].get_pixmap()
        pix.set_pixel(0, 0, (1, 2, 3))
        png = pix.tobytes('png')
        path.write_bytes(png)
        bundle['media'][name]['sha256'] = hashlib.sha256(png).hexdigest()
        bundle['media'][name]['bytes'] = len(png)
    data = json.dumps(bundle).encode()
    (package / 'bundle.json').write_bytes(data)
    (package / 'COMPLETE').write_text(hashlib.sha256(data).hexdigest())
    with pytest.raises(ValueError):
        helper.verify_prepared(vault, package, source_practice.verify)


def test_shared_proof_does_not_supply_a_publisher_model_receipt(source_packages, tmp_path, monkeypatch):
    import publish_native
    import native_nested_parts as nested
    vault, package, replay, row, _ = sample(source_packages)
    manifest, packet = helper.prepared_packet(package, replay, row, AssetLibrary(vault))
    assert manifest['status'] == 'source_manifest'
    monkeypatch.setattr(source_practice, '_guard_holds', lambda: {})
    def fresh(vault, output):
        actual = source_practice.verify(vault, output)
        actual['items'] = [r for r in actual['items'] if r['id'] == row['id']]
        return actual
    monkeypatch.setattr(publish_native, 'original_verify', fresh)
    worker = tmp_path / 'worker'
    monkeypatch.setattr(publish_native, 'R', worker)
    before = {p.relative_to(package): p.read_bytes() for p in package.rglob('*') if p.is_file()}
    result = publish_native.approved(vault, package)
    assert result['items'] == [] and result['semantic_pending']
    # A fabricated checked envelope still lacks the actual matching blind wire.
    receipt = {'packet_digest': packet['digest'], 'item_id': row['id'], 'kind': 'mcq',
               'outcome': 'solved', 'context_complete': True, 'question_number': row['label'],
               'scheme_question_number': None, 'parts': [], 'proposals': [], 'answer': row['answer'],
               'reasons': ['Disposable test receipt without an actual model request.']}
    request = nested.plan_request(packet, [])
    attempt = check.record_attempt(packet, receipt, model=request['model'], effort=request['effort'])
    dest = worker / 'semantic-checks' / packet['digest']
    dest.mkdir(parents=True)
    state = dest / 'state.json'
    state.write_text(json.dumps({'qid': row['id'], 'packet_digest': packet['digest'],
                                'status': 'checked', 'attempts': [{'envelope': asdict(attempt)}]}))
    saved = state.read_bytes()
    result = publish_native.approved(vault, package)
    assert result['items'] == [] and result['semantic_pending']
    assert state.read_bytes() == saved
    assert {p.relative_to(package): p.read_bytes() for p in package.rglob('*') if p.is_file()} == before
