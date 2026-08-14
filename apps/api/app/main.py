"""FastAPI application entry point for RankPilot AI."""

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.v1.router import api_router
from app.core.config import settings
from app.core.eventloop import use_selector_event_loop_on_windows
from app.core.queue import create_arq_pool

# psycopg3 async needs a SelectorEventLoop on Windows. Set the policy at
# import time, before uvicorn creates the event loop.
use_selector_event_loop_on_windows()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup/shutdown hooks.

    Schema is managed by Alembic (``alembic upgrade head``). Scheduled cron
    and heavy tasks run in the ARQ worker (``arq app.worker.WorkerSettings``),
    NOT in the web process — the web process only holds an ArqRedis pool to
    enqueue jobs. If Redis is unavailable, enqueue endpoints return 503 but
    the rest of the API keeps working.
    """
    try:
        app.state.arq = await create_arq_pool()
    except Exception:  # noqa: BLE001 - degrade: enqueue endpoints will 503
        app.state.arq = None
    try:
        yield
    finally:
        pool = getattr(app.state, "arq", None)
        if pool is not None:
            await pool.close()


app = FastAPI(
    title="RankPilot AI API",
    version="0.1.0",
    description="AI-powered SEO audits, keyword research, and content generation.",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(api_router, prefix=settings.API_V1_PREFIX)


@app.get("/health", tags=["meta"])
async def health() -> dict[str, str]:
    """Liveness probe."""
    return {"status": "ok"}
