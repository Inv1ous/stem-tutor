# Now
_Equations of motion · test · 09:01_

> [!question] Q1 · MCQ · 1 mark · no hints
> Which quantity is a vector?
>
> **A.** distance
> **B.** speed
> **C.** displacement
> **D.** time

*Test check: one question per syllabus point, no hints until answered. 'Don't know' is a fine answer.*

> [!quote] You
> Can you show me an example using three consecutive integers? The notes do not have one.

> [!tip] Tutor-written: Three consecutive integers example
> Short version: let the first integer be n, so the three are n, n + 1, n + 2. Because n is any integer, this covers every case.
>
> Claim: the sum of any three consecutive integers is a multiple of 3.
>
> Step 1 (assumptions and domain): n is an integer, and the three integers are n, n + 1 and n + 2.
> Step 2 (add them): n + (n + 1) + (n + 2) = 3n + 3.
> Step 3 (factorise): 3n + 3 = 3(n + 1).
> Step 4 (conclude): n + 1 is an integer, so 3(n + 1) is 3 times an integer. The sum is therefore a multiple of 3, for every integer n.
>
> Why this works: we did not write n = 2k or pick a particular n, so we added no hidden assumption. Trying 4, 5, 6 (sum 15) or 7, 8, 9 (sum 24) would only be examples, not a proof.
>
> I can show a version with the product of three consecutive integers if you'd like more detail.
>
> Written by the tutor for your question: it is not from your notes or a past paper. Checked by computer algebra: `n + (n+1) + (n+2) = 3n + 3`; `3(n+1) = 3n + 3`. The wording and reasoning are not machine-checked.

> [!abstract] In your own words
> Which step of an argument would you challenge if it assumes an integer is even without saying so?

> [!quote] You
> I cannot picture how the even and odd cases together cover every integer.

> [!tip] Tutor-written: Why even and odd cover every integer
> Short version: the integers alternate even, odd, even, odd along the number line, so there is no gap and no third type.
>
> Picture it: ... −2, −1, 0, 1, 2, 3, 4 ... Each even number 2k is followed by the next number 2k + 1, and then 2k + 2 is the next even number. Every integer sits at one of these two positions.
>
> Why that is certain: divide any integer n by 2. The remainder can only be 0 or 1. Remainder 0 means n = 2k (even). Remainder 1 means n = 2k + 1 (odd). No other remainder is possible, so two cases are enough.
>
> This also shows why 'n = 2k' on its own is not general: it only covers the even half.
>
> Try this: where would −3 fit, as 2k or 2k + 1? What is k?
>
> Written by the tutor for your question: it is not from your notes or a past paper. Checked by computer algebra: `(2k+1)+1 = 2k+2`. The wording and reasoning are not machine-checked.

> [!abstract] Diagram
> Case split. start: Any integer n; end: Every integer is covered; cases: Even: n = 2k / Odd: n = 2k + 1
>
> ![[docs/benchmarks/2026-10-29-pilot-demo/Assets/generated/case_split-cf2937b7a826.svg]]
