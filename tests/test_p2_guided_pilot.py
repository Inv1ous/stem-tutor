"""Run the unpublished proof draft in a disposable vault, not the learner's vault."""
import json
import itertools
import random
import sys
from pathlib import Path

from fixtures import make_vault
from library_assets import install_course, library_course_diagrams, read_bytes, read_json
from tutorlib import session, store

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def _snapshot():
    """The P2 chapter as it was when the refine pass began: the baseline the no-loss gate compares with. The live pack is
    now the integrated candidate (corrections, guided cards and forms already in it), so the tests that stage the draft
    onto "the original" start from this."""
    return read_json('build/work/refine/P2-1.snapshot.json')


def original_pack():
    return _snapshot()['pack']


def original_note():
    return _snapshot()['note']


def test_written_pilot_candidate_matches_review_and_preserves_disproof():
    from build.written_review import faded_review_items, validate_reviews
    from tutorlib.faded import question_item

    root = ROOT / 'build/work/guided'
    candidate = read_json('build/work/guided/P2-1-written-pilot-candidate.json')
    reviews = json.loads((root / 'P2-1-we2-written-faded-review.json').read_text())
    worked = next(row for row in candidate['worked'] if row['id'] == 'we2')
    item = question_item(worked['faded'], worked['kc'])
    assert 'Disprove' in item['stem'] and 'factor' in item['stem']
    assert item['kind'] == 'short' and len(item['rubric']) == 3
    assert not validate_reviews(faded_review_items(candidate['worked']), reviews)
    worked['faded']['rubric'][0]['point'] += ' changed'
    assert validate_reviews(faded_review_items(candidate['worked']), reviews)


def test_written_pilot_alternative_domain_explanation_requires_judgment(tmp_path):
    from tutorlib.faded import question_item

    candidate = read_json('build/work/guided/P2-1-written-pilot-candidate.json')
    worked = next(row for row in candidate['worked'] if row['id'] == 'we2')
    tutor = session.Tutor(store.Vault(make_vault(tmp_path)))
    tutor.start('learn', focus=['9702-2.1.1'])
    item = question_item(worked['faded'], '9702-2.1.1')
    n = tutor._present(item, block='learn', phase='faded')['n']
    response = '11 is an integer greater than 9. 121 - 11 + 1 = 111 = 37 × 3 so it is composite.'
    tutor.answer(f'{n} = {response}')
    assert tutor.confirm_faded_attempt(n, response)['ok']
    result = tutor.answer(f'{n} = {response}')['results'][0]
    assert result['pending_judgement']
    assert not [e for e in tutor.vault.events() if e['type'] == 'answer' and e.get('n') == n]


def test_written_pilot_skipped_answer_stays_private_after_restart(tmp_path, monkeypatch):
    from tutorlib.faded import question_item

    identifiers = itertools.count(0x370000000000)
    monkeypatch.setattr(store.uuid, 'uuid4',
                        lambda: store.uuid.UUID(hex=f'{next(identifiers):012x}' + '0' * 20))
    candidate = read_json('build/work/guided/P2-1-written-pilot-candidate.json')
    worked = next(row for row in candidate['worked'] if row['id'] == 'we2')
    vault = make_vault(tmp_path)
    tutor = session.Tutor(store.Vault(vault))
    tutor.start('learn', focus=['9702-2.1.1'])
    n = tutor._present(question_item(worked['faded'], '9702-2.1.1'), block='learn', phase='faded')['n']
    skipped = tutor.answer(f'{n}?')
    displayed = [{key: value for key, value in result.items() if key != 'event'}
                 for result in skipped['results']]
    assert '111' not in str(displayed) and '37' not in str(displayed)
    tutor = session.Tutor(store.Vault(vault))
    retry = tutor.retry_skipped()['items'][0]
    assert '111' not in str(retry) and '37' not in str(retry)
    assert tutor.session['skipped_answer_guards']


def corrected_draft_pack():
    """The integrated P2 candidate: the live pack, which now holds the reviewed corrections, the guided cards and the
    form inventory (refine's gates compare it with the pass-start snapshot, `original_pack`)."""
    return read_json('build/out/packs/P2/P2-1.json')


def _stage_p2(vault):
    """Install the actual Library pack/graph and their catalogued media into a temp vault."""
    return install_course(vault, 'P2', 'P2-1')


def test_p2_exhaustion_corrections_match_the_current_pack():
    pack = original_pack()
    corrections = read_json('build/work/guided/P2-1-corrections.json')['corrections']
    assert corrections[0]['old'] in pack['outline']
    worked = next(w for w in pack['worked'] if w['id'] == 'we1')
    assert worked['steps'][0]['why'] == corrections[1]['old']
    assert 'finite domain' not in corrections[1]['new'].lower() or 'here' in corrections[1]['new'].lower()


def test_existing_proof_note_examples_cover_their_stated_domains():
    import itertools
    import sympy as sp
    pack = original_pack()
    note = original_note()
    assert '$(1,1),(1,3),(1,5),(3,3),(3,5),(5,5)$' in note
    assert '$n=5$' in note and '$n=4$' in note
    allowed = (1, 3, 5)
    listed = {(1, 1), (1, 3), (1, 5), (3, 3), (3, 5), (5, 5)}
    assert listed == set(itertools.combinations_with_replacement(allowed, 2))
    assert all((a + b) % 2 == 0 for a, b in itertools.product(allowed, repeat=2))
    assert -1 < 7 and -1 % 2 == 1 and -1 not in allowed
    assert 5**2 - 5 + 1 == 21 and not sp.isprime(21)
    assert sp.isprime(4**2 - 4 + 1)


def test_finite_enumeration_check_has_distinct_claim_and_correct_cases():
    cards = read_json('build/work/teach/P2-1.json')
    form = next(f for f in cards['P2-1.2']['forms'] if f['name'] == 'Finite enumeration')
    # The earlier worked proof already establishes n(n+1) is even for all integers.
    # Check a different claim, rather than asking for that same proof again.
    assert r'n^2 \leq 4' in form['check']
    assert [n * n for n in range(3)] == [0, 1, 4]
    assert all(n * n <= 4 for n in range(3))
    assert '0, 1 and 4' in form['answer']
    assert all(n * n >= n for n in range(4))


def test_algebraic_retry_expansion_is_exact():
    import sympy as sp
    a, b = sp.symbols('a b', integer=True)
    assert sp.expand((2*a + 1)*(2*b + 1) - (2*(2*a*b + a + b) + 1)) == 0


def test_hence_series_example_and_check_follow_from_given_sum():
    import sympy as sp
    cards = read_json('build/work/teach/P2-1.json')
    form = next(f for f in cards['P2-1.1']['forms'] if f['name'] == 'Derive a formula from a series')
    n = sp.symbols('n', integer=True, positive=True)
    given = n * (n + 1) / 2
    assert 'hence' in form['example'].lower() and 'hence' in form['check'].lower()
    assert sp.simplify(3 * given - 3*n*(n+1)/2) == 0
    assert sp.simplify(2 * given - n - n**2) == 0
    assert sp.simplify(2 * given - n*(n+1)) == 0


def test_geometric_calculus_and_counterexample_retry_values():
    import sympy as sp
    x = sp.symbols('x', real=True)
    assert 5 > 1 + 2
    assert (2*x + 1).subs(x, -1) == -1
    assert (2**2 + 1) % 2 == 1
    assert sp.Rational(1, 2).is_integer is False
    assert 0 - 1 < 0


def test_circle_diameter_midpoint_routes_use_equal_distances():
    import sympy as sp
    cards = read_json('build/work/teach/P2-1.json')
    form = next(f for f in cards['P2-1.1']['forms']
                if f['name'] == 'Geometric proof with alternative chains of reasoning')
    for exercise in (form, form['retry']):
        assert 'midpoint' in exercise['check'].lower()
        assert 'midpoint' in exercise['rubric'][0]['point'].lower()
        assert 'centre' in exercise['rubric'][1]['point'].lower()
    for a, b, c, expected in [((0, 0), (6, 0), (3, 3), 9),
                              ((0, 0), (10, 0), (8, 4), 25),
                              ((0, 0), (13, 0), (4, 6), sp.Rational(169, 4))]:
        a, b, c = (sp.Point(*point) for point in (a, b, c))
        midpoint = sp.Segment(a, b).midpoint
        assert all(midpoint.distance(point)**2 == expected for point in (a, b, c))
        assert not sp.Line(a, b).contains(c)


def test_remaining_proof_retry_calculations():
    import sympy as sp
    from itertools import product
    k, n, theta = sp.symbols('k n theta', integer=True)
    assert sp.simplify(2 * sp.summation(k, (k, 1, n)) - n*(n+1)) == 0
    for count in range(1, 8):
        assert 3 * sum(4**i for i in range(count)) == 4**count - 1
    assert 4**2 + (-4)**2 == 32 and 8**2 == 64
    assert sp.trigsimp(1 + sp.sin(theta)**2 / sp.cos(theta)**2 - 1 / sp.cos(theta)**2) == 0
    assert sp.expand((2*k + 1)**3 - (2*(4*k**3 + 6*k**2 + 3*k) + 1)) == 0
    assert sp.expand((2*k)**2 - 4*k**2) == 0
    assert all(x + 2*y <= 3 for x, y in product((0, 1), repeat=2))


def test_restricted_residue_example_covers_two_distinct_classes():
    import sympy as sp
    k = sp.symbols('k', integer=True)
    n = sp.symbols('n', integer=True)
    expression = n**2 - 1
    for value in (3*k + 1, 3*k + 2, 3*k - 1):
        assert all(coefficient % 3 == 0 for coefficient in sp.Poly(expression.subs(n, value), k).all_coeffs())
        product = (n * (n + 1) * (n + 2)).subs(n, value).expand()
        assert all(coefficient % 3 == 0 for coefficient in sp.Poly(product, k).all_coeffs())
        retry_product = (n * (n - 1) * (n + 1)).subs(n, value).expand()
        assert all(coefficient % 3 == 0 for coefficient in sp.Poly(retry_product, k).all_coeffs())
    assert sp.simplify((3*k + 2) - (3*(k + 1) - 1)) == 0
    assert {(3*k0 - 1) % 3 for k0 in range(-3, 4)} == {2}
    assert {(3*k0 + 1) % 3 for k0 in range(-3, 4)} == {1}


def test_p2_draft_diagnostics_record_misconceptions_in_disposable_vault(tmp_path, monkeypatch):
    vault = make_vault(tmp_path)
    pack = _stage_p2(vault)
    base = vault / '.tutor/packs/v1'
    dest = base / 'specs/P2'
    draft = read_json('build/work/guided/P2-1-misconceptions.json')
    monkeypatch.syspath_prepend(str(ROOT / 'build'))
    import validate_pack
    graph = json.loads((dest / 'graph.json').read_text())
    assert validate_pack.validate(pack, graph) == []
    (dest / 'packs/P2-1.json').write_text(json.dumps(pack))
    tutor = session.Tutor(store.Vault(vault), rng=random.Random(0))
    tutor.start('test', minutes=30, focus=['P2-1'])
    for item in draft['items']:
        kc = item['kcs'][0]
        block = {'kind': 'node', 'kc': kc, 'card': pack['teach'][kc], 'i': 0,
                 'phases': ['done'], 'misses': 0, 'mistakes': []}
        tutor.session['blocks'] = [block]
        tutor.session['cursor'] = 0
        activity = tutor._questions(block, 0, [item], phase='check', unassisted=True)
        n = activity['items'][0]['n']
        instance = tutor.session['presented'][str(n)]['inst']
        wrong = next(choice for choice, ident in instance['distractors'].items() if ident in ('m6', 'm7'))
        result = tutor.answer(f'{n}{wrong}3')['results'][0]
        ident = instance['distractors'][wrong]
        assert result['misconception']['id'] == ident
        assert ident in tutor.state['kcs'][item['kcs'][0]]['active_misconceptions']
        explanation = tutor.next()
        match = next(m for m in pack['teach'][kc]['misconceptions'] if m.get('id') == ident)
        assert explanation['part'] == 'fix' and match['fix'] in explanation['text']
        assert tutor.state['kcs'][kc]['fsrs']
        assert block['phases'][block['i']] == 'check'
        assert tutor.respond({})['ok']
        followup = tutor.next()
        assert followup['activity'] == 'questions' and followup['phase'] == 'check'
        # Finish this follow-up before constructing the next diagnostic scenario.
        view = followup['items'][0]
        pending = tutor.session['presented'][str(view['n'])]['inst']
        if pending['kind'] == 'mcq':
            tutor.answer(f"{view['n']}{pending['answer']}3")
        else:
            tutor.answer(f"{view['n']} = A complete answer ~3", judge={view['n']: 1})
    restored = session.Tutor(store.Vault(vault), rng=random.Random(0))
    for item in draft['items']:
        ident = next(iter(item['distractors'].values()))
        assert ident in restored.state['kcs'][item['kcs'][0]]['active_misconceptions']


def test_pilot_form_miss_revisits_its_own_example_in_real_session(tmp_path):
    vault = make_vault(tmp_path)
    pack = _stage_p2(vault)
    base = vault / '.tutor/packs/v1'
    dest = base / 'specs/P2'
    (dest / 'packs/P2-1.json').write_text(json.dumps(pack))
    tutor = session.Tutor(store.Vault(vault), rng=random.Random(0))
    tutor.start('lesson', minutes=30, focus=['P2-1'])
    card = pack['teach']['P2-1.2']
    index = next(i for i, form in enumerate(card['forms']) if form['name'] == 'Restricted residue cases')
    second = next(i for i, form in enumerate(card['forms']) if form['name'] == 'Exhaustion with ordered pairs')
    block = {'kind': 'node', 'kc': 'P2-1.2', 'card': card, 'i': 0,
             'phases': [f'form_check:{index}', f'form_check:{second}', 'done'], 'misses': 0, 'mistakes': []}
    tutor.session['blocks'] = [block]
    tutor.session['cursor'] = 0
    activity = tutor.next()
    assert activity['phase'] == 'form_check'
    n = activity['items'][0]['n']
    result = tutor.answer(f'{n} = I covered one case', judge={n: 0.5},
                          explanation={n: '✓ One step\n✗ Other case'})
    assert result['results'][0]['score'] == 0.5
    repair = tutor.next()
    assert repair['part'] == 'fix' and card['forms'][index]['example'] in repair['text']
    assert card['forms'][index]['answer'] not in repair['text']
    assert '✗ Other case' in block['mistakes'][-1]
    tutor.respond({})
    recheck = tutor.next()
    assert recheck['activity'] == 'questions' and recheck['phase'] == 'form_check'
    followup = recheck['items'][0]
    item = tutor.session['presented'][str(followup['n'])]['inst']
    assert followup['stem'] == card['forms'][index]['retry']['check']
    assert card['forms'][index]['retry']['answer'] not in str(followup)
    if item['kind'] == 'mcq':
        tutor.answer(f"{followup['n']}{item['answer']}3")
    else:
        tutor.answer(f"{followup['n']} = A complete answer ~3", judge={followup['n']: 1})
    later = tutor.next()
    assert later['phase'] == 'form_check'
    n2 = later['items'][0]['n']
    tutor.answer(f'{n2} = One pair only', judge={n2: 0.5}, explanation={n2: '✗ Missing cases'})
    later_repair = tutor.next()
    assert later_repair['part'] == 'fix' and card['forms'][second]['example'] in later_repair['text']
    assert not block.get('stuck')
    tutor.respond({})
    second_recheck = tutor.next()
    assert second_recheck['phase'] == 'form_check'
    assert second_recheck['items'][0]['stem'] == card['forms'][second]['retry']['check']
    tutor.answer(f"{second_recheck['items'][0]['n']}?")
    assert block['stuck'] and 'P2-1.2' in tutor.state['gaps']


def test_every_pilot_form_serves_its_distinct_retry_without_a_key(tmp_path):
    vault = make_vault(tmp_path)
    pack = _stage_p2(vault)
    base = vault / '.tutor/packs/v1'
    dest = base / 'specs/P2'
    (dest / 'packs/P2-1.json').write_text(json.dumps(pack))
    tutor = session.Tutor(store.Vault(vault), rng=random.Random(0))
    count = 0
    for kc, card in pack['teach'].items():
        for index, form in enumerate(card['forms']):
            retry = form['retry']
            tutor.start('lesson', minutes=30, focus=['P2-1'], replace=True)
            block = {'kind': 'node', 'kc': kc, 'card': card, 'i': 0,
                     'phases': [f'form_check:{index}', 'done'], 'misses': 0, 'mistakes': []}
            tutor.session['blocks'] = [block]
            tutor.session['cursor'] = 0
            first = tutor.next()['items'][0]
            if form.get('review_rule'):
                assert tutor.session['presented'][str(first['n'])]['inst']['review_rule'] == form['review_rule']
            tutor.answer(f"{first['n']} = an incomplete attempt", judge={first['n']: 0})
            repair = tutor.next()
            assert repair['part'] == 'fix' and retry['answer'] not in repair['text'], form['name']
            tutor.respond({})
            activity = tutor.next()
            question = activity['items'][0]
            assert question['stem'] == retry['check'] and 'rubric' not in question
            if form.get('review_rule'):
                assert tutor.session['presented'][str(question['n'])]['inst']['review_rule'] == form['review_rule']
            assert retry['answer'] not in str(question)
            assert retry['answer'] not in (vault / 'Now.md').read_text()
            result = tutor.answer(f"{question['n']}?")
            assert retry['answer'] not in str(result) and block['stuck']
            recovered = tutor.retry_skipped()['items'][0]
            tutor.answer(f"{recovered['n']} = an attempt", judge={recovered['n']: 0})
            count += 1
    assert count == sum(len(card['forms']) for card in pack['teach'].values()) == 36


def test_proof_pilot_reaches_every_idea_and_form_without_leaking_keys(tmp_path):
    vault = make_vault(tmp_path)
    pack = _stage_p2(vault)
    base = vault / '.tutor/packs/v1'
    dest = base / 'specs/P2'
    (dest / 'packs/P2-1.json').write_text(json.dumps(pack))
    tutor = session.Tutor(store.Vault(vault), rng=random.Random(0))
    worked = next(w for w in tutor.packs.worked_for('P2-1.2') if w['id'] == 'we1')
    assert worked['steps'][0]['why'] == 'Here the domain is finite, so listing its values gives a complete set of cases.'
    tutor.start('lesson', minutes=90, focus=['P2-1'])
    seen, forms, diagrams = set(), [], []
    calculus_check_seen = False
    for _ in range(200):
        act = tutor.next()
        kind = act['activity']
        if kind == 'end':
            break
        if kind == 'choose':
            tutor.respond({'choice': 'scratch'})
        elif kind == 'plan':
            tutor.respond({'teach': act['nodes_all']})
        elif kind == 'explain':
            seen.add((act['kc'], act['part']))
            if act.get('diagram'):
                diagrams.append(act['diagram'])
                assert act['diagram'] in (vault / 'Now.md').read_text()
            tutor.respond({})
        elif kind in ('worked', 'walkthrough'):
            if act.get('kc') == 'P2-1.2':
                assert 'Exhaustion needs a finite, complete domain.' not in str(act)
            tutor.respond({'done': True})
        elif kind in ('own_words', 'refute', 'stuck'):
            tutor.respond({})
        elif kind in ('questions', 'awaiting'):
            for view in act['items']:
                n = view['n']
                item = tutor.session['presented'][str(n)]['inst']
                assert 'rubric' not in view and 'answer' not in view
                if act.get('phase') == 'form_check':
                    forms.append(item['id'])
                    if 'g\\prime\\prime(x)' in item['stem']:
                        calculus_check_seen = True
                        assert item['stem'] in (vault / 'Now.md').read_text()
                if item['kind'] == 'mcq':
                    tutor.answer(f"{n}{item['answer']}3")
                elif item['kind'] == 'short':
                    tutor.answer(f'{n} = A complete answer ~3', judge={n: 1})
                elif item['kind'] == 'numeric':
                    tutor.answer(f"{n} = {item['answer']['value']} {item['answer'].get('unit', '')} ~3")
                elif item['kind'] == 'expression':
                    tutor.answer(f"{n} = {item['answer']['expr']} ~3", judge={n: 1})
                else:
                    raise AssertionError(f"Unsupported question kind: {item['kind']}")
    else:
        raise AssertionError(f'Pilot did not finish: {act}')
    assert {kc for kc, part in seen if part == 'plain_words'} == {'P2-1.1', 'P2-1.2', 'P2-1.3'}
    assert len(forms) == sum(len(card['forms']) for card in pack['teach'].values())
    assert calculus_check_seen
    assert len(diagrams) == sum(len(card["diagrams"]) for card in pack["teach"].values())
    assert len(tutor.state['terms']) == sum(len(card['terms']) for card in pack['teach'].values())


def test_p2_preview_contains_every_current_form_and_review_answer():
    import re
    cards = read_json('build/work/teach/P2-1.json')
    preview = (ROOT / 'docs/benchmarks/2026-10-28-p2-guided/P2-lesson-draft.md').read_text()
    for card in cards.values():
        for form in card['forms']:
            match = re.search(r'^### ' + re.escape(form['name']) + r'\n(.*?)(?=^#{1,3} |\Z)',
                              preview, re.MULTILINE | re.DOTALL)
            assert match, form['name']
            section = match.group(1)
            assert all(wording in section for wording in form['wordings'])
            assert form['example'] in section
            assert f"**Try it:** {form['check']}" in section
            assert f"**Review answer:** {form['answer']}" in section
            for point in form['rubric']:
                assert point['point'] in section
            if retry := form.get('retry'):
                assert f"**If another try is needed:** {retry['check']}" in section
                assert f"**Review answer:** {retry['answer']}" in section
                for point in retry['rubric']:
                    assert point['point'] in section


def test_p2_candidate_satisfies_guided_structure_in_memory():
    import importlib.util
    pack = corrected_draft_pack()
    inventory = read_json('build/work/guided/P2-1-form-inventory.json')
    pack['guided_forms'] = {kc: [form['name'] for form in forms]
                            for kc, forms in inventory['forms'].items()}
    graph = read_json('build/out/specs/P2/graph.json')
    spec = importlib.util.spec_from_file_location('p2_pilot_foundry', ROOT / 'foundry/foundry.py')
    foundry = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(foundry)
    note = '\n'.join(f'![[{diagram}]]' for card in pack['teach'].values()
                     for diagram in card.get('diagrams', []))
    assets = library_course_diagrams('P2')
    assert foundry.guided_problems(pack, graph, note, assets) == []
    pack['teach']['P2-1.2']['disclosed_item_ids'] = ['missing-question']
    assert any('not in this pack' in issue for issue in foundry.guided_problems(pack, graph, note, assets))
    pack['teach']['P2-1.2']['disclosed_item_ids'] = ['P2-1-i09', 'P2-1-i09']
    assert any('unique non-empty' in issue for issue in foundry.guided_problems(pack, graph, note, assets))


def test_p2_draft_additions_preserve_staged_correction_baseline(monkeypatch):
    """Audit additions separately; this does not approve changing the real snapshot."""
    monkeypatch.syspath_prepend(str(ROOT / 'build'))
    monkeypatch.syspath_prepend(str(ROOT / 'refine'))
    from correction_review import stage_corrections
    import refine

    original = original_pack()
    proposal = read_json('build/work/refine/P2-1.corrections.json')
    note = original_note()
    baseline, corrected_note = stage_corrections(original, note, proposal)
    candidate = corrected_draft_pack()
    inventory = read_json('build/work/guided/P2-1-form-inventory.json')
    candidate['guided_forms'] = {kc: [form['name'] for form in forms]
                                 for kc, forms in inventory['forms'].items()}
    assert refine.no_loss({'pack': baseline, 'note': corrected_note}, candidate, corrected_note) == []
    assert refine.no_loss({'pack': original, 'note': note}, candidate, corrected_note)


def test_p2_correction_audit_never_hides_unrelated_changes(monkeypatch):
    monkeypatch.syspath_prepend(str(ROOT / 'build'))
    monkeypatch.syspath_prepend(str(ROOT / 'refine'))
    from correction_review import audit_corrections, stage_corrections
    import refine
    original = original_pack()
    proposal = read_json('build/work/refine/P2-1.corrections.json')
    note = original_note()
    candidate, candidate_note = stage_corrections(original, note, proposal)
    audit = audit_corrections(original, note, proposal, candidate, candidate_note, refine.no_loss)
    assert audit['against_original'] and not audit['outside_proposal']
    candidate['items'][0]['stem'] += ' accidental edit'
    audit = audit_corrections(original, note, proposal, candidate, candidate_note, refine.no_loss)
    assert any('stem' in issue for issue in audit['outside_proposal'])


def test_p2_correction_selectors_match_exact_original_and_candidate_values():
    original = original_pack()
    candidate = corrected_draft_pack()
    proposal = read_json('build/work/refine/P2-1.corrections.json')
    import sys
    sys.path.insert(0, str(ROOT / 'build'))
    from correction_review import stage_corrections
    note = original_note()
    staged, staged_note = stage_corrections(original, note, proposal)
    assert staged_note != note

    def selected(document, selector):
        value = document
        for part in selector:
            if isinstance(part, dict):
                matches = [entry for entry in value if all(entry.get(k) == v for k, v in part.items())]
                assert len(matches) == 1
                value = matches[0]
            else:
                value = value[part]
        return value

    for correction in proposal['corrections']:
        old = selected(original, correction['selector'])
        new = selected(candidate, correction['selector'])
        assert selected(staged, correction['selector']) == new
        if correction['selector'] == ['outline']:
            assert old.count(correction['old']) == 1
            assert new == old.replace(correction['old'], correction['new'])
        else:
            assert old == correction['old']
            assert new == correction['new']


def test_p2_preview_includes_current_core_content_and_diagrams():
    cards = read_json('build/work/teach/P2-1.json')
    preview_path = ROOT / 'docs/benchmarks/2026-10-28-p2-guided/P2-lesson-draft.md'
    preview = preview_path.read_text()
    import re
    for kc, card in cards.items():
        match = re.search(r'^## [^\n]*\(' + re.escape(kc) + r'\)\n(.*?)(?=^## |\Z)',
                          preview, re.MULTILINE | re.DOTALL)
        assert match, kc
        section = match.group(1)
        probe = card.get('guided_discover') or card.get('discover')
        if probe:
            assert probe['stem'] in section
            for letter, option in probe['options'].items():
                assert f'- {letter}. {option}' in section
            assert f"**Review key:** {probe['answer']}. {probe['explanation']}" in section
        for key in ('motivate', 'plain_words', 'establish', 'connect', 'self_explain'):
            assert card[key] in section, (kc, key)
        assert card['note'] in section
        for entry in card.get('exam_language', []):
            assert entry['name'] in section and entry['meaning'] in section
        for term in card['terms']:
            assert term['term'] in section and term['meaning'] in section
            assert term['notation'] in section and term['spoken'] in section
        for misconception in card['misconceptions']:
            for key in ('idea', 'temptation', 'fix'):
                assert misconception[key] in section, (kc, key)
        for path, description in zip(card['diagrams'], card['diagram_descriptions']):
            assert description in section
            assert read_bytes(path)
            assert path in section


def test_p2_series_identities_and_boundary_cases():
    import sympy as sp
    k, n = sp.symbols('k n', integer=True, positive=True)
    r = sp.symbols('r', real=True)
    assert sp.simplify(sp.summation(k, (k, 1, n)) - n * (n + 1) / 2) == 0
    assert sp.simplify(sp.summation(2 * k - 1, (k, 1, n)) - n ** 2) == 0
    assert sp.cancel((1 - r ** 2) / (1 - r)) == 1 + r
    for count in (1, 2, 3, 4, 7):
        assert sp.simplify(sum(r ** i for i in range(count)) * (1 - r) - (1 - r ** count)) == 0
        assert sum(1 ** i for i in range(count)) == count
        assert sum(3 ** i for i in range(count)) == (3 ** count - 1) // 2


def test_skipping_each_pilot_form_withholds_its_key_during_repair(tmp_path):
    vault = make_vault(tmp_path)
    pack = _stage_p2(vault)
    base = vault / '.tutor/packs/v1'
    dest = base / 'specs/P2'
    (dest / 'packs/P2-1.json').write_text(json.dumps(pack))
    tutor = session.Tutor(store.Vault(vault), rng=random.Random(0))
    for kc, card in pack['teach'].items():
        for index, form in enumerate(card['forms']):
            for worked_before in (False, True):
                tutor.start('lesson', minutes=30, focus=['P2-1'], replace=True)
                phases = (['worked'] if worked_before else []) + [f'form_check:{index}', 'done']
                block = {'kind': 'node', 'kc': kc, 'card': card, 'i': int(worked_before),
                         'phases': phases, 'misses': 0, 'mistakes': []}
                tutor.session['blocks'] = [block]
                tutor.session['cursor'] = 0
                question = tutor.next()['items'][0]
                feedback = tutor.answer(f"{question['n']}?")
                assert form['answer'] not in str(feedback), form['name']
                from tutor_app import prompts
                assert form['answer'] not in prompts.learn(tutor, kc, 'I am stuck'), form['name']
                repair = tutor.next()
                assert form['answer'] not in str(repair), form['name']
                assert form['answer'] not in (vault / 'Now.md').read_text(), form['name']
                assert repair['part'] == 'guard_pause'
                resumed = tutor.retry_skipped()['items'][0]
                tutor.answer(f"{resumed['n']} = an attempt", judge={resumed['n']: 0})
                if repair['activity'] == 'worked':
                    for step in range(1, len(repair['steps']) + 1):
                        tutor.respond({'step': step})
                        assert form['answer'] not in (vault / 'Now.md').read_text(), form['name']


def test_trigonometric_check_does_not_require_restating_given_domain():
    from tutorlib import grade
    cards = read_json('build/work/teach/P2-1.json')
    form = next(f for f in cards['P2-1.1']['forms'] if f['name'] == 'Show a trigonometric identity')
    result = grade._grade_rubric({'rubric': form['rubric']}, {'value':
        'Using the given identity the numerator is cos²θ. Dividing by cosθ gives cosθ, the RHS.'})
    assert result['score'] == 1
    assert result['needs_judgement']  # keyword matches are only a marking hint


def test_prime_domain_counterexamples_are_valid_and_distinct():
    import sympy as sp
    cards = read_json('build/work/teach/P2-1.json')
    form = next(f for f in cards['P2-1.3']['forms'] if f['name'] == 'Counterexample with a prime domain')
    assert 'prime' in form['check'].lower() and 'prime' in form['retry']['check'].lower()
    assert sp.isprime(7) and not sp.isprime(7 + 2)
    assert sp.isprime(2) and not sp.isprime(2**2 + 4)
    assert sp.isprime(2) and sp.isprime(2**2 + 1)
    assert sp.isprime(3) and not sp.isprime(3**2 + 6)
    # The earlier discovery probe already disproves n² + 2 using the prime n = 5.
    assert '$p^2+4$' in form['check'] and '$p^2+6$' in form['retry']['check']
    assert '$n^2+2$' in cards['P2-1.3']['guided_discover']['stem']
    assert "$p^2+6$" in form["retry"]["check"]
    assert "$p=3$" in form["retry"]["answer"]
    assert form['check'] != form['retry']['check']


def test_parity_check_is_not_settled_by_the_preceding_example():
    import sympy as sp
    cards = read_json('build/work/teach/P2-1.json')
    form = next(f for f in cards['P2-1.2']['forms'] if f['name'] == 'Finite classes covering an infinite domain')
    assert '$n(n+1)$ is even' in form['example']
    assert '$n^3$' in form['check'] and '$n^4$' in form['retry']['check']
    k = sp.symbols('k', integer=True)
    assert sp.expand((2*k+1)**4 - (2*(8*k**4+16*k**3+12*k**2+4*k)+1)) == 0


def test_general_geometric_check_covers_zero_negative_and_fractional_ratios():
    import sympy as sp
    cards = read_json('build/work/teach/P2-1.json')
    form = next(f for f in cards['P2-1.1']['forms'] if f['name'] == 'Geometric-series proof by cancellation')
    assert r'$r\ne1$' in form['check'] and 'unfactorised' in form['check']
    assert r'$S-rS=a-ar^n$' in form['answer']
    for ratio in (sp.Integer(0), sp.Integer(-2), sp.Rational(1, 2), sp.Integer(3)):
        for n in (3, 4, 7):
            total = sum(2 * ratio**i for i in range(n))
            assert sp.simplify(total - 2*(1-ratio**n)/(1-ratio)) == 0


def test_geometric_check_uses_distinct_lengths_and_gradients():
    import sympy as sp
    cards = read_json('build/work/teach/P2-1.json')
    form = next(f for f in cards['P2-1.1']['forms'] if f['name'] == 'Geometric proof with alternative chains of reasoning')
    assert '$C=(8,4)$' in form['check']
    assert '$AC^2=80$' in form['answer'] and '$BC^2=20$' in form['answer']
    assert 8**2 + 4**2 == 80 and (10-8)**2 + 4**2 == 20
    assert sp.Rational(4, 8) * sp.Rational(4, 8-10) == -1


def test_geometric_retry_does_not_repeat_worked_gradients():
    import sympy as sp
    cards = read_json('build/work/teach/P2-1.json')
    retry = next(f for f in cards['P2-1.1']['forms'] if f['name'] == 'Geometric proof with alternative chains of reasoning')['retry']
    assert '$B=(13,0)$' in retry['check'] and '$C=(4,6)$' in retry['check']
    assert '$AC^2=52$' in retry['answer'] and '$BC^2=117$' in retry['answer']
    assert 4**2 + 6**2 == 52 and (13-4)**2 + 6**2 == 117
    assert 52 + 117 == 13**2
    assert sp.Rational(6, 4) * sp.Rational(6, 4-13) == -1


def test_constrained_pairs_proof_checks_every_allowed_case():
    cards = read_json('build/work/teach/P2-1.json')
    form = next(f for f in cards['P2-1.2']['forms'] if f['name'] == 'Exhaustion with constrained positive integers')
    def pairs(total):
        return [(a, total-a) for a in range(1, total) if a <= total-a]
    assert pairs(4) == [(1, 3), (2, 2)]
    assert pairs(5) == [(1, 4), (2, 3)]
    assert all(a*b % 2 == 0 for a, b in pairs(5))
    assert pairs(6) == [(1, 5), (2, 4), (3, 3)]
    assert all(a*b <= 9 for a, b in pairs(6))
    assert 'sum is $5$' in form['check'] and 'sum is $6$' in form['retry']['check']


def test_three_variable_exhaustion_respects_both_constraints():
    cards = read_json('build/work/teach/P2-1.json')
    form = next(f for f in cards['P2-1.2']['forms'] if f['name'] == 'Exhaustion with two simultaneous constraints')
    def cases(total):
        return [(a, b, c) for a in range(1, total) for b in range(1, total)
                for c in range(1, total) if a+b+c == total and c == b+1]
    assert cases(9) == [(2, 3, 4), (4, 2, 3), (6, 1, 2)]
    assert cases(11) == [(2, 4, 5), (4, 3, 4), (6, 2, 3), (8, 1, 2)]
    assert cases(7) == [(2, 2, 3), (4, 1, 2)]
    assert all(a*b*c % 2 == 0 for total in (7, 9, 11) for a,b,c in cases(total))
    assert '$a+b+c=11$' in form['check'] and '$a+b+c=7$' in form['retry']['check']


def test_square_and_consecutive_prime_forms_have_valid_distinct_answers():
    import sympy as sp
    cards = read_json('build/work/teach/P2-1.json')
    square = next(f for f in cards['P2-1.1']['forms'] if f['name'] == 'Prove an inequality using a non-negative square')
    primes = next(f for f in cards['P2-1.3']['forms'] if f['name'] == 'Counterexample involving consecutive primes')
    x = sp.symbols('x', real=True)
    assert sp.expand((x-1)**2 - (x*x+1-2*x)) == 0
    assert sp.expand((x-2)**2 - (x*x+4-4*x)) == 0
    assert sp.expand((x+3)**2 - (x*x+6*x+10-1)) == 0
    triples = [(3, 5, 7), (5, 7, 11), (2, 3, 5)]
    for triple in triples:
        assert all(sp.isprime(n) for n in triple)
        assert all(sp.nextprime(a) == b for a, b in zip(triple, triple[1:]))
    assert sum(triples[0]) % 5 == 0 and sum(triples[0]) % 2 == 1
    assert sum(triples[1]) % 5 != 0 and sum(triples[1]) % 2 == 1
    assert sum(triples[2]) % 2 == 0
    assert square['check'] != square['retry']['check']
    assert primes['check'] != primes['retry']['check']


def test_square_root_inequality_form_tracks_the_real_domain():
    import sympy as sp
    cards = read_json('build/work/teach/P2-1.json')
    form = next(f for f in cards['P2-1.1']['forms'] if f['name'] == 'Prove an inequality involving a square root')
    x = sp.symbols('x', nonnegative=True)
    assert sp.simplify((sp.sqrt(x)-1)**2 - (x+1-2*sp.sqrt(x))) == 0
    assert sp.simplify((sp.sqrt(x)-2)**2 - (x+4-4*sp.sqrt(x))) == 0
    assert sp.simplify((sp.sqrt(x)-3)**2 - (x+9-6*sp.sqrt(x))) == 0
    assert 'x\\geq0' in form['check'] and 'x\\geq0' in form['retry']['check']


def test_automatic_lesson_diagram_is_withheld_for_skipped_answer(tmp_path):
    vault = make_vault(tmp_path)
    tutor = session.Tutor(store.Vault(vault), rng=random.Random(0))
    tutor.start('lesson', minutes=30, focus=['9702-2.1'])
    tutor.session['skipped_answer_guards'] = {'item': {'key': 'secret', 'kind': 'short'}}
    activity = {'activity': 'explain', 'block_idx': 0, 'kc': '9702-2.1.1', 'part': 'diagram:0',
                'title': 'Diagram', 'text': 'The answer is secret.', 'diagram': 'Assets/secret.svg'}
    shown = tutor._await(activity)
    assert 'diagram' not in shown and 'secret' not in str(shown)
    assert 'Assets/secret.svg' not in (vault / 'Now.md').read_text()
    assert activity['diagram'] == 'Assets/secret.svg'
    tutor._save()
    recovered = session.Tutor(store.Vault(vault), rng=random.Random(0))
    assert 'diagram' not in recovered.session['awaiting']
    assert 'Assets/secret.svg' not in str(recovered.session['thread'])
    example = {'activity': 'explain', 'block_idx': 0, 'kc': '9702-2.1.1', 'part': 'form_example',
               'title': 'Example', 'text': 'A separate example.', 'diagram': 'Assets/secret.svg',
               'diagram_description': 'The answer is secret.'}
    shown = recovered._await(example)
    assert shown['text'] == 'A separate example.'
    assert 'diagram' not in shown and 'diagram_description' not in shown
    assert 'The answer is secret.' not in (vault / 'Now.md').read_text()


def test_replacement_discover_probe_options_are_correct():
    import sympy as sp
    cards = read_json('build/work/teach/P2-1.json')
    original = original_pack()['teach']
    for kc in ('P2-1.1', 'P2-1.2', 'P2-1.3'):
        assert cards[kc]['discover'] == original[kc]['discover']
    domain = cards['P2-1.1']['guided_discover']
    assert domain['answer'] == 'C' and domain['options']['C'] == '$n=k+211$'
    for n in (-3, 0, 2, 19):
        assert (n - 211) + 211 == n
    assert -1 not in [k*k for k in range(-10, 11)]
    pair = cards['P2-1.2']['guided_discover']
    assert pair['answer'] == 'A' and pair['options']['A'] == '$(9,9)$'
    allowed = {1, 7, 9}
    assert 9 in allowed and all(not set(p) <= allowed for p in ((1, 8), (8, 8), (0, 7)))
    prime = cards['P2-1.3']['guided_discover']
    assert prime['answer'] == 'A' and '27=3\\times9' in prime['options']['A']
    assert 5**2 + 2 == 27 and not sp.isprime(27)
    assert all(sp.isprime(n*n + 2) for n in (1, 3, 9))


def test_replacement_discover_probes_pause_until_attempt_then_resume(tmp_path):
    vault = make_vault(tmp_path)
    pack = _stage_p2(vault)
    base = vault / '.tutor/packs/v1'
    dest = base / 'specs/P2'
    (dest / 'packs/P2-1.json').write_text(json.dumps(pack))
    tutor = session.Tutor(store.Vault(vault), rng=random.Random(0))
    for kc in ('P2-1.1', 'P2-1.2', 'P2-1.3'):
        card = pack['teach'][kc]
        expected = card['guided_discover']['options'][card['guided_discover']['answer']]
        tutor.start('lesson', minutes=30, focus=['P2-1'], replace=True)
        block = {'kind': 'node', 'kc': kc, 'card': card, 'i': 0,
                 'phases': ['discover', 'terms', 'plain_words', 'establish', 'worked', 'done'],
                 'misses': 0, 'mistakes': []}
        tutor.session['blocks'] = [block]
        tutor.session['cursor'] = 0
        question = tutor.next()['items'][0]
        assert tutor.session['presented'][str(question['n'])]['item'] == f'{kc}-guided-discover'
        feedback = tutor.answer(f"{question['n']}?")
        assert expected not in str(feedback)
        paused = tutor.next()
        assert paused['part'] == 'guard_pause' and expected not in str(paused)
        retried = tutor.retry_skipped()['items'][0]
        assert retried['stem'] == question['stem']
        tutor.answer(f"{retried['n']}{card['guided_discover']['answer']}3")
        seen = set()
        for _ in range(12):
            act = tutor.next()
            seen.add(act.get('part') or act['activity'])
            if act['activity'] == 'end':
                break
            if act['activity'] in ('worked', 'walkthrough'):
                for step in range(1, len(act['steps']) + 1):
                    tutor.respond({'step': step})
                tutor.respond({'done': True})
            elif act['activity'] in ('explain', 'own_words', 'stuck', 'refute'):
                tutor.respond({})
            else:
                break
        assert {'plain_words', 'establish', 'worked'} <= seen


def test_factor_theorem_form_has_correct_roots_and_parameters():
    import sympy as sp
    cards = read_json('build/work/teach/P2-1.json')
    form = next(f for f in cards['P2-1.1']['forms'] if f['name'] == 'Show a parameter using the factor theorem')
    x, k, a, b = sp.symbols('x k a b')
    assert '$x-1$' in form['example'] and '$k=-3$' in form['example']
    assert sp.solve((x**2 + k*x + 2).subs(x, 1), k) == [-3]
    assert '$x-2$' in form['check'] and '$a=1$' in form['check']
    assert sp.solve((x**2 + a*x - 6).subs(x, 2), a) == [1]
    assert '$x+2$' in form['retry']['check'] and '$b=5$' in form['retry']['check']
    assert sp.solve((x**2 + b*x + 6).subs(x, -2), b) == [5]
    for exercise in (form, form['retry']):
        assert 'Alternatively, substitute' not in exercise['answer']
        assert all('or substitutes' not in point['point'] and 'or verifies' not in point['point']
                   for point in exercise['rubric'])


def test_new_proof_terms_enter_the_review_queue_and_record_a_review(tmp_path):
    from datetime import timedelta
    from tutorlib import lesson, policy
    vault = make_vault(tmp_path)
    pack = _stage_p2(vault)
    base = vault / '.tutor/packs/v1'
    dest = base / 'specs/P2'
    (dest / 'packs/P2-1.json').write_text(json.dumps(pack))
    tutor = session.Tutor(store.Vault(vault), rng=random.Random(0))
    tutor.start('lesson', minutes=30, focus=['P2-1'])
    for kc, term in [('P2-1.1', 'Product'), ('P2-1.1', 'Factor theorem'), ('P2-1.3', 'Consecutive primes')]:
        block = {'kind': 'node', 'kc': kc, 'card': pack['teach'][kc], 'i': 0,
                 'phases': ['terms', 'done'], 'misses': 0, 'mistakes': []}
        tutor.session['blocks'] = [block]
        tutor.session['cursor'] = 0
        activity = tutor.next()
        assert activity['part'] == 'terms' and term in activity['text']
        tutor.respond({})
        tid = lesson.term_id(kc, term)
        assert tid in policy.review_terms(tutor.state, tutor.packs, tutor.now() + timedelta(seconds=1))
        tutor.session['blocks'] = [{'kind': 'term_review', 'terms': [tid]}]
        tutor.session['cursor'] = 0
        question = tutor.next()['items'][0]
        definition = next(t['meaning'] for t in pack['teach'][kc]['terms'] if t['term'] == term)
        pending = tutor.session['presented'][str(question['n'])]['inst']
        assert term in question['stem'] and 'rubric' not in question
        assert definition not in str(question) and pending['review_answer'] == definition
        result = tutor.answer(f"{question['n']} = My definition", judge={question['n']: 1})
        assert result['results'][0]['answer'] == definition
        assert tutor.state['terms'][tid]['reviews'] == 1
        restored = session.Tutor(store.Vault(vault), rng=random.Random(0))
        assert restored.state['terms'][tid]['reviews'] == 1


def test_p2_candidate_passes_pack_and_content_checks_in_memory(monkeypatch):
    monkeypatch.syspath_prepend(str(ROOT / 'build'))
    import content_checks
    import validate_pack
    pack = corrected_draft_pack()
    graph = read_json('build/out/specs/P2/graph.json')
    assert validate_pack.validate(pack, graph) == []
    for check in (content_checks.latex_problems, content_checks.debris_problems,
                  content_checks.stacked_problems, content_checks.precision_problems,
                  content_checks.id_problems, content_checks.letter_problems):
        assert check(pack) == [], check.__name__


def test_pilot_teaching_text_does_not_repeat_later_review_answers_verbatim():
    cards = read_json('build/work/teach/P2-1.json')
    for kc, card in cards.items():
        prior = '\n'.join(str(card.get(key, '')) for key in
                          ('motivate', 'plain_words', 'establish', 'connect', 'self_explain'))
        for form in card['forms']:
            prior += '\n' + form['example']
            assert form['answer'] not in prior, (kc, form['name'])
            assert form['retry']['answer'] not in prior, (kc, form['name'], 'retry')
            prior += '\n' + form['check'] + '\n' + form['answer']


def test_june_2019_inspired_show_that_examples_and_checks():
    import sympy as sp
    cards = read_json('build/work/teach/P2-1.json')
    forms = {f['name']: f for f in cards['P2-1.1']['forms']}
    x, c = sp.symbols('x c')
    approx = forms['Show an approximation from binomial expansions']
    assert 'degree $4$' in approx['check']
    assert sp.series((1+x)**4 + (1-x)**4, x, 0, 4).removeO().expand() == 2+12*x**2
    assert sp.series((1+x)**5 + (1-x)**5, x, 0, 4).removeO().expand() == 2+20*x**2
    assert sp.expand((2+x)**3+(2-x)**3) == 16+12*x**2
    trig = forms['Transform a trigonometric equation']
    assert r'\cos\theta\ne0' in trig['example'] and r'\cos\theta\ne0' in trig['check']
    assert sp.expand(c**2+c-2*(1-c**2)) == 3*c**2+c-2
    assert sp.expand(c**2-c-3*(1-c**2)) == 4*c**2-c-3
    integral = forms['Show a stated definite integral']
    assert 'both substituted values' in integral['check']
    assert sp.integrate(x-1, (x, 0, 2)) == 0
    assert sp.integrate(2*x-4, (x, 1, 3)) == 0
    assert sp.integrate(3*x**2-4*x, (x, 0, 2)) == 0


def test_quadratic_gradient_form_uses_correct_derivatives_and_discriminants():
    """The example and both checks must retain their independently verified arithmetic."""
    import sympy as sp
    cards = read_json('build/work/teach/P2-1.json')
    form = next(f for f in cards['P2-1.1']['forms']
                if f['name'] == 'Prove no turning points using a quadratic gradient')
    x = sp.symbols('x', real=True)
    assert '3x^2-6x+5' in form['example'] and '-24' in form['example']
    assert sp.discriminant(3*x**2-6*x+5, x) == -24
    for question, answer, curve_text, gradient_text, curve, gradient, square, discriminant in (
        (form['check'], form['answer'], 'x^3-3x^2+4x', '3x^2-6x+4', x**3-3*x**2+4*x, 3*x**2-6*x+4, 3*(x-1)**2+1, -12),
        (form['retry']['check'], form['retry']['answer'], '2x^3-6x^2+7x', '6x^2-12x+7', 2*x**3-6*x**2+7*x, 6*x**2-12*x+7, 6*(x-1)**2+1, -24),
    ):
        assert curve_text in question and gradient_text in question
        assert str(discriminant) in answer
        assert 'derivative' in question and 'turning points' in question
        assert sp.diff(curve, x) == gradient == sp.expand(square)
        assert sp.discriminant(gradient, x) == discriminant < 0
        assert sp.solveset(gradient, x, domain=sp.S.Reals) == sp.S.EmptySet


def test_geometric_and_domain_retries_do_not_reuse_disclosed_answer_route():
    cards = read_json('build/work/teach/P2-1.json')
    geometric = next(f for f in cards['P2-1.1']['forms'] if f['name'] == 'Geometric-series proof by cancellation')
    assert 'sum $85$' in geometric['retry']['check']
    assert 'exactly $4$ terms' in geometric['retry']['check']
    assert '$4^n=256=4^4$' in geometric['retry']['answer']
    widened = next(f for f in cards['P2-1.3']['forms'] if f['name'] == 'Counterexample after widening the domain')
    assert 'positive real' in widened['retry']['check']
    assert '$x=1$' in widened['retry']['answer'] and '$y=2$' in widened['retry']['answer']
