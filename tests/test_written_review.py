from build.written_review import validate_reviews, fingerprint

def record(item, solution='valid working', reviewer='independent reviewer'):
    return {'fingerprint': fingerprint(item), 'solution': solution, 'solver': 'solver-agent', 'reviewer': reviewer,
            'verdict': 'accepted', 'rationale': 'The solution meets both points.',
            'solution_hash': fingerprint({'id': item['id'], 'stem': solution, 'answer': None, 'rubric': None})}

def test_fresh_review_matches_exact_question_answer_and_rubric():
    item = {'id': 'proof', 'stem': 'Prove it', 'answer': 'working', 'rubric': [{'point': 'reason'}]}
    assert validate_reviews([item], {'proof': record(item)}) == []
    for key, value in [('stem', 'Changed'), ('answer', 'Changed'), ('rubric', [{'point': 'Changed'}])]:
        changed = {**item, key: value}
        assert validate_reviews([changed], {'proof': record(item)})

def test_missing_rejected_or_empty_review_fails_closed():
    item = {'id': 'proof', 'stem': 'Prove it', 'answer': 'working', 'rubric': [{'point': 'reason'}]}
    for reviews in ({}, {'proof': record(item, solution='')}, {'proof': {**record(item), 'verdict': 'rejected'}},
                    {'proof': {**record(item), 'rationale': ''}}, {'proof': record(item, reviewer='')}):
        assert validate_reviews([item], reviews)

def test_duplicate_ids_cannot_reuse_one_review():
    a = {'id': 'proof', 'stem': 'Prove it', 'answer': 'working', 'rubric': [{'point': 'reason'}]}
    b = {**a, 'stem': 'Another question'}
    assert validate_reviews([a, b], {'proof': record(a)})

def test_review_is_invalid_if_independent_solution_changes():
    item = {'id': 'proof', 'stem': 'Prove it', 'answer': 'working', 'rubric': [{'point': 'reason'}]}
    review = record(item)
    review['solution_hash'] = fingerprint({'id': 'proof', 'stem': review['solution'], 'answer': None, 'rubric': None})
    assert validate_reviews([item], {'proof': review}) == []
    review['solution'] = 'Different working'
    assert validate_reviews([item], {'proof': review})

def test_empty_or_malformed_inventory_fails_closed():
    for items, reviews in (([], {}), (None, {}), ([None], {}), ([{'id': []}], {}), ([{'id': 'x'}], None)):
        assert validate_reviews(items, reviews)

def test_changed_supporting_context_invalidates_review():
    item = {'id': 'proof', 'stem': 'Prove it', 'answer': 'working', 'rubric': [{'point': 'reason'}],
            'context': {'diagram_sha256': 'a'}}
    review = record(item)
    assert validate_reviews([item], {'proof': review}) == []
    assert validate_reviews([{**item, 'context': {'diagram_sha256': 'b'}}], {'proof': review})


def test_extract_review_items_matches_all_written_checks_and_retries():
    from build.written_review import review_items
    cards = {'P2-1.1': {'forms': [{'name': 'Proof', 'check': 'Prove it', 'answer': 'Because',
        'rubric': [{'point': 'reason'}], 'retry': {'check': 'Try again', 'answer': 'Because again',
        'rubric': [{'point': 'reason again'}]}}]}}
    rows = review_items(cards)
    assert [r['id'] for r in rows] == ['P2-1.1.form.0.check', 'P2-1.1.form.0.retry']
    assert rows[0]['stem'] == 'Prove it' and rows[1]['answer'] == 'Because again'
    assert len(rows[1]['rubric']) == 1


def test_changed_worked_example_invalidates_both_check_reviews():
    from build.written_review import review_items
    form = {'name': 'Cases', 'wordings': ['Show'], 'example': 'First example.', 'check': 'Check',
            'answer': 'Answer', 'rubric': [{'point': 'Reason'}],
            'retry': {'check': 'Retry', 'answer': 'Other answer', 'rubric': [{'point': 'Reason'}]}}
    cards = {'P2-1.2': {'forms': [form]}}
    original = review_items(cards)
    records = {item['id']: record(item) for item in original}
    form['example'] = 'A changed example.'
    assert len(validate_reviews(review_items(cards), records)) == 2


def test_build_review_records_requires_separate_solver_and_reviewer():
    from build.written_review import build_records
    item = {'id': 'q1', 'stem': 'Why?', 'answer': 'Because', 'rubric': [{'point': 'reason'}]}
    solution = {'q1': 'Independent reasoning.'}
    decisions = {'q1': {'verdict': 'accepted', 'rationale': 'Correct reasoning.'}}
    records = build_records([item], solution, decisions, solver='solver-agent', reviewer='review-agent')
    assert validate_reviews([item], records) == []
    import pytest
    with pytest.raises(ValueError):
        build_records([item], solution, decisions, solver='same', reviewer='same')
    with pytest.raises(ValueError):
        build_records([item], solution, {}, solver='solver-agent', reviewer='review-agent')


def test_build_records_rejects_invalid_ids_and_equivalent_identities():
    from build.written_review import build_records
    import pytest
    item = {'id': 'q1', 'stem': 'Why?', 'answer': 'Because', 'rubric': [{'point': 'reason'}]}
    solutions = {'q1': 'Proof'}
    decisions = {'q1': {'verdict': 'accepted', 'rationale': 'Correct'}}
    with pytest.raises(ValueError):
        build_records([item], solutions, decisions, solver='agent', reviewer=' agent ')
    with pytest.raises(ValueError):
        build_records([{**item, 'id': []}], solutions, decisions, solver='a', reviewer='b')


def test_retry_review_fingerprint_binds_retry_specific_rule():
    from build.written_review import review_items, fingerprint
    card = {'K': {'forms': [{'name': 'Example', 'example': 'Teaching', 'wordings': ['Show'],
            'check': 'First', 'answer': 'Answer', 'rubric': [{'point': 'P'}],
            'retry': {'check': 'Retry', 'answer': 'Retry answer', 'rubric': [{'point': 'P'}]}}]}}
    before = review_items(card)[1]
    card['K']['forms'][0]['retry']['review_rule'] = 'positive_pair'
    after = review_items(card)[1]
    assert fingerprint(before) != fingerprint(after)
    assert review_items(card)[0]['context']['review_rule'] is None


def test_written_faded_review_binds_worked_context_and_redacts_blind_export():
    from build.written_review import faded_review_items, blind_written_faded
    worked = [{'id': 'we2', 'kc': 'K', 'problem': 'Worked problem', 'steps': [{'why': 'reason'}],
               'faded': {'id': 'we2f', 'kind': 'short', 'problem': 'Disprove.', 'review_answer': '111 = 3 × 37',
                         'rubric': [{'point': 'Factors the result', 'keywords': [['3'], ['37']]}]}}]
    items = faded_review_items(worked)
    assert items[0]['id'] == 'we2.faded'
    assert blind_written_faded(worked) == [{'id': 'we2.faded', 'stem': 'Disprove.'}]
    reviews = {'we2.faded': record(items[0])}
    assert not validate_reviews(items, reviews)
    worked[0]['steps'][0]['why'] = 'changed'
    assert validate_reviews(faded_review_items(worked), reviews)


def test_written_faded_is_not_sent_to_automatic_blind_comparator():
    from build.blind import strip
    pack = {'worked': [{'id': 'we2', 'kc': 'K', 'faded': {'id': 'we2f', 'kind': 'short',
            'problem': 'Disprove.', 'review_answer': 'secret answer',
            'rubric': [{'point': 'secret point', 'keywords': [['secret']]}]}}]}
    assert strip(pack) == []


def test_prior_visible_sibling_context_excludes_private_answers_and_other_kcs():
    import json
    from build.written_review import review_items
    first = {'name': 'First', 'wordings': ['Classify'], 'example': 'Visible worked molecule',
             'check': 'Visible earlier question', 'answer': 'PRIVATE first key',
             'rubric': [{'point': 'PRIVATE mark scheme'}],
             'retry': {'check': 'CONDITIONAL retry', 'answer': 'PRIVATE retry key',
                       'rubric': [{'point': 'PRIVATE retry marks'}]}}
    second = {'name': 'Second', 'example': 'Next example', 'check': 'Next question',
              'answer': 'Next key', 'rubric': [{'point': 'Reason'}]}
    cards = {'kc': {'forms': [first, second]}, 'other': {'forms': [first]}}
    rows = review_items(cards)
    prior = rows[2]['context']['learner_visible_prior']
    assert prior == [
        {'phase': 'form_example:0', 'title': 'First',
         'text': '**Wording:** Classify\n\nVisible worked molecule'},
        {'phase': 'form_check:0', 'stem': 'Visible earlier question'}]
    assert 'PRIVATE' not in json.dumps(prior)
    assert 'CONDITIONAL' not in json.dumps(prior)
    assert rows[-1]['context']['learner_visible_prior'] == []


def test_changed_prior_visible_sibling_invalidates_later_review_only():
    from build.written_review import review_items
    first = {'name': 'First', 'example': 'Earlier worked answer', 'check': 'Earlier question',
             'answer': 'Earlier private answer', 'rubric': [{'point': 'Reason'}]}
    second = {'name': 'Second', 'example': 'Later example', 'check': 'Later question',
              'answer': 'Later key', 'rubric': [{'point': 'Reason'}]}
    cards = {'kc': {'forms': [first, second]}}
    before = review_items(cards)
    later_record = record(before[1])
    first['example'] = 'Changed visible answer duplicates later question'
    assert validate_reviews([review_items(cards)[1]], {before[1]['id']: later_record})
    first['example'] = 'Earlier worked answer'
    first['answer'] = 'Changed PRIVATE key never shown before answering'
    assert fingerprint(review_items(cards)[1]) == fingerprint(before[1])


def test_conditional_cross_kc_context_binds_visible_examples_without_keys_or_retry():
    import json
    from build.written_review import review_items
    prior = {'name': 'Prior', 'example': 'Earlier KC example reveals target', 'check': 'Prior stem',
             'answer': 'PRIVATE answer', 'rubric': [{'point': 'PRIVATE marking'}],
             'retry': {'check': 'PRIVATE conditional retry', 'answer': 'PRIVATE retry answer',
                       'rubric': [{'point': 'PRIVATE marks'}]}}
    target = {'name': 'Target', 'example': 'Target example', 'check': 'Target stem',
              'answer': 'Target key', 'rubric': [{'point': 'Reason'}]}
    cards = {'first': {'forms': [prior]}, 'second': {'forms': [target]}}
    before = review_items(cards)[-1]
    possible = before['context']['possible_other_kc_context']
    assert possible[0]['kc'] == 'first'
    assert possible[0]['visibility'].startswith('conditional:')
    assert 'Earlier KC example reveals target' in json.dumps(possible)
    assert 'PRIVATE' not in json.dumps(possible)
    prior['example'] = 'Changed visible cross-KC example'
    assert fingerprint(review_items(cards)[-1]) != fingerprint(before)


def test_forms_skipped_by_runtime_are_absent_from_prior_visible_context():
    from build.written_review import review_items
    # A malformed, rubric-less sibling fails inventory validation, rather than
    # being advertised as a learner-visible step that runtime would skip.
    import pytest
    cards = {'kc': {'forms': [{'check': 'Skipped', 'answer': 'Key', 'rubric': []}]}}
    with pytest.raises(ValueError):
        review_items(cards)


def test_cross_kc_projection_matches_primary_prose_and_conditional_detail():
    from build.written_review import review_items
    form = {'name': 'Task', 'check': 'Question', 'answer': 'Key', 'rubric': [{'point': 'Reason'}]}
    cards = {'prior': {'plain_words': 'PRIMARY', 'establish': 'EXPANDABLE', 'connect': 'LINK',
                      'forms': [form]}, 'target': {'forms': [form]}}
    content = review_items(cards)[-1]['context']['possible_other_kc_context'][0]['content']
    assert content['primary_explanation'] == {'phase': 'plain_words', 'text': 'PRIMARY'}
    assert 'establish' not in content
    assert content['conditional_detail']['visibility'].startswith('conditional:')
    assert content['conditional_detail']['text'] == 'EXPANDABLE\n\n**How it connects:** LINK'
    del cards['prior']['plain_words']
    content = review_items(cards)[-1]['context']['possible_other_kc_context'][0]['content']
    assert content['primary_explanation'] == {'phase': 'establish', 'text': 'EXPANDABLE\n\n**How it connects:** LINK'}
    assert 'conditional_detail' not in content


def test_cross_kc_visible_exam_misconception_diagram_context_and_bytes_are_bound(tmp_path):
    import json
    from build.written_review import review_items
    diagram = tmp_path / 'synthetic-diagram.svg'
    diagram.write_text('<svg>first</svg>')
    form = {'name': 'Task', 'check': 'Question', 'answer': 'PRIVATE key', 'rubric': [{'point': 'Reason'}]}
    prior = {'forms': [form], 'exam_language': [{'name': 'Deduce', 'meaning': 'VISIBLE exam meaning'}],
             'misconceptions': [{'idea': 'VISIBLE idea', 'temptation': 'VISIBLE temptation', 'fix': 'VISIBLE fix',
                                'answer': 'PRIVATE extra'}],
             'diagrams': ['Library/diagram.svg'], 'diagram_descriptions': ['VISIBLE diagram description']}
    cards = {'prior': prior, 'target': {'forms': [form]}}
    before = review_items(cards, diagram_resolver=lambda ref: diagram)[-1]
    context = before['context']['possible_other_kc_context']
    text = json.dumps(context)
    for value in ('VISIBLE exam meaning', 'VISIBLE idea', 'VISIBLE temptation', 'VISIBLE fix', 'VISIBLE diagram description'):
        assert value in text
    assert 'PRIVATE' not in text
    assert context[0]['content']['diagrams'][0]['sha256']
    diagram.write_text('<svg>changed</svg>')
    assert fingerprint(review_items(cards, diagram_resolver=lambda ref: diagram)[-1]) != fingerprint(before)


def test_current_form_same_reference_diagram_byte_change_invalidates_review(tmp_path):
    import json
    from build.written_review import review_items
    figure = tmp_path / 'synthetic-current.svg'
    figure.write_text('<svg>old visible figure</svg>')
    form = {'name': 'Current', 'example': 'Worked example', 'diagram': 'Library/current.svg',
            'check': 'Question', 'answer': 'PRIVATE key', 'rubric': [{'point': 'PRIVATE marks'}]}
    cards = {'kc': {'plain_words': 'Primary', 'diagrams': ['Library/current.svg'],
                    'diagram_descriptions': ['Visible current figure description'], 'forms': [form]}}
    before = review_items(cards, diagram_resolver=lambda ref: figure)[0]
    visible = before['context']['current_visible_diagrams']
    assert visible[0]['phase'] == 'form_example:0'
    assert visible[0]['sha256']
    assert 'Visible current figure description' in json.dumps(visible)
    assert 'PRIVATE' not in json.dumps(visible)
    figure.write_text('<svg>changed visible figure</svg>')
    after = review_items(cards, diagram_resolver=lambda ref: figure)[0]
    assert fingerprint(after) != fingerprint(before)
    assert validate_reviews([after], {before['id']: record(before)})


def test_current_visible_diagrams_excludes_future_form_solution_figures(tmp_path):
    from build.written_review import review_items
    figure = tmp_path / 'synthetic.svg'
    figure.write_text('<svg/>')
    first = {'name': 'First', 'example': 'Example', 'check': 'Question',
             'answer': 'Key', 'rubric': [{'point': 'Reason'}]}
    future = {**first, 'name': 'Future', 'diagram': 'Library/future.svg'}
    cards = {'kc': {'diagrams': ['Library/overview.svg', 'Library/extra.svg', 'Library/future.svg'],
                    'forms': [first, future]}}
    visible = review_items(cards, diagram_resolver=lambda ref: figure)[0]['context']['current_visible_diagrams']
    assert [(x['phase'], x['reference']) for x in visible] == [
        ('introduction', 'Library/overview.svg'), ('diagram:1', 'Library/extra.svg')]
    assert all(x['sha256'] for x in visible)


def test_diagram_resolution_and_byte_hashing_are_memoized_only_within_extraction(tmp_path):
    from build.written_review import review_items
    figure = tmp_path / 'synthetic-shared.svg'
    figure.write_text('<svg>first</svg>')
    calls = []
    reads = []
    class Resolved:
        def read_bytes(self):
            reads.append(True)
            return figure.read_bytes()
    def resolver(reference):
        calls.append(reference)
        return Resolved()
    form = {'name': 'Task', 'diagram': 'Library/shared.svg', 'example': 'Example',
            'check': 'Question', 'answer': 'Key', 'rubric': [{'point': 'Reason'}]}
    cards = {kc: {'diagrams': ['Library/shared.svg'], 'forms': [form, form]}
             for kc in ('first', 'second')}
    before = review_items(cards, diagram_resolver=resolver)
    assert calls == ['Library/shared.svg']
    assert len(reads) == 1
    figure.write_text('<svg>second</svg>')
    after = review_items(cards, diagram_resolver=resolver)
    assert calls == ['Library/shared.svg', 'Library/shared.svg']
    assert len(reads) == 2
    assert fingerprint(before[0]) != fingerprint(after[0])
