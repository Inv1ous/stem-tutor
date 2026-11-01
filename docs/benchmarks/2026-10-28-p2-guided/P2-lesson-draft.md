# P2 Proof: draft lesson preview

**Unpublished draft.** This preview contains answers and marking points for review. The live lesson presents material in steps and hides check answers until attempted. Question selection and lesson sequence adapt to your session. The learning AI, final source review and refine gates are not complete.

The source is the P2 draft card and the current P2 pack, with the proposed exhaustion wording correction applied for this preview. This preview is a content review, not a recording of the live interface.

## Structure of mathematical proof (P2-1.1)

### Why this matters

A convincing pattern is not yet a proof. In an exam, a marker must be able to follow why the result holds for every value covered by the question.

### Try it first

In a proof about every integer $n$, $k$ is an integer. Which expression can represent every integer $n$?
- A. $n=2k$
- B. $n=2k+1$
- C. $n=k+211$
- D. $n=k^2$

**Review key:** C. For every integer $n$, choose $k=n-211$, which is an integer. The form $2k$ misses odd integers; $2k+1$ misses even integers; $k^2$ misses negative integers.

### Helpful terms

- **Proof**: A logical argument that establishes a claim from its assumptions. Notation: none. Read aloud: proof.
- **Assumption**: A given fact or condition used as the starting point. Notation: none. Read aloud: assumption.
- **Domain**: The allowed values to which a claim applies. Notation: none. Read aloud: domain.
- **Integer**: A whole number, including zero and negative whole numbers. Notation: ℤ. Read aloud: the integers.
- **LHS and RHS**: The left-hand and right-hand sides of a statement. Notation: LHS, RHS. Read aloud: left-hand side; right-hand side.
- **Product**: The result of multiplication, not addition. For example, the product of 2 and 3 is 6. Notation: $ab$ or $a\times b$. Read aloud: a times b.

- **Factor theorem**: For a polynomial f, x − r is a factor exactly when f(r) equals zero. Notation: $f(r)=0$. Read aloud: f of r equals zero.

### In plain words

A proof explains why a claim follows from its assumptions. A few successful examples can suggest a pattern, but they do not establish a claim about every integer.

### More detail

A mathematical proof starts from stated assumptions: the given facts and the domain of allowed values. Each following line must be a logical consequence of those assumptions or an established result. The final line states precisely the conclusion required. If a line quietly adds a new assumption, the argument may prove only a narrower statement. For example, from '$n$ is an integer' you cannot write $n=2k$ without also assuming that $n$ is even. Check the chain in both directions: does each step follow, and does the final conclusion answer the original claim?

Proof by exhaustion and disproof by counterexample use this same structure. In each, the stated domain determines which cases or inputs are allowed.

### Exam language

- **Prove**: Give a complete logical argument that covers the stated domain.
- **Show that**: Establish the supplied result with sufficient working; the result itself is not the proof.
- **Hence**: Use the preceding result as directed. Check the exact question wording.
- **Hence or otherwise**: The preceding result may help, but a different valid method can earn marks.
- **Verify**: Check that the given values satisfy the stated conditions; one verification does not prove a universal claim.
- **M marks**: Method marks reward an appropriate method or substantial step, as defined by the question-specific scheme.
- **A marks**: Accuracy marks reward a correct result or step; they can depend on the associated method mark.
- **B marks**: Independent marks reward a correct result or statement without depending on a method mark. Specific award and follow-through rules come from the mark scheme.

### Diagram

Begin with the assumptions and allowed domain. Follow justified logical steps to the required conclusion.

![Begin with the assumptions and allowed domain. Follow justified logical steps to the required conclusion.](../../../build/out/Assets/P2/P2-1-proof-flow.svg)

### Worked example

Show that $n(n+1)$ is even for every integer $n$.

1. Let $n$ be an arbitrary integer. Every integer is either even or odd. The domain includes positive integers, zero and negative integers; these two cases cover it completely.
2. If $n=2k$, where $k$ is an integer, then $n(n+1)=2k(2k+1)=2[k(2k+1)]$. The bracket is an integer, so this is twice an integer and therefore even.
3. If $n=2k+1$, where $k$ is an integer, then $n(n+1)=(2k+1)(2k+2)=2[(2k+1)(k+1)]$. Again the bracket is an integer, so the product is even.
4. Therefore $n(n+1)$ is even for every integer $n$. Both possible parity cases have been proved generally. Checking sample values alone leaves infinitely many integers untested.

### Common misconception

**Wrong idea:** Several examples prove a universal claim.

**Why it is tempting:** All checked examples fit the pattern.

**Fix:** Give a general argument or a complete set of cases.

### Common misconception

**Wrong idea:** Every integer can be written as $2k$.

**Why it is tempting:** $2k$ is a familiar integer representation.

**Fix:** $2k$ represents even integers only; an arbitrary integer may be odd.

### General algebraic argument

**Possible wording:** Prove that, Show that

**Claim:** The sum of two even integers is even.

- Let the integers be $2a$ and $2b$, where $a$ and $b$ are integers.
- Their sum is $2(a+b)$.
- Since $a+b$ is an integer, the sum is even.

Two even integers can be written as $2m$ and $2n$, where $m$ and $n$ are integers. They may be equal, but need not be. Writing both as $2n$ without justification covers only equal inputs. Their product is $4mn$, a multiple of $4$.

**Try it:** Prove that the sum of two odd integers is even.

**Review answer:** Let the odd integers be 2a+1 and 2b+1. Their sum is 2(a+b+1), which is even.

**Mark points:**
- Applies a general property to both odd integers, such as independently writing 2a+1 and 2b+1, or giving both remainder 1 modulo 2. The integers may be equal.
- Shows the sum is even for arbitrary odd integers, using algebra or remainders; equal inputs alone are insufficient.


**If another try is needed:** Prove that the product of two odd integers is odd.

**Review answer:** Write the integers as $2a+1$ and $2b+1$, where $a$ and $b$ are integers. Their product is $2(2ab+a+b)+1$, which is odd.

**Mark points:**
- Represents both odd integers generally, for example as 2a + 1 and 2b + 1.
- Shows the product is twice an integer plus one and concludes it is odd.

### Identify invalid working

**Possible wording:** Explain why the argument is invalid, What is wrong with this proof?

A student starts a proof with $n=2k$ for an arbitrary integer $n$.

- This representation assumes that $n$ is even.
- Odd integers are also allowed, so the argument does not cover the whole domain.

**Try it:** A student solves $n^2=n$ for real $n$ by dividing both sides by $n$ and concludes that the only solution is $n=1$. Explain the gap.

**Review answer:** Dividing by $n$ assumes $n\ne0$. But $n=0$ also satisfies $n^2=n$ and is lost by that division.

**Mark points:**
- Identifies that division by n excludes n = 0, which also satisfies the original equation.


**If another try is needed:** A student solves $x^2=9$ over the real numbers and concludes $x=3$ is the only solution. Explain the gap.

**Review answer:** The value $x=-3$ also satisfies $x^2=9$, so the student has omitted another real solution.

**Mark points:**
- Identifies −3 as another real solution and explains that it satisfies the original equation.

### Justify division in an inequality proof

**Possible wording:** Prove that, Explain why the inequality follows

**Claim:** If $t>0$ and $tx>ty$, then $x>y$.

- The assumption $t>0$ means $t$ is positive and non-zero.
- Divide both sides by $t$; division by a positive number preserves the inequality.
- Therefore $x>y$.

**Try it:** Suppose $c<0$ and $cx<cy$. Explain why $x>y$.

**Review answer:** Since $c$ is negative and non-zero, dividing both sides by $c$ reverses the inequality, giving $x>y$.

**Mark points:**
- Identifies c as negative (which also implies it is non-zero).
- Divides by c, or multiplies by its negative reciprocal, reverses the inequality and concludes $x>y$.


**If another try is needed:** Suppose $a<0$ and $ax>ay$. Explain why $x<y$.

**Review answer:** Since $a$ is negative and nonzero, dividing both sides by $a$ reverses the inequality, giving $x<y$.

**Mark points:**
- Identifies the divisor as negative and nonzero.
- Reverses the inequality when dividing and concludes x < y.

### Geometric proof using earlier results

**Possible wording:** Prove that the circles do not meet, Using your earlier results, show that the circles are separate

**Given:** Two circles have radii $3$ and $4$ units. Their centres are $10$ units apart. If the distance between centres is greater than the sum of their radii, the circles cannot touch or intersect.

- The sum of the radii is $3+4=7$.
- The centre distance is $10$, and $10>7$.
- The given criterion applies, so the circles neither touch nor intersect.

**Try it:** Two circles have radii $2$ and $4$ units, and their centres are $9$ units apart. If the distance between centres is greater than the sum of their radii, the circles cannot touch or intersect. Use this fact to explain why these circles cannot touch or intersect.

**Review answer:** The radii sum to $2+4=6$. Since $9>6$, the distance between centres exceeds the sum of the radii, so the circles cannot touch or intersect.

**Mark points:**
- Calculates the sum of the radii as 6 units.
- States that the centre distance 9 exceeds 6, then uses the given criterion to conclude that the circles neither touch nor intersect. A conclusion without that comparison is insufficient.


**If another try is needed:** Two circles have radii $1$ and $2$ units, and their centres are $5$ units apart. If the centre distance is greater than the sum of the radii, the circles cannot touch or intersect. Use this fact to show that these circles cannot touch or intersect.

**Review answer:** The radii sum to $1+2=3$. Since $5>3$, the supplied criterion shows that the circles neither touch nor intersect.

**Mark points:**
- Calculates the sum of the radii as 3.
- Compares the distance with the sum and concludes the circles cannot touch or intersect.

### Derive a formula from a series

**Possible wording:** Prove the formula for the sum, Show that the sum to n terms is the given expression, Hence show a related sum using the preceding result

**Claim:** For an integer $n\geq3$, $1+2+\cdots+n=\frac{n(n+1)}{2}$.

- Let $S=1+2+\cdots+n$. Reverse the same sum: $S=n+(n-1)+\cdots+1$.
- Add corresponding terms. Each pair is $n+1$, and there are $n$ pairs, so $2S=n(n+1)$.
- Divide by $2$ to obtain the stated formula.
- For $n=1$ and $n=2$, the sums are $1$ and $3$ respectively, matching the formula.

**General arithmetic series:** Let $n\geq3$ be an integer, with first term $a$ and common difference $d$. The last term is $a+(n-1)d$, not $a+nd$.

- Write $S=a+(a+d)+\cdots+[a+(n-1)d]$.
- Write the same sum in reverse: $S=[a+(n-1)d]+[a+(n-2)d]+\cdots+a$.
- Add matching columns. There are $n$ pairs, each equal to $2a+(n-1)d$, so $2S=n[2a+(n-1)d]$.
- Divide by $2$: $S=\frac{n}{2}[2a+(n-1)d]$. The two-row method works for odd and even $n$; no unpaired middle term is lost.
- For $n=1$ and $n=2$, direct addition also gives the formula. The formula is derived from the terms, not assumed at the start.

**Using a previous result:** Given $1+2+\cdots+n=\frac{n(n+1)}{2}$, hence show that $3+6+\cdots+3n=\frac{3n(n+1)}{2}$.

- Each term is three times its counterpart in the given sum.
- Multiply the given result by $3$ to obtain the required sum. Here “hence” directs you to use that result.

**Try it:** Given that $1+2+\cdots+n=\frac{n(n+1)}{2}$ for positive integer $n$. Hence prove that the sum of the first $n$ positive odd integers is $n^2$.

**Review answer:** Write the sum as $2(1+2+\cdots+n)-n$. Substituting the given formula gives $n(n+1)-n=n^2$.

**Mark points:**
- Writes the odd-number sum as twice the given sum minus n.
- Uses the given formula and derives n squared.


**If another try is needed:** Given $1+2+\cdots+n=\frac{n(n+1)}{2}$ for positive integer $n$, prove that the sum of the first $n$ positive even integers is $n(n+1)$.

**Review answer:** The even-number sum is $2(1+2+\cdots+n)$. Using the given formula gives $2\times\frac{n(n+1)}{2}=n(n+1)$.

**Mark points:**
- Expresses the even-number sum as twice the given sum.
- Uses the given formula and derives n(n+1).

### Geometric-series proof by cancellation

**Possible wording:** Prove the sum of a geometric series, Show the formula and state any restriction

**Claim:** For an integer $n\geq3$, the sum $S=1+2+\cdots+2^{n-1}$ equals $2^n-1$.

- Multiply each term by $2$: $2S=2+2^2+\cdots+2^n$.
- Subtract $S$ from $2S$. The intermediate powers cancel, giving $2S-S=2^n-1$.
- Therefore $S=2^n-1$.
- For $n=1$ and $n=2$, the sums are $1$ and $3$, matching the formula.

When subtracting, keep the order consistent: $2S-S$ leaves $2^n-1$, not $1-2^n$. Show that uncancelled line before simplifying. In a general derivation, division by $1-r$ is allowed only when $r\ne1$. If $r=1$, all $n$ terms equal the first term $a$, so the sum is $na$; handle that case separately.

**Try it:** For real $a$ and $r$ with $r\ne1$, and integer $n\geq3$, prove that $a+ar+\cdots+ar^{n-1}=\frac{a(1-r^n)}{1-r}$. Show the unfactorised line after subtracting.

**Review answer:** Let $S=a+ar+\cdots+ar^{n-1}$. Multiplying gives $rS=ar+ar^2+\cdots+ar^n$. Subtracting in this order gives $S-rS=a-ar^n$. Thus $(1-r)S=a(1-r^n)$; since $r\ne1$, divide by $1-r$ to obtain the stated formula. Alternatively, subtract $S$ from $rS$: $rS-S=ar^n-a$. Since $r-1\ne0$, this gives $S=\frac{a(r^n-1)}{r-1}$, equivalent to the stated formula.

**Mark points:**
- Writes the sum and its multiple by r, aligned so that intermediate terms cancel.
- Subtracts in a consistent order and shows S − rS = a − ar^n, or its equivalent.
- Factorises and divides by the nonzero 1 − r to obtain the stated formula; accepts equivalent signs.


**If another try is needed:** A geometric series has first term $1$, ratio $4$ and sum $85$. Using $S_n=\frac{4^n-1}{3}$ for positive integer $n$, show that it has exactly $4$ terms.

**Review answer:** Substitute $S_n=85$: $85=\frac{4^n-1}{3}$, so $4^n=256=4^4$. Since powers of $4$ are strictly increasing for positive integer exponents, $n=4$.

**Mark points:**
- Uses the stated formula with working to verify the sum for n = 4, or rearranges to obtain 4^n = 256.
- Establishes n = 4 and explains why it is the only positive integer solution.

### Prove a stationary point is a maximum

**Possible wording:** Use further calculus to prove that the stationary point is a maximum, Justify the nature of the stationary point

**Given:** A twice-differentiable function $f$ has a stationary point at $x=1$ and $f\prime\prime(x)=-2$. At a stationary point, a negative second derivative establishes a local maximum.

- At $x=1$, $f\prime\prime(1)=-2<0$.
- The stated second-derivative criterion applies, so the stationary point is a local maximum.
- The sign establishes the local nature of the point; it does not alone prove a global maximum on an arbitrary domain.

**Try it:** A twice-differentiable function $g$ has a stationary point at $x=2$ and $g\prime\prime(x)=-2x-2$. At a stationary point, a negative second derivative establishes a local maximum. Prove that this stationary point is a local maximum.

**Review answer:** $g\prime\prime(2)=-6<0$. Since the point is stationary, the given criterion shows it is a local maximum.

**Mark points:**
- Substitutes x = 2 into the second derivative and obtains −6.
- Uses the negative second derivative at the stationary point to conclude it is a local maximum.


**If another try is needed:** A twice-differentiable function $h$ has a stationary point at $x=-1$ and $h\prime\prime(x)=2x+1$. At a stationary point, a negative second derivative establishes a local maximum. Prove that this stationary point is a local maximum.

**Review answer:** $h\prime\prime(-1)=-1<0$. The given criterion therefore establishes a local maximum at the stationary point.

**Mark points:**
- Substitutes x = −1 and finds a negative second derivative.
- Uses the supplied criterion to conclude a local maximum.

### Geometric proof with alternative chains of reasoning

**Diagram: geometric proof example**

In the worked geometry example, A, B and C lie on a circle. The lines AC and BC form a right angle at C, so AB is a diameter.

![Circle through A, B and C with a right angle at C](../../../build/out/Assets/P2/P2-1-geometry.svg)

**Possible wording:** Prove that a chord is a diameter, Use geometry to justify the conclusion

**Given:** Distinct points $A=(0,0)$, $B=(6,0)$ and $C=(3,3)$ lie on a circle. A chord joining two points on a circle is a diameter if the angle at a third point on the circle is a right angle.

- **Using lengths:** $AC^2=18$, $BC^2=18$ and $AB^2=36$. The converse of Pythagoras gives a right angle at $C$.
- **Alternatively, using gradients:** $AC$ has gradient $1$ and $BC$ has gradient $-1$. Their product is $-1$, so the lines are perpendicular.
- Either complete route establishes a right angle at $C$. The given circle fact then shows that $AB$ is a diameter.
- **Alternatively, using the midpoint:** $M=(3,0)$ is the midpoint of $AB$, and $MA=MB=MC=3$. The three non-collinear points have a unique circle, so $M$ is its centre; therefore $AB$ is a diameter.

**Try it:** Distinct points $A=(0,0)$, $B=(10,0)$ and $C=(8,4)$ lie on a circle. A chord joining two points on a circle is a diameter if the angle at a third point on the circle is a right angle. Prove that $AB$ is a diameter, using gradients, squared lengths, or the midpoint.

**Review answer:** $AC^2=80$, $BC^2=20$ and $AB^2=100$. By the converse of Pythagoras the angle at $C$ is a right angle, so the given circle fact makes $AB$ a diameter. Alternatively the gradients of $AC$ and $BC$ are $\frac12$ and $-2$, so the lines are perpendicular and the same conclusion follows. Alternatively, the midpoint is $M=(5,0)$ and $MA=MB=MC=5$. The non-collinear points determine a unique circle centred at $M$, so $AB$ is a diameter.

**Mark points:**
- Calculates the relevant squared lengths or gradients, or finds midpoint (5, 0) and the three equal distances.
- Justifies the right angle and applies the circle fact, or justifies that the midpoint is the circle centre, and concludes AB is a diameter.


**If another try is needed:** Distinct points $A=(0,0)$, $B=(13,0)$ and $C=(4,6)$ lie on a circle. A chord joining two points on a circle is a diameter if the angle at a third point is a right angle. Prove that $AB$ is a diameter, using gradients, squared lengths, or the midpoint.

**Review answer:** $AC^2=52$, $BC^2=117$ and $AB^2=169$, so the converse of Pythagoras gives a right angle at $C$. The supplied circle fact makes $AB$ a diameter. Alternatively the gradients are $\frac32$ and $-\frac23$, giving perpendicular lines and the same conclusion. Alternatively $M=(13/2,0)$ and $MA^2=MB^2=MC^2=169/4$. The non-collinear points determine a unique circle centred at $M$, so $AB$ is a diameter.

**Mark points:**
- Establishes a right angle using valid gradients or squared lengths, or finds the midpoint and the three equal distances.
- Uses the supplied circle fact, or justifies that the midpoint is the circle centre, and concludes AB is a diameter.

### Show a trigonometric identity

**Possible wording:** Show that the identity holds, Prove the identity on the stated domain

**Given:** $\sin^2\theta+\cos^2\theta=1$. Show that $\frac{1-\cos^2\theta}{\sin\theta}=\sin\theta$ where $\sin\theta\ne 0$.

- Work from the left-hand side. The given identity gives $1-\cos^2\theta=\sin^2\theta$.
- Since $\sin\theta\ne 0$, division gives $\frac{\sin^2\theta}{\sin\theta}=\sin\theta$.
- This is the right-hand side, so the identity holds on the stated domain.

**Try it:** Given $\sin^2\theta+\cos^2\theta=1$, show that $\frac{1-\sin^2\theta}{\cos\theta}=\cos\theta$ where $\cos\theta\ne 0$.

**Review answer:** The given identity gives $1-\sin^2\theta=\cos^2\theta$. Since $\cos\theta\ne 0$, the left-hand side becomes $\frac{\cos^2\theta}{\cos\theta}=\cos\theta$, the right-hand side.

**Mark points:**
- Uses the given identity to rewrite the numerator as cos²θ.
- Divides by cosθ using the stated domain and concludes that the left-hand side equals the right-hand side; the nonzero condition need not be repeated.


**If another try is needed:** Given $\sin^2\theta+\cos^2\theta=1$, show that $1+\frac{\sin^2\theta}{\cos^2\theta}=\frac{1}{\cos^2\theta}$ where $\cos\theta\ne0$.

**Review answer:** Write $1$ as $\frac{\cos^2\theta}{\cos^2\theta}$. The left side becomes $\frac{\cos^2\theta+\sin^2\theta}{\cos^2\theta}=\frac1{\cos^2\theta}$, as required on the stated domain.

**Mark points:**
- Combines the terms over the nonzero common denominator.
- Uses the supplied identity and reaches the right-hand side.

### In your own words

Which step of an argument would you challenge if it assumes an integer is even without saying so?

### Prove an inequality using a non-negative square

**Possible wording:** Use algebra to prove the inequality, Prove the inequality for all real values

**Claim:** For every real $x$, $x^2+1\geq2x$.

- The square $(x-1)^2$ is non-negative.
- Expand: $x^2-2x+1\geq0$.
- Add $2x$ to both sides. Thus $x^2+1\geq2x$ for every real $x$.

**Try it:** Prove that $x^2+4\geq4x$ for every real $x$.

**Review answer:** For real $x$, $(x-2)^2\geq0$. Expanding and adding $4x$ to both sides gives $x^2+4\geq4x$, as required.

**Mark points:**
- Establishes a non-negative expression equivalent to the difference between the sides, or uses another valid general argument.
- Rearranges with justified steps and concludes the stated inequality on the real domain.



**If another try is needed:** Prove that $x^2+6x+10\geq1$ for every real $x$.

**Review answer:** For real $x$, $(x+3)^2\geq0$. Expanding and adding $1$ gives $x^2+6x+10\geq1$ for all real $x$.

**Mark points:**
- Establishes a non-negative expression equivalent to the difference between the sides, or uses another valid general argument.
- Rearranges with justified steps and concludes the stated inequality on the real domain.


### Prove an inequality involving a square root

**Possible wording:** Use algebra to prove an inequality on a restricted domain, Show that the inequality holds when the square root is defined

**Claim:** For every real $x\geq0$, $x+1\geq2\sqrt{x}$.

- The stated domain makes $\sqrt{x}$ real, so $(\sqrt{x}-1)^2\geq0$.
- Expand: $x-2\sqrt{x}+1\geq0$.
- Add $2\sqrt{x}$ to both sides. Thus the claim holds on the stated domain.

**Try it:** Prove that $x+4\geq4\sqrt{x}$ for every real $x\geq0$.

**Review answer:** On the stated domain, $(\sqrt{x}-2)^2\geq0$. Expanding gives $x-4\sqrt{x}+4\geq0$. Add $4\sqrt{x}$ to both sides to obtain the claim.

**Mark points:**
- Uses a valid general argument on the stated domain, such as the non-negative square (√x − 2)².
- Obtains the required inequality with valid steps and states the conclusion; accepts other complete proofs.



**If another try is needed:** Prove that $x+9\geq6\sqrt{x}$ for every real $x\geq0$.

**Review answer:** On the stated domain, $(\sqrt{x}-3)^2\geq0$. Expanding and adding $6\sqrt{x}$ gives $x+9\geq6\sqrt{x}$, as required.

**Mark points:**
- Uses a valid general argument on the stated domain, such as the non-negative square (√x − 3)².
- Obtains the required inequality with valid steps and concludes; accepts other complete proofs.


### Show a parameter using the factor theorem

**Possible wording:** Show that the constant has the given value, Use the factor theorem to establish the stated parameter

**Given:** $f(x)=x^2+kx+2$ and $x-1$ is a factor. Show that $k=-3$. You may use the factor theorem: if $x-r$ is a factor of $f(x)$, then $f(r)=0$.

- The factor $x-1$ gives $f(1)=0$.
- Substitute: $1+k+2=0$.
- Solve to obtain $k=-3$, as required.

Exam note: A mark scheme may credit checking a supplied value, but that check alone establishes compatibility, not that the condition forces the value. Deriving the value from the given factor also establishes necessity.

**Try it:** Let $g(x)=x^2+ax-6$. Given that $x-2$ is a factor and using the factor theorem, show that $a=1$.

**Review answer:** The factor theorem gives $g(2)=0$. Substitution gives $4+2a-6=0$, so $2a=2$ and $a=1$.

**Mark points:**
- Uses the given factor to infer g(2) = 0 for the unknown parameter.
- Shows correct intermediate arithmetic and derives a = 1.


**If another try is needed:** Let $h(x)=x^2+bx+6$. Given that $x+2$ is a factor and using the factor theorem, show that $b=5$.

**Review answer:** The factor theorem gives $h(-2)=0$. Substitution gives $4-2b+6=0$, so $2b=10$ and $b=5$.

**Mark points:**
- Uses the given factor to infer h(-2) = 0 for the unknown parameter.
- Shows correct intermediate arithmetic and derives b = 5.


### Prove there are no turning points

**Possible wording:** Prove the curve has no turning points, Show that the gradient never becomes zero

**Claim:** $y=x^3+x$ has no turning points. The derivative gives the gradient.

- $dy/dx=3x^2+1$.
- Since $x^2\geq0$ for every real $x$, $3x^2+1>0$.
- The gradient is never zero. The differentiable curve has no turning points.

**Try it:** Prove that $y=x^3+3x$ has no turning points.

**Review answer:** $dy/dx=3x^2+3>0$ for every real $x$ because $x^2\geq0$. The derivative is never zero, so this differentiable curve has no turning points.

**Mark points:**
- Differentiates correctly to obtain 3x² + 3.
- Justifies that the derivative is positive for all real x and concludes there are no turning points.


**If another try is needed:** Prove that $y=2x^3+x$ has no turning points.

**Review answer:** $dy/dx=6x^2+1>0$ for every real $x$, so the differentiable curve has no turning points.

**Mark points:**
- Differentiates correctly to obtain 6x² + 1.
- Justifies positivity for every real x and concludes there are no turning points.


### Show a relation from an arithmetic sequence

**Possible wording:** Show the stated relation using consecutive arithmetic-sequence terms, Use equal differences to derive the given equation

**Given:** $t$, $2t+1$, $5t-2$ are consecutive terms of an arithmetic sequence. Show that $2t=4$.

- Consecutive differences are equal: $(2t+1)-t=(5t-2)-(2t+1)$.
- Simplify to $t+1=3t-3$.
- Rearrange to obtain $2t=4$, as required.

**Try it:** The terms $p$, $3p-1$, $4p+2$ are consecutive terms of an arithmetic sequence. Show that $p=4$.

**Review answer:** Equal differences give $(3p-1)-p=(4p+2)-(3p-1)$, so $2p-1=p+3$. Hence $p=4$.

**Mark points:**
- Equates the consecutive differences: 2p − 1 = p + 3.
- Rearranges correctly and concludes p = 4.


**If another try is needed:** The terms $q$, $2q+1$, $5q$ are consecutive terms of an arithmetic sequence. Show that $q=1$.

**Review answer:** Equal differences give $q+1=3q-1$, so $2q=2$ and $q=1$.

**Mark points:**
- Equates consecutive differences: q + 1 = 3q − 1.
- Rearranges correctly and concludes q = 1.


### Derive a trigonometric relation from a sequence

**Possible wording:** Show the stated trigonometric relation from consecutive arithmetic-sequence terms, Use equal differences to establish the relation

**Given:** $\sin\theta$, $\cos\theta$ and $2\sin\theta$ are consecutive terms of an arithmetic sequence. Show that $2\cos\theta=3\sin\theta$.

- Equal consecutive differences give $\cos\theta-\sin\theta=2\sin\theta-\cos\theta$.
- Add $\cos\theta$ and $\sin\theta$ to both sides. This gives $2\cos\theta=3\sin\theta$, as required.
- This relation follows from the sequence condition; it is not an identity for every angle.

**Try it:** The terms $\sin\alpha$, $\cos\alpha$ and $3\sin\alpha$ are consecutive terms of an arithmetic sequence. Show that $2\cos\alpha=4\sin\alpha$.

**Review answer:** Equal differences give $\cos\alpha-\sin\alpha=3\sin\alpha-\cos\alpha$. Rearranging yields $2\cos\alpha=4\sin\alpha$.

**Mark points:**
- Sets the consecutive differences equal: cos α − sin α = 3 sin α − cos α.
- Rearranges correctly to obtain 2 cos α = 4 sin α and states the conclusion.



**If another try is needed:** The terms $\cos\beta$, $\sin\beta$ and $3\cos\beta$ are consecutive terms of an arithmetic sequence. Show that $2\sin\beta=4\cos\beta$.

**Review answer:** Equal differences give $\sin\beta-\cos\beta=3\cos\beta-\sin\beta$. Rearranging yields $2\sin\beta=4\cos\beta$.

**Mark points:**
- Sets the consecutive differences equal: sin β − cos β = 3 cos β − sin β.
- Rearranges correctly to obtain 2 sin β = 4 cos β and states the conclusion.



### Derive a relation using reciprocal tangent

**Possible wording:** Use consecutive arithmetic-sequence terms to show a trigonometric relation, Rewrite reciprocal tangent and establish the stated equation

**Given:** $\sin\theta$, $1/\tan\theta$ and $3\sin\theta$ are consecutive terms of an arithmetic sequence, where $\sin\theta\ne0$ and $\cos\theta\ne0$. Show that $2\cos\theta=4\sin^2\theta$.

- Equal differences give $1/\tan\theta-\sin\theta=3\sin\theta-1/\tan\theta$.
- Rearrange: $2/\tan\theta=4\sin\theta$.
- Because both sine and cosine are nonzero, $1/\tan\theta=\cos\theta/\sin\theta$. Multiply by $\sin\theta$ to obtain $2\cos\theta=4\sin^2\theta$.
- The conclusion follows for angles satisfying the stated conditions and sequence condition; it is not an identity for every angle.

**Try it:** The terms $2\sin\alpha$, $1/\tan\alpha$ and $4\sin\alpha$ are consecutive terms of an arithmetic sequence. Given $\sin\alpha\ne0$ and $\cos\alpha\ne0$, show that $2\cos\alpha=6\sin^2\alpha$.

**Review answer:** Equal differences imply $1/\tan\alpha-2\sin\alpha=4\sin\alpha-1/\tan\alpha$, so $2/\tan\alpha=6\sin\alpha$. Substitute $1/\tan\alpha=\cos\alpha/\sin\alpha$ and multiply by $\sin\alpha$, which is nonzero, to obtain $2\cos\alpha=6\sin^2\alpha$.

**Mark points:**
- Equates consecutive differences and obtains 2/tan α = 6 sin α.
- Rewrites reciprocal tangent as cos α / sin α and obtains 2 cos α = 6 sin² α with valid steps.



**If another try is needed:** The terms $\sin\beta$, $1/\tan\beta$ and $4\sin\beta$ are consecutive terms of an arithmetic sequence. Given $\sin\beta\ne0$ and $\cos\beta\ne0$, show that $2\cos\beta=5\sin^2\beta$.

**Review answer:** Equal differences give $2/\tan\beta=5\sin\beta$. Since $1/\tan\beta=\cos\beta/\sin\beta$ and $\sin\beta\ne0$, multiplying by $\sin\beta$ yields $2\cos\beta=5\sin^2\beta$.

**Mark points:**
- Equates consecutive differences and obtains 2/tan β = 5 sin β.
- Rewrites reciprocal tangent and obtains 2 cos β = 5 sin² β with valid steps.

### Saved lesson note

- Start with the assumptions and the allowed domain.
- Justify each logical step.
- End with the exact conclusion claimed.

### Show an approximation from binomial expansions

**Possible wording:** Show an approximation, Use expansions to find constants

**Given:** Ignore terms of degree $4$ and above. Show that $(1+x)^4+(1-x)^4$ is approximately $2+12x^2$.

- Expand to cubic terms: $1+4x+6x^2+4x^3$ and $1-4x+6x^2-4x^3$.
- Adding cancels odd powers and gives $2+12x^2$. The discarded $2x^4$ explains why this is an approximation.

**Try it:** Ignoring terms of degree $4$ and above, show that $(1+x)^5+(1-x)^5$ is approximately $2+20x^2$. Show the relevant expansions.

**Review answer:** The expansions through cubic terms are $1+5x+10x^2+10x^3$ and $1-5x+10x^2-10x^3$. Adding gives $2+20x^2$ after discarding terms of degree $4$ and above.

**Mark points:**
- Expands both expressions consistently through cubic terms, with opposite odd-power signs.
- Adds the expansions correctly and gives the stated approximation; cancellation may be shown by the sum without an explicit statement.

**If another try is needed:** Show exactly that $(2+x)^3+(2-x)^3=16+12x^2$ by expanding both expressions.

**Review answer:** The expansions are $8+12x+6x^2+x^3$ and $8-12x+6x^2-x^3$. Adding gives $16+12x^2$ exactly.

**Mark points:**
- Expands the two cubes with opposite signs on the odd terms.
- Adds the expansions and establishes the exact result.

### Transform a trigonometric equation

**Possible wording:** Show that an equation can be written as, Use trigonometric identities

**Given:** $\cos\theta\ne0$ and $\sin\theta\tan\theta=1-\cos\theta$. Show that $\cos\theta=1$.

- Replace tangent by $\sin\theta/\cos\theta$ and multiply by the nonzero cosine.
- This gives $\sin^2\theta=\cos\theta-\cos^2\theta$.
- Substitute $\sin^2\theta=1-\cos^2\theta$ and simplify to $\cos\theta=1$. The original domain is retained.

**Try it:** Given $\cos\theta\ne0$ and $\cos\theta+1=2\sin\theta\tan\theta$, show that $3\cos^2\theta+\cos\theta-2=0$. Show both identities used.

**Review answer:** Replace $\tan\theta$ with $\sin\theta/\cos\theta$ and multiply by $\cos\theta$: $\cos^2\theta+\cos\theta=2\sin^2\theta$. Substituting $\sin^2\theta=1-\cos^2\theta$ and rearranging yields the stated equation.

**Mark points:**
- Uses the tangent identity and multiplies by the given nonzero cosine.
- Uses the Pythagorean identity and shows a correct rearrangement.

**If another try is needed:** Given $\cos\theta\ne0$ and $\cos\theta-1=3\sin\theta\tan\theta$, show that $4\cos^2\theta-\cos\theta-3=0$.

**Review answer:** Multiplying $\cos\theta-1=3\sin^2\theta/\cos\theta$ by nonzero $\cos\theta$ gives $\cos^2\theta-\cos\theta=3\sin^2\theta$. Replace $\sin^2\theta$ by $1-\cos^2\theta$ and rearrange.

**Mark points:**
- Uses the tangent identity and the nonzero cosine to remove the denominator.
- Uses the Pythagorean identity and obtains the stated equation.

### Show a stated definite integral

**Possible wording:** Show that the integral has the stated value, Evaluate and justify

**Show:** $\int_0^2 (x-1)\,dx=0$.

- An antiderivative is $F(x)=x^2/2-x$.
- Substitute both limits: $F(2)-F(0)=(2-2)-0=0$.
- Brackets make the subtraction at the lower limit clear.

**Try it:** Show that $\int_1^3 (2x-4)\,dx=0$, writing the antiderivative and both substituted values.

**Review answer:** An antiderivative is $F(x)=x^2-4x$. Thus $F(3)-F(1)=(9-12)-(1-4)=-3-(-3)=0$.

**Mark points:**
- Finds a correct antiderivative.
- Substitutes both limits, subtracts correctly and establishes the given value.

**If another try is needed:** Show that $\int_0^2 (3x^2-4x)\,dx=0$, writing the antiderivative and both substituted values.

**Review answer:** An antiderivative is $F(x)=x^3-2x^2$. Then $F(2)-F(0)=(8-8)-0=0$.

**Mark points:**
- Finds a correct antiderivative.
- Substitutes both limits and subtracts to obtain the stated value.

### Show a quadratic from a contextual arithmetic series

**Common wordings:** Show that the number of rows satisfies the given quadratic; Hence find the number of rows

**Example:** The first row has 5 seats, each next row has 3 more, and there are 185 seats in total. Show that $3n^2+7n-370=0$, where $n$ is the number of rows. Hence find $n$.

- Use $S_n=\frac{n}{2}[2a+(n-1)d]$ with $a=5$ and $d=3$.
- $185=\frac{n}{2}[10+3(n-1)]=\frac{n}{2}(3n+7)$.
- Multiply by 2 and rearrange to obtain $3n^2+7n-370=0$.
- Factor as $(n-10)(3n+37)=0$. A row count must be positive, so $n=10$.

**Try it:** A hall has 4 seats in its first row and 2 more seats in each subsequent row. There are 154 seats altogether. Show that $n^2+3n-154=0$, where $n$ is the number of rows. Hence find $n$.

**Review answer:** $154=\frac{n}{2}[8+2(n-1)]=n(n+3)$. Rearranging gives $n^2+3n-154=0$. Factoring gives $(n-11)(n+14)=0$; the positive row count is $n=11$.

**Review mark points:**

- Uses a correct arithmetic-series sum with first term 4, common difference 2 and total 154.
- Shows a correct intermediate equation and rearranges to the stated quadratic.
- Finds n=11 and selects the positive value for the number of rows.

**If another try is needed:** A hall has 3 seats in its first row and 4 more seats in each subsequent row. There are 171 seats altogether. Show that $2n^2+n-171=0$, where $n$ is the number of rows. Hence find $n$.

**Review answer:** $171=\frac{n}{2}[6+4(n-1)]=n(2n+1)$. Rearranging gives $2n^2+n-171=0$. Factoring gives $(n-9)(2n+19)=0$; the positive row count is $n=9$.

**Retry mark points:**

- Uses a correct arithmetic-series sum with first term 3, common difference 4 and total 171.
- Shows a correct intermediate equation and rearranges to the stated quadratic.
- Finds n=9 and selects the positive value for the number of rows.

### Show a radius-line equation from a tangent

**Possible wording:** Show the equation of the radius line through the point of tangency; Use perpendicular gradients to show the given line equation

**Example:** A circle has centre $(1,2)$, and its tangent at $P$ has gradient $\frac{3}{2}$. Show that the line through the centre and $P$ is $2x+3y-8=0$.

- A radius to the point of tangency is perpendicular to the tangent, so its gradient is $-\frac{2}{3}$.
- Through $(1,2)$, $y-2=-\frac{2}{3}(x-1)$.
- Multiply by 3 and rearrange: $3y-6=-2x+2$, so $2x+3y-8=0$.

**Try it:** A circle has centre $(2,1)$, and its tangent at $P$ has gradient $\frac{4}{3}$. Show that the radius line through the centre and $P$ is $3x+4y-10=0$, giving a reason for its gradient.

**Review answer:** The radius and tangent are perpendicular, so the radius has gradient $-\frac{3}{4}$. Through $(2,1)$, $y-1=-\frac{3}{4}(x-2)$; hence $4y-4=-3x+6$ and $3x+4y-10=0$.

**Mark points:**
- Uses perpendicularity to find the radius gradient -3/4.
- Uses the centre (2,1) in a correct line equation.
- Shows valid intermediate algebra and obtains the stated line equation.

**If another try is needed:** A circle has centre $(-1,3)$, and its tangent at $P$ has gradient $\frac{2}{5}$. Show that the radius line through the centre and $P$ is $5x+2y-1=0$, giving a reason for its gradient.

**Review answer:** The radius and tangent are perpendicular, so the radius has gradient $-\frac{5}{2}$. Through $(-1,3)$, $y-3=-\frac{5}{2}(x+1)$; hence $2y-6=-5x-5$ and $5x+2y-1=0$.

**Mark points:**
- Uses perpendicularity to find the radius gradient -5/2.
- Uses the centre (-1,3) in a correct line equation.
- Shows valid intermediate algebra and obtains the stated line equation.

### Show surface area from a volume constraint

**Possible wording:** Use the volume constraint to show an area formula; Derive the open-box area in terms of x

**Example:** An open box has a square base of side $x$ m, height $h$ m and volume $8\,\mathrm{m}^3$, where $x>0$. Use volume = base area × height, and add the base and four side faces. Show that $S=x^2+32/x\,\mathrm{m}^2$. There is no lid.

- The volume gives $x^2h=8$, so $h=8/x^2$.
- The base and four walls give $S=x^2+4xh$.
- Substitution gives $S=x^2+32/x$.

**Try it:** An open box has base $x$ by $3x$ m and volume $6\,\mathrm{m}^3$, where $x>0$. Use volume = base area × height and add the base and four side faces. Show that its surface area is $3x^2+16/x\,\mathrm{m}^2$.

**Review answer:** With height $h$, $3x^2h=6$, so $h=2/x^2$. Adding the base and four walls gives $S=3x^2+2xh+6xh=3x^2+16/x$.

**Mark points:**
- Uses the volume relation to find or substitute the height.
- Includes the base and all four side faces with correct areas.
- Substitutes correctly and derives the stated area for positive x.

**If another try is needed:** An open box has base $x$ by $2x$ m and volume $12\,\mathrm{m}^3$, where $x>0$. Use volume = base area × height and add the base and four side faces. Show that its surface area is $2x^2+36/x$ m².

**Review answer:** With height $h$, $2x^2h=12$, so $h=6/x^2$. The base and four walls give $S=2x^2+2xh+4xh=2x^2+36/x$.

**Mark points:**
- Uses the volume relation to find or substitute the height.
- Includes the base and all four side faces with correct areas.
- Substitutes correctly and derives the stated area for positive x.

A square base is surrounded by four rectangular side faces, one on each side; there is no lid. The net is schematic, not to scale.

![A square base is surrounded by four rectangular side faces, one on each side; there is no lid. The net is schematic, not to scale.](../../../build/out/Assets/P2/P2-1-open-box-net.svg)

### Show an exponential intersection using index laws

**Possible wording:** Show the exact intersection using logarithms; Equate exponential functions and justify each algebraic step

**Example:** Show that $y=8^{1-x}$ and $y=2\cdot4^x$ meet at $x=\log(4)/\log(32)$. At an intersection the $y$ values agree. For positive bases, $a^{u+v}=a^ua^v$ and $\log(a^u)=u\log(a)$.

- Equate: $8/8^x=2\cdot4^x$.
- Multiply by $8^x$ and divide by 2: $4=32^x$.
- Taking logarithms gives $x=\log(4)/\log(32)=2/5$.

**Try it:** Show that $y=9^{1-x}$ and $y=3\cdot3^x$ meet at $x=1/3$. At an intersection the y values agree; for positive bases $a^{u+v}=a^ua^v$.

**Review answer:** Equating gives $9/9^x=3\cdot3^x$, so $3=27^x$. Equating powers of 3 gives $x=1/3$; logarithms give the same result.

**Mark points:**
- Equates the two functions and applies index laws correctly.
- Solves the resulting exponential equation by logarithms or a valid common-base argument.
- Shows valid intermediate working and the stated exact result.

**If another try is needed:** Show that $y=10^{1-x}$ and $y=2\cdot5^x$ meet at $x=\log(5)/\log(50)$. At an intersection the y values agree; use $a^{u+v}=a^ua^v$ and $\log(a^u)=u\log(a)$ for positive bases.

**Review answer:** Equating and rearranging gives $5=50^x$. Taking logarithms gives $x=\log(5)/\log(50)$.

**Mark points:**
- Equates the two functions and applies index laws correctly.
- Solves the resulting exponential equation by logarithms or a valid common-base argument.
- Shows valid intermediate working and the stated exact result.

### Prove no turning points using a quadratic gradient

**Possible wording:** Prove a curve has no turning points using a negative discriminant; Show a quadratic gradient is positive for every real input

**Useful facts:** For real $x$, $(x-h)^2\geq0$. A quadratic $ax^2+bx+c$ with $b^2-4ac<0$ has no real roots. A differentiable curve on the real line can turn only at a point where its derivative is zero. The converse is not guaranteed: a zero derivative need not be a turning point.

**Example:** A differentiable curve has gradient $3x^2-6x+5$. Prove it has no turning points.

- Completing the square gives $3(x-1)^2+2>0$ for every real $x$, so the gradient is never zero.
- Alternatively, the gradient equation has discriminant $(-6)^2-4(3)(5)=-24<0$, so it has no real solution.
- In either route the gradient is never zero. The curve therefore has no turning points.

**Try it:** The differentiable curve $y=x^3-3x^2+4x$ has derivative $3x^2-6x+4$. Prove it has no turning points for real $x$. You may use the facts stated in the example.

**Review answer:** $3x^2-6x+4=3(x-1)^2+1>0$ for every real $x$, so its derivative has no real zero and the curve has no turning points. Alternatively, the derivative quadratic has discriminant $(-6)^2-4(3)(4)=-12<0$; it has no real zero, so there are no turning points. Alternatively, $y=(x-1)^3+x+1$ is strictly increasing, being the sum of strictly increasing functions, so it has no turning points.

**Mark points:**
- Establishes a valid global method: the derivative has no real zero, or the curve is strictly monotonic on the real line.
- Justifies the method and concludes that the curve has no turning points.

**If another try is needed:** The differentiable curve $y=2x^3-6x^2+7x$ has derivative $6x^2-12x+7$. Prove it has no turning points for real $x$. You may use the facts stated in the example.

**Review answer:** $6x^2-12x+7=6(x-1)^2+1>0$ for every real $x$, so its derivative has no real zero and the curve has no turning points. Alternatively, the derivative quadratic has discriminant $(-12)^2-4(6)(7)=-24<0$; it has no real zero, so there are no turning points. Alternatively, $y=2(x-1)^3+x+2$ is strictly increasing, being the sum of strictly increasing functions, so it has no turning points.

**Mark points:**
- Establishes a valid global method: the derivative has no real zero, or the curve is strictly monotonic on the real line.
- Justifies the method and concludes that the curve has no turning points.

## Proof by exhaustion (P2-1.2)

### Why this matters

When only finitely many possibilities are allowed, a complete list can be a rigorous proof. The hard part is showing that the list really is complete.

### Try it first

If $x,y\in\{1,7,9\}$ and swapping them does not change the result, which pair is easy to omit?
- A. $(9,9)$
- B. $(1,8)$
- C. $(8,8)$
- D. $(0,7)$

**Review key:** A. Equal-value pairs are allowed; the other pairs contain values outside the domain.

### Helpful terms

- **Proof by exhaustion**: An argument that checks or proves a claim for every case in a complete set. Notation: none. Read aloud: proof by exhaustion.
- **Divisible by**: For integers a and b with a nonzero, a divides b when b divided by a is an integer. Notation: $a \mid b$. Read aloud: a divides b.
- **Residue class**: Integers grouped by their remainder on division by a fixed positive integer. Notation: $n=3k+r$. Read aloud: n equals three k plus r.
- **Product**: The result of multiplication, not addition. For example, the product of 2 and 3 is 6. Notation: $ab$ or $a\times b$. Read aloud: a times b.

### In plain words

Exhaustion divides the allowed possibilities into cases, then proves the claim in every case. The cases must cover the whole domain. A finite number of cases can also cover infinitely many numbers. For all integers, use two cases: even $n=2k$ and odd $n=2k+1$, where $k$ is any integer. Together they include negative integers and zero. Covering the domain is only the start: establish the claim separately in both cases.

### More detail

Proof by exhaustion means covering all possible cases. First establish a finite, complete list of cases from the assumptions. A case can be a single value or a class containing infinitely many values; prove the conclusion for every value in each case. For positive odd integers less than 7, the only values are $1,3,5$. If both $x$ and $y$ may take these values, the unordered pairs are $(1,1),(1,3),(1,5),(3,3),(3,5),(5,5)$. For the claim that $x+y$ is divisible by 2, their sums are $2,4,6,6,8,10$, all even. Swapping a pair gives the same sum, so unordered pairs suffice here. If the question merely says 'odd integers less than 7', negative odd integers are also allowed and this three-value list is incomplete.

Exhaustion depends on proof structure: the initial assumptions justify the case list, and the final conclusion follows only after every case is checked.

### Diagram

Every integer is either even or odd. Prove the claim separately in each case; together they cover all integers.

![Every integer is either even or odd. Prove the claim separately in each case; together they cover all integers.](../../../build/out/Assets/P2/P2-1-parity-cases.svg)

### Worked example

Prove by exhaustion that $x+y$ is divisible by 2 when $x,y$ are positive odd integers less than 7.

1. List the complete possibilities: $x,y\in\{1,3,5\}$. Here the domain is finite, so listing its values gives a complete set of cases.
2. Up to swapping, list $(1,1),(1,3),(1,5),(3,3),(3,5),(5,5)$. The sum is unchanged by swapping, but equal-value pairs still count.
3. Their sums are $2,4,6,6,8,10$, all divisible by 2. Checking every permitted pair establishes the universal conclusion for this domain.

### Common misconception

**Wrong idea:** Exhaustion always requires a finite domain.

**Why it is tempting:** A first example lists a finite set of numbers.

**Fix:** Finitely many exhaustive classes can cover an infinite domain; prove the result for every member of each class.

### Common misconception

**Wrong idea:** Some convenient cases are enough.

**Why it is tempting:** They all satisfy the claim.

**Fix:** Justify that the cases cover every allowed input and handle each case.

### Common misconception

**Wrong idea:** Checking only pairs of different values covers every pair.

**Why it is tempting:** Swapping the order does not make a new case, so equal pairs can be overlooked too.

**Fix:** Include equal-value pairs unless the question excludes them. For positive odd integers below 7, $(3,3)$ is allowed.

### Finite enumeration

**Possible wording:** Prove by exhaustion, Consider all possible values

**Claim:** $n(n+1)$ is even for integers $n$ from $1$ to $3$ inclusive.

- The allowed values are $1$, $2$ and $3$.
- The products are $2$, $6$ and $12$ respectively.
- All three products are even, and the list covers every allowed value.

**Try it:** For integer $n$ with $0 \leq n \leq 2$, prove by exhaustion that $n^2 \leq 4$.

**Review answer:** The allowed values are 0, 1 and 2, giving squares 0, 1 and 4. Each square is at most 4.

**Mark points:**
- Lists all allowed cases 0, 1 and 2.
- Calculates squares 0, 1 and 4 and concludes each is at most 4.


**If another try is needed:** For integer $n$ with $0 \leq n \leq 3$, prove by exhaustion that $n^2 \geq n$.

**Review answer:** The allowed values are 0, 1, 2 and 3. Their squares are 0, 1, 4 and 9, respectively; each square is at least its original value.

**Mark points:**
- Lists or accounts for all four cases 0, 1, 2 and 3.
- Checks each square against its original value and concludes the inequality holds.

### Exhaustion with constrained positive integers

**Possible wording:** List all possible pairs, Prove the product has the stated property

**Claim:** Positive integers $a$ and $b$ satisfy $a\leq b$ and $a+b=4$. Their product is at most 4.

- The complete allowed pairs are $(1,3)$ and $(2,2)$. Positivity excludes zero, and the inequality excludes swapped duplicates.
- Their products are $3$ and $4$. Both are at most $4$, so the claim holds for all allowed pairs.

**Try it:** Positive integers $a$ and $b$ satisfy $a\leq b$ and their sum is $5$. Prove by exhaustion that their product is even.

**Review answer:** The allowed pairs are $(1,4)$ and $(2,3)$. Their products are $4$ and $6$, both even. These are all the allowed pairs, so the product is always even.

**Mark points:**
- Lists or accounts for both allowed pairs without out-of-domain values.
- Checks the products and concludes both are even.



**If another try is needed:** Positive integers $a$ and $b$ satisfy $a\leq b$ and their sum is $6$. Prove by exhaustion that their product is at most $9$.

**Review answer:** The allowed pairs are $(1,5)$, $(2,4)$ and $(3,3)$. Their products are $5$, $8$ and $9$, all at most $9$. The complete list proves the claim.

**Mark points:**
- Lists or accounts for all three allowed pairs.
- Checks the products and concludes all are at most 9.


### Exhaustion with two simultaneous constraints

**Possible wording:** List every permitted triple, Use both equations to prove the product is even

**Claim:** Positive integers $a,b,c$ satisfy $a+b+c=9$ and $c=b+1$. Their product is even.

- Substitute $c=b+1$ into the sum to get $a=8-2b$. Positivity permits $b=1,2,3$ only.
- The complete triples $(a,b,c)$ are $(6,1,2)$, $(4,2,3)$ and $(2,3,4)$.
- Their products are $12$, $24$ and $24$, all even. Every allowed triple is covered, so the claim holds.

Label each variable in your case list and check every row against every restriction. Exclude out-of-domain rows, check the calculations for the remaining cases, and state that every allowed case is covered.

**Try it:** Positive integers $a,b,c$ satisfy $a+b+c=11$ and $c=b+1$. Prove by exhaustion that their product is even.

**Review answer:** Substitution gives $a=10-2b$, so positivity allows $b=1,2,3,4$. The complete triples $(a,b,c)$ are $(8,1,2)$, $(6,2,3)$, $(4,3,4)$ and $(2,4,5)$. Their products are $16,36,48,40$, all even. Therefore the claim holds for every allowed triple.

**Mark points:**
- Uses both constraints and positivity to list or establish all four allowed triples.
- Checks the four products and concludes that all are even.



**If another try is needed:** Positive integers $a,b,c$ satisfy $a+b+c=7$ and $c=b+1$. Prove by exhaustion that their product is even.

**Review answer:** Substitution gives $a=6-2b$, so positivity allows only $b=1,2$. The allowed triples are $(4,1,2)$ and $(2,2,3)$; their products are $8$ and $12$, both even. The claim holds for all allowed triples.

**Mark points:**
- Uses both constraints and positivity to list or establish both allowed triples.
- Checks the products and concludes both are even.


### Finite classes covering an infinite domain

**Possible wording:** Consider even and odd cases, Prove by considering all possible remainders

**Claim:** $n(n+1)$ is even for every integer $n$.

- If $n=2k$, then $n(n+1)=2k(2k+1)$, which is even.
- If $n=2k+1$, then $n(n+1)=(2k+1)2(k+1)$, which is even.
- Every integer is even or odd, so these cases cover the whole domain.

**Try it:** For any integer $n$, show by parity cases that $n^3$ and $n$ have the same parity.

**Review answer:** If $n=2k$, then $n^3=2(4k^3)$ is even. If $n=2k+1$, then $n^3=2(4k^3+6k^2+3k)+1$ is odd. These cases cover all integers.

**Mark points:**
- Covers general even and odd cases.
- Shows the cube has matching parity in each case and concludes.



**If another try is needed:** For any integer $n$, show by parity cases that $n^4$ and $n$ have the same parity.

**Review answer:** If $n=2k$, then $n^4=2(8k^4)$ is even. If $n=2k+1$, then $n^4=2(8k^4+16k^3+12k^2+4k)+1$ is odd. These cases cover all integers.

**Mark points:**
- Covers general even and odd cases.
- Shows the fourth power has matching parity in each case and concludes.



### Complete a partially written proof

**Possible wording:** Complete this proof, The first case is shown; finish the remaining cases

**Claim:** When an integer is divided by $3$, its square has remainder $0$ or $1$.

The given proof has already shown the case $n=3k$, where the remainder is $0$. Keep the supplied division into three cases and complete the two missing ones.

- If $n=3k+1$, then $n^2=3(3k^2+2k)+1$, so its remainder is $1$.
- If $n=3k+2$, then $n^2=3(3k^2+4k+1)+1$, so its remainder is $1$.
- Together with the given case, these cover every integer; every square has remainder $0$ or $1$.

**Try it:** A proof that $n(n-1)$ is even has already covered $n=2k$. Complete it for the remaining parity case and state why the proof is complete.

**Review answer:** For $n=2k+1$, $n(n-1)=(2k+1)2k$, which is even. Every integer is even or odd, so both cases are covered.

**Mark points:**
- Consider the odd case using a general odd integer.
- Show that the product has a factor of 2 and conclude both parity cases cover every integer.


**If another try is needed:** A proof that $n^2+2n$ has remainder 0 or 3 when divided by 4 for every integer $n$ has already covered the odd case. Complete the even case and state why the proof is complete.

**Review answer:** If $n=2k$, then $n^2+2n=4k^2+4k=4(k^2+k)$, which has remainder 0 modulo 4. Together with the given odd case, this covers every integer.

**Mark points:**
- Represents the even case generally and shows that n² + 2n is divisible by 4.
- Combines it with the given odd case and concludes all integers are covered.

### Restricted residue cases

**Possible wording:** For integers not divisible by 3, prove by exhaustion, Consider all allowed remainders

**Claim:** $n^2-1$ is divisible by $3$ when integer $n$ is not divisible by $3$.

- The allowed cases are $n=3k+1$ and $n=3k+2$.
- For $n=3k+1$, $n^2-1=3(3k^2+2k)$.
- For $n=3k+2$, $n^2-1=3(3k^2+4k+1)$.
- Both results are divisible by $3$, and the cases cover all allowed integers.

For integer $k$, $3k-1$ and $3k+2$ describe the same remainder class, so using both would miss the remainder-$1$ class. One valid alternative pair is $3k-1$ and $3k+1$. The distinct forms $6k+1$ and $6k+2$ still miss allowed values: 5 is neither, although it is not divisible by 3. Check coverage as well as overlap.

**Try it:** For an integer $n$ not divisible by $3$, prove by exhaustion that $n(n+1)(n+2)$ is divisible by $3$.

**Review answer:** If $n=3k+1$, then $n+2=3(k+1)$. If $n=3k+2$, then $n+1=3(k+1)$. In both cases the product has a factor of $3$. These are all the allowed residue classes, so the claim holds.

**Mark points:**
- Covers both allowed residue classes, for example n = 3k + 1 and n = 3k + 2.
- Shows at least one of n, n + 1 or n + 2 is divisible by 3 in each case, and concludes for all allowed integers.

**If another try is needed:** For an integer $n$ not divisible by $3$, prove by exhaustion that $n(n+2)(n+4)$ is divisible by $3$.

**Review answer:** If $n=3k+1$, then $n+2=3(k+1)$. If $n=3k+2$, then $n+4=3(k+2)$. Both allowed cases give a factor of $3$, so the product is divisible by $3$.

**Mark points:**
- Covers both allowed residue classes, for example n = 3k + 1 and n = 3k + 2.
- Establishes divisibility by 3 in each case and concludes for all allowed integers.

### Exhaustion with ordered pairs

**Possible wording:** Prove by considering every allowed pair, Show the bounds hold for each combination

**Claim:** $x+2y \leq 6$ when $x,y\in\{1,2\}$.

- The ordered pairs are $(1,1)$, $(1,2)$, $(2,1)$ and $(2,2)$.
- The corresponding values are $3$, $5$, $4$ and $6$.
- Each value is at most $6$, so the claim holds for every allowed pair.

Do not combine $(1,2)$ and $(2,1)$: the expression changes when the inputs are swapped.

**Try it:** For $x,y\in\{1,2\}$, prove by exhaustion that $-1\leq x-y\leq1$.

**Review answer:** The pairs $(1,1)$, $(1,2)$, $(2,1)$ and $(2,2)$ give $0$, $-1$, $1$ and $0$. All are within the stated bounds.

**Mark points:**
- Lists or otherwise accounts for all four ordered pairs, including the swapped pairs.
- Checks the differences and concludes that all fall in the stated interval.


**If another try is needed:** For $x,y\in\{0,1\}$, prove by exhaustion that $x+2y\leq3$.

**Review answer:** The ordered pairs $(0,0),(0,1),(1,0),(1,1)$ give $0,2,1,3$. Each is at most $3$, and the list covers all allowed pairs.

**Mark points:**
- Lists or accounts for all four ordered pairs.
- Checks their values and concludes they are at most 3.

### In your own words

Why is checking $(1,3)$ enough to cover $(3,1)$ for a sum, while $(3,3)$ still needs checking?

### Saved lesson note

- Identify a finite, complete set of cases.
- Include equal-value cases unless excluded.
- Check each case, then conclude for the whole domain.

## Disproof by counterexample (P2-1.3)

### Why this matters

A claim about every positive integer can collapse at one input. Finding and explaining that failure is often quicker than trying many successful examples.

### Try it first

Which result disproves '$n^2+2$ is prime for every positive integer $n$'?
- A. $n=5$ gives $27=3\times9$
- B. $n=1$ gives the prime 3
- C. $n=3$ gives the prime 11
- D. $n=9$ gives the prime 83

**Review key:** A. The allowed input 5 gives 27, which is composite, so the universal claim is false.

### Helpful terms

- **Counterexample**: An allowed case where the claimed conclusion is false. Notation: none. Read aloud: counterexample.
- **Universal claim**: A statement asserting a property for every value in its stated domain. Notation: ∀. Read aloud: for all.
- **Prime**: An integer greater than one with exactly two positive divisors. Notation: none. Read aloud: prime.
- **Consecutive primes**: Prime numbers listed in order with no prime omitted between them. Notation: none. Read aloud: consecutive primes.

### In plain words

One valid counterexample disproves a claim that says something is true for every allowed value. The value must obey the assumptions and make the conclusion fail.

### More detail

Disproof by counterexample means giving one input that satisfies the assumptions but makes the claimed conclusion false. For '$n^2-n+1$ is prime for all positive integers $n$', choose $n=5$. Then $n^2-n+1=25-5+1=21=3\times7$. Because 21 has factors other than 1 and itself, it is composite. Therefore the claim is false. A prime output at another input proves only that instance. The counterexample must lie inside the domain: a negative integer cannot refute a statement restricted to positive integers. Calculate and justify the failure explicitly; merely guessing that a value is not prime is insufficient.

A single valid counterexample disproves a universal claim. By contrast, proof by exhaustion establishes a claim only after every allowed case has succeeded.

### Diagram

Choose an input inside the domain. Show the claimed conclusion fails, then reject the universal claim.

![Choose an input inside the domain. Show the claimed conclusion fails, then reject the universal claim.](../../../build/out/Assets/P2/P2-1-counterexample-flow.svg)

### Worked example

Disprove the claim that $n^2-n+1$ is prime for every positive integer $n$.

1. Choose the admissible input $n=5$. A universal claim needs only one valid counterexample to be false.
2. Calculate $5^2-5+1=21$. The output must be evaluated exactly before testing primality.
3. Factor $21=3\times7$. Therefore 21 is composite, so the claim is false. A factorisation using factors greater than 1 proves the output is not prime.

### Common misconception

**Wrong idea:** Any value giving a failure disproves a restricted claim.

**Why it is tempting:** The calculation produces a contradiction.

**Fix:** First check that the value belongs to the stated domain.

### Common misconception

**Wrong idea:** One successful example proves a universal claim.

**Why it is tempting:** The statement holds in the example.

**Fix:** A successful case is consistent with the claim but does not establish every case.

### Disprove a universal statement

**Possible wording:** Disprove by counterexample, Show that the statement is false

**Claim:** Every positive integer has an odd square.

- Choose $n=2$, which is a positive integer.
- Its square is $n^2=4$, which is even.
- The allowed input makes the conclusion fail, so the claim is false.

**Try it:** Disprove: every integer $n\geq 4$ has $n^2+n$ divisible by $4$.

**Review answer:** Take $n=5$, which is at least 4: $n^2+n=30$, which is not divisible by 4.

**Mark points:**
- Gives an integer at least 4 as a counterexample.
- Shows its value is not divisible by 4.


**If another try is needed:** Disprove: for every integer $n>2$, $n^2+1$ is even.

**Review answer:** Take $n=4$, which is greater than 2. Then $n^2+1=17$, which is odd, so the claim is false.

**Mark points:**
- Gives an integer greater than 2 as a counterexample.
- Calculates an odd result and concludes the claim is false.

### Check domain and failed conclusion

**Possible wording:** Is this a valid counterexample?, Explain why the example does not disprove the claim

A claim applies only to positive integers. A student tries $n=-1$ as a counterexample.

- The input $-1$ is outside the stated domain.
- It cannot disprove the restricted claim, even if the calculation fails there.

For a claim restricted to prime numbers, $n=1$ is also outside the domain: 1 is not prime. A valid counterexample must be prime and make the conclusion false.

**Try it:** Can $n=0$ disprove a claim restricted to positive integers? Explain.

**Review answer:** No. Zero is not a positive integer and is outside the stated domain.

**Mark points:**
- States that zero is outside the positive integer domain.


**If another try is needed:** Can $n=\frac12$ disprove a claim restricted to integers? Explain.

**Review answer:** No. One half is not an integer, so it is outside the stated domain.

**Mark points:**
- States that one half is not an integer.
- Concludes that an out-of-domain input cannot disprove the claim.

### Counterexample with a prime domain

**Possible wording:** Disprove the claim for prime numbers, Find a prime counterexample

Disprove: for every prime $p$, $p+2$ is prime.

- Choose $p=7$, which is prime and allowed.
- Then $p+2=9=3\times3$, which is not prime.
- The allowed input makes the conclusion false, so the claim is disproved.

**Try it:** Disprove: for every prime $p$, $p^2+4$ is prime.

**Review answer:** Choose $p=2$, which is prime. Then $p^2+4=8=2\times4$, which is not prime. This disproves the claim.

**Mark points:**
- Gives an allowed prime input.
- Shows that its corresponding value is not prime, making the claim false; a separate concluding sentence is not required.


**If another try is needed:** Disprove: for every prime $p$, $p^2+6$ is prime.

**Review answer:** Choose $p=3$, which is prime. Then $p^2+6=15=3\times5$, which is not prime. The claim is false.

**Mark points:**
- Gives an allowed prime input.
- Shows that its corresponding value is not prime, making the claim false; a separate concluding sentence is not required.


### Counterexample after widening the domain

**Possible wording:** Show the result need not hold for all real numbers, Disprove the extended claim with a counterexample

**Original claim:** If $x$ and $y$ are positive real numbers, then $x+y>0$.

**Extended claim:** $x+y>0$ for all real $x$ and $y$.

- Choose $x=-1$ and $y=-2$. Both are real.
- Their sum is $-3$, which is not positive.
- The extended claim fails. This does not disprove the original claim, which requires both numbers to be positive.

**Try it:** For positive real $x$ and $y$, $xy>0$. Disprove the claim that $xy>0$ for all real $x$ and $y$.

**Review answer:** For example, $x=-1$ and $y=2$ are real and give $xy=-2$, which is not positive. Other valid real pairs, including a zero input, also disprove the claim.

**Mark points:**
- Gives a pair of real numbers allowed in the extended domain.
- Shows their product is not positive, making the extended claim false; a separate concluding sentence is not required.


**If another try is needed:** For positive real numbers with $x>y$, $x-y>0$. Disprove the widened claim that $x-y>0$ for all positive real $x$ and $y$.

**Review answer:** Take $x=1$ and $y=2$. Both are positive real numbers, but $x-y=-1$, which is not positive. This disproves the widened claim without contradicting the restricted one.

**Mark points:**
- Gives a pair of positive real numbers allowed in the widened domain.
- Shows the difference is not positive, making the widened claim false; a separate concluding sentence is not required.

### In your own words

Why does $n=5$ settle the prime claim, while $n=4$ does not prove it?

### Counterexample involving consecutive primes

**Possible wording:** Disprove a statement about consecutive primes, Find a counterexample satisfying every condition

Consecutive primes have no other prime between them. A prime has exactly two positive factors; $1$ is not prime, while $2$ is prime.

**Claim:** Every three consecutive primes start with an even number.

- The primes $3,5,7$ are consecutive: no prime is skipped.
- They start with $3$, which is odd.
- This allowed triple makes the conclusion false, so the claim is disproved.

**Try it:** Disprove: the sum of every three consecutive primes is divisible by $5$.

**Review answer:** The numbers $5,7,11$ are consecutive primes. Their sum is $23$, which is not divisible by $5$. This counterexample disproves the claim.

**Mark points:**
- Gives three consecutive primes.
- Uses a valid consecutive-prime triple, calculates its sum and shows it is not divisible by 5; concludes the claim is false. Accept any valid triple.



**If another try is needed:** Disprove: the sum of every three consecutive primes is odd.

**Review answer:** The numbers $2,3,5$ are consecutive primes. Their sum is $10$, which is even. This counterexample disproves the claim.

**Mark points:**
- Gives three consecutive primes.
- Uses a valid consecutive-prime triple, calculates its sum and shows it is even; concludes the claim is false. Accept any valid triple.

### Saved lesson note

- Choose an input inside the stated domain.
- Calculate the claimed expression exactly.
- Show that the conclusion fails, then reject the universal claim.

## Pilot limitations

- The adaptive learning AI is experimental and hidden while free-form maths verification remains incomplete.
- Source coverage and marking need independent review. The inventory does not claim every possible exam form.
- The full app includes a probe, plan, additional question checks and review steps selected dynamically.
