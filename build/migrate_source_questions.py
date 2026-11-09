"""Migrate tagged, source-verified practice questions onto the course ``Questions`` shelf.

DRY-RUN BY DEFAULT.  Inputs are the sealed release (read-only), ``source_topics.json`` and
``image_cleaning.json`` (both under Work/Preparation/source-migration/).  Apply registers, per course,

  Library/Courses/<course>/Questions/SourceVerified/bank-<sha12>.json          (immutable bank)
  Library/Courses/<course>/Questions/SourceVerified/Media/<sha256>.png          (cleaned images only)

through ``tutorlib.asset_library.write_asset`` (digest-checked, never overwrites, catalog metadata carries
provenance back to the sealed release sha).  Originals stay where they are; unchanged images keep their
existing Library paths.  Ids, source_verified=true, mastery_certified=false and teaching_approved=false are
preserved/forced; items without a confident syllabus mapping are written as ``held`` (not served by
``SourceQuestions.items`` by default).  No existing Library file, alias, CURRENT pointer, learner event or
attempt is modified.

    .venv/bin/python build/migrate_source_questions.py                      # dry run, whole vault
    .venv/bin/python build/migrate_source_questions.py --courses P1,M1      # dry run, subset
    .venv/bin/python build/migrate_source_questions.py --apply --vault <vault> [--allow-production]
"""
from __future__ import annotations

import argparse
import collections
import hashlib
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from tutorlib.asset_library import AssetLibrary, write_asset  # noqa: E402
from tutorlib.source_questions import KIND  # noqa: E402
import source_topics  # noqa: E402
import clean_question_images  # noqa: E402

WORK = ROOT.parent / 'Work/Preparation/source-migration'
DEFAULT_VAULT = Path(os.environ.get('STEM_TUTOR_VAULT') or ROOT.parent / 'STEM Tutor')
SCHEMA = 1
READY = ('mapped', 'partial')
KEEP_FIELDS = ('id', 'canonical_id', 'official_qid', 'course', 'source', 'label', 'kind', 'marks', 'answer',
               'answer_status', 'maximum_authority', 'bank_id', 'review_reasons')


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def canonical_json(value) -> bytes:
    return (json.dumps(value, ensure_ascii=False, indent=1, sort_keys=True) + '\n').encode()


def media_rows(item, sidecar, course):
    """Image lists with cleaned files referenced by their future Library path."""
    resolved = clean_question_images.resolve(sidecar, item) if sidecar else None

    def target(row):
        if row['cleaned']:
            return f'Library/Courses/{course}/Questions/SourceVerified/Media/{row["cleaned"]}'
        return row['original']

    out = {}
    for key in ('question_media', 'context_media'):
        rows = resolved[key] if resolved else [{'original': r, 'cleaned': None, 'decision': 'keep'} for r in item.get(key, [])]
        out[key] = [{'path': target(r), 'original': r['original'], 'decision': r['decision']} for r in rows]
    out['cover_dropped'] = resolved.get('cover_dropped', []) if resolved else []
    out['mark_scheme_media'] = [{'path': r, 'original': r, 'decision': 'keep'} for r in item.get('mark_scheme_media', [])]
    return out


def build_item(item: dict, tag: dict, sidecar, include_low_trust: bool) -> dict:
    ready = tag['status'] in READY and (include_low_trust or tag.get('trust') != 'low')
    reason = None
    if not ready:
        reason = ('low_trust_part_union_only' if tag['status'] in READY else
                  tag['reason'] or tag['status'])
    media = media_rows(item, sidecar, item['course'])
    if media['cover_dropped'] and not (media['question_media'] or media['context_media']):
        # the exam cover page was the item's only image: never serve an imageless question
        ready, reason = False, 'only_image_was_exam_cover_page'
    row = {key: item[key] for key in KEEP_FIELDS if key in item}
    row.update({
        'stem': item.get('question_text', ''), 'scheme_text': item.get('scheme_text', ''),
        'kcs': tag['kcs_required'] if ready else [],
        'parts': [{k: p[k] for k in ('label', 'kcs', 'confidence', 'method')} for p in tag['parts']] if ready else [],
        'tag': {'status': tag['status'], 'method': tag['method'], 'confidence': tag['confidence'],
                'trust': tag.get('trust', 'none'), 'subtopics': tag['subtopics'] if ready else tag['subtopics'],
                'candidate_kcs': [] if ready else tag['kcs_required']},
        'media': media,
        'held': not ready, 'held_reason': reason,
        'source_verified': True, 'mastery_certified': False, 'teaching_approved': False,
    })
    return row


def build_documents(vault: Path, mapping: dict, sidecar: dict | None, *, courses=None, include_low_trust=False) -> dict:
    release, data = source_topics.load_release(vault, mapping['release'])
    tags = {t['id']: t for t in mapping['items']}
    docs: dict[str, dict] = {}
    for item in sorted(data['items'], key=lambda i: i['id']):
        if courses and item['course'] not in courses:
            continue
        tag = tags.get(item['id'])
        if tag is None:
            raise ValueError('no topic tag for ' + item['id'])
        doc = docs.setdefault(item['course'], {
            'schema_version': SCHEMA, 'kind': KIND, 'course': item['course'], 'items': [],
            'provenance': {'release': release, 'release_sha256': Path(release).stem,
                           'topics_sha256': sha(canonical_json(mapping)),
                           'image_cleaning_sha256': sha(canonical_json(sidecar)) if sidecar else None,
                           'generator': 'build/migrate_source_questions.py'}})
        doc['items'].append(build_item(item, tag, sidecar, include_low_trust))
    for doc in docs.values():
        doc['counts'] = {'items': len(doc['items']), 'ready': sum(not i['held'] for i in doc['items']),
                         'held': sum(i['held'] for i in doc['items'])}
    return docs


def plan(vault: Path, docs: dict, sidecar: dict | None, work: Path) -> dict:
    """Everything apply would write; touches nothing."""
    needed = collections.defaultdict(dict)
    for course, doc in docs.items():
        for item in doc['items']:
            for key in ('question_media', 'context_media'):
                for m in item['media'][key]:
                    if m['decision'] in ('crop', 'collapse'):
                        needed[course][m['path']] = m['path'].rsplit('/', 1)[-1]
    report = {'vault': str(vault), 'courses': {}}
    for course, doc in sorted(docs.items()):
        blob = canonical_json(doc)
        report['courses'][course] = {
            'bank_path': f'Library/Courses/{course}/Questions/SourceVerified/bank-{sha(blob)[:12]}.json',
            'bank_sha256': sha(blob), **doc['counts'], 'cleaned_images_to_register': len(needed[course]),
            'held_reasons': dict(collections.Counter(i['held_reason'] for i in doc['items'] if i['held']).most_common())}
    return report


def apply(vault: Path, docs: dict, sidecar: dict | None, work: Path) -> dict:
    """Idempotent: re-running registers nothing new (write_asset refuses changed bytes at a taken path)."""
    vault = Path(vault)
    result = {}
    for course, doc in sorted(docs.items()):
        built_at = doc['provenance']['release_sha256'][:12]
        images = {}
        for item in doc['items']:
            for key in ('question_media', 'context_media'):
                for m in item['media'][key]:
                    if m['decision'] in ('crop', 'collapse'):
                        images[m['path']] = m
        for path, m in sorted(images.items()):
            name = path.rsplit('/', 1)[-1]
            data = (work / sidecar['cleaned_dir'] / name).read_bytes()
            if sha(data) + '.png' != name:
                raise ValueError('cleaned image digest mismatch: ' + name)
            write_asset_idempotent(vault, path, data, metadata={
                'kind': 'source_verified_question_media', 'course': course, 'derived_from': m['original'],
                'cleaning': m['decision'], 'release_sha256': doc['provenance']['release_sha256']})
        blob = canonical_json(doc)
        path = f'Library/Courses/{course}/Questions/SourceVerified/bank-{sha(blob)[:12]}.json'
        reference = write_asset_idempotent(vault, path, blob, metadata={
            'kind': KIND, 'course': course, 'built_at': built_at + '-' + sha(blob)[:12], 'items': doc['counts']['items'],
            'ready': doc['counts']['ready'], 'held': doc['counts']['held'], 'provenance': doc['provenance'],
            'mastery_certified': False, 'teaching_approved': False})
        result[course] = {'reference': reference, 'path': path, 'images': len(images)}
    return result


def write_asset_idempotent(vault: Path, path: str, data: bytes, *, metadata: dict) -> str:
    target = Path(vault) / path
    if target.exists():
        if target.read_bytes() != data:
            raise ValueError('refusing to replace existing Library resource ' + path)
        from tutorlib.asset_library import register_asset
        return register_asset(vault, path, metadata=metadata)
    return write_asset(vault, path, data, metadata=metadata)


def load_work(work: Path):
    mapping = json.loads((work / 'source_topics.json').read_text())
    side = work / 'image_cleaning.json'
    return mapping, (json.loads(side.read_text()) if side.is_file() else None)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    ap.add_argument('--vault', type=Path, default=DEFAULT_VAULT)
    ap.add_argument('--work', type=Path, default=WORK)
    ap.add_argument('--courses')
    ap.add_argument('--apply', action='store_true', help='register the banks (default: dry run)')
    ap.add_argument('--allow-production', action='store_true', help='required to apply to the real STEM Tutor vault')
    ap.add_argument('--include-low-trust', action='store_true', help='serve items tagged only by a union of part tags')
    ap.add_argument('--emit-dir', type=Path, help='also write the per-course bank documents here (inspection)')
    args = ap.parse_args(argv)
    mapping, sidecar = load_work(args.work)
    courses = set(args.courses.split(',')) if args.courses else None
    docs = build_documents(args.vault, mapping, sidecar, courses=courses, include_low_trust=args.include_low_trust)
    report = plan(args.vault, docs, sidecar, args.work)
    if args.emit_dir:
        args.emit_dir.mkdir(parents=True, exist_ok=True)
        for course, doc in docs.items():
            (args.emit_dir / f'{course}.json').write_bytes(canonical_json(doc))
    print(json.dumps(report, indent=1))
    if not args.apply:
        print('DRY RUN: nothing written.  Add --apply to register.')
        return 0
    if Path(args.vault).resolve() == DEFAULT_VAULT.resolve() and not args.allow_production:
        print('refusing: target is the production vault; pass --allow-production deliberately', file=sys.stderr)
        return 2
    print(json.dumps(apply(args.vault, docs, sidecar, args.work), indent=1))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
