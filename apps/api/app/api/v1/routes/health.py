"""Health / readiness routes."""

from fastapi import APIRouter

router = APIRouter()


@router.get("/ping")
async def ping() -> dict[str, str]:
    """Simple readiness check for the v1 API."""
    return {"status": "ok", "service": "rankpilot-api"}
