---
tags: [stem-tutor/lesson, edexcel-fp1]
spec: "FP1"
subtopic: "FP1-1"
kcs: ["FP1-1.1", "FP1-1.2", "FP1-1.3", "FP1-1.4", "FP1-1.5", "FP1-1.6"]
---
# 1 Complex numbers
> [!abstract] In one breath
> A complex number combines real and imaginary components. The same algebra that solves quadratics also unlocks higher-degree polynomials when you use conjugate pairs.

## Key ideas
A complex number is $z=a+ib$, where $a,b\in\mathbb R$ and $i^2=-1$. Its real part is $a$ and its imaginary part is $b$, not $ib$. Two complex numbers are equal only when their real parts match and their imaginary parts match. The conjugate is $z^*=a-ib$. The modulus is $|z|=\sqrt{a^2+b^2}$, its distance from the origin. The argument $\theta$ is the angle from the positive real axis to the line from the origin to $z$. Thus $a=r\cos\theta$, $b=r\sin\theta$, and $z=r\cos\theta+ir\sin\theta$, where $r=|z|$.

Plot $a+ib$ at $(a,b)$ on an Argand diagram: the horizontal axis is real and the vertical axis is imaginary. Addition is vector addition. Multiplying by $i$ rotates a point $90^\circ$ anticlockwise about the origin. More generally, multiplication combines scaling and rotation; division reverses the denominator's scaling and rotation. In particular, $|z_1z_2|=|z_1||z_2|$ and, for $z_2\ne0$, $|z_1/z_2|=|z_1|/|z_2|$.

## Method
1. For sums and products, collect real and imaginary terms and replace $i^2$ by $-1$. For a quotient, multiply numerator and denominator by the denominator's conjugate; the denominator then becomes real.
2. For $ax^2+bx+c=0$, use $x=(-b\pm\sqrt{b^2-4ac})/(2a)$. If $b^2-4ac<0$, write $\sqrt{-q}=i\sqrt q$. With real coefficients, the two roots are conjugates.
3. For a cubic with real or integer coefficients, pair any given non-real root $u+vi$ with $u-vi$. Multiply their linear factors to get the real quadratic $(x-u)^2+v^2$, divide the cubic by it, and solve the remaining linear factor.
4. For a quartic with real coefficients, do the same for a given complex root. Alternatively, use two known real roots as linear factors. Divide by the known factors and solve the remaining quadratic, whose roots may be real or complex.

> [!example]- Worked example
> Given $2+i$ is a root of $f(x)=(x^2-4x+5)(x-1)(x+2)$, find all roots.
> Since coefficients are real, $2-i$ is also a root.
> Their factors multiply to $(x-2-i)(x-2+i)=(x-2)^2+1=x^2-4x+5$.
> The remaining factors are $x-1$ and $x+2$. The four roots are $2+i$, $2-i$, $1$, and $-2$.

## Traps
- **Trap:** Treat $ib$ as the imaginary part. **Why it's wrong:** The imaginary part is a real number. **Instead:** Report $b$.
- **Trap:** Divide real parts and imaginary parts separately. **Why it's wrong:** Complex division couples them. **Instead:** Multiply by the denominator's conjugate.
- **Trap:** Stop after finding one complex root of a cubic or quartic. **Why it's wrong:** Real coefficients force its conjugate to be a root. **Instead:** Form the real quadratic factor and divide.

## Exam technique
For **Find** or **Calculate**, show the factor or formula before the roots. For **Show that** or **Prove**, write the full conjugate-factor expansion and polynomial division. For **Sketch**, label both Argand axes, plotted coordinates and any transformation. Give exact values such as $2\pm3i$ when the question asks for an exact answer.

## Links
Builds on [[Solving quadratic equations]] · Leads to [[Roots of polynomials]]
