"""Local preparation hides independent work without changing answer or cloud controls."""
import asyncio
import time

import pytest

from tutor_app import local_models
from tutor_app.ai import Result
from tutor_app.local_ai import LocalAI
from tutor_app.local_ocr import NativeOCR
from tutor_app.tutor_ai import TutorAI


MODEL = "ollama:phi4-mini:3.8b"
HELPER = "ollama:qwen3.5:2b"


@pytest.fixture(autouse=True)
def installed_models(monkeypatch):
    monkeypatch.setattr(local_models, "available_models", lambda: (MODEL, HELPER))


@pytest.mark.parametrize("foreground", [False, True])
def test_native_ocr_and_model_load_overlap_and_preserve_request(tmp_path, monkeypatch, foreground):
    async def go():
        image = tmp_path / "question.png"
        image.write_bytes(b"exact question pixels")
        client = TutorAI(tmp_path, model=MODEL, binary="/missing/claude")
        loading, reading, release = asyncio.Event(), asyncio.Event(), asyncio.Event()
        payloads = []

        async def events(self, payload, timeout, path="/api/chat"):
            payloads.append(payload)
            if not payload["messages"]:
                loading.set()
                await release.wait()
                yield {"done": True, "done_reason": "load"}
            else:
                yield {"message": {"content": '{"score":1}'}, "done": True}

        async def describe(self, pixels, prompt, **kwargs):
            assert pixels == b"exact question pixels"
            reading.set()
            await release.wait()
            return {"transcription": "Force = 6 N", "diagram": "", "uncertainties": []}, Result()

        monkeypatch.setattr(LocalAI, "_events", events)
        monkeypatch.setattr(NativeOCR, "describe_image", describe)
        call = (client.one_shot("Mark this answer", model=MODEL, image=image, think=False)
                if foreground else client.prepare_local(MODEL, image=image))
        task = asyncio.create_task(call)
        try:
            await asyncio.wait_for(asyncio.gather(loading.wait(), reading.wait()), .5)
        finally:
            release.set()
            value = await task
            await client.close()
        assert len([p for p in payloads if not p["messages"]]) == (2 if foreground else 1)
        if foreground:
            data, result = value
            assert data == {"score": 1} and result.ok
            request = payloads[-1]
            assert "Mark this answer" in request["messages"][-1]["content"]
            assert "Force = 6 N" in request["messages"][-1]["content"]
            assert "images" not in request["messages"][-1]
            assert "think" not in request  # this text model does not support thinking
            assert request["options"] == {"num_ctx": 8192}
        assert client._codex is None
    asyncio.run(go())


def test_native_preparation_cancellation_joins_model_load_and_does_not_generate(tmp_path, monkeypatch):
    async def go():
        client = TutorAI(tmp_path, model=MODEL, binary="/missing/claude")
        image = tmp_path / "question.png"
        image.write_bytes(b"pixels")
        started, stopped = asyncio.Event(), asyncio.Event()

        async def events(self, payload, timeout, path="/api/chat"):
            assert payload["messages"] == []
            started.set()
            try:
                await asyncio.Event().wait()
                yield
            finally:
                stopped.set()

        async def describe(self, *args, **kwargs):
            await asyncio.Event().wait()

        monkeypatch.setattr(LocalAI, "_events", events)
        monkeypatch.setattr(NativeOCR, "describe_image", describe)
        task = asyncio.create_task(client.prepare_local(MODEL, image=image))
        try:
            await asyncio.wait_for(started.wait(), .5)
        finally:
            task.cancel()
            await asyncio.gather(task, return_exceptions=True)
            await client.close()
        assert stopped.is_set() and not client._observing
    asyncio.run(go())


def test_generative_image_helper_finishes_before_tutor_model_load(tmp_path, monkeypatch):
    async def go():
        client = TutorAI(tmp_path, model=MODEL, binary="/missing/claude")
        client.local_vision_model = HELPER
        image = tmp_path / "question.png"
        image.write_bytes(b"pixels")
        calls = []

        async def events(self, payload, timeout, path="/api/chat"):
            calls.append((payload["model"], bool(payload["messages"])))
            if payload["messages"]:
                yield {"message": {"content": '{"transcription":"6 N","diagram":"","uncertainties":[]}'}, "done": True}
            else:
                yield {"done": True, "done_reason": "load"}

        monkeypatch.setattr(LocalAI, "_events", events)
        await client.prepare_local(MODEL, image=image)
        assert calls == [("qwen3.5:2b", False), ("qwen3.5:2b", True), ("phi4-mini:3.8b", False)]
        await client.close()
    asyncio.run(go())


def test_web_retrieval_and_model_load_overlap_without_sending_private_context(tmp_path, monkeypatch):
    async def go():
        client = TutorAI(tmp_path, model=MODEL, binary="/missing/claude")
        loading, searching, release = asyncio.Event(), asyncio.Event(), asyncio.Event()
        calls = []

        async def events(self, payload, timeout, path="/api/chat"):
            calls.append((path, payload))
            if path == "/api/experimental/web_search":
                assert payload == {"query": "Look up the latest syllabus", "max_results": 3}
                searching.set()
                await release.wait()
                yield {"results": [{"title": "Syllabus", "url": "https://example.org/syllabus", "content": "Current scope"}]}
            elif not payload["messages"]:
                loading.set()
                await release.wait()
                yield {"done": True, "done_reason": "load"}
            else:
                yield {"message": {"content": '{"reply":"Here is the scope."}'}, "done": True}

        monkeypatch.setattr(LocalAI, "_events", events)
        async def answer():
            return "".join([part async for part in client.stream("Private lesson packet", model=MODEL,
                                      web_query="Look up the latest syllabus", think=False)])
        task = asyncio.create_task(answer())
        try:
            await asyncio.wait_for(asyncio.gather(loading.wait(), searching.wait()), .5)
        finally:
            release.set()
            text = await task
            await client.close()
        assert "Here is the scope." in text and "https://example.org/syllabus" in text
        assert len(calls) == 4
        request = calls[-1][1]
        assert "Private lesson packet" in request["messages"][-1]["content"]
        assert "Current scope" in request["messages"][-1]["content"]
    asyncio.run(go())


def test_plain_text_request_requires_preload_without_prior_preparation(tmp_path, monkeypatch):
    async def go():
        client = TutorAI(tmp_path, model=MODEL, binary="/missing/claude")
        calls = []
        async def events(self, payload, timeout, path="/api/chat"):
            calls.append(payload)
            yield ({"message": {"content": '{"reply":"Use F = ma."}'}, "done": True}
                   if payload["messages"] else {"done": True, "done_reason": "load"})
        monkeypatch.setattr(LocalAI, "_events", events)
        assert "".join([p async for p in client.stream("Explain force", think=False)]) == "Use F = ma."
        assert len(calls) == 2 and calls[0]["messages"] == []
        assert calls[1]["messages"][-1]["content"] == "Explain force"
        await client.close()
    asyncio.run(go())


def test_queued_cached_response_reports_actual_wait(tmp_path, monkeypatch):
    async def go():
        client = TutorAI(tmp_path, model=MODEL, binary="/missing/claude")
        started, finish = asyncio.Event(), asyncio.Event()
        calls = []
        async def events(self, payload, timeout, path="/api/chat"):
            if not payload["messages"]:
                yield {"done": True, "done_reason": "load"}
                return
            calls.append(payload)
            started.set()
            await finish.wait()
            yield {"message": {"content": '{"score":1}'}, "done": True}
        monkeypatch.setattr(LocalAI, "_events", events)
        one = asyncio.create_task(client.one_shot("Mark", model=MODEL))
        await started.wait()
        two = asyncio.create_task(client.one_shot("Mark", model=MODEL))
        await asyncio.sleep(.03)
        finish.set()
        first, second = await asyncio.gather(one, two)
        assert first[0] == second[0] == {"score": 1} and len(calls) == 1
        assert second[1].performance["cached_reply"]
        assert second[1].performance["total_seconds"] >= .02
        assert second[1].performance["first_token_seconds"] >= .02
        await client.close()
    asyncio.run(go())


def test_failed_ocr_cancels_loading_before_returning_visible_error(tmp_path, monkeypatch):
    async def go():
        client = TutorAI(tmp_path, model=MODEL, binary="/missing/claude")
        image = tmp_path / "unreadable.png"
        image.write_bytes(b"pixels")
        loading, stopped = asyncio.Event(), asyncio.Event()
        async def events(self, payload, timeout, path="/api/chat"):
            assert not payload["messages"]
            loading.set()
            try:
                await asyncio.Event().wait()
                yield
            finally:
                stopped.set()
        async def describe(self, *args, **kwargs):
            await loading.wait()
            return None, Result(ok=False, message="OCR unavailable")
        monkeypatch.setattr(LocalAI, "_events", events)
        monkeypatch.setattr(NativeOCR, "describe_image", describe)
        data, result = await client.one_shot("Mark", model=MODEL, image=image)
        assert data is None and not result.ok and "OCR unavailable" in result.message
        assert stopped.is_set() and not client._observing
        await client.close()
    asyncio.run(go())


def test_reset_during_overlapped_preparation_never_starts_generation(tmp_path, monkeypatch):
    async def go():
        client = TutorAI(tmp_path, model=MODEL, binary="/missing/claude")
        image = tmp_path / "question.png"
        image.write_bytes(b"pixels")
        loading, release = asyncio.Event(), asyncio.Event()
        calls = []
        async def events(self, payload, timeout, path="/api/chat"):
            calls.append(payload)
            assert not payload["messages"]
            loading.set()
            await release.wait()
            yield {"done": True, "done_reason": "load"}
        async def describe(self, *args, **kwargs):
            await release.wait()
            return {"transcription": "6 N", "diagram": "", "uncertainties": []}, Result()
        monkeypatch.setattr(LocalAI, "_events", events)
        monkeypatch.setattr(NativeOCR, "describe_image", describe)
        task = asyncio.create_task(client.one_shot("Mark", model=MODEL, image=image))
        await loading.wait()
        await client.reset(warm=False)
        release.set()
        with pytest.raises(asyncio.CancelledError):
            await task
        assert len(calls) == 1 and not client._observing
        await client.close()
    asyncio.run(go())


def test_web_timing_excludes_load_wait_but_total_includes_it(tmp_path, monkeypatch):
    async def go():
        client = TutorAI(tmp_path, model=MODEL, binary="/missing/claude")
        async def events(self, payload, timeout, path="/api/chat"):
            if path == "/api/experimental/web_search":
                yield {"results": []}
            elif not payload["messages"]:
                await asyncio.sleep(.04)
                yield {"done": True, "done_reason": "load"}
            else:
                yield {"message": {"content": '{"reply":"I cannot verify current facts."}'}, "done": True}
        monkeypatch.setattr(LocalAI, "_events", events)
        before = time.monotonic()
        [part async for part in client.stream("Explain", web_query="Look up the latest syllabus")]
        elapsed = time.monotonic() - before
        performance = client.last.performance
        assert performance["total_seconds"] >= .03
        assert abs(performance["total_seconds"] - elapsed) < .02
        assert performance["first_token_seconds"] >= .03
        assert performance["search_seconds"] < performance["total_seconds"] - .02
        await client.close()
    asyncio.run(go())


def test_cached_image_answer_never_waits_for_or_loads_an_evicted_model(tmp_path, monkeypatch):
    async def go():
        client = TutorAI(tmp_path, model=MODEL, binary="/missing/claude")
        image = tmp_path / "question.png"
        image.write_bytes(b"same exact image")
        calls, reading = [], []
        async def events(self, payload, timeout, path="/api/chat"):
            calls.append(bool(payload["messages"]))
            yield ({"message": {"content": '{"score":1}'}, "done": True}
                   if payload["messages"] else {"done": True, "done_reason": "load"})
        async def describe(self, *args, **kwargs):
            reading.append(True)
            return {"transcription": "6 N", "diagram": "", "uncertainties": []}, Result()
        monkeypatch.setattr(LocalAI, "_events", events)
        monkeypatch.setattr(NativeOCR, "describe_image", describe)
        first = await client.one_shot("Mark", model=MODEL, image=image)
        assert first[0] == {"score": 1}
        async def no_runtime(self, *args, **kwargs):
            pytest.fail("A cached image answer must not access the model runtime")
            yield
        monkeypatch.setattr(LocalAI, "_events", no_runtime)
        second = await client.one_shot("Mark", model=MODEL, image=image)
        assert second[0] == first[0] and second[1].performance["cached_reply"]
        assert len(reading) == 1 and calls == [False, False, True]
        await client.close()
    asyncio.run(go())


def test_background_image_preparation_still_loads_after_busy_inference_finishes(tmp_path, monkeypatch):
    async def go():
        client = TutorAI(tmp_path, model=MODEL, binary="/missing/claude")
        image = tmp_path / "question.png"
        image.write_bytes(b"pixels")
        reading, finish, loaded = asyncio.Event(), asyncio.Event(), asyncio.Event()
        async def events(self, payload, timeout, path="/api/chat"):
            assert not payload["messages"]
            loaded.set()
            yield {"done": True, "done_reason": "load"}
        async def describe(self, *args, **kwargs):
            reading.set()
            await finish.wait()
            return {"transcription": "6 N", "diagram": "", "uncertainties": []}, Result()
        monkeypatch.setattr(LocalAI, "_events", events)
        monkeypatch.setattr(NativeOCR, "describe_image", describe)
        await client.local._lock.acquire()
        task = asyncio.create_task(client.prepare_local(MODEL, image=image))
        await reading.wait()
        assert not loaded.is_set()
        client.local._lock.release()
        finish.set()
        await task
        assert loaded.is_set(), "Busy inference must not permanently suppress speculative preparation"
        await client.close()
    asyncio.run(go())


def test_loading_deadline_includes_wait_for_another_image_observation(tmp_path, monkeypatch):
    from tutor_app.local_vision import LocalVision

    async def go():
        client = TutorAI(tmp_path, model=MODEL, binary="/missing/claude")
        client._vision = LocalVision()
        image = tmp_path / "question.png"
        image.write_bytes(b"pixels")
        deadline = time.monotonic() + .15
        async def events(self, payload, timeout, path="/api/chat"):
            assert timeout <= deadline - time.monotonic() + .01, "Loading must use only the remaining request budget"
            yield ({"message": {"content": '{"score":1}'}, "done": True}
                   if payload["messages"] else {"done": True, "done_reason": "load"})
        async def describe(self, *args, **kwargs):
            return {"transcription": "6 N", "diagram": "", "uncertainties": []}, Result()
        monkeypatch.setattr(LocalAI, "_events", events)
        monkeypatch.setattr(NativeOCR, "describe_image", describe)
        await client._vision._lock.acquire()
        task = asyncio.create_task(client.one_shot("Mark", model=MODEL, image=image, timeout=.15))
        await asyncio.sleep(.04)
        client._vision._lock.release()
        try:
            data, result = await task
            assert data == {"score": 1} and result.ok
        finally:
            await client.close()
    asyncio.run(go())
