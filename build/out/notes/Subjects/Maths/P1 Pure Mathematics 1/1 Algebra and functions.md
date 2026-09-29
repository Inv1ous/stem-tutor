---
tags: [stem-tutor/lesson, P1]
spec: "P1"
subtopic: "P1-1"
kcs: ["P1-1.1", "P1-1.2", "P1-1.3", "P1-1.4", "P1-1.5", "P1-1.6", "P1-1.7", "P1-1.8", "P1-1.9", "P1-1.10", "P1-1.11", "P1-1.12"]
---
# 1 Algebra and functions
> [!abstract] In one breath
> Indices and surds are the arithmetic toolkit; quadratics (vertex, discriminant, factorising, the formula) are the workhorse curve; simultaneous equations, inequalities, polynomials and transformations all come back to reading or solving that same quadratic.

## Key ideas
**Laws of indices**: $a^m\times a^n=a^{m+n}$, $a^m\div a^n=a^{m-n}$, $(a^m)^n=a^{mn}$, $a^0=1$, $a^{-n}=\dfrac{1}{a^n}$, $a^{1/n}=\sqrt[n]{a}$, $a^{m/n}=(\sqrt[n]{a})^m$.

**Surds**: rationalise a denominator by multiplying by a form of 1 that clears the root, e.g. $\dfrac{1}{\sqrt a}\times\dfrac{\sqrt a}{\sqrt a}=\dfrac{\sqrt a}{a}$.

**Quadratics**: complete the square, $ax^2+bx+c=a\left(x+\dfrac{b}{2a}\right)^2+c-\dfrac{b^2}{4a}$, to read off the turning point directly. The **discriminant** $b^2-4ac$ decides the nature of the roots: $b^2-4ac>0$ gives two distinct real roots, $b^2-4ac=0$ gives equal (repeated) roots, $b^2-4ac<0$ gives no real roots.

**Polynomials**: expand and collect like terms; factorise by taking out a common factor first, then factorising what remains.

**Curve sketching**: a cubic has one, two or three real roots; it crosses the $x$-axis at a single root and touches it at a repeated root. $y=k/x$ and $y=k/x^2$ have asymptotes $x=0$ and $y=0$. An **asymptote** is a straight line that the curve approaches (gets closer and closer to) as $x$ or $y$ tends to infinity.

**Transformations of $y=f(x)$**: $y=f(x)+a$ is a translation by $\begin{pmatrix}0\\a\end{pmatrix}$ (up $a$); $y=f(x+a)$ is a translation by $\begin{pmatrix}-a\\0\end{pmatrix}$ (**left** $a$); $y=af(x)$ is a stretch parallel to the $y$-axis, scale factor $a$; $y=f(ax)$ is a stretch parallel to the $x$-axis, scale factor $\frac1a$.

![[Assets/P1/P1-1-quadratic-vertex.svg]]

## Method
1. **Solving a quadratic**: try factorising first; otherwise use $x=\dfrac{-b\pm\sqrt{b^2-4ac}}{2a}$, or complete the square.
2. **Completing the square**: take out the coefficient of $x^2$ from the $x$ terms, halve the $x$ coefficient inside the bracket, then subtract the square you added: $x^2+8x+3=(x+4)^2-16+3=(x+4)^2-13$.
3. **Simultaneous equations (linear + quadratic)**: make $y$ (or $x$) the subject of the linear equation, substitute into the quadratic, solve it, then substitute *each* root back into the linear equation to find its matching partner.
4. **Quadratic or linear inequalities**: find the critical values (the roots), sketch the graph(s), then read the $x$-range straight off the sketch — outside the roots for an upward parabola that's $>0$, between them for $<0$ (the other way round if the parabola opens downward). For a fraction such as $\dfrac{a}{x}<b$, multiply both sides by $x^2$ (always positive, so the sign stays) to get $ax<bx^2$, $x\neq0$; multiplying by $x$ would fail when $x<0$.
5. **Graphing a region**: dotted (dashed) boundary for a strict inequality, solid for $\le$ or $\ge$; shade the side of each line or curve that satisfies it, then find the overlap.

> [!example]- Worked example
> Solve the simultaneous equations $y=x+2$ and $y=x^2-4$.
> Substitute: $x+2=x^2-4\Rightarrow x^2-x-6=0\Rightarrow(x-3)(x+2)=0$, so $x=3$ or $x=-2$.
> Substitute back into $y=x+2$: $x=3\Rightarrow y=5$; $x=-2\Rightarrow y=0$.
> Solutions: $(3,5)$ and $(-2,0)$ — always pair each $x$ with its own $y$.

![[Assets/P1/P1-1-inequality-region.svg]]

## Traps
- **Trap:** dropping the minus sign, writing the discriminant as $b^2+4ac$ or the formula's numerator as $b\pm\sqrt{\ldots}$. **Why it's wrong:** both come from $-b\pm\sqrt{b^2-4ac}$, where the sign of $b$ is reversed. **Instead:** write out $a$, $b$, $c$ (with their own signs) before substituting anything.
- **Trap:** believing $\sqrt a+\sqrt b=\sqrt{a+b}$. **Why it's wrong:** a square root does not distribute over addition. **Instead:** evaluate each root separately, then add.
- **Trap:** thinking $y=f(x+a)$ shifts the graph *right*. **Why it's wrong:** replacing $x$ with $x+a$ makes every output of $f$ appear $a$ units earlier. **Instead:** $f(x+a)$ moves left by $a$; only $f(x-a)$ moves right by $a$.
- **Trap:** forgetting to reverse an inequality sign when multiplying or dividing both sides by a negative number. **Why it's wrong:** $-3x>12$ is true for $x=-5$, but $x>-4$ is not. **Instead:** reverse the sign, $x<-4$, or avoid the division by moving the $x$-term to the other side.

![[Assets/P1/P1-1-reciprocal-asymptotes.svg]]

## Exam technique
- *Show that* / *Hence*: every line of working must appear, and the *hence* step must build on the previous result rather than start a fresh method.
- *Exact*: give the answer as a surd, fraction or in terms of $\pi$ — never a rounded decimal.
- *Sketch*: label intercepts, turning points and asymptotes; for inequality regions, whether the boundary is solid or dotted carries meaning and can be marked.
- For inequalities, a quick sketch is usually faster and safer than memorised rules — especially once the leading coefficient is negative, which flips which side of the roots is the answer.

![[Assets/P1/P1-1-transformation-shift.svg]]

## Links
Builds on GCSE algebra and factorising · Leads to [[2 Coordinate geometry in the (x, y) plane]] and [[4 Differentiation]]
