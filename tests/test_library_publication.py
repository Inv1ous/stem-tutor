"""Runtime prefers canonical Library releases but keeps legacy vault compatibility."""
import json

from fixtures import make_vault, GRAPH, PACK, PLAN
from tutorlib import packs, store


def test_canonical_release_preferred_when_present(tmp_path):
    root=make_vault(tmp_path)
    release=root/'Library/Releases/v1'
    packdir=release/'specs/9702/packs'; packdir.mkdir(parents=True)
    (release/'manifest.json').write_text(json.dumps({'version':'v1','specs':['9702']}))
    (release/'plan.json').write_text(json.dumps(PLAN))
    (release/'papers.json').write_text(json.dumps({'papers':[]}))
    (release/'specs/9702/graph.json').write_text(json.dumps(GRAPH))
    canonical={**PACK,'outline':'canonical release'}
    (packdir/'9702-2.1.json').write_text(json.dumps(canonical))
    reader=packs.Packs(store.Vault(root))
    assert reader.root==release
    assert reader.pack('9702-2.1')['outline']=='canonical release'


def test_legacy_vault_falls_back_until_current_canonical_release_exists(tmp_path):
    root=make_vault(tmp_path)
    reader=packs.Packs(store.Vault(root))
    assert reader.root==root/'.tutor/packs/v1'
    assert reader.pack('9702-2.1')['outline']==PACK['outline']


def test_new_current_pointer_switches_to_new_canonical_release(tmp_path):
    root=make_vault(tmp_path)
    releases=root/'Library/Releases'
    release=releases/'v2'; packdir=release/'specs/9702/packs'; packdir.mkdir(parents=True)
    (release/'manifest.json').write_text(json.dumps({'version':'v2','specs':['9702']}))
    (release/'plan.json').write_text(json.dumps(PLAN))
    (release/'papers.json').write_text(json.dumps({'papers':[]}))
    (release/'specs/9702/graph.json').write_text(json.dumps(GRAPH))
    (packdir/'9702-2.1.json').write_text(json.dumps({**PACK,'outline':'v2'}))
    (root/'.tutor/packs/CURRENT').write_text('v2')
    reader=packs.Packs(store.Vault(root))
    assert reader.root==release
    assert reader.pack('9702-2.1')['outline']=='v2'
