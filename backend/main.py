from __future__ import annotations

import asyncio
import logging
from contextlib import asynccontextmanager, suppress

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware

from backend.api.routes import devices, historical, outlet, sensors
from backend.config import Settings
from backend.database import session, initialize
from backend.services.aggregation import aggregate_closed_windows

logger = logging.getLogger("aquasentinel.backend")


async def _aggregation_loop(settings: Settings) -> None:
    while True:
        try:
            with session(settings.resolved_database_path()) as conn:
                aggregate_closed_windows(conn, settings)
        except Exception:
            # Keep the API available and retry during the next cycle.
            logger.exception("Background aggregation cycle failed")
        await asyncio.sleep(settings.aggregation_poll_seconds)


def create_app(settings: Settings | None = None, *, start_aggregation_worker: bool = True) -> FastAPI:
    configured = settings or Settings.from_env()
    task: asyncio.Task | None = None

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        nonlocal task
        initialize(configured.resolved_database_path())
        with session(configured.resolved_database_path()) as conn:
            aggregate_closed_windows(conn, configured)
        if start_aggregation_worker:
            task = asyncio.create_task(_aggregation_loop(configured))
        yield
        if task:
            task.cancel()
            with suppress(asyncio.CancelledError):
                await task

    app = FastAPI(
        title="AquaSentinel Backend",
        description="Telemetry ingestion and dashboard API for AquaSentinel V1.",
        version="1.0.0",
        docs_url="/docs",
        redoc_url="/redoc",
        lifespan=lifespan,
    )
    app.state.settings = configured
    if configured.cors_origins:
        app.add_middleware(
            CORSMiddleware,
            allow_origins=list(configured.cors_origins),
            allow_credentials=False,
            allow_methods=["GET", "POST", "OPTIONS"],
            allow_headers=["Content-Type", "X-Device-Token"],
        )

    @app.middleware("http")
    async def enforce_ingestion_content_length(request: Request, call_next):
        if request.url.path == "/api/v1/sensors/outlet":
            content_type = request.headers.get("content-type", "").split(";", 1)[0].strip().lower()
            if content_type != "application/json":
                return JSONResponse(status_code=415, content={"detail": "Content-Type must be application/json"})
            raw_length = request.headers.get("content-length")
            if raw_length:
                try:
                    if int(raw_length) > 8192:
                        return JSONResponse(status_code=413, content={"detail": "Telemetry payload exceeds 8192 bytes"})
                except ValueError:
                    return JSONResponse(status_code=400, content={"detail": "Invalid Content-Length header"})
        return await call_next(request)

    @app.get("/api/v1/health", tags=["health"])
    def health():
        return {"status": "ok", "service": "aquasentinel-backend", "api_version": "v1"}

    app.include_router(sensors.router, prefix="/api/v1")
    app.include_router(outlet.router, prefix="/api/v1")
    app.include_router(devices.router, prefix="/api/v1")
    app.include_router(historical.router, prefix="/api/v1")
    return app


app = create_app()
