"""Build the 9702-3.2 teaching pack (non-uniform motion: friction, drag, terminal velocity).

All computed values originate here; the JSON is never hand-edited.
"""
from __future__ import annotations
import json
from itertools import product
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
OUT = ROOT / 'build/out/packs/9702/9702-3.2.json'
BANK = {q['id']: q for q in json.loads((ROOT / 'build/work/mcq/9702.tagged.json').read_text())}
FIX = {q: {k: v for k, v in f.items() if k in ('stem', 'options')}
       for q, f in json.loads((ROOT / 'build/work/mcq/overrides.json').read_text()).items()}
K = lambda n: f'9702-3.2.{n}'  # noqa: E731
G = 9.81

mis = [
 dict(id='m1', kc=K(1),
      statement='The drag force on a body has a fixed value set by the fluid, so it does not change as the body speeds up.',
      refutation='Drag arises from the body pushing fluid out of its path, so it is zero at rest and grows as the speed grows.',
      contrast='A graph of drag force against speed starts at the origin and rises; it is not a horizontal line.',
      source='ER 9702 s23 P11 Q9'),
 dict(id='m2', kc=K(2),
      statement='Once air resistance acts on a falling object, the object slows down.',
      refutation='While the weight still exceeds the air resistance the resultant force is downwards, so the object keeps speeding up — just less rapidly.',
      contrast='Air resistance gives a decreasing acceleration, not a deceleration, until the forces balance.',
      source='ER 9702 w23 P22 Q2'),
 dict(id='m3', kc=K(3),
      statement='Resistive forces can be left out of the force balance: the resultant force on a falling body stays equal to its weight, so its acceleration stays at $9.81\\ \\mathrm{m\\,s^{-2}}$.',
      refutation='The resultant force is the weight minus every upward force (air resistance or viscous drag, and upthrust in a liquid), so it shrinks as the drag grows and is zero at terminal velocity.',
      contrast='At terminal velocity the acceleration is zero, not $9.81\\ \\mathrm{m\\,s^{-2}}$.',
      source='ER 9702 w23 P12 Q9'),
 dict(id='m4', kc=K(3),
      statement='A body falling at terminal velocity is still converting gravitational potential energy into its own kinetic energy.',
      refutation='The velocity is constant, so the kinetic energy of the body is constant; the lost potential energy goes to the body and the fluid as thermal energy and to kinetic energy of the fluid.',
      contrast='Kinetic energy of the falling body only grows while it is accelerating.',
      source='ER 9702 s21 P12 Q15'),
 dict(id='m5', kc=K(3),
      statement='Two bodies of the same size and shape must reach the same terminal velocity whatever their masses.',
      refutation='Terminal velocity is reached when drag balances weight, so a heavier body needs a larger drag force and must therefore be moving faster.',
      contrast='Same shape, larger mass $\\Rightarrow$ larger terminal velocity.',
      source='ER 9702 s23 P13 Q9'),
]

# (bank id, kc, difficulty, command word, explanation, distractor -> misconception)
past_info = [
 ('9702_s23_11_q9', K(1), 3, 'Identify',
  'The drag force is zero while the ball is at rest and grows as the ball speeds up, so the graph must start at the origin and rise. A line of constant height would say the drag never changes with speed.',
  {'B': 'm1', 'C': 'm1'}),
 ('9702_w21_13_q9', K(2), 4, 'Identify',
  'After falling a long way the skydiver is at terminal velocity, so the acceleration has fallen to zero: $a$ starts at $9.81\\ \\mathrm{m\\,s^{-2}}$ and decays to zero. Graph B was often chosen because it looks like the velocity–distance graph, but it shows a non-zero final acceleration.',
  {'B': 'm3', 'C': 'm3', 'D': 'm3'}),
 ('9702_w19_12_q8', K(2), 4, 'Identify',
  'The gradient of the displacement–time graph is the velocity, so it must increase from zero and then become constant at terminal velocity. B was almost as popular but its gradient decreases at the start, which would mean the ball slowed down as soon as it was released.',
  {'A': 'm2', 'B': 'm2'}),
 ('9702_w19_11_q9', K(2), 4, 'Describe',
  'The skydiver speeds up, so $v$ increases; the growing air resistance cuts the resultant force $mg - F$, so $a$ decreases. The majority chose C, keeping the acceleration constant and so ignoring the increase in air resistance with speed.',
  {'C': 'm1', 'A': 'm2', 'B': 'm2'}),
 ('9702_s19_11_q10', K(2), 4, 'Identify',
  'At any given speed the lighter stone meets the same resistive force $F$ but has a smaller resultant force $mg - F$, so it accelerates less and falls a shorter distance in the same time (graph C). B was the common error, placing the lighter stone ahead of the heavier one.',
  {'B': 'm5'}),
 ('9702_w23_12_q9', K(3), 3, 'Describe',
  'Only the weight acts at the instant of release, so $a = 9.81\\ \\mathrm{m\\,s^{-2}}$; as the speed rises the air resistance rises, the resultant force $W - F$ falls, and at terminal velocity the forces balance so $a = 0$. Answers A and D keep the acceleration at $9.81\\ \\mathrm{m\\,s^{-2}}$, which would mean the air resistance never mattered.',
  {'A': 'm3', 'D': 'm3', 'C': 'm3'}),
 ('9702_w19_13_q8', K(3), 2, 'Identify',
  'With no resultant force there is no acceleration, so by Newton’s first law the snowflake keeps falling at a constant velocity. Balanced forces do not mean the body is stationary, nor that it slows down.',
  {'A': 'm3', 'B': 'm2'}),
 ('9702_s21_13_q11', K(3), 4, 'Identify',
  'The upthrust and the viscous drag both act upwards and the weight acts downwards, and at constant speed upthrust $+$ drag $=$ weight, so the weight is the largest. In air the upthrust is tiny, so it is the smallest: upthrust $\\to$ drag $\\to$ weight.',
  {'C': 'm3', 'D': 'm3'}),
 ('9702_w22_13_q9', K(3), 4, 'Identify',
  'At terminal velocity the forces balance, so $X = Y + Z$. The upthrust $X$ is the weight of the water displaced, which far exceeds the weight of the air in the bubble, so the larger downward force $Z$ must be the viscous force and $Y$ the weight.',
  {'B': 'm3'}),
 ('9702_w19_13_q10', K(3), 5, 'Describe',
  'The water has uniform density, so the upthrust on the fully immersed sphere stays constant. As the sphere speeds up the viscous drag $D$ grows, so the resultant force $U - (W + D)$ decreases. Many candidates chose an increasing resultant force, forgetting that drag grows with speed.',
  {'A': 'm1', 'C': 'm1', 'D': 'm1'}),
 ('9702_s23_13_q9', K(3), 5, 'Identify',
  'Both balls are at terminal velocity. For each, $D + U = W$ where $W$ is the weight, and $U$ is the same because the balls displace equal volumes, so the heavier ball needs the larger drag $D$ and must therefore fall faster. C assumes terminal velocity is independent of mass.',
  {'C': 'm5', 'A': 'm3', 'B': 'm2'}),
 ('9702_s21_12_q15', K(3), 4, 'Identify',
  'At constant velocity the kinetic energy of the stone is constant, so the gravitational potential energy it loses ends up as thermal energy of the stone and the air. B was common: it would require the stone to be speeding up.',
  {'B': 'm4', 'C': 'm4'}),
]

items = []
for qid, kc, diff, word, explanation, distractors in past_info:
    q = {**BANK[qid], **FIX.get(qid, {})}
    items.append(dict(id=f'9702-3.2-p{len(items) + 1:02}', kcs=[kc], kind='mcq', difficulty=diff,
                      command_word=word, source={'type': 'past', 'ref': q['ref'], 'qid': qid},
                      stem=q['stem'], options=q['options'], answer=q['answer'], image=q.get('image'),
                      marks=1, explanation=explanation, distractors=distractors))


def gen(kind, kcs, stem, difficulty, command_word, explanation, hints, **more):
    n = 1 + sum(i['source']['type'] == 'generated' for i in items)
    items.append(dict(id=f'9702-3.2-i{n:02}', kcs=kcs, kind=kind, difficulty=difficulty,
                      command_word=command_word, source={'type': 'generated'}, stem=stem,
                      marks=more.pop('marks', 1), explanation=explanation, hints=hints, **more))


def num(value, unit, sf=(2, 3)):
    return {'value': round(value, 10), 'unit': unit, 'sf_ok': list(sf)}


def template(kc, stem, params, derived, answer_expr, unit, wrong, explanation, hints, difficulty=3, word='Calculate'):
    env = {name: (spec['choices'][0] if 'choices' in spec else spec['min']) for name, spec in params.items()}
    for name, expr in derived.items():
        env[name] = eval(expr, {'__builtins__': {}}, env)
    a = eval(answer_expr, {'__builtins__': {}}, env)
    ranges = [spec['choices'] if 'choices' in spec else
              [spec['min'] + i * spec['step'] for i in range(round((spec['max'] - spec['min']) / spec['step']) + 1)]
              for spec in params.values()]
    for values in product(*ranges):  # every instantiation must keep answer and distractors apart
        trial = dict(zip(params, values))
        for name, expr in derived.items():
            trial[name] = eval(expr, {'__builtins__': {}}, trial)
        right = eval(answer_expr, {'__builtins__': {}}, trial)
        assert right > 0, (kc, trial, right)
        for expr, _ in wrong:
            bad = eval(expr, {'__builtins__': {}}, trial)
            assert abs(bad - right) > 0.02 * right, (kc, trial, right, bad)
    ds = [{'value': eval(expr, {'__builtins__': {}}, env), 'misconception': mid} for expr, mid in wrong]
    gen('numeric', [kc], stem, difficulty, word, explanation, hints, answer=num(a, unit), distractors=ds,
        template={'params': params, 'derived': derived, 'answer': answer_expr,
                  'distractors': [{'expr': expr, 'misconception': mid} for expr, mid in wrong], 'constraints': []})


# --- KC 1: friction and drag, qualitatively ------------------------------------------------
gen('short', [K(1)], 'State what is meant by a frictional force and by a viscous (drag) force.', 2, 'State',
    'Both oppose relative motion; friction acts where two surfaces are in contact, while a viscous or drag force acts on a body moving through a fluid and grows with speed.',
    ['Both forces oppose something.',
     'Say what each force opposes and where it acts.',
     'Begin with the direction of each force relative to the motion.'],
    marks=2,
    rubric=[{'point': 'Friction opposes (relative) motion of two surfaces in contact.',
             'keywords': [['opposes', 'opposing', 'against', 'resists'], ['surfaces', 'contact', 'sliding']]},
            {'point': 'A viscous or drag force opposes the motion of a body through a fluid (liquid or gas).',
             'keywords': [['opposes', 'opposing', 'against', 'resists'], ['fluid', 'air', 'liquid', 'gas']]}])
gen('mcq', [K(1)],
    'A cyclist freewheels along a level road. Which statement about the air resistance acting on her is correct?',
    3, 'Identify',
    'Air resistance acts backwards along the direction of motion and increases as her speed increases, so it falls to zero only when she is at rest.',
    ['Think about what the air resistance does as she goes faster.',
     'Decide both the direction of the force and how its size depends on speed.',
     'A drag force must be zero when there is no relative motion through the air.'],
    options={'A': 'It acts backwards and has the same magnitude at every speed.',
             'B': 'It acts backwards and increases in magnitude as her speed increases.',
             'C': 'It acts forwards and increases in magnitude as her speed increases.',
             'D': 'It acts backwards and decreases in magnitude as her speed increases.'},
    answer='B', distractors={'A': 'm1', 'D': 'm1'}, shuffle=True)
gen('mcq', [K(1)],
    'A wooden block is given a push and then slides across a rough horizontal bench, slowing down. Which row describes the frictional force on the block and the resultant force on it?',
    3, 'Identify',
    'Friction acts backwards, opposite to the sliding motion, and it is the only horizontal force once the push has ended, so the resultant force is also backwards and the block decelerates.',
    ['The push has already finished.',
     'List the horizontal forces on the block while it is sliding.',
     'Decide the direction of friction from the direction the block slides.'],
    options={'A': 'friction backwards; resultant force backwards',
             'B': 'friction backwards; resultant force zero',
             'C': 'friction forwards; resultant force forwards',
             'D': 'friction backwards; resultant force forwards'},
    answer='A', distractors={'B': 'm3', 'D': 'm3'}, shuffle=True)
template(K(1),
         'A car of mass [[m]] kg travels along a straight level road. The forward driving force on it is [[F]] N and the total resistive force on it is [[R]] N. Calculate the magnitude of its acceleration.',
         {'m': {'choices': [800, 1000, 1200]}, 'F': {'choices': [2400, 3000, 3600]},
          'R': {'choices': [400, 600, 900]}},
         {}, '(F - R)/m', 'm s^-2', [('F/m', 'm3')],
         'The resultant force is the driving force minus the resistive force, and $a = F_\\mathrm{res}/m$.',
         ['Resistive forces act backwards.',
          'Find the resultant horizontal force first, then apply Newton’s second law.',
          'Subtract the resistive force from the driving force before dividing by the mass.'],
         difficulty=3)

# --- KC 2: falling with air resistance ------------------------------------------------------
gen('mcq', [K(2)],
    'A ball is thrown vertically upwards in air. Air resistance is significant. Which statement about the ball on the way up is correct?',
    4, 'Identify',
    'On the way up the weight and the air resistance both act downwards, so the deceleration is greater than $9.81\\ \\mathrm{m\\,s^{-2}}$ and it decreases as the ball slows and the air resistance falls.',
    ['Air resistance opposes the motion, and on the way up the motion is upwards.',
     'Draw the two forces on the rising ball and add them.',
     'Decide whether the two forces act in the same direction or in opposite directions.'],
    options={'A': 'Its deceleration is greater than $9.81\\ \\mathrm{m\\,s^{-2}}$ and decreases as it rises.',
             'B': 'Its deceleration is exactly $9.81\\ \\mathrm{m\\,s^{-2}}$ throughout.',
             'C': 'Its deceleration is less than $9.81\\ \\mathrm{m\\,s^{-2}}$ and increases as it rises.',
             'D': 'Its acceleration is directed upwards and decreases as it rises.'},
    answer='A', distractors={'B': 'm3', 'C': 'm1', 'D': 'm2'}, shuffle=True)
gen('structured', [K(2)],
    'A sphere is released from rest and falls vertically through air. (a) Explain why the acceleration of the sphere decreases as it falls. (b) Explain why the sphere eventually falls at a constant velocity.',
    4, 'Explain', '', [], marks=4,
    scheme=[{'mark': 'B1', 'point': 'As the sphere falls its speed increases, so the air resistance acting upwards on it increases.'},
            {'mark': 'B1', 'point': 'The resultant force (weight $-$ air resistance) therefore decreases, so the acceleration decreases (the sphere still speeds up).'},
            {'mark': 'B1', 'point': 'Eventually the air resistance becomes equal in magnitude to the weight, so the resultant force is zero.'},
            {'mark': 'B1', 'point': 'With zero resultant force the acceleration is zero, so the sphere falls at a constant (terminal) velocity.'}])

# --- KC 3: terminal velocity ----------------------------------------------------------------
gen('mcq', [K(3)],
    'A raindrop falls through still air at its terminal velocity. Which statement about the raindrop is correct?',
    3, 'Identify',
    'At terminal velocity the resultant force is zero, so the air resistance equals the weight in magnitude and the acceleration is zero while the drop keeps moving downwards.',
    ['Constant velocity tells you something about the resultant force.',
     'Apply Newton’s first law to the drop, then read off each quantity.',
     'Start by writing down the value of the resultant force.'],
    options={'A': 'The air resistance on it equals its weight in magnitude and its acceleration is zero.',
             'B': 'Its weight is greater than the air resistance on it and its acceleration is $9.81\\ \\mathrm{m\\,s^{-2}}$.',
             'C': 'The air resistance on it is greater than its weight and it is decelerating.',
             'D': 'The air resistance on it equals its weight in magnitude and it is momentarily at rest.'},
    answer='A', distractors={'B': 'm3', 'C': 'm2', 'D': 'm3'}, shuffle=True)
template(K(3),
         'A small metal sphere of weight [[W]] N falls at a constant (terminal) velocity through oil. The upthrust acting on the sphere is [[U]] N. Determine the viscous (drag) force acting on the sphere.',
         {'W': {'choices': [0.40, 0.50, 0.60]}, 'U': {'choices': [0.05, 0.10, 0.15]}},
         {}, 'W - U', 'N', [('W', 'm3'), ('W + U', 'm3')],
         'At terminal velocity the resultant force is zero, so upthrust $+$ drag $=$ weight, giving drag $= W - U$.',
         ['Constant velocity means zero resultant force.',
          'Write the balance of the three vertical forces on the sphere.',
          'Both the upthrust and the drag force act upwards, against the weight.'],
         difficulty=4, word='Determine')

# --- worked examples ------------------------------------------------------------------------
m_sky, F_sky = 75.0, 420.0
W_sky = m_sky * G
a_sky = (W_sky - F_sky) / m_sky
W_ball, U_ball = 0.48, 0.12
D_ball = W_ball - U_ball
worked = [
 {'id': 'we1', 'kc': K(2),
  'problem': f'A skydiver of mass {m_sky:.0f} kg falls vertically through air. At one instant the air resistance acting on her is {F_sky:.0f} N. Calculate her acceleration at that instant, and state what happens to this acceleration as she continues to fall.',
  'steps': [
   {'do': f'Find the weight: $W = mg = {m_sky:.0f} \\times {G} = {W_sky:.1f}$ N.',
    'why': 'The weight is the only downward force; it is needed before the forces can be combined.'},
   {'do': f'Take downwards as positive: resultant force $= W - F = {W_sky:.1f} - {F_sky:.0f} = {W_sky - F_sky:.1f}$ N, downwards.',
    'why': 'Air resistance opposes the motion, so it acts upwards and is subtracted — not added — from the weight.'},
   {'do': f'Apply Newton’s second law: $a = F_\\mathrm{{res}}/m = {W_sky - F_sky:.1f}/{m_sky:.0f} = {a_sky:.2f}\\ \\mathrm{{m\\,s^{{-2}}}}$, downwards.',
    'why': 'The acceleration follows the resultant force, so it is less than $9.81\\ \\mathrm{m\\,s^{-2}}$ but still downwards.',
    'check': {'kind': 'numeric', 'answer': num(a_sky, 'm s^-2')}},
   {'do': 'As she speeds up, the air resistance increases, so the resultant force and hence the acceleration decrease towards zero.',
    'why': 'A decreasing acceleration is not a deceleration: she keeps speeding up until the forces balance at terminal velocity.'}],
  'faded': {'id': 'we1f',
            'problem': 'A parachutist of mass 60 kg falls vertically through air. At one instant the air resistance acting on her is 240 N. Calculate her acceleration at that instant.',
            'answer': num((60 * G - 240) / 60, 'm s^-2'), 'blank_from': 1}},
 {'id': 'we2', 'kc': K(3),
  'problem': f'A ball of weight {W_ball:.2f} N falls at a constant (terminal) velocity through a liquid. The upthrust on the ball is {U_ball:.2f} N. Determine the viscous force on the ball.',
  'steps': [
   {'do': 'The velocity is constant, so by Newton’s first law the resultant force on the ball is zero.',
    'why': 'Constant velocity, not constant speed alone, is the clue that the forces balance.'},
   {'do': 'Balance the vertical forces: upthrust $U$ + viscous force $D$ = weight $W$.',
    'why': 'Both the upthrust and the viscous force act upwards on the falling ball; omitting the upthrust is the common error in a liquid.'},
   {'do': f'$D = W - U = {W_ball:.2f} - {U_ball:.2f} = {D_ball:.2f}$ N, upwards.',
    'why': 'The answer must carry a unit and a direction, as the mark scheme requires for a force.',
    'check': {'kind': 'numeric', 'answer': num(D_ball, 'N')}}],
  'faded': {'id': 'we2f',
            'problem': 'A bead of weight 0.75 N sinks at a constant velocity through glycerine. The upthrust on it is 0.20 N. Determine the viscous force on the bead.',
            'answer': num(0.75 - 0.20, 'N'), 'blank_from': 1}},
]

flashcards = [
 {'id': 'fc1', 'kc': K(1), 'front': 'What is a frictional force?',
  'back': 'A force that opposes the relative motion (or tendency to move) of two surfaces in contact.'},
 {'id': 'fc2', 'kc': K(1), 'front': 'What is a viscous (drag) force?',
  'back': 'A resistive force on a body moving through a fluid; it opposes the motion and increases as the speed of the body increases. Air resistance is the drag force due to air.'},
 {'id': 'fc3', 'kc': K(3), 'front': 'What is terminal velocity?',
  'back': 'The constant velocity reached by a body moving through a fluid when the resistive force (plus upthrust) becomes equal in magnitude to the weight, so the resultant force and the acceleration are zero.'},
 {'id': 'fc4', 'kc': K(3), 'front': 'At terminal velocity, where does the lost gravitational potential energy go?',
  'back': 'The kinetic energy of the body is constant, so the gravitational potential energy lost becomes thermal energy (and kinetic energy) of the body and the surrounding fluid.'},
 {'id': 'fc5', 'kc': K(2), 'front': 'How does the acceleration of an object dropped from rest in air change as it falls?',
  'back': 'It starts at $9.81\\ \\mathrm{m\\,s^{-2}}$ (weight only), then decreases as the air resistance increases with speed, reaching zero at terminal velocity.'},
]

diagrams = [
 {'file': 'Assets/9702/9702-3.2-vt-fall.svg', 'type': 'graph_sketch',
  'params': {'lines': [{'points': [[0, 0], [0.5, 4.6], [1.0, 7.6], [1.5, 9.2], [2.0, 10.0],
                                   [2.5, 10.4], [3.0, 10.5], [3.5, 10.5]],
                        'label': 'falling in air', 'style': 'solid'},
                       {'points': [[0, 0], [3.5, 34.3]], 'label': 'free fall (no air resistance)', 'style': 'dashed'}],
             'xlabel': 'time t', 'ylabel': 'velocity v',
             'annotations': [{'xy': [3.0, 10.5], 'text': 'terminal velocity', 'xytext': [1.6, 16.0]}],
             'ticks': False}},
 {'file': 'Assets/9702/9702-3.2-terminal-forces.svg', 'type': 'free_body',
  'params': {'body': 'dot',
             'forces': [{'label': 'weight W', 'angle': -90, 'length': 1.0},
                        {'label': 'air resistance D', 'angle': 90, 'length': 1.0}]}},
]

outline = ('Friction opposes the relative motion of surfaces in contact; a viscous or drag force opposes the motion '
           'of a body through a fluid and grows from zero as the speed grows (air resistance is the drag due to air). '
           'For a body dropped from rest, only the weight acts at first, so $a = g = 9.81\\ \\mathrm{m\\,s^{-2}}$. '
           'As $v$ rises the drag $D$ rises, so the resultant force $W - D$ and the acceleration fall: the body speeds '
           'up less and less, but never slows down. When $D = W$ the resultant force is zero and the body falls at a '
           'constant terminal velocity, with zero acceleration. In a liquid the upthrust $U$ also acts upwards, so '
           'terminal velocity needs $D + U = W$. A larger mass with the same shape needs a larger drag, so it has a '
           'larger terminal velocity. At terminal velocity the kinetic energy is constant, so the lost gravitational '
           'potential energy becomes thermal energy of the body and the fluid.')

pack = {'subtopic': '9702-3.2', 'spec': '9702', 'version': 1,
        'note': 'Subjects/9702 Physics/03 Dynamics/3.2 Non-uniform motion.md',
        'outline': outline, 'misconceptions': mis, 'worked': worked, 'items': items,
        'flashcards': flashcards, 'diagrams': diagrams}
OUT.parent.mkdir(parents=True, exist_ok=True)
OUT.write_text(json.dumps(pack, ensure_ascii=False, indent=1) + '\n')
print(OUT, 'items', len(items), 'worked', len(worked), 'a_sky', round(a_sky, 3), 'D', D_ball)
