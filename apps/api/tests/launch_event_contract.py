"""Shared deterministic contract that every `LaunchEventSource` Adapter must satisfy."""

from typing import get_args

from paper_trade.launch_events import (
    LIFECYCLE_STATES,
    UNKNOWN,
    LaunchEvent,
    LaunchEventSource,
    LaunchSource,
)
from paper_trade.research_configuration import ResearchConfigurationStore
from paper_trade.tokens import TokenRegistrationService, TokenStore

LAUNCH_PLATFORMS = get_args(LaunchSource)


async def assert_launch_event_source_contract(source: LaunchEventSource) -> None:
    events = await source.launch_events()

    assert events, "a recorded launch event source must return at least one event"
    ordering = [(event.observed_at, event.event_id) for event in events]
    assert ordering == sorted(ordering), "events must be ordered by observed time"
    assert await source.launch_events() == events, "recorded reads must be deterministic"

    for event in events:
        _assert_event_shape(event)


async def assert_launch_event_registration_is_idempotent(
    source: LaunchEventSource,
    store: TokenStore,
    configuration_store: ResearchConfigurationStore,
) -> None:
    service = TokenRegistrationService(
        store=store,
        configuration_store=configuration_store,
    )
    events = await source.launch_events()
    confirmed = [event for event in events if event.coverage.commitment == "confirmed"]
    for event in confirmed:
        await service.register_launch_event(event)
        await service.register_launch_event(event)
    for event in events:
        if event.coverage.commitment == "processed":
            rejected = await service.register_launch_event(event)
            assert rejected.status == "rejected"

    tokens = await store.list()
    expected_addresses = {event.address for event in confirmed}
    assert {token.address for token in tokens} == expected_addresses
    for token in tokens:
        event_ids = {event.event_id for event in confirmed if event.address == token.address}
        assert len(token.lifecycle_transitions) == len(event_ids)
        assert len(token.coverage) == len(event_ids)


def _assert_event_shape(event: LaunchEvent) -> None:
    assert event.event_id
    assert event.address
    assert event.created_at <= event.observed_at
    assert event.launch_platform in LAUNCH_PLATFORMS
    assert event.lifecycle_state in LIFECYCLE_STATES

    coverage = event.coverage
    assert coverage.provider
    assert coverage.as_of_start <= coverage.as_of_end
    assert coverage.commitment in ("confirmed", "processed")
    assert coverage.freshness_seconds >= 0
    assert coverage.signature
    assert coverage.slot >= 0
    assert coverage.normalization_version
    if not coverage.complete:
        assert coverage.unknown_fields or coverage.warnings, (
            "incomplete coverage must declare unknown fields or warnings"
        )
    for field in coverage.unknown_fields:
        assert field in LaunchEvent.model_fields, f"{field} is not a launch event field"
        observed = getattr(event, field)
        assert observed is None or observed == UNKNOWN, (
            f"{field} is declared unknown but carries {observed!r}"
        )
