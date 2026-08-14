"""Background job status polling.

Clients enqueue heavy work and poll here for status + result. Works with
either backend: ARQ (Redis) job ids, or in-process fallback ids (prefixed
`local-`) held in memory when Redis isn't configured.
"""

from __future__ import annotations

from arq.jobs import Job, JobStatus
from fastapi import APIRouter, Depends, HTTPException, Request

from app.api.deps import get_current_user
from app.core.queue import get_arq_optional, local_job
from app.models.user import User
from app.schemas.jobs import JobStatusResponse

router = APIRouter()

_STATUS_MAP = {
    JobStatus.deferred: "queued",
    JobStatus.queued: "queued",
    JobStatus.in_progress: "running",
}


@router.get("/{job_id}", response_model=JobStatusResponse)
async def get_job(
    job_id: str,
    request: Request,
    _current_user: User = Depends(get_current_user),
) -> JobStatusResponse:
    """Return a job's status and (once finished) its result."""
    # In-process fallback jobs (no Redis).
    local = local_job(job_id)
    if local is not None:
        return JobStatusResponse(
            job_id=job_id,
            status=local["status"],
            result=local["result"],
            error=local["error"],
        )

    pool = get_arq_optional(request)
    if pool is None:
        raise HTTPException(status_code=404, detail="Job not found")

    job = Job(job_id, pool)
    job_status = await job.status()
    if job_status == JobStatus.not_found:
        raise HTTPException(status_code=404, detail="Job not found")

    if job_status != JobStatus.complete:
        return JobStatusResponse(
            job_id=job_id, status=_STATUS_MAP.get(job_status, "running")
        )

    info = await job.result_info()
    if info is not None and info.success:
        return JobStatusResponse(
            job_id=job_id, status="complete", result=info.result
        )
    error = str(info.result) if info is not None else "Job failed"
    return JobStatusResponse(job_id=job_id, status="failed", error=error)
