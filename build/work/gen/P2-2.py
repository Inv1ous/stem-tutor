import json
from pathlib import Path
import sympy as s

x=s.symbols('x')
root=Path(__file__).resolve().parents[3]
sub='P2-2'; kc='P2-2.1'

def value(poly, at):
    return float(s.expand(poly).subs(x, s.Rational(at)))

def item(n,kind,word,stem,answer,explanation,difficulty=2,**extra):
    d={'id':f'{sub}-i{n:02d}','kcs':[kc],'kind':kind,'difficulty':difficulty,'command_word':word,'source':{'type':'generated'},'stem':stem,'marks':1,'explanation':explanation,'hints':['Find the zero of the linear divisor.','Use substitution or polynomial division as appropriate.','Check the signs carefully before completing the calculation.']}
    if kind=='numeric': d['answer']={'value':answer,'unit':'','exact':True}
    elif kind=='expression': d['answer']={'expr':answer}
    d.update(extra)
    return d

p1=x**3+3*x**2-4
q1,r1=s.div(p1,x-1)
p2=6*x**3+11*x**2-x-6
q2,r2=s.div(p2,2*x+3)
assert r1==0 and r2==0
assert s.factor(p1)==(x-1)*(x+2)**2
assert s.factor(p2)==(x+1)*(2*x+3)*(3*x-2)
assert value(p2,s.Rational(-3,2))==0

mis=[
 {'id':'m1','kc':kc,'statement':'The remainder on division by $ax+b$ is $f(b/a)$.','refutation':'The divisor is zero at $x=-b/a$, so the remainder is $f(-b/a)$.','contrast':'For $2x+3$, substitute $-3/2$, not $3/2$.','source':'research'},
 {'id':'m2','kc':kc,'statement':'If $f(b/a)=0$, then $x-b/a$ is the only factor to report.','refutation':'A nonzero scalar multiple is also a factor: $(ax-b)=a(x-b/a)$.','contrast':'A root $2/3$ gives the integer-coefficient factor $3x-2$.','source':'research'},
 {'id':'m3','kc':kc,'statement':'A zero remainder means the quotient is zero.','refutation':'The quotient is the polynomial multiplying the divisor; the remainder is the separate constant left over.','contrast':'$x^3+3x^2-4=(x-1)(x^2+4x+4)+0$.','source':'research'}]
items=[
 item(1,'numeric','Find','Find the remainder when $f(x)=x^3+3x^2-4$ is divided by $x-2$.',value(p1,2),'The Remainder Theorem gives $f(2)=8+12-4=16$.',distractors=[{'value':value(p1,-2),'misconception':'m1'}]),
 item(2,'numeric','Find','Find the remainder when $f(x)=2x^3-x+5$ is divided by $2x+3$.',value(2*x**3-x+5,s.Rational(-3,2)),'The divisor vanishes at $x=-3/2$. Substitution gives $2(-3/2)^3-(-3/2)+5=-1/4$.',difficulty=3,distractors=[{'value':value(2*x**3-x+5,s.Rational(3,2)),'misconception':'m1'}]),
 item(3,'expression','Find','Find the quotient when $x^3+3x^2-4$ is divided by $x-1$.',str(q1).replace('**','**'),'Division gives $x^3+3x^2-4=(x-1)(x^2+4x+4)$, with remainder zero.',difficulty=3),
 item(4,'expression','Find','Find the quotient when $6x^3+11x^2-x-6$ is divided by $2x+3$.',str(q2),'The quotient is $3x^2+x-2$, because $(2x+3)(3x^2+x-2)=6x^3+11x^2-x-6$.',difficulty=4),
 item(5,'expression','Find','Find the fully factorised form of $x^3+3x^2-4$.',str(s.factor(p1)),'Since $f(1)=0$, divide by $x-1$ to get $x^2+4x+4=(x+2)^2$.',difficulty=4),
 item(6,'expression','Find','Find the fully factorised form of $6x^3+11x^2-x-6$.',str(s.factor(p2)),'Since $f(-1)=0$, divide by $x+1$ to obtain $6x^2+5x-6=(2x+3)(3x-2)$.',difficulty=5),
 item(7,'numeric','Calculate','Calculate $f(-3/2)$ for $f(x)=6x^3+11x^2-x-6$.',value(p2,s.Rational(-3,2)),'Substitution gives zero, so $2x+3$ is a factor.',difficulty=2),
]
worked=[{'id':'we1','kc':kc,'problem':'Show that $2x+3$ is a factor of $6x^3+11x^2-x-6$, then factorise the cubic completely.','steps':[
 {'do':'Set $2x+3=0$, giving $x=-3/2$.','why':'The Factor Theorem uses the zero of the proposed divisor.'},
 {'do':'Evaluate $f(-3/2)=0$.','why':'Zero remainder proves $2x+3$ is a factor.','check':{'kind':'numeric','answer':{'value':value(p2,s.Rational(-3,2)),'unit':'','exact':True}}},
 {'do':'Divide to obtain quotient $3x^2+x-2$.','why':'The identity $f(x)=(2x+3)q(x)+0$ determines the quotient.'},
 {'do':'Factor the quotient: $3x^2+x-2=(x+1)(3x-2)$, so $f(x)=(2x+3)(x+1)(3x-2)$.','why':'Factorising the quadratic completes the cubic factorisation.'}],
 'faded':{'id':'we1f','problem':'Find the remainder when $2x^3-x+5$ is divided by $2x+3$.','answer':{'value':value(2*x**3-x+5,s.Rational(-3,2)),'unit':'','exact':True},'blank_from':1}}]
pack={'subtopic':sub,'spec':'P2','version':1,'note':'Subjects/Maths/P2 Pure Mathematics 2/2 Algebra and functions.md','outline':'For polynomial $f(x)$, division by $ax+b$ gives $f(x)=(ax+b)q(x)+r$, where $q$ is the quotient and $r$ the constant remainder. Substituting $x=-b/a$ gives $r=f(-b/a)$. Therefore $ax+b$ is a factor exactly when $f(-b/a)=0$. For $ax-b$, use $x=b/a$. After finding a linear factor of a cubic, divide and factorise the resulting quadratic. Check by expanding the final product.','misconceptions':mis,'worked':worked,'items':items,'flashcards':[{'id':'fc1','kc':kc,'front':'State the Remainder Theorem for division by $ax+b$.','back':'The remainder is $f(-b/a)$, where $a\\ne0$.'},{'id':'fc2','kc':kc,'front':'State the Factor Theorem for $ax-b$.','back':'$ax-b$ is a factor of $f(x)$ if and only if $f(b/a)=0$, where $a\\ne0$.'}],'diagrams':[]}
out=root/'build/out/packs/P2/P2-2.json';out.write_text(json.dumps(pack,ensure_ascii=False,indent=1)+'\n')
print(out)
