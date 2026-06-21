"""
ProposalPilot AI — FastAPI Application Entry Point
Handles app factory, middleware, lifespan, and exception handler registration.
"""
import uuid
import asyncio
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, status
from fastapi.encoders import jsonable_encoder
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from loguru import logger
from pydantic import ValidationError as PydanticValidationError

from app.config import get_settings
from app.database import check_db_connection, engine
from app.exceptions import ProposalPilotError
from app.logging_config import configure_logging

settings = get_settings()


def _local_dev_cors_origin_regex() -> str | None:
    # Allow localhost / 127.0.0.1 and any Netlify subdomains (including preview deploys)
    return r"^(https?://(localhost|127\.0\.0\.1|\[::1\])(:\d+)?|https://.*\.netlify\.app)$"


# ── Lifespan ──────────────────────────────────────────────────────────────
@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup and shutdown lifecycle management."""
    configure_logging()
    logger.info(f"Starting {settings.APP_NAME} in {settings.APP_ENV} mode")

    # Verify DB is reachable
    db_ok = await check_db_connection()
    if not db_ok:
        logger.error("Database connection FAILED on startup — check DATABASE_URL")
    else:
        logger.info("Database connection verified [OK]")

    # Initialize Qdrant collections (imported here to avoid circular deps)
    from app.services.vector_service import initialize_qdrant_collections
    try:
        await asyncio.wait_for(initialize_qdrant_collections(), timeout=8)
        logger.info("Qdrant collections initialized [OK]")
    except Exception as exc:
        logger.warning(f"Qdrant initialization skipped during startup: {exc}")

    # Ensure upload directory exists
    import os
    os.makedirs(settings.UPLOAD_DIR, exist_ok=True)
    logger.info(f"Upload directory ready: {settings.UPLOAD_DIR} [OK]")

    yield

    # Cleanup
    logger.info("Shutting down application...")
    await engine.dispose()
    logger.info("Database engine disposed [OK]")


# ── App Factory ───────────────────────────────────────────────────────────
def create_app() -> FastAPI:
    app = FastAPI(
        title=settings.APP_NAME,
        description="Internal RFP Intelligence Platform powered by Multi-Agent AI",
        version="1.0.0",
        docs_url="/api/docs" if not settings.is_production else None,
        redoc_url="/api/redoc" if not settings.is_production else None,
        openapi_url="/api/openapi.json" if not settings.is_production else None,
        lifespan=lifespan,
    )

    _register_middleware(app)
    _register_exception_handlers(app)
    _register_routers(app)

    from fastapi import WebSocket, WebSocketDisconnect
    from app.ws_registry import subscribe, unsubscribe

    @app.websocket("/ws/war-room/{session_id}")
    async def war_room_ws(websocket: WebSocket, session_id: str):
        await websocket.accept()
        await subscribe(session_id, websocket)
        try:
            while True:
                await websocket.receive_text()
        except WebSocketDisconnect:
            unsubscribe(session_id, websocket)

    return app


# ── Middleware ─────────────────────────────────────────────────────────────
def _register_middleware(app: FastAPI) -> None:
    # CORS
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.APP_CORS_ORIGINS,
        allow_origin_regex=_local_dev_cors_origin_regex(),
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Request ID + structured logging
    @app.middleware("http")
    async def request_id_middleware(request: Request, call_next):
        request_id = request.headers.get("X-Request-ID", str(uuid.uuid4()))
        request.state.request_id = request_id

        with logger.contextualize(
            request_id=request_id,
            method=request.method,
            path=request.url.path,
        ):
            logger.debug(f"--> {request.method} {request.url.path}")
            response = await call_next(request)
            response.headers["X-Request-ID"] = request_id
            response.headers["X-Content-Type-Options"] = "nosniff"
            response.headers["X-Frame-Options"] = "DENY"
            response.headers["Referrer-Policy"] = "no-referrer"
            response.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=()"
            if request.url.path.startswith("/api/"):
                response.headers["Cache-Control"] = "no-store"
                response.headers["Pragma"] = "no-cache"
            logger.debug(f"<-- {response.status_code}")

        return response


# ── Exception Handlers ────────────────────────────────────────────────────
def _register_exception_handlers(app: FastAPI) -> None:

    @app.exception_handler(ProposalPilotError)
    async def app_error_handler(request: Request, exc: ProposalPilotError):
        logger.warning(
            f"Application error [{exc.error_code}]: {exc.message}",
            detail=exc.detail,
        )
        return JSONResponse(
            status_code=exc.status_code,
            content={
                "error": exc.error_code,
                "message": exc.message,
                "detail": exc.detail,
                "request_id": getattr(request.state, "request_id", None),
            },
        )

    @app.exception_handler(PydanticValidationError)
    async def pydantic_error_handler(request: Request, exc: PydanticValidationError):
        return JSONResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            content={
                "error": "VALIDATION_ERROR",
                "message": "Request body validation failed.",
                "detail": jsonable_encoder(exc.errors()),
                "request_id": getattr(request.state, "request_id", None),
            },
        )

    @app.exception_handler(Exception)
    async def generic_error_handler(request: Request, exc: Exception):
        logger.exception(f"Unhandled exception on {request.url.path}")
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={
                "error": "INTERNAL_ERROR",
                "message": "An unexpected error occurred. Our team has been notified.",
                "request_id": getattr(request.state, "request_id", None),
            },
        )


# ── Routers ────────────────────────────────────────────────────────────────
def _register_routers(app: FastAPI) -> None:
    from app.api.v1 import health, rfp, knowledge, sessions, war_room, proposals

    prefix = "/api/v1"
    app.include_router(health.router, prefix=prefix, tags=["Health"])
    app.include_router(rfp.router, prefix=prefix, tags=["RFP"])
    app.include_router(knowledge.router, prefix=prefix, tags=["Knowledge Base"])
    app.include_router(sessions.router, prefix=prefix, tags=["Sessions"])
    app.include_router(war_room.router, prefix=prefix, tags=["War Room"])
    app.include_router(proposals.router, prefix=prefix, tags=["Proposals"])


# ── Entry Point ────────────────────────────────────────────────────────────
app = create_app()
