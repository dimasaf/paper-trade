from datetime import datetime, timezone
from uuid import UUID

from fastapi.testclient import TestClient
from recorded_launch_events import (
    recorded_processed_launch_event,
    recorded_pump_fun_launch_event,
    recorded_pump_swap_launch_event,
)

from paper_trade.health import ComponentHealth, HealthComponents, HealthReport
from paper_trade.main import create_app
from paper_trade.research_configuration import InMemoryResearchConfigurationStore
from paper_trade.tokens import InMemoryTokenStore


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


def _configuration_ids() -> list[UUID]:
    return [UUID(f"00000000-0000-0000-0000-{index:012d}") for index in range(1, 20)]


def _client() -> TestClient:
    identifiers = iter(_configuration_ids())
    return TestClient(
        create_app(
            health_service=ReadyHealthService(),
            research_configuration_store=InMemoryResearchConfigurationStore(
                now=lambda: datetime(2026, 9, 28, 9, 0, tzinfo=timezone.utc),
                id_factory=lambda: next(identifiers),
            ),
            token_store=InMemoryTokenStore(),
        )
    )


def test_registering_a_recorded_launch_event_creates_a_token_with_provenance() -> None:
    client = _client()
    event = recorded_pump_swap_launch_event()

    response = client.post("/tokens", json={"event": event.model_dump(mode="json")})

    assert response.status_code == 201
    document = response.json()
    assert document["address"] == "7GCihgDB8fe6KNjn2MYtkzZcRjQy3t9GHdC8uHYmW2hr"
    assert document["name"] == "Recorded Swap Token"
    assert document["symbol"] == "RSWAP"
    assert document["creator"] == "5Q544fKrFoe6tsEbD7S8EmxGTJYAKtTVhAW5Q5pge4j1"
    assert document["created_at"] == "2026-09-28T09:00:00Z"
    assert document["observed_at"] == "2026-09-28T09:00:05Z"
    assert document["launch_platform"] == "PUMP_SWAP"
    assert document["lifecycle_state"] == "NEW"
    assert document["lifecycle_transitions"] == [
        {
            "state": "NEW",
            "observed_at": "2026-09-28T09:00:05Z",
            "source_event_id": "recorded-pumpswap-pool-0001",
            "reason": "launch event registered",
        }
    ]
    assert document["coverage"] == [
        {
            "provider": "recorded-pumpswap",
            "as_of_start": "2026-09-28T09:00:00Z",
            "as_of_end": "2026-09-28T09:05:00Z",
            "complete": True,
            "commitment": "confirmed",
            "unknown_fields": [],
            "warnings": [],
        }
    ]

    detail = client.get("/tokens/7GCihgDB8fe6KNjn2MYtkzZcRjQy3t9GHdC8uHYmW2hr")
    assert detail.status_code == 200
    assert detail.json() == document


def test_classification_records_pass_fail_evidence_for_the_active_configuration() -> None:
    client = _client()
    event = recorded_pump_swap_launch_event()

    document = client.post("/tokens", json={"event": event.model_dump(mode="json")}).json()

    classification = document["classification"]
    assert classification["configuration_id"] == "00000000-0000-0000-0000-000000000001"
    assert classification["configuration_version"] == 1
    assert classification["passed"] is True
    assert classification["criteria"] == [
        {
            "criterion": "launch_source",
            "threshold": ("PUMP_FUN, PUMP_SWAP, RAYDIUM_LAUNCHLAB, METEORA_DBC, JUPITER_STUDIO"),
            "observed": "PUMP_SWAP",
            "passed": True,
        },
        {"criterion": "pool", "threshold": "required", "observed": "present", "passed": True},
        {
            "criterion": "liquidity_usd",
            "threshold": ">= 10000",
            "observed": "52000",
            "passed": True,
        },
        {
            "criterion": "market_cap_usd",
            "threshold": ">= 25000",
            "observed": "120000",
            "passed": True,
        },
        {
            "criterion": "volume_24h_usd",
            "threshold": ">= 10000",
            "observed": "30000",
            "passed": True,
        },
    ]


def test_classification_uses_the_active_configuration_version_and_thresholds() -> None:
    client = _client()
    configuration = client.get("/research-configurations/active").json()["configuration"]
    configuration["token"]["launch_sources"] = ["JUPITER_STUDIO"]
    configuration["token"]["minimum_liquidity_usd"] = 100_000
    created = client.post("/research-configurations", json={"configuration": configuration})
    assert created.status_code == 201

    event = recorded_pump_swap_launch_event()
    document = client.post("/tokens", json={"event": event.model_dump(mode="json")}).json()

    classification = document["classification"]
    assert classification["configuration_id"] == created.json()["id"]
    assert classification["configuration_version"] == 2
    assert classification["passed"] is False
    criteria = {item["criterion"]: item for item in classification["criteria"]}
    assert criteria["launch_source"]["passed"] is False
    assert criteria["launch_source"]["threshold"] == "JUPITER_STUDIO"
    assert criteria["liquidity_usd"] == {
        "criterion": "liquidity_usd",
        "threshold": ">= 100000",
        "observed": "52000",
        "passed": False,
    }


def test_replaying_a_recorded_launch_event_is_idempotent() -> None:
    client = _client()
    event = recorded_pump_swap_launch_event()

    first = client.post("/tokens", json={"event": event.model_dump(mode="json")})
    second = client.post("/tokens", json={"event": event.model_dump(mode="json")})

    assert first.status_code == 201
    assert second.status_code == 200
    assert second.json() == first.json()
    detail = client.get("/tokens/7GCihgDB8fe6KNjn2MYtkzZcRjQy3t9GHdC8uHYmW2hr").json()
    assert len(detail["lifecycle_transitions"]) == 1
    assert len(detail["coverage"]) == 1
    assert len(client.get("/tokens").json()) == 1


def test_processed_launch_events_are_rejected_without_a_token() -> None:
    client = _client()
    event = recorded_processed_launch_event()

    response = client.post("/tokens", json={"event": event.model_dump(mode="json")})

    assert response.status_code == 409
    assert response.json()["detail"] == (
        "Only confirmed launch events can create or transition a Token (ADR-0002)"
    )
    assert client.get("/tokens").json() == []
    assert client.get("/tokens/9BB6NFEcjBCtnNLFko2FqVQBq8HHM13kCyYcdQbgpump").status_code == 404


def test_missing_market_facts_remain_explicit_unknown_with_coverage_warnings() -> None:
    client = _client()
    event = recorded_pump_fun_launch_event()

    document = client.post("/tokens", json={"event": event.model_dump(mode="json")}).json()

    coverage = document["coverage"][0]
    assert coverage["complete"] is False
    assert coverage["unknown_fields"] == [
        "liquidity_usd",
        "market_cap_usd",
        "volume_24h_usd",
    ]
    assert coverage["warnings"] == ["Bonding-curve market facts are not available at creation"]
    criteria = {item["criterion"]: item for item in document["classification"]["criteria"]}
    assert criteria["pool"] == {
        "criterion": "pool",
        "threshold": "required",
        "observed": "absent",
        "passed": False,
    }
    for name in ("liquidity_usd", "market_cap_usd", "volume_24h_usd"):
        assert criteria[name]["observed"] == "UNKNOWN"
        assert criteria[name]["passed"] is False


def test_listing_tokens_returns_every_registered_token_in_order() -> None:
    client = _client()
    for event in (recorded_pump_swap_launch_event(), recorded_pump_fun_launch_event()):
        assert (
            client.post("/tokens", json={"event": event.model_dump(mode="json")}).status_code == 201
        )

    response = client.get("/tokens")

    assert response.status_code == 200
    assert [token["address"] for token in response.json()] == [
        "7GCihgDB8fe6KNjn2MYtkzZcRjQy3t9GHdC8uHYmW2hr",
        "27G8MtK7VtTcCHkpASjSDdkWWYfoqT6ggEuKidVJidD4",
    ]
