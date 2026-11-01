# Closeout fix report

Addressed the sole Standards P2: the evaluator import-safety assertion incorrectly required `mlx.core` to be absent from the shared pytest process, although the preceding optional training proof may legitimately import it. Spec review reported no findings.

Only `tests/app/test_stem_training_eval.py` changed, alongside this report. The test now imports and reloads the evaluator in a clean `-I -S` Python subprocess. An import blocker rejects both `mlx` and `mlx_lm` families, records attempted imports even if swallowed, and checks that no MLX modules were added. Parametrized coverage includes a pre-existing parent `mlx.core` placeholder; `monkeypatch.context()` restores its previous entry, with identity assertions before and after restoration.

RED, after adding the placeholder reproduction while retaining the original assertion:

```sh
PYTHONPATH=tests/app .venv/bin/python -m pytest tests/app/test_stem_training_eval.py -k generation_import_is_cpu_safe --import-mode=importlib -q
```

Exit 1: **1 failed, 1 passed, 27 deselected in 0.21s**. Only the preloaded placeholder case failed, at the original global-absence assertion.

GREEN, after replacing that assertion with the subprocess proof:

```sh
PYTHONPATH=tests/app .venv/bin/python -m pytest tests/app/test_stem_training_eval.py -k generation_import_is_cpu_safe --import-mode=importlib -q
```

Exit 0: **2 passed, 27 deselected in 0.20s**.

Covering CPU suites:

```sh
PYTHONPATH=tests/app .venv/bin/python -m pytest tests/app/test_stem_training.py tests/app/test_stem_training_data.py tests/app/test_stem_training_eval.py tests/app/test_stem_training_protocol.py tests/app/test_stem_training_fuse.py --import-mode=importlib -q
```

Exit 0: **156 passed, 1 skipped in 3.68s**. The optional native MLX proof remains skipped in the main virtual environment. No real MLX runtime, model, GPU or external-provider calls ran. Production APIs and behavior, packages, source weights/configuration and learner data were unchanged. No Git metadata was mutated.

The scoped before/after diff is `/tmp/stem-closeout-fix.diff`; its whitespace check passed. The coordinator retains ownership of the requested single scoped rereview and any full-suite rerun.
