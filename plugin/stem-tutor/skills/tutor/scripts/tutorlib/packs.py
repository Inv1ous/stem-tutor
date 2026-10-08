"""Read-only access to pre-built content packs (.tutor/packs/<CURRENT>/).

Layout: manifest.json · plan.json · specs/<spec>/graph.json · specs/<spec>/packs/<subtopic>.json
Template placeholders in stems/options use [[name]] or [[name:fmt]] so they never clash with LaTeX braces.
"""
from __future__ import annotations

import ast
import copy
import math
import operator
import re
from datetime import datetime, timedelta

from . import model
from .store import Vault, read_json

FRESH_DAYS = 7
_PLACEHOLDER = re.compile(r"\[\[(\w+)(?::([^\]]+))?\]\]")
_SAFE = {k: getattr(math, k) for k in ("sqrt", "sin", "cos", "tan", "asin", "acos", "atan", "atan2",
                                       "exp", "log", "log10", "pi", "e", "radians", "degrees", "floor", "ceil")}
_SAFE.update(abs=abs, round=round, min=min, max=max)


_BIN = {ast.Add: operator.add, ast.Sub: operator.sub, ast.Mult: operator.mul, ast.Div: operator.truediv,
        ast.Pow: operator.pow, ast.Mod: operator.mod, ast.FloorDiv: operator.floordiv}
_CMP = {ast.Lt: operator.lt, ast.LtE: operator.le, ast.Gt: operator.gt, ast.GtE: operator.ge,
        ast.Eq: operator.eq, ast.NotEq: operator.ne}


def _eval(expr: str, env: dict) -> float:
    """Arithmetic-only evaluator for template expressions (no attribute access, no arbitrary calls)."""
    names = {**_SAFE, **env}

    def ev(n):
        if isinstance(n, ast.Expression):
            return ev(n.body)
        if isinstance(n, ast.Constant) and isinstance(n.value, (int, float)):
            return n.value
        if isinstance(n, ast.Name) and n.id in names:
            return names[n.id]
        if isinstance(n, ast.BinOp) and type(n.op) in _BIN:
            return _BIN[type(n.op)](ev(n.left), ev(n.right))
        if isinstance(n, ast.UnaryOp) and isinstance(n.op, (ast.USub, ast.UAdd)):
            return -ev(n.operand) if isinstance(n.op, ast.USub) else ev(n.operand)
        if isinstance(n, ast.Call) and isinstance(n.func, ast.Name) and callable(names.get(n.func.id)) and not n.keywords:
            return names[n.func.id](*[ev(a) for a in n.args])
        if isinstance(n, ast.Compare) and all(type(o) in _CMP for o in n.ops):
            left = ev(n.left)
            for op, right in zip(n.ops, n.comparators):
                r = ev(right)
                if not _CMP[type(op)](left, r):
                    return False
                left = r
            return True
        if isinstance(n, ast.BoolOp):
            vals = [ev(v) for v in n.values]
            return all(vals) if isinstance(n.op, ast.And) else any(vals)
        raise ValueError(f"disallowed expression: {ast.dump(n)[:60]}")

    return float(ev(ast.parse(expr, mode="eval")))


def _fill(text: str, env: dict) -> str:
    def sub(m):
        v = env[m[1]]
        return format(v, m[2]) if m[2] else (f"{v:g}" if isinstance(v, float) else str(v))
    return _PLACEHOLDER.sub(sub, text)


def _sample(spec: dict, rng) -> float:
    if "choices" in spec:
        return rng.choice(spec["choices"])
    lo, hi, step = spec["min"], spec["max"], spec.get("step")
    if step:
        n = int(round((hi - lo) / step))
        return round(lo + step * rng.randint(0, n), 10)
    return rng.uniform(lo, hi)


def instantiate(item: dict, rng) -> dict:
    """Concrete copy of an item: template sampled, answers computed, generated MCQs shuffled."""
    inst = copy.deepcopy(item)
    tpl = item.get("template")
    if tpl:
        for _ in range(50):
            env = {name: _sample(spec, rng) for name, spec in tpl["params"].items()}
            for name, expr in tpl.get("derived", {}).items():
                env[name] = _eval(expr, env)
            if all(_eval(c, env) for c in tpl.get("constraints", [])):
                break
        else:
            raise ValueError(f"{item['id']}: template constraints unsatisfiable")
        inst["params"] = {k: env[k] for k in tpl["params"]}
        if "answer" in tpl:
            env["answer"] = _eval(tpl["answer"], env)
            inst["answer"] = {**item.get("answer", {}), "value": env["answer"]}
        inst["distractors"] = [
            {"value": _eval(d["expr"], env), **{k: v for k, v in d.items() if k != "expr"}}
            for d in tpl.get("distractors", [])
        ] if item["kind"] != "mcq" else item.get("distractors", {})
        inst["stem"] = _fill(item["stem"], env)
        if "options" in item:
            inst["options"] = {k: _fill(v, env) for k, v in item["options"].items()}
        inst.pop("template")
    if item["kind"] == "mcq" and item.get("shuffle") and item.get("source", {}).get("type") != "past":
        letters = sorted(inst["options"])
        order = letters[:]
        rng.shuffle(order)  # new letter i shows old option order[i]
        remap = {old: new for new, old in zip(letters, order)}
        inst["options"] = {new: inst["options"][old] for new, old in zip(letters, order)}
        inst["answer"] = remap[inst["answer"]]
        inst["distractors"] = {remap[k]: v for k, v in (inst.get("distractors") or {}).items()}
    return inst


REINSTALL = "reinstall the content (run publish) — the rest of your data is untouched"


class DamagedContent(ValueError):
    """A content file that is not valid JSON (cut off, or edited by hand): named, with what puts it right."""

    def __init__(self, path: str):
        self.path = path
        super().__init__(f"The content file {path} is damaged: {REINSTALL}")


class Packs:
    def __init__(self, vault: Vault):
        base = self.base = vault.tutor / "packs"
        self.vault_root = vault.root
        version = (base / "CURRENT").read_text().strip()
        self.root = base / version
        self.damaged: list[str] = []  # chapter packs left out because they could not be read
        self.manifest = self._read(self.root / "manifest.json") or {}
        self.plan = self._read(self.root / "plan.json") or {}
        self.kcs: dict[str, dict] = {}
        self.subtopics: dict[str, dict] = {}
        self.topics: dict[str, dict] = {}
        for spec in self.manifest.get("specs", []):
            g = self._read(self.root / "specs" / spec / "graph.json")
            for tp in g.get("topics", []):
                self.topics[tp["id"]] = {**tp, "spec": spec, "subject": g["subject"]}
            for st in g["subtopics"]:
                self.subtopics[st["id"]] = {**st, "spec": spec}
            for k in g["kcs"]:
                self.kcs[k["id"]] = {**k, "spec": spec, "subject": g["subject"]}
        self._packs: dict[str, dict | None] = {}
        self.papers = (self._read(self.root / "papers.json") or {}).get("papers", [])

    def _read(self, path):
        try:
            return read_json(path)
        except ValueError:
            raise DamagedContent(path.relative_to(self.vault_root).as_posix()) from None

    def kc(self, kc_id: str) -> dict:
        return self.kcs[kc_id]

    def pack(self, subtopic: str) -> dict | None:
        if subtopic not in self._packs:
            spec = self.subtopics[subtopic]["spec"]
            if not self.root.exists():  # a newer publish pruned the version this app loaded: read the current one
                self.root = self.base / (self.base / "CURRENT").read_text().strip()
            try:
                self._packs[subtopic] = self._read(self.root / "specs" / spec / "packs" / f"{subtopic}.json")
            except DamagedContent as e:  # that chapter is left out, as if not built yet; the rest still works
                self._packs[subtopic] = None
                self.damaged.append(e.path)
        return self._packs[subtopic]

    def published(self) -> set[str]:
        """Subtopics that have a pack in this version."""
        return {p.stem for p in self.root.glob("specs/*/packs/*.json")}

    def pack_for_kc(self, kc_id: str) -> dict | None:
        meta = self.kcs.get(kc_id)  # an idea a republish dropped can still have a review card in your history
        return self.pack(meta["subtopic"]) if meta else None

    def items_for(self, kc_id: str) -> list[dict]:
        p = self.pack_for_kc(kc_id)
        return [i for i in (p or {}).get("items", []) if kc_id in i["kcs"]]

    def worked_for(self, kc_id: str) -> list[dict]:
        p = self.pack_for_kc(kc_id)
        return [w for w in (p or {}).get("worked", []) if w["kc"] == kc_id]

    def misconception(self, subtopic: str, mis_id: str) -> dict | None:
        p = self.pack(subtopic) or {}
        return next((m for m in p.get("misconceptions", []) if m["id"] == mis_id), None)

    def select_item(self, kc_id: str, state: dict, target_p: float, rng, now: datetime | None = None,
                    kinds: tuple[str, ...] | None = None, exclude: frozenset[str] | set[str] = frozenset()) -> dict | None:
        theta = state["kcs"].get(kc_id, {}).get("theta", 0.0)
        cutoff = (now - timedelta(days=FRESH_DAYS)) if now else None
        scored = []
        for item in self.items_for(kc_id):
            if item["id"] in exclude or (kinds and item["kind"] not in kinds):
                continue
            seen = state["items_seen"].get(item["id"])
            stale = bool(seen) and not item.get("template") and (
                cutoff is None or datetime.fromisoformat(seen) > cutoff)
            gap = abs(model.p_correct(theta, item.get("difficulty", 3)) - target_p)
            extra = item.get("tier") == "extra"  # unexplained bank questions: only after explained ones
            scored.append((stale, extra, round(gap, 2), bool(seen), rng.random(), item))
        if not scored:
            return None
        return min(scored, key=lambda s: s[:5])[5]
