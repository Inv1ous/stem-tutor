"""Make vendored pure-Python wheels importable without pip or network.

Wheels live in `../wheels/`. Each is unzipped once into a temp cache and put on sys.path.
"""
from __future__ import annotations

import importlib.util
import os
import sys
import tempfile
import types
import zipfile
from pathlib import Path

WHEELS = Path(__file__).resolve().parents[1] / "wheels"
CACHE = Path(os.environ.get("STEM_TUTOR_DEPS", Path(tempfile.gettempdir()) / "stem-tutor-deps"))

# import name -> wheel filename prefixes it needs
NEEDS = {
    "sympy": ["sympy-", "mpmath-"],
    "fsrs": ["fsrs-", "typing_extensions-"],
    "genanki": ["genanki-", "cached_property-", "chevron-", "frozendict-"],
}


def ensure(name: str) -> None:
    if importlib.util.find_spec(name) is None:
        for prefix in NEEDS.get(name, [name + "-"]):
            for wheel in sorted(WHEELS.glob(prefix + "*.whl")):
                target = CACHE / wheel.stem
                if not target.exists():
                    tmp = target.with_name(target.name + ".part")
                    with zipfile.ZipFile(wheel) as z:
                        z.extractall(tmp)
                    tmp.rename(target)
                if str(target) not in sys.path:
                    sys.path.insert(0, str(target))
        importlib.invalidate_caches()
    if name == "genanki" and importlib.util.find_spec("yaml") is None:
        # genanki imports yaml at module load but only uses it for string templates, which we never pass.
        sys.modules["yaml"] = types.ModuleType("yaml")
    if importlib.util.find_spec(name) is None:
        raise ImportError(f"{name} unavailable: no wheel in {WHEELS} and not installed")
