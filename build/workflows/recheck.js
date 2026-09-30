export const meta = {
  name: 'recheck-packs',
  description: 'Fresh blind solve of pack items changed after their first blind solve',
  phases: [{ title: 'Recheck', detail: 'Sonnet re-solves only the stale ids, then resolves disagreements', model: 'sonnet' }],
}
const ROOT = '/Users/sora/Miscellaneous/02 Education/AI Workflow/stem-tutor'
const PY = '.venv/bin/python'
const RECHK = { type: 'object', properties: { rechecked: { type: 'number' }, agreed: { type: 'number' }, fixed: { type: 'number' },
  remaining: { type: 'array', items: { type: 'string' } } }, required: ['rechecked', 'agreed', 'remaining'] }
const items = Array.isArray(args) ? args : []   // [{sub, pack}]
const out = await parallel(items.map(it => () => agent(
  `Working directory: ${ROOT}. Some questions in pack ${it.pack} (subtopic ${it.sub}) changed after they were blind-solved. ` +
  `1. Run \`${PY} build/blind.py stale ${it.pack} build/work/blind/${it.sub}.answers.json\` — it prints only the ids that need a fresh solve (no answers). If it prints nothing, return rechecked 0. ` +
  `2. Run \`${PY} build/blind.py strip ${it.pack} --ids <those ids> > build/work/blind/${it.sub}.recheck.questions.json\`, read ONLY that file, and solve each question yourself with full working (python/sympy). ` +
  `3. Write {"<id>": "<answer>"} to build/work/blind/${it.sub}.recheck.json, merge it into build/work/blind/${it.sub}.answers.json (replace those ids) and run \`${PY} build/blind.py compare ${it.pack} build/work/blind/${it.sub}.answers.json --ids <those ids>\`. ` +
  `4. For any remaining disagreement, now open the pack, work it from scratch and decide: fix the key/question if wrong (then re-run the validator), or record that your own answer was wrong. Report counts and anything unresolved. Aim for at most 20 tool calls.`,
  { label: `recheck ${it.sub}`, phase: 'Recheck', model: 'sonnet', effort: 'high', schema: RECHK })))
return out.map((r, i) => ({ sub: items[i].sub, ...(r || { error: 'failed' }) }))
