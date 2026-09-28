import asyncio
import logging
from datetime import datetime, timezone

from fastapi.testclient import TestClient

from paper_trade.health import ComponentHealth, HealthReport, RuntimeHealthService
from paper_trade.main import create_app


class ReadyHealthService:
    async def check(self) -> HealthReport:
        return HealthReport(
            checked_at=datetime(2026, 9, 28, 8, 0, tzinfo=timezone.utc),
            components={
                "application": ComponentHealth(status="ready", message="API is serving requests"),
                "database": ComponentHealth(status="ready", message="PostgreSQL accepted a query"),
                "redis": ComponentHealth(status="ready", message="Redis responded to ping"),
                "worker": ComponentHealth(status="ready", message="ARQ heartbeat is current"),
            },
        )


def test_health_reports_each_ready_dependency_with_correlation_context() -> None:
    client = TestClient(create_app(health_service=ReadyHealthService()))

    response = client.get("/health", headers={"X-Correlation-ID": "trace-123"})

    assert response.status_code == 200
    assert response.headers["X-Correlation-ID"] == "trace-123"
    assert response.json() == {
        "status": "ready",
        "checked_at": "2026-09-28T08:00:00Z",
        "correlation_id": "trace-123",
        "components": {
            "application": {"status": "ready", "message": "API is serving requests"},
            "database": {"status": "ready", "message": "PostgreSQL accepted a query"},
            "redis": {"status": "ready", "message": "Redis responded to ping"},
            "worker": {"status": "ready", "message": "ARQ heartbeat is current"},
        },
    }


class ReadyProbe:
    async def check(self) -> str:
        return "dependency accepted a probe"


class SecretFailureProbe:
    async def check(self) -> str:
        raise RuntimeError("postgresql://admin:super-secret@database/paper_trade")


class NeverReturningProbe:
    async def check(self) -> str:
        await asyncio.Future()
        raise AssertionError("unreachable")


def test_health_degrades_failed_dependency_without_leaking_the_failure() -> None:
    health_service = RuntimeHealthService(
        database=SecretFailureProbe(),
        redis=ReadyProbe(),
        worker=ReadyProbe(),
        now=lambda: datetime(2026, 9, 28, 8, 30, tzinfo=timezone.utc),
    )
    client = TestClient(create_app(health_service=health_service))

    response = client.get("/health")

    assert response.status_code == 200
    document = response.json()
    assert document["status"] == "degraded"
    assert document["components"] == {
        "application": {"status": "ready", "message": "API is serving requests"},
        "database": {"status": "unavailable", "message": "Database probe failed"},
        "redis": {"status": "ready", "message": "dependency accepted a probe"},
        "worker": {"status": "ready", "message": "dependency accepted a probe"},
    }
    assert "super-secret" not in response.text


def test_health_bounds_a_nonresponsive_dependency() -> None:
    health_service = RuntimeHealthService(
        database=NeverReturningProbe(),
        redis=ReadyProbe(),
        worker=ReadyProbe(),
        probe_timeout_seconds=0.01,
        now=lambda: datetime(2026, 9, 28, 8, 45, tzinfo=timezone.utc),
    )
    client = TestClient(create_app(health_service=health_service))

    response = client.get("/health")

    assert response.status_code == 200
    assert response.json()["status"] == "degraded"
    assert response.json()["components"]["database"] == {
        "status": "unavailable",
        "message": "Database probe failed",
    }


def test_request_log_includes_correlation_id_without_authorization_secret(caplog: object) -> None:
    client = TestClient(create_app(health_service=ReadyHealthService()))

    with caplog.at_level(logging.INFO, logger="paper_trade.http"):
        client.get(
            "/health",
            headers={
                "X-Correlation-ID": "trace-log-456",
                "Authorization": "Bearer never-log-this",
            },
        )

    request_records = [record for record in caplog.records if record.name == "paper_trade.http"]
    assert len(request_records) == 1
    assert request_records[0].correlation_id == "trace-log-456"
    assert request_records[0].path == "/health"
    assert "never-log-this" not in caplog.text
