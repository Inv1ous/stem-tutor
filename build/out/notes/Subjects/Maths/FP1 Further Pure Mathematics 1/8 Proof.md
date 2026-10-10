---
tags: [stem-tutor/lesson, edexcel-fp1]
spec: "FP1"
subtopic: "FP1-8"
kcs: ["FP1-8.1"]
---
# 8 Proof

> [!abstract] In one breath
> Mathematical induction proves a statement throughout a sequence of integers: establish its first case, then prove that any true case forces the next one. The same logic handles sums, divisibility, recurrence formulae and matrix powers.

## Key ideas

Let $P(n)$ be the claim for an integer $n$. If its first permitted value is $n_0$, verify **the base case** $P(n_0)$. For **the inductive step**, take an arbitrary integer $k\geq n_0$, assume $P(k)$, and use that assumption to establish $P(k+1)$. Then state explicitly that $P(n)$ holds for all integers $n\geq n_0$ by mathematical induction. This is a proof for every such integer: checking several early cases only suggests a pattern.

Choose the first value carefully. A sequence with $u_1$ starts at $1$; a claim for non-negative integers starts at $0$. Write the induction hypothesis in the exact form you will substitute. The next case must follow from the hypothesis rather than being assumed.

## Method

1. State $P(n)$ and its range. Substitute the first allowed integer on **both** sides of the proposed identity, or evaluate the expression for a divisibility claim.
2. Assume $P(k)$ for an arbitrary allowed $k$. Keep this assumption visible in your algebra.
3. Build the $k+1$ case from the $k$ case: add the next summand, use a recurrence, rewrite a divisibility expression, or multiply matrices.
4. Simplify until the answer is exactly the proposed expression with $n=k+1$. State the conclusion and range.

For a series, the crucial line is $S_{k+1}=S_k+a_{k+1}$. For example, if $S_k=\frac14k^2(k+1)^2$ for a sum of cubes, add $(k+1)^3$ and factor: $S_{k+1}=\frac14(k+1)^2(k+2)^2$. Similarly, the proposed identity $\sum_{r=1}^{n}r(r+1)=\frac13n(n+1)(n+2)$ works because adding $(k+1)(k+2)$ to the assumed sum factors into the expression at $k+1$.

> [!example]- Worked example: divisibility
> Prove $3^{2n+1}+1$ is divisible by $4$ for every non-negative integer $n$.
> At $n=0$, $3^1+1=4$, so the base case holds.
> Assume $3^{2k+1}+1=4q$ for some integer $q$.
> The next expression is $3^{2(k+1)+1}+1=9(3^{2k+1}+1)-8=4(9q-2)$.
> Since $9q-2$ is an integer, the next expression is divisible by $4$. The result follows by induction.

For a recurrence, start with the given relation. If $u_{n+1}=3u_n+4$, $u_1=1$, and the proposed general term is $u_n=3^n-2$, check $u_1=3^1-2=1$. Under the hypothesis $u_k=3^k-2$, obtain $u_{k+1}=3(3^k-2)+4=3^{k+1}-2$. This is the required next term.

For matrix powers, equality means equality of every entry. With $A=\begin{pmatrix}1&1\\0&1\end{pmatrix}$, the proposed form is $A^n=\begin{pmatrix}1&n\\0&1\end{pmatrix}$. At $n=0$, both sides are $I$. Assuming the form for $A^k$, multiplication gives $A^{k+1}=A^kA=\begin{pmatrix}1&k+1\\0&1\end{pmatrix}$. This proves the pattern, rather than merely observing it in small powers.

## Traps

- **Trap:** Check the first three values and say “therefore true”. **Why it's wrong:** finitely many cases do not prove the next case. **Instead:** prove $P(k)\Rightarrow P(k+1)$ for arbitrary $k$.
- **Trap:** Replace $u_{k+1}$ or $A^{k+1}$ by the proposed formula at the start. **Why it's wrong:** that is the statement you must prove. **Instead:** begin from the recurrence or from $A^kA$.
- **Trap:** Say an expression is “clearly divisible”. **Why it's wrong:** the dependence on the hypothesis is hidden. **Instead:** show it equals the divisor times an integer, as in $4(9q-2)$.

## Exam technique

For **Show that** and **Prove**, show the base case, the hypothesis, the algebraic transition and the final conclusion. In a sum, display the new term. In a matrix product, display enough multiplication to check all entries. Use “for arbitrary $k$” so your step is general, and finish with the exact range in the question.

## Links

Builds on [[7 Summing simple finite series]] and [[5 Multiplying matrices together]].
