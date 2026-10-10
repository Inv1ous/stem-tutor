"""Generate FP1-6; all matrix answers, distractors, and worked checks use SymPy."""
import json
from pathlib import Path
from sympy import Matrix, eye, cos, sin, pi, simplify

ROOT = Path(__file__).resolve().parents[3]
SUB = 'FP1-6'
NOTE = 'Subjects/Maths/FP1 Further Pure Mathematics 1/6 Transformations using matrices.md'
K = {i: f'{SUB}.{i}' for i in range(1, 5)}
def mat(x): return Matrix(x)
def tex(A): return r'\begin{pmatrix}' + r'\\'.join('&'.join(str(v) for v in A.row(i)) for i in range(A.rows)) + r'\end{pmatrix}'
def val(x): return {'value': float(x), 'unit': '', 'exact': True}
def ck(x): return {'kind':'numeric','answer':val(x)}
def ent(A,r,c): return A[r-1,c-1]
def verified(A,v):
    w=A*v
    assert all(simplify(w[i]-sum(A[i,j]*v[j] for j in range(2)))==0 for i in range(2))
    return w
items=[]
def numeric(k,stem,ans,exp,hints,wrong=(),difficulty=2,marks=2,word='Calculate'):
    assert len(hints)==3 and all(float(w)!=float(ans) for w,_ in wrong)
    items.append({'id':f'{SUB}-i{len(items)+1:02}','kcs':[K[k]],'kind':'numeric','difficulty':difficulty,'command_word':word,'source':{'type':'generated'},'stem':stem,'marks':marks,'answer':val(ans),'explanation':exp,'hints':hints,'distractors':[{'value':float(w),'misconception':m} for w,m in wrong]})
def mcq(k,stem,opts,key,exp,hints,wrong={},difficulty=2):
    assert sorted(opts)==list('ABCD') and len(set(opts.values()))==4 and len(hints)==3
    items.append({'id':f'{SUB}-i{len(items)+1:02}','kcs':[K[k]],'kind':'mcq','difficulty':difficulty,'command_word':'State','source':{'type':'generated'},'stem':stem,'marks':1,'options':opts,'answer':key,'distractors':wrong,'shuffle':True,'explanation':exp,'hints':hints})
mis=[
('m1',1,'The columns of a transformation matrix are the images of the wrong basis vectors.','The first column is the image of $(1,0)^T$ and the second is the image of $(0,1)^T$.','Apply the matrix to each basis vector in order.'),
('m2',2,'A stretch parallel to one axis scales the other coordinate.','A stretch parallel to the $x$-axis scales the $x$ coordinate; parallel to $y$ scales $y$.','Test the image of $(1,1)^T$.'),
('m3',3,'The first transformation named is the left matrix in the product.','For column vectors, $AB$ applies $B$ first, then $A$.','Write the rightmost matrix next to the input column.'),
('m4',4,'A zero determinant transformation can be reversed.','A zero determinant collapses area to zero and has no inverse.','Check $\det A$ before computing $A^{-1}$.'),
('m5',4,'An inverse of a product retains the original factor order.','The inverse of $AB$ is $B^{-1}A^{-1}$ when both exist.','Undo the last transformation first.')]
misconceptions=[{'id':m,'kc':K[k],'statement':s,'refutation':r,'contrast':c,'source':'research'} for m,k,s,r,c in mis]
worked=[]
def work(k,p,steps,fp,fa):
    worked.append({'id':f'we{k}','kc':K[k],'problem':p,'steps':steps,'faded':{'id':f'we{k}f','problem':fp,'answer':val(fa),'blank_from':1}})
def step(do,why,x=None):
    z={'do':do,'why':why}
    if x is not None:z['check']=ck(x)
    return z
# 1 Representation: image of columns and action on vectors.
A=mat([[2,-1],[3,4]])
for v in [mat([1,0]),mat([0,1]),mat([2,1]),mat([-1,2])]:
    w=verified(A,v)
    numeric(1,f'Calculate the first coordinate of the image of $v={tex(v)}$ under $T(v)=Av$, where $A={tex(A)}$.',w[0],f'Row 1 of $A$ dotted with $v$ gives ${w[0]}$.',['Use the first row of the matrix.','Take its dot product with the input column.','Multiply corresponding entries, then add.'],difficulty=4 if abs(v[0])+abs(v[1])>2 else 2)
B=mat([[3,5],[-2,1]])
numeric(1,f'Calculate the $(1,2)$ entry of the matrix whose images of $(1,0)^T$ and $(0,1)^T$ are respectively ${tex(B[:,0])}$ and ${tex(B[:,1])}$.',B[0,1],'The second image forms the second column, whose first coordinate is $5$.',['Use the standard basis vectors.','Their images become columns in the same order.','Read the top entry of the second image.'],wrong=[(B[0,0],'m1')],difficulty=3)
mcq(1,'State the matrix representing a linear map that sends $(1,0)^T$ to $(2,3)^T$ and $(0,1)^T$ to $(-1,4)^T$.',{'A':f'${tex(A)}$','B':f'${tex(A.T)}$','C':f'${tex(-A)}$','D':f'${tex(eye(2))}$'},'A','The images of the two basis vectors are the two columns of the matrix.',['Recall how a matrix acts on basis vectors.','Put each image in a column.','Use the image of the first basis vector first.'],{'B':'m1'},4)
work(1,f'Find the matrix $T$ with $T(1,0)^T=(2,3)^T$ and $T(0,1)^T=(-1,4)^T$, then find the first coordinate of $T(2,1)^T$.',[step(f'$T={tex(A)}$.','The basis-vector images are its columns.'),step(f'$T{tex(mat([2,1]))}={tex(verified(A,mat([2,1])))}$.','Linearity makes each output coordinate a row-column product.',ent(A*mat([2,1]),1,1))],f'Find the first coordinate of the image of $(1,2)^T$ under $T={tex(A)}$.',ent(A*mat([1,2]),1,1))
# 2 standard geometrical transformations.
Rx=mat([[1,0],[0,-1]]); Ry=mat([[-1,0],[0,1]]); Rxy=mat([[0,1],[1,0]]); Rnxy=mat([[0,-1],[-1,0]])
for label,M,v in [('the $x$-axis',Rx,mat([2,3])),('the $y$-axis',Ry,mat([2,3])),('the line $y=x$',Rxy,mat([2,3])),('the line $y=-x$',Rnxy,mat([2,3]))]:
    w=verified(M,v)
    numeric(2,f'Calculate the first coordinate of the image of ${tex(v)}$ under reflection in {label}.',w[0],f'The reflection matrix is ${tex(M)}$; its image is ${tex(w)}$.',['Identify the fixed line.','Write its reflection matrix.','Multiply it by the input column.'],difficulty=3)
Sx=mat([[3,0],[0,1]]);Sy=mat([[1,0],[0,2]]);En=mat([[-2,0],[0,-2]])
for name,M in [('stretch parallel to the $x$-axis by factor $3$',Sx),('stretch parallel to the $y$-axis by factor $2$',Sy),('enlargement about the origin by scale factor $-2$',En)]:
    v=mat([2,3]);w=verified(M,v)
    numeric(2,f'Calculate the first coordinate of the image of ${tex(v)}$ under a {name}.',w[0],f'The matrix is ${tex(M)}$, giving the image ${tex(w)}$.',['Identify which coordinates are scaled.','Put the factor on the matching diagonal entry.','Multiply the matrix by the vector.'],wrong=[(ent(Sy*v,1,1),'m2')] if M==Sx else (),difficulty=4 if M==En else 3)
R90=mat([[0,-1],[1,0]])
mcq(2,'State which option gives both the matrix $R$ for anticlockwise rotation through $60^\\circ$ about the origin and the image $R\\begin{pmatrix}2\\\\0\\end{pmatrix}$.',{'A':r'$R=\frac12\begin{pmatrix}1&-\sqrt3\\sqrt3&1\end{pmatrix}$; image $\begin{pmatrix}1\\sqrt3\end{pmatrix}$.','B':r'$R=\frac12\begin{pmatrix}1&\sqrt3\-\sqrt3&1\end{pmatrix}$; image $\begin{pmatrix}1\-\sqrt3\end{pmatrix}$.','C':r'$R=\frac12\begin{pmatrix}1&-\sqrt3\\sqrt3&1\end{pmatrix}$; image $\begin{pmatrix}-\sqrt3\1\end{pmatrix}$.','D':r'$R=\frac12\begin{pmatrix}1&\sqrt3\\sqrt3&-1\end{pmatrix}$; image $\begin{pmatrix}1\\sqrt3\end{pmatrix}.'},'A',r'For anticlockwise rotation, $R=\begin{pmatrix}\cos\theta&-\sin\theta\\sin\theta&\cos\theta\end{pmatrix}$. With $\theta=60^\circ$, $\cos\theta=1/2$ and $\sin\theta=\sqrt3/2$, so $R=\frac12\begin{pmatrix}1&-\sqrt3\\sqrt3&1\end{pmatrix}$ and $R(2,0)^T=(1,\sqrt3)^T$. B rotates clockwise. C uses the correct matrix but gives the wrong image. D has the same first column but is a reflection, not the requested rotation: its second column is wrong.', ['Use the general anticlockwise rotation matrix.','Substitute $\\cos60^\\circ=1/2$ and $\\sin60^\\circ=\\sqrt3/2$.','The image of $(2,0)^T$ is twice the first column; check both columns of the matrix as well.'],difficulty=3)
items[-1].update(json.loads(r'''{"stem": "State which option gives both the matrix $R$ for anticlockwise rotation through $60^\\circ$ about the origin and the image $R\\begin{pmatrix}2\\\\0\\end{pmatrix}$.", "marks": 2, "difficulty": 3, "options": {"A": "$R=\\frac12\\begin{pmatrix}1&-\\sqrt3\\\\\\sqrt3&1\\end{pmatrix}$; image $\\begin{pmatrix}1\\\\\\sqrt3\\end{pmatrix}$.", "B": "$R=\\frac12\\begin{pmatrix}1&\\sqrt3\\\\-\\sqrt3&1\\end{pmatrix}$; image $\\begin{pmatrix}1\\\\-\\sqrt3\\end{pmatrix}$.", "C": "$R=\\frac12\\begin{pmatrix}1&-\\sqrt3\\\\\\sqrt3&1\\end{pmatrix}$; image $\\begin{pmatrix}-\\sqrt3\\\\1\\end{pmatrix}$.", "D": "$R=\\frac12\\begin{pmatrix}1&\\sqrt3\\\\\\sqrt3&-1\\end{pmatrix}$; image $\\begin{pmatrix}1\\\\\\sqrt3\\end{pmatrix}$."}, "answer": "A", "distractors": {}, "explanation": "For anticlockwise rotation, $R=\\begin{pmatrix}\\cos\\theta&-\\sin\\theta\\\\\\sin\\theta&\\cos\\theta\\end{pmatrix}$. With $\\theta=60^\\circ$, $\\cos\\theta=1/2$ and $\\sin\\theta=\\sqrt3/2$, so $R=\\frac12\\begin{pmatrix}1&-\\sqrt3\\\\\\sqrt3&1\\end{pmatrix}$ and $R(2,0)^T=(1,\\sqrt3)^T$. B rotates clockwise. C uses the correct matrix but gives the wrong image. D has the same first column but is a reflection, not the requested rotation: its second column is wrong.", "hints": ["Use the general anticlockwise rotation matrix.", "Substitute $\\cos60^\\circ=1/2$ and $\\sin60^\\circ=\\sqrt3/2$.", "The image of $(2,0)^T$ is twice the first column; check both columns of the matrix as well."]}'''))
assert mat([[cos(pi/2),-sin(pi/2)],[sin(pi/2),cos(pi/2)]])==R90
work(2,f'Find the matrix for anticlockwise rotation through $90^\\circ$ and the second coordinate of the image of $(2,3)^T$.',[step(f'$R={tex(R90)}$.','Substitute $\cos90^\circ=0$ and $\sin90^\circ=1$ in the rotation formula.'),step(f'$R{tex(mat([2,3]))}={tex(R90*mat([2,3]))}$.','Multiply the rotation matrix by the column vector.',ent(R90*mat([2,3]),2,1))],f'Find the second coordinate after reflecting $(4,-1)^T$ in the line $y=x$.',ent(Rxy*mat([4,-1]),2,1))
# 3 composition, rightmost first.
comps=[(R90,Sx,mat([1,2])),(Ry,R90,mat([2,1])),(Sx,Rxy,mat([-1,2])),(Rxy,Rx,mat([3,-2])),(Sy,R90,mat([2,-3]))]
for P,Q,v in comps:
    M=P*Q;w=verified(M,v);wrong=(Q*P*v)[0]
    numeric(3,f'Calculate the first coordinate of $PQv$ for $P={tex(P)}$, $Q={tex(Q)}$ and $v={tex(v)}$.',w[0],f'Apply $Q$ first and then $P$: $PQ={tex(M)}$, so $PQv={tex(w)}$.',['Start at the right of the product.','Multiply $Qv$ before applying $P$.','Keep the order of matrix multiplication.'],wrong=[(wrong,'m3')] if wrong!=w[0] else (),difficulty=4)
mcq(3,'A reflection in the $x$-axis is followed by a reflection in the line $y=x$. State which option gives both the combined matrix and the equivalent single transformation.',{'A':r'$\begin{pmatrix}0&-1\\1&0\end{pmatrix}$; anticlockwise rotation through $90^\circ$ about the origin.','B':r'$\begin{pmatrix}0&1\-1&0\end{pmatrix}$; clockwise rotation through $90^\circ$ about the origin.','C':r'$\begin{pmatrix}0&1\\1&0\end{pmatrix}$; reflection in the line $y=x$.','D':r'$\begin{pmatrix}-1&0\0&-1\end{pmatrix}$; rotation through $180^\circ$ about the origin.'},'A',r'Let $X=\begin{pmatrix}1&0\0&-1\end{pmatrix}$ represent reflection in the $x$-axis and $Y=\begin{pmatrix}0&1\1&0\end{pmatrix}$ represent reflection in $y=x$. The first transformation is on the right, so the combined matrix is $YX=\begin{pmatrix}0&-1\1&0\end{pmatrix}$. It sends $(x,y)^T$ to $(-y,x)^T$, an anticlockwise rotation through $90^\circ$ about the origin. B reverses the order by using $XY$; C omits the first reflection; D gives a half-turn instead of a quarter-turn.', ['Write the matrices for the two reflections.','The reflection in the $x$-axis happens first, so put its matrix on the right.','Multiply the matrices and compare the product with the standard rotation matrix.'],{'B':'m3'},3)
items[-1].update(json.loads(r'''{"stem": "A reflection in the $x$-axis is followed by a reflection in the line $y=x$. State which option gives both the combined matrix and the equivalent single transformation.", "marks": 2, "difficulty": 3, "options": {"A": "$\\begin{pmatrix}0&-1\\\\1&0\\end{pmatrix}$; anticlockwise rotation through $90^\\circ$ about the origin.", "B": "$\\begin{pmatrix}0&1\\\\-1&0\\end{pmatrix}$; clockwise rotation through $90^\\circ$ about the origin.", "C": "$\\begin{pmatrix}0&1\\\\1&0\\end{pmatrix}$; reflection in the line $y=x$.", "D": "$\\begin{pmatrix}-1&0\\\\0&-1\\end{pmatrix}$; rotation through $180^\\circ$ about the origin."}, "answer": "A", "distractors": {"B": "m3"}, "explanation": "Let $X=\\begin{pmatrix}1&0\\\\0&-1\\end{pmatrix}$ represent reflection in the $x$-axis and $Y=\\begin{pmatrix}0&1\\\\1&0\\end{pmatrix}$ represent reflection in $y=x$. The first transformation is on the right, so the combined matrix is $YX=\\begin{pmatrix}0&-1\\\\1&0\\end{pmatrix}$. It sends $(x,y)^T$ to $(-y,x)^T$, an anticlockwise rotation through $90^\\circ$ about the origin. B reverses the order by using $XY$; C omits the first reflection; D gives a half-turn instead of a quarter-turn.", "hints": ["Write the matrices for the two reflections.", "The reflection in the $x$-axis happens first, so put its matrix on the right.", "Multiply the matrices and compare the product with the standard rotation matrix."]}'''))
P=R90;Q=Sx;M=P*Q
work(3,f'Find the combined matrix for a stretch parallel to the $x$-axis by $3$, followed by anticlockwise rotation through $90^\\circ$, and calculate the first coordinate of the image of $(1,2)^T$.',[step(f'$R={tex(P)}$, $S={tex(Q)}$, so the combined matrix is $RS={tex(M)}$.','The stretch happens first, so its matrix is on the right.'),step(f'$RS{tex(mat([1,2]))}={tex(M*mat([1,2]))}$.','Apply the product to the column vector.',ent(M*mat([1,2]),1,1))],f'Find the first coordinate after $SR$ acts on $(1,2)^T$, with $S={tex(Q)}$, $R={tex(P)}$.',ent(Q*P*mat([1,2]),1,1))
# 4 determinants, inverse, area factor.
As=[mat([[2,0],[0,3]]),mat([[0,-1],[1,0]]),mat([[1,1],[0,2]]),mat([[2,1],[1,2]])]
for C in As:
    d=C.det();assert d!=0 and C*C.inv()==eye(2)
    numeric(4,f'Calculate the area scale factor of the transformation with matrix $A={tex(C)}$.',abs(d),f'$\det A={d}$, so area is multiplied by $|\det A|={abs(d)}$.',['Calculate the determinant.','Area uses its magnitude.','A negative determinant changes orientation, not the sign of area.'],difficulty=3)
C=mat([[2,1],[0,1]]);D=R90;H=C*D;assert H.inv()==D.inv()*C.inv()
numeric(4,f'Calculate the $(1,2)$ entry of the inverse of the combined matrix $CD$, where $C={tex(C)}$ and $D={tex(D)}$.',ent(H.inv(),1,2),f'$(CD)^{{-1}}=D^{{-1}}C^{{-1}}={tex(H.inv())}$.',['Check both determinants are nonzero.','Reverse factor order when finding a product inverse.','Read the top-right entry of the result.'],wrong=[(ent(C.inv()*D.inv(),1,2),'m5')] if ent(C.inv()*D.inv(),1,2)!=ent(H.inv(),1,2) else (),difficulty=4)
Sing=mat([[1,2],[2,4]])
numeric(4,f'Calculate the determinant of $A={tex(Sing)}$ and hence decide whether its transformation has an inverse. Enter the determinant.',Sing.det(),'The determinant is $1(4)-2(2)=0$, so the plane is collapsed to a line and there is no inverse.',['Multiply diagonal entries.','Subtract the off-diagonal product.','A zero result means no inverse.'],difficulty=4,marks=3,word='Find')
mcq(4,'State what $\det A=0$ means for a two-dimensional transformation.',{'A':'Areas collapse to zero and no inverse exists.','B':'Areas are unchanged and the inverse is $A$.','C':'Orientation reverses but area is unchanged.','D':'Every point is fixed.'},'A','The determinant is the signed area scale; zero collapses every area and makes the matrix singular.',['Recall the area-scale interpretation.','Consider what zero does to a unit square.','Decide whether the collapsed image can be reversed.'],{'B':'m4'},3)
work(4,f'Find the inverse of $A={tex(C)}$ and its area scale factor.',[step(f'$\det A={C.det()}$.','A nonzero determinant guarantees an inverse.',C.det()),step(f'$A^{{-1}}={tex(C.inv())}$.','Use the two-by-two inverse formula; checking $AA^{-1}=I$ verifies it.',ent(C.inv(),1,2)),step(f'Area scale factor $=|\det A|={abs(C.det())}$.','Area cannot have a negative scale.',abs(C.det()))],f'Find the $(1,1)$ entry of the inverse of $A={tex(mat([[3,1],[1,1]]))}$.',ent(mat([[3,1],[1,1]]).inv(),1,1))
pack={'subtopic':SUB,'spec':'FP1','version':1,'note':NOTE,'outline':'A linear transformation of two-dimensional column vectors is represented by a $2\\times2$ matrix whose columns are the images of the standard basis. Standard matrices give reflections in the axes and $y=\\pm x$, rotations about the origin, stretches parallel to either coordinate axis and nonzero real enlargements about the origin. For a combined transformation, $AB$ applies $B$ first, then $A$. A nonzero determinant gives an inverse; $(AB)^{-1}=B^{-1}A^{-1}$. The absolute determinant is the area scale factor. A zero determinant collapses area and has no inverse.','misconceptions':misconceptions,'worked':worked,'items':items,'flashcards':[],'diagrams':[]}
assert len(worked)==4 and len(items)>=24
out=ROOT/'build/out/packs/FP1/FP1-6.json';out.parent.mkdir(parents=True,exist_ok=True);out.write_text(json.dumps(pack,ensure_ascii=False,indent=1))
print(f'Wrote {out}: {len(items)} items, {len(worked)} worked')
