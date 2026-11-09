"""Structured Codex marking receives every source image without chat/history leakage."""
import asyncio

import pytest

from test_codex_ai import MODEL, make, requests


@pytest.mark.parametrize('missing', [False, True])
def test_codex_one_shot_images_are_ordered_complete_and_isolated(tmp_path, monkeypatch, missing):
    client = make(tmp_path, monkeypatch)
    pages = [tmp_path / f'page-{i}.png' for i in (1, 2)]
    for page in pages:
        page.write_bytes(b'disposable transport fixture')
    if missing:
        pages[-1].unlink()
    async def go():
        data, result = await client.one_shot('Mark complete source.', model=MODEL, images=pages,
                                            schema={'type': 'object', 'properties': {'feedback': {'type': 'string'}},
                                                    'required': ['feedback']})
        if missing:
            assert not result.ok and data is None
            assert not (tmp_path / 'requests.jsonl').exists()
        else:
            assert result.ok
            _ = [part async for part in client.stream('Separate chat', model=MODEL)]
            calls = requests(tmp_path)
            args = calls[0]['args']
            assert [args[i + 1] for i, arg in enumerate(args[:-1]) if arg == '--image'] == [str(p) for p in pages]
            assert '--image' not in calls[1]['args']
            assert len(calls[1]['prompt']['messages']) == 1
        await client.close()
    asyncio.run(go())


def test_image_disappearing_before_transport_never_sends_a_partial_question(tmp_path, monkeypatch):
    client = make(tmp_path, monkeypatch)
    pages = [tmp_path / f'page-{i}.png' for i in (1, 2)]
    for page in pages:
        page.write_bytes(b'disposable transport fixture')
    events = client._events
    async def vanished(*args, **kwargs):
        pages[-1].unlink()
        async for event in events(*args, **kwargs):
            yield event
    monkeypatch.setattr(client, '_events', vanished)
    async def go():
        data, result = await client.one_shot('Mark both pages.', model=MODEL, images=pages)
        assert data is None and not result.ok
        assert not (tmp_path / 'requests.jsonl').exists()
        await client.close()
    asyncio.run(go())
