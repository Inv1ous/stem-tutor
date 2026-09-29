export const meta = {
  name: 'build-packs',
  description: 'Draft, blind-solve and adjudicate A-Level content packs (token-lean), one pipeline per subtopic',
  whenToUse: 'Building STEM Tutor content packs for a list of subtopic ids (args: array of ids)',
  phases: [
    { title: 'Draft', detail: 'Sonnet drafts pack + lesson note per PACK.md; write once, fix with small edits', model: 'sonnet' },
    { title: 'Blind-solve', detail: 'independent Sonnet solver answers every item without keys; fact review', model: 'sonnet' },
    { title: 'Adjudicate', detail: 'resolve disagreements and fact errors, re-validate (only when needed)' },
    { title: 'Recheck', detail: 'fresh blind solve of items changed during adjudication', model: 'sonnet' },
  ],
}

const ROOT = '/Users/sora/Miscellaneous/02 Education/~~ AI Workflow/stem-tutor'
const PY = '.venv/bin/python'
const subs = Array.isArray(args) ? args : []
if (!subs.length) throw new Error('pass subtopic ids as args')

const DRAFT = { type: 'object', properties: {
  pack_path: { type: 'string' }, note_path: { type: 'string' }, items: { type: 'number' }, past_items: { type: 'number' },
  templates: { type: 'number' }, validator_ok: { type: 'boolean' }, lint_ok: { type: 'boolean' }, diagrams: { type: 'number' },
  concerns: { type: 'array', items: { type: 'string' } } },
  required: ['pack_path', 'note_path', 'items', 'validator_ok', 'lint_ok'] }
const SOLVE = { type: 'object', properties: {
  agreed: { type: 'number' },
  disagreements: { type: 'array', items: { type: 'object', properties: {
    id: { type: 'string' }, key: {}, solver: { type: 'string' }, solver_reasoning: { type: 'string' } }, required: ['id', 'solver', 'solver_reasoning'] } },
  fact_issues: { type: 'array', items: { type: 'object', properties: {
    where: { type: 'string' }, issue: { type: 'string' }, fix: { type: 'string' }, severity: { type: 'string', enum: ['error', 'improve'] } },
    required: ['where', 'issue', 'severity'] } } },
  required: ['agreed', 'disagreements', 'fact_issues'] }
const ADJ = { type: 'object', properties: {
  key_fixed: { type: 'number' }, solver_wrong: { type: 'number' }, facts_fixed: { type: 'number' },
  validator_ok: { type: 'boolean' }, lint_ok: { type: 'boolean' }, remaining: { type: 'array', items: { type: 'string' } } },
  required: ['validator_ok', 'lint_ok', 'remaining'] }

const RECHK = { type: 'object', properties: { rechecked: { type: 'number' }, agreed: { type: 'number' }, fixed: { type: 'number' },
  remaining: { type: 'array', items: { type: 'string' } } }, required: ['rechecked', 'agreed', 'remaining'] }
const RECHECK = (s, pack) => `Working directory: ${ROOT}. Some questions in pack ${pack} (subtopic ${s}) changed after they were blind-solved. ` +
  `1. Run \`${PY} build/blind.py stale ${pack} build/work/blind/${s}.answers.json\` — it prints only the ids that need a fresh solve (no answers). If it prints nothing, return rechecked 0. ` +
  `2. Run \`${PY} build/blind.py strip ${pack} --ids <those ids> > build/work/blind/${s}.recheck.questions.json\`, read ONLY that file, and solve each question yourself with full working (python/sympy). ` +
  `3. Write {"<id>": "<answer>"} to build/work/blind/${s}.recheck.json, then merge it into build/work/blind/${s}.answers.json (replace those ids) and run \`${PY} build/blind.py compare ${pack} build/work/blind/${s}.answers.json --ids <those ids>\`. ` +
  `4. For any remaining disagreement, now open the pack, work it from scratch and decide: fix the key/question if wrong (then re-run the validator), or record that your own answer was wrong. Report counts and anything unresolved. Aim for at most 20 tool calls.`
const LEAN = 'Work economically: write each file once (a pack generator script in build/work/gen/ that holds the content as data and computes every numeric answer is ideal), then fix problems with small targeted edits — never regenerate a whole file. Aim for at most 30 tool calls.'

const results = await pipeline(
  subs,
  s => agent(
    `Working directory: ${ROOT}. Build the content pack for subtopic ${s}.\n` +
    `Read build/PACK.md (spec and quality bar) and the bundle build/work/bundles/${s}.md. ` +
    `If the pack file already exists from an interrupted run, validate it and complete what is missing instead of starting over.\n` +
    `Coverage target per KC: the validator minimum of 6 retrieval variants (a template counts 3) up to about 8 — typically one or two templates plus two or three fixed items (concept MCQ with misconception distractors, an exam-style item). Quality over quantity.\n` +
    `Write the pack JSON and the Obsidian lesson note exactly where the bundle says; request diagrams in the pack's "diagrams" list and render them with \`${PY} build/diagrams.py <pack path>\`. ` +
    `Verify every numeric answer, distractor and worked step with python/sympy as you write it (sympy is in the venv).\n` +
    `Finish only when both are clean: \`${PY} build/validate_pack.py <pack path> build/out/specs/<spec>/graph.json\` and \`${PY} plugin/stem-tutor/skills/tutor/scripts/tutor.py lint "<note path under build/out/notes>"\`.\n` + LEAN,
    { label: `draft ${s}`, phase: 'Draft', model: 'sonnet', effort: 'high', schema: DRAFT }),
  (d, s) => d && agent(
    `Working directory: ${ROOT}. You are an independent examiner checking the content pack for subtopic ${s} (syllabus statements in build/work/bundles/${s}.md).\n` +
    `STEP 1 — blind solve. Run \`${PY} build/blind.py strip ${d.pack_path} > build/work/blind/${s}.questions.json\` and read ONLY that file (do not open the pack yet). ` +
    `Solve every question with full working (python/sympy for arithmetic): MCQ letter; numeric value with unit to 3 s.f.; expression in sympy syntax. ` +
    `Write {"<id>": "<answer>", ...} to build/work/blind/${s}.answers.json and run \`${PY} build/blind.py compare ${d.pack_path} build/work/blind/${s}.answers.json\`. Re-check your working on each disagreement.\n` +
    `STEP 2 — fact review. Read the pack and the lesson note (build/out/notes/${d.note_path}). Report factual or mathematical errors, content beyond or against the syllabus, definitions not in mark-scheme wording, hints that give away the answer, MCQ distractors that are also correct, wrong constants, rendering problems. Severity "error" for anything wrong, "improve" for quality.\n` +
    `Aim for at most 25 tool calls.`,
    { label: `solve ${s}`, phase: 'Blind-solve', model: 'sonnet', effort: 'high', schema: SOLVE }).then(v => ({ d, v })),
  (r, s) => {
    if (!r || !r.v) return { sub: s, error: 'draft or solve failed', draft: r && r.d }
    const { d, v } = r
    const errors = v.fact_issues.filter(f => f.severity === 'error')
    if (!v.disagreements.length && !errors.length && !v.fact_issues.length) return { sub: s, draft: d, solve: v, adj: null }
    return agent(
      `Working directory: ${ROOT}. Adjudicate the review of content pack ${d.pack_path} (subtopic ${s}; lesson note build/out/notes/${d.note_path}; syllabus in build/work/bundles/${s}.md; rules in build/PACK.md).\n` +
      `Key vs blind-solver disagreements:\n${JSON.stringify(v.disagreements)}\nFact-review issues:\n${JSON.stringify(v.fact_issues)}\n` +
      `For each disagreement, work the problem from scratch (python/sympy) and decide who is right; fix the key, wording, template or distractors when they are wrong or ambiguous, leave it when the solver erred. ` +
      `Fix every "error" issue and each "improve" issue that is clearly right. Re-run the validator, the note lint and diagrams if changed, and \`${PY} build/blind.py compare\` against build/work/blind/${s}.answers.json. ` +
      `Report what changed and anything unresolved. ${LEAN}`,
      { label: `adjudicate ${s}`, phase: 'Adjudicate', effort: 'high', schema: ADJ }).then(a => ({ sub: s, draft: d, solve: v, adj: a }))
  },
  (r, s) => (!r || !r.adj) ? r : agent(RECHECK(s, r.draft.pack_path), { label: `recheck ${s}`, phase: 'Recheck', model: 'sonnet', effort: 'high', schema: RECHK })
    .then(k => ({ ...r, recheck: k })),
)

return results.map((r, i) => r ? {
  sub: r.sub || subs[i], items: r.draft && r.draft.items, past: r.draft && r.draft.past_items,
  agreed: r.solve && r.solve.agreed, disagreements: r.solve && r.solve.disagreements.length,
  fact_errors: r.solve && r.solve.fact_issues.filter(f => f.severity === 'error').length,
  key_fixed: r.adj && r.adj.key_fixed, solver_wrong: r.adj && r.adj.solver_wrong, facts_fixed: r.adj && r.adj.facts_fixed,
  final_ok: r.adj ? (r.adj.validator_ok && r.adj.lint_ok) : (r.draft && r.draft.validator_ok && r.draft.lint_ok),
  recheck: r.recheck ? { n: r.recheck.rechecked, agreed: r.recheck.agreed, fixed: r.recheck.fixed || 0, remaining: r.recheck.remaining } : null,
  remaining: r.adj ? r.adj.remaining : [], concerns: r.draft && r.draft.concerns, error: r.error || null,
} : { sub: subs[i], error: 'failed' })
