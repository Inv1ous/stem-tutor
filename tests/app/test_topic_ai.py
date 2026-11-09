"""The app's synchronous topic adapter: images, model choice, and the loop bridge."""
import asyncio
import threading
from pathlib import Path

import pytest

from tutor_app import local_models
from tutor_app.ai import Result
from tutor_app.topic_ai import TopicAI


class FakeAI:
    def __init__(self, model="haiku", ok=True, codex=False):
        self.model, self.ok, self.codex, self.calls = model, ok, codex, []

    def available_for(self, model):
        return self.codex if str(model).startswith('codex:') else True

    async def one_shot(self, prompt, schema=None, model=None, timeout=120, system=None, speech=False, think=False,
                       image=None, images=None):
        self.calls.append({'prompt': prompt, 'schema': schema, 'model': model, 'system': system, 'images': images})
        return ({'kcs': ['9702-2.1.1']}, Result(ok=True)) if self.ok else (None, Result(ok=False, message='off'))


@pytest.fixture
def loop():
    running = asyncio.new_event_loop()
    thread = threading.Thread(target=running.run_forever, daemon=True)
    thread.start()
    yield running
    running.call_soon_threadsafe(running.stop)
    thread.join(5)
    running.close()


def call_from_worker(adapter, request):
    out = {}

    def run():
        out['reply'] = adapter(request)
    worker = threading.Thread(target=run)
    worker.start()
    worker.join(10)
    return out['reply']


def request(images=()):
    return {'purpose': 'topic_identification', 'course': '9702', 'system': 'sys', 'schema': {'type': 'object'},
            'prompt': 'Which idea?', 'images': [str(p) for p in images]}


def test_text_only_question_uses_the_configured_model(loop):
    ai = FakeAI(model='haiku')
    adapter = TopicAI(ai, loop, model='haiku')
    assert call_from_worker(adapter, request()) == {'kcs': ['9702-2.1.1']}
    assert ai.calls[0]['model'] == 'haiku' and ai.calls[0]['images'] is None


def test_images_switch_to_the_vision_capable_local_model(loop, monkeypatch):
    monkeypatch.setattr(local_models, 'available_models', lambda: (local_models.DEFAULT_VISION_MODEL,))
    ai = FakeAI(model='haiku')
    adapter = TopicAI(ai, loop, model='haiku')
    image = Path('/tmp/q.png')
    assert call_from_worker(adapter, request([image])) == {'kcs': ['9702-2.1.1']}
    assert ai.calls[0]['model'] == local_models.DEFAULT_VISION_MODEL
    assert ai.calls[0]['images'] == [image]


def test_no_image_capable_model_means_unavailable(loop, monkeypatch):
    monkeypatch.setattr(local_models, 'available_models', lambda: ())
    ai = FakeAI(model='haiku', codex=False)
    assert call_from_worker(TopicAI(ai, loop, model='haiku'), request([Path('/tmp/q.png')])) is None
    assert not ai.calls


def test_chatgpt_is_the_image_fallback_when_no_local_vision_model(loop, monkeypatch):
    monkeypatch.setattr(local_models, 'available_models', lambda: ())
    ai = FakeAI(model='haiku', codex=True)
    assert call_from_worker(TopicAI(ai, loop, model='haiku'), request([Path('/tmp/q.png')])) == {'kcs': ['9702-2.1.1']}
    assert ai.calls[0]['model'].startswith('codex:') and ai.calls[0]['images'] == [Path('/tmp/q.png')]


def test_failed_call_is_unavailable(loop):
    ai = FakeAI(ok=False)
    assert call_from_worker(TopicAI(ai, loop), request()) is None


def test_main_thread_never_blocks_the_app_loop(loop):
    ai = FakeAI()
    assert TopicAI(ai, loop)(request()) is None and not ai.calls
