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
    (r"$v\cos\theta$", "v cos θ"),
    (r"$v_y$", "v_y"),
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


@pytest.mark.parametrize("reply,key,kind", [  # B-018: each gives the open answer away
    ("B.", "B: 0.35 kg", "mcq"), ("(B)", "B: 0.35 kg", "mcq"), ("B) because the mass halves", "B: 0.35 kg", "mcq"),
    ("Go with option B.", "B", "mcq"), ("The correct answer: B", "B", "mcq"),
    ("The answer is x^2 + 2*x + 1", "x**2+2*x+1", "expression"), ("so v² = u² + 2as", "u**2 + 2*a*s", "expression"),
    ("v^2 = 2as + u^2", "u**2 + 2*a*s", "expression"),
    ("1000 m", "1e+03 m", "numeric"), ("it is 1.0 × 10^3 m", "1e+03 m", "numeric"), ("about 10^3 m", "1e+03 m", "numeric"),
    ("that gives 1,000 m", "1e+03 m", "numeric"), ("so 4.2 × 10⁻³ mol", "0.0042 mol", "numeric"),
])
def test_leak_guard_catches_plain_disclosures(reply, key, kind):
    assert ai.leaks(reply, key, kind)


@pytest.mark.parametrize("reply,key,kind", [
    ("A force is a push or a pull.", "A: 3 N", "mcq"), ("Compare the options carefully.", "B", "mcq"),
    ("Which suvat equation has no t in it?", "u**2 + 2*a*s", "expression"),
    ("use g = 9.81 and u = 12", "1e+03 m", "numeric"), ("start from v = u + at", "19.6 m s-1", "numeric"),
])
def test_leak_guard_lets_hints_through(reply, key, kind):
    assert not ai.leaks(reply, key, kind)


@pytest.mark.parametrize("reply,key,answer", [
    ("so it is 3.75", "3.8 %", {"value": 3.75, "unit": "%", "sf_ok": [2]}),  # more figures than the key shows
    ("so it is 0.0253906", "0.025 g cm^-3", {"value": 0.025390625, "unit": "g cm^-3", "sf_ok": [2]}),
    ("about 0.025 kg", "0.0254 kg", {"value": 0.02539, "unit": "kg", "sf_ok": [2, 3]}),  # fewer: still marked right
    ("it comes to 12.25", "12.25", {"value": 12.25, "exact": True}),
])
def test_leak_guard_catches_the_answer_at_any_precision(reply, key, answer):
    assert ai.leaks(reply, key, "numeric", answer)


@pytest.mark.parametrize("reply,key,answer", [
    ("halve it: divide by 2", "1.96 m", {"value": 1.96, "unit": "m", "sf_ok": [3]}),  # "2" is 1 s.f., not the answer
    ("use g = 9.81 and t = 2.0", "19.6 m s-1", {"value": 19.62, "unit": "m s-1", "sf_ok": [2, 3]}),
    ("there are 12 of them", "12.25", {"value": 12.25, "exact": True}),  # an exact answer is not its rounding
])
def test_leak_guard_given_the_true_value_still_lets_hints_through(reply, key, answer):
    assert not ai.leaks(reply, key, "numeric", answer)


def test_overlapping_requests_respect_the_daily_cap(tmp_path, monkeypatch):  # B-017
    c = make(tmp_path, monkeypatch, cap=1)

    async def go():
        results = await asyncio.gather(c.reply("first"), c.reply("second"))
        await c.close()
        return results

    asyncio.run(go())
    assert c.today()["replies"] == 1 and c.last.status == "cap"


@pytest.mark.parametrize("tex,want", [  # published maths that reached the terminal as raw LaTeX
    (r"$k\ge3$", "k≥3"), (r"$20 \le t < 35$", "20≤t<35"), (r"$a\ne b$", "a≠b"),
    (r"$Q_3 + 1.5\times\text{IQR}$", "Q₃+1.5×IQR"),
    (r"$\text{frequency density}=\text{frequency}\div\text{class width}$", "frequency density=frequency÷class width"),
    (r"$1, 2, \ldots, n$", "1,2,…,n"), (r"$\begin{pmatrix}3\\-4\end{pmatrix}$", "(3; -4)"),
])
def test_terminal_maths_has_no_raw_latex_left(tex, want):
    assert to_terminal(tex) == want


def test_units_with_brace_exponents_are_left_readable():
    from tutor_app.texmath import pretty_units
    assert pretty_units("m s^-2") == "m s⁻²" and pretty_units("m^{-1}") == "m⁻¹"
    assert pretty_units("x^{1/2}") == "x^{1/2}" and pretty_units("m^{2.0}") == "m^{2.0}"
