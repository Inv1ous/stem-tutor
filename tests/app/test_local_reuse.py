"""Local structured replies can be reused without changing provider or reset semantics."""
import asyncio

from tutor_app.ai import Result
from tutor_app.local_reuse import LocalReplies, reply_key


def test_successful_exact_reply_is_reused_and_returned_objects_are_independent():
    async def go():
        replies, calls = LocalReplies(), []
        async def answer(timeout):
            calls.append(timeout)
            return {"feedback": "Good."}, Result(text='{"feedback":"Good."}', performance={"model": "local", "output_tokens": 5})
        first = await replies.run("same", answer, 2)
        second = await replies.run("same", answer, 2)
        assert len(calls) == 1
        assert second[0] == first[0] and second[1].performance["cached_reply"]
        assert not first[1].performance.get("cached_reply")
        second[0]["feedback"] = "changed"
        assert (await replies.run("same", answer, 2))[0]["feedback"] == "Good."
    asyncio.run(go())


def test_failures_are_not_reused_and_keys_include_every_answer_setting():
    async def go():
        replies, calls = LocalReplies(), []
        async def answer(timeout):
            calls.append(True)
            return None, Result(ok=False)
        await replies.run("same", answer, 2)
        await replies.run("same", answer, 2)
        assert len(calls) == 2
    asyncio.run(go())
    base = {"model": "one", "prompt": "mark", "schema": {"required": ["x"]},
            "system": "brief", "speech": False, "think": False}
    assert len({reply_key(**base), *(reply_key(**{**base, k: v}) for k, v in
        [("model", "two"), ("prompt", "other"), ("schema", None), ("system", "different"),
         ("speech", True), ("think", True)])}) == 7


def test_duplicate_calls_share_work_and_reset_prevents_stale_reuse():
    async def go():
        replies, started, finish, calls = LocalReplies(), asyncio.Event(), asyncio.Event(), []
        async def answer(timeout):
            calls.append(True)
            started.set()
            await finish.wait()
            return {"x": 1}, Result()
        one = asyncio.create_task(replies.run("same", answer, 2))
        await started.wait()
        two = asyncio.create_task(replies.run("same", answer, 2))
        finish.set()
        await asyncio.gather(one, two)
        assert len(calls) == 1
        replies.clear()
        await replies.run("same", answer, 2)
        assert len(calls) == 2
    asyncio.run(go())


def test_expired_and_reset_during_request_results_are_not_reused():
    async def go():
        now, calls = [10.0], []
        replies = LocalReplies(clock=lambda: now[0])
        async def answer(timeout):
            calls.append(True)
            return {"x": 1}, Result()
        await replies.run("key", answer, 2)
        now[0] += 601
        await replies.run("key", answer, 2)
        assert len(calls) == 2
        async def reset(timeout):
            replies.clear()
            return await answer(timeout)
        await replies.run("new", reset, 2)
        await replies.run("new", answer, 2)
        assert len(calls) == 4
    asyncio.run(go())


def test_queue_wait_counts_towards_deadline_and_cancelled_work_is_not_cached():
    async def go():
        replies, started, finish = LocalReplies(), asyncio.Event(), asyncio.Event()
        async def answer(timeout):
            started.set()
            await finish.wait()
            return {"x": 1}, Result()
        task = asyncio.create_task(replies.run("one", answer, 2))
        await started.wait()
        try:
            await replies.run("two", answer, .01)
        except asyncio.TimeoutError:
            pass
        else:
            raise AssertionError("A queued request must honour its timeout.")
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass
        finish.set()
        data, result = await replies.run("one", answer, 2)
        assert data == {"x": 1} and not result.performance.get("cached_reply")
    asyncio.run(go())


def test_reset_cancels_old_queued_request_before_it_can_run_or_fill_new_cache():
    async def go():
        replies, started, finish, calls = LocalReplies(), asyncio.Event(), asyncio.Event(), []
        async def answer(timeout):
            calls.append(True)
            started.set()
            await finish.wait()
            return {'x': 1}, Result()
        first = asyncio.create_task(replies.run('old', answer, 2))
        await started.wait()
        queued = asyncio.create_task(replies.run('old', answer, 2))
        await asyncio.sleep(0)
        replies.clear()
        finish.set()
        await first
        try:
            await queued
        except asyncio.CancelledError:
            pass
        else:
            raise AssertionError('A request queued before reset must not execute after reset.')
        assert len(calls) == 1
        await replies.run('old', answer, 2)
        assert len(calls) == 2
    asyncio.run(go())
