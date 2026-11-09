"""Plan where question media still loose in Questions/Media/ belongs.

Only images sitting directly in ``Library/Courses/<course>/Questions/Media/`` are
considered; anything already inside MCQ, Long, Keys or Reference is out of scope.
Classification reuses the evidence ``organize_question_library.collect`` gathers and
the plan is emitted by ``organize_question_library.build_plan`` itself, so
``organize_question_library.py apply --plan`` accepts the result unchanged.

Read-only: nothing here writes to the vault. Low-confidence images stay loose and are
listed in ``held`` with the reason; validator-pinned images are held, never moved.
"""
from __future__ import annotations

import argparse
import collections
import json
import sys
from pathlib import Path, PurePosixPath

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'build'))
sys.path.insert(0, str(ROOT / 'src'))

import organize_question_library as organize
from question_media_names import FOLDER, canonical_name, classify, is_fallback, qid_from_filename
from tutorlib.asset_library import asset_path_key

TOOL = 'file_unfiled_question_media'
WORK = ROOT.parent / 'Work' / 'Preparation' / 'question-naming'
PLAN = WORK / 'unfiled-plan.json'


def is_loose(path: str) -> bool:
    """True for an image whose parent directory is Questions/Media itself."""
    place = organize.locate(path)
    return bool(place and place[2] == 'Media' and organize.is_image(path)
                and PurePosixPath(path).parent.name == 'Media')


def loose_decisions(vault: Path):
    """Classify only the loose images, reusing collect()'s evidence and decide()'s rules."""
    library, records, evidence = organize.collect(vault)
    decisions, unclassified = {}, []
    for identifier, record in sorted(records.items()):
        path = record['path']
        if not is_loose(path):
            continue
        scope, path_course, area = organize.locate(path)
        name = PurePosixPath(path).name
        verdict = classify(list(evidence.votes.get(identifier, [])), name)
        courses = evidence.courses.get(identifier, set()) | ({path_course} if path_course else set())
        course = path_course or (next(iter(courses)) if len(courses) == 1 else None)
        problem = None
        if verdict['conflict']:
            problem = 'conflicting evidence: ' + ','.join(verdict['disagree'])
        elif verdict['role'] is None:
            problem = 'no classification evidence'
        elif len(courses) > 1:
            problem = 'conflicting courses: ' + ','.join(sorted(courses))
        elif course is None:
            problem = 'course not determinable'
        candidates = list(evidence.qids.get(identifier, []))
        legacy = qid_from_filename(name)
        if legacy:
            candidates.append((legacy, ''))
        qid, part, qid_state = organize.choose_qid(candidates, course) if course else (None, '', 'none')
        entry = {'id': identifier, 'path': path, 'sha256': record['sha256'], 'scope': scope, 'area': area,
                 'course': course, 'role': verdict['role'], 'tier': verdict['tier'],
                 'sources': verdict['sources'][:3], 'disagree': verdict['disagree'], 'qid': qid,
                 'qid_state': qid_state, 'problem': problem,
                 'pinned': bool(record.get('kind') == 'Questions/Media' and organize.PINNED.fullmatch(name))}
        if problem is None:
            ext = PurePosixPath(path).suffix
            entry['name'] = canonical_name(course, verdict['role'], record['sha256'], qid=qid, part=part, ext=ext)
            entry['fallback'] = is_fallback(entry['name'])
            entry['folder'] = FOLDER[verdict['role']]
        else:
            unclassified.append({'id': identifier, 'path': path, 'course': course, 'problem': problem})
        decisions[identifier] = entry
    return library, records, decisions, unclassified


def build_plan(vault: Path, *, references: bool = True) -> dict:
    """Emit an apply-compatible plan for the loose images only."""
    vault = Path(vault).resolve()
    library, records, decisions, unclassified = loose_decisions(vault)
    report = organize.build_plan(vault, (library, records, decisions, unclassified), scope='course')
    report['source'] = TOOL
    for item in unclassified:
        report['held'].append({'id': item['id'], 'path': item['path'], 'reason': item['problem']})
    for item in report['held']:
        entry = decisions.get(item['id'])
        if entry and not entry['problem']:
            report['details'][item['id']] = {
                **{k: entry[k] for k in ('course', 'role', 'folder', 'tier', 'qid', 'qid_state',
                                         'fallback', 'pinned', 'sources')}, 'held': item['reason']}
    report['loose'] = {
        'images': len(decisions),
        'moves': len(report['moves']),
        'held_pinned': sum(1 for h in report['held'] if h['reason'] == 'validator-pinned legacy name'),
        'held_low_confidence': len(unclassified),
        'by_folder': dict(collections.Counter(d['folder'] for d in decisions.values() if not d['problem'])),
        'by_course': dict(collections.Counter(d['course'] for d in decisions.values() if not d['problem'])),
        'fallback_names': sum(1 for d in decisions.values() if d.get('fallback')),
    }
    if references:
        refs = {asset_path_key(ref): i for i, r in records.items() for ref in [r['path'], *r.get('aliases', [])]}
        _, tokens = organize.scan_references(vault, library, records, refs, set())
        report['reference_check'] = organize.simulate(vault, report['moves'], tokens)
    return report


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--vault', type=Path, default=ROOT.parent / 'STEM Tutor')
    parser.add_argument('--out', type=Path, default=PLAN)
    parser.add_argument('--skip-references', action='store_true')
    args = parser.parse_args(argv)
    report = build_plan(args.vault, references=not args.skip_references)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(report, indent=1, ensure_ascii=False) + '\n')
    print(json.dumps({'out': str(args.out), 'loose': report['loose'], 'errors': len(report['errors']),
                      'reference_check': report.get('reference_check', {}).get('broken_count')}))


if __name__ == '__main__':
    main()
