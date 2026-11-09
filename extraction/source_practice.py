#!/usr/bin/env python3
"""Replay frozen preparations against registered PDFs, then publish separate practice."""
from __future__ import annotations

import argparse
from collections import defaultdict
import copy
import hashlib
import io
import json
from pathlib import Path
import re
import sys
import time

import pymupdf
from PIL import Image
from pypdf import PdfReader

HERE = Path(__file__).resolve().parent
sys.path[:0] = [str(HERE), str(HERE.parent / 'src'), str(HERE.parent / 'build')]
import fastpath as native
import topical_fastpath as topical
from tutorlib.asset_library import AssetLibrary, write_asset, _directory, _read_at, _atomic_at
from tutorlib.source_practice import Collection, collection_lock
from question_media_names import store_question_media

WORKERS = HERE.parents[1] / 'Work/Workers/extraction'
KNOWN_CONTENT_HOLDS = {'P1_pearson-edexcel-ial_WMA11_2019-01_01_q7', 'P1_pearson-edexcel-ial_WMA11_2020-01_01_q9'}

PMT_SOURCE = 'asset:asset-4b7b93f6b6a352d6e2cabe11'
PMT_SHA = 'd07bda24d42f4583d06f6b793b3bdc2da51ffb85d6bd41525a1d10d5a5d22408'


def _json(value):
    return json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(',', ':')).encode()


def _serialized_key(raw):
    """Second PDF engine; ordered text rows, independent of spatial-key geometry."""
    found = {}
    for page in PdfReader(io.BytesIO(raw)).pages:
        text = page.extract_text()
        # Historical two-column tables omit the Marks column.
        for match in re.finditer(r'(?m)^\s*([1-9]|[1-3]\d|40)\s+([ABCD])(?:\s+1)?[ \t]*$', text):
            number, answer = int(match[1]), match[2]
            if number in found:
                raise ValueError('duplicate serialized official key')
            found[number] = answer
    if set(found) != set(range(1, 41)):
        raise ValueError('independent serialized official key incomplete')
    return found


def _replay_media(bundle, native_profile):
    """Materialize the exact preparation naming contract from fresh source geometry."""
    requests = {}
    public, private = set(), set()
    def add(regions, visibility, role=None):
        names = []
        for region in regions:
            name = (role or visibility) + '/' + native.sha(_json(region))[:24] + '.png'
            requests[name] = {'region': region, 'visibility': visibility}
            names.append(name)
        return names
    for row in bundle['questions']:
        if native_profile:
            row['question_media'] = add(row['regions'], 'public_question', 'qp')
            row['context_media'] = add(row['context_regions'], 'public_question', 'qp')
            row['mark_scheme_media'] = add(row['mark_scheme_regions'], 'private_answer', 'ms')
            public.update(row['question_media'] + row['context_media']); private.update(row['mark_scheme_media'])
        else:
            row['question_media'] = add(row['regions'], 'questions')
            row['context_media'] = add(row['context_regions'], 'context')
    if native_profile:
        bundle.update(public_media=sorted(public), private_media=sorted(private))
    else:
        for field, visibility in [('review_pages', 'review'), ('private_pages', 'private')]:
            for row in bundle[field]: row['media'] = add([row['region']], visibility)
    return requests


def _pmt_written(raw, fresh):
    """Bounded authenticated D1 profile: observed native MS anchors and final totals.

    This profile intentionally supports one registered compilation. Other PMT
    layouts get an exact unsupported-format error rather than guessed rubrics.
    """
    if fresh['source']['id'] != PMT_SOURCE or fresh['source']['sha256'] != PMT_SHA:
        raise ValueError('unsupported PMT written source profile')
    with pymupdf.open(stream=raw, filetype='pdf') as doc:
        title = doc[0].get_text().splitlines()[0].strip()
        anchors, pages = [], []
        for n, page in enumerate(doc, 1):
            text = page.get_text()
            role = ('questions' if n <= 3 else 'examiner_comments' if n >= 8 else 'mark_scheme')
            if role == 'mark_scheme':
                if not re.search(r'\b[MA]1(?:ft)?\b', text):
                    raise ValueError(f'missing native grading tokens on MS page {n}')
                for word in page.get_text('words', sort=True):
                    m = re.fullmatch(r'([1-6])\.', word[4])
                    if m and .045 < word[0] / page.rect.width < .12 and .06 < word[1] / page.rect.height < .9:
                        anchors.append({'number': int(m[1]), 'page': n, 'top': word[1] / page.rect.height})
            if role == 'examiner_comments' and not re.search(r'\bcandidates\b', text, re.I):
                raise ValueError('PMT commentary boundary missing')
            pages.append({'page': n, 'role': role})
        if [a['number'] for a in anchors] != list(range(1, 7)):
            raise ValueError('ambiguous PMT numbered marking blocks')
        items = []
        for index, question in enumerate(fresh['questions']):
            row = copy.deepcopy(question)
            anchor = anchors[index]; end = anchors[index + 1] if index < 5 else {'page': 7, 'top': .95}
            regions = []
            for n in range(anchor['page'], end['page'] + 1):
                lo = anchor['top'] - .004 if n == anchor['page'] else .10
                hi = end['top'] - .004 if n == end['page'] else .95
                if hi > lo:
                    regions.append(native._region(PMT_SOURCE, PMT_SHA, n, [0, lo, 1, hi]))
            def text_for(regions):
                return '\n'.join(doc[r['page'] - 1].get_text(clip=pymupdf.Rect(
                    r['box'][0] * doc[r['page'] - 1].rect.width, r['box'][1] * doc[r['page'] - 1].rect.height,
                    r['box'][2] * doc[r['page'] - 1].rect.width, r['box'][3] * doc[r['page'] - 1].rect.height)) for r in regions)
            # The observed final [total] closes a scheme, before any next-page header.
            endings = []
            for region in regions:
                page = doc[region['page'] - 1]
                for word in page.get_text('words', sort=True):
                    if (re.fullmatch(r'\[\d+\]', word[4]) and region['box'][1] <= word[1] / page.rect.height < region['box'][3]):
                        endings.append((region['page'], min(.95, word[3] / page.rect.height + .008)))
            if endings:
                end_page, end_y = endings[-1]
                regions = [r for r in regions if r['page'] <= end_page]
                regions[-1]['box'][3] = round(end_y, 8)
            text = text_for(row['regions'])
            totals = re.findall(r'\(Total\s+(\d+)\s+marks?\)', text, re.I)
            scheme_text = text_for(regions)
            scheme_totals = re.findall(r'\[(\d+)\]', scheme_text)
            row.update(mark_scheme_regions=regions, scheme_text=scheme_text, maximum_authority='printed_question_total')
            if len(totals) != 1 or not scheme_totals or int(scheme_totals[-1]) != int(totals[0]):
                row['hold_reasons'] = ['ambiguous_printed_total_or_scheme_termination']
                row['marks'] = None
            else: row['marks'] = int(totals[0])
            items.append(row)
    return title, pages, items


def _guard_holds():
    """Read current guard ownership without resetting or transferring worker state."""
    held = {qid: ['known_source_content_conflict'] for qid in KNOWN_CONTENT_HOLDS}
    def identities(value):
        found = set()
        if isinstance(value, dict):
            for key, child in value.items():
                if key in {'official_qid', 'qid'} and isinstance(child, str): found.add(child)
                elif key in {'official_qids', 'qids'} and isinstance(child, list): found.update(x for x in child if isinstance(x, str))
                else: found.update(identities(child))
        elif isinstance(value, list):
            for child in value: found.update(identities(child))
        return found
    for path in sorted(WORKERS.rglob('state.json')) if WORKERS.exists() else []:
        state = json.loads(path.read_bytes())
        failures = state.get('reliability_failures', {}).get(str(state.get('pass', 1)), {})
        if not any(isinstance(rows, list) and len(rows) >= 2 for rows in failures.values()): continue
        scope = state.get('selected_item_scope') or state.get('current_selected_item_scope')
        owned = identities(scope) if scope else set()
        if not owned:
            owned = identities(state.get('preparedRecordMap', {}))
            for key in ('candidate', 'previous_candidate'):
                target = state.get(key)
                if target and Path(target).is_file(): owned.update(identities(json.loads(Path(target).read_bytes())))
        for qid in owned: held.setdefault(qid, []).append('guard2:' + path.parent.name)
    return held


def verify(vault: Path, output: Path) -> dict:
    """Re-sealing a preparation cannot authorize different answers, pixels or scope."""
    start = time.perf_counter(); output = Path(output)
    guard_holds = _guard_holds()
    if (output / 'descriptor.json').exists():
        from native_written_practice import verify as verify_native_written
        return verify_native_written(vault, output, guard_holds=guard_holds)
    raw_bundle = (output / 'bundle.json').read_bytes(); bundle = json.loads(raw_bundle)
    library = AssetLibrary(vault)
    is_native = bundle.get('profile') == native.PROFILE
    compiled = None
    if is_native:
        native.verify_bundle(output)
        sources = bundle['sources']; data = {role: library.read(s['reference']) for role, s in sources.items()}
        paper = native._paper(library, sources['qp']['reference'], sources['ms']['reference'])
        fresh = native.analyse_pair(data['qp'], data['ms'], paper, sources['qp']['reference'], sources['ms']['reference'])
        keys = _serialized_key(data['ms'])
        if any(keys[int(q['official_qid'].rsplit('_q', 1)[1])] != q['answer'] for q in fresh['questions']):
            raise ValueError('independent official key disagreement')
        course, title = paper.split('_')[0], paper
        pages = [{'source': role, **page} for role in ('qp', 'ms') for page in fresh[role + '_pages']]
        items = fresh['questions']; exceptions = fresh['exceptions']
    elif bundle.get('kind') in {'pmt_complete_preparation', 'pmt_cover_complete_preparation'}:
        if bundle.get('kind') == 'pmt_cover_complete_preparation':
            import pmt_cover_complete_profile as complete
        else:
            import pmt_complete_profile as complete
        complete.verify_bundle(output)
        source = bundle['source']; source_raw = library.read(source['id'])
        record = library.record(source['id'])
        fresh = complete.analyse(source_raw, bundle['course'], source['id'], source_path=record['path'])
        fresh['render_recipe'] = bundle['render_recipe']
        data = {'source': source_raw}; course = bundle['course']
        title, pages, items = fresh['title'], fresh['pages'], fresh['questions']
        sources = {'source': {'reference': source['id'], 'sha256': native.sha(source_raw), 'pages': len(pages)}}
        exceptions = fresh['issues']
    elif bundle.get('kind') == 'topical_preparation':
        topical.verify_bundle(output)
        source = bundle['source']; source_raw = library.read(source['id'])
        record = library.record(source['id'])
        fresh = topical.analyse_source(source_raw, bundle['course'], source['id'], source_path=record['path'])
        data = {'source': source_raw}; course = bundle['course']
        if fresh['source']['id'] == PMT_SOURCE and fresh['source']['sha256'] == PMT_SHA:
            title, pages, items = _pmt_written(source_raw, fresh)
        elif fresh['source']['id'] == 'asset:legacy-94c51c9bcbba526ad8f64b38':
            from caie_compiled_profile import compile_mcq
            compiled = compile_mcq(source_raw, fresh)
            title, pages, items = compiled['title'], compiled['pages'], compiled['items']
        else:
            from pmt_source_profile import compile_written
            title, pages, items = compile_written(source_raw, fresh, source_path=record['path'])
        sources = {'source': {'reference': source['id'], 'sha256': native.sha(source_raw), 'pages': len(pages)}}
        exceptions = fresh['issues']
    else: raise ValueError('unsupported source preparation profile')
    requests = _replay_media(fresh, is_native)
    if not is_native:
        public_rows = {q['id']: q for q in fresh['questions']}
        for row in items:
            public_row = public_rows[row['id']]
            row['question_media'] = list(public_row['question_media'])
            row['context_media'] = list(public_row['context_media'])
    # Every source-derived field, including complete question/page ledgers, must match.
    expected = {k: v for k, v in fresh.items() if k not in {'media', 'metrics'}}
    actual = {k: v for k, v in bundle.items() if k not in {'media', 'metrics'}}
    if actual != expected:
        raise ValueError('preparation differs from fresh registered source replay')
    source_names = set(requests)
    if not is_native:
        for row in items:
            row['mark_scheme_media'] = []
            for region in row['mark_scheme_regions']:
                name = 'ms/' + native.sha(_json(region))[:24] + '.png'
                requests[name] = {'region': region, 'visibility': 'private_answer'}
                row['mark_scheme_media'].append(name)
    dpi = bundle['metrics']['dpi']; media, pixels, renders = {}, {}, 0
    # Render ALL physical pages once, including private comments and front matter.
    grouped = defaultdict(list)
    for name, value in requests.items(): grouped[value['region']['source_id']].append((name, value))
    page_proofs = []; source_text = {}
    for role, source in sources.items():
        ref = source['reference']; source_raw = data[role]
        if native.sha(source_raw) != source['sha256']: raise ValueError('registered source digest differs')
        with pymupdf.open(stream=source_raw, filetype='pdf') as doc:
            if len(doc) != source['pages']: raise ValueError('source page count differs')
            for n, page in enumerate(doc, 1):
                pix = page.get_pixmap(dpi=dpi, alpha=False); renders += 1
                image = Image.frombytes('RGB', [pix.width, pix.height], pix.samples)
                page_proofs.append({'source': ref, 'page': n, 'pixels_sha256': native.sha(pix.samples), 'width': pix.width, 'height': pix.height})
                for name, value in grouped[ref]:
                    if value['region']['page'] != n: continue
                    box = value['region']['box']
                    source_text[_json(value['region'])] = page.get_text(clip=pymupdf.Rect(box[0]*page.rect.width, box[1]*page.rect.height, box[2]*page.rect.width, box[3]*page.rect.height))
                    png = native._png(image, box)
                    meta = {**value, 'sha256': native.sha(png), 'bytes': len(png)}
                    if name in source_names and (bundle['media'].get(name) != meta or (output / name).read_bytes() != png):
                        raise ValueError('preparation pixels differ from fresh source render')
                    media[name] = meta; pixels[name] = png
                image.close()
    if source_names != set(bundle['media']): raise ValueError('media partition differs from source replay')
    held, available = [], []
    file_holds = []
    if is_native:
        owned = {
            'qp': {r['page'] for q in items for r in q['regions'] + q['context_regions']},
            'ms': {r['page'] for q in items for r in q['mark_scheme_regions']},
        }
        for error in exceptions:
            if not isinstance(error, dict) or error.get('question') is not None: continue
            role = error.get('source', 'ms' if error.get('reason') == 'unassigned_ms_page' else 'qp')
            page = error.get('page')
            if page is not None and page not in owned.get(role, set()):
                file_holds.append(f'unassigned_source_page:{role}:{page}')
        observed = {q['official_qid'] for q in items}
        for number in range(1, 41):
            qid = f'{title}_q{number}'
            if qid not in observed:
                held.append({'id': qid, 'reasons': ['source_segmentation_incomplete']})
    for q in items:
        row = copy.deepcopy(q)
        row['question_text'] = '\n'.join(source_text[_json(r)] for r in row['context_regions'] + row['regions'])
        reasons = list(row.pop('hold_reasons', [])) + file_holds
        qid = row.get('official_qid') or row['id']
        reasons.extend(guard_holds.get(qid, []))
        for error in exceptions:
            if isinstance(error, dict) and (error.get('question') == int(qid.rsplit('_q', 1)[-1]) if '_q' in qid else False):
                reasons.append(error['reason'])
            if isinstance(error, dict) and error.get('page') in {r['page'] for r in row['regions']}:
                reasons.append(error.get('reason', 'source_page_exception'))
        if compiled:
            row['source_occurrence_id'] = row['id']
        row.update(id=qid, canonical_id=qid, course=course, source=title, title=title,
                   label=row.get('label') or qid.rsplit('_q', 1)[-1], kcs=[], source_verified=True,
                   mastery_certified=False, teaching_approved=False)
        if reasons: held.append({'id': qid, 'reasons': sorted(set(reasons))})
        else: available.append(row)
    compiled_proof = {}
    if compiled:
        from caie_compiled_profile import reuse_verified
        pointer = Path(vault) / '.tutor/source_practice/CURRENT'
        selected = Collection(vault) if pointer.exists() or pointer.is_symlink() else None
        available, reused, conflicts = reuse_verified(available, selected)
        held.extend(conflicts)
        compiled_proof = {'occurrence_exclusions': compiled['occurrence_exclusions'],
                          'provenance_reuse': reused,
                          'selected_collection_release': selected.release if selected else None,
                          'compiled_key_rows': compiled['key_rows']}
    return {'schema_version': 1, 'course': course, 'title': title, 'sources': sources,
            'source_verified': True, 'mastery_certified': False, 'items': available, 'held': held,
            'exceptions': exceptions, 'pages': pages, 'page_proofs': page_proofs, 'media': media,
            '_pixels': pixels, 'key_extractors': ['pymupdf_spatial', 'pypdf_serialized'] if is_native or compiled else [],
            **compiled_proof,
            'metrics': {'elapsed_seconds': time.perf_counter() - start, 'page_renders': renders, 'model_calls': 0},
            'preparation_sha256': native.sha(raw_bundle)}


def _canonical_evidence(row):
    """Compare authenticated content and scope, independent of publication paths."""
    fields = ('canonical_id', 'official_qid', 'part', 'kind', 'answer', 'marks',
              'question_text', 'scheme_text', 'maximum_authority')
    evidence = {field: row.get(field) for field in fields}
    for field in ('regions', 'context_regions', 'mark_scheme_regions'):
        evidence[field] = [{key: region[key] for key in ('source_sha256', 'page', 'box')}
                           for region in row.get(field, [])]
    return evidence


def publish(vault: Path, outputs: list[Path], *, expected_current: str | None) -> dict:
    """Append immutable Library release; one locked compare-and-swap selects it."""
    vault = Path(vault)
    verified = [verify(vault, output) for output in outputs]
    with collection_lock(vault):
        with _directory(vault, ['.tutor', 'source_practice'], create=True) as directory:
            previous_raw = _read_at(directory, 'CURRENT', optional=True)
            previous = previous_raw.decode().strip() if previous_raw else None
            if previous != expected_current: raise ValueError('CURRENT changed; publication compare-and-swap refused')
            old = Collection(vault) if previous else None
            old_items = old._items if old else {}
            items = copy.deepcopy(old_items)
            held = copy.deepcopy(old._manifest.get('held', [])) if old else []
            proofs = copy.deepcopy(old._manifest.get('proofs', [])) if old else []
            reused = []; new = []
            # This one observation defines admission-time guard ownership for
            # both retained entries and already-verified incoming entries.
            publication_holds = _guard_holds()
            quarantine = {}
            canonical_seen = copy.deepcopy(old_items)
            def hold(qid, reasons):
                quarantine.setdefault(qid, set()).update(reasons)
                items.pop(qid, None)
            for held_item in held:
                hold(held_item['id'], held_item['reasons'])
            for qid, reasons in publication_holds.items():
                if qid in items: hold(qid, reasons)
            # Existing adaptive Bank identities are read-only evidence, never re-admitted.
            bank_ids = {}; bank_keys = defaultdict(set)
            bank_pointer = vault / '.tutor/topicals/CURRENT'
            if bank_pointer.exists() or bank_pointer.is_symlink():
                with _directory(vault, ['.tutor', 'topicals']) as bank_dir:
                    version = _read_at(bank_dir, 'CURRENT').decode().strip()
                if not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_.-]*', version): raise ValueError('invalid Topicals CURRENT')
                bank = json.loads(AssetLibrary(vault).read(f'Library/Shared/Topicals/Releases/{version}/bank.json'))
                for row in bank['items']:
                    qid = row.get('source', {}).get('qid')
                    if qid:
                        bank_ids[qid] = row['id']
                        if row.get('kind') == 'mcq': bank_keys[qid].add(str(row.get('answer')))
            for qid, row in list(items.items()):
                if row['kind'] == 'mcq' and any(key != row['answer'] for key in bank_keys[qid]):
                    hold(qid, ['existing_bank_key_conflict'])
            for result in verified:
                for held_item in result['held']:
                    hold(held_item['id'], held_item['reasons'])
                for row in result['items']:
                    qid = row['id']
                    if qid in publication_holds: hold(qid, publication_holds[qid])
                    if row['kind'] == 'mcq' and any(key != row['answer'] for key in bank_keys[qid]):
                        hold(qid, ['existing_bank_key_conflict'])
                    if qid in canonical_seen and _canonical_evidence(canonical_seen[qid]) != _canonical_evidence(row):
                        hold(qid, ['canonical_evidence_conflict'])
                    canonical_seen.setdefault(qid, copy.deepcopy(row))
                    if qid in quarantine: continue
                    if qid in items:
                        reused.append(qid); continue
                    row = copy.deepcopy(row)
                    row['bank_id'] = bank_ids.get(qid)
                    (reused if row['bank_id'] else new).append(qid)
                    roles = {'question_media': 'mcq' if row['kind'] == 'mcq' else 'long',
                             'context_media': 'mcq' if row['kind'] == 'mcq' else 'ctx', 'mark_scheme_media': 'key'}
                    for field in ('question_media', 'context_media', 'mark_scheme_media'):
                        refs = []
                        for name in row.get(field, []):
                            png = result['_pixels'][name]; digest = native.sha(png)
                            binding = native.sha(_json(result['media'][name]))[:16]
                            # the release keeps this reference string; the file itself goes to its course folder
                            target = f'Library/SourcePractice/Media/{digest}-{binding}.png'
                            store_question_media(vault, png, target, course=row['course'], role=roles[field],
                                                 qid=row.get('official_qid'), topic=row.get('source'), label=row.get('label'),
                                                 metadata={'provenance': result['media'][name]})
                            refs.append(target)
                        row[field] = refs
                    items[qid] = row
                proofs.append({k: v for k, v in result.items() if k not in {'items', '_pixels', 'media'}})
            for held_item in held:
                quarantine.setdefault(held_item['id'], set()).update(held_item['reasons'])
            held = [{'id': qid, 'reasons': sorted(reasons)} for qid, reasons in sorted(quarantine.items())]
            reused = [qid for qid in reused if qid not in quarantine]
            new = [qid for qid in new if qid not in quarantine]
            manifest = {'schema_version': 1, 'items': list(items.values()), 'held': held, 'proofs': proofs,
                        'mastery_certified': 0, 'source_verified': len(items), 'reused': sorted(set(reused)), 'new': sorted(set(new))}
            release = native.sha(_json(manifest)); path = f'Library/SourcePractice/Releases/{release}.json'
            write_asset(vault, path, _json(manifest), metadata={'kind': 'SourcePractice/Release'})
            journal = {'previous': previous, 'current': path, 'release': release}
            _atomic_at(directory, 'journal-' + release + '.json', _json(journal), replace=False)
            # Recheck immediately before pointer replacement under the same writer lock.
            if _read_at(directory, 'CURRENT', optional=True) != previous_raw: raise ValueError('CURRENT changed during publication')
            _atomic_at(directory, 'CURRENT', (path + '\n').encode(), replace=True)
    return {k: v for k, v in manifest.items() if k not in {'items', 'proofs'}} | {'current': path}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command', choices=['verify', 'publish'])
    parser.add_argument('--vault', type=Path, required=True)
    parser.add_argument('--bundle', type=Path, action='append', required=True)
    parser.add_argument('--expected-current', default=None)
    args = parser.parse_args(argv)
    try:
        if args.command == 'publish': result = publish(args.vault, args.bundle, expected_current=args.expected_current)
        else: result = [{k: v for k, v in verify(args.vault, b).items() if k not in {'_pixels', 'items', 'media'}} for b in args.bundle]
        print(json.dumps(result, indent=2)); return 0
    except (OSError, ValueError, KeyError) as exc:
        print(str(exc), file=sys.stderr); return 2


if __name__ == '__main__': raise SystemExit(main())
