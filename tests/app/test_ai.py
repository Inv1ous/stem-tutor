import asyncio
import json
import sys
from pathlib import Path

import pytest

from tutor_app import ai
from tutor_app.texmath import to_terminal

FAKE = str(Path(__file__).with_name("fake_claude.py"))


def make(tmp_path, monkeypatch, mode="ok", cap=80):
    monkeypatch.setenv("FAKE_CLAUDE_MODE", mode)
    monkeypatch.setenv("FAKE_CLAUDE_LOG", str(tmp_path / "argv.log"))
    return ai.Claude(tmp_path, binary=FAKE, usage_file=tmp_path / "usage.json", daily_cap=cap)


def collect(c, prompt):
    async def go():
        out = [chunk async for chunk in c.stream(prompt)]
        await c.close()
        return out
    return asyncio.run(go())


def test_streams_text_in_pieces_and_counts_usage(tmp_path, monkeypatch):
    c = make(tmp_path, monkeypatch)
    chunks = collect(c, "hello tutor")
    assert len(chunks) > 1 and "".join(chunks).startswith("Reply 1: hello tutor")
    assert c.last.ok and c.session.replies == 1 and c.session.cached_tokens == 300
    assert c.today()["replies"] == 1


def test_lean_flags_are_used(tmp_path, monkeypatch):
    c = make(tmp_path, monkeypatch)
    collect(c, "x")
    argv = json.loads((tmp_path / "argv.log").read_text().splitlines()[0])
    for flag in ("--safe-mode", "--disable-slash-commands", "--strict-mcp-config", "--no-session-persistence"):
        assert flag in argv
    assert argv[argv.index("--tools") + 1] == "" and argv[argv.index("--model") + 1] == "haiku"


def test_one_process_serves_many_turns(tmp_path, monkeypatch):
    c = make(tmp_path, monkeypatch)
    async def go():
        a = await c.reply("one")
        b = await c.reply("two")
        await c.close()
        return a, b
    a, b = asyncio.run(go())
    assert a.text.startswith("Reply 1") and b.text.startswith("Reply 2")
    assert len((tmp_path / "argv.log").read_text().splitlines()) == 1


def test_login_error_switches_to_login_status(tmp_path, monkeypatch):
    c = make(tmp_path, monkeypatch, mode="login")
    collect(c, "x")
    assert not c.last.ok and c.status == "login" and "claude auth login" in c.message and not c.available


def test_usage_limit_pauses_ai_with_reset_time(tmp_path, monkeypatch):
    c = make(tmp_path, monkeypatch, mode="limit")
    collect(c, "x")
    assert c.status == "limit" and "10:30pm" in c.message


def test_daily_cap_stops_calls(tmp_path, monkeypatch):
    c = make(tmp_path, monkeypatch, cap=1)
    collect(c, "x")
    collect(c, "y")
    assert c.last.status == "cap"


def test_missing_binary_means_offline(tmp_path):
    c = ai.Claude(tmp_path, binary=str(tmp_path / "nope"))
    assert c.status == "off" and not c.available


def test_one_shot_returns_structured_json(tmp_path, monkeypatch):
    c = make(tmp_path, monkeypatch)
    data, res = asyncio.run(c.one_shot("mark this", schema={"type": "object"}))
    assert res.ok and data["points"][0]["met"] is True


def test_leak_guard():
    assert ai.leaks("I think the answer is B here", "B: 0.35 kg", "mcq")
    assert ai.leaks("so it is 0.35 kg overall", "B: 0.35 kg overall", "mcq")
    assert not ai.leaks("think about units first", "B: 0.35 kg", "mcq")
    assert ai.leaks("it comes to 19.6 m s-1", "19.6 m s-1", "numeric")
    assert not ai.leaks("try v = u + at", "19.6 m s-1", "numeric")


def test_first_json_finds_embedded_object():
    assert ai.first_json('Sure! {"a": {"b": 1}} done') == {"a": {"b": 1}}


@pytest.mark.parametrize("src,want", [
    (r"$v^2=u^2+2as$", "v²=u²+2as"),
    (r"$\tfrac12at^2$", "at²"),
    (r"$9.81\ \mathrm{m\,s^{-2}}$", "m s⁻²"),
    (r"$\ce{H2SO4}$", "H₂SO₄"),
    (r"$0.48\%$", "0.48%"),
    ("plain text", "plain text"),
    (r"$0.348\to0.3$", "0.348→0.3"),
])
def test_terminal_maths(src, want):
    assert want in to_terminal(src)


def test_pretty_units():
    from tutor_app.texmath import pretty_units
    assert pretty_units("0.27 m s^-2") == "0.27 m s⁻²" and pretty_units("kg m^{-3}") == "kg m⁻³"


def test_stopping_a_reply_midway_does_not_corrupt_the_next(tmp_path, monkeypatch):
    c = make(tmp_path, monkeypatch)

    async def go():
        gen = c.stream("first question")
        async for _ in gen:
            break  # the learner moved on before the reply finished
        await gen.aclose()
        r = await c.reply("second question")
        await c.close()
        return r
    r = asyncio.run(go())
    assert r.ok and r.text.endswith("second question")


def test_leak_guard_catches_more_phrasings():
    assert ai.leaks("**B** is correct here", "B: 0.35 kg", "mcq")
    assert ai.leaks("so it's about 19.60 m/s", "19.6 m s-1", "numeric")
    assert not ai.leaks("start from v = u + at with u = 0", "19.6 m s-1", "numeric")


def test_ai_comes_back_after_a_limit_block(tmp_path, monkeypatch):
    from datetime import datetime, timedelta
    c = make(tmp_path, monkeypatch, mode="limit")
    collect(c, "x")
    assert not c.available
    c.blocked_until = datetime.now() - timedelta(seconds=1)
    assert c.available
