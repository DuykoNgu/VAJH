import os

import pytest
from arq import func
from arq.connections import RedisSettings
from arq.jobs import Job, JobStatus
from arq.worker import Worker

from app import jobs, worker

SETTINGS = RedisSettings.from_dsn(os.environ["REDIS_URL"])


@pytest.fixture
async def queue():
    jobs.configure_queue(os.environ["REDIS_URL"])
    pool = await jobs.queue()
    await pool.flushdb()
    yield pool
    await pool.flushdb()
    await jobs.close_queue()


def burst_worker(functions):
    return Worker(functions=functions, redis_settings=SETTINGS, burst=True, poll_delay=0.05,
                  max_tries=worker.MAX_TRIES, handle_signals=False)


async def test_enqueued_job_runs_in_worker(queue):
    job_id = await jobs.enqueue("ping", "xin chào")
    w = burst_worker(worker.WorkerSettings.functions)
    await w.main()
    await w.close()

    assert await Job(job_id, queue).result(timeout=5) == "xin chào"


async def test_failed_job_is_retried_then_succeeds(queue, monkeypatch):
    monkeypatch.setattr(worker, "RETRY_BASE_S", 0.05)
    tries = []

    @worker.retrying
    async def flaky(ctx):
        tries.append(ctx["job_try"])
        if len(tries) == 1:
            raise ConnectionError("first attempt fails")
        return "ok"

    job = await queue.enqueue_job("flaky")
    w = burst_worker([func(flaky, name="flaky")])
    await w.main()
    await w.close()
    assert await job.result(timeout=5) == "ok"
    assert tries == [1, 2]
    assert await job.status() == JobStatus.complete
