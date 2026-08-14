"""Windows asyncio event-loop compatibility for psycopg3 (async).

On Windows, asyncio defaults to the ProactorEventLoop, but psycopg3's async
mode requires a SelectorEventLoop. Call ``use_selector_event_loop_on_windows``
at the top of every async entry point (web app, ARQ worker, Alembic env)
BEFORE any event loop is created. No-op on non-Windows platforms (Linux prod
already uses a selector/epoll loop that psycopg3 supports).
"""

from __future__ import annotations

import asyncio
import sys


def use_selector_event_loop_on_windows() -> None:
    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
