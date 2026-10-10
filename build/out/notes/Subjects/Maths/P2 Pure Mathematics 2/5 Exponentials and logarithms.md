---
tags: [stem-tutor/lesson, P2]
spec: "P2"
subtopic: "P2-5"
kcs: ["P2-5.1", "P2-5.2", "P2-5.3"]
---
# 5 Exponentials and logarithms
> [!abstract] In one breath
> Exponential functions turn an input into an exponent. Logarithms reverse that operation, and their laws let you simplify expressions and solve equations with unknown exponents.

## Key ideas
For the exponential function $y=a^x$, require $a>0$ and $a\ne1$. Every curve passes through $(0,1)$ because $a^0=1$. Its outputs are positive, so it never touches or crosses the $x$-axis; $y=0$ is a horizontal asymptote. Its domain is all real numbers and its range is positive real numbers. If $a>1$, the graph increases from left to right. If $0<a<1$, it decreases. A sketch should label $(0,1)$ and the asymptote and show the correct direction.

The statement $\log_a b=x$ means exactly $a^x=b$. Here $a>0$, $a\ne1$, and $b>0$. This inverse relationship gives $\log_a a=1$ and $\log_a1=0$. The argument of a real logarithm must be positive; a zero or negative argument is invalid.

For $a,x,y>0$ with $a\ne1$, the laws of logarithms are
$$
\log_a(xy)=\log_a x+\log_a y,\qquad
\log_a(x/y)=\log_a x-\log_a y.
$$
The power law is $\log_a(x^k)=k\log_a x$. Setting $k=-1$ gives $\log_a(1/x)=-\log_a x$. All logs in a product or quotient law must have the same base. These laws come directly from the laws of indices: multiplying powers adds exponents, and dividing powers subtracts them.

## Method
1. To simplify a log expression, check that each argument is positive and that the bases match. Move coefficients inside using the power law, then combine sums as products and differences as quotients.
2. To solve $a^x=b$, check that $b>0$. Take logarithms of both sides: $x\ln a=\ln b$. Divide by $\ln a$ to obtain $x=\ln b/\ln a$. This is the change of base formula; common logarithms work just as well if you use the same base above and below.
3. Substitute the result into the original exponential equation to check it, and round only at the end if a decimal answer is requested.

> [!example]- Worked example
> Solve $3^x=20$ to three significant figures.
> Take natural logarithms: $\ln(3^x)=\ln20$.
> Use the power law: $x\ln3=\ln20$.
> Divide: $x=\ln20/\ln3=2.73$ to three significant figures.
> Check: $3^{2.73}$ is close to $20$; the small difference is from rounding.

## Traps
- **Trap:** Adding arguments when logs are added. **Why it's wrong:** The product law combines $\log_a x+\log_a y$ into $\log_a(xy)$. **Instead:** Multiply the arguments.
- **Trap:** Reversing the change of base fraction. **Why it's wrong:** In $x\ln a=\ln b$, the coefficient of $x$ is $\ln a$. **Instead:** Divide $\ln b$ by $\ln a$.
- **Trap:** Drawing an $x$-intercept on an exponential graph. **Why it's wrong:** $a^x$ remains positive. **Instead:** Draw the curve approaching $y=0$ without meeting it.

## Exam technique
For **Sketch**, show the intercept, asymptote, and increasing or decreasing shape; a plotted table alone is insufficient. For **Find** or **Calculate**, show the logarithm step before giving a decimal. For an **Exact** answer, leave $\ln b/\ln a$ rather than rounding it. For **Show that**, write each algebraic step, especially the power law and division. Check positivity before using any logarithm law.

## Links
Builds on [[1 Laws of indices]] · Leads to [[6 Trigonometry]]
