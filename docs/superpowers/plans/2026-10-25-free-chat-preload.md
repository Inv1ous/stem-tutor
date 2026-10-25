# Free-chat preload repair

The Home menu's **Ask the tutor anything** opens `ChatScreen`, separate from the session's Ask modal. Fresh chat
already preloaded, but its reset worker ran concurrently with preparation. Pending native OCR cleanup delayed the
local reset and invalidated a preload against the old conversation. Settings suspension also cancelled preparation
without restarting it on return.

Keep the fix in `ChatScreen`: sequence initial reset before preparation, wait for that reset on an early local Send,
guard preparation after leaving, and restore the selected Ask preload when resuming. Preserve conversation guards,
cloud behavior, model settings, existing local readiness, and terminal-only activity. No new settings or timers.

- [x] Reproduce through the actual Home menu with an offline transport and delayed native cleanup.
- [x] Observe five failing lifecycle regressions and six passing baseline/isolation cases before changing production.
- [x] Add reset/preparation ordering, local early-Send coordination, and resume preparation.
- [x] Run focused and full regression gates; obtain independent review; record results.

## Review evidence

Independent review reproduced shared-reset cancellation when a second exclusive reply cancelled an early first
reply. The direct Worker.wait propagated cancellation to setup and could terminate the app. A new two-Send test and
the early-Send departure test failed before the correction. Replies now await a screen-owned completion event;
cancelling a waiter leaves setup alone. Setup always signals completion, and a reply verifies successful reset and
continued screen membership before generation. No model settings or provider controls change.

## Verification

- Focused free-chat, progress, session composer and provider gate: **46 passed**. Thirteen new free-chat cases cover
  the three original local selections, delayed OCR reset, early/repeated Send, departure, Settings cancel/model Save,
  and cloud/AI-off isolation.
- Original offline race probe now shows OCR cleanup finishing before generation-1 preload, with a successful result.
  Original Settings probe shows cancelled preparation followed by a new chat-owned preload on return.
- Full command: `PYTHONPATH=tests/app .venv/bin/python -m pytest tests --import-mode=importlib -n 4 --dist=loadscope -q`.
  Result: **3,464 passed, 28 existing warnings in 134.96 seconds**. Compilation and whitespace checks pass.
- Only the free-chat screen, focused regression file, changelog and this plan changed for this repair. Previous
  uncommitted work is preserved. No cloud client/model settings changes, live inference, downloads, commits or pushes.
