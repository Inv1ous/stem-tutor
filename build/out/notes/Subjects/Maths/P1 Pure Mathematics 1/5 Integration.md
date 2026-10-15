---
tags: [stem-tutor/lesson, P1]
spec: "P1"
subtopic: "P1-5"
kcs: ["P1-5.1", "P1-5.2"]
---
# 5 Integration
> [!abstract] In one breath
> Indefinite integration reverses differentiation. An answer needs an arbitrary constant because differentiation removes constants.

## Key ideas
If $F'(x)=f(x)$, then $F$ is an **antiderivative** of $f$. Indefinite integration finds the whole family:
$$
\int f(x)\,dx=F(x)+C.
$$
Here $C$ is the **constant of integration**. For example, both $x^2+3$ and $x^2-5$ differentiate to $2x$. So $\int 2x\,dx=x^2+C$, where any real value of $C$ is possible until further information is given. The answer is a function, rather than a single number.

For a power of $x$, reverse $\frac{d}{dx}x^{n+1}=(n+1)x^n$:
$$
\int x^n\,dx=\frac{x^{n+1}}{n+1}+C,\qquad n\ne-1.
$$
The restriction matters: when $n=-1$, the denominator would be zero, and this power rule cannot be used. You can also integrate a sum or difference term by term and take constant multiples outside. For instance, $\int(3x^2-4x+6)\,dx=x^3-2x^2+6x+C$. Put just one $C$ at the end because the separate constants combine into one arbitrary constant.

## Method
1. Rewrite the integrand as a sum of powers. Expand a squared bracket such as $(x+2)^2=x^2+4x+4$. For a quotient, divide each numerator term by the denominator: $(3x-1)/(2x^2)=\frac32x^{-1}-\frac12x^{-2}$. In this last example, use $\int x^{-1}\,dx=\ln|x|+C$ for the excluded power. Thus $\int(3x-1)/(2x^2)\,dx=\frac32\ln|x|+\frac1{2x}+C$, on an interval that does not cross $x=0$.
2. For each allowed power $ax^n$, raise the exponent to $n+1$ and divide the coefficient by $n+1$.
3. Add $C$. Differentiate your answer to check that it returns the original integrand.
4. If you know $f'(x)$ and a point $(a,b)$ on the curve, first integrate to get $f(x)=F(x)+C$. Then use $b=F(a)+C$ to find $C$ and write the full equation $y=f(x)$.

> [!example]- Worked example
> Given $f'(x)=3x^2-2x$ and $(1,5)$ on the curve, find $y=f(x)$.
> Integrate term by term: $f(x)=x^3-x^2+C$.
> Substitute the point: $5=1-1+C$, so $C=5$.
> Therefore $y=x^3-x^2+5$. Differentiating gives $3x^2-2x$, as required.

> [!example]- Worked example: a quotient using only the power rule
> Find $\int\frac{3x-1}{2x^3}\,dx$ for $x\ne0$.
> Divide each numerator term by $2x^3$: $\frac{3x-1}{2x^3}=\frac32x^{-2}-\frac12x^{-3}$.
> Both exponents are allowed. Raise each by one and divide by the new exponent:
> $\int\frac{3x-1}{2x^3}\,dx=-\frac32x^{-1}+\frac14x^{-2}+C$.
> Check by differentiation: $\frac{d}{dx}(-\frac32x^{-1}+\frac14x^{-2}+C)=\frac32x^{-2}-\frac12x^{-3}=\frac{3x-1}{2x^3}$.

> [!example]- Faded practice
> Find $\int\frac{4x+3}{2x^3}\,dx$ for $x\ne0$. The rewriting step is $2x^{-2}+\frac32x^{-3}$; finish the integration, include $C$, and differentiate to check.

> [!answer]- Faded practice answer
> $-2x^{-1}-\frac34x^{-2}+C$. Its derivative is $2x^{-2}+\frac32x^{-3}=\frac{4x+3}{2x^3}$.

> [!warning] The excluded power needs a separate rule
> The earlier quotient with denominator $2x^2$ contains $x^{-1}$. Its logarithm term uses the separately stated rule $\int x^{-1}\,dx=\ln|x|+C$, on an interval away from zero; it does not follow from the P1 power rule, whose stated outcome excludes $n=-1$. Never try to divide by $n+1=0$. The quotient above instead gives only allowed negative powers.

## Traps
- **Trap:** Leave out $C$. **Why it's wrong:** Every constant has derivative zero. **Instead:** Include $C$ for every indefinite integral.
- **Trap:** Keep the exponent the same. **Why it's wrong:** Differentiation would not return the original power. **Instead:** Increase it by one and divide by the new exponent.
- **Trap:** Apply the power rule to $x^{-1}$. **Why it's wrong:** The denominator becomes zero. **Instead:** Recognise this as the excluded case.
- **Trap:** Use the given point in $f'(x)$. **Why it's wrong:** A point on the curve satisfies $y=f(x)$. **Instead:** Integrate first, then substitute the coordinates to determine $C$.

## Exam technique
For **Find**, show the rewritten powers and the integration step so the method is visible. For **Verify**, differentiate the proposed answer and compare it with the integrand. If the question gives a point, finish with an equation for $y$, not just a value of $C$. Check your final curve against both the derivative and the given point.

## Links
Builds on [[4 Differentiation]] · Leads to later applications of integration.
