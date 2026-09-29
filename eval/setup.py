"""Create one scratch vault per (persona, model) from the current build: python eval/setup.py <root> <model>..."""
import json
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "build"))
import publish  # noqa: E402

root = Path(sys.argv[1])
models = sys.argv[2:] or ["haiku", "opus"]
personas = json.loads((ROOT / "eval/personas.json").read_text())
out = []
for p in personas:
    for m in models:
        v = root / f"{p['id']}-{m}"
        shutil.rmtree(v, ignore_errors=True)
        publish.publish(v)
        out.append({"persona": p["id"], "model": m, "vault": str(v)})
print(json.dumps(out))
