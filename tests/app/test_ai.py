import asyncio
import json
import sys
from pathlib import Path

import pytest

from tutor_app import ai
from tutor_app.texmath import to_terminal

FAKE = str(Path(__file__).with_name("fake_claude.py"))


def make(tmp_path, monkeypatch, mode="ok"):
    monkeypatch.setenv("FAKE_CLAUDE_MODE", mode)
    monkeypatch.setenv("FAKE_CLAUDE_LOG", str(tmp_path / "argv.log"))
    return ai.Claude(tmp_path, binary=FAKE, usage_file=tmp_path / "usage.json")


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


def test_replies_are_not_capped(tmp_path, monkeypatch):
    """Asked by the learner: no limit of the tutor's own on AI replies in a day."""
    c = make(tmp_path, monkeypatch)
    for _ in range(4):
        collect(c, "x")
    assert c.last.ok and c.today()["replies"] == 4 and c.available and not hasattr(c, "daily_cap")


def test_a_settings_file_saved_with_the_old_cap_still_loads(tmp_path):
    from tutor_app import config
    (tmp_path / ".tutor").mkdir()
    (tmp_path / ".tutor/app_settings.json").write_text('{"daily_cap": 5, "minutes": 30}')
    s = config.Settings.load(tmp_path)
    assert s.minutes == 30 and not hasattr(s, "daily_cap")


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
    (r"$v^2=u^2+2as$", "v² = u² + 2as"),
    (r"$\tfrac12at^2$", "at²"),
    (r"$9.81\ \mathrm{m\,s^{-2}}$", "m s⁻²"),
    (r"$\ce{H2SO4}$", "H₂SO₄"),
    (r"$0.48\%$", "0.48%"),
    ("plain text", "plain text"),
    (r"$0.348\to0.3$", "0.348 → 0.3"),
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
    ("the energy is 10³ J", "1000 J", "numeric"), ("so 10⁻³ m", "0.001 m", "numeric"),  # B-036: not 103 and 10
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
    ("roughly 2400 N", "2380 N", {"value": 2375.0, "unit": "N", "sf_ok": [2, 3]}),  # 2 s.f. written with zeros
])
def test_leak_guard_catches_the_answer_at_any_precision(reply, key, answer):
    assert ai.leaks(reply, key, "numeric", answer)


@pytest.mark.parametrize("reply,key,answer", [
    ("halve it: divide by 2", "1.96 m", {"value": 1.96, "unit": "m", "sf_ok": [3]}),  # "2" is 1 s.f., not the answer
    ("use g = 9.81 and t = 2.0", "19.6 m s-1", {"value": 19.62, "unit": "m s-1", "sf_ok": [2, 3]}),
    ("there are 12 of them", "12.25", {"value": 12.25, "exact": True}),  # an exact answer is not its rounding
    ("start from the 96 N weight", "100 N", {"value": 100.5, "unit": "N", "sf_ok": [2, 3]}),  # 96 is not 100.5 rounded
])
def test_leak_guard_given_the_true_value_still_lets_hints_through(reply, key, answer):
    assert not ai.leaks(reply, key, "numeric", answer)


@pytest.mark.parametrize("tex,want", [  # published maths that reached the terminal as raw LaTeX
    (r"$k\ge3$", "k ≥ 3"), (r"$20 \le t < 35$", "20 ≤ t < 35"), (r"$a\ne b$", "a ≠ b"),
    (r"$Q_3 + 1.5\times\text{IQR}$", "Q₃ + 1.5 × IQR"),
    (r"$\text{frequency density}=\text{frequency}\div\text{class width}$", "frequency density = frequency ÷ class width"),
    (r"$1, 2, \ldots, n$", "1,2,…,n"), (r"$\begin{pmatrix}3\\-4\end{pmatrix}$", "(3; −4)"),
])
def test_terminal_maths_has_no_raw_latex_left(tex, want):
    assert to_terminal(tex) == want


def test_units_with_brace_exponents_are_left_readable():
    from tutor_app.texmath import pretty_units
    assert pretty_units("m s^-2") == "m s⁻²" and pretty_units("m^{-1}") == "m⁻¹"
    assert pretty_units("x^{1/2}") == "x^{1/2}" and pretty_units("m^{2.0}") == "m^{2.0}"


def test_the_tutor_is_told_what_you_answered_and_why_a_mark_was_lost(tmp_path):
    """From the learner's lesson: asked about a marked answer, the AI did not know what they had written."""
    import random
    from fixtures import make_vault
    from tutor_app import prompts
    from tutorlib import session, store
    t = session.Tutor(store.Vault(make_vault(tmp_path)), rng=random.Random(0))
    t.start("long", minutes=20, focus=["9702-2.1.4"])
    item = next(i for i in t.packs.items_for("9702-2.1.4") if i["id"] == "9702-2.1-i03")  # 4.0 m s-2, 2 or 3 s.f.
    n = t._present(item, block="practice", phase=None)["n"]
    t.answer(f"{n} = 4.0 ~3")
    told = prompts.context(t)
    assert f"Marked earlier in this session, Q{n}: " in told
    assert "They answered: 4.0 (right value but a mark lost (missing unit)); the answer is 4.00 m s-2." in told
    m = t._present(item, block="practice", phase=None)["n"]
    t.answer(f"{m}?")
    assert "They answered: don't know (wrong); the answer is 4.00 m s-2." in prompts.context(t)


def test_the_tutor_is_told_what_just_happened_in_the_session(tmp_path):
    """Asked by the learner: "what's the correct full answer in this case?" got "no question was asked". Once the
    session had moved on, the question just marked was no longer in what the AI is told."""
    import random
    from datetime import datetime
    from fixtures import make_vault
    from tutor_app import prompts
    from tutorlib import session, store
    t = session.Tutor(store.Vault(make_vault(tmp_path)), rng=random.Random(0),
                      now=lambda: datetime.fromisoformat("2026-09-29T17:00:00+08:00"))
    assert "none" in prompts.context(t)  # nothing answered yet, no session
    t.start("test", minutes=30, focus=["9702-2.1"])
    act = t.next()
    stems = [t.session["presented"][str(q["n"])]["inst"]["stem"] for q in act["items"]]
    t.answer(", ".join(f"{q['n']}?" for q in act["items"]))
    t.next()  # the session moves on
    told = prompts.context(t)
    assert all(s[:30] in told for s in stems) and "don't know" in told and "the answer is" in told
    t.session["now"] = {"activity": "worked", "problem": "A car accelerates from rest.", "revealed": 1,
                        "steps": [{"do": "List s, u, v, a, t"}, {"do": "Use the secret second step"}]}
    told = prompts.context(t)
    assert "A car accelerates" in told and "List s, u, v, a, t" in told and "secret second step" not in told
    t.end()
    assert stems[0][:30] in prompts.context(t)  # from the menu afterwards: the last questions answered


def test_the_plans_limits_are_shown_as_what_is_left(tmp_path, monkeypatch):
    """Asked by the learner: what is left of the plan's limit, next to the tokens. Then: the week only, since the
    five-hour figure was nearly always unknown."""
    import json
    from tutor_app import mac
    c = make(tmp_path, monkeypatch)
    lines = [json.dumps({"type": "rate_limit_event", "rate_limit_info": {
                 "rateLimitType": "five_hour", "utilization": 0.15, "resetsAt": 4102444800}}).encode() + b"\n",
             json.dumps({"type": "result", "result": "ok", "usage": {}}).encode() + b"\n"]

    class Out:
        async def readline(self):
            return lines.pop(0) if lines else b""

    class Proc:
        stdout = Out()

    async def go():
        async for _ in c._read(Proc(), []):
            pass
    asyncio.run(go())
    assert c.limits["five_hour"]["used"] == 15  # what Claude tells this app itself is exact
    note = tmp_path / "claude.json"
    note.write_text(json.dumps({"cachedUsageUtilization": {"fetchedAtMs": 1, "utilization": {"limits": [
        {"kind": "session", "percent": 40, "is_active": True, "resets_at": "2099-01-01T00:00:00+00:00"},
        {"kind": "weekly_all", "percent": 92, "is_active": True, "resets_at": "2099-01-01T00:00:00+00:00"}]}}}))
    noted = mac.claude_limits(note)
    assert noted["seven_day"]["used"] == 92 and mac.claude_limits(tmp_path / "missing.json") == {}
    assert c.limits_text(noted) == "week ~8% left"  # Claude Code's own note can lag: marked ~
    c.limits["seven_day"] = {"used": 93, "resets": 4102444800}
    assert c.limits_text(noted) == "week 7% left"  # what Claude told this app itself is exact
    assert ai.Claude(tmp_path, binary=FAKE).limits_text({}) == ""  # nothing known: nothing shown


def _script(tmp_path, body, mode=0o755):
    # a shebang cannot hold a path with spaces (this project's folder has them): run the body through a shell wrapper
    body_file = tmp_path / "slow_claude_body.py"
    body_file.write_text(body)
    p = tmp_path / "slow_claude"
    p.write_text(f'#!/bin/sh\nexec "{sys.executable}" "{body_file}" "$@"\n')
    p.chmod(mode)
    return p


def test_cancelling_a_one_shot_cancels_the_caller(tmp_path):
    c = ai.Claude(tmp_path, binary=str(_script(tmp_path, "import time\ntime.sleep(30)\n")))
    async def go():
        t = asyncio.ensure_future(c.one_shot("x"))
        await asyncio.sleep(0.5)
        t.cancel()
        await asyncio.wait([t])
        return t.cancelled()
    assert asyncio.run(go())


def test_a_binary_that_cannot_start_is_an_error_not_a_crash(tmp_path):
    c = ai.Claude(tmp_path, binary=str(_script(tmp_path, "pass\n", mode=0o644)))
    async def go():
        data, res = await c.one_shot("x")
        return data, res, await c.reply("x")
    data, res, res2 = asyncio.run(go())
    assert data is None and not res.ok and not res2.ok


def test_an_unwritable_usage_file_does_not_lose_the_reply(tmp_path, monkeypatch):
    monkeypatch.setenv("FAKE_CLAUDE_MODE", "ok")
    (tmp_path / "usage.json").mkdir()  # cannot be read or written as a file
    c = ai.Claude(tmp_path, binary=FAKE, usage_file=tmp_path / "usage.json")
    assert "".join(collect(c, "hello")).startswith("Reply 1: hello") and c.last.ok


def test_a_huge_stream_line_is_a_failed_reply_not_a_crash(tmp_path):
    big = _script(tmp_path, "import sys\nsys.stdin.readline()\nsys.stdout.write('x' * 5_000_000 + '\\n')\n"
                            "sys.stdout.flush()\nimport time\ntime.sleep(5)\n")
    c = ai.Claude(tmp_path, binary=str(big))
    async def go():
        res = await c.reply("x")
        await c.close()
        return res
    assert not asyncio.run(go()).ok
