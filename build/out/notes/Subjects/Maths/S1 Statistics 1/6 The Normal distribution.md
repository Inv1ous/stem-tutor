---
tags: [stem-tutor/lesson, S1]
spec: "S1"
subtopic: "S1-6"
kcs: ["S1-6.1"]
---
# 6 The Normal distribution
> [!abstract] In one breath
> A Normal distribution models a continuous quantity with a symmetric, bell-shaped curve. Its mean locates the centre, its variance controls the spread, and standard Normal tables give areas to the left of a chosen value.

## Key ideas
Write $X\sim N(\mu,\sigma^2)$: the mean is $\mu$, the variance is $\sigma^2$, and the standard deviation is the positive value $\sigma$. The curve is symmetric about $x=\mu$. Its total area is $1$, with half on either side of the mean. Probabilities are areas under the curve, so $P(X=a)=0$ for any single exact value $a$. Consequently $P(X<a)=P(X\leq a)$.

The standard Normal variable is $Z\sim N(0,1)$. Convert a value of $X$ by standardising:

$$Z=\frac{X-\mu}{\sigma}.$$

The cumulative distribution function $\Phi(z)=P(Z<z)$ is tabulated. It gives the area **left** of $z$. Symmetry gives $\Phi(-z)=1-\Phi(z)$. For an upper tail, use $P(Z>z)=1-\Phi(z)$. Between two values $a<b$, subtract: $P(a<Z<b)=\Phi(b)-\Phi(a)$. The tables do not require you to know the probability density function formula, derive the mean or variance, or interpolate.

## Method
1. Read $\mu$ and $\sigma^2$ from the model; take the positive square root to get $\sigma$.
2. Sketch the symmetric bell curve, mark the mean and bounds, and shade the required area.
3. Standardise each bound using $z=(x-\mu)/\sigma$.
4. Read the cumulative table, then complement or subtract as the shading requires. Keep enough digits from the table until the final answer.
5. For a percentile, find the table value of $z$ first and reverse the formula: $x=\mu+z\sigma$. If two probabilities are given and both parameters are unknown, form two equations in $\mu$ and $\sigma$ and solve them simultaneously.

> [!example]- Worked example
> Let $X\sim N(70,10^2)$. Find $P(60<X<85)$.
> The standard deviation is $10$. The bounds become $z=(60-70)/10=-1$ and $z=(85-70)/10=1.5$.
> From the table, $\Phi(-1)=0.1587$ and $\Phi(1.5)=0.9332$.
> Subtract the lower cumulative area from the upper: $P(60<X<85)=0.9332-0.1587=0.7745$.

## Traps
- **Trap:** Reading $N(70,10^2)$ as standard deviation $100$. **Why it's wrong:** The second parameter is the variance. **Instead:** Use $\sigma=10$.
- **Trap:** Giving $\Phi(z)$ for an upper tail. **Why it's wrong:** The table gives the lower tail. **Instead:** Shade the region and calculate $1-\Phi(z)$.
- **Trap:** Giving $\Phi(z_2)$ for a bounded interval. **Why it's wrong:** That includes all area below the lower bound. **Instead:** Subtract $\Phi(z_1)$.

## Exam technique
For **Find** or **Calculate**, show the standardisation and the table values before the final probability. For **Show that**, write each link of the argument even if the target is printed in the question. In simultaneous-equation problems, state which cumulative probabilities correspond to each $z$ score, form both equations, and solve for the positive $\sigma$. A quick sketch catches tail and symmetry errors without needing a precise graph.

## Links
Builds on [[5.3 Mean and variance of a discrete RV]] and [[2.3 Variance, standard deviation, IQR]].
