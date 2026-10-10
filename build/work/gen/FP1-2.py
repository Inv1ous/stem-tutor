import json
from fractions import Fraction as F
from pathlib import Path

root=Path(__file__).resolve().parents[3]
sub='FP1-2'; k1=sub+'.1'; k2=sub+'.2'; k3=sub+'.3'
pack={'subtopic':sub,'spec':'FP1','version':1,'note':'Subjects/Maths/FP1 Further Pure Mathematics 1/2 Roots of quadratic equations.md','outline':'For $ax^2+bx+c=0$, the roots have sum $S=-b/a$ and product $P=c/a$. Rewrite symmetric expressions in $S,P$, such as $\\alpha^2+\\beta^2=S^2-2P$ and $\\alpha^3+\\beta^3=S^3-3PS$. To form a quadratic with transformed roots, calculate their sum $T$ and product $U$, then write $x^2-Tx+U=0$ and clear denominators. Reciprocal transformations require $P\\ne0$.','misconceptions':[{'id':'m1','kc':k1,'statement':'The root sum is $b/a$.','refutation':'Expanding $a(x-\\alpha)(x-\\beta)$ gives coefficient $-a(\\alpha+\\beta)=b$.','contrast':'The sum is $-b/a$.','source':'research'},{'id':'m2','kc':k2,'statement':'$\\alpha^2+\\beta^2=S^2$.','refutation':'$S^2$ contains the cross term $2P$.','contrast':'Subtract $2P$.','source':'research'},{'id':'m3','kc':k3,'statement':'Transform the old coefficients separately to get the new quadratic.','refutation':'A transformation acts on each root, so calculate the transformed sum and product first.','contrast':'Use $x^2-Tx+U=0$.','source':'research'}],'worked':[],'items':[],'flashcards':[{'id':'fc1','kc':k1,'front':'State the sum and product of the roots of $ax^2+bx+c=0$.','back':'$\\alpha+\\beta=-b/a$ and $\\alpha\\beta=c/a$, for $a\\ne0$.'}],'diagrams':[]}
def ans(v):
 assert isinstance(v,(int,F)); return {'value':float(v),'unit':'','sf_ok':[2,3]}
def item(k,stem,v,explanation,difficulty=2,word='Find'):
 n=len(pack['items'])+1
 pack['items'].append({'id':f'{sub}-i{n:02}','kcs':[k],'kind':'numeric','difficulty':difficulty,'command_word':word,'source':{'type':'generated'},'stem':stem,'marks':2 if difficulty<4 else 4,'answer':ans(v),'explanation':explanation,'hints':['Identify the two roots or their sum and product.','Use the coefficient identities or a symmetric identity.','Write $S=-b/a$ and $P=c/a$ before substituting.']})
def roots(a,b,c): return -F(b,a),F(c,a)
for a,b,c in [(2,-6,4),(3,9,6),(5,-15,10)]:
 s,p=roots(a,b,c); item(k1,f'Find the sum of the roots of ${a}x^2{b:+}x{c:+}=0$.',s,'The sum is $-b/a$.')
 item(k1,f'Find the product of the roots of ${a}x^2{b:+}x{c:+}=0$.',p,'The product is $c/a$.',4)
for a,b,c in [(1,-5,6),(2,-8,6),(3,-9,6)]:
 s,p=roots(a,b,c); item(k2,f'Find $\\alpha^2+\\beta^2$ for roots of ${a}x^2{b:+}x{c:+}=0$.',s*s-2*p,'Use $S^2-2P$.')
 item(k2,f'Calculate $\\alpha^3+\\beta^3$ for roots of ${a}x^2{b:+}x{c:+}=0$.',s**3-3*p*s,'Use $S^3-3PS$.',4,'Calculate')
for a,b,c in [(1,-5,6),(2,-8,6),(3,-9,6)]:
 s,p=roots(a,b,c)
 item(k3,f'The roots of ${a}x^2{b:+}x{c:+}=0$ are $\\alpha,\\beta$. Find the sum of the new roots $\\alpha^2,\\beta^2$.',s*s-2*p,'The new sum is $S^2-2P$.')
 item(k3,f'The roots of ${a}x^2{b:+}x{c:+}=0$ are $\\alpha,\\beta$. Find the product of the new roots $1/\\alpha,1/\\beta$.',1/p,'The new product is $1/P$.',4)

pack['items'][13]={'id':'FP1-2-i14','kcs':['FP1-2.3'],'kind':'short','difficulty':4,'command_word':'Find','source':{'type':'generated'},'stem':'The roots of $x^2-5x+6=0$ are $\\alpha,\\beta$. Find a quadratic equation with integer coefficients whose roots are $1/\\alpha,1/\\beta$. Show your working.','marks':4,'rubric':[{'point':'Identify $S=\\alpha+\\beta=5$ and $P=\\alpha\\beta=6$.','keywords':[['5'],['6']]},{'point':'Find the new sum $T=S/P=5/6$.','keywords':[['5/6']]},{'point':'Find the new product $U=1/P=1/6$.','keywords':[['1/6']]},{'point':'Form $x^2-(5/6)x+1/6=0$ and clear denominators to obtain $6x^2-5x+1=0$; accept any nonzero integer multiple of this equation.','keywords':[['6x^2-5x+1=0']]}],'explanation':'The original roots have sum $S=5$ and product $P=6\\ne0$. The reciprocal roots therefore have sum $T=S/P=5/6$ and product $U=1/P=1/6$. Using $x^2-Tx+U=0$ gives $x^2-(5/6)x+1/6=0$, hence $6x^2-5x+1=0$. The coefficient of $x$ is the negative of the new sum; clear denominators across the whole equation.','hints':['Find the original sum $S=-b/a$ and product $P=c/a$.','For reciprocal roots use $T=S/P$ and $U=1/P$.','Form $x^2-Tx+U=0$ and multiply every term by 6.']}

def worked(k,id,problem,steps,faded,answer):
 pack['worked'].append({'id':id,'kc':k,'problem':problem,'steps':[{'do':d,'why':w} for d,w in steps],'faded':{'id':id+'f','problem':faded,'answer':ans(answer),'blank_from':1}})
worked(k2,'we1','For roots of $x^2-5x+6=0$, find $\\alpha^3+\\beta^3$.',[('$S=5$, $P=6$.','Apply coefficient identities.'),('$\\alpha^3+\\beta^3=S^3-3PS$.','This identity removes individual roots.'),('$5^3-3(6)(5)=35$.','Substitute and simplify.')],'For roots of $x^2-4x+3=0$, find $\\alpha^3+\\beta^3$.',F(4)**3-3*3*4)
worked(k3,'we2','Form the quadratic with roots $1/\\alpha,1/\\beta$ when $\\alpha,\\beta$ solve $2x^2-5x+2=0$.',[('$S=5/2$, $P=1$.','Read sum and product from the original coefficients.'),('$T=S/P=5/2$, $U=1/P=1$.','Use reciprocal-root identities; $P$ is nonzero.'),('$x^2-(5/2)x+1=0$, hence $2x^2-5x+2=0$.','Use the new sum and product, then clear fractions.')],'For roots of $x^2-5x+6=0$, find the sum of reciprocal roots.',F(5,6))
path=root/'build/out/packs/FP1/FP1-2.json'; path.parent.mkdir(parents=True,exist_ok=True);path.write_text(json.dumps(pack,ensure_ascii=False,indent=1))
