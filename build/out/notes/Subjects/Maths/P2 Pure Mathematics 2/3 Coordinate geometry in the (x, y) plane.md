---
tags: [stem-tutor/lesson, P2]
spec: "P2"
subtopic: "P2-3"
kcs: ["P2-3.1"]
---
# 3 Coordinate geometry in the $(x,y)$ plane
> [!abstract] In one breath
> The equation of a circle records every point at a fixed distance from its centre. Three geometric facts about diameters, chords and tangents turn circle questions into coordinate calculations.

## Key ideas
A circle with centre $(a,b)$ and positive radius $r$ has equation
$$
(x-a)^2+(y-b)^2=r^2.
$$
This is the distance formula: every point $(x,y)$ on the circle is distance $r$ from $(a,b)$. To read the centre, identify the numbers that make each bracket zero. For example, $(x-3)^2+(y+2)^2=25$ has centre $(3,-2)$ and radius $\sqrt{25}=5$. The right-hand side is the **square** of the radius. To write an equation from a centre and radius, substitute them into the same form. A point lies on the circle exactly when its coordinates satisfy the equation.

Three circle properties are useful in coordinate geometry. An angle at the circumference subtended by a **diameter** is a right angle: this is the angle-in-a-semicircle property. A perpendicular drawn from the centre to a chord bisects that chord. At a point of contact, the tangent is perpendicular to the radius drawn to that point. Each property has a coordinate version: perpendicular lines have gradients whose product is $-1$ when both gradients exist, and the midpoint of a chord with endpoints $(x_1,y_1)$ and $(x_2,y_2)$ is $((x_1+x_2)/2,(y_1+y_2)/2)$. A horizontal radius has a vertical tangent, so the gradient rule is not needed in that case.

## Method
1. **Read or build the circle equation.** Put it into $(x-a)^2+(y-b)^2=r^2$ form. State the centre and take the positive square root to obtain the radius. If the centre and a point on the circle are given, calculate $r^2$ as the sum of squared coordinate differences.
2. **Check membership.** Substitute a proposed point into the circle equation. Equality means it lies on the circumference.
3. **Choose the geometric property.** For a diameter, identify the right angle at the circumference. For a chord, find its midpoint if the line from the centre is perpendicular. For a tangent, find the radius gradient and then its negative reciprocal.
4. **Write the required line.** Use the known point and gradient in $y-y_1=m(x-x_1)$; treat horizontal and vertical lines separately.

> [!example]- Worked example
> Find the tangent at $(6,2)$ to $(x-3)^2+(y+2)^2=25$.
> The centre is $(3,-2)$ and radius $5$. First verify the point: $(6-3)^2+(2+2)^2=9+16=25$.
> The radius from $(3,-2)$ to $(6,2)$ has gradient $4/3$. The tangent gradient is $-3/4$ because radius and tangent are perpendicular.
> Through $(6,2)$, the tangent is $y-2=-\frac34(x-6)$.

## Traps
- **Trap:** Read the centre as $(-3,2)$ from $(x-3)^2+(y+2)^2$. **Why it's wrong:** The brackets vanish at $(3,-2)$. **Instead:** Set each bracket to zero.
- **Trap:** Call $25$ the radius. **Why it's wrong:** The equation contains $r^2$. **Instead:** Take the positive square root.
- **Trap:** Give the tangent the same gradient as the radius. **Why it's wrong:** The two lines are perpendicular. **Instead:** Use the negative reciprocal, or identify a horizontal–vertical pair.
- **Trap:** Use an endpoint of a chord as the foot of the centre's perpendicular. **Why it's wrong:** That perpendicular bisects the chord. **Instead:** Calculate its midpoint.

## Exam technique
For **Show that**, substitute the proposed point or expand the claimed equation and show every equality. For **Find** or **Calculate**, name the circle property you use before applying midpoint or gradient arithmetic. For **Explain** and **Prove**, give the reason that an angle is right or two lines are perpendicular; a sketch alone does not establish the result. Keep exact fractions for gradients and exact surds for radii when requested.

## Links
Builds on [[2 Parallel and perpendicular lines]] · Leads to tangent and chord problems in coordinate geometry.
