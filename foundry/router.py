"""Which allowance pays for each foundry job, and which model does it.

Two allowances pay for the foundry: Claude (the `claude` command) and Codex (the `codex` command). Each has usage
windows, a short one and a weekly one. Before every job the foundry reads what is left of each and sends the job to
the allowance with the most of its longest window left per hour until that window resets. With equal reset times
that is simply the one with more left, so the two are levelled and then run out together, whichever started with
less; when one resets sooner, what would be lost at its reset is used first.

Two things come before that rule. The blind roles (solver, tiebreak) never run on the family that drafted the
chapter, or a wrong answer key would be confirmed by the AI that wrote it. And each role runs on the cheapest tier of
its ladder that has not failed it twice running.
"""
from __future__ import annotations

import json
import os
import select
import subprocess
import time
from datetime import datetime
from pathlib import Path

PROVIDERS = ("codex", "claude")  # when the two are level, Codex takes the job
NAMES = {"codex": "Codex", "claude": "Claude"}
BLIND = ("solver", "tiebreak")
MINUTES = {"five_hour": 300, "seven_day": 10080}
RATE = {"five_hour": 6.0, "seven_day": 1.0}  # percent of a Claude window per dollar of work, until it has been learned
LIMIT_WORDS = ("usage limit", "rate limit", "limit reached", "session limit", "weekly limit")
UNKNOWN = -1.0


class Wait(SystemExit):
    """No allowance can take the job now: a slot has to free up or a window has to reset."""


# ---------------- reading the allowances ----------------
def codex_usage(binary: str, timeout: float = 20) -> dict | None:
    """Codex's windows from its app server, which costs nothing: {"five_hour": {"used": 29.0, "resets": 1790953291},
    "seven_day": {…}}. None when it cannot be asked."""
    ask = "".join(json.dumps(m) + "\n" for m in (
        {"jsonrpc": "2.0", "id": 1, "method": "initialize",
         "params": {"clientInfo": {"name": "stem-tutor-foundry", "title": "Foundry", "version": "1"}}},
        {"jsonrpc": "2.0", "method": "initialized"},
        {"jsonrpc": "2.0", "id": 2, "method": "account/rateLimits/read"}))
    try:
        proc = subprocess.Popen([binary, "app-server"], stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                                stderr=subprocess.DEVNULL, bufsize=0)
    except OSError:
        return None
    try:
        proc.stdin.write(ask.encode())
        fd, buf, end = proc.stdout.fileno(), b"", time.time() + timeout
        while time.time() < end and select.select([fd], [], [], max(0.0, end - time.time()))[0]:
            chunk = os.read(fd, 65536)
            if not chunk:
                break
            *lines, buf = (buf + chunk).split(b"\n")
            for line in lines:
                try:
                    msg = json.loads(line)
                except ValueError:
                    continue
                if isinstance(msg, dict) and msg.get("id") == 2:
                    limits = (msg.get("result") or {}).get("rateLimits") or {}
                    names = {v: k for k, v in MINUTES.items()}
                    return {names.get(w.get("windowDurationMins"), f"{w.get('windowDurationMins')}m"):
                            {"used": float(w["usedPercent"]), "resets": w.get("resetsAt")}
                            for w in (limits.get("primary"), limits.get("secondary")) if w} or None
    except (OSError, ValueError, KeyError, TypeError):
        return None
    finally:
        proc.kill()
        proc.wait()
    return None


def claude_cache(path: Path) -> tuple[dict, float]:
    """What Claude Code last fetched about its own limits (it refreshes this when a session starts): the windows in
    force, and when they were read. Nothing when the file is not there or has another shape."""
    try:
        cached = json.loads(Path(path).read_text())["cachedUsageUtilization"]
        windows = {}
        for lim in cached["utilization"].get("limits") or []:
            if lim.get("is_active") and lim.get("percent") is not None:
                name = {"session": "five_hour", "weekly_all": "seven_day"}.get(lim.get("kind"), str(lim.get("kind")))
                resets = lim.get("resets_at")
                windows[name] = {"used": float(lim["percent"]),
                                 "resets": datetime.fromisoformat(resets).timestamp() if resets else None}
        return windows, cached["fetchedAtMs"] / 1000
    except (OSError, ValueError, KeyError, TypeError, AttributeError):
        return {}, 0.0


LEAN = ["--output-format", "stream-json", "--verbose", "--safe-mode", "--disable-slash-commands", "--strict-mcp-config",
        "--setting-sources", "", "--no-session-persistence"]  # none of the learner's plugins, skills, hooks or servers


def claude_probe(binary: str, timeout: float = 90) -> dict:
    """Ask Claude for one word on its smallest model with everything switched off (a fraction of a cent): every run is
    told how much of the allowance is used, and nothing else reports it. The same facts as `claude_log`."""
    try:
        res = subprocess.run([binary, "-p", "Reply with the single word: ok", "--model", "haiku", *LEAN, "--tools", ""],
                             stdin=subprocess.DEVNULL, capture_output=True, text=True, timeout=timeout,
                             env={**os.environ, "CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC": "1"})
    except (OSError, subprocess.SubprocessError):
        return claude_events("")
    return claude_events(res.stdout)


def claude_log(path: Path) -> dict:
    """What a finished Claude worker's output says: its report, what it cost in dollars, the window it was told about,
    and whether it ran into a limit."""
    try:
        return claude_events(Path(path).read_text(errors="ignore"))
    except OSError:
        return claude_events("")


def claude_events(text: str) -> dict:
    out: dict = {"report": {}, "cost": 0.0, "windows": {}, "limit": False}
    for line in text.splitlines():
        try:
            e = json.loads(line)
        except ValueError:
            continue
        if not isinstance(e, dict):
            continue
        if e.get("type") == "rate_limit_event":
            info = e.get("rate_limit_info") or {}
            rejected = info.get("status") == "rejected"
            out["limit"] = out["limit"] or rejected
            if info.get("rateLimitType") and (rejected or info.get("utilization") is not None):
                out["windows"][info["rateLimitType"]] = {
                    "used": 100.0 if rejected else round(100 * info["utilization"], 1), "resets": info.get("resetsAt")}
        elif e.get("type") == "result":
            text, structured = str(e.get("result") or ""), e.get("structured_output")
            out["cost"] = float(e.get("total_cost_usd") or 0)
            if e.get("is_error"):
                out["limit"] = out["limit"] or any(w in text.lower() for w in LIMIT_WORDS)
            else:
                out["report"] = structured if isinstance(structured, dict) else {"text": text} if text else {}
    return out


def _reading(claude: dict, name: str, used: float, resets, at: float) -> None:
    """Take a fresh reading of one Claude window. From the one before, learn what a dollar of our work costs."""
    seen = claude.setdefault("windows", {})
    old = seen.get(name)
    same_window = old and (old.get("resets") is None or resets is None or abs(old["resets"] - resets) < 600)
    if old and same_window and old.get("spent", 0) >= 0.05 and used > old["used"]:
        rate = claude.setdefault("rate", {})
        seen_rate = (used - old["used"]) / old["spent"]
        rate[name] = round(min(30.0, max(0.05, 0.7 * rate.get(name, RATE.get(name, 1.0)) + 0.3 * seen_rate)), 3)
    seen[name] = {"used": used, "resets": resets, "at": at, "spent": 0.0}


def usage(notes: dict, codex: str, claude: str, now: float | None = None) -> dict:
    """What is used of every window of both allowances, as well as it can be known now:
    {"codex": {"five_hour": {"used", "resets"}, …}, "claude": {…}}; None for an allowance nothing is known about.
    Codex is asked (at most once a minute). Claude is the newest of Claude Code's own cache, the last worker's
    report and, when both are over ten minutes old, a one-word run to ask; plus what our workers have cost since."""
    now = now or time.time()
    if os.environ.get("FOUNDRY_USAGE_FILE"):  # tests: never the learner's real allowances
        live = json.loads(Path(os.environ["FOUNDRY_USAGE_FILE"]).read_text())
        out = {p: live.get(p) for p in PROVIDERS}
    else:
        c = notes.setdefault("codex", {})
        if now - c.get("at", 0) > 60 and (windows := codex_usage(codex)):
            c.update(windows=windows, at=now)
        k = notes.setdefault("claude", {})
        cached, at = claude_cache(Path(os.environ.get("FOUNDRY_CLAUDE_STATE") or Path.home() / ".claude.json"))
        for name, w in cached.items():
            if at > k.get("windows", {}).get(name, {}).get("at", 0):
                _reading(k, name, w["used"], w["resets"], at)
        newest = max([w.get("at", 0) for w in k.get("windows", {}).values()] + [k.get("probed", 0)])
        if now - newest > 600:  # other sessions use this allowance too: an old figure is a wrong one
            k["probed"] = now
            for name, w in claude_probe(claude)["windows"].items():
                _reading(k, name, w["used"], w.get("resets"), now)
        rate = k.get("rate", {})
        out = {"codex": c.get("windows"),
               "claude": {name: {"used": min(100.0, w["used"] + w.get("spent", 0) * rate.get(name, RATE.get(name, 1.0))),
                                 "resets": w.get("resets")} for name, w in k.get("windows", {}).items()} or None}
    for p in PROVIDERS:  # a limit a worker ran into closes the allowance for a while, whatever the figures say
        until = notes.get(p, {}).get("closed_until", 0)
        if until > now:
            out[p] = {**(out[p] or {}), "limit": {"used": 100.0, "resets": until}}
    return out


# ---------------- where a job goes ----------------
def score(provider: str, windows: dict | None, cfg: dict, running: list[str], model: str = "",
          now: float | None = None) -> tuple[float | None, str]:
    """Percent of this allowance's longest window left per hour until it resets. (None, why) when it is closed:
    no free slot, or some window has no room once the jobs already running on it are counted."""
    now = now or time.time()
    if len(running) >= cfg["max_parallel"][provider]:
        return None, f"{len(running)} workers already running on {NAMES[provider]}"
    if not windows:
        return UNKNOWN, ""
    pending = sum(cfg["weights"].get(r.split("#")[0], 1.0) for r in running)  # in percent of a five-hour window
    longest = None
    for name, w in windows.items():
        if name.endswith(("_opus", "_sonnet")) and not name.endswith("_" + model):
            continue  # a cap on another model
        mins = MINUTES.get(name, 10080)
        over = w.get("resets") is not None and w["resets"] <= now  # the window has reset since it was read
        room = 100.0 - cfg["reserve"].get(provider, 0) - (0.0 if over else w["used"]) - pending / (1 if mins <= 300 else 7)
        if room <= 0:
            when = f" until {datetime.fromtimestamp(w['resets']):%a %H:%M}" if w.get("resets") and not over else ""
            return None, f"{NAMES[provider]}'s allowance is used up{when}"
        hours = max(1.0, (w["resets"] - now) / 3600) if w.get("resets") and not over else mins / 60
        if longest is None or mins > longest[0]:
            longest = (mins, room / hours)
    return (longest[1] if longest else UNKNOWN), ""


def pick(role: str, maker: str | None, usage: dict, cfg: dict, busy: dict, now: float | None = None) -> str:
    """The allowance this job goes to. `maker` is the allowance that drafted the chapter (None when not known);
    `busy` the jobs running now on each. Raises Wait when none can take it."""
    scores, closed = {}, []
    for p in PROVIDERS:
        if p not in cfg["ladders"][role] or (role in BLIND and p == maker):
            continue
        s, why = score(p, usage.get(p), cfg, busy.get(p, []), cfg["ladders"][role][p][0][0], now)
        if s is None:
            closed.append(why)
        else:
            scores[p] = s
    if not scores:
        raise Wait(f"no allowance can take a {role} now: " + ("; ".join(closed) or "none is set up for it"))
    known = [s for s in scores.values() if s != UNKNOWN]
    level = sum(known) / len(known) if known else 1.0  # an allowance nothing is known about counts as average
    return max(scores, key=lambda p: (round(level if scores[p] == UNKNOWN else scores[p], 6), -PROVIDERS.index(p)))


# ---------------- which tier ----------------
def rung(notes: dict, cfg: dict, role: str, provider: str, retry: int | None = None) -> int:
    """The ladder rung a job starts on: the lowest that has not failed this role twice running. A chapter's retry of
    its own failed job (which ran at rung `retry`) goes one up."""
    top = len(cfg["ladders"][role][provider]) - 1
    floor = notes.get("floor", {}).get(f"{role}/{provider}", 0)
    return min(top, max(floor, retry + 1 if retry is not None else 0))


def record(notes: dict, cfg: dict, role: str, provider: str, at_rung: int, ok: bool, limit: bool = False,
           cost: float = 0.0, windows: dict | None = None, now: float | None = None) -> None:
    """Note how a finished job went: for the tier (two failures running raise the role's floor), for the allowance
    (a usage limit closes it for ten minutes and is not held against the tier), and for the Claude readings."""
    now = now or time.time()
    key, misses = f"{role}/{provider}", notes.setdefault("misses", {})
    if limit:
        notes.setdefault(provider, {})["closed_until"] = now + 600
    elif ok:
        misses[key] = 0
    else:
        misses[key] = misses.get(key, 0) + 1
        if misses[key] >= 2:
            top = len(cfg["ladders"][role][provider]) - 1
            notes.setdefault("floor", {})[key] = min(top, max(notes.get("floor", {}).get(key, 0), at_rung + 1))
            misses[key] = 0
    if provider == "claude":
        claude = notes.setdefault("claude", {})
        for w in claude.get("windows", {}).values():
            w["spent"] = round(w.get("spent", 0) + cost, 4)
        for name, w in (windows or {}).items():
            _reading(claude, name, w["used"], w.get("resets"), now)
