# Adjustable AI marking strictness

The learner's ice answer explicitly mentions weaker London dispersion forces, yet the AI feedback says that comparison is absent. The marking prompt currently mandates strict marking for every task. This change adds a saved, provider-independent marking policy and clarifies evidence-based semantic marking. It cannot guarantee that every model makes every judgement correctly.

## Approaches and decision

Provider-specific controls would drift. A second AI pass would add latency and usage, while keyword overrides would risk awarding scientifically wrong answers. Use one shared marking policy in the existing prompt builders, with unchanged validated mark-point results and scoring. These are implementation choices under the learner's standing request to proceed without questions.

## Behaviour

- Add Settings > AI marking strictness: Auto, Lenient, Balanced, Strict. Default missing, corrupt or unknown saved values to Auto, without rewriting files during load. Save and Cancel follow existing Settings behaviour; presets do not change strictness.
- Auto resolves deterministically to Balanced for learning, review and other ordinary practice; Strict for Test prep (`test`), Long questions (`long`), Topical past papers (`topical`) and Challenge re-marks (`challenge`). Do not adapt based on confidence, prior scores, model, or an AI classification request.
- Lenient accepts a clearly demonstrated correct core idea despite informal language or a minor nonessential omission. Balanced requires every substantive idea or relationship in the mark point and accepts equivalent wording. Strict requires precise, unambiguous evidence of each substantive requirement and any terminology, unit or precision explicitly required by the question. All levels accept scientifically equivalent wording and valid methods.
- Every level reads the complete submitted answer, including later paragraphs, before declaring a requirement missing. Do not add requirements beyond the supplied question/rubric, use confidence as evidence, award absent mechanisms, or accept contradictions. Request the shortest supporting quotation or a specific missing idea for each point. A one-mark point must not acquire extra model-answer detail requirements.
- Apply the setting to short written marking, long-answer AI checks, session re-marks and Challenge re-marks, for cloud, Codex and local models. A changed prompt naturally separates local reply-cache entries; do not reset chats or mutate provider settings.
- Explain Auto and each level beside the existing compact selector using normal Settings widgets. Keep keyboard navigation and Save accessible in small windows and all three themes.

## Preservation and limits

Deterministic MCQ/numeric grading, units/precision rules, rubric identities, partial-credit calculation, manual fallback, confirmation controls, protected retries and historical learner bytes remain unchanged. The setting affects future AI judgements, not earlier scores. No live paid calls, teaching-resource edits, model changes, automatic re-marking or dashboard are required.

## Acceptance

Tests cover saved-value validation, Save/Cancel, dynamic help, Auto resolution, explicit overrides, both marking prompt builders, all four UI request paths and provider routing/cache separation. The exact two-paragraph answer must reach the marker unchanged. Invalid point identities must still fall back to manual marking. Review the scoped change on Standards and Spec separately and record verification honestly: scripted/provider tests prove policy delivery, not live examiner correctness.
