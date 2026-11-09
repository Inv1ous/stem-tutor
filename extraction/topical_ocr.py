"""Provisional whole-question markers from five frozen, unreviewed OCR caches.

No OCR execution or source writes. All cache pages are verified before any
marker is returned. Coordinates use the original PDF's displayed page frame,
including its declared rotation, matching normalized full-width source crops.
Literal OCR confidence never establishes source review or teaching approval.
"""
from __future__ import annotations

import hashlib
import math
from pathlib import Path
import re

import pymupdf
from tutor_workers import source_ocr

# Source revisions and OCR manifests are immutable inputs to these provisional
# scan profiles. A regenerated cache needs an explicit new profile revision.
_PROFILES = {
    'asset:legacy-a17b0a2a2c3378405e7f563e': ('be884bdfc5ff0ad6897292af2d2a14ec656ea04d0c703ee1df319656381cc26c', '3964a94a48d7b231324f70a6f4321e0ccb0ff0125cb42d91e1c6ee35343bff38', 'crack', 4),
    'asset:legacy-fc98465053396209207e8eff': ('e47e54589cb8eb118c69d2bd41f8d6824a6598af8a67b666563b198ac75e8c50', '9e7191b8bf9eb26ed6b680f7d702510898420516d5161860dfb8a5f53cfc7f64', 'crack', 4),
    'asset:legacy-6fc87cbf2a4250110b70efa4': ('f7c8b1395b89543731d64f17955fe87b63558baaa56abf5e565b20740c4423d0', 'da59bb7a7282dd1a685553d4a365b373032fd21f3eb02e958fdfea7edb6a2254', 'exammate', 3),
    'asset:legacy-8f2f9994d0b9bb3f82615c58': ('74551848fcee94794f4fee4dc5ced435865016a01a14857b65c599df3c888e57', '843aaa923d00187b2108a964e51ebd9adaea8ebb825b669d1015b2dca606b8d9', 'readwrite', 6),
    'asset:legacy-b47a42bc4290a20b9604d211': ('b7c71253f5b31e5a175355afb7838977b893d066323dc8d1a9e9c60b7b2423ad', '1397a9a1788d4857e8768a6262773e86f4c9091e4588b9adc9a40f09858c8287', 'readwrite', 6),
}
_RW = re.compile(r'^\s*(?:(\d{1,3})[.)]\s*)?(M\s*/\s*J|O\s*/\s*N|MAR)\s*(\d{2})\s*/\s*P(\d{2})\s*/\s*Q(\d+)\s*$', re.I)
_EXAM = re.compile(r'^\s*(\d+)\s*-\s*\(9701/(\d{2})_(Summer|Winter|Spring|March|February)_(20\d{2})_Q(\d+)\)', re.I)
_CRACK = re.compile(r'^9701/(May/June|Oct/Nov|October/November|Feb/March)/(20\d{2})/(\d{2})$', re.I)
_SEASON = {'M/J': 's', 'O/N': 'w', 'MAR': 'm', 'summer': 's', 'winter': 'w', 'spring': 'm', 'march': 'm', 'february': 'm'}

def _empty(reason, detail=''):
    return {'profile': 'ocr_unavailable', 'anchors': [], 'page_roles': {},
            'issues': [{'reason': reason, 'detail': detail}], 'validated_ocr_pages': [],
            'segmentation_status': 'provisional', 'teaching_approved': False}

def _geometry(page, data):
    geometry = data['geometry']
    crop = geometry.get('pdf_cropbox')
    if (geometry.get('page_rotation') != page.rotation or not isinstance(crop, list) or len(crop) != 4
            or any(type(v) not in (int,float) or not math.isfinite(v) for v in crop)
            or any(abs(a-b) > .05 for a,b in zip(crop, page.cropbox))
            or geometry.get('width') != data['width'] or geometry.get('height') != data['height']
            or abs(data['width'] - page.rect.width*2.5) > 2
            or abs(data['height'] - page.rect.height*2.5) > 2
            or geometry.get('coordinate_system') not in {
                'Normalised bottom-left OCR text boxes; no diagram geometry inferred.',
                'Normalised bottom-left text boxes relative to this render; not question crop boxes or diagram geometry.'}):
        raise ValueError('OCR geometry cannot map to original displayed PDF page')

def _lines(page, data):
    result=[]
    for line in data['lines']:
        box=line['box']
        x,y,w,h=(box[k] for k in ('x','y','width','height'))
        if x+w > 1.001 or y+h > 1.001 or w <= 0 or h <= 0:
            continue
        result.append({**line, 'bbox':[x*page.rect.width, (1-y-h)*page.rect.height,
                                      (x+w)*page.rect.width, (1-y)*page.rect.height]})
    return sorted(result,key=lambda line:(line['bbox'][1],line['bbox'][0]))

def find_anchors_from_cache(raw: bytes, source_id: str, cache_dir: Path) -> dict:
    """Fail closed on drift; return provisional starts, explicit stops, and issues."""
    profile=_PROFILES.get(source_id)
    digest=hashlib.sha256(raw).hexdigest()
    if profile is None or digest != profile[0]:
        return _empty('unsupported_ocr_source')
    _, pinned_manifest, kind, first_content=profile
    try:
        with pymupdf.open(stream=raw,filetype='pdf') as doc:
            source={'id':source_id,'sha256':digest,'pages':len(doc)}
            folder, manifest_bytes, manifest=source_ocr._manifest(source,cache_dir)
            if hashlib.sha256(manifest_bytes).hexdigest() != pinned_manifest:
                raise ValueError('OCR manifest differs from frozen provisional profile')
            pages=[]
            for number,page in enumerate(doc,1):
                data=source_ocr._page(source,folder,manifest,number,manifest['pages'].get(str(number)))
                _geometry(page,data)
                pages.append(_lines(page,data))

            result={'profile':f'ocr_{kind}_provisional_v1', 'anchors':[], 'page_roles':{},
                    'source_course':'9702' if kind=='readwrite' else '9701',
                    'issues':[{'reason':'unreviewed_ocr','requires_visual_review':True}],
                    'validated_ocr_pages':list(range(1,len(doc)+1)),
                    'segmentation_status':'provisional','teaching_approved':False,
                    'provenance':{'source_id':source_id,'source_sha256':digest,'total_pages':len(doc),
                                  'manifest_sha256':pinned_manifest,'dpi':180,
                                  'native_helper_sha256':manifest['native_helper_sha256'],
                                  'native_helper_source_sha256':manifest['native_helper_source_sha256'],
                                  'coordinate_system':'original_pdf_display_top_left'}}
            result['candidate_unit']='page_fragment' if kind=='crack' else 'whole_question_start'
            if kind=='crack':
                result['issues'].append({'reason':'source_header_not_whole_question_proof',
                                         'candidate_unit':'page_fragment'})
            private_pages=set()
            if kind=='crack':
                for lines in pages:
                    for line in lines:
                        match=re.search(r'Answer\s+Key\s+Pages?\s*:\s*(\d+)\s*(?:[-–]\s*(\d+))?',line['text'],re.I)
                        if match:
                            a,b=int(match[1]),int(match[2] or match[1])
                            if not 1 <= a <= b <= len(doc):
                                raise ValueError('declared answer page range outside original PDF')
                            private_pages.update(range(a,b+1))
            private=False
            unit=None
            for number,(page,lines) in enumerate(zip(doc,pages),1):
                texts=[line['text'].strip() for line in lines]
                text='\n'.join(texts)
                if number<first_content:
                    result['page_roles'][str(number)]='front_matter'
                    continue
                if kind=='readwrite':
                    headers=[re.search(r'\bUnit\s*(\d+)\s*:\s*(.*)',line['text'],re.I)
                             for line in lines if line['bbox'][1]<page.rect.height*.16]
                    headers=[m for m in headers if m]
                    for match in headers:
                        if unit is not None and int(match[1]) != unit and not re.search('answer',match[2],re.I):
                            private=False
                        unit=int(match[1])
                    if any(re.search(r'Answers?\s+Section',t,re.I) for t in texts):
                        private=True
                elif kind=='exammate' and any(re.fullmatch(r'ANSWERS?',t,re.I) for t in texts):
                    private=True
                if number in private_pages or private or (kind=='crack' and any(re.fullmatch(r'Answer(?:\s+Keys?)?',t,re.I) for t in texts)):
                    result['page_roles'][str(number)]='answer'
                    continue
                if re.search(r'\bBLANK PAGE\b',text,re.I):
                    result['page_roles'][str(number)]='blank'
                    continue
                if kind=='crack' and re.search(r'Worksheet\s+Pages?\s*:',text,re.I):
                    result['page_roles'][str(number)]='front_matter'
                    continue
                anchors=[]
                for pos,line in enumerate(lines):
                    value=line['text'].strip()
                    label=qid=None
                    if kind=='readwrite':
                        match=_RW.fullmatch(value)
                        if not match:
                            continue
                        label,season,year,paper,question=match.groups()
                        if label is None:
                            peers=[p for p in lines[max(0,pos-2):pos] if re.fullmatch(r'\d{1,3}[.)]',p['text'].strip())
                                   and abs(p['bbox'][1]-line['bbox'][1])<page.rect.height*.035
                                   and p['bbox'][0]<page.rect.width*.2]
                            if len(peers)!=1:
                                continue
                            label=peers[0]['text'].strip().rstrip('.)')
                        qid=f'9702_{_SEASON[re.sub(r"\s+","",season.upper())]}{year}_{paper}_q{int(question)}'
                    elif kind=='exammate':
                        match=_EXAM.match(value)
                        if not match:
                            continue
                        label,paper,season,year,question=match.groups()
                        qid=f'9701_{_SEASON[season.lower()]}{year[-2:]}_{paper}_q{int(question)}'
                    elif _CRACK.fullmatch(value):
                        # Printed paper code has no original question number.
                        label=f'p{number}-header{len(anchors)+1}'
                    else:
                        continue
                    if line['bbox'][0]>page.rect.width*.3:
                        result['issues'].append({'page':number,'reason':'unsupported_anchor_geometry'})
                        continue
                    if line['confidence']<.9:
                        result['issues'].append({'page':number,'reason':'low_ocr_anchor_confidence','confidence':line['confidence']})
                        continue
                    anchor={'page':number,'top':max(0,line['bbox'][1]/page.rect.height),
                            'bottom':min(1,line['bbox'][3]/page.rect.height),'label':label,'official_qid':qid,
                            'part':'','profile':result['profile'],'evidence_bbox':line['bbox'],
                            'coordinate_system':'original_pdf_display_top_left','ocr_confidence':line['confidence'],
                            'candidate_unit':result['candidate_unit'],
                            'requires_visual_review':True,'ocr_page_sha256':manifest['pages'][str(number)]['sha256'],
                            'ocr_render_sha256':manifest['pages'][str(number)]['render_sha256']}
                    anchors.append(anchor)
                    if qid is None:
                        result['issues'].append({'page':number,'reason':'missing_question_identity','label':label})
                result['anchors'].extend(anchors)
                # Never attach an opaque, unanchored page across a possible answer
                # boundary. Missing markers and continuations require visual review.
                result['page_roles'][str(number)]='question' if anchors else 'unanchored'
                if not anchors:
                    result['issues'].append({'page':number,'reason':'unanchored_ocr_page'})
            if not result['anchors']:
                result['issues'].append({'reason':'no_anchors'})
            return result
    except (OSError,ValueError,KeyError,TypeError,RuntimeError) as exc:
        return _empty('invalid_ocr_cache',f'{type(exc).__name__}: {exc}')
