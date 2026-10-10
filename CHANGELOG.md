# Changelog

## 2.1.1 — 2026-10-10

Asked by the learner.

- **The foundry keeps Codex's five-hour limit in mind.** It already scored any window Codex reports; now it reads every
  limit Codex names (`router.codex_windows`) and treats "use not allowed" as used up until the nearest reset. This
  account's Codex plan reports a week only, so there is no five-hour figure to read: `foundry usage` says so. A Codex
  job that runs into a limit now pauses Codex until the window reopens (from Codex's own figures, or the time in its
  message, `router.reset_from_message`) instead of ten minutes.
- `foundry usage` and the guide show the version 2.1.1.

## 2.1.0 — 2026-10-09

Asked by the learner.

- **Challenge mode** (home menu: "Challenge: hard calculation questions"; `app/tutor_app/challenge_screen.py`,
  `tutorlib/challenge.py`, `tutorlib/challenge_gen.py`). Questions are written for fun and mastery and never touch the
  mastery model, reviews, reports or the Almanac: answers are saved in `.tutor/challenge/<set>.json` and logged as
  `challenge` events, which everything else ignores.
- **Ten levels**, from Warm-up to Impossible (7 "rare in exams", 8 "beyond the exam", 10 "far beyond A-level but
  still solvable"). Pick the easiest and hardest level and how the set climbs: steady, fast-then-slow (quick jump to
  hard, slow creep to extreme), slow-then-fast, hardest-first, wave, random or flat.
- **Multiple choice and typed answers**, calculation only (no "explain" or "design an experiment"). Typed questions
  have no options, so no hints; the real grader marks value, unit and significant figures. Re-mark (AI) is offered
  for a typed answer marked wrong.
- **Set up by words or menu**: type "12 questions on 9702-5.1, start easy, jump to hard fast, end extreme, opus", or
  step through Topics, How many, Types, Easiest, Hardest, Ramp and Model. A live preview shows the level of every
  question. The last settings are remembered. The whole set is written first, then shown one question at a time with
  a check after each; an unfinished set can be resumed.
- **Solvable by construction**: the writer is given only the syllabus points of the chosen chapters, the earlier
  chapters of the same spec and their prerequisites, and must build each question on required points from the chosen
  chapters. Then an independent model solves it blind and must match the key, and an examiner call checks that every
  idea used is in scope and rates the difficulty; a question that fails is retried with the reason, then written one
  level easier, then left out. At levels 8 and up a solver that misses is accepted only when a second careful blind
  solve by the independent model reaches the key. A question rated easier than asked is shown at the level it really
  is ("level 9 (asked for 10)").
- **When Opus declines** (its safeguards sometimes flag ordinary physics), that one call goes to Sonnet instead and
  the screen says so; it is never reworded to get around the filter. Calls are capped per question and a run stops
  after repeated failures; Esc cancels cleanly.
- `Claude.one_shot` takes `timeout` and `system`; hard questions can take several minutes to write.
- Not covered: temperature answers in °C (the unit parser does not read `°C`).

## 2.0.0 — 2026-10-08

A new look for the terminal window, and a long bug-and-comfort pass hunted by parallel agents (read-only hunters,
test-first fixers, independent reviews). 1.6.1 → 2.0.0 is one release because the new look touches every screen.

- **A cleaner window.** Three looks, chosen in Settings (F2): **Night** (calm dark, one blue accent, quiet grey
  frames), **Day** (warm paper, dark ink) and **Classic** (the colours of 1.6.1, byte for byte; it is what you get
  until you opt in). Every colour comes from one palette of roles (`look.py`); Night and Day pass contrast checks
  (text 7:1, colours 4.5:1). Night and Day use 24-bit colour on macOS 26 and later.
- **`tutor look`** sets up macOS Terminal once: it backs up Terminal's settings first (and stops if it cannot),
  installs the bundled **JuliaMono** (OFL; one fixed-width font that also draws the maths), adds "STEM Tutor Night"
  and "STEM Tutor Day" profiles built from the same palette (never touching your own profiles), switches to Night
  and prints a test page. The tutor's own tab follows the look and is put back as it was on exit. `tutor look
  --undo` goes back and lists how to remove the rest. `tutor doctor` checks the font, the profiles and the colour
  depth, and now exits 1 when something is wrong.
- **Symbols:** colour emoji, which can draw two cells wide and overlap, are one-cell shapes (✶ ↻ ⧗ ▦ △ ▸ ◷ ✓ ✗);
  a test checks every character on every screen is in the font, one cell wide and not an emoji.
- **Maths reads as printed:** `s = ut + ½at²`, `√(b² − 4ac)`, a true minus, `ΔH⦵ = −286 kJ mol⁻¹`,
  `Cu²⁺ + 2e⁻ → Cu`, `dy/dx`, `𝐅 = m𝐚`, `∫₀¹ x² dx`, `A —Δ→ B`, `⟨c²⟩`, accents over several letters, `Kc`,
  `|−3| = 3`. Fixed: `Fe3+` shown as `Fe₃+`, `Na+(g)` losing its charge, `⇌` shown as "leftharpoons", raw `$…$` in
  card titles and on Summary, Progress and Insights, unbraced limits, nested bars, and dozens more commands.
- **Marking:** `× 1000` and `x 105` are no longer read as a power of ten (`3 x 100` was accepted for 3); `J/(mol K)`
  is `J mol⁻¹ K⁻¹`; `mm` is never m·m (3.0 mm for 3.0 m² was full marks); the ohm sign, `⋅`, `º`, other dashes and
  `− 3.2` read as meant; `ΔH = −57 kJ` and `θ = 30°` read like `x = 24`; `sin2x` is sin(2x); a decimal comma
  (`3 = 1,5 m`) keeps the question open; a unit ending in a digit never swallows the next answer; blind MCQ answers
  like "(B)" read by their letter. Checked over ~1,000,000 numeric cases: every published answer is still right for
  its own key, and every changed decision moved toward correct or toward "unreadable" (the question stays open).
- **Screens:** a self-marking point is shown in full under the tick list; long questions open at their top and
  alt+up/alt+down scroll the session; the summary scrolls and keeps its way out; focused buttons look right in every
  look; tick boxes show a ✓ and ctrl+s confirms a list; Settings labels the model, shows the minutes as a box and
  says Save applies and Esc cancels; the chat asks before dropping a typed question; the confidence step shows one
  prompt; a narrow Home shows streak, due and exam countdown in one line; the Progress forecast is labelled by day;
  a checked blurt shows what you wrote; hint keys after an answer say the question is marked.
- **Engine:** an answer recovered after a stop now does to the session what marking it did (a missed idea became a
  gap again); events from an iCloud conflict copy are read in time order and a clean start no longer refolds every
  time; an idea missing from the packs no longer crashes brief, today or session start; a torn learner, session,
  config or AI-summary file no longer blocks the tutor; a paper marked in part is not full marks and unreadable marks
  are refused; a question left open overnight no longer adds hours to a week's time; judge scores are clamped; a
  reason for a miss is refused for a re-marked answer; a test on many topics no longer fails on a too-long file name;
  session notes never overwrite.
- **AI client:** cancelling an AI call cancels the screen's work; a `claude` that cannot start, an unwritable usage
  file, an oversized reply line and an unwritable card cache are errors, not crashes; Claude reset times ending in Z
  read on older Pythons.
- **Publishing and tools:** a crashed publish can no longer push the real rollback versions out; the engine, CURRENT
  and the launcher are swapped in atomically; publishing follows `STEM_TUTOR_VAULT`; Finder `.DS_` files are not
  copied; the launcher quotes its path; `bin/tutor` repairs a failed first install and names a too-old Python;
  `validate_pack` reports malformed packs and five silent faults instead of crashing; the foundry keeps its usage
  readings, locks `HOLD.json`, signs only after the checker, and shows what the note linter found; `sandbox.sh`
  judges the real path before deleting; `package.sh` makes `dist/`.
- **Content:** `\times` saved as a tab plus "imes", PDF-extraction debris (bracket pieces, lost fractions, degree
  signs, soft hyphens) repaired in the packs and their sources from the original papers, and five 9701 questions
  whose options were shifted by one (the key pointed at the wrong text; one showed +61 where the answer is −61)
  rebuilt. Flattened maths in some examiner comments remains (a note for a later pass).
- **Published packs repaired (audit of all 24):** options shuffled so the key letter is no longer predictable, numeric
  tolerances and hints that gave the answer away, questions whose options are figures no longer show blank options,
  rubric marks that did not add up, and the broken maths text in a few packs. Fixes are in the generators and in the
  published JSON; `tests/test_packs_content.py` pins each audited fault.
- **Crashes and layout:** a double ⏎ on a blurt no longer submits twice; a doubled pick on a session panel is
  ignored; Tab no longer strands focus on the log; a damaged content file is named in one line (and `tutor doctor`
  has a "Content files" row) instead of stopping the tutor; the footer ends on a whole key at 60 columns; headings
  3 are no louder than 2 in Night and Day; a focused one-line button is an even chip (Classic too).
- **macOS Terminal hardening:** the profile lookup uses `settings sets whose name is`, the script times out at 20 s,
  and a refused Automation permission says so once with the fix; profiles are written as version 2.07.
- **Known:** checked here only through a Textual screenshot and pilot tests, not in the learner's Terminal; whether
  Option+Up reaches the app as alt+up depends on Terminal's "Use Option as Meta key"; 9702-1.4-x016 repeats
  x002 (CAIE reused the question) and is kept.

## 1.6.1 — 2026-10-07

A bug and comfort pass, hunted and fixed without the Codex bug watch.

- **Marking:** `2,880kJ` (comma then unit) and `x = 24` / `v = 3.0 m s^-1` (a leading label) are read; an equation
  `v² = u² + 2as` is marked on its right side (wrong ones stay wrong); `sin^2(x)`, `sinx` read; `30 degrees`,
  `0.5 M` (for a concentration) and `g dm^{-3}` are right units. A re-marked answer no longer keeps its slip damping.
  A duplicate event (an iCloud conflict copy of the log) is counted once.
- **Maths display:** `\mathrm K`, nuclides (`¹⁴₆C`), `Cu²⁺`, `kJ mol⁻¹`, integrals and sums, `\binom`, matrices;
  units everywhere (options, "Exam point"); `3*x**2` shown as typed; line breaks in data tables kept.
- **Terminal:** Settings fits and scrolls; ctrl+q goes back a screen (quits only from Home) and asks before losing
  typed text; Home fits 60–80 columns and 24 rows; footer shows Menu and Help; compact buttons in short windows;
  Esc says how to leave; the summary cannot be closed by a held ⏎; picker and hint wording fixed; Insights shows no
  Obsidian markers; the menu keeps your place.
- **Almanac sync:** your own paper stage is kept; Reset does not bring tutor ticks back; ticks the tutor added are no
  longer read as ones you claimed (so Today.md and a later re-mark are right).
- **Notes and tools:** right answers in Mistakes.md use maths, plurals fixed, far-off exams collapsed, plan lines
  capped; review lessons are titled "Review"; links to unbuilt chapters stay plain text and wrong-apostrophe links
  are repaired; the iPad import no longer duplicates files; `tutor doctor` counts real events and flags a damaged
  log or empty content; a launcher for another vault opens that vault.

## 1.6.0 — 2026-10-04

Asked by the learner.

- **Every box you type in wraps and grows.** Number, formula and short answers (`ValuePanel`), the next-step guess
  in a worked example and the note under a multiple-choice question now use the same box as written answers
  (`Composer`): ⏎ sends, ctrl+j starts a new line. Only the minutes field in Settings is still one line.
- **The same quantity is the same answer.** A prefix always converted (1.5 kW for 1500 W: checked on all 60 numeric
  questions that have a unit, 318 conversions, none marked wrong). What was marked "wrong unit" by mistake: words
  after the unit (`200 W of input`, in the learner's log), a unit typed without its capitals (`kw`, `KW`, `pa`) and
  one spelled out (`kilowatts`, `joules per second`). All are now read as the unit they name
  (`units.unit_readings`); a word that could be part of the unit (`W s`, `W per second`) is never dropped. A unit of
  the wrong kind still loses the mark, and the feedback names it: "wrong unit: 'kN' is not a unit of this quantity
  (the answer is in W)".
- **Re-mark (AI).** After an answer you gave is marked wrong, or loses a mark, a button (and option 6 of "Why did
  you miss it?") sends the question, the mark scheme answer and your answer to the AI examiner (Sonnet, whatever the
  model setting). If it finds the answer right, a `regrade` event overrides the first mark wherever the log is read
  (`Vault.events`), so the record, the reviews, the journal and the Almanac follow it, and a reason already given
  for missing it is dropped. In the session the answer is recorded again as right from the state before the wrong
  mark (`Tutor.regrade`, `Tutor._mark`): no fix step, relearning question or gap comes of it. One re-mark an answer;
  not offered for "I don't know", nor for written answers the AI has just marked.
- **Feedback buttons wrap** onto a second row when the window is too narrow for them, and return to one row when it
  widens (`ContinuePanel.rows`).

## 1.5.1 — 2026-10-04

Asked by the learner.

- **The session bar wraps to a second line** when the window is too narrow for it (`SessionScreen.bar_text`): the
  running figures (time, score, AI use) move whole to line two; a line still too long ends in an ellipsis; never
  more than two lines.
- **Only the week's limit is shown** beside the token count: the five-hour figure was nearly always unknown.

## 1.5.0 — 2026-10-04

Asked by the learner.

- **A question folds the session log.** The Now page shows an open question alone, but the terminal kept everything
  said before it, so a check on an explanation could be answered by reading the explanation. `SessionScreen.fold`
  hides the earlier entries when a question or an own-words prompt opens; `ctrl+l` shows them again once it is
  answered.
- **`panels.Composer`**: a text box that wraps and grows (3 to 10 lines), `⏎` sends, `ctrl+j` starts a new line.
  Used for written and own-words answers, the ask box and the menu's chat.
- **The AI is told the session.** `prompts.context` now carries the step on screen (only what has been shown), each
  open question, and the last three marked questions with stem, answer given, verdict and key
  (`session["recent"]`, kept by the engine); with no session, the last answers in the log. Before, a marked
  question dropped out as soon as the session moved on, and the menu's chat was told nothing.
- **Limits beside the token count** (session bar, home screen): `ai.Claude` keeps the window named in each
  `rate_limit_event` of its own stream (exact); `mac.claude_limits` reads Claude Code's own note for the rest
  (marked ~, can lag); the five-hour figure is "?" when neither has it.

## 1.4.0 — 2026-10-03

Asked by the learner: tick Almanac objectives for me when I have done them; set the Green/Amber/Red of every syllabus
topic from my level, since I cannot rate myself honestly; fill in everything else the Almanac offers and keep it up
to date as I study; and remove the cap on AI replies.

- **The tutor writes `A-Levels.tutor.js` beside the planner** (`report.almanac_push`: at every return to the menu and
  after every session), and the planner page merges it when it opens and every half minute (`build/almanac_link.py`
  puts the block from `build/almanac_link.js` into the page, keeping a copy of the page in `.backup/`). It carries:
  ticks the learner has earned (`policy.earned`), a colour for all 74 syllabus topics (`policy.rag`), mark-bank
  scores, the days studied, mistakes by the Almanac's six families, the retrospective for this week and the last,
  and the paper stage. The page keeps what the learner ticks, types or writes; only the colours are always the
  tutor's. This replaces the hand-made `almanac-import-<date>.json`.
- **What earns a tick:** a NEW objective, each idea answered right without help once; a review, check or gate with
  ideas of its own or naming weeks or a phase, those ideas secure (or the share its "done when" asks for). 168 of
  the 465 objectives; practicals, paper sittings and routines stay the learner's to tick. Earned objectives count as
  done in the tutor's own plan too (`Tutor.ticks`).
- **From the Almanac:** exam dates in its export replace the plan's (`almanac.exam_dates`); within a week, objectives
  are taught in the planner's priority order.
- **No cap on AI replies:** `daily_cap` is gone from the settings and from `ai.Claude`; replies are still counted.

## 1.3.1 — 2026-10-02

Asked by the learner: why does `foundry usage` not show Claude's own five-hour window?

- **It was not known, and 1.3.0 wrongly took that for "no five-hour cap".** Claude Code's cache had been fetched as a
  new five-hour window began (0%, not active), and a headless run is told about one limit only, the one nearest its
  end (the weekly one). The Claude app's usage card showed the window at 74%.
- `foundry usage` now says "not reported by Claude" for that window when it does not know it.
- `foundry reading claude five_hour <percent> [reset time]` passes the figure on; the manager does so from the app's
  usage tool before the first `step` and about every half hour. The router then counts it like any other window.
- **A job goes only where there is room for it.** The router now counts the job's own nominal cost before calling an
  allowance open: with 18% of Claude's five-hour window left it no longer starts an Opus draft (about 21% of one).
- A Claude job refused by a limit was already recorded as a limit, not a failure of its tier, and closes Claude until
  the reset time the refusal names; that path is now tested, for the five-hour window too.

## 1.3.0 — 2026-10-02

Asked by the learner: the foundry should use the Claude and Codex usage limits together, split so that both run out
at the same time and adapting as it goes; any model may do any job; each job gets the least model that gives
consistent output. Design: `docs/superpowers/specs/2026-10-02-foundry-two-allowances-design.md`.

- **One launcher for every role, on either allowance.** `foundry run <role> <chapter>` starts a headless worker:
  `codex exec`, or `claude -p` with plugins, skills, hooks and MCP servers left out. Solvers and the checker are no
  longer the manager's subagents, so they finish without it.
- **`foundry/router.py` decides where each job goes**, afresh before every job: the allowance with more of its
  longest window left per hour until it resets. Codex is read from its app server; Claude from Claude Code's cache,
  from what each worker is told, and from a one-word run when both are over ten minutes old.
- **The family that drafts a chapter never blind-solves or tiebreaks it.**
- **Ladders of models per role and allowance** (`foundry/config.json`): a job starts on the lowest rung that has not
  failed the role twice running; a chapter's retry goes one up; a usage limit closes the allowance and is not held
  against the tier; a solver is judged by how often the tiebreak overturns it.
- **`foundry step`** does everything that needs no judgement in one pass; **`foundry usage`** shows both allowances.
- **First real run** (9701-2.2 drafted by `gpt-6-sol` low, 9701-2.4 by Opus at low effort; both signed): each first
  rung passed its gates except the Codex solver, where `gpt-6-luna` low slipped on 34 of 92 questions, so its ladder
  now starts at medium. The run also showed that asking again for a big chapter's remaining shards discarded the
  finished ones; fixed.

## 1.2.8 — 2026-10-02

Asked by the learner: Today's plan showed only the calendar week however far ahead they were, and objectives ticked
in the Almanac were not counted, so the plan kept teaching them.

- **Ticks reach the tutor.** The Almanac keeps ticks in the browser (`S.done`, keyed `week-subjectN`); they leave it
  only through its Export button. `build/plan.py` now gives every objective that id, `tutorlib/almanac.py` reads the
  newest `almanac-progress-*.json` in the vault's `Almanac/` folder, and the app moves exports from `~/Downloads`
  into that folder when it opens and at each return to the menu (`mac.import_almanac_exports`).
- **A ticked objective is checked, not taught.** Its ideas (`policy.claimed`) never enter `new_kcs`; autopilot adds a
  `sweep` block flagged `claimed` over those never answered here. A miss becomes a gap and is taught first next time.
  A tick covers the section the objective refers to, not ideas attached from unscheduled sections (`outside`).
- **Ahead of the calendar.** `new_kcs` walks every week in order instead of stopping at the calendar week plus one,
  and `policy.focus_week` moves the home panel, the menu label and `Today.md` to the next week with something left.
- **The foundry builds what is in front of the learner first:** `coverage` puts chapters whose ideas are all ticked
  last.

## 1.2.7 — 2026-10-02

- **A resize clears what Terminal kept beyond the new edge.** The learner's original layout report: Terminal keeps
  the columns beyond a narrowed window's right edge and shows them in the strip beside its scrollbar (old borders,
  scrollbar pieces, letters). `TutorApp.on_resize` clears the display in the screen's colour (`ED 2`) and repaints.
  Found by reading pixels in the learner's screenshot, reproduced and checked in Terminal itself with a scratch copy
  of the app. (1.2.5 fixed real layout faults, but not this.)
- **The launcher opens in the "Study" Terminal profile** when there is one (`publish.launcher_script`: an AppleScript
  moves the launcher's own window, found by its tty). The learner's profile shows only the title the app sends and
  uses the app's colours.

## 1.2.6 — 2026-10-02

- **The terminal window is named.** The app sends its title (`OSC 0`) before it takes the screen and hands it back
  when it ends; Textual sends none, so Terminal showed only the folder, launcher, process and window size.

## 1.2.5 — 2026-10-01

Layout, reported by the learner (window resized to half the screen).

- **Button ids no longer borrow layout styles.** `Button#ask` matched the Ask pop-up's rule (`#ask`: 90 columns wide,
  round orange border) and `Button#home` the home row's (`#home`: height 1fr), so "Ask the tutor" ran off the right
  edge of a narrow window and "Back to menu" was as tall as the screen. The rules are now `Vertical#ask` and
  `Horizontal#home`.
- **One grid for the log and the answer area.** Textual puts a scrollbar inside the padding, so the log's sat one
  column in from the edge and cards ended a column before the answer boxes. Boxes now span columns 1 to width-3 in
  both; the scrollbar is on the last column, reserved (`scrollbar-gutter: stable`), its track the background colour.
- **The home screen's side box scrolls.** With 22 chapters it ran off the bottom of the window (now a
  `VerticalScroll`: mouse wheel, or Tab and the arrow keys).
- "I don't know" is no longer shown as an exam point (card, Now, lesson log).
- Checked in Textual's own renderer at 80, 100 and 140 columns and by layout tests that resize mid-session; not seen
  in the learner's Terminal itself.

## 1.2.4 — 2026-10-01

Numeric marking, asked for by the learner after "9 m s⁻²" lost a mark for not being 9.0.

- **An exact answer needs no zeros added.** A right value typed with fewer figures than `sf_ok` asks keeps the mark
  when it is exactly the true value (nothing was rounded away). CAIE's "Calculation specific guidance" credits an
  answer that equals the mark scheme's once rounded to its figures; Edexcel asks for 3 s.f. only of answers that are
  not exact. Exceptions, where the figures carry meaning (`grade._figures_count`):
  - the question fixes them: its stem says how many, or one count only is accepted (`sf`, or a one-item `sf_ok`), as
    for a reading quoted to its instrument's precision (1.50 mm on a micrometer);
  - too many figures: in the sciences an unrounded result (3 × 9.81 × 2.5 = 73.575 J) still loses the mark; in maths
    an exact value may be given in full (112.5).
  In the published chapters: 18 questions now accept their short exact answer, 7 keep the rule (4 "correct to 3
  s.f.", 2 "to 2 significant figures", the micrometer), 2 maths questions accept a long exact answer.
- **A rounded answer is the rounding itself.** "Correctly rounded at your own figures" was a window of half a unit on
  the answer's scale, so just above a power of ten it took values from the decade below as right (96 for 100.5; 0.5
  for 1.0 where one figure is accepted): 26 published questions. The value must now be a whole number of units in
  the last figure kept.
- **A rounded whole number can be written with zeros.** 2400 for 2375 was read as four figures and marked wrong (18
  published questions). A whole number ending in zeros may be the rounding at any of its figures. The AI leak guard
  reads numbers the same way.

## 1.2.3 — 2026-10-01

Bug hunt with Codex (`bugwatch/`, B-035 to B-039) and two bugs from the learner's own lesson.

- **One question at a time in the app (reported by the learner).** The engine opened questions two at a time while
  the app showed one. After the first was marked, the unseen second was still open: in a no-help check, asking the AI
  about the marked answer was refused ("answer it first"); in an assisted pair the unseen question was silently marked
  as hinted, and its time included the time spent on the first. The app now runs the engine with `one_at_a_time`: the
  rest of a batch waits in `session["queue"]` and opens (clock, Now, lesson log, help rules, AI context) only when it
  comes on screen. Same questions, same order; the chat interface is unchanged.
- **A lost mark says why.** Now and the lesson log called a right value with a mark lost "incorrect" with no reason;
  they now give the exam point. The AI's context for a marked answer carries what the learner wrote and that point.
- **B-036** `10³ J` was read as 103 J (and missed by the AI leak guard). A typed power of ten is a number; any other
  power (`5²`) is unreadable, so the question stays open.
- **B-038** An answer that reached the log but no save (the app stopped in between) left the saved state behind the
  log and the question open, to be recorded twice. The state records the newest event it holds and is rebuilt when the
  log is ahead; a question whose answer is already logged is closed on start.
- **B-039** AI help counted as a hint before the reply arrived, so a failed or withheld reply cost the credit for an
  unaided answer. It counts once a reply is shown.
- **B-037** The mistake journal and session note found only written questions (`-i01`); past-paper questions and
  extras (778 of 1,249) showed "Question: not recorded".
- **B-035** A long run of unit letters froze marking (every split was tried); such text is now refused at once.

## 1.2.2 — 2026-10-01

- **Syllabus gate.** A chapter cannot be signed unless every syllabus outcome in it has a teaching card, is covered by
  the lesson note, has its definition or derivation where the syllabus asks for one, and (CAIE) is asked with the
  syllabus's command words. Teaching cards are now part of the foundry (drafted, merged, their check questions
  blind-solved); the checker reads for outcomes that are not really taught or tested.
- **`foundry coverage`**: the whole syllabus against what is built (873 outcomes; holes in signed chapters; what to
  build next), and an audit of the outcome list against the official syllabus documents. Fixed from it: D1 listed
  three subtopics twice; 9701-2.4.1 had lost the syllabus's note on significant figures.
- **The foundry runs on Sonnet.** `/foundry` runs the manager on Sonnet at medium effort for that turn; it calls an
  Opus adjudicator (`foundry escalate`) for the decisions it must not make alone. `foundry wait`, `foundry queue`.
- Fixed: the drafting queue stalled on finished workers; a refused sign now records which gates failed.

## 1.2.1 — 2026-10-01

- **Shown answers.** A numeric model answer keeps the significant figures it states (11.0 m, 2.50, 0.0300, 4.69e5 J),
  and an exact answer is shown in full (12.25, 1200) instead of rounded to 3 s.f.; typing back what is shown always
  earns the marks.
- **AI leak guard.** While a question is open, a reply stating its answer is blocked at any precision the marking
  would accept, not only near the rounded key as shown (111 of 15,132 sampled instances got through before).

## 1.2.0 — 2026-10-01

- **What the tutor knows about you** (menu, and Profile.md): every finding the tutor has worked out, with the
  evidence, how sure it is (not enough data / early sign / likely / clear, tied to the thresholds at which the tutor
  acts) and what it changed because of it; what was recorded; adjustments in force; what it never does. Press **a**
  for a short AI summary of the findings (one reply; only the findings are sent).
- **Fix my weak spots** (menu): a session on active misconceptions, gaps and ideas answered right under half the time.
- **Exam readiness** per exam: syllabus built, started and secure; predicted recall on the day if reviews stopped now
  vs kept up.
- **Mistake journal** (`Mistakes.md`): every wrong or unknown answer with the right answer, marked when put right.
  Answer events now log the key as shown.
- **Week in review** (`Weekly/<year>-W<nn>.md`), written once when the app opens in a new week.
- The guide starts with **Everything the tutor can do**, the full feature list.

## 1.1.5 — 2026-09-30

- **Your Almanac plans your day in the app.** The terminal app could not reach the engine's Almanac-driven plan:
  the menu now starts with **Today's plan** (due reviews, then the Almanac's topics in week order, practice, an exit
  check). The home screen shows this week's Almanac objectives and which have questions yet; `Today.md` is written
  when the app opens, not only after a session, and matches your session length; the home screen says when
  `A-Levels.html` has changed since the plan was built (the plan now records the file's path and fingerprint).

## 1.1.4 — 2026-09-30

- **The app always starts.** Opened from `Start Tutor.command`, it runs under Terminal, and macOS privacy settings
  can stop Terminal reading iCloud Drive; listing the iPad inbox then crashed the app at start-up. It now starts
  anyway and says how to allow access; a file still downloading from iCloud is left for next time instead of
  stopping the import; `tutor doctor` shows whether the inbox can be read.

## 1.1.3 — 2026-09-30

- **Chapters reach you as soon as they are done.** Signing a chapter in the foundry publishes it into the vault,
  commits it and notifies you; the app picks it up at the menu ("New chapters ready: …") without a restart, and a
  running session survives the old content version being pruned.
- Foundry: progress survives a session that stops (state on disk after every step; Codex jobs finish on their own;
  Haiku jobs that were cut off are flagged as stalled and re-sent); a live `foundry watch` screen, Mac notifications,
  parallel Haiku solvers per chapter with the checker alongside, and `bin/foundry` that works from any folder.

## 1.1.2 — 2026-09-30

### Content
- Past-paper questions that Cambridge printed in two papers (the P11/P13 timezone variants, sometimes a later year)
  were in the bank twice under different ids: 23 repeats removed, none lost. `add_past.py` now skips a question
  already in the pack, files a question on two subtopics under its first one, and keeps ids stable;
  `validate_pack.py` rejects a repeated question.
- The vault's `Assets/mcq` held 2,094 old copies named "… 2.png" (from a Finder "keep both" merge, not the app) and
  a stray copy of one Subjects note; moved to the Bin (49 MB).

### Tools
- **Content foundry** (`foundry/`): chapters built by Codex workers (draft, tiebreak, fix) and Claude Haiku workers
  (blind solve, rule check), with Opus managing from a board and small packets; deterministic gates between steps.
- The doctor accepts a vault opened from a parent folder in Obsidian.
- Guide and README updated to this version.

## 1.1.1 — 2026-09-30

Bug-hunt release: a second AI (Codex) searched for bugs live while Claude fixed them (`bugwatch/`), then a Haiku
review pass checked each area once more. 34 Codex findings fixed with tests, plus 3 found while fixing and 3 from the
Haiku pass; details in `bugwatch/FIXES.md`.

### Marking
- Numbers: `exact` answers allow no error (118 is not 117); a value correctly rounded to the learner's own s.f. is right
  (16 N for 16.46 N), with the s.f. rule deciding full or half marks; "20" is read strictly as 2 s.f.; a unit or sum
  after a plain-number answer ("500 kg", "500 + 1", "2^10") is refused and the question stays open ("%" only where the
  question asks for a percentage); compact units after a slash ("kg/ms2") put every factor below the line; "ms-1" as
  the expected unit also matches "m/s", and an identical unit (°C) always matches; extreme exponents and wildly wrong
  values no longer crash grading.
- Expressions: parsed as plain maths only (they could run Python before), can't freeze grading with huge powers, are
  checked at negative values too (abs(x) is not x), read "as" and subscripts (R1, m2) as variables, accept Unicode maths
  as the app displays it (u², 2×a×s, π, √), and an unreadable one stays open instead of being marked wrong.
- Written answers are never marked right on keywords alone: every short answer is judged (AI examiner or self-mark).

### Your work is kept
- Lesson logs and Anki exports made in the same minute no longer overwrite each other; iPad imports never overwrite a
  PDF; the event log survives a crash mid-save (even mid-character) and answers containing Unicode line separators;
  re-teaching keeps every paragraph of your own words; long-answer working is saved to the lesson log; a failed AI
  marking gives the tick list back. Tests can no longer touch the real iPad inbox.

### Learner model and teaching
- Study from midnight to 5 am counts as late night; hinted answers don't clear a misconception; lost-mark answers count
  as misses in the profile and session notes (saved progress is rebuilt from the event log once, model 1.1.1).
- Repair teaching, worked examples and trap cards in Test/repair sessions show in Now, are logged, and resume after a
  restart; finished teaching experiments now pick the method; retest scores go to the idea being retested; My Notes
  refreshes for every idea answered in a session.
- AI help: replies are checked for the answer of every open question; asking the AI during a question counts as a hint,
  and no-help checks refuse it; overlapping requests respect the daily cap.
- Anki: cards from different topics no longer block each other; inequalities and arrows survive as HTML.
- Terminal maths: no raw LaTeX left (≥, ≤, ≠, …, column vectors, words inside formulas).
- Publishing keeps the two newest rollback versions after v9.

## 1.1.0 — 2026-09-30

### Learning algorithms
- FSRS now uses all four grades: wrong → Again; right only with a hint, or right but guessing/unsure → Hard; right →
  Good; certain on an idea already recalled on two earlier days → Easy.
- Exam-aware retention: each answer records a retention target that rises as the idea's exam approaches (planner dates;
  AS 2027 / A2 2028 estimates for CAIE), bounded 0.85–0.97, so rebuilds reproduce scheduling exactly.
- Reviews ordered by forgetting risk (1 − recall probability) weighted towards sooner exams, then interleaved across
  subtopics.
- Successive relearning: a missed review/practice idea is re-asked later in the same session with a different item.
- Likely slips (fast miss on an idea normally answered correctly, with no misconception) halve the ability update.
- Fatigue measured as accuracy against expectation; one break suggestion per session.
- Problem-first method now delivers a real challenge phase; the "quick" goal never joins method experiments.
- Blurting (free recall) scored offline from each idea's glossary and title terms; missed ideas already studied come due.

### Profiling
- New `tutorlib/profile.py`: confidence table per level, time-of-day and stamina residuals, mistakes by kind,
  forgetting vs forecast, pace, study habits, 7-day workload, experiments, plain-English advice.
- Profile.md rewritten in plain English; the app's My progress screen uses the same summary.
- Profile adjustments are now real in the app: checking routine, confidence notes, have-a-go-first hints, break point.
- One-key "why did I miss it?" reflection after unexplained wrong answers (capped at 6 per session, skippable).

### App
- Keys that work while typing: ctrl+t ask, ctrl+g hint, ctrl+r re-explain, ctrl+o Obsidian, ctrl+b / ctrl+q back to menu.
- Blurt screen; richer My progress; version shown on the menu.
- Guard before abandoning an unfinished session; resume restores elapsed time and revealed worked-example steps.
- Esc on the confidence step returns to the answer; review with nothing due no longer starts an empty session.

### Fixes
- Diagnose mode KeyError when an item's first idea wasn't the probed one.
- Review/exit blocks skipped remaining ideas after a batch without usable items.
- `pts=` on non-long questions, `5/0`, `1e999` and huge exponents no longer crash grading.
- Second Anki export in a run crashed on the yaml stub.
- A corrupt line in the event log no longer blocks the whole history.
- Stuck ideas were reported as learned; re-teaching an idea erased the learner's earlier own-words note and mistakes.
- Paper scores above the marks available are rejected; `end()` with no session logs nothing; plans with nothing to
  teach give a practice check instead of an exit ticket on untaught ideas.
- Right value but mark lost (units/s.f.) now counts as not yet correct everywhere (session score, gaps, lesson checks).
- AI: stopping a reply midway desynchronised later replies; login/limit states never recovered; answers could leak via
  re-explain; ctrl+q quit the app mid-session; option labels lost maths such as `v[y]`; commas split typed answers.
- Settings and usage files load safely and save atomically; settings inputs are clamped.

### Performance
- FSRS schedulers cached; the menu no longer refolds the whole history; streak and last Anki export kept in state.
- Learner state saved only after it changes, as compact JSON; answer map bounded; view files written atomically and
  skipped when unchanged; AI usage counter cached in memory; maths library warmed in the background.
- Saved states from 1.0 are rebuilt once from the event log (model version 1.1).

## 1.0.0 — 2026-09-30
- Terminal app (Textual) with lesson mode (goal → probe → plan → teach per idea), review, test prep, long questions and
  chat; Obsidian views (Now, Lessons, My Notes, Home); lean headless Claude on the subscription; local vault; teach cards
  for the 7 published packs; plain-English guide.
