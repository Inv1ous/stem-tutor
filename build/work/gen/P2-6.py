import json
from pathlib import Path
import sympy as s

ROOT = Path(__file__).resolve().parents[3]
OUT = ROOT / 'build/out/packs/P2/P2-6.json'
K1, K2 = 'P2-6.1', 'P2-6.2'
pi = s.pi
assert s.simplify(s.sin(pi/6)**2+s.cos(pi/6)**2)==1
assert s.simplify(s.tan(pi/4)-s.sin(pi/4)/s.cos(pi/4))==0

def short(n,k,stem,points,explanation,difficulty=2,word='Find'):
    return dict(id=f'P2-6-i{n:02}',kcs=[k],kind='short',difficulty=difficulty,
        command_word=word,source={'type':'generated'},stem=stem,marks=len(points),
        rubric=[{'point':p,'keywords':[[q]]} for p,q in points],explanation=explanation,
        hints=['Recall the relevant identity or trig graph.','Write the equation in one trig function.','Check the specified domain and endpoints.'])
def mcq(n,k,stem,options,answer,explanation,difficulty=2,distractors=None):
    assert len(set(options.values()))==4 and answer in options
    return dict(id=f'P2-6-i{n:02}',kcs=[k],kind='mcq',difficulty=difficulty,
        command_word='Find',source={'type':'generated'},stem=stem,marks=1,options=options,
        answer=answer,distractors=distractors or {},shuffle=True,explanation=explanation,
        hints=['Recall an identity or reference angle.','Consider the signs in each quadrant.','Substitute a candidate into the original equation.'])
I=[]
I.append(short(1,K1,'State the identity relating $\\tan\\theta$, $\\sin\\theta$ and $\\cos\\theta$.',[('$\\tan\\theta=\\sin\\theta/\\cos\\theta$','tan')],'Tangent is sine divided by cosine, provided cosine is nonzero.',1,'State'))
I.append(short(2,K1,'State the Pythagorean identity for sine and cosine.',[('$\\sin^2\\theta+\\cos^2\\theta=1$','sin')],'The squares of sine and cosine sum to one for every angle.',1,'State'))
I.append(mcq(3,K1,'Given $\\sin\\theta=3/5$ and $\\cos\\theta=4/5$, find $\\tan\\theta$.',{'A':'$3/4$','B':'$4/3$','C':'$7/5$','D':'$12/25$'},'A','Divide sine by cosine: $(3/5)/(4/5)=3/4$.',distractors={'B':'m1','D':'m1'}))
I.append(mcq(4,K1,'Given $\\sin\\theta=5/13$ and $\\theta$ is in quadrant II, find $\\cos\\theta$.',{'A':'$-12/13$','B':'$12/13$','C':'$-5/13$','D':'$-144/169$'},'A','The identity gives $|\\cos\\theta|=12/13$; cosine is negative in quadrant II.',distractors={'B':'m2'}))
I.append(short(5,K1,'Show that $1-\\cos^2\\theta=\\sin^2\\theta$.',[('Start from $\\sin^2\\theta+\\cos^2\\theta=1$.','sin'),('Subtract $\\cos^2\\theta$ from both sides.','subtract')],'Rearrange the Pythagorean identity.',3,'Show that'))
I.append(short(6,K1,'Prove that $(1-\\sin^2\\theta)/\\cos\\theta=\\cos\\theta$ wherever $\\cos\\theta\\ne0$.',[('Replace $1-\\sin^2\\theta$ by $\\cos^2\\theta$.','cos'),('Cancel one factor of $\\cos\\theta$, noting $\\cos\\theta\\ne0$.','cancel')],'The identity makes the numerator $\\cos^2\\theta$; the denominator may be cancelled only where it is nonzero.',4,'Prove'))
I.append(mcq(7,K2,'Find all solutions of $\\sin x=1/2$ for $0\\le x<360^{\\circ}$.',{'A':'$30^{\\circ},150^{\\circ}$','B':'$30^{\\circ}$','C':'$30^{\\circ},330^{\\circ}$','D':'$150^{\\circ},210^{\\circ}$'},'A','Sine is positive in quadrants I and II, giving $30^{\\circ}$ and $150^{\\circ}$.',distractors={'B':'m3','C':'m4'}))
I.append(mcq(8,K2,'Find all solutions of $\\tan 2x=1$ for $90^{\\circ}<x<270^{\\circ}$.',{'A':'$112.5^{\\circ},202.5^{\\circ}$','B':'$22.5^{\\circ},112.5^{\\circ}$','C':'$112.5^{\\circ}$','D':'$135^{\\circ},225^{\\circ}$'},'A','Here $180^{\\circ}<2x<540^{\\circ}$; $2x=225^{\\circ},405^{\\circ}$, then halve.',4,{'B':'m5','C':'m3'}))
I.append(short(9,K2,'Find all solutions of $\\cos(x+30^{\\circ})=1/2$ for $-180^{\\circ}<x<180^{\\circ}$.',[('Set $u=x+30^{\\circ}$ so $-150^{\\circ}<u<210^{\\circ}$.','interval'),('Use $u=-60^{\\circ},60^{\\circ}$.','60'),('Hence $x=-90^{\\circ},30^{\\circ}$.','90')],'The shifted interval contains both $-60^{\\circ}$ and $60^{\\circ}$.',4))
I.append(short(10,K2,'Find all solutions of $\\sin(x+\\pi/2)=3/4$ for $0<x<2\\pi$. Give exact answers using $\\arccos$.',[('Use $\\sin(x+\\pi/2)=\\cos x$.','cos'),('Set $\\alpha=\\arccos(3/4)$.','arccos'),('The solutions are $x=\\alpha,2\\pi-\\alpha$.','pi')],'The equation is $\\cos x=3/4$, with two solutions in the open interval.',4))
I.append(short(11,K2,'Find all solutions of $6\\cos^2x+\\sin x-5=0$ for $0\\le x<360^{\\circ}$.',[('Replace $\\cos^2x$ by $1-\\sin^2x$.','sin'),('Factor $6\\sin^2x-\\sin x-1=(3\\sin x+1)(2\\sin x-1)$.','factor'),('For $\\sin x=1/2$, obtain $30^{\\circ},150^{\\circ}$; for $\\sin x=-1/3$, obtain $180^{\\circ}+\\arcsin(1/3)$ and $360^{\\circ}-\\arcsin(1/3)$.','arcsin')],'The identity gives a quadratic in sine. Both roots lie in the allowable range, so solve each over the full interval.',5))
I.append(short(12,K2,'Find all solutions of $\\sin(2x+\\pi/6)=1/2$ for $-\\pi\\le x<\\pi$.',[('Transform the interval to $-11\\pi/6\\le 2x+\\pi/6<13\\pi/6$.','interval'),('Use angles $-11\\pi/6,-7\\pi/6,\\pi/6,5\\pi/6$.','pi'),('Hence $x=-\\pi,-2\\pi/3,0,\\pi/3$.','pi')],'Solve for the transformed angle in its transformed interval, keeping the included left endpoint.',5))

def ans(v,unit=''):
    return {'value':float(s.N(v)),'unit':unit,'sf_ok':[2,3]}
worked=[{'id':'we1','kc':K2,'problem':'Find all solutions of $\\tan 2x=1$ for $90^{\\circ}<x<270^{\\circ}$.',
 'steps':[{'do':'Let $u=2x$, so $180^{\\circ}<u<540^{\\circ}$.','why':'Transform the interval together with the angle.'},
 {'do':'$\\tan u=1$ gives $u=225^{\\circ},405^{\\circ}$.','why':'Tangent repeats every $180^{\\circ}$; include every value in the transformed interval.'},
 {'do':'Divide by two: $x=112.5^{\\circ},202.5^{\\circ}$.','why':'Undo the substitution and check both satisfy the original bounds.'}],
 'faded':{'id':'we1f','problem':'Find the smallest solution of $\\tan 2x=1$ for $90^{\\circ}<x<270^{\\circ}$.','answer':ans(s.Rational(225,2)),'blank_from':1}}]
pack={'subtopic':'P2-6','spec':'P2','version':1,'note':'Subjects/Maths/P2 Pure Mathematics 2/6 Trigonometry.md',
 'outline':'Use $\\tan\\theta=\\sin\\theta/\\cos\\theta$ where cosine is nonzero and $\\sin^2\\theta+\\cos^2\\theta=1$. For equations, transform the interval with the angle, find every solution using quadrant signs and periodicity, reverse the transformation, and check endpoints.',
 'misconceptions':[{'id':'m1','kc':K1,'statement':'Tangent is a product or reciprocal of sine and cosine.','refutation':'$\\tan\\theta=\\sin\\theta/\\cos\\theta$.','contrast':'Divide sine by cosine, where cosine is nonzero.','source':'research'},
 {'id':'m2','kc':K1,'statement':'The square root from the identity is always positive.','refutation':'$\\cos\\theta=\\pm\\sqrt{1-\\sin^2\\theta}$; the quadrant fixes the sign.','contrast':'Find the magnitude, then use the quadrant.','source':'research'},
 {'id':'m3','kc':K2,'statement':'A calculator principal value is the only solution.','refutation':'Periodic trig graphs can give several solutions in an interval.','contrast':'Enumerate all quadrants and periods in the interval.','source':'research'},
 {'id':'m4','kc':K2,'statement':'Sine is positive in quadrant IV.','refutation':'Sine is negative in quadrant IV.','contrast':'For positive sine, inspect quadrants I and II.','source':'research'},
 {'id':'m5','kc':K2,'statement':'Keep the original interval after replacing $x$ by $2x$.','refutation':'Multiplying the angle by two also doubles its interval bounds.','contrast':'Transform the bounds before listing solutions.','source':'research'}],
 'worked':worked,'items':I,'flashcards':[{'id':'fc1','kc':K1,'front':'State the tangent identity.','back':'$\\tan\\theta=\\dfrac{\\sin\\theta}{\\cos\\theta}$, provided $\\cos\\theta\\ne0$.'},{'id':'fc2','kc':K1,'front':'State the Pythagorean trigonometric identity.','back':'$\\sin^2\\theta+\\cos^2\\theta=1$.'}], 'diagrams':[]}
OUT.parent.mkdir(parents=True,exist_ok=True)
OUT.write_text(json.dumps(pack,ensure_ascii=False,indent=1)+'\n')
