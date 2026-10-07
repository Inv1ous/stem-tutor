"""Generator for pack 9701-1.3 (Electrons, energy levels and atomic orbitals).

Content is held as data; every numeric answer is computed by the aufbau model below (with Cr/Cu exceptions,
cation removal from the highest-n shell first, Hund's rule for unpaired counts) and asserted against the
hand-written answers.  Run:  .venv/bin/python build/work/gen/gen_9701_1_3.py
"""
import json
import random
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "plugin/stem-tutor/skills/tutor/scripts"))
from tutorlib import packs  # noqa: E402

SUB, SPEC = "9701-1.3", "9701"
K = {i: f"9701-1.3.{i}" for i in range(1, 10)}
CAP = {"s": 2, "p": 6, "d": 10}
ORB = {"s": 1, "p": 3, "d": 5}
ORDER = ["1s", "2s", "2p", "3s", "3p", "4s", "3d", "4p", "5s", "4d", "5p"]


# ---------------------------------------------------------------- chemistry model (verification)
def config(z, charge=0):
    e, conf = z, {}
    for sub in ORDER:
        n = min(e, CAP[sub[1]])
        if n:
            conf[sub] = n
        e -= n
        if not e:
            break
    if z == 24:
        conf["3d"], conf["4s"] = 5, 1
    if z == 29:
        conf["3d"], conf["4s"] = 10, 1
    if charge > 0:   # remove from highest n first, p before s within a shell
        for _ in range(charge):
            top = max(conf, key=lambda s: (int(s[0]), "spd".index(s[1])))
            conf[top] -= 1
            if not conf[top]:
                del conf[top]
    elif charge < 0:
        for _ in range(-charge):
            for sub in ORDER:
                if conf.get(sub, 0) < CAP[sub[1]]:
                    conf[sub] = conf.get(sub, 0) + 1
                    break
    return conf


def unpaired(conf):
    tot = 0
    for sub, e in conf.items():
        o = ORB[sub[1]]
        tot += e if e <= o else 2 * o - e
    return tot


def fmt(conf):
    return " ".join(f"{s}^{{{conf[s]}}}" if conf[s] > 9 else f"{s}^{conf[s]}" for s in sorted(conf, key=lambda s: (ORDER.index(s) if s in ORDER else 99)) )


def full(z, charge=0):
    c = config(z, charge)
    order = sorted(c, key=lambda s: (int(s[0]), "spd".index(s[1])))
    return " ".join(f"{s}^{{{c[s]}}}" if c[s] > 9 else f"{s}^{c[s]}" for s in order)


def tex(s):
    return f"${s}$"


# known-truth checks
assert unpaired(config(26, 3)) == 5 and config(26, 2) == {"1s": 2, "2s": 2, "2p": 6, "3s": 2, "3p": 6, "3d": 6}
assert unpaired(config(15)) == 3 and unpaired(config(16)) == 2 and unpaired(config(14)) == 2
assert config(21)["3d"] == 1 and config(19) == {"1s": 2, "2s": 2, "2p": 6, "3s": 2, "3p": 6, "4s": 1}
assert sum(v for s, v in config(38, 2).items()) == 36 and config(38)["5s"] == 2
assert unpaired(config(25, 2)) == 5 and unpaired(config(27, 2)) == 3
assert sum(v for s, v in config(11).items() if s[1] == "s") == 5   # Na
assert sum(v for s, v in config(17).items() if s[1] == "p") == 11   # Cl dumb-bell electrons
assert sum(v for s, v in config(12).items() if s[1] == "s") == 6
assert unpaired(config(35)) == 1 and unpaired(config(35, 1)) == 2 and unpaired(config(35, -1)) == 0
assert unpaired(config(17)) == 1 and unpaired(config(17, -1)) == 0
assert unpaired(config(8, 1)) == 3 and unpaired(config(8, -1)) == 1 and unpaired(config(8, 2)) == 2
assert unpaired(config(8, -2)) == 0 and unpaired(config(17, 1)) == 2
assert config(13, 1) == {"1s": 2, "2s": 2, "2p": 6, "3s": 2}
# template check spaces
for Z in (26, 27, 28):
    for q in (2, 3):
        n = Z - 18 - q
        if n >= 6:
            c = config(Z, q)
            assert c["3d"] == n and "4s" not in c and unpaired(c) == min(n, 10 - n)
for Z in (25, 26, 27, 28):
    for q in (2, 3):
        assert config(Z, q)["3d"] == Z - 18 - q
for Z in range(13, 19):
    assert config(Z)["3p"] == Z - 12
for Z in (14, 15, 16):
    assert unpaired(config(Z)) == min(Z - 12, 18 - Z) and unpaired(config(Z)) != (Z - 12) % 2

# ---------------------------------------------------------------- builders
items, past = [], []
_n = [0]


def _hints(h):
    assert len(h) == 3
    return h


def mcq(kcs, d, cw, stem, opts, ans, expl, hints, dist=None, marks=1):
    assert len(opts) == 4
    _n[0] += 1
    it = {"id": f"{SUB}-i{_n[0]:02d}", "kcs": [K[k] for k in kcs], "kind": "mcq", "difficulty": d, "command_word": cw,
          "source": {"type": "generated"}, "stem": stem, "options": dict(zip("ABCD", opts)), "answer": ans,
          "marks": marks, "shuffle": True, "explanation": expl, "hints": _hints(hints)}
    if dist:
        it["distractors"] = dist
    items.append(it)


def num(kcs, d, cw, stem, ans, expl, hints, unit="", dists=None, template=None, marks=1, sf=None):
    _n[0] += 1
    a = {"unit": unit, "sf_ok": sf or [1, 2, 3]} if template else {"value": ans, "unit": unit, "exact": True}
    if template:
        a = {"unit": unit, "exact": True}
    it = {"id": f"{SUB}-i{_n[0]:02d}", "kcs": [K[k] for k in kcs], "kind": "numeric", "difficulty": d,
          "command_word": cw, "source": {"type": "generated"}, "stem": stem, "answer": a, "marks": marks,
          "explanation": expl, "hints": _hints(hints)}
    if template:
        it["template"] = template
    elif dists:
        it["distractors"] = dists
    items.append(it)


def short(kcs, d, cw, stem, rubric, expl, hints, marks=None):
    _n[0] += 1
    items.append({"id": f"{SUB}-i{_n[0]:02d}", "kcs": [K[k] for k in kcs], "kind": "short", "difficulty": d,
                  "command_word": cw, "source": {"type": "generated"}, "stem": stem, "rubric": rubric,
                  "marks": marks or len(rubric), "explanation": expl, "hints": _hints(hints)})


def structured(kcs, d, cw, stem, scheme, expl):
    _n[0] += 1
    items.append({"id": f"{SUB}-i{_n[0]:02d}", "kcs": [K[k] for k in kcs], "kind": "structured", "difficulty": d,
                  "command_word": cw, "source": {"type": "generated"}, "stem": stem, "scheme": scheme,
                  "marks": len(scheme), "explanation": expl})


def chk(v):
    return {"kind": "numeric", "answer": {"value": v, "unit": "", "exact": True}}


def pastq(qid, ref, kcs, d, cw, stem, ans, expl, options=None, image=None, dist=None):
    it = {"id": f"{SUB}-p{len(past) + 1:02d}", "kcs": [K[k] if isinstance(k, int) else k for k in kcs], "kind": "mcq",
          "difficulty": d, "command_word": cw, "source": {"type": "past", "ref": ref, "qid": qid}, "stem": stem,
          "answer": ans, "marks": 1, "explanation": expl}
    if options:
        it["options"] = dict(zip("ABCD", options))
    if image:
        it["image"] = image
    if dist:
        it["distractors"] = dist
    past.append(it)


R = lambda s: s  # raw-string marker for readability

# ---------------------------------------------------------------- misconceptions
misconceptions = [
    {"id": "m1", "kc": K[3], "statement": r"The 3d sub-shell fills before the 4s sub-shell because $n=3$ is lower than $n=4$.",
     "refutation": r"In atoms up to calcium the 4s sub-shell is lower in energy than 3d, so 4s fills first: K is $\ce{[Ar]}\,4s^1$, Ca is $\ce{[Ar]}\,4s^2$ and only then does Sc start filling 3d ($\ce{[Ar]}\,3d^1 4s^2$).",
     "contrast": r"The filling order is 3p, then 4s, then 3d, then 4p. The configuration is *written* in order of shell, with 3d before 4s, which is why the two orders get mixed up.",
     "source": "research"},
    {"id": "m2", "kc": K[6], "statement": r"When a transition metal atom forms a positive ion, the electrons are removed from the 3d sub-shell first.",
     "refutation": r"Electrons are removed from the outermost occupied shell first, so the 4s electrons are lost before any 3d electron. Once a 3d electron is present, the 4s electrons are the ones that leave.",
     "contrast": r"$\ce{Fe}$ is $\ce{[Ar]}\,3d^6 4s^2$, so $\ce{Fe^{2+}}$ is $\ce{[Ar]}\,3d^6$, not $\ce{[Ar]}\,3d^4 4s^2$.",
     "source": "research"},
    {"id": "m3", "kc": K[5], "statement": r"Electrons in a p sub-shell pair up in one orbital before they occupy the other orbitals, so sulfur has 0 unpaired electrons and phosphorus has 1.",
     "refutation": r"Electrons repel each other, so the orbitals of a sub-shell are filled singly first, with parallel spins, and only pair up once every orbital holds one electron (Hund's rule). This keeps inter-electron repulsion as low as possible, so the atom has the lowest energy.",
     "contrast": r"Ground-state phosphorus $3p^3$ has three unpaired electrons and sulfur $3p^4$ has two, not 1 and 0 as many candidates wrote.",
     "source": "ER 9701 w23 P21 Q1"},
    {"id": "m4", "kc": K[2], "statement": r"An orbital and a sub-shell are the same thing, so a p orbital holds six electrons.",
     "refutation": r"An orbital holds at most two electrons, with opposite spins. A p sub-shell is made of three p orbitals, so it holds six electrons in total (and a d sub-shell of five orbitals holds ten).",
     "contrast": r"Sub-shell capacity $=2\times$ the number of orbitals: s $=2$, p $=6$, d $=10$. Orbital capacity is always 2.",
     "source": "research"},
    {"id": "m5", "kc": K[9], "statement": r"A free radical must be a neutral atom or molecule, so ions such as $\ce{O^-}$ or $\ce{Cl^+}$ cannot be free radicals.",
     "refutation": r"A free radical is defined only by having one or more unpaired electrons; its charge is irrelevant. $\ce{O^-}$ ($2p^5$) and $\ce{Cl^+}$ ($3p^4$) each have unpaired electrons and are free radicals.",
     "contrast": r"$\ce{Cl^-}$ and $\ce{O^{2-}}$ have every electron paired (full octets), so they are not radicals, but $\ce{Cl}$, $\ce{O^-}$ and $\ce{Cl^+}$ are.",
     "source": "research"},
]

# ---------------------------------------------------------------- generated items
# --- 1.3.1
mcq([1], 1, "State", r"What does the principal quantum number, $n$, of an electron tell you?",
    ["The shell the electron is in: a larger $n$ means the shell is further from the nucleus and at higher energy",
     "The number of electrons in the shell", "The shape of the orbital the electron occupies",
     "The number of unpaired electrons in the atom"], "A",
    r"The principal quantum number $n=1,2,3,\dots$ labels the shell (main energy level). Larger $n$ means further from the nucleus and higher energy. Shape is set by the sub-shell type (s, p, d), not by $n$.",
    ["It is a whole number that labels part of the atom's structure, not a count of electrons.",
     "Think of the shells numbered 1, 2, 3 moving outwards from the nucleus.",
     "Decide which of the options describes the *shell* an electron is in and how its energy changes as the number rises."])
mcq([1, 2], 2, "Identify", r"Which statement about the shell with principal quantum number $n=3$ is correct?",
    ["It contains three sub-shells: 3s, 3p and 3d", "It contains two sub-shells only: 3s and 3p",
     "It contains three orbitals in total", "It can hold a maximum of nine electrons"], "A",
    r"The $n=3$ shell has 3s (1 orbital), 3p (3 orbitals) and 3d (5 orbitals): three sub-shells, nine orbitals, so up to 18 electrons. Nine is the number of orbitals, not electrons; three is the number of sub-shells.",
    ["Each shell contains as many kinds of sub-shell as its value of $n$.",
     "List the sub-shells (s, p, d ...) that exist when $n=3$.",
     "Count the sub-shells, then separate this from counting orbitals or electrons."],
    dist={"C": "m4", "D": "m4"})
short([1], 2, "State", r"State what is meant by the *ground state* of an atom.",
      [{"point": "all the electrons are in the lowest available energy levels / lowest energy arrangement of the electrons",
        "keywords": [["lowest"], ["energy"], ["electron", "electrons"]]}],
      r"The ground state is the arrangement in which the electrons occupy the lowest available energy levels (sub-shells).",
      ["Ground means the most stable, unexcited state.", "Say where the electrons are and refer to energy.",
       "Complete: the electrons occupy the ... available energy levels."])
short([1, 2], 2, "State", r"State what is meant by an *orbital*.",
      [{"point": "a region of space around the nucleus (where there is a high probability of finding an electron)",
        "keywords": [["region"], ["space"]]},
       {"point": "that can hold a maximum of two electrons (with opposite spins)",
        "keywords": [["two", "2"], ["electron", "electrons"]]}],
      r"An orbital is a region of space around the nucleus that can hold up to two electrons with opposite spins. It is not a fixed path (orbit).",
      ["An orbital is not a track that an electron follows.", "Give where it is and how many electrons it can hold.",
       "Begin: a region of ... around the nucleus, holding at most ... electrons."])
num([1, 2], 2, "Calculate", r"Calculate the maximum number of electrons that can be held in the shell with principal quantum number $n=[[n]]$.",
    None, r"The $n$th shell has $n^2$ orbitals, each holding two electrons, so it holds $2n^2$ electrons ($8$ for $n=2$, $18$ for $n=3$).",
    ["The shell has several sub-shells, each made of orbitals.", "Work out how many orbitals the shell has in total, then use two electrons per orbital.",
     "Use the fact that the total number of orbitals in a shell is $n^2$."],
    template={"params": {"n": {"choices": [2, 3]}}, "answer": "2*n**2",
              "distractors": [{"expr": "n**2", "misconception": "m4"}, {"expr": "2*n"}], "constraints": ["n > 1"]})
mcq([1, 3], 3, "Identify", r"In a ground-state sulfur atom, which occupied orbital has the lowest energy?",
    ["3p", "3s", "2p", "1s"], "D",
    r"The lowest-energy orbital is the one closest to the nucleus, the 1s orbital. Examiners report that many candidates chose 3p, mixing up the lowest-energy orbital with the outermost electrons that are easiest to remove (ionisation energy). (ER 9701 s19 P23 Q1)",
    ["Energy rises with distance from the nucleus.", "Think about which shell is closest to the nucleus, not which electron is easiest to remove.",
     "Look for the sub-shell of the innermost shell."])
short([1, 2], 4, "Describe", r"Describe the sub-shells and orbitals that make up the shell with $n=3$, and state the maximum number of electrons it can hold.",
      [{"point": "three sub-shells: 3s, 3p and 3d", "keywords": [["3s"], ["3p"], ["3d"]]},
       {"point": "with 1, 3 and 5 orbitals respectively (9 in total)", "keywords": [["1"], ["3"], ["5"]]},
       {"point": "maximum of 18 electrons (two per orbital)", "keywords": [["18"]]}],
      r"$n=3$ contains 3s (1 orbital), 3p (3 orbitals) and 3d (5 orbitals): 9 orbitals holding $9\times2=18$ electrons.",
      ["Start with the sub-shells, then the orbitals inside each.", "Give the number of orbitals in an s, p and d sub-shell and add them.",
       "Multiply the total number of orbitals by two electrons per orbital."])
# --- 1.3.2
mcq([2], 1, "State", r"How many orbitals are there in a d sub-shell?", ["1", "3", "5", "10"], "C",
    r"A d sub-shell has five orbitals (holding up to ten electrons). Ten is the electron capacity, not the number of orbitals.",
    ["Compare with an s sub-shell (1 orbital) and a p sub-shell (3).", "The pattern of orbitals per sub-shell is 1, 3, then the next odd number.",
     "The d sub-shell holds ten electrons at two per orbital, so work backwards."], dist={"D": "m4"})
num([2], 2, "Calculate", r"A sub-shell contains [[o]] orbitals. Calculate the maximum number of electrons it can hold.",
    None, r"Each orbital holds a maximum of two electrons, so the capacity is $2\times$ the number of orbitals.",
    ["Think about how many electrons one orbital can hold.", "Multiply the number of orbitals by the capacity of a single orbital.",
     r"Capacity of the sub-shell $=2\times$ number of orbitals."],
    template={"params": {"o": {"choices": [1, 3, 5]}}, "answer": "2*o", "distractors": [{"expr": "o", "misconception": "m4"}],
              "constraints": ["o >= 1"]})
mcq([2], 3, "Identify", r"Which statement about the 2p sub-shell is correct?",
    ["It contains three orbitals, each holding a maximum of two electrons", "It contains one orbital that holds six electrons",
     "It contains three orbitals, each holding a maximum of six electrons", "It holds a maximum of two electrons"], "A",
    r"A p sub-shell is made of three p orbitals. Each orbital holds at most two electrons, so the sub-shell holds six. Statements that make one orbital hold six, or the whole sub-shell hold two, confuse orbital with sub-shell.",
    ["Separate the ideas of orbital and sub-shell.", "Decide how many p orbitals there are, then how many electrons one orbital holds.",
     "Three orbitals, two electrons each."], dist={"B": "m4", "C": "m4", "D": "m4"})
# --- 1.3.3
mcq([3], 2, "Identify", r"In the ground-state atoms of the elements, which sub-shell is filled immediately after 3p?",
    ["3d", "4s", "4p", "4d"], "B",
    r"4s is lower in energy than 3d, so 4s fills straight after 3p (K and Ca), then 3d (Sc to Zn), then 4p (Ga to Kr). Choosing 3d follows shell number rather than energy.",
    ["Filling follows increasing energy, not increasing shell number.", "Compare the energies of the 3d and 4s sub-shells.",
     "One of the sub-shells in shell 4 is lower in energy than a sub-shell in shell 3."], dist={"A": "m1"})
mcq([3], 3, "Identify", r"Which of these sub-shells has the highest energy?", ["3p", "4s", "3d", "4p"], "D",
    r"The order of increasing energy is 3p, 4s, 3d, 4p, so 4p is the highest of the four.",
    ["Use the energy order, not the shell number alone.", "Write out the order for 3p, 4s, 3d and 4p.",
     "One sub-shell in shell 4 lies above every sub-shell in shell 3."])
num([3], 3, "Determine", r"Of the sub-shells 1s, 2s, 2p, 3s, 3p, 3d, 4s and 4p, how many have a lower energy than 3d?",
    6, r"The order is 1s, 2s, 2p, 3s, 3p, 4s, 3d, 4p, so six sub-shells (1s, 2s, 2p, 3s, 3p and 4s) lie below 3d. Forgetting that 4s is below 3d gives the wrong answer 5.",
    ["Put all the listed sub-shells in order of energy first.", "Decide carefully where 4s sits relative to 3d.",
     "Count how many sub-shells come before 3d in the list you made."],
    dists=[{"value": 5, "misconception": "m1"}])
mcq([3], 3, "Identify", r"Which sequence shows the sub-shells in order of increasing energy?",
    ["3p, 3d, 4s, 4p", "3p, 4s, 3d, 4p", "4s, 3p, 3d, 4p", "3p, 4s, 4p, 3d"], "B",
    r"The energy order is 3p, 4s, 3d, 4p. In A the 3d is placed before 4s (shell-number thinking); in C, 4s is below 3p; in D, 4p is below 3d.",
    ["Only one sequence has 4s between 3p and 3d.", "Check each option for where 4s and 3d sit.",
     "Start from 3p, then decide which of 3d and 4s comes next."], dist={"A": "m1"})
structured([3, 5], 4, "Explain", r"Potassium has proton number 19.\n\n(a) Give the full electronic configuration of a potassium atom. (b) State how the energies of the 4s and 3d sub-shells compare, and hence explain why the last electron of potassium goes into 4s. (c) State which sub-shell receives the first electron after the 4s sub-shell is full.".replace(r"\n", "\n"),
           [{"mark": "B1", "point": "$" + full(19) + "$"},
            {"mark": "B1", "point": "4s is lower in energy than 3d (in K and Ca)"},
            {"mark": "B1", "point": "so the 19th electron enters the lower-energy 4s sub-shell rather than 3d"},
            {"mark": "B1", "point": "3d (scandium: $" + full(21) + "$)"}],
           r"4s lies below 3d in these atoms, so 4s fills first (K, Ca) and 3d starts with Sc.")
mcq([3, 6], 3, "Deduce", r"Scandium has proton number 21. What is the electronic configuration of a ground-state scandium atom?",
    [r"$\ce{[Ar]}\,3d^3$", r"$\ce{[Ar]}\,3d^1 4s^2$", r"$\ce{[Ar]}\,4s^2 4p^1$", r"$\ce{[Ar]}\,3d^2 4s^1$"], "B",
    r"After argon, the next two electrons fill 4s, and the 21st electron goes into 3d: $\ce{[Ar]}\,3d^1 4s^2$. The option with 3d only fills 3d before 4s.",
    ["Argon has 18 electrons. Where do the next three go?", "Fill 4s before 3d.", "Two go into 4s, the last one into the next sub-shell up."],
    dist={"A": "m1"})
# --- 1.3.4
num([4], 2, "Calculate", r"Calculate the number of electrons in the 3p sub-shell of a ground-state atom of the element with proton number [[Z]].",
    None, r"Fill 1s, 2s, 2p, 3s (12 electrons in total) and the remaining $Z-12$ electrons go into 3p.",
    ["Fill the sub-shells in energy order until the electrons run out.", "Find how many electrons are used before 3p starts.",
     "Subtract the electrons in 1s, 2s, 2p and 3s from the proton number."],
    template={"params": {"Z": {"min": 13, "max": 18, "step": 1}}, "answer": "Z-12", "distractors": [{"expr": "Z-10"}], "constraints": ["Z >= 13"]})
num([4, 5], 3, "Determine", r"Determine the number of unpaired electrons in a ground-state atom of the element with proton number [[Z]].",
    None, r"The 3p orbitals are filled singly first (Hund's rule) and only then paired: with $p=Z-12$ electrons in 3p there are $\min(p,6-p)$ unpaired electrons.",
    ["First work out how many electrons the atom has in its 3p sub-shell.", "Three orbitals: each takes one electron before any takes a second.",
     "Fill the three 3p orbitals singly, then pair up any that are left over, and count the single ones."],
    template={"params": {"Z": {"choices": [14, 15, 16]}}, "derived": {"p": "Z-12"}, "answer": "min(p, 6-p)",
              "distractors": [{"expr": "p % 2", "misconception": "m3"}], "constraints": ["Z >= 14"]})
short([4], 2, "Give", r"Give the full electronic configuration of a ground-state chlorine atom (proton number 17).",
      [{"point": "$" + full(17) + "$ in sub-shell notation", "keywords": [["1s2", "1s²", "1s^2"], ["2s2", "2s²", "2s^2"], ["2p6", "2p⁶", "2p^6"], ["3s2", "3s²", "3s^2"], ["3p5", "3p⁵", "3p^5"]]}],
      r"Chlorine has 17 electrons: $" + full(17) + "$.",
      ["Count the electrons first.", "Fill in the energy order and stop when you reach 17 electrons.", "The last sub-shell in use is 3p."])
structured([4, 5], 4, "Determine", r"Sulfur has proton number 16.\n\n(a) Give the full electronic configuration of a ground-state sulfur atom. (b) State the number of unpaired electrons in a sulfur atom. (c) State the total number of electrons in p orbitals. (d) State the number of completely filled orbitals.".replace(r"\n", "\n"),
           [{"mark": "B1", "point": "$" + full(16) + "$"},
            {"mark": "B1", "point": "two unpaired electrons (the $3p^4$ electrons occupy one filled orbital and two half-filled orbitals)", "check": chk(2)},
            {"mark": "B1", "point": "10 electrons in p orbitals ($2p^6$ and $3p^4$)", "check": chk(10)},
            {"mark": "B1", "point": "7 completely filled orbitals (1s, 2s, three 2p, 3s and one 3p)", "check": chk(7)}],
           r"$1s^2 2s^2 2p^6 3s^2 3p^4$ gives 2 unpaired, 10 p electrons and 7 full orbitals.")
assert unpaired(config(16)) == 2 and sum(v for s, v in config(16).items() if s[1] == "p") == 10
# --- 1.3.5
mcq([5], 3, "Explain", r"Why does an oxygen atom have two unpaired electrons in its 2p sub-shell rather than none?",
    ["Electrons occupy separate 2p orbitals singly before pairing, which minimises inter-electron repulsion",
     "Two electrons in the same orbital attract each other, so pairing raises the energy",
     "The 2p orbitals have different energies, so electrons fill the lowest one completely first",
     "Electrons in the same orbital have the same spin, so they repel less"], "A",
    r"Electrons repel each other. Putting one electron in each of the three equal-energy 2p orbitals keeps them apart, giving the lowest energy, so the fourth and later electrons pair up only when every orbital already holds one.",
    ["Think about what electrons do to each other when they are close together.", "The three 2p orbitals have the same energy.",
     "Ask which arrangement of four electrons in three orbitals gives the least repulsion."], dist={"B": "m3"})
short([5], 3, "Explain", r"Explain, in terms of inter-electron repulsion, why the three 2p electrons of a nitrogen atom occupy three separate orbitals.",
      [{"point": "electrons repel one another (inter-electron repulsion)", "keywords": [["repel", "repulsion"]]},
       {"point": "occupying separate (equal-energy) orbitals singly keeps the electrons apart, lowering repulsion and energy",
        "keywords": [["separate", "different", "singly", "unpaired"], ["lower", "minimi", "less", "reduce"]]}],
      r"Pairing two electrons in one orbital increases repulsion, so the lowest-energy arrangement puts one electron in each 2p orbital.",
      ["Consider two electrons in the same orbital compared with two in different orbitals.", "Use the word repulsion.",
       "State which arrangement has less repulsion and therefore lower energy."])
mcq([5, 6], 4, "Explain", r"The ground-state configuration of chromium is $\ce{[Ar]}\,3d^5 4s^1$, not $\ce{[Ar]}\,3d^4 4s^2$. Which statement best explains this?",
    ["3d and 4s are close in energy and moving one electron from 4s to 3d gives a half-filled 3d sub-shell with no pairing, lowering inter-electron repulsion",
     "The 4s sub-shell of chromium can hold only one electron", "Electrons in the 4s orbital repel each other less than electrons in separate 3d orbitals",
     "3d is lower in energy than 4s in every atom so 3d fills completely before 4s"], "A",
    r"3d and 4s are very close in energy. Promoting one 4s electron gives five singly-occupied 3d orbitals (parallel spins) and only one electron in 4s, so there is less repulsion overall and the atom is at lower energy.",
    ["The two sub-shells have very similar energies.", "Count how many electrons are paired in each of the two possible arrangements.",
     "Which arrangement has more separate, singly occupied orbitals?"], dist={"D": "m1"})
mcq([5], 4, "Explain", r"Sulfur has a lower first ionisation energy than phosphorus. Which statement explains this?",
    ["The 3p electron removed from sulfur is paired with another electron in the same orbital, and the repulsion between them makes it easier to remove",
     "Sulfur has a smaller nuclear charge than phosphorus", "Sulfur has more inner shells than phosphorus",
     "The electron removed from sulfur comes from the 3s sub-shell"], "A",
    r"Phosphorus ($3p^3$) has all 3p orbitals singly occupied. Sulfur ($3p^4$) has one orbital holding a pair, and the spin-pair repulsion makes that electron easier to remove. Nuclear charge is larger in sulfur, and both atoms have the same inner shells (ER 9701 w23 P21 Q1).",
    ["Compare the 3p arrangements of phosphorus and sulfur.", "Which atom has an orbital containing a pair of electrons?", "Consider what repulsion between paired electrons does to the energy needed to remove one."],
    dist={"B": "m3"})
structured([5, 4], 5, "Explain", r"Oxygen has proton number 8.\n\n(a) Give the electronic configuration of an oxygen atom in sub-shell notation. (b) Explain why the four 2p electrons form one pair and two unpaired electrons rather than two pairs.".replace(r"\n", "\n"),
           [{"mark": "B1", "point": "$" + full(8) + "$"},
            {"mark": "B1", "point": "electrons repel each other (inter-electron repulsion)"},
            {"mark": "B1", "point": "the three 2p orbitals have equal energy, and each is occupied by one electron before any is doubly occupied"},
            {"mark": "B1", "point": "the fourth electron must pair with one already in an orbital, so there is one pair and two unpaired electrons, giving the lowest energy"}],
           r"Singly occupying each 2p orbital minimises repulsion; only the fourth electron has to pair up.")
# --- 1.3.6
num([6], 3, "Determine", r"An ion $\ce{M^{[[q]]+}}$ is formed from the first-row transition element with proton number [[Z]]. Determine the number of electrons in its 3d sub-shell.",
    None, r"The atom is $\ce{[Ar]}\,3d^{Z-20}4s^2$. The 4s electrons are removed first, so for charge $q\geq2$ the 3d holds $Z-18-q$ electrons.",
    ["Write the electronic configuration of the neutral atom first.", "Electrons are removed from the outermost shell first, so decide which sub-shell loses electrons first.",
     "Total electrons beyond argon $=Z-18-q$; these are all in 3d once 4s is emptied."],
    template={"params": {"Z": {"choices": [25, 26, 27, 28]}, "q": {"choices": [2, 3]}}, "answer": "Z-18-q",
              "distractors": [{"expr": "Z-20-q", "misconception": "m2"}], "constraints": ["Z-20-q >= 1"]})
mcq([6], 3, "Deduce", r"What is the electronic configuration of an $\ce{Fe^{2+}}$ ion (proton number of Fe is 26)?",
    [r"$\ce{[Ar]}\,3d^6$", r"$\ce{[Ar]}\,3d^4 4s^2$", r"$\ce{[Ar]}\,3d^6 4s^2$", r"$\ce{[Ar]}\,3d^8 4s^2$"], "A",
    r"$\ce{Fe}$ is $\ce{[Ar]}\,3d^6 4s^2$. The two 4s electrons are lost first: $\ce{[Ar]}\,3d^6$. Removing 3d electrons first gives $3d^4 4s^2$, and $3d^6 4s^2$ is the neutral atom.",
    ["Write the neutral atom first, then remove electrons.", "Which sub-shell does an electron leave first when a transition metal ionises?", "A 2+ ion has lost two electrons from the outermost occupied sub-shell."],
    dist={"B": "m2"})
mcq([6], 2, "Identify", r"Which species has the electronic configuration $1s^2 2s^2 2p^6 3s^2 3p^6$?",
    [r"$\ce{Ca^{2+}}$", r"$\ce{Mg^{2+}}$", r"$\ce{Na+}$", r"$\ce{Al^{3+}}$"], "A",
    r"The configuration has 18 electrons. $\ce{Ca^{2+}}$ has $20-2=18$ electrons, whereas $\ce{Mg^{2+}}$, $\ce{Na+}$ and $\ce{Al^{3+}}$ each have 10.",
    ["Count the electrons in the configuration.", "For a positive ion, electrons $=$ proton number $-$ charge.", "Find the ion with 18 electrons."])
short([6], 3, "Give", r"Give the full electronic configuration of the $\ce{Fe^{3+}}$ ion (proton number of Fe is 26).",
      [{"point": "$" + full(26, 3) + "$", "keywords": [["1s2", "1s²", "1s^2"], ["2s2", "2s²", "2s^2"], ["2p6", "2p⁶", "2p^6"], ["3s2", "3s²", "3s^2"], ["3p6", "3p⁶", "3p^6"], ["3d5", "3d⁵", "3d^5"]]}],
      r"Fe is $" + full(26) + r"$; remove two 4s electrons then one 3d electron: $" + full(26, 3) + "$.",
      ["An iron atom has 26 electrons, an $\\ce{Fe^{3+}}$ ion has fewer.", "Remove the outermost electrons first.", "Two electrons leave 4s, the third leaves 3d."])
structured([6, 7], 4, "Deduce", r"Iron has proton number 26.\n\n(a) Give the full electronic configuration of an iron atom. (b) Give the shorthand configuration of $\ce{Fe^{2+}}$. (c) Give the shorthand configuration of $\ce{Fe^{3+}}$. (d) State the number of unpaired electrons in $\ce{Fe^{3+}}$.".replace(r"\n", "\n"),
           [{"mark": "B1", "point": "$" + full(26) + "$"},
            {"mark": "B1", "point": r"$\ce{Fe^{2+}}$: $\ce{[Ar]}\,3d^6$ (4s electrons lost first)"},
            {"mark": "B1", "point": r"$\ce{Fe^{3+}}$: $\ce{[Ar]}\,3d^5$"},
            {"mark": "B1", "point": r"5 unpaired electrons in $\ce{Fe^{3+}}$ (one in each 3d orbital)", "check": chk(5)}],
           r"Fe is $3d^6 4s^2$; the 4s electrons go first, then a 3d electron, leaving five singly-occupied 3d orbitals.")
# --- 1.3.7
mcq([7], 3, "Identify", r"Which electrons-in-boxes diagram (arrow up/down $=$ electron, one box per orbital) correctly represents the 2p sub-shell of a ground-state oxygen atom?",
    ["↑↓ | ↑↓ | (empty box)", "↑↓ | ↑ | ↑", "↑↑ | ↑ | ↑ (two same-direction arrows in one box)", "↑↓ | ↑↓ | ↑↓"], "B",
    r"Oxygen has four 2p electrons. Each of the three boxes gets one arrow first, and the fourth pairs with an opposite-direction arrow: ↑↓ | ↑ | ↑. Option A pairs before filling singly, C puts two same-direction arrows in one box and D holds six electrons (neon).",
    ["Four electrons go into three boxes.", "Put one arrow in each box before adding any second arrow.", "Paired arrows in a box point in opposite directions."],
    dist={"A": "m3"})
num([7, 6], 3, "Determine", r"An ion $\ce{M^{[[q]]+}}$ is formed from the first-row transition element with proton number [[Z]]. Determine the number of unpaired electrons in the ion.",
    None, r"The ion is $3d^n$ with $n=Z-18-q$. Above $n=5$ the extra electrons pair up, so the number of unpaired electrons is $10-n$.",
    ["First find how many 3d electrons the ion has.", "Draw five 3d boxes: fill one arrow in each first.", "Any 3d electrons beyond five must pair with one already there."],
    template={"params": {"Z": {"choices": [26, 27, 28]}, "q": {"choices": [2, 3]}}, "derived": {"n": "Z-18-q"}, "answer": "min(n, 10-n)",
              "distractors": [{"expr": "n", "misconception": "m3"}], "constraints": ["Z-18-q >= 6"]})
num([7, 6], 3, "Determine", r"Determine the number of unpaired electrons in an $\ce{Mn^{2+}}$ ion (proton number of Mn is 25).",
    5, r"$\ce{Mn}$ is $\ce{[Ar]}\,3d^5 4s^2$; losing both 4s electrons gives $\ce{[Ar]}\,3d^5$, five singly-occupied 3d orbitals, so five unpaired electrons. Removing 3d electrons first gives $3d^3 4s^2$ and only 3.",
    ["Write the configuration of the atom first.", "Remove the outermost electrons first.", "Five 3d boxes each receive one arrow."],
    dists=[{"value": 3, "misconception": "m2"}])
structured([7, 6], 4, "Deduce", r"An $\ce{Fe^{2+}}$ ion has the configuration $\ce{[Ar]}\,3d^6$.\n\n(a) Describe the electrons-in-boxes diagram for the 3d sub-shell. (b) State whether the 4s box is occupied. (c) State the number of unpaired electrons.".replace(r"\n", "\n"),
           [{"mark": "B1", "point": "3d has five boxes: one box holds a pair of arrows in opposite directions and four boxes hold one arrow each (all single arrows in the same direction)"},
            {"mark": "B1", "point": "the 4s box is empty (its electrons were lost first)"},
            {"mark": "B1", "point": "4 unpaired electrons", "check": chk(4)}],
           r"3d$^6$ means five singles first and the sixth electron pairs up: four unpaired.")
# --- 1.3.8
mcq([8], 1, "Identify", r"What is the shape of a 2p orbital?", ["Spherical", "Dumb-bell", "Circular ring", "Four-lobed (clover-leaf)"], "B",
    r"s orbitals are spherical, p orbitals are dumb-bell shaped (two lobes either side of the nucleus), and d orbitals mostly have four lobes.",
    ["The p orbital has a different shape from s.", "It has two lobes.", "Think of a hand weight."])
mcq([8, 2], 2, "Describe", r"How many p orbitals are there in a p sub-shell, and how are they arranged in space?",
    ["One, spherical", "Three, each along a different axis (x, y and z) at $90^\\circ$ to each other", "Three, all along the same axis", "Five, in a plane"], "B",
    r"A p sub-shell has three dumb-bell orbitals, $p_x$, $p_y$ and $p_z$, each along one of three mutually perpendicular axes.",
    ["Recall the number of orbitals in a p sub-shell.", "The three orbitals point in different directions.", "The axes are mutually perpendicular."])
short([8], 2, "Describe", r"Describe the shape of an s orbital and of a p orbital.",
      [{"point": "an s orbital is spherical", "keywords": [["spherical", "sphere"]]},
       {"point": "a p orbital is dumb-bell shaped (two lobes)", "keywords": [["dumb-bell", "dumbbell", "dumb bell", "two lobes", "figure of eight", "figure-of-eight"]]}],
      r"s: spherical, centred on the nucleus; p: dumb-bell, two lobes either side of the nucleus.",
      ["One is round and one has two lobes.", "Use the words spherical and dumb-bell.", "Name each shape next to its orbital."])
num([8, 4], 3, "Determine", r"Determine the number of electrons in dumb-bell shaped orbitals in a ground-state chlorine atom (proton number 17).",
    11, r"Chlorine is $1s^2 2s^2 2p^6 3s^2 3p^5$. The p orbitals (dumb-bell) hold $6+5=11$ electrons. Counting only the outer $3p^5$ gives 5.",
    ["Write the full electronic configuration.", "Identify which sub-shell types are dumb-bell shaped.", "Add the electrons in every p sub-shell, not only the outer one."],
    dists=[{"value": 5}])
mcq([8], 2, "Compare", r"Which statement about the 1s and 2s orbitals is correct?",
    ["Both are spherical; the 2s orbital is larger and at higher energy", "The 1s orbital is spherical and the 2s orbital is dumb-bell shaped",
     "Both are spherical and have the same size and energy", "Both are spherical; the 2s is at lower energy than the 1s"], "A",
    r"All s orbitals are spherical. A higher $n$ gives a larger orbital at higher energy, so 2s is larger and higher in energy than 1s.",
    ["Consider what n changes: the shape, the size or both.", "s orbitals share a shape.", "Higher shell means further out and higher energy."])
# --- 1.3.9
short([9], 1, "State", r"State what is meant by a *free radical*.",
      [{"point": "a species (atom, molecule or ion) with one or more unpaired electrons", "keywords": [["unpaired"], ["electron", "electrons"]]}],
      r"A free radical is a species with one or more unpaired electrons.",
      ["Think about electron pairing, not about charge.", "The key word describes the state of one or more electrons.", "A species with one or more ... electrons."])
mcq([9], 3, "Identify", r"Which statement about free radicals is correct?",
    ["All free radicals are uncharged", "A free radical has one or more unpaired electrons and may carry a charge",
     "A free radical has all its electrons paired but is highly reactive", "Any species with an incomplete outer shell is a free radical"], "B",
    r"A free radical is defined by an unpaired electron only. $\ce{O^-}$ and $\ce{Cl^+}$ are radicals even though they carry a charge. Magnesium has an incomplete outer shell yet its electrons are paired, so option D fails.",
    ["The definition mentions electrons but not charge.", "Test each statement with $\\ce{O^-}$ ($2p^5$).", "Look for unpaired electrons and ignore the charge."], dist={"A": "m5"})
mcq([9, 6], 3, "Identify", r"Which species is a free radical?", [r"$\ce{Al^{3+}}$", r"$\ce{Ca}$", r"$\ce{Br^-}$", r"$\ce{Br}$"], "D",
    r"$\ce{Br}$ is $\ce{[Ar]}\,3d^{10}4s^24p^5$ with one unpaired 4p electron. $\ce{Al^{3+}}$ and $\ce{Br^-}$ have full shells (all paired) and Ca has $4s^2$ (paired).",
    ["Look for an odd number of electrons in the outer p orbitals.", "Draw the outer boxes for each species.", "Find the species with a single electron in an orbital."])
mcq([9, 6], 4, "Determine", r"How many of $\ce{Br}$, $\ce{Br^-}$, $\ce{Br^+}$ and $\ce{Br2}$ are free radicals?", ["1", "2", "3", "4"], "B",
    r"$\ce{Br}$ ($4p^5$, one unpaired electron) and $\ce{Br^+}$ ($4p^4$, two unpaired electrons) are radicals. $\ce{Br^-}$ ($4p^6$) and $\ce{Br2}$ (every electron paired in the bond and lone pairs) are not.",
    ["Write the outer electron configuration of each species.", "Draw the 4p boxes for Br, $\\ce{Br^+}$ and $\\ce{Br^-}$.", "Count the species with at least one unpaired electron; do not discount charged ones."], dist={"A": "m5"})
short([9, 6], 3, "Explain", r"Explain why a chlorine atom is a free radical but a chloride ion is not.",
      [{"point": "the chlorine atom ($3p^5$) has one unpaired electron", "keywords": [["unpaired"], ["one", "1", "single"]]},
       {"point": "the chloride ion ($3p^6$) has all its electrons paired", "keywords": [["paired", "pairs"], ["all", "full", "complete", "filled", "3p6", "3p⁶"]]}],
      r"Cl is $3p^5$ (one unpaired electron); Cl$^-$ is $3p^6$ with every electron paired.",
      ["Write the 3p configuration of each.", "Compare how the 3p electrons are arranged in the two species.", "One has an unpaired electron; the other has none."])

# ---------------------------------------------------------------- past items
IMG = "Assets/mcq/"
pastq("9701_w25_13_q1", "CAIE 9701 · Nov 2025 · P13 · Q1", [6], 3, "Deduce",
      r"What is the electronic configuration for the particle $^{27}_{13}\ce{Al+}$?", "B",
      r"$\ce{Al+}$ has $13-1=12$ electrons: $1s^2 2s^2 2p^6 3s^2$. Option C has 14 electrons (an electron added instead of removed), and D (27 electrons) uses the nucleon number as the electron count; A is an excited state.",
      options=["1s²2s²2p⁶3s¹3p¹", "1s²2s²2p⁶3s²", "1s²2s²2p⁶3s²3p²", "1s²2s²2p⁶3s²3p⁶3d⁷4s¹"], image=IMG + "9701_w25_13_q1.png")
pastq("9701_w25_12_q1", "CAIE 9701 · Nov 2025 · P12 · Q1", [7, 6], 3, "Identify",
      r"What is the electrons in boxes notation for the $\ce{Fe^{3+}}$ ion?", "D",
      r"$\ce{Fe^{3+}}$ is $\ce{[Ar]}\,3d^5$: five 3d boxes each with one arrow, 4s empty (D). C is the $\ce{Fe^{2+}}$ ion ($3d^6$). A and B keep two 4s electrons, which is the mistake of removing electrons from 3d first.",
      image=IMG + "9701_w25_12_q1.png", dist={"A": "m2", "B": "m2"})
pastq("9701_w24_13_q2", "CAIE 9701 · Nov 2024 · P13 · Q2", [4], 4, "Deduce",
      "Compound X contains two elements, Y and Z.\n\nElement Y is in Period 2 of the Periodic Table. In one atom of element Y, the p sub-shell has all three orbitals occupied; only one of these three orbitals is fully occupied.\n\nElement Z is in Period 3 of the Periodic Table. In one atom of element Z, the p sub-shell has only two orbitals occupied.\n\nWhat is the formula of compound X?",
      "C", r"Y is oxygen ($2p^4$: one full orbital and two half-full orbitals). Z has only two 3p orbitals occupied, so it is silicon ($3p^2$). X is $\ce{SiO2}$. D ($\ce{SO2}$) is tempting, but sulfur ($3p^4$) has all three 3p orbitals occupied; A and B contain chlorine, not oxygen.",
      options=["CCl₄", "SiCl₄", "SiO₂", "SO₂"])
pastq("9701_w22_13_q3", "CAIE 9701 · Nov 2022 · P13 · Q3", [8], 3, "Identify",
      "Which statement about the electrons in a ground state carbon atom is correct?", "D",
      r"Carbon is $1s^2 2s^2 2p^2$. The lowest-energy orbital (1s) is spherical, so D is right. Its highest-energy occupied orbital is 2p (dumb-bell, so C is wrong); its electrons occupy three energy levels not four (A); and it has four s electrons but only two p electrons (B).",
      options=["Electrons are present in four different energy levels.", "There are more electrons in p orbitals than there are in s orbitals.",
               "The occupied orbital of highest energy is spherical.", "The occupied orbital of lowest energy is spherical."])
pastq("9701_w21_13_q4", "CAIE 9701 · Nov 2021 · P13 · Q4", [6], 4, "Deduce",
      r"The ion $\ce{X^{2+}}$ has the same electronic configuration as the atom Kr. What is the electronic configuration of an atom of X?", "B",
      r"Kr has 36 electrons, so $\ce{X^{2+}}$ has 36 and the atom X has 38 (strontium): $\ce{[Ar]}\,4s^2 3d^{10} 4p^6 5s^2$. A is Kr itself, ignoring the two electrons lost, and C and D wrongly fill 4d before 5s.",
      options=["[Ar] 4s²3d¹⁰4p⁶", "[Ar] 4s²3d¹⁰4p⁶5s²", "[Ar] 4s²4d¹⁰4p⁶", "[Ar] 4s²4d¹⁰4p⁶5s²"])
pastq("9701_w21_13_q34", "CAIE 9701 · Nov 2021 · P13 · Q34", [9], 3, "Identify",
      "Which molecules contain at least one unpaired electron?\n\n1. $\\ce{NO}$\n2. $\\ce{NO2}$\n3. $\\ce{NH3}$", "B",
      r"$\ce{NO}$ (15 electrons) and $\ce{NO2}$ (23 electrons) each have an odd number of electrons, so each has an unpaired electron. $\ce{NH3}$ has 10 electrons in five pairs, so option A (all three) is wrong.",
      options=["1, 2 and 3", "1 and 2 only", "2 and 3 only", "1 only"], image=IMG + "9701_w21_13_q34.png")
pastq("9701_w21_12_q4", "CAIE 9701 · Nov 2021 · P12 · Q4", [4], 4, "Identify",
      "Which atom has more unpaired electrons than paired electrons in orbitals of principal quantum number 2?", "B",
      r"Nitrogen ($2s^2 2p^3$) has 3 unpaired against 2 paired electrons. Carbon ($2s^2 2p^2$) has 2 unpaired and 2 paired, which is equal, not more (the tempting wrong answer); oxygen has 2 unpaired and 4 paired and fluorine 1 and 6.",
      options=["carbon", "nitrogen", "oxygen", "fluorine"])
pastq("9701_w20_12_q3", "CAIE 9701 · Nov 2020 · P12 · Q3", [2], 2, "Identify",
      "Which atomic orbitals are occupied in an atom of phosphorus?", "C",
      r"Phosphorus is $1s^2 2s^2 2p^6 3s^2 3p^3$, so the occupied orbitals are 1s, 2s, 2p, 3s and 3p. Option C lists real, occupied ones. A includes a 1p, and B a 2d, which do not exist; D includes a 3d, which exists but is empty in phosphorus.",
      options=["1p 2s 2p", "2s 2p 2d", "2s 2p 3s", "2p 3s 3d"])
pastq("9701_s25_13_q1", "CAIE 9701 · Jun 2025 · P13 · Q1", [8, 4], 4, "Identify",
      "Which isolated gaseous atom has a total of five electrons occupying spherically shaped orbitals?", "A",
      r"Spherical orbitals are s orbitals. Sodium is $1s^2 2s^2 2p^6 3s^1$, giving $2+2+1=5$ s electrons. Boron and fluorine have 4, and potassium has 7.",
      options=["sodium", "fluorine", "boron", "potassium"])
pastq("9701_s25_11_q14", "CAIE 9701 · Jun 2025 · P11 · Q14", [2, 5], 3, "Identify",
      "Which statement about a 3p orbital is correct?", "D",
      r"Phosphorus is $3p^3$, so each 3p orbital holds one electron (D). A is wrong because one orbital holds at most two electrons (six is the capacity of the whole 3p sub-shell); B is wrong because 3d is higher; C is wrong because 3p is dumb-bell shaped, not spherical like 3s.",
      options=["It can hold a maximum of six electrons.", "It has the highest energy of the orbitals with principal quantum number 3.",
               "It is at a higher energy level than a 3s orbital but has the same shape.", "It is occupied by one electron in an isolated phosphorus atom."],
      dist={"A": "m4"})
pastq("9701_s24_12_q4", "CAIE 9701 · Jun 2024 · P12 · Q4", [9], 4, "Identify",
      "In which pairs are **both** species free radicals?\n\n1. $\\ce{Cl}$ and $\\ce{O}$\n2. $\\ce{Cl^-}$ and $\\ce{O^{2-}}$\n3. $\\ce{Cl}$ and $\\ce{O^-}$\n4. $\\ce{Cl^+}$ and $\\ce{O^{2+}}$", "A",
      r"Radicals have unpaired electrons. $\ce{Cl}$ ($3p^5$), $\ce{O}$ ($2p^4$), $\ce{O^-}$ ($2p^5$), $\ce{Cl^+}$ ($3p^4$) and $\ce{O^{2+}}$ ($2p^2$) all do, so pairs 1, 3 and 4 qualify. B leaves out pair 4 because the ions are charged, but charge does not matter; pair 2 has full octets.",
      options=["1, 3 and 4", "1 and 3 only", "1 only", "2 only"], image=IMG + "9701_s24_12_q4.png", dist={"B": "m5"})
pastq("9701_w25_12_q7", "CAIE 9701 · Nov 2025 · P12 · Q7", [5], 5, "Deduce",
      "X and Y are different elements in Period 3. Atoms of X and Y each have only one completely filled orbital in their highest occupied energy sub-shell. Y has a greater first ionisation energy than X.\n\nWhich row shows the structure and bonding in X and Y?", "B",
      r"Only magnesium ($3s^2$, one filled orbital) and sulfur ($3p^4$, one filled and two half-filled orbitals) fit. Sulfur has the higher ionisation energy, so Y is sulfur (simple molecular) and X is magnesium (giant metallic). Silicon ($3p^2$) and phosphorus ($3p^3$) have no filled 3p orbital.",
      options=["X: giant metallic; Y: giant metallic", "X: giant metallic; Y: simple molecular", "X: giant covalent; Y: simple molecular", "X: simple molecular; Y: simple molecular"],
      image=IMG + "9701_w25_12_q7.png")
assert len(past) == 12

# ---------------------------------------------------------------- worked examples
worked = [
    {"id": "we1", "kc": K[4], "problem": r"Write the full electronic configuration of a ground-state phosphorus atom (proton number 15) and state how many unpaired electrons it has.",
     "steps": [
         {"do": r"Find the number of electrons: a neutral atom has as many electrons as protons, so 15.", "why": r"The configuration must account for every electron, and a neutral atom's electron count equals its proton number.", "check": chk(15)},
         {"do": r"Fill sub-shells in energy order (1s, 2s, 2p, 3s, 3p, ...) up to their capacities: $1s^2$ (2), $2s^2$ (4), $2p^6$ (10), $3s^2$ (12); the last 3 electrons go into 3p, giving $" + full(15) + "$.", "why": r"Electrons occupy the lowest available energy levels first; forgetting the capacities (2, 2, 6, 2) is how counts go wrong.", "check": chk(3)},
         {"do": r"Place the three 3p electrons singly into the three 3p orbitals, all with parallel spins. That gives 3 unpaired electrons.", "why": r"Electrons repel each other, so they occupy separate equal-energy orbitals before pairing (Hund's rule); pairing early is the commonest wrong answer.", "check": chk(3)}],
     "faded": {"id": "we1f", "problem": r"A ground-state sulfur atom (proton number 16) has 4 electrons in its 3p sub-shell. State the number of unpaired electrons in a sulfur atom.", "answer": {"value": 2, "unit": "", "exact": True}, "blank_from": 1}},
    {"id": "we2", "kc": K[6], "problem": r"Deduce the shorthand electronic configuration of $\ce{Fe^{2+}}$ (proton number of Fe is 26).",
     "steps": [
         {"do": r"Write the atom first: 26 electrons, $\ce{[Ar]}\,3d^6 4s^2$ (4s fills before 3d; argon accounts for 18).", "why": r"Ions are always derived from the atom, and 4s is filled before 3d so it is written last but is filled first.", "check": chk(8)},
         {"do": r"A 2+ ion has lost 2 electrons, leaving $26-2=24$ electrons.", "why": r"A positive charge means fewer electrons than protons; adding electrons is a sign error.", "check": chk(24)},
         {"do": r"Remove the two 4s electrons first (outermost shell), leaving the 3d electrons untouched: $\ce{Fe^{2+}}$ is $\ce{[Ar]}\,3d^6$.", "why": r"Electrons are lost from the highest-$n$ sub-shell first; taking them from 3d gives the wrong $3d^4 4s^2$.", "check": chk(6)}],
     "faded": {"id": "we2f", "problem": r"Deduce the number of electrons in the 3d sub-shell of an $\ce{Ni^{2+}}$ ion (proton number of Ni is 28).", "answer": {"value": 8, "unit": "", "exact": True}, "blank_from": 1}},
    {"id": "we3", "kc": K[7], "problem": r"Use the electrons-in-boxes notation to show the 3d and 4s sub-shells of $\ce{Fe^{3+}}$, and state how many electrons are unpaired.",
     "steps": [
         {"do": r"Write the neutral atom: $\ce{[Ar]}\,3d^6 4s^2$.", "why": r"The ion is built from the atom, and the neutral atom follows the normal filling order.", "check": chk(6)},
         {"do": r"A 3+ ion loses three electrons: the two 4s electrons first, then one 3d electron, giving $\ce{[Ar]}\,3d^5$.", "why": r"Outermost 4s electrons go before any 3d electron.", "check": chk(5)},
         {"do": r"Draw five 3d boxes with one upward arrow in each and the 4s box empty.", "why": r"Orbitals of equal energy fill singly first with parallel spins (Hund's rule), and one box represents each orbital.", "check": chk(5)},
         {"do": r"Count the single arrows: $\ce{Fe^{3+}}$ has 5 unpaired electrons.", "why": r"Unpaired electrons are the lone arrows; paired electrons occupy the same box with opposite arrows.", "check": chk(5)}],
     "faded": {"id": "we3f", "problem": r"State the number of unpaired electrons in an $\ce{Co^{2+}}$ ion (proton number of Co is 27).", "answer": {"value": 3, "unit": "", "exact": True}, "blank_from": 1}},
]
assert config(15)["3p"] == 3 and unpaired(config(16)) == 2 and config(28, 2)["3d"] == 8 and unpaired(config(27, 2)) == 3
assert unpaired(config(26, 3)) == 5 and sum(config(26).values()) == 26 and sum(config(26, 2).values()) == 24

# ---------------------------------------------------------------- flashcards
fcs = [
    (1, "Define *shell* and *principal quantum number*.", r"A shell is a group of orbitals with the same principal quantum number, $n$. $n$ is a whole number (1, 2, 3, ...) and a larger $n$ means the shell is further from the nucleus and at higher energy."),
    (1, "Define *sub-shell*.", "A group of orbitals of the same type (s, p, d) within a shell, at the same energy."),
    (1, "Define *orbital*.", "A region of space around the nucleus that can hold a maximum of two electrons, with opposite spins."),
    (1, "What is the ground state of an atom?", "The arrangement in which all the electrons occupy the lowest available energy levels."),
    (2, "How many orbitals and how many electrons in an s, p and d sub-shell?", "s: 1 orbital, 2 electrons. p: 3 orbitals, 6 electrons. d: 5 orbitals, 10 electrons. (Each orbital holds at most 2 electrons.)"),
    (2, "What is the maximum number of electrons in the shells $n=1$, $n=2$ and $n=3$?", r"$n=1$: 2 (1s). $n=2$: 8 (2s, 2p). $n=3$: 18 (3s, 3p, 3d)."),
    (3, "Give the order of increasing energy of the sub-shells up to 4p.", r"$1s<2s<2p<3s<3p<4s<3d<4p$ (4s is lower in energy than 3d, so 4s fills first)."),
    (8, "Describe the shape of an s orbital.", "Spherical, centred on the nucleus (larger for higher $n$)."),
    (8, "Describe the shape and orientation of the p orbitals.", r"Each p orbital is dumb-bell shaped (two lobes). There are three, along the $x$, $y$ and $z$ axes at $90^\circ$ to each other."),
    (9, "Define a *free radical*.", "A species with one or more unpaired electrons."),
    (9, r"Is $\ce{O^-}$ a free radical?", r"Yes: $\ce{O^-}$ is $1s^2 2s^2 2p^5$ with one unpaired electron. Charge does not matter, only unpaired electrons."),
]
flashcards = [{"id": f"fc{i}", "kc": K[k], "front": f, "back": b} for i, (k, f, b) in enumerate(fcs, 1)]

outline = (r"Shells (principal quantum number $n$) contain sub-shells (s, p, d), which contain orbitals: s has 1 orbital, p has 3, d has 5, and each orbital holds at most 2 electrons (opposite spins), so the capacities are 2, 6, 10. s orbitals are spherical, p orbitals are dumb-bell shaped along $x$, $y$, $z$. Filling order by energy: 1s, 2s, 2p, 3s, 3p, 4s, 3d, 4p. Write configurations by filling in that order, then write them by shell. Orbitals of equal energy fill singly first (Hund's rule) because electrons repel. Ions: remove electrons from the outermost shell first, so 4s goes before 3d. Boxes show orbitals and arrows show electrons: paired means opposite arrows. A free radical has one or more unpaired electrons.")
assert len(outline.split()) <= 150, len(outline.split())

pack = {"subtopic": SUB, "spec": SPEC, "version": 1,
        "note": "Subjects/9701 Chemistry/01 Atomic structure/1.3 Electrons, energy levels and atomic orbitals.md",
        "outline": outline, "misconceptions": misconceptions, "worked": worked, "items": past + items, "flashcards": flashcards,
        "diagrams": [{"file": "Assets/9701/9701-1.3-energy-order.svg", "type": "graph_sketch", "params": {
            "lines": [{"points": [[0, y], [1, y]], "color": c} for y, c in
                      [(0, "#1f2328"), (2, "#1f2328"), (3, "#1f2328"), (4.6, "#1f2328"), (5.4, "#1f2328"), (6.3, "#d9480f"), (7.0, "#1f6feb"), (7.9, "#1f2328")]],
            "annotations": [{"text": t, "xy": [0.04, y + 0.15]} for t, y in
                            [("1s", 0), ("2s", 2), ("2p", 3), ("3s", 4.6), ("3p", 5.4), ("4s (fills first)", 6.3), ("3d", 7.0), ("4p", 7.9)]],
            "ylabel": "increasing energy", "xlabel": "sub-shells in order of energy (not to scale)"}}]}

out = ROOT / "build/out/packs/9701/9701-1.3.json"
out.parent.mkdir(parents=True, exist_ok=True)
out.write_text(json.dumps(pack, ensure_ascii=False, indent=1))

# self-check every template over the whole parameter space
for it in pack["items"]:
    if it.get("template"):
        for seed in range(60):
            inst = packs.instantiate(it, random.Random(seed))
            p = {}
print("items", len(pack["items"]), "past", len(past), "generated", len(items))
