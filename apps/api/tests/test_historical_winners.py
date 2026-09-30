"""Recorded historical-winner discovery through its Adapter and HTTP seams."""

import asyncio
import json
from datetime import datetime
from pathlib import Path
from typing import Optional
from uuid import UUID

import pytest
from fastapi.testclient import TestClient
from recorded_launch_events import recorded_pump_swap_launch_event

from paper_trade.health import ComponentHealth, HealthComponents, HealthReport
from paper_trade.historical_winners import (
    HistoricalWinnerCohortRequest,
    InMemoryHistoricalWinnerDiscoveryStore,
    RecordedEarlyBuyerSource,
    RecordedEarlyBuyerTransaction,
)
from paper_trade.main import create_app
from paper_trade.market_state import (
    InMemoryMarketStateStore,
    MarketObservation,
    MarketPool,
    MarketProviderCoverage,
)
from paper_trade.research_configuration import InMemoryResearchConfigurationStore
from paper_trade.tokens import InMemoryTokenStore
from paper_trade.wallet_accounting import WalletHistoryCoverage

TOKEN = "7GCihgDB8fe6KNjn2MYtkzZcRjQy3t9GHdC8uHYmW2hr"
WALLET = "5Q544fKrFoe6tsEbD7S8EmxGTJYAKtTVhAW5Q5pge4j1"
OTHER_WALLET = "4wBqpZM9W7D6h2ZQ5E6o1CymCPG9hrpE7cXkYkKpE8Qm"
POOL = "9xQeWvG816bUx9EPf8aYxGB4pXzv5S1kYQBF3h4r7S1i"
FIXTURE_PATH = Path(__file__).parent / "fixtures" / "recorded_early_buyers.json"


def at(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


class ReadyHealthService:
    async def check(self) -> HealthReport:
        ready = ComponentHealth(status="ready", message="ready")
        return HealthReport(
            checked_at=at("2026-09-28T09:00:00Z"),
            components=HealthComponents(
                application=ready, database=ready, redis=ready, worker=ready
            ),
        )


def fixture() -> dict[str, object]:
    return json.loads(FIXTURE_PATH.read_text())


def coverage() -> WalletHistoryCoverage:
    return WalletHistoryCoverage.model_validate(fixture()["coverage"])


def transaction(**changes: object) -> RecordedEarlyBuyerTransaction:
    document = fixture()["transactions"][0]
    assert isinstance(document, dict)
    document.update(changes)
    return RecordedEarlyBuyerTransaction.model_validate(document)


@pytest.mark.asyncio
async def test_recorded_early_buyer_adapter_is_deterministic_and_as_of_bounded() -> None:
    first = transaction()
    future = transaction(
        signature="recorded-early-buy-future-0002",
        chain_time=at("2026-09-28T11:00:00Z"),
    )
    source = RecordedEarlyBuyerSource(pages=[[first, future], [first]], coverage=coverage())

    history = await source.early_buyers(TOKEN, at("2026-09-28T10:00:00Z"))

    assert [item.signature for item in history.transactions] == ["recorded-early-buy-0001"]
    assert history.coverage.requested_as_of == at("2026-09-28T10:00:00Z")
    assert history.coverage.unknown_fields == ["price_usd", "liquidity_usd"]


def observation(
    observation_id: str, observed_at: str, market_cap: float, liquidity: Optional[float]
) -> MarketObservation:
    return MarketObservation(
        observation_id=observation_id,
        address=TOKEN,
        observed_at=at(observed_at),
        price_usd=0.002,
        supply=1_000_000_000,
        market_cap_usd=market_cap,
        liquidity_usd=liquidity,
        volume_24h_usd=20_000,
        pools=[MarketPool(address=POOL, venue="Raydium")],
        coverage=MarketProviderCoverage(
            provider="DEXSCREENER",
            requested_as_of=at(observed_at),
            as_of_start=at(observed_at),
            as_of_end=at(observed_at),
            complete=True,
            freshness_seconds=3600,
            unknown_fields=[] if liquidity is not None else ["liquidity_usd"],
        ),
    )


def client() -> TestClient:
    market_store = InMemoryMarketStateStore()
    asyncio.run(market_store.record(observation("initial", "2026-09-28T09:00:00Z", 120_000, 5_000)))
    asyncio.run(market_store.record(observation("entry", "2026-09-28T09:04:00Z", 125_000, None)))
    # This peak qualifies the Token, but it is deliberately unavailable to its 09:05 entry.
    asyncio.run(
        market_store.record(observation("future-peak", "2026-09-28T09:50:00Z", 1_200_000, 60_000))
    )
    source = RecordedEarlyBuyerSource(
        pages=[
            [
                transaction(),
                transaction(
                    wallet_address=OTHER_WALLET,
                    signature="recorded-failed-buy-0002",
                    succeeded=False,
                    notional_usd=20,
                ),
            ]
        ],
        coverage=coverage(),
    )
    identifiers = iter([UUID("00000000-0000-0000-0000-000000000001")])
    app = create_app(
        health_service=ReadyHealthService(),
        research_configuration_store=InMemoryResearchConfigurationStore(
            now=lambda: at("2026-09-28T09:00:00Z"), id_factory=lambda: next(identifiers)
        ),
        token_store=InMemoryTokenStore(),
        market_state_store=market_store,
        early_buyer_source=source,
        historical_winner_discovery_store=InMemoryHistoricalWinnerDiscoveryStore(),
    )
    return TestClient(app)


def test_historical_winner_endpoint_freezes_configuration_and_hides_future_entry_facts() -> None:
    api = client()
    assert (
        api.post(
            "/tokens", json={"event": recorded_pump_swap_launch_event().model_dump(mode="json")}
        ).status_code
        == 201
    )

    response = api.post(
        "/discovery/historical-winners",
        json={
            "cohort_id": "recorded-september-winners",
            "created_from": "2026-09-28T09:00:00Z",
            "created_to": "2026-09-28T09:00:00Z",
            "qualification_as_of": "2026-09-28T10:00:00Z",
        },
    )

    assert response.status_code == 201
    document = response.json()
    assert document["configuration_version"] == 1
    assert document["winners"][0]["qualified"] is True
    assert document["winners"][0]["initial_market_cap_usd"] == 120_000
    assert document["winners"][0]["peak_market_cap_usd"] == 1_200_000
    assert document["winners"][0]["qualifying_facts"] == [
        {
            "criterion": "initial_market_cap_usd",
            "observed": "120000",
            "threshold": ">= 10000 and <= 500000",
            "passed": True,
        },
        {
            "criterion": "peak_market_cap_usd",
            "observed": "1.2e+06",
            "threshold": ">= 1e+06",
            "passed": True,
        },
    ]
    early_buyer = document["early_buyers"][0]
    assert early_buyer["wallet_address"] == WALLET
    assert early_buyer["amount_tokens"] == 10
    assert early_buyer["price_usd"] is None
    assert early_buyer["market_cap_usd"] == 125_000
    assert early_buyer["liquidity_usd"] is None
    assert early_buyer["token_age_seconds"] == 300
    assert early_buyer["venue"] == "Raydium"
    assert early_buyer["signature"] == "recorded-early-buy-0001"
    assert early_buyer["entry_market_cap_bucket"] == "<= 250000"
    assert early_buyer["entry_evaluation"] == {
        "as_of": "2026-09-28T09:05:00Z",
        "unavailable_facts": [
            "future_peak_market_cap_usd",
            "future_rug_status",
            "future_wallet_quality",
        ],
    }
    assert "price_usd is UNKNOWN at the entry as-of time" in early_buyer["warnings"]
    assert "liquidity_usd is UNKNOWN at the entry as-of time" in early_buyer["warnings"]
    assert [(item["wallet_address"], item["passed"]) for item in document["candidate_wallets"]] == [
        (OTHER_WALLET, False),
        (WALLET, True),
    ]
    assert document["candidate_wallets"][1]["evidence"][0]["criterion"] == "successful_buy"

    latest = api.get("/discovery/historical-winners/latest")
    assert latest.status_code == 200
    assert latest.json() == document


def test_historical_winner_endpoint_rejects_a_cohort_cutoff_before_its_boundary() -> None:
    response = client().post(
        "/discovery/historical-winners",
        json={
            "cohort_id": "invalid",
            "created_from": "2026-09-28T09:00:00Z",
            "created_to": "2026-09-28T10:00:00Z",
            "qualification_as_of": "2026-09-28T09:59:00Z",
        },
    )
    assert response.status_code == 422
    assert "qualification_as_of must not be earlier than created_to" in response.text
