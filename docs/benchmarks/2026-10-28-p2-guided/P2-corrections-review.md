# Draft proof corrections for review

These proposed changes are unpublished. The refine no-loss gate still rejects them. Staging does not approve or apply them. Source evidence: Pearson WMA12 January 2022 Q10(ii), question paper PDF page 34 and mark scheme PDF page 23; see docs/RESEARCH.md.

```diff
--- current pack
+++ proposed pack
@@ -3,7 +3,7 @@
   "spec": "P2",
   "version": 1,
   "note": "Subjects/Maths/P2 Pure Mathematics 2/1 Proof.md",
-  "outline": "A proof begins from stated assumptions and reaches a conclusion through justified logical steps. Proof by exhaustion identifies a complete finite domain and checks every case; for two chosen values, include equal-value pairs unless excluded. A universal claim is disproved by one counterexample that satisfies the assumptions and makes the conclusion false. Positive odd integers below 7 are $1,3,5$; their six unordered pairs all have even sums. For $n^2-n+1$, $n=5$ gives $21=3\\times7$, disproving the claim that it is always prime.",
+  "outline": "A proof begins from stated assumptions and reaches a conclusion through justified logical steps. Proof by exhaustion covers a finite, complete set of cases, with a general proof for any case containing infinitely many values; for two chosen values, include equal-value pairs unless excluded. A universal claim is disproved by one counterexample that satisfies the assumptions and makes the conclusion false. Positive odd integers below 7 are $1,3,5$; their six unordered pairs all have even sums. For $n^2-n+1$, $n=5$ gives $21=3\\times7$, disproving the claim that it is always prime.",
   "misconceptions": [
     {
       "id": "m1",
@@ -17,7 +17,7 @@
       "id": "m2",
       "kc": "P2-1.2",
       "statement": "Testing a few cases is proof by exhaustion even when the domain has more cases.",
-      "refutation": "Exhaustion works only after the complete finite set of possible cases has been identified and every case checked.",
+      "refutation": "Identify a complete set of cases and establish the result throughout each case; a case may contain infinitely many values.",
       "contrast": "For positive odd integers below 7 the complete list is $1,3,5$; omitting 5 leaves the argument unfinished.",
       "source": "research"
     },
@@ -54,7 +54,7 @@
       "steps": [
         {
           "do": "List the complete possibilities: $x,y\\in\\{1,3,5\\}$.",
-          "why": "Exhaustion needs a finite, complete domain."
+          "why": "Here the domain is finite, so listing its values gives a complete set of cases."
         },
         {
           "do": "Up to swapping, list $(1,1),(1,3),(1,5),(3,3),(3,5),(5,5)$.",
@@ -573,7 +573,7 @@
       "hints": [
         "Identify the domain first.",
         "Ask whether any allowed integer remains unchecked.",
-        "Only a complete finite list supports exhaustion."
+        "For this finite domain, check every allowed integer."
       ]
     },
     {
@@ -1095,7 +1095,7 @@
       "id": "fc2",
       "kc": "P2-1.2",
       "front": "When is proof by exhaustion valid?",
-      "back": "When all possible cases form a finite complete list and each case is checked."
+      "back": "When the cases cover the whole domain and the result is established for every value in each case."
     },
     {
       "id": "fc3",
@@ -1138,7 +1138,7 @@
         "answer": "A",
         "explanation": "Equal-value pairs are allowed; the other pairs contain values outside the domain."
       },
-      "establish": "Proof by exhaustion means trying all possible cases. First establish a finite, complete list from the assumptions. Then check the conclusion in each case and state that every case has passed. For positive odd integers less than 7, the only values are $1,3,5$. If both $x$ and $y$ may take these values, the unordered pairs are $(1,1),(1,3),(1,5),(3,3),(3,5),(5,5)$. For the claim that $x+y$ is divisible by 2, their sums are $2,4,6,6,8,10$, all even. Swapping a pair gives the same sum, so unordered pairs suffice here. If the question merely says 'odd integers less than 7', negative odd integers are also allowed and this three-value list is incomplete.",
+      "establish": "Proof by exhaustion means covering all possible cases. First establish a finite, complete list of cases from the assumptions. A case can be a single value or a class containing infinitely many values; prove the conclusion for every value in each case. For positive odd integers less than 7, the only values are $1,3,5$. If both $x$ and $y$ may take these values, the unordered pairs are $(1,1),(1,3),(1,5),(3,3),(3,5),(5,5)$. For the claim that $x+y$ is divisible by 2, their sums are $2,4,6,6,8,10$, all even. Swapping a pair gives the same sum, so unordered pairs suffice here. If the question merely says 'odd integers less than 7', negative odd integers are also allowed and this three-value list is incomplete.",
       "connect": "Exhaustion depends on proof structure: the initial assumptions justify the case list, and the final conclusion follows only after every case is checked.",
       "note": "- Identify a finite, complete set of cases.\n- Include equal-value cases unless excluded.\n- Check each case, then conclude for the whole domain.",
       "self_explain": "Why is checking $(1,3)$ enough to cover $(3,1)$ for a sum, while $(3,3)$ still needs checking?",

--- current note
+++ proposed note
@@ -20,9 +20,9 @@
 > In both cases the bracket is an integer, so the product is even. These cases cover every integer, including zero and negative integers; therefore $n(n+1)$ is even for every integer $n$.
 > Checking sample values cannot replace this general step: any finite sample leaves other integers untested.
 
-**Proof by exhaustion** means trying all possible cases. It works when the assumptions lead to a finite, complete list. For example, if $x$ and $y$ are *positive* odd integers less than 7, each must be in $\{1,3,5\}$. The unordered pairs are $(1,1),(1,3),(1,5),(3,3),(3,5),(5,5)$. Their sums are $2,4,6,6,8,10$, each divisible by 2. Swapping the numbers does not change a sum, but equal-value pairs must still be included. Thus every allowed pair has an even sum.
+**Proof by exhaustion** divides the allowed domain into a complete, finite list of cases and establishes the claim in each case. A case may represent one value or a whole class of values. For example, if $x$ and $y$ are *positive* odd integers less than 7, each must be in $\{1,3,5\}$. The unordered pairs are $(1,1),(1,3),(1,5),(3,3),(3,5),(5,5)$. Their sums are $2,4,6,6,8,10$, each divisible by 2. Swapping the numbers does not change a sum, but equal-value pairs must still be included. Thus every allowed pair has an even sum.
 
-The word *positive* matters. “Odd integers less than 7” also includes $-1,-3,-5,\ldots$, so $\{1,3,5\}$ is not an exhaustive list under those assumptions. You would need a general argument, such as writing odd integers as $2a+1$ and $2b+1$, to cover that infinite domain.
+The word *positive* matters. “Odd integers less than 7” also includes $-1,-3,-5,\ldots$, so $\{1,3,5\}$ is not an exhaustive list under those assumptions. To cover that infinite domain, use a general argument, such as writing odd integers as $2a+1$ and $2b+1$; a finite set of general cases can also form an exhaustion proof.
 
 **Disproof by counterexample** targets a statement claiming something for every allowed input. A counterexample is one input that satisfies all assumptions but makes the conclusion false. To disprove “$n^2-n+1$ is prime for every positive integer $n$,” take $n=5$. Then $5^2-5+1=21=3\times7$. Since 21 is composite, the claim is false. A prime result for $n=4$ is not enough to prove the universal claim, and an input outside the domain cannot disprove it.
 

```

## Candidate fingerprints

These SHA-256 hashes identify the original snapshot, proposal and latest disposable integrated candidate used for the source review in `build/work/guided/P2-1-correction-source-review.json`. The diff above shows the correction scope; the candidate also includes the guided pilot additions. The hashes are evidence only: they do not approve corrections or waive no-loss. JSON is canonicalised by sorted keys and compact separators before hashing.

- **original:** `9ca0d4235f94027329d5c2e7f51134c0a5bacb4eb6df233c374f0774a628ba54`
- **proposal:** `0490c5f4f8cdacb3a1d9ad7a4a2d20feda84616e8c7ac80e9ebce859e452b480`
- **candidate:** `1496bd05d3b24a5144485dcaf438e8497bb73b01462c1dd0a8f32622064d0f33`

Rechecked against the disposable candidate and source files: the fingerprints match the recorded review, the original comparison reports seven no-loss findings, and the comparison after staging the proposed corrections reports no additional losses. This consistency check does not establish reviewer identity and does not change the failing refine gate.
