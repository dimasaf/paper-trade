"""Recorded pump.fun and PumpSwap Adapter over documented on-chain program events.

This Adapter deliberately accepts recorded program facts instead of making network
requests. A realtime RPC or webhook client can supply the same facts later without
changing Token registration or the deterministic provider contract.
"""

from collections.abc import Sequence
from datetime import datetime
from typing import Literal, Optional

from pydantic import Field, field_validator, model_validator

from paper_trade.launch_events import (
    LaunchEvent,
    LaunchEventModel,
    LaunchProgramEvidence,
    LifecycleState,
    ProviderCoverage,
    _is_solana_public_key,
)

# Documented in the pump.fun public program documentation and PumpSwap README.
PUMP_FUN_PROGRAM_ID = "6EF8rrecthR5Dkzon8Nwu78hRvfCKubJ14M5uBEwF6P"
PUMP_SWAP_PROGRAM_ID = "pAMMBay6oceH9fJKBRHGP5D4bD4sWpmSwMn52FMfXEA"

PumpProgramEventType = Literal[
    "CREATE",
    "BONDING_CURVE_PROGRESS",
    "GRADUATION",
    "POOL_CREATE",
    "MIGRATION",
]

_PUMP_FUN_EVENT_TYPES = frozenset({"CREATE", "BONDING_CURVE_PROGRESS", "GRADUATION"})
_PUMP_SWAP_EVENT_TYPES = frozenset({"POOL_CREATE", "MIGRATION"})
_EVENT_NAMES: dict[PumpProgramEventType, str] = {
    "CREATE": "CreateEvent",
    "BONDING_CURVE_PROGRESS": "TradeEvent",
    "GRADUATION": "CompleteEvent",
    "POOL_CREATE": "CreatePoolEvent",
    "MIGRATION": "CreatePoolEvent",
}


class PumpProgramEvent(LaunchEventModel):
    """One recorded, documented pump.fun or PumpSwap program event."""

    event_id: str = Field(min_length=1)
    program_id: str
    event_type: PumpProgramEventType
    address: str
    creator: str
    name: str = "UNKNOWN"
    symbol: str = "UNKNOWN"
    occurred_at: datetime
    observed_at: datetime
    bonding_curve: Optional[str] = None
    bonding_curve_progress_percent: Optional[float] = Field(default=None, ge=0, le=100)
    pool: Optional[str] = None
    coverage: ProviderCoverage

    @field_validator("program_id", "address", "creator", "bonding_curve", "pool")
    @classmethod
    def validate_solana_public_key(cls, value: Optional[str]) -> Optional[str]:
        if value is not None and not _is_solana_public_key(value):
            raise ValueError("must be a valid Solana public key")
        return value

    @model_validator(mode="after")
    def validate_documented_program(self) -> "PumpProgramEvent":
        expected_program = (
            PUMP_FUN_PROGRAM_ID
            if self.event_type in _PUMP_FUN_EVENT_TYPES
            else PUMP_SWAP_PROGRAM_ID
        )
        if self.program_id != expected_program:
            raise ValueError("event_type must originate from its documented program")
        if self.observed_at < self.occurred_at:
            raise ValueError("observed_at must not be earlier than occurred_at")
        if (
            self.event_type == "BONDING_CURVE_PROGRESS"
            and self.bonding_curve_progress_percent is None
        ):
            raise ValueError("bonding-curve progress must include its observed percentage")
        if self.event_type in _PUMP_SWAP_EVENT_TYPES and self.pool is None:
            raise ValueError("PumpSwap pool creation or migration must include its pool")
        return self


class PumpLaunchEventSource:
    """Normalize confirmed recorded pump.fun/PumpSwap program events.

    Replayed records with the same event id are collapsed before they reach the
    Token universe. Conflicting records with one id are rejected rather than
    choosing one silently. Processed facts never normalize into launch events.
    """

    def __init__(self, events: Sequence[PumpProgramEvent]) -> None:
        # Revalidation rejects untrusted model copies as well as parsed input.
        self._events = [PumpProgramEvent.model_validate(event.model_dump()) for event in events]

    async def launch_events(self) -> Sequence[LaunchEvent]:
        unique: dict[str, PumpProgramEvent] = {}
        for event in self._events:
            if event.coverage.commitment != "confirmed":
                continue
            prior = unique.get(event.event_id)
            if prior is not None and prior != event:
                raise ValueError("conflicting recorded pump program event id")
            unique[event.event_id] = event
        return sorted(
            (self._normalize(event) for event in unique.values()),
            key=lambda event: (event.observed_at, event.event_id),
        )

    @staticmethod
    def _normalize(event: PumpProgramEvent) -> LaunchEvent:
        is_pumpswap = event.event_type in _PUMP_SWAP_EVENT_TYPES
        lifecycle_state: LifecycleState = (
            "NEW"
            if event.event_type == "CREATE"
            else "ACTIVE"
            if event.event_type == "BONDING_CURVE_PROGRESS"
            else "MIGRATED"
        )
        return LaunchEvent(
            event_id=event.event_id,
            address=event.address,
            name=event.name,
            symbol=event.symbol,
            creator=event.creator,
            created_at=event.occurred_at,
            observed_at=event.observed_at,
            launch_platform="PUMP_SWAP" if is_pumpswap else "PUMP_FUN",
            lifecycle_state=lifecycle_state,
            has_pool=True if is_pumpswap else False,
            evidence=[
                LaunchProgramEvidence(
                    event_type=event.event_type,
                    program_id=event.program_id,
                    event_name=_EVENT_NAMES[event.event_type],
                    bonding_curve=event.bonding_curve,
                    bonding_curve_progress_percent=event.bonding_curve_progress_percent,
                    pool=event.pool,
                )
            ],
            coverage=event.coverage,
        )
