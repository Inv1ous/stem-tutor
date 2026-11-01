"""A new lesson places its overview figure beside its prepared explanation."""
import pytest

from tutorlib import lesson, session, store
from fixtures import make_vault


@pytest.mark.parametrize("path_keyed", [False, True])
def test_overview_diagram_accompanies_explanation_and_survives_resume(tmp_path, monkeypatch, path_keyed):
    vault = make_vault(tmp_path)
    card = {'motivate': 'Start with the motion.', 'establish': 'Displacement has a direction.',
            'note': '- Displacement is a vector.', 'plain_words': 'Compare the start and finish.',
            'diagrams': ['Assets/test.svg'], 'diagram_descriptions': ['An arrow joins the two positions.']}
    description = card['diagram_descriptions'][0]
    if path_keyed:
        card['diagram_descriptions'] = {card['diagrams'][0]: description}
    monkeypatch.setattr(lesson, 'teach_card', lambda tutor, kc: card)
    tutor = session.Tutor(store.Vault(vault))
    tutor.start('lesson', minutes=20, focus=['9702-2.1'])
    assert tutor.next()['purpose'] == 'goal'
    tutor.respond({'choice': 'scratch'})
    plan = tutor.next()
    kc = plan['default_teach'][0]
    tutor.respond({'teach': [kc]})
    for _ in range(10):
        act = tutor.next()
        if act.get('part') == 'plain_words':
            break
        tutor.respond({})
    assert act.get('diagram') == 'Assets/test.svg'
    assert act.get('diagram_description') == description
    block = tutor.session['blocks'][tutor.session['cursor']]
    assert 'diagram:0' not in block['phases'], 'The overview is already shown with the explanation.'
    resumed = session.Tutor(store.Vault(vault))
    assert resumed.next() == act
    assert resumed.session['blocks'][resumed.session['cursor']]['i'] == block['i']


def test_overview_figure_is_withheld_for_a_guard_from_an_earlier_session(tmp_path, monkeypatch):
    tutor = session.Tutor(store.Vault(make_vault(tmp_path)))
    tutor.start('lesson', minutes=20, focus=['9702-2.1'])
    monkeypatch.setattr(tutor, 'marking_guards', lambda: {'earlier': {'key': 'secret'}})
    activity = {'activity': 'explain', 'kc': '9702-2.1.1', 'part': 'plain_words',
                'text': 'Read this idea.', 'diagram': 'Assets/test.svg', 'diagram_description': 'PRIVATE PICTURE'}
    shown = tutor._await(activity)
    assert 'diagram' not in shown and 'diagram_description' not in shown
    assert 'PRIVATE PICTURE' not in str(tutor.session['now'])
