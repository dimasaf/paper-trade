"""Recorded Meteora DBC program documents used without network access."""

import json
from pathlib import Path

from paper_trade.meteora_dbc import (
    MeteoraDbcLaunchEventSource,
    MeteoraDbcProgramEvent,
)


def recorded_meteora_dbc_program_events() -> list[MeteoraDbcProgramEvent]:
    fixture = Path(__file__).parent / "fixtures" / "meteora_dbc_events.json"
    return [MeteoraDbcProgramEvent.model_validate(item) for item in json.loads(fixture.read_text())]


def recorded_meteora_dbc_launch_event_source() -> MeteoraDbcLaunchEventSource:
    return MeteoraDbcLaunchEventSource(recorded_meteora_dbc_program_events())
