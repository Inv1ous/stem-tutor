# FIXES — written by Claude only, append-only

One line per event: `- HH:MM B-nnn STATUS · detail`. Statuses: `CONFIRMED`, `FIXED` (detail: commit · test id),
`REJECTED`, `DUPLICATE of B-nnn`, `DEFERRED`, `NEEDS-INFO` (a question for Codex). Also `- HH:MM LAST-READ B-nnn` after
each pass through `codex/BUGS.md`, and `- HH:MM SESSION-END · …` at the end. Full rules: `README.md`.

Codex: read this before every sweep. Don't re-report anything marked FIXED, REJECTED, DUPLICATE or DEFERRED. When a fix
lands, try to break it and log `VERIFIED` or `REOPEN`. Answer `NEEDS-INFO` questions with a `REPLY`.

<!-- ↓↓↓ append below this line ↓↓↓ -->

- 12:12 B-005 CONFIRMED · parse_expr evaluates the student's text; proof file written from my scratchpad
- 12:12 B-002 CONFIRMED · 118 scores 1.0 against exact 117; exact is never read
- 12:12 B-001 CONFIRMED · '500 kg' and '500 banana' both score 1.0 when the answer has no unit
- 12:12 B-004 CONFIRMED · '16 N' scores 0 against 16.46 N with sf_ok [2,3]
- 12:12 B-003 CONFIRMED · '1 km9999' raises OverflowError out of grade_item
- 12:19 B-005 FIXED · 0c64aee · tests/test_grade.py::test_expression_input_cannot_run_code · plain-maths character whitelist, no builtins in the parser namespace; also refuses power towers (9^9^9^9 froze >20 s): test_expression_power_tower_is_refused_not_computed
- 12:22 B-002 FIXED · 6701db5 · tests/test_grade.py::test_exact_answers_allow_no_error
- 12:27 B-004 FIXED · 9b0d36d · tests/test_grade.py::test_value_rounded_to_its_own_sig_figs_is_right (+ trailing-zero and magnitude tests); all 1,260 published instances at every allowed s.f. score 1.0
- 12:29 B-022 FIXED · bfa34c7 · tests/test_grade.py::test_joined_units_after_a_slash_are_all_below_the_line; 1,950 published answers still score 1.0
- 12:30 B-003 FIXED · ff56c77 · tests/test_grade.py::test_extreme_unit_exponent_is_a_wrong_unit_not_a_crash + test_value_overflowing_on_unit_conversion_is_not_a_crash (1e305 Gm in pm also crashed)
- 12:33 B-001 FIXED · cd2f9a0 · tests/test_grade.py::test_unit_on_a_plain_number_answer_earns_no_credit, test_arithmetic_after_the_number_is_unreadable; tests/test_v110.py::test_unit_on_a_plain_number_question_keeps_it_open (app refuses, question stays open)
- 12:39 B-021 FIXED · 5efc2ab · tests/test_grade.py::test_identities_true_only_for_positive_values_are_rejected; my B-005 test's false identity replaced with abs(-x) = abs(x)
- 12:44 B-023 FIXED · 7edd366 · tests/test_grade.py::test_expression_grading_time_is_bounded (10 inputs incl. Pow(2,1e9), (x+1)^10000, x^x^x^x, x^(x^x): all refused in <0.1 s); simplify removed, numeric evalf(subs=) sampling
- 12:49 B-023 FIXED · dda030e · follow-up: sample values now come from a real-float evaluator (evalf gave 1e135 noise at a pole); tests/test_grade.py::test_equivalence_survives_a_sample_on_a_pole; x^(x^10) added to the timing test
- 12:49 NOTE · found while fixing B-005, fixed in c108d2c: "u^2 + 2as" (the answer to published 9702-2.1-i24) never matched because "as" is a Python keyword; R1 was split into R times 1, so R2 equalled 2 R1. tests/test_grade.py::test_keywords_and_subscripted_names_are_variables, test_subscripted_names_are_not_numbers
- 12:50 B-012 FIXED · 849113d · tests/test_store.py::test_event_after_a_torn_line_survives_replay
- 13:52 B-011 FIXED · ad4eb3a · tests/test_v110.py::test_retaught_idea_keeps_every_paragraph_of_your_words (three paragraphs, re-taught twice)
- 13:52 B-010 FIXED · 622926e · tests/test_v110.py::test_same_title_lessons_in_one_minute_get_separate_logs
- 13:53 B-013 FIXED · 42dac54 · tests/test_anki.py::test_second_export_in_the_same_minute_keeps_the_first
- 13:54 B-016 FIXED · 03c9159 · tests/app/test_mac.py::test_ipad_import_never_overwrites_a_pdf; also Imported/ originals (test_ipad_import_keeps_every_original_in_imported)
- 13:57 B-015 FIXED · 66600c6 · tests/app/test_tui.py::test_long_answer_working_is_saved_in_the_lesson_log (written to the lesson log on submit, before marking)
- 13:57 B-014 FIXED · 66600c6 · tests/app/test_tui.py::test_failed_ai_marking_gives_the_tick_list_back (ticks kept, submit works)
- 14:00 B-018 FIXED · 8b55619 · tests/app/test_ai.py::test_leak_guard_catches_plain_disclosures (13 cases incl. Codex's 3) + test_leak_guard_lets_hints_through (5)
- 14:01 B-006 FIXED · bb7df32 · tests/test_v110.py::test_time_blocks_cover_the_small_hours (hours 0-23 boundaries; takes effect with the model-version bump below)
- 14:02 B-007 FIXED · 2d0c96b · tests/test_v110.py::test_hinted_answers_do_not_clear_a_misconception
- 14:05 B-008 FIXED · 6c5b0e9 · tests/test_v110.py::test_lost_mark_answers_count_as_wrong_in_the_profile + tests/test_report.py::test_session_note_accuracy_counts_lost_marks_as_the_session_does (the session note had the same mismatch); MODEL_VERSION 1.1.1 rebuilds saved states with B-006/7/8
- 14:06 B-017 FIXED · 025f85a · tests/app/test_ai.py::test_overlapping_requests_respect_the_daily_cap (limit: a one-shot started while a stream is mid-reply can still exceed the cap by one)
- 14:06 LAST-READ B-023
- 14:06 NOTE · Claude paused (usage limit). Still open: B-020, B-009, B-019. Not yet done: SESSION-END, CHANGELOG, republish to the vault
- 16:54 B-020 FIXED · d8304e2 · tests/test_v110.py::test_restart_resumes_the_repair_worked_example_where_it_was; tests/test_cli.py::test_next_after_a_worked_example_moves_on (the chat CLI's next still completes it)
- 16:55 B-019 FIXED · 15487a0 · tests/test_publish.py::test_pruning_keeps_the_two_newest_previous_versions_past_v9
- 16:57 B-009 FIXED · 7341511 · tests/test_v110.py::test_a_finished_experiment_decides_the_method (winner used; no_difference, ineligible type and active misconception keep the default)
- 16:59 B-001 FIXED · 0d4fef7 · reopen: '%' allowed only where the stem asks for a percentage; tests/test_grade.py::test_percent_sign_only_where_the_question_asks_for_a_percentage; 9702-1.1-i01 seed 4 '500%' now refused, 1,950 published answers still 1.0
- 17:01 B-024 FIXED · 1c4f630 · tests/test_grade.py::test_keywords_alone_never_mark_a_short_answer_right; tests/test_session.py::test_short_answer_with_every_keyword_still_waits_for_judgement; SKILL.md and How It Works.md updated (every short answer is judged; keywords only a hint)
- 17:02 B-025 FIXED · 9faba09 · tests/test_grade.py::test_wildly_wrong_finite_values_grade_without_crashing (1e308, -1e308, 1e-308, 5e-324 against 7.5e-7)
- 17:02 LAST-READ B-025
- 17:11 B-012 FIXED · 1fb1360 · reopen: replay decodes line by line from bytes; tests/test_store.py::test_a_torn_multibyte_character_loses_only_its_own_line (mac.py startup count also read in binary)
- 17:11 B-030 FIXED · 1fb1360 · tests/test_store.py::test_unicode_line_separators_inside_an_answer_survive_replay (U+2028, U+2029, U+0085, form feed)
- 17:14 B-031 FIXED · d6b3bc4 · tests/app/test_tui.py::test_ai_replies_are_guarded_for_every_open_question; every AI stream (not only ask/explain) is now guarded against all open questions
- 17:15 NOTE · found while fixing B-031, fixed in 5c3e4f5: every app test imported from the real iCloud iPad inbox (empty, so nothing moved); tests now use a temp inbox (tests/app/test_mac.py::test_tests_never_see_the_real_ipad_inbox)
- 17:16 B-026 FIXED · f2d1b66 · tests/test_v110.py::test_ending_a_session_refreshes_notes_for_every_idea_answered
- 17:18 B-027 FIXED · 89edb11 · tests/test_session.py::test_retest_score_goes_to_the_idea_retested_even_on_a_multi_idea_item
- 17:20 B-028 FIXED · 1663f25 · tests/test_anki.py::test_same_card_id_in_two_packs_exports_both (ids and GUIDs now pack-qualified; the real vault has no past exports)
- 17:21 B-029 FIXED · 1c9d20b · tests/test_anki.py::test_inequalities_and_arrows_survive_as_html (11 published cards affected)
- 17:21 LAST-READ B-031
- 17:23 B-034 FIXED · 87c559b · tests/test_grade.py::test_unicode_maths_is_read_like_ascii (11 forms); tests/test_session.py::test_expression_answers_unicode_right_and_unreadable_stays_open
- 17:25 B-032 FIXED · 0335c13 · tests/test_v110.py::test_repair_teaching_is_shown_in_now_logged_and_resumed; the refute card had the same gap and is fixed the same way
- 17:27 B-033 FIXED · 2a464ee · tests/test_session.py::test_ai_help_counts_as_a_hint_and_is_refused_on_no_help_checks; tests/app/test_tui.py::test_asking_the_ai_is_refused_during_a_no_help_check
- 17:27 LAST-READ B-034
- 17:33 NOTE · Haiku review (numbers/units): 2 findings, both confirmed and fixed in 728e6f6 ("ms-1" expected unit read only as per-millisecond; "°C" never matched itself). tests/test_grade.py::test_expected_units_read_every_way_and_identical_units_match
- 17:33 NOTE · Haiku review (CLI/storage/build): 3 findings, all rejected. The hook's "STEM Tutor:" prefix is plain context for Cowork's SessionStart hook, not a JSON command; publish.py --vault and blind.py --ids with no value are developer-script misuse, not student-reachable
- 17:36 NOTE · Haiku review (app): 2 findings. pretty_units half-converting brace exponents: confirmed (the student's own typed answer), fixed in 636a129. flatlatex fallback leaving '\,': rejected as stated (the converter raised on 0 of 4,894 published spans), but checking it turned up 142 spans rendered with raw LaTeX (\ge, \le, \ne, \ldots, pmatrix, \text glued onto commands), also fixed in 636a129: tests/app/test_ai.py::test_terminal_maths_has_no_raw_latex_left
- 17:36 NOTE · Haiku review (session engine): no findings
- 17:38 LAST-READ B-034
- 17:38 SESSION-END · fixed 34, rejected 0, deferred 0 (B-001 and B-012 reopened once, then fixed again). Also: 3 found while fixing (keyword/subscript names, pole sampling, real iPad inbox in tests), Haiku review 3 fixed + 142 raw-LaTeX spans, 4 rejected. Released as v1.1.1
