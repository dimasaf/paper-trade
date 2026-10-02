"""The Discovery funnel through its service, store, and HTTP seams."""

import asyncio
import itertools
import json
from collections.abc import Callable, Mapping, Sequence
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional, get_args
from uuid import UUID

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError
from recorded_launch_events import recorded_pump_swap_launch_event

from paper_trade.discovery_funnel import (
    FUNNEL_STAGE_ORDER,
    DiscoveryFunnelRequest,
    DiscoveryFunnelRun,
    DiscoveryFunnelService,
    FunnelReasonCode,
    FunnelStage,
    InMemoryDiscoveryFunnelStore,
)
from paper_trade.health import ComponentHealth, HealthComponents, HealthReport
from paper_trade.historical_winners import (
    EarlyBuyerSource,
    HistoricalWinnerDiscoveryService,
    RecordedEarlyBuyerSource,
    RecordedEarlyBuyerTransaction,
    TokenEarlyBuyerHistory,
)
from paper_trade.launch_events import LaunchEvent
from paper_trade.main import create_app
from paper_trade.market_state import (
    InMemoryMarketStateStore,
    MarketObservation,
    MarketPool,
    MarketProviderCoverage,
)
from paper_trade.research_configuration import InMemoryResearchConfigurationStore
from paper_trade.tokens import InMemoryTokenStore
from paper_trade.wallet_accounting import (
    InMemoryWalletAccountingStore,
    RecordedWalletHistorySource,
    WalletAccountingService,
    WalletActivity,
    WalletHistoryCoverage,
    WalletMarkPrice,
)
from paper_trade.wallet_behavior import (
    MarketEvidenceCoverage,
    RecordedMarketEvidenceSource,
    WalletBehaviorService,
    WalletMarketEvidence,
)
from paper_trade.wallet_copyability import (
    CopyabilityPoolCoverage,
    RecordedCopyabilityMarketPoolSource,
    RecordedMarketPool,
    WalletCopyabilityService,
)
from paper_trade.wallet_scoring import (
    InMemoryWalletScoringStore,
    ScoreComponent,
    WalletScore,
    WalletScoreCoverage,
    WalletScoreResult,
    WalletScoringService,
)

FIXTURES = Path(__file__).parent / "fixtures"
TOKEN_ONE = "7GCihgDB8fe6KNjn2MYtkzZcRjQy3t9GHdC8uHYmW2hr"
TOKEN_TWO = "27G8MtK7VtTcCHkpASjSDdkWWYfoqT6ggEuKidVJidD4"
TOKEN_THREE = "9BB6NFEcjBCtnNLFko2FqVQBq8HHM13kCyYcdQbgpump"
POOL = "9xQeWvG816bUx9EPf8aYxGB4pXzv5S1kYQBF3h4r7S1i"
WALLET_STRONG = "5Q544fKrFoe6tsEbD7S8EmxGTJYAKtTVhAW5Q5pge4j1"
WALLET_WEAK = "4wBqpZM9W7D6h2ZQ5E6o1CymCPG9hrpE7cXkYkKpE8Qm"
WALLET_UNRECORDED = "7gmqiaGJpHKo5jVLWkxSSr8HFxzMPtHQthhaABcjjJB1"
WALLET_FAILED = "H78u6JJ82BpT8kae6UXkBbRWLYWUTfu7HXSGVxgY5dAY"
WALLET_TRANSFER = "FzxLwSeXuftPCPGwxchPNuaU813LxzJBLDtsD8ZwpFRK"
WALLET_UNKNOWN = "Fz79XcXMRZ5ijyyQ8zZNwJBWXnr7hP3bVM1q4bRDGb7P"
WALLET_UNQUALIFIED = "EAESH8FF1DpkjrL3zJcGFN9F4tJuC1cwuThZJYVrGp4Y"
AS_OF = datetime(2026, 9, 28, 10, 0, tzinfo=timezone.utc)
FUNNEL_REQUEST: dict[str, Any] = {
    "cohort": {
        "cohort_id": "recorded-september-winners",
        "created_from": "2026-09-28T09:00:00Z",
        "created_to": "2026-09-28T09:00:00Z",
        "qualification_as_of": "2026-09-28T10:00:00Z",
    },
    "as_of": "2026-09-28T10:00:00Z",
}
TOKENS: tuple[tuple[str, str], ...] = (
    (TOKEN_ONE, "RSWAP"),
    (TOKEN_TWO, "RSLOW"),
    (TOKEN_THREE, "RUNKNOWN"),
)
REASON_CODES = set(get_args(FunnelReasonCode))


def at(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def fixed_clock() -> datetime:
    return AS_OF


def identifier_factory(start: int) -> Callable[[], UUID]:
    counter = itertools.count(start)
    return lambda: UUID(int=next(counter))


class ReadyHealthService:
    async def check(self) -> HealthReport:
        ready = ComponentHealth(status="ready", message="ready")
        return HealthReport(
            checked_at=AS_OF,
            components=HealthComponents(
                application=ready, database=ready, redis=ready, worker=ready
            ),
        )


def launch_event(address: str, event_id: str, symbol: str) -> LaunchEvent:
    return recorded_pump_swap_launch_event().model_copy(
        update={"address": address, "event_id": event_id, "symbol": symbol}
    )


def observation(
    address: str,
    observation_id: str,
    observed_at: str,
    market_cap: float,
    liquidity: Optional[float],
) -> MarketObservation:
    return MarketObservation(
        observation_id=observation_id,
        address=address,
        observed_at=at(observed_at),
        price_usd=0.002,
        supply=1_000_000_000,
        market_cap_usd=market_cap,
        liquidity_usd=liquidity,
        volume_24h_usd=20_000,
        pools=[MarketPool(address=POOL, venue="Raydium")],
        coverage=MarketProviderCoverage(
            provider="DEXSCREENER",
            requested_as_of=at(observed_at),
            as_of_start=at(observed_at),
            as_of_end=at(observed_at),
            complete=True,
            freshness_seconds=3600,
            unknown_fields=[] if liquidity is not None else ["liquidity_usd"],
        ),
    )


def market_store() -> InMemoryMarketStateStore:
    store = InMemoryMarketStateStore()
    recorded = [
        observation(TOKEN_ONE, "one-initial", "2026-09-28T09:00:00Z", 120_000, 5_000),
        observation(TOKEN_ONE, "one-entry", "2026-09-28T09:04:00Z", 125_000, None),
        observation(TOKEN_ONE, "one-peak", "2026-09-28T09:50:00Z", 1_200_000, 60_000),
        observation(TOKEN_TWO, "two-initial", "2026-09-28T09:00:00Z", 120_000, 5_000),
        observation(TOKEN_TWO, "two-peak", "2026-09-28T09:30:00Z", 300_000, 20_000),
    ]
    for item in recorded:
        asyncio.run(store.record(item))
    return store


def early_buyer_transaction(
    wallet_address: str,
    signature: str,
    chain_time: str,
    *,
    token_address: str = TOKEN_ONE,
    movement_type: str = "BUY",
    succeeded: bool = True,
) -> RecordedEarlyBuyerTransaction:
    return RecordedEarlyBuyerTransaction(
        wallet_address=wallet_address,
        signature=signature,
        movement_index=0,
        slot=314159266,
        chain_time=at(chain_time),
        observed_at=at(chain_time),
        succeeded=succeeded,
        token_address=token_address,
        movement_type=movement_type,
        quantity=10,
        notional_usd=None,
        venue="Raydium",
        evidence=["recorded Helius SWAP"],
    )


def early_buyer_coverage() -> WalletHistoryCoverage:
    return WalletHistoryCoverage.model_validate(
        json.loads((FIXTURES / "recorded_early_buyers.json").read_text())["coverage"]
    )


def recorded_early_buyer_source() -> RecordedEarlyBuyerSource:
    return RecordedEarlyBuyerSource(
        pages=[
            [
                early_buyer_transaction(
                    WALLET_STRONG, "recorded-buy-strong", "2026-09-28T09:05:00Z"
                ),
                early_buyer_transaction(WALLET_WEAK, "recorded-buy-weak", "2026-09-28T09:06:00Z"),
                early_buyer_transaction(
                    WALLET_UNRECORDED, "recorded-buy-unrecorded", "2026-09-28T09:07:00Z"
                ),
                early_buyer_transaction(
                    WALLET_FAILED,
                    "recorded-buy-failed",
                    "2026-09-28T09:08:00Z",
                    succeeded=False,
                ),
                early_buyer_transaction(
                    WALLET_TRANSFER,
                    "recorded-transfer-in",
                    "2026-09-28T09:09:00Z",
                    movement_type="TRANSFER_IN",
                ),
                early_buyer_transaction(
                    WALLET_UNKNOWN,
                    "recorded-unknown-movement",
                    "2026-09-28T09:10:00Z",
                    movement_type="UNKNOWN",
                ),
                # A buyer of a Token that never qualified must stay outside the funnel.
                early_buyer_transaction(
                    WALLET_UNQUALIFIED,
                    "recorded-buy-unqualified-token",
                    "2026-09-28T09:11:00Z",
                    token_address=TOKEN_TWO,
                ),
            ]
        ],
        coverage=early_buyer_coverage(),
    )


class FailingEarlyBuyerSource:
    """An Adapter whose recorded provider is unavailable."""

    async def early_buyers(self, token_address: str, as_of: datetime) -> TokenEarlyBuyerHistory:
        raise ValueError("recorded early-buyer provider is unavailable")


COMPONENT_WEIGHTS: dict[str, float] = {
    "profitability": 20,
    "consistency": 20,
    "copyability": 25,
    "risk_quality": 15,
    "entry_quality": 10,
    "history_quality": 10,
}


def funnel_score(
    address: str,
    components: Mapping[str, Optional[float]],
    *,
    state: str = "CANDIDATE",
    coverage: Sequence[tuple[str, bool]] = (("HELIUS", True),),
    unknowns: Sequence[str] = (),
    warnings: Sequence[str] = (),
) -> WalletScoreResult:
    """A recorded Smart Wallet Score whose components drive the funnel gates."""
    built = [
        ScoreComponent(
            name=name,
            score=components[name],
            weight=COMPONENT_WEIGHTS[name],
            weighted_points=round(COMPONENT_WEIGHTS[name] * (components[name] or 0.0) / 100, 10),
            reasons=[f"{name} reads versioned configuration for {address}."],
            evidence=[f"{name} evidence for {address}."],
            warnings=[],
            unknowns=[] if components[name] is not None else [f"{name} is UNKNOWN."],
        )
        for name in COMPONENT_WEIGHTS
    ]
    score = WalletScore(
        address=address,
        as_of=AS_OF,
        configuration_id="00000000-0000-0000-0000-000000000001",
        configuration_version=1,
        total_score=round(sum(component.weighted_points for component in built), 10),
        recommended_state=state,
        components=built,
        quality=[],
        reasons=[f"Total score for {address}.", f"The Registry recommends {state} for {address}."],
        warnings=list(warnings),
        evidence=[f"Registry evidence for {address}."],
        unknowns=list(unknowns),
        coverage=[
            WalletScoreCoverage(source=source, complete=complete)
            for source, complete in coverage
        ],
    )
    return WalletScoreResult(
        address=address,
        created=True,
        version=1,
        created_at=AS_OF,
        transitioned=False,
        score=score,
    )


def strong_score() -> WalletScoreResult:
    return funnel_score(
        WALLET_STRONG, dict.fromkeys(COMPONENT_WEIGHTS, 100.0), state="SMART_WALLET"
    )


def weak_score() -> WalletScoreResult:
    components: dict[str, Optional[float]] = dict.fromkeys(COMPONENT_WEIGHTS, 100.0)
    components["profitability"] = 20.0
    return funnel_score(WALLET_WEAK, components, state="REJECTED")


class StubWalletScoreSource:
    """Deterministic recorded-score Adapter used by funnel HTTP tests."""

    def __init__(self, scores: Mapping[str, WalletScoreResult]) -> None:
        self._scores = dict(scores)

    def set(self, address: str, score: WalletScoreResult) -> None:
        self._scores[address] = score

    async def score(self, address: str, as_of: datetime) -> WalletScoreResult:
        if address not in self._scores:
            raise KeyError(address)
        return self._scores[address]


class Journey:
    """One wired journey: deterministic sources, stores, and HTTP client."""

    def __init__(
        self,
        *,
        early_buyer_source: Optional[EarlyBuyerSource] = None,
        tokens: Sequence[tuple[str, str]] = TOKENS,
    ) -> None:
        self.token_store = InMemoryTokenStore()
        self.market_store = market_store()
        self.early_buyer_source = early_buyer_source or recorded_early_buyer_source()
        self.configuration_store = InMemoryResearchConfigurationStore(
            now=fixed_clock, id_factory=identifier_factory(1)
        )
        self.funnel_store = InMemoryDiscoveryFunnelStore(
            now=fixed_clock, id_factory=identifier_factory(100)
        )
        self.scores = StubWalletScoreSource(
            {WALLET_STRONG: strong_score(), WALLET_WEAK: weak_score()}
        )
        service = DiscoveryFunnelService(
            HistoricalWinnerDiscoveryService(
                self.token_store, self.market_store, self.early_buyer_source
            ),
            self.scores,
            self.funnel_store,
            self.configuration_store,
        )
        self.client = TestClient(
            create_app(
                health_service=ReadyHealthService(),
                research_configuration_store=self.configuration_store,
                token_store=self.token_store,
                market_state_store=self.market_store,
                early_buyer_source=self.early_buyer_source,
                discovery_funnel_store=self.funnel_store,
                discovery_funnel_service=service,
            )
        )
        for index, (address, symbol) in enumerate(tokens):
            registered = self.client.post(
                "/tokens",
                json={
                    "event": launch_event(
                        address, f"recorded-funnel-launch-{index}", symbol
                    ).model_dump(mode="json")
                },
            )
            assert registered.status_code == 201


def stage_of(run: Mapping[str, Any], name: str) -> Mapping[str, Any]:
    return next(stage for stage in run["stages"] if stage["name"] == name)


def member_of(run: Mapping[str, Any], stage_name: str, subject: str) -> Mapping[str, Any]:
    stage = stage_of(run, stage_name)
    return next(member for member in stage["members"] if member["subject"] == subject)


def reason_codes(member: Mapping[str, Any]) -> list[str]:
    return [reason["code"] for reason in member["reasons"]]


def assert_stages_are_consistent(run: Mapping[str, Any]) -> None:
    stages = run["stages"]
    assert [stage["name"] for stage in stages] == list(FUNNEL_STAGE_ORDER)
    assert run["configuration_version"] == stages[0]["configuration_version"]
    for stage in stages:
        assert stage["evaluated"] == len(stage["members"])
        assert stage["included"] + stage["excluded"] + stage["unknown"] == stage["evaluated"]
        for outcome in ("INCLUDED", "EXCLUDED", "UNKNOWN"):
            assert stage[outcome.lower()] == sum(
                1 for member in stage["members"] if member["outcome"] == outcome
            )
        for member in stage["members"]:
            assert member["reasons"]
            for reason in member["reasons"]:
                assert reason["code"] in REASON_CODES
                assert reason["message"]
                assert reason["configuration_version"] == stage["configuration_version"]
                assert reason["as_of"] == stage["as_of"]
            assert member["outcome"] in [reason["outcome"] for reason in member["reasons"]]
    for previous, stage in zip(stages[1:], stages[2:]):
        assert stage["evaluated"] == previous["included"]


def test_discovery_funnel_http_journey_explains_every_stage_and_stays_consistent() -> None:
    journey = Journey()

    response = journey.client.post("/discovery/funnel", json=FUNNEL_REQUEST)

    assert response.status_code == 201
    run = response.json()
    assert run["run_id"] == "00000000-0000-0000-0000-000000000064"
    assert run["status"] == "COMPLETED"
    assert run["started_at"] == "2026-09-28T10:00:00Z"
    assert run["completed_at"] == "2026-09-28T10:00:00Z"
    assert run["error"] is None
    assert run["cohort"] == FUNNEL_REQUEST["cohort"]
    assert run["as_of"] == FUNNEL_REQUEST["as_of"]
    assert run["configuration_version"] == 1
    assert_stages_are_consistent(run)

    counts = {
        stage["name"]: (stage["evaluated"], stage["included"], stage["excluded"], stage["unknown"])
        for stage in run["stages"]
    }
    assert counts == {
        "TOKENS_ANALYZED": (3, 1, 1, 1),
        "WALLETS_FOUND": (6, 6, 0, 0),
        "CANDIDATES": (6, 3, 2, 1),
        "PROFITABLE": (3, 1, 1, 1),
        "CONSISTENT": (1, 1, 0, 0),
        "COPYABLE": (1, 1, 0, 0),
        "SMART_WALLET": (1, 1, 0, 0),
    }
    subjects = {member["subject"] for member in stage_of(run, "WALLETS_FOUND")["members"]}
    assert subjects == {
        WALLET_STRONG,
        WALLET_WEAK,
        WALLET_UNRECORDED,
        WALLET_FAILED,
        WALLET_TRANSFER,
        WALLET_UNKNOWN,
    }

    qualified = member_of(run, "TOKENS_ANALYZED", TOKEN_ONE)
    assert qualified["outcome"] == "INCLUDED"
    assert reason_codes(qualified) == [
        "INITIAL_MARKET_CAP_IN_RANGE",
        "PEAK_MARKET_CAP_AT_OR_ABOVE_MINIMUM",
    ]
    slow = member_of(run, "TOKENS_ANALYZED", TOKEN_TWO)
    assert slow["outcome"] == "EXCLUDED"
    assert reason_codes(slow)[-1] == "PEAK_MARKET_CAP_BELOW_MINIMUM"
    unknown_token = member_of(run, "TOKENS_ANALYZED", TOKEN_THREE)
    assert unknown_token["outcome"] == "UNKNOWN"
    assert reason_codes(unknown_token) == [
        "INITIAL_MARKET_CAP_UNKNOWN",
        "PEAK_MARKET_CAP_UNKNOWN",
    ]

    failed = member_of(run, "CANDIDATES", WALLET_FAILED)
    assert failed["outcome"] == "EXCLUDED"
    assert reason_codes(failed) == ["ENTRY_TRANSACTION_FAILED"]
    transferred = member_of(run, "CANDIDATES", WALLET_TRANSFER)
    assert transferred["outcome"] == "EXCLUDED"
    assert reason_codes(transferred) == ["ENTRY_NOT_A_BUY"]
    unknown_movement = member_of(run, "CANDIDATES", WALLET_UNKNOWN)
    assert unknown_movement["outcome"] == "UNKNOWN"
    assert reason_codes(unknown_movement) == ["ENTRY_MOVEMENT_UNKNOWN"]
    assert member_of(run, "CANDIDATES", WALLET_STRONG)["outcome"] == "INCLUDED"

    weak = member_of(run, "PROFITABLE", WALLET_WEAK)
    assert weak["outcome"] == "EXCLUDED"
    assert reason_codes(weak) == ["CLEAN_PROFITABILITY_BELOW_MIDPOINT"]
    assert weak["reasons"][0]["observed"] == "20"
    assert weak["reasons"][0]["threshold"] == ">= 50"
    unrecorded = member_of(run, "PROFITABLE", WALLET_UNRECORDED)
    assert unrecorded["outcome"] == "UNKNOWN"
    assert reason_codes(unrecorded) == ["NO_RECORDED_ACCOUNTING"]
    promoted = member_of(run, "SMART_WALLET", WALLET_STRONG)
    assert promoted["outcome"] == "INCLUDED"
    assert reason_codes(promoted) == ["REGISTRY_SMART_WALLET"]

    found = member_of(run, "WALLETS_FOUND", WALLET_STRONG)
    assert found["coverage"] == [
        {
            "source": "HELIUS",
            "complete": False,
            "unknown_fields": ["price_usd", "liquidity_usd"],
        }
    ]
    assert found["evidence"] == [
        "Recorded early buy recorded-buy-strong at 2026-09-28T09:05:00+00:00 in Raydium."
    ]
    assert "Recorded fixture has incomplete entry coverage" in run["warnings"]
    assert "price_usd is UNKNOWN at the entry as-of time" in run["warnings"]

    latest = journey.client.get("/discovery/funnel/latest")
    assert latest.status_code == 200
    assert latest.json() == run


def test_discovery_funnel_run_states_and_missing_stores_are_visible() -> None:
    journey = Journey()
    request = DiscoveryFunnelRequest.model_validate(FUNNEL_REQUEST)
    configuration = asyncio.run(journey.configuration_store.get_active())

    started = asyncio.run(journey.funnel_store.start_run(request, configuration))

    assert started.status == "RUNNING"
    assert started.stages == []
    assert started.completed_at is None
    running = journey.client.get("/discovery/funnel/latest")
    assert running.status_code == 200
    assert running.json()["status"] == "RUNNING"
    assert running.json()["run_id"] == started.run_id

    failing = Journey(
        early_buyer_source=FailingEarlyBuyerSource(), tokens=((TOKEN_ONE, "RSWAP"),)
    )
    failed = failing.client.post("/discovery/funnel", json=FUNNEL_REQUEST)

    assert failed.status_code == 502
    assert "recorded early-buyer provider is unavailable" in failed.json()["detail"]
    recorded = failing.client.get("/discovery/funnel/latest").json()
    assert recorded["status"] == "FAILED"
    assert recorded["stages"] == []
    assert recorded["error"] == "ValueError: recorded early-buyer provider is unavailable"

    unavailable = TestClient(create_app())
    assert unavailable.get("/discovery/funnel/latest").status_code == 503
    assert unavailable.post("/discovery/funnel", json=FUNNEL_REQUEST).status_code == 503

    empty = TestClient(create_app(discovery_funnel_store=InMemoryDiscoveryFunnelStore()))
    assert empty.get("/discovery/funnel/latest").status_code == 404


def test_recording_a_failure_clears_whatever_the_run_held() -> None:
    journey = Journey()
    document = journey.client.post("/discovery/funnel", json=FUNNEL_REQUEST).json()
    request = DiscoveryFunnelRequest.model_validate(FUNNEL_REQUEST)
    configuration = asyncio.run(journey.configuration_store.get_active())
    started = asyncio.run(journey.funnel_store.start_run(request, configuration))
    asyncio.run(
        journey.funnel_store.complete_run(
            started.run_id,
            [FunnelStage.model_validate(stage) for stage in document["stages"]],
            document["warnings"],
        )
    )

    failed = asyncio.run(
        journey.funnel_store.fail_run(started.run_id, "ValueError: provider unavailable")
    )

    assert failed.status == "FAILED"
    assert failed.stages == []
    assert failed.warnings == []
    assert failed.error == "ValueError: provider unavailable"
    latest = asyncio.run(journey.funnel_store.latest())
    assert latest is not None and latest.status == "FAILED"


def test_discovery_funnel_stays_consistent_when_the_cohort_or_configuration_changes() -> None:
    journey = Journey()
    first = journey.client.post("/discovery/funnel", json=FUNNEL_REQUEST).json()
    empty_cohort = {
        **FUNNEL_REQUEST,
        "cohort": {
            **FUNNEL_REQUEST["cohort"],
            "cohort_id": "recorded-august-winners",
            "created_from": "2026-09-28T08:00:00Z",
            "created_to": "2026-09-28T08:59:00Z",
        },
    }
    empty = journey.client.post("/discovery/funnel", json=empty_cohort).json()

    assert_stages_are_consistent(empty)
    assert [stage["evaluated"] for stage in empty["stages"]] == [0] * 7
    assert empty["cohort"]["cohort_id"] == "recorded-august-winners"
    assert empty["warnings"] == []

    changed = journey.client.get("/research-configurations/active").json()["configuration"]
    changed["wallet"]["minimum_trades"] = 10
    created = journey.client.post("/research-configurations", json={"configuration": changed})
    assert created.status_code == 201
    assert created.json()["version"] == 2
    journey.scores.set(
        WALLET_STRONG,
        funnel_score(
            WALLET_STRONG,
            {**dict.fromkeys(COMPONENT_WEIGHTS, 100.0), "profitability": 20.0},
            state="REJECTED",
        ),
    )

    second = journey.client.post("/discovery/funnel", json=FUNNEL_REQUEST).json()

    assert_stages_are_consistent(second)
    assert second["configuration_version"] == 2
    assert second["configuration_id"] != first["configuration_id"]
    assert stage_of(second, "SMART_WALLET")["included"] == 0
    promoted = member_of(second, "PROFITABLE", WALLET_STRONG)
    assert promoted["outcome"] == "EXCLUDED"
    assert promoted["reasons"][0]["configuration_version"] == 2
    assert (
        stage_of(second, "TOKENS_ANALYZED")["included"]
        == stage_of(first, "TOKENS_ANALYZED")["included"]
    )
    latest = journey.client.get("/discovery/funnel/latest").json()
    assert latest["run_id"] == second["run_id"]


def test_discovery_funnel_reads_the_configured_wallet_score_source() -> None:
    history = json.loads((FIXTURES / "recorded_wallet_history.json").read_text())
    evidence = json.loads((FIXTURES / "recorded_wallet_behavior_evidence.json").read_text())
    pools = json.loads((FIXTURES / "recorded_copyability_market_pools.json").read_text())
    accounting_store = InMemoryWalletAccountingStore(
        WalletAccountingService(
            RecordedWalletHistorySource(
                [[WalletActivity.model_validate(item) for item in history["activities"]]],
                WalletHistoryCoverage.model_validate(history["coverage"]),
            ),
            [
                WalletMarkPrice(
                    token_address=TOKEN_ONE,
                    price_usd=5,
                    observed_at=at("2026-09-28T09:50:00Z"),
                    provider="DEXSCREENER",
                )
            ],
        ),
        addresses=[WALLET_STRONG],
    )
    scoring_service = WalletScoringService(
        WalletBehaviorService(
            accounting_store,
            RecordedMarketEvidenceSource(
                [WalletMarketEvidence.model_validate(item) for item in evidence["evidence"]],
                MarketEvidenceCoverage.model_validate(evidence["coverage"]),
            ),
        ),
        WalletCopyabilityService(
            accounting_store,
            RecordedCopyabilityMarketPoolSource(
                [RecordedMarketPool.model_validate(item) for item in pools["pools"]],
                CopyabilityPoolCoverage.model_validate(pools["coverage"]),
            ),
        ),
        InMemoryResearchConfigurationStore(now=fixed_clock),
        InMemoryWalletScoringStore(now=fixed_clock),
        accounting_store,
    )
    client = TestClient(
        create_app(
            health_service=ReadyHealthService(),
            research_configuration_store=InMemoryResearchConfigurationStore(now=fixed_clock),
            token_store=InMemoryTokenStore(),
            market_state_store=market_store(),
            early_buyer_source=RecordedEarlyBuyerSource(
                pages=[
                    [
                        early_buyer_transaction(
                            WALLET_STRONG, "recorded-buy-strong", "2026-09-28T09:05:00Z"
                        )
                    ]
                ],
                coverage=early_buyer_coverage(),
            ),
            wallet_scoring_service=scoring_service,
            discovery_funnel_store=InMemoryDiscoveryFunnelStore(now=fixed_clock),
        )
    )
    assert (
        client.post(
            "/tokens",
            json={
                "event": launch_event(
                    TOKEN_ONE, "recorded-funnel-launch-0", "RSWAP"
                ).model_dump(mode="json")
            },
        ).status_code
        == 201
    )

    run = client.post("/discovery/funnel", json=FUNNEL_REQUEST).json()

    assert run["status"] == "COMPLETED"
    assert_stages_are_consistent(run)
    profitable = member_of(run, "PROFITABLE", WALLET_STRONG)
    assert profitable["outcome"] == "INCLUDED"
    assert reason_codes(profitable) == ["CLEAN_PROFITABILITY_AT_OR_ABOVE_MIDPOINT"]
    assert any("clean realized PnL 21.5 USD" in item for item in profitable["evidence"])
    assert profitable["coverage"][0]["complete"] is False
    scored = client.get(
        f"/wallets/{WALLET_STRONG}/score?as_of=2026-09-28T10:00:00Z"
    )
    assert scored.status_code == 200
    assert run["configuration_version"] == scored.json()["configuration_version"]


def test_discovery_funnel_run_rejects_an_inconsistent_stage_chain() -> None:
    run = Journey().client.post("/discovery/funnel", json=FUNNEL_REQUEST).json()
    assert run["status"] == "COMPLETED"

    oversized = json.loads(json.dumps(run["stages"]))
    oversized[2]["evaluated"] = 3
    with pytest.raises(ValidationError, match="evaluated must count every member"):
        DiscoveryFunnelRun.model_validate({**run, "stages": oversized})

    incomplete = json.loads(json.dumps(run["stages"]))[:-1]
    with pytest.raises(ValidationError, match="every stage in order"):
        DiscoveryFunnelRun.model_validate({**run, "stages": incomplete})

    unchained = json.loads(json.dumps(run["stages"]))
    unchained[4].update({"evaluated": 0, "included": 0, "excluded": 0, "unknown": 0})
    unchained[4]["members"] = []
    with pytest.raises(ValidationError, match="must evaluate every Wallet included by PROFITABLE"):
        DiscoveryFunnelRun.model_validate({**run, "stages": unchained})


def test_discovery_funnel_request_rejects_an_as_of_before_its_cohort() -> None:
    journey = Journey()

    response = journey.client.post(
        "/discovery/funnel", json={**FUNNEL_REQUEST, "as_of": "2026-09-28T09:59:00Z"}
    )

    assert response.status_code == 422
    assert "as_of must not be earlier than cohort.qualification_as_of" in response.text
    assert journey.client.get("/discovery/funnel/latest").status_code == 404
