"""Disposable vaults for solvability / practice-mode tests (never the production vault)."""
import hashlib
import json
import random
from datetime import datetime

from test_topicals import bank_vault, OTHER, THIRD, TARGET  # noqa: F401
from tutorlib import session, store
from tutorlib.asset_library import write_asset

NOW = datetime.fromisoformat('2026-10-27T12:00:00+08:00')


def vault_with_flashcards(tmp_path):
    """9702: chapters 2.1 (exists), 3.1 (flashcard for 3.1.1), 4.1 (no teaching material).  3.1.1 is OTHER + '.1'."""
    root = bank_vault(tmp_path)
    pack = {'subtopic': OTHER, 'spec': '9702', 'note': 'n.md', 'outline': 'o', 'misconceptions': [], 'worked': [],
            'items': [], 'flashcards': [{'id': 'f1', 'kc': OTHER + '.1', 'front': 'State Newton second law.',
                                         'back': 'Net force equals mass times acceleration, F = ma.'}]}
    (root / '.tutor/packs/v1/specs/9702/packs' / (OTHER + '.json')).write_text(json.dumps(pack))
    (root / '.tutor/packs/v1/papers.json').write_text('{"papers": []}')  # a Library catalog now exists
    return root


def tutor_for(root, **kw):
    return session.Tutor(store.Vault(root), rng=random.Random(0), now=lambda: NOW, **kw)


def png_bytes(tag: str) -> bytes:
    return b'\x89PNG\r\n\x1a\n' + tag.encode()


def source_item(qid, kind='mcq', kcs=('9702-2.1.1',), parts=(), held=False, answer='B', marks=None, scheme_media=(), **extra):
    marks = marks or (1 if kind == 'mcq' else 3)
    image = 'Library/Courses/9702/Questions/SourceVerified/Media/' + hashlib.sha256(qid.encode()).hexdigest() + '.png'
    row = {'id': qid, 'canonical_id': qid, 'official_qid': qid, 'bank_id': None, 'course': '9702', 'held': held,
           'held_reason': 'unmapped' if held else None, 'kcs': list(kcs), 'kind': kind, 'label': '1', 'marks': marks,
           'maximum_authority': 'x', 'parts': [{'label': l, 'kcs': list(k), 'confidence': 0.9, 'method': 'text'} for l, k in parts],
           'source': 'src', 'source_verified': True, 'mastery_certified': False, 'teaching_approved': False,
           'stem': f'Stem of {qid}.', 'scheme_text': 'PMT scheme', 'tag': {'subtopics': sorted({k.rsplit('.', 1)[0] for k in kcs}),
                                                                       'status': 'mapped', 'trust': 'medium'},
           'media': {'question_media': [{'path': image, 'original': image, 'decision': 'keep'}], 'context_media': [],
                     'cover_dropped': [], 'mark_scheme_media': [{'path': m, 'original': m, 'decision': 'keep'} for m in scheme_media]}}
    if kind == 'mcq':
        row['answer'] = answer
    row.update(extra)
    return row


def register_bank(root, items, course='9702'):
    for it in items:
        for m in it['media']['question_media']:
            try:
                write_asset(root, m['path'], png_bytes(it['id']), metadata={'kind': 'source_verified_question_media', 'course': course})
            except ValueError:
                pass
        for m in it['media']['mark_scheme_media']:
            try:
                write_asset(root, m['path'], png_bytes('scheme' + m['path']), metadata={'kind': 'source_practice_media'})
            except ValueError:
                pass
    doc = {'kind': 'source_verified_questions', 'course': course, 'schema_version': 1, 'provenance': {},
           'counts': {'items': len(items), 'held': sum(i['held'] for i in items), 'ready': 0}, 'items': items}
    blob = json.dumps(doc, sort_keys=True).encode()
    path = f'Library/Courses/{course}/Questions/SourceVerified/bank-{hashlib.sha256(blob).hexdigest()[:12]}.json'
    return write_asset(root, path, blob, metadata={'kind': 'source_verified_questions', 'course': course, 'built_at': 'test-1'})
