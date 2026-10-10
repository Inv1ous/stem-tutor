---
tags: [stem-tutor/lesson, edexcel-fp1]
spec: "FP1"
subtopic: "FP1-6"
kcs: ["FP1-6.1", "FP1-6.2", "FP1-6.3", "FP1-6.4"]
---
# 6 Transformations using matrices
> [!abstract] In one breath
> A $2\times2$ matrix transforms a two-dimensional column vector by multiplication. Matrix order tells you the order of successive transformations, and the determinant tells you whether the action can be undone and how it scales area.

## Key ideas
A **linear transformation** $T$ satisfies $T(u+v)=T(u)+T(v)$ and $T(cu)=cT(u)$. In two dimensions, its matrix $A$ gives $T(v)=Av$. The columns of $A$ are the images of the standard basis vectors $(1,0)^T$ and $(0,1)^T$, in that order. Thus knowing those two images determines the whole matrix. Every matrix transformation in this chapter fixes the origin.

For reflections, remember what happens to a general point $(x,y)$: in the $x$-axis it becomes $(x,-y)$, in the $y$-axis $(-x,y)$, in $y=x$ it becomes $(y,x)$, and in $y=-x$ it becomes $(-y,-x)$. The respective matrices are
$$
\begin{pmatrix}1&0\\0&-1\end{pmatrix},\quad
\begin{pmatrix}-1&0\\0&1\end{pmatrix},\quad
\begin{pmatrix}0&1\\1&0\end{pmatrix},\quad
\begin{pmatrix}0&-1\\-1&0\end{pmatrix}.
$$
An anticlockwise rotation through angle $\theta$ about $(0,0)$ has matrix $\begin{pmatrix}\cos\theta&-\sin\theta\\\sin\theta&\cos\theta\end{pmatrix}$. A clockwise turn uses a negative angle. At $90^\circ$ anticlockwise, $(1,0)^T$ becomes $(0,1)^T$, a useful sign check.

A stretch parallel to the $x$-axis by factor $a$ has matrix $\begin{pmatrix}a&0\\0&1\end{pmatrix}$; parallel to the $y$-axis by factor $b$, use $\begin{pmatrix}1&0\\0&b\end{pmatrix}$. An enlargement about $(0,0)$ by real nonzero scale factor $k$ is $kI=\begin{pmatrix}k&0\\0&k\end{pmatrix}$. A negative $k$ puts the image on the opposite side of the origin.

## Method
1. Write each single-transformation matrix and test it on a simple vector.
2. For a combination, write the matrices in reverse order of action: the matrix $AB$ means $B$ followed by $A$, since $ABv=A(Bv)$. Matrix products generally cannot be reordered.
3. Multiply the matrices before applying the result to a column vector. To reverse a combination, check its determinant first. If nonzero, use $(AB)^{-1}=B^{-1}A^{-1}$, reversing both actions and factor order.
4. For $A=\begin{pmatrix}a&b\\c&d\end{pmatrix}$, calculate $\det A=ad-bc$. The area scale factor is $|\det A|$. A negative determinant reverses orientation. If $\det A=0$, areas collapse to zero and no inverse exists; otherwise $A^{-1}=\frac{1}{ad-bc}\begin{pmatrix}d&-b\\-c&a\end{pmatrix}$.

> [!example]- Worked example
> A stretch parallel to the $x$-axis by $3$ is followed by an anticlockwise $90^\circ$ rotation. Find the combined matrix and the image of $(1,2)^T$.
> Let $S=\begin{pmatrix}3&0\\0&1\end{pmatrix}$ and $R=\begin{pmatrix}0&-1\\1&0\end{pmatrix}$. The stretch acts first, so the combined matrix is
> $$
> RS=\begin{pmatrix}0&-1\\3&0\end{pmatrix}.
> $$
> Therefore $RS\begin{pmatrix}1\\2\end{pmatrix}=\begin{pmatrix}-2\\3\end{pmatrix}$. Its determinant is $3$, so areas triple and an inverse exists. To undo the combination, apply $R^{-1}$ first and then $S^{-1}$, giving $(RS)^{-1}=S^{-1}R^{-1}$.

## Traps
- **Trap:** Put basis images in rows. **Why it's wrong:** multiplying by $(1,0)^T$ selects the first column. **Instead:** place the images in columns in standard-basis order.
- **Trap:** Write $SR$ for a stretch followed by rotation. **Why it's wrong:** the rightmost factor acts first. **Instead:** write $RS$ and check on a vector.
- **Trap:** Use the signed determinant as a negative area scale. **Why it's wrong:** area is nonnegative. **Instead:** take $|\det A|$ and discuss orientation separately.

## Exam technique
For **Find** or **Calculate**, show the component matrices, their product in the correct order, and the requested image or inverse. For **Explain**, connect a zero determinant to collapsed area and loss of invertibility. Check a rotation by applying it to $(1,0)^T$ and check an inverse by multiplying to get $I$.

## Links
Builds on [[5 Matrix algebra integration]] · Leads to later coordinate geometry and linear algebra.
