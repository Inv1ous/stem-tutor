"""Generate the 9701-13.2 pack from checked text and the official tagged MCQs."""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
SUB = '9701-13.2'
K1, K2 = SUB + '.1', SUB + '.2'
NOTE = 'Subjects/9701 Chemistry/13 An introduction to AS Level organic chemistry/13.2 Characteristic organic reactions.md'

mis = [
    dict(id='m1', kc=K1, statement='Homolytic fission produces ions.', refutation='Each atom receives one bonding electron, forming radicals; heterolytic fission produces ions.', contrast='Homolytic: one electron each. Heterolytic: both electrons to one atom.', source='research'),
    dict(id='m2', kc=K2, statement='Every nucleophile is negatively charged.', refutation='A neutral molecule with a lone pair, such as ammonia, can donate that pair.', contrast='Electron-pair donation defines a nucleophile, not charge.', source='research'),
    dict(id='m3', kc=K2, statement='A curly arrow can start at an electrophilic atom.', refutation='A full curly arrow traces an electron pair from its source: a bond or lone pair.', contrast='Start at the electron pair and point towards its destination.', source='ER 9701 s22 P23 Q4'),
    dict(id='m4', kc=K2, statement='Cyanide addition to a carbonyl first makes a positive carbonyl intermediate.', refutation='The carbon nucleophile attacks the carbonyl carbon while the C=O pair moves to oxygen, giving an alkoxide.', contrast='Show the C=O polarity and arrows from the cyanide lone pair and C=O bond.', source='ER 9701 s23 P23 Q6'),
]

def short(n, kc, command, stem, points, explanation, difficulty=2):
    return dict(id=f'{SUB}-i{n:02d}', kcs=[kc], kind='short', difficulty=difficulty,
                command_word=command, source={'type':'generated'}, stem=f'{command} {stem}',
                marks=len(points), rubric=[{'point':p,'keywords':keys} for p,keys in points],
                explanation=explanation,
                hints=['Recall the precise syllabus terminology.', 'Identify what changes in bonds or electrons.', 'Start with the defining feature of the named process.'])

items = [
 short(1,K1,'Define','homologous series.', [('A family with the same functional group and general formula.', [['same functional group'],['general formula']]),('Successive members differ by $\\ce{CH2}$.',[['successive'],['CH2']])], 'Members have the same functional group and general formula, and consecutive members differ by $\\ce{CH2}$.',1),
 short(2,K1,'Compare','saturated and unsaturated organic compounds.', [('Saturated compounds contain only single carbon–carbon bonds.', [['single'],['carbon']]),('Unsaturated compounds contain a carbon–carbon multiple bond.', [['multiple','double','triple'],['carbon']])], 'Saturation refers to carbon–carbon bonds: an unsaturated compound has a C=C or C≡C bond.'),
 short(3,K1,'Contrast','homolytic and heterolytic fission of a covalent bond.', [('Homolysis gives one bonding electron to each atom, forming radicals.', [['one'],['each'],['radical']]),('Heterolysis gives both bonding electrons to one atom, forming ions.', [['both'],['one atom'],['ion']])], 'Homolysis splits the pair equally; heterolysis transfers the pair to one fragment.'),
 short(4,K1,'Describe','initiation, propagation and termination in free-radical substitution.', [('Initiation generates radicals by homolytic fission.', [['radical'],['homolytic']]),('Propagation uses a radical and regenerates a radical.', [['radical'],['regenerat','another']]),('Termination combines radicals so no radical remains.', [['combine','react'],['no radical','radical removed']])], 'Initiation creates radicals, propagation sustains the chain, and termination removes radicals.',4),
 short(5,K1,'Define','nucleophile and electrophile.', [('A nucleophile donates an electron pair.', [['electron pair'],['donat']]),('An electrophile accepts an electron pair.', [['electron pair'],['accept']])], 'The two terms describe electron-pair donors and acceptors.'),
 short(6,K1,'Explain','the difference between addition, substitution and elimination reactions.', [('Addition combines reactants into one product.', [['one product'],['add','combin']]),('Substitution replaces an atom or group.', [['replac'],['atom','group']]),('Elimination removes atoms or groups and forms a multiple bond.', [['remov'],['multiple bond','double bond']])], 'Addition joins, substitution replaces, and elimination removes groups, commonly creating a multiple bond.',4),
 short(7,K1,'Describe','hydrolysis and condensation, and state the meanings of oxidation and reduction in organic chemistry.', [('Hydrolysis breaks a bond by reaction with water.', [['water'],['break']]),('Condensation joins molecules with loss of a small molecule.', [['join'],['small molecule','water']]),('Oxidation involves gain of oxygen or loss of hydrogen.', [['oxygen','hydrogen'],['gain','loss']]),('Reduction involves loss of oxygen or gain of hydrogen.', [['oxygen','hydrogen'],['gain','loss']])], 'Hydrolysis uses water to split; condensation joins with elimination. Organic oxidation can be represented by $[O]$, reduction by $[H]$.',4),
 short(8,K2,'Describe','free-radical substitution of an alkane with chlorine.', [('Initiation: UV light causes homolytic fission of $\\ce{Cl2}$.',[['UV'],['homolytic']]),('Propagation: a chlorine radical removes H and the alkyl radical reacts with chlorine.', [['hydrogen','H'],['alkyl radical']]),('Termination: two radicals combine.', [['radical'],['combine']])], 'The chain starts with chlorine radicals, continues through radical-producing steps, and stops when radicals combine.',4),
 short(9,K2,'Explain','why addition of HCl to an alkene is electrophilic addition.', [('The electron-rich π bond attacks the electrophilic hydrogen.', [['pi','π'],['hydrogen','H']]),('The C=C bond becomes a C–C single bond as H and Cl add.', [['single'],['add']])], 'The π electrons attack the H of HCl, and chloride subsequently attacks the carbocation.',4),
 short(10,K2,'Describe','nucleophilic substitution of a halogenoalkane with cyanide ions.', [('The cyanide ion donates a lone pair from carbon to the carbon bearing halogen.', [['cyanide','CN'],['lone pair']]),('The C–halogen bond breaks and the halide leaves.', [['bond'],['halide','halogen']])], 'Cyanide replaces halide; the nucleophile supplies the electron pair for the new C–C bond.',3),
 short(11,K2,'Describe','nucleophilic addition of cyanide to a carbonyl compound.', [('The carbonyl C is partially positive and is attacked by the carbon lone pair of cyanide.', [['carbonyl'],['cyanide','CN'],['lone pair']]),('The C=O electron pair moves to oxygen, forming an alkoxide.', [['oxygen'],['alkoxide','negative']]),('Protonation of the alkoxide forms a hydroxynitrile.', [['proton'],['hydroxynitrile','OH']])], 'The nucleophile adds across C=O; protonation gives the alcohol group.',4),
 short(12,K2,'Explain','where a full curly arrow begins in an organic mechanism.', [('It begins at a bond or lone pair of electrons.', [['bond','lone pair']]),('It points to where that electron pair moves.', [['electron pair'],['moves','destination']])], 'A full curly arrow represents movement of an electron pair from a bond or lone pair.',2),
]

bank = {q['id']:q for q in json.loads((ROOT/'build/work/mcq/9701.tagged.json').read_text())}
past = [
 ('9701_w24_12_q28','A nucleophile donates a lone pair; it need not carry a negative charge, so D is wrong.',{'D':'m2'}),
 ('9701_w21_12_q21','Homolytic fission gives neutral radicals; a bromine radical has the 35 electrons of a neutral bromine atom, so C is wrong.',{'B':'m1','D':'m1'}),
 ('9701_s22_12_q27','The cation has six electrons around carbon, the radical seven and the anion eight; B swaps the radical and nucleophile.',{}),
 ('9701_s20_12_q22','Cyanide replaces bromide in the first reaction; cyanide adds to the carbonyl in the second. C incorrectly makes the second reaction electrophilic.',{}),
 ('9701_s20_11_q31','First ionisation forms a cation and heterolytic fission can form a cation; atomisation forms gaseous atoms, so a choice including 3 is wrong.',{}),
]
for i,(qid,explanation,distractors) in enumerate(past,1):
    q=bank[qid]
    items.append(dict(id=f'{SUB}-p{i:02d}',kcs=[K2],kind='mcq',difficulty=3,command_word=None,
        source={'type':'past','ref':q['ref'],'qid':qid},stem=q['stem'],options=q['options'],
        answer=q['answer'],image=q.get('image'),marks=1,explanation=explanation,
        distractors=distractors,hints=['Identify the electron movement or species.','Apply the formal definition to each option.','Eliminate the option that contradicts the defining electron count or mechanism.']))

flash = [
 ('homologous series','A family of organic compounds with the same functional group and general formula; successive members differ by $\\ce{CH2}$.'),
 ('saturated and unsaturated','Saturated: contains only carbon–carbon single bonds. Unsaturated: contains a carbon–carbon double or triple bond.'),
 ('homolytic and heterolytic fission','Homolytic: each atom receives one electron from the bond, forming radicals. Heterolytic: one atom receives both bonding electrons, forming ions.'),
 ('free radical','A species with an unpaired electron.'),
 ('nucleophile and electrophile','A nucleophile donates an electron pair; an electrophile accepts an electron pair.'),
 ('addition, substitution and elimination','Addition combines reactants into one product; substitution replaces an atom or group; elimination removes atoms or groups, usually forming a multiple bond.'),
 ('hydrolysis and condensation','Hydrolysis breaks a bond by reaction with water. Condensation joins molecules with loss of a small molecule, often water.'),
 ('organic oxidation and reduction','Oxidation is gain of oxygen or loss of hydrogen; reduction is loss of oxygen or gain of hydrogen. $[O]$ and $[H]$ each represent one atom supplied by the appropriate reagent.'),
]
flashcards=[dict(id=f'fc{i}',kc=K1,front=f'Define {term}.',back=back) for i,(term,back) in enumerate(flash,1)]
pack=dict(subtopic=SUB,spec='9701',version=1,note=NOTE,
 outline='Identify the reaction by what changes: addition, substitution, elimination, hydrolysis, condensation or redox. Follow electron movement to classify the mechanism. Homolysis creates radicals; heterolysis creates ions. Nucleophiles donate electron pairs and electrophiles accept them. In a full curly-arrow mechanism, every arrow begins at the source bond or lone pair.',
 misconceptions=mis,worked=[],items=items,flashcards=flashcards,diagrams=[])
out=ROOT/'build/out/packs/9701'/f'{SUB}.json'
out.write_text(json.dumps(pack,ensure_ascii=False,indent=1))
print(out)
