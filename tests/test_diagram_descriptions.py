"""Legacy path-keyed descriptions remain readable without rewriting protected cards."""
from copy import deepcopy

from build.teach_cards import check_card
from build.written_review import _visible_diagram
from tutorlib.lesson import overview_figure


def test_mapping_descriptions_follow_diagram_order_without_mutation():
    card = {'diagrams': ['b.svg', 'a.svg'],
            'diagram_descriptions': {'a.svg': 'Figure A', 'b.svg': 'Figure B'}}
    before = deepcopy(card)
    assert overview_figure(card)['diagram_description'] == 'Figure B'
    assert _visible_diagram('a.svg', card, None)['description'] == 'Figure A'
    assert card == before


def test_guided_validator_accepts_complete_path_mapping():
    card = {'diagrams': ['b.svg', 'a.svg'],
            'diagram_descriptions': {'a.svg': 'Figure A', 'b.svg': 'Figure B'}}
    assert not any('diagram_descriptions' in e for e in check_card('kc', card, guided=True))


def test_guided_validator_rejects_incomplete_or_invalid_mapping():
    for descriptions in ({'a.svg': 'Figure A'}, {'a.svg': 'Figure A', 'b.svg': ''},
                         {'a.svg': 'Figure A', 'b.svg': 42}, {'unrelated.svg': 'Figure'}):
        card = {'diagrams': ['b.svg', 'a.svg'], 'diagram_descriptions': descriptions}
        assert any('diagram_descriptions' in e for e in check_card('kc', card, guided=True))


def test_foundry_counts_path_mapped_descriptions_as_display_use():
    import importlib.util
    from pathlib import Path
    spec = importlib.util.spec_from_file_location('diagram_schema_foundry', Path(__file__).parents[1] / 'foundry/foundry.py')
    foundry = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(foundry)
    card = {'diagrams': ['b.svg', 'a.svg'],
            'diagram_descriptions': {'a.svg': 'Figure A', 'b.svg': 'Figure B'}}
    assert foundry._card_display_paths({'teach': {'kc': card}}) == {'a.svg', 'b.svg'}


def test_missing_map_binding_stays_missing_and_extra_keys_are_rejected():
    from tutorlib.card_diagrams import diagram_descriptions, valid_diagram_descriptions
    card = {'diagrams': ['b.svg', 'a.svg'], 'diagram_descriptions': {'a.svg': 'Figure A'}}
    assert diagram_descriptions(card) == ['', 'Figure A']
    assert not valid_diagram_descriptions(card)
    card['diagram_descriptions'].update({'b.svg': 'Figure B', 'c.svg': 'Extra'})
    assert not valid_diagram_descriptions(card)
