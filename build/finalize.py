"""After a pack wave: append extra-tier past MCQs, mark cards already in Anki, re-validate and lint everything.

  python build/finalize.py            prints a summary; exit 1 if any pack or note fails
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "build"))
sys.path.insert(0, str(ROOT / "plugin/stem-tutor/skills/tutor/scripts"))
import add_past  # noqa: E402
import anki_existing  # noqa: E402
import validate_pack  # noqa: E402
from tutorlib import lint  # noqa: E402


def main() -> int:
    bad = 0
    rows = []
    for pack_path in sorted((ROOT / "build/out/packs").glob("*/*.json")):
        extras = add_past.add(pack_path)
        pack = json.loads(pack_path.read_text())
        graph = json.loads((ROOT / f"build/out/specs/{pack['spec']}/graph.json").read_text())
        errs = validate_pack.validate(pack, graph)
        note = ROOT / "build/out/notes" / pack["note"]
        lint_errs = lint.lint(note.read_text(), vault_root=ROOT / "build/out") if note.exists() else [{"rule": "missing-note"}]
        ok = not errs and not lint_errs
        bad += not ok
        rows.append({"sub": pack["subtopic"], "items": len(pack["items"]), "extra": extras,
                     "ok": ok, "errors": [e["rule"] for e in errs][:5], "note": [e["rule"] for e in lint_errs][:5]})
    marked = anki_existing.mark()
    print(json.dumps({"packs": len(rows), "failing": bad, "anki_marked": marked, "rows": rows}, indent=1))
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
