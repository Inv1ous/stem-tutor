"""The dot-and-cross renderer (build/diagrams.py): counts the drawn electrons, refuses bad input, writes SVG."""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "build"))
import diagrams  # noqa: E402


def caf2_params():
    """Ca loses two electrons; each F gains one. Before: Ca (2 crosses) and two F (7 dots). After: Ca2+ and two F- (8)."""
    f_before = ["dot"] * 7
    f_after = ["dot"] * 7 + ["cross"]
    return {"panels": [
        {"title": "Before: Ca 2 e-, F 7 e- each",
         "atoms": [{"symbol": "Ca", "x": 0.0, "y": 0.0, "electrons": ["cross", "cross"]},
                   {"symbol": "F", "x": -2.6, "y": 0.0, "electrons": f_before},
                   {"symbol": "F", "x": 2.6, "y": 0.0, "electrons": f_before}],
         "arrows": [{"from": 0, "to": 1, "label": "e-"}, {"from": 0, "to": 2, "label": "e-"}]},
        {"title": "After: Ca2+ and 2 F- (8 e- each)",
         "atoms": [{"symbol": "Ca", "x": 0.0, "y": 0.0, "electrons": [], "bracket": True, "charge": "2+"},
                   {"symbol": "F", "x": -2.6, "y": 0.0, "electrons": f_after, "bracket": True, "charge": "-"},
                   {"symbol": "F", "x": 2.6, "y": 0.0, "electrons": f_after, "bracket": True, "charge": "-"}]},
    ]}


def _marker_counts(fig):
    lines = [ln for ax in fig.axes for ln in ax.lines]
    return {"dot": sum(1 for ln in lines if ln.get_marker() == "o"),
            "cross": sum(1 for ln in lines if ln.get_marker() == "x")}


def test_caf2_draws_each_electron_once():
    fig = diagrams.dot_cross(caf2_params())
    counts = _marker_counts(fig)
    # before: Ca 2 crosses, 2 x F 7 dots; after: 2 x F- (7 dots, 1 cross) and Ca2+ with none
    assert counts == {"dot": 14 + 14, "cross": 2 + 2}


def test_arrows_and_titles_are_drawn():
    fig = diagrams.dot_cross(caf2_params())
    texts = [t.get_text() for ax in fig.axes for t in ax.texts]
    assert "Before: Ca 2 e-, F 7 e- each" in texts and "After: Ca2+ and 2 F- (8 e- each)" in texts
    assert sum(1 for ax in fig.axes for c in ax.get_children() if type(c).__name__ == "Annotation") == 2


def test_every_atom_is_inside_the_frame_and_panels_do_not_overlap():
    """Regression: the reviewed render clipped the outer F atoms and let adjacent panels overlap."""
    fig = diagrams.dot_cross(caf2_params())
    ax = fig.axes[0]
    x0, x1 = ax.get_xlim()
    symbols = [(t.get_position()[0], t.get_text()) for t in ax.texts if t.get_text() in ("Ca", "F")]
    assert symbols and all(x0 < x < x1 for x, _ in symbols)
    charges = [t.get_position()[0] for t in ax.texts if t.get_text() in ("2+", "-")]
    assert charges and all(x0 < x + 0.5 < x1 for x in charges)  # a charge label near the right edge stays in frame
    xs = sorted(x for x, _ in symbols)
    assert min(b - a for a, b in zip(xs, xs[1:])) > 2.5  # neighbouring atoms, across panel boundaries too


def test_more_than_eight_electrons_is_refused():
    params = {"panels": [{"atoms": [{"symbol": "F", "x": 0, "y": 0, "electrons": ["dot"] * 9}]}]}
    with pytest.raises(ValueError, match="at most 8"):
        diagrams.dot_cross(params)


def test_unknown_electron_mark_is_refused():
    params = {"panels": [{"atoms": [{"symbol": "F", "x": 0, "y": 0, "electrons": ["star"]}]}]}
    with pytest.raises(ValueError, match="unknown electron mark"):
        diagrams.dot_cross(params)


def test_empty_panels_are_refused():
    with pytest.raises(ValueError):
        diagrams.dot_cross({"panels": []})
    with pytest.raises(ValueError):
        diagrams.dot_cross({"panels": [{"atoms": []}]})


def test_render_writes_svg_through_the_normal_path(tmp_path, monkeypatch):
    monkeypatch.setattr(diagrams, "OUT", tmp_path)
    out = diagrams.render({"type": "dot_cross", "file": "Assets/9701/test-caf2.svg", "params": caf2_params()})
    assert out.exists() and out.suffix == ".svg"
    assert out.read_text(encoding="utf-8").lstrip().startswith("<?xml")
