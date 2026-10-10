import json
from fractions import Fraction
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
SUB = 'S1-5'
K = [f'{SUB}.{i}' for i in range(1, 5)]
items = []

def add(k, stem, answer, explanation, difficulty=2):
    n = len(items) + 1
    base = dict(id=f'{SUB}-i{n:02}', kcs=[K[k-1]], difficulty=difficulty,
                command_word='Calculate' if isinstance(answer, (int, float, Fraction)) else 'Explain',
                source={'type':'generated'}, stem=stem, marks=1, explanation=explanation,
                hints=['Identify the relevant definition or formula.', 'List the possible values and their probabilities.',
                       'Substitute the given information and simplify.'])
    if isinstance(answer, (int, float, Fraction)):
        base.update(kind='numeric', answer={'value':float(answer),'unit':'','sf_ok':[2,3]})
    else:
        base.update(kind='short', rubric=[{'point':answer,'keywords':[[w] for w in answer.split('|')]}])
    items.append(base)

for stem, ans in [
 ('Explain what a random variable assigns to outcomes.','number|outcome'),
 ('Explain what makes a random variable discrete.','countable|values'),
 ('Explain why the number of heads in four tosses is discrete.','finite|values'),
 ('Explain why exact time is not a discrete random variable.','continuous|range'),
 ('Explain how a red or blue draw can become a random variable.','assign|numbers'),
 ('Explain why a complete probability distribution sums to one.','all|outcomes')]:
    add(1,stem,ans,ans.replace('|',' and '),4 if 'red or blue' in stem else 2)

p=[Fraction(1,5),Fraction(3,10),Fraction(1,2)]
for stem, value, why in [
 ('For $X=0,1,2$ with probabilities $0.2,0.3,0.5$, calculate $p(1)$.',p[1],'$p(1)=P(X=1)=0.3$.'),
 ('For the same distribution, calculate $F(1)$.',sum(p[:2]),'$F(1)=p(0)+p(1)=0.5$.'),
 ('For the same distribution, calculate $P(X>0)$.',sum(p[1:]),'$P(X>0)=p(1)+p(2)=0.8$.'),
 ('For the same distribution, calculate $F(0)$.',p[0],'Only $X=0$ is included.'),
 ('For the same distribution, calculate $P(X\\leq2)$.',sum(p),'All possible values are included.'),
 ('For the same distribution, calculate $P(0<X\\leq2)$.',sum(p[1:]),'Add $p(1)+p(2)$.')]: add(2,stem,value,why,4 if '0<X' in stem else 2)

q=[Fraction(1,4),Fraction(1,2),Fraction(1,4)]; xs=[0,1,2]
mu=sum(x*v for x,v in zip(xs,q)); e2=sum(x*x*v for x,v in zip(xs,q)); var=e2-mu*mu
for stem,value,why in [
 ('For $X=0,1,2$ with probabilities $0.25,0.5,0.25$, calculate $E(X)$.',mu,'$E(X)=\\sum xp(x)=1$.'),
 ('For the same distribution, calculate $E(X^2)$.',e2,'$E(X^2)=\\sum x^2p(x)=1.5$.'),
 ('For the same distribution, calculate $\\operatorname{Var}(X)$.',var,'$E(X^2)-[E(X)]^2=0.5$.'),
 ('For the same distribution, calculate $E(3X+2)$.',3*mu+2,'$3E(X)+2=5$.'),
 ('For the same distribution, calculate $\\operatorname{Var}(3X+2)$.',9*var,'$3^2\\operatorname{Var}(X)=4.5$.'),
 ('For the same distribution, calculate $E(2X-1)$.',2*mu-1,'$2E(X)-1=1$.')]: add(3,stem,value,why,4 if '3X' in stem else 3)

for stem,value,why in [
 ('For a fair die scored 1 to 6, calculate $P(X=4)$.',Fraction(1,6),'Each of six outcomes has probability $1/6$.'),
 ('For a fair die scored 1 to 6, calculate $E(X)$.',Fraction(7,2),'The mean is $(1+6)/2=3.5$.'),
 ('For a fair die scored 1 to 6, calculate $\\operatorname{Var}(X)$.',Fraction(35,12),'Use $(6^2-1)/12=35/12$.'),
 ('For a uniform variable on 2, 3, 4, 5, 6, calculate its mean.',4,'The mean is $(2+6)/2=4$.'),
 ('For a uniform variable on 2, 3, 4, 5, 6, calculate its variance.',2,'Use $(5^2-1)/12=2$.'),
 ('For a uniform variable on 1, 2, 3, 4, calculate $P(X\\leq2)$.',Fraction(1,2),'Two of four equally likely outcomes qualify.')]: add(4,stem,value,why,4 if 'variance' in stem else 2)

def ans(v): return {'value':float(v),'unit':'','sf_ok':[2,3]}
def worked(k,id,problem,steps,faded,answer):
    return {'id':id,'kc':K[k-1],'problem':problem,
            'steps':[{'do':d,'why':w,'check':{'kind':'numeric','answer':ans(v)} if v is not None else None} for d,w,v in steps],
            'faded':{'id':id+'f','problem':faded,'answer':ans(answer),'blank_from':1}}
W=[
 worked(2,'we1','Find $F(1)$ when $p(0)=0.2$, $p(1)=0.3$, $p(2)=0.5$.',
        [('Write $F(1)=P(X\\leq1)$.','The bound is inclusive.',None),('Add $0.2+0.3=0.5$.','Both eligible probabilities contribute.',Fraction(1,2))],
        'Find $F(1)$ when $p(0)=0.1$, $p(1)=0.2$, $p(2)=0.7$.',Fraction(3,10)),
 worked(3,'we2','Find the variance of $X=0,1,2$ with probabilities $0.25,0.5,0.25$.',
        [('Find $E(X)=1$.','Weight each value by its probability.',mu),('Find $E(X^2)=1.5$.','Square each value before weighting.',e2),
         ('Calculate $1.5-1^2=0.5$.','Subtract the squared mean.',var)],
        'Find the variance for $X=0,1,2$ with probabilities $0.5,0.25,0.25$.',Fraction(11,16)),
 worked(4,'we3','Find the mean and variance of a fair die score.',
        [('Count $n=6$ equally likely scores.','Uniformity permits the standard formula.',None),('Calculate $(1+6)/2=3.5$.','The mean is the midpoint.',Fraction(7,2)),
         ('Calculate $(6^2-1)/12=35/12$.','There are six consecutive integers.',Fraction(35,12))],
        'Find the variance of a uniform variable on 1, 2, 3, 4.',Fraction(5,4))]
M=[{'id':f'm{i}','kc':K[k-1],'statement':s,'refutation':r,'contrast':c,'source':'research'} for i,(k,s,r,c) in enumerate([
 (2,'Cumulative probability concerns one value.','$F(x)$ sums all probabilities at or below $x$.','$p(x)=P(X=x)$; $F(x)=P(X\\leq x)$.'),
 (3,'Variance is $E(X^2)-E(X)$.','Square the mean in $E(X^2)-[E(X)]^2$.','Calculate both moments first.'),
 (3,'Adding a constant increases variance.','A shift does not change spread.','$\\operatorname{Var}(aX+b)=a^2\\operatorname{Var}(X)$.'),
 (4,'Uniform means equally spaced values.','Uniform means equal probabilities.','Equal spacing alone is insufficient.')],1)]
F=[{'id':f'fc{i}','kc':K[k-1],'front':front,'back':back} for i,(k,front,back) in enumerate([
 (1,'What is a discrete random variable?','A random variable with a finite or countably infinite set of possible values.'),
 (2,'Define $p(x)$ and $F(x_0)$.','$p(x)=P(X=x)$; $F(x_0)=P(X\\leq x_0)=\\sum_{x\\leq x_0}p(x)$.'),
 (3,'State the mean and variance formulae.','$E(X)=\\sum xp(x)$ and $\\operatorname{Var}(X)=E(X^2)-[E(X)]^2$.'),
 (3,'State the linear transformation rules.','$E(aX+b)=aE(X)+b$; $\\operatorname{Var}(aX+b)=a^2\\operatorname{Var}(X)$.'),
 (4,'State the mean and variance on $1,\\ldots,n$.','$E(X)=(n+1)/2$ and $\\operatorname{Var}(X)=(n^2-1)/12$.')],1)]
pack={'subtopic':SUB,'spec':'S1','version':1,'note':'Subjects/Maths/S1 Statistics 1/5 Discrete random variables.md',
      'outline':'A discrete random variable has countable numerical values. Its probability function is $p(x)=P(X=x)$; its cumulative distribution function sums up to $x$. The mean is $E(X)=\\sum xp(x)$ and variance is $E(X^2)-[E(X)]^2$. Linear transformations change mean and variance differently. A discrete uniform variable has equally likely values.',
      'misconceptions':M,'worked':W,'items':items,'flashcards':F,'diagrams':[]}
path=ROOT/'build/out/packs/S1/S1-5.json';path.parent.mkdir(parents=True,exist_ok=True);path.write_text(json.dumps(pack,ensure_ascii=False,indent=1))
