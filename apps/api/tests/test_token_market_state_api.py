"""HTTP behavior for a Token's point-in-time market state."""

import asyncio
from datetime import datetime, timezone
from uuid import UUID

from fastapi.testclient import TestClient
from recorded_launch_events import recorded_pump_swap_launch_event

from paper_trade.health import ComponentHealth, HealthComponents, HealthReport
from paper_trade.main import create_app
from paper_trade.market_state import (
    InMemoryMarketStateStore,
    MarketObservation,
    MarketPool,
    MarketProvider,
    MarketProviderCoverage,
)
from paper_trade.research_configuration import InMemoryResearchConfigurationStore
from paper_trade.tokens import InMemoryTokenStore

TOKEN_ADDRESS = "7GCihgDB8fe6KNjn2MYtkzZcRjQy3t9GHdC8uHYmW2hr"
POOL_ADDRESS = "4wBqpZM9W7D6h2ZQ5E6o1CymCPG9hrpE7cXkYkKpE8Qm"


class ReadyHealthService:
    async def check(self) -> HealthReport:
        ready = ComponentHealth(status="ready", message="ready")
        return HealthReport(
            checked_at=datetime(2026, 9, 28, 9, 0, tzinfo=timezone.utc),
            components=HealthComponents(
                application=ready,
                database=ready,
                redis=ready,
                worker=ready,
            ),
        )


def _at(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def _client(store: InMemoryMarketStateStore) -> TestClient:
    identifiers = iter([UUID("00000000-0000-0000-0000-000000000001")])
    return TestClient(
        create_app(
            health_service=ReadyHealthService(),
            research_configuration_store=InMemoryResearchConfigurationStore(
                now=lambda: _at("2026-09-28T09:00:00Z"),
                id_factory=lambda: next(identifiers),
            ),
            token_store=InMemoryTokenStore(),
            market_state_store=store,
        )
    )


def _observation(
    *,
    observation_id: str,
    observed_at: str,
    provider: MarketProvider = "DEXSCREENER",
    market_cap: float,
) -> MarketObservation:
    return MarketObservation(
        observation_id=observation_id,
        address=TOKEN_ADDRESS,
        observed_at=_at(observed_at),
        price_usd=0.0025,
        supply=1_000_000_000,
        market_cap_usd=market_cap,
        liquidity_usd=market_cap / 20,
        volume_24h_usd=450_000,
        pools=[MarketPool(address=POOL_ADDRESS, venue="Raydium")],
        coverage=MarketProviderCoverage(
            provider=provider,
            requested_as_of=_at(observed_at),
            as_of_start=_at(observed_at),
            as_of_end=_at(observed_at),
            complete=True,
            freshness_seconds=60,
        ),
    )


def _register_token(client: TestClient) -> None:
    response = client.post(
        "/tokens", json={"event": recorded_pump_swap_launch_event().model_dump(mode="json")}
    )
    assert response.status_code == 201


def test_market_state_returns_one_coherent_current_provider_and_derived_peaks() -> None:
    store = InMemoryMarketStateStore()
    client = _client(store)
    _register_token(client)

    stale_dex = _observation(
        observation_id="recorded-dex-0001",
        observed_at="2026-09-28T09:00:00Z",
        market_cap=2_500_000,
    )
    current_gecko = _observation(
        observation_id="recorded-gecko-0002",
        observed_at="2026-09-28T09:01:30Z",
        provider="GECKOTERMINAL",
        market_cap=2_000_000,
    )
    asyncio.run(store.record(stale_dex))
    asyncio.run(store.record(current_gecko))

    response = client.get(f"/tokens/{TOKEN_ADDRESS}/market-state?as_of=2026-09-28T09:02:00Z")

    assert response.status_code == 200
    document = response.json()
    assert document["current"]["observation_id"] == "recorded-gecko-0002"
    assert document["current"]["coverage"]["provider"] == "GECKOTERMINAL"
    assert document["peaks"]["market_cap_usd"] == {
        "value_usd": 2500000.0,
        "observed_at": "2026-09-28T09:00:00Z",
        "observation_id": "recorded-dex-0001",
        "provider": "DEXSCREENER",
    }
    assert "DEXSCREENER observation is stale at the requested as-of time" in document["warnings"]
    assert [entry["observation_id"] for entry in document["observations"]] == [
        "recorded-dex-0001",
        "recorded-gecko-0002",
    ]


def test_market_state_keeps_unknown_state_explicit_and_rejects_unregistered_tokens() -> None:
    store = InMemoryMarketStateStore()
    client = _client(store)
    _register_token(client)

    response = client.get(f"/tokens/{TOKEN_ADDRESS}/market-state?as_of=2026-09-28T09:02:00Z")

    assert response.status_code == 200
    assert response.json()["current"] is None
    assert response.json()["peaks"] == {"market_cap_usd": None, "liquidity_usd": None}
    assert response.json()["warnings"] == [
        "Market state is UNKNOWN because no observation is recorded"
    ]

    missing = client.get("/tokens/not-registered/market-state?as_of=2026-09-28T09:02:00Z")
    assert missing.status_code == 404
    assert missing.json() == {"detail": "Token not-registered is not registered"}
