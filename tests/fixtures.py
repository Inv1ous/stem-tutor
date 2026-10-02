"""A tiny but realistic vault + pack set used across tests."""
import json
from pathlib import Path

GRAPH = {
    "spec": "9702", "subject": "phys", "title": "CAIE AS & A Level Physics", "version": "2025-2027",
    "topics": [{"id": "9702-2", "title": "Kinematics", "level": "AS"}],
    "subtopics": [{"id": "9702-2.1", "title": "Equations of motion", "topic": "9702-2"}],
    "kcs": [
        {"id": "9702-2.1.1", "subtopic": "9702-2.1", "title": "Distance, displacement, speed, velocity",
         "statement": "define and use distance, displacement, speed, velocity and acceleration",
         "level": "AS", "type": "conceptual", "prereqs": [], "glossary": ["displacement", "velocity", "speed", "vector"]},
        {"id": "9702-2.1.4", "subtopic": "9702-2.1", "title": "suvat",
         "statement": "derive and use the equations of uniformly accelerated motion in a straight line",
         "level": "AS", "type": "procedural", "prereqs": ["9702-2.1.1"], "glossary": ["suvat", "uniform acceleration", "v = u + at"]},
    ],
}

PACK = {
    "subtopic": "9702-2.1", "spec": "9702",
    "note": "Subjects/9702 Physics/02 Kinematics/2.1 Equations of motion.md",
    "outline": "Uniform acceleration: $v=u+at$, $s=ut+\\tfrac12at^2$, $v^2=u^2+2as$.",
    "misconceptions": [
        {"id": "m1", "kc": "9702-2.1.1", "statement": "Distance and displacement are the same thing",
         "refutation": "Displacement is a vector: straight-line change in position with direction.",
         "contrast": "Run one lap of a 400 m track: distance 400 m, displacement 0."},
        {"id": "m2", "kc": "9702-2.1.4", "statement": "Using s = vt when the velocity changes",
         "refutation": "s = vt only holds at constant velocity.", "contrast": "..."},
    ],
    "worked": [
        {"id": "we1", "kc": "9702-2.1.4", "problem": "A car accelerates from $4.0\\,\\mathrm{m\\,s^{-1}}$ at $2.5\\,\\mathrm{m\\,s^{-2}}$ for $6.0$ s. Find the distance.",
         "steps": [{"do": "List s,u,v,a,t", "why": "Choose the equation without v"},
                   {"do": "$s = ut + \\tfrac12 a t^2$", "why": "u, a, t known"},
                   {"do": "$s = 4.0(6.0) + 0.5(2.5)(6.0)^2 = 69$ m", "why": "substitute",
                    "check": {"kind": "numeric", "answer": {"value": 69.0, "unit": "m", "sf_ok": [2, 3]}}}],
         "faded": {"id": "we1f", "problem": "From rest at $3.0\\,\\mathrm{m\\,s^{-2}}$ for $5.0$ s. Find the distance.",
                   "answer": {"value": 37.5, "unit": "m", "sf_ok": [2, 3]}, "blank_from": 1}},
    ],
    "items": [
        {"id": "9702-2.1-i01", "kcs": ["9702-2.1.1"], "kind": "mcq", "difficulty": 2, "command_word": "State",
         "source": {"type": "generated"}, "stem": "Which quantity is a vector?",
         "options": {"A": "distance", "B": "displacement", "C": "speed", "D": "time"}, "answer": "B",
         "distractors": {"A": "m1"}, "marks": 1, "shuffle": True,
         "explanation": "Displacement has direction.", "hints": ["Which has a direction?", "Vectors have magnitude and direction.", "Compare distance and displacement."]},
        {"id": "9702-2.1-i02", "kcs": ["9702-2.1.4"], "kind": "numeric", "difficulty": 3, "command_word": "Calculate",
         "source": {"type": "generated"},
         "stem": "A ball is released from rest and falls for [[t:.1f]] s. Calculate the distance fallen. ($g = 9.81\\,\\mathrm{m\\,s^{-2}}$)",
         "template": {"params": {"t": {"min": 1.0, "max": 3.0, "step": 0.5}}, "answer": "0.5*9.81*t**2",
                      "distractors": [{"expr": "9.81*t", "misconception": "m2"}],
                      "constraints": ["abs(t - 2) > 0.1"]},
         "answer": {"unit": "m", "sf_ok": [2, 3]}, "marks": 2, "explanation": "$s = \\tfrac12 g t^2$"},
        {"id": "9702-2.1-i03", "kcs": ["9702-2.1.4"], "kind": "numeric", "difficulty": 4, "command_word": "Calculate",
         "source": {"type": "past", "ref": "CAIE 9702 · Jun 2023 · P22 · Q2(a)"},
         "stem": "A car decelerates uniformly from 20 m/s to rest in 50 m. Calculate the deceleration.",
         "answer": {"value": 4.0, "unit": "m s-2", "sf_ok": [2, 3]}, "marks": 2},
        {"id": "9702-2.1-i04", "kcs": ["9702-2.1.1"], "kind": "mcq", "difficulty": 4, "command_word": "Deduce",
         "source": {"type": "generated"}, "stem": "A runner completes one lap of a 400 m track in 80 s. What is the average velocity?",
         "options": {"A": "5.0 m/s", "B": "0 m/s", "C": "2.5 m/s", "D": "10 m/s"}, "answer": "B",
         "distractors": {"A": "m1"}, "marks": 1},
        {"id": "9702-2.1-i05", "kcs": ["9702-2.1.4"], "kind": "structured", "difficulty": 4, "command_word": "Calculate",
         "source": {"type": "generated"}, "marks": 3,
         "stem": "A stone is thrown vertically up at $12\\,\\mathrm{m\\,s^{-1}}$. Calculate the maximum height.",
         "scheme": [{"mark": "M1", "point": "uses v^2 = u^2 + 2as with v = 0"},
                    {"mark": "A1", "point": "s = 7.3 m", "check": {"kind": "numeric", "answer": {"value": 7.34, "unit": "m", "sf_ok": [2, 3]}}},
                    {"mark": "B1", "point": "states direction/upward"}]},
    ],
    "flashcards": [{"id": "fc1", "kc": "9702-2.1.1", "front": "Define displacement.", "back": "Distance in a stated direction ($\\vec s$)."}],
}

PAPERS = {"papers": [{"id": "9702_s23_qp_22", "code": "9702", "component": "22", "series": "s23", "marks": 60,
                       "qp": "Papers/9702/9702_s23_qp_22.pdf", "ms": "Papers/9702/9702_s23_ms_22.pdf",
                       "questions": [{"q": "1a", "marks": 2, "kcs": ["9702-2.1.1"]}, {"q": "1b", "marks": 3, "kcs": ["9702-2.1.4"]}]}]}

PLAN = {
    "start": "2026-09-01", "week2_monday": "2026-09-07",
    "weeks": {"5": [{"id": "5-phys1", "subject": "phys", "title": "Kinematics", "kcs": ["9702-2.1.1", "9702-2.1.4"], "type": "NEW", "priority": "A"}]},
    "sittings": {"9702-AS": "2027-05-10"},
}


def make_vault(tmp_path) -> Path:
    root = tmp_path / "mnt" / "STEM Tutor"
    t = root / ".tutor"
    (t / "packs" / "v1" / "specs" / "9702" / "packs").mkdir(parents=True)
    (t / "config.json").write_text(json.dumps({"tz": "Asia/Hong_Kong"}))
    (t / "packs" / "CURRENT").write_text("v1")
    (t / "packs" / "v1" / "manifest.json").write_text(json.dumps({"version": "v1", "specs": ["9702"]}))
    (t / "packs" / "v1" / "specs" / "9702" / "graph.json").write_text(json.dumps(GRAPH))
    (t / "packs" / "v1" / "specs" / "9702" / "packs" / "9702-2.1.json").write_text(json.dumps(PACK))
    (t / "packs" / "v1" / "plan.json").write_text(json.dumps(PLAN))
    (t / "packs" / "v1" / "papers.json").write_text(json.dumps(PAPERS))
    return root
