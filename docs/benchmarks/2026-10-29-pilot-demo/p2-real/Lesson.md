# Lesson - Proof
_Thursday 29 October 2026, 09:47_

> [!abstract] Let's go
> We'll find out what you already know, agree a plan, then build each idea step by step. Your notes grow in Obsidian as we go.

> [!abstract] What do you want from Proof?
> - Learn it properly from scratch
>
> - I've had lessons: find and fill my gaps
>
> - Revise for a test soon
>
> - Just the key ideas, quickly

> [!quote] You
> Show me a worked example of a proof using three consecutive integers; the notes only have even and odd examples.

> [!tip] Tutor-written: Worked proof using three consecutive integers, e.g. the sum of three consecutive integers is divisible by 3, with n as a
> Short version: call the three consecutive integers $n$, $n+1$ and $n+2$, add them, and factorise to show the total is $3$ times an integer, so it is divisible by $3$.
>
> **Worked proof**
>
> 1. Let $n$ be any integer. Then three consecutive integers are $n$, $n+1$ and $n+2$, because each integer is one more than the one before. This works for every starting integer, so it covers all cases.
>
> 2. Write their sum.
>
> $$
> S = n + (n+1) + (n+2)
> $$
>
> 3. Collect like terms: there are three $n$ terms and the constants $1+2=3$.
>
> $$
> S = 3n + 3
> $$
>
> 4. Factorise out $3$.
>
> $$
> S = 3(n+1)
> $$
>
> 5. Since $n$ is an integer, $n+1$ is also an integer. So $S$ is $3$ multiplied by an integer, which is the definition of being divisible by $3$.
>
> Conclusion: the sum of any three consecutive integers is divisible by $3$. Notice the link with your even and odd work: there you wrote $2k$ or $2k+1$, whereas here the 'shape' $n$, $n+1$, $n+2$ does the job instead.
>
> **Your turn**
>
> Try this yourself using the same set-up: prove that the sum of three consecutive integers is always three times the middle integer. Have a go, then send me your working and I will check it with you.
>
> If you would like more detail, I can show a second version that starts from the middle integer, written as $n-1$, $n$, $n+1$.
>
> Written by the tutor for your question: it is not from your notes or a past paper. Other equations, the wording and the reasoning are not machine-checked.

> [!quote] You
> I cannot picture how the even and odd cases together cover every integer. Is there a figure?

> [!abstract] Diagram
> Case split. A branching figure shows the two cases splitting the whole domain, which is what the learner is trying to picture.; start: Any integer n (negative, zero or positive); end: Every integer is covered, with no gaps; cases: Even: n = 2k / Odd: n = 2k + 1
>
> ![[docs/benchmarks/2026-10-29-pilot-demo/p2-real/Assets/generated/case_split-b7d3837e08d9.svg]]

> [!tip] Tutor-written: Number line picture: even and odd integers alternating and covering all integers
> Picture the integers as evenly spaced points on a line. Colour them alternately: even, odd, even, odd, and so on. Every point gets exactly one colour, so the two cases together cover every integer with no gaps and no overlaps.
>
> **The number line picture**
>
> - Even integers (multiples of 2) sit at: ..., -4, -2, 0, 2, 4, ...  Call these the 'red' points.
>
> - Odd integers sit at: ..., -3, -1, 1, 3, 5, ...  Call these the 'blue' points.
>
> - Reading left to right, the colours go: red, blue, red, blue, ... For example: -2 (red), -1 (blue), 0 (red), 1 (blue), 2 (red).
>
> **Why the alternation never breaks**
>
> 1. Every even integer can be written in the form below, where $k$ is an integer. These are the red points.
>
> $$
> n=2k
> $$
>
> 2. The integer immediately after an even integer is one step to the right. Adding 1 gives the blue points.
>
> $$
> n=2k+1
> $$
>
> 3. The next integer after that is the next red point, because $2k+2$ equals $2(k+1)$, which is even.
>
> $$
> 2k+2=2(k+1)
> $$
>
> 4. So the pattern restarts every 2 steps. Each pair of neighbouring integers, $2k$ and $2k+1$, contains one red and one blue point. As $k$ runs through all integers, these pairs tile the whole line, so no integer is missed.
>
> Your turn: choose any integer you like, such as $-7$, and decide which of the two forms $2k$ or $2k+1$ it fits, then find $k$. Tell me what you get and I will check it with you.
>
> Written by the tutor for your question: it is not from your notes or a past paper. Checked by computer algebra: `2k+2 = 2(k+1)`. Other equations, the wording and the reasoning are not machine-checked.

> [!quote] You
> Give me a question to try on this.

> [!question] Q1 · MCQ · 1 mark · no hints
> A proof starts: 'Let $n$ be any integer. Write $n=2k$ for an integer $k$.' What is the problem?
>
> **A.** An integer cannot be named $n$.
> **B.** It excludes even integers.
> **C.** There is no problem: every integer has this form.
> **D.** This form excludes odd integers.

*A question on this idea. Try it without hints.*

> [!failure] Q1 — Not quite ✗
> **Your answer:** A (fairly sure)
> **Answer:** D: This form excludes odd integers.
>
> The form $2k$ represents even integers. An arbitrary integer may be odd, so the proof needs to cover odd integers too.
>
> ⚑ You were confident but wrong: this is the best moment to fix the idea. Ask why (t).
