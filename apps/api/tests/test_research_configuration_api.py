from datetime import datetime, timezone
from uuid import UUID

import pytest
from fastapi.testclient import TestClient

from paper_trade.health import ComponentHealth, HealthComponents, HealthReport
from paper_trade.main import create_app
from paper_trade.research_configuration import InMemoryResearchConfigurationStore


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


def test_fresh_installation_exposes_a_complete_default_research_configuration() -> None:
    store = InMemoryResearchConfigurationStore(
        now=lambda: datetime(2026, 9, 28, 9, 0, tzinfo=timezone.utc),
        id_factory=lambda: UUID("00000000-0000-0000-0000-000000000001"),
    )
    client = TestClient(
        create_app(
            health_service=ReadyHealthService(),
            research_configuration_store=store,
        )
    )

    response = client.get("/research-configurations/active")

    assert response.status_code == 200
    document = response.json()
    assert document["id"] == "00000000-0000-0000-0000-000000000001"
    assert document["version"] == 1
    assert document["created_at"] == "2026-09-28T09:00:00Z"
    assert set(document["configuration"]) == {
        "token",
        "wallet",
        "cluster",
        "signal",
        "paper_trading",
        "risk",
        "execution",
    }
    assert document["configuration"]["wallet"]["copyability_delays_ms"] == [
        500,
        1000,
        2000,
        3000,
        5000,
        10000,
    ]
    assert document["configuration"]["wallet"]["copyability_sizes_sol"] == [
        0.1,
        0.25,
        0.5,
        1.0,
        2.0,
    ]


def test_saving_creates_an_immutable_version_and_preserves_history() -> None:
    ids = iter(
        [
            UUID("00000000-0000-0000-0000-000000000001"),
            UUID("00000000-0000-0000-0000-000000000002"),
        ]
    )
    store = InMemoryResearchConfigurationStore(
        now=lambda: datetime(2026, 9, 28, 9, 15, tzinfo=timezone.utc),
        id_factory=lambda: next(ids),
    )
    client = TestClient(
        create_app(
            health_service=ReadyHealthService(),
            research_configuration_store=store,
        )
    )
    original = client.get("/research-configurations/active").json()
    changed = original["configuration"]
    changed["cluster"]["minimum_contributing_independent_wallets"] = 4

    create_response = client.post("/research-configurations", json={"configuration": changed})
    history_response = client.get("/research-configurations")

    assert create_response.status_code == 201
    assert create_response.json()["id"] == "00000000-0000-0000-0000-000000000002"
    assert create_response.json()["version"] == 2
    assert (
        create_response.json()["configuration"]["cluster"][
            "minimum_contributing_independent_wallets"
        ]
        == 4
    )
    assert history_response.status_code == 200
    history = history_response.json()
    assert [item["version"] for item in history] == [2, 1]
    assert history[1]["configuration"]["cluster"]["minimum_contributing_independent_wallets"] == 3
    assert client.get("/research-configurations/active").json()["version"] == 2
    historical = client.get("/research-configurations/1")
    assert historical.status_code == 200
    assert historical.json()["id"] == "00000000-0000-0000-0000-000000000001"


def test_saving_rejects_incompatible_ranges_with_an_actionable_message() -> None:
    store = InMemoryResearchConfigurationStore()
    client = TestClient(
        create_app(
            health_service=ReadyHealthService(),
            research_configuration_store=store,
        )
    )
    changed = client.get("/research-configurations/active").json()["configuration"]
    changed["paper_trading"]["position_size_percent"] = 5
    changed["paper_trading"]["maximum_position_percent"] = 3

    response = client.post("/research-configurations", json={"configuration": changed})

    assert response.status_code == 422
    assert response.json()["detail"][0]["msg"] == (
        "Value error, position_size_percent must not exceed maximum_position_percent"
    )
    assert client.get("/research-configurations").json()[0]["version"] == 1


@pytest.mark.parametrize(
    ("case", "message"),
    [
        ("wallet_weights", "wallet score weights must total 100"),
        ("signal_thresholds", "watch_score must be lower than paper_buy_score"),
        (
            "winner_market_caps",
            "winner_initial_market_cap_min_usd must be lower than "
            "winner_initial_market_cap_max_usd",
        ),
        ("partial_exits", "partial take-profit sell percentages must not exceed 100"),
        ("launch_sources", "List should have at least 1 item after validation"),
        ("market_cap_buckets", "entry_market_cap_buckets_usd must be strictly increasing"),
        ("copyability_delays", "Input should be greater than 0"),
        ("copyability_sizes", "copyability_sizes_sol must not contain duplicates"),
    ],
)
def test_saving_rejects_incompatible_domain_assumptions(case: str, message: str) -> None:
    store = InMemoryResearchConfigurationStore()
    client = TestClient(
        create_app(
            health_service=ReadyHealthService(),
            research_configuration_store=store,
        )
    )
    changed = client.get("/research-configurations/active").json()["configuration"]
    if case == "wallet_weights":
        changed["wallet"]["score_weights"]["profitability"] = 21
    elif case == "signal_thresholds":
        changed["signal"]["watch_score"] = 90
    elif case == "winner_market_caps":
        changed["token"]["winner_initial_market_cap_min_usd"] = 600_000
    elif case == "partial_exits":
        changed["risk"]["partial_take_profits"][0]["sell_percent"] = 75
    elif case == "launch_sources":
        changed["token"]["launch_sources"] = []
    elif case == "market_cap_buckets":
        changed["token"]["entry_market_cap_buckets_usd"] = [100_000, 50_000]
    elif case == "copyability_delays":
        changed["wallet"]["copyability_delays_ms"] = [-1]
    else:
        changed["wallet"]["copyability_sizes_sol"] = [0.5, 0.5]

    response = client.post("/research-configurations", json={"configuration": changed})

    assert response.status_code == 422
    assert message in response.json()["detail"][0]["msg"]
