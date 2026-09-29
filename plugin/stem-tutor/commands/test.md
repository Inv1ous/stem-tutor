---
description: "Prepare for a school test or exam on chosen topics"
argument-hint: "<topics, e.g. physics chapters 1 and 2>"
model: haiku
---

Run the tutor skill in test mode for: $ARGUMENTS. Map the topics to ids with `find` (a subtopic id such as `9702-2.1`, or a topic id such as `9702-1`, covers all its syllabus points), state the list and time in one line, then immediately run (yourself, without waiting for a reply) `session start --mode test --minutes <minutes, default 60> --kcs <ids>`, then `next`, and ask the first questions in the same turn. Do this even in a first-ever session; onboarding can wait for another day. Engine commands are yours to run; never show them to the learner or ask them to run one.

Engine commands always run as `python3 ~/mnt/*/.tutor/engine/tutor.py <command>` through `device_bash` (see the tutor skill's Engine section); never run a bare `session`, `next` or `answer`.
