---
tags: [stem-tutor/lesson, S1]
spec: "S1"
subtopic: "S1-5"
kcs: ["S1-5.1", "S1-5.2", "S1-5.3", "S1-5.4"]
---
# 5 Discrete random variables
> [!abstract] In one breath
> A discrete random variable assigns numbers to outcomes and has a finite or countably infinite set of values. Its probabilities let us calculate cumulative probabilities, the mean and the variance.

## Key ideas
A **random variable** assigns a numerical value to each outcome of a random experiment. It is **discrete** when its possible values form a finite or countably infinite set. The number of heads in four tosses can be $0,1,2,3,4$, so it is discrete. Exact time can vary continuously, so it is not. A probability distribution gives the probability of every possible value. Each probability is non-negative and the probabilities sum to one.

The **probability function** is $p(x)=P(X=x)$. The **cumulative distribution function** gives the probability up to and including a cutoff:
$$
F(x_0)=P(X\leq x_0)=\sum_{x\leq x_0}p(x).
$$
If $p(0)=0.2$, $p(1)=0.3$ and $p(2)=0.5$, then $F(1)=0.2+0.3=0.5$. A cumulative probability cannot decrease when its cutoff increases because additional probabilities are non-negative. To calculate $P(X>1)$, subtract $F(1)$ from one.

The **mean** or expectation is a probability-weighted average, $E(X)=\sum xp(x)$. For **variance**, first find $E(X^2)=\sum x^2p(x)$, squaring each value before weighting it. Then use
$$
\operatorname{Var}(X)=E(X^2)-[E(X)]^2.
$$
This describes spread around the mean. If $Y=aX+b$, then $E(Y)=aE(X)+b$, whereas $\operatorname{Var}(Y)=a^2\operatorname{Var}(X)$. Adding $b$ shifts all values equally and leaves the spread unchanged. Multiplying by $a$ scales each deviation by $a$, so its square scales by $a^2$.

A **discrete uniform distribution** assigns equal probability to each possible value. For $n$ consecutive integers $1,2,\ldots,n$, each probability is $1/n$, the mean is $(n+1)/2$ and the variance is $(n^2-1)/12$. For consecutive values from $r$ to $s$, count $n=s-r+1$ values. Their mean is $(r+s)/2$ and their variance is still $(n^2-1)/12$, because shifting every value does not change variance. Equal spacing alone does not imply uniformity; check that the probabilities are equal.

## Method
1. List the possible values and check that their probabilities total one.
2. For $F(x_0)$, add the probabilities for every $x\leq x_0$, including equality.
3. For a mean, sum $xp(x)$. For a variance, sum $x^2p(x)$ and subtract the square of the mean.
4. For $aX+b$, apply the distinct mean and variance rules. For a uniform distribution, count the possible values before substituting $n$.

> [!example]- Worked example
> Let $X=0,1,2$ have probabilities $0.25,0.5,0.25$. Find its variance.
> First, $E(X)=0(0.25)+1(0.5)+2(0.25)=1$.
> Next, $E(X^2)=0^2(0.25)+1^2(0.5)+2^2(0.25)=1.5$.
> Hence $\operatorname{Var}(X)=1.5-1^2=0.5$.
> If $Y=3X+2$, then $E(Y)=3(1)+2=5$ and $\operatorname{Var}(Y)=3^2(0.5)=4.5$.

## Traps
- **Trap:** Read $F(1)$ as $P(X=1)$. **Why it's wrong:** Cumulative probability includes every value up to one. **Instead:** Add each eligible $p(x)$.
- **Trap:** Use $E(X^2)-E(X)$ for variance. **Why it's wrong:** The mean must be squared. **Instead:** Write the formula first.
- **Trap:** Add $b$ to variance for $aX+b$. **Why it's wrong:** A shift preserves spread. **Instead:** Multiply variance by $a^2$.
- **Trap:** Call equally spaced values uniform. **Why it's wrong:** Uniform refers to equal probabilities. **Instead:** Check every $p(x)$.

## Exam technique
For **Calculate** or **Find**, show the formula and substituted values before the answer. For **Explain**, refer to the outcomes and probabilities in context. For **Show that**, include every intermediate step even when the final value is printed in the question. Keep exact fractions when requested. Distinguish $E(X^2)$ from $[E(X)]^2$ in variance working.

## Links
Builds on 3 Elementary probability · Leads to 6 Binomial distribution
