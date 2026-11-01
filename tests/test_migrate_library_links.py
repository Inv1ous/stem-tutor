"""Historical link migration is exercised only in an isolated temporary vault."""
import hashlib
import json
from pathlib import Path

import pytest

from build import migrate_library_links as migration


@pytest.fixture
def vault(tmp_path):
    root=tmp_path/'STEM Tutor'
    data=b'<svg>asset</svg>'
    target=root/'Library/Courses/P1/Diagrams/curve.svg'
    target.parent.mkdir(parents=True)
    target.write_bytes(data)
    catalog={'format_version':1,'assets':{'curve':{
        'path':'Library/Courses/P1/Diagrams/curve.svg',
        'sha256':hashlib.sha256(data).hexdigest(),
        'aliases':['Assets/P1/curve.svg','build/out/assets/P1/curve.svg']}}}
    (root/'Library/catalog.json').write_text(json.dumps(catalog))
    return root,target


def put(vault, rel, text):
    path=vault/rel; path.parent.mkdir(parents=True,exist_ok=True); path.write_text(text)
    return path


def test_rewrites_wikilinks_images_and_markdown_destinations_preserving_surrounding_syntax(vault):
    root,_=vault
    note=put(root,'Lessons/P1.md',
      '![curve](Assets/P1/curve.svg "Caption")\n'
      '[[Assets/P1/curve.svg#part|diagram label]]\n'
      '![[build/out/assets/P1/curve.svg|320]]\n'
      '[PDF](build/out/assets/P1/curve.svg#page=2)\n')
    result=migration.plan(root)
    assert result['errors']==[] and len(result['edits'])==1
    edit=result['edits'][0]
    assert edit['replacements']==4
    updated=bytes.fromhex(edit['updated']).decode()
    assert '![curve](Library/Courses/P1/Diagrams/curve.svg "Caption")' in updated
    assert '[[Library/Courses/P1/Diagrams/curve.svg#part|diagram label]]' in updated
    assert '![[Library/Courses/P1/Diagrams/curve.svg|320]]' in updated
    assert '[PDF](Library/Courses/P1/Diagrams/curve.svg#page=2)' in updated
    assert note.read_text().startswith('![curve](Assets/')


def test_ignores_fenced_code_prose_and_unrecognized_paths(vault):
    root,_=vault
    note=put(root,'Lessons/P1.md',
      'Text mentioning Assets/P1/curve.svg remains prose.\n'
      '`[inline](Assets/P1/curve.svg)`\n'
      '```md\n![code](Assets/P1/curve.svg)\n```\n'
      '[other](Assets/P1/other.svg)\n')
    result=migration.plan(root)
    assert result['edits']==[]
    assert note.read_text().count('Assets/P1/curve.svg')==3


def test_only_markdown_outside_library_and_private_state_is_scanned(vault):
    root,target=vault
    put(root,'Library/source.md','[x](Assets/P1/curve.svg)')
    put(root,'.tutor/event/state.md','[x](Assets/P1/curve.svg)')
    put(root,'state/lesson.md','[x](Assets/P1/curve.svg)')
    put(root,'Lessons/page.txt','[x](Assets/P1/curve.svg)')
    note=put(root,'Lessons/page.md','[x](Assets/P1/curve.svg)')
    result=migration.plan(root)
    assert [e['path'] for e in result['edits']]==['Lessons/page.md']
    assert target.read_bytes()==b'<svg>asset</svg>'


def test_apply_requires_backup_journal_and_is_idempotent(vault,tmp_path):
    root,_=vault
    note=put(root,'Lessons/page.md','![x](Assets/P1/curve.svg)\n')
    report=migration.plan(root)
    with pytest.raises(TypeError): migration.apply(report)
    journal=tmp_path/'Archive/link-migration'
    result=migration.apply(report,journal)
    assert result['updated_files']==1 and result['replacements']==1
    assert note.read_text()=='![x](Library/Courses/P1/Diagrams/curve.svg)\n'
    backup=next((journal/'originals').iterdir())
    assert backup.read_bytes()==b'![x](Assets/P1/curve.svg)\n'
    manifest=json.loads((journal/'journal.json').read_text())
    assert manifest['edits'][0]['sha256']==hashlib.sha256(backup.read_bytes()).hexdigest()
    assert migration.apply(migration.plan(root),journal)['updated_files']==0


def test_apply_refuses_concurrent_note_change_and_journals_original(vault,tmp_path):
    root,_=vault
    note=put(root,'Lessons/page.md','[x](Assets/P1/curve.svg)')
    report=migration.plan(root)
    note.write_text('user edit')
    with pytest.raises(ValueError,match='changed'):
        migration.apply(report,tmp_path/'Archive')
    assert note.read_text()=='user edit'
    backup=next((tmp_path/'Archive/originals').iterdir())
    assert backup.read_bytes()==b'[x](Assets/P1/curve.svg)'


def test_bad_catalog_digest_fails_closed(vault):
    root,target=vault
    target.write_bytes(b'tampered')
    with pytest.raises(ValueError,match='digest mismatch'):
        migration.plan(root)


def test_symlinked_note_is_never_traversed(vault,tmp_path):
    root,_=vault
    outside=tmp_path/'outside.md'; outside.write_text('[x](Assets/P1/curve.svg)')
    link=root/'Lessons.md'; link.symlink_to(outside)
    assert migration.plan(root)['edits']==[]
