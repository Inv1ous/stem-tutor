"""Generate P2-1 Proof. All numerical claims and option values are checked here."""
import json
from itertools import combinations_with_replacement
from pathlib import Path
import sympy as sp

ROOT = Path(__file__).resolve().parents[3]
SUB = "P2-1"
K1, K2, K3 = (f"{SUB}.{i}" for i in (1, 2, 3))
OUT = ROOT / "build/out/packs/P2/P2-1.json"

odds = [n for n in range(1, 7) if n % 2 == 1]
pairs = list(combinations_with_replacement(odds, 2))
sums = [a + b for a, b in pairs]
assert odds == [1, 3, 5] and len(pairs) == 6
assert sums == [2, 4, 6, 6, 8, 10] and all(s % 2 == 0 for s in sums)
f = lambda n: n*n - n + 1
assert f(5) == 21 and sp.factorint(f(5)) == {3: 1, 7: 1}
assert f(4) == 13 and sp.isprime(f(4))
assert f(6) == 31 and sp.isprime(f(6))
assert f(7) == 43 and sp.isprime(f(7))
assert f(1) == 1 and not sp.isprime(f(1))
assert f(11) == 111 and sp.factorint(f(11)) == {3: 1, 37: 1}
assert all((n*n+n) % 2 == 0 for n in range(-30, 31))
assert [n*n for n in range(1, 6)] == [1, 4, 9, 16, 25]

mis = [
 {"id":"m1","kc":K1,"statement":"Several correct examples prove a claim about every integer.","refutation":"A universal claim needs an argument covering its whole domain. Any finite sample can miss an exception.","contrast":"Checking $n=1,2,3$ does not establish a claim for every integer; one valid counterexample can disprove it.","source":"research"},
 {"id":"m2","kc":K2,"statement":"Testing a few cases is proof by exhaustion even when the domain has more cases.","refutation":"Exhaustion works only after the complete finite set of possible cases has been identified and every case checked.","contrast":"For positive odd integers below 7 the complete list is $1,3,5$; omitting 5 leaves the argument unfinished.","source":"research"},
 {"id":"m3","kc":K2,"statement":"For two numbers, checking only pairs of distinct values covers every case.","refutation":"The two numbers may be equal unless the assumptions exclude equality. Repeated-value pairs must be included.","contrast":"The pair $(3,3)$ is allowed when $x$ and $y$ are positive odd integers below 7.","source":"research"},
 {"id":"m4","kc":K3,"statement":"A single prime value proves a formula is prime for all positive integers.","refutation":"One instance supports only that instance. To disprove a universal prime claim, find one allowed input with a composite output.","contrast":"At $n=5$, $n^2-n+1=21=3\\times7$, so the universal prime claim is false.","source":"research"},
 {"id":"m5","kc":K3,"statement":"A counterexample may be outside the stated domain or merely look suspicious.","refutation":"The input must satisfy every assumption, and the conclusion must demonstrably fail.","contrast":"If the claim is for positive integers, $n=-1$ is inadmissible; $n=5$ is admissible and gives a proven composite value.","source":"research"}
]

def mcq(kc, difficulty, word, stem, options, answer, explanation, hints, distractors=None):
    assert set(options) == set("ABCD") and answer in options
    assert len(set(options.values())) == 4
    it = {"id":f"{SUB}-i{len(items)+1:02}", "kcs":[kc], "kind":"mcq",
          "difficulty":difficulty,"command_word":word,"source":{"type":"generated"},
          "stem":stem,"options":options,"answer":answer,"marks":1,
          "explanation":explanation,"hints":hints,"shuffle":True}
    if distractors: it["distractors"] = distractors
    items.append(it)

def short(kc, difficulty, word, stem, points, explanation, hints):
    items.append({"id":f"{SUB}-i{len(items)+1:02}","kcs":[kc],"kind":"short",
                  "difficulty":difficulty,"command_word":word,"source":{"type":"generated"},
                  "stem":stem,"marks":len(points),
                  "rubric":[{"point":p,"keywords":k} for p,k in points],
                  "explanation":explanation,"hints":hints})

items = []
# Proof structure: six independent retrieval routes, including a demanding argument audit.
mcq(K1,1,"State","Which sequence describes the structure of a mathematical proof?",
 {"A":"Assumptions, justified logical steps, conclusion","B":"Conclusion, examples, assumption",
  "C":"Guess, diagram, conclusion","D":"Examples, pattern, unproved conclusion"},"A",
 "A proof starts with stated assumptions, makes each inference valid, and reaches the claimed conclusion. Examples alone cannot justify a universal conclusion.",
 ["Think about what may be used at the start.","Each line must follow from earlier lines or a stated fact.","Look for a chain from what is given to what is claimed."],{"D":"m1"})
mcq(K1,2,"Explain","A student checks that $n^2+n$ is even for $n=1,2,3$ and concludes it is even for every integer $n$. What is missing?",
 {"A":"A step covering every integer","B":"One more positive example","C":"A decimal approximation","D":"A different order for the three examples"},"A",
 "Three examples do not cover all integers. A proof can write $n^2+n=n(n+1)$ and use the fact that consecutive integers include an even number.",
 ["Compare the number of tested inputs with the stated domain.","A universal statement needs a reason that applies to any allowed input.","Consider what remains untested after three substitutions."],{"B":"m1"})
short(K1,2,"Explain","Explain why the statement of assumptions matters in a proof.",
 [("The assumptions specify the allowed domain or starting facts.",[["domain","allowed","given"],["starting","facts","values","inputs"]]),
  ("Each later step must follow from those assumptions or established results.",[["step","conclusion","inference"],["follow","justify","valid"]])],
 "The assumptions fix exactly which cases are being considered. Logical steps then establish the conclusion for those cases.",
 ["Ask what the claim is about.","A proof needs a justified starting point and justified inferences.","Name the permitted inputs before considering the conclusion."])
mcq(K1,3,"Verify","Which argument proves that $n(n+1)$ is even for every integer $n$?",
 {"A":"Consecutive integers include an even integer; therefore their product is even.",
  "B":"The result holds for $n=1,2,3$; therefore it holds for every integer.",
  "C":"The product is usually even, so the exceptions can be ignored.",
  "D":"Assume the product is even; therefore it is even."},"A",
 "Every integer and its successor are consecutive, so one factor is even and their product is even. The other arguments sample, ignore possible exceptions, or assume the conclusion.",
 ["Find an argument valid for any integer.","Use a property of two consecutive integers.","Check that the conclusion follows from a fact rather than being assumed."],{"B":"m1"})
short(K1,3,"State","State the conclusion reached from the assumptions '$n$ is an integer' and '$n=2k$ for some integer $k$' after calculating $n^2=4k^2$.",
 [("$n^2$ is divisible by 4.",[["n^2","square"],["divisible","multiple"],["4"]])],
 "Since $k^2$ is an integer, $n^2=4k^2$ is a multiple of 4.",
 ["Interpret the displayed factor of 4.","An integer multiple of 4 is divisible by 4.","Use that $k^2$ remains an integer."])
mcq(K1,5,"Explain","A proposed proof begins, 'Let $n$ be any positive integer. Since $n=2k$, $n^2$ is divisible by 4.' Identify the flaw.",
 {"A":"Not every positive integer has the form $2k$.","B":"Squaring $2k$ does not give $4k^2$.",
  "C":"A multiple of 4 is never even.","D":"A proof may not begin with an arbitrary integer."},"A",
 "Writing $n=2k$ silently restricts $n$ to even integers, contrary to the original domain. The algebra is valid only under that added assumption.",
 ["Compare the chosen form of $n$ with its stated domain.","Test whether the form can represent an odd integer.","Find the first step that is not justified by the assumptions."])

# Exhaustion: explicitly finite domains and equal-value pairs.
mcq(K2,1,"State","Which set lists all positive odd integers less than 7?",
 {"A":"$\\{1,3,5\\}$","B":"$\\{1,3\\}$","C":"$\\{1,3,5,7\\}$","D":"$\\{3,5\\}$"},"A",
 "The positive odd integers below 7 are 1, 3 and 5. Including 7 violates the strict bound; omitting 1 or 5 misses a case.",
 ["Start at the smallest positive odd integer.","Advance by two while staying below the bound.","Check whether the upper bound itself is allowed."],{"B":"m2","D":"m2"})
mcq(K2,2,"Find","How many unordered pairs $(x,y)$, allowing $x=y$, can be formed from $\\{1,3,5\\}$?",
 {"A":str(len(pairs)),"B":str(len(list(combinations_with_replacement(odds,2)))-3),
  "C":str(len(odds)**2),"D":str(len(odds)+2)},"A",
 "There are three equal pairs and three pairs with distinct entries, so six unordered pairs. Counting only distinct pairs omits cases; counting all ordered pairs double counts swaps.",
 ["List pairs beginning with 1, then with 3, then with 5.","Remember that a number can be paired with itself.","Treat a swapped pair as the same pair here."],{"B":"m3"})
short(K2,3,"Prove","Let $x$ and $y$ be positive odd integers less than 7. Prove by exhaustion that $x+y$ is divisible by 2.",
 [("Lists the complete allowed values $1,3,5$.",[["1"],["3"],["5"]]),
  ("Checks all six unordered pairs, including equal pairs.",[["six","6","all"],["pairs","cases"],["equal","same","repeated"]]),
  ("Concludes all sums are even or divisible by 2.",[["sum","sums"],["even","divisible by 2"]])],
 "The unordered pairs are $(1,1),(1,3),(1,5),(3,3),(3,5),(5,5)$, with sums $2,4,6,6,8,10$. All six sums are multiples of 2.",
 ["First list every allowed value.","A swapped pair has the same sum, but an equal-value pair is still allowed.","Compute the sum for every unordered pair."])
mcq(K2,3,"Verify","A student checks $(1,1),(1,3),(1,5),(3,5),(5,5)$ for positive odd $x,y<7$. Is this exhaustive?",
 {"A":"No: $(3,3)$ is missing.","B":"Yes: every distinct-value pair is present.",
  "C":"No: $(7,7)$ is missing.","D":"No: there are infinitely many positive odd integers below 7."},"A",
 "The pair $(3,3)$ satisfies the assumptions and is missing. Equal values must be checked unless the problem requires distinct values.",
 ["Check the complete set of allowed values.","Try pairing the middle value with itself.","The strict bound rules out the endpoint."],{"B":"m3"})
short(K2,4,"Explain","Explain why checking $n=1,2,3,4,5$ proves a statement for every integer $n$ with $1\\leq n\\leq5$, provided each check succeeds.",
 [("The assumptions leave exactly five possible integer values.",[["five","5"],["possible","allowed","integer"]]),
  ("Every case has been checked, so the conclusion holds throughout the domain.",[["every","all"],["checked","tested"],["conclusion","statement","holds"]])],
 "The domain is finite and consists exactly of those five integers. Successful checks for each one cover the entire claim.",
 ["Identify the domain first.","Ask whether any allowed integer remains unchecked.","Only a complete finite list supports exhaustion."])
mcq(K2,5,"Explain","A student writes, 'If $x,y$ are odd integers less than 7, then $x,y\\in\\{1,3,5\\}$; checking those values proves the claim.' Why is the argument incomplete as stated?",
 {"A":"Negative odd integers also satisfy the assumptions.","B":"The three displayed numbers are not odd.",
  "C":"The sum of two odd integers is never even.","D":"The number 7 must be included."},"A",
 "The phrase 'odd integers less than 7' includes negative odd integers, so the proposed finite list is not complete. Adding 'positive' makes that list exhaustive.",
 ["Read the domain literally.","Is there a lower bound on the integers?","Try an odd integer below zero."],{"B":"m2"})

# Counterexample: compute all displayed outputs, including a second composite.
mcq(K3,1,"State","What is sufficient to disprove a claim that a property holds for every positive integer?",
 {"A":"One allowed input for which the property fails","B":"Three allowed inputs for which it holds",
  "C":"A guess that a failure exists","D":"An input outside the stated domain"},"A",
 "A universal claim fails as soon as one admissible counterexample is established. Examples where it succeeds cannot disprove it.",
 ["Focus on the word 'every'.","Ask how many failures are needed to make 'every' false.","Check that any proposed input satisfies the assumptions."],{"D":"m5"})
mcq(K3,2,"Calculate","For $f(n)=n^2-n+1$, which value is $f(5)$?",
 {"A":str(f(5)),"B":str(5*5+5+1),"C":str(5*5-5),"D":str(5*5-1)},"A",
 "Substitution gives $f(5)=25-5+1=21$. This is composite because $21=3\\times7$.",
 ["Substitute for every occurrence of $n$.","Square before subtracting.","Keep the final $+1$ term."])
short(K3,3,"Prove","Disprove the claim '$n^2-n+1$ is prime for every positive integer $n$'.",
 [("Chooses the admissible input $n=5$.",[["n=5","n = 5","5"]]),
  ("Calculates $n^2-n+1=21$.",[["21"]]),
  ("Shows $21=3\\times7$, so it is composite and the universal claim is false.",[["3"],["7"],["composite","not prime"]])],
 "For the positive integer $n=5$, the expression equals $25-5+1=21=3\\times7$. Since 21 is composite, the statement for every positive integer is false.",
 ["You need just one allowed failure.","Look for an input that makes the output divisible by 3.","After substitution, factor the output to establish that it is not prime."])
mcq(K3,3,"Explain","A student finds $f(4)=13$ for $f(n)=n^2-n+1$ and says this proves $f(n)$ is prime for every positive integer. What is the error?",
 {"A":"One prime output cannot establish a universal claim.","B":"$13$ is composite.",
  "C":"$4$ is not a positive integer.","D":"A counterexample must use a negative integer."},"A",
 "The calculation at $n=4$ is correct and 13 is prime, but it proves only that instance. The value $n=5$ yields 21, which is composite.",
 ["Separate checking one input from proving all inputs.","The calculation at 4 may be correct yet insufficient.","Test a neighboring positive integer."],{"B":"m4"})
mcq(K3,4,"Verify","Which calculation is a valid counterexample to '$n^2-n+1$ is prime for every positive integer $n$'?",
 {"A":f"$n=5:\\ {f(5)}=3\\times7$",
  "B":f"$n=4:\\ {f(4)}$ is prime",
  "C":f"$n=6:\\ {f(6)}$ is prime",
  "D":f"$n=7:\\ {f(7)}$ is prime"},"A",
 "At the allowed input $n=5$, the output is $21=3\\times7$, so it is not prime. The other calculations give prime values and cannot refute the universal claim.",
 ["A counterexample must make the claimed property fail.","Prime outputs support their individual cases.","Find the option with a factorisation into smaller integers."],{"B":"m4"})
short(K3,5,"Explain","A claim says '$n^2-n+1$ is prime for every positive integer $n$'. Explain why choosing $n=-1$ is not a valid counterexample, even if its output were composite.",
 [("$-1$ is not a positive integer and so violates the assumption.",[["-1"],["not positive","negative","outside"]]),
  ("A counterexample must be within the stated domain and make the conclusion false.",[["counterexample"],["domain","allowed","assumption"],["false","fail","composite"]])],
 "The input $-1$ is outside the positive-integer domain, so it cannot refute the stated claim. A valid counterexample must satisfy the assumptions and violate the conclusion.",
 ["Look at the quantifier's domain.","Check whether the proposed input is admissible.","Only an allowed input can refute the stated universal claim."],)

worked = [
 {"id":"we1","kc":K2,"problem":"Prove by exhaustion that $x+y$ is divisible by 2 when $x,y$ are positive odd integers less than 7.",
  "steps":[
   {"do":"List the complete possibilities: $x,y\\in\\{1,3,5\\}$.","why":"Exhaustion needs a finite, complete domain."},
   {"do":"Up to swapping, list $(1,1),(1,3),(1,5),(3,3),(3,5),(5,5)$.","why":"The sum is unchanged by swapping, but equal-value pairs still count."},
   {"do":"Their sums are $2,4,6,6,8,10$, all divisible by 2.","why":"Checking every permitted pair establishes the universal conclusion for this domain."}],
  "faded":{"id":"we1f","problem":"If $x,y$ are positive odd integers less than 5, how many unordered pairs must be checked in a proof by exhaustion?","answer":{"value":len(list(combinations_with_replacement([1,3],2))),"unit":"","exact":True},"blank_from":1}},
 {"id":"we2","kc":K3,"problem":"Disprove the claim that $n^2-n+1$ is prime for every positive integer $n$.",
  "steps":[
   {"do":"Choose the admissible input $n=5$.","why":"A universal claim needs only one valid counterexample to be false."},
   {"do":"Calculate $5^2-5+1=21$.","why":"The output must be evaluated exactly before testing primality.",
    "check":{"kind":"numeric","answer":{"value":f(5),"unit":"","exact":True}}},
   {"do":"Factor $21=3\\times7$. Therefore 21 is composite, so the claim is false.","why":"A factorisation using factors greater than 1 proves the output is not prime."}],
  "faded":{"id":"we2f","problem":"Disprove the claim that $n^2-n+1$ is prime for every integer $n\\geq10$ by using $n=11$. Calculate the output and factor it.","answer":{"value":f(11),"unit":"","exact":True},"blank_from":1}}
]

pack = {
 "subtopic":SUB,"spec":"P2","version":1,
 "note":"Subjects/Maths/P2 Pure Mathematics 2/1 Proof.md",
 "outline":"A proof begins from stated assumptions and reaches a conclusion through justified logical steps. Proof by exhaustion identifies a complete finite domain and checks every case; for two chosen values, include equal-value pairs unless excluded. A universal claim is disproved by one counterexample that satisfies the assumptions and makes the conclusion false. Positive odd integers below 7 are $1,3,5$; their six unordered pairs all have even sums. For $n^2-n+1$, $n=5$ gives $21=3\\times7$, disproving the claim that it is always prime.",
 "misconceptions":mis,"worked":worked,"items":items,
 "flashcards":[
  {"id":"fc1","kc":K1,"front":"State the basic structure of a mathematical proof.","back":"State the assumptions, give justified logical steps, and reach the required conclusion."},
  {"id":"fc2","kc":K2,"front":"When is proof by exhaustion valid?","back":"When all possible cases form a finite complete list and each case is checked."},
  {"id":"fc3","kc":K3,"front":"What makes a valid counterexample to a universal statement?","back":"An input satisfying the assumptions for which the claimed conclusion is false."}
 ],"diagrams":[]
}
assert len(items) == 18
assert all(len(it.get("hints",[])) == 3 for it in items)
assert all(it["command_word"] in {"State","Explain","Verify","Find","Calculate","Prove"} for it in items)
OUT.parent.mkdir(parents=True,exist_ok=True)
OUT.write_text(json.dumps(pack,ensure_ascii=False,indent=1)+"\n")
print(f"Wrote {OUT}: {len(items)} items, {len(worked)} worked examples")
