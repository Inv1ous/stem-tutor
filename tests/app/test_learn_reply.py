from tutor_app.learn_reply import render_reply


def test_active_misconception_selection_uses_only_tracked_card_entries():
    from tutor_app.learn_reply import active_misconception_selection
    cards = {'P2-1.1': {'misconceptions': [
        {'id': 'm1', 'idea': 'A sample proves a claim.', 'temptation': 'It worked once.', 'fix': 'Cover the domain.'},
        {'id': 'm2', 'idea': 'The domain is irrelevant.', 'temptation': 'The algebra looks general.', 'fix': 'Check assumptions.'}]}}
    state = {'kcs': {'P2-1.1': {'active_misconceptions': ['m2', 'missing']}}}
    assert active_misconception_selection('What have I misunderstood?', 'P2-1.1', cards, state) == {
        'sections': ['P2-1.1|misconception:1']}
    assert active_misconception_selection('Explain proof', 'P2-1.1', cards, state) is None
    assert active_misconception_selection('What have I misunderstood?', 'P2-1.1', cards, {'kcs': {}}) == {'sections': []}


def test_active_misconception_selection_can_revisit_prerequisites():
    from tutor_app.learn_reply import active_misconception_selection
    entry = lambda ident: {'id': ident, 'idea': 'Mistake', 'temptation': 'Temptation', 'fix': 'Fix'}
    cards = {'P2-1.1': {'misconceptions': [entry('current')]},
             'P1-1.1': {'misconceptions': [entry('prior')]},
             'P2-1.2': {'misconceptions': [entry('unrelated')]}}
    state = {'kcs': {kc: {'active_misconceptions': [ident]} for kc, ident in
                     [('P2-1.1', 'current'), ('P1-1.1', 'prior'), ('P2-1.2', 'unrelated')]}}
    result = active_misconception_selection('What earlier misconceptions should I review?', 'P2-1.1', cards, state,
                                            prerequisites=['P1-1.1'])
    assert result == {'sections': ['P1-1.1|misconception:0']}


def test_explicit_misconception_match_does_not_treat_questions_as_assertions():
    from tutor_app.learn_reply import explicit_misconception
    card = {'misconceptions': [{'id': 'm1', 'idea': 'Several examples prove a universal claim.',
                                'temptation': 'The examples agree.', 'fix': 'Use a general argument.'}]}
    assert explicit_misconception('I think several examples prove a universal claim.', card) == 'm1'
    assert explicit_misconception('Do several examples prove a universal claim?', card) is None
    assert explicit_misconception('I do not think several examples prove a universal claim.', card) is None


def test_try_first_requires_confident_success_no_gap_and_general_request():
    from tutor_app.learn_reply import try_first
    card = {'self_explain': 'Which assumption would you check?'}
    session = {'probe': {'kc': {'ok': True, 'conf': 3}}, 'learn_history': {}}
    state = {'gaps': []}
    assert try_first('How should I approach this?', 'kc', card, session, state) == card['self_explain']
    assert try_first('What does domain mean?', 'kc', card, session, state) is None
    assert try_first('How should I approach this?', 'kc', card, session, {'gaps': ['kc']}) is None
    assert try_first('How should I approach this?', 'kc', card, session,
                     {'gaps': [], 'kcs': {'kc': {'active_misconceptions': ['m1']}}}) is None
    session['goal'] = 'scratch'
    assert try_first('How should I approach this?', 'kc', card, session, state) is None
    session.pop('goal')
    session['probe']['kc']['conf'] = 1
    assert try_first('How should I approach this?', 'kc', card, session, state) is None
    session['probe']['kc']['conf'] = 3
    session['learn_history'] = {'kc': [{'question': 'Earlier', 'reply': 'Earlier'}]}
    assert try_first('How should I approach this?', 'kc', card, session, state) is None


def test_exact_term_lookup_prefers_current_card_and_avoids_ambiguous_related_terms():
    from tutor_app.learn_reply import exact_term_selection
    def term(name, meaning):
        return {'term': name, 'meaning': meaning, 'notation': 'none', 'spoken': name}
    cards = {'a': {'terms': [term('Domain', 'Allowed values')]},
             'b': {'terms': [term('Domain', 'Another definition'), term('Counterexample', 'Allowed failure')]},
             'c': {'terms': [term('Counterexample', 'Another explanation')]}}
    assert exact_term_selection('What does domain mean?', 'a', cards) == {'sections': ['a|term:0']}
    assert exact_term_selection('What is the domain?', 'a', cards) == {'sections': ['a|term:0']}
    assert exact_term_selection('What is the counterexample?', 'a', cards) is None
    cards['a']['terms'].append(term('The Domain', 'A separately named term'))
    assert exact_term_selection('What is the domain?', 'a', cards) == {'sections': ['a|term:1']}
    assert exact_term_selection('Define counterexample', 'a', cards) is None
    assert exact_term_selection('Why is the domain important?', 'a', cards) is None
    assert exact_term_selection('What does missing mean?', 'a', cards) is None


def test_exact_term_lookup_understands_notation_without_guessing_ambiguities():
    from tutor_app.learn_reply import exact_term_selection
    cards = {'a': {'terms': [{'term': 'Integer', 'meaning': 'A whole number', 'notation': 'ℤ', 'spoken': 'integers'}]},
             'b': {'terms': [{'term': 'Complex numbers', 'meaning': 'Numbers', 'notation': 'ℂ', 'spoken': 'complex numbers'}]}}
    assert exact_term_selection('What does ℤ mean?', 'a', cards) == {'sections': ['a|term:0']}
    assert exact_term_selection('What is ℂ?', 'a', cards) == {'sections': ['b|term:0']}
    cards['b']['terms'].append({'term': 'Other', 'notation': 'ℂ'})
    assert exact_term_selection('What is ℂ?', 'a', cards) is None
    assert exact_term_selection('What is none?', 'a', {'a': {'terms': [{'term': 'Term', 'notation': 'none'}]}}) is None


def test_checked_arithmetic_request_returns_only_verified_exact_results():
    from tutor_app.learn_reply import checked_arithmetic_request
    assert checked_arithmetic_request('Calculate 2 + 3 * 4') == '$2+3\\cdot 4 = 14$'
    assert checked_arithmetic_request('Calculate (1 + 2) / 4') == '$\\frac{1+2}{4} = \\frac{3}{4}$'
    assert checked_arithmetic_request('Calculate 2^3') == '$2^{3} = 8$'
    for question in ('Calculate x+1', 'Calculate 1/0', 'Calculate 2^999999',
                     'Calculate __import__("os")', 'Why is 2+3 five?', 'Calculate 1 +'):
        assert checked_arithmetic_request(question) is None


def test_checked_arithmetic_withholds_when_verification_unavailable(monkeypatch):
    from tutor_app import learn_reply
    monkeypatch.setattr(learn_reply, 'check_equality', lambda left, right: None)
    assert learn_reply.checked_arithmetic_request('Calculate 2+3') is None


def test_published_related_cards_excludes_cached_and_unrelated_content():
    from types import SimpleNamespace
    from tutor_app.learn_reply import published_related_cards
    graph = {'s.1': {'subtopic': 's', 'prereqs': ['p.1']},
             's.2': {'subtopic': 's'}, 'p.1': {'subtopic': 'p'}, 'other': {'subtopic': 'z'}}
    packs = {'s.1': {'teach': {'s.1': {'plain_words': 'Current'}, 's.2': {'plain_words': 'Sibling'},
                                'other': {'plain_words': 'Unrelated'}}},
             'p.1': {'teach': {'p.1': {'plain_words': 'Prerequisite'}}}}
    packs['s.2'] = packs['s.1']
    tutor = SimpleNamespace(packs=SimpleNamespace(kcs=graph, pack_for_kc=lambda kc: packs.get(kc)))
    result = published_related_cards(tutor, 's.1')
    assert set(result) == {'s.1', 's.2', 'p.1'}
    assert published_related_cards(tutor, 'missing') == {}
    packs['s.1']['teach']['s.2']['source'] = 'ai'
    assert 's.2' not in published_related_cards(tutor, 's.1')


def test_source_selection_can_reference_only_supplied_related_cards():
    from tutor_app.learn_reply import related_card_options, render_related_selection, selection_prompt
    cards = {'P2-1.1': {'plain_words': 'A proof uses reasoning.'},
             'P2-1.3': {'terms': [{'term': 'Counterexample', 'meaning': 'An allowed case that disproves a universal claim.',
                                    'notation': 'none', 'spoken': 'counterexample'}],
                        'forms': [{'answer': 'SECRET'}]}}
    choices = related_card_options(cards)
    assert 'P2-1.3|term:0' in choices and 'SECRET' not in str(choices)
    prompt = selection_prompt('What is a counterexample?', cards, 'Previously unsure of domain.')
    assert 'at most six section IDs' in prompt
    assert 'short explanation first' in prompt and 'more detail' in prompt
    assert 'P2-1.3|term:0' in prompt and 'Previously unsure' in prompt and 'SECRET' not in prompt
    assert 'empty' in prompt.lower()
    prompt = selection_prompt('Why?', cards, 'Profile', recent_questions='Reviewed: ✓ first; ✗ second')
    assert 'Reviewed: ✓ first; ✗ second' in prompt
    long_context = 'x' * 5000
    prompt = selection_prompt('Why?', cards, long_context, 'Student: recent question\nTutor: recent reply')
    assert 'recent question' in prompt and 'recent reply' in prompt
    text, problem = render_related_selection({'sections': ['P2-1.3|term:0']}, cards)
    assert problem is None and 'disproves' in text
    for selection in ({'sections': ['P2-1.3|forms:0']}, {'sections': ['P2-1.4|term:0']},
                      {'sections': ['P2-1.3|term:0', 'P2-1.3|term:0']},
                      {'sections': ['P2-1.3|term:0'], 'text': 'invented'}):
        assert render_related_selection(selection, cards)[1]


def test_source_backed_reply_selects_only_allowed_card_sections():
    from tutor_app.learn_reply import card_selection_options, render_card_selection
    card = {'plain_words': 'Proof follows from assumptions.',
            'establish': 'Start from the given assumptions.', 'connect': 'The domain matters.',
            'self_explain': 'What assumption would you check first?',
            'terms': [{'term': 'Domain', 'meaning': 'Allowed values.', 'notation': 'none', 'spoken': 'domain'}],
            'misconceptions': [{'idea': 'Examples prove all cases.', 'temptation': 'Examples agree.', 'fix': 'Use general reasoning.'}],
            'forms': [{'answer': 'SECRET ANSWER'}]}
    text, problem = render_card_selection({'sections': ['plain_words', 'term:0', 'misconception:0']}, card)
    assert problem is None and 'Allowed values.' in text and 'Use general reasoning.' in text
    assert 'Notation: none' not in text
    assert 'SECRET ANSWER' not in text
    options = card_selection_options(card)
    assert options['establish'] == 'Start from the given assumptions.'
    assert 'SECRET ANSWER' not in str(options)
    assert render_card_selection({'sections': ['establish', 'connect']}, card)[1] is None
    assert 'What assumption' in render_card_selection({'sections': ['self_explain']}, card)[0]
    text, problem = render_card_selection({'sections': []}, card)
    assert not text and 'no matching' in problem.lower()
    for selection in ({'sections': ['forms:0']}, {'sections': ['term:-1']},
                      {'sections': ['plain_words', 'plain_words']},
                      {'sections': ['plain_words'], 'text': 'Every odd number is prime.'}):
        text, problem = render_card_selection(selection, card)
        assert not text and problem


def test_verified_equation_and_prose_can_be_rendered():
    reply = {"blocks": [{"kind": "text", "text": "Expand the brackets carefully."},
                        {"kind": "equality", "left": "(x+1)**2", "right": "x**2+2*x+1"}]}
    text, problem = render_reply(reply)
    assert problem is None and "Expand" in text and "=" in text


def test_verified_powers_and_fractions_render_with_tex_grouping():
    reply = {"blocks": [{"kind": "equality", "left": "(x+1)**2/2", "right": "(x**2+2*x+1)/2"}]}
    text, problem = render_reply(reply)
    assert problem is None
    assert r"^{2}" in text and r"\frac{" in text


def test_checked_equation_is_readable_in_terminal_without_redundant_grouping():
    from tutor_app.texmath import to_terminal
    reply = {"blocks": [{"kind": "equality", "left": "(x+1)**2/2", "right": "(x**2+2*x+1)/2"}]}
    text, problem = render_reply(reply)
    terminal = to_terminal(text)
    assert problem is None and "(((x" not in terminal and "(x)²" not in terminal
    assert "(x + 1)²" in terminal and "x²" in terminal


def test_incorrect_unsupported_or_unstructured_mathematics_is_not_shown():
    for reply in (
        {"blocks": [{"kind": "equality", "left": "2+2", "right": "5"}]},
        {"blocks": [{"kind": "equality", "left": "sin(x)", "right": "x"}]},
        {"blocks": [{"kind": "text", "text": "The result is 2 + 2 = 5."}]},
        {"blocks": [{"kind": "text", "text": "A formula is $x^2$."}]},
        {"blocks": [{"kind": "text", "text": "Two plus two equals five."}]},
        {"blocks": [{"kind": "text", "text": "x × y is negative."}]},
        {"blocks": [{"kind": "text", "text": "Then x - y follows."}]},
        {"blocks": [{"kind": "other", "text": "unknown"}]},
    ):
        text, problem = render_reply(reply)
        assert not text and problem


def test_spelled_out_arithmetic_is_not_treated_as_verified_prose():
    for explanation in ("Twenty is half of forty.", "A dozen is twice a score.",
                        "Thirty-five is an odd multiple of forty."):
        text, problem = render_reply({"blocks": [{"kind": "text", "text": explanation}]})
        assert not text and problem


def test_checked_identity_request_handles_only_verified_polynomial_identities(monkeypatch):
    from tutor_app import learn_reply
    assert 'identity for all real values' in learn_reply.checked_identity_request('Check identity: (x+1)^2 = x^2+2*x+1')
    assert 'not an identity' in learn_reply.checked_identity_request('Check identity: x+1 = x+2')
    for question in ('Check identity: x/x = 1', 'Check identity: sqrt(x) = x',
                     'Check identity: x^999 = x', 'Check identity: x =', 'Is x=x?',
                     'Check identity: x=1=2'):
        assert learn_reply.checked_identity_request(question) is None
    monkeypatch.setattr(learn_reply, 'check_equality', lambda left, right: None)
    assert learn_reply.checked_identity_request('Check identity: x=x') is None




def test_relevant_form_suggestion_requires_distinctive_unambiguous_match():
    from tutor_app.learn_reply import relevant_form_suggestion
    card = {'forms': [
        {'name': 'Prove no turning points using a quadratic gradient', 'wordings': ['Show a quadratic gradient is positive']},
        {'name': 'Disprove a claim with a counterexample', 'wordings': ['Find a counterexample']},
    ]}
    assert relevant_form_suggestion('How do I prove a cubic curve has no turning points using its quadratic gradient?', card) == 0
    assert relevant_form_suggestion("How do I prove a curve doesn't have turning points using a quadratic gradient?", card) == 0
    assert relevant_form_suggestion('How do I find turning points using a quadratic gradient?', card) is None
    assert relevant_form_suggestion("I don't understand how to prove a curve has turning points using a quadratic gradient", card) is None
    assert relevant_form_suggestion("I can't understand turning points using a quadratic gradient", card) is None
    assert relevant_form_suggestion('I do not know how to find turning points using a quadratic gradient', card) is None
    assert relevant_form_suggestion('I am not sure how to prove a curve has turning points using a quadratic gradient', card) is None
    assert relevant_form_suggestion('Explain proof', card) is None
    assert relevant_form_suggestion('Tell me about the industrial revolution', card) is None
    card['forms'].append({'name': 'Prove no turning points using a quadratic gradient'})
    assert relevant_form_suggestion('How do I prove no turning points using a quadratic gradient?', card) is None
