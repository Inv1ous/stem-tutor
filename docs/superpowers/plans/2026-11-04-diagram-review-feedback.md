# Authenticated feedback for unfocused repairs implementation plan

> For agentic workers: use superpowers:subagent-driven-development. User forbids commits and destructive cleanup.

**Goal:** A manager-launched diagram review finding reaches the next maker repair instead of causing a paid unchanged copy.
**Architecture:** Extend the existing authenticated feedback packet seam to source-page jobs with no selected_item_scope. Keep focused/native scope binding unchanged, same packet schema, unchanged real maker/reviewer lifecycle.
**Tech Stack:** Existing Python manager and pytest, no dependencies.
**Spec:** User extraction continuation authorization; actual red-capable probe in Work/Workers/extraction/resume-pmt-20261104/diagram-feedback-red.txt. Read Work/Workers/extraction/pmt-20261104-FP2-notes-complex-p11-15 source/review/prompt/state read-only for the concrete case.

## Global Constraints

Use current dirty checkout, preserve unrelated work. No commits/push, actual job/candidate/source/Library/learner mutations, guard resets or provider launches by implementer/reviewers. Tests run only disposable vaults and fake providers, shared inputs via tests/library_assets.py. Preserve existing focused/native feedback, guard counts, successful-stage semantics, source/graph/candidate/review hashes and blind-review isolation. Coordinator owns real state and paid launches. No extra reset/purchases;20%weekly floor. Changes preserve previous candidates and feedback records; a pending finding is not approval.

## Design and alternatives

Chosen: reuse authenticated packet logic and source/page/graph/candidate bindings for actual unfocused independent review attempts. Rejected: unbound freeform notes (no provenance), manual actual-candidate edits (lose missing-stage manager provenance), repeating unchanged review/extraction (waste and guard risk). This choice is delegated by user.

## Review Focus

Actual nonselected diagram and ordinary question reviews must forward exact authenticated findings. Forged/edited/stale review or source/graph/candidate changes must fail closed. Legacy manually placed reviews lacking attempt evidence retain existing no-packet behavior and confer no approval. A pass never becomes repair feedback. Reviewer prompts remain blind; consumed feedback cannot replay; existing focused completion history stays valid.

### Task 1: Broaden exact feedback binding to authenticated page scopes

**Files:** Modify extraction/extract.py, tests/test_extraction_repair_feedback.py; extraction/README.md only if contract clarification needed.
**Interface:** Keep _review_repair_input(state), _review_scope_binding(state), run(...retry='extract') call interfaces and packet schema. For unfocused scope, authenticate against actual review output_sha256 or matching recorded independent pending failure; freeze exact course/scope/source page inventory/current graph and reviewed candidate bytes. Do not weaken focused/native checks. Call prior selected-scope completion logic only when such scope exists.

- [ ] Reproduce actual helper returning None for authenticated diagram pending findings without modifying actual job. The existing red probe already failed and root cause is the early unfocused return and selected-scope-only binding helper.
- [ ] Add meaningful fake-provider integration regression for nonselected diagrams (and ordinary questions): real manager review returns pending; next maker contract contains exactly its source-bound findings and candidate binding. Run RED before fix. Add stale source/graph, edited finding/candidate and unauthenticated no-packet cases at the same interface. Preserve legacy focused tests.
- [ ] Make narrow manager change, retaining legacy no-authentication behavior without forwarding untrusted review text, all existing pass/replay/corruption/guards and blind reviewer checks.
- [ ] Run tests/test_extraction_repair_feedback.py and necessary directly affected tests only. Use no broad corpus/suite repeat. Demonstrate direct actual-job read-only _review_repair_input now yields the saved exact source error (no run/packet write).
- [ ] Write report with RED/GREEN commands/results and code hashes, and a snapshot diff; keep uncommitted. Coordinator will request separate independent Spec/Standards review before a real repair launch.
