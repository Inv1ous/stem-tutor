"""Status events from the two append-only Bugwatch logs need calendar dates."""
import sys
from types import SimpleNamespace
from pathlib import Path
import re

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "bugwatch"))
import bugs
import post


@pytest.mark.parametrize(
    ("bugs_line", "fixes_line", "expected"),
    [
        ("- 2026-10-31 19:15 REOPEN B-003 · still fails",
         "- 2026-11-01 14:00 B-003 FIXED · regression test", "FIXED"),
        ("- 2026-11-01 14:00 REOPEN B-003 · still fails",
         "- 2026-10-31 19:15 B-003 FIXED · regression test", "REOPENED"),
    ],
)
def test_status_uses_calendar_order_across_bugwatch_logs(tmp_path, monkeypatch, bugs_line, fixes_line, expected):
    bug_log = tmp_path / "BUGS.md"
    fix_log = tmp_path / "FIXES.md"
    bug_log.write_text(
        "### B-003 · P2 · units.py · overflow\n"
        "- **Found:** 19:00 · **Method:** ran · **Confidence:** high\n"
        "- **Where:** units.py\n- **Repro:** probe\n- **Expected:** safe\n"
        "- **Actual:** crash\n- **Impact:** interrupted\n"
        f"{bugs_line}\n",
        encoding="utf-8",
    )
    fix_log.write_text(f"{fixes_line}\n", encoding="utf-8")
    monkeypatch.setattr(bugs, "BUGS", bug_log)
    monkeypatch.setattr(bugs, "FIXES", fix_log)
    monkeypatch.setattr(bugs, "QOL", tmp_path / "QOL.md")

    findings, events, problems, _ = bugs.load()
    assert not problems
    assert bugs.status_of("B-003", events) == expected
    assert "B-003" in findings


def test_legacy_undated_events_are_older_than_dated_events(tmp_path, monkeypatch):
    bug_log = tmp_path / "BUGS.md"
    fix_log = tmp_path / "FIXES.md"
    bug_log.write_text(
        "### B-003 · P2 · units.py · overflow\n"
        "- **Found:** 19:00 · **Method:** ran · **Confidence:** high\n"
        "- **Where:** units.py\n- **Repro:** probe\n- **Expected:** safe\n"
        "- **Actual:** crash\n- **Impact:** interrupted\n"
        "- 19:15 REOPEN B-003 · legacy entry\n"
        "- 2026-11-01 14:01 SWEEP · dated activity\n",
        encoding="utf-8",
    )
    fix_log.write_text("- 2026-11-01 14:00 B-003 FIXED · dated entry\n", encoding="utf-8")
    monkeypatch.setattr(bugs, "BUGS", bug_log)
    monkeypatch.setattr(bugs, "FIXES", fix_log)
    monkeypatch.setattr(bugs, "QOL", tmp_path / "QOL.md")

    _, events, problems, _ = bugs.load()
    assert not problems
    assert bugs.status_of("B-003", events) == "FIXED"
    assert "dated activity" in bugs.render(SimpleNamespace(check=False, unseen=False, all=True, watch=None))


def test_codex_verified_event_closes_its_own_finding_without_claude_fix_entry(tmp_path, monkeypatch):
    bug_log = tmp_path / "BUGS.md"
    bug_log.write_text(
        "### B-144 · P2 · report.py · confidence appears in answer\n"
        "- **Found:** 15:35 · **Method:** regression · **Confidence:** high\n"
        "- **Where:** report.py\n- **Repro:** create a session note\n- **Expected:** separate fields\n"
        "- **Actual:** confidence was appended\n- **Impact:** misstates the learner's answer\n"
        "- 2026-11-01 15:37 VERIFIED B-144 · independent review and regression passed\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(bugs, "BUGS", bug_log)
    monkeypatch.setattr(bugs, "FIXES", tmp_path / "FIXES.md")
    monkeypatch.setattr(bugs, "QOL", tmp_path / "QOL.md")

    findings, events, problems, _ = bugs.load()
    assert not problems
    assert bugs.status_of("B-144", events) == "VERIFIED"
    rendered_rows = bugs.render(SimpleNamespace(check=False, unseen=False, all=False, watch=None)).splitlines()
    assert not any(line.startswith("B-144 ") for line in rendered_rows)


def test_codex_rejected_event_closes_a_disproved_finding_without_claude_fix_entry(tmp_path, monkeypatch):
    bug_log = tmp_path / "BUGS.md"
    bug_log.write_text(
        "### B-133 · P3 · session.py · deliberate skip is mislabeled\n"
        "- **Found:** 15:35 · **Method:** runtime repro · **Confidence:** high\n"
        "- **Where:** session.py\n- **Repro:** skip a question\n- **Expected:** skip title\n"
        "- **Actual:** expected title appears\n- **Impact:** stale report\n"
        "- 2026-11-01 15:42 REJECTED B-133 · current path uses shared feedback card; reproduction contradicts report\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(bugs, "BUGS", bug_log)
    monkeypatch.setattr(bugs, "FIXES", tmp_path / "FIXES.md")
    monkeypatch.setattr(bugs, "QOL", tmp_path / "QOL.md")

    findings, events, problems, _ = bugs.load()
    assert not problems
    assert bugs.status_of("B-133", events) == "REJECTED"
    rendered_rows = bugs.render(SimpleNamespace(check=False, unseen=False, all=False, watch=None)).splitlines()
    assert not any(line.startswith("B-133 ") for line in rendered_rows)


def test_latest_activity_uses_dates_not_append_order(tmp_path, monkeypatch):
    bug_log = tmp_path / "BUGS.md"
    bug_log.write_text(
        "- 2026-11-01 14:05 SWEEP · newest\n"
        "- 2026-10-31 23:50 REPLY B-003 · older date\n"
        "- 2026-11-01 14:00 SWEEP · midday\n"
        "- 2026-11-01 13:00 REPLY B-003 · earlier\n"
        "- 2026-11-01 14:06 VERIFIED B-144 · confidence fix verified\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(bugs, "BUGS", bug_log)
    monkeypatch.setattr(bugs, "FIXES", tmp_path / "FIXES.md")
    monkeypatch.setattr(bugs, "QOL", tmp_path / "QOL.md")
    output = bugs.render(SimpleNamespace(check=False, unseen=False, all=True, watch=None))
    assert "older date" not in output
    assert output.index("earlier") < output.index("midday") < output.index("newest")
    assert output.index("newest") < output.index("VERIFIED B-144")


def test_all_board_uses_only_done_verified_or_rejected_terminal_labels(tmp_path, monkeypatch):
    bug_log = tmp_path / "BUGS.md"
    fix_log = tmp_path / "FIXES.md"
    qol_log = tmp_path / "QOL.md"
    finding = (
        "- **Found:** today\n- **Where:** module.py\n- **Repro:** run probe\n"
        "- **Expected:** works\n- **Actual:** fails\n- **Impact:** blocked\n"
    )
    bug_log.write_text(
        "### B-003 · P2 · module.py · fixed finding\n" + finding
        + "### B-004 · P2 · module.py · rejected finding\n" + finding
        + "- 2026-11-01 10:00 REJECTED B-004 · disproved\n"
        + "### B-005 · P2 · module.py · verified finding\n" + finding
        + "- 2026-11-01 10:01 VERIFIED B-005 · regression passes\n",
        encoding="utf-8",
    )
    fix_log.write_text(
        "- 2026-11-01 10:00 B-003 FIXED · test passes\n"
        "- 2026-11-01 10:01 Q-001 DONE · shipped\n"
        "- 2026-11-01 10:02 Q-002 DECLINED · duplicate\n",
        encoding="utf-8",
    )
    qol_log.write_text("### Q-001 · module.py · done\n### Q-002 · module.py · declined\n", encoding="utf-8")
    monkeypatch.setattr(bugs, "BUGS", bug_log)
    monkeypatch.setattr(bugs, "FIXES", fix_log)
    monkeypatch.setattr(bugs, "QOL", qol_log)

    output = bugs.render(SimpleNamespace(check=False, unseen=False, all=True, watch=None))

    assert "B-003  " in output and "DONE" in output
    assert "B-004  " in output and "REJECTED" in output
    assert "B-005  " in output and "VERIFIED" in output
    assert "Q-001  DONE" in output and "Q-002  REJECTED" in output
    assert "FIXED" not in output and "DECLINED" not in output


def test_post_main_accepts_qol_verdicts_and_board_shows_codex_activity(tmp_path, monkeypatch, capsys):
    bug_log = tmp_path / "BUGS.md"
    qol_log = tmp_path / "QOL.md"
    fix_log = tmp_path / "FIXES.md"
    lock = tmp_path / ".post.lock"
    qol_log.write_text(
        "### Q-001 · module.py · complete idea\n"
        "### Q-002 · module.py · declined idea\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(post, "BUGS", bug_log)
    monkeypatch.setattr(post, "QOL", qol_log)
    monkeypatch.setattr(post, "LOCK", lock)
    monkeypatch.setattr(bugs, "BUGS", bug_log)
    monkeypatch.setattr(bugs, "FIXES", fix_log)
    monkeypatch.setattr(bugs, "QOL", qol_log)

    assert post.main(["line", "DONE Q-001 · shipped and checked"]) == 0
    assert post.main(["line", "DECLINED Q-002 · duplicates existing behavior"]) == 0
    posted = capsys.readouterr().out
    assert posted.splitlines() == ["posted", "posted"]
    assert re.search(r"^- \d{4}-\d\d-\d\d \d\d:\d\d DONE Q-001 · shipped and checked$", bug_log.read_text(), re.M)
    assert re.search(r"^- \d{4}-\d\d-\d\d \d\d:\d\d DECLINED Q-002 · duplicates existing behavior$", bug_log.read_text(), re.M)

    output = bugs.render(SimpleNamespace(check=False, unseen=False, all=True, watch=None))
    assert "Q-001  DONE" in output and "Q-002  REJECTED" in output
    assert "DONE Q-001" in output and "DECLINED Q-002" in output


@pytest.mark.parametrize(
    ("fixes_line", "codex_line", "expected"),
    [
        ("- 2026-10-31 19:15 Q-001 DONE · Claude's older verdict", "- 2026-11-01 14:00 DONE Q-001 · Codex newer", "DONE"),
        ("- 2026-11-01 14:00 Q-001 DONE · Claude's newer verdict", "- 2026-10-31 19:15 DECLINED Q-001 · Codex older", "DONE"),
        ("- 2026-10-31 19:15 Q-001 DECLINED · Claude's older verdict", "- 2026-11-01 14:00 DONE Q-001 · Codex newer", "DONE"),
        ("- 2026-11-01 14:00 Q-001 DECLINED · Claude's newer verdict", "- 2026-10-31 19:15 DONE Q-001 · Codex older", "REJECTED"),
    ],
)
def test_qol_verdict_uses_newest_calendar_event_across_logs(tmp_path, monkeypatch, fixes_line, codex_line, expected):
    bug_log = tmp_path / "BUGS.md"
    fix_log = tmp_path / "FIXES.md"
    qol_log = tmp_path / "QOL.md"
    bug_log.write_text(codex_line + "\n", encoding="utf-8")
    fix_log.write_text(fixes_line + "\n", encoding="utf-8")
    qol_log.write_text("### Q-001 · module.py · idea\n", encoding="utf-8")
    monkeypatch.setattr(bugs, "BUGS", bug_log)
    monkeypatch.setattr(bugs, "FIXES", fix_log)
    monkeypatch.setattr(bugs, "QOL", qol_log)

    output = bugs.render(SimpleNamespace(check=False, unseen=False, all=True, watch=None))

    assert "Q-001  " + expected in output
    assert "LATEST ACTIVITY\n" in output
    assert codex_line[2:] in output
    assert not bugs.load()[2]


def test_generated_four_digit_qol_identifier_accepts_completion(tmp_path, monkeypatch):
    bug_log = tmp_path / 'BUGS.md'
    qol_log = tmp_path / 'QOL.md'
    qol_log.write_text('### Q-999 · module.py · prior idea\n', encoding='utf-8')
    monkeypatch.setattr(post, 'BUGS', bug_log)
    monkeypatch.setattr(post, 'QOL', qol_log)
    monkeypatch.setattr(post, 'LOCK', tmp_path / '.post.lock')
    identifier = post.next_id(qol_log, 'Q')
    assert identifier == 'Q-1000'

    assert post.main(['line', f'DONE {identifier} · completed and checked']) == 0
    assert f'DONE {identifier}' in bug_log.read_text()


def test_verified_qol_posts_updates_board_and_preserves_dated_order(tmp_path, monkeypatch, capsys):
    """Verified QOL must close an idea without hiding or rewriting its history."""
    bug_log = tmp_path / 'BUGS.md'
    fix_log = tmp_path / 'FIXES.md'
    qol_log = tmp_path / 'QOL.md'
    bug_log.write_text('- 2026-10-30 12:00 DONE Q-001 · implemented\n')
    fix_log.write_text('- 2026-10-31 12:00 Q-001 DONE · previous check\n')
    qol_log.write_text('### Q-001 · board · verified improvement\n')
    monkeypatch.setattr(post, 'BUGS', bug_log)
    monkeypatch.setattr(post, 'QOL', qol_log)
    monkeypatch.setattr(post, 'LOCK', tmp_path / '.post.lock')
    monkeypatch.setattr(bugs, 'BUGS', bug_log)
    monkeypatch.setattr(bugs, 'FIXES', fix_log)
    monkeypatch.setattr(bugs, 'QOL', qol_log)
    prior = bug_log.read_bytes()

    assert post.main(['line', 'VERIFIED Q-001 · fresh behavior check passed']) == 0
    assert capsys.readouterr().out == 'posted\n'
    assert bug_log.read_bytes().startswith(prior)
    assert bugs.qol_verdicts()['Q-001'] == 'VERIFIED'
    assert not bugs.load()[2]
    output = bugs.render(SimpleNamespace(check=False, unseen=False, all=True, watch=None))
    assert 'Q-001  VERIFIED' in output
    assert 'VERIFIED Q-001 · fresh behavior check passed' in output
    assert '0 open of 1' in output
    assert 'Q-001  VERIFIED' not in bugs.render(SimpleNamespace(check=False, unseen=False, all=False, watch=None))


@pytest.mark.parametrize('verb', ['VERIFIED', 'REJECTED'])
def test_qol_terminal_verdicts_win_only_when_newer(tmp_path, monkeypatch, verb):
    bug_log, fix_log, qol_log = (tmp_path / name for name in ('BUGS.md', 'FIXES.md', 'QOL.md'))
    bug_log.write_text(f'- 2026-11-01 14:00 {verb} Q-001 · checked\n')
    fix_log.write_text('- 2026-10-31 12:00 Q-001 DONE · implemented\n')
    qol_log.write_text('### Q-001 · board · improvement\n')
    monkeypatch.setattr(bugs, 'BUGS', bug_log)
    monkeypatch.setattr(bugs, 'FIXES', fix_log)
    monkeypatch.setattr(bugs, 'QOL', qol_log)
    assert bugs.qol_verdicts()['Q-001'] == verb
    assert not bugs.load()[2]
    assert f'Q-001  {verb}' in bugs.render(SimpleNamespace(check=False, unseen=False, all=True, watch=None))
    fix_log.write_text('- 2026-11-02 12:00 Q-001 DONE · later implementation\n')
    assert bugs.qol_verdicts()['Q-001'] == 'DONE'
