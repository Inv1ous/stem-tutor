---
tags: [stem-tutor/lesson, edexcel-fp1]
spec: "FP1"
subtopic: "FP1-2"
kcs: ["FP1-2.1", "FP1-2.2", "FP1-2.3"]
---
# 2 Roots of quadratic equations
> [!abstract] In one breath
> A quadratic's coefficients tell you the sum and product of its roots without solving it. Those two quantities are enough to evaluate many symmetric expressions and to form equations whose roots are transformed versions of the originals.

## Key ideas
Suppose $ax^2+bx+c=0$, where $a\ne0$, has roots $\alpha$ and $\beta$. Factorisation gives $a(x-\alpha)(x-\beta)=ax^2-a(\alpha+\beta)x+a\alpha\beta$. Comparing coefficients, write
$$
S=\alpha+\beta=-\frac ba,\qquad P=\alpha\beta=\frac ca.
$$
These identities hold whether the roots are distinct, repeated, real or complex. The minus sign in the sum is essential. If the equation is not monic, divide by $a$ or keep the divisions explicitly. For example, $2x^2-7x+3=0$ has $S=7/2$ and $P=3/2$; you need not find either root.

A symmetric root expression is unchanged when $\alpha$ and $\beta$ are exchanged. Rewrite it in $S$ and $P$ before substituting numbers. From $S^2=\alpha^2+2\alpha\beta+\beta^2$,
$$
\alpha^2+\beta^2=S^2-2P.
$$
Expanding $S^3$ and collecting the cross terms gives
$$
\alpha^3+\beta^3=S^3-3PS.
$$
Similarly, provided $P\ne0$, $1/\alpha+1/\beta=S/P$. The condition matters: if either original root is zero, a reciprocal root does not exist.

## Method
To form a quadratic equation with new roots, call them $u$ and $v$. First find their sum $T=u+v$ and product $U=uv$ using $S$ and $P$. Then write $x^2-Tx+U=0$. Clear fractions by multiplying the *whole equation* by a nonzero common denominator. Any nonzero multiple describes the same equation; integer coefficients in their simplest ratio are usually preferred.

For squared roots, $u=\alpha^2$ and $v=\beta^2$, so $T=S^2-2P$ and $U=P^2$. For cubed roots, $T=S^3-3PS$ and $U=P^3$. For reciprocal roots, $T=S/P$ and $U=1/P$. A less direct transformation can still be handled systematically. If $u=\alpha+2/\alpha$ and $v=\beta+2/\beta$, then $T=S+2S/P$ and $U=P+2(\alpha/\beta+\beta/\alpha)+4/P$. Replace $\alpha/\beta+\beta/\alpha$ by $(S^2-2P)/P$ to finish entirely in $S,P$.

> [!example]- Worked example
> The roots of $x^2-5x+6=0$ are $\alpha,\beta$. Form the quadratic with roots $\alpha^2,\beta^2$.
> $S=5$ and $P=6$ from the coefficients.
> The new sum is $T=S^2-2P=25-12=13$; the new product is $U=P^2=36$.
> Therefore the required equation is $x^2-13x+36=0$.
> Check: the old roots are $2,3$, whose squares are $4,9$; their sum is $13$ and product $36$.

## Traps
- **Trap:** Taking the root sum as $b/a$. **Why it's wrong:** The $x$ coefficient of $a(x-\alpha)(x-\beta)$ is $-a(\alpha+\beta)$. **Instead:** Use $-b/a$.
- **Trap:** Writing $\alpha^2+\beta^2=S^2$. **Why it's wrong:** $S^2$ contains $2\alpha\beta$. **Instead:** Subtract $2P$.
- **Trap:** Applying a root transformation to the coefficients individually. **Why it's wrong:** Coefficients encode a *sum and product*, and these change together. **Instead:** Find the transformed $T,U$ first.

## Exam technique
For **Find** or **Calculate**, state $S$ and $P$, show the identity used and simplify to an exact fraction or integer. For **Show that** or **Prove**, show the expansion or algebraic identity and every substitution leading to the given result. For **Hence**, use the relation established in the earlier part. A quick check by solving the original quadratic can detect arithmetic slips, but the sum-and-product method is usually shorter and still works when explicit roots are awkward.

## Links
Builds on [[Solving quadratic equations]] · Leads to [[Further algebra with polynomial roots]]
