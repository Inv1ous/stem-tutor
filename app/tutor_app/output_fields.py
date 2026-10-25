"""Normalise audited visual prose fields; grading, speech and private work stay literal."""
from __future__ import annotations

from tutorlib import challenge_gen

from . import prompts
from .output_format import normalise_visual


# Each array path names one explicitly audited prose field in its rows. This is not
# a recursive JSON-string formatter: additions require a schema and field audit.
_VISUAL_FIELDS = (
    (prompts.JUDGE, (("feedback",), ("points", "why"))),
    (prompts.REMARK, (("why",),)),
    (prompts.CARD, tuple((name,) for name in ("motivate", "establish", "connect", "note", "self_explain"))),
    (prompts.PROFILE, (("summary",),)),
    (challenge_gen.GENERATE_SCHEMA, (("stem",), ("solution",), ("wrong", "mistake"))),
    (challenge_gen.GENERATE_MCQ_SCHEMA, (("stem",), ("solution",), ("wrong", "mistake"))),
    (challenge_gen.AUDIT_SCHEMA, (("concepts", "idea"),)),
)


def _same_shape(schema: dict, known: dict, *, speech: bool = False) -> bool:
    """Recognise a known schema family, including local enums and speech extensions."""
    if not isinstance(schema, dict) or schema.get("type") != known.get("type"):
        return False
    if known.get("type") == "object":
        props, expected = schema.get("properties", {}), known.get("properties", {})
        if not isinstance(props, dict):
            return False
        omitted = {"speech"} if speech else set()
        if "speech" in props and speech and props["speech"] != {"type": "string"}:
            return False
        if set(props) - omitted != set(expected):
            return False
        required = schema.get("required", [])
        if not isinstance(required, list) or set(required) - omitted != set(known.get("required", [])):
            return False
        return all(_same_shape(props[name], field) for name, field in expected.items())
    if known.get("type") == "array":
        return _same_shape(schema.get("items"), known.get("items"))
    return True


def visual_fields(schema: dict | None) -> tuple[tuple[str, ...], ...]:
    """Return only the prose paths authorised by this complete, known schema shape."""
    if not isinstance(schema, dict):
        return ()
    return next((paths for known, paths in _VISUAL_FIELDS if _same_shape(schema, known, speech=True)), ())


def normalise_fields(data: dict | None, schema: dict | None) -> dict | None:
    """Copy changed prose branches without touching caller objects or cached JSON."""
    if not isinstance(data, dict):
        return data
    result = data
    for path in visual_fields(schema):
        key = path[0]
        value = data.get(key)
        if len(path) == 1:
            replacement = normalise_visual(value) if isinstance(value, str) else value
        elif isinstance(value, list):
            replacement = value
            field = path[1]
            for index, row in enumerate(value):
                if not isinstance(row, dict) or not isinstance(row.get(field), str):
                    continue
                text = normalise_visual(row[field])
                if text != row[field]:
                    if replacement is value:
                        replacement = list(value)
                    replacement[index] = {**row, field: text}
        else:
            continue
        if replacement != value:
            if result is data:
                result = dict(data)
            result[key] = replacement
    return result
