from recorded_meteora_dbc_events import recorded_meteora_dbc_launch_event_source

from paper_trade.research_configuration import InMemoryResearchConfigurationStore
from paper_trade.tokens import InMemoryTokenStore, TokenRegistrationService


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
