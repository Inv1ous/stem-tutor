---
tags: [stem-tutor/lesson, P1]
spec: "P1"
subtopic: "P1-3"
kcs: ["P1-3.1", "P1-3.2", "P1-3.3"]
---
# 3 Trigonometry
> [!abstract] In one breath
> Triangle rules connect sides and angles without a right angle. Radians make circle geometry simple, while periodic graphs show how trigonometric values repeat.

## Key ideas

For a triangle with sides $a,b,c$ opposite angles $A,B,C$, the **sine rule** is $a/\sin A=b/\sin B=c/\sin C$. The **cosine rule** is $c^2=a^2+b^2-2ab\cos C$; rearrange it to find an angle when all three sides are known. The **area of a triangle** formed by sides $a,b$ and their included angle $C$ is $\frac12ab\sin C$. The angle must be between the named sides.

The sine rule has an **ambiguous case** when two sides and a non-included angle are given. Since $\sin B=\sin(180^\circ-B)$, an inverse sine result can give two triangles, one triangle or no triangle. Check that each candidate leaves a positive third angle and fits the side lengths. A calculator's inverse sine only displays its principal angle.

One **radian** is the central angle subtended by an arc whose length equals the radius. A full turn is $2\pi$ radians, so $180^\circ=\pi$ radians. For an angle $\theta$ in radians, **arc length** is $s=r\theta$ and **area of a sector** is $A=\frac12r^2\theta$. These formulas require radians; convert degrees first. Both formulas scale directly with the fraction of a full circle.

The **sine graph** starts at $(0,0)$ and rises; the **cosine graph** starts at $(0,1)$. Both have amplitude 1, range $[-1,1]$ and period $2\pi$. Sine is odd, $\sin(-x)=-\sin x$; cosine is even, $\cos(-x)=\cos x$. The **tangent graph** passes through the origin, has period $\pi$, and has vertical asymptotes at $x=\pi/2+k\pi$ for integer $k$. Tangent is also odd.

In $y=a\sin(bx+c)$, amplitude is $|a|$ and period is $2\pi/|b|$. A positive $c$ shifts the graph left by $c/b$ when $b>0$. Thus $y=3\sin x$ has amplitude 3; $y=\sin(x+\pi/6)$ is shifted left $\pi/6$; and $y=\sin2x$ has period $\pi$. Read horizontal changes from the whole argument, not from the isolated constant.

## Method

1. Draw and label a triangle. Pair each known side with its opposite angle. Choose the sine rule when an opposite pair is known, the cosine rule for two sides and their included angle or all three sides, and $\frac12ab\sin C$ for area.
2. For sine-rule angles, calculate the principal angle, test its supplement, and reject any impossible angle sum.
3. In circle questions, convert degrees using $\theta_{\mathrm{rad}}=\theta_{\mathrm{deg}}\pi/180$, then insert the radian angle in $s=r\theta$ or $A=\frac12r^2\theta$.
4. For graph sketches, mark intercepts, peaks or troughs, period, and any tangent asymptotes before drawing the curve.

> [!example]- Worked example
> A triangle has $a=5$, $b=7$ and included angle $C=60^\circ$. Find $c$ and the area.
> Use the cosine rule: $c^2=5^2+7^2-2(5)(7)\cos60^\circ=39$, so $c=\sqrt{39}$.
> Use the included angle for area: $\frac12(5)(7)\sin60^\circ=35\sqrt3/4$.
> Both answers are exact; rounding early would lose exactness.

## Traps

- **Trap:** Keep only the calculator's inverse sine angle. **Why it's wrong:** Sine has the same value for supplementary angles. **Instead:** Test both against the angle sum.
- **Trap:** Put $60$ into $s=r\theta$. **Why it's wrong:** The formula assumes radians. **Instead:** Use $\pi/3$.
- **Trap:** Give $y=\sin2x$ amplitude 2. **Why it's wrong:** The 2 changes horizontal scale. **Instead:** Give amplitude 1 and period $\pi$.

## Exam technique

For **Find** and **Calculate**, show the formula and substitution. For **Sketch**, label intercepts, extrema, periods and asymptotes. For an **Exact** answer, keep $\pi$ and surds rather than decimal approximations. For an ambiguous triangle, state why any second angle is accepted or rejected.

## Links

Builds on [[2 Coordinate geometry in the (x, y) plane]] · Leads to [[4 Differentiation]]
