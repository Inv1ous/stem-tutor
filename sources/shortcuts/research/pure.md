<!-- spec: P1 -->
## Exam working and accuracy

- **Quote the formula before the numbers.** `10/10` When a question needs a learned formula, write the symbolic equation first, then a separate substitution line; this makes a wrong sign or misplaced value visible and can preserve a method mark. Check that each substituted quantity occupies the same position as its symbol in the first line. [src: WMA12 Jan 2024 mark scheme p6]
- **Keep exact values until the last line.** `10/10` When the question asks for an exact answer or uses surds or $\pi$, carry fractions and radicals through the calculation instead of reusing rounded display values. Check the final form against the instruction: a decimal is not an exact surd answer. [src: WMA12 Jan 2024 mark scheme p6]
- **Show a mathematical step when a calculator solves it.** `9/10` For a calculator-found quadratic root or numerical answer, write the equation you solved and the substitution or factorisation that connects it to the question. Check by putting the reported root into the original equation; an unsupported calculator output may not show the method the mark scheme asks for. [src: WFM01 Jun 2024 mark scheme p8]
- **Label the requested object and units.** `8/10` On a multi-part geometry or calculus question, finish with $x=\cdots$, $A=\cdots\ \mathrm{cm}^2$, or the requested line equation rather than an unlabelled intermediate number. Check dimensions: a length scales as $L$, an area as $L^2$, and a volume as $L^3$. [src: derived]

<!-- spec: P2 -->
## 1. Algebra and functions

- **Factor out a supplied intersection.** `9/10` If a line and a quadratic meet at a known $x=a$, form their difference $D(x)$ and divide by $x-a$; the remaining linear factor gives the second intersection without a quadratic formula. Check $D(a)=0$ before dividing and substitute the second root into both original equations. [src: WMA11 Jun 2023 examiner report Q10(a)]
- **Record exclusions before clearing denominators.** `9/10` For a rational equation, list every forbidden value from the original denominators before multiplying by a common denominator; cancellation can hide an excluded root. Check each candidate against those exclusions and the original equation, especially if a factor was cancelled. [src: derived]
- **Separate a coefficient from its term.** `8/10` In a binomial question asking for the coefficient of $x^r$, calculate the multiplier of $x^r$ and report that number alone; retain the $x^r$ factor only while locating the term. Check the question's wording before the final line. [src: WMA12 Jan 2024 examiner report Q2]
- **Use the output range to prune a composite equation.** `7/10` When $f(g(x))=c$ has several algebraic candidates for $g(x)$, discard any outside the actual range of $g$ before solving for $x$. Check the domain of $f$ as well; for example, $g(x)=x^2$ cannot supply a negative intermediate value. [src: derived]

## 2. Coordinate geometry and parametrics

- **Horizontal chord from its half-length.** `8/10` For a horizontal chord of length $L$ in $(x-h)^2+(y-k)^2=r^2$, its endpoint has $|x-h|=L/2$, so $|y-k|=\sqrt{r^2-(L/2)^2}$. Choose $y=k+\cdots$ or $k-\cdots$ from the diagram, and check $L\le2r$. [src: WMA12 Jan 2024 examiner report Q3(b)]
- **Circle radius reality check.** `8/10` In $x^2+y^2+2gx+2fy+c=0$, calculate $r^2=g^2+f^2-c$ before describing a real circle or tangent. Check $r^2>0$ for a genuine circle, $r^2=0$ for one point, and $r^2<0$ for no real locus. [src: derived]
- **Parametric elimination keeps its range.** `8/10` After eliminating $t$, carry the given parameter interval into restrictions on $x$ and $y$; $x=t^2$ with $t\ge0$ gives $t=\sqrt{x}$, not both square-root signs. Check one endpoint and the direction of travel against the Cartesian curve. [src: derived]
- **Convert the gradient fully to the parameter.** `8/10` For a tangent or normal at parameter $t=u$, simplify $dy/dx$ into a function of $t$ and evaluate at $u$ before building the line. Check that the line passes through $(x(u),y(u))$ and that its gradient uses the same parameter value. [src: WFM01 Jan 2024 examiner report Q3]
- **Arc length can replace the sector angle.** `7/10` If a sector's arc length $s$ and radius $r$ are known, use $A=\tfrac12rs$ directly, since $s=r\theta$ and $A=\tfrac12r^2\theta$ for radians. Check that $s$ is the curved arc, not the chord, and that the result has square units. [src: WMA11 Jan 2024 examiner report Q8]

## 3. Trigonometry

- **Restrict the harmonic maximum to the given interval.** `8/10` After writing $a\sin x+b\cos x=R\sin(x+\alpha)$, do not automatically claim the maximum on a restricted interval is $R$. Test the interval endpoints and every in-range point with $x+\alpha=\pi/2+2\pi k$; the largest of those values is the required maximum. [src: derived]
- **Find a sinusoid from its extremes.** `8/10` If a graph or context gives maximum $M$ and minimum $m$, set amplitude $R=(M-m)/2$ and midline $d=(M+m)/2$ before finding phase or period. Check that $d+R=M$ and $d-R=m$; this avoids solving for several coefficients at once. [src: WMA12 Jan 2024 examiner report Q9(ii)]
- **Track radians through derivatives.** `7/10` Standard trig derivatives such as $d(\sin x)/dx=\cos x$ assume $x$ is measured in radians; convert degree data to radians before differentiating a trig model. Check that an angle of $180^\circ$ enters as $\pi$, while a final angle may be converted back if requested. [src: derived]

## 4. Sequences and series

- **Read the first indexed term, not the displayed multiplier.** `9/10` For $\sum_{j=p}^{\infty}aq^j$, substitute the actual starting index $p$ to get the first term before using $S_\infty=\text{first}/(1-q)$. Check the next term divided by the first equals $q$ and that $|q|<1$. [src: WMA12 Jan 2024 examiner report Q5]
- **Count gaps rather than data points.** `8/10` If a trapezium table has $m$ equally spaced ordinates, it has $m-1$ strips and width $h=(b-a)/(m-1)$. Check that the first and last $x$ values differ by exactly $(m-1)h$ before applying the weights. [src: WMA12 Jan 2024 examiner report Q4]
- **Protect the interior trapezium sum with brackets.** `8/10` Write $T=\tfrac h2[y_0+y_n+2(y_1+\cdots+y_{n-1})]$ with a visible bracket around every interior ordinate before entering it into the calculator. Check that endpoints have weight $1$ and every interior value has weight $2$. [src: WMA12 Jan 2024 examiner report Q4]
- **Delay rounding a sequence parameter.** `8/10` When an AP or GP is used in later parts, retain the exact common difference or ratio and calculate later sums from it, not from a rounded intermediate decimal. Check the first two reconstructed terms against the original data. [src: WMA12 Jan 2024 examiner report Q7]
- **Test a proposed sum by finite differences.** `7/10` If $S_n$ is claimed to sum terms $u_1,\ldots,u_n$, compute $S_n-S_{n-1}$ and see whether it simplifies to $u_n$. Also check $S_1=u_1$; these two tests detect an index shift without re-summing the series. [src: derived]

## 5. Differentiation and integration

- **Differentiate a factorised product at a root.** `8/10` If $f(x)=(x-a)g(x)$ and only the tangent gradient at $x=a$ is needed, use $f'(a)=g(a)$; all terms containing $x-a$ vanish. Check that $f(a)=0$ so the tangent passes through $(a,0)$. [src: derived]
- **Bound an area before calculating it.** `7/10` If $a<b$ and $m\le f(x)\le M$ on $[a,b]$, then $m(b-a)\le\int_a^bf(x)\,dx\le M(b-a)$; for a positive integrand this gives an instant size check. Confirm the bounds really hold throughout the interval, not just at its endpoints. [src: derived]

<!-- spec: FP1 -->
## 6. Numerical solution of equations

- **Bracket each reported decimal root.** `8/10` To justify a root rounded to $d$ decimal places, evaluate a continuous $f$ at the two half-unit rounding boundaries around the claimed value and show opposite signs. Check that the interval lies inside the required domain; a sign change justifies existence, not uniqueness unless monotonicity or another argument is supplied. [src: derived]
- **Bisection chooses a new half every row.** `8/10` After evaluating midpoint $m=(a+b)/2$, stop if $f(m)=0$; otherwise keep $[a,m]$ if $f(a)f(m)<0$ and $[m,b]$ if it is positive, assuming continuity and a sign-changing starting bracket. Check the retained interval's width halves each row and its endpoint values still have opposite signs. [src: WFM01 Jun 2023 examiner report Q7]
- **Use a calculator table as a sign map.** `7/10` If your permitted calculator has table mode, enter the original $f(x)$ and scan a stated interval for sign changes before selecting a bracket or a Newton starting value. Check any candidate using the original function, since a table can miss an even-multiplicity root or a sign change between coarse steps. [src: Casio fx-991EX User's Guide, Creating a Number Table]

## 7. Complex numbers

- **Argument needs a quadrant check.** `8/10` If $\arg z=\theta$ gives an equation using $\tan\theta=\operatorname{Im}z/\operatorname{Re}z$, filter its parameter solutions by the signs of both components. Check the point lies in the stated quadrant, because tangent alone repeats after $\pi$ and can admit the opposite ray. [src: WFM01 Jan 2024 examiner report Q9]
- **The conjugate pair is a symmetry check on a diagram.** `7/10` For non-real roots of a real polynomial, plot $a+bi$ and $a-bi$ with the same real coordinate on opposite sides of the real axis before calculating any geometry. Check their distances from any point on the real axis agree; a non-symmetric sketch indicates a sign or plotting slip. [src: WFM01 Jun 2024 mark scheme p9]

## 8. Matrices

- **Both signs of a determinant's magnitude.** `9/10` If the condition is $|\det M|=k$, with $k>0$, solve the two equations $\det M=k$ and $\det M=-k$. Check each resulting matrix against the original absolute-value condition. [src: WFM01 Jun 2023 examiner report Q4]
- **Solve a matrix product in the correct order.** `8/10` From $BC=A$ with invertible $B$, multiply on the left to get $C=B^{-1}A$; do not commute the factors. Check by multiplying $B(B^{-1}A)$ and confirming it gives $A$. [src: WFM01 Jun 2023 examiner report Q4]
- **Area scale of a composed rotation and stretch.** `8/10` If a rotation is followed by a stretch of factor $s$ parallel to one axis, the area scale is $|s|$ because the rotation has determinant $1$. Check that the stretch's other axis is unchanged and use $|s|$ even when the signed determinant is negative. [src: WFM01 Jan 2024 examiner report Q4]
- **Prove nonsingularity with a positive form.** `7/10` If a parameter-dependent $2\times2$ determinant is $k^2+2k+4$, rewrite it as $(k+1)^2+3>0$ for every real $k$, then explicitly conclude the matrix is nonsingular. Check the square term cannot be negative; this is stronger and clearer than testing a few parameter values. [src: WFM01 Jan 2024 examiner report Q1]

## 9. Proof by induction

- **Start at the specified base index.** `8/10` If a claim begins at $n=2$, verify both sides at $n=2$, then assume it at $n=k\ge2$; matching the question's stated starting value keeps the proof complete and easy to mark. Check that the final implication reaches $k+1$ and explicitly states the induction conclusion. [src: WFM01 Jan 2024 examiner report Q9]
- **Match the requested finite difference exactly.** `7/10` If asked for $S_{n+1}-S_{n-1}$, write those two indexed expressions before simplifying; it is $u_n+u_{n+1}$ when $S_n=\sum_{r=1}^n u_r$. Check with a small $n$ to catch an accidental replacement by $S_{n+1}-S_n$. [src: WFM01 Jan 2024 examiner report Q8]
