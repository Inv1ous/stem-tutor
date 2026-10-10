"""Generate FP1-7. SymPy verifies all displayed numerical results and template cases."""
import json
from pathlib import Path
import sympy as sp

ROOT = Path(__file__).resolve().parents[3]
SUB = 'FP1-7'
KC = 'FP1-7.1'
NOTE = 'Subjects/Maths/FP1 Further Pure Mathematics 1/7 Series.md'
r, n = sp.symbols('r n', integer=True, positive=True)
S1 = n*(n+1)/2
S2 = n*(n+1)*(2*n+1)/6
S3 = S1**2
assert sp.simplify(sp.summation(r,(r,1,n))-S1)==0
assert sp.simplify(sp.summation(r**2,(r,1,n))-S2)==0
assert sp.simplify(sp.summation(r**3,(r,1,n))-S3)==0

def total(term, lo, hi):
    return sp.summation(term, (r, lo, hi))
def num(v):
    assert sp.sympify(v).is_number
    return {'value': float(v), 'unit': '', 'exact': True}
def check(v):
    return {'kind': 'numeric', 'answer': num(v)}
items=[]
def base(kind, stem, explanation, hints, difficulty=2, word='Find', marks=2):
    assert len(hints)==3
    z={'id':f'{SUB}-i{len(items)+1:02}', 'kcs':[KC], 'kind':kind, 'difficulty':difficulty,
       'command_word':word, 'source':{'type':'generated'}, 'stem':stem, 'marks':marks,
       'explanation':explanation, 'hints':hints}
    items.append(z)
    return z

def templ(stem, term, formula, wrong, explanation, hints, difficulty=3):
    # Every sampled n is checked against direct symbolic summation, including all distractors.
    p={'n':{'min':4,'max':12,'step':1}}
    ds=[]
    for expr, misconception in wrong:
        ds.append({'expr':expr,'misconception':misconception})
    z=base('numeric',stem,explanation,hints,difficulty)
    z['answer']=num(total(term,1,4))
    z['template']={'params':p,'derived':{},'answer':formula,'distractors':ds,'constraints':[]}
    for k in range(4,13):
        env={n:k}
        a=total(term,1,k)
        assert sp.simplify(a-sp.sympify(formula, locals={"n":n}).subs(env))==0
        for d in ds:
            b=sp.sympify(d['expr'], locals={'n':n}).subs(env)
            assert a!=b and abs(float(a-b))>0.02*max(abs(float(a)),1e-12)
    return z

def fixed(stem, term, lo, hi, explanation, hints, difficulty=3, wrong=()):
    a=total(term,lo,hi)
    z=base('numeric',stem,explanation,hints,difficulty)
    z['answer']=num(a)
    z['distractors']=[{'value':float(v),'misconception':m} for v,m in wrong]
    assert all(abs(float(a-v))>0.02*max(abs(float(a)),1e-12) for v,m in wrong)
    return z

def mcq(stem, choices, key, explanation, hints, distractors=None, difficulty=2, word='State'):
    assert len(choices)==4 and len(set(choices))==4
    z=base('mcq',stem,explanation,hints,difficulty,word,1)
    z.update(options=dict(zip('ABCD',choices)),answer=key,distractors=distractors or {},shuffle=True)
    return z

mis=[
 {'id':'m1','kc':KC,'statement':'The sum of squares is the square of the sum of the integers.','refutation':'$\\sum r^2$ adds the square of each term; $(\\sum r)^2$ contains extra cross terms.','contrast':'For $r=1,2$, $1^2+2^2=5$, whereas $(1+2)^2=9$.','source':'research'},
 {'id':'m2','kc':KC,'statement':'The sum of cubes is the cube of the sum of the integers.','refutation':'$\\sum_{r=1}^n r^3=[n(n+1)/2]^2$, not $[n(n+1)/2]^3$.','contrast':'The cube-sum formula is the square of the triangular number.','source':'research'},
 {'id':'m3','kc':KC,'statement':'A product inside a sum can be replaced by a product of sums.','refutation':'In general $\\sum r(r+2)=\\sum r^2+2\\sum r$ after expanding each summand; it is not $(\\sum r)(\\sum(r+2))$.','contrast':'Expand the summand first and apply linearity.','source':'research'},
 {'id':'m4','kc':KC,'statement':'For a sum from $r=a$ to $b$, subtract the sum through $a$ from the sum through $b$.','refutation':'The term at $r=a$ must remain, so subtract the sum through $a-1$.','contrast':'$\\sum_{r=a}^b f(r)=\\sum_{r=1}^b f(r)-\\sum_{r=1}^{a-1} f(r)$.','source':'research'}]

# Formula questions span all three syllabus examples.
templ('Calculate $\\sum_{r=1}^{[[n]]}r^2$.',r**2,'n*(n+1)*(2*n+1)/6',
      [('(n*(n+1)/2)**2','m1')],
      'Use the sum of squares formula $n(n+1)(2n+1)/6$.',
      ['Identify the power in the summand.','Recall the finite sum of squares formula.','Substitute the upper limit for $n$; simplify the factors.'])
templ('Calculate $\\sum_{r=1}^{[[n]]}r^3$.',r**3,'(n*(n+1)/2)**2',
      [('(n*(n+1)/2)**3','m2')],
      'The sum of cubes equals the square of $1+2+\\cdots+n$.',
      ['Identify the cube-sum identity.','First find the triangular number.','Square the whole triangular number, not each factor separately.'])
templ('Find $\\sum_{r=1}^{[[n]]}r(r+2)$.',r*(r+2),'n*(n+1)*(2*n+1)/6+n*(n+1)',
      [('n*(n+1)*(2*n+1)/6','m3')],
      'Expand $r(r+2)=r^2+2r$, then add the square sum and twice the integer sum.',
      ['Expand one general summand.','Split the sum into a squares sum and a linear sum.','Use $\\sum r^2+2\\sum r$.'],4)

fixed('Calculate $\\sum_{r=3}^{8}r^2$.',r**2,3,8,
      'The sum is $S_2(8)-S_2(2)$, retaining the $r=3$ term.',
      ['Use the sum through the upper limit.','Subtract the terms before the lower limit.','Subtract $S_2(2)$ from $S_2(8)$.'],4,
      [(total(r**2,1,8)-total(r**2,1,3),'m4')])
fixed('Find $\\sum_{r=2}^{6}r(r+2)$.',r*(r+2),2,6,
      'Expand each term, then evaluate $[S_2(6)-S_2(1)]+2[S_1(6)-S_1(1)]$.',
      ['Expand $r(r+2)$.','Use squares and linear sums.','Remove only the term before the lower limit.'],4,
      [(total(r*(r+2),1,6)-total(r*(r+2),1,2),'m4')])

mcq('State the correct formula for $\\sum_{r=1}^{n}r^2$.',
     ['$\\frac{n(n+1)(2n+1)}6$','$\\left[\\frac{n(n+1)}2\\right]^2$',
      '$\\frac{n(n+1)}2$','$\\left[\\frac{n(n+1)}2\\right]^3$'],'A',
     'The square-sum formula has the factor $2n+1$; the square of the triangular number is the cube sum.',
     ['Distinguish a squares sum from a cubes sum.','Look for the factor associated with squares.','Check the formula at a small upper limit.'],{'B':'m1'},2)
mcq('State the formula for $\\sum_{r=1}^{n}r^3$.',
     ['$\\left[\\frac{n(n+1)}2\\right]^2$','$\\left[\\frac{n(n+1)}2\\right]^3$',
      '$\\frac{n(n+1)(2n+1)}6$','$\\frac{n(n+1)}2$'],'A',
     'The cube sum is the square of the sum of the first $n$ positive integers.',
     ['Recall how cubes relate to triangular numbers.','Find $1+2+\\cdots+n$ first.','Choose the expression that squares that result.'],{'B':'m2'},2)
mcq('Find the correct first step for summing $\\sum_{r=1}^{n}r(r+2)$.',
     ['$\\sum_{r=1}^{n}r^2+2\\sum_{r=1}^{n}r$',
      '$(\\sum_{r=1}^{n}r)(\\sum_{r=1}^{n}(r+2))$',
      '$\\sum_{r=1}^{n}r^2+2$',
      '$\\sum_{r=1}^{n}r^3+2\\sum_{r=1}^{n}r$'],'A',
     'Distribute within each summand: $r(r+2)=r^2+2r$, then split the sum.',
     ['Expand the term indexed by $r$.','Use linearity of summation.','Both $r^2$ and $2r$ are summed over the full range.'],{'B':'m3','C':'m3'},3)
mcq('State the correct difference for $\\sum_{r=5}^{n}r^2$ when $n\\ge5$, using $S_2(k)=\\sum_{r=1}^{k}r^2$.',
     ['$S_2(n)-S_2(4)$','$S_2(n)-S_2(5)$','$S_2(n)+S_2(4)$','$S_2(n)-S_2(n-5)$'],'A',
     'Remove the terms with indices $1$ through $4$, so the term with index $5$ remains.',
     ['Write which terms must be removed.','Keep the term at the lower limit.','Subtract the sum ending immediately before the lower limit.'],{'B':'m4'},3)

# A complete exam-style derivation with independently checked mark points.
poly=sp.factor(S2+2*S1)
assert sp.simplify(poly-n*(n+1)*(2*n+7)/6)==0
z=base('structured','Show that $\\sum_{r=1}^{n}r(r+2)=\\frac{n(n+1)(2n+7)}6$.',
       'Expand each summand, apply the two standard formulae, then factor $n(n+1)/6$.',
       ['Expand the general term.','Split the finite sum.','Substitute the known sums of $r^2$ and $r$.'],4,'Show that',4)
z['scheme']=[
 {'mark':'M1','point':'Expand $r(r+2)=r^2+2r$.'},
 {'mark':'M1','point':'Write the sum as $\\sum_{r=1}^{n}r^2+2\\sum_{r=1}^{n}r$.'},
 {'mark':'A1','point':'Substitute $n(n+1)(2n+1)/6+n(n+1)$.'},
 {'mark':'A1','point':'Factor to obtain $n(n+1)(2n+7)/6$.'}]

worked=[
 {'id':'we1','kc':KC,'problem':'Find $\\sum_{r=1}^{10}r(r+2)$.',
  'steps':[
   {'do':'Write $r(r+2)=r^2+2r$, hence $\\sum_{r=1}^{10}r(r+2)=\\sum_{r=1}^{10}r^2+2\\sum_{r=1}^{10}r$.','why':'Linearity applies after expanding each summand.'},
   {'do':f'For $n=10$, $\\sum r^2={total(r**2,1,10)}$ and $\\sum r={total(r,1,10)}$.','why':'Use the two standard finite-sum formulae.', 'check':check(total(r**2,1,10))},
   {'do':f'Add ${total(r**2,1,10)}+2({total(r,1,10)})={total(r*(r+2),1,10)}$.','why':'The factor $2$ multiplies the whole linear sum.', 'check':check(total(r*(r+2),1,10))}],
  'faded':{'id':'we1f','problem':'Find $\\sum_{r=1}^{7}r(r+2)$.','answer':num(total(r*(r+2),1,7)),'blank_from':1}},
 {'id':'we2','kc':KC,'problem':'Calculate $\\sum_{r=4}^{9}r^3$.',
  'steps':[
   {'do':'Write $\\sum_{r=4}^{9}r^3=S_3(9)-S_3(3)$, where $S_3(k)=[k(k+1)/2]^2$.','why':'Subtract exactly the terms before the lower limit.'},
   {'do':f'$S_3(9)={total(r**3,1,9)}$ and $S_3(3)={total(r**3,1,3)}$.','why':'Apply the cube-sum formula at both limits.', 'check':check(total(r**3,1,9))},
   {'do':f'$S_3(9)-S_3(3)={total(r**3,4,9)}$.','why':'This leaves the terms from $r=4$ through $r=9$.', 'check':check(total(r**3,4,9))}],
  'faded':{'id':'we2f','problem':'Calculate $\\sum_{r=3}^{6}r^3$.','answer':num(total(r**3,3,6)),'blank_from':1}}
]
flash=[
 {'id':'fc1','kc':KC,'front':'State the sum of the first $n$ squares.','back':'$\\sum_{r=1}^{n}r^2=\\frac{n(n+1)(2n+1)}6$.'},
 {'id':'fc2','kc':KC,'front':'State the sum of the first $n$ cubes.','back':'$\\sum_{r=1}^{n}r^3=\\left[\\frac{n(n+1)}2\\right]^2$.'},
 {'id':'fc3','kc':KC,'front':'How do you sum $r(r+2)$ over a finite range?','back':'Expand $r(r+2)=r^2+2r$, then use the square-sum and integer-sum formulae.'}]
pack={'subtopic':SUB,'spec':'FP1','version':1,'note':NOTE,
      'outline':'A finite series adds terms indexed by an integer. Use $\\sum_{r=1}^{n}r=n(n+1)/2$, $\\sum_{r=1}^{n}r^2=n(n+1)(2n+1)/6$, and $\\sum_{r=1}^{n}r^3=[n(n+1)/2]^2$. Expand polynomial summands such as $r(r+2)=r^2+2r$ before applying linearity. For a sum starting at $r=a>1$, subtract the sum through $a-1$ from the sum through the upper limit. Check a result by adding a few terms directly. The method of differences is not required.',
      'misconceptions':mis,'worked':worked,'items':items,'flashcards':flash,'diagrams':[]}
out=ROOT/'build/out/packs/FP1/FP1-7.json'
out.parent.mkdir(parents=True,exist_ok=True)
out.write_text(json.dumps(pack,ensure_ascii=False,indent=1))
print(f'Wrote {out}: {len(items)} items, {sum(bool(i.get("template")) for i in items)} templates, {len(worked)} worked')
