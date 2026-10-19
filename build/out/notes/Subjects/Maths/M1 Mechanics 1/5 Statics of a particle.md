---
tags: [stem-tutor/lesson, edexcel-m1]
spec: "M1"
subtopic: "M1-5"
kcs: ["M1-5.1", "M1-5.2", "M1-5.3"]
---
# 5 Statics of a particle
> [!abstract] In one breath
> A particle is in equilibrium when the vector sum of all forces acting on it is zero. Resolve forces along two perpendicular axes, then use the two zero-sum equations; for static friction, use $F\leq\mu R$.

## Key ideas
A **force as a vector** has a magnitude and a direction. To **resolve a force** means to replace it with components whose vector sum is the original force. If a force $P$ acts at angle $\theta$ above the horizontal, its rightward component is $P\cos\theta$ and its upward component is $P\sin\theta$. State the axes and directions before using signs. For a downward force or a force pointing left, the corresponding signed component is negative.

A particle in **equilibrium** has zero resultant force. For **coplanar forces**, resolving in any two perpendicular directions gives $\sum F_x=0$ and $\sum F_y=0$. These two equations must both hold. Equilibrium does not mean that each force is zero: nonzero forces balance one another.

**Weight** is $mg$ vertically downward, using $g=9.8\,\mathrm{m\,s^{-2}}$. A **normal reaction** $R$ acts perpendicular to a contact surface. **Tension** pulls along a taut string; **thrust** pushes along a strut or contact direction. **Friction** lies along the contact surface and opposes actual or impending relative motion. On a horizontal surface without another vertical force, $R=mg$. If an upward pull has a vertical component, that component reduces $R$. On a slope, resolve the weight along and perpendicular to the plane: the components are $mg\sin\theta$ down the plane and $mg\cos\theta$ into the plane.

The **coefficient of friction** $\mu$ sets the maximum available static friction. In equilibrium, $F\leq\mu R$. The actual friction $F$ is what the force balance requires. At **limiting equilibrium**, the particle is just about to slip, so $F=\mu R$. If the force needed for balance exceeds $\mu R$, equilibrium is impossible.

## Method
1. Isolate the particle. Draw every force acting **on it**, with its direction: weight, reaction, tension or thrust, applied forces and friction where appropriate.
2. Choose convenient perpendicular axes. On a slope, take one axis along the plane and one normal to it. Resolve angled forces with sine and cosine relative to the stated angle.
3. Write a zero-resultant equation on each axis. Solve these equations for the unknown forces.
4. For rough contact, first find $R$, then find the friction needed for equilibrium. Check $F\leq\mu R$; use equality only when the question says the particle is on the point of moving or asks for a maximum or minimum threshold.

> [!example]- Worked example
> A $3\,\mathrm{kg}$ particle rests on a smooth plane inclined at $30^\circ$, held by a string parallel to the plane. Find the tension and reaction.
> Along the plane, $T-3g\sin30^\circ=0$, so $T=14.7\,\mathrm{N}$.
> Perpendicular to the plane, $R-3g\cos30^\circ=0$, so $R\approx25.5\,\mathrm{N}$ to three significant figures.
> Check the directions: tension acts uphill; reaction acts out of the plane. Their components balance weight, so the resultant is zero.

## Traps
- **Trap:** Using $\sin\theta$ for every horizontal component. **Why it's wrong:** the angle may be measured from the horizontal, making the horizontal component adjacent. **Instead:** draw the component triangle and label the given angle.
- **Trap:** Writing $R=mg$ automatically. **Why it's wrong:** contact angle and other vertical forces change the perpendicular balance. **Instead:** resolve normal to the surface.
- **Trap:** Writing $F=\mu R$ whenever a particle rests. **Why it's wrong:** static friction may be smaller than its maximum. **Instead:** find the required $F$ from equilibrium, then check the inequality.

## Exam technique
For **Calculate** and **Find**, show the force equations before substituting numbers. For **Explain**, state why friction points in its chosen direction and why equality with $\mu R$ does or does not apply. Give numerical answers to two or three significant figures after using $g=9.8$.

## Links
Builds on [[2 Vectors]] and [[4 Dynamics of a particle moving in a straight line or plane]].
