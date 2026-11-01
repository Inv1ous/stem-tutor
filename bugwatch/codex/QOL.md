# QOL — written by Codex only, append-only

Quality-of-life ideas for the learner (not bugs: things that work but cost time, clicks, attention or allowance).
Append only, quoted heredoc, next free `Q-nnn`. Claude triages these after the bug fixes.

```
### Q-001 · app/screens.py · one-line title of the friction
- **Seen:** where and how (ran it in the sandbox / read the code)
- **Friction:** what it costs the learner (keys, seconds, confusion, AI allowance)
- **Idea:** the smallest change that removes it (at most three lines)
- **Size:** S | M | L
```

### Q-001 · build/out/packs · Replace generic past-paper feedback with the deciding step
- **Seen:** Read published 9701-7.1-p08: after the learner answers a Haber/Contact-process question, its explanation says “The official key follows the equilibrium rule in the stem.” That exact line appears in nine past-paper MCQs. Another generic line (“The keyed option follows the measured rate, particle collision argument or balanced reaction...”) appears nine times, including 9701-8.1-p03, a stoichiometric rate calculation.
- **Friction:** These lines do not show the deciding equation or rule, so the learner must spend an AI request or reconstruct the solution to understand a mistake.
- **Idea:** Replace each generic explanation in the ordinary past-paper bank with one question-specific calculation or rule and why the nearest distractor fails.
- **Size:** M

### Q-002 · app/tutor_app/ai.py · Warm the model selected for Ask instead of an obsolete conversation key
- **Seen:** Read `TutorApp.on_mount`, `Claude.__init__`, `reset`, `warm` and `stream`; ran a process-start spy without launching a CLI. Constructing Claude with general model Haiku then applying the app's `ai.model, ai.think = settings.ai_for("ask")` with Ask=Sonnet leaves `ai.key` at Haiku. Warming starts `(haiku, False)`; the first Ask request then starts `(sonnet, False)`. The initial chat/session reset uses that warm path.
- **Friction:** With separate Explain/Ask models, the intended advance startup warms the wrong conversation, leaving the first Ask to start its process on demand and potentially keeping an unused process alive. The extra startup delay is not measured here; no extra AI reply or allowance spend is claimed.
- **Idea:** Select the intended model/thinking key explicitly when warming after startup or a settings change, so advance startup benefits the next Ask request.
- **Size:** S

### Q-003 · app/tutor_app/tts.py · Skip cancelled speech preparation before starting the newly requested reading
- **Seen:** Read Speaker.stop, _run and _audio; ran /tmp/bugwatch-scratch/coordinator/speech_cancel_probe.py with fake player, fake _one and join_wavs, no synthesis or playback. The probe holds preparation of the first old part, calls stop() then say(new), and releases it. Trace is make old first, make old second, make old third, make new requested line, play new requested line. _run checks generation only after _audio has prepared all parts; synthesize also processes all chunks without cancellation checks.
- **Friction:** Moving on or stopping a long reading prevents stale playback but still spends work preparing its remaining parts before the latest reading can start. The deterministic mock confirms avoidable work and ordering; no real synthesis latency, CPU saving or one-second delay is claimed.
- **Idea:** Check the current generation between parts/chunks and abandon stale preparation before starting another part, so the latest requested reading can proceed sooner.
- **Size:** S

### Q-004 · app/tutor_app/screens.py · Throttle full Markdown reparsing while an AI reply streams
- **Seen:** Read `SessionScreen._stream` and `ChatScreen.reply`: both append each stream chunk to `buf` then call `w.update(cards.ai(buf))`; `cards.ai` runs `to_terminal` and Rich Markdown over the whole accumulated reply. Pure local benchmark with the app module (no CLI or vault writes): for a 20,000-character Markdown reply, rebuilding the card after every 20-character chunk took 2.308 s of CPU; every 100-character chunk took 0.461 s. At 10,000 characters and 20-character chunks it took 0.604 s. The fake CLI in `tests/app/fake_claude.py` emits seven-character chunks, confirming that small chunks are a supported stream shape. This isolates card construction and excludes Textual layout/render cost.
- **Friction:** A long streamed explanation can make the terminal sluggish and spend seconds of local CPU as each new chunk reparses all previous text. The measurements are synthetic and do not claim a particular real Claude chunk size or end-to-end delay.
- **Idea:** Coalesce chunks and refresh the card on a short timer or meaningful boundary, then render the complete reply once when the stream ends. Keep the existing final leak check before showing answers to open questions.
- **Size:** S

### Q-005 · app/tutor_app/app.py · Show the home screen before copying iPad inbox files
- **Seen:** Read `TutorApp.on_mount` and `mac.import_ipad_inbox`; a scratch-only `paper.pdf` probe confirmed the import performs `shutil.copy2` before returning. `on_mount` calls the import synchronously before `push_screen(HomeScreen())`, and the importer copies each PDF or image before moving its original to Imported. Published pack loading in the isolated vault took 0.084 s for 239 subtopics; no real iCloud file or network wait was measured.
- **Friction:** If the learner has a large or still-downloading iPad file, the first usable screen waits for its copy. The code establishes the blocking order; the size of an actual wait is unmeasured.
- **Idea:** Open Home first, then import inbox files in a worker and notify when they arrive, preserving the current copy-before-move and collision safeguards.
- **Size:** M

### Q-006 · views.py · Link each Home subtopic to its reference note
- **Seen:** Ran `views.write_home` in the scrubbed `/tmp/bugwatch-notes-qol-round3` vault. Its 102 published subtopics all have an existing `Subjects/...` reference note, but a fresh Home table shows plain subtopic text and `–` in Notes for every row because no progressive My Notes file exists yet. Example: `| 9701-1.1 Particles in the atom and atomic radius | ... | – |` even though `Subjects/9701 Chemistry/01 Atomic structure/1.1 Particles in the atom and atomic radius.md` exists.
- **Friction:** Home is the grouped subject dashboard, yet a learner cannot jump from any unstarted row to that subtopic's existing explanation; they must find it again in the vault tree.
- **Idea:** Make the subtopic label link to its published `pack['note']` when that file exists, keeping the separate My Notes link for notes earned during study.
- **Size:** S

### Q-007 · report.py · Keep the complete question accessible from Mistakes
- **Seen:** Read `mistakes_note` and ran `_clip_math` against the published `9701-1.2-p03` MCQ in the scrubbed scratch vault. The question asks which numbered statements about chlorine isotopes are correct; the journal would show only `Which statements are correct when referring to the two common isotopes of chlorine?…` because `_clip_math` drops every line after the first. It also omits all MCQ options. Across 5,198 published items, 2,416 stems have multiple lines and 417 have a first line longer than 160 characters, so this affects ordinary content, not just a contrived stem.
- **Friction:** When reviewing a mistake, the learner sees their choice and the answer but may not see the statements or options that made it wrong. They must hunt for the question in another note or session log before the journal entry makes sense.
- **Idea:** Keep the short preview but add a link to the full question or a collapsed full stem and options under each mistake.
- **Size:** M

### Q-008 · app/tutor_app/screens.py · Show how to reach the home side box's hidden progress rows
- **Seen:** In a scrubbed fake-Claude Textual pilot at 100x30, the home side box shows the date, Almanac week and five objectives; `Your topics` and the chapter rows are below its 21-row viewport. `#stats.max_scroll_y` is 414. Pressing Tab moves focus from `#menu` to `#stats`, then PageDown scrolls it by 18 rows; the visible home screen and footer give no cue for this. At 80x24 the side box is intentionally hidden, and at 140x46 its first few chapter rows are visible. Screenshot: `bugwatch/codex/shots/visual-qol-round3-home-keys-100x30.svg` (after two PageDowns).
- **Friction:** A keyboard user at a common window size sees the side box as a short plan and can miss the topic/progress list below it, despite that being one of the home screen's main summaries.
- **Idea:** When the side box overflows, add a quiet one-line cue such as “Tab to topics · PgDn to scroll” near its heading or at the bottom, while keeping the existing Tab/PageDown behavior.
- **Size:** S

### Q-009 · app/tutor_app/panels.py + tutorlib/views.py · De-emphasize bad extracted text when a readable past-paper scan is present
- **Seen:** Published image-backed MCQ `9701-8.1-x003` has a clear full-question scan at `Assets/mcq/9701_s23_13_q18.png`: four distinct graph choices. Its extracted options are three copies of `FRQFHQWUDWLRQ \x13 \x13 WLPH` and one `FRQFHQWUDWLRQ`; the stem ends with `WLPH`. A scrubbed, fake-Claude Textual pilot at 80x24, 100x30 and 140x46 shows those strings as the A–D choices in the terminal (`bugwatch/codex/shots/visual-qol-round3-ocr-graph-<cols>x<rows>.svg`); `views.question_block` writes the same text under the readable scan in Now.md. Another full-question scan, `9701_w21_11_q19.png` (`9701-12.1-x016`), clearly shows a tick/cross table while its extracted options are control characters. Among 2,022 published `Assets/mcq` image-backed questions, 78 have C0 control characters in the extracted stem/options. This is distinct from B-056, which has no fallback image.
- **Friction:** When a scan already contains the complete readable question, duplicated broken extraction fills the answer panel and Now page with misleading noise. A student has to ignore it and switch to the scan to distinguish the choices; it also makes the session transcript harder to review.
- **Idea:** For full-question scan items whose extracted stem or options fail a quality check, put the scan first in Now and collapse the suspect extraction behind a clear “Extracted text may be wrong” label; in the terminal keep the usable stem and A–D keys but suppress only the bad option text, directing the student to Now. Keep clean selectable text/options visible, and do not apply this rule to image-only diagrams such as the published SVG practice figures.
- **Size:** M

### Q-010 · app/tutor_app/tts.py + config.py · Offer a wider reading-speed range
- **Seen:** Settings labels Reading speed as `0.8 to 1.3`; `SettingsScreen.save`, `Settings.load`, and `tts.synthesize` all clamp to that range. In `/tmp/bugwatch-scratch/visual-qol-round3/tts_speed_probe.py`, a fake engine receives speed 0.8 when 0.5 was requested and 1.3 when 1.75 was requested; a saved setting of 1.75 reloads as 1.3. The probe writes only fake WAVs inside the scrubbed scratch vault and does not run Kokoro or a player.
- **Friction:** The learner asked for more speed control. Someone who needs slower speech for dense maths or faster speech for familiar material cannot choose beyond the current narrow range; typing a higher value silently lands at 1.3 after Save.
- **Idea:** Offer an explicitly wider range in Settings and keep the UI, loading clamp, synthesis clamp, and cache key in agreement. Choose endpoints after checking real Kokoro intelligibility and voice quality; no listening or quality claim was made here.
- **Size:** M

### Q-011 · app/tutor_app/tts.py · Begin long replies as soon as the first audio segment is ready
- **Seen:** `Speaker._audio` prepares every spoken part with `_one`, joins their WAVs, and only then returns a path to `_run` for `Player.play`. For a single long part, `synthesize` collects all `CHUNK_CHARS` audio frames before writing its WAV. `/tmp/bugwatch-scratch/visual-qol-round3/tts_latency_probe.py` used three delayed fake `_one` callbacks, a fake join, and a fake player: the first part was ready at 0.085 s, the other parts at 0.170 and 0.255 s, and `play` was first called at 0.255 s. No Kokoro engine or real player ran, so this proves ordering, not a real-world latency estimate. Fully pre-generated single-part audio already takes the cache path.
- **Friction:** An uncached multipart explanation or long answer stays silent while later audio is prepared, even when its opening segment is already available. The wait grows with the remaining parts and synthesis chunks; a learner cannot start listening during that work.
- **Idea:** Let playback consume ordered ready segments while the next segments are prepared, keeping stop/new-request generation handling and pause spacing intact. Preserve the joined/cached file path if needed for later replay, and measure actual first-audio latency before choosing a streaming granularity.
- **Size:** M

### Q-012 · app/tutor_app/tts.py · Keep replayed speech in the bounded live cache
- **Seen:** `Speaker._one` returns a live cached WAV without touching its modification time, while `_prune` deletes the oldest modification times only after a new `synthesize`. In `/tmp/bugwatch-scratch/visual-qol-round3/tts_cache_probe.py`, with a reduced `LIVE_KEEP=3` and fake synthesis, replaying the oldest “hot answer” did not protect it: creating a fourth clip deleted it, and the next replay synthesized it again. The production limit is 200, so this is a small-cache ordering demonstration, not a measured frequency in normal use. The same probe used pre-generated fake component files for five distinct two-part readings: `_audio` wrote five joined live files with a limit of three, because joins do not call `_prune`. No Kokoro or player ran.
- **Friction:** Repeatedly read lines can be discarded ahead of less-used newer lines, causing avoidable preparation on the next replay. Sequences composed of already generated parts can also grow the live directory beyond its intended file cap until an unrelated new synthesis triggers pruning.
- **Idea:** Apply one bounded cache policy to newly synthesized and newly joined files, and count cache hits as recent use when deciding what to keep. Verify the policy with the actual 200-file limit and representative replay/combination traces before estimating time or storage savings.
- **Size:** S

### Q-013 · app/tutor_app/tts.py · Keep blocking player control off the screen's response path
- **Seen:** Read `Speaker.say`, `sample`, `stop` and `_run` plus `Player.stop`/`play`; ran `/tmp/bugwatch-scratch/notes-qol-round3/tts_lock_probe.py` with a fake engine and player, no synthesis or audio. A fake `stop()` taking 0.2 s makes `say()` itself take 0.203 s. A fake `play()` held at a barrier keeps the speaker condition lock, and `Speaker.stop()` cannot finish until that barrier is released. Production `Player.stop()` can wait up to one second for `afplay` to terminate; `_run` invokes `play()` while holding the same condition lock.
- **Friction:** Starting or stopping a reading is a synchronous screen action. When the player takes time to stop or start, the terminal input handler waits on player control or on the lock held by the reading worker. This is separate from Q-003's cancelled synthesis work; the probe demonstrates ordering only, not actual `afplay` latency.
- **Idea:** Keep generation changes under the condition lock, but perform potentially blocking player stop/start on a worker with a final generation check so stale audio cannot begin. Avoid holding the condition lock across player operations.
- **Size:** M

### Q-014 · app/tutor_app/prompts.py · Reuse unchanged question context across follow-up AI turns
- **Seen:** In a scrubbed `/tmp/bugwatch-reports-crosscheck-round5` vault with all plan.json `source_path` removed and `report.almanac_push` stubbed, `/tmp/bugwatch-scratch/reports-crosscheck-round5/prompt_repeat.py` opens published long MCQ `9702-10.2-x026` and builds two `prompts.ask` strings for consecutive questions about it. They are 1,987 and 1,975 characters; their 1,941-character CONTEXT prefix is byte-identical. `SessionScreen._stream` sends each prompt to `Claude.stream`, whose process is persistent for the chosen model/thinking key. No AI was launched, so latency and billed tokens were not measured.
- **Friction:** Repeated follow-ups about an unchanged question resend its full stem, choices and teaching context. This increases input size on every turn and may consume allowance or response time depending on provider caching; the exact charge is unverified.
- **Idea:** Track the context last sent to each AI conversation and send only changed parts on follow-up turns; resend the full packet after a reset, model switch or question change.
- **Size:** M

### Q-015 · app/tutor_app/screens.py · Keep the AI process asleep when AI is switched off
- **Seen:** In a scrubbed `/tmp/bugwatch-reports-crosscheck-round5` vault with every `plan.json` `source_path` removed, run `PYTHONDONTWRITEBYTECODE=1 STEM_TUTOR_VAULT='/tmp/bugwatch-reports-crosscheck-round5/mnt/STEM Tutor' PYTHONPATH="$R/app:$R/plugin/stem-tutor/skills/tutor/scripts" env -u TERM_PROGRAM "$R/.venv/bin/python" /tmp/bugwatch-scratch/reports-crosscheck-round5/ai_off_warm.py`. The isolated fake-Claude Textual pilot sets `app.settings.ai=False`, then opens ChatScreen. It prints `initial_starts 0`, `starts_after_offline_chat 1`, `fake_messages 0`. `ChatScreen.on_mount` unconditionally calls `ai.reset()`; `Claude.reset` schedules `warm()` when the binary is available without consulting the app's AI-off setting. Session block changes use the same unconditional reset.
- **Friction:** Choosing AI off still starts an unused background Claude process on entering chat (and on lesson block changes). This costs process startup and memory even though all reply actions correctly refuse AI use. The fake provider proves process creation only; no real startup time or AI allowance use was measured.
- **Idea:** Skip or disable warm-up while `settings.ai` is false; warm again when AI is enabled.
- **Size:** S

### Q-016 · tutorlib/insights.py · Reuse the event history when building Weekly
- **Seen:** In the scrubbed `/tmp/bugwatch-reports-crosscheck-round5` vault, `/tmp/bugwatch-scratch/reports-crosscheck-round5/events_latency.py` generated 20,000 then 50,000 synthetic answer events and timed normal report and session actions with `Vault.events` calls counted. At 50,000, Weekly took 1.405 s and read the whole JSONL log three times; answer and end took 0.002 and 0.008 s with zero reads. Four repeated Weekly builds in `/tmp/bugwatch-scratch/reports-crosscheck-round5/report_repeat.py` took 1.281, 1.617, 1.834, and 1.454 s, each with three reads. `week_report` loads all events, then `state_at(start)` and `state_at(end)` each reparse all events. A scratch-only substitution making `Vault.events` iterate an already loaded 50,000-event list gave a 0.097 s median for four Weekly builds. No real learner history was read or timed.
- **Friction:** For a large history, opening or regenerating Weekly pauses for over a second while the same log is parsed three times. The 50,000-answer case is synthetic and may exceed a typical learner's history; the measured 20,000-answer Weekly call was 0.425 s.
- **Idea:** Reuse the events already loaded in `week_report` when calculating the two boundary states, preserving event order and effective regrades. This removes two disk parses without changing the report.
- **Size:** S

### Q-017 · app/tutor_app/cards.py · Show earned mark points alongside full-question accuracy
- **Seen:** In a scrubbed scratch Tutor session, published four-mark structured item `P2-4-r05` self-marked with points 1, 2 and 3 records `score: 0.75` (three of four points) but `cards.feedback` says only “Not quite,” the Lesson log says “incorrect,” and the final summary displays `Correct: 0`, `Accuracy: 0%`. A three-mark numeric item with the right value but no unit records `score: 0.5` and says “a mark lost.” “Don't know” correctly records zero. The session's binary correct/accuracy counters are internally consistent; this is a presentation gap, not a wrong-total claim. Probe: `/tmp/bugwatch-scratch/lesson-navigation-round5/score_consistency.py` with a scrubbed scratch vault, fake external paths not needed, and `report.almanac_push` stubbed.
- **Friction:** After ticking most scheme points, the learner cannot see how many points they earned in immediate feedback or the summary, and may read 0% accuracy as zero exam marks despite 3/4 self-marked credit.
- **Idea:** Display “3 of 4 scheme points” in structured feedback and label the summary's percentage “fully correct questions”; keep the binary progress rule explicit.
- **Size:** S

### Q-018 · app/tutor_app/screens.py · Match plain-keyboard spellings of Unicode topic titles
- **Seen:** Ran a scrubbed 80x24 fake-Claude picker pilot against 102 active subtopics. Searching `Brønsted` finds `9701-7.2`, but `Bronsted` returns 0; `Hess’s` finds `9701-5.2`, while ordinary keyboard `Hess's` returns 0. The same straight-apostrophe mismatch affects `Newton's`. Upper/lowercase Greek searches (`ΔH`/`δh`, `Σ`/`σ`) work, and Enter/Escape navigation through a no-results state remains safe. `PickerScreen._matches` lowercases and replaces hyphens only.
- **Friction:** A learner typing the common ASCII spelling of a visible chemistry term or a straight apostrophe can be told that no topic matches, despite a published topic with that exact name apart from typography. They must shorten the query or know the title's Unicode characters.
- **Idea:** Normalize apostrophe variants and searchable accent/transliteration variants alongside case in the topic search index and query; keep displayed titles unchanged.
- **Size:** S

### Q-019 · tutorlib/anki.py · Let corrected flashcards reach learners who already exported them
- **Seen:** Read `anki.export`: `done = set(state.get("anki_exported", []))` and `if uid in done ...: continue` skip an exported card forever, without checking whether its front/back changed. Stable GUIDs are already available for updates. The learner guide currently promises new cards only; no actual Anki import/update was run.
- **Friction:** If a later content release corrects an already-exported definition or formula under the same card ID, routine weekly exports omit that correction. The learner has to find and edit the old Anki card manually, or arrange a re-export outside the normal flow.
- **Idea:** Track exported content hashes and include changed cards with their existing GUIDs, allowing Anki to update the existing note rather than create another one.
- **Size:** M

### Q-020 · bugwatch.py · Open the board from the workspace root
- **Seen:** The workspace is the parent directory of `stem-tutor`, while the canonical entrypoint lives in the repository root. Adding the requested `bugwatch.py` adapter makes the board command available from both locations.
- **Friction:** Starting a task from the workspace root and running `python3 bugwatch.py --all` did not have an entrypoint, even though the repository-root command was already supported.
- **Idea:** Keep a parent-level `bugwatch.py` symlink to `stem-tutor/bugwatch.py`, so the canonical implementation remains in the repository and the workspace command works from any directory.
- **Size:** S

### Q-021 · tests/library_assets.py · Reuse the fresh Library reader inside one resource operation
- **Seen:** Six known pack/graph reads were instrumented before edits: each creates two AssetLibrary readers, parses Library/catalog.json twice and verifies asset bytes twice; individual reads took about144–154ms. Two baseline reads came from codex_qol_board and four distinct references were measured by visual_round3. Saved references, hashes, construction counts and timings: /tmp/bugwatch-library-helper/before.json. read_bytes/canonical_path/copy_to_vault create one reader, then _source_alias creates a second reader for the same operation.
- **Friction:** Repeated integration-fixture reads unnecessarily parse the large catalog twice per resource, slowing local verification without providing freshness between operations.
- **Idea:** Let _source_alias reuse its caller's reader within that operation; keep a fresh reader for every public operation and standalone alias call, with existing SHA checks intact. No persistent cache.
- **Size:** S

### Q-022 · tests/app/test_learning_tutor.py · Keep delayed Learn guard regressions non-vacuous
- **Seen:** Three delayed Learn tests still return obsolete blocks-shaped responses and assert that the model-only string STALE RESPONSE never appears. Current Learn selects published card sections instead. Disposable contract proof rejects the old payload and accepts a valid sections response. An in-memory mutation bypassing the completed-question-count guard leaves the old closed-question-boundary test passing, showing it does not detect the regression it names. Proof: /tmp/bugwatch-learning-regression/mutation-before.json; no live production code was changed for the mutation.
- **Friction:** A stale reply could bypass the intended request boundary while these regressions still report green because response validation independently discards their obsolete payload.
- **Idea:** Return valid current sections selecting a marker from the fixture teaching card, await the actual worker, and retain display/history/event/context assertions. Reuse the existing valid no-transition control and confirm the stale test fails when the boundary guard is bypassed in memory.
- **Size:** S

### Q-023 · Library question reviews · Refresh the active Q34 source-bound duplicate review
- **Seen:** The v273 disposable inventory finds one unresolved canonical selection conflict, 9702_w24_13_q34, and the original review correctly rejects the changed p08 record fingerprint. The x027 binding and source image digest still match.
- **Friction:** The active candidate pool includes the OCR fraction V 2 1 alongside the source-correct V/2 transcription, despite both being the same printed question. Preserving the prior review is required; silently weakening its fingerprint check would be incorrect.
- **Idea:** Independently review the exact current pair against publisher PDF page 14 and its registered image, then publish one fresh immutable equivalence-review resource with current full-record hashes. Keep both original questions, their IDs and aliases, the old review and all learner history intact.
- **Size:** Small source-bound review resource only; no engine or question-content change. Independent exact-diff review and disposable proof required before registration.

### Q-024 · bugwatch · Reuse machine-isolation fixtures for external scratch probes
- **Seen:** Pytest probes outside tests/ do not inherit the repository conftest fixtures. The existing sandbox guidance correctly makes explicit configuration isolation the caller's responsibility; no wrapper defect is claimed.
- **Friction:** Each scratch app probe repeats the same Inbox, Downloads, learner-vault and worker-check setup, making accidental real-machine defaults easier to overlook.
- **Idea:** Add a small opt-in pytest plugin that reuses only the three existing machine-isolation fixtures from the fixed repository conftest path. Load it explicitly with -p bugwatch.probe_isolation; leave default check.sh behavior and all fixture definitions unchanged. Document that fixtures apply at test setup, so module-level app/file actions still require explicit discipline.
- **Size:** One small plugin, one command example and a harmless subprocess sentinel regression proving external isolation and unchanged ordinary in-repository behavior. No app or resource change.

### Q-025 · Ask composer · Explain the first-image limit for multi-page questions
- **Seen:** A real two-page v274 topical question was inspected in SessionScreen and Ask at 80x24 and 140x46. SessionScreen directs learners to all pages in Obsidian, but its note is covered by the Ask modal; the composer only gives generic context guidance.
- **Friction:** The current, intentional provider contract sends the question text and primary image. A learner can submit a question about another source page without seeing that limitation where they decide to send.
- **Idea:** Show a short passive notice in the Ask composer only when its actual focus has multiple source pages: the AI receives the question text and first image, and all pages should be read in Obsidian. Verify any advertised shortcut works in that modal or give a precise return-to-session instruction. Keep drafts, focus, requests and single-page behavior unchanged.
- **Size:** Small UI-only guidance with focused single-page/multi-page, draft/focus and two-size visual checks. No provider capability, grading, source resource or publication change.

### Q-026 · bugwatch · Distinguish verified quality-of-life work from completed work
- **Seen:** A fresh isolated regression posts VERIFIED Q-001 successfully, but the board keeps the previous DONE status.
- **Friction:** The requested verification pass cannot show genuine QOL verification using the existing append-only event format.
- **Idea:** Read Codex VERIFIED and REJECTED QOL verdicts separately from bug verdicts, preserving dated cross-log ordering, latest activity and all history.
- **Size:** Small board parser change with focused regression checks.

### Q-027 · tests/conftest.py · Keep extraction tests from discovering paid provider executables
- **Seen:** A new extraction test omitted its fake CLI override and launched a disposable real review worker. The agent terminated its process immediately. Two controlled regressions now prove both Codex and Claude defaults would discover an installed provider; the proof uses harmless sentinel scripts, not real providers.
- **Friction:** Test authors can accidentally spend provider usage when they forget to configure a fake executable, despite isolating the vault and disabling workflow preflight checks.
- **Idea:** Set unavailable extraction provider paths in the existing test isolation fixture. Individual tests still override those paths with explicit fake providers. Production launches outside pytest remain unchanged.
- **Size:** Two default environment assignments plus a public worker regression for each provider; reuse the opt-in external-probe fixture.

### Q-028 · extraction jobs · Honor an explicitly authorized Codex reserve for one run
- **Seen:** This user explicitly asks for Codex work until about20% weekly allowance remains. Existing shared extraction defaults would stop at30% remaining, and changing shared configuration would affect unrelated workflows.
- **Friction:** A single authorized goal cannot express its stopping boundary without changing global limits or misreporting the actual allowance.
- **Idea:** Persist an explicit Codex-only job stopping percentage, with a minimum reserve of20%, strict fresh-allowance admission and unchanged defaults for other jobs/providers. Preserve failure, source and independent-review gates.
- **Size:** One optional creation argument/CLI flag with default, boundary, invalid-data, provider-isolation and config-preservation regressions.

### Q-029 · Insights AI summary · Show the newly requested profile reply in the viewport
- **Seen:** An actual successful A request saves the AI summary near the bottom of Insights, while the viewport stays at unchanged top statistics. Native before capture confirms the requested result is offscreen.
- **Friction:** Learners must search the report to discover whether the requested reply arrived.
- **Idea:** After successful cache save and Markdown rebuild, use the existing AI-summary anchor. Keep cache-error scroll position, saved content and request count unchanged; note-only output failure still displays the saved new summary.
- **Size:** One existing anchor navigation call after awaited Markdown rebuild, with real viewport/error/navigation controls.

### Q-030 · extraction reader · Read scanned source pages through hash-bound native OCR aids
- **Seen:** All-course extraction found five scan-only sources (2522 pages) without usable PDF text.
- **Friction:** Repeated manual page reading costs worker context and does not preserve reusable literal OCR provenance.
- **Idea:** Explicit per-job enable-ocr freezes selected source/page/sidecar/render hashes; ocr-text returns compact literal text, confidence summary and an unreviewed warning. Validate every frozen byte before reads/workers. Original PDFs, pending_ocr status and teaching/publication gates remain unchanged.
- **Size:** Bounded reader module, opt-in CLI, disposable provenance/tampering controls and Work-only native caches.

### Q-031 · report.py Today note · Name the glossary review work in the daily plan
- **Seen:** 00:11 generated Today note contains a literal empty Term_review label for an available glossary review block.
- **Friction:** The learner cannot tell which definitions the daily plan asks them to revisit.
- **Idea:** Render a readable glossary-review label with its available term names/count, preserving ordinary existing plan rows.
- **Size:** One report formatting seam plus public output controls; no schedule or history changes.

### Q-032 · extraction source verification · Verify exact selected resources without rehashing the full course
- **Seen:** 00:25 one10source job verification hash-reads507 PDFs totalling1.32GB.
- **Friction:** Cropping and source checking repeat unrelated resource I/O for every selected batch.
- **Idea:** Apply exact ID/path/declared-alias selectors to fresh catalog metadata before resolving bytes, and reuse one local metadata snapshot per inventory operation. Preserve per-operation source hash checks and default full-inventory behavior; no persistent cache.
- **Size:** Optional source selector seam plus extraction inventory/verification call sites and immutable-resource controls.

### Q-033 · extraction graph reader · Query bounded authoritative graph context from a worker
- **Seen:** 01:10 S2 and M1 extraction workers dump8077 and7011 characters of KC context; two relevant S2 rows need377bytes before provenance.
- **Friction:** Handwritten graph snippets waste context and make parent-subtopic/prerequisite schemas harder to follow.
- **Idea:** Add read-only graph JOB exact-ID or literal-query command, bounded to8results by default/max20, returning graph hash, matched current-courseKC, parent and declared prerequisite validity. Use verified canonical adapters; no mapping inference, mutation, persistent cache or approval.
- **Size:** Bounded reader/contract/CLI and targeted immutable-input/limit controls; separate from publication.

### Q-034 · extraction role contract · Separate approval status and empty output scope from factual uncertainty
- **Seen:** 01:22 complete P4/FP1 diagram batches fail only because generic not-teaching-approved disclaimers occupy uncertainty; one answer-only job marks no_relevant_content=false despite zero bound question records.
- **Friction:** Workflow status is mistaken for a factual source doubt, and supporting keys are confused with extracted question/diagram content.
- **Idea:** Clarify uncertainty holds concrete source/OCR/mapping/content doubts while approval stays false separately. Answer-only sources without selected question bindings are empty relative to output scope and require an explicit reason. Preserve all source and review gates; never blanket-strip existing doubts.
- **Size:** Two role-contract clarifications plus reviewable metadata repair of two exact status-only batches; raw originals and independent review preserved.

### Q-035 · extraction role contract · Retain worked teaching example figures for independent review
- **Seen:** 02:12 independent P4 FP1 and Physics notes reviews identify omitted worked-example figures; some maker coverage reasons excluded assessment-context material based on its format.
- **Friction:** Subparts marks or MCQ-like layout alone do not establish past-exam provenance, so useful teaching diagrams and their context can disappear from candidate extraction.
- **Idea:** Clarify explanatory worked examples in notes/textbooks remain eligible. Keep actual past-paper/mark-scheme media attached to question context; uncertain provenance retains unapproved contextual media and explicit doubts rather than silent omission or approval.
- **Size:** Narrow prospective role wording; no source/candidate bulk repair or gate waiver, effectiveness remains subject to independent review.

### Q-036 · report.py question sheet · Direct learners back to their current tutor session
- **Seen:** Shared question-sheet output still says Answer in the Cowork chat despite supporting native tutor and Codex sessions.
- **Friction:** Learners using another supported tutor surface are sent toward an obsolete app-specific location.
- **Idea:** Use Answer in your tutor session while preserving the question content, timing and output path.
- **Size:** One learner-facing instruction line; prose correction only, no grade/history/schema change.

### Q-037 · extraction global reference collector · Reuse unchanged media digests within one collection
- **Seen:** Frozen245-artifact reference snapshot hashes media20220times over7204distinct file identities:2.35GBreads versus0.73GBunique,1.62GBavoidable repeated reads.
- **Friction:** Many question occurrences share the same rendered page; rebuilding the reference-only index repeatedly rereads identical media bytes.
- **Idea:** Cache digests only within one collector invocation using resolved path plus device/inode/size/mtime/ctime. Re-stat each hit, hash and compare before/after file identity on misses; changed files refresh or refuse, preserving all provenance/occurrences/output.
- **Size:** Local collector helper plus focused unchanged/changed-file and exact-output controls; no persistent cache, source/candidate mutation or paid-model changes.

### Q-038 · SessionScreen question controls · Hide the solvability action after its question is answered
- **Seen:** Public Learn→Find my gaps→MCQ→confidence4 still shows Can I solve this after marking; pressing it only reports This question is no longer open.
- **Friction:** Dead control occupies a dedicated row in compact terminals and adds noise instead of helping the learner.
- **Idea:** Show/activate solvability only for the currently presented question; retain open no-help/self-mark stages and restore on next/retry question.
- **Size:** Narrow UI visibility/action eligibility; two public80x24/100x30 expectations failed before change, native evidence inspected. No grading/event mutation.

### Q-039 · extraction reference graph inputs · Bind graph context to verified canonical Library bytes
- **Seen:** Collector reads fourteen registered regular graph file adapters directly. Independent census confirms all14 currently equal their verified canonical resources; no active corruption found.
- **Friction:** A stale adapter copy could silently change reference-only context despite the declared Library source and hash contract.
- **Idea:** Read exact registered aliases through AssetLibrary, preserve graph IDs/contexts, and include requested alias plus canonical path/stable resource/hash in input provenance. Reject unknown/tampered canonical inputs with no raw-copy fallback.
- **Size:** Narrow collector reader and synthetic stale-adapter/unknown/corrupt/healthy controls; no publication, model input, candidate or active graph mutation.

### Q-040 · Shortcut lesson keyboard navigation · Scroll a revealed explanation without hiding its later sections
- **Seen:** Public Kirchhoff shortcut lesson with all8sections revealed has no keyboard log scrolling: PageUp and Alt+Up leave scroll at32/32 (80x24) and19/19 (100x30), focusNone. Two external RED cases in3.70s with native captures.
- **Friction:** Earlier explanation sits above the viewport; Left can hide later sections to revisit it, but the full revealed explanation cannot be scrolled by keyboard.
- **Idea:** Reuse established log-scroll bindings/actions in the shared shortcut frame, preserving Enter/Left section controls and focused input/list navigation.
- **Size:** Small keyboard-accessibility change; preserve current phase/revealed sections/queue/events and source bytes. No content-loss claim.

### Q-041 · screens.py · Coalesce repeated identical numeric-format warning toasts
- **Seen:** 2026-11-02 04:45 HKT · Native disposable Learn flow at80x24/100x30; four public repeated-refusal controls passed, no provider calls.
- **Friction:** Three consecutive ungraded refusals for the same comma decimal create three identical six-second warnings. Native `ui/repeated-numeric-refusals/ask-returned.svg.png` shows them covering the question and much of the editor, with the last warning clipped below the window. Draft, selection and exactly-once grading are already correct (B251); this is duplicate visual obstruction.
- **Idea:** While an exact same format-only warning is already visible, keep one copy. Preserve distinct errors, other app notifications, original warning duration and numeric draft/selection/focus/events. Use a small screen-local mechanism or supported notification API; no global clearing or notification framework.
- **Size:** S · Narrow format-refusal branch, with native repeated-warning and distinct-error/expiry/preservation controls; no backend protocol or grading changes.
