export const meta = {
  name: 'tutor-parity-eval',
  description: 'Simulated learners with planted misconceptions talk to the tutor (Haiku vs Opus) through the real engine; blind pairwise judging',
  phases: [
    { title: 'Sessions', detail: 'alternating tutor (model under test) and learner persona (Sonnet) turns' },
    { title: 'Judge', detail: 'blind pairwise comparison per persona', model: 'sonnet' },
  ],
}

const ROOT = '/Users/sora/Miscellaneous/02 Education/~~ AI Workflow/stem-tutor'
const PLUGIN = `${ROOT}/plugin/stem-tutor`
const SCRIPTS = `${PLUGIN}/skills/tutor/scripts`
const { sessions, personas, turns } = args          // sessions: [{persona, model, vault}]
const MAX = turns || 14
const P = Object.fromEntries(personas.map(p => [p.id, p]))

const render = t => t.map(m => `${m.role === 'tutor' ? 'TUTOR' : 'LEARNER'}: ${m.text}`).join('\n\n')

const tutorPrompt = (s, t, transcript) =>
  `You are the tutor in a study session running inside Claude Cowork with the stem-tutor plugin. ` +
  `Read ${PLUGIN}/skills/tutor/SKILL.md and follow it exactly, including any reference file it tells you to read for the chosen mode. ` +
  `Run every engine command as: STEM_TUTOR_VAULT="${s.vault}" STEM_TUTOR_AUDIT=1 STEM_TUTOR_TURN=${t} python3 "${SCRIPTS}/tutor.py" <command>\n` +
  `Differences from Cowork in this session: AskUserQuestion is unavailable, so ask exactly those questions in chat (lettered options, and ask for confidence 1-4); you cannot send files; there was no SessionStart hook output. ` +
  `Learner-facing text is always full, clear sentences — ignore any instruction to compress output style.\n\n` +
  `Conversation so far:\n${render(transcript)}\n\n` +
  `Now take your next tutor turn: run whatever engine commands this turn needs, then return as your final text exactly the message you send to the learner, nothing else. ` +
  `If you have fully closed the session (session end and week done), end the message with [[END]].`

const learnerPrompt = (p, transcript) =>
  `You are role-playing an A-Level student in a tutoring chat. Stay in character; never mention being simulated.\n` +
  `Your knowledge and habits: ${p.profile}\n` +
  `Reply to the tutor's last message as this student would: answer questions according to your knowledge (make your characteristic mistakes consistently until the tutor genuinely corrects them with a reason), ` +
  `give confidence 1-4 when asked, keep messages short and natural. If asked to upload handwritten work, say you can't right now.\n\n` +
  `Conversation so far:\n${render(transcript)}\n\nReturn only your next message.`

async function runSession(s) {
  const p = P[s.persona]
  const transcript = [{ role: 'learner', text: p.opening }]
  for (let t = 1; t <= MAX; t++) {
    const reply = await agent(tutorPrompt(s, t, transcript), { label: `${s.persona}/${s.model} tutor ${t}`, phase: 'Sessions', model: s.model })
    if (reply === null) { transcript.push({ role: 'tutor', text: '[agent failed]' }); break }
    transcript.push({ role: 'tutor', text: String(reply) })
    if (String(reply).includes('[[END]]')) break
    const learner = await agent(learnerPrompt(p, transcript), { label: `${s.persona}/${s.model} learner ${t}`, phase: 'Sessions', model: 'sonnet', effort: 'low' })
    if (learner === null) break
    transcript.push({ role: 'learner', text: String(learner) })
  }
  return { ...s, transcript }
}

const done = await parallel(sessions.map(s => () => runSession(s)))
const runs = done.filter(Boolean)

const JUDGE = { type: 'object', properties: {
  winner: { type: 'string', enum: ['A', 'B', 'tie'] },
  scores_A: { type: 'object', properties: { accuracy: { type: 'number' }, pedagogy: { type: 'number' }, diagnosis: { type: 'number' }, clarity: { type: 'number' } } },
  scores_B: { type: 'object', properties: { accuracy: { type: 'number' }, pedagogy: { type: 'number' }, diagnosis: { type: 'number' }, clarity: { type: 'number' } } },
  errors_A: { type: 'array', items: { type: 'string' } }, errors_B: { type: 'array', items: { type: 'string' } },
  reason: { type: 'string' } }, required: ['winner', 'scores_A', 'scores_B', 'errors_A', 'errors_B', 'reason'] }

const judged = await parallel(personas.map((p, i) => () => {
  const pair = runs.filter(r => r.persona === p.id)
  if (pair.length < 2) return null
  const [a, b] = i % 2 ? [pair[1], pair[0]] : [pair[0], pair[1]]
  return agent(
    `You are an experienced A-Level teacher judging two AI tutoring sessions with the same simulated student (profile: ${p.profile}). ` +
    `Score each 1-5 on: accuracy (every fact, answer and explanation correct), pedagogy (student attempts before any answer, one step per turn, hints that don't give answers away, misconceptions refuted with a reason and contrasting case), ` +
    `diagnosis (did the tutor find and fix the student's real problem), clarity (clear, warm, concise). List every factual or pedagogical error you see. Then pick the better session or tie.\n\n` +
    `SESSION A:\n${render(a.transcript)}\n\n----------\n\nSESSION B:\n${render(b.transcript)}`,
    { label: `judge ${p.id}`, phase: 'Judge', model: 'sonnet', effort: 'high', schema: JUDGE })
    .then(j => j && ({ persona: p.id, A: a.model, B: b.model, ...j }))
}))

return { runs: runs.map(r => ({ persona: r.persona, model: r.model, vault: r.vault, turns: r.transcript.length, transcript: r.transcript })),
         judgements: judged.filter(Boolean) }
