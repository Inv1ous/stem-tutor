# Shortcuts & Elegant Methods — a course that is not the syllabus

Goal: cut slips and wasted time on long questions and complex ideas by teaching the shortcut that fits (trigger → shortcut →
check), then keeping it alive with its own spaced recall. Entirely separate from syllabus chapters and from the syllabus
spaced recall: its own settings, events, state and review queue (like Challenge mode, `docs`/`tutorlib/challenge.py`).

## Content

- **Source entries** — ranked notes in `sources/shortcuts/base/<spec>.md` (hand-made, 722 entries over 9702, 9701, P1, P2,
  FP1, M1, S1) and `sources/shortcuts/research/<name>.md` (written by Codex research workers). Entry =
  `**Title** \`N/10\`. body`. `build/shortcuts.py parse` writes `build/out/shortcuts/<spec>.json`: a list of
  `{id, spec, section, topic, title, score, origin, body, source?}`; id `SEM-<spec>-<slug>` is stable.
- **Lessons** — generated, optional per entry, `build/out/shortcuts/lessons/<spec>.json`: `{entry id: lesson}`. Every entry
  is teachable without one (the course shows the source entry itself and derives plain recall cards); a generated lesson
  enriches it. Lesson object (all strings may hold `$LaTeX$`):

```
{ "id": "SEM-…",
  "hook":    "the pain: what the long way costs or where it slips",
  "when":    "how to recognise the trigger",
  "idea":    "the shortcut, stated plainly",
  "why":     "why it works, and the condition under which it holds",
  "steps":   ["2 to 5 short steps"],
  "worked":  {"question": "…", "long": "the long way, briefly", "short": "the shortcut way", "saving": "what it saves / the slip it avoids"},
  "pitfalls":["1 to 3 ways it goes wrong"],
  "check":   "a quick way to verify the answer",
  "practice":[{"kind": "numeric|mcq|short", "stem": "…", "options": {"A": "…"}  /* mcq only */, "answer": "…",
               "hints": ["h1","h2","h3"], "explanation": "…", "shortcut_use": "which step uses the shortcut"}],
  "recall":  [{"q": "…", "a": "…"}]  /* 2 to 3 flash questions answerable in a sentence */ }
```

## Publishing to the vault

`build/publish.py` also copies `build/out/shortcuts/` to `<vault>/.tutor/shortcuts/course/` (entries + lessons). Never touches
learner state.

## Learner state (separate from the syllabus)

- Settings `<vault>/.tutor/shortcuts/settings.json`: `min_score` (default 8), `max_score` (10), `specs` ([] = all), `levels`
  ([] = both; "AS"/"A"), `sections` (substring filters), `origins` ([] = all; "base"/"research"), `order` ("score" | "section"),
  `new_per_day` (5), `lessons_only` (false), `recall_scope` ("learned" = only what the learner has been taught).
- Events `<vault>/.tutor/shortcuts/events.jsonl` (append-only): `{"t", "type": "learn"|"recall"|"practice", "id", "rating"
  (1 again, 2 hard, 3 good, 4 easy) , "mode"}`. State is a fold of the events (FSRS via py-fsrs, one card per entry), cached at
  `<vault>/.tutor/shortcuts/state.json`, refolded if the log is ahead. The syllabus model (`model.apply`) never sees these.

## Engine API (`tutorlib/shortcuts.py`)

`DEFAULT_CONFIG`, `normalise_config(d)`, `load_config(vault)`, `save_config(vault, cfg)`, `level_of(entry)`,
`select(entries, cfg)` (the filter used everywhere; `build/shortcuts.py` imports it), `load_entries(vault)` (entries each with a
`lesson` key, None when absent), and `Course(vault)` with `.cfg`, `.entries()` (filtered, ordered), `.pool()` (all, unfiltered),
`.next_lessons(n, now=None)` (not yet learned, filtered, `new_per_day` minus today's learns by default), `.due(now=None)` (ids of
learned entries whose FSRS card is due, honouring `recall_scope` and the filters), `.record(kind, entry_id, rating, mode="", now=None)`,
`.recall_cards(entry)` (the lesson's `recall` list, or derived: Q "What is the shortcut for: <title>?" / A the body), `.stats()`
→ `{"selected": n, "learned": n, "due": n, "new_today": n, "lessons": n}`.

## App

Home menu gains "shortcuts" (learn new ones, with practice) and "shortcut recall" (the separate due queue) and a settings
panel for the filters above. `app/tutor_app/shortcuts_screen.py`, same shape as `challenge_screen.py`.

## Generation

`foundry/shortcuts_gen.py` writes lessons in batches with Codex (cheapest tier), best-ranked entries first, resumable, stopping
at a Codex weekly percentage; a second pass checks a sample of practice answers with a different model.
