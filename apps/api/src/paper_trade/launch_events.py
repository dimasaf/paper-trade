"""Source-neutral launch events and the provider contract seam.

Every launch Adapter (pump.fun/PumpSwap, Raydium LaunchLab, Meteora DBC, Jupiter
Studio) normalizes documented program activity into a `LaunchEvent` and satisfies
`LaunchEventSource`. Token registration, classification, lifecycle, and coverage
behaviour therefore stays shared rather than provider specific.
"""

from collections.abc import Sequence
from datetime import datetime
from typing import Literal, Optional, Protocol

from pydantic import BaseModel, ConfigDict, Field, model_validator

from paper_trade.research_configuration import LaunchSource

UNKNOWN = "UNKNOWN"

Commitment = Literal["confirmed", "processed"]

LifecycleState = Literal["NEW", "ACTIVE", "MIGRATED", "ILLIQUID", "DEAD", "SUSPICIOUS"]

LIFECYCLE_STATES: tuple[LifecycleState, ...] = (
    "NEW",
    "ACTIVE",
    "MIGRATED",
    "ILLIQUID",
    "DEAD",
    "SUSPICIOUS",
)


class LaunchEventModel(BaseModel):
    """Base for recorded provider documents; unexpected fields are rejected."""

    model_config = ConfigDict(extra="forbid")


class ProviderCoverage(LaunchEventModel):
    """Coverage metadata retained with every recorded provider observation."""

    provider: str = Field(min_length=1)
    as_of_start: datetime
    as_of_end: datetime
    complete: bool
    commitment: Commitment
    unknown_fields: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_interval(self) -> "ProviderCoverage":
        if self.as_of_end < self.as_of_start:
            raise ValueError("as_of_end must not be earlier than as_of_start")
        return self


class LaunchEvent(LaunchEventModel):
    """A source-neutral recorded launch fact as returned by any Adapter."""

    event_id: str = Field(min_length=1)
    address: str = Field(min_length=1)
    name: str = UNKNOWN
    symbol: str = UNKNOWN
    creator: str = UNKNOWN
    created_at: datetime
    observed_at: datetime
    launch_platform: LaunchSource
    lifecycle_state: LifecycleState = "NEW"
    has_pool: Optional[bool] = None
    liquidity_usd: Optional[float] = None
    market_cap_usd: Optional[float] = None
    volume_24h_usd: Optional[float] = None
    coverage: ProviderCoverage


class LaunchEventSource(Protocol):
    """Launch event Adapter contract shared by every provider integration."""

    async def launch_events(self) -> Sequence[LaunchEvent]:
        """Return source-neutral launch events ordered by observed time."""


class RecordedLaunchEventSource:
    """Deterministic Adapter over recorded events; performs no network I/O."""

    def __init__(self, events: Sequence[LaunchEvent]) -> None:
        self._events = list(events)

    async def launch_events(self) -> Sequence[LaunchEvent]:
        return sorted(self._events, key=lambda event: (event.observed_at, event.event_id))
