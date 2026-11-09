"""Replay complete native written packages for non-adaptive source practice.

The descriptor's graph digest binds its frozen bytes only. Neither that binding
nor an original-source raster proof constitutes semantic or teaching approval.
"""
from __future__ import annotations

import copy
from pathlib import Path
import time

import pymupdf

import prepared_scope
from tutorlib.asset_library import AssetLibrary
from tutorlib.prepared_evidence import PROFILE, WHOLE_ASSESSMENT, canonical_qid, sha


def verify(vault: Path, output: Path, *, guard_holds: dict | None = None) -> dict:
    """Authenticate every package byte from Library before adapting its rows."""
    start = time.perf_counter()
    output = prepared_scope._physical(Path(output))
    binding = prepared_scope._read_json(output / 'descriptor.json')
    if binding.get('profile') != PROFILE:
        raise ValueError('unsupported native written preparation profile')
    if (not binding.get('questions') or any(q.get('assessment_mode') != WHOLE_ASSESSMENT
                                          for q in binding['questions'])):
        raise ValueError('source practice requires explicit whole assessment mode')
    library = AssetLibrary(vault)
    descriptor = prepared_scope.verify_native_package(output, library, binding.get('graph_sha256'))
    if guard_holds is None:
        # The public function and source_practice dispatch share current guards.
        from source_practice import _guard_holds
        guard_holds = _guard_holds()
    sources = {role: {**copy.deepcopy(pin), 'reference': pin['asset_id']}
               for role, pin in descriptor['sources'].items()}
    docs = {}
    try:
        pages, page_proofs, exceptions = [], [], []
        cover_context = None
        for role, source in sources.items():
            raw = library.read(source['reference'])
            if sha(raw) != source['sha256']:
                raise ValueError('registered native source digest differs')
            doc = pymupdf.open(stream=raw, filetype='pdf'); docs[role] = doc
            if len(doc) != source['pages']:
                raise ValueError('native source page count differs')
            for n, page in enumerate(doc, 1):
                pix = page.get_pixmap(dpi=144, alpha=False)
                pages.append({'source': role, 'page': n})
                page_proofs.append({'source': source['reference'], 'page': n,
                    'pixels_sha256': sha(pix.samples), 'width': pix.width, 'height': pix.height})
                if descriptor['course'] == 'M1' and role == 'qp' and n == 1:
                    # Mechanics assumptions (g and precision) belong to the
                    # learner's original public evidence. Reuse this fresh
                    # page render without adding a file to the frozen package.
                    png = pix.tobytes('png')
                    cover_context = ('public/m1-qp-cover-' + sha(png)[:24] + '.png', png,
                        {'role': 'qp', 'source_id': source['asset_id'],
                         'source_sha256': source['sha256'], 'page': 1, 'box': [0,0,1,1]})
            exceptions.extend({'source': role, **copy.deepcopy(issue)} for issue in source.get('issues', []))
        media, pixels = {}, {}
        for name, proof in descriptor['media'].items():
            data = (output / name).read_bytes()
            if sha(data) != proof['sha256']:
                raise ValueError('native package pixels changed after source replay')
            pixels[name] = data
            media[name] = {**copy.deepcopy(proof), 'bytes': len(data),
                'visibility': 'public_question' if proof['visibility'] == 'public' else 'private_answer'}
        if cover_context:
            name, data, region = cover_context
            pixels[name] = data
            media[name] = {'region': region, 'visibility': 'public_question',
                'sha256': sha(data), 'bytes': len(data)}
        items, held = [], []
        title = descriptor['questions'][0]['official_qid'].rsplit('_q', 1)[0]
        for question in descriptor['questions']:
            qid = canonical_qid(descriptor['exam'], question['number'])
            if question['official_qid'] != qid or question.get('assessment_mode') != WHOLE_ASSESSMENT:
                raise ValueError('native whole assessment canonical identity differs')
            part = question['parts'][0]
            if len(question['parts']) != 1 or part['part'] != '':
                raise ValueError('native source practice requires whole assessment without subparts')
            private_regions = part['scheme_media_regions']
            context_regions = copy.deepcopy(part.get('reference_regions', []))
            context_media = list(part.get('reference_media', []))
            if cover_context:
                context_regions.insert(0, copy.deepcopy(cover_context[2]))
                context_media.insert(0, cover_context[0])
            text = lambda regions: '\n'.join(prepared_scope._region_text(docs[r['role']], [r]) for r in regions)
            row = {'id': qid, 'canonical_id': qid, 'official_qid': qid, 'part': '',
                'course': descriptor['course'], 'source': title, 'title': title,
                'label': str(question['number']), 'kind': 'structured',
                'assessment_mode': WHOLE_ASSESSMENT,
                'whole_assessment': copy.deepcopy(question['whole_assessment']),
                'marks': question['whole_assessment']['max_marks'],
                'maximum_authority': 'independent_original_qp_ms_totals',
                'regions': copy.deepcopy(question['question_regions']),
                'context_regions': copy.deepcopy(context_regions),
                'mark_scheme_regions': copy.deepcopy(private_regions),
                'private_guidance_regions': copy.deepcopy(question.get('private_guidance_regions', [])),
                'question_media': list(part['question_media']),
                'context_media': context_media,
                'mark_scheme_media': list(part['scheme_media']),
                'question_text': text(context_regions + part['question_media_regions']),
                'scheme_text': text(private_regions),
                'pending_occurrences': copy.deepcopy(question['pending_occurrences']),
                'kcs': [], 'source_verified': True, 'mastery_certified': False, 'teaching_approved': False}
            reasons = list(guard_holds.get(qid, []))
            # These are original-source discrepancies, never cleared by replay.
            reasons.extend('source_issue:' + issue['type'] for issue in exceptions)
            if reasons:
                held.append({'id': qid, 'reasons': sorted(set(reasons))})
            else:
                items.append(row)
        return {'schema_version': 1, 'course': descriptor['course'], 'title': title,
            'sources': sources, 'source_verified': True, 'mastery_certified': False,
            'items': items, 'held': held, 'exceptions': exceptions, 'pages': pages,
            'page_proofs': page_proofs, 'media': media, '_pixels': pixels, 'key_extractors': [],
            'whole_source_proof': {'profile': PROFILE, 'graph_sha256': descriptor['graph_sha256'],
                'descriptor_sha256': sha((output / 'descriptor.json').read_bytes()),
                'required_asset_pages': copy.deepcopy(descriptor['required_asset_pages']),
                'semantic_status': 'not_checked'},
            'metrics': {'elapsed_seconds': time.perf_counter() - start,
                'page_renders': len(page_proofs), 'model_calls': 0},
            'preparation_sha256': sha((output / 'COMPLETE').read_bytes())}
    finally:
        for doc in docs.values():
            doc.close()
