"""One candidate batch shares a proof before durable question presentation."""
from contextlib import contextmanager
from datetime import datetime

from fixtures import make_vault
from tutorlib import session, store


def test_candidate_batch_authenticates_once_before_presentation(tmp_path, monkeypatch):
    tutor = session.Tutor(store.Vault(make_vault(tmp_path)),
                          now=lambda: datetime.fromisoformat('2026-09-29T17:00:00+08:00'))
    kcs = list(tutor.packs.kcs)
    tutor.start('test', focus=kcs)
    before = dict(tutor.session['presented'])
    original = tutor.packs.topicals.request
    authentications = []
    @contextmanager
    def tracked():
        with original() as outer:
            if outer:
                authentications.append(True)
            yield outer
    monkeypatch.setattr(tutor.packs.topicals, 'request', tracked)
    result = tutor._pick_batch(kcs, .6)
    assert len(result) == 2
    assert authentications == [True]
    assert tutor.session['presented'] == before


def test_candidate_batch_rejects_rollover_before_any_question_is_presented(tmp_path, monkeypatch):
    tutor = session.Tutor(store.Vault(make_vault(tmp_path)))
    kcs = list(tutor.packs.kcs)
    tutor.start('test', focus=kcs)
    original = tutor._pick
    def changed(*args, **kwargs):
        value = original(*args, **kwargs)
        pointer = tutor.vault.root / '.tutor/topicals/CURRENT'
        pointer.parent.mkdir(parents=True, exist_ok=True)
        pointer.write_text('new-unavailable-release')
        return value
    monkeypatch.setattr(tutor, '_pick', changed)
    assert tutor._pick_batch(kcs, .6) == []
    assert not tutor.session['presented']
