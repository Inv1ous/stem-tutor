"""Generator for pack 9701-1.4 (Ionisation energy). Content as data; numeric answers computed and asserted here."""
import json, math
from pathlib import Path
import sympy as sp

ROOT = Path(__file__).resolve().parents[3]
SUB = "9701-1.4"
K1, K2, K3, K4, K5, K6, K7, K8 = (f"{SUB}.{i}" for i in range(1, 9))
NA = 6.02e23

# ---------- data (data-book successive ionisation energies, kJ mol^-1) and verified numbers ----------
Mg = [738, 1451, 7733, 10543, 13630, 18020, 21711, 25661, 31653, 35458, 169988, 189368]
Al = [578, 1817, 2745, 11577, 14842, 18379, 23326, 27465]
B = [801, 2427, 3660, 25026, 32827]
Si = [786, 1577, 3232, 4356, 16091, 19805, 23780, 29287]
N = [1402, 2856, 4578, 7475, 9445, 53267, 64360]
Be = [900, 1757, 14849, 21007]
K = [419, 3052, 4420, 5877, 7975, 9590]
Na8 = [496, 4562, 6910, 9543, 13354, 16613, 20117, 25496]
Cl8 = [1251, 2298, 3822, 5159, 6542, 9362, 11018, 33604]
P3 = {"Na": 496, "Mg": 738, "Al": 578, "Si": 789, "P": 1012, "S": 1000, "Cl": 1251, "Ar": 1521}


def biggest_jump(v):
    r = [v[i + 1] / v[i] for i in range(len(v) - 1)]
    return r.index(max(r)) + 1  # number of electrons before the big jump


assert biggest_jump(Mg) == 2 and biggest_jump(Mg[2:]) == 8 and Mg[10] / Mg[9] > 4.7
assert biggest_jump(Al) == 3 and biggest_jump(B) == 3 and biggest_jump(Si) == 4 and biggest_jump(N) == 5
assert biggest_jump(Be) == 2 and biggest_jump(K) == 1 and biggest_jump(Na8) == 1 and biggest_jump(Cl8) == 7
r32 = round(Mg[2] / Mg[1], 2); r21 = round(Mg[1] / Mg[0], 2)
assert (r32, r21) == (5.33, 1.97)
rN = round(N[5] / N[4], 1); assert rN == 5.6
e1_atom = 738 * 1000 / NA
assert f"{e1_atom:.2e}" == "1.23e-18"
assert Mg[0] + Mg[1] == 2189 and sum(Mg[:3]) == 9922
# valence-electron / group logic for Period 3: group = 10 + valence electrons for k >= 3
for k, g in zip(range(3, 8), range(13, 18)):
    assert 10 + k == g
# Period 2: 2p electrons = valence - 2
for k, p in zip(range(3, 8), range(1, 6)):
    assert k - 2 == p
lg = [round(math.log10(x), 2) for x in Mg]
assert lg[10] - lg[9] > 0.65 and lg[2] - lg[1] > 0.7


def mcq(i, kcs, d, cw, stem, opts, ans, expl, hints, dist=None, past=None, marks=1, **kw):
    it = {"id": f"{SUB}-{i}", "kcs": kcs, "kind": "mcq", "difficulty": d, "command_word": cw,
          "source": past or {"type": "generated"}, "stem": stem, "options": opts, "answer": ans, "marks": marks, "explanation": expl}
    if hints: it["hints"] = hints
    if dist: it["distractors"] = dist
    if not past: it["shuffle"] = True
    it.update(kw)
    return it


def past(n, qid, ref, kcs, d, stem, opts, ans, expl, dist=None, image=None):
    it = mcq(f"p{n:02d}", kcs, d, "Identify", stem, opts, ans, expl, None, dist,
             past={"type": "past", "ref": ref, "qid": qid})
    if image: it["image"] = image
    return it


def short(i, kcs, d, cw, stem, rubric, expl, hints):
    return {"id": f"{SUB}-{i}", "kcs": kcs, "kind": "short", "difficulty": d, "command_word": cw, "source": {"type": "generated"},
            "stem": stem, "rubric": rubric, "marks": len(rubric), "explanation": expl, "hints": hints}


def struct(i, kcs, d, cw, stem, scheme, expl, hints):
    return {"id": f"{SUB}-{i}", "kcs": kcs, "kind": "structured", "difficulty": d, "command_word": cw, "source": {"type": "generated"},
            "stem": stem, "scheme": scheme, "marks": len(scheme), "explanation": expl, "hints": hints}


def tab(name, vals, unit=True):
    hdr = "| " + " | ".join(f"IE {n + 1}" for n in range(len(vals))) + " |\n|" + "---|" * len(vals) + "\n"
    return hdr + "| " + " | ".join(f"{v:,}".replace(",", " ") for v in vals) + " |"


misc = [
 {"id": "m1", "kc": K1, "statement": "The first ionisation energy is the energy needed to remove an electron from one mole of gaseous atoms (or from an atom in any state).",
  "refutation": "The definition needs one electron removed from **each** atom in one mole of **gaseous** atoms, forming one mole of gaseous $1+$ ions. Removing one electron from a mole of atoms, or from atoms that are solid or liquid, is a different (and much bigger) energy change.",
  "contrast": "Removing one electron from each of $6.02\\times10^{23}$ gaseous atoms is $IE_1$. Removing one electron in total from a mole of atoms is not, because only one atom would be ionised.",
  "source": "ER 9701 s22 P23 Q1"},
 {"id": "m2", "kc": K2, "statement": "An ionisation equation can leave out the state symbols, remove more than one electron in a single step, or start from a molecule or a negative ion.",
  "refutation": "Each ionisation removes exactly one electron. The $n$th ionisation energy is for $\\ce{X^{(n-1)+}(g) -> X^{n+}(g) + e-}$, and every species must carry (g). $IE_1$ starts from the gaseous atom, so $\\ce{Mg(g) -> Mg^2+(g) + 2e-}$ is not $IE_1$, and $\\ce{Br2}$ or an anion is never the starting species.",
  "contrast": "$IE_1$ of magnesium is $\\ce{Mg(g) -> Mg+(g) + e-}$. $IE_2$ is $\\ce{Mg+(g) -> Mg^2+(g) + e-}$. The sum of the two steps gives $\\ce{Mg(g) -> Mg^2+(g) + 2e-}$, which is $IE_1+IE_2$ and not a single ionisation energy.",
  "source": "ER 9701 w20 P21 Q1"},
 {"id": "m3", "kc": K3, "statement": "Ionisation energy should increase down a group because the nuclear charge increases, or because shielding stays the same.",
  "refutation": "Nuclear charge does increase down a group, but so does shielding, because each extra shell of inner electrons screens the outer electron. The outer electron is also further from the nucleus. The net attraction on the outer electron falls, so ionisation energy decreases.",
  "contrast": "Li to Cs: more protons, but more inner shells and a larger radius. $IE_1$ falls from $520$ to $376\\ \\mathrm{kJ\\,mol^{-1}}$. Writing 'the nuclear charge increases' as the reason for a decrease loses the marks.",
  "source": "ER 9701 s23 P21 Q1"},
 {"id": "m4", "kc": K6, "statement": "The dips in first ionisation energy across Period 3 (Mg to Al, P to S) happen because a full or half-full subshell is stable, or because shielding changes.",
  "refutation": "Mg to Al: the outer electron of Al is in a 3p subshell, which is slightly higher in energy and more shielded by the 3s electrons, so it is removed more easily. P to S: S has a pair of electrons in one 3p orbital, and spin-pair repulsion makes one of them easier to remove, even though the nuclear charge is greater. Cambridge credits these two reasons.",
  "contrast": "P is $3p^3$ (three unpaired electrons) and S is $3p^4$ (one pair). $IE_1$ of S ($1000$) is below that of P ($1012\\ \\mathrm{kJ\\,mol^{-1}}$). Writing 'S has a lower nuclear charge' is false: S has one more proton.",
  "source": "ER 9701 s22 P23 Q1"},
 {"id": "m5", "kc": K8, "statement": "The group of an element is found from how large the ionisation energies are, or from the electron number after the big jump.",
  "refutation": "The group comes from the number of electrons **before** the big jump, which is the number of outer (valence) electrons. Large values alone do not fix the group. The next electron after the jump comes from an inner shell that is closer to the nucleus.",
  "contrast": "A jump between the 6th and 7th values means 6 outer electrons (Group 16), not Group 17. Data with no big jump between the 5th and 8th values (all from one inner shell) fits silicon (Group 14), not chlorine.",
  "source": "ER 9701 s23 P11 Q12"},
]

items = []
A = items.append

# ================= KC 1.4.1 definition =================
A(mcq("i01", [K1], 2, "Identify", "Which statement gives the correct definition of the first ionisation energy of an element?",
      {"A": "The energy required to remove one electron from each atom in one mole of gaseous atoms to form one mole of gaseous $1+$ ions.",
       "B": "The energy required to remove one electron from one mole of atoms of the element.",
       "C": "The energy released when one electron is removed from each atom in one mole of gaseous atoms.",
       "D": "The energy required to remove one electron from each atom in one mole of the element in its standard state."},
      "A", "Both the state and the amount matter: every atom in one mole of **gaseous** atoms loses one electron, and energy has to be put in. That gives one mole of gaseous $1+$ ions.",
      ["Check each option for the state of the atoms and for whether energy is put in or given out.", "A full definition mentions one electron, each atom, one mole, gaseous atoms and $1+$ ions.", "Rule out any option that says energy is released, and any that misses the gaseous state."],
      {"B": "m1", "D": "m1"}))
A({"id": f"{SUB}-i02", "kcs": [K1], "kind": "numeric", "difficulty": 3, "command_word": "Calculate", "source": {"type": "generated"},
   "stem": "The first ionisation energy of an element is [[ie]] kJ mol$^{-1}$. Calculate the energy, in units of $10^{-19}\\ \\mathrm{J}$, needed to remove one electron from a single gaseous atom of this element. Use $N_A = 6.02\\times10^{23}\\ \\mathrm{mol^{-1}}$.",
   "template": {"params": {"ie": {"choices": [496, 578, 738, 789, 1000, 1012, 1251, 1521]}},
                "answer": "ie*1000/6.02e23*1e19",
                "distractors": [{"expr": "ie/6.02e23*1e19"}, {"expr": "ie*1000*1e19/6.02e26"}], "constraints": ["ie > 0"]},
   "answer": {"unit": "", "sf_ok": [2, 3]}, "marks": 3,
   "explanation": "$IE_1$ is per mole of atoms. Convert kJ to J ($\\times 1000$), then divide by $N_A$ to get the energy for one atom in J: $E = \\dfrac{IE_1\\times1000}{6.02\\times10^{23}}$. Finally express it in units of $10^{-19}\\ \\mathrm{J}$.",
   "hints": ["$IE_1$ refers to a whole mole of atoms, but the question asks about one atom.", "Convert kJ to J first, then divide by the number of atoms in a mole, then express the result in units of $10^{-19}\\ \\mathrm{J}$.", "Multiply the value by 1000, then divide by $6.02\\times10^{23}$."]})
A(short("i03", [K1], 2, "Define", "Define the term *first ionisation energy*.",
        [{"point": "energy required to remove one electron (from each atom)", "keywords": [["energy"], ["remov", "lose", "take"], ["electron"]]},
         {"point": "one mole of gaseous atoms", "keywords": [["mole"], ["gaseous", "(g)", "gas "]]},
         {"point": "to form one mole of gaseous $1+$ ions", "keywords": [["1+", "+1", "unipositive", "one positive", "single positive", "positive ion", "positive ions", "cation"]]}],
        "Mark scheme wording: the energy required to remove one electron from each atom in one mole of gaseous atoms to form one mole of gaseous $1+$ ions.",
        ["Start with what is put in and what is taken out of the atom.", "State the amount (one mole), the state (gaseous) and the ion formed.", "Write it as: energy required to remove ... from each atom in ... to form ..."]))
A(struct("i04", [K1, K2], 4, "Define", "(a) Define the term *first ionisation energy*.\n(b) Write an equation, with state symbols, for the first ionisation energy of magnesium.\n(c) Explain why the first ionisation energy is always positive (endothermic).",
         [{"mark": "B1", "point": "energy required to remove one electron from each atom"},
          {"mark": "B1", "point": "in one mole of gaseous atoms (to form one mole of gaseous $1+$ ions)"},
          {"mark": "B1", "point": "$\\ce{Mg(g) -> Mg+(g) + e-}$ (state symbols and one electron required)"},
          {"mark": "B1", "point": "energy must be supplied to overcome the attraction between the positive nucleus and the negative outer electron"}],
         "The definition earns two marks (energy per electron, mole of gaseous atoms). The equation needs (g) on both species and one electron. Ionisation is endothermic because the electron is attracted to the nucleus.",
         ["(b) needs one electron and (g) on every species.", "For (c) think about what holds the outer electron in the atom.", "The electron has to be pulled away from the nucleus against an attraction."]))

# ================= KC 1.4.2 equations =================
A(mcq("i05", [K2], 3, "Identify", "Which equation represents the third ionisation energy of aluminium?",
      {"A": "$\\ce{Al2+(g) -> Al^3+(g) + e-}$", "B": "$\\ce{Al(g) -> Al^3+(g) + 3e-}$",
       "C": "$\\ce{Al2+ -> Al^3+ + e-}$", "D": "$\\ce{Al^3+(g) -> Al^4+(g) + e-}$"},
      "A", "The third ionisation removes the third electron, from $\\ce{Al2+(g)}$ to $\\ce{Al^3+(g)}$, one electron only and with state symbols.",
      ["Count how many electrons have already been removed before the third one.", "The starting particle already has a $2+$ charge, and only one electron leaves.", "Write the species before and after with the right charges and state symbols."],
      {"B": "m2", "C": "m2", "D": "m2"}))
A({"id": f"{SUB}-i06", "kcs": [K2], "kind": "numeric", "difficulty": 3, "command_word": "Calculate", "source": {"type": "generated"},
   "stem": "An element X has $IE_1$ of [[ie1]] kJ mol$^{-1}$ and $IE_2$ of [[ie2]] kJ mol$^{-1}$. Calculate the energy, in kJ, needed to convert one mole of gaseous X atoms into one mole of gaseous $\\ce{X^2+}$ ions.",
   "template": {"params": {"ie1": {"min": 500, "max": 900, "step": 10}, "k": {"choices": [1.9, 2.0, 2.1, 2.2]}},
                "derived": {"ie2": "round(ie1*k/10)*10"},
                "answer": "ie1+ie2", "distractors": [{"expr": "ie2"}, {"expr": "2*ie1"}], "constraints": ["ie1 > 0"]},
   "answer": {"unit": "kJ", "sf_ok": [2, 3, 4]}, "marks": 2,
   "explanation": "Forming $\\ce{X^2+}$ from X involves two ionisation steps: $\\ce{X(g) -> X+(g) + e-}$ then $\\ce{X+(g) -> X^2+(g) + e-}$. The energies add: $IE_1 + IE_2$.",
   "hints": ["Write the two equations that turn X into $\\ce{X^2+}$.", "The overall change is the sum of the two separate steps.", "Add the two given values."]})
A(mcq("i07", [K2], 2, "Identify", "Which equation represents the first ionisation energy of magnesium?",
      {"A": "$\\ce{Mg(g) -> Mg+(g) + e-}$", "B": "$\\ce{Mg(g) -> Mg^2+(g) + 2e-}$",
       "C": "$\\ce{Mg(s) -> Mg+(g) + e-}$", "D": "$\\ce{Mg(g) + e- -> Mg-(g)}$"},
      "A", "$IE_1$ removes one electron from a gaseous atom to give a gaseous $1+$ ion. Removing two electrons, starting from a solid, or adding an electron does not match.",
      ["Check the number of electrons removed and the states of each species.", "The reaction begins with a gaseous atom and forms a $1+$ ion.", "Eliminate equations that start from a solid or that add an electron."],
      {"B": "m2", "C": "m2", "D": "m2"}))
A(struct("i08", [K2], 4, "State", "Write equations, including state symbols, for\n(a) the first ionisation energy of sodium,\n(b) the second ionisation energy of sodium,\n(c) the third ionisation energy of nitrogen.",
         [{"mark": "B1", "point": "$\\ce{Na(g) -> Na+(g) + e-}$"},
          {"mark": "B1", "point": "$\\ce{Na+(g) -> Na^2+(g) + e-}$"},
          {"mark": "B1", "point": "$\\ce{N^2+(g) -> N^3+(g) + e-}$"},
          {"mark": "B1", "point": "state symbol (g) on every species and one electron removed in each equation"}],
         "Each equation removes one electron from a gaseous species. The starting charge is one less than the number of the ionisation, so the third ionisation of N starts from $\\ce{N^2+}$.",
         ["The starting charge is one less than the number of the ionisation.", "Each equation shows one electron leaving, with (g) on the ions and the atom.", "Write the atom or ion, then the ion with one more positive charge, then $e^-$."]))

# ================= KC 1.4.3 trends =================
A(mcq("i09", [K3], 3, "Identify", "Which statement best describes the variation of first ionisation energy across Period 3 from sodium to argon?",
      {"A": "It increases generally, with a small decrease from magnesium to aluminium and a small decrease from phosphorus to sulfur.",
       "B": "It increases steadily with no decreases at all.",
       "C": "It increases generally, with a small decrease from silicon to phosphorus and a small decrease from sulfur to chlorine.",
       "D": "It decreases generally, with small increases at magnesium and phosphorus."},
      "A", "Across the period the nuclear charge rises while the electrons are removed from the same shell, so $IE_1$ generally rises. The two dips are Mg to Al (3p electron is higher in energy) and P to S (spin-pair repulsion).",
      ["Look at the values for Na, Mg, Al, Si, P, S, Cl and Ar in order.", "There are two places where the value goes down even though the nuclear charge goes up.", "The dips involve a change of subshell and then an electron pair in a p orbital."],
      {"B": "m4"}))
A(mcq("i10", [K3], 3, "Explain", "First ionisation energy decreases from beryllium to barium. Which statement explains this?",
      {"A": "The outer electron is in a shell further from the nucleus and is shielded by more inner shells, so it is less strongly attracted.",
       "B": "The nuclear charge decreases down the group, so the attraction to the outer electron falls.",
       "C": "The nuclear charge increases and the shielding stays the same, so the attraction to the outer electron falls.",
       "D": "The atoms have more electrons, so the repulsion between electrons in the outer shell increases."},
      "A", "Down a group the outer electron is in a shell further away and is shielded by more inner shells. The increase in nuclear charge is outweighed, so the net attraction to the outer electron decreases.",
      ["Compare the outer shell of Be with that of Ba: what changes about distance and inner shells?", "Nuclear charge goes up down a group, so something else must outweigh it.", "Link distance and shielding to the attraction on the outer electron."],
      {"B": "m3", "C": "m3"}))
A(short("i11", [K3], 3, "Explain", "Explain why the first ionisation energy of magnesium is greater than that of sodium.",
        [{"point": "Mg has more protons / greater nuclear charge", "keywords": [["more proton", "greater nuclear charge", "higher nuclear charge", "larger nuclear charge", "increased nuclear charge", "12 proton"]]},
         {"point": "outer electron in the same shell / similar shielding", "keywords": [["same shell", "same energy level", "similar shielding", "same shielding", "same number of shell", "same number of inner"]]},
         {"point": "greater attraction between nucleus and outer electron", "keywords": [["attract"], ["greater", "stronger", "more", "higher"]]}],
        "Mg has one more proton, so its nuclear charge is greater. The outer electron is in the same shell (3s) with similar shielding, so the attraction between the nucleus and the outer electron is greater and more energy is needed.",
        ["Compare the number of protons in Na and Mg.", "Where is the outer electron of each atom, and how many inner shells shield it?", "Finish by comparing the attraction between nucleus and outer electron."]))
A(short("i12", [K3], 4, "Explain", "Explain why the first ionisation energy decreases down Group 1 from lithium to caesium.",
        [{"point": "outer electron in a shell further from the nucleus / larger atomic radius", "keywords": [["further", "larger", "greater distance", "more distant", "bigger", "increased radius"]]},
         {"point": "more inner shells so greater shielding", "keywords": [["shield"], ["more", "greater", "increase", "extra"]]},
         {"point": "so weaker nuclear attraction on the outer electron", "keywords": [["attraction", "attracted"], ["weaker", "less", "decrease", "lower", "reduced"]]}],
        "The outer electron is in a shell further from the nucleus and there are more inner shells shielding it. The increased nuclear charge is outweighed, so the attraction on the outer electron decreases and less energy is needed to remove it.",
        ["Think about how the outer shell changes from Li to Cs.", "Two factors weaken the nuclear attraction on the outer electron: distance and the inner shells in between.", "Link both factors to a weaker attraction, and say what that means for the energy needed."]))
A(struct("i13", [K3, K6], 5, "Explain", "The first ionisation energy of aluminium is lower than that of magnesium, and the first ionisation energy of sulfur is lower than that of phosphorus.\n\nExplain each of these two observations.",
         [{"mark": "B1", "point": "Al: outer electron is in a 3p subshell, which is higher in energy (further from the nucleus) than the 3s subshell of Mg"},
          {"mark": "B1", "point": "Al: the 3p electron is shielded by the 3s electrons, so it is less strongly attracted and easier to remove"},
          {"mark": "B1", "point": "S: two electrons are paired in one 3p orbital (3p$^4$), whereas P has three unpaired 3p electrons (3p$^3$)"},
          {"mark": "B1", "point": "S: spin-pair repulsion makes it easier to remove one of the paired electrons, outweighing the greater nuclear charge"}],
         "Mg is $3s^2$ and Al is $3p^1$: the 3p electron is higher in energy and shielded by 3s. P is $3p^3$ and S is $3p^4$: the paired electrons repel and one is lost more easily, despite the extra proton in S.",
         ["Write the outer electron configurations of Mg, Al, P and S.", "For Al, compare the subshell the electron is removed from; for S, look at whether any electrons are paired.", "Name the effect on the electron in each case: subshell energy, shielding and spin-pair repulsion."]))

# ================= KC 1.4.4 successive =================
A(mcq("i14", [K4], 3, "Explain", "Why does each successive ionisation energy of an element increase?",
      {"A": "After each electron is removed the remaining electrons are drawn closer to the same nuclear charge, with less electron repulsion, so they are held more strongly.",
       "B": "Each time an electron is removed the nuclear charge increases by one, so the attraction increases.",
       "C": "Electrons removed from a positive ion are always taken from a lower shell.",
       "D": "The electron being removed has to overcome the repulsion of the electron already removed."},
      "A", "The nuclear charge stays the same but there are fewer electrons, so the electron cloud contracts and there is less repulsion between electrons. The attraction on each remaining electron increases, so the next ionisation energy is larger.",
      ["The number of protons in the nucleus does not change during ionisation.", "Think about what happens to the size of the ion and to the repulsion between the remaining electrons.", "Compare the attraction on an electron in an ion with that in a neutral atom."],
      None))
A(mcq("i16", [K4], 3, "Identify", "For the element aluminium, which pair of successive ionisation energies has the largest difference between them?",
      {"A": "first and second", "B": "second and third", "C": "third and fourth", "D": "fourth and fifth"},
      "C", "Aluminium has three outer electrons (3s$^2$3p$^1$). The fourth electron comes from the second shell, which is closer to the nucleus and much less shielded, so a large jump occurs between the third and fourth ionisation energies.",
      ["Write the electron configuration of aluminium and count the outer electrons.", "A big jump appears when the next electron comes from a different, inner shell.", "Find the position after the last outer electron."],
      None))
A(short("i17", [K4, K7], 4, "Explain", "The third ionisation energy of magnesium ($7733\\ \\mathrm{kJ\\,mol^{-1}}$) is much greater than its second ionisation energy ($1451\\ \\mathrm{kJ\\,mol^{-1}}$). Explain why.",
        [{"point": "the third electron is removed from an inner shell (second shell / $n=2$)", "keywords": [["inner", "second shell", "2nd shell", "n = 2", "n=2", "different shell", "lower shell", "2p"]]},
         {"point": "closer to the nucleus / less shielded", "keywords": [["closer", "nearer", "less shield", "smaller radius", "less shielding"]]},
         {"point": "greater nuclear attraction so more energy needed", "keywords": [["attract", "held more strongly", "held more tightly"], ["greater", "stronger", "more", "higher"]]}],
        "Mg has two outer electrons in the third shell. The third electron is removed from the second shell, which is closer to the nucleus and less shielded, so it is more strongly attracted and needs much more energy.",
        ["How many outer electrons does magnesium have?", "After those two, which shell does the next electron come from?", "Compare distance from the nucleus, shielding and attraction for this electron."]))
A(struct("i18", [K4, K7], 5, "Explain", "The first twelve ionisation energies of magnesium (kJ mol$^{-1}$) are:\n\n" + tab("Mg", Mg) +
         "\n\n(a) Deduce the group of magnesium from these data.\n(b) Explain why the third ionisation energy is much greater than the second.\n(c) Explain why the 11th ionisation energy is much greater than the 10th.",
         [{"mark": "B1", "point": "Group 2, because there is a big jump between the 2nd and 3rd ionisation energies (two outer electrons)"},
          {"mark": "B1", "point": "the third electron is removed from an inner shell (the second shell) closer to the nucleus and less shielded"},
          {"mark": "B1", "point": "so it is held by a greater nuclear attraction and much more energy is needed"},
          {"mark": "B1", "point": "the 11th electron is removed from the first shell ($1s$), the closest shell to the nucleus with the least shielding, giving the second big jump (shells $2$, $8$, $2$)"}],
         "Magnesium has electron shells of 2, 8 and 2 electrons. The big jumps come after the 2nd (start of the second shell) and after the 10th (start of the first shell).",
         ["Look for large jumps and count how many electrons are removed before each.", "Each jump marks the start of a new, closer shell.", "Magnesium has 12 electrons in shells of 2, 8, 2; use that to place the second jump."]))

# ================= KC 1.4.5 nuclear attraction =================
A(mcq("i19", [K5], 2, "Explain", "Why is energy needed to remove an electron from a gaseous atom?",
      {"A": "The negative electron is attracted to the positive nucleus.",
       "B": "The negative electron is repelled by the positive nucleus.",
       "C": "The electron is attracted to the other electrons in the atom.",
       "D": "The electron is held in place by the neutrons."},
      "A", "Ionisation energy measures how strongly the negatively charged outer electron is attracted to the positively charged nucleus. Energy must overcome this electrostatic attraction.",
      ["Think about the charges on the electron and the nucleus.", "What kind of force acts between opposite charges?", "Energy has to be put in to overcome that force."],
      {"B": "m1"}))
A(mcq("i20", [K5], 3, "Identify", "Which change would increase the attraction between the nucleus and the outer electron of an atom?",
      {"A": "More protons in the nucleus with the outer electron in the same shell.",
       "B": "Adding an extra inner shell of electrons.",
       "C": "Fewer protons in the nucleus.",
       "D": "The outer electron moving to a shell further from the nucleus."},
      "A", "Attraction increases with the nuclear charge and decreases with distance and with shielding. More protons with the outer electron in the same shell gives a larger nuclear charge and about the same shielding.",
      ["List what makes an electrostatic attraction stronger or weaker.", "A larger nuclear charge, a shorter distance and less shielding all raise the attraction.", "Look for the option where only the nuclear charge changes."],
      {"B": "m3"}))
A(short("i21", [K5], 2, "Explain", "Explain why energy has to be supplied to remove an electron from an atom.",
        [{"point": "there is an attraction between the nucleus (protons) and the (outer) electron", "keywords": [["attract"], ["nucle", "proton"], ["electron"]]},
         {"point": "energy is needed to overcome this attraction", "keywords": [["overcome", "break", "work against", "pull"], ["energy"]]}],
        "Opposite charges attract: the positive nucleus attracts the negative electron, so energy must be supplied to overcome the electrostatic attraction.",
        ["Think about the charges of the particles involved.", "What force holds the electron in the atom?", "State the force, then say what the energy is used for."]))
A(mcq("i22", [K5], 4, "Explain", "Which statement about the first ionisation energy of an atom is correct?",
      {"A": "It depends on the strength of attraction between the nucleus and the outer electron.",
       "B": "It depends on how strongly the outer electron is attracted to the inner electrons.",
       "C": "It depends only on the number of protons in the nucleus.",
       "D": "It depends only on the number of electrons in the outer shell."},
      "A", "Ionisation energy depends on the net attraction between the nucleus and the outer electron. This depends on nuclear charge, distance and shielding, not on one factor alone.",
      ["Which particles attract each other to hold the outer electron?", "Several factors affect the attraction: it is more than a single count.", "Reject options that use 'only'."],
      {"C": "m3"}))
A(short("i23", [K5, K6], 4, "Explain", "The first ionisation energy of helium ($2372\\ \\mathrm{kJ\\,mol^{-1}}$) is much greater than that of lithium ($520\\ \\mathrm{kJ\\,mol^{-1}}$). Explain this difference in terms of the attraction between the nucleus and the outer electron.",
        [{"point": "Li outer electron is in a shell further from the nucleus (second shell) than He (first shell)", "keywords": [["further", "more distant", "second shell", "2nd shell", "n=2", "n = 2", "greater distance", "larger"]]},
         {"point": "Li outer electron is shielded by the inner electrons (1s)", "keywords": [["shield"]]},
         {"point": "so there is a weaker attraction between the nucleus and the outer electron in Li", "keywords": [["attraction", "attracted"], ["weaker", "less", "lower", "smaller"]]}],
        "The outer electron of helium is in the first shell, close to the nucleus and unshielded. The outer electron of lithium is in the second shell, further out and shielded by the inner electrons, so it is attracted less strongly.",
        ["Compare the shell that the outer electron is in for each atom.", "Consider whether other electrons come between the outer electron and the nucleus.", "Link both points to the strength of attraction."]))
A(struct("i24", [K5], 4, "Describe", "Ionisation energy is the result of the electrostatic attraction between the nucleus and an outer electron.\n\n(a) State two factors that increase this attraction.\n(b) State two factors that decrease this attraction.",
         [{"mark": "B1", "point": "greater nuclear charge (more protons)"},
          {"mark": "B1", "point": "smaller distance between the nucleus and the outer electron (smaller atomic or ionic radius)"},
          {"mark": "B1", "point": "more inner shells or subshells of electrons shielding the outer electron"},
          {"mark": "B1", "point": "a larger distance (a bigger radius), or spin-pair repulsion between two electrons in one orbital"}],
         "Attraction increases with nuclear charge and with a smaller distance; it decreases with more shielding, a larger radius, and spin-pair repulsion within an orbital.",
         ["Think of the nucleus and the electron as opposite charges and consider what changes their attraction.", "One factor is the number of protons; another is distance.", "Which electrons lie between the nucleus and the outer electron, and which pair repel?"]))

# ================= KC 1.4.6 factors =================
A(mcq("i25", [K6], 4, "Explain", "The first ionisation energy of oxygen is lower than that of nitrogen. Which statement explains this?",
      {"A": "Two of the oxygen 2p electrons are paired in one orbital, and the repulsion between them makes one easier to remove.",
       "B": "Oxygen has a lower nuclear charge than nitrogen.",
       "C": "Oxygen has more shielding by inner shells than nitrogen.",
       "D": "The half-filled 2p subshell in nitrogen is more stable, so it has a lower energy."},
      "A", "N is $2p^3$ (three unpaired electrons) and O is $2p^4$ (one pair). Spin-pair repulsion raises the energy of an electron in the pair, so it is easier to remove. The nuclear charge of O is greater and the shielding is the same.",
      ["Write the electron configurations of N and O.", "Oxygen has one more proton and the same inner shells as nitrogen, so those factors do not explain the drop.", "Look at how the 2p electrons are arranged in the orbitals."],
      {"D": "m4"}))
A(mcq("i26", [K6], 3, "Explain", "The first ionisation energy of sodium is much lower than that of neon. Which statement explains this?",
      {"A": "The outer electron of sodium is in a new shell further from the nucleus and is shielded by more inner electrons.",
       "B": "Sodium has a greater nuclear charge than neon.",
       "C": "The outer electron in sodium is in a $2p$ orbital.",
       "D": "The atomic radius of sodium is smaller than that of neon."},
      "A", "Sodium starts a new shell (3s), further from the nucleus and shielded by the full inner shells, so its outer electron is weakly attracted. Neon's outer electron is in the second shell.",
      ["Compare the outer electron configuration of Na and Ne.", "Which atom has its outer electron in a new shell?", "Consider distance and shielding together."],
      {"B": "m3"}))

# ================= KC 1.4.7 config from data =================
A({"id": f"{SUB}-i28", "kcs": [K7], "kind": "numeric", "difficulty": 3, "command_word": "Deduce", "source": {"type": "generated"},
   "stem": "An element in Period 2 has successive ionisation energies with a very large increase between the [[k]]th and the [[k1]]th values. How many electrons does its atom have in the $2p$ subshell?",
   "template": {"params": {"k": {"choices": [3, 4, 5, 6, 7]}}, "derived": {"k1": "k+1"},
                "answer": "k-2", "distractors": [{"expr": "k"}, {"expr": "k+1"}], "constraints": ["k > 2"]},
   "answer": {"unit": "", "sf_ok": [1]}, "marks": 2,
   "explanation": "The big jump shows the number of electrons in the outer (second) shell, $k$. Two of these are in $2s$, so the number in $2p$ is $k-2$.",
   "hints": ["The size of the big jump shows how many electrons are in the outer shell.", "The outer shell of a Period 2 element is $2s$ plus $2p$; the $2s$ subshell is full.", "Subtract the electrons in $2s$ from the outer-shell total."]})
A(mcq("i29", [K7], 3, "Deduce", "The first five ionisation energies of an element in Period 2 are 801, 2427, 3660, 25 026 and 32 827 kJ mol$^{-1}$. What is the outer electron configuration of the element?",
      {"A": "$2s^2\\,2p^1$", "B": "$2s^2$", "C": "$2s^2\\,2p^2$", "D": "$2s^2\\,2p^4$"},
      "A", "The big jump is between the 3rd and 4th values, so there are three outer electrons: $2s^2\\,2p^1$.",
      ["Look for the biggest jump in the data.", "Count how many ionisation energies come before the jump.", "Fill $2s$ first and put the remaining outer electrons in $2p$."],
      None))
A(struct("i30", [K7], 5, "Deduce", "The first eight ionisation energies of an element in Period 3 (kJ mol$^{-1}$) are:\n\n" + tab("Si", Si) +
         "\n\n(a) Deduce the number of outer electrons.\n(b) Deduce the full electronic configuration, using $1s^2$ notation.\n(c) State the shell from which the 5th electron is removed.",
         [{"mark": "M1", "point": "identifies the big jump between the 4th and 5th ionisation energies", "check": {"kind": "numeric", "answer": {"value": 4, "unit": "", "exact": True}}},
          {"mark": "A1", "point": "4 outer electrons (Group 14)"},
          {"mark": "A1", "point": "$1s^2\\,2s^2\\,2p^6\\,3s^2\\,3p^2$"},
          {"mark": "B1", "point": "the 5th electron is from the second shell ($n=2$), an inner shell closer to the nucleus"}],
         "The jump from the 4th to the 5th value shows four outer electrons. In Period 3 this gives $3s^2\\,3p^2$ after the full $1s^2\\,2s^2\\,2p^6$ core.",
         ["Find the largest increase between consecutive values and count the values before it.", "A Period 3 element has the core $1s^2\\,2s^2\\,2p^6$ then its outer electrons in $3s$ and $3p$.", "For (c) consider the shell after the outer shell has lost all its electrons."]))

# ================= KC 1.4.8 group =================
A({"id": f"{SUB}-i15", "kcs": [K8, K4], "kind": "numeric", "difficulty": 3, "command_word": "Deduce", "source": {"type": "generated"},
   "stem": "The successive ionisation energies of an element in Period 3 show the largest increase between the [[k]]th and the [[k1]]th values. In which group of the Periodic Table is the element? Give the group number.",
   "template": {"params": {"k": {"choices": [3, 4, 5, 6, 7]}}, "derived": {"k1": "k+1"},
                "answer": "k+10", "distractors": [{"expr": "k", "misconception": "m5"}, {"expr": "k+11", "misconception": "m5"}],
                "constraints": ["k > 2"]},
   "answer": {"unit": "", "sf_ok": [2]}, "marks": 2,
   "explanation": "The big jump comes after the last outer electron, so there are $k$ outer electrons. In Period 3 the element with $k$ outer electrons is in Group $10+k$ (for $k\\ge3$).",
   "hints": ["The largest jump shows where an inner shell starts to be ionised.", "The number of ionisation energies before the jump equals the number of outer electrons.", "In Period 3 the group number is 10 more than the number of outer electrons (for three or more)."]})
A(mcq("i32", [K8], 3, "Deduce", "The first six ionisation energies of an element in Period 4 are 419, 3052, 4420, 5877, 7975 and 9590 kJ mol$^{-1}$. In which group of the Periodic Table is the element?",
      {"A": "Group 1", "B": "Group 2", "C": "Group 3", "D": "Group 6"},
      "A", "The largest increase is between the 1st and 2nd values ($3052/419\\approx7.3$), so the element has one outer electron and is in Group 1.",
      ["Compare each value with the one before it.", "The biggest increase marks the start of an inner shell.", "The number of electrons before the jump is the number of outer electrons."],
      {"D": "m5"}))
A(struct("i33", [K8, K4], 5, "Deduce", "Elements Q and R are in Period 3. The first eight ionisation energies (kJ mol$^{-1}$) of element Q are:\n\n" + tab("Q", Na8) + "\n\nThose of element R are:\n\n" + tab("R", Cl8) + "\n\n(a) Deduce the group of Q.\n(b) Deduce the group of R.\n(c) Deduce the formula of the ionic compound formed between Q and R.",
         [{"mark": "M1", "point": "Q: big jump between the 1st and 2nd values, so Group 1", "check": {"kind": "numeric", "answer": {"value": 1, "unit": "", "exact": True}}},
          {"mark": "M1", "point": "R: big jump between the 7th and 8th values, so 7 outer electrons and Group 17", "check": {"kind": "numeric", "answer": {"value": 17, "unit": "", "exact": True}}},
          {"mark": "A1", "point": "Q forms $\\mathrm{Q^+}$ and R forms $\\mathrm{R^-}$, so the formula is QR"}],
         "Q has one outer electron (Group 1) and R has seven (Group 17). Q loses one electron and R gains one, so they combine 1 : 1.",
         ["Find the largest jump in each row.", "The number of values before the jump is the number of outer electrons.", "Group 1 loses one electron; Group 17 gains one."]))

flash = [
 {"id": "fc1", "kc": K1, "front": "Define the first ionisation energy.", "back": "The energy required to remove one electron from each atom in one mole of gaseous atoms to form one mole of gaseous $1+$ ions."},
 {"id": "fc2", "kc": K1, "front": "Write the general equation for the first ionisation energy of X.", "back": "$\\ce{X(g) -> X+(g) + e-}$, with (g) on both X and $\\ce{X+}$."},
 {"id": "fc3", "kc": K1, "front": "Is first ionisation energy exothermic or endothermic? Why?", "back": "Endothermic ($\\Delta H$ positive): energy must be supplied to overcome the attraction between the nucleus and the outer electron."},
 {"id": "fc4", "kc": K2, "front": "Write the equation for the second ionisation energy of magnesium.", "back": "$\\ce{Mg+(g) -> Mg^2+(g) + e-}$"},
 {"id": "fc5", "kc": K2, "front": "What starts and ends the equation for the $n$th ionisation energy?", "back": "It starts from $\\ce{X^{(n-1)+}(g)}$ and ends with $\\ce{X^{n+}(g)}$ plus one electron, with (g) on every species."},
 {"id": "fc6", "kc": K3, "front": "State the trend in first ionisation energy across a period, and the two exceptions in Period 3.", "back": "Generally increases across a period. Exceptions: Al is lower than Mg (3p electron, higher energy and shielded by 3s), and S is lower than P (spin-pair repulsion in a 3p orbital)."},
 {"id": "fc7", "kc": K3, "front": "Explain the trend in first ionisation energy down a group.", "back": "It decreases: the outer electron is in a shell further from the nucleus and is shielded by more inner shells, so the nuclear attraction is weaker."},
 {"id": "fc8", "kc": K4, "front": "Why do successive ionisation energies of an element increase?", "back": "Each electron is removed from an ion with a greater positive charge and fewer electrons: the same nuclear charge attracts fewer electrons, so they are closer and there is less repulsion."},
 {"id": "fc9", "kc": K4, "front": "What does a big jump in successive ionisation energies show?", "back": "The next electron is being removed from an inner shell that is closer to the nucleus and less shielded, so the attraction is much greater."},
 {"id": "fc10", "kc": K5, "front": "What causes ionisation energy in terms of forces?", "back": "The electrostatic attraction between the positive nucleus and the negative outer electron."},
 {"id": "fc11", "kc": K6, "front": "List the factors that influence ionisation energy.", "back": "Nuclear charge, atomic (or ionic) radius, shielding by inner shells and subshells, and spin-pair repulsion."},
 {"id": "fc12", "kc": K7, "front": "How do you get an electron configuration from successive ionisation energies?", "back": "Count the values before each big jump: these are the electrons in the outer shell; the next group of values gives the next shell inwards."},
 {"id": "fc13", "kc": K8, "front": "How do you get the group number from successive ionisation energies?", "back": "The number of ionisation energies before the first big jump is the number of outer electrons, which gives the group (Group 1 or 2, or 10 more than the outer electrons for Groups 13 to 18)."},
]

# ---------- past-paper MCQs ----------
P = "CAIE 9701 · "
past_items = [
 past(1, "9701_w25_12_q2", P + "Nov 2025 · P12 · Q2", [K1], 2, "Which equation has an energy change that is equal to the first ionisation energy of bromine?",
      {"A": "Br(g) → Br⁺(g) + e⁻", "B": "Br(g) → Br⁻(g) – e⁻", "C": "½Br₂(g) → Br⁺(g) + e⁻", "D": "½Br₂(g) → Br⁻(g) – e⁻"}, "A",
      "$IE_1$ starts from one gaseous atom and removes one electron to give a gaseous $1+$ ion. The options that begin with $\\ce{½Br2}$ include the atomisation of the molecule, and forming $\\ce{Br-}$ is not ionisation. Options C and D start from $\\ce{½Br2(g)}$, which adds the energy to break the bond, and option B forms $\\ce{Br-}$, which is not ionisation.",
      {"B": "m2", "C": "m2", "D": "m2"}),
 past(2, "9701_w22_12_q1", P + "Nov 2022 · P12 · Q1", [K3], 3, "Why is the first ionisation energy of phosphorus greater than the first ionisation energy of silicon?",
      {"A": "A phosphorus atom has one more proton in its nucleus.", "B": "The atomic radius of a phosphorus atom is greater.",
       "C": "The outer electron in a phosphorus atom is more shielded.", "D": "The outer electron in a phosphorus atom is paired."}, "A",
      "P and Si are in the same period, so the outer electrons are in the same shell with similar shielding. P has one more proton, so its nuclear charge is greater and the attraction is stronger. Its radius is smaller, not greater, and its 3p electrons are unpaired ($3p^3$).",
      {"D": "m4"}),
 past(3, "9701_w22_12_q25", P + "Nov 2022 · P12 · Q25", [K3], 4, "T is an element in Period 3.\nThe first ionisation energy of T is lower than that of the element with one less proton.\nThe oxide of T does not react with water.\nWhat is the identity of T?",
      {"A": "aluminium", "B": "silicon", "C": "sodium", "D": "sulfur"}, "A",
      "The two dips in Period 3 are Al (lower than Mg) and S (lower than P). Sulfur's oxides react with water, but aluminium oxide does not, so T is aluminium. Sodium also has a lower first ionisation energy than the element with one less proton (neon), but its oxide reacts with water, and silicon has a higher value than aluminium.",
      {"D": "m4"}),
 past(4, "9701_w24_12_q2", P + "Nov 2024 · P12 · Q2", [K6], 3, "Which factor causes helium to have a higher first ionisation energy than hydrogen?",
      {"A": "In the 1s orbital in helium, electrons are paired.", "B": "The lowest energy level in helium is filled.",
       "C": "The nuclear charge in helium is higher than in hydrogen.", "D": "There is less shielding of the outer shell in helium."}, "C",
      "Both electrons are in the same 1s orbital, so the difference is the nuclear charge: 2 protons in He against 1 in H. Pairing lowers ionisation energy, He has more shielding than H (from its other electron), and a filled level is not itself a cause.",
      {"A": "m4"}),
 past(5, "9701_s25_13_q10", P + "Jun 2025 · P13 · Q10", [K6], 4, "Why is the second ionisation energy of sodium larger than the second ionisation energy of magnesium?",
      {"A": "The attraction between the nucleus and the outer electron is greater in Na⁺ than in Mg⁺.", "B": "The nuclear charge of Na⁺ is greater than that of Mg⁺.",
       "C": "The outer electron of Na⁺ is more shielded than the outer electron of Mg⁺.", "D": "The outer electron of Na is in the same orbital as the outer electron of Mg."}, "A",
      "The second electron of Na comes from the $2p$ subshell of $\\ce{Na+}$ (second shell, close to the nucleus), whereas the second electron of Mg comes from the $3s$ orbital of $\\ce{Mg+}$. So the attraction is greater in $\\ce{Na+}$. The nuclear charge of Na is lower (11 against 12) and its outer electron is less shielded, not more.",
      {"B": "m3"}),
 past(6, "9701_w23_13_q2", P + "Nov 2023 · P13 · Q2", [K6], 4, "The graph shows the variation of the first ionisation energy with proton number for some elements. The letters used are not the actual symbols for the elements.\nWhich statement about the elements is correct?",
      {"A": "P and X are in the same period in the Periodic Table.", "B": "The general increase from Q to X is due to increasing atomic radius.",
       "C": "The small decrease from R to S is due to decreased shielding.", "D": "The small decrease from U to V is due to repulsion between paired electrons."}, "D",
      "Q to X is Period 3 (Na to Ar); P is a noble gas in Period 2, so A is wrong. The general rise across the period is due to the increasing nuclear charge and a decreasing radius, not increasing radius. The small dip from R to S (Mg to Al) is due to the higher-energy 3p subshell, not decreased shielding. The dip from U to V (P to S) is due to repulsion between paired electrons.",
      {"C": "m4"}, image="Assets/mcq/9701_w23_13_q2.png"),
 past(7, "9701_w22_13_q4", P + "Nov 2022 · P13 · Q4", [K4], 3, "For the element sulfur, which pair of ionisation energies has the largest difference between them?",
      {"A": "third and fourth ionisation energies", "B": "fourth and fifth ionisation energies", "C": "fifth and sixth ionisation energies", "D": "sixth and seventh ionisation energies"}, "D",
      "Sulfur has six outer electrons ($3s^2\\,3p^4$). The first six are removed from the third shell, so the values rise gradually, but the seventh comes from the second shell, which is much closer to the nucleus, so the largest gap is between the sixth and seventh."),
 past(8, "9701_w21_13_q3", P + "Nov 2021 · P13 · Q3", [K4], 4, "Which of these elements has the highest fifth ionisation energy?",
      {"A": "C", "B": "N", "C": "P", "D": "Si"}, "A",
      "Carbon has only four outer electrons, so the fifth electron is removed from the 1s subshell, closest to the nucleus and the least shielded. In N, P and Si the fifth electron is either an outer electron (N and P) or from the second shell of Si (further from the nucleus and shielded by $1s^2$)."),
 past(9, "9701_s25_11_q4", P + "Jun 2025 · P11 · Q4", [K7], 3, "The first seven ionisation energies of an element between lithium and neon in the Periodic Table are shown: 1310, 3390, 5320, 7450, 11 000, 13 300 and 71 000 kJ mol⁻¹.\nWhat is the outer electronic configuration of the element?",
      {"A": "2s²", "B": "2s²2p¹", "C": "2s²2p⁴", "D": "2s²2p⁶"}, "C",
      "The big jump comes between the 6th and 7th values, so there are six outer electrons: $2s^2\\,2p^4$. A neon-like $2s^2\\,2p^6$ would have eight, and the jump would be between the 8th and 9th.",
      None, image="Assets/mcq/9701_s25_11_q4.png"),
 past(10, "9701_w25_13_q2", P + "Nov 2025 · P13 · Q2", [K7, K8], 4, "The data in the table gives the 5th to the 10th ionisation energies of three elements from Period 3 of the Periodic Table.\nWhat are the correct identities of these three elements?",
      {"A": "Na Mg Al", "B": "Mg Al Si", "C": "P S Cl", "D": "S Cl Ar"}, "C",
      "The big jumps are between the 5th and 6th values for X (5 outer electrons: P), the 6th and 7th for Y (6 outer electrons: S), and the 7th and 8th for Z (7 outer electrons: Cl). For the elements in option D, the jumps would come after the 6th, 7th and 8th values.",
      None, image="Assets/mcq/9701_w25_13_q2.png"),
 past(11, "9701_s23_11_q12", P + "Jun 2023 · P11 · Q12", [K8], 4, "Four successive ionisation energies (IE) of element E are shown: fifth 16 000, sixth 20 000, seventh 24 000 and eighth 29 000 kJ mol⁻¹.\nElement E is in Period 3 of the Periodic Table.\nIn which group of the Periodic Table is E?",
      {"A": "14", "B": "15", "C": "16", "D": "17"}, "A",
      "The four values are of similar size and rise steadily with no big jump, so they are all removed from the same inner (second) shell. This fits silicon, which has four outer electrons in the third shell and is in Group 14. Chlorine (Group 17, option D) would show a much larger 8th value than 7th value, which the data do not show.",
      {"D": "m5"}, image="Assets/mcq/9701_s23_11_q12.png"),
 past(12, "9701_s24_12_q3", P + "Jun 2024 · P12 · Q3", [K8], 4, "The first eight successive ionisation energies for two elements of Period 3 of the Periodic Table are shown in the graphs.\nWhat is the formula of the ionic compound formed from these elements?",
      {"A": "MgCl₂", "B": "CaBr₂", "C": "Na₂S", "D": "K₂Se"}, "A",
      "One graph shows a big jump after the 7th electron (seven outer electrons, Group 17, chlorine), the other after the 2nd (Group 2, magnesium). Both are in Period 3, and they form $\\ce{MgCl2}$. Calcium, bromine, potassium and selenium are in Period 4.",
      None, image="Assets/mcq/9701_s24_12_q3.png"),
]
items = past_items + items

# ---------- worked examples ----------
worked = [
 {"id": "we1", "kc": K2, "problem": "Write the equation, with state symbols, for the third ionisation energy of aluminium.",
  "steps": [
   {"do": "Count the electrons already removed: the first and second, so the third ionisation starts from $\\ce{Al^2+}$.", "why": "The $n$th ionisation acts on the ion left after $n-1$ electrons have gone, and students often start from the neutral atom.", "check": {"kind": "numeric", "answer": {"value": 2, "unit": "", "exact": True}}},
   {"do": "Remove one electron: the ion becomes $\\ce{Al^3+}$ and one electron $e^-$ is released.", "why": "Every ionisation energy is for the loss of exactly one electron, so the charge increases by one.", "check": {"kind": "numeric", "answer": {"value": 3, "unit": "", "exact": True}}},
   {"do": "Put state symbols on every species: $\\ce{Al^2+(g) -> Al^3+(g) + e-}$.", "why": "Ionisation energies are defined for gaseous species and the mark scheme requires (g) on the ions."}],
  "faded": {"id": "we1f", "problem": "Write the equation for the third ionisation energy of phosphorus. What is the charge on the ion formed?", "answer": {"value": 3, "unit": "", "exact": True}, "blank_from": 1}},
 {"id": "we2", "kc": K7, "problem": "The first six ionisation energies of magnesium are 738, 1451, 7733, 10 543, 13 630 and 18 020 kJ mol$^{-1}$. Deduce the outer electron configuration of magnesium.",
  "steps": [
   {"do": "Compare each value with the one before: $1451/738 \\approx 2.0$, then $7733/1451 \\approx 5.3$, then $10543/7733 \\approx 1.4$.", "why": "A big jump shows a change of shell, so look at the ratios.", "check": {"kind": "numeric", "answer": {"value": r32, "unit": "", "sf_ok": [2, 3]}}},
   {"do": "The big jump follows the 2nd value, so there are two outer electrons.", "why": "The number of values before the big jump equals the number of outer electrons."},
   {"do": "Magnesium is in Period 3, so the two outer electrons are in $3s$: outer configuration $3s^2$ (full $1s^2\\,2s^2\\,2p^6\\,3s^2$).", "why": "The outer shell is the third, and $3s$ fills before $3p$."}],
  "faded": {"id": "we2f", "problem": "The first five ionisation energies of an element in Period 3 are 578, 1817, 2745, 11 577 and 14 842 kJ mol$^{-1}$. How many electrons does its atom have in the $3p$ subshell?", "answer": {"value": 1, "unit": "", "exact": True}, "blank_from": 1}},
 {"id": "we3", "kc": K8, "problem": "The first seven ionisation energies of an element in Period 2 are 1402, 2856, 4578, 7475, 9445, 53 267 and 64 360 kJ mol$^{-1}$. Deduce the group of the element.",
  "steps": [
   {"do": "Find the biggest jump: $53267/9445 \\approx 5.6$, between the 5th and 6th values.", "why": "A jump in ionisation energy of this size shows that the next electron comes from an inner shell.", "check": {"kind": "numeric", "answer": {"value": rN, "unit": "", "sf_ok": [2]}}},
   {"do": "There are five electrons before the jump, so the element has five outer electrons.", "why": "The electrons before the jump are all in the outer shell; the group is not found from the size of the values."},
   {"do": "In Period 2 the element with five outer electrons ($2s^2\\,2p^3$) is in Group 15.", "why": "For Groups 13 to 18 the group number is 10 plus the number of outer electrons.", "check": {"kind": "numeric", "answer": {"value": 15, "unit": "", "exact": True}}}],
  "faded": {"id": "we3f", "problem": "The first four ionisation energies of an element in Period 2 are 900, 1757, 14 849 and 21 007 kJ mol$^{-1}$. In which group is the element?", "answer": {"value": 2, "unit": "", "exact": True}, "blank_from": 1}},
]

diagrams = [
 {"file": "Assets/9701/9701-1.4-period3-ie1.svg", "type": "graph_sketch", "params": {
   "lines": [{"points": [[11 + i, v] for i, v in enumerate(P3.values())]}],
   "annotations": [{"text": "Mg to Al: 3p higher in energy", "xy": [13, 578], "xytext": [11.2, 200]},
                   {"text": "P to S: spin-pair repulsion", "xy": [16, 1000], "xytext": [13.6, 350]}],
   "xlabel": "proton number (Na = 11 ... Ar = 18)", "ylabel": "first ionisation energy / kJ mol$^{-1}$", "ticks": True}},
 {"file": "Assets/9701/9701-1.4-log-ie-mg.svg", "type": "graph_sketch", "params": {
   "lines": [{"points": [[i + 1, v] for i, v in enumerate(lg)]}],
   "annotations": [{"text": "3rd electron: 2nd shell", "xy": [3, lg[2]], "xytext": [4.5, 3.2]},
                   {"text": "11th electron: 1st shell", "xy": [11, lg[10]], "xytext": [5.2, 5.0]}],
   "xlabel": "number of electrons removed", "ylabel": "log10 (IE / kJ mol$^{-1}$)", "ticks": True}},
]

pack = {"subtopic": SUB, "spec": "9701", "version": 1,
 "note": "Subjects/9701 Chemistry/01 Atomic structure/1.4 Ionisation energy.md",
 "outline": "First ionisation energy is the energy required to remove one electron from each atom in one mole of gaseous atoms to form one mole of gaseous $1+$ ions: $\\ce{X(g) -> X+(g) + e-}$. Successive ionisation energies remove one electron at a time from the ion left, and always increase. Ionisation energy comes from the attraction between the nucleus and the outer electron, which depends on nuclear charge, distance, shielding and spin-pair repulsion. It generally rises across a period (dips at Al and S) and falls down a group. A big jump in successive values marks a new inner shell: the number of electrons before it gives the outer electrons, the group and the configuration.",
 "misconceptions": misc, "worked": worked, "items": items, "flashcards": flash, "diagrams": diagrams}
out = ROOT / "build/out/packs/9701/9701-1.4.json"
out.parent.mkdir(parents=True, exist_ok=True)
out.write_text(json.dumps(pack, indent=1, ensure_ascii=False))
print("items", len(items), "words outline", len(pack["outline"].split()))
