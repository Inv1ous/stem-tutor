import json
from pathlib import Path
import sympy as s

ROOT = Path(__file__).resolve().parents[3]
OUT = ROOT / 'build/out/packs/P2/P2-7.json'
K = 'P2-7.1'
x = s.symbols('x', real=True)
f = x**3-6*x**2+9*x+1
fp = s.diff(f,x)
roots = s.solve(fp,x)
assert roots == [1,3]
assert [f.subs(x,r) for r in roots] == [5,1]
assert [s.diff(f,x,2).subs(x,r) for r in roots] == [-6,6]

def base(n,kind,stem,marks,difficulty,word,explanation):
    return dict(id=f'P2-7-i{n:02}',kcs=[K],kind=kind,difficulty=difficulty,
        command_word=word,source={'type':'generated'},stem=stem,marks=marks,
        explanation=explanation,hints=['Differentiate before choosing an interval.','Picture the tangent at a stationary point. What does its direction tell you about its gradient?','Use a sign table or the second derivative, then substitute into the original function.'])

def short(n,stem,points,difficulty,word,explanation):
    a=base(n,'short',stem,len(points),difficulty,word,explanation)
    a['rubric']=[{'point':p,'keywords':[[k]]} for p,k in points]
    return a

def mcq(n,stem,options,key,difficulty,explanation,ds={}):
    a=base(n,'mcq',stem,1,difficulty,'Find',explanation)
    a.update(options={k:options[k] for k in 'ABCD'},answer=key,distractors=ds,shuffle=True)
    assert len(set(options.values()))==4
    return a

def val(z): return s.sstr(s.simplify(z))
I=[]
I.append(short(1,'State the condition on $f\'(x)$ at a stationary point.',[('The first derivative is zero.','zero')],1,'State','A stationary point has gradient zero, so $f\'(x)=0$.'))
I.append(short(2,'Explain how the sign of $f\'(x)$ determines where a differentiable function is increasing or decreasing.',[('Positive derivative means increasing.','positive'),('Negative derivative means decreasing.','negative')],2,'Explain','A positive tangent gradient gives an increasing function; a negative gradient gives a decreasing function.'))
I.append(mcq(3,'Find the nature of the stationary point at $x=1$ for $f(x)=x^3-6x^2+9x+1$.',
    {'A':'Local maximum','B':'Local minimum','C':'Stationary point of inflection','D':'No stationary point'},'A',2,
    'Here $f\'(1)=0$ and $f\'\'(1)=-6<0$, so the curve turns from increasing to decreasing.',{'B':'m1','C':'m2'}))
I.append(mcq(4,'Find the intervals where $f(x)=x^3-6x^2+9x+1$ is increasing.',
    {'A':'$x<1$ and $x>3$','B':'$1<x<3$','C':'$x<3$','D':'$x>1$'},'A',3,
    '$f\'(x)=3(x-1)(x-3)$ is positive outside its two roots and negative between them.',{'B':'m3'}))
I.append(short(5,'Find and classify all stationary points of $y=x^3-6x^2+9x+1$.',
    [('Solve $3(x-1)(x-3)=0$ to obtain $x=1,3$.','1'),('The points are $(1,5)$ and $(3,1)$.','5'),('At $x=1$ there is a maximum and at $x=3$ a minimum.','maximum')],4,'Find',
    'The derivative vanishes at $1$ and $3$. The second derivative is negative at $1$ and positive at $3$; substitute into $y$ for the coordinates.'))
# Parametric maximum: A(x)=x(P/2-x), x in (0,P/2). Both coefficients and result are symbolic.
P=s.symbols('P',positive=True)
area=x*(P/s.Integer(2)-x)
xmax=s.solve(s.diff(area,x),x)[0]
assert s.simplify(xmax-P/4)==0
assert s.simplify(area.subs(x,xmax)-P**2/16)==0
assert s.diff(area,x,2)==-2
numeric=base(6,'numeric','A rectangle has perimeter $[[P]]$ cm. Find its maximum area in $\\mathrm{cm^2}$.',1,4,'Find',
    'If one side is $x$, the other is $P/2-x$. The area $A=x(P/2-x)$ has $A\'=P/2-2x=0$ at $x=P/4$; $A\'\'=-2<0$, so the maximum is $P^2/16$.')
numeric.update(answer={'unit':'cm^2','sf_ok':[2,3]},template={'params':{'P':{'min':20,'max':60,'step':4}},'derived':{'half':'P/2'},'answer':'P**2/16',
    'distractors':[{'expr':'P**2/4','misconception':'m4'},{'expr':'P**2/8','misconception':'m4'}], 'constraints':['P>0']})
I.append(numeric)
I.append(short(7,'Sketch $y=x^3-6x^2+9x+1$, labelling its two stationary points and indicating where the curve rises and falls.',
    [('Local maximum at $(1,5)$.','1'),('Local minimum at $(3,1)$.','3'),('Rises for $x<1$ and $x>3$, falls for $1<x<3$.','rises'),('Crosses the $y$-axis at $(0,1)$ and has cubic end behaviour.','axis')],5,'Sketch',
    'The positive leading coefficient makes the left tail descend and right tail ascend. The gradient signs and stationary coordinates determine the turns; $f(0)=1$.'))
I.append(short(8,'Explain why $y=x^3$ has a stationary point at $x=0$ but neither a local maximum nor a local minimum there.',
    [('$y\'=3x^2$ is zero at $x=0$.','zero'),('The derivative is positive on both sides, so the curve is increasing through the point.','positive')],3,'Explain',
    'Although the tangent is horizontal at the origin, $3x^2$ does not change sign. This is a stationary point of inflection.'))
worked=[{'id':'we1','kc':K,'problem':'Find and classify the stationary points of $y=x^3-6x^2+9x+1$, and state its decreasing interval.',
 'steps':[{'do':'Differentiate: $y\'=3x^2-12x+9=3(x-1)(x-3)$.','why':'Stationary points occur where the tangent gradient is zero.'},
 {'do':'Set $y\'=0$: $x=1$ or $x=3$. Substitute into $y$: $(1,5)$ and $(3,1)$.','why':'The derivative gives the $x$-coordinates; the original function gives the $y$-coordinates.'},
 {'do':'$y\'\'=6x-12$: at $1$ it is $-6$, so $(1,5)$ is a local maximum; at $3$ it is $6$, so $(3,1)$ is a local minimum.','why':'A negative second derivative indicates concave down, a positive one concave up.'},
 {'do':'$3(x-1)(x-3)<0$ for $1<x<3$; the function decreases there.','why':'The sign of the first derivative, rather than the height of the curve, determines decreasing behaviour.'}],
 'faded':{'id':'we1f','problem':'For $y=x^3-6x^2+9x+1$, find the $x$-coordinate of the local minimum.','answer':{'value':float(roots[1]),'unit':'','sf_ok':[2,3]},'blank_from':1}},
 {'id':'we2','kc':K,'problem':'A rectangle has perimeter $40$ cm. Find its greatest possible area.',
 'steps':[{'do':'Let one side be $x$ cm; the other is $20-x$ cm, so $A=x(20-x)$.','why':'The perimeter constraint expresses area in one variable.'},
 {'do':'$A\'=20-2x=0$ gives $x=10$ cm.','why':'An interior optimum must be stationary.'},
 {'do':'$A\'\'=-2<0$, so the area is a maximum. $A(10)=100\\,\\mathrm{cm^2}$.','why':'Classify the stationary value and report the quantity requested.'}],
 'faded':{'id':'we2f','problem':'A rectangle has perimeter $48$ cm. Find its greatest possible area in $\\mathrm{cm^2}$.','answer':{'value':float((s.Integer(48)**2)/16),'unit':'cm^2','sf_ok':[2,3]},'blank_from':1}}]
pack={'subtopic':'P2-7','spec':'P2','version':1,'note':'Subjects/Maths/P2 Pure Mathematics 2/7 Differentiation.md',
 'outline':'Differentiate to locate stationary points from $f\'(x)=0$. Substitute into $f$ for coordinates. Classify by the sign change of $f\'$ or by $f\'\'$ when nonzero. Positive $f\'$ means increasing; negative $f\'$ means decreasing. Combine turning points, intercepts and end behaviour to sketch curves. In practical maxima and minima, first express the quantity to optimise as a function of one variable, find stationary candidates, and check endpoints and the domain.',
 'misconceptions':[{'id':'m1','kc':K,'statement':'A positive second derivative indicates a maximum.','refutation':'At a stationary point, $f\'\'>0$ indicates a local minimum.','contrast':'Concave up gives a minimum; concave down gives a maximum.','source':'research'},
 {'id':'m2','kc':K,'statement':'Every stationary point is a turning point.','refutation':'$y=x^3$ has $y\'(0)=0$ but continues increasing through the origin.','contrast':'Check the derivative sign on each side.','source':'research'},
 {'id':'m3','kc':K,'statement':'The derivative is positive between any two stationary points.','refutation':'For $3(x-1)(x-3)$ it is negative when $1<x<3$.','contrast':'Test the sign in each interval.','source':'research'},
 {'id':'m4','kc':K,'statement':'Use the whole perimeter as a rectangle side length.','refutation':'For perimeter $P$, adjacent sides sum to $P/2$.','contrast':'Write the perimeter constraint before forming the area.','source':'research'}],
 'worked':worked,'items':I,'flashcards':[{'id':'fc1','kc':K,'front':'What is a stationary point?','back':'A point on a curve where the gradient is zero, so $f\'(x)=0$.'},{'id':'fc2','kc':K,'front':'How do derivative signs identify increasing and decreasing intervals?','back':'A function is increasing where $f\'(x)>0$ and decreasing where $f\'(x)<0$.'}], 'diagrams':[]}
OUT.parent.mkdir(parents=True,exist_ok=True)
OUT.write_text(json.dumps(pack,ensure_ascii=False,indent=1)+'\n')
