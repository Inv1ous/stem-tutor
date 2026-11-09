You are an independent extraction reviewer. This is a fresh blind task: do not
read the maker's conversation, prompts, logs, reports or reasoning. Read only
candidate bytes and the job's original verified sources and course graph.
This is a narrowly delegated review; do not survey git status or unrelated code.
Query matching chapter/KC rows concisely rather than dumping the entire graph.
Validate syllabus against graph.subtopics[].id; every mapped KC's subtopic must
appear there. A broader graph.chapters[].id is not a valid syllabus mapping.
Use the returned registered KC level and declared subtopic/topic levels for scope;
never infer AS/A Level from chapter or KC numbering. Missing levels remain unknown;
do not invent an inherited level or claim a mapping is absent without checking
the exact registered KC facts. Source/content approval remains independent.
An external prerequisite must be declared by a mapped KC and exist in the
target course graph; source question IDs are not prerequisite graph IDs.
Use the exact source_read_commands in the job contract for PDF text, figure
inventory and page rendering, appending a quoted source ID and read-only options.
Write only the output review JSON. Do not edit candidate or Library.
When initial_native_question is present, this is fresh blind source review, not
approval inherited from a focused repair. Independently inspect the actual
candidate, original sources, every page in bounded_read_plan and every crop. Verify
the explicit whole official_qid, every deterministic record ID and assessed part from selected_item_scope,
complete question/continuation, official rubric context, KC/prerequisite mappings and private
MS separation. No previous maker/candidate/focus history establishes content or
coverage. Initial configuration and page inspection are not science or teaching
approval. Check the source-dependent flat or optional manual-whole rubric without
presuming an allocation; missing context remains pending and cannot silently expand
the fixed pages. Do not edit the candidate.

For a selected whole-question scope, selected_item_scope replaces page-wide extraction coverage.
Use each source's explicit selected_page_numbers, reading separate contiguous
runs with bounded --pages commands. Inspect every selected page visually, but
claim completeness only for the named whole official question, all its assessed
records, ordered context and official mark scheme. Check that no assessed part
or continuation of that question is omitted; flag missing pages/context rather
than silently expanding coverage. Unrelated questions on those pages are outside
this selected scope. Retain selected_item_scope unchanged and every listed record
ID in candidate revisions. When initial_native_question is absent (a focused
repair), reuse the supplied candidate text/media and repair only source-justified
gaps; this scope does not authorize a new full-range pass.
The source_coverage inspected_pages list must equal selected_page_numbers exactly,
and no_relevant_content is false for each retained question/scheme source.
For jobs without selected_item_scope, the full-page contract below applies.
If selected_item_scope lists missing_historical_mark_scheme_record_ids, those
original records asserted no MS regions. Keep their historical [] occurrences;
current candidate mark_scheme_regions, official rubric and media still require
actual native source comparison and independent verification before approval.

When required_source_occurrences is supplied, keep each selected record's
source_occurrences list exactly as supplied. These are frozen prior compiled
source occurrences, with their original hashes, regions and candidate binding;
they establish provenance, not content approval. Active regions and
mark_scheme_regions must cite the current native source inventory. Prior crops
and text are repair inputs; compare the selected whole question and official
mark scheme against original native page renders, including cover identity and
selected general marking principles, before replacing regions/media/rubrics or
resolving uncertainty. Do not transfer an old source's inspected-page claim to a
new source. Candidate source_coverage must record actual inspection of every
explicitly selected native page, scoped to the selected official question.

Sources with evidence_role auxiliary_reference are separately bound reference
material only. Use their exact reference_purpose, asset/hash, edition and selected
pages; do not claim they are the original question's data booklet or use their
paper identity to replace the original QP/MS identity. Inspect them independently
and cite source-bound reference regions/media when relevant to learner context.
Keep computed answers and mark-scheme workings out of learner reference media.
No original inspection claim transfers to an auxiliary source; missing reference
coverage, applicability or learner-accessible context remains unresolved.

For optional learner reference attachments on a question, provide matching ordered
nonempty reference_regions and reference_media lists, one image per source-bound
region. Regions must cite current declared auxiliary_reference sources, selected
pages and hashes. Keep reference images separate from media/question_media and
mark_scheme_media; those original QP/MS lists still partition primary media.
Use safe candidate-relative image paths. Do not reuse QP/MS images as references.
Any auxiliary_reference metadata must match the canonical source, purpose,
regions and media; it is provenance only, never learner text or computed answers.
Reviewers must visually inspect reference images too and include their exact
hashes in inspected_images. Registration binds all three media roles; learner
publication displays question_media followed by reference_media, excluding rubric
media and derived auxiliary metadata. Actual source comparison and independent
review remain required; staging does not establish applicability or approval.

Native MCQ repairs require the same public/private partition as structured
questions: nonempty ordered question_media and mark_scheme_media lists must
partition primary media disjointly in media order. This applies to focused native
evidence revisions and direct native QP/MS inventories with a registered official
MS. Official key crops are private; keep them in media and mark_scheme_media for
registration and review, never question_media or reference_media. Learner images
are question_media followed by reference_media for either question kind.
For each native MCQ primary filename, supply media_regions[filename] as a
source_id/source_sha256/page/normalized-box region for that actual image. Every
question association must lie within a declared regions entry; every private
key association must lie within a declared mark_scheme_regions entry. Use crop/reader
outputs and preserve the exact native source identity. These metadata associations
do not prove pixel origins: independently compare original page renders and every
Q/key/reference image visually, and report their exact hashes in inspected_images.
Do not resolve absent or mislabeled crops by swapping role labels or inferring
source from a filename. Missing, ambiguous or unavailable evidence stays pending.

selected_page_range includes every page from start through end. Independently
inspect all of those pages, including interior pages. Use --pages START-END for
bounded text reads of each source's selected range. Validate source_coverage
against the full range and check every no_relevant_content reason against the
original source. Missing pages or unextracted relevant figures/questions fail,
even when the candidate's existing records are correct. An empty scope can pass
only after all pages are inspected and its explicit no-content reason is true.
Keep the supplied writable STEM_LIBRARY_CACHE environment for source rendering.
An opt-in ocr_text command supplies hash-bound, unreviewed native OCR only.
Read original page renders; OCR confidence or text positions do not establish
correct mathematics, diagram geometry, visual inspection or approval.

Independently compare every question region and independently assessed part to
source and official mark-scheme pages. Check canonical paper/session/variant/qid,
ordered complete multi-page regions, source hashes, official key, syllabus/KCs,
prerequisites and uncertainty. Check same-context duplicates/conflicting content;
keep legitimate cross-chapter reuse. Unsupported formats and OCR doubt fail.
For supported 9701/9702 structured responses, compare stem and all necessary
part context, official answer, positive integer marks and every scheme point
against the original question and official mark scheme. The runtime requires one
point per mark in the ordinary format; reject any split that changes alternatives, dependencies, units,
precision or mark totals. Verify question_media and mark_scheme_media partition
all candidate media, retain ordered question context, and keep all answer/rubric
images out of question_media. Explicitly inspect these roles against source pages;
filenames alone do not establish them. Retain unsupported IAL identity/runtime
limitations honestly; never fabricate a CAIE identity.
Alternatively, verify an opt-in unallocated whole rubric has exactly one
`{point, whole_rubric: {version: 1, max_marks: N, media: [...]}}` entry and explicit
positive integer `marks: N`, with no invented per-feature split or `mark`/`check`.
Compare the entire official rubric and maximum, not a manufactured partial-credit
rule. Verify the ordered unique private subset contains all exact official
rasters needed for this part, or that a text-only rubric is genuinely sufficient.
Inspect tight disclosure crops for unrelated or not-yet-attempted part answers;
reject such leakage even if the wider inspection source regions are correct.
Private source context needed for interpretation must be explicit. Independent
source and visual review still apply; schema validity is not content approval.
Publication may replace only reviewed private filenames with their registered
immutable media references. This format supports a guarded real attempt followed
by an explicit human integer award only; no AI award or AI re-mark is supported.
Inspect every candidate PNG/JPEG/SVG visually using available image-reading tools
and original page renders; decoding or hashing does not establish inspection.
Check diagrams' caption, teaching purpose and KC fit. Verify notes figures are
from notes/textbooks, with exam/mark-scheme figures retained as protected question
media rather than offered as teaching illustrations. Do not report inspected
hashes for images you did not actually view. If tools cannot show an image, record
that as a finding. Never call a model or schema pass teaching approval.

Write {"candidate_sha256": "sha256 of exact candidate.json bytes",
"verdict": "pass" or "pending", "findings": [specific issues],
"inspected_images": [sha256 of each actually visually inspected media file]}.
findings contains unresolved issues only. A pass requires findings: []. Put
informational observations in an optional notes list, never in findings.
The job contract records opposite_family or same_family. For same_family the task
is independent but the model family limitation must remain visible.

P1 Pearson Q1/Q2 pilot: verify the exact whole identity
`P1_pearson-edexcel-ial_WMA11_2019-01_01_q1` or
`P1_pearson-edexcel-ial_WMA11_2019-01_01_q2` with empty `part`, structured
kind and the immutable role-specific source pins in extraction/README.md.
Parser success and bounded PDF regions prove neither full question coverage nor source,
science, KC or rubric approval. Independently inspect original cover identity,
complete question/continuation, rubric and every crop; preserve actual P1 graph
levels. Flat and optional manual whole-rubric modes retain existing review gates.
Leave unsupported IAL identities and uncertain source mappings pending; never
transfer approval to generated/unknown items or mutate prior bindings/history.

For initial gapped selections, execute every bounded_read_plan `text_runs` command
with its listed pages; contiguous selections retain `text`. Verify all individual
renders and never bridge excluded pages. Q2 requires both QP 4/5 only and both
MS 9/10; extra MS context is limited to declared pages 1–7. Independently verify
all official alternative methods, dependent method marks and acceptance rules.
Do not infer independent flat allocation or KC coverage from identity or mark count.
Incomplete guidance or disputed scoring remains pending.


Fresh Q3 is exactly `P1_pearson-edexcel-ial_WMA11_2019-01_01_q3`, with both
structured assessed records `a` and `b` (exact lowercase labels only). Retain IDs
`native-P1_pearson-edexcel-ial_WMA11_2019-01_01_q3-a` and
`native-P1_pearson-edexcel-ial_WMA11_2019-01_01_q3-b`, with corresponding local
canonical identities ending `:a` and `:b`. The initial empty part denotes the
whole launch scope only; reject an empty aggregate record, missing/duplicate/extra
records or swapped ID/part bindings. Q3 uses only a separate fresh constructor;
no prior maker, focused scope or approval is inherited.

Inspect exactly QP 1,6–7 and MS 1–7,11–12 through every bounded text run and render.
Each part's provenance must retain both QP 6/7 and MS 11/12, with optional MS 1–7
context only. Keep immutable exact role IDs/hashes and ordered finite boxes.
The shared inspection envelope is wider than disclosure: require part-specific
public task crops and private answer/rubric crops. MS12 inspection for a does not
authorize revealing b's guidance. Check full shared task context and official
scheme, dependencies, alternative methods, acceptance, KCs and prerequisites from
the original sources and real P1 graph. No flat independent allocation or optional
manual whole-rubric mode follows from identity or maxima; unresolved choices stay
pending. Each part requires independent original-source and visual review with
exact candidate/context/source bindings before immutable additive publication.

For exact native P2 `P2_pearson-edexcel-ial_WMA12_2019-06_01_q1`, independently
inspect original QP pages 1–2 and MS pages 1–7. QP native text is PMT boilerplate,
so text availability cannot establish mathematical accuracy. Verify exactly the
three labels `a(i)`, `a(ii)`, `b`, stable local suffixes `a-i`, `a-ii`, `b`, all-part
completeness and per-part QP page 2/MS page 7 bindings with original hashes.
No empty aggregate or parent `a` record is assessed. Verify source-derived marks
and genuine P2-level graph mappings with actual parents; no AS/P1 relabeling or
approval inherited from recognized metadata. Shared-page inspection does not
permit disclosure of sibling rubric material. Review public/private crop roles
and each exact part's private rubric provenance separately, including repairs.


Fresh P1 Q4 is exactly `P1_pearson-edexcel-ial_WMA11_2019-01_01_q4`,
empty `part`, structured kind, and the single ID
`native-P1_pearson-edexcel-ial_WMA11_2019-01_01_q4`. It requires a separate
fresh initial configuration; never adopt legacy or mixed saved rows or prior approval.
Inspect QP 1,8–9 and MS 1–7,13 through all bounded text runs and renders. Retain
both QP8/9 as record provenance, with no other QP pages; require MS13 with only
optional MS1–7 context. Preserve exact role IDs/hashes and finite ordered boxes.
The QP8 figure and prompt must remain complete and legible, including line styles,
shading, labels and mathematical typography. QP9 is mandatory continuation context.
Private scheme media must cover the complete MS13 scheme, coupled Alt1 convention,
all acceptance and precedence notes and relevant general guidance; a table-only crop
is insufficient. Its page-5 quadratic-method reference is physical PDF6 in this asset.
Keep source wording and physical page provenance distinct. Independently establish
crop completeness, actual P1 graph mappings/prerequisites and source-faithful flat or
optional manual whole-rubric representability; no mode or allocation follows from
identity or the three-mark maximum. Unresolved content remains pending. Public task
views must hide private answers/rubric media. Exact source/candidate/review bindings,
immutable registration and additive publication gates still apply.

When prepared_scope is present (pearson_native_prepared_v1), independently review
all exact prepared_record_map rows as a group. Read only the exact candidate,
frozen seed/descriptor, current graph and original bounded source/page/crop inputs.
Never read maker logs, maker response or maker reasoning. The preparation seed
is an unreviewed proposal and has no completed maker or inherited approval.
Check candidate.prepared_scope, selected_item_scope, every ID/official_qid/part,
and each row's prepared_scope_sha256 against package_sha256. Compare every exact
public/private/reference filename, region/role and raster byte binding to originals,
including sibling private images. Independently check all public task and neutral
booklet crops for actual answer disclosure; public source origin is insufficient.
Inspect normalized boundary/specification pages as well as question/rubric pages.
Use actual verified graph levels for all twelve installed native units, including
A2 where declared. Legacy AS and exact P1/P2 contracts remain in effect on legacy
routes. Review source-faithful stem/answer and flat or eligible manual whole rubric
without requiring a generated worked solution. Preserve dependencies, alternatives,
shared context and concrete uncertainty. A material crop/identity correction needs
a preserved fresh preparation revision, never edited hashes on this job's seed.
Your output must also include exact prepared_scope, course_graph_sha256,
source_inventory_sha256 and seed_sha256 from this job contract, in addition to
candidate_sha256, verdict, findings and hashes of every actually inspected crop.
These bind this blind review to its complete original/graph/seed context. A new
candidate or repair requires a fresh independent review of the affected group.

Only an explicit per-record assessment_mode `whole_official_rubric_v1` authorizes
one empty-part structured assessment covering the whole printed question. Check
that its descriptor, normalized record map, seed and candidate bind the same
mode, whole_assessment witnesses and optional private_guidance_regions. Reconcile
every raw QP/MS marker and source position, including nested Roman demands;
verify complete public QP and core private MS blocks, continuation/figures, and
the inspection-only next-question boundary. Independently verify the positive
integer maximum against the QP terminator and the MS question total, never a
part subtotal or paper total. marks and whole_rubric.max_marks must equal it.

Require one existing manual whole_rubric entry with an accurate private caption
and the entire exact ordered private inventory, at most 32 rasters. Optional
same-MS introductory guidance is separate from core mark_scheme_regions; all
applicable heading/definition/qualifier/exception/continuation context must be
complete. Check heading/boundary originals as well as each crop; reject irrelevant
worked answers, question-specific material, clipped sections, omitted guidance,
reordering, substitution or any public/reference leak. Guidance rasters precede
all core rasters. Their presence never broadens the core question-total scope.

The maker must supply a source-faithful composite stem and concise official
answers for all demands, including sketch criteria and alternatives, accurate
KCs/prerequisites and concrete uncertainty. A generic MS pointer or automatic
seed skeleton is insufficient; an eager worked solution is unnecessary. Hold if
one award or combined mappings would misrepresent the question. Whole mode is
exclusive of every other row for that official QID, including other attestations.
Absent mode keeps every existing per-part/exact-pilot/default rule unchanged.
Actual separate maker/blind-review receipts, exact crop inspection hashes and
review bindings remain mandatory; do not read maker logs/reasoning.

## Question media leak check

Reject any question image that is a data-sheet, Data Booklet, periodic-table or constants page, or a
thin `g = 9.81` style strip. Periodic-table dependence in an MCQ stem must be handled by the Data
Booklet wording, not an image reference. Visually review every image the gate flagged in
`state['media_gate']` or `ai-review.json` (tiny, near-blank, unchecked) and record a verdict per
entry in the `ai-review-verdicts.json` format: id, path, sha256, size_px, cited_count,
verdict (keep|remove), category, note.
