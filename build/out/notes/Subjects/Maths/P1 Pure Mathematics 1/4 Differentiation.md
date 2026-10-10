---
tags: [stem-tutor/lesson, P1]
spec: "P1"
subtopic: "P1-4"
kcs: ["P1-4.1", "P1-4.2", "P1-4.3"]
---
# 4 Differentiation
> [!abstract] In one breath
> Differentiation gives the gradient of a tangent and an instantaneous rate of change. Power rules make this gradient easy to calculate, then a point and gradient determine a tangent or normal.

## Key ideas

For two points on $y=f(x)$, the gradient of their secant is $[f(a+h)-f(a)]/h$. Let the second point move towards the first: if the limit exists, the **derivative** at $x=a$ is

$$
f'(a)=\lim_{h\to0}\frac{f(a+h)-f(a)}{h}.
$$

This is the gradient of the tangent at $(a,f(a))$. It is also the instantaneous **rate of change** of $y$ with respect to $x$, written $dy/dx$ or $f'(x)$. For instance, if $y$ is displacement and $x$ is time, $dy/dx$ is instantaneous velocity. Its sign tells you whether the curve is rising or falling as $x$ increases; a zero derivative means a horizontal tangent. Differentiating again gives the **second derivative**, $d^2y/dx^2=f''(x)$: the rate at which the first derivative changes. In the displacement example, this is acceleration.

The **power rule** is $\frac{d}{dx}(x^n)=nx^{n-1}$. Differentiate sums and differences term by term and carry constant multiples through: $\frac{d}{dx}(cf+g)=cf'+g'$. A constant has derivative zero. Negative and fractional powers work by the same rule wherever the expression is defined; for example, $\frac{d}{dx}(x^{-1})=-x^{-2}$.

## Method

1. Simplify the expression into powers of $x$. Expand $(2x+5)(x-1)=2x^2+3x-5$. For a quotient such as $(2x^2+5x-3)/(3x)$, divide each numerator term by $3x$ to get $2x/3+5/3-1/x$.
2. Differentiate term by term. These examples give $4x+3$ and $2/3+1/x^2$, respectively. Keep the sign of a negative power: the derivative of $-x^{-1}$ is $+x^{-2}$.
3. For a tangent or normal at $x=a$, find the actual point $(a,f(a))$ and tangent gradient $m=f'(a)$. Use $y-f(a)=m(x-a)$ for the tangent.
4. For the normal, use gradient $-1/m$ when $m\ne0$, and the same point. When $m=0$, the normal is the vertical line $x=a$.

> [!example]- Worked example
> Find the tangent and normal to $y=x^2+1$ at $x=2$.
> The point is $(2,5)$. Differentiate: $dy/dx=2x$, hence $m=4$.
> Tangent: $y-5=4(x-2)$, so $y=4x-3$.
> Normal: its gradient is $-1/4$, so $y-5=-\frac14(x-2)$.
> Both lines pass through $(2,5)$, and their gradients multiply to $-1$.

## Traps

- **Trap:** Using the gradient between two separated points as the tangent gradient. **Why it's wrong:** A secant is an average rate over an interval. **Instead:** Take the limit as the interval shrinks to zero, or use $f'(a)$.
- **Trap:** Differentiating each factor of a product and multiplying the results. **Why it's wrong:** That does not follow from the power rule. **Instead:** Expand the product before differentiating in P1.
- **Trap:** Keeping the exponent unchanged when differentiating $x^n$. **Why it's wrong:** The power rule subtracts one from the exponent. **Instead:** Write $nx^{n-1}$ before simplifying.
- **Trap:** Giving the tangent gradient to the normal. **Why it's wrong:** They are perpendicular. **Instead:** Take the negative reciprocal, or use a vertical normal for a horizontal tangent.

## Exam technique

For **Find** or **Calculate**, show the rewritten curve, derivative, substituted coordinate and final line equation. For **Show that**, show each algebraic step to the stated result. For **Explain** or **Interpret**, name the variables and state what the derivative measures in context. Check that a proposed tangent or normal passes through the specified point.

## Links

Builds on [[1 Algebra and functions]] and [[2 Coordinate geometry]] · Leads to [[5 Integration]]
