"""
ProposalPilot AI — Health Check Router
Provides system health status for monitoring and readiness probes.
"""
from fastapi import APIRouter, status
from pydantic import BaseModel

from app.database import check_db_connection
from app.services.vector_service import check_qdrant_health

router = APIRouter()


class HealthComponent(BaseModel):
    status: str  # ok | degraded | down
    message: str | None = None


class HealthResponse(BaseModel):
    status: str  # healthy | degraded | unhealthy
    version: str
    components: dict[str, HealthComponent]


@router.get(
    "/health",
    response_model=HealthResponse,
    summary="System health check",
    description="Returns health status of all system components.",
)
async def health_check() -> HealthResponse:
    components: dict[str, HealthComponent] = {}

    # Database
    db_ok = await check_db_connection()
    components["database"] = HealthComponent(
        status="ok" if db_ok else "down",
        message=None if db_ok else "Cannot reach PostgreSQL",
    )

    # Vector DB
    qdrant_ok = await check_qdrant_health()
    components["vector_database"] = HealthComponent(
        status="ok" if qdrant_ok else "down",
        message=None if qdrant_ok else "Cannot reach Qdrant",
    )

    all_ok = all(c.status == "ok" for c in components.values())
    any_down = any(c.status == "down" for c in components.values())

    overall = "healthy" if all_ok else ("unhealthy" if any_down else "degraded")

    return HealthResponse(
        status=overall,
        version="1.0.0",
        components=components,
    )


@router.get("/ping", summary="Basic liveness probe")
async def ping() -> dict[str, str]:
    return {"status": "pong"}
