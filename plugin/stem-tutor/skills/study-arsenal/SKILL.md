---
name: study-arsenal
description: >-
  Study-mode replacement for full-arsenal: routes any study, revision or exam-preparation request to the
  right skill and output, with Pro-plan token rules. Use for notes, revision PDFs, flashcards, quizzes,
  study plans, "what should I study", homework help and exam technique, and whenever full-arsenal would
  otherwise run on a study request.
---

# Study arsenal

A pre-composed stack for study. It replaces the general full-arsenal survey on study requests, so routing costs one lookup instead of a full inventory pass.

## Route

| Request | Skill | Output |
|---|---|---|
| study session, "what now", learn a syllabus topic, quiz, review, after a video, mark iPad working, past paper, progress | `tutor` | chat + notes in the STEM Tutor folder |
| notes / revision PDF / cheat sheet on a topic | `stem-topic-pdf` | pageless PDF, written to the connected folder |
| a flashcard deck from a document or PDF | `anki-deck-builder` | `.apkg` |
| a concept outside the syllabus, pure curiosity | `learn` | chat |
| homework that will be handed in | `tutor` rules: hints and parallel examples, never the finished answer | chat |
| anything that is not study | `full-arsenal` | – |

Ask the exam board and level only when the request does not make them clear: this learner's boards are CAIE 9701/9702 and Edexcel IAL Maths/Further Maths.

## Modes during study

- Explanations and feedback to the learner are full, clear sentences, whatever compression style is active elsewhere.
- Subagents return JSON only; relay what matters in your own words.
- Tutoring runs on its own diagnose-first procedure, so no separate brainstorming or planning pass.
- When a turn ends because the learner must act (upload iPad working, sit a paper, import into Anki), end with an explicit line such as "Waiting for your working (7.pdf)." so any keep-going hook sees a genuine human wait.

## Budget (Pro plan)

- Haiku handles tutoring; the engine's scripts do scheduling, grading and reports at no token cost.
- Subagents only where isolation saves tokens: `marker` for handwriting images, `digest` for long transcripts or documents.
- One Cowork session per study block; past about 40 turns, suggest a fresh session. Keep only the STEM Tutor folder connected, and turn off connectors the study Project does not use.
