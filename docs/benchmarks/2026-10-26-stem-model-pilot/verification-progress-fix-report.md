# Verification progress fixture fix

The canonical four-worker suite exposed one fixture failure: `test_local_marking_json_progress_never_changes_the_submitted_work_or_notes`. `LocalActivity` initially displays preparing, then reads `progress_for` every 0.2 seconds. This test replaced `one_shot` and warming without supplying progress, so the first refresh correctly displayed waiting. Its 50 ms pause could cross that timer boundary under load.

Only that case in `tests/app/test_local_progress.py` changed. The fake backend now explicitly reports `{"phase": "preparing"}`. An event signals the actual progress read; the assertion waits for that event and a UI refresh. This exercises the timer path without depending on the initial frame, increasing sleeps, or retrying assertions. All existing marking-label, unchanged `Now.md`, submitted-answer preservation and progress-removal assertions remain intact.

Deterministic RED wrapped the original `progress_for` with the same event, ensuring the timer refresh occurred before the existing assertion. Exact focused command, used for both RED and GREEN:

```sh
PYTHONPATH=tests/app .venv/bin/python -m pytest tests/app/test_local_progress.py::test_local_marking_json_progress_never_changes_the_submitted_work_or_notes --import-mode=importlib -q
```

RED: exit 1, **1 failed in 1.91s**, at the missing preparing label after the timer refresh. GREEN with explicit fake progress: exit 0, **1 passed in 4.26s**.

Covering progress and preload CPU fake suites, with the canonical worker count:

```sh
PYTHONPATH=tests/app .venv/bin/python -m pytest tests/app/test_local_progress.py tests/app/test_local_chat_preload.py tests/app/test_local_preload_lifecycle.py --import-mode=importlib -n 4 -q
```

Exit 0: **33 passed in 7.24s**.

No production APIs/behavior, GPU/model/runtime calls, learner data, packages or Git metadata changed. SHA-256 verification confirms `/tmp/structured-full-suite-4.log`, the cleared evaluator import-safety test and `/tmp/stem-closeout-fix.diff` are unchanged. This test fix and report are captured in `/tmp/stem-progress-verification-fix.diff`, with no whitespace errors. The coordinator owns the scoped rereview and canonical full-suite rerun.
