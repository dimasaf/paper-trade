"""Recorded-data Adapter for the documented Raydium LaunchLab program.

The adapter accepts decoded transaction facts from the documented LaunchLab
program address, not a launchpad frontend endpoint. It emits the common
source-neutral ``LaunchEvent`` form so creation and migration lifecycle updates
follow the same registration path as every other launch source.
"""

from collections.abc import Mapping, Sequence
from datetime import datetime
from typing import Any, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field, ValidationError, model_validator

from paper_trade.launch_events import LaunchEvent, ProviderCoverage

RAYDIUM_LAUNCHLAB_PROGRAM_ID = "LanMV9sAd7wArD4vJFi2qDdfnVhFxYSUg6eADduJ3uj"
RAYDIUM_LAUNCHLAB_PROVIDER = "raydium-launchlab-program"
RAYDIUM_LAUNCHLAB_NORMALIZATION_VERSION = "raydium-launchlab/v1"


class RaydiumLaunchLabProgramActivity(BaseModel):
    """One decoded fact from Raydium's documented LaunchLab program data."""

    model_config = ConfigDict(extra="forbid")

    program_id: Literal["LanMV9sAd7wArD4vJFi2qDdfnVhFxYSUg6eADduJ3uj"]
    activity: Literal["creation", "migration", "pool_creation"]
    signature: str = Field(min_length=1)
    slot: int = Field(ge=0)
    block_time: datetime
    observed_at: datetime
    commitment: Literal["confirmed", "processed"]
    mint: str = Field(min_length=1)
    creator: str = Field(min_length=1)
    name: Optional[str] = None
    symbol: Optional[str] = None
    pool: Optional[str] = None

    @model_validator(mode="after")
    def validate_activity(self) -> "RaydiumLaunchLabProgramActivity":
        if self.observed_at < self.block_time:
            raise ValueError("observed_at must not be earlier than block_time")
        if self.activity in ("migration", "pool_creation") and not self.pool:
            raise ValueError("migration and pool_creation activity requires pool")
        return self


class RecordedRaydiumLaunchLabSource:
    """Network-free LaunchLab Adapter over recorded decoded program activity.

    Malformed records are rejected rather than guessed. Processed records are
    deliberately omitted: only confirmed activity may enter Token registration.
    A transaction can expose both migration and pool-creation facts, so the
    source uses its signature and mint as the source event identity.
    """

    def __init__(self, records: Sequence[Mapping[str, Any]]) -> None:
        self._records: list[RaydiumLaunchLabProgramActivity] = []
        self.rejected_record_count = 0
        for record in records:
            try:
                activity = RaydiumLaunchLabProgramActivity.model_validate(dict(record))
                _normalize(activity)
                self._records.append(activity)
            except ValidationError:
                self.rejected_record_count += 1

    async def launch_events(self) -> Sequence[LaunchEvent]:
        events_by_id: dict[str, LaunchEvent] = {}
        for record in self._records:
            if record.commitment != "confirmed":
                continue
            event = _normalize(record)
            events_by_id.setdefault(event.event_id, event)
        return sorted(events_by_id.values(), key=lambda event: (event.observed_at, event.event_id))


def _normalize(record: RaydiumLaunchLabProgramActivity) -> LaunchEvent:
    missing_metadata = [
        field for field, value in (("name", record.name), ("symbol", record.symbol)) if not value
    ]
    warnings: list[str] = []
    if record.activity != "creation":
        warnings.append(f"Raydium LaunchLab migration created pool {record.pool}")
    if missing_metadata:
        warnings.append("LaunchLab program data does not include Token metadata")

    return LaunchEvent(
        event_id=f"raydium-launchlab:{record.signature}",
        address=record.mint,
        name=record.name or "UNKNOWN",
        symbol=record.symbol or "UNKNOWN",
        creator=record.creator,
        created_at=record.block_time,
        observed_at=record.observed_at,
        launch_platform="RAYDIUM_LAUNCHLAB",
        lifecycle_state="NEW" if record.activity == "creation" else "MIGRATED",
        has_pool=record.activity != "creation",
        coverage=ProviderCoverage(
            provider=RAYDIUM_LAUNCHLAB_PROVIDER,
            as_of_start=record.block_time,
            as_of_end=record.observed_at,
            complete=not missing_metadata,
            commitment=record.commitment,
            freshness_seconds=int((record.observed_at - record.block_time).total_seconds()),
            signature=record.signature,
            slot=record.slot,
            normalization_version=RAYDIUM_LAUNCHLAB_NORMALIZATION_VERSION,
            unknown_fields=missing_metadata,
            warnings=warnings,
        ),
    )
