---
tags: [stem-tutor/lesson, S1]
spec: "S1"
subtopic: "S1-2"
kcs: ["S1-2.1", "S1-2.2", "S1-2.3", "S1-2.4"]
---
# 2 Representation and summary of data

> [!abstract] In one breath
> Histograms, stem-and-leaf diagrams and box plots each display a distribution a different way — trading individual values for shape, or shape for a five-figure summary. Mean, median and mode locate the "middle"; variance, standard deviation and IQR measure the spread; comparing mean with median reveals skew and flags outliers.

## Key ideas

**Frequency density** $=\text{frequency}\div\text{class width}$. On a histogram this is the quantity plotted as **height**; it is the bar's **area** (height $\times$ width) that represents frequency, which matters as soon as class widths differ.

**Stem-and-leaf diagram**: keeps every raw value, split into a stem (leading digit(s)) and leaves (final digit), ordered within each stem. A **back-to-back** stem-and-leaf diagram shares one stem column between two data sets, with each side keeping its own leaves and its own key.

**Box plot**: shows the five-figure summary — minimum, lower quartile $Q_1$, median, upper quartile $Q_3$, maximum. When a value is an outlier it is plotted as a separate point, and the whisker stops at the largest (or smallest) value that is **not** an outlier; the outlier is still the data's maximum (or minimum).

![[Assets/S1/S1-2-boxplot-outlier.svg]]

**Mean** $\bar x = \dfrac{\Sigma x}{n}$ (or $\dfrac{\Sigma fx}{n}$ for frequency data; for grouped data use the class mid-point as $x$, so the mean and standard deviation are then **estimates**); **median** is the middle value in the ordered data (the mean of the two middle values when $n$ is even); **mode** is the most frequently occurring value.

**Coding**: if $y=(x-a)/b$, then $\bar x = a+b\bar y$ — undo the coding in reverse order (multiply by $b$, then add $a$).

**Variance** $\mathrm{Var}(X) = \dfrac{S_{xx}}{n} = \dfrac{\Sigma x^2}{n} - \bar x^2$ (dividing by $n$, not $n-1$, on this specification); **standard deviation** $=\sqrt{\mathrm{Var}(X)}$. Coding by $y=(x-a)/b$ scales the variance by $b^2$ only: $\mathrm{Var}(X) = b^2\,\mathrm{Var}(Y)$ — the additive constant $a$ never changes spread.

**Range** $=$ largest value $-$ smallest value; it uses only the two extremes, so one outlier changes it a lot. **Interquartile range** $\mathrm{IQR} = Q_3-Q_1$, the spread of the middle 50%. An **interpercentile range** is the difference between two percentiles, e.g. the 10–90 interpercentile range $P_{90}-P_{10}$ covers the middle 80% (the IQR is the 25–75 case). For grouped data, quartiles and percentiles need **linear interpolation** within the class that contains them.

**Skewness**: comparing mean and median shows the direction of the tail. If $\bar x > \text{median}$, a few high values pull the mean up — **positive (right) skew**. If $\bar x < \text{median}$, it's **negative (left) skew**. From the quartiles (e.g. on a box plot): if $Q_2-Q_1<Q_3-Q_2$ the skew is positive; if $Q_2-Q_1>Q_3-Q_2$ it is negative; roughly equal means symmetric.

![[Assets/S1/S1-2-skew-shapes.svg]]

**Outliers**: a value is an outlier if it lies more than a stated multiple of the IQR beyond the nearer quartile — the rule is always given in the question, never assumed.

## Method

**Frequency density:** find the class width, then divide the class frequency by it.

**Mean, variance, sd from a frequency table:** find $n=\Sigma f$, $\Sigma fx$, $\Sigma fx^2$; mean $\bar x = \Sigma fx/n$; variance $=\Sigma fx^2/n-\bar x^2$; sd is its square root.

**Reversing coding:** find $\bar y$ (or $\mathrm{Var}(Y)$) from the coded data, then apply $\bar x = a+b\bar y$ for the mean, or $\mathrm{Var}(X)=b^2\,\mathrm{Var}(Y)$ (no $a$ term) for the variance.

**Quartiles of a small ungrouped list:** order the data; for $Q_1$ find $\tfrac{n}{4}$ (for $Q_3$, $\tfrac{3n}{4}$). If it is a whole number, take the mean of that value and the next one; otherwise round up and take that value. E.g. $n=10$: $\tfrac{n}{4}=2.5$, so $Q_1$ is the 3rd value.

**Quartiles by linear interpolation (grouped data):**
1. Build the cumulative frequency table.
2. Find the target position ($\tfrac{n}{4}$ for $Q_1$, $\tfrac{n}{2}$ for the median, $\tfrac{3n}{4}$ for $Q_3$) and its class.
3. Interpolate: $Q = L + \dfrac{\text{target} - \text{cf before}}{f}\times w$, with $L$ the class's lower boundary, $f$ its frequency, $w$ its width.

> [!example]- Worked example
> The table shows the number of texts sent, $x$, by 20 students in a day.
>
> | $x$ | 5 | 10 | 15 | 20 |
> |---|---|---|---|---|
> | $f$ | 4 | 6 | 7 | 3 |
>
> Calculate the mean and the standard deviation.
>
> 1. Find $\Sigma fx$ and $\Sigma fx^2$: $\Sigma fx = 4(5)+6(10)+7(15)+3(20)=245$; $\Sigma fx^2 = 4(25)+6(100)+7(225)+3(400)=3475$.
>    *(The variance formula needs both totals, not just the mean.)*
> 2. Find the mean: $\bar x = \Sigma fx / n = 245 \div 20 = 12.25$.
>    *(Mean is total divided by count, using $n=\Sigma f=20$.)*
> 3. Find the variance then square root it: $\mathrm{Var}(X)=\Sigma fx^2/n-\bar x^2 = 3475/20 - 12.25^2 = 23.6875$, so $\mathrm{sd}=\sqrt{23.6875}=4.87$ (3 s.f.).
>    *(Variance is mean-of-squares minus square-of-mean; standard deviation is its square root, in the original units.)*

## Traps

- **Trap:** Reading histogram bar **height** as the frequency. **Why it's wrong:** height is frequency density; once widths differ, only **area** gives frequency back. **Instead:** always divide frequency by class width before comparing bars.
- **Trap:** Reversing coding as $\bar x = b\bar y$, forgetting to add $a$ back. **Why it's wrong:** coding must be undone in reverse order — multiply by $b$, *then* add $a$. **Instead:** always write $\bar x = a+b\bar y$ in full before substituting.
- **Trap:** Dividing by $n-1$ to find variance. **Why it's wrong:** on this specification variance is $S_{xx}/n$, the mean of the squared deviations. **Instead:** always divide by $n$ here.
- **Trap:** Assuming $\bar x>\text{median}$ means *negative* skew. **Why it's wrong:** it's the opposite — a long right-hand tail pulls the mean *above* the median, which is *positive* (right) skew. **Instead:** picture which way the tail points.
- **Trap:** Applying $a$ to variance, e.g. $\mathrm{Var}(X)=b^2\mathrm{Var}(Y)+a$. **Why it's wrong:** a shift never changes spread — only the scale factor $b$ does. **Instead:** $\mathrm{Var}(X)=b^2\,\mathrm{Var}(Y)$, with no $+a$.

## Exam technique

- *Calculate* / *Find* need working shown, even for a quick formula.
- *Interpret* / *Explain* must stay **in context** — name what is being compared ("Team A's heights are more varied than Team B's", not just "the IQR is bigger"). A model comparison: "On average Team B are slightly taller (median 170 cm against 168 cm), and Team B's heights are more consistent (IQR 7 cm against 16 cm)."
- An outlier rule (e.g. $Q_3+1.5\times\mathrm{IQR}$) is always **given** in the question — never assume $1.5$.
- Drawing the diagrams is rarely the focus — reading, comparing and interpreting them is.
- Don't round intermediate cumulative-frequency working before interpolating.

## Links
Builds on [[1 Modelling in probability and statistics]] · Leads to [[3 Elementary probability]]
