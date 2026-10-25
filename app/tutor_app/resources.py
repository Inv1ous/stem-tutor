"""System RAM, including memory held by the separate local model runtime."""
from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path


def ram_text() -> str:
    """Used/total RAM; inactive and speculative pages are available for reuse on macOS."""
    try:
        if sys.platform == "darwin":
            total = int(subprocess.run(["sysctl", "-n", "hw.memsize"], capture_output=True, text=True,
                                       check=True, timeout=2).stdout.strip())
            vm = subprocess.run(["vm_stat"], capture_output=True, text=True, check=True, timeout=2).stdout
            page = re.search(r"page size of (\d+) bytes", vm)
            pages = dict(re.findall(r"^(Pages (?:free|inactive|speculative)):\s+(\d+)\.", vm, re.M))
            if not page or len(pages) != 3:
                return "RAM unavailable"
            available = sum(int(value) for value in pages.values()) * int(page[1])
        elif sys.platform.startswith("linux"):
            memory = dict(re.findall(r"^(MemTotal|MemAvailable):\s+(\d+) kB", Path("/proc/meminfo").read_text(), re.M))
            total, available = int(memory["MemTotal"]) * 1024, int(memory["MemAvailable"]) * 1024
        else:
            return "RAM unavailable"
        if total <= 0 or not 0 <= available <= total:
            return "RAM unavailable"
        return f"RAM {(total - available) / 1024 ** 3:.1f}/{total / 1024 ** 3:.1f} GiB"
    except (OSError, ValueError, KeyError, subprocess.SubprocessError):
        return "RAM unavailable"
