"""Evidence-backed Wallet relationships, Contributing-independent counts, and HTTP seam."""

import asyncio
from collections.abc import Mapping, Sequence
from datetime import datetime, timedelta, timezone
from typing import Optional

import pytest
from fastapi.testclient import TestClient

from paper_trade.main import create_app
from paper_trade.research_configuration import (
    ClusterSettings,
    InMemoryResearchConfigurationStore,
    ResearchConfiguration,
)
from paper_trade.wallet_accounting import (
    RecordedWalletHistorySource,
    RecordedWalletMovement,
    WalletAccounting,
    WalletAccountingService,
    WalletActivity,
    WalletHistoryCoverage,
)
from paper_trade.wallet_relationships import (
    InMemoryWalletRelationshipStore,
    RecordedWalletFundingSource,
    WalletFundingCoverage,
    WalletFundingEvidence,
    WalletRelationshipService,
)

WALLET_A = "5Q544fKrFoe6tsEbD7S8EmxGTJYAKtTVhAW5Q5pge4j1"
WALLET_B = "4wBqpZM9W7D6h2ZQ5E6o1CymCPG9hrpE7cXkYkKpE8Qm"
WALLET_C = "9BB6NFEcjBCtnNLFko2FqVQBq8HHM13kCyYcdQbgpump"
WALLET_D = "Fz79XcXMRZ5ijyyQ8zZNwJBWXnr7hP3bVM1q4bRDGb7P"
FUNDER = "pAMMBay6oceH9fJKBRHGP5D4bD4sWpmSwMn52FMfXEA"
TOKEN_A = "7GCihgDB8fe6KNjn2MYtkzZcRjQy3t9GHdC8uHYmW2hr"
TOKEN_B = "6EF8rrecthR5Dkzon8Nwu78hRvfCKubJ14M5uBEwF6P"
TOKEN_C = "9xQeWvG816bUx9EPf8aYxGB4pXzv5S1kYQBF3h4r7S1i"
TOKEN_D = "CebN5WGQ4jvEPvsVU4EoHEpgzWSwZyg2ECvZNaaopump"
AS_OF = datetime(2026, 9, 28, 10, 0, tzinfo=timezone.utc)


def at(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def fixed_clock() -> datetime:
    return AS_OF


def movement(
    kind: str, token: str, quantity: float, *, notional: Optional[float] = None
) -> RecordedWalletMovement:
    trade = kind in ("BUY", "SELL")
    return RecordedWalletMovement(
        token_address=token,
        movement_type=kind,
        quantity=quantity,
        notional_usd=notional if trade else None,
        venue="Raydium" if trade else None,
        evidence=[f"recorded {kind} of {quantity:g} units of {token}"],
    )


def activity(
    signature: str, slot: int, chain_time: str, movements: Sequence[RecordedWalletMovement]
) -> WalletActivity:
    return WalletActivity(
        signature=signature,
        slot=slot,
        chain_time=at(chain_time),
        observed_at=at(chain_time),
        succeeded=True,
        fee_usd=0.0,
        movements=list(movements),
    )


def helius_coverage(*, complete: bool = True) -> WalletHistoryCoverage:
    return WalletHistoryCoverage(
        provider="HELIUS",
        requested_as_of=AS_OF,
        as_of_start=AS_OF - timedelta(days=30),
        as_of_end=AS_OF,
        complete=complete,
        freshness_seconds=10,
        commitment="confirmed",
        unknown_fields=[] if complete else ["notional_usd"],
        warnings=[] if complete else ["Recorded Helius coverage is incomplete."],
    )


async def make_accounting(
    address: str,
    activities: Sequence[WalletActivity],
    *,
    coverage: Optional[WalletHistoryCoverage] = None,
) -> WalletAccounting:
    service = WalletAccountingService(
        RecordedWalletHistorySource([list(activities)], coverage or helius_coverage()),
        [],
    )
    return await service.accounting(address, AS_OF)


def funding(
    wallet_address: str,
    funder_address: str,
    signature: str,
    funded_at: str,
    amount_sol: float,
) -> WalletFundingEvidence:
    return WalletFundingEvidence(
        wallet_address=wallet_address,
        funder_address=funder_address,
        signature=signature,
        funded_at=at(funded_at),
        amount_sol=amount_sol,
        evidence=[f"{signature} funded {wallet_address} from {funder_address}"],
    )


def funding_source(
    items: Sequence[WalletFundingEvidence], *, complete: bool = True
) -> RecordedWalletFundingSource:
    return RecordedWalletFundingSource(
        list(items),
        WalletFundingCoverage(
            provider="RECORDED_WALLET_FUNDING",
            requested_as_of=AS_OF,
            as_of_start=AS_OF - timedelta(days=30),
            as_of_end=AS_OF,
            complete=complete,
            unknown_fields=[] if complete else ["funder_address"],
            warnings=[] if complete else ["Recorded funding coverage is incomplete."],
        ),
    )


def related_funding() -> RecordedWalletFundingSource:
    return funding_source(
        [
            funding(WALLET_A, FUNDER, "fund-a", "2026-09-28T08:00:00Z", 1.0),
            funding(WALLET_B, FUNDER, "fund-b", "2026-09-28T08:30:00Z", 1.0),
        ]
    )


def related_activities(wallet: str, offset_seconds: int) -> list[WalletActivity]:
    prefix = "a" if wallet == WALLET_A else "b"
    return [
        activity(
            f"related-{prefix}-buy-1",
            1,
            "2026-09-28T09:00:00Z",
            [movement("BUY", TOKEN_A, 100.0, notional=50.0)],
        ),
        activity(
            f"related-{prefix}-buy-2",
            2,
            "2026-09-28T09:05:00Z",
            [movement("BUY", TOKEN_B, 200.0, notional=80.0)],
        ),
        activity(
            "related-transfer-1",
            3,
            "2026-09-28T09:10:00Z",
            [
                movement(
                    "TRANSFER_OUT" if wallet == WALLET_A else "TRANSFER_IN",
                    TOKEN_C,
                    10.0,
                )
            ],
        ),
    ]


def separate_activities() -> list[WalletActivity]:
    return [
        activity(
            "separate-a-buy-1",
            1,
            "2026-09-28T09:00:00Z",
            [movement("BUY", TOKEN_A, 100.0, notional=50.0)],
        ),
        activity(
            "separate-a-buy-2",
            2,
            "2026-09-28T09:05:00Z",
            [movement("BUY", TOKEN_B, 100.0, notional=50.0)],
        ),
    ]


def separate_peer_activities() -> list[WalletActivity]:
    return [
        activity(
            "separate-c-buy-1",
            1,
            "2026-09-28T07:00:00Z",
            [movement("BUY", TOKEN_C, 100.0, notional=50.0)],
        ),
        activity(
            "separate-c-buy-2",
            2,
            "2026-09-28T07:05:00Z",
            [movement("BUY", TOKEN_D, 100.0, notional=50.0)],
        ),
    ]


def conflicting_peer_activities() -> list[WalletActivity]:
    return [
        activity(
            "conflicting-d-buy-1",
            1,
            "2026-09-28T09:00:30Z",
            [movement("BUY", TOKEN_A, 100.0, notional=50.0)],
        ),
        activity(
            "conflicting-d-buy-2",
            2,
            "2026-09-28T09:06:00Z",
            [movement("BUY", TOKEN_C, 100.0, notional=50.0)],
        ),
    ]


class AccountingStore:
    def __init__(
        self,
        accountings: Mapping[str, WalletAccounting],
        addresses: Optional[Sequence[str]] = None,
    ) -> None:
        self._accountings = dict(accountings)
        self._addresses = sorted(addresses if addresses is not None else accountings)

    async def accounting(self, address: str, as_of: datetime) -> WalletAccounting:
        accounting = self._accountings.get(address)
        if accounting is None:
            raise KeyError(address)
        return accounting

    async def list_wallets(self) -> list[str]:
        return list(self._addresses)


def relationship_service(
    accountings: Mapping[str, WalletAccounting],
    *,
    addresses: Optional[Sequence[str]] = None,
    funding: Optional[RecordedWalletFundingSource] = None,
    configuration_store: Optional[InMemoryResearchConfigurationStore] = None,
    store: Optional[InMemoryWalletRelationshipStore] = None,
) -> WalletRelationshipService:
    return WalletRelationshipService(
        AccountingStore(accountings, addresses),
        funding,
        configuration_store or InMemoryResearchConfigurationStore(now=fixed_clock),
        store or InMemoryWalletRelationshipStore(now=fixed_clock),
    )


def sync_service(
    accountings: Mapping[str, WalletAccounting],
    *,
    addresses: Optional[Sequence[str]] = None,
    funding: Optional[RecordedWalletFundingSource] = None,
) -> WalletRelationshipService:
    return relationship_service(accountings, addresses=addresses, funding=funding)


async def related_service() -> WalletRelationshipService:
    return relationship_service(
        {
            WALLET_A: await make_accounting(WALLET_A, related_activities(WALLET_A, 0)),
            WALLET_B: await make_accounting(WALLET_B, related_activities(WALLET_B, 60)),
        },
        funding=related_funding(),
    )


@pytest.mark.asyncio
async def test_clearly_related_wallets_share_every_evidence_type() -> None:
    service = await related_service()

    relationships = await service.relationships(WALLET_A, AS_OF)

    assert len(relationships.relationships) == 1
    relationship = relationships.relationships[0]
    assert relationship.wallets == sorted([WALLET_A, WALLET_B])
    assert relationship.as_of == AS_OF
    assert relationship.confidence == "HIGH"
    assert {item.evidence_type: item.confidence for item in relationship.evidence} == {
        "COMMON_FUNDING": "HIGH",
        "INTER_WALLET_TRANSFER": "HIGH",
        "SYNCHRONIZED_TRADES": "MEDIUM",
        "TRANSACTION_PATTERN_SIMILARITY": "MEDIUM",
        "SHARED_TOKEN_HISTORY": "LOW",
    }
    assert relationship.unknowns == []
    assert {item.source for item in relationship.coverage} == {
        "HELIUS",
        "RECORDED_WALLET_FUNDING",
    }
    assert all(item.complete for item in relationship.coverage)
    assert "does not establish shared ownership, control, or intent" in relationship.wording
    count = relationships.contributing_independent
    assert count.raw_wallet_count == 2
    assert count.contributing_independent_wallet_count == 1
    assert count.groups[0].wallets == sorted([WALLET_A, WALLET_B])
    assert count.confidence_threshold == "MEDIUM"
    assert count.configuration_version == 1


@pytest.mark.asyncio
async def test_clearly_separate_wallets_produce_no_relationship() -> None:
    service = relationship_service(
        {
            WALLET_A: await make_accounting(WALLET_A, separate_activities()),
            WALLET_C: await make_accounting(WALLET_C, separate_peer_activities()),
        },
        funding=funding_source([]),
    )

    relationships = await service.relationships(WALLET_A, AS_OF)

    assert relationships.relationships == []
    assert relationships.unknowns == []
    count = relationships.contributing_independent
    assert count.raw_wallet_count == 1
    assert count.contributing_independent_wallet_count == 1
    assert count.groups[0].wallets == [WALLET_A]


@pytest.mark.asyncio
async def test_conflicting_evidence_is_reported_without_overstating_relatedness() -> None:
    service = relationship_service(
        {
            WALLET_A: await make_accounting(WALLET_A, separate_activities()),
            WALLET_D: await make_accounting(WALLET_D, conflicting_peer_activities()),
        },
        funding=funding_source([]),
    )

    relationships = await service.relationships(WALLET_A, AS_OF)

    relationship = relationships.relationships[0]
    assert [item.evidence_type for item in relationship.evidence] == ["SYNCHRONIZED_TRADES"]
    assert relationship.confidence == "LOW"
    assert any("COMMON_FUNDING" in unknown for unknown in relationship.unknowns)
    assert "does not establish coordination" in relationship.evidence[0].wording
    count = relationships.contributing_independent
    assert count.raw_wallet_count == 2
    assert count.contributing_independent_wallet_count == 2
    assert count.groups[0].reason.startswith("No recorded relationship reached")


@pytest.mark.asyncio
async def test_configuration_controls_the_collapse_threshold() -> None:
    configuration_store = InMemoryResearchConfigurationStore(now=fixed_clock)
    await configuration_store.create(
        ResearchConfiguration(
            cluster=ClusterSettings(relationship_confidence_threshold="LOW")
        )
    )
    service = relationship_service(
        {
            WALLET_A: await make_accounting(WALLET_A, separate_activities()),
            WALLET_D: await make_accounting(WALLET_D, conflicting_peer_activities()),
        },
        funding=funding_source([]),
        configuration_store=configuration_store,
    )

    relationships = await service.relationships(WALLET_A, AS_OF)

    count = relationships.contributing_independent
    assert count.confidence_threshold == "LOW"
    assert count.configuration_version == 2
    assert count.raw_wallet_count == 2
    assert count.contributing_independent_wallet_count == 1


@pytest.mark.asyncio
async def test_configuration_controls_the_synchronized_trade_window() -> None:
    configuration_store = InMemoryResearchConfigurationStore(now=fixed_clock)
    await configuration_store.create(
        ResearchConfiguration(
            cluster=ClusterSettings(synchronized_trade_window_seconds=10)
        )
    )
    service = relationship_service(
        {
            WALLET_A: await make_accounting(WALLET_A, separate_activities()),
            WALLET_D: await make_accounting(WALLET_D, conflicting_peer_activities()),
        },
        funding=funding_source([]),
        configuration_store=configuration_store,
    )

    relationships = await service.relationships(WALLET_A, AS_OF)

    assert relationships.relationships == []


@pytest.mark.asyncio
async def test_insufficient_evidence_is_reported_as_unknown() -> None:
    service = relationship_service(
        {WALLET_A: await make_accounting(WALLET_A, separate_activities())},
        addresses=[WALLET_A, WALLET_B],
        funding=None,
    )

    relationships = await service.relationships(WALLET_A, AS_OF)

    assert relationships.relationships == []
    assert any("COMMON_FUNDING" in unknown for unknown in relationships.unknowns)
    assert any(WALLET_B in unknown for unknown in relationships.unknowns)
    assert relationships.contributing_independent.raw_wallet_count == 1
    assert relationships.contributing_independent.contributing_independent_wallet_count == 1
    funding_coverage = next(
        item
        for item in relationships.coverage
        if item.source == "UNCONFIGURED_WALLET_FUNDING"
    )
    assert funding_coverage.complete is False
    assert "funder_address" in funding_coverage.unknown_fields


@pytest.mark.asyncio
async def test_contributing_independent_count_collapses_only_strongly_related_wallets() -> None:
    service = relationship_service(
        {
            WALLET_A: await make_accounting(WALLET_A, related_activities(WALLET_A, 0)),
            WALLET_B: await make_accounting(WALLET_B, related_activities(WALLET_B, 60)),
            WALLET_C: await make_accounting(WALLET_C, separate_peer_activities()),
        },
        funding=related_funding(),
    )

    count = await service.contributing_independent(
        [WALLET_A, WALLET_B, WALLET_C], AS_OF
    )

    assert count.raw_wallet_count == 3
    assert count.contributing_independent_wallet_count == 2
    assert count.groups[0].wallets == sorted([WALLET_A, WALLET_B])
    assert count.groups[1].wallets == [WALLET_C]
    assert any("Collapsed group" in item for item in count.evidence)


@pytest.mark.asyncio
async def test_contributing_independent_count_handles_an_empty_wallet_set() -> None:
    service = relationship_service({}, funding=None)

    count = await service.contributing_independent([], AS_OF)

    assert count.raw_wallet_count == 0
    assert count.contributing_independent_wallet_count == 0
    assert count.groups == []
    assert count.evidence == [
        "No Wallets were supplied for the Contributing-independent calculation."
    ]


@pytest.mark.asyncio
async def test_recording_a_relationship_analysis_is_idempotent_and_as_of_scoped() -> None:
    store = InMemoryWalletRelationshipStore(now=fixed_clock)
    service = relationship_service(
        {
            WALLET_A: await make_accounting(WALLET_A, related_activities(WALLET_A, 0)),
            WALLET_B: await make_accounting(WALLET_B, related_activities(WALLET_B, 60)),
        },
        funding=related_funding(),
        store=store,
    )

    first = await service.analyze(WALLET_A, AS_OF)
    second = await service.analyze(WALLET_A, AS_OF)

    assert first.created is True
    assert first.version == 1
    assert second.created is False
    assert second.version == 1
    assert await service.latest(WALLET_A, AS_OF) == first.analysis
    assert await service.latest(WALLET_A, AS_OF - timedelta(hours=1)) is None


def test_relationship_endpoints_compute_record_and_report() -> None:
    accountings = {
        WALLET_A: asyncio.run(make_accounting(WALLET_A, related_activities(WALLET_A, 0))),
        WALLET_B: asyncio.run(make_accounting(WALLET_B, related_activities(WALLET_B, 60))),
    }
    client = TestClient(
        create_app(
            wallet_relationship_service=sync_service(accountings, funding=related_funding())
        )
    )

    response = client.get(f"/wallets/{WALLET_A}/relationships?as_of=2026-09-28T10:00:00Z")

    assert response.status_code == 200
    document = response.json()
    assert document["relationships"][0]["confidence"] == "HIGH"
    assert document["contributing_independent"]["contributing_independent_wallet_count"] == 1

    created = client.post(f"/wallets/{WALLET_A}/relationships?as_of=2026-09-28T10:00:00Z")

    assert created.status_code == 201
    assert created.json()["created"] is True

    repeated = client.post(f"/wallets/{WALLET_A}/relationships?as_of=2026-09-28T10:00:00Z")

    assert repeated.status_code == 200
    assert repeated.json()["created"] is False


def test_relationship_service_composes_from_injected_stores() -> None:
    accountings = {
        WALLET_A: asyncio.run(make_accounting(WALLET_A, related_activities(WALLET_A, 0))),
        WALLET_B: asyncio.run(make_accounting(WALLET_B, related_activities(WALLET_B, 60))),
    }
    client = TestClient(
        create_app(
            wallet_accounting_store=AccountingStore(accountings),
            research_configuration_store=InMemoryResearchConfigurationStore(now=fixed_clock),
            wallet_funding_source=related_funding(),
            wallet_relationship_store=InMemoryWalletRelationshipStore(now=fixed_clock),
        )
    )

    response = client.get(f"/wallets/{WALLET_A}/relationships")

    assert response.status_code == 200
    assert response.json()["address"] == WALLET_A


def test_relationship_endpoints_report_a_wallet_without_recorded_history() -> None:
    accountings = {
        WALLET_A: asyncio.run(make_accounting(WALLET_A, related_activities(WALLET_A, 0))),
        WALLET_B: asyncio.run(make_accounting(WALLET_B, related_activities(WALLET_B, 60))),
    }
    client = TestClient(
        create_app(
            wallet_relationship_service=sync_service(accountings, funding=related_funding())
        )
    )

    response = client.get(f"/wallets/{WALLET_C}/relationships")

    assert response.status_code == 404


def test_relationship_endpoints_return_503_without_a_service() -> None:
    client = TestClient(create_app())

    assert client.get(f"/wallets/{WALLET_A}/relationships").status_code == 503
    assert client.post(f"/wallets/{WALLET_A}/relationships").status_code == 503
