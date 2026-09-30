"""Recorded market-state Adapter behavior at the public provider contract seam."""

from datetime import datetime
from typing import Optional

import pytest

from paper_trade.market_state import (
    MarketObservation,
    MarketPool,
    MarketProvider,
    MarketProviderCoverage,
    RecordedMarketDataSource,
)

TOKEN_ADDRESS = "7GCihgDB8fe6KNjn2MYtkzZcRjQy3t9GHdC8uHYmW2hr"
POOL_ADDRESS = "4wBqpZM9W7D6h2ZQ5E6o1CymCPG9hrpE7cXkYkKpE8Qm"


def _at(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def _observation(
    *,
    observation_id: str,
    provider: MarketProvider = "DEXSCREENER",
    observed_at: str = "2026-09-28T09:01:00Z",
    complete: bool = True,
    unknown_fields: Optional[list[str]] = None,
    warnings: Optional[list[str]] = None,
) -> MarketObservation:
    return MarketObservation(
        observation_id=observation_id,
        address=TOKEN_ADDRESS,
        observed_at=_at(observed_at),
        price_usd=0.0025,
        supply=1_000_000_000 if complete else None,
        market_cap_usd=2_500_000 if complete else None,
        liquidity_usd=125_000 if complete else None,
        volume_24h_usd=450_000 if complete else None,
        pools=[MarketPool(address=POOL_ADDRESS, venue="Raydium")] if complete else [],
        coverage=MarketProviderCoverage(
            provider=provider,
            requested_as_of=_at(observed_at),
            as_of_start=_at(observed_at),
            as_of_end=_at(observed_at),
            complete=complete,
            freshness_seconds=30,
            unknown_fields=unknown_fields or [],
            warnings=warnings or [],
        ),
    )


@pytest.mark.asyncio
async def test_recorded_market_source_returns_deduplicated_pages_in_provider_order() -> None:
    later = _observation(
        observation_id="recorded-dex-0002",
        observed_at="2026-09-28T09:02:00Z",
    )
    earlier = _observation(observation_id="recorded-dex-0001")
    source = RecordedMarketDataSource(pages=[[later], [earlier, earlier]])

    observations = await source.market_observations(TOKEN_ADDRESS, _at("2026-09-28T09:03:00Z"))

    assert [observation.observation_id for observation in observations] == [
        "recorded-dex-0001",
        "recorded-dex-0002",
    ]
    assert all(observation.coverage.provider == "DEXSCREENER" for observation in observations)


@pytest.mark.asyncio
async def test_recorded_market_source_preserves_omissions_and_rate_limit_coverage() -> None:
    omitted = _observation(
        observation_id="recorded-jupiter-rate-limit-0001",
        provider="JUPITER",
        complete=False,
        unknown_fields=["supply", "market_cap_usd", "liquidity_usd", "volume_24h_usd", "pools"],
        warnings=["Recorded rate limit after one retry; market fields remain UNKNOWN"],
    )
    source = RecordedMarketDataSource(pages=[[omitted]])

    observations = await source.market_observations(TOKEN_ADDRESS, _at("2026-09-28T09:01:00Z"))

    assert observations == [omitted]
    assert observations[0].coverage.complete is False
    assert observations[0].market_cap_usd is None
    assert "rate limit" in observations[0].coverage.warnings[0].lower()


@pytest.mark.asyncio
async def test_recorded_market_source_rejects_conflicting_retries_for_one_observation() -> None:
    initial = _observation(observation_id="recorded-dex-retry-0001")
    conflicting_retry = initial.model_copy(update={"price_usd": 0.003})
    source = RecordedMarketDataSource(pages=[[initial], [conflicting_retry]])

    with pytest.raises(ValueError, match="conflicting recorded market observation"):
        await source.market_observations(TOKEN_ADDRESS, _at("2026-09-28T09:01:00Z"))
