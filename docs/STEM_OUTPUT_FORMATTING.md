# STEM output formatting: inventory and proposed standard

Status: implemented after user approval on 25 October 2026. Verification is recorded in the implementation plan.
The inventory describes the renderer before this implementation.

## Renderer inventory before this change

The terminal uses Rich Markdown inside Textual. Obsidian reads the Markdown written to the vault and renders its
own MathJax equations. They receive the same underlying card text, but the terminal converts maths to Unicode first.
There is no separate Obsidian renderer in this repository.

There is no finite list of every character either application can display: ordinary Unicode passes through, and
glyph coverage depends on the font. The companion [character catalogue](STEM_OUTPUT_CHARACTER_CATALOGUE.json) records the installed
converter's complete command names, symbol maps, alphabet maps, script maps and accent maps. Registered commands
are capabilities to investigate, not proof that every TeX combination is supported correctly.

Installed versions: Textual 8.2.8, Rich 15.0.0, flatlatex 0.15, markdown-it-py 4.2.0, SymPy 1.14.0.

| Content | Terminal today | Obsidian reading view / Live Preview |
| --- | --- | --- |
| Paragraphs and explicit breaks | Supported; some single newlines are intentionally joined | Markdown paragraphs and hard breaks |
| Bold, italic, strikeout | Supported by Rich Markdown | Supported by Markdown |
| Bullets and numbered steps | Supported, including nesting | Supported, including nesting |
| Headings, quotes, rules, tables | Supported; wide tables wrap poorly in small windows | Supported; more flexible page layout |
| Links and images | Link labels; transcript hyperlinks disabled; images are not inline diagrams | Clickable links and rendered images |
| Code | Inline, fenced and indented Markdown code; current maths preprocessing can incorrectly alter code | Literal inline/fenced code |
| Maths delimiters | Converts `$...$`, `$$...$$`, `\(...\)`, `\[...\]` to text | Documented `$...$` and `$$...$$` MathJax; source mode intentionally shows source |
| Greek letters | α β γ δ ε θ λ μ π ρ σ φ ω Γ Δ Θ Λ Π Σ Φ Ω, plus variants | Typeset Greek in MathJax or ordinary Unicode |
| Arithmetic and relations | + − ± ∓ × ÷ · = ≠ ≈ ≡ ∝ < > ≤ ≥ | Typeset operators and relations |
| Sets and logic | ∈ ∉ ⊂ ⊆ ∪ ∩ ∅ ∀ ∃ ∧ ∨ ¬ ⇒ ⇔ and related mapped symbols | Typeset sets and logic |
| Geometry and arrows | ° ∠ △ ⟂ ∥ → ← ⟷ ⇒ ⇐ ⇔, brackets and labelled arrows | Typeset notation and annotations |
| Numeric scripts | ₀₁₂₃₄₅₆₇₈₉₊₋₌₍₎ and ⁰¹²³⁴⁵⁶⁷⁸⁹⁺⁻⁼⁽⁾; superscript lone ⁿ and ⁱ | Arbitrary typeset subscript/superscript groups |
| Letter scripts | Deliberately converted to baseline `_k`, `_(n+1)`, `^a`, `^(−kt)` under current common-font policy | Arbitrary typeset letter scripts |
| Fractions | 17 vulgar fractions such as ½ and ⅔; numeric ²⁄₇; grouped linear algebraic fractions | Stacked fractions and nested fractions |
| Roots | √ ∛ ∜; indexed roots; compound radicands grouped | Typeset radicals with overbars and indices |
| Calculus | ∫ ∮ ∑ ∏, limits, derivatives, primes, trig/log functions; complex bounds remain linear | Typeset bounds, fractions, aligned derivations |
| Matrices and cases | Rows flattened with semicolons; columns separated by spaces | Two-dimensional matrices and cases |
| Accents and vectors | Hats, bars, dots, tildes, combining arrows, bold 𝐅; →AB for multi-letter vectors | Typeset accents and vectors |
| Chemistry | H₂O, Fe³⁺, ¹⁴₆C, hydrates, bonds, ⇌, reaction conditions, standard-state ⦵ | MathJax and supported chemistry extensions; ordinary Unicode also works |
| Units | m s⁻², mol dm⁻³, kJ mol⁻¹, μ, Ω, Å, °, ‰, % | Upright typeset units and ordinary symbols |
| Math alphabets | Bold, italic, blackboard, script, fraktur, monospace maps exist; inconsistent aliases today | Semantic mathematical font styles |
| Diagrams and Obsidian extensions | No MathJax/HTML/Mermaid engine in transcript cards | Callouts, embeds and Mermaid are supported Obsidian features |

The dependency supplies 322 symbol entries, six alphabet maps, 14 combining-accent entries and 17 known fractions.
The customised converter registers 407 command names, in addition to preprocessing for chemistry, matrices and
derivative macros. A command's registration does not guarantee safe arbitrary nesting or every environment.

## Fonts and scripts

The tutor's configured terminal profile uses bundled JuliaMono. Its font contains every one of the dependency's
110 mathematical-italic mappings and every character in its six alphabet maps. It also contains the letter scripts
that the current renderer rejects. Menlo lacks many of those script letters and mathematical alphabets; SF Mono
lacks subscripts. This explains why requesting subscripts from the AI alone cannot solve the inconsistency.

Even JuliaMono cannot add arbitrary missing Unicode characters. Unicode has selected script letters, not complete
script alphabets or arbitrary two-dimensional expressions. The proposed standard uses real script characters only
when the whole group is supported, with an explicit readable fallback for everything else.

## Reproduced problems

These cases were rendered locally through the existing cards, without asking any AI:

| Input | Current terminal result |
| --- | --- |
| `$x_1+x_i+x_n+E_k$` | `x₁ + x_i + x_n + E_k` |
| `$\frac{dy}{dx}=3x^2$` | `dy/dx = 3x²`, with upright variables |
| `$\mathit{x}$` versus `$\it{x}$` | `x` versus `𝑥` |
| `$e^{-kt}$` | `e^(−kt)` |
| `$\sum_{i=1}^{n}x_i$` | `∑_(i=1)^n x_i` |
| `$a*b*c$` | `abc`: Markdown consumes the multiplication asterisks |
| Code containing `x_1^2` | Powers are converted inside code |
| Unfinished `$x_1^2` | A dollar delimiter is displayed until the expression closes |
| `$ x^2 $` | Dollar delimiters remain visible |
| An `aligned` environment | Raw command fragments appear |
| `$\iint_D f\,dx\,dy$` | `∬_Df dx dy`: separation is lost |
| `$\bot$` | `⊤`: incorrect inherited symbol mapping |

Existing maths tests passed: 303 cases. These gaps need new regression coverage; the existing tests do not prove
the reported formatting is already correct.

## Shared writing standard for every provider

The implementation shares this visual brief across providers and enforces the mechanical rules after generation.

- Use one shared British-English visual-writing brief for local, Claude and ChatGPT tutor responses.
- Put the key idea first. Use one topic per paragraph, normally one or two short sentences.
- Use numbered steps for a calculation or derivation. Use bullets for independent points or comparisons.
- Put one blank line between logical blocks and between substantial steps. Keep formulas near the step they explain.
- Use occasional short bold labels such as **Method**, **Check** and **Next step** only when useful. Do not force a
  three-section template onto a one-sentence hint or a marking verdict.
- Keep the existing brevity and open-question answer protection. Do not add a final answer while a question is open.
- Keep marking, re-marking, teaching cards and summaries in their existing application-owned structures.
- Reserve tables for comparisons that remain readable at narrow terminal widths. Do not invent diagrams from text.

| Kind of output | Structure |
| --- | --- |
| Concept or definition | Key idea, brief explanation, one helpful example if needed |
| Worked method | Key idea, numbered steps with formulas on their own lines, brief check |
| Hint for an open question | One useful nudge and, if useful, one guiding question; no answer |
| Comparison | Short introduction and parallel bullets; small table only when it helps |
| Marking or re-marking | Existing verdict and mark-point layout, concise reason and next correction |
| Teaching card | Existing motivate / establish / connect / note / self-explain fields |
| Profile summary | Existing revision-focused bullets and uncertainty wording |
| Code or literal notation | Code blocks or inline code, preserved exactly |

The structure is shared; different models can still vary in wording and mathematical correctness. A prompt cannot
make them literally indistinguishable or prove a zero-percent formatting error rate.

## Mathematical style

- Store well-formed canonical Markdown and LaTeX for Obsidian. Translate recognised expressions for the terminal.
- Render mathematical variables in italic: 𝑥, 𝑦, 𝑣, 𝑡. Keep numbers, units, function names, chemical elements,
  descriptive labels and the differential d upright. A derivative becomes d𝑦/d𝑥, not italicised ordinary prose.
- Preserve bold vectors and other meaningful mathematical alphabets instead of flattening them to ordinary letters.
- Prefer true scripts when the complete group exists in the font: 𝑥², 𝑥ᵢ, 𝑥ₙ, H₂O, 10⁻³.
- For unsupported terminal indices use an explicit grouped label such as `𝑥[index: 𝑁]`; for unsupported powers use
  `(𝑥) to the power (𝑎 + 𝑏)`. This is a readable fallback, not a claim of full terminal typesetting. A complete
  convertible group such as `n+1` may use `ₙ₊₁`; never mix baseline letters into half-converted script groups.
- Show integral and sum bounds consistently, for example `∫[0 to π] sin 𝑥 d𝑥` and `∑[𝑖 = 1 to 𝑛] 𝑥ᵢ`, when
  compact typeset bounds cannot be represented. Preserve grouping in fractions and roots.
- Keep `%` for percentages, currency signs for money, and literal code operators in code. The problem is leaked
  formatting syntax, not the existence of these characters. Never strip meaningful symbols to make a test pass.
- Valid LaTeX unsupported only by the terminal stays mathematical LaTeX in Obsidian; apply its fallback only in the
  terminal adapter. Malformed or ambiguous mathematics must never be silently changed or discarded. Preserve its exact source in
  an explicitly labelled literal fallback. Raw syntax may therefore appear in that exceptional fallback or when
  the student asks to see source; it must not masquerade as a successfully formatted equation.

## Implementation approach and alternatives

Recommended: one provider-neutral visual contract and parser, followed by separate display adapters. This preserves
Obsidian's richer equations and gives the terminal a consistent, font-tested representation.

Prompt-only formatting is smaller but cannot enforce balanced delimiters, protect code or repair renderer defects.
Unicode-only storage would make simple equations look similar but would discard arbitrary scripts, matrices and
MathJax structure. Replacing all AI replies with a new JSON block protocol would make some layouts easier to enforce
but would substantially change streaming, speech and provider interfaces. Those alternatives are not recommended.

Implementation boundaries:

1. Use the existing Markdown parser to protect code, links and other literal spans. Add a small shared visual-text
   module for recognised math spans, safe delimiter canonicalisation, layout normalisation and validation.
2. Apply the shared writing brief to human-facing tutor work across providers. Keep model selection, thinking,
   transport, preload gates, timeouts, usage and conversation ownership unchanged.
3. Normalise completed visual text before it diverges into terminal rendering, Obsidian mirroring or cached prose.
   Use a field whitelist for structured replies. Never recursively rewrite all JSON strings.
4. Whitelist marking `feedback` and `points[].why`, re-mark `why`, teaching-card prose fields and profile `summary`.
   Preserve copied `point` identities. Challenge-generated `stem`, `solution`, wrong-answer explanations and human
   conceptual explanations need a separate audited whitelist. Preserve machine fields, numeric values, IDs, options,
   `expr`, `unit`, exact answers, solver/audit work, image transcription, speech and student text.
5. During streaming, show complete safe prose immediately. Buffer incomplete math delimiters/commands, including
   delimiters split across chunks, while keeping the existing progress indicator visible. At completion, validate
   and either render the expression or use the explicit literal fallback. Inline math cannot consume a paragraph
   break; a pending span is capped at 2,048 characters. At that boundary, emit a labelled exact-source fallback and
   resume normal text rather than hiding the rest of the reply. A dollar followed by a price is currency unless
   the same span contains explicit mathematical syntax. Protect escaped dollars and code. No AI repair request is required.
6. Repair the converter's demonstrated semantic and Markdown-collision defects. Extend AI visual rendering for
   JuliaMono's verified math glyphs. Preserve the established common-font renderer for authored lesson content and
   literal learner answers unless a targeted defect fix is required.
7. Do not rewrite historical notes, generated question banks or existing cached content in bulk. Normalise visual
   fields when cached AI prose is consumed, preserving machine data and avoiding extra model requests.

This is a bounded formatting change, not a new rendering engine. Remaining macro details and parser organisation
are implementation choices, provided they preserve meaning and pass the acceptance checks below.

The implementation is in `output_format.py`, `stem_math.py` and `output_fields.py`. AI cards use their own Markdown
adapter to preserve explicit line breaks and visible list-item gaps. Authored content retains its established
common-font converter. Cached AI cards and profile summaries use an optional engine callback that defaults to
identity outside the terminal app. No additional AI repair calls are made.

## Acceptance checks

- All three provider routes use the same style brief and display normalisation for the same response kind.
- Maths samples cover variables, differential d, units, powers, scripts, fractions, roots, calculus, matrices, chemistry,
  vectors, Greek, percentages and currency, including complex and unsupported expressions.
- A named regression corpus requires successful rendering of every common expression category and reproduced
  defect that can be represented faithfully; unsupported macros and malformed inputs have separate fallback cases.
  The corpus must have zero unlabelled syntax leakage. Test two prices, escaped dollars, paragraph boundaries,
  the pending-span size limit and cancellation during buffering.
- Code, URLs, student text, machine fields and speech are unchanged. No multiplication, sign, bound, index, charge,
  denominator or grouping is lost in display conversion.
- Streaming tests split every supported delimiter and speech marker at each boundary; incomplete maths never leaks
  as ordinary formatted output. Failed or cancelled streams retain clear progress/error behaviour.
- The same final canonical visual text reaches terminal cards, Now.md, chat/lesson logs and relevant prose caches.
- Render samples at 80×24, 100×30 and 140×46 in Night, Day and Classic. Check overflow, gaps and font coverage.
- Retain cloud routing and local preload regressions; run the complete documented test suite before claiming done.
- Independent reviews check both repository standards and this specification. No model downloads or additional
  runtime service is planned; no production AI requests are needed to test display conversion.

## Research and source map

- [Obsidian advanced formatting](https://help.obsidian.md/Editing+and+formatting/Advanced+formatting+syntax): MathJax,
  tables and diagrams. Source mode remains source text; this proposal concerns reading view and Live Preview.
- [Rich Markdown implementation](https://rich.readthedocs.io/en/stable/_modules/rich/markdown.html) and
  [Textual Markdown](https://textual.textualize.io/widgets/markdown/): Markdown support is not a maths layout engine.
- [MathJax delimiters](https://docs.mathjax.org/en/latest/input/tex/delimiters.html): dollar/currency ambiguity.
- [Unicode mathematics](https://www.unicode.org/reports/tr25/) and
  [Unicode scripts](https://www.unicode.org/versions/Unicode16.0.0/core-spec/chapter-22/): mathematical alphabets and
  incomplete script character coverage. A glyph catalogue cannot replace mathematical structure.
- [MathML identifiers](https://www.w3.org/TR/MathML3/chapter3.html#presm.mi): semantic distinction between italic
  identifiers and upright multi-letter names; this guides the proposal rather than a global italic substitution.
- [W3C succinct text guidance](https://www.w3.org/WAI/WCAG2/supplemental/patterns/o3p05-succinct-text/): one topic per
  paragraph, short chunks, descriptive labels and lists. This is accessibility guidance, not a tutor-specific trial.
- [MathJax accessibility](https://docs.mathjax.org/en/v3.2/basic/accessibility.html): structured maths can support
  assistive technology. Terminal Unicode alone does not confer equivalent accessibility; preserve separate speech.

Repository evidence: `app/tutor_app/{cards,texmath,ai,prompts,tutor_ai,screens,challenge_screen}.py`,
`plugin/stem-tutor/skills/tutor/scripts/tutorlib/{views,session,challenge_gen,speech}.py`,
`tests/app/{test_texmath,test_glyphs,test_obsidian_matches_terminal,test_tts}.py`.
