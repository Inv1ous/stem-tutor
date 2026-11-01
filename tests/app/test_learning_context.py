from types import SimpleNamespace

from tutor_app import prompts


def test_learning_context_uses_card_history_and_withholds_answers(monkeypatch):
    card = {"plain_words": "A proof is a logical argument.", "terms": [{"term": "integer", "meaning": "whole number"}],
            "diagram_descriptions": ["A proof proceeds from assumptions to conclusion."],
            "forms": [{"name": "Counterexample", "example": "EXAMPLE", "check": "CHECK SECRET", "answer": "ANSWER SECRET", "rubric": [{"point": "RUBRIC SECRET"}]}]}
    monkeypatch.setattr(prompts.lesson, "teach_card", lambda tutor, kc: card)
    tutor = SimpleNamespace(session={"presented": {}, "recent": []},
                            packs=SimpleNamespace(kcs={"kc": {"title": "Proof", "statement": "Use proof", "spec": "P2"}},
                                                  kc=lambda kc: {"title": "Proof", "statement": "Use proof", "spec": "P2"}),
                            state={"kcs": {"kc": {"n": 3, "active_misconceptions": ["m1"], "reviews": 2}}})
    packet = prompts.learn(tutor, "kc", "Please explain")
    assert "logical argument" in packet and "EXAMPLE" in packet and "m1" in packet
    assert "A proof proceeds from assumptions to conclusion." in packet
    assert all(secret not in packet for secret in ("CHECK SECRET", "ANSWER SECRET", "RUBRIC SECRET"))
    tutor.session["presented"] = {"1": {"inst": {"stem": "Open question"}}}
    tutor.session["recent"] = [{"n": 2, "stem": "Earlier question", "answer": "PAST ANSWER SECRET", "correct": True}]
    guarded = prompts.learn(tutor, "kc", "I am stuck")
    assert "Open question" in guarded
    assert "A proof proceeds from assumptions to conclusion." not in guarded
    assert all(secret not in guarded for secret in ("EXAMPLE", "CHECK SECRET", "ANSWER SECRET", "RUBRIC SECRET", "PAST ANSWER SECRET"))


def test_learning_context_includes_relevant_prerequisite_history(monkeypatch):
    monkeypatch.setattr(prompts.lesson, "teach_card", lambda tutor, kc: {"plain_words": "Current idea"})
    points = {"current": {"title": "Current", "statement": "Current point", "spec": "P2", "prereqs": ["earlier"]},
              "earlier": {"title": "Earlier idea", "statement": "Earlier point", "spec": "P2"}}
    tutor = SimpleNamespace(session={"presented": {}, "recent": []},
                            packs=SimpleNamespace(kcs=points, kc=points.__getitem__),
                            state={"kcs": {"current": {"n": 2}, "earlier": {"n": 4, "reviews": 1,
                                    "active_misconceptions": ["m2"], "last_rating": 1}}, "gaps": ["earlier"]})
    packet = prompts.learn(tutor, "current", "I am confused")
    assert "Earlier idea" in packet and '"m2"' in packet and '"gap": true' in packet
    assert '"last_rating": 1' in packet


def test_learning_context_resolves_misconceptions_by_chapter_without_open_answer_leaks(monkeypatch):
    monkeypatch.setattr(prompts.lesson, "teach_card", lambda tutor, kc: {})
    points = {"current": {"title": "Current", "statement": "Point", "spec": "P2", "subtopic": "P2-1", "prereqs": ["earlier"]},
              "earlier": {"title": "Earlier", "statement": "Point", "spec": "P2", "subtopic": "P2-2"}}
    misconceptions = {("P2-1", "m1"): {"id": "m1", "kc": "current", "statement": "Current misconception"},
                      ("P2-2", "m1"): {"id": "m1", "kc": "earlier", "statement": "Earlier misconception"}}
    tutor = SimpleNamespace(session={"presented": {}, "recent": []},
                            packs=SimpleNamespace(kcs=points, kc=points.__getitem__,
                                                  misconception=lambda sub, ident: misconceptions.get((sub, ident))),
                            state={"kcs": {"current": {"active_misconceptions": ["m1"]},
                                           "earlier": {"active_misconceptions": ["m1"]}}})
    packet = prompts.learn(tutor, "current", "Explain")
    assert "Current misconception" in packet and "Earlier misconception" in packet
    tutor.session['presented'] = {"1": {"inst": {"stem": "Open question"}}}
    guarded = prompts.learn(tutor, "current", "Explain")
    assert "Current misconception" not in guarded and "Earlier misconception" not in guarded


def test_learning_context_withholds_examples_when_question_is_queued(monkeypatch):
    monkeypatch.setattr(prompts.lesson, 'teach_card', lambda tutor, kc: {
        'forms': [{'name': 'Proof', 'example': 'EXAMPLE SECRET'}],
        'diagram_descriptions': ['DIAGRAM SECRET'],
        'misconceptions': [{'idea': 'SECRET MISCONCEPTION'}]})
    tutor = SimpleNamespace(session={'presented': {}, 'queue': {'2': {'inst': {'stem': 'PENDING SECRET'}}},
                                     'recent': []},
                            packs=SimpleNamespace(kcs={'kc': {'title': 'Proof', 'statement': 'Use proof', 'spec': 'P2'}},
                                                  kc=lambda kc: {'title': 'Proof', 'statement': 'Use proof', 'spec': 'P2'}),
                            state={'kcs': {}})
    packet = prompts.learn(tutor, 'kc', 'Explain')
    for secret in ('EXAMPLE SECRET', 'DIAGRAM SECRET', 'SECRET MISCONCEPTION', 'PENDING SECRET'):
        assert secret not in packet


def test_learning_context_includes_only_current_idea_lesson_mistakes(monkeypatch):
    monkeypatch.setattr(prompts.lesson, 'teach_card', lambda tutor, kc: {})
    points = {'current': {'title': 'Current', 'statement': 'Point', 'spec': 'P2'}}
    tutor = SimpleNamespace(session={'presented': {}, 'recent': [], 'cursor': 0,
        'blocks': [{'kind': 'node', 'kc': 'current', 'mistakes': ['Student omitted a case.']},
                   {'kind': 'node', 'kc': 'other', 'mistakes': ['UNRELATED SECRET']}]},
        packs=SimpleNamespace(kcs=points, kc=points.__getitem__), state={'kcs': {}})
    packet = prompts.learn(tutor, 'current', 'What did I miss?')
    assert 'Student omitted a case.' in packet
    assert 'UNRELATED SECRET' not in packet
    tutor.session['queue'] = {'1': {'inst': {'stem': 'pending'}}}
    assert 'Student omitted a case.' not in prompts.learn(tutor, 'current', 'Explain')


def test_learning_context_reports_current_gap_and_probe_evidence(monkeypatch):
    monkeypatch.setattr(prompts.lesson, 'teach_card', lambda tutor, kc: {})
    points = {'kc': {'title': 'Proof', 'statement': 'Use proof', 'spec': 'P2'}}
    tutor = SimpleNamespace(session={'presented': {}, 'recent': [], 'probe': {'kc': {'ok': False, 'conf': 1}}},
        packs=SimpleNamespace(kcs=points, kc=points.__getitem__),
        state={'kcs': {'kc': {'n': 2}}, 'gaps': ['kc']})
    packet = prompts.learn(tutor, 'kc', 'Teach me')
    assert '"gap": true' in packet
    assert '"ok": false' in packet and '"conf": 1' in packet


def test_skipped_question_context_marks_it_unattempted_without_requesting_an_answer():
    from tutor_app.prompts import _marked
    text = _marked({'stem': 'Find x.', 'response': "don't know", 'answer': '', 'correct': False}, full=True)
    assert 'not attempted' in text.lower()
    assert 'do not reveal' in text.lower()
    assert 'the answer is' not in text.lower()
