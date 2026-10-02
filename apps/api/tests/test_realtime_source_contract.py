from collections.abc import Callable

import pytest
from realtime_event_contract import (
    StaticSmartWalletSource,
    assert_realtime_source_contract,
    assert_realtime_tracking_is_idempotent,
)
from recorded_realtime_activity import (
    SMART_WALLET,
    recorded_realtime_source,
    recorded_smart_wallet_subscriptions,
)

from paper_trade.realtime_tracking import (
    InMemoryRealtimeTrackingStore,
    RealtimeSource,
    RealtimeTrackingService,
)

SOURCE_FACTORIES: list[tuple[str, Callable[[], RealtimeSource]]] = [
    ("recorded", recorded_realtime_source),
]


@pytest.mark.parametrize(
    ("source_name", "source_factory"),
    SOURCE_FACTORIES,
    ids=[name for name, _ in SOURCE_FACTORIES],
)
async def test_realtime_source_satisfies_the_provider_contract(
    source_name: str,
    source_factory: Callable[[], RealtimeSource],
) -> None:
    await assert_realtime_source_contract(source_factory(), [SMART_WALLET])


@pytest.mark.parametrize(
    ("source_name", "source_factory"),
    SOURCE_FACTORIES,
    ids=[name for name, _ in SOURCE_FACTORIES],
)
async def test_recorded_realtime_tracking_is_idempotent(
    source_name: str,
    source_factory: Callable[[], RealtimeSource],
) -> None:
    service = RealtimeTrackingService(
        source_factory(),
        StaticSmartWalletSource(recorded_smart_wallet_subscriptions()),
        InMemoryRealtimeTrackingStore(),
    )
    subscriptions = recorded_smart_wallet_subscriptions()
    await assert_realtime_tracking_is_idempotent(service, subscriptions[0].as_of)
