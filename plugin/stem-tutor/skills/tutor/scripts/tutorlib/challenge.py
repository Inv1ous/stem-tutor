"""Challenge mode, the config half: difficulty levels and ramps, the learner's request in plain words, the
solvability scope (what a question may rely on) and the stored sets of pre-generated questions with their results.

Question dicts in a set come from the generator; this module only plans for them and stores them.
"""
from __future__ import annotations

import random
import re

from .store import Vault, read_json, write_json

LEVELS: list[dict] = [
    {"level": 1, "name": "Warm-up", "blurb": "Quick and friendly: one idea, one step.", "exam_chance": "every paper"},
    {"level": 2, "name": "Standard", "blurb": "A typical exam question you can do once you know the topic.", "exam_chance": "every paper"},
    {"level": 3, "name": "Solid", "blurb": "A few steps, and you must pick the right method yourself.", "exam_chance": "every paper"},
    {"level": 4, "name": "Demanding", "blurb": "Several linked steps; careless slips will cost you.", "exam_chance": "most papers"},
    {"level": 5, "name": "Exam-hard", "blurb": "The hard end of what a real paper asks.", "exam_chance": "once a paper"},
    {"level": 6, "name": "Top of the paper", "blurb": "The last question that separates the A* from the A.", "exam_chance": "once in a while"},
    {"level": 7, "name": "Rare in exams", "blurb": "Needs a clever idea or a long chain; most students stall.", "exam_chance": "very rarely"},
    {"level": 8, "name": "Beyond the exam", "blurb": "Harder than any paper, but only uses the A-level syllabus.", "exam_chance": "almost never"},
    {"level": 9, "name": "Extreme", "blurb": "Olympiad-flavoured: several ideas combined in an unusual way.", "exam_chance": "never, but learnable"},
    {"level": 10, "name": "Impossible", "blurb": "Far too hard for A-level, yet still solvable with what you know.", "exam_chance": "never, but learnable"},
]

RAMPS: dict[str, str] = {
    "steady": "Climb evenly from the easiest level to the hardest.",
    "fast-then-slow": "Jump quickly to hard questions, then creep up slowly towards the extreme at the end.",
    "slow-then-fast": "Stay gentle for a long while, then shoot up to the hardest at the end.",
    "hardest-first": "Start at the hardest level and work down to the easiest.",
    "easiest-first-jump": "One easy question to settle in, then jump straight to the middle and climb to the top.",
    "wave": "Alternate harder and easier questions, trending upward.",
    "random": "All levels in the range, in a shuffled order.",
    "flat": "Every question at the hardest level.",
}

DEFAULT_CONFIG: dict = {"topics": [], "count": 10, "kinds": "mix", "typed_share": 0.5, "lo": 4, "hi": 8,
                        "ramp": "steady", "model": "sonnet", "maths_forms": True}
KINDS = ("mcq", "typed", "mix")
MODELS = ("sonnet", "opus")
MAX_COUNT = 30


# ---------------- difficulty ramps ----------------
def _clamp(x: int, lo: int, hi: int) -> int:
    return max(lo, min(hi, x))


def ramp_levels(n: int, shape: str, lo: int, hi: int, seed: int | None = None) -> list[int]:
    """n levels (each 1..10, within lo..hi) following the ramp shape; an unknown shape counts as steady.

    A single question is always at hi, whatever the shape. Rising shapes start at lo and end at hi;
    hardest-first runs hi down to lo; flat is all hi; random shuffles the steady spread (seed makes it repeatable).
    """
    lo, hi = sorted((_clamp(int(lo), 1, 10), _clamp(int(hi), 1, 10)))
    if n <= 0:
        return []
    if n == 1 or shape == "flat":
        return [hi] * n
    span = hi - lo
    out = []
    for i in range(n):
        t = i / (n - 1)
        if shape == "fast-then-slow":
            f = 1 - (1 - t) ** 2  # steep at first, flattening towards the end
        elif shape == "slow-then-fast":
            f = t ** 2
        elif shape == "hardest-first":
            f = 1 - t
        elif shape == "easiest-first-jump":
            f = 0.0 if i == 0 else 0.5 + 0.5 * (i - 1) / (n - 2) if n > 2 else 1.0
        elif shape == "wave":
            f = t if i in (0, n - 1) else t + (0.15 if i % 2 else -0.15)
        else:  # steady, random
            f = t
        out.append(_clamp(lo + round(span * min(1.0, max(0.0, f))), lo, hi))
    if shape == "random":
        random.Random(seed).shuffle(out)
    return out


# ---------------- config ----------------
def _int(v, default: int) -> int:
    try:
        return int(float(v))
    except (TypeError, ValueError):
        return default


def normalise_config(cfg: dict, packs) -> tuple[dict, list[str]]:
    """The config with every setting in range, and plain-English notes of what had to change."""
    out, notes = {**DEFAULT_CONFIG, **{k: v for k, v in (cfg or {}).items() if k in DEFAULT_CONFIG}}, []
    raw = out["topics"]
    raw = [raw] if isinstance(raw, str) else list(raw or [])
    known = [t for t in dict.fromkeys(raw) if t in packs.subtopics]
    if len(known) != len(set(raw)):
        notes.append("Left out unknown topics: " + ", ".join(sorted(set(raw) - set(known))))
    out["topics"] = known
    count = _clamp(_int(out["count"], DEFAULT_CONFIG["count"]), 1, MAX_COUNT)
    if count != out["count"]:
        notes.append(f"Number of questions set to {count} (allowed 1 to {MAX_COUNT}).")
    out["count"] = count
    lo, hi = (_clamp(_int(out[k], DEFAULT_CONFIG[k]), 1, 10) for k in ("lo", "hi"))
    swapped = lo > hi
    lo, hi = sorted((lo, hi))
    if (lo, hi) != (out["lo"], out["hi"]):
        notes.append(f"Difficulty range set to levels {lo} to {hi}" + (" (swapped)." if swapped else " (allowed 1 to 10)."))
    out["lo"], out["hi"] = lo, hi
    try:
        share = min(1.0, max(0.0, float(out["typed_share"])))
    except (TypeError, ValueError):
        share = DEFAULT_CONFIG["typed_share"]
    if share != out["typed_share"]:
        notes.append(f"Share of typed answers set to {share:g}.")
    out["typed_share"] = share
    for key, allowed in (("kinds", KINDS), ("model", MODELS)):
        val = str(out[key]).strip().lower()
        if val not in allowed:
            notes.append(f"{key} '{out[key]}' not recognised: using {DEFAULT_CONFIG[key]}.")
            val = DEFAULT_CONFIG[key]
        out[key] = val
    ramp = str(out["ramp"]).strip().lower().replace(" ", "-").replace("_", "-")
    if ramp not in RAMPS:
        notes.append(f"Ramp '{out['ramp']}' not recognised: using {DEFAULT_CONFIG['ramp']}.")
        ramp = DEFAULT_CONFIG["ramp"]
    out["ramp"] = ramp
    out["maths_forms"] = bool(out["maths_forms"])
    return out, notes


def plan_slots(cfg: dict, seed: int | None = None) -> list[dict]:
    """One slot per question: {"n", "level", "kind"}. Typed questions are spread evenly through the set."""
    n = int(cfg["count"])
    kinds = cfg.get("kinds", "mix")
    share = {"mcq": 0.0, "typed": 1.0}.get(kinds, float(cfg.get("typed_share", 0.5)))
    typed = _clamp(int(n * share + 0.5), 0, n)
    levels = ramp_levels(n, cfg.get("ramp", "steady"), cfg.get("lo", 4), cfg.get("hi", 8), seed)
    return [{"n": i + 1, "level": levels[i], "kind": "typed" if (i + 1) * typed // n > i * typed // n else "mcq"}
            for i in range(n)]


def _config_path(vault: Vault):
    return vault.tutor / "challenge" / "settings" / "last.json"  # a folder of its own: sets are challenge/*.json


def load_config(vault: Vault, packs) -> dict:
    """The settings used last time (normalised: a topic since removed is dropped), else the defaults."""
    try:
        saved = read_json(_config_path(vault))
    except (ValueError, OSError):
        saved = None
    return normalise_config(saved if isinstance(saved, dict) else {}, packs)[0]


def save_config(vault: Vault, cfg: dict) -> None:
    """Remember these settings for the next visit. A vault that cannot be written just forgets them."""
    try:
        write_json(_config_path(vault), {k: cfg[k] for k in DEFAULT_CONFIG if k in cfg})
    except OSError:
        pass


# ---------------- scope: what a question may rely on ----------------
def _key(subtopic: str) -> tuple[int, ...]:
    """'9702-10.1' -> (10, 1); 'P1-2' -> (2,). Numeric, so chapter 10 comes after chapter 5."""
    return tuple(int(x) for x in re.findall(r"\d+", subtopic.split("-", 1)[-1]))


def allowed_scope(packs, topics: list[str]) -> list[dict]:
    """Every idea (KC) a question on these subtopics may use, in graph order, each as
    {id, spec, subtopic, title, statement, type, chosen}.

    That is: the chosen subtopics, plus every earlier subtopic of the same spec, plus the transitive closure of the
    prereqs of all of those (which may lie in another spec, e.g. physics needing P1 maths). "Earlier" compares the
    numeric part of the subtopic id within one spec ('9702-10.1' after '9702-5.1'). The maths units (P1..P4, M1,
    S1.., FP1.., D1) are separate specs with ids like 'P1-2': earlier chapters of the same unit count, and other
    units (P1 under P2) enter only through the prereqs the graph states.
    """
    chosen = {t for t in topics if t in packs.subtopics}
    reach = {(packs.subtopics[t]["spec"], _key(t)) for t in chosen}
    ids = {k for k, kc in packs.kcs.items()
           if any(kc["spec"] == s and _key(kc["subtopic"]) <= key for s, key in reach)}
    todo = list(ids)
    while todo:
        for p in packs.kcs[todo.pop()].get("prereqs", []):
            if p in packs.kcs and p not in ids:
                ids.add(p)
                todo.append(p)
    return [{"id": k, "spec": kc["spec"], "subtopic": kc["subtopic"], "title": kc["title"],
             "statement": kc["statement"], "type": kc.get("type", ""), "chosen": kc["subtopic"] in chosen}
            for k, kc in packs.kcs.items() if k in ids]


SUBJECTS = {"chem": "Chemistry", "phys": "Physics", "math": "Maths"}


def scope_summary(packs, topics: list[str]) -> str:
    """'Physics 9702-5.1 plus earlier chapters (62 ideas)'."""
    chosen = [t for t in dict.fromkeys(topics) if t in packs.subtopics]
    if not chosen:
        return "No topics chosen"
    scope = allowed_scope(packs, chosen)
    subject = {kc["subtopic"]: kc["subject"] for kc in packs.kcs.values()}
    by_subject: dict[str, list[str]] = {}
    for t in chosen:
        sub = subject.get(t, "")
        by_subject.setdefault(SUBJECTS.get(sub, sub.title()), []).append(t)
    head = "; ".join(f"{name} {', '.join(ts)}".strip() for name, ts in by_subject.items())
    more = sum(1 for k in scope if not k["chosen"])
    return f"{head}{' plus earlier chapters' if more else ''} ({len(scope)} idea{'s' if len(scope) != 1 else ''})"


def topic_choices(packs) -> list[dict]:
    """Every subtopic that has at least one idea, built (has a question pack) or not, for a picker."""
    with_kcs = {kc["subtopic"] for kc in packs.kcs.values()}
    built = packs.published()
    rows = [{"id": s, "spec": st["spec"], "title": st["title"], "built": s in built, "label": f"{s}  {st['title']}"}
            for s, st in packs.subtopics.items() if s in with_kcs]
    return sorted(rows, key=lambda r: (r["spec"], _key(r["id"])))


# ---------------- reading the learner's words ----------------
_ONES = ["one", "two", "three", "four", "five", "six", "seven", "eight", "nine", "ten", "eleven", "twelve",
         "thirteen", "fourteen", "fifteen", "sixteen", "seventeen", "eighteen", "nineteen"]
WORD_NUMBERS = {w: i + 1 for i, w in enumerate(_ONES)}
WORD_NUMBERS.update({"twenty": 20, "thirty": 30})
WORD_NUMBERS.update({f"twenty {o}": 21 + i for i, o in enumerate(_ONES[:9])})
_NUM = "|".join(w.replace(" ", "[ -]") for w in sorted(WORD_NUMBERS, key=len, reverse=True)) + r"|\d{1,3}"
_COUNT = re.compile(rf"\b({_NUM})\s+(?:[a-z-]+\s+){{0,3}}?(?:questions?|qs?|problems?|mcqs?)\b")

_LEVEL_WORDS = [  # (pattern, level), longest first
    (r"warm[- ]?up", 1), (r"standard", 2), (r"solid", 3), (r"demanding", 4), (r"exam[- ]hard", 5),
    (r"top of the paper", 6), (r"rare in (?:the )?exams?", 7), (r"beyond(?: the exams?)?", 8),
    (r"extreme(?:ly)?", 9), (r"impossible", 10), (r"easy|easiest", 1), (r"hard", 5),
]
_LEVEL_RE = re.compile(r"\b(?:levels?|difficulty|tiers?)\s*(\d{1,2})(?:\s*(?:to|-|–|through|until|and)\s*(?:level\s*)?(\d{1,2}))?\b"
                       r"|\b(" + "|".join(f"(?:{p})" for p, _ in _LEVEL_WORDS) + r")\b")
_NO_LEVEL = {"easy", "easiest", "hard"}  # filler unless they sit among other level words
_RAMP_PHRASES = [
    ("hardest-first", r"hardest first|hardest to easiest|start(?:ing)? (?:with )?the hardest|descending|get(?:s|ting)? easier|work(?:ing)? down|reverse order"),
    ("easiest-first-jump", r"easiest first|easy first|one easy (?:one |question )?first|(?:a|one) warm[- ]?up (?:then|and then) jump"),
    ("wave", r"wave|zig-?zag|up and down|ups and downs|roller ?coaster|alternat\w*"),
    ("random", r"random\w*|shuffl\w*|in any order|jumbled|mixed(?: up)? difficult\w*"),
    ("flat", r"flat|all (?:of them |the questions |questions )?at|everything at|all the same|same difficulty|constant\w*"),
]
_FAST = r"(?:fast|quick\w*|rapid\w*|sharp\w*|steep\w*|jump\w*|straight to)"
_SLOW = r"(?:slow\w*|gentl\w*|creep\w*|gradual\w*|ease[- ]in)"
_STEADY = r"steady|steadily|evenly|linear\w*|gradual\w*|progressive\w*|ramp(?:ing)? up|get(?:ting)? harder|increasing\w*|build(?:ing)? up|climb\w*"
_SUBJECT_SPECS = {"chem": {"9701"}, "chemistry": {"9701"}, "phys": {"9702"}, "physics": {"9702"}}
_MATHS = {"maths", "math", "mathematics", "pure", "mechanics", "statistics", "stats"}
_STOP = set("""a an and are as at be but by can do for from get give go has have i in is it its just make me more my not of
on one only or please some questions question q qs problems problem set so some than that the then there these this
those to up use want we what when which will with would you your hard harder hardest easy easier easiest start starting
begin begins level levels difficulty tier tiers chapter topic section unit ch quickly slowly towards toward through
mcq mcqs typed type answers answer options multiple choice mix mixed both half fast slow steady steadily wave random
flat go goes finish end ending finishing ramp jump jumps order first climb calculation calculations""".split())


def _words(text: str) -> list[str]:
    return re.findall(r"[a-z]+|\d+(?:\.\d+)?", text)


def parse_request(text: str, packs) -> dict:
    """Read a request in plain English into a config. Returns {"config": only the settings found,
    "understood": [what was taken], "unclear": [what was not]}. Deterministic (no AI); never raises."""
    try:
        return _parse(str(text), packs)
    except Exception as e:  # a request must never crash the app; say it was not read
        return {"config": {}, "understood": [], "unclear": [f"Could not read that request ({type(e).__name__}): {text!r}"]}


def _parse(raw: str, packs) -> dict:
    s = raw.lower().replace("–", "-")
    cfg: dict = {}
    got: list[str] = []
    unclear: list[str] = []

    def take(pattern: str, flags: int = 0) -> list[re.Match]:
        nonlocal s
        found = list(re.finditer(pattern, s, flags))
        for m in found:
            s = s[:m.start()] + " " * (m.end() - m.start()) + s[m.end():]
        return found

    valid = {r["id"] for r in topic_choices(packs)}
    subject_of = {r["id"]: r["spec"] for r in topic_choices(packs)}

    # --- topics by id ('9702-5.1', 'p1-2', '9702-5' for the whole chapter)
    topics: list[str] = []
    for m in take(r"\b(9701|9702|fp\d|[pmsd]\d)-(\d+(?:\.\d+)?)\b"):
        tid = f"{m[1].upper()}-{m[2]}"
        hits = [tid] if tid in valid else sorted((v for v in valid if v.startswith(tid + ".")), key=_key)
        if hits:
            topics += hits
            got.append(f"topic {tid}" + (f" ({len(hits)} chapters)" if len(hits) > 1 else ""))
        else:
            unclear.append(f"Topic {tid} is not in the syllabus graph.")
    # --- topics by number and subject ('chapter 3.1 chemistry', 'chapter 3 physics')
    subjects = [(m.start(), m[0]) for m in re.finditer(r"\b(?:chemistry|chem|physics|phys|maths|math|mathematics)\b", s)]
    for m in take(r"(?:\b(?:chapter|ch|topic|section|unit)\.?\s*)?(?<![\d.\-])(\d{1,2}\.\d{1,2})(?![\d.%])"
                  r"|\b(?:chapter|ch|topic|section|unit)\.?\s*(\d{1,2})\b(?![.\d%])"):
        num = m[1] or m[2]
        near = [w for p, w in subjects if -25 <= p - m.start() <= 25]
        word = near[0] if near else (subjects[0][1] if len({w for _, w in subjects}) == 1 else None)
        specs = _SUBJECT_SPECS.get(word) if word and word not in _MATHS else None
        if "." in num:
            cands = [v for v in valid if v.split("-", 1)[1] == num and (specs is None or subject_of[v] in specs)]
        else:  # a whole chapter: all its subtopics (physics and chemistry number their chapters)
            cands = [v for v in valid if subject_of[v] in ("9701", "9702") and v.split("-", 1)[1].split(".")[0] == num
                     and (specs is None or subject_of[v] in specs)]
        chapters = {subject_of[v] for v in cands}
        if not cands:
            unclear.append(f"No chapter {num}{' in ' + word if word else ''} was found.")
        elif ("." in num and len(cands) > 1) or ("." not in num and len(chapters) > 1):
            unclear.append(f"{num} could be {', '.join(sorted(cands, key=_key))}: say which subject.")
        else:
            topics += sorted(cands, key=_key)
            got.append(f"topic {cands[0]}" if len(cands) == 1 else f"chapter {num} ({len(cands)} sub-chapters)")
    if topics:
        take(r"\b(?:chemistry|chem|physics|phys|maths|math|mathematics)\b")
        cfg["topics"] = list(dict.fromkeys(topics))

    # --- model
    models = [m[1] for m in take(r"\b(opus|sonnet)\b")]
    if len(set(models)) == 1:
        cfg["model"] = models[0]
        got.append(f"model {models[0]}")
    elif models:
        unclear.append("Both Sonnet and Opus were mentioned: pick one.")

    # --- ramp
    ramp = None
    for shape, pat in _RAMP_PHRASES:
        if take(rf"\b(?:{pat})\b"):
            ramp = shape
            break
    if ramp is None:
        fast, slow = re.search(rf"\b{_FAST}\b", s), re.search(rf"\b{_SLOW}\b", s)
        if re.search(r"\bfront[- ]loaded\b", s):
            ramp = "fast-then-slow"
        elif re.search(r"\bback[- ]loaded\b", s):
            ramp = "slow-then-fast"
        elif fast and slow and fast.start() != slow.start():
            ramp = "fast-then-slow" if fast.start() < slow.start() else "slow-then-fast"
            take(rf"\b{_FAST}\b")
            take(rf"\b{_SLOW}\b")
        elif fast and not slow:  # 'start easy, jump to hard fast, end extreme'
            ramp = "fast-then-slow"
            take(rf"\b{_FAST}\b")
        elif take(rf"\b(?:{_STEADY})\b"):
            ramp = "steady"
    if ramp:
        cfg["ramp"] = ramp
        got.append(f"ramp {ramp}")

    # --- difficulty levels
    cues: list[tuple[int, int, str]] = []  # (position, level, how it was said)
    floor = take(r"\b(?:(?:levels?|difficulty|tiers?)\s*)?(\d{1,2})\s*(?:\+|plus\b|(?:and|or) (?:above|up|harder)\b"
                 r"|upwards?\b)")  # 'level 7 and above', '7+': the lowest level only
    for m in take(_LEVEL_RE.pattern):
        if m[3] is None:
            for g in (m[1], m[2]):
                if g:
                    cues.append((m.start(), int(g), "number"))
        else:
            word = m[3]
            level = next(lv for p, lv in _LEVEL_WORDS if re.fullmatch(p, word))
            cues.append((m.start(), level, "generic" if word in _NO_LEVEL else "named"))
    before = raw.lower()
    if floor and not any(c[2] == "number" for c in cues):
        cfg["lo"] = min(10, int(floor[0][1]))
        got.append(f"level from {cfg['lo']}")
    elif len(cues) >= 2 or any(c[2] != "generic" for c in cues):
        levels = [c[1] for c in cues]
        lo, hi = min(levels), max(levels)
        if len(cues) == 1 and ramp == "hardest-first":
            lo = None  # 'start extreme and get easier' names only the top
        elif len(cues) == 1:
            lead = before[max(0, cues[0][0] - 18):cues[0][0]]
            if re.search(r"(?:up to|at most|max\w*|no harder than|until|capped at)\s*(?:level\s*)?$", lead):
                lo = None
            elif re.search(r"(?:from|starting at|at least|min\w*|no easier than)\s*(?:level\s*)?$", lead):
                hi = None
        if lo is not None:
            cfg["lo"] = lo
        if hi is not None:
            cfg["hi"] = hi
        a, b = (lo if lo is not None else "?"), (hi if hi is not None else "?")
        got.append("level " + (str(a) if a == b else f"{a} to {b}" if lo is not None and hi is not None
                                else f"up to {b}" if lo is None else f"from {a}"))

    # --- number of questions (after levels so 'level 6 to 9' is not a count)
    m = _COUNT.search(s)
    if m:
        count = int(m[1]) if m[1].isdigit() else WORD_NUMBERS[re.sub(r"[ -]+", " ", m[1])]
        cfg["count"] = count
        got.append(f"{count} question{'s' if count != 1 else ''}")
        s = s[:m.start(1)] + " " * (m.end(1) - m.start(1)) + s[m.end(1):]

    # --- kinds
    share = re.search(r"(\d{1,3})\s*%\s*(typed|mcq|multiple choice)", s)
    if share:
        pct = min(100, int(share[1])) / 100
        cfg.update(kinds="mix", typed_share=pct if share[2] == "typed" else 1 - pct)
        got.append(f"{share[1]}% {share[2]}")
        take(r"\d{1,3}\s*%\s*(?:typed|mcq|multiple choice)")
    elif take(r"\b(?:mostly|mainly|more|largely)\s+(?:typed|written|numeric\w*)\b"):
        cfg.update(kinds="mix", typed_share=0.75)
        got.append("mostly typed")
    elif take(r"\b(?:mostly|mainly|more|largely)\s+(?:mcqs?|multiple[- ]choice|options)\b"):
        cfg.update(kinds="mix", typed_share=0.25)
        got.append("mostly multiple choice")
    elif take(r"\b(?:half and half|half[- ]half|50[/-]50|an even mix|equal mix|a mix|mix of both|mixed|mix|both)\b"):
        cfg.update(kinds="mix", typed_share=0.5)
        got.append("a mix of multiple choice and typed")
    elif take(r"\b(?:no|without|not|zero)\s+(?:any\s+)?(?:mcqs?|multiple[- ]choice(?: questions)?)\b"):
        cfg["kinds"] = "typed"
        got.append("typed answers only")
    else:
        typed = take(r"\b(?:typed|type[- ]in|written answers?|numeric\w*|no options|no choices)\b")
        mcq = take(r"\b(?:mcqs?|multiple[- ]choice|options)\b")
        if typed and mcq:
            cfg.update(kinds="mix", typed_share=0.5)
            got.append("a mix of multiple choice and typed")
        elif typed or mcq:
            cfg["kinds"] = "typed" if typed else "mcq"
            got.append("typed answers only" if typed else "multiple choice only")

    # --- whatever is left over
    run: list[str] = []
    for w in _words(s) + [""]:
        if w and (w not in _STOP and w not in WORD_NUMBERS or w[0].isdigit()):
            run.append(w)
        elif run:
            unclear.append("Not understood: " + " ".join(run))
            run = []
    return {"config": cfg, "understood": got, "unclear": unclear}


# ---------------- stored sets ----------------
class ChallengeSet:
    """One pre-generated set of questions with the learner's answers, kept in <vault>/.tutor/challenge/<id>.json."""

    def __init__(self, vault: Vault, set_id: str | None = None):
        self.vault = vault
        self.folder = vault.tutor / "challenge"
        self.id = set_id or f"{vault.now():%Y%m%d-%H%M%S}"
        self.created = vault.now().isoformat(timespec="seconds")
        self.cfg: dict = {}
        self.questions: list[dict] = []
        self.answers: list[dict] = []
        self.closed = False
        if set_id:
            data = read_json(self.path)
            if data is None:
                raise FileNotFoundError(f"No challenge set {set_id}")
            if not (isinstance(data, dict) and isinstance(data.get("cfg"), dict)
                    and isinstance(data.get("questions"), list) and isinstance(data.get("answers"), list)
                    and all(isinstance(q, dict) and isinstance(q.get("item"), dict) for q in data["questions"])):
                raise ValueError(f"Challenge set {set_id} is damaged")
            self.created = str(data.get("created", ""))
            self.cfg, self.questions = data["cfg"], data["questions"]
            n = len(self.questions)
            self.answers = [a for a in data["answers"] if isinstance(a, dict) and isinstance(a.get("index"), int)
                            and 0 <= a["index"] < n and isinstance(a.get("grade"), dict)]  # a damaged answer is dropped
            self.closed = bool(data.get("closed"))

    @property
    def path(self):
        return self.folder / f"{self.id}.json"

    @classmethod
    def new(cls, vault: Vault, cfg: dict, questions: list[dict]) -> ChallengeSet:
        s = cls(vault)
        while s.path.exists():  # two sets in the same second
            s.id += "x"
        s.cfg, s.questions = dict(cfg), list(questions)
        s._save()
        return s

    @classmethod
    def all(cls, vault: Vault) -> list[dict]:
        """Summaries of the stored sets, newest first. A damaged file is skipped: this never raises."""
        out = []
        for path in sorted((vault.tutor / "challenge").glob("*.json"), reverse=True):
            try:
                s = cls(vault, path.stem)
                sm = s.summary()
            except Exception:  # noqa: BLE001 - one bad file must not keep the learner out of every set
                continue
            out.append({"id": s.id, "created": s.created, "count": len(s.questions), "answered": sm["answered"],
                        "correct": sm["correct"], "topics": s.cfg.get("topics", [])})
        return out

    @classmethod
    def open_latest_unfinished(cls, vault: Vault) -> ChallengeSet | None:
        """The newest set still to finish: not all answered, and not stopped or set aside (closed)."""
        for row in cls.all(vault):
            if row["answered"] < row["count"]:
                try:
                    s = cls(vault, row["id"])
                except Exception:  # noqa: BLE001 - changed since it was listed
                    continue
                if not s.closed:
                    return s
        return None

    def close(self) -> None:
        """Stopped early or set aside for a new one: it is no longer offered to continue."""
        self.closed = True
        self._save()

    @property
    def cursor(self) -> int:
        """Index of the first unanswered question (the number of questions when all are answered)."""
        done = {a["index"] for a in self.answers}
        return next((i for i in range(len(self.questions)) if i not in done), len(self.questions))

    def _save(self) -> None:
        write_json(self.path, {"id": self.id, "created": self.created, "cfg": self.cfg,
                               "questions": self.questions, "answers": self.answers,
                               **({"closed": True} if self.closed else {})})

    def _answer(self, index: int) -> dict | None:
        return next((a for a in self.answers if a["index"] == index), None)

    def record(self, index: int, response: str, grade: dict, seconds: int, confidence: int | None = None) -> None:
        """Save the answer to question `index` (0-based; answering again replaces it) and log one event."""
        if not 0 <= index < len(self.questions):
            raise IndexError(f"No question {index} in set {self.id}")
        q = self.questions[index]
        entry = {"index": index, "response": response, "grade": grade, "seconds": seconds, "confidence": confidence}
        self.answers = sorted([a for a in self.answers if a["index"] != index] + [entry], key=lambda a: a["index"])
        self._save()
        self.vault.append_event({"type": "challenge", "set": self.id, "n": q.get("n", index + 1), "level": q.get("level"),
                                 "kind": q.get("kind"), "correct": bool(grade.get("correct")), "seconds": seconds,
                                 "conf": confidence, "concepts": q.get("concepts", [])})

    def regrade(self, index: int, why: str) -> bool:
        """An AI re-mark found the answer right: mark it correct and log it. Once only: a second call changes
        nothing and returns False."""
        a = self._answer(index)
        if a is None:
            raise ValueError(f"Question {index} of set {self.id} has not been answered")
        if "regraded" in a:
            return False
        a["grade"] = {**a["grade"], "correct": True, "score": 1.0}
        a["regraded"] = why
        self._save()
        self.vault.append_event({"type": "challenge_regrade", "set": self.id, "n": self.questions[index].get("n", index + 1),
                                 "why": why})
        return True

    def summary(self) -> dict:
        """{answered, correct, by_level: {level: [right, total]}, best_level (highest level got right), seconds}."""
        by_level: dict[int, list[int]] = {}
        for a in self.answers:
            level = self.questions[a["index"]].get("level")
            level = level if isinstance(level, int) else None
            row = by_level.setdefault(level, [0, 0])
            row[0] += bool(a["grade"].get("correct"))
            row[1] += 1
        right = [lv for lv, (r, _) in by_level.items() if r and lv is not None]
        return {"answered": len(self.answers), "correct": sum(r for r, _ in by_level.values()),
                "by_level": dict(sorted(by_level.items(), key=lambda kv: kv[0] or 0)),
                "best_level": max(right, default=None), "seconds": sum(a.get("seconds") or 0 for a in self.answers)}
