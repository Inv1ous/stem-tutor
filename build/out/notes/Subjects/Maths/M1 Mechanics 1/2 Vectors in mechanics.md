---
tags: [stem-tutor/lesson, edexcel-ial-m1]
spec: "M1"
subtopic: "M1-2"
kcs: ["M1-2.1", "M1-2.2"]
---
# 2 Vectors in mechanics
> [!abstract] In one breath
> A vector has magnitude and direction. Write vectors in perpendicular components, combine those components to find a resultant, and use changes in displacement or velocity to calculate velocity or acceleration.

## Key ideas
A **scalar** has magnitude only; a **vector** has magnitude and direction. In a horizontal–vertical plane, $\mathbf{i}$ is a unit vector to the right and $\mathbf{j}$ is a unit vector upwards. Thus $3\mathbf{i}-4\mathbf{j}$ means three units right and four down. The signs carry the direction; do not discard them while adding vectors.

For $\mathbf{v}=x\mathbf{i}+y\mathbf{j}$, its magnitude is $|\mathbf{v}|=\sqrt{x^2+y^2}$. Its direction must be stated relative to a named axis, with a sense of rotation. The reference angle satisfies $\tan\alpha=|y/x|$ when $x\ne0$, but the signs of $x$ and $y$ determine the quadrant. For instance, $-6\mathbf{i}+8\mathbf{j}$ points into quadrant II; its direction is about $127^\circ$ anticlockwise from positive $\mathbf{i}$, rather than $53.1^\circ$.

To **resolve** a vector of magnitude $V$ at angle $\theta$ above the positive horizontal, use $V\cos\theta$ horizontally and $V\sin\theta$ vertically. The horizontal side is adjacent to the stated angle. If the angle is measured from the vertical, the roles of sine and cosine switch. A vector diagram shows this right triangle and the direction of each component.

The **resultant vector** is the single vector equivalent to two or more vectors together. Add signed components: $(a\mathbf{i}+b\mathbf{j})+(c\mathbf{i}+d\mathbf{j})=(a+c)\mathbf{i}+(b+d)\mathbf{j}$. Displacements, velocities, accelerations and forces in a plane all combine by this rule, provided the quantities being added have the same units.

## Method
1. Choose positive horizontal and vertical directions, and write every vector using $\mathbf{i}$ and $\mathbf{j}$.
2. Resolve angled vectors into signed components. Add components to obtain a resultant; calculate its magnitude only after this addition.
3. At constant velocity, use $\mathbf{v}=\Delta\mathbf{r}/\Delta t=(\mathbf{r}_2-\mathbf{r}_1)/\Delta t$. The displacement change has units m, and velocity has units $\mathrm{m\,s^{-1}}$.
4. At constant acceleration, use $\mathbf{a}=\Delta\mathbf{v}/\Delta t=(\mathbf{v}_2-\mathbf{v}_1)/\Delta t$. Acceleration has units $\mathrm{m\,s^{-2}}$; a change in direction counts as a change in velocity even if speed stays constant.

> [!example]- Worked example
> A particle moves at constant velocity from $2\mathbf{i}-3\mathbf{j}$ m to $8\mathbf{i}+9\mathbf{j}$ m in 3 s. Find its velocity and speed.
> First subtract the initial position from the final position:
> $$\Delta\mathbf{r}=(8-2)\mathbf{i}+[9-(-3)]\mathbf{j}=6\mathbf{i}+12\mathbf{j}\ \mathrm{m}.$$
> Divide by elapsed time: $\mathbf{v}=(2\mathbf{i}+4\mathbf{j})\,\mathrm{m\,s^{-1}}$.
> Speed is the magnitude: $|\mathbf{v}|=\sqrt{2^2+4^2}=\sqrt{20}\,\mathrm{m\,s^{-1}}\approx4.47\,\mathrm{m\,s^{-1}}$.

## Traps
- **Trap:** Add vector magnitudes to get the resultant magnitude. **Why it's wrong:** Vectors can oppose or meet at an angle. **Instead:** Add signed components first, then use Pythagoras.
- **Trap:** Divide the final position by time to find velocity. **Why it's wrong:** The initial position might not be zero. **Instead:** Subtract initial position before dividing by elapsed time.
- **Trap:** Use change in speed for acceleration. **Why it's wrong:** Velocity includes direction. **Instead:** Subtract the velocity vectors component by component.
- **Trap:** Report only an acute angle. **Why it's wrong:** It may put the vector in the wrong quadrant. **Instead:** State the axis, rotation sense and quadrant.

## Exam technique
For **Find** or **Calculate**, show the vector equation, the component substitution and the answer with units. If asked to **Show that**, include every algebraic step leading to the given result. For a force, label components and the resultant in N. For velocity and acceleration, keep the time interval with its unit; round a decimal only at the end. A quick vector diagram can expose a sign error before you calculate.

## Links
Builds on [[1 Mathematical models in mechanics]] · Leads to [[3 Motion in a straight line]]
