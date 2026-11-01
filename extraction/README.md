# PDF extraction

`bin/extract` manages per-job provider and scope choices without changing shared
router preferences. TQ means topical questions. Default: Claude; both scopes.

```sh
bin/extract new physics-notes --course 9702 --provider both --scope diagrams
# A job-local Codex choice leaves shared Foundry ladders unchanged:
bin/extract new chemistry-notes --course 9701 --provider codex --scope diagrams --codex-model gpt-6.1-sol --codex-effort low
bin/extract inventory physics-notes
bin/extract plan physics-notes
bin/extract run physics-notes --weekly-remaining 85
bin/extract resume physics-notes
# Once the first worker finishes, run again with the review provider's fresh reading.
bin/extract run physics-notes --weekly-remaining 80
bin/extract check physics-notes
bin/extract board
```

Inventory selects catalogued exact-course Sources shelves and shared PDFs with
explicit `courses` / `shared_for` metadata (or `all_courses: true`). The two
existing shared IAL specification/formula PDFs have exact-path applicability to
the source syllabus units; declared catalog metadata overrides this fallback. Every source
is hash verified before reading and before each worker/check. Byte-identical PDFs
share inventory work but retain aliases and source records. No Library cache is
written: reader caches and extraction state/logs live in Work/Workers; candidates
live in Work/Candidates. STEM_EXTRACT_ROOT and STEM_LIBRARY_ROOT support isolated
fixtures. `--weekly-remaining` must be a current actual reading for the stage's
selected provider. Default shared caps and reserves stop launches at their configured
boundary (at least 25%); unknown readings stop launches. No provider fallback.
An explicitly authorized Codex job may set `new --codex-stop-remaining 20` (or a
higher percentage below 100). This persists only that job's Codex stopping
boundary; actual remaining allowance must be strictly above it. Claude stages,
shared configuration, review gates and the two-failure guard remain unchanged.

`new` accepts repeatable exact `--source asset:ID` / canonical path selectors and
`--pages 3-12`; these choices persist across restarts. Inventory may cover a whole
course, while each paid worker batch is capped at 100 selected pages. Create
fresh source/page jobs to extract larger inventories in bounded batches.
Exact source selectors are applied before PDF bytes are read. A selected job
still verifies its registered resources and frozen hashes on every operation;
an unrelated source's availability does not block it. Full inventory continues
to verify every applicable source, with no persistent verification cache.

`run --retry extract` repairs a pending candidate in a fresh task while retaining
the previous candidate bytes; `run --retry review` starts a separate new review.

`run` launches the selected CLI as a real detached process. Its worker is bounded
to 1800 seconds and completion is persisted. Resume never reruns a successful
stage. Failed/interrupted workers can be retried; prior output is retained.
Maker and reviewer are separate tasks. Both-provider mode uses Claude then Codex;
single-provider mode records `same_family` and its limitation. Paid jobs are not
needed for inventory, plan, check, board or registration validation.

Workers receive an explicit inclusive page range and a writable reader cache
inside their job directory. Candidates include source_coverage for every source:
source_id, source_sha256, ordered inspected_pages, no_relevant_content and reason.
Validation rejects missing interior pages. A source containing no relevant
content for the selected scope can pass only with complete coverage, an explicit
reason and independent source review; empty arrays alone remain pending.

Scans can opt into a prepared native OCR cache before planning:
`bin/extract enable-ocr JOB --source asset:ID`, then
`bin/extract ocr-text JOB --source asset:ID --pages 3-12`.
The cache is under `Work/Workers/extraction/ocr-cache/<PDF-sha256>/` with a
versioned `manifest.json`, per-page JSON and PNG renders. Isolated renderer
provenance, original source identity/hash, page, helper hashes and every selected
sidecar/render hash are validated and frozen into the job. Changed derived bytes
fail rather than silently supplying replacement OCR. Per-page fallback renderer
metadata and diagnostics remain hash-bound. This reader never rewrites PDFs or
changes the general Library reader: sources remain `pending_ocr`, text is labeled
unreviewed, original visual inspection and all candidate uncertainty/approval
gates remain required. Only explicit opted-in jobs receive the OCR command.

Candidate and review contracts are in roles/. Questions preserve complete ordered
regions, independently assessed part, official identity and mark scheme, syllabus,
KCs, prerequisites and doubts. Unknown/OCR/incomplete and unsupported question
formats remain pending. Diagrams retain source hashes/pages/boxes, captions,
purpose and course/KC mapping. Reviews bind exact candidate bytes and hashes of
visually inspected images. An image decoder/schema/model pass is not approval.

`bin/extract crop JOB --source ID --page 1 --box 0,0,1,1 --output media/page1.png`
uses the existing PDF renderer/cropper, writing only fresh candidate PNGs.

For a requested Library import, `register JOB` requires passing validation
and an independent review. It registers immutable media plus provenance sidecars
under course `Questions/Media` (flat) or `Diagrams`. Registration establishes
availability; teaching approval stays false. `publish JOB --topical-batch PATH`
is separate and delegates official-key/review gates to build/topicals.py, whose
current supported format is 9701/9702 MCQ topicals. It does not manufacture a
reviewed topical bank from unsupported extracted questions.

Install the Claude manager from the tracked template with
`bin/extract install-skill` (default `~/.claude/skills/extract/SKILL.md`).

Model selection inherits Foundry's active ladders unless a persisted job-local
`--codex-model` / `--codex-effort` is supplied: extraction uses the drafter
model and independent review uses the checker model. Codex currently uses
`gpt-6.1-terra` for both, with `gpt-6.1-sol` reserved for maximum-tier work and
`gpt-6-luna` for narrow low-tier work. Claude checks use `claude-haiku-5-5`;
Claude extraction retains its configured Opus tier. Per-job provider selection is unchanged.


## Reliability and spending safeguards

Run `bin/foundry doctor` before paid work; it exercises native SVG rendering and imports the PDF/image libraries, rather than only checking package names. Refine and Foundry direct launches also perform this check. Extraction verifies registered PDF hashes before each worker. Bugwatch must use its verified disposable vault and run the same doctor before an AI repair attempt.

The shared paid-worker guard stops a role after two failed results in one pass/job, including timeouts, malformed output and failed gates. Changing model output does not reset this allowance. Inspect saved evidence and fix the root cause before explicitly clearing the guard. `bin/refine unstick CHAPTER "reason"`, `bin/foundry unstick CHAPTER`, or `bin/extract unstick JOB "reason"` archives the decision; never run these automatically. Provider preferences, review gates and course deadlines still apply. Repeated Refine failures preserve candidate work and leave the chapter pending.

Extraction charges a pending reviewer verdict or failed validation gate once
per actual stage attempt. Repeated `check` polling does not consume another
failure allowance, and stale reviews after candidate edits are not new attempts.

Existing question text containing PDF debris is a source-repair task, not a lesson-authoring task. Refine blocks lessons-scope workers before spending on such items. Never infer ×, −, Ω or another symbol solely from a control character: inspect the original PDF/image and bind independent source review to a new revision. Missing guided forms must be authored against the complete reviewed inventory, not filled with placeholders. Every planned lesson visual must be registered, inspected and bound to its teaching card with an accessible description. Written approval remains independent of authoring.

The default weekly launch cap is 70% used and Codex reserve is at least 25%. Unknown allowance readings block launches. An explicit job-local Codex stopping boundary is available only when the user authorizes a different reserve; do not change shared limits or automatically restart an expired course run. For Bugwatch, compare the current failure with the previous attempt: if inputs and blocker are unchanged, stop instead of asking another model to repeat the same repair. Source gaps and disputed content remain visible; tests do not establish teaching approval.
