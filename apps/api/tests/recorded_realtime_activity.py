"""Recorded, network-free realtime Wallet activity used by the deterministic suite."""

import json
from datetime import datetime, timezone
from pathlib import Path

from paper_trade.realtime_tracking import (
    RealtimeBatch,
    RecordedRealtimeSource,
    SmartWalletSubscription,
)

FIXTURE = Path(__file__).parent / "fixtures" / "recorded_realtime_activity.json"

SMART_WALLET = "5Q544fKrFoe6tsEbD7S8EmxGTJYAKtTVhAW5Q5pge4j1"
UNSUBSCRIBED_WALLET = "4wBqpZM9W7D6h2ZQ5E6o1CymCPG9hrpE7cXkYkKpE8Qm"
TOKEN = "7GCihgDB8fe6KNjn2MYtkzZcRjQy3t9GHdC8uHYmW2hr"
SMART_WALLET_SCORE = 91.0
AS_OF = datetime(2026, 9, 28, 10, 0, tzinfo=timezone.utc)


def recorded_realtime_batches() -> list[RealtimeBatch]:
    document = json.loads(FIXTURE.read_text())
    return [RealtimeBatch.model_validate(item) for item in document["batches"]]


def recorded_realtime_source() -> RecordedRealtimeSource:
    return RecordedRealtimeSource(recorded_realtime_batches())


def recorded_smart_wallet_subscriptions() -> list[SmartWalletSubscription]:
    return [
        SmartWalletSubscription(address=SMART_WALLET, score=SMART_WALLET_SCORE, as_of=AS_OF)
    ]
