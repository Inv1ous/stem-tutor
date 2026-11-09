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
An explicitly authorized Codex job may set `new --codex-stop-remaining PERCENT`
(from 1 to below 100). This persists only that job's Codex stopping
boundary; actual remaining allowance must be strictly above it. Claude stages,
shared configuration, review gates and the two-failure guard remain unchanged.

Update an existing job's authorized boundary and role settings without restarting
completed stages:

```sh
bin/extract configure JOB --reason 'Explicit pre-reset authorization' --codex-stop-remaining 1 --codex-extract-model gpt-6.1-sol --codex-extract-effort medium --codex-review-model gpt-6.1-sol --codex-review-effort high
# After the controller verifies the reset (or a natural weekly reset):
bin/extract configure JOB --reason 'Verified post-reset phase' --codex-stop-remaining 40
```

`configure` requires an explicit reason and refuses changes while a worker runs.
Its audit retains previous settings, successful stages, candidate/review bytes,
and failure histories. A budget-only launch rejection does not create a failure
or persisted hold: after verifying the authorized phase and fresh allowance,
use normal `run JOB --weekly-remaining PERCENT` to launch the missing stage.
Configuration never clears the two-failure guard; `unstick` still requires a
separate explicit operator decision. These controls neither read account limits
nor redeem reset credits, and cannot guarantee a precise floor while other work
consumes the shared allowance.

`new` accepts repeatable exact `--source asset:ID` / canonical path selectors and
`--pages 3-12`; these choices persist across restarts. Inventory may cover a whole
course, while each paid worker batch is capped at 100 selected pages. Create
fresh source/page jobs to extract larger inventories in bounded batches.
Exact source selectors are applied before PDF bytes are read. A selected job
still verifies its registered resources and frozen hashes on every operation;
an unrelated source's availability does not block it. Full inventory continues
to verify every applicable source, with no persistent verification cache.

A saved maker range can be narrowed to one whole official question for a bounded
repair/review pilot, without another extraction pass:

```sh
bin/extract focus JOB --official-qid 9701_w25_22_q3 --reason 'Whole structured-question pilot'
bin/extract check JOB
# Only if source comparison/rubric/media repair is required:
bin/extract run JOB --retry extract --weekly-remaining PERCENT
# Once the candidate passes free validation, normal run starts independent review:
bin/extract run JOB --weekly-remaining PERCENT
```

`focus` requires the exact saved successful maker output and refuses already
focused or reviewed/registered jobs and running workers. It selects every record
with that official_qid, retaining complete/uncertainty flags, source hashes,
ordered question/mark-scheme regions and media bytes. A fresh candidate revision
and full original-state snapshot preserve the original candidate, broad maker
coverage, review, attempt commands and history. The job name, pass and existing
failure guards are retained; focus never clears a hold or certifies content.
The snapshot path/hash and original sources/jobs are in `focus_history`.
For an OCR-enabled focused source, integrity checking recovers its original
reader selection from that hash-verified state snapshot. The current source
identity/hash/status and full OCR binding must still match. Every originally
frozen OCR page is verified, including pages outside the sparse working scope;
OCR reads return only the focused working pages. Neither the frozen binding nor
the source's pending-OCR status is narrowed or promoted by focus.
The original snapshot determines whether OCR verification is required, even if
the current binding field is missing or falsey; removing that field is rejected.
Sources introduced by a supported native evidence revision must instead match
its frozen inventory and hash-verified predecessor snapshot/selected-item lineage.
Explicit `selected_page_numbers` may be disjoint, and drive the prompt, coverage,
region gate and worker-page cap. Review establishes only selected-item coverage;
it does not credit other questions or every page in the original maker range.
All selected assessed record IDs and the original course graph remain bound.

After the current whole-question scope is independently reviewed, registered and
published, reuse another whole question from the original maker artifact:

```sh
bin/extract next-question JOB --official-qid 9702_s23_22_q9 --reason 'Continue completed maker work one whole question at a time'
bin/extract check JOB
# If native originals are needed, stage this scope's exact evidence next:
bin/extract evidence-sources JOB --source-pages asset:QP_ID=PAGES --source-pages asset:MS_ID=PAGES --reason 'Native evidence for the next selected whole question'
```

`next-question` is a free, one-question transition. It verifies current candidate,
independent review, registered media/provenance, source and frozen graph hashes,
and publication bindings. A free `check` may leave the stage `reviewed`; durable
publication evidence and every exact proof gate are still required. The active
bank may have a newer release from other jobs, but must retain the completed
scope's exact items and IDs. Processed and active whole-question checks use the
runtime canonical identity, including accepted case, `qp_` and question-number
spellings, while original source-record identity validation stays unchanged. Running workers,
current two-failure holds, pending/unpublished candidates, changed evidence,
already processed/active targets and targets absent the original maker block it.

A fresh `Work/Preparation` archive contains the complete prior state, exact review
and publication bank/report bytes with hashes, registration references and native
source history. `completed_scope_history` keeps those pointers; candidate/media
and Library resources remain unchanged. Only active scope stage, registration,
publication and native-provenance bindings reset. The job name, pass, all failure
maps/history, model settings and authorized stop boundary carry forward.
The new scope copies every original target record and its stable IDs/parts/flags,
uses sparse source/question coverage, and keeps the original full maker coverage.
Original frozen OCR inputs are still all checked through the verified original
reader snapshot. A native evidence revision can then be staged once for the new
scope; older native histories remain in its completed-scope archive. The prior
question stays active while the next candidate is pending. The route verification
harness selects both extraction job and candidate hash when checking a scope.

When an original maker record has exactly `mark_scheme_regions: []`, explicitly
stage its missing historical evidence with `focus ... --stage-missing-scheme`
or `next-question ... --stage-missing-scheme`. Defaults remain strict. This
opt-in refuses current two-failure holds, preserves every original flag/ID/byte,
and records the affected IDs in the frozen selected scope. Missing/null/malformed
fields and invalid nonempty old regions are rejected. `evidence-sources` retains
those original empty lists in source occurrences while staging exact native
sources; no historical inspection is transferred to them. Current candidate,
review, registration and publication gates remain strict: a maker must compare
native sources and supply complete official scheme regions/rubrics/media, then
independent review must verify the new bytes. Staging establishes no approval.

If a focused compiled-source question needs newly located native original
QP/MS evidence, stage exact catalogued sources with bounded per-source pages:

```sh
bin/extract evidence-sources JOB --source-pages asset:QP_ID=1,19-20 --source-pages asset:MS_ID=1-3,14 --reason 'Located original native QP/MS for the selected question'
bin/extract check JOB
bin/extract run JOB --retry extract --weekly-remaining PERCENT
```

This command requires an existing focused, unreviewed/unregistered job with no
running worker and no two-failure role hold. It uses exact AssetLibrary IDs and
the existing verified source reader, requires native text availability, and
limits the explicit pages to 100. An existing native evidence revision cannot
be restarted through this command. It does not relax pending-OCR validation,
clear guards, or approve content. It creates a fresh candidate revision and full
state snapshot, retains prior media/content/flags/coverage unchanged, and appends
an exact prior candidate/hash/region occurrence to each selected record. The
old compiled source inventory and attempts remain in `source_rebase_history`.

Before the first native maker/reviewer attempt, a native-staged scope can append
new native PDF assets as explicitly auxiliary reference data:

```sh
bin/extract reference-sources JOB --source-pages asset:REFERENCE_ID=1,15-16 --purpose 'Distinct later-edition constants and atomic table; reference only' --reason 'Bind missing learner reference data before native repair'
```

This one-time append preserves existing source order/selections, candidate/media,
flags, settings, guards and original native rebase history. It archives exact
state, candidate and media plus a hash-bound append manifest separately. It
refuses attempted, reviewed, registered, published, running or guard-two work,
existing source IDs and combined selections over 100 pages. Auxiliary sources
carry `evidence_role: auxiliary_reference` and their declared `reference_purpose`
in both worker contracts. Their distinct edition/source provenance cannot
replace the original question or mark-scheme identity. No inspection coverage,
answers or approval transfer to the appended source; actual source-bound repair
and fresh independent review remain mandatory. Later scopes archive this append
with their completed state and start without its reference inventory.

The active inventory becomes the native sources, so old active regions and
coverage deliberately fail validation until a source-backed maker repair.
Every later candidate must retain `required_source_occurrences` exactly;
registration includes them in each media provenance sidecar. Current review and
registration bindings are invalidated while historical resources remain intact.
The existing whole-question identity, assessed parts, graph hash and role failure
counts remain bound. Native source identity/text availability is not science,
marking, visual-inspection or teaching approval.

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

An explicit maker retry forwards exact pending review findings only when the
manager's saved output hash or matching recorded independent failure authenticates
them. A direct result must be a completed, zero-exit, structurally valid pending
review; `ok=false` is expected for unresolved findings. Its one-use packet
preserves the review, prompt and candidate bytes and
binds the course, scope, source page inventory and graph. This includes ordinary
page-scoped diagrams and questions. Before each review launch, the manager saves
the exact input state at `Workers/extraction/JOB/review-inputs/FINGERPRINT/state.json`
under Work, freezes `review.prompt.txt` beside it, and dispatches those exact
prompt bytes. Launch and completion receipts bind that prompt's digest and graph
alongside candidate/output receipts across role resets. Both feedback paths
verify these contracts and require recomputing the actual input fingerprint from
the original logical input paths, saved state bytes and exact reviewed candidate;
matching finding text alone cannot establish historical candidate provenance.
Missing or changed input proof fails closed. A legacy page-scope review without a
manager-bound dispatched contract can use only one consistent
`mapping_evidence.graph_sha256` from every
retained record in the exact reviewed candidate, matching the current graph.
This witness is mandatory even if the unbound prompt contains a graph hash.
The packet records that normalization and archives the original prompt unchanged;
missing, mixed or stale witnesses require a fresh independent review. Manually
placed legacy reviews without attempt evidence supply no repair feedback. Passing
reviews never supply repair findings, and reviewer prompts remain blind.

`bin/extract crop JOB --source ID --page 1 --box 0,0,1,1 --output media/page1.png`
uses the existing PDF renderer/cropper, writing only fresh candidate PNGs.

For a requested Library import, `register JOB` requires passing validation
and an independent review. It registers immutable media plus provenance sidecars
under course `Questions/Media` (flat) or `Diagrams`. Registration establishes
availability; teaching approval stays false. `publish JOB --topical-batch PATH`
is separate and delegates runtime bank gates to build/topicals.py. Supported
extraction formats are 9701/9702 MCQs and structured responses with AS assessed
KCs. Structured records additionally require a canonical `stem`, official text
`answer`, positive integer `marks`, and runtime `scheme` (one nonempty `point`
per mark, optional `mark` label and deterministic `check`). Fresh revisions need
independent source/rubric review; old uncertainty flags are not auto-cleared.
An unallocated official whole rubric may opt into this versioned alternative:
`"scheme": [{"point": "Exact official text or source-backed raster caption", "whole_rubric": {"version": 1, "max_marks": 2, "media": ["official-ms.png"]}}]`,
with explicit `marks: 2` and `kind: structured`. Use exactly one entry, with no
`mark`/`check` fields; the positive integer maximum must equal `marks`. Media is
an ordered unique private subset of reviewed `mark_scheme_media` (at most 32).
Use an empty list only for a sufficient, genuinely textual official rubric.
Never invent graph feature allocations, an all-or-nothing rule, or partial-credit
thresholds absent from the source. Exact source-backed cumulative thresholds
(for example, at least two of three criteria, then all three) may instead retain
the ordinary point format after independent review of threshold equivalence.
Preparation maps only those private filenames to registered immutable Library
references; publication binds every other scheme field exactly to the review.
Runtime revalidates their source provenance and bytes at disclosure and award.
This mode requires an actual typed attempt or separate explicit paper-attempt
confirmation before showing the official text and exact per-part raster subset.
Human integer marks use a single-use attempt-bound ticket; ordinary `pts=`, AI
judgment and AI re-marking cannot award credit. Work remains saved and ungraded
until a human explicitly confirms an integer from zero to the official maximum.
Explicit ordered `question_media` and `mark_scheme_media` lists partition every
structured record's `media`. Reviewers inspect both sets against original pages;
Only question media enters pre-attempt learner views. Whole-rubric private media
is disclosed only after the guarded attempt described above. All media remains hash-bound and is
registered with its provenance. IAL identity/runtime support remains pending;
source-local numbering is never converted into a CAIE identity.

After registration, `prepare-publication JOB --output Work/Candidates/...` writes
a fresh additive bank and report outside the learner vault. It preserves active
questions and IDs, binds preparation to CURRENT and the prior bank digest, and
translates reviewed KC prerequisites to runtime chapter requirements. Publish
that batch with `publish JOB --topical-batch PATH`. Publication rechecks exact
reviewed content, source regions, ordered question media and active bank
preservation. Existing canonical question/part identities block duplicate
preparation, including unresolved assessed-context conflicts; reuse the active
identity or resolve the conflict explicitly. The runtime still permits only one
bank row per canonical question/part. Preparation, registration and test use do
not establish teaching approval.

Install the Claude manager from the tracked template with
`bin/extract install-skill` (default `~/.claude/skills/extract/SKILL.md`).

Model selection inherits Foundry's active ladders unless a persisted job-local
`--codex-model` / `--codex-effort` is supplied: extraction uses the drafter
model and independent review uses the checker model. The job-local
`configure --codex-extract-model/--codex-extract-effort` and
`--codex-review-model/--codex-review-effort` override only their selected role;
omitted values retain the existing job-wide choice or shared ladder fallback.
They do not rewrite commands recorded for completed attempts. Codex currently uses
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

The Pearson P1 identity pilot admits the exact whole identities
`P1_pearson-edexcel-ial_WMA11_2019-01_01_q1` and
`P1_pearson-edexcel-ial_WMA11_2019-01_01_q2`, each with `part: ""` and
`kind: "structured"`. Exact Q3 adds assessed parts `a` and `b` as described below.
It binds January 2019 WMA11/01 to the existing immutable
QP `asset:legacy-5433803d0abf868d346949c8` (SHA-256
`dfdc644b3818d2242980e515b0b408fd959036cb0ccde78d410e392941360968`)
and MS `asset:legacy-49fc389000ec4447e3b10835` (SHA-256
`03d6d5ba312b272436e189b45b9e0d5e6540e442b5b140c67ac089ef7d2b5fda`).
Regions retain exact role IDs and hashes, ordered pages within QP 1–28 and
MS 1–29, and normalized boxes. These bounds verify source structure, not Q1
coverage. Q2 additionally requires QP regions on both pages 4/5, with no other
QP pages, and MS regions on both pages 9/10. Extra MS context may use only pages
1–7. These page pins prevent same-PDF question transplantation; they do not approve
coverage or content. Use the configured vault's AssetLibrary; filesystem source overrides
are unsupported for this pilot. P1 KCs retain their actual P1 graph levels.

Unknown/generated identities remain pending and unchanged; other IAL units,
sessions, Q5 onward and assessed labels outside the exact Q3 a/b policy remain
unsupported. Identity recognition never approves mathematics, mappings, source coverage or rubric allocation.
Flat structured and optional manual whole-rubric schemas retain their existing
gates; source review determines the appropriate schema. Independent whole-source
and crop review, exact review bindings, immutable registration and explicit
additive publication remain required. Ordinary structured selectors and MCQ
registration-reuse evidence are unchanged.

Fresh native P1 configuration uses the supported constructor or `new` command;
it does not call `focus` or manufacture a successful saved maker. The exact
paired options are `official_qid` and `source_pages` in `create(...)`, or:

```sh
bin/extract new FRESH_JOB --course P1 --scope questions --provider codex \
  --official-qid P1_pearson-edexcel-ial_WMA11_2019-01_01_q1 \
  --source-pages 'asset:legacy-5433803d0abf868d346949c8=1-3' \
  --source-pages 'asset:legacy-49fc389000ec4447e3b10835=1-8'
bin/extract plan FRESH_JOB
```

Q2 uses a separate fresh job with the same options and these exact replacements:

```sh
bin/extract new FRESH_Q2_JOB --course P1 --scope questions --provider codex \
  --official-qid P1_pearson-edexcel-ial_WMA11_2019-01_01_q2 \
  --source-pages 'asset:legacy-5433803d0abf868d346949c8=1,4-5' \
  --source-pages 'asset:legacy-49fc389000ec4447e3b10835=1-7,9-10'
bin/extract plan FRESH_Q2_JOB
```

Do not advance or rebind Q1 to create Q2. Q2 freezes QP pages 1,4–5 and MS pages
1–7,9–10 (12 inspected pages), excluding QP 2/3 and MS 8.

This documents configuration, not an executed job or content approval. Creation
verifies the original native QP/MS resources and actual P1 graph before persisting
an inventoried job. Q1 retains exactly QP pages 1–3 and MS pages 1–8 (11 inspected
pages), whole identity with empty part, record ID `native-` plus the official qid,
and graph hash. Source selectors may arrive in either order; saved order is QP,
then MS. The initial origin is `fresh_native_p1_v1`. Jobs are empty, and no
candidate, review, successful maker, old source occurrence or focus history is
created. Existing jobs or orphan candidate/media targets cannot be adopted.

Both options are required together; `--source`/`--pages`, aliases/paths, extra or
duplicate sources, other role page sets and other identities are rejected. With
neither option, existing create/inventory behavior is unchanged. Verified resume,
manager boundaries and worker preflight recheck the initial source/page/scope/
graph binding. Fresh jobs cannot focus, rebind evidence, add auxiliary sources,
advance to another question or enable OCR. Their real same-scope maker/reviewer
attempts and guarded repairs remain available, with existing review, registration
and immutable additive publication gates still required.

The maker derives new source content; a blind reviewer inspects it independently.
`bounded_read_plan` supplies exact text runs and individual page render commands.
For gapped selections, execute every `text_runs[].command` with its explicit
`pages` list; no min/max text command is supplied. Contiguous Q1 selections retain
the existing single `text` command. Never widen a run across excluded pages.
Q2 source review must retain official alternative methods, dependent method marks
and acceptance rules; its identity does not imply independent flat mark allocation.
Every selected page, including covers and general marking context, needs inspection;
only the complete named question and necessary rubric context are extracted.
Candidate scope, every manager-assigned record ID/part and ordered source-coverage
lists must match the initial request. Fresh crops refuse unselected pages before rendering
or creating output. Generic Library readers are not an OS access sandbox; missing
context remains uncertain and cannot silently expand this pilot's fixed scope.
No mathematical task, answer, rubric mode/allocation or KC mapping is preselected.
Existing usage, concurrency, failure-count and independent review gates remain.


Q3 uses a separate fresh job; do not advance, focus or rebind an earlier job:

```sh
bin/extract new FRESH_Q3_JOB --course P1 --scope questions --provider codex \
  --official-qid P1_pearson-edexcel-ial_WMA11_2019-01_01_q3 \
  --source-pages 'asset:legacy-5433803d0abf868d346949c8=1,6-7' \
  --source-pages 'asset:legacy-49fc389000ec4447e3b10835=1-7,11-12'
bin/extract plan FRESH_Q3_JOB
```

The whole Q3 scope requires exactly two structured assessed records, with exact
lowercase parts `a` and `b`. Canonical assessed identities are the whole qid plus
`:a` and `:b`; candidate IDs are `native-` plus the whole qid plus `-a` and `-b`.
These are local assessed identities, not separate Pearson-issued question IDs.
The version 1 `initial_native_question` keeps `part: ""` as whole-scope metadata;
an empty-part Q3 candidate/runtime aggregate remains invalid. Punctuation, case
and whitespace variants are rejected. Existing Q1/Q2 descriptors, IDs and config
remain unchanged. Q3 is unavailable through legacy focus/next-question selection.

Q3 inspects QP 1,6–7 and MS 1–7,11–12 (12 pages), with separate text runs across
both gaps. Each assessed record requires both QP 6/7 only and both MS 11/12;
optional scheme context is limited to MS 1–7. Exact registered role IDs, hashes,
catalog ownership, ordered finite normalized boxes and original bytes remain
required. Both records, ordered page inspection and reviewed publication bijection
must be complete before registration/publication; no sibling record may be omitted,
swapped, duplicated or replaced by an empty aggregate.

The shared source inspection envelope grants no sibling-answer disclosure right.
Author part-specific learner task crops and private scheme/rubric media; MS12
inspection for part a must not expose part b guidance. Derive full shared task
context, dependencies, alternatives, acceptance rules, prerequisites and KC mapping
from original sources and the real P1 graph. Retain uncertainty for unresolved
scoring; no flat independent allocation or manual whole-rubric choice is implied.
Blind independent source/visual review must inspect both parts and tight disclosure.
Private answers/rubrics remain hidden before attempts, and distinct assessed
identity preserves existing attempt/correction and Topical/Long eligibility rules.
Schema tests establish availability only; they grant no scientific or teaching approval.

### Exact native P2 Q1

The neutral `tutorlib.ial_identity` interface admits only
`P2_pearson-edexcel-ial_WMA12_2019-06_01_q1` for P2. The whole scope has no
assessed aggregate record: its three exact parts are `a(i)`, `a(ii)`, `b`.
Their local candidate suffixes are explicitly `a-i`, `a-ii`, `b`; printed labels
are never punctuation-normalized. Existing P1 descriptors and
`fresh_native_p1_v1` remain unchanged. P2 uses `fresh_native_ial_v1`, with the
same fresh owned-output, no-adoption, source-reverification and lifecycle guards.
P2 manager candidate, registration and publication admission require the fully
reverified initial contract; generic P2 inventory remains available. Standalone
bank loading validates immutable identity/source/graph evidence without relying
on transient manager state.

Initial selectors are `asset:legacy-f10afe0b25e647fb783a2dee=1-2` (QP) and
`asset:legacy-4da88baf2635cd6489af022d=1-7` (MS). Each assessed record binds QP
page 2 and MS page 7, with optional MS context pages 1–6, exact original hashes,
registered course/role metadata and finite normalized ordered source boxes.
Every selected page requires inspection and an original render. QP native text
is only PMT boilerplate; reader availability proves no mathematical extraction.
Use original images and a separate blind source review; do not substitute OCR,
weaken the reader or infer per-part marks. Use the genuine registered P2 graph
(P2 levels and actual parents), never AS/P1 relabeling. Shared inspection grants
no sibling rubric disclosure: public question images and each part's private
rubric images retain their reviewed roles and part bindings.

Reusable collector key code is owned by
`src/tutor_workers/collector_question_key.py`. The dated worker helper is an
import-safe explicit compatibility adapter for `encoded`, `context`, and
`question_key`; collector provenance records both adapter and implementation
hashes. Recognition transfers no review, teaching or publication approval.


Fresh P1 Q4 uses exactly `P1_pearson-edexcel-ial_WMA11_2019-01_01_q4`,
`kind: "structured"`, empty `part`, and one record ID
`native-P1_pearson-edexcel-ial_WMA11_2019-01_01_q4`. Create a separate fresh
job with `--official-qid` set to that identity and these fixed selectors:
`--source-pages asset:legacy-5433803d0abf868d346949c8=1,8-9` and
`--source-pages asset:legacy-49fc389000ec4447e3b10835=1-7,13`.
Inspect every bounded text run and render. Record question regions require both
QP 8/9 and no other QP pages; scheme regions require MS13 with optional MS1–7.
Legacy focus/next-question and adoption of saved Q4 rows are refused, including
mixed candidates and removed scope markers. Manager admission requires the exact
initial configuration and its reconstructed source, graph, scope and output bindings.
Standalone identity, source validation and bank imports remain stateless.

Review QP8's figure and prompt together for legibility and completeness, preserving
source line styles, shading, labels, exponents and fractions; QP9 remains mandatory
continuation provenance. Private scheme crops must retain all MS13 guidance,
including the coupled Alt1 convention and acceptance/precedence notes, rather than
only the top table. The scheme's page-5 quadratic reference corresponds to physical
PDF6, already within the initial 1–7 context. Preserve source wording and accurate
physical provenance. Actual Maker and independent blind original-source review
choose crops, KCs, prerequisites and flat or optional manual whole-rubric handling;
identity, three marks and schema tests grant no content or teaching approval.

## Fresh prepared native groups

`bin/extract new NAME --course S3 --provider codex --scope questions --prepared-scope /absolute/package --codex-stop-remaining 20`
creates an unplanned fresh authoring job from `prepare-native` output. This selector
cannot combine with source/pages or exact-pilot selectors. Existing exact P1/P2
reservations take precedence. `plan`, `run`, `run` (independent review), `check`
use the ordinary manager lifecycle; no seed/COMPLETE marker manufactures a maker.
The default budget is unchanged; this explicit local setting stops at 20% and
requires a current reading strictly above it. Both role failure guards remain two.

The manager serializes native claims with `.prepared-claims.lock`, reconciles
live job scopes, completed maker identities/source occurrences, operator
continuation queues/claims and active bank, and retains immutable whole-question
claims in `prepared-claims.json`. An overlapping owner/hold blocks even under a
new name or batch. Same-name identical requests point to resume. Setup journals
retain interrupted claims; a same-name exact request recovers the verified frozen
input and state without resetting a guard. Incomplete staging trees are preserved.
Broad source inspection of another identified question is never ownership of this
question. Unresolved overlapping broad ranges remain held with their named owner.
Active bank matches are attached as reuse/conflict decisions and block paid planning.

`prepared_scope` contains profile, package_sha256 (exact COMPLETE bytes),
descriptor_sha256, seed_sha256, graph_sha256 and job_name. The manager freezes a
private package at `Workers/extraction/NAME/prepared-input`, independent of editable
authoring input. The group inventory uses the descriptor's normalized
required_asset_pages, including specification, boundary and pending occurrence
witnesses. Every stage recomputes the frozen package from original Library bytes
and current graph. Legacy focus, rebase, OCR and in-place extensions are refused.
Candidate output leaves cannot be aliases/hardlinks. Immutable public/private seed
filenames, original role/regions and pixels are checked across the whole group;
material crop/identity corrections require a new preserved preparation/review.

Maker/reviewer launch normally as distinct manager attempts. State keeps
attempt_id, started, worker_started, finished, exit, input fingerprint, prompt hash
and output hash, plus retained `prepared_attempt_receipts`. Check binds both exact
role outputs and the blind verdict to prepared scope, source inventory, seed,
current graph, candidate and every visually inspected image hash. Manually placed
JSON, a bare exit=0, old provider responses and changed review bytes cannot complete
this route. These receipts are local manager authority, not cryptographic security
against an administrator editing manager state. Repeated check does not charge a
failed attempt twice. Textual/mapping repairs preserve authenticated feedback and
previous candidate bytes; the affected group needs a new independent review.

Optional topical occurrence witnesses remain pending identity joins with their
original IDs, hashes, regions and context. The manager also freezes each exact
verified bundle under `prepared-occurrences/<COMPLETE-sha256>`. Frozen verification
uses these deterministic managed copies while preserving the original request and
package hashes; later upstream bundle edits cannot alter or invalidate the job.
Declared available external prerequisite graphs retain version/SHA pins and are
rechecked at each stage. An external mapping without a frozen version stays pending.

### Explicit whole-question manual assessment

A fresh prepared request may set `assessment_mode: "whole_official_rubric_v1"`
on an individual question. It requires exactly one empty-part record with the
complete ordered QP/core-MS blocks. Preparation derives independently located
QP/MS question-total witnesses and preserves raw printed markers (including
nested Roman labels) without inventing a hierarchy. The maker supplies the full
composite task, concise official answers/sketch criteria, graph mappings and
uncertainty; the automatic seed supplies only IDs/pixels/maximum/manual skeleton.
Only the existing one-entry `whole_rubric` manual integer-award protocol is valid;
marks/max_marks must equal the witnessed total. No eager worked solution or
new grading API is introduced. Whole-QID exclusivity applies in either arrival
order, including across attestations; legitimate existing siblings are unchanged.

Optional `private_guidance_regions` are complete introductory sections from the
same MS, before its first authenticated question row. Retain headings, definitions,
qualifiers, exceptions and continuation context; inspect applicability and hold
ambiguity/unrelated worked answers. Keep them separate from core scheme_regions
and candidate mark_scheme_regions. Ordered private media are guidance first then
all core pages (maximum 32 per item); public/reference media remain unchanged.
Guidance and inspection-only section/question boundaries count toward the existing
100 distinct asset-page cap. Actual maker, separate blind review, immutable
registration/attestation and additive publication remain mandatory. This mode is
for fresh questions intended to be attempted together; mastery/part-practice
information is coarser. An absent discriminator serializes and verifies the
legacy branch unchanged. No teaching approval or readiness follows from a package.

## Question-media leak gate

`check` runs `build/question_leak_gate.py` on every question record's media (on by default).
A data-sheet, periodic-table, constants-table or single-constant strip in question media is a
blocking finding ("delete the file and drop it from the record") so it never registers into
Library; mark-scheme media and tiny, near-blank or unchecked images are only flagged in
`state['media_gate']` for an AI look. Any gate error keeps the image and flags it.
Near-duplicates of leaks confirmed by `build/prune_question_leaks.py plan` (signatures in
`Work/Preparation/question-leaks/leak-signatures.json`) are rejected even when OCR fails.
`prune_question_leaks.py apply` deletes only unreferenced leaks; its rollback restores the catalog
from `catalog.before-prune.json` but cannot restore deleted bytes (the journal keeps a sha256 manifest).

`bin/extract leaks JOB|--vault VAULT [--out PATH] [--apply]` runs the gate in plan mode (counts per class, `ai-review.json`); `--apply` (vault only) calls `prune_question_leaks.apply`.
