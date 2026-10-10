"""Generate M1-4; all numerical keys, distractors and checks are calculated here."""
from __future__ import annotations
import itertools
import json
import math
from pathlib import Path
import sympy as sp

ROOT = Path(__file__).resolve().parents[3]
G = sp.Rational(49, 5)
K = [f'M1-4.{i}' for i in range(1, 5)]
NOTE = 'Subjects/Maths/M1 Mechanics 1/4 Dynamics of a particle moving in a straight line or plane.md'
p = dict(subtopic='M1-4', spec='M1', version=1, note=NOTE,
    outline='A force changes motion according to Newton’s laws. Draw separate force diagrams and apply $\\sum\\mathbf F=m\\mathbf a$, resolving along chosen axes. Connected particles share the magnitude of acceleration while a light string over a smooth pulley has one tension. On an incline, resolve weight into $mg\\sin\\theta$ along the plane and $mg\\cos\\theta$ perpendicular to it. For a moving particle, friction has magnitude $\\mu R$ and opposes motion. Momentum is $mv$; impulse is the change in momentum. In a direct collision, total signed momentum is conserved when external impulse is negligible.',
    misconceptions=[
        dict(id='m1',kc=K[0],statement='A moving particle needs a forward resultant force to keep moving.',refutation='With zero resultant force, velocity stays constant by Newton’s first law.',contrast='A resultant force changes velocity, not merely maintains it.',source='research'),
        dict(id='m2',kc=K[0],statement='Action and reaction cancel on one particle.',refutation='Newton’s third-law forces act on different bodies.',contrast='Only forces on the chosen particle belong in its $\\sum F=ma$ equation.',source='research'),
        dict(id='m3',kc=K[1],statement='The same force equation applies unchanged after one connected particle hits the ground.',refutation='After contact, the string may become slack and the moving particle has a new force balance.',contrast='Split the motion into phases and carry the contact velocity into the next phase.',source='research'),
        dict(id='m4',kc=K[1],statement='Tension is an extra force on the combined two-particle system.',refutation='The two tension forces are internal and cancel when equations for the two particles are added.',contrast='Keep tension in each separate particle equation.',source='research'),
        dict(id='m5',kc=K[2],statement='Momentum is always positive, even when a particle reverses direction.',refutation='Momentum $mv$ has the signed direction of velocity in one dimension.',contrast='Choose a positive direction before writing collision equations.',source='research'),
        dict(id='m6',kc=K[2],statement='Kinetic energy must be conserved in every direct collision.',refutation='Momentum is conserved when external impulse is negligible; kinetic energy can change.',contrast='Use signed momentum before and after, without assuming restitution or energy conservation.',source='research'),
        dict(id='m7',kc=K[3],statement='The normal reaction on a slope always equals $mg$.',refutation='With no other perpendicular force or acceleration, $R=mg\\cos\\theta$.',contrast='Resolve forces perpendicular to the plane.',source='research'),
        dict(id='m8',kc=K[3],statement='Friction always acts down a rough plane.',refutation='Friction opposes the actual or impending relative motion.',contrast='A particle sliding down has friction up the plane; one sliding up has friction down it.',source='research')],
    worked=[],items=[],flashcards=[],diagrams=[])

def num(x,unit):
    x=float(sp.sympify(x))
    assert math.isfinite(x)
    return {'value':x,'unit':unit,'sf_ok':[2,3,4,5,6]}

def base(kc,kind,diff,word,stem,marks,explanation,hints):
    assert len(hints)==3
    return dict(id=f'M1-4-i{len(p["items"])+1:02d}',kcs=[kc],kind=kind,difficulty=diff,command_word=word,source={'type':'generated'},stem=stem,marks=marks,explanation=explanation,hints=hints)

def template(kc,diff,stem,unit,params,expr,wrongs,explanation,hints,constraints=()):
    it=base(kc,'numeric',diff,'Calculate',stem,2,explanation,hints)
    it['answer']={'unit':unit,'sf_ok':[2,3,4,5,6]}
    it['template']={'params':{n:{'choices':v} for n,v in params.items()},'answer':expr,'distractors':[{'expr':e,'misconception':m} for e,m in wrongs],'constraints':list(constraints)}
    safe={'__builtins__':{},'sqrt':math.sqrt,'sin':math.sin,'cos':math.cos,'pi':math.pi,'abs':abs}
    count=0
    for vals in itertools.product(*params.values()):
        env=dict(zip(params,vals))
        if not all(eval(c,safe,env) for c in constraints): continue
        a=float(eval(expr,safe,env))
        assert math.isfinite(a)
        for e,_ in wrongs:
            b=float(eval(e,safe,env))
            assert math.isfinite(b) and abs(a-b)>0.02*max(abs(a),1e-12),(stem,env,a,b)
        count+=1
    assert count>=4
    p['items'].append(it)

def short(kc,diff,word,stem,points,explanation,hints):
    it=base(kc,'short',diff,word,stem,len(points),explanation,hints)
    it['rubric']=[{'point':s,'keywords':groups} for s,groups in points]
    p['items'].append(it)

def worked(kc,problem,steps,faded_problem,faded_answer,unit):
    p['worked'].append({'id':f'we{len(p["worked"])+1}','kc':kc,'problem':problem,'steps':steps,'faded':{'id':f'we{len(p["worked"])+1}f','problem':faded_problem,'answer':num(faded_answer,unit),'blank_from':1}})

# Newton's laws: computed scalar and two-component resultant-force applications.
template(K[0],2,'A $[[m]]\\,\\mathrm{kg}$ particle has resultant force $[[F]]\\,\\mathrm{N}$ in the positive direction. Calculate its acceleration.','m s^-2',{'m':[2,3,4],'F':[12,18,24]},'F/m',[('F*m','m1')],'Newton’s second law gives $a=F/m$ in the direction of the resultant force.',['Identify the resultant, rather than one individual force.','Apply Newton’s second law to the particle.','Divide the resultant force by mass.'])
template(K[0],3,'A $[[m]]\\,\\mathrm{kg}$ particle has forces $[[P]]\\mathbf i+[[Q]]\\mathbf j$ newtons. Calculate the magnitude of its acceleration.','m s^-2',{'m':[2,4],'P':[6,8],'Q':[3,5]},'sqrt(P*P+Q*Q)/m',[('sqrt(P*P+Q*Q)*m','m1')],'The acceleration vector is $(P\\mathbf i+Q\\mathbf j)/m$; its magnitude is $\\sqrt{P^2+Q^2}/m$.',['Work component by component.','Find the magnitude of the resultant vector.','Use $\\sum\\mathbf F=m\\mathbf a$.'])
short(K[0],4,'Explain','Explain Newton’s three laws and why an action–reaction pair does not cancel in a single particle’s equation.',[
('With zero resultant force, a particle stays at rest or moves with constant velocity.',[['zero','no'],['resultant'],['constant','rest']]),
('The resultant force equals mass times acceleration. ',[['resultant'],['mass'],['acceleration']]),
('An interaction produces equal and opposite forces on different bodies. ',[['equal'],['opposite'],['different']]),
('Only forces on the selected particle enter its equation. ',[['selected','chosen'],['particle','body']])],
'Newton’s first law describes zero resultant, the second gives $\\sum\\mathbf F=m\\mathbf a$, and the third concerns equal opposite forces on different bodies.',['Think about motion when the resultant is zero.','State the force–acceleration equation.','Name which body receives each interaction force.'])
F,m=sp.Integer(15),sp.Integer(3)
a=sp.simplify(F/m)
worked(K[0],f'A {m} kg particle experiences a resultant force of {F} N along $\\mathbf i$. Find its acceleration vector.',[
{'do':'Choose $\\mathbf i$ as the positive direction.','why':'The signs of force and acceleration must use the same axis.'},
{'do':f'Apply $\\sum\\mathbf F=m\\mathbf a$: ${F}\\mathbf i={m}\\mathbf a$.','why':'Newton’s second law uses the resultant force on this particle.'},
{'do':f'$\\mathbf a=({F}/{m})\\mathbf i={a}\\mathbf i\\,\\mathrm{{m\\,s^{{-2}}}}$.','why':'Divide each force component by the mass.','check':{'kind':'numeric','answer':num(a,'m s^-2')}}],
'A 4 kg particle experiences a resultant force of 28 N along $\\mathbf i$. Find its acceleration magnitude.',sp.Rational(28,4),'m s^-2')

# Connected particles, inclines and change of force phase.
template(K[1],3,'Masses $[[m1]]$ kg and $[[m2]]$ kg hang on either side of a light string over a smooth fixed pulley, with $m2>m1$. Calculate their acceleration magnitude. Take $g=9.8\\,\\mathrm{m\\,s^{-2}}$.','m s^-2',{'m1':[1,2,3],'m2':[5,6,7]},'9.8*(m2-m1)/(m1+m2)',[('9.8*(m2-m1)/m2','m4')],'Adding the two separate equations eliminates tension: $(m_2-m_1)g=(m_1+m_2)a$.',['Draw one force diagram for each mass.','Give both particles the same acceleration magnitude.','Add the two $F=ma$ equations to eliminate tension.'])
template(K[1],4,'A $[[m]]$ kg particle slides down a smooth plane inclined at $[[theta]]$ degrees to the horizontal. Calculate its acceleration down the plane. Take $g=9.8\\,\\mathrm{m\\,s^{-2}}$.','m s^-2',{'m':[2,3],'theta':[30,60]},'9.8*sin(theta*pi/180)',[('9.8*cos(theta*pi/180)','m7')],'Resolving along the smooth plane gives $ma=mg\\sin\\theta$, so mass cancels.',['Resolve weight parallel to the slope.','There is no friction on a smooth plane.','Write $ma=mg\\sin\\theta$.'])
short(K[1],4,'Explain','Two particles initially move on a taut string over a smooth pulley. One hits the ground while the other is still moving. Explain how to find the subsequent motion.',[
('Use separate force equations while the string is taut and the same acceleration magnitude for both particles.',[['separate'],['taut'],['acceleration']]),
('At impact carry the velocity forward, then check whether the string becomes slack.',[['velocity'],['slack']]),
('For the later phase use the remaining particle’s new force balance and constant-acceleration equations.',[['later','subsequent'],['force'],['acceleration']])],
'The force system changes at impact. The velocity is continuous through the instant, but the later acceleration must come from a new force diagram.',['Split the motion at the impact instant.','Decide whether tension continues to act.','Use the impact velocity as the new initial velocity.'])
m1,m2=sp.Integer(2),sp.Integer(3)
a=sp.simplify((m2-m1)*G/(m1+m2)); T=sp.simplify(m1*(G+a))
worked(K[1],f'Masses {m1} kg and {m2} kg are connected by a light string over a smooth fixed pulley. Find the acceleration and tension.',[
{'do':f'Take the {m2} kg mass downward and the {m1} kg mass upward as positive.','why':'Both particles have acceleration of the same magnitude.'},
{'do':f'Write ${m2}g-T={m2}a$ and $T-{m1}g={m1}a$.','why':'The string tension acts opposite to each chosen positive direction.'},
{'do':f'Add: $({m2}-{m1})g=({m1}+{m2})a$, so $a={float(a):.2f}\\,\\mathrm{{m\\,s^{{-2}}}}$.','why':'Tension cancels because it is internal to the two-particle system.','check':{'kind':'numeric','answer':num(a,'m s^-2')}},
{'do':f'Substitute into $T-{m1}g={m1}a$: $T={float(T):.2f}\\,\\mathrm{{N}}$.','why':'Use one particle’s equation to recover the string tension.','check':{'kind':'numeric','answer':num(T,'N')}}],
'Masses 1 kg and 4 kg hang over a smooth fixed pulley. Find their acceleration magnitude.',sp.simplify(3*G/5),'m s^-2')

# Momentum and impulse, all one-dimensional.
template(K[2],2,'A $[[m]]$ kg particle changes velocity from $[[u]]$ to $[[v]]\\,\\mathrm{m\\,s^{-1}}$ along a chosen positive line. Calculate the signed impulse on it.','N s',{'m':[2,3,4],'u':[1,2],'v':[5,7]},'m*(v-u)',[('m*(v+u)','m5')],'The impulse–momentum principle gives $J=mv-mu=m(v-u)$.',['Momentum has a direction sign.','Subtract initial momentum from final momentum.','Multiply the velocity change by mass.'])
template(K[2],4,'A $[[m1]]$ kg particle moves right at $[[u1]]\\,\\mathrm{m\\,s^{-1}}$ and collides directly with a stationary $[[m2]]$ kg particle. They stick together. Calculate their common speed after collision.','m s^-1',{'m1':[2,3],'m2':[1,4],'u1':[4,6]},'m1*u1/(m1+m2)',[('m1*u1/m2','m6')],'Conservation of signed momentum gives $m_1u_1=(m_1+m_2)v$ for the joined particles.',['Choose right as positive.','Write total momentum before and after.','The joined mass is the sum of the two masses.'])
short(K[2],4,'Explain','Explain when momentum may be conserved in a direct collision and why kinetic energy need not be conserved.',[
('Total momentum is conserved when the external impulse on the two-particle system is negligible.',[['momentum'],['external'],['impulse'],['negligible','zero']]),
('Momentum is signed in a one-dimensional collision.',[['signed','direction'],['momentum']]),
('Kinetic energy can change to other forms during impact.',[['kinetic'],['energy'],['change','other']])],
'Internal collision impulses cancel for the system. This supports momentum conservation without assuming an elastic collision or a restitution rule.',['Treat the two particles as one system.','Ask which impulses are external.','Keep velocity signs in the momentum equation.'])
ma,mb,ua,ub=sp.Integer(2),sp.Integer(3),sp.Integer(5),sp.Integer(-1)
v=sp.simplify((ma*ua+mb*ub)/(ma+mb))
worked(K[2],f'A {ma} kg particle moves right at {ua} m s^-1 and collides directly with a {mb} kg particle moving left at 1 m s^-1. They stick together. Find their common velocity.',[
{'do':'Take right as positive, so the initial velocities are $+5$ and $-1\\,\\mathrm{m\\,s^{-1}}$.','why':'Momentum is a signed vector quantity along the line.'},
{'do':f'Conserve momentum: $({ma})({ua})+({mb})({ub})=({ma}+{mb})v$.','why':'The collision is brief and external impulse is taken as negligible.'},
{'do':f'$v={v}\\,\\mathrm{{m\\,s^{{-1}}}}$ to the right.','why':'The positive sign identifies direction.','check':{'kind':'numeric','answer':num(v,'m s^-1')}}],
'A 2 kg particle moving right at 6 m s^-1 sticks to a stationary 4 kg particle. Find their common speed.',sp.Rational(2*6,2+4),'m s^-1')

# Moving friction: resolve normal reaction before using mu R.
template(K[3],3,'A $[[m]]$ kg particle slides on a rough horizontal surface with coefficient of friction $[[mu]]$. Calculate the friction magnitude. Take $g=9.8\\,\\mathrm{m\\,s^{-2}}$.','N',{'m':[2,3,4],'mu':[0.2,0.3,0.4]},'mu*m*9.8',[('m*9.8','m7')],'On the horizontal surface $R=mg$, so moving friction has magnitude $F=\\mu R=\\mu mg$.',['Find the normal reaction first.','Use $F=\\mu R$ for a moving particle.','Friction opposes the sliding direction.'])
template(K[3],4,'A $[[m]]$ kg particle slides down a rough plane inclined at $[[theta]]$ degrees to the horizontal. The coefficient of friction is $[[mu]]$. Calculate its acceleration down the plane. Take $g=9.8\\,\\mathrm{m\\,s^{-2}}$.','m s^-2',{'m':[2,4],'theta':[30,45],'mu':[0.1,0.2]},'9.8*(sin(theta*pi/180)-mu*cos(theta*pi/180))',[('9.8*(sin(theta*pi/180)+mu*cos(theta*pi/180))','m8'),('9.8*(sin(theta*pi/180)-mu)','m7')],'Here $R=mg\\cos\\theta$ and friction is up the plane. Thus $ma=mg\\sin\\theta-\\mu mg\\cos\\theta$.',['Set axes parallel and perpendicular to the plane.','Find $R$ before calculating friction.','Because motion is down the plane, friction is up it.'])
short(K[3],4,'Explain','A particle is sliding up a rough incline. Explain the direction and magnitude of friction and how the normal reaction is found.',[
('Friction acts down the plane, opposite the upward motion.',[['friction'],['down'],['opposite']]),
('Its magnitude is $F=\\mu R$.',[['mu','coefficient'],['reaction']]),
('With only weight and reaction perpendicular to the plane, $R=mg\\cos\\theta$.',[['reaction'],['cos']])],
'Friction opposes sliding, so it points downhill here. Resolve perpendicular to the slope to obtain $R$, then use $F=\\mu R$.',['Use the actual direction of sliding.','Resolve perpendicular to the plane.','Use the coefficient only after finding the reaction.'])
m=sp.Integer(2); mu=sp.Rational(1,5); theta=sp.pi/6
R=sp.simplify(m*G*sp.cos(theta)); Ff=sp.simplify(mu*R); acc=sp.simplify(G*sp.sin(theta)-Ff/m)
worked(K[3],'A 2 kg particle slides down a rough $30^\\circ$ plane with coefficient of friction $0.2$. Find its acceleration.',[
{'do':'Take down the plane as positive. Friction acts up the plane.','why':'Friction opposes the actual sliding direction.'},
{'do':f'Resolve perpendicular: $R=mg\\cos30^\\circ={sp.latex(R)}\\,\\mathrm{{N}}$.','why':'There is no acceleration perpendicular to the plane.','check':{'kind':'numeric','answer':num(R,'N')}},
{'do':f'Use $F=\\mu R={sp.latex(Ff)}\\,\\mathrm{{N}}$.','why':'The particle is moving, so the stated friction rule applies.','check':{'kind':'numeric','answer':num(Ff,'N')}},
{'do':f'Along the plane, $ma=mg\\sin30^\\circ-F$, giving $a={float(acc):.3g}\\,\\mathrm{{m\\,s^{{-2}}}}$.','why':'The weight component drives downhill motion and friction resists it.','check':{'kind':'numeric','answer':num(acc,'m s^-2')}}],
'A 3 kg particle slides down a rough 30 degree plane with coefficient of friction 0.1. Find its acceleration.',sp.simplify(G*(sp.sin(sp.pi/6)-sp.Rational(1,10)*sp.cos(sp.pi/6))),'m s^-2')

p['flashcards']=[
{'id':'fc1','kc':K[0],'front':'State Newton’s first law.','back':'A body remains at rest or moves with constant velocity unless acted on by a non-zero resultant force.'},
{'id':'fc2','kc':K[0],'front':'State Newton’s second law for constant mass.','back':'The resultant force on a body equals its mass times acceleration, in the direction of the acceleration: $\\sum\\mathbf F=m\\mathbf a$.'},
{'id':'fc3','kc':K[0],'front':'State Newton’s third law.','back':'When two bodies interact, they exert forces on each other that are equal in magnitude and opposite in direction.'},
{'id':'fc4','kc':K[2],'front':'State the impulse–momentum principle.','back':'The impulse on a particle equals its change in momentum: $J=mv-mu$.'},
{'id':'fc5','kc':K[2],'front':'When is momentum conserved for two colliding particles?','back':'Their total momentum is conserved when the resultant external impulse on the two-particle system is negligible.'},
{'id':'fc6','kc':K[3],'front':'State the moving friction rule.','back':'The magnitude of friction is $F=\\mu R$ for a particle moving relative to a rough surface; friction opposes motion.'}]

assert len(p['items'])==12 and len(p['worked'])==4
out=ROOT/'build/out/packs/M1/M1-4.json'
out.parent.mkdir(parents=True,exist_ok=True)
out.write_text(json.dumps(p,ensure_ascii=False,indent=1)+'\n')
print(out)
