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
import time
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import AsyncIterator

from tutorlib import grade
from tutorlib.units import SUPERSCRIPT

LEAN = ["-p", "--safe-mode", "--disable-slash-commands", "--strict-mcp-config", "--setting-sources", "",
        "--tools", "", "--no-session-persistence"]
# Claude thinks before it answers unless told not to: for a tutor's nudge or marking an answer against its scheme that is
# most of the wait (measured: ~700 output tokens and 7-9 s for a 50-token reply; ~55 tokens and 1.3 s without) and most of
# the usage. Writing a challenge question or a re-mark still thinks (`think=True`).
NO_THINKING = ["--settings", json.dumps({"alwaysThinkingEnabled": False})]
THINKING = ["--settings", json.dumps({"alwaysThinkingEnabled": True})]  # chosen in Settings: slower, far more usage
MEDIA = {".png": "image/png", ".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".gif": "image/gif", ".webp": "image/webp"}

SYSTEM = """You are a patient, exact A-Level tutor (CAIE 9701 Chemistry, CAIE 9702 Physics, Edexcel IAL Mathematics) \
inside a terminal study app. The student is 17, studying in Hong Kong. Write British English.
Rules:
- Keep replies under 120 words unless asked for more. Short paragraphs, no headings.
- Use $...$ for maths. Use exam wording for definitions.
- Ground everything in the CONTEXT you are given; if you are not sure of a fact, say so plainly.
- If CONTEXT marks a question as OPEN, never state its answer, option letter or final value; give a nudge instead.
- Teach by building from what they already know: why it matters, how it could have been discovered, how it connects.
- When they are stuck, ask one guiding question at a time rather than lecturing."""

SPEECH_MARK = "[[SPEECH]]"
SPEECH_RULE = f"""
- Your reply is also read aloud. End EVERY reply with one last line that starts {SPEECH_MARK} followed by the same \
reply rewritten as plain spoken English for a text-to-speech voice: no symbols, no LaTeX, no Markdown, no lists; \
numbers, units, powers, subscripts, fractions, roots, integrals, sums and limits in words (x squared, ten to the minus \
three, metres per second squared, the integral from nought to one of x squared d x, the sum from r equals one to n); \
chemical formulae letter by letter (H two S O four); short sentences. Never put that line in a code block, and never \
let it say anything the reply itself does not."""
SPEECH_FIELD = ("Also return speech: everything you wrote for the student, rewritten as plain spoken English for a "
                "text-to-speech voice (no symbols, LaTeX or Markdown; numbers, units, powers, integrals and sums in "
                "words; short sentences).")

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


def split_speech(text: str) -> tuple[str, str]:
    """A whole reply → (what is shown, what is read aloud). Everything from the speech marker on is speech, never
    shown; a code fence the marker left open is closed off (dropped)."""
    shown, mark, speech = (text or "").partition(SPEECH_MARK)
    if not mark:
        return text or "", ""
    shown = shown.rstrip()
    if shown.count("```") % 2:  # the marker was put inside a code block: drop the fence it opened
        shown = shown[:shown.rfind("```")].rstrip()
    return shown, speech.replace("```", " ").strip()


class SpeechFilter:
    """The same split on a stream: `feed(chunk)` returns what may be shown now, holding back a piece that could be
    the start of the marker (it can arrive split across chunks); `finish()` returns what was held back."""

    def __init__(self) -> None:
        self.held, self.speech, self.found = "", "", False

    def feed(self, chunk: str) -> str:
        if self.found:
            self.speech += chunk
            return ""
        text = self.held + chunk
        before, mark, after = text.partition(SPEECH_MARK)
        if mark:
            self.found, self.held, self.speech = True, "", after
            return before
        keep = next((n for n in range(min(len(SPEECH_MARK) - 1, len(text)), 0, -1)
                     if SPEECH_MARK.startswith(text[-n:])), 0)
        self.held = text[len(text) - keep:] if keep else ""
        return text[:len(text) - keep] if keep else text

    def finish(self) -> str:
        out, self.held = self.held, ""
        return "" if self.found else out


@dataclass
class Result:
    text: str = ""
    ok: bool = True
    status: str = "ready"  # ready | login | limit | error | off
    message: str = ""
    usage: dict = field(default_factory=dict)
    speech: str = ""  # the reply as spoken English, when the AI was asked for it (read aloud on); "" otherwise


class Claude:
    """A persistent streaming conversation. `stream(prompt)` yields text as it arrives; `last` holds the outcome."""

    def __init__(self, cwd: Path, model: str = "haiku", system: str = SYSTEM, binary: str | None = None,
                 usage_file: Path | None = None, speech: bool = False):
        self.cwd, self.model, self.system = Path(cwd), model, system
        self.think = False  # the default conversation's thinking (Settings chooses per mode: marking, explaining, asking)
        self.speech = speech  # read aloud is on: replies end with a spoken version (costs nothing when off)
        self.binary = binary or os.environ.get("STEM_TUTOR_CLAUDE") or shutil.which("claude") or "claude"
        # one conversation per (model, thinking): explaining and asking can use different ones without restarting
        self.key: tuple[str, bool] = (model, False)
        self.procs: dict[tuple[str, bool], asyncio.subprocess.Process] = {}
        self._shown: dict[tuple[str, bool], set[str]] = {}  # images a conversation has already been shown
        self.status = "ready" if shutil.which(self.binary) or Path(self.binary).exists() else "off"
        self.message = "" if self.status != "off" else "Claude Code is not installed, so AI help is off."
        self.session = Usage()
        self.usage_file = usage_file
        self.limits: dict = {}  # the plan's limits as Claude itself last named them to this app
        self.last = Result()
        self._lock = asyncio.Lock()
        self._pending = 0  # one-shot calls in flight, counted against the daily cap before they finish
        self.wanted = lambda: True  # the app's AI switch (Settings): when off, no process is started ahead (Q-015)

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
        try:
            write_text(self.usage_file, json.dumps(dict(sorted(data.items())[-60:]), indent=1))
        except OSError:  # a read-only vault or full disk must not cost the learner the reply
            pass
        self._today = (date.today().isoformat(), d)

    @property
    def available(self) -> bool:
        if self.status in ("login", "limit") and datetime.now() >= getattr(self, "blocked_until", datetime.max):
            self.status, self.message = "ready", ""  # try again: you may have signed in, or the limit reset
        return self.status == "ready"

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
    @property
    def proc(self) -> asyncio.subprocess.Process | None:
        """The conversation in use now (the model and thinking last asked for)."""
        return self.procs.get(self.key)

    @proc.setter
    def proc(self, value) -> None:
        if value is None:
            self.procs.pop(self.key, None)
            self._shown.pop(self.key, None)
        else:
            self.procs[self.key] = value

    async def _start(self) -> None:
        env = {**os.environ, "CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC": "1"}
        model, think = self.key
        self._shown[self.key] = set()
        self.proc = await asyncio.create_subprocess_exec(
            self.binary, *LEAN, *(THINKING if think else NO_THINKING), "--model", model,
            "--system-prompt", self.system + (SPEECH_RULE if self.speech else ""),
            "--input-format", "stream-json", "--output-format", "stream-json", "--include-partial-messages", "--verbose",
            cwd=str(self.cwd), env=env, stdin=asyncio.subprocess.PIPE, stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.DEVNULL, limit=4 * 1024 * 1024)

    async def warm(self) -> None:
        """Start the conversation's process now, before it is needed: Claude Code takes a second or two to start, and
        that is then over before the learner asks. Costs nothing until a message is sent."""
        if self.status == "off" or getattr(self, "_closed", False) or not self.wanted():
            return
        async with self._lock:
            # the conversation asked for next is the default one (Settings' "Ask"), whatever a stream used last (Q-002)
            self.key = (self.model, self.think)
            if self.proc is None or self.proc.returncode is not None:
                try:
                    await self._start()
                except OSError:
                    self.proc = None

    async def reset(self, warm: bool = True) -> None:
        """Forget the conversations (e.g. a new idea starts): a fresh process takes over, started at once so the
        next question does not wait for it."""
        procs, self.procs, self._shown = list(self.procs.values()), {}, {}
        for proc in procs:
            if proc and proc.returncode is None:
                try:
                    if proc.stdin:
                        proc.stdin.close()
                    await asyncio.wait_for(proc.wait(), 3)
                except (asyncio.TimeoutError, ProcessLookupError, BrokenPipeError, ConnectionResetError):
                    proc.kill()
        if warm and self.available:
            self._warming = asyncio.ensure_future(self.warm())

    async def close(self) -> None:
        self._closed = True
        await self.reset(warm=False)

    async def stream(self, prompt: str, image: Path | None = None, model: str | None = None,
                     think: bool | None = None) -> AsyncIterator[str]:
        """Send `prompt` (with `image`, a diagram, the first time this conversation sees it) and yield the reply as it
        comes. `model`/`think`: the conversation to use (Settings chooses them per mode); default, the app's own."""
        if self.status == "off":
            self.last = Result(ok=False, status="off", message=self.message)
            return
        async with self._lock:
            self.key = (model or self.model, self.think if think is None else bool(think))
            if self.proc is None or self.proc.returncode is not None:
                try:
                    await self._start()
                except OSError:  # not executable, or gone since the check: an error result, never a crash
                    self.proc = None
                    self.last = Result(ok=False, status="error", message="Claude Code could not be started.")
                    return
            proc = self.proc
            assert proc is not None and proc.stdin is not None and proc.stdout is not None
            content: str | list = prompt
            shown = self._shown.setdefault(self.key, set())
            if image is not None and str(image) not in shown and Path(image).suffix.lower() in MEDIA:
                try:  # once per conversation: it stays in the conversation's memory after that
                    import base64
                    data = base64.b64encode(Path(image).read_bytes()).decode()
                    content = [{"type": "image", "source": {"type": "base64", "media_type": MEDIA[Path(image).suffix.lower()],
                                                            "data": data}}, {"type": "text", "text": prompt}]
                    shown.add(str(image))
                except OSError:
                    content = prompt
            msg = {"type": "user", "message": {"role": "user", "content": content}}
            try:
                proc.stdin.write((json.dumps(msg) + "\n").encode())
                await proc.stdin.drain()
            except (BrokenPipeError, ConnectionResetError):
                self.proc = None
                self.last = Result(ok=False, status="error", message="The AI process stopped; try again.")
                return
            parts, finished = [], False
            spoken = SpeechFilter()  # the spoken version at the end of a reply is never shown
            try:
                async for piece in self._read(proc, parts):
                    if (shown := spoken.feed(piece)):
                        yield shown
                if (tail := spoken.finish()):
                    yield tail
                finished = True
                self.last.text, self.last.speech = split_speech(self.last.text)
            except asyncio.TimeoutError:
                self.last = Result(ok=False, status="error", text=split_speech("".join(parts))[0],
                                   message="The AI took too long to answer; try again.")
            finally:
                if not finished:  # stopped mid-reply: the rest would leak into the next answer, so start fresh
                    await self.reset()

    async def _read(self, proc, parts: list) -> AsyncIterator[str]:
        """Read one reply's events up to its result (sets self.last)."""
        streamed = False
        while True:
            try:
                line = await asyncio.wait_for(proc.stdout.readline(), 120)
            except ValueError:  # one line longer than the stream limit: the rest of it would poison the next reply
                proc.kill()
                self.proc = None
                self.last = Result(ok=False, status="error", text="".join(parts),
                                   message="The AI sent an unreadable reply; try again.")
                return
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
            elif kind == "rate_limit_event":  # Claude names one window: the one nearest its end
                info = ev.get("rate_limit_info") or {}
                if info.get("rateLimitType") and info.get("utilization") is not None:
                    self.limits[info["rateLimitType"]] = {"used": round(100 * info["utilization"]),
                                                          "resets": info.get("resetsAt")}
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

    def limits_text(self, noted: dict) -> str:
        """What is left of the week's limit, for beside the token count: "week 8% left". A figure Claude gave this
        app itself is exact; one from Claude Code's own note (`noted`) can lag and is marked ~. Nothing when neither
        has it. The five-hour limit is not shown: Claude seldom names it to a background helper."""
        own, note, now = self.limits.get("seven_day"), noted.get("seven_day"), time.time()
        if own and (not own.get("resets") or own["resets"] > now):
            return f"week {100 - own['used']}% left"
        if note and note["resets"] > now:
            return f"week ~{100 - round(note['used'])}% left"
        return ""

    async def reply(self, prompt: str) -> Result:
        async for _ in self.stream(prompt):
            pass
        return self.last

    async def one_shot(self, prompt: str, schema: dict | None = None, model: str | None = None,
                       timeout: float = 120, system: str | None = None,
                       speech: bool = False, think: bool = False) -> tuple[dict | None, Result]:
        """A separate, memory-less call that must return JSON (judging an answer, writing a teach card). `timeout` is
        in seconds: a hard challenge question can take Opus several minutes. `system` replaces the tutor brief for
        this call only (writing a challenge question needs its full worked solution, not a short nudge). `speech`:
        an on-the-spot comment the learner may hear; with read aloud on, the reply carries a `speech` field too (in
        the same call: no second request). `think`: let the model think first (slower, more usage) — for writing a
        challenge question or a re-mark; marking, nudges and cards answer straight away and return their JSON in one
        turn (a schema-checked second try only if that JSON is missing or incomplete)."""
        if not self.available:
            return None, Result(ok=False, status=self.status, message=self.message or "AI unavailable")
        self._pending += 1
        try:
            if speech and self.speech and schema:
                schema = {**schema, "properties": {**schema.get("properties", {}), "speech": {"type": "string"}}}
                prompt = f"{prompt}\n\n{SPEECH_FIELD}"
            if schema and not think:
                data, res = await self._one_shot(f"{prompt}\n\n{json_instruction(schema)}", None, model, timeout,
                                                 system, think=False)
                if res.ok and complete(data, schema):
                    return data, res
                if not res.ok and res.status in ("login", "limit"):
                    return data, res
            return await self._one_shot(prompt, schema, model, timeout, system, think=think)
        finally:
            self._pending -= 1

    async def _one_shot(self, prompt: str, schema: dict | None, model: str | None,
                        timeout: float = 120, system: str | None = None,
                        think: bool = True) -> tuple[dict | None, Result]:
        args = [*LEAN, *(THINKING if think else NO_THINKING), "--model", model or self.model,
                "--system-prompt", system or self.system, "--output-format", "json"]
        if schema:
            args += ["--json-schema", json.dumps(schema)]
        try:
            proc = await asyncio.create_subprocess_exec(self.binary, *args, cwd=str(self.cwd), stdin=asyncio.subprocess.PIPE,
                                                        stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.DEVNULL)
        except OSError:
            return None, Result(ok=False, status="error", message="Claude Code could not be started.")
        try:
            out, _ = await asyncio.wait_for(proc.communicate(prompt.encode()), timeout)
        except asyncio.CancelledError:  # the caller was cancelled (new judge started, screen left): stop for real
            proc.kill()
            await proc.wait()
            raise
        except asyncio.TimeoutError:
            proc.kill()
            await proc.wait()
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
        speech = data.get("speech") if isinstance(data, dict) and isinstance(data.get("speech"), str) else ""
        return data, Result(text=ev.get("result", ""), speech=speech.strip(), usage=usage)


def json_instruction(schema: dict) -> str:
    """Asking for the JSON in words: one turn, where `--json-schema` takes two (a tool call, then a reply)."""
    return ("Reply with ONLY one JSON object (no code fence, no other text) that matches this JSON schema. Inside JSON "
            "strings write every LaTeX backslash twice ($\\\\frac{1}{2}$).\n" + json.dumps(schema, ensure_ascii=False))


def complete(data, schema: dict) -> bool:
    """The reply has every field the schema requires, each of the right basic type."""
    if not isinstance(data, dict):
        return False
    kinds = {"string": str, "boolean": bool, "array": list, "object": dict, "integer": int, "number": (int, float)}
    props = schema.get("properties", {})
    for key in schema.get("required", list(props)):
        if key not in data:
            return False
        want = kinds.get((props.get(key) or {}).get("type"))
        if want and not isinstance(data[key], want):
            return False
    return True


_CONTROL = re.compile(r"[\x08\x0c]|[\t\r](?=[A-Za-z])")  # a LaTeX backslash read as an escape: \frac -> form feed + "rac"


def _unescape_latex(x):
    if isinstance(x, str):
        return _CONTROL.sub(lambda m: {"\x08": "\\b", "\x0c": "\\f", "\t": "\\t", "\r": "\\r"}[m.group(0)], x)
    if isinstance(x, dict):
        return {k: _unescape_latex(v) for k, v in x.items()}
    if isinstance(x, list):
        return [_unescape_latex(v) for v in x]
    return x


def first_json(text: str) -> dict | None:
    found = _first_json(text)
    return _unescape_latex(found) if found is not None else None


def _first_json(text: str) -> dict | None:
    start = text.find("{")
    while start != -1:
        depth = 0
        for i in range(start, len(text)):
            depth += {"{": 1, "}": -1}.get(text[i], 0)
            if depth == 0:
                try:
                    return json.loads(text[start:i + 1])
                except json.JSONDecodeError:
                    try:  # LaTeX written with one backslash (`\theta`, `\,`) is not valid JSON: double the odd ones
                        return json.loads(re.sub(r'\\(?!["\\/bfnrtu])', r"\\\\", text[start:i + 1]))
                    except json.JSONDecodeError:
                        break
        start = text.find("{", start + 1)
    return None


_NUMBER = re.compile(r"(?P<pow>\b10\s*\^\s*[({]?\s*(?P<p>[+-]?\d+))|(?P<num>-?(?:\d{1,3}(?:,\d{3})+|\d+)(?:\.\d+)?"
                     r"(?:\s*(?:[eE][+-]?\d+|(?:[x×*·]|\\times)\s*10\s*\^?\s*[({]?\s*[+-]?\d+))?|-?\.\d+)")
_SUPERSCRIPTS = re.compile(r"[⁻⁺]?[⁰¹²³⁴⁵⁶⁷⁸⁹]+")


def _numbers(text: str):
    """Every number written in `text`, with its significant figures and the digits it was written to, as the marking
    reads them (both None for a bare power of ten): 1000, 1,000, 1.0 × 10^3, 1e3, 10^3, 4.2 × 10⁻³."""
    for m in _NUMBER.finditer(grade.plain_powers(text).replace("−", "-")):
        if m["pow"]:
            yield 10.0 ** int(m["p"]), None, None
            continue
        try:
            value, _, sf, digits = grade._parse(m["num"])
        except grade.ParseError:
            continue
        yield value, sf, digits


def _flat(text: str) -> str:
    """Maths with spacing, *, $ and braces removed and powers as ^: u² + 2·a·s and u**2 + 2*a*s both read u^2+2as."""
    text = _SUPERSCRIPTS.sub(lambda m: "^" + m[0].translate(SUPERSCRIPT), text.replace("**", "^"))
    return re.sub(r"[\s*$\\{}·×]", "", text)


def leaks(reply: str, key: str, kind: str, answer: dict | None = None) -> bool:
    """True when a reply gives away an open question's answer (letter, option text, expression or final value).

    `answer` is a numeric question's own answer: with it, a number counts at any precision the marking would accept,
    not only near the rounded key that is shown (a key shown as 3.8 has the true value 3.75)."""
    if not key:
        return False
    text = re.sub(r"[*_`$\\]", "", reply)
    if kind == "mcq":
        letter, _, opt = key.partition(": ")
        L = f"(?-i:{re.escape(letter)})"  # the capital letter itself: "it is a vector" is not option A
        any_case = re.escape(letter)  # where the words can only be naming an option, "b" is option B too (B-072)
        pats = [rf"\b(answer|option|choice)\s*(is|would be|must be|=|:)\s*\(?{any_case}\b",
                rf"\bit\s*(is|would be|must be|=|:)\s*\(?{L}\b",
                rf"\b\(?{any_case}\)?\s+is\s+(correct|right|the answer)",
                rf"\b(option|choice|letter)\s*\(?{any_case}\)?(?![A-Za-z0-9])",
                rf"^\W*\(?{L}\)?\s*(?:[.):\-–—]|$)"]  # the reply is, or starts by labelling, the letter
        if any(re.search(p, text.strip(), re.I) for p in pats):
            return True
        clean = re.sub(r"[*_`$\\]", "", opt).strip().lower()
        if len(clean) > 6:
            return clean in text.lower()
        # a short option ("1", "6 N") gives the answer away when it is given as the answer, not when it is merely
        # mentioned: "the y-intercept is 1" (B-072)
        return bool(clean) and bool(re.search(rf"(?:\b(?:is|are|equals|gives|be)|=|:)\s*(?:just\s+|exactly\s+)?"
                                              rf"{re.escape(clean)}(?!\w|\.\d)", text.lower()))
    if kind == "short":  # the model answer itself, word for word (B-072)
        said, model = " ".join(text.lower().split()), " ".join(re.sub(r"[*_`$\\]", "", key).lower().split()).rstrip(".")
        return len(model) > 12 and model in said
    if kind == "expression":
        # An equation key still gives away the answer when only its right side is shown.
        if len(flat := _flat(grade._sides(key)[1])) >= 4 and flat in _flat(reply):
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
    targets = []
    try:
        targets.append(grade.parse_quantity(key)[0])
    except grade.ParseError:
        pass
    true = (answer or {}).get("value")
    if true is not None:
        targets.append(true)
    rounded_ok = true is not None and not answer.get("exact")  # as marked: right when rounded at its own digits
    allowed = (answer or {}).get("sf_ok") or [(answer or {}).get("sf")]
    for v, sf, digits in _numbers(text):
        if any(abs(v - t) <= max(abs(t) * 0.01, 1e-12) for t in targets):
            return True
        if rounded_ok and grade.rounding_of(v, true, sf, digits, allowed):
            return True
    want = (answer or {}).get("unit")
    if want:  # the same answer in another unit the marking accepts: 0.4 kN for 400 N (B-074)
        from tutorlib.units import unit_readings
        for v, unit in _quantities(text):
            factors, _ = unit_readings(unit, want)
            if any(abs(v * f - t) <= max(abs(t) * 0.01, 1e-12) for f in factors for t in targets):
                return True
    return False


def _quantities(text: str):
    """Each number written with the words after it that may be its unit: (value, "kN of force")."""
    plain = grade.plain_powers(text).replace("−", "-")
    for m in _NUMBER.finditer(plain):
        rest = re.match(r"\s*([A-Za-zµΩ°][^\s,;]*(?:\s+(?:per\s+)?[A-Za-zµΩ][^\s,;]*)?)", plain[m.end():]) if m["num"] else None
        if not rest:
            continue
        try:
            value = grade._parse(m["num"])[0]
        except grade.ParseError:
            continue
        yield value, rest[1].rstrip(".")
