"""Human-facing JSON prose shares display formatting without rewriting grading data."""
import asyncio
from copy import deepcopy

import pytest

from tutor_app import ai, local_models, prompts, tutor_ai
from tutor_app.local_vision import EXTRACTION_SCHEMA
from tutorlib import challenge_gen


RAW = r"Use \(x^2\)."
CANONICAL = "Use $x^2$."
LOCAL = "ollama:qwen3.5:9b"


def normalise(data, schema):
    from tutor_app.output_fields import normalise_fields

    return normalise_fields(data, schema)


@pytest.mark.parametrize("model", ["haiku", "codex:gpt-6.1-sol", LOCAL])
def test_successful_provider_prose_is_canonical_without_changing_machine_data(tmp_path, monkeypatch, model):
    """Missing any successful route's normalisation leaves its feedback in legacy delimiters."""
    monkeypatch.setattr(local_models, "available_models", lambda: (LOCAL,))
    source = {"points": [{"point": RAW, "met": False, "why": RAW}], "feedback": RAW, "speech": RAW}
    original = deepcopy(source)
    result = ai.Result(text="provider JSON", speech=RAW, usage={"output_tokens": 7})

    async def go():
        client = tutor_ai.TutorAI(tmp_path, binary="/missing/claude", speech=True)
        seen = []

        async def answer(prompt, **kwargs):
            seen.append(kwargs)
            return source, result

        if model == "haiku":
            async def claude_answer(self, prompt, **kwargs):
                return await answer(prompt, **kwargs)
            monkeypatch.setattr(ai.Claude, "one_shot", claude_answer)
        elif model.startswith("codex:"):
            monkeypatch.setattr(client.codex, "one_shot", answer)
        else:
            monkeypatch.setattr(client.local, "one_shot", answer)
        data, returned = await client.one_shot("Mark", schema=prompts.JUDGE, model=model, speech=True, think=True)
        assert data["feedback"] == CANONICAL
        assert data["points"] == [{"point": RAW, "met": False, "why": CANONICAL}]
        assert data["speech"] == RAW and source == original
        assert returned is result and returned.text == "provider JSON" and returned.speech == RAW
        assert returned.usage == {"output_tokens": 7}
        assert seen[0]["model"] == model and seen[0]["speech"] and seen[0]["think"]
        await client.close()

    asyncio.run(go())


@pytest.mark.parametrize("schema,source,expected", [
    (prompts.JUDGE, {"feedback": RAW, "points": [{"point": RAW, "met": True, "why": RAW}]},
     {"feedback": CANONICAL, "points": [{"point": RAW, "met": True, "why": CANONICAL}]}),
    (prompts.local_judge_schema([RAW]), {"feedback": RAW, "points": [{"point": RAW, "met": True, "why": RAW}]},
     {"feedback": CANONICAL, "points": [{"point": RAW, "met": True, "why": CANONICAL}]}),
    (prompts.REMARK, {"correct": False, "why": RAW}, {"correct": False, "why": CANONICAL}),
    (prompts.CARD, {field: RAW for field in ("motivate", "establish", "connect", "note", "self_explain")},
     {field: CANONICAL for field in ("motivate", "establish", "connect", "note", "self_explain")}),
    (prompts.PROFILE, {"summary": RAW}, {"summary": CANONICAL}),
    (challenge_gen.GENERATE_SCHEMA,
     {"stem": RAW, "solution": RAW, "working": RAW, "correct": RAW, "wrong": [{"text": RAW, "mistake": RAW}],
      "value": 1.25, "unit": RAW, "sf": 3, "exact": True, "expr": RAW, "concepts": [RAW], "options": {"A": RAW}},
     {"stem": CANONICAL, "solution": CANONICAL, "working": RAW, "correct": RAW,
      "wrong": [{"text": RAW, "mistake": CANONICAL}], "value": 1.25, "unit": RAW, "sf": 3, "exact": True,
      "expr": RAW, "concepts": [RAW], "options": {"A": RAW}}),
    (challenge_gen.GENERATE_MCQ_SCHEMA,
     {"stem": RAW, "solution": RAW, "correct": RAW, "wrong": [{"text": RAW, "mistake": RAW}], "concepts": [RAW]},
     {"stem": CANONICAL, "solution": CANONICAL, "correct": RAW,
      "wrong": [{"text": RAW, "mistake": CANONICAL}], "concepts": [RAW]}),
    (challenge_gen.AUDIT_SCHEMA,
     {"working": RAW, "solution_correct": True, "concepts": [{"idea": RAW, "kc": RAW}],
      "out_of_scope": [RAW], "rated_level": 8, "problems": [RAW]},
     {"working": RAW, "solution_correct": True, "concepts": [{"idea": CANONICAL, "kc": RAW}],
      "out_of_scope": [RAW], "rated_level": 8, "problems": [RAW]}),
])
def test_only_audited_fields_are_normalised_and_input_is_not_mutated(schema, source, expected):
    before, schema_before = deepcopy(source), deepcopy(schema)
    source["speech"] = RAW
    before["speech"] = RAW
    expected = {**expected, "speech": RAW}
    assert normalise(source, schema) == expected
    assert source == before and schema == schema_before


@pytest.mark.parametrize("schema", [None, {}, EXTRACTION_SCHEMA, challenge_gen.SOLVE_SCHEMA,
    {"type": "object", "properties": {"why": {"type": "string"}}, "required": ["why"]},
    {"type": "object", "properties": {"summary": {"type": "number"}}, "required": ["summary"]},
    {"type": "object", "properties": {"stem": {"type": "string"}, "solution": {"type": "string"}},
     "required": ["stem", "solution"]},
])
def test_unknown_solver_and_vision_schemas_do_not_rewrite_matching_field_names(schema):
    data = {"feedback": RAW, "why": RAW, "summary": RAW, "stem": RAW, "solution": RAW,
            "answer": RAW, "working": RAW, "transcription": RAW}
    before = deepcopy(data)
    assert normalise(data, schema) is data
    assert data == before


def test_normalisation_copies_only_changed_branches_and_ignores_invalid_prose_values():
    stable = {"point": RAW, "met": True, "why": 3}
    changed = {"point": RAW, "met": False, "why": RAW}
    data = {"feedback": None, "points": [stable, changed, "unexpected"], "machine": {"answer": RAW}}
    result = normalise(data, prompts.JUDGE)
    assert result is not data and result["points"] is not data["points"]
    assert result["points"][0] is stable and result["points"][1] is not changed
    assert result["points"][1]["why"] == CANONICAL and changed["why"] == RAW
    assert result["points"][2] == "unexpected" and result["feedback"] is None
    assert result["machine"] is data["machine"]
    assert normalise(None, prompts.JUDGE) is None


def test_speech_extension_is_recognised_without_modifying_speech():
    schema = deepcopy(prompts.REMARK)
    schema["properties"]["speech"] = {"type": "string"}
    schema["required"].append("speech")
    data = {"correct": True, "why": RAW, "speech": RAW}
    assert normalise(data, schema) == {"correct": True, "why": CANONICAL, "speech": RAW}


def test_literal_code_urls_and_currency_are_kept_in_visual_prose():
    literal = r"`\(x^2\)` and [source](https://example.com/x_1). Costs $5 and $10; 25%."
    assert normalise({"summary": literal}, prompts.PROFILE)["summary"] == literal


def test_local_cached_prose_is_normalised_on_each_read_without_rewriting_cache(tmp_path, monkeypatch):
    monkeypatch.setattr(local_models, "available_models", lambda: (LOCAL,))

    async def go():
        client = tutor_ai.TutorAI(tmp_path, binary="/missing/claude", model=LOCAL)
        calls = []

        async def answer(prompt, **kwargs):
            calls.append(prompt)
            return {"summary": RAW}, ai.Result(text="original JSON", performance={"model": LOCAL})

        monkeypatch.setattr(client.local, "one_shot", answer)
        first, _ = await client.one_shot("Profile", schema=prompts.PROFILE)
        second, result = await client.one_shot("Profile", schema=prompts.PROFILE)
        assert first == second == {"summary": CANONICAL} and len(calls) == 1
        assert result.performance["cached_reply"]
        assert next(iter(client._replies._entries.values()))[1] == {"summary": RAW}
        await client.close()

    asyncio.run(go())


@pytest.mark.parametrize("model", ["haiku", "codex:gpt-6.1-sol", LOCAL])
def test_failed_results_keep_data_and_status_untouched(tmp_path, monkeypatch, model):
    monkeypatch.setattr(local_models, "available_models", lambda: (LOCAL,))

    async def go():
        client = tutor_ai.TutorAI(tmp_path, binary="/missing/claude")
        source = {"summary": RAW}
        failure = ai.Result(ok=False, status="limit", message="Wait", usage={"output_tokens": 2})

        async def answer(prompt, **kwargs):
            return source, failure

        if model == "haiku":
            async def claude_answer(self, prompt, **kwargs):
                return await answer(prompt, **kwargs)
            monkeypatch.setattr(ai.Claude, "one_shot", claude_answer)
        elif model.startswith("codex:"):
            monkeypatch.setattr(client.codex, "one_shot", answer)
        else:
            monkeypatch.setattr(client.local, "one_shot", answer)
        data, result = await client.one_shot("Profile", schema=prompts.PROFILE, model=model)
        assert data is source and result is failure
        assert data["summary"] == RAW and result.status == "limit" and result.message == "Wait"
        await client.close()

    asyncio.run(go())


@pytest.mark.parametrize("model", ["haiku", "codex:gpt-6.1-sol", LOCAL])
def test_explicit_visual_system_receives_shared_brief_without_changing_request_options(tmp_path, monkeypatch, model):
    monkeypatch.setattr(local_models, "available_models", lambda: (LOCAL,))

    async def go():
        client = tutor_ai.TutorAI(tmp_path, binary="/missing/claude")
        assert client.local.system == client.codex.system == client.system
        requests = []

        async def answer(prompt, **kwargs):
            requests.append((prompt, kwargs))
            return {"stem": "A question", "solution": "A method", "concepts": []}, ai.Result()

        if model == "haiku":
            async def claude_answer(self, prompt, **kwargs):
                return await answer(prompt, **kwargs)
            monkeypatch.setattr(ai.Claude, "one_shot", claude_answer)
        elif model.startswith("codex:"):
            monkeypatch.setattr(client.codex, "one_shot", answer)
        else:
            monkeypatch.setattr(client.local, "one_shot", answer)
        await client.one_shot("Generate", schema=challenge_gen.GENERATE_SCHEMA, model=model,
                              system=challenge_gen.GEN_SYSTEM, think=True, timeout=15)
        prompt, options = requests[0]
        assert prompt == "Generate" and options["model"] == model and options["think"] is True
        assert options["system"].startswith(challenge_gen.GEN_SYSTEM + "\n\n")
        assert options["system"].endswith(ai.VISUAL_BRIEF)
        await client.close()

    asyncio.run(go())


def test_solver_override_is_not_given_visual_prose_instructions(tmp_path, monkeypatch):
    async def go():
        client = tutor_ai.TutorAI(tmp_path, binary="/missing/claude")

        async def answer(self, prompt, **kwargs):
            assert kwargs["system"] == challenge_gen.GEN_SYSTEM
            return {"working": RAW, "answer": RAW}, ai.Result()

        monkeypatch.setattr(ai.Claude, "one_shot", answer)
        data, _ = await client.one_shot("Solve", schema=challenge_gen.SOLVE_SCHEMA, system=challenge_gen.GEN_SYSTEM)
        assert data == {"working": RAW, "answer": RAW}
        await client.close()

    asyncio.run(go())
