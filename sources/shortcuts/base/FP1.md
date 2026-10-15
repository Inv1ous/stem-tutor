---
tags: [stem-tutor/extra, shortcuts, edexcel-fp1]
spec: "FP1"
note: "Personal reading. Not taught or tested by the tutor. Pick the ones you like and drill them on past papers."
---
# ★ Shortcuts and Elegant Methods — FP1

> [!abstract] How to use this page
> Each entry says **when it fires**, the **shortcut**, and a **check** you can do in your head. Items marked *(beyond spec)* are not in the specification but are legal in an exam: a correct method is a correct method. Skim the headings, then try each trick on a past paper question you have already done the long way.

## Ranked index (usefulness out of 10)

> [!tip] Reading the scores
> **10** = used on a large share of papers or saves minutes every time. **8–9** = comes up regularly, clear time saver. **6–7** = worth knowing for the right question. **≤5** = situational or beyond spec. Scores are my judgement from how often each pattern appears in past papers of this syllabus; adjust to your own weak spots.

| Score     | Where                                       | Technique                                                                      |
| --------- | ------------------------------------------- | ------------------------------------------------------------------------------ |
| **10/10** | 2. Roots of quadratics, cubics and quartics | Symmetric sums: stop solving, start substituting                               |
| **10/10** | 5. Matrices                                 | Inverse of $\begin{pmatrix}a&b\\c&d\end{pmatrix}$ in one line                  |
| **10/10** | 5. Matrices                                 | Read a transformation matrix straight from the images                          |
| **10/10** | 7. Series and the method of differences     | The three results (memorise, don't derive)                                     |
| **10/10** | 7. Series and the method of differences     | Factorise before expanding                                                     |
| **10/10** | 7. Series and the method of differences     | Instant closed forms worth knowing                                             |
| **10/10** | 7. Series and the method of differences     | Method of differences recipe                                                   |
| **10/10** | 8. Proof by induction                       | Divisibility: the subtraction trick                                            |
| **9/10**  | 1. Complex numbers                          | Conjugate-pair quadratic (build in 5 seconds)                                  |
| **9/10**  | 1. Complex numbers                          | Real polynomial, one complex root $\Rightarrow$ the conjugate is a root        |
| **9/10**  | 2. Roots of quadratics, cubics and quartics | New equation from the old: substitute, don't recompute roots                   |
| **9/10**  | 3. Numerical solution of equations          | Newton–Raphson                                                                 |
| **9/10**  | 3. Numerical solution of equations          | Linear interpolation (similar triangles, one line)                             |
| **9/10**  | 5. Matrices                                 | Standard matrices (2×2)                                                        |
| **9/10**  | 5. Matrices                                 | Area scale factor $=\vert \det\mathbf M\vert$                                  |
| **9/10**  | 6. Area and geometry shortcuts              | Shoelace formula (polygons, fast)                                              |
| **9/10**  | 7. Series and the method of differences     | Range $r=a$ to $b$                                                             |
| **8/10**  | 1. Complex numbers                          | Modulus and argument of products without multiplying out                       |
| **8/10**  | 2. Roots of quadratics, cubics and quartics | Reciprocal roots in one glance                                                 |
| **8/10**  | 2. Roots of quadratics, cubics and quartics | Sum / product method (the default for "equation with roots $p,q$")             |
| **8/10**  | 2. Roots of quadratics, cubics and quartics | Cubic $ax^3+bx^2+cx+d=0$                                                       |
| **8/10**  | 2. Roots of quadratics, cubics and quartics | Quartic $ax^4+bx^3+cx^2+dx+e=0$                                                |
| **8/10**  | 2. Roots of quadratics, cubics and quartics | Two roots related ($\beta=2\alpha$, $\beta=-\alpha$, $\gamma=\alpha+\beta$...) |
| **8/10**  | 5. Matrices                                 | Composition order                                                              |
| **8/10**  | 5. Matrices                                 | Invariant points and lines                                                     |
| **8/10**  | 6. Area and geometry shortcuts              | Triangle                                                                       |
| **8/10**  | 8. Proof by induction                       | Series                                                                         |
| **8/10**  | 8. Proof by induction                       | Matrix powers                                                                  |

*Everything rated 7 or lower is tagged inline next to its entry.*

---
## 1. Complex numbers

**Conjugate-pair quadratic (build in 5 seconds).** `9/10` Real-coefficient quadratic with root $c+di$ is
$$x^2-2c\,x+(c^2+d^2)=0.$$
Root $3-2i$: $x^2-6x+13=0$. Check: sum of roots $=2c$, product $=|z|^2$.

**Never rationalise a quotient by expanding twice.** `7/10` $\dfrac{a+bi}{c+di}=\dfrac{(a+bi)(c-di)}{c^2+d^2}$. The denominator is the **modulus squared**, read it straight off. Real part $=\dfrac{ac+bd}{c^2+d^2}$, imaginary part $=\dfrac{bc-ad}{c^2+d^2}$.

**Modulus and argument of products without multiplying out.** `8/10`
$|z_1z_2|=|z_1||z_2|$, $\arg(z_1z_2)=\arg z_1+\arg z_2$, $\arg(z_1/z_2)=\arg z_1-\arg z_2$, $|z^n|=|z|^n$.
Need $|(3+4i)(5-12i)|$? $5\times13=65$. No expanding.

**Pythagorean triple spotting.** `5/10` $|a+bi|$ for $(3,4),(5,12),(8,15),(7,24),(20,21),(9,40)$ is $5,13,17,25,29,41$.

**Multiplying by $i$ rotates by $90^\circ$ anticlockwise.** `6/10` $i(a+bi)=-b+ai$: swap and negate. $-i$ rotates clockwise: $(a,b)\to(b,-a)$.

**Square root of a complex number by inspection.** `7/10` To solve $(x+iy)^2=a+bi$: $x^2-y^2=a$, $2xy=b$. Use $x^2+y^2=\sqrt{a^2+b^2}$ as a free third equation, so
$$x^2=\tfrac12\!\left(\sqrt{a^2+b^2}+a\right),\quad y^2=\tfrac12\!\left(\sqrt{a^2+b^2}-a\right),$$
and the **sign of $b$ fixes whether $x,y$ share a sign**. Example $(x+iy)^2=-5+12i$: modulus $13$, $x^2=4$, $y^2=9$, $b>0$ so $x,y$ same sign: $\pm(2+3i)$.

**Real polynomial, one complex root $\Rightarrow$ the conjugate is a root.** `9/10` A cubic with real coefficients and root $2+i$ also has $2-i$; together they give the factor $x^2-4x+5$. Divide **once** by that, never by each root separately. The third root then comes from the sum of roots ($-b/a$).

**Equal complex numbers.** `6/10` $z_1=z_2\iff$ real parts and imaginary parts match; always split into two real equations at once.

**Handy identities.** `6/10` $z+z^*=2\operatorname{Re}z$, $z-z^*=2i\operatorname{Im}z$, $zz^*=|z|^2$, $(z_1+z_2)^*=z_1^*+z_2^*$, $(z_1z_2)^*=z_1^*z_2^*$, $\left(z^n\right)^*=(z^*)^n$.

**Powers of $i$.** `6/10` $i^n$ cycles $i,-1,-i,1$ with period 4: reduce $n$ mod 4. $(1+i)^2=2i$, so $(1+i)^{4}=-4$, $(1+i)^8=16$. Likewise $(1-i)^2=-2i$.

**Exponential form (beyond spec).** `6/10` $z=re^{i\theta}$ makes powers and products one-liners: $(1+i)^{10}=(\sqrt2)^{10}e^{i10\pi/4}=32e^{i\pi/2}=32i$. De Moivre: $(\cos\theta+i\sin\theta)^n=\cos n\theta+i\sin n\theta$.

**Cube roots of unity (beyond spec).** `3/10` $1,\omega,\omega^2$ with $\omega=-\tfrac12+\tfrac{\sqrt3}{2}i$; $1+\omega+\omega^2=0$ and $\omega^3=1$.

---
## 2. Roots of quadratics, cubics and quartics

**Symmetric sums: stop solving, start substituting.** `10/10`
For $ax^2+bx+c=0$: $\alpha+\beta=-\dfrac ba$, $\alpha\beta=\dfrac ca$. Everything else is built from those two:

| Want | Use |
|---|---|
| $\alpha^2+\beta^2$ | $(\alpha+\beta)^2-2\alpha\beta$ |
| $\alpha^3+\beta^3$ | $(\alpha+\beta)^3-3\alpha\beta(\alpha+\beta)$ |
| $\alpha^4+\beta^4$ | $(\alpha^2+\beta^2)^2-2(\alpha\beta)^2$ |
| $\dfrac1\alpha+\dfrac1\beta$ | $\dfrac{\alpha+\beta}{\alpha\beta}$ |
| $\dfrac\alpha\beta+\dfrac\beta\alpha$ | $\dfrac{\alpha^2+\beta^2}{\alpha\beta}$ |
| $(\alpha-\beta)^2$ | $(\alpha+\beta)^2-4\alpha\beta=\dfrac{b^2-4ac}{a^2}$ |
| $(\alpha+k)(\beta+k)$ | $\alpha\beta+k(\alpha+\beta)+k^2$ |
| $\alpha^2\beta+\alpha\beta^2$ | $\alpha\beta(\alpha+\beta)$ |
| $\dfrac{1}{\alpha^2}+\dfrac1{\beta^2}$ | $\dfrac{(\alpha+\beta)^2-2\alpha\beta}{(\alpha\beta)^2}$ |

**New equation from the old: substitute, don't recompute roots.** `9/10` If $f(x)=0$ has roots $\alpha,\beta,\dots$ then

| New roots | Replace $x$ by | Effect on coefficients |
|---|---|---|
| $\alpha+k$ | $x-k$ | shift |
| $\alpha-k$ | $x+k$ | shift |
| $k\alpha$ | $x/k$ | $a_n\to a_n/k^{\,n}$-style scale |
| $1/\alpha$ | $1/x$ | **reverse the coefficient list** (and clear fractions) |
| $\alpha^2$ | $\sqrt x$ | isolate odd terms, square both sides |
| $-\alpha$ | $-x$ | flip sign of odd-power coefficients |
| $\alpha/(\alpha+1)$ etc. | solve $y=\dots$ for $x$, substitute | |

**Reciprocal roots in one glance.** `8/10` Roots of $ax^2+bx+c=0$ reciprocated give $cx^2+bx+a=0$. Cubic $ax^3+bx^2+cx+d$ becomes $dx^3+cx^2+bx+a$.

**Sum / product method (the default for "equation with roots $p,q$").** `8/10` Build $x^2-(p+q)x+pq=0$. Compute $p+q$ and $pq$ using the table above; never find $\alpha,\beta$ themselves.

**Cubic $ax^3+bx^2+cx+d=0$:** `8/10` $\sum\alpha=-\dfrac ba$, $\sum\alpha\beta=\dfrac ca$, $\alpha\beta\gamma=-\dfrac da$. Then
$\sum\alpha^2=(\sum\alpha)^2-2\sum\alpha\beta$;
$\sum\alpha^3-3\alpha\beta\gamma=(\sum\alpha)\big(\sum\alpha^2-\sum\alpha\beta\big)$;
$\sum\dfrac1\alpha=\dfrac{\sum\alpha\beta}{\alpha\beta\gamma}$.

**Quartic $ax^4+bx^3+cx^2+dx+e=0$:** `8/10` $\sum\alpha=-\dfrac ba$, $\sum\alpha\beta=\dfrac ca$, $\sum\alpha\beta\gamma=-\dfrac da$, $\alpha\beta\gamma\delta=\dfrac ea$. Signs alternate $-,+,-,+$: write them down before touching algebra.

**Newton's identity shortcut for power sums.** `5/10` If $\alpha$ is a root of $x^3=px^2+qx+r$, then $S_n=pS_{n-1}+qS_{n-2}+rS_{n-3}$ for $S_n=\alpha^n+\beta^n+\gamma^n$, with $S_0=3$. Use for $\sum\alpha^4$ and higher without expanding.

**Cubic with complex root.** `7/10` Given one non-real root, the conjugate is another; the third root is real and equals $-b/a-2\operatorname{Re}(\text{root})$.

**Two roots related ($\beta=2\alpha$, $\beta=-\alpha$, $\gamma=\alpha+\beta$...).** `8/10` Set the relation into the three Vieta equations: three equations, three unknowns, and the *simplest* equation is usually the one with the relation in it. For $\beta=-\alpha$: $\alpha+\beta=0$ so $\gamma=-b/a$ immediately.

---
## 3. Numerical solution of equations

**Newton–Raphson.** `9/10` $x_{n+1}=x_n-\dfrac{f(x_n)}{f'(x_n)}$. Three formulas worth memorising so you never differentiate:

| Task | Iteration |
|---|---|
| $\sqrt a$ (Heron / Babylonian) | $x_{n+1}=\tfrac12\!\left(x_n+\dfrac a{x_n}\right)$ |
| $\sqrt[3]{a}$ | $x_{n+1}=\dfrac{2x_n+a/x_n^2}{3}$ |
| $1/a$ without dividing | $x_{n+1}=x_n(2-a\,x_n)$ |
| $\sqrt[k]{a}$ | $x_{n+1}=\dfrac{(k-1)x_n+a/x_n^{\,k-1}}{k}$ |

**Where Newton fails.** `6/10` $f'(x_n)\approx0$ (stationary point near the guess) throws the next value far away; a starting value on the other side of a turning point can converge to a different root. Say so in "comment" questions.

**Linear interpolation (similar triangles, one line).** `9/10` For a sign change on $[a,b]$:
$$\text{root}\approx a+(b-a)\,\frac{|f(a)|}{|f(a)|+|f(b)|}=\frac{a|f(b)|+b|f(a)|}{|f(a)|+|f(b)|}.$$
Check: the answer is nearer the end where $|f|$ is **smaller**.

**Bisection error bound.** `5/10` After $n$ halvings of $[a,b]$ the root lies in an interval of width $\dfrac{b-a}{2^n}$ (so the midpoint is within half of that). For accuracy $\epsilon$: $n\ge\log_2\dfrac{b-a}{\epsilon}$.

**Sign-change checklist.** `6/10` Quote $f(a)$, $f(b)$ with signs and say "continuous function, sign change, so a root". Check that $f$ really is continuous (no asymptote) in the interval.

**Calculator trick for iterations.** `7/10` Type the first iterate, press `=`, then retype the formula using `Ans`. Repeat `=` until digits stop changing.

---
## 4. Coordinate systems (parabola and rectangular hyperbola)

### Parabola $y^2=4ax$
Parametric point $(at^2,\,2at)$. Focus $(a,0)$, directrix $x=-a$.

| Quantity | Result |
|---|---|
| Gradient at $t$ | $\dfrac1t$ |
| Tangent at $t$ | $ty=x+at^2$ |
| Normal at $t$ | $y+tx=2at+at^3$ |
| Chord through $t_1,t_2$ | $2x-(t_1+t_2)y+2a\,t_1t_2=0$ |
| Gradient of chord | $\dfrac{2}{t_1+t_2}$ |
| Focal chord | $t_1t_2=-1$ |
| Distance from focus to $P(t)$ | $a(1+t^2)$ |
| Length of focal chord | $a\left(t+\dfrac1t\right)^2$ |
| Tangents at $t_1,t_2$ meet at | $\big(a\,t_1t_2,\;a(t_1+t_2)\big)$ |

**Check:** the tangent at $t=0$ is $x=0$, the $y$-axis. Tangents at the ends of a focal chord meet on the directrix (since $at_1t_2=-a$) and are perpendicular.

**Normals (beyond spec).** `3/10` The normal at $t_1$ meets the parabola again at $t_2=-t_1-\dfrac2{t_1}$. If three normals pass through one point, their parameters satisfy $t_1+t_2+t_3=0$.

### Rectangular hyperbola $xy=c^2$
Parametric point $\left(ct,\dfrac ct\right)$.

| Quantity | Result |
|---|---|
| Gradient at $t$ | $-\dfrac1{t^2}$ |
| Tangent at $t$ | $x+t^2y=2ct$ |
| Normal at $t$ | $t^3x-ty=c\,(t^4-1)$ |
| Chord through $t_1,t_2$ | $x+t_1t_2\,y=c(t_1+t_2)$ |
| Gradient of chord | $-\dfrac1{t_1t_2}$ |

**Check:** tangent at $t=1$ is $x+y=2c$, correct for the point $(c,c)$.

**Tangent without calculus.** `7/10` Write the point, plug into $x\,y_1+x_1\,y=2c^2$ (polar line): for the hyperbola and $y^2=4ax$ ($y\,y_1=2a(x+x_1)$) the **tangent at $(x_1,y_1)$** comes by replacing $y^2\to y y_1$, $x\to\tfrac12(x+x_1)$, $xy\to\tfrac12(xy_1+x_1y)$.

**Chord equation by symmetry.** `6/10` The chord of $xy=c^2$ through $t_1,t_2$ and the tangent at $t$ are the same formula with $t_1=t_2=t$: $x+t^2y=2ct$.

**Area of triangle from three parametric points** `7/10` is far quicker through the shoelace formula (§6).

---
## 5. Matrices

**Inverse of $\begin{pmatrix}a&b\\c&d\end{pmatrix}$ in one line.** `10/10`
$$\frac1{ad-bc}\begin{pmatrix}d&-b\\-c&a\end{pmatrix}$$
Swap the diagonal, negate the off-diagonal, divide by the determinant. Check: $\det=0\Rightarrow$ no inverse.

**Solve $\mathbf{A}\mathbf x=\mathbf b$ for 2×2 by Cramer's rule.** `6/10` For $ax+by=e$, $cx+dy=f$:
$$x=\frac{ed-bf}{ad-bc},\qquad y=\frac{af-ec}{ad-bc}.$$

**Read a transformation matrix straight from the images.** `10/10` The first column is the image of $(1,0)$, the second the image of $(0,1)$. So "maps $(1,0)\to(3,1)$ and $(0,1)\to(-2,4)$" is $\begin{pmatrix}3&-2\\1&4\end{pmatrix}$ — no solving.

**Standard matrices (2×2).** `9/10`

| Transformation | Matrix |
|---|---|
| Rotation by $\theta$ anticlockwise about $O$ | $\begin{pmatrix}\cos\theta&-\sin\theta\\\sin\theta&\cos\theta\end{pmatrix}$ |
| Reflection in $y=(\tan\theta)x$ | $\begin{pmatrix}\cos2\theta&\sin2\theta\\\sin2\theta&-\cos2\theta\end{pmatrix}$ |
| Reflection in $x$-axis / $y$-axis | $\begin{pmatrix}1&0\\0&-1\end{pmatrix}$ / $\begin{pmatrix}-1&0\\0&1\end{pmatrix}$ |
| Reflection in $y=x$ / $y=-x$ | $\begin{pmatrix}0&1\\1&0\end{pmatrix}$ / $\begin{pmatrix}0&-1\\-1&0\end{pmatrix}$ |
| Enlargement scale $k$, centre $O$ | $k\mathbf I$ |
| Stretch factor $k$ parallel to $x$-axis | $\begin{pmatrix}k&0\\0&1\end{pmatrix}$ |
| Shear, $x$-axis invariant | $\begin{pmatrix}1&k\\0&1\end{pmatrix}$ |
| Shear, $y$-axis invariant | $\begin{pmatrix}1&0\\k&1\end{pmatrix}$ |

**Rotation checks.** `7/10` $90^\circ$ anticlockwise $=\begin{pmatrix}0&-1\\1&0\end{pmatrix}$, $180^\circ=-\mathbf I$, $270^\circ=\begin{pmatrix}0&1\\-1&0\end{pmatrix}$. A rotation matrix's inverse is its **transpose**.

**Area scale factor $=|\det\mathbf M|$.** `9/10` A negative determinant means orientation is reversed (reflection-type). $\det\mathbf M=1$ and positive: area preserved (shears, rotations).

**Determinant rules.** `7/10` $\det(\mathbf{AB})=\det\mathbf A\,\det\mathbf B$; $\det(k\mathbf A)=k^2\det\mathbf A$ (2×2), $k^3$ (3×3); $\det(\mathbf A^{-1})=1/\det\mathbf A$; $\det\mathbf A^{\mathrm T}=\det\mathbf A$.

**Inverse of a product.** `7/10` $(\mathbf{AB})^{-1}=\mathbf B^{-1}\mathbf A^{-1}$; $(\mathbf{AB})^{\mathrm T}=\mathbf B^{\mathrm T}\mathbf A^{\mathrm T}$. Order always reverses.

**Composition order.** `8/10` "$\mathbf A$ then $\mathbf B$" is the matrix $\mathbf B\mathbf A$. Write the product right-to-left, in the order the transformations act.

**Invariant points and lines.** `8/10` Invariant points: $\mathbf M\mathbf x=\mathbf x$, i.e. $(\mathbf M-\mathbf I)\mathbf x=\mathbf 0$. Invariant line through $O$, $y=mx$: apply $\mathbf M$ to $(1,m)$ and demand the result is a multiple of $(1,m)$: $\begin{pmatrix}a+bm\\c+dm\end{pmatrix}=\lambda\begin{pmatrix}1\\m\end{pmatrix}$, so $m(a+bm)=c+dm$. **Quadratic in $m$.** Lines of **invariant points** have $\lambda=1$.

**$\mathbf M^2$ for a $2\times2$ (Cayley–Hamilton, beyond spec).** `4/10` $\mathbf M^2=(\operatorname{tr}\mathbf M)\mathbf M-(\det\mathbf M)\mathbf I$. Gives $\mathbf M^2,\mathbf M^3$ without multiplying full matrices.

**Singular matrix with a parameter.** `7/10` $\det=0$ gives the parameter value directly; solve the (quadratic) equation, don't invert.

**3×3 determinant (Sarrus, if your paper uses 3×3).** `6/10` Copy columns 1 and 2 to the right; add the three downward diagonals, subtract the three upward ones.

**Three-point collinearity / area from a determinant:** `6/10` see §6.

---
## 6. Area and geometry shortcuts

**Shoelace formula (polygons, fast).** `9/10` For vertices $(x_1,y_1),\dots,(x_n,y_n)$ in order (anticlockwise gives positive, but take $|\cdot|$ anyway):
$$A=\tfrac12\left|\sum_{i=1}^{n}\left(x_iy_{i+1}-x_{i+1}y_i\right)\right|,\qquad (x_{n+1},y_{n+1})=(x_1,y_1).$$
Write the coordinates in two columns, repeat the first row at the bottom, multiply down-right, subtract down-left:

$$\begin{array}{c|c}x&y\\\hline x_1&y_1\\x_2&y_2\\x_3&y_3\\x_1&y_1\end{array}$$
**Triangle:** `8/10` $A=\tfrac12|x_1(y_2-y_3)+x_2(y_3-y_1)+x_3(y_1-y_2)|$. Collinear points give $0$.

**Triangle from two vectors.** `6/10` $A=\tfrac12|a_1b_2-a_2b_1|$ for sides $\mathbf a=(a_1,a_2)$, $\mathbf b=(b_1,b_2)$ from the same vertex.

**Area of image = $|\det\mathbf M|\times$ area of object.** `7/10` Transform the triangle's three points, or just scale: quicker.

**Midpoint / section formula.** `6/10` Point dividing $AB$ in ratio $m:n$: $\dfrac{n\mathbf a+m\mathbf b}{m+n}$.

**Distance from $(x_0,y_0)$ to $ax+by+c=0$.** `7/10` $\dfrac{|ax_0+by_0+c|}{\sqrt{a^2+b^2}}$.

**Perpendicular gradient.** `6/10` $m_1m_2=-1$; rotate $(a,b)\to(-b,a)$ for the direction vector.

---
## 7. Series and the method of differences

**The three results (memorise, don't derive).** `10/10`
$$\sum_{r=1}^n r=\frac{n(n+1)}2,\quad\sum r^2=\frac{n(n+1)(2n+1)}6,\quad\sum r^3=\left[\frac{n(n+1)}2\right]^2.$$

**Range $r=a$ to $b$:** `9/10` $\sum_{r=a}^b=\sum_{r=1}^b-\sum_{r=1}^{a-1}$. Never restart the formula.

**Factorise before expanding.** `10/10` A sum like $\sum(r^2+r)$ becomes $\dfrac{n(n+1)(2n+1)}6+\dfrac{n(n+1)}2=\dfrac{n(n+1)(n+2)}3$. **Take out $n(n+1)$, keep the rest in brackets, simplify the bracket only.** The answer is nearly always a product of linear factors; if your bracket doesn't factorise, check arithmetic.

**Instant closed forms worth knowing.** `10/10`

| Sum | Result |
|---|---|
| $\sum_{r=1}^n(2r-1)$ (odds) | $n^2$ |
| $\sum_{r=1}^n 2r$ (evens) | $n(n+1)$ |
| $\sum r(r+1)$ | $\dfrac{n(n+1)(n+2)}3$ |
| $\sum r(r+1)(r+2)$ | $\dfrac{n(n+1)(n+2)(n+3)}4$ |
| $\sum(2r-1)^2$ | $\dfrac{n(2n-1)(2n+1)}3$ |
| $\sum r(r-1)$ | $\dfrac{(n-1)n(n+1)}3$ |
| $\sum r\cdot r!$ | $(n+1)!-1$ |
| $\sum r\,2^r$ | $(n-1)2^{n+1}+2$ |
| $\sum_{r=1}^n\dfrac1{r(r+1)}$ | $1-\dfrac1{n+1}=\dfrac n{n+1}$ |
| $\sum\dfrac1{r(r+1)(r+2)}$ | $\dfrac14-\dfrac1{2(n+1)(n+2)}$ |
| $\sum\ln\dfrac{r+1}r$ | $\ln(n+1)$ |

**Method of differences recipe.** `10/10`
1. Split into partial fractions (cover-up rule): $\dfrac1{r(r+k)}=\dfrac1k\left(\dfrac1r-\dfrac1{r+k}\right)$.
2. Write the first **and** last few terms; the middle cancels.
3. For gap $k$, **$k$ terms survive at each end**: $\dfrac1k\left(1+\tfrac12+\dots+\tfrac1k-\tfrac1{n+1}-\dots-\tfrac1{n+k}\right)$.
4. Let $n\to\infty$: terms in $\frac1n$ vanish, giving the sum to infinity.

**Difference-of-squares trick for odd/even blocks.** `4/10` $(2r)^2-(2r-1)^2=4r-1$.

**Sum of an arithmetic series.** `6/10` $\dfrac n2(\text{first}+\text{last})$.

**Telescoping for polynomial differences.** `5/10` If $f(r)-f(r-1)=g(r)$ then $\sum_{r=1}^ng(r)=f(n)-f(0)$. Choose $f$ to be a cubic for $\sum r^2$-type targets.

---
## 8. Proof by induction

**Skeleton (use the same four lines every time).** `7/10`
1. **Basis:** show $n=1$ (or the stated start) is true.
2. **Assume:** true for $n=k$.
3. **Step:** show it holds for $n=k+1$ by manipulating the $k+1$ expression using the assumption.
4. **Conclude:** "True for $n=1$; if true for $n=k$ then true for $n=k+1$; so true for all positive integers $n$ by induction."

**Series.** `8/10` Add the $(k+1)$th term to the assumed $S_k$, **factorise out the common bracket**, and compare with the target $S_{k+1}$ written in advance on the side.

**Divisibility: the subtraction trick.** `10/10` For "$f(n)$ divisible by $m$":
$$f(k+1)-a\,f(k)=\text{an obvious multiple of }m,$$
where $a$ is the base of the exponential. E.g. $f(n)=7^n-1$ divisible by 6: $f(k+1)-7f(k)=7^{k+1}-1-7^{k+1}+7=6$. So $f(k+1)=7f(k)+6$.
For $f(n)=2^{3n}+13$ divisible by 7: $f(k+1)-8f(k)=13-104=-91=-7\times13$.
Mixed bases such as $a^n+b^n$: use $f(k+1)=a\,f(k)+(b-a)b^k$.

**Matrix powers.** `8/10` Guess the pattern from $\mathbf M,\mathbf M^2,\mathbf M^3$; assume $\mathbf M^k$, then $\mathbf M^{k+1}=\mathbf M\,\mathbf M^k$ (or $\mathbf M^k\mathbf M$), multiply out and match.

**Recurrences.** `7/10` State the claim for $u_n$, assume for $u_k$, substitute into $u_{k+1}=g(u_k)$.

**Inequalities.** `6/10` Show $f(k+1)-f(k)>0$ (or $\ge0$) and combine with the assumption.

---
## 9. Quick checks worth a few seconds

- **Series answers:** `6/10` substitute $n=1$ and $n=2$; they must equal the first term and first two terms.
- **Vieta:** `6/10` sum $-b/a$, product $c/a$: signs trip more marks than anything.
- **Complex:** `6/10` check $|z|^2=zz^*$.
- **Matrices:** `6/10` $\det\mathbf M$ sign tells orientation; area factor is the modulus.
- **Parabola/hyperbola:** `6/10` parameter $t=1$ gives a friendly point to test any formula.
