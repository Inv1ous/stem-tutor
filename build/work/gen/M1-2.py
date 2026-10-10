"""Generate M1-2; all numerical values and template alternatives are calculated here."""
from __future__ import annotations
import itertools
import json
import math
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
K1, K2 = 'M1-2.1', 'M1-2.2'
pack = dict(subtopic='M1-2', spec='M1', version=1,
 note='Subjects/Maths/M1 Mechanics 1/2 Vectors in mechanics.md',
 outline='In a plane, write a vector as $x\\mathbf{i}+y\\mathbf{j}$ using signed horizontal and vertical components. Add vectors component by component to find a resultant. Magnitude is $\\sqrt{x^2+y^2}$ and direction is fixed by a reference axis and the signs of the components. Resolve a vector of magnitude $V$ at angle $\\theta$ above the positive horizontal as $(V\\cos\\theta)\\mathbf{i}+(V\\sin\\theta)\\mathbf{j}$. Displacement, velocity, acceleration and force all obey these vector rules. For constant velocity, divide change in displacement by time; for constant acceleration, divide change in velocity by time.',
 misconceptions=[
 dict(id='m1',kc=K1,statement='The magnitude of $x\\mathbf{i}+y\\mathbf{j}$ is $x+y$.',refutation='Perpendicular components form a right triangle, so magnitude is $\\sqrt{x^2+y^2}$.',contrast='For $3\\mathbf{i}+4\\mathbf{j}$ the magnitude is $5$, not $7$.',source='research'),
 dict(id='m2',kc=K1,statement='A resultant is found by adding the magnitudes of all vectors.',refutation='Add corresponding signed components first; only then find the resultant magnitude.',contrast='Opposite vectors can cancel even though both have positive magnitudes.',source='research'),
 dict(id='m3',kc=K1,statement='The horizontal component of a vector at an angle from the horizontal is $V\\sin\\theta$.',refutation='The horizontal component is adjacent to that angle and equals $V\\cos\\theta$.',contrast='The vertical component is $V\\sin\\theta$.',source='research'),
 dict(id='m4',kc=K2,statement='Velocity equals position divided by time even when the initial position is nonzero.',refutation='Velocity at constant rate is change in displacement divided by elapsed time.',contrast='Subtract the initial position vector before dividing.',source='research'),
 dict(id='m5',kc=K2,statement='Acceleration is the change in speed divided by time.',refutation='Acceleration is change in the velocity vector divided by time.',contrast='A change of direction can give acceleration without changing speed.',source='research')],
 worked=[],items=[],flashcards=[],diagrams=[])

def answer(value,unit=''):
    v=float(value)
    assert math.isfinite(v)
    return {'value':v,'unit':unit,'sf_ok':[2,3,4,5,6]}

def base(k,kind,difficulty,word,stem,marks,explanation,hints):
    return dict(id=f'M1-2-i{len(pack["items"])+1:02d}',kcs=[k],kind=kind,difficulty=difficulty,
                command_word=word,source={'type':'generated'},stem=stem,marks=marks,
                explanation=explanation,hints=hints)

def numeric(k, difficulty, stem, unit, params, expr, wrong, explanation, hints, constraints=None):
    it=base(k,'numeric',difficulty,'Find',stem,2,explanation,hints)
    it['answer']={'unit':unit,'sf_ok':[2,3,4,5,6]}
    it['template']={'params':{p:{'choices':vals} for p,vals in params.items()},'answer':expr,
                    'distractors':[{'expr':e,'misconception':m} for e,m in wrong],
                    'constraints':constraints or []}
    # Independently check every choice combination, including distractor separation.
    for vals in itertools.product(*params.values()):
        env=dict(zip(params,vals))
        if not all(eval(c,{'__builtins__':{},'sqrt':math.sqrt,'abs':abs},env) for c in it['template']['constraints']): continue
        actual=eval(expr,{'__builtins__':{},'sqrt':math.sqrt,'abs':abs},env)
        assert math.isfinite(actual)
        for e,_ in wrong:
            alt=eval(e,{'__builtins__':{},'sqrt':math.sqrt,'abs':abs},env)
            assert abs(alt-actual)>0.02*max(abs(actual),1e-12),(stem,env,actual,alt)
    pack['items'].append(it)

def mcq(k,difficulty,stem,opts,key,mapping,explanation,hints):
    it=base(k,'mcq',difficulty,'Find',stem,1,explanation,hints)
    it.update(options=dict(zip('ABCD',opts)),answer=key,distractors=mapping,shuffle=True)
    pack['items'].append(it)

def short(k,difficulty,word,stem,points,explanation,hints):
    it=base(k,'short',difficulty,word,stem,len(points),explanation,hints)
    it['rubric']=[{'point':p,'keywords':keys} for p,keys in points]
    pack['items'].append(it)

numeric(K1,2,'Find the magnitude of $[[x]]\\mathbf{i}+[[y]]\\mathbf{j}$.','',
 {'x':[3,5,8],'y':[4,12,15]},'sqrt(x*x+y*y)',[('x+y','m1'),('sqrt(x*x-y*y)','m1')],
 'The components are perpendicular, so use Pythagoras: $|\\mathbf{v}|=\\sqrt{x^2+y^2}$.',
 ['Draw the component triangle.','Use the two perpendicular component lengths.','Square both components before combining them.'],['x*x>y*y'])
numeric(K1,3,'For $\\mathbf{a}=[[x]]\\mathbf{i}+[[y]]\\mathbf{j}$ and $\\mathbf{b}=[[u]]\\mathbf{i}-[[v]]\\mathbf{j}$, find the magnitude of $\\mathbf{a}+\\mathbf{b}$.','',
 {'x':[3,6,9],'y':[8,10],'u':[4,8],'v':[2,4]},'sqrt((x+u)**2+(y-v)**2)',
 [('sqrt(x*x+y*y)+sqrt(u*u+v*v)','m2'),('sqrt((x+u)**2+(y+v)**2)','m2')],
 'Add signed horizontal and vertical components, then take the magnitude of the resulting vector.',
 ['The second vector has a negative vertical component.','Add the horizontal and vertical components separately.','Form the resultant before using Pythagoras.'])
mcq(K1,2,'Find the resultant of $3\\mathbf{i}+4\\mathbf{j}$ and $-5\\mathbf{i}+2\\mathbf{j}$.',
 ['$-2\\mathbf{i}+6\\mathbf{j}$','$8\\mathbf{i}+6\\mathbf{j}$','$-2\\mathbf{i}+2\\mathbf{j}$','$2\\mathbf{i}+6\\mathbf{j}$'],'A',{'B':'m2','C':'m2'},
 'Add like components: $3-5=-2$ and $4+2=6$. Magnitudes are not added to obtain vector components.',
 ['Treat $\\mathbf{i}$ and $\\mathbf{j}$ separately.','Keep the negative sign of the second horizontal component.','Add each pair of signed coefficients.'])
short(K1,3,'Explain','A force of magnitude $10\\,\\mathrm{N}$ acts $30^\\circ$ above the positive horizontal. Explain how to resolve it into $\\mathbf{i}$ and $\\mathbf{j}$ components.',
 [('The horizontal component is $10\\cos30^\\circ=5\\sqrt3\\,\\mathrm{N}$.',[['cos'],['horizontal']]),
  ('The vertical component is $10\\sin30^\\circ=5\\,\\mathrm{N}$.',[['sin'],['vertical']])],
 'The horizontal side is adjacent to the angle, and the vertical side is opposite it. Both are positive in this quadrant.',
 ['Sketch a right triangle with the angle at the horizontal.','Label adjacent and opposite sides.','Apply cosine to the adjacent side and sine to the opposite side.'])
short(K1,4,'Find','A force is $-6\\mathbf{i}+8\\mathbf{j}\\,\\mathrm{N}$. Find its magnitude and direction, measured anticlockwise from the positive $\\mathbf{i}$ direction.',
 [('The magnitude is $10\\,\\mathrm{N}$.',[['10']]),('The direction is approximately $126.87^\\circ$ anticlockwise from positive $\\mathbf{i}$.',[['126.87','126.9','127']])],
 'Pythagoras gives $\\sqrt{(-6)^2+8^2}=10$. The vector is in quadrant II, so the direction is $180^\\circ-\\tan^{-1}(8/6)\\approx126.87^\\circ$.',
 ['Locate the quadrant from the component signs.','Use Pythagoras for magnitude.','Find the reference angle, then adjust it for quadrant II.'])

numeric(K2,3,'A particle moves at constant velocity from $[[x0]]\\mathbf{i}+[[y0]]\\mathbf{j}\\,\\mathrm{m}$ to $[[x1]]\\mathbf{i}+[[y1]]\\mathbf{j}\\,\\mathrm{m}$ in $[[t]]\\,\\mathrm{s}$. Find the magnitude of its velocity.','m s^-1',
 {'x0':[1,2],'y0':[1,2],'x1':[9,14],'y1':[7,10],'t':[2,4]},'sqrt((x1-x0)**2+(y1-y0)**2)/t',
 [('sqrt(x1*x1+y1*y1)/t','m4'),('sqrt((x1-x0)**2+(y1-y0)**2)*t','m4')],
 'Subtract the initial position to get displacement, divide each component by time, and then find speed as the velocity magnitude.',
 ['Work with a change in position.','Subtract initial coordinates from final coordinates.','Divide the displacement magnitude by elapsed time.'])
numeric(K2,4,'A velocity changes at constant acceleration from $[[ux]]\\mathbf{i}+[[uy]]\\mathbf{j}\\,\\mathrm{m\\,s^{-1}}$ to $[[vx]]\\mathbf{i}+([[vy]])\\mathbf{j}\\,\\mathrm{m\\,s^{-1}}$ in $[[t]]\\,\\mathrm{s}$. Find the magnitude of the acceleration.','m s^-2',
 {'ux':[1,3],'uy':[4,6],'vx':[7,11],'vy':[-2,-4],'t':[2,4]},'sqrt((vx-ux)**2+(vy-uy)**2)/t',
 [('abs(vx-ux)/t','m5'),('sqrt((vx-ux)**2+(vy+uy)**2)/t','m5')],
 'Acceleration is the change of the velocity vector divided by time; subtract components before calculating its magnitude.',
 ['Use velocity vectors, not just speeds.','Subtract the initial velocity component by component.','Find the magnitude after dividing by time.'])
mcq(K2,2,'Find the constant velocity when displacement changes from $2\\mathbf{i}-3\\mathbf{j}\\,\\mathrm{m}$ to $8\\mathbf{i}+9\\mathbf{j}\\,\\mathrm{m}$ in $3\\,\\mathrm{s}$.',
 ['$2\\mathbf{i}+4\\mathbf{j}\\,\\mathrm{m\\,s^{-1}}$','$\\frac83\\mathbf{i}+3\\mathbf{j}\\,\\mathrm{m\\,s^{-1}}$','$6\\mathbf{i}+12\\mathbf{j}\\,\\mathrm{m\\,s^{-1}}$','$2\\mathbf{i}+2\\mathbf{j}\\,\\mathrm{m\\,s^{-1}}$'],'A',{'B':'m4','C':'m4'},
 'The displacement change is $(8-2)\\mathbf{i}+[9-(-3)]\\mathbf{j}=6\\mathbf{i}+12\\mathbf{j}\\,\\mathrm{m}$; dividing by 3 s gives the velocity. Dividing final position alone by time ignores the starting position.',
 ['Find the displacement change first.','Subtract the initial vector, including its negative component.','Divide each resulting component by the elapsed time.'])
short(K2,2,'Explain','Explain why a particle can have non-zero acceleration while its speed remains constant.',
 [('Velocity has direction as well as magnitude, so a change in direction changes velocity.',[['direction'],['velocity']]),('Acceleration is change in velocity divided by time.',[['change'],['velocity'],['time']])],
 'Constant speed fixes the magnitude of velocity, but the velocity vector may turn; a change in velocity over time is acceleration.',
 ['Distinguish speed from velocity.','Consider what happens when direction changes.','Use the definition of acceleration.'])
short(K2,4,'Calculate','A constant force is $6\\mathbf{i}-8\\mathbf{j}\\,\\mathrm{N}$ and a second constant force is $-2\\mathbf{i}+5\\mathbf{j}\\,\\mathrm{N}$. Calculate the resultant force and its magnitude.',
 [('The resultant force is $4\\mathbf{i}-3\\mathbf{j}\\,\\mathrm{N}$.',[['4'],['-3']]),('Its magnitude is $5\\,\\mathrm{N}$.',[['5']])],
 'Add signed force components to get $4\\mathbf{i}-3\\mathbf{j}$ N. Its magnitude is $\\sqrt{4^2+(-3)^2}=5$ N.',
 ['Combine forces as vectors.','Add horizontal and vertical parts separately.','Use Pythagoras on the resultant components.'])

# Computed checks for worked examples and faded follow-ups.
mag=math.hypot(3,4); faded_mag=math.hypot(5,12)
assert mag==5 and faded_mag==13
pack['worked'].append(dict(id='we1',kc=K1,problem='Find the magnitude and direction of $3\\mathbf{i}+4\\mathbf{j}$, measured anticlockwise from positive $\\mathbf{i}$.',steps=[
 {'do':'Identify horizontal component $3$ and vertical component $4$.','why':'Their signs place the vector in quadrant I.'},
 {'do':'Use $|\\mathbf{v}|=\\sqrt{3^2+4^2}=5$.','why':'The components are perpendicular.','check':{'kind':'numeric','answer':answer(mag)}},
 {'do':'Use $\\theta=\\tan^{-1}(4/3)\\approx53.13^\\circ$.','why':'Direction must name a reference axis and sense of rotation.'}],
 faded={'id':'we1f','problem':'Find the magnitude of $5\\mathbf{i}+12\\mathbf{j}$.','answer':answer(faded_mag),'blank_from':1}))
vx=(8-2)/3; vy=(9-(-3))/3; speed=math.hypot(vx,vy)
faded_speed=math.hypot((13-1)/4,(10-2)/4)
assert (vx,vy)==(2,4) and math.isclose(speed,math.sqrt(20)) and math.isclose(faded_speed,math.sqrt(13))
pack['worked'].append(dict(id='we2',kc=K2,problem='A particle moves at constant velocity from $2\\mathbf{i}-3\\mathbf{j}$ m to $8\\mathbf{i}+9\\mathbf{j}$ m in 3 s. Find its velocity and speed.',steps=[
 {'do':'Calculate $\\Delta\\mathbf{r}=(8-2)\\mathbf{i}+[9-(-3)]\\mathbf{j}=6\\mathbf{i}+12\\mathbf{j}$ m.','why':'Velocity uses change in displacement, including both signed coordinates.'},
 {'do':'Divide by time: $\\mathbf{v}=2\\mathbf{i}+4\\mathbf{j}\\,\\mathrm{m\\,s^{-1}}$.','why':'Velocity is displacement change per unit time at constant velocity.','check':{'kind':'numeric','answer':answer(vx,'m s^-1')}},
 {'do':'Find speed $|\\mathbf{v}|=\\sqrt{2^2+4^2}=\\sqrt{20}\\,\\mathrm{m\\,s^{-1}}$.','why':'Speed is the magnitude of the velocity vector.','check':{'kind':'numeric','answer':answer(speed,'m s^-1')}}],
 faded={'id':'we2f','problem':'A particle moves at constant velocity from $\\mathbf{i}+2\\mathbf{j}$ m to $13\\mathbf{i}+10\\mathbf{j}$ m in 4 s. Find its speed.','answer':answer(faded_speed,'m s^-1'),'blank_from':1}))

# Computed checks for fixed numerical assessment content.
assert math.hypot(-6,8)==10
assert math.isclose(180-math.degrees(math.atan2(8,6)),126.86989764584402)
assert (6-2,-8+5)==(4,-3) and math.hypot(4,-3)==5
assert math.isclose(10*math.cos(math.radians(30)),5*math.sqrt(3))
assert math.isclose(10*math.sin(math.radians(30)),5)
assert len(pack['items'])==10 and len(pack['worked'])==2
path=ROOT/'build/out/packs/M1/M1-2.json'
path.write_text(json.dumps(pack,ensure_ascii=False,indent=1)+'\n')
print(path)
