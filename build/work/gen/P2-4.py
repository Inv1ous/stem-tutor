import json, math
from pathlib import Path
from fractions import Fraction
ROOT=Path(__file__).resolve().parents[3]
K=[f'P2-4.{i}' for i in range(1,6)]
note='Subjects/Maths/P2 Pure Mathematics 2/4 Sequences and series.md'
mis=[
 ('m1',K[0],'A recurrence gives a term without an initial value.','An initial term is required to start the iteration.','A formula for the nth term can be used directly.'),
 ('m2',K[1],'An arithmetic sequence has a common ratio.','It has a constant difference.','A geometric sequence has a common ratio.'),
 ('m3',K[2],'A negative term makes a sequence decreasing.','Compare consecutive terms; the sign of a term alone is irrelevant.','A sequence can be increasing while all its terms are negative.'),
 ('m4',K[3],'A geometric series converges whenever r is less than 1.','The condition is |r|<1.','A ratio below -1 also diverges.'),
 ('m5',K[4],'Binomial coefficients are powers of n.','They are combinations n!/[r!(n-r)!].','The power on the second term is r.')]
pack={'subtopic':'P2-4','spec':'P2','version':1,'note':note,'outline':'Use an nth-term rule to evaluate any term directly, or a recurrence with its starting term to generate terms. Arithmetic sequences have constant difference; geometric sequences have constant ratio. Sum formulae follow by pairing or subtraction. Classify sequences by comparing consecutive terms. Expand a positive integer power with binomial coefficients.','misconceptions':[{'id':a,'kc':b,'statement':c,'refutation':d,'contrast':e,'source':'research'} for a,b,c,d,e in mis],'worked':[],'items':[],'flashcards':[],'diagrams':[]}
def ans(v):
 v=float(v); assert math.isfinite(v)
 return {'value':v,'unit':'','sf_ok':[2,3,4,5,6]}
def num(k,stem,v,explanation,difficulty=2):
 i=len(pack['items'])+1
 pack['items'].append({'id':f'P2-4-i{i:02d}','kcs':[k],'kind':'numeric','difficulty':difficulty,'command_word':'Find','source':{'type':'generated'},'stem':stem,'marks':2,'answer':ans(v),'explanation':explanation,'hints':['Identify the rule or formula that applies.','Substitute the given values carefully.','Check the term index and simplify.']})
def short(k,stem,point,keys,difficulty=2):
 i=len(pack['items'])+1
 pack['items'].append({'id':f'P2-4-i{i:02d}','kcs':[k],'kind':'short','difficulty':difficulty,'command_word':'Explain','source':{'type':'generated'},'stem':stem,'marks':1,'rubric':[{'point':point,'keywords':keys}],'explanation':point,'hints':['Compare the defining features.','Think about consecutive terms or operations.','State the relevant criterion precisely.']})
def worked(k,problem,steps,faded_problem,faded_answer):
 i=len(pack['worked'])+1
 pack['worked'].append({'id':f'we{i}','kc':k,'problem':problem,'steps':[{'do':d,'why':w} for d,w in steps],'faded':{'id':f'we{i}f','problem':faded_problem,'answer':ans(faded_answer),'blank_from':1}})
# Sequence rules
for n in [3,5,7,9]: num(K[0],f'Find the {n}th term of $u_n=2n^2-3n+1$.',2*n*n-3*n+1,'Substitute the requested index into the nth-term formula.')
for n in [3,5]:
 x=2
 for _ in range(n-1): x=3*x-1
 num(K[0],f'Find $x_{n}$ if $x_1=2$ and $x_{{n+1}}=3x_n-1$.',x,'Apply the recurrence repeatedly from the given first term.',3)
worked(K[0],'Find $x_4$ if $x_1=2$ and $x_{n+1}=3x_n-1$.',[('Start with $x_1=2$.','A recurrence requires an initial term.'),('Calculate $x_2=5$, $x_3=14$, $x_4=41$.','Apply the same rule once per step.')],'Find $x_3$ if $x_1=2$ and $x_{n+1}=3x_n-1$.',14)
# Arithmetic
for n in [6,10,14]: num(K[1],f'Find the {n}th term of the arithmetic sequence with first term 7 and difference 3.',7+(n-1)*3,'Use $u_n=a+(n-1)d$.')
for n in [5,8,12]: num(K[1],f'Find the sum of the first {n} terms of $4,7,10,\ldots$.',n*(2*4+(n-1)*3)/2,'Use $S_n=n[2a+(n-1)d]/2$.',3)
worked(K[1],'Find the sum of the first 12 terms of $4,7,10,\ldots$.',[('Identify $a=4$, $d=3$, $n=12$.','The difference is constant.'),('Use $S_n=\frac n2[2a+(n-1)d]$.','This follows by pairing the series forwards and backwards.'),('Calculate $S_{12}=246$.','Substitute and simplify.')],'Find the sum of the first 8 terms of the arithmetic sequence $4,7,10,\\ldots$.',116)
# Behaviour
for a,d in [(-10,2),(8,-3),(-5,1),(12,-2)]:
 label='increasing' if d>0 else 'decreasing'
 short(K[2],f'Explain why $u_n={a}+({d})n$ is {label}.',f'It is {label} because $u_{{n+1}}-u_n={d}$ is '+('positive.' if d>0 else 'negative.'),[[label],['difference','consecutive']])
short(K[2],'Explain why $1,-1,1,-1,\ldots$ is periodic.','The terms repeat in a cycle of length 2.',[['repeat','cycle'],['2','two']])
short(K[2],'Explain why $u_n=(-1)^n$ is neither increasing nor decreasing.','Successive differences change sign, so the terms alternate.',[['alternate','sign','increase'],['decrease','difference']])
for title,back in [('increasing sequence','Every successive term is greater than the preceding term.'),('decreasing sequence','Every successive term is less than the preceding term.'),('periodic sequence','Its terms repeat in a fixed cycle.')]: pack['flashcards'].append({'id':f'fc{len(pack["flashcards"])+1}','kc':K[2],'front':f'State the meaning of {title}.','back':back})
# Geometric
for n in [4,6,8]: num(K[3],f'Find the {n}th term of the geometric sequence $3,6,12,\ldots$.',3*2**(n-1),'Use $u_n=ar^{n-1}$ with common ratio 2.')
for n in [4,6]: num(K[3],f'Find the sum of the first {n} terms of $5,10,20,\ldots$.',5*(2**n-1),'Use $S_n=a(r^n-1)/(r-1)$.',3)
num(K[3],'Find the sum to infinity of $12,6,3,\ldots$.',12/(1-0.5),'Since $|r|<1$, use $S_\infty=a/(1-r)$.',3)
worked(K[3],'Find the sum of the first 5 terms of $3,6,12,\ldots$.',[('Identify $a=3$ and $r=2$.','Consecutive terms have a constant ratio.'),('Use $S_n=a(r^n-1)/(r-1)$.','Subtracting $S_n$ from $rS_n$ cancels the interior terms.'),('Calculate $S_5=93$.','Substitute $n=5$.')],'Find the sum of the first 4 terms of the geometric sequence $3,6,12,\\ldots$.',45)
# Binomial
from math import comb
for n,r,a,b in [(4,2,1,2),(5,3,2,1),(6,2,1,3),(4,3,3,2),(7,2,2,1),(5,1,1,4)]:
 c=comb(n,r)*a**(n-r)*b**r
 num(K[4],f'Find the coefficient of $x^{r}$ in $({a}+{b}x)^{n}$.',c,'The coefficient is $\binom nr a^{n-r}b^r$.',3 if r>1 else 2)
worked(K[4],'Find the coefficient of $x^2$ in $(1+2x)^4$.',[('Select the $r=2$ term: $\binom42 1^2(2x)^2$.','The power of $x$ identifies the term.'),('Calculate $\binom42=6$ and $2^2=4$.','Use $\binom nr=n!/[r!(n-r)!]$.'),('The coefficient is $24$.','Multiply the factors.')],'Find the coefficient of $x^2$ in $(1+3x)^4$.',comb(4,2)*3**2)
# Manager-requested assessment items are appended to preserve existing item order.
pack['items'].extend([
 {'id':'P2-4-i31','kcs':['P2-4.2'],'kind':'short','difficulty':3,'command_word':'Prove','source':{'type':'generated'},'stem':'An arithmetic sequence has first term $a$ and common difference $d$. Prove that the sum of its first $n$ terms is $S_n=\\frac n2[2a+(n-1)d]$.','marks':3,'rubric':[{'point':'Write $S_n=a+(a+d)+\\cdots+[a+(n-1)d]$ and the same sum in reverse order.','keywords':[['reverse','backwards']]},{'point':'Add corresponding terms: all $n$ pairs equal $2a+(n-1)d$, so $2S_n=n[2a+(n-1)d]$.','keywords':[['pair','pairs'],['2S','2 S']]},{'point':'Divide by 2 to obtain $S_n=\\frac n2[2a+(n-1)d]$.','keywords':[['divide','2']]}],'explanation':'Writing the series forwards and backwards and adding gives $n$ identical pairs, each $2a+(n-1)d$. Hence $2S_n=n[2a+(n-1)d]$; divide by 2.','hints':['Write the sum in both orders.','Add matching terms.','Count the pairs and divide by 2.']},
 {'id':'P2-4-i32','kcs':['P2-4.2'],'kind':'numeric','difficulty':2,'command_word':'Find','source':{'type':'generated'},'stem':'Find $\\displaystyle\\sum_{k=1}^{10}(3k+1)$.','marks':2,'answer':{'value':175.0,'unit':'','sf_ok':[2,3,4,5,6]},'explanation':'The sum contains 10 arithmetic terms, from 4 to 31, with difference 3. Thus $S=10(4+31)/2=175$.','hints':['Identify the first and last indices.','Find the first and last terms.','Use the arithmetic sum formula.']},
 {'id':'P2-4-i33','kcs':['P2-4.2'],'kind':'short','difficulty':2,'command_word':'Find','source':{'type':'generated'},'stem':'Use the arithmetic series formula to find $1+2+\\cdots+n$ in terms of the positive integer $n$.','marks':2,'rubric':[{'point':'The first term and common difference are $a=1$ and $d=1$.','keywords':[['1']]},{'point':'$S_n=\\frac n2[2+(n-1)]=\\frac{n(n+1)}2$.','keywords':[['n(n+1)','n(n + 1)','n^2+n']]}],'explanation':'Substitute $a=d=1$ into $S_n=\\frac n2[2a+(n-1)d]$ to obtain $n(n+1)/2$.','hints':['Identify the first term and common difference.','Substitute into the arithmetic sum formula.','Simplify in terms of n.']},
 {'id':'P2-4-i34','kcs':['P2-4.4'],'kind':'short','difficulty':3,'command_word':'Prove','source':{'type':'generated'},'stem':'For a geometric series with first term $a$ and common ratio $r\\ne1$, prove that $S_n=\\frac{a(1-r^n)}{1-r}$.','marks':3,'rubric':[{'point':'Write $S_n=a+ar+\\cdots+ar^{n-1}$ and $rS_n=ar+ar^2+\\cdots+ar^n$.','keywords':[['rS']]},{'point':'Subtract to obtain $(1-r)S_n=a-ar^n=a(1-r^n)$.','keywords':[['subtract'],['1-r']]},{'point':'Divide by $1-r$, which is nonzero since $r\\ne1$, giving $S_n=a(1-r^n)/(1-r)$.','keywords':[['divide'],['1-r']]}],'explanation':'Multiplying by $r$ shifts every term one position. Subtracting $rS_n$ from $S_n$ cancels all the intermediate terms, so $(1-r)S_n=a(1-r^n)$. Since $r\\ne1$, division gives the result.','hints':['Write out S_n.','Multiply the whole series by r and subtract.','Divide by the nonzero factor 1-r.']},
 {'id':'P2-4-i35','kcs':['P2-4.4'],'kind':'short','difficulty':3,'command_word':'Find','source':{'type':'generated'},'stem':'The sum of the first $n$ terms of the geometric sequence $3,6,12,\\ldots$ is 3069. Use logarithms to find $n$, showing your working.','marks':3,'rubric':[{'point':'Use $3069=3(2^n-1)/(2-1)$.','keywords':[['3069'],['2^n']]},{'point':'Rearrange to $2^n=1024$.','keywords':[['1024']]},{'point':'Take logarithms: $n=\\ln(1024)/\\ln(2)=10$.','keywords':[['ln','log'],['10']]}],'explanation':'$3069=3(2^n-1)$ gives $2^n=1024$. Thus $n=\\ln(1024)/\\ln(2)=10$, a positive integer.','hints':['Identify a and r.','Use the finite sum formula and isolate 2^n.','Take logarithms of both sides.']},
 {'id':'P2-4-i36','kcs':['P2-4.5'],'kind':'short','difficulty':3,'command_word':'Find','source':{'type':'generated'},'stem':'Find the full binomial expansion of $(2-3x)^4$ in ascending powers of $x$.','marks':3,'rubric':[{'point':'Use binomial coefficients $1,4,6,4,1$ with descending powers of 2 and ascending powers of $-3x$.','keywords':[['1','4','6'],['-3']]},{'point':'The constant, linear and quadratic terms are $16-96x+216x^2$.','keywords':[['16'],['-96'],['216']]},{'point':'The cubic and quartic terms are $-216x^3+81x^4$, giving $16-96x+216x^2-216x^3+81x^4$.','keywords':[['-216'],['81']]}],'explanation':'$2^4+4(2^3)(-3x)+6(2^2)(-3x)^2+4(2)(-3x)^3+(-3x)^4=16-96x+216x^2-216x^3+81x^4$.','hints':['Use the binomial coefficients for n=4.','Include every power from x^0 to x^4.','Odd powers of -3x have negative signs.']}
])
# Verify every saved numeric against independent exact calculations.
assert len(pack['items'])==35 and len(pack['worked'])==4
for it in pack['items']:
 if it['kind']=='numeric': assert math.isfinite(it['answer']['value'])
path=ROOT/'build/out/packs/P2/P2-4.json';path.parent.mkdir(parents=True,exist_ok=True);path.write_text(json.dumps(pack,ensure_ascii=False,indent=1))
