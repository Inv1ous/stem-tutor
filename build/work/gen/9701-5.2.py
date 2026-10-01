"""Generate Hess's law chapter. Fixed and parametric arithmetic is evaluated here."""
import json
from pathlib import Path
from sympy import Rational, sympify

ROOT=Path(__file__).resolve().parents[3]
SUB='9701-5.2'
K={1:SUB+'.1',2:SUB+'.2'}
BANK={q['id']:q for q in json.loads((ROOT/'build/work/mcq/9701.tagged.json').read_text())}
items=[]

def calc(expr,**values):
    return float(sympify(expr,locals={k:Rational(str(v)) for k,v in values.items()}))

# Audit every fixed numerical result used in the explanations and worked steps.
assert calc('52.2-(-175.8)')==228
assert round(calc('4*(-241.8)-(2*50.6+9.2)'),1)==-1077.6
assert calc('2*32.8-(-34.0)')==99.6
assert calc('(698-(-602+88))/6')==202
assert calc('(-276-335)-25.9')==-636.9
assert round(calc('(-601.7-393.5)-(-1095.8)'),1)==100.6
assert calc('-(6*(1648/4)+350)')==-2822
assert calc('4*(-394)+5*(-286)-(-129)')==-2877
assert calc('2*(-573)-3*(-452)')==210
assert calc('(-394+2*(-286))-(-726)')==-240
assert round(calc('4*90.3+6*(-241.8)-4*(-46.1)'),1)==-905.2

mis=[
 dict(id='m1',kc=K[1],statement='Reverse a cycle arrow without changing its enthalpy sign.',refutation='Reversing a reaction changes the sign of its enthalpy change.',contrast='If $A\\to B$ is $-50$ kJ mol$^{-1}$, $B\\to A$ is $+50$ kJ mol$^{-1}$.',source='ER 9701 w23 P22 Q3'),
 dict(id='m2',kc=K[2],statement='Ignore equation coefficients when combining enthalpy changes.',refutation='Multiplying an equation multiplies its enthalpy change by the same factor.',contrast='Two moles of water formed contribute twice $\\Delta H_f^\\ominus(\\ce{H2O})$.',source='ER 9701 w23 P22 Q3'),
 dict(id='m3',kc=K[2],statement='Add reactant and product formation enthalpies.',refutation='For a formation cycle, subtract the total formation enthalpy of reactants from that of products.',contrast='$\\Delta H_r^\\ominus=\\sum\\Delta H_f^\\ominus(\\text{products})-\\sum\\Delta H_f^\\ominus(\\text{reactants})$.',source='ER 9701 w23 P22 Q3'),
 dict(id='m4',kc=K[2],statement='Treat bond energies as energies released on breaking bonds.',refutation='Bond breaking absorbs energy; bond formation releases it. Use broken minus formed, with gaseous species.',contrast='For $\\ce{H2 + Cl2 -> 2HCl}$, use $E(\\ce{H-H})+E(\\ce{Cl-Cl})-2E(\\ce{H-Cl})$.',source='ER 9701 w23 P22 Q3'),
 dict(id='m5',kc=K[1],statement='An element in its standard state has a nonzero standard enthalpy of formation.',refutation='Its formation reaction makes the same substance from itself, so its standard enthalpy of formation is zero.',contrast='$\\Delta H_f^\\ominus(\\ce{O2(g)})=0$; an oxygen bond energy is not needed in a formation-enthalpy cycle.',source='ER 9701 w22 P13 Q9'),
]

def past(qid,kcs,explanation,wrong=None):
 q=BANK[qid]; n=1+sum(x['source']['type']=='past' for x in items)
 it=dict(id=f'{SUB}-p{n:02d}',kcs=[K[k] for k in kcs],kind='mcq',difficulty=3,command_word='Calculate',source={'type':'past','ref':q['ref'],'qid':qid},stem=q['stem'],options=q['options'],answer=q['answer'],marks=1,explanation=explanation)
 if q.get('image'):it['image']=q['image']
 if wrong:it['distractors']=wrong
 items.append(it)

def gen(kind,kcs,stem,explanation,**kw):
 n=1+sum(x['source']['type']=='generated' for x in items)
 it=dict(id=f'{SUB}-i{n:02d}',kcs=[K[k] for k in kcs],kind=kind,difficulty=kw.pop('difficulty',3),command_word=kw.pop('command_word','Calculate'),source={'type':'generated'},stem=stem,marks=kw.pop('marks',1),explanation=explanation,hints=['Identify the starting and finishing chemical states.','Draw two routes between the same states and label each arrow.','Reverse arrows with a sign change and scale enthalpies with equation coefficients.'])
 it.update(kw);items.append(it)

def numeric(kcs,stem,params,expr,wrong,explanation,difficulty=3):
 # Evaluate all representative choices, including each distractor, before emitting a template.
 vals={k:v['choices'][0] for k,v in params.items()}
 ans=calc(expr,**vals)
 for e,m in wrong:
  assert m in {x['id'] for x in mis}
  assert abs(calc(e,**vals)-ans)>0.02*max(abs(ans),1e-12)
 gen('numeric',kcs,stem,explanation,difficulty=difficulty,marks=3,answer={'unit':'kJ mol^-1','sf_ok':[2,3,4]},template={'params':params,'answer':expr,'distractors':[{'expr':e,'misconception':m} for e,m in wrong],'constraints':['1>0']})

past('9701_s19_11_q8',[1,2],'Reverse the second equation: $52.2-(-175.8)=+228.0$ kJ mol$^{-1}$. A reverses the final sign.',{'A':'m1'})
past('9701_w19_11_q7',[2],'Products minus reactants gives $4(-241.8)-[2(50.6)+9.2]=-1077.6$ kJ mol$^{-1}$. B misses a coefficient in the cycle.',{'B':'m2'})
past('9701_s20_13_q4',[1,2],'Twice the hydrogencarbonate reaction, then reverse the carbonate reaction: $2(32.8)-(-34.0)=99.6$ kJ mol$^{-1}$. C omits the reversed carbonate step.',{'C':'m1'})
past('9701_w20_11_q7',[1,2],'The atomisation route requires $698$ kJ and formation of two liquid products releases $602$ kJ; vaporising them requires $88$ kJ. The gaseous product to atoms step is $698-(-602+88)=1212$ kJ for six Br–F bonds, or $202$ kJ mol$^{-1}$. C uses an incorrect cycle sign.',{'C':'m1'})
past('9701_s21_13_q7',[1,2],'Hydrate the gaseous ions, then reverse dissolution: $-276-335-25.9=-636.9$ kJ mol$^{-1}$. B adds dissolution instead of reversing it.',{'B':'m1'})
past('9701_s21_13_q8',[1],'The marked route forms two moles of liquid water from its elements, so its enthalpy is twice the formation enthalpy of water. C reverses that arrow.',{'C':'m1'})
past('9701_s22_13_q10',[2],'Products minus reactant is $-601.7-393.5-(-1095.8)=+100.6$ kJ mol$^{-1}$. C omits the product formation terms.',{'C':'m3'})
past('9701_w22_12_q16',[2],'Methane atomisation gives $E(\\ce{C-H})=1648/4=412$ kJ mol$^{-1}$; forming six C–H and one C–C bond gives $-[6(412)+350]=-2822$ kJ mol$^{-1}$. C omits two C–H bonds.',{'C':'m2'})
past('9701_w24_13_q9',[1,2],'Combust the elements to the same products: $4(-394)+5(-286)-(-129)=-2877$ kJ mol$^{-1}$. C adds the formation enthalpy rather than reversing that route.',{'C':'m1'})
past('9701_w24_12_q10',[2],'$2(-573)-3(-452)=+210$ kJ mol$^{-1}$; vanadium metal has zero formation enthalpy. A reverses the overall sign.',{'A':'m3'})
past('9701_s25_12_q6',[1,2],'Element combustion totals $-394+2(-286)=-966$ kJ mol$^{-1}$. Hence methanol formation is $-966-(-726)=-240$ kJ mol$^{-1}$; D loses the sign.',{'D':'m1'})
past('9701_s25_13_q6',[2],'Use formation enthalpies and the balanced coefficients: $4(90.3)+6(-241.8)-4(-46.1)=-905.2$ kJ mol$^{-1}$. A reverses the sign.',{'A':'m3'})

gen('mcq',[1],'A cycle gives $A\\to B=-80$ kJ mol$^{-1}$. What is the enthalpy change of $B\\to A$?','A reversed path has the opposite sign.',options={'A':'$-160$ kJ mol$^{-1}$','B':'$-80$ kJ mol$^{-1}$','C':'$+80$ kJ mol$^{-1}$','D':'$+160$ kJ mol$^{-1}$'},answer='C',distractors={'B':'m1'},shuffle=True,command_word='Determine')
gen('mcq',[1],'In a formation-enthalpy cycle for $\\ce{2NO(g) + O2(g) -> 2NO2(g)}$, which starting level is used?','Both routes start from the elements in their standard states, with enough material to form two moles of nitrogen dioxide.',options={'A':'$\\ce{N2(g) + 2O2(g)}$','B':'$\\ce{2N(g) + 4O(g)}$','C':'$\\ce{N2(g) + O2(g)}$','D':'$\\ce{2NO(g) + O2(g)}$'},answer='A',distractors={'B':'m5','C':'m2'},shuffle=True,command_word='Identify')
gen('short',[1],'Explain Hess’s law and why two routes between identical chemical states have the same total enthalpy change.','Enthalpy is a state function, so total enthalpy change depends only on initial and final states, provided physical states and conditions are the same.',marks=2,command_word='Explain',difficulty=4,rubric=[{'point':'Enthalpy change is independent of the route taken.','keywords':[['independent','does not depend'],['route','path']]},{'point':'The initial and final chemical states must be the same.','keywords':[['initial','start'],['final','end'],['state']]}])
numeric([1,2],'For $\\ce{A -> C}$, the route $\\ce{A -> B}$ is [[ab]] and $\\ce{B -> C}$ is [[bc]] kJ mol$^{-1}$. Calculate the direct enthalpy change.',{'ab':{'choices':[-80,-100,-120]},'bc':{'choices':[30,40,50]}},'ab+bc',[('ab-bc','m1'),('-ab-bc','m1')],'Add signed enthalpy changes along the route from A to C.',4)
numeric([2],'For $\\ce{X2 -> 2X}$, the enthalpy is [[atom]] kJ mol$^{-1}$. For $\\ce{2X + Y2 -> 2XY}$, the enthalpy is [[form]] kJ mol$^{-1}$. Calculate $\\Delta H$ for $\\ce{X2 + Y2 -> 2XY}$.',{'atom':{'choices':[100,120,140]},'form':{'choices':[-200,-240,-280]}},'atom+form',[('atom-form','m1'),('form/2+atom','m2')],'Combine the two equations in the direction written and add their enthalpies.',4)
numeric([2],'For $\\ce{2NO(g) + O2(g) -> 2NO2(g)}$, $\\Delta H_f^\\ominus(\\ce{NO})=[[no]]$ and $\\Delta H_f^\\ominus(\\ce{NO2})=[[no2]]$ kJ mol$^{-1}$. Calculate $\\Delta H_r^\\ominus$.',{'no':{'choices':[80,90,100]},'no2':{'choices':[20,30,40]}},'2*no2-2*no',[('no2-no','m2'),('2*no2+2*no','m3')],'Subtract the reactant formation total from the product formation total; oxygen contributes zero.',4)
numeric([2],'Estimate $\\Delta H$ for $\\ce{H2(g) + Cl2(g) -> 2HCl(g)}$ from H–H = [[hh]], Cl–Cl = [[cc]], and H–Cl = [[hc]] kJ mol$^{-1}$.',{'hh':{'choices':[430,436,440]},'cc':{'choices':[240,242,244]},'hc':{'choices':[425,430,435]}},'hh+cc-2*hc',[('2*hc-hh-cc','m4'),('hh+cc-hc','m2')],'Break one H–H and one Cl–Cl; form two H–Cl bonds. Subtract energies of bonds formed.',4)

worked=[
 {'id':'we1','kc':K[1],'problem':'Find $\\Delta H$ for $\\ce{C(s) + 1/2O2(g) -> CO(g)}$ from $\\Delta H_c^\\ominus(\\ce{C})=-394$ and $\\Delta H_c^\\ominus(\\ce{CO})=-283$ kJ mol$^{-1}$.','steps':[{'do':'Draw both routes from $\\ce{C(s) + O2(g)}$ to $\\ce{CO2(g)}$.','why':'The common end state lets Hess’s law compare the two paths.'},{'do':'Write $\\Delta H_f^\\ominus(\\ce{CO})+(-283)=-394$.','why':'The second leg is combustion of CO in the forward direction.'},{'do':'$\\Delta H_f^\\ominus(\\ce{CO})=-394-(-283)=-111$ kJ mol$^{-1}$.','why':'Subtract the CO combustion leg to isolate the target arrow.','check':{'kind':'numeric','answer':{'value':calc('-394-(-283)'),'unit':'kJ mol^-1','sf_ok':[2,3,4]}}}], 'faded':{'id':'we1f','problem':'Use $\\Delta H_c^\\ominus(\\ce{C})=-394$ and $\\Delta H_c^\\ominus(\\ce{CO})=-280$ kJ mol$^{-1}$ to find formation enthalpy of CO(g).','answer':{'value':calc('-394-(-280)'),'unit':'kJ mol^-1','sf_ok':[2,3,4]},'blank_from':1}},
 {'id':'we2','kc':K[2],'problem':'Calculate $\\Delta H$ for $\\ce{2NO(g) + O2(g) -> 2NO2(g)}$ if formation enthalpies of NO and NO₂ are $+90$ and $+33$ kJ mol$^{-1}$.','steps':[{'do':'Write $\\Delta H_r^\\ominus=\\sum\\Delta H_f^\\ominus(\\text{products})-\\sum\\Delta H_f^\\ominus(\\text{reactants})$.','why':'Both routes connect the elements and the reaction species.'},{'do':'Substitute $2(33)-[2(90)+0]$.','why':'The coefficient two applies to both oxides; standard oxygen has zero formation enthalpy.'},{'do':'$\\Delta H_r^\\ominus=-114$ kJ mol$^{-1}$.','why':'Products minus reactants gives the signed answer for the equation as written.','check':{'kind':'numeric','answer':{'value':calc('2*33-2*90'),'unit':'kJ mol^-1','sf_ok':[2,3,4]}}}], 'faded':{'id':'we2f','problem':'For the same reaction, use $\\Delta H_f^\\ominus(\\ce{NO})=+91$ and $\\Delta H_f^\\ominus(\\ce{NO2})=+34$ kJ mol$^{-1}$. Calculate $\\Delta H_r^\\ominus$.','answer':{'value':calc('2*34-2*91'),'unit':'kJ mol^-1','sf_ok':[2,3,4]},'blank_from':1}},
 {'id':'we3','kc':K[2],'problem':'Estimate $\\Delta H$ for $\\ce{H2(g)+Cl2(g)->2HCl(g)}$ using H–H 436, Cl–Cl 242, H–Cl 431 kJ mol$^{-1}$.','steps':[{'do':'Broken bonds: $436+242=678$ kJ mol$^{-1}$.','why':'Breaking reactant bonds absorbs energy.'},{'do':'Formed bonds: $2(431)=862$ kJ mol$^{-1}$.','why':'The balanced equation makes two H–Cl bonds.'},{'do':'$\\Delta H=678-862=-184$ kJ mol$^{-1}$.','why':'Bond formation releases energy, so subtract its total.','check':{'kind':'numeric','answer':{'value':calc('436+242-2*431'),'unit':'kJ mol^-1','sf_ok':[2,3,4]}}}], 'faded':{'id':'we3f','problem':'For the same reaction use H–H 440, Cl–Cl 240, H–Cl 430 kJ mol$^{-1}$. Estimate $\\Delta H$.','answer':{'value':calc('440+240-2*430'),'unit':'kJ mol^-1','sf_ok':[2,3,4]},'blank_from':1}}
]
flashcards=[{'id':'fc1','kc':K[1],'front':'State Hess’s law.','back':'The enthalpy change of a reaction is independent of the route taken, provided initial and final conditions are the same.'},{'id':'fc2','kc':K[2],'front':'What is the formation-enthalpy cycle formula?','back':'$\\Delta H_r^\\ominus=\\sum\\Delta H_f^\\ominus(\\text{products})-\\sum\\Delta H_f^\\ominus(\\text{reactants})$, using stoichiometric coefficients.'},{'id':'fc3','kc':K[2],'front':'What is the bond-energy estimate?','back':'$\\Delta H\\approx\\sum E(\\text{bonds broken})-\\sum E(\\text{bonds formed})$ for gaseous species.'}]
pack=dict(subtopic=SUB,spec='9701',version=1,note='Subjects/9701 Chemistry/05 Chemical energetics/5.2 Hess’s law.md',outline='Hess’s law says that enthalpy change depends only on initial and final states. Construct two routes connecting the same chemical states, then reverse arrows with a sign change and multiply enthalpies with equation coefficients. A formation cycle gives $\\Delta H_r^\\ominus=\\sum\\Delta H_f^\\ominus(\\text{products})-\\sum\\Delta H_f^\\ominus(\\text{reactants})$; elemental standard states contribute zero. A combustion cycle leads both routes to the same fully oxidised products. For gaseous bond-energy routes, $\\Delta H\\approx\\sum E(\\text{broken})-\\sum E(\\text{formed})$. Always match states, stoichiometry and the requested direction.',misconceptions=mis,worked=worked,items=items,flashcards=flashcards,diagrams=[])
out=ROOT/'build/out/packs/9701/9701-5.2.json';out.parent.mkdir(parents=True,exist_ok=True);out.write_text(json.dumps(pack,ensure_ascii=False,indent=1))
print(len(items),'draft items',sum('template' in i for i in items),'templates')
