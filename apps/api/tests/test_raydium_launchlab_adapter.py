from collections.abc import Callable
from datetime import datetime, timezone
from uuid import UUID

import pytest
from fastapi.testclient import TestClient
from launch_event_contract import (
    assert_launch_event_registration_is_idempotent,
    assert_launch_event_source_contract,
)
from recorded_raydium_launchlab_events import (
    RAYDIUM_MINT_ADDRESS,
    RAYDIUM_POOL_ADDRESS,
    recorded_raydium_launchlab_program_activity,
)

from paper_trade.health import ComponentHealth, HealthComponents, HealthReport
from paper_trade.launch_events import LaunchEventSource
from paper_trade.main import create_app
from paper_trade.raydium_launchlab import RecordedRaydiumLaunchLabSource
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


def _source() -> RecordedRaydiumLaunchLabSource:
    return RecordedRaydiumLaunchLabSource(recorded_raydium_launchlab_program_activity())


def _client() -> TestClient:
    identifiers = iter(UUID(f"00000000-0000-0000-0000-{index:012d}") for index in range(1, 20))
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


SOURCE_FACTORIES: list[tuple[str, Callable[[], LaunchEventSource]]] = [
    ("recorded-raydium-launchlab", _source),
]


@pytest.mark.parametrize(
    ("source_name", "source_factory"),
    SOURCE_FACTORIES,
    ids=[name for name, _ in SOURCE_FACTORIES],
)
async def test_raydium_launchlab_source_satisfies_the_common_provider_contract(
    source_name: str,
    source_factory: Callable[[], LaunchEventSource],
) -> None:
    await assert_launch_event_source_contract(source_factory())
    await assert_launch_event_registration_is_idempotent(
        source_factory(),
        InMemoryTokenStore(),
        InMemoryResearchConfigurationStore(),
    )


async def test_documented_program_activity_normalizes_creation_and_one_migration() -> None:
    source = _source()

    events = await source.launch_events()

    assert [(event.event_id, event.lifecycle_state) for event in events] == [
        ("raydium-launchlab:recorded-raydium-launchlab-create-0001", "NEW"),
        ("raydium-launchlab:recorded-raydium-launchlab-migrate-0002", "MIGRATED"),
    ]
    assert events[0].launch_platform == "RAYDIUM_LAUNCHLAB"
    assert events[0].name == "Recorded Raydium Token"
    assert events[0].symbol == "RRAY"
    assert events[1].has_pool is True
    assert events[1].coverage.unknown_fields == ["name", "symbol"]
    assert events[1].coverage.warnings == [
        f"Raydium LaunchLab migration created pool {RAYDIUM_POOL_ADDRESS}",
        "LaunchLab program data does not include Token metadata",
    ]
    assert all(event.coverage.commitment == "confirmed" for event in events)
    assert source.rejected_record_count == 1


async def test_http_registration_preserves_raydium_provenance_and_migration_without_duplicates() -> (
    None
):
    client = _client()
    creation, migration = await _source().launch_events()

    created = client.post("/tokens", json={"event": creation.model_dump(mode="json")})
    migrated = client.post("/tokens", json={"event": migration.model_dump(mode="json")})
    replayed = client.post("/tokens", json={"event": migration.model_dump(mode="json")})

    assert created.status_code == 201
    assert migrated.status_code == 200
    assert replayed.status_code == 200
    detail = client.get(f"/tokens/{RAYDIUM_MINT_ADDRESS}")
    assert detail.status_code == 200
    document = detail.json()
    assert document["launch_platform"] == "RAYDIUM_LAUNCHLAB"
    assert document["lifecycle_state"] == "MIGRATED"
    assert [transition["state"] for transition in document["lifecycle_transitions"]] == [
        "NEW",
        "MIGRATED",
    ]
    assert len(document["coverage"]) == 2
    assert document["coverage"][1]["provider"] == "raydium-launchlab-program"
    assert document["coverage"][1]["unknown_fields"] == ["name", "symbol"]
