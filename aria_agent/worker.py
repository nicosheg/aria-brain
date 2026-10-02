from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timedelta, timezone

from .config import settings
from .runtime import AriaRuntime
from .storage import store

logger = logging.getLogger("aria.worker")


async def worker_loop(runtime: AriaRuntime, worker_index: int) -> None:
    while True:
        try:
            job = await asyncio.to_thread(store.claim_job)
        except Exception:
            logger.exception("Worker %s could not claim a job", worker_index)
            await asyncio.sleep(3)
            continue

        if not job:
            await asyncio.sleep(1.5)
            continue

        job_id = job["id"]
        try:
            payload = job.get("payload") or {}
            goal = payload.get("goal") or payload.get("message") or str(payload)
            result = await runtime.run(job["user_id"], goal)
            await asyncio.to_thread(store.complete_job, job_id, result)

            repeat_seconds = int(payload.get("repeat_seconds") or 0)
            if repeat_seconds > 0:
                next_payload = dict(payload)
                next_id = await asyncio.to_thread(
                    store.enqueue_job,
                    job["user_id"],
                    job["kind"],
                    next_payload,
                    (datetime.now(timezone.utc) + timedelta(seconds=repeat_seconds)).isoformat(),
                )
                logger.info("Scheduled recurring job %s from %s", next_id, job_id)
        except Exception as exc:
            logger.exception("Job %s failed", job_id)
            retried = await asyncio.to_thread(
                store.retry_job,
                job_id,
                int(job.get("attempts") or 1),
                str(exc),
            )
            if not retried:
                logger.error("Job %s permanently failed after %s attempts", job_id, job.get("attempts"))


async def main():
    if settings.require_database and not settings.database_url:
        raise RuntimeError("ARIA_REQUIRE_DATABASE is enabled but SUPABASE_DB_URL/DATABASE_URL is not configured.")

    runtimes = [AriaRuntime(store) for _ in range(settings.worker_concurrency)]
    try:
        await asyncio.gather(
            *(worker_loop(runtime, index + 1) for index, runtime in enumerate(runtimes))
        )
    finally:
        await asyncio.gather(*(runtime.close() for runtime in runtimes), return_exceptions=True)


if __name__ == "__main__":
    asyncio.run(main())
