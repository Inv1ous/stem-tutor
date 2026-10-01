---
tags: [stem-tutor/lesson, S1]
spec: "S1"
subtopic: "S1-4"
kcs: ["S1-4.1", "S1-4.2", "S1-4.3"]
---
# 4 Correlation and regression
> [!abstract] In one breath
> A scatter diagram shows how two paired variables move together. Regression gives a least-squares line for predicting a response; the product moment correlation coefficient (PMCC) describes the direction and strength of *linear* association.

## Key ideas

Put the **explanatory variable** on the horizontal axis and the **response variable** on the vertical axis. The explanatory variable is the input used to predict the response. A scatter diagram may show a positive trend, a negative trend, a curved pattern or no clear pattern. Check for unusual points before summarising it with a straight line.

For the regression of $y$ on $x$, write $y=a+bx$, where $b$ is the gradient and $a$ is the vertical intercept. The least-squares method chooses the line that minimises the sum of the squared *vertical* residuals, $\sum(y_i-\hat y_i)^2$. Its gradient and intercept are

$$
b=\frac{S_{xy}}{S_{xx}},\qquad a=\bar y-b\bar x.
$$

Here $S_{xx}=\sum(x_i-\bar x)^2$ and $S_{xy}=\sum(x_i-\bar x)(y_i-\bar y)$. If summary totals are supplied, $S_{xx}=\sum x_i^2-(\sum x_i)^2/n$ and $S_{xy}=\sum x_iy_i-(\sum x_i)(\sum y_i)/n$. The fitted line always passes through the mean point $(\bar x,\bar y)$. To draw it, plot that point and one more point found from the equation. Regressing $x$ on $y$ answers a different prediction question and normally gives a different line.

The PMCC is

$$
r=\frac{S_{xy}}{\sqrt{S_{xx}S_{yy}}},\qquad -1\le r\le1.
$$

The sign gives direction: positive means that larger $x$ tends to accompany larger $y$; negative means the reverse. The closer $|r|$ is to $1$, the stronger the **linear** association. A value near zero signals little linear association, but a curved relationship could still be strong. An outlier can change $r$ markedly. Correlation alone does not establish that changing one variable causes the other to change.

## Method

1. Decide which variable predicts which. Label the axes and identify the observed range of the explanatory variable.
2. For the regression of response $y$ on explanatory $x$, calculate the means, $S_{xx}$ and $S_{xy}$ if needed. Find $b=S_{xy}/S_{xx}$, then $a=\bar y-b\bar x$.
3. Write the equation with the original variable names and units. Check it at $(\bar x,\bar y)$. To predict, substitute the given explanatory value.
4. Say whether the prediction is **interpolation** (within the observed range) or **extrapolation** (outside it). An extrapolation is less reliable because the observed pattern might not continue.
5. For PMCC, calculate $S_{yy}$ too, then use the formula for $r$. Interpret both sign and strength in the problem's context; inspect the plot for curves and outliers.

> [!example]- Worked example
> For $y$ on $x$, suppose $\bar x=4$, $\bar y=9$, $S_{xx}=16$ and $S_{xy}=24$. Find the regression line.
> $$
> b=\frac{24}{16}=1.5.
> $$
> $$
> a=9-1.5(4)=3.
> $$
> Hence $y=3+1.5x$. Check: at $x=4$, the fitted $y$ is $9$, so the line passes through $(4,9)$.

## Traps

- **Trap:** Force the line through the origin. **Why it's wrong:** Least squares requires it to pass through the mean point, which usually gives a nonzero intercept. **Instead:** Calculate $a=\bar y-b\bar x$.
- **Trap:** Use the line to predict far beyond the recorded explanatory values. **Why it's wrong:** No observations confirm that the trend continues there. **Instead:** State that this is extrapolation and qualify its reliability.
- **Trap:** Treat $r$ as evidence of cause, or treat $r\approx0$ as proof of no relationship. **Why it's wrong:** PMCC measures linear association only. **Instead:** Describe association in context and inspect the scatter diagram.

## Exam technique

For **Calculate** and **Find**, show the centred-sum formula, substitution and final equation rather than only a calculator result. For **Interpret**, name both variables and describe the trend in context. When asked to **Explain** a prediction's reliability, compare the proposed explanatory value with the observed interval. If a question uses different letters, identify predictor and response before choosing the regression direction. A linear change of variable needs algebraic substitution into the equation; do not merely relabel the axis.

## Links

Builds on [[2 Representation and summary of data]] · Leads to [[5 Discrete random variables]]
