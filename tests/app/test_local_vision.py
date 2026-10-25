"""Image observations stay local, exact, bounded and separate from the tutor's private context."""
import asyncio

import pytest

from tutor_app.ai import Result


MODEL = "ollama:qwen3.5:2b"
OTHER = "ollama:qwen3.5:4b"


def observation():
    return {"transcription": "Which graph is correct? A B C D", "diagram": "Horizontal axis t / s, ticks 0, 2, 4; vertical axis v / m s⁻¹, ticks 0, 6. A line joins (0, 0) to (4, 6).",
            "uncertainties": ["The small label beside B is unreadable."]}


def test_full_image_bytes_and_all_visible_question_details_are_retained(tmp_path):
    from tutor_app.local_vision import LocalVision

    async def go():
        image = tmp_path / "question.png"
        original = b"\x89PNG\r\n\x1a\nfull question scan"
        image.write_bytes(original)
        calls = []
        async def describe(pixels, prompt, **kw):
            calls.append((pixels, prompt, kw))
            return observation(), Result(performance={"load_seconds": 1, "input_tokens": 50, "output_tokens": 60})
        seen = await LocalVision().describe(image, model=MODEL, describe=describe, timeout=3)
        assert calls[0][0] == original and image.read_bytes() == original
        assert calls[0][2]["model"] == MODEL and 0 < calls[0][2]["timeout"] <= 3
        assert calls[0][2]["schema"]["additionalProperties"] is False
        assert "options" in calls[0][1].lower() and "axis" in calls[0][1].lower()
        assert "do not solve" in calls[0][2]["system"].lower()
        assert "Which graph is correct? A B C D" in seen.context
        assert "(4, 6)" in seen.context and "unreadable" in seen.context
        assert "untrusted" in seen.context.lower() and "instructions" in seen.context.lower()
        assert not seen.cached and seen.model == MODEL
        assert seen.performance["vision_input_tokens"] == 50
    asyncio.run(go())


def test_bytes_input_is_shared_by_hashing_and_transport_without_rereading_a_path():
    from tutor_app.local_vision import LocalVision

    async def go():
        bridge, pixels, calls = LocalVision(), b"already read exact image bytes", []
        async def describe(image, *args, **kw):
            calls.append(image)
            return observation(), Result()
        first = await bridge.describe(pixels, model=MODEL, describe=describe)
        cached = await bridge.describe(pixels, model=MODEL, describe=describe)
        assert calls == [pixels] and calls[0] is pixels
        assert first.context == cached.context and cached.cached
        assert not (await bridge.describe(b"different bytes", model=MODEL, describe=describe)).cached
        assert len(calls) == 2
    asyncio.run(go())


def test_exact_native_ocr_id_uses_the_same_private_success_cache():
    from tutor_app.local_vision import LocalVision

    async def go():
        bridge, calls = LocalVision(), []
        async def describe(image, *args, **kwargs):
            calls.append(image)
            return {"transcription": "Literal text only", "diagram": "",
                    "uncertainties": ["No graph geometry was interpreted; ask for clarification."]}, Result()
        one = await bridge.describe(b"exact pixels", model="macos:vision", describe=describe)
        two = await bridge.describe(b"exact pixels", model="macos:vision", describe=describe)
        assert len(calls) == 1 and one.model == "macos:vision" and two.cached
        assert "No graph geometry was interpreted" in one.context
    asyncio.run(go())


@pytest.mark.parametrize("model", ["macos:vision", MODEL])
def test_failed_helper_keeps_bounded_actionable_diagnostic_without_caching(model):
    from tutor_app.local_vision import LocalVision, VisionError

    async def go():
        bridge, calls = LocalVision(), []
        async def describe(*args, **kwargs):
            calls.append(True)
            return None, Result(ok=False, message="Install Xcode Command Line Tools. " + "x" * 2000)
        for _ in range(2):
            with pytest.raises(VisionError) as failure:
                await bridge.describe(b"image bytes", model=model, describe=describe)
            assert "Install Xcode Command Line Tools" in str(failure.value)
            assert len(str(failure.value)) < 800
        assert len(calls) == 2
    asyncio.run(go())


def test_equal_content_coalesces_and_content_model_or_extraction_prompt_changes_miss(tmp_path, monkeypatch):
    from tutor_app import local_vision

    async def go():
        image, duplicate = tmp_path / "one.png", tmp_path / "two.png"
        image.write_bytes(b"same image")
        duplicate.write_bytes(b"same image")
        bridge, started, finish, calls = local_vision.LocalVision(), asyncio.Event(), asyncio.Event(), []
        async def describe(pixels, prompt, **kw):
            calls.append((pixels, prompt, kw["model"]))
            started.set()
            await finish.wait()
            return observation(), Result()
        one = asyncio.create_task(bridge.describe(image, model=MODEL, describe=describe))
        await started.wait()
        two = asyncio.create_task(bridge.describe(duplicate, model=MODEL, describe=describe))
        finish.set()
        first, cached = await asyncio.gather(one, two)
        assert len(calls) == 1 and not first.cached and cached.cached
        assert cached.performance["vision_cached"]
        image.write_bytes(b"changed image")
        await bridge.describe(image, model=MODEL, describe=describe)
        await bridge.describe(image, model=OTHER, describe=describe)
        monkeypatch.setattr(local_vision, "EXTRACTION_PROMPT", "Read the whole revised question image.")
        await bridge.describe(image, model=OTHER, describe=describe)
        assert len(calls) == 4
    asyncio.run(go())


def test_cache_expires_evicts_old_entries_and_does_not_share_mutable_performance(tmp_path):
    from tutor_app.local_vision import LocalVision

    async def go():
        now, calls = [1.0], []
        bridge, image = LocalVision(clock=lambda: now[0]), tmp_path / "scan.png"
        async def describe(*args, **kw):
            calls.append(True)
            return observation(), Result()
        image.write_bytes(b"original")
        first = await bridge.describe(image, model=MODEL, describe=describe)
        first.performance["private"] = "mutated"
        cached = await bridge.describe(image, model=MODEL, describe=describe)
        assert "private" not in cached.performance
        now[0] += 601
        assert not (await bridge.describe(image, model=MODEL, describe=describe)).cached
        for index in range(16):
            image.write_bytes(f"another {index}".encode())
            await bridge.describe(image, model=MODEL, describe=describe)
        image.write_bytes(b"original")
        assert not (await bridge.describe(image, model=MODEL, describe=describe)).cached
        assert len(calls) == 19
    asyncio.run(go())


@pytest.mark.parametrize("bad", [None, {}, {"transcription": "", "diagram": "", "uncertainties": []},
    {"transcription": "x", "diagram": 4, "uncertainties": []},
    {"transcription": "x", "diagram": "", "uncertainties": "none"},
    {"transcription": "x" * 65537, "diagram": "", "uncertainties": []}])
def test_unusable_or_oversized_observations_fail_without_caching_or_losing_image(tmp_path, bad):
    from tutor_app.local_vision import LocalVision, VisionError

    async def go():
        image, calls = tmp_path / "scan.png", []
        image.write_bytes(b"keep this image")
        bridge = LocalVision()
        async def describe(*args, **kw):
            calls.append(True)
            return bad, Result()
        for _ in range(2):
            with pytest.raises(VisionError, match="image|vision"):
                await bridge.describe(image, model=MODEL, describe=describe)
        assert len(calls) == 2 and image.read_bytes() == b"keep this image"
    asyncio.run(go())


def test_helper_failure_is_actionable_and_never_cached(tmp_path):
    from tutor_app.local_vision import LocalVision, VisionError

    async def go():
        image, calls = tmp_path / "scan.png", []
        image.write_bytes(b"original")
        async def describe(*args, **kw):
            calls.append(True)
            return None, Result(ok=False, message="External SSD unavailable.")
        bridge = LocalVision()
        for _ in range(2):
            with pytest.raises(VisionError, match="vision"):
                await bridge.describe(image, model=MODEL, describe=describe)
        assert len(calls) == 2 and image.read_bytes() == b"original"
    asyncio.run(go())


def test_missing_image_and_nonlocal_helper_never_launch_inference(tmp_path):
    from tutor_app.local_vision import LocalVision, VisionError

    async def go():
        async def describe(*args, **kw):
            pytest.fail("Inference must not start without a local helper and readable image.")
        bridge = LocalVision()
        with pytest.raises(VisionError):
            await bridge.describe(tmp_path / "missing.png", model=MODEL, describe=describe)
        image = tmp_path / "scan.png"
        image.write_bytes(b"image")
        for model in ("sonnet", "codex:gpt-6.1-sol", "ollama:model:cloud", "macos:other"):
            with pytest.raises(VisionError):
                await bridge.describe(image, model=model, describe=describe)
    asyncio.run(go())


def test_reset_rejects_active_and_pre_reset_queued_extraction(tmp_path):
    from tutor_app.local_vision import LocalVision

    async def go():
        bridge, started, finish, calls = LocalVision(), asyncio.Event(), asyncio.Event(), []
        image = tmp_path / "scan.png"
        image.write_bytes(b"image")
        async def describe(*args, **kw):
            calls.append(True)
            started.set()
            await finish.wait()
            return observation(), Result()
        active = asyncio.create_task(bridge.describe(image, model=MODEL, describe=describe))
        await started.wait()
        queued = asyncio.create_task(bridge.describe(image, model=MODEL, describe=describe))
        await asyncio.sleep(0)
        bridge.clear()
        finish.set()
        for task in (active, queued):
            with pytest.raises(asyncio.CancelledError):
                await task
        fresh = await bridge.describe(image, model=MODEL, describe=describe)
        assert not fresh.cached and len(calls) == 2
    asyncio.run(go())


def test_cancelled_extraction_closes_work_and_is_not_cached(tmp_path):
    from tutor_app.local_vision import LocalVision

    async def go():
        bridge, started, closed, calls = LocalVision(), asyncio.Event(), asyncio.Event(), []
        image = tmp_path / "scan.png"
        image.write_bytes(b"image")
        async def describe(*args, **kw):
            calls.append(True)
            if len(calls) == 1:
                started.set()
                try:
                    await asyncio.Event().wait()
                finally:
                    closed.set()
            return observation(), Result()
        active = asyncio.create_task(bridge.describe(image, model=MODEL, describe=describe))
        await started.wait()
        active.cancel()
        with pytest.raises(asyncio.CancelledError):
            await active
        assert closed.is_set()
        assert not (await bridge.describe(image, model=MODEL, describe=describe)).cached
        assert len(calls) == 2
    asyncio.run(go())


def test_queue_wait_and_helper_work_share_the_deadline(tmp_path):
    from tutor_app.local_vision import LocalVision, VisionError

    async def go():
        bridge, started, finish, calls = LocalVision(), asyncio.Event(), asyncio.Event(), []
        image = tmp_path / "scan.png"
        image.write_bytes(b"image")
        async def describe(*args, **kw):
            calls.append(True)
            started.set()
            await finish.wait()
            return observation(), Result()
        active = asyncio.create_task(bridge.describe(image, model=MODEL, describe=describe))
        await started.wait()
        try:
            with pytest.raises(VisionError, match="long|time"):
                await bridge.describe(image, model=MODEL, describe=describe, timeout=.01)
            assert len(calls) == 1
        finally:
            finish.set()
            await active
        bridge.clear()
        finish.clear()
        with pytest.raises(VisionError, match="long|time"):
            await bridge.describe(image, model=MODEL, describe=describe, timeout=.01)
        assert len(calls) == 2
    asyncio.run(go())
