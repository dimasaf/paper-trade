"""Recorded, network-free launch events used by the deterministic suite."""

from datetime import datetime

from paper_trade.launch_events import LaunchEvent, ProviderCoverage, RecordedLaunchEventSource

PUMP_SWAP_ADDRESS = "7GCihgDB8fe6KNjn2MYtkzZcRjQy3t9GHdC8uHYmW2hr"
PUMP_FUN_ADDRESS = "27G8MtK7VtTcCHkpASjSDdkWWYfoqT6ggEuKidVJidD4"
PROCESSED_ADDRESS = "9BB6NFEcjBCtnNLFko2FqVQBq8HHM13kCyYcdQbgpump"
CREATOR_ADDRESS = "5Q544fKrFoe6tsEbD7S8EmxGTJYAKtTVhAW5Q5pge4j1"


def _at(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def recorded_pump_swap_launch_event() -> LaunchEvent:
    """A confirmed PumpSwap pool launch with complete recorded coverage."""

    return LaunchEvent(
        event_id="recorded-pumpswap-pool-0001",
        address=PUMP_SWAP_ADDRESS,
        name="Recorded Swap Token",
        symbol="RSWAP",
        creator=CREATOR_ADDRESS,
        created_at=_at("2026-09-28T09:00:00Z"),
        observed_at=_at("2026-09-28T09:00:05Z"),
        launch_platform="PUMP_SWAP",
        lifecycle_state="NEW",
        has_pool=True,
        liquidity_usd=52_000.0,
        market_cap_usd=120_000.0,
        volume_24h_usd=30_000.0,
        coverage=ProviderCoverage(
            provider="recorded-pumpswap",
            as_of_start=_at("2026-09-28T09:00:00Z"),
            as_of_end=_at("2026-09-28T09:05:00Z"),
            complete=True,
            commitment="confirmed",
            freshness_seconds=5,
            signature="recorded-signature-pumpswap-0001",
            slot=314159265,
            normalization_version="launch-event/v1",
        ),
    )


def recorded_pump_fun_launch_event() -> LaunchEvent:
    """A confirmed pump.fun creation with explicit missing market facts."""

    return LaunchEvent(
        event_id="recorded-pumpfun-create-0002",
        address=PUMP_FUN_ADDRESS,
        name="Recorded Bonding Token",
        symbol="RBOND",
        creator=CREATOR_ADDRESS,
        created_at=_at("2026-09-28T09:10:00Z"),
        observed_at=_at("2026-09-28T09:10:04Z"),
        launch_platform="PUMP_FUN",
        lifecycle_state="NEW",
        has_pool=False,
        coverage=ProviderCoverage(
            provider="recorded-pumpfun",
            as_of_start=_at("2026-09-28T09:10:00Z"),
            as_of_end=_at("2026-09-28T09:12:00Z"),
            complete=False,
            commitment="confirmed",
            freshness_seconds=4,
            signature="recorded-signature-pumpfun-0002",
            slot=314159266,
            normalization_version="launch-event/v1",
            unknown_fields=["liquidity_usd", "market_cap_usd", "volume_24h_usd"],
            warnings=["Bonding-curve market facts are not available at creation"],
        ),
    )


def recorded_processed_launch_event() -> LaunchEvent:
    """A launch event observed at processed commitment, which must never register."""

    return LaunchEvent(
        event_id="recorded-pumpswap-processed-0003",
        address=PROCESSED_ADDRESS,
        name="Recorded Processed Token",
        symbol="RPROC",
        creator=CREATOR_ADDRESS,
        created_at=_at("2026-09-28T09:20:00Z"),
        observed_at=_at("2026-09-28T09:20:02Z"),
        launch_platform="PUMP_SWAP",
        lifecycle_state="NEW",
        coverage=ProviderCoverage(
            provider="recorded-pumpswap",
            as_of_start=_at("2026-09-28T09:20:00Z"),
            as_of_end=_at("2026-09-28T09:20:02Z"),
            complete=False,
            commitment="processed",
            freshness_seconds=2,
            signature="recorded-signature-processed-0003",
            slot=314159267,
            normalization_version="launch-event/v1",
            unknown_fields=["has_pool", "liquidity_usd", "market_cap_usd", "volume_24h_usd"],
        ),
    )


def recorded_launch_events() -> list[LaunchEvent]:
    return [
        recorded_pump_swap_launch_event(),
        recorded_pump_fun_launch_event(),
        recorded_processed_launch_event(),
    ]


def recorded_launch_event_source() -> RecordedLaunchEventSource:
    return RecordedLaunchEventSource(recorded_launch_events())
