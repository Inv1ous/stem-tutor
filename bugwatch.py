#!/usr/bin/env python3
"""Run the repository's bug-watch board from the repository root."""
from pathlib import Path
import runpy


if __name__ == "__main__":
    runpy.run_path(str(Path(__file__).resolve().parent / "bugwatch" / "bugs.py"), run_name="__main__")
