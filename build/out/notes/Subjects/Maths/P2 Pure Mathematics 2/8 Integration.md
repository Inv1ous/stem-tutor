---
tags: [stem-tutor/lesson, P2]
spec: "P2"
subtopic: "P2-8"
kcs: ["P2-8.1", "P2-8.2", "P2-8.3"]
---
# 8 Integration
> [!abstract] In one breath
> A definite integral is evaluated by subtracting the antiderivative at the lower limit from its value at the upper limit. The same calculation gives signed area; geometry tells you when to reverse or split it.

## Key ideas
If $F'(x)=f(x)$, the fundamental theorem of calculus gives $\int_a^b f(x)\,dx=F(b)-F(a)$. The numbers $a$ and $b$ are the limits of integration. Write $[F(x)]_a^b$ as a reminder to substitute both limits in the correct order. A definite integral has a number as its value; the arbitrary constant in an indefinite integral cancels in the subtraction. Reversing the limits changes the sign, and equal limits give zero.

The definite integral represents signed area between a curve and the $x$-axis. Where $f(x)\geq0$, $\int_a^b f(x)\,dx$ is the area under the curve. Where the curve lies below the axis, its integral is negative but its geometric area is positive. If a curve crosses the axis inside the interval, find the crossing and split the integral before taking positive areas.

For a region bounded by two curves, solve $f(x)=g(x)$ to find the intersection coordinates. On each interval, identify which curve is higher. Then the enclosed area is $\int_a^b(\text{upper}-\text{lower})\,dx$. A straight line is treated just like another curve. If the order changes, split at the crossing. The result is in square units when both axes measure lengths in the same unit.

The trapezium rule is numerical integration: it estimates area from function values when an antiderivative is inconvenient. Divide $[a,b]$ into $n$ equal strips of width $h=(b-a)/n$, and let $y_i=f(a+ih)$. Then
$$
T=\frac h2[y_0+2y_1+2y_2+\cdots+2y_{n-1}+y_n].
$$
This is equivalent to giving the first and last ordinates half weight. For a convex curve such as $y=x^2$, the straight edges lie above the curve, so the rule overestimates. More strips usually reduce the error, although the direction and size depend on the curve. If asked for an error, compare the estimate with an exact integral: absolute error is $|T-I|$, and percentage error is $100|T-I|/|I|\%$ when $I\ne0$.

## Method
1. For a definite integral, integrate first, write the antiderivative in square brackets, then substitute upper and lower limits separately.
2. For a bounded region, solve for intersections, decide which curve is upper, integrate their difference, and check the answer is non-negative.
3. For a trapezium estimate, calculate $h$, list all $n+1$ ordinates in order, halve only the endpoints, and multiply the weighted sum by $h$.

> [!example]- Worked example
> Find the area between $y=6x-x^2$ and $y=2x$.
> The curves meet where $6x-x^2=2x$, so $x(4-x)=0$ and $x=0,4$.
> Between these points, the quadratic is above the line.
> $$
> A=\int_0^4[(6x-x^2)-2x]\,dx=[2x^2-x^3/3]_0^4=32/3.
> $$
> The area is $32/3$ square units.

## Traps
- **Trap:** Add the two limit values. **Why it's wrong:** The definite integral is a change in antiderivative. **Instead:** Use $F(b)-F(a)$.
- **Trap:** Integrate lower curve minus upper curve. **Why it's wrong:** This gives a negative signed integral. **Instead:** Check the vertical order between intersections.
- **Trap:** Use every ordinate once in the trapezium sum. **Why it's wrong:** Endpoint ordinates each border only one strip. **Instead:** Halve the first and last.

## Exam technique
For *Find* and *Calculate*, show the integration or weighted sum, substitutions, and final value. If asked for an exact area, keep fractions rather than rounding. For an error estimate, state whether the trapezium result is high or low and give the requested absolute or percentage error. A sketch can help identify intersections and the upper curve, but the area calculation still needs justified limits.

## Links
Builds on [[5 Integration]] · Leads to [[9 Differential equations]]
