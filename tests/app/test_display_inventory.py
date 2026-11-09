"""Presentation inventories cannot become learner-dependent eligibility caches."""
from contextlib import contextmanager
import json
from types import SimpleNamespace

import pytest

from fixtures import make_vault
from tutorlib import model, packs, store
from tutor_app.display_inventory import get_inventory, resource_key


@pytest.fixture
def inventory_app(tmp_path, monkeypatch):
    root = make_vault(tmp_path)
    runtime = packs.Packs(store.Vault(root))
    app = SimpleNamespace(vault=root, tutor=SimpleNamespace(packs=runtime, state=model.new_state()))
    outer_calls, lookups = [], []
    original_request = runtime.topicals.request
    original_items = runtime.items_for

    @contextmanager
    def tracked():
        with original_request() as outer:
            if outer:
                outer_calls.append(True)
            yield outer

    def items(kc, **kwargs):
        lookups.append(kc)
        return original_items(kc, **kwargs)

    monkeypatch.setattr(runtime.topicals, 'request', tracked)
    monkeypatch.setattr(runtime, 'items_for', items)
    return app, outer_calls, lookups


def test_inventory_uses_one_proof_and_ignores_learner_state(inventory_app):
    app, proofs, lookups = inventory_app
    first = get_inventory(app)
    assert first.kinds['9702-2.1.1'] == frozenset({'mcq'})
    assert first.kinds['9702-2.1.4'] == frozenset({'numeric', 'structured'})
    assert len(proofs) == 1 and len(lookups) == len(app.tutor.packs.kcs)
    before = list(lookups)
    app.tutor.state['gaps'] = list(app.tutor.packs.kcs)
    app.tutor.state['kcs']['9702-2.1.1'] = {'n': 7, 'theta': -2}
    assert get_inventory(app) is first
    assert proofs == [True] and lookups == before
    assert first.resource_key == resource_key(app)


def test_inventory_is_immutable_and_contains_only_kind_sets(inventory_app):
    app, _, _ = inventory_app
    result = get_inventory(app)
    with pytest.raises(TypeError):
        result.kinds['another'] = frozenset({'mcq'})
    with pytest.raises(AttributeError):
        result.topical_chapters.add('another')
    with pytest.raises(AttributeError):
        result.resource_key = ()
    assert all(isinstance(k, str) and isinstance(v, frozenset)
               and all(isinstance(kind, str) for kind in v) for k, v in result.kinds.items())
    assert set(vars(result)) == {'kinds', 'topical_chapters', 'resource_key', 'source_courses'}


@pytest.mark.parametrize('changed', ['packs', 'topicals', 'catalog', 'packs_identity'])
def test_inventory_reloads_when_resource_key_changes(inventory_app, changed):
    app, proofs, lookups = inventory_app
    first = get_inventory(app)
    if changed == 'packs_identity':
        app.tutor.packs = packs.Packs(store.Vault(app.vault))
    else:
        relative = {'packs': '.tutor/packs/CURRENT', 'topicals': '.tutor/topicals/CURRENT',
                    'catalog': 'Library/catalog.json'}[changed]
        path = app.vault / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        if changed == 'catalog':
            path.write_text(json.dumps({'format_version': 1, 'assets': {}}))
        else:
            path.write_text(path.read_text() + '\n' if path.exists() else 'no-bank')
    second = get_inventory(app)
    assert second is not first and second.resource_key != first.resource_key
    if changed != 'packs_identity':
        assert len(proofs) == 2 and len(lookups) == 2 * len(app.tutor.packs.kcs)


def test_inventory_force_reloads_without_changing_resource_key(inventory_app):
    app, proofs, _ = inventory_app
    first = get_inventory(app)
    second = get_inventory(app, force=True)
    assert second is not first and second.resource_key == first.resource_key
    assert len(proofs) == 2
    assert get_inventory(app) is second


def test_inventory_discards_rollover_and_does_not_cache_it(inventory_app, monkeypatch):
    app, proofs, _ = inventory_app
    first = get_inventory(app)
    original = app.tutor.packs.items_for
    changed = []

    def raced(kc, **kwargs):
        rows = original(kc, **kwargs)
        if not changed:
            changed.append(True)
            pointer = app.vault / '.tutor/packs/CURRENT'
            pointer.write_text(pointer.read_text() + '\n')
        return rows
    monkeypatch.setattr(app.tutor.packs, 'items_for', raced)
    empty = get_inventory(app, force=True)
    assert not empty.kinds and not empty.topical_chapters
    recovered = get_inventory(app)
    assert recovered.kinds and recovered is not empty and recovered is not first
    assert len(proofs) == 3


def test_inventory_discards_failed_final_bank_gate(inventory_app, monkeypatch):
    app, _, _ = inventory_app
    original = app.tutor.packs.topicals.request_current
    monkeypatch.setattr(app.tutor.packs.topicals, 'request_current', lambda: False)
    empty = get_inventory(app)
    assert not empty.kinds and not empty.topical_chapters
    monkeypatch.setattr(app.tutor.packs.topicals, 'request_current', original)
    assert get_inventory(app).kinds


def test_resource_key_observes_dangling_pointer_replacement(inventory_app):
    app, _, _ = inventory_app
    pointer = app.vault / '.tutor/topicals/CURRENT'
    pointer.parent.mkdir(parents=True, exist_ok=True)
    pointer.symlink_to('missing-one')
    first = resource_key(app)
    pointer.unlink()
    pointer.symlink_to('missing-two')
    assert resource_key(app) != first
