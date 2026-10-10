import json
from pathlib import Path
import sympy as s

root=Path(__file__).resolve().parents[3]
sub='P2-3'; kc='P2-3.1'
def num(v):
    return {'value':float(s.N(v)),'unit':'','exact':True}
def item(n,kind,word,stem,explanation,difficulty=2,**kw):
    d={'id':f'{sub}-i{n:02d}','kcs':[kc],'kind':kind,'difficulty':difficulty,'command_word':word,'source':{'type':'generated'},'stem':stem,'marks':1,'explanation':explanation,'hints':['Identify the centre, radius, or relevant circle property.','Translate the geometric fact into an equation or perpendicular slope.','Substitute the given coordinates before simplifying.']}
    d.update(kw)
    return d
# All coordinates, lengths and option values below are computed from exact arithmetic.
C=s.Point(3,-2); r=s.Integer(5); P=s.Point(6,2)
assert P.distance(C)==r
A=s.Point(-2,-2); B=s.Point(8,-2)
assert A.distance(C)==r and B.distance(C)==r and s.Line(A,P).is_perpendicular(s.Line(P,B))
M=s.Point(3,2); U=s.Point(0,2); V=s.Point(6,2)
assert U.distance(C)==r and V.distance(C)==r and M==s.Segment(U,V).midpoint
assert s.Line(C,M).is_perpendicular(s.Line(U,V))
mis=[
 {'id':'m1','kc':kc,'statement':'The centre of $(x-a)^2+(y-b)^2=r^2$ is $(-a,-b)$.','refutation':'The centre is $(a,b)$; set each bracket to zero.','contrast':'$(x-3)^2+(y+2)^2=25$ has centre $(3,-2)$.','source':'research'},
 {'id':'m2','kc':kc,'statement':'The right-hand side of a circle equation is the radius.','refutation':'It is the radius squared, so the radius is its positive square root.','contrast':'A right-hand side of $25$ means radius $5$.','source':'research'},
 {'id':'m3','kc':kc,'statement':'A tangent has the same gradient as the radius at contact.','refutation':'The tangent and radius at contact are perpendicular; their nonzero gradients have product $-1$.','contrast':'A radius gradient $4/3$ gives tangent gradient $-3/4$.','source':'research'},
 {'id':'m4','kc':kc,'statement':'A perpendicular from the centre can meet a chord away from its midpoint.','refutation':'The perpendicular from the centre to a chord bisects that chord.','contrast':'The midpoint of $(0,2)$ and $(6,2)$ is $(3,2)$.','source':'research'}]
items=[
 item(1,'mcq','State','State the centre of $(x-3)^2+(y+2)^2=25$.','The brackets vanish at $(3,-2)$; reversing signs twice gives the common wrong answer.',options={'A':'$(3,-2)$','B':'$(-3,2)$','C':'$(3,2)$','D':'$(-3,-2)$'},answer='A',distractors={'B':'m1','C':'m1','D':'m1'},shuffle=True),
 item(2,'numeric','Find','Find the radius of $(x-3)^2+(y+2)^2=25$.','The radius squared is $25$, so the positive radius is $5$.',answer=num(s.sqrt(r*r)),distractors=[{'value':float(r*r),'misconception':'m2'}]),
 item(3,'mcq','Find','Find the equation of the circle with centre $(3,-2)$ and radius $5$.','Substitute $a=3$, $b=-2$, $r=5$ into the standard form.',options={'A':'$(x-3)^2+(y+2)^2=25$','B':'$(x+3)^2+(y-2)^2=25$','C':'$(x-3)^2+(y+2)^2=5$','D':'$(x+3)^2+(y-2)^2=5$'},answer='A',distractors={'B':'m1','C':'m2','D':'m1'},shuffle=True),
 item(4,'mcq','Verify','Verify which point lies on $(x-3)^2+(y+2)^2=25$.','For $(6,2)$, the squared displacement from $(3,-2)$ is $3^2+4^2=25$.',options={'A':'$(6,2)$','B':'$(3,2)$','C':'$(6,-2)$','D':'$(8,2)$'},answer='A',shuffle=True),
 item(5,'numeric','Find','The diameter of a circle has endpoints $(-2,-2)$ and $(8,-2)$. Find its radius.','The diameter is $10$ units, so its radius is half the diameter.',answer=num(A.distance(B)/2),difficulty=3),
 item(6,'mcq','State','State the angle at a point on a circle subtended by a diameter.','The angle in a semicircle is a right angle.',options={'A':'$90^\\circ$','B':'$45^\\circ$','C':'$180^\\circ$','D':'It depends on the point.'},answer='A',shuffle=True),
 item(7,'numeric','Find','A chord has endpoints $(0,2)$ and $(6,2)$. Find the $x$-coordinate where the perpendicular from the centre meets this chord.','The perpendicular from the centre bisects the chord, whose midpoint has $x$-coordinate $3$.',answer=num(M.x),difficulty=3,distractors=[{'value':float(U.x),'misconception':'m4'}]),
 item(8,'mcq','Find','The radius to a point of contact has gradient $4/3$. Find the gradient of the tangent there.','The tangent is perpendicular to the radius, so its gradient is the negative reciprocal $-3/4$.',options={'A':'$-3/4$','B':'$4/3$','C':'$3/4$','D':'$-4/3$'},answer='A',distractors={'B':'m3','D':'m3'},shuffle=True,difficulty=3),
 item(9,'mcq','Find','The centre is $(3,-2)$ and the tangent touches the circle at $(6,2)$. Find the tangent equation.','The radius gradient is $4/3$, so the tangent gradient is $-3/4$; through $(6,2)$ this is $y-2=-3(x-6)/4$.',options={'A':'$y-2=-3(x-6)/4$','B':'$y-2=4(x-6)/3$','C':'$y+2=-3(x-3)/4$','D':'$y-2=3(x-6)/4$'},answer='A',distractors={'B':'m3','D':'m3'},shuffle=True,difficulty=4),
 item(10,'short','Explain','Explain why the lines joining $(-2,-2)$ and $(8,-2)$ to $(6,2)$ are perpendicular.','The first two points are endpoints of a diameter of the circle centred at $(3,-2)$; the angle at $(6,2)$ is an angle in a semicircle.',rubric=[{'point':'An angle subtended by a diameter at the circumference is a right angle.','keywords':[['diameter'],['right angle','90']]}],difficulty=4),
]
worked=[{'id':'we1','kc':kc,'problem':'Find the tangent at $(6,2)$ to $(x-3)^2+(y+2)^2=25$.','steps':[{'do':'Read centre $(3,-2)$ and radius $5$.','why':'The standard form gives centre and radius directly.'},{'do':'Check $(6-3)^2+(2+2)^2=25$.','why':'The point must lie on the circle before it can be a contact point.','check':{'kind':'numeric','answer':num((P.x-C.x)**2+(P.y-C.y)**2)}},{'do':'Radius gradient $=(2-(-2))/(6-3)=4/3$; tangent gradient $=-3/4$.','why':'A tangent is perpendicular to the radius at contact.'},{'do':'Use point–gradient form: $y-2=-\\frac34(x-6)$.','why':'The tangent passes through the point of contact.'}], 'faded':{'id':'we1f','problem':'Find the gradient of the tangent to $(x-1)^2+(y-1)^2=25$ at $(4,5)$.','answer':num(-s.Rational(3,4)),'blank_from':2}}]
pack={'subtopic':sub,'spec':'P2','version':1,'note':'Subjects/Maths/P2 Pure Mathematics 2/3 Coordinate geometry in the (x, y) plane.md','outline':'A circle with centre $(a,b)$ and radius $r$ has equation $(x-a)^2+(y-b)^2=r^2$. Read the centre by setting each bracket to zero, and take the positive square root for the radius. A diameter subtends a right angle at the circumference. The perpendicular from the centre to a chord bisects the chord. At a point of contact, the tangent is perpendicular to the radius. Use midpoint and gradient methods to turn these properties into coordinate equations.','misconceptions':mis,'worked':worked,'items':items,'flashcards':[{'id':'fc1','kc':kc,'front':'State the standard equation of a circle with centre $(a,b)$ and radius $r$.','back':'$(x-a)^2+(y-b)^2=r^2$, with $r>0$.'},{'id':'fc2','kc':kc,'front':'State the angle-in-a-semicircle property.','back':'The angle subtended by a diameter at the circumference is a right angle.'},{'id':'fc3','kc':kc,'front':'State the chord and tangent perpendicularity properties.','back':'The perpendicular from the centre to a chord bisects the chord; the tangent at a point of contact is perpendicular to the radius there.'}],'diagrams':[]}
out=root/'build/out/packs/P2/P2-3.json';out.parent.mkdir(parents=True,exist_ok=True);out.write_text(json.dumps(pack,ensure_ascii=False,indent=1)+'\n');print(out)
