"""Recorded Meteora Dynamic Bonding Curve launch-program normalizer.

Meteora documents its Dynamic Bonding Curve program; Jupiter Studio uses that
curve and graduates its Tokens into a Meteora pool.  This Adapter accepts only
recorded program facts and maps them to the source-neutral ``LaunchEvent``
contract.  It deliberately performs no RPC or HTTP calls.
"""

from collections.abc import Sequence
from datetime import datetime
from typing import Literal, Optional

from pydantic import Field, model_validator

from paper_trade.launch_events import (
    UNKNOWN,
    LaunchEvent,
    LaunchEventModel,
    ProviderCoverage,
    _is_solana_public_key,
)
from paper_trade.research_configuration import LaunchSource

METEORA_DBC_PROGRAM_ID = "dbcij3LWUppWqq96dh6gJWwBifmcGfLSB5D4DuSMaqN"
MeteoraDbcEventKind = Literal["create", "graduate"]
MeteoraDbcLaunchSource = Literal["METEORA_DBC", "JUPITER_STUDIO"]


class MeteoraDbcProgramEvent(LaunchEventModel):
    """A documented Meteora DBC create or graduation fact recorded by a provider.

    ``launch_source`` denotes the original launch provenance.  A Jupiter Studio
    graduation is observed on Meteora DBC, but remains ``JUPITER_STUDIO`` so a
    Token does not lose its source when it enters a Meteora pool.
    """

    event_id: str = Field(min_length=1)
    kind: MeteoraDbcEventKind
    address: str = Field(min_length=1)
    name: str = UNKNOWN
    symbol: str = UNKNOWN
    creator: str = UNKNOWN
    created_at: datetime
    observed_at: datetime
    launch_source: MeteoraDbcLaunchSource
    graduation_pool_address: Optional[str] = None
    liquidity_usd: Optional[float] = None
    market_cap_usd: Optional[float] = None
    volume_24h_usd: Optional[float] = None
    coverage: ProviderCoverage

    @model_validator(mode="after")
    def validate_graduation_pool(self) -> "MeteoraDbcProgramEvent":
        if not _is_solana_public_key(self.address):
            raise ValueError("address must be a valid Solana public key")
        if self.creator != UNKNOWN and not _is_solana_public_key(self.creator):
            raise ValueError("creator must be a valid Solana public key")
        if self.graduation_pool_address is not None and not _is_solana_public_key(
            self.graduation_pool_address
        ):
            raise ValueError("graduation_pool_address must be a valid Solana public key")
        if self.kind == "graduate" and self.graduation_pool_address is None:
            if "graduation_pool_address" not in self.coverage.unknown_fields:
                raise ValueError(
                    "graduate events require graduation_pool_address or explicit unknown coverage"
                )
        if self.kind == "create" and self.graduation_pool_address is not None:
            raise ValueError("create events cannot carry graduation_pool_address")
        return self


class MeteoraDbcLaunchEventSource:
    """Deterministic LaunchEventSource over recorded Meteora DBC program facts."""

    def __init__(self, events: Sequence[MeteoraDbcProgramEvent]) -> None:
        self._events = list(events)

    async def launch_events(self) -> Sequence[LaunchEvent]:
        return sorted(
            (normalize_meteora_dbc_event(event) for event in self._events),
            key=lambda event: (event.observed_at, event.event_id),
        )


def normalize_meteora_dbc_event(event: MeteoraDbcProgramEvent) -> LaunchEvent:
    """Normalize a documented DBC create/graduation into the shared event form."""

    return LaunchEvent(
        event_id=event.event_id,
        address=event.address,
        name=event.name,
        symbol=event.symbol,
        creator=event.creator,
        created_at=event.created_at,
        observed_at=event.observed_at,
        launch_platform=_launch_source(event.launch_source),
        lifecycle_state="NEW" if event.kind == "create" else "MIGRATED",
        has_pool=False if event.kind == "create" else True,
        graduation_pool_address=event.graduation_pool_address,
        liquidity_usd=event.liquidity_usd,
        market_cap_usd=event.market_cap_usd,
        volume_24h_usd=event.volume_24h_usd,
        coverage=event.coverage,
    )


def _launch_source(source: MeteoraDbcLaunchSource) -> LaunchSource:
    return source
