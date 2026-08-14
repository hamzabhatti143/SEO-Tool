"""ARQ worker definition.

Run with:  arq app.worker.WorkerSettings

This single worker (scale to a few replicas as needed) processes all
enqueued heavy tasks AND owns the cron schedule — so scheduled jobs fire
exactly once no matter how many *web* replicas run. Contrast with the old
in-process APScheduler, which fired once per web process.
"""

from __future__ import annotations

from arq import cron

from app.core.config import settings
from app.core.eventloop import use_selector_event_loop_on_windows
from app.core.queue import redis_settings

# psycopg3 async needs a SelectorEventLoop on Windows (ARQ creates the loop).
use_selector_event_loop_on_windows()
from app.tasks import (
    cron_automation_daily,
    cron_automation_weekly,
    task_analyze_competitor,
    task_analyze_gaps,
    task_crawl_internal_links,
    task_find_broken_links,
    task_research_keywords,
    task_run_audit,
)


class WorkerSettings:
    redis_settings = redis_settings()
    keep_result = settings.QUEUE_KEEP_RESULT
    max_jobs = 10
    # A cron whose scheduled time is deferred into the past (e.g. the machine
    # slept past a daily/weekly run) makes arq compute
    # ``expires_ms = defer_score - now + expires_extra_ms``. With the 24h
    # default this goes negative for gaps > ~24h, and Redis rejects the
    # PSETEX ("invalid expire time"), crashing the worker. A 30-day buffer
    # keeps the TTL positive across any realistic downtime.
    expires_extra_ms = 30 * 24 * 60 * 60 * 1000

    functions = [
        task_run_audit,
        task_crawl_internal_links,
        task_analyze_competitor,
        task_analyze_gaps,
        task_find_broken_links,
        task_research_keywords,
    ]

    cron_jobs = [
        cron(
            cron_automation_daily,
            hour=settings.AUTOMATION_DAILY_HOUR,
            minute=0,
        ),
        cron(
            cron_automation_weekly,
            weekday=settings.AUTOMATION_WEEKLY_DAY,
            hour=settings.AUTOMATION_WEEKLY_HOUR,
            minute=0,
        ),
    ]
