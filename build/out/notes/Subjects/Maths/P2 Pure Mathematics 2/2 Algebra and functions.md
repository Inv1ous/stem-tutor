---
tags: [stem-tutor/lesson, P2]
spec: "P2"
subtopic: "P2-2"
kcs: ["P2-2.1"]
---
# 2 Algebra and functions
> [!abstract] In one breath
> Dividing a polynomial by a linear expression leaves a constant remainder. Evaluate the polynomial at the zero of that expression to find the remainder; if it is zero, the expression is a factor.

## Key ideas
For a polynomial $f(x)$ and a nonzero linear divisor $ax+b$, algebraic division has the form $f(x)=(ax+b)q(x)+r$. Here $q(x)$ is the **quotient**, and $r$ is the **remainder**. The remainder is a constant because its degree must be smaller than the degree of the linear divisor. Substituting $x=-b/a$ makes $ax+b$ vanish, leaving $r=f(-b/a)$. This is the **Remainder Theorem**. In particular, $ax+b$ is a factor precisely when $f(-b/a)=0$: this is the **Factor Theorem**. For a divisor $ax-b$, its zero is $b/a$, so the corresponding test is $f(b/a)=0$.

A factor is a divisor that leaves zero remainder. A root is an input at which the polynomial equals zero. Thus a root $x=c$ gives factor $x-c$, and any nonzero constant multiple of this expression is also a factor. For example, a root $2/3$ gives factor $3x-2$.

## Method
1. Set the proposed linear divisor equal to zero. This gives the input for substitution; check the sign carefully.
2. Evaluate $f$ at that input. The result is the remainder. If it is zero, state that the proposed expression is a factor by the Factor Theorem.
3. To factorise a cubic, divide it by a known linear factor. Use long division or coefficient matching to find the quadratic quotient, then factorise the quadratic.
4. Multiply the factors back out to check all coefficients and the constant term.

To divide $6x^3+11x^2-x-6$ by $2x+3$, write $6x^3+11x^2-x-6=(2x+3)(Ax^2+Bx+C)+r$. Expanding the right-hand side gives $2Ax^3+(2B+3A)x^2+(2C+3B)x+3C+r$. Match coefficients in descending powers: $2A=6$, so $A=3$; $2B+3A=11$, so $2B+9=11$ and $B=1$; $2C+3B=-1$, so $2C+3=-1$ and $C=-2$; $3C+r=-6$, so $-6+r=-6$ and $r=0$. Thus the quotient is $3x^2+x-2$ and the remainder is $0$.

> [!example]- Worked example
> Show that $2x+3$ is a factor of $f(x)=6x^3+11x^2-x-6$, and factorise $f(x)$ completely.
> Set $2x+3=0$, so $x=-3/2$. Substitution gives
> $$f(-3/2)=6(-3/2)^3+11(-3/2)^2-(-3/2)-6=0.$$
> By the Factor Theorem, $2x+3$ is a factor. Dividing gives quotient $3x^2+x-2$. Then $3x^2+x-2=(x+1)(3x-2)$, so
> $$f(x)=(2x+3)(x+1)(3x-2).$$
> Expanding this product recovers the original cubic.

## Traps
- **Trap:** Substitute $b/a$ for a divisor $ax+b$. **Why it's wrong:** Its zero is $-b/a$. **Instead:** Solve the divisor equation first.
- **Trap:** Treat a zero remainder as a zero quotient. **Why it's wrong:** The quotient is the polynomial left after division. **Instead:** Write $f=(\text{divisor})(\text{quotient})+\text{remainder}$.
- **Trap:** Stop after finding one linear factor of a cubic. **Why it's wrong:** The quadratic quotient may factor further. **Instead:** Factorise that quotient and check the complete product.

## Exam technique
For **Show that** a linear expression is a factor, display its zero and the full substitution giving zero. For **Find** the remainder, use the zero of the divisor even when the divisor is $ax+b$ rather than $x-c$. When asked to factorise completely, state all linear factors and verify by expansion.

## Links
Builds on [[1 Algebra and functions]] · Leads to later work with polynomial equations.
