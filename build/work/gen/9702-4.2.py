import json, math
from pathlib import Path
ROOT=Path(__file__).resolve().parents[3]
sub='9702-4.2'; ks=[sub+'.'+str(i) for i in (1,2,3)]
P=ROOT/'build/out/packs/9702/9702-4.2.json'
mis=[
 {'id':'m1','kc':ks[0],'statement':'The weight of a uniform rod acts at its far end.','refutation':'Its weight acts at the centre of mass, halfway along the rod.','contrast':'Use half the rod length as the weight lever arm.','source':'ER 9702 w23 P13 Q12'},
 {'id':'m2','kc':ks[0],'statement':'Clockwise and anticlockwise moments may be summed about different points.','refutation':'The principle compares moments about the same point.','contrast':'Choose one pivot and use it for every term.','source':'ER 9702 w22 P23 Q3'},
 {'id':'m3','kc':ks[1],'statement':'Zero resultant force alone proves equilibrium.','refutation':'A nonzero resultant torque can still cause rotation.','contrast':'Check both force and torque sums.','source':'ER 9702 w23 P23 Q3'},
 {'id':'m4','kc':ks[2],'statement':'One inclined string supplies the whole vertical support when two strings pull symmetrically.','refutation':'Both strings supply upward components.','contrast':'Use twice the vertical component of one tension.','source':'ER 9702 w20 P12 Q14'}]
num=lambda v,u='N':{'value':round(v,8),'unit':u,'sf_ok':[2,3]}
def item(i,k,kind,stem,answer,explanation,diff=2,**kw):
 return {'id':f'{sub}-i{i:02d}','kcs':[k],'kind':kind,'difficulty':diff,'command_word':kw.pop('command_word','Calculate' if kind=='numeric' else 'State'),'source':{'type':'generated'},'stem':stem,'marks':1,'answer':answer,'explanation':explanation,'hints':kw.pop('hints',['Identify the forces and their directions.','Choose the equilibrium condition relevant here.','Write the appropriate sum before substituting.']),**kw}
items=[]; n=0
def add(k,kind,stem,ans,exp,**kw):
 global n;n+=1;items.append(item(n,k,kind,stem,ans,exp,**kw))
# Templates calculate all sampled values in Python as well as declarative expressions.
for k,stem,params,expr,unit,exp,dist in [
 (ks[0],'A uniform horizontal rod weighs [[W]] N. A vertical force acts at its far end to hold it level about a hinge at the other end. Calculate the force.',{'W':{'min':12,'max':40,'step':2}},'W/2','N','The weight acts at the centre, so $F L=W L/2$.',[{'expr':'W','misconception':'m1'}]),
 (ks[2],'A ball weighs [[W]] N and hangs from a string at [[a]]° to the vertical. A horizontal force holds it in equilibrium. Calculate the horizontal force.',{'W':{'min':6,'max':20,'step':2},'a':{'choices':[30,45,60]}},'W*tan(a*pi/180)','N','The closed force triangle gives horizontal force $F=W\\tan a$.',[{'expr':'W*sin(a*pi/180)','misconception':'m4'}])]:
 vals={p:(v.get('choices') or list(range(v['min'],v['max']+1,v['step'])))[0] for p,v in params.items()}
 val=eval(expr,{'__builtins__':{} ,'tan':math.tan,'sin':math.sin,'pi':math.pi},vals)
 for d in dist: assert abs(val-eval(d['expr'],{'__builtins__':{},'sin':math.sin,'pi':math.pi},vals))>1e-6
 add(k,'numeric',stem,num(val,unit),exp,difficulty=3,template={'params':params,'answer':expr,'distractors':dist,'constraints':[]})
# Exact conceptual retrieval variants
concepts=[
 (ks[0],'State the principle of moments.', 'For an object in rotational equilibrium, the sum of clockwise moments about a point equals the sum of anticlockwise moments about the same point.'),
 (ks[0],'Identify the point about which all moments must be compared.','The same point for all moments.'),
 (ks[0],'Explain why the weight of a uniform beam acts at its midpoint in a moments calculation.','Its centre of mass is at its midpoint, so its weight acts there.'),
 (ks[1],'State both conditions for the equilibrium of a rigid object.','The resultant force and the resultant torque must each be zero.'),
 (ks[1],'Explain why an equal and opposite pair of forces can still turn an object.','The forces can form a couple: their resultant force is zero but their torques add.'),
 (ks[1],'State whether a rigid object moving at constant velocity can be in equilibrium.','Yes. Constant velocity means zero acceleration, and zero resultant force; it is in equilibrium if its resultant torque is also zero.'),
 (ks[1],'State whether zero resultant torque alone ensures equilibrium.','No. A nonzero resultant force can still accelerate the object.'),
 (ks[2],'Describe the vector triangle for three coplanar forces in equilibrium.','Draw the three force vectors head to tail, to scale and in their directions; the triangle closes.'),
 (ks[2],'Explain what a gap between the start and end of a force triangle means.','The resultant force is nonzero, so the forces are not in translational equilibrium.'),
 (ks[2],'State why the direction of each arrow matters in a triangle of forces.','The head-to-tail vector sum must close; reversing an arrow changes the sum.'),
]
for k,stem,point in concepts:
 add(k,'short',stem,None,point,command_word=stem.split()[0],rubric=[{'point':point,'keywords':[[w] for w in (['clockwise','anticlockwise','same','point'] if 'principle' in stem else [point.split()[0]])]}])
# Additional exam-style numeric cases
add(ks[0],'numeric','A uniform horizontal beam of weight 24 N is hinged at one end. A vertical upward force at the other end holds it in equilibrium. Calculate the force.',num(24/2),'The weight acts halfway along, so $F L=24L/2$.',difficulty=4)
add(ks[1],'short','Explain why an object with zero net force but a nonzero couple is not in equilibrium.',None,'The couple gives a nonzero resultant torque and angular acceleration.',difficulty=4,command_word='Explain',rubric=[{'point':'The couple gives a nonzero resultant torque.','keywords':[['torque','moment'],['nonzero','not zero']]}])
add(ks[2],'numeric','Two equal strings support a 12 N load symmetrically. Each string makes 30° to the horizontal. Calculate the tension in each string.',num(12/(2*math.sin(math.pi/6))),'The two vertical tension components support the weight: $2T\\sin30^\\circ=12$.',difficulty=4)
# Past questions retained exactly from the tagged bank
chosen=['9702_w23_13_q12','9702_w23_12_q4','9702_w23_12_q13','9702_w22_13_q13','9702_w21_12_q14','9702_w20_12_q14','9702_w19_12_q11','9702_s23_12_q12','9702_s23_11_q13','9702_w24_13_q6','9702_w24_12_q11','9702_w22_13_q12']
bank={x['id']:x for x in json.loads((ROOT/'build/work/mcq/9702.tagged.json').read_text())}
for j,qid in enumerate(chosen,1):
 b=bank[qid]; k=next((x for x in b['kcs'] if x in ks),ks[1]); er=b.get('er','')
 exp=er[:500] if er else ('The correct option follows from both equilibrium conditions.' if k==ks[1] else 'Resolve the forces or moments using the directions shown.')
 if qid=='9702_w23_12_q13': exp='Horizontal force is $0.15\\tan30^\\circ=0.087$ N. Option A uses $0.15\\sin30^\\circ$, treating weight as tension.'
 items.append({'id':f'{sub}-p{j:02d}','kcs':[k],'kind':'mcq','difficulty':3,'command_word':'Identify','source':{'type':'past','ref':b['ref'],'qid':qid},'stem':b['stem'],'options':b['options'],'answer':b['answer'],'image':b.get('image'),'marks':1,'explanation':exp,'hints':['Identify the forces and geometry.','Apply both relevant equilibrium conditions.','Check the lever arm or component direction.']})
worked=[
 {'id':'we1','kc':ks[0],'problem':'A uniform 2.0 m rod weighs 18 N and is hinged at one end. Find the vertical supporting force at the other end.','steps':[{'do':'Take moments about the hinge: $F(2.0)=18(1.0)$.','why':'The hinge force has no moment and the uniform rod weight acts at its midpoint.'},{'do':'$F=9.0$ N.','why':'Clockwise and anticlockwise moments balance.','check':{'kind':'numeric','answer':num(18/2)}}], 'faded':{'id':'we1f','problem':'A uniform 3.0 m rod weighs 30 N and is hinged at one end. Find the vertical supporting force at the other end.','answer':num(30/2),'blank_from':1}},
 {'id':'we2','kc':ks[2],'problem':'A 12 N weight is held by a sloping string at 45° to the vertical and a horizontal force. Find the horizontal force.','steps':[{'do':'Draw the force triangle: vertical side $W=12$ N, horizontal side $F$, and sloping tension.','why':'The three forces close head to tail in equilibrium.'},{'do':'$F=12\\tan45^\\circ=12$ N.','why':'The angle is measured from the vertical.','check':{'kind':'numeric','answer':num(12*math.tan(math.pi/4))}}], 'faded':{'id':'we2f','problem':'A 10 N weight is held by a string at 30° to vertical and a horizontal force. Find the horizontal force.','answer':num(10*math.tan(math.pi/6)),'blank_from':1}}]
pack={'subtopic':sub,'spec':'9702','version':1,'note':'Subjects/9702 Physics/04 Forces, density and pressure/4.2 Equilibrium of forces.md','outline':'For a rigid object in equilibrium, both the resultant force and resultant torque are zero. The principle of moments balances clockwise and anticlockwise sums about the same point. For three coplanar forces, a closed head-to-tail vector triangle shows zero resultant force.','misconceptions':mis,'worked':worked,'items':items,'flashcards':[{'id':'fc1','kc':ks[0],'front':'State the principle of moments.','back':'For an object in rotational equilibrium, the sum of clockwise moments about a point equals the sum of anticlockwise moments about the same point.'},{'id':'fc2','kc':ks[1],'front':'State the conditions for equilibrium.','back':'The resultant force is zero and the resultant torque is zero.'},{'id':'fc3','kc':ks[2],'front':'How do three coplanar forces in equilibrium appear as vectors?','back':'They form a closed head-to-tail vector triangle.'}],'diagrams':[]}
P.write_text(json.dumps(pack,ensure_ascii=False,indent=1))
