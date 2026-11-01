# Personal learning tutor revision

The learner wants Learn a topic across all courses to feel like personal tutoring,
with useful visual guidance and a mixture of prepared lessons and responsive AI.
Chemistry 9701-1.4 was the diagnostic example. Its latest legacy Refine pass was abandoned after
written-review failures, restored its additions and returned to `ready`.
Publication is currently disabled. A board status therefore did not establish a
changed learner experience.

Extend the existing engine, teaching cards and Learning tutor rather than create
a second tutor or trigger another bulk Refine run. A content-only revision would
leave the Learning tutor hidden; an unrestricted live generator would bypass the
prepared material and existing answer checks. The chosen approach combines
visible, contextual tutor controls with explicit card-bound diagrams and a
separately reviewed Chemistry pilot.

The existing Textual application is the visual target. Capture its actual lesson
screen in a disposable vault before and after. Make the Learning tutor reachable
from lesson explanations, preserve its bounded conversation and learner context,
and retain independent-question protection. Show useful source images within
the learning flow when possible and keep a full-size Obsidian route and accessible
description. A failed or unsupported preview must retain the explanation.

Use only diagrams explicitly bound to a teaching card, with verified Library
reads. Keep prepared lesson prose visible and let the existing Learning tutor
select it or write a checked alternative when appropriate. Do not automatically
spend model tokens on every Continue. Preserve saved node phases and progress;
new content applies to newly started lessons, not in-flight activities.

The user clarified that course-specific rewriting is not wanted. Leave the
diagnostic Chemistry draft unpublished and stop its review/publication work.
Do not change or activate any course content. Focus on shared runtime features:
inline follow-up questions, quick requests for help or another example, goal-aware
and conversation-aware tutor context, and useful source-image previews. Preserve
the prepared lesson while talking; chat must not fabricate mastery or consume the
next step. Keep typed follow-ups through a terminal resize.

Constraints: do not stop/restart/requeue workers, modify their states, edit their
in-progress candidates, change provider/publication preferences, or run bulk
generation. The user previously opted out of questions; choose the existing-flow
extension and record the choices. Review this task against its saved starting
files because the checkout already contains unrelated work. Do not commit those
unrelated changes. The repository has no issue-tracker conventions file;
`/setup-matt-pocock-skills` can install those conventions later.
