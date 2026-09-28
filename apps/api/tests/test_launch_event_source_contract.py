from collections.abc import Callable

import pytest
from launch_event_contract import (
    assert_launch_event_registration_is_idempotent,
    assert_launch_event_source_contract,
)
from recorded_launch_events import recorded_launch_event_source

from paper_trade.launch_events import LaunchEventSource
from paper_trade.research_configuration import InMemoryResearchConfigurationStore
from paper_trade.tokens import InMemoryTokenStore

SOURCE_FACTORIES: list[tuple[str, Callable[[], LaunchEventSource]]] = [
    ("recorded", recorded_launch_event_source),
]


@pytest.mark.parametrize(
    ("source_name", "source_factory"),
    SOURCE_FACTORIES,
    ids=[name for name, _ in SOURCE_FACTORIES],
)
async def test_launch_event_source_satisfies_the_provider_contract(
    source_name: str,
    source_factory: Callable[[], LaunchEventSource],
) -> None:
    await assert_launch_event_source_contract(source_factory())


@pytest.mark.parametrize(
    ("source_name", "source_factory"),
    SOURCE_FACTORIES,
    ids=[name for name, _ in SOURCE_FACTORIES],
)
async def test_recorded_stream_registration_is_idempotent(
    source_name: str,
    source_factory: Callable[[], LaunchEventSource],
) -> None:
    await assert_launch_event_registration_is_idempotent(
        source_factory(),
        InMemoryTokenStore(),
        InMemoryResearchConfigurationStore(),
    )
