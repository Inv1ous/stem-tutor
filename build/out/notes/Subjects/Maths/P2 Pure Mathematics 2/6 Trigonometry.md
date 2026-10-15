---
tags: [stem-tutor/lesson, P2]
spec: "P2"
subtopic: "P2-6"
kcs: ["P2-6.1", "P2-6.2"]
---
# 6 Trigonometry
> [!abstract] In one breath
> Two identities let you rewrite trigonometric expressions. To solve an equation, find every matching angle in the given interval, then undo any transformation of the angle.

## Key ideas
An **identity** is true for every angle for which both sides are defined. The tangent identity is $\tan\theta=\dfrac{\sin\theta}{\cos\theta}$, provided $\cos\theta\ne0$. The Pythagorean identity is $\sin^2\theta+\cos^2\theta=1$. Thus $\cos^2\theta=1-\sin^2\theta$ and $\sin^2\theta=1-\cos^2\theta$. If you take a square root, choose its sign from the quadrant: a square gives a magnitude, not a sign. For instance, if $\sin\theta=5/13$ in quadrant II, $\cos\theta=-12/13$.

Sine is positive in quadrants I and II; cosine in I and IV; tangent in I and III. The reference angle gives the acute angle, while the quadrant gives the other solutions. Sine and cosine repeat every $360^\circ$ or $2\pi$; tangent repeats every $180^\circ$ or $\pi$. Keep degree and radian modes consistent.

## Method
1. Rewrite an equation using an identity if needed. For $6\cos^2x+\sin x-5=0$, substitute $\cos^2x=1-\sin^2x$, giving $6\sin^2x-\sin x-1=0$. Factor it as $(3\sin x+1)(2\sin x-1)=0$; solve both branches.
2. If the angle is $u=2x+\pi/6$ or $u=x+30^\circ$, transform **both** interval bounds to bounds for $u$ before finding any angles.
3. Find all angles in the transformed interval. Use a principal value, quadrant symmetry, and the correct period. List values at included endpoints and omit values at excluded endpoints.
4. Reverse the substitution to obtain $x$, then substitute into the original equation and compare against the original interval.

After factorisation, check every proposed sine or cosine value lies in $[-1,1]$ **before** finding angles. Discard values outside this range because no real angle can attain them. In step 1, both $1/2$ and $-1/3$ are valid, so both branches must be solved.

> [!example]- Worked example: a squared sine
> Find all exact solutions of $\sin^2(x+\pi/6)=1/2$ for $-\pi\le x<\pi$.
> Let $u=x+\pi/6$. Adding $\pi/6$ to both bounds gives $-5\pi/6\le u<7\pi/6$.
> Taking square roots gives $\sin u=\pm1/\sqrt{2}$; keeping only the positive root loses solutions.
> The reference angle is $\pi/4$. Searching both signs in the transformed interval gives $u=-3\pi/4,-\pi/4,\pi/4,3\pi/4$.
> Subtract $\pi/6$ from each: $x=-11\pi/12,-5\pi/12,\pi/12,7\pi/12$.
> Each lies in $-\pi\le x<\pi$ and gives squared sine $1/2$ on substitution. At either original endpoint the squared sine is $1/4$, so neither adds a solution.

Source notes: branch checking follows `sources/library/SaveMyExams/YMA01 pure-2/YMA01 c6.1.pdf`, p.11. The squared-sine example follows [Pearson's IAL Mathematics specification, P2 section 6.2, printed p.20 (PDF p.26)](https://qualifications.pearson.com/content/dam/pdf/International%20Advanced%20Level/Mathematics/2018/Specification-and-Sample-Assessment/international-a-level-maths-spec.pdf); the working is supplied here.

> [!example]- Worked example
> Find all solutions of $\tan 2x=1$ for $90^\circ<x<270^\circ$.
> Put $u=2x$. Then $180^\circ<u<540^\circ$.
> Since tangent has period $180^\circ$, $u=225^\circ,405^\circ$ in this interval.
> Therefore $x=112.5^\circ,202.5^\circ$. Both lie strictly inside the stated interval.

## Traps
- **Trap:** Keep only the inverse trig calculator result. **Why it's wrong:** A trig graph often reaches the same value more than once. **Instead:** Use quadrant signs and repeat by the period until the interval is exhausted.
- **Trap:** Solve for $2x$ using the original bounds for $x$. **Why it's wrong:** The transformation changes the admissible angle range. **Instead:** Transform both bounds first.
- **Trap:** Write $\cos\theta=\sqrt{1-\sin^2\theta}$ in every quadrant. **Why it's wrong:** Cosine may be negative. **Instead:** Use the quadrant to select the sign.

## Exam technique
For **Find** and **Calculate**, show the identity or reference angle, all admissible angles, the inverse transformation, and the final interval check. For **Show that** or **Prove**, write each algebraic identity step and state when division requires $\cos\theta\ne0$. If an answer is requested **exact**, retain fractions, $\pi$, and inverse trig expressions instead of premature decimals. Watch a mixed boundary such as $-\pi\le x<\pi$: the left endpoint may be a solution even though the right one is excluded.

## Links
Builds on 3.3 Trig function graphs and periodicity · Leads to later trigonometric modelling and calculus.

Builds on [[3 Trigonometry]] · Leads to [[2 Trigonometry]].
