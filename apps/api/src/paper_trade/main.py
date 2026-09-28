"""FastAPI application factory."""

import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from time import perf_counter
from typing import Optional
from uuid import uuid4

from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import create_async_engine
from starlette.middleware.base import RequestResponseEndpoint

from paper_trade.config import Settings
from paper_trade.health import (
    ComponentHealth,
    HealthService,
    RuntimeHealthService,
    StartupHealthService,
)
from paper_trade.observability import configure_logging
from paper_trade.probes import DatabaseProbe, RedisProbe, WorkerProbe

http_logger = logging.getLogger("paper_trade.http")


class HealthResponse(BaseModel):
    status: str
    checked_at: str
    correlation_id: str
    components: dict[str, ComponentHealth]


def create_app(
    health_service: Optional[HealthService] = None,
    settings: Optional[Settings] = None,
) -> FastAPI:
    runtime_settings = settings or Settings()

    @asynccontextmanager
    async def lifespan(application: FastAPI) -> AsyncIterator[None]:
        if health_service is not None:
            application.state.health_service = health_service
            yield
            return

        configure_logging(runtime_settings.log_level)
        engine = create_async_engine(runtime_settings.database_url, pool_pre_ping=True)
        redis = Redis.from_url(runtime_settings.redis_url, decode_responses=True)
        application.state.health_service = RuntimeHealthService(
            database=DatabaseProbe(engine),
            redis=RedisProbe(redis),
            worker=WorkerProbe(
                redis,
                heartbeat_key=runtime_settings.worker_heartbeat_key,
                maximum_age_seconds=runtime_settings.worker_heartbeat_max_age_seconds,
            ),
        )
        try:
            yield
        finally:
            await redis.aclose()
            await engine.dispose()

    app = FastAPI(title="Paper Trade API", version="0.1.0", lifespan=lifespan)
    app.state.health_service = health_service or StartupHealthService()
    app.add_middleware(
        CORSMiddleware,
        allow_origins=list(
            {
                runtime_settings.web_origin,
                "http://127.0.0.1:3000",
                "http://localhost:3000",
            }
        ),
        allow_credentials=False,
        allow_methods=["GET"],
        allow_headers=["Content-Type", "X-Correlation-ID"],
    )

    @app.middleware("http")
    async def correlation_context(request: Request, call_next: RequestResponseEndpoint) -> Response:
        correlation_id = request.headers.get("X-Correlation-ID") or str(uuid4())
        request.state.correlation_id = correlation_id
        started_at = perf_counter()
        response = await call_next(request)
        response.headers["X-Correlation-ID"] = correlation_id
        http_logger.info(
            "request.completed",
            extra={
                "correlation_id": correlation_id,
                "method": request.method,
                "path": request.url.path,
                "status_code": response.status_code,
                "duration_ms": round((perf_counter() - started_at) * 1000, 2),
            },
        )
        return response

    @app.get("/live")
    async def live() -> dict[str, str]:
        return {"status": "ready"}

    @app.get("/health", response_model=HealthResponse)
    async def health(request: Request) -> HealthResponse:
        report = await app.state.health_service.check()
        return HealthResponse(
            status=report.status,
            checked_at=report.checked_at.isoformat().replace("+00:00", "Z"),
            correlation_id=request.state.correlation_id,
            components=report.components,
        )

    return app


app = create_app()
