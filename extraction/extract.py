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
import subprocess
import sys
import uuid

REPO = Path(__file__).resolve().parents[1]
for directory in ('build', 'src', 'foundry'):
    sys.path.insert(0, str(REPO / directory))
import library
import router
from tutor_workers.lifecycle import process_alive, timestamp, transition
from tutor_workers import candidates, reliability, source_ocr, timeout as worker_timeout


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
    if type(value) not in (int, float) or not 20 <= value < 100:
        raise ValueError('Codex stop remaining must be a percentage from 20 up to 100 (exclusive)')
    return float(value)


def create(name, course, provider='claude', scope='both', sources=None, pages=None,
           codex_model=None, codex_effort=None, codex_stop_remaining=None):
    if provider not in ('claude', 'codex', 'both') or scope not in ('questions', 'diagrams', 'both'):
        raise ValueError('unknown provider or scope')
    if not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_-]*', course):
        raise ValueError('invalid course')
    if codex_stop_remaining is not None:
        codex_stop_remaining = _codex_stop_remaining(codex_stop_remaining)
    with state_lock(name) as state:
        if state:
            raise ValueError('job exists: use resume, inventory, plan, run or check')
        state.update(name=name, course=course, provider=provider, scope=scope, stage='new',
                     created=timestamp(), history=[], jobs={}, sources=[], teaching_approved=False,
                     requested_sources=list(sources or []), requested_pages=pages,
                     candidate=str(work_root() / 'Candidates/extraction' / name / 'candidate.json'))
        if codex_model:
            state['codex_model'] = codex_model
        if codex_effort:
            state['codex_effort'] = codex_effort
        if codex_stop_remaining is not None:
            state['codex_stop_remaining'] = codex_stop_remaining
    return load(name)


def _verify_sources(state):
    selected_paths = {source['path'] for source in state['sources']}
    available = {str(path): path for _, path in library.source_files('all', state['course'], references=selected_paths)}
    for source in state['sources']:
        if source['path'] not in available or digest(source['path']) != source['sha256']:
            raise ValueError(f"source changed or is unavailable: {source['path']}; inventory a fresh job")
        if source.get('ocr'):
            source_ocr.read(source, ocr_cache_root())


def enable_ocr(name, source_id):
    """Explicitly freeze unreviewed native OCR inputs before a job is planned."""
    with state_lock(name) as state:
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
    result = source_ocr.read(source, ocr_cache_root(), selected)
    for page in result['pages']:
        lines = page.pop('lines')
        page['line_count'] = len(lines)
        page['minimum_line_confidence'] = min((line['confidence'] for line in lines), default=None)
    return result


def inventory(name):
    with state_lock(name) as state:
        if state.get('jobs'):
            raise ValueError('planned job inventory is frozen; create a fresh job for different sources')
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
        if state['jobs']:
            return state
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


def _prompt(state, role):
    contract = (REPO / 'extraction/roles' / f'{role}.md').read_text()
    sources = []
    for source in state['sources']:
        start, end = source.get('selected_pages') or (1, source['pages'])
        sources.append({**{k: v for k, v in source.items() if k != 'selected_pages'},
                        'selected_page_range': {'start': start, 'end': end, 'inclusive': True}})
    return contract + '\nJOB CONTRACT:\n' + json.dumps({
        'course': state['course'], 'scope': state['scope'], 'sources': sources,
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
        **({'previous_candidate': state.get('previous_candidate'), 'pending_findings': state.get('problems', [])} if role == 'extract' else {}),
    }, ensure_ascii=False, indent=2)


def worker_command(state, role):
    provider = state['jobs'][role]['provider']
    cfg = json.loads((REPO / 'foundry/config.json').read_text())
    model, effort = cfg['ladders']['drafter' if role == 'extract' else 'checker'][provider][0]
    if provider == 'codex':
        model = state.get('codex_model') or model
        effort = state.get('codex_effort') or effort
    binary = os.environ.get('STEM_EXTRACT_' + provider.upper()) or shutil.which(provider)
    if not binary:
        raise ValueError(f'{provider} CLI unavailable; selected provider is never silently replaced')
    prompt = _prompt(state, role)
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
            candidate_errors, _ = _candidate_problems(state)
            if candidate_errors:
                raise ValueError('candidate validation failed before review: ' + '; '.join(candidate_errors))
        import capabilities
        if why := capabilities.preflight():
            raise ValueError(why)
        launch_fingerprint = reliability.fingerprint(state, role, inputs)
        selected_pages = sum((s.get('selected_pages') or [1, s['pages']])[-1] - (s.get('selected_pages') or [1, s['pages']])[0] + 1 for s in state['sources'])
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
        output = _output(state, role)
        output.parent.mkdir(parents=True, exist_ok=True)
        # A retry cannot inherit a stale successful candidate/review.
        if output.exists():
            previous = output.with_name(output.name + '.' + uuid.uuid4().hex + '.previous')
            output.rename(previous)
            if role == 'extract':
                state['previous_candidate'] = str(previous)
                state['jobs']['review'] = {'provider': state['jobs']['review']['provider']}
        command = worker_command(state, role)
        (job_dir(name) / f'{role}.prompt.txt').write_text(_prompt(state, role))
        state['jobs'][role].update(started=timestamp(), finished=None, exit=None,
                                  failure_recorded=False,
                                  failure_input=launch_fingerprint,
                                  weekly_remaining=weekly_remaining, weekly_read_at=timestamp())
        state['jobs'][role]['command'] = command[:-1]  # prompt stored separately, no global router writes
        log = job_dir(name) / f'{role}.log'
        state['jobs'][role]['log'] = str(log)
        transition(state, 'extracting' if role == 'extract' else 'reviewing')
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
    output = _output(state, role)
    environment = {**os.environ, 'EXTRACT_OUTPUT': str(output), 'EXTRACT_ROLE': role,
                   'STEM_LIBRARY_CACHE': str(job_dir(name) / 'reader-cache'),
                   'CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC': '1'}
    issues = []
    output_sha256 = None
    try:
        _verify_sources(state)
        result = worker_timeout.run_captured(worker_command(state, role), cwd=REPO, env=environment,
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
        output_sha256 = digest(output) if output.is_file() else None
        if code == 0:
            data = json.loads(output.read_text())
            if not isinstance(data, dict):
                raise ValueError('worker output must be a JSON object')
            if role == 'extract' and any(not isinstance(data.get(key), list) for key in ('questions', 'diagrams')):
                raise ValueError('candidate requires questions and diagrams lists')
            if role == 'extract' and (coverage_errors := _coverage(state, data)):
                raise ValueError('; '.join(coverage_errors))
            if role == 'review' and (data.get('verdict') not in ('pass', 'pending')
                    or not isinstance(data.get('findings'), list)
                    or not isinstance(data.get('inspected_images'), list)
                    or any(not isinstance(value, str) for value in data.get('inspected_images', []))
                    or data.get('candidate_sha256') != digest(candidate_path(state))):
                raise ValueError('review requires current candidate binding, findings, images and verdict')
    except (OSError, ValueError, TypeError, KeyError, library.Fail, subprocess.TimeoutExpired) as exc:
        print(str(exc), file=sys.stderr, flush=True)
        issues = [str(exc)]
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
        current['jobs'][role].update(finished=timestamp(), exit=code, ok=gate_ok, output_sha256=output_sha256)
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
        elif source.get('selected_pages') and not source['selected_pages'][0] <= page <= source['selected_pages'][1]:
            errors.append(f'{key}: page is outside the selected batch')
        elif page < last.get(region.get('source_id'), 0):
            errors.append(f'{key}: pages are out of order')
        else:
            last[region.get('source_id')] = page
        if not isinstance(box, list) or len(box) != 4 or not all(type(v) in (int, float) for v in box) or not (0 <= box[0] < box[2] <= 1 and 0 <= box[1] < box[3] <= 1):
            errors.append(f'{key}: invalid normalized box')
    return errors


def _media(state, record):
    errors, hashes = [], []
    files = record.get('media', [])
    if not isinstance(files, list) or not files:
        return ['candidate media missing'], []
    root = candidate_path(state).parent.resolve()
    for file in files:
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


def _coverage(state, data):
    """Require an explicit inspection disposition for every selected source page."""
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
            for key in ('regions', 'mark_scheme_regions') if kind == 'questions' else ('regions',):
                regions = record.get(key, [])
                if not isinstance(regions, list):
                    return [f'source page coverage requires a {key} list']
                for region in regions:
                    if not isinstance(region, dict) or not isinstance(region.get('source_id'), str):
                        return ['source page coverage requires source-bound region objects']
                    content_sources.add(region['source_id'])
    for row in rows:
        source = expected[row['source_id']]
        start, end = source.get('selected_pages') or (1, source['pages'])
        pages = row.get('inspected_pages')
        if (row.get('source_sha256') != source['sha256'] or not isinstance(pages, list)
                or any(type(page) is not int for page in pages)
                or pages != list(range(start, end + 1))):
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
        rows.append({**{key: row.get(key, '') for key in ('id', 'title', 'statement', 'guidance')},
                     'subtopic': {'id': parent['id'], 'title': parent.get('title', '')},
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


def _candidate_problems(state):
    """Read-only structural/content gates shared by completion and review preflight."""
    errors, image_hashes = [], []
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
                    errors.extend(_regions(record, sources, 'mark_scheme_regions'))
                    if record.get('kind') != 'mcq' or state['course'] not in ('9701', '9702'):
                        errors.append('unsupported publication format remains pending')
                    if record.get('answer') not in ('A', 'B', 'C', 'D'):
                        errors.append('official answer is missing')
                    if valid_identity and valid_part and valid_context:
                        identity = (record['official_qid'], record['part'], tuple(sorted(record['syllabus'])), tuple(sorted(record['kcs'])))
                        fields = {k: record.get(k) for k in ('answer', 'prerequisites', 'mark_scheme_regions')}
                        if identity in seen:
                            errors.append('content conflict' if seen[identity] != fields else 'duplicate same-context question')
                        seen[identity] = fields
                else:
                    if not record.get('caption') or not record.get('purpose'):
                        errors.append('diagram caption/teaching purpose is missing')
                media_errors, hashes = _media(state, record)
                errors.extend(media_errors)
                image_hashes.extend(hashes)
                if len(errors) > before:
                    errors.append(f"{kind}: {record.get('official_qid', record.get('id', 'unknown'))} remains pending")
    except (OSError, ValueError, TypeError) as exc:
        errors.append(f'candidate unavailable or invalid: {exc}')
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
            if review.get('verdict') != 'pass' or review.get('findings') != []:
                errors.append('independent review has pending findings')
            if not set(image_hashes).issubset(set(review.get('inspected_images', []))):
                errors.append('candidate images lack hash-bound visual inspection evidence')
        except (OSError, ValueError, TypeError):
            errors.append('independent review required')
        review_errors = errors[len(candidate_errors):]
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
    from tutorlib.asset_library import write_asset
    data, registrations, media_mapping = json.loads(candidate_path(state).read_text()), [], {}
    registered_records = {}
    review = json.loads((job_dir(name) / 'review.json').read_text())
    for kind in ('questions', 'diagrams'):
        for record in data[kind]:
            for media in record['media']:
                path = candidate_path(state).parent / media
                shelf = 'Questions/Media' if kind == 'questions' else 'Diagrams'
                namepart = re.sub(r'[^A-Za-z0-9_-]', '-', path.stem)[:70]
                context = hashlib.sha256(json.dumps(record, sort_keys=True).encode()).hexdigest()[:12]
                relative = f"Library/Courses/{state['course']}/{shelf}/{namepart}-{context}-{digest(path)[:16]}{path.suffix.lower()}"
                sidecar = write_asset(library.learner_vault(), relative + '.json',
                                     json.dumps({'extraction_job': state['name'], 'record': record,
                                                 'sha256': digest(path), 'course': state['course'],
                                                 'subtopics': record['syllabus'], 'kcs': record['kcs'],
                                                 'caption': record.get('caption', ''), 'why': record.get('purpose', ''),
                                                 'pdf': record['regions'][0]['source_id'],
                                                 'page': record['regions'][0]['page'], 'box': record['regions'][0]['box'],
                                                 'source_sha256': record['regions'][0]['source_sha256'],
                                                 'regions': record['regions'],
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


def publish(name, batch):
    state = check(name)
    if state['stage'] != 'reviewed' or not state.get('registrations'):
        raise ValueError('review and registration required before explicit topical publication')
    if state['course'] not in ('9701', '9702') or state['scope'] == 'diagrams':
        raise ValueError('unsupported question publication format remains pending')
    if state.get('registered_candidate_sha256') != state['candidate_sha256']:
        raise ValueError('registration is not bound to the current reviewed candidate')
    bank = json.loads((Path(batch) / 'bank.json').read_text())
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
    if not bank.get('items') or Counter(bank_identity(item) for item in bank['items']) != Counter(expected.keys()):
        raise ValueError('topical batch must contain exactly every reviewed question part/context (a bijection)')
    for item in bank['items']:
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
        required = [registered.get(media) for media in original['media']]
        if item.get('answer') != original['answer'] or item.get('kcs') != original['kcs'] or images != required:
            raise ValueError('topical batch differs from reviewed answers, KC mapping or registered media')
        source = item['source']
        if (source.get('extraction_regions') != original['regions']
                or source.get('mark_scheme_regions') != original['mark_scheme_regions']
                or source.get('extraction_prerequisites') != original['prerequisites']):
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
    new.add_argument('--codex-model', help='Persist a job-local Codex model choice for extraction and review')
    new.add_argument('--codex-effort', choices=('low', 'medium', 'high', 'xhigh'))
    new.add_argument('--codex-stop-remaining', type=float,
                     help='Explicit job-local Codex stopping boundary (20 to below 100 percent remaining)')
    for command in ('inventory', 'plan', 'resume', 'check', 'register'):
        sub.add_parser(command).add_argument('job')
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
    publication = sub.add_parser('publish'); publication.add_argument('job'); publication.add_argument('--topical-batch', required=True)
    clipping = sub.add_parser('crop'); clipping.add_argument('job'); clipping.add_argument('--source', required=True)
    clipping.add_argument('--page', type=int, required=True); clipping.add_argument('--box', required=True)
    clipping.add_argument('--output', required=True); clipping.add_argument('--dpi', type=int, default=160)
    worker = sub.add_parser('_worker'); worker.add_argument('job'); worker.add_argument('role')
    install = sub.add_parser('install-skill'); install.add_argument('--to', type=Path, default=Path.home() / '.claude/skills/extract')
    args = parser.parse_args(argv)
    try:
        if args.command == 'new': result = create(args.job, args.course, args.provider, args.scope, args.source, args.pages,
                                                args.codex_model, args.codex_effort, args.codex_stop_remaining)
        elif args.command == 'resume': result = load(args.job)
        elif args.command == 'graph': result = graph(args.job, kc_id=args.kc_id, query=args.query, limit=args.limit)
        elif args.command == 'enable-ocr': result = enable_ocr(args.job, args.source)
        elif args.command == 'ocr-text': result = ocr_text(args.job, args.source, args.pages)
        elif args.command == 'board':
            result = [json.loads(path.read_text()) for path in sorted((work_root() / 'Workers/extraction').glob('*/state.json'))]
        elif args.command == 'run': result = run(args.job, args.weekly_remaining, args.wait, args.retry)
        elif args.command == 'unstick':
            with state_lock(args.job) as state:
                if any(process_alive(j.get('pid')) and not j.get('finished') for j in state.get('jobs', {}).values()):
                    raise ValueError('cannot clear failures while a worker is running')
                reliability.clear_failures(state, args.reason)
                result = state
        elif args.command == '_worker': return _worker(args.job, args.role)
        elif args.command == 'publish': result = publish(args.job, args.topical_batch)
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
