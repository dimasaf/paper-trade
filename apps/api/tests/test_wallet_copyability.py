"""Recorded Copyability calculations and their public HTTP seam."""

import json
from datetime import datetime
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from paper_trade.main import create_app
from paper_trade.market_state import InMemoryMarketStateStore
from paper_trade.research_configuration import InMemoryResearchConfigurationStore
from paper_trade.wallet_accounting import (
    InMemoryWalletAccountingStore,
    RecordedWalletHistorySource,
    WalletAccountingService,
    WalletActivity,
    WalletHistoryCoverage,
    WalletMarkPrice,
)
from paper_trade.wallet_copyability import (
    CopyabilityPoolCoverage,
    RecordedCopyabilityMarketPoolSource,
    RecordedMarketPool,
    StoredCopyabilityMarketPoolSource,
    WalletCopyabilityService,
)

FIXTURES = Path(__file__).parent / "fixtures"
WALLET = "5Q544fKrFoe6tsEbD7S8EmxGTJYAKtTVhAW5Q5pge4j1"
TOKEN = "7GCihgDB8fe6KNjn2MYtkzZcRjQy3t9GHdC8uHYmW2hr"


def at(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def accounting_store() -> InMemoryWalletAccountingStore:
    document = json.loads((FIXTURES / "recorded_wallet_history.json").read_text())
    return InMemoryWalletAccountingStore(
        WalletAccountingService(
            RecordedWalletHistorySource(
                [[WalletActivity.model_validate(item) for item in document["activities"]]],
                WalletHistoryCoverage.model_validate(document["coverage"]),
            ),
            [
                WalletMarkPrice(
                    token_address=TOKEN,
                    price_usd=5,
                    observed_at=at("2026-09-28T09:50:00Z"),
                    provider="DEXSCREENER",
                )
            ],
        )
    )


def pool_source(
    *, reserves: bool = True, illiquid: bool = False
) -> RecordedCopyabilityMarketPoolSource:
    document = json.loads((FIXTURES / "recorded_copyability_market_pools.json").read_text())
    pools = [RecordedMarketPool.model_validate(item) for item in document["pools"]]
    if not reserves:
        pools = [
            pool.model_copy(update={"sol_reserve": None, "token_reserve": None}) for pool in pools
        ]
    elif illiquid:
        pools = [pool.model_copy(update={"sol_reserve": 1, "token_reserve": 50}) for pool in pools]
    return RecordedCopyabilityMarketPoolSource(
        pools, CopyabilityPoolCoverage.model_validate(document["coverage"])
    )


@pytest.mark.asyncio
async def test_recorded_copyability_uses_delayed_pool_states_and_constant_product_fills() -> None:
    result = await WalletCopyabilityService(accounting_store(), pool_source()).copyability(
        WALLET, at("2026-09-28T10:00:00Z")
    )

    assert result.delays_ms == [500, 1000, 2000, 3000, 5000, 10000]
    assert result.follower_sizes_sol == [0.1, 0.25, 0.5, 1.0, 2.0]
    first = next(
        outcome
        for outcome in result.outcomes
        if outcome.follower_delay_ms == 500 and outcome.follower_size_sol == 0.1
    )
    delayed = next(
        outcome
        for outcome in result.outcomes
        if outcome.follower_delay_ms == 10000 and outcome.follower_size_sol == 0.1
    )
    assert first.status == "FILLED"
    assert first.entry_fill is not None and first.exit_fill is not None
    assert first.entry_fill.model == "CONSTANT_PRODUCT"
    assert first.entry_fill.requested_at == at("2026-09-28T09:05:00.500000Z")
    assert first.entry_fill.filled_at == at("2026-09-28T09:05:00.500000Z")
    assert first.entry_fill.liquidity_usd == 200000
    assert first.entry_fill.price_impact_percent is not None
    assert first.follower_roi_percent is not None
    assert first.copy_decay_percent is not None
    assert delayed.entry_fill is not None
    assert delayed.entry_fill.price_usd > first.entry_fill.price_usd
    assert delayed.follower_roi_percent is not None
    assert delayed.follower_roi_percent < first.follower_roi_percent


@pytest.mark.asyncio
async def test_recorded_copyability_rejects_illiquid_follower_size() -> None:
    source = pool_source(illiquid=True)
    result = await WalletCopyabilityService(accounting_store(), source).copyability(
        WALLET, at("2026-09-28T10:00:00Z")
    )

    rejected = next(
        outcome
        for outcome in result.outcomes
        if outcome.follower_delay_ms == 500 and outcome.follower_size_sol == 2
    )
    assert rejected.status == "REJECTED"
    assert rejected.follower_roi_percent is None
    assert "pool participation limit" in rejected.warnings[0]


@pytest.mark.asyncio
async def test_recorded_copyability_marks_missing_reserves_as_low_confidence_fallback() -> None:
    service = WalletCopyabilityService(accounting_store(), pool_source(reserves=False))
    result = await service.copyability(WALLET, at("2026-09-28T10:00:00Z"))

    outcome = next(outcome for outcome in result.outcomes if outcome.status == "FILLED")
    assert outcome.entry_fill is not None
    assert outcome.entry_fill.model == "FIXED_SLIPPAGE"
    assert outcome.entry_fill.confidence == "LOW"
    assert outcome.entry_fill.slippage_percent == 2
    assert outcome.entry_fill.venue_fee_sol > 0
    assert outcome.entry_fill.source_evidence
    assert outcome.entry_fill.fallback_assumptions
    assert "fixed-slippage fallback" in outcome.warnings[0]
    assert "Recorded market-pool coverage is incomplete." in result.warnings


@pytest.mark.asyncio
async def test_copyability_rejects_stale_snapshots_and_reports_scenario_unknowns() -> None:
    document = json.loads((FIXTURES / "recorded_copyability_market_pools.json").read_text())
    coverage = CopyabilityPoolCoverage.model_validate(document["coverage"]).model_copy(
        update={"freshness_seconds": 0}
    )
    source = RecordedCopyabilityMarketPoolSource(
        [RecordedMarketPool.model_validate(item) for item in document["pools"]], coverage
    )

    result = await WalletCopyabilityService(accounting_store(), source).copyability(
        WALLET, at("2026-09-28T10:00:00Z")
    )

    outcome = next(
        item
        for item in result.outcomes
        if item.follower_delay_ms == 500 and item.follower_size_sol == 0.1
    )
    assert outcome.status == "REJECTED"
    assert "exit_pool_snapshot_stale" in outcome.coverage.unknown_fields
    assert outcome.pool_selections[1].status == "STALE"


@pytest.mark.asyncio
async def test_copyability_rejects_pools_that_do_not_match_the_leader_venue() -> None:
    document = json.loads((FIXTURES / "recorded_copyability_market_pools.json").read_text())
    source = RecordedCopyabilityMarketPoolSource(
        [
            RecordedMarketPool.model_validate(item).model_copy(update={"venue": "Meteora"})
            for item in document["pools"]
        ],
        CopyabilityPoolCoverage.model_validate(document["coverage"]),
    )

    result = await WalletCopyabilityService(accounting_store(), source).copyability(
        WALLET, at("2026-09-28T10:00:00Z")
    )

    assert all(outcome.status == "REJECTED" for outcome in result.outcomes)
    assert "No Raydium pool snapshot" in result.outcomes[0].pool_selections[0].warning


@pytest.mark.asyncio
async def test_copyability_requires_liquidity_for_fallback_and_limits_exit_participation() -> None:
    document = json.loads((FIXTURES / "recorded_copyability_market_pools.json").read_text())
    pools = [RecordedMarketPool.model_validate(item) for item in document["pools"]]
    unsupported_fallback = [
        pool.model_copy(update={"pool_model": "DLMM", "sol_reserve": None, "token_reserve": None})
        for pool in pools
    ]
    fallback = await WalletCopyabilityService(
        accounting_store(),
        RecordedCopyabilityMarketPoolSource(
            unsupported_fallback, CopyabilityPoolCoverage.model_validate(document["coverage"])
        ),
    ).copyability(WALLET, at("2026-09-28T10:00:00Z"))
    assert fallback.outcomes[0].entry_fill is not None
    assert fallback.outcomes[0].entry_fill.model == "FIXED_SLIPPAGE"
    assert "Unsupported pool model DLMM" in fallback.outcomes[0].warnings[0]

    rejected = await WalletCopyabilityService(
        accounting_store(),
        RecordedCopyabilityMarketPoolSource(
            [pool.model_copy(update={"liquidity_usd": None}) for pool in unsupported_fallback],
            CopyabilityPoolCoverage.model_validate(document["coverage"]),
        ),
    ).copyability(WALLET, at("2026-09-28T10:00:00Z"))
    assert all(outcome.status == "REJECTED" for outcome in rejected.outcomes)
    assert "fallback sizing is unsupported" in rejected.outcomes[0].warnings[0]

    exit_limited = [
        pool.model_copy(update={"token_reserve": 100})
        if pool.observed_at >= at("2026-09-28T09:20:00Z")
        else pool
        for pool in pools
    ]
    result = await WalletCopyabilityService(
        accounting_store(),
        RecordedCopyabilityMarketPoolSource(
            exit_limited, CopyabilityPoolCoverage.model_validate(document["coverage"])
        ),
    ).copyability(WALLET, at("2026-09-28T10:00:00Z"))
    outcome = next(
        item
        for item in result.outcomes
        if item.follower_delay_ms == 500 and item.follower_size_sol == 0.1
    )
    assert outcome.status == "REJECTED"
    assert "exit exceeds" in outcome.warnings[0]


def test_wallet_copyability_endpoint_exposes_recorded_outcomes_and_coverage() -> None:
    client = TestClient(
        create_app(
            wallet_copyability_store=WalletCopyabilityService(accounting_store(), pool_source())
        )
    )

    response = client.get(f"/wallets/{WALLET}/copyability?as_of=2026-09-28T10:00:00Z")

    assert response.status_code == 200
    document = response.json()
    assert document["delays_ms"] == [500, 1000, 2000, 3000, 5000, 10000]
    assert document["follower_sizes_sol"] == [0.1, 0.25, 0.5, 1.0, 2.0]
    assert document["outcomes"][0]["entry_fill"]["model"] == "CONSTANT_PRODUCT"
    assert document["outcomes"][0]["pool_selections"][0]["venue"] == "Raydium"
    assert document["outcomes"][0]["coverage"]["token_address"] == TOKEN
    assert document["coverage"]["provider"] == "RECORDED_MARKET_POOL"


def test_wallet_copyability_endpoint_composes_stored_market_evidence() -> None:
    client = TestClient(
        create_app(
            wallet_accounting_store=accounting_store(),
            market_state_store=InMemoryMarketStateStore(),
            research_configuration_store=InMemoryResearchConfigurationStore(),
        )
    )

    response = client.get(f"/wallets/{WALLET}/copyability?as_of=2026-09-28T10:00:00Z")

    assert response.status_code == 200
    assert response.json()["configuration_version"] == 1
    assert response.json()["coverage"]["unknown_fields"] == ["market_pool_state"]


@pytest.mark.asyncio
async def test_pool_coverage_is_token_specific_and_not_unioned_across_tokens() -> None:
    other = "9BB6NFEcjBCtnNLFko2FqVQBq8HHM13kCyYcdQbgpump"

    result = await pool_source().market_pools([TOKEN, other], at("2026-09-28T10:00:00Z"))

    assert "market_pool_state" not in result.token_coverage[TOKEN].unknown_fields
    assert "market_pool_state" in result.token_coverage[other].unknown_fields
    assert any(other in warning for warning in result.token_coverage[other].warnings)


@pytest.mark.asyncio
async def test_stored_pool_coverage_reports_each_tokens_own_gaps() -> None:
    other = "9BB6NFEcjBCtnNLFko2FqVQBq8HHM13kCyYcdQbgpump"
    store = InMemoryMarketStateStore()

    result = await StoredCopyabilityMarketPoolSource(store).market_pools(
        [TOKEN, other], at("2026-09-28T10:00:00Z")
    )

    assert result.coverage.complete is False
    assert result.token_coverage[TOKEN].complete is False
    assert result.token_coverage[other].complete is False
    assert "market_pool_state" in result.token_coverage[other].unknown_fields
