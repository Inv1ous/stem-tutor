# How STEM Tutor works

_Version 1.3.1_

STEM Tutor is your personal A-Level tutor for **CAIE Physics (9702)**, **CAIE Chemistry (9701)** and **Edexcel IAL Maths and Further Maths**. You work with it in a **Terminal window**. Everything worth keeping is written into **Obsidian** (this vault) as you go: the question in front of you, notes that grow as you learn, and a record of every session.

It is built around how memory actually works. It teaches one idea at a time, makes you *recall* things instead of re-reading them, brings each idea back just before you would forget it, and keeps track of what works best for **you**.

> [!tip] The short version
> Double-click **Start Tutor.command** in this folder. Put the Terminal window on the left and Obsidian on the right, showing **Now**. Choose **Today's plan** (or "Learn a topic") and follow the prompts. Press **?** at any time for help.

> [!example] New in 1.3.1
> - **Claude's 5-hour limit is no longer invisible to the foundry.** Claude tells a background job about one limit only (the one nearest its end, usually the weekly one), so the foundry could not see how full Claude's 5-hour window was, and `foundry usage` showed nothing for it. It now says "not reported" when it does not know, takes the figure when it is passed on from the Claude app's usage card (`foundry reading claude five_hour <percent> <reset time>`; the manager does this for you), and if a Claude job is refused by that limit it keeps Claude closed until the window resets and gives the work to Codex.

> [!example] New in 1.3.0
> - **New chapters are built on both of your allowances at once.** The foundry (the workshop that builds chapters) now splits its work between your Claude allowance and your Codex allowance. Before every job it reads what is left of each and gives the job to the one with more left, so the two run out together instead of one sitting unused. `foundry usage` shows both, and `foundry watch` shows them live.
> - **The smallest model that does the job.** Every kind of job starts on the cheapest model and moves up only when that proves not enough. The AI family that writes a chapter never checks it: the other one does.
> - **Two new chapters**, built this way as the first run: **9701-2.2 The mole and the Avogadro constant** and **9701-2.4 Reacting masses and volumes**.

> [!example] New in 1.2.8
> - **Your Almanac ticks count.** Tick objectives in your Almanac as usual, then press **Export** there. The tutor finds the exported file in your Downloads folder the next time it opens (or when you come back to its menu) and reads your ticks from it. A ticked objective is no longer taught from the start: **Today's plan** asks one quick check question on each of its ideas instead. Get it right and the idea joins your reviews; miss it and it becomes your next lesson.
> - **The plan follows you when you are ahead.** Once everything in this week's Almanac is ticked (or secure in the tutor), the home screen and **Today** move on to the next week with something left, and Today's plan teaches from there, however far ahead of the calendar that is.
> - **Chapters you need come first.** New chapters are now built in the order you need them: the ones in front of you before the ones you have ticked off.
> - macOS may ask once whether Terminal may look in your Downloads folder. Allow it, or move the exported file into this vault's **Almanac** folder yourself.

> [!example] New in 1.2.7
> - **No more leftovers at the right edge.** After you resized the window, bits of the old screen (pieces of border and scrollbar, stray letters) stayed in the strip between the tutor and Terminal's own scrollbar. The tutor now wipes them every time the window changes size.
> - **Start Tutor opens in your Study profile.** The window's title bar shows only **STEM Tutor**, and the profile's colours match the tutor, so the thin frame Terminal leaves round the text no longer shows. Your other Terminal windows are unchanged.

> [!example] New in 1.2.6
> - **The Terminal window is named STEM Tutor** while the tutor runs. Terminal adds its own details after the name (folder, running program, window size). To show the name alone, untick them in Terminal → Settings → Profiles → Window.

> [!example] New in 1.2.5
> - **Half-screen windows look right.** With the window at half the screen, the "Ask the tutor" button turned into a wide orange box that ran off the right edge, the lesson's scrollbar sat one column in from the edge, and answer boxes ended a column away from the cards above them. Everything now shares one grid and the scrollbar sits on the edge.
> - **The home screen's side panel scrolls.** With 22 chapters its list ran off the bottom of the window. It now fits: scroll it with the mouse wheel, or press **Tab** to move to it and use the arrow keys (**Tab** again returns to the menu).
> - An "I don't know" answer no longer shows the line "Exam point: don't know".

> [!example] New in 1.2.4
> - **An exact answer never needs zeros added.** `9 m s-2` used to lose a mark for not being `9.0`. The exam boards give the mark when nothing was rounded away, so the tutor now does too. The figures still count where they mean something: when the question says how many to give, for an instrument reading (a micrometer's `1.50 mm`), and for a long unrounded value in physics or chemistry (`73.575 J` is `74 J`). In maths an exact answer can be given in full (`112.5`).
> - **A rounded whole number can be typed with zeros.** `2400` is now accepted for 2375. It used to be marked wrong; only `2.4×10^3` or `2380` counted.
> - **A near miss is no longer taken for a rounding.** Just above a power of ten the tutor accepted answers up to 5% too small as "correctly rounded" (`96` for 100.5). It no longer does.

> [!example] New in 1.2.3
> - **Ask about an answer as soon as it is marked.** In a check with no hints, the tutor had quietly lined up the next question, so asking the AI about the one just marked was refused ("answer it first"). Questions now come one at a time: once yours is marked, you can always ask (ctrl+t) or have it explained.
> - **The AI tutor knows what you wrote.** When you ask about a marked answer, it is told your answer and why a mark was lost, so it can answer the question you actually have.
> - **A lost mark says why.** Now and the lesson record used to say just "incorrect" for a right value that lost a mark. They now give the exam point, for example `1 s.f. (want 2/3)`: one significant figure was given and two or three were wanted.
> - **Typed powers are read properly.** `10³ J` is a thousand joules (it was read as 103). A power the tutor can't use as a number, like `5²`, is asked for again instead of being marked.
> - **Only help you received counts as a hint.** If the AI was signed out or over its limit when you asked, your answer still counts as your own.
> - **Nothing is recorded twice.** If the tutor stops in the middle of saving an answer, it picks up exactly where the record ends.
> - **The mistake journal shows past-paper questions** (it used to say "not recorded").

> [!example] New in 1.2.2
> - **Chapters are checked against the syllabus, outcome by outcome.** A new chapter can't reach you unless every syllabus learning outcome in it is taught, covered by the notes and asked the way the syllabus words it, and the whole syllabus is tracked so nothing is left out.

> [!example] New in 1.2.1
> - **The answer shown is the answer wanted.** Model answers keep their significant figures (`11.0 m`, `2.50`, `4.69e5 J`), and exact answers are shown in full (`12.25`, `1200`) instead of being rounded to three figures.
> - **The AI can't let an answer slip at a different precision.** While a question is open, its answer is blocked at any number of figures, not only as shown.

> [!example] New in 1.2.0
> - **What the tutor knows about you.** A new menu choice shows everything the tutor has worked out about you, with the evidence, how sure it is and what it changed because of it. Press **a** for a short AI summary (section 8).
> - **Fix my weak spots.** A session on your active misconceptions, gaps and the ideas you keep getting wrong (section 3).
> - **Exam readiness** for every exam, a **mistake journal** and a **week in review** page in Obsidian (sections 8 and 9).
> - The full list of features is just below.

> [!example] Earlier updates (1.1.1 to 1.1.5)
> - **Your Almanac plans your day.** The menu now starts with **Today's plan**: ideas due for review first, then the next topics in your Almanac's week order. The home screen lists this week's Almanac objectives and which are ready to study, and **Today** in Obsidian shows the whole plan as soon as the tutor opens (section 3).
> - **The tutor always starts.** If macOS stops it opening your iPad inbox in iCloud Drive, it starts anyway and tells you how to allow it (section 16).
> - **New chapters arrive while you study.** As soon as a chapter has passed every check it is added to this vault; if the tutor is open, the menu says **New chapters ready: …** next time you are back at it. A session you are in the middle of is never disturbed.
> - **Fairer marking.** A number correctly rounded to 2 significant figures now counts where the question allows it; formulas typed the way the app shows them (`u² + 2as`, `2πr`, `√(2gh)`) are accepted; a formula that is only right for positive numbers (like `√(x²)` for `x`) no longer gets full marks.
> - **Nothing is marked wrong by accident.** If a question wants just a number and you add a unit, or the tutor can't read a formula, it asks you to type it again instead of marking it wrong.
> - **Written answers are always checked properly**, by the AI examiner or by your own ticks, never just by spotting key words.
> - **Asking the AI during a question counts as a hint**, and on no-hint checks it waits until you've answered.
> - **Nothing of yours gets overwritten**: lesson records, Anki files and iPad PDFs made at the same moment all keep their own copy, every paragraph of your own words survives re-teaching, and long-answer working is saved in the lesson record.
> - **Pick up where you left off**: after a restart, an explanation or worked example comes back at the step you reached.
> - **Anki**: cards from every topic you study now arrive, and maths with < or > shows correctly.
> - **No repeated questions**: past-paper questions that Cambridge printed in two different papers now appear once.
> - The first time you open 1.1.1 or later, your progress is re-counted once from your answer history with the corrected rules. Full list: `stem-tutor/CHANGELOG.md`.

> [!example]- What came in 1.1.0
> - **Blurt**: write everything you remember about a topic; the tutor shows what you left out and schedules it.
> - **Smarter reviews**: the ideas you're closest to forgetting come first, mixed across topics, and reviews tighten as an exam gets close.
> - **Second chances**: an idea you miss in a review comes back a few questions later, so you finish the session getting it right.
> - **Honest confidence tracking**: "unsure but right" and "certain and right" are now scheduled differently.
> - **"Why did I miss it?"**: one keypress after a mistake (careless slip, misread, didn't know, wrong method, wrong idea), so your profile shows where marks really go.
> - **Break suggestions** when your accuracy dips, and a **checking routine** if careless slips cost you marks.
> - **Keys that work while you type**: ctrl+t ask, ctrl+g hint, ctrl+r re-explain, ctrl+o Obsidian, ctrl+b menu.
> - A clearer **profile** (Profile page and "My progress"), plus many fixes. Full list: `stem-tutor/CHANGELOG.md`.

---

## Everything the tutor can do

**Plan your day**
- **Today's plan**: ideas due for review first, a quick check of what you have ticked in your Almanac, then your Almanac's next topics (however far ahead you are), mixed practice and a short exit check (section 3).
- **Your Almanac week** on the home screen: what you have ticked, which topics are ready to study, the next week once this one is done, and a countdown to your next exam (section 3).
- **Today** page in Obsidian: the day's plan, what's due and what each Almanac objective needs to count as done (section 9).
- **Exam readiness** for every exam: how much of its syllabus is built, started and secure, and your predicted recall on the day (section 8).

**Learn**
- **Lessons** built around you: your goal, a quick check of what you know, a plan you agree to, then each idea with a try-it-first question, a worked example, a no-hints check and your own words (section 4).
- **Teaching that adapts**: misconceptions are tackled head-on, and teaching methods are tested on you fairly so the one that works better is kept (section 8).
- **Subjects**: complete reference notes for every subtopic, and **My Notes**, which grow as you learn (section 9).

**Practise and remember**
- **Spaced reviews** timed to just before you would forget, most at risk first, topics mixed, sharper as exams get close, with second chances in the same session (section 7).
- **Fix my weak spots**: active misconceptions, gaps and ideas you keep getting wrong, re-taught and practised (section 3).
- **Test prep** for a school test on the chapters you choose (section 7).
- **Blurting**: write everything you remember and see what you left out, checked without AI (section 6).
- **Long questions and past papers** marked against the real mark scheme, typed or on the iPad (section 5).
- **Anki flashcards** exported every week (section 10).

**Answer and get marked**
- Multiple choice with **confidence ratings**; numbers checked for value, unit and significant figures; formulas typed as you'd write them; written answers judged by the AI examiner (section 5).
- **Why did you miss it?** questions after mistakes, and a **break** suggested when your accuracy drops (section 5).

**Know yourself**
- **What the tutor knows about you**: every finding with its evidence, how sure it is and what it changed; an **AI summary** when you ask (section 8).
- **Mistake journal**: every question you got wrong, with the right answer (section 9).
- **Week in review** every week (section 9), and **My progress** for a quick look at your topics (section 3).

**AI help (optional)**
- Ask anything (**ctrl+t**), have an idea explained another way (**ctrl+r**), hints (**ctrl+g**), a talk-through when you're stuck, and feedback on your own words, within a daily allowance you set (sections 11 to 13).

**Behind the scenes**
- **Nothing is lost**: every answer is saved the moment you give it, and an unfinished session can be resumed (sections 3 and 15).
- **New chapters arrive while you study**, checked by a team of AIs before they reach you (sections 3 and 15).
- **Your Almanac** stays in charge of the plan, and can exchange progress with the tutor (sections 3 and 15).
- **iPad inbox** for handwritten work, and a **doctor check** that tells you how to fix anything that's wrong (sections 1, 5 and 15).

---

## 1. Setting up (once)

1. **Open this folder as a vault in Obsidian.** In Obsidian: *Open another vault → Open folder as vault →* choose **STEM Tutor** (it is in `Miscellaneous › 02 Education › ~~ AI Workflow`), or a folder that contains it. This lets the tutor show its pages automatically.
2. **Sign in the AI (optional but recommended).** Open the Terminal app, type `claude auth login` and follow the steps with your normal Claude account. This lets the tutor answer your questions and explain things in new ways. Everything else works without it.
3. **Check everything.** In Terminal, run the tutor's check:
   `"$HOME/Miscellaneous/02 Education/~~ AI Workflow/stem-tutor/bin/tutor" doctor`
   Every line should show ✅. Anything with ❌ tells you exactly what to do.

> [!info] Want to start it by typing `tutor`?
> Run this once in Terminal, then open a new Terminal window:
> `echo 'alias tutor="$HOME/Miscellaneous/02\ Education/~~\ AI\ Workflow/stem-tutor/bin/tutor"' >> ~/.zshrc`

This folder lives on your Mac only, not iCloud, so nothing needs to be "kept downloaded". Your progress is saved in the hidden `.tutor` folder inside it.

---

## 2. Starting a session

**Double-click `Start Tutor.command`** in this folder (in Finder). A Terminal window opens and the tutor starts. If you set up the shortcut above, you can type `tutor` instead.

**The layout that works best:** Terminal on the left half of the screen, Obsidian on the right half showing **Now**. You can minimise the Claude app: the tutor doesn't need it open. If the window is small the tutor says so; make it bigger or full-screen.

Everything is done with the keyboard (see section 11).

---

## 3. The home screen

When new chapters have been added since you opened the tutor, the menu tells you ("New chapters ready: …") and they are available straight away.

| Choice | What it does |
|---|---|
| **Resume** | Only appears if you left a session unfinished. Carries on where you stopped. |
| **Today's plan** | The tutor decides for you: ideas due for review first, then a quick check of ideas you have ticked in your Almanac but never answered here, then the next topics from your Almanac in week order (earlier weeks you haven't done come first, and it carries on past the calendar week when you are ahead), then mixed practice and a short exit check. Topics without questions yet are skipped. |
| **Learn a topic** | A full lesson on one subtopic: a quick check of what you know, a plan you agree to, then each idea taught step by step. |
| **Review what's due** | Mixed questions on ideas that are due to be refreshed (section 7). If nothing is due it tells you, instead of starting an empty session. |
| **Fix my weak spots** | A session on what's weak right now: ideas with a misconception still active, gaps found by blurts, test prep or checks, and ideas you keep getting wrong. Each is re-taught (a misconception head-on, with a contrasting example), then practised with fresh questions. The number shows how many there are. |
| **Test prep** | For a school test: one question on every point of the chapters you choose, then it fixes only what you got wrong. |
| **Long questions** | Exam-style long questions. You write the answer, then mark it against the real mark scheme. |
| **Blurt** | Write down everything you remember about a subtopic. The tutor shows what you left out (section 6). |
| **Ask the tutor anything** | A free chat with the AI tutor. |
| **What the tutor knows about you** | Everything the tutor has worked out about you, with the evidence, how sure it is, and what it changed because of it (section 8). |
| **My progress** | A quick look: how secure each topic is, how sure vs how right, and your habits. |
| **Open my notes in Obsidian** | Shows your Home page in Obsidian. |
| **Settings / How it works / Quit** | As they say. |

If you choose something new while a session is unfinished, the tutor asks first: **resume it**, or **abandon it and start**.

The right side of the home screen shows today's date, your **streak** (days in a row you studied), how many ideas are **due**, the countdown to your next exam, your **Almanac week** (each objective marked ✓ when it is done, otherwise *ready*, partly ready or *not built yet*), a progress bar for each topic, and whether the AI is on. When everything in the calendar week is done, the next week with something left is shown instead, with a line saying you are ahead.

**Your Almanac.** The tutor follows your planner, `00 Important › 01 AS/A › A-Levels.html`: the objectives for each week and the exam dates. If you change the planner, the home screen says **Your Almanac has changed**: ask Claude Code to refresh the plan. Until then the tutor keeps following the plan it last read.

**Your ticks.** The Almanac keeps its ticks inside your browser, where the tutor can't see them. To pass them on, press **Export** in the Almanac after ticking: the browser saves a small file in Downloads, and the tutor picks it up the next time it opens or you come back to its menu (it moves the file into this vault's **Almanac** folder). The home screen says which export your ticks were read from. An objective counts as done when you have ticked it, or when every idea in it is secure in the tutor. Ticking does two things:

- **No lesson for what you have ticked.** Today's plan asks one check question on each ticked idea instead (no hints, a few per session). Right: the idea joins your review schedule. Wrong or "don't know": it becomes a gap and is taught first next time.
- **The plan moves on.** When the whole week is done, the home screen and **Today** show the next week with something left, and Today's plan teaches from there.

A tick covers the syllabus section the objective refers to. A few ideas from sections the Almanac never schedules are attached to the nearest objective; those are still taught.

---

## 4. A lesson, step by step

A lesson works like a good private tutor, and every step has a reason.

1. **Your goal.** You choose: *learn it from scratch*, *fill my gaps*, *revise for a test soon*, or *just the key ideas quickly*. This changes how much checking and explaining happens.
2. **A quick check (the "probe").** One question on each idea in the topic, and on anything it builds on. This finds the edge of what you already know, so the tutor doesn't waste time on what you've got or skip what you haven't. "I don't know" is a perfectly good answer here.
3. **The plan.** The tutor shows the ideas it will teach, in order, with a **concept map** in Obsidian. Ideas you clearly know are unticked. Tick or untick anything with the space bar, then start. If you already know everything, you get a quick harder mixed check instead.
4. **Each idea, one at a time:**
   - **Why this matters.** A sentence on what problem the idea solves, so it doesn't feel random.
   - **Try it first** (sometimes). A question *before* you're taught. Getting it wrong here is expected, and it makes the real answer stick better. For some ideas the tutor tries a harder "have a go" problem first; this is one of the teaching methods it tests on you (section 8).
   - **The idea.** A short explanation, built up from things you already accept, and how it connects to what you know.
   - **Worked example** (sometimes). Shown one step at a time. Predict each step before you reveal it.
   - **Check, with no hints.** One question to prove it landed. If you miss it, the tutor fixes the exact mistake (often a common trap) and gives you one more try. If it still hasn't clicked, it is saved as a **gap** that comes back later, and you can talk it through with the AI tutor.
   - **In your own words.** One or two sentences explaining the idea. This is one of the most useful study habits there is, and your sentence goes into your notes.
   - **Your notes grow.** The idea's summary, your own words and any mistakes you made are added to **My Notes** in Obsidian.
5. **Final check.** A couple of no-hint questions on today's ideas, then a summary of what you learned, what's due next, and how much AI you used.

---

## 5. Answering questions

- **Multiple choice:** move with **↑ ↓** and press **⏎**, or press the letter **A–D**. Press **0** for *I don't know*.
- **How sure are you?** After choosing, rate your confidence **1–4**: 1 guess, 2 unsure, 3 fairly sure, 4 certain. Changed your mind? Press **Esc** to go back to the options. Be honest. A *confident* wrong answer is the best moment to fix a misunderstanding, so the tutor makes a point of it. A right answer you were unsure about comes back sooner than one you were certain of.
- **Optional note:** under the options you can type why you chose it (**Tab** to reach the box). It goes into the lesson record.
- **Number answers:** type the value **with its unit**, e.g. `19.6 m s-1` or `4.5e-3 mol dm-3`, then ⏎ and your confidence. Brackets and minus signs like `(−1)` are fine. The tutor checks the value, the unit and significant figures. A right value with a missing unit, or rounded to the wrong number of figures, shows as **"Right value, but a mark lost"**, and the **Exam point** line says what was wanted. An exact answer never needs zeros added: `9 m s-2` is right for 9.0, as it is in the exam. The figures still count when the question fixes them (it says how many, or the value is an instrument reading such as a micrometer's `1.50 mm`) and when there are too many in physics or chemistry (`73.575 J` should be `74 J`); in maths an exact answer may be given in full. A rounded whole number can be typed with zeros (`2400` for 2375). Type the final number, not a sum (`500 + 1` isn't worked out); a power of ten is fine as `4.5e-3`, `4.5×10^-3` or `10³`. If a question wants just a number (a count, a ratio, a value "in mm"), type only the number: add a unit and the tutor asks you to send it again, with no mark lost.
- **Formula answers:** type them as you would write them: `u^2 + 2as`, `u² + 2as`, `2πr` and `√(2gh)` all work. If the tutor can't read one, it asks you to type it again.
- **Written answers** (definitions, explanations): type them. The AI examiner always compares your wording with the mark points, because spotting the right words isn't enough ("velocity is the rate of change of velocity" has all the right words in the wrong places). Without AI, you tick which points you really covered.
- **Long questions:** write your full working in the box, then **ctrl+s**. The mark scheme appears as a checklist: tick each mark you really earned with the space bar. Honest self-marking is itself excellent practice. You can also ask the **AI examiner** to check your marking.
  - Prefer paper or the iPad? Do it there, type `done on paper`, press ctrl+s, and self-mark from the scheme. PDFs you save on the iPad into **iCloud Drive › STEM Tutor Inbox** are copied into this folder's **Inbox** the next time the tutor starts, so your working is kept with your notes.

After every answer you see ✓ or ✗, the correct answer and a short explanation. Past-paper questions show the official answer and any examiner comments; press the **Explain this answer** button for an AI explanation.

**After a wrong answer** the tutor may ask **why you missed it**: 1 careless slip, 2 misread the question, 3 didn't know or forgot, 4 wrong method, 5 had the wrong idea. Press **Esc** to skip. It asks at most six times a session, never during the quick check, and suggests "slip" when you answered unusually fast on something you normally get right. Your answers build the "Mistakes by kind" part of your profile.

**If you seem tired:** when your accuracy drops clearly below what's normal for you (or after the number of questions where you usually start to fade), the tutor suggests a short break. Keep going or save and stop; your place is kept either way.

---

## 6. Blurting (free recall)

Choose **Blurt** on the home screen and pick a subtopic. Write down **everything you remember** about it: definitions, equations, units, examples, traps. Don't look anything up; about three minutes is plenty. Then press **ctrl+s**.

The tutor checks which ideas your writing covers, using each idea's key terms from the syllabus. No AI is needed for this. You see ✓ for ideas you covered and ✗ for ideas you left out, with a short summary of each one you missed. **Missed ideas you have studied before are pulled forward, so they come up in your next review**; ones you haven't studied yet are a sign to start a lesson on that topic. Your blurt and its results are saved in **Lessons**.

Blurting is a strong form of recall practice, far better than re-reading notes. Use it at the start of a revision day, or to check a topic before a test.

---

## 7. Reviews, memory and "secure"

Everyone forgets. The tutor uses the method behind Anki's modern scheduler, called **FSRS**, to predict when *you* are about to forget each idea, and asks about it just before that.

- Each time you remember an idea, the gap before its next review grows: days, then weeks, then months. A slip brings it back sooner.
- **How you remembered matters.** Right and certain, on an idea you have already remembered on earlier days, pushes the next review furthest. Right but unsure, or right only after a hint, brings it back sooner. Wrong starts it again.
- **Most at risk first.** When several ideas are due, the ones you are closest to forgetting come first, with more weight for exams that are coming soon. Reviews also **mix topics together**. That feels harder, but it builds what exams test: recognising which idea a question needs.
- **Exam-aware.** As an exam gets close (the last few weeks), reviews aim for a higher level of recall, so you are sharpest on the day. When an exam is over a year away, they relax slightly to save you time.
- **Second chances.** If you miss an idea in a review, it comes back a few questions later in the same session with a different question, so you leave having got it right.

An idea counts as **secure** when you have answered it correctly **without help on at least two different days** and your overall record on it is strong.

**Test prep** is different: it's for a test coming up soon. It asks one question on every point of the chapters you choose, reteaches only what you missed, and re-checks it. Anything still weak is saved and comes back later.

---

## 8. What the tutor knows about you

Choose **What the tutor knows about you** on the home screen, or open the **Profile** page in Obsidian. Everything there is counted from your own answers and compared with **what was expected for those questions**, so a hard topic doesn't look like a bad day. Nothing is guessed by AI.

| Part | What it tells you |
|---|---|
| **What the tutor has recorded** | What the findings are based on: answers, sessions, study days, confidence ratings, hints, mistakes sorted by kind, misconceptions spotted, blurts and past papers. |
| **What it has worked out** | One finding per area, each with the evidence (the numbers), **how sure** the tutor is, and **what the tutor does about it**. The areas: memory in each subject, confidence vs accuracy, what costs you marks, misconceptions (still active and fixed, in their own words), time of day, stamina, pace, hints, teaching experiments, strongest and weakest topics, and study habits. |
| **What the tutor has adjusted for you** | Every change currently in force, with the reason. |
| **Exam readiness** | For each exam: how much of its syllabus is built, started and secure, and your predicted recall on the day, both if you stopped reviewing now and if you keep your reviews up. Exams without a date in your Almanac use an estimate and say so. |
| **Weak spots** | What **Fix my weak spots** will work on, and why each one is there. |
| **AI summary** | Only if you asked for one (below). |
| **What it never does** | No learning styles, no AI guessing about you, no acting on one bad day, and nothing sent anywhere unless you ask. |

**How sure it is.** ⚪ **not enough data** · 🟡 **early sign**: some answers, not yet enough for the tutor to act on · 🟢 **likely**: enough to act on · ✅ **clear**: three times that much. The tutor only changes something at 🟢 or ✅. For example, confidence needs 30 rated answers, review timing 10 spaced reviews in a subject, and a mistake pattern 8 mistakes sorted by kind.

**AI summary.** Press **a** on that screen and the AI tutor turns the findings into a few lines: what's going well, the one change most likely to gain you marks, and what to do this week. It sees only the findings, never your answers, uses one reply from today's allowance, and says when the evidence is still early. The summary is saved with its date on the Profile page.

**Keys on that screen:** **a** AI summary · **o** open it in Obsidian · **m** your mistake journal · **w** your latest week in review · **Esc** back.

**Adjustments it can make** (only when your data supports them):
- **Checking routine:** if careless slips cost you many marks, answer boxes show a quick reminder: units, significant figures, sign, and whether you answered what was actually asked.
- **Confidence notes:** if your confidence is often off, feedback shows how often you are really right at the confidence you chose.
- **Have a go first:** if you use hints a lot, the first press of the hint key asks you to try first, and the second press gives the hint.
- **Break point:** if your accuracy reliably dips after a certain number of questions, a break is suggested there.
- **Review timing:** if you forget faster or slower than the model predicts, your reviews move to match.
- **Teaching method:** when an experiment finds that one way of teaching works better for you, lessons use it for that kind of idea.

There are no "learning styles" here. The research is clear that they don't help. The tutor only uses what measurably works for you.

---

## 9. What appears in Obsidian

| Page / folder | What it is |
|---|---|
| **Now** | Whatever is in front of you right now, in full: the question (with its diagram, if any) or the explanation, with proper maths. Your notes for the topic are shown underneath. Keep this open beside the Terminal. |
| **My Notes** | Your notes, one page per subtopic, **built as you learn**. Each idea gets a short summary, your own words and a "Watch out" list of the mistakes *you* made. At the top is a coloured map of the topic. If you re-learn an idea, your earlier words and mistakes are kept. |
| **Lessons** | A full record of every session and blurt: explanations, every question (shown before you answer, never with the answer), your answers and the feedback. |
| **Home** | A dashboard: progress per subtopic, reviews due, and links to your notes and recent lessons. |
| **Subjects** | Complete reference notes for each subtopic, written in advance and checked. Read these whenever you want the whole topic in one place. |
| **Profile** | What the tutor knows about you (section 8). Refreshed after each session. |
| **Mistakes** | Your mistake journal: every question you got wrong or didn't know, by subtopic and newest first, with your answer, the right answer and the kind of mistake. ✓ marks the ones you have put right since. Refreshed after each session. |
| **Weekly** | A week in review for each week you studied: days, answers and how many were right (compared with the week before), ideas newly secure, misconceptions fixed, and what changed in your profile. Written the first time the tutor opens in the following week. |
| **Today** | Today's plan: what's due, your Almanac week's objectives (the next week when you are ahead) with which are ticked, how many of their ideas you have mastered and what each needs to count as done, and which topics aren't built yet. Refreshed when the tutor opens, when it reads a new export, and after each session. |
| **Anki** | Flashcard files (section 10). |

**Colours in the map and headings:** ✅ green = secure, 🟡 yellow = learning, 🔴 red = a gap to fix, ⚪ grey = not started, 🔵 blue = the idea you are on now.

You can add your own writing to **My Notes** anywhere outside the grey markers (the lines starting `<!-- stem-tutor`). The tutor only rewrites what is between its markers.

---

## 10. Anki flashcards

About once a week, after a session, the tutor exports new flashcards for facts and definitions you have met, as a file in the **Anki** folder. The summary screen tells you when there is one. Double-click it to add the cards to Anki. Cards you already have in Anki aren't duplicated.

---

## 11. Keys

These work **everywhere, even while you are typing an answer**:

| Key | What it does |
|---|---|
| **ctrl+t** | Ask the tutor a question (AI) |
| **ctrl+r** | Explain this idea again, a different way (AI) |
| **ctrl+g** | Hint (not allowed on no-hints checks) |
| **ctrl+o** | Show the current question or explanation in Obsidian |
| **ctrl+b** or **ctrl+q** | Save and go back to the menu (you can resume later). On the menu, ctrl+q quits. |

Answering and moving around:

| Key | What it does |
|---|---|
| **↑ ↓** then **⏎** | Choose / continue |
| **A B C D** | Pick that option |
| **0** | I don't know |
| **1 2 3 4** | Confidence: guess / unsure / fairly sure / certain |
| **Esc** | Go back a step (change your answer, skip a prompt, close a pop-up) |
| **space** | Tick or untick a box |
| **Tab** | Move to the next box or button |
| **ctrl+s** | Submit a long answer or a blurt |
| **?** | Help · **F2** Settings (from the menu) |

When you are **not** typing, the single letters **t e h o** do the same as ctrl+t, ctrl+r, ctrl+g and ctrl+o.

---

## 12. Settings (F2 on the menu)

| Setting | What it changes |
|---|---|
| **AI tutor** | Turn AI help on or off completely. |
| **AI comments on your own words** | Short feedback on your "in your own words" answers (on by default). |
| **Show Now in Obsidian** | Whether Obsidian jumps to the Now page when a session starts. |
| **Model** | **Haiku** (default: fast and cheapest) or **Sonnet** (clearer explanations, but uses about three times more of your Claude limit). |
| **AI replies per day** | A daily allowance, 80 by default, so the tutor can never use up your Claude limit. |
| **Session length** | How long a session aims to be, 40 minutes by default. |

---

## 13. The AI, and your Claude usage limit

Most of the tutor needs **no AI at all**: choosing questions, marking multiple choice and numbers, scheduling reviews, the lessons' explanations (written in advance and checked), blurt checking, your notes, profile and records. That's why it's quick and cheap.

The AI (Claude, on your normal Claude subscription) is only used when it genuinely helps:

- when you **ask a question** (ctrl+t) or chat from the menu;
- when you ask for an idea **explained a different way** (ctrl+r), or for a past-paper answer to be explained;
- short feedback on your **"in your own words"** answers (you can turn this off);
- judging **written answers** and checking **long answers** (the AI examiner);
- talking an idea through with you when you're **stuck**;
- writing a teaching card for an idea that doesn't have one yet (done once, then saved);
- a short **summary of your profile**, only when you press **a** on *What the tutor knows about you*.

It runs quietly in the background, so the Claude app doesn't need to be open. It uses the small, fast **Haiku** model by default, sends only the few lines it needs each time, and starts a fresh, short conversation for every new idea and every new part of a session. Each request stays small.

**The top bar** shows `AI ●` (on) or `AI ○` (off), plus how many AI replies and tokens this session used.

- If your **Claude limit is reached**, the tutor says when it resets, carries on without AI, and turns AI back on by itself after that time.
- If it says you need to **sign in**, type `claude auth login` in Terminal once. The tutor tries again a few minutes later by itself.
- If you **stop a reply part-way** (for example by asking something else), the next reply still comes out correctly.

> [!warning] Questions that are still open
> While a question is waiting for your answer, the AI won't give you the answer, even if you ask or ask for a re-explanation. Asking the AI then counts as using a hint, like ctrl+g, and on a no-hints check it waits until you've answered. Answer first; then it will explain.

---

## 14. Why each part works (the research, in plain words)

The tutor uses methods with good evidence behind them, and is honest about how strong that evidence is. The full references are in `stem-tutor/docs/RESEARCH.md`.

| Method | What happens in the tutor | Evidence |
|---|---|---|
| **Recall instead of re-reading** | Every question, the probe, blurting | **Strong.** Recalling beats re-reading by a wide margin, and more so with feedback. |
| **Spacing and successive relearning** | FSRS reviews; missed ideas return in the same session and on later days | **Strong.** Relearning an idea until you get it right, across several sessions, gives large long-term gains. |
| **Fixing confident mistakes** | The "confident but wrong" moment, and quick retests | **Strong.** Confident errors are corrected especially well when you get feedback, but they can creep back, so they are retested. |
| **Explaining in your own words** | The own-words step and its feedback | **Strong to moderate.** Self-explanation reliably helps, especially with feedback. |
| **Worked examples, then doing more yourself** | Worked examples one step at a time, then a similar problem | **Strong** for new procedures. They help less once you're good at something, so the tutor stops using them then. |
| **Trying before being taught** | "Try it first" questions and the probe | **Moderate to strong.** Guessing first improves what you remember from the teaching. |
| **Mixing topics** | Reviews and test prep interleave subtopics | **Moderate.** A large classroom trial in maths found a big benefit; it works best after each topic has first been learned on its own, which is how the tutor uses it. |
| **Blurting** | The Blurt screen | **Strong compared with re-reading**; the benefit over other active methods is smaller than first thought. Always check what you missed, and the tutor shows you. |
| **Breaks** | Break suggestions when accuracy dips | **Moderate for feeling fresher**; weak evidence that breaks raise scores. The tutor suggests them and doesn't insist. |
| **Studying at your best time** | "When you learn best" in your profile | **Modest.** Real, but differs from person to person, so it is advice, not a rule. |
| **Tagging your own mistakes** | "Why did you miss it?" | **Weak** as a score booster. Kept because it's a one-key habit that shows where marks go. |
| **Tighter reviews before exams** | Exam-aware review targets | A sensible rule from how the memory model works, **not yet tested in trials**. |

---

## 15. Where everything lives

- **This vault (your data):** `Miscellaneous › 02 Education › ~~ AI Workflow › STEM Tutor`. Everything you see in Obsidian, plus the hidden `.tutor` folder with your progress. Every answer you've ever given is recorded there, so nothing is lost. Don't edit `.tutor` by hand. If a file in it is ever damaged (for example by a crash mid-save), the tutor skips the damaged line and carries on.
- **The program:** `~~ AI Workflow › stem-tutor`. You don't need to open it.
- **iPad inbox:** `iCloud Drive › STEM Tutor Inbox`, only for PDFs from the iPad.
- **Your Almanac:** `00 Important › 01 AS/A › A-Levels.html` (section 3). Press **Export** in the Almanac whenever you have ticked something: the tutor reads your ticks from that file (it looks in Downloads and in this vault's **Almanac** folder). After your next session the tutor writes `almanac-import-<date>.json` there, with your study days, mistake types, topic ratings and paper scores added; open it with the Almanac's **Import** button. Your ticks in the Almanac are kept.
- **New chapters** are prepared in advance by a team of AIs, paid for by your Claude and Codex allowances together, and checked before they reach this vault (the "foundry": `stem-tutor › foundry › README.md`). Until a chapter has passed every check it stays out of the vault.
- The old copy in your main Obsidian vault (`Notes › 01 Study › STEM Tutor`) is no longer used; it has a MOVED note. You can delete it once you're happy.

---

## 16. If something goes wrong

| Problem | Fix |
|---|---|
| The top bar says **AI ○** or "sign-in needed" | In Terminal: `claude auth login`. Or AI is switched off in Settings (F2). |
| "AI paused (limit)" | Your Claude usage limit is reached. Keep going without AI; it comes back by itself after the reset time shown. |
| A key like **h** types a letter instead of giving a hint | You're in an answer box: use **ctrl+g** (and ctrl+t, ctrl+r, ctrl+o), which work while typing. |
| Obsidian doesn't jump to **Now** | Open this folder as a vault once (section 1), or press ctrl+o. |
| The Terminal window is small | Make it bigger or full-screen; the tutor re-fits. |
| "Another STEM Tutor window is already open" | Use the other window, or close it first. Only one can run at a time so your progress can't get mixed up. |
| "Your answer was read as several parts" | Avoid commas between numbers in one answer, then send it again. |
| A question or answer looks wrong | Answer it anyway and press ctrl+t to ask why, then note it down; content can be corrected in the next update. |
| My Almanac ticks aren't counted | Press **Export** in the Almanac, then open the tutor or go back to its menu. If macOS asked whether Terminal may access your Downloads folder and you chose *Don't Allow*: System Settings › Privacy & Security › Files & Folders › Terminal › turn on Downloads Folder, or move the exported file into this vault's **Almanac** folder. |
| "Your Almanac has changed since the tutor read it" | Ask Claude Code to refresh the Almanac plan. Until then the tutor keeps following the plan it last read. |
| "macOS isn't letting the tutor open your iPad inbox" | System Settings › Privacy & Security › Files & Folders › **Terminal** › turn on **iCloud Drive** (or add Terminal under **Full Disk Access**), then restart the tutor. Everything else works in the meantime. |
| Anything else | Run the doctor check (section 1). It tells you what's wrong and how to fix it. |

---

## 17. Words you'll see

- **Idea** (in the program, a *KC*): one point from the syllabus, like "define displacement".
- **Subtopic:** a group of ideas, like "2.1 Equations of motion".
- **Probe:** the quick check at the start of a lesson.
- **Due:** an idea the tutor wants to refresh now, before you forget it.
- **Secure / learning / gap:** how well you know an idea (section 7).
- **Confidence:** how sure you said you were. The tutor compares it with how often you're right.
- **Misconception / trap:** a common wrong idea (for example "distance and displacement are the same thing"). Wrong multiple-choice answers are designed around these, so a wrong choice tells the tutor exactly what to fix.
- **Hypercorrection:** confidently wrong answers, once corrected, are remembered especially well, which is why the tutor pauses on them.
- **Relearning:** getting a missed idea right again later in the same session, and on later days.
- **Blurt:** writing down everything you remember, then checking what you missed.
- **FSRS:** the memory model that decides when each idea is due.
