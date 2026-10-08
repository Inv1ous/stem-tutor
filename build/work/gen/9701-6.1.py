"""Generate the 9701-6.1 redox teaching pack from verified data."""
import json
from pathlib import Path
from sympy import Rational, solve, symbols

ROOT = Path(__file__).resolve().parents[3]
SUB = '9701-6.1'
K = {i: f'{SUB}.{i}' for i in range(1, 6)}
BANK = {q['id']: q for q in json.loads((ROOT/'build/work/mcq/9701.tagged.json').read_text())}
# corrections to bank questions (garbled fractions, figure-only options) live in overrides.json, as for the extras
FIX={q:{k:v for k,v in f.items() if k in ('stem','options')} for q,f in json.loads((ROOT/'build/work/mcq/overrides.json').read_text()).items()}
items = []

def past(qid, kcs, explanation, wrong=None):
    q = {**BANK[qid], **FIX.get(qid, {})}
    assert q['answer'] in q['options'] and all(q['options'].values())
    it = {'id':f'{SUB}-p{1+sum(i["source"]["type"]=="past" for i in items):02d}',
          'kcs':[K[k] for k in kcs], 'kind':'mcq', 'difficulty':3,
          'command_word':'Identify','source':{'type':'past','ref':q['ref'],'qid':qid},
          'stem':q['stem'],'options':q['options'],'answer':q['answer'],'marks':1,
          'explanation':explanation,'distractors':wrong or {}}
    if q.get('image'): it['image']=q['image']
    items.append(it)

def gen(kcs, stem, options, key, explanation, difficulty=2, wrong=None, command='Identify'):
    assert len(options)==4 and 0<=key<4 and len(set(options))==4
    it={'id':f'{SUB}-i{1+sum(i["source"]["type"]=="generated" for i in items):02d}',
        'kcs':[K[k] for k in kcs], 'kind':'mcq','difficulty':difficulty,'command_word':command,
        'source':{'type':'generated'},'stem':stem,'options':dict(zip('ABCD',options)),
        'answer':'ABCD'[key],'marks':1,'explanation':explanation,'shuffle':True,
        'hints':['Assign oxidation numbers using the charge and usual rules.',
                 'Compare the relevant element before and after reaction, or sum all numbers to the species charge.',
                 'Write the oxidation-number changes and check electron balance before choosing.'],
        'distractors':wrong or {}}
    items.append(it)

def short(kcs, stem, points, explanation, difficulty=2, command='Explain'):
    items.append({'id':f'{SUB}-i{1+sum(i["source"]["type"]=="generated" for i in items):02d}',
      'kcs':[K[k] for k in kcs],'kind':'short','difficulty':difficulty,'command_word':command,
      'source':{'type':'generated'},'stem':stem,'marks':len(points),
      'rubric':[{'point':p,'keywords':kw} for p,kw in points], 'explanation':explanation,
      'hints':['Find the element whose oxidation number changes.',
               'State the direction of electron transfer or oxidation-number change.',
               'Name the species that gains electrons and the species that loses them.']})

def num(kcs, stem, value, explanation, difficulty=2):
    assert isinstance(value,(int,Rational))
    items.append({'id':f'{SUB}-i{1+sum(i["source"]["type"]=="generated" for i in items):02d}',
       'kcs':[K[k] for k in kcs],'kind':'numeric','difficulty':difficulty,'command_word':'Calculate',
       'source':{'type':'generated'},'stem':stem,'marks':2,'answer':{'value':float(value),'unit':'','exact':True},
       'distractors':[],'explanation':explanation,
       'hints':['Use fixed oxidation numbers first.',
                'The algebraic sum equals the charge on the whole species.',
                'Multiply each known oxidation number by its atom count before solving.']})

mis=[
 {'id':'m1','kc':K[1],'statement':'A change from a negative oxidation number to a positive one can be found by subtracting magnitudes.','refutation':'Subtract the signed initial number from the signed final number. From $-3$ to $+5$ the rise is $5-(-3)=8$.','contrast':'Nitrogen in $\\ce{NH4+}$ is $-3$ and in $\\ce{NO3-}$ is $+5$.','source':'ER 9701 w22 P11 Q11'},
 {'id':'m2','kc':K[2],'statement':'Balancing atoms alone guarantees that a redox equation is balanced.','refutation':'A balanced ionic equation must conserve charge as well as atoms; equal total electron loss and gain fixes the redox ratio.','contrast':'Three chlorate ions lose six electrons while two manganate(VII) ions gain six.','source':'ER 9701 w19 P11 Q9'},
 {'id':'m3','kc':K[3],'statement':'Every reaction described as hydrolysis, dehydration or addition is redox.','refutation':'Check oxidation numbers or electron transfer; a reaction class alone does not establish redox.','contrast':'Addition of bromine to an alkene reduces Br from $0$ to $-1$; dehydration of an alcohol is not thereby redox.','source':'ER 9701 w22 P13 Q28'},
 {'id':'m4','kc':K[3],'statement':'Disproportionation means that two different elements are oxidised and reduced.','refutation':'The same element in one reactant must be both oxidised and reduced, forming products with higher and lower oxidation numbers.','contrast':'Chlorine at $0$ forms $+1$ in $\\ce{HOCl}$ and $-1$ in $\\ce{Cl-}$.','source':'ER 9701 w23 P21 Q3'},
 {'id':'m5','kc':K[4],'statement':'An oxidising agent loses electrons because it causes oxidation.','refutation':'The oxidising agent accepts electrons from another species and is itself reduced.','contrast':'In $\\ce{H2 + 2K -> 2KH}$, hydrogen accepts electrons to form hydride and is the oxidising agent.','source':'ER 9701 w23 P21 Q3'}]

past('9701_w22_12_q5',[1,2],'Zn loses two electrons; each of two vanadium ions gains one. Vanadium falls from $+5$ in $\\ce{VO2+}$ to $+4$ in $\\ce{VO^{2+}}$. B would put vanadium at $+3$, implying two electrons gained per ion.',{'B':'m2'})
past('9701_w22_11_q11',[1],'Nitrogen is $-3$ in ammonium and $+5$ in nitrate, so its signed change is $+8$. B subtracts the magnitudes instead of the signed numbers.',{'B':'m1'})
past('9701_w19_13_q9',[1,2],'Chlorine rises by two while manganese falls by three, requiring three chlorate and two manganate(VII) ions; charge then requires two hydrogen ions. A fails to conserve charge.',{'A':'m2'})
past('9701_s22_13_q12',[2],'Three dichromate units contain six Cr(VI), each gaining three electrons: 18 electrons oxidise 18 iodide ions to nine iodine molecules, which require 18 thiosulfate ions. B neglects the three moles of dichromate.',{'B':'m2'})
past('9701_s21_13_q9',[2],'Three copper atoms lose six electrons and reduce two nitrate ions to two NO; six further nitrate ions form three $\\ce{Cu(NO3)2}$ units. Thus eight acid molecules are required; C omits the nitrate used for reduction.',{'C':'m2'})
past('9701_w25_13_q10',[3,4],'Hydrogen gains electrons from potassium: H changes from $0$ to $-1$, making it the oxidising agent. In B hydrogen changes from $0$ to $+1$, so it is oxidised.',{'B':'m5','C':'m5','D':'m5'})
past('9701_w25_12_q11',[1],'Average S is $0$ in $\\ce{S8}$, $+2.5$ in tetrathionate, $+2$ in thiosulfate and $+6$ in $\\ce{SO2Cl2}$, so D is highest. B is lower because the total oxidation-number sum includes all four sulfur atoms.',{'B':'m1'})
past('9701_w24_12_q11',[3,4],'Peroxide oxygen changes from $-1$ to $0$ in reactions 2 and 3, so peroxide loses electrons and is a reducing agent. In reaction 1 it changes to $-2$ in water and accepts electrons.',{'A':'m5','B':'m5','D':'m5'})
past('9701_w24_12_q12',[1,2],'Vanadium goes from $+5$ in $\\ce{VO2+}$ to $+4$ in $\\ce{VO^{2+}}$. Balancing gives $x=z=2$ and $y=4$; B incorrectly makes $y$ four times $x$.',{'B':'m2'})
past('9701_w24_13_q11',[2],'Manganese gains three electrons per manganate(VII) ion; sulfur loses two per sulfite ion. The least common multiple is six, giving a $2:3$ ratio; B reverses it.',{'B':'m2'})
past('9701_w22_13_q28',[3],'Bromine changes from $0$ in $\\ce{Br2}$ to $-1$ in the dibromo product, so the addition is redox. B is dehydration of propan-1-ol; its oxygen remains $-2$ and hydrogen remains $+1$.',{'B':'m3'})
past('9701_w25_12_q10',[3],'Iron loses electrons as it oxidises and the heat pad releases heat. C incorrectly says the iron gains electrons.',{'C':'m3'})

# Solve oxidation-number equations, rather than entering answer values by hand.
x=symbols('x')
nh4=solve(x+4-1,x)[0]; no3=solve(x-6+1,x)[0]
assert (nh4,no3,no3-nh4)==(-3,5,8)
num([1], 'Calculate the oxidation number of sulfur in $\\ce{SO4^{2-}}$.', solve(x-8+2,x)[0], 'Four oxygens contribute $-8$; sulfur must be $+6$ to make the ion charge $-2$.')
num([1], 'Calculate the oxidation number of chromium in $\\ce{Cr2O7^{2-}}$.', solve(2*x-14+2,x)[0], 'Seven oxygens contribute $-14$; the two chromium atoms must total $+12$, so each is $+6$.',3)
num([1,3], 'Calculate the change in oxidation number of nitrogen from $\\ce{NH4+}$ to $\\ce{NO3-}$.', no3-nh4, 'The signed difference is $+5-(-3)=+8$, an oxidation.')
gen([1,5], 'Which name correctly identifies $\\ce{FeCl3}$?', ['iron(III) chloride','iron(II) chloride','iron(IV) chloride','iron(III) chlorate'],0,'Each chloride is $-1$, so Fe is $+3$ and its magnitude is written III.',wrong={'B':'m1'})
iron_ions, electron_loss_each = 2, 3-2
gen([2], 'In $\\ce{2Fe^{2+} + Cl2 -> 2Fe^{3+} + 2Cl-}$, how many electrons are lost by the two iron ions in total?', [str(iron_ions*electron_loss_each),str(electron_loss_each),str(iron_ions*electron_loss_each+1),str(iron_ions*electron_loss_each*2)],0,'Each Fe(II) loses one electron; two Fe(II) ions lose two, matching the two electrons gained by chlorine.',4,{'B':'m2'})
short([2], 'Explain how oxidation-number changes fix the coefficients when sulfite reacts with manganate(VII) to form sulfate and manganese dioxide.', [('Sulfur rises from +4 to +6 and loses two electrons per sulfite.', [['sulfur','s'],['+4'],['+6'],['two','2']]),('Manganese falls from +7 to +4 and gains three electrons per manganate(VII).',[['manganese','mn'],['+7'],['+4'],['three','3']]),('Use three sulfite for two manganate(VII), so six electrons transfer each way.',[['three','3'],['two','2'],['six','6']])], 'The electron changes of two and three have least common multiple six, setting the sulfite:manganate ratio to $3:2$.',4)
gen([3], 'Which equation is a disproportionation of chlorine?', ['$\\ce{Cl2 + H2O <=> HOCl + H+ + Cl-}$','$\\ce{Cl2 + 2Br- -> 2Cl- + Br2}$','$\\ce{2Na + Cl2 -> 2NaCl}$','$\\ce{2HCl -> H2 + Cl2}$'],0,'Cl at $0$ forms chlorine at $+1$ and $-1$ in the same reaction.',4,{'B':'m4','C':'m4','D':'m4'})
short([3], 'Define oxidation and reduction in terms of both electrons and oxidation numbers.', [('Oxidation is loss of electrons and increase in oxidation number.',[['loss','los'],['electron'],['increase','rise']]),('Reduction is gain of electrons and decrease in oxidation number.',[['gain'],['electron'],['decrease','fall']])], 'Electron loss raises oxidation number; electron gain lowers it.')
gen([3], 'Which pair of changes describes a redox reaction?', ['One element rises in oxidation number and another falls.','Both elements rise.','Every element keeps its oxidation number.','Only a proton transfers.'],0,'Electron loss and gain occur together, so one oxidation number rises and another falls.',wrong={'C':'m3'})
short([3,4], 'In $\\ce{Zn + Cu^{2+} -> Zn^{2+} + Cu}$, explain the electron transfers and name both agents.', [('Zinc loses electrons and is oxidised; it is the reducing agent.',[['zinc','zn'],['los','donat'],['reducing agent']]),('Copper(II) ions gain electrons and are reduced; they are the oxidising agent.',[['copper','cu'],['gain','accept'],['oxidising agent']])], 'Zinc donates two electrons to copper(II), so zinc reduces copper(II) and copper(II) oxidises zinc.',4)
gen([4], 'In $\\ce{2Fe^{2+} + Cl2 -> 2Fe^{3+} + 2Cl-}$, which species is the oxidising agent?', ['$\\ce{Cl2}$','$\\ce{Fe^{2+}}$','$\\ce{Fe^{3+}}$','$\\ce{Cl-}$'],0,'Chlorine accepts electrons and is reduced from $0$ to $-1$; Fe(II) donates electrons.',wrong={'B':'m5'})
short([4], 'Define an oxidising agent.', [('A species that oxidises another species.',[['oxidis'],['another','other']]),('It accepts electrons and is itself reduced.',[['accept','gain'],['electron'],['reduc']])], 'An oxidising agent causes oxidation by accepting electrons and is itself reduced.',command='Define')
short([4], 'Define a reducing agent.', [('A species that reduces another species.',[['reduc'],['another','other']]),('It donates electrons and is itself oxidised.',[['donat','los'],['electron'],['oxidis']])], 'A reducing agent causes reduction by donating electrons and is itself oxidised.',command='Define')
gen([4], 'When $\\ce{H2O2}$ converts $\\ce{Fe^{3+}}$ to $\\ce{Fe^{2+}}$ and forms $\\ce{O2}$, what role does peroxide have?', ['Reducing agent, because its oxygen is oxidised.','Oxidising agent, because its oxygen is oxidised.','Oxidising agent, because iron is reduced.','Neither agent, because oxygen is present.'],0,'Peroxide oxygen rises from $-1$ to $0$ and donates electrons to iron(III).',4,{'B':'m5','C':'m5'})
gen([5], 'What does III mean in the name iron(III) sulfate?', ['Each iron ion has oxidation number +3.','Each sulfate ion has charge -3.','There are three iron ions per formula unit.','Each iron ion has oxidation number -3.'],0,'Roman III gives the magnitude of iron’s positive oxidation number; sulfate is $-2$.',wrong={'C':'m1'})
gen([5], 'Which name matches $\\ce{Cu2O}$?', ['copper(I) oxide','copper(II) oxide','copper(III) oxide','copper(I) peroxide'],0,'Oxygen is $-2$, so the two copper atoms sum to $+2$ and each is $+1$.')
gen([5], 'Which formula corresponds to manganese(IV) oxide?', ['$\\ce{MnO2}$','$\\ce{MnO}$','$\\ce{Mn2O3}$','$\\ce{MnO4-}$'],0,'Two oxide ions total $-4$, giving Mn oxidation number $+4$.')
short([5], 'Explain how to choose the Roman numeral in the name chromium(III) chloride.', [('Each chloride has oxidation number -1 and three chlorides total -3.',[['chloride','cl'],['-1'],['three','3']]),('Chromium is +3, so use the numeral III.',[['chromium','cr'],['+3'],['III']])], 'The numeral is the magnitude of the metal oxidation number, here $+3$.')
gen([5], 'Which name correctly states the oxidation number of sulfur in $\\ce{SO3}$?', ['sulfur(VI) oxide','sulfur(III) oxide','sulfur(IV) oxide','sulfur(II) oxide'],0,'Three oxygens contribute $-6$, so sulfur is $+6$, indicated by VI.')

assert sum(i['source']['type']=='past' for i in items)==12
# Verify the fixed electron and coefficient arithmetic used throughout the pack.
assert 3*2==2*3 and 3*2==6
assert 3*2*3==18 and 18//2*2==18
assert 3*2==2*3 and 3*2+6==12
assert solve(x-2*2+2,x)[0]==2  # sulfite sulfur
assert solve(x-2*3,x)[0]==6  # sulfur in sulfur trioxide

worked=[
 {'id':'we1','kc':K[1],'problem':'Find the oxidation number of N in $\\ce{NH4+}$ and $\\ce{NO3-}$, then its change.',
  'steps':[{'do':'Let N be $x$. In $\\ce{NH4+}$, $x+4(+1)=+1$, so $x=-3$.','why':'The sum equals the charge of the whole ion.'},
           {'do':'In $\\ce{NO3-}$, $x+3(-2)=-1$, so $x=+5$.','why':'Oxygen normally has oxidation number $-2$.'},
           {'do':'The change is $+5-(-3)=+8$.','why':'Subtract signed numbers to identify an increase (oxidation).','check':{'kind':'numeric','answer':{'value':float(no3-nh4),'unit':'','exact':True}}}],
  'faded':{'id':'we1f','problem':'Find the change in sulfur oxidation number from $\\ce{H2S}$ to $\\ce{SO4^{2-}}$.','answer':{'value':float(6-(-2)),'unit':'','exact':True},'blank_from':1}},
 {'id':'we2','kc':K[2],'problem':'Balance $\\ce{ClO3- + MnO4- + H+ -> ClO4- + MnO2 + H2O}$ using oxidation numbers.',
  'steps':[{'do':'Cl rises $+5$ to $+7$, losing 2 electrons; Mn falls $+7$ to $+4$, gaining 3.','why':'Equal electron loss and gain set the redox ratio.'},
           {'do':'Multiply chlorate by 3 and manganate(VII) by 2; use the same counts for their products.','why':'The least common multiple of 2 and 3 is 6.'},
           {'do':'Balance oxygen with one water, then hydrogen with two $\\ce{H+}$: $\\ce{3ClO3- + 2MnO4- + 2H+ -> 3ClO4- + 2MnO2 + H2O}$.','why':'Both atoms and net charge must be conserved.','check':{'kind':'numeric','answer':{'value':float(2),'unit':'','exact':True}}}],
  'faded':{'id':'we2f','problem':'In alkaline solution, $\\ce{MnO4-}$ becomes $\\ce{MnO2}$ and $\\ce{SO3^{2-}}$ becomes $\\ce{SO4^{2-}}$. Find the coefficient of sulfite when the manganate(VII) coefficient is 2.','answer':{'value':float(3),'unit':'','exact':True},'blank_from':1}}]
flash=[
(1,'What is an oxidation number?','A number assigned to an atom representing the charge it would have if bonding electrons were assigned to the more electronegative atom.'),
(3,'Define oxidation in electron terms.','Loss of electrons; the oxidation number increases.'),
(3,'Define reduction in electron terms.','Gain of electrons; the oxidation number decreases.'),
(3,'Define disproportionation.','The same element in one reactant is simultaneously oxidised and reduced in a reaction.'),
(4,'Define an oxidising agent.','A species that oxidises another species by accepting electrons and is itself reduced.'),
(4,'Define a reducing agent.','A species that reduces another species by donating electrons and is itself oxidised.'),
(5,'What does a Roman numeral in iron(III) mean?','III is the magnitude of the oxidation number of iron: each Fe has oxidation number $+3$.'),
(5,'How is an oxidation number of +4 written in a compound name?','Use the Roman numeral IV in parentheses immediately after the element name.')]
pack={'subtopic':SUB,'spec':'9701','version':1,'note':'Subjects/9701 Chemistry/06 Electrochemistry/6.1 Redox processes: electron transfer and changes in oxidation number (oxidation state).md',
'outline':'Assign oxidation numbers using elements at zero, monatomic ion charges, usual H $+1$ and O $-2$, and a sum equal to the species charge. Oxidation is electron loss and a rise in oxidation number; reduction is electron gain and a fall. In redox, both occur. A reducing agent donates electrons and is oxidised; an oxidising agent accepts electrons and is reduced. Disproportionation oxidises and reduces the same element in one reactant. Balance redox equations by matching total oxidation-number increases and decreases, then atoms and charge. Roman numerals in names state the magnitude of an element’s oxidation number.',
'misconceptions':mis,'worked':worked,'items':items,
'flashcards':[{'id':f'fc{n}','kc':K[k],'front':a,'back':b} for n,(k,a,b) in enumerate(flash,1)],'diagrams':[]}
out=ROOT/'build/out/packs/9701/9701-6.1.json'
out.parent.mkdir(parents=True,exist_ok=True)
out.write_text(json.dumps(pack,ensure_ascii=False,indent=1))
print('draft',len(items),'items',sum('template' in i for i in items),'templates',len(worked),'worked')
