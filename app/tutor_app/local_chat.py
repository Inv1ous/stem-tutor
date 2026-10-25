"""Conversational instructions for local streams; other providers keep their brief."""
from __future__ import annotations

from .ai import VISUAL_BRIEF


def chat_system(system: str, *, speech: bool = False) -> str:
    """Scope lesson grounding and describe the local chat transport on a fresh copy."""
    system = system.replace(
        "Ground everything in the CONTEXT you are given;",
        "CONTEXT describes current or recent study background, not an exclusive knowledge source. "
        "Answer the student's current question directly using general A-Level knowledge, including a different topic. "
        "Use the supplied question and lesson details when relevant;",
    ).replace(
        VISUAL_BRIEF.split("\n", 1)[0],
        "Visual writing (conversational Markdown inside the reply string):",
    )
    transport = (
        "Local chat response:\n"
        "- Answer the current request in its requested form, while respecting OPEN-question restrictions. "
        "When asked for a list, list actual named items or formulae rather than general study advice. "
        "Interpret terms in the named subject. Unrelated recent lesson topics must not redirect the answer.\n"
        "- Return the requested outer JSON object. Put the complete student-facing answer in the reply string "
        "as Markdown; do not add another reply wrapper or split the answer into extra fields.\n"
        "- If the student requests literal JSON or code, keep that content inside the reply string.\n"
    )
    if speech:
        transport += (
            "- Put the same answer rewritten as plain spoken English in the speech field only: "
            "no symbols, LaTeX, Markdown or lists. Say numbers, units and formulae in words. "
            "Do not append a spoken copy or a speech marker to reply."
        )
    else:
        transport += "- Do not add a speech field, spoken copy or speech marker."
    return f"{system}\n\n{transport}"
