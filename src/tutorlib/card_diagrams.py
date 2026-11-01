"""Read positional and legacy path-keyed descriptions without changing source cards."""
from __future__ import annotations


def diagram_descriptions(card: dict) -> list:
    """Return descriptions in declared diagram order; missing map entries stay empty.

    Keys bind to exact declared references. Do not resolve aliases here: their
    provenance and hash checks belong to the asset library, not this adapter.
    """
    descriptions = card.get("diagram_descriptions")
    if isinstance(descriptions, list):
        return list(descriptions)
    if isinstance(descriptions, dict):
        diagrams = card.get("diagrams")
        return [descriptions.get(path, "") if isinstance(path, str) else ""
                for path in diagrams] if isinstance(diagrams, list) else []
    return []


def valid_diagram_descriptions(card: dict) -> bool:
    diagrams = card.get("diagrams")
    raw = card.get("diagram_descriptions")
    if not isinstance(diagrams, list) or not isinstance(raw, (list, dict)):
        return False
    if isinstance(raw, dict) and (any(not isinstance(p, str) for p in diagrams)
                                  or set(raw) != set(diagrams)):
        return False
    descriptions = diagram_descriptions(card)
    return len(descriptions) == len(diagrams) and all(
        isinstance(text, str) and text.strip() for text in descriptions)
