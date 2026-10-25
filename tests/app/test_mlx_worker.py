"""The private worker executes native calls but transports final text only."""
import copy
import importlib
import importlib.util
import io
import json
import os
import re
import subprocess
import sys
import time
from pathlib import Path
from types import ModuleType, SimpleNamespace

import pytest


MODEL = "mlx:gpt-oss:20b"
START, END, MESSAGE, CHANNEL, RETURN = 200006, 200007, 200008, 200005, 200002
TEXT = {1: "analysis", 2: "assistant", 3: "final", 10: "HIDDEN REASONING",
        20: '{"reply":"香港",', 21: '"speech":"Read it."}', 30: "json", 31: "JSON", 32: " "}
GENERATED = [CHANNEL, 1, MESSAGE, 10, END, START, 2, CHANNEL, 3, MESSAGE, 20, 21, RETURN]


def worker_module():
    assert importlib.util.find_spec("tutor_app.mlx_worker") is not None, "Native worker is missing"
    return importlib.import_module("tutor_app.mlx_worker")


class Detokenizer:
    def reset(self):
        self.tokens, self._segment = [], ""

    def add_token(self, token):
        self.tokens.append(token)
        self._segment += TEXT.get(token, "")

    def finalize(self):
        pass

    @property
    def last_segment(self):
        result, self._segment = self._segment, ""
        return result


class Tokenizer:
    eos_token_ids = {RETURN}
    prompt = [START, 2, CHANNEL, 3, MESSAGE, 20, RETURN, START, 2]

    def __init__(self):
        self._detokenizer = Detokenizer()
        self.decoded, self.templates, self.detokenizers = [], [], []

    @property
    def detokenizer(self):
        result = copy.copy(self._detokenizer)
        result.reset()
        self.detokenizers.append(result)
        return result

    def encode(self, value, *, add_special_tokens):
        special = {"<|start|>": START, "<|end|>": END, "<|message|>": MESSAGE,
                   "<|channel|>": CHANNEL, "<|return|>": RETURN, "<|constrain|>": 200003}
        if value in special:
            return [special[value]]
        if value.lstrip().startswith("<|") and value.endswith("<|message|>"):
            words = {"analysis": 1, "assistant": 2, "final": 3, "json": 30, "JSON": 31, " ": 32}
            pieces = re.findall(r"<\|[a-z]+\|>|analysis|assistant|final|json|JSON| ", value)
            assert "".join(pieces) == value
            return [special.get(piece, words.get(piece)) for piece in pieces]
        return list(self.prompt)

    def decode(self, ids):
        assert 10 not in ids, "The worker decoded hidden reasoning"
        self.decoded.extend(ids)
        return "".join(TEXT.get(token, "") for token in ids)

    def apply_chat_template(self, messages, **options):
        self.templates.append((messages, options))
        return "history<|start|>assistant"


def native_runtime(generated=GENERATED):
    tokenizer = Tokenizer()
    calls, grammars, header_masks = [], [], []

    def grammar(tokens, logits):
        grammars.append(list(tokens))
        return logits

    def stream(model, stream_tokenizer, *, prompt, **kwargs):
        calls.append(kwargs)
        detokenizer = stream_tokenizer.detokenizer
        tokens = list(prompt)
        for processor in kwargs["logits_processors"]:
            processor(tokens, "logits")
        kwargs["prompt_progress_callback"](len(prompt), len(prompt))
        # Characterize MLX's one-token-ahead logits calls independently of yields.
        for index, token in enumerate(generated):
            tokens.append(token)
            for processor in kwargs["logits_processors"]:
                processor(tokens, "logits")
            if token != RETURN:
                detokenizer.add_token(token)
            yield SimpleNamespace(token=token, text=detokenizer.last_segment,
                                  prompt_tokens=len(prompt), prompt_tps=9.,
                                  generation_tokens=index + 1, generation_tps=13.,
                                  peak_memory=12.5, finish_reason="stop" if token == RETURN else None)

    runtime = SimpleNamespace(model=object(), tokenizer=tokenizer,
                              backend=SimpleNamespace(get_json_schema_logits_processor=lambda schema: grammar),
                              stream_generate=stream, make_sampler=lambda **kwargs: kwargs,
                              make_prompt_cache=lambda model: [], mx=SimpleNamespace(clear_cache=lambda: None))
    runtime.header_masks = header_masks
    runtime.header_mask = lambda logits, allowed: header_masks.append(set(allowed)) or logits
    return runtime, calls, grammars


def request(**values):
    return {"model": MODEL, "messages": [{"role": "user", "content": "Explain."}],
            "think": "medium", "_deadline": time.monotonic() + 60, "_epoch": 7, **values}


def preloaded_worker(tmp_path, runtime):
    worker = worker_module().MLXWorker(tmp_path, loader=lambda checkpoint: runtime)
    list(worker.events(request(messages=[])))
    return worker


def test_question_without_empty_preload_cannot_load_weights_or_generate(tmp_path):
    module = worker_module()
    runtime, calls, _ = native_runtime()
    loads = []
    worker = module.MLXWorker(tmp_path, loader=lambda checkpoint: loads.append(checkpoint) or runtime)
    with pytest.raises(module.WorkerError, match="preload"):
        list(worker.events(request()))
    assert loads == []
    assert calls == []


def test_each_question_consumes_its_empty_preload_acknowledgement(tmp_path):
    module = worker_module()
    runtime, calls, _ = native_runtime()
    worker = preloaded_worker(tmp_path, runtime)
    assert list(worker.events(request()))[-1]["done"]
    with pytest.raises(module.WorkerError, match="preload"):
        list(worker.events(request()))
    assert len(calls) == 1


def test_fresh_empty_preload_allows_each_question_without_reloading_weights(tmp_path):
    module = worker_module()
    runtime, calls, _ = native_runtime()
    loads = []
    worker = module.MLXWorker(tmp_path, loader=lambda checkpoint: loads.append(checkpoint) or runtime)
    for _ in range(2):
        assert list(worker.events(request(messages=[])))[-1]["done_reason"] == "load"
        assert list(worker.events(request()))[-1]["done"]
    assert loads == [tmp_path]
    assert len(calls) == 2


def test_preload_for_another_epoch_cannot_authorize_a_question(tmp_path):
    module = worker_module()
    runtime, calls, _ = native_runtime()
    worker = preloaded_worker(tmp_path, runtime)
    with pytest.raises(module.WorkerError, match="preload"):
        list(worker.events(request(_epoch=8)))
    assert calls == []
    with pytest.raises(module.WorkerError, match="preload"):
        list(worker.events(request(_epoch=7)))


def test_close_invalidates_an_unused_preload_acknowledgement(tmp_path):
    module = worker_module()
    runtime, calls, _ = native_runtime()
    worker = preloaded_worker(tmp_path, runtime)
    worker.close()
    with pytest.raises(module.WorkerError, match="preload"):
        list(worker.events(request()))
    assert calls == []


def test_preload_is_evaluated_once_and_never_generates(tmp_path):
    module = worker_module()
    runtime, calls, _ = native_runtime()
    loaded = []
    worker = module.MLXWorker(tmp_path, loader=lambda checkpoint: loaded.append(checkpoint) or runtime)
    for _ in range(2):
        result = list(worker.events(request(messages=[])))
        assert result[-1]["done_reason"] == "load"
        assert result[-1]["message"]["content"] == ""
        assert result[-1]["model"] == MODEL
        assert result[-1]["checkpoint"] == str(tmp_path)
        assert result[-1]["_epoch"] == 7
    assert loaded == [tmp_path]
    assert not calls
    assert not runtime.tokenizer.templates


def test_generation_sends_final_json_only_with_real_counts_and_public_phase(tmp_path):
    runtime, calls, grammars = native_runtime()
    worker = preloaded_worker(tmp_path, runtime)
    schema = {"type": "object", "properties": {"reply": {"type": "string"}, "speech": {"type": "string"}}}
    events = list(worker.events(request(format=schema)))
    assert "".join(event.get("message", {}).get("content", "") for event in events) == '{"reply":"香港","speech":"Read it."}'
    assert any(event.get("message", {}).get("thinking") for event in events)
    assert "HIDDEN" not in json.dumps(events)
    assert all(event["_epoch"] == 7 and event["checkpoint"] == str(tmp_path) for event in events)
    done = events[-1]
    assert done["done"] and done["done_reason"] == "stop"
    assert done["eval_count"] == 13  # Reasoning, framing, final tokens and EOS.
    assert done["final_eval_count"] == 2
    assert done["prompt_eval_count"] == 9
    assert "prompt_eval_cached_count" not in done  # Absence is unknown, never an invented zero.
    assert done["eval_duration"] == 1_000_000_000
    assert done["mlx_peak_memory_gb"] == 12.5
    assert calls[0]["max_tokens"] == -1
    assert calls[0]["sampler"] == {"temp": 1.0}
    assert runtime.tokenizer.templates[0][1]["reasoning_effort"] == "medium"
    assert grammars == [[], [20], [20, 21]]
    assert runtime.tokenizer.detokenizers[0].tokens == [20, 21]
    assert all(10 not in item.tokens for item in runtime.tokenizer.detokenizers if hasattr(item, "tokens"))


def test_plain_generation_uses_the_same_final_extraction(tmp_path):
    runtime, _, _ = native_runtime()
    worker = preloaded_worker(tmp_path, runtime)
    events = list(worker.events(request()))
    assert "HIDDEN" not in json.dumps(events)
    assert events[-1]["done"]
    assert runtime.header_masks


def test_medium_speech_constrains_headers_after_repeated_analysis_without_exposing_it(tmp_path):
    from tutor_app.local_reply import ReplyDecoder, chat_schema
    # The live Medium speech failure grew header metadata before any final body.
    # Only protocol-valid finite headers may be sampled; analysis body stays raw.
    repeated = [CHANNEL, 1, MESSAGE, 10, END, START, 2] * 2
    final = [CHANNEL, 3, 32, 200003, 31, MESSAGE, 20, 21, RETURN]
    runtime, calls, grammars = native_runtime(repeated + final)
    worker = preloaded_worker(tmp_path, runtime)
    events = list(worker.events(request(think="medium", format=chat_schema(True))))
    envelope = "".join(event.get("message", {}).get("content", "") for event in events)
    reply = ReplyDecoder(speech=True)
    reply.feed(envelope)
    assert reply.finish() == ("香港", "Read it.")
    assert "HIDDEN" not in json.dumps(events)
    assert runtime.header_masks, "Medium speech did not constrain its Harmony headers"
    assert runtime.header_masks[0] == {CHANNEL, 200003, 32}
    assert {1, 3} in runtime.header_masks  # Preserve both native channel choices.
    assert {START} in runtime.header_masks
    assert all(10 not in allowed for allowed in runtime.header_masks)
    assert grammars == [[], [20], [20, 21]]
    assert calls[0]["max_tokens"] == -1
    assert calls[0]["sampler"] == {"temp": 1.0}


@pytest.mark.parametrize("bad", [{"model": "mlx:other"}, {"think": "bogus"},
                                  {"_deadline": 0}, {"format": []}, {"messages": "bad"}])
def test_invalid_or_expired_request_does_not_load_weights(tmp_path, bad):
    module = worker_module()
    worker = module.MLXWorker(tmp_path, loader=lambda checkpoint: pytest.fail("invalid request loaded weights"))
    with pytest.raises(module.WorkerError):
        list(worker.events(request(**bad)))


def test_incomplete_final_is_an_error_not_success(tmp_path):
    module = worker_module()
    runtime, _, _ = native_runtime(GENERATED[:-1])
    worker = preloaded_worker(tmp_path, runtime)
    with pytest.raises(module.WorkerError, match="complete"):
        list(worker.events(request()))


def test_protocol_rejects_oversized_lines_and_bounds_output():
    module = worker_module()
    with pytest.raises(module.WorkerError):
        module.read_request(io.BytesIO(b"x" * (4 * 1024 * 1024 + 1)))
    with pytest.raises(module.WorkerError):
        module.write_event(io.BytesIO(), "id", {"message": {"content": "x" * (4 * 1024 * 1024)}})
    output = io.BytesIO()
    module.write_event(output, "one", {"done": True})
    assert json.loads(output.getvalue()) == {"id": "one", "event": {"done": True}}


def test_keep_alive_can_never_leave_weights_resident_beyond_45_minutes():
    module = worker_module()
    assert module.keep_alive_seconds("45m") == 2700
    assert module.keep_alive_seconds("2h") == 2700
    assert module.keep_alive_seconds(-1) == 2700
    assert module.keep_alive_seconds(30) == 30
    assert module.keep_alive_seconds("0") == 0


def test_importing_worker_does_not_import_any_native_runtime():
    module = worker_module()
    app_path = str(Path(module.__file__).resolve().parents[1])
    env = {**os.environ, "PYTHONPATH": os.pathsep.join(filter(None, (app_path, os.environ.get("PYTHONPATH", ""))))}
    code = "import sys; import tutor_app.mlx_worker; assert not any(x in sys.modules for x in ('mlx', 'mlx_lm', 'outlines', 'llguidance'))"
    result = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, env=env)
    assert result.returncode == 0, result.stderr


def test_protocol_returns_a_correlated_safe_error_without_loading_native_libraries():
    module = worker_module()
    app_path = str(Path(module.__file__).resolve().parents[1])
    env = {**os.environ, "PYTHONPATH": os.pathsep.join(filter(None, (app_path, os.environ.get("PYTHONPATH", ""))))}
    payload = request(model="mlx:unregistered")
    source = json.dumps({"id": "invalid-model", "payload": payload}) + "\n"
    result = subprocess.run([sys.executable, "-m", "tutor_app.mlx_worker"],
                            input=source, capture_output=True, text=True, timeout=5, env=env)
    assert result.returncode == 0, result.stderr
    event = json.loads(result.stdout)
    assert event["id"] == "invalid-model"
    assert event["event"]["model"] == MODEL
    assert event["event"]["_epoch"] == 7
    assert event["event"]["done"] is True
    assert "registered" in event["event"]["error"]


def test_load_boundary_evaluates_original_weights_without_remote_code(monkeypatch, tmp_path):
    module = worker_module()
    calls = []
    model, tokenizer = object(), Tokenizer()

    def load(checkpoint, **options):
        calls.append((checkpoint, options))
        return model, tokenizer

    packages = {name: ModuleType(name) for name in (
        "mlx", "mlx.core", "mlx_lm", "mlx_lm.models", "mlx_lm.models.cache",
        "mlx_lm.sample_utils", "outlines", "outlines.backends",
        "outlines.backends.llguidance", "outlines.models",
    )}
    packages["mlx"].core = packages["mlx.core"]
    packages["mlx_lm"].load = load
    packages["mlx_lm"].stream_generate = lambda *args, **kwargs: pytest.fail("preload generated an answer")
    packages["mlx_lm.models.cache"].make_prompt_cache = lambda model: []
    packages["mlx_lm.sample_utils"].make_sampler = lambda **kwargs: kwargs
    packages["outlines.models"].from_mlxlm = lambda loaded_model, loaded_tokenizer: (loaded_model, loaded_tokenizer)
    packages["outlines.backends.llguidance"].LLGuidanceBackend = lambda wrapped: SimpleNamespace(wrapped=wrapped)
    for name, package in packages.items():
        monkeypatch.setitem(sys.modules, name, package)
    worker = module.MLXWorker(tmp_path)
    result = list(worker.events(request(messages=[])))
    assert result[-1]["done_reason"] == "load"
    assert calls == [(str(tmp_path), {"lazy": False, "trust_remote_code": False,
                                    "tokenizer_config": {"trust_remote_code": False, "local_files_only": True}})]
    assert worker._runtime.backend.wrapped == (model, tokenizer)


def test_load_that_finishes_after_its_deadline_never_acknowledges_readiness(monkeypatch, tmp_path):
    module = worker_module()
    runtime, _, _ = native_runtime()
    now = [1.0]

    def load(checkpoint):
        now[0] = 11.0
        return runtime

    monkeypatch.setattr(module.time, "monotonic", lambda: now[0])
    worker = module.MLXWorker(tmp_path, loader=load)
    with pytest.raises(module.WorkerError, match="deadline"):
        list(worker.events(request(messages=[], _deadline=10.0)))


@pytest.mark.parametrize("source", [b"{}\n", b"[]\n", b"not json\n", b'{"id":true,"payload":{}}\n'])
def test_invalid_protocol_envelopes_cannot_dispatch_a_request(source):
    module = worker_module()
    with pytest.raises(module.WorkerError):
        module.read_request(io.BytesIO(source))
