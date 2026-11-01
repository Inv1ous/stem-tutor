"""True time and session time. Asked by the learner: true time keeps ticking even after the terminal is closed; session time is
the real time spent on the screen. And the time studied for the day."""
import json
import sys
import pytest
from pathlib import Path
from types import SimpleNamespace

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "plugin/stem-tutor/skills/tutor/scripts"))
from tutorlib import clock  # noqa: E402


def test_formats():
    assert clock.fmt(0) == "0 min" and clock.fmt(59) == "0 min" and clock.fmt(18 * 60 + 42) == "18 min"
    assert clock.fmt(3600 + 5 * 60) == "1 h 05 min" and clock.fmt(7 * 3600) == "7 h 00 min"
    assert clock.fmt(18 * 60 + 42, True) == "18:42" and clock.fmt(3600 + 5 * 60 + 9, True) == "1:05:09"


def test_the_clock_adds_to_the_day_and_the_session_and_remembers_across_runs(tmp_path):
    vault = SimpleNamespace(tutor=tmp_path / ".tutor")
    c = clock.StudyClock(vault)
    c.add("2026-10-19", 60, "s1")
    c.add("2026-10-19", 30, "s2")
    c.add("2026-10-19", 15, "s1")
    c.add("2026-10-19", 0, "s1")  # nothing to add
    assert c.today("2026-10-19") == 105 and c.session("s1") == 75 and c.sessions_on("2026-10-19") == 2
    assert not (tmp_path / ".tutor/state/time.json").exists()  # kept in memory until flushed
    c.flush()
    again = clock.StudyClock(vault)  # the terminal was closed and opened: session time carries on from where it was
    assert again.today("2026-10-19") == 105 and again.session("s1") == 75 and again.today("2026-10-20") == 0
    again.add("2026-10-19", 5, "s1")
    assert again.session("s1") == 80


def test_a_damaged_file_starts_the_count_again_and_old_days_are_dropped(tmp_path):
    vault = SimpleNamespace(tutor=tmp_path / ".tutor")
    (tmp_path / ".tutor/state").mkdir(parents=True)
    (tmp_path / ".tutor/state/time.json").write_text("{not json")
    c = clock.StudyClock(vault)
    assert c.today("2026-10-19") == 0
    for i in range(130):
        c.add(f"2026-{1 + i // 28:02d}-{1 + i % 28:02d}", 10, f"s{i}")
    c.flush()
    saved = json.loads((tmp_path / ".tutor/state/time.json").read_text())
    assert len(saved["days"]) == clock.KEEP_DAYS and "2026-01-01" not in saved["days"]
    assert set(saved["day_sessions"]) <= set(saved["days"])


@pytest.mark.parametrize('field', ['days', 'sessions', 'day_sessions'])
def test_scalar_clock_bucket_recovers_without_writing_damaged_history(tmp_path, field):
    vault = SimpleNamespace(tutor=tmp_path / '.tutor')
    path = vault.tutor / 'state/time.json'
    path.parent.mkdir(parents=True)
    original = json.dumps({field: 42}).encode()
    path.write_bytes(original)
    c = clock.StudyClock(vault)
    assert c.today('2026-11-01') == 0
    assert c.session('s1') == 0
    assert c.sessions_on('2026-11-01') == 0
    c.flush()
    assert path.read_bytes() == original
    c.add('2026-11-01', 10, 's1')
    assert c.today('2026-11-01') == 10


@pytest.mark.parametrize('bad', ['broken', [], {}, True, -2, float('nan'), float('inf')])
def test_invalid_clock_values_preserve_valid_counters_and_load_without_writes(tmp_path, bad):
    vault = SimpleNamespace(tutor=tmp_path / '.tutor')
    path = vault.tutor / 'state/time.json'
    path.parent.mkdir(parents=True)
    original = json.dumps({'days': {'2026-11-01': bad, '2026-10-31': 23},
                           'sessions': {'broken': bad, 'valid': 12},
                           'day_sessions': {'2026-11-01': 42, '2026-10-31': ['valid']}}).encode()
    path.write_bytes(original)
    c = clock.StudyClock(vault)
    assert c.today('2026-11-01') == 0
    assert c.today('2026-10-31') == 23
    assert c.session('broken') == 0
    assert c.session('valid') == 12
    assert c.sessions_on('2026-11-01') == 0
    assert c.sessions_on('2026-10-31') == 1
    c.flush()
    assert path.read_bytes() == original
    c.add('2026-11-01', 10, 'fresh')
    assert c.today('2026-11-01') == 10


def test_invalid_clock_bucket_does_not_discard_other_valid_buckets(tmp_path):
    vault = SimpleNamespace(tutor=tmp_path / '.tutor')
    path = vault.tutor / 'state/time.json'
    path.parent.mkdir(parents=True)
    path.write_text(json.dumps({'days': 42, 'sessions': {'saved': 30},
                               'day_sessions': {'2026-11-01': ['saved']}}))
    c = clock.StudyClock(vault)
    assert c.session('saved') == 30
    assert c.sessions_on('2026-11-01') == 1

