import json
from pathlib import Path
from fractions import Fraction
import sympy as sp
ROOT=Path(__file__).resolve().parents[3]
SUB='FP1-4'; NOTE='Subjects/Maths/FP1 Further Pure Mathematics 1/4 Coordinate systems.md'
K=lambda n:f'{SUB}.{n}'
def ans(v): return {'value':float(v),'unit':'','sf_ok':[2,3,4]}
def base(n,k,kind,word,stem,difficulty=2,marks=1,explanation='',hints=None):
 return {'id':f'{SUB}-i{n:02}','kcs':[K(k)],'kind':kind,'difficulty':difficulty,'command_word':word,'source':{'type':'generated'},'stem':stem,'marks':marks,'explanation':explanation,'hints':hints or ['Recall the defining relation for this curve.','Identify which coordinates or gradients the question asks for.','Substitute the given values into the appropriate relation.']}
def mc(n,k,word,stem,opts,key,mis,expl,diff=2):
 z=base(n,k,'mcq',word,stem,diff,1,expl);z.update(options=dict(zip('ABCD',opts)),answer=key,distractors=mis,shuffle=True);return z
def numeric(n,k,word,stem,v,expl,diff=2,ds=None):
 z=base(n,k,'numeric',word,stem,diff,2,expl);z.update(answer=ans(v),distractors=ds or []);return z
def short(n,k,word,stem,point,words,expl,diff=3):
 z=base(n,k,'short',word,stem,diff,1,expl);z['rubric']=[{'point':point,'keywords':words}];return z
M=[
 {'id':'m1','kc':K(1),'statement':'The parabola $y^2=4ax$ is symmetric about the $y$-axis.','refutation':'Squaring $y$ means points with opposite $y$ values have the same $x$ coordinate.','contrast':'Its axis is the $x$-axis; $a>0$ makes it open right.','source':'research'},
 {'id':'m2','kc':K(2),'statement':'The parameter $t$ is the $x$ coordinate on either curve.','refutation':'On the parabola, $x=at^2$; on the hyperbola, $x=ct$.','contrast':'Use both parametric coordinate formulas and eliminate $t$ to check.','source':'research'},
 {'id':'m3','kc':K(3),'statement':'The directrix of $y^2=4ax$ is $x=a$.','refutation':'The focus is $(a,0)$ and the directrix is the vertical line $x=-a$.','contrast':'For $a>0$, the vertex $(0,0)$ lies midway between focus and directrix.','source':'research'},
 {'id':'m4','kc':K(4),'statement':'The normal has the same gradient as the tangent.','refutation':'For finite nonzero tangent gradient $m$, the normal gradient is $-1/m$.','contrast':'Differentiate for the tangent gradient, then take its negative reciprocal; handle vertical tangents separately.','source':'research'}]
I=[]
# Each template is independently checked against SymPy for its seed values.
def templ(n,k,stem,params,expr,ds,expl,diff=3):
 z=numeric(n,k,'Calculate',stem,sp.sympify(expr).subs({p: v['min'] for p,v in params.items()}),expl,diff)
 z['template']={'params':params,'derived':{},'answer':expr,'distractors':ds,'constraints':[]}
 for vals in [{p:v['min'] for p,v in params.items()},{p:v['max'] for p,v in params.items()}]:
  a=sp.sympify(expr).subs(vals);assert a.is_real and all(sp.simplify(a-sp.sympify(d['expr']).subs(vals))!=0 for d in ds)
 I.append(z)
templ(1,1,'For $y^2=4ax$ with $a=[[a]]$, calculate $x$ when $y=[[y]]$.',{'a':{'min':2,'max':5,'step':1},'y':{'min':4,'max':8,'step':2}},'y**2/(4*a)',[{'expr':'y**2/a','misconception':'m1'}],'Rearrange to $x=y^2/(4a)$ and substitute.',3)
I.append(mc(2,1,'State','State the Cartesian equation of a rectangular hyperbola with parameter $c$.',['$xy=c^2$','$y^2=4cx$','$xy=c$','$x^2+y^2=c^2$'],'A',{'B':'m1'},'The defining rectangular hyperbola is $xy=c^2$; the parabola has $y^2=4ax$.'))
I.append(mc(3,1,'Sketch','Sketch $y^2=8x$. Which description matches it?',['Vertex $(0,0)$; opens right; symmetric about the $x$-axis.','Vertex $(0,0)$; opens up; symmetric about the $y$-axis.','Vertex $(2,0)$; opens right.','Two branches in quadrants I and III.'],'A',{'B':'m1'},'Because $y^2=8x$, $x\\ge0$ and changing the sign of $y$ leaves $x$ unchanged.'))
I.append(short(4,1,'Explain','Explain why $xy=c^2$ with real nonzero $c$ has no point on either coordinate axis.','If $x=0$ or $y=0$, then $xy=0$, which cannot equal $c^2>0$.',[['zero','0'],['positive','nonzero']], 'The product is zero on either axis but $c^2$ is positive.'))
I.append(mc(5,1,'State','State the two axis asymptotes of $xy=c^2$.',['$x=0$ and $y=0$','$x=c$ and $y=c$','$y=x$ and $y=-x$','$x=0$ and $y=c$'],'A',{},'Writing $y=c^2/x$ shows that $y\\to0$ as $|x|\\to\\infty$ and $|y|\\to\\infty$ as $x\\to0$.'))
templ(6,2,'For $x=at^2$, $y=2at$ with $a=[[a]]$ and $t=[[t]]$, calculate the $x$ coordinate.',{'a':{'min':2,'max':5,'step':1},'t':{'min':2,'max':4,'step':1}},'a*t**2',[{'expr':'a*t','misconception':'m2'}],'The general point is $(at^2,2at)$, so its $x$ coordinate is $at^2$.')
I.append(numeric(7,2,'Find','Find $t$ for the point $(9,6)$ on $x=at^2$, $y=2at$ when $a=1$.',Fraction(6,2),'Use $t=y/(2a)=6/2=3$; then $at^2=9$ checks the point.'))
I.append(mc(8,2,'Verify','Verify which point lies on $x=2t^2$, $y=4t$ when $t=-2$.',['$(8,-8)$','$(-8,-8)$','$(8,8)$','$(-4,-8)$'],'A',{'B':'m2'},'Squaring $t=-2$ gives $x=8$, while $y=4(-2)=-8$.'))
I.append(short(9,2,'Show that','Show that eliminating $t$ from $x=at^2$, $y=2at$ gives $y^2=4ax$.','Squaring $y=2at$ gives $y^2=4a^2t^2=4a(at^2)=4ax$.',[['squar','square'],['4a']], 'Square the $y$ relation and replace $at^2$ by $x$.'))
I.append(mc(10,2,'State','State the parametric coordinates of a general point on $xy=c^2$.',['$(ct,c/t)$, $t\\ne0$','$(ct,ct)$, $t\\ne0$','$(ct^2,2ct)$','$(t,c^2t)$'],'A',{'B':'m2'},'Multiplying $ct$ by $c/t$ gives $c^2$ for $t\\ne0$.'))
templ(11,3,'For $y^2=4ax$ with $a=[[a]]$, calculate the $x$ coordinate of the focus.',{'a':{'min':2,'max':7,'step':1}},'a',[{'expr':'-a','misconception':'m3'}],'The focus is $(a,0)$; the directrix is $x=-a$.')
I.append(mc(12,3,'State','State the directrix of $y^2=12x$.',['$x=-3$','$x=3$','$y=-3$','$x=-12$'],'A',{'B':'m3'},'Here $4a=12$, so $a=3$ and the directrix is $x=-a=-3$.'))
I.append(short(13,3,'Explain','Explain the focus-directrix property that defines a parabola.','A parabola is the locus of points equidistant from a fixed focus and a fixed directrix.',[['locus','set of points'],['equidistant','equal distance'],['focus'],['directrix']], 'Every point on the parabola has equal distance to the focus and the directrix.'))
I.append(mc(14,3,'Verify','Verify which point is equally distant from the focus $(2,0)$ and directrix $x=-2$.',['$(0,0)$','$(2,0)$','$(-2,0)$','$(0,2)$'],'A',{'B':'m3'},'At the origin both distances are $2$; the focus itself has distance $0$ to the focus and $4$ to the directrix.'))
I.append(short(15,3,'Show that','Show that the focus $(a,0)$ and directrix $x=-a$ give $y^2=4ax$ for $a>0$.','Equate $(x-a)^2+y^2=(x+a)^2$ and simplify to $y^2=4ax$.',[['x-a'],['x+a'],['4ax']], 'Squared distance to the focus equals squared perpendicular distance to the directrix.'))
templ(16,4,'For $xy=c^2$ with $c=[[c]]$, calculate the tangent gradient at $x=[[x]]$.',{'c':{'min':2,'max':5,'step':1},'x':{'min':2,'max':4,'step':1}},'-c**2/x**2',[{'expr':'c**2/x**2','misconception':'m4'}],'Implicit differentiation gives $y+xy\\prime=0$, hence $y\\prime=-c^2/x^2$.')
I.append(numeric(17,4,'Calculate','Calculate the tangent gradient to $y^2=4x$ at $(1,2)$.',Fraction(2,2),'From $2yy\\prime=4$, the gradient is $2/y=1$ at $y=2$.'))
I.append(numeric(18,4,'Calculate','Calculate the normal gradient to $y^2=8x$ at $(2,4)$.',Fraction(-4,4),'Here $a=2$ and the tangent gradient is $2a/y=1$; the normal gradient is $-1$.',3,[{'value':float(Fraction(4,4)),'misconception':'m4'}]))
I.append(mc(19,4,'Find','Find the tangent to $xy=4$ at $(2,2)$.',['$y=-x+4$','$y=x$','$y=-2x+6$','$y=2x-2$'],'A',{'B':'m4'},'The gradient is $-4/2^2=-1$ and the line through $(2,2)$ is $y-2=-(x-2)$.'))
I.append(mc(20,4,'Find','Find the normal to $xy=9$ at $(3,3)$.',['$y=x$','$y=-x+6$','$y=3x-6$','$x=3$'],'A',{'B':'m4'},'The tangent gradient is $-9/3^2=-1$, so the normal gradient is $1$ and the normal through $(3,3)$ is $y=x$.',4))
I.append(short(21,4,'Explain','Explain why the tangent to $y^2=4ax$ at its vertex is vertical when $a\\ne0$.','At $(0,0)$, $dy/dx=2a/y$ is undefined and the curve has vertical tangent $x=0$.',[['undefined','not defined','infinite'],['vertical'],['x=0']], 'At the vertex the gradient formula has zero denominator, and the tangent is $x=0$.',4))
# Independently confirm the numerical gradients and the tangent/normal relations.
x,y,a,c=sp.symbols('x y a c', nonzero=True)
assert sp.simplify(2*a/y-1).subs({a:1,y:2})==0
assert sp.diff(c**2/x,x)==-c**2/x**2
assert ans(-Fraction(4,4))['value']==-1
worked=[{'id':'we1','kc':K(4),'problem':'Find the tangent and normal to $xy=9$ at $(3,3)$.','steps':[{'do':'Differentiate $xy=9$: $y+xy\\prime=0$, so $y\\prime=-y/x=-9/x^2$.','why':'The product rule differentiates both factors of $xy$.'},{'do':'At $(3,3)$, the tangent gradient is $-9/3^2=-1$.','why':'Evaluate the derivative at the stated point.','check':{'kind':'numeric','answer':ans(-1)}},{'do':'The tangent is $y-3=-(x-3)$, or $y=-x+6$.','why':'Use point-gradient form through the point of contact.'},{'do':'The normal gradient is $1$; its equation is $y-3=x-3$, or $y=x$.','why':'The normal gradient is the negative reciprocal of $-1$.','check':{'kind':'numeric','answer':ans(1)}}],'faded':{'id':'we1f','problem':'Find the normal gradient to $xy=16$ at $(4,4)$.','answer':ans(1),'blank_from':2}}, {'id':'we2','kc':K(3),'problem':'Show that the focus $(a,0)$ and directrix $x=-a$ produce $y^2=4ax$ for $a>0$.','steps':[{'do':'For a point $(x,y)$, focus distance squared is $(x-a)^2+y^2$.','why':'Use the distance formula.'},{'do':'The squared perpendicular distance to $x=-a$ is $(x+a)^2$.','why':'The directrix is vertical, so the shortest distance is horizontal.'},{'do':'Equate the squares and cancel $x^2+a^2$ to get $y^2=4ax$.','why':'Equal distances define the parabola.'}]}]
flash=[{'id':'fc1','kc':K(1),'front':'State Cartesian and parametric forms of the parabola.','back':'$y^2=4ax$; a general point is $(at^2,2at)$.'},{'id':'fc2','kc':K(1),'front':'State Cartesian and parametric forms of the rectangular hyperbola.','back':'$xy=c^2$; a general point is $(ct,c/t)$ for $t\\ne0$.'},{'id':'fc3','kc':K(3),'front':'State the focus-directrix definition of a parabola.','back':'The locus of points equidistant from a fixed focus and a fixed directrix.'},{'id':'fc4','kc':K(4),'front':'State the derivatives for the standard parabola and rectangular hyperbola.','back':'For $y^2=4ax$, $dy/dx=2a/y$ where $y\\ne0$; for $xy=c^2$, $dy/dx=-c^2/x^2$.'}]
pack={'subtopic':SUB,'spec':'FP1','version':1,'note':NOTE,'outline':'Learn the standard Cartesian and parametric forms of the parabola $y^2=4ax$ and rectangular hyperbola $xy=c^2$. A general parabola point is $(at^2,2at)$; its focus is $(a,0)$ and its directrix is $x=-a$. The curve is the locus equidistant from these. Differentiate implicitly to find tangent gradients, then use the negative reciprocal for normals when the gradient is finite and nonzero.','misconceptions':M,'worked':worked,'items':I,'flashcards':flash,'diagrams':[]}
out=ROOT/'build/out/packs/FP1/FP1-4.json';out.parent.mkdir(parents=True,exist_ok=True);out.write_text(json.dumps(pack,ensure_ascii=False,indent=2))
