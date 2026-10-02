"""Smart Wallet Clusters: thresholds, related Wallets, updates, and invalidation."""

import asyncio
from collections.abc import Mapping, Sequence
from datetime import datetime, timedelta, timezone
from typing import Optional

import pytest
from fastapi.testclient import TestClient

from paper_trade.main import create_app
from paper_trade.realtime_tracking import RealtimeCoverage
from paper_trade.research_configuration import (
    ClusterSettings,
    InMemoryResearchConfigurationStore,
    ResearchConfiguration,
)
from paper_trade.wallet_clusters import (
    ClusterActivity,
    ClusterDetectorService,
    InMemoryWalletClusterStore,
    RecordedClusterActivitySource,
)
from paper_trade.wallet_relationships import (
    ContributingIndependentCount,
    ContributingIndependentGroup,
)

TOKEN_A = "7GCihgDB8fe6KNjn2MYtkzZcRjQy3t9GHdC8uHYmW2hr"
TOKEN_B = "6EF8rrecthR5Dkzon8Nwu78hRvfCKubJ14M5uBEwF6P"
WALLET_A = "5Q544fKrFoe6tsEbD7S8EmxGTJYAKtTVhAW5Q5pge4j1"
WALLET_B = "4wBqpZM9W7D6h2ZQ5E6o1CymCPG9hrpE7cXkYkKpE8Qm"
WALLET_C = "9BB6NFEcjBCtnNLFko2FqVQBq8HHM13kCyYcdQbgpump"
WALLET_D = "Fz79XcXMRZ5ijyyQ8zZNwJBWXnr7hP3bVM1q4bRDGb7P"
WALLET_E = "CebN5WGQ4jvEPvsVU4EoHEpgzWSwZyg2ECvZNaaopump"
AS_OF = datetime(2026, 9, 28, 10, 0, tzinfo=timezone.utc)
AS_OF_QUERY = "2026-09-28T10:00:00Z"


def at(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def fixed_clock() -> datetime:
    return AS_OF


def coverage(
    *,
    commitment: str = "confirmed",
    complete: bool = True,
    unknown_fields: Optional[list[str]] = None,
) -> RealtimeCoverage:
    fields = list(unknown_fields or [])
    return RealtimeCoverage(
        provider="recorded-cluster-activity",
        as_of_start=AS_OF - timedelta(minutes=5),
        as_of_end=AS_OF + timedelta(minutes=1),
        complete=complete,
        commitment=commitment,  # type: ignore[arg-type]
        freshness_seconds=2,
        normalization_version="cluster/v1",
        unknown_fields=fields,
        warnings=[] if not fields else ["Recorded cluster coverage is incomplete."],
    )


def activity(
    wallet: str,
    token: str,
    *,
    signature: str,
    slot: int,
    chain_time: str,
    sol: float = 1.0,
    score: Optional[float] = 90.0,
    notional: Optional[float] = 100.0,
    movement: str = "BUY",
    commitment: str = "confirmed",
) -> ClusterActivity:
    unknown_fields = [] if notional is not None else ["notional_usd"]
    return ClusterActivity(
        event_id=signature,
        wallet_address=wallet,
        token_address=token,
        movement_type=movement,  # type: ignore[arg-type]
        quantity=10.0,
        sol_amount=sol,
        notional_usd=notional,
        wallet_score=score,
        score_as_of=None if score is None else at(chain_time),
        signature=signature,
        slot=slot,
        chain_time=at(chain_time),
        observed_at=at(chain_time),
        commitment=commitment,  # type: ignore[arg-type]
        eligible_for_decisions=commitment == "confirmed",
        evidence=[f"recorded {movement} of {token} by {wallet}"],
        coverage=coverage(
            commitment=commitment,
            complete=not unknown_fields,
            unknown_fields=unknown_fields,
        ),
    )


class GroupingCalculator:
    """Collapse Wallets listed together into one Contributing-independent group."""

    def __init__(self, *, merges: Sequence[Sequence[str]] = ()) -> None:
        self._merges = [list(group) for group in merges]

    async def contributing_independent(
        self, wallets: Sequence[str], as_of: datetime
    ) -> ContributingIndependentCount:
        unique = sorted(set(wallets))
        parent = {wallet: wallet for wallet in unique}

        def find(wallet: str) -> str:
            root = wallet
            while parent[root] != root:
                root = parent[root]
            return root

        for group in self._merges:
            members = [wallet for wallet in group if wallet in parent]
            for member in members[1:]:
                parent[find(member)] = find(members[0])
        collapsed: dict[str, list[str]] = {}
        for wallet in unique:
            collapsed.setdefault(find(wallet), []).append(wallet)
        groups = [
            ContributingIndependentGroup(
                wallets=sorted(members),
                representative=sorted(members)[0],
                reason=(
                    "These Wallets are connected by recorded relationship evidence."
                    if len(members) > 1
                    else "No recorded relationship reached the configured threshold."
                ),
            )
            for members in sorted(collapsed.values(), key=lambda members: members[0])
        ]
        return ContributingIndependentCount(
            raw_wallet_count=len(unique),
            contributing_independent_wallet_count=len(groups),
            groups=groups,
            as_of=as_of,
            configuration_id="00000000-0000-0000-0000-000000000001",
            configuration_version=1,
            confidence_threshold="MEDIUM",
            evidence=[
                f"{len(unique)} recorded Wallet(s) collapse to {len(groups)}."
            ],
            unknowns=[],
        )


def three_wallet_buys(
    *,
    token: str = TOKEN_A,
    start: str = "2026-09-28T09:56:00Z",
    scores: Sequence[Optional[float]] = (85.0, 90.0, 95.0),
    sols: Sequence[float] = (1.0, 2.0, 3.0),
) -> list[ClusterActivity]:
    wallets = (WALLET_A, WALLET_B, WALLET_C)
    return [
        activity(
            wallet,
            token,
            signature=f"cluster-{wallet}",
            slot=index + 1,
            chain_time=start,
            sol=sols[index],
            score=scores[index],
        )
        for index, wallet in enumerate(wallets)
    ]


async def configured(**cluster: object) -> InMemoryResearchConfigurationStore:
    store = InMemoryResearchConfigurationStore(now=fixed_clock)
    if cluster:
        await store.create(ResearchConfiguration(cluster=ClusterSettings(**cluster)))
    return store


def service(
    activities: Sequence[ClusterActivity],
    *,
    configuration_store: InMemoryResearchConfigurationStore,
    merges: Sequence[Sequence[str]] = (),
    store: Optional[InMemoryWalletClusterStore] = None,
) -> ClusterDetectorService:
    return ClusterDetectorService(
        RecordedClusterActivitySource(activities),
        GroupingCalculator(merges=merges),
        configuration_store,
        store or InMemoryWalletClusterStore(now=fixed_clock),
    )


async def test_two_wallets_below_the_minimum_form_no_cluster() -> None:
    detector = service(
        three_wallet_buys()[:2],
        configuration_store=await configured(minimum_contributing_independent_wallets=3),
    )

    detection = await detector.detect(AS_OF)

    assert detection.created_clusters == 0
    assert detection.recorded == 2
    assert await detector.live(AS_OF) == []


async def test_three_independent_wallets_form_a_cluster() -> None:
    detector = service(
        three_wallet_buys(),
        configuration_store=await configured(minimum_contributing_independent_wallets=3),
    )

    detection = await detector.detect(AS_OF)

    assert detection.created_clusters == 1
    cluster = detection.clusters[0].cluster
    assert cluster.status == "ACTIVE"
    assert cluster.token_address == TOKEN_A
    assert cluster.raw_wallet_count == 3
    assert cluster.contributing_independent_wallet_count == 3
    assert cluster.average_wallet_score == 90
    assert cluster.weighted_wallet_score == pytest.approx(90.1852)
    assert cluster.total_sol == 6
    assert cluster.total_notional_usd == 300
    assert cluster.buy_count == 3
    assert cluster.first_buy_at == at("2026-09-28T09:56:00Z")
    assert cluster.last_buy_at == at("2026-09-28T09:56:00Z")
    assert cluster.window_span_seconds == 0
    assert cluster.buy_velocity_per_minute is None
    assert cluster.window_seconds == 300
    assert cluster.score_weighting == "WALLET_SCORE"
    assert cluster.configuration_version == 2
    assert {item.source for item in cluster.coverage} == {"recorded-cluster-activity"}
    assert cluster.unknowns == []
    assert len(cluster.contributing_independent.groups) == 3
    assert await detector.live(AS_OF) == [detection.clusters[0]]


async def test_related_wallets_collapse_the_contributing_independent_count() -> None:
    detector = service(
        three_wallet_buys(),
        configuration_store=await configured(minimum_contributing_independent_wallets=2),
        merges=[(WALLET_A, WALLET_B)],
    )

    detection = await detector.detect(AS_OF)

    cluster = detection.clusters[0].cluster
    assert cluster.status == "ACTIVE"
    assert cluster.raw_wallet_count == 3
    assert cluster.contributing_independent_wallet_count == 2
    merged = next(
        group
        for group in cluster.contributing_independent.groups
        if len(group.wallets) == 2
    )
    assert merged.wallets == sorted([WALLET_A, WALLET_B])
    independence = {
        contribution.wallet_address: contribution.independent
        for contribution in cluster.wallets
    }
    assert independence[merged.representative] is True
    assert independence[WALLET_C] is True
    assert sum(1 for value in independence.values() if value) == 2


async def test_quality_and_activity_threshold_edges() -> None:
    below_score = service(
        three_wallet_buys(scores=(79.0, 79.0, 79.0)),
        configuration_store=await configured(
            minimum_contributing_independent_wallets=3,
            minimum_average_wallet_score=80,
        ),
    )
    at_score = service(
        three_wallet_buys(scores=(80.0, 80.0, 80.0)),
        configuration_store=await configured(
            minimum_contributing_independent_wallets=3,
            minimum_average_wallet_score=80,
        ),
    )
    below_sol = service(
        three_wallet_buys(sols=(1.0, 1.0, 1.0)),
        configuration_store=await configured(
            minimum_contributing_independent_wallets=3,
            minimum_total_sol=4,
        ),
    )
    at_sol = service(
        three_wallet_buys(sols=(2.0, 1.0, 1.0)),
        configuration_store=await configured(
            minimum_contributing_independent_wallets=3,
            minimum_total_sol=4,
        ),
    )

    assert (await below_score.detect(AS_OF)).created_clusters == 0
    assert (await at_score.detect(AS_OF)).created_clusters == 1
    assert (await below_sol.detect(AS_OF)).created_clusters == 0
    assert (await at_sol.detect(AS_OF)).created_clusters == 1


async def test_unknown_wallet_quality_never_becomes_a_safe_cluster() -> None:
    detector = service(
        three_wallet_buys(scores=(85.0, 90.0, None)),
        configuration_store=await configured(minimum_contributing_independent_wallets=3),
    )

    detection = await detector.detect(AS_OF)

    assert detection.created_clusters == 0
    assert await detector.live(AS_OF) == []


async def test_out_of_window_activity_does_not_change_the_cluster() -> None:
    store = InMemoryWalletClusterStore(now=fixed_clock)
    detector = service(
        three_wallet_buys(),
        configuration_store=await configured(minimum_contributing_independent_wallets=3),
        store=store,
    )
    first = await detector.detect(AS_OF)

    detection = await detector.observe(
        [
            activity(
                WALLET_D,
                TOKEN_A,
                signature="cluster-out-of-window",
                slot=99,
                chain_time="2026-09-28T09:00:00Z",
                sol=5.0,
                score=99.0,
            )
        ],
        AS_OF,
    )

    assert detection.recorded == 1
    assert detection.duplicates == 0
    assert detection.created_clusters == 0
    assert detection.updated_clusters == 0
    assert detection.unchanged_clusters == 1
    current = await detector.detail(TOKEN_A, AS_OF)
    assert current is not None
    cluster = current.current.cluster
    assert cluster.buy_count == 3
    assert cluster.total_sol == 6
    assert cluster.contributing_independent_wallet_count == 3
    assert current.current.version == first.clusters[0].version


async def test_duplicate_activity_cannot_inflate_counts_or_volume() -> None:
    store = InMemoryWalletClusterStore(now=fixed_clock)
    detector = service(
        three_wallet_buys(),
        configuration_store=await configured(minimum_contributing_independent_wallets=3),
        store=store,
    )
    first = await detector.detect(AS_OF)

    detection = await detector.detect(AS_OF)

    assert detection.recorded == 0
    assert detection.duplicates == 3
    assert detection.unchanged_clusters == 1
    current = await detector.detail(TOKEN_A, AS_OF)
    assert current is not None
    assert current.current.version == first.clusters[0].version
    assert current.current.cluster.buy_count == 3
    assert current.current.cluster.total_sol == 6


async def test_new_activity_supersedes_the_existing_cluster() -> None:
    store = InMemoryWalletClusterStore(now=fixed_clock)
    detector = service(
        three_wallet_buys(),
        configuration_store=await configured(minimum_contributing_independent_wallets=3),
        store=store,
    )
    first = await detector.detect(AS_OF)

    detection = await detector.observe(
        [
            activity(
                WALLET_D,
                TOKEN_A,
                signature="cluster-wallet-d",
                slot=50,
                chain_time="2026-09-28T09:58:00Z",
                sol=4.0,
                score=90.0,
            )
        ],
        AS_OF,
    )

    assert detection.updated_clusters == 1
    assert detection.created_clusters == 0
    detail = await detector.detail(TOKEN_A, AS_OF)
    assert detail is not None
    assert len(detail.history) == 2
    assert detail.current.version == 2
    assert detail.current.cluster.status == "ACTIVE"
    assert detail.current.cluster.raw_wallet_count == 4
    assert detail.current.cluster.total_sol == 10
    superseded = detail.history[1]
    assert superseded.version == first.clusters[0].version == 1
    assert superseded.cluster.status == "SUPERSEDED"
    assert superseded.cluster.superseded_by_version == 2
    assert "Materially changed evidence" in superseded.cluster.status_reason


async def test_expired_cluster_is_invalidated() -> None:
    store = InMemoryWalletClusterStore(now=fixed_clock)
    detector = service(
        three_wallet_buys(),
        configuration_store=await configured(minimum_contributing_independent_wallets=3),
        store=store,
    )
    await detector.detect(AS_OF)

    later = AS_OF + timedelta(minutes=10)
    detection = await detector.observe([], later)

    assert detection.invalidated_clusters == 1
    detail = await detector.detail(TOKEN_A, later)
    assert detail is not None
    assert detail.current.cluster.status == "INVALIDATED"
    assert detail.current.cluster.status_reason.startswith("EXPIRED:")
    assert await detector.live(later) == []


async def test_threshold_loss_invalidates_an_existing_cluster() -> None:
    store = InMemoryWalletClusterStore(now=fixed_clock)
    configuration_store = await configured(minimum_contributing_independent_wallets=3)
    detector = ClusterDetectorService(
        RecordedClusterActivitySource(three_wallet_buys()),
        GroupingCalculator(),
        configuration_store,
        store,
    )
    await detector.detect(AS_OF)

    related = ClusterDetectorService(
        RecordedClusterActivitySource([]),
        GroupingCalculator(merges=[(WALLET_A, WALLET_B)]),
        configuration_store,
        store,
    )
    detection = await related.observe(
        [
            activity(
                WALLET_A,
                TOKEN_A,
                signature="cluster-recheck",
                slot=7,
                chain_time="2026-09-28T09:59:00Z",
            )
        ],
        AS_OF,
    )

    assert detection.invalidated_clusters == 1
    detail = await related.detail(TOKEN_A, AS_OF)
    assert detail is not None
    assert detail.current.cluster.status == "INVALIDATED"
    assert detail.current.cluster.status_reason.startswith("THRESHOLD_LOST:")


async def test_processed_activity_is_recorded_but_never_forms_a_cluster() -> None:
    detector = service(
        [
            activity(
                WALLET_A,
                TOKEN_A,
                signature="cluster-processed",
                slot=1,
                chain_time="2026-09-28T09:58:00Z",
                commitment="processed",
            )
        ],
        configuration_store=await configured(minimum_contributing_independent_wallets=2),
    )

    detection = await detector.detect(AS_OF)

    assert detection.recorded == 1
    assert detection.created_clusters == 0
    assert await detector.live(AS_OF) == []


async def test_score_weighting_is_configurable() -> None:
    equal = service(
        three_wallet_buys(scores=(60.0, 90.0, 90.0), sols=(1.0, 0.1, 0.1)),
        configuration_store=await configured(
            minimum_contributing_independent_wallets=3,
            score_weighting="EQUAL",
        ),
    )
    by_sol = service(
        three_wallet_buys(scores=(60.0, 90.0, 90.0), sols=(1.0, 0.1, 0.1)),
        configuration_store=await configured(
            minimum_contributing_independent_wallets=3,
            score_weighting="TOTAL_SOL",
        ),
    )

    equal_cluster = (await equal.detect(AS_OF)).clusters[0].cluster
    sol_cluster = (await by_sol.detect(AS_OF)).clusters[0].cluster
    assert equal_cluster.average_wallet_score == 80
    assert equal_cluster.weighted_wallet_score == 80
    assert sol_cluster.weighted_wallet_score is not None
    assert sol_cluster.weighted_wallet_score < equal_cluster.weighted_wallet_score


async def test_two_tokens_produce_two_clusters() -> None:
    detector = service(
        three_wallet_buys() + three_wallet_buys(token=TOKEN_B, start="2026-09-28T09:57:00Z"),
        configuration_store=await configured(minimum_contributing_independent_wallets=3),
    )

    detection = await detector.detect(AS_OF)

    assert detection.created_clusters == 2
    assert {stored.cluster.token_address for stored in await detector.live(AS_OF)} == {
        TOKEN_A,
        TOKEN_B,
    }


def test_cluster_http_contract() -> None:
    configuration_store = asyncio.run(configured(minimum_contributing_independent_wallets=3))
    client = TestClient(
        create_app(
            cluster_detector_service=service(
                three_wallet_buys(), configuration_store=configuration_store
            )
        )
    )

    detection = client.post(f"/clusters/detections?as_of={AS_OF_QUERY}")
    live = client.get(f"/clusters?as_of={AS_OF_QUERY}")
    detail = client.get(f"/clusters/{TOKEN_A}?as_of={AS_OF_QUERY}")
    history = client.get(f"/clusters/{TOKEN_A}/history?as_of={AS_OF_QUERY}")
    missing = client.get(f"/clusters/{TOKEN_B}?as_of={AS_OF_QUERY}")

    assert detection.status_code == 201
    assert detection.json()["created_clusters"] == 1
    assert live.status_code == 200
    assert len(live.json()) == 1
    assert live.json()[0]["cluster"]["token_address"] == TOKEN_A
    assert detail.status_code == 200
    assert detail.json()["current"]["cluster"]["contributing_independent_wallet_count"] == 3
    assert detail.json()["current"]["cluster"]["status"] == "ACTIVE"
    assert history.status_code == 200
    assert len(history.json()) == 1
    assert missing.status_code == 404


def test_cluster_endpoints_return_503_when_unavailable() -> None:
    client = TestClient(create_app())

    assert client.post("/clusters/detections").status_code == 503
    assert client.get("/clusters").status_code == 503
    assert client.get(f"/clusters/{TOKEN_A}").status_code == 503
    assert client.get(f"/clusters/{TOKEN_A}/history").status_code == 503


def test_cluster_service_composes_from_injected_stores() -> None:
    configuration_store = asyncio.run(configured(minimum_contributing_independent_wallets=3))
    client = TestClient(
        create_app(
            cluster_activity_source=RecordedClusterActivitySource(three_wallet_buys()),
            cluster_relationship_calculator=GroupingCalculator(),
            wallet_cluster_store=InMemoryWalletClusterStore(now=fixed_clock),
            research_configuration_store=configuration_store,
        )
    )

    assert client.post(f"/clusters/detections?as_of={AS_OF_QUERY}").status_code == 201
    response = client.get(f"/clusters/{TOKEN_A}?as_of={AS_OF_QUERY}")

    assert response.status_code == 200
    assert response.json()["current"]["cluster"]["raw_wallet_count"] == 3


def test_in_memory_store_conflicting_activity_is_rejected() -> None:
    store = InMemoryWalletClusterStore(now=fixed_clock)
    first = activity(
        WALLET_A, TOKEN_A, signature="cluster-conflict", slot=1, chain_time="2026-09-28T09:58:00Z"
    )
    conflicting = first.model_copy(update={"sol_amount": 99.0})

    async def run() -> None:
        await store.record_activity(first)
        with pytest.raises(ValueError):
            await store.record_activity(conflicting)

    asyncio.run(run())


def test_configuration_store_round_trips_cluster_settings() -> None:
    store = InMemoryResearchConfigurationStore(now=fixed_clock)

    async def run() -> Mapping[str, object]:
        created = await store.create(
            ResearchConfiguration(
                cluster=ClusterSettings(
                    minimum_contributing_independent_wallets=4,
                    window_seconds=120,
                    score_weighting="TOTAL_SOL",
                    minimum_buy_count=2,
                    minimum_total_sol=5,
                )
            )
        )
        active = await store.get_active()
        assert active.version == created.version
        settings = active.configuration.cluster
        assert settings.minimum_contributing_independent_wallets == 4
        assert settings.window_seconds == 120
        assert settings.score_weighting == "TOTAL_SOL"
        assert settings.minimum_buy_count == 2
        assert settings.minimum_total_sol == 5
        return {"version": active.version}

    assert asyncio.run(run()) == {"version": 2}
