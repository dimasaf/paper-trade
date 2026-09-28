"""ARQ worker configuration and readiness heartbeat."""

from time import time
from typing import Any, cast

from arq import cron
from arq.connections import RedisSettings
from arq.typing import WorkerCoroutine

from paper_trade.config import Settings
from paper_trade.observability import configure_logging

settings = Settings()


async def heartbeat(context: dict[Any, Any], *args: Any, **kwargs: Any) -> None:
    ttl_seconds = max(20, int(settings.worker_heartbeat_max_age_seconds * 2))
    await context["redis"].set(
        settings.worker_heartbeat_key,
        str(time()),
        ex=ttl_seconds,
    )


async def startup(context: dict[Any, Any]) -> None:
    configure_logging(settings.log_level)
    await heartbeat(context)


class WorkerSettings:
    redis_settings = RedisSettings.from_dsn(settings.redis_url)
    on_startup = startup
    cron_jobs = [
        cron(
            cast(WorkerCoroutine, heartbeat),
            second=set(range(0, 60, 5)),
            run_at_startup=True,
            unique=False,
        )
    ]
    health_check_interval = 5
