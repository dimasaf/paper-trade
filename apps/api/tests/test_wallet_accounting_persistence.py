"""Recorded Wallet-accounting persistence through its public contracts."""

import json
from datetime import datetime
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from paper_trade.main import create_app
from paper_trade.wallet_accounting import (
    InMemoryRecordedWalletAccountingStore,
    RecordWalletAccountingRequest,
    WalletActivity,
    WalletHistory,
    WalletHistoryCoverage,
    WalletMarkPrice,
)

FIXTURE_PATH = Path(__file__).parent / "fixtures" / "recorded_wallet_history.json"
WALLET = "5Q544fKrFoe6tsEbD7S8EmxGTJYAKtTVhAW5Q5pge4j1"
TOKEN = "7GCihgDB8fe6KNjn2MYtkzZcRjQy3t9GHdC8uHYmW2hr"


def at(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def recorded_request() -> RecordWalletAccountingRequest:
    document = json.loads(FIXTURE_PATH.read_text())
    return RecordWalletAccountingRequest(
        history=WalletHistory(
            address=WALLET,
            activities=[WalletActivity.model_validate(item) for item in document["activities"]],
            coverage=WalletHistoryCoverage.model_validate(document["coverage"]),
        ),
        mark_prices=[
            WalletMarkPrice(
                token_address=TOKEN,
                price_usd=5,
                observed_at=at("2026-09-28T09:50:00Z"),
                provider="DEXSCREENER",
            )
        ],
    )


@pytest.mark.asyncio
async def test_recorded_accounting_contract_persists_idempotently_and_isolates_as_of() -> None:
    store = InMemoryRecordedWalletAccountingStore()
    request = recorded_request()

    created = await store.record(request)
    replayed = await store.record(request)
    earlier = await store.accounting(WALLET, at("2026-09-28T09:20:00Z"))
    later = await store.accounting(WALLET, at("2026-09-28T10:00:00Z"))

    assert created.created is True
    assert created.activities_recorded == 8
    assert replayed.created is False
    assert replayed.activities_recorded == 0
    assert [activity.signature for activity in earlier.source_transactions] == [
        "recorded-wallet-buy-0001",
        "recorded-wallet-buy-0002",
        "recorded-wallet-airdrop-0001",
        "recorded-wallet-transfer-in-0001",
    ]
    assert earlier.mark_price_provenance == []
    assert later.pnl.clean.total_usd == pytest.approx(27.2)


def test_recorded_accounting_ingestion_and_detail_http_contract() -> None:
    client = TestClient(create_app(wallet_accounting_store=InMemoryRecordedWalletAccountingStore()))
    request = recorded_request()

    created = client.post(
        f"/wallets/{WALLET}/accounting/recordings", json=request.model_dump(mode="json")
    )
    replayed = client.post(
        f"/wallets/{WALLET}/accounting/recordings", json=request.model_dump(mode="json")
    )
    detail = client.get(f"/wallets/{WALLET}/accounting?as_of=2026-09-28T10:00:00Z")

    assert created.status_code == 201
    assert created.json()["activities_recorded"] == 8
    assert replayed.status_code == 200
    assert replayed.json()["created"] is False
    assert detail.status_code == 200
    assert detail.json()["pnl"]["clean"]["total_usd"] == 27.2


def test_recorded_accounting_detail_http_contract_excludes_activity_observed_after_as_of() -> None:
    client = TestClient(create_app(wallet_accounting_store=InMemoryRecordedWalletAccountingStore()))
    request = recorded_request()
    delayed_activity = request.history.activities[0].model_copy(
        update={
            "signature": "recorded-wallet-observed-after-as-of-0001",
            "chain_time": at("2026-09-28T09:19:00Z"),
            "observed_at": at("2026-09-28T09:21:00Z"),
        }
    )
    request = request.model_copy(
        update={
            "history": request.history.model_copy(
                update={"activities": [*request.history.activities, delayed_activity]}
            )
        }
    )

    created = client.post(
        f"/wallets/{WALLET}/accounting/recordings", json=request.model_dump(mode="json")
    )
    detail = client.get(f"/wallets/{WALLET}/accounting?as_of=2026-09-28T09:20:00Z")

    assert created.status_code == 201
    assert detail.status_code == 200
    assert "recorded-wallet-observed-after-as-of-0001" not in {
        activity["signature"] for activity in detail.json()["source_transactions"]
    }
