"""Publish a new topical release that no longer shows confirmed data-sheet leaks.

prepare  reads the CURRENT topical release and the confirmed leak ids (LEAK_REFERENCED rows of
         Work/Preparation/question-leaks/ai-review.json, or --leaks), and writes a batch
         (bank.json + report.json) where every item keeps its exact JSON except that image paths
         resolving to a leak are dropped from `images`/`image`. An item whose only image is a leak
         is kept and listed under `flagged_items` in the report. The report binds the CURRENT
         version it was prepared against and lists every removed (item, bare asset id, sha256) -
         never a path, which would count as a citation and keep the leak referenced.
publish  validates and publishes the batch through topicals.publish (validate_bank, debris
         checks, catalogued immutable release, compare-and-swap of CURRENT), pinning the exact
         bank and report bytes. Older releases stay untouched; retire them with
         retire_topical_releases.py.
restate, verify-restated, publish-restated, rollback
         display-text correction for stems that still point at a removed leak image (see the section
         above main); publication needs an independent review bound to the proposal digest.
"""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'build'))
sys.path.insert(0, str(ROOT / 'src'))
from tutorlib.asset_library import AssetLibrary  # noqa: E402

WORK = ROOT.parent / 'Work' / 'Preparation' / 'question-leaks'


def confirmed_leaks(review: Path) -> list[str]:
    data = json.loads(Path(review).read_text())
    return sorted(row['id'] for row in data['items'] if row['class'] == 'LEAK_REFERENCED')


def _asset_id(library: AssetLibrary, reference: str) -> str | None:
    from tutorlib.asset_library import _reference_key
    if reference.startswith('asset:'):
        return reference[6:]
    try:
        library.record(reference)  # verifies the reference is catalogued
        return library._references[_reference_key(reference)]
    except (ValueError, KeyError):
        return None


def prepare(vault: Path, leaks: list[str], output: Path) -> dict:
    vault = Path(vault).resolve()
    output = Path(output)
    if output.exists():
        raise ValueError('output already exists; use a fresh batch directory')
    library = AssetLibrary(vault)
    records = library.records()
    missing = [leak for leak in leaks if leak not in records]
    if missing:
        raise ValueError(f'unknown leak ids: {missing}')
    current = (vault / '.tutor/topicals/CURRENT').read_text().strip()
    canonical = f'Library/Shared/Topicals/Releases/{current}/bank.json'
    raw = library.read(canonical)
    bank = json.loads(raw)
    leakset, removed, flagged, items = set(leaks), [], [], []
    for item in bank['items']:
        new = copy.deepcopy(item)
        dropped = []
        if isinstance(new.get('images'), list):
            kept = []
            for ref in new['images']:
                ident = _asset_id(library, ref) if isinstance(ref, str) else None
                (dropped if ident in leakset else kept).append(ref)
            new['images'] = kept
        if isinstance(new.get('image'), str) and _asset_id(library, new['image']) in leakset:
            dropped.append(new.pop('image'))
        if dropped:
            for ref in dict.fromkeys(dropped):
                ident = _asset_id(library, ref)
                # Bare id + digest only: a path or asset: token here would itself cite the leak.
                removed.append({'item': item['id'], 'asset_id': ident, 'sha256': records[ident]['sha256']})
            if not new.get('images') and not new.get('image'):
                flagged.append({'item': item['id'], 'reason': 'its only image was a data-sheet leak'})
        items.append(new)
    out = {**{k: v for k, v in bank.items() if k != 'items'}, 'items': items}
    report = {'preparation': {'expected_current': current},
              'leak_removal': {'method': 'Dropped confirmed data-sheet/periodic-table/constants images from the '
                                         'items that cited them; all other item bytes unchanged.',
                               'previous_bank_sha256': hashlib.sha256(raw).hexdigest(),
                               'leak_ids': sorted(leakset), 'removed': removed, 'flagged_items': flagged,
                               'changed_items': len({r['item'] for r in removed}),
                               'preserved_items': len(items)}}
    output.mkdir(parents=True)
    (output / 'bank.json').write_text(json.dumps(out, ensure_ascii=False, indent=1))
    (output / 'report.json').write_text(json.dumps(report, ensure_ascii=False, indent=1))
    return {'output': str(output), 'expected_current': current, 'changed_items': report['leak_removal']['changed_items'],
            'removed_refs': len(removed), 'flagged': flagged}


def publish(batch: Path, vault: Path) -> dict:
    import topicals
    batch = Path(batch)
    bank_sha = hashlib.sha256((batch / 'bank.json').read_bytes()).hexdigest()
    report_sha = hashlib.sha256((batch / 'report.json').read_bytes()).hexdigest()
    return topicals.publish(batch, vault, expected_bank_sha256=bank_sha, expected_report_sha256=report_sha)


# ---- display-text correction for stems that still point at a removed leak image ----
# restate          prepares bank.json + proposal.json from CURRENT: only `stem` changes, and only on items whose stem
#                  is exactly OLD_STEM and that content_checks.dangling_image_problems flags (one image left).
# publish-restated needs an independent review bound to the proposal digest (reviewer != author, accepted),
#                  re-checks that every other byte of every item is unchanged, then publishes via topicals.publish.
# rollback         compare-and-swap CURRENT from the restated release back to the release it was prepared against.
OLD_STEM = ('Read the question and original options in the first source image. '
            'An official periodic-table reference is provided in the next image when needed.')
NEW_STEM = 'Read the question and original options in the source image. Use the periodic table in your Data Booklet.'


def _encoded(value) -> bytes:
    return (json.dumps(value, ensure_ascii=False, sort_keys=True, indent=1) + '\n').encode()


def proposal_digest(proposal: dict) -> str:
    return hashlib.sha256(_encoded(proposal)).hexdigest()


def restate(vault: Path, output: Path, author: str) -> dict:
    import content_checks
    vault, output = Path(vault).resolve(), Path(output)
    if output.exists():
        raise ValueError('output already exists; use a fresh batch directory')
    current = (vault / '.tutor/topicals/CURRENT').read_text().strip()
    raw = AssetLibrary(vault).read(f'Library/Shared/Topicals/Releases/{current}/bank.json')
    bank = json.loads(raw)
    changes, items = [], []
    for item in bank['items']:
        new = copy.deepcopy(item)
        if item.get('stem') == OLD_STEM and content_checks.dangling_image_problems(item):
            new['stem'] = NEW_STEM
            changes.append({'item': item['id'], 'field': 'stem', 'old': OLD_STEM, 'new': NEW_STEM})
        items.append(new)
    if not changes:
        raise ValueError('no item carries the dangling periodic-table instruction')
    candidate = {**{k: v for k, v in bank.items() if k != 'items'}, 'items': items}
    left = [p for i in items for p in content_checks.dangling_image_problems(i)]
    if left:
        raise ValueError(f'dangling image text remains after restating: {left[:3]}')
    bank_bytes = json.dumps(candidate, ensure_ascii=False, indent=1).encode()
    proposal = {'format_version': 1, 'author': author, 'expected_current': current,
                'previous_bank_sha256': hashlib.sha256(raw).hexdigest(),
                'candidate_bank_sha256': hashlib.sha256(bank_bytes).hexdigest(),
                'reason': 'The periodic-table/constants image these stems pointed at was a confirmed data-sheet leak and '
                          'was removed; the app has no built-in reference viewer, so the stem names the Data Booklet.',
                'changes': changes}
    output.mkdir(parents=True)
    (output / 'bank.json').write_bytes(bank_bytes)
    (output / 'proposal.json').write_bytes(_encoded(proposal))
    return {'output': str(output), 'expected_current': current, 'changed_items': len(changes),
            'proposal_sha256': proposal_digest(proposal)}


def verify_restated(vault: Path, batch: Path) -> dict:
    """Mechanical check: the batch bank equals the prepared-against bank except the proposed stems."""
    batch = Path(batch)
    proposal = json.loads((batch / 'proposal.json').read_text())
    bank_raw = (batch / 'bank.json').read_bytes()
    if hashlib.sha256(bank_raw).hexdigest() != proposal['candidate_bank_sha256']:
        raise ValueError('batch bank differs from the proposal')
    raw = AssetLibrary(Path(vault).resolve()).read(
        f"Library/Shared/Topicals/Releases/{proposal['expected_current']}/bank.json")
    if hashlib.sha256(raw).hexdigest() != proposal['previous_bank_sha256']:
        raise ValueError('prepared-against bank changed')
    old, new = json.loads(raw), json.loads(bank_raw)
    changes = {c['item']: c for c in proposal['changes']}
    if ({k: v for k, v in old.items() if k != 'items'} != {k: v for k, v in new.items() if k != 'items'}
            or [i['id'] for i in old['items']] != [i['id'] for i in new['items']]):
        raise ValueError('bank structure or item order changed')
    seen = 0
    for before, after in zip(old['items'], new['items']):
        change = changes.get(before['id'])
        expected = copy.deepcopy(before)
        if change:
            if change['field'] != 'stem' or before.get('stem') != change['old']:
                raise ValueError(f"proposal old text does not match {before['id']}")
            expected['stem'] = change['new']
            seen += 1
        if json.dumps(expected, sort_keys=True) != json.dumps(after, sort_keys=True):
            raise ValueError(f"unproposed change in {before['id']}")
    if seen != len(changes):
        raise ValueError('proposal names items absent from the bank')
    return proposal


def publish_restated(batch: Path, vault: Path, review_path: Path) -> dict:
    import topicals
    batch = Path(batch)
    proposal = verify_restated(vault, batch)
    review = json.loads(Path(review_path).read_text())
    if (not review.get('reviewer') or review['reviewer'] == proposal['author'] or review.get('accepted') is not True
            or review.get('proposal_sha256') != proposal_digest(proposal)):
        raise ValueError('missing independent exact-proposal review')
    report = {'preparation': {'expected_current': proposal['expected_current']},
              'display_correction': {'method': 'Only the listed stems changed; ids, keys, options, images and all '
                                               'other item bytes are unchanged.',
                                     'proposal_sha256': proposal_digest(proposal), 'proposal': proposal,
                                     'review': review}}
    (batch / 'report.json').write_bytes(_encoded(report))
    bank_sha = hashlib.sha256((batch / 'bank.json').read_bytes()).hexdigest()
    report_sha = hashlib.sha256((batch / 'report.json').read_bytes()).hexdigest()
    return topicals.publish(batch, vault, expected_bank_sha256=bank_sha, expected_report_sha256=report_sha)


def rollback(vault: Path, release: str, to: str) -> dict:
    import topicals
    vault = Path(vault).resolve()
    library = AssetLibrary(vault)
    library.read(f'Library/Shared/Topicals/Releases/{to}/bank.json')  # the target must still be catalogued
    topicals._activate_current(vault / '.tutor/topicals', to, release)
    return {'current': to, 'previous': release}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest='command', required=True)
    p = sub.add_parser('prepare')
    p.add_argument('--vault', type=Path, default=ROOT.parent / 'STEM Tutor')
    p.add_argument('--review', type=Path, default=WORK / 'ai-review.json')
    p.add_argument('--leaks', help='comma-separated asset ids (overrides --review)')
    p.add_argument('--output', type=Path, required=True)
    p = sub.add_parser('publish')
    p.add_argument('batch', type=Path)
    p.add_argument('--vault', type=Path, default=ROOT.parent / 'STEM Tutor')
    p = sub.add_parser('restate')
    p.add_argument('--vault', type=Path, default=ROOT.parent / 'STEM Tutor')
    p.add_argument('--output', type=Path, required=True)
    p.add_argument('--author', required=True)
    p = sub.add_parser('verify-restated')
    p.add_argument('batch', type=Path)
    p.add_argument('--vault', type=Path, default=ROOT.parent / 'STEM Tutor')
    p = sub.add_parser('publish-restated')
    p.add_argument('batch', type=Path)
    p.add_argument('--review', type=Path, required=True)
    p.add_argument('--vault', type=Path, default=ROOT.parent / 'STEM Tutor')
    p = sub.add_parser('rollback')
    p.add_argument('--release', required=True, help='the CURRENT release to leave')
    p.add_argument('--to', required=True, help='the release to make CURRENT again')
    p.add_argument('--vault', type=Path, default=ROOT.parent / 'STEM Tutor')
    args = parser.parse_args(argv)
    if args.command == 'prepare':
        leaks = args.leaks.split(',') if args.leaks else confirmed_leaks(args.review)
        result = prepare(args.vault, leaks, args.output)
    elif args.command == 'restate':
        result = restate(args.vault, args.output, args.author)
    elif args.command == 'verify-restated':
        proposal = verify_restated(args.vault, args.batch)
        result = {'verified': True, 'changed_items': len(proposal['changes']),
                  'proposal_sha256': proposal_digest(proposal)}
    elif args.command == 'publish-restated':
        result = publish_restated(args.batch, args.vault, args.review)
    elif args.command == 'rollback':
        result = rollback(args.vault, args.release, args.to)
    else:
        result = publish(args.batch, args.vault)
    print(json.dumps(result, indent=1))


if __name__ == '__main__':
    main()
