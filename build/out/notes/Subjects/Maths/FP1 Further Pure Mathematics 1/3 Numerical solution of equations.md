---
tags: [stem-tutor/lesson, edexcel-fp1]
spec: "FP1"
subtopic: "FP1-3"
kcs: ["FP1-3.1"]
---
# 3 Numerical solution of equations
> [!abstract] In one breath
> A numerical method approaches a root of $f(x)=0$ through successive estimates. Interval bisection uses a sign-changing bracket, linear interpolation uses a secant, and Newton-Raphson uses a tangent.

## Key ideas

Opposite endpoint signs prove a root only when the function is continuous throughout the interval. For $f(x)=1/x$ on $[-1,1]$, the signs differ but $x=0$ is a discontinuity and there is no root. A tangent root, such as that of $x^2$ at zero, may show no sign change. An interval can also contain several roots: the test proves existence, not uniqueness.

A **root** is a value $r$ for which $f(r)=0$. Often an exact solution is unavailable or inconvenient, so calculate estimates and check their accuracy. For the methods here, $f$ uses functions from P1 and P2; the differentiation needed for Newton-Raphson is also from P1 and P2.

**Interval bisection** starts with $a<b$ where a continuous $f$ has opposite signs at the endpoints: $f(a)f(b)<0$. Calculate $m=(a+b)/2$. If $f(m)=0$, stop. Otherwise retain $[a,m]$ when $f(a)f(m)<0$; retain $[m,b]$ when $f(m)f(b)<0$. Each step halves the bracket width. The midpoint is an estimate, while the whole bracket gives a useful error bound: its distance from the root is at most half the current width.

**Linear interpolation** replaces the curve between $(a,f(a))$ and $(b,f(b))$ with a straight line. Its crossing of the $x$-axis is
$$
x=a-\frac{f(a)(b-a)}{f(b)-f(a)}.
$$
This is also called a secant estimate. It uses the sizes as well as the signs of the endpoint values, so it generally differs from the midpoint. If repeating with a bracket, evaluate $f(x)$ and replace the endpoint with the same sign as $f(x)$.

![[Assets/FP1/FP1-3-secant.svg]]
Notice that the secant joins two curve points; its axis crossing $4/3$ is an estimate, not a point on the curve.

**Newton-Raphson** starts with a chosen $x_0$. The tangent to $y=f(x)$ at $x_n$ crosses the $x$-axis at the next estimate:
$$
x_{n+1}=x_n-\frac{f(x_n)}{f'(x_n)}.
$$
Differentiate correctly and make sure $f'(x_n)\ne0$. A poor starting value or a very small derivative can make the iterates unreliable. Check each iterate against the equation rather than assuming it converges.

![[Assets/FP1/FP1-3-tangent.svg]]
Notice that the tangent uses the slope at $x=1.5$; its axis crossing $17/12$ supplies the next iterate.

## Method
1. Rearrange the equation as $f(x)=0$ and identify the required method and accuracy.
2. For bisection, show endpoint signs, calculate the midpoint and its sign, then write the new bracket. Repeat until its width meets the required accuracy.
3. For interpolation, calculate both signed endpoint values, substitute in the secant formula, then check the new function value if another step is needed.
4. For Newton-Raphson, find $f'(x)$, write the recurrence, substitute the current estimate, and calculate the next one. Repeat and verify stability to the requested decimal places.

> [!example]- Worked example
> Let $f(x)=x^2-2$ and start from $[1,2]$. Since $f(1)=-1$ and $f(2)=2$, a root is bracketed.
> Bisection gives $m=1.5$ and $f(1.5)=0.25$, so the new bracket is $[1,1.5]$.
> Linear interpolation from the original endpoints gives $x=1-(-1)(2-1)/(2-(-1))=4/3$.
> For Newton-Raphson, $f'(x)=2x$. Starting at $x_0=1.5$ gives $x_1=1.5-0.25/3=17/12\approx1.4167$.
> These are estimates made by different geometric rules. Substituting each into $f$ checks how close it is to zero.

## Traps
- **Trap:** Keep the half with the smaller endpoint value in bisection. **Why it's wrong:** The root is identified by a sign change, not a magnitude comparison. **Instead:** State the signs at both ends of the retained bracket.
- **Trap:** Treat interpolation as another midpoint calculation. **Why it's wrong:** The secant crosses the axis according to its endpoint heights. **Instead:** Substitute the signed values in the secant formula.
- **Trap:** Reverse the Newton-Raphson quotient. **Why it's wrong:** The tangent's horizontal correction is function value divided by gradient. **Instead:** Write $f(x_n)/f'(x_n)$ before substituting.

## Exam technique
For **Calculate** or **Find**, show the formula, substitution and estimate. For **Show that**, include the signs or algebra that justify the stated result. If asked to give an answer to a stated number of decimal places, retain extra figures in intermediate steps and confirm the final rounding using a sufficiently narrow bracket or stable iterates. State when an iterate is undefined because its derivative is zero.

A bracket gives two bounds; an approximation gives one value, often the midpoint. After $n$ bisections, the width is $(b-a)/2^n$: choose the smallest integer $n$ meeting the target width. Stable Newton iterates suggest convergence but alone do not prove correct rounding; a bracket must lie within the same rounding boundaries.

> [!example]- Worked example: certify two decimal places
> For the positive root of $f(x)=x^2-3$, test the boundaries around $1.73$: $1.725$ and $1.735$.
> $f(1.725)=-0.024375<0$ and $f(1.735)=0.010225>0$.
> The polynomial is continuous, so a root lies strictly inside $(1.725,1.735)$. Every number there rounds to $1.73$, proving two-decimal-place accuracy. There is only one positive root because $x^2$ increases for $x>0$.

## Links
Builds on [[P1 Differentiation]] · Leads to [[FP1 Further numerical methods]]
