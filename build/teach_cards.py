"""Teach cards: one per syllabus point (KC), used by lesson mode (motivate → discover → establish → connect → note).

  python build/teach_cards.py check <subtopic>...   validate build/work/teach/<subtopic>.json
  python build/teach_cards.py merge <subtopic>...   validate, then write the valid cards into the pack as pack["teach"]
  python build/teach_cards.py merge <subtopic> --draft <teach.json> --pack <pack.json>   the same on Work copies

Card: {"motivate", "establish", "connect", "note", "self_explain", "discover"?: {"stem", "options": {A..D}, "answer",
"explanation"}}. Markdown with $...$ maths; must pass the Obsidian lint.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "plugin/stem-tutor/skills/tutor/scripts"))
from tutorlib import lint  # noqa: E402
from tutorlib.card_diagrams import valid_diagram_descriptions

LIMITS = {"motivate": 100, "establish": 400, "connect": 100, "self_explain": 80}


def words(s: str) -> int:
    return len(str(s).split())


def is_guided(card: dict) -> bool:
    """Any guided field opts a card into full validation, even when the draft is incomplete."""
    return any(key in card for key in ("plain_words", "terms", "forms", "diagrams", "misconceptions", "exam_language", "guided_discover"))


def check_card(kc: str, card: dict, *, guided: bool = False) -> list[str]:
    if not isinstance(card, dict):
        return [f"{kc}: card must be an object"]
    errs = []
    if 'disclosed_item_ids' in card:
        ids = card['disclosed_item_ids']
        if (not isinstance(ids, list) or any(not isinstance(i, str) or not i.strip() for i in ids)
                or len(set(ids)) != len(ids)):
            errs.append(f'{kc}: disclosed_item_ids must be a list of unique non-empty item IDs')
    for f in ("motivate", "establish", "connect", "note", "self_explain"):
        if not str(card.get(f, "")).strip():
            errs.append(f"{kc}: missing {f}")
    for f, n in LIMITS.items():
        if words(card.get(f, "")) > n:
            errs.append(f"{kc}: {f} has {words(card.get(f, ''))} words (max {n})")
    bullets = [l for l in str(card.get("note", "")).splitlines() if l.strip()]
    if not 2 <= len(bullets) <= 7 or not all(l.lstrip().startswith("- ") for l in bullets):
        errs.append(f"{kc}: note must be 2-7 lines each starting '- '")
    d = card.get("discover")
    if d:
        opts = d.get("options") if isinstance(d, dict) else None
        if (not isinstance(opts, dict) or set(opts) != {"A", "B", "C", "D"}
                or not isinstance(d.get("answer"), str) or d.get("answer") not in opts
                or not d.get("stem") or not d.get("explanation")):
            errs.append(f"{kc}: discover needs stem, options A-D, answer among them, explanation")
    for f in ("motivate", "establish", "connect", "note", "self_explain"):
        for x in lint.lint(str(card.get(f, ""))):
            errs.append(f"{kc}: {f} lint {x['rule']}: {x.get('message', '')}")
    if isinstance(d, dict) and isinstance(d.get("options"), dict):
        for part in [d.get("stem", ""), d.get("explanation", "")] + list((d.get("options") or {}).values()):
            for x in lint.lint(str(part)):
                errs.append(f"{kc}: discover lint {x['rule']}")
    if "guided_discover" in card:
        probe = card["guided_discover"]
        if (not isinstance(probe, dict) or not isinstance(probe.get("options"), dict)
                or set(probe["options"]) != {"A", "B", "C", "D"}
                or any(not isinstance(v, str) or not v.strip() for v in probe["options"].values())
                or not isinstance(probe.get("answer"), str) or probe["answer"] not in probe["options"]
                or any(not isinstance(probe.get(k), str) or not probe[k].strip() for k in ("stem", "explanation"))):
            errs.append(f"{kc}: guided_discover needs stem, options A-D, answer among them, explanation")
        else:
            for part in [probe["stem"], probe["explanation"], *probe["options"].values()]:
                for x in lint.lint(str(part)):
                    errs.append(f"{kc}: guided_discover lint {x['rule']}")
    if guided:
        def valid_rubric(rubric) -> bool:
            return isinstance(rubric, list) and bool(rubric) and all(
                isinstance(p, dict) and isinstance(p.get("point"), str) and p["point"].strip()
                and isinstance(p.get("keywords"), list) and p["keywords"]
                and all(isinstance(group, list) and group and all(isinstance(k, str) and k.strip() for k in group)
                        for group in p["keywords"]) for p in rubric)

        def lint_nested(path: str, value) -> None:
            if isinstance(value, str):
                errs.extend(f"{kc}: {path} lint {issue['rule']}: {issue.get('message', '')}" for issue in lint.lint(value))
            elif isinstance(value, list):
                for i, part in enumerate(value):
                    lint_nested(f"{path}[{i}]", part)
            elif isinstance(value, dict):
                for key, part in value.items():
                    if key not in ("source", "id"):
                        lint_nested(f"{path}.{key}", part)

        for field in ("plain_words", "terms", "forms", "misconceptions", "diagram_descriptions", "exam_language"):
            if field in card:
                lint_nested(field, card[field])
        if not isinstance(card.get("plain_words"), str) or not card["plain_words"].strip():
            errs.append(f"{kc}: missing plain_words")
        if "exam_language" in card:
            entries = card["exam_language"]
            if not isinstance(entries, list) or not entries or any(
                not isinstance(e, dict) or any(not isinstance(e.get(k), str) or not e[k].strip() for k in ("name", "meaning"))
                for e in entries
            ):
                errs.append(f"{kc}: exam_language needs names and meanings")
        for name, fields in (("terms", ("term", "meaning", "notation", "spoken", "source")),
                             ("forms", ("name", "example", "check", "answer", "source")),
                             ("misconceptions", ("id", "idea", "temptation", "fix"))):
            entries = card.get(name)
            if not isinstance(entries, list) or not entries:
                errs.append(f"{kc}: {name} must be a nonempty list")
                continue
            if name == "forms":
                names = [entry.get("name").strip() for entry in entries
                         if isinstance(entry, dict) and isinstance(entry.get("name"), str) and entry["name"].strip()]
                if len(names) != len(set(names)):
                    errs.append(f"{kc}: form names must be unique")
            for entry in entries:
                if not isinstance(entry, dict) or any(not isinstance(entry.get(f), str) or not entry[f].strip() for f in fields):
                    errs.append(f"{kc}: {name} entry needs {', '.join(fields)}")
                if name == "forms" and isinstance(entry, dict):
                    if (isinstance(entry.get("example"), str) and isinstance(entry.get("check"), str)
                            and entry["example"].strip() and entry["example"].strip() == entry["check"].strip()):
                        errs.append(f"{kc}: form example and check must be distinct")
                    if "review_rule" in entry and entry["review_rule"] not in ("consecutive_primes", "geometric_subtraction"):
                        errs.append(f"{kc}: unknown form review rule")
                    if "diagram" in entry:
                        diagram = entry["diagram"]
                        declared = card.get("diagrams")
                        if not isinstance(diagram, str) or not diagram.strip() or not isinstance(declared, list) or diagram not in declared:
                            errs.append(f"{kc}: form diagram must reference a declared card diagram")
                    wordings = entry.get("wordings")
                    if not isinstance(wordings, list) or not wordings or any(not isinstance(w, str) or not w.strip() for w in wordings):
                        errs.append(f"{kc}: forms entry needs question wordings")
                    rubric = entry.get("rubric")
                    if not valid_rubric(rubric):
                        errs.append(f"{kc}: forms entry needs a marking rubric with keyword groups")
                    if "retry" in entry:
                        retry = entry["retry"]
                        if isinstance(retry, dict) and 'review_rule' in retry and retry['review_rule'] != 'positive_pair':
                            errs.append(f"{kc}: unknown retry review rule")
                        if (not isinstance(retry, dict) or
                            any(not isinstance(retry.get(k), str) or not retry[k].strip() for k in ("check", "answer")) or
                            retry.get("check", "").strip() == str(entry.get("check", "")).strip() or
                            not valid_rubric(retry.get("rubric"))):
                            errs.append(f"{kc}: form retry needs a distinct check, answer and marking rubric")
        gaps = card.get("source_gaps")
        if gaps is not None and (not isinstance(gaps, list) or any(not isinstance(g, str) or not g.strip() for g in gaps)):
            errs.append(f"{kc}: source_gaps must list what the sources did not cover, one sentence each")
        diagrams = card.get("diagrams")
        if not isinstance(diagrams, list) or (not diagrams and not str(card.get("diagram_reason", "")).strip()):
            errs.append(f"{kc}: diagrams or a diagram_reason is required")
        if isinstance(diagrams, list) and diagrams:
            if not valid_diagram_descriptions(card):
                errs.append(f"{kc}: diagram_descriptions must describe every diagram")
    return errs


def identity_problems(sub: str, pack: dict, cards: dict) -> list[str]:
    """Refuse to write when either file belongs to another subtopic: a pack whose `subtopic` is not `sub`, or teach
    cards whose KC ids are not `sub`'s own (`<sub>.<n>`). A drafted chapter once had another chapter's cards in its
    teach file, so the check runs before any write, not only on the cards."""
    out = []
    if pack.get("subtopic") != sub:
        out.append(f"pack says subtopic {pack.get('subtopic')!r}, not {sub!r}")
    out += [f"teach card {kc!r} is not a KC of {sub}" for kc in cards if not kc.startswith(sub + ".")]
    return out


def load(sub: str, draft: Path | None = None, pack: Path | None = None) -> tuple[dict, Path, dict]:
    cards = json.loads((draft or ROOT / f"build/work/teach/{sub}.json").read_text())
    pack_path = pack or next((ROOT / "build/out/packs").glob(f"*/{sub}.json"))
    return cards, pack_path, json.loads(pack_path.read_text())


def merge_cards(existing: dict, staged: dict) -> dict:
    """Overlay validated cards without deleting omitted KCs or card fields.

    Supplied values, including lists, replace explicitly; correction/no-loss gates
    still decide whether those edits are authorized. Do not merge list entries:
    their positions and source/review bindings can carry identity.
    """
    merged = dict(existing)
    for kc, card in staged.items():
        merged[kc] = {**existing.get(kc, {}), **card, "source": "pack"}
    return merged


def _option(args: list[str], name: str) -> tuple[list[str], Path | None]:
    if name not in args:
        return args, None
    i = args.index(name)
    return args[:i] + args[i + 2:], Path(args[i + 1])


def main(cmd: str, subs: list[str]) -> int:
    # --draft/--pack: a refine pass edits Work copies, since the shared draft and pack can be read-only Library adapters
    subs, draft = _option(subs, "--draft")
    subs, pack_file = _option(subs, "--pack")
    if (draft or pack_file) and len(subs) != 1:
        raise SystemExit("--draft and --pack take exactly one subtopic")
    bad = 0
    for sub in subs:
        cards, pack_path, pack = load(sub, draft, pack_file)
        if cmd == "merge" and (pack_path.is_symlink() or "Library" in pack_path.resolve().parts):
            print(f"{sub}: REFUSED, author a Work copy instead of a Library resource or file adapter")
            bad += 1
            continue
        if identity := identity_problems(sub, pack, cards):
            print(f"{sub}: REFUSED, wrong subtopic:\n  - " + "\n  - ".join(identity))
            bad += 1
            continue
        graph = json.loads((ROOT / f"build/out/specs/{pack['spec']}/graph.json").read_text())
        kcs = [k["id"] for k in graph["kcs"] if k["subtopic"] == sub]
        errs = [f"{k}: no card" for k in kcs if k not in cards] + [f"{k}: not a KC of {sub}" for k in cards if k not in kcs]
        good = {}
        guided = any(is_guided(card) for card in cards.values())
        for kc, card in cards.items():
            e = check_card(kc, card, guided=guided)
            errs += e
            if not e and kc in kcs:
                good[kc] = {**card, "source": "pack"}
        print(f"{sub}: {len(good)}/{len(kcs)} valid" + ("".join("\n  - " + e for e in errs) if errs else ""))
        bad += len(errs)
        if cmd == "merge" and good and not (errs and guided):
            pack["teach"] = merge_cards(pack.get("teach") or {}, good)
            pack_path.write_text(json.dumps(pack, ensure_ascii=False, indent=1))
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1], sys.argv[2:]))
