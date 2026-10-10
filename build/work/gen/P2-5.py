import json
import math
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
OUT = ROOT / 'build/out/packs/P2/P2-5.json'
K = ['P2-5.1', 'P2-5.2', 'P2-5.3']
items = []

def add(k, stem, options, correct, explanation, difficulty=2, word='Find'):
    n = len(items) + 1
    assert len(options) == 4 and len(set(options)) == 4
    items.append(dict(id=f'P2-5-i{n:02}', kcs=[k], kind='mcq', difficulty=difficulty,
        command_word=word, source={'type':'generated'}, stem=stem,
        options=dict(zip('ABCD', options)), answer='ABCD'[options.index(correct)],
        shuffle=True, marks=1, explanation=explanation,
        hints=['Recall the defining property.', 'Check the relevant index or logarithm rule.', 'Substitute the given base and argument.']))

add(K[0], 'State the $y$-intercept of $y=3^x$.', ['$1$','$0$','$3$','$-1$'], '$1$', 'At $x=0$, every positive base to the zero power is $1$.',1,'State')
add(K[0], 'State the horizontal asymptote of $y=2^x$.', ['$y=0$','$x=0$','$y=1$','$y=2$'], '$y=0$', 'As $x$ tends to negative infinity, $2^x$ tends to zero from above.',2,'State')
add(K[0], 'For $y=(1/2)^x$, state what happens as $x$ increases.', ['The curve decreases towards zero.','The curve increases without bound.','The curve crosses the $x$-axis.','The curve becomes negative.'], 'The curve decreases towards zero.', 'A base between zero and one gives a decreasing, always positive exponential curve.',2,'State')
add(K[0], 'Find the point on $y=4^x$ where $x=-1$.', ['$( -1,1/4)$','$( -1,4)$','$( -1,-4)$','$( -1,0)$'], '$( -1,1/4)$', '$4^{-1}=1/4$.',2)
add(K[0], 'Explain why $y=5^x$ never crosses the $x$-axis.', ['Because $5^x>0$ for every real $x$.','Because $5^x$ is always greater than $5$.','Because $x$ must be positive.','Because the graph has no $y$-intercept.'], 'Because $5^x>0$ for every real $x$.', 'Positive bases produce positive outputs for all real exponents.',3,'Explain')
add(K[0], 'Sketch $y=(1/3)^x$. Which labelled features must appear?', ['$(0,1)$ and asymptote $y=0$, decreasing','$(0,0)$ and asymptote $y=1$, decreasing','$(0,1)$ and asymptote $x=0$, increasing','$(1,0)$ and asymptote $y=0$, increasing'], '$(0,1)$ and asymptote $y=0$, decreasing', 'The graph passes through $(0,1)$ and approaches $y=0$ as $x$ grows.',4,'Sketch')

add(K[1], 'Find $\log_2(8\\times4)$.', ['$5$','$6$','$2$','$32$'], '$5$', '$\log_2 8+\log_2 4=3+2=5$.')
add(K[1], 'Find $\log_3(81/9)$.', ['$2$','$6$','$1$','$9$'], '$2$', '$\log_3 81-\log_3 9=4-2=2$.')
add(K[1], 'Find $\log_5(25^3)$.', ['$6$','$5$','$3$','$125$'], '$6$', '$3\log_5 25=3(2)=6$.')
add(K[1], 'Find $\log_7(1/7)$.', ['$-1$','$1$','$0$','$7$'], '$-1$', '$1/7=7^{-1}$, so its base-seven logarithm is $-1$.')
add(K[1], 'State $\log_a a$ for $a>0$, $a\\ne1$.', ['$1$','$0$','$a$','$-1$'], '$1$', '$a^1=a$, so $\log_a a=1$.',1,'State')
add(K[1], 'Simplify $\log_2 x+2\log_2 y-\log_2 z$ for $x,y,z>0$.', ['$\log_2(xy^2/z)$','$\log_2(x+2y-z)$','$\log_2(xy/z^2)$','$\log_2(xy^2z)$'], '$\log_2(xy^2/z)$', 'The power law makes $2\log_2 y=\log_2 y^2$; then apply product and quotient laws.',4)

for a,b in [(2,16),(3,81),(5,125),(4,8),(9,27),(2,10)]:
    value=math.log(b)/math.log(a)
    opts=[f'${value:.4g}$', f'${value+1:.4g}$', f'${value-1:.4g}$', f'${1/value:.4g}$']
    # Distinct and computed from the defining change-of-base expression.
    assert len(set(opts))==4
    add(K[2], f'Find $x$ if ${a}^x={b}$; give a decimal where needed.', opts, opts[0],
        f'Take logarithms: $x=\ln({b})/\ln({a})={value:.4g}$.',4 if b==10 else 2)

def check(v):
    return {'kind':'numeric','answer':{'value':v,'unit':'','sf_ok':[2,3]}}

worked=[
 {'id':'we1','kc':K[1],'problem':'Simplify $\log_3 81+\log_3 9-\log_3 3$.',
  'steps':[{'do':'Apply the product and quotient laws: $\log_3(81\\times9/3)$.','why':'The logs have the same base and positive arguments.'},
           {'do':'Evaluate $\log_3 243=5$.','why':'$3^5=243$.','check':check(math.log(243,3))}],
  'faded':{'id':'we1f','problem':'Find $\log_2 32+\log_2 4-\log_2 8$.','answer':{'value':math.log(32*4/8,2),'unit':'','sf_ok':[2,3]},'blank_from':1}},
 {'id':'we2','kc':K[2],'problem':'Solve $3^x=20$, giving $x$ to three significant figures.',
  'steps':[{'do':'Take natural logarithms: $x\ln3=\ln20$.','why':'The power law brings the unknown exponent down.'},
           {'do':f'Divide: $x=\ln20/\ln3={math.log(20)/math.log(3):.3g}$.','why':'$\ln3$ is nonzero.','check':check(round(math.log(20)/math.log(3),2))}],
  'faded':{'id':'we2f','problem':'Solve $5^x=18$, giving $x$ to three significant figures.','answer':{'value':round(math.log(18)/math.log(5),3),'unit':'','sf_ok':[3]},'blank_from':1}}
]
pack={'subtopic':'P2-5','spec':'P2','version':1,'note':'Subjects/Maths/P2 Pure Mathematics 2/5 Exponentials and logarithms.md',
 'outline':'For $a>0$, $a\\ne1$, the graph of $y=a^x$ passes through $(0,1)$ and approaches $y=0$. Logarithms invert exponentials. Product, quotient, power, reciprocal and base laws simplify logarithms with positive arguments. Solve $a^x=b$ by $x=\ln b/\ln a$ for $b>0$.',
 'misconceptions':[
  {'id':'m1','kc':K[0],'statement':'An exponential curve crosses the $x$-axis.','refutation':'$a^x$ is strictly positive for positive $a$.','contrast':'The $x$-axis is a horizontal asymptote.','source':'research'},
  {'id':'m2','kc':K[1],'statement':'$\log_a(x+y)=\log_a x+\log_a y$.','refutation':'The addition law applies to a product $xy$.','contrast':'$\log_a(xy)=\log_a x+\log_a y$.','source':'research'},
  {'id':'m3','kc':K[2],'statement':'$a^x=b$ gives $x=\ln a/\ln b$.','refutation':'Taking logarithms gives $x\ln a=\ln b$.','contrast':'Divide by $\ln a$ to get $x=\ln b/\ln a$.','source':'research'}],
 'worked':worked,'items':items,
 'flashcards':[{'id':'fc1','kc':K[0],'front':'State the key features of $y=a^x$.','back':'For $a>0$, $a\\ne1$: domain $\mathbb{R}$, range $(0,\infty)$, $y$-intercept $(0,1)$, horizontal asymptote $y=0$.'},
 {'id':'fc2','kc':K[1],'front':'State the three main laws of logarithms.','back':'For positive arguments: $\log_a(xy)=\log_a x+\log_a y$, $\log_a(x/y)=\log_a x-\log_a y$, and $\log_a(x^k)=k\log_a x$.'}], 'diagrams':[]}
OUT.parent.mkdir(parents=True,exist_ok=True)
OUT.write_text(json.dumps(pack,ensure_ascii=False,indent=1))
