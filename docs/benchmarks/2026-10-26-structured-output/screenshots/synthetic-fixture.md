**Synthetic semantic display fixture**

**Bold label** and *italic explanation*. Variables $x_i^2$, $a$, $v$; upright units $9.81\,\mathrm{m\,s^{-2}}$. This is a deterministic display fixture, not a model answer.

- Chemistry: $\mathrm{H_2SO_4}$, $\mathrm{SO_4^{2-}}$, $\mathrm{NH_4^+}$; $\mathrm{CuSO_4}\cdot5\mathrm{H_2O}$. Elements must stay upright; charges and hydration dots must survive.

- Literal notation stays literal: `x_1^2 * y`, price $5 and $10, accuracy 50%. Separate list items need visible gaps and hanging indentation when they wrap.

**Numbered calculation**

1. Choose the integral of the italic variable $x$ over the complete bounds $0$ to $1$.

$$
\int_0^1 x^2\,\mathrm{d}x = \left[\frac{x^3}{3}\right]_0^1 = \frac{1}{3}
$$

2. Keep the numbered explanation associated with its equation. A summation keeps both the lower and upper bound.

$$
\sum_{i=1}^{n} i = \frac{n(n+1)}{2}
$$

3. Check a limit without losing the approach direction or denominator.

$$
\lim_{x\to0}\frac{\sin x}{x}=1
$$

**Literal code and wrapping**

```
x_1^2 * y
{"blocks": [{"kind": "paragraph", "text": "literal JSON"}]}
print("$5, 50%, H_2SO_4")
```

A longer explanation should wrap inside the tutor card, leaving the input and menu controls reachable. Each paragraph holds one idea. Read this at a narrow terminal width to check the right edge, then scroll to compare the same text across themes.

The extra sentence deliberately extends across several rows without requiring horizontal scrolling.

A second paragraph must have a real gap above it. Mathematical indices $x_{n+1}$ and grouped powers $a^{n+1}$ may need the established labelled or grouped source fallback when Unicode cannot represent them fully; the complete expression must remain available.

- Final checklist: readable blank lines, complete signs and charges, distinct prose emphasis, stable list alignment and intact code.
