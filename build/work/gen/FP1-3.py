import json
from pathlib import Path
from fractions import Fraction
ROOT=Path(__file__).resolve().parents[3]
K='FP1-3.1'
N='Subjects/Maths/FP1 Further Pure Mathematics 1/3 Numerical solution of equations.md'
def f(x,c): return x*x-c
def a(v): return {'value':float(v),'unit':'','sf_ok':[2,3,4]}
def item(i,stem,value,explanation,hints,difficulty=3,ds=None):
 return {'id':f'FP1-3-i{i:02}','kcs':[K],'kind':'numeric','difficulty':difficulty,'command_word':'Calculate','source':{'type':'generated'},'stem':stem,'marks':2,'answer':a(value),'explanation':explanation,'hints':hints,'distractors':ds or []}
def bisection(lo,hi,c):
 mid=Fraction(lo+hi,2)
 assert f(lo,c)<0<f(hi,c)
 return mid
lo,hi,c=1,2,2
m=bisection(lo,hi,c)
items=[item(1,f'For $f(x)=x^2-{c}$, the root lies in $[{lo},{hi}]$. Calculate the first bisection midpoint.',m,'The midpoint is $(1+2)/2=1.5$; $f(1.5)>0$, so the retained interval is $[1,1.5]$.',['Use the endpoints of the bracket.','Take their arithmetic mean.','Add the two endpoints before dividing.'],2)]
lo,hi=Fraction(1),m
m2=bisection(lo,hi,c)
items.append(item(2,'For $f(x)=x^2-2$, the current bracket is $[1,1.5]$. Calculate the next bisection midpoint.',m2,'The midpoint is $1.25$ and $f(1.25)<0$, so the next bracket is $[1.25,1.5]$.',['Locate the two current endpoints.','Bisect the current bracket, not the original one.','Form the mean of $1$ and $1.5$.'],2))
def linear(lo,hi,c):
 fl,fh=f(lo,c),f(hi,c)
 assert fl<0<fh
 return Fraction(lo*fh-hi*fl,fh-fl)
r=linear(1,2,2)
items.append(item(3,'For $f(x)=x^2-2$, use linear interpolation between $x=1$ and $x=2$ to calculate a root estimate.',r,'The endpoint values are $-1$ and $2$. The secant meets the axis at $1-(-1)(2-1)/(2-(-1))=4/3$.',['Evaluate the function at each endpoint.','Use the straight line joining the two function values.','Substitute into $x=a-f(a)(b-a)/(f(b)-f(a))$.'],3))
r2=linear(Fraction(5,4),Fraction(3,2),2)
items.append(item(4,'For $f(x)=x^2-2$, use linear interpolation between $x=1.25$ and $x=1.50$ to calculate a root estimate.',r2,'Here $f(1.25)=-7/16$ and $f(1.5)=1/4$; the secant estimate is $31/22$.',['Find both signed function values.','Use the secant formula with $a=1.25$ and $b=1.5$.','Keep fractions until the final estimate.'],3))
def newton(x,c): return Fraction(x*x+c,2*x)
x=Fraction(3,2); n=newton(x,2)
items.append(item(5,'For $f(x)=x^2-2$, calculate one Newton-Raphson iterate from $x_0=1.5$.',n,'Since $f\prime(x)=2x$, $x_1=x_0-(x_0^2-2)/(2x_0)=17/12$.',['Differentiate $f$.','Use $x_{n+1}=x_n-f(x_n)/f\prime(x_n)$.','Substitute $x_0=1.5$ into both $f$ and $f\prime$.'],3))
n2=newton(n,2)
items.append(item(6,'For $f(x)=x^2-2$, calculate the next Newton-Raphson iterate after $x_1=17/12$.',n2,'Applying $x_{n+1}=(x_n^2+2)/(2x_n)$ gives $x_2=577/408$.',['Use the current iterate as the starting value.','Apply the Newton-Raphson recurrence again.','Substitute $17/12$ for $x_n$.'],4))
items.append({'id':'FP1-3-i07','kcs':[K],'kind':'short','difficulty':4,'command_word':'Explain','source':{'type':'generated'},'stem':'Explain why bisection of $[1,2]$ for $f(x)=x^2-2$ retains $[1,1.5]$ after the first step, and why linear interpolation may give a different estimate.','marks':2,'rubric':[{'point':'$f(1)<0<f(1.5)$, so the sign change and root remain in $[1,1.5]$.','keywords':[['sign change','opposite signs'],['1.5']]},{'point':'Linear interpolation uses the zero of the secant through endpoint function values, rather than the interval midpoint.','keywords':[['secant','straight line'],['midpoint','middle']]}],'explanation':'Bisection retains the half with opposite endpoint signs. Linear interpolation instead finds the zero of the chord, so its estimate need not be the midpoint.','hints':['Check the signs at the midpoint and endpoints.','Choose the half containing a sign change.','Compare a midpoint with a secant-axis intersection.']})
pack={'subtopic':'FP1-3','spec':'FP1','version':1,'note':N,'outline':'Solve $f(x)=0$ numerically by maintaining a sign-changing bracket for interval bisection, finding the zero of a secant for linear interpolation, or following a tangent using $x_{n+1}=x_n-f(x_n)/f\prime(x_n)$ for Newton-Raphson. Check function values and convergence.','misconceptions':[{'id':'m1','kc':K,'statement':'Bisection keeps the half whose midpoint is closest to zero without checking signs.','refutation':'A valid bracket retains opposite signs at its endpoints.','contrast':'Evaluate $f$ at the midpoint, then keep the sign-changing half.','source':'research'},{'id':'m2','kc':K,'statement':'Linear interpolation always uses the midpoint.','refutation':'It uses the zero of the straight line joining endpoint function values.','contrast':'Weight the interval using the signed function values.','source':'research'},{'id':'m3','kc':K,'statement':'Newton-Raphson subtracts $f\prime(x_n)/f(x_n)$.','refutation':'The tangent intersection gives $x_{n+1}=x_n-f(x_n)/f\prime(x_n)$.','contrast':'Function value over gradient is the horizontal correction.','source':'research'}],'worked':[{'id':'we1','kc':K,'problem':'For $f(x)=x^2-2$, start with $[1,2]$. Find one bisection midpoint, one linear interpolation estimate and one Newton-Raphson iterate from $x_0=1.5$.','steps':[{'do':'$f(1)=-1$ and $f(2)=2$; a root is bracketed.','why':'Opposite signs justify bisection for this continuous polynomial.'},{'do':'Midpoint $m=(1+2)/2=1.5$; $f(m)=0.25$, so retain $[1,1.5]$.','why':'The sign change is in the left half.','check':{'kind':'numeric','answer':a(Fraction(3,2))}},{'do':'Secant estimate $x=1-(-1)(2-1)/(2-(-1))=4/3$.','why':'Linear interpolation uses both signed endpoint values.','check':{'kind':'numeric','answer':a(r)}},{'do':'$f\prime(x)=2x$; $x_1=1.5-0.25/3=17/12$.','why':'Newton-Raphson follows the tangent to the axis.','check':{'kind':'numeric','answer':a(n)}}],'faded':{'id':'we1f','problem':'For $f(x)=x^2-3$, find one Newton-Raphson iterate from $x_0=2$.','answer':a(newton(Fraction(2),3)),'blank_from':1}}],'items':items,'flashcards':[],'diagrams':[]}
assert all(abs(float(z)-float(Fraction(z)))<1e-12 for z in [m,m2,r,r2,n,n2])
out=ROOT/'build/out/packs/FP1/FP1-3.json';out.parent.mkdir(parents=True,exist_ok=True);out.write_text(json.dumps(pack,ensure_ascii=False,indent=2))
