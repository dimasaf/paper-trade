from datetime import datetime, timezone
from uuid import UUID

from fastapi.testclient import TestClient
from launch_event_contract import (
    assert_launch_event_registration_is_idempotent,
    assert_launch_event_source_contract,
)
from recorded_meteora_dbc_events import recorded_meteora_dbc_launch_event_source

from paper_trade.health import ComponentHealth, HealthComponents, HealthReport
from paper_trade.main import create_app
from paper_trade.research_configuration import InMemoryResearchConfigurationStore
from paper_trade.tokens import InMemoryTokenStore, TokenRegistrationService


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


async def test_meteora_dbc_normalizes_documented_creation_and_graduation_events() -> None:
    events = await recorded_meteora_dbc_launch_event_source().launch_events()

    meteora_creation, studio_creation, studio_graduation, processed = events

    assert (meteora_creation.launch_platform, meteora_creation.lifecycle_state) == (
        "METEORA_DBC",
        "NEW",
    )
    assert (studio_creation.launch_platform, studio_creation.lifecycle_state) == (
        "JUPITER_STUDIO",
        "NEW",
    )
    assert (studio_graduation.launch_platform, studio_graduation.lifecycle_state) == (
        "JUPITER_STUDIO",
        "MIGRATED",
    )
    assert (
        studio_graduation.graduation_pool_address == "9BB6NFEcjBCtnNLFko2FqVQBq8HHM13kCyYcdQbgpump"
    )
    assert studio_graduation.has_pool is True
    assert studio_graduation.evidence[0].model_dump() == {
        "event_type": "GRADUATE",
        "program_id": "dbcij3LWUppWqq96dh6gJWwBifmcGfLSB5D4DuSMaqN",
        "event_name": "Meteora DBC graduate",
        "bonding_curve": None,
        "bonding_curve_progress_percent": None,
        "pool": "9BB6NFEcjBCtnNLFko2FqVQBq8HHM13kCyYcdQbgpump",
    }
    assert processed.coverage.commitment == "processed"


async def test_jupiter_studio_provenance_and_graduation_survive_out_of_order_replay() -> None:
    source = recorded_meteora_dbc_launch_event_source()
    _, creation, graduation, _ = await source.launch_events()
    store = InMemoryTokenStore()
    service = TokenRegistrationService(
        store=store,
        configuration_store=InMemoryResearchConfigurationStore(),
    )

    for event in (graduation, creation, graduation, creation):
        await service.register_launch_event(event)

    token = await store.get(creation.address)

    assert token is not None
    assert token.launch_platform == "JUPITER_STUDIO"
    assert token.lifecycle_state == "MIGRATED"
    assert [
        (transition.state, transition.source_event_id) for transition in token.lifecycle_transitions
    ] == [
        ("NEW", "recorded-jupiter-studio-create-0002"),
        ("MIGRATED", "recorded-jupiter-studio-graduation-0003"),
    ]
    assert token.lifecycle_transitions[-1].graduation_pool_address == (
        "9BB6NFEcjBCtnNLFko2FqVQBq8HHM13kCyYcdQbgpump"
    )
    assert len(token.coverage) == 2


async def test_meteora_dbc_source_satisfies_the_common_provider_contract() -> None:
    await assert_launch_event_source_contract(recorded_meteora_dbc_launch_event_source())
    await assert_launch_event_registration_is_idempotent(
        recorded_meteora_dbc_launch_event_source(),
        InMemoryTokenStore(),
        InMemoryResearchConfigurationStore(),
    )


async def test_post_tokens_preserves_jupiter_studio_provenance_and_meteora_graduation() -> None:
    client = _client()
    _, creation, graduation, _ = await recorded_meteora_dbc_launch_event_source().launch_events()

    created = client.post("/tokens", json={"event": creation.model_dump(mode="json")})
    migrated = client.post("/tokens", json={"event": graduation.model_dump(mode="json")})
    replayed = client.post("/tokens", json={"event": graduation.model_dump(mode="json")})

    assert created.status_code == 201
    assert migrated.status_code == 200
    assert replayed.status_code == 200
    document = client.get(f"/tokens/{creation.address}").json()
    assert document["launch_platform"] == "JUPITER_STUDIO"
    assert document["lifecycle_state"] == "MIGRATED"
    assert document["lifecycle_transitions"][1]["graduation_pool_address"] == (
        "9BB6NFEcjBCtnNLFko2FqVQBq8HHM13kCyYcdQbgpump"
    )
    assert document["lifecycle_transitions"][1]["evidence"][0]["program_id"] == (
        "dbcij3LWUppWqq96dh6gJWwBifmcGfLSB5D4DuSMaqN"
    )
