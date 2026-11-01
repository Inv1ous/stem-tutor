"""Private durable queue for notes that may disclose unanswered questions.

Lesson completion stores guarded notes here until their saved questions are attempted.
"""
from __future__ import annotations

import copy
import fcntl
import json
from functools import wraps
from pathlib import Path

from .store import read_json, write_json


def _serialized_writer(fn):
    @wraps(fn)
    def write(path, *args, **kwargs):
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.with_name(path.name + '.lock').open('a') as lock:
            fcntl.flock(lock, fcntl.LOCK_EX)
            try:
                return fn(path, *args, **kwargs)
            finally:
                fcntl.flock(lock, fcntl.LOCK_UN)
    return write


def _read(path):
    data = read_json(path, default={'entries': []})
    if not isinstance(data, dict) or not isinstance(data.get('entries'), list):
        raise ValueError('invalid deferred-note store')
    if not isinstance(data.setdefault('guards', {}), dict):
        raise ValueError('invalid deferred-note guards')
    revisions = data.setdefault('guard_revisions', {})
    if not isinstance(revisions, dict) or any(not isinstance(k, str) or type(v) is not int or v < 0
                                              for k, v in revisions.items()):
        raise ValueError('invalid guard revisions')
    generations = data.setdefault('guard_generations', {})
    if not isinstance(generations, dict) or any(not isinstance(k, str) or type(v) is not int or v < 0
                                                for k, v in generations.items()):
        raise ValueError('invalid guard generations')
    return data


def _bump(data, ident):
    revisions = data['guard_revisions']
    revisions[ident] = revisions.get(ident, 0) + 1


@_serialized_writer
def guard_revision(path, ident):
    return _read(path)['guard_revisions'].get(ident, 0)


@_serialized_writer
def guard_snapshot(path, ident):
    """Capture the exact guard and its revision under one cooperating-writer lock."""
    data = _read(path)
    copies = [data['guards'][ident]] if ident in data['guards'] else []
    copies.extend(row['guards'][ident] for row in data['entries'] if ident in row['guards'])
    if not copies:
        return None
    canonical = lambda value: json.dumps(value, sort_keys=True, ensure_ascii=False, allow_nan=False)
    if any(canonical(value) != canonical(copies[0]) for value in copies[1:]):
        raise ValueError('conflicting guard copies')
    return {'guard': copy.deepcopy(copies[0]), 'revision': data['guard_revisions'].get(ident, 0),
            'generation': data['guard_generations'].get(ident, 0)}


@_serialized_writer
def defer(path, entry_id, subtopic, node, guards):
    if not isinstance(entry_id, str) or not entry_id or not isinstance(guards, dict) or not guards:
        raise ValueError('a deferred note needs an identity and guards')
    data = _read(path)
    entry = {'id': entry_id, 'subtopic': subtopic, 'node': copy.deepcopy(node), 'guards': copy.deepcopy(guards)}
    previous = [row for row in data['entries'] if row.get('id') == entry_id]
    if previous:
        if len(previous) != 1 or previous[0] != entry:
            raise ValueError('deferred-note identity already exists')
        return
    for ident in guards:
        if ident not in data['guards'] and not any(ident in row['guards'] for row in data['entries']):
            data['guard_generations'][ident] = data['guard_generations'].get(ident, 0) + 1
        _bump(data, ident)
    data['entries'].append(entry)
    write_json(path, data)


@_serialized_writer
def resolve(path, guard_id):
    data = _read(path)
    changed = guard_id in data['guards']
    data['guards'].pop(guard_id, None)
    for entry in data['entries']:
        if guard_id in entry['guards']:
            del entry['guards'][guard_id]
            changed = True
    if changed:
        _bump(data, guard_id)
        write_json(path, data)


def ready(path):
    return [{'id': row['id'], 'subtopic': row['subtopic'], 'node': copy.deepcopy(row['node'])}
            for row in _read(path)['entries'] if not row['guards']]


def _merge_guard(guards, ident, question):
    if ident in guards and guards[ident] != question:
        previous = guards[ident]
        old_inst = (previous.get('question') or {}).get('inst')
        new_inst = (question.get('question') or {}).get('inst')
        if (not isinstance(old_inst, dict) or old_inst != new_inst or
                any(previous.get(k) != question.get(k) for k in ('key', 'kind', 'numeric', 'short_answers'))):
            raise ValueError('conflicting deferred-note guard')
    guards[ident] = copy.deepcopy(question)


@_serialized_writer
def hold(path, ident, question):
    data = _read(path)
    previous = [data['guards'][ident]] if ident in data['guards'] else []
    previous.extend(entry['guards'][ident] for entry in data['entries'] if ident in entry['guards'])
    if not previous:
        data['guard_generations'][ident] = data['guard_generations'].get(ident, 0) + 1
    canonical = lambda value: json.dumps(value, sort_keys=True, ensure_ascii=False, allow_nan=False)
    if ident in data['guards'] and all(canonical(value) == canonical(question) for value in previous):
        return
    _merge_guard(data['guards'], ident, question)
    for entry in data['entries']:
        if ident in entry['guards']:
            _merge_guard(entry['guards'], ident, question)
    incoming = (question.get('question') or {}).get('saved_work')
    for guard in previous:
        draft = (guard.get('question') or {}).get('saved_work')
        if isinstance(draft, str) and draft != incoming:
            history = data.setdefault('draft_history', {}).setdefault(ident, [])
            if draft not in history:
                history.append(draft)
    _bump(data, ident)
    write_json(path, data)


@_serialized_writer
def reconcile_written_draft(path, ident, question):
    """Keep a divergent session draft without replacing or resurrecting the durable guard."""
    data = _read(path)
    copies = [data['guards'][ident]] if ident in data['guards'] else []
    copies.extend(row['guards'][ident] for row in data['entries'] if ident in row['guards'])
    if copies and all(row == question for row in copies):
        return 'current'
    draft = (question.get('question') or {}).get('saved_work')
    if isinstance(draft, str):
        histories = data.setdefault('draft_history', {})
        if not isinstance(histories, dict) or not isinstance(histories.get(ident, []), list) or any(
                not isinstance(x, str) for x in histories.get(ident, [])):
            raise ValueError('invalid guard draft history')
        history = histories.setdefault(ident, [])
        if draft not in history:
            history.append(draft)
            write_json(path, data)
    return 'conflict'


def draft_history(path, ident):
    """Return older drafts retained privately when a guard was refreshed."""
    history = _read(path).get('draft_history', {})
    if not isinstance(history, dict) or not isinstance(history.get(ident, []), list):
        raise ValueError('invalid guard draft history')
    return copy.deepcopy(history.get(ident, []))


def all_draft_history(path):
    history = _read(path).get('draft_history', {})
    if not isinstance(history, dict) or any(not isinstance(rows, list) or
            any(not isinstance(row, str) for row in rows) for rows in history.values()):
        raise ValueError('invalid guard draft history')
    return copy.deepcopy(history)


@_serialized_writer
def guard_and_history(path, ident):
    """Read guards and one history together under the cooperating-writer lock."""
    data = _read(path)
    guards = copy.deepcopy(data['guards'])
    for row in data['entries']:
        for key, guard in row['guards'].items():
            _merge_guard(guards, key, guard)
    history = data.get('draft_history', {})
    if not isinstance(history, dict) or not isinstance(history.get(ident, []), list):
        raise ValueError('invalid guard draft history')
    rows = history.get(ident, [])
    if any(not isinstance(row, str) for row in rows):
        raise ValueError('invalid guard draft history')
    return guards, copy.deepcopy(rows)


@_serialized_writer
def compare_update(path, ident, expected, proposed):
    """Conditionally update a draft in one store file.

    Both full guards are required, so an unexpected protected key or question
    never becomes an implicit draft update. A repeated successful update is safe.
    """
    if not isinstance(ident, str) or not ident:
        raise ValueError('guard identity is required')
    def canonical(value):
        return json.dumps(value, sort_keys=True, ensure_ascii=False, allow_nan=False)
    def identity(guard):
        if not isinstance(guard, dict):
            raise ValueError('invalid guard')
        guard = copy.deepcopy(guard)
        question = guard.get('question')
        if not isinstance(question, dict):
            raise ValueError('guard has no question')
        if 'saved_work' in question and not isinstance(question['saved_work'], str):
            raise ValueError('draft must be text')
        question.pop('saved_work', None)
        return canonical(guard)
    if identity(expected) != identity(proposed):
        raise ValueError('draft update changes protected guard')
    expected_key, proposed_key = canonical(expected), canonical(proposed)
    data = _read(path)
    copies = [data['guards'][ident]] if ident in data['guards'] else []
    copies.extend(row['guards'][ident] for row in data['entries'] if ident in row['guards'])
    if not copies:
        return 'conflict'
    if all(canonical(row) == proposed_key for row in copies):
        return 'already_applied'
    if not all(canonical(row) == expected_key for row in copies):
        return 'conflict'
    if ident in data['guards']:
        data['guards'][ident] = copy.deepcopy(proposed)
    for row in data['entries']:
        if ident in row['guards']:
            row['guards'][ident] = copy.deepcopy(proposed)
    _bump(data, ident)
    write_json(path, data)
    return 'applied'


@_serialized_writer
def cancel_draft(path, operation, ident, expected, proposed, revision):
    """Persist a guarded draft and its operation identity in one locked store write."""
    if not all(isinstance(v, str) and v for v in (operation, ident)):
        raise ValueError('operation and guard identity are required')
    if type(revision) is not int or revision < 0:
        raise ValueError('guard revision is required')
    def canonical(value):
        return json.dumps(value, sort_keys=True, ensure_ascii=False, allow_nan=False)
    def protected(guard):
        if not isinstance(guard, dict) or not isinstance(guard.get('question'), dict):
            raise ValueError('invalid guard')
        value = copy.deepcopy(guard)
        draft = value['question'].pop('saved_work', None)
        if draft is not None and not isinstance(draft, str):
            raise ValueError('draft must be text')
        return canonical(value)
    if protected(expected) != protected(proposed):
        raise ValueError('draft changes protected guard')
    data = _read(path)
    operations = data.setdefault('draft_operations', {})
    if not isinstance(operations, dict):
        raise ValueError('invalid draft operations')
    record = {'guard': ident, 'expected': expected, 'proposed': proposed, 'revision': revision}
    copies = [data['guards'][ident]] if ident in data['guards'] else []
    copies.extend(row['guards'][ident] for row in data['entries'] if ident in row['guards'])
    if operation in operations:
        if canonical(operations[operation]) != canonical(record):
            raise ValueError('operation identity reused')
        return 'already_applied' if (data['guard_revisions'].get(ident, 0) == revision + 1 and copies
                                     and all(canonical(x) == canonical(proposed) for x in copies)) else 'conflict'
    if data['guard_revisions'].get(ident, 0) != revision or not copies or any(canonical(x) != canonical(expected) for x in copies):
        return 'conflict'
    draft = (expected.get('question') or {}).get('saved_work')
    new_draft = (proposed.get('question') or {}).get('saved_work')
    if isinstance(draft, str) and draft != new_draft:
        histories = data.setdefault('draft_history', {})
        if not isinstance(histories, dict) or not isinstance(histories.get(ident, []), list) or any(
                not isinstance(x, str) for x in histories.get(ident, [])):
            raise ValueError('invalid guard draft history')
        history = histories.setdefault(ident, [])
        if draft not in history:
            history.append(draft)
    if ident in data['guards']:
        data['guards'][ident] = copy.deepcopy(proposed)
    for row in data['entries']:
        if ident in row['guards']:
            row['guards'][ident] = copy.deepcopy(proposed)
    operations[operation] = copy.deepcopy(record)
    _bump(data, ident)
    write_json(path, data)
    return 'applied'


@_serialized_writer
def record_draft_conflict(path, operation, ident, expected, local, generation):
    """Retain both versions privately without resolving or changing the guard."""
    if not all(isinstance(x, str) and x for x in (operation, ident)):
        raise ValueError('operation and guard identity are required')
    if type(generation) is not int or generation < 0:
        raise ValueError('guard generation is required')
    def canonical(value):
        return json.dumps(value, sort_keys=True, ensure_ascii=False, allow_nan=False)
    def protected(value):
        if not isinstance(value, dict) or not isinstance(value.get('question'), dict):
            raise ValueError('invalid guard')
        guard = copy.deepcopy(value)
        work = guard['question'].pop('saved_work', None)
        if work is not None and not isinstance(work, str):
            raise ValueError('invalid draft')
        return canonical(guard)
    if protected(expected) != protected(local):
        raise ValueError('draft changes protected guard')
    data = _read(path)
    conflicts = data.setdefault('draft_conflicts', {})
    if not isinstance(conflicts, dict):
        raise ValueError('invalid draft conflicts')
    if operation in conflicts:
        record = conflicts[operation]
        if (not isinstance(record, dict) or record.get('guard') != ident or record.get('generation') != generation
                or canonical(record.get('expected')) != canonical(expected)
                or canonical(record.get('local')) != canonical(local)):
            raise ValueError('operation identity reused')
        return 'already_recorded'
    copies = [data['guards'][ident]] if ident in data['guards'] else []
    copies.extend(row['guards'][ident] for row in data['entries'] if ident in row['guards'])
    if data['guard_generations'].get(ident, 0) != generation or not copies or any(canonical(x) != canonical(copies[0]) for x in copies):
        return 'conflict'
    if protected(copies[0]) != protected(expected):
        return 'conflict'
    histories = data.setdefault('draft_history', {})
    if not isinstance(histories, dict) or not isinstance(histories.get(ident, []), list) or any(
            not isinstance(x, str) for x in histories.get(ident, [])):
        raise ValueError('invalid guard draft history')
    history = histories.setdefault(ident, [])
    for guard in (expected, local, copies[0]):
        work = guard['question'].get('saved_work')
        if isinstance(work, str) and work not in history:
            history.append(work)
    conflicts[operation] = {'guard': ident, 'expected': copy.deepcopy(expected), 'local': copy.deepcopy(local),
                            'stored': copy.deepcopy(copies[0]), 'revision': data['guard_revisions'].get(ident, 0),
                            'generation': generation}
    write_json(path, data)
    return 'recorded'


@_serialized_writer
def read_draft_conflict(path, operation):
    conflicts = _read(path).get('draft_conflicts', {})
    if not isinstance(conflicts, dict):
        raise ValueError('invalid draft conflicts')
    return copy.deepcopy(conflicts.get(operation))


@_serialized_writer
def current_draft_conflict(path, operation):
    """Return a conflict only while its recorded guard snapshot remains current."""
    data = _read(path)
    conflicts = data.get('draft_conflicts', {})
    if not isinstance(conflicts, dict):
        raise ValueError('invalid draft conflicts')
    record = conflicts.get(operation)
    if not isinstance(record, dict):
        return None
    ident = record.get('guard')
    all_guards = set(data['guards'])
    for entry in data['entries']:
        all_guards.update(entry['guards'])
    if all_guards != {ident}:
        return None
    copies = [data['guards'][ident]] if ident in data['guards'] else []
    copies.extend(row['guards'][ident] for row in data['entries'] if ident in row['guards'])
    canonical = lambda value: json.dumps(value, sort_keys=True, ensure_ascii=False, allow_nan=False)
    if (not copies or data['guard_generations'].get(ident, 0) != record.get('generation')
            or data['guard_revisions'].get(ident, 0) != record.get('revision')
            or any(canonical(row) != canonical(record.get('stored')) for row in copies)):
        return None
    return copy.deepcopy(record)


def outstanding(path):
    data = _read(path)
    guards = copy.deepcopy(data['guards'])
    for row in data['entries']:
        for ident, question in row['guards'].items():
            _merge_guard(guards, ident, question)
    return guards


@_serialized_writer
def acknowledge(path, entry_id):
    data = _read(path)
    matches = [row for row in data['entries'] if row['id'] == entry_id]
    if any(row['guards'] for row in matches):
        raise ValueError('cannot acknowledge a guarded note')
    if matches:
        data['entries'] = [row for row in data['entries'] if row['id'] != entry_id]
        write_json(path, data)
