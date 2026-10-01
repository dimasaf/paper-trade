"""Wallet history contract and FIFO accounting behavior through public seams."""

import json
from datetime import datetime
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from paper_trade.main import create_app
from paper_trade.wallet_accounting import (
    InMemoryWalletAccountingStore,
    RecordedWalletHistorySource,
    RecordedWalletMovement,
    WalletAccountingService,
    WalletActivity,
    WalletHistoryCoverage,
    WalletMarkPrice,
)

FIXTURE_PATH = Path(__file__).parent / "fixtures" / "recorded_wallet_history.json"
WALLET = "5Q544fKrFoe6tsEbD7S8EmxGTJYAKtTVhAW5Q5pge4j1"
TOKEN = "7GCihgDB8fe6KNjn2MYtkzZcRjQy3t9GHdC8uHYmW2hr"


def at(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def recorded_source() -> RecordedWalletHistorySource:
    document = json.loads(FIXTURE_PATH.read_text())
    coverage = WalletHistoryCoverage.model_validate(document["coverage"])
    activities = [WalletActivity.model_validate(item) for item in document["activities"]]
    return RecordedWalletHistorySource(pages=[activities], coverage=coverage)


@pytest.mark.asyncio
async def test_recorded_history_contract_keeps_failed_transactions() -> None:
    source = recorded_source()

    history = await source.wallet_history(WALLET, at("2026-09-28T10:00:00Z"))

    assert [activity.signature for activity in history.activities] == [
        "recorded-wallet-buy-0001",
        "recorded-wallet-buy-0002",
        "recorded-wallet-airdrop-0001",
        "recorded-wallet-transfer-in-0001",
        "recorded-wallet-sell-0001",
        "recorded-wallet-transfer-out-0001",
        "recorded-wallet-failed-buy-0001",
        "recorded-wallet-unknown-0001",
    ]
    assert history.coverage.complete is False
    assert history.activities[6].succeeded is False
    assert {
        movement.movement_type for activity in history.activities for movement in activity.movements
    } == {"BUY", "SELL", "TRANSFER_IN", "TRANSFER_OUT", "AIRDROP", "UNKNOWN"}

    duplicate_source = RecordedWalletHistorySource(
        pages=[history.activities, history.activities], coverage=history.coverage
    )
    assert (
        len((await duplicate_source.wallet_history(WALLET, at("2026-09-28T10:00:00Z"))).activities)
        == 8
    )

    earlier = await source.wallet_history(WALLET, at("2026-09-28T09:20:00Z"))
    assert earlier.coverage.requested_as_of == at("2026-09-28T09:20:00Z")
    assert [activity.signature for activity in earlier.activities][
        -1
    ] == "recorded-wallet-transfer-in-0001"


@pytest.mark.asyncio
async def test_recorded_history_contract_excludes_activity_observed_after_as_of() -> None:
    document = json.loads(FIXTURE_PATH.read_text())
    coverage = WalletHistoryCoverage.model_validate(document["coverage"])
    activities = [WalletActivity.model_validate(item) for item in document["activities"]]
    activities.append(
        activities[0].model_copy(
            update={
                "signature": "recorded-wallet-observed-after-as-of-0001",
                "chain_time": at("2026-09-28T09:19:00Z"),
                "observed_at": at("2026-09-28T09:21:00Z"),
            }
        )
    )
    source = RecordedWalletHistorySource(pages=[activities], coverage=coverage)

    history = await source.wallet_history(WALLET, at("2026-09-28T09:20:00Z"))

    assert "recorded-wallet-observed-after-as-of-0001" not in {
        activity.signature for activity in history.activities
    }


@pytest.mark.asyncio
async def test_wallet_accounting_uses_fifo_and_separates_clean_from_airdrop_contamination() -> None:
    source = recorded_source()
    service = WalletAccountingService(
        history_source=source,
        prices=[
            WalletMarkPrice(
                token_address=TOKEN,
                price_usd=5,
                observed_at=at("2026-09-28T09:50:00Z"),
                provider="DEXSCREENER",
            )
        ],
    )

    accounting = await service.accounting(WALLET, at("2026-09-28T10:00:00Z"))

    assert accounting.pnl.inclusive.realized_usd == pytest.approx(21.5)
    assert accounting.pnl.clean.realized_usd == pytest.approx(21.5)
    assert accounting.pnl.inclusive.unrealized_usd == pytest.approx(40.7)
    assert accounting.pnl.clean.unrealized_usd == pytest.approx(5.7)
    assert accounting.pnl.inclusive.total_usd == pytest.approx(62.2)
    assert accounting.pnl.clean.total_usd == pytest.approx(27.2)
    assert accounting.holdings[0].quantity == pytest.approx(10)
    assert accounting.holdings[0].contaminated_quantity == pytest.approx(7)
    assert accounting.failed_transactions[0].signature == "recorded-wallet-failed-buy-0001"
    assert accounting.unknown_movements[0].signature == "recorded-wallet-unknown-0001"
    assert [item.source_signature for item in accounting.contamination] == [
        "recorded-wallet-airdrop-0001",
        "recorded-wallet-transfer-in-0001",
    ]


@pytest.mark.asyncio
async def test_wallet_accounting_applies_repeated_partial_sells_to_one_fifo_lot() -> None:
    coverage = WalletHistoryCoverage(
        provider="HELIUS",
        requested_as_of=at("2026-09-28T10:00:00Z"),
        as_of_start=at("2026-09-28T09:00:00Z"),
        as_of_end=at("2026-09-28T10:00:00Z"),
        complete=True,
        freshness_seconds=0,
        commitment="finalized",
    )
    buy = WalletActivity(
        signature="recorded-repeated-buy",
        slot=1,
        chain_time=at("2026-09-28T09:00:00Z"),
        observed_at=at("2026-09-28T09:00:01Z"),
        succeeded=True,
        fee_usd=1,
        movements=[
            RecordedWalletMovement(
                token_address=TOKEN,
                movement_type="BUY",
                quantity=10,
                notional_usd=20,
                evidence=["recorded Helius SWAP"],
            )
        ],
    )
    first_sell = buy.model_copy(
        update={
            "signature": "recorded-repeated-sell-1",
            "slot": 2,
            "chain_time": at("2026-09-28T09:05:00Z"),
            "fee_usd": 2,
            "movements": [
                RecordedWalletMovement(
                    token_address=TOKEN,
                    movement_type="SELL",
                    quantity=4,
                    notional_usd=20,
                    evidence=["recorded Helius SWAP"],
                )
            ],
        }
    )
    second_sell = buy.model_copy(
        update={
            "signature": "recorded-repeated-sell-2",
            "slot": 3,
            "chain_time": at("2026-09-28T09:10:00Z"),
            "fee_usd": 1,
            "movements": [
                RecordedWalletMovement(
                    token_address=TOKEN,
                    movement_type="SELL",
                    quantity=3,
                    notional_usd=21,
                    evidence=["recorded Helius SWAP"],
                )
            ],
        }
    )
    service = WalletAccountingService(
        RecordedWalletHistorySource([[buy, first_sell, second_sell]], coverage),
        prices=[
            WalletMarkPrice(
                token_address=TOKEN,
                price_usd=5,
                observed_at=at("2026-09-28T09:15:00Z"),
                provider="DEXSCREENER",
            )
        ],
    )

    accounting = await service.accounting(WALLET, at("2026-09-28T10:00:00Z"))

    assert accounting.lots[0].remaining_quantity == pytest.approx(3)
    assert accounting.pnl.clean.realized_usd == pytest.approx(23.3)
    assert accounting.pnl.clean.unrealized_usd == pytest.approx(8.7)


def test_wallet_accounting_endpoint_exposes_source_transactions_lots_pnl_and_coverage() -> None:
    source = recorded_source()
    store = InMemoryWalletAccountingStore(
        WalletAccountingService(
            history_source=source,
            prices=[
                WalletMarkPrice(
                    token_address=TOKEN,
                    price_usd=5,
                    observed_at=at("2026-09-28T09:50:00Z"),
                    provider="DEXSCREENER",
                )
            ],
        )
    )
    client = TestClient(create_app(wallet_accounting_store=store))

    response = client.get(f"/wallets/{WALLET}/accounting", params={"as_of": "2026-09-28T10:00:00Z"})

    assert response.status_code == 200
    document = response.json()
    assert document["address"] == WALLET
    assert document["pnl"]["inclusive"]["total_usd"] == 62.2
    assert document["pnl"]["clean"]["total_usd"] == 27.2
    assert document["lots"][0]["source_signature"] == "recorded-wallet-buy-0001"
    assert document["source_transactions"][6]["succeeded"] is False
    assert document["coverage"][0]["provider"] == "HELIUS"


def test_wallet_accounting_endpoint_returns_unknown_marks_with_explicit_warning() -> None:
    store = InMemoryWalletAccountingStore(
        WalletAccountingService(history_source=recorded_source(), prices=[])
    )
    client = TestClient(create_app(wallet_accounting_store=store))

    response = client.get(f"/wallets/{WALLET}/accounting", params={"as_of": "2026-09-28T10:00:00Z"})

    assert response.status_code == 200
    assert response.json()["pnl"]["inclusive"]["unrealized_usd"] is None
    assert any("mark price is UNKNOWN" in warning for warning in response.json()["warnings"])
