"""Build the 9701-3.4 teaching pack (covalent and dative covalent bonding). All numbers computed here."""
from __future__ import annotations
import json
from itertools import product
from math import sqrt
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
OUT = ROOT / 'build/out/packs/9701/9701-3.4.json'
BANK = {q['id']: q for q in json.loads((ROOT / 'build/work/mcq/9701.tagged.json').read_text())}
K = lambda n: f'9701-3.4.{n}'

# ---------------------------------------------------------------- bond data (Cambridge data booklet)
BE = {'N-H': 391, 'C-H': 410, 'O-H': 460, 'C-C': 350, 'C=C': 610, 'C#C': 840,
      'Cl-Cl': 244, 'Br-Br': 193, 'I-I': 151, 'N#N': 994, 'O=O': 496, 'H-H': 436}
BL = {'C-C': 154, 'C=C': 134, 'C#C': 120}


def sigma_pi(c: int, h: int, doubles: int, triples: int, rings: int = 0) -> tuple[int, int]:
    """sigma and pi bonds of an acyclic/cyclic hydrocarbon skeleton: one sigma per bond, extra pairs are pi."""
    return (c - 1 + rings) + h, doubles + 2 * triples


# ---------------------------------------------------------------- misconceptions
mis = [
 dict(id='m1', kc=K(1),
      statement='A covalent bond is simply a shared pair of electrons sitting between two atoms; no force needs to be named.',
      refutation='Cambridge credits the electrostatic attraction between the nuclei of the two atoms and the shared pair of electrons: the bond is a force, and both nuclei and the shared pair must appear in the definition.',
      contrast='"The electrostatic attraction between the nuclei of two atoms and a shared pair of electrons" earns the mark; "two atoms sharing electrons" does not.',
      source='ER 9701 s23 P22 Q1'),
 dict(id='m2', kc=K(1),
      statement='A coordinate (dative covalent) bond still needs one electron from each atom, so a species such as $\\ce{NH4+}$ or $\\ce{Al2Cl6}$ contains no coordinate bonds.',
      refutation='In a coordinate bond both electrons of the shared pair come from the same atom: a lone pair on the donor atom is donated into an empty orbital on the acceptor. $\\ce{NH3}$ donates its lone pair to $\\ce{H+}$ to give $\\ce{NH4+}$, and in $\\ce{Al2Cl6}$ a lone pair on a chlorine atom of each $\\ce{AlCl3}$ unit is donated to the aluminium atom of the other.',
      contrast='$\\ce{NH4+}$ has one coordinate bond (and four identical $\\ce{N-H}$ bonds once formed); $\\ce{Al2Cl6}$ has two.',
      source='ER 9701 s19 P22 Q1'),
 dict(id='m3', kc=K(2),
      statement='When bonds are counted, a double bond is taken as two $\\pi$ bonds and a triple bond as three, and $\\ce{C-H}$ bonds are left out of the count of $\\sigma$ bonds.',
      refutation='Every bond between two atoms, including every $\\ce{C-H}$ bond, contains exactly one $\\sigma$ bond. A double bond is $1\\sigma + 1\\pi$ and a triple bond is $1\\sigma + 2\\pi$, so the number of $\\pi$ bonds is (number of double bonds) $+\\ 2\\times$(number of triple bonds).',
      contrast='$\\ce{C2H4}$: 5 $\\sigma$ (one $\\ce{C-C}$, four $\\ce{C-H}$) and 1 $\\pi$, not 1 $\\sigma$ and 2 $\\pi$.',
      source='ER 9701 w21 P21 Q1'),
 dict(id='m4', kc=K(3),
      statement='Bond energy is the energy released when a bond forms, measured for the substance in any state.',
      refutation='Bond energy is defined as the energy required to break one mole of a particular covalent bond in the gaseous state, so it is an endothermic quantity with a positive sign; bond formation releases the same magnitude of energy but is not what the definition states.',
      contrast='$E(\\ce{Cl-Cl}) = +244$ kJ mol$^{-1}$ breaks one mole of $\\ce{Cl-Cl}$ bonds in gaseous chlorine; $-244$ kJ mol$^{-1}$ would be bond formation.',
      source='ER 9701 w21 P21 Q1'),
 dict(id='m5', kc=K(3),
      statement='A longer bond is a stronger bond, so a molecule with long bonds is less reactive.',
      refutation='Bond length is the internuclear distance of two covalently bonded atoms; the longer that distance, the weaker the electrostatic attraction holding the atoms together, so bond energy falls as bond length rises and the molecule becomes more easily broken, that is more reactive.',
      contrast='$\\ce{C#C}$ (120 pm, 840 kJ mol$^{-1}$) is shorter and stronger than $\\ce{C-C}$ (154 pm, 350 kJ mol$^{-1}$); $\\ce{I2}$ has the longest, weakest bond of the halogens and dissociates most readily.',
      source='ER 9701 s19 P22 Q1'),
]

# ---------------------------------------------------------------- past-paper items
# (bank id, kcs, difficulty, command word, explanation, distractor map)
past_info = [
 ('9701_w25_13_q6', [K(1), K(2)], 4, 'Deduce',
  'In $\\ce{NH4+}$ the nitrogen lone pair is donated to $\\ce{H+}$, giving one coordinate bond, and the cyanide ion $\\ce{CN-}$ contains a triple bond, which is $1\\sigma + 2\\pi$: one coordinate bond and two $\\pi$ bonds, so B. The popular wrong choice D counts the triple bond as three $\\pi$ bonds instead of one $\\sigma$ and two $\\pi$; A and C miss the coordinate bond because they expect each atom to supply one electron.',
  {'A': 'm2', 'C': 'm2', 'D': 'm3'}),
 ('9701_w25_12_q25', [K(2)], 3, 'Deduce',
  'Methanal, $\\ce{HCHO}$, has three $\\sigma$ bonds (two $\\ce{C-H}$ and the $\\sigma$ of the $\\ce{C=O}$) plus one $\\pi$ bond, and its $sp^2$ carbon makes it planar, so both statements are correct (A). Candidates who reject statement 2 have forgotten that the $\\ce{C-H}$ bonds are $\\sigma$ bonds and that a double bond contains one $\\sigma$ bond as well as one $\\pi$ bond.',
  {'B': 'm3', 'C': 'm3', 'D': 'm3'}),
 ('9701_w22_13_q5', [K(2)], 4, 'Deduce',
  'In $\\ce{H-C#C-C(CH3)=CH(CH3)}$ there are 5 $\\sigma$ bonds in the carbon skeleton and 8 $\\ce{C-H}$ bonds, giving 13 (C). The popular answer of 11 leaves out two of the $\\ce{C-H}$ bonds or does not count the $\\sigma$ bond inside the multiple bonds; 16 counts the extra pairs of the double and triple bonds as $\\sigma$ bonds as well.',
  {'B': 'm3', 'D': 'm3'}),
 ('9701_w19_13_q4', [K(2)], 5, 'Determine',
  '$\\ce{C2H4}$ has 5 $\\sigma$ bonds and $\\ce{CH3CO2H}$ has 7, both odd, while $\\ce{C2H5OH}$ has 8 and $\\ce{CH3CHO}$ has 6: two compounds, so B. Candidates who answer 1 or 3 have missed the $\\sigma$ bond inside a $\\ce{C=O}$ double bond or the $\\ce{O-H}$ bond, both of which count.',
  {'A': 'm3', 'C': 'm3'}),
 ('9701_w19_13_q37', [K(2)], 4, 'Deduce',
  'Tiglic acid, $\\ce{CH3CH=C(CH3)CO2H}$, has one $\\ce{C=C}$ and one $\\ce{C=O}$, so two $\\pi$ bonds (statement 1), and its two oxygen atoms carry two lone pairs each, so four lone pairs (statement 2); statement 3 fails because the hydrogen atoms of the methyl groups lie out of the plane. The common error is to accept statement 3 because the $sp^2$ centres are planar, forgetting the tetrahedral $\\ce{CH3}$ groups.',
  {}),
 ('9701_w19_12_q32', [K(1), K(2)], 4, 'Deduce',
  'In $\\ce{CO}$ the triple bond is $1\\sigma + 2\\pi$ and one of its three bonds is a coordinate bond from oxygen to carbon, which leaves one lone pair on each atom, so all three features are present (A). Candidates who reject the coordinate bond have assumed that every bond must take one electron from each atom.',
  {}),
 ('9701_s25_13_q8', [K(2)], 3, 'Deduce',
  'The sugar shown has only single bonds, so it contains only $\\sigma$ bonds (statement 1), and the ring carbons are $sp^3$ hybridised and tetrahedral, so the six-membered ring is non-planar (statement 4): B. The popular wrong answer takes the ring to be planar, which would require $sp^2$ carbon atoms as in benzene.',
  {'A': 'm3', 'C': 'm3', 'D': 'm3'}),
 ('9701_s22_12_q5', [K(2)], 2, 'Identify',
  'Every bond in both molecules is at least a $\\sigma$ bond, so $\\sigma$ covalent bonds are the shared feature (C). D is wrong because only ethene has a $\\pi$ bond; ethane is not planar and ethene has bond angles of about $120^\\circ$, not $109^\\circ$.',
  {'D': 'm3'}),
 ('9701_s19_12_q4', [K(2)], 3, 'Identify',
  'The $\\ce{C-C}$ $\\sigma$ bond of ethene is formed by direct, end-on overlap of an $sp^2$ orbital on each carbon atom along the line joining the nuclei, which is diagram C. The diagrams showing two p orbitals overlapping sideways above and below that line are $\\pi$ bonds, not the $\\sigma$ bond asked for.',
  {}),
]

items = []
for qid, kcs, diff, cw, explanation, distractors in past_info:
 q = BANK[qid]
 it = dict(id='9701-3.4-p' + str(len(items) + 1).zfill(2), kcs=kcs, kind='mcq', difficulty=diff,
           command_word=cw, source={'type': 'past', 'ref': q['ref'], 'qid': qid}, stem=q['stem'],
           answer=q['answer'], marks=1, explanation=explanation,
           distractors={k: v for k, v in distractors.items() if k != q['answer']})
 if q.get('options'):
  it['options'] = q['options']
 if q.get('image'):
  it['image'] = q['image']
 assert q.get('options') or q.get('image'), qid
 items.append(it)


def gen(kind, kcs, stem, difficulty, command_word, explanation, hints, **more):
 n = 1 + sum(i['source']['type'] == 'generated' for i in items)
 items.append(dict(id=f'9701-3.4-i{n:02}', kcs=kcs, kind=kind, difficulty=difficulty,
                   command_word=command_word, source={'type': 'generated'}, stem=stem,
                   marks=more.pop('marks', 1), explanation=explanation, hints=hints, **more))


def num(value, unit, sf=(2, 3)):
 return {'value': round(value, 10), 'unit': unit, 'sf_ok': list(sf)}


def template(kcs, stem, params, derived, answer_expr, unit, wrong, explanation, hints,
             difficulty=3, command_word='Calculate', constraints=(), sf=(2, 3)):
 def ev(expr, env):
  return eval(expr, {'__builtins__': {}, 'sqrt': sqrt, 'abs': abs}, env)

 def base(spec):
  return spec['choices'] if 'choices' in spec else [round(spec['min'] + i * spec['step'], 10)
                                                    for i in range(round((spec['max'] - spec['min']) / spec['step']) + 1)]
 nominal = None
 for values in product(*[base(s) for s in params.values()]):
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
 gen('numeric', kcs, stem, difficulty, command_word, explanation, hints,
     answer=num(ev(answer_expr, nominal), unit, sf),
     distractors=[{'value': round(ev(expr, nominal), 10), 'misconception': mid} for expr, mid in wrong],
     template={'params': params, 'derived': derived, 'answer': answer_expr,
               'distractors': [{'expr': expr, 'misconception': mid} for expr, mid in wrong],
               'constraints': list(constraints)})


# ================================================================ KC1: covalent and dative covalent bonding
gen('short', [K(1)], 'Define covalent bonding.', 1, 'Define',
    'Cambridge credits the electrostatic attraction between the nuclei of two atoms and a shared pair of electrons; both nuclei and the shared pair must be named.',
    ['The definition names a force, not just a picture of electrons.',
     'State which particles attract which, using the word electrostatic.',
     'Begin "the electrostatic attraction between…".'],
    marks=2,
    rubric=[{'point': 'Electrostatic attraction (between oppositely charged particles).',
             'keywords': [['electrostatic', 'attraction', 'attractive force']]},
            {'point': 'Between the nuclei of the two atoms and the shared pair of electrons.',
             'keywords': [['nuclei', 'nucleus'], ['shared pair', 'shared electrons', 'pair of electrons']]}])

gen('short', [K(1)], 'Describe what is meant by a coordinate (dative covalent) bond.', 1, 'Describe',
    'A coordinate bond is a shared pair of electrons in which both electrons are supplied by the same atom: a lone pair on the donor is donated into an empty orbital on the acceptor.',
    ['Compare it with an ordinary covalent bond: where do the two electrons come from?',
     'Say which atom supplies the electrons and what the other atom must have available.',
     'The donated electrons start as a lone pair.'],
    marks=2,
    rubric=[{'point': 'A shared pair of electrons in which both electrons come from the same atom.',
             'keywords': [['both electrons', 'two electrons', 'both'], ['same atom', 'one atom', 'donor']]},
            {'point': 'The donor supplies a lone pair to an empty orbital on the acceptor atom.',
             'keywords': [['lone pair'], ['empty orbital', 'vacant orbital', 'empty', 'accept']]}])

gen('mcq', [K(1)], 'Which molecule contains an atom whose outer shell holds more than eight electrons?', 2, 'Identify',
    'Sulfur is a period 3 element and can expand its octet: in $\\ce{SF6}$ the sulfur atom forms six bonding pairs, giving 12 electrons in its outer shell. The period 2 central atoms in $\\ce{CO2}$, $\\ce{NH3}$ and $\\ce{C2H4}$ are limited to eight.',
    ['Only elements in period 3 and beyond can expand the octet.',
     'Count the bonding pairs around the central atom of each molecule.',
     'A central atom with six bonding pairs has 12 outer electrons.'],
    options={'A': '$\\ce{CO2}$', 'B': '$\\ce{NH3}$', 'C': '$\\ce{SF6}$', 'D': '$\\ce{C2H4}$'},
    answer='C', distractors={'A': 'm1', 'B': 'm1', 'D': 'm1'}, shuffle=True)

gen('mcq', [K(1)], 'How many coordinate (dative covalent) bonds are present in one molecule of $\\ce{Al2Cl6}$?', 3, 'Deduce',
    'Two $\\ce{AlCl3}$ units join by each donating a lone pair from one of its chlorine atoms into the empty orbital on the aluminium atom of the other unit, so the molecule contains two coordinate bonds (and four ordinary $\\ce{Al-Cl}$ bonds).',
    ['The molecule is two $\\ce{AlCl3}$ units joined through bridging chlorine atoms.',
     'Count how many lone pairs have to be donated to hold the two halves together.',
     'Each $\\ce{AlCl3}$ unit has an aluminium atom with an incomplete shell that accepts one pair.'],
    options={'A': '1', 'B': '2', 'C': '3', 'D': '4'},
    answer='B', distractors={'A': 'm2', 'C': 'm2', 'D': 'm2'}, shuffle=True)

gen('short', [K(1)], 'Ammonia gas and hydrogen chloride gas react to form solid ammonium chloride. Explain how the bonding in the ammonium ion is formed, and state how the four $\\ce{N-H}$ bonds compare once the ion has formed.', 3, 'Explain',
    'The nitrogen lone pair is donated to the $\\ce{H+}$ released by $\\ce{HCl}$, forming a coordinate bond; all four $\\ce{N-H}$ bonds are then identical because each is a shared pair held by the same two nuclei.',
    ['Nitrogen in ammonia has something no hydrogen atom has.',
     'Say what nitrogen donates, what accepts it, and what kind of bond results.',
     'The $\\ce{H+}$ ion has an empty 1s orbital.'],
    marks=3,
    rubric=[{'point': 'The $\\ce{HCl}$ supplies $\\ce{H+}$, which has an empty orbital and no electrons of its own.',
             'keywords': [['H+', 'proton', 'hydrogen ion'], ['empty', 'vacant', 'no electrons']]},
            {'point': 'The lone pair on the nitrogen atom of $\\ce{NH3}$ is donated to it, forming a coordinate (dative covalent) bond.',
             'keywords': [['lone pair'], ['donat', 'coordinate', 'co-ordinate', 'dative']]},
            {'point': 'All four $\\ce{N-H}$ bonds in $\\ce{NH4+}$ are identical/equivalent once formed.',
             'keywords': [['four', 'all'], ['identical', 'equivalent', 'the same', 'indistinguishable']]}])

gen('structured', [K(1)], 'A molecule of carbon dioxide, $\\ce{CO2}$, and a molecule of sulfur dioxide, $\\ce{SO2}$, each contain two oxygen atoms bonded to a central atom. Describe the covalent bonding in each molecule, including the number of shared pairs of electrons, and explain why only one of the two central atoms can hold more than eight electrons in its outer shell.', 4, 'Describe',
    '$\\ce{CO2}$ has two $\\ce{C=O}$ double bonds, so four shared pairs and eight electrons around carbon; $\\ce{SO2}$ can be drawn with two $\\ce{S=O}$ double bonds, giving four shared pairs plus a lone pair, so ten electrons around sulfur, which is possible because sulfur is in period 3.',
    ['Start by counting double bonds in each molecule.',
     'Count shared pairs around each central atom, then say which period each central atom is in.',
     'Carbon is in period 2 and sulfur in period 3.'],
    marks=4,
    scheme=[{'mark': 'B1', 'point': '$\\ce{CO2}$: two $\\ce{C=O}$ double bonds, that is four shared pairs of electrons, with two lone pairs on each oxygen atom.',
             'check': {'kind': 'numeric', 'answer': num(4, '', (1,))}},
            {'mark': 'B1', 'point': 'Carbon therefore has eight electrons in its outer shell, a complete octet.',
             'check': {'kind': 'numeric', 'answer': num(8, '', (1,))}},
            {'mark': 'B1', 'point': '$\\ce{SO2}$: two $\\ce{S=O}$ double bonds (four shared pairs) and one lone pair on the sulfur atom, giving ten electrons in the outer shell of sulfur.',
             'check': {'kind': 'numeric', 'answer': num(10, '', (2,))}},
            {'mark': 'B1', 'point': 'Sulfur is in period 3 and can expand its octet (it has d orbitals available), whereas a period 2 atom such as carbon cannot hold more than eight outer electrons.'}])

# ================================================================ KC2: sigma and pi bonds, hybridisation
s_eth, p_eth = sigma_pi(2, 4, 1, 0)
assert (s_eth, p_eth) == (5, 1)
s_hcn, p_hcn = sigma_pi(2, 1, 0, 1)
assert (s_hcn, p_hcn) == (2, 2)

gen('short', [K(2)], 'State what is meant by a $\\sigma$ bond and by a $\\pi$ bond.', 1, 'State',
    'A $\\sigma$ bond is formed by direct (end-on) overlap of orbitals between the bonding atoms; a $\\pi$ bond is formed by the sideways overlap of adjacent p orbitals above and below the $\\sigma$ bond.',
    ['Both answers describe how orbitals overlap.',
     'For each bond say which orbitals overlap and in what direction.',
     'One overlap is end-on along the line joining the nuclei.'],
    marks=2,
    rubric=[{'point': '$\\sigma$: direct/end-on overlap of orbitals between the bonding atoms (along the internuclear axis).',
             'keywords': [['direct', 'end-on', 'head-on', 'along'], ['overlap']]},
            {'point': '$\\pi$: sideways overlap of adjacent p orbitals, above and below the $\\sigma$ bond.',
             'keywords': [['sideways', 'side-on', 'parallel'], ['p orbital', 'p orbitals'], ['above and below', 'above', 'below']]}])

gen('mcq', [K(2)], 'Which statement about the bonding in a molecule of ethene, $\\ce{C2H4}$, is correct?', 3, 'Identify',
    'Each carbon atom in ethene is $sp^2$ hybridised: three $sp^2$ orbitals form $\\sigma$ bonds (two to hydrogen atoms and one to the other carbon atom) and the remaining 2p orbital on each carbon overlaps sideways to give one $\\pi$ bond.',
    ['Count the $\\sigma$ bonds first: there are five of them.',
     'Decide how many orbitals each carbon atom needs for $\\sigma$ bonding, and what it does with the rest.',
     'A carbon atom forming three $\\sigma$ bonds uses three hybrid orbitals.'],
    options={'A': 'Each carbon atom is $sp^2$ hybridised and the $\\ce{C=C}$ bond is one $\\sigma$ and one $\\pi$ bond.',
             'B': 'Each carbon atom is $sp^3$ hybridised and the $\\ce{C=C}$ bond is two $\\sigma$ bonds.',
             'C': 'Each carbon atom is sp hybridised and the $\\ce{C=C}$ bond is two $\\pi$ bonds.',
             'D': 'The $\\ce{C-H}$ bonds are $\\pi$ bonds and the $\\ce{C=C}$ bond is a $\\sigma$ bond.'},
    answer='A', distractors={'B': 'm3', 'C': 'm3', 'D': 'm3'}, shuffle=True)

gen('mcq', [K(2)], 'In which molecule is the central carbon atom sp hybridised?', 2, 'Identify',
    'Hydrogen cyanide, $\\ce{HCN}$, has $\\ce{H-C#N}$: the carbon atom forms two $\\sigma$ bonds and two $\\pi$ bonds, so it uses two sp hybrid orbitals and keeps two unhybridised p orbitals.',
    ['The number of hybrid orbitals equals the number of $\\sigma$ bonds the atom forms.',
     'Count the $\\sigma$ bonds at the carbon atom in each molecule.',
     'A carbon atom forming only two $\\sigma$ bonds is sp hybridised.'],
    options={'A': '$\\ce{CH4}$', 'B': '$\\ce{C2H4}$', 'C': '$\\ce{HCN}$', 'D': '$\\ce{C2H6}$'},
    answer='C', distractors={'A': 'm3', 'B': 'm3', 'D': 'm3'}, shuffle=True)

template([K(2)],
         'A hydrocarbon molecule contains [[c]] carbon atoms and [[h]] hydrogen atoms in an open chain, with [[d]] carbon-carbon double bonds and no other multiple bonds. Calculate the number of $\\sigma$ bonds in one molecule.',
         {'c': {'choices': [4, 5, 6, 7]}, 'h': {'choices': [8, 10, 12]}, 'd': {'choices': [1, 2]}},
         {}, '(c-1)+h', '',
         [('c-1', 'm3'), ('(c-1)+h+d', 'm3')],
         'Every bond between two atoms contains exactly one $\\sigma$ bond, so the count is (number of carbon-carbon bonds) $+$ (number of $\\ce{C-H}$ bonds) $=(c-1)+h$; the extra pair in each double bond is a $\\pi$ bond, not a second $\\sigma$ bond.',
         ['Each pair of bonded atoms is joined by exactly one $\\sigma$ bond.',
          'Count the carbon-carbon bonds and the carbon-hydrogen bonds separately, then add them.',
          'An open chain of $c$ carbon atoms has $c-1$ carbon-carbon bonds.'],
         difficulty=3, command_word='Calculate', constraints=['h == 2*c+2-2*d', 'c-1 > 0'], sf=(1, 2))

gen('mcq', [K(2)], 'How many $\\pi$ bonds are present in one molecule of $\\ce{N2}$ and in one molecule of $\\ce{C2H6}$?', 2, 'Deduce',
    'The triple bond in $\\ce{N2}$ is $1\\sigma + 2\\pi$, so nitrogen has two $\\pi$ bonds, while every bond in ethane is a single bond and therefore a $\\sigma$ bond only, so ethane has none.',
    ['Decide what kind of bond each molecule contains.',
     'Split each multiple bond into its $\\sigma$ and $\\pi$ parts.',
     'A triple bond is one $\\sigma$ bond and two $\\pi$ bonds.'],
    options={'A': '$\\ce{N2}$: 2, $\\ce{C2H6}$: 0', 'B': '$\\ce{N2}$: 3, $\\ce{C2H6}$: 0',
             'C': '$\\ce{N2}$: 2, $\\ce{C2H6}$: 1', 'D': '$\\ce{N2}$: 1, $\\ce{C2H6}$: 1'},
    answer='A', distractors={'B': 'm3', 'C': 'm3', 'D': 'm3'}, shuffle=True)

gen('structured', [K(2)], 'Describe how the $\\sigma$ and $\\pi$ bonds in a molecule of ethene, $\\ce{C2H4}$, are formed from the orbitals of its atoms, and explain why ethene is planar while ethane, $\\ce{C2H6}$, is not.', 5, 'Explain',
    'Each carbon in ethene uses three $sp^2$ hybrid orbitals for $\\sigma$ bonds and one 2p orbital for the $\\pi$ bond; the three $sp^2$ orbitals lie in a plane at $120^\\circ$, and the sideways p overlap locks the two $\\ce{CH2}$ units coplanar, whereas the $sp^3$ carbons of ethane are tetrahedral.',
    ['Count the $\\sigma$ bonds at each carbon atom before naming the hybridisation.',
     'Describe the hybrid orbitals, then the leftover p orbitals, then relate the shape to each.',
     'Each carbon atom in ethene forms three $\\sigma$ bonds, so it needs three hybrid orbitals.'],
    marks=5,
    scheme=[{'mark': 'B1', 'point': 'Each carbon atom is $sp^2$ hybridised: one 2s and two 2p orbitals mix to give three $sp^2$ orbitals.'},
            {'mark': 'B1', 'point': 'The $sp^2$ orbitals overlap directly (end-on) to give five $\\sigma$ bonds: four $\\ce{C-H}$ and one $\\ce{C-C}$.',
             'check': {'kind': 'numeric', 'answer': num(s_eth, '', (1,))}},
            {'mark': 'B1', 'point': 'The unhybridised 2p orbital on each carbon atom overlaps sideways, above and below the $\\ce{C-C}$ $\\sigma$ bond, forming one $\\pi$ bond.',
             'check': {'kind': 'numeric', 'answer': num(p_eth, '', (1,))}},
            {'mark': 'B1', 'point': 'The three $sp^2$ orbitals on each carbon atom lie in one plane at about $120^\\circ$ to one another, so all six atoms of ethene are coplanar.'},
            {'mark': 'B1', 'point': 'In ethane each carbon atom forms four $\\sigma$ bonds, is $sp^3$ hybridised and is tetrahedral (about $109.5^\\circ$), so the molecule cannot be planar; there is also no $\\pi$ bond to prevent rotation about the $\\ce{C-C}$ bond.'}])

# ================================================================ KC3: bond energy and bond length
gen('short', [K(3)], 'Define bond energy.', 1, 'Define',
    'Bond energy is the energy required to break one mole of a particular covalent bond in the gaseous state, so it is always endothermic.',
    ['The definition is about breaking, not making.',
     'State the amount of bonds, the process and the state of the substance.',
     'Begin "the energy required to break one mole of…".'],
    marks=2,
    rubric=[{'point': 'The energy required to break one mole of a particular covalent bond.',
             'keywords': [['energy'], ['break', 'breaking', 'dissociate'], ['one mole', '1 mol', 'per mole', 'mole']]},
            {'point': 'With the species in the gaseous state.',
             'keywords': [['gaseous', 'gas', 'g)']]}])

gen('short', [K(3)], 'Define bond length.', 1, 'Define',
    'Bond length is the internuclear distance of two covalently bonded atoms, that is the distance between the two nuclei.',
    ['The distance is measured between two particular points in the atoms.',
     'Name the two points the distance is measured between.',
     'It is a distance between nuclei, not between electron shells.'],
    marks=1,
    rubric=[{'point': 'The internuclear distance (distance between the nuclei) of two covalently bonded atoms.',
             'keywords': [['internuclear', 'nuclei', 'nucleus'], ['distance', 'separation']]}])

gen('mcq', [K(3)], 'The $\\ce{C-C}$, $\\ce{C=C}$ and $\\ce{C#C}$ bonds have lengths of 154 pm, 134 pm and 120 pm. Which statement about these bonds is correct?', 3, 'Deduce',
    'The shorter the bond, the closer the nuclei are to the shared electrons, so the stronger the electrostatic attraction and the larger the bond energy: $\\ce{C#C}$ (120 pm) is the shortest and has the highest bond energy of the three.',
    ['Decide first which of the three bonds is the shortest.',
     'Relate the internuclear distance to the strength of the attraction holding the atoms together.',
     'More shared pairs between the same two nuclei pull them closer together.'],
    options={'A': 'The $\\ce{C#C}$ bond is the shortest and has the highest bond energy.',
             'B': 'The $\\ce{C-C}$ bond is the longest and has the highest bond energy.',
             'C': 'All three bonds have the same bond energy because they join the same two elements.',
             'D': 'The $\\ce{C=C}$ bond is the shortest and has the lowest bond energy.'},
    answer='A', distractors={'B': 'm5', 'C': 'm5', 'D': 'm5'}, shuffle=True)

template([K(3)],
         'The $\\ce{N-H}$ bond energy in ammonia is [[e]] kJ mol$^{-1}$. Calculate the energy required to break all of the bonds in [[n]] mol of gaseous ammonia, $\\ce{NH3}$.',
         {'e': {'choices': [388, 391, 394]}, 'n': {'choices': [0.5, 1.5, 2.0, 2.5]}},
         {}, '3*n*e', 'kJ',
         [('n*e', 'm4'), ('3*e', 'm4')],
         'Each $\\ce{NH3}$ molecule contains three $\\ce{N-H}$ bonds, so breaking $n$ mol of ammonia breaks $3n$ mol of $\\ce{N-H}$ bonds: energy $=3ne$.',
         ['Count the bonds in one molecule of ammonia before using the bond energy.',
          'Find the number of moles of $\\ce{N-H}$ bonds, then multiply by the bond energy.',
          'One mole of $\\ce{NH3}$ contains three moles of $\\ce{N-H}$ bonds.'],
         difficulty=2, command_word='Calculate', constraints=['n != 1'], sf=(2, 3, 4))

gen('mcq', [K(3)], 'The bond energies of $\\ce{Cl-Cl}$, $\\ce{Br-Br}$ and $\\ce{I-I}$ are 244 kJ mol$^{-1}$, 193 kJ mol$^{-1}$ and 151 kJ mol$^{-1}$. Which deduction about these molecules is correct?', 3, 'Deduce',
    'Bond energy falls from $\\ce{Cl2}$ to $\\ce{I2}$ because the bond length increases down the group, so the $\\ce{I-I}$ bond is the easiest to break and $\\ce{I2}$ dissociates into atoms most readily.',
    ['Decide which bond needs least energy to break.',
     'Link the bond energy to how easily the molecule splits into atoms, and to the bond length.',
     'The atoms get larger down the group, so the bonds get longer.'],
    options={'A': '$\\ce{I2}$ has the longest bond and dissociates into atoms most readily.',
             'B': '$\\ce{I2}$ has the shortest bond and dissociates into atoms most readily.',
             'C': '$\\ce{Cl2}$ has the longest bond and dissociates into atoms most readily.',
             'D': 'All three molecules dissociate equally readily because each contains one single bond.'},
    answer='A', distractors={'B': 'm5', 'C': 'm5', 'D': 'm5'}, shuffle=True)

template([K(3)],
         'The $\\ce{C-H}$ bond energy is [[e]] kJ mol$^{-1}$ and the $\\ce{C-C}$ bond energy is [[f]] kJ mol$^{-1}$. Calculate the energy required to break all of the bonds in [[n]] mol of gaseous ethane, $\\ce{C2H6}$.',
         {'e': {'choices': [410, 413]}, 'f': {'choices': [347, 350]}, 'n': {'choices': [0.5, 1.5, 2.0]}},
         {}, 'n*(6*e+f)', 'kJ',
         [('n*(6*e)', 'm4'), ('n*(e+f)', 'm4')],
         'One molecule of ethane has six $\\ce{C-H}$ bonds and one $\\ce{C-C}$ bond, so breaking $n$ mol needs $n(6E(\\ce{C-H})+E(\\ce{C-C}))$; the $\\ce{C-C}$ bond must not be forgotten.',
         ['Draw ethane and count each type of bond.',
          'Multiply the number of moles of each type of bond by its bond energy, then add the two totals.',
          'One mole of ethane contains six moles of $\\ce{C-H}$ bonds and one mole of $\\ce{C-C}$ bonds.'],
         difficulty=3, command_word='Calculate', constraints=['n != 1'], sf=(3, 4, 5))

gen('structured', [K(3), K(2)], 'Nitrogen, $\\ce{N2}$, has a bond energy of 994 kJ mol$^{-1}$ and a bond length of 110 pm. Oxygen, $\\ce{O2}$, has a bond energy of 496 kJ mol$^{-1}$ and a bond length of 121 pm. Explain, in terms of bonding, bond energy and bond length, why nitrogen is much less reactive than oxygen at room temperature.', 5, 'Explain',
    'Nitrogen has a triple bond ($1\\sigma + 2\\pi$) and oxygen a double bond ($1\\sigma + 1\\pi$); the extra shared pair pulls the nuclei closer, giving the shorter, much stronger bond, so far more energy is needed to break $\\ce{N#N}$ and nitrogen reacts only under extreme conditions.',
    ['Start from the number of shared pairs in each molecule.',
     'Link the number of bonds to the bond length, the bond length to the bond energy, and the bond energy to reactivity.',
     'Nitrogen has a triple bond and oxygen a double bond.'],
    marks=5,
    scheme=[{'mark': 'B1', 'point': '$\\ce{N2}$ contains a triple bond, that is one $\\sigma$ and two $\\pi$ bonds (three shared pairs).',
             'check': {'kind': 'numeric', 'answer': num(2, '', (1,))}},
            {'mark': 'B1', 'point': '$\\ce{O2}$ contains a double bond, that is one $\\sigma$ and one $\\pi$ bond (two shared pairs).'},
            {'mark': 'B1', 'point': 'The extra shared pair in $\\ce{N2}$ gives a greater electrostatic attraction between the nuclei and the shared electrons, so the bond length is shorter (110 pm against 121 pm).'},
            {'mark': 'B1', 'point': 'The shorter bond is the stronger bond: the bond energy of $\\ce{N#N}$ is 994 kJ mol$^{-1}$, about twice that of $\\ce{O=O}$ at 496 kJ mol$^{-1}$.',
             'check': {'kind': 'numeric', 'answer': num(BE['N#N'] - BE['O=O'], 'kJ mol^-1')}},
            {'mark': 'B1', 'point': 'Far more energy must therefore be supplied to break the $\\ce{N#N}$ bond before nitrogen can react, so $\\ce{N2}$ is unreactive at room temperature while $\\ce{O2}$ reacts readily.'}])

# ================================================================ worked examples
nh3_total = 3 * 2.0 * BE['N-H']
ch4_total = 4 * 0.5 * BE['C-H']
assert (nh3_total, ch4_total) == (2346.0, 820.0)
s_pent, p_pent = sigma_pi(5, 6, 1, 1)
assert (s_pent, p_pent) == (10, 3)
s_bute, p_bute = sigma_pi(4, 8, 1, 0)
assert (s_bute, p_bute) == (11, 1)

worked = [
 {'id': 'we1', 'kc': K(1),
  'problem': 'Phosphorus pentachloride, $\\ce{PCl5}$, is a covalent molecule in which five chlorine atoms are each bonded to the central phosphorus atom. Describe the bonding and determine the number of electrons in the outer shell of the phosphorus atom.',
  'steps': [
   {'do': 'Identify the bonding: each $\\ce{P-Cl}$ bond is a covalent bond, the electrostatic attraction between the two nuclei and a shared pair of electrons, with one electron of each pair supplied by phosphorus and one by chlorine.',
    'why': 'The question says "describe the bonding", so the definition in the syllabus wording must appear, not just the word "covalent".'},
   {'do': 'Count the shared pairs around the central atom: phosphorus forms five single bonds, so there are five bonding pairs and no lone pair on phosphorus.',
    'why': 'Counting the pairs around the central atom is the step that decides whether the octet has been expanded.',
    'check': {'kind': 'numeric', 'answer': num(5, '', (1,))}},
   {'do': 'Each shared pair contributes two electrons to the outer shell of phosphorus: $5\\times2=10$ electrons.',
    'why': 'Both electrons of a shared pair count towards the outer shell of each bonded atom; a student who counts only the electron phosphorus supplied gets 5.',
    'check': {'kind': 'numeric', 'answer': num(10, '', (2,))}},
   {'do': 'State the conclusion: phosphorus has 10 electrons in its outer shell, more than an octet. This is possible because phosphorus is in period 3 and can expand its octet.',
    'why': 'The mark for the explanation depends on naming period 3 (expanded octet); a period 2 atom such as nitrogen cannot form $\\ce{NCl5}$.'}],
  'faded': {'id': 'we1f',
            'problem': 'In sulfur hexafluoride, $\\ce{SF6}$, six fluorine atoms are each bonded to the central sulfur atom. Determine the number of electrons in the outer shell of the sulfur atom.',
            'answer': num(12, '', (2,)), 'blank_from': 1}},
 {'id': 'we2', 'kc': K(2),
  'problem': 'Determine the number of $\\sigma$ bonds and the number of $\\pi$ bonds in one molecule of $\\ce{CH3CH=CH-C#CH}$.',
  'steps': [
   {'do': 'Write out the skeleton and count the bonds between atoms: 5 carbon atoms in a chain give 4 carbon-carbon bonds, and the formula $\\ce{C5H6}$ gives 6 carbon-hydrogen bonds.',
    'why': 'The count of $\\sigma$ bonds is a count of bonded pairs of atoms, so the hydrogen atoms must be included: they are the bonds most often left out.'},
   {'do': f'Every bond between two atoms contains exactly one $\\sigma$ bond, so the number of $\\sigma$ bonds is $4+6={s_pent}$.',
    'why': 'A double or triple bond still contributes only one $\\sigma$ bond; the extra pairs are $\\pi$ bonds.',
    'check': {'kind': 'numeric', 'answer': num(s_pent, '', (1, 2))}},
   {'do': f'Count the extra pairs: the double bond adds one $\\pi$ bond and the triple bond adds two, so there are ${p_pent}$ $\\pi$ bonds.',
    'why': 'A double bond is $1\\sigma+1\\pi$ and a triple bond is $1\\sigma+2\\pi$; counting a triple bond as three $\\pi$ bonds is the standard error.',
    'check': {'kind': 'numeric', 'answer': num(p_pent, '', (1,))}},
   {'do': f'Answer: ${s_pent}$ $\\sigma$ bonds and ${p_pent}$ $\\pi$ bonds. Check: the $\\pi$ bonds come from sideways overlap of adjacent p orbitals, so the two carbon atoms of the triple bond are sp hybridised.',
    'why': 'Relating the count back to orbital overlap is what earns the hybridisation marks in a structured question.'}],
  'faded': {'id': 'we2f',
            'problem': 'Determine the number of $\\sigma$ bonds in one molecule of $\\ce{CH3CH2CH=CH2}$.',
            'answer': num(s_bute, '', (1, 2)), 'blank_from': 1}},
 {'id': 'we3', 'kc': K(3),
  'problem': 'The $\\ce{N-H}$ bond energy is 391 kJ mol$^{-1}$. Calculate the energy required to break all of the bonds in 2.0 mol of gaseous ammonia, $\\ce{NH3}$.',
  'steps': [
   {'do': 'State what the bond energy means: 391 kJ breaks one mole of $\\ce{N-H}$ bonds in the gaseous state, and bond breaking is endothermic.',
    'why': 'Writing the definition first fixes the direction of the energy change, so the answer is quoted as energy required, not released.'},
   {'do': 'Count the bonds: one molecule of $\\ce{NH3}$ has three $\\ce{N-H}$ bonds, so 2.0 mol of $\\ce{NH3}$ contains $3\\times2.0=6.0$ mol of $\\ce{N-H}$ bonds.',
    'why': 'The bond energy is per mole of bonds, not per mole of molecules; missing the factor of 3 is the commonest slip here.',
    'check': {'kind': 'numeric', 'answer': num(6.0, 'mol')}},
   {'do': f'Multiply: energy $=6.0\\times391={nh3_total:.0f}$ kJ.',
    'why': 'The unit is kJ, not kJ mol$^{-1}$, because a stated amount of substance has been used.',
    'check': {'kind': 'numeric', 'answer': num(nh3_total, 'kJ', (3, 4))}}],
  'faded': {'id': 'we3f',
            'problem': 'The $\\ce{C-H}$ bond energy is 410 kJ mol$^{-1}$. Calculate the energy required to break all of the bonds in 0.50 mol of gaseous methane, $\\ce{CH4}$.',
            'answer': num(ch4_total, 'kJ', (2, 3)), 'blank_from': 1}},
]

# ================================================================ flashcards
flashcards = [
 {'id': 'fc1', 'kc': K(1), 'front': 'Define covalent bonding.',
  'back': 'The electrostatic attraction between the nuclei of two atoms and a shared pair of electrons.'},
 {'id': 'fc2', 'kc': K(1), 'front': 'What is a coordinate (dative covalent) bond?',
  'back': 'A covalent bond in which both electrons of the shared pair come from the same atom: a lone pair is donated into an empty orbital on the acceptor atom.'},
 {'id': 'fc3', 'kc': K(1), 'front': 'Which molecules in the syllabus show an expanded octet, and how many outer electrons has the central atom?',
  'back': 'Period 3 central atoms can expand the octet: $\\ce{SO2}$ (10 electrons on S), $\\ce{PCl5}$ (10 on P) and $\\ce{SF6}$ (12 on S).'},
 {'id': 'fc4', 'kc': K(1), 'front': 'How is the ammonium ion formed when ammonia and hydrogen chloride gases react?',
  'back': 'The lone pair on the nitrogen atom of $\\ce{NH3}$ is donated to the empty orbital of $\\ce{H+}$ from $\\ce{HCl}$, forming a coordinate bond; all four $\\ce{N-H}$ bonds in $\\ce{NH4+}$ are then identical.'},
 {'id': 'fc5', 'kc': K(2), 'front': 'How is a $\\sigma$ bond formed?',
  'back': 'By direct (end-on) overlap of orbitals between the bonding atoms, along the line joining the two nuclei.'},
 {'id': 'fc6', 'kc': K(2), 'front': 'How is a $\\pi$ bond formed?',
  'back': 'By the sideways overlap of adjacent p orbitals, giving electron density above and below the $\\sigma$ bond.'},
 {'id': 'fc7', 'kc': K(2), 'front': 'How many $\\sigma$ and $\\pi$ bonds are in a single, double and triple bond?',
  'back': 'Single: $1\\sigma$. Double: $1\\sigma+1\\pi$. Triple: $1\\sigma+2\\pi$. Every bond between two atoms, including every $\\ce{C-H}$ bond, contains one $\\sigma$ bond.'},
 {'id': 'fc8', 'kc': K(2), 'front': 'What hybridisation goes with 4, 3 and 2 $\\sigma$ bonds at a carbon atom?',
  'back': '4 $\\sigma$ bonds: $sp^3$ (tetrahedral, as in $\\ce{C2H6}$). 3 $\\sigma$ bonds: $sp^2$ (planar, as in $\\ce{C2H4}$). 2 $\\sigma$ bonds: sp (linear, as in $\\ce{HCN}$).'},
 {'id': 'fc9', 'kc': K(3), 'front': 'Define bond energy.',
  'back': 'The energy required to break one mole of a particular covalent bond in the gaseous state.'},
 {'id': 'fc10', 'kc': K(3), 'front': 'Define bond length.',
  'back': 'The internuclear distance of two covalently bonded atoms.'},
 {'id': 'fc11', 'kc': K(3), 'front': 'How do bond length, bond energy and reactivity of a covalent molecule go together?',
  'back': 'The shorter the bond, the stronger the electrostatic attraction and the larger the bond energy, so the less readily the bond breaks and the less reactive the molecule.'},
]

# ================================================================ diagram: bond length against bond energy
diagrams = [
 {'file': 'Assets/9701/9701-3.4-bond-length-energy.svg', 'type': 'graph_sketch',
  'params': {'lines': [{'points': [[BL['C#C'], BE['C#C']], [BL['C=C'], BE['C=C']], [BL['C-C'], BE['C-C']]],
                        'label': 'carbon-carbon bonds: triple, double, single', 'style': 'solid'}],
             'xlabel': 'bond length / pm', 'ylabel': 'bond energy / kJ mol^-1',
             'annotations': [{'xy': [BL['C#C'], BE['C#C']], 'text': 'C#C 120 pm, 840', 'xytext': [BL['C#C'] + 4, BE['C#C'] - 90]},
                             {'xy': [BL['C=C'], BE['C=C']], 'text': 'C=C 134 pm, 610', 'xytext': [BL['C=C'] + 4, BE['C=C'] + 60]},
                             {'xy': [BL['C-C'], BE['C-C']], 'text': 'C-C 154 pm, 350', 'xytext': [BL['C-C'] - 26, BE['C-C'] + 80]}],
             'ticks': True}},
]

pack = {
 'subtopic': '9701-3.4', 'spec': '9701', 'version': 1,
 'note': 'Subjects/9701 Chemistry/03 Chemical bonding/3.4 Covalent bonding and coordinate (dative covalent) bonding.md',
 'outline': 'A covalent bond is the electrostatic attraction between the nuclei of two atoms and a shared pair of electrons: single bonds in $\\ce{H2}$, $\\ce{Cl2}$, $\\ce{HCl}$, $\\ce{CH4}$ and $\\ce{C2H6}$, double bonds in $\\ce{O2}$, $\\ce{CO2}$ and $\\ce{C2H4}$, a triple bond in $\\ce{N2}$. Period 3 atoms can expand the octet ($\\ce{SO2}$, $\\ce{PCl5}$, $\\ce{SF6}$). In a coordinate (dative covalent) bond both electrons come from one atom: $\\ce{NH3}$ donates its lone pair to $\\ce{H+}$ to give $\\ce{NH4+}$, and two such bonds hold $\\ce{Al2Cl6}$ together. Orbital overlap splits bonds into $\\sigma$ (direct, end-on overlap) and $\\pi$ (sideways overlap of adjacent p orbitals), so single $=1\\sigma$, double $=1\\sigma+1\\pi$, triple $=1\\sigma+2\\pi$, with sp, $sp^2$ and $sp^3$ hybridisation for 2, 3 and 4 $\\sigma$ bonds. Bond energy (energy to break one mole of a bond in the gaseous state) rises as bond length falls, which sets how reactive a molecule is.',
 'misconceptions': mis, 'worked': worked, 'items': items, 'flashcards': flashcards, 'diagrams': diagrams,
}
OUT.write_text(json.dumps(pack, ensure_ascii=False, indent=1) + '\n')
print(OUT, 'items', len(items), '(past', sum(i['source']['type'] == 'past' for i in items), ')',
      'worked', len(worked), 'flashcards', len(flashcards))
