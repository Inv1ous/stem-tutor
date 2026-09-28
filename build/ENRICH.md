# KC enrichment spec

You are enriching syllabus knowledge components (KCs) for an A-Level tutor. Each KC is one learning outcome from an official specification (CAIE 9701 Chemistry, CAIE 9702 Physics, or a Pearson Edexcel IAL Maths unit). The IDs and verbatim wording were extracted by script; you add the structure a tutor needs. Your output drives prerequisite ordering, diagnosis and free-text mapping for a real student's two-year course, so accuracy matters more than speed.

## Input

`build/work/graph/<chunk>.input.json`: an array of `{id, subtopic, level, raw, guidance?, context}`. `raw` is the PDF text of the outcome; PDF extraction has broken superscripts, subscripts and fractions (e.g. `am × an = am + n` means $a^m \times a^n = a^{m+n}$). `build/work/graph/all-ids.txt` lists every KC id in all specs with its context (tab-separated). It is large: never read it whole; `grep` it for the candidates you need (e.g. `grep -P '^P1-' all-ids.txt`, `grep -i 'logarithm' all-ids.txt`).

## Output

`build/work/graph/<chunk>.enriched.json`: a JSON array with exactly one object per input KC, in the same order:

```json
{"id": "9702-2.1.7",
 "title": "Solving suvat problems",
 "statement": "solve problems using equations that represent uniformly accelerated motion in a straight line, including the motion of bodies falling in a uniform gravitational field without air resistance",
 "type": "procedural",
 "prereqs": ["9702-2.1.6", "9702-2.1.1"],
 "glossary": ["suvat", "uniform acceleration", "free fall", "v = u + at", "s = ut + 1/2 at^2", "acceleration of free fall"],
 "guidance": "optional, IAL only"}
```

Field rules:

- **title**: at most 8 words, a noun phrase a student would recognise.
- **statement**: the official wording, kept word for word, with broken maths repaired as Obsidian LaTeX using `$…$` only (never `\(`). Keep sub-parts as `(a) …; (b) …`. Chemical formulae in `$\ce{…}$` (e.g. `$\ce{NH4+}$`).
- **guidance** (IAL only): the guidance column cleaned the same way; omit when empty.
- **type**, exactly one of:
  - `factual`: recall of definitions, facts, names, observations, colours, conditions (state, recall, define, give).
  - `conceptual`: understanding relationships and reasons (explain, describe why, understand that, interpret).
  - `procedural`: methods and calculations (calculate, use, solve, determine, derive, sketch, apply).
  Pick the dominant behaviour an examiner assesses.
- **prereqs**: the direct prerequisites only — KCs a student must already know to learn this one — 0 to 4 ids, each present in `all-ids.txt`. Mostly earlier KCs in the same spec. Cross-spec links only for genuine dependencies (e.g. 9702 kinematics on P1 quadratics; 9701 rates on logarithms; S2 on P2 binomial). Leave out anything implied transitively. The graph must stay acyclic: a prerequisite is always something taught earlier in a normal course order.
- **glossary**: 3–8 lowercase terms or phrases a student would say when talking about this KC (key terms, named laws, equation names, symbols written plainly). They are matched against free text, so prefer distinctive phrases over generic words like "energy".

## Before you finish

Run this check and fix everything it reports:

```bash
python3 - <<'EOF'
import json,sys
chunk=sys.argv[1] if len(sys.argv)>1 else "CHUNK"
inp=json.load(open(f"build/work/graph/{chunk}.input.json")); out=json.load(open(f"build/work/graph/{chunk}.enriched.json"))
ids={l.split("\t")[0] for l in open("build/work/graph/all-ids.txt")}
assert [k["id"] for k in inp]==[k["id"] for k in out], "ids/order differ"
for k in out:
    assert k["type"] in ("factual","conceptual","procedural"), k["id"]
    assert all(p in ids and p!=k["id"] for p in k["prereqs"]), k["id"]
    assert 3<=len(k["glossary"])<=8 and len(k["title"].split())<=8, k["id"]
    assert k["statement"].count("$")%2==0 and "\\(" not in k["statement"], k["id"]
print("ok", len(out))
EOF
```

(Replace CHUNK with your chunk name.)

## Writing the output

Work in batches of at most 30 KCs: write each batch as its own file `build/work/graph/<chunk>.part<N>.json` (a JSON array) as soon as it is done, then move to the next batch. When every batch exists, combine them in order with a short python script into `<chunk>.enriched.json`, delete the part files, and run the check. Writing as you go means no work is lost if you are interrupted; if part files already exist when you start, continue from the next KC after the last one written.
