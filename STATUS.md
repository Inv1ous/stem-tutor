# Build status

## Overnight build (2026-09-29 → 30) — terminal app; plan: ~/.claude/plans/can-you-continue-what-polished-swing.md
- [ ] 1 Vault moved to `~~ AI Workflow/STEM Tutor` (local vault, Obsidian config, publish default, iCloud inbox)
- [ ] 2 Engine: texmath, views (Now/Lessons/My Notes/Home), lesson flow, teach-card fallback, inbox import (+tests)
- [ ] 3 AI client (persistent headless Claude, lean flags) + prompts (+fake-claude tests)
- [ ] 4 Textual app (+pilot tests, screenshots)
- [ ] 5 Launcher (`bin/tutor`, `Start Tutor.command`) + `doctor`
- [ ] 6 Teach cards for the 7 packs (Sonnet) + validate + publish
- [ ] 7 How It Works.md, Home.md, README, memory
- [ ] 8 Final offline E2E, commit, morning summary


## Done
- Engine `plugin/stem-tutor/skills/tutor/scripts/` — 161 pytest tests green; clean-Python run via vendored wheels.
  Live `Question Sheets/Current.md`; Unicode sub/superscripts converted to LaTeX in notes.
- Plugin: tutor + study-arsenal skills, mode references, 7 commands, marker/digest agents, SessionStart hook.
- Sources: 6 specs + 639 past papers/MS/ER (`sources/index.csv`).
- Syllabus graph: 873 KCs across 14 specs (`build/out/specs/*/graph.json`); Year-1 chunks enriched by agents,
  A2 chunks (9701 23–37, 9702 12–25) are heuristic placeholders (`enriched: false`) — enrich before Feb 2027.
- Almanac import `build/out/plan.json`: all 873 KCs scheduled; 22 gap-fills listed in `added_by_tutor`.
  Planner HTML fixed for P3 → June 2027 (backups in `00 Important/01 AS:A/.backup/`).
- MCQ bank: 3360 CAIE Paper 1 MCQs with official keys (`build/work/mcq/`), 2204 figure crops;
  examiner-report comments split per question (`build/work/er/`).
- Build tools: validate_pack.py, bundle.py, diagrams.py (IEC symbols), blind.py, publish.py, tag_mcq.py.
- Vault: `Notes/01 Study/STEM Tutor/` published as pack v1 (graphs + plan + figures, no packs yet).
- Obsidian check (app 1.13.7): inline/display/aligned maths, mhchem `\ce`, callout maths, table maths,
  Mermaid, SVG and PNG embeds all render. Editor font lacks some Unicode subscripts → notes use LaTeX.
- `dist/full-arsenal-cowork.zip`: Cowork full-arsenal that hands study requests to study-arsenal (upload it).

## In flight
- Workflow `tag-caie-mcqs`: tag → audit → fix for 12 chunks; then `python build/tag_mcq.py merge`.
- Workflow `build-content-packs` pilot on P1-1, S1-2 (draft → blind-solve → adjudicate).

## Remote Cowork (verified 2026-09-29)
Cowork sessions run in a cloud container; `device_bash` runs in the Mac's VM with connected folders at
`$HOME/mnt/<folder>/`, and rm/unlink there fail until the learner grants deletion. The engine therefore ships
inside the vault (`.tutor/engine/`, copied by publish.py) and runs as `python3 ~/mnt/*/.tutor/engine/tutor.py`.
It never deletes (flock lock in the temp dir, closed session written as null) and refuses to run on a copy.

## Deferred audit findings (remote Cowork)
- digest agent + after-video transcript fallback cannot see device files: add `diagnose map --file`, stage via device_stage_files.
- /profile reads Profile.md that the container cannot see: add a `profile` engine command.
- mark mode: `inbox` should return absolute device paths for device_stage_files; name uploads <session>-<n>.pdf.
- paper mode: papers.json empty; say so, and stage paper + mark scheme before marking.

## Next
1. Review pilot packs; tune PACK.md; run `build-content-packs` over batch 1 (74 subtopics, weeks 1–10).
2. Anki: mark pack flashcards already in the learner's existing decks (dedupe) before first export.
3. Publish v2 with packs; package `dist/stem-tutor.plugin`; user uploads + Cowork Project setup.
4. E2E in Cowork + Haiku-parity evals.
5. Papers for paper mode (P2 + IAL question→KC maps), A2 enrichment, batch 2+ packs just in time.
