---
tags: [stem-tutor/lesson, P2]
spec: "P2"
subtopic: "P2-4"
kcs: ["P2-4.1", "P2-4.2", "P2-4.3", "P2-4.4", "P2-4.5"]
---
# 4 Sequences and series
> [!abstract] In one breath
> A sequence is an ordered list of terms; a series adds its terms. Recognise whether the rule uses an index, a constant difference, or a constant ratio before choosing a formula.

## Key ideas
An **nth-term formula** gives $u_n$ directly from $n$. A **recurrence relation** $x_{n+1}=f(x_n)$ generates the next term from the previous one, so it also needs a starting value. If $x_1=2$ and $x_{n+1}=3x_n-1$, then $x_2=5$, $x_3=14$ and $x_4=41$. Indexing matters: an initial value $x_0$ is different from $x_1$.

An **arithmetic sequence** has a constant difference $d$. Starting at $a$, its nth term is $u_n=a+(n-1)d$. Its first $n$ terms sum to $S_n=\frac n2[2a+(n-1)d]$, or $S_n=\frac n2(a+l)$ if the last term $l$ is known. To prove this, write the sum both forwards and backwards. Each of the $n$ paired columns totals $a+l$, giving $2S_n=n(a+l)$. Taking $a=d=1$ gives $1+2+\cdots+n=n(n+1)/2$. Sigma notation $\sum_{k=1}^n u_k$ means add the terms with indices 1 to $n$ inclusive.

A sequence is **increasing** when $u_{n+1}>u_n$ for every relevant $n$, and **decreasing** when $u_{n+1}<u_n$. It is **periodic** when a fixed positive integer $p$ satisfies $u_{n+p}=u_n$ throughout; the smallest such $p$ is the period. For example, $1,-1,1,-1,\ldots$ has period 2. Test consecutive terms: negative values can still increase, and alternating signs do not guarantee periodicity when magnitudes change.

A **geometric sequence** has a constant ratio $r$: $u_n=ar^{n-1}$. Its finite sum is $S_n=a(1-r^n)/(1-r)$ for $r\ne1$; if $r=1$, then $S_n=na$. To prove the formula, subtract $rS_n$ from $S_n$: intermediate terms cancel and $(1-r)S_n=a(1-r^n)$. A sum to infinity exists only if $|r|<1$, when $r^n\to0$ and $S_\infty=a/(1-r)$. If a finite sum is given and the number of terms is unknown, rearrange to isolate $r^n$, then take logarithms; check the resulting $n$ meets the question's integer condition.

For positive integer $n$, the **binomial expansion** is $(a+bx)^n=\sum_{r=0}^{n}\binom nr a^{n-r}(bx)^r$. Here $\binom nr={}^nC_r=n!/[r!(n-r)!]$, with $0!=1$. The coefficient of $x^r$ is $\binom nr a^{n-r}b^r$, and there are $n+1$ terms.

## Method
1. Identify whether consecutive terms have a fixed difference, a fixed ratio, or a more general recurrence.
2. Label the first term $a$, difference $d$ or ratio $r$, and the required index $n$.
3. Select a term or sum formula. For a geometric sum to infinity, check $|r|<1$ before substitution.
4. For a binomial coefficient, select the term whose power of $x$ matches the question, then calculate $\binom nr a^{n-r}b^r$.

> [!example]- Worked example
> Find the sum of the first 8 terms of $4,7,10,\ldots$.
> The sequence is arithmetic: $a=4$, $d=3$, $n=8$.
> $$S_8=\frac82[2(4)+(8-1)3]=4(29)=116.$$
> The use of $n-1$ counts the seven gaps between the first and eighth terms.

## Traps
- **Trap:** Use $n$ gaps to reach term $n$. **Why it's wrong:** The first term is already at index 1. **Instead:** Use $n-1$ in term formulae.
- **Trap:** Accept a geometric sum to infinity for $r=-2$. **Why it's wrong:** $|r|=2>1$. **Instead:** Check the absolute value of the ratio.
- **Trap:** Treat $\binom nr$ as $n^r$. **Why it's wrong:** It counts combinations. **Instead:** Evaluate $n!/[r!(n-r)!]$.

## Exam technique
For **Find** or **Calculate**, show the chosen formula and substitution before the answer. For **Show that** or **Prove**, give the forward and reversed arithmetic sums, or the original and multiplied geometric sums, then show the cancellation. For **Explain**, state the criterion using consecutive terms; for periodicity, give a fixed period. Keep exact fractions where possible.

## Links
Builds on algebraic substitution and powers · Leads to [[5 Exponentials and logarithms]]
