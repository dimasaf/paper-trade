"""Runtime dependency Adapters used by the health module."""

from time import time
from typing import Callable

from redis.asyncio import Redis
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine


class DatabaseProbe:
    def __init__(self, engine: AsyncEngine) -> None:
        self._engine = engine

    async def check(self) -> str:
        async with self._engine.connect() as connection:
            await connection.execute(text("SELECT 1"))
        return "PostgreSQL accepted a query"


class RedisProbe:
    def __init__(self, redis: Redis) -> None:
        self._redis = redis

    async def check(self) -> str:
        if not await self._redis.ping():
            raise RuntimeError("Redis ping returned false")
        return "Redis responded to ping"


class WorkerProbe:
    def __init__(
        self,
        redis: Redis,
        *,
        heartbeat_key: str,
        maximum_age_seconds: float,
        now: Callable[[], float] = time,
    ) -> None:
        self._redis = redis
        self._heartbeat_key = heartbeat_key
        self._maximum_age_seconds = maximum_age_seconds
        self._now = now

    async def check(self) -> str:
        heartbeat = await self._redis.get(self._heartbeat_key)
        if heartbeat is None:
            raise RuntimeError("ARQ worker heartbeat is missing")
        age = max(0.0, self._now() - float(heartbeat))
        if age > self._maximum_age_seconds:
            raise RuntimeError("ARQ worker heartbeat is stale")
        return "ARQ heartbeat is current"
