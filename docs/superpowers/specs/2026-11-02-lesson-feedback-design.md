# Learn a topic processing feedback

The learner reports that lesson actions feel unresponsive and requests visible feedback that inputs are being processed. Existing local-model progress is not shown for cloud requests. Synchronous lesson transitions also need a rendered acknowledgement before their work starts.

Reuse the terminal app style: one compact spinner and descriptive status beside the lesson controls, visible even with answer-only enabled. Acknowledge accepted lesson inputs before running the action. Show elapsed time for pending requests, and name the selection/writing stage without claiming measured server progress. Block duplicate submissions while processing; preserve the current draft and selection. Clear activity after success, failure, cancellation or leaving. Do not mirror activity into learner notes, change scoring, advance lessons for a conversation, weaken answer guards or add a dashboard/provider request.

Approaches considered: transient notifications disappear during long requests; replacing the whole panel loses context and risks drafts. A compact status beside existing controls preserves context and works for synchronous and asynchronous actions. This is the implementation choice within the user's requested change and standing instruction to proceed without questions.

Acceptance: delayed cloud and local lesson requests visibly acknowledge input; buttons and Enter cannot repeat pending work; stages and elapsed time remain honest; synchronous transitions paint an acknowledgement before work; cancellation/failure release controls; later activities are not overwritten; layouts fit 60/80/100-column terminals. Use fake providers and disposable vaults. Review this feature separately from earlier uncommitted fixes.
