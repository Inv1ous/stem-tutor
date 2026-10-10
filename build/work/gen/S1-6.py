import json
from pathlib import Path
from statistics import NormalDist

ROOT = Path(__file__).resolve().parents[3]
KC = 'S1-6.1'
N = NormalDist()

def answer(v, unit=''):
    return {'value': round(v, 6), 'unit': unit, 'sf_ok': [2, 3]}

def item(i, kind, stem, explanation, difficulty=2, word='Find', **extra):
    return {'id': f'S1-6-i{i:02}', 'kcs': [KC], 'kind': kind, 'difficulty': difficulty,
            'command_word': word, 'source': {'type': 'generated'}, 'stem': stem,
            'marks': 1, 'explanation': explanation,
            'hints': ['Sketch the bell curve and mark the required region.',
                      'Standardise with $z=(x-\\mu)/\\sigma$ and use $\\Phi(z)$.',
                      'Identify whether the shaded region is left, right or between two bounds.'], **extra}

mu, sigma, x = 70, 10, 85
p = N.cdf((x-mu)/sigma)
lo, hi = 60, 80
between = N.cdf((hi-mu)/sigma)-N.cdf((lo-mu)/sigma)
q = N.inv_cdf(.9)
items = [
 item(1,'numeric','If $X\\sim N(70,10^2)$, find $P(X<85)$.',
      'Standardise: $z=(85-70)/10=1.5$, so $P(X<85)=\\Phi(1.5)$.',
      answer=answer(p), distractors=[{'value':round(1-p,6),'misconception':'m1'}]),
 item(2,'numeric','If $X\\sim N(70,10^2)$, find $P(60<X<80)$.',
      'The limits standardise to $-1$ and $1$. Subtract cumulative probabilities: $\\Phi(1)-\\Phi(-1)$.',
      answer=answer(between), distractors=[{'value':round(N.cdf(1),6),'misconception':'m2'}]),
 item(3,'numeric','If $X\\sim N(70,10^2)$, find the value $a$ for which $P(X<a)=0.9$.',
      'The table gives $z=\\Phi^{-1}(0.9)$; rearrange $z=(a-70)/10$ to obtain $a=70+10z$.', difficulty=3,
      answer=answer(mu+sigma*q), distractors=[{'value':round(mu-sigma*q,6),'misconception':'m1'}]),
 item(4,'mcq','State the mean and variance of $X\\sim N(12,3^2)$.',
      'In $N(\\mu,\\sigma^2)$ the first parameter is the mean and the second is the variance.',
      word='State', options={'A':'mean $12$, variance $9$','B':'mean $12$, variance $3$',
                            'C':'mean $3$, variance $12$','D':'mean $9$, variance $12$'},
      answer='A', distractors={'B':'m3','C':'m3','D':'m3'}, shuffle=True),
 item(5,'mcq','For a continuous Normal random variable with mean $20$, state $P(X=20)$.',
      'A single point has zero area under a continuous density curve.', word='State',
      options={'A':'$0$','B':'$0.5$','C':'$1$','D':'It depends on the variance'},
      answer='A', distractors={'B':'m4'}, shuffle=True),
 item(6,'short','Explain why $P(X<\\mu)=0.5$ when $X$ has a Normal distribution.',
      'The Normal curve is symmetric about its mean, so half its total area lies to the left.',
      word='Explain', rubric=[{'point':'Symmetry about the mean divides total probability equally.',
                               'keywords':[['symmetric','symmetry'],['mean'],['half','0.5','equal']]}]),
 item(7,'structured','The variable $X$ is Normally distributed. Given $P(X<54)=0.1587$ and $P(X<78)=0.8413$, find its mean and standard deviation.',
      'The table values correspond to $z=-1$ and $z=1$. Hence $54=\\mu-\\sigma$ and $78=\\mu+\\sigma$, giving $\\mu=66$ and $\\sigma=12$.',
      difficulty=4, scheme=[{'mark':'M1','point':'Use table values $z=-1$ and $z=1$.'},
                             {'mark':'M1','point':'Set up $54=\\mu-\\sigma$ and $78=\\mu+\\sigma$.'},
                             {'mark':'A1','point':'Solve $\\mu=66$ and $\\sigma=12$.'}], marks=3),
]

worked=[{'id':'we1','kc':KC,
         'problem':'For $X\\sim N(70,10^2)$, find $P(60<X<85)$.',
         'steps':[{'do':'Write $\\mu=70$ and $\\sigma=10$.','why':'The second Normal parameter is variance, so take its square root.'},
                  {'do':'Standardise: $z_1=(60-70)/10=-1$ and $z_2=(85-70)/10=1.5$.','why':'Tables give cumulative probabilities for standard Normal values.'},
                  {'do':'Subtract $\\Phi(1.5)-\\Phi(-1)=0.7745$ (4 d.p.).','why':'The area between bounds is the difference of cumulative areas.',
                   'check':{'kind':'numeric','answer':answer(N.cdf(1.5)-N.cdf(-1))}}],
         'faded':{'id':'we1f','problem':'For $Y\\sim N(50,8^2)$, find $P(42<Y<58)$. Standardise both bounds, then subtract the table values.',
                  'answer':answer(N.cdf(1)-N.cdf(-1)), 'blank_from':1}}]

pack={'subtopic':'S1-6','spec':'S1','version':1,
      'note':'Subjects/Maths/S1 Statistics 1/6 The Normal distribution.md',
      'outline':'A Normal distribution is a continuous, symmetric bell curve. Write $X\\sim N(\\mu,\\sigma^2)$, where $\\mu$ is the mean and $\\sigma^2$ the variance. Standardise with $Z=(X-\\mu)/\\sigma$ and use cumulative tables $\\Phi(z)=P(Z<z)$. Use complements for upper tails and subtraction for intervals. Reverse the process to find quantiles or solve equations for unknown parameters.',
      'misconceptions':[
          {'id':'m1','kc':KC,'statement':'Use the left-tail table value for a right-tail probability, or reverse the sign of a quantile.','refutation':'Cumulative tables give area to the left; the right tail is $1-\\Phi(z)$.','contrast':'Sketch and shade the required region first.','source':'research'},
          {'id':'m2','kc':KC,'statement':'Use one cumulative probability for an interval.','refutation':'The interval area is the upper cumulative area minus the lower cumulative area.','contrast':'Compute $\\Phi(z_2)-\\Phi(z_1)$.','source':'research'},
          {'id':'m3','kc':KC,'statement':'Treat the second parameter of $N(\\mu,\\sigma^2)$ as the standard deviation.','refutation':'The second parameter is variance; standard deviation is its positive square root.','contrast':'Label $\\mu$, $\\sigma^2$, and $\\sigma$ separately.','source':'research'},
          {'id':'m4','kc':KC,'statement':'Assign nonzero probability to one exact value of a continuous variable.','refutation':'A single point has zero width and therefore zero area.','contrast':'Use an interval when seeking a nonzero probability.','source':'research'}],
      'worked':worked,'items':items,
      'flashcards':[{'id':'fc1','kc':KC,'front':'State the parameters and shape of $X\\sim N(\\mu,\\sigma^2)$.',
                     'back':'Mean $\\mu$, variance $\\sigma^2$; a symmetric bell-shaped continuous distribution centred on $\\mu$.'},
                    {'id':'fc2','kc':KC,'front':'What does $\\Phi(z)$ represent?',
                     'back':'The cumulative probability $P(Z<z)$ for standard Normal $Z\\sim N(0,1)$.'}],
      'diagrams':[]}
path=ROOT/'build/out/packs/S1/S1-6.json'
path.parent.mkdir(parents=True,exist_ok=True)
path.write_text(json.dumps(pack,ensure_ascii=False,indent=1)+'\n')
