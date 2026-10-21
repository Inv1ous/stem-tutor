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
