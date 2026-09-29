"""Render diagram requests from packs into SVG files (build time, macOS).

Agents never hand-write SVG coordinates: they request a diagram type with parameters and this
module draws it, so every figure is geometrically correct and consistently styled. White
background so figures read in both light and dark Obsidian themes.

  python build/diagrams.py <pack.json> [...]   renders every entry in each pack's "diagrams" list
"""
from __future__ import annotations

import json
import math
import sys
from pathlib import Path

import matplotlib
import matplotlib.patches

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "plugin/stem-tutor/skills/tutor/scripts"))
from tutorlib.packs import _eval  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "build/out"
INK, BLUE, ORANGE, GREY = "#1f2328", "#1f6feb", "#d9480f", "#8c959f"
plt.rcParams.update({"font.size": 11, "svg.fonttype": "none", "axes.edgecolor": INK, "axes.labelcolor": INK,
                     "xtick.color": INK, "ytick.color": INK, "figure.facecolor": "white"})


def _axes(size=(5.2, 3.6)):
    fig, ax = plt.subplots(figsize=size)
    ax.set_facecolor("white")
    for side in ("top", "right"):
        ax.spines[side].set_visible(False)
    return fig, ax


def graph_sketch(p: dict):
    fig, ax = _axes()
    colors = [BLUE, ORANGE, INK, GREY]
    for i, line in enumerate(p["lines"]):
        xs, ys = zip(*line["points"])
        ax.plot(xs, ys, color=line.get("color", colors[i % 4]), lw=2.2,
                ls="--" if line.get("style") == "dashed" else "-", label=line.get("label"),
                marker=line.get("marker"), ms=5)
    if p.get("shade", {}).get("polygon"):
        ax.fill(*zip(*p["shade"]["polygon"]), color=BLUE, alpha=0.15, lw=0)
    elif p.get("shade"):
        xs, ys = zip(*p["lines"][p["shade"].get("line", 0)]["points"])
        ax.fill_between(xs, ys, 0, color=BLUE, alpha=0.15)
    for a in p.get("annotations", []):
        ax.annotate(a["text"], a["xy"], xytext=a.get("xytext", (a["xy"][0], a["xy"][1])), color=INK,
                    arrowprops={"arrowstyle": "->", "color": INK} if a.get("xytext") else None)
    ax.set_xlabel(p.get("xlabel", "")); ax.set_ylabel(p.get("ylabel", ""))
    if not p.get("ticks", False):
        ax.set_xticks([]); ax.set_yticks([])
    if p.get("xticklabels"):
        ax.set_xticks([t[0] for t in p["xticklabels"]], [t[1] for t in p["xticklabels"]])
    if any(l.get("label") for l in p["lines"]):
        ax.legend(frameon=False)
    if p.get("ylim"):
        ax.set_ylim(*p["ylim"])
    else:
        ax.axhline(0, color=INK, lw=0.8)
    return fig


def function_plot(p: dict):
    fig, ax = _axes()
    colors = [BLUE, ORANGE, INK]
    for i, f in enumerate(p["functions"]):
        lo, hi = f["domain"]
        xs, ys = [], []
        for k in range(401):
            x = lo + (hi - lo) * k / 400
            try:
                y = _eval(f["expr"], {"x": x})
                if math.isfinite(y) and abs(y) < 1e6:
                    xs.append(x); ys.append(y); continue
            except (ZeroDivisionError, ValueError, OverflowError):
                pass
            if xs:
                ax.plot(xs, ys, color=colors[i % 3], lw=2.2); xs, ys = [], []
        if xs:
            ax.plot(xs, ys, color=colors[i % 3], lw=2.2, label=f.get("label"))
    for x in p.get("asymptotes", {}).get("x", []):
        ax.axvline(x, color=GREY, ls="--", lw=1)
    for y in p.get("asymptotes", {}).get("y", []):
        ax.axhline(y, color=GREY, ls="--", lw=1)
    for pt in p.get("points", []):
        ax.plot(*pt["xy"], "o", color=INK, ms=4)
        ax.annotate(pt.get("label", ""), pt["xy"], textcoords="offset points", xytext=(6, 6))
    ax.spines["left"].set_position("zero"); ax.spines["bottom"].set_position("zero")
    if p.get("xlim"): ax.set_xlim(p["xlim"])
    if p.get("ylim"): ax.set_ylim(p["ylim"])
    ax.set_xlabel(p.get("xlabel", "x"), loc="right"); ax.set_ylabel(p.get("ylabel", "y"), loc="top", rotation=0)
    if any(f.get("label") for f in p["functions"]):
        ax.legend(frameon=False, loc="best")
    return fig


def box_plot(p: dict):
    """Horizontal box plot on a real value axis; outliers drawn as crosses beyond the whiskers."""
    fig, ax = plt.subplots(figsize=(6.4, 2.4))
    ax.set_facecolor("white")
    for side in ("top", "right", "left"):
        ax.spines[side].set_visible(False)
    lo, q1, med, q3, hi = p["min"], p["q1"], p["median"], p["q3"], p["max"]
    y, h = 0.5, 0.18
    ax.add_patch(matplotlib.patches.Rectangle((q1, y - h), q3 - q1, 2 * h, fill=False, ec=BLUE, lw=2.2))
    ax.plot([med, med], [y - h, y + h], color=BLUE, lw=2.2)
    for a, b in ((lo, q1), (q3, hi)):
        ax.plot([a, b], [y, y], color=BLUE, lw=2.2)
    for end in (lo, hi):
        ax.plot([end, end], [y - h / 2, y + h / 2], color=BLUE, lw=2.2)
    for o in p.get("outliers", []):
        ax.plot(o, y, marker="x", color=ORANGE, ms=10, mew=2.4, ls="none")
    if p.get("labels", True):
        above, below = y + h + 0.1, y - h - 0.1
        ax.text(q1, above, f"$Q_1$ = {q1:g}", ha="center", va="bottom", color=INK)
        ax.text(med, below, f"median = {med:g}", ha="center", va="top", color=INK)
        ax.text(q3, above, f"$Q_3$ = {q3:g}", ha="center", va="bottom", color=INK)
        ax.text(lo, below, f"min = {lo:g}", ha="center", va="top", color=INK)
        ax.text(hi, below, p.get("whisker_label", f"{hi:g}"), ha="center", va="top", color=INK)
        for o in p.get("outliers", []):
            ax.text(o, above, p.get("outlier_label", f"outlier = {o:g}"), ha="center", va="bottom", color=ORANGE)
    ticks = p.get("ticks")
    if ticks:
        ax.set_xticks(ticks)
        ax.set_xlim(ticks[0], ticks[-1])
    ax.set_yticks([])
    ax.set_ylim(-0.08, 1.05)
    ax.set_xlabel(p.get("xlabel", ""))
    return fig


def density_panels(p: dict):
    """Side-by-side smooth distribution shapes; optionally marks mode, median and mean (computed numerically)."""
    panels = p["panels"]
    fig, axes = plt.subplots(1, len(panels), figsize=(3.4 * len(panels), 2.8), sharey=True)
    axes = list(axes) if len(panels) > 1 else [axes]
    for ax, pan in zip(axes, panels):
        ax.set_facecolor("white")
        for side in ("top", "right", "left"):
            ax.spines[side].set_visible(False)
        lo, hi = pan["domain"]
        n = 2000
        xs = [lo + (hi - lo) * k / n for k in range(n + 1)]
        ys = [max(_eval(pan["expr"], {"x": x}), 0.0) for x in xs]
        ax.plot(xs, ys, color=BLUE, lw=2.2)
        ax.fill_between(xs, ys, 0, color=BLUE, alpha=0.10)
        if p.get("mark_centres", True):
            dx = (hi - lo) / n
            area = sum(ys) * dx
            mean = sum(x * y for x, y in zip(xs, ys)) * dx / area
            run, median = 0.0, xs[-1]
            for x, y in zip(xs, ys):
                run += y * dx
                if run >= area / 2:
                    median = x
                    break
            mode = xs[max(range(len(ys)), key=ys.__getitem__)]
            top = max(ys)
            for x, name, style in ((mode, "mode", ":"), (median, "median", "--"), (mean, "mean", "-")):
                ax.plot([x, x], [0, top * 1.05], color=ORANGE if name == "mean" else INK, lw=1.3, ls=style)
            order = sorted(((mode, "mode"), (median, "median"), (mean, "mean")))
            for j, (x, name) in enumerate(order):
                ax.text(x, top * (1.12 + 0.13 * j), name, ha="center", va="bottom", fontsize=9,
                        color=ORANGE if name == "mean" else INK)
            ax.set_ylim(0, top * 1.55)
        ax.set_yticks([])
        ax.set_xticks([])
        ax.set_xlim(lo, hi)
        ax.set_xlabel(p.get("xlabel", ""))
        ax.set_title(pan.get("title", ""), fontsize=10, color=INK)
    return fig


def free_body(p: dict):
    fig, ax = plt.subplots(figsize=(4.2, 4.2))
    ax.set_aspect("equal"); ax.axis("off")
    tilt = p.get("incline_deg", 0)
    if tilt:  # slope passes through the bottom-centre of the rotated box
        t = math.radians(tilt)
        bx, by = 0.35 * math.sin(t), -0.35 * math.cos(t)
        ax.plot([-2.2, 2.2], [by + math.tan(t) * (-2.2 - bx), by + math.tan(t) * (2.2 - bx)], color=GREY, lw=2)
    if p.get("body", "box") == "box":
        box = matplotlib.patches.Rectangle((-0.45, -0.35), 0.9, 0.7, angle=tilt, rotation_point="center",
                                           fill=False, ec=INK, lw=2)
        ax.add_patch(box)
    else:
        ax.plot(0, 0, "o", color=INK, ms=8)
    for f in p["forces"]:
        a, L = math.radians(f["angle"]), f.get("length", 1.2)
        ax.annotate("", (L * math.cos(a), L * math.sin(a)), (0, 0),
                    arrowprops={"arrowstyle": "-|>", "color": f.get("color", BLUE), "lw": 2.2, "mutation_scale": 16})
        ax.text((L + 0.25) * math.cos(a), (L + 0.25) * math.sin(a), f["label"], ha="center", va="center", color=INK)
    ax.set_xlim(-2.3, 2.3); ax.set_ylim(-2.3, 2.3)
    return fig


def energy_profile(p: dict):
    fig, ax = _axes()
    r, pr, ea = p.get("reactants", 0.0), p["products"], p["ea"]
    peak = r + ea
    xs = [0, 1, 1.6, 2.4, 3, 4]
    def curve(top):
        import numpy as np
        t = np.linspace(0, 1, 200)
        left = r + (top - r) * np.sin(t * math.pi / 2) ** 2
        right = top + (pr - top) * np.sin(t * math.pi / 2) ** 2
        return np.concatenate([np.linspace(0, 1, 30), 1 + t, 2 + t, np.linspace(3, 4, 30)]), \
            np.concatenate([[r] * 30, left, right, [pr] * 30])
    x, y = curve(peak)
    ax.plot(x, y, color=BLUE, lw=2.4, label=p.get("label"))
    if p.get("catalysed_ea"):
        x2, y2 = curve(r + p["catalysed_ea"])
        ax.plot(x2, y2, color=ORANGE, lw=2, ls="--", label=p.get("catalysed_label", "with catalyst"))
    ax.annotate("", (2, peak), (2, r), arrowprops={"arrowstyle": "<->", "color": INK})
    ax.text(1.94, (r + peak) / 2, p.get("ea_label", "$E_a$"), ha="right")
    ax.annotate("", (3.6, pr), (3.6, r), arrowprops={"arrowstyle": "<->", "color": INK})
    ax.text(3.66, (r + pr) / 2, p.get("dh_label", r"$\Delta H$"))
    ax.hlines([r], 0, 3.8, colors=GREY, lw=0.8, linestyles=":")
    ax.text(0.05, r + 0.08 * abs(ea), p.get("reactants_label", "reactants"))
    ax.text(3.05, pr + 0.08 * abs(ea), p.get("products_label", "products"))
    ax.set_xticks([]); ax.set_yticks([])
    ax.set_xlabel("progress of reaction"); ax.set_ylabel("energy")
    if p.get("catalysed_ea"):
        ax.legend(frameon=False)
    return fig


def maxwell_boltzmann(p: dict):
    import numpy as np
    fig, ax = _axes()
    e = np.linspace(0, 10, 400)
    colors = [BLUE, ORANGE, INK]
    for i, T in enumerate(p.get("temps", [1.0])):
        f = np.sqrt(e) * np.exp(-e / T) / T ** 1.5
        ax.plot(e, f, color=colors[i % 3], lw=2.2, label=(p.get("labels") or [None] * 3)[i])
        if p.get("ea") and p.get("shade_ea", True):
            m = e >= p["ea"]
            ax.fill_between(e[m], f[m], color=colors[i % 3], alpha=0.12)
    if p.get("ea"):
        ax.axvline(p["ea"], color=GREY, ls="--", lw=1)
        ax.text(p["ea"] + 0.1, ax.get_ylim()[1] * 0.85, "$E_a$")
    ax.set_xticks([]); ax.set_yticks([])
    ax.set_xlabel("energy"); ax.set_ylabel("number of molecules")
    if p.get("labels"):
        ax.legend(frameon=False)
    return fig


def wave(p: dict):
    import numpy as np
    fig, ax = _axes((5.6, 2.8))
    A, lam, n = p.get("amplitude", 1.0), p.get("wavelength", 2.0), p.get("cycles", 2)
    x = np.linspace(0, lam * n, 400)
    ax.plot(x, A * np.sin(2 * np.pi * x / lam), color=BLUE, lw=2.2)
    ax.axhline(0, color=INK, lw=0.8)
    if p.get("show_amplitude", True):
        ax.annotate("", (lam / 4, A), (lam / 4, 0), arrowprops={"arrowstyle": "<->", "color": INK})
        ax.text(lam / 4 + 0.05 * lam, A / 2, "A")
    if p.get("show_wavelength", True):
        ax.annotate("", (lam * 1.25, A * 1.15), (lam * 0.25, A * 1.15), arrowprops={"arrowstyle": "<->", "color": INK})
        ax.text(lam * 0.75, A * 1.22, r"$\lambda$", ha="center")
    ax.set_ylim(-1.4 * A, 1.5 * A)
    ax.set_xticks([]); ax.set_yticks([])
    ax.set_xlabel(p.get("xlabel", "distance")); ax.set_ylabel(p.get("ylabel", "displacement"))
    return fig


def circuit(p: dict):
    import schemdraw
    import schemdraw.elements as elm
    # CAIE/UK (IEC) symbols: rectangular resistor, crossed-circle lamp
    kinds = {"battery": elm.BatteryCell, "cell": elm.Battery, "resistor": elm.ResistorIEC, "lamp": elm.Lamp2,
             "ammeter": elm.MeterA, "voltmeter": elm.MeterV, "switch": elm.Switch, "ldr": elm.PhotoresistorIEC,
             "thermistor": elm.Thermistor, "diode": elm.Diode, "variable_resistor": elm.ResistorVarIEC,
             "potentiometer": elm.PotentiometerIEC}
    d = schemdraw.Drawing(show=False)
    d.config(fontsize=12, color=INK)
    seq = p["elements"]
    # series loop: first half along the top, then down, back along the bottom, and up
    half = max(1, math.ceil(len(seq) / 2))
    for i, e in enumerate(seq):
        direction = "right" if i < half else "left"
        el = kinds[e["type"]]().label(e.get("label", ""))
        d.add(getattr(el, direction)())
        if i == half - 1:
            d.add(elm.Line().down())
    d.add(elm.Line().up())
    return d


RENDER = {"graph_sketch": graph_sketch, "function_plot": function_plot, "free_body": free_body,
          "energy_profile": energy_profile, "maxwell_boltzmann": maxwell_boltzmann, "wave": wave, "circuit": circuit,
          "box_plot": box_plot, "density_panels": density_panels}


def render(req: dict) -> Path:
    out = OUT / req["file"]
    out.parent.mkdir(parents=True, exist_ok=True)
    obj = RENDER[req["type"]](req.get("params", {}))
    if req["type"] == "circuit":
        obj.save(str(out))
    else:
        obj.tight_layout()
        obj.savefig(out, format="svg", facecolor="white")
        plt.close(obj)
    return out


if __name__ == "__main__":
    for pack_path in sys.argv[1:]:
        pack = json.loads(Path(pack_path).read_text())
        for req in pack.get("diagrams", []):
            print(render(req).relative_to(ROOT))
