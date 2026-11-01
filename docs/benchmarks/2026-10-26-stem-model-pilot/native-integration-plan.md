# Native integration plan

CPU/source inspection only, 27 October 2026. No source changes, package installation, Git writes or model/GPU jobs. Ollama 0.40.11 source compatibility with mixed precision is established; the fused checkpoint, native import and inference remain unproved. Follow the promotion gates in `docs/superpowers/specs/2026-10-26-stem-model-pilot-design.md:67`.

## Smallest integration

1. After fusion/reload/native gates pass, add `ollama:stem-tutor-qwen35:pilot` to `LOCAL_MODELS` with an explicitly experimental, text-only label, and to `TEXT_MODELS` (`app/tutor_app/local_models.py:13`, `:33`). Existing dictionary comprehensions supply keep-alive/context defaults (`:41`, `:45`); measure their suitability. Manifest discovery already recognises `manifests-v2/ollama.com/library/stem-tutor-qwen35/pilot` (`:109`). Do not route this alias through the separate GPT-OSS worker.
2. Preserve boolean thinking: `thinking_value(..., False/True)` already yields native Off/On for this added model (`local_models.py:71`). Leave `thinking_levels` empty and `always_thinks` false. This avoids inventing low/medium/high. Existing Settings switch and boolean persistence work (`screens.py:2150`, `:2156`; `config.py:95`). Optional alias-specific tooltip can say “Fast = Off; Deep = On”; no settings migration is needed.
3. A selectable experimental model needs format/inference/memory gates; **presets additionally need useful held-out improvement without critical regressions**. Only then append separate experimental Fast/Deep entries to `PRESETS` (`presets.py:25`), all three tasks using this alias with `False`/`True`. Preserve every existing preset, default and saved selection. Availability and explicit Apply/Save already gate presets (`presets.py:58`; `screens.py:2199`).
4. Reuse text-only OCR/helper and ownership flow (`tutor_ai.py:148`, `:179`, `:324`); retain `macos:vision` default. Do not advertise native vision. Preload already demands empty content/thinking and `done_reason=load` (`local_ai.py:355`), and reports separate load/thinking/first-token/wall timing (`:444`).

## Conditional sampler change

Do nothing until development evidence approves a sampler. Add one exact-alias resolver in `local_models.py`; merge its mode-specific options in `LocalAI._with_context` (`local_ai.py:70`) without altering other payloads. Keep Fast/Deep separate. Preserve explicit penalty span (`repeat_last_n`), neutral repetition/frequency and resolved seed/bounds in receipts. Add the entire resolved sampler to one-shot `reply_key` inputs (`tutor_ai.py:339`; `local_reuse.py:12`), conversation identity (`local_ai.py:512`) and performance. Native/Python sampling orders differ; identical scalar options do not prove parity. No global Modelfile sampler can represent both modes.

## Gates before exposure

After exclusive GPU ownership, fuse the accepted checkpoint with existing utility (`stem_training_fuse.py:178`), verify preservation/reload receipt, then create a new Modelfile containing `FROM .` beside the fused files. Use the app’s loopback server configured with the SSD root (`local_ai.py:139`). From the fused directory:

```sh
OLLAMA_MODELS='/Volumes/External SSD TB4/LocalAI' ollama create stem-tutor-qwen35:pilot -f Modelfile
ollama show stem-tutor-qwen35:pilot --modelfile
```

Use no `--force` or requantisation. Inspect the actual manifest for `runner: mlx`; compare tokenizer/template/thought/stop assets and licence against fusion receipt.

Prepare distinct native Off/On request JSON files using **actual complete** `document_schema(False/True)` (`chat_output.py:30`) and `local_judge_schema(points)` (`prompts.py:147`), plus real production system/user roles. Example execution, repeated per mode/schema:

```sh
curl --fail --max-time 300 http://127.0.0.1:11434/api/chat --json @native-fast-document-request.json
```

Discard hidden `message.thinking` text immediately; retain sanitised public-final events, requested options, completion and memory only. Require Fast without hidden thinking; Deep with genuine thinking followed by complete final content. Thinking-only/token-limit output fails. Exercise all six block kinds, separate speech, exact code/JSON/backslashes, complete definitions/units, negated/omitted marking criteria, OPEN hints, topic/history changes and OCR uncertainty. Validate raw full schemas recursively; `ai.complete` (`ai.py:616`) checks only top-level types. Require `DocumentDecoder.finish` (`chat_output.py:185`), exact criterion order/copying and scientific decisions. Keep unassisted learned-format scores separate from schema-constrained app results. Measure cold/warm/preload latency, cancellation/reload, switching, sustained memory and TUI/Obsidian screenshots.

CPU regression command after implementation:

```sh
PYTHONPATH=tests/app .venv/bin/python -m pytest tests/app/test_model_catalogue.py tests/app/test_local_strengths.py tests/app/test_ai_presets.py tests/app/test_local_chat_wire.py tests/app/test_local_document.py tests/app/test_local_mark_schema.py tests/app/test_local_vision.py tests/app/test_local_chat_preload.py tests/app/test_local_preload_lifecycle.py tests/app/test_local_reuse.py --import-mode=importlib -q
```

Add alias-specific catalogue/Off-On, disconnected discovery, unchanged saved/cloud/preset choices, OCR/preload and custom-only sampler/cache tests to those suites. Rollback removes only the new selection/presets/alias after restoring any explicitly changed task choices.
