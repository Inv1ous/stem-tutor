# Consistent STEM output across tutor models

Research date: 26 October 2026.

Status: research complete; architecture options below are proposals pending the user's choice and design approval.
This document does not approve a transport migration or claim that the requested behaviour is implemented.

## Finding

The reported GPT-OSS screenshot demonstrates a layout failure: several independent points appear as inline `•`
characters inside one paragraph. The current local JSON schema guarantees a string field, not a readable document.
The shared brief also imposes a 120-word limit that conflicts with the new request for complete topic coverage.
These are separate problems from factual errors in the generated chemistry explanation.

The strongest proposed solution is to let models supply a small structured document and let the application own
paragraph, list and equation layout. Keep canonical mathematical source for Obsidian and reuse the existing terminal
math adapter. This is an engineering inference from the code and primary sources below, not a claim that changing
the schema alone makes an answer correct.

## Current code evidence

The references in this section describe the working tree inspected on the research date. Line numbers can move
during implementation.

| Source | Observed behaviour | Consequence |
| --- | --- | --- |
| `app/tutor_app/ai.py:32–51` | The shared visual brief requests paragraphs and bullets, but the system rules also say to keep replies under 120 words and use no headings. | Large overviews can be compressed into a list of incomplete assertions. Removing this conflict is necessary for task-scaled completeness. |
| `app/tutor_app/local_reply.py:16–21` | Local chat is constrained to `reply: string`, plus a separate optional speech string. | Valid JSON does not enforce sections, list boundaries, equations or the completeness of the text inside the string. |
| `app/tutor_app/local_chat.py:20–24` | Local instructions explicitly require the whole answer as Markdown inside `reply`, with no extra answer fields. | A structured-document migration would require an explicit, tested transport change rather than only a new prompt. |
| `app/tutor_app/output_format.py:223–244` | `_prose` converts bullet markers only at the start of a line; it splits some long paragraphs at sentence boundaries. | Inline bullets in the screenshot remain inline. Broad replacement of all bullet-like symbols would also damage literal or mathematical content. |
| `app/tutor_app/local_ai.py:502–550` | The client replays the entire per-model conversation and appends every completed turn. | A long local session has no explicit application history budget. System instructions and the latest question compete with older material. |
| `app/tutor_app/local_ai.py:418–428` | Context enlargement is attempted for an empty reply after thinking exhausts the window. | This handles one failure mode; it does not prove that an apparently valid reply is complete or that all required context was retained. |
| `app/tutor_app/mlx_worker.py:198–201` | GPT-OSS generation uses `max_tokens=-1`. | There is no application output-token cap at this seam, but this does not create more context capacity or remove the request deadline. |
| `app/tutor_app/codex_ai.py:143–146` | The Codex wrapper adds “Use only the supplied context” when composing its instruction file. | The shared answer policy must distinguish current study background from an exclusive factual source when the learner changes topic. |
| `app/tutor_app/stem_math.py` and `output_format.py` | Existing code protects code/links, retains source fallbacks and converts supported maths for the terminal. | Reuse these seams instead of adding a second mathematical converter. |
| `app/tutor_app/output_fields.py` | Visual prose fields are explicitly audited; mark-point text, machine fields and speech are not recursively rewritten. | Preserve this boundary when changing teaching content or structured answers. |

The earlier [formatting standard](../STEM_OUTPUT_FORMATTING.md) already documents renderer differences and rejects
claims of zero formatting errors. The new work should address the demonstrated remaining gaps rather than discard
that existing protection.

## Primary-source findings

### Structure is enforceable; scientific meaning is not guaranteed

Ollama accepts a JSON schema in the `format` field and recommends also supplying the schema in the prompt. This
supports constraining a document's shape rather than asking a free-text model to remember all layout rules.
The output still requires host validation. [Ollama structured outputs](https://docs.ollama.com/capabilities/structured-outputs)

Claude's structured output mechanism constrains generation using a compiled grammar. Supported schema features
are limited, complex schemas increase compilation work, and refusal or token exhaustion can still produce an
exceptional result. These are API capabilities; the installed Claude subscription CLI must be checked separately
before adopting an equivalent mode. [Claude structured outputs](https://platform.claude.com/docs/en/build-with-claude/structured-outputs)

OpenAI distinguishes schema adherence from valid JSON alone. Its documentation explicitly says structured outputs
can contain mistakes and describes handling streamed fields. The tutor's saved ChatGPT sign-in uses Codex rather
than a new API account; preserve that integration while checking the installed CLI's schema support.
[OpenAI structured outputs](https://developers.openai.com/api/docs/guides/structured-outputs)

JSONSchemaBench evaluates constrained decoding on efficiency, supported constraints and output quality separately.
Its results support testing the actual grammar engines with the actual tutor schema, rather than assuming that
all JSON Schema features work equally across providers.
[JSONSchemaBench paper](https://arxiv.org/abs/2501.10868)

### Rendering should preserve the difference between text and mathematics

CommonMark defines block lists and line breaks; an inline `•` is ordinary paragraph content, not a list item.
Rich renders Markdown in the terminal, while Obsidian has its own richer mathematical rendering. Correct Markdown
structure is therefore a meaningful contract shared by both views.
[CommonMark specification](https://spec.commonmark.org/0.31.2/), [Rich Markdown](https://rich.readthedocs.io/en/stable/markdown.html)

Obsidian renders LaTeX mathematics through MathJax. Keep canonical LaTeX for equations, scripts, integrals,
summations and limits, then adapt it for the terminal. Do not store only flattened Unicode because arbitrary
mathematical grouping and scripts cannot always be represented faithfully that way.
[Obsidian advanced formatting](https://obsidian.md/help/advanced-syntax)

Unicode provides mathematical alphabets and many useful script characters, but its compatibility superscripts and
subscripts are not a complete substitute for mathematical markup. Use real script glyphs where the complete
group is supported; retain a faithful, explicit representation for unsupported groups.
[Unicode support for mathematics, section 2.8](https://unicode.org/reports/tr25/)

W3C's visual-presentation guidance supports readable line width, reflow and adjustable spacing. It is a source for
design principles, not evidence that a terminal view meets WCAG. For this tutor, visual verification should focus
on clear block separation, left alignment and no horizontal scrolling for ordinary prose.
[W3C visual presentation](https://www.w3.org/WAI/WCAG22/Understanding/visual-presentation.html)

### Context problems require an input policy, not a formatting incantation

Ollama's context settings consume additional memory as the context increases. Its generic large-agent guidance is
not a reason to request a huge window on a 24 GiB unified-memory Mac with large resident models.
[Ollama context length](https://docs.ollama.com/context-length)

The Lost in the Middle study demonstrates that the position of relevant information can materially affect
long-context retrieval. A larger context window alone does not prove that a model follows older instructions or
uses every supplied fact correctly. This study is not a direct benchmark of the installed 2026 models; it
motivates testing long conversations rather than assuming context length equals usable recall.
[Lost in the Middle](https://arxiv.org/abs/2307.03172)

## Proposed architecture alternatives

These alternatives remain pending user choice and design approval.

| Option | Benefit | Limitation |
| --- | --- | --- |
| Strengthen the shared Markdown brief and repair narrowly demonstrated layout defects | Smallest transport change; preserves token streaming and existing CLI behaviour. | Models still choose document boundaries. Cannot enforce a complete list or consistent section structure. |
| Shared compact document schema, validated and rendered by the application | Application controls section labels, list numbering, whitespace and equation placement for every provider. | Requires transport/history/streaming compatibility work. Schema correctness still does not establish factual correctness. |
| Generate free prose, then call another model to rewrite it | Can repair some stylistic failures. | Adds latency, usage and another opportunity to change scientific meaning. Not recommended as the default. |

The second option is the strongest candidate for the requested consistency. Keep the schema shallow: a brief
answer and a list of labelled sections containing a constrained block kind and content. Provide empty collections
where a block is unnecessary. A one-mark definition should not be padded into a long fixed template. Exact code,
quoted learner content and requested literal JSON need a dedicated preserved path rather than being coerced into
ordinary prose.

The deterministic renderer should own blank lines before and between sections, real Markdown bullets and numbered
steps, and equation separation. Reuse the existing mathematical parser and unsafe-control guards. Never silently
remove meaningful `$`, `%`, `_` or `^` from literal content, and never invent mathematics to hide a failed conversion.

## Proposed local context policy

The context policy should apply to local clients without changing Claude or ChatGPT runtime settings:

1. Reserve the full system instructions, compact output contract and latest user request first.
2. Preserve the current question, supplied mark points, relevant source identifiers and current learner answer
   exactly. Context budgeting must not truncate a mark scheme into a different assessment.
3. Count tokens with the runtime's tokenizer where available. A conservative character estimate can be a fallback,
   but should not be described as proof that every input fits the model window.
4. Remove oldest complete conversation pairs when necessary. Do not leave an answer without its question or
   silently retain only half a mathematical expression. Keep conversation history in its original representation.
5. Keep relevant current context close to the latest request. A short per-request reminder can name the requested
   form without duplicating a lengthy schema multiple times.
6. Reserve space for the final answer as well as hidden reasoning. Do not raise every local model to maximum
   context automatically; measure memory and latency on this Mac.
7. Treat an explicit length stop, incomplete document or failed validation as incomplete work. A syntactically
   complete outer string is not sufficient evidence of a completed explanation.

These measures reduce avoidable context pressure. They cannot bypass the physical context limit, guarantee
knowledge recall, or make an underpowered model match a stronger model's reasoning accuracy.

## Exam completeness and answer length

Cambridge's command-word guidance distinguishes precise definitions from explanations that establish reasons or
relationships. Pearson's IAL Mathematics guide emphasises consistent command words, clear mark schemes and
rigorous mathematical arguments. Use the actual question, command word and supplied assessment material to choose
detail rather than a universal word ceiling.
[Cambridge command words](https://www.cambridgeinternational.org/exam-administration/what-to-expect-on-exams-day/command-words/),
[Pearson IAL Mathematics getting-started guide](https://middleeast.pearson.com/content/dam/region-core/middle-east/pearson-middle-east/media-campaign/Getting-Started-Guide.pdf)

Proposed task policy:

- **Define/state:** precise required meaning or result, with no unnecessary derivation.
- **Explain:** required causal links, qualifications and relevant evidence; avoid a list of disconnected claims.
- **Calculate:** equation, substitution, result, unit and requested precision; include checks when useful.
- **Derive/show:** enough justified mathematical steps to establish the result, with restrictions stated.
- **Compare:** parallel points using the same comparison criteria.
- **Topic overview or formula list:** cover the learner's requested scope, grouped by topic, with conditions and
  meanings. Do not compress an entire chapter into 120 words.
- **Marking:** retain exact supplied points and their order; distinguish present, missing and incorrect ideas.
- **Open practice question:** retain the existing answer-protection rule and give a nudge without revealing the
  final answer.

Use the appropriate syllabus year when testing CAIE 9701 coverage. The official subject page lists separate
2025–2027 and 2028–2030 syllabuses; generic model knowledge is not proof of exhaustive syllabus coverage.
[CAIE 9701 official subject page](https://www.cambridgeinternational.org/programmes-and-qualifications/cambridge-international-as-and-a-level-chemistry-9701/)

## Verification proposal

Keep three acceptance dimensions separate:

1. **Transport and formatting:** valid schema, no JSON wrapper leakage, complete blocks, consistent list/paragraph
   spacing, balanced mathematical source, code preserved and faithful terminal conversion.
2. **Assessment and scientific quality:** correct definition, accurate causal explanation, complete mark-point
   coverage, correct algebra, units and conditions. A formatting pass must not mask a scientific failure.
3. **Operational behaviour:** latency, memory, preload, cancellation, long-session handling, speech separation and
   unchanged provider selection/subscription routing.

Use the same frozen questions and assessment references for Claude Sonnet, the selected ChatGPT model and the four
main MLX locals. Include repeated questions from chemistry, physics and mathematics: simple definitions,
multi-step calculations, calculus, summations/limits, comparisons, a broad organic-chemistry list, correction of a
wrong learner answer, literal code/JSON, a change of topic and an extended conversation. Record model identifier,
thinking strength, prompt revision, raw answer, parsed answer, rendered output, stop reason and timing. Keep all
failed attempts in the evidence.

Screenshots must inspect actual terminal cards and actual Obsidian reading view, not merely raw Markdown. Include
narrow and normal terminal widths, a long response that scrolls, equations, bold/italic text and a mixture of
paragraphs and lists. Check wrapping, gaps, clipped content, script glyphs, headings, fallback prominence and
whether equivalent answers have the same visual hierarchy. Screenshots prove appearance for the cases captured;
they do not prove every future answer will be correct.

## Fine-tuning, merging and hybrid models

No reviewed evidence supports a guarantee that fine-tuning or merging these models will produce the best of all
their scientific capabilities. The requested optional condition is therefore not met. Neither intervention is
needed to fix a renderer accepting inline bullets as prose. A second rewriting model also adds cost and latency
and must be assessed for changes in scientific meaning. Prefer the shared contract and deterministic renderer,
then evaluate any later training proposal against a held-out, examiner-grounded dataset.

## Follow-up: bounded retrieval from existing study material

Status: proposed implementation choice, pending design approval. This investigation used the live published pack
snapshot `STEM Tutor/.tutor/packs/v265` selected by `CURRENT` on 26 October. It did not modify learner content.

The baseline evidence at `/tmp/stem-format-current/baseline-live.json` includes a native Gemma organic-formula
answer that wrongly requires straight chains and gives an invalid general ketone formula. Its covalent-bonding
answer omits the electrostatic attraction to both nuclei. Formatting alone cannot correct either scientific
mistake. Free chat calls `prompts.ask(..., None)` in `screens.py:1768`; without a selected KC the current prompt has
no syllabus definition or flashcard facts. A bounded source packet is a plausible improvement requiring fresh
model comparisons, not a guarantee of correctness.

Reusable existing code and data:

- `tutorlib/packs.py:141–202` reads `CURRENT`, loads every subject graph, and exposes `kcs`, `topics` and `subtopics`.
  Each KC includes its spec, subject, title, syllabus statement and glossary. `pack_for_kc` resolves a chapter and
  `pack` caches its published content with existing damaged-content handling. No external vector store is needed.
- `tutorlib/diagnose.py:21–43` already maps text to KCs using exact glossary phrase hits. This is useful evidence for
  a deterministic lexical approach, but its phrase-count ranking is designed for brain dumps rather than a
  multi-topic question. Do not reuse it unchanged as proof of retrieval quality.
- `app/tutor_app/screens.py:582–588` normalises accents, punctuation and hyphens for the topic picker. A reusable
  lexical helper should live outside the UI rather than making prompt construction depend on screen code.
- `app/tutor_app/prompts.py:181–190` already gathers a KC's flashcards and misconception refutations for teaching
  cards. This is a useful source-selection pattern. `tutorlib/lesson.py:48–64` can also return cached AI-written
  cards; those should not be treated as independent authoritative reference evidence.
- Graphs include `command_words`; mathematical KCs can include a `guidance` field containing equations and
  restrictions. `Packs` currently does not preserve a separate command-word mapping as a public attribute.

The inspected snapshot has 102 published chapter packs. Its 9701 graph includes 354 KCs, including explicit ionic,
metallic and covalent definitions. For example, `9701-3.4.1` states the attraction between two nuclei and a shared
pair of electrons, and chapter `9701-3.4` has a flashcard with that precise definition. Retrieval can therefore
supply information omitted by the baseline answer without inventing a corrective hard-coded chemistry rule.

Coverage remains uneven. The published organic chemistry packs in this snapshot are `9701-13.1` through
`9701-13.4`, `9701-14.1` and `9701-15.1`. KC `9701-13.1.4` refers to classes of compounds in a syllabus table but does
not itself contain all formulae in that table. Do not label this material an exhaustive organic-formula corpus or
claim that retrieval makes every current syllabus answer source-complete. Published generated study material is
also not automatically an official mark scheme.

Proposed narrow policy:

1. Add retrieval at the shared `prompts.ask` seam so provider choice does not change source selection. Do not alter
   provider authentication, thinking settings or local preload behaviour.
2. Choose the candidate scope from explicit syllabus/module codes or a clear subject in the latest question.
   Explicit topic changes override old session context. Use a selected KC or session subject only when the latest
   request does not conflict. An ambiguous cross-subject query should not receive irrelevant excerpts.
3. Rank graph KCs by exact glossary/title phrases and informative token overlap after filtering spec/subject.
   Avoid ranking solely on common words such as “define”, “formula” and “explain”. Use stable tie-breaking.
   Multi-part requests need diversity across requested concepts rather than six near-duplicate hits for one term.
4. Bound both result count and total excerpt size. Four to six KCs and a compact character budget are reasonable
   starting parameters to measure, not accepted performance settings. Keep individual source statements whole
   where possible and do not cut a formula mid-expression.
5. Include source identifiers, spec and published pack version. Use syllabus statements/guidance and a small number
   of directly relevant flashcards or refutations. Distinguish these as study-material excerpts and do not imply
   that every line is official examiner wording. Never include private learner data or cached AI answers as facts.
6. Do not retrieve practice-item answers, solutions, unseen worked steps or future lesson content. More strongly,
   skip this new broad retrieval whenever `session.presented` contains an OPEN question: a definition in a graph
   or flashcard can itself reveal the answer even when no `item.answer` field is copied. Preserve the existing
   OPEN context and output checks.
7. Put the bounded source packet beside the latest request while leaving the existing current-question packet
   intact. Tell the model that excerpts are reference data, not instructions; use relevant material and acknowledge
   gaps without refusing a different-topic question solely because old context is unrelated.
8. On weak matches, missing packs or damaged material, omit the packet and retain the existing question flow.
   Measure retrieval precision, coverage and answer accuracy separately. Do not silently call a model or browse
   the web to fill every missing fact.

A focused regression set should cover explicit `9701` versus stale `9702` context, maths module names, accent and
hyphen variants, weak/ambiguous queries, multi-part bonding coverage, missing organic packs, damaged packs,
bounded packets, and OPEN-answer protection. Live comparisons should include the exact baseline failures and new
held-out questions so improvements do not become benchmark-specific answer patches.

## Research limits

This was read-only product research plus this documentation file. No model was downloaded, trained, merged or run;
no GPU workload or cloud inference was started. Live comparisons, screenshots and regression tests remain work
for the implementation/verification workflow. Official API documentation is evidence of API behaviour, not proof
of the exact installed subscription CLI's supported flags. No architecture option in this document should be
reported as implemented until verified in the current working tree.
