# P2 Proof pilot: AI-led teaching demonstration (2026-10-29)

`p2-real/` is one real run: the real P2 pack published into a scratch vault (never the learner's), Claude Sonnet as the
learning and marking model, three learner requests through the actual lesson screen. `model_replies.json` holds the
model's raw action replies, `terminal.txt` the Terminal log, `Now.md`/`Lesson.md` what Obsidian gets (image paths
rewritten to sit inside this folder so the repo vault can render them). The older `Lesson.md`, `Now.md` and
`Notes-figure.md` in this folder are the first demo (a physics scratch vault with the P2 card injected).

Verified: the model wrote new, relevant explanations the card did not contain (labelled as the tutor's own, with its
algebra checked by SymPy), chose and drew a case-split diagram, and asked for a question, which the program picked and
marked; Terminal and Obsidian (app, reading view) show the same cards, the diagram and the embedded notes figure.

Not verified: that unchecked prose is correct (only listed identities are checked), model marking of written proofs, answer
protection beyond the existing guard, a model choosing the notes figure in this run (the action works; see tests).
Local Gemma 4 E4B: wrote on-topic but thinner text, sometimes left `text` out (the screen now asks a second focused
request), chose a section of another idea once (refused, not shown) and once returned incomplete JSON.
