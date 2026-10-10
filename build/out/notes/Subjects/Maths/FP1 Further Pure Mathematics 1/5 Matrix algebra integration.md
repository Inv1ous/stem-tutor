---
tags: [stem-tutor/lesson, edexcel-fp1]
spec: "FP1"
subtopic: "FP1-5"
kcs: ["FP1-5.1", "FP1-5.2", "FP1-5.3", "FP1-5.4", "FP1-5.5"]
---
# 5 Matrix algebra integration
> [!abstract] In one breath
> Matrix addition, subtraction and scalar multiplication work entry by entry. Products use rows against columns, while the determinant tells you whether a $2\times2$ matrix can be inverted.

## Key ideas
A matrix is a rectangular array with an **order**: rows by columns. Matrices are **conformable for addition or subtraction** only if they have the same order. Add or subtract entries in corresponding positions. For example, the top-right entry of $A-B$ is $a_{12}-b_{12}$, never $b_{12}-a_{12}$ unless the question asks for $B-A$.

**Scalar multiplication** applies to every entry: if $A=\begin{pmatrix}a&b\\c&d\end{pmatrix}$, then $kA=\begin{pmatrix}ka&kb\\kc&kd\end{pmatrix}$. It distributes over matrix addition: $k(A+B)=kA+kB$. This lets you simplify linear combinations such as $2A-3B$ by scaling both matrices first, then subtracting corresponding entries.

For a **matrix product** $AB$, the number of columns of $A$ must equal the number of rows of $B$. Thus a $2\times3$ matrix times a $3\times4$ matrix gives a $2\times4$ matrix. To obtain entry $(i,j)$, multiply row $i$ of $A$ by column $j$ of $B$ and add the products. Matrix multiplication is generally not commutative: $AB$ and $BA$ may differ, and one may not even exist. You may regroup compatible products because multiplication is associative: $(AB)C=A(BC)$.

For $A=\begin{pmatrix}a&b\\c&d\end{pmatrix}$, its **determinant** is $\det A=ad-bc$. A matrix is **singular** if its determinant is zero, and **non-singular** if its determinant is nonzero. Only a non-singular matrix has an inverse. When $ad-bc\ne0$,

$$
A^{-1}=\frac{1}{ad-bc}\begin{pmatrix}d&-b\\-c&a\end{pmatrix},\qquad AA^{-1}=A^{-1}A=I.
$$

For two invertible matrices, $(AB)^{-1}=B^{-1}A^{-1}$. The order reverses because $AB(B^{-1}A^{-1})=A(BB^{-1})A^{-1}=I$.

## Method
1. Before adding or subtracting, check that the orders match. Before multiplying, check the inner dimensions; write down the outer dimensions of the result.
2. For addition, subtraction or scalar multiplication, work at matching positions. For a product, take each required row-column dot product and preserve the factor order.
3. For a $2\times2$ inverse, calculate $ad-bc$ first. If it is zero, state that no inverse exists. Otherwise swap $a,d$, negate $b,c$, and divide the whole matrix by the determinant.
4. If the expression is $(AB)^{-1}$, invert the factors and reverse their order. Multiply back to the identity if asked to verify.

> [!example]- Worked example
> Let $A=\begin{pmatrix}2&1\\1&1\end{pmatrix}$ and $B=\begin{pmatrix}1&2\\0&1\end{pmatrix}$. Find $(AB)^{-1}$.
> Both determinants are $1$, so each inverse exists.
> $A^{-1}=\begin{pmatrix}1&-1\\-1&2\end{pmatrix}$ and $B^{-1}=\begin{pmatrix}1&-2\\0&1\end{pmatrix}$.
> Reverse the order: $(AB)^{-1}=B^{-1}A^{-1}=\begin{pmatrix}3&-5\\-1&2\end{pmatrix}$.
> Check: $AB=\begin{pmatrix}2&5\\1&3\end{pmatrix}$, and multiplying it by the proposed inverse gives $I$.

## Traps
- **Trap:** Adding matrices with different orders. **Why it's wrong:** Corresponding positions cannot all be paired. **Instead:** Check both row and column counts first.
- **Trap:** Multiplying matrices entrywise, or assuming $AB=BA$. **Why it's wrong:** Products are built from row-column dot products and factor order matters. **Instead:** Check inner dimensions and keep the written order.
- **Trap:** Using $ad+bc$ or inverting a singular matrix. **Why it's wrong:** The determinant is $ad-bc$, and zero would cause division by zero. **Instead:** Calculate the determinant before applying the inverse formula.
- **Trap:** Writing $(AB)^{-1}=A^{-1}B^{-1}$. **Why it's wrong:** The adjacent factors will not generally cancel. **Instead:** Reverse the order to $B^{-1}A^{-1}$.

## Exam technique
For **Calculate** or **Find**, show the row-column products or the determinant substitution before the answer. For **Show that** or **Verify**, multiply the claimed inverse by the original matrix and display the identity. For **Hence**, use the result just obtained, especially a determinant or an inverse, rather than restarting the calculation. State clearly when a matrix is singular and why no inverse exists.

## Links
Builds on arithmetic and algebraic manipulation · Leads to matrix transformations and solving simultaneous equations with inverses.
