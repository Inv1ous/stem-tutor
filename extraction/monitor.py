#!/usr/bin/env python3
"""Read-only extraction dashboard. Standard library only; Python 3.9+.

Run this file from any directory. Ctrl+C stops the monitor, never the workers.
See monitor.md for metric definitions and command options.
"""
import argparse
from collections import Counter, defaultdict
from datetime import datetime, timezone
import json
import math
from pathlib import Path
import re
import shutil
import sys
import textwrap
import time


COURSES = {
    "9701": "Chemistry", "9702": "Physics", "P1": "Pure 1", "P2": "Pure 2",
    "P3": "Pure 3", "P4": "Pure 4", "FP1": "Further Pure 1",
    "FP2": "Further Pure 2", "FP3": "Further Pure 3", "M1": "Mechanics 1",
    "D1": "Decision 1", "S1": "Statistics 1", "S2": "Statistics 2", "S3": "Statistics 3",
}
DEFAULT_RUN = "Work/Workers/extraction/all-course-20261101"


class JsonReader:
    """Cache unchanged JSON and tolerate a concurrent writer's partial file."""

    def __init__(self):
        self.cache = {}

    def read(self, path):
        path = Path(path)
        old = self.cache.get(path)
        try:
            stat = path.stat()
            stamp = (stat.st_mtime_ns, stat.st_size, stat.st_ino)
            if old and old[0] == stamp:
                return old[1], None
            data = json.loads(path.read_text(encoding="utf-8"))
            if not isinstance(data, dict):
                raise ValueError("expected a JSON object")
            after = path.stat()
            if stamp != (after.st_mtime_ns, after.st_size, after.st_ino):
                raise ValueError("changed during read")
            self.cache[path] = (stamp, data)
            return data, None
        except (OSError, ValueError) as error:
            fallback = "using last good value" if old else "unavailable"
            return old[1] if old else {}, f"{path.name}: {fallback} ({error})"


def percent(done, total):
    return 100 * done / total if total else None


def page_coverage(document):
    """Union full-scope baseline pages by stable source identity, not job count."""
    sources = {}
    for row in document.get("sources", []):
        key = (row["course"], row["source_id"], row["source_sha256"])
        total = row["total_pages"]
        if not isinstance(total, int) or total < 0:
            raise ValueError("invalid source page total")
        target = sources.setdefault(key, {"total": total, "inspected": set(), "reviewed": set()})
        if target["total"] != total:
            raise ValueError("conflicting page totals for one source identity")
        for field, name in [("maker_inspected_pages", "inspected"),
                            ("independently_reviewed_pages", "reviewed")]:
            pages = row[field]
            if any(not isinstance(p, int) or not 1 <= p <= total for p in pages):
                raise ValueError("out-of-range coverage page")
            target[name].update(pages)
    result = defaultdict(lambda: {"sources": 0, "total": 0, "inspected": 0, "reviewed": 0})
    for (course, _, _), row in sources.items():
        result[course]["sources"] += 1
        result[course]["total"] += row["total"]
        for name in ("inspected", "reviewed"):
            result[course][name] += len(row[name])
    return dict(result)


def number(value):
    return f"{value:,}" if isinstance(value, (int, float)) else "--"


def percentage(value):
    return f"{value:.1f}%" if value is not None else "--"


def age(timestamp):
    try:
        moment = datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
        if moment.tzinfo is None:
            return "unknown age"
        seconds = max(0, (datetime.now(timezone.utc) - moment).total_seconds())
        if seconds < 60:
            return f"{int(seconds)}s ago"
        if seconds < 3600:
            return f"{int(seconds // 60)}m ago"
        return f"{seconds / 3600:.1f}h ago"
    except (TypeError, ValueError, AttributeError):
        return "unknown age"


class Monitor:
    def __init__(self, root, run):
        self.root, self.run = Path(root), Path(run)
        self.reader = JsonReader()

    def current_practice(self, width):
        """Load the selected sealed release afresh, without reading media or attempts."""
        try:
            # Locate engine source from this script, independently of --root/cwd.
            source = str(Path(__file__).resolve().parents[1] / "src")
            if source not in sys.path:
                sys.path.insert(0, source)
            from tutorlib.source_practice import Collection

            collection = Collection(self.root / "STEM Tutor")
            rows = collection.questions()
            counts = defaultdict(Counter)
            for row in rows:
                grain = "topical" if row["id"].startswith("occurrence-") else "native"
                counts[row["course"]][grain] += 1
            topical = sum(row["topical"] for row in counts.values())
            lines = ["CURRENT LIBRARY SOURCE PRACTICE",
                     f"{len(rows):,} source-practice items | {len(rows) - topical:,} native paper-ID items | "
                     f"{topical:,} math topical occurrences",
                     f"{'Course':<22} {'Items':>7} {'Native':>7} {'Topical':>7}"]
            for course in dict.fromkeys([*COURSES, *counts]):
                row = counts[course]
                label = f"{course} {COURSES.get(course, '')}".strip() if width >= 80 else course
                lines.append(f"{label:<22} {sum(row.values()):>7,} {row['native']:>7,} {row['topical']:>7,}")
            lines += ["Native = paper-ID items; Topical = math source occurrences (may overlap papers).",
                      "Source/course completion denominator / ETA unknown; counts are not whole-PDF coverage.",
                      "Practice is separate from the old teaching bank; counts are not added (overlap unknown).",
                      f"Current immutable release: {Path(collection.release).name}"]
            return lines
        except (ImportError, OSError, ValueError, KeyError, TypeError, AttributeError) as error:
            # No cached success or zeros can masquerade as the selected release.
            return ["CURRENT LIBRARY SOURCE PRACTICE",
                    f"WARNING: Current source practice unavailable ({error})",
                    "Source/course completion denominator / ETA unknown."]

    def current_activity(self, read):
        """Choose by saved start time, rather than lexical run name or old budget."""
        latest = None
        for path in sorted((self.root / "Work/Workers/extraction").glob("*/run.json")):
            data = read(path)
            try:
                started = datetime.fromisoformat(data["started_at_utc"].replace("Z", "+00:00"))
                floor = data["stop_floor"]
                if (started.tzinfo is None or not isinstance(data.get("starting_current"), str)
                        or not re.fullmatch(r"Library/SourcePractice/Releases/[a-f0-9]{64}\.json", data["starting_current"])
                        or type(floor) not in (int, float) or not math.isfinite(floor) or not 0 <= floor <= 100):
                    continue
                if latest is None or started > latest[0]:
                    latest = (started, path, data)
            except (KeyError, TypeError, ValueError, AttributeError):
                continue
        if latest is None:
            return ["Saved current activity: unavailable (no valid source-practice run.json)"]
        _, path, data = latest
        observed = data.get("last_observed_at_utc")
        return [f"Saved current activity: {path.parent.name} | status: {data.get('status', 'unknown')}",
                f"Saved quota: {number(data.get('last_weekly_remaining'))}% weekly remaining | "
                f"{number(data['stop_floor'])}% stop floor | observed {age(observed)}",
                f"Saved run started {age(data['started_at_utc'])}; no usage API queried."]

    def render(self, width=120):
        warnings = []

        def read(path):
            data, warning = self.reader.read(path)
            if warning:
                warnings.append(warning)
            return data

        baseline = read(self.run / "all-source-progress.json")
        report = read(self.run / "continuation-report.json")
        checkpoint = read(self.run / "continuation-checkpoint.json")
        dispatch = read(self.run / "continuation-dispatch-state.json")
        try:
            coverage = page_coverage(baseline)
        except (KeyError, TypeError, ValueError) as error:
            coverage = {}
            warnings.append(f"Page coverage unavailable: {error}")
        per_course = report.get("per_course", {})
        totals = report.get("publication_counts", {})
        pending = report.get("pending_activated_counts", {})
        status = checkpoint.get("goal_status", "unknown")
        now = datetime.now().astimezone().strftime("%Y-%m-%d %H:%M:%S %Z")
        lines = [f"EXTRACTION MONITOR | {now}",
                 "Read-only | Ctrl+C stops this monitor | refreshes local records", ""]
        lines += self.current_practice(width)
        lines += self.current_activity(read)
        lines += ["", f"OLD TEACHING BANK CENSUS | saved status: {str(status).upper()}",
                 f"Old verified usable: {number(totals.get('whole_questions'))} whole questions | "
                 f"{number(totals.get('question_records'))} records/parts | {number(totals.get('marks'))} marks",
                 f"Separate pending output: {number(pending.get('whole_questions'))} awaiting full route verification"]
        if coverage:
            total = sum(r["total"] for r in coverage.values())
            inspected = sum(r["inspected"] for r in coverage.values())
            reviewed = sum(r["reviewed"] for r in coverage.values())
            lines.append(f"Old baseline source inspection: {percentage(percent(inspected, total))} "
                         f"({inspected:,}/{total:,} pages) | full-scope reviewed: {reviewed:,} pages")
        lines += ["", "OLD PAGE BASELINE BY COURSE (saved full-scope pages; not current question coverage)"]
        wide = width >= 110
        if wide:
            lines.append(f"{'Course':<22} {'Scan':>7} {'Pages inspected':>17} {'Review':>7} "
                         f"{'Usable Q':>8} {'Parts':>6} {'Marks':>6} {'Route wait':>10}")
        else:
            lines.append(f"{'Course':<6} {'Scan':>6} {'Pages':>14} {'Review':>6} "
                         f"{'Q':>4} {'Parts':>5} {'Marks':>5} {'Wait':>4}")
        for course in dict.fromkeys([*COURSES, *per_course, *coverage]):
            data, pages = per_course.get(course, {}), coverage.get(course)
            label = f"{course} {COURSES.get(course, '')}".strip()
            empty = data.get("source_shelf") == "empty"
            if not pages:
                lines.append(f"{label:<22} {'no sources' if empty else 'coverage unknown'}")
                continue
            scan = percentage(percent(pages["inspected"], pages["total"]))
            review = percentage(percent(pages["reviewed"], pages["total"]))
            page_count = f"{pages['inspected']:,}/{pages['total']:,}"
            whole = data.get("whole_questions")
            parts, marks = data.get("question_records"), data.get("marks")
            waiting = data.get("pending_activated_whole_questions")
            if wide:
                lines.append(f"{label:<22} {scan:>7} {page_count:>17} {review:>7} "
                             f"{number(whole):>8} {number(parts):>6} {number(marks):>6} {number(waiting):>10}")
            else:
                lines.append(f"{course:<6} {scan:>6} {page_count:>14} {review:>6} "
                             f"{number(whole):>4} {number(parts):>5} {number(marks):>5} {number(waiting):>4}")
        lines += ["", "Old baseline only: Scan = pages inspected by maker; Review = pages reviewed across full scope.",
                  "Selected-question reviews do not increase page-wide coverage. Usable Q = verified whole questions.",
                  "Question completion % / ETA unknown: raw records overlap and include parts; no reliable whole-question total."]
        registered = report.get("registered_this_continuation", {})
        lines.append(f"Registered: {number(registered.get('question_records'))} question records | "
                     f"{number(registered.get('diagram_records'))} diagrams | "
                     f"{number(registered.get('registered_media_resources'))} media resources")
        # State files are small; never load candidates, source PDFs or learner data.
        stages, unfinished = Counter(), []
        for path in sorted((self.root / "Work/Workers/extraction").glob("allsource*/state.json")):
            state = read(path)
            if not state:
                continue
            stages[state.get("stage", "unknown")] += 1
            for role, worker in state.get("jobs", {}).items():
                if worker.get("started") and not worker.get("finished"):
                    unfinished.append(f"{state.get('course', '?')} {role} | {state.get('name', path.parent.name)} "
                                      f"| PID {worker.get('pid', '?')} | started {age(worker['started'])}")
        held = Counter(c.get("status", "unknown") for c in dispatch.get("claims", [])
                       if c.get("status") in ("blocked", "blocked_metadata", "needs_diagnosis"))
        lines += ["", f"Live source states: {sum(stages.values())} jobs | "
                  + (", ".join(f"{k} {v}" for k, v in sorted(stages.items())) or "none found"),
                  f"Held question scopes: {sum(held.values())} | "
                  + (", ".join(f"{k} {v}" for k, v in sorted(held.items())) or "none recorded"),
                  f"Source workers recorded unfinished: {len(unfinished)} (saved status; PID liveness not verified)"]
        lines.extend("  " + item for item in unfinished[:6])
        if len(unfinished) > 6:
            lines.append(f"  ... {len(unfinished) - 6} more")
        lines.append("Coordinator/code-review agents are not measured by source-worker state files.")
        unit = checkpoint.get("current_code_unit")
        if unit and Path(unit).name == unit:
            freeze_name = unit.replace("implementation-plan.json", "build-freeze.json")
            if freeze_name != unit:
                freeze = read(self.run / freeze_name)
                lines.append(f"Code work: {unit.removesuffix('-implementation-plan.json')} | "
                             f"{freeze.get('status', 'see saved plan')}")
        lines += [f"Output census: {report.get('as_of', 'unknown')} ({age(report.get('as_of'))})",
                  f"Page baseline: {baseline.get('dispatched_at', 'unknown')} "
                  f"({age(baseline.get('dispatched_at'))}); frozen until coverage census is refreshed",
                  "Polling reads new records automatically; it does not run extraction, refresh censuses, or call paid APIs.",
                  f"Run: {self.run}"]
        if warnings:
            lines += ["", "DATA WARNINGS (values may be stale or unknown):", *warnings[:8]]
            if len(warnings) > 8:
                lines.append(f"... {len(warnings) - 8} more unreadable files")
        # Strip terminal control characters from values read from worker files.
        safe_lines = ["".join(c if c.isprintable() else " " for c in line) for line in lines]
        return "\n".join(textwrap.fill(line, width=max(30, width), subsequent_indent="  ",
                                       replace_whitespace=False) if line else "" for line in safe_lines)


def default_root():
    for directory in Path(__file__).resolve().parents:
        if (directory / DEFAULT_RUN).is_dir():
            return directory
    return Path.cwd()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=default_root(), help="Workspace root (auto-detected)")
    parser.add_argument("--run-dir", type=Path, help="Census directory; relative paths are relative to --root")
    parser.add_argument("--interval", type=float, default=5, help="Refresh seconds (default: 5; minimum: 1)")
    parser.add_argument("--once", action="store_true", help="Print one snapshot and exit")
    args = parser.parse_args()
    if not math.isfinite(args.interval) or args.interval < 1:
        parser.error("--interval must be a finite number of at least 1 second")
    root = args.root.expanduser().resolve()
    run = args.run_dir or Path(DEFAULT_RUN)
    run = (root / run.expanduser()).resolve()
    if not run.is_dir():
        parser.error(f"Extraction census directory not found: {run}")
    monitor = Monitor(root, run)
    interactive = sys.stdout.isatty() and not args.once
    try:
        if interactive:
            sys.stdout.write("\x1b[?1049h\x1b[?25l")
        while True:
            terminal = shutil.get_terminal_size((120, 40))
            frame = monitor.render(terminal.columns)
            if interactive:
                # Avoid scrolling the header off a short terminal on every poll.
                rows = frame.splitlines()
                if len(rows) >= terminal.lines:
                    hint = "More details: use --once or enlarge terminal. Ctrl+C exits."
                    frame = "\n".join(rows[:max(0, terminal.lines - 1)] + [hint[:terminal.columns]])
                sys.stdout.write("\x1b[H\x1b[2J")
            print(frame, flush=True)
            if args.once:
                return 0
            if not interactive:
                print("\n" + "-" * 40, flush=True)
            time.sleep(args.interval)
    except KeyboardInterrupt:
        return 0
    except BrokenPipeError:
        return 0
    finally:
        if interactive:
            sys.stdout.write("\x1b[?25h\x1b[?1049l")
            sys.stdout.flush()


if __name__ == "__main__":
    sys.exit(main())
