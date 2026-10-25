"""Text-only models receive local observations; native models keep their image and cloud paths stay unchanged."""
import asyncio

from tutor_app import ai, tutor_ai
from tutor_app.local_vision import VisionError

TEXT='ollama:gpt-oss:20b'
HELPER='ollama:qwen3.5:2b'
NATIVE='ollama:qwen3.5:4b'


def setup(tmp_path, monkeypatch):
    image=tmp_path/'figure.png'
    image.write_bytes(b'synthetic image bytes')
    monkeypatch.setattr(tutor_ai.local_models,'available_models',lambda:(TEXT,HELPER,NATIVE))
    client=tutor_ai.TutorAI(tmp_path,binary='/missing/claude',model=TEXT)
    client.local_vision_model=HELPER  # exercise the explicitly selected experimental LLM helper
    return client,image


def test_text_stream_uses_observations_and_reuses_prefetch_without_raw_image(tmp_path,monkeypatch):
    async def go():
        client,image=setup(tmp_path,monkeypatch)
        described,primary=[],[]
        async def describe(pixels,prompt,**kw):
            described.append((pixels,kw['model']))
            return {'transcription':'Axis t/s; v/m s^-1','diagram':'Line joins labelled points (0,0) and (3,6).','uncertainties':[]},ai.Result(performance={'total_seconds':1})
        async def warm(model):
            return ai.Result()
        async def stream(prompt,**kw):
            primary.append((prompt,kw))
            client.local.last=ai.Result(text='Use the labelled axes.',performance={'model':TEXT,'total_seconds':2,'first_token_seconds':1})
            yield client.local.last.text
        monkeypatch.setattr(client.local,'describe_image',describe)
        monkeypatch.setattr(client.local,'warm',warm)
        monkeypatch.setattr(client.local,'stream',stream)
        await client.prepare_local(TEXT,image=image)
        assert ''.join([x async for x in client.stream('OPEN question, do not reveal answer',image=image)])=='Use the labelled axes.'
        assert described==[(b'synthetic image bytes',HELPER)]
        assert primary[0][1]['image'] is None
        assert 'UNTRUSTED IMAGE OBSERVATIONS' in primary[0][0] and 'OPEN question' in primary[0][0]
        assert client.last.performance['vision_cached']
        await client.close()
    asyncio.run(go())


def test_native_one_shot_passes_exact_bytes_and_cache_changes_with_image(tmp_path,monkeypatch):
    async def go():
        client,image=setup(tmp_path,monkeypatch)
        calls=[]
        async def answer(prompt,**kw):
            calls.append(kw['image'])
            return {'feedback':'Good'},ai.Result(text='Good',performance={'model':NATIVE})
        monkeypatch.setattr(client.local,'one_shot',answer)
        await client.one_shot('mark',model=NATIVE,image=image)
        await client.one_shot('mark',model=NATIVE,image=image)
        assert calls==[b'synthetic image bytes']
        image.write_bytes(b'different image')
        await client.one_shot('mark',model=NATIVE,image=image)
        assert calls[-1]==b'different image' and len(calls)==2
        await client.close()
    asyncio.run(go())


def test_text_marking_never_runs_after_vision_failure_or_without_helper(tmp_path,monkeypatch):
    async def go():
        client,image=setup(tmp_path,monkeypatch)
        calls=[]
        async def broken(*args,**kw):
            return None,ai.Result(ok=False)
        async def forbidden(*args,**kw):
            calls.append(True)
            return {},ai.Result()
        monkeypatch.setattr(client.local,'describe_image',broken)
        monkeypatch.setattr(client.local,'one_shot',forbidden)
        data,result=await client.one_shot('mark',model=TEXT,image=image)
        assert data is None and not result.ok and not calls
        assert 'image' in result.message.lower()
        monkeypatch.setattr(tutor_ai.local_models,'available_models',lambda:(TEXT,))
        assert [x async for x in client.stream('ask',image=image)]==[]
        assert not client.last.ok and not calls
        await client.close()
    asyncio.run(go())


def test_reset_during_observation_never_launches_primary(tmp_path,monkeypatch):
    async def go():
        client,image=setup(tmp_path,monkeypatch)
        started,finish,calls=asyncio.Event(),asyncio.Event(),[]
        async def describe(*args,**kw):
            started.set()
            await finish.wait()
            return {'transcription':'A','diagram':'B','uncertainties':[]},ai.Result()
        async def forbidden(*args,**kw):
            calls.append(True)
            yield 'stale'
        monkeypatch.setattr(client.local,'describe_image',describe)
        monkeypatch.setattr(client.local,'stream',forbidden)
        async def consume():
            return [x async for x in client.stream('old',image=image)]
        task=asyncio.create_task(consume())
        await asyncio.wait_for(started.wait(), 1)
        await client.reset(warm=False)
        finish.set()
        try:
            await task
        except asyncio.CancelledError:
            pass
        assert not calls
        await client.close()
    asyncio.run(go())


def test_cached_answer_notification_does_not_hide_new_image_work(tmp_path,monkeypatch):
    from test_tui import app_for
    app,_=app_for(tmp_path,monkeypatch)
    said=[]
    monkeypatch.setattr(app,'notify',lambda message,**kwargs:said.append(message))
    app.show_local_performance(ai.Result(performance={'model':TEXT,'cached_reply':True,'vision_model':HELPER,
        'vision_cached':False,'vision_seconds':2.4,'vision_output_tokens':50}))
    assert 'no model generation needed' not in said[0]
    assert 'image' in said[0].lower() and '2.4' in said[0] and '50' in said[0]


def test_default_text_bridge_uses_native_ocr_without_loading_a_vision_llm(tmp_path,monkeypatch):
    async def go():
        client,image=setup(tmp_path,monkeypatch)
        client.local_vision_model='macos:vision'
        called=[]
        class OCR:
            async def describe_image(self,pixels,prompt,**kwargs):
                called.append((pixels,kwargs['model']))
                return {'transcription':'Axis labels only','diagram':'',
                        'uncertainties':['Geometry is not interpreted.']},ai.Result()
            async def reset(self):
                pass
            async def close(self):
                pass
        monkeypatch.setattr(tutor_ai,'NativeOCR',OCR,raising=False)
        async def stream(prompt,**kwargs):
            assert 'Geometry is not interpreted' in prompt and kwargs['image'] is None
            client.local.last=ai.Result(text='Please describe the curve if its position matters.')
            yield client.local.last.text
        def forbidden(*args,**kwargs):
            raise AssertionError('Native OCR must not start a vision LLM.')
        monkeypatch.setattr(client.local,'describe_image',forbidden)
        monkeypatch.setattr(client.local,'stream',stream)
        assert [x async for x in client.stream('OPEN question',image=image)]
        assert called==[(b'synthetic image bytes','macos:vision')]
        await client.close()
    asyncio.run(go())
