---
tags: [stem-tutor/lesson, P2]
spec: "P2"
subtopic: "P2-1"
kcs: ["P2-1.1", "P2-1.2", "P2-1.3"]
---
# 1 Proof
> [!abstract] In one breath
> A proof moves from stated assumptions through justified logical steps to the required conclusion. Exhaustion proves a claim by checking a complete finite set of cases; one valid counterexample disproves a claim about every case.

## Key ideas

A **mathematical proof** is an argument whose conclusion follows from its assumptions. Start by stating the allowed values and any given facts. Explain why each step follows. End by stating exactly what has been established. A few correct examples may suggest a general result, but they do not prove it for every integer. Equally, a step cannot quietly narrow the domain: writing $n=2k$ assumes that $n$ is even, so it is not justified by the statement that $n$ is an integer alone.

**Proof by exhaustion** means trying all possible cases. It works when the assumptions lead to a finite, complete list. For example, if $x$ and $y$ are *positive* odd integers less than 7, each must be in $\{1,3,5\}$. The unordered pairs are $(1,1),(1,3),(1,5),(3,3),(3,5),(5,5)$. Their sums are $2,4,6,6,8,10$, each divisible by 2. Swapping the numbers does not change a sum, but equal-value pairs must still be included. Thus every allowed pair has an even sum.

The word *positive* matters. “Odd integers less than 7” also includes $-1,-3,-5,\ldots$, so $\{1,3,5\}$ is not an exhaustive list under those assumptions. You would need a general argument, such as writing odd integers as $2a+1$ and $2b+1$, to cover that infinite domain.

**Disproof by counterexample** targets a statement claiming something for every allowed input. A counterexample is one input that satisfies all assumptions but makes the conclusion false. To disprove “$n^2-n+1$ is prime for every positive integer $n$,” take $n=5$. Then $5^2-5+1=21=3\times7$. Since 21 is composite, the claim is false. A prime result for $n=4$ is not enough to prove the universal claim, and an input outside the domain cannot disprove it.

## Method

1. Read the statement literally. Record the domain and the conclusion.
2. For exhaustion, list **every** permitted case. If order does not affect the result, explain why swapped cases need no separate check. Keep equal-value cases unless excluded.
3. Calculate or reason through each case, then conclude that all allowed cases satisfy the claim.
4. For disproof, choose one allowed input. Evaluate the expression exactly and demonstrate why the claimed property fails.

> [!example]- Worked example
> Prove by exhaustion that $x+y$ is divisible by 2 when $x,y$ are positive odd integers less than 7.
> The assumptions give $x,y\in\{1,3,5\}$. Up to swapping, the six pairs are $(1,1),(1,3),(1,5),(3,3),(3,5),(5,5)$.
> Their sums are $2,4,6,6,8,10$. Every sum is divisible by 2, so the claim holds for every allowed pair.

> [!example]- Worked counterexample
> Disprove “$n^2-n+1$ is prime for every positive integer $n$.”
> Choose $n=5$, which is in the stated domain. Then $n^2-n+1=25-5+1=21=3\times7$.
> Since 21 is composite, this one counterexample disproves the universal statement.

## Traps

- **Trap:** Checking several successful values is called proof by exhaustion. **Why it's wrong:** The untested domain may contain a failure. **Instead:** Identify a complete finite set before checking cases.
- **Trap:** Check only pairs with different values. **Why it's wrong:** $x=y$ is allowed unless excluded. **Instead:** Include pairs such as $(3,3)$.
- **Trap:** Give a counterexample outside the domain. **Why it's wrong:** It does not contradict the stated claim. **Instead:** Show both that the input is allowed and that the conclusion fails.

## Exam technique

For **Prove**, give the full logical chain and an explicit conclusion. For **Show that**, include every step leading to the given result. For **Explain**, name why the cases are complete or why a proposed input is a valid counterexample. In an exhaustion proof, a tidy list or table helps a marker see that no case was skipped. In a counterexample, factor a supposedly prime output so its failure is beyond doubt.

## Links

Builds on integer parity and divisibility · Leads to further methods of proof in Pure Mathematics.
