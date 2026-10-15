---
tags: [stem-tutor/lesson, P2]
spec: "P2"
subtopic: "P2-7"
kcs: ["P2-7.1"]
---
# 7 Differentiation
> [!abstract] In one breath
> A derivative gives the gradient of a curve. Its zeros locate stationary points, while its sign shows where the function increases or decreases; together these facts solve optimisation problems and guide a sketch.

## Key ideas
A **stationary point** has a horizontal tangent: $f'(x)=0$. It might be a local maximum, a local minimum, or a stationary point of inflection. Do not call every stationary point a turning point. For instance, $f(x)=x^3$ has $f'(0)=0$, yet the curve rises on both sides of the origin.

A function is **increasing** on an interval where $f'(x)>0$ and **decreasing** where $f'(x)<0$. A change in $f'$ from positive to negative identifies a local maximum; a change from negative to positive identifies a local minimum. No sign change means there is no turning point. At a stationary point, the **second derivative test** offers a shortcut: $f''(x)<0$ gives a local maximum and $f''(x)>0$ a local minimum. If $f''(x)=0$, the test is inconclusive, so inspect the sign of $f'$ on either side.

A *local* maximum is higher than nearby points; it need not be the highest value over an entire domain. In a practical problem with a restricted domain, compare all feasible stationary values and any included endpoints before claiming an absolute maximum or minimum.

### See the derivative sign test
![[Assets/P2/P2-7-sign-test.svg]]
*For $y=x^3-3x$, the gradient $3(x-1)(x+1)$ is positive for $x<-1$ and $x>1$, and negative for $-1<x<1$.*
The positive-to-negative change at $(-1,2)$ gives a local maximum; the negative-to-positive change at $(1,-2)$ gives a local minimum.

![[Assets/P2/P2-7-stationary-inflection.svg]]
*For $y=x^3$, the horizontal tangent at $(0,0)$ is a stationary inflection.*
Here $y'=3x^2$ is positive on both sides of zero. The curve continues rising through its horizontal tangent; it does not turn.

## Method
1. Differentiate $f(x)$ and solve $f'(x)=0$. Check that each solution belongs to the stated domain.
2. Substitute each $x$-value into the original function to find the coordinates. Classify it using a sign table for $f'$ or the second derivative test.
3. For increasing and decreasing intervals, split the domain at stationary values and test the sign of $f'$ in every interval.
4. For a curve sketch, mark stationary points and intercepts, then draw the curve consistently with the sign of $f'$ and its end behaviour. A sketch need not be to scale.
5. For a practical maximum or minimum, use the given constraint to write the target quantity as a function of one variable. State its feasible domain, then optimise and check boundaries.

> [!example]- Worked example
> Find and classify the stationary points of $y=x^3-6x^2+9x+1$, and state where the function decreases.
> Differentiate and factor:
> $$y'=3x^2-12x+9=3(x-1)(x-3).$$
> Hence $y'=0$ at $x=1$ and $x=3$. Substitution into the original function gives $(1,5)$ and $(3,1)$.
> Since $y''=6x-12$, we have $y''(1)=-6<0$ and $y''(3)=6>0$. Therefore $(1,5)$ is a local maximum and $(3,1)$ a local minimum.
> Between the roots, $3(x-1)(x-3)<0$, so the function decreases for $1<x<3$.

> [!example]- Worked example: compare the whole closed interval
> Find the absolute maximum and minimum of $h(x)=x^3-3x$ on $-2\leq x\leq3$.
> Since $h'(x)=3(x-1)(x+1)$, the stationary candidates are $x=-1,1$, both within the interval.
> Evaluate every candidate and both endpoints: $h(-2)=-2$, $h(-1)=2$, $h(1)=-2$, $h(3)=18$.
> The absolute maximum is $18$ at $x=3$; the absolute minimum is $-2$, attained at both $x=-2$ and $x=1$.
> The local maximum at $x=-1$ is not the absolute maximum. Continuity on this closed interval ensures that comparing this complete list finds both absolute extrema.

## Traps
- **Trap:** Using $f'(x)=0$ alone to claim a maximum. **Why it's wrong:** A minimum or stationary inflection can also have zero gradient. **Instead:** Check the derivative sign or use $f''$ when it is nonzero.
- **Trap:** Reading the height of the graph to decide whether it increases. **Why it's wrong:** Increasing concerns the change in $y$ as $x$ grows. **Instead:** Test the sign of $f'(x)$.
- **Trap:** Optimising a rectangle using the full perimeter as a side. **Why it's wrong:** Adjacent sides sum to half the perimeter. **Instead:** Write the constraint before forming the area function.

## Exam technique
For **Find**, show the derivative equation, the stationary solutions and the classification. For **Sketch**, label coordinates and intercepts clearly, with a shape consistent with increasing and decreasing intervals. For **Explain**, say why the sign change or second derivative justifies the classification. In context, give the requested quantity with its units and check the feasible domain.

## Links
Builds on [[4 Differentiation]] and Tangents and normals · Leads to Optimisation

### Sources for these additions
The sign-test diagrams and question explanations use the methods in the learner’s `sources/library/SaveMyExams/YMA01 pure-2/YMA01 c7.1.pdf`, PDF pp. 5–7 (original examples here). For the strict-increase proof, the positive-derivative criterion is justified by [University of Cambridge: The mean value theorem](https://www.dpmms.cam.ac.uk/~wtg10/meanvalue.html); applying it on each side of the isolated zero gives the argument used in the added question.
