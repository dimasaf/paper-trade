"""Health reporting at the public HTTP seam."""

from datetime import datetime, timezone
from typing import Callable, Literal, Protocol

from pydantic import BaseModel


class ComponentHealth(BaseModel):
    """Readiness of one externally meaningful application component."""

    status: Literal["ready", "unavailable"]
    message: str


class HealthReport(BaseModel):
    """Point-in-time readiness reported by the health module."""

    checked_at: datetime
    components: dict[str, ComponentHealth]

    @property
    def status(self) -> Literal["ready", "degraded"]:
        if all(component.status == "ready" for component in self.components.values()):
            return "ready"
        return "degraded"


class HealthService(Protocol):
    """Interface consumed by the HTTP health endpoint."""

    async def check(self) -> HealthReport:
        """Return current dependency readiness."""


class DependencyProbe(Protocol):
    """Small Adapter interface for one runtime dependency."""

    async def check(self) -> str:
        """Return a safe human-readable readiness message or raise on failure."""


class RuntimeHealthService:
    """Combines dependency probes into one stable health report."""

    def __init__(
        self,
        *,
        database: DependencyProbe,
        redis: DependencyProbe,
        worker: DependencyProbe,
        now: Callable[[], datetime] = lambda: datetime.now(timezone.utc),
    ) -> None:
        self._database = database
        self._redis = redis
        self._worker = worker
        self._now = now

    async def check(self) -> HealthReport:
        components = {
            "application": ComponentHealth(status="ready", message="API is serving requests"),
            "database": await self._check_dependency(label="Database", probe=self._database),
            "redis": await self._check_dependency(label="Redis", probe=self._redis),
            "worker": await self._check_dependency(label="Worker", probe=self._worker),
        }
        return HealthReport(checked_at=self._now(), components=components)

    @staticmethod
    async def _check_dependency(*, label: str, probe: DependencyProbe) -> ComponentHealth:
        try:
            message = await probe.check()
        except Exception:
            return ComponentHealth(status="unavailable", message=f"{label} probe failed")
        return ComponentHealth(status="ready", message=message)


class StartupHealthService:
    """Safe report used until runtime dependency probes are configured."""

    async def check(self) -> HealthReport:
        return HealthReport(
            checked_at=datetime.now(timezone.utc),
            components={
                "application": ComponentHealth(status="ready", message="API is serving requests"),
                "database": ComponentHealth(
                    status="unavailable", message="Database probe is not configured"
                ),
                "redis": ComponentHealth(
                    status="unavailable", message="Redis probe is not configured"
                ),
                "worker": ComponentHealth(
                    status="unavailable", message="Worker probe is not configured"
                ),
            },
        )
