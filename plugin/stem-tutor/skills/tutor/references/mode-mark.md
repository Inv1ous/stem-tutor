# Long questions and handwritten working

Goal: exam-style marking of iPad working. The learner self-marks first against the scheme (a proven learning gain in itself); the `marker` agent audits. Completion: every open structured question is answered through `answer` with agreed points, and its file is archived with `inbox done`.

1. `session start --mode long` (add `--kcs <ids>` for chosen topics). `next` gives a structured question: show the stem and say "Do it on the iPad with full working. Export it as a PDF named `<n>.pdf` into STEM Tutor/Inbox, then tell me." End the turn with the line: "Waiting for your working (<n>.pdf)."
2. When they say it is done, run `inbox`. A file under `syncing` is still arriving from iCloud: wait a moment and run `inbox` once more; if it is still syncing, ask them to open the Inbox folder in Finder.
3. `scheme <n>` → show the points as a numbered list. They self-mark: AskUserQuestion multi-select of the points (four per question; split across two questions when there are more). Hold their selection.
4. Dispatch the `marker` agent with: the file path, the stem, the scheme points, and their self-marked points. In remote Cowork the PDF is on the learner's computer: first copy it into this container with `device_stage_files` (path: the STEM Tutor folder's `Inbox/<file>`) and give the marker the staged path.
5. Reconcile using the marker's JSON:
   - it agrees → keep the point as marked;
   - it disagrees with `confidence` ≥ 0.8 → quote that line of their working and the scheme point, ask for their view, then decide;
   - it disagrees with lower confidence → their self-mark stands.
6. `answer "<n> pts=<final points>"`, then feedback focused on lost marks: which scheme point, and what the working lacked.
7. `inbox done Inbox/<file>`.

Handwritten work that is not an open question (school homework, a worksheet): help them self-assess against its own mark scheme and give hints rather than finished answers for anything they will hand in. Nothing is logged for it.
