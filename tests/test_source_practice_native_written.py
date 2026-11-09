"""Whole native source practice replays real originals in disposable vaults."""
import copy
import hashlib
import importlib
import json
from pathlib import Path
import sys

import pymupdf
import pytest
from library_assets import canonical_path, copy_to_vault, read_bytes
from tutorlib.asset_library import AssetLibrary
from tutorlib.prepared_evidence import WHOLE_ASSESSMENT, canonical_bytes, source_identity
from tutorlib.source_practice import Collection

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'extraction'))
import prepared_scope as prepared
import source_practice as practice

GRAPH = 'a' * 64
SPEC = 'Library/Shared/Sources/Specifications/ial-maths-spec.pdf'
PAIRS = {
    'M1': ('legacy-93ee75a63bbc175a4a777efd', 'legacy-100b1b43dde608b77e6e486e', 1, [2,3], [7], 6),
    'P1': ('legacy-5433803d0abf868d346949c8', 'legacy-49fc389000ec4447e3b10835', 5, [10,11], [14,15], 6),
    'FP1': ('legacy-ccd4b04a607025471cd19567', 'legacy-6112bfaf30ed89481a953ae8', 1, [2,3], [7], 4),
    'FP2': ('legacy-4feb8fa28182b7b84ff8646f', 'legacy-05de55f2ac913134fcfd7f52', 1, [2,3,4,5], [7], 7),
    'FP3': ('legacy-60b9712260c8c2fdffecd495', 'legacy-6f838e266dd038af0e3a7c16', 1, [2,3], [7], 5),
}

def region(role, page):
    return {'role': role, 'page': page, 'box': [0,0,1,1]}


def setup(tmp_path, course='P1', *, whole=True):
    vault = tmp_path / 'vault'; vault.mkdir(exist_ok=True)
    qp, ms, number, qp_pages, ms_pages, _ = PAIRS[course]
    refs = {'qp':'asset:'+qp, 'ms':'asset:'+ms}
    for asset in [*refs.values(), SPEC]:
        copy_to_vault(canonical_path(asset), vault)
        if asset.startswith('asset:'):
            catalog_path = vault / 'Library/catalog.json'
            catalog = json.loads(catalog_path.read_bytes())
            key = next(k for k,v in catalog['assets'].items() if v['path']==canonical_path(asset))
            catalog['assets'][asset[6:]] = catalog['assets'].pop(key)
            catalog_path.write_text(json.dumps(catalog))
    lib = AssetLibrary(vault)
    public = [region('qp',p) for p in qp_pages]
    private = [region('ms',p) for p in ms_pages]
    question = {'number':number, 'question_regions':public, 'scheme_regions':private,
        'parts':[{'part':'','label':'','question_media_regions':public,'scheme_media_regions':private}]}
    if whole:
        question.update(assessment_mode=WHOLE_ASSESSMENT,
            private_guidance_regions=[region('ms',p) for p in [3,4,5,6]])
    request = {'course':course, 'sources':{role:{'asset_id':ref,'sha256':lib.record(ref)['sha256'],
        'inspection_pages':list(range(1, 17 if role=='ms' and course=='P1' else max(qp_pages if role=='qp' else ms_pages)+2))}
        for role,ref in refs.items()}, 'questions':[question]}
    path = tmp_path / 'request.json'; path.write_text(json.dumps(request))
    return vault, lib, request, path, tmp_path / 'package'


def build(inputs):
    vault, lib, request, path, output = inputs
    path.write_text(json.dumps(request))
    return prepared.prepare_native(path, output, lib, GRAPH)


@pytest.fixture(autouse=True)
def no_workers(tmp_path, monkeypatch):
    monkeypatch.setattr(practice, 'WORKERS', tmp_path / 'no-workers')


@pytest.mark.parametrize('course', ['FP1','FP2','FP3'])
def test_real_fp_whole_packages_have_independent_printed_maxima(tmp_path, course):
    inputs=setup(tmp_path,course); descriptor=build(inputs)
    assert descriptor==prepared.verify_native_package(inputs[4],inputs[1],GRAPH)
    result=practice.verify(inputs[0],inputs[4]); item=result['items'][0]
    assert item['marks']==PAIRS[course][-1]
    assert item['id']==descriptor['questions'][0]['official_qid']==item['canonical_id']
    assert item['scheme_text'] and item['question_text']
    assert item['kcs']==[] and item['mastery_certified'] is False and item['teaching_approved'] is False
    assert result['metrics']['model_calls']==0
    assert result['whole_source_proof']['graph_sha256']==GRAPH
    assert result['whole_source_proof']['semantic_status']=='not_checked'


def test_native_adapter_complete_private_guidance_pixels_and_publication(tmp_path):
    inputs=setup(tmp_path)
    # Existing P1 guidance spans 3..5; page 6 is unrelated next section.
    inputs[2]['questions'][0]['private_guidance_regions']=[region('ms',p) for p in [3,4,5]]
    descriptor=build(inputs); result=practice.verify(inputs[0],inputs[4]); row=result['items'][0]
    assert row['assessment_mode']==WHOLE_ASSESSMENT and row['part']==''
    assert row['marks']==6 and not result['held']
    assert [r['page'] for r in row['mark_scheme_regions']]==[3,4,5,14,15]
    assert 'General Marking Guidance' in row['scheme_text']
    assert all(result['media'][n]['visibility']=='private_answer' for n in row['mark_scheme_media'])
    assert all(result['_pixels'][n]==(inputs[4]/n).read_bytes() for n in descriptor['media'])
    assert len(result['page_proofs'])==sum(s['pages'] for s in result['sources'].values())
    old=inputs[0]/'.tutor/events.jsonl';old.parent.mkdir();old.write_bytes(b'preserved events\n')
    bank=inputs[0]/'.tutor/topicals/CURRENT';bank.parent.mkdir();bank.write_text('v1\n')
    from tutorlib.asset_library import write_asset
    write_asset(inputs[0],'Library/Shared/Topicals/Releases/v1/bank.json',canonical_bytes({'items':[
        {'id':'old-adaptive-id','kind':'structured','source':{'qid':row['id']}}]}))
    old_state=inputs[0]/'.tutor/state.json';old_state.write_bytes(b'{"mastery":42}')
    before={p:p.read_bytes() for p in (old,bank,old_state)}
    first=practice.publish(inputs[0],[inputs[4],inputs[4]],expected_current=None)
    assert first['new']==[] and first['reused']==[row['id']]
    collection=Collection(inputs[0]); public=collection.question(row['id'])
    assert public['bank_id']=='old-adaptive-id'
    assert not {'scheme_text','mark_scheme_regions','private_guidance_regions','answer'} & public.keys()
    scheme=collection._items[row['id']]['mark_scheme_media'][0]
    with pytest.raises(ValueError,match='private'):collection.media_path(row['id'],scheme)
    attempt=collection.submit(row['id'],'Working')
    assert 'General Marking Guidance' in collection.feedback(attempt['attempt_id'])['scheme_text']
    assert collection.media_path(row['id'],scheme,attempt_id=attempt['attempt_id']).is_file()
    release_bytes=(inputs[0]/first['current']).read_bytes()
    second=practice.publish(inputs[0],[inputs[4]],expected_current=first['current'])
    assert second['new']==[] and second['reused']==[row['id']]
    assert (inputs[0]/first['current']).read_bytes()==release_bytes
    assert before=={p:p.read_bytes() for p in before}


@pytest.mark.parametrize('fault', ['answer','geometry','image','guidance','extra','canonical'])
def test_native_resealed_package_tampering_fails(tmp_path, fault):
    inputs=setup(tmp_path,'FP2'); descriptor=build(inputs); out=inputs[4]
    if fault=='image':
        name=next(iter(descriptor['media']));(out/name).write_bytes(b'changed pixels')
    elif fault=='extra':(out/'extra.json').write_text('{}')
    else:
        if fault=='answer':descriptor['questions'][0]['answer']='invented answer'
        elif fault=='canonical':descriptor['questions'][0]['official_qid']='invented-id'
        elif fault=='geometry':descriptor['questions'][0]['question_regions'][0]['box'][1]=.01
        else:descriptor['questions'][0]['parts'][0]['scheme_media'].pop(0)
        (out/'descriptor.json').write_bytes(canonical_bytes(descriptor))
    manifest=json.loads((out/'COMPLETE').read_bytes())
    manifest['descriptor_sha256']=hashlib.sha256((out/'descriptor.json').read_bytes()).hexdigest()
    (out/'COMPLETE').write_bytes(canonical_bytes(manifest))
    with pytest.raises(ValueError):practice.verify(inputs[0],out)


def test_adapter_rejects_valid_package_without_whole_mode(tmp_path):
    # Construct the valid control only from shared Library originals, never Work.
    from test_prepared_native_scope import inputs as native_inputs, prepare
    inputs = native_inputs.__wrapped__(tmp_path)
    descriptor = prepare(inputs)
    lib, _, _, out = inputs
    assert descriptor == prepared.verify_native_package(out, lib, GRAPH)
    assert all('assessment_mode' not in q for q in descriptor['questions'])
    with pytest.raises(ValueError,match='whole assessment'):
        practice.verify(lib.root,out)


def test_current_worker_and_known_content_holds_remain_held(tmp_path, monkeypatch):
    inputs=setup(tmp_path,'FP2');build(inputs)
    qid='FP2_pearson-edexcel-ial_WFM02_2023-06_01_q1'
    owner=tmp_path/'workers/owner';owner.mkdir(parents=True);state=owner/'state.json'
    state.write_text(json.dumps({'reliability_failures':{'1':{'extract':[{},{}]}},'selected_item_scope':{'official_qid':qid}}))
    before=state.read_bytes();monkeypatch.setattr(practice,'WORKERS',owner.parent)
    result=practice.verify(inputs[0],inputs[4]);assert result['items']==[]
    assert result['held']==[{'id':qid,'reasons':['guard2:owner']}]
    assert state.read_bytes()==before
    monkeypatch.setattr(practice,'KNOWN_CONTENT_HOLDS',{qid})
    assert 'known_source_content_conflict' in practice.verify(inputs[0],inputs[4])['held'][0]['reasons']


def test_ms_label_grammar_accepts_truthful_literal_but_rejects_qp_and_prose():
    from tutorlib.prepared_evidence import _whole_total
    assert _whole_total('Total 7','ms',1)==7
    assert _whole_total('(2)','ms',1)==2
    for label,role in [('Total 7','qp'),('subtotal 7','ms'),('Total 7 marks in notes','ms'),('(2)','qp')]:
        with pytest.raises(ValueError):_whole_total(label,role,1)


def test_real_may_date_is_june_qp_series_only_and_calendar_remains_provisional():
    from tutorlib.prepared_evidence import source_identity
    ref='asset:'+PAIRS['FP1'][0]
    with pymupdf.open(stream=read_bytes(ref),filetype='pdf') as doc:
        exam=source_identity(canonical_path(ref),'qp','FP1')
        assert prepared._cover(doc,exam,'qp')['session']=='2023-06'
        bad={**exam,'session':'2023-10'}
        with pytest.raises(ValueError,match='cover_session'):prepared._cover(doc,bad,'qp')
    timetable=read_bytes('asset:asset-655f80e435e9d92469e1f6fc')
    assert hashlib.sha256(timetable).hexdigest()=='27951759e6f522cafd811ee5643cff936fa9e25103cf965335a28902fcc0599d'
    with pymupdf.open(stream=timetable,filetype='pdf') as doc:
        text=' '.join(' '.join(page.get_text().split()) for page in doc)
        # Preserve the issuer PDF's misspelled provisional label as evidence.
        assert 'Provisonal' in text and 'Summer 2023' in text and 'WFM01' in text and '30 May' in text


def table_doc(*, shifted=.0, notes_total=False, fake_formula=False, shared=False, no_header=False):
    """Disposable adversarial table geometry, never registered as learning input."""
    doc=pymupdf.open();page=doc.new_page(width=600,height=800)
    x=60+shifted
    if not no_header:
        page.insert_text((x,55),'Question');page.insert_text((x,70),'Number')
        page.insert_text((290,60),'Scheme');page.insert_text((520,60),'Marks')
    page.insert_text((x+12,100),'1')
    page.insert_text((290,105),'M1')
    if fake_formula:page.insert_text((180,140),'9')
    if shared:page.insert_text((x+12,170),'2')
    page.insert_text((50,300),'Notes')
    page.insert_text((490,350 if notes_total else 250),'Total 7')
    return doc


def test_shifted_question_column_requires_header_and_excludes_formula_values():
    with table_doc(shifted=65,fake_formula=True) as doc:
        layout=prepared._source_layout(doc,'ms')
        assert [s['number'] for s in layout[0]['starts']]==[1]
    with table_doc(shifted=65,no_header=True) as doc:
        assert prepared._source_layout(doc,'ms')[0]['starts']==[]


@pytest.mark.parametrize('fault', ['notes','unaligned','multiline','no-marks','competing','prose'])
def test_literal_total_requires_located_marks_column_before_notes(fault):
    with table_doc(notes_total=fault=='notes') as doc:
        page=doc[0]
        if fault=='unaligned':
            page.add_redact_annot(pymupdf.Rect(480,230,560,260));page.apply_redactions();page.insert_text((260,250),'Total 7')
        elif fault=='multiline':
            page.add_redact_annot(pymupdf.Rect(480,230,560,260));page.apply_redactions();page.insert_text((490,230),'Total');page.insert_text((520,250),'7')
        elif fault=='no-marks':
            page.add_redact_annot(pymupdf.Rect(515,40,570,65));page.apply_redactions()
        elif fault=='competing':page.insert_text((490,200),'Total 8')
        elif fault=='prose':
            page.add_redact_annot(pymupdf.Rect(480,230,560,260));page.apply_redactions();page.insert_text((490,250),'Total 7 notes')
        layouts={'ms':prepared._source_layout(doc,'ms')}
        q={'number':1,'scheme_regions':[{'role':'ms','source_id':'asset:x','source_sha256':'a'*64,'page':1,'box':[0,0,1,1]}]}
        with pytest.raises(ValueError,match='question_total'):
            prepared._located_whole_total(q,layouts,{},'ms')


def test_shifted_shared_page_scheme_remains_held():
    with table_doc(shifted=65,shared=True) as ms, pymupdf.open() as qp:
        page=qp.new_page();page.insert_text((40,80),'1. Task (Total 7 marks)')
        layouts={role:prepared._source_layout(doc,role) for role,doc in [('qp',qp),('ms',ms)]}
        assert [s['number'] for s in layouts['ms'][0]['starts']]==[1,2]
        question={'number':1,'question_regions':[region('qp',1)],'scheme_regions':[region('ms',1)]}
        with pytest.raises(ValueError,match='shared-page'):
            prepared._whole_question_scope(question,layouts,{})


@pytest.mark.parametrize('role,session', [('ms','2023-06'),('qp','2023-10')])
def test_may_cover_never_equates_ms_or_october(role,session):
    with pymupdf.open() as doc:
        page=doc.new_page()
        page.insert_text((40,60),'Pearson Edexcel International Advanced Level')
        page.insert_text((40,90),'Mark Scheme WFM01 Paper 01' if role=='ms' else 'Paper reference WFM01/01')
        page.insert_text((40,120),'May 2023')
        exam={'unit':'WFM01','session':session}
        with pytest.raises(ValueError,match='cover_session'):prepared._cover(doc,exam,role)


def test_actual_2020_may_qp_october_ms_pair_stays_held():
    qp='asset:legacy-57833e5da861684c0c4ae20d'
    ms='asset:legacy-c8f144d57ba279153332fe5e'
    with pymupdf.open(stream=read_bytes(qp),filetype='pdf') as doc:
        exam=source_identity(canonical_path(qp),'qp','FP1')
        assert 'May 2020' in ' '.join(doc[0].get_text().split())
        assert prepared._cover(doc,exam,'qp')['session']=='2020-06'
    with pymupdf.open(stream=read_bytes(ms),filetype='pdf') as doc:
        assert 'October 2020' in ' '.join(doc[0].get_text().split())
        with pytest.raises(ValueError,match='cover_session'):
            prepared._cover(doc,source_identity(canonical_path(ms),'ms','FP1'),'ms')


@pytest.mark.parametrize('course,unit,session', [
    ('FP1','WFM01','2021_Oct'), ('M1','WME01','2019_Jun'), ('M1','WME01','2020_Jan')])
def test_real_modern_ms_issuer_spelling_variants(course,unit,session):
    path=f'Library/Courses/{course}/Sources/PastPapers/ial/{unit}/{unit}_{session}_ms.pdf'
    with pymupdf.open(stream=read_bytes(path),filetype='pdf') as doc:
        exam=source_identity(canonical_path(path),'ms',course)
        assert prepared._cover(doc,exam,'ms')['unit']==unit


@pytest.mark.parametrize('issuer,unit,role', [
    ('Pearson Edexcel IAL','WFM01','qp'),
    ('Pearson Edexcel International A Level','WFM01','qp'),
    ('Pearson Edexcel International GCE','6667','ms'),
    ('Other Edexcel International A Level','WFM01','ms'),
    ('Pearson Edexcel GCE Advanced Level','WFM01','ms'),
])
def test_ms_issuer_aliases_do_not_rebadge_qps_legacy_or_other_boards(issuer,unit,role):
    with pymupdf.open() as doc:
        page=doc.new_page()
        page.insert_text((40,60),issuer)
        page.insert_text((40,90),f'Mark Scheme {unit} Paper 01' if role=='ms' else f'Paper reference {unit}/01')
        page.insert_text((40,120),'June 2023')
        with pytest.raises(ValueError):
            prepared._cover(doc,{'unit':'WFM01','session':'2023-06'},role)


def test_native_printed_number_matches_lightweight_packet_receipt(tmp_path):
    import lightweight_verification as checks
    inputs=setup(tmp_path,'FP2');build(inputs)
    row=practice.verify(inputs[0],inputs[4])['items'][0]
    packet=checks.build_packet(row)
    # Synthetic transport receipt checks numbering, not semantic approval.
    content={'packet_digest':packet['digest'],'item_id':packet['item_id'],
        'kind':'structured','outcome':'solved','answer':None,'context_complete':True,
        'question_number':'1','scheme_question_number':'1','parts':[],
        'reasons':['Numbering transport check only.'],'proposals':[]}
    attempt=checks.record_attempt(packet,content,model='gpt-6-luna',effort='medium')
    result=checks.evaluate_receipt(packet,attempt)
    assert row['label']=='1'
    assert not {'question_number_mismatch','scheme_question_number_mismatch'} & set(result['reasons'])
    # Missing authenticated part inventory stays held; do not infer it from a model.
    assert result['status']=='hold' and 'source_part_manifest_required' in result['reasons']


def test_m1_cover_context_has_true_original_pixels_text_and_public_privacy(tmp_path):
    import lightweight_verification as checks
    inputs=setup(tmp_path,'M1')
    inputs[2]['questions'][0].pop('private_guidance_regions')
    descriptor=build(inputs)
    out=inputs[4]
    package_before={p.relative_to(out).as_posix():p.read_bytes() for p in out.rglob('*') if p.is_file()}
    result=practice.verify(inputs[0],out);row=result['items'][0]
    assert len(row['context_regions'])==len(row['context_media'])==1
    context=row['context_regions'][0];name=row['context_media'][0]
    assert context=={'role':'qp','source_id':'asset:'+PAIRS['M1'][0],
        'source_sha256':descriptor['sources']['qp']['sha256'],'page':1,'box':[0,0,1,1]}
    with pymupdf.open(stream=inputs[1].read(context['source_id']),filetype='pdf') as doc:
        pix=doc[0].get_pixmap(dpi=144,alpha=False);expected=pix.tobytes('png')
        assert result['_pixels'][name]==expected
        proof=next(p for p in result['page_proofs'] if p['source']==context['source_id'] and p['page']==1)
        assert proof['pixels_sha256']==hashlib.sha256(pix.samples).hexdigest()
        assert (proof['width'],proof['height'])==(pix.width,pix.height)
        cover_text=prepared._region_text(doc,[context])
    assert cover_text in row['question_text'] and '9.8' in row['question_text']
    assert 'significant figures' in row['question_text']
    assert result['media'][name]=={'region':context,'visibility':'public_question',
        'sha256':hashlib.sha256(expected).hexdigest(),'bytes':len(expected)}
    assert not (out/name).exists() and name not in descriptor['media']
    assert set(row['context_media']).isdisjoint(row['mark_scheme_media'])
    assert all(result['media'][n]['visibility']=='private_answer' for n in row['mark_scheme_media'])
    packet=checks.build_packet(row)
    launch=checks.plan_attempt(packet)
    assert name in launch['images'] and '9.8' in launch['prompt']
    publication=practice.publish(inputs[0],[out],expected_current=None)
    collection=Collection(inputs[0]);public=collection.question(row['id'])
    assert '9.8' in public['question_text'] and len(public['context_media'])==1
    assert collection.media_path(row['id'],public['context_media'][0]).read_bytes()==expected
    assert not {'scheme_text','mark_scheme_regions','private_guidance_regions','answer'} & public.keys()
    private=collection._items[row['id']]['mark_scheme_media'][0]
    with pytest.raises(ValueError,match='private'):
        collection.media_path(row['id'],private)
    assert publication['new']==[row['id']]
    assert package_before=={p.relative_to(out).as_posix():p.read_bytes() for p in out.rglob('*') if p.is_file()}
