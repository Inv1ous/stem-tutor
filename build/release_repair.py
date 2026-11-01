"""Publish independently reviewed display corrections against the exact active release.

This deliberately reads no authoring/build output and changes no existing alias,
assessment key, historical resource or whole-pack review binding.
"""
from __future__ import annotations

import copy
import fcntl
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import sys
import uuid

sys.path.insert(0, str(Path(__file__).resolve().parent))

from tutorlib.asset_library import AssetLibrary, write_asset
from tutorlib.store import Vault
from build import content_checks
from build.publish import _validate_pack_assets
from build.validate_pack import validate


def _encoded(value):
    return (json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2) + '\n').encode()


def proposal_digest(proposal: dict) -> str:
    return hashlib.sha256(_encoded(proposal)).hexdigest()


def _faults(pack, graph):
    faults = {json.dumps(fault, sort_keys=True) for fault in validate(pack, graph)}
    for checker in (content_checks.letter_problems, content_checks.latex_problems,
                    content_checks.debris_problems, content_checks.stacked_problems,
                    content_checks.precision_problems, content_checks.id_problems,
                    content_checks.chemical_spacing_problems):
        faults.update(checker.__name__ + ': ' + fault for fault in checker(pack))
    return faults


def _correct(pack, changes):
    candidate, seen = copy.deepcopy(pack), set()
    if not isinstance(changes, list) or not changes:
        raise ValueError('missing reviewed display corrections')
    for change in changes:
        selector = change.get('selector')
        # The supported seam is text displayed for an existing item. Identity,
        # grading, lesson forms and all other pack structure remain exact.
        if (not isinstance(selector, list) or len(selector) not in (3, 4)
                or selector[0] != 'items' or type(selector[1]) is not int or selector[1] < 0
                or not (selector[2:] in (['stem'], ['explanation'], ['source', 'ref'])
                        or len(selector) == 4 and selector[2] == 'options' and selector[3] in 'ABCD')):
            raise ValueError('unsupported display correction selector')
        key = tuple(selector)
        if key in seen:
            raise ValueError('duplicate correction selector')
        seen.add(key)
        if (not isinstance(change.get('old'), str) or not isinstance(change.get('new'), str)
                or change['old'] == change['new'] or not change.get('reason')):
            raise ValueError('incomplete display correction')
        try:
            parent = candidate
            for part in selector[:-1]:
                parent = parent[part]
            if parent[selector[-1]] != change['old']:
                raise ValueError('reviewed old text does not match active pack')
            parent[selector[-1]] = change['new']
        except (IndexError, KeyError, TypeError) as exc:
            raise ValueError('missing display correction selector') from exc
    return candidate


def repair_release(vault: Path, proposal: dict, review: dict) -> dict:
    """Validate everything first, register a fresh release, then switch CURRENT last.

    Review is a separate person's attestation bound to the complete proposal,
    including old release/file hashes and every replacement. It approves these
    corrections only; prior reviews remain bound to their original bytes.
    """
    vault = Path(vault).resolve(strict=True)
    digest = proposal_digest(proposal)
    if (proposal.get('format_version') != 1 or not proposal.get('author')
            or not review.get('reviewer') or review['reviewer'] == proposal['author']
            or review.get('accepted') is not True or review.get('proposal_sha256') != digest):
        raise ValueError('missing independent exact-proposal review')
    version = proposal.get('version', '')
    if not re.fullmatch(r'v[1-9][0-9]*', version):
        raise ValueError('invalid active release version')
    pointer = vault / '.tutor/packs/CURRENT'
    if pointer.is_symlink() or not pointer.is_file():
        raise ValueError('unsafe CURRENT pointer')
    lock_path = pointer.parent / '.release-repair.lock'
    if lock_path.is_symlink():
        raise ValueError('unsafe release lock')
    with lock_path.open('a') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        def unchanged():
            if pointer.is_symlink() or pointer.read_text().strip() != version:
                raise ValueError('active release changed during repair')
        unchanged()
        library = AssetLibrary(vault)
        prefix = f'Library/Releases/{version}/'
        root = vault / prefix
        if root.is_symlink() or not root.is_dir():
            raise ValueError('unsafe active release directory')
        records = {entry['path'][len(prefix):]: entry for entry in library.records().values()
                   if entry['path'].startswith(prefix)}
        physical = set()
        for folder, dirs, files in os.walk(root, followlinks=False):
            for name in dirs + files:
                if (Path(folder) / name).is_symlink():
                    raise ValueError('symlink in active release')
            physical.update((Path(folder) / name).relative_to(root).as_posix() for name in files)
        if not records or physical != records.keys():
            raise ValueError('active release contains unregistered or missing files')
        files = {relative: library.read(prefix + relative) for relative in records}
        required = {'manifest.json', 'plan.json', 'papers.json'}
        if not required <= files.keys() or json.loads(files['manifest.json']).get('version') != version:
            raise ValueError('incomplete active release')
        repairs = proposal.get('repairs')
        if not isinstance(repairs, list) or not repairs:
            raise ValueError('missing repairs')
        seen = set()
        for repair in repairs:
            relative = repair.get('path', '')
            path = PurePosixPath(relative)
            if (not re.fullmatch(r'specs/[^/]+/packs/[^/]+\.json', relative)
                    or '..' in path.parts or relative not in files or relative in seen):
                raise ValueError('invalid or duplicate repair pack path')
            seen.add(relative)
            if hashlib.sha256(files[relative]).hexdigest() != repair.get('before_sha256'):
                raise ValueError('active pack digest does not match review')
            for change in repair.get('changes', []):
                if 'evidence' in change:
                    evidence = change['evidence']
                    if (not isinstance(evidence, dict) or not evidence.get('pdf')
                            or hashlib.sha256(library.read(evidence['pdf'])).hexdigest() != evidence.get('sha256')):
                        raise ValueError('source evidence digest does not match review')
            original = json.loads(files[relative])
            candidate = _correct(original, repair.get('changes'))
            graph = json.loads(files[f'specs/{path.parts[1]}/graph.json'])
            if _faults(candidate, graph) - _faults(original, graph):
                raise ValueError('correction introduces content or validation faults')
            _validate_pack_assets(candidate, vault, location=relative)
            files[relative] = _encoded(candidate)
        releases = vault / 'Library/Releases'
        versions = [int(p.name[1:]) for directory in (releases, pointer.parent)
                    for p in directory.iterdir() if re.fullmatch(r'v[1-9][0-9]*', p.name)]
        target = f'v{max(versions) + 1}'
        manifest = json.loads(files['manifest.json'])
        manifest['version'] = target
        files['manifest.json'] = _encoded(manifest)
        attestation = {'proposal': proposal, 'review': review, 'prior_release': version}
        review_path = f'Library/Releases/{target}/repair-review-{digest[:16]}.json'
        # Catalog writes use asset_library's exclusive writer lock and atomic
        # replacement. Partial registration stays inactive after any failure.
        for relative, data in files.items():
            write_asset(vault, f'Library/Releases/{target}/{relative}', data,
                        metadata={'kind': 'Releases', 'version': target,
                                  'prior_release': version, 'repair_review': review_path})
        write_asset(vault, review_path, _encoded(attestation),
                    metadata={'kind': 'ReleaseRepairReview', 'proposal_sha256': digest})
        with Vault(vault).lock():
            unchanged()
            # Older consumers address the release through this adapter directly.
            # Create it before activation; any failure leaves CURRENT untouched.
            (pointer.parent / target).symlink_to(Path('../../Library/Releases') / target,
                                                target_is_directory=True)
            temporary = pointer.with_name('.CURRENT-' + uuid.uuid4().hex)
            try:
                with temporary.open('xb') as stream:
                    stream.write(target.encode())
                    stream.flush()
                    os.fsync(stream.fileno())
                unchanged()
                os.replace(temporary, pointer)
            finally:
                temporary.unlink(missing_ok=True)
        return {'version': target, 'prior_version': version, 'repaired_packs': sorted(seen),
                'review': review_path, 'proposal_sha256': digest}
