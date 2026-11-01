"""Pre-pass baselines for the no-loss gate.

A refine pass must be compared with the chapter as it was before that pass changed anything. Two rules follow:

1. A new pass takes its snapshot when the pass starts (`begin_pass`), not later, so drafting or any other edit
   made before the refiner runs is never part of the baseline.
2. Snapshots are never overwritten silently: the one being replaced is archived under `history/<sub>/` with its
   provenance, and every event is appended to `history/<sub>/log.jsonl`.

When a chapter was edited before its snapshot could be taken, `reconstruct` rebuilds the pre-edit state from git
HEAD and the known additions, and refuses unless the two agree exactly, or the only leftover difference is listed.
"""
from __future__ import annotations

import copy
import hashlib
import json
import subprocess
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
GUIDED_TEACH_FIELDS = {"plain_words", "terms", "forms", "misconceptions", "source_gaps", "diagram_reason", "diagram_descriptions",
                       "diagrams", "exam_language", "guided_discover", "disclosed_item_ids"}


def _sha(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _git(*args: str) -> str:
    """Git's answer, or "" when git cannot be run. Git is provenance, not the baseline itself: a pass must still
    start (and say so in its record) when git is unavailable."""
    try:
        return subprocess.run(["git", *args], cwd=ROOT, capture_output=True, text=True).stdout
    except Exception:  # noqa: BLE001 - e.g. no git, or a test that replaces subprocess
        return ""


def provenance(pack_text: str, note_text: str, pack_rel: str) -> dict:
    head = _git("rev-parse", "HEAD").strip()
    committed = _git("show", f"HEAD:{pack_rel}")
    same = bool(committed) and json.loads(committed) == json.loads(pack_text)  # formatting does not count
    return {"pack_sha256": _sha(pack_text), "note_sha256": _sha(note_text), "git_head": head,
            "git_available": bool(head), "pack_matches_head": same}


def _history(snap_file: Path) -> Path:
    """History sits beside the snapshot it belongs to (the refine work folder, or a test's copy of it)."""
    return snap_file.parent / "history"


def _log(snap_file: Path, sub: str, event: dict) -> None:
    (_history(snap_file) / sub).mkdir(parents=True, exist_ok=True)
    with open(_history(snap_file) / sub / "log.jsonl", "a", encoding="utf-8") as f:
        f.write(json.dumps({"at": datetime.now().isoformat(timespec="seconds"), **event}, ensure_ascii=False) + "\n")


def archive(sub: str, snap_file: Path) -> str | None:
    """Keep a superseded snapshot. Returns the archive path, or None when there was nothing to keep."""
    if not snap_file.exists():
        return None
    (_history(snap_file) / sub).mkdir(parents=True, exist_ok=True)
    dest = _history(snap_file) / sub / f"snapshot.{datetime.now():%Y%m%d-%H%M%S-%f}.json"
    dest.write_bytes(snap_file.read_bytes())
    return str(dest)


def write_snapshot(sub: str, snap_file: Path, pack: dict, note: str, pass_no: int, reason: str,
                   pack_rel: str) -> dict:
    prov = provenance(json.dumps(pack, ensure_ascii=False, indent=1), note, pack_rel)
    old = archive(sub, snap_file)
    snap = {"pass": pass_no, "taken": datetime.now().isoformat(timespec="seconds"), "reason": reason,
            "provenance": prov, "pack": pack, "note": note}
    snap_file.parent.mkdir(parents=True, exist_ok=True)
    snap_file.write_text(json.dumps(snap, ensure_ascii=False), encoding="utf-8")
    _log(snap_file, sub, {"event": "snapshot", "pass": pass_no, "reason": reason, "archived_previous": old,
               "pack_matches_head": prov["pack_matches_head"], "git_head": prov["git_head"][:12]})
    return snap


def begin_pass(sub: str, snap_file: Path, pass_no: int, pack_rel: str, pack_file: Path, note_file: Path | None) -> dict:
    """Take the baseline for a new pass, before anything in the pass is edited."""
    pack_text = pack_file.read_text(encoding="utf-8")
    note = note_file.read_text(encoding="utf-8") if note_file and note_file.is_file() else ""
    snap = write_snapshot(sub, snap_file, json.loads(pack_text), note, pass_no,
                          reason="pass start (before any edit in this pass)", pack_rel=pack_rel)
    snap["note_bytes_sha256"] = hashlib.sha256(note_file.read_bytes() if note_file and note_file.is_file() else b"").hexdigest()
    snap_file.write_text(json.dumps(snap, ensure_ascii=False), encoding="utf-8")
    return snap


def _drafter_fields_only(cur_card: dict, head_card: dict | None) -> dict:
    """The card as it was before drafting: fields the drafter added are removed; legacy fields are kept as they are."""
    if head_card is None:
        return None
    return {k: v for k, v in cur_card.items() if k in head_card}


def _note_without_figures(head_note: str, cur_note: str, sub: str) -> str:
    """The note minus the blocks the drafter inserted. Each inserted block may hold only figure embeds, their
    *Figure:* captions and blank lines; anything else (a deletion, an edit, other text) is refused."""
    import difflib
    a, b = head_note.splitlines(), cur_note.splitlines()
    keep, sm = [], difflib.SequenceMatcher(None, a, b, autojunk=False)
    for tag, i1, i2, j1, j2 in sm.get_opcodes():
        if tag == "equal":
            keep += b[j1:j2]
        elif tag == "insert":
            block = b[j1:j2]
            if not all(not l.strip() or l.startswith("![[Assets/") or l.startswith("*Figure:") for l in block):
                raise ValueError(f"{sub}: note has inserted text beyond figure lines; not reconstructed")
        else:
            raise ValueError(f"{sub}: note has a {tag} of existing lines; not reconstructed")
    return "\n".join(keep) + ("\n" if cur_note.endswith("\n") else "")


def reconstruct(sub: str, pack_rel: str, guided_ids: set[str], pack_file: Path, note_file: Path | None,
                snap_file: Path, pass_no: int, reason: str) -> dict:
    """Rebuild the pre-draft pack and note from git HEAD plus the drafter additions, and verify the result.

    Refuses (raises ValueError with the differences) when the current pack, minus the additions, is not exactly
    the committed pack: that would mean a change was made outside the drafting, and it is not in the baseline."""
    cur = json.loads(pack_file.read_text(encoding="utf-8"))
    head_text = _git("show", f"HEAD:{pack_rel}")
    if not head_text:
        raise ValueError(f"{sub}: no committed version of {pack_rel}; baseline cannot be reconstructed")
    head = json.loads(head_text)
    pre = copy.deepcopy(cur)
    if "guided_forms" not in head:
        pre.pop("guided_forms", None)
    head_ids = {m["id"] for m in head.get("misconceptions", [])}
    added_mis = [m["id"] for m in pre.get("misconceptions", []) if m["id"] not in head_ids]
    pre["misconceptions"] = [m for m in pre.get("misconceptions", []) if m["id"] in head_ids]
    for kc, card in (pre.get("teach") or {}).items():
        hc = (head.get("teach") or {}).get(kc)
        if hc is None:
            raise ValueError(f"{sub}: teach card {kc} is new, but drafting only extends existing cards")
        extra = set(card) - set(hc)
        if extra - GUIDED_TEACH_FIELDS:
            raise ValueError(f"{sub}: {kc} gained non-guided fields {sorted(extra - GUIDED_TEACH_FIELDS)}")
        for k in extra:
            del card[k]
    if added_mis:
        # every appended misconception must be referenced by a drafted card, or it is not a drafter addition
        referenced = {m.get("id") for c in (cur.get("teach") or {}).values() for m in c.get("misconceptions", [])}
        unexplained = [i for i in added_mis if i not in referenced]
        if unexplained:
            raise ValueError(f"{sub}: misconceptions {unexplained} are not referenced by any drafted card")
    if pre != head:
        diffs = [k for k in set(pre) | set(head) if pre.get(k) != head.get(k)]
        raise ValueError(f"{sub}: pre-draft pack differs from git HEAD in {sorted(diffs)}; not reconstructed")
    note_now = note_file.read_text(encoding="utf-8") if note_file and note_file.is_file() else ""
    note_pre = note_now
    head_note = _git("show", f"HEAD:build/out/notes/{head.get('note', '')}")
    if head_note and note_now != head_note:
        note_pre = _note_without_figures(head_note, note_now, sub)
    snap = write_snapshot(sub, snap_file, head, note_pre, pass_no,
                          reason=f"reconstructed from git HEAD ({reason}); drafter additions removed and verified",
                          pack_rel=pack_rel)
    return snap
