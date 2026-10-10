"""Which syllabus points a diagram can illustrate: the words that say a point is a graph, a circuit, a force picture...

A chapter whose points match must request at least one diagram (or say why not): drafters used to leave them out.
Light on purpose (no matplotlib): the foundry's gates import it.
"""
from __future__ import annotations

import re

# diagram type (see build/diagrams.py) -> words in a syllabus point's title or statement that call for it
HINTS: dict[str, tuple[str, ...]] = {
    "graph_sketch": ("graph", "sketch", "gradient", "area under", "displacement–time", "velocity–time", "against time"),
    "function_plot": ("curve", "asymptote", "plot", "transformation of graphs", "graphs of functions"),
    "circuit": ("circuit", "potential divider", "resistors in", "ammeter", "voltmeter", "internal resistance"),
    "free_body": ("free-body", "free body", "resultant force", "equilibrium", "inclined plane", "resolv", "tension"),
    "energy_profile": ("energy profile", "reaction pathway", "activation energy", "energy level diagram"),
    "maxwell_boltzmann": ("boltzmann", "distribution of molecular", "distribution of energies"),
    "wave": ("wavelength", "amplitude", "transverse", "progressive wave", "stationary wave", "polaris"),
    "box_plot": ("box plot", "box-and-whisker", "quartile", "outlier"),
    "density_panels": ("normal distribution", "skew", "probability density"),
}


def suggest(kcs: list[dict]) -> dict[str, list[str]]:
    """{diagram type: [kc ids whose title or statement calls for it]} for one chapter's points."""
    out: dict[str, list[str]] = {}
    for k in kcs:
        text = f"{k.get('title', '')} {k.get('statement', '')}".lower()
        for kind, words in HINTS.items():
            if any(re.search(r"\b" + re.escape(w) if w[-1].isalpha() and " " not in w else re.escape(w), text) for w in words):
                out.setdefault(kind, []).append(k["id"])
    return out
