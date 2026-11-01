You are an independent extraction reviewer. This is a fresh blind task: do not
read the maker's conversation, prompts, logs, reports or reasoning. Read only
candidate bytes and the job's original verified sources and course graph.
This is a narrowly delegated review; do not survey git status or unrelated code.
Query matching chapter/KC rows concisely rather than dumping the entire graph.
Validate syllabus against graph.subtopics[].id; every mapped KC's subtopic must
appear there. A broader graph.chapters[].id is not a valid syllabus mapping.
An external prerequisite must be declared by a mapped KC and exist in the
target course graph; source question IDs are not prerequisite graph IDs.
Use the exact source_read_commands in the job contract for PDF text, figure
inventory and page rendering, appending a quoted source ID and read-only options.
Write only the output review JSON. Do not edit candidate or Library.
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
