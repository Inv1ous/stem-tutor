# How STEM Tutor works

STEM Tutor is your personal A-Level tutor for **CAIE Physics (9702)**, **CAIE Chemistry (9701)** and **Edexcel IAL Maths and Further Maths**. You talk to it in a **Terminal window**, and it writes everything worth keeping into **Obsidian** (this vault) as you go: the question in front of you, notes that grow as you learn, and a record of every lesson.

It is built around how memory actually works. It teaches one idea at a time, makes you *retrieve* things rather than re-read them, brings ideas back just before you would forget them, and keeps track of what works best for **you**.

> [!tip] The short version
> Double-click **Start Tutor.command** in this folder. Put the Terminal window on the left and Obsidian on the right, showing **Now**. Pick "Learn a topic" and follow the prompts.

---

## 1. Setting up (once)

1. **Open this folder as a vault in Obsidian.** In Obsidian: *Open another vault → Open folder as vault →* choose **STEM Tutor** (it lives in `Miscellaneous › 02 Education › ~~ AI Workflow`). Obsidian can then show the tutor's pages automatically.
2. **Sign in the AI (optional but recommended).** Open the Terminal app and type `claude auth login`, then follow the steps with your normal Claude account. This lets the tutor answer your questions and explain things in new ways. Without it, everything else still works.
3. **Check everything.** In Terminal, run the tutor's check:
   `"$HOME/Miscellaneous/02 Education/~~ AI Workflow/stem-tutor/bin/tutor" doctor`
   Every line should show ✅.

> [!info] Want to start it by typing `tutor`?
> Run this once in Terminal, then open a new Terminal window:
> `echo 'alias tutor="$HOME/Miscellaneous/02\ Education/~~\ AI\ Workflow/stem-tutor/bin/tutor"' >> ~/.zshrc`

This folder is on your Mac only (not iCloud), so nothing needs to be "kept downloaded". Your progress is saved in the hidden `.tutor` folder inside it.

---

## 2. Starting a session

**Double-click `Start Tutor.command`** in this folder (in Finder). A Terminal window opens and the tutor starts. You can also type `tutor` if you set up the shortcut above.

**The layout that works best:** Terminal on the left half of the screen, Obsidian on the right half showing the **Now** page. You can minimise the Claude app: the tutor doesn't need it.

You never need the mouse in the tutor: everything is done with the keyboard (see section 9).

---

## 3. The home screen

| Choice | What it does |
|---|---|
| **Resume** | Only appears if you left a session unfinished. Carries on exactly where you stopped. |
| **Learn a topic (lesson)** | A full lesson on one subtopic: the tutor checks what you already know, agrees a plan with you, then teaches each idea step by step. |
| **Review what's due** | Quick mixed questions on ideas that are due to be refreshed (see section 7). The number tells you how many are due. |
| **Test prep** | For a school test: one question on every point of the chapters you choose, then it fixes only what you got wrong. |
| **Long questions** | Exam-style long questions. You write the answer, then mark it against the real mark scheme. |
| **Ask the tutor anything** | A free chat with the AI tutor. |
| **My progress** | How secure each subtopic is. |
| **Open my notes in Obsidian** | Shows your Home page in Obsidian. |
| **Settings / How it works / Quit** | As they say. |

The right side of the home screen shows today's date, your **streak** (days in a row you studied), how many ideas are **due**, the countdown to your next exam, a progress bar for every topic, and whether the AI is on.

---

## 4. A lesson, step by step

A lesson works like a good private tutor, and each step has a reason.

1. **Your goal.** You choose what you want: *learn it from scratch*, *fill my gaps*, *revise for a test soon*, or *just the key ideas quickly*. This changes how much checking and explaining happens.
2. **A quick check (the "probe").** One question on each idea in the topic (and anything it builds on). This finds the edge of what you already know, so the tutor doesn't waste your time on things you've got or skip things you haven't. "I don't know" is a perfectly good answer here.
3. **The plan.** The tutor shows the ideas it will teach, in order, with a **concept map** in Obsidian. Ideas you clearly know are unticked. You can tick or untick anything (space bar), then start.
4. **Each idea, one at a time:**
   - **Why this matters.** A sentence on what problem the idea solves, so it doesn't feel random.
   - **Have a go first** (sometimes). A question *before* you're told. Getting it wrong here is expected and actually helps you remember the real answer.
   - **The idea.** A short explanation, built up from things you already accept, and how it connects to what you know.
   - **Worked example** (sometimes). Shown one step at a time. Try to predict each step before you reveal it.
   - **Check, with no hints.** One question to prove it landed. If you miss it, the tutor fixes the exact mistake (often a common trap) and gives you one more try.
   - **In your own words.** One or two sentences explaining the idea. This is one of the most powerful study habits there is, and your sentence goes into your notes.
   - **Your notes grow.** The idea's summary, your own words and any mistakes you made are added to **My Notes** in Obsidian.
5. **Final check.** A couple of no-hint questions on today's ideas, then a summary.

> [!note] Why "no hints" and "have a go first"?
> Struggling a little to recall something is what makes it stick. Checks without hints show what you *really* know; guessing before being taught makes the teaching land harder.

---

## 5. Answering questions

- **Multiple choice:** move with **↑ ↓** and press **⏎**, or just press the letter **A–D**. Press **0** for *I don't know*.
- **How sure are you?** After choosing, rate your confidence **1–4** (1 guess, 2 unsure, 3 fairly sure, 4 certain). Be honest: a *confident* wrong answer is the best moment to fix a misunderstanding, and the tutor treats it specially. A lucky guess is re-checked later.
- **Optional note:** under the options you can type why you chose it (press Tab to reach the box). It goes into the lesson record.
- **Number answers:** type the value **with its unit**, e.g. `19.6 m s-1` or `4.5e-3 mol dm-3`, then ⏎ and your confidence. Brackets and minus signs like `(−1)` are fine. The tutor checks the value, the unit and significant figures, and tells you if a mark would be lost for units or s.f.
- **Written answers** (definitions, explanations): type them. If the wording needs judging, the AI examiner compares it with the mark points; without AI, you tick which points you covered.
- **Long questions:** write your full working in the box (**ctrl+s** to submit). The mark scheme then appears as a checklist: tick each mark you really earned (space bar). Honest self-marking is itself excellent practice. You can also ask the **AI examiner** to check your marking.
  - Prefer paper or the iPad? Do it there, type `done on paper` as your answer, and self-mark from the scheme. PDFs you save on the iPad into **iCloud Drive › STEM Tutor Inbox** are copied into this folder's **Inbox** next time the tutor starts, so your working is kept with your notes.

After every answer you see ✓ or ✗, the correct answer, and a short explanation. For past-paper questions the official answer and examiner comments are shown.

---

## 6. What appears in Obsidian

| Page / folder | What it is |
|---|---|
| **Now** | Whatever is in front of you right now, in full: the question (with its diagram, if any) or the explanation, with proper maths. Your notes for the topic are shown underneath. Keep this open beside the Terminal. |
| **My Notes** | Your notes, one page per subtopic, **built as you learn**. Each idea gets its short summary, your own words, and a "Watch out" list of the mistakes *you* made. At the top is a coloured map of the topic. |
| **Lessons** | A full record of every session: explanations, every question (shown before you answer, never with the answer), your answers and the feedback. Great for looking back. |
| **Home** | A dashboard: progress per subtopic, reviews due, links to your notes and recent lessons. |
| **Subjects** | Complete reference notes for each subtopic, written in advance and checked. Read these whenever you want the whole topic in one place. |
| **Profile** and **Today** | What the tutor has learned about how you learn best, and today's suggested plan. Updated after sessions. |
| **Anki** | Flashcard files (see section 8). |

**Colours in the map and headings:** ✅ green = secure, 🟡 yellow = learning, 🔴 red = a gap to fix, ⚪ grey = not started, 🔵 blue = the idea you're on now.

You can add your own writing to **My Notes** anywhere outside the grey markers (the lines starting `<!-- stem-tutor`). The tutor only rewrites what's between its markers.

---

## 7. Reviews, memory and "secure"

Everyone forgets. The tutor uses the same method as Anki's modern scheduler (called FSRS) to predict when *you* are about to forget each idea, and asks you about it just before that. Each time you get it right, the gap before the next review grows (days, then weeks, then months). Each time you slip, it comes back sooner.

An idea counts as **secure** when you've answered it correctly **without help on at least two different days** and your overall record on it is strong. Reviews also mix topics together, which feels harder but builds exactly the skill exams test: recognising *which* idea a question needs.

**Test prep** is different: it's for a test coming up soon. It asks one question on every point of the chapters you choose, then reteaches only what you missed and re-checks it. Anything still weak is saved and comes back later.

---

## 8. Your profile, experiments and Anki

**The tutor learns how you learn.** For each idea it chooses a teaching method based on research (for example, worked examples first for new procedures, or "try the problem first" once you know the basics). Occasionally it runs a fair **experiment** on you: it teaches similar ideas in two different ways and checks a week later which ones you remember better. When it's confident one way works better for you, it switches to it. The results are in **Profile**.

It also tracks how well your confidence matches reality, the kinds of mistakes you make (careless slip, misread question, wrong method, a misconception…), and how fast you forget each subject.

**Anki:** about once a week, after a session, the tutor exports new flashcards for facts and definitions you've met as a file in the **Anki** folder (the summary screen tells you). Double-click it to add them to Anki. Cards you already have in Anki aren't duplicated.

---

## 9. Keys

| Key | What it does |
|---|---|
| **↑ ↓** then **⏎** | Choose / continue |
| **A B C D** | Pick that option |
| **0** | I don't know |
| **1 2 3 4** | Confidence: guess / unsure / fairly sure / certain |
| **space** | Tick or untick a box |
| **Tab** | Move to the next box or button |
| **t** | Ask the tutor a question (AI) |
| **e** | Explain this idea a different way (AI) |
| **h** | Hint (not allowed on no-hints checks) |
| **o** | Show the current question or explanation in Obsidian |
| **ctrl+s** | Submit a long answer |
| **ctrl+q** | Save and go back to the menu (you can resume later) |
| **?** | Help · **F2** Settings (from the menu) · **q** Quit (from the menu) |

---

## 10. The AI, and your Claude usage limit

Most of the tutor needs **no AI at all**: choosing questions, marking multiple choice and numbers, scheduling reviews, the lessons' explanations (written in advance and checked), your notes and records. That's why it's quick and cheap.

The AI (Claude, using your normal Claude subscription) is only used when it genuinely helps:

- when you **ask a question** (**t**) or chat from the menu,
- when you ask for an idea **explained a different way** (**e**) or for a past-paper answer to be explained,
- short feedback on your **"in your own words"** answers (you can turn this off),
- judging **written answers** and checking **long answers** (the AI examiner),
- talking an idea through with you when you're **stuck**,
- writing a teaching card for an idea that doesn't have one yet (once; it's saved).

It runs quietly in the background: you don't need the Claude app open. It uses the small, fast **Haiku** model by default, sends only the few lines it needs each time, and forgets the chat whenever a new idea starts, so each request stays small.

**The top bar** shows `AI ●` (on) or `AI ○` (off), plus how many AI replies and tokens this session used. **Settings (F2)** let you: turn the AI off completely, turn off own-words feedback, choose Sonnet (clearer but uses about three times more of your limit), and set a **daily allowance** of AI replies (default 80) so the tutor can never eat your limit.

If your Claude limit is reached, the tutor tells you when it resets and simply carries on without AI. If it says you need to sign in, type `claude auth login` in Terminal once.

> [!warning] Questions that are still open
> While a question is waiting for your answer, the AI won't tell you the answer, even if you ask. Use a hint (**h**) or answer first; then it will explain.

---

## 11. Where everything lives

- **This vault (your data):** `Miscellaneous › 02 Education › ~~ AI Workflow › STEM Tutor`. Everything you see in Obsidian, plus the hidden `.tutor` folder with your progress (every answer you've ever given is recorded there, so nothing is lost). Don't edit `.tutor` by hand.
- **The program:** `~~ AI Workflow › stem-tutor`. You don't need to open it.
- **iPad inbox:** `iCloud Drive › STEM Tutor Inbox` (only for PDFs from the iPad).
- The old copy in your main Obsidian vault (`Notes › 01 Study › STEM Tutor`) is no longer used; it has a MOVED note. You can delete it once you're happy.

---

## 12. If something goes wrong

| Problem | Fix |
|---|---|
| The top bar says **AI ○** or "sign-in needed" | In Terminal: `claude auth login`. Or AI is switched off in Settings (F2). |
| "AI paused (limit)" | Your Claude usage limit is reached. Keep going without AI; it comes back after the reset time shown. |
| Obsidian doesn't jump to **Now** | Open this folder as a vault once (section 1). Or press **o** in the tutor, or open **Now** yourself. |
| The Terminal window is small | Drag it bigger or maximise it: the tutor re-fits instantly. |
| "Another STEM Tutor window is already open" | Use the other window, or close it first. Only one can run at a time so your progress can't get mixed up. |
| A question or answer looks wrong | Answer it anyway and press **t** to ask why; note it down. Content can be corrected in the next update. |
| Anything else | Run the doctor check (section 1). It tells you exactly what's wrong and how to fix it. |

---

## 13. Words you'll see

- **Idea** (in the code, a *KC*): one point from the syllabus, like "define displacement".
- **Subtopic:** a group of ideas, like "2.1 Equations of motion".
- **Probe:** the quick check at the start of a lesson.
- **Due:** an idea the tutor wants to refresh now, before you forget it.
- **Secure / learning / gap:** how well you know an idea (section 7).
- **Confidence:** how sure you said you were. The tutor compares it with how often you're right.
- **Misconception / trap:** a common wrong idea (for example "distance and displacement are the same thing"). Wrong multiple-choice answers are designed around these, so a wrong choice tells the tutor exactly what to fix.
- **Hypercorrection:** the finding that confidently-wrong answers, once corrected, are remembered especially well, which is why the tutor pauses on them.
- **Worked → faded example:** a solved example, then a similar one where you do more of the steps yourself.
