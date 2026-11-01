# Decisions and limits

These decisions preserve the worktree's implementation ledger for review. No Git staging, commits, push, tag move,
cloud training, model publication or private learner-data change was performed.

| Decision, in order | Reason | Cost if wrong |
| --- | --- | --- |
| Continue in the current checkout on `main`, with no Git writes. | The task extends the user's current program and its uncommitted work. | Less isolation; a scoped path list and retained diff are needed to keep unrelated work out of the commit. |
| Use one decoder/wire document across providers; commit history only after final validation. | Layout and replay need one contract. | A shared bug affects several providers, so direct legacy constructors and provider-specific regression checks remain necessary. |
| Keep visual normalization at its existing boundary and assign shared files to one writer at a time. | Avoid conflicting formatter changes. | A missed caller could retain an older style; the provider/display matrix checks those routes. |
| Make document mode additive for direct clients and default it on in `TutorAI`. | Preserve existing direct API contracts while updating the app. | Incorrect routing could change one-shot machine data; isolation and schema tests cover that boundary. |
| Keep shared teaching policy in `ai.py` and source selection in its own module. | Separate response policy from bounded evidence lookup. | Incorrect scope could bias answers; source provenance, subject and OPEN tests remain required. |
| Wait for each active baseline/model job to finish before another GPU job. | Avoid memory contention and duplicated trials after a tool yields. | Longer wall time; an incorrectly identified job could stall the queue. Handles and terminal status were retained. |
| Retain both original questions and expanded source context. | Source augmentation changes the actual request. | Incomplete receipts would weaken comparisons; prompt hashes and expanded requests are preserved. |
| Review accepted untracked source as well as tracked diffs. | New helpers and tests are part of the implementation. | A mistaken scope could include unrelated files; release staging is explicitly enumerated. |
| Store model/data/cache artifacts on the SSD and preserve originals; use no cloud training or uploads. | Follow the requested location and make rollback possible. | Additional SSD space and local runtime maintenance are required. |
| Treat native Off/On as Fast/Deep; invent no intermediate reasoning level. | Qwen's tested native interface has two modes. | The user receives fewer controls than a fabricated slider would suggest. |
| Keep the original model matrix authoritative and never restart a live job because a polling call yields. | Avoid duplicated GPU work and overwritten evidence. | A failed run needs a separately identified retry rather than replacing its first result. |
| Retain presence 1.5 for the experimental Fast/Deep reference. | Zero improved one document but worsened delivery and did not recover marking. | The one-seed, correlated development test may miss another useful setting; it does not establish a universal optimum. |
| Permit three vision-processor omissions and native-save metadata differences only in the text-only fusion comparison. | The removed files contain image/video processing configuration; text assets and resolved token identities match. | No vision preservation claim is possible. Exact text/config exceptions, source contents and hashes are retained. |
| Attempt the marking and genuine Deep controls even after the small Fast diagnosis fails. | These are independent required checks. | Extra bounded GPU time; the seven-request cap and all failures remain visible. |
| Test document-only native grammar omission for the exact custom alias, keeping full instructions and host validation. | A matched development pair reproduced a grammar/prompt interaction. | Six successful documents cannot establish general reliability; this was confined to the experiment. |
| Stop without promoting the custom model or its strengths. | Content fidelity and Deep delivery failed the documented gates. | The user cannot select this prototype in the tutor; the preserved model, adapters and reports support a future independently validated attempt. |
| Preserve the current workspace and provide scoped push commands instead of integrating it automatically. | The user requested the command and the work has not been committed. | The user must review and commit the changes; deleting the scratch ledger now would lose uncommitted evidence. |

The research outcome does not change existing provider selections. The shared formatting change is intentional
across providers; local-only runtime experiments do not modify saved Claude/ChatGPT settings.
