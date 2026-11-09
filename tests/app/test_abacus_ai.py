import asyncio
import json
import urllib.error

from tutor_app import abacus_ai, abacus_models, config, tutor_ai
from tutor_app.abacus_ai import AbacusAI
from tutor_app.screens import model_choice_label
from tutorlib import challenge, challenge_gen


def with_key(monkeypatch, tmp_path, key="test-key"):
    monkeypatch.delenv("ABACUS_ROUTELLM_API_KEY", raising=False)
    monkeypatch.setattr(abacus_ai, "KEY_FILE", tmp_path / "key")
    if key:
        (tmp_path / "key").write_text(key + "\n")


def reply(text):
    return {"choices": [{"message": {"content": text}}], "usage": {"total_tokens": 3}}


def test_no_key_means_unavailable_with_how_to_add_it(monkeypatch, tmp_path):
    with_key(monkeypatch, tmp_path, key="")
    client = AbacusAI(system="s")
    assert not client.available and "~/.config/routellm/key" in client.message


def test_stream_keeps_history_and_sends_the_model_without_its_prefix(monkeypatch, tmp_path):
    with_key(monkeypatch, tmp_path)
    sent = []
    client = AbacusAI(system="be brief")
    monkeypatch.setattr(client, "_post", lambda body, timeout: sent.append(body) or reply("Hello there"))

    async def go():
        first = [c async for c in client.stream("hi", model="abacus:claude-sonnet-5-5")]
        second = [c async for c in client.stream("again", model="abacus:claude-sonnet-5-5")]
        return first, second
    first, second = asyncio.run(go())
    assert "".join(first) == "Hello there" and client.last.ok and client.last.text == "Hello there"
    assert sent[0]["model"] == "claude-sonnet-5-5" and sent[0]["messages"][0]["role"] == "system"
    assert [m["content"] for m in sent[1]["messages"][1:]] == ["hi", "Hello there", "again"]


def test_one_shot_reads_json_and_a_text_only_model_refuses_images(monkeypatch, tmp_path):
    with_key(monkeypatch, tmp_path)
    client = AbacusAI(system="s")
    monkeypatch.setattr(client, "_post", lambda body, timeout: reply('```json\n{"ok": true}\n```'))
    schema = {"type": "object", "properties": {"ok": {"type": "boolean"}}, "required": ["ok"]}
    data, result = asyncio.run(client.one_shot("mark", schema=schema, model="abacus:route-llm"))
    assert data == {"ok": True} and result.ok
    image = tmp_path / "q.png"
    image.write_bytes(b"\x89PNG")
    data, result = asyncio.run(client.one_shot("mark", schema=schema, model="abacus:moonshotai/Kimi-K3",
                                                images=[image]))
    assert data is None and "text only" in result.message


def test_a_refused_key_is_a_login_problem(monkeypatch, tmp_path):
    with_key(monkeypatch, tmp_path)
    client = AbacusAI(system="s")

    def refuse(request, timeout):
        raise urllib.error.HTTPError("u", 401, "no", {}, None)
    monkeypatch.setattr(abacus_ai.urllib.request, "urlopen", refuse)
    data, result = asyncio.run(client.one_shot("x", model="abacus:route-llm"))
    assert data is None and result.status == "login" and not client.available


def test_router_settings_and_challenge_know_the_abacus_models(monkeypatch, tmp_path):
    with_key(monkeypatch, tmp_path)
    ai = tutor_ai.TutorAI(tmp_path)
    assert isinstance(ai.api_client("abacus:route-llm"), AbacusAI) and ai.api_client("haiku") is None
    assert ai.available_for("abacus:gpt-6.1-sol")
    assert all(model in config.AI_MODELS for model in abacus_models.ABACUS_MODELS)
    assert model_choice_label("Abacus", "Kimi K3 (Abacus; text only)") == "Abacus · Kimi K3 (text only)"
    assert model_choice_label("Local", "Gemma 4 26B (local MLX)") == "Local · Gemma 4 26B (MLX)"
    assert "abacus:claude-opus-5-5" in challenge.MODELS
    assert challenge_gen._other("abacus:claude-opus-5-5") == "abacus:claude-sonnet-5-5"
    assert challenge_gen._other("opus") == "sonnet"
    assert json.dumps(challenge_gen.timeout_for("generate", "abacus:claude-opus-5-5", 9)) == "900"


SCHEMA = {"type": "object", "properties": {"ok": {"type": "boolean"}, "why": {"type": "string"}},
          "required": ["ok", "why"]}


def replies(monkeypatch, client, *texts, cut_first=False):
    sent, queue = [], list(texts)

    def post(body, timeout):
        sent.append(body)
        out = reply(queue.pop(0))
        if cut_first and len(sent) == 1:
            out["choices"][0]["finish_reason"] = "length"
        return out
    monkeypatch.setattr(client, "_post", post)
    return sent


def test_a_reply_that_is_not_the_json_asked_for_is_asked_for_again(monkeypatch, tmp_path):
    with_key(monkeypatch, tmp_path)
    client = AbacusAI(system="s")
    sent = replies(monkeypatch, client, "Sure! Here is my answer in words.", '{"ok": true}',
                   '{"ok": true, "why": "fine"}')
    data, result = asyncio.run(client.one_shot("mark", schema=SCHEMA, model="abacus:route-llm", timeout=120))
    assert data == {"ok": True, "why": "fine"} and result.ok and len(sent) == 3
    assert "ONLY the complete JSON" in sent[1]["messages"][-1]["content"]
    assert "every required field" in sent[2]["messages"][-1]["content"]


def test_a_cut_off_reply_is_retried_more_briefly(monkeypatch, tmp_path):
    with_key(monkeypatch, tmp_path)
    client = AbacusAI(system="s")
    sent = replies(monkeypatch, client, '{"ok": true, "why": "long long', '{"ok": true, "why": "short"}',
                   cut_first=True)
    data, result = asyncio.run(client.one_shot("mark", schema=SCHEMA, model="abacus:claude-opus-5-5", timeout=120))
    assert data["why"] == "short" and "cut off" in sent[1]["messages"][-1]["content"]
    assert sent[0]["max_tokens"] == abacus_ai.MAX_TOKENS


def test_it_gives_up_with_a_clear_message_after_three_tries(monkeypatch, tmp_path):
    with_key(monkeypatch, tmp_path)
    client = AbacusAI(system="s")
    sent = replies(monkeypatch, client, "no", "still no", "nope")
    data, result = asyncio.run(client.one_shot("mark", schema=SCHEMA, model="abacus:route-llm", timeout=120))
    assert data is None and not result.ok and "incomplete JSON" in result.message and len(sent) == 3


def test_a_latex_backslash_written_once_is_still_read(monkeypatch, tmp_path):
    with_key(monkeypatch, tmp_path)
    client = AbacusAI(system="s")
    sent = replies(monkeypatch, client, '{"ok": true, "why": "use \\frac{1}{2}kx^2 and \\int F dx"}')
    data, result = asyncio.run(client.one_shot("mark", schema=SCHEMA, model="abacus:route-llm", timeout=120))
    assert result.ok and "frac{1}{2}" in data["why"] and len(sent) == 1
