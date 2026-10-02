import asyncio

from .runtime import AriaRuntime
from .storage import store


async def main():
    runtime = AriaRuntime(store)
    while True:
        job = store.claim_job()
        if not job:
            await asyncio.sleep(2)
            continue
        try:
            payload = job.get("payload") or {}
            goal = payload.get("goal") or payload.get("message") or str(payload)
            result = await runtime.run(job["user_id"], goal)
            store.complete_job(job["id"], result=result)
        except Exception as exc:
            store.complete_job(job["id"], error=str(exc))


if __name__ == "__main__":
    asyncio.run(main)
