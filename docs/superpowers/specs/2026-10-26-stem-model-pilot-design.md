# Experimental STEM Tutor model

Date: 26 October 2026. Status: research complete; user requested an experimental fine-tuning attempt and delegated
routine model/optimisation choices. This is a bounded reversible pilot, not a replacement of working tutor models.
The existing structured-output implementation and its verification remain required work.

## Decision and alternatives

Train a small LoRA adapter on a pinned Qwen3.5 4B MLX 4-bit base, then fuse the selected adapter into a separate
native MLX checkpoint. This is a compatible merge of learned changes with their own base. Retain the original base,
adapter and existing models. A small trainable model is a better first experiment for this 24 GiB M4 Air than full
fine-tuning of a large model. Cross-architecture weight mixing and arbitrary topic/weight pruning do not have an
established preservation guarantee and are excluded from this pilot. Text-only loading may omit unused vision
weights; the existing native OCR/helper supplies image observations.

Base: `mlx-community/Qwen3.5-4B-4bit@0e7ffd5c629ef7719d4cbc04069232580bfa9d9c` (about 3.03 GB weights).
Upstream: `Qwen/Qwen3.5-4B@851bf6e806efd8d0a36b00ddf55e13ccb7b8cd0a`, Apache 2.0. Preserve attribution, upstream
LICENSE, snapshot revision/checksums and community-conversion provenance. Use a separate SSD training environment
pinned to MLX 0.32.3 / MLX-LM 0.32.2 / Transformers 5.20.2; do not modify the tutor/GPT-OSS environments.

All weights, adapters, caches, data, checkpoints and receipts live under `/Volumes/External SSD TB4/LocalAI`.
Research/scripts/reports/tests belong in this repository. No cloud training, dataset upload or model publication.
No training job overlaps local inference/benchmark GPU jobs. Originals and saved Claude/ChatGPT selections remain intact.

## Training content and model behaviour

Teach the actual shared semantic document format in the weights: correct block kinds, real paragraph/list boundaries,
canonical mathematics, exact code/JSON and separate speech. The app continues deterministic rendering and schema
validation. Format learning reduces the need for a long formatting prompt; it cannot remove the current question,
mark scheme, syllabus version or learner context needed for accurate assessment.

Use public authored study-pack flashcards/definitions and visible worked solutions, plus carefully verified synthetic
mathematics, units, source-copying, code and marking examples. Include CAIE9701, CAIE9702 and relevant EdexcelIAL
modules, British exam terminology, qualifications, complete requested parts, uncertainty and OPEN-answer protection.
Never use private learner logs, screenshots or hidden model reasoning. Do not use unchecked model outputs as gold.
Record provenance and validation for each example. Exclude malformed or unsupported examples rather than silently
changing scientific meaning. Preserve canonical Markdown/LaTeX/code and source identifiers.

Split by syllabus point and question/algorithm family before augmentation. Training, development and sealed test
sets must be disjoint by those groups; evaluate unseen subject content and formatting combinations. Keep raw-format
adherence, scientific accuracy/mark-point decisions and delivery timing separate.

Qwen3.5 chat templates include a reasoning region even in final-only assistant examples. Use a standalone trainer
wrapper with loss beginning after the rendered `</think>` boundary. Do not teach immediate thinking termination by
naively masking only the prompt. No installed model architecture or package-source patch is required. Native
inference strengths are Fast (Thinking Off) and Deep (Thinking On); advertise no unsupported native intermediate level.

## Bounded pilot

1. Download/verify pinned public snapshot and provenance. Install isolated dependencies with a receipt and `pip check`.
2. Prepare validated train/development/sealed-test JSONL and a reproducible split manifest.
3. Verify base inference and memory with compact/missing-format instructions. Freeze base evaluation before training.
4. Five-update smoke at 512 tokens, batch1, rank8, scale2, learning rate1e-5, last8 decoder MLP gate/up/down projections.
   Check finite loss, real adapter parameter changes, adapter-only save/reload, and memory. Use an explicit conservative
   MLX memory limit and leave OS/application headroom; abort cleanly if it cannot fit.
5. If smoke passes, at most100 updates or one hour, sequence length at most1024, gradient accumulation up to4.
   Record losses, elapsed time, peak memory, dataset hashes and training arguments. Choose checkpoint using development
   data only. Stop earlier when evidence justifies it; do not claim five updates make an expert tutor.
6. Compare base/adapter on sealed tests, including native Off/On, equations, scripts, full definitions, mark-point
   negation/omission traps, coverage, literal code, OPEN hints and topic changes. Repeat representative failures.
7. Fuse into a new directory and evaluate fusion separately. Import under a new experimental Ollama alias without
   `--force` or additional quantisation. Verify actual `runner: mlx`, tokenizer/template, Off/On, preload and screenshots.
   Native import compatibility is unproven until tested; do not claim GGUF export for this architecture.

## Promotion and rollback

A model is a selectable experimental option only after reload/inference/format/memory checks pass. A recommended
preset additionally needs evidence of useful held-out improvement without critical regressions in marking, maths,
exact source preservation or OPEN protection. If the adapter fails these gates, retain the measured experiment and
keep the established models as defaults; report the failure plainly. Do not substitute lower loss for correctness.

Native Fast/Deep controls must perform actual Off/On generation and report measured latency, including preloading.
Keep existing presets and cloud routing untouched. An experimental model may use a shorter format reminder only
when held-out checks show its learned contract is reliable; schema validation and deterministic rendering remain.
No assertion of perfect marks, guaranteed speed or elimination of scientific context follows from fine-tuning.

See [primary-source research](../../research/2026-10-26-stem-model-specialisation.md).
