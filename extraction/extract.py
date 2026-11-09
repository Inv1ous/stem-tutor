#!/usr/bin/env python3
"""Resumable PDF extraction, with per-job providers and explicit review/publication."""
from __future__ import annotations

import argparse
from contextlib import contextmanager
import fcntl
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import shlex
import stat
import subprocess
import sys
import uuid

REPO = Path(__file__).resolve().parents[1]
for directory in ('build', 'src', 'foundry'):
    sys.path.insert(0, str(REPO / directory))
import library
import router
from tutorlib.ial_p1_identity import p1_pilot, p1_question
from tutorlib.ial_identity import ial_namespace, ial_assessed, ial_question, validate_ial_sources
from tutor_workers.lifecycle import process_alive, timestamp, transition
from tutor_workers import candidates, reliability, source_ocr, timeout as worker_timeout


_FRESH_ONLY_P1_Q4 = 'P1_pearson-edexcel-ial_WMA11_2019-01_01_q4'

def work_root():
    return Path(os.environ.get('STEM_EXTRACT_ROOT') or REPO.parent / 'Work')


def ocr_cache_root():
    return work_root() / 'Workers/extraction/ocr-cache'


def job_dir(name):
    if not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_-]*', name):
        raise ValueError('job name needs letters, numbers, _ or -')
    return work_root() / 'Workers/extraction' / name


def load(name):
    return json.loads((job_dir(name) / 'state.json').read_text())


@contextmanager
def state_lock(name):
    directory = job_dir(name)
    directory.mkdir(parents=True, exist_ok=True)
    with (directory / '.lock').open('a') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        path = directory / 'state.json'
        state = json.loads(path.read_text()) if path.exists() else {}
        yield state
        temp = directory / (uuid.uuid4().hex + '.tmp')
        temp.write_text(json.dumps(state, ensure_ascii=False, indent=2) + '\n')
        temp.replace(path)


def candidate_path(state):
    return Path(state['candidate'])


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def _codex_stop_remaining(value):
    if type(value) not in (int, float) or not 1 <= value < 100:
        raise ValueError('Codex stop remaining must be a percentage from 1 up to 100 (exclusive)')
    return float(value)


def create(name, course, provider='claude', scope='both', sources=None, pages=None,
           codex_model=None, codex_effort=None, codex_stop_remaining=None, *,
           official_qid=None, source_pages=None, prepared_scope=None):
    if provider not in ('claude', 'codex', 'both') or scope not in ('questions', 'diagrams', 'both'):
        raise ValueError('unknown provider or scope')
    if not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_-]*', course):
        raise ValueError('invalid course')
    if codex_stop_remaining is not None:
        codex_stop_remaining = _codex_stop_remaining(codex_stop_remaining)
    if prepared_scope is not None:
        if sources or pages is not None or official_qid is not None or source_pages is not None:
            raise ValueError("prepared scope cannot combine with legacy/fresh source selectors")
        return _create_prepared(name, course, provider, scope, prepared_scope, codex_model, codex_effort, codex_stop_remaining)
    fresh = official_qid is not None or source_pages is not None
    if fresh and (official_qid is None or source_pages is None or sources or pages is not None):
        raise ValueError('fresh P1 requires paired official_qid/source_pages without legacy source/pages selectors')
    with state_lock(name) as state:
        if state:
            raise ValueError('job exists: use resume, inventory, plan, run or check')
        material = None
        if fresh:
            output = work_root() / 'Candidates/extraction' / name
            if (output.exists() or output.is_symlink()
                    or any(path.name != '.lock' for path in job_dir(name).iterdir())):
                raise ValueError('fresh P1 target already exists; never adopt prior outputs')
            material = _fresh_native_material(course, scope, official_qid, source_pages)
            material['initial_native_question']['job_name'] = name
        state.update(name=name, course=course, provider=provider, scope=scope, stage='new',
                     created=timestamp(), history=[], jobs={}, sources=[], teaching_approved=False,
                     requested_sources=list(sources or []), requested_pages=pages,
                     candidate=str(work_root() / 'Candidates/extraction' / name / 'candidate.json'))
        if material is not None:
            state.update(material, stage='inventoried')
        if codex_model:
            state['codex_model'] = codex_model
        if codex_effort:
            state['codex_effort'] = codex_effort
        if codex_stop_remaining is not None:
            state['codex_stop_remaining'] = codex_stop_remaining
    return load(name)


_FRESH_NATIVE_P1_ORIGIN = 'fresh_native_p1_v1'
_FRESH_NATIVE_IAL_ORIGIN = 'fresh_native_ial_v1'


def _prepared_mode(state):
    scope=state.get('selected_item_scope')
    return ('prepared_scope' in state or 'prepared_input' in state
            or isinstance(scope,dict) and scope.get('origin') == 'pearson_native_prepared_v1')


def _owned_output_bytes(directory, name):
    """Read one physical, unshared file through an already owned directory FD."""
    descriptor = os.open(name, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=directory)
    try:
        info = os.fstat(descriptor)
        if not stat.S_ISREG(info.st_mode) or info.st_nlink != 1:
            raise ValueError('prepared output must be a private regular file')
        chunks = []
        while chunk := os.read(descriptor, 1024 * 1024):
            chunks.append(chunk)
        return b''.join(chunks)
    finally:
        os.close(descriptor)


def _prepared_output_digest(state, path):
    root = candidate_path(state).parent
    if path.parent != root:
        raise ValueError('prepared output is outside its managed directory')
    directory = os.open(root, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    try:
        try:
            return hashlib.sha256(_owned_output_bytes(directory, path.name)).hexdigest()
        except FileNotFoundError:
            return None
    finally:
        os.close(directory)


def _seed_prepared_media(state, descriptor):
    """Preflight every role/leaf before copying; create missing leaves without following aliases."""
    root = candidate_path(state).parent
    root.mkdir(parents=True, exist_ok=True)
    directories = {}
    root_fd = os.open(root, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    try:
        # Both role directories are checked before creating either role or any PNG.
        for role in ('public', 'private'):
            try:
                info = os.stat(role, dir_fd=root_fd, follow_symlinks=False)
            except FileNotFoundError:
                continue
            if not stat.S_ISDIR(info.st_mode):
                raise ValueError('prepared seed role directory must be physical: ' + role)
            directories[role] = os.open(role, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=root_fd)
        missing, content = [], {}
        for name, pin in descriptor['media'].items():
            role, leaf = name.split('/')
            raw = candidates.verified_bytes(Path(state['prepared_input']) / name)
            if hashlib.sha256(raw).hexdigest() != pin['sha256']:
                raise ValueError('prepared frozen seed changed before copy')
            content[name] = raw
            try:
                current = _owned_output_bytes(directories[role], leaf) if role in directories else None
            except FileNotFoundError:
                current = None
            if current is None:
                missing.append(name)
            elif hashlib.sha256(current).hexdigest() != pin['sha256']:
                raise ValueError('prepared seed media changed before launch')
        for role in ('public', 'private'):
            if role not in directories:
                os.mkdir(role, mode=0o700, dir_fd=root_fd)
                directories[role] = os.open(role, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=root_fd)
        for name in missing:
            role, leaf = name.split('/')
            current = os.stat(role, dir_fd=root_fd, follow_symlinks=False)
            owned = os.fstat(directories[role])
            if not stat.S_ISDIR(current.st_mode) or (current.st_dev, current.st_ino) != (owned.st_dev, owned.st_ino):
                raise ValueError('prepared seed role directory changed during copy')
            target = os.open(leaf, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW,
                             0o600, dir_fd=directories[role])
            try:
                raw = memoryview(content[name])
                while raw:
                    written = os.write(target, raw)
                    if not written:
                        raise OSError('prepared seed write made no progress')
                    raw = raw[written:]
            finally:
                os.close(target)
    except OSError as exc:
        raise ValueError('prepared seed/output alias or exclusive-write failure: ' + str(exc)) from exc
    finally:
        for directory in directories.values():
            os.close(directory)
        os.close(root_fd)


def _verify_prepared(state):
    from prepared_scope import verify_prepared_state, retained_output_hashes
    from tutorlib.asset_library import AssetLibrary
    config = state.get('prepared_scope', {})
    _verify_initial_output(state, config)
    prior_attempts=[r for r in state.get('prepared_attempt_receipts',[])
                    if r.get('role')=='extract' and r.get('worker_started') and r.get('finished')
                    and r.get('prepared_scope')==config]
    if state.get('previous_candidate'):
        previous=Path(state['previous_candidate'])
        if (not prior_attempts or previous.parent!=candidate_path(state).parent
                or re.fullmatch(r'candidate\.json\.[0-9a-f]{32}\.previous',previous.name) is None
                or previous.is_symlink() or not previous.is_file() or previous.stat().st_nlink!=1):
            raise ValueError('prepared previous candidate requires an owned real manager attempt')
        if _prepared_output_digest(state, previous) not in retained_output_hashes(state):
            raise ValueError('prepared previous candidate receipt/output binding changed')
    if state.get('prepared_input') != str(job_dir(state['name']) / 'prepared-input'):
        raise ValueError('prepared input must retain its managed private path')
    for course,pin in state.get('prepared_external_graphs',{}).items():
        graph,sha=_course_graph_input(course)
        if sha!=pin['sha256'] or graph.get('version')!=pin['version']:
            raise ValueError('prepared external graph version/bytes changed: '+course)
    return verify_prepared_state(state, AssetLibrary(library.learner_vault()),
                                 _course_graph_input(state['course'])[1])


@contextmanager
def _prepared_claim_lock():
    root = work_root() / 'Workers/extraction'
    root.mkdir(parents=True, exist_ok=True)
    with (root / '.prepared-claims.lock').open('a') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        yield root


def _atomic_json(path, data):
    temporary = path.with_name(path.name + '.' + uuid.uuid4().hex + '.tmp')
    temporary.write_text(json.dumps(data, ensure_ascii=False, indent=2) + '\n')
    temporary.replace(path)


def _prepared_ownership(descriptor, root, name):
    """Live scopes/claims and completed maker rows own items; inspection alone does not."""
    qids = {q['official_qid'] for q in descriptor['questions']}
    regions = [r for q in descriptor['questions'] for r in q['question_regions']]
    occurrences = {o['original_occurrence_id'] for q in descriptor['questions'] for o in q.get('pending_occurrences', [])}
    def occurrence_overlap(value):
        if isinstance(value,dict):
            if any(value.get(key) in occurrences for key in ('id','item_id','original_occurrence_id')
                   if isinstance(value.get(key),str)): return True
            return any(occurrence_overlap(child) for child in value.values())
        return isinstance(value,list) and any(occurrence_overlap(child) for child in value)
    def overlaps(row):
        if not isinstance(row, dict): return False
        if occurrence_overlap(row): return True
        source = row.get('source', {}) if isinstance(row.get('source'), dict) else {}
        qid = row.get('official_qid', source.get('official_qid', source.get('qid')))
        if qid in qids: return True
        # Only a recognized other whole question on this original pair resolves
        # shared-page inspection. An arbitrary/unknown label cannot release it.
        prefix=next(iter(qids)).rsplit('_q',1)[0]+'_q'
        if isinstance(qid,str) and re.fullmatch(re.escape(prefix)+r'[1-9]\d?',qid): return False
        if row.get('id') in occurrences or row.get('item_id') in occurrences: return True
        rr = row.get('regions', row.get('source_regions', []))
        if row.get('source_sha256') and row.get('page_ranges'):
            rr = [dict(source_sha256=row['source_sha256'], page=p, box=[0,0,1,1])
                  for a,b in row['page_ranges'] for p in range(a,b+1)]
        return any(isinstance(r,dict) and r.get('source_sha256') == s['source_sha256']
                   and r.get('page') == s['page'] for r in (rr or []) for s in regions)
    prefix = next(iter(qids)).rsplit('_q', 1)[0] + '_q'
    source_hashes = {r['source_sha256'] for r in regions}
    def scope_ids(scope):
        if not isinstance(scope, dict): return []
        values = scope.get('official_qids', [scope.get('official_qid')])
        return values if isinstance(values, list) else []
    def recognized_other(scope):
        values = scope_ids(scope)
        return bool(values) and all(isinstance(value, str)
            and re.fullmatch(re.escape(prefix) + r'[1-9]\d?', value) and value not in qids for value in values)
    def same_original(sources):
        return any(s.get('sha256') in source_hashes for s in sources)
    def source_overlap(sources):
        return any(s.get('sha256') == r['source_sha256'] and r['page'] in _selected_page_numbers(s)
                   for s in sources for r in regions)
    for path in sorted(root.glob('*/state.json')):
        prior = json.loads(candidates.verified_bytes(path))
        owner = prior.get('name', path.parent.name)
        if owner == name: continue
        def blocked(reason):
            raise ValueError(f'prepared owner {owner}: ' + reason)
        def inspect_candidate(candidate, expected_sha=None):
            try:
                raw = candidates.verified_bytes(candidate)
                if expected_sha is not None and hashlib.sha256(raw).hexdigest() != expected_sha:
                    raise ValueError('candidate hash changed')
                data = json.loads(raw)
                rows = data.get('questions', [])
                if not isinstance(rows, list): raise ValueError('invalid retained questions')
            except (OSError, ValueError, TypeError, AttributeError) as exc:
                blocked('retained maker evidence is unresolved: ' + str(exc))
            if occurrence_overlap(data) or any(overlaps(row) for row in rows):
                blocked('existing or preserved maker identity/source occurrence')
        if occurrence_overlap(prior.get('required_source_occurrences', {})):
            blocked('surviving original source occurrence/hold')
        scope = prior.get('selected_item_scope') or prior.get('initial_native_question') or {}
        if qids.intersection(scope_ids(scope)):
            blocked('existing selected scope/hold')
        candidate = Path(prior.get('candidate', path.parent / 'missing'))
        if candidate.exists(): inspect_candidate(candidate)
        # Focus/next-question retain exact original makers even when the current
        # selected item and current source pages have moved elsewhere.
        inspected = set()
        for key in ('focus_history', 'completed_scope_history'):
            for entry in prior.get(key, []):
                relevant = (same_original(entry.get('sources', [])) or same_original(prior.get('sources', []))
                    or occurrence_overlap(entry) or any(isinstance(qid, str) and qid.startswith(prefix)
                                                       for qid in scope_ids(entry.get('selected_item_scope'))))
                if not relevant: continue
                try:
                    reader = 'reader_state_snapshot' if entry.get('reader_state_snapshot') else 'state_snapshot'
                    raw = candidates.verified_bytes(Path(entry[reader]))
                    if hashlib.sha256(raw).hexdigest() != entry[reader + '_sha256']:
                        raise ValueError('preserved state hash changed')
                    snapshot = json.loads(raw)
                    retained = Path(entry['candidate']); pin = entry['candidate_sha256']
                    if (snapshot.get('name') != owner or snapshot.get('course') != prior.get('course')
                            or snapshot.get('candidate') != str(retained)):
                        raise ValueError('preserved state/candidate ownership changed')
                    if key == 'focus_history':
                        maker = snapshot.get('jobs', {}).get('extract', {})
                        if maker.get('exit') != 0 or maker.get('output_sha256') != pin:
                            raise ValueError('original maker completion/hash binding changed')
                    elif (snapshot.get('selected_item_scope') != entry.get('selected_item_scope')
                            or snapshot.get('candidate_sha256', pin) != pin):
                        raise ValueError('completed selected scope binding changed')
                    inspect_candidate(retained, pin)
                    inspected.add(str(retained))
                    if qids.intersection(scope_ids(entry.get('selected_item_scope'))):
                        blocked('preserved selected scope/hold')
                except (OSError, ValueError, KeyError, TypeError) as exc:
                    blocked('preserved scope/maker evidence is unresolved: ' + str(exc))
        previous = prior.get('previous_candidate')
        if previous and previous not in inspected and (same_original(prior.get('sources', []))
                or any(isinstance(qid, str) and qid.startswith(prefix) for qid in scope_ids(scope))):
            maker = prior.get('jobs', {}).get('extract', {})
            pin = maker.get('reused_candidate_sha256')
            if maker.get('exit') != 0 or not pin:
                # Prepared retries preserve ordinary manager outputs, rather
                # than manufacturing a legacy focus/next-question reuse pin.
                config = prior.get('prepared_scope')
                try:
                    pin = hashlib.sha256(candidates.verified_bytes(Path(previous))).hexdigest()
                except (OSError, ValueError) as exc:
                    blocked('previous candidate receipt binding is unresolved: ' + str(exc))
                receipts = prior.get('prepared_attempt_receipts', [])
                if (not isinstance(config, dict) or config.get('profile') != 'pearson_native_prepared_v1'
                        or config.get('job_name') != owner or not any(
                            r.get('role') == 'extract' and r.get('prepared_scope') == config
                            and r.get('output_sha256') == pin and r.get('candidate_sha256') == pin
                            and re.fullmatch(r'[0-9a-f]{32}', str(r.get('attempt_id', '')))
                            and r.get('started') and r.get('worker_started') and r.get('finished')
                            and type(r.get('exit')) is int for r in receipts)):
                    blocked('previous candidate extract/output/scope receipt binding is unresolved')
            inspect_candidate(Path(previous), pin)
        if recognized_other(scope): continue
        if source_overlap(prior.get('sources', [])) and prior.get('scope') in ('questions', 'both'):
            maker = prior.get('jobs', {}).get('extract', {})
            completed = (maker.get('finished') and maker.get('exit') == 0 and candidate.is_file()
                         and maker.get('output_sha256') == digest(candidate))
            if scope or not completed:
                blocked('unresolved selected/broad source/range scope or hold')
            # Only an exact completed broad pass with no unresolved overlapping
            # rows, or a recognized different selected item, releases inspection.
    for pattern in ('*/continuation-dispatch-state.json', '*/continuation-queue.json'):
        for path in sorted(root.glob(pattern)):
            data = json.loads(candidates.verified_bytes(path))
            def walk(value, owner=None):
                if isinstance(value, dict):
                    owner = value.get('job', value.get('artifact', owner))
                    scope = value.get('selected_item_scope') or {}
                    if overlaps(value) or scope.get('official_qid') in qids:
                        raise ValueError(f'prepared owner {owner or path}: current queue/claim {value.get("status", "unresolved")}')
                    for child in value.values(): walk(child, owner)
                elif isinstance(value, list):
                    for child in value: walk(child, owner)
            walk(data)


def _create_prepared(name, course, provider, scope, package, codex_model, codex_effort, stop):
    from prepared_scope import verify_native_package, prepared_material, PROFILE
    from tutorlib.asset_library import AssetLibrary
    if scope != 'questions': raise ValueError('prepared scope requires questions scope')
    reader = AssetLibrary(library.learner_vault())
    graph, graph_sha = _course_graph_input(course); _graph_indexes(graph, course)
    descriptor = verify_native_package(Path(package), reader, graph_sha)
    request=json.loads((Path(package)/'request.json').read_text())
    occurrence_roots={q['occurrence']['bundle']:str(job_dir(name)/'prepared-occurrences'/q['occurrence']['complete_sha256'])
                      for q in request['questions'] if q.get('occurrence')}
    external_graphs={}
    for node in graph.get('kcs',[]):
        for prerequisite in node.get('prereqs',[]):
            target=prerequisite.split('-',1)[0]
            if target!=course and target not in external_graphs:
                try:
                    authority,external_sha=_course_graph_input(target)
                    _graph_indexes(authority,target)
                    if not authority.get('version'): continue
                    external_graphs[target]={'version':authority['version'],'sha256':external_sha}
                except (OSError,ValueError):
                    pass  # Unavailable external authority cannot validate a later mapping.
    if descriptor['course'] != course: raise ValueError('prepared scope course mismatch')
    pin = {'profile': PROFILE, 'package_sha256': digest(Path(package)/'COMPLETE'),
           'descriptor_sha256': digest(Path(package)/'descriptor.json'),
           'seed_sha256': digest(Path(package)/'seed.json'), 'graph_sha256': graph_sha,'job_name':name}
    directory = job_dir(name); output = work_root() / 'Candidates/extraction' / name
    with _prepared_claim_lock() as root:
        ledger_path = root / 'prepared-claims.json'
        ledger = json.loads(candidates.verified_bytes(ledger_path)) if ledger_path.exists() else {'version':1,'claims':[]}
        own = [claim for claim in ledger['claims'] if claim['job_name'] == name]
        if (directory/'state.json').exists():
            prior = load(name)
            if prior.get('prepared_scope') == pin: raise ValueError('identical prepared job exists: use resume '+name)
            raise ValueError('prepared target job already exists')
        if own and (len(own) != 1 or own[0]['prepared_scope'] != pin):
            raise ValueError('prepared owner '+name+': interrupted setup has different frozen scope')
        qids = {q['official_qid'] for q in descriptor['questions']}
        occurrence_ids={o['original_occurrence_id'] for q in descriptor['questions'] for o in q.get('pending_occurrences',[])}
        for claim in ledger['claims']:
            if claim['job_name'] != name and (qids.intersection(claim['official_qids'])
                    or occurrence_ids.intersection(claim.get('source_occurrences',[]))):
                raise ValueError('prepared owner '+claim['job_name']+': immutable claim/hold')
        _prepared_ownership(descriptor, root, name)
        if output.exists() or output.is_symlink() or directory.is_symlink():
            raise ValueError('prepared target cannot inherit previous candidate or alias')
        if directory.exists() and not own and any(p.name != '.lock' for p in directory.iterdir()):
            raise ValueError('prepared target cannot inherit maker or worker artifacts')
        frozen = directory/'prepared-input'
        if not own:
            claim={'job_name':name,'prepared_scope':pin,'official_qids':sorted(qids),'source_occurrences':sorted(occurrence_ids),'status':'setting_up'}
            ledger['claims'].append(claim); _atomic_json(ledger_path, ledger)
        else: claim=own[0]
        directory.mkdir(parents=True,exist_ok=True)
        for original,destination in occurrence_roots.items():
            destination=Path(destination)
            if not destination.exists():
                destination.parent.mkdir(parents=True,exist_ok=True)
                staging_occurrence=destination.with_name(destination.name+'.'+uuid.uuid4().hex+'.staging')
                shutil.copytree(original,staging_occurrence)
                from topical_fastpath import verify_bundle
                verify_bundle(staging_occurrence)
                if digest(staging_occurrence/'COMPLETE') != destination.name:
                    raise ValueError('prepared occurrence changed during freeze')
                staging_occurrence.rename(destination)
        if not frozen.exists():
            staging=directory/('prepared-input.'+uuid.uuid4().hex+'.staging')
            shutil.copytree(package,staging)
            verify_native_package(staging,reader,graph_sha,occurrence_roots=occurrence_roots)
            if digest(staging/'COMPLETE') != pin['package_sha256']: raise ValueError('prepared package changed during freeze')
            staging.rename(frozen)
        verify_native_package(frozen,reader,graph_sha,occurrence_roots=occurrence_roots)
        if digest(frozen/'COMPLETE') != pin['package_sha256']: raise ValueError('prepared recovery frozen package differs')
        _, bank_sha, bank = _active_topical_bank(library.learner_vault())
        matches=[{'decision':'reuse_or_conflict','bank_sha256':bank_sha,'item_id':row.get('id'),
                  'official_qid':row.get('source',{}).get('official_qid',row.get('source',{}).get('qid'))}
                 for row in bank.get('items',[]) if row.get('source',{}).get('official_qid',row.get('source',{}).get('qid')) in qids]
        state=dict(name=name,course=course,provider=provider,scope=scope,stage='inventoried',
                   created=timestamp(),history=[],jobs={},teaching_approved=False,candidate=str(output/'candidate.json'),
                   prepared_scope=pin,prepared_input=str(frozen),prepared_occurrences=occurrence_roots,
                   prepared_external_graphs=external_graphs,reuse_decisions=matches,
                   **prepared_material(descriptor,reader))
        if codex_model: state['codex_model']=codex_model
        if codex_effort: state['codex_effort']=codex_effort
        if stop is not None: state['codex_stop_remaining']=stop
        _atomic_json(directory/'state.json',state)
        claim['status']='claimed'; _atomic_json(ledger_path,ledger)
    return state


def _prepared_receipt_problems(state, roles=('extract','review')):
    errors=[]; identifiers=[]
    for role in roles:
        job=state.get('jobs',{}).get(role,{})
        output=_output(state,role)
        receipts=[r for r in state.get('prepared_attempt_receipts',[]) if r.get('attempt_id')==job.get('attempt_id')]
        if (not job.get('attempt_id') or not job.get('started') or not job.get('worker_started')
                or not job.get('finished') or job.get('exit') != 0 or job.get('ok') is not True
                or len(receipts)!=1 or not output.is_file()):
            errors.append('prepared '+role+' requires a successful distinct manager worker attempt'); continue
        receipt=receipts[0]; identifiers.append(job['attempt_id'])
        if (receipt.get('role')!=role or receipt.get('prepared_scope')!=state['prepared_scope']
                or receipt.get('output_sha256')!=digest(output) or job.get('output_sha256')!=digest(output)
                or receipt.get('prompt_sha256')!=job.get('prompt_sha256')
                or receipt.get('failure_input')!=job.get('failure_input')
                or receipt.get('ok') is not True or receipt.get('exit')!=0
                or any(receipt.get(key)!=job.get(key) for key in ('started','worker_started','finished'))):
            errors.append('prepared '+role+' manager receipt/output binding changed')
        prompt=job_dir(state['name'])/f'{role}.prompt.txt'
        if not prompt.is_file() or digest(prompt)!=receipt.get('prompt_sha256'):
            errors.append('prepared '+role+' dispatched prompt digest changed')
        if role=='review' and receipt.get('candidate_sha256')!=digest(candidate_path(state)):
            errors.append('prepared review receipt candidate binding changed')
    if len(identifiers)==2 and len(set(identifiers))!=2: errors.append('prepared roles require distinct attempt identities')
    return errors


def _prepared_review_problems(state, data, image_hashes):
    expected={'prepared_scope':state['prepared_scope'], 'course_graph_sha256':state['focus_graph_sha256'],
              'source_inventory_sha256':hashlib.sha256(json.dumps(state['sources'],sort_keys=True).encode()).hexdigest(),
              'seed_sha256':state['prepared_scope']['seed_sha256']}
    if any(data.get(key)!=value for key,value in expected.items()):
        return ['prepared review source/seed/graph/scope binding changed']
    return [] if set(image_hashes).issubset(set(data.get('inspected_images',[]))) else ['prepared crops lack exact visual review hashes']


def _initial_native_mode(state):
    scope = state.get('selected_item_scope')
    return ('initial_native_question' in state
            or isinstance(scope, dict) and scope.get('origin') in (_FRESH_NATIVE_P1_ORIGIN, _FRESH_NATIVE_IAL_ORIGIN))


def _fresh_native_p1_material(course: str, scope: str, official_qid: str, selectors: list[str]) -> dict:
    """Read exact original inputs; initial scope is a request, never maker evidence."""
    from tutorlib.asset_library import AssetLibrary
    pilot = p1_question(official_qid)
    if course != 'P1' or scope != 'questions' or pilot is None:
        raise ValueError('fresh native launch requires an exact supported P1 whole-question scope')
    if (not isinstance(selectors, list) or len(selectors) != 2
            or any(not isinstance(value, str) for value in selectors)):
        raise ValueError('fresh P1 needs exactly two stable source-ID/page selectors')
    sources = _native_evidence_sources(course, selectors)
    by_id = {source['id']: source for source in sources}
    library_reader = AssetLibrary(library.learner_vault())
    ordered, canonical = [], []
    for role, last_page in (('qp', 3), ('ms', 8)):
        pin = pilot[role]
        selected_pages = pin.get('initial_pages', list(range(1, last_page + 1)))
        source = by_id.get(pin['asset_id'])
        record = library_reader.record(pin['asset_id'])
        if (source is None or source['sha256'] != pin['sha256'] or source['pages'] != pin['pages']
                or source['path'] != str(library_reader.root / pin['path'])
                or source['selected_page_numbers'] != selected_pages
                or source['status'] != 'available' or source.get('ocr')
                or record.get('path') != pin['path'] or record.get('sha256') != pin['sha256']
                or record.get('course') != course or record.get('kind') != 'Sources/PastPapers'):
            raise ValueError('fresh P1 source role, metadata, bytes or selected pages changed')
        ordered.append(source)
        canonical.append(pin['asset_id'] + '=' + pin.get('initial_selector', '1-' + str(last_page)))
    if set(by_id) != {source['id'] for source in ordered}:
        raise ValueError('fresh P1 source inventory must be exactly QP and MS')
    graph_data, graph_sha = _course_graph_input(course)
    _graph_indexes(graph_data, course)
    parts = pilot.get('assessed_parts', [''])
    assessed = {'native-' + official_qid + ('-' + part if part else ''): part for part in parts}
    selected = {'type': 'official_question', 'origin': _FRESH_NATIVE_P1_ORIGIN,
                'official_qid': official_qid, 'record_ids': list(assessed), 'assessed_parts': assessed,
                'coverage_claim': 'Inspect every selected QP/MS page; extract only the complete named whole question and necessary official marking context. No page-wide extraction or content approval is claimed.'}
    if parts != ['']:
        selected['coverage_claim'] = ('Inspect every selected QP/MS page; extract both assessed parts a and b of the complete named whole question and necessary official marking context. No page-wide extraction or content approval is claimed.')
    return {'sources': ordered, 'requested_sources': [source['id'] for source in ordered], 'requested_pages': None,
            'initial_native_question': {'version': 1, 'official_qid': official_qid, 'part': '', 'source_pages': canonical},
            'selected_item_scope': selected, 'focus_graph_sha256': graph_sha}


def _fresh_native_material(course, scope, official_qid, selectors):
    if course == 'P1':
        return _fresh_native_p1_material(course, scope, official_qid, selectors)
    from tutorlib.asset_library import AssetLibrary
    question = ial_question(official_qid)
    if course != 'P2' or scope != 'questions' or question is None or question['course'] != course:
        raise ValueError('fresh native launch requires an exact supported IAL whole-question scope')
    if (not isinstance(selectors, list) or len(selectors) != 2
            or any(not isinstance(value, str) for value in selectors)):
        raise ValueError('fresh P2 needs exactly two stable source-ID/page selectors')
    sources = _native_evidence_sources(course, selectors)
    by_id = {source['id']: source for source in sources}
    reader = AssetLibrary(library.learner_vault())
    ordered, canonical = [], []
    for role in ('qp', 'ms'):
        pin = question[role]
        source = by_id.get(pin['asset_id'])
        record = reader.record(pin['asset_id'])
        if (source is None or source['sha256'] != pin['sha256'] or source['pages'] != pin['pages']
                or source['path'] != str(reader.root / pin['path'])
                or source['selected_page_numbers'] != pin['initial_pages']
                or source['status'] != 'available' or source.get('ocr')
                or record.get('path') != pin['path'] or record.get('sha256') != pin['sha256']
                or record.get('course') != course or record.get('kind') != 'Sources/PastPapers'):
            raise ValueError('fresh P2 source role, metadata, bytes or selected pages changed')
        ordered.append(source)
        canonical.append(pin['asset_id'] + '=' + pin['initial_selector'])
    if set(by_id) != {source['id'] for source in ordered}:
        raise ValueError('fresh P2 source inventory must be exactly QP and MS')
    graph_data, graph_sha = _course_graph_input(course)
    _graph_indexes(graph_data, course)
    assessed = {'native-' + official_qid + '-' + question['part_suffixes'][part]: part
                for part in question['assessed_parts']}
    selected = {'type': 'official_question', 'origin': _FRESH_NATIVE_IAL_ORIGIN,
                'official_qid': official_qid, 'record_ids': list(assessed), 'assessed_parts': assessed,
                'coverage_claim': 'Inspect every selected QP/MS page and original render; extract all three assessed parts a(i), a(ii), b of the complete named whole question and necessary official marking context. QP native text is PMT boilerplate only; original images require independent source review. No page-wide extraction or content approval is claimed.'}
    return {'sources': ordered, 'requested_sources': [source['id'] for source in ordered], 'requested_pages': None,
            'initial_native_question': {'version': 1, 'official_qid': official_qid, 'part': '', 'source_pages': canonical},
            'selected_item_scope': selected, 'focus_graph_sha256': graph_sha}


def _verify_initial_output(state, config):
    """Trust managed parent adapters, never an alias at this job's output leaf."""
    name = config.get('job_name')
    if not isinstance(name, str) or state.get('name') != name:
        raise ValueError('fresh P1 initial job ownership changed')
    job_dir(name)  # apply the manager's job-name grammar before constructing paths
    target = work_root() / 'Candidates/extraction' / name / 'candidate.json'
    if state.get('candidate') != str(target):
        raise ValueError('fresh P1 candidate must retain its managed output path')
    directory = target.parent
    if directory.is_symlink() or directory.exists() and not directory.is_dir():
        raise ValueError('fresh P1 named output directory must not be an alias')
    if target.is_symlink() or target.exists() and (not target.is_file() or target.stat().st_nlink != 1):
        raise ValueError('fresh P1 candidate must be an owned regular file, not an alias')


def _verify_initial_native_question(state: dict) -> None:
    """Recheck fixed initial provenance without assuming a later lifecycle stage."""
    if _prepared_mode(state):
        _verify_prepared(state)
        return
    if not _initial_native_mode(state):
        return
    config = state.get('initial_native_question')
    if not isinstance(config, dict):
        raise ValueError('fresh P1 initial configuration is missing or malformed')
    _verify_initial_output(state, config)
    if any(key in state for key in ('focus_history', 'completed_scope_history', 'source_rebase_history',
                                    'reference_source_history', 'required_source_occurrences')):
        raise ValueError('fresh P1 cannot inherit focused/rebound source provenance')
    expected = _fresh_native_material(state.get('course'), state.get('scope'),
                                         config.get('official_qid'), config.get('source_pages'))
    expected['initial_native_question']['job_name'] = config['job_name']
    # JSON preserves numeric/boolean distinctions that Python container equality
    # would otherwise collapse (e.g. page True == page 1).
    for key, value in expected.items():
        if key not in state or json.dumps(state[key], sort_keys=True) != json.dumps(value, sort_keys=True):
            raise ValueError('fresh P1 initial binding changed: ' + key)


def _refuse_initial_native_change(state, operation):
    if _prepared_mode(state):
        raise ValueError('prepared immutable scope does not support ' + operation)
    if _initial_native_mode(state):
        raise ValueError('fresh P1 initial scope does not support ' + operation)


def leaks(job=None, vault=None, courses=None, out=None, apply=False):
    """Run the question-media leak gate over a job's candidate media or a vault (plan only unless apply)."""
    import question_leak_gate
    if bool(job) == bool(vault):
        raise ValueError('leaks needs exactly one of JOB or --vault')
    if apply and not vault:
        raise ValueError('--apply prunes Library media: use --vault after register; a candidate is repaired by the worker')
    if vault:
        import prune_question_leaks as prune
        out = Path(out) if out else prune.WORK
        plan = prune.build_plan(Path(vault), courses=tuple((courses or ','.join(prune.COURSES)).split(',')),
                                cache_path=out / prune.OCR_CACHE)
        plan['reference_check'] = prune.simulate(Path(plan['vault']), plan)
        prune.journalled._json(out / 'plan.json', plan)
        prune.journalled._json(out / 'ai-review.json', prune.review_file(plan))
        prune.journalled._json(out / 'leak-signatures.json', prune.signatures(plan))
        by_class = prune.summarize(plan)['by_class']
        result = {'mode': 'vault', 'counts': {'delete': by_class.get('LEAK_UNREFERENCED', 0),
                  'review': by_class.get('LEAK_REFERENCED', 0) + by_class.get('SMALL_REVIEW', 0),
                  'keep': by_class.get('KEEP', 0)}, 'by_class': by_class, 'plan': str(out / 'plan.json'),
                  'review': str(out / 'ai-review.json'), 'applied': False}
        if apply:
            if plan['reference_check']['broken_count']:
                raise ValueError('prune plan would break references; not applying')
            journal = out / 'prune-journal.json'
            result['apply'] = prune.apply(plan, journal, backup=out / 'catalog.before-prune.json')
            result['applied'], result['journal'] = True, str(journal)
        return result
    state = load(job)
    root = candidate_path(state).parent.resolve()
    data = json.loads(candidate_path(state).read_text())
    private, names = set(), []
    for record in data.get('questions', []):
        private.update(record.get('mark_scheme_media') or [])
        names += [n for n in _record_media(record) if isinstance(n, str) and n not in names]
    verdicts = question_leak_gate.classify_many([root / n for n in names]) if names else {}
    counts, items = {'delete': 0, 'review': 0, 'keep': 0}, []
    for name in names:
        verdict = verdicts.get(str((root / name).resolve())) or {'action': 'review', 'reason': 'gate returned no verdict'}
        action = 'review' if verdict['action'] == 'delete' and name in private else verdict['action']
        counts[action] = counts.get(action, 0) + 1
        if action != 'keep':
            items.append({'class': 'LEAK_CANDIDATE' if action == 'delete' else 'SMALL_REVIEW', 'course': state.get('course'),
                          'id': name, 'path': name, 'sha256': digest(root / name) if (root / name).is_file() else None,
                          'width': verdict.get('width'), 'height': verdict.get('height'), 'reason': verdict.get('reason')})
    target = Path(out) if out else job_dir(job) / 'ai-review.json'
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps({'format_version': 1, 'tool': 'extract leaks', 'instructions':
        'LEAK_CANDIDATE: data-sheet/periodic-table/constants media: delete the file and drop it from the record. '
        'SMALL_REVIEW: tiny, near-blank or unchecked: confirm real question content or mark for removal.',
        'counts': {k: v for k, v in counts.items() if k != 'keep'} , 'items': items}, indent=1))
    return {'mode': 'job', 'counts': counts, 'review': str(target), 'applied': False}


def resume(name):
    state = load(name)
    _verify_initial_native_question(state)
    return state


def configure(name, reason, *, codex_stop_remaining=None, codex_role_overrides=None):
    """Audit explicitly authorized job settings without restarting or clearing guards."""
    if not isinstance(reason, str) or not reason.strip():
        raise ValueError('a reason is required to change job settings')
    updates = {}
    if codex_stop_remaining is not None:
        updates['codex_stop_remaining'] = _codex_stop_remaining(codex_stop_remaining)
    roles = codex_role_overrides or {}
    for role, choices in roles.items():
        if role not in ('extract', 'review') or not isinstance(choices, dict):
            raise ValueError('Codex role settings must select extract or review')
        for key, value in choices.items():
            if key == 'model' and isinstance(value, str) and value.strip():
                continue
            if key == 'effort' and value in ('low', 'medium', 'high', 'xhigh'):
                continue
            raise ValueError('Codex role settings need a nonempty model or a supported effort')
    if not updates and not any(roles.values()):
        raise ValueError('select at least one job setting to change')
    with state_lock(name) as state:
        if not state:
            raise ValueError('job does not exist')
        _verify_initial_native_question(state)
        if any(process_alive(job.get('pid')) and not job.get('finished') for job in state.get('jobs', {}).values()):
            raise ValueError('cannot change job settings while a worker is running')
        if roles:
            merged = {role: dict(choices) for role, choices in state.get('codex_role_overrides', {}).items()}
            for role, choices in roles.items():
                merged.setdefault(role, {}).update(choices)
            updates['codex_role_overrides'] = merged
        changes = {key: {'before': state.get(key), 'after': value} for key, value in updates.items()
                   if state.get(key) != value}
        if changes:
            state.setdefault('configuration_history', []).append({
                't': timestamp(), 'reason': reason.strip(), 'changes': changes})
            state.update(updates)
            transition(state, state['stage'], 'Job settings changed: ' + reason.strip())
    return load(name)


def _selected_page_numbers(source):
    if source.get('selected_page_numbers') is not None:
        return source['selected_page_numbers']
    start, end = source.get('selected_pages') or (1, source['pages'])
    return list(range(start, end + 1))


def focus(name, official_qid, reason, *, stage_missing_scheme=False):
    """Derive one whole-question revision without resetting the job or its guard."""
    if not isinstance(reason, str) or not reason.strip():
        raise ValueError('a reason is required for a focused revision')
    with state_lock(name) as state:
        _refuse_initial_native_change(state, 'focus')
        if state.get('selected_item_scope'):
            raise ValueError('job is already focused; repair its existing revision')
        if state.get('stage') in ('reviewed', 'registered', 'published') or state.get('registrations'):
            raise ValueError('reviewed or registered candidates cannot be focused')
        if any(process_alive(job.get('pid')) and not job.get('finished') for job in state.get('jobs', {}).values()):
            raise ValueError('cannot focus while a worker is running')
        if stage_missing_scheme:
            failures = state.get('reliability_failures', {}).get(str(state.get('pass', 1)), {})
            if any(len(failures.get(role, [])) >= reliability.MAX_FAILURES for role in ('extract', 'review')):
                raise ValueError('missing-scheme staging refuses a current two-failure guard')
        maker = state.get('jobs', {}).get('extract', {})
        original = candidate_path(state)
        original_sha = digest(original)
        if maker.get('exit') != 0 or maker.get('output_sha256') != original_sha:
            raise ValueError('focus requires the exact saved successful maker output')
        _verify_sources(state)
        original, original_sha, records, narrowed, rows, scope, graph_sha = _question_focus_material(state, official_qid, stage_missing_scheme=stage_missing_scheme)
        revision_id = 'focus-' + official_qid + '-' + uuid.uuid4().hex
        revision = original.parent / 'revisions' / revision_id
        snapshot = work_root() / 'Preparation/extraction' / name / revision_id / 'state.json'
        revision.mkdir(parents=True)
        snapshot.parent.mkdir(parents=True)
        snapshot.write_bytes((job_dir(name) / 'state.json').read_bytes())
        media_hashes = {}
        for row in records:
            for media in _record_media(row):
                source = (original.parent / media).resolve()
                destination = revision / media
                destination.parent.mkdir(parents=True, exist_ok=True)
                if not destination.exists():
                    shutil.copyfile(source, destination)
                media_hashes[media] = digest(destination)
        candidate = revision / 'candidate.json'
        candidate.write_text(json.dumps({'questions': records, 'diagrams': [], 'source_coverage': rows,
                                        'selected_item_scope': scope}, ensure_ascii=False, indent=2) + '\n')
        state.setdefault('focus_history', []).append({
            't': timestamp(), 'reason': reason.strip(), 'state_snapshot': str(snapshot),
            'state_snapshot_sha256': digest(snapshot), 'candidate': str(original),
            'candidate_sha256': original_sha, 'sources': state['sources'], 'jobs': state['jobs'],
            'selected_item_scope': scope, 'reused_media_sha256': media_hashes})
        state.update(candidate=str(candidate), sources=narrowed, scope='questions',
                     selected_item_scope=scope, focus_graph_sha256=graph_sha,
                     previous_candidate=str(original), candidate_sha256=digest(candidate), problems=[], teaching_approved=False)
        state['jobs'] = {
            'extract': {'provider': maker['provider'], 'exit': 0, 'finished': timestamp(),
                        'reused_candidate_sha256': original_sha},
            'review': {'provider': state['jobs']['review']['provider']}}
        transition(state, 'focused', 'Whole-question revision reuses saved maker bytes: ' + reason.strip())
    return load(name)


def _validate_ial_record(state, record):
    """Use only the configured vault's catalog for the exact structured pilot."""
    from tutorlib.asset_library import AssetLibrary
    if os.environ.get('STEM_LIBRARY_ROOT'):
        raise ValueError(f"{state['course']} sources require the configured vault AssetLibrary")
    if record.get('kind') != 'structured':
        raise ValueError(f"{state['course']} pilot supports structured whole questions only")
    validate_ial_sources(record.get('official_qid'), record.get('part'), state['course'],
                        record.get('regions'), record.get('mark_scheme_regions'),
                        AssetLibrary(library.learner_vault()))


def _question_focus_material(state, official_qid, *, stage_missing_scheme=False):
    if official_qid == _FRESH_ONLY_P1_Q4:
        raise ValueError('P1 Q4 requires a separate authentic fresh native scope')
    original = candidate_path(state)
    original_sha = digest(original)
    data = json.loads(original.read_text())
    records = [row for row in data.get('questions', []) if row.get('official_qid') == official_qid]
    valid_identity = (p1_pilot(official_qid, '') is not None if state['course'] == 'P1'
                      else re.fullmatch(re.escape(state['course']) + r'_[msw]\d{2}_\d{2}_q\d+', official_qid) is not None)
    if not records or not valid_identity:
        raise ValueError('official question is absent or invalid')
    ids = [row.get('id') for row in records]
    if any(not isinstance(identifier, str) or not identifier for identifier in ids) or len(set(ids)) != len(ids):
        raise ValueError('selected question requires unique stable record IDs')
    sources = {source['id']: source for source in state['sources']}
    selected, missing_scheme = {}, []
    for row in records:
        if state['course'] in ('P1', 'P2') or ial_namespace(row.get('official_qid')):
            _validate_ial_record(state, row)
        for key in ('regions', 'mark_scheme_regions'):
            if key == 'mark_scheme_regions' and stage_missing_scheme and row.get(key) == []:
                missing_scheme.append(row['id'])
                continue
            if errors := _regions(row, sources, key):
                raise ValueError('; '.join(errors))
            for region in row[key]:
                selected.setdefault(region['source_id'], set()).add(region['page'])
        if errors := _media(state, row)[0]:
            raise ValueError('; '.join(errors))
        if any(not isinstance(media, str) or Path(media).is_absolute() or '..' in Path(media).parts
               for media in _record_media(row)):
            raise ValueError('focused revision requires safe candidate-relative media paths')
    coverage = {row['source_id']: row for row in data.get('source_coverage', [])}
    narrowed, rows = [], []
    for source_id, pages in selected.items():
        source, prior = sources[source_id], coverage.get(source_id, {})
        if (prior.get('source_sha256') != source['sha256'] or prior.get('no_relevant_content') is not False
                or not pages.issubset(set(prior.get('inspected_pages', [])))):
            raise ValueError('focused pages must have saved maker inspection coverage')
        narrowed.append({**source, 'selected_page_numbers': sorted(pages)})
        narrowed[-1].pop('selected_pages', None)
        rows.append({**prior, 'inspected_pages': sorted(pages), 'reason': ''})
    _, graph_sha = _course_graph_input(state['course'])
    scope = {'type': 'official_question', 'official_qid': official_qid, 'record_ids': ids,
             'assessed_parts': {row['id']: row.get('part') for row in records},
             'coverage_claim': 'Only the complete selected question and its official mark scheme; no page-wide completeness claim.'}
    if missing_scheme:
        scope['missing_historical_mark_scheme_record_ids'] = missing_scheme
    return original, original_sha, records, narrowed, rows, scope, graph_sha


def _published_scope_evidence(state):
    """Read-only proof that the exact reviewed/registered scope remains published."""
    from tutorlib.asset_library import AssetLibrary
    if (state.get('stage') not in ('published', 'reviewed') or not state.get('publication')
            or not state.get('selected_item_scope') or not state.get('registrations')):
        raise ValueError('next-question requires the current scope to be reviewed, registered and published')
    _verify_sources(state)
    errors, images = _candidate_problems(state)
    if errors:
        raise ValueError('published candidate validation failed: ' + '; '.join(errors))
    candidate = candidate_path(state)
    sha = digest(candidate)
    if sha != state.get('candidate_sha256') or sha != state.get('registered_candidate_sha256'):
        raise ValueError('published candidate/registration binding changed')
    review_raw = (job_dir(state['name']) / 'review.json').read_bytes()
    review = json.loads(review_raw)
    review_sha = hashlib.sha256(review_raw).hexdigest()
    if (state['jobs']['review'].get('exit') != 0 or review.get('candidate_sha256') != sha
            or review.get('verdict') != 'pass' or review.get('findings') != []
            or not set(images).issubset(review.get('inspected_images', []))
            or state['jobs']['review'].get('output_sha256', review_sha) != review_sha):
        raise ValueError('independent review binding or visual evidence changed')
    catalog = AssetLibrary(library.learner_vault())
    rows = json.loads(candidate.read_text())['questions']
    registered, media_hashes = [], {}
    for row in rows:
        context = hashlib.sha256(json.dumps(row, sort_keys=True).encode()).hexdigest()[:12]
        mapping = state.get('registered_records', {}).get(context, {})
        if set(mapping) != set(_record_media(row)):
            raise ValueError('registered record/media binding changed')
        for local in _record_media(row):
            reference = mapping[local]
            raw = catalog.read(reference)
            if raw != (candidate.parent / local).read_bytes():
                raise ValueError('registered media differs from the reviewed candidate')
            media_hashes[local] = hashlib.sha256(raw).hexdigest()
            registered.append(str(catalog.resolve(reference)))
            sidecars = catalog.record(reference).get('provenance', {}).get('sidecars', [])
            provenance = [json.loads(catalog.read(ref)) for ref in sidecars]
            if not provenance or any(value.get('record') != row or value.get('review') != review
                    or value.get('source_inventory') != state['sources']
                    or value.get('sha256') != media_hashes[local] for value in provenance):
                raise ValueError('registered source/review provenance changed')
    if sorted(registered) != sorted(str(catalog.resolve(ref)) for ref in state['registrations']):
        raise ValueError('registration inventory changed')
    release = state['publication']['release']
    report_raw = catalog.read(release + '/report.json')
    binding = json.loads(report_raw).get('extraction', {})
    if (binding.get('job') != state['name'] or binding.get('candidate_sha256') != sha
            or binding.get('review_sha256') != review_sha):
        raise ValueError('publication candidate/review binding changed')
    bank_raw = catalog.read(release + '/bank.json')
    published = [item for item in json.loads(bank_raw)['items']
                 if item.get('source', {}).get('extraction_job') == state['name']
                 and item.get('source', {}).get('candidate_sha256') == sha]
    expected = {'extracted-' + row['official_qid'] + '-' +
                hashlib.sha256(json.dumps(row, sort_keys=True).encode()).hexdigest()[:12] for row in rows}
    if len(published) != len(rows) or {item['id'] for item in published} != expected:
        raise ValueError('published scope does not contain the exact candidate IDs')
    version, bank_sha, active = _active_topical_bank(library.learner_vault())
    active_by_id = {item['id']: item for item in active['items']}
    if any(active_by_id.get(item['id']) != item for item in published):
        raise ValueError('active bank no longer preserves every published scope item unchanged')
    return {'review_raw': review_raw, 'review_sha256': review_sha, 'report_raw': report_raw,
            'bank_raw': bank_raw, 'published_items': published, 'media_sha256': media_hashes,
            'active_version': version, 'active_bank_sha256': bank_sha, 'active_bank': active}


def next_question(name, official_qid, reason, *, stage_missing_scheme=False):
    """Archive a completed scope and reuse another whole question from its original maker."""
    from tutorlib.topicals import identity

    def whole_question(source):
        canonical = identity({'source': source})
        return canonical.split(':', 1)[0] if canonical else None

    if not isinstance(reason, str) or not reason.strip():
        raise ValueError('a reason is required to advance to the next question')
    with state_lock(name) as state:
        _refuse_initial_native_change(state, 'next_question')
        if any(process_alive(job.get('pid')) and not job.get('finished') for job in state.get('jobs', {}).values()):
            raise ValueError('cannot advance while a worker is running')
        failures = state.get('reliability_failures', {}).get(str(state.get('pass', 1)), {})
        if any(len(failures.get(role, [])) >= reliability.MAX_FAILURES for role in ('extract', 'review')):
            raise ValueError('current scope has a two-failure guard; next-question never clears failures')
        evidence = _published_scope_evidence(state)
        processed = {whole_question({'qid': entry['selected_item_scope']['official_qid']})
                     for entry in state.get('focus_history', [])}
        active = {whole_question(item.get('source', {})) for item in evidence['active_bank']['items']}
        target = whole_question({'qid': official_qid})
        if target is not None and target in processed | active:
            raise ValueError('target question is already processed or active')
        first = state['focus_history'][0]
        raw = candidates.verified_bytes(Path(first['state_snapshot']))
        if hashlib.sha256(raw).hexdigest() != first['state_snapshot_sha256']:
            raise ValueError('original maker state snapshot changed')
        baseline = json.loads(raw)
        original = candidate_path(baseline)
        if (str(original) != first['candidate'] or digest(original) != first['candidate_sha256']
                or baseline['jobs']['extract'].get('exit') != 0
                or baseline['jobs']['extract'].get('output_sha256') != first['candidate_sha256']
                or baseline['name'] != name or baseline['course'] != state['course']):
            raise ValueError('original maker artifact binding changed')
        _verify_sources(baseline)
        original, original_sha, records, narrowed, rows, scope, graph_sha = _question_focus_material(baseline, official_qid, stage_missing_scheme=stage_missing_scheme)
        revision_id = 'next-' + official_qid + '-' + uuid.uuid4().hex
        revision = original.parent / 'revisions' / revision_id
        archive = work_root() / 'Preparation/extraction' / name / revision_id
        revision.mkdir(parents=True)
        archive.mkdir(parents=True)
        snapshot = archive / 'state.json'
        snapshot.write_bytes((job_dir(name) / 'state.json').read_bytes())
        files = {'review.json': evidence['review_raw'], 'publication-report.json': evidence['report_raw'],
                 'publication-bank.json': evidence['bank_raw']}
        for filename, contents in files.items():
            (archive / filename).write_bytes(contents)
        archived = {'t': timestamp(), 'reason': reason.strip(), 'selected_item_scope': state['selected_item_scope'],
                    'candidate': state['candidate'], 'candidate_sha256': state['candidate_sha256'],
                    'state_snapshot': str(snapshot), 'state_snapshot_sha256': digest(snapshot),
                    'review_snapshot': str(archive / 'review.json'), 'review_sha256': evidence['review_sha256'],
                    'files': {filename: {'path': str(archive / filename), 'sha256': digest(archive / filename)} for filename in files},
                    'registrations': state['registrations'], 'registered_records': state['registered_records'],
                    'publication': state['publication'], 'source_rebase_history': state.get('source_rebase_history', []),
                    'reference_source_history': state.get('reference_source_history', []),
                    'media_sha256': evidence['media_sha256'], 'published_items': evidence['published_items'],
                    'active_version': evidence['active_version'], 'active_bank_sha256': evidence['active_bank_sha256']}
        media_hashes = {}
        for row in records:
            for media in _record_media(row):
                target = revision / media
                target.parent.mkdir(parents=True, exist_ok=True)
                if not target.exists():
                    shutil.copyfile(original.parent / media, target)
                media_hashes[media] = digest(target)
        candidate = revision / 'candidate.json'
        candidate.write_text(json.dumps({'questions': records, 'diagrams': [], 'source_coverage': rows,
                                        'selected_item_scope': scope}, ensure_ascii=False, indent=2) + '\n')
        state.setdefault('completed_scope_history', []).append(archived)
        state['focus_history'].append({'t': timestamp(), 'reason': reason.strip(),
            'state_snapshot': str(snapshot), 'state_snapshot_sha256': digest(snapshot),
            'reader_state_snapshot': first['state_snapshot'], 'reader_state_snapshot_sha256': first['state_snapshot_sha256'],
            'candidate': str(original), 'candidate_sha256': original_sha, 'sources': baseline['sources'],
            'jobs': baseline['jobs'], 'selected_item_scope': scope, 'reused_media_sha256': media_hashes})
        providers = {role: job['provider'] for role, job in state['jobs'].items()}
        for key in ('publication', 'registrations', 'registered_media', 'registered_records', 'registered_candidate_sha256',
                    'required_source_occurrences', 'source_rebase_history', 'reference_source_history'):
            state.pop(key, None)
        state.update(candidate=str(candidate), candidate_sha256=digest(candidate), previous_candidate=str(original),
                     sources=narrowed, selected_item_scope=scope, focus_graph_sha256=graph_sha,
                     scope='questions', problems=[], teaching_approved=False,
                     jobs={'extract': {'provider': providers['extract'], 'exit': 0, 'finished': timestamp(),
                                       'reused_candidate_sha256': original_sha}, 'review': {'provider': providers['review']}})
        transition(state, 'focused', 'Next whole question reuses original maker work: ' + reason.strip())
    return load(name)


def _native_evidence_sources(course, selectors):
    """Resolve exact catalog IDs and bounded per-source pages through Library readers."""
    if os.environ.get('STEM_LIBRARY_ROOT'):
        raise ValueError('native evidence sources require catalogued AssetLibrary resources')
    if not selectors:
        raise ValueError('select at least one exact source and its pages')
    from tutorlib.asset_library import AssetLibrary
    catalog = AssetLibrary(library.learner_vault())
    sources, seen = [], set()
    for selector in selectors:
        if not isinstance(selector, str) or '=' not in selector:
            raise ValueError('source pages require asset:ID=1,3-4')
        ref, page_spec = selector.split('=', 1)
        if not ref.startswith('asset:') or not page_spec or ref in seen:
            raise ValueError('select unique exact asset IDs with explicit pages')
        files = library.source_files('all', course, references={ref})
        if len(files) != 1:
            raise ValueError('native evidence source must be an exact catalogued source for this course')
        kind, path = files[0]
        record = catalog.record(ref)
        text = library.load(path, quiet=True)
        if text['error'] or text['scanned'] or not text['pages']:
            raise ValueError('native evidence source must have an available native text layer')
        pages = set()
        for token in page_spec.split(','):
            match = re.fullmatch(r'(\d+)(?:-(\d+))?', token)
            if not match:
                raise ValueError('source pages require positive pages or inclusive ranges')
            start, end = int(match[1]), int(match[2] or match[1])
            if not 1 <= start <= end <= len(text['pages']):
                raise ValueError('native evidence pages are outside the source')
            pages.update(range(start, end + 1))
        sha = digest(path)
        if sha != record['sha256']:
            raise ValueError('native evidence source hash changed')
        sources.append({'id': ref, 'path': str(path), 'sha256': sha, 'kind': kind,
                        'aliases': [str(path), *record.get('aliases', [])], 'pages': len(text['pages']),
                        'selected_page_numbers': sorted(pages), 'status': 'available', 'error': ''})
        seen.add(ref)
    if sum(len(source['selected_page_numbers']) for source in sources) > 100:
        raise ValueError('native evidence revisions are limited to 100 selected pages')
    return sources


def evidence_sources(name, selectors, reason):
    """Stage native source evidence for a focused repair, preserving original occurrences."""
    if not isinstance(reason, str) or not reason.strip():
        raise ValueError('a reason is required for native evidence sources')
    with state_lock(name) as state:
        _refuse_initial_native_change(state, 'evidence_sources')
        if not state.get('selected_item_scope'):
            raise ValueError('focus one whole official question before selecting native evidence sources')
        if state.get('source_rebase_history'):
            raise ValueError('job already has a native evidence revision; repair that revision')
        if state.get('stage') in ('reviewed', 'registered', 'published') or state.get('registrations'):
            raise ValueError('reviewed or registered candidates cannot change evidence sources')
        if any(process_alive(job.get('pid')) and not job.get('finished') for job in state['jobs'].values()):
            raise ValueError('cannot change evidence sources while a worker is running')
        failures = state.get('reliability_failures', {}).get(str(state.get('pass', 1)), {})
        for role in ('extract', 'review'):
            if len(failures.get(role, [])) >= reliability.MAX_FAILURES:
                raise ValueError(f'{role} paused after two failures; native evidence cannot clear a guard')
        _verify_sources(state)
        original = candidate_path(state)
        sha = digest(original)
        if sha != state.get('candidate_sha256'):
            raise ValueError('native evidence revision requires the exact saved focused candidate')
        data = json.loads(original.read_text())
        if errors := _coverage(state, data):
            raise ValueError('; '.join(errors))
        sources = _native_evidence_sources(state['course'], selectors)
        required = {}
        for record in data['questions']:
            occurrences = record.get('source_occurrences', [])
            if not isinstance(occurrences, list):
                raise ValueError('source occurrences must be a list')
            for key in ('regions', 'mark_scheme_regions'):
                if (key == 'mark_scheme_regions' and record.get(key) == []
                        and record['id'] in state['selected_item_scope'].get('missing_historical_mark_scheme_record_ids', [])):
                    continue  # Preserve explicitly declared historical absence; current validators stay strict.
                if errors := _regions(record, {source['id']: source for source in state['sources']}, key):
                    raise ValueError('; '.join(errors))
            if errors := _media(state, record)[0]:
                raise ValueError('; '.join(errors))
            if any(not isinstance(media, str) or Path(media).is_absolute() or '..' in Path(media).parts
                   for media in _record_media(record)):
                raise ValueError('native evidence requires safe candidate-relative media paths')
            record['source_occurrences'] = occurrences + [{'candidate_sha256': sha,
                'regions': record['regions'], 'mark_scheme_regions': record['mark_scheme_regions']}]
            required[record['id']] = record['source_occurrences']
        revision_id = 'native-evidence-' + uuid.uuid4().hex
        revision = original.parent / 'revisions' / revision_id
        snapshot = work_root() / 'Preparation/extraction' / name / revision_id / 'state.json'
        revision.mkdir(parents=True)
        snapshot.parent.mkdir(parents=True)
        snapshot.write_bytes((job_dir(name) / 'state.json').read_bytes())
        for record in data['questions']:
            for media in _record_media(record):
                destination = revision / media
                destination.parent.mkdir(parents=True, exist_ok=True)
                if not destination.exists():
                    shutil.copyfile(original.parent / media, destination)
        candidate = revision / 'candidate.json'
        candidate.write_text(json.dumps(data, ensure_ascii=False, indent=2) + '\n')
        history = {'t': timestamp(), 'reason': reason.strip(), 'state_snapshot': str(snapshot),
                   'state_snapshot_sha256': digest(snapshot), 'candidate': str(original),
                   'candidate_sha256': sha, 'sources': state['sources'], 'jobs': state['jobs'],
                   'source_coverage': data['source_coverage'], 'native_sources': sources,
                   'required_source_occurrences': required}
        review = job_dir(name) / 'review.json'
        if review.exists():
            archived = snapshot.parent / 'review.json'
            shutil.copyfile(review, archived)
            history.update(review_snapshot=str(archived), review_sha256=digest(archived))
        state.setdefault('source_rebase_history', []).append(history)
        state.update(candidate=str(candidate), candidate_sha256=digest(candidate), previous_candidate=str(original),
                     sources=sources, required_source_occurrences=required, teaching_approved=False,
                     problems=['Native source evidence staged; original regions/coverage require source-bound maker repair.'])
        state['jobs'] = {role: {'provider': job['provider']} for role, job in state['jobs'].items()}
        for key in ('registered_candidate_sha256', 'registered_media', 'registered_records'):
            state.pop(key, None)
        transition(state, 'evidence_repair_required', 'Native evidence staged without content approval: ' + reason.strip())
    return load(name)


def reference_sources(name, selectors, purpose, reason):
    """Append explicitly auxiliary native references before the first native repair."""
    if any(not isinstance(value, str) or not value.strip() for value in (purpose, reason)):
        raise ValueError('a reference-only purpose and reason are required')
    with state_lock(name) as state:
        _refuse_initial_native_change(state, 'reference_sources')
        if (state.get('stage') != 'evidence_repair_required' or not state.get('source_rebase_history')
                or not state.get('selected_item_scope') or state.get('registrations') or state.get('publication')
                or state.get('registered_candidate_sha256')):
            raise ValueError('references require an unreviewed native-staged question before its first repair')
        if state.get('reference_source_history'):
            raise ValueError('reference sources already appended for this scope')
        if (set(state['jobs']) != {'extract', 'review'}
                or any(set(job) != {'provider'} for job in state['jobs'].values())):
            raise ValueError('cannot append references after a native maker/reviewer attempt or while running')
        failures = state.get('reliability_failures', {}).get(str(state.get('pass', 1)), {})
        if any(len(failures.get(role, [])) >= reliability.MAX_FAILURES for role in ('extract', 'review')):
            raise ValueError('two-failure guard prevents reference staging')
        _verify_sources(state)
        original = candidate_path(state)
        if digest(original) != state.get('candidate_sha256'):
            raise ValueError('reference staging requires the exact saved native-staged candidate')
        data = json.loads(original.read_text())
        rebase = state['source_rebase_history'][-1]
        prior_raw = candidates.verified_bytes(Path(rebase['candidate']))
        if hashlib.sha256(prior_raw).hexdigest() != rebase['candidate_sha256']:
            raise ValueError('reference staging original focused candidate binding changed')
        expected = json.loads(prior_raw)
        for row in expected['questions']:
            row['source_occurrences'] = state['required_source_occurrences'][row['id']]
        if data != expected:
            raise ValueError('reference staging candidate scope, content or occurrence provenance changed')
        additions = _native_evidence_sources(state['course'], selectors)
        if {source['id'] for source in state['sources']} & {source['id'] for source in additions}:
            raise ValueError('references must append new source IDs without replacing existing selections')
        if sum(len(_selected_page_numbers(source)) for source in state['sources'] + additions) > 100:
            raise ValueError('reference inventory is limited to 100 selected pages combined')
        for source in additions:
            source.update(evidence_role='auxiliary_reference', reference_purpose=purpose.strip())
        folder = work_root() / 'Preparation/extraction' / name / ('references-' + uuid.uuid4().hex)
        media = {}
        for row in data['questions']:
            errors, _ = _media(state, row)
            if errors:
                raise ValueError('; '.join(errors))
            for relative in _record_media(row):
                if Path(relative).is_absolute() or '..' in Path(relative).parts:
                    raise ValueError('reference staging requires safe relative media paths')
                media[relative] = original.parent / relative
        folder.mkdir(parents=True)
        snapshot = folder / 'state.json'
        snapshot.write_bytes((job_dir(name) / 'state.json').read_bytes())
        candidate = folder / 'candidate.json'
        shutil.copyfile(original, candidate)
        media_bindings = {}
        for relative, path in media.items():
            target = folder / 'media' / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(path, target)
            media_bindings[relative] = {'path': str(target), 'sha256': digest(target)}
        entry = {'t': timestamp(), 'reason': reason.strip(),
            'purpose': purpose.strip(), 'state_snapshot': str(snapshot), 'state_snapshot_sha256': digest(snapshot),
            'candidate_snapshot': str(candidate), 'candidate_sha256': digest(candidate),
            'media': media_bindings, 'added_sources': additions}
        manifest = folder / 'reference-append.json'
        manifest.write_text(json.dumps(entry, ensure_ascii=False, indent=2) + '\n')
        state['reference_source_history'] = [{**entry, 'manifest': str(manifest), 'manifest_sha256': digest(manifest)}]
        state['sources'] = state['sources'] + additions
    return load(name)


def _reference_inventory(state, rebase):
    """Authenticate the append separately; the original native rebase stays frozen."""
    entries = state.get('reference_source_history')
    if not entries:
        return rebase['native_sources']
    if len(entries) != 1:
        raise ValueError('reference append history changed')
    entry = entries[0]
    manifest_raw = candidates.verified_bytes(Path(entry['manifest']))
    if (hashlib.sha256(manifest_raw).hexdigest() != entry['manifest_sha256']
            or json.loads(manifest_raw) != {k: v for k, v in entry.items() if k not in ('manifest', 'manifest_sha256')}):
        raise ValueError('reference append manifest changed')
    raw = candidates.verified_bytes(Path(entry['state_snapshot']))
    if hashlib.sha256(raw).hexdigest() != entry['state_snapshot_sha256']:
        raise ValueError('reference state snapshot hash changed')
    prior = json.loads(raw)
    if (prior.get('reference_source_history') or prior['sources'] != rebase['native_sources']
            or any(prior.get(key) != state.get(key) for key in ('name', 'course', 'scope', 'selected_item_scope',
                    'focus_graph_sha256', 'focus_history', 'source_rebase_history', 'required_source_occurrences'))
            or prior['candidate_sha256'] != entry['candidate_sha256']
            or digest(entry['candidate_snapshot']) != entry['candidate_sha256']):
        raise ValueError('reference source, candidate, scope or graph lineage changed')
    for binding in entry['media'].values():
        if digest(binding['path']) != binding['sha256']:
            raise ValueError('reference archived media changed')
    additions = entry['added_sources']
    if (not additions or not isinstance(entry['purpose'], str) or not entry['purpose'].strip()
            or any(source.get('evidence_role') != 'auxiliary_reference'
                   or source.get('reference_purpose') != entry['purpose'] for source in additions)
            or len({source['id'] for source in prior['sources'] + additions}) != len(prior['sources'] + additions)
            or sum(len(_selected_page_numbers(source)) for source in prior['sources'] + additions) > 100):
        raise ValueError('reference-only inventory changed')
    return prior['sources'] + additions


def _ocr_reader_source(state, source):
    """Resolve frozen reader inputs and reject unsupported focused source changes."""
    if _initial_native_mode(state):
        _verify_initial_native_question(state)
        for native in state['sources']:
            if json.dumps(source, sort_keys=True) == json.dumps(native, sort_keys=True):
                return native
        raise ValueError('source is outside the fresh P1 inventory')
    if not state.get('selected_item_scope'):
        return source
    try:
        history = state['focus_history'][-1]
        raw = candidates.verified_bytes(Path(history.get('reader_state_snapshot', history['state_snapshot'])))
        if hashlib.sha256(raw).hexdigest() != history.get('reader_state_snapshot_sha256', history['state_snapshot_sha256']):
            raise ValueError('snapshot hash mismatch')
        snapshot = json.loads(raw)
        if state.get('source_rebase_history'):
            rebase = state['source_rebase_history'][-1]
            prior_raw = candidates.verified_bytes(Path(rebase['state_snapshot']))
            if hashlib.sha256(prior_raw).hexdigest() != rebase['state_snapshot_sha256']:
                raise ValueError('native evidence snapshot hash mismatch')
            prior = json.loads(prior_raw)
            expected = _reference_inventory(state, rebase)
            if (state['sources'] != expected or source not in expected
                    or prior['sources'] != rebase['sources']
                    or prior['selected_item_scope'] != state['selected_item_scope']
                    or prior['focus_graph_sha256'] != state['focus_graph_sha256']
                    or history['selected_item_scope'] != state['selected_item_scope']):
                raise ValueError('native evidence inventory or focused lineage changed')
            return source
        originals = [row for row in snapshot['sources'] if row['id'] == source['id']]
        if len(originals) != 1 or history['selected_item_scope'] != state['selected_item_scope']:
            raise ValueError('original source or selected item changed')
        original = originals[0]
        if (any(original.get(key) != source.get(key) for key in ('id', 'sha256', 'path', 'pages', 'status', 'ocr'))
                or not set(_selected_page_numbers(source)).issubset(_selected_page_numbers(original))):
            raise ValueError('original source identity, status, OCR binding or working pages changed')
    except (KeyError, IndexError, OSError, TypeError, ValueError) as exc:
        raise ValueError('focused OCR reader provenance is unavailable or changed: ' + str(exc)) from exc
    return original


def _verify_sources(state):
    if _prepared_mode(state):
        _verify_prepared(state)
        return
    if _initial_native_mode(state):
        _verify_initial_native_question(state)
        return
    if state.get('focus_graph_sha256') and _course_graph_input(state['course'])[1] != state['focus_graph_sha256']:
        raise ValueError('course graph changed since focused revision; independent review binding is stale')
    if state.get('reference_source_history'):
        if (not state.get('source_rebase_history')
                or state['sources'] != _reference_inventory(state, state['source_rebase_history'][-1])):
            raise ValueError('reference inventory or native rebase binding changed')
    selected_paths = {source['path'] for source in state['sources']}
    available = {str(path): path for _, path in library.source_files('all', state['course'], references=selected_paths)}
    for source in state['sources']:
        if source['path'] not in available or digest(source['path']) != source['sha256']:
            raise ValueError(f"source changed or is unavailable: {source['path']}; inventory a fresh job")
        reader = _ocr_reader_source(state, source)
        if reader.get('ocr'):
            source_ocr.read(reader, ocr_cache_root())


def enable_ocr(name, source_id):
    """Explicitly freeze unreviewed native OCR inputs before a job is planned."""
    with state_lock(name) as state:
        _refuse_initial_native_change(state, 'enable_ocr')
        if state.get('jobs'):
            raise ValueError('enable OCR before planning; create a fresh job for different reader inputs')
        _verify_sources(state)
        source = next((s for s in state['sources'] if s['id'] == source_id), None)
        if not source or source['status'] != 'pending_ocr':
            raise ValueError('OCR opt-in requires a scan source in this job inventory')
        source['ocr'] = source_ocr.freeze(source, ocr_cache_root())
        transition(state, state['stage'], 'Unreviewed native OCR inputs frozen; source remains pending_ocr.')
    return load(name)


def ocr_text(name, source_id, pages=None):
    state = load(name)
    source = next((s for s in state['sources'] if s['id'] == source_id), None)
    if not source:
        raise ValueError('source is outside this job inventory')
    if not source.get('ocr'):
        raise ValueError('native OCR is not enabled for this job source')
    _verify_sources(state)
    selected = None
    if pages is not None:
        start, end = library.page_range(pages, source['pages'], Path(source['path']))
        selected = range(start, end + 1)
    if state.get('selected_item_scope'):
        selected = _selected_page_numbers(source) if selected is None else list(selected)
        if any(page not in _selected_page_numbers(source) for page in selected):
            raise ValueError('OCR read is outside the selected focused source pages')
    result = source_ocr.read(_ocr_reader_source(state, source), ocr_cache_root(), selected)
    for page in result['pages']:
        lines = page.pop('lines')
        page['line_count'] = len(lines)
        page['minimum_line_confidence'] = min((line['confidence'] for line in lines), default=None)
    return result


def inventory(name):
    with state_lock(name) as state:
        if state.get('jobs'):
            raise ValueError('planned job inventory is frozen; create a fresh job for different sources')
        if _initial_native_mode(state) or _prepared_mode(state):
            _verify_initial_native_question(state)
            return state
        unique, matched = {}, set()
        catalog = None
        if not os.environ.get('STEM_LIBRARY_ROOT'):
            from tutorlib.asset_library import AssetLibrary
            catalog = AssetLibrary(library.learner_vault())
        by_path = {record['path']: (identifier, record) for identifier, record in catalog.records().items()} if catalog else {}
        requested = set(state.get('requested_sources', []))
        for kind, path in library.source_files('all', state['course'], references=requested or None):
            refs = {str(path)}
            ref = str(path)
            if catalog:
                relative = path.relative_to(catalog.root).as_posix()
                identifier, record = by_path[relative]
                ref = 'asset:' + identifier
                refs.update([ref, relative, str(library.learner_vault() / relative), *record.get('aliases', [])])
            if requested and not requested.intersection(refs):
                continue
            matched.update(requested.intersection(refs))
            sha = digest(path)
            if sha in unique:
                unique[sha]['aliases'].append(str(path))
                continue
            text = library.load(path, quiet=True)
            # Source identities remain stable; byte aliases are an inventory optimization only.
            unique[sha] = {'id': ref, 'path': str(path), 'sha256': sha, 'kind': kind,
                           'aliases': [str(path)], 'pages': len(text['pages']),
                           'selected_pages': list(library.page_range(state.get('requested_pages'), len(text['pages']), path)) if text['pages'] else [],
                           'status': 'pending_ocr' if text['scanned'] else 'unreadable' if text['error'] else 'available',
                           'error': text['error']}
        if requested - matched:
            raise ValueError('source selectors must exactly match verified sources for this course: ' + ', '.join(sorted(requested - matched)))
        state['sources'] = list(unique.values())
        transition(state, 'inventoried', f'{len(unique)} unique source PDFs')
    return load(name)


def plan(name):
    with state_lock(name) as state:
        _verify_initial_native_question(state)
        if state['jobs']:
            return state
        if _prepared_mode(state) and state.get('reuse_decisions'):
            raise ValueError('prepared attested bank matches require reuse/conflict resolution; no paid worker')
        if not state['sources']:
            raise ValueError('inventory has no sources; inventory first')
        _verify_sources(state)
        maker = 'claude' if state['provider'] == 'both' else state['provider']
        reviewer = 'codex' if state['provider'] == 'both' else maker
        state['jobs'] = {'extract': {'provider': maker}, 'review': {'provider': reviewer}}
        state['review_independence'] = 'opposite_family' if maker != reviewer else 'same_family'
        state['review_limitation'] = '' if maker != reviewer else 'Separate blind task uses the same model family.'
        transition(state, 'planned')
    return load(name)


def _output(state, role):
    return candidate_path(state) if role == 'extract' else job_dir(state['name']) / 'review.json'


def _record_attempt_failure(state, role, issues, exit_code=0):
    """Charge a failed result/gate once per launch, never once per check poll."""
    job = state['jobs'][role]
    if not job.get('failure_recorded'):
        reliability.record_result(state, role, ok=False, exit_code=exit_code, issues=issues)
        job['failure_recorded'] = True
    job['ok'] = False


def _review_scope_binding(state):
    contract = json.loads(_prompt(state, 'review').split('JOB CONTRACT:\n', 1)[1])
    if (not contract.get('course_graph_sha256')
            or _course_graph_input(state['course'])[1] != contract['course_graph_sha256']):
        raise ValueError('review feedback binding requires the unchanged frozen source/graph scope')
    keys=('course', 'scope', 'selected_item_scope', 'sources', 'course_graph_sha256', 'required_source_occurrences')
    if _prepared_mode(state): keys+=('prepared_scope','seed_sha256','prepared_external_graphs')
    return {key: contract.get(key) for key in keys}


def _review_input_fingerprint(state, state_raw, candidate_raw):
    """Recompute reliability's exact framing using historical bytes at logical input paths."""
    value = hashlib.sha256()
    value.update(json.dumps(['review', str(state.get('pass', 1))], separators=(',', ':')).encode())
    for path, raw in ((job_dir(state['name']) / 'state.json', state_raw),
                      (candidate_path(state), candidate_raw)):
        json.loads(raw)
        name = str(path).encode()
        value.update(len(name).to_bytes(8, 'big'))
        value.update(name)
        value.update(len(raw).to_bytes(8, 'big'))
        value.update(raw)
    return value.hexdigest()


def _save_review_input(state, fingerprint):
    raw = candidates.verified_bytes(job_dir(state['name']) / 'state.json')
    prior = json.loads(raw)
    candidate_raw = candidates.verified_bytes(candidate_path(state))
    if _review_input_fingerprint(prior, raw, candidate_raw) != fingerprint:
        raise ValueError('review feedback input changed before snapshot capture')
    path = job_dir(state['name']) / 'review-inputs' / fingerprint / 'state.json'
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        if candidates.verified_bytes(path) != raw:
            raise ValueError('review feedback input snapshot binding changed')
    else:
        path.write_bytes(raw)
    return hashlib.sha256(raw).hexdigest()


def _review_input_proof(state, fingerprint, reviewed):
    if re.fullmatch(r'[0-9a-f]{64}', str(fingerprint)) is None:
        raise ValueError('review feedback historical input fingerprint is missing or invalid')
    path = job_dir(state['name']) / 'review-inputs' / fingerprint / 'state.json'
    try:
        raw = candidates.verified_bytes(path)
        prior = json.loads(raw)
    except (OSError, ValueError) as exc:
        raise ValueError('review feedback historical input state binding is missing or invalid') from exc
    fields = ('name', 'course', 'scope', 'selected_item_scope', 'sources',
              'required_source_occurrences', 'focus_graph_sha256', 'initial_native_question', 'prepared_scope', 'prepared_input', 'prepared_occurrences', 'prepared_external_graphs')
    if (not isinstance(prior, dict) or any(prior.get(key) != state.get(key) for key in fields)
            or str(prior.get('pass', 1)) != str(state.get('pass', 1))
            or prior.get('candidate') != state['candidate']
            or _review_input_fingerprint(prior, raw, candidates.verified_bytes(reviewed)) != fingerprint):
        raise ValueError('review feedback historical input/candidate binding changed')
    return hashlib.sha256(raw).hexdigest()


def _review_attempt_receipt(state, fingerprint):
    receipts = [entry for entry in state.get('review_attempt_history', [])
                if entry.get('failure_input') == fingerprint]
    if len(receipts) > 1:
        raise ValueError('review feedback retained attempt receipt binding is ambiguous')
    return receipts[0] if receipts else {}


def _retained_review_authentication(state, attempt, review_sha, reviewed):
    snapshot_sha = _review_input_proof(state, attempt.get('failure_input'), reviewed)
    receipt = _review_attempt_receipt(state, attempt['failure_input'])
    if receipt and any(receipt.get(key) != value for key, value in (
            ('pass', str(state.get('pass', 1))), ('output_sha256', review_sha),
            ('candidate_sha256', digest(reviewed)), ('input_state_sha256', snapshot_sha))):
        raise ValueError('review feedback retained attempt receipt binding changed')
    if attempt.get('input_state_sha256', snapshot_sha) != snapshot_sha:
        raise ValueError('review feedback launch input state binding changed')
    return {'review_input_state_sha256': snapshot_sha}


def _review_contract_authentication(state, attempt, prompt_raw, binding):
    receipt = _review_attempt_receipt(state, attempt.get('failure_input'))
    proofs = [(entry.get('prompt_sha256'), entry.get('course_graph_sha256'))
              for entry in (attempt, receipt) if 'prompt_sha256' in entry]
    if not proofs:
        return None  # Historical graph proof must come from the reviewed candidate.
    prompt_sha, graph_sha = proofs[0]
    if (any(proof != proofs[0] for proof in proofs)
            or hashlib.sha256(prompt_raw).hexdigest() != prompt_sha
            or graph_sha != binding['course_graph_sha256']):
        raise ValueError('review feedback dispatched prompt/graph binding changed')
    path = job_dir(state['name']) / 'review-inputs' / attempt['failure_input'] / 'review.prompt.txt'
    try:
        frozen = candidates.verified_bytes(path)
        contract = json.loads(frozen.decode().split('JOB CONTRACT:\n', 1)[1])
    except (OSError, UnicodeError, ValueError, IndexError) as exc:
        raise ValueError('review feedback dispatched contract binding is unavailable') from exc
    if (frozen != prompt_raw or {key: contract.get(key) for key in binding} != binding
            or contract.get('candidate') != str(candidate_path(state))):
        raise ValueError('review feedback dispatched contract binding changed')
    return {'dispatched_prompt_sha256': prompt_sha, 'course_graph_sha256': graph_sha}


def _valid_review_result(data):
    if not isinstance(data, dict) or data.get('verdict') not in ('pass', 'pending'):
        return False
    findings, images = data.get('findings'), data.get('inspected_images')
    return (isinstance(findings, list) and all(isinstance(value, str) and value.strip() for value in findings)
            and bool(findings) == (data['verdict'] == 'pending')
            and isinstance(images, list) and all(isinstance(value, str) for value in images)
            and re.fullmatch(r'[0-9a-f]{64}', str(data.get('candidate_sha256', ''))) is not None)


def _resolved_prior_scope_review(state, recorded):
    """An archived published pass resolves its retained failures, not a new scope's review."""
    if any(key in state['jobs']['review'] for key in ('started', 'finished', 'exit', 'failure_input', 'output_sha256')):
        return False  # Only a reset, never-started review role may use prior-scope completion.
    history = state.get('completed_scope_history', [])
    if not history or history[-1]['selected_item_scope'] == state['selected_item_scope']:
        return False
    entry = history[-1]
    raw = candidates.verified_bytes(Path(entry['state_snapshot']))
    if hashlib.sha256(raw).hexdigest() != entry['state_snapshot_sha256']:
        raise ValueError('review feedback archived completion binding changed')
    prior = json.loads(raw)
    failures = prior.get('reliability_failures', {}).get(str(state.get('pass', 1)), {}).get('review', [])
    if (failures[-1] if failures else {}) != recorded:
        return False
    review_raw = candidates.verified_bytes(Path(entry['review_snapshot']))
    review = json.loads(review_raw)
    if (not entry.get('publication') or prior.get('stage') not in ('published', 'reviewed')
            or hashlib.sha256(review_raw).hexdigest() != entry['review_sha256']
            or review.get('verdict') != 'pass' or review.get('findings') != []
            or review.get('candidate_sha256') != entry['candidate_sha256']
            or prior.get('candidate_sha256') != entry['candidate_sha256']
            or prior.get('registered_candidate_sha256') != entry['candidate_sha256']
            or prior.get('publication') != entry['publication']
            or prior.get('selected_item_scope') != entry['selected_item_scope'] or prior.get('name') != state['name']):
        raise ValueError('review feedback archived published pass binding changed')
    return True


def _review_repair_input(state):
    """Capture one exact pending review before a retry changes the saved candidate pointers."""
    expected = state['jobs']['review'].get('output_sha256')
    failures = state.get('reliability_failures', {}).get(str(state.get('pass', 1)), {}).get('review', [])
    recorded = failures[-1] if failures else {}
    if not state.get('selected_item_scope') and expected is None and not recorded:
        return None  # Unauthenticated legacy reviews never supply maker feedback.
    if expected is None and state.get('selected_item_scope') and _resolved_prior_scope_review(state, recorded):
        return None
    review_path = job_dir(state['name']) / 'review.json'
    if not review_path.exists():
        if expected is not None or recorded:
            raise ValueError('review feedback output is missing despite recorded review evidence')
        return None
    raw = review_path.read_bytes()
    review = json.loads(raw)
    if not isinstance(review, dict):
        raise ValueError('review feedback binding requires a review object')
    findings = review.get('findings')
    review_sha = hashlib.sha256(raw).hexdigest()
    if expected is not None:
        if expected != review_sha:
            raise ValueError('review feedback output binding changed')
        if state['jobs']['review'].get('exit') != 0 or not state['jobs']['review'].get('finished'):
            raise ValueError('review feedback requires a completed zero-exit review attempt')
        authentication = {'attempt_output_sha256': expected}
    else:
        if (review.get('verdict') != 'pending' or recorded.get('issues') != findings or recorded.get('exit_code') != 0
                or re.fullmatch(r'[0-9a-f]{64}', str(recorded.get('failure_input', ''))) is None):
            raise ValueError('review feedback findings lack matching recorded independent review evidence')
        authentication = {'recorded_review_failure': recorded}
    if not _valid_review_result(review):
        raise ValueError('review feedback review schema binding is invalid')
    if review.get('verdict') == 'pass' and findings == []:
        return None
    if (review.get('verdict') != 'pending' or not isinstance(findings, list) or not findings
            or any(not isinstance(item, str) or not item.strip() for item in findings)):
        raise ValueError('review feedback binding requires specific unresolved findings')
    prompt_path = job_dir(state['name']) / 'review.prompt.txt'
    try:
        prompt_raw = prompt_path.read_bytes()
        contract = json.loads(prompt_raw.decode().split('JOB CONTRACT:\n', 1)[1])
    except (OSError, UnicodeError, ValueError, IndexError) as exc:
        raise ValueError('review feedback input binding is unavailable') from exc
    binding = _review_scope_binding(state)
    current = candidate_path(state)
    previous = Path(state['previous_candidate']) if state.get('previous_candidate') else None
    eligible = [path for path in (current, previous) if path is not None and path.is_file()]
    reviewed = next((path for path in eligible if digest(path) == review.get('candidate_sha256')), None)
    if reviewed is None:
        raise ValueError('reviewed candidate binding matches neither current nor saved previous candidate bytes')
    binding_sha = hashlib.sha256(json.dumps(binding, sort_keys=True).encode()).hexdigest()
    feedback_id = hashlib.sha256(json.dumps([review['candidate_sha256'], binding_sha]).encode()).hexdigest()
    if any(entry.get('feedback_id') == feedback_id for entry in state.get('review_repair_history', [])):
        raise ValueError('review feedback was already consumed by a repair attempt')
    attempt = state['jobs']['review'] if expected is not None else recorded
    authentication.update(_retained_review_authentication(state, attempt, review_sha, reviewed))
    dispatched = _review_contract_authentication(state, attempt, prompt_raw, binding)
    if dispatched:
        authentication.update(dispatched)
    if not state.get('selected_item_scope') and not dispatched:
        # A historical prompt is not graph evidence, even if it has a hash.
        # Require every record inside the exact authenticated reviewed bytes.
        data = json.loads(reviewed.read_text())
        rows = data.get('questions', []) + data.get('diagrams', [])
        graph_sha = binding['course_graph_sha256']
        if (not rows or any(not isinstance(row, dict)
                or not isinstance(row.get('mapping_evidence'), dict)
                or row['mapping_evidence'].get('graph_sha256') != graph_sha for row in rows)):
            raise ValueError('review feedback legacy graph witness binding is missing, mixed or stale')
        if 'course_graph_sha256' not in contract:
            contract['course_graph_sha256'] = graph_sha
        authentication['legacy_graph_witness'] = {
            'origin': 'reviewed-candidate.mapping_evidence.graph_sha256', 'sha256': graph_sha}
    if ({key: contract.get(key) for key in binding} != binding
            or contract.get('candidate') != str(candidate_path(state))):
        raise ValueError('review feedback source/scope/graph binding changed')
    repair_input = current if current.is_file() else reviewed
    sources = {source['id']: source for source in state['sources']}
    for path in (reviewed, repair_input):
        data = json.loads(path.read_text())
        if problems := _coverage(state, data):
            raise ValueError('review feedback candidate scope binding changed: ' + '; '.join(problems))
        for kind in ('questions', 'diagrams'):
            for row in data[kind]:
                for key in (('regions', 'mark_scheme_regions') if kind == 'questions' else ('regions',)):
                    if problems := _regions(row, sources, key):
                        raise ValueError('review feedback candidate source binding changed: ' + '; '.join(problems))
    return {'feedback_id': feedback_id, 'findings': findings, 'review_sha256': review_sha,
            'review_authentication': authentication,
            'review_candidate_sha256': review['candidate_sha256'],
            'repair_input_candidate_sha256': digest(repair_input), 'binding': binding,
            'binding_sha256': binding_sha, 'inputs': {'review.json': raw,
            'review.prompt.txt': prompt_raw, 'reviewed-candidate.json': reviewed.read_bytes(),
            'repair-input-candidate.json': repair_input.read_bytes()}}


def _save_review_feedback(state, feedback):
    folder = work_root() / 'Preparation/extraction' / state['name'] / ('review-repair-' + uuid.uuid4().hex)
    folder.mkdir(parents=True)
    packet = {key: value for key, value in feedback.items() if key != 'inputs'}
    packet['files'] = {}
    for filename, raw in feedback['inputs'].items():
        path = folder / filename
        path.write_bytes(raw)
        packet['files'][filename] = {'path': str(path), 'sha256': hashlib.sha256(raw).hexdigest()}
    path = folder / 'packet.json'
    path.write_text(json.dumps(packet, ensure_ascii=False, indent=2) + '\n')
    metadata = {'path': str(path), 'sha256': digest(path), 'feedback_id': packet['feedback_id'],
                'review_sha256': packet['review_sha256'], 'review_candidate_sha256': packet['review_candidate_sha256'],
                'repair_input_candidate_sha256': packet['repair_input_candidate_sha256']}
    state.setdefault('review_repair_history', []).append({**metadata, 'captured_at': timestamp()})
    return metadata


def _bound_review_feedback(state):
    metadata = state.get('jobs', {}).get('extract', {}).get('review_feedback')
    if not metadata:
        return None
    path = Path(metadata['path'])
    if digest(path) != metadata['sha256']:
        raise ValueError('review feedback packet binding changed')
    packet = json.loads(path.read_text())
    if packet['binding'] != _review_scope_binding(state):
        raise ValueError('review feedback source/scope/graph binding changed')
    for entry in packet['files'].values():
        if digest(entry['path']) != entry['sha256']:
            raise ValueError('review feedback archived input binding changed')
    if not state.get('previous_candidate') or digest(state['previous_candidate']) != packet['repair_input_candidate_sha256']:
        raise ValueError('review feedback repair input candidate binding changed')
    return {key: packet[key] for key in ('findings', 'review_sha256', 'review_candidate_sha256',
                                        'repair_input_candidate_sha256', 'binding_sha256')}


def _prompt(state, role):
    _verify_initial_native_question(state)
    contract = (REPO / 'extraction/roles' / f'{role}.md').read_text()
    feedback = _bound_review_feedback(state) if role == 'extract' else None
    sources = []
    for source in state['sources']:
        selected = ({'selected_page_numbers': _selected_page_numbers(source)} if state.get('selected_item_scope')
                    else {'selected_page_range': dict(zip(('start', 'end'), source.get('selected_pages') or (1, source['pages'])), inclusive=True)})
        sources.append({**{k: v for k, v in source.items() if k not in ('selected_pages', 'selected_page_numbers')}, **selected})
    bounded = {}
    if _initial_native_mode(state) or _prepared_mode(state):
        cli = [str(REPO / '.venv/bin/python'), str(REPO / 'build/library.py')]
        for source in state['sources']:
            pages = source['selected_page_numbers']
            runs = []
            for page in pages:
                if not runs or page != runs[-1][-1] + 1:
                    runs.append([])
                runs[-1].append(page)
            if len(runs) == 1:
                # Preserve the original contiguous Q1 contract exactly.
                text_plan = {'text': shlex.join([*cli, 'text', source['id'], '--pages', f'{pages[0]}-{pages[-1]}'])}
            else:
                text_plan = {'text_runs': [
                    {'pages': run, 'command': shlex.join([
                        *cli, 'text', source['id'], '--pages',
                        str(run[0]) if len(run) == 1 else f'{run[0]}-{run[-1]}'])}
                    for run in runs]}
            bounded[source['id']] = {
                **text_plan,
                'render': [{'page': page, 'command': shlex.join([*cli, 'page', source['id'], str(page)])}
                           for page in pages]}
    return contract + '\nJOB CONTRACT:\n' + json.dumps({
        'course': state['course'], 'scope': state['scope'], 'sources': sources,
        **({'prepared_scope': state['prepared_scope'], 'seed_sha256': state['prepared_scope']['seed_sha256'],
            'prepared_record_map': state['selected_item_scope']['records'], 'bounded_read_plan': bounded,
            'frozen_preparation_seed': str(Path(state['prepared_input'])/'seed.json'),
            'source_inventory_sha256': hashlib.sha256(json.dumps(state['sources'],sort_keys=True).encode()).hexdigest(),
            'prepared_external_graphs':state.get('prepared_external_graphs',{})}
           if _prepared_mode(state) else {}),
        **({'initial_native_question': state['initial_native_question'], 'bounded_read_plan': bounded}
           if _initial_native_mode(state) else {}),
        **({'selected_item_scope': state['selected_item_scope'], 'course_graph_sha256': state['focus_graph_sha256']}
           if state.get('selected_item_scope') else
           {'course_graph_sha256': _course_graph_input(state['course'])[1]} if role == 'review' else {}),
        **({'required_source_occurrences': state['required_source_occurrences']}
           if state.get('required_source_occurrences') else {}),
        'candidate': str(candidate_path(state)), 'output': str(_output(state, role)),
        'allowed_output_directory': str(candidate_path(state).parent),
        'review_independence': state['review_independence'],
        'repository': str(REPO), 'render_and_crop_cli': str(REPO / 'bin/extract'),
        'source_read_commands': {
            'course_graph': {
                'relative': f"bin/extract graph {state['name']}",
                'absolute': shlex.join([str(REPO / 'bin/extract'), 'graph', state['name']]),
                'lookup_option': '--id', 'query_option': '--query',
                'default_results': 8, 'max_results': 20,
                'scope': 'Current-course KC facts and declared prerequisite validity; source mappings still need review.',
            },
            **({'ocr_text': {
                'relative': f"bin/extract ocr-text {state['name']}",
                'absolute': shlex.join([str(REPO / 'bin/extract'), 'ocr-text', state['name']]),
                'source_option': '--source', 'pages_option': '--pages', 'warning': source_ocr.WARNING,
            }} if any(source.get('ocr') for source in state['sources']) else {}),
            **{
            action: {'relative': f'.venv/bin/python build/library.py {action}',
                     'absolute': shlex.join([str(REPO / '.venv/bin/python'), str(REPO / 'build/library.py'), action])}
            for action in ('text', 'figures', 'page')}},
        'candidate_crop_command': shlex.join([str(REPO / 'bin/extract'), 'crop', state['name']]),
        **({'previous_candidate': state.get('previous_candidate'),
            'pending_findings': (feedback['findings'] if feedback else []) + state.get('problems', []),
            **({'review_feedback': feedback} if feedback else {})} if role == 'extract' else {}),
    }, ensure_ascii=False, indent=2)


def worker_command(state, role, *, prompt=None):
    _verify_initial_native_question(state)
    provider = state['jobs'][role]['provider']
    cfg = json.loads((REPO / 'foundry/config.json').read_text())
    model, effort = cfg['ladders']['drafter' if role == 'extract' else 'checker'][provider][0]
    if provider == 'codex':
        overrides = state.get('codex_role_overrides', {}).get(role, {})
        model = overrides.get('model') or state.get('codex_model') or model
        effort = overrides.get('effort') or state.get('codex_effort') or effort
    binary = os.environ.get('STEM_EXTRACT_' + provider.upper()) or shutil.which(provider)
    if not binary:
        raise ValueError(f'{provider} CLI unavailable; selected provider is never silently replaced')
    prompt = _prompt(state, role) if prompt is None else prompt
    if provider == 'codex':
        return [binary, 'exec', '-m', model, '-c', f'model_reasoning_effort="{effort}"',
                '-c', 'approval_policy="never"', '-s', 'workspace-write', '-C', str(REPO),
                '--add-dir', str(candidate_path(state).parent), '--add-dir', str(job_dir(state['name'])),
                '--color', 'never', '-o', str(job_dir(state['name']) / f'{role}.response.json'), prompt]
    allowed = []
    relative = f"bin/extract graph {state['name']}"
    absolute = shlex.join([str(REPO / 'bin/extract'), 'graph', state['name']])
    allowed.extend([f'Bash({relative} *)', f'Bash({absolute} *)'])
    for action in ('text', 'figures', 'page'):
        relative = f'.venv/bin/python build/library.py {action}'
        absolute = shlex.join([str(REPO / '.venv/bin/python'), str(REPO / 'build/library.py'), action])
        allowed.extend([f'Bash({relative} *)', f'Bash({absolute} *)'])
    if role == 'extract':
        relative = f"bin/extract crop {state['name']}"
        absolute = shlex.join([str(REPO / 'bin/extract'), 'crop', state['name']])
        allowed.extend([f'Bash({relative} *)', f'Bash({absolute} *)'])
    return [binary, '-p', prompt, '--model', model, *(['--effort', effort] if effort else []),
            *router.LEAN, '--tools', 'Read,Write,Edit,Bash,Glob,Grep', '--permission-mode', 'acceptEdits',
            '--allowedTools', *allowed, '--add-dir', str(candidate_path(state).parent),
            '--add-dir', str(job_dir(state['name']))]


def run(name, weekly_remaining=None, wait=False, retry=None):
    """Launch one persisted stage; the next invocation starts its independent reviewer."""
    with state_lock(name) as state:
        if not state['jobs']:
            raise ValueError('plan the job first')
        _verify_sources(state)
        if any(process_alive(job.get('pid')) and not job.get('finished') for job in state['jobs'].values()):
            return state
        role = retry or ('review' if state['jobs']['extract'].get('exit') == 0 else 'extract')
        if role not in ('extract', 'review'):
            raise ValueError('retry must select extract or review')
        inputs = [job_dir(name) / 'state.json']
        if role == 'review':
            inputs.append(candidate_path(state))
        if why := reliability.launch_problem(state, role, inputs):
            raise ValueError(why)
        if role == 'review':
            if _prepared_mode(state) and (problems := _prepared_receipt_problems(state, ('extract',))):
                raise ValueError('; '.join(problems))
            candidate_errors, _ = _candidate_problems(state)
            if candidate_errors:
                raise ValueError('candidate validation failed before review: ' + '; '.join(candidate_errors))
        import capabilities
        if why := capabilities.preflight():
            raise ValueError(why)
        launch_fingerprint = reliability.fingerprint(state, role, inputs)
        selected_pages = sum(len(_selected_page_numbers(source)) for source in state['sources'])
        if selected_pages > 100:
            raise ValueError('worker batches are limited to 100 pages; create a job with exact --source and --pages selectors')
        if not retry and role == 'review' and state['jobs']['review'].get('exit') == 0:
            try:
                previous = json.loads(_output(state, role).read_text())
                if previous.get('candidate_sha256') == digest(candidate_path(state)):
                    return state
            except (OSError, ValueError):
                pass
        cfg = json.loads((REPO / 'foundry/config.json').read_text())
        reserve = max(25, 100 - cfg.get('weekly_launch_cap', 70),
                      cfg.get('reserve', {}).get(state['jobs'][role]['provider'], 0))
        if state['jobs'][role]['provider'] == 'codex' and state.get('codex_stop_remaining') is not None:
            reserve = _codex_stop_remaining(state['codex_stop_remaining'])
        if weekly_remaining is None or not reserve < weekly_remaining <= 100:
            raise ValueError(f'a current weekly remaining percentage above the {reserve}% launch boundary is required')
        if role == 'review':
            input_state_sha = _save_review_input(state, launch_fingerprint)
            review_prompt = _prompt(state, role)
            frozen_prompt = job_dir(name) / 'review-inputs' / launch_fingerprint / 'review.prompt.txt'
            if frozen_prompt.exists() and candidates.verified_bytes(frozen_prompt) != review_prompt.encode():
                raise ValueError('review feedback dispatched prompt snapshot binding changed')
            frozen_prompt.write_bytes(review_prompt.encode())
            review_launch = {'input_state_sha256': input_state_sha,
                             'prompt_sha256': hashlib.sha256(review_prompt.encode()).hexdigest(),
                             'course_graph_sha256': json.loads(review_prompt.split('JOB CONTRACT:\n', 1)[1])['course_graph_sha256']}
        feedback = _review_repair_input(state) if role == 'extract' and retry == 'extract' else None
        if role == 'extract':
            if feedback:
                state['jobs']['extract']['review_feedback'] = _save_review_feedback(state, feedback)
            else:
                state['jobs']['extract'].pop('review_feedback', None)
        if _prepared_mode(state) and role == 'extract':
            if candidate_path(state).exists() and not any(
                    r.get('role')=='extract' and r.get('worker_started') and r.get('finished')
                    and r.get('prepared_scope')==state['prepared_scope']
                    for r in state.get('prepared_attempt_receipts',[])):
                raise ValueError('prepared first maker cannot adopt inherited output without a real manager attempt')
            from prepared_scope import retained_output_hashes
            descriptor=_verify_prepared(state)
            if candidate_path(state).exists():
                current_sha = _prepared_output_digest(state, candidate_path(state))
                current_job = state['jobs']['extract']
                owners = [r for r in state.get('prepared_attempt_receipts', [])
                          if r.get('role') == 'extract' and r.get('attempt_id') == current_job.get('attempt_id')
                          and r.get('prepared_scope') == state['prepared_scope']]
                if (current_sha not in retained_output_hashes(state) or len(owners) != 1
                        or current_job.get('output_sha256') != current_sha
                        or owners[0].get('output_sha256') != current_sha
                        or owners[0].get('candidate_sha256') != current_sha):
                    raise ValueError('prepared current predecessor differs from its current extract attempt receipt')
            _seed_prepared_media(state, descriptor)
        output = _output(state, role)
        output.parent.mkdir(parents=True, exist_ok=True)
        # A retry cannot inherit a stale successful candidate/review.
        if output.exists():
            previous = output.with_name(output.name + '.' + uuid.uuid4().hex + '.previous')
            output.rename(previous)
            if role == 'extract':
                state['previous_candidate'] = str(previous)
                state['jobs']['review'] = {'provider': state['jobs']['review']['provider']}
        prompt = review_prompt if role == 'review' else _prompt(state, role)
        command = worker_command(state, role, prompt=prompt)
        (job_dir(name) / f'{role}.prompt.txt').write_text(prompt)
        if _prepared_mode(state):
            response=job_dir(name)/f'{role}.response.json'
            if response.exists(): response.rename(response.with_name(response.name+'.'+uuid.uuid4().hex+'.previous'))
            state['jobs'][role].update(attempt_id=uuid.uuid4().hex,
                prompt_sha256=hashlib.sha256(prompt.encode()).hexdigest(),prepared_scope=state['prepared_scope'])
            state['jobs'][role].pop('worker_started',None)
        state['jobs'][role].update(started=timestamp(), finished=None, exit=None,
                                  failure_recorded=False,
                                  failure_input=launch_fingerprint,
                                  weekly_remaining=weekly_remaining, weekly_read_at=timestamp())
        if role == 'review':
            state['jobs'][role].update(review_launch)
        state['jobs'][role]['command'] = command[:-1]  # prompt stored separately, no global router writes
        log = job_dir(name) / f'{role}.log'
        state['jobs'][role]['log'] = str(log)
        transition(state, 'extracting' if role == 'extract' else 'reviewing')
        if _prepared_mode(state):
            # The child may read immediately; its issued identity must already
            # be durable before spawning, while the parent still owns the lock.
            _atomic_json(job_dir(name)/'state.json',state)
        try:
            with log.open('a') as stream:
                process = subprocess.Popen([sys.executable, str(Path(__file__).resolve()), '_worker', name, role],
                                           cwd=REPO, stdout=stream, stderr=stream, start_new_session=True,
                                           env={**os.environ, 'STEM_EXTRACT_ROOT': str(work_root())})
            state['jobs'][role]['pid'] = process.pid
        except (OSError, ValueError) as exc:
            state['jobs'][role].update(finished=timestamp(), exit=-1, ok=False, launch_error=str(exc))
            _record_attempt_failure(state, role, [str(exc)], exit_code=-1)
            transition(state, 'pending', 'worker launch failed')
            return state
    if wait:
        process.wait()
    return load(name)


def _worker(name, role):
    state = load(name)
    if not _prepared_mode(state):
        _verify_initial_native_question(state)
    output = _output(state, role)
    if _prepared_mode(state):
        job=state.get('jobs',{}).get(role,{})
        if not job.get('attempt_id') or not job.get('started') or job.get('finished') or job.get('worker_started'):
            raise ValueError('prepared worker requires a fresh manager-issued attempt')
        with state_lock(name) as current:
            current['jobs'][role]['worker_started']=timestamp()
        state=load(name)
    environment = {**os.environ, 'EXTRACT_OUTPUT': str(output), 'EXTRACT_ROLE': role,
                   'STEM_LIBRARY_CACHE': str(job_dir(name) / 'reader-cache'),
                   'CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC': '1'}
    issues = []
    output_sha256 = None
    try:
        _verify_sources(state)
        review_job = state['jobs'][role] if role == 'review' else {}
        if review_job.get('input_state_sha256'):
            _review_input_proof(state, review_job.get('failure_input'), candidate_path(state))
        prompt = None
        if 'prompt_sha256' in review_job:
            prompt_raw = candidates.verified_bytes(job_dir(name) / 'review.prompt.txt')
            _review_contract_authentication(state, review_job, prompt_raw, _review_scope_binding(state))
            prompt = prompt_raw.decode()
        if _prepared_mode(state) and role == 'extract':
            prompt_raw=candidates.verified_bytes(job_dir(name)/'extract.prompt.txt')
            if hashlib.sha256(prompt_raw).hexdigest()!=state['jobs'][role]['prompt_sha256']:
                raise ValueError('prepared maker dispatched prompt changed')
            prompt=prompt_raw.decode()
        command = worker_command(state, role) if prompt is None else worker_command(state, role, prompt=prompt)
        result = worker_timeout.run_captured(command, cwd=REPO, env=environment,
                                             seconds=1800)
        print(result.stdout, flush=True)
        print(result.stderr, file=sys.stderr, flush=True)
        if result.returncode == 0 and not output.exists():
            # Accept structured provider output as well as the explicitly requested file.
            text = result.stdout
            if state['jobs'][role]['provider'] == 'claude':
                report = router.claude_events(text)['report']
                text = json.dumps(report) if 'text' not in report else report['text']
            else:
                response = job_dir(name) / f'{role}.response.json'
                if response.exists():
                    text = response.read_text()
            data = json.loads(text)
            output.write_text(json.dumps(data, indent=2))
        code = result.returncode if result.returncode else (0 if output.exists() else 1)
        output_sha256 = (_prepared_output_digest(state, output) if _prepared_mode(state) and role == 'extract'
                         else digest(output) if output.is_file() else None)
        if code == 0:
            data = json.loads(output.read_text())
            if not isinstance(data, dict):
                raise ValueError('worker output must be a JSON object')
            if role == 'extract' and any(not isinstance(data.get(key), list) for key in ('questions', 'diagrams')):
                raise ValueError('candidate requires questions and diagrams lists')
            if role == 'extract' and (coverage_errors := _coverage(state, data)):
                raise ValueError('; '.join(coverage_errors))
            if role == 'review' and (not _valid_review_result(data)
                    or data.get('candidate_sha256') != digest(candidate_path(state))):
                raise ValueError('review requires current candidate binding, findings, images and verdict')
            if role == 'review' and _prepared_mode(state):
                _, hashes=_candidate_problems(state)
                if problems := _prepared_review_problems(state,data,hashes):
                    raise ValueError('; '.join(problems))
            if review_job.get('input_state_sha256'):
                _review_input_proof(state, review_job.get('failure_input'), candidate_path(state))
            if 'prompt_sha256' in review_job:
                _review_contract_authentication(state, review_job,
                    candidates.verified_bytes(job_dir(name) / 'review.prompt.txt'), _review_scope_binding(state))
    except (OSError, ValueError, TypeError, KeyError, library.Fail, subprocess.TimeoutExpired) as exc:
        print(str(exc), file=sys.stderr, flush=True)
        issues = [str(exc)]
        code = 1
    if _prepared_mode(state) and role == 'extract':
        # Timeouts can leave useful incomplete bytes; failure is retained, ownership is not lost.
        try:
            output_sha256 = _prepared_output_digest(state, output)
        except (OSError, ValueError) as exc:
            output_sha256 = None
            issues.append('prepared failed output cannot be safely bound: ' + str(exc))
            code = 1
    gate_ok = code == 0
    if gate_ok and role == 'extract':
        issues, _ = _candidate_problems(state)
        gate_ok = not issues
    if gate_ok and role == 'review' and (data.get('verdict') != 'pass' or data.get('findings')):
        gate_ok = False
        issues = [str(issue) for issue in data['findings']] or ['independent review remains pending']
    if gate_ok and role == 'review':
        issues, image_hashes = _candidate_problems(state)
        if not set(image_hashes).issubset(set(data['inspected_images'])):
            issues.append('candidate images lack hash-bound visual inspection evidence')
        gate_ok = not issues
    with state_lock(name) as current:
        if _prepared_mode(state) and current['jobs'][role].get('attempt_id')!=state['jobs'][role].get('attempt_id'):
            raise ValueError('prepared completion attempt ownership changed')
        current['jobs'][role].update(finished=timestamp(), exit=code, ok=gate_ok, output_sha256=output_sha256)
        if _prepared_mode(state):
            job=current['jobs'][role]
            current.setdefault('prepared_attempt_receipts',[]).append({
                **{key:job.get(key) for key in ('attempt_id','started','worker_started','finished','exit','ok','output_sha256','prompt_sha256','failure_input')},
                'role':role,'prepared_scope':state['prepared_scope'],
                'candidate_sha256':(output_sha256 if role == 'extract' else
                                    digest(candidate_path(state)) if candidate_path(state).is_file() else None)})
        if role == 'review' and code == 0 and state['jobs'][role].get('input_state_sha256'):
            current.setdefault('review_attempt_history', []).append({
                'pass': str(state.get('pass', 1)),
                'failure_input': state['jobs'][role]['failure_input'],
                'input_state_sha256': state['jobs'][role]['input_state_sha256'],
                'output_sha256': output_sha256, 'candidate_sha256': data['candidate_sha256'],
                **{key: state['jobs'][role][key] for key in ('prompt_sha256', 'course_graph_sha256')
                   if key in state['jobs'][role]}})
        if not gate_ok:
            _record_attempt_failure(current, role, issues or ['worker failed, timed out, or wrote invalid output'], exit_code=code)
        transition(current, 'extracted' if role == 'extract' and gate_ok else 'review_required' if gate_ok else 'pending')


def _regions(record, sources, key='regions'):
    regions = record.get(key)
    if not isinstance(regions, list) or not regions:
        return [f'{key} must contain all ordered page regions']
    errors, last = [], {}
    for region in regions:
        if not isinstance(region, dict):
            errors.append(f'{key}: invalid region object')
            continue
        source = sources.get(region.get('source_id'))
        page, box = region.get('page'), region.get('box')
        if not source or region.get('source_sha256') != source['sha256']:
            errors.append(f'{key}: source identity/hash mismatch')
        if type(page) is not int or not source or not 1 <= page <= source['pages']:
            errors.append(f'{key}: invalid source page')
        elif page not in _selected_page_numbers(source):
            errors.append(f'{key}: page is outside the selected batch')
        elif page < last.get(region.get('source_id'), 0):
            errors.append(f'{key}: pages are out of order')
        else:
            last[region.get('source_id')] = page
        if not isinstance(box, list) or len(box) != 4 or not all(type(v) in (int, float) for v in box) or not (0 <= box[0] < box[2] <= 1 and 0 <= box[1] < box[3] <= 1):
            errors.append(f'{key}: invalid normalized box')
    return errors


def _record_media(record):
    return record.get('media', []) + record.get('reference_media', [])


def _learner_media(record):
    return (record['question_media'] if record['kind'] == 'structured' or 'question_media' in record else record['media']) + record.get('reference_media', [])


def _reference_problems(state, record):
    """Optional flat attachments are auxiliary source-bound images, never QP/MS media."""
    if _prepared_mode(state):
        # Exact frozen reference roles/bytes are checked across the prepared group.
        return []
    if not any(key in record for key in ('reference_regions', 'reference_media', 'auxiliary_reference')):
        return []
    regions, media = record.get('reference_regions'), record.get('reference_media')
    if (not isinstance(regions, list) or not regions or not isinstance(media, list) or not media
            or len(regions) != len(media) or not all(isinstance(name, str) for name in media)
            or len(set(media)) != len(media)):
        return ['reference regions/media must be matching nonempty ordered attachments']
    auxiliary = {source['id']: source for source in state['sources']
                 if source.get('evidence_role') == 'auxiliary_reference' and source.get('reference_purpose')}
    errors = _regions(record, auxiliary, 'reference_regions')
    try:
        if (not state.get('reference_source_history') or not state.get('source_rebase_history')
                or _reference_inventory(state, state['source_rebase_history'][-1]) != state['sources']):
            raise ValueError('undeclared auxiliary inventory')
    except (OSError, ValueError, KeyError, TypeError) as exc:
        errors.append('reference source lineage changed: ' + str(exc))
    primary = record.get('media', [])
    if (any(Path(name).is_absolute() or '..' in Path(name).parts for name in media)
            or set(media) & set(primary)):
        errors.append('reference media must be safe separate candidate-relative attachments')
    root = candidate_path(state).parent.resolve()
    primary_hashes = {digest(root / name) for name in primary
                      if isinstance(name, str) and (root / name).resolve().is_relative_to(root) and (root / name).is_file()}
    if any((root / name).resolve().is_relative_to(root) and (root / name).is_file()
           and digest(root / name) in primary_hashes for name in media):
        errors.append('reference media duplicates primary or mark-scheme imagery')
    if metadata := record.get('auxiliary_reference'):
        source = auxiliary.get(metadata.get('source_id')) if isinstance(metadata, dict) else None
        if (not source or metadata.get('source_sha256') != source['sha256']
                or metadata.get('evidence_role') != 'auxiliary_reference'
                or metadata.get('reference_purpose') != source['reference_purpose']
                or metadata.get('regions') != regions or metadata.get('media') != media):
            errors.append('auxiliary reference metadata differs from declared source or canonical attachments')
        elif metadata.get('identity_region'):
            errors.extend(_regions({'reference_identity': [metadata['identity_region']]}, auxiliary, 'reference_identity'))
    return errors


def _media(state, record):
    errors, hashes = [], []
    files = record.get('media', [])
    references = record.get('reference_media', [])
    if (not isinstance(files, list) or not files or not isinstance(references, list)
            or not all(isinstance(name, str) for name in files + references)):
        return ['candidate media missing'], []
    root = candidate_path(state).parent.resolve()
    for file in files + references:
        path = (root / file).resolve()
        if not path.is_relative_to(root) or not path.is_file() or path.suffix.lower() not in ('.png', '.jpg', '.jpeg', '.svg'):
            errors.append('candidate media unavailable or unsafe')
        else:
            try:
                if path.suffix.lower() == '.svg':
                    from tutor_workers.media_checks import svg_problem
                    problem = svg_problem(path.read_bytes())
                    if problem:
                        raise ValueError(problem)
                else:
                    Image, _ = library._pil()
                    with Image.open(path) as image:
                        image.verify()
                hashes.append(digest(path))
            except Exception:
                errors.append('candidate media cannot be decoded')
    return errors, hashes


def _leak_gate_problems(state, record):
    """Run build/question_leak_gate on question media (on by default; fail-safe keep + flag).

    A data-sheet/periodic-table/constants leak in question media blocks registration until the
    worker drops it from the record; mark-scheme media and tiny, near-blank or unchecked images
    are only flagged for an AI look in state['media_gate'] (never blocking, never deleted here).
    """
    root = candidate_path(state).parent.resolve()
    names = [name for name in _record_media(record) if isinstance(name, str)]
    private = set(record.get('mark_scheme_media') or [])
    try:
        import question_leak_gate
        verdicts = question_leak_gate.classify_many([root / name for name in names])
        by_name = {name: verdicts.get(str((root / name).resolve())) or
                   {'action': 'review', 'reason': 'gate returned no verdict'} for name in names}
    except Exception as exc:  # noqa: BLE001 - the gate must never stop extraction by crashing
        by_name = {name: {'action': 'review', 'reason': f'gate error: {type(exc).__name__}: {exc}'} for name in names}
    errors, flags = [], state.setdefault('media_gate', {})
    for name, verdict in by_name.items():
        action = verdict.get('action')
        if action == 'delete' and name not in private:
            errors.append(f"question media {name} is a data-sheet leak ({verdict.get('reason')}): "
                          'delete the file and drop it from the record')
        if action in ('delete', 'review'):
            flags[name] = {'record': record.get('id') or record.get('official_qid'), 'action': action,
                           'reason': verdict.get('reason'), 'blocking': action == 'delete' and name not in private}
    return errors


def _question_scope_media_problems(state, records):
    """Known private bytes stay private across every record's public channels."""
    root = candidate_path(state).parent.resolve()
    private_paths = {(root / name).resolve() for record in records
                     for name in record.get('mark_scheme_media', [])}
    private_hashes = {digest(path) for path in private_paths}
    for record in records:
        for name in _learner_media(record):
            path = (root / name).resolve()
            if path in private_paths or digest(path) in private_hashes:
                return ['question scope public media contains private mark-scheme imagery']
    return []


def _coverage(state, data):
    """Require an explicit inspection disposition for every selected source page."""
    if _prepared_mode(state):
        from prepared_scope import prepared_candidate_problems
        errors = prepared_candidate_problems(state, data, _verify_prepared(state), candidate_path(state).parent)
        if errors: return errors
    elif scope := state.get('selected_item_scope'):
        records = data.get('questions', [])
        if (data.get('selected_item_scope') != scope or data.get('diagrams') != []
                or not isinstance(records, list) or any(not isinstance(row, dict) for row in records)
                or sorted(row.get('id', '') for row in records) != sorted(scope['record_ids'])
                or any(row.get('official_qid') != scope['official_qid']
                       or row.get('part') != scope['assessed_parts'].get(row.get('id')) for row in records)):
            return ['focused revision must retain the whole selected question and all assessed records']
    if required := state.get('required_source_occurrences'):
        if any(record.get('source_occurrences') != required.get(record.get('id')) for record in data.get('questions', [])):
            return ['required source occurrence provenance is missing or changed']
    rows = data.get('source_coverage')
    if not isinstance(rows, list) or any(not isinstance(row, dict) or not isinstance(row.get('source_id'), str) for row in rows):
        return ['source page coverage is missing or invalid']
    expected = {source['id']: source for source in state['sources']}
    if len(rows) != len(expected) or {row.get('source_id') for row in rows} != set(expected):
        return ['source page coverage must cover exactly every inventoried source']
    errors = []
    content_sources = set()
    for kind in ('questions', 'diagrams'):
        for record in data.get(kind, []):
            if not isinstance(record, dict) or not isinstance(record.get('regions'), list):
                return ['source page coverage requires record objects with region lists']
            keys = ['regions', 'mark_scheme_regions'] if kind == 'questions' else ['regions']
            if kind == 'questions' and record.get('reference_regions') and not _reference_problems(state, record):
                keys.append('reference_regions')
            for key in keys:
                regions = record.get(key, [])
                if not isinstance(regions, list):
                    return [f'source page coverage requires a {key} list']
                for region in regions:
                    if not isinstance(region, dict) or not isinstance(region.get('source_id'), str):
                        return ['source page coverage requires source-bound region objects']
                    content_sources.add(region['source_id'])
    for row in rows:
        source = expected[row['source_id']]
        selected_pages = _selected_page_numbers(source)
        pages = row.get('inspected_pages')
        if (row.get('source_sha256') != source['sha256'] or not isinstance(pages, list)
                or any(type(page) is not int for page in pages)
                or pages != selected_pages):
            errors.append(f"{source['id']}: source page coverage must include every selected page in order")
        empty = row.get('no_relevant_content')
        if type(empty) is not bool or (empty and (not isinstance(row.get('reason'), str) or not row['reason'].strip())):
            errors.append(f"{source['id']}: source page coverage requires an explicit content disposition and empty-scope reason")
        if empty and source['id'] in content_sources:
            errors.append(f"{source['id']}: source page coverage contradicts extracted content")
        if not empty and source['id'] not in content_sources:
            errors.append(f"{source['id']}: source page coverage has no extracted content or empty-scope reason")
    return errors


def _course_graph_input(course, *, max_bytes=None):
    if not isinstance(course, str) or not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_-]*', course):
        raise ValueError('invalid graph course')
    path = Path(os.environ.get('STEM_LIBRARY_SPECS') or REPO / 'build/out/specs') / course / 'graph.json'
    data = candidates.verified_bytes(path, max_bytes=max_bytes)
    return json.loads(data), hashlib.sha256(data).hexdigest()


def _course_graph(course):
    return _course_graph_input(course)[0]


def _graph_indexes(data, course):
    if not isinstance(data, dict) or data.get('spec') not in (None, course):
        raise ValueError('graph does not match the requested course')
    indexes = []
    for field in ('kcs', 'subtopics'):
        rows = data.get(field)
        if (not isinstance(rows, list) or any(not isinstance(row, dict)
                or not isinstance(row.get('id'), str) or not row['id'].startswith(course + '-') for row in rows)):
            raise ValueError(f'invalid current-course graph {field}')
        index = {row['id']: row for row in rows}
        if len(index) != len(rows):
            raise ValueError(f'ambiguous graph {field} identity')
        indexes.append(index)
    kcs, subtopics = indexes
    if any(not isinstance(row.get('subtopic'), str) or row['subtopic'] not in subtopics for row in kcs.values()):
        raise ValueError('graph KC has no current-course parent subtopic')
    return kcs, subtopics


def graph(name, *, kc_id=None, query=None, limit=8):
    """Bounded, read-only graph facts; matching rows never approve source mappings."""
    if type(limit) is not int or not 1 <= limit <= 20:
        raise ValueError('graph result limit must be from 1 to 20')
    if (kc_id is None) == (query is None):
        raise ValueError('choose one exact KC id or literal query')
    state = load(name)
    _verify_initial_native_question(state)
    course = state['course']
    data, sha = _course_graph_input(course, max_bytes=2_000_000)
    kcs, subtopics = _graph_indexes(data, course)
    snapshots = {course: (kcs, subtopics, sha)}
    unavailable = {}
    if kc_id is not None:
        if not isinstance(kc_id, str) or not kc_id.startswith(course + '-') or kc_id not in kcs:
            raise ValueError('unknown current-course KC id')
        matching = [kcs[kc_id]]
    else:
        if not isinstance(query, str) or not query.strip():
            raise ValueError('graph query must contain literal terms')
        terms = query.casefold().split()
        matching = []
        for row in kcs.values():
            parent = subtopics[row['subtopic']]
            fields = [row.get(key) for key in ('id', 'title', 'statement', 'guidance')]
            fields += [parent['id'], parent.get('title')]
            text = ' '.join(value if isinstance(value, str) else json.dumps(value, ensure_ascii=False)
                            for value in fields if value).casefold()
            if all(term in text for term in terms):
                matching.append(row)

    def prerequisite(identifier):
        result = {'id': identifier, 'valid': False}
        if not isinstance(identifier, str) or '-' not in identifier:
            return {**result, 'reason': 'invalid prerequisite graph ID'}
        target = course if identifier.startswith(course + '-') else identifier.split('-', 1)[0]
        if not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_-]*', target):
            return {**result, 'reason': 'invalid prerequisite course'}
        if target not in snapshots and target not in unavailable:
            try:
                other, other_sha = _course_graph_input(target, max_bytes=2_000_000)
                nodes, parents = _graph_indexes(other, target)
                snapshots[target] = (nodes, parents, other_sha)
            except (OSError, ValueError, KeyError, TypeError) as exc:
                unavailable[target] = str(exc)
        if target in unavailable:
            return {**result, 'reason': 'target graph unavailable: ' + unavailable[target]}
        nodes, parents, _ = snapshots[target]
        if identifier in nodes or identifier in parents:
            return {**result, 'valid': True}
        return {**result, 'reason': 'unknown prerequisite graph ID'}

    rows = []
    for row in sorted(matching, key=lambda row: row['id'])[:limit]:
        declared = row.get('prereqs', [])
        if not isinstance(declared, list):
            raise ValueError('invalid declared prerequisites for ' + row['id'])
        parent = subtopics[row['subtopic']]
        topics = data.get('topics', [])
        if not isinstance(topics, list):
            raise ValueError('invalid current-course graph topics')
        topic = [node for node in topics if isinstance(node, dict)
                 and parent.get('topic') is not None and node.get('id') == parent['topic']]
        if len(topic) > 1:
            raise ValueError('ambiguous graph parent topic identity')
        rows.append({**{key: row.get(key, '') for key in ('id', 'title', 'statement', 'guidance')},
                     **({'level': row['level']} if 'level' in row else {}),
                     'subtopic': {'id': parent['id'], 'title': parent.get('title', ''),
                                  **({'level': parent['level']} if 'level' in parent else {})},
                     **({'topic': {key: topic[0][key] for key in ('id', 'title', 'level') if key in topic[0]}}
                        if topic else {}),
                     'prereqs': [prerequisite(identifier) for identifier in declared]})
    result = {'course': course, 'graph_sha256': sha, 'matched': len(matching), 'limit': limit,
              'results': rows, 'target_graph_sha256': {key: value[2] for key, value in snapshots.items() if key != course}}
    if len(json.dumps(result, ensure_ascii=False, indent=2)) + 1 > 24_000:
        raise ValueError('graph output exceeds size limit; use a narrower query or lower --limit')
    return result


def _valid_prerequisites(record, course, chapters, kcs, kc_rows, external_ids):
    declared = set()
    for identifier in record.get('kcs', []):
        prerequisites = kc_rows.get(identifier, {}).get('prereqs', [])
        if isinstance(prerequisites, list):
            declared.update(value for value in prerequisites if isinstance(value, str))
    for value in record['prerequisites']:
        if not isinstance(value, str):
            return False
        if value in chapters or value in kcs:
            continue
        target = value.split('-', 1)[0]
        if value not in declared or target == course or not re.fullmatch(r'[A-Za-z0-9]+', target):
            return False
        if target not in external_ids:
            try:
                graph = _course_graph(target)
                external_ids[target] = {row['id'] for key in ('subtopics', 'kcs') for row in graph[key]}
            except (OSError, ValueError, KeyError, TypeError):
                external_ids[target] = set()
        if value not in external_ids[target]:
            return False
    return True


def _structured_problems(state, record):
    """Require an explicit rubric and reviewed separation of answers from prompts."""
    from tutorlib.topicals import validate_structured_scheme, whole_rubric
    errors = []
    if type(record.get('marks')) is not int or record['marks'] <= 0:
        errors.append('structured marks must be an explicit positive integer')
    for key in ('stem', 'answer'):
        if not isinstance(record.get(key), str) or not record[key].strip():
            errors.append(f'structured {key} is missing')
    try:
        validate_structured_scheme(record)
        entry = whole_rubric(record)
        if entry and any(name not in record.get('mark_scheme_media', [])
                         or name not in record.get('media', [])
                         or name in record.get('reference_media', [])
                         or name in record.get('question_media', [])
                         for name in entry['whole_rubric']['media']):
            errors.append('whole-rubric media must be reviewed private mark-scheme media')
    except (ValueError, TypeError, KeyError, AttributeError) as exc:
        errors.append(f'structured marking scheme remains pending: {exc}')
    errors.extend(_media_partition_problems(state, record))
    return errors


def _native_mcq_partition(state, record):
    if record.get('kind') != 'mcq':
        return False
    if state.get('selected_item_scope') and state.get('source_rebase_history'):
        return True
    # Inventory already resolves these native, course-specific paper paths through
    # AssetLibrary. A direct QP/MS job needs the same privacy contract as a rebase.
    return any(source.get('status') == 'available' and source.get('kind') == 'papers:' + state['course']
               and re.fullmatch(re.escape(state['course']) + r'_[msw]\d{2}_ms_\d{2}\.pdf', Path(source['path']).name, re.I)
               for source in state['sources'])


def _media_partition_problems(state, record):
    """Keep reviewed Q/MS roles private; new native MCQs also bind every crop."""
    errors = []
    label = 'structured' if record.get('kind') == 'structured' else 'MCQ'
    media = record.get('media')
    questions, answers = record.get('question_media'), record.get('mark_scheme_media')
    if (not isinstance(media, list) or not all(isinstance(name, str) for name in media)
            or not isinstance(questions, list) or not questions
            or not isinstance(answers, list)
            or not all(isinstance(name, str) for name in questions + answers)
            or len(questions + answers) != len(set(questions + answers))
            or set(questions + answers) != set(media)
            or questions != [name for name in media if name in questions]):
        errors.append(f'{label} question/mark-scheme media roles must partition all reviewed media in question order')
    else:
        root = candidate_path(state).parent.resolve()
        safe = {name: (root / name).resolve() for name in media
                if (root / name).resolve().is_relative_to(root) and (root / name).is_file()}
        # Renaming a mark-scheme image must not allow it into the question view.
        if any(name in safe for name in answers):
            answer_hashes = {digest(safe[name]) for name in answers if name in safe}
            if any(name in safe and digest(safe[name]) in answer_hashes for name in questions):
                errors.append(f'{label} question media contains a mark-scheme image')
    if _native_mcq_partition(state, record) and not errors:
        if not answers or answers != [name for name in media if name in answers]:
            errors.append('native MCQ private mark-scheme media must be nonempty and ordered')
        bindings = record.get('media_regions')
        if not isinstance(bindings, dict) or set(bindings) != set(media):
            errors.append('native MCQ media_regions must bind every primary image to its source region')
            return errors
        sources = {source['id']: source for source in state['sources']}
        for role, names, regions in (('question', questions, record.get('regions', [])),
                                      ('mark-scheme', answers, record.get('mark_scheme_regions', []))):
            for name in names:
                region = bindings[name]
                invalid = _regions({'media_regions': [region]}, sources, 'media_regions')
                errors.extend(invalid)
                if invalid:
                    continue
                box = region['box']
                def contains(parent):
                    if not isinstance(parent, dict) or any(parent.get(key) != region[key] for key in ('source_id', 'source_sha256', 'page')):
                        return False
                    bounds = parent.get('box')
                    return (isinstance(bounds, list) and len(bounds) == 4
                            and bounds[0] <= box[0] < box[2] <= bounds[2]
                            and bounds[1] <= box[1] < box[3] <= bounds[3])
                if not any(contains(parent) for parent in regions):
                    errors.append(f'native MCQ {role} media is not bound to its declared source role')
    return errors


def _candidate_problems(state):
    """Read-only structural/content gates shared by completion and review preflight."""
    # A valid stateless identity does not authenticate fresh manager provenance.
    # Inspect actual rows too: legacy state and candidate scope markers can vanish.
    q4 = any(isinstance(value, dict) and value.get('official_qid') == _FRESH_ONLY_P1_Q4
             for value in (state.get('selected_item_scope'), state.get('initial_native_question')))
    try:
        candidate = json.loads(candidate_path(state).read_text())
    except (OSError, ValueError, TypeError):
        candidate = None  # Ordinary malformed candidates retain common diagnostics.
    if isinstance(candidate, dict) and isinstance(candidate.get('questions'), list):
        q4 = q4 or any(isinstance(row, dict) and row.get('official_qid') == _FRESH_ONLY_P1_Q4
                       for row in candidate['questions'])
    if q4:
        config = state.get('initial_native_question')
        if not isinstance(config, dict) or config.get('official_qid') != _FRESH_ONLY_P1_Q4:
            raise ValueError('P1 Q4 candidate admission requires an authentic fresh native scope')
        _verify_initial_native_question(state)
    if state.get('course') == 'P2' and not _prepared_mode(state):
        if not isinstance(state.get('initial_native_question'), dict):
            raise ValueError('P2 candidate admission requires an authentic fresh native scope')
        _verify_initial_native_question(state)
    from tutorlib.prepared_evidence import project_identity, PROFILE
    native_rows = candidate.get('questions', []) if isinstance(candidate, dict) else []
    if not isinstance(native_rows,list): native_rows=[]
    prepared_rows = [row for row in native_rows if isinstance(row,dict) and (
        'prepared_scope_sha256' in row or isinstance(row.get('source'),dict) and row['source'].get('profile') == PROFILE
        or not _initial_native_mode(state) and project_identity({'profile':PROFILE,'course':state['course'],
            'official_qid':row.get('official_qid'),'part':row.get('part')}) is not None)]
    if _prepared_mode(state) or isinstance(candidate,dict) and 'prepared_scope' in candidate or prepared_rows:
        if not _prepared_mode(state):
            raise ValueError('prepared candidate admission requires authentic frozen manager scope')
        _verify_prepared(state)
    errors, image_hashes = [], []
    state['media_gate'] = {}  # Fresh leak-gate flags for this check (see _leak_gate_problems).
    sources = {source['id']: source for source in state['sources']}
    try:
        graph = _course_graph(state['course'])
        chapters = {row['id'] for row in graph['subtopics']}
        kcs = {row['id']: row['subtopic'] for row in graph['kcs']}
        kc_rows = {row['id']: row for row in graph['kcs']}
    except (OSError, ValueError, KeyError, TypeError):
        chapters, kcs, kc_rows = set(), {}, {}
        errors.append('course graph unavailable: mapping remains pending')
    external_ids = {}
    errors.extend(f"{s['id']}: {s['status']}" for s in state['sources'] if s['status'] != 'available')
    try:
        data = json.loads(candidate_path(state).read_text())
        if not isinstance(data, dict):
            raise ValueError('candidate must be an object')
        for kind in ('questions', 'diagrams'):
            if not isinstance(data.get(kind), list):
                raise ValueError(f'{kind} must be a list')
        errors.extend(_coverage(state, data))
        for kind in ('questions', 'diagrams'):
            if state['scope'] != 'both' and state['scope'] != kind and data[kind]:
                errors.append(f'{kind} is outside selected scope')
            seen = {}
            for record in data[kind]:
                before = len(errors)
                if not isinstance(record, dict):
                    errors.append(f'invalid {kind} record')
                    continue
                errors.extend(_regions(record, sources))
                if record.get('complete') is not True or not isinstance(record.get('uncertainty'), list) or record['uncertainty']:
                    errors.append('incomplete or uncertain extraction')
                valid_context = True
                for key in ('syllabus', 'kcs'):
                    if not isinstance(record.get(key), list) or not record[key] or not all(isinstance(v, str) and v.startswith(state['course'] + '-') for v in record[key]):
                        valid_context = False
                        errors.append(f'missing or wrong-course {key} mapping')
                if any(kc not in kcs or kcs[kc] not in record.get('syllabus', []) for kc in record.get('kcs', [])) or any(ch not in chapters for ch in record.get('syllabus', [])):
                    valid_context = False
                    errors.append('course graph does not validate the chapter/KC mapping')
                if kind == 'questions':
                    is_ial = state['course'] in ('P1', 'P2') or ial_namespace(record.get('official_qid'))
                    if _prepared_mode(state):
                        item=state['selected_item_scope']['records'].get(record.get('id'),{})
                        valid_identity=(record.get('official_qid')==item.get('official_qid')
                                        and record.get('part')==item.get('part'))
                    elif is_ial:
                        assessed = ial_assessed(record.get('official_qid'), record.get('part'))
                        valid_identity = assessed is not None and assessed['course'] == state['course']
                        try:
                            _validate_ial_record(state, record)
                        except (OSError, ValueError) as exc:
                            errors.append(str(exc))
                    else:
                        valid_identity = re.fullmatch(re.escape(state['course']) + r'_[msw]\d{2}_\d{2}_q\d+', str(record.get('official_qid', ''))) is not None
                    if not valid_identity:
                        errors.append('official paper/session/variant/question identity is missing')
                    valid_part = isinstance(record.get('part'), str)
                    if not valid_part:
                        errors.append('independently assessed part identity is missing')
                    if not isinstance(record.get('prerequisites'), list):
                        errors.append('prerequisite mapping is missing')
                    elif not _valid_prerequisites(record, state['course'], chapters, kcs, kc_rows, external_ids):
                        errors.append('course graph does not validate prerequisites')
                    if _prepared_mode(state):
                        for value in record.get('prerequisites',[]):
                            if isinstance(value,str) and value.split('-',1)[0]!=state['course']:
                                if value.split('-',1)[0] not in state.get('prepared_external_graphs',{}):
                                    errors.append('prepared external prerequisite requires a frozen graph version')
                    errors.extend(_regions(record, sources, 'mark_scheme_regions'))
                    errors.extend(_reference_problems(state, record))
                    if record.get('kind') not in ('mcq', 'structured') or (not _prepared_mode(state) and state['course'] not in ('9701', '9702', 'P1', 'P2')):
                        errors.append('unsupported publication format remains pending')
                    if record.get('kind') == 'structured':
                        errors.extend(_structured_problems(state, record))
                    else:
                        if record.get('answer') not in ('A', 'B', 'C', 'D'):
                            errors.append('official answer is missing')
                        if _native_mcq_partition(state, record):
                            try:
                                _publication_stem(record)
                            except ValueError as exc:
                                errors.append(str(exc))
                        if (_native_mcq_partition(state, record)
                                or any(key in record for key in ('question_media', 'mark_scheme_media'))):
                            errors.extend(_media_partition_problems(state, record))
                    if valid_identity and valid_part and valid_context:
                        identity = (record['official_qid'], record['part'], tuple(sorted(record['syllabus'])), tuple(sorted(record['kcs'])))
                        fields = {k: record.get(k) for k in ('answer', 'prerequisites', 'mark_scheme_regions',
                                                           'kind', 'stem', 'marks', 'scheme')}
                        if identity in seen:
                            errors.append('content conflict' if seen[identity] != fields else 'duplicate same-context question')
                        seen[identity] = fields
                else:
                    if any(key in record for key in ('reference_regions', 'reference_media', 'auxiliary_reference')):
                        errors.append('reference attachments are supported only on question records')
                    if not record.get('caption') or not record.get('purpose'):
                        errors.append('diagram caption/teaching purpose is missing')
                media_errors, hashes = _media(state, record)
                errors.extend(media_errors)
                image_hashes.extend(hashes)
                if kind == 'questions' and not media_errors:
                    errors.extend(_leak_gate_problems(state, record))
                if len(errors) > before:
                    errors.append(f"{kind}: {record.get('official_qid', record.get('id', 'unknown'))} remains pending")
    except (OSError, ValueError, TypeError) as exc:
        errors.append(f'candidate unavailable or invalid: {exc}')
    if not errors:
        errors.extend(_question_scope_media_problems(state, data['questions']))
    return errors, image_hashes


def check(name):
    with state_lock(name) as state:
        _verify_sources(state)
        errors, image_hashes = _candidate_problems(state)
        candidate_errors = list(errors)
        extract_job = state['jobs'].get('extract', {})
        if (candidate_errors and extract_job.get('finished') and extract_job.get('exit') == 0
                and extract_job.get('output_sha256') and candidate_path(state).is_file()
                and extract_job['output_sha256'] == digest(candidate_path(state))):
            _record_attempt_failure(state, 'extract', candidate_errors)
        if _prepared_mode(state):
            errors.extend(_prepared_receipt_problems(state))
        review_start = len(errors)
        review_bound = False
        try:
            review = json.loads((job_dir(name) / 'review.json').read_text())
            if not isinstance(review, dict):
                raise ValueError('review must be an object')
            if state['jobs'].get('review', {}).get('exit') != 0:
                errors.append('independent review task has not completed successfully')
            review_bound = review.get('candidate_sha256') == digest(candidate_path(state))
            if not review_bound:
                errors.append('review is not bound to current candidate bytes')
            if _prepared_mode(state):
                errors.extend(_prepared_review_problems(state,review,image_hashes))
            if review.get('verdict') != 'pass' or review.get('findings') != []:
                errors.append('independent review has pending findings')
            if not set(image_hashes).issubset(set(review.get('inspected_images', []))):
                errors.append('candidate images lack hash-bound visual inspection evidence')
        except (OSError, ValueError, TypeError):
            errors.append('independent review required')
        review_errors = errors[review_start:]
        review_job = state['jobs'].get('review', {})
        if review_errors and review_bound and review_job.get('finished') and review_job.get('exit') == 0:
            _record_attempt_failure(state, 'review', review_errors)
        state['problems'] = errors
        state['candidate_sha256'] = digest(candidate_path(state)) if candidate_path(state).is_file() else None
        state['teaching_approved'] = False
        transition(state, 'pending' if errors else 'reviewed', f'{len(errors)} pending findings')
    return load(name)


def register(name):
    """Register reviewed immutable bytes; never mark content teaching-approved."""
    state = check(name)
    if state['stage'] != 'reviewed':
        raise ValueError('independent review and complete validation required before registration')
    if _prepared_mode(state):
        return _register_prepared(state)
    from tutorlib.asset_library import write_asset
    from tutorlib.topicals import whole_rubric
    data, registrations, media_mapping = json.loads(candidate_path(state).read_text()), [], {}
    registered_records = {}
    review = json.loads((job_dir(name) / 'review.json').read_text())
    for kind in ('questions', 'diagrams'):
        for record in data[kind]:
            for media in _record_media(record):
                path = candidate_path(state).parent / media
                media_regions = ([record['reference_regions'][record['reference_media'].index(media)]]
                                 if media in record.get('reference_media', []) else
                                 [record['media_regions'][media]] if _native_mcq_partition(state, record) else
                                 record['mark_scheme_regions'] if kind == 'questions' and media in record.get('mark_scheme_media', [])
                                 else record['regions'])
                whole = whole_rubric(record)
                if whole is not None and media in whole['whole_rubric']['media']:
                    media_regions = record['mark_scheme_regions']
                shelf = 'Questions/Media' if kind == 'questions' else 'Diagrams'
                namepart = re.sub(r'[^A-Za-z0-9_-]', '-', path.stem)[:70]
                context = hashlib.sha256(json.dumps(record, sort_keys=True).encode()).hexdigest()[:12]
                relative = f"Library/Courses/{state['course']}/{shelf}/{namepart}-{context}-{digest(path)[:16]}{path.suffix.lower()}"
                private_media = {}
                if state['course'] == 'P2' and kind == 'questions':
                    for name in record['mark_scheme_media']:
                        private_path = candidate_path(state).parent / name
                        private_stem = re.sub(r'[^A-Za-z0-9_-]', '-', private_path.stem)[:70]
                        private_media[name] = (f"Library/Courses/P2/Questions/Media/{private_stem}-"
                                               f"{context}-{digest(private_path)[:16]}{private_path.suffix.lower()}")
                sidecar = write_asset(library.learner_vault(), relative + '.json',
                                     json.dumps({'extraction_job': state['name'], 'record': record,
                                                 **({'private_media': private_media} if state['course'] == 'P2' and kind == 'questions' else {}),
                                                 'sha256': digest(path), 'course': state['course'],
                                                 'subtopics': record['syllabus'], 'kcs': record['kcs'],
                                                 'caption': record.get('caption', ''), 'why': record.get('purpose', ''),
                                                 'pdf': media_regions[0]['source_id'],
                                                 'page': media_regions[0]['page'], 'box': media_regions[0]['box'],
                                                 'source_sha256': media_regions[0]['source_sha256'],
                                                 'regions': media_regions,
                                                 'review': review, 'source_inventory': state['sources'],
                                                 'teaching_approved': False}, ensure_ascii=False).encode(),
                                     metadata={'course': state['course'], 'kind': 'Sources/Provenance'})
                reference = write_asset(library.learner_vault(), relative, path.read_bytes(),
                                                  metadata={'course': state['course'], 'kind': shelf,
                                                            'provenance': {'sidecars': [sidecar]}})
                registrations.append(reference)
                media_mapping[media] = relative
                registered_records.setdefault(context, {})[media] = relative
    with state_lock(state['name']) as current:
        current['registrations'] = registrations
        current['registered_media'] = media_mapping
        current['registered_records'] = registered_records
        current['registered_candidate_sha256'] = state['candidate_sha256']
        transition(current, 'registered', 'Registration is availability, not teaching approval; publication is explicit.')
    return load(state['name'])


def _register_prepared(state):
    """Issue one immutable group attestation after every reviewed resource exists."""
    from tutorlib.asset_library import write_asset, AssetLibrary
    from tutorlib.prepared_evidence import canonical_bytes, sha, PROFILE
    descriptor = _verify_prepared(state)
    vault, course, name = library.learner_vault(), state['course'], state['name']
    candidate_raw = candidate_path(state).read_bytes()
    review_raw = (job_dir(name) / 'review.json').read_bytes()
    candidate, review = json.loads(candidate_raw), json.loads(review_raw)

    def snapshot(raw, owner=course):
        relative = f'Library/Courses/{owner}/Sources/Provenance/prepared-evidence-v1/{sha(raw)}.json'
        write_asset(vault, relative, raw, metadata={'course': owner, 'kind': 'Sources/Provenance'})
        return {'reference': relative, 'sha256': sha(raw)}

    frozen = Path(state['prepared_input'])
    pins = {field: snapshot(raw) for field, raw in {
        'candidate': candidate_raw, 'review': review_raw,
        **{field: (frozen / filename).read_bytes() for field, filename in
           [('descriptor', 'descriptor.json'), ('seed', 'seed.json'), ('complete', 'COMPLETE')]}}.items()}
    graph_path = Path(os.environ.get('STEM_LIBRARY_SPECS') or REPO / 'build/out/specs') / course / 'graph.json'
    pins['graph'] = snapshot(candidates.verified_bytes(graph_path))
    if pins['graph']['sha256'] != state['prepared_scope']['graph_sha256']:
        raise ValueError('prepared graph changed during registration')
    external = {}
    for target, pin in state.get('prepared_external_graphs', {}).items():
        path = graph_path.parent.parent / target / 'graph.json'
        external[target] = snapshot(candidates.verified_bytes(path), target)
        if external[target]['sha256'] != pin['sha256']:
            raise ValueError('prepared external graph changed during registration')
    receipts = [next(r for r in state['prepared_attempt_receipts']
                     if r['attempt_id'] == state['jobs'][role]['attempt_id']) for role in ('extract', 'review')]
    prompts = {role: snapshot((job_dir(name) / f'{role}.prompt.txt').read_bytes()) for role in ('extract', 'review')}
    registrations, registered, media_pins = [], {}, {}
    for row in candidate['questions']:
        context = sha(json.dumps(row, sort_keys=True).encode())[:12]
        mapping, bound = {}, {}
        for local in _record_media(row):
            path = candidate_path(state).parent / local
            media = descriptor['media'][local]
            raw = candidates.verified_bytes(path)
            if sha(raw) != media['sha256']:
                raise ValueError('prepared media changed during registration')
            stem = re.sub(r'[^A-Za-z0-9_-]', '-', path.stem)[:70]
            relative = f'Library/Courses/{course}/Questions/Media/{stem}-{context}-{sha(raw)[:16]}{path.suffix.lower()}'
            sidecar_raw = canonical_bytes({'extraction_job': name, 'course': course, 'record': row,
                'prepared_scope': state['prepared_scope'], 'media_name': local, 'visibility': media['visibility'],
                'sha256': sha(raw), 'regions': [media['region']], 'review': review, 'teaching_approved': False})
            sidecar = snapshot(sidecar_raw)
            reference = write_asset(vault, relative, raw, metadata={'course': course, 'kind': 'Questions/Media',
                                    'provenance': {'sidecars': [sidecar['reference']]}})
            registrations.append(reference); mapping[local] = relative
            bound[local] = {'reference': relative, 'sidecar': sidecar}
        registered[context], media_pins[context] = mapping, bound
    catalog = AssetLibrary(vault)
    attestation = {'schema_version': 1, 'profile': PROFILE, 'course': course, 'teaching_approved': False,
        'extraction_job': name, 'prepared_scope': state['prepared_scope'],
        'selected_item_scope': state['selected_item_scope'], 'source_inventory': state['sources'],
        'manager_receipts': receipts, 'prompts': prompts, 'external_graphs': external, 'media': media_pins,
        'source_catalog': {identifier: {key: catalog.record(identifier).get(key)
                           for key in ('path', 'sha256', 'course', 'kind', 'provenance')}
                           for identifier in {r['asset_id'] for r in descriptor['required_asset_pages']}}, **pins}
    raw = canonical_bytes(attestation)
    relative = f'Library/Courses/{course}/Sources/Provenance/prepared-v1/{sha(raw)}.json'
    write_asset(vault, relative, raw, metadata={'course': course, 'kind': 'Sources/Provenance'})
    marker = {'profile': PROFILE, 'attestation_ref': relative, 'attestation_sha256': sha(raw)}
    from tutorlib.prepared_evidence import _load_attestation, _VerifiedLibrary
    _load_attestation(marker, _VerifiedLibrary(AssetLibrary(vault)))
    with state_lock(name) as current:
        if (current['candidate_sha256'] != state['candidate_sha256']
                or current.get('prepared_scope') != state['prepared_scope']
                or any(current['jobs'][role].get('attempt_id') != state['jobs'][role]['attempt_id']
                       for role in ('extract', 'review'))
                or _prepared_receipt_problems(current)
                or digest(candidate_path(current)) != pins['candidate']['sha256']
                or digest(job_dir(name) / 'review.json') != pins['review']['sha256']):
            raise ValueError('prepared review changed during registration')
        current.update(registrations=registrations, registered_records=registered,
                       registered_media={n: ref for mapping in registered.values() for n, ref in mapping.items()},
                       registered_candidate_sha256=state['candidate_sha256'], prepared_admission=marker)
        transition(current, 'registered', 'Immutable prepared group available; teaching approval is separate.')
    return load(name)


def _active_topical_bank(vault):
    """Read and validate the exact active bank, without changing its pointer."""
    from tutorlib.asset_library import AssetLibrary
    from tutorlib.packs import Packs
    from tutorlib.store import Vault
    from tutorlib.topicals import validate_bank
    vault = Path(vault)
    pointer = vault / '.tutor/topicals/CURRENT'
    if not pointer.exists():
        return None, None, {'items': [], 'syllabus_versions': {}}
    version = pointer.read_text().strip()
    if not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_.-]*', version) or version in ('.', '..'):
        raise ValueError('invalid topical CURRENT pointer')
    canonical = f'Library/Shared/Topicals/Releases/{version}/bank.json'
    target = vault / canonical
    if target.exists() or target.is_symlink():
        raw = AssetLibrary(vault).read(canonical)
    else:
        target = vault / '.tutor/topicals' / version / 'bank.json'
        if not target.resolve().is_relative_to(vault.resolve()):
            raise ValueError('unsafe existing topical bank')
        raw = target.read_bytes()
    data = json.loads(raw)
    validate_bank(data, Packs(Vault(vault)), vault)
    return version, hashlib.sha256(raw).hexdigest(), data


def _reviewed_runtime_requirements(record, graph, packs):
    """Resolve reviewed dependencies through graph facts and the active runtime."""
    kcs = {row['id']: row for row in graph['kcs']}
    chapters = {row['id'] for row in graph['subtopics']}
    declared = {value for identifier in record['kcs'] for value in kcs[identifier].get('prereqs', [])}
    requirements, versions, targets = list(record['syllabus']), {}, {}
    for value in record['prerequisites']:
        if value in kcs or value in chapters:
            requirements.append(kcs[value]['subtopic'] if value in kcs else value)
            continue
        target = value.split('-', 1)[0]
        if value not in declared:
            raise ValueError('external prerequisite is not declared by a reviewed assessed KC')
        if target not in targets:
            authority = _course_graph(target)
            nodes, parents = _graph_indexes(authority, target)
            if authority.get('version') != packs.syllabus_versions.get(target) or not authority.get('version'):
                raise ValueError('external prerequisite runtime graph version differs from registered authority')
            targets[target] = nodes, parents, authority['version']
        nodes, parents, version = targets[target]
        parent = nodes[value]['subtopic'] if value in nodes else value
        runtime = packs.subtopics.get(parent, {})
        if (parent not in parents or runtime.get('spec') != target
                or value in nodes and (packs.kcs.get(value, {}).get('subtopic') != parent
                                       or packs.kcs.get(value, {}).get('spec') != target)):
            raise ValueError('external prerequisite target is unknown or differs from runtime graph')
        requirements.append(parent)
        versions[target] = version
    return list(dict.fromkeys(requirements)), versions


def _publication_scheme(record, registered):
    """Only reviewed private filenames may change in a published rubric."""
    import copy
    from tutorlib.topicals import whole_rubric
    scheme = copy.deepcopy(record['scheme'])
    entry = whole_rubric(record)
    if entry is not None:
        names = entry['whole_rubric']['media']
        if any(name not in record.get('mark_scheme_media', [])
               or name not in record.get('media', []) or not registered.get(name) for name in names):
            raise ValueError('whole-rubric media lacks reviewed private registration')
        scheme[0]['whole_rubric']['media'] = [registered[name] for name in names]
    return scheme


def _publication_stem(row):
    """Map reviewed MCQ text only when no explicit stem was supplied."""
    if row['kind'] != 'mcq':
        return row.get('stem')
    field = 'stem' if 'stem' in row else 'text'
    value = row.get(field)
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f'reviewed MCQ {field} must be a nonempty string')
    return value


def prepare_publication(name, output):
    """Prepare an additive batch from reviewed bytes; never register or activate it."""
    from tutorlib.packs import Packs
    from tutorlib.store import Vault
    from tutorlib.topicals import identity, validate_bank
    state = check(name)
    if (state['stage'] != 'reviewed' or not state.get('registrations')
            or state.get('registered_candidate_sha256') != state['candidate_sha256']):
        raise ValueError('current independent review and registration required before preparation')
    output = Path(output).resolve()
    if output.exists():
        raise ValueError('publication preparation requires a fresh output directory')
    vault = library.learner_vault()
    if output.is_relative_to(vault.resolve()):
        raise ValueError('publication preparation belongs outside the learner vault')
    version, prior_hash, prior = _active_topical_bank(vault)
    packs = Packs(Vault(vault))
    rows = json.loads(candidate_path(state).read_text())['questions']
    if not rows:
        raise ValueError('publication preparation requires reviewed questions')
    bank = {'format_version': 1, 'syllabus_versions': dict(prior['syllabus_versions']),
            'items': list(prior['items'])}
    seen = {identity(item) for item in bank['items']}
    graph = _course_graph(state['course'])
    for row in rows:
        if _prepared_mode(state):
            if not state.get('prepared_admission'):
                raise ValueError('prepared group lacks immutable registration attestation')
            from tutorlib.prepared_evidence import project_bank_item
            context = hashlib.sha256(json.dumps(row, sort_keys=True).encode()).hexdigest()[:12]
            item = project_bank_item(row, state['registered_records'][context], state['course'], name,
                                     state['candidate_sha256'], graph,
                                     {c: _course_graph(c) for c in state.get('prepared_external_graphs', {})},
                                     state.get('prepared_admission'))
            if identity(item) in seen:
                raise ValueError('canonical question/part already active; resolve reuse/conflict')
            seen.add(identity(item)); bank['items'].append(item)
            bank['syllabus_versions'].update(item['topical'].get('prerequisite_versions', {}))
            continue
        context = hashlib.sha256(json.dumps(row, sort_keys=True).encode()).hexdigest()[:12]
        registered = state.get('registered_records', {}).get(context, {})
        media = _learner_media(row)
        requires, prerequisite_versions = _reviewed_runtime_requirements(row, graph, packs)
        item = {key: row[key] for key in ('kind', 'answer', 'kcs')}
        item.update(id='extracted-' + row['official_qid'] + '-' + context,
                    stem=_publication_stem(row), marks=row.get('marks', 1), difficulty=row.get('difficulty', 3),
                    images=[registered.get(name) for name in media],
                    source={'type': 'past', 'qid': row['official_qid'], 'part': row['part'],
                            'extraction_regions': row['regions'], 'mark_scheme_regions': row['mark_scheme_regions'],
                            'extraction_prerequisites': row['prerequisites'],
                            **({'reference_regions': row['reference_regions']} if row.get('reference_regions') else {}),
                            'extraction_job': name, 'candidate_sha256': state['candidate_sha256']},
                    topical={'reviewed': True, 'chapters': row['syllabus'],
                             'requires': requires,
                             'support': {}, 'revision': packs.syllabus_versions[state['course']],
                             **({'prerequisite_versions': prerequisite_versions} if prerequisite_versions else {})})
        if row['kind'] == 'structured':
            item['scheme'] = _publication_scheme(row, registered)
        else:
            item['options'] = row.get('options', {})
        if identity(item) in seen:
            raise ValueError('canonical question/part already active; reuse its ID or resolve the assessed-context conflict explicitly')
        seen.add(identity(item))
        bank['items'].append(item)
        bank['syllabus_versions'].update(prerequisite_versions)
    bank['syllabus_versions'][state['course']] = packs.syllabus_versions[state['course']]
    validate_bank(bank, packs, vault)
    report = {'preparation': {'expected_current': version}, 'extraction': {
        'job': name, 'candidate_sha256': state['candidate_sha256'],
        'review_sha256': digest(job_dir(name) / 'review.json'), 'previous_bank_sha256': prior_hash,
        'preserved_items': len(prior['items']), 'added_items': len(rows)}}
    output.mkdir(parents=True)
    (output / 'bank.json').write_text(json.dumps(bank, ensure_ascii=False, indent=1))
    (output / 'report.json').write_text(json.dumps(report, ensure_ascii=False, indent=1))
    return {'output': str(output), **report}


def publish(name, batch):
    state = check(name)
    if state['stage'] != 'reviewed' or not state.get('registrations'):
        raise ValueError('review and registration required before explicit topical publication')
    if (not _prepared_mode(state) and state['course'] not in ('9701', '9702', 'P1', 'P2')) or state['scope'] == 'diagrams':
        raise ValueError('unsupported question publication format remains pending')
    if state.get('registered_candidate_sha256') != state['candidate_sha256']:
        raise ValueError('registration is not bound to the current reviewed candidate')
    bank_raw = (Path(batch) / 'bank.json').read_bytes()
    bank = json.loads(bank_raw.decode('utf-8'))
    report_raw = (Path(batch) / 'report.json').read_bytes() if _prepared_mode(state) else None
    report = json.loads(report_raw.decode('utf-8')) if report_raw is not None else None
    version, prior_hash, prior = _active_topical_bank(library.learner_vault())
    items = bank.get('items', [])
    if prior['items']:
        if report_raw is None:
            report = json.loads((Path(batch) / 'report.json').read_text())
        if (report.get('preparation', {}).get('expected_current') != version
                or report.get('extraction', {}).get('previous_bank_sha256') != prior_hash):
            raise ValueError('publication preparation is not bound to the existing active bank')
        old_ids = {item['id'] for item in prior['items']}
        from tutorlib.prepared_evidence import canonical_bytes
        if canonical_bytes([item for item in items if item.get('id') in old_ids]) != canonical_bytes(prior['items']):
            raise ValueError('publication must preserve every existing active question and ID unchanged')
        items = [item for item in items if item.get('id') not in old_ids]
    if _prepared_mode(state):
        from tutorlib.packs import Packs
        from tutorlib.store import Vault
        from tutorlib.topicals import validate_bank
        expected_report = {'job': name, 'candidate_sha256': state['candidate_sha256'],
                           'review_sha256': digest(job_dir(name) / 'review.json'),
                           'previous_bank_sha256': prior_hash, 'preserved_items': len(prior['items']),
                           'added_items': len(json.loads(candidate_path(state).read_text())['questions'])}
        if (report.get('preparation', {}).get('expected_current') != version
                or report.get('extraction') != expected_report or not items
                or any(i.get('source', {}).get('prepared_admission') != state.get('prepared_admission') for i in items)):
            raise ValueError('prepared publication requires current review, registration and bank bindings')
        validate_bank(bank, Packs(Vault(library.learner_vault())), library.learner_vault())
        import topicals
        with state_lock(name) as current:
            if (current.get('prepared_scope') != state['prepared_scope']
                    or current.get('prepared_admission') != state['prepared_admission']
                    or current.get('candidate_sha256') != state['candidate_sha256']
                    or any(current['jobs'][role].get('attempt_id') != state['jobs'][role]['attempt_id']
                           for role in ('extract', 'review'))
                    or _prepared_receipt_problems(current)):
                raise ValueError('prepared current manager review changed during publication')
            # Serialize new role issuance with the independent importer and its CURRENT CAS.
            result = topicals.publish(Path(batch), library.learner_vault(), expected_current=version,
                                      expected_bank_sha256=hashlib.sha256(bank_raw).hexdigest(),
                                      expected_report_sha256=hashlib.sha256(report_raw).hexdigest())
            current['publication'] = result
            transition(current, 'published')
        return result
    data = json.loads(candidate_path(state).read_text())
    from collections import Counter
    def identity(qid, part, chapters, kcs):
        return qid, part, tuple(sorted(chapters)), tuple(sorted(kcs))
    expected = {identity(row['official_qid'], row['part'], row['syllabus'], row['kcs']): row
                for row in data['questions']}
    def bank_identity(item):
        source = item.get('source', {})
        return identity(source.get('qid'), source.get('part', ''),
                        item.get('topical', {}).get('chapters', []), item.get('kcs', []))
    if not items or Counter(bank_identity(item) for item in items) != Counter(expected.keys()):
        raise ValueError('topical batch must contain exactly every reviewed question part/context (a bijection)')
    graph = _course_graph(state['course'])
    from tutorlib.packs import Packs
    from tutorlib.store import Vault
    local_ids = {row['id'] for key in ('kcs', 'subtopics') for row in graph[key]}
    has_external = any(value not in local_ids for row in expected.values() for value in row['prerequisites'])
    packs = Packs(Vault(library.learner_vault())) if has_external else None
    for item in items:
        original = expected[bank_identity(item)]
        primary, pages = item.get('image'), item.get('images')
        if pages is not None and not isinstance(pages, list):
            raise ValueError('topical media pages must be an ordered list')
        # saved_figures.prepare_question displays images when populated, otherwise
        # image. A primary image aliases the first page rather than adding a page.
        images = pages or ([primary] if primary else [])
        if primary and (not images or images[0] != primary):
            raise ValueError('topical primary media differs from the first ordered page')
        context = hashlib.sha256(json.dumps(original, sort_keys=True).encode()).hexdigest()[:12]
        registered = state.get('registered_records', {}).get(context, {})
        question_media = _learner_media(original)
        required = [registered.get(media) for media in question_media]
        if item.get('answer') != original['answer'] or item.get('kcs') != original['kcs'] or images != required:
            raise ValueError('topical batch differs from reviewed answers, KC mapping or registered media')
        if original['kind'] == 'structured' and (any(item.get(key) != original[key]
                                                   for key in ('kind', 'stem', 'marks'))
                or item.get('scheme') != _publication_scheme(original, registered)):
            raise ValueError('topical batch differs from reviewed structured stem, kind, marks or marking scheme')
        if original['kind'] == 'mcq' and item.get('stem') != _publication_stem(original):
            raise ValueError('topical batch differs from reviewed MCQ stem')
        requires, prerequisite_versions = _reviewed_runtime_requirements(original, graph, packs)
        if (item.get('topical', {}).get('requires') != requires
                or item.get('topical', {}).get('prerequisite_versions', {}) != prerequisite_versions
                or any(bank.get('syllabus_versions', {}).get(course) != version for course, version in prerequisite_versions.items())
                or item.get('topical', {}).get('support') != {}):
            raise ValueError('topical batch differs from reviewed runtime prerequisites or adds unreviewed support')
        source = item['source']
        if state['course'] in ('P1', 'P2') or ial_namespace(source.get('qid')):
            from tutorlib.asset_library import AssetLibrary
            validate_ial_sources(source.get('qid'), source.get('part'), state['course'],
                                source.get('extraction_regions'), source.get('mark_scheme_regions'),
                                AssetLibrary(library.learner_vault()))
        if (source.get('extraction_regions') != original['regions']
                or source.get('mark_scheme_regions') != original['mark_scheme_regions']
                or source.get('extraction_prerequisites') != original['prerequisites']
                or source.get('reference_regions', []) != original.get('reference_regions', [])):
            raise ValueError('topical source regions, mark-scheme regions and prerequisites must preserve every reviewed mapping')
    import topicals
    # This importer independently enforces official-key, mapping and review gates.
    result = topicals.publish(Path(batch), library.learner_vault())
    with state_lock(name) as current:
        current['publication'] = result
        transition(current, 'published')
    return result


def crop(name, source_id, page, box, output, dpi=160):
    state = load(name)
    _verify_sources(state)
    source = next((s for s in state['sources'] if s['id'] == source_id), None)
    if not source:
        raise ValueError('source is outside this job inventory')
    if (_initial_native_mode(state) or _prepared_mode(state)) and (type(page) is not int or page not in source['selected_page_numbers']):
        raise ValueError('crop page is outside the selected fresh P1 source pages')
    if _prepared_mode(state):
        raise ValueError('prepared media corrections require a fresh preserved preparation revision and review')
    root = candidate_path(state).parent.resolve()
    path = (root / output).resolve()
    if not path.is_relative_to(root) or path.suffix.lower() != '.png' or path.exists():
        raise ValueError('crop requires a new PNG inside the candidate directory')
    box = library.parse_box(box)
    Image, _ = library._pil()
    with Image.open(library.render(Path(source['path']), page, dpi)) as full:
        image = library.cut(full, box)
        path.parent.mkdir(parents=True, exist_ok=True)
        image.save(path)
    return {'media': output, 'sha256': digest(path), 'source_id': source_id,
            'source_sha256': source['sha256'], 'page': page, 'box': box}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='command', required=True)
    new = sub.add_parser('new')
    new.add_argument('job'); new.add_argument('--course', required=True)
    new.add_argument('--provider', choices=('claude', 'codex', 'both'), default='claude')
    new.add_argument('--scope', choices=('questions', 'diagrams', 'both'), default='both')
    new.add_argument('--source', action='append', default=[])
    new.add_argument('--pages')
    new.add_argument('--prepared-scope', type=Path, help='Fresh verified native preparation package; exclusive of other selectors')
    new.add_argument('--official-qid', help='Exact fresh native P1 whole-question pilot identity')
    new.add_argument('--source-pages', action='append', metavar='asset:ID=PAGES',
                     help='Paired fresh-P1 per-source page selection; cannot combine with --source/--pages')
    new.add_argument('--codex-model', help='Persist a job-local Codex model choice for extraction and review')
    new.add_argument('--codex-effort', choices=('low', 'medium', 'high', 'xhigh'))
    new.add_argument('--codex-stop-remaining', type=float,
                     help='Explicit job-local Codex stopping boundary (1 to below 100 percent remaining)')
    settings = sub.add_parser('configure', help='Audit authorized job-local settings without resetting stages or guards')
    settings.add_argument('job')
    settings.add_argument('--reason', required=True)
    settings.add_argument('--codex-stop-remaining', type=float)
    for role in ('extract', 'review'):
        settings.add_argument(f'--codex-{role}-model')
        settings.add_argument(f'--codex-{role}-effort', choices=('low', 'medium', 'high', 'xhigh'))
    for command in ('inventory', 'plan', 'resume', 'check', 'register'):
        sub.add_parser(command).add_argument('job')
    focusing = sub.add_parser('focus', help='Reuse a saved whole question in a fresh scoped revision without clearing guards')
    focusing.add_argument('job'); focusing.add_argument('--official-qid', required=True)
    focusing.add_argument('--reason', required=True)
    focusing.add_argument('--stage-missing-scheme', action='store_true',
                          help='Explicit staging only: retain empty historical MS regions pending native repair/review')
    advancing = sub.add_parser('next-question', help='Archive a published scope and reuse another original maker question without resetting guards')
    advancing.add_argument('job'); advancing.add_argument('--official-qid', required=True)
    advancing.add_argument('--reason', required=True)
    advancing.add_argument('--stage-missing-scheme', action='store_true',
                           help='Explicit staging only: retain empty historical MS regions pending native repair/review')
    native = sub.add_parser('evidence-sources', help='Stage exact native source evidence for a focused repair, preserving provenance and guards')
    native.add_argument('job'); native.add_argument('--source-pages', action='append', required=True, metavar='asset:ID=PAGES')
    native.add_argument('--reason', required=True)
    reference = sub.add_parser('reference-sources', help='Append explicitly auxiliary native references before the first native repair')
    reference.add_argument('job'); reference.add_argument('--source-pages', action='append', required=True, metavar='asset:ID=PAGES')
    reference.add_argument('--purpose', required=True); reference.add_argument('--reason', required=True)
    graph_reader = sub.add_parser('graph')
    graph_reader.add_argument('job')
    selector = graph_reader.add_mutually_exclusive_group(required=True)
    selector.add_argument('--id', dest='kc_id')
    selector.add_argument('--query')
    graph_reader.add_argument('--limit', type=int, default=8)
    for command in ('enable-ocr', 'ocr-text'):
        reader = sub.add_parser(command)
        reader.add_argument('job'); reader.add_argument('--source', required=True)
        if command == 'ocr-text':
            reader.add_argument('--pages')
    clearing = sub.add_parser('unstick'); clearing.add_argument('job'); clearing.add_argument('reason')
    running = sub.add_parser('run'); running.add_argument('job')
    running.add_argument('--weekly-remaining', type=float)
    running.add_argument('--wait', action='store_true')
    running.add_argument('--retry', choices=('extract', 'review'))
    sub.add_parser('board')
    leak = sub.add_parser('leaks', help='Run the question-media leak gate (plan only unless --apply)')
    leak.add_argument('job', nargs='?'); leak.add_argument('--vault', type=Path); leak.add_argument('--courses')
    leak.add_argument('--out', type=Path); leak.add_argument('--apply', action='store_true')
    publication = sub.add_parser('publish'); publication.add_argument('job'); publication.add_argument('--topical-batch', required=True)
    preparation = sub.add_parser('prepare-publication'); preparation.add_argument('job')
    preparation.add_argument('--output', required=True, type=Path)
    native_preparation = sub.add_parser('prepare-native', help='Prepare a source-bound native Pearson proposal offline')
    native_preparation.add_argument('--request', required=True, type=Path)
    native_preparation.add_argument('--output', required=True, type=Path)
    clipping = sub.add_parser('crop'); clipping.add_argument('job'); clipping.add_argument('--source', required=True)
    clipping.add_argument('--page', type=int, required=True); clipping.add_argument('--box', required=True)
    clipping.add_argument('--output', required=True); clipping.add_argument('--dpi', type=int, default=160)
    worker = sub.add_parser('_worker'); worker.add_argument('job'); worker.add_argument('role')
    install = sub.add_parser('install-skill'); install.add_argument('--to', type=Path, default=Path.home() / '.claude/skills/extract')
    args = parser.parse_args(argv)
    try:
        if args.command == 'new': result = create(args.job, args.course, args.provider, args.scope, args.source, args.pages,
                                                args.codex_model, args.codex_effort, args.codex_stop_remaining,
                                                official_qid=args.official_qid, source_pages=args.source_pages, prepared_scope=args.prepared_scope)
        elif args.command == 'configure':
            roles = {role: {key: value for key in ('model', 'effort')
                            if (value := getattr(args, f'codex_{role}_{key}')) is not None}
                     for role in ('extract', 'review')}
            result = configure(args.job, args.reason, codex_stop_remaining=args.codex_stop_remaining,
                               codex_role_overrides={role: choices for role, choices in roles.items() if choices})
        elif args.command == 'focus': result = focus(args.job, args.official_qid, args.reason, stage_missing_scheme=args.stage_missing_scheme)
        elif args.command == 'next-question': result = next_question(args.job, args.official_qid, args.reason, stage_missing_scheme=args.stage_missing_scheme)
        elif args.command == 'evidence-sources': result = evidence_sources(args.job, args.source_pages, args.reason)
        elif args.command == 'reference-sources': result = reference_sources(args.job, args.source_pages, args.purpose, args.reason)
        elif args.command == 'resume': result = resume(args.job)
        elif args.command == 'graph': result = graph(args.job, kc_id=args.kc_id, query=args.query, limit=args.limit)
        elif args.command == 'enable-ocr': result = enable_ocr(args.job, args.source)
        elif args.command == 'ocr-text': result = ocr_text(args.job, args.source, args.pages)
        elif args.command == 'board':
            result = [json.loads(path.read_text()) for path in sorted((work_root() / 'Workers/extraction').glob('*/state.json'))]
        elif args.command == 'leaks': result = leaks(args.job, args.vault, args.courses, args.out, args.apply)
        elif args.command == 'run': result = run(args.job, args.weekly_remaining, args.wait, args.retry)
        elif args.command == 'unstick':
            with state_lock(args.job) as state:
                if any(process_alive(j.get('pid')) and not j.get('finished') for j in state.get('jobs', {}).values()):
                    raise ValueError('cannot clear failures while a worker is running')
                reliability.clear_failures(state, args.reason)
                result = state
        elif args.command == '_worker': return _worker(args.job, args.role)
        elif args.command == 'publish': result = publish(args.job, args.topical_batch)
        elif args.command == 'prepare-publication': result = prepare_publication(args.job, args.output)
        elif args.command == 'prepare-native':
            from prepared_scope import prepare_native
            from tutorlib.asset_library import AssetLibrary
            request = json.loads(args.request.read_bytes())
            _, graph_sha256 = _course_graph_input(request.get('course'))
            result = prepare_native(args.request, args.output, AssetLibrary(library.learner_vault()), graph_sha256)
        elif args.command == 'crop': result = crop(args.job, args.source, args.page, args.box, args.output, args.dpi)
        elif args.command == 'install-skill':
            args.to.mkdir(parents=True, exist_ok=True)
            target = args.to / 'SKILL.md'
            target.write_text((REPO / 'extraction/skill/SKILL.md').read_text().replace('{REPO}', str(REPO)))
            result = {'installed': str(target)}
        else: result = globals()[args.command](args.job)
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0
    except (ValueError, OSError, library.Fail) as exc:
        print(str(exc), file=sys.stderr)
        return 1


if __name__ == '__main__':
    sys.exit(main())
