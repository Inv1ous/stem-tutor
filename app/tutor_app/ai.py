"""The tutor's AI: one background Claude process on your Claude subscription (no API key, no Claude window).

It runs `claude -p` with everything switched off except text (no tools, skills, plugins, MCP servers or CLAUDE.md), so
each request carries only a short tutor brief plus a small context packet. The process stays alive for the session so
the brief is cached; it is restarted (fresh memory) whenever a new idea starts.
"""
from __future__ import annotations

import asyncio
import json
import os
import re
import shutil
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import AsyncIterator

from tutorlib import grade
from tutorlib.units import SUPERSCRIPT

LEAN = ["-p", "--safe-mode", "--disable-slash-commands", "--strict-mcp-config", "--setting-sources", "",
        "--tools", "", "--no-session-persistence"]

SYSTEM = """You are a patient, exact A-Level tutor (CAIE 9701 Chemistry, CAIE 9702 Physics, Edexcel IAL Mathematics) \
inside a terminal study app. The student is 17, studying in Hong Kong. Write British English.
Rules:
- Keep replies under 120 words unless asked for more. Short paragraphs, no headings.
- Use $...$ for maths. Use exam wording for definitions.
- Ground everything in the CONTEXT you are given; if you are not sure of a fact, say so plainly.
- If CONTEXT marks a question as OPEN, never state its answer, option letter or final value; give a nudge instead.
- Teach by building from what they already know: why it matters, how it could have been discovered, how it connects.
- When they are stuck, ask one guiding question at a time rather than lecturing."""

LOGIN_HELP = ("The AI needs you to sign in once: open Terminal and run  claude auth login  "
              "(use your Claude account, the same one as the app). Everything else works without it.")


def classify(text: str) -> str:
    t = (text or "").lower()
    if any(k in t for k in ("authenticate", "oauth", "not logged in", "/login", "log in", "invalid api key")):
        return "login"
    if any(k in t for k in ("usage limit", "session limit", "weekly limit", "rate limit", "429", "limit reached")):
        return "limit"
    return "error"


def reset_time(text: str) -> str | None:
    m = re.search(r"resets?\s+(?:at\s+)?([0-9]{1,2}(?::[0-9]{2})?\s*[ap]m)", text or "", re.I)
    return m.group(1) if m else None


@dataclass
class Usage:
    replies: int = 0
    input_tokens: int = 0
    cached_tokens: int = 0
    output_tokens: int = 0

    def add(self, u: dict) -> None:
        self.replies += 1
        self.input_tokens += int(u.get("input_tokens") or 0) + int(u.get("cache_creation_input_tokens") or 0)
        self.cached_tokens += int(u.get("cache_read_input_tokens") or 0)
        self.output_tokens += int(u.get("output_tokens") or 0)


@dataclass
class Result:
    text: str = ""
    ok: bool = True
    status: str = "ready"  # ready | login | limit | error | off
    message: str = ""
    usage: dict = field(default_factory=dict)


class Claude:
    """A persistent streaming conversation. `stream(prompt)` yields text as it arrives; `last` holds the outcome."""

    def __init__(self, cwd: Path, model: str = "haiku", system: str = SYSTEM, binary: str | None = None,
                 usage_file: Path | None = None, daily_cap: int = 80):
        self.cwd, self.model, self.system = Path(cwd), model, system
        self.binary = binary or os.environ.get("STEM_TUTOR_CLAUDE") or shutil.which("claude") or "claude"
        self.proc: asyncio.subprocess.Process | None = None
        self.status = "ready" if shutil.which(self.binary) or Path(self.binary).exists() else "off"
        self.message = "" if self.status != "off" else "Claude Code is not installed, so AI help is off."
        self.session = Usage()
        self.usage_file, self.daily_cap = usage_file, daily_cap
        self.last = Result()
        self._lock = asyncio.Lock()
        self._pending = 0  # one-shot calls in flight, counted against the daily cap before they finish

    # ---------------- daily usage (kept in the vault so it survives restarts) ----------------
    def today(self) -> dict:
        key = date.today().isoformat()
        if getattr(self, "_today", (None,))[0] != key:  # read the file once a day, not every second
            self._today = (key, self._load().get(key, {"replies": 0, "input": 0, "cached": 0, "output": 0}))
        return self._today[1]

    def _load(self) -> dict:
        try:
            data = json.loads(self.usage_file.read_text()) if self.usage_file and self.usage_file.exists() else {}
            return data if isinstance(data, dict) else {}
        except (OSError, ValueError):  # a damaged counter file must never stop the app
            return {}

    def _record_day(self, u: dict) -> None:
        if not self.usage_file:
            return
        data = self._load()
        d = data.setdefault(date.today().isoformat(), {"replies": 0, "input": 0, "cached": 0, "output": 0})
        d["replies"] += 1
        d["input"] += int(u.get("input_tokens") or 0) + int(u.get("cache_creation_input_tokens") or 0)
        d["cached"] += int(u.get("cache_read_input_tokens") or 0)
        d["output"] += int(u.get("output_tokens") or 0)
        from tutorlib.store import write_text
        write_text(self.usage_file, json.dumps(dict(sorted(data.items())[-60:]), indent=1))
        self._today = (date.today().isoformat(), d)

    @property
    def available(self) -> bool:
        if self.status in ("login", "limit") and datetime.now() >= getattr(self, "blocked_until", datetime.max):
            self.status, self.message = "ready", ""  # try again: you may have signed in, or the limit reset
        return self.status == "ready" and self.today()["replies"] < self.daily_cap

    def _block(self, status: str, text: str) -> None:
        now = datetime.now()
        until = now + timedelta(minutes=3)
        if status == "limit" and (when := reset_time(text)):
            try:
                t = datetime.strptime(when.replace(" ", "").upper(), "%I:%M%p" if ":" in when else "%I%p").time()
                until = datetime.combine(now.date(), t)
                until += timedelta(days=1) if until <= now else timedelta(0)
            except ValueError:
                until = now + timedelta(minutes=30)
        self.blocked_until = until

    # ---------------- process ----------------
    async def _start(self) -> None:
        env = {**os.environ, "CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC": "1"}
        self.proc = await asyncio.create_subprocess_exec(
            self.binary, *LEAN, "--model", self.model, "--system-prompt", self.system,
            "--input-format", "stream-json", "--output-format", "stream-json", "--include-partial-messages", "--verbose",
            cwd=str(self.cwd), env=env, stdin=asyncio.subprocess.PIPE, stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.DEVNULL, limit=4 * 1024 * 1024)

    async def reset(self) -> None:
        """Forget the conversation (e.g. a new idea starts): the next message opens a fresh process."""
        proc, self.proc = self.proc, None
        if proc and proc.returncode is None:
            try:
                if proc.stdin:
                    proc.stdin.close()
                await asyncio.wait_for(proc.wait(), 3)
            except (asyncio.TimeoutError, ProcessLookupError, BrokenPipeError, ConnectionResetError):
                proc.kill()

    async def close(self) -> None:
        await self.reset()

    async def stream(self, prompt: str) -> AsyncIterator[str]:
        if self.status == "off":
            self.last = Result(ok=False, status="off", message=self.message)
            return
        if self.today()["replies"] >= self.daily_cap:
            self.last = Result(ok=False, status="cap", message=f"Today's AI allowance ({self.daily_cap} replies) is used up.")
            return
        async with self._lock:
            if self.today()["replies"] + self._pending >= self.daily_cap:  # re-check: a queued request may be over
                self.last = Result(ok=False, status="cap", message=f"Today's AI allowance ({self.daily_cap} replies) is used up.")
                return
            if self.proc is None or self.proc.returncode is not None:
                await self._start()
            proc = self.proc
            assert proc is not None and proc.stdin is not None and proc.stdout is not None
            msg = {"type": "user", "message": {"role": "user", "content": prompt}}
            try:
                proc.stdin.write((json.dumps(msg) + "\n").encode())
                await proc.stdin.drain()
            except (BrokenPipeError, ConnectionResetError):
                self.proc = None
                self.last = Result(ok=False, status="error", message="The AI process stopped; try again.")
                return
            parts, finished = [], False
            try:
                async for piece in self._read(proc, parts):
                    yield piece
                finished = True
            except asyncio.TimeoutError:
                self.last = Result(ok=False, status="error", text="".join(parts),
                                   message="The AI took too long to answer; try again.")
            finally:
                if not finished:  # stopped mid-reply: the rest would leak into the next answer, so start fresh
                    await self.reset()

    async def _read(self, proc, parts: list) -> AsyncIterator[str]:
        """Read one reply's events up to its result (sets self.last)."""
        streamed = False
        while True:
            line = await asyncio.wait_for(proc.stdout.readline(), 120)
            if not line:
                self.proc = None
                self.last = Result(ok=False, status="error", text="".join(parts),
                                   message="The AI process ended unexpectedly; try again.")
                return
            try:
                ev = json.loads(line)
            except json.JSONDecodeError:
                continue
            kind = ev.get("type")
            if kind == "stream_event":
                e = ev.get("event", {})
                if e.get("type") == "content_block_delta" and e.get("delta", {}).get("type") == "text_delta":
                    streamed = True
                    parts.append(e["delta"]["text"])
                    yield e["delta"]["text"]
            elif kind == "assistant" and not streamed:
                for block in ev.get("message", {}).get("content", []) or []:
                    if block.get("type") == "text" and block.get("text"):
                        parts.append(block["text"])
            elif kind == "result":
                usage = ev.get("usage") or {}
                if ev.get("is_error"):
                    text = ev.get("result") or "".join(parts)
                    status = classify(text)
                    self.status = status if status in ("login", "limit") else "ready"
                    if status in ("login", "limit"):
                        self._block(status, text)
                    when = reset_time(text)
                    self.message = LOGIN_HELP if status == "login" else (
                        f"Your Claude usage limit is reached{f' (resets {when})' if when else ''}; "
                        "AI help pauses, everything else carries on." if status == "limit" else text)
                    self.last = Result(ok=False, status=status, message=self.message, usage=usage)
                    if status != "error":
                        await self.reset()
                    return
                if not streamed and parts:
                    yield "".join(parts)
                self.session.add(usage)
                self._record_day(usage)
                self.last = Result(text=ev.get("result") or "".join(parts), usage=usage)
                return

    async def reply(self, prompt: str) -> Result:
        async for _ in self.stream(prompt):
            pass
        return self.last

    async def one_shot(self, prompt: str, schema: dict | None = None, model: str | None = None) -> tuple[dict | None, Result]:
        """A separate, memory-less call that must return JSON (judging an answer, writing a teach card)."""
        if not self.available or self.today()["replies"] + self._pending >= self.daily_cap:
            return None, Result(ok=False, status=self.status, message=self.message or "AI unavailable")
        self._pending += 1
        try:
            return await self._one_shot(prompt, schema, model)
        finally:
            self._pending -= 1

    async def _one_shot(self, prompt: str, schema: dict | None, model: str | None) -> tuple[dict | None, Result]:
        args = [*LEAN, "--model", model or self.model, "--system-prompt", self.system, "--output-format", "json"]
        if schema:
            args += ["--json-schema", json.dumps(schema)]
        proc = await asyncio.create_subprocess_exec(self.binary, *args, cwd=str(self.cwd), stdin=asyncio.subprocess.PIPE,
                                                    stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.DEVNULL)
        try:
            out, _ = await asyncio.wait_for(proc.communicate(prompt.encode()), 120)
        except (asyncio.TimeoutError, asyncio.CancelledError):
            proc.kill()
            return None, Result(ok=False, status="error", message="The AI took too long to answer.")
        try:
            ev = json.loads(out.decode() or "{}")
        except json.JSONDecodeError:
            return None, Result(ok=False, status="error", message="The AI returned something unreadable.")
        if ev.get("is_error"):
            status = classify(ev.get("result", ""))
            if status in ("login", "limit"):
                self.status = status
                self._block(status, ev.get("result", ""))
                self.message = LOGIN_HELP if status == "login" else "Your Claude usage limit is reached."
            return None, Result(ok=False, status=status, message=ev.get("result", ""))
        usage = ev.get("usage") or {}
        self.session.add(usage)
        self._record_day(usage)
        data = ev.get("structured_output")
        if data is None:
            data = first_json(ev.get("result", ""))
        return data, Result(text=ev.get("result", ""), usage=usage)


def first_json(text: str) -> dict | None:
    start = text.find("{")
    while start != -1:
        depth = 0
        for i in range(start, len(text)):
            depth += {"{": 1, "}": -1}.get(text[i], 0)
            if depth == 0:
                try:
                    return json.loads(text[start:i + 1])
                except json.JSONDecodeError:
                    break
        start = text.find("{", start + 1)
    return None


_NUMBER = re.compile(r"(?P<pow>\b10\s*\^\s*[({]?\s*(?P<p>[+-]?\d+))|(?P<num>-?(?:\d{1,3}(?:,\d{3})+|\d+)(?:\.\d+)?"
                     r"(?:\s*(?:[eE][+-]?\d+|(?:[x×*·]|\\times)\s*10\s*\^?\s*[({]?\s*[+-]?\d+))?|-?\.\d+)")
_SUPERSCRIPTS = re.compile(r"[⁻⁺]?[⁰¹²³⁴⁵⁶⁷⁸⁹]+")


def _numbers(text: str):
    """Every number written in `text`: 1000, 1,000, 1.0 × 10^3, 1e3, 10^3, 4.2 × 10⁻³."""
    for m in _NUMBER.finditer(text.translate(SUPERSCRIPT).replace("−", "-")):
        if m["pow"]:
            yield 10.0 ** int(m["p"])
            continue
        try:
            yield grade.parse_quantity(m["num"])[0]
        except grade.ParseError:
            continue


def _flat(text: str) -> str:
    """Maths with spacing, *, $ and braces removed and powers as ^: u² + 2·a·s and u**2 + 2*a*s both read u^2+2as."""
    text = _SUPERSCRIPTS.sub(lambda m: "^" + m[0].translate(SUPERSCRIPT), text.replace("**", "^"))
    return re.sub(r"[\s*$\\{}·×]", "", text)


def leaks(reply: str, key: str, kind: str) -> bool:
    """True when a reply gives away an open question's answer (letter, option text, expression or final value)."""
    if not key:
        return False
    text = re.sub(r"[*_`$\\]", "", reply)
    if kind == "mcq":
        letter, _, opt = key.partition(": ")
        L = f"(?-i:{re.escape(letter)})"  # the capital letter itself: "it is a vector" is not option A
        pats = [rf"\b(answer|option|choice|it)\s*(is|would be|must be|=|:)\s*\(?{L}\b",
                rf"\b\(?{L}\)?\s+is\s+(correct|right|the answer)",
                rf"\b(option|choice|letter)\s*\(?{L}\)?(?![A-Za-z0-9])",
                rf"^\W*\(?{L}\)?\s*(?:[.):\-–—]|$)"]  # the reply is, or starts by labelling, the letter
        if any(re.search(p, text.strip(), re.I) for p in pats):
            return True
        clean = re.sub(r"[*_`$\\]", "", opt).strip().lower()
        return len(clean) > 6 and clean in text.lower()
    if kind == "expression":
        if len(flat := _flat(key)) >= 4 and flat in _flat(reply):
            return True
        for part in re.split(r"=|\bis\b|:", reply)[1:]:  # each right-hand side, in any equivalent form
            try:
                if grade.expressions_equal(re.split(r"[\n;,]|\.(?:\s|$)", part.strip())[0], key):
                    return True
            except Exception:  # noqa: BLE001 - prose is not maths
                continue
        return False
    if kind != "numeric":
        return False
    try:
        target = grade.parse_quantity(key)[0]
    except grade.ParseError:
        return False
    return any(abs(v - target) <= max(abs(target) * 0.01, 1e-12) for v in _numbers(text))
