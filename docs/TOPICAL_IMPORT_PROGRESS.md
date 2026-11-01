# Topical import: first published batch

27 October 2026. **Published locally:** 1,532 question/part entries in 74 chapter selections. Of these, 501 entries are new relative to the previously published teaching packs. The remaining entries preserve existing question identities and exposure history.

Restart the tutor and choose **Topical past papers**. This route includes reviewed question chapters whose lessons are not published yet. **Can I solve this? / ctrl+y** checks prerequisites, including during no-hints questions. See [the usage and storage guide](TOPICAL_QUESTION_BANK.md).

## Batch and coverage

| Subject | Bank entries | MCQs | Structured parts | New entries | Available source references across the tutor | Identifiable source references, provisional | Rough availability |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| Chemistry 9701 | 900 | 893 | 7 | 189 | 1,294 | 2,673 | 48.4% |
| Physics 9702 | 632 | 616 | 16 | 312 | 1,225 | 3,703 | 33.1% |

**These percentages estimate availability against identifiable paper/question references, not certified completion of every question in every PDF.** Existing teaching questions count alongside the new bank. A parent reference counts when at least one assessed part is available; it does not imply every subpart is marked. The 23 structured entries cover 11 whole parent questions, with complete screenshots reused for independently assessed parts. Across the bank there are 1,520 distinct parent paper/question references; distinct papers may reuse the same scientific question.

The denominator combines PDF text labels and unreviewed OCR labels. Missing labels, OCR errors, old one-digit paper formats and image-only compilations make it incomplete. This is a first-run estimate, not a count of all printable question appearances. Earlier text-layer-only estimates have been superseded by the broader scan inventory. [Machine-readable counts and caveat](benchmarks/2026-10-27-topical-bank/coverage.json).

Only the requested Chemistry 9701 AS Topicals and Physics 9702 AS Topicals collections were used for questions: **82 PDFs, 9,919 pages**. Official syllabus PDFs were used for scope/data checks. Source PDFs remain unchanged.

## Verification and holds

- The initial 1,199 MCQs reuse existing checked AS mappings and require matching independently parsed topical answer-table keys. They are mostly existing questions, not a new-question count.
- Additional source-image review admitted 34 chemistry MCQs and 276 physics MCQs. Three chemistry and 17 physics candidates remain pending. This includes two apparent source/key conflicts; their original keys were preserved and neither question was admitted.
- Twenty-three structured parts were checked against official marking schemes. Only requested parts are assessed. Old Data Booklet references receive the required supplied data. An upright official periodic table accompanies new atomic-structure image questions.
- Syllabus checks use the current published 2025–2027 Cambridge AS objectives. Old compilation chapter labels alone are insufficient. Pure gas-expansion-work items outside current AS were held. Some old-context parts remain usable when the required relation/data is supplied and only an AS skill is tested.
- The two root physics scans were OCR-inventoried across all **686 + 550 pages**, producing 3,133 and 366 distinct provisional reference labels respectively. Three scanned chemistry books were also OCR-inventoried. These OCR results add **no playable questions** until orientation, crop boundaries, symbols, answer separation and content are reviewed. The Crack-A-Level scans produced no recognized canonical labels, not zero questions.
- Automatic header cropping rejects rotated pages and records them for physical review. Sampled root physics pages alternate 90°/270° PDF rotation; arbitrary second rotation or unverified deskewing would be unsafe.

## Delivery and preservation

The independent database is `.tutor/topicals/vfec1b9cd0d634d249c98ff17ed52233e/bank.json` in the learner vault. Its atomic `CURRENT` pointer selects that version. **1,526 source assets** were copied and checked byte-for-byte. The loaded bank reports no errors. Bank SHA-256: `9256fdec833869c68a43c7f1dc62800cead0f39cc2ebe69d87fcd7af4f83103e`.

The published engine was installed separately with a recoverable `engine.before-topicals-0ff055d56cd7` backup. No unfinished lesson packs were republished. Six protected learner/config/event files retained identical hashes across publication; saved Claude/ChatGPT/local selections were not changed. Copied copyrighted questions and source images remain local and excluded from Git. Nothing was committed or pushed to GitHub.

Final frozen-code suite: **4,766 passed, one existing optional MLX skip, 28 existing warnings, 157.24 seconds, exit 0**. Importer focused tests: 9 passed. Actual-bank terminal/Now integration probe: 2 passed. Independent Standards and Spec findings were fixed and scoped rereviews are clear. [Review and evidence](benchmarks/2026-10-27-topical-bank/review.md).

Preparation stopped with **22% weekly remaining** at the last reading, leaving a margin above the requested 20% floor. Further imports should begin with physically reviewed scan crops and the held mapping/key cases, without silently admitting unreviewed OCR.
