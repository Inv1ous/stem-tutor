# Structured tutor output across providers

Date: 26 October 2026. Status: approved by the user for implementation on 26 October 2026.

## Intent

Make Claude, ChatGPT and the main local models produce consistently readable STEM teaching in the terminal and
Obsidian. The reported GPT-OSS answer contains five inline bullet glyphs in one dense paragraph. The current
schema only constrains a reply string; the shared system also requests fewer than 120 words and forbids headings.
The application must own layout rather than relying on each model to remember Markdown punctuation.

The user requests detailed but concise A-Level answers, precise exam definitions and supplied mark-scheme coverage,
readable mathematics, extensive model comparisons and visual checks of both actual displays. Formatting consistency
means the same layout rules and mathematical conventions for the same response kind. It cannot mean identical
wording, guaranteed scientific accuracy or identical typography between a terminal and MathJax.

## Approaches

1. Strengthen Markdown prompts and repair demonstrated inline bullets. Smaller change, but a string schema cannot
   enforce document structure. This leaves the reported class of failure possible.
2. Use a compact structured document, validated and rendered by the app. More transport work, but paragraphs,
   headings, lists, numbering and equation spacing become application behaviour. **Selected by the user.**
3. Run a second model to rewrite every response. Adds latency, usage and another opportunity to change scientific
   meaning. Rejected as the default. Fine-tuning or merging local weights is also excluded: neither can guarantee
   the requested quality, and neither fixes a deterministic layout defect.

## Shared document

Add one small provider-neutral module for the schema, strict bounded incremental decoding, validation and rendering.
A chat answer is an object with a nonempty `blocks` array. Each block has exactly `kind` and `text`. Initial kinds:
`paragraph`, `heading`, `bullet`, `step`, `equation`, `code`. A separate `speech` string is required only when read
aloud is enabled. This shallow schema avoids provider-specific unions and arbitrary nested documents.

- A paragraph holds one logical idea. Inline emphasis, links and inline mathematics remain supported.
- A heading is a short label; the renderer supplies bold styling and surrounding blank lines.
- Each bullet or numbered step is its own block. The renderer supplies markers, numbering, hanging indentation
  and real blank lines. Consecutive steps number consistently; an immediately associated equation keeps the sequence. A heading, paragraph, bullet or code block restarts it.
- An equation holds mathematical source without outer delimiters. The renderer supplies a display-math block.
  Numbered steps may contain inline mathematics; associated equation blocks remain next to their explanation.
- Code holds literal text. The renderer chooses a safe fence and preserves its content. Requested literal JSON,
  code and source notation use this path. Comparisons normally use parallel bullets; no new table transport is
  needed for this defect. Existing structured teaching/marking content retains its established interfaces.
- A response may contain only one paragraph. No mandatory multi-section padding. Longer answers use short labels
  and grouped blocks, not a chapter-sized paragraph. The schema bounds transport size without imposing a new
  universal answer-length cap.

Emit only complete, validated blocks. Transport characters, field names and speech never appear in the answer.
The progress indicator remains until the first block is ready. Final canonical Markdown must equal the streamed
blocks and reach the existing card, Now.md and log boundaries. Failed or cancelled replies do not enter history.
Use a 4 MiB document bound, at most 256 blocks and a 256 KiB bound per block. Bounds apply while accumulating even ignored fields. Prose blocks cannot smuggle a whole Markdown document or a dense run of inline bullets; validate or safely normalise those cases outside protected literal and mathematical spans. Unknown controls and malformed data fail safely; unsupported mathematics retains the existing labelled source
fallback. Do not silently remove signs, charges, bounds, indices or units to produce a prettier answer.

## Provider integration

Keep the existing provider routes and ownership. Enable the document contract for tutor chat without rewriting
one-shot grading, solver, OCR, challenge or audit schemas.

- **Ollama and GPT-OSS MLX:** use the shared schema in the existing native `format` field and prompt. Replace only
  the tutor's chat envelope; keep the legacy reply decoder for its existing callers/tests where appropriate. Feed
  visible JSON fragments into the shared decoder after the existing local event/Harmony layers. Keep mandatory
  preload, request lock, deadlines, native reasoning strengths and owned-runtime cleanup.
- **ChatGPT:** use Codex's existing `--output-schema`. Its current transport delivers completed message blocks;
  retain that granularity, cancellation, subscription sign-in and model selection.
- **Claude:** use native `--json-schema` in a distinct chat-document mode. A bounded Sonnet probe on CLI 2.1.309
  confirmed `StructuredOutput` content blocks, `input_json_delta` events and a final `structured_output` object.
  Correlate message identity, tool-use ID and block index, since indices can restart between messages. Validate the final object; suppress narration and tool protocol. Do not concatenate repeated structured candidates. A final object that disagrees with emitted blocks is an incomplete failure, not a silently replaced successful answer. Do not
  feed these events through the current plain-text-only reader. Preserve the legacy reader for other uses.
  Keep persistent conversation reuse and actual usage accounting; do not request Opus or change saved model settings.

All clients use the same document renderer and field validation. Contract changes start fresh conversations; no old
plain-string history is mixed into document-mode history. Host-managed local and Codex histories retain validated protocol rather than an unstructured visual copy. Claude owns its internal tool history; reset that conversation after malformed, failed or divergent output. No automatic fallback to another provider or a second formatting-model request.
If native structured generation or host validation fails, show the existing actionable failure state and keep the
partial response clearly incomplete. Do not silently certify malformed output or silently spend an unbounded retry.

## Writing and assessment policy

Replace the blanket 120-word/no-heading rule with task-scaled guidance shared by all providers:

- Define/state: precise exam meaning or result, with necessary qualifications.
- Explain: causal links and conditions, with an example when useful.
- Calculate/derive/show: justified steps, formulae, substitution, result, units and requested precision.
- Compare: parallel criteria. Topic overview/formula list: cover the requested scope and assumptions.
- Mark/re-mark: preserve exact supplied mark points, order, values and learner evidence. Give a concise correction.
- Open practice question: retain answer protection and give only a useful nudge. Broad Ask mode remains free to
  change topic; recent lesson context is background rather than an exclusive knowledge source.

Do not claim a general-knowledge overview is an exhaustive official mark scheme. Ground assessed answers in the
supplied question, scheme and syllabus reference; state uncertainty when the relevant source is absent.
Keep private working, identifiers, numeric values, options, machine expressions, image transcription and speech
outside visual prose transformations. Existing whitelisted one-shot prose fields share the corrected writing brief.

## Bounded study references

Reuse the existing in-memory `Packs` syllabus graph and published study packs to supply relevant definitions and
facts to `prompts.ask` across all providers. This is a small lexical lookup, not a new embedding service or another
model request. An explicit syllabus/module or subject in the current question takes precedence over session
background. Rank exact glossary/title phrases and distinctive term overlap; omit weak or ambiguous matches.
Select at most six relevant syllabus points, bounded excerpts from their graph statements, matching flashcards and
misconception corrections. Include the syllabus-point ID and pack version as provenance. Skip this broad reference lookup whenever a practice question is OPEN, because even a glossary definition could reveal its answer. Keep current question,
OPEN restrictions and learner evidence intact; never retrieve hidden item answers, solutions or cached AI cards.

Label these as supplied study references, not an official mark scheme. Published packs do not cover every chapter,
so absent matches must not be presented as exhaustive syllabus evidence. Test subject/topic changes, weak matches,
answer protection, reference bounds and reproducible source ordering. This reduces dependence on local model recall
for covered facts without claiming a correctness guarantee.

## Local context protection

Local-only budgeting assembles the immutable system/schema and latest complete request first, reserving room for
reasoning and the final document. Remove only oldest complete user/assistant pairs when necessary. Never truncate
the latest question, mark scheme, mathematical expression or current image. Store only validated successful turns.

Use actual token counts where the existing runtime exposes its tokenizer cheaply; otherwise document a conservative
estimate and a bounded history limit. An estimate is not a guarantee of fitting the physical context window.
Oversized current requests fail with a clear message rather than silently losing assessment evidence. If an older
image turn is removed, reattach the current relevant image rather than assuming the model still sees it. Do not
increase every model's context or change sampling, model precision, reasoning levels or cloud history policy.

Reject explicit length/truncation stops and incomplete documents. A grammar-valid short fragment is still not proof
of a complete or correct explanation; live coverage checks must catch and report that separate failure.

## Display compatibility and preservation

Reuse `normalise_visual`, `terminal_visual`, `stem_math` and the existing AI card adapter. Obsidian keeps canonical
Markdown/LaTeX; the terminal uses faithful JuliaMono mathematical glyphs. Keep italic variables, upright units and
chemical elements, true complete scripts, grouped fallbacks for unsupported scripts, integrals, summations and
limits. Preserve code, URLs, currency and percentages. Do not modify historical learner notes or model weights.

Add narrow protected recovery for the reproduced inline prose bullets in cached/legacy AI content. Do not treat
mathematical dot products, chemical hydration dots or literal code as lists. Prefer real semantic blocks for new
responses, so recovery is compatibility work rather than the main structure mechanism.

Claude/ChatGPT settings, routing, authentication and thinking choices remain unchanged. Their tutor output contract
and shared writing policy intentionally change as requested. Local context management remains local-only.

## Verification and stop conditions

1. Red/green regressions cover the supplied screenshot, inline bullets, literal escapes, code, controls and maths.
2. Shared decoder tests cover every split boundary, JSON escaping/Unicode, duplicate/unknown fields, arbitrary field
   order, invalid kinds, empty documents, cancellation, incomplete replies and bounded storage. No protocol leakage.
3. Renderer tests cover one-paragraph hints, definitions, comparisons, long overviews, numbered calculations,
   equations, code, chemistry, units, powers, scripts, fractions, roots, derivatives, integrals, sums and limits.
   Same document yields the same canonical Markdown across providers; terminal math preserves meaning.
4. Local context tests prove oldest-pair pruning, current request preservation, image reattachment, contract identity,
   bounded memory and explicit truncation failure. Retain all preload/readiness/cancellation tests.
5. Live comparisons use frozen prompts on Sonnet, ChatGPT GPT-6.1-Sol, native Gemma 26B, E4B, Qwen 27B and GPT-OSS
   20B. Cover chemistry/physics/maths, precise definitions, broad formula lists, calculations/derivations,
   supplied-mark-point correction, topic changes, literal code/JSON, speech and long context. Repeat representative
   difficult cases. Record visible answers and timing, never hidden reasoning. Keep Claude exclusively Sonnet.
6. Score transport/layout, coverage/scientific correctness and latency separately. Preserve failed trials and
   disclose limitations. No test may equate schema validity with teaching accuracy or claim zero model error.
7. Capture actual Textual output at 80x24, 100x30 and 140x46 in Night/Day/Classic using isolated test data. Inspect
   screenshot pixels for gaps, wrapping, clipping and glyphs. Capture Obsidian reading view in an isolated vault;
   inspect actual MathJax, lists and code. Keep the user's live vault unchanged.
8. Run the complete documented test suite, `git diff --check` and independent Standards/Spec reviews. Fix actionable
   findings and recheck. Document research, measured comparisons, visual evidence and remaining limitations.

Completion requires implemented shared formatting, verified provider compatibility, actual model comparisons and
both visual surfaces. A green unit suite alone is insufficient. No Git push, release retag, runtime model migration
or training is part of this task.

## Sources and evidence

See [the primary-source research](../../research/2026-10-26-consistent-stem-output.md),
[the existing format inventory](../../STEM_OUTPUT_FORMATTING.md) and the character catalogue.
Current before-change evidence is in `/tmp/stem-format-current/`; accepted durable evidence will accompany the
comparison report. The Sonnet native-schema probe stores event metadata and its visible final document only.
