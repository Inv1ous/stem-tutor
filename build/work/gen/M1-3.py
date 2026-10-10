"""Generate the M1-3 pack; calculate and audit every numerical result."""
from __future__ import annotations
import itertools
import json
import math
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
KC = 'M1-3.1'
G = 9.8
pack = dict(
    subtopic='M1-3', spec='M1', version=1,
    note='Subjects/Maths/M1 Mechanics 1/3 Kinematics of a particle moving in a straight line.md',
    outline='Choose a positive direction and use signed displacement $s$, initial velocity $u$, final velocity $v$, constant acceleration $a$ and time $t$. The constant-acceleration equations include $v=u+at$, $s=ut+\\tfrac12at^2$, $s=\\tfrac12(u+v)t$ and $v^2=u^2+2as$. Select an equation containing the known quantities and the unknown, then check the sign and units. The gradient of a displacement–time graph is velocity; the gradient of a velocity–time graph is acceleration. Signed area under velocity–time gives displacement, while area under speed–time gives distance. Area under acceleration–time gives change in velocity. A straight velocity–time line represents constant acceleration; the corresponding displacement–time curve is quadratic.',
    misconceptions=[
        dict(id='m1',kc=KC,statement='Initial velocity can be ignored when finding final velocity or displacement.',refutation='Initial velocity contributes $u$ to $v=u+at$ and $ut$ to $s=ut+\\tfrac12at^2$.',contrast='Even before acceleration acts, the particle may already be moving.',source='research'),
        dict(id='m2',kc=KC,statement='Area below the time axis on a velocity–time graph counts positively towards displacement.',refutation='Velocity is signed, so area below the axis is negative displacement.',contrast='For distance, add the magnitudes of all areas.',source='research'),
        dict(id='m3',kc=KC,statement='The gradient of a velocity–time graph gives displacement.',refutation='The gradient is change in velocity divided by time, which is acceleration.',contrast='Area under velocity–time gives displacement.',source='research'),
        dict(id='m4',kc=KC,statement='The acceleration contribution to displacement is $at^2$.',refutation='For constant acceleration it is $\\tfrac12at^2$ because velocity rises linearly.',contrast='The acceleration contribution is the triangular area under a velocity–time line.',source='research'),
        dict(id='m5',kc=KC,statement='A negative acceleration always means a particle is slowing down.',refutation='Negative acceleration means acceleration points in the negative chosen direction.',contrast='If velocity is also negative, speed increases.',source='research')],
    worked=[], items=[], flashcards=[], diagrams=[])

def ans(value, unit):
    value=float(value)
    assert math.isfinite(value)
    return dict(value=value,unit=unit,sf_ok=[2,3,4,5,6])

def base(kind,diff,word,stem,marks,explanation,hints):
    assert len(hints)==3
    return dict(id=f'M1-3-i{len(pack["items"])+1:02d}',kcs=[KC],kind=kind,difficulty=diff,command_word=word,source={'type':'generated'},stem=stem,marks=marks,explanation=explanation,hints=hints)

def template(diff,word,stem,unit,params,expr,wrongs,explanation,hints,constraints=()):
    it=base('numeric',diff,word,stem,2,explanation,hints)
    it['answer']=dict(unit=unit,sf_ok=[2,3,4,5,6])
    it['template']=dict(params={name:{'choices':values} for name,values in params.items()},answer=expr,distractors=[dict(expr=x,misconception=m) for x,m in wrongs],constraints=list(constraints))
    count=0
    safe={'__builtins__':{},'sqrt':math.sqrt,'abs':abs}
    for values in itertools.product(*params.values()):
        env=dict(zip(params,values))
        if not all(eval(c,safe,env) for c in constraints): continue
        right=eval(expr,safe,env)
        assert math.isfinite(right)
        for x,_ in wrongs:
            wrong=eval(x,safe,env)
            assert math.isfinite(wrong) and abs(right-wrong)>0.02*max(abs(right),1e-12),(stem,env,right,wrong)
        count+=1
    assert count>=4
    pack['items'].append(it)

def mcq(diff,word,stem,options,key,mapping,explanation,hints):
    it=base('mcq',diff,word,stem,1,explanation,hints)
    it.update(options=dict(zip('ABCD',options)),answer=key,distractors=mapping,shuffle=True)
    assert len(set(options))==4 and key in 'ABCD'
    pack['items'].append(it)

def short(diff,word,stem,points,explanation,hints):
    it=base('short',diff,word,stem,len(points),explanation,hints)
    it['rubric']=[dict(point=p,keywords=k) for p,k in points]
    pack['items'].append(it)

# All parameter choices and distractors are evaluated above, rather than accepted by inspection.
template(2,'Find','A particle has initial velocity $[[u]]\\,\\mathrm{m\\,s^{-1}}$ and constant acceleration $[[a]]\\,\\mathrm{m\\,s^{-2}}$. Find its velocity after $[[t]]\\,\\mathrm{s}$.','m s^-1',
    {'u':[2,4,6],'a':[2,3],'t':[3,5]},'u+a*t',[('a*t','m1')],
    'For constant acceleration, $v=u+at$: add the change in velocity $at$ to the initial velocity.',
    ['List the known suvat quantities.','Choose the equation relating initial and final velocity, acceleration and time.','Multiply acceleration by elapsed time before adding initial velocity.'])
template(3,'Calculate','A particle moves in a straight line with initial velocity $[[u]]\\,\\mathrm{m\\,s^{-1}}$ and constant acceleration $[[a]]\\,\\mathrm{m\\,s^{-2}}$ for $[[t]]\\,\\mathrm{s}$. Calculate its displacement.','m',
    {'u':[2,4,6],'a':[2,4],'t':[3,5]},'u*t+0.5*a*t*t',[('u*t+a*t*t','m4'),('0.5*a*t*t','m1')],
    'Use $s=ut+\\tfrac12at^2$ and include both the initial-velocity and acceleration terms.',
    ['Displacement depends on starting velocity as well as acceleration.','Choose the suvat equation without final velocity.','Calculate $ut$ and $\\tfrac12at^2$ separately, then add.'])
template(4,'Find','A particle has initial velocity $[[u]]\\,\\mathrm{m\\,s^{-1}}$ and constant acceleration $[[a]]\\,\\mathrm{m\\,s^{-2}}$. Find its displacement when its velocity first reaches $[[v]]\\,\\mathrm{m\\,s^{-1}}$.','m',
    {'u':[2,4],'a':[2,4],'v':[10,14]},'(v*v-u*u)/(2*a)',[('(v*v-u*u)/a','m4')],
    'Eliminate time with $v^2=u^2+2as$, giving $s=(v^2-u^2)/(2a)$.',
    ['Time is not given.','Use the suvat equation without time.','Subtract the squared initial velocity from the squared final velocity.'])
template(4,'Calculate','A particle starts from rest and accelerates uniformly at $[[a]]\\,\\mathrm{m\\,s^{-2}}$ for $[[t1]]\\,\\mathrm{s}$, then travels at its attained constant speed for $[[t2]]\\,\\mathrm{s}$. Calculate the total distance.','m',
    {'a':[2,4],'t1':[3,5],'t2':[2,4]},'0.5*a*t1*t1+a*t1*t2',[('a*t1*t1+a*t1*t2','m4')],
    'The velocity–time graph has a triangle during acceleration and a rectangle at constant speed; their areas add to the distance.',
    ['Split the journey into two intervals.','Find the final speed of the accelerating interval.','Add the triangle area to the rectangle area beneath the velocity–time graph.'])
template(4,'Find','A particle moves at $[[u]]\\,\\mathrm{m\\,s^{-1}}$ in the positive direction and has constant acceleration $-[[b]]\\,\\mathrm{m\\,s^{-2}}$ for $[[t]]\\,\\mathrm{s}$. Find its total distance travelled.','m',
    {'u':[6,8],'b':[2,4],'t':[4,5]},'u*u/(2*b)+0.5*b*(t-u/b)**2',[('u*t-0.5*b*t*t','m2'),('u*u/(2*b)-0.5*b*(t-u/b)**2','m2')],
    'The particle turns at $u/b$ seconds. Add the positive outward distance $u^2/(2b)$ and the distance after reversal $\\tfrac12b(t-u/b)^2$.',
    ['Check whether velocity changes sign.','Find the turning time using $v=u-bt$.','Find the two positive distances on either side of the turn and add.'],['t>u/b'])
mcq(2,'State','State what the gradient of a velocity–time graph represents.',
    ['Acceleration','Displacement','Distance','Velocity'],'A',{'B':'m3','C':'m3'},
    'The gradient is change in velocity divided by change in time: acceleration. Displacement comes from signed area under the graph.',
    ['Think of rise divided by run.','The vertical axis measures velocity and the horizontal axis measures time.','Write the units of the gradient.'])
peak, final, first_time, second_time = 4, -2, 2, 3
first_area=(0+peak)*first_time/2
second_signed=(peak+final)*second_time/2
second_positive=peak*(peak/(peak-final))/2*second_time
second_negative=abs(final)*(abs(final)/(peak-final))/2*second_time
displacement=first_area+second_signed
distance=first_area+second_positive+second_negative
wrong_unsigned=first_area+abs(peak*second_time/2)
wrong_second_only=second_signed
assert (displacement,distance,wrong_unsigned,wrong_second_only)==(7,9,10,3)
def metres(n): return f'${n:g}\\,\\mathrm{{m}}$'
mcq(3,'State','A velocity–time graph has a straight line from $0$ to $4\\,\\mathrm{m\\,s^{-1}}$ over $2\\,\\mathrm{s}$, then a straight line to $-2\\,\\mathrm{m\\,s^{-1}}$ over the next $3\\,\\mathrm{s}$. State the displacement over the $5\\,\\mathrm{s}$.',
    [metres(displacement),metres(distance),metres(wrong_unsigned),metres(wrong_second_only)],'A',{'B':'m2','C':'m2'},
    'The first triangle has area $4$ m. The second trapezium has signed area $3$ m, giving $7$ m; adding the area below the axis positively gives distance, not displacement.',
    ['Areas below the time axis have a negative sign.','Split the graph into the first triangle and the later trapezium.','Use average velocity times time for each straight segment.'])
short(3,'Explain','Explain how displacement, velocity, speed and acceleration can be read from displacement–time, velocity–time, speed–time and acceleration–time graphs.',[
    ('The gradient of a displacement–time graph gives velocity.',[['gradient'],['displacement'],['velocity']]),
    ('The gradient of a velocity–time graph gives acceleration.',[['gradient'],['velocity'],['acceleration']]),
    ('Signed area under velocity–time gives displacement, while area under speed–time gives distance.',[['area'],['displacement'],['distance']]),
    ('Signed area under acceleration–time gives change in velocity.',[['area'],['acceleration'],['change','difference'],['velocity']])],
    'A graph gradient compares change in the vertical quantity with time; an area multiplies the vertical quantity by time. Keep the sign for vector quantities.',
    ['Match the vertical axis to the quantity.','Use slope for rates of change and area for accumulated change.','Distinguish signed velocity from nonnegative speed.'])
short(4,'Explain','A particle has velocity $-3\\,\\mathrm{m\\,s^{-1}}$ and constant acceleration $-2\\,\\mathrm{m\\,s^{-2}}$. Explain what happens to its speed over the next second and why.',[
    ('Its speed increases from $3$ to $5\\,\\mathrm{m\\,s^{-1}}$.',[['increase'],['3'],['5']]),
    ('Velocity and acceleration point in the same negative direction, so the magnitude of velocity increases.',[['same'],['negative'],['magnitude','speed']])],
    'Using $v=u+at$ gives $v=-5\\,\\mathrm{m\\,s^{-1}}$ after one second. The speed is its magnitude, $5\\,\\mathrm{m\\,s^{-1}}$, so negative acceleration does not by itself mean slowing.',
    ['Keep direction signs separate from speed.','Use $v=u+at$ for one second.','Compare the magnitudes of the initial and final velocities.'])
short(4,'Sketch','Sketch a velocity–time and a displacement–time graph for a particle starting with positive velocity and moving with constant negative acceleration, until it stops. Label each graph’s key features.',[
    ('Velocity–time is a straight line with negative gradient from positive velocity to zero.',[['straight'],['negative'],['zero']]),
    ('Displacement–time rises with decreasing gradient and reaches a horizontal tangent at the stop.',[['rise','increase'],['decreasing','reducing'],['horizontal']])],
    'Constant negative acceleration gives a linearly decreasing velocity. Because displacement gradient equals velocity, the displacement curve rises but flattens to a horizontal tangent at rest.',
    ['A constant acceleration fixes the velocity graph gradient.','Velocity is the displacement graph gradient.','Mark the stop where velocity reaches zero.'])

# Worked numbers are computed from the stated motion, then inserted into prose.
u,a,t=3,2,4
v=u+a*t
s=u*t+0.5*a*t*t
faded_u,faded_a,faded_t=5,3,4
faded_s=faded_u*faded_t+0.5*faded_a*faded_t**2
assert (v,s,faded_s)==(11,28,44)
pack['worked'].append(dict(id='we1',kc=KC,problem=f'A particle has initial velocity ${u}\\,\\mathrm{{m\\,s^{{-1}}}}$ and constant acceleration ${a}\\,\\mathrm{{m\\,s^{{-2}}}}$ for ${t}\\,\\mathrm{{s}}$. Find its final velocity and displacement.',steps=[
    {'do':f'Choose the direction of motion as positive and list $u={u}$, $a={a}$, $t={t}$.','why':'Signed values must be consistent before selecting equations.'},
    {'do':f'Use $v=u+at={u}+({a})({t})={v}\\,\\mathrm{{m\\,s^{{-1}}}}$.','why':'Acceleration is constant, and this equation uses the three known values.','check':{'kind':'numeric','answer':ans(v,'m s^-1')}},
    {'do':f'Use $s=ut+\\tfrac12at^2=({u})({t})+\\tfrac12({a})({t})^2={s:g}\\,\\mathrm{{m}}$.','why':'This equation calculates signed displacement over the whole interval.','check':{'kind':'numeric','answer':ans(s,'m')}}],
    faded={'id':'we1f','problem':f'A particle has initial velocity ${faded_u}\\,\\mathrm{{m\\,s^{{-1}}}}$ and constant acceleration ${faded_a}\\,\\mathrm{{m\\,s^{{-2}}}}$ for ${faded_t}\\,\\mathrm{{s}}$. Find its displacement.','answer':ans(faded_s,'m'),'blank_from':1}))

# Verify all fixed numerical content with the same equations used in the explanations.
assert 0.5*2*4 == 4
assert (4+(-2))/2*3 == 3
assert 4+3 == 7
assert abs(4)+abs(0.5*4*2)+abs(0.5*2*1) == 9
assert -3+(-2)*1 == -5
assert len(pack['items'])==10
out=ROOT/'build/out/packs/M1/M1-3.json'
out.parent.mkdir(parents=True,exist_ok=True)
out.write_text(json.dumps(pack,ensure_ascii=False,indent=1)+'\n')
print(out)
