"""Generate FP1-5. All numeric keys, distractors and worked checks derive from SymPy matrices."""
import json
from pathlib import Path
from sympy import Matrix, eye

ROOT = Path(__file__).resolve().parents[3]
SUB = 'FP1-5'
NOTE = 'Subjects/Maths/FP1 Further Pure Mathematics 1/5 Matrix algebra integration.md'
K = {i: f'FP1-5.{i}' for i in range(1, 6)}
def mat(rows): return Matrix(rows)
def fmt(M):
    return r'\begin{pmatrix}' + r'\\'.join('&'.join(str(v) for v in M.row(i)) for i in range(M.rows)) + r'\end{pmatrix}'
def val(x): return {'value':float(x),'unit':'','exact':True}
def check(x): return {'kind':'numeric','answer':val(x)}
def det(A): return A.det()
def inv(A):
    assert det(A) != 0
    B=A.inv()
    assert A*B == eye(2) and B*A == eye(2)
    return B
def get(M,r,c): return M[r-1,c-1]
items=[]
def numeric(k,stem,answer,explanation,hints,difficulty=2,wrong=None,marks=2,word='Calculate'):
    idx=len(items)+1
    assert len(hints)==3
    ds=[{'value':float(v),'misconception':mid} for v,mid in (wrong or []) if v != answer]
    assert all(abs(d['value']-float(answer))>1e-10 for d in ds)
    items.append({'id':f'{SUB}-i{idx:02}', 'kcs':[K[k]], 'kind':'numeric','difficulty':difficulty,'command_word':word,'source':{'type':'generated'},'stem':stem,'marks':marks,'answer':val(answer),'explanation':explanation,'hints':hints,'distractors':ds})
def mcq(k,stem,options,answer,explanation,hints,difficulty=2,distractors=None):
    idx=len(items)+1
    assert sorted(options)==list('ABCD') and len(set(options.values()))==4
    items.append({'id':f'{SUB}-i{idx:02}','kcs':[K[k]],'kind':'mcq','difficulty':difficulty,'command_word':'State','source':{'type':'generated'},'stem':stem,'marks':1,'options':options,'answer':answer,'distractors':distractors or {},'shuffle':True,'explanation':explanation,'hints':hints})

# Addition and subtraction: dimensions and corresponding entries.
A=mat([[2,-3],[5,4]]); B=mat([[7,1],[-2,6]])
numeric(1,f'Calculate the $(1,2)$ entry of $A+B$, where $A={fmt(A)}$ and $B={fmt(B)}$.',get(A+B,1,2),'Add corresponding entries: $-3+1=-2$.',['Locate the first row and second column in each matrix.','Add entries in the same position.','Use the entries $-3$ and $1$.'],wrong=[(get(A-B,1,2),'m1')])
numeric(1,f'Calculate the $(2,1)$ entry of $A-B$, where $A={fmt(A)}$ and $B={fmt(B)}$.',get(A-B,2,1),'Subtract the corresponding entries: $5-(-2)=7$.',['Use row 2, column 1.','Subtract the entry of $B$ from the entry of $A$.','Pay attention to the negative entry in $B$.'],wrong=[(get(B-A,2,1),'m1')])
C=mat([[1,4,0],[-2,3,5]]); D=mat([[3,-1,6],[7,0,-4]])
numeric(1,f'Calculate the $(2,3)$ entry of $C+D$, where $C={fmt(C)}$ and $D={fmt(D)}$.',get(C+D,2,3),'Both matrices are $2\\times3$; the required entry is $5+(-4)=1$.',['Check that the dimensions agree.','Find row 2, column 3 in both matrices.','Add $5$ and $-4$.'])
numeric(1,f'Calculate the $(1,2)$ entry of $C-D$, where $C={fmt(C)}$ and $D={fmt(D)}$.',get(C-D,1,2),'Subtract entrywise: $4-(-1)=5$.',['Find the matching positions.','Keep the order $C-D$.','Subtract a negative number in row 1, column 2.'],wrong=[(get(D-C,1,2),'m1')])
mcq(1,'State which pair of matrix orders can be added.',{'A':'$2\\times3$ and $3\\times2$','B':'$2\\times3$ and $2\\times3$','C':'$2\\times3$ and $2\\times2$','D':'$2\\times3$ and $3\\times3$'},'B','Addition requires exactly the same number of rows and columns in both matrices.',['Think about matching entries.','Compare both dimensions, not just one.','Check rows and columns separately.'],distractors={'A':'m1','C':'m1','D':'m1'})
E=mat([[6,-4],[1,8]]);F=mat([[-3,7],[5,-2]])
numeric(1,f'Calculate the $(2,2)$ entry of $E-F+E$, where $E={fmt(E)}$ and $F={fmt(F)}$.',get(E-F+E,2,2),'Work entrywise: $8-(-2)+8=18$.',['Use the same entry from each occurrence of $E$.','Write the scalar calculation for row 2, column 2.','Account for subtracting the negative entry of $F$.'],4,wrong=[(get(E+F+E,2,2),'m1')],marks=3)

# Scalar multiplication.
A=mat([[2,-5],[0,3]])
numeric(2,f'Calculate the $(1,2)$ entry of $3A$, where $A={fmt(A)}$.',get(3*A,1,2),'Multiply each entry of $A$ by $3$: $3(-5)=-15$.',['Find the required entry of $A$.','Multiply that entry by the scalar.','Retain its sign.'],wrong=[(get(A,1,2)+3,'m2')])
numeric(2,f'Calculate the $(2,2)$ entry of $-2A$, where $A={fmt(A)}$.',get(-2*A,2,2),'The entry is $-2(3)=-6$.',['Locate row 2, column 2.','Apply the scalar to this entry.','A negative scalar reverses the sign.'],wrong=[(get(A,2,2)-2,'m2')])
B=mat([[4,1],[-3,2]])
numeric(2,f'Calculate the $(2,1)$ entry of $2A-3B$, where $A={fmt(A)}$ and $B={fmt(B)}$.',get(2*A-3*B,2,1),'The entry is $2(0)-3(-3)=9$.',['Select the matching entries.','Multiply each selected entry by its coefficient.','Subtract the second product.'],wrong=[(get(2*A+3*B,2,1),'m2')])
numeric(2,f'Calculate the $(1,1)$ entry of $-A+2B$, where $A={fmt(A)}$ and $B={fmt(B)}$.',get(-A+2*B,1,1),'The entry is $-(2)+2(4)=6$.',['Find the top-left entries.','Apply both scalar multipliers.','Add the resulting entries.'])
mcq(2,'State which expression equals $3(A+B)$ for matrices $A$ and $B$ of the same order.',{'A':'$3A+B$','B':'$A+3B$','C':'$3A+3B$','D':'$A+B+3$'},'C','Scalar multiplication distributes across matrix addition: each entry in both matrices is multiplied by $3$.',['Expand the brackets entry by entry.','The scalar multiplies both matrix terms.','Compare the coefficients of $A$ and $B$.'],distractors={'A':'m2','B':'m2'})
C=mat([[1,2,0],[-1,4,3]]);D=mat([[2,-3,5],[4,1,-2]])
numeric(2,f'Calculate the $(2,3)$ entry of $4C-2D$, where $C={fmt(C)}$ and $D={fmt(D)}$.',get(4*C-2*D,2,3),'The entry is $4(3)-2(-2)=16$.',['Check matching positions in both $2\\times3$ matrices.','Scale both entries separately.','Then subtract the second scaled entry.'],4,wrong=[(get(4*C+2*D,2,3),'m2')],marks=3)

# Matrix products.
A=mat([[2,1],[-1,3]]);B=mat([[4,-2],[5,1]])
numeric(3,f'Calculate the $(1,1)$ entry of $AB$, where $A={fmt(A)}$ and $B={fmt(B)}$.',get(A*B,1,1),'First row by first column gives $2(4)+1(5)=13$.',['Select row 1 of $A$.','Select column 1 of $B$.','Multiply corresponding components and add.'],wrong=[(get(A.multiply_elementwise(B),1,1),'m3')])
numeric(3,f'Calculate the $(1,2)$ entry of $AB$, where $A={fmt(A)}$ and $B={fmt(B)}$.',get(A*B,1,2),'First row by second column gives $2(-2)+1(1)=-3$.',['Use row 1 of the left matrix.','Use column 2 of the right matrix.','Add the two products.'],wrong=[(get(A.multiply_elementwise(B),1,2),'m3')])
numeric(3,f'Calculate the $(2,1)$ entry of $BA$, where $A={fmt(A)}$ and $B={fmt(B)}$.',get(B*A,2,1),'Second row of $B$ by first column of $A$ gives $5(2)+1(-1)=9$.',['Read the order $BA$ carefully.','Use row 2 of $B$ and column 1 of $A$.','Multiply and sum the paired entries.'],wrong=[(get(A*B,2,1),'m3')])
C=mat([[1,2,3],[4,0,-1]]);D=mat([[2,1],[-3,4],[5,-2]])
numeric(3,f'Calculate the $(2,2)$ entry of $CD$, where $C={fmt(C)}$ and $D={fmt(D)}$.',get(C*D,2,2),'Row 2 by column 2 gives $4(1)+0(4)+(-1)(-2)=6$.',['Check inner dimensions: $3$ and $3$.','Take row 2 of $C$ and column 2 of $D$.','Sum three pairwise products.'],4,marks=3)
mcq(3,'State the order of the product of a $2\\times3$ matrix and a $3\\times4$ matrix, in that order.',{'A':'$2\\times4$','B':'$3\\times3$','C':'$4\\times2$','D':'The product is undefined.'},'A','The inner dimensions match, so the product exists and has the outer dimensions $2\\times4$.',['Compare the inner dimensions.','If they match, use the outer dimensions.','Keep the order of the factors.'],distractors={'B':'m3','C':'m3','D':'m3'})
numeric(3,f'Calculate the $(1,2)$ entry of $A(BA)$, where $A={fmt(A)}$ and $B={fmt(B)}$.',get(A*(B*A),1,2),f'Associativity gives $A(BA)=(AB)A$; multiplying the appropriate row and column gives ${get(A*(B*A),1,2)}$.',['Multiply the inner pair first or use associativity.','Find the row and column for the requested final entry.','Keep the factor order while regrouping.'],5,marks=4)

# Determinants and singularity.
for j,rows in enumerate([[[3,2],[1,5]],[[2,-3],[4,1]],[[-1,4],[2,3]],[[0,7],[-2,5]]],start=1):
    A=mat(rows);d=det(A);wrong=A[0,0]*A[1,1]+A[0,1]*A[1,0]
    numeric(4,f'Calculate the determinant of $A={fmt(A)}$.',d,f'For a $2\\times2$ matrix, $\\det A=ad-bc=({A[0,0]})({A[1,1]})-({A[0,1]})({A[1,0]})={d}$.',['Label the entries $a,b,c,d$ in reading order.','Use $ad-bc$.','Subtract the off-diagonal product.'],2 if j<3 else 3,wrong=[(wrong,'m4')])
mcq(4,'State when a $2\\times2$ matrix is singular.',{'A':'When its determinant is $0$.','B':'When its determinant is $1$.','C':'When an entry is $0$.','D':'When its diagonal entries are equal.'},'A','A $2\\times2$ matrix is singular exactly when its determinant is zero; then it has no inverse.',['Recall the test for an inverse.','The determinant controls invertibility.','Identify the determinant value that makes division impossible.'],distractors={'B':'m4','C':'m4'})
A=mat([[2,3],[4,6]])
numeric(4,f'Calculate $\\det A$ and hence decide whether $A={fmt(A)}$ is singular. Enter the determinant.',det(A),'$2(6)-3(4)=0$, so $A$ is singular and has no inverse.',['Compute the two diagonal products.','Subtract the second from the first.','A zero determinant means singular.'],4,marks=3)

# Inverses and reversed product rule.
for rows,pos in [([[2,1],[3,2]],(1,1)),([[4,1],[2,1]],(1,2)),([[1,2],[3,5]],(2,1))]:
    A=mat(rows);B=inv(A);r,c=pos
    adj=mat([[A[1,1],-A[0,1]],[-A[1,0],A[0,0]]])
    assert B==adj/det(A)
    numeric(5,f'Calculate the $({r},{c})$ entry of $A^{{-1}}$ for $A={fmt(A)}$.',get(B,r,c),f'$\\det A={det(A)}$ and $A^{{-1}}=\\frac{{1}}{{\\det A}}{fmt(adj)}$, so the required entry is ${get(B,r,c)}$.',['Find the determinant first.','Swap diagonal entries and negate off-diagonal entries.','Divide the relevant adjugate entry by the determinant.'],3,wrong=[(get(adj,r,c) if det(A)!=1 else -get(adj,r,c),'m5')])
A=mat([[2,1],[1,1]]);B=mat([[1,2],[0,1]])
P=A*B;Pinv=inv(P);right=inv(B)*inv(A);assert Pinv==right
numeric(5,f'Calculate the $(1,2)$ entry of $(AB)^{{-1}}$, where $A={fmt(A)}$ and $B={fmt(B)}$.',get(Pinv,1,2),'Use $(AB)^{-1}=B^{-1}A^{-1}$; the required entry is $-5$.',['Both factors are invertible.','Reverse the factor order when inverting a product.','Multiply $B^{-1}$ by $A^{-1}$.'],4,wrong=[(get(inv(A)*inv(B),1,2),'m5')],marks=3)
mcq(5,'State the inverse of $AB$ when both square matrices are non-singular.',{'A':'$A^{-1}B^{-1}$','B':'$B^{-1}A^{-1}$','C':'$(A+B)^{-1}$','D':'$AB^{-1}$'},'B','$(AB)^{-1}=B^{-1}A^{-1}$ because $(AB)(B^{-1}A^{-1})=I$.',['Think of undoing two operations.','Undo the rightmost factor first.','Check which product cancels adjacent inverse pairs.'],distractors={'A':'m5','D':'m5'})
C=mat([[3,1],[2,1]]);Ci=inv(C)
numeric(5,f'Calculate the $(2,2)$ entry of $C^{{-1}}C$, where $C={fmt(C)}$.',get(Ci*C,2,2),'A non-singular matrix times its inverse is the identity matrix, whose $(2,2)$ entry is $1$.',['Check that $C$ is invertible.','Use the defining property of an inverse.','Read the requested entry of the identity matrix.'],4,marks=3)

mis=[
 ('m1',1,'Matrix subtraction or addition can be performed on mismatched positions or dimensions.','Only equal-sized matrices combine, entry by matching entry.','Check both dimensions; for subtraction keep the stated order.'),
 ('m2',2,'A scalar multiplies only one selected entry or one term in a matrix sum.','The scalar multiplies every entry, and distributes to both matrices in a sum.','Scale each whole matrix before combining entries.'),
 ('m3',3,'Matrix multiplication is entrywise or changing factor order has no effect.','Each product entry is a row-column dot product; generally $AB\\ne BA$.','Check inner dimensions and preserve factor order.'),
 ('m4',4,'A $2\\times2$ determinant is $ad+bc$, or any zero entry makes the matrix singular.','The determinant is $ad-bc$; singular means precisely $ad-bc=0$.','Calculate both diagonal products and subtract.'),
 ('m5',5,'The inverse of $AB$ is $A^{-1}B^{-1}$, or the adjugate needs no determinant divisor.','The product inverse reverses order, and $A^{-1}=\\operatorname{adj}(A)/\\det A$ for nonzero determinant.','Divide by the determinant and reverse factors in a product inverse.')]
misconceptions=[{'id':mid,'kc':K[k],'statement':s,'refutation':r,'contrast':c,'source':'research'} for mid,k,s,r,c in mis]

worked=[]
def work(k,problem,steps,faded_problem,faded_answer):
    worked.append({'id':f'we{k}','kc':K[k],'problem':problem,'steps':steps,'faded':{'id':f'we{k}f','problem':faded_problem,'answer':val(faded_answer),'blank_from':1}})
def step(do,why,x=None):
    z={'do':do,'why':why}
    if x is not None:z['check']=check(x)
    return z
A=mat([[1,-2],[3,4]]);B=mat([[5,6],[-1,2]]);R=A-B
work(1,f'Find $A-B$ for $A={fmt(A)}$ and $B={fmt(B)}$.',[step('Both matrices are $2\\times2$.','Equal dimensions are required for subtraction.'),step(f'Subtract corresponding entries: $A-B={fmt(R)}$.','Each output entry uses the same position in both matrices.',get(R,1,2))],f'Find the $(2,1)$ entry of $B-A$ for $A={fmt(A)}$, $B={fmt(B)}$.',get(B-A,2,1))
A=mat([[2,-1],[3,0]]);B=mat([[1,4],[-2,5]]);R=3*A-2*B
work(2,f'Find $3A-2B$ for $A={fmt(A)}$ and $B={fmt(B)}$.',[step(f'$3A={fmt(3*A)}$ and $2B={fmt(2*B)}$.','Each scalar multiplies every entry.'),step(f'$3A-2B={fmt(R)}$.','Subtract the scaled matrices entrywise.',get(R,1,2))],f'Find the $(1,2)$ entry of $2A+B$ for $A={fmt(A)}$, $B={fmt(B)}$.',get(2*A+B,1,2))
A=mat([[1,2],[3,-1]]);B=mat([[4,0],[-2,5]]);R=A*B
work(3,f'Find $AB$ for $A={fmt(A)}$ and $B={fmt(B)}$.',[step('The inner dimensions match: $(2\\times2)(2\\times2)$ gives a $2\\times2$ result.','A product requires matching inner dimensions.'),step(f'Take row-column dot products: $AB={fmt(R)}$.','Each output entry is the sum of paired products.',get(R,2,1))],f'Find the $(1,2)$ entry of $BA$ for $A={fmt(A)}$, $B={fmt(B)}$.',get(B*A,1,2))
A=mat([[4,3],[2,5]])
work(4,f'Calculate $\\det A$ and state whether $A={fmt(A)}$ is singular.',[step(f'$\\det A=4(5)-3(2)={det(A)}$.','Use $ad-bc$, with the off-diagonal product subtracted.',det(A)),step('Because $\\det A\\ne0$, $A$ is non-singular.','A nonzero determinant is equivalent to having an inverse.')],f'Calculate the determinant of $A={fmt(mat([[3,6],[1,2]]))}$.',det(mat([[3,6],[1,2]])))
A=mat([[2,1],[1,1]]);B=mat([[1,2],[0,1]]);R=inv(B)*inv(A)
work(5,f'Find $(AB)^{{-1}}$ for $A={fmt(A)}$ and $B={fmt(B)}$.',[step(f'$\\det A={det(A)}$ and $\\det B={det(B)}$; both inverses exist.','The inverse formula requires nonzero determinants.'),step(f'$A^{{-1}}={fmt(inv(A))}$ and $B^{{-1}}={fmt(inv(B))}$.','Swap the diagonal entries, negate the off-diagonal entries and divide by the determinant.'),step(f'$(AB)^{{-1}}=B^{{-1}}A^{{-1}}={fmt(R)}$.','Inverting a product reverses the factor order.',get(R,1,2)),step('Check $(AB)(B^{-1}A^{-1})=I$.','Adjacent inverse pairs cancel in the correct order.')],f'Find the $(1,1)$ entry of $A^{{-1}}$ for $A={fmt(mat([[3,1],[2,1]]))}$.',get(inv(mat([[3,1],[2,1]])),1,1))
pack={'subtopic':SUB,'spec':'FP1','version':1,'note':NOTE,'outline':'Add and subtract matrices of equal order entrywise, and multiply every entry when scaling by a scalar. For products, match the inner dimensions and form each entry by a row-column dot product; in general $AB\\ne BA$. A $2\\times2$ determinant is $ad-bc$: zero means singular. A non-singular matrix has inverse $\\frac1{ad-bc}\\begin{pmatrix}d&-b\\-c&a\\end{pmatrix}$. For invertible products, $(AB)^{-1}=B^{-1}A^{-1}$.','misconceptions':misconceptions,'worked':worked,'items':items,'flashcards':[],'diagrams':[]}
assert len(items)==30 and len(worked)==5
for w in worked:
    assert w['faded']['answer']['value']==float(w['faded']['answer']['value'])
out=ROOT/'build/out/packs/FP1/FP1-5.json'
out.parent.mkdir(parents=True,exist_ok=True)
out.write_text(json.dumps(pack,ensure_ascii=False,indent=1))
print(f'Wrote {out}: {len(items)} items, {len(worked)} worked examples')
