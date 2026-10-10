import json
from pathlib import Path
import sympy as s

ROOT = Path(__file__).resolve().parents[3]
OUT = ROOT / 'build/out/packs/P2/P2-8.json'
x = s.symbols('x')
K = ['P2-8.1', 'P2-8.2', 'P2-8.3']
def num(expr):
    return float(s.N(expr, 12))
def ans(v, unit=''):
    return {'value': num(v), 'unit': unit, 'sf_ok': [2, 3]}
def hints(a,b,c): return [a,b,c]
items=[]
def add(k, stem, value, explanation, hs, difficulty=3, unit='', distractors=None):
    n=len(items)+1
    items.append({'id':f'P2-8-i{n:02}', 'kcs':[K[k]], 'kind':'numeric', 'difficulty':difficulty,
      'command_word':'Find', 'source':{'type':'generated'}, 'stem':stem, 'marks':3,
      'answer':ans(value,unit), 'explanation':explanation, 'hints':hs,
      'distractors':distractors or []})
def short(k, stem, point, groups, explanation, hs, difficulty=2):
    n=len(items)+1
    items.append({'id':f'P2-8-i{n:02}', 'kcs':[K[k]], 'kind':'short','difficulty':difficulty,
      'command_word':'Explain','source':{'type':'generated'},'stem':stem,'marks':1,
      'rubric':[{'point':point,'keywords':groups}], 'explanation':explanation,'hints':hs})

for power, upper in [(2,3),(3,2),(4,2),(2,5)]:
    val=s.integrate(x**power,(x,0,upper))
    add(0,f'Find $\\int_0^{upper} x^{power}\\,dx$.',val,
        f'An antiderivative is $x^{power+1}/{power+1}$; evaluate it at the upper and lower limits.',
        hints('Recall the power rule for integration.','Find an antiderivative before using the limits.',
              'Start by increasing the power by one and dividing by the new power.'),2)
short(0,'Explain how limits $a$ and $b$ are used after finding an antiderivative $F(x)$.',
      'Evaluate the antiderivative at the upper limit and subtract its value at the lower limit.',
      [['upper','b'],['subtract','minus'],['lower','a']],
      'The fundamental theorem gives $\\int_a^b f(x)\\,dx=F(b)-F(a)$.',
      hints('Think of the order of the limits.','Apply the fundamental theorem of calculus.','Evaluate at the upper limit first.'))
short(0,'Explain why $\\int_2^2 f(x)\\,dx=0$ for continuous $f$.',
      'The upper and lower limits coincide, so the antiderivative values cancel.',
      [['same','coincide','equal'],['cancel','subtract','zero']],
      '$F(2)-F(2)=0$.',hints('Consider the interval width.','Apply the fundamental theorem.','Write $F(2)-F(2)$.'))

for a,b in [(4,1),(6,2),(8,3),(5,2),(7,1)]:
    # area enclosed by y=ax-x^2 and y=bx, with a>b
    d=a-b
    val=s.integrate(d*x-x*x,(x,0,d))
    add(1,f'Find the area bounded by $y={a}x-x^2$ and $y={b}x$.',val,
      f'The curves meet at $x=0$ and $x={d}$; integrate upper minus lower between those intersections.',
      hints('First find the intersections.','Subtract the lower curve from the upper curve.','Solve $({a}-{b})x-x^2=0$.'),
      4, '', [{'value':num(-val),'misconception':'m2'}])
short(1,'Explain how to calculate the area enclosed between $y=f(x)$ and $y=g(x)$ when $f(x)$ is above $g(x)$.',
      'Integrate upper curve minus lower curve between their intersections.',
      [['upper','above'],['lower','below'],['integrate','integral'],['intersection','limits']],
      'The area is $\\int_a^b(f(x)-g(x))\\,dx$, where $a,b$ are intersection coordinates.',
      hints('The integrand represents a vertical height.','Find the two boundary x-coordinates.','Write upper function minus lower function.'))

for n in [2,4,6,8,10]:
    # y=x^2 on [0,2], n equal strips
    h=s.Rational(2,n)
    ys=[(i*h)**2 for i in range(n+1)]
    val=h*(s.Rational(1,2)*ys[0]+sum(ys[1:-1])+s.Rational(1,2)*ys[-1])
    add(2,f'Calculate the trapezium-rule estimate for $\\int_0^2 x^2\\,dx$ using {n} equal strips.',val,
      f'The width is $2/{n}$; add the two endpoint heights with half weight and all interior heights with full weight.',
      hints('Find the common strip width.','Tabulate the function at every equally spaced x-value.',
            'Use half weights for the first and last ordinates.'),3,'',
      [{'value':num(h*sum(ys)),'misconception':'m3'}])
short(2,'Explain why the trapezium rule overestimates $\\int_0^2 x^2\\,dx$.',
      'The curve is convex, so each straight trapezium edge lies above the curve.',
      [['convex','curves upwards'],['above','overestimate']],
      'For $y=x^2$, the secant joining adjacent points lies above the curve; the trapezia include extra area.',
      hints('Compare each straight top edge with the curve.','Think about the curvature of $x^2$.',
            'Sketch y=x^2 from x=0 to x=1 and join the endpoints with a straight line. Compare the region beneath that line with the region beneath the curve.'))
items.append({'id':'P2-8-i19','kcs':['P2-8.3'],'kind':'short','difficulty':3,
  'command_word':'Calculate','source':{'type':'generated'},
  'stem':'For $I=\\int_0^2 x^2\\,dx$, the trapezium-rule estimates using two and four equal strips are $T_2=3$ and $T_4=11/4$. Calculate $I$ exactly and the absolute error of each estimate. State which estimate is more accurate and explain how the errors support your conclusion.',
  'marks':4,
  'rubric':[{'point':'$I=[x^3/3]_0^2=8/3$.','keywords':[['8/3','2.6666666667']]},
            {'point':'The two-strip absolute error is $|3-8/3|=1/3$.','keywords':[['1/3','0.3333333333']]},
            {'point':'The four-strip absolute error is $|11/4-8/3|=1/12$.','keywords':[['1/12','0.0833333333']]},
            {'point':'The four-strip estimate is more accurate because its absolute error is smaller (one quarter of the two-strip error).','keywords':[['four','4'],['smaller','less','quarter']]}],
  'explanation':'The exact integral is $8/3$. The absolute errors are $1/3$ for two strips and $1/12$ for four strips. Increasing the number of strips from two to four reduces the absolute error to one quarter, so the four-strip estimate is more accurate.',
  'hints':['First evaluate the integral using an antiderivative.','For each estimate, calculate the absolute difference from the exact integral.','Compare the two absolute errors; greater accuracy corresponds to a smaller error.']})

def worked(k, problem, steps, faded_problem, faded_value, unit=''):
    return {'id':f'we{k+1}','kc':K[k],'problem':problem,
      'steps':[{'do':d,'why':w,**({'check':{'kind':'numeric','answer':ans(v,unit)}} if v is not None else {})} for d,w,v in steps],
      'faded':{'id':f'we{k+1}f','problem':faded_problem,'answer':ans(faded_value,unit),'blank_from':1}}
worked_examples=[
 worked(0,'Find $\\int_1^3 2x\\,dx$.',[
   ('$\\int 2x\\,dx=x^2$','Use the reverse power rule.',None),
   ('$[x^2]_1^3=3^2-1^2$','Substitute upper limit, then lower limit.',None),
   ('$=8$','Evaluate the difference.',8)],'Find $\\int_0^4 3x^2\\,dx$.',64),
 worked(1,'Find the area between $y=6x-x^2$ and $y=2x$.',[
   ('$6x-x^2=2x$ gives $x=0,4$','Intersections are the limits.',None),
   ('$A=\\int_0^4(4x-x^2)\\,dx$','Integrate upper minus lower.',None),
   ('$A=[2x^2-x^3/3]_0^4=32/3$ square units','Evaluate both bounds.',s.Rational(32,3))],
   'Find the area between $y=5x-x^2$ and $y=x$.',s.Rational(32,3)),
 worked(2,'Estimate $\\int_0^2 x^2\\,dx$ with four trapezia.',[
   ('$h=(2-0)/4=1/2$','Equal strips have common width.',None),
   ('The ordinates are $0,1/4,1,9/4,4$.','Evaluate the function at all five endpoints.',None),
   ('$T=\\frac12[\\frac12(0)+\\frac14+1+\\frac94+\\frac12(4)]=11/4$ square units','Only endpoint ordinates are halved.',s.Rational(11,4))],
   'Estimate $\\int_0^2 x^2\\,dx$ with two trapezia.',3)]

pack={'subtopic':'P2-8','spec':'P2','version':1,'note':'Subjects/Maths/P2 Pure Mathematics 2/8 Integration.md',
 'outline':'Evaluate definite integrals by finding an antiderivative and subtracting its lower-limit value from its upper-limit value. For bounded area, find intersections and integrate the upper curve minus the lower curve. The trapezium rule approximates an integral using equal strips; endpoint ordinates have half weight. More strips usually improve accuracy.',
 'misconceptions':[
 {'id':'m1','kc':K[0],'statement':'Add the antiderivative values at the limits.','refutation':'The fundamental theorem requires $F(b)-F(a)$.','contrast':'Upper minus lower.','source':'research'},
 {'id':'m2','kc':K[1],'statement':'Subtract the upper curve from the lower curve when finding area.','refutation':'This makes the integral negative for a positive enclosed area.','contrast':'Integrate upper minus lower.','source':'research'},
 {'id':'m3','kc':K[2],'statement':'Give every ordinate full weight in the trapezium rule.','refutation':'The first and last ordinates belong to only one trapezium each.','contrast':'Halve the endpoint ordinates.','source':'research'}],
 'worked':worked_examples,'items':items,'flashcards':[], 'diagrams':[]}
OUT.parent.mkdir(parents=True,exist_ok=True)
OUT.write_text(json.dumps(pack,ensure_ascii=False,indent=2))
print(f'wrote {len(items)} items')
