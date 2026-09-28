"""Structured logging with an explicit safe field allowlist."""

import json
import logging
from datetime import datetime, timezone
from typing import Any

SAFE_CONTEXT_FIELDS = (
    "correlation_id",
    "method",
    "path",
    "status_code",
    "duration_ms",
    "component",
    "exception_type",
)


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        document: dict[str, Any] = {
            "timestamp": datetime.fromtimestamp(record.created, tz=timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        for field in SAFE_CONTEXT_FIELDS:
            if hasattr(record, field):
                document[field] = getattr(record, field)
        return json.dumps(document, separators=(",", ":"), sort_keys=True)


def configure_logging(level: str) -> None:
    handler = logging.StreamHandler()
    handler.setFormatter(JsonFormatter())
    logging.basicConfig(level=level.upper(), handlers=[handler], force=True)
