"""Smart Wallet Scores, Registry transitions, and their public HTTP seam."""

import json
from collections.abc import Mapping, Sequence
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

import pytest
from fastapi.testclient import TestClient

from paper_trade.main import create_app
from paper_trade.research_configuration import (
    InMemoryResearchConfigurationStore,
    ResearchConfiguration,
    WalletScoreWeights,
    WalletSettings,
)
from paper_trade.wallet_accounting import (
    InMemoryRecordedWalletAccountingStore,
    InMemoryWalletAccountingStore,
    RecordedWalletHistorySource,
    RecordWalletAccountingRequest,
    WalletAccountingService,
    WalletActivity,
    WalletHistory,
    WalletHistoryCoverage,
    WalletMarkPrice,
)
from paper_trade.wallet_behavior import (
    BehaviorFlagCoverage,
    ConsistencyMetrics,
    Distribution,
    MarketEvidenceCoverage,
    MemeMetrics,
    ProfitConcentration,
    RecordedMarketEvidenceSource,
    WalletBehavior,
    WalletBehaviorService,
    WalletBehaviorWindow,
    WalletMarketEvidence,
)
from paper_trade.wallet_copyability import (
    CopyabilityOutcome,
    CopyabilityPoolCoverage,
    CopyabilityScenarioCoverage,
    RecordedCopyabilityMarketPoolSource,
    RecordedMarketPool,
    WalletCopyability,
    WalletCopyabilityService,
)
from paper_trade.wallet_scoring import (
    InMemoryWalletScoringStore,
    WalletScore,
    WalletScoringService,
)

FIXTURES = Path(__file__).parent / "fixtures"
WALLET = "5Q544fKrFoe6tsEbD7S8EmxGTJYAKtTVhAW5Q5pge4j1"
WALLET_TWO = "4wBqpZM9W7D6h2ZQ5E6o1CymCPG9hrpE7cXkYkKpE8Qm"
WALLET_THREE = "9BB6NFEcjBCtnNLFko2FqVQBq8HHM13kCyYcdQbgpump"
TOKEN = "7GCihgDB8fe6KNjn2MYtkzZcRjQy3t9GHdC8uHYmW2hr"
AS_OF = datetime(2026, 9, 28, 10, 0, tzinfo=timezone.utc)


def at(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def fixed_clock() -> datetime:
    return AS_OF


def distribution(value: Optional[float] = None) -> Distribution:
    if value is None:
        return Distribution(count=0, average=None, median=None, minimum=None, maximum=None)
    return Distribution(count=1, average=value, median=value, minimum=value, maximum=value)


def meme(**overrides: object) -> MemeMetrics:
    defaults: dict[str, object] = {
        "entry_count": 1,
        "early_entry_rate_percent": 100.0,
        "creation_to_entry_latency_seconds": distribution(30.0),
        "entry_market_cap_usd": distribution(12_000.0),
        "entry_liquidity_usd": distribution(8_000.0),
        "sub_100k_entry_rate_percent": 100.0,
        "sub_500k_entry_rate_percent": 100.0,
        "rug_exposure_rate_percent": 0.0,
        "dead_token_exposure_rate_percent": 0.0,
        "migration_success_rate_percent": 100.0,
        "token_activity_per_active_day": 1.0,
    }
    defaults.update(overrides)
    return MemeMetrics(**defaults)


def window(period: str, **overrides: object) -> WalletBehaviorWindow:
    defaults: dict[str, object] = {
        "period": period,
        "starts_at": None if period == "ALL_TIME" else AS_OF,
        "as_of": AS_OF,
        "definition": "Clean FIFO metrics.",
        "realized_pnl_usd": 0.0,
        "unrealized_pnl_usd": 0.0,
        "total_pnl_usd": 0.0,
        "roi_percent": None,
        "win_rate_percent": None,
        "trade_count": 0,
        "winning_tokens": 0,
        "losing_tokens": 0,
        "average_win_usd": None,
        "median_win_usd": None,
        "average_loss_usd": None,
        "median_loss_usd": None,
        "profit_factor": None,
        "max_drawdown_usd": 0.0,
        "largest_win_usd": None,
        "largest_loss_usd": None,
        "position_size_usd": distribution(None),
        "holding_time_seconds": distribution(None),
        "consistency": ConsistencyMetrics(
            profit_concentration=ProfitConcentration(
                top_one_percent=None, top_three_percent=None, top_five_percent=None
            ),
            profitable_days=0,
            profitable_weeks=0,
            profitable_months=0,
        ),
        "meme": meme(),
        "unknowns": [],
    }
    defaults.update(overrides)
    return WalletBehaviorWindow(**defaults)


def complete_coverage(source: str = "HELIUS") -> BehaviorFlagCoverage:
    return BehaviorFlagCoverage(source=source, complete=True, unknown_fields=[])


def behavior(
    windows: Sequence[WalletBehaviorWindow],
    *,
    coverage: Optional[Sequence[BehaviorFlagCoverage]] = None,
    flags: Sequence[object] = (),
    warnings: Sequence[str] = (),
) -> WalletBehavior:
    return WalletBehavior(
        address=WALLET,
        as_of=AS_OF,
        metric_definitions=["Clean FIFO metrics; contaminated quantities are excluded."],
        windows=list(windows),
        classifications=[],
        flags=list(flags),
        coverage=list(coverage) if coverage is not None else [complete_coverage()],
        warnings=list(warnings),
    )


def strong_behavior(
    recent_roi: float = 50.0, recent_win_rate: float = 60.0, **overrides: object
) -> WalletBehavior:
    """A Wallet whose components are all known, complete, and strong."""
    all_time_overrides: dict[str, object] = {
        "realized_pnl_usd": 20.0,
        "unrealized_pnl_usd": 5.0,
        "total_pnl_usd": 25.0,
        "roi_percent": 50.0,
        "win_rate_percent": 60.0,
        "trade_count": 25,
        "winning_tokens": 15,
        "losing_tokens": 10,
        "meme": meme(sub_100k_entry_rate_percent=80.0),
        "consistency": ConsistencyMetrics(
            profit_concentration=ProfitConcentration(
                top_one_percent=40.0, top_three_percent=70.0, top_five_percent=85.0
            ),
            profitable_days=12,
            profitable_weeks=6,
            profitable_months=3,
        ),
    }
    all_time_overrides.update(overrides)
    return behavior(
        [
            window("30D", roi_percent=recent_roi, win_rate_percent=recent_win_rate, trade_count=5),
            window("ALL_TIME", **all_time_overrides),
        ]
    )


def weak_behavior(*, roi: float, top_one: float, rug: float, sub_100k: float) -> WalletBehavior:
    return behavior(
        [
            window("30D", roi_percent=roi, win_rate_percent=40.0, trade_count=5),
            window(
                "ALL_TIME",
                roi_percent=roi,
                win_rate_percent=max(0.0, 100.0 - top_one),
                trade_count=25,
                realized_pnl_usd=-10.0,
                consistency=ConsistencyMetrics(
                    profit_concentration=ProfitConcentration(
                        top_one_percent=top_one, top_three_percent=top_one, top_five_percent=top_one
                    ),
                    profitable_days=1,
                    profitable_weeks=1,
                    profitable_months=1,
                ),
                meme=meme(rug_exposure_rate_percent=rug, sub_100k_entry_rate_percent=sub_100k),
            ),
        ]
    )


def unknown_behavior() -> WalletBehavior:
    """A Wallet whose recorded evidence cannot establish any component."""
    return behavior(
        [
            window(
                "30D",
                meme=meme(
                    rug_exposure_rate_percent=None,
                    dead_token_exposure_rate_percent=None,
                    sub_100k_entry_rate_percent=None,
                ),
            ),
            window(
                "ALL_TIME",
                meme=meme(
                    rug_exposure_rate_percent=None,
                    dead_token_exposure_rate_percent=None,
                    sub_100k_entry_rate_percent=None,
                ),
            ),
        ]
    )


def pool_coverage(*, complete: bool = True) -> CopyabilityPoolCoverage:
    return CopyabilityPoolCoverage(
        provider="RECORDED_MARKET_POOL",
        requested_as_of=AS_OF,
        as_of_start=AS_OF,
        as_of_end=AS_OF,
        complete=complete,
        freshness_seconds=10,
        unknown_fields=[] if complete else ["historical_pool_state"],
        warnings=[] if complete else ["Recorded pool snapshots are incomplete."],
    )


def outcome(
    *, follower_roi: Optional[float], decay: Optional[float], delay: int = 500, size: float = 0.1
) -> CopyabilityOutcome:
    return CopyabilityOutcome(
        token_address=TOKEN,
        leader_entry_signature=f"leader-entry-{delay}-{size}",
        leader_exit_signature=f"leader-exit-{delay}-{size}",
        follower_delay_ms=delay,
        follower_size_sol=size,
        leader_roi_percent=50.0,
        follower_roi_percent=follower_roi,
        copy_decay_percent=decay,
        status="FILLED" if follower_roi is not None else "REJECTED",
        coverage=CopyabilityScenarioCoverage(
            token_address=TOKEN,
            entry_requested_at=AS_OF,
            exit_requested_at=AS_OF,
            complete=follower_roi is not None,
        ),
        warnings=[],
    )


def copyability(
    outcomes: Sequence[CopyabilityOutcome], *, complete: bool = True
) -> WalletCopyability:
    return WalletCopyability(
        address=WALLET,
        as_of=AS_OF,
        configuration_version=1,
        delays_ms=[500],
        follower_sizes_sol=[0.1],
        outcomes=list(outcomes),
        coverage=pool_coverage(complete=complete),
        warnings=[],
    )


class BehaviorStore:
    def __init__(self, behaviors: Mapping[str, WalletBehavior]) -> None:
        self._behaviors = dict(behaviors)

    def set(self, address: str, value: WalletBehavior) -> None:
        self._behaviors[address] = value

    async def behavior(self, address: str, as_of: datetime) -> WalletBehavior:
        return self._behaviors[address].model_copy(update={"address": address})


class CopyabilityStore:
    def __init__(self, copyabilities: Mapping[str, WalletCopyability]) -> None:
        self._copyabilities = dict(copyabilities)

    def set(self, address: str, value: WalletCopyability) -> None:
        self._copyabilities[address] = value

    async def copyability(self, address: str, as_of: datetime) -> WalletCopyability:
        return self._copyabilities[address].model_copy(update={"address": address})


class AddressStore:
    def __init__(self, addresses: Sequence[str]) -> None:
        self._addresses = list(addresses)

    async def list_wallets(self) -> list[str]:
        return list(self._addresses)


def scoring_service(
    behaviors: Mapping[str, WalletBehavior],
    copyabilities: Mapping[str, WalletCopyability],
    addresses: Optional[Sequence[str]] = None,
    *,
    configuration_store: Optional[InMemoryResearchConfigurationStore] = None,
    scoring_store: Optional[InMemoryWalletScoringStore] = None,
) -> WalletScoringService:
    return WalletScoringService(
        BehaviorStore(behaviors),
        CopyabilityStore(copyabilities),
        configuration_store or InMemoryResearchConfigurationStore(now=fixed_clock),
        scoring_store or InMemoryWalletScoringStore(now=fixed_clock),
        AddressStore(addresses if addresses is not None else list(behaviors)),
    )


def component(score: WalletScore, name: str) -> object:
    return next(item for item in score.components if item.name == name)


async def configured_store(**wallet_overrides: object) -> InMemoryResearchConfigurationStore:
    store = InMemoryResearchConfigurationStore(now=fixed_clock)
    await store.create(
        ResearchConfiguration(wallet=WalletSettings(**wallet_overrides))
    )
    return store


@pytest.mark.asyncio
async def test_score_is_the_weight_normalized_sum_of_configured_components() -> None:
    service = scoring_service(
        {WALLET: strong_behavior()},
        {WALLET: copyability([outcome(follower_roi=50.0, decay=0.0)])},
    )

    result = await service.score(WALLET, AS_OF)

    score = result.score
    assert score.total_score == pytest.approx(91)
    assert score.recommended_state == "SMART_WALLET"
    scores = {item.name: item.score for item in score.components}
    assert scores == {
        "profitability": 100,
        "consistency": 60,
        "copyability": 100,
        "risk_quality": 100,
        "entry_quality": 90,
        "history_quality": 100,
    }
    assert [item.weight for item in score.components] == [20, 20, 25, 15, 10, 10]
    assert sum(
        item.weighted_points for item in score.components
    ) == pytest.approx(score.total_score)
    assert score.unknowns == []
    assert score.configuration_version == 1
    assert score.configuration_id


@pytest.mark.asyncio
async def test_score_weights_are_read_from_versioned_configuration() -> None:
    configuration_store = await configured_store(
        score_weights=WalletScoreWeights(
            profitability=50,
            consistency=10,
            copyability=10,
            risk_quality=10,
            entry_quality=10,
            history_quality=10,
        )
    )
    service = scoring_service(
        {WALLET: strong_behavior()},
        {WALLET: copyability([outcome(follower_roi=50.0, decay=0.0)])},
        configuration_store=configuration_store,
    )

    result = await service.score(WALLET, AS_OF)

    assert result.score.configuration_version == 2
    assert result.score.total_score == pytest.approx(95)
    assert component(result.score, "profitability").weighted_points == pytest.approx(50)


@pytest.mark.asyncio
async def test_unknown_evidence_removes_weighted_points_and_is_reported() -> None:
    service = scoring_service(
        {WALLET: strong_behavior(meme=meme(
            rug_exposure_rate_percent=None, dead_token_exposure_rate_percent=None
        ))},
        {WALLET: copyability([outcome(follower_roi=50.0, decay=0.0)])},
    )

    result = await service.score(WALLET, AS_OF)

    assert component(result.score, "risk_quality").score is None
    assert component(result.score, "risk_quality").weighted_points == 0
    assert component(result.score, "entry_quality").score is None
    assert component(result.score, "entry_quality").weighted_points == 0
    assert result.score.total_score == pytest.approx(67)
    assert any(item.startswith("risk_quality:") for item in result.score.unknowns)
    assert any(item.startswith("entry_quality:") for item in result.score.unknowns)


@pytest.mark.asyncio
async def test_a_wallet_without_usable_evidence_scores_conservatively() -> None:
    service = scoring_service(
        {WALLET: unknown_behavior()},
        {WALLET: copyability([outcome(follower_roi=None, decay=None)])},
    )

    result = await service.score(WALLET, AS_OF)

    assert result.score.total_score == pytest.approx(5)
    assert result.score.recommended_state == "CANDIDATE"
    assert len(result.score.unknowns) == 5
    assert component(result.score, "history_quality").score == 50
    assert any("no configured delay" in unknown for unknown in result.score.unknowns)
    assert any("scenarios were rejected" in warning for warning in result.score.warnings)


@pytest.mark.asyncio
async def test_scoring_reads_clean_pnl_and_penalizes_contamination() -> None:
    history_document = json.loads((FIXTURES / "recorded_wallet_history.json").read_text())
    evidence_document = json.loads(
        (FIXTURES / "recorded_wallet_behavior_evidence.json").read_text()
    )
    pools_document = json.loads((FIXTURES / "recorded_copyability_market_pools.json").read_text())
    accounting_store = InMemoryWalletAccountingStore(
        WalletAccountingService(
            RecordedWalletHistorySource(
                [[WalletActivity.model_validate(item) for item in history_document["activities"]]],
                WalletHistoryCoverage.model_validate(history_document["coverage"]),
            ),
            [
                WalletMarkPrice(
                    token_address=TOKEN,
                    price_usd=5,
                    observed_at=at("2026-09-28T09:50:00Z"),
                    provider="DEXSCREENER",
                )
            ],
        ),
        addresses=[WALLET],
    )
    behavior_service = WalletBehaviorService(
        accounting_store,
        RecordedMarketEvidenceSource(
            [WalletMarketEvidence.model_validate(item) for item in evidence_document["evidence"]],
            MarketEvidenceCoverage.model_validate(evidence_document["coverage"]),
        ),
    )
    copyability_service = WalletCopyabilityService(
        accounting_store,
        RecordedCopyabilityMarketPoolSource(
            [RecordedMarketPool.model_validate(item) for item in pools_document["pools"]],
            CopyabilityPoolCoverage.model_validate(pools_document["coverage"]),
        ),
    )
    service = WalletScoringService(
        behavior_service,
        copyability_service,
        InMemoryResearchConfigurationStore(now=fixed_clock),
        InMemoryWalletScoringStore(now=fixed_clock),
        accounting_store,
    )

    result = await service.score(WALLET, at("2026-09-28T10:00:00Z"))

    score = result.score
    profitability = component(score, "profitability")
    assert profitability.score == 100
    assert "clean realized PnL 21.5 USD" in profitability.evidence[0]
    assert "62.2" not in json.dumps(score.model_dump(mode="json"))
    risk_quality = component(score, "risk_quality")
    assert risk_quality.score == 70
    assert "30 points for 3 risk flags" in risk_quality.reasons[0]
    assert component(score, "entry_quality").score == 100
    assert component(score, "consistency").score == 50
    assert score.recommended_state == "CANDIDATE"
    assert [item.source for item in score.coverage] == [
        "HELIUS",
        "RECORDED_MARKET_EVIDENCE",
        "RECORDED_MARKET_POOL",
    ]
    assert all(item.complete is False for item in score.coverage)
    assert [item.period for item in score.quality] == ["30D", "ALL_TIME"]
    assert score.quality[1].roi_percent == pytest.approx(59.3886462882)
    assert any("below the configured minimum" in warning for warning in score.warnings)


@pytest.mark.asyncio
async def test_transitions_record_every_state_and_never_become_permanent() -> None:
    behavior_store = BehaviorStore({WALLET: strong_behavior()})
    copyability_store = CopyabilityStore(
        {WALLET: copyability([outcome(follower_roi=50.0, decay=0.0)])}
    )
    store = InMemoryWalletScoringStore(now=fixed_clock)
    service = WalletScoringService(
        behavior_store,
        copyability_store,
        InMemoryResearchConfigurationStore(now=fixed_clock),
        store,
        AddressStore([WALLET]),
    )

    first = await service.score(WALLET, AS_OF)
    assert first.created is True and first.transitioned is True

    behavior_store.set(WALLET, weak_behavior(roi=0.0, top_one=50.0, rug=0.0, sub_100k=50.0))
    copyability_store.set(
        WALLET, copyability([outcome(follower_roi=0.0, decay=25.0)])
    )
    watchlist = await service.score(WALLET, AS_OF)

    behavior_store.set(WALLET, weak_behavior(roi=-40.0, top_one=80.0, rug=50.0, sub_100k=20.0))
    copyability_store.set(
        WALLET, copyability([outcome(follower_roi=-40.0, decay=90.0)])
    )
    suspended = await service.score(WALLET, AS_OF)

    behavior_store.set(WALLET, weak_behavior(roi=-50.0, top_one=100.0, rug=100.0, sub_100k=0.0))
    copyability_store.set(
        WALLET, copyability([outcome(follower_roi=-50.0, decay=100.0)])
    )
    rejected = await service.score(WALLET, AS_OF)

    behavior_store.set(WALLET, strong_behavior())
    copyability_store.set(WALLET, copyability([outcome(follower_roi=50.0, decay=0.0)]))
    promoted_again = await service.score(WALLET, AS_OF)

    assert [first.score.recommended_state, watchlist.score.recommended_state,
            suspended.score.recommended_state, rejected.score.recommended_state,
            promoted_again.score.recommended_state] == [
        "SMART_WALLET",
        "WATCHLIST",
        "SUSPENDED",
        "REJECTED",
        "SMART_WALLET",
    ]
    assert watchlist.score.total_score == pytest.approx(68.125)
    assert suspended.score.total_score == pytest.approx(29.5)
    assert rejected.score.total_score == pytest.approx(10)
    registry = await service.registry(WALLET)
    assert registry.state == "SMART_WALLET"
    assert [item.from_state for item in registry.transitions] == [
        "CANDIDATE",
        "SMART_WALLET",
        "WATCHLIST",
        "SUSPENDED",
        "REJECTED",
    ]
    assert [item.to_state for item in registry.transitions] == [
        "SMART_WALLET",
        "WATCHLIST",
        "SUSPENDED",
        "REJECTED",
        "SMART_WALLET",
    ]
    assert all(item.reason and item.evidence and item.as_of for item in registry.transitions)
    assert all(item.configuration_version == 1 for item in registry.transitions)


@pytest.mark.asyncio
async def test_rescoring_identical_inputs_is_idempotent() -> None:
    service = scoring_service(
        {WALLET: strong_behavior()},
        {WALLET: copyability([outcome(follower_roi=50.0, decay=0.0)])},
    )

    first = await service.score(WALLET, AS_OF)
    second = await service.score(WALLET, AS_OF)

    assert first.created is True
    assert second.created is False
    assert second.transitioned is False
    assert second.version == first.version
    assert second.score == first.score
    registry = await service.registry(WALLET)
    assert len(registry.transitions) == 1


@pytest.mark.asyncio
async def test_reassessment_is_idempotent_across_every_recorded_wallet() -> None:
    behaviors = {
        WALLET: strong_behavior(),
        WALLET_TWO: weak_behavior(roi=0.0, top_one=50.0, rug=0.0, sub_100k=50.0),
    }
    copyabilities = {
        WALLET: copyability([outcome(follower_roi=50.0, decay=0.0)]),
        WALLET_TWO: copyability([outcome(follower_roi=0.0, decay=25.0)]),
    }
    service = scoring_service(behaviors, copyabilities)

    first = await service.reassess_all(AS_OF)
    second = await service.reassess_all(AS_OF)

    assert [item.address for item in first.outcomes] == [WALLET, WALLET_TWO]
    assert all(item.created for item in first.outcomes)
    assert all(item.transitioned for item in first.outcomes)
    assert all(item.created is False for item in second.outcomes)
    assert all(item.transitioned is False for item in second.outcomes)
    assert [item.version for item in second.outcomes] == [
        item.version for item in first.outcomes
    ]


@pytest.mark.asyncio
async def test_leaderboard_sorts_filters_and_shows_recent_and_long_term_quality() -> None:
    behaviors = {
        WALLET: strong_behavior(recent_roi=-5.0),
        WALLET_TWO: weak_behavior(roi=0.0, top_one=50.0, rug=0.0, sub_100k=50.0),
        WALLET_THREE: weak_behavior(roi=-40.0, top_one=80.0, rug=50.0, sub_100k=20.0),
    }
    copyabilities = {
        WALLET: copyability([outcome(follower_roi=50.0, decay=0.0)]),
        WALLET_TWO: copyability([outcome(follower_roi=0.0, decay=25.0)]),
        WALLET_THREE: copyability([outcome(follower_roi=-40.0, decay=90.0)]),
    }
    service = scoring_service(behaviors, copyabilities)
    await service.reassess_all(AS_OF)

    by_score = await service.leaderboard(AS_OF)
    by_recent_roi = await service.leaderboard(AS_OF, sort="RECENT_ROI")
    watchlist_only = await service.leaderboard(AS_OF, registry_state="WATCHLIST")
    limited = await service.leaderboard(AS_OF, limit=1)

    assert [entry.address for entry in by_score] == [WALLET, WALLET_TWO, WALLET_THREE]
    assert [entry.total_score for entry in by_score] == sorted(
        [entry.total_score for entry in by_score], reverse=True
    )
    assert [entry.address for entry in by_recent_roi] == [WALLET_TWO, WALLET, WALLET_THREE]
    assert [entry.address for entry in watchlist_only] == [WALLET_TWO]
    assert [entry.address for entry in limited] == [WALLET]
    assert [item.period for item in by_score[0].quality] == ["30D", "ALL_TIME"]
    assert by_score[0].quality[0].roi_percent == pytest.approx(-5.0)
    assert by_score[0].quality[1].roi_percent == pytest.approx(50.0)
    assert by_score[0].quality[1].trade_count == 25


def http_service() -> WalletScoringService:
    return scoring_service(
        {
            WALLET: strong_behavior(),
            WALLET_TWO: weak_behavior(roi=0.0, top_one=50.0, rug=0.0, sub_100k=50.0),
        },
        {
            WALLET: copyability([outcome(follower_roi=50.0, decay=0.0)]),
            WALLET_TWO: copyability([outcome(follower_roi=0.0, decay=25.0)]),
        },
    )


def test_wallet_score_endpoints_recompute_persist_and_report_registry() -> None:
    client = TestClient(create_app(wallet_scoring_service=http_service()))
    url = f"/wallets/{WALLET}/score?as_of=2026-09-28T10:00:00Z"

    created = client.post(url)
    replayed = client.post(url)
    detail = client.get(url)
    registry = client.get(f"/wallets/{WALLET}/registry")

    assert created.status_code == 201
    assert created.json()["created"] is True
    assert created.json()["transitioned"] is True
    assert created.json()["score"]["recommended_state"] == "SMART_WALLET"
    assert replayed.status_code == 200
    assert replayed.json()["created"] is False
    assert replayed.json()["version"] == created.json()["version"]
    assert detail.status_code == 200
    assert [item["name"] for item in detail.json()["components"]] == [
        "profitability",
        "consistency",
        "copyability",
        "risk_quality",
        "entry_quality",
        "history_quality",
    ]
    assert detail.json()["components"][0]["evidence"]
    assert registry.status_code == 200
    assert registry.json()["state"] == "SMART_WALLET"
    assert registry.json()["transitions"][0]["from_state"] == "CANDIDATE"


def test_wallet_score_endpoints_report_missing_scores_and_coverage() -> None:
    client = TestClient(create_app(wallet_scoring_service=http_service()))

    missing = client.get(f"/wallets/{WALLET_THREE}/score")
    unscored_registry = client.get(f"/wallets/{WALLET}/registry")

    assert missing.status_code == 404
    assert unscored_registry.status_code == 200
    assert unscored_registry.json()["state"] == "CANDIDATE"
    assert unscored_registry.json()["transitions"] == []


def test_wallet_score_endpoint_reports_a_wallet_without_recorded_history() -> None:
    client = TestClient(create_app(wallet_scoring_service=http_service()))

    response = client.post(f"/wallets/{WALLET_THREE}/score?as_of=2026-09-28T10:00:00Z")

    assert response.status_code == 404


def test_wallet_score_endpoints_compose_from_injected_stores() -> None:
    history_document = json.loads((FIXTURES / "recorded_wallet_history.json").read_text())
    accounting_store = InMemoryWalletAccountingStore(
        WalletAccountingService(
            RecordedWalletHistorySource(
                [], WalletHistoryCoverage.model_validate(history_document["coverage"])
            ),
            [],
        ),
        addresses=[WALLET],
    )
    client = TestClient(
        create_app(
            wallet_accounting_store=accounting_store,
            wallet_behavior_store=BehaviorStore({WALLET: strong_behavior()}),
            wallet_copyability_store=CopyabilityStore(
                {WALLET: copyability([outcome(follower_roi=50.0, decay=0.0)])}
            ),
            research_configuration_store=InMemoryResearchConfigurationStore(now=fixed_clock),
            wallet_scoring_store=InMemoryWalletScoringStore(now=fixed_clock),
        )
    )

    scored = client.post(f"/wallets/{WALLET}/score?as_of=2026-09-28T10:00:00Z")
    leaderboard = client.get("/wallets/scores?as_of=2026-09-28T10:00:00Z")

    assert scored.status_code == 201
    assert scored.json()["score"]["recommended_state"] == "SMART_WALLET"
    assert [row["address"] for row in leaderboard.json()] == [WALLET]


def test_wallet_score_endpoints_return_503_without_a_scoring_service() -> None:
    client = TestClient(create_app())

    assert client.get("/wallets/scores").status_code == 503
    assert client.get(f"/wallets/{WALLET}/score").status_code == 503
    assert client.post(f"/wallets/{WALLET}/score").status_code == 503
    assert client.get(f"/wallets/{WALLET}/registry").status_code == 503
    assert client.post("/wallet-scores/reassess").status_code == 503


def test_leaderboard_and_reassessment_endpoints_sort_filter_and_stay_idempotent() -> None:
    client = TestClient(create_app(wallet_scoring_service=http_service()))

    reassessed = client.post("/wallet-scores/reassess?as_of=2026-09-28T10:00:00Z")
    replayed = client.post("/wallet-scores/reassess?as_of=2026-09-28T10:00:00Z")
    leaderboard = client.get(
        "/wallets/scores?as_of=2026-09-28T10:00:00Z"
        "&sort=LONG_TERM_ROI&registry_state=WATCHLIST&limit=5"
    )
    all_rows = client.get("/wallets/scores?as_of=2026-09-28T10:00:00Z")

    assert reassessed.status_code == 200
    assert [item["address"] for item in reassessed.json()["outcomes"]] == [WALLET, WALLET_TWO]
    assert all(item["created"] for item in reassessed.json()["outcomes"])
    assert all(item["created"] is False for item in replayed.json()["outcomes"])
    assert leaderboard.status_code == 200
    assert [row["address"] for row in leaderboard.json()] == [WALLET_TWO]
    assert leaderboard.json()[0]["recommended_state"] == "WATCHLIST"
    assert [item["period"] for item in leaderboard.json()[0]["quality"]] == [
        "30D",
        "ALL_TIME",
    ]
    assert [row["address"] for row in all_rows.json()] == [WALLET, WALLET_TWO]


@pytest.mark.asyncio
async def test_accounting_stores_enumerate_recorded_wallets() -> None:
    history_document = json.loads((FIXTURES / "recorded_wallet_history.json").read_text())
    recorded = InMemoryRecordedWalletAccountingStore()
    await recorded.record(
        RecordWalletAccountingRequest(
            history=WalletHistory(
                address=WALLET,
                activities=[
                    WalletActivity.model_validate(item)
                    for item in history_document["activities"]
                ],
                coverage=WalletHistoryCoverage.model_validate(history_document["coverage"]),
            )
        )
    )
    in_memory = InMemoryWalletAccountingStore(
        WalletAccountingService(
            RecordedWalletHistorySource([], WalletHistoryCoverage.model_validate(
                history_document["coverage"]
            )),
            [],
        ),
        addresses=[WALLET_TWO, WALLET, WALLET_TWO],
    )

    assert await recorded.list_wallets() == [WALLET]
    assert await in_memory.list_wallets() == [WALLET_TWO, WALLET]
