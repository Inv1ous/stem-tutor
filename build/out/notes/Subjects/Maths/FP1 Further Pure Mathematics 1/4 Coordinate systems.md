---
tags: [stem-tutor/lesson, edexcel-fp1]
spec: "FP1"
subtopic: "FP1-4"
kcs: ["FP1-4.1", "FP1-4.2", "FP1-4.3", "FP1-4.4"]
---
# 4 Coordinate systems
> [!abstract] In one breath
> The standard parabola and rectangular hyperbola have both Cartesian and parametric descriptions. Their points can be described by a parameter, while their tangents and normals come from ordinary implicit differentiation.

## Key ideas
The **parabola** in standard position has Cartesian equation $y^2=4ax$, where $a\ne0$. When $a>0$, it opens to the right; when $a<0$, it opens to the left. Its vertex is $(0,0)$ and its axis is the $x$-axis. The parameter equations $x=at^2$ and $y=2at$ give the **general point** $(at^2,2at)$. Squaring the second equation gives $y^2=4a^2t^2=4ax$, so every such point lies on the parabola. Conversely, $t=y/(2a)$ describes every point of the curve.

The **rectangular hyperbola** has $xy=c^2$, with $c\ne0$. Its parameter equations are $x=ct$, $y=c/t$, where $t\ne0$. Their product is $c^2$. Since $c^2>0$, its two branches lie in quadrants I and III. Neither axis is crossed: $x=0$ and $y=0$ are asymptotes. Negative $t$ reaches the quadrant III branch when $c>0$. A sketch should show both branches approaching, but never meeting, their asymptotes.

A **parabola** is the locus of points equidistant from a fixed **focus** and a fixed **directrix**. For $y^2=4ax$, the focus is $(a,0)$ and the directrix is $x=-a$. For a point $(x,y)$, the squared distance to the focus is $(x-a)^2+y^2$. The squared perpendicular distance to the directrix is $(x+a)^2$. Equating them and cancelling common terms gives $y^2=4ax$. This explains why the vertex is midway between the focus and directrix.

## Method
1. To find a point from a parameter, substitute the given $t$ into both coordinate formulas. To recover $t$ on a parabola, use $t=y/(2a)$ and check $x=at^2$.
2. For a tangent, differentiate the Cartesian equation implicitly. From $y^2=4ax$, obtain $2y\,dy/dx=4a$, hence $dy/dx=2a/y$ when $y\ne0$. From $xy=c^2$, the product rule gives $y+x\,dy/dx=0$, hence $dy/dx=-y/x=-c^2/x^2$.
3. Evaluate the gradient at the given point and use $y-y_1=m(x-x_1)$ for the tangent. For a finite, nonzero tangent gradient $m$, the normal gradient is $-1/m$. At the parabola's vertex, the tangent is vertical, $x=0$, and the normal is horizontal, $y=0$.

> [!example]- Worked example
> Find the tangent and normal to $xy=9$ at $(3,3)$.
> Differentiating gives $y+x\,dy/dx=0$, so $dy/dx=-y/x=-1$ at $(3,3)$.
> The tangent is $y-3=-(x-3)$, or $y=-x+6$.
> Its perpendicular normal has gradient $1$, so $y-3=x-3$, or $y=x$.
> Both lines pass through $(3,3)$, which also satisfies $xy=9$.


![[Assets/FP1/FP1-4-hyperbola.svg]]
The two branches of $y=9/x$ approach the coordinate axes as asymptotes. At the marked point $(3,3)$, the tangent gradient is $-1$ and the normal gradient is $1$, as in the example above.

> [!example]- Worked example: normal at a general parabola point
> Find the normal to $y^2=4ax$ at $P=(at^2,2at)$, where $a\ne0$ and $t\ne0$.
> Differentiate the Cartesian equation: $2y\,dy/dx=4a$, so $dy/dx=2a/y$.
> At $P$, the tangent gradient is $2a/(2at)=1/t$, hence the normal gradient is $-t$.
> Point-gradient form gives $y-2at=-t(x-at^2)$, or $y+tx=at^3+2at$.
> This works for negative $t$ too: use the signed $y$ coordinate rather than assuming the positive square-root branch.
> At $t=0$, division by $t$ is invalid. The vertex tangent is $x=0$ and its normal is $y=0$.

> [!example]- Complete the method
> For $y^2=8x$ and $t=-1$, start with $2y\,dy/dx=8$. Find the point, the normal gradient and the normal equation.

> [!success]- Faded example answer
> Here $a=2$, so the point is $(2,-4)$. The tangent gradient is $-1$, the normal gradient is $1$, and $y+4=x-2$, giving $y=x-6$.

*Method reference: sources/library/SaveMyExams/YFM01 further-pure-1/YFM01 c4.1.pdf, pp.10–11; example and practice written afresh.*
The signed-branch treatment uses implicit differentiation, as illustrated for a lower-branch parabola point in [Wai Yan Pong, Calculus Single Variable, §1.2.2](https://math.csudh.edu/~pong/calc/compute_der.html).

## Traps
- **Trap:** Sketch $y^2=4ax$ as an upward-opening curve. **Why it's wrong:** Squaring $y$ gives symmetry above and below the $x$-axis. **Instead:** Check the sign of $a$ to decide whether it opens right or left.
- **Trap:** Put the directrix at $x=a$. **Why it's wrong:** That is the focus's $x$ coordinate. **Instead:** Put the directrix at $x=-a$, opposite the focus across the vertex.
- **Trap:** Use the tangent gradient for the normal. **Why it's wrong:** The two lines are perpendicular. **Instead:** Take the negative reciprocal, with special care for horizontal or vertical tangents.

## Exam technique
For **Show that**, begin with the focus and directrix distances or the two parameter equations and display the algebra leading to the given result. For **Find** and **Calculate**, show the differentiation, substitution and point-gradient line equation. For **Sketch**, label the parabola's vertex and axis or the hyperbola's two asymptotes and branches. Keep equations and gradients exact where the question asks for an **Exact** answer.

## Links
Builds on [[P1 Sketching curves]] and [[P1 Equations of straight lines]] · Leads to [[FP1 Further coordinate geometry]]

Builds on [[1 Algebra and functions]] · [[2 Coordinate geometry in the (x, y) plane]] · [[4 Differentiation]]
Leads to [[2 Further coordinate systems]]
