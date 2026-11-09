"""Prepared manager lifecycle sentinels use real sources in a disposable vault."""
import copy
import json
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
import pytest
from test_prepared_native_scope import inputs, question, module, QP, MS, whole_inputs
from test_extraction import extraction

@pytest.fixture
def prepared(inputs, monkeypatch, tmp_path):
    lib, request, path, out = inputs
    monkeypatch.setenv('STEM_TUTOR_VAULT', str(lib.root))
    monkeypatch.setenv('STEM_EXTRACT_ROOT', str(tmp_path / 'Work'))
    monkeypatch.delenv('STEM_LIBRARY_ROOT', raising=False)
    graph = tmp_path / 'specs/S3/graph.json'; graph.parent.mkdir(parents=True)
    graph.write_text(json.dumps({'course': 'S3', 'subtopics': [{'id':'S3-1', 'level':'A2'}],
        'kcs':[{'id':'S3-1.1','subtopic':'S3-1','level':'A2','prereqs':[]}]}))
    monkeypatch.setenv('STEM_LIBRARY_SPECS', str(graph.parent.parent))
    ex = extraction(); graph_sha = ex._course_graph_input('S3')[1]
    module().prepare_native(path, out, lib, graph_sha)
    return ex, lib, request, path, out

def create(prepared, name='fresh', **changes):
    ex, _, _, _, out = prepared
    options = dict(provider='codex', scope='questions', prepared_scope=out, codex_stop_remaining=20)
    options.update(changes)
    return ex.create(name, 'S3', **options)

def test_fresh_real_seed_no_maker_and_normal_plan(prepared):
    ex, lib, _, _, out = prepared
    state = create(prepared)
    assert state['jobs'] == {} and not Path(state['candidate']).exists()
    assert not (ex.job_dir('fresh')/'review.json').exists()
    assert state['prepared_scope']['package_sha256'] == ex.digest(out/'COMPLETE')
    assert state['selected_item_scope']['type'] == 'prepared_group'
    state = ex.plan('fresh')
    assert set(state['jobs']) == {'extract','review'}
    for role in ('extract','review'):
        contract=json.loads(ex._prompt(state,role).split('JOB CONTRACT:\n')[1])
        assert contract['prepared_scope'] == state['prepared_scope']
        assert contract['prepared_record_map']
        assert contract['bounded_read_plan'][MS]['render'][-1]['page'] == 7
    original = (out/'seed.json').read_bytes(); (out/'seed.json').write_text('{}')
    assert ex.resume('fresh')['prepared_scope'] == state['prepared_scope']
    (out/'seed.json').write_bytes(original)

def test_overlapping_names_and_batches_have_one_owner(prepared):
    ex, lib, req, path, out = prepared
    batch_request=copy.deepcopy(req); batch_request['questions'].append(question(2))
    path.write_text(json.dumps(batch_request)); batch=out.with_name('overlapping-batch')
    module().prepare_native(path,batch,lib,ex._course_graph_input('S3')[1])
    packages={'one':out,'two':batch}
    def attempt(name):
        try: create(prepared,name,prepared_scope=packages[name]); return 'created'
        except ValueError as exc: return str(exc)
    with ThreadPoolExecutor(2) as pool: results=list(pool.map(attempt,['one','two']))
    assert results.count('created') == 1
    assert any('owner' in result for result in results)
    owner = 'one' if (ex.job_dir('one')/'state.json').exists() else 'two'
    with pytest.raises(ValueError,match='resume'): create(prepared, owner,prepared_scope=packages[owner])

def test_disjoint_whole_question_can_proceed(prepared):
    ex, lib, req, path, out = prepared
    create(prepared)
    req['questions']=[question(2)]; path.write_text(json.dumps(req)); second=out.with_name('second')
    module().prepare_native(path,second,lib,ex._course_graph_input('S3')[1])
    state=create(prepared,'second',prepared_scope=second)
    assert state['selected_item_scope']['record_ids'] != ex.load('fresh')['selected_item_scope']['record_ids']

@pytest.mark.parametrize('change', [dict(sources=[QP]),dict(pages='1-5'),dict(official_qid='x'),dict(source_pages=['x'])])
def test_constructor_mixed_flags_refused(prepared,change):
    with pytest.raises(ValueError,match='prepared'): create(prepared,**change)


def candidate(state, descriptor):
    rows=[]
    for rid,item in state['selected_item_scope']['records'].items():
        media=item['question_media']+item['mark_scheme_media']
        names=media+item['reference_media']
        row={'id':rid, 'official_qid':item['official_qid'],'part':item['part'],
             'prepared_scope_sha256':state['prepared_scope']['package_sha256'],
             'kind':'structured','complete':True,'uncertainty':[],
             'stem':'Synthetic schema sentinel; no teaching approval.', 'answer':'Synthetic private answer.',
             'marks':1,'scheme':[{'point':'Synthetic private rubric point.'}],
             'syllabus':['S3-1'],'kcs':['S3-1.1'],'prerequisites':[],
             'regions':copy.deepcopy(item['regions']),'mark_scheme_regions':copy.deepcopy(item['mark_scheme_regions']),
             'media':media,'question_media':item['question_media'],'mark_scheme_media':item['mark_scheme_media'],
             'media_regions':{name:descriptor['media'][name]['region'] for name in names}}
        if item['reference_media']:
            row.update(reference_media=item['reference_media'],reference_regions=item['reference_regions'])
        rows.append(row)
    return {'prepared_scope':state['prepared_scope'],'selected_item_scope':state['selected_item_scope'],
            'questions':rows,'diagrams':[], 'source_coverage':[
                {'source_id':s['id'],'source_sha256':s['sha256'],'inspected_pages':s['selected_page_numbers'],
                 'no_relevant_content':s['prepared_role']=='inspection_only',
                 'reason':'Specification/occurrence identity inspection only.' if s['prepared_role']=='inspection_only' else ''}
                for s in state['sources']]}

def mock_workers(ex, monkeypatch, *, pending=False):
    import subprocess
    import capabilities
    monkeypatch.setattr(capabilities,'preflight',lambda:None)
    monkeypatch.setattr(ex,'worker_command',lambda *a,**k:['mock-worker'])
    class Launch:
        pid=None
        def __init__(self,*a,**k):
            launched=ex.load('fresh')['jobs'][a[0][-1]]
            assert launched.get('attempt_id') and launched.get('started')
            assert launched.get('finished') is None
    monkeypatch.setattr(ex.subprocess,'Popen',Launch)
    def execute(command,*,env,**kwargs):
        state=ex.load('fresh'); role=env['EXTRACT_ROLE']
        descriptor=ex._verify_prepared(state)
        if role=='extract':
            data=candidate(state,descriptor)
            if state.get('previous_candidate'):
                data['questions'][0]['stem']+=' Repaired synthetic textual sentinel.'
        else:
            data={'candidate_sha256':ex.digest(Path(state['candidate'])), 'verdict':'pending' if pending else 'pass',
                  'findings':['Source-backed textual repair required.'] if pending else [],
                  'inspected_images':[item['sha256'] for item in descriptor['media'].values()],
                  'prepared_scope':state['prepared_scope'],'seed_sha256':state['prepared_scope']['seed_sha256'],
                  'course_graph_sha256':state['focus_graph_sha256'],
                  'source_inventory_sha256':ex.hashlib.sha256(json.dumps(state['sources'],sort_keys=True).encode()).hexdigest()}
        Path(env['EXTRACT_OUTPUT']).write_text(json.dumps(data))
        return subprocess.CompletedProcess(command,0,'','')
    monkeypatch.setattr(ex.worker_timeout,'run_captured',execute)


def completed(prepared,monkeypatch,*,pending=False):
    ex=prepared[0]; create(prepared); ex.plan('fresh'); mock_workers(ex,monkeypatch,pending=pending)
    ex.run('fresh',weekly_remaining=49); ex._worker('fresh','extract')
    assert ex.load('fresh')['jobs']['extract']['ok'], ex.load('fresh').get('reliability_failures')
    ex.run('fresh',weekly_remaining=49); ex._worker('fresh','review')
    return ex


def test_real_manager_completion_receipts_and_blind_review(prepared,monkeypatch):
    ex=completed(prepared,monkeypatch)
    state=ex.check('fresh')
    assert state['stage']=='reviewed', state['problems']
    assert len(state['prepared_attempt_receipts'])==2
    assert state['jobs']['extract']['attempt_id'] != state['jobs']['review']['attempt_id']
    assert all(state['jobs'][role]['worker_started'] for role in ('extract','review'))
    prompt=json.loads((ex.job_dir('fresh')/'review.prompt.txt').read_text().split('JOB CONTRACT:\n')[1])
    assert 'previous_candidate' not in prompt and 'review_feedback' not in prompt
    assert ex.check('fresh')['stage']=='reviewed'

@pytest.mark.parametrize('fault',['review-bytes','bare-exit','missing-maker-receipt','same-attempt','candidate-bytes'])
def test_manually_placed_or_tampered_completion_fails(prepared,monkeypatch,fault):
    ex=completed(prepared,monkeypatch); state=ex.load('fresh')
    if fault=='review-bytes':
        p=ex.job_dir('fresh')/'review.json'; p.write_text(p.read_text()+' ')
    elif fault=='candidate-bytes':
        p=Path(state['candidate']); p.write_text(p.read_text()+' ')
    else:
        with ex.state_lock('fresh') as current:
            if fault=='bare-exit': current['jobs']['review']={'exit':0}
            if fault=='missing-maker-receipt': current['prepared_attempt_receipts']=current['prepared_attempt_receipts'][1:]
            if fault=='same-attempt': current['jobs']['review']['attempt_id']=current['jobs']['extract']['attempt_id']
    checked=ex.check('fresh'); assert checked['stage']=='pending'
    before=copy.deepcopy(checked.get('reliability_failures'))
    assert ex.check('fresh').get('reliability_failures')==before

@pytest.mark.parametrize('fault',['missing-state','missing-candidate','row-part','row-swap','crop-bytes','private-reference','region-rehash','candidate-ref','graph'])
def test_preflight_group_identity_and_frozen_crop_tamper(prepared,monkeypatch,fault):
    ex=prepared[0]; create(prepared); state=ex.plan('fresh'); mock_workers(ex,monkeypatch)
    ex.run('fresh',weekly_remaining=49); ex._worker('fresh','extract'); state=ex.load('fresh')
    path=Path(state['candidate']); data=json.loads(path.read_text())
    if fault=='missing-state':
        with ex.state_lock('fresh') as current:
            for key in ('prepared_scope','prepared_input'): current.pop(key)
            current['selected_item_scope'].pop('origin')
    elif fault=='candidate-ref':
        with ex.state_lock('fresh') as current: current['candidate']=str(path.with_name('swap.json'))
    elif fault=='graph':
        graph=Path(ex.os.environ['STEM_LIBRARY_SPECS'])/'S3/graph.json'; graph.write_text(graph.read_text()+' ')
    else:
        if fault=='missing-candidate': data.pop('prepared_scope')
        if fault=='row-part': data['questions'][0]['part']='b'
        if fault=='row-swap': data['questions'][0]['id']=data['questions'][1]['id']
        if fault=='crop-bytes': (path.parent/data['questions'][0]['question_media'][0]).write_bytes(b'changed')
        if fault=='private-reference':
            data['questions'][0]['reference_media']=data['questions'][1]['mark_scheme_media']
            data['questions'][0]['reference_regions']=data['questions'][1]['mark_scheme_regions']
        if fault=='region-rehash':
            data['questions'][0]['media_regions'][data['questions'][0]['question_media'][0]]['box']=[0,0,1,1]
        path.write_text(json.dumps(data))
    with pytest.raises(ValueError): ex.run('fresh',weekly_remaining=49)


def test_repair_once_preserves_feedback_then_requires_fresh_review(prepared,monkeypatch):
    ex=completed(prepared,monkeypatch,pending=True)
    assert ex.check('fresh')['stage']=='pending'
    old=ex.load('fresh'); candidate_sha=ex.digest(old['candidate'])
    review_sha=ex.digest(ex.job_dir('fresh')/'review.json')
    ex.run('fresh',weekly_remaining=49,retry='extract')
    state=ex.load('fresh')
    assert state['previous_candidate'] and ex.digest(state['previous_candidate'])==candidate_sha
    feedback=state['jobs']['extract']['review_feedback']
    assert feedback['review_sha256']==review_sha
    ex._worker('fresh','extract')
    assert ex.digest(ex.load('fresh')['candidate']) != candidate_sha
    assert ex.check('fresh')['stage']=='pending'
    mock_workers(ex,monkeypatch,pending=False)
    ex.run('fresh',weekly_remaining=49); ex._worker('fresh','review')
    assert ex.check('fresh')['stage']=='reviewed'

@pytest.mark.parametrize('remaining',[20,None,19])
def test_budget_floor_and_unknown_block(prepared,monkeypatch,remaining):
    ex=prepared[0]; create(prepared); ex.plan('fresh'); mock_workers(ex,monkeypatch)
    with pytest.raises(ValueError,match='20'): ex.run('fresh',weekly_remaining=remaining)
    assert not Path(ex.load('fresh')['candidate']).exists()


def test_two_failure_guard_is_not_reset_by_check_or_creation(prepared,monkeypatch):
    ex=prepared[0]; create(prepared); ex.plan('fresh'); mock_workers(ex,monkeypatch)
    with ex.state_lock('fresh') as state:
        state['reliability_failures']={'1':{'extract':[{'issues':['a']},{'issues':['b']}]}}
    with pytest.raises(ValueError,match='two|2 failures'): ex.run('fresh',weekly_remaining=49)
    with pytest.raises(ValueError,match='owner'): create(prepared,'evade')


@pytest.mark.parametrize('held_by_legacy',[False,True])
def test_optional_occurrence_freezes_original_bundle_and_pending_id(prepared,held_by_legacy):
    from test_prepared_native_scope import install_extra
    import topical_fastpath
    ex, lib, req, path, out=prepared
    copied,asset=install_extra((lib,req,path,out),'asset:asset-2974885b9b9ed953fc2e1d23')
    lib=copied[0]
    bundle_root=out.parent/'occurrence-bundle'
    bundle=topical_fastpath.prepare(lib.root,asset,'S3',bundle_root,dpi=72)
    original=bundle['questions'][1]
    req['questions'][0]['occurrence']={'bundle':str(bundle_root),
        'complete_sha256':ex.digest(bundle_root/'COMPLETE'),'id':original['id']}
    path.write_text(json.dumps(req)); revised=out.with_name('with-occurrence')
    module().prepare_native(path,revised,lib,ex._course_graph_input('S3')[1])
    if held_by_legacy:
        old=ex.job_dir('legacy-occurrence-owner'); old.mkdir(parents=True)
        (old/'state.json').write_text(json.dumps({'name':'legacy-occurrence-owner',
            'selected_item_scope':{'official_qid':'S3_pearson-edexcel-ial_WST03_2023-06_01_q2'},
            'required_source_occurrences':{'old-row':[{'original_occurrence_id':original['id']}]}}))
        with pytest.raises(ValueError,match='owner'): create(prepared,prepared_scope=revised)
        return
    state=create(prepared,prepared_scope=revised)
    (bundle_root/'bundle.json').write_text('{}')
    descriptor=ex._verify_prepared(state)
    pending=descriptor['questions'][0]['pending_occurrences'][0]
    assert pending['original_occurrence_id']==original['id']
    assert pending['source']['id']==asset and pending['status']=='pending_identity_join'
    assert pending['regions']==original['regions']
    assert asset in [s['id'] for s in state['sources']]


def test_external_graph_version_drift_invalidates_prepared_stage(prepared):
    ex,lib,req,path,out=prepared
    graph_path=Path(ex.os.environ['STEM_LIBRARY_SPECS'])/'S3/graph.json'
    graph=json.loads(graph_path.read_text()); graph['kcs'][0]['prereqs']=['S1-1.1']
    graph_path.write_text(json.dumps(graph))
    external=graph_path.parent.parent/'S1/graph.json'; external.parent.mkdir()
    external.write_text(json.dumps({'version':'v1','subtopics':[{'id':'S1-1'}],
        'kcs':[{'id':'S1-1.1','subtopic':'S1-1'}]}))
    revised=out.with_name('external'); module().prepare_native(path,revised,lib,ex._course_graph_input('S3')[1])
    state=create(prepared,prepared_scope=revised)
    data=json.loads(external.read_text()); data['version']='v2'; external.write_text(json.dumps(data))
    with pytest.raises(ValueError,match='external'): ex.plan('fresh')

@pytest.mark.parametrize('owner',['selected','held','anonymous','unknown','broad','queue'])
def test_live_exact_held_broad_or_queue_owner_blocks(prepared,owner):
    ex,lib,req,path,out=prepared
    old=ex.job_dir('owner'); old.mkdir(parents=True)
    state={'name':'owner','course':'S3','scope':'questions','jobs':{},
           'candidate':str(old/'maker.json'),'sources':[]}
    qid='S3_pearson-edexcel-ial_WST03_2023-06_01_q1'
    if owner in ('selected','held'):
        state['selected_item_scope']={'official_qid':qid}
        if owner=='held': state['reliability_failures']={'1':{'extract':[{},{}]}}
    if owner=='broad':
        state['sources']=[{'sha256':lib.record(QP)['sha256'],'selected_page_numbers':[2,3,4,5]}]
    if owner in ('anonymous','unknown'):
        Path(state['candidate']).write_text(json.dumps({'questions':[{'id':'original-anonymous',
            'official_qid':'unknown' if owner=='unknown' else None,
            'regions':[{'source_sha256':lib.record(QP)['sha256'],'page':2}]}]}))
    if owner=='queue':
        (old/'continuation-dispatch-state.json').write_text(json.dumps({'claims':[
            {'job':'owner','status':'blocked','selected_item_scope':{'official_qid':qid}}]}))
    (old/'state.json').write_text(json.dumps(state))
    with pytest.raises(ValueError,match='owner'): create(prepared)
    assert not (ex.job_dir('fresh')/'state.json').exists()


def test_unrelated_completed_broad_inspection_does_not_own_question(prepared):
    ex,lib,_,_,_=prepared
    old=ex.job_dir('old'); old.mkdir(parents=True); maker=old/'maker.json'
    maker.write_text(json.dumps({'questions':[{'official_qid':'S3_pearson-edexcel-ial_WST03_2023-06_01_q2',
        'regions':[{'source_sha256':lib.record(QP)['sha256'],'page':2}]}]}))
    (old/'state.json').write_text(json.dumps({'name':'old','scope':'questions','candidate':str(maker),
        'sources':[{'sha256':lib.record(QP)['sha256'],'selected_page_numbers':[2]}],
        'jobs':{'extract':{'exit':0,'ok':False,'finished':'retained-time','output_sha256':ex.digest(maker)}}}))
    assert create(prepared)['stage']=='inventoried'


def test_interrupted_setup_recovers_same_claim_without_new_owner(prepared,monkeypatch):
    ex=prepared[0]; real=ex._atomic_json
    def interrupt(path,data):
        if path.name=='state.json': raise OSError('interrupted before state commit')
        return real(path,data)
    monkeypatch.setattr(ex,'_atomic_json',interrupt)
    with pytest.raises(OSError,match='interrupted'): create(prepared)
    frozen=ex.job_dir('fresh')/'prepared-input/COMPLETE'; before=frozen.read_bytes()
    with pytest.raises(ValueError,match='owner'): create(prepared,'second')
    monkeypatch.setattr(ex,'_atomic_json',real)
    assert create(prepared)['stage']=='inventoried' and frozen.read_bytes()==before
    ledger=json.loads((ex.job_dir('fresh').parent/'prepared-claims.json').read_text())
    assert len(ledger['claims'])==1 and ledger['claims'][0]['status']=='claimed'

@pytest.mark.parametrize('operation',['focus','next_question','evidence_sources','reference_sources'])
def test_prepared_scope_cannot_use_legacy_mutators(prepared,operation):
    ex=prepared[0]; create(prepared)
    with pytest.raises(ValueError,match='prepared'):
        if operation in ('focus','next_question'): getattr(ex,operation)('fresh','x','reason')
        elif operation=='evidence_sources': ex.evidence_sources('fresh',['x'],'reason')
        else: ex.reference_sources('fresh',['x'],'purpose','reason')


def test_review_preflight_requires_real_completed_maker(prepared,monkeypatch):
    ex=prepared[0]; create(prepared); state=ex.plan('fresh'); mock_workers(ex,monkeypatch)
    descriptor=ex._verify_prepared(state)
    root=Path(state['candidate']).parent; root.mkdir(parents=True)
    for name in descriptor['media']:
        import shutil
        target=root/name; target.parent.mkdir(parents=True,exist_ok=True)
        shutil.copyfile(Path(state['prepared_input'])/name,target)
    Path(state['candidate']).write_text(json.dumps(candidate(state,descriptor)))
    with ex.state_lock('fresh') as current: current['jobs']['extract']['exit']=0
    with pytest.raises(ValueError,match='maker|extract|attempt'): ex.run('fresh',weekly_remaining=49)


def test_check_waiting_for_review_does_not_charge_successful_maker(prepared,monkeypatch):
    ex=prepared[0]; create(prepared); ex.plan('fresh'); mock_workers(ex,monkeypatch)
    ex.run('fresh',weekly_remaining=49); ex._worker('fresh','extract')
    assert ex.check('fresh')['stage']=='pending'
    assert not ex.load('fresh').get('reliability_failures',{}).get('1',{}).get('extract')


def test_hardlinked_candidate_leaf_refused(prepared,monkeypatch):
    ex=prepared[0]; create(prepared); state=ex.plan('fresh')
    path=Path(state['candidate']); path.parent.mkdir(parents=True); path.write_text('{}')
    ex.os.link(path,path.with_name('alias.json'))
    with pytest.raises(ValueError,match='alias'): ex.resume('fresh')


def test_cli_prepared_selector_and_exact_normalized_inventory(prepared,capsys):
    ex,_,_,_,out=prepared
    assert ex.main(['new','cli','--course','S3','--scope','questions','--provider','codex',
                    '--prepared-scope',str(out),'--codex-stop-remaining','20'])==0
    state=json.loads(capsys.readouterr().out)
    descriptor=json.loads((out/'descriptor.json').read_text())
    assert {(s['id'],p) for s in state['sources'] for p in s['selected_page_numbers']} == {
        (r['asset_id'],r['page']) for r in descriptor['required_asset_pages']}


def test_active_attested_match_is_reuse_decision_without_paid_plan(prepared,monkeypatch):
    ex=prepared[0]
    monkeypatch.setattr(ex,'_active_topical_bank',lambda vault:('v1','b'*64,{'items':[
        {'id':'existing-attested','source':{'profile':'pearson_native_prepared_v1',
         'official_qid':'S3_pearson-edexcel-ial_WST03_2023-06_01_q1'}}]}))
    state=create(prepared)
    assert state['reuse_decisions'][0]['item_id']=='existing-attested'
    with pytest.raises(ValueError,match='reuse'): ex.plan('fresh')
    assert ex.load('fresh')['jobs']=={}


def test_unbound_extra_candidate_raster_cannot_bypass_group_partition(prepared,monkeypatch):
    ex=prepared[0]; create(prepared); ex.plan('fresh'); mock_workers(ex,monkeypatch)
    ex.run('fresh',weekly_remaining=49); ex._worker('fresh','extract')
    state=ex.load('fresh'); root=Path(state['candidate']).parent
    import shutil
    source=root/next(iter(state['selected_item_scope']['records'].values()))['mark_scheme_media'][0]
    shutil.copyfile(source,root/'unbound-private.png')
    with pytest.raises(ValueError,match='raster|partition'): ex.run('fresh',weekly_remaining=49)


@pytest.mark.parametrize('inherited',['candidate','previous'])
def test_first_maker_cannot_adopt_manually_inherited_output(prepared,monkeypatch,inherited):
    ex=prepared[0]; create(prepared); state=ex.plan('fresh'); mock_workers(ex,monkeypatch)
    path=Path(state['candidate']); path.parent.mkdir(parents=True)
    if inherited=='candidate': path.write_text('{}')
    else:
        previous=path.with_name('candidate.json.unowned.previous'); previous.write_text('{}')
        with ex.state_lock('fresh') as current: current['previous_candidate']=str(previous)
    with pytest.raises(ValueError,match='inherited|previous|manager'): ex.run('fresh',weekly_remaining=49)


@pytest.mark.parametrize('retained',['current','focus','previous','completed','unknown-selected','tampered-focus'])
def test_gate_preserved_native_owner_cannot_be_released_by_other_scope(prepared,retained):
    ex,lib,_,_,out=prepared
    owner=ex.job_dir('preserved-owner'); owner.mkdir(parents=True)
    q1='S3_pearson-edexcel-ial_WST03_2023-06_01_q1'; q2=q1[:-1]+'2'
    sources=[{'id':QP,'sha256':lib.record(QP)['sha256'],'selected_page_numbers':[2]}]
    broad=owner/'broad-maker.json'; broad.write_text(json.dumps({'questions':[
        {'official_qid':q1,'part':'a','complete':True,
         'regions':[{'source_sha256':lib.record(QP)['sha256'],'page':2}]}]}))
    maker={'exit':0,'ok':False,'finished':'retained-finish','output_sha256':ex.digest(broad)}
    baseline={'name':'preserved-owner','course':'S3','scope':'questions','sources':sources,
        'candidate':str(broad),'jobs':{'extract':maker}}
    snapshot=owner/'before-focus-state.json'; snapshot.write_text(json.dumps(baseline))
    current=owner/'focused-q2.json'; current.write_text(json.dumps({'questions':[
        {'official_qid':q2,'part':'a','regions':[{'source_sha256':lib.record(QP)['sha256'],'page':2}]}]}))
    state={**baseline,'candidate':str(current),'selected_item_scope':{'official_qid':q2},
           'jobs':{'extract':{'exit':0,'finished':'focused-reuse','reused_candidate_sha256':ex.digest(broad)}}}
    entry={'candidate':str(broad),'candidate_sha256':ex.digest(broad),'sources':sources,
           'jobs':baseline['jobs'],'selected_item_scope':{'official_qid':q2},
           'state_snapshot':str(snapshot),'state_snapshot_sha256':ex.digest(snapshot)}
    if retained=='current': state['candidate']=str(broad)
    if retained in ('focus','tampered-focus'):
        state['focus_history']=[entry]; state['previous_candidate']=str(broad)
        if retained=='tampered-focus': broad.write_text(broad.read_text()+' ')
    if retained=='previous': state['previous_candidate']=str(broad)
    if retained=='completed':
        baseline.update(selected_item_scope={'official_qid':q1},candidate_sha256=ex.digest(broad))
        snapshot.write_text(json.dumps(baseline))
        state['completed_scope_history']=[{**entry,'selected_item_scope':{'official_qid':q1},
            'state_snapshot_sha256':ex.digest(snapshot)}]
    if retained=='unknown-selected':
        state['selected_item_scope']={'official_qid':'unknown'}; state['jobs']={}; current.unlink()
    (owner/'state.json').write_text(json.dumps(state))
    descriptor=json.loads((out/'descriptor.json').read_text())
    with pytest.raises(ValueError,match='preserved-owner'):
        ex._prepared_ownership(descriptor,owner.parent,'incoming')


@pytest.mark.parametrize('name,format_name',[('unbound-private.webp','WEBP'),
    ('unbound-private.payload','WEBP'),('unbound-private.json','PNG')])
def test_gate_every_extra_raster_format_and_mis_suffix_is_partitioned(prepared,monkeypatch,name,format_name):
    from PIL import Image
    ex=prepared[0]; create(prepared); ex.plan('fresh'); mock_workers(ex,monkeypatch)
    ex.run('fresh',weekly_remaining=49); ex._worker('fresh','extract')
    state=ex.load('fresh'); root=Path(state['candidate']).parent
    source=root/next(iter(state['selected_item_scope']['records'].values()))['mark_scheme_media'][0]
    with Image.open(source) as image: image.save(root/name,format=format_name)
    errors,_=ex._candidate_problems(state)
    assert any('raster' in error or 'partition' in error for error in errors), errors


@pytest.mark.parametrize('selected',['recognized-shared','unknown-disjoint'])
def test_gate_resolved_other_item_and_disjoint_scope_remain_available(prepared,selected):
    ex,lib,_,_,out=prepared
    owner=ex.job_dir('other-owner'); owner.mkdir(parents=True)
    q2='S3_pearson-edexcel-ial_WST03_2023-06_01_q2'
    pages=[2] if selected=='recognized-shared' else [6]
    sources=[{'id':QP,'sha256':lib.record(QP)['sha256'],'selected_page_numbers':pages}]
    maker=owner/'other-maker.json'; maker.write_text(json.dumps({'questions':[
        {'official_qid':q2,'regions':[{'source_sha256':lib.record(QP)['sha256'],'page':pages[0]}]}]}))
    baseline={'name':'other-owner','course':'S3','scope':'questions','candidate':str(maker),'sources':sources,
        'jobs':{'extract':{'exit':0,'ok':False,'output_sha256':ex.digest(maker)}}}
    snapshot=owner/'before-focus.json'; snapshot.write_text(json.dumps(baseline))
    state={**baseline,'selected_item_scope':{'official_qid':q2 if selected=='recognized-shared' else 'unknown'}}
    if selected=='recognized-shared':
        state.update(previous_candidate=str(maker),focus_history=[{'candidate':str(maker),
            'candidate_sha256':ex.digest(maker),'sources':sources,'jobs':baseline['jobs'],
            'selected_item_scope':state['selected_item_scope'],'state_snapshot':str(snapshot),
            'state_snapshot_sha256':ex.digest(snapshot)}])
    (owner/'state.json').write_text(json.dumps(state))
    ex._prepared_ownership(json.loads((out/'descriptor.json').read_text()),owner.parent,'incoming')


def test_gate_real_prepared_repair_then_disjoint_question_requires_predecessor_receipt(prepared,monkeypatch):
    ex=completed(prepared,monkeypatch,pending=True)
    ex.run('fresh',weekly_remaining=49,retry='extract'); ex._worker('fresh','extract')
    mock_workers(ex,monkeypatch,pending=False)
    ex.run('fresh',weekly_remaining=49); ex._worker('fresh','review')
    state=ex.check('fresh'); assert state['stage']=='reviewed',state['problems']
    previous=Path(state['previous_candidate']); previous_sha=ex.digest(previous)
    assert previous_sha != ex.digest(state['candidate'])
    original_receipts=copy.deepcopy(state['prepared_attempt_receipts'])
    previous_receipt=next(r for r in original_receipts
        if r['role']=='extract' and r['output_sha256']==previous_sha)
    assert previous_receipt['worker_started'] and previous_receipt['finished']
    _,lib,request,path,out=prepared
    request['questions']=[question(2)]; path.write_text(json.dumps(request)); second=out.with_name('after-repair-q2')
    module().prepare_native(path,second,lib,ex._course_graph_input('S3')[1])
    with ex.state_lock('fresh') as current:
        current['prepared_attempt_receipts']=[r for r in original_receipts
            if r['attempt_id']!=previous_receipt['attempt_id']]
    with pytest.raises(ValueError,match='previous.*binding|previous.*receipt'):
        create(prepared,'missing-receipt',prepared_scope=second)
    with ex.state_lock('fresh') as current:
        current['prepared_attempt_receipts']=copy.deepcopy(original_receipts)
        old=next(r for r in current['prepared_attempt_receipts'] if r['attempt_id']==previous_receipt['attempt_id'])
        old['prepared_scope']['seed_sha256']='0'*64
    with pytest.raises(ValueError,match='previous.*binding|previous.*receipt'):
        create(prepared,'tampered-receipt',prepared_scope=second)
    with ex.state_lock('fresh') as current: current['prepared_attempt_receipts']=original_receipts
    next_state=create(prepared,'after-repair',prepared_scope=second)
    assert next_state['stage']=='inventoried' and next_state['jobs']=={}
    assert next_state['selected_item_scope']['official_qids']==[
        'S3_pearson-edexcel-ial_WST03_2023-06_01_q2']
    assert ex.load('fresh')['reliability_failures']==state['reliability_failures']
    assert ex.digest(previous)==previous_sha


def test_gate_failed_real_prepared_predecessor_does_not_block_disjoint_or_reset_guard(prepared,monkeypatch):
    ex,lib,request,path,out=prepared
    create(prepared); ex.plan('fresh'); mock_workers(ex,monkeypatch)
    real_execute=ex.worker_timeout.run_captured
    def incomplete(command,*,env,**kwargs):
        result=real_execute(command,env=env,**kwargs)
        if env['EXTRACT_ROLE']=='extract':
            output=Path(env['EXTRACT_OUTPUT']); data=json.loads(output.read_text())
            data['questions'][0].update(complete=False,uncertainty=['Synthetic unresolved text sentinel.'])
            output.write_text(json.dumps(data))
        return result
    monkeypatch.setattr(ex.worker_timeout,'run_captured',incomplete)
    ex.run('fresh',weekly_remaining=49); ex._worker('fresh','extract')
    first=ex.load('fresh'); assert first['jobs']['extract']['exit']==0
    assert first['jobs']['extract']['ok'] is False
    failures=copy.deepcopy(first['reliability_failures'])
    mock_workers(ex,monkeypatch)
    ex.run('fresh',weekly_remaining=49,retry='extract'); ex._worker('fresh','extract')
    ex.run('fresh',weekly_remaining=49); ex._worker('fresh','review')
    state=ex.check('fresh'); assert state['stage']=='reviewed',state['problems']
    previous_sha=ex.digest(state['previous_candidate'])
    receipt=next(r for r in state['prepared_attempt_receipts']
        if r['role']=='extract' and r['output_sha256']==previous_sha)
    assert receipt['ok'] is False and receipt['worker_started'] and receipt['finished']
    request['questions']=[question(2)]; path.write_text(json.dumps(request)); second=out.with_name('failed-then-q2')
    module().prepare_native(path,second,lib,ex._course_graph_input('S3')[1])
    assert create(prepared,'after-failed-repair',prepared_scope=second)['stage']=='inventoried'
    assert ex.load('fresh')['reliability_failures']==failures
    with pytest.raises(ValueError,match='owner'): create(prepared,'same-question-bypass')


@pytest.mark.parametrize('role',['public','private'])
@pytest.mark.parametrize('existing',[False,True])
def test_final_wave_seed_directory_alias_refused_before_any_copy_or_attempt(prepared,monkeypatch,tmp_path,role,existing):
    ex=prepared[0];create(prepared);state=ex.plan('fresh');mock_workers(ex,monkeypatch)
    root=Path(state['candidate']).parent;root.mkdir(parents=True,exist_ok=True)
    outside=tmp_path/'unrelated';outside.mkdir()
    descriptor=ex._verify_prepared(state)
    if existing:
        name=next(n for n in descriptor['media'] if n.startswith(role+'/'))
        (outside/Path(name).name).write_bytes((Path(state['prepared_input'])/name).read_bytes())
    before={p.name:p.read_bytes() for p in outside.iterdir()}
    (root/role).symlink_to(outside,target_is_directory=True)
    before_root=sorted(p.relative_to(root).as_posix() for p in root.rglob('*'))
    with pytest.raises(ValueError):ex.run('fresh',weekly_remaining=49)
    assert {p.name:p.read_bytes() for p in outside.iterdir()}==before
    assert sorted(p.relative_to(root).as_posix() for p in root.rglob('*'))==before_root
    current=ex.load('fresh')
    assert not current['jobs']['extract'].get('attempt_id')
    assert not current.get('prepared_attempt_receipts')


def test_final_wave_seed_missing_leaf_uses_exclusive_no_follow_creation(prepared,monkeypatch,tmp_path):
    ex=prepared[0];create(prepared);state=ex.plan('fresh');mock_workers(ex,monkeypatch)
    root=Path(state['candidate']).parent;root.mkdir(parents=True,exist_ok=True)
    victim=tmp_path/'outside.png';victim.write_bytes(b'preserved outside bytes')
    original=ex.os.open;injected=[]
    def raced(path,flags,*args,**kwargs):
        if not injected and kwargs.get('dir_fd') is not None and flags & ex.os.O_CREAT and str(path).endswith('.png'):
            name=next(n for n in ex._verify_prepared(ex.load('fresh'))['media'] if Path(n).name==str(path))
            (root/name).symlink_to(victim);injected.append(name)
        return original(path,flags,*args,**kwargs)
    monkeypatch.setattr(ex.os,'open',raced)
    with pytest.raises(ValueError):ex.run('fresh',weekly_remaining=49)
    assert injected and victim.read_bytes()==b'preserved outside bytes'
    assert not ex.load('fresh')['jobs']['extract'].get('attempt_id')


@pytest.mark.parametrize('substituted',[False,True])
def test_final_wave_actual_timeout_output_binds_failed_attempt_and_allows_one_repair(prepared,monkeypatch,substituted):
    import subprocess
    ex=prepared[0];create(prepared);ex.plan('fresh');mock_workers(ex,monkeypatch)
    execute=ex.worker_timeout.run_captured;calls=[]
    def timed(command,*,env,**kwargs):
        result=execute(command,env=env,**kwargs)
        if env['EXTRACT_ROLE']=='extract' and not calls:
            calls.append('timeout')
            raise subprocess.TimeoutExpired(command,1800,output='partial provider output')
        return result
    monkeypatch.setattr(ex.worker_timeout,'run_captured',timed)
    ex.run('fresh',weekly_remaining=49);ex._worker('fresh','extract')
    first=ex.load('fresh');raw=Path(first['candidate']).read_bytes();first_sha=ex.digest(first['candidate'])
    failures=copy.deepcopy(first['reliability_failures'])
    assert first['jobs']['extract']['ok'] is False and first['jobs']['extract']['exit']!=0
    if substituted:
        Path(first['candidate']).write_bytes(raw+b'\nsubstituted')
        with pytest.raises(ValueError):ex.run('fresh',weekly_remaining=49,retry='extract')
        held=ex.load('fresh')
        assert held['jobs']['extract']['attempt_id']==first['jobs']['extract']['attempt_id']
        assert held['reliability_failures']==failures
        return
    ex.run('fresh',weekly_remaining=49,retry='extract');ex._worker('fresh','extract')
    repaired=ex.load('fresh')
    assert repaired['jobs']['extract']['ok'] is True,repaired.get('problems')
    ex.run('fresh',weekly_remaining=49);ex._worker('fresh','review')
    current=ex.check('fresh');assert current['stage']=='reviewed',current['problems']
    receipt=next(r for r in current['prepared_attempt_receipts'] if r['attempt_id']==first['jobs']['extract']['attempt_id'])
    assert receipt['output_sha256']==receipt['candidate_sha256']==first_sha
    assert receipt['ok'] is False and receipt['exit']!=0
    assert current['reliability_failures']==failures
    assert Path(current['previous_candidate']).read_bytes()==raw


def test_preservation_followup_current_timeout_output_cannot_use_an_older_authentic_receipt(prepared,monkeypatch):
    import subprocess
    ex=prepared[0];create(prepared);ex.plan('fresh');mock_workers(ex,monkeypatch)
    ex.run('fresh',weekly_remaining=49);ex._worker('fresh','extract')
    a=ex.load('fresh');a_raw=Path(a['candidate']).read_bytes();a_sha=ex.digest(a['candidate'])
    execute=ex.worker_timeout.run_captured
    def timeout(command,*,env,**kwargs):
        execute(command,env=env,**kwargs)
        raise subprocess.TimeoutExpired(command,1800)
    monkeypatch.setattr(ex.worker_timeout,'run_captured',timeout)
    ex.run('fresh',weekly_remaining=49,retry='extract');ex._worker('fresh','extract')
    b=ex.load('fresh');b_raw=Path(b['candidate']).read_bytes();b_sha=ex.digest(b['candidate'])
    assert a_sha!=b_sha and b['jobs']['extract']['output_sha256']==b_sha
    assert any(r['output_sha256']==a_sha for r in b['prepared_attempt_receipts'])
    failures=copy.deepcopy(b['reliability_failures'])
    root=Path(b['candidate']).parent;before={p.relative_to(root).as_posix() for p in root.rglob('*')}
    Path(b['candidate']).write_bytes(a_raw)
    with pytest.raises(ValueError):ex.run('fresh',weekly_remaining=49,retry='extract')
    held=ex.load('fresh')
    assert held['jobs']['extract']['attempt_id']==b['jobs']['extract']['attempt_id']
    assert held['previous_candidate']==b['previous_candidate']
    assert held['reliability_failures']==failures
    assert {p.relative_to(root).as_posix() for p in root.rglob('*')}==before
    assert Path(b['candidate']).read_bytes()==a_raw
    Path(b['candidate']).write_bytes(b_raw);mock_workers(ex,monkeypatch)
    ex.run('fresh',weekly_remaining=49,retry='extract');ex._worker('fresh','extract')
    ex.run('fresh',weekly_remaining=49);ex._worker('fresh','review')
    current=ex.check('fresh');assert current['stage']=='reviewed',current['problems']
    assert current['reliability_failures']==failures
    assert Path(current['previous_candidate']).read_bytes()==b_raw


@pytest.fixture
def native_whole_prepared(whole_inputs, monkeypatch, tmp_path):
    from library_assets import read_bytes
    lib, request, path, out = whole_inputs
    monkeypatch.setenv('STEM_TUTOR_VAULT', str(lib.root))
    monkeypatch.setenv('STEM_EXTRACT_ROOT', str(tmp_path/'Work'))
    monkeypatch.delenv('STEM_LIBRARY_ROOT', raising=False)
    graph = tmp_path/'specs/P1/graph.json'; graph.parent.mkdir(parents=True)
    graph.write_bytes(read_bytes('build/out/specs/P1/graph.json'))
    monkeypatch.setenv('STEM_LIBRARY_SPECS', str(graph.parent.parent))
    ex = extraction()
    path.write_text(json.dumps(request))
    module().prepare_native(path, out, lib, ex._course_graph_input('P1')[1])
    original = candidate
    def whole_candidate(state, descriptor):
        data = original(state, descriptor)
        for row in data['questions']:
            item = state['selected_item_scope']['records'][row['id']]
            row.update(assessment_mode=item['assessment_mode'], whole_assessment=copy.deepcopy(item['whole_assessment']),
                private_guidance_regions=copy.deepcopy(item['private_guidance_regions']), marks=6,
                syllabus=['P1-1'], kcs=['P1-1.1'],
                scheme=[{'point':'Synthetic schema sentinel; inspect all official guidance/core raster pages.',
                    'whole_rubric':{'version':1,'max_marks':6,'media':item['mark_scheme_media']}}])
        return data
    monkeypatch.setattr(__import__('sys').modules[__name__], 'candidate', whole_candidate)
    return ex, lib, request, path, out


def native_whole_complete(prepared, monkeypatch):
    ex = prepared[0]
    ex.create('fresh','P1',provider='codex',scope='questions',prepared_scope=prepared[4],codex_stop_remaining=20)
    ex.plan('fresh');mock_workers(ex,monkeypatch)
    ex.run('fresh',weekly_remaining=49);ex._worker('fresh','extract')
    assert ex.load('fresh')['jobs']['extract']['ok'],ex.load('fresh').get('reliability_failures')
    ex.run('fresh',weekly_remaining=49);ex._worker('fresh','review')
    state = ex.check('fresh');assert state['stage']=='reviewed',state['problems']
    return ex


def test_native_whole_actual_receipts_and_shared_candidate_guards(native_whole_prepared, monkeypatch):
    ex = native_whole_complete(native_whole_prepared, monkeypatch)
    state = ex.load('fresh'); descriptor = ex._verify_prepared(state)
    data = json.loads(Path(state['candidate']).read_text())
    assert len(state['prepared_attempt_receipts']) == 2
    assert len({r['attempt_id'] for r in state['prepared_attempt_receipts']}) == 2
    assert all(r['worker_started'] and r['ok'] for r in state['prepared_attempt_receipts'])
    assert data['questions'][0]['marks'] == 6
    for fault in ('mode','marks','whole-max','flat','partial-private','reordered-private','guidance-missing','guidance-leak','generic-answer'):
        bad=copy.deepcopy(data);row=bad['questions'][0]
        if fault=='mode': row.pop('assessment_mode')
        elif fault=='marks': row['marks']=2
        elif fault=='whole-max': row['scheme'][0]['whole_rubric']['max_marks']=2
        elif fault=='flat': row['scheme']=[{'point':'Synthetic flat point'}]*6
        elif fault=='partial-private': row['scheme'][0]['whole_rubric']['media'].pop()
        elif fault=='reordered-private': row['scheme'][0]['whole_rubric']['media'].reverse()
        elif fault=='guidance-missing': row.pop('private_guidance_regions')
        elif fault=='guidance-leak': row['question_media'].append(row['mark_scheme_media'][0])
        else: row['answer']='Consult the official mark scheme.'
        assert module().prepared_candidate_problems(state,bad,descriptor,Path(state['candidate']).parent),fault
    assert ex.check('fresh')['stage']=='reviewed'
