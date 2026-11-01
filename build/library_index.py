"""Generate human navigation for the shared Library without changing resources."""
from __future__ import annotations

import argparse
from collections import defaultdict
from pathlib import Path
import re
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))
from tutorlib.asset_library import AssetLibrary  # noqa: E402
from tutorlib.store import write_text  # noqa: E402

MARKER = '<!-- generated: stem-tutor-library-index -->'


def _save(path: Path, text: str) -> None:
    if path.is_symlink() or any(parent.is_symlink() for parent in path.parents):
        raise ValueError(f'navigation destination must not use symlinks: {path}')
    before = path.read_text() if path.exists() else None
    if before is not None and not before.startswith(MARKER):
        raise ValueError(f'navigation destination contains unrelated content: {path}')
    write_text(path, text, expect=before)


def generate(vault: Path) -> dict:
    vault = vault.resolve(strict=True)
    library = AssetLibrary(vault)
    groups = defaultdict(lambda: defaultdict(list))
    for identifier, record in library.records().items():
        course = record.get('course') or 'Shared'
        if not isinstance(course, str) or not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_-]*', course):
            raise ValueError('invalid course identifier in navigation metadata')
        kind = record.get('kind', 'Resources')
        area = kind.split('/')[0]
        if area not in {'Sources', 'Questions', 'Diagrams', 'Notes'}:
            area = 'Other resources'
        groups[course][area].append((identifier, record))
    pages = 0
    home = [MARKER, '# Learning Library', '',
            'All reusable course resources and source files are resolved through this library.', '',
            'Resource availability and course-content review are separate. Preparation evidence remains in the workspace Work folder.', '',
            '## Courses', '']
    for course, areas in sorted(groups.items()):
        folder = Path('Library/Shared') if course == 'Shared' else Path('Library/Courses') / course
        total = sum(len(rows) for rows in areas.values())
        home.append(f'- [[{folder.as_posix()}/Index|{course}]] — {total} resources')
        overview = [MARKER, f'# {course} library', '', '[[Library/Home|All courses]]', '']
        for area, rows in sorted(areas.items()):
            relative = folder / ('Resources' if area == 'Other resources' else area) / 'Index.md'
            overview.append(f'- [[{relative.with_suffix("").as_posix()}|{area}]] — {len(rows)} resources')
            text = [MARKER, f'# {course}: {area}', '', f'[[{folder.as_posix()}/Index|Course library]]', '']
            by_kind = defaultdict(list)
            for identifier, record in rows:
                by_kind[record.get('kind', 'Resources')].append((identifier, record))
            for kind, entries in sorted(by_kind.items()):
                text += ['## ' + kind, '']
                for _, record in sorted(entries, key=lambda item: item[1]['path']):
                    label = '/'.join(Path(record['path']).parts[-2:]).replace('|', '-')
                    text.append(f'- [[{record["path"]}|{label}]]')
                text.append('')
            _save(vault / relative, '\n'.join(text) + '\n'); pages += 1
        _save(vault / folder / 'Index.md', '\n'.join(overview) + '\n'); pages += 1
    home += ['', '## Storage', '',
             '- Course resources: `Courses/<course-id>/Sources`, `Questions`, `Diagrams`, `Notes`.',
             '- Shared resources: `Shared`.', '- Published course snapshots: `Releases`.',
             '- `catalog.json` stores identities, hashes, provenance and legacy aliases.', '']
    _save(vault / 'Library/Home.md', '\n'.join(home)); pages += 1
    return {'navigation_pages': pages, 'resource_records': sum(sum(len(r) for r in g.values()) for g in groups.values())}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--vault', type=Path, required=True)
    print(generate(parser.parse_args().vault))
