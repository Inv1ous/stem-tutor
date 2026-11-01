# Fusion parity preflight review

27 October 2026. Scoped CPU review: **0 serious findings** in the frozen scratch probe.

Reviewed `fusion-parity-v1/probe.py`, its inputs and copied resource/attempt helpers against the parity plan.
The current script SHA256 is `d94a4653fcf3a0405740a003d5f198396eca3cf8202676db64771e062a18ff77`;
input SHA256 is `22b31a6a86f10ca920d2e135f70ff7a3320cbe1b0294fcff562edf2547d03b1a`.
Input code hashes and all seven numerical tolerances match the current source before execution.

Independent CPU assertions verified all 18 ordered IDs and original user messages against frozen DEV18, without
copying assistant gold, expected answers or checks. Inputs have 288 selected positions, maximum length111;
each last selected index is the final prompt-token index that predicts the first answer token. The capture
rechecks actual native Fast token IDs before any forward (`probe.py:191–195`). It generates no answer or
reasoning tokens and saves only selected raw logits and public-input identities.

Live capture loads the pinned base plus accepted update100 adapter; fused capture loads only the completed,
reload-verified candidate, with hashes checked before and after capture (`60–85`, `185–190`, `241–244`). Each
process loads one model and clears model references/cache on exit (`253–257`). Separate exclusive processes
and root GPU coordination remain operational requirements, as documented.

Resource checks run before loading, after parameter evaluation before cache clearing, before forwards and
after logit/finite evaluation. The copied guards enforce the observed14GiB budget, normal initial pressure,
sustained-warning/critical-pressure stop,512MiB added swap,20GiB free SSD and600-second boundary deadline.
Their stated limitation concerning in-flight kernels is accurate.

New outputs use exclusive creation; capture paths exclude model/adapter/data overlap. Resume checks identity
and raw hashes. Comparison uses latest attempts, requires completed captures, exact input/position alignment,
finite matching vocabulary shapes and raw hashes. Centred errors, live-margin disagreements and stable
first-answer KL use corresponding token indices; thresholds remain explicit engineering screens, not identity
or answer-quality claims (`265–348`).

**Eight CPU checks passed**, including confident flips, common offsets, nonfinite values, immutable writes and
failed/orphaned latest attempts. No GPU/model loading, API calls, fusion, original-input edits, Git operations or
learner writes occurred. Actual numeric parity and resource behaviour remain pending execution.
