# Written faded check: implementation boundary

## Current status (29 October)

The entries below record successive design and review decisions; they are not all current implementation descriptions. Written faded checks remain blocked from publication. The experimental lesson paths now use the shared converter, require explicit attempt confirmation before review, and include the written-check review in the foundry gate. The P2 draft retains the disproof and factorisation task, with a separately reviewed rubric. The candidate is not installed.

For unavailable retries, the experimental cancellation path now persists an intent and uses the locked draft operation before closing the question. A retry is available after a transient failure. Conflicting versions can be archived, but there is no user-facing choice or complete conflict resolution yet; the draft retrieval prototype is not connected to the interface. Concurrent disclosure and interruption paths still need review. The older structured-question cancellation tests remain expected failures and do not establish the behavior of this written-check path.

Focused tests cover the actual P2 candidate and an interface confirmation flow, plus generic skip, retry and restart cases. They do not prove universal protection against answer disclosure, live marking accuracy, or release readiness. Do not remove the publication block on this evidence alone.

The preserved P2 `we2` asks for an admissible counterexample and factorisation, but its legacy answer is numeric. Converting the prompt to arithmetic alone loses the independent reasoning check. Keep that original demand and make its response type match it.

Add an explicit written faded variant using the existing short-answer judgment flow, while keeping legacy numeric/expression inference when no kind is specified. Validate required fields and reject mixed or unknown shapes; preserve marks and the existing attempt, skip, restart and answer-disclosure guards. Both guided and older lesson execution paths need the same conversion.

Automatic blind comparison currently assumes numeric/expression answers. Written faded prompts must be exported without answers for separate independent solving and review; bind that review to the exact prompt, rubric, model answer and worked-example context, and make the refine gate fail closed if missing or stale. Do not treat keyword matches or an AI verdict as proof of correctness. Recheck the existing answer-protection path before exposing any rubric or worked solution.

Verify legacy numeric and expression examples, the written example, incomplete and invalid schemas, redaction, attempt and skip/restart behavior, separate blind-review freshness and both lesson paths. Then restore the P2 task, review it independently and rerun preservation and publication gates. The separate review identified this direction; it has not yet been implemented or approved for release.

Independent code review found that the foundry release path does not yet require this review, and that legacy learn-mode skip handling would disclose a written faded rubric without an attempt. The UI's reviewed-marking branch also does not cover this phase. Runtime integration has been removed and pack validation explicitly blocks publication of this variant until those paths are fixed. The lesson test is marked as an expected failure until then. The isolated skip/restart test exercises the ordinary lesson guard only; it is not proof for legacy learn mode.

The lesson conversion is reconnected for development after adding the scoped skip guard, foundry review gate and manual marking path. A UI test injects a written faded example into a disposable in-memory pack and verifies that the engine presents its stem and withholds its model solution until an attempt; this is not an installed-pack or foundry-sign test. Pack validation still blocks publication, and review identities remain attestations. Do not release this variant yet.

A further independent review identified that exact non-attempt phrases cannot establish whether arbitrary prose is a real attempt. The explicitly tested phrases are guarded, and a bare “no” remains a possible answer, but automatic model-answer display remains unsafe for unrecognised declarations of uncertainty. Keep the publication block until the workflow handles that ambiguity; phrase matching alone is not evidence of the requested no-disclosure guarantee.

The unavailable-retry cancellation needs the same durable recovery work described in `GUARD_DRAFT_RECOVERY.md`: persist an operation intent before a locked, idempotent store update, preserve displaced drafts, and only close the retry after that update. Replaying must occur before unconditional draft synchronisation; guard conflicts leave the working open. The existing structured cancellation and a bare compare-and-swap do not establish these guarantees. An expected-failure test records the desired skip behavior; this remains unfinished.
