"""Generate the P1-4 differentiation pack; numerical values come from SymPy."""
import json
from pathlib import Path
import sympy as s

ROOT = Path(__file__).resolve().parents[3]
OUT = ROOT / 'build/out/packs/P1/P1-4.json'
x = s.symbols('x')
K = ['P1-4.1', 'P1-4.2', 'P1-4.3']
def val(expr):
    return float(s.N(expr, 14))
def ans(expr):
    return {'value': val(expr), 'unit': '', 'sf_ok': [2, 3]}
def check(actual, expected):
    assert s.simplify(actual-expected) == 0
    return ans(actual)
def item(k, kind, stem, answer=None, options=None, explanation='', difficulty=2, word='Find', distractors=None, template=None):
    n = len(pack['items'])+1
    d = {'id':f'P1-4-i{n:02}', 'kcs':[K[k]], 'kind':kind, 'difficulty':difficulty,
         'command_word':word, 'source':{'type':'generated'}, 'stem':stem, 'marks':1,
         'explanation':explanation, 'hints':['Identify the curve and the requested quantity.',
         'Use the derivative or a secant-gradient limit as appropriate.',
         'Write the relevant expression before substituting.']}
    if kind == 'mcq':
        d.update(options=options, answer=answer, shuffle=True, distractors=distractors or {})
    elif kind == 'numeric':
        d.update(answer=answer, distractors=distractors or [])
        if template: d['template']=template
    elif kind == 'expression': d['answer']={'expr':answer}
    pack['items'].append(d)

pack={'subtopic':'P1-4','spec':'P1','version':1,
 'note':'Subjects/Maths/P1 Pure Mathematics 1/4 Differentiation.md',
 'outline':'A derivative is the limiting gradient of a secant, so $f\'(a)$ is the tangent gradient and the instantaneous rate of change at $x=a$. A second derivative describes how that gradient changes. Differentiate powers with $\\frac{d}{dx}x^n=nx^{n-1}$, applying sums and constant multiples term by term; expand products or divide each term before differentiating. A tangent uses gradient $f\'(a)$ at $(a,f(a))$; a normal has the negative reciprocal gradient when the tangent gradient is nonzero.',
 'misconceptions':[
  {'id':'m1','kc':K[0],'statement':'The derivative at a point is the gradient of a finite secant.','refutation':'The tangent gradient is the limit as the second point approaches the first.','contrast':'Use $\\lim_{h\\to0}[f(a+h)-f(a)]/h$.','source':'research'},
  {'id':'m2','kc':K[1],'statement':'Differentiate a product by differentiating each factor and multiplying.','refutation':'For this syllabus, expand the product first; differentiating factors separately gives the wrong polynomial.','contrast':'$(2x+5)(x-1)=2x^2+3x-5$, whose derivative is $4x+3$.','source':'research'},
  {'id':'m3','kc':K[1],'statement':'The derivative of $x^n$ is $nx^n$.','refutation':'The exponent decreases by one.','contrast':'$\\frac{d}{dx}x^3=3x^2$.','source':'research'},
  {'id':'m4','kc':K[2],'statement':'A normal has the same gradient as the tangent.','refutation':'A normal is perpendicular to the tangent, so nonzero gradients multiply to $-1$.','contrast':'Tangent gradient $2$ means normal gradient $-1/2$.','source':'research'}],
 'worked':[], 'items':[], 'flashcards':[], 'diagrams':[]}

f=x*x
check(s.limit((f.subs(x,3+s.Symbol('h'))-f.subs(x,3))/s.Symbol('h'),s.Symbol('h'),0),6)
pack['worked'].append({'id':'we1','kc':K[0],'problem':'Find the tangent gradient to $y=x^2$ at $x=3$ from a limit.',
 'steps':[{'do':'$m=\\lim_{h\\to0}[f(3+h)-f(3)]/h$.','why':'A tangent gradient is the limiting secant gradient.'},
 {'do':'$[(3+h)^2-9]/h=6+h$ for $h\\ne0$.','why':'Expand and cancel only before taking the limit.'},
 {'do':'As $h\\to0$, $m=6$.','why':'The limit gives the instantaneous gradient.','check':{'kind':'numeric','answer':ans(6)}}],
 'faded':{'id':'we1f','problem':'Use a limit to find the gradient of $y=x^2$ at $x=4$.','answer':check(s.diff(f,x).subs(x,4),8),'blank_from':1}})

g=(2*x+5)*(x-1)
assert s.simplify(s.diff(s.expand(g),x)-(4*x+3)) == 0
pack['worked'].append({'id':'we2','kc':K[1],'problem':'Find $dy/dx$ for $y=(2x+5)(x-1)$.',
 'steps':[{'do':'Expand: $y=2x^2+3x-5$.','why':'The P1 power rule applies to a sum of powers.'},
 {'do':'Differentiate each term: $dy/dx=4x+3$.','why':'Use $\\frac{d}{dx}x^n=nx^{n-1}$; the constant differentiates to zero.'}],
 'faded':{'id':'we2f','problem':'Find $dy/dx$ at $x=2$ for $y=(x+3)(2x-1)$.','answer':check(s.diff(s.expand((x+3)*(2*x-1)),x).subs(x,2),13),'blank_from':1}})

q=x*x+1
check(s.diff(q,x).subs(x,2),4)
pack['worked'].append({'id':'we3','kc':K[2],'problem':'Find the tangent and normal to $y=x^2+1$ at $x=2$.',
 'steps':[{'do':'The point is $(2,5)$ and $dy/dx=2x$, so the tangent gradient is $4$.','why':'Both lines pass through the point on the curve.'},
 {'do':'Tangent: $y-5=4(x-2)$, hence $y=4x-3$.','why':'Use the point-gradient equation.'},
 {'do':'Normal gradient is $-1/4$, so $y-5=-\\frac14(x-2)$.','why':'Perpendicular nonzero gradients multiply to $-1$.','check':{'kind':'numeric','answer':ans(s.Rational(-1,4))}}],
 'faded':{'id':'we3f','problem':'Find the normal gradient to $y=x^2+1$ at $x=3$.','answer':check(-1/s.diff(q,x).subs(x,3),s.Rational(-1,6)),'blank_from':1}})

# One parameterised retrieval item plus three fixed items per KC = six variants each.
item(0,'numeric','Find the limiting secant gradient of $y=x^2$ at $x=[[a]]$.',ans(4),
 explanation='The difference quotient is $2a+h$; its limit is $2a$.',
 template={'params':{'a':{'min':2,'max':8,'step':1}},'derived':{},'answer':'2*a',
           'distractors':[{'expr':'a*a','misconception':'m1'}],'constraints':['a != 2']})
item(0,'mcq','Interpret $dy/dx$ at a point on a displacement-time graph.', 'A',
 {'A':'The instantaneous rate of change of displacement with time','B':'The total displacement','C':'The average rate over the whole interval','D':'The rate of change of time with displacement'},
 'It is the tangent gradient, or instantaneous velocity; an average over a finite interval uses a secant.',word='Interpret',distractors={'C':'m1'})
item(0,'mcq','State what $f\'\'(x)$ measures.', 'A',
 {'A':'The rate of change of $f\'(x)$ with $x$','B':'The square of $f\'(x)$','C':'The gradient of a secant over a fixed interval','D':'The reciprocal of $f\'(x)$'},
 'The second derivative is the derivative of the first derivative.',word='State')
item(0,'mcq','Find the gradient of $y=x^2$ at $x=5$.', 'A',
 {'A':'$10$','B':'$25$','C':'$5$','D':'$2$'},
 'The limiting gradient is $2x$, giving $10$ at $x=5$.',difficulty=4,distractors={'B':'m1'})

item(1,'numeric','Find $dy/dx$ at $x=[[a]]$ for $y=[[c]]x^3+2x$.',ans(14),
 explanation='Apply the power and sum rules: $dy/dx=3cx^2+2$.',
 template={'params':{'a':{'min':2,'max':6,'step':1},'c':{'min':1,'max':4,'step':1}},
           'derived':{},'answer':'3*c*a*a+2',
           'distractors':[{'expr':'3*c*a*a*a+2','misconception':'m3'}],'constraints':[]})
item(1,'expression','Find $dy/dx$ for $y=5x^4-3x^2+7$.','20*x**3-6*x',
 explanation='Differentiate each power separately and remove the constant.')
item(1,'mcq','Find $dy/dx$ for $y=(2x+5)(x-1)$.','A',
 {'A':'$4x+3$','B':'$4x-2$','C':'$2x^2+3x-5$','D':'$4x^2+3$'},
 'Expand to $2x^2+3x-5$ first, then differentiate to $4x+3$.',distractors={'B':'m2','D':'m3'})
item(1,'expression','Find $dy/dx$ for $y=(2x^2+5x-3)/(3x)$.','2/3+1/x**2',
 explanation='Rewrite as $2x/3+5/3-1/x$; differentiate term by term.',difficulty=4)

item(2,'numeric','Find the tangent gradient to $y=x^2+1$ at $x=[[a]]$.',ans(6),
 explanation='Differentiate to $2x$ and substitute the given coordinate.',
 template={'params':{'a':{'min':2,'max':8,'step':1}},'derived':{},'answer':'2*a',
           'distractors':[{'expr':'a*a+1','misconception':'m4'}],'constraints':['a != 2']})
item(2,'mcq','Find the normal gradient to $y=x^2$ at $x=1$.','A',
 {'A':'$-1/2$','B':'$2$','C':'$1/2$','D':'$-2$'},
 'The tangent gradient is $2$; the normal gradient is its negative reciprocal.',distractors={'B':'m4'})
item(2,'mcq','Find the tangent to $y=x^2+1$ at $x=2$.','A',
 {'A':'$y=4x-3$','B':'$y=4x+5$','C':'$y=2x+1$','D':'$y=-x/4+11/2$'},
 'The point is $(2,5)$ and tangent gradient is $4$, hence $y-5=4(x-2)$.',difficulty=4,distractors={'D':'m4'})
item(2,'mcq','Find the normal to $y=x^2$ at the origin.','A',
 {'A':'$x=0$','B':'$y=0$','C':'$y=x$','D':'$y=-x$'},
 'The tangent gradient is zero, so the tangent is horizontal and the normal is vertical.',difficulty=4,distractors={'B':'m4'})

pack['flashcards']=[
 {'id':'fc1','kc':K[0],'front':'State the meaning of $f\'(a)$.','back':'The gradient of the tangent to $y=f(x)$ at $x=a$, or the instantaneous rate of change of $f$ with respect to $x$.'},
 {'id':'fc2','kc':K[0],'front':'State the limiting-gradient definition.','back':'$f\'(a)=\\lim_{h\\to0}\\frac{f(a+h)-f(a)}{h}$, when this limit exists.'},
 {'id':'fc3','kc':K[0],'front':'State the meaning of $f\'\'(x)$.','back':'The rate of change of $f\'(x)$ with respect to $x$.'},
 {'id':'fc4','kc':K[1],'front':'State the power rule.','back':'$\\frac{d}{dx}(x^n)=nx^{n-1}$.'},
 {'id':'fc5','kc':K[2],'front':'State the gradient relation for a normal.','back':'At a point with nonzero tangent gradient $m$, the normal gradient is $-1/m$.'}]
OUT.parent.mkdir(parents=True,exist_ok=True)
OUT.write_text(json.dumps(pack,ensure_ascii=False,indent=1)+'\n')
print(f'wrote {OUT}: {len(pack["items"])} items')
