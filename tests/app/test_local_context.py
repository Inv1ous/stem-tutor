"""Local request assembly never truncates current evidence or drops half a turn."""
import asyncio
import base64
import json

import pytest

from test_local_runtime import event, models, server
from tutor_app import local_models
from tutor_app.local_ai import LocalAI

MODEL = "ollama:gemma4:26b-a4b-it-qat"
WIRE = '{"blocks":[{"kind":"paragraph","text":"Answer."}]}'


def test_oldest_complete_pairs_pruned_and_current_request_preserved(models, monkeypatch):
    async def go():
        monkeypatch.setitem(local_models.CONTEXT_LENGTH, MODEL, 4096)
        async with server(monkeypatch, [[event(WIRE, done=True)]], raw_chat=True) as (requests, _):
            client = LocalAI("Brief", document=True)
            history = []
            for n in range(7):
                history += [{"role": "user", "content": f"Old {n}:" + "x" * 1500},
                            {"role": "assistant", "content": WIRE}]
            client._history[(MODEL, False, False)] = history
            prompt = "Use ALL supplied mark points: " + "α+β=γ; " * 30
            _ = [p async for p in client.stream(prompt, model=MODEL)]
            assert client.last.ok
            messages = requests[0]["messages"]
            assert messages[-1]["content"] == prompt
            retained = messages[1:-1]
            assert len(retained) % 2 == 0 and 0 < len(retained) < len(history)
            assert retained == history[-len(retained):]
            assert len(client._history[(MODEL, False, False)]) == len(retained) + 2
            await client.close()
    asyncio.run(go())


def test_oversized_current_request_fails_before_preload_without_truncating(models, monkeypatch):
    async def go():
        async with server(monkeypatch, [], raw_chat=True, record_preloads=True) as (requests, _):
            client = LocalAI("Brief", document=True)
            prompt = "Exact assessment evidence. " * 10000
            assert [p async for p in client.stream(prompt, model=MODEL)] == []
            assert not client.last.ok and not requests and not client._history
            assert "current request" in client.last.message.lower()
            await client.close()
    asyncio.run(go())


def test_retained_memory_is_bounded_and_reset_clears_contract_history(models, monkeypatch):
    async def go():
        async with server(monkeypatch, [[event(WIRE, done=True)] for _ in range(35)], raw_chat=True) as (requests, _):
            client = LocalAI("Brief", document=True)
            for n in range(35):
                _ = [p async for p in client.stream(f"Question {n}", model=MODEL)]
                assert client.last.ok
            assert len(client._history[(MODEL, False, False)]) <= 16
            assert requests[-1]["messages"][-1]["content"] == "Question 34"
            await client.reset()
            assert not client._history and not client._shown
            await client.close()
    asyncio.run(go())


def test_current_image_reattached_when_old_image_pair_pruned(models, monkeypatch, tmp_path):
    async def go():
        image = tmp_path / "question.png"
        image.write_bytes(b"exact image pixels")
        async with server(monkeypatch, [[event(WIRE, done=True)] for _ in range(11)], raw_chat=True) as (requests, _):
            client = LocalAI("Brief", document=True)
            _ = [p async for p in client.stream("Read", image=image, model=MODEL)]
            for n in range(9):
                _ = [p async for p in client.stream(f"Question {n}", model=MODEL)]
            _ = [p async for p in client.stream("Return to this image", image=image, model=MODEL)]
            assert client.last.ok
            assert requests[-1]["messages"][-1]["images"] == [base64.b64encode(image.read_bytes()).decode()]
            assert not any(m.get("images") for m in requests[-1]["messages"][1:-1])
            await client.close()
    asyncio.run(go())


def test_budget_counts_system_schema_and_images_without_changing_native_context():
    from tutor_app.local_context import ContextError, select_history
    user = {"role": "user", "content": "Preserve me."}
    with pytest.raises(ContextError, match="current request"):
        select_history("x" * 3000, {"properties": {"x": {"description": "y" * 3000}}},
                       user, [], context=3000)
    with pytest.raises(ContextError, match="current request"):
        select_history("Brief", {}, {**user, "images": ["small image"]}, [], context=2200)
    assert user == {"role": "user", "content": "Preserve me."}


def test_optional_history_prompt_limit_prunes_oldest_complete_pairs():
    from tutor_app.local_context import select_history
    history = [{"role": role, "content": f"{tag}{n}"} for n in range(3)
               for role, tag in (("user", "u"), ("assistant", "a"))]
    # Hand-counted estimate: mandatory material is 52 tokens; each complete pair is 34.
    selected = select_history("Brief", {}, {"role": "user", "content": "Now"}, history,
                              context=8192, history_prompt_limit=120)
    assert selected == history[2:]
    assert history[0]["content"] == "u0" and len(history) == 6


@pytest.mark.parametrize("history_prompt_limit", [0, 20, 2048])
def test_current_sources_above_optional_history_limit_remain_complete(history_prompt_limit):
    from tutor_app.local_context import select_history
    current = {"role": "user", "content": "MARK SCHEME: " + "x" * 6000 + " α+β=γ; 1.2 mol dm⁻³"}
    schema = {"type": "object", "properties": {"blocks": {"type": "array"}}}
    history = [{"role": "user", "content": "Old question"}, {"role": "assistant", "content": WIRE}]
    original = json.dumps({"schema": schema, "current": current, "history": history}, ensure_ascii=False)
    assert select_history("Brief", schema, current, history, context=8192,
                          history_prompt_limit=history_prompt_limit) == []
    assert json.dumps({"schema": schema, "current": current, "history": history}, ensure_ascii=False) == original


def test_optional_limit_does_not_bypass_the_normal_physical_context_budget():
    from tutor_app.local_context import ContextError, select_history
    with pytest.raises(ContextError, match="current request"):
        select_history("Brief", {}, {"role": "user", "content": "x" * 20000}, [],
                       context=8192, history_prompt_limit=2048)


def test_no_optional_history_limit_preserves_normal_context_selection():
    from tutor_app.local_context import select_history
    history = [{"role": "user", "content": "Old question"}, {"role": "assistant", "content": WIRE}]
    assert select_history("Brief", {}, {"role": "user", "content": "Now"}, history,
                          context=8192, history_prompt_limit=None) == history


@pytest.mark.parametrize("think", [False, "low", "medium", "xhigh"])
def test_qwen_optional_history_budget_preserves_current_sources_and_native_payload(models, monkeypatch, think):
    async def go():
        qwen = "ollama:qwen3.8:27b"
        source = "CURRENT MARK SCHEME: " + "Exact supplied marking evidence. " * 190 + "α+β=γ; 1.2 mol dm⁻³"
        history = [{"role": role, "content": content} for n in range(6)
                   for role, content in (("user", f"Old question {n}:" + "x" * 800), ("assistant", WIRE))]
        async with server(monkeypatch, [[event(WIRE, done=True)], [event(WIRE, done=True)]],
                          raw_chat=True, record_preloads=True) as (requests, _):
            client = LocalAI("Brief", document=True)
            client._history[(qwen, local_models.thinking_value(qwen, think), False)] = list(history)
            client._history[(MODEL, False, False)] = list(history)
            _ = [p async for p in client.stream(source, model=qwen, think=think)]
            assert client.last.ok, client.last.message
            _ = [p async for p in client.stream(source, model=MODEL)]
            assert client.last.ok, client.last.message
            preload, payload, other_preload, other_payload = requests
            assert len(payload["messages"]) == 2  # mandatory material exceeds the optional history limit
            assert len(other_payload["messages"]) > 2
            assert payload["messages"][-1] == {"role": "user", "content": source}
            assert other_payload["messages"][-1] == payload["messages"][-1]
            assert payload["format"] == other_payload["format"]
            assert payload["messages"][0] == other_payload["messages"][0]
            assert preload["messages"] == [] and other_preload["messages"] == []
            assert payload["think"] == think and "think" not in preload
            assert "options" not in payload and "options" not in preload
            assert not any(k in payload for k in ("num_batch", "num_predict", "temperature", "top_p"))
            assert "num_ctx" not in other_payload.get("options", {}) or other_payload["options"]["num_ctx"] == 8192
            await client.close()
    asyncio.run(go())


def test_optional_history_pruning_reattaches_current_image(models, monkeypatch, tmp_path):
    monkeypatch.setattr(local_models, "HISTORY_PROMPT_LIMIT", {MODEL: 0}, raising=False)
    async def go():
        image = tmp_path / "current.png"
        image.write_bytes(b"Exact current pixels")
        async with server(monkeypatch, [[event(WIRE, done=True)], [event(WIRE, done=True)]], raw_chat=True) as (requests, _):
            client = LocalAI("Brief", document=True)
            for _ in range(2):
                _ = [part async for part in client.stream("Use every mark point.", image=image, model=MODEL)]
                assert client.last.ok
            assert len(requests[-1]["messages"]) == 2
            assert requests[-1]["messages"][-1]["images"] == [base64.b64encode(image.read_bytes()).decode()]
            await client.close()
    asyncio.run(go())


def test_qwen_exhaustion_never_introduces_automatic_16k_context_retry(models, monkeypatch):
    async def go():
        exhausted = {"message": {"thinking": "Private reasoning"}, "done": True, "done_reason": "length"}
        async with server(monkeypatch, [[exhausted]], raw_chat=True, record_preloads=True) as (requests, _):
            client = LocalAI("Brief", document=True)
            _ = [part async for part in client.stream("Question", model="ollama:qwen3.8:27b", think="low")]
            assert not client.last.ok and not client._history
            assert len(requests) == 2 and requests[0]["messages"] == []
            assert requests[1]["think"] == "low"
            assert "num_ctx" not in requests[0].get("options", {})
            assert "num_ctx" not in requests[1].get("options", {})
            assert not client._contexts
            await client.close()
    asyncio.run(go())
