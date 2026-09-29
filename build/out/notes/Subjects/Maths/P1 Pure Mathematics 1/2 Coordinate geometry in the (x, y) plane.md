---
tags: [stem-tutor/lesson, P1]
spec: "P1"
subtopic: "P1-2"
kcs: ["P1-2.1", "P1-2.2"]
---
# 2 Coordinate geometry in the (x, y) plane
> [!abstract] In one breath
> Every straight-line question starts with a gradient: find it from two points, or from an equation by rearranging to $y=mx+c$. Parallel lines share a gradient; perpendicular gradients multiply to $-1$.

## Key ideas
**Gradient** of the line through $(x_1,y_1)$ and $(x_2,y_2)$:

$$m=\frac{y_2-y_1}{x_2-x_1}$$

**Equation of a line** with gradient $m$ through $(x_1,y_1)$: $y-y_1=m(x-x_1)$. The same line can be written as $y=mx+c$ or as $ax+by+c=0$ (with $a$, $b$, $c$ integers when the question asks). The gradient of $ax+by+c=0$ is $-\dfrac{a}{b}$.

**Parallel lines** have equal gradients: $m_1=m_2$.

**Perpendicular lines** have gradients with product $-1$:

$$m_1m_2=-1 \quad\Longleftrightarrow\quad m_2=-\frac{1}{m_1}$$

Turn the gradient upside down **and** change its sign. A horizontal line ($y=k$, gradient 0) and a vertical line ($x=k$, no gradient) are perpendicular, but this test cannot be applied to them.

![[Assets/P1/P1-2-perpendicular.svg]]

## Method
1. **Find the gradient.** From two points use $\dfrac{y_2-y_1}{x_2-x_1}$, taking both differences in the same order. From an equation, rearrange to $y=mx+c$ first. For a parallel line, keep the gradient; for a perpendicular line, apply $m_2=-\dfrac{1}{m_1}$.
2. **Substitute a point.** Put the gradient and one known point into $y-y_1=m(x-x_1)$.
3. **Tidy into the requested form.** Multiply through to clear fractions, collect the terms on one side, and keep the $x$ term positive.
4. **Check.** Substitute the given point (and the other point, if there is one) into your final equation; both sides must agree.

> [!example]- Worked example
> Find an equation of the line through $(-3,2)$ perpendicular to $4x+3y=12$, in the form $ax+by+c=0$ with integer coefficients.
>
> **Gradient of the given line.** $3y=-4x+12$, so $y=-\dfrac{4}{3}x+4$ and $m_1=-\dfrac{4}{3}$.
>
> **Perpendicular gradient.** Turn over and change the sign:
>
> $$m_2=-\frac{1}{m_1}=\frac{3}{4}$$
>
> **Equation.** $y-2=\dfrac{3}{4}(x+3)$, so $4y-8=3x+9$.
>
> **Answer.** $3x-4y+17=0$. Check: $3(-3)-4(2)+17=0$.

## Traps
- **Trap:** the gradient of $2x+5y=20$ is $2$, $-2$ or $\dfrac{2}{5}$. **Why it's wrong:** the equation is not yet in the form $y=mx+c$; the $y$ term has to be moved to the left with its coefficient divided out. **Instead:** rearrange to $y=-\dfrac{2}{5}x+4$, so $m=-\dfrac{2}{5}$.
- **Trap:** the perpendicular of $\dfrac{2}{3}$ is $-\dfrac{2}{3}$ (sign only) or $\dfrac{3}{2}$ (inverse only). **Why it's wrong:** the product must be $-1$, and each of these fails. **Instead:** $-\dfrac{3}{2}$, and check by multiplying.
- **Trap:** $\dfrac{\Delta x}{\Delta y}$, or subtracting in opposite orders. **Why it's wrong:** gradient is rise over run, and mixed orders flip the sign. **Instead:** second minus first on top and on the bottom.
- **Trap:** $y=3$ and $x=-2$ are not perpendicular because $3\times(-2)\ne-1$. **Why it's wrong:** $-2$ is a position, not a gradient, and a vertical line has no gradient. **Instead:** horizontal and vertical lines are always perpendicular.

## Exam technique
- *Show that* two lines are perpendicular: work out both gradients, show the product $=-1$, and write a conclusion sentence. Marks are lost if the product is not stated.
- *Find an equation in the form $ax+by+c=0$*: integers are required, so clear fractions; any integer multiple is accepted, but a fraction in the coefficients is not.
- *Find the coordinates where the line meets the axes*: put $y=0$ for the $x$-axis and $x=0$ for the $y$-axis into your final equation.
- With *hence*, use your previous gradient or equation rather than starting again.

![[Assets/P1/P1-2-parallel.svg]]

## Links
Builds on [[1 Algebra and functions]] · Leads to [[4 Differentiation]], where the normal to a curve uses the perpendicular gradient rule
