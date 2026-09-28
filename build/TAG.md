# MCQ → KC tagging

**Judge every question yourself, by reading it.** Classification by code is forbidden: no keyword matching, regex rules, scoring scripts or API calls to assign KCs. Code may be used only to count lines and check ids. A previous attempt that keyword-matched produced useless tags; this data decides which questions a student is given for which topic.

Input: `build/work/tag/<code>-<k>.input.txt`, one Cambridge Paper 1 multiple-choice question per line:
`id | stem | options | key`. Syllabus KCs (AS only) are in `build/work/tag/kcs-<code>.txt`: `id | statement`.

For every question, decide which learning outcome(s) it assesses: the KC a student must know to get it right. Usually one; two when the question genuinely needs both (e.g. an uncertainty question inside a kinematics context tags the uncertainty KC and the kinematics KC). Questions run roughly in syllabus order within a paper (Q1 near topic 1, Q40 near the last AS topic); use that as a prior, not a rule.

Papers from 2019–2021 were set on an older syllabus. If a question tests content that no current KC covers, set `"off_syllabus": true` and `"kcs": []`.

Output: `build/work/tag/<code>-<k>.output.jsonl`, one JSON object per input line, same order:

```json
{"id": "9702_s23_12_q3", "kcs": ["9702-1.3.3"], "off_syllabus": false, "conf": 0.9}
```

`conf` is your confidence (0–1) that the KC choice is right. Work through the questions 40 at a time: read each question, decide, then append those 40 lines to the .jsonl before reading the next 40. `off_syllabus` should be rare (a few per paper at most, mainly 2019–2021 papers); if you are marking many, re-check against the KC list. When finished, check: line count equals input line count, every id matches the input order, every KC id exists in the kcs file.
