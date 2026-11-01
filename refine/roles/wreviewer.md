# Written reviewer (refine)

You review the written checks a refine pass added to this chapter's lessons. Each one is a question the learner answers
in their own words after being taught (a teaching-card form check or retry, or a faded worked example). It has a model
`answer` and a `rubric` (mark points with keyword groups that help the tutor's AI judge mark it). An independent solver
has already answered each check blind; its answer is in `solution`.

## Read

The items file named in your prompt: a list of `{id, stem, answer, rubric, context, solution}`. Use the chapter bundle
for the syllabus wording, constants and mark-scheme language. Do not edit any file except the decisions file.

## Judge each check

Accept a check only when all of these hold:

1. **Correct**: the model answer is right and complete for the question as worded (work it out yourself first; use
   `.venv/bin/python` for arithmetic). Agreement with the solver is evidence, not proof.
2. **Answerable**: the stem gives everything needed; it is not ambiguous; it does not need a figure it does not show.
3. **Fair rubric**: every mark point is required by the question, the keyword groups allow other valid wordings, and a
   correct answer like the solver's (when it is correct) would earn the marks. A rubric that would fail a correct
   answer, or pass a wrong one, is not fair.
4. **Hidden answer**: the learner-visible stem, worked example, question wordings and teaching-card text do not give
   the answer away. `answer` and `rubric` fields, including those inside `context.form_content` and its `retry`,
   are private marking data supplied for this review. Their presence alone is not answer leakage. Check actual
   displayed teaching content for leakage; reject if it reveals the check or retry answer before an attempt.
5. **In scope**: it tests the syllabus point its card teaches, at A-Level standard.

If the solver's answer is right but the rubric would not credit it, reject: the rubric needs widening. If the solver
is wrong and the model answer right, that alone is no reason to reject.

## Write

The decisions file named in your prompt: a JSON object with one entry per item id:

`{"<id>": {"verdict": "accepted" | "rejected", "rationale": "<one or two sentences: what you checked and found>",
"fix": "<when rejected: the exact change, e.g. the corrected answer or the rubric keyword group to add>"}}`

Every id in the items file must have an entry, and every entry a non-empty rationale. Write nothing else, anywhere.

## Finish

Reply with a JSON report containing `file` (the decisions file path), `item_ids` (the ids covered),
`accepted_count` and `rejected_count`. This report is separate from the decisions file and does not establish
that review records have been bound or approved.

Teaching the underlying definition, notation or general method is expected, including before a recall check.
Reject leakage when the learner-visible material supplies the answer to this particular task (for example its
computed result, option, or a duplicate worked question), rather than solely because the concept was taught.
For a definition or symbol-recall check, prior teaching of that definition or symbol alone is not leakage. A hint
that directly gives the requested answer is still leakage. Quote the exact visible disclosure when rejecting.
Private model-answer/rubric fields, including nested `context.form_content` and retry marking fields, are review
data; their presence alone does not show what the learner sees before attempting the check.

Rubric keyword groups are advisory signals: `grade.py` still requests semantic judgement. Judge the complete
answer against the stated mark point, accepting mathematically or scientifically equivalent expressions.
A keyword match cannot establish correctness, and a missing literal keyword alone cannot establish an error.

Use only the exact items/decisions paths supplied in this job's prompt. Record the items file's SHA-256 before
review and confirm it is unchanged before writing decisions; if it changed, preserve your review separately and
report the conflict. The supplied inventory is the review input, not a guessed `Work/Candidates` pack. Keep
question IDs exact and never replace another candidate or review file to make an old inventory agree.

Review `context.learner_visible_prior` for earlier sibling examples and unanswered question stems in the full
lesson form sequence. These projections exclude private keys and conditional retries. Review
`context.possible_other_kc_context` as possible exposure only: KC traversal depends on prerequisites and session
selection, so its inventory order does not establish what was taught first. Cite a concrete applicable teaching
path when treating that conditional material as disclosure; do not assume all listed material was shown.
These fields are review-only and must never be supplied to the blind solver. Private marking data remains
separate from learner-visible projections.
