<!-- spec: M1 -->
# Additional shortcuts and elegant methods — M1 and S1

# M1 Mechanics

## 1. Kinematics in a straight line (suvat and graphs)

- **Reset the clock when the motion changes** `9/10`. At an impact, break, or change of surface, record the current position and velocity, then start the next phase at local time $\tau=0$. Recalculate $a$ for that phase; one suvat equation across the boundary works only if acceleration stays constant. [src: Pearson WME01 Jan 2024 examiner report Q8(b)]
- **Screen a meeting quadratic before solving** `7/10`. If equating two positions produces $At^2+Bt+C=0$ with $A\ne0$, the discriminant $B^2-4AC$ tells you whether there are zero, one, or two real candidate meetings. Keep only nonnegative roots inside the time interval where both position formulae apply, and substitute back. [src: derived]
- **Time spent above a height** `7/10`. For a vertical projection at speed $u$, solving $h=ut-\tfrac12gt^2$ gives the duration above height $h$ as $2\sqrt{u^2-2gh}/g$ when $0\le h\le u^2/(2g)$. It becomes zero at the maximum height, which checks the result. [src: derived]
- **Distinguish a velocity graph from a speed graph** `7/10`. With up positive, vertical velocity is the straight line $v=u-gt$, while speed is $|u-gt|$ and has a V-shaped graph. Reflect the negative part only for speed or total distance; check that the descending velocity still has gradient $-g$. [src: Pearson WME01 Jan 2024 examiner report Q6(d)]

## 2. Vectors and 2D motion

- **Name the axis in a direction answer** `7/10`. After finding an angle from vector components, write, for example, "$\theta$ above the positive $\mathbf i$ direction" and use the component signs to choose the quadrant. A bare $\tan^{-1}(y/x)$ can give the wrong direction when $x<0$. [src: Pearson WME01 Jun 2023 examiner report Q2(b)]
- **Compare squared distances** `6/10`. If a question asks whether the least separation exceeds a nonnegative threshold $r$, compare $d_{\min}^2$ with $r^2$ and skip the final square root. Check that the calculated closest-approach time lies in the allowed interval; otherwise use its nearest endpoint. [src: derived]

## 3. Dynamics, connected particles and friction

- **Use the force diagram as an equation checklist** `9/10`. For each body, draw and label only forces acting on that body, then tick each arrow as it enters the appropriate $F=ma$ equation. Check that the mass multiplying $a$ belongs to the same body and that no weight or tension was silently omitted. [src: Pearson WME01 Jun 2023 examiner report Q7]
- **Recalculate the normal reaction for oblique forces** `8/10`. If a tension $T$ pulls at angle $\phi$ above a plane inclined at $\theta$, $R=mg\cos\theta-T\sin\phi$ while contact remains. Check $R\ge0$ and use this value, rather than $mg\cos\theta$, in any friction limit. [src: Cambridge 9709 Jun 2024 examiner report Paper 42 Q5]
- **Reverse friction after a turn** `8/10`. On a rough surface, label the actual direction of motion in each phase and make kinetic friction oppose it. After a reversal, form a new force equation; check that friction's arrow has reversed too. [src: Pearson WME01 Jan 2024 examiner report Q8(b)]
- **Find required friction before testing the limit** `8/10`. In equilibrium, solve the along-surface balance for signed $F_{\rm req}$, then test $|F_{\rm req}|\le\mu R$. Its sign gives the friction direction, and equality identifies the limiting case. [src: derived]
- **One string distance can mean different vertical changes** `8/10`. With a taut, inextensible string, if one particle rises $x$ vertically while another moves $x$ along a plane at $\theta$, their vertical changes are $x$ and $x\sin\theta$. For a vertical gap $H$ closing between them, check the geometry with $x+x\sin\theta=H$ before using suvat. [src: Cambridge 9709 Jun 2024 examiner report Paper 42 Q7(b)]
- **Choose the body with known velocities for impulse** `8/10`. When impulse on a particle is requested, use $\mathbf J=m(\mathbf v-\mathbf u)$ for the particle whose before and after velocities are given. Check that a requested magnitude is nonnegative and has units $\mathrm{N\,s}$ or $\mathrm{kg\,m\,s^{-1}}$. [src: Pearson WME01 Jun 2023 examiner report Q1(c)]
- **Separate mass from weight in the data margin** `8/10`. Mark a given $m\,\mathrm{kg}$ as mass and $W\,\mathrm N$ as an already calculated weight; only the first needs multiplication by $g$. Check every force equation is in newtons, preventing an erroneous $Wg$. [src: Pearson WME01 Jun 2023 examiner report Q6]

## 4. Statics and moments

- **Treat two support reactions as load shares** `8/10`. For vertical loads on a horizontal beam supported at $x=0,L$, let $W=\sum W_i$ and $\bar x=\sum W_ix_i/W$; then $R_L=W\bar x/L$ and $R_0=W-R_L$. Check $R_0+R_L=W$ and both reactions are nonnegative while both supports touch. [src: derived]
- **Cancel $g$ only after writing every weight moment** `7/10`. When every term in a moments equation is a weight $m_i g$ times a distance, write those terms first and divide the entire equation by $g$. Check that no independent force in newtons was included before cancellation. [src: derived]
- **Locate the tipping boundary from the load centre** `7/10`. With only vertical loads and upward supports, the weighted position $\bar x=\sum W_ix_i/\sum W_i$ must lie between the supports for both reactions to be nonnegative. At either support position the opposite reaction is zero, which checks a tilting calculation. [src: derived]

## 6. Fast checks

- **Keep exact trigonometric ratios until the end** `8/10`. If $\tan\theta=p/q$, use a right triangle to keep $\sin\theta=p/\sqrt{p^2+q^2}$ and $\cos\theta=q/\sqrt{p^2+q^2}$ rather than rounding $\theta$ first. Check the final numerical answer with the paper's required significant figures. [src: Cambridge 9709 Jun 2024 examiner report Paper 42 Q4]
- **A coefficient of friction may exceed one** `6/10`. Since $\mu=F_{\max}/R$ is a force ratio, a calculated $\mu>1$ is not automatically impossible. Substitute it into the limiting-friction and force equations instead of treating it like a probability. [src: Pearson 9MA0-32 Jun 2024 examiner report Q7(b)]

# S1 Statistics

<!-- spec: S1 -->
## 1. Data: summary and representation

- **Show the rounding that proves a printed answer** `9/10`. In a "show that" question, display the formula, exact or unrounded substitution, and a value with more figures than the printed result. Check that the displayed value actually rounds to that result; merely copying the printed answer does not establish it. [src: Pearson WST01 Jan 2024 examiner report Q2(a)(ii)]
- **Count a fraction of a grouped class** `8/10`. If a threshold $t$ lies within class $[L,U)$ of frequency $f$, estimate the number below it in that class as $f(t-L)/(U-L)$, assuming uniform spread within the class. Add the complete lower classes and check the partial count lies from $0$ to $f$. [src: Pearson WST01 Jun 2022 examiner report Q3(c)]
- **Interpolate down from the upper boundary** `7/10`. If the desired rank $r$ is near the upper end of a class with upper boundary $U$, frequency $f$, width $w$, and cumulative frequency $C$ through the class, use $Q=U-(C-r)w/f$. Check it agrees with upward interpolation from the lower boundary. [src: Pearson WST01 Jun 2022 examiner report Q3(b)]

## 2. Correlation and regression

- **Predict a change using only the gradient** `9/10`. For $\hat y=a+bx$ with $b\ne0$, a change $\Delta y$ corresponds to $\Delta x=\Delta y/b$; the intercept cancels. Check units and the sign of $b$ before interpreting the direction of change. [src: Pearson WST01 Jun 2022 examiner report Q2(f)]
- **Find the regression slope from correlation and spread** `8/10`. If $r,\sigma_x,\sigma_y$ are known and $\sigma_x>0$, the $y$-on-$x$ slope is $b=r\sigma_y/\sigma_x$. Check that its sign matches $r$ and its units are response units per explanatory unit. [src: derived]
- **Enter scaled predictor units literally** `8/10`. If a regression's $x$ is measured in millions, seven million means $x=7$ in the equation. Check the resulting prediction against the scale and range of the original data, and state the output units. [src: Pearson WST01 Jun 2022 examiner report Q2(e)]
- **Keep the full gradient when finding the intercept** `8/10`. Compute $a=\bar y-b\bar x$ with the unrounded calculator value of $b$, then round the stated line as instructed. Check the displayed equation at $x=\bar x$; it should give approximately $\bar y$. [src: Pearson WST01 Jan 2024 examiner report Q4(b)]

## 3. Probability

- **Check every denominator in sampling without replacement** `9/10`. For $k$ ordered draws from $N$ objects without replacement, denominators run $N(N-1)\cdots(N-k+1)$, and a repeated-success numerator also decreases. A denominator fixed at $N$ would model replacement, so inspect that pattern before multiplying. [src: Pearson WST01 Jun 2022 examiner report Q3(d)]
- **Make stopping outcomes terminal immediately** `8/10`. In a game that ends on a specified result, draw no further branches after that result. Add the probabilities of all terminal leaves to check they total $1$. [src: Pearson WST01 Jun 2022 examiner report Q5(f)]
- **Independence extends to complements** `7/10`. If $A$ and $B$ are independent, then $P(A\cap B')=P(A)[1-P(B)]$. Cross-check by subtracting $P(A\cap B)$ from $P(A)$. [src: derived]
- **Keep three-set overlaps once** `7/10`. For three events, use $P(A\cup B\cup C)=P(A)+P(B)+P(C)-P(A\cap B)-P(A\cap C)-P(B\cap C)+P(A\cap B\cap C)$. Check a mutually exclusive pair has zero pair and triple intersection before substituting. [src: derived]

## 4. Discrete random variables

- **Use a joint table for products unless independent** `8/10`. For independent $X,Y$, $E(XY)=E(X)E(Y)$; otherwise compute $\sum_{x,y}xyP(X=x,Y=y)$ from the joint distribution. Check independence is stated or proved before multiplying separate means. [src: derived]
- **Merge equal products from two draws** `8/10`. With two independent draws with replacement, ordered pair $(x_i,x_j)$ has probability $p_ip_j$; combine pairs that yield the same product. Off-diagonal pairs contribute $2p_ip_j$ when both orders are possible, but a diagonal pair contributes $p_i^2$ only once. [src: Pearson WST01 Oct 2022 examiner report Q7(e,f)]
- **Fix a discrete CDF at its upper endpoint** `8/10`. If the largest possible value is $m$, use $F(m)=1$ to find an unknown constant before differencing the CDF. Check that $F$ is nondecreasing and all successive differences are nonnegative. [src: Pearson WST01 Jan 2024 examiner report Q7(a,b)]
- **Build a payoff table from terminal outcomes** `7/10`. List each game's terminal route with its probability and net gain, including the entry fee exactly once, then calculate $E(G)=\sum g_ip_i$. Check route probabilities sum to $1$ before taking the expectation. [src: derived]

## 5. The Normal distribution

- **Solve a conditional normal quantile by CDF arithmetic** `9/10`. For $v<c$ and $P(X>v\mid X<c)=q$, write $[F(c)-F(v)]/F(c)=q$, then find $F(v)=(1-q)F(c)$ and invert once. Check $v<c$ and $0<F(v)<F(c)$. [src: Pearson WST01 Jun 2022 examiner report Q6(c)]
- **Equal opposite tails locate the mean** `8/10`. If $X$ is normal and $P(X<a)=P(X>b)$ with $a<b$, symmetry gives $\mu=(a+b)/2$ without a table. Check that $a$ and $b$ are equally far from this mean. [src: derived]
- **Simplify a cutoff containing the mean** `8/10`. If a probability at cutoff $k\mu$ gives $(k\mu-\mu)/\sigma=z$, rewrite it at once as $(k-1)\mu=z\sigma$. Combine that short relation with the other condition and check $\sigma>0$. [src: Pearson WST01 Jan 2024 examiner report Q8]
- **Separate the normal model from the sampling model** `8/10`. First calculate $p=P(X>c)$; for two independent attempts, both exceeding $c$ has probability $p^2$. For two draws without replacement from a counted group with $M$ successes among $N$, use $M(M-1)/[N(N-1)]$ instead; check which model the question states. [src: Pearson WST01 Jan 2024 examiner report Q1(d)]

## 7. Fast checks

- **Name both variables when interpreting correlation** `8/10`. State how the named response tends to change as the named explanatory variable increases, including strength and direction. Check that the sentence describes a relationship in context rather than merely saying "positive correlation". [src: Pearson WST01 Jun 2022 examiner report Q2(b)]
