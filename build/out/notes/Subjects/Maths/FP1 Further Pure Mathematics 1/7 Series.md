---
tags: [stem-tutor/lesson, edexcel-fp1]
spec: "FP1"
subtopic: "FP1-7"
kcs: ["FP1-7.1"]
---
# 7 Series
> [!abstract] In one breath
> A finite series adds a fixed list of terms. For polynomial terms, expand the summand, split the sum, and apply the standard formulae with the correct limits.

## Key ideas
The symbol $\sum_{r=1}^{n}f(r)$ means $f(1)+f(2)+\cdots+f(n)$: $r$ is an index, and $1$ and $n$ are the lower and upper limits. The result is a single number when $n$ is specified, or an expression in $n$ when it is not. Sigma notation saves writing every term but does not change what is being added. For example, $\sum_{r=1}^{4}r^2=1^2+2^2+3^2+4^2=30$.

These three standard finite sums are the starting point:
$$
\sum_{r=1}^{n}r=\frac{n(n+1)}2,\qquad
\sum_{r=1}^{n}r^2=\frac{n(n+1)(2n+1)}6,\qquad
\sum_{r=1}^{n}r^3=\left[\frac{n(n+1)}2\right]^2.
$$
Notice that the cube sum is the **square** of the sum of the first $n$ integers. A sum of squares has a different formula. Test either formula at $n=2$ if you are unsure: $1^2+2^2=5$, while $1^3+2^3=9$.

A sum can be split across addition and a constant factor: $\sum(f(r)+g(r))=\sum f(r)+\sum g(r)$ and $\sum c f(r)=c\sum f(r)$ when the limits are the same. Thus $r(r+2)=r^2+2r$ gives
$$
\sum_{r=1}^{n}r(r+2)=\sum_{r=1}^{n}r^2+2\sum_{r=1}^{n}r
=\frac{n(n+1)(2n+7)}6.
$$
This uses the formulae directly; the method of differences is not required for this chapter.

## Method
1. Read the lower and upper limits. If needed, write the first two terms to confirm the pattern.
2. Expand a polynomial summand, then split the sum into known types. Keep each coefficient outside its sum.
3. Substitute the upper limit into the relevant formula and simplify only after writing the formula clearly.
4. If the lower limit is $a>1$, calculate the sum through the upper limit and subtract all terms *before* $a$:
   $\sum_{r=a}^{b}f(r)=\sum_{r=1}^{b}f(r)-\sum_{r=1}^{a-1}f(r)$.
5. Check the size and sign against a few directly evaluated terms. For a short range, direct addition is also a valid way to check.

> [!example]- Worked example
> Find $\sum_{r=3}^{6}r(r+2)$.
> First expand the summand: $r(r+2)=r^2+2r$. Remove the terms at $r=1,2$ from both standard sums:
> $$
> \sum_{r=3}^{6}r(r+2)
> =[S_2(6)-S_2(2)]+2[S_1(6)-S_1(2)],
> $$
> where $S_1(k)=k(k+1)/2$ and $S_2(k)=k(k+1)(2k+1)/6$. Now $S_2(6)=91$, $S_2(2)=5$, $S_1(6)=21$, and $S_1(2)=3$, so the answer is $(91-5)+2(21-3)=122$. Direct addition confirms it: $15+24+35+48=122$.

## Traps
- **Trap:** Treat $\sum r^2$ as $(\sum r)^2$. **Why it's wrong:** squaring a sum adds cross terms. **Instead:** use the separate square-sum formula.
- **Trap:** Cube the triangular number to obtain $\sum r^3$. **Why it's wrong:** the cube-sum identity squares that number. **Instead:** write the brackets and exponent before substitution.
- **Trap:** Multiply two sums to evaluate $\sum r(r+2)$. **Why it's wrong:** a product of sums includes terms with different indices multiplied together. **Instead:** expand each summand, then split the sum.
- **Trap:** For a sum starting at $r=a$, subtract through $a$. **Why it's wrong:** that removes the first required term. **Instead:** subtract through $a-1$.

## Exam technique
For **Find** or **Calculate**, state the relevant formula, show the substitution, and simplify to an exact integer or algebraic expression. For **Show that**, include the expansion and the line where both known sums are substituted; the final factorisation alone does not prove the given result. A quick check at a small $n$ can catch a missing factor of $2$ or a shifted limit.

## Links
Builds on [[4 Sequences and series]] in P2 · Leads to polynomial sums and later uses of sigma notation.
