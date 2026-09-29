"""Source-neutral launch events and the provider contract seam.

Every launch Adapter (pump.fun/PumpSwap, Raydium LaunchLab, Meteora DBC, Jupiter
Studio) normalizes documented program activity into a `LaunchEvent` and satisfies
`LaunchEventSource`. Token registration, classification, lifecycle, and coverage
behaviour therefore stays shared rather than provider specific.
"""

from collections.abc import Sequence
from datetime import datetime
from typing import Literal, Optional, Protocol

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from paper_trade.research_configuration import LaunchSource

UNKNOWN = "UNKNOWN"

Commitment = Literal["confirmed", "processed"]

LifecycleState = Literal["NEW", "ACTIVE", "MIGRATED", "ILLIQUID", "DEAD", "SUSPICIOUS"]

BASE58_ALPHABET = frozenset("123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz")
SOLANA_PUBLIC_KEY_LENGTHS = frozenset(range(32, 45))

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
    freshness_seconds: int = Field(ge=0)
    signature: str = Field(min_length=1)
    slot: int = Field(ge=0)
    normalization_version: str = Field(min_length=1)
    unknown_fields: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_interval(self) -> "ProviderCoverage":
        if self.as_of_end < self.as_of_start:
            raise ValueError("as_of_end must not be earlier than as_of_start")
        if not self.complete and not (self.unknown_fields or self.warnings):
            raise ValueError("incomplete coverage must declare unknown_fields or warnings")
        return self


class LaunchProgramEvidence(LaunchEventModel):
    """Documented on-chain program evidence retained with a launch transition."""

    event_type: str = Field(min_length=1)
    program_id: str
    event_name: str = Field(min_length=1)
    bonding_curve: Optional[str] = None
    bonding_curve_progress_percent: Optional[float] = Field(default=None, ge=0, le=100)
    pool: Optional[str] = None

    @field_validator("program_id", "bonding_curve", "pool")
    @classmethod
    def validate_optional_solana_public_key(cls, value: Optional[str]) -> Optional[str]:
        if value is not None and not _is_solana_public_key(value):
            raise ValueError("must be a valid Solana public key")
        return value


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
    evidence: list[LaunchProgramEvidence] = Field(default_factory=list)
    coverage: ProviderCoverage

    @field_validator("address", "creator")
    @classmethod
    def validate_solana_public_key(cls, value: str) -> str:
        if not _is_solana_public_key(value):
            raise ValueError("must be a valid Solana public key")
        return value

    @model_validator(mode="after")
    def validate_coverage_facts(self) -> "LaunchEvent":
        for field in self.coverage.unknown_fields:
            value = getattr(self, field)
            if value is not None and value != UNKNOWN:
                raise ValueError(f"{field} is declared unknown but carries {value!r}")
        return self


def _is_solana_public_key(value: str) -> bool:
    if len(value) not in SOLANA_PUBLIC_KEY_LENGTHS or not set(value) <= BASE58_ALPHABET:
        return False
    number = 0
    for character in value:
        number = number * 58 + "123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz".index(
            character
        )
    return len(number.to_bytes((number.bit_length() + 7) // 8, "big")) == 32


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
