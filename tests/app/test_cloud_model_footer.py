import asyncio

from tutor_app import abacus_ai, tutor_ai
from tutor_app.abacus_ai import AbacusAI


def label(**p):
    from tutor_app.app import TutorApp
    return TutorApp.cloud_label(p)


def test_cloud_labels_name_the_model_and_the_routed_model():
    assert label(model="sonnet") == "Claude Sonnet"
    assert label(model="codex:gpt-6.1-sol") == "GPT-6.1-Sol (ChatGPT)"
    assert label(model="abacus:claude-opus-5-5") == "Claude Opus 5.5 (Abacus)"
    assert label(model="abacus:route-llm", routed="gpt-6-luna") == "RouteLLM → GPT-6-Luna"
    assert label(model="abacus:route-llm", routed="some/new-model") == "RouteLLM → some/new-model"
    assert label(model="abacus:route-llm", routed="") == "RouteLLM → model not reported"


def test_abacus_stream_reports_the_routed_model_and_the_router_adds_time(monkeypatch, tmp_path):
    monkeypatch.setenv("ABACUS_ROUTELLM_API_KEY", "k")
    seen = []

    def post(self, body, timeout):
        return {"choices": [{"message": {"content": '{"blocks": [{"kind": "paragraph", "text": "Hi"}]}'}}], "model": "gpt-6-luna",
                "usage": {"output_tokens": 6}}
    monkeypatch.setattr(AbacusAI, "_post", post)

    async def go():
        ai = tutor_ai.TutorAI(tmp_path)
        ai.on_result = seen.append
        [x async for x in ai.stream("hello", model="abacus:route-llm")]
        return ai.last
    last = asyncio.run(go())
    p = last.performance
    assert p["cloud"] and p["model"] == "abacus:route-llm" and p["routed"] == "gpt-6-luna"
    assert p["output_tokens"] == 6 and p["total_seconds"] >= 0 and seen == [last]


def test_a_failed_cloud_reply_shows_no_footer(monkeypatch, tmp_path):
    monkeypatch.delenv("ABACUS_ROUTELLM_API_KEY", raising=False)
    monkeypatch.setattr(abacus_ai, "KEY_FILE", tmp_path / "none")
    seen = []

    async def go():
        ai = tutor_ai.TutorAI(tmp_path)
        ai.on_result = seen.append
        [x async for x in ai.stream("hello", model="abacus:route-llm")]
    asyncio.run(go())
    assert seen == []


def test_the_footer_text_is_the_model_then_speed_time_and_tokens_and_leaves_Now_md_alone(tmp_path, monkeypatch):
    from test_tui import app_for
    from tutor_app import ai
    app, vault = app_for(tmp_path, monkeypatch)

    async def go():
        async with app.run_test(size=(120, 40)) as pilot:
            await pilot.pause()
            before = (vault / "Now.md").read_text() if (vault / "Now.md").exists() else None
            notices = []
            monkeypatch.setattr(app, "notify", lambda message, **kwargs: notices.append(message))
            app.show_local_performance(ai.Result(performance={
                "cloud": True, "model": "abacus:route-llm", "routed": "gpt-6-luna", "total_seconds": 3.2,
                "output_tokens": 64, "tokens_per_second": 20.0}))
            assert notices == ["RouteLLM → GPT-6-Luna · 20.0 tok/s · total 3.2s · 64 tokens"]
            after = (vault / "Now.md").read_text() if (vault / "Now.md").exists() else None
            assert after == before
            await app.ai.close()
    asyncio.run(go())


def test_an_incomplete_cloud_reply_is_asked_for_once_more(monkeypatch, tmp_path):
    from tutor_app.ai import Result
    from tutor_app.codex_ai import CodexAI
    calls = []

    async def one_shot(self, prompt, **kwargs):
        calls.append(kwargs["timeout"])
        if len(calls) == 1:
            return None, Result(ok=False, status="error", message="ChatGPT returned incomplete JSON; try again.")
        return {"ok": True}, Result()
    monkeypatch.setattr(CodexAI, "one_shot", one_shot)
    monkeypatch.setattr(CodexAI, "available", property(lambda self: True))

    async def go():
        ai = tutor_ai.TutorAI(tmp_path)
        return await ai.one_shot("x", schema={"type": "object"}, model="codex:gpt-6-luna", timeout=120)
    data, result = asyncio.run(go())
    assert data == {"ok": True} and result.ok and len(calls) == 2 and calls[1] < calls[0]
    calls.clear()
    assert not tutor_ai.TutorAI._worth_retrying(Result(ok=False, status="login", message="incomplete"), 100)
    assert not tutor_ai.TutorAI._worth_retrying(Result(ok=False, status="error", message="incomplete"), 10)
