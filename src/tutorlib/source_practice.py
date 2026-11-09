"""Library-only source practice. Attempts never enter adaptive learner events."""
from __future__ import annotations

from contextlib import contextmanager
import copy
from datetime import datetime, timezone
import fcntl
import hashlib
import json
import os
from pathlib import Path
import re
import stat
import uuid

from .asset_library import AssetLibrary, _directory, _read_at, _atomic_at

RELEASE = re.compile(r'Library/SourcePractice/Releases/[a-f0-9]{64}\.json\Z')
ATTEMPT = re.compile(r'[a-f0-9]{32}\Z')


@contextmanager
def collection_lock(vault):
    with _directory(Path(vault), ['.tutor', 'source_practice'], create=True) as directory:
        descriptor = os.open('.writer.lock', os.O_RDWR | os.O_CREAT | os.O_NOFOLLOW, 0o600, dir_fd=directory)
        try:
            if not stat.S_ISREG(os.fstat(descriptor).st_mode): raise ValueError('unsafe practice lock')
            fcntl.flock(descriptor, fcntl.LOCK_EX)
            yield
        finally: os.close(descriptor)


class Collection:
    """Safe public views and attempt-gated official feedback from one sealed release."""
    def __init__(self, vault: Path, *, release: str | None = None):
        self.vault = Path(vault)
        self.library = AssetLibrary(self.vault)
        if release is None:
            with _directory(self.vault, ['.tutor', 'source_practice']) as directory:
                release = _read_at(directory, 'CURRENT').decode().strip()
        if not RELEASE.fullmatch(release): raise ValueError('invalid source practice CURRENT')
        self.release = release
        raw = self.library.read(release)
        if hashlib.sha256(raw).hexdigest() != Path(release).stem: raise ValueError('practice release digest mismatch')
        manifest = json.loads(raw)
        self._manifest = manifest
        if manifest.get('schema_version') != 1 or manifest.get('mastery_certified') != 0: raise ValueError('invalid practice release')
        self._items = {}; public, private = set(), set()
        for row in manifest['items']:
            if (row['id'] in self._items or row['id'] != row['canonical_id'] or row['kcs'] != []
                    or row['mastery_certified'] is not False or row['source_verified'] is not True
                    or type(row['marks']) is not int or row['marks'] < 1): raise ValueError('invalid practice item')
            for key, partition in [('question_media', public), ('context_media', public), ('mark_scheme_media', private)]:
                for reference in row.get(key, []):
                    if not re.fullmatch(r'Library/SourcePractice/Media/[a-f0-9-]+\.png', reference): raise ValueError('unsafe practice media')
                    partition.add(reference)
            self._items[row['id']] = row
        if public & private: raise ValueError('practice public/private media conflict')

    def courses(self):
        return sorted({row['course'] for row in self._items.values()})

    def sources(self, course=None):
        return sorted({row['source'] for row in self._items.values() if course is None or row['course'] == course})

    def questions(self, course=None, source=None):
        return [{key: row[key] for key in ('id', 'course', 'source', 'label', 'kind')}
                for row in self._items.values() if (course is None or row['course'] == course) and (source is None or row['source'] == source)]

    def question(self, qid):
        row = self._items[qid]
        keys = ('id', 'canonical_id', 'course', 'source', 'title', 'label', 'kind', 'marks', 'maximum_authority',
                'question_media', 'context_media', 'question_text', 'kcs', 'source_verified', 'mastery_certified', 'bank_id')
        return copy.deepcopy({key: row[key] for key in keys if key in row})

    def media_path(self, qid, reference, *, attempt_id=None):
        row = self._items[qid]
        allowed = row.get('question_media', []) + row.get('context_media', [])
        if attempt_id is not None:
            attempt = self._attempt(attempt_id)
            if attempt['qid'] != qid or attempt['release'] != self.release: raise ValueError('attempt does not own scheme')
            allowed += row.get('mark_scheme_media', [])
        if reference not in allowed: raise ValueError('media is private or outside question scope')
        return self.library.resolve(reference)

    def submit(self, qid, answer):
        row = self._items[qid]
        if not isinstance(answer, str) or not answer.strip(): raise ValueError('write an answer before revealing feedback')
        if row['kind'] == 'mcq' and answer.strip().upper() not in ('A', 'B', 'C', 'D'): raise ValueError('choose A, B, C or D')
        attempt_id = uuid.uuid4().hex
        record = {'schema_version': 1, 'attempt_id': attempt_id, 'release': self.release, 'qid': qid,
                  'answer': answer, 'submitted_at': datetime.now(timezone.utc).isoformat(), 'mastery_credit': False}
        if row['kind'] == 'mcq': record['awarded'] = int(answer.strip().upper() == row['answer'])
        data = json.dumps(record, ensure_ascii=False, sort_keys=True).encode()
        with collection_lock(self.vault), _directory(self.vault, ['.tutor', 'source_practice', 'attempts'], create=True) as directory:
            _atomic_at(directory, attempt_id + '.json', data, replace=False)
        return copy.deepcopy(record)

    def _attempt(self, attempt_id):
        if not isinstance(attempt_id, str) or not ATTEMPT.fullmatch(attempt_id): raise ValueError('unknown attempt')
        try:
            with _directory(self.vault, ['.tutor', 'source_practice', 'attempts']) as directory:
                record = json.loads(_read_at(directory, attempt_id + '.json'))
        except (OSError, ValueError) as exc: raise ValueError('unknown attempt') from exc
        if record.get('attempt_id') != attempt_id or record.get('release') != self.release or record.get('qid') not in self._items:
            raise ValueError('attempt release or question mismatch')
        return record

    def feedback(self, attempt_id):
        record = self._attempt(attempt_id); row = self._items[record['qid']]
        result = {'attempt_id': attempt_id, 'qid': row['id'], 'marks': row['marks'], 'mastery_credit': False}
        if row['kind'] == 'mcq': result.update(answer=row['answer'], awarded=record['awarded'])
        else:
            result.update(scheme_media=copy.deepcopy(row['mark_scheme_media']), scheme_text=row['scheme_text'],
                          maximum_authority=row['maximum_authority'])
            with _directory(self.vault, ['.tutor', 'source_practice', 'attempts']) as directory:
                raw = _read_at(directory, attempt_id + '-award.json', optional=True)
            if raw: result['awarded'] = json.loads(raw)['awarded']
        return result

    def award(self, attempt_id, marks):
        attempt = self._attempt(attempt_id); row = self._items[attempt['qid']]
        if row['kind'] == 'mcq' or type(marks) is not int or not 0 <= marks <= row['marks']:
            raise ValueError('award must be an integer within the printed question maximum')
        record = {'attempt_id': attempt_id, 'qid': row['id'], 'release': self.release, 'awarded': marks,
                  'authority': 'human_self_mark', 'mastery_credit': False,
                  'submission_sha256': hashlib.sha256(json.dumps(attempt, ensure_ascii=False, sort_keys=True).encode()).hexdigest()}
        with collection_lock(self.vault), _directory(self.vault, ['.tutor', 'source_practice', 'attempts']) as directory:
            if _read_at(directory, attempt_id + '-award.json', optional=True) is not None: raise ValueError('attempt already awarded')
            _atomic_at(directory, attempt_id + '-award.json', json.dumps(record, sort_keys=True).encode(), replace=False)
        return record
