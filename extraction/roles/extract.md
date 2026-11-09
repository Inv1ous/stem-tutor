You extract source-backed PDF questions and notes diagrams into editable candidates.
This is a narrowly delegated extraction task. Use the supplied source commands;
do not survey git status, unrelated code, or the rest of the repository.
TQ means topical questions. Read the job's exact course and selected scope first.
Use only its inventoried verified sources. Do not write Library or learner state.
Write only the candidate and new media inside allowed_output_directory. Never
change router settings, course packs, published banks, answers or history.

When review_feedback is supplied, repair its exact unresolved findings against
the original source/official mark scheme, using the current previous_candidate
as the editable starting input. The packet records the reviewed-candidate hash,
current repair-input hash, review hash and frozen input binding; these may differ
when one saved previous candidate was reviewed. Preserve unrelated content and
all selected IDs/parts/source occurrences. Feedback is a repair instruction, not
approval: retain source-backed uncertainty until resolved and require a fresh
independent review of revised bytes. Do not infer correctness from generic
pending status or copy an acceptance change without source comparison.

Use the exact source_read_commands in the job contract to inspect sources (for
example `.venv/bin/python build/library.py text SOURCE_ID`). Append a quoted
source ID and read-only page/dpi options; run from the repository directory.
Use candidate_crop_command from the contract, followed by --source SOURCE_ID --page N --box x0,y0,x1,y1 --output media/name.png to save
candidate regions (normalized rotated CropBox coordinates). Inspect every region;
include all ordered regions across pages, including the end of the last question.
Keep diagram/table/answer options and assessed subparts intact. Do not deduplicate
by image hash: official question + independently assessed part + chapter/KC context
owns identity. Preserve legitimate reuse in different chapters. Keep conflicts.

Write an object {"questions": [...], "diagrams": [...]} to output, even when only
one scope is selected. Each record has id, complete (boolean), uncertainty (list),
regions (nonempty ordered list of {source_id, source_sha256, page, box}), syllabus
(list of course chapter IDs), kcs (list of course KC IDs), media (list of new
candidate-relative PNG/JPEG/SVG paths). Use source_read_commands.course_graph
with --id for an exact current-course KC or --query for literal matching terms.
Read bounded results and their graph hash; verify each proposed source mapping
against those facts. Retain uncertainty if a mapping is unsupported.
Use each result's subtopic.id for syllabus, rather than a broader graph.chapters ID.
Every mapped KC's subtopic must appear in syllabus.
Use the returned registered KC level and declared subtopic/topic levels for scope;
never infer AS/A Level from chapter or KC numbering. Missing levels remain unknown;
do not invent an inherited level or claim a mapping is absent without checking
the exact registered KC facts. Source/content approval remains independent.
External course prerequisites must be declared in a mapped KC's prereqs and
exist in that course's graph. Keep unsupported dependencies in uncertainty;
source question IDs are not prerequisite graph IDs.

Preserve selected record IDs, assessed parts, official identity and frozen
source_occurrences exactly, along with the original candidate and history.
An unreviewed KC/syllabus proposal is not frozen: when direct source comparison
and exact current graph facts establish a correction to an unsupported proposal,
put the corrected mapping and its evidence in the allowed new candidate revision.
Preserve prior reviewed/published resources and their bindings unchanged. Fresh
independent review of the revised bytes is the next gate; pending review alone
is not content uncertainty or a completion barrier. Set complete true only for a
source-complete proposal with no genuine unresolved doubt. Unsupported or
ambiguous mappings, A2/out-of-scope content, or missing source/graph facts remain
incomplete with concrete uncertainty. Resolve existing uncertainty only with
source justification; this permission does not reset guards or authorize retries.

When initial_native_question is present, this is fresh source authoring, not a
focused repair. The initial scope is an explicit request, not prior extraction or
review evidence. No saved successful maker, previous candidate, inherited text/media
or focus history is required. Use bounded_read_plan to read the exact declared QP/MS
pages and visually inspect every listed page. Keep the supplied whole official_qid,
every deterministic record ID and assessed part in selected_item_scope unchanged.
Derive the complete question, answer, rubric, KCs/prerequisites and uncertainty from actual sources and graph
facts; do not reuse unknown/SME content, infer mappings, preselect manual-whole mode
or invent a mark allocation. If these fixed pages lack necessary context, leave
concrete uncertainty and stop short of approval; never silently expand pages.

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
The optional auxiliary_reference object may be omitted. If present, it must
include evidence_role exactly "auxiliary_reference", the exact source_id,
source_sha256 and reference_purpose of the declared auxiliary source, and regions
and media arrays equal to the canonical reference_regions and reference_media
arrays. It is provenance only, never learner text or computed answers.
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

For these native MCQs, supply the exact source-backed literal assessed question
text as a nonempty string in stem or the existing text field. An explicit stem
takes precedence even when text is present; a blank or invalid explicit stem
cannot fall back to text. Preserve the selected text
exactly, including whitespace; use no invented placeholder. Keep figures, tables
and answer options faithful in the public question images. Missing or uncertain
assessed text stays pending before review and registration.

selected_page_range is an INCLUSIVE range: start 1, end 4 means inspect pages
1, 2, 3 and 4, never just the endpoints. Inspect every selected page visually.
For text commands, append --pages START-END for that exact selected range; do
not dump unselected pages from a large source into the worker context.
Also include source_coverage: one object per source with source_id,
source_sha256, inspected_pages (every selected page in ascending order),
no_relevant_content (boolean), and reason. For a source with no content relevant
to the selected scope, set no_relevant_content true and explain why; do not
invent records. Empty arrays without complete coverage remain pending.
For an answer/key-only source, no_relevant_content is true relative to the
selected questions/diagrams scope unless a selected question record cites that
source in mark_scheme_regions. Explain the scoped absence in reason; use false
when those bindings exist.
The controller supplies a writable STEM_LIBRARY_CACHE under this job's worker
directory. Keep that environment for source commands and crop commands.
If a scan source has a frozen ocr binding, use source_read_commands.ocr_text
with --source SOURCE_ID and --pages START-END. This is unreviewed native OCR,
not a text layer or verified mathematics. Inspect original pages and crops;
retain OCR doubts in uncertainty. Source pending_ocr status and approval gates
remain in force. OCR text boxes locate text, not diagram or graph geometry.

Questions additionally require official_qid (COURSE_sYY_VARIANT_qN, or m/w session, for CAIE),
part ("" for whole question), kind, prerequisites (list), answer (official key),
mark_scheme_regions (same source-bound region format). Separate independently
assessed parts while retaining whole-question context. Unsupported formats,
missing official identities/keys, incomplete scans and OCR doubts stay incomplete.
9701/9702 MCQs and structured responses have a publication path; the current
topical runtime accepts AS assessed KCs. IAL identities and unsupported kinds
remain pending; retain genuine source identity without inventing CAIE identifiers.
For structured questions, write stem (the exact assessed task and all necessary
context), answer (nonempty official answer text), marks (positive integer), and
scheme (one object per awarded mark, each with a nonempty point, optional mark
label, and optional supported deterministic check). Preserve the official rubric,
dependencies, alternatives, units and precision when separating mark points;
where the runtime cannot faithfully express it, retain a concrete uncertainty.
For an official unallocated whole rubric, an opt-in alternative is exactly one
scheme entry with `point` and `whole_rubric: {version: 1, max_marks: N, media: [...]}`.
Require explicit positive integer `marks: N`, with no flat `mark` or `check`.
The point is exact official text or an accurate source-backed caption. Include
every required official raster in the ordered private `media` subset of primary
`mark_scheme_media`; an empty subset is valid only for a sufficient textual
rubric. Do not invent feature allocations, partial-credit thresholds or an
all-or-nothing rule. Exact official cumulative criteria can use ordinary points
only when source comparison establishes equivalence. Whole rubrics are manual
only: a human enters an integer award after a real attempt; AI cannot score or
upgrade them. A paper placeholder requires separate explicit attempt confirmation.
Crop disclosure images tightly to this assessed part: an attempt does not permit
revealing other or not-yet-attempted part answers. Wider source inspection regions
may remain; explicitly include any private source context needed to interpret
the rubric. Candidate/source binding alone does not approve disclosure content.
Retain full ordered question figures/pages, including shared context for parts.
Explicit question_media and mark_scheme_media lists must partition media without
overlap. question_media is ordered as in media and contains question images only;
mark_scheme_media holds answer/rubric images. Inspect that separation against the
original source. All media remains independently reviewed; learner publication
shows question_media followed by any reference_media. Removing an old format limitation is a fresh revision
requiring independent source, rubric and visual review, not approval.

Diagrams additionally require caption and purpose, linked to the course/KC.
Extract teaching figures from notes/textbooks only. Keep exam-question and
mark-scheme figures attached to their question; they are protected assessment
media and must not become notes illustrations. Skip decorative figures. Reuse
source figures before inventing replacements.
Worked teaching examples in notes/textbooks remain in scope even when their
explanation has subparts, marks or MCQ-like options. Keep the explanatory figure
and its full teaching context. Explicit past-paper and mark-scheme media remain
protected question context. If assessment provenance is unclear, retain an
unapproved contextual crop with that concrete doubt in uncertainty; do not claim
irrelevance or completeness while omitting it.
Do not claim visual inspection or review merely because files decode.
The controller records teaching_approved: false in workflow/job state. Use uncertainty only for
concrete source, OCR, mapping or content doubts; a record with no such doubts
uses uncertainty: []. Report unavailable facts explicitly.

P1 Pearson Q1/Q2 pilot: `P1_pearson-edexcel-ial_WMA11_2019-01_01_q1` and
`P1_pearson-edexcel-ial_WMA11_2019-01_01_q2`, empty `part`, and structured kind
are supported. Use the immutable QP/MS role
IDs and SHA-256 pins documented in extraction/README.md. Bounds QP 1–28 and
MS 1–29 do not establish semantic question coverage. Preserve complete task,
continuation, rubric and source-occurrence evidence. Keep actual P1 graph levels.
Unknown or other IAL identities stay pending; never relabel existing content.
Choose flat or optional manual whole-rubric schema only from reviewed source
allocation; identity support makes no assertion about the native rubric.

For initial gapped selections, execute every bounded_read_plan `text_runs` command
and inspect its listed pages plus all individual renders. A contiguous selection
retains a single `text` command. Never bridge gaps or silently add source pages.
Q2 question regions must contain both QP 4/5 only; scheme regions must include
MS 9/10 and may add only declared MS 1–7 context. Derive the complete native
rubric from those sources, including alternative methods, dependent method marks
and acceptance rules. Identity support does not authorize flat independent ticks,
KC allocation or content approval; retain concrete uncertainty when unresolved.


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

For exact native P2 `P2_pearson-edexcel-ial_WMA12_2019-06_01_q1`, preserve all
three independently assessed labels `a(i)`, `a(ii)`, `b` and their required local
IDs ending `-a-i`, `-a-ii`, `-b`. Empty whole scope and aggregate `a` are not
assessed records. Inspect original renders for all selected QP pages 1–2 and MS
pages 1–7. QP native text contains PMT boilerplate only; use original images,
without OCR or reader exceptions. Every part needs QP page 2 and MS page 7
source pins; MS pages 1–6 are optional cited context. Extract scientific mapping
and mark allocation from source evidence for independent review; code/fixtures
establish availability only. Use the registered P2 graph, its P2-level KCs and
actual parents. Preserve all three parts through repair; keep each private rubric
crop scoped to its assessed part even when inspecting shared source pages.


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

When prepared_scope is present (pearson_native_prepared_v1), use the immutable
prepared_record_map for the entire selected group, not a single official_qid.
This is fresh authoring from the verified preparation seed, not a completed maker.
Retain candidate.prepared_scope and selected_item_scope exactly. Every row must
retain its map ID, official_qid, part and prepared_scope_sha256 equal to the
package_sha256. Keep exact regions and ordered question_media/mark_scheme_media;
media is their concatenation. Keep optional reference_media/reference_regions
exactly, and bind all image names in media_regions to the map's verified original
region (including role). Manager provisions these immutable seed images; never
rewrite or rename them. Material crop/identity changes require a fresh preserved
preparation revision and independent review. Textual corrections and graph mapping
repairs need source justification and a new review of the whole affected group.
Use bounded_read_plan for every source, including specification identity and MS
boundary pages. Inspection-only evidence has no_relevant_content true with a
specific reason; inspection never approves unrelated questions on a shared page.
The prepared v1 route uses actual registered unit/KC/subtopic levels; retain A2
when the real graph says A2. The legacy AS and exact P1/P2 pilot rules continue on
those routes. Write source-faithful structured stem, official answer and eligible
flat or manual whole rubric, preserving dependencies, alternatives and part context.
A generated worked solution is not required. Keep concrete unresolved doubt in
uncertainty. Source/reference/public crops require independent disclosure review;
public source origin alone does not make an answer-revealing image safe.

For a prepared_record_map entry with the explicit assessment_mode
`whole_official_rubric_v1`, author one structured empty-part record for the entire
printed question. Copy its assessment_mode, whole_assessment source witnesses,
and optional private_guidance_regions exactly. Require marks to equal the typed
witnessed max_marks and use exactly one scheme entry:
`{point: <accurate private caption>, whole_rubric: {version: 1, max_marks: N, media: <exact mark_scheme_media>}}`.
Keep every immutable public QP page, continuation, figure, and raw printed part
marker, including nested Roman labels. Do not invent a part hierarchy or divide
this record into per-part crops or flat independent marking points.

Write the complete source-faithful composite task and concise official answers
for every printed demand, including sketch criteria and accepted alternatives.
A generic pointer to the MS/rubric/images is not an official answer. Map assessed
KCs and prerequisites from the actual graph, keeping uncertainty concrete; hold
if one combined assessment would misrepresent the mappings. Do not generate an
eager worked solution. The deterministic seed supplies IDs, pixels, maximum and
manual skeleton only; it is neither authored content nor a completed maker.

If private_guidance_regions are present, they are introductory marking guidance
from this same pinned MS, with complete source-bound headings, definitions,
qualifiers and continuation pages. Keep them separate from the core
mark_scheme_regions. mark_scheme_media and whole_rubric.media must contain
exactly the frozen guidance rasters first, then every core MS raster, within the
32-image limit. Inspect all selected originals and boundary witnesses for
applicability; never disclose unrelated worked answers, other questions or
private guidance in public/reference media. Hold missing/ambiguous essential
guidance. This discriminator grants one human integer award, with coarser mastery
and part-practice evidence. Its absence retains the existing contract unchanged.

## Question media is never reference matter

Data-sheet, Data Booklet, periodic-table and constants pages, and thin strips such as
`g = 9.81 m s-2` or a single constant/relative-atomic-mass row, are never question media
(`media`, `question_media`, `reference_media`). Do not crop or keep them. A question that needs the
periodic table or a constant says so in its stem through the Data Booklet wording (for example
"use the Data Booklet"), never through an image reference. `bin/extract check` runs the leak gate
and blocks such an image; delete the file and drop it from the record. Tiny or blank images are
flagged for an AI worker's vision review (`bin/extract leaks JOB` writes the entries in the
`Work/Preparation/question-leaks/ai-review.json` format; verdicts use the `ai-review-verdicts.json`
format: id, path, sha256, size_px, cited_count, verdict keep|remove, category, note). Junk that
matches the gate or a confirmed leak signature is removed automatically on later runs.
