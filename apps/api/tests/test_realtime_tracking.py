"""Confirmed real-time Wallet tracking through its public contracts and HTTP seam."""

from datetime import datetime, timedelta, timezone
from typing import Callable, Optional

import pytest
from fastapi.testclient import TestClient
from realtime_event_contract import StaticSmartWalletSource
from recorded_realtime_activity import (
    AS_OF,
    SMART_WALLET,
    TOKEN,
    UNSUBSCRIBED_WALLET,
    recorded_realtime_source,
    recorded_smart_wallet_subscriptions,
)

from paper_trade.main import create_app
from paper_trade.realtime_tracking import (
    InMemoryRealtimeTrackingStore,
    RealtimeTrackingService,
    RealtimeWalletEvent,
)
from paper_trade.research_configuration import InMemoryResearchConfigurationStore
from paper_trade.wallet_behavior import WalletBehavior
from paper_trade.wallet_copyability import WalletCopyability
from paper_trade.wallet_scoring import (
    InMemoryWalletScoringStore,
    RecordWalletRegistryTransition,
    WalletScoringService,
)


def fixed_clock() -> datetime:
    return AS_OF


class StepClock:
    """A monotonic test clock so processing latency is deterministic and positive."""

    def __init__(self) -> None:
        self._calls = 0

    def __call__(self) -> datetime:
        self._calls += 1
        return AS_OF + timedelta(milliseconds=100 * self._calls)


def tracking_service(
    *, clock: Optional[Callable[[], datetime]] = None
) -> RealtimeTrackingService:
    return RealtimeTrackingService(
        recorded_realtime_source(),
        StaticSmartWalletSource(recorded_smart_wallet_subscriptions()),
        InMemoryRealtimeTrackingStore(),
        now=clock or fixed_clock,
    )


def by_signature(events: list[RealtimeWalletEvent]) -> dict[str, RealtimeWalletEvent]:
    return {event.signature: event for event in events}


async def test_only_the_smart_wallet_registry_state_is_subscribed() -> None:
    service = tracking_service()

    run = await service.poll(AS_OF)

    assert run.subscribed_wallets == [SMART_WALLET]
    assert UNSUBSCRIBED_WALLET not in run.subscribed_wallets


async def test_tracking_never_publishes_activity_from_unsubscribed_wallets() -> None:
    service = tracking_service()

    run = await service.poll(AS_OF)
    events = await service.feed(100)

    assert run.skipped_unsubscribed == 1
    assert UNSUBSCRIBED_WALLET not in {event.wallet_address for event in events}
    assert "recorded-realtime-unsubscribed-0006" not in {event.signature for event in events}


async def test_smart_wallets_reads_the_registry_state_not_the_recommendation() -> None:
    scoring_store = InMemoryWalletScoringStore(now=fixed_clock)
    await scoring_store.record_transition(
        RecordWalletRegistryTransition(
            address=SMART_WALLET,
            from_state="CANDIDATE",
            to_state="SMART_WALLET",
            reason="The recorded score met the Smart Wallet threshold.",
            evidence=["recorded score met the Smart Wallet threshold"],
            as_of=AS_OF,
            configuration_version=1,
        )
    )
    await scoring_store.record_transition(
        RecordWalletRegistryTransition(
            address=UNSUBSCRIBED_WALLET,
            from_state="CANDIDATE",
            to_state="WATCHLIST",
            reason="The recorded score met only the Watchlist threshold.",
            evidence=["recorded score met only the Watchlist threshold"],
            as_of=AS_OF,
            configuration_version=1,
        )
    )
    service = WalletScoringService(
        _UnusedBehaviorStore(),
        _UnusedCopyabilityStore(),
        InMemoryResearchConfigurationStore(now=fixed_clock),
        scoring_store,
        _AddressStore([SMART_WALLET, UNSUBSCRIBED_WALLET]),
    )

    subscriptions = await service.smart_wallets(AS_OF)

    assert [subscription.address for subscription in subscriptions] == [SMART_WALLET]
    assert subscriptions[0].score is None


async def test_confirmed_activity_normalizes_into_historical_movement_forms() -> None:
    service = tracking_service()

    await service.poll(AS_OF)
    events = by_signature(await service.feed(100))

    assert {event.movement_type for event in events.values()} == {
        "BUY",
        "SELL",
        "TRANSFER_IN",
        "TRANSFER_OUT",
    }

    buy = events["recorded-realtime-buy-0001"]
    assert buy.token_address == TOKEN
    assert buy.quantity == pytest.approx(1000)
    assert buy.notional_usd == pytest.approx(500)
    assert buy.price_usd == pytest.approx(0.5)
    assert buy.wallet_score == pytest.approx(91)
    assert buy.score_as_of == AS_OF
    assert buy.chain_time == datetime(2026, 9, 28, 10, 0, tzinfo=timezone.utc)
    assert buy.observed_at == datetime(2026, 9, 28, 10, 0, 4, tzinfo=timezone.utc)
    assert buy.coverage.provider == "recorded-realtime"

    sell = events["recorded-realtime-sell-0002"]
    assert sell.movement_type == "SELL"
    assert sell.price_usd == pytest.approx(0.65)

    transfer_in = events["recorded-realtime-transfer-in-0003"]
    assert transfer_in.movement_type == "TRANSFER_IN"
    assert transfer_in.notional_usd is None
    assert transfer_in.price_usd is None

    unknown = events["recorded-realtime-buy-unknown-0005"]
    assert unknown.movement_type == "BUY"
    assert unknown.notional_usd is None
    assert unknown.price_usd is None
    assert unknown.coverage.complete is False
    assert unknown.coverage.unknown_fields == ["notional_usd"]


async def test_processed_only_activity_is_recorded_but_never_triggers_decisions() -> None:
    service = tracking_service()

    await service.poll(AS_OF)
    events = await service.feed(100)
    processed = next(event for event in events if event.commitment == "processed")

    assert processed.eligible_for_decisions is False
    assert processed.warnings

    decision_events = await service.decision_events()
    assert processed.signature not in {event.signature for event in decision_events}
    assert all(event.eligible_for_decisions for event in decision_events)
    assert {event.commitment for event in decision_events} == {"confirmed"}


async def test_signature_and_slot_idempotency_survives_reconnect_and_replay() -> None:
    service = tracking_service()

    first = await service.poll(AS_OF)
    stored_after_first = len(await service.feed(100))
    second = await service.poll(AS_OF)

    assert first.duplicates == 1
    assert second.recorded == 0
    assert second.duplicates == first.recorded + first.duplicates
    assert len(await service.feed(100)) == stored_after_first

    replayed = by_signature(await service.feed(100))["recorded-realtime-buy-0001"]
    assert replayed.observed_at == datetime(2026, 9, 28, 10, 0, 4, tzinfo=timezone.utc)


async def test_tracking_run_and_status_make_lag_duplicates_and_latency_observable() -> None:
    service = tracking_service(clock=StepClock())

    run = await service.poll(AS_OF)
    status = await service.status()

    assert run.received == 8
    assert run.recorded == 6
    assert run.duplicates == 1
    assert run.processed_only == 1
    assert run.skipped_unsubscribed == 1
    assert run.reconnects == 1
    assert run.max_lag_seconds == pytest.approx(22.0)
    assert run.processing_latency_seconds > 0

    assert status.subscribed_wallets == [SMART_WALLET]
    assert status.stored_events == 6
    assert status.decision_events == 5
    assert status.received == 8
    assert status.duplicates == 1
    assert status.reconnects == 1
    assert status.max_lag_seconds == pytest.approx(22.0)
    assert status.last_run_at == run.completed_at


def test_realtime_tracking_http_contract() -> None:
    client = TestClient(create_app(realtime_tracking_service=tracking_service()))

    poll = client.post("/realtime/polls")
    feed = client.get("/realtime/feed?limit=3")
    status = client.get("/realtime/status")

    assert poll.status_code == 201
    assert poll.json()["subscribed_wallets"] == [SMART_WALLET]
    assert poll.json()["recorded"] == 6
    assert feed.status_code == 200
    assert len(feed.json()) == 3
    assert status.status_code == 200
    assert status.json()["stored_events"] == 6
    assert status.json()["decision_events"] == 5


def test_realtime_tracking_endpoints_return_503_when_unavailable() -> None:
    client = TestClient(create_app())

    assert client.post("/realtime/polls").status_code == 503
    assert client.get("/realtime/feed").status_code == 503
    assert client.get("/realtime/status").status_code == 503


class _AddressStore:
    def __init__(self, addresses: list[str]) -> None:
        self._addresses = addresses

    async def list_wallets(self) -> list[str]:
        return list(self._addresses)


class _UnusedBehaviorStore:
    async def behavior(self, address: str, as_of: datetime) -> WalletBehavior:
        raise AssertionError("smart_wallets must not read recorded Wallet behavior")


class _UnusedCopyabilityStore:
    async def copyability(self, address: str, as_of: datetime) -> WalletCopyability:
        raise AssertionError("smart_wallets must not read recorded Copyability")
