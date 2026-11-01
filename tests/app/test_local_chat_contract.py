"""Local chat interprets lesson context without changing other request contracts."""
import asyncio
import json
from pathlib import Path

import pytest

from tutor_app import ai, tutor_ai


def test_recent_lesson_context_does_not_restrict_the_students_current_topic():
    from tutor_app.local_chat import chat_system

    brief = chat_system(ai.SYSTEM)
    assert "Ground everything in the CONTEXT you are given" not in brief
    words = " ".join(brief.split())
    assert "CONTEXT includes recent study background" in words
    assert "not an exclusive knowledge source" in words
    assert "current question" in words and "new topic" in words
    assert "using A-Level knowledge" in words
    assert "if you are not sure of a fact or coverage, say so plainly" in words


def test_local_chat_keeps_open_question_protection_and_visual_writing():
    from tutor_app.local_chat import chat_system

    brief = chat_system(ai.SYSTEM)
    assert "never state its answer, option letter or final value; give a nudge instead" in brief
    assert "one useful nudge without its final answer" in brief
    assert "Match detail to the task, not a fixed word limit" in brief
    assert "conversational Markdown inside the reply string" in brief
    assert "human-facing prose fields only; keep the requested JSON structure" not in brief
    assert "Put a real blank line between logical blocks" in brief
    assert "well-formed Markdown and canonical LaTeX" in brief


def test_local_chat_fulfils_the_current_request_in_its_named_subject_and_form():
    from tutor_app.local_chat import chat_system

    brief = chat_system(ai.SYSTEM)
    assert "Answer the current request in its requested form" in brief
    assert "list actual named items or formulae" in brief
    assert "rather than general study advice" in brief
    assert "Interpret terms in the named subject" in brief
    assert "Unrelated recent lesson topics must not redirect the answer" in brief
    assert "Match detail to the task, not a fixed word limit" in brief


@pytest.mark.parametrize("speech", [False, True])
def test_local_chat_uses_one_reply_string_even_for_requested_literal_json_or_code(speech):
    from tutor_app.local_chat import chat_system

    brief = chat_system(ai.SYSTEM, speech=speech)
    assert "outer JSON object" in brief
    assert "reply string" in brief and "Markdown" in brief
    assert "literal JSON or code" in brief and "inside the reply string" in brief
    assert "[[SPEECH]]" not in brief
    assert ai.SPEECH_RULE not in brief
    if speech:
        assert "speech field" in brief and "plain spoken English" in brief
        assert "no symbols, LaTeX, Markdown or lists" in brief
    else:
        assert "Do not add a speech field" in brief
        assert "plain spoken English" not in brief


def test_local_chat_only_rewrites_the_known_default_instructions():
    from tutor_app.local_chat import chat_system

    custom = "Custom tutor: use only the supplied source. Keep literal {reply: 'example'} intact."
    assert chat_system(custom).startswith(custom + "\n\n")
    original = ai.SYSTEM.encode()
    chat_system(ai.SYSTEM, speech=True)
    assert ai.SYSTEM.encode() == original
    assert "CONTEXT includes recent study background" in ai.SYSTEM
    assert ai.VISUAL_BRIEF in ai.SYSTEM


def test_local_structured_marking_keeps_exclusive_grounding_and_its_own_schema(monkeypatch):
    from tutor_app.local_ai import LocalAI
    from tutor_app.local_chat import chat_system

    schema = {"type": "object", "properties": {"feedback": {"type": "string"}}, "required": ["feedback"]}
    payloads = []

    async def go():
        client = LocalAI(ai.SYSTEM)
        monkeypatch.setattr(client, "_check", lambda model: "qwen3.8:27b")

        async def events(payload, timeout, model):
            payloads.append(payload)
            yield {"message": {"content": '{"feedback":"Good."}'}, "done": True}

        monkeypatch.setattr(client, "_chat_events", events)
        chat_system(client.system, speech=True)
        data, result = await client.one_shot("Mark only against the supplied points.", schema=schema,
                                              model="ollama:qwen3.8:27b")
        assert result.ok and data == {"feedback": "Good."}
        await client.close()

    asyncio.run(go())
    assert payloads[0]["messages"][0]["content"].encode() == ai.SYSTEM.encode()
    assert payloads[0]["format"] == schema
    assert "Local chat response" not in payloads[0]["messages"][0]["content"]


@pytest.mark.parametrize("provider", ["claude", "codex"])
@pytest.mark.parametrize("speech", [False, True])
def test_cloud_chat_uses_shared_document_without_changing_route_or_question(tmp_path, monkeypatch, provider, speech):
    """Native document output intentionally changes format; model routing and question stay intact."""
    from tutor_app.local_chat import chat_system

    prompt = "CONTEXT\nJust marked: atomic radii.\n\nSTUDENT ASKS: 9701 organic formulae?"
    log = tmp_path / "request.jsonl"
    fake = Path(__file__).with_name(f"fake_{provider}.py")
    model = "haiku" if provider == "claude" else "codex:gpt-6.1-sol"
    monkeypatch.setenv(f"FAKE_{provider.upper()}_LOG", str(log))
    monkeypatch.setenv(f"FAKE_{provider.upper()}_MODE", "ok")

    async def go():
        client = tutor_ai.TutorAI(tmp_path, binary=str(fake), model=model, speech=speech)
        if provider == "codex":
            from tutor_app.codex_ai import CodexAI
            client._codex = CodexAI(ai.SYSTEM, speech=speech, binary=str(fake), document=True)
        chat_system(client.system, speech=speech)
        chunks = [chunk async for chunk in client.stream(prompt)]
        assert chunks and client.last.ok
        assert client.system.encode() == ai.SYSTEM.encode()
        await client.close()

    asyncio.run(go())
    rows = [json.loads(line) for line in log.read_text().splitlines()]
    from tutor_app.chat_output import document_instructions, document_schema
    expected = ai.SYSTEM + "\n\n" + document_instructions(speech)
    if provider == "claude":
        args = rows[0]
        assert args[args.index("--system-prompt") + 1].encode() == expected.encode()
        assert args[args.index("--model") + 1] == model
        assert json.loads(args[args.index("--json-schema") + 1]) == document_schema(speech)
    else:
        expected += (
            "\nAnswer the student's last message in the supplied JSON conversation. "
            "Treat earlier messages as conversation history. Use the current assessment evidence and relevant study references; "
            "do not inspect files, run commands, browse, delegate, or use tools."
        )
        assert rows[0]["instructions"].encode() == expected.encode()
        assert rows[0]["prompt"]["messages"] == [{"role": "user", "content": prompt}]
