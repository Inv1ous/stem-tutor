"""Build a deterministic, provenance-carrying corpus without learner data or model calls.

Published cards/visible worked examples are *source transformation* tasks: the
prompt carries the source and gold preserves it. They are not independently
verified exam mark schemes. Synthetic answers use small exact calculations or
explicitly curated truth tables. Nothing is read outside the published pack tree.
"""
from __future__ import annotations

import argparse
from collections import Counter
from fractions import Fraction
import hashlib
import json
from pathlib import Path
import re

from .chat_output import DocumentDecoder, DocumentError

SEED = 20261026
FORMAT = "STEM Tutor. Reply in document JSON. "
MATH_SPECS = {"D1", "FP1", "FP2", "FP3", "M1", "P1", "P2", "P3", "P4", "S1", "S2", "S3"}


def _json(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _sha(value):
    return hashlib.sha256(value if isinstance(value, bytes) else value.encode()).hexdigest()


def _pack_root(packs):
    # Support the app's public Packs facade without calling accessors that can
    # discover state, learner logs, or drafts.
    if not isinstance(packs, (str, Path)):
        packs = packs.root if hasattr(packs, "root") else packs.tutor / "packs"
    root = Path(packs)
    if (root / ".tutor/packs").is_dir():
        root = root / ".tutor/packs"
    if root.name == "CURRENT" and root.is_file():
        marker = root
    else:
        marker = root / "CURRENT"
    if marker.is_file():
        version = marker.read_text().strip()
        if not re.fullmatch(r"v[0-9]+", version):
            raise ValueError("Invalid published pack CURRENT version")
        root = marker.parent / version
    if not root.is_dir() or not list(root.glob("specs/*/packs/*.json")):
        raise ValueError("Expected a published pack root, CURRENT file, or vault")
    return root.resolve()


def _source_blocks(text, kind="paragraph"):
    if not isinstance(text, str) or not text.strip() or len(text) > 20000:
        raise ValueError("empty_or_unsupported_source")
    # No repairs or scientific paraphrasing: normal paragraph boundaries and
    # whole-source equation delimiters are the only transformations.
    blocks = []
    for part in re.split(r"\n\s*\n", text.strip()):
        if part.startswith("$$") and part.endswith("$$") and part.count("$$") == 2:
            blocks.append({"kind": "equation", "text": part[2:-2].strip()})
        elif part.startswith("$") and part.endswith("$") and part.count("$") == 2:
            blocks.append({"kind": "equation", "text": part[1:-1].strip()})
        else:
            if part.count("$") % 2:
                raise ValueError("unbalanced_math_delimiters")
            blocks.append({"kind": kind, "text": part})
    return blocks


def _row(group, subject, task, question, expected, provenance, **checks):
    if "blocks" in expected:
        decoder = DocumentDecoder(speech="speech" in expected)
        decoder.feed(_json(expected))
        decoder.finish()
        # A repaired control or step wrapper is not acceptable gold. Source must
        # already meet the transport contract.
        if decoder.document != expected:
            raise ValueError("source_requires_repair")
    else:
        if set(expected) != {"points", "feedback"} or not isinstance(expected["feedback"], str):
            raise ValueError("invalid_marking_gold")
        if not expected["points"] or any(set(p) != {"point", "met", "why"}
                or type(p["met"]) is not bool for p in expected["points"]):
            raise ValueError("invalid_marking_gold")
    content = _json(expected)
    return {"id": _sha(_json([subject, task, question, expected]))[:24], "group": group,
            "subject": subject, "task": task,
            "messages": [{"role": "user", "content": question},
                         {"role": "assistant", "content": content}],
            "expected": expected, "provenance": provenance,
            "checks": {"validated": True, "schema": "document" if "blocks" in expected else "marking",
                       **checks}}


def _public_rows(root, rejected, sources):
    rows = []
    for path in sorted(root.glob("specs/*/packs/*.json")):
        if path.is_symlink() or root not in path.resolve().parents:
            rejected.append({"source": str(path.relative_to(root)), "reason": "source_outside_published_tree"})
            continue
        relative = path.relative_to(root).as_posix()
        blob = path.read_bytes()
        sources.append({"path": relative, "sha256": _sha(blob)})
        try:
            pack = json.loads(blob)
        except (ValueError, UnicodeError):
            rejected.append({"source": relative, "reason": "malformed_pack_json"})
            continue
        spec = path.parents[1].name
        subject = "chem" if spec == "9701" else "phys" if spec == "9702" else "math" if spec in MATH_SPECS else None
        if subject is None or not isinstance(pack, dict) or pack.get("spec") != spec:
            rejected.append({"source": relative, "reason": "unsupported_or_inconsistent_spec"})
            continue
        subtopic = pack.get("subtopic")
        if not isinstance(subtopic, str) or not subtopic.startswith(spec + "-"):
            rejected.append({"source": relative, "reason": "invalid_subtopic"})
            continue
        for collection in ("flashcards", "worked"):
            entries = pack.get(collection, [])
            if not isinstance(entries, list):
                rejected.append({"source": relative, "reason": "invalid_collection"})
                continue
            for entry in entries:
                ident = entry.get("id", "unknown") if isinstance(entry, dict) else "unknown"
                try:
                    if not isinstance(entry, dict) or not isinstance(entry.get("kc"), str) or not entry["kc"].startswith(subtopic + "."):
                        raise ValueError("missing_or_inconsistent_kc")
                    provenance = [{"kind": "published_pack", "spec": spec, "kc": entry["kc"],
                                   "pack_version": root.name, "content_version": pack.get("version"),
                                   "file": relative, "sha256": _sha(blob), "source_id": ident,
                                   "source_field": collection}]
                    if collection == "flashcards":
                        front = entry.get("front")
                        if not isinstance(front, str) or not front.strip():
                            raise ValueError("empty_or_unsupported_source")
                        blocks = _source_blocks(entry.get("back"))
                        question = (FORMAT + "Answer the published study-card question using only its supplied answer; "
                                    "preserve every qualification, symbol and requested part.\n"
                                    + _json({"qualification": "CAIE A Level " + spec if spec in {"9701", "9702"} else "Edexcel IAL " + spec,
                                             "question": front, "published_answer": entry["back"]}))
                        task = "published_flashcard"
                    else:
                        if not isinstance(entry.get("problem"), str) or not entry["problem"].strip() or not isinstance(entry.get("steps"), list) or not entry["steps"]:
                            raise ValueError("empty_or_unsupported_source")
                        blocks = []
                        visible = []
                        for step in entry["steps"]:
                            if not isinstance(step, dict):
                                raise ValueError("empty_or_unsupported_source")
                            action, why = step.get("do"), step.get("why")
                            blocks.extend(_source_blocks(action, "step"))
                            blocks.extend(_source_blocks(why))
                            visible.append({"do": action, "why": why})
                        question = (FORMAT + "Reformat the supplied visible worked solution. Preserve all its steps and reasons "
                                    "without adding scientific claims or deriving hidden reasoning. This is source transcription.\n"
                                    + _json({"problem": entry["problem"], "visible_solution": visible}))
                        task = "published_worked"
                    rows.append(_row("public:" + subtopic, subject, task, question, {"blocks": blocks}, provenance,
                                     source_fidelity=True, scientific_truth="published_source_not_independently_rederived",
                                     question_family_sha256=_sha(" ".join((front if collection == "flashcards" else entry["problem"]).casefold().split()))))
                except (ValueError, DocumentError, TypeError) as error:
                    reason = str(error) if isinstance(error, ValueError) and not isinstance(error, DocumentError) else "invalid_document_source"
                    rejected.append({"source": relative, "source_id": ident, "reason": reason})
    return rows


def _synthetic(subject, family, question, blocks, reference, **checks):
    return _row("synthetic:" + family, subject, "open_hint" if family.startswith("open_hint_") else family, FORMAT + question, {"blocks": blocks},
                [{"kind": "verified_synthetic", "reference": reference, "version": 1,
                  "sha256": _sha(reference)}], truth="exact_formula_or_curated", **checks)


def _calc(subject, family, question, equation, reference, **checks):
    return _synthetic(subject, family, question,
                      [{"kind": "step", "text": "Substitute the given quantities into the stated relationship."},
                       {"kind": "equation", "text": equation}], reference, **checks)


def _synthetic_rows():
    rows = []
    # Algorithm families are indivisible, including every numerical variant.
    for n in range(2, 14):
        rows.extend([
            _calc("phys", "force_calculation", f"A constant mass {n} kg accelerates at 3 m s^-2. Calculate resultant force with F=ma.",
                  rf"F={n}\times3={n*3}\,\mathrm{{N}}", "Newton II for constant mass: F=ma; kg m s^-2=N", inputs={"mass": n, "acceleration": 3}),
            _calc("phys", "kinetic_energy", f"Mass is {2*n} kg and speed is 3 m s^-1. Calculate kinetic energy using E=mv^2/2.",
                  rf"E_k=\frac{{1}}{{2}}\times{2*n}\times3^2={9*n}\,\mathrm{{J}}", "Kinetic energy: E_k=mv^2/2"),
            _calc("phys", "wave_speed", f"Frequency is {n} Hz and wavelength is 2 m. Calculate speed using v=f lambda.",
                  rf"v={n}\times2={2*n}\,\mathrm{{m\,s^{{-1}}}}", "Wave speed: v=f lambda"),
            _calc("phys", "electrical_charge", f"A steady current of {n} A flows for 4 s. Calculate charge using Q=It.",
                  rf"Q={n}\times4={4*n}\,\mathrm{{C}}", "Charge for steady current: Q=It; A s=C"),
            _calc("phys", "pressure", f"A normal force of {5*n} N acts uniformly on {n} m^2. Calculate pressure using p=F/A.",
                  rf"p=\frac{{{5*n}}}{{{n}}}=5\,\mathrm{{Pa}}", "Uniform pressure: p=normal force/area"),
            _calc("phys", "potential_energy", f"A mass {n} kg rises 2 m in uniform g=10 m s^-2. Calculate increase in gravitational potential energy using delta E=mgh.",
                  rf"\Delta E_p={n}\times10\times2={20*n}\,\mathrm{{J}}", "Uniform gravitational field: delta E_p=m g delta h"),
            _calc("chem", "amount_from_mass", f"A pure substance has molar mass 20 g mol^-1. Calculate amount in {20*n} g using n=m/M.",
                  rf"n=\frac{{{20*n}}}{{20}}={n}\,\mathrm{{mol}}", "Amount of substance: n=m/M; mass and molar-mass units must agree"),
            _calc("chem", "concentration", f"There are {n} mol of solute in 2 dm^3 of solution. Calculate concentration using c=n/V.",
                  rf"c=\frac{{{n}}}{{2}}={n/2:g}\,\mathrm{{mol\,dm^{{-3}}}}", "Amount concentration: c=n/V in mol dm^-3 for V in dm^3"),
            _calc("chem", "gas_volume", f"At the specified conditions the molar gas volume is 24 dm^3 mol^-1. Calculate volume of {n} mol using V=n V_m.",
                  rf"V={n}\times24={24*n}\,\mathrm{{dm^3}}", "Gas volume at given conditions: V=n V_m; V_m supplied, not assumed universally"),
            _calc("chem", "volume_unit_conversion", f"Convert {1000*n} cm^3 into dm^3. Use 1 dm^3=1000 cm^3.",
                  rf"V=\frac{{{1000*n}}}{{1000}}={n}\,\mathrm{{dm^3}}", "SI decimal length cubed: (10 cm)^3=1 dm^3=1000 cm^3"),
            _calc("chem", "dilution", f"An aliquot of solution has concentration {n} mol dm^-3 and volume 2 dm^3. It is diluted to 4 dm^3, with solute amount unchanged. Calculate final concentration.",
                  rf"c_2=\frac{{c_1V_1}}{{V_2}}=\frac{{{n}\times2}}{{4}}={n/2:g}\,\mathrm{{mol\,dm^{{-3}}}}", "Dilution conserving amount of solute: c1 V1=c2 V2"),
            _calc("chem", "percentage_yield", f"The theoretical yield is {10*n} g and actual yield is {8*n} g. Calculate percentage yield.",
                  rf"\text{{yield}}=\frac{{{8*n}}}{{{10*n}}}\times100\%=80\%", "Percentage yield=actual yield/theoretical yield times 100 percent; same mass units"),
            _calc("math", "monomial_derivative", rf"Differentiate $y=x^{{{n}}}$ with respect to $x$.",
                  rf"\frac{{d}}{{dx}}x^{{{n}}}={n}x^{{{n-1}}}", "Power rule for positive integer exponent n: d(x^n)/dx=n x^(n-1)"),
            _calc("math", "monomial_integral", rf"Evaluate $\int_0^1 {n}x^{{{n-1}}}\,dx$ exactly using the power rule.",
                  rf"\int_0^1 {n}x^{{{n-1}}}\,dx=\left[x^{{{n}}}\right]_0^1=1", "Power antiderivative and fundamental theorem: integral_0^1 n x^(n-1) dx=1 for n>0"),
            _calc("math", "arithmetic_sequence", f"An arithmetic sequence has first term {n} and common difference 3. Find its fifth term.",
                  rf"a_5=a_1+4d={n}+4\times3={n+12}", "Arithmetic sequence: a_k=a1+(k-1)d"),
            _calc("math", "linear_equation", rf"Solve $3x+{n}= {n+12}$ exactly and show substitution.",
                  rf"3x={n+12}-{n}=12,\qquad x=4", "Equal operations on both sides: 3x+n=n+12 implies x=4"),
            _calc("math", "binomial_expansion", rf"Expand $(x+{n})^2$ fully.",
                  rf"(x+{n})^2=x^2+{2*n}x+{n*n}", "Distributive law: (x+a)^2=x^2+2ax+a^2"),
            _calc("math", "fraction_addition", rf"Calculate $\frac{{1}}{{{n}}}+\frac{{1}}{{{2*n}}}$ as an exact reduced fraction.",
                  rf"\frac{{1}}{{{n}}}+\frac{{1}}{{{2*n}}}=\frac{{{Fraction(3,2*n).numerator}}}{{{Fraction(3,2*n).denominator}}}", "Common denominator: 1/n+1/(2n)=3/(2n), n nonzero; reduced by integer gcd"),
        ])
    curated = [
        ("chem", "catalyst_criteria", ["Provides a reaction pathway with lower activation energy.", "Does not change the reaction enthalpy change."],
         [("It provides a lower activation energy pathway and leaves the reaction enthalpy change unchanged.", [True, True]),
          ("It provides a lower activation energy pathway.", [True, False]),
          ("It raises activation energy and changes the reaction enthalpy change.", [False, False]),
          ("It speeds up a reaction.", [False, False])]),
        ("phys", "vector_criteria", ["A vector has magnitude.", "A vector has direction."],
         [("A vector has magnitude and direction.", [True, True]), ("It has magnitude.", [True, False]),
          ("It has direction.", [False, True]), ("It has neither magnitude nor direction.", [False, False])]),
        ("math", "quadratic_root_criteria", ["x=2 is a root of x^2-4=0.", "x=-2 is a root of x^2-4=0."],
         [("The roots are 2 and -2.", [True, True]), ("x=2.", [True, False]),
          ("x=-2.", [False, True]), ("The only root is 4.", [False, False])]),
    ]
    curated.extend([
        ("chem", "isotope_criteria", ["Isotopes have the same number of protons.", "Isotopes have different numbers of neutrons."],
         [("They have the same proton number but different neutron numbers.", [True, True]),
          ("They have the same proton number.", [True, False]),
          ("They have different neutron numbers.", [False, True]),
          ("They have different proton numbers and the same neutron number.", [False, False])]),
        ("chem", "dynamic_equilibrium_criteria", ["The forward and reverse reaction rates are equal at dynamic equilibrium.", "Reactant and product concentrations remain constant at dynamic equilibrium."],
         [("Forward and reverse rates are equal and concentrations remain constant.", [True, True]),
          ("Forward and reverse rates are equal.", [True, False]),
          ("The concentrations remain constant.", [False, True]),
          ("Both reactions stop and concentrations keep changing.", [False, False])]),
        ("phys", "work_criteria", ["For constant force parallel to displacement, work equals force times displacement.", "The SI unit of work is the joule."],
         [("Work is force times displacement for parallel constant force, measured in joules.", [True, True]),
          ("Work is force times displacement for parallel constant force.", [True, False]),
          ("Work is measured in joules.", [False, True]),
          ("Work is force divided by displacement, measured in watts.", [False, False])]),
        ("phys", "momentum_criteria", ["Linear momentum is mass times velocity.", "Linear momentum is a vector quantity."],
         [("Momentum is mass times velocity and is a vector.", [True, True]),
          ("Momentum is mass times velocity.", [True, False]),
          ("Momentum is a vector.", [False, True]),
          ("Momentum is mass divided by velocity and is scalar.", [False, False])]),
        ("math", "square_domain_criteria", ["For real x, x squared is nonnegative.", "For real x, x squared is zero exactly when x is zero."],
         [("The square is nonnegative, with zero only when x is zero.", [True, True]),
          ("The square is nonnegative.", [True, False]),
          ("The square is zero if and only if x is zero.", [False, True]),
          ("Every real square is negative and zero occurs at x=1.", [False, False])]),
        ("math", "triangle_angles_criteria", ["The interior angles of a Euclidean triangle sum to 180 degrees.", "An equilateral Euclidean triangle has three equal interior angles."],
         [("The angle sum is 180 degrees; an equilateral triangle has equal angles.", [True, True]),
          ("The angle sum is 180 degrees.", [True, False]),
          ("An equilateral triangle has three equal interior angles.", [False, True]),
          ("The angle sum is 360 degrees and equilateral triangles have unequal angles.", [False, False])]),
    ])
    for subject, family, criteria, responses in curated:
        reference = _json({"curated_truth_table": family, "criteria": criteria, "responses": responses})
        for response, labels in responses:
            expected = {"points": [{"point": point, "met": met,
                                    "why": "Explicitly stated correctly." if met else "Missing or contradicted in the response."}
                                   for point, met in zip(criteria, labels)],
                        "feedback": "Credit only criteria explicitly and correctly supported by this response."}
            rows.append(_row("synthetic:" + family, subject, "marking",
                             'Return only JSON {"points":[{"point":"exact criterion","met":true,"why":"brief reason"}],'
                             '"feedback":"brief feedback"}. Preserve criterion order; an omitted or contradicted criterion is false. '
                             'Assess only these two supplied criteria, without adding an exam question.\n'
                             + _json({"criteria": criteria, "response": response}), expected,
                             [{"kind": "verified_synthetic", "reference": reference, "version": 1, "sha256": _sha(reference)}],
                             truth="curated_labels", labels=labels))
    snippets = [
        ("literal_python_square", 'def square(x):\n    return x * x\nrecord = {"reply": "x_1^2"}'),
        ("literal_json", '{\n  "quantity": "charge",\n  "unit": "C",\n  "latex": "x_1^2"\n}'),
        ("literal_csv", 'quantity,value,unit\n"force",6,"N"\n"charge",8,"C"'),
        ("literal_python_quote", 'label = "She said \\"hello\\""\npath = r"C:\\data\\stem"\nprint(label, path)'),
    ]
    for family, source in snippets:
        for subject in ("chem", "phys", "math"):
            rows.append(_synthetic(subject, family, "Copy this requested literal source exactly into a code block, preserving quotes and line breaks:\n" + source,
                                   [{"kind": "code", "text": source}], "Exact supplied literal source; no code execution or scientific claim", source_fidelity=True))
    for subject, question, hint in [
        ("chem", "Find the concentration after diluting an aliquot.", "Which quantity of solute remains unchanged during dilution?"),
        ("phys", "Find the resultant force from mass and acceleration.", "Which relationship connects resultant force, mass and acceleration?"),
        ("math", "Differentiate a positive integer power of x.", "How does the power rule change the coefficient and exponent?"),
    ]:
        rows.append(_synthetic(subject, "open_hint_" + subject,
                               "An OPEN practice question is active: " + question + " Give exactly one guiding question; do not solve it or state its final answer.",
                               [{"kind": "paragraph", "text": hint}], "OPEN policy: one conceptual guiding question without final answer", open_answer_protected=True))
    return rows


def _speech_variants(rows):
    """Plain prose can be read verbatim without guessing a maths pronunciation."""
    variants = []
    for row in rows:
        blocks = row["expected"].get("blocks", [])
        if row["task"] != "published_flashcard" or not blocks or any(b["kind"] != "paragraph" for b in blocks):
            continue
        spoken = " ".join(b["text"] for b in blocks)
        if len(spoken) > 600 or re.search(r"[^A-Za-z ,.;:?!'()\n-]", spoken):
            continue
        expected = {"blocks": blocks, "speech": spoken}
        question = row["messages"][0]["content"] + "\nInclude a separate required speech string reading this plain prose verbatim. Speech is not an extra visual block."
        variants.append(_row(row["group"], row["subject"], row["task"], question, expected,
                             row["provenance"], **{k: v for k, v in row["checks"].items() if k not in {"validated", "schema"}}))
    return variants


def _direct_recall_rows():
    """Small hand-checked registry; primary sources verified 2026-10-26.

    Claim hashes identify our paraphrase/identity, not unarchived web-page bytes.
    Related groups reserve known public/synthetic versions of the same concept.
    """
    caie = "https://www.cambridgeinternational.org/Images/664565-2025-2027-syllabus.pdf"
    pearson = ("https://qualifications.pearson.com/content/dam/pdf/International%20Advanced%20Level/"
               "Mathematics/2018/Specification-and-Sample-Assessment/IAL-Mathematics-Formula-Book.pdf")
    gold = "https://goldbook.iupac.org/terms/view/"
    # subject, fact id, family, two source-free prompts, gold blocks, source,
    # primary-source location and explicitly linked content/algorithm groups.
    facts = [
        ("chem", "chem_atomic_number", "atomic_nucleus", ["Define atomic number.", "What does the proton number of an atom count?"],
         [{"kind": "paragraph", "text": "The atomic number counts the protons in an atomic nucleus."}],
         "https://www.nrc.gov/education-regulatory-research/glossary/atomic-number", "NRC glossary: Atomic number", ["public:9701-1.1"]),
        ("chem", "chem_mass_number", "atomic_nucleus", ["Define mass number.", "What does an atom's nucleon number count?"],
         [{"kind": "paragraph", "text": "The mass number is the combined count of protons and neutrons in the nucleus."}],
         gold + "M03726", "IUPAC Gold Book 5.0.0: mass number", ["public:9701-1.1"]),
        ("chem", "chem_isotopes", "isotopes", ["Define isotopes using atomic and mass numbers.", "How do atomic number and mass number distinguish isotopes of an element?"],
         [{"kind": "paragraph", "text": "Isotopes share an atomic number but have different mass numbers."}],
         gold + "I03331/pdf", "IUPAC Gold Book: isotopes", ["public:9701-1.2", "synthetic:isotope_criteria"]),
        ("chem", "chem_oxidation", "oxidation", ["Define oxidation in electron-transfer terms.", "What happens to electrons during oxidation?"],
         [{"kind": "paragraph", "text": "Oxidation involves a net loss of electrons from the species being oxidised."}],
         gold + "O04362", "IUPAC Gold Book 5.0.0: oxidation, definition 1", ["public:9701-6.1"]),
        ("chem", "chem_amount_concentration", "amount_concentration", ["Define amount concentration.", "How is amount-of-substance concentration defined for a constituent of a mixture?"],
         [{"kind": "paragraph", "text": "Amount concentration is the amount of a constituent per unit volume of the mixture."},
          {"kind": "equation", "text": "c=n/V"}],
         gold + "A00295", "IUPAC Gold Book 5.0.0: amount concentration", ["public:9701-2.4", "synthetic:concentration", "synthetic:dilution"]),
        ("chem", "chem_molar_mass", "molar_mass", ["Define molar mass.", "Which ratio defines the molar mass of a substance?"],
         [{"kind": "paragraph", "text": "Molar mass expresses the mass per unit amount of substance."},
          {"kind": "equation", "text": "M=m/n"}],
         gold + "12214/plain", "IUPAC Gold Book 5.0.0: molar mass", ["public:9701-2.1", "synthetic:amount_from_mass"]),
        ("phys", "phys_momentum", "dynamics", ["Define linear momentum.", "How is the linear momentum of an object related to its mass and velocity?"],
         [{"kind": "paragraph", "text": "Linear momentum is the product of an object's mass and its velocity."},
          {"kind": "equation", "text": "p=mv"}],
         caie, "CAIE9702 2025-27 v1: 3.1.3, printed page17", ["public:9702-3.1", "synthetic:momentum_criteria"]),
        ("phys", "phys_force", "dynamics", ["Define resultant force in momentum terms.", "How is resultant force related to a body's rate of change of momentum?"],
         [{"kind": "paragraph", "text": "The resultant force is the rate at which momentum changes with time."},
          {"kind": "equation", "text": r"F=\frac{dp}{dt}"}],
         caie, "CAIE9702 2025-27 v1: 3.1.4, printed page17", ["public:9702-3.1", "synthetic:force_calculation"]),
        ("phys", "phys_power", "power", ["Define power in terms of work.", "What rate does mechanical power measure?"],
         [{"kind": "paragraph", "text": "Power measures the rate at which work is done."}],
         caie, "CAIE9702 2025-27 v1: 5.1.5, printed page19", ["public:9702-5.1"]),
        ("phys", "phys_potential_difference", "potential_difference", ["Define the potential difference across a component.", "What does potential difference across a component measure per unit charge?"],
         [{"kind": "paragraph", "text": "Potential difference across a component is the energy transferred per unit charge passing through it."},
          {"kind": "equation", "text": "V=W/Q"}],
         caie, "CAIE9702 2025-27 v1: 9.2.1-2, printed page23", ["public:9702-9.2"]),
        ("phys", "phys_gravitational_field", "gravitational_field", ["Define gravitational field strength.", "What gravitational force ratio defines field strength at a point?"],
         [{"kind": "paragraph", "text": "Gravitational field strength is the gravitational force per unit mass at the point."},
          {"kind": "equation", "text": "g=F/m"}],
         caie, "CAIE9702 2025-27 v1: 13.1.1, printed page26", ["public:9702-13.1"]),
        ("phys", "phys_electric_field", "electric_field", ["Define electric field strength.", "Which force-per-charge ratio defines electric field strength at a point?"],
         [{"kind": "paragraph", "text": "Electric field strength is the force per unit positive test charge at the point."},
          {"kind": "equation", "text": "E=F/q"}],
         caie, "CAIE9702 2025-27 v1: 18.1.1-2, printed page30", ["public:9702-18.1"]),
        ("math", "math_sphere_area", "mensuration", ["State the surface area formula for a sphere of radius r.", "What is the total surface area of a sphere in terms of its radius r?"],
         [{"kind": "equation", "text": r"A=4\pi r^2"}], pearson, "Pearson IAL formula book issue2 January2021: P1 Mensuration, printed page3", []),
        ("math", "math_cone_area", "mensuration", ["State the curved surface area of a cone with radius r and slant height l.", "Give the cone's curved area formula using base radius r and slant height l."],
         [{"kind": "equation", "text": r"A=\pi r\ell"}], pearson, "Pearson IAL formula book issue2 January2021: P1 Mensuration, printed page3", []),
        ("math", "math_cosine_rule", "cosine_rule", ["State the cosine rule for side a opposite angle A.", "Relate triangle sides a, b, c to angle A opposite side a using the cosine rule."],
         [{"kind": "equation", "text": r"a^2=b^2+c^2-2bc\cos A"}], pearson, "Pearson IAL formula book issue2 January2021: P1 Cosine rule, printed page3", ["public:P1-3"]),
        ("math", "math_arithmetic_term", "sequences", ["State the nth term of an arithmetic sequence with first term a and common difference d.", "Give u_n for an arithmetic progression starting at a with common difference d."],
         [{"kind": "equation", "text": "u_n=a+(n-1)d"}], pearson, "Pearson IAL formula book issue2 January2021: P2 Arithmetic series, printed page3", ["public:P2-4", "synthetic:arithmetic_sequence"]),
        ("math", "math_geometric_sum", "sequences", ["State the sum to infinity of a geometric series starting at a with ratio r, and its convergence condition.", "For a geometric series with first term a, give S_infinity and the required restriction on common ratio r."],
         [{"kind": "paragraph", "text": "The series converges when the magnitude of the common ratio is less than one."},
          {"kind": "equation", "text": r"S_\infty=\frac{a}{1-r},\qquad |r|<1"}], pearson, "Pearson IAL formula book issue2 January2021: P2 Geometric series, printed page3", ["public:P2-4"]),
        ("math", "math_log_change_base", "logarithms", ["State the change-of-base formula for logarithms and its real-domain conditions.", "Express log_a(x) using logarithms to base b, including restrictions on a, b and x."],
         [{"kind": "equation", "text": r"\log_a x=\frac{\log_b x}{\log_b a}"},
          {"kind": "paragraph", "text": "For real logarithms, require positive x, positive bases a and b, and neither base equal to one."}], pearson,
         "Pearson IAL formula book issue2 January2021: P2 Logarithms, printed page3; real-domain restrictions from logarithm definition", ["public:P2-5"]),
    ]
    rows = []
    for subject, fact_id, family, prompts, blocks, url, location, related in facts:
        claim = _json(blocks)
        provenance = [{"kind": "curated_primary_source", "fact_id": fact_id, "url": url,
                       "location": location, "verified_on": "2026-10-26", "claim": claim,
                       "claim_sha256": _sha(claim), "paraphrase": True}]
        for prompt in prompts:
            rows.append(_row("curated:" + subject + ":" + family, subject, "direct_recall",
                             FORMAT + prompt, {"blocks": blocks}, provenance,
                             source_free=True, truth="hand_checked_primary_source",
                             related_groups=related, fact_id=fact_id))
    return rows


def _group_duplicates(rows):
    # Whole subtopics keep every KC and visible solution together. Cross-subtopic
    # duplicate questions or answers union those groups before any split.
    parent = {r["group"]: r["group"] for r in rows}
    def find(key):
        while parent[key] != key:
            parent[key] = parent[parent[key]]
            key = parent[key]
        return key
    seen = {}
    for row in rows:
        if not row["group"].startswith("public:"):
            continue
        # Exact answer duplication and question duplication are independent guards.
        for signature in (_json(row["expected"]), row["checks"]["question_family_sha256"]):
            key = _sha(signature)
            if key in seen:
                left, right = find(row["group"]), find(seen[key])
                parent[max(left, right)] = min(left, right)
            seen[key] = row["group"]
    for row in rows:
        for related in row["checks"].get("related_groups", []):
            if related in parent:
                left, right = find(row["group"]), find(related)
                parent[max(left, right)] = min(left, right)
    for row in rows:
        row["group"] = find(row["group"])


def build_dataset(packs, output: Path, seed: int = SEED) -> dict:
    """Write only to explicit output and return its deterministic manifest.

    Input accepts a vault, published pack directory, CURRENT marker or Packs
    facade. Splitting precedes parameter/speech variation via indivisible groups.
    The public glob is deliberately narrower than the vault or .tutor tree.
    """
    root = _pack_root(packs)
    output = Path(output)
    if root == output.resolve() or root in output.resolve().parents:
        raise ValueError("Output must not modify the published pack tree")
    rejected, sources = [], []
    rows = _public_rows(root, rejected, sources) + _synthetic_rows() + _direct_recall_rows()
    _group_duplicates(rows)
    rows += _speech_variants(rows)
    unique, seen = [], set()
    for row in rows:
        if row["id"] in seen:
            rejected.append({"source_id": row["id"], "reason": "duplicate_example"})
        else:
            seen.add(row["id"])
            unique.append(row)
    corpus = {name: [] for name in ("train", "valid", "test")}
    # Tiny curated marking strata otherwise can all hash into training. Allocate
    # by group hash rank per subject, reserving one or 15% for each holdout;
    # this never splits a concept's positive/omission/contradiction variants.
    marking_splits = {}
    for subject in ("chem", "phys", "math"):
        groups = sorted({r["group"] for r in unique if r["task"] == "marking" and r["subject"] == subject},
                        key=lambda group: _sha(f"{seed}:{group}"))
        if len(groups) >= 3:
            holdout = max(1, round(len(groups) * .15))
            marking_splits.update({group: "valid" if i < holdout else "test" if i < 2*holdout else "train"
                                   for i, group in enumerate(groups)})
    recall_splits = {}
    for subject in ("chem", "phys", "math"):
        groups = sorted({r["group"] for r in unique if r["task"] == "direct_recall" and r["subject"] == subject},
                        key=lambda group: _sha(f"{seed}:{group}"))
        if len(groups) >= 3:
            holdout = max(1, round(len(groups) * .15))
            recall_splits.update({group: "valid" if i < holdout else "test" if i < 2*holdout else "train"
                                  for i, group in enumerate(groups)})
    for row in sorted(unique, key=lambda r: r["id"]):
        bucket = int(_sha(f"{seed}:{row['group']}")[:8], 16) % 100
        split = recall_splits.get(row["group"], marking_splits.get(row["group"], "train" if bucket < 70 else "valid" if bucket < 85 else "test"))
        corpus[split].append(row)
    manifest = {"format_version": 2, "seed": seed, "pack_version": root.name,
                "source_policy": "published cards/visible worked solutions as source tasks plus hand-checked primary-source direct recall; no learner state or model outputs",
                "split_policy": "SHA256(seed:group) mod100; train<70,valid<85,test otherwise; public whole subtopics unioned on duplicate gold/question; synthetic whole algorithm families; marking group hash rank per subject reserves max(1,round(groups*.15)) groups for each holdout; direct-recall groups similarly ranked within subject and take precedence, including explicitly joined related public/synthetic groups",
                "sources": sources, "files": {}, "splits": {}, "discard_reasons": dict(sorted(Counter(r["reason"] for r in rejected).items())),
                "rows": len(unique), "quarantined": len(rejected),
                "limitations": ["Published scientific facts are source-fidelity targets, not independently rederived gold.",
                                "Public grouping protects whole subtopics and exact duplicates; semantic paraphrases across subtopics may remain.",
                                "This small local corpus does not establish syllabus completeness or expert marking accuracy."]}
    output.mkdir(parents=True, exist_ok=True)
    for split, split_rows in corpus.items():
        content = "".join(_json(row) + "\n" for row in split_rows)
        groups = sorted({r["group"] for r in split_rows})
        manifest["files"][split + ".jsonl"] = {"sha256": _sha(content), "rows": len(split_rows), "groups": groups}
        manifest["splits"][split] = {"rows": len(split_rows), "subjects": dict(sorted(Counter(r["subject"] for r in split_rows).items())),
                                      "tasks": dict(sorted(Counter(r["task"] for r in split_rows).items())), "groups": groups}
        (output / (split + ".jsonl")).write_text(content, encoding="utf-8")
    quarantine = "".join(_json(record) + "\n" for record in rejected)
    (output / "quarantine.jsonl").write_text(quarantine, encoding="utf-8")
    manifest["files"]["quarantine.jsonl"] = {"sha256": _sha(quarantine), "rows": len(rejected)}
    (output / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return manifest


def _format_challenge_rows():
    """Original questions combining known facts with held-out presentation demands."""
    caie = "https://www.cambridgeinternational.org/Images/664565-2025-2027-syllabus.pdf"
    iupac = "https://goldbook.iupac.org/terms/view/O04362"
    references = {
        "chem": [iupac, "https://goldbook.iupac.org/terms/view/A00295", "https://goldbook.iupac.org/terms/view/M03726"],
        "phys": [caie],
        "math": ["https://qualifications.pearson.com/content/dam/pdf/International%20Advanced%20Level/Mathematics/2018/Specification-and-Sample-Assessment/IAL-Mathematics-Formula-Book.pdf"],
    }
    rows = []
    def add(subject, task, prompt, expected, claim, **checks):
        provenance = [{"kind": "hand_checked_format_challenge", "version": 1,
                       "primary_sources": references[subject], "claim": claim,
                       "claim_sha256": _sha(claim), "review": "hand_checked_before_model_testing"}]
        rows.append(_row("format-challenge-v1:" + subject + ":" + task, subject, task,
                         FORMAT + prompt, expected, provenance,
                         format_combination_challenge=True, underlying_fact_overlap_allowed=True,
                         **checks))
    literals = {
        "chem": '{\n  "sample": "NH4+",\n  "yield": "82.5%",\n  "cost": "£4.20",\n  "note": "Keep \\"aqueous\\" quoted"\n}',
        "phys": 'reading = {"efficiency": "75%", "cost": "£2.40"}\nlabel = "She said \\"steady\\""\nprint(reading, label)',
        "math": 'const record = {"growth": "12%", "price": "$3.50"};\nconst label = "x_2^3 stays literal";\nconsole.log(record, label);',
    }
    for subject, source in literals.items():
        add(subject, "format_literal_source", "Copy the following literal source exactly as code. Preserve every quote, currency symbol, percent sign and actual line break.\n" + source,
            {"blocks": [{"kind": "code", "text": source}]},
            "Literal source fidelity only; no execution or scientific claim. Currency/percent symbols are literal strings.",
            source_fidelity=True, code_requires_exact_fidelity=True, alternate_code_semantics="manual_review_separate_from_exact_copy")
    add("chem", "format_speech", "A solution contains 0.15 mol of solute in 0.50 dm^3. Calculate its amount concentration and give a separate spoken version of the result.",
        {"blocks": [{"kind": "equation", "text": r"c=\frac{0.15}{0.50}=0.30\,\mathrm{mol\,dm^{-3}}"}],
         "speech": "The amount concentration is zero point three zero moles per cubic decimetre."},
        "Amount concentration n/V: 0.15/0.50=0.30 mol dm^-3, two significant figures. IUPAC A00295.", speech_separate=True)
    add("phys", "format_speech", "A constant force of 4.0 N acts along a displacement of 0.75 m. Calculate the work done and give a separate spoken version of the answer.",
        {"blocks": [{"kind": "equation", "text": r"W=Fs=4.0\times0.75=3.0\,\mathrm{J}"}],
         "speech": "The work done is three point zero joules."},
        "Work=constant force times displacement along force: 4.0*0.75=3.0 J, two significant figures. CAIE9702 5.1.1.", speech_separate=True)
    add("math", "format_speech", "Differentiate y=3x^2, then provide a separate spoken version of the derivative.",
        {"blocks": [{"kind": "equation", "text": r"\frac{dy}{dx}=6x"}], "speech": "The derivative is six x."},
        "Power rule and constant multiple: d(3x^2)/dx=6x; exact polynomial identity.", speech_separate=True)
    opens = [
        ("chem", "An OPEN exercise asks for the empirical formula from measured carbon and hydrogen masses. Give one initial guiding question without calculating or naming the final formula.",
         "How can you convert each elemental mass into an amount in moles?", "Empirical-formula method starts by comparing mole amounts; no mass values or final formula revealed."),
        ("phys", "An OPEN exercise asks for distance travelled from a speed-time graph. Ask one guiding question without stating the graphical operation or final distance.",
         "What units would you obtain by combining a time interval with the corresponding speed?", "Speed times time has units of distance; guiding question does not state graph area or final result."),
        ("math", "An OPEN exercise is to solve x^2+8x+7=0 by completing the square. Give one guiding question without giving the completed square or either root.",
         "How does the coefficient of the linear term help you choose the term inside the squared bracket?", "Completing the square uses half the linear coefficient; hint does not state that value, completed square or roots."),
    ]
    for subject, prompt, hint, claim in opens:
        add(subject, "format_open_hint", prompt, {"blocks": [{"kind": "paragraph", "text": hint}]}, claim,
            open_answer_protected=True, open_protection_review="manual")
    marking = [
        ("chem", ["Oxidation involves net loss of electrons.", "Oxidation increases oxidation number."],
         "The species gains electrons and its oxidation number decreases.", [False, False],
         "Both claims explicitly contradict oxidation definitions1/2 in IUPAC O04362."),
        ("phys", ["Kinetic energy equals one half of mass multiplied by speed squared.", "At constant mass, doubling speed quadruples kinetic energy."],
         "Kinetic energy is one half of the mass times the square of the speed.", [True, False],
         "First criterion explicitly stated; second omitted. Scaling follows E_k=mv^2/2, CAIE9702 5.2.4; no inferential credit for unstated requested conclusion."),
        ("math", ["The derivative of 3x^2 is 6x.", "The derivative of the constant 7 is zero."],
         "The derivative of 3x^2 is 6x. The derivative of 7 is 7.", [True, False],
         "Power rule gives6x; constant derivative is0. First response correct, second explicitly false."),
    ]
    for subject, criteria, response, labels, claim in marking:
        expected = {"points": [{"point": point, "met": met,
                                "why": "Explicitly stated correctly." if met else "Omitted or contradicted by the response."}
                               for point, met in zip(criteria, labels)],
                    "feedback": "Award only the criteria explicitly and correctly expressed."}
        prompt = ('Assess each criterion independently; an omitted or contradicted requested statement earns no credit. '
                  'Return only JSON {"points":[{"point":"exact criterion","met":true,"why":"brief reason"}],'
                  '"feedback":"brief feedback"}; preserve criterion order.\n'
                  + _json({"criteria": criteria, "response": response}))
        add(subject, "format_marking", prompt, expected, claim, labels=labels, marking_review="curated_truth_labels")
    add("chem", "format_topic_change", "We have finished discussing force-time graphs. Change to chemistry and answer both parts: (a) define oxidation in electron-transfer terms; (b) explain what mass number counts.",
        {"blocks": [{"kind": "heading", "text": "Chemistry"},
                    {"kind": "bullet", "text": "Oxidation is a net loss of electrons from a species."},
                    {"kind": "bullet", "text": "Mass number counts the protons and neutrons in the nucleus."}]},
        "Both requested chemistry parts covered; electron loss from IUPAC O04362 and nucleon count from M03726.", requested_parts=2, topic_change=True)
    add("phys", "format_topic_change", "Stop discussing logarithm laws. Now give both definitions: (a) potential difference across a component; (b) mechanical power.",
        {"blocks": [{"kind": "heading", "text": "Potential difference and power"},
                    {"kind": "bullet", "text": "Potential difference is the energy transferred per unit charge passing through a component."},
                    {"kind": "bullet", "text": "Mechanical power is the rate at which work is done."}]},
        "Both requested definitions covered; CAIE9702 9.2.1 and5.1.5; no continuation of previous logarithm topic.", requested_parts=2, topic_change=True)
    add("math", "format_topic_change", "We have finished the chemistry dilution question. Change to geometry: (a) state the cosine rule for side a opposite angle A; (b) state the surface area of a sphere with radius r.",
        {"blocks": [{"kind": "heading", "text": "Geometry"},
                    {"kind": "equation", "text": r"a^2=b^2+c^2-2bc\cos A"},
                    {"kind": "equation", "text": r"S=4\pi r^2"}]},
        "Cosine rule and sphere area are independent required parts; Pearson IAL formula book issue2 page3.", requested_parts=2, topic_change=True)
    add("chem", "format_equation_units", "A neutral magnesium atom becomes an Mg2+ ion. Write the balanced oxidation half-equation, showing the electrons on the correct side.",
        {"blocks": [{"kind": "equation", "text": r"\mathrm{Mg}\rightarrow\mathrm{Mg}^{2+}+2e^-"}]},
        "Atom and charge balance:0=+2-2. Magnesium neutral to supplied2+ ion requires loss of two electrons; electron loss is oxidation, IUPAC O04362.", charge_balance="0=2-2")
    add("phys", "format_equation_units", "A normal force of 18 N is spread uniformly across 0.060 m^2. Using p=F/A, calculate the pressure with its SI unit.",
        {"blocks": [{"kind": "equation", "text": r"p=\frac{18}{0.060}=3.0\times10^2\,\mathrm{Pa}"}]},
        "18/0.060=300 N m^-2=300 Pa, two significant figures; supplied pressure equation, CAIE9702 4.3.", exact_value=300, unit="Pa")
    add("math", "format_equation_units", "Add 5/12 and 7/18 exactly, showing a common denominator and a reduced final fraction.",
        {"blocks": [{"kind": "equation", "text": r"\frac{5}{12}+\frac{7}{18}=\frac{15}{36}+\frac{14}{36}=\frac{29}{36}"}]},
        "LCM(12,18)=36;15+14=29;gcd(29,36)=1, exact rational arithmetic.", exact_fraction="29/36")
    return rows


def build_format_challenge(training: Path, output: Path, seed: int = 42) -> dict:
    """Freeze a separate format-combination challenge; never mutate training data."""
    from .stem_training_eval import freeze_selection
    training, output = Path(training).resolve(), Path(output)
    if output.resolve() == training or training in output.resolve().parents:
        raise ValueError("Challenge output must be separate from frozen training data")
    if output.exists() and any(output.iterdir()):
        raise FileExistsError("Challenge output is already frozen")
    manifest_path = training / "manifest.json"
    source_manifest = json.loads(manifest_path.read_text())
    train_blob = (training / "train.jsonl").read_bytes()
    if _sha(train_blob) != source_manifest["files"]["train.jsonl"]["sha256"]:
        raise ValueError("Training hash differs from manifest")
    train_rows = [json.loads(line) for line in train_blob.splitlines() if line.strip()]
    train_prompts = {" ".join(r["messages"][0]["content"].casefold().split()) for r in train_rows}
    train_gold = {_json(r["expected"]) for r in train_rows}
    train_blocks = {_json(block) for r in train_rows for block in r["expected"].get("blocks", [])}
    rows = sorted(_format_challenge_rows(), key=lambda row: row["id"])
    for row in rows:
        row["checks"]["novel_question"] = " ".join(row["messages"][0]["content"].casefold().split()) not in train_prompts
        row["checks"]["exact_training_gold_overlap"] = _json(row["expected"]) in train_gold
        row["checks"]["exact_training_block_overlap_count"] = sum(_json(b) in train_blocks for b in row["expected"].get("blocks", []))
        if not row["checks"]["novel_question"] or row["checks"]["exact_training_gold_overlap"]:
            raise ValueError("Challenge duplicates a training prompt or full gold answer")
    content = "".join(_json(row) + "\n" for row in rows)
    groups = sorted({r["group"] for r in rows})
    manifest = {"format_version": 1, "corpus_kind": "format_combination_challenge", "seed": seed,
                "rows": len(rows), "ids": [r["id"] for r in rows],
                "training_audit": {"dataset": str(training), "manifest_sha256": _sha(manifest_path.read_bytes()),
                                   "train_sha256": _sha(train_blob), "rows": len(train_rows),
                                   "exact_prompt_duplicates": 0, "exact_full_gold_duplicates": 0,
                                   "rows_with_exact_block_overlap": sum(r["checks"]["exact_training_block_overlap_count"] > 0 for r in rows)},
                "files": {"test.jsonl": {"sha256": _sha(content), "rows": len(rows), "groups": groups}},
                "splits": {"test": {"rows": len(rows), "groups": groups,
                                     "subjects": dict(sorted(Counter(r["subject"] for r in rows).items())),
                                     "tasks": dict(sorted(Counter(r["task"] for r in rows).items()))}},
                "limitations": ["Format-combination challenge, not proof of independent unseen scientific knowledge.",
                                "Underlying facts intentionally overlap; exact prompt/full-gold duplicates are excluded, semantic overlap is not claimed absent.",
                                "Code is scored for literal fidelity; alternate valid implementations require separate semantic review and are never executed.",
                                "Science, requested-part coverage, spoken correctness and OPEN answer protection require manual review."]}
    output.mkdir(parents=True, exist_ok=True)
    (output / "test.jsonl").write_text(content, encoding="utf-8")
    (output / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    freeze_selection(output, output / "selection.json", per_subject=6, seed=seed)
    return manifest


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--vault", required=True, type=Path, help="Vault, published pack root, or CURRENT marker")
    parser.add_argument("--output", required=True, type=Path, help="Explicit destination for dataset files")
    parser.add_argument("--seed", type=int, default=SEED)
    args = parser.parse_args()
    manifest = build_dataset(args.vault, args.output, seed=args.seed)
    print(json.dumps({"rows": manifest["rows"], "splits": manifest["splits"], "discard_reasons": manifest["discard_reasons"]}, indent=2))


if __name__ == "__main__":
    main()
