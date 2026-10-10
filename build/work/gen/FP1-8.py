"""Generate FP1-8. SymPy computes and verifies every numerical result."""
import json
from pathlib import Path
from sympy import Matrix, summation, symbols, simplify, factor

ROOT = Path(__file__).resolve().parents[3]
SUB = "FP1-8"
KC = "FP1-8.1"
NOTE = "Subjects/Maths/FP1 Further Pure Mathematics 1/8 Proof.md"
n, r, k = symbols("n r k", integer=True, positive=True)

def value(x):
    return {"value": float(x), "unit": "", "exact": True}

def check(x):
    return {"kind": "numeric", "answer": value(x)}

def step(do, why, x=None):
    out = {"do": do, "why": why}
    if x is not None:
        out["check"] = check(x)
    return out

def worked(idx, problem, steps, faded_problem, faded_answer):
    return {"id": f"we{idx}", "kc": KC, "problem": problem, "steps": steps,
            "faded": {"id": f"we{idx}f", "problem": faded_problem,
                      "answer": value(faded_answer), "blank_from": 1}}

def base(kind, stem, difficulty, command, marks):
    return {"id": f"{SUB}-i{len(items)+1:02}", "kcs": [KC], "kind": kind,
            "difficulty": difficulty, "command_word": command,
            "source": {"type": "generated"}, "stem": stem, "marks": marks}

def numeric(stem, ans, explanation, hints, difficulty=2, wrong=()):
    out = base("numeric", stem, difficulty, "Calculate", 2)
    assert len(hints) == 3 and all(simplify(ans - x) != 0 for x, _ in wrong)
    out.update(answer=value(ans), explanation=explanation, hints=hints,
               distractors=[{"value": float(x), "misconception": m} for x, m in wrong])
    items.append(out)

def mcq(stem, opts, answer, explanation, hints, wrong, difficulty=2):
    out = base("mcq", stem, difficulty, "State", 1)
    assert len(hints) == 3 and len(set(opts.values())) == 4
    out.update(options=opts, answer=answer, explanation=explanation, hints=hints,
               distractors=wrong, shuffle=True)
    items.append(out)

def structured(stem, points, difficulty=4):
    out = base("structured", stem, difficulty, "Prove", len(points))
    out["scheme"] = [{"mark": m, "point": p} for m, p in points]
    items.append(out)

S_cube = summation(r**3, (r, 1, n))
S_pairs = summation(r*(r+1), (r, 1, n))
assert simplify(S_cube - n**2*(n+1)**2/4) == 0
assert simplify(S_pairs - n*(n+1)*(n+2)/3) == 0
assert simplify(S_cube.subs(n,k) + (k+1)**3 - S_cube.subs(n,k+1)) == 0
assert simplify(S_pairs.subs(n,k) + (k+1)*(k+2) - S_pairs.subs(n,k+1)) == 0

A = Matrix([[1, 1], [0, 1]])
An = Matrix([[1, n], [0, 1]])
assert A**0 == An.subs(n, 0)
assert simplify(A*An - An.subs(n, n+1)) == Matrix.zeros(2)

mis = [
    ("m1", "Checking a few values proves a statement for every positive integer.",
     "A finite list of cases does not establish all positive integers; the inductive step must work for arbitrary $k$.",
     "Prove the base case and then $P(k)\\Rightarrow P(k+1)$ for arbitrary $k$."),
    ("m2", "The induction hypothesis may be assumed true at $k+1$.",
     "Only $P(k)$ is assumed; $P(k+1)$ must be obtained from it.",
     "Add the new term or apply the recurrence to the expression at $k$."),
    ("m3", "A divisibility proof can end by checking a few remainders.",
     "The step must exhibit the next expression as a multiple of the divisor using the hypothesis.",
     "Write the next expression as a multiple of the previous one plus a divisible remainder."),
    ("m4", "Matrix induction needs only an entrywise pattern from small powers.",
     "The pattern is a conjecture until the matrix product establishes the $k+1$ case.",
     "Multiply the assumed $A^k$ by $A$ in the stated order and compare every entry."),
]
misconceptions = [{"id": mid, "kc": KC, "statement": s, "refutation": ref,
                   "contrast": con, "source": "research"} for mid, s, ref, con in mis]

worked_examples = [
    worked(1, "Show that $\\sum_{r=1}^{n}r^3=\\frac14n^2(n+1)^2$ for every positive integer $n$.", [
        step("At $n=1$, the sum is $1$ and $\\frac14(1)^2(2)^2=1$.", "This establishes the base case.", S_cube.subs(n,1)),
        step("Assume $\\sum_{r=1}^{k}r^3=\\frac14k^2(k+1)^2$ for an arbitrary positive integer $k$.", "This is the induction hypothesis, not the result to be proved."),
        step("$\\sum_{r=1}^{k+1}r^3=\\frac14k^2(k+1)^2+(k+1)^3=\\frac14(k+1)^2(k+2)^2$.", "Add the new term, then factor; this is the claimed form at $k+1$.", S_cube.subs(n,2)),
        step("Therefore the identity holds for every positive integer $n$ by induction.", "The base and implication together cover all positive integers.")],
        "Calculate $\\sum_{r=1}^{4}r^3$ from the proved formula.", S_cube.subs(n,4)),
    worked(2, "Prove that $3^{2n+1}+1$ is divisible by $4$ for every non-negative integer $n$.", [
        step("At $n=0$, $3^{1}+1=4$, which is divisible by $4$.", "Start at the first value named in the claim.", 3**1+1),
        step("Assume $3^{2k+1}+1=4q$ for some integer $q$.", "Divisibility must be expressed as an integer multiple."),
        step("$3^{2(k+1)+1}+1=9(3^{2k+1}+1)-8=4(9q-2)$.", "The hypothesis makes the new expression an explicit multiple of $4$."),
        step("Since $9q-2$ is an integer, the claim follows by induction.", "State why the new quotient is an integer.")],
        "Calculate the integer quotient $(3^{2(2)+1}+1)/4$.", (3**5+1)//4),
    worked(3, "Given $u_1=1$ and $u_{n+1}=3u_n+4$, prove that $u_n=3^n-2$.", [
        step("At $n=1$, $3^1-2=1=u_1$.", "The formula must match the supplied initial term.", 3**1-2),
        step("Assume $u_k=3^k-2$.", "Use the claimed formula only at $k$."),
        step("$u_{k+1}=3(3^k-2)+4=3^{k+1}-2$.", "Substitute the hypothesis into the given recurrence."),
        step("Hence $u_n=3^n-2$ for every $n\\geq1$ by induction.", "The recurrence carries the valid base case onward.")],
        "Calculate $u_4$ using the proved formula.", 3**4-2),
    worked(4, "For $A=\\begin{pmatrix}1&1\\\\0&1\\end{pmatrix}$, prove that $A^n=\\begin{pmatrix}1&n\\\\0&1\\end{pmatrix}$ for non-negative integers $n$.", [
        step("At $n=0$, $A^0=I=\\begin{pmatrix}1&0\\\\0&1\\end{pmatrix}$.", "The claimed matrix gives the identity at the first value."),
        step("Assume $A^k=\\begin{pmatrix}1&k\\\\0&1\\end{pmatrix}$.", "This is the matrix induction hypothesis."),
        step("$A^{k+1}=A^kA=\\begin{pmatrix}1&k\\\\0&1\\end{pmatrix}\\begin{pmatrix}1&1\\\\0&1\\end{pmatrix}=\\begin{pmatrix}1&k+1\\\\0&1\\end{pmatrix}$.", "Multiply the matrices and compare all four entries."),
        step("The formula follows for every non-negative integer $n$ by induction.", "The base case and step establish the claim.")],
        "Calculate the $(1,2)$ entry of $A^7$ from the proved formula.", (A**7)[0,1]),
]

items = []
mcq("State which pair of arguments completes a proof by induction of a claim $P(n)$ for all positive integers $n$.",
    {"A": "Prove $P(1)$ and prove $P(k)\\Rightarrow P(k+1)$ for arbitrary positive integer $k$.",
     "B": "Check $P(1)$, $P(2)$ and $P(3)$ only.",
     "C": "Assume $P(k+1)$ and deduce $P(k)$ only.",
     "D": "Prove $P(k)$ for one unspecified value of $k$ only."}, "A",
    "The base case starts the chain and the implication carries truth to every following integer. A finite check cannot cover all integers.",
    ["Think of the first link in a chain.", "Ask what carries truth from one integer to the next.", "Name the base and the implication separately."], {"B":"m1","C":"m2","D":"m1"})

for N in (4, 6):
    ans = S_cube.subs(n,N)
    numeric(f"Calculate $\\sum_{{r=1}}^{{{N}}}r^3$ using the proved identity $\\sum_{{r=1}}^n r^3=\\frac14n^2(n+1)^2$.", ans,
        f"Substitution gives $\\frac14({N})^2({N+1})^2={ans}$.",
        ["Use the stated closed form.", "Substitute the upper limit for $n$.", "Square each of the consecutive factors before dividing by four."],
        wrong=[(sum(x**2 for x in range(1,N+1)),"m1")])

structured("Prove by induction that $\\sum_{r=1}^n r(r+1)=\\frac13n(n+1)(n+2)$ for every positive integer $n$.", [
    ("B1", "At $n=1$, both sides equal $2$."),
    ("M1", "Assume the identity holds at an arbitrary positive integer $k$."),
    ("M1", "Add $(k+1)(k+2)$ to the assumed sum."),
    ("A1", "Factor the result as $\\frac13(k+1)(k+2)(k+3)$ and conclude by induction.")], 4)

mcq("State the correct expression for $3^{2(k+1)+1}+1$ in terms of $3^{2k+1}+1$.",
    {"A":"$9(3^{2k+1}+1)-8$", "B":"$3(3^{2k+1}+1)-2$",
     "C":"$9(3^{2k+1}+1)$", "D":"$3^{2k+1}+1+2$"}, "A",
    "Expanding the first expression gives $3^{2k+3}+1$, so the induction hypothesis makes it a multiple of $4$.",
    ["Compare successive exponents.", "The exponential term gains a factor when $n$ increases by one.", "Adjust the constant after multiplying the whole previous expression."],
    {"B":"m3","C":"m3","D":"m3"}, 3)

for N in (2, 3):
    num = 3**(2*N+1)+1
    q, rem = divmod(num,4)
    assert rem == 0
    numeric(f"Calculate the integer quotient $q$ such that $3^{{2({N})+1}}+1=4q$.", q,
        f"$3^{{2({N})+1}}+1={num}=4({q})$.",
        ["Evaluate the exponent first.", "Add one to the power of three.", "Divide the resulting integer by four."],
        wrong=[(num,"m3")])

structured("Prove by induction that $3^{2n+1}+1$ is divisible by $4$ for every non-negative integer $n$.", [
    ("B1", "At $n=0$, the expression is $4$."),
    ("M1", "Assume $3^{2k+1}+1=4q$ for an integer $q$."),
    ("M1", "Write the next expression as $9(3^{2k+1}+1)-8$."),
    ("A1", "Obtain $4(9q-2)$ and conclude divisibility by induction.")], 4)

mcq("Given $u_{n+1}=3u_n+4$, $u_1=1$ and the hypothesis $u_k=3^k-2$, state the expression obtained directly for $u_{k+1}$.",
    {"A":"$3(3^k-2)+4$", "B":"$3^{k+1}-2$ without using the recurrence",
     "C":"$3(3^{k+1}-2)+4$", "D":"$3^k-2+4$"}, "A",
    "Substitute the hypothesis at $k$ into the supplied recurrence, then simplify to the claimed form. Option C assumes the next case prematurely.",
    ["Start from the recurrence.", "Replace only $u_k$ using the hypothesis.", "Keep multiplication by three and addition of four visible."],
    {"B":"m2","C":"m2","D":"m2"}, 3)

for N in (4, 5):
    ans = 3**N-2
    numeric(f"Calculate $u_{N}$ if $u_1=1$, $u_{{n+1}}=3u_n+4$ and $u_n=3^n-2$ has been proved.", ans,
        f"The proved formula gives $u_{N}=3^{N}-2={ans}$.",
        ["Use the established general term.", "Replace $n$ by the requested index.", "Evaluate the power before subtracting two."],
        wrong=[(3**(N-1)-2,"m2")])

structured("Given $u_1=1$ and $u_{n+1}=3u_n+4$, prove by induction that $u_n=3^n-2$ for all positive integers $n$.", [
    ("B1", "Check $u_1=3^1-2=1$."),
    ("M1", "Assume $u_k=3^k-2$."),
    ("M1", "Substitute into $u_{k+1}=3u_k+4$."),
    ("A1", "Simplify to $3^{k+1}-2$ and conclude by induction.")], 4)

mcq("For $A=\\begin{pmatrix}1&1\\\\0&1\\end{pmatrix}$, state the base case for a proof of $A^n=\\begin{pmatrix}1&n\\\\0&1\\end{pmatrix}$ for $n\\geq0$.",
    {"A":"$A^0=I$ and the proposed matrix at $n=0$ is $I$.",
     "B":"$A^0=A$ and the proposed matrix at $n=0$ is $A$.",
     "C":"$A^1=I$ and the proposed matrix at $n=1$ is $I$.",
     "D":"Checking $A^2$ alone establishes every power."}, "A",
    "A zero power is the identity matrix, matching the proposed form at zero. One isolated power cannot establish the general statement.",
    ["Find the first allowed index.", "Recall the zeroth power of a square matrix.", "Substitute zero into the proposed matrix."],
    {"D":"m4"}, 2)

for N in (5, 8):
    ans = (A**N)[0,1]
    assert ans == An.subs(n,N)[0,1]
    numeric(f"Calculate the $(1,2)$ entry of $A^{N}$ for $A=\\begin{{pmatrix}}1&1\\\\0&1\\end{{pmatrix}}$.", ans,
        f"The proved form is $A^n=\\begin{{pmatrix}}1&n\\\\0&1\\end{{pmatrix}}$, giving entry $(1,2)$ equal to ${ans}$.",
        ["Use the form of a general power.", "Identify the entry that changes with the exponent.", "Substitute the requested exponent into that entry."],
        wrong=[(N+1,"m4")])

structured("For $A=\\begin{pmatrix}1&1\\\\0&1\\end{pmatrix}$, prove by induction that $A^n=\\begin{pmatrix}1&n\\\\0&1\\end{pmatrix}$ for every non-negative integer $n$.", [
    ("B1", "Check $A^0=I$, matching the proposed matrix at $n=0$."),
    ("M1", "Assume $A^k=\\begin{pmatrix}1&k\\\\0&1\\end{pmatrix}$."),
    ("M1", "Multiply the assumed $A^k$ by $A$ to obtain $A^{k+1}$."),
    ("A1", "Show the product is $\\begin{pmatrix}1&k+1\\\\0&1\\end{pmatrix}$ and conclude by induction.")], 5)

pack = {"subtopic": SUB, "spec": "FP1", "version": 1, "note": NOTE,
        "outline": "Mathematical induction proves a claim for every integer in a stated range. Verify the first allowed value, assume the claim at an arbitrary $k$, then deduce it at $k+1$ and conclude. For series, add the new term; for divisibility, exhibit an integer multiple; for recurrence sequences, substitute the assumed general term; for matrix powers, multiply the assumed power by the given matrix. The base case and the inductive step are both essential.",
        "misconceptions": misconceptions, "worked": worked_examples, "items": items,
        "flashcards": [{"id":"fc1","kc":KC,"front":"State the two parts needed to prove a claim by mathematical induction for all integers $n\\geq n_0$.",
                        "back":"Verify the base case $P(n_0)$; then, for arbitrary $k\\geq n_0$, assume $P(k)$ and prove $P(k+1)$. Conclude the claim holds for all $n\\geq n_0$."}],
        "diagrams": []}
out = ROOT / "build/out/packs/FP1/FP1-8.json"
out.parent.mkdir(parents=True, exist_ok=True)
out.write_text(json.dumps(pack, ensure_ascii=False, indent=1))
print(f"Wrote {out}: {len(items)} items, {len(worked_examples)} worked")
