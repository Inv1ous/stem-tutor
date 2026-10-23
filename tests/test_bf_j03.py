from __future__ import annotations

import os
from pathlib import Path
import subprocess
import sys

import pytest

from tutorlib import grade


@pytest.mark.parametrize("entry", ["parse_quantity", "value_problem"])
@pytest.mark.parametrize("text", ["1e10000000 m", "1 × 10^{10000000} m", "10¹⁰⁰⁰⁰⁰⁰⁰ m"])
def test_an_extreme_exponent_is_refused_without_stalling(entry: str, text: str) -> None:
    """B-109 (bug watch): a pasted exponent must not stall synchronous answer handling."""
    scripts = Path(__file__).resolve().parents[1] / "plugin/stem-tutor/skills/tutor/scripts"
    code = """
import sys
from tutorlib.grade import ParseError, parse_quantity, value_problem

entry, text = sys.argv[1:]
if entry == "parse_quantity":
    try:
        parse_quantity(text)
    except ParseError:
        pass
    else:
        raise AssertionError("out-of-range number was accepted")
else:
    assert value_problem({"answer": {"value": 1, "unit": "m"}}, text) == "unreadable"
"""
    # subprocess.run kills and waits for a timed-out child, even before this fix is applied.
    result = subprocess.run(
        [sys.executable, "-c", code, entry, text],
        env={**os.environ, "PYTHONPATH": str(scripts), "PYTHONDONTWRITEBYTECODE": "1"},
        capture_output=True, text=True, timeout=2,
    )
    assert result.returncode == 0, result.stderr


@pytest.mark.parametrize("text,value,sf", [
    ("4.52e-3 m", 0.00452, 3),
    ("1.20 × 10^3 m", 1200.0, 3),
    ("1/4 × 10^2 m", 25.0, None),
    ("1e308 m", 1e308, 1),
    ("1e-308 m", 1e-308, 1),
    ("0e3 m", 0.0, 1),
])
def test_representable_standard_form_keeps_its_value_unit_and_figures(
    text: str, value: float, sf: int | None,
) -> None:
    """B-109: bounding exponent evaluation preserves ordinary answers and float-range edges."""
    got, unit, figures = grade.parse_quantity(text)
    assert got == pytest.approx(value, abs=0)
    assert (unit, figures) == ("m", sf)
