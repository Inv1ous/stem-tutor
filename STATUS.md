# Build status (2026-09-27, paused at usage limit)

## Done
- Engine `plugin/stem-tutor/skills/tutor/scripts/tutor.py` + `tutorlib/` — 143 pytest tests green; runs on clean Python via vendored wheels.
- Plugin: tutor + study-arsenal skills, mode references (onboarding, after-video, mark, paper), 7 commands, marker/digest agents, SessionStart hook, README.
- Sources: 6 specs + 639 past papers/MS/ER in `sources/` (index.csv).
- Syllabus extraction: 9701 (354 outcomes), 9702 (300), IAL 12 units (219) -> `build/work/graph/*.input.json`; subtopics match Almanac 100%.
- Command words: `build/command_words.json`.

## In flight / next
1. KC enrichment agents write `build/work/graph/<chunk>.enriched.json` (7 chunks). Check all 7 exist, then `python build/graph.py merge` (validates types, prereqs, DAG).
2. Almanac import -> `plan.json` (map OBJ specRefs to KCs; split repeated sections across weeks; NEW objectives only). P3 sits Jun 2027: move P3 paper objectives (weeks 70–84) into year-1 exam weeks 27–35 like P2; fix PAPERS entry + catch-up ladder + Maths Overview text (backup both HTML files first).
3. Content packs batch 1 (9702 §1–2 first, then Almanac weeks 4–10): mine CAIE P1 MCQs + P2 structured + ER misconceptions, draft packs (Sonnet), validate_pack.py, blind-solve, adjudicate.
4. Vault setup: create `Notes/01 Study/STEM Tutor/.tutor/` (config tz Asia/Hong_Kong, packs v1, CURRENT), lesson notes, Papers/, Assets/; Obsidian plugins (Latex Suite, Chem) in root `.obsidian`; render test via screenshot; Bases dashboard.
5. Package `dist/stem-tutor.plugin`; Cowork full-arsenal routing line; E2E + Haiku-parity evals.
