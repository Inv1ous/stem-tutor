"""Neutral native Pearson evidence grammar. Recognition alone grants no admission.

Keep this module free of workflow/PDF dependencies: learner loaders may use its
identity and source checks, but must additionally authenticate their attestation.
"""
from __future__ import annotations

import hashlib
import json
import math
import re

PROFILE = 'pearson_native_prepared_v1'
COURSE_UNITS = {'P1': 'WMA11', 'P2': 'WMA12', 'P3': 'WMA13', 'P4': 'WMA14',
                'FP1': 'WFM01', 'FP2': 'WFM02', 'FP3': 'WFM03', 'M1': 'WME01',
                'S1': 'WST01', 'S2': 'WST02', 'S3': 'WST03', 'D1': 'WDM11'}
SPEC_PATH = 'Library/Shared/Sources/Specifications/ial-maths-spec.pdf'
SPEC_SHA256 = '71351e66d8434cc8976fa41801b65d77bdcad56f902e45807bc635bca317b408'
PATH_PATTERN = re.compile(r'Library/Courses/([^/]+)/Sources/PastPapers/ial/([A-Z0-9]+)/\2_([0-9]{4})_(Jan|Jun|Oct)_(qp|ms)\.pdf')


def canonical_bytes(value) -> bytes:
    return (json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2, allow_nan=False) + '\n').encode()


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def digest(value) -> bool:
    return isinstance(value, str) and re.fullmatch('[0-9a-f]{64}', value) is not None


def part_suffix(part: str) -> str:
    if not isinstance(part, str) or not re.fullmatch(r'(?:[a-z](?:\((?:i|ii|iii|iv|v|vi|vii|viii|ix|x)\))?)?', part):
        raise ValueError('invalid assessed part label')
    return part.replace('(', '-').replace(')', '')


def canonical_qid(exam: dict, number: int) -> str:
    if type(number) is not int or not 1 <= number <= 99:
        raise ValueError('invalid printed question number')
    return f"{exam['course']}_pearson-edexcel-ial_{exam['unit']}_{exam['session']}_01_q{number}"


def reject_reserved(exam: dict, number: int) -> None:
    if ((exam['unit'], exam['session']) == ('WMA11', '2019-01') and number in (1, 2, 3, 4)
            or (exam['unit'], exam['session']) == ('WMA12', '2019-06') and number == 1):
        raise ValueError('reserved_exact_pilot: use the existing exact admission route')


def source_identity(path: str, role: str, course: str) -> dict:
    match = PATH_PATTERN.fullmatch(path) if isinstance(path, str) else None
    if not match or match[5] != role:
        raise ValueError('source_role: not a registered native original for this role')
    if not isinstance(course,str) or course not in COURSE_UNITS or match[1] != course or match[2] != COURSE_UNITS[course]:
        raise ValueError('source_course: course/unit does not match specification')
    return {'board': 'Pearson Edexcel', 'qualification': 'International Advanced Level',
            'course': course, 'unit': match[2], 'session': match[3] + '-' + {'Jan': '01', 'Jun': '06', 'Oct': '10'}[match[4]],
            'component': '01'}


def validate_region(region: dict, role: str, sources: dict) -> None:
    if not isinstance(region, dict) or region.get('role') != role or role not in sources:
        raise ValueError('region_role: explicit source role mismatch')
    source = sources[role]
    if (region.get('source_id') != source['asset_id'] or region.get('source_sha256') != source['sha256']):
        raise ValueError('region_source: source pin mismatch')
    if type(region.get('page')) is not int or region['page'] not in source['inspection_pages']:
        raise ValueError('region_page: outside role inspection selection')
    box = region.get('box')
    if (not isinstance(box, list) or len(box) != 4
            or any(type(v) not in (int, float) or not math.isfinite(v) for v in box)
            or not (0 <= box[0] < box[2] <= 1 and 0 <= box[1] < box[3] <= 1)):
        raise ValueError('region_box: invalid normalized rotated CropBox coordinates')


def validate_source_pins(sources: dict, library) -> None:
    for role, pin in sources.items():
        if role not in ('qp', 'ms', 'reference') or not isinstance(pin, dict):
            raise ValueError('source_role: invalid source role')
        if not isinstance(pin.get('asset_id'), str) or not pin['asset_id'].startswith('asset:'):
            raise ValueError('source_id: stable asset ID required')
        record = library.record(pin['asset_id'])
        if record['path'] != pin['path'] or record['sha256'] != pin['sha256'] or sha(library.read(pin['asset_id'])) != pin['sha256']:
            raise ValueError('source_pin: original source drift')
        if role in ('qp','ms'):
            match=PATH_PATTERN.fullmatch(pin['path'])
            if not match or record.get('course')!=match[1] or record.get('kind')!='Sources/PastPapers':
                raise ValueError('source_pin: original source metadata drift')


def required_asset_pages(sources: dict, mapping: dict, questions: list) -> list[dict]:
    """One deduplicated page budget for originals, identity and occurrences."""
    if (not isinstance(mapping,dict) or set(mapping)!={'asset_id','path','sha256','page'}
            or not isinstance(mapping.get('asset_id'),str) or not mapping['asset_id'].startswith('asset:')
            or mapping.get('path')!=SPEC_PATH or mapping.get('sha256')!=SPEC_SHA256 or mapping.get('page')!=84):
        raise ValueError('invalid prepared specification evidence')
    pairs={(mapping['asset_id'],84)}
    pairs.update((pin['asset_id'],page) for pin in sources.values() for page in pin['inspection_pages'])
    for question in questions:
        witness=question.get('witness')
        if not isinstance(witness,dict) or not isinstance(witness.get('whole_question_regions'),dict):
            raise ValueError('missing original whole-question inspection evidence')
        for role in ('qp','ms'):
            regions=witness['whole_question_regions'].get(role)
            if not isinstance(regions,list) or not regions: raise ValueError('missing original whole-question inspection evidence')
            for r in regions:
                validate_region(r,role,sources)
                pairs.add((sources[role]['asset_id'],r['page']))
        boundary=witness.get('scheme_boundary')
        if (not isinstance(boundary,dict) or boundary.get('kind') not in ('next_question','document_end')
                or type(boundary.get('page')) is not int or not 1<=boundary['page']<=sources['ms']['pages']
                or boundary['page'] not in sources['ms']['inspection_pages']):
            raise ValueError('missing required scheme boundary asset-page')
        pairs.add((sources['ms']['asset_id'],boundary['page']))
        for r in question.get('private_guidance_regions',[]):
            validate_region(r,'ms',sources)
            pairs.add((sources['ms']['asset_id'],r['page']))
        occurrences=question.get('pending_occurrences',[])
        if not isinstance(occurrences,list): raise ValueError('invalid occurrence evidence inventory')
        for occurrence in occurrences:
            if not isinstance(occurrence,dict): raise ValueError('invalid occurrence evidence inventory')
            source=occurrence.get('source')
            if (not isinstance(source,dict) or not isinstance(source.get('id'),str) or not source['id'].startswith('asset:')
                    or not digest(source.get('sha256')) or type(source.get('pages')) is not int or source['pages']<1):
                raise ValueError('invalid occurrence source pin')
            regions=occurrence.get('regions'); context=occurrence.get('context_regions')
            if not isinstance(regions,list) or not regions or not isinstance(context,list):
                raise ValueError('invalid occurrence witness regions')
            pages={1}
            for r in regions+context:
                if (not isinstance(r,dict) or r.get('source_id')!=source['id'] or r.get('source_sha256')!=source['sha256']
                        or type(r.get('page')) is not int or not 1<=r['page']<=source['pages']):
                    raise ValueError('invalid occurrence witness page/source')
                pages.add(r['page'])
            if occurrence.get('inspection_pages')!=sorted(pages):
                raise ValueError('invalid occurrence asset-page inventory')
            pairs.update((source['id'],page) for page in pages)
    return [{'asset_id':identifier,'page':page} for identifier,page in sorted(pairs)]


WHOLE_ASSESSMENT = 'whole_official_rubric_v1'


def _whole_total(label, role, number):
    if not isinstance(label, str):
        raise ValueError('whole question total label missing')
    if role == 'ms' and re.fullmatch(r'Total\s+[1-9]\d*', label, re.I):
        return int(label.split()[-1])
    if role == 'ms' and re.fullmatch(r'[1-9]\d*\s+marks', label, re.I):
        return int(label.split()[0])
    if role == 'ms' and re.fullmatch(r'[1-9]\d*', label):
        return int(label)
    # Neutral syntax only; ownership still needs an independent source locator.
    if role == 'ms' and re.fullmatch(r'\([1-9]\d*\)', label):
        return int(label[1:-1])
    if role == 'ms' and re.fullmatch(r'\[[1-9]\d*\s+marks\]', label, re.I):
        return int(label[1:].split()[0])
    pattern = (r'\(Total\s+(?:for\s+Question\s+(\d+)\s+is\s+)?(\d+)\s+marks\)'
               if role == 'qp' else r'\((?:(?:Total\s+)?for\s+Question\s+(\d+)\s+is\s+)?(\d+)\s+marks\)')
    match = re.fullmatch(pattern, label, re.I)
    if not match or match[1] is not None and int(match[1]) != number:
        raise ValueError('whole question total is not an independently identified question maximum')
    return int(match[2])


def _contained(region, containers):
    return any(all(region.get(k) == parent.get(k) for k in ('role','source_id','source_sha256','page'))
               and parent['box'][0] <= region['box'][0] < region['box'][2] <= parent['box'][2]
               and parent['box'][1] <= region['box'][1] < region['box'][3] <= parent['box'][3]
               for parent in containers)


def validate_whole_question(question, sources):
    """Neutral whole-mode grammar; original PDF reconstruction remains authoring-only."""
    q = question
    if 'assessment_mode' not in q:
        if any(k in q for k in ('whole_assessment','private_guidance_regions','guidance_witness')):
            raise ValueError('whole assessment requires its explicit mode')
        return
    if q['assessment_mode'] != WHOLE_ASSESSMENT:
        raise ValueError('unknown whole assessment mode')
    if len(q['parts']) != 1 or q['parts'][0]['part'] != '':
        raise ValueError('whole assessment requires one empty-part record')
    w = q.get('whole_assessment')
    if (not isinstance(w,dict) or set(w) != {'max_marks','totals','printed_markers'}
            or type(w.get('max_marks')) is not int or w['max_marks'] <= 0
            or not isinstance(w.get('totals'),dict) or set(w['totals']) != {'qp','ms'}
            or not isinstance(w.get('printed_markers'),dict) or set(w['printed_markers']) != {'qp','ms'}):
        raise ValueError('whole assessment typed maximum/witnesses missing')
    for role, field in (('qp','question_regions'),('ms','scheme_regions')):
        regions=q[field]
        if (regions != q['witness']['whole_question_regions'][role]
                or any(r['box'] != [0,0,1,1] for r in regions)
                or [r['page'] for r in regions] != list(range(regions[0]['page'],regions[-1]['page']+1))):
            raise ValueError('whole assessment must preserve the complete ordered original block')
        total=w['totals'][role]
        if (not isinstance(total,dict) or set(total) != {'kind','value','label','region'}
                or total.get('kind') != 'question_total' or type(total.get('value')) is not int
                or total['value'] != w['max_marks'] or _whole_total(total.get('label'),role,q['number']) != w['max_marks']):
            raise ValueError('whole assessment maximum differs from independent question total')
        validate_region(total['region'],role,sources)
        if not _contained(total['region'],regions):
            raise ValueError('whole assessment total lies outside its core question block')
        if role == 'qp' and (total['region']['page'] != q['witness']['terminator']['page']
                            or total['label'] != q['witness']['terminator']['label']):
            raise ValueError('whole assessment total differs from original question terminator')
        markers=w['printed_markers'][role]
        if not isinstance(markers,list):raise ValueError('whole printed marker inventory missing')
        for marker in markers:
            if not isinstance(marker,dict) or set(marker) != {'text','region'} or not re.fullmatch(r'(?:[1-9]\d?\.?)?\((?:[a-z]|[ivx]+)\)',str(marker.get('text'))):
                raise ValueError('invalid raw whole printed marker')
            validate_region(marker['region'],role,sources)
            if not _contained(marker['region'],regions):raise ValueError('whole printed marker outside core block')
        labels={re.search(r'\(([^)]+)\)',m['text'])[1] for m in markers}
        if not set(q['witness'][role+'_parts']) <= labels:
            raise ValueError('whole printed marker inventory omits source demands')
    guidance=q.get('private_guidance_regions',[])
    if guidance:
        gw=q.get('guidance_witness')
        if (not isinstance(gw,dict) or set(gw) != {'first_question_page','first_question_row','boundary_headings','regions'}
                or type(gw.get('first_question_page')) is not int
                or gw['first_question_page'] > q['scheme_regions'][0]['page']
                or not isinstance(gw.get('regions'),list) or len(gw['regions']) != len(guidance)):
            raise ValueError('whole private guidance witness missing')
        first_row=gw['first_question_row']
        if (not isinstance(first_row,dict) or set(first_row)!={'number','region'}
                or type(first_row.get('number')) is not int or first_row['number']!=1
                or first_row['region'].get('page')!=gw['first_question_page']):
            raise ValueError('whole private guidance first assessment row missing')
        validate_region(first_row['region'],'ms',sources)
        if not isinstance(gw['boundary_headings'],list):raise ValueError('whole private guidance boundary inventory missing')
        for heading in gw['boundary_headings']:
            if not isinstance(heading,dict) or set(heading)!={'heading','region'} or not isinstance(heading['heading'],str):
                raise ValueError('whole private guidance boundary heading missing')
            validate_region(heading['region'],'ms',sources)
        for region, witness in zip(guidance,gw['regions']):
            validate_region(region,'ms',sources)
            if (region['page'] >= gw['first_question_page'] or witness.get('region') != region
                    or not isinstance(witness.get('headings'),list) or not witness['headings']
                    or not digest(witness.get('text_sha256'))):
                raise ValueError('whole private guidance must be introductory same-MS marking guidance')
            for heading in witness['headings']:
                if (not isinstance(heading,dict) or set(heading)!={'heading','region'}
                        or not re.fullmatch(r'General Marking Guidance|General Instructions for Marking|General Principles for(?: Pure Mathematics)? Marking|Use of a formula|Exact answers',str(heading.get('heading')),re.I)):
                    raise ValueError('whole private guidance heading is not marking guidance')
                validate_region(heading['region'],'ms',sources)
                if not _contained(heading['region'],guidance):raise ValueError('whole private guidance heading/context omitted')
        if guidance != sorted(guidance,key=lambda r:(r['page'],r['box'][1])):
            raise ValueError('whole private guidance is unordered')
    elif 'private_guidance_regions' in q or 'guidance_witness' in q:
        raise ValueError('empty or unbound whole private guidance')
    p=q['parts'][0]
    if (p['question_media_regions'] != q['question_regions']
            or p['scheme_media_regions'] != guidance + q['scheme_regions']
            or not 1 <= len(p['scheme_media']) <= 32 or len(set(p['scheme_media']))!=len(p['scheme_media'])):
        raise ValueError('whole assessment public/private media must cover guidance then complete core')


def validate_whole_row(row, question, part):
    """One shared candidate/Library reload whole-rubric and guidance contract."""
    q=question
    if 'assessment_mode' not in q:
        if any(k in row for k in ('assessment_mode','whole_assessment','private_guidance_regions')):
            raise ValueError('whole assessment row lacks its descriptor mode')
        return
    if (row.get('assessment_mode') != WHOLE_ASSESSMENT
            or canonical_bytes(row.get('whole_assessment')) != canonical_bytes(q['whole_assessment'])
            or row.get('part') != '' or type(row.get('marks')) is not int
            or row['marks'] != q['whole_assessment']['max_marks']):
        raise ValueError('whole assessment row mode/typed maximum/witness changed')
    if (('private_guidance_regions' in q) != ('private_guidance_regions' in row)
            or canonical_bytes(row.get('private_guidance_regions')) != canonical_bytes(q.get('private_guidance_regions'))):
        raise ValueError('whole assessment private guidance binding changed')
    expected={'version':1,'max_marks':row['marks'],'media':part['scheme_media']}
    scheme=row.get('scheme')
    if (not isinstance(scheme,list) or len(scheme) != 1 or not isinstance(scheme[0],dict)
            or set(scheme[0]) != {'point','whole_rubric'} or not isinstance(scheme[0].get('point'),str)
            or not scheme[0]['point'].strip() or canonical_bytes(scheme[0].get('whole_rubric')) != canonical_bytes(expected)):
        raise ValueError('whole assessment requires exact complete private manual whole rubric')
    if (not isinstance(row.get('answer'),str) or not row['answer'].strip()
            or re.match(r'\s*(?:see|consult|refer to)\b.*(?:mark.?scheme|rubric|images?)',row['answer'],re.I|re.S)):
        raise ValueError('whole assessment needs concise source-backed official answers, not a generic scheme pointer')


def validate_descriptor(descriptor: dict, library=None, graph_sha256: str | None = None) -> dict:
    """Check the neutral grammar and source/role bindings, without PDF imports.

    This is deliberately separate from workflow recomputation or an immutable
    admission attestation. A well-formed proposal is not a reviewed assessment.
    """
    d=descriptor
    if (not isinstance(d,dict) or type(d.get('schema_version')) is not int or d.get('schema_version')!=1 or d.get('profile')!=PROFILE
            or d.get('teaching_approved') is not False or not digest(d.get('graph_sha256'))):
        raise ValueError('invalid prepared descriptor schema')
    if graph_sha256 is not None and d['graph_sha256']!=graph_sha256:
        raise ValueError('prepared graph digest mismatch')
    sources=d.get('sources')
    if not isinstance(sources,dict) or not {'qp','ms'}<=set(sources) or set(sources)-{'qp','ms','reference'}:
        raise ValueError('invalid prepared source roles')
    exam=d.get('exam'); course=d.get('course')
    for role,pin in sources.items():
        if (not isinstance(pin,dict) or not isinstance(pin.get('asset_id'),str)
                or not pin['asset_id'].startswith('asset:') or not digest(pin.get('sha256'))
                or type(pin.get('pages')) is not int or pin['pages']<1):
            raise ValueError('invalid prepared source pin')
        pages=pin.get('inspection_pages')
        if (not isinstance(pages,list) or not pages or any(type(p) is not int or not 1<=p<=pin['pages'] for p in pages)
                or pages!=sorted(set(pages)) or 1 not in pages):
            raise ValueError('invalid prepared inspection pages')
        if role in ('qp','ms') and source_identity(pin.get('path'),role,course)!=exam:
            raise ValueError('prepared source identity mismatch')
        header=pin.get('header_evidence')
        if (not isinstance(header,dict) or header.get('page')!=1 or not isinstance(header.get('text'),str)
                or sha(header['text'].encode())!=header.get('text_sha256')):
            raise ValueError('invalid prepared header evidence')
        if role in ('qp','ms') and any(header.get(key)!=value for key,value in {'role':role,'unit':exam['unit'],'session':exam['session'],'component':'01'}.items()):
            raise ValueError('prepared header role/identity mismatch')
    if sources['qp']['asset_id']==sources['ms']['asset_id']:
        raise ValueError('prepared source roles must be distinct originals')
    if d.get('verified_pairs')!=[{'qp':sources['qp']['asset_id'],'ms':sources['ms']['asset_id'],'exam':exam}]:
        raise ValueError('invalid prepared verified source pair')
    recipe=d.get('render_recipe')
    if (not isinstance(recipe,dict) or set(recipe)!={'dpi','renderer','version','coordinates','alpha','format'}
            or recipe.get('dpi')!=144 or recipe.get('renderer')!='PyMuPDF' or not isinstance(recipe.get('version'),str)
            or recipe.get('coordinates')!='normalized rotated CropBox' or recipe.get('alpha') is not False or recipe.get('format')!='png'):
        raise ValueError('invalid prepared role-bound render recipe')
    questions=d.get('questions'); media=d.get('media')
    if not isinstance(questions,list) or not 1<=len(questions)<=8 or not isinstance(media,dict) or any(not isinstance(q,dict) for q in questions):
        raise ValueError('invalid prepared question group')
    inventory=required_asset_pages(sources,d.get('unit_mapping_evidence'),questions)
    if len(inventory)>100 or d.get('selected_asset_pages')!=len(inventory) or d.get('required_asset_pages')!=inventory:
        raise ValueError('invalid prepared selected asset-page inventory/count')
    if library is not None:
        validate_source_pins(sources,library)
        mapping=d['unit_mapping_evidence']; spec_record=library.record(mapping['asset_id'])
        if (spec_record['path']!=SPEC_PATH or spec_record['sha256']!=SPEC_SHA256
                or sha(library.read(mapping['asset_id']))!=SPEC_SHA256):
            raise ValueError('prepared specification bytes changed')
    seen=set(); refs=set(); previous=0
    for q in questions:
        if not isinstance(q,dict): raise ValueError('invalid prepared question')
        n=q.get('number'); qid=canonical_qid(exam,n); reject_reserved(exam,n)
        if n<=previous or q.get('official_qid')!=qid:
            raise ValueError('invalid prepared question identity/order')
        previous=n
        for field,role in [('question_regions','qp'),('scheme_regions','ms')]:
            regions=q.get(field)
            if not isinstance(regions,list) or not regions: raise ValueError('missing prepared inspection scope')
            for r in regions: validate_region(r,role,sources)
        parts=q.get('parts')
        if not isinstance(parts,list) or not parts: raise ValueError('missing prepared assessed records')
        labels=[]
        for part in parts:
            if not isinstance(part,dict): raise ValueError('invalid prepared assessed record')
            p=part.get('part'); suffix=part_suffix(p)
            identifier='native-'+qid+('-'+suffix if suffix else '')
            if part.get('id')!=identifier or identifier in seen or part.get('label')!=(f'({p})' if p else ''):
                raise ValueError('invalid prepared assessed ID')
            seen.add(identifier); labels.append(p)
            for field,role,visibility in [('question_media_regions','qp','public'),('scheme_media_regions','ms','private'),('reference_regions','reference','public')]:
                regions=part.get(field,[]); names=part.get('reference_media' if field=='reference_regions' else field.replace('_regions',''),[])
                if (not isinstance(regions,list) or not isinstance(names,list) or len(regions)!=len(names)
                        or role!='reference' and not regions):
                    raise ValueError('invalid prepared media binding')
                for r,name in zip(regions,names):
                    validate_region(r,role,sources)
                    if (not isinstance(name,str) or not re.fullmatch(visibility+r'/[a-f0-9]{24}\.png',name)
                            or name!=visibility+'/'+sha(canonical_bytes(r))[:24]+'.png'
                            or media.get(name,{}).get('region')!=r or media[name].get('visibility')!=visibility
                            or not digest(media[name].get('sha256'))):
                        raise ValueError('prepared media role/source mismatch')
                    refs.add(name)
        if '' in labels and len(labels)>1: raise ValueError('mixed whole/part records')
        validate_whole_question(q,sources)
    if refs!=set(media): raise ValueError('prepared media inventory mismatch')
    return d


def project_identity(source: dict) -> tuple[str, str] | None:
    """Project a strict canonical assessed key; this is not evidence validation."""
    if not isinstance(source, dict) or source.get('profile') != PROFILE:
        return None
    course, qid, part = source.get('course'), source.get('official_qid'), source.get('part')
    if not isinstance(course,str) or course not in COURSE_UNITS or not isinstance(qid, str):
        return None
    match = re.fullmatch(re.escape(course + '_pearson-edexcel-ial_' + COURSE_UNITS[course]) + r'_(\d{4}-(?:01|06|10))_01_q([1-9]\d?)', qid)
    if not match:
        return None
    try:
        part_suffix(part)
        reject_reserved({'unit': COURSE_UNITS[course], 'session': match[1]}, int(match[2]))
    except ValueError:
        return None
    return course, qid + (':' + part if part else '')


def pearson_namespace(qid) -> bool:
    """Reserve every installed Pearson course against permissive CAIE aliases."""
    return isinstance(qid, str) and (qid.split('_', 1)[0].upper() in COURSE_UNITS
                                            or 'pearson' in qid.lower())


def bank_identity(source: dict) -> tuple[str, str] | None:
    marker = source.get('prepared_admission')
    if not isinstance(marker, dict) or marker.get('profile') != PROFILE:
        return None
    qid = source.get('qid')
    course = qid.split('_', 1)[0] if isinstance(qid, str) else None
    return project_identity({'profile': PROFILE, 'course': course,
                             'official_qid': qid, 'part': source.get('part')})


class _VerifiedLibrary:
    """Ephemeral per-load memoization, never authority across loads."""
    def __init__(self, library):
        self.library, self.content = library, {}

    def record(self, reference):
        return self.library.record(reference)

    def read(self, reference):
        path = self.record(reference)['path']
        if path not in self.content:
            self.content[path] = self.library.read(reference)
        return self.content[path]


def _resource(pin, library, course, kind):
    if not isinstance(pin, dict) or set(pin) != {'reference', 'sha256'} or not digest(pin['sha256']):
        raise ValueError('invalid prepared registered resource pin')
    record = library.record(pin['reference'])
    if (pin['reference'] != record['path'] or record.get('course') != course or record.get('kind') != kind
            or record['sha256'] != pin['sha256']):
        raise ValueError('prepared resource catalog binding changed')
    if kind == 'Sources/Provenance' and record['path'] not in {
            f"Library/Courses/{course}/Sources/Provenance/{shelf}/{pin['sha256']}.json"
            for shelf in ('prepared-evidence-v1', 'prepared-v1')}:
        raise ValueError('prepared evidence requires its content-addressed canonical path')
    raw = library.read(pin['reference'])
    if sha(raw) != pin['sha256']:
        raise ValueError('prepared resource bytes changed')
    return raw


def _runtime_graph(graph, course, rows, packs):
    """Compare relevant frozen facts to loaded runtime facts, without file IO."""
    if not isinstance(graph, dict) or not isinstance(graph.get('version'), str) or not graph['version']:
        raise ValueError('prepared graph requires an explicit version')
    nodes = {r['id']: r for r in graph['kcs']}
    parents = {r['id']: r for r in graph['subtopics']}
    selected = {v for row in rows for v in row['kcs'] + row['syllabus'] + row['prerequisites']
                if v in nodes or v in parents}
    selected.update(nodes[v]['subtopic'] for v in list(selected) if v in nodes)
    if packs is not None:
        if packs.syllabus_versions.get(course) != graph['version']:
            raise ValueError('prepared runtime graph version changed')
        for identifier in selected:
            frozen = nodes.get(identifier, parents.get(identifier))
            runtime = (packs.kcs if identifier in nodes else packs.subtopics).get(identifier, {})
            fields = ('id', 'subtopic', 'level', 'prereqs') if identifier in nodes else ('id', 'topic', 'level')
            if runtime.get('spec') != course or any(runtime.get(k) != frozen.get(k) for k in fields):
                raise ValueError('prepared relevant runtime graph fact changed')
    return nodes, parents


def project_bank_item(row, mapping, course, job, candidate_sha256, graph, external, marker):
    """The sole reviewed-to-bank projection, shared by authoring and runtime."""
    import copy
    nodes = {r['id']: r for r in graph['kcs']}
    parents = {r['id']: r for r in graph['subtopics']}
    if (row.get('kind') != 'structured' or not row['kcs'] or not row['syllabus']
            or any(k not in nodes or nodes[k].get('subtopic') not in row['syllabus'] for k in row['kcs'])
            or any(k not in parents for k in row['syllabus'])):
        raise ValueError('prepared assessed graph mapping changed')
    declared = {p for k in row['kcs'] for p in nodes[k].get('prereqs', [])}
    requires, versions = list(row['syllabus']), {}
    for requirement in row['prerequisites']:
        if requirement in nodes or requirement in parents:
            requires.append(nodes[requirement]['subtopic'] if requirement in nodes else requirement)
            continue
        target = requirement.split('-', 1)[0]
        if requirement not in declared or target not in external:
            raise ValueError('prepared external prerequisite lacks frozen declaration')
        authority = external[target]
        target_nodes = {r['id']: r for r in authority['kcs']}
        target_parents = {r['id']: r for r in authority['subtopics']}
        parent = target_nodes[requirement]['subtopic'] if requirement in target_nodes else requirement
        if parent not in target_parents:
            raise ValueError('prepared external prerequisite is unknown')
        requires.append(parent); versions[target] = authority['version']
    context = sha(json.dumps(row, sort_keys=True).encode())[:12]
    scheme = copy.deepcopy(row['scheme'])
    if len(scheme) == 1 and 'whole_rubric' in scheme[0]:
        names = scheme[0]['whole_rubric']['media']
        if any(name not in row['mark_scheme_media'] for name in names):
            raise ValueError('prepared rubric is not private reviewed media')
        scheme[0]['whole_rubric']['media'] = [mapping[n] for n in names]
    return {'kind': row['kind'], 'answer': copy.deepcopy(row['answer']), 'kcs': list(row['kcs']),
            'id': 'extracted-' + row['official_qid'] + '-' + context,
            'stem': row['stem'], 'marks': row.get('marks', 1), 'difficulty': row.get('difficulty', 3),
            'images': [mapping[n] for n in row['question_media'] + row.get('reference_media', [])],
            'scheme': scheme,
            'source': {'type': 'past', 'qid': row['official_qid'], 'part': row['part'],
                       'extraction_regions': copy.deepcopy(row['regions']),
                       'mark_scheme_regions': copy.deepcopy(row['mark_scheme_regions']),
                       'extraction_prerequisites': list(row['prerequisites']),
                       **({'reference_regions': copy.deepcopy(row['reference_regions'])} if row.get('reference_regions') else {}),
                       **({'assessment_mode':row['assessment_mode']} if 'assessment_mode' in row else {}),
                       'extraction_job': job, 'candidate_sha256': candidate_sha256,
                       'prepared_admission': dict(marker)},
            'topical': {'reviewed': True, 'chapters': list(row['syllabus']),
                        'requires': list(dict.fromkeys(requires)), 'support': {}, 'revision': graph['version'],
                        **({'prerequisite_versions': versions} if versions else {})}}


def _load_attestation(marker, library, packs=None):
    if (not isinstance(marker, dict) or set(marker) != {'profile', 'attestation_ref', 'attestation_sha256'}
            or marker.get('profile') != PROFILE or not digest(marker.get('attestation_sha256'))):
        raise ValueError('invalid prepared admission marker')
    record = library.record(marker['attestation_ref'])
    course = record.get('course')
    expected_path = f"Library/Courses/{course}/Sources/Provenance/prepared-v1/{marker['attestation_sha256']}.json"
    if (course not in COURSE_UNITS or record.get('kind') != 'Sources/Provenance'
            or record['path'] != expected_path or marker['attestation_ref'] != expected_path):
        raise ValueError('prepared attestation requires its immutable catalog path')
    raw = _resource({'reference': expected_path, 'sha256': marker['attestation_sha256']}, library, course, 'Sources/Provenance')
    a = json.loads(raw)
    if (a.get('schema_version') != 1 or a.get('profile') != PROFILE or a.get('course') != course
            or a.get('teaching_approved') is not False):
        raise ValueError('invalid prepared attestation schema')
    for field in ('candidate', 'descriptor', 'review', 'seed', 'complete', 'graph'):
        _resource(a[field], library, course, 'Sources/Provenance')
    candidate = json.loads(library.read(a['candidate']['reference']))
    descriptor = validate_descriptor(json.loads(library.read(a['descriptor']['reference'])), library, a['graph']['sha256'])
    expected_sources = {r['asset_id'] for r in descriptor['required_asset_pages']}
    if set(a['source_catalog']) != expected_sources:
        raise ValueError('prepared original source inventory changed')
    for identifier, pin in a['source_catalog'].items():
        record = library.record(identifier)
        if ({key: record.get(key) for key in ('path', 'sha256', 'course', 'kind', 'provenance')} != pin
                or sha(library.read(identifier)) != pin['sha256']):
            raise ValueError('prepared original source catalog metadata or bytes changed')
    review = json.loads(library.read(a['review']['reference']))
    graph = json.loads(library.read(a['graph']['reference']))
    scope = a['prepared_scope']
    if (descriptor['course'] != course or scope.get('profile') != PROFILE or scope.get('job_name') != a['extraction_job']
            or scope.get('descriptor_sha256') != a['descriptor']['sha256']
            or scope.get('seed_sha256') != a['seed']['sha256'] or scope.get('package_sha256') != a['complete']['sha256']
            or scope.get('graph_sha256') != a['graph']['sha256'] or candidate.get('prepared_scope') != scope
            or candidate.get('selected_item_scope') != a['selected_item_scope']
            or review.get('prepared_scope') != scope or review.get('candidate_sha256') != a['candidate']['sha256']
            or review.get('course_graph_sha256') != a['graph']['sha256']
            or review.get('source_inventory_sha256') != sha(json.dumps(a['source_inventory'], sort_keys=True).encode())
            or review.get('seed_sha256') != a['seed']['sha256'] or review.get('verdict') != 'pass'
            or review.get('findings') != []):
        raise ValueError('prepared attestation review/context binding changed')
    receipts = a['manager_receipts']
    if not isinstance(receipts, list) or len(receipts) != 2 or {r.get('role') for r in receipts} != {'extract', 'review'}:
        raise ValueError('prepared admission requires both actual manager roles')
    attempts = set()
    for receipt in receipts:
        role = receipt['role']; prompt = a['prompts'][role]
        _resource(prompt, library, course, 'Sources/Provenance')
        if (not receipt.get('attempt_id') or receipt['attempt_id'] in attempts
                or any(not receipt.get(k) for k in ('started', 'worker_started', 'finished'))
                or type(receipt.get('exit')) is not int or receipt['exit'] != 0 or receipt.get('ok') is not True
                or receipt.get('prepared_scope') != scope or receipt.get('candidate_sha256') != a['candidate']['sha256']
                or receipt.get('prompt_sha256') != prompt['sha256'] or not digest(receipt.get('failure_input'))
                or receipt.get('output_sha256') != a['candidate' if role == 'extract' else 'review']['sha256']):
            raise ValueError('prepared manager role receipt binding changed')
        attempts.add(receipt['attempt_id'])
    rows = candidate['questions']
    parts = {p['id']: (q, p) for q in descriptor['questions'] for p in q['parts']}
    if (not isinstance(rows, list) or len(rows) != len(parts)
            or {r['id'] for r in rows} != set(parts) or candidate.get('diagrams') != []):
        raise ValueError('prepared admission requires the complete reviewed group')
    external = {}
    for target, pin in a['external_graphs'].items():
        external[target] = json.loads(_resource(pin, library, target, 'Sources/Provenance'))
        _runtime_graph(external[target], target, rows, packs)
    _runtime_graph(graph, course, rows, packs)
    public_hashes, private_hashes = set(), set()
    contexts = {sha(json.dumps(row, sort_keys=True).encode())[:12] for row in rows}
    if set(a['media']) != contexts:
        raise ValueError('prepared registered record inventory changed')
    expected = []
    for row in rows:
        q, part = parts[row['id']]
        validate_whole_row(row,q,part)
        if (row['official_qid'] != q['official_qid'] or row['part'] != part['part']
                or row.get('prepared_scope_sha256') != scope['package_sha256']
                or row['regions'] != q['question_regions'] or row['mark_scheme_regions'] != q['scheme_regions']
                or any(row.get(field, []) != part.get(field, []) for field in ('question_media', 'reference_media', 'reference_regions'))
                or row.get('mark_scheme_media') != part['scheme_media']
                or row.get('media') != part['question_media'] + part['scheme_media']
                or row.get('media_regions') != {n: descriptor['media'][n]['region'] for n in part['question_media'] + part['scheme_media'] + part.get('reference_media', [])}):
            raise ValueError('prepared reviewed record differs from immutable descriptor')
        context = sha(json.dumps(row, sort_keys=True).encode())[:12]
        media = a['media'][context]
        names = row['media'] + row.get('reference_media', [])
        if set(media) != set(names):
            raise ValueError('prepared registered per-record media inventory changed')
        mapping = {}
        for name in names:
            pin = media[name]; original = descriptor['media'][name]
            data = _resource({'reference': pin['reference'], 'sha256': original['sha256']}, library, course, 'Questions/Media')
            sidecar = json.loads(_resource(pin['sidecar'], library, course, 'Sources/Provenance'))
            record = library.record(pin['reference'])
            if (record.get('provenance') != {'sidecars': [pin['sidecar']['reference']]}
                    or sidecar.get('prepared_scope') != scope or sidecar.get('media_name') != name
                    or sidecar.get('visibility') != original['visibility'] or sidecar.get('regions') != [original['region']]
                    or sidecar.get('sha256') != sha(data) or sidecar.get('review') != review
                    or sidecar.get('extraction_job') != a['extraction_job'] or sidecar.get('record') != row):
                raise ValueError('prepared per-media provenance changed')
            (public_hashes if original['visibility'] == 'public' else private_hashes).add(sha(data))
            if sha(data) not in review.get('inspected_images', []):
                raise ValueError('prepared media lacks actual inspected review hash')
            mapping[name] = pin['reference']
            from pathlib import PurePosixPath
            path = PurePosixPath(name)
            stem = re.sub(r'[^A-Za-z0-9_-]', '-', path.stem)[:70]
            canonical = f"Library/Courses/{course}/Questions/Media/{stem}-{context}-{original['sha256'][:16]}{path.suffix.lower()}"
            if mapping[name] != canonical:
                raise ValueError('prepared registered media name mapping changed')
        expected.append(project_bank_item(row, mapping, course, a['extraction_job'], a['candidate']['sha256'], graph, external, marker))
    if public_hashes & private_hashes:
        raise ValueError('prepared public media discloses private group imagery')
    # Occurrences corroborate originals; their recorded source bytes remain pinned.
    for q in descriptor['questions']:
        for occurrence in q.get('pending_occurrences', []):
            source = occurrence['source']; source_record = library.record(source['id'])
            if source_record['sha256'] != source['sha256'] or sha(library.read(source['id'])) != source['sha256']:
                raise ValueError('prepared occurrence original bytes changed')
    return a, rows, expected


def authenticate_prepared_item(item, library, packs=None):
    """Verify a row through its entire immutable group, without requiring bank IO."""
    a, rows, expected = _load_attestation(item.get('source', {}).get('prepared_admission'), _VerifiedLibrary(library), packs)
    for row, projected in zip(rows, expected):
        if canonical_bytes(item) == canonical_bytes(projected):
            return row
    raise ValueError('prepared item differs from exact reviewed bank projection')


def validate_prepared_group(items: list[dict], library, packs) -> None:
    """Authenticate each group once per load and require a question/part bijection."""
    library = _VerifiedLibrary(library)
    for item in items:
        source=item.get('source',{})
        if source.get('assessment_mode') == WHOLE_ASSESSMENT and sum(i.get('source',{}).get('qid') == source.get('qid') for i in items) != 1:
            raise ValueError('whole-question assessment is exclusive of every other row with the same official QID')
    groups = {}
    for item in items:
        source = item.get('source', {})
        if 'prepared_admission' in source:
            marker = source['prepared_admission']
            groups.setdefault(json.dumps(marker, sort_keys=True), []).append(item)
    for group in groups.values():
        _, _, expected = _load_attestation(group[0]['source']['prepared_admission'], library, packs)
        actual = {(i['source']['qid'], i['source']['part']): i for i in group}
        required = {(i['source']['qid'], i['source']['part']): i for i in expected}
        if (len(actual) != len(group) or set(actual) != set(required)
                or any(canonical_bytes(actual[key]) != canonical_bytes(required[key]) for key in required)):
            raise ValueError('prepared bank requires the complete exact reviewed group projection')
