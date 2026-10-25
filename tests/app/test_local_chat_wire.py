"""Real HTTP chat envelopes never become prose, speech, history or formatter input."""
import asyncio
import json

import pytest

from test_local_runtime import event, models, server
from tutor_app import ai, local_ai
from tutor_app.local_ai import LocalAI


@pytest.mark.parametrize("model", ["ollama:qwen3.8:27b", "ollama:gemma4:26b-a4b-it-qat", "ollama:gemma4:e4b"])
def test_local_question_changes_topic_and_only_decoded_reply_reaches_the_caller(models, monkeypatch, model):
    if model.endswith(":e4b"):
        (models / "manifests/registry.ollama.ai/library/gemma4/e4b").write_text("{}")
    prompt = "CONTEXT\nJust marked: compare ionic radii.\n\nSTUDENT ASKS: What are the 9701 organic formulae?"
    reply = r"Alkanes: $C_nH_{2n+2}$." + '\n\nLiteral code: `{"reply":"example"}`.'
    wire = json.dumps({"reply": reply})

    async def go():
        async with server(monkeypatch, [[event(wire[:11]), event(wire[11:], done=True)]], raw_chat=True) as (requests, _):
            client = LocalAI(ai.SYSTEM)
            output = "".join([part async for part in client.stream(prompt, model=model)])
            assert output == reply and client.last.text == reply and client.last.ok
            payload = requests[0]
            assert payload["format"]["properties"] == {"reply": {"type": "string"}}
            assert payload["messages"][-1]["content"] == prompt
            system = payload["messages"][0]["content"]
            assert "not an exclusive knowledge source" in system
            assert "never state its answer" in system
            assert "Ground everything in the CONTEXT" not in system
            assert client._history[(model, False, False)][-1]["content"] == reply
            await client.close()
    asyncio.run(go())


def test_chat_speech_is_separate_and_literal_json_is_not_guessed_or_stripped(models, monkeypatch):
    reply = '{"reply":"a literal object","speech":"literal content"}'
    speech = "Here is the object you requested."
    wire = json.dumps({"speech": speech, "reply": reply})

    async def go():
        async with server(monkeypatch, [[event(wire[:22]), event(wire[22:], done=True)]], raw_chat=True) as (requests, _):
            client = LocalAI(ai.SYSTEM, speech=True)
            output = "".join([part async for part in client.stream("Show this JSON literally.", model="ollama:qwen3.8:27b")])
            assert output == reply and client.last.text == reply
            assert client.last.speech == speech and speech not in output
            assert requests[0]["format"]["required"] == ["reply", "speech"]
            await client.close()
    asyncio.run(go())


@pytest.mark.parametrize("wire", ['{reply:"bad"}', '{"reply":42}', '{"reply":"one","reply":"two"}', '```json\n{"reply":"bad"}\n```'])
def test_bad_chat_transport_is_an_error_and_never_successful_history(models, monkeypatch, wire):
    async def go():
        async with server(monkeypatch, [[event(wire, done=True)]], raw_chat=True):
            client = LocalAI(ai.SYSTEM)
            _ = [part async for part in client.stream("Question", model="ollama:qwen3.8:27b")]
            assert not client.last.ok and not client._history
            assert "reply" in client.last.message.lower()
            await client.close()
    asyncio.run(go())


def test_thinking_time_is_measured_without_retaining_hidden_text(models, monkeypatch):
    async def go():
        async with server(monkeypatch, [[{"message": {"thinking": "Private reasoning"}, "done": False},
                                         event('{"reply":"Visible"}', done=True)]], raw_chat=True):
            client = LocalAI(ai.SYSTEM)
            output = "".join([part async for part in client.stream("Question", model="ollama:qwen3.8:27b", think=True)])
            assert output == "Visible" and client.last.ok
            assert client.last.performance["thinking_seconds"] > 0
            assert "Private reasoning" not in repr(client._history)
            assert "Private reasoning" not in repr(client.progress_for("ollama:qwen3.8:27b"))
            await client.close()
    asyncio.run(go())


def test_qwen_strength_selector_explains_maximum_effort(tmp_path, monkeypatch):
    from test_tui import app_for
    from textual.widgets import Select
    app, _ = app_for(tmp_path, monkeypatch)

    async def go():
        async with app.run_test(size=(120, 40)) as pilot:
            await pilot.pause()
            app.action_settings()
            await pilot.pause()
            app.screen.query_one("#ai_ask_model", Select).value = "ollama:qwen3.8:27b"
            await pilot.pause()
            strength = app.screen.query_one("#ai_ask_effort", Select)
            assert strength.display and strength.value == "off"
            assert "xhigh" in str(strength.tooltip) and "minutes" in str(strength.tooltip)
            assert app.settings.ai_for("ask") == ("haiku", False)
            await app.ai.close()
    asyncio.run(go())


def test_observed_thinking_duration_is_terminal_only(tmp_path, monkeypatch):
    from test_tui import app_for
    app, vault = app_for(tmp_path, monkeypatch)

    async def go():
        async with app.run_test(size=(120, 40)) as pilot:
            await pilot.pause()
            before = (vault / "Now.md").read_text() if (vault / "Now.md").exists() else None
            notices = []
            monkeypatch.setattr(app, "notify", lambda message, **kwargs: notices.append(message))
            app.show_local_performance(ai.Result(performance={"model": "ollama:qwen3.8:27b", "thinking_seconds": 7.5}))
            assert any("thinking 7.5s" in note for note in notices)
            after = (vault / "Now.md").read_text() if (vault / "Now.md").exists() else None
            assert after == before
            await app.ai.close()
    asyncio.run(go())


def test_thinking_timeout_explains_the_limit_without_switching_thinking_off(models, monkeypatch):
    monkeypatch.setattr(local_ai, "CHAT_TIMEOUT", 0.08, raising=False)

    async def go():
        async with server(monkeypatch, [[{"message": {"thinking": "Private reasoning"}, "done": False}, "wait"]],
                          raw_chat=True) as (requests, _):
            client = LocalAI(ai.SYSTEM)
            async def consume():
                return [part async for part in client.stream("Question", model="ollama:qwen3.8:27b", think=True)]
            await asyncio.wait_for(consume(), 1)
            assert not client.last.ok and "still thinking" in client.last.message
            assert "Think first" in client.last.message and not client._history
            assert requests[0]["think"] == "xhigh"
            await client.close()
    asyncio.run(go())
