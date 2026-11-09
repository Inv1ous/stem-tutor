"""Complete topical source pages must reach only the selected marking provider."""
import asyncio

import pytest

from tutor_app import tutor_ai
from tutor_app.ai import Result


@pytest.mark.parametrize('model,page_count,want', [
    ('codex:gpt-6.1-terra', 2, 'codex'),
    ('ollama:gemma4:e4b', 1, 'local'),
    ('ollama:gemma4:e4b', 2, None),
    ('haiku', 1, None),
    ('haiku', 2, None),
])
def test_image_lists_reach_only_a_provider_that_can_read_every_page(
        tmp_path, monkeypatch, model, page_count, want):
    calls = []
    pages = [tmp_path / f'page-{n}.png' for n in range(page_count)]
    for n, page in enumerate(pages):
        page.write_bytes(f'disposable page {n}'.encode())

    def provider(name):
        async def one_shot(self, prompt, **kwargs):
            calls.append((name, prompt, kwargs))
            return {'feedback': 'Scripted verdict'}, Result()
        return one_shot

    monkeypatch.setattr(tutor_ai.Claude, 'one_shot', provider('claude'))
    monkeypatch.setattr(tutor_ai.CodexAI, 'one_shot', provider('codex'))
    monkeypatch.setattr(tutor_ai.LocalAI, 'one_shot', provider('local'))
    monkeypatch.setattr(tutor_ai.TutorAI, 'available_for', lambda self, chosen: True)
    monkeypatch.setattr(tutor_ai.local_models, 'supports_vision', lambda chosen: True)
    monkeypatch.setattr(tutor_ai.LocalAI, '_effort', lambda *args: None)

    async def go():
        client = tutor_ai.TutorAI(tmp_path, model=model, binary='/missing/claude')
        data, result = await client.one_shot('Mark complete source.', model=model, images=pages)
        if want is None:
            assert data is None and not result.ok
            assert not calls
        else:
            assert result.ok and data == {'feedback': 'Scripted verdict'}
            assert len(calls) == 1
            name, prompt, kwargs = calls[0]
            assert name == want and prompt == 'Mark complete source.'
            assert kwargs['model'] == model
            if want == 'codex':
                assert kwargs['images'] == pages
                assert 'image' not in kwargs
            else:
                assert kwargs['image'] == pages[0].read_bytes()
                assert 'images' not in kwargs
        await client.close()
    asyncio.run(go())
