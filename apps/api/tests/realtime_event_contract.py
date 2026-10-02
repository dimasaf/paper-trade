"""Shared deterministic contract that every ``RealtimeSource`` Adapter must satisfy."""

from collections.abc import Sequence
from datetime import datetime
from typing import get_args

from paper_trade.realtime_tracking import (
    RealtimeActivity,
    RealtimeSource,
    RealtimeTrackingService,
    SmartWalletSubscription,
)
from paper_trade.wallet_accounting import WalletMovementType


class StaticSmartWalletSource:
    """Deterministic SmartWalletSource over a fixed subscription list."""

    def __init__(self, subscriptions: Sequence[SmartWalletSubscription]) -> None:
        self._subscriptions = list(subscriptions)

    async def smart_wallets(self, as_of: datetime) -> list[SmartWalletSubscription]:
        return list(self._subscriptions)


async def assert_realtime_source_contract(
    source: RealtimeSource, wallets: Sequence[str]
) -> None:
    batches = await source.subscribe(wallets)

    assert batches, "a recorded realtime source must return at least one batch"
    ordering = [(batch.connected_at, batch.connection_id) for batch in batches]
    assert ordering == sorted(ordering), "batches must be ordered by connected time"
    assert await source.subscribe(wallets) == batches, "recorded reads must be deterministic"

    for batch in batches:
        within = [(item.observed_at, item.signature, item.slot) for item in batch.activity]
        assert within == sorted(within), "activity must be ordered by observed time"
    activity = [item for batch in batches for item in batch.activity]
    assert activity, "a recorded realtime source must return at least one activity"
    for item in activity:
        _assert_activity_shape(item)


def _assert_activity_shape(activity: RealtimeActivity) -> None:
    assert activity.event_id
    assert activity.wallet_address
    assert activity.token_address
    assert activity.signature
    assert activity.slot >= 0
    assert activity.chain_time <= activity.observed_at
    assert activity.quantity > 0
    assert activity.movement_type in get_args(WalletMovementType)

    coverage = activity.coverage
    assert coverage.provider
    assert coverage.normalization_version
    assert coverage.commitment in ("confirmed", "processed")
    assert coverage.freshness_seconds >= 0
    assert coverage.as_of_start <= coverage.as_of_end
    if activity.movement_type in ("BUY", "SELL"):
        if activity.notional_usd is None:
            assert "notional_usd" in coverage.unknown_fields, (
                "a BUY or SELL without a valuation must declare notional_usd unknown"
            )
    else:
        assert activity.notional_usd is None
    if not coverage.complete:
        assert coverage.unknown_fields or coverage.warnings, (
            "incomplete coverage must declare unknown fields or warnings"
        )


async def assert_realtime_tracking_is_idempotent(
    service: RealtimeTrackingService, as_of: datetime
) -> None:
    first = await service.poll(as_of)
    second = await service.poll(as_of)

    assert second.received == first.received
    assert second.recorded == 0
    assert second.duplicates == first.recorded + first.duplicates
