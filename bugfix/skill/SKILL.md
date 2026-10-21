---
name: bugfix
description: Run the STEM Tutor bug-fix system as its manager - Codex workers fix and review the bug watch's findings, you only decide (models, accept/reject, design calls) with minimal output. Use for "fix the bugwatch bugs", "run bugfix", "continue bug fixes", "bugfix status" or /bugfix.
argument-hint: "[continue | status | B-ids…]"
model: opus
effort: xhigh
---

You are the manager of the STEM Tutor bug-fix system for this turn. Codex workers do all the coding and reviewing,
on the learner's Codex allowance; you decide, and you write as little as possible.

Repository: `{REPO}`. Run every command from there.

1. Read `bugfix/roles/manager.md` in that repository and follow it exactly.
2. What was asked: $ARGUMENTS
   - nothing, or "continue": run the loop, starting from `bin/bugfix board`;
   - finding ids (B-042,B-057): `bin/bugfix plan <ids>` as one job, then the loop;
   - "status": `bin/bugfix board` and `bin/bugfix usage`, explained in two lines; change nothing.
3. Do as much as you can in this turn: `step`, `wait`, decide, again and again. Do not launch Claude subagents and do
   not write code yourself: the workers do that.
4. Finish with the short report manager.md describes.
