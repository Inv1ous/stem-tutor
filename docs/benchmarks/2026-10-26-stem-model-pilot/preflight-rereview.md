# STEM pilot preflight re-review

26 October 2026. Scope: the two findings in `preflight-review.md`, their fixes in
`stem_training.py`, related CPU tests and the appended runtime-report corrections.
No GPU/model calls, dependency changes, broad suite, data modifications or source
edits. The coordinator's base compatibility probe remains the exclusive GPU user.

**Verdict: both findings addressed; no new serious defect identified in these fixes.**
This removes the two code-review objections to the bounded five-update smoke;
the coordinator still owns the base-probe outcome and exclusive execution GO.

| Finding | Verdict | Evidence |
| --- | --- | --- |
| P1: allocation guideline alone does not enforce the budget | ADDRESSED | `MlxMemoryMonitor` checks both active and historical peak allocation. Checks follow model loading, evaluated initialization, backward pass, finite checks, optimizer evaluation, each development forward and reload, and precede checkpoint/publication/next operation. Default observed budget is 14 GiB; the 87.5% allocation hint is 12.25 GiB. |
| P2: final development deterioration reports completion and publishes the worse candidate | ADDRESSED | Final validation now compares to best development loss, marks the run stopped/rejected on deterioration, and saves a separately named rejected candidate. Interval candidates are pending until accepted; canonical publication retains the latest development-accepted checkpoint. |

The report now accurately states that the memory observation is cooperative and
cannot prevent an in-flight allocation overshoot or account for all OS/process
memory. System pressure, swap and disk guards remain in place. An over-budget
historical peak prevents further model work/publication; recovery retains the last
already saved finite adapter rather than attempting an over-budget checkpoint.

Verification: **48 trainer CPU tests passed** in 0.16 seconds with bytecode and
pytest cache writes disabled. The new cases cover active or peak observations of
17 GiB against 16 GiB, prevention of the next training step, and initial/final
development losses of 1.0/2.0. CLI and dataclass defaults both resolve to 14 GiB.

Additional independent CPU loop probes checked checkpoint publication:

- Five updates, development 1.0 → 2.0: stopped/rejected, canonical remains update 0.
- Five updates, 1.0 → 0.9: completed/accepted, canonical update 5.
- Thirty updates, 1.0 → 0.9 → 1.1: stopped/rejected, canonical update 25.
- One hundred updates, steadily improving development: accepted canonical update 100.
- One hundred updates, final deterioration after accepted update 75: stopped/rejected,
  canonical remains update 75.

No loaded-model training, real gradient/reload behavior or quality outcome was
established by this re-review. Those remain smoke and subsequent evaluation gates.
