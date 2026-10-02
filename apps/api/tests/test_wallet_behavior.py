"""Wallet behavior metrics through recorded evidence and HTTP public seams."""

import json
from datetime import datetime
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from paper_trade.main import create_app
from paper_trade.market_state import InMemoryMarketStateStore
from paper_trade.wallet_accounting import (
    InMemoryWalletAccountingStore,
    RecordedWalletHistorySource,
    WalletAccountingService,
    WalletActivity,
    WalletHistoryCoverage,
    WalletMarkPrice,
)
from paper_trade.wallet_behavior import (
    InMemoryWalletBehaviorStore,
    MarketEvidenceCoverage,
    RecordedMarketEvidenceSource,
    WalletBehaviorService,
    WalletMarketEvidence,
)

FIXTURE_DIRECTORY = Path(__file__).parent / "fixtures"
WALLET = "5Q544fKrFoe6tsEbD7S8EmxGTJYAKtTVhAW5Q5pge4j1"
TOKEN = "7GCihgDB8fe6KNjn2MYtkzZcRjQy3t9GHdC8uHYmW2hr"


def at(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def accounting_store() -> InMemoryWalletAccountingStore:
    history_document = json.loads((FIXTURE_DIRECTORY / "recorded_wallet_history.json").read_text())
    return InMemoryWalletAccountingStore(
        WalletAccountingService(
            history_source=RecordedWalletHistorySource(
                pages=[
                    [WalletActivity.model_validate(item) for item in history_document["activities"]]
                ],
                coverage=WalletHistoryCoverage.model_validate(history_document["coverage"]),
            ),
            prices=[
                WalletMarkPrice(
                    token_address=TOKEN,
                    price_usd=5,
                    observed_at=at("2026-09-28T09:50:00Z"),
                    provider="DEXSCREENER",
                )
            ],
        )
    )


def behavior_store() -> InMemoryWalletBehaviorStore:
    evidence_document = json.loads(
        (FIXTURE_DIRECTORY / "recorded_wallet_behavior_evidence.json").read_text()
    )
    evidence_source = RecordedMarketEvidenceSource(
        evidence=[
            WalletMarketEvidence.model_validate(item) for item in evidence_document["evidence"]
        ],
        coverage=MarketEvidenceCoverage.model_validate(evidence_document["coverage"]),
    )
    return InMemoryWalletBehaviorStore(WalletBehaviorService(accounting_store(), evidence_source))


@pytest.mark.asyncio
async def test_recorded_behavior_calculates_all_windows_without_future_evidence() -> None:
    behavior = await behavior_store().behavior(WALLET, at("2026-09-28T10:00:00Z"))

    assert [window.period for window in behavior.windows] == ["24H", "7D", "30D", "90D", "ALL_TIME"]
    all_time = behavior.windows[-1]
    assert all_time.realized_pnl_usd == pytest.approx(21.5)
    assert all_time.unrealized_pnl_usd == pytest.approx(5.7)
    assert all_time.total_pnl_usd == pytest.approx(27.2)
    assert all_time.roi_percent == pytest.approx(59.3886462882)
    assert all_time.win_rate_percent == 100
    assert all_time.trade_count == 2
    assert all_time.position_size_usd.median == 26
    assert all_time.holding_time_seconds.median == 750
    assert all_time.consistency.profit_concentration.top_one_percent == 100
    assert all_time.consistency.profitable_days == 1
    assert all_time.meme.early_entry_rate_percent == 100
    assert all_time.meme.creation_to_entry_latency_seconds.median == 30
    assert all_time.meme.entry_market_cap_usd.average == 12000
    assert all_time.meme.entry_liquidity_usd.average == 8000
    assert all_time.meme.sub_100k_entry_rate_percent == 100
    assert all_time.meme.sub_500k_entry_rate_percent == 100
    assert all_time.meme.rug_exposure_rate_percent == 0
    assert all_time.meme.dead_token_exposure_rate_percent == 0
    assert all_time.meme.migration_success_rate_percent == 100
    assert all_time.meme.token_activity_per_active_day == 1
    assert {item.name for item in behavior.classifications} == {"EARLY_BUYER", "SCALPER"}
    assert all(item.score_effect == "NONE" for item in behavior.classifications)
    flags = {item.name: item for item in behavior.flags}
    assert {
        "INCOMPLETE_HISTORY_COVERAGE",
        "TRANSFER_DERIVED_INVENTORY",
        "UNCLASSIFIED_ACTIVITY",
        "RAPID_TOKEN_ENTRY",
    } <= set(flags)
    assert "does not identify intent" in flags["RAPID_TOKEN_ENTRY"].wording
    assert flags["RAPID_TOKEN_ENTRY"].confidence == "MEDIUM"
    assert all(flag.evidence and flag.coverage for flag in behavior.flags)
    assert "future observation" not in str(behavior.model_dump())


def test_wallet_behavior_endpoint_exposes_definitions_and_flags() -> None:
    client = TestClient(create_app(wallet_behavior_store=behavior_store()))

    response = client.get(f"/wallets/{WALLET}/behavior?as_of=2026-09-28T10:00:00Z")

    assert response.status_code == 200
    document = response.json()
    assert len(document["metric_definitions"]) == 4
    assert document["windows"][0]["period"] == "24H"
    assert document["windows"][-1]["meme"]["migration_success_rate_percent"] == 100
    assert document["classifications"][0]["score_effect"] == "NONE"
    assert document["flags"][0]["coverage"]
    assert document["coverage"][1]["unknown_fields"] == [
        "historical_liquidity_before_recorded_observation"
    ]


@pytest.mark.asyncio
async def test_behavior_uses_only_evidence_at_or_before_wallet_entry() -> None:
    wallet_store = accounting_store()
    source = RecordedMarketEvidenceSource(
        evidence=[
            WalletMarketEvidence(
                token_address=TOKEN,
                observed_at=at("2026-09-28T09:06:00Z"),
                entry_market_cap_usd=999_999,
                entry_liquidity_usd=999_999,
                evidence=["recorded after Wallet entry"],
            )
        ],
        coverage=MarketEvidenceCoverage(
            provider="RECORDED_MARKET_EVIDENCE",
            requested_as_of=at("2026-09-28T10:00:00Z"),
            as_of_start=at("2026-09-28T09:00:00Z"),
            as_of_end=at("2026-09-28T10:00:00Z"),
            complete=False,
            unknown_fields=["entry_market_cap_usd", "entry_liquidity_usd"],
        ),
    )

    behavior = await WalletBehaviorService(wallet_store, source).behavior(
        WALLET, at("2026-09-28T10:00:00Z")
    )

    assert behavior.windows[-1].meme.entry_market_cap_usd.average is None
    assert behavior.windows[-1].meme.entry_liquidity_usd.average is None


def test_wallet_behavior_endpoint_composes_a_service_from_accounting_and_market_stores() -> None:
    wallet_store = accounting_store()
    client = TestClient(
        create_app(
            wallet_accounting_store=wallet_store,
            market_state_store=InMemoryMarketStateStore(),
        )
    )

    response = client.get(f"/wallets/{WALLET}/behavior?as_of=2026-09-28T10:00:00Z")

    assert response.status_code == 200
    assert response.json()["windows"][-1]["meme"]["entry_market_cap_usd"]["average"] is None
