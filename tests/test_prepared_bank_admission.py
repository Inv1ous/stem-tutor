"""Prepared admission uses real originals, mocked providers and disposable vaults.

The S3 pack here is synthetic code-path scaffolding, never production readiness.
"""
import copy
import json
from pathlib import Path

import pytest
from test_prepared_native_scope import inputs, module, install_extra, region, whole_inputs
import test_extraction_prepared_scope as lifecycle
from test_extraction_prepared_scope import native_whole_prepared
from tutorlib import packs, store, topicals
from tutorlib.asset_library import AssetLibrary


@pytest.fixture
def admitted(inputs, monkeypatch, tmp_path, external=False):
    inputs, reference = install_extra(inputs, 'Library/Shared/Sources/Specifications/ial-maths-formula-book.pdf')
    inputs[1]['sources']['reference'] = {'asset_id': reference, 'sha256': inputs[0].record(reference)['sha256'],
        'inspection_pages': [1,33], 'edition': 'Issue 2', 'purpose': 'Neutral complete correlation critical-value tables'}
    for part in inputs[1]['questions'][0]['parts'][1:]:
        part['reference_regions'] = [region('reference',33)]
    inputs[2].write_text(json.dumps(inputs[1]))
    prepared = lifecycle.prepared.__wrapped__(inputs, monkeypatch, tmp_path)
    ex, lib, request, path, original = prepared
    graph_path = Path(ex.os.environ['STEM_LIBRARY_SPECS']) / 'S3/graph.json'
    graph = json.loads(graph_path.read_text())
    graph.update(version='synthetic-s3-v1', subject='maths', topics=[])
    graph['kcs'][0].update(level='S3',title='Synthetic S3 concept',statement='Synthetic code-path concept only.')
    graph['subtopics'][0]['level'] = 'S3'
    if external:
        from library_assets import read_bytes
        authority=read_bytes('build/out/specs/P1/graph.json')
        target=graph_path.parent.parent/'P1/graph.json';target.parent.mkdir(parents=True)
        target.write_bytes(authority)
        graph['kcs'][0]['prereqs']=['P1-1.5']
        original_candidate=lifecycle.candidate
        def dependent(state,descriptor):
            data=original_candidate(state,descriptor)
            for row in data['questions']:row['prerequisites']=['P1-1.5']
            return data
        monkeypatch.setattr(lifecycle,'candidate',dependent)
    graph_path.write_text(json.dumps(graph))
    out = original.with_name('runtime-package')
    module().prepare_native(path, out, lib, ex._course_graph_input('S3')[1])
    prepared = ex, lib, request, path, out
    runtime = lib.root / '.tutor/packs/v1'
    (runtime / 'specs/S3/packs').mkdir(parents=True)
    (runtime / 'specs/S3/graph.json').write_bytes(graph_path.read_bytes())
    if external:
        (runtime/'specs/P1').mkdir(parents=True)
        (runtime/'specs/P1/graph.json').write_bytes(authority)
    (runtime / 'manifest.json').write_text(json.dumps({'specs':['S3','P1'] if external else ['S3']}))
    (runtime / 'plan.json').write_text('{}')
    (runtime.parent / 'CURRENT').write_text('v1')
    lifecycle.completed(prepared, monkeypatch)
    state = ex.check('fresh'); assert state['stage'] == 'reviewed', state['problems']
    ex.register('fresh')
    batch = tmp_path / 'batch'; ex.prepare_publication('fresh', batch)
    bank = json.loads((batch / 'bank.json').read_text())
    return ex, AssetLibrary(lib.root), batch, bank


def test_attested_full_group_roundtrip_and_every_projection_tamper(admitted):
    ex, lib, batch, bank = admitted
    runtime = packs.Packs(store.Vault(lib.root))
    topicals.validate_bank(bank, runtime, lib.root)
    assert len(bank['items']) == 3
    marker = bank['items'][0]['source']['prepared_admission']
    assert marker['profile'] == 'pearson_native_prepared_v1'
    attestation = json.loads(lib.read(marker['attestation_ref']))
    assert attestation['schema_version'] == 1
    assert {r['role'] for r in attestation['manager_receipts']} == {'extract','review'}
    faults = {
        'missing-sibling': lambda b: b['items'].pop(),
        'public-swap': lambda b: b['items'][0].update(images=b['items'][1]['images']),
        'answer': lambda b: b['items'][0].update(answer='changed'),
        'mark': lambda b: b['items'][0].update(marks=2),
        'rubric': lambda b: b['items'][0]['scheme'][0].update(point='changed'),
        'part': lambda b: b['items'][0]['source'].update(part='z'),
        'syllabus': lambda b: b['items'][0]['topical'].update(chapters=['S3-2']),
        'prerequisite': lambda b: b['items'][0]['source'].update(extraction_prerequisites=['S3-1.1']),
        'support': lambda b: b['items'][0]['topical'].update(support={'S3-1':'changed'}),
        'difficulty': lambda b: b['items'][0].update(difficulty=5),
        'job': lambda b: b['items'][0]['source'].update(extraction_job='other'),
        'candidate': lambda b: b['items'][0]['source'].update(candidate_sha256='0'*64),
        'source': lambda b: b['items'][0]['source']['extraction_regions'][0].update(source_id='asset:other'),
        'unrelated-attestation': lambda b: b['items'][0]['source']['prepared_admission'].update(attestation_ref=attestation['candidate']['reference']),
        'stripped-marker': lambda b: b['items'][0]['source'].pop('prepared_admission'),
        'case-fallback': lambda b: b['items'][0]['source'].update(qid=b['items'][0]['source']['qid'].lower(), ref='CAIE 9702 Jun 2023 P22 Q1'),
        'caie-fallback': lambda b: b['items'][0]['source'].update(qid='S3_unknown', ref='CAIE 9702 Jun 2023 P22 Q1'),
    }
    for label, mutate in faults.items():
        changed=copy.deepcopy(bank); mutate(changed)
        with pytest.raises(ValueError):
            topicals.validate_bank(changed, runtime, lib.root)
        legacy=lib.root/'.tutor/topicals/untrusted';legacy.mkdir(parents=True,exist_ok=True)
        (legacy/'bank.json').write_text(json.dumps(changed))
        pointer=legacy.parent/'CURRENT';pointer.write_text('untrusted')
        reloaded=packs.Packs(store.Vault(lib.root))
        assert not reloaded.topicals.items and reloaded.topical_errors,label
        pointer.unlink()
        (batch/'bank.json').write_text(json.dumps(changed))
        with pytest.raises(ValueError): ex.publish('fresh', batch)
        import topicals as importer
        with pytest.raises(ValueError): importer.publish(batch, lib.root)
        assert not (lib.root/'.tutor/topicals/CURRENT').exists(), label
    (batch/'bank.json').write_text(json.dumps(bank))
    ex.publish('fresh', batch)
    fresh = packs.Packs(store.Vault(lib.root))
    assert not fresh.topical_errors and len(fresh.topicals.items) == 3
    install_synthetic_lesson(lib)
    from tutorlib import session
    tutor=session.Tutor(store.Vault(lib.root))
    for mode in ('learn','test','review'):
        tutor.start(mode,focus=['S3-1'],replace=True)
        activity=tutor.next()
        assert not any(i.get('kind')=='structured' for i in activity.get('items',[])),(mode,activity)
    tutor.start('topical',focus=['S3-1'],replace=True,topical_count=1,topical_types=['structured'])
    selected=tutor.next()['items'][0]
    assert not selected.get('manual_marking')
    result=tutor.answer(f"{selected['n']} pts=1")
    assert result['results'][0].get('event'),result


def test_collector_requires_authenticated_applicable_binding(admitted):
    from tutor_workers.collector_question_key import question_key
    ex, lib, _, bank = admitted
    row=json.loads(Path(ex.load('fresh')['candidate']).read_text())['questions'][0]
    graphs={'S3':({'S3-1'},{'S3-1.1':'S3-1'})}
    assert question_key('S3',row,graphs,lib) is None
    key=question_key('S3',row,graphs,lib,bank_item=bank['items'][0])
    assert key is not None
    minimal={k:row[k] for k in ('official_qid','part','syllabus','kcs')}
    assert question_key('S3',minimal,graphs,lib,bank_item=bank['items'][0])==key
    assert question_key('S3',{**minimal,'official_qid':None},graphs,lib,bank_item=bank['items'][0]) is None
    wrong=copy.deepcopy(row); wrong['answer']='changed'
    assert question_key('S3',wrong,graphs,lib,bank_item=bank['items'][0]) is None


def test_original_catalog_and_bytes_are_revalidated_without_a_stale_load_cache(admitted):
    ex, lib, batch, bank = admitted
    ex.publish('fresh', batch)
    runtime = packs.Packs(store.Vault(lib.root))
    assert len(runtime.topicals.items) == 3
    marker = bank['items'][0]['source']['prepared_admission']
    attestation = json.loads(lib.read(marker['attestation_ref']))
    references = [marker['attestation_ref'], attestation['descriptor']['reference'],
                  attestation['candidate']['reference'], attestation['review']['reference'],
                  attestation['graph']['reference'], bank['items'][0]['images'][0],
                  next(iter(next(iter(attestation['media'].values())).values()))['sidecar']['reference'],
                  'asset:legacy-e934f2475d864b1fddbaf929']
    for reference in references:
        path = lib.root / lib.record(reference)['path']; raw = path.read_bytes()
        path.write_bytes(raw + b'corrupt')
        runtime.topicals.refresh()
        assert not runtime.topicals.items and runtime.topicals.errors, reference
        path.write_bytes(raw)
        runtime.topicals.refresh()
        assert len(runtime.topicals.items) == 3 and not runtime.topicals.errors
    for field, value in [('kind','Diagrams'),('course','P1')]:
        path=lib.root/'Library/catalog.json'; raw=path.read_bytes(); catalog=json.loads(raw)
        next(r for r in catalog['assets'].values() if r['path']==bank['items'][0]['images'][0])[field]=value
        path.write_text(json.dumps(catalog)); runtime.topicals.refresh()
        assert not runtime.topicals.items and runtime.topicals.errors
        path.write_bytes(raw); runtime.topicals.refresh()
        assert len(runtime.topicals.items)==3

    path=lib.root/'Library/catalog.json'; raw=path.read_bytes(); catalog=json.loads(raw)
    next(r for r in catalog['assets'].values() if r['path'].endswith('/ial-maths-formula-book.pdf'))['kind']='Diagrams'
    path.write_text(json.dumps(catalog)); runtime.topicals.refresh()
    assert not runtime.topicals.items and runtime.topicals.errors
    path.write_bytes(raw)


def test_registration_retry_is_identical_and_stale_current_is_reprepared(admitted, tmp_path):
    ex, lib, batch, bank = admitted
    before=(lib.root/'Library/catalog.json').read_bytes()
    marker=ex.load('fresh')['prepared_admission']
    ex.register('fresh')
    assert ex.load('fresh')['prepared_admission']==marker
    assert (lib.root/'Library/catalog.json').read_bytes()==before
    import topicals as importer
    empty=tmp_path/'empty';empty.mkdir()
    (empty/'bank.json').write_text(json.dumps({**bank,'items':[]}))
    (empty/'report.json').write_text(json.dumps({'preparation':{'expected_current':None}}))
    importer.publish(empty,lib.root)
    pointer=lib.root/'.tutor/topicals/CURRENT'; current=pointer.read_bytes()
    with pytest.raises(ValueError): ex.publish('fresh',batch)
    assert pointer.read_bytes()==current
    ex.prepare_publication('fresh',tmp_path/'fresh-preparation')
    ex.publish('fresh',tmp_path/'fresh-preparation')
    assert pointer.read_bytes()!=current


@pytest.fixture
def whole_admitted(inputs, monkeypatch, tmp_path):
    original=lifecycle.candidate
    def sentinel(state,descriptor):
        data=original(state,descriptor)
        for row in data['questions']:
            row['scheme']=[{'point':'Synthetic whole-rubric sentinel; not content approval.',
                           'whole_rubric':{'version':1,'max_marks':row['marks'],'media':row['mark_scheme_media']}}]
        return data
    monkeypatch.setattr(lifecycle,'candidate',sentinel)
    return admitted.__wrapped__(inputs,monkeypatch,tmp_path)


def install_synthetic_lesson(lib):
    """Explicitly synthetic readiness; never evidence of the real S3 release."""
    base=lib.root/'.tutor/packs/v1'
    pack={'subtopic':'S3-1','spec':'S3','note':'Subjects/S3/synthetic.md','outline':'Synthetic lesson.',
          'items':[],'worked':[],'flashcards':[],'misconceptions':[]}
    (base/'specs/S3/packs/S3-1.json').write_text(json.dumps(pack))
    (lib.root/'.tutor/config.json').write_text(json.dumps({'tz':'Asia/Hong_Kong'}))


@pytest.mark.parametrize('mode',['topical','long'])
def test_actual_selectors_private_disclosure_and_selected_manual_mode(whole_admitted, mode):
    from tutorlib import session
    ex,lib,batch,bank=whole_admitted
    install_synthetic_lesson(lib);ex.publish('fresh',batch)
    tutor=session.Tutor(store.Vault(lib.root))
    start=tutor.start(mode,focus=['S3-1'])
    assert not start.get('error'),start
    act=tutor.next();assert act.get('items'),act
    view=act['items'][0];n=view['n']
    assert view['manual_marking'] is True
    text=json.dumps(view)
    assert not any(k in view for k in ('answer','scheme','point','media','ticket'))
    shown=tutor.session['presented'][str(n)]['inst']
    for item in bank['items']:
        for private in item['scheme'][0]['whole_rubric']['media']: assert private not in text
        if item['id'] != shown['id']:
            own_question=item['images'][:len(json.loads(Path(ex.load('fresh')['candidate']).read_text())['questions'][bank['items'].index(item)]['question_media'])]
            assert not set(own_question) & set(view.get('images',[]))
    assert tutor.whole_rubric(n,'idk').get('error')
    tutor.session['skipped_answer_guards']={'other':{'question':{'inst':{'answer':'protected'}}}}
    assert tutor.whole_rubric(n,'My substantive written solution.').get('error')
    tutor.session.pop('skipped_answer_guards')
    pending=tutor.session['presented'][str(n)];pending['unassisted']=True
    assert tutor.hint(n).get('refused')
    pending['unassisted']=False
    work='My substantive written solution.'
    rubric=tutor.whole_rubric(n,work)
    assert rubric.get('ticket'),rubric
    assert rubric['media']==shown['scheme'][0]['whole_rubric']['media']
    result=tutor.answer(f'{n} = {work}',manual_awards={n:{'earned_marks':1,'ticket':rubric['ticket']}})
    assert result['results'][0].get('event'),result
    event=next(e for e in tutor.vault.events() if e.get('id')==result['results'][0]['event'])
    assert event['human_award']['marker']=='human'
    restart=tutor.start(mode,focus=['S3-1'],replace=True)
    assert not restart.get('error'),restart
    next_view=tutor.next()['items'][0]
    skipped=next_view['n'];tutor.answer(f'{skipped}?')
    retry=tutor.retry_skipped();assert retry.get('items'),retry
    retried=retry['items'][0]['n']
    disclosed=tutor.whole_rubric(retried,'My substantive retried solution.')
    assert disclosed.get('ticket'),disclosed
    private=lib.root/disclosed['media'][0];raw=private.read_bytes();private.write_bytes(raw+b'changed')
    stale=tutor.answer(f'{retried} = My substantive retried solution.',
        manual_awards={retried:{'earned_marks':1,'ticket':disclosed['ticket']}})
    assert stale['results'][0].get('error'),stale
    private.write_bytes(raw)
    assert not tutor.regrade(event['id'],'AI replacement')['ok']


@pytest.mark.parametrize('qid',[None,'S3_unknown'])
def test_stripped_direct_whole_rubric_cannot_use_the_empty_caie_media_exception(whole_admitted,qid):
    _, lib, _, bank = whole_admitted
    item=copy.deepcopy(bank['items'][0])
    item['source'].pop('prepared_admission')
    if qid is not None: item['source']['qid']=qid
    item['scheme'][0]['whole_rubric']['media']=[]
    with pytest.raises(ValueError): topicals.whole_rubric_media(item,lib.root)


def test_runtime_hashes_each_original_and_attestation_once_per_load_and_never_renders(admitted,monkeypatch):
    from collections import Counter
    import time
    import pymupdf
    ex,lib,batch,bank=admitted
    ex.publish('fresh',batch)
    displaylists=[]
    displaylist=pymupdf.Page.get_displaylist
    def displayed(page,*args,**kwargs):
        displaylists.append((id(page.parent),page.number+1))
        return displaylist(page,*args,**kwargs)
    monkeypatch.setattr(pymupdf.Page,'get_displaylist',displayed)
    descriptor=ex._verify_prepared(ex.load('fresh'))
    rendered_pages={(m['region']['role'],m['region']['page']) for m in descriptor['media'].values()}
    assert len(displaylists)==len(set(displaylists))==len(rendered_pages)==3
    original=AssetLibrary.read
    reads=Counter()
    def counted(reader,reference,**kwargs):
        reads[reader.record(reference)['path']]+=1
        return original(reader,reference,**kwargs)
    def forbidden(*args,**kwargs):
        raise AssertionError('Runtime must not parse or render source PDFs')
    monkeypatch.setattr(AssetLibrary,'read',counted)
    monkeypatch.setattr(pymupdf,'open',forbidden)
    start=time.monotonic()
    for _ in range(2):
        runtime=packs.Packs(store.Vault(lib.root))
        assert len(runtime.topicals.items)==3 and not runtime.topical_errors
    elapsed=time.monotonic()-start
    marker=bank['items'][0]['source']['prepared_admission']
    originals=[r['path'] for r in lib.records().values() if r['path'].endswith('.pdf')]
    assert all(reads[path]==2 for path in originals)
    assert reads[marker['attestation_ref']]==2
    metrics={'prepared_distinct_source_pages':descriptor['selected_asset_pages'],
             'prepared_crop_count':len(descriptor['media']),'displaylist_pages_per_recomputation':3,
             'displaylist_calls_measured':len(displaylists),'independent_loads':2,'elapsed_seconds':elapsed,'pdf_parse_calls':0,'render_calls':0,
             'original_reads':{p:reads[p] for p in originals},'attestation_reads':2,
             'whole_questions':1,'assessed_rows_registered':3,'assessed_rows_loaded_each_time':3,
             'provider_calls':'two mocked actual manager completions per fixture; no real provider calls'}
    (lib.root.parent/'runtime-metrics.json').write_text(json.dumps(metrics,indent=2))
    runtime.kcs['S3-1.1']['level']='AS'
    with pytest.raises(ValueError): topicals.validate_bank(bank,runtime,lib.root)


def test_new_p1_q6_uses_attestation_while_q1_to_q4_keep_exact_precedence(inputs,monkeypatch,tmp_path):
    """Real P1 originals, synthetic graph/content, real manager completion only."""
    qp='asset:legacy-5433803d0abf868d346949c8';ms='asset:legacy-49fc389000ec4447e3b10835'
    inputs,_=install_extra(inputs,qp);inputs,_=install_extra(inputs,ms)
    lib,request,path,out=inputs
    request['course']='P1'
    request['sources']={role:{'asset_id':asset,'sha256':lib.record(asset)['sha256'],'inspection_pages':pages}
        for role,asset,pages in [('qp',qp,[1,12,13]),('ms',ms,[1,2,3,4,5,6,7,16])]}
    request['questions']=[{'number':6,'question_regions':[region('qp',12),region('qp',13)],
        'scheme_regions':[region('ms',16)],'parts':[
        {'part':'a','label':'(a)','question_media_regions':[region('qp',12,.065,.21)],
         'scheme_media_regions':[region('ms',16,.16,.28),region('ms',16,.42,.63),region('ms',16,.79,.925)]},
        {'part':'b','label':'(b)','question_media_regions':[region('qp',12,.065,.16),region('qp',12,.218,.26)],
         'scheme_media_regions':[region('ms',16,.28,.39),region('ms',16,.63,.925)]}]}]
    path.write_text(json.dumps(request))
    monkeypatch.setenv('STEM_TUTOR_VAULT',str(lib.root))
    monkeypatch.setenv('STEM_EXTRACT_ROOT',str(tmp_path/'Work'))
    monkeypatch.delenv('STEM_LIBRARY_ROOT',raising=False)
    runtime=lib.root/'.tutor/packs/v1';(runtime/'specs/P1/packs').mkdir(parents=True)
    graph={'course':'P1','version':'synthetic-p1-v1','subject':'maths','topics':[],
           'subtopics':[{'id':'P1-4','level':'P1'}],
           'kcs':[{'id':'P1-4.1','level':'P1','subtopic':'P1-4','prereqs':[]}]}
    (runtime/'specs/P1/graph.json').write_text(json.dumps(graph))
    (runtime/'manifest.json').write_text(json.dumps({'specs':['P1']}));(runtime/'plan.json').write_text('{}')
    (runtime.parent/'CURRENT').write_text('v1')
    monkeypatch.setenv('STEM_LIBRARY_SPECS',str(runtime/'specs'))
    from test_extraction import extraction
    ex=extraction();module().prepare_native(path,out,lib,ex._course_graph_input('P1')[1])
    original=lifecycle.candidate
    def sentinel(state,descriptor):
        data=original(state,descriptor)
        for row in data['questions']:row.update(syllabus=['P1-4'],kcs=['P1-4.1'])
        return data
    monkeypatch.setattr(lifecycle,'candidate',sentinel)
    ex.create('fresh','P1',provider='codex',scope='questions',prepared_scope=out,codex_stop_remaining=20)
    ex.plan('fresh');lifecycle.mock_workers(ex,monkeypatch)
    for role in ('extract','review'):
        ex.run('fresh',weekly_remaining=49);ex._worker('fresh',role)
    assert ex.check('fresh')['stage']=='reviewed'
    ex.register('fresh');batch=tmp_path/'p1-batch';ex.prepare_publication('fresh',batch)
    ex.publish('fresh',batch)
    loaded=packs.Packs(store.Vault(lib.root));assert not loaded.topical_errors
    assert [topicals.identity(i) for i in loaded.topicals.items]==[
        'P1_pearson-edexcel-ial_WMA11_2019-01_01_q6:a','P1_pearson-edexcel-ial_WMA11_2019-01_01_q6:b']
    from tutorlib.prepared_evidence import project_identity
    for n in (1,2,3,4):
        assert project_identity({'profile':'pearson_native_prepared_v1','course':'P1',
            'official_qid':f'P1_pearson-edexcel-ial_WMA11_2019-01_01_q{n}','part':''}) is None


@pytest.mark.parametrize('qid',['some_pearson_question','S3_unknown','s3_unknown','FP2_unknown','D1_unknown'])
def test_pearson_resemblance_never_falls_back_to_a_caie_citation(qid):
    source={'qid':qid,'part':'a','ref':'CAIE 9702 Jun 2023 P22 Q1'}
    assert topicals.identity({'source':source}) is None
    assert topicals.official_course(source) is None


@pytest.mark.parametrize('operation',['register','publish'])
def test_concurrent_new_manager_review_cannot_activate_an_old_registration(admitted,monkeypatch,operation):
    ex,lib,batch,_=admitted
    def supersede():
        with ex.state_lock('fresh') as current:
            current['jobs']['review'].update(attempt_id='concurrent-new-attempt',finished=None,ok=None)
            current['stage']='review_required'
    if operation=='register':
        import tutorlib.asset_library as assets
        original=assets.write_asset;called=False
        def writing(*args,**kwargs):
            nonlocal called
            if not called:supersede();called=True
            return original(*args,**kwargs)
        monkeypatch.setattr(assets,'write_asset',writing)
        action=lambda:ex.register('fresh')
    else:
        original=ex._active_topical_bank
        def current(vault):
            result=original(vault);supersede();return result
        monkeypatch.setattr(ex,'_active_topical_bank',current)
        action=lambda:ex.publish('fresh',batch)
    with pytest.raises(ValueError):action()
    assert not (lib.root/'.tutor/topicals/CURRENT').exists()
    assert ex.load('fresh')['jobs']['review']['attempt_id']=='concurrent-new-attempt'
    assert ex.load('fresh')['stage']=='review_required'


def test_exact_projection_rejects_equal_but_differently_typed_region_numbers(admitted):
    _,lib,_,bank=admitted
    runtime=packs.Packs(store.Vault(lib.root))
    for field in ('page','box'):
        changed=copy.deepcopy(bank)
        region=changed['items'][0]['source']['extraction_regions'][0]
        if field=='page':region['page']=float(region['page'])
        else:region['box'][0]=False
        with pytest.raises(ValueError):topicals.validate_bank(changed,runtime,lib.root)


def test_prepared_external_authority_version_facts_and_prerequisite_policy(inputs,monkeypatch,tmp_path):
    ex,lib,batch,bank=admitted.__wrapped__(inputs,monkeypatch,tmp_path,external=True)
    runtime=packs.Packs(store.Vault(lib.root));item=bank['items'][0]
    assert item['topical']['requires']==['S3-1','P1-1']
    assert item['topical']['prerequisite_versions']=={'P1':runtime.syllabus_versions['P1']}
    missing=topicals.eligibility(item,'S3-1',{},runtime,unassisted=True)
    assert missing['status']=='unavailable' and missing['missing']==['P1-1']
    ready=topicals.eligibility(item,'S3-1',{'started_chapters':['P1-1']},runtime,unassisted=True)
    assert ready['status']=='solvable'
    for field,value in [('level','AS'),('subtopic','P1-2'),('prereqs',[])]:
        before=runtime.kcs['P1-1.5'][field]
        assert before!=value
        runtime.kcs['P1-1.5'][field]=value
        with pytest.raises(ValueError):topicals.validate_bank(bank,runtime,lib.root)
        runtime.kcs['P1-1.5'][field]=before
    version=runtime.syllabus_versions['P1'];runtime.syllabus_versions['P1']='stale'
    with pytest.raises(ValueError):topicals.validate_bank(bank,runtime,lib.root)
    runtime.syllabus_versions['P1']=version
    marker=item['source']['prepared_admission'];attestation=json.loads(lib.read(marker['attestation_ref']))
    path=lib.root/attestation['external_graphs']['P1']['reference'];raw=path.read_bytes()
    path.write_bytes(raw+b'changed')
    with pytest.raises(ValueError):topicals.validate_bank(bank,runtime,lib.root)
    path.write_bytes(raw)
    ex.publish('fresh',batch)
    assert not packs.Packs(store.Vault(lib.root)).topical_errors


@pytest.mark.parametrize('replacement',['bank','report','missing-report'])
def test_fix_round1_checked_batch_replacement_cannot_activate(admitted,monkeypatch,replacement):
    ex,lib,batch,bank=admitted
    import topicals as importer
    original=importer.publish
    catalog=(lib.root/'Library/catalog.json').read_bytes()
    def replaced(*args,**kwargs):
        if replacement=='bank':
            (batch/'bank.json').write_text(json.dumps({**bank,'items':[]}))
        elif replacement=='report':
            report=json.loads((batch/'report.json').read_bytes())
            report['extraction']['job']='unrelated-job'
            (batch/'report.json').write_text(json.dumps(report))
        else:
            (batch/'report.json').unlink()
        return original(*args,**kwargs)
    monkeypatch.setattr(importer,'publish',replaced)
    with pytest.raises(ValueError):ex.publish('fresh',batch)
    assert not (lib.root/'.tutor/topicals/CURRENT').exists()
    assert ex.load('fresh')['stage']!='published'
    assert (lib.root/'Library/catalog.json').read_bytes()==catalog


def prior_numeric_release(ex,lib,tmp_path):
    """A valid nonempty CAIE legacy bank, independent of the new S3 group."""
    import topicals as importer
    from fixtures import GRAPH
    runtime=lib.root/'.tutor/packs/v1'
    target=runtime/'specs/9702/graph.json';target.parent.mkdir(parents=True)
    target.write_text(json.dumps(GRAPH))
    manifest=json.loads((runtime/'manifest.json').read_bytes());manifest['specs'].append('9702')
    (runtime/'manifest.json').write_text(json.dumps(manifest))
    legacy={'id':'preserved-legacy-numeric','kind':'numeric','stem':'Synthetic legacy numeric sentinel.',
        'answer':{'value':1,'unit':'m'},'marks':1,'difficulty':3,'kcs':['9702-2.1.1'],
        'source':{'type':'past','qid':'9702_s24_22_q99','part':'a'},
        'topical':{'reviewed':True,'revision':GRAPH['version'],'chapters':['9702-2.1'],
                   'requires':['9702-2.1'],'support':{}}}
    old=tmp_path/'prior-numeric';old.mkdir()
    (old/'bank.json').write_text(json.dumps({'format_version':1,'syllabus_versions':{'9702':GRAPH['version']},'items':[legacy]}))
    (old/'report.json').write_text(json.dumps({'preparation':{'expected_current':None}}))
    result=importer.publish(old,lib.root)
    prior=AssetLibrary(lib.root).read(result['release']+'/bank.json')
    additive=tmp_path/'additive-numeric';ex.prepare_publication('fresh',additive)
    return legacy,additive,result,prior


def test_fix_round1_prior_row_types_reject_mutation_and_preserve_real_activation(admitted,tmp_path,monkeypatch):
    from tutorlib.prepared_evidence import canonical_bytes
    ex,lib,_,_=admitted
    legacy,batch,old,old_raw=prior_numeric_release(ex,lib,tmp_path)
    bank=json.loads((batch/'bank.json').read_bytes());changed=copy.deepcopy(bank)
    changed['items'][0]['answer']['value']=1.0
    assert changed['items'][0]==legacy
    assert canonical_bytes(changed['items'][0])!=canonical_bytes(legacy)
    topicals.validate_bank(changed,packs.Packs(store.Vault(lib.root)),lib.root)
    pointer=lib.root/'.tutor/topicals/CURRENT';before=pointer.read_bytes()
    (batch/'bank.json').write_text(json.dumps(changed))
    with pytest.raises(ValueError):ex.publish('fresh',batch)
    assert pointer.read_bytes()==before and ex.load('fresh')['stage']!='published'
    (batch/'bank.json').write_text(json.dumps(bank))
    import topicals as importer
    original=importer.publish
    def dropped(*args,**kwargs):
        replacement={**bank,'items':bank['items'][1:]}
        topicals.validate_bank(replacement,packs.Packs(store.Vault(lib.root)),lib.root)
        (batch/'bank.json').write_text(json.dumps(replacement))
        return original(*args,**kwargs)
    with monkeypatch.context() as patch:
        patch.setattr(importer,'publish',dropped)
        with pytest.raises(ValueError):ex.publish('fresh',batch)
    assert pointer.read_bytes()==before and ex.load('fresh')['stage']!='published'
    (batch/'bank.json').write_text(json.dumps(bank))
    result=ex.publish('fresh',batch)
    loaded=json.loads(AssetLibrary(lib.root).read(result['release']+'/bank.json'))
    assert canonical_bytes(loaded['items'][0])==canonical_bytes(legacy)
    assert type(loaded['items'][0]['answer']['value']) is int
    assert len(loaded['items'])==4
    assert AssetLibrary(lib.root).read(old['release']+'/bank.json')==old_raw


def test_fix_round1_importer_consumes_the_digest_checked_bank_and_report_snapshot(tmp_path,monkeypatch):
    import hashlib
    import topicals as importer
    from test_topical_import import _publish_vault
    vault=_publish_vault(tmp_path);batch=tmp_path/'bound-batch';batch.mkdir()
    bank_raw=json.dumps({'format_version':1,'syllabus_versions':{'9702':'2025-2027'},'items':[]}).encode()
    report_raw=b'{"preparation":{"expected_current":null},"exact":"checked report bytes"}\n'
    (batch/'bank.json').write_bytes(bank_raw);(batch/'report.json').write_bytes(report_raw)
    original=topicals.validate_bank
    def checked(*args,**kwargs):
        original(*args,**kwargs)
        (batch/'bank.json').write_text('{"changed":"after consumed snapshot"}')
        (batch/'report.json').write_text('{"changed":"after consumed snapshot"}')
    monkeypatch.setattr(topicals,'validate_bank',checked)
    result=importer.publish(batch,vault,expected_bank_sha256=hashlib.sha256(bank_raw).hexdigest(),
                            expected_report_sha256=hashlib.sha256(report_raw).hexdigest())
    stored=AssetLibrary(vault)
    assert json.loads(stored.read(result['release']+'/bank.json'))==json.loads(bank_raw)
    assert stored.read(result['release']+'/report.json')==report_raw


def test_fix_round1_bound_importer_keeps_final_current_compare_and_swap(tmp_path,monkeypatch):
    import hashlib
    import topicals as importer
    from test_topical_import import _publish_vault
    vault=_publish_vault(tmp_path);batch=tmp_path/'cas-batch';batch.mkdir()
    bank_raw=json.dumps({'format_version':1,'syllabus_versions':{'9702':'2025-2027'},'items':[]}).encode()
    report_raw=b'{"preparation":{"expected_current":null}}'
    (batch/'bank.json').write_bytes(bank_raw);(batch/'report.json').write_bytes(report_raw)
    original=importer._activate_current
    def raced(base,version,expected):
        base.mkdir(parents=True,exist_ok=True)
        (base/'CURRENT').write_text('concurrent-release\n')
        return original(base,version,expected)
    monkeypatch.setattr(importer,'_activate_current',raced)
    with pytest.raises(ValueError,match='changed during preparation'):
        importer.publish(batch,vault,expected_bank_sha256=hashlib.sha256(bank_raw).hexdigest(),
                         expected_report_sha256=hashlib.sha256(report_raw).hexdigest())
    assert (vault/'.tutor/topicals/CURRENT').read_text()=='concurrent-release\n'


def test_fix_round1_checked_activation_preserves_prior_declared_aliases(admitted,tmp_path):
    """A supported old bank keeps its raw rows; runtime resolves declared aliases."""
    from tutorlib.asset_library import write_asset
    from tutorlib.prepared_evidence import canonical_bytes
    ex,lib,_,_=admitted
    legacy,_,_,_=prior_numeric_release(ex,lib,tmp_path)
    image='Library/Courses/9702/Questions/Media/legacy-numeric.png'
    alias='Assets/topicals/legacy-numeric.png'
    write_asset(lib.root,image,b'synthetic legacy image',aliases=[alias],
                metadata={'course':'9702','kind':'Questions/Media'})
    legacy['image']=alias
    prior={'format_version':1,'syllabus_versions':{'9702':'2025-2027'},'items':[legacy]}
    topicals.validate_bank(prior,packs.Packs(store.Vault(lib.root)),lib.root)
    old=lib.root/'.tutor/topicals/legacy-alias';old.mkdir()
    raw=json.dumps(prior).encode();(old/'bank.json').write_bytes(raw)
    (old.parent/'CURRENT').write_text('legacy-alias')
    batch=tmp_path/'preserve-alias';ex.prepare_publication('fresh',batch)
    result=ex.publish('fresh',batch)
    stored=json.loads(AssetLibrary(lib.root).read(result['release']+'/bank.json'))
    assert canonical_bytes(stored['items'][0])==canonical_bytes(legacy)
    assert (old/'bank.json').read_bytes()==raw
    loaded=packs.Packs(store.Vault(lib.root));assert not loaded.topical_errors
    assert next(i for i in loaded.topicals.items if i['id']==legacy['id'])['image']==image


def test_fix_round1_bound_importer_validates_the_exact_items_it_stores(admitted):
    import hashlib
    import topicals as importer
    from tutorlib.asset_library import write_asset
    _,lib,batch,bank=admitted
    original=bank['items'][0]['images'][0]
    alias='Assets/topicals/prepared-projection-alias.png'
    write_asset(lib.root,original,lib.read(original),aliases=[alias])
    bank['items'][0]['images'][0]=alias
    # The unbound normalizer can repair aliases, but a bound release stores the
    # checked values themselves and must validate that strict v1 projection.
    raw=json.dumps(bank).encode();(batch/'bank.json').write_bytes(raw)
    report=(batch/'report.json').read_bytes()
    with pytest.raises(ValueError):
        importer.publish(batch,lib.root,expected_bank_sha256=hashlib.sha256(raw).hexdigest(),
                         expected_report_sha256=hashlib.sha256(report).hexdigest())
    assert not (lib.root/'.tutor/topicals/CURRENT').exists()


def test_final_wave_public_selector_shares_one_fresh_authentication_per_request(admitted,monkeypatch):
    import random
    from tutorlib import model
    ex,lib,batch,bank=admitted;ex.publish('fresh',batch)
    runtime=packs.Packs(store.Vault(lib.root));runtime.items_for('S3-1.1')
    calls=[];validate=topicals.validate_bank
    def counted(*args,**kwargs):calls.append(1);return validate(*args,**kwargs)
    monkeypatch.setattr(topicals,'validate_bank',counted)
    def select():return runtime.select_item('S3-1.1',model.new_state(),.5,random.Random(1),exclude={'unrelated'})
    assert select() and len(calls)==1
    assert select() and len(calls)==2
    path=lib.root/bank['items'][0]['images'][0];raw=path.read_bytes();path.write_bytes(raw+b'changed')
    assert select() is None and runtime.topical_errors and len(calls)==3
    path.write_bytes(raw)
    assert select() and not runtime.topical_errors and len(calls)==4
    runtime.kcs['S3-1.1']['level']='AS'
    assert select() is None and runtime.topical_errors and len(calls)==5


def test_final_wave_pointer_change_during_selection_refuses_mixed_snapshot(admitted,monkeypatch):
    import random
    from tutorlib import model
    from tutorlib.asset_library import write_asset
    ex,lib,batch,bank=admitted;ex.publish('fresh',batch)
    runtime=packs.Packs(store.Vault(lib.root));runtime.items_for('S3-1.1')
    write_asset(lib.root,'Library/Shared/Topicals/Releases/v-other/bank.json',json.dumps(bank).encode(),
                metadata={'kind':'Topicals/Releases','version':'v-other'})
    original=runtime.aliases_for;changed=[]
    def raced(*args,**kwargs):
        if not changed:
            changed.append(True);(lib.root/'.tutor/topicals/CURRENT').write_text('v-other')
        return original(*args,**kwargs)
    monkeypatch.setattr(runtime,'aliases_for',raced)
    assert runtime.select_item('S3-1.1',model.new_state(),.5,random.Random(1),exclude={'unrelated'}) is None
    assert runtime.select_item('S3-1.1',model.new_state(),.5,random.Random(1),exclude={'unrelated'})
    assert runtime.topicals.pointer=='v-other' and not runtime.topical_errors


@pytest.mark.parametrize('excluded',['own-id','different-alias'])
def test_preservation_followup_actual_pool_keeps_disclosure_exclusions_on_rollover(tmp_path,monkeypatch,excluded):
    from test_topicals import bank_vault,item,publish,TARGET
    from tutorlib import model,topical_selection
    root=bank_vault(tmp_path)
    row=item(id='pool-item',kind='numeric',kcs=[TARGET+'.4'],answer={'value':4,'unit':'m s-2'},
             source={'type':'past','qid':'9702_s23_22_q2','part':'a'})
    publish(root,[row],version='one');publish(root,[row],version='two')
    pointer=root/'.tutor/topicals/CURRENT';pointer.write_text('one')
    runtime=packs.Packs(store.Vault(root))
    visible=topical_selection.pools(runtime,model.new_state(),[TARGET],['calculation'])[TARGET]
    assert len(visible)==1 and visible[0]['id']!='pool-item'
    disclosed={visible[0]['id']} if excluded=='own-id' else {'pool-item'}
    assert not topical_selection.pools(runtime,model.new_state(),[TARGET],['calculation'],disclosed=disclosed)[TARGET]
    original=runtime.aliases_for
    def rollover(*args,**kwargs):
        real_refresh=runtime.topicals.refresh;calls=[]
        def refreshed():
            calls.append(1)
            if len(calls)==2:pointer.write_text('two')
            return real_refresh()
        with monkeypatch.context() as patch:
            patch.setattr(runtime.topicals,'refresh',refreshed)
            return original(*args,**kwargs)
    monkeypatch.setattr(runtime,'aliases_for',rollover)
    assert not topical_selection.pools(runtime,model.new_state(),[TARGET],['calculation'],disclosed=disclosed)[TARGET]


def test_native_whole_attested_library_reload_exclusivity_and_private_manual_protocol(native_whole_prepared, monkeypatch, tmp_path):
    from library_assets import install_course
    from tutorlib import session
    import pymupdf
    ex, lib, _, _, _ = native_whole_prepared
    install_course(lib.root,'P1','P1-1')
    (lib.root/'.tutor/packs/CURRENT').write_text('v1')
    lifecycle.native_whole_complete(native_whole_prepared,monkeypatch)
    ex.register('fresh');batch=tmp_path/'whole-batch';ex.prepare_publication('fresh',batch)
    bank=json.loads((batch/'bank.json').read_text());ex.publish('fresh',batch)
    assert len(bank['items'])==1
    item=bank['items'][0]
    assert item['source']['assessment_mode']=='whole_official_rubric_v1'
    assert [r['page'] for r in item['source']['mark_scheme_regions']]==[14,15]
    def forbidden(*args,**kwargs): raise AssertionError('No runtime PDF or Work reads')
    monkeypatch.setattr(pymupdf,'open',forbidden)
    original_read=Path.read_bytes
    def library_only(path):
        if path.is_relative_to(ex.work_root()):forbidden()
        return original_read(path)
    monkeypatch.setattr(Path,'read_bytes',library_only)
    runtime=packs.Packs(store.Vault(lib.root));assert len(runtime.topicals.items)==1
    for extra_marker in (None,{'profile':'pearson_native_prepared_v1','attestation_ref':'Library/unrelated.json','attestation_sha256':'0'*64}):
        other=copy.deepcopy(item);other['id']='other-part';other['source']['part']='a'
        other['source'].pop('assessment_mode')
        if extra_marker is None:other['source'].pop('prepared_admission')
        else:other['source']['prepared_admission']=extra_marker
        for rows in ([item,other],[other,item]):
            with pytest.raises(ValueError,match='whole.question.*exclusive'):
                from tutorlib.prepared_evidence import validate_prepared_group
                validate_prepared_group(rows,AssetLibrary(lib.root),runtime)
    tutor=session.Tutor(store.Vault(lib.root))
    assert tutor.start('topical',focus=['P1-1'],topical_count=1,topical_types=['structured']).get('ok') is not False
    view=tutor.next()['items'][0];n=view['n'];private=item['scheme'][0]['whole_rubric']['media']
    assert len(private)==5 and not any(ref in json.dumps(view) for ref in private)
    assert tutor.whole_rubric(n,'  ').get('error')
    tutor.answer(f'{n}?');retry=tutor.retry_skipped();assert retry.get('items'),retry
    n=retry['items'][0]['n'];work='Synthetic disposable protocol attempt, not a mathematical answer.'
    count=len([e for e in tutor.vault.events() if e['type']=='answer'])
    rubric=tutor.whole_rubric(n,work);assert rubric.get('ticket') and rubric['media']==private
    assert len([e for e in tutor.vault.events() if e['type']=='answer'])==count
    result=tutor.answer(f'{n} = {work}',manual_awards={n:{'earned_marks':0,'ticket':rubric['ticket']}})
    assert result['results'][0].get('event'),result
    event=[e for e in tutor.vault.events() if e['type']=='answer'][-1]
    assert event['human_award']['max_marks']==6 and event['question']['scheme']==item['scheme']


@pytest.mark.parametrize("operation", ["plan", "missing"])
def test_session_planning_authenticates_bank_once_and_rechecks_next_plan(admitted, monkeypatch, operation):
    from datetime import datetime
    from tutorlib import model, policy
    ex, lib, batch, bank = admitted
    ex.publish('fresh', batch)
    runtime = packs.Packs(store.Vault(lib.root))
    # Several skill lookups in one real plan must share the admission proof.
    for key in ('S3-1.2', 'S3-1.3'):
        runtime.kcs[key] = {**runtime.kcs['S3-1.1'], 'id': key}
    focus = ['S3-1.1', 'S3-1.2', 'S3-1.3']
    runtime.plan = {'weeks': {'1': [{'kcs': focus}]}}
    calls = []
    validate = topicals.validate_bank
    def counted(*args, **kwargs):
        calls.append(1)
        return validate(*args, **kwargs)
    monkeypatch.setattr(topicals, 'validate_bank', counted)
    def plan():
        if operation == 'missing':
            return policy.missing_packs(runtime, datetime(2026, 11, 6))
        return policy.plan_session(model.new_state(), runtime, datetime(2026, 11, 6),
                                   50, mode='test', focus=focus)
    assert plan() == ([{'kind': 'sweep', 'kcs': ['S3-1.1']}] if operation == 'plan' else ['S3-1'])
    assert len(calls) == 1
    assert plan() and len(calls) == 2
    image = lib.root / bank['items'][0]['images'][0]
    raw = image.read_bytes()
    image.write_bytes(raw + b'changed')
    assert plan() == ([] if operation == 'plan' else ['S3-1']) and runtime.topical_errors and len(calls) == 3
    image.write_bytes(raw)
    assert plan() and len(calls) == 4


def test_home_readiness_checks_share_one_fresh_bank_load(admitted, monkeypatch):
    import asyncio
    from datetime import datetime
    from tutorlib import session
    from tutor_app import app as app_module
    from tutor_app.screens import HomeScreen
    ex, lib, batch, bank = admitted
    ex.publish('fresh', batch)
    (lib.root / '.tutor/config.json').write_text('{"tz":"Asia/Hong_Kong"}')
    tutor = session.Tutor(store.Vault(lib.root),
                          now=lambda: datetime.fromisoformat('2026-09-01T12:00:00+08:00'))
    for key in ('S3-1.2', 'S3-1.3'):
        tutor.packs.kcs[key] = {**tutor.packs.kcs['S3-1.1'], 'id': key}
    tutor.packs.plan = {'weeks': {'1': [{'id': 'sample', 'subject': 'maths', 'title': 'Sample',
        'kcs': ['S3-1.1', 'S3-1.2', 'S3-1.3']}]}}
    monkeypatch.setattr(app_module, 'Tutor', lambda *args, **kwargs: tutor)
    calls = []
    validate = topicals.validate_bank
    def counted(*args, **kwargs):
        calls.append(1)
        return validate(*args, **kwargs)
    monkeypatch.setattr(topicals, 'validate_bank', counted)
    app = app_module.TutorApp(lib.root, open_obsidian=False)
    app.settings.ai = False
    async def go():
        async with app.run_test(size=(140, 46)) as pilot:
            await pilot.pause()
            assert isinstance(app.screen, HomeScreen)
            calls.clear()
            app.screen.stats_text(datetime.fromisoformat('2026-09-01T12:00:00+08:00'), [])
            assert calls == []
            calls.clear()
            app.screen.refresh_home()
            await app.workers.wait_for_complete()  # a forced recheck reads the bank in the background
            await pilot.pause()
            assert len(calls) == 1
            assert app.screen._ready_kcs == frozenset({'S3-1.1'})
            image = lib.root / bank['items'][0]['images'][0]
            image.write_bytes(image.read_bytes() + b'changed')
            app.screen.refresh_home()
            await app.workers.wait_for_complete()
            await pilot.pause()
            assert len(calls) == 2 and tutor.packs.topical_errors
            assert not app.screen._ready_kcs
            await app.ai.close()
    asyncio.run(go())
