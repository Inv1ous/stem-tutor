"""Generate and verify the P1-5 integration pack."""
import json
from pathlib import Path
import sympy as s
ROOT=Path(__file__).resolve().parents[3]
OUT=ROOT/'build/out/packs/P1/P1-5.json'
x=s.symbols('x', real=True, nonzero=True)
K=['P1-5.1','P1-5.2']
def expr(f): return str(s.expand(f))
def antiderivative(f):
    F=s.integrate(f,x)
    assert s.simplify(s.diff(F,x)-f)==0
    return F
def num(v): return {'value':float(s.N(v)), 'unit':'', 'sf_ok':[2,3]}
def mcq(k,stem,choices,correct,why,difficulty=2,word='Find',mis=None):
    assert len(choices)==4 and len(set(map(s.simplify,choices)))==4
    options={l:'$'+s.latex(v)+'$' for l,v in zip('ABCD',choices)}
    add(k,'mcq',stem,why,difficulty,word,options=options,answer='ABCD'[choices.index(correct)],shuffle=True,distractors=mis or {})
def add(k,kind,stem,explanation,difficulty=2,word='Find',**fields):
    n=len(pack['items'])+1
    row={'id':f'P1-5-i{n:02}','kcs':[K[k]],'kind':kind,'difficulty':difficulty,'command_word':word,'source':{'type':'generated'},'stem':stem,'marks':1,'explanation':explanation,'hints':['Identify the power of $x$ in each term.','Reverse differentiation, then consider the arbitrary constant.','Increase the exponent by one and divide by the new exponent.']}
    row.update(fields);pack['items'].append(row)
pack={'subtopic':'P1-5','spec':'P1','version':1,'note':'Subjects/Maths/P1 Pure Mathematics 1/5 Integration.md','outline':'Indefinite integration reverses differentiation: if $F\' (x)=f(x)$, then $\\int f(x)\\,dx=F(x)+C$. The constant $C$ represents every antiderivative with the same derivative. For $n\\ne-1$, $\\int x^n\\,dx=x^{n+1}/(n+1)+C$. Integrate sums, differences and constant multiples term by term. Expand a squared bracket or divide a numerator by a power of $x$ before applying the rule. If a point on a curve and $f\'(x)$ are given, integrate and substitute the point to determine $C$.','misconceptions':[
{'id':'m1','kc':K[0],'statement':'An indefinite integral has only one answer.','refutation':'Differentiating any constant gives zero, so all antiderivatives differ by a constant.','contrast':'$\\int 2x\\,dx=x^2+C$.','source':'research'},
{'id':'m2','kc':K[1],'statement':'Integrating $x^n$ keeps its exponent unchanged.','refutation':'The exponent increases by one and the coefficient is divided by that new exponent.','contrast':'$\\int x^2\\,dx=x^3/3+C$.','source':'research'},
{'id':'m3','kc':K[1],'statement':'The power rule applies when $n=-1$.','refutation':'The denominator $n+1$ would be zero; that case is excluded from this chapter.','contrast':'Use the rule only for $n\\ne-1$.','source':'research'},
{'id':'m4','kc':K[1],'statement':'The given point can be substituted into $f\'(x)$ to determine the constant.','refutation':'The point lies on $y=f(x)$, so substitute it into the integrated expression.','contrast':'If $f\'(x)=2x$ and $(1,4)$ lies on the curve, $4=1+C$, so $C=3$.','source':'research'}], 'worked':[],'items':[],'flashcards':[],'diagrams':[]}
F=antiderivative(2*x)
pack['worked'].append({'id':'we1','kc':K[0],'problem':'Find $\\int 2x\\,dx$ and explain the constant.','steps':[{'do':'Differentiate $x^2$: $d(x^2)/dx=2x$.','why':'Integration reverses differentiation.'},{'do':'Hence $\\int 2x\\,dx=x^2+C$.','why':'Every constant has derivative zero, so the full family needs $C$.'}], 'faded':{'id':'we1f','problem':'Find $\\int 4x^3\\,dx$, including the arbitrary constant.','answer':{'expr':expr(antiderivative(4*x**3))+' + C'},'blank_from':1}})
f=s.expand((x+2)**2); F=antiderivative(f)
assert s.simplify(F-(x**3/s.Integer(3)+2*x*x+4*x))==0
pack['worked'].append({'id':'we2','kc':K[1],'problem':'Find $\\int (x+2)^2\\,dx$.','steps':[{'do':'Expand: $(x+2)^2=x^2+4x+4$.','why':'This gives a sum of powers to integrate term by term.'},{'do':'Integrate: $x^3/3+2x^2+4x+C$.','why':'Increase each exponent and divide by its new value.'},{'do':'Differentiate the result to obtain $x^2+4x+4$.','why':'Differentiation checks the antiderivative.'}], 'faded':{'id':'we2f','problem':'Find $\\int (x+3)^2\\,dx$.','answer':{'expr':expr(antiderivative((x+3)**2))+' + C'},'blank_from':1}})
g=3*x*x-2*x; G=antiderivative(g); c=s.Integer(5)-G.subs(x,1); assert s.simplify(c-5)==0
pack['worked'].append({'id':'we3','kc':K[1],'problem':'Given $f\'(x)=3x^2-2x$ and the point $(1,5)$ on the curve, find $y=f(x)$.','steps':[{'do':'Integrate: $f(x)=x^3-x^2+C$.','why':'Reverse the derivative term by term, keeping the arbitrary constant.'},{'do':'At $(1,5)$, $5=1-1+C$, so $C=5$.','why':'The point satisfies the curve equation $y=f(x)$.'},{'do':'Therefore $y=x^3-x^2+5$.','why':'Substitute the determined constant into the family of curves.'}], 'faded':{'id':'we3f','problem':'Given $f\'(x)=2x+3$ and $f(1)=7$, find $f(0)$.','answer':num(7-antiderivative(2*x+3).subs(x,1)),'blank_from':1}})
# Conceptual retrieval: six distinct applications.
mcq(0,'State the indefinite integral of $2x$.',[x*x+ s.Symbol('C'),2*x*x,x*x,2],x*x+s.Symbol('C'),'Since $d(x^2+C)/dx=2x$, the constant is needed to describe every antiderivative.',word='State',mis={'C':'m1'})
add(0,'short','Explain why an indefinite integral includes $C$.','A constant differentiates to zero, so adding any constant leaves the derivative unchanged.',word='Explain',rubric=[{'point':'Any constant differentiates to zero, so the integral describes a family of antiderivatives.','keywords':[['constant'],['zero','0'],['derivative','differentiat']]}])
mcq(0,'Find a function whose derivative is $6x$.',[3*x*x+7,6*x*x,3*x,6],3*x*x+7,'Differentiating $3x^2+7$ gives $6x$; the constant vanishes.',mis={'B':'m2'})
mcq(0,'Verify which function has derivative $2x$ and value $4$ at $x=1$.',[x*x+3,x*x-5,x*x+x,2*x*x],x*x+3,'Differentiating $x^2+3$ gives $2x$, and its value at $x=1$ is $4$.',word='Verify')
add(0,'expression','Find $\\int 7\\,dx$.','The derivative of $7x+C$ is $7$.',answer={'expr':expr(antiderivative(s.Integer(7)))+' + C'})
add(0,'short','Explain why $x^3+2$ and $x^3-9$ are both antiderivatives of $3x^2$.','Their derivatives are both $3x^2$ because the constants disappear.',difficulty=4,word='Explain',rubric=[{'point':'Both differentiate to $3x^2$ because their constants have zero derivative.','keywords':[['differentiat','derivative'],['constant'],['zero','disappear']]}])
# Procedural retrieval: powers, brackets, quotients and point conditions.
for stem,integrand in [('Find $\\int 5x^4\\,dx$.',5*x**4),('Find $\\int (3x^2-4x+6)\\,dx$.',3*x*x-4*x+6),('Find $\\int (x+2)^2\\,dx$.',(x+2)**2),('Find $\\int (3x-1)/(2x^2)\\,dx$.',(3*x-1)/(2*x*x))]:
    a=antiderivative(integrand)
    if '/' in stem:
        a=s.Rational(3,2)*s.log(s.Abs(x))+s.Rational(1,2)/x
        assert s.simplify(s.diff(a,x)-integrand)==0
    add(1,'expression',stem,'Rewrite as powers if necessary, integrate each term, and add $C$.',difficulty=4 if '/' in stem else 2,answer={'expr':expr(a)+' + C'})
point_f=2*x+3; P=antiderivative(point_f); constant=s.Integer(7)-P.subs(x,1); v=P.subs(x,0)+constant
assert v==3
add(1,'numeric','Given $f\'(x)=2x+3$ and $f(1)=7$, find $f(0)$.','Integrate to $f(x)=x^2+3x+C$; the point gives $C=3$.',difficulty=4,answer=num(v),distractors=[{'value':float(P.subs(x,0)),'misconception':'m4'}])
mcq(1,'State which exponent is excluded from the power rule for integration.',[s.Integer(-1),s.Integer(0),s.Integer(1),s.Integer(2)],s.Integer(-1),'When $n=-1$, dividing by $n+1$ would divide by zero.',word='State',mis={'B':'m3'})
for front,back,k in [('What is indefinite integration?','Finding the family of functions whose derivative is the given function.',0),('Why is $C$ needed in an indefinite integral?','The derivative of every constant is zero, so antiderivatives can differ by a constant.',0),('State the power rule for integration.','$\\int x^n\\,dx=x^{n+1}/(n+1)+C$ for $n\\ne-1$.',1),('How is $C$ found when a point on the curve is given?','Integrate $f\'(x)$, then substitute the point into $y=f(x)$ and solve for $C$.',1)]:
 pack['flashcards'].append({'id':f'fc{len(pack["flashcards"])+1}','kc':K[k],'front':front,'back':back})
OUT.parent.mkdir(parents=True,exist_ok=True)
OUT.write_text(json.dumps(pack,ensure_ascii=False,indent=1))
