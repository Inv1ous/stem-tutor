from datetime import datetime, timedelta, timezone

from tutorlib import model


def event(kind, when, **data):
    return {"type": kind, "ts": when.isoformat(), **data}


def test_terms_have_independent_fsrs_cards_and_rebuild_from_events():
    now = datetime(2026, 1, 1, tzinfo=timezone.utc)
    events = [event("term_introduced", now, term_id="term:A", kc="kc"),
              event("term_introduced", now, term_id="term:B", kc="kc")]
    state = model.new_state()
    for e in events:
        model.apply(state, e)
    assert state["terms"]["term:A"]["fsrs"] != state["terms"]["term:B"]["fsrs"]
    due = datetime.fromisoformat(state["terms"]["term:A"]["fsrs"]["due"])
    assert set(model.due_terms(state, due + timedelta(seconds=1))) == {"term:A", "term:B"}
    review = event("term_review", due + timedelta(seconds=1), term_id="term:A", rating="good")
    model.apply(state, review)
    assert model.due_terms(state, due + timedelta(seconds=1)) == ["term:B"]
    rebuilt = model.new_state()
    for e in events + [review]:
        model.apply(rebuilt, e)
    assert rebuilt["terms"] == state["terms"]


def test_reintroduced_term_preserves_previous_schedule():
    now = datetime(2026, 1, 1, tzinfo=timezone.utc)
    state = model.new_state()
    model.apply(state, event("term_introduced", now, term_id="term:A", kc="kc"))
    original = state["terms"]["term:A"]["fsrs"]
    model.apply(state, event("term_introduced", now + timedelta(days=20), term_id="term:A", kc="kc"))
    assert state["terms"]["term:A"]["fsrs"] == original


def test_conversation_misconception_is_replayable_without_fabricating_an_answer():
    now = datetime(2026, 1, 1, tzinfo=timezone.utc)
    e = event('misconception_noted', now, kc='kc', misconception='m1')
    state = model.apply(model.new_state(), e)
    assert 'm1' in state['kcs']['kc']['active_misconceptions']
    assert state['kcs']['kc']['mis_counts']['m1'] == 1
    assert state['kcs']['kc']['n'] == 0 and 'kc' in state['gaps']
    assert model.apply(model.new_state(), e) == state


def test_conversation_misconception_brings_scheduled_review_forward():
    now = datetime(2026, 1, 1, tzinfo=timezone.utc)
    state = model.new_state()
    state['kcs']['kc'] = model._new_kc()
    model._review(state, 'kc', True, now, 'maths')
    later = now + timedelta(days=20)
    state['kcs']['kc']['fsrs']['due'] = later.isoformat()
    event_time = now + timedelta(days=1)
    e = event('misconception_noted', event_time, kc='kc', misconception='m1')
    model.apply(state, e)
    assert datetime.fromisoformat(state['kcs']['kc']['fsrs']['due']) == event_time
    assert 'kc' in model.due_kcs(state, event_time + timedelta(seconds=1))
    # A later report must not postpone an already-due review.
    model.apply(state, event('misconception_noted', event_time + timedelta(days=1), kc='kc', misconception='m1'))
    assert datetime.fromisoformat(state['kcs']['kc']['fsrs']['due']) == event_time


def test_removed_term_does_not_create_an_unanswerable_review(monkeypatch):
    from types import SimpleNamespace
    from tutorlib import lesson, policy
    now = datetime(2026, 1, 1, tzinfo=timezone.utc)
    state = model.new_state()
    present = lesson.term_id("kc", "Current term")
    removed = lesson.term_id("kc", "Old term")
    for tid in (present, removed):
        model.apply(state, event("term_introduced", now, term_id=tid, kc="kc"))
    packs = SimpleNamespace(kcs={"kc": {}}, pack_for_kc=lambda kc: {"teach": {"kc": {"terms": [
        {"term": "Current term", "meaning": "Definition"}]}}})
    assert policy.review_terms(state, packs, now) == [present]
    assert removed in state["terms"]  # preserve history if a later content version restores it


def test_cached_teaching_card_terms_remain_reviewable(tmp_path):
    import json
    from types import SimpleNamespace
    from tutorlib import lesson, policy
    now = datetime(2026, 1, 1, tzinfo=timezone.utc)
    state = model.new_state()
    tid = lesson.term_id('kc', 'Cached term')
    model.apply(state, event('term_introduced', now, term_id=tid, kc='kc'))
    cache = tmp_path / '.tutor/cache/teach'
    cache.mkdir(parents=True)
    (cache / 'kc.json').write_text(json.dumps({'motivate': 'Why', 'establish': 'Idea', 'note': 'Note',
                                               'terms': [{'term': 'Cached term', 'meaning': 'Definition'}]}))
    packs = SimpleNamespace(kcs={'kc': {}}, vault_root=tmp_path, pack_for_kc=lambda kc: {})
    assert policy.review_terms(state, packs, now) == [tid]


def test_term_recall_prefers_published_card_and_ignores_torn_cache(tmp_path):
    import json
    from types import SimpleNamespace
    from tutorlib import lesson, policy
    now = datetime(2026, 1, 1, tzinfo=timezone.utc)
    state = model.new_state()
    current = lesson.term_id('kc', 'Published term')
    cached = lesson.term_id('kc', 'Cached term')
    for tid in (current, cached):
        model.apply(state, event('term_introduced', now, term_id=tid, kc='kc'))
    cache = tmp_path / '.tutor/cache/teach'
    cache.mkdir(parents=True)
    (cache / 'kc.json').write_text(json.dumps({'motivate': 'Why', 'establish': 'Idea', 'note': 'Note',
                                               'terms': [{'term': 'Cached term'}]}))
    packs = SimpleNamespace(kcs={'kc': {}}, vault_root=tmp_path, pack_for_kc=lambda kc: {
        'teach': {'kc': {'terms': [{'term': 'Published term'}]}}})
    assert policy.review_terms(state, packs, now) == [current]
    packs.pack_for_kc = lambda kc: {}
    (cache / 'kc.json').write_text('{broken')
    assert policy.review_terms(state, packs, now) == []
