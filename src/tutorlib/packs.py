"""Read-only access to pre-built content packs (.tutor/packs/<CURRENT>/).

Layout: manifest.json · plan.json · specs/<spec>/graph.json · specs/<spec>/packs/<subtopic>.json
Template placeholders in stems/options use [[name]] or [[name:fmt]] so they never clash with LaTeX braces.
"""
from __future__ import annotations

import ast
import copy
import json
import math
import operator
import re
from datetime import datetime, timedelta

from . import model, topicals, question_duplicates
from .store import Vault, read_json
from .library_refs import LibraryRefs

FRESH_DAYS = 7
_PLACEHOLDER = re.compile(r"\[\[(\w+)(?::([^\]]+))?\]\]")
_SAFE = {k: getattr(math, k) for k in ("sqrt", "sin", "cos", "tan", "asin", "acos", "atan", "atan2",
                                       "exp", "log", "log10", "pi", "e", "radians", "degrees", "floor", "ceil")}
_SAFE.update(abs=abs, round=round, min=min, max=max)


def _selection_content(item: dict) -> tuple[dict, dict]:
    """Compare every field, separating optional teaching supplements.

    Canonical paper identity replaces citation typography, whitespace is
    immaterial, and optional teaching detail may enrich an otherwise identical
    assessment. Unknown fields and differing nonempty supplements conflict.
    """
    def normal(value):
        if isinstance(value, str):
            return re.sub(r'\s+', ' ', value).strip()
        if isinstance(value, dict):
            return {key: normal(child) for key, child in value.items() if child is not None}
        if isinstance(value, list):
            return [normal(child) for child in value]
        return value

    content = normal(copy.deepcopy(item))
    for key in ('id', 'tier', '_canonical_identity'):
        content.pop(key, None)
    content['kcs'] = sorted(content.get('kcs', []))
    source = content.get('source')
    if isinstance(source, dict):
        for key in ('qid', 'ref', 'part'):
            source.pop(key, None)
    supplements = {key: content.pop(key) for key in ('explanation', 'hints', 'distractors', 'command_word')
                   if key in content and content[key] not in ('', [], {})}
    return content, supplements


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
            vals = (ev(v) for v in n.values)
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
        from decimal import Decimal
        # Keep supplied grid resolution, including a fractional offset; ordinary grids retain ten-place rounding.
        places = max(10, -Decimal(str(lo)).as_tuple().exponent, -Decimal(str(step)).as_tuple().exponent)
        n = int(round((hi - lo) / step))
        if n > 0 and round(lo + step * n, places) > hi:
            n -= 1  # a nondivisible interval must not round up to a grid point beyond its maximum
        return round(lo + step * rng.randint(0, n), places)
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
        if item.get("options") is not None:
            inst["options"] = {k: _fill(v, env) for k, v in item["options"].items()}
        if item.get("explanation"):
            inst["explanation"] = _fill(item["explanation"], env)
        if item.get("hints"):
            inst["hints"] = [_fill(hint, env) for hint in item["hints"]]
        inst.pop("template")
    if (item["kind"] == "mcq" and item.get("shuffle") and item.get("source", {}).get("type") != "past"
            and inst.get("options") is not None):  # choices printed only in an image keep their original labels
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
        legacy_base = vault.tutor / "packs"
        self.pointer_base = legacy_base
        self.vault_root = vault.root
        try:
            self.library_refs = LibraryRefs(vault.root)
        except ValueError:  # a broken catalog makes every Library-backed reference untrustworthy
            raise DamagedContent("Library/catalog.json") from None
        version = (legacy_base / "CURRENT").read_text().strip()
        canonical_base = vault.root / "Library" / "Releases"
        # New publications live in the visible, synchronized Library. Old
        # vaults keep reading their historical .tutor/packs layout until the
        # corresponding canonical release has been migrated.
        base = canonical_base if (canonical_base / version).is_dir() else legacy_base
        self.base = base
        self.root = base / version
        self.damaged: list[str] = []  # chapter packs left out because they could not be read
        self.manifest = self._read(self.root / "manifest.json") or {}
        self.plan = self._read(self.root / "plan.json") or {}
        # Keep the published dates so removing an Almanac override restores them until the next publication.
        self.plan_dates = {k: copy.deepcopy(self.plan[k]) for k in ("papers", "sittings") if k in self.plan}
        self.syllabus_versions: dict[str, str] = {}
        self.kcs: dict[str, dict] = {}
        self.subtopics: dict[str, dict] = {}
        self.topics: dict[str, dict] = {}
        for spec in self.manifest.get("specs", []):
            g = self._read(self.root / "specs" / spec / "graph.json")
            self.syllabus_versions[spec] = g.get("version")
            for tp in g.get("topics", []):
                self.topics[tp["id"]] = {**tp, "spec": spec, "subject": g["subject"]}
            for st in g["subtopics"]:
                self.subtopics[st["id"]] = {**st, "spec": spec}
            for k in g["kcs"]:
                self.kcs[k["id"]] = {**k, "spec": spec, "subject": g["subject"]}
        self._packs: dict[str, dict | None] = {}
        self._asset_failures: set[str] = set()
        self.topicals = topicals.Bank(vault.root, self)
        self.topicals.refresh()
        self._topical_index_version = None
        self._topical_index: dict[str, list[dict]] = {}
        self._topical_aliases: dict[str, set[str]] = {}
        self.selection_conflicts: list[dict] = []
        self.duplicate_reviews = question_duplicates.Reviews(vault.root)
        self._legacy_aliases: dict[str, set[str]] | None = None
        papers_path = self.root / "papers.json"
        papers = (self._read(papers_path) or {}).get("papers", [])
        try:
            self.papers = self.library_refs.content(papers)
        except ValueError:  # a source index with unverified assets cannot be used for marking or attribution
            raise DamagedContent(papers_path.relative_to(self.vault_root).as_posix()) from None

    @property
    def topical_errors(self) -> list[str]:
        return self.topicals.errors

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
            if not self.root.exists():
                path = self.root / "specs" / spec / "packs" / f"{subtopic}.json"
                raise DamagedContent(path.relative_to(self.vault_root).as_posix())
            path = self.root / "specs" / spec / "packs" / f"{subtopic}.json"
            try:
                source = self._read(path)
            except DamagedContent as e:  # that chapter is left out, as if not built yet; the rest still works
                self._packs[subtopic] = None
                self.damaged.append(e.path)
            else:
                try:
                    loaded = self.library_refs.content(source)
                    # Older immutable packs can repeat one assessed ID. Adapt
                    # only this runtime copy so a new answer counts once per KC.
                    if isinstance(loaded, dict) and isinstance(loaded.get('items'), list):
                        for item in loaded['items']:
                            kcs = item.get('kcs') if isinstance(item, dict) else None
                            if (isinstance(kcs, list) and all(isinstance(k, str) for k in kcs)
                                    and len(kcs) != len(set(kcs))):
                                item['kcs'] = list(dict.fromkeys(kcs))
                    self._packs[subtopic] = loaded
                except ValueError:  # a missing, unsafe, or hash-mismatched asset invalidates this chapter only
                    self._asset_failures.add(subtopic)
                    relative = path.relative_to(self.vault_root).as_posix()
                    if relative not in self.damaged:
                        self.damaged.append(relative)
                    return None  # a later explicit load rechecks restored bytes; cache only verified content
                else:
                    relative = path.relative_to(self.vault_root).as_posix()
                    if self._packs[subtopic] is not None and relative in self.damaged:
                        self._asset_failures.discard(subtopic)
                        self.damaged.remove(relative)
                        self._legacy_aliases = None
                        self._topical_index_version = None
        return self._packs[subtopic]

    def published(self) -> set[str]:
        """Subtopics that have a pack in this version."""
        return {p.stem for p in self.root.glob("specs/*/packs/*.json")}

    def pack_for_kc(self, kc_id: str) -> dict | None:
        meta = self.kcs.get(kc_id)  # an idea a republish dropped can still have a review card in your history
        return self.pack(meta["subtopic"]) if meta else None

    def items_for(self, kc_id: str, *, _retry_assets: bool = True) -> list[dict]:
        # All canonical aliases participate, including duplicates in other chapter packs.
        self.topicals.refresh()
        if not self.topicals.items:
            p = self.pack_for_kc(kc_id)
            return self._distinct_candidates([i for i in (p or {}).get("items", []) if kc_id in i["kcs"]])
        if _retry_assets:
            for subtopic in tuple(self._asset_failures):
                self.pack(subtopic)  # one probe per pending chapter; rebuild the overlay only after recovery
        if self._topical_index_version != self.topicals.pointer:
            self.library_refs = LibraryRefs(self.vault_root)
            originals = [i for sub in sorted(self.published()) if sub in self.subtopics
                         for i in (self.pack(sub) or {}).get("items", [])]
            self._topical_aliases = {}
            for original in [*originals, *self.topicals.items]:
                if (ident := topicals.identity(original)):
                    self._topical_aliases.setdefault(ident, set()).add(original["id"])
            self._topical_index = {}
            items = self.library_refs.content(self._distinct_candidates(self.topicals.overlay(originals)))
            for item in items:
                for kc in item["kcs"]:
                    self._topical_index.setdefault(kc, []).append(item)
            self._topical_index_version = self.topicals.pointer
        return list(self._topical_index.get(kc_id, []))

    def _distinct_candidates(self, items: list[dict]) -> list[dict]:
        groups = {}
        for item in items:
            identity = topicals.identity(item)
            key = (identity or item['id'], tuple(sorted(item['kcs'])))
            groups.setdefault(key, []).append(item)
        result = []
        for (identity, context), rows in groups.items():
            rows = self.duplicate_reviews.filter(rows, identity, context)
            if len(rows) == 1:
                result.extend(rows)
                continue
            compared = [_selection_content(row) for row in rows]
            fields = set()
            for index, (assessment, supplements) in enumerate(compared):
                for other, extra in compared[index + 1:]:
                    fields.update(key for key in assessment.keys() | other.keys() if assessment.get(key) != other.get(key))
                    fields.update(key for key in supplements.keys() & extra.keys() if supplements[key] != extra[key])
            if fields:
                conflict = {'identity': identity, 'kcs': list(context), 'ids': [row['id'] for row in rows],
                            'fields': sorted(fields)}
                if conflict not in self.selection_conflicts:
                    self.selection_conflicts.append(conflict)
                result.extend(rows)
            else:
                # Prefer an explained original, then the richest available copy.
                result.append(max(rows, key=lambda row: (bool(row.get('explanation')), row.get('tier') != 'extra',
                                                         len(json.dumps(row, sort_keys=True)))))
        return result

    def topical_chapters(self) -> set[str]:
        self.topicals.refresh()
        return {chapter for item in self.topicals.items for chapter in item["topical"]["chapters"]}

    def _legacy_alias_index(self) -> dict[str, set[str]]:
        if self._legacy_aliases is not None:
            return self._legacy_aliases
        aliases: dict[str, set[str]] = {}
        for sub in self.published():
            if sub in self.subtopics:
                for row in (self.pack(sub) or {}).get('items', []):
                    if ident := topicals.identity(row):
                        aliases.setdefault(ident, set()).add(row['id'])
        self._legacy_aliases = aliases
        return aliases

    def aliases_for(self, item: dict, legacy_aliases: dict[str, set[str]] | None = None) -> set[str]:
        """Return known IDs for the same paper question, including legacy packs."""
        ident = topicals.identity(item)
        if not ident:
            return {item['id']}
        self.topicals.refresh()
        if self.topicals.items:
            if item.get('kcs'):
                self.items_for(item['kcs'][0], _retry_assets=False)
            return self._topical_aliases.get(ident, set()) | {item['id']}
        return (legacy_aliases if legacy_aliases is not None else self._legacy_alias_index()).get(ident, set()) | {item['id']}

    def topical_items(self, chapter: str) -> list[dict]:
        """Reviewed bank questions, with existing canonical IDs preserved, independent of lessons."""
        self.topicals.refresh()
        if not self.topicals.items:
            return []
        self.items_for(self.topicals.items[0]["kcs"][0])  # refresh the canonical overlay index
        bank_ids = {topicals.identity(item) for item in self.topicals.items}
        candidates = [item for rows in self._topical_index.values() for item in rows
                      if topicals.identity(item) in bank_ids and item.get("topical", {}).get("reviewed")
                      and chapter in item["topical"]["chapters"]]
        candidates.sort(key=lambda item: not any(self.kcs.get(k, {}).get("subtopic") == chapter for k in item["kcs"]))
        unique = {}
        for item in candidates:
            unique.setdefault((item['id'], tuple(sorted(item['kcs']))), {**item, "_serving_chapter": chapter})
        return list(unique.values())

    def worked_for(self, kc_id: str) -> list[dict]:
        p = self.pack_for_kc(kc_id)
        return [w for w in (p or {}).get("worked", []) if w["kc"] == kc_id]

    def misconception(self, subtopic: str, mis_id: str) -> dict | None:
        p = self.pack(subtopic) or {}
        return next((m for m in p.get("misconceptions", []) if m["id"] == mis_id), None)

    def select_item(self, kc_id: str, state: dict, target_p: float, rng, now: datetime | None = None,
                    kinds: tuple[str, ...] | None = None, exclude: frozenset[str] | set[str] = frozenset(),
                    unassisted: bool = False) -> dict | None:
        theta = state["kcs"].get(kc_id, {}).get("theta", 0.0)
        cutoff = (now - timedelta(days=FRESH_DAYS)) if now else None
        scored = []
        legacy_aliases = None
        chapter = self.kcs.get(kc_id, {}).get("subtopic")
        candidates = self.items_for(kc_id)
        initial_aliases = {key: set(ids) for key, ids in self._topical_aliases.items()}
        for item in candidates:
            ident = topicals.identity(item) or item["id"]
            if any(e["identity"] == ident and e["chapter"] == chapter for e in state.get("topical_exclusions", [])):
                continue
            if item.get("topical") and topicals.eligibility(item, chapter, state, self, unassisted)["status"] not in ("solvable", "supported"):
                continue
            if item["id"] in exclude or (kinds and item["kind"] not in kinds):
                continue
            aliases = self.aliases_for(item, legacy_aliases)
            if exclude:
                self.topicals.refresh()
                if not self.topicals.items and topicals.identity(item) and legacy_aliases is None:
                    legacy_aliases = self._legacy_alias_index()
                if (self.aliases_for(item, legacy_aliases) | initial_aliases.get(ident, set())) & set(exclude):
                    continue
            seen = max((datetime.fromisoformat(state["items_seen"][key])
                        for key in aliases if key in state["items_seen"]), default=None)
            stale = bool(seen) and not item.get("template") and (
                cutoff is None or seen > cutoff)
            gap = abs(model.p_correct(theta, item.get("difficulty", 3)) - target_p)
            extra = item.get("tier") == "extra"  # unexplained bank questions: only after explained ones
            scored.append((stale, extra, round(gap, 2), bool(seen), rng.random(), item))
        if not scored:
            return None
        return {**min(scored, key=lambda s: s[:5])[5], "_serving_chapter": chapter, "_serving_kc": kc_id, "_selection_kinds": kinds}
