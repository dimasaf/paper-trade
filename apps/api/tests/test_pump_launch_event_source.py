"""Recorded pump.fun and PumpSwap program activity at the Adapter contract seam."""

from datetime import datetime

import pytest
from launch_event_contract import (
    assert_launch_event_registration_is_idempotent,
    assert_launch_event_source_contract,
)

from paper_trade.launch_events import ProviderCoverage
from paper_trade.pump_launch_events import (
    PUMP_FUN_PROGRAM_ID,
    PUMP_SWAP_PROGRAM_ID,
    PumpLaunchEventSource,
    PumpProgramEvent,
)
from paper_trade.research_configuration import InMemoryResearchConfigurationStore
from paper_trade.tokens import InMemoryTokenStore, TokenRegistrationService

TOKEN_ADDRESS = "7GCihgDB8fe6KNjn2MYtkzZcRjQy3t9GHdC8uHYmW2hr"
CREATOR_ADDRESS = "5Q544fKrFoe6tsEbD7S8EmxGTJYAKtTVhAW5Q5pge4j1"
BONDING_CURVE_ADDRESS = "CebN5WGQ4jvEPvsVU4EoHEpgzWSwZyg2ECvZNaaopump"
POOL_ADDRESS = "4wBqpZM9W7D6h2ZQ5E6o1CymCPG9hrpE7cXkYkKpE8Qm"


def _at(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def _coverage(*, event_id: str, commitment: str = "confirmed") -> ProviderCoverage:
    return ProviderCoverage(
        provider="recorded-pump-programs",
        as_of_start=_at("2026-09-28T09:00:00Z"),
        as_of_end=_at("2026-09-28T09:30:00Z"),
        complete=True,
        commitment=commitment,  # type: ignore[arg-type]
        freshness_seconds=2,
        signature=f"recorded-signature-{event_id}",
        slot=314159300,
        normalization_version="pump-launch-event/v1",
    )


def _recorded_program_events() -> list[PumpProgramEvent]:
    return [
        PumpProgramEvent(
            event_id="pump-create-0001",
            program_id=PUMP_FUN_PROGRAM_ID,
            event_type="CREATE",
            address=TOKEN_ADDRESS,
            creator=CREATOR_ADDRESS,
            name="Recorded Pump Token",
            symbol="RPUMP",
            occurred_at=_at("2026-09-28T09:00:00Z"),
            observed_at=_at("2026-09-28T09:00:02Z"),
            bonding_curve=BONDING_CURVE_ADDRESS,
            coverage=_coverage(event_id="pump-create-0001"),
        ),
        PumpProgramEvent(
            event_id="pump-progress-0002",
            program_id=PUMP_FUN_PROGRAM_ID,
            event_type="BONDING_CURVE_PROGRESS",
            address=TOKEN_ADDRESS,
            creator=CREATOR_ADDRESS,
            occurred_at=_at("2026-09-28T09:05:00Z"),
            observed_at=_at("2026-09-28T09:05:02Z"),
            bonding_curve=BONDING_CURVE_ADDRESS,
            bonding_curve_progress_percent=72.5,
            coverage=_coverage(event_id="pump-progress-0002"),
        ),
        PumpProgramEvent(
            event_id="pumpswap-pool-0003",
            program_id=PUMP_SWAP_PROGRAM_ID,
            event_type="POOL_CREATE",
            address=TOKEN_ADDRESS,
            creator=CREATOR_ADDRESS,
            occurred_at=_at("2026-09-28T09:10:00Z"),
            observed_at=_at("2026-09-28T09:10:02Z"),
            pool=POOL_ADDRESS,
            coverage=_coverage(event_id="pumpswap-pool-0003"),
        ),
        PumpProgramEvent(
            event_id="processed-create-0004",
            program_id=PUMP_FUN_PROGRAM_ID,
            event_type="CREATE",
            address="9BB6NFEcjBCtnNLFko2FqVQBq8HHM13kCyYcdQbgpump",
            creator=CREATOR_ADDRESS,
            occurred_at=_at("2026-09-28T09:20:00Z"),
            observed_at=_at("2026-09-28T09:20:02Z"),
            coverage=_coverage(event_id="processed-create-0004", commitment="processed"),
        ),
    ]


def _source() -> PumpLaunchEventSource:
    events = _recorded_program_events()
    return PumpLaunchEventSource([events[2], events[0], events[1], events[2], events[3]])


async def test_pump_launch_event_source_satisfies_the_provider_contract() -> None:
    await assert_launch_event_source_contract(_source())


async def test_pump_source_normalizes_documented_program_evidence_and_filters_processed() -> None:
    events = await _source().launch_events()

    assert [event.event_id for event in events] == [
        "pump-create-0001",
        "pump-progress-0002",
        "pumpswap-pool-0003",
    ]
    assert [event.lifecycle_state for event in events] == ["NEW", "ACTIVE", "MIGRATED"]
    assert events[0].launch_platform == "PUMP_FUN"
    assert events[2].launch_platform == "PUMP_SWAP"
    assert events[1].evidence[0].bonding_curve_progress_percent == 72.5
    assert events[2].evidence[0].pool == POOL_ADDRESS


async def test_pump_source_create_and_migration_register_once_with_retained_evidence() -> None:
    source = _source()
    await assert_launch_event_registration_is_idempotent(
        source,
        InMemoryTokenStore(),
        InMemoryResearchConfigurationStore(),
    )

    store = InMemoryTokenStore()
    service = TokenRegistrationService(
        store=store,
        configuration_store=InMemoryResearchConfigurationStore(),
    )
    for event in await source.launch_events():
        await service.register_launch_event(event)
        await service.register_launch_event(event)

    token = (await store.list())[0]
    assert token.lifecycle_state == "MIGRATED"
    assert [transition.state for transition in token.lifecycle_transitions] == [
        "NEW",
        "ACTIVE",
        "MIGRATED",
    ]
    assert token.lifecycle_transitions[1].evidence[0].bonding_curve == BONDING_CURVE_ADDRESS
    assert token.lifecycle_transitions[2].evidence[0].pool == POOL_ADDRESS
    assert len(token.coverage) == 3


def test_pump_source_rejects_an_event_from_the_wrong_documented_program() -> None:
    event = _recorded_program_events()[0].model_copy(update={"program_id": PUMP_SWAP_PROGRAM_ID})
    with pytest.raises(ValueError, match="documented program"):
        PumpLaunchEventSource([event])
