"""Dev/prod launcher for the FastAPI app.

Why this exists: on Windows, psycopg3's async mode requires a
SelectorEventLoop. uvicorn (esp. newer versions) sets up its own event loop
on Windows and may pick the ProactorEventLoop, ignoring the global policy —
so we explicitly create a SelectorEventLoop and run uvicorn's server inside
it. On non-Windows this is a normal `uvicorn.run`.

Run it with:  python run.py
Env overrides: HOST, PORT, RELOAD (RELOAD only applies off Windows; the
Windows selector-loop path runs a single process without the reloader).
"""

from __future__ import annotations

import asyncio
import os
import sys

import uvicorn


def main() -> None:
    host = os.getenv("HOST", "127.0.0.1")
    port = int(os.getenv("PORT", "8000"))
    reload = os.getenv("RELOAD", "false").lower() == "true"

    if sys.platform == "win32":
        # Force a SelectorEventLoop (psycopg3 async is incompatible with the
        # ProactorEventLoop). Run uvicorn's server inside it directly so
        # uvicorn's own loop setup can't override us.
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
        config = uvicorn.Config(f"app.main:app", host=host, port=port)
        server = uvicorn.Server(config)
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            loop.run_until_complete(server.serve())
        finally:
            loop.close()
    else:
        uvicorn.run("app.main:app", host=host, port=port, reload=reload)


if __name__ == "__main__":
    main()
