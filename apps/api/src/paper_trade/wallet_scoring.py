"""Explainable Smart Wallet Scores and the reversible Smart Wallet Registry.

The module composes recorded Wallet behavior and recorded Copyability into a
weighted 0-100 score and recommends a Registry state from versioned
configuration.  Only clean PnL and clean FIFO closes are read, so
transfer-contaminated quantities cannot raise a score.  Missing evidence never
raises a score: it removes a component's weighted points and is reported as an
unknown rather than being assumed.
"""

import json
from collections.abc import Sequence
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Callable, Literal, Optional, Protocol

from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import text
from sqlalchemy.engine import RowMapping
from sqlalchemy.ext.asyncio import AsyncEngine

from paper_trade.realtime_tracking import SmartWalletSubscription
from paper_trade.research_configuration import (
    ResearchConfigurationStore,
    VersionedResearchConfiguration,
    WalletSettings,
)
from paper_trade.wallet_behavior import (
    BehaviorPeriod,
    WalletBehavior,
    WalletBehaviorStore,
    WalletBehaviorWindow,
)
from paper_trade.wallet_copyability import WalletCopyability, WalletCopyabilityStore

RegistryState = Literal["CANDIDATE", "WATCHLIST", "SMART_WALLET", "SUSPENDED", "REJECTED"]
ScoreComponentName = Literal[
    "profitability",
    "consistency",
    "copyability",
    "risk_quality",
    "entry_quality",
    "history_quality",
]
LeaderboardSort = Literal[
    "TOTAL_SCORE",
    "RECENT_ROI",
    "LONG_TERM_ROI",
    "RECENT_PNL",
    "LONG_TERM_PNL",
]
QualityPeriod = Literal["30D", "ALL_TIME"]
_SCORE_COMPONENT_NAMES: tuple[ScoreComponentName, ...] = (
    "profitability",
    "consistency",
    "copyability",
    "risk_quality",
    "entry_quality",
    "history_quality",
)
_RISK_FLAG_NAMES: tuple[str, ...] = (
    "TRANSFER_DERIVED_INVENTORY",
    "UNCLASSIFIED_ACTIVITY",
    "RAPID_TOKEN_ENTRY",
)


class WalletScoreModel(BaseModel):
    """Base document for Smart Wallet Score and Registry public contracts."""

    model_config = ConfigDict(extra="forbid")


class WalletScoreCoverage(WalletScoreModel):
    """One evidence source used by a score, including its declared gaps."""

    source: str = Field(min_length=1)
    complete: bool
    unknown_fields: list[str] = Field(default_factory=list)


class ScoreComponent(WalletScoreModel):
    """One explainable 0-100 component; ``None`` means the evidence is UNKNOWN."""

    name: ScoreComponentName
    score: Optional[float]
    weight: float = Field(ge=0, le=100)
    weighted_points: float = Field(ge=0, le=100)
    reasons: list[str] = Field(min_length=1)
    evidence: list[str] = Field(min_length=1)
    warnings: list[str] = Field(default_factory=list)
    unknowns: list[str] = Field(default_factory=list)


class WalletQualityPeriod(WalletScoreModel):
    """Recent or long-term quality retained so poor periods stay visible."""

    period: QualityPeriod
    starts_at: Optional[datetime]
    total_pnl_usd: Optional[float]
    realized_pnl_usd: float
    roi_percent: Optional[float]
    win_rate_percent: Optional[float]
    trade_count: int
    max_drawdown_usd: float


class WalletScore(WalletScoreModel):
    """The stored point-in-time score document for one Wallet."""

    address: str
    as_of: datetime
    configuration_id: str
    configuration_version: int = Field(ge=1)
    total_score: float = Field(ge=0, le=100)
    recommended_state: RegistryState
    components: list[ScoreComponent]
    quality: list[WalletQualityPeriod]
    reasons: list[str]
    warnings: list[str]
    evidence: list[str]
    unknowns: list[str]
    coverage: list[WalletScoreCoverage]


class WalletScoreVersion(WalletScoreModel):
    """One immutable stored score version."""

    address: str
    version: int = Field(ge=1)
    created_at: datetime
    configuration_id: str
    configuration_version: int = Field(ge=1)
    score: WalletScore


class RecordWalletScoreResult(WalletScoreModel):
    """Observable idempotency outcome of one score persistence."""

    created: bool
    version: WalletScoreVersion


class RecordWalletRegistryTransition(WalletScoreModel):
    """A Registry transition request; the store assigns its sequence version."""

    address: str
    from_state: RegistryState
    to_state: RegistryState
    reason: str = Field(min_length=1)
    evidence: list[str] = Field(min_length=1)
    as_of: datetime
    configuration_version: int = Field(ge=1)


class WalletRegistryTransition(WalletScoreModel):
    """One recorded, never permanent Registry transition."""

    address: str
    version: int = Field(ge=1)
    from_state: RegistryState
    to_state: RegistryState
    reason: str
    evidence: list[str]
    as_of: datetime
    configuration_version: int = Field(ge=1)
    created_at: datetime


class WalletRegistry(WalletScoreModel):
    """Current Registry state plus its full transition history."""

    address: str
    state: RegistryState
    transitions: list[WalletRegistryTransition]


class WalletScoreResult(WalletScoreModel):
    """Outcome of one scoring pass, including whether it changed anything."""

    address: str
    created: bool
    version: int = Field(ge=1)
    created_at: datetime
    transitioned: bool
    score: WalletScore


class WalletLeaderboardEntry(WalletScoreModel):
    """One leaderboard row with recent and long-term quality."""

    address: str
    total_score: float
    recommended_state: RegistryState
    as_of: datetime
    configuration_version: int = Field(ge=1)
    quality: list[WalletQualityPeriod]
    warnings: list[str]


class WalletReassessmentOutcome(WalletScoreModel):
    address: str
    created: bool
    version: int = Field(ge=1)
    recommended_state: RegistryState
    total_score: float
    transitioned: bool


class WalletScoreReassessment(WalletScoreModel):
    """Per-Wallet outcomes of one periodic reassessment."""

    as_of: datetime
    configuration_id: str
    configuration_version: int = Field(ge=1)
    outcomes: list[WalletReassessmentOutcome]


class WalletScoringStore(Protocol):
    """Durable persistence seam for score versions and Registry transitions."""

    async def record_score(self, score: WalletScore) -> RecordWalletScoreResult:
        """Persist a new score version, or return the identical existing version."""

    async def current_score(self, address: str, as_of: datetime) -> Optional[WalletScore]:
        """Return the latest score version computed at or before ``as_of``."""

    async def record_transition(
        self, request: RecordWalletRegistryTransition
    ) -> WalletRegistryTransition:
        """Persist a Registry transition unless it is already the latest one."""

    async def registry(self, address: str) -> WalletRegistry:
        """Return the current Registry state and its transition history."""


class WalletAddressStore(Protocol):
    """Enumeration seam for periodically reassessing every recorded Wallet."""

    async def list_wallets(self) -> list[str]:
        """Return every Wallet address with recorded activity."""


@dataclass
class _Assessment:
    score: Optional[float]
    reasons: list[str]
    evidence: list[str]
    warnings: list[str] = field(default_factory=list)
    unknowns: list[str] = field(default_factory=list)


def _json_document(document: WalletScoreModel) -> str:
    return json.dumps(document.model_dump(mode="json"), sort_keys=True, separators=(",", ":"))


def _json_value(value: Any) -> Any:
    return json.loads(value) if isinstance(value, str) else value


def _round(value: float) -> float:
    return round(value, 10)


def _clamp(value: float) -> float:
    return min(100.0, max(0.0, value))


def _usd(value: Optional[float]) -> str:
    return "UNKNOWN" if value is None else f"{value:g} USD"


def _percent(value: Optional[float]) -> str:
    return "UNKNOWN" if value is None else f"{value:g}%"


def _window(behavior: WalletBehavior, period: BehaviorPeriod) -> Optional[WalletBehaviorWindow]:
    return next((window for window in behavior.windows if window.period == period), None)


def _all_time(behavior: WalletBehavior) -> WalletBehaviorWindow:
    window = _window(behavior, "ALL_TIME")
    if window is None:
        raise ValueError("Wallet behavior must include an ALL_TIME window")
    return window


def _coverage(
    behavior: WalletBehavior, copyability: WalletCopyability
) -> list[WalletScoreCoverage]:
    sources = [
        WalletScoreCoverage(
            source=item.source,
            complete=item.complete,
            unknown_fields=list(item.unknown_fields),
        )
        for item in behavior.coverage
    ]
    sources.append(
        WalletScoreCoverage(
            source=copyability.coverage.provider,
            complete=copyability.coverage.complete,
            unknown_fields=list(copyability.coverage.unknown_fields),
        )
    )
    selected: dict[str, WalletScoreCoverage] = {}
    for source in sources:
        selected.setdefault(source.source, source)
    return [selected[source] for source in sorted(selected)]


def _profitability(window: WalletBehaviorWindow, settings: WalletSettings) -> _Assessment:
    target = settings.profitability_roi_target_percent
    roi = window.roi_percent
    evidence = [
        (
            f"ALL_TIME clean realized PnL {_usd(window.realized_pnl_usd)} and clean unrealized "
            f"PnL {_usd(window.unrealized_pnl_usd)} over {window.trade_count} closed trades."
        )
    ]
    if roi is None:
        return _Assessment(
            score=None,
            reasons=["Clean ROI is UNKNOWN, so profitability cannot be scored."],
            evidence=evidence,
            unknowns=[
                "profitability: clean ROI is UNKNOWN because no clean cost basis is recorded."
            ],
        )
    score = _clamp(50 * (1 + roi / target))
    return _Assessment(
        score=_round(score),
        reasons=[
            (
                f"Clean ALL_TIME ROI {_percent(roi)} against the configured "
                f"{_percent(target)} target scores {_round(score):g} out of 100."
            )
        ],
        evidence=evidence,
    )


def _consistency(window: WalletBehaviorWindow) -> _Assessment:
    win_rate = window.win_rate_percent
    top_one = window.consistency.profit_concentration.top_one_percent
    evidence = [
        (
            f"ALL_TIME profitable days {window.consistency.profitable_days}, weeks "
            f"{window.consistency.profitable_weeks}, months "
            f"{window.consistency.profitable_months}; winning/losing Tokens "
            f"{window.winning_tokens}/{window.losing_tokens}."
        )
    ]
    missing = [
        name
        for name, value in (("win_rate_percent", win_rate), ("top_one_concentration", top_one))
        if value is None
    ]
    if missing:
        return _Assessment(
            score=None,
            reasons=["Win rate and profit concentration are required to score consistency."],
            evidence=evidence,
            unknowns=[f"consistency: {', '.join(missing)} is UNKNOWN."],
        )
    assert win_rate is not None and top_one is not None
    score = _clamp((win_rate + (100 - top_one)) / 2)
    return _Assessment(
        score=_round(score),
        reasons=[
            (
                f"Win rate {_percent(win_rate)} and top-one profit concentration "
                f"{_percent(top_one)} average to {_round(score):g} out of 100."
            )
        ],
        evidence=evidence,
    )


def _copyability_component(
    copyability: WalletCopyability, settings: WalletSettings
) -> _Assessment:
    target = settings.profitability_roi_target_percent
    followers: list[float] = []
    worst_follower: Optional[float] = None
    worst_follower_label = "UNKNOWN"
    worst_decay: Optional[float] = None
    rejected = 0
    for outcome in copyability.outcomes:
        if outcome.status == "REJECTED":
            rejected += 1
        follower = outcome.follower_roi_percent
        decay = outcome.copy_decay_percent
        if follower is None or decay is None:
            continue
        followers.append(follower)
        if worst_follower is None or follower < worst_follower:
            worst_follower = follower
            worst_follower_label = (
                f"{outcome.follower_delay_ms} ms delay at {outcome.follower_size_sol:g} SOL"
            )
        if worst_decay is None or decay > worst_decay:
            worst_decay = decay
    warnings = []
    if rejected:
        warnings.append(
            f"{rejected} of {len(copyability.outcomes)} follower scenarios were rejected, so "
            "Copy Decay is measured only on the scenarios that filled."
        )
    if not followers or worst_follower is None or worst_decay is None:
        return _Assessment(
            score=None,
            reasons=["No follower scenario filled, so Copyability cannot be scored."],
            evidence=[f"{len(copyability.outcomes)} configured follower scenarios were evaluated."],
            warnings=warnings,
            unknowns=[
                "copyability: no configured delay and follower size produced a filled outcome."
            ],
        )
    follower_score = _clamp(50 * (1 + worst_follower / target))
    decay_score = _clamp(100 - worst_decay)
    score = (follower_score + decay_score) / 2
    return _Assessment(
        score=_round(score),
        reasons=[
            (
                f"The worst filled follower ROI {_percent(worst_follower)} at "
                f"{worst_follower_label} scores {_round(follower_score):g}, and the worst Copy "
                f"Decay {_percent(worst_decay)} scores {_round(decay_score):g}; they average to "
                f"{_round(score):g} out of 100."
            )
        ],
        evidence=[
            (
                f"{len(followers)} filled follower scenarios used recorded pool state after the "
                "configured delay."
            )
        ],
        warnings=warnings,
    )


def _risk_quality(
    behavior: WalletBehavior, window: WalletBehaviorWindow, settings: WalletSettings
) -> _Assessment:
    rug = window.meme.rug_exposure_rate_percent
    dead = window.meme.dead_token_exposure_rate_percent
    flags = [flag.name for flag in behavior.flags if flag.name in _RISK_FLAG_NAMES]
    penalty = settings.risk_flag_penalty * len(flags)
    evidence = [
        (
            f"ALL_TIME rug exposure {_percent(rug)} and dead Token exposure {_percent(dead)}; "
            f"evidence-backed risk flags: {', '.join(flags) if flags else 'none'}."
        )
    ]
    missing = [
        name
        for name, value in (
            ("rug_exposure_rate_percent", rug),
            ("dead_token_exposure_rate_percent", dead),
        )
        if value is None
    ]
    if missing:
        return _Assessment(
            score=None,
            reasons=["Rug and dead Token exposure are required to score risk quality."],
            evidence=evidence,
            unknowns=[f"risk_quality: {', '.join(missing)} is UNKNOWN."],
        )
    assert rug is not None and dead is not None
    score = _clamp(100 - rug - dead - penalty)
    return _Assessment(
        score=_round(score),
        reasons=[
            (
                f"100 minus {_percent(rug)} rug exposure, {_percent(dead)} dead Token exposure, "
                f"and {penalty:g} points for {len(flags)} risk flags scores {_round(score):g}."
            )
        ],
        evidence=evidence,
    )


def _entry_quality(window: WalletBehaviorWindow) -> _Assessment:
    sub_100k = window.meme.sub_100k_entry_rate_percent
    rug = window.meme.rug_exposure_rate_percent
    evidence = [
        (
            f"ALL_TIME entries below 100k market cap {_percent(sub_100k)}, below 500k "
            f"{_percent(window.meme.sub_500k_entry_rate_percent)}, early entries "
            f"{_percent(window.meme.early_entry_rate_percent)}."
        )
    ]
    missing = [
        name
        for name, value in (
            ("sub_100k_entry_rate_percent", sub_100k),
            ("rug_exposure_rate_percent", rug),
        )
        if value is None
    ]
    if missing:
        return _Assessment(
            score=None,
            reasons=["Entry size and rug exposure are required to score entry quality."],
            evidence=evidence,
            unknowns=[f"entry_quality: {', '.join(missing)} is UNKNOWN."],
        )
    assert sub_100k is not None and rug is not None
    score = _clamp((sub_100k + (100 - rug)) / 2)
    return _Assessment(
        score=_round(score),
        reasons=[
            (
                f"Small-market-cap entry rate {_percent(sub_100k)} and non-rugged exposure "
                f"{_percent(100 - rug)} average to {_round(score):g} out of 100."
            )
        ],
        evidence=evidence,
    )


def _history_quality(
    behavior: WalletBehavior,
    copyability: WalletCopyability,
    window: WalletBehaviorWindow,
    settings: WalletSettings,
) -> _Assessment:
    coverage = _coverage(behavior, copyability)
    complete = sum(1 for source in coverage if source.complete)
    coverage_score = 100 * complete / len(coverage)
    trade_score = _clamp(window.trade_count / settings.minimum_trades * 100)
    score = (trade_score + coverage_score) / 2
    return _Assessment(
        score=_round(score),
        reasons=[
            (
                f"{window.trade_count} ALL_TIME closed trades against the configured minimum "
                f"{settings.minimum_trades} scores {_round(trade_score):g}, and {complete} of "
                f"{len(coverage)} coverage sources are complete; they average to "
                f"{_round(score):g} out of 100."
            )
        ],
        evidence=[
            (
                "Coverage sources: "
                + "; ".join(
                    f"{source.source} {'complete' if source.complete else 'incomplete'}"
                    for source in coverage
                )
                + "."
            )
        ],
    )


def _quality_period(period: QualityPeriod, window: WalletBehaviorWindow) -> WalletQualityPeriod:
    return WalletQualityPeriod(
        period=period,
        starts_at=window.starts_at,
        total_pnl_usd=window.total_pnl_usd,
        realized_pnl_usd=window.realized_pnl_usd,
        roi_percent=window.roi_percent,
        win_rate_percent=window.win_rate_percent,
        trade_count=window.trade_count,
        max_drawdown_usd=window.max_drawdown_usd,
    )


def _recommend_state(
    total_score: float,
    all_time: WalletBehaviorWindow,
    components: Sequence[ScoreComponent],
    coverage: Sequence[WalletScoreCoverage],
    settings: WalletSettings,
) -> tuple[RegistryState, list[str], list[str], list[str]]:
    """Return the recommended state with its reasons, evidence, and warnings."""
    evidence = [
        (
            f"Total score {total_score:g} compared against thresholds rejection "
            f"{settings.rejection_score:g}, suspension {settings.suspension_score:g}, Smart Wallet "
            f"{settings.minimum_score:g}, and minimum closed trades {settings.minimum_trades}."
        )
    ]
    if all_time.trade_count < settings.minimum_trades:
        return (
            "CANDIDATE",
            [
                (
                    f"ALL_TIME closed trades {all_time.trade_count} is below the configured "
                    f"minimum {settings.minimum_trades}, so the Wallet cannot be judged yet."
                )
            ],
            evidence,
            [
                (
                    "Registry state is provisional because recorded closed trades are below the "
                    "configured minimum."
                )
            ],
        )
    if total_score < settings.rejection_score:
        return (
            "REJECTED",
            [
                (
                    f"Total score {total_score:g} is below the rejection threshold "
                    f"{settings.rejection_score:g}."
                )
            ],
            evidence,
            [],
        )
    if total_score < settings.suspension_score:
        return (
            "SUSPENDED",
            [
                (
                    f"Total score {total_score:g} is below the suspension threshold "
                    f"{settings.suspension_score:g}."
                )
            ],
            evidence,
            [],
        )
    if total_score < settings.minimum_score:
        return (
            "WATCHLIST",
            [
                (
                    f"Total score {total_score:g} is below the Smart Wallet threshold "
                    f"{settings.minimum_score:g}."
                )
            ],
            evidence,
            [],
        )
    blockers = [
        f"Component {name} is UNKNOWN." for name in _unknown_component_names(components)
    ] + [
        f"Coverage from {source} is incomplete."
        for source in sorted({item.source for item in coverage if not item.complete})
    ]
    if blockers:
        return (
            "WATCHLIST",
            [
                (
                    f"Total score {total_score:g} meets the Smart Wallet threshold "
                    f"{settings.minimum_score:g}, but the Wallet does not pass every gate."
                )
            ],
            evidence + blockers,
            blockers,
        )
    return (
        "SMART_WALLET",
        [
            (
                f"Total score {total_score:g} meets the Smart Wallet threshold "
                f"{settings.minimum_score:g} with known components and complete coverage."
            )
        ],
        evidence,
        [],
    )


def _unknown_component_names(components: Sequence[ScoreComponent]) -> list[str]:
    return [component.name for component in components if component.score is None]


class WalletScoringService:
    """Score recorded behavior and Copyability, then maintain Registry state."""

    def __init__(
        self,
        behavior_store: WalletBehaviorStore,
        copyability_store: WalletCopyabilityStore,
        configuration_store: ResearchConfigurationStore,
        scoring_store: WalletScoringStore,
        wallet_store: WalletAddressStore,
    ) -> None:
        self._behavior_store = behavior_store
        self._copyability_store = copyability_store
        self._configuration_store = configuration_store
        self._scoring_store = scoring_store
        self._wallet_store = wallet_store

    async def score(self, address: str, as_of: datetime) -> WalletScoreResult:
        configuration = await self._configuration_store.get_active()
        return await self._score(address, as_of, configuration)

    async def current_score(self, address: str, as_of: datetime) -> Optional[WalletScore]:
        return await self._scoring_store.current_score(address, as_of)

    async def registry(self, address: str) -> WalletRegistry:
        return await self._scoring_store.registry(address)

    async def smart_wallets(self, as_of: datetime) -> list[SmartWalletSubscription]:
        """Return every Wallet whose current Registry state is SMART_WALLET."""
        subscriptions: list[SmartWalletSubscription] = []
        for address in await self._wallet_store.list_wallets():
            registry = await self._scoring_store.registry(address)
            if registry.state != "SMART_WALLET":
                continue
            score = await self._scoring_store.current_score(address, as_of)
            subscriptions.append(
                SmartWalletSubscription(
                    address=address,
                    score=None if score is None else score.total_score,
                    as_of=as_of,
                )
            )
        return subscriptions

    async def leaderboard(
        self,
        as_of: datetime,
        *,
        registry_state: Optional[RegistryState] = None,
        sort: LeaderboardSort = "TOTAL_SCORE",
        limit: Optional[int] = None,
    ) -> list[WalletLeaderboardEntry]:
        entries: list[WalletLeaderboardEntry] = []
        for address in await self._wallet_store.list_wallets():
            score = await self._scoring_store.current_score(address, as_of)
            if score is None:
                continue
            if registry_state is not None and score.recommended_state != registry_state:
                continue
            entries.append(
                WalletLeaderboardEntry(
                    address=score.address,
                    total_score=score.total_score,
                    recommended_state=score.recommended_state,
                    as_of=score.as_of,
                    configuration_version=score.configuration_version,
                    quality=score.quality,
                    warnings=score.warnings,
                )
            )
        entries.sort(key=lambda entry: _sort_key(entry, sort))
        return entries[:limit] if limit is not None else entries

    async def reassess_all(self, as_of: datetime) -> WalletScoreReassessment:
        configuration = await self._configuration_store.get_active()
        outcomes: list[WalletReassessmentOutcome] = []
        for address in await self._wallet_store.list_wallets():
            try:
                result = await self._score(address, as_of, configuration)
            except KeyError:
                continue
            outcomes.append(
                WalletReassessmentOutcome(
                    address=result.address,
                    created=result.created,
                    version=result.version,
                    recommended_state=result.score.recommended_state,
                    total_score=result.score.total_score,
                    transitioned=result.transitioned,
                )
            )
        return WalletScoreReassessment(
            as_of=as_of,
            configuration_id=str(configuration.id),
            configuration_version=configuration.version,
            outcomes=outcomes,
        )

    async def _score(
        self,
        address: str,
        as_of: datetime,
        configuration: VersionedResearchConfiguration,
    ) -> WalletScoreResult:
        behavior = await self._behavior_store.behavior(address, as_of)
        copyability = await self._copyability_store.copyability(address, as_of)
        score = self._calculate(address, as_of, behavior, copyability, configuration)
        recorded = await self._scoring_store.record_score(score)
        registry = await self._scoring_store.registry(address)
        transitioned = False
        if registry.state != score.recommended_state:
            await self._scoring_store.record_transition(
                RecordWalletRegistryTransition(
                    address=address,
                    from_state=registry.state,
                    to_state=score.recommended_state,
                    reason=(
                        f"Reassessment under configuration version {configuration.version} scored "
                        f"{score.total_score:g} and recommended {score.recommended_state}."
                    ),
                    evidence=score.evidence,
                    as_of=as_of,
                    configuration_version=configuration.version,
                )
            )
            transitioned = True
        return WalletScoreResult(
            address=address,
            created=recorded.created,
            version=recorded.version.version,
            created_at=recorded.version.created_at,
            transitioned=transitioned,
            score=recorded.version.score,
        )

    def _calculate(
        self,
        address: str,
        as_of: datetime,
        behavior: WalletBehavior,
        copyability: WalletCopyability,
        configuration: VersionedResearchConfiguration,
    ) -> WalletScore:
        settings = configuration.configuration.wallet
        weights = settings.score_weights
        all_time = _all_time(behavior)
        weights_by_name: dict[ScoreComponentName, float] = {
            "profitability": weights.profitability,
            "consistency": weights.consistency,
            "copyability": weights.copyability,
            "risk_quality": weights.risk_quality,
            "entry_quality": weights.entry_quality,
            "history_quality": weights.history_quality,
        }
        assessments: dict[ScoreComponentName, _Assessment] = {
            "profitability": _profitability(all_time, settings),
            "consistency": _consistency(all_time),
            "copyability": _copyability_component(copyability, settings),
            "risk_quality": _risk_quality(behavior, all_time, settings),
            "entry_quality": _entry_quality(all_time),
            "history_quality": _history_quality(behavior, copyability, all_time, settings),
        }
        components = [
            _component(name, weights_by_name[name], assessments[name])
            for name in _SCORE_COMPONENT_NAMES
        ]
        total_score = _round(sum(component.weighted_points for component in components))
        coverage = _coverage(behavior, copyability)
        state, reasons, evidence, registry_warnings = _recommend_state(
            total_score, all_time, components, coverage, settings
        )
        quality: list[WalletQualityPeriod] = []
        for period in ("30D", "ALL_TIME"):
            window = _window(behavior, period)
            if window is not None:
                quality.append(_quality_period(period, window))
        warnings = list(
            dict.fromkeys(
                [
                    *behavior.warnings,
                    *copyability.warnings,
                    *registry_warnings,
                    *[warning for component in components for warning in component.warnings],
                ]
            )
        )
        unknowns = list(
            dict.fromkeys(
                [unknown for component in components for unknown in component.unknowns]
            )
        )
        return WalletScore(
            address=address,
            as_of=as_of,
            configuration_id=str(configuration.id),
            configuration_version=configuration.version,
            total_score=total_score,
            recommended_state=state,
            components=components,
            quality=quality,
            reasons=[
                (
                    f"Total score {total_score:g} is the weight-normalized sum of the configured "
                    "components."
                ),
                *reasons,
            ],
            warnings=warnings,
            evidence=evidence,
            unknowns=unknowns,
            coverage=coverage,
        )


def _component(name: ScoreComponentName, weight: float, assessment: _Assessment) -> ScoreComponent:
    return ScoreComponent(
        name=name,
        score=assessment.score,
        weight=weight,
        weighted_points=_round(weight * (assessment.score or 0.0) / 100),
        reasons=assessment.reasons,
        evidence=assessment.evidence,
        warnings=assessment.warnings,
        unknowns=assessment.unknowns,
    )


def _sort_key(
    entry: WalletLeaderboardEntry, sort: LeaderboardSort
) -> tuple[int, float, str]:
    if sort == "TOTAL_SCORE":
        return (0, -entry.total_score, entry.address)
    period: QualityPeriod = "30D" if sort.startswith("RECENT") else "ALL_TIME"
    window = next(
        (quality for quality in entry.quality if quality.period == period),
        None,
    )
    if window is None:
        return (1, 0.0, entry.address)
    value = window.total_pnl_usd if sort.endswith("PNL") else window.roi_percent
    if value is None:
        return (1, 0.0, entry.address)
    return (0, -value, entry.address)


class InMemoryWalletScoringStore:
    """Deterministic score-version and Registry store used by HTTP tests."""

    def __init__(
        self, *, now: Callable[[], datetime] = lambda: datetime.now(timezone.utc)
    ) -> None:
        self._now = now
        self._versions: dict[str, list[WalletScoreVersion]] = {}
        self._transitions: dict[str, list[WalletRegistryTransition]] = {}

    async def record_score(self, score: WalletScore) -> RecordWalletScoreResult:
        versions = self._versions.setdefault(score.address, [])
        if versions and versions[-1].score == score:
            return RecordWalletScoreResult(created=False, version=versions[-1])
        version = WalletScoreVersion(
            address=score.address,
            version=len(versions) + 1,
            created_at=self._now(),
            configuration_id=score.configuration_id,
            configuration_version=score.configuration_version,
            score=score,
        )
        versions.append(version)
        return RecordWalletScoreResult(created=True, version=version)

    async def current_score(self, address: str, as_of: datetime) -> Optional[WalletScore]:
        eligible = [
            version
            for version in self._versions.get(address, [])
            if version.score.as_of <= as_of
        ]
        if not eligible:
            return None
        return max(eligible, key=lambda version: version.version).score

    async def record_transition(
        self, request: RecordWalletRegistryTransition
    ) -> WalletRegistryTransition:
        transitions = self._transitions.setdefault(request.address, [])
        if transitions:
            latest = transitions[-1]
            if latest.to_state == request.to_state and latest.as_of == request.as_of:
                return latest
        transition = WalletRegistryTransition(
            address=request.address,
            version=len(transitions) + 1,
            from_state=request.from_state,
            to_state=request.to_state,
            reason=request.reason,
            evidence=list(request.evidence),
            as_of=request.as_of,
            configuration_version=request.configuration_version,
            created_at=self._now(),
        )
        transitions.append(transition)
        return transition

    async def registry(self, address: str) -> WalletRegistry:
        transitions = list(self._transitions.get(address, []))
        return WalletRegistry(
            address=address,
            state=transitions[-1].to_state if transitions else "CANDIDATE",
            transitions=transitions,
        )


class PostgresWalletScoringStore:
    """PostgreSQL source of truth for score versions and Registry transitions."""

    def __init__(self, engine: AsyncEngine) -> None:
        self._engine = engine

    async def record_score(self, score: WalletScore) -> RecordWalletScoreResult:
        async with self._engine.begin() as connection:
            await connection.execute(
                text("SELECT pg_advisory_xact_lock(hashtext(:address))"),
                {"address": score.address},
            )
            latest = await connection.execute(
                text(
                    """
                    SELECT version, created_at, configuration_id, configuration_version, score
                    FROM wallet_score_versions
                    WHERE wallet_address = :wallet_address
                    ORDER BY version DESC
                    LIMIT 1
                    """
                ),
                {"wallet_address": score.address},
            )
            row = latest.mappings().one_or_none()
            if row is not None:
                existing = self._version_from_row(score.address, row)
                if existing.score == score:
                    return RecordWalletScoreResult(created=False, version=existing)
            next_version = await connection.scalar(
                text(
                    """
                    SELECT COALESCE(MAX(version), 0) + 1
                    FROM wallet_score_versions
                    WHERE wallet_address = :wallet_address
                    """
                ),
                {"wallet_address": score.address},
            )
            inserted = await connection.execute(
                text(
                    """
                    INSERT INTO wallet_score_versions (
                        wallet_address, version, as_of, configuration_id,
                        configuration_version, score
                    ) VALUES (
                        :wallet_address, :version, :as_of, CAST(:configuration_id AS UUID),
                        :configuration_version, CAST(:score AS JSONB)
                    )
                    RETURNING version, created_at, configuration_id, configuration_version, score
                    """
                ),
                {
                    "wallet_address": score.address,
                    "version": int(next_version or 1),
                    "as_of": score.as_of,
                    "configuration_id": score.configuration_id,
                    "configuration_version": score.configuration_version,
                    "score": _json_document(score),
                },
            )
            return RecordWalletScoreResult(
                created=True,
                version=self._version_from_row(score.address, inserted.mappings().one()),
            )

    async def current_score(self, address: str, as_of: datetime) -> Optional[WalletScore]:
        async with self._engine.connect() as connection:
            result = await connection.execute(
                text(
                    """
                    SELECT version, created_at, configuration_id, configuration_version, score
                    FROM wallet_score_versions
                    WHERE wallet_address = :wallet_address AND as_of <= :as_of
                    ORDER BY as_of DESC, version DESC
                    LIMIT 1
                    """
                ),
                {"wallet_address": address, "as_of": as_of},
            )
            row = result.mappings().one_or_none()
        return None if row is None else self._version_from_row(address, row).score

    async def record_transition(
        self, request: RecordWalletRegistryTransition
    ) -> WalletRegistryTransition:
        async with self._engine.begin() as connection:
            await connection.execute(
                text("SELECT pg_advisory_xact_lock(hashtext(:address))"),
                {"address": request.address},
            )
            latest = await connection.execute(
                text(
                    """
                    SELECT version, from_state, to_state, reason, evidence, as_of,
                           configuration_version, created_at
                    FROM wallet_registry_transitions
                    WHERE wallet_address = :wallet_address
                    ORDER BY version DESC
                    LIMIT 1
                    """
                ),
                {"wallet_address": request.address},
            )
            row = latest.mappings().one_or_none()
            if row is not None:
                existing = self._transition_from_row(request.address, row)
                if existing.to_state == request.to_state and existing.as_of == request.as_of:
                    return existing
            next_version = await connection.scalar(
                text(
                    """
                    SELECT COALESCE(MAX(version), 0) + 1
                    FROM wallet_registry_transitions
                    WHERE wallet_address = :wallet_address
                    """
                ),
                {"wallet_address": request.address},
            )
            inserted = await connection.execute(
                text(
                    """
                    INSERT INTO wallet_registry_transitions (
                        wallet_address, version, from_state, to_state, reason, evidence, as_of,
                        configuration_version
                    ) VALUES (
                        :wallet_address, :version, :from_state, :to_state, :reason,
                        CAST(:evidence AS JSONB), :as_of, :configuration_version
                    )
                    RETURNING version, from_state, to_state, reason, evidence, as_of,
                              configuration_version, created_at
                    """
                ),
                {
                    "wallet_address": request.address,
                    "version": int(next_version or 1),
                    "from_state": request.from_state,
                    "to_state": request.to_state,
                    "reason": request.reason,
                    "evidence": json.dumps(list(request.evidence)),
                    "as_of": request.as_of,
                    "configuration_version": request.configuration_version,
                },
            )
            return self._transition_from_row(request.address, inserted.mappings().one())

    async def registry(self, address: str) -> WalletRegistry:
        async with self._engine.connect() as connection:
            result = await connection.execute(
                text(
                    """
                    SELECT version, from_state, to_state, reason, evidence, as_of,
                           configuration_version, created_at
                    FROM wallet_registry_transitions
                    WHERE wallet_address = :wallet_address
                    ORDER BY version
                    """
                ),
                {"wallet_address": address},
            )
            transitions = [
                self._transition_from_row(address, row) for row in result.mappings()
            ]
        return WalletRegistry(
            address=address,
            state=transitions[-1].to_state if transitions else "CANDIDATE",
            transitions=transitions,
        )

    @staticmethod
    def _version_from_row(address: str, row: RowMapping) -> WalletScoreVersion:
        return WalletScoreVersion(
            address=address,
            version=int(row["version"]),
            created_at=row["created_at"],
            configuration_id=str(row["configuration_id"]),
            configuration_version=int(row["configuration_version"]),
            score=WalletScore.model_validate(_json_value(row["score"])),
        )

    @staticmethod
    def _transition_from_row(address: str, row: RowMapping) -> WalletRegistryTransition:
        return WalletRegistryTransition(
            address=address,
            version=int(row["version"]),
            from_state=row["from_state"],
            to_state=row["to_state"],
            reason=str(row["reason"]),
            evidence=[str(item) for item in _json_value(row["evidence"])],
            as_of=row["as_of"],
            configuration_version=int(row["configuration_version"]),
            created_at=row["created_at"],
        )
