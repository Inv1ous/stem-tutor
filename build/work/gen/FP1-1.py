import json
from pathlib import Path
from sympy import I, expand, solve, symbols

ROOT=Path(__file__).resolve().parents[3]
sub='FP1-1'
kcs=[f'{sub}.{i}' for i in range(1,7)]
items=[]
mis=[
('m1',0,'The imaginary part of $a+ib$ is $ib$.','The imaginary part is the real coefficient $b$.','For $3+2i$, $\\operatorname{Im}(z)=2$.'),
('m2',1,'Divide complex numbers by dividing their real and imaginary parts separately.','Multiply numerator and denominator by the denominator’s conjugate.','$(1+i)/(1-i)=i$.'),
('m3',2,'Multiplication on an Argand diagram is vector addition.','Addition is vector addition; multiplication combines scale factors and rotations.','Multiplying by $i$ rotates through $90^\\circ$ anticlockwise.'),
('m4',3,'A negative discriminant means a quadratic has no roots.','It has two complex conjugate roots.','$x^2+1=0$ has roots $i$ and $-i$.'),
('m5',4,'A non-real root of a real-coefficient polynomial can occur alone.','Its conjugate is also a root.','If $2+i$ is a root, so is $2-i$.'),
('m6',5,'One given root of a quartic is enough to identify every other root.','Use conjugacy where applicable, divide by the resulting factor, then solve the residual quadratic.','A root $2+i$ gives factor $(x-2)^2+1$.')]
mis=[dict(id=a,kc=kcs[b],statement=c,refutation=d,contrast=e,source='research') for a,b,c,d,e in mis]

def add(k,stem,rubric,d=2,word='Find',marks=1,explanation=None):
    n=len(items)+1
    items.append(dict(id=f'{sub}-i{n:02}',kcs=[kcs[k]],kind='short',difficulty=d,command_word=word,source={'type':'generated'},stem=f'{word} {stem}' if word not in ('Explain','State') else f'{word} {stem}',marks=marks,rubric=[{'point':p,'keywords':[g if isinstance(g,list) else [g] for g in groups]} for p,groups in rubric],explanation=explanation or rubric[0][0],hints=['Recall the definition or relevant theorem.','Write the appropriate algebraic form.','Start with the real and imaginary parts or a known factor.']))

def num(k,stem,v,unit='',d=2,word='Calculate',explanation=None):
    n=len(items)+1
    items.append(dict(id=f'{sub}-i{n:02}',kcs=[kcs[k]],kind='numeric',difficulty=d,command_word=word,source={'type':'generated'},stem=f'{word} {stem}',marks=1,answer={'value':float(v),'unit':unit,'sf_ok':[2,3]},explanation=explanation or f'The required value is {v}.',hints=['Identify the complex number or polynomial.','Apply the relevant formula or factorisation.','Substitute the given values before simplifying.']))

def mcq(k,stem,opts,key,mid,d=2,word='Find'):
    n=len(items)+1
    items.append(dict(id=f'{sub}-i{n:02}',kcs=[kcs[k]],kind='mcq',difficulty=d,command_word=word,source={'type':'generated'},stem=f'{word} {stem}',marks=1,options=dict(zip('ABCD',opts)),answer=key,distractors={l:mid for l in 'ABCD' if l!=key},shuffle=True,explanation=f'{opts["ABCD".index(key)]} is correct by the relevant definition or algebra; the other options reflect the stated misconception.',hints=['Recall the appropriate definition.','Work through the algebra before choosing.','Check the real and imaginary components separately.']))

# Six distinct retrieval variants per KC.
add(0,'the real and imaginary parts of $z=a+ib$.',[('Real part is $a$.',['a']),('Imaginary part is $b$.',['b'])],1,'State',2)
num(0,'the modulus of $3+4i$.',5)
num(0,'the principal argument in radians of $1+i$.',__import__('math').pi/4,'rad')
mcq(0,'the conjugate of $3-2i$.',['$3+2i$','$-3+2i$','$3-2i$','$-3-2i$'],'A','m1')
add(0,'the condition for $a+ib=c+id$ to be equal.',[('Real parts and imaginary parts are equal.',['a=c','b=d'])],3,'State')
add(0,'the relation between $a+ib$ and $r\\cos\\theta+ir\\sin\\theta$.',[('$a=r\\cos\\theta$ and $b=r\\sin\\theta$.',['r\\cos','r\\sin'])],4,'Explain')

num(1,'the real part of $(2+i)(3-2i)$.',8)
num(1,'the imaginary part of $(2+i)(3-2i)$.',-1)
num(1,'the real part of $(1+i)/(1-i)$.',0,d=3)
mcq(1,'$(1+i)/(1-i)$.',['$i$','$1$','$-i$','$2i$'],'A','m2',3)
add(1,'the rule for the modulus of a product $z_1z_2$.',[('$|z_1z_2|=|z_1||z_2|$.',['|z_1|','|z_2|'])],2,'State')
add(1,'how to divide by $c+di$.',[('Multiply numerator and denominator by $c-di$.',['conjugate'])],4,'Explain')

add(2,'how $a+ib$ is plotted on an Argand diagram.',[('Plot the point $(a,b)$ on real and imaginary axes.',['a','b'])],1,'Explain')
num(2,'the real coordinate after adding $2+i$ and $3-4i$ on an Argand diagram.',5)
num(2,'the imaginary coordinate after adding $2+i$ and $3-4i$ on an Argand diagram.',-3)
mcq(2,'the image of $1+i$ after multiplication by $i$.',['$-1+i$','$1+2i$','$1-i$','$-1-i$'],'A','m3',3)
add(2,'the geometric effect of multiplication by $i$.',[('It is a $90^\\circ$ anticlockwise rotation about the origin.',['90','anticlockwise'])],4,'Explain')
add(2,'the geometric meaning of a quotient $z_1/z_2$ when $z_2\\ne0$.',[('Its modulus is $|z_1|/|z_2|$ and its angle is the difference of arguments.',['modulus','angle'])],4,'Explain')

num(3,'the positive imaginary coefficient of a root of $x^2+16=0$.',4)
num(3,'the real part of a root of $x^2-4x+13=0$.',2)
num(3,'the positive imaginary coefficient of a root of $x^2-4x+13=0$.',3)
mcq(3,'the roots of $x^2+4=0$.',['$\\pm2i$','$\\pm2$','$4i$','$0$'],'A','m4',3)
add(3,'why the non-real roots of a real-coefficient quadratic are conjugates.',[('The quadratic formula has real common part and opposite imaginary parts.',['opposite','imaginary'])],4,'Explain')
add(3,'the discriminant condition for non-real roots.',[('$b^2-4ac<0$.',['b^2-4ac','0'])],2,'State')

num(4,'the real root of a monic cubic with roots $1+i$, $1-i$ and one real root, given constant term $-6$.',3,d=4)
num(4,'the coefficient of $x^2$ in $(x-3)((x-1)^2+1)$.',-5,d=3)
num(4,'the value of $(1+i)(1-i)$.',2)
mcq(4,'the root paired with $2+3i$ in a real-coefficient cubic.',['$2-3i$','$-2+3i$','$-2-3i$','$3+2i$'],'A','m5')
add(4,'the quadratic factor from roots $a+bi$ and $a-bi$.',[('The factor is $(x-a)^2+b^2$.',['(x-a)^2','b^2'])],3,'State')
add(4,'how to finish a real-coefficient cubic after finding the conjugate pair.',[('Divide by their real quadratic factor and solve the remaining linear factor.',['quadratic','linear'])],4,'Explain')

items[24].update(kind='short',difficulty=4,command_word='Find',stem='Given that $1+2i$ is a root of $x^3-6x^2+13x-20=0$, find all three roots. Show the conjugate root, form its real quadratic factor, and use polynomial division to find the remaining root.',marks=4,rubric=[{'point':'$1-2i$ is also a root because the coefficients are real.','keywords':[['1-2i']]},{'point':'The conjugate pair gives $(x-(1+2i))(x-(1-2i))=x^2-2x+5$.','keywords':[['x^2-2x+5']]},{'point':'Polynomial division by $x^2-2x+5$ gives quotient $x-4$ and remainder zero.','keywords':[['x-4']]},{'point':'The remaining real root is $4$; all roots are $1+2i,1-2i,4$.','keywords':[['4']]}],explanation='Real coefficients imply that $1-2i$ is also a root. The conjugate factors multiply to $(x-1)^2+4=x^2-2x+5$. In polynomial division the first quotient term is $x$, leaving $-4x^2+8x-20$ after subtraction; the next term is $-4$, leaving zero. Thus $x^3-6x^2+13x-20=(x^2-2x+5)(x-4)$ and all roots are $1+2i,1-2i,4$.',hints=['Use the conjugate-root theorem for real coefficients.','Multiply the two conjugate linear factors.','Divide the cubic by $x^2-2x+5$ and solve the remaining linear equation.'])
items[24].pop('answer',None)

x=symbols('x')
p=expand((x**2-4*x+5)*(x-1)*(x+2))
num(5,'the coefficient of $x^3$ in $(x^2-4x+5)(x-1)(x+2)$.',p.coeff(x,3),d=3)
num(5,'the real root of $(x^2-4x+5)(x-1)(x+2)=0$ that is positive.',1,d=3)
num(5,'the real root of $(x^2-4x+5)(x-1)(x+2)=0$ that is negative.',-2,d=3)
mcq(5,'the quadratic factor implied by a root $2+i$ of a real-coefficient quartic.',['$x^2-4x+5$','$x^2-4x+3$','$x^2+4x+5$','$x^2-2x+5$'],'A','m6',3)
add(5,'the next algebraic step after finding a conjugate pair of quartic roots.',[('Divide the quartic by the corresponding real quadratic and solve the remaining quadratic.',['divide','quadratic'])],4,'Explain')
add(5,'how two known real roots of a quartic help solve it completely.',[('Use their linear factors, divide the quartic, then solve the remaining quadratic.',['linear','quadratic'])],4,'Explain')

items[31].update(kind='short',difficulty=4,command_word='Find',stem='Given that $2+i$ is a root of $x^4-3x^3-x^2+13x-10=0$, find all four roots. Show the conjugate root, form its real quadratic factor, and use polynomial division to find and solve the remaining quadratic.',marks=5,rubric=[{'point':'$2-i$ is also a root because the coefficients are real.','keywords':[['2-i']]},{'point':'The conjugate factors multiply to $x^2-4x+5$.','keywords':[['x^2-4x+5']]},{'point':'Polynomial division gives quotient $x^2+x-2$ and remainder zero.','keywords':[['x^2+x-2']]},{'point':'Factor the residual quadratic as $(x-1)(x+2)$.','keywords':[['x-1'],['x+2']]},{'point':'All four roots are $2+i,2-i,1,-2$.','keywords':[['2+i'],['2-i'],['1'],['-2']]}],explanation='The real coefficients give the conjugate root $2-i$, so $x^2-4x+5$ is a factor. Polynomial division has successive quotient terms $x^2$, $x$, and $-2$, leaving successive remainders $x^3-6x^2+13x-10$, $-2x^2+8x-10$, and zero. Hence the quartic equals $(x^2-4x+5)(x^2+x-2)=(x^2-4x+5)(x-1)(x+2)$. Its roots are $2+i,2-i,1,-2$.',hints=['Use real coefficients to find the conjugate root.','Multiply the conjugate factors and divide the quartic by $x^2-4x+5$.','Factor the residual quadratic and list all four roots.'])
items[31].pop('answer',None)

worked=[]
def work(k,problem,steps,faded,answer):
    worked.append({'id':f'we{k+1}','kc':kcs[k],'problem':problem,'steps':[{'do':a,'why':b} for a,b in steps],'faded':{'id':f'we{k+1}f','problem':faded,'answer':{'value':float(answer),'unit':'','sf_ok':[2,3]},'blank_from':1}})
work(1,'Calculate $(3+2i)/(1-i)$.',[('Multiply top and bottom by $1+i$.','The conjugate makes the denominator real.'),('$(3+2i)(1+i)/(1+1)=(1+5i)/2$.','Expand using $i^2=-1$.'),('The quotient is $1/2+(5/2)i$.','Separate real and imaginary parts.')],'Find the real part of $(2+i)/(1-i)$.',.5)
work(3,'Solve $x^2-4x+13=0$.',[('Use $x=(4\\pm\\sqrt{16-52})/2$.','The quadratic formula still applies when the discriminant is negative.'),('$\\sqrt{-36}=6i$, so $x=(4\\pm6i)/2$.','Use $i^2=-1$.'),('$x=2\\pm3i$.','Simplify both parts.')],'Find the positive imaginary coefficient of the roots of $x^2-6x+13=0$.',2)
work(4,'Given $1+i$ is a root of $x^3-5x^2+8x-6=0$, find all roots.',[('$1-i$ is also a root.','Coefficients are real.'),('$(x-(1+i))(x-(1-i))=x^2-2x+2$.','Multiply conjugate factors.'),('Divide to get $(x^2-2x+2)(x-3)$; roots are $1+i,1-i,3$.','The remaining factor is linear.')],'Given $1+i$ is a root of $(x^2-2x+2)(x-4)=0$, find the real root.',4)
work(5,'Given $2+i$ is a root of $x^4-3x^3-x^2+13x-10=0$, find all roots.',[('$2-i$ is also a root.','Real coefficients give conjugate roots.'),('The pair gives factor $x^2-4x+5$.','Multiply conjugate linear factors.'),('Divide by $x^2-4x+5$: quotient terms $x^2$, $x$, $-2$ leave successive remainders $x^3-6x^2+13x-10$, $-2x^2+8x-10$, $0$. Thus the quotient is $x^2+x-2=(x-1)(x+2)$, and all roots are $2+i,2-i,1,-2$.','Removing the conjugate quadratic factor reduces the quartic to a quadratic, whose roots supply the two remaining roots.')],'Find the positive real root of $(x^2-4x+5)(x-3)(x+1)=0$.',3)

pack={'subtopic':sub,'spec':'FP1','version':1,'note':'Subjects/Maths/FP1 Further Pure Mathematics 1/1 Complex numbers.md','outline':'Write $z=a+ib$ or $r\\cos\\theta+ir\\sin\\theta$; identify its parts, modulus, argument and conjugate. Perform arithmetic using $i^2=-1$ and conjugate denominators for division. The Argand diagram shows points and vector addition; multiplication and division correspond to scaling and rotation. Apply the quadratic formula to negative discriminants, then use conjugate pairs and polynomial division to solve cubics and quartics with real coefficients.','misconceptions':mis,'worked':worked,'items':items,'flashcards':[{'id':f'fc{j+1}','kc':kcs[0],'front':q,'back':a} for j,(q,a) in enumerate([('What is a complex number?','A number $a+ib$, where $a,b$ are real and $i^2=-1$.'),('What are the real and imaginary parts of $a+ib$?','$\\operatorname{Re}(z)=a$ and $\\operatorname{Im}(z)=b$.'),('What are modulus and argument?','The modulus is $|z|=\\sqrt{a^2+b^2}$; the argument is the angle from the positive real axis.'),('What is the conjugate of $a+ib$?','$a-ib$.'),('When are two complex numbers equal?','Their real parts are equal and their imaginary parts are equal.')])],'diagrams':[]}
path=ROOT/'build/out/packs/FP1/FP1-1.json'
path.write_text(json.dumps(pack,ensure_ascii=False,indent=1)+'\n')
print(path, len(items),len(worked),p)
