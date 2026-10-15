#!/usr/bin/env python3
"""Stands in for `codex exec` (the lesson writer) and for `claude -p` (the blind checker) in the shortcut generator tests.

FAKE_SG_MODE=bad          every lesson has a hint that gives its answer away
FAKE_SG_MODE=bad_first    the first run is bad, later runs are good (needs FAKE_SG_COUNT=<file>)
FAKE_SG_MODE=garbage      the output file is not JSON
FAKE_SG_MODE=limit        print a usage-limit message and exit 1
FAKE_SG_ONLY=<id>         write a lesson for this id only, not the whole batch
FAKE_SG_WRONG=1         as Claude: answer sums wrongly (by one)
FAKE_ARGV=<file>          save the command line there
Claude side: answers a stem "Evaluate $a + b$" with a+b, an mcq with its first option's letter (A).
"""
import json
import os
import re
import sys

args = sys.argv[1:]
if "app-server" in args:
    sys.exit(0)
if os.environ.get("FAKE_ARGV"):
    open(os.environ["FAKE_ARGV"], "w").write(json.dumps(args))


def lesson(lid: str, bad: bool, n: int) -> dict:
    a, b = n + 2, n + 5
    ans = a + b
    return {
        "id": lid, "hook": "The long way takes four lines.", "when": "Two numbers are added.", "idea": "Add them: $a + b$.",
        "why": "Holds for any real numbers.", "steps": ["Read the numbers.", "Add."],
        "worked": {"question": f"Evaluate ${a} + {b}$.", "long": "Count on.", "short": "Add.", "saving": "Time."},
        "pitfalls": ["Dropping a sign."], "check": "Estimate first.",
        "practice": [
            {"kind": "numeric", "stem": f"Evaluate ${a} + {b}$.", "options": {c: "" for c in "ABCD"}, "answer": str(ans),
             "hints": ["Look at the operation.", "It is a sum.", f"The total is {ans}." if bad else "Add the two."],
             "explanation": f"${a} + {b} = {ans}$.", "shortcut_use": "Direct addition."},
            {"kind": "mcq", "stem": "Which is the sum of $1 + 1$?", "options": {"A": "2", "B": "3", "C": "4", "D": "5"},
             "answer": "A", "hints": ["Add.", "Two ones.", "Count up from one."],
             "explanation": "$1 + 1 = 2$.", "shortcut_use": "Direct addition."}],
        "recall": [{"q": "What does $a + b$ give?", "a": "The sum."}, {"q": "When does it hold?", "a": "Always."}]}


if "exec" in args:
    prompt = args[-1]
    out = args[args.index("-o") + 1]
    mode = os.environ.get("FAKE_SG_MODE", "")
    if mode == "limit":
        print("You've hit your usage limit.")
        sys.exit(1)
    count = 0
    if os.environ.get("FAKE_SG_COUNT"):
        path = os.environ["FAKE_SG_COUNT"]
        count = int(open(path).read()) if os.path.exists(path) else 0
        open(path, "w").write(str(count + 1))
    ids = re.findall(r"^### ID: (\S+)$", prompt, flags=re.M)
    if os.environ.get("FAKE_SG_ONLY"):
        ids = [i for i in ids if i == os.environ["FAKE_SG_ONLY"]]
    bad = mode == "bad" or (mode == "bad_first" and count == 0)
    if mode == "garbage":
        open(out, "w").write("not json")
    else:
        open(out, "w").write(json.dumps({"lessons": [lesson(i, bad, k) for k, i in enumerate(ids)]}))
else:
    prompt = args[args.index("-p") + 1]
    m = re.search(r"Evaluate \$(\d+) \+ (\d+)\$", prompt)
    if m:
        reply = str(int(m[1]) + int(m[2]) + (1 if os.environ.get("FAKE_SG_WRONG") else 0))
    else:
        reply = "A"
    print(json.dumps({"type": "result", "subtype": "success", "is_error": False, "total_cost_usd": 0.01, "result": reply}))
