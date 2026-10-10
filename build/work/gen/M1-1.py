"""Generate the M1-1 modelling pack from checked question data."""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
SUB = 'M1-1'
KC = 'M1-1.1'
SOURCE = {'type': 'generated'}
items = []

misconceptions = [
    {'id': 'm1', 'kc': KC, 'statement': 'A particle has no mass.', 'refutation': 'A particle has mass, but its dimensions are negligible for the problem.', 'contrast': 'A vehicle can be treated as a particle when only its motion along a route matters.', 'source': 'research'},
    {'id': 'm2', 'kc': KC, 'statement': 'A light rod or string has zero tension or force.', 'refutation': 'Light means its mass is negligible; it can still transmit a force.', 'contrast': 'A light string can pull with non-zero tension.', 'source': 'research'},
    {'id': 'm3', 'kc': KC, 'statement': 'A smooth surface or pulley has no normal reaction or tension.', 'refutation': 'Smooth removes friction, not the normal reaction or the tension in a string.', 'contrast': 'A block on a smooth table still experiences a normal reaction.', 'source': 'research'},
    {'id': 'm4', 'kc': KC, 'statement': 'Uniform means the same as light or rigid.', 'refutation': 'Uniform describes even mass distribution; light describes negligible mass and rigid describes no deformation.', 'contrast': 'A uniform heavy rod may be rigid and has its centre of mass at its midpoint.', 'source': 'research'},
    {'id': 'm5', 'kc': KC, 'statement': 'Inextensible means the string cannot move.', 'refutation': 'Its length stays constant; different parts can still move.', 'contrast': 'For a taut inextensible string over a fixed pulley, connected particles have equal displacement magnitudes.', 'source': 'research'},
]


def short(stem, points, *, difficulty=2, word='State', explanation=None, hints=None):
    rubric = [{'point': point, 'keywords': [[term] for term in terms]} for point, terms in points]
    items.append({'id': f'{SUB}-i{len(items)+1:02}', 'kcs': [KC], 'kind': 'short',
                  'difficulty': difficulty, 'command_word': word, 'source': SOURCE,
                  'stem': f'{word} {stem}', 'marks': len(rubric), 'rubric': rubric,
                  'explanation': explanation or ' '.join(p for p, _ in points),
                  'hints': hints or ['Identify which property of the model matters.',
                                    'Connect the stated assumption to a physical quantity.',
                                    'Write the implication in the context of the object.']})


def mcq(stem, options, answer, wrong, *, difficulty=2, word='Find', explanation, hints=None):
    assert set(options) == set('ABCD') and len(set(options.values())) == 4
    assert answer in options and all(letter != answer for letter in wrong)
    assert all(mid in {m['id'] for m in misconceptions} for mid in wrong.values())
    items.append({'id': f'{SUB}-i{len(items)+1:02}', 'kcs': [KC], 'kind': 'mcq',
                  'difficulty': difficulty, 'command_word': word, 'source': SOURCE,
                  'stem': f'{word} {stem}', 'marks': 1, 'options': options, 'answer': answer,
                  'distractors': wrong, 'shuffle': True, 'explanation': explanation,
                  'hints': hints or ['Focus on what the model simplifies.',
                                    'Separate mass, size, and deformation.',
                                    'Check which physical property the adjective describes.']})


short('what is meant by treating a body as a particle.',
      [('It has mass but negligible dimensions for the problem.', ['mass', 'negligible'])],
      difficulty=1, explanation='The body retains its mass; its size and shape have no effect on the motion being modelled.')
short('what is meant by a lamina.',
      [('A thin flat sheet whose thickness is negligible compared with its other dimensions.', ['flat', 'thickness', 'negligible'])],
      difficulty=1)
short('what is meant by a rigid body.',
      [('Its shape and size do not change under the forces considered.', ['shape', 'do not change'])],
      difficulty=1)
mcq('the property represented by a light rod.',
    {'A': 'Its mass is negligible.', 'B': 'Its length is negligible.',
     'C': 'It cannot transmit a force.', 'D': 'Its mass is evenly distributed.'},
    'A', {'C': 'm2', 'D': 'm4'},
    explanation='Light means negligible mass, so the rod can still transmit force. Equal mass distribution describes a uniform rod.')
short('the difference between a uniform rod and a non-uniform rod.',
      [('A uniform rod has mass evenly distributed along its length.', ['mass', 'evenly']),
       ('A non-uniform rod does not have mass evenly distributed along its length.', ['non-uniform', 'not evenly'])],
      explanation='A uniform rod has constant mass per unit length, so its centre of mass is at its midpoint. A non-uniform rod need not have its centre of mass there.')
short('the two assumptions for a light inextensible string.',
      [('Its mass is negligible.', ['mass', 'negligible']),
       ('Its length remains constant when pulled taut.', ['length', 'constant'])],
      difficulty=2, explanation='Light removes the string’s own weight from the model. Inextensible means it does not stretch; tension may still be present.')
mcq('the force that a smooth horizontal table can exert on a resting block.',
    {'A': 'A normal reaction but no friction.', 'B': 'Neither a normal reaction nor friction.',
     'C': 'Friction but no normal reaction.', 'D': 'A fixed friction force and a normal reaction.'},
    'A', {'B': 'm3', 'C': 'm3', 'D': 'm3'},
    difficulty=3, explanation='Smooth means frictionless contact. The table can still exert a normal reaction on the block.')
short('what a rough surface permits that a smooth surface does not.',
      [('A rough surface can exert friction tangential to the contact.', ['friction', 'tangential'])],
      explanation='Rough contact can exert friction; its size depends on the situation. Smooth contact has no friction.')
short('the assumptions of a light smooth pulley.',
      [('Its mass is negligible.', ['mass', 'negligible']),
       ('There is no friction between the pulley and the string.', ['friction', 'no'])],
      explanation='The pulley’s mass and bearing friction are neglected. With a light string, the tension is the same on both sides of a smooth pulley.')
mcq('what inextensibility implies for two particles joined by a taut string over a fixed pulley.',
    {'A': 'They have equal displacement magnitudes along the string.',
     'B': 'Both particles remain stationary.',
     'C': 'The string has zero tension.',
     'D': 'Both particles have equal mass.'},
    'A', {'B': 'm5', 'C': 'm2'}, difficulty=4,
    explanation='The total taut string length is fixed, so one end moving a given distance makes the other end move the same distance along the string. The particles can move and may have different masses.')
short('what is meant by a bead moving on a wire.',
      [('A small object is constrained to move along the wire.', ['constrained', 'wire'])],
      explanation='A bead is modelled as a small object threaded on a wire; its path is constrained by the wire. Contact friction depends on whether the wire is specified as smooth.')
short('how a peg differs from a pulley in a string model.',
      [('A peg is a fixed small support about which the string can pass.', ['fixed', 'support']),
       ('A pulley is a wheel that can rotate as the string moves.', ['wheel', 'rotate'])],
      difficulty=3, word='Explain', explanation='A peg is fixed and a pulley rotates. A peg must be specified as smooth before friction can be neglected.')
short('why a uniform rigid rod can have a non-zero weight even if its shape does not change.',
      [('Rigid describes lack of deformation, not lack of mass.', ['rigid', 'mass']),
       ('Uniform describes even mass distribution, with weight acting through the midpoint in a uniform gravitational field.', ['uniform', 'midpoint'])],
      difficulty=4, word='Explain', explanation='Rigid and uniform describe different properties. A uniform rod may be heavy; its centre of mass is at the midpoint.')
short('the modelling assumptions needed to use equal tension on both sides of a pulley in a connected-particle problem.',
      [('The string is light, so its mass is negligible.', ['string', 'light']),
       ('The pulley is smooth, so friction at contact is neglected.', ['pulley', 'smooth'])],
      difficulty=4, word='Explain', explanation='For a light string passing over a smooth pulley, tension is equal on the two sides. Light alone does not remove pulley friction.')
short('whether a rough wire guarantees friction acts on a stationary bead, and give a reason.',
      [('Roughness permits friction but does not guarantee a non-zero friction force.', ['permits', 'not guarantee']),
       ('Friction depends on the tendency for relative motion.', ['relative', 'motion'])],
      difficulty=4, word='Explain', explanation='Rough means friction is available. If there is no tendency to slip along the wire, the friction force can be zero.')

flashcards = [
    ('What is a particle?', 'A body with mass whose dimensions are negligible in the problem.'),
    ('What is a lamina?', 'A flat sheet whose thickness is negligible compared with its other dimensions.'),
    ('What is a rigid body?', 'A body whose shape and size do not change under the forces considered.'),
    ('What do light, uniform and non-uniform mean for a rod?', 'Light: negligible mass. Uniform: mass evenly distributed along its length. Non-uniform: mass not evenly distributed.'),
    ('What is a light inextensible string?', 'A string with negligible mass whose length remains constant when taut.'),
    ('What is a smooth surface? What is a rough surface?', 'A smooth surface exerts no friction; a rough surface may exert friction.'),
    ('What is a light smooth pulley?', 'A pulley of negligible mass with no friction at the string contact; for a light string, tension is equal on both sides.'),
    ('What are a bead, wire and peg in mechanics?', 'A bead is a small object constrained to move on a wire. A wire provides its path. A peg is a fixed small support around which a string may pass.'),
]
pack = {'subtopic': SUB, 'spec': 'M1', 'version': 1,
        'note': 'Subjects/Maths/M1 Mechanics 1/1 Mathematical models in mechanics.md',
        'outline': 'Mechanics replaces objects and contacts with idealised models. A particle has mass but negligible size; a lamina has negligible thickness; a rigid body does not deform. Light means negligible mass, uniform means evenly distributed mass, and inextensible means fixed length. Smooth contact has no friction, while rough contact may have friction. A light smooth pulley with a light string gives equal tension on both sides. A bead is constrained to a wire; a peg is a fixed support. Choose each assumption for the property relevant to the problem.',
        'misconceptions': misconceptions, 'worked': [], 'items': items,
        'flashcards': [{'id': f'fc{i+1}', 'kc': KC, 'front': front, 'back': back}
                       for i, (front, back) in enumerate(flashcards)], 'diagrams': []}
assert len(items) >= 6 and all(item['kcs'] == [KC] for item in items)
path = ROOT / 'build/out/packs/M1/M1-1.json'
path.parent.mkdir(parents=True, exist_ok=True)
path.write_text(json.dumps(pack, ensure_ascii=False, indent=1) + '\n')
print(path, len(items), 'items')
