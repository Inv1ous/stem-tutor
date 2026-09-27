# After a video, lesson or lecture

Goal: find what did not land, repair it, and schedule it. Watching feels like learning; the brain dump and unassisted items show what actually stuck. Completion: the diagnose session has ended with every mapped KC either secure or repaired.

1. Ask for the video title or link and which course topic it was for, in one message. For a YouTube link, fetch the title: `curl -s "https://www.youtube.com/oembed?url=<link>&format=json"`.
2. Brain dump, closed book. Say: "Without looking back, type everything you remember: ideas, equations, examples, anything. Two or three minutes; messy is fine." Wait for it. Correct nothing yet.
3. Map it, passing the dump verbatim on stdin:
   ```
   python3 "${CLAUDE_SKILL_DIR}/scripts/tutor.py" diagnose map --title "<title>" <<'DUMP'
   <their brain dump>
   DUMP
   ```
4. Fewer than 3 `kcs` → ask them to paste the transcript into `STEM Tutor/Inbox/transcript.md` (YouTube: … → Show transcript → copy all), then dispatch the `digest` agent with that path and the scripts folder path, and merge its KC ids.
5. Show the KC titles (up to 6) and confirm them with AskUserQuestion (multi-select; add an option "All of these"). Keep any echoed `misconceptions` to yourself: the diagnostic tests them.
6. `session start --mode diagnose --kcs <ids>` and run the normal loop.
7. The first time `next` returns block `exit`, pause for a teach-back before asking it: they explain the main repaired idea in two or three sentences, as if to a friend; correct it precisely. Then ask the exit ticket.
8. Close as usual.
