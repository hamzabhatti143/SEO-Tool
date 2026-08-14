"""Job dispatch: ARQ (Redis) when available, in-process fallback otherwise.

Preferred: the web process holds an ArqRedis pool and enqueues jobs to a
separate ARQ worker (app.worker) — cron runs only in the worker, so it fires
once regardless of web-replica count, and heavy work is off the request path.

Fallback (no Redis / no Docker): jobs run as asyncio background tasks in the
web process with an in-memory result store, so the queued features still work
out of the box in local dev. This fallback is single-process only (results
live in memory) — use real Redis (e.g. Upstash) for multi-worker/production.
"""

from __future__ import annotations

import asyncio
import uuid
from collections.abc import Awaitable, Callable
from typing import Any

from fastapi import Request

try:  # arq is optional at import time
    from arq import create_pool
    from arq.connections import ArqRedis, RedisSettings
except Exception:  # noqa: BLE001
    create_pool = None  # type: ignore[assignment]
    ArqRedis = object  # type: ignore[assignment,misc]
    RedisSettings = object  # type: ignore[assignment,misc]

from app.core.config import settings

# In-memory job store for the no-Redis fallback: job_id -> {status,result,error}
_LOCAL_JOBS: dict[str, dict[str, Any]] = {}


def redis_settings() -> "RedisSettings":
    return RedisSettings.from_dsn(settings.REDIS_URL)


async def create_arq_pool() -> "ArqRedis":
    if create_pool is None:  # pragma: no cover
        raise RuntimeError("arq is not installed")
    return await create_pool(redis_settings())


def get_arq_optional(request: Request) -> "ArqRedis | None":
    """Return the ArqRedis pool if connected, else None (no error)."""
    return getattr(request.app.state, "arq", None)


def _run_local(func: Callable[..., Awaitable[Any]], args: tuple) -> str:
    """Run a task in-process as a background asyncio task; return a job id."""
    job_id = f"local-{uuid.uuid4().hex}"
    _LOCAL_JOBS[job_id] = {"status": "running", "result": None, "error": None}

    async def _runner() -> None:
        try:
            # Tasks take an ARQ-style ctx as the first arg; pass an empty dict.
            result = await func({}, *args)
            _LOCAL_JOBS[job_id] = {
                "status": "complete",
                "result": result,
                "error": None,
            }
        except Exception as exc:  # noqa: BLE001
            _LOCAL_JOBS[job_id] = {
                "status": "failed",
                "result": None,
                "error": str(exc),
            }

    asyncio.create_task(_runner())
    return job_id


async def dispatch(
    pool: "ArqRedis | None",
    task_name: str,
    func: Callable[..., Awaitable[Any]],
    *args: Any,
) -> str:
    """Enqueue to ARQ if a pool is available, else run in-process."""
    if pool is not None:
        job = await pool.enqueue_job(task_name, *args)
        return job.job_id
    return _run_local(func, args)


def local_job(job_id: str) -> dict[str, Any] | None:
    """Return an in-memory job's state, or None if it isn't a local job."""
    return _LOCAL_JOBS.get(job_id)
