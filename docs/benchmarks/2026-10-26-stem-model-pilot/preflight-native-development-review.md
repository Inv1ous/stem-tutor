# Seven-condition native development preflight

27 October 2026. Scoped CPU-only review: **0 serious findings** in the frozen development diagnostic.

Verified the exact ordered conditions: Python fused user-only/unconstrained reference; native A user-only/no-format,
B user-only/speech-schema, C full-app/no-format, D actual TutorAI/full-schema, production marking and genuine Deep D.
All are attempted regardless of answer quality; fatal guard/server failures stop the run. The six Fast conditions
retain512 tokens/45 seconds and0.7/0.8/20/presence1.5/seed42; Deep retains1024/60 and1.0/0.95/20/presence1.5.
The outer wall limit is360 seconds.

CPU-captured production D is frozen, runtime outgoing payloads must equal their frozen requests, and C equals D
with only `format` removed (`diagnostic.py:100–160`, `287–292`, `448–450`). A/B preserve the same user and options.
The new6.0N/0.50m question is separate from the failed challenge item. Supplied VALID marking criteria/response
use `prompts.judge`, `TutorAI.one_shot` and the real criterion schema; separate gold is `[true,false]`.
These related-family checks are labelled development evidence, with arithmetic/speech meaning requiring review.

Native residency must be empty before and during Python. The parent waits for its child and terminates/kills and
reaps it on cancellation before advancing. Native work is serial; process-local catalogue entries are restored.
Guards cover initial/sustained pressure,512MiB swap growth,20GiB SSD,3GiB OS headroom and total/per-condition
deadlines. Python checks observed14GiB peak; native checks reported `size_vram`, accurately distinguished from
a hard allocation cap. Cleanup unloads the owned candidate and checks empty residency.

The sanitizer drops hidden thought text/unknown token fields before logging; Python exports only public content.
Failures, partial Python prefixes, missing counters and app failures remain observable. Strict schema/decoder
and marking-vector gates remain separate from manual science judgement. No generated code execution appears.
Source/fixture hashes are frozen and checked; output must be new and outside frozen inputs.

Independently reran **nine CPU tests: passed**, plus manifest, matrix/options, C/D isolation and gold-label checks.
Manifest SHA256: `427dd7ff3cd4b4937dbb5ec71c2203ef181ef5bda082d8ec35182f08f23f768a`.
No API/server/GPU/model calls, MLX imports, production/data/weight edits, learner writes or Git operations occurred.
This clears only the bounded diagnosis, without authorising a large batch or asserting a cause for native looping.
