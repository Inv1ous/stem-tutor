# Terminal extraction monitor

Run from the workspace root, with Python 3.9 or newer. No packages are required:

```sh
python3 stem-tutor/extraction/monitor.py
```

The screen refreshes every five seconds. Press **Ctrl+C** to exit. This stops only
the monitor. It does not stop or start extraction workers. The script locates the
workspace from its own file location, so an absolute script path works from any
directory too.

```sh
python3 stem-tutor/extraction/monitor.py --interval 10
python3 stem-tutor/extraction/monitor.py --once
python3 stem-tutor/extraction/monitor.py --root /path/to/workspace --run-dir Work/Workers/extraction/all-course-20261101
```

In an interactive terminal the monitor replaces its screen. Redirected output
contains timestamped snapshots without terminal escape codes. Wider terminals
show course names; narrower terminals use course codes. If the screen is short,
the live view shows the first rows and a notice. Use `--once` to retain a complete,
scrollable snapshot, or enlarge the terminal to see the details below the table.

## Current practice comes first

The first table reads the immutable release selected by
`STEM Tutor/.tutor/source_practice/CURRENT` through `tutorlib.source_practice.Collection`
and its digest-checking `AssetLibrary`. It lists all fourteen courses, including
zero counts, before the older page baseline. Each refresh opens a fresh collection,
so publishing a new CURRENT release appears automatically. Missing, invalid, or
digest-mismatched releases show **unavailable**, never a successful zero count.

**Items** count source-practice entries. **Native** counts entries identified by
their original paper question IDs; **Topical** counts math source occurrences
(`occurrence-` IDs). Topical occurrences can overlap original papers. These counts
are separate from the old teaching-bank questions, parts, and marks below; the
monitor never adds them together. Availability does not establish mastery
certification or whole-PDF completion. Source/course completion totals and ETA
remain unknown.

**Saved current activity** uses the most recent valid `started_at_utc` among
`Work/Workers/extraction/*/run.json` files containing `starting_current` and a
numeric `stop_floor`. It shows that run's saved status, weekly remaining quota,
stop floor, observation age, and start age. This is a saved reading, not a live
account query. An unreadable update can retain a last good JSON value with a
warning. No valid activity file means unavailable; the old continuation budget
and reset-consumed counters are not substituted or changed.

## Older census and page baseline

- **Old baseline Scan %:** inspected pages divided by total inventoried PDF pages, per course.
  Coverage comes from `all-source-progress.json`, the saved full-scope baseline.
  Pages are unioned by course, source ID and source hash. Overlapping occurrences
  do not increase coverage. A course without sources has no percentage.
- **Old baseline Review %:** full-scope independently reviewed pages divided by the same total.
  Later reviews of selected questions do not establish full-page coverage.
- **Usable Q / Parts / Marks:** newly published output that passed the recorded
  applicable learner-route gates, from `continuation-report.json`. Parts count
  assessed records, including single-record whole questions and MCQs. The monitor
  displays the saved census; it does not independently re-audit its evidence.
- **Route wait:** activated whole questions awaiting complete route verification.
  They remain separate from usable output. Registration alone is not teaching approval.
- **Live source states:** current `allsource*/state.json` files, checked every
  refresh. An unfinished worker means a start exists without a recorded finish.
  It does not establish that its PID is still running. Coordinator and native
  code-review agents are outside these source-worker records.

There is no reliable total of unique complete questions yet. Consequently the
monitor does not invent a question-completion percentage or ETA. A 100% scan
means all inventoried pages were inspected, not all questions are usable.

The monitor polls files without writing them, invoking maintenance scripts,
reading learner answers/events/grades or practice attempts, or loading source PDFs
or question media. Current practice advances when CURRENT changes; old output and
page coverage advance when the workflow saves updated censuses. Their timestamps remain visible
even if the monitor itself has just refreshed. Concurrent partial JSON writes
produce a warning and retain the last good value until a valid file is available.
