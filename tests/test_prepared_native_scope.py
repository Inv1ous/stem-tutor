"""Native source preparation uses real catalogued originals in a disposable vault."""
import copy
import hashlib
import importlib
import json
from pathlib import Path
import sys

import pymupdf
import pytest
from library_assets import copy_to_vault, read_bytes, canonical_path
from tutorlib.asset_library import AssetLibrary

sys.path.insert(0, str(Path(__file__).parents[1] / 'extraction'))
QP = 'asset:legacy-e934f2475d864b1fddbaf929'
MS = 'asset:legacy-1c5b81467c4b4a3e71f51442'
SPEC = 'Library/Shared/Sources/Specifications/ial-maths-spec.pdf'
S3_Q1 = 'S3_pearson-edexcel-ial_WST03_2023-06_01_q1'
GRAPH = 'a' * 64

def region(role, page, top=0, bottom=1):
    return {'role': role, 'page': page, 'box': [0, top, 1, bottom]}

def question(n):
    if n == 1:
        intervals = {'a': (.065, .125, .085, .145, .38, .42),
                     'b': (.13, .26, .145, .265, .42, .56),
                     'c': (.13, .365, .265, .36, .56, .65)}
        pages, mp = range(2, 6), 6
    else:
        intervals = {'a': (.065, .57, .083, .167, .53, .587),
                     'b': (.065, .715, .167, .505, .587, .91)}
        pages, mp = range(6, 10), 7
    q = {'number': n, 'question_regions': [region('qp', p) for p in pages],
            'scheme_regions': [region('ms', mp)],
            'parts': [{'part': part, 'label': f'({part})',
                       'question_media_regions': [region('qp', min(pages), a, b)],
                       'scheme_media_regions': [region('ms', mp, c, d), region('ms', mp, e, f)]}
                      for part, (a,b,c,d,e,f) in intervals.items()]}
    if n == 1:
        q['parts'][2]['question_media_regions'] = [region('qp',2,.13,.20),region('qp',2,.266,.365)]
    else:
        q['parts'][1]['question_media_regions'] = [region('qp',6,.065,.44),region('qp',6,.578,.715)]
    return q

@pytest.fixture
def inputs(tmp_path):
    vault = tmp_path / 'vault'; vault.mkdir()
    for asset in (QP, MS, SPEC):
        copy_to_vault(canonical_path(asset), vault)
        if asset.startswith('asset:'):
            catalog_path = vault / 'Library/catalog.json'
            catalog = json.loads(catalog_path.read_text())
            key = next(k for k, v in catalog['assets'].items() if v['path'] == canonical_path(asset))
            catalog['assets'][asset[6:]] = catalog['assets'].pop(key)
            catalog_path.write_text(json.dumps(catalog))
    lib = AssetLibrary(vault)
    req = {'course': 'S3', 'sources': {
        role: {'asset_id': asset, 'sha256': lib.record(asset)['sha256'], 'inspection_pages': pages}
        for role, asset, pages in [('qp', QP, list(range(1,10))), ('ms', MS, list(range(1,8)))]},
        'questions': [question(1)]}
    path = tmp_path / 'request.json'; path.write_text(json.dumps(req))
    return lib, req, path, tmp_path / 'package'

def module(): return importlib.import_module('prepared_scope')

def prepare(inputs):
    lib, req, path, out = inputs; path.write_text(json.dumps(req))
    return module().prepare_native(path, out, lib, GRAPH)

def test_real_s3_source_bound_package_and_renders(inputs):
    scope = prepare(inputs)
    assert scope['profile'] == 'pearson_native_prepared_v1'
    assert [q['official_qid'] for q in scope['questions']] == [S3_Q1]
    assert scope == module().verify_native_package(inputs[3], inputs[0], GRAPH)
    for name, media in scope['media'].items():
        r = media['region']; doc = pymupdf.open(stream=read_bytes(QP if r['role']=='qp' else MS), filetype='pdf')
        page = doc[r['page']-1]; b=r['box']; box = pymupdf.Rect(b[0]*page.rect.width,b[1]*page.rect.height,b[2]*page.rect.width,b[3]*page.rect.height)
        expected = page.get_pixmap(dpi=144, clip=box, alpha=False).tobytes('png')
        assert media['sha256'] == hashlib.sha256(expected).hexdigest()
        assert (inputs[3]/name).read_bytes() == expected
        assert name.startswith('public/' if r['role']=='qp' else 'private/')

def test_two_actual_same_paper_questions(inputs):
    inputs[1]['questions'].append(question(2)); scope = prepare(inputs)
    assert [q['official_qid'] for q in scope['questions']] == [S3_Q1, S3_Q1[:-1]+'2']
    assert len(scope['verified_pairs']) == 1

@pytest.mark.parametrize('change,blocker', [
    (lambda r: r['sources']['qp'].update(inspection_pages=[0]), 'inspection'),
    (lambda r: r['sources']['qp'].update(inspection_pages=[101]), 'inspection'),
    (lambda r: r.update(questions=[question(n) for n in range(1,10)]), '1..8'),
    (lambda r: r['questions'][0]['parts'].append(copy.deepcopy(r['questions'][0]['parts'][0])), 'part'),
    (lambda r: r['questions'][0]['parts'].pop(), 'part_inventory'),
    (lambda r: r['questions'][0]['parts'][0]['question_media_regions'][0].update(role='ms'), 'role'),
    (lambda r: r['sources'].update(qp=r['sources']['ms'], ms=r['sources']['qp']), 'source_role'),
    (lambda r: r.update(course='S2'), 'course'),
    (lambda r: r['questions'][0]['parts'][0]['question_media_regions'][0].update(box=[0,0,float('nan'),1]), 'box'),
    (lambda r: r['questions'][0].update(occurrence={'bundle':'../bad','complete_sha256':'b'*64,'id':'x'}), 'occurrence'),
])
def test_reject_bad_request(inputs, change, blocker):
    change(inputs[1])
    with pytest.raises(ValueError, match=blocker): prepare(inputs)

def test_tampered_render_cannot_be_resealed(inputs):
    scope=prepare(inputs); root=inputs[3]; name=next(iter(scope['media']))
    (root/name).write_bytes(b'not source pixels')
    scope['media'][name]['sha256']=hashlib.sha256(b'not source pixels').hexdigest()
    (root/'descriptor.json').write_bytes(module().canonical_bytes(scope))
    complete=json.loads((root/'COMPLETE').read_text())
    complete['descriptor_sha256']=hashlib.sha256((root/'descriptor.json').read_bytes()).hexdigest()
    (root/'COMPLETE').write_bytes(module().canonical_bytes(complete))
    with pytest.raises(ValueError,match='source_recomputation'): module().verify_native_package(root,inputs[0],GRAPH)

def test_reused_or_alias_output_is_refused(inputs):
    prepare(inputs)
    with pytest.raises(ValueError,match='fresh'): prepare(inputs)
    other=inputs[3].parent/'linked'; other.symlink_to(inputs[3],target_is_directory=True)
    with pytest.raises(ValueError,match='physical|fresh'): module().prepare_native(inputs[2],other,inputs[0],GRAPH)

@pytest.mark.parametrize('course,unit', [
    ('P1','WMA11'),('P2','WMA12'),('P3','WMA13'),('P4','WMA14'),
    ('FP1','WFM01'),('FP2','WFM02'),('FP3','WFM03'),('M1','WME01'),
    ('S1','WST01'),('S2','WST02'),('S3','WST03'),('D1','WDM11')])
def test_all_installed_unit_mappings_have_actual_2023_ms_cover(tmp_path,course,unit):
    from tutorlib.prepared_evidence import source_identity, COURSE_UNITS
    assert COURSE_UNITS[course]==unit and 'M2' not in COURSE_UNITS and 'M3' not in COURSE_UNITS
    path=f'Library/Courses/{course}/Sources/PastPapers/ial/{unit}/{unit}_2023_Jun_ms.pdf'
    vault=tmp_path/'vault';vault.mkdir(); physical=copy_to_vault(path,vault)
    with pymupdf.open(physical) as doc:
        exam=source_identity(path,'ms',course)
        assert module()._cover(doc,exam,'ms')['unit']==unit


def test_actual_2019_p1_ms_cover_unit_slash_component_form(tmp_path):
    from tutorlib.prepared_evidence import source_identity
    path=canonical_path('asset:legacy-49fc389000ec4447e3b10835')
    vault=tmp_path/'vault';vault.mkdir();physical=copy_to_vault(path,vault)
    with pymupdf.open(physical) as doc:
        assert module()._cover(doc,source_identity(path,'ms','P1'),'ms')['component']=='01'


def replace_disposable_cover(inputs,role,text):
    lib,request,_,_=inputs; pin=request['sources'][role]; record=lib.record(pin['asset_id'])
    with pymupdf.open(stream=lib.read(pin['asset_id']),filetype='pdf') as doc:
        doc[0].add_redact_annot(doc[0].rect);doc[0].apply_redactions()
        doc[0].insert_textbox(pymupdf.Rect(40,40,550,700),text,fontsize=12)
        data=doc.tobytes()
    (lib.root/record['path']).write_bytes(data)
    catalog_path=lib.root/'Library/catalog.json';catalog=json.loads(catalog_path.read_text())
    catalog['assets'][pin['asset_id'][6:]]['sha256']=hashlib.sha256(data).hexdigest()
    catalog_path.write_text(json.dumps(catalog));pin['sha256']=hashlib.sha256(data).hexdigest()
    return AssetLibrary(lib.root),request,inputs[2],inputs[3]


@pytest.mark.parametrize('text,blocker',[
    ('Pearson Edexcel International Advanced Level\nMark Scheme\nSummer 2023\nWST02\nPaper 01','competing_cover_marker'),
    ('Pearson Edexcel International Advanced Level\nMark Scheme\nSummer 2023\nWST03 WST02\nPaper 01','competing_cover_marker'),
    ('Pearson Edexcel International Advanced Level\nMark Scheme\nSummer 2022\nWST03\nPaper 01','cover_session'),
    ('Pearson Edexcel International Advanced Level\nMark Scheme\nSummer 2023\nWST03\nPaper 02','source_role|component'),
    ('Pearson Edexcel GCE Advanced Level\nMark Scheme\nSummer 2023\nWST03\nPaper 01','cover_identity'),
    ('PMT\nWST03 Summer 2023','cover_identity'),
])
def test_changed_original_cover_cannot_be_fixed_by_metadata(inputs,text,blocker):
    inputs=replace_disposable_cover(inputs,'ms',text)
    with pytest.raises(ValueError,match=blocker):prepare(inputs)


def test_publisher_publication_code_discrepancy_is_visible(inputs):
    scope=prepare(inputs)
    assert scope['sources']['ms']['issues']==[{
        'type':'publication_code_discrepancy','page':2,'label':'Publications Code',
        'value':'WST02_01_2306_MS','expected_unit':'WST03','disposition':'independent_review_required'}]


@pytest.mark.parametrize('unit,session,number', [('WMA11','2019-01',n) for n in (1,2,3,4)]+[('WMA12','2019-06',1)])
def test_exact_pilot_reservations_use_typed_exam_not_user_spelling(unit,session,number):
    from tutorlib.prepared_evidence import reject_reserved,project_identity
    with pytest.raises(ValueError,match='reserved_exact_pilot'):reject_reserved({'unit':unit,'session':session},number)
    course='P1' if unit=='WMA11' else 'P2'
    qid=f'{course}_pearson-edexcel-ial_{unit}_{session}_01_q{number}'
    for spelling in (qid,qid.lower(),qid.replace('_q','_q0'),qid.replace(course,'S3',1),'new_'+qid):
        assert project_identity({'profile':'pearson_native_prepared_v1','course':course,'official_qid':spelling,'part':''}) is None


def test_neutral_identity_projects_only_canonical_profile_without_pdf_import():
    import subprocess
    from tutorlib.prepared_evidence import project_identity
    source={'profile':'pearson_native_prepared_v1','course':'S3','official_qid':S3_Q1,'part':'b'}
    assert project_identity(source)==('S3',S3_Q1+':b')
    assert project_identity({**source,'profile':'other'}) is None
    command="import sys;sys.path.insert(0,'src');import tutorlib.prepared_evidence;assert not any(n in sys.modules for n in ('pymupdf','fitz','PIL'))"
    subprocess.run([sys.executable,'-c',command],cwd=Path(__file__).parents[1],check=True)


def test_legacy_6691_originals_stay_native_profile_incompatible(tmp_path):
    from tutorlib.prepared_evidence import source_identity
    for asset,role in [('asset:asset-cadfdb79e1343cfe71a9d528','qp'),('asset:asset-9f6c0dadf18831d2cec3b770','ms')]:
        path=canonical_path(asset);vault=tmp_path/role;vault.mkdir();copy_to_vault(path,vault)
        with pytest.raises(ValueError,match='source_role'):source_identity(path,role,'S3')


def test_sibling_public_paragraph_without_its_label_is_refused(inputs):
    inputs[1]['questions'][0]['parts'][0]['question_media_regions'].append({'role':'qp','page':2,'box':[.2,.21,1,.24]})
    with pytest.raises(ValueError,match='sibling_disclosure'):prepare(inputs)


def test_graph_drift_and_extra_media_fail_verification(inputs):
    prepare(inputs)
    with pytest.raises(ValueError,match='source_recomputation'):module().verify_native_package(inputs[3],inputs[0],'b'*64)
    (inputs[3]/'private/extra.png').write_bytes(b'extra')
    with pytest.raises(ValueError,match='inventory'):module().verify_native_package(inputs[3],inputs[0],GRAPH)


def test_native_cli_uses_existing_manager_dispatch(inputs,monkeypatch,capsys):
    import importlib.util
    spec=importlib.util.spec_from_file_location('prepared_cli_manager',Path(__file__).parents[1]/'extraction/extract.py')
    manager=importlib.util.module_from_spec(spec);spec.loader.exec_module(manager)
    monkeypatch.setenv('STEM_TUTOR_VAULT',str(inputs[0].root))
    monkeypatch.setattr(manager,'_course_graph_input',lambda course: ({},GRAPH))
    assert manager.main(['prepare-native','--request',str(inputs[2]),'--output',str(inputs[3])])==0
    assert json.loads(capsys.readouterr().out)['profile']=='pearson_native_prepared_v1'


def install_extra(inputs,asset):
    lib,request,path,out=inputs;relative=canonical_path(asset);copy_to_vault(relative,lib.root)
    catalog_path=lib.root/'Library/catalog.json';catalog=json.loads(catalog_path.read_text())
    key=next(k for k,v in catalog['assets'].items() if v['path']==relative)
    if asset.startswith('asset:'):
        catalog['assets'][asset[6:]]=catalog['assets'].pop(key);catalog_path.write_text(json.dumps(catalog))
    else:
        asset='asset:'+key
    return (AssetLibrary(lib.root),request,path,out),asset


def test_real_p1_q6_data_driven_compact_ms_rows_and_shared_context(inputs):
    qp='asset:legacy-5433803d0abf868d346949c8';ms='asset:legacy-49fc389000ec4447e3b10835'
    inputs,_=install_extra(inputs,qp);inputs,_=install_extra(inputs,ms)
    lib,request,_,_=inputs;request['course']='P1'
    request['sources']={role:{'asset_id':asset,'sha256':lib.record(asset)['sha256'],'inspection_pages':pages}
                        for role,asset,pages in [('qp',qp,[1,12,13]),('ms',ms,[1,2,3,4,5,6,7,16])]}
    request['questions']=[{'number':6,'question_regions':[region('qp',12),region('qp',13)],
                          'scheme_regions':[region('ms',16)],'parts':[
        {'part':'a','label':'(a)','question_media_regions':[region('qp',12,.065,.21)],
         'scheme_media_regions':[region('ms',16,.16,.28),region('ms',16,.42,.63),region('ms',16,.79,.925)]},
        {'part':'b','label':'(b)','question_media_regions':[region('qp',12,.065,.16),region('qp',12,.218,.26)],
         'scheme_media_regions':[region('ms',16,.28,.39),region('ms',16,.63,.925)]}]}]
    scope=prepare(inputs)
    assert scope['questions'][0]['official_qid']=='P1_pearson-edexcel-ial_WMA11_2019-01_01_q6'
    assert scope['questions'][0]['witness']['qp_parts']==['a','b']


def test_real_reference_cover_edition_and_part_binding(inputs):
    inputs,asset=install_extra(inputs,'Library/Shared/Sources/Specifications/ial-maths-formula-book.pdf')
    inputs[1]['sources']['reference']={'asset_id':asset,'sha256':inputs[0].record(asset)['sha256'],
                                     'inspection_pages':[1,33],'edition':'Issue 2','purpose':'Neutral complete correlation critical-value tables'}
    inputs[1]['questions'][0]['parts'][1]['reference_regions']=[region('reference',33)]
    scope=prepare(inputs);root=inputs[3]
    part=scope['questions'][0]['parts'][1]
    assert part['reference_media'] and all(name.startswith('public/') for name in part['reference_media'])
    seed=json.loads((root/'seed.json').read_text())
    assert seed['records'][1]['reference_media']==part['reference_media']


def test_over_100_distinct_selected_asset_pages_is_refused(inputs):
    inputs,asset=install_extra(inputs,'Library/Shared/Sources/Specifications/ial-maths-formula-book.pdf')
    lib,request,_,_=inputs;record=lib.record(asset)
    with pymupdf.open(stream=lib.read(asset),filetype='pdf') as doc:
        for _ in range(101-len(doc)):doc.new_page()
        data=doc.tobytes()
    (lib.root/record['path']).write_bytes(data)
    cp=lib.root/'Library/catalog.json';cat=json.loads(cp.read_text());cat['assets'][asset[6:]]['sha256']=hashlib.sha256(data).hexdigest();cp.write_text(json.dumps(cat))
    request['sources']['reference']={'asset_id':asset,'sha256':hashlib.sha256(data).hexdigest(),
                                    'inspection_pages':list(range(1,102)),'edition':'Issue 2','purpose':'Synthetic invalid page-limit request'}
    with pytest.raises(ValueError,match='selected_page_limit'):prepare((AssetLibrary(lib.root),request,inputs[2],inputs[3]))


def test_verified_legacy_pmt_occurrence_keeps_original_id_pending(inputs):
    inputs,asset=install_extra(inputs,'asset:asset-2974885b9b9ed953fc2e1d23')
    import topical_fastpath
    bundle_root=inputs[3].parent/'bundle'
    bundle=topical_fastpath.prepare(inputs[0].root,asset,'S3',bundle_root,dpi=72)
    original=bundle['questions'][1]
    occurrence={'bundle':str(bundle_root),'complete_sha256':hashlib.sha256((bundle_root/'COMPLETE').read_bytes()).hexdigest(),'id':original['id']}
    inputs[1]['questions'][0]['occurrence']=occurrence
    scope=prepare(inputs)
    pending=scope['questions'][0]['pending_occurrences'][0]
    assert pending['status']=='pending_identity_join' and pending['original_occurrence_id']==original['id']
    assert pending['regions']==original['regions'] and pending['source']['id']==asset
    assert pending['source']['id']!=scope['sources']['qp']['asset_id']
    occurrence['complete_sha256']='0'*64
    inputs[2].write_text(json.dumps(inputs[1]))
    with pytest.raises(ValueError,match='stale bundle'):module().prepare_native(inputs[2],inputs[3].parent/'stale',inputs[0],GRAPH)


@pytest.mark.parametrize('change,blocker',[
    (lambda r:r['questions'][0]['question_regions'].pop(),'terminator'),
    (lambda r:r['questions'][0]['parts'][0]['scheme_media_regions'].pop(),'crop_witness'),
    (lambda r:r['questions'][0]['parts'][0]['question_media_regions'][0].update(page=6),'containment'),
    (lambda r:r['questions'][0]['parts'][0].update(part='',label=''),'part_inventory|sibling'),
    (lambda r:r['questions'][0].update(official_qid='other'),'question request'),
])
def test_incomplete_or_competing_scope_stays_pending(inputs,change,blocker):
    change(inputs[1])
    with pytest.raises(ValueError,match=blocker):prepare(inputs)


def test_neutral_grammar_rejects_role_or_media_rebinding(inputs):
    from tutorlib.prepared_evidence import validate_descriptor
    scope=prepare(inputs)
    assert validate_descriptor(scope,inputs[0],GRAPH)==scope
    changed=copy.deepcopy(scope)
    name=next(iter(changed['media']));changed['media'][name]['visibility']='private'
    with pytest.raises(ValueError,match='media role'):validate_descriptor(changed)
    changed=copy.deepcopy(scope);changed['sources']['qp']['header_evidence']['role']='ms'
    with pytest.raises(ValueError,match='header role'):validate_descriptor(changed)


def test_native_request_rejects_duplicate_json_keys(inputs):
    inputs[2].write_text('{"course":"P1","course":"S3"}')
    with pytest.raises(ValueError,match='competing JSON'):module().prepare_native(inputs[2],inputs[3],inputs[0],GRAPH)


def test_wrong_timetable_month_does_not_inherit_summer_equivalence(inputs):
    text='Pearson Edexcel International Advanced Level\nMathematics Statistics S3\nPaper reference\nWST03/01\nTuesday 16 May 2023\nSummer 2023'
    inputs=replace_disposable_cover(inputs,'qp',text)
    with pytest.raises(ValueError,match='cover_session'):prepare(inputs)


def test_output_inside_source_learner_vault_is_refused(inputs):
    with pytest.raises(ValueError,match='outside the learner'):module().prepare_native(inputs[2],inputs[0].root/'bad-output',inputs[0],GRAPH)


def test_gate_request_strips_cannot_hide_actual_assessed_part(inputs):
    q=inputs[1]['questions'][0]
    q['parts']=q['parts'][:2]
    q['question_regions'][0]['box']=[0,0,1,.266]
    q['scheme_regions']=[region('ms',6,0,.265),region('ms',6,.35,.56)]
    with pytest.raises(ValueError,match='whole_question_scope|part_inventory'):
        prepare(inputs)


@pytest.mark.parametrize('role',['qp','ms'])
def test_gate_complete_parts_do_not_allow_inspection_holes(inputs,role):
    q=inputs[1]['questions'][0]
    if role=='qp':
        q['question_regions'][0]['box']=[0,0,1,.8]
    else:
        q['scheme_regions']=[region('ms',6,0,.8)]
    with pytest.raises(ValueError,match='whole_question_scope'):
        prepare(inputs)


def gate_page_boundary_inputs(inputs,total_reference_pages):
    inputs,asset=install_extra(inputs,'Library/Shared/Sources/Specifications/ial-maths-formula-book.pdf')
    lib,request,_,_=inputs;record=lib.record(asset)
    with pymupdf.open(stream=lib.read(asset),filetype='pdf') as doc:
        for _ in range(total_reference_pages-len(doc)):doc.new_page()
        data=doc.tobytes()
    (lib.root/record['path']).write_bytes(data)
    cp=lib.root/'Library/catalog.json';cat=json.loads(cp.read_text())
    cat['assets'][asset[6:]]['sha256']=hashlib.sha256(data).hexdigest();cp.write_text(json.dumps(cat))
    request['sources']['reference']={'asset_id':asset,'sha256':hashlib.sha256(data).hexdigest(),
                                    'inspection_pages':list(range(1,total_reference_pages+1)),
                                    'edition':'Issue 2','purpose':'Synthetic boundary request only'}
    return AssetLibrary(lib.root),request,inputs[2],inputs[3]


def test_gate_specification_page_makes_100_selected_source_pages_101(inputs):
    inputs=gate_page_boundary_inputs(inputs,84)
    assert sum(len(p['inspection_pages']) for p in inputs[1]['sources'].values())==100
    with pytest.raises(ValueError,match='selected_page_limit'):prepare(inputs)


def test_gate_100_total_pages_include_one_stable_specification_witness(inputs):
    from tutorlib.prepared_evidence import validate_descriptor
    inputs=gate_page_boundary_inputs(inputs,83)
    scope=prepare(inputs)
    spec_id=next('asset:'+key for key,value in inputs[0].records().items() if value['path']==SPEC)
    pairs={(r['asset_id'],r['page']) for r in scope['required_asset_pages']}
    assert (spec_id,84) in pairs and len(pairs)==100==scope['selected_asset_pages']
    assert len(scope['required_asset_pages'])==len(pairs)
    assert validate_descriptor(scope,inputs[0],GRAPH)==scope
    changed=copy.deepcopy(scope)
    changed['required_asset_pages']=[p for p in changed['required_asset_pages'] if p['asset_id']!=spec_id]
    changed['selected_asset_pages']=99
    with pytest.raises(ValueError,match='asset-page|specification'):validate_descriptor(changed)


@pytest.mark.parametrize('course',[[],{},None,17])
def test_gate_malformed_course_value_has_valueerror_contract(inputs,course):
    inputs[1].clear();inputs[1]['course']=course
    with pytest.raises(ValueError,match='unsupported native course'):prepare(inputs)


def test_gate_occurrence_witness_pages_count_once_with_original_ids(inputs):
    from tutorlib.prepared_evidence import validate_descriptor
    inputs,asset=install_extra(inputs,'asset:asset-2974885b9b9ed953fc2e1d23')
    import topical_fastpath
    bundle_root=inputs[3].parent/'gate-bundle'
    bundle=topical_fastpath.prepare(inputs[0].root,asset,'S3',bundle_root,dpi=72)
    original=bundle['questions'][1]
    occurrence={'bundle':str(bundle_root),'complete_sha256':hashlib.sha256((bundle_root/'COMPLETE').read_bytes()).hexdigest(),'id':original['id']}
    inputs[1]['questions'].append(question(2))
    for q in inputs[1]['questions']:q['occurrence']=copy.deepcopy(occurrence)
    scope=prepare(inputs)
    pending=scope['questions'][0]['pending_occurrences'][0]
    assert pending['source']['id']==asset and pending['original_occurrence_id']==original['id']
    occurrence_pages={1}|{r['page'] for r in original['regions']+original['context_regions']}
    assert pending['inspection_pages']==sorted(occurrence_pages)
    pairs={(r['asset_id'],r['page']) for r in scope['required_asset_pages']}
    assert {(asset,p) for p in occurrence_pages}<=pairs
    source_pairs={(s['asset_id'],p) for s in scope['sources'].values() for p in s['inspection_pages']}
    expected=source_pairs|{(scope['unit_mapping_evidence']['asset_id'],84)}|{(asset,p) for p in occurrence_pages}
    assert pairs==expected and len(pairs)==scope['selected_asset_pages']==len(scope['required_asset_pages'])
    # The source-authored end boundary is required even if an edited role pin
    # and edited inventory both try to omit the next scheme question's page.
    boundary=scope['questions'][1]['witness']['scheme_boundary']['page']
    assert boundary==8 and boundary in scope['sources']['ms']['inspection_pages']
    changed=copy.deepcopy(scope)
    changed['sources']['ms']['inspection_pages'].remove(boundary)
    changed['required_asset_pages']=[r for r in changed['required_asset_pages'] if (r['asset_id'],r['page'])!=(MS,boundary)]
    changed['selected_asset_pages']=len(changed['required_asset_pages'])
    with pytest.raises(ValueError,match='boundary asset-page'):validate_descriptor(changed)
    changed=copy.deepcopy(scope)
    changed['required_asset_pages']=[r for r in changed['required_asset_pages'] if r['asset_id']!=asset]
    changed['selected_asset_pages']=len(changed['required_asset_pages'])
    with pytest.raises(ValueError,match='asset-page'):validate_descriptor(changed)


WHOLE_MODE = 'whole_official_rubric_v1'
P1_QP = 'asset:legacy-5433803d0abf868d346949c8'
P1_MS = 'asset:legacy-49fc389000ec4447e3b10835'


@pytest.fixture
def whole_inputs(inputs):
    for asset in (P1_QP, P1_MS):
        inputs, _ = install_extra(inputs, asset)
    lib, request, path, out = inputs
    public = [region('qp', 10), region('qp', 11)]
    private = [region('ms', 14), region('ms', 15)]
    request.update(course='P1', sources={role: {'asset_id': asset,
        'sha256': lib.record(asset)['sha256'], 'inspection_pages': pages}
        for role, asset, pages in [('qp', P1_QP, [1,10,11]), ('ms', P1_MS, [1,3,4,5,14,15,16])]})
    request['questions'] = [{'number': 5, 'assessment_mode': WHOLE_MODE,
        'question_regions': public, 'scheme_regions': private,
        'private_guidance_regions': [region('ms', 3), region('ms', 4), region('ms', 5)],
        'parts': [{'part': '', 'label': '', 'question_media_regions': public, 'scheme_media_regions': private}]}]
    return inputs


def test_native_whole_q5_preserves_nested_markers_independent_totals_and_private_guidance(whole_inputs):
    d = prepare(whole_inputs); q = d['questions'][0]; part = q['parts'][0]
    assert q['assessment_mode'] == WHOLE_MODE and part['part'] == ''
    evidence = q['whole_assessment']
    assert type(evidence['max_marks']) is int and evidence['max_marks'] == 6
    assert evidence['totals']['qp']['region']['page'] == 11
    assert evidence['totals']['ms']['region']['page'] == 14
    assert evidence['totals']['qp']['value'] == evidence['totals']['ms']['value'] == 6
    for role in ('qp','ms'):
        raw = [m['text'] for m in evidence['printed_markers'][role]]
        assert '(i)' in raw and '(ii)' in raw
        assert all(m['region']['source_id'] == d['sources'][role]['asset_id'] for m in evidence['printed_markers'][role])
    assert [r['page'] for r in q['question_regions']] == [10,11]
    assert [r['page'] for r in q['scheme_regions']] == [14,15]
    assert q['witness']['scheme_boundary']['page'] == 16
    assert [d['media'][n]['region']['page'] for n in part['scheme_media']] == [3,4,5,14,15]
    assert all(d['media'][n]['visibility'] == 'private' for n in part['scheme_media'])
    seed = json.loads((whole_inputs[3]/'seed.json').read_text())['records'][0]
    assert seed['assessment_mode'] == WHOLE_MODE and seed['marks'] == 6
    assert seed['scheme'][0]['whole_rubric'] == {'version':1,'max_marks':6,'media':part['scheme_media']}
    assert not any(k in seed for k in ('stem','answer','kcs','syllabus','prerequisites'))
    assert {(r['asset_id'],r['page']) for r in d['required_asset_pages']} >= {(P1_MS,3),(P1_MS,4),(P1_MS,5),(P1_MS,6),(P1_MS,8),(P1_MS,16)}


@pytest.mark.parametrize('fault', ['unknown','stripped','partial-public','partial-core','reordered-core','mixed-parts',
    'publisher-guidance','answer-guidance','reordered-guidance','clipped-guidance','malformed-part'])
def test_native_whole_source_scope_and_guidance_fail_closed(whole_inputs, fault):
    q = whole_inputs[1]['questions'][0]
    if fault == 'unknown': q['assessment_mode'] = 'whole'
    elif fault == 'stripped': q.pop('assessment_mode')
    elif fault == 'partial-public': q['parts'][0]['question_media_regions'] = [region('qp',10)]
    elif fault == 'partial-core': q['parts'][0]['scheme_media_regions'] = [region('ms',14)]
    elif fault == 'reordered-core': q['scheme_regions'].reverse()
    elif fault == 'malformed-part': q['parts']=[None]
    elif fault == 'mixed-parts': q['parts'].append({**q['parts'][0], 'part':'a','label':'(a)'})
    elif fault == 'publisher-guidance':
        whole_inputs[1]['sources']['ms']['inspection_pages'].insert(1,2)
        q['private_guidance_regions'] = [region('ms',2)]
    elif fault == 'answer-guidance': q['private_guidance_regions'] = [region('ms',14)]
    elif fault == 'reordered-guidance': q['private_guidance_regions'].reverse()
    else: q['private_guidance_regions'][0]['box'] = [0,.1,1,.5]
    with pytest.raises(ValueError): prepare(whole_inputs)


def test_native_whole_neutral_witness_drift_cannot_relabel_part_subtotal(whole_inputs):
    from tutorlib.prepared_evidence import validate_descriptor
    d = prepare(whole_inputs)
    for fault in ('qp-question','ms-subtotal','bool-total','markers-missing','narrow-block'):
        bad = copy.deepcopy(d); q = bad['questions'][0]; w = q['whole_assessment']
        if fault == 'qp-question': w['totals']['qp']['region']['page'] = 10
        elif fault == 'ms-subtotal':
            w['totals']['ms']['label'] = '(2)'; w['totals']['ms']['value'] = 2
        elif fault == 'bool-total': w['max_marks'] = True
        elif fault == 'markers-missing': w['printed_markers']['qp'] = []
        else: q['parts'][0]['question_media_regions'].pop()
        with pytest.raises(ValueError): validate_descriptor(bad)


def legacy_control_package(inputs, case):
    if case == 'S3':
        prepare(inputs)
    elif case == 'P1Q6':
        test_real_p1_q6_data_driven_compact_ms_rows_and_shared_context(inputs)
    else:
        qp = 'asset:legacy-ddc29c27de07e2012cca42fc'; ms = 'asset:legacy-a010e1eb2b90436870af0c6f'
        for asset in (qp,ms): inputs,_ = install_extra(inputs,asset)
        lib, request, _, _ = inputs
        request.update(course='P1',sources={role:{'asset_id':asset,'sha256':lib.record(asset)['sha256'],'inspection_pages':pages}
            for role,asset,pages in [('qp',qp,[1,2,3,20,21,22,23]),('ms',ms,[1,2,3,4,5,6,7,8,19,20,21,22])]})
        request['questions']=[]
        for n,qp_pages,ms_pages in [(1,[2,3],[7]),(8,[20,21],[19]),(9,[22,23],[20,21])]:
            public=[region('qp',p) for p in qp_pages];private=[region('ms',p) for p in ms_pages]
            request['questions'].append({'number':n,'question_regions':public,'scheme_regions':private,
                'parts':[{'part':'','label':'','question_media_regions':public,'scheme_media_regions':private}]})
        prepare(inputs)
    return inputs[3]


def package_bytes_fingerprint(root):
    from tutorlib.prepared_evidence import canonical_bytes, sha
    return sha(canonical_bytes({p.relative_to(root).as_posix():sha(p.read_bytes())
                                for p in root.rglob('*') if p.is_file()}))


@pytest.mark.parametrize('case,expected', [
    ('S3','e7f756c9f91bbddbf12386b45b1055ad2b9847f4404e5d97aeacc0f45088278b'),
    ('P1Q6','4c0d3fe24484d81b071b1298c2e35447a22d29c234dd9a2e2e55ee6b6d5756ef'),
    ('P1Jan2020group','b3e49d29b60ad72c183c14dba8a213577553efd6cb4848946309249d5fc0a8f2'),
])
def test_native_whole_absent_mode_preserves_all_original_package_bytes(inputs,case,expected):
    root=legacy_control_package(inputs,case)
    assert package_bytes_fingerprint(root)==expected


def test_native_whole_guidance_requires_complete_continuation_and_allows_a_complete_section(whole_inputs):
    q=whole_inputs[1]['questions'][0]
    q['private_guidance_regions']=[region('ms',4)]
    with pytest.raises(ValueError,match='guidance'):prepare(whole_inputs)
    whole_inputs[1]['sources']['ms']['inspection_pages'].append(7)
    whole_inputs[1]['sources']['ms']['inspection_pages'].sort()
    q['private_guidance_regions']=[region('ms',7,.32,1)]
    d=prepare(whole_inputs)
    assert [d['media'][name]['region']['page'] for name in d['questions'][0]['parts'][0]['scheme_media']]==[7,14,15]


def test_native_whole_guidance_cannot_exceed_manual_private_image_limit(whole_inputs):
    whole_inputs[1]['questions'][0]['private_guidance_regions']=[region('ms',3)]*31
    with pytest.raises(ValueError):prepare(whole_inputs)


def test_native_whole_optional_guidance_is_omitted_without_changing_core_scope(whole_inputs):
    whole_inputs[1]['questions'][0].pop('private_guidance_regions')
    d=prepare(whole_inputs);q=d['questions'][0]
    assert 'private_guidance_regions' not in q and 'guidance_witness' not in q
    assert [d['media'][n]['region']['page'] for n in q['parts'][0]['scheme_media']]==[14,15]
    seed=json.loads((whole_inputs[3]/'seed.json').read_text())['records'][0]
    assert 'private_guidance_regions' not in seed
    assert seed['scheme'][0]['whole_rubric']['max_marks']==6


def guidance_transition_document(prefix, *, heading_y=70, graphic=None):
    """Disposable geometry counterexample, not a reusable teaching resource."""
    doc=pymupdf.open()
    page=doc.new_page()
    page.insert_text((40,45),'General Marking Guidance',fontsize=12)
    page.insert_text((40,80),'Award the sketch mark only for the curve illustrated overleaf.' if graphic else 'Award a method mark for a valid method.',fontsize=11)
    page=doc.new_page()
    page.insert_text((40,30),prefix,fontsize=11)
    if graphic=='vector':
        page.draw_polyline([(40,60),(70,30),(100,50),(140,35)],color=(0,0,0),width=1)
    elif graphic=='image':
        image=pymupdf.Pixmap(pymupdf.csRGB,pymupdf.IRect(0,0,20,20),False)
        image.clear_with(0)
        page.insert_image(pymupdf.Rect(40,25,140,65),stream=image.tobytes('png'))
    page.insert_text((40,heading_y),'Exact answers',fontsize=12)
    page.insert_text((40,heading_y+35),'Answers must be exact.',fontsize=11)
    page=doc.new_page()
    for point,text in [((40,40),'Question'),((40,55),'Number'),((180,40),'Scheme'),((500,40),'Marks'),((40,85),'1')]:
        page.insert_text(point,text,fontsize=11)
    return doc


def test_native_whole_guidance_cannot_drop_an_exception_above_an_early_next_heading():
    phrase='Withhold that mark if the given result was used.'
    with guidance_transition_document(phrase) as doc:
        layout=module()._source_layout(doc,'ms')
        assert layout[2]['starts'][0]['number']==1
        assert not layout[0]['starts'] and not layout[1]['starts']
        first={'role':'ms','source_id':'asset:synthetic-guidance-ms','source_sha256':'a'*64,'page':1,'box':[0,0,1,1]}
        with pytest.raises(ValueError,match='guidance'):
            module()._private_guidance([first],layout,{'ms':doc})
        top=min(w['box'][1] for w in layout[1]['words'] if w['text']=='Exact')
        assert top<.16
        exception={**first,'page':2,'box':[0,0,1,top]}
        assert phrase in module()._region_text(doc,[exception])
        result=module()._private_guidance([first,exception],layout,{'ms':doc})
        assert result['first_question_page']==3
        assert result['regions'][1]['region']==exception
        assert [h['heading'] for h in result['regions'][1]['headings']]==['General Marking Guidance']


def test_native_whole_guidance_exempts_the_recognized_edition_title_only():
    with guidance_transition_document('PEARSON EDEXCEL IAL MATHEMATICS') as doc:
        layout=module()._source_layout(doc,'ms')
        first={'role':'ms','source_id':'asset:synthetic-guidance-ms','source_sha256':'a'*64,'page':1,'box':[0,0,1,1]}
        result=module()._private_guidance([first],layout,{'ms':doc})
        assert len(result['regions'])==1
        assert result['boundary_headings'][0]['region']['page']==2


@pytest.mark.parametrize('heading_y,graphic', [(260,'vector'),(110,'vector'),(110,'image')])
def test_native_whole_guidance_preserves_graphic_prefix_without_native_words(heading_y,graphic):
    with guidance_transition_document('',heading_y=heading_y,graphic=graphic) as doc:
        layout=module()._source_layout(doc,'ms')
        assert layout[2]['starts'][0]['number']==1
        top=min(w['box'][1] for w in layout[1]['words'] if w['text']=='Exact')
        assert (top>.16)==(heading_y==260)
        assert not [w for w in layout[1]['words'] if w['box'][1]<top-.003]
        first={'role':'ms','source_id':'asset:synthetic-guidance-ms','source_sha256':'a'*64,'page':1,'box':[0,0,1,1]}
        with pytest.raises(ValueError,match='guidance'):
            module()._private_guidance([first],layout,{'ms':doc})
        figure={**first,'page':2,'box':[0,0,1,top]}
        result=module()._private_guidance([first,figure],layout,{'ms':doc})
        assert len(result['regions'])==2 and result['regions'][1]['region']==figure
        assert [h['heading'] for h in result['regions'][1]['headings']]==['General Marking Guidance']
