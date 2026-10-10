"""Build the 9702-3.3 teaching pack. All computed values originate here."""
from __future__ import annotations
import json
from itertools import product
from math import sqrt, sin, cos, atan2, degrees, radians
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
OUT = ROOT / 'build/out/packs/9702/9702-3.3.json'
BANK = {q['id']: q for q in json.loads((ROOT / 'build/work/mcq/9702.tagged.json').read_text())}
FIX = {q: {k: v for k, v in f.items() if k in ('stem', 'options')} for q, f in json.loads((ROOT / 'build/work/mcq/overrides.json').read_text()).items()}
K = lambda n: f'9702-3.3.{n}'

mis = [
 dict(id='m1', kc=K(4),
      statement='Total kinetic energy is conserved in every collision in which momentum is conserved.',
      refutation='Momentum is conserved whenever no resultant external force acts, but kinetic energy is only conserved when the collision is perfectly elastic; otherwise some is transferred to internal energy, sound and deformation.',
      contrast='Momentum: always conserved in an isolated system. Kinetic energy: conserved only in an elastic collision.',
      source='ER 9702 w24 P12 Q7'),
 dict(id='m2', kc=K(3),
      statement='For an elastic collision the relative speed of separation is the speed of the struck object alone.',
      refutation='The rule compares the two objects with each other: the speed of separation is the difference between the final velocities, so the velocity of the still-moving first object must be subtracted.',
      contrast='Approach $u_1-u_2$ equals separation $v_2-v_1$, not $v_2$ by itself.',
      source='ER 9702 w22 P12 Q11'),
 dict(id='m3', kc=K(1),
      statement='The principle of conservation of momentum says that momentum is always constant, with no stated condition.',
      refutation='The principle holds only for a system on which no resultant external force acts, that is, an isolated or closed system.',
      contrast='"The total momentum of an isolated system is constant" earns the mark; "momentum is always conserved" does not.',
      source='ER 9702 s23 P23 Q3'),
 dict(id='m4', kc=K(2),
      statement='Momentum terms are counted as magnitudes: approach or rebound velocities are added without a sign, or only the target mass is used for a combined object after impact.',
      refutation='Momentum is a vector, so one direction must be chosen positive and velocities in the opposite direction entered as negative; after a sticking collision the moving mass is the sum of both masses.',
      contrast='Head-on: $m_1u_1-m_2u_2=(m_1+m_2)v$, not $m_1u_1+m_2u_2=m_2v$.',
      source='ER 9702 s23 P11 Q10'),
 dict(id='m5', kc=K(2),
      statement='In two dimensions the velocity components are equated instead of the momentum components.',
      refutation='Each conservation equation is a sum of momenta, so every velocity component must be multiplied by its own mass before the components are added.',
      contrast='Perpendicular to the original line: $m_1v_1\\sin\\theta_1=m_2v_2\\sin\\theta_2$, not $v_1\\sin\\theta_1=v_2\\sin\\theta_2$.',
      source='ER 9702 w23 P22 Q4'),
]

# (bank id, kcs, difficulty, command word, explanation incl. why the popular wrong option is wrong, distractor map)
past_info = [
 ('9702_w25_12_q9', [K(1)], 1, 'Identify',
  'The principle is that the total momentum of an isolated system is constant, so D is the statement. A restricts the principle to elastic collisions, but momentum is conserved in inelastic collisions too; B defines momentum and C is Newton’s second law.', {'A': 'm1', 'B': 'm3', 'C': 'm3'}),
 ('9702_w25_13_q9', [K(1)], 2, 'Identify',
  'Momentum is conserved when no resultant external force acts, which is what "isolated system" means, so C is correct. A is wrong because an external force such as friction or a wall can change the total momentum of two colliding objects; equal masses or equal and opposite velocities are irrelevant conditions.', {'A': 'm3', 'B': 'm3', 'D': 'm3'}),
 ('9702_w23_11_q10', [K(1), K(4)], 3, 'Identify',
  'The objects are at rest afterwards, so the total momentum after the collision is zero; because the system is isolated the total momentum before must also have been zero, giving B. A is wrong because the kinetic energy has fallen to zero in this completely inelastic collision, and equal momenta do not require equal masses or equal speeds.', {'A': 'm1', 'C': 'm4', 'D': 'm4'}),
 ('9702_w24_12_q7', [K(1), K(4)], 2, 'Identify',
  'The system is isolated, so the total momentum is unchanged at 6 kg m s$^{-1}$, while an inelastic collision in which the objects move off together must lose kinetic energy: 90 J falls to 30 J, which is C. D keeps the kinetic energy constant as well and so describes an elastic collision, which cannot happen when the objects coalesce.', {'A': 'm3', 'B': 'm1', 'D': 'm1'}),
 ('9702_w24_13_q11', [K(4)], 1, 'Identify',
  'With no external forces the total momentum is conserved, but an inelastic collision by definition does not conserve total kinetic energy, so B is correct. A is the common error of assuming that the two conservation statements always go together.', {'A': 'm1', 'C': 'm3', 'D': 'm3'}),
 ('9702_w23_12_q10', [K(2), K(4)], 5, 'Calculate',
  'The total momentum before is $m(2v)-2m(v)=0$, so it is zero afterwards: with $m$ moving left at $v$ the mass $2m$ must move right at $v/2$. The kinetic energy falls from $\\tfrac12m(2v)^2+\\tfrac12(2m)v^2=3mv^2$ to $\\tfrac12mv^2+\\tfrac12(2m)(v/2)^2=0.75mv^2$, a loss of $\\tfrac94mv^2$ (C). B, the most popular wrong answer, comes from mis-handling the signs of the opposing velocities so that the total initial momentum is not zero.', {'B': 'm4', 'A': 'm4', 'D': 'm1'}),
 ('9702_w22_13_q10', [K(2)], 5, 'Predict',
  'Both situations start with the same total momentum, and momentum is conserved, so each ends with it. The rebounding ball carries momentum back to the left, so the steel block must carry more forward momentum than the wooden block with the ball embedded in it; equal block masses then make the steel block faster, which is B. C reverses the argument, and D is wrong because the comparison follows from momentum conservation alone and needs no numerical masses.', {'C': 'm4', 'D': 'm4', 'A': 'm4'}),
 ('9702_w24_12_q10', [K(2), K(4)], 4, 'Calculate',
  'Taking right as positive, $5000(2.00)-5000(1.00)=10000v$ gives $v=0.50$ m s$^{-1}$; the kinetic energy falls from $12\\,500$ J to $\\tfrac12(10000)(0.50)^2=1250$ J, a loss of $11\\,250$ J (C). D is the total initial kinetic energy, chosen by candidates who assume all of it is lost when the carriages join.', {'D': 'm1', 'A': 'm1', 'B': 'm4'}),
 ('9702_w24_11_q12', [K(2)], 5, 'Determine',
  'Perpendicular to the original direction, $M(4.0)\\sin45^\\circ=4Mv\\sin45^\\circ$, so the large disc moves at $1.0$ m s$^{-1}$. Along the original direction, $Mu=M(4.0)\\cos45^\\circ+4M(1.0)\\cos45^\\circ$, giving $u=5.7$ m s$^{-1}$ (D). B comes from equating velocity components instead of momentum components, which leaves out the masses.', {'B': 'm5', 'A': 'm5', 'C': 'm4'}),
 ('9702_w20_12_q11', [K(2)], 4, 'Determine',
  'For the first impact momentum conservation gives $Mv=mu$, so $v=(m/M)u$. Doubling every mass and the pellet speed gives $2Mv_2=2m(2u)$, hence $v_2=2(m/M)u=2v$ (C). A is the common error of assuming that scaling all the masses and the speed leaves the final speed unchanged, which ignores the extra factor of 2 carried by the speed.', {'A': 'm4', 'B': 'm4', 'D': 'm1'}),
 ('9702_w22_12_q11', [K(3)], 4, 'Determine',
  'The collision is elastic, so the relative speed of separation equals the relative speed of approach, $6$ cm s$^{-1}$. Sphere X still moves forwards at $2$ cm s$^{-1}$, so Y must move at $2+6=8$ cm s$^{-1}$ (D). B is the popular error of setting the speed of Y itself equal to the approach speed minus the speed of X, instead of comparing the two final velocities.', {'B': 'm2', 'C': 'm2', 'A': 'm2'}),
 ('9702_w19_13_q9', [K(3)], 4, 'Determine',
  'X approaches Y with a relative speed of $20-12=8$ m s$^{-1}$, and in a perfectly elastic collision the relative speed of separation is also $8$ m s$^{-1}$; with X at $10$ m s$^{-1}$ afterwards, Y moves at $10+8=18$ m s$^{-1}$ (B). C, the usual wrong choice, adds the approach speed to the initial speed of Y instead of to the final speed of X.', {'C': 'm2', 'A': 'm2', 'D': 'm2'}),
]

items = []
for qid, kcs, diff, cw, explanation, distractors in past_info:
 q = {**BANK[qid], **FIX.get(qid, {})}
 it = dict(id='9702-3.3-p' + str(len(items) + 1).zfill(2), kcs=kcs, kind='mcq', difficulty=diff,
           command_word=cw, source={'type': 'past', 'ref': q['ref'], 'qid': qid}, stem=q['stem'],
           options=q['options'], answer=q['answer'], marks=1, explanation=explanation,
           distractors={k: v for k, v in distractors.items() if k != q['answer']})
 if q.get('image'):
  it['image'] = q['image']
 items.append(it)


def gen(kind, kcs, stem, difficulty, command_word, explanation, hints, **more):
 n = 1 + sum(i['source']['type'] == 'generated' for i in items)
 items.append(dict(id=f'9702-3.3-i{n:02}', kcs=kcs, kind=kind, difficulty=difficulty,
                   command_word=command_word, source={'type': 'generated'}, stem=stem,
                   marks=more.pop('marks', 1), explanation=explanation, hints=hints, **more))


def num(value, unit, sf=(2, 3)):
 return {'value': round(value, 10), 'unit': unit, 'sf_ok': list(sf)}


# ---------------------------------------------------------------- KC1: the principle
gen('short', [K(1)], 'State the principle of conservation of momentum.', 1, 'State',
    'Cambridge credits the total momentum of a system remaining constant together with the condition that no resultant external force acts (an isolated or closed system).',
    ['Two ideas are needed: what stays the same, and when.',
     'Name the quantity that is constant and the property the system must have.',
     'Begin with "the total momentum of a system…".'],
    marks=2,
    rubric=[{'point': 'The total momentum of the system is constant (unchanged before and after).',
             'keywords': [['total', 'sum'], ['momentum'], ['constant', 'conserved', 'unchanged', 'the same']]},
            {'point': 'Provided no resultant external force acts on the system (isolated/closed system).',
             'keywords': [['no', 'zero', 'without', 'isolated', 'closed'], ['external force', 'resultant force', 'isolated', 'closed']]}])

gen('mcq', [K(1)], 'Two skaters push each other apart on frictionless ice. Which statement about the momentum of the two-skater system is correct?', 3, 'Identify',
    'No resultant external force acts along the ice, so the total momentum of the system stays at its initial value of zero; the skaters therefore gain equal and opposite momenta.',
    ['The skaters started at rest.',
     'Apply the principle to the two skaters taken together as one system.',
     'Work out the total momentum before the push.'],
    options={'A': 'The total momentum stays zero, so the skaters gain equal and opposite momenta.',
             'B': 'The total momentum increases, because each skater gains momentum.',
             'C': 'Momentum is conserved only if the skaters have equal mass.',
             'D': 'The total momentum is conserved only if their kinetic energies are also equal.'},
    answer='A', distractors={'B': 'm4', 'C': 'm3', 'D': 'm1'}, shuffle=True)

gen('structured', [K(1), K(2)], 'A stationary object of mass 3.0 kg explodes into two fragments, of mass 1.0 kg and 2.0 kg, which move apart along the same straight line. The 1.0 kg fragment moves away at 6.0 m s$^{-1}$. Determine the speed of the 2.0 kg fragment and explain how the principle of conservation of momentum applies.', 4, 'Determine',
    'The total momentum stays zero, so the fragments carry equal and opposite momenta: $2.0v=1.0\\times6.0$ gives $v=3.0$ m s$^{-1}$ in the opposite direction.',
    ['The object was at rest before the explosion.',
     'Write the total momentum before the explosion and set the total afterwards equal to it.',
     'State that the total momentum before is zero.'],
    marks=4,
    scheme=[{'mark': 'B1', 'point': 'Total momentum before the explosion is zero, and no resultant external force acts, so the total momentum afterwards is also zero.'},
            {'mark': 'M1', 'point': 'Momenta are equal and opposite: $2.0v=1.0\\times6.0$.'},
            {'mark': 'A1', 'point': 'Speed $v=3.0$ m s$^{-1}$.',
             'check': {'kind': 'numeric', 'answer': num(1.0 * 6.0 / 2.0, 'm s^-1')}},
            {'mark': 'B1', 'point': 'The 2.0 kg fragment moves in the opposite direction to the 1.0 kg fragment.'}])

# ---------------------------------------------------------------- templates


def template(kcs, stem, params, derived, answer_expr, unit, wrong, explanation, hints,
             difficulty=3, command_word='Calculate', constraints=()):
 def ev(expr, env):
  return eval(expr, {'__builtins__': {}, 'sqrt': sqrt, 'abs': abs}, env)

 def base(spec):
  return spec['choices'] if 'choices' in spec else [round(spec['min'] + i * spec['step'], 10)
                                                    for i in range(round((spec['max'] - spec['min']) / spec['step']) + 1)]
 nominal = None
 ranges = [base(s) for s in params.values()]
 for values in product(*ranges):
  trial = dict(zip(params, values))
  for name, expr in derived.items():
   trial[name] = ev(expr, trial)
  if not all(ev(c, trial) for c in constraints):
   continue
  right = ev(answer_expr, trial)
  assert right > 0, (trial, right)
  for expr, _ in wrong:
   bad = ev(expr, trial)
   assert abs(bad - right) > 0.02 * right, (trial, right, expr, bad)
  if nominal is None:
   nominal = trial
 assert nominal is not None
 a = ev(answer_expr, nominal)
 ds = [{'value': round(ev(expr, nominal), 10), 'misconception': mid} for expr, mid in wrong]
 gen('numeric', kcs, stem, difficulty, command_word, explanation, hints,
     answer=num(a, unit), distractors=ds,
     template={'params': params, 'derived': derived, 'answer': answer_expr,
               'distractors': [{'expr': expr, 'misconception': mid} for expr, mid in wrong],
               'constraints': list(constraints)})


template([K(2)],
         'A trolley of mass [[m1]] kg moving at [[u1]] m s$^{-1}$ along a frictionless horizontal track collides with a stationary trolley of mass [[m2]] kg. The trolleys stick together. Calculate their common speed immediately after the collision.',
         {'m1': {'choices': [0.5, 1.0, 1.5, 2.0]}, 'u1': {'choices': [2.0, 3.0, 4.0, 5.0]}, 'm2': {'choices': [1.0, 2.5, 3.0, 4.0]}},
         {}, 'm1*u1/(m1+m2)', 'm s^-1',
         [('m1*u1/m2', 'm4'), ('u1*sqrt(m1/(m1+m2))', 'm1')],
         'Momentum is conserved: $m_1u_1=(m_1+m_2)v$, so $v=m_1u_1/(m_1+m_2)$. The mass that moves afterwards is the sum of both masses.',
         ['Nothing leaves the system, so write down the momentum before and after.',
          'Set the momentum of the moving trolley equal to the momentum of the joined pair.',
          'The combined object has mass $m_1+m_2$.'],
         difficulty=3, constraints=['m2 != m1'])

template([K(2), K(4)],
         'A ball of mass [[m1]] kg moving east at [[u1]] m s$^{-1}$ collides head-on with a ball of mass [[m2]] kg moving west at [[u2]] m s$^{-1}$ on a frictionless surface. The balls stick together. Calculate the speed of the combined ball immediately after the collision.',
         {'m1': {'choices': [2.0, 3.0, 4.0]}, 'u1': {'choices': [4.0, 5.0, 6.0]}, 'm2': {'choices': [1.0, 1.5, 2.0]}, 'u2': {'choices': [1.0, 2.0, 3.0]}},
         {}, '(m1*u1-m2*u2)/(m1+m2)', 'm s^-1',
         [('(m1*u1+m2*u2)/(m1+m2)', 'm4'), ('sqrt((m1*u1**2+m2*u2**2)/(m1+m2))', 'm1')],
         'Taking east as positive, $m_1u_1-m_2u_2=(m_1+m_2)v$: the westward momentum is negative because momentum is a vector.',
         ['Momentum is a vector, so one direction must be chosen as positive.',
          'Write the conservation equation with the westward velocity entered as negative.',
          'The total momentum before is $m_1u_1-m_2u_2$.'],
         difficulty=4, constraints=['m1*u1 - m2*u2 > 0.5'])

template([K(3)],
         'Object X, travelling at [[u1]] m s$^{-1}$, catches up with object Y, which is moving at [[u2]] m s$^{-1}$ in the same direction along the same straight line. The two objects have a perfectly elastic collision, and immediately afterwards X is still moving forwards at [[v1]] m s$^{-1}$. Determine the speed of Y immediately after the collision.',
         {'u1': {'choices': [10.0, 12.0, 14.0]}, 'u2': {'choices': [2.0, 3.0, 4.0]}, 'v1': {'choices': [5.0, 6.0]}},
         {}, 'v1+(u1-u2)', 'm s^-1',
         [('u1-u2', 'm2'), ('u1', 'm2')],
         'For an elastic collision the relative speed of separation equals the relative speed of approach: $v_2-v_1=u_1-u_2$, so $v_2=v_1+(u_1-u_2)$.',
         ['An elastic collision gives a second equation as useful as momentum conservation.',
          'Compare the two objects with each other before and after, not with the ground.',
          'Find the relative speed of approach, $u_1-u_2$.'],
         difficulty=3, command_word='Determine', constraints=['u1-u2 > 5.0', 'v1 < u1', 'v1 != u2'])

template([K(4)],
         'A railway truck of mass [[m1]] kg moving at [[u1]] m s$^{-1}$ collides with a stationary truck of mass [[m2]] kg on a level track. The trucks couple together. Calculate the loss of kinetic energy in the collision.',
         {'m1': {'choices': [1000.0, 2000.0, 3000.0]}, 'u1': {'choices': [2.0, 3.0, 4.0]}, 'm2': {'choices': [1000.0, 4000.0, 5000.0]}},
         {'v': 'm1*u1/(m1+m2)'}, '0.5*m1*u1**2 - 0.5*(m1+m2)*v**2', 'J',
         [('0.5*m1*u1**2', 'm1'), ('0.5*(m1+m2)*v**2', 'm1')],
         'Find the common speed from momentum conservation, then subtract the final kinetic energy from the initial kinetic energy; momentum is conserved but kinetic energy is not.',
         ['Momentum conservation comes first, then the energy sum.',
          'Calculate the common speed after coupling, then compare the kinetic energies before and after.',
          'Use $m_1u_1=(m_1+m_2)v$ to get the common speed.'],
         difficulty=4, constraints=['m2 != m1'])

# ---------------------------------------------------------------- KC3: elastic collisions
gen('short', [K(3)], 'State what is meant by a perfectly elastic collision, and give the relationship between the relative speeds of the colliding objects before and after it.', 2, 'State',
    'In a perfectly elastic collision the total kinetic energy of the system is conserved, and the relative speed of approach equals the relative speed of separation.',
    ['One statement is about energy, the other about relative speeds.',
     'Name the quantity that is conserved, then compare the objects with each other.',
     'Start with the total kinetic energy of the system.'],
    marks=2,
    rubric=[{'point': 'Total kinetic energy is conserved (the same before and after).',
             'keywords': [['kinetic energy'], ['conserved', 'constant', 'unchanged', 'the same']]},
            {'point': 'Relative speed of approach equals relative speed of separation.',
             'keywords': [['approach'], ['separation'], ['equal', 'same', '=']]}])

gen('mcq', [K(3)], 'Sphere P, moving at 9.0 m s$^{-1}$, strikes a stationary sphere Q head-on. The collision is perfectly elastic and afterwards P continues forwards at 3.0 m s$^{-1}$. What is the speed of Q after the collision?', 4, 'Determine',
    'The relative speed of approach is 9.0 m s$^{-1}$, so the relative speed of separation is also 9.0 m s$^{-1}$: Q moves at $3.0+9.0=12.0$ m s$^{-1}$.',
    ['Use the elastic-collision rule about relative speeds.',
     'The speed of separation is measured between the two spheres, not from the ground.',
     'Write $v_Q-v_P$ equal to the relative speed of approach.'],
    options={'A': '6.0 m s$^{-1}$', 'B': '9.0 m s$^{-1}$', 'C': '12.0 m s$^{-1}$', 'D': '3.0 m s$^{-1}$'},
    answer='C', distractors={'A': 'm2', 'B': 'm2', 'D': 'm2'}, shuffle=True)

gen('structured', [K(3), K(2)], 'A trolley of mass 2.0 kg moving at 5.0 m s$^{-1}$ has a perfectly elastic head-on collision with a stationary trolley of mass 3.0 kg on a frictionless track. Determine the velocity of each trolley after the collision, and show that the total kinetic energy is unchanged.', 5, 'Determine',
    'Momentum conservation with the elastic relative-speed rule gives $-1.0$ m s$^{-1}$ for the 2.0 kg trolley and $+4.0$ m s$^{-1}$ for the 3.0 kg trolley; the kinetic energy is 25 J before and $1.0+24=25$ J after.',
    ['Two equations are needed for two unknown velocities.',
     'Combine momentum conservation with the relative-speed rule for an elastic collision.',
     'Momentum: $2.0\\times5.0=2.0v_1+3.0v_2$.'],
    marks=5,
    scheme=[{'mark': 'M1', 'point': 'Momentum: $2.0(5.0)=2.0v_1+3.0v_2$.'},
            {'mark': 'M1', 'point': 'Elastic collision: $v_2-v_1=5.0$ (separation equals approach).'},
            {'mark': 'A1', 'point': 'The 2.0 kg trolley rebounds at $1.0$ m s$^{-1}$ (velocity $-1.0$ m s$^{-1}$).',
             'check': {'kind': 'numeric', 'answer': num(1.0, 'm s^-1')}},
            {'mark': 'A1', 'point': 'The 3.0 kg trolley moves forwards at $4.0$ m s$^{-1}$.',
             'check': {'kind': 'numeric', 'answer': num(4.0, 'm s^-1')}},
            {'mark': 'B1', 'point': 'Kinetic energy before $=\\tfrac12(2.0)(5.0)^2=25$ J; after $=\\tfrac12(2.0)(1.0)^2+\\tfrac12(3.0)(4.0)^2=25$ J, so it is conserved.',
             'check': {'kind': 'numeric', 'answer': num(25.0, 'J')}}])

# ---------------------------------------------------------------- KC4: momentum vs kinetic energy
gen('mcq', [K(4)], 'Two lumps of clay collide in an isolated system and stick together. Which row correctly describes the total momentum and the total kinetic energy of the system?', 2, 'Identify',
    'An isolated system always conserves momentum, but a collision in which the objects coalesce is inelastic, so some kinetic energy is transferred to internal energy and sound.',
    ['Decide the two answers separately.',
     'One quantity is conserved because the system is isolated; the other depends on whether the collision is elastic.',
     'Ask whether a collision in which the objects stick together can be elastic.'],
    options={'A': 'momentum conserved, kinetic energy conserved',
             'B': 'momentum conserved, kinetic energy not conserved',
             'C': 'momentum not conserved, kinetic energy conserved',
             'D': 'momentum not conserved, kinetic energy not conserved'},
    answer='B', distractors={'A': 'm1', 'C': 'm3', 'D': 'm3'}, shuffle=True)

gen('short', [K(4)], 'Explain why the total momentum of a system is conserved in a collision in which the total kinetic energy decreases.', 3, 'Explain',
    'The internal forces of the collision are equal and opposite (Newton’s third law) and act for the same time, so the momentum changes cancel while work done in deforming the objects transfers kinetic energy to internal energy.',
    ['Think about the pair of forces the colliding objects exert on each other.',
     'Use Newton’s third law for the momentum, then say where the kinetic energy goes.',
     'The two forces act for the same time, so the impulses are equal and opposite.'],
    marks=3,
    rubric=[{'point': 'The forces between the objects are equal and opposite and act for the same time, so the impulses (changes in momentum) are equal and opposite and cancel.',
             'keywords': [['equal and opposite', 'Newton’s third law', "Newton's third law", 'third law'], ['impulse', 'time', 'change in momentum']]},
            {'point': 'No resultant external force acts on the system, so its total momentum is constant.',
             'keywords': [['no', 'zero', 'isolated', 'closed'], ['external force', 'resultant force', 'isolated', 'closed']]},
            {'point': 'Kinetic energy is transferred to other forms (internal energy/thermal energy/sound/deformation), and energy forms are not restricted in the way momentum is.',
             'keywords': [['internal energy', 'thermal', 'heat', 'sound', 'deformation', 'other forms'], ['kinetic energy', 'transferred', 'lost']]}])

# ---------------------------------------------------------------- KC2: two-dimensional exam-style item
m, u = 0.40, 6.0
v1, th1 = 3.0, 60.0
p0 = m * u
p1x, p1y = m * v1 * cos(radians(th1)), m * v1 * sin(radians(th1))
p2x, p2y = p0 - p1x, -p1y
v2 = sqrt(p2x ** 2 + p2y ** 2) / m
th2 = degrees(atan2(abs(p2y), p2x))
ke_i, ke_f = 0.5 * m * u ** 2, 0.5 * m * v1 ** 2 + 0.5 * m * v2 ** 2

gen('structured', [K(2), K(5 - 3)], 'A puck A of mass 0.40 kg slides at 6.0 m s$^{-1}$ across a frictionless horizontal table and strikes an identical stationary puck B. After the collision A moves at 3.0 m s$^{-1}$ at an angle of 60$^\\circ$ to its original direction. Determine the speed of B after the collision and the angle between its velocity and the original direction of A.', 5, 'Determine',
    f'Resolving momentum along and perpendicular to the original direction gives $p_{{Bx}}={p2x:.2f}$ N s and $p_{{By}}={abs(p2y):.2f}$ N s, so $v_B={v2:.2f}$ m s$^{{-1}}$ at ${th2:.0f}^\\circ$ on the other side of the original direction.',
    ['Momentum is conserved separately in two perpendicular directions.',
     'Resolve the momentum of each puck along and perpendicular to the original direction of A, then combine the components for B.',
     'Perpendicular to the original direction the total momentum before the collision is zero.'],
    marks=5,
    scheme=[{'mark': 'M1', 'point': 'Perpendicular: $0=0.40(3.0)\\sin60^\\circ+0.40v_B\\sin\\theta$, so B has perpendicular momentum $1.04$ N s on the opposite side.',
             'check': {'kind': 'numeric', 'answer': num(abs(p2y), 'N s')}},
            {'mark': 'M1', 'point': 'Along the original direction: $0.40(6.0)=0.40(3.0)\\cos60^\\circ+0.40v_B\\cos\\theta$, so B has forward momentum $1.80$ N s.',
             'check': {'kind': 'numeric', 'answer': num(p2x, 'N s')}},
            {'mark': 'M1', 'point': 'Combine the components: $p_B=\\sqrt{1.80^2+1.04^2}$.'},
            {'mark': 'A1', 'point': f'Speed $v_B={v2:.1f}$ m s$^{{-1}}$.',
             'check': {'kind': 'numeric', 'answer': num(v2, 'm s^-1')}},
            {'mark': 'A1', 'point': f'Angle $\\theta={th2:.0f}^\\circ$ to the original direction of A, on the opposite side to A.'}])  # no numeric check: the unit library has no degree

# ---------------------------------------------------------------- worked examples (KC2 is the procedural KC)
mA, uA, mB = 0.80, 3.0, 1.20
vAB = mA * uA / (mA + mB)
loss = 0.5 * mA * uA ** 2 - 0.5 * (mA + mB) * vAB ** 2
fade_v = 0.50 * 4.0 / (0.50 + 1.50)

worked = [
 {'id': 'we1', 'kc': K(2),
  'problem': 'A trolley of mass 0.80 kg moving at 3.0 m s$^{-1}$ collides with a stationary trolley of mass 1.20 kg on a frictionless track and the two move off together. Calculate their common speed and the loss of kinetic energy.',
  'steps': [
   {'do': 'Take the initial direction of motion as positive and state the principle: with no resultant external force, total momentum before $=$ total momentum after, so $m_Au_A=(m_A+m_B)v$.',
    'why': 'Choosing a positive direction first is what keeps the signs right, and the examiner expects the conservation equation to be written before any numbers.'},
   {'do': f'Substitute: $0.80\\times3.0=(0.80+1.20)v$, so $v={vAB:.1f}$ m s$^{{-1}}$.',
    'why': 'The mass moving after the collision is the sum of both masses, not the target mass alone.',
    'check': {'kind': 'numeric', 'answer': num(vAB, 'm s^-1')}},
   {'do': f'Kinetic energy before $=\\tfrac12(0.80)(3.0)^2={0.5*mA*uA**2:.2f}$ J; after $=\\tfrac12(2.00)({vAB:.1f})^2={0.5*(mA+mB)*vAB**2:.2f}$ J.',
    'why': 'Kinetic energy must be recalculated from the new speed; it is not conserved here because the collision is inelastic.'},
   {'do': f'Loss of kinetic energy $={0.5*mA*uA**2:.2f}-{0.5*(mA+mB)*vAB**2:.2f}={loss:.2f}$ J.',
    'why': 'The "lost" kinetic energy has been transferred to internal energy, sound and deformation; momentum is still conserved.',
    'check': {'kind': 'numeric', 'answer': num(loss, 'J')}}],
  'faded': {'id': 'we1f',
            'problem': 'A trolley of mass 0.50 kg moving at 4.0 m s$^{-1}$ collides with a stationary trolley of mass 1.50 kg on a frictionless track and the two move off together. Calculate their common speed.',
            'answer': num(fade_v, 'm s^-1'), 'blank_from': 1}},
 {'id': 'we2', 'kc': K(2),
  'problem': 'A ball of mass 0.30 kg moving at 4.0 m s$^{-1}$ to the right collides head-on with a ball of mass 0.20 kg moving at 2.0 m s$^{-1}$ to the left. After the collision the 0.30 kg ball continues to the right at 1.6 m s$^{-1}$. Calculate the velocity of the 0.20 kg ball after the collision.',
  'steps': [
   {'do': 'Take motion to the right as positive, so the second ball approaches with velocity $-2.0$ m s$^{-1}$.',
    'why': 'Momentum is a vector: entering the opposing velocity as a negative number is the single most common source of lost marks here.'},
   {'do': 'Write momentum conservation: $0.30(4.0)+0.20(-2.0)=0.30(1.6)+0.20v$.',
    'why': 'Every object in the system appears on both sides of the equation, each with its own mass.'},
   {'do': f'$0.80=0.48+0.20v$, so $v={(0.30*4.0+0.20*-2.0-0.30*1.6)/0.20:.1f}$ m s$^{{-1}}$.',
    'why': 'A positive answer means the 0.20 kg ball has reversed and now moves to the right.',
    'check': {'kind': 'numeric', 'answer': num((0.30 * 4.0 + 0.20 * -2.0 - 0.30 * 1.6) / 0.20, 'm s^-1')}}],
  'faded': {'id': 'we2f',
            'problem': 'A ball of mass 0.40 kg moving at 5.0 m s$^{-1}$ to the right collides head-on with a ball of mass 0.20 kg moving at 3.0 m s$^{-1}$ to the left. After the collision the 0.40 kg ball moves to the right at 2.0 m s$^{-1}$. Calculate the velocity of the 0.20 kg ball.',
            'answer': num((0.40 * 5.0 + 0.20 * -3.0 - 0.40 * 2.0) / 0.20, 'm s^-1'), 'blank_from': 1}},
]

flashcards = [
 {'id': 'fc1', 'kc': K(1), 'front': 'State the principle of conservation of momentum.',
  'back': 'The total momentum of a system is constant, provided that no resultant external force acts on the system (an isolated or closed system).'},
 {'id': 'fc2', 'kc': K(1), 'front': 'What is an isolated (closed) system?',
  'back': 'A system on which no resultant external force acts, so that its total momentum cannot change.'},
 {'id': 'fc3', 'kc': K(3), 'front': 'What is a perfectly elastic collision?',
  'back': 'A collision in which the total kinetic energy of the system is conserved; equivalently, the relative speed of approach equals the relative speed of separation.'},
 {'id': 'fc4', 'kc': K(3), 'front': 'For an elastic collision, how are the relative speeds before and after related?',
  'back': 'The relative speed of approach equals the relative speed of separation: $u_1-u_2=v_2-v_1$.'},
 {'id': 'fc5', 'kc': K(3), 'front': 'What is an inelastic collision?',
  'back': 'A collision in which the total kinetic energy of the system is not conserved, although the total momentum is; the relative speed of separation is less than the relative speed of approach.'},
]

diagrams = [
 {'file': 'Assets/9702/9702-3.3-momentum-triangle.svg', 'type': 'graph_sketch',
  'params': {'lines': [{'points': [[0, 0], [2.4, 0]], 'label': 'total momentum before, 2.40 N s', 'style': 'solid'},
                       {'points': [[0, 0], [round(p1x, 3), round(p1y, 3)]], 'label': 'momentum of A after, 1.20 N s', 'style': 'solid'},
                       {'points': [[round(p1x, 3), round(p1y, 3)], [2.4, 0]], 'label': 'momentum of B after, 2.08 N s', 'style': 'dashed'}],
             'xlabel': 'momentum component along original direction / N s',
             'ylabel': 'perpendicular component / N s',
             'ticks': True}},
]

pack = {
 'subtopic': '9702-3.3', 'spec': '9702', 'version': 1,
 'note': 'Subjects/9702 Physics/03 Dynamics/3.3 Linear momentum and its conservation.md',
 'outline': 'The principle of conservation of momentum: the total momentum of a system is constant provided no resultant external force acts on it. Momentum is a vector, so a direction must be chosen positive and opposing velocities entered as negative: $m_1u_1+m_2u_2=m_1v_1+m_2v_2$. In two dimensions, momentum is conserved separately along two perpendicular directions, and components must be formed from momenta, not velocities. Momentum is conserved in every interaction in an isolated system, but kinetic energy need not be: in a perfectly elastic collision total kinetic energy is conserved and the relative speed of approach equals the relative speed of separation, while in an inelastic collision some kinetic energy becomes internal energy, sound and deformation.',
 'misconceptions': mis, 'worked': worked, 'items': items, 'flashcards': flashcards, 'diagrams': diagrams,
}
OUT.write_text(json.dumps(pack, ensure_ascii=False, indent=1) + '\n')
print(OUT, 'items', len(items), 'worked', len(worked), '| 2D:', round(v2, 3), round(th2, 2), '| ke', ke_i, ke_f)
