import sys
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parents[1] / "plugin/stem-tutor/skills/tutor/scripts"
sys.path.insert(0, str(SCRIPTS))
import sys, pathlib; sys.path.insert(0, str(pathlib.Path(__file__).parent))
