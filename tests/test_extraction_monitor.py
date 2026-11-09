"""The monitor must not turn partial extraction evidence into completion."""
import importlib.util
import io
import json
from pathlib import Path
import subprocess
import sys
import tempfile
from unittest.mock import patch
import unittest


from library_assets import copy_to_vault


BASE_RELEASE = "Library/SourcePractice/Releases/faba5b65f17ff95a345504acf4d9cc8ce94394b5c2394e513d492550cd2007cb.json"
NEW_RELEASE = "Library/SourcePractice/Releases/c5aa9002dc08029f606c8ceda5f71838fc10f162a90ac54e3b17f8678e5fe03c.json"


MODULE = Path(__file__).resolve().parents[1] / "extraction" / "monitor.py"


class MonitorTests(unittest.TestCase):
    def load(self):
        self.assertTrue(MODULE.exists(), "The terminal monitor has not been implemented")
        spec = importlib.util.spec_from_file_location("extraction_monitor", MODULE)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module

    def install_release(self, root, reference):
        vault = root / "STEM Tutor"
        vault.mkdir(exist_ok=True)
        copy_to_vault(reference, vault)
        pointer = vault / ".tutor/source_practice/CURRENT"
        pointer.parent.mkdir(parents=True, exist_ok=True)
        pointer.write_text(reference + "\n")
        return vault, pointer

    def test_current_registered_release_refreshes_before_old_page_baseline(self):
        # Removing Collection reads would hide new practice; adding old bank totals
        # to this count would turn 4,071 into a false combined total.
        monitor = self.load()
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory).resolve()
            run = root / "Work/Workers/extraction/old"
            run.mkdir(parents=True)
            (run / "continuation-report.json").write_text(json.dumps({
                "publication_counts": {"whole_questions": 3, "question_records": 4, "marks": 12}}))
            self.install_release(root, BASE_RELEASE)
            dashboard = monitor.Monitor(root, run)
            first = dashboard.render(120)
            self.assertIn("3,697 source-practice items", first)
            self.assertIn("3,234 native paper-ID", first)
            self.assertIn("463 math topical occurrences", first)
            for course in ("FP1", "FP2", "FP3"):
                self.assertRegex(first, rf"(?m)^{course} .*\s0\s+0\s+0$")
            self.install_release(root, NEW_RELEASE)
            second = dashboard.render(120)
            self.assertIn("4,071 source-practice items", second)
            self.assertIn("3,459 native paper-ID", second)
            self.assertIn("612 math topical occurrences", second)
            self.assertIn("3 whole questions", second)
            self.assertNotIn("4,074", second)
            current = second.split("OLD PAGE BASELINE", 1)[0]
            for course in monitor.COURSES:
                self.assertRegex(current, rf"(?m)^{course} ")
            self.assertLess(second.index("CURRENT LIBRARY SOURCE PRACTICE"), second.index("OLD PAGE BASELINE"))
            self.assertIn("completion denominator / ETA unknown", current)
            self.assertIn("not added", second)

    def test_missing_corrupt_and_changed_release_never_claim_zero_success(self):
        monitor = self.load()
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory).resolve()
            dashboard = monitor.Monitor(root, root / "old")
            self.assertIn("Current source practice unavailable", dashboard.render())
            vault, pointer = self.install_release(root, BASE_RELEASE)
            self.assertIn("3,697 source-practice items", dashboard.render())
            pointer.write_text("Library/SourcePractice/Releases/")
            invalid = dashboard.render()
            self.assertIn("Current source practice unavailable", invalid)
            self.assertNotIn("0 source-practice items", invalid)
            pointer.write_text(BASE_RELEASE)
            (vault / BASE_RELEASE).write_text("{}")
            corrupt = dashboard.render()
            self.assertIn("Current source practice unavailable", corrupt)
            self.assertIn("digest mismatch", corrupt)
            self.assertNotIn("3,697 source-practice items", corrupt)

    def test_latest_saved_current_activity_replaces_old_reset_budget(self):
        monitor = self.load()
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory).resolve()
            extraction = root / "Work/Workers/extraction"
            run = extraction / "old"
            run.mkdir(parents=True)
            (run / "budget-continuation.json").write_text(json.dumps({
                "current_reading": {"weekly_remaining": 69},
                "redemption": {"consumed_earned_resets": 1}}))
            for name, started, remaining in (("z-older", "2026-11-04T12:00:00Z", 32),
                                               ("a-current", "2026-11-05T12:00:00Z", 19)):
                activity = extraction / name / "run.json"
                activity.parent.mkdir()
                activity.write_text(json.dumps({"started_at_utc": started,
                    "starting_current": BASE_RELEASE, "stop_floor": 10,
                    "last_weekly_remaining": remaining, "status": "running\x1b[31m\x9b2J\x7f",
                    "last_observed_at_utc": started, "no_further_resets": True}))
            invalid = extraction / "new-invalid" / "run.json"
            invalid.parent.mkdir()
            invalid.write_text(json.dumps({"started_at_utc": "2026-11-06T12:00:00Z",
                "starting_current": BASE_RELEASE, "stop_floor": "broken"}))
            dashboard = monitor.Monitor(root, run)
            rendered = dashboard.render()
            self.assertIn("Saved current activity", rendered)
            self.assertIn("19% weekly remaining", rendered)
            self.assertIn("10% stop floor", rendered)
            self.assertIn("a-current", rendered)
            self.assertNotIn("69%", rendered)
            self.assertNotIn("resets consumed", rendered)
            self.assertNotIn("\x1b", rendered)
            self.assertNotIn("\x9b", rendered)
            self.assertNotIn("\x7f", rendered)
            self.assertIn("ago", rendered)
            current = extraction / "a-current/run.json"
            data = json.loads(current.read_text())
            data["last_weekly_remaining"] = 17
            current.write_text(json.dumps(data))
            self.assertIn("17% weekly remaining", dashboard.render())
            current.write_text('{"last_weekly_remaining":')
            stale = dashboard.render()
            self.assertIn("17% weekly remaining", stale)
            self.assertIn("last good", stale)

    def test_standalone_once_from_other_directory_and_interval_validation(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory).resolve()
            self.install_release(root, NEW_RELEASE)
            (root / "custom-census").mkdir()
            command = [sys.executable, "-I", str(MODULE), "--root", str(root),
                       "--run-dir", "custom-census", "--once", "--interval", "1"]
            result = subprocess.run(command, cwd=root, capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn("4,071 source-practice items", result.stdout)
            self.assertNotIn("\x1b", result.stdout)
            self.assertIn(str(root / "custom-census"), result.stdout)
            invalid = subprocess.run(command[:-1] + ["nan"], cwd=root, capture_output=True, text=True)
            self.assertEqual(invalid.returncode, 2)
            self.assertIn("finite number", invalid.stderr)

    def test_polling_ctrl_c_restores_terminal_and_non_tty_has_no_controls(self):
        import os
        monitor = self.load()
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory).resolve()
            self.install_release(root, NEW_RELEASE)
            (root / "old").mkdir()
            for interactive in (False, True):
                class Output(io.StringIO):
                    def isatty(self):
                        return interactive
                output = Output()
                args = [str(MODULE), "--root", str(root), "--run-dir", "old", "--interval", "1"]
                with patch.object(sys, "argv", args), patch.object(sys, "stdout", output), \
                        patch.object(monitor.time, "sleep", side_effect=KeyboardInterrupt), \
                        patch.object(monitor.shutil, "get_terminal_size", return_value=os.terminal_size((80, 40))):
                    self.assertEqual(monitor.main(), 0)
                rendered = output.getvalue()
                self.assertIn("4,071 source-practice items", rendered)
                self.assertIn("S3 Statistics 3", rendered)
                if interactive:
                    self.assertTrue(rendered.endswith("\x1b[?25h\x1b[?1049l"))
                else:
                    self.assertNotIn("\x1b", rendered)

    def test_current_collection_reads_only_metadata_and_writes_nothing(self):
        import os
        monitor = self.load()
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory).resolve()
            self.install_release(root, NEW_RELEASE)
            before = {p.relative_to(root): p.read_bytes() for p in root.rglob("*") if p.is_file()}
            original_open = os.open
            def read_only_open(path, flags, *args, **kwargs):
                self.assertFalse(flags & (os.O_WRONLY | os.O_RDWR | os.O_CREAT | os.O_TRUNC))
                name = str(path).lower()
                self.assertFalse(name.endswith(".pdf"))
                self.assertNotIn(Path(name).name, {"attempts", "events", "answers", "grades"})
                return original_open(path, flags, *args, **kwargs)
            with patch("os.open", side_effect=read_only_open):
                rendered = monitor.Monitor(root, root / "old").render(80)
            self.assertIn("4,071 source-practice items", rendered)
            after = {p.relative_to(root): p.read_bytes() for p in root.rglob("*") if p.is_file()}
            self.assertEqual(before, after)

    def test_coverage_unions_pages_and_does_not_count_question_reviews(self):
        monitor = self.load()
        source = {"course": "P1", "source_id": "asset:example", "source_sha256": "abc",
                  "total_pages": 10, "maker_inspected_pages": [1, 2, 2],
                  "independently_reviewed_pages": [1]}
        overlap = {**source, "maker_inspected_pages": [2, 3]}
        rows = monitor.page_coverage({"sources": [source, overlap]})
        self.assertEqual(rows["P1"], {"sources": 1, "total": 10, "inspected": 3, "reviewed": 1})
        self.assertIsNone(monitor.percent(0, 0))
        with self.assertRaises(ValueError):
            monitor.page_coverage({"sources": [{**source, "maker_inspected_pages": [11]}]})

    def test_partial_json_keeps_last_good_read_and_recovers(self):
        monitor = self.load()
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "input.json"
            cache = monitor.JsonReader()
            path.write_text('{"count": 3}')
            self.assertEqual(cache.read(path)[0], {"count": 3})
            path.write_text('{"count":')
            data, warning = cache.read(path)
            self.assertEqual(data, {"count": 3})
            self.assertIn("last good", warning)
            path.write_text('{"count": 15}')
            self.assertEqual(cache.read(path), ({"count": 15}, None))

    def test_live_changes_refresh_and_pending_questions_stay_separate(self):
        monitor = self.load()
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory).resolve()
            run = root / "Work/Workers/extraction/all-course-20261101"
            run.mkdir(parents=True)
            documents = {
                "all-source-progress.json": {"sources": []},
                "continuation-report.json": {"as_of": "2026-11-03T22:30:00+00:00",
                    "per_course": {"P1": {"whole_questions": 3, "question_records": 4,
                        "marks": 12, "raw_current_question_records": 859},
                        "FP2": {"source_shelf": "empty"}},
                    "publication_counts": {"whole_questions": 3, "question_records": 4, "marks": 12},
                    "pending_activated_counts": {"whole_questions": 5}},
                "continuation-checkpoint.json": {"goal_status": "paused"},
                "budget-continuation.json": {"phase": "post_reset", "current_reading": {
                    "weekly_remaining": 69, "observed_at": "2026-11-03T22:36:25+00:00"},
                    "redemption": {"consumed_earned_resets": 1}},
                "continuation-dispatch-state.json": {"claims": []},
            }
            for name, data in documents.items():
                (run / name).write_text(json.dumps(data))
            monitor_instance = monitor.Monitor(root, run)
            first = monitor_instance.render(120)
            self.assertIn("PAUSED", first)
            self.assertIn("3 whole", first)
            self.assertIn("5 awaiting", first)
            self.assertIn("FP2", first)
            self.assertIn("no sources", first)
            self.assertIn("saved", first)
            documents["continuation-report.json"]["publication_counts"]["whole_questions"] = 8
            (run / "continuation-report.json").write_text(json.dumps(documents["continuation-report.json"]))
            self.assertIn("8 whole", monitor_instance.render(80))
            self.assertNotIn("\x1b", monitor_instance.render(80))
            self.assertEqual(set(p.name for p in run.iterdir()), set(documents))

    def test_unfinished_worker_is_reported_without_claiming_pid_is_live(self):
        monitor = self.load()
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory).resolve()
            run = root / "Work/Workers/extraction/all-course-20261101"
            run.mkdir(parents=True)
            state = run.parent / "allsource-test" / "state.json"
            state.parent.mkdir()
            state.write_text(json.dumps({"name": "allsource-test", "course": "P1", "stage": "extracting",
                "jobs": {"extract": {"pid": 123, "started": "2026-11-03T20:00:00Z"}}}))
            text = monitor.Monitor(root, run).render(100)
            self.assertIn("unfinished", text)
            self.assertIn("allsource-test", text)
            state.write_text(json.dumps({"name": "allsource-test", "course": "P1", "stage": "pending",
                "jobs": {"extract": {"pid": 123, "finished": "2026-11-03T21:00:00Z"}}}))
            self.assertNotIn("allsource-test", monitor.Monitor(root, run).render(100))


if __name__ == "__main__":
    unittest.main()
