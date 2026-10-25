"""Native OCR is literal, on-device and cancellable; its executable cache never stores the input image."""
import asyncio
import json
from pathlib import Path

import pytest


PAYLOAD = {"width": 900, "height": 500, "lines": [
    {"text": "D The wave has a wavelength of 20 ms.", "confidence": .97,
     "box": {"x": .05, "y": .1, "width": .8, "height": .04}},
    {"text": "time / ms", "confidence": .8, "box": {"x": .7, "y": .4, "width": .2, "height": .04}}]}


@pytest.fixture
def native(tmp_path, monkeypatch):
    from tutor_app import local_ocr

    root = tmp_path / "SSD" / "LocalAI"
    root.mkdir(parents=True)
    monkeypatch.setattr(local_ocr.local_models, "ROOT", root)
    monkeypatch.setattr(local_ocr.sys, "platform", "darwin")
    compiler, runtime = tmp_path / "swiftc", tmp_path / "fake-ocr"
    compiler.write_text('''#!/usr/bin/env python3
import os, shutil, sys
from pathlib import Path
with Path(os.environ['OCR_COMPILES']).open('a') as out: out.write('compiled\\n')
if os.environ.get('OCR_COMPILE_FAIL'): sys.exit(1)
target = Path(sys.argv[sys.argv.index('-o') + 1])
shutil.copy2(os.environ['OCR_RUNTIME'], target)
target.chmod(0o755)
''')
    runtime.write_text('''#!/usr/bin/env python3
import json, os, sys, time
from pathlib import Path
pixels = sys.stdin.buffer.read()
Path(os.environ['OCR_STDIN']).write_bytes(pixels)
if os.environ.get('OCR_WAIT'): time.sleep(30)
if os.environ.get('OCR_FAIL'): sys.exit(1)
print(os.environ['OCR_PAYLOAD'])
''')
    compiler.chmod(0o755)
    runtime.chmod(0o755)
    monkeypatch.setenv("OCR_RUNTIME", str(runtime))
    monkeypatch.setenv("OCR_COMPILES", str(tmp_path / "compiles"))
    monkeypatch.setenv("OCR_STDIN", str(tmp_path / "stdin"))
    monkeypatch.setenv("OCR_PAYLOAD", json.dumps(PAYLOAD))
    return local_ocr, root, compiler, tmp_path


async def describe(client, image=b"unique private image bytes", timeout=2):
    return await client.describe_image(image, "Private tutor context must never reach OCR", schema={},
                                       model="macos:vision", timeout=timeout, system="Private mark scheme")


def test_ocr_returns_literal_lines_confidence_and_text_boxes_without_interpreting_geometry(native):
    module, root, compiler, folder = native
    async def go():
        client = module.NativeOCR(compiler=str(compiler))
        data, result = await describe(client)
        assert result.ok and data["diagram"] == "" and result.usage == {} and result.speech == ""
        literal = json.loads(data["transcription"])
        assert literal["lines"] == PAYLOAD["lines"]
        assert "text" in literal["coordinate_system"].lower()
        assert any("geometry" in item.lower() for item in data["uncertainties"])
        assert any("native vision" in item.lower() for item in data["uncertainties"])
        assert (folder / "stdin").read_bytes() == b"unique private image bytes"
        assert all(b"unique private image bytes" not in path.read_bytes() for path in root.rglob("*") if path.is_file())
        assert result.performance["model"] == "macos:vision"
        await client.close()
    asyncio.run(go())


def test_compilation_is_cached_on_ssd_across_clients_and_invalidated_by_source_hash(native, monkeypatch):
    module, root, compiler, folder = native
    async def go():
        one = module.NativeOCR(compiler=str(compiler))
        assert (await describe(one))[1].ok
        await one.close()
        two = module.NativeOCR(compiler=str(compiler))
        assert (await describe(two))[1].ok
        assert (folder / "compiles").read_text().splitlines() == ["compiled"]
        source = folder / "revised.swift"
        source.write_bytes(module.SOURCE.read_bytes() + b"\n// new source revision\n")
        monkeypatch.setattr(module, "SOURCE", source)
        assert (await describe(two))[1].ok
        assert (folder / "compiles").read_text().splitlines() == ["compiled", "compiled"]
        assert len(list((root / "tutor-runtime").glob("vision-ocr-*"))) == 2
        await two.close()
    asyncio.run(go())


@pytest.mark.parametrize("payload", ["not JSON", "{}", json.dumps({**PAYLOAD, "lines": []}),
    json.dumps({**PAYLOAD, "lines": [{"text": "x", "confidence": 4, "box": PAYLOAD["lines"][0]["box"]}]}),
    json.dumps({**PAYLOAD, "lines": [{"text": "x", "confidence": .5, "box": {"x": "bad"}}]})])
def test_unreadable_native_output_is_an_actionable_failure_not_guessed_text(native, monkeypatch, payload):
    module, _, compiler, _ = native
    monkeypatch.setenv("OCR_PAYLOAD", payload)
    async def go():
        client = module.NativeOCR(compiler=str(compiler))
        data, result = await describe(client)
        assert data is None and not result.ok and "native vision" in result.message.lower()
        await client.close()
    asyncio.run(go())


@pytest.mark.parametrize("failure", ["compiler", "ssd", "image", "platform"])
def test_missing_requirements_never_write_images_or_start_unavailable_services(native, monkeypatch, failure):
    module, root, compiler, folder = native
    if failure == "compiler":
        compiler.unlink()
    elif failure == "ssd":
        root.rename(root.with_name("disconnected"))
    elif failure == "platform":
        monkeypatch.setattr(module.sys, "platform", "linux")
    async def go():
        client = module.NativeOCR(compiler=str(compiler))
        data, result = await describe(client, b"" if failure == "image" else b"pixels")
        assert data is None and not result.ok and "native vision" in result.message.lower()
        assert not (folder / "stdin").exists()
        await client.close()
    asyncio.run(go())


def test_native_timeout_terminates_and_reaps_the_process(native, monkeypatch):
    module, _, compiler, folder = native
    async def go():
        client = module.NativeOCR(compiler=str(compiler))
        assert (await describe(client))[1].ok  # compilation is outside this short OCR deadline
        monkeypatch.setenv("OCR_WAIT", "1")
        data, result = await describe(client, timeout=.05)
        assert data is None and not result.ok and "long" in result.message
        assert not client._procs
        await client.close()
    asyncio.run(go())


def test_failed_compilation_is_actionable_and_never_publishes_an_executable(native, monkeypatch):
    module, root, compiler, _ = native
    monkeypatch.setenv("OCR_COMPILE_FAIL", "1")
    async def go():
        client = module.NativeOCR(compiler=str(compiler))
        data, result = await describe(client)
        assert data is None and not result.ok and "compile" in result.message.lower()
        assert not list((root / "tutor-runtime").glob("vision-ocr-*"))
        assert not list((root / "tutor-runtime").glob(".vision-build-*"))
        await client.close()
    asyncio.run(go())


def test_cancelled_launch_remains_owned_until_the_late_child_is_reaped(native, monkeypatch):
    module, _, compiler, _ = native
    async def go():
        client = module.NativeOCR(compiler=str(compiler))
        assert (await describe(client))[1].ok
        started, release, processes = asyncio.Event(), asyncio.Event(), []
        launch = module.asyncio.create_subprocess_exec
        async def delayed(*args, **kwargs):
            child = await launch(*args, **kwargs)
            processes.append(child)
            started.set()
            await release.wait()
            return child
        monkeypatch.setattr(module.asyncio, "create_subprocess_exec", delayed)
        task = asyncio.create_task(describe(client))
        await asyncio.wait_for(started.wait(), 1)
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task
        closing = asyncio.create_task(client.close())
        release.set()
        await asyncio.wait_for(closing, 1)
        assert processes[0].returncode is not None and not client._procs
    asyncio.run(go())


def test_reset_cancels_active_and_queued_ocr_without_launching_the_old_queue(native, monkeypatch):
    module, _, compiler, folder = native
    async def go():
        client = module.NativeOCR(compiler=str(compiler))
        assert (await describe(client))[1].ok
        monkeypatch.setenv("OCR_WAIT", "1")
        active = asyncio.create_task(describe(client))
        for _ in range(100):
            if client._procs:
                break
            await asyncio.sleep(.005)
        assert client._procs
        queued = asyncio.create_task(describe(client, b"old queued image"))
        await asyncio.sleep(0)
        await client.reset()
        for task in (active, queued):
            with pytest.raises(asyncio.CancelledError):
                await task
        assert (folder / "stdin").read_bytes() != b"old queued image"
        assert not client._procs
        monkeypatch.delenv("OCR_WAIT")
        assert (await describe(client, b"fresh image"))[1].ok
        await client.close()
    asyncio.run(go())
