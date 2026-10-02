"""Detect, update, and invalidate Smart Wallet Clusters per Token.

A Cluster is at least N Contributing-independent Wallets buying the same Token
inside a configured window.  The detector consumes qualifying Smart Wallet
activity, collapses strongly related Wallets into a Contributing-independent
count through the relationship module, and records raw Wallet count,
average/weighted quality, total SOL, first and last buy, and buy velocity.

Duplicate realtime activity is suppressed by signature/slot idempotency, so a
reconnect or replay cannot inflate counts or volume.  A materially changed
Cluster supersedes its previous version, while a Cluster whose window has
elapsed or whose thresholds are no longer met is invalidated in place.  Every
version keeps the evidence, relationships, timing, and coverage used to produce
it, and missing wallet quality never becomes a safe Cluster.
"""

import json
from collections.abc import Callable, Sequence
from datetime import datetime, timedelta, timezone
from typing import Any, Literal, Optional, Protocol

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator
from sqlalchemy import text
from sqlalchemy.engine import RowMapping
from sqlalchemy.ext.asyncio import AsyncEngine

from paper_trade.launch_events import Commitment, _is_solana_public_key
from paper_trade.realtime_tracking import RealtimeCoverage
from paper_trade.research_configuration import (
    ClusterScoreWeighting,
    ClusterSettings,
    ResearchConfigurationStore,
    VersionedResearchConfiguration,
)
from paper_trade.wallet_relationships import ContributingIndependentCount

ClusterMovementType = Literal["BUY", "SELL"]
ClusterStatus = Literal["ACTIVE", "SUPERSEDED", "INVALIDATED"]
ClusterInvalidationReason = Literal["EXPIRED", "THRESHOLD_LOST"]


class ClusterModel(BaseModel):
    """Base document for Smart Wallet Cluster public contracts."""

    model_config = ConfigDict(extra="forbid")


class ClusterCoverage(ClusterModel):
    """One evidence source behind a Cluster, including its declared gaps."""

    source: str = Field(min_length=1)
    complete: bool
    unknown_fields: list[str] = Field(default_factory=list)


class ClusterActivity(ClusterModel):
    """One qualifying Smart Wallet movement offered to the Cluster Detector."""

    event_id: str = Field(min_length=1)
    wallet_address: str
    token_address: str
    movement_type: ClusterMovementType
    quantity: float = Field(gt=0)
    sol_amount: float = Field(ge=0)
    notional_usd: Optional[float] = Field(default=None, ge=0)
    wallet_score: Optional[float] = Field(default=None, ge=0, le=100)
    score_as_of: Optional[datetime] = None
    signature: str = Field(min_length=1)
    slot: int = Field(ge=0)
    chain_time: datetime
    observed_at: datetime
    commitment: Commitment
    eligible_for_decisions: bool
    evidence: list[str] = Field(min_length=1)
    coverage: RealtimeCoverage

    @field_validator("wallet_address", "token_address")
    @classmethod
    def validate_solana_public_key(cls, value: str) -> str:
        if not _is_solana_public_key(value):
            raise ValueError("must be a valid Solana public key")
        return value

    @model_validator(mode="after")
    def validate_activity(self) -> "ClusterActivity":
        if self.observed_at < self.chain_time:
            raise ValueError("observed_at must not be earlier than chain_time")
        if self.commitment != self.coverage.commitment:
            raise ValueError("activity commitment must match its coverage commitment")
        if self.eligible_for_decisions != (self.commitment == "confirmed"):
            raise ValueError("only confirmed activity may be eligible for decisions")
        if self.notional_usd is None and "notional_usd" not in self.coverage.unknown_fields:
            raise ValueError(
                "a BUY or SELL without a valuation must declare notional_usd unknown"
            )
        if (self.wallet_score is None) != (self.score_as_of is None):
            raise ValueError("wallet_score and score_as_of must be provided together")
        return self


class ClusterActivitySource(Protocol):
    """Replaceable Adapter contract for qualifying Smart Wallet activity."""

    async def activity(self, as_of: datetime) -> Sequence[ClusterActivity]:
        """Return qualifying activity no later than ``as_of`` in deterministic order."""


class ContributingIndependentCalculator(Protocol):
    """Seam that collapses related Wallets into a Contributing-independent count."""

    async def contributing_independent(
        self, wallets: Sequence[str], as_of: datetime
    ) -> ContributingIndependentCount:
        """Return the raw and Contributing-independent counts for ``wallets``."""


class RecordedClusterActivitySource:
    """Fixture-only activity Adapter; it performs no network calls."""

    def __init__(self, activities: Sequence[ClusterActivity]) -> None:
        self._activities = [
            ClusterActivity.model_validate(activity.model_dump()) for activity in activities
        ]

    async def activity(self, as_of: datetime) -> Sequence[ClusterActivity]:
        return sorted(
            (
                activity
                for activity in self._activities
                if activity.observed_at <= as_of
            ),
            key=lambda activity: (
                activity.chain_time,
                activity.slot,
                activity.signature,
                activity.wallet_address,
            ),
        )


class ClusterWalletContribution(ClusterModel):
    """One Wallet's recorded contribution to a Cluster."""

    wallet_address: str
    wallet_score: Optional[float] = Field(default=None, ge=0, le=100)
    score_as_of: Optional[datetime] = None
    total_sol: float = Field(ge=0)
    buy_count: int = Field(ge=1)
    first_buy_at: datetime
    last_buy_at: datetime
    independent: bool
    evidence: list[str] = Field(min_length=1)

    @field_validator("wallet_address")
    @classmethod
    def validate_solana_public_key(cls, value: str) -> str:
        if not _is_solana_public_key(value):
            raise ValueError("must be a valid Solana public key")
        return value


class WalletCluster(ClusterModel):
    """One Token's Cluster content; the store assigns its version and timestamp."""

    token_address: str
    status: ClusterStatus
    status_reason: str = Field(min_length=1)
    superseded_by_version: Optional[int] = Field(default=None, ge=1)
    as_of: datetime
    configuration_id: str
    configuration_version: int = Field(ge=1)
    window_seconds: int = Field(ge=1)
    score_weighting: ClusterScoreWeighting
    raw_wallet_count: int = Field(ge=0)
    contributing_independent_wallet_count: int = Field(ge=0)
    average_wallet_score: Optional[float] = Field(default=None, ge=0, le=100)
    weighted_wallet_score: Optional[float] = Field(default=None, ge=0, le=100)
    total_sol: float = Field(ge=0)
    total_notional_usd: Optional[float] = Field(default=None, ge=0)
    buy_count: int = Field(ge=0)
    first_buy_at: Optional[datetime] = None
    last_buy_at: Optional[datetime] = None
    window_span_seconds: Optional[float] = Field(default=None, ge=0)
    buy_velocity_per_minute: Optional[float] = Field(default=None, ge=0)
    wallets: list[ClusterWalletContribution]
    contributing_independent: ContributingIndependentCount
    activity: list[ClusterActivity]
    evidence: list[str] = Field(min_length=1)
    unknowns: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    coverage: list[ClusterCoverage] = Field(min_length=1)

    @field_validator("token_address")
    @classmethod
    def validate_token_address(cls, value: str) -> str:
        if not _is_solana_public_key(value):
            raise ValueError("token_address must be a valid Solana public key")
        return value

    @model_validator(mode="after")
    def validate_counts(self) -> "WalletCluster":
        if (
            self.contributing_independent_wallet_count
            > self.raw_wallet_count
        ):
            raise ValueError(
                "the Contributing-independent count must not exceed the raw Wallet count"
            )
        if self.raw_wallet_count != self.contributing_independent.raw_wallet_count:
            raise ValueError("the raw Wallet count must match the independence calculation")
        if (
            self.contributing_independent_wallet_count
            != self.contributing_independent.contributing_independent_wallet_count
        ):
            raise ValueError(
                "the Contributing-independent count must match the independence calculation"
            )
        if self.buy_count != len(self.activity):
            raise ValueError("buy_count must equal the recorded activity")
        if self.wallets and (self.first_buy_at is None or self.last_buy_at is None):
            raise ValueError("a Cluster with Wallets must record its first and last buy")
        return self


class StoredWalletCluster(ClusterModel):
    """One immutable Cluster version and the time it was recorded."""

    token_address: str
    version: int = Field(ge=1)
    created_at: datetime
    cluster: WalletCluster


class WalletClusterDetail(ClusterModel):
    """Current Cluster state plus every superseded and invalidated version."""

    token_address: str
    current: StoredWalletCluster
    history: list[StoredWalletCluster]

    @field_validator("token_address")
    @classmethod
    def validate_token_address(cls, value: str) -> str:
        if not _is_solana_public_key(value):
            raise ValueError("token_address must be a valid Solana public key")
        return value


class RecordClusterActivityResult(ClusterModel):
    """Observable idempotency outcome of one qualifying activity persistence."""

    created: bool
    activity: ClusterActivity


class RecordWalletClusterResult(ClusterModel):
    """Observable outcome of one Cluster version persistence."""

    created: bool
    version: int = Field(ge=1)
    created_at: datetime
    cluster: WalletCluster


class ClusterDetection(ClusterModel):
    """Counters and current state from one detection pass."""

    as_of: datetime
    configuration_id: str
    configuration_version: int = Field(ge=1)
    received: int = Field(ge=0)
    recorded: int = Field(ge=0)
    duplicates: int = Field(ge=0)
    created_clusters: int = Field(ge=0)
    updated_clusters: int = Field(ge=0)
    invalidated_clusters: int = Field(ge=0)
    unchanged_clusters: int = Field(ge=0)
    clusters: list[StoredWalletCluster]
    warnings: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_counters(self) -> "ClusterDetection":
        if self.received != self.recorded + self.duplicates:
            raise ValueError("received activity must equal recorded and duplicate activity")
        return self


class WalletClusterStore(Protocol):
    """Durable persistence seam for Cluster activity and versions."""

    async def record_activity(
        self, activity: ClusterActivity
    ) -> RecordClusterActivityResult:
        """Persist activity unless its signature/slot idempotency key is recorded."""

    async def activity(self, token_address: str, as_of: datetime) -> list[ClusterActivity]:
        """Return every recorded activity for a Token at or before ``as_of``."""

    async def tokens(self) -> list[str]:
        """Return every Token with recorded activity, in deterministic order."""

    async def record(self, cluster: WalletCluster) -> RecordWalletClusterResult:
        """Append a Cluster version, or return the identical latest version."""

    async def transition_status(
        self,
        token_address: str,
        version: int,
        status: ClusterStatus,
        status_reason: str,
        superseded_by_version: Optional[int] = None,
    ) -> StoredWalletCluster:
        """Mark a stored version's status without changing its recorded evidence."""

    async def current(
        self, token_address: str, as_of: datetime
    ) -> Optional[StoredWalletCluster]:
        """Return the latest version recorded at or before ``as_of``."""

    async def history(
        self, token_address: str, as_of: datetime
    ) -> list[StoredWalletCluster]:
        """Return every version recorded at or before ``as_of``, newest first."""

    async def live(self, as_of: datetime) -> list[StoredWalletCluster]:
        """Return every Token whose current version at ``as_of`` is ACTIVE."""


def _idempotency_key(activity: ClusterActivity) -> str:
    return ":".join(
        (
            activity.signature,
            str(activity.slot),
            activity.wallet_address,
            activity.token_address,
            activity.movement_type,
        )
    )


def _round(value: float) -> float:
    return round(value, 4)


def _json_document(document: BaseModel) -> str:
    return json.dumps(document.model_dump(mode="json"), sort_keys=True, separators=(",", ":"))


def _json_value(value: Any) -> Any:
    return json.loads(value) if isinstance(value, str) else value


def _is_expired(cluster: WalletCluster, as_of: datetime) -> bool:
    if cluster.last_buy_at is None:
        return True
    return cluster.last_buy_at + timedelta(seconds=cluster.window_seconds) < as_of


def _weighted_score(
    contributions: Sequence[ClusterWalletContribution],
    weighting: ClusterScoreWeighting,
    average: Optional[float],
) -> Optional[float]:
    known = [
        (contribution.wallet_score, contribution.total_sol)
        for contribution in contributions
        if contribution.wallet_score is not None
    ]
    if not known:
        return None
    if weighting == "EQUAL":
        return average
    if weighting == "WALLET_SCORE":
        total_score = sum(score for score, _ in known)
        if total_score <= 0:
            return average
        return _round(sum(score * score for score, _ in known) / total_score)
    total_sol = sum(sol for _, sol in known)
    if total_sol <= 0:
        return average
    return _round(sum(score * sol for score, sol in known) / total_sol)


def _coverage(activities: Sequence[ClusterActivity]) -> list[ClusterCoverage]:
    selected: dict[str, ClusterCoverage] = {}
    for activity in activities:
        candidate = ClusterCoverage(
            source=activity.coverage.provider,
            complete=activity.coverage.complete,
            unknown_fields=list(activity.coverage.unknown_fields),
        )
        existing = selected.get(candidate.source)
        if existing is None or (existing.complete and not candidate.complete):
            selected[candidate.source] = candidate
    if not selected:
        selected["NO_RECORDED_ACTIVITY"] = ClusterCoverage(
            source="NO_RECORDED_ACTIVITY",
            complete=False,
            unknown_fields=["activity"],
        )
    return [selected[source] for source in sorted(selected)]


def _build_cluster(
    token_address: str,
    as_of: datetime,
    configuration: VersionedResearchConfiguration,
    buys: Sequence[ClusterActivity],
    collapse: ContributingIndependentCount,
    settings: ClusterSettings,
) -> WalletCluster:
    ordered = sorted(
        buys,
        key=lambda activity: (
            activity.chain_time,
            activity.slot,
            activity.signature,
            activity.wallet_address,
        ),
    )
    by_wallet: dict[str, list[ClusterActivity]] = {}
    for activity in ordered:
        by_wallet.setdefault(activity.wallet_address, []).append(activity)
    representatives = {group.representative for group in collapse.groups}
    contributions: list[ClusterWalletContribution] = []
    for wallet in sorted(by_wallet):
        items = by_wallet[wallet]
        scored = [item for item in items if item.wallet_score is not None]
        latest = max(scored, key=lambda item: item.observed_at, default=None)
        contributions.append(
            ClusterWalletContribution(
                wallet_address=wallet,
                wallet_score=None if latest is None else latest.wallet_score,
                score_as_of=None if latest is None else latest.score_as_of,
                total_sol=_round(sum(item.sol_amount for item in items)),
                buy_count=len(items),
                first_buy_at=items[0].chain_time,
                last_buy_at=items[-1].chain_time,
                independent=wallet in representatives,
                evidence=[
                    (
                        f"{len(items)} recorded BUY movement(s) of {token_address} by {wallet} "
                        f"totalling {_round(sum(item.sol_amount for item in items)):g} SOL."
                    )
                ],
            )
        )
    scores = [
        contribution.wallet_score
        for contribution in contributions
        if contribution.wallet_score is not None
    ]
    average = _round(sum(scores) / len(scores)) if scores else None
    weighted = _weighted_score(contributions, settings.score_weighting, average)
    first_buy_at = ordered[0].chain_time if ordered else None
    last_buy_at = ordered[-1].chain_time if ordered else None
    span: Optional[float] = None
    velocity: Optional[float] = None
    if first_buy_at is not None and last_buy_at is not None:
        span = (last_buy_at - first_buy_at).total_seconds()
        if span > 0:
            velocity = _round(len(ordered) / (span / 60))
    total_sol = _round(sum(activity.sol_amount for activity in ordered))
    notionals = [activity.notional_usd for activity in ordered]
    total_notional = (
        None
        if any(notional is None for notional in notionals)
        else _round(sum(notional for notional in notionals if notional is not None))
    )
    unknowns: list[str] = list(collapse.unknowns)
    unknown_scores = [
        contribution.wallet_address
        for contribution in contributions
        if contribution.wallet_score is None
    ]
    if unknown_scores:
        unknowns.append(
            "wallets: recorded Smart Wallet score is UNKNOWN for "
            + ", ".join(sorted(unknown_scores))
            + "."
        )
    if total_notional is None:
        unknowns.append(
            "total_notional_usd: one or more recorded BUY movements have no valuation."
        )
    warnings = list(
        dict.fromkeys(
            warning
            for activity in ordered
            for warning in activity.coverage.warnings
        )
    )
    window_seconds = settings.window_seconds
    evidence = [
        (
            f"{collapse.raw_wallet_count} raw Wallet(s) collapse to "
            f"{collapse.contributing_independent_wallet_count} Contributing-independent "
            f"Wallet(s) inside the configured {window_seconds}s window."
        ),
        (
            f"{len(ordered)} confirmed BUY movement(s) totalling {total_sol:g} SOL qualify for "
            f"{token_address} at the requested as-of time."
        ),
    ]
    if span is not None and velocity is not None:
        evidence.append(
            f"The Cluster formed over {span:.1f} seconds at {velocity:g} buys per minute."
        )
    return WalletCluster(
        token_address=token_address,
        status="ACTIVE",
        status_reason="The Cluster currently meets the configured thresholds.",
        superseded_by_version=None,
        as_of=as_of,
        configuration_id=str(configuration.id),
        configuration_version=configuration.version,
        window_seconds=window_seconds,
        score_weighting=settings.score_weighting,
        raw_wallet_count=collapse.raw_wallet_count,
        contributing_independent_wallet_count=(
            collapse.contributing_independent_wallet_count
        ),
        average_wallet_score=average,
        weighted_wallet_score=weighted,
        total_sol=total_sol,
        total_notional_usd=total_notional,
        buy_count=len(ordered),
        first_buy_at=first_buy_at,
        last_buy_at=last_buy_at,
        window_span_seconds=span,
        buy_velocity_per_minute=velocity,
        wallets=contributions,
        contributing_independent=collapse,
        activity=ordered,
        evidence=evidence,
        unknowns=unknowns,
        warnings=warnings,
        coverage=_coverage(ordered),
    )


def _meets_thresholds(
    cluster: WalletCluster, settings: ClusterSettings
) -> tuple[bool, str]:
    if cluster.buy_count < settings.minimum_buy_count:
        return (
            False,
            (
                f"{cluster.buy_count} recorded BUY movement(s) is below the configured "
                f"minimum {settings.minimum_buy_count}."
            ),
        )
    if cluster.total_sol < settings.minimum_total_sol:
        return (
            False,
            (
                f"total SOL {cluster.total_sol:g} is below the configured minimum "
                f"{settings.minimum_total_sol:g}."
            ),
        )
    if (
        cluster.contributing_independent_wallet_count
        < settings.minimum_contributing_independent_wallets
    ):
        return (
            False,
            (
                f"{cluster.contributing_independent_wallet_count} Contributing-independent "
                f"Wallet(s) is below the configured minimum "
                f"{settings.minimum_contributing_independent_wallets}."
            ),
        )
    if cluster.average_wallet_score is None:
        return (
            False,
            "Wallet quality is UNKNOWN, so the Cluster cannot meet the quality threshold.",
        )
    if cluster.average_wallet_score < settings.minimum_average_wallet_score:
        return (
            False,
            (
                f"average Wallet quality {cluster.average_wallet_score:g} is below the "
                f"configured minimum {settings.minimum_average_wallet_score:g}."
            ),
        )
    if any(contribution.wallet_score is None for contribution in cluster.wallets):
        return (
            False,
            "One or more contributing Wallet scores are UNKNOWN, so the Cluster is provisional.",
        )
    return (
        True,
        (
            f"{cluster.contributing_independent_wallet_count} Contributing-independent "
            f"Wallet(s) averaging {cluster.average_wallet_score:g} bought inside the configured "
            f"{cluster.window_seconds}s window."
        ),
    )


def _material_key(cluster: WalletCluster) -> tuple:
    return (
        cluster.window_seconds,
        cluster.score_weighting,
        cluster.raw_wallet_count,
        cluster.contributing_independent_wallet_count,
        cluster.average_wallet_score,
        cluster.weighted_wallet_score,
        cluster.total_sol,
        cluster.total_notional_usd,
        cluster.buy_count,
        cluster.first_buy_at,
        cluster.last_buy_at,
        tuple(
            (
                contribution.wallet_address,
                contribution.wallet_score,
                contribution.total_sol,
                contribution.buy_count,
                contribution.first_buy_at,
                contribution.last_buy_at,
            )
            for contribution in cluster.wallets
        ),
        tuple(
            (
                activity.signature,
                activity.slot,
                activity.wallet_address,
                activity.token_address,
                activity.movement_type,
            )
            for activity in cluster.activity
        ),
    )


class ClusterDetectorService:
    """Aggregate qualifying Smart Wallet buys into per-Token Clusters."""

    def __init__(
        self,
        activity_source: ClusterActivitySource,
        relationship_calculator: ContributingIndependentCalculator,
        configuration_store: ResearchConfigurationStore,
        cluster_store: WalletClusterStore,
    ) -> None:
        self._activity_source = activity_source
        self._relationship_calculator = relationship_calculator
        self._configuration_store = configuration_store
        self._cluster_store = cluster_store

    async def detect(self, as_of: datetime) -> ClusterDetection:
        activities = await self._activity_source.activity(as_of)
        return await self.observe(activities, as_of)

    async def observe(
        self, activities: Sequence[ClusterActivity], as_of: datetime
    ) -> ClusterDetection:
        configuration = await self._configuration_store.get_active()
        received = len(activities)
        recorded = 0
        duplicates = 0
        touched: set[str] = set()
        warnings: list[str] = []
        for activity in activities:
            result = await self._cluster_store.record_activity(activity)
            if result.created:
                recorded += 1
            else:
                duplicates += 1
            warnings.extend(activity.coverage.warnings)
            if activity.movement_type == "BUY":
                touched.add(activity.token_address)

        created = 0
        updated = 0
        invalidated = 0
        unchanged = 0
        clusters: list[StoredWalletCluster] = []
        for live_cluster in await self._cluster_store.live(as_of):
            token_address = live_cluster.cluster.token_address
            if token_address in touched or not _is_expired(live_cluster.cluster, as_of):
                continue
            clusters.append(
                await self._invalidate(
                    live_cluster,
                    "EXPIRED",
                    (
                        f"The Cluster expired because its last qualifying buy at "
                        f"{_timestamp(live_cluster.cluster.last_buy_at)} is older than the "
                        f"configured {live_cluster.cluster.window_seconds}s window."
                    ),
                )
            )
            invalidated += 1
        for token_address in sorted(touched):
            outcome, current_cluster = await self._recompute(
                token_address, as_of, configuration
            )
            if current_cluster is not None:
                clusters.append(current_cluster)
            if outcome == "created":
                created += 1
            elif outcome == "superseded":
                updated += 1
            elif outcome == "invalidated":
                invalidated += 1
            else:
                unchanged += 1
        return ClusterDetection(
            as_of=as_of,
            configuration_id=str(configuration.id),
            configuration_version=configuration.version,
            received=received,
            recorded=recorded,
            duplicates=duplicates,
            created_clusters=created,
            updated_clusters=updated,
            invalidated_clusters=invalidated,
            unchanged_clusters=unchanged,
            clusters=clusters,
            warnings=list(dict.fromkeys(warnings)),
        )

    async def live(self, as_of: datetime) -> list[StoredWalletCluster]:
        return [
            stored
            for stored in await self._cluster_store.live(as_of)
            if not _is_expired(stored.cluster, as_of)
        ]

    async def detail(
        self, token_address: str, as_of: datetime
    ) -> Optional[WalletClusterDetail]:
        current = await self._cluster_store.current(token_address, as_of)
        if current is None:
            return None
        return WalletClusterDetail(
            token_address=token_address,
            current=current,
            history=await self._cluster_store.history(token_address, as_of),
        )

    async def _recompute(
        self,
        token_address: str,
        as_of: datetime,
        configuration: VersionedResearchConfiguration,
    ) -> tuple[str, Optional[StoredWalletCluster]]:
        settings = configuration.configuration.cluster
        stored = await self._cluster_store.activity(token_address, as_of)
        window_start = as_of - timedelta(seconds=settings.window_seconds)
        buys = [
            activity
            for activity in stored
            if activity.movement_type == "BUY"
            and activity.eligible_for_decisions
            and window_start <= activity.chain_time <= as_of
        ]
        wallets = sorted({activity.wallet_address for activity in buys})
        collapse = await self._relationship_calculator.contributing_independent(
            wallets, as_of
        )
        cluster = _build_cluster(
            token_address, as_of, configuration, buys, collapse, settings
        )
        current = await self._cluster_store.current(token_address, as_of)
        meets, reason = _meets_thresholds(cluster, settings)
        if not meets:
            if current is not None and current.cluster.status == "ACTIVE":
                return "invalidated", await self._invalidate(current, "THRESHOLD_LOST", reason)
            return "unchanged", None
        draft = cluster.model_copy(
            update={"status": "ACTIVE", "status_reason": reason}
        )
        if (
            current is not None
            and current.cluster.status == "ACTIVE"
            and _material_key(current.cluster) == _material_key(draft)
        ):
            return "unchanged", current
        recorded = await self._cluster_store.record(draft)
        new_version = StoredWalletCluster(
            token_address=token_address,
            version=recorded.version,
            created_at=recorded.created_at,
            cluster=recorded.cluster,
        )
        if current is not None and current.cluster.status == "ACTIVE":
            await self._cluster_store.transition_status(
                token_address,
                current.version,
                "SUPERSEDED",
                (
                    f"Materially changed evidence superseded this version with version "
                    f"{recorded.version}."
                ),
                superseded_by_version=recorded.version,
            )
            return "superseded", new_version
        return "created", new_version

    async def _invalidate(
        self, stored: StoredWalletCluster, reason: ClusterInvalidationReason, text_reason: str
    ) -> StoredWalletCluster:
        return await self._cluster_store.transition_status(
            stored.cluster.token_address,
            stored.version,
            "INVALIDATED",
            f"{reason}: {text_reason}",
            superseded_by_version=None,
        )


def _timestamp(value: Optional[datetime]) -> str:
    return "UNKNOWN" if value is None else value.isoformat()


class InMemoryWalletClusterStore:
    """Deterministic Cluster store used by HTTP tests."""

    def __init__(
        self, *, now: Callable[[], datetime] = lambda: datetime.now(timezone.utc)
    ) -> None:
        self._now = now
        self._activities: dict[str, ClusterActivity] = {}
        self._activity_order: list[str] = []
        self._versions: dict[str, list[StoredWalletCluster]] = {}

    async def record_activity(
        self, activity: ClusterActivity
    ) -> RecordClusterActivityResult:
        key = _idempotency_key(activity)
        existing = self._activities.get(key)
        if existing is not None:
            if existing != activity:
                raise ValueError("conflicting recorded cluster activity")
            return RecordClusterActivityResult(created=False, activity=existing)
        self._activities[key] = activity
        self._activity_order.append(key)
        return RecordClusterActivityResult(created=True, activity=activity)

    async def activity(self, token_address: str, as_of: datetime) -> list[ClusterActivity]:
        return [
            self._activities[key]
            for key in self._activity_order
            if self._activities[key].token_address == token_address
            and self._activities[key].observed_at <= as_of
        ]

    async def tokens(self) -> list[str]:
        return sorted({self._activities[key].token_address for key in self._activity_order})

    async def record(self, cluster: WalletCluster) -> RecordWalletClusterResult:
        versions = self._versions.setdefault(cluster.token_address, [])
        if versions:
            latest = versions[-1]
            if _material_key(latest.cluster) == _material_key(cluster) and (
                latest.cluster.status == cluster.status
            ):
                return RecordWalletClusterResult(
                    created=False,
                    version=latest.version,
                    created_at=latest.created_at,
                    cluster=latest.cluster,
                )
        stored = StoredWalletCluster(
            token_address=cluster.token_address,
            version=len(versions) + 1,
            created_at=self._now(),
            cluster=cluster.model_copy(deep=True),
        )
        versions.append(stored)
        return RecordWalletClusterResult(
            created=True,
            version=stored.version,
            created_at=stored.created_at,
            cluster=stored.cluster,
        )

    async def transition_status(
        self,
        token_address: str,
        version: int,
        status: ClusterStatus,
        status_reason: str,
        superseded_by_version: Optional[int] = None,
    ) -> StoredWalletCluster:
        versions = self._versions.get(token_address, [])
        for index, stored in enumerate(versions):
            if stored.version != version:
                continue
            updated = stored.model_copy(
                update={
                    "cluster": stored.cluster.model_copy(
                        update={
                            "status": status,
                            "status_reason": status_reason,
                            "superseded_by_version": superseded_by_version,
                        }
                    )
                }
            )
            versions[index] = updated
            return updated
        raise KeyError(version)

    async def current(
        self, token_address: str, as_of: datetime
    ) -> Optional[StoredWalletCluster]:
        eligible = [
            stored
            for stored in self._versions.get(token_address, [])
            if stored.cluster.as_of <= as_of
        ]
        if not eligible:
            return None
        return max(eligible, key=lambda stored: stored.version)

    async def history(
        self, token_address: str, as_of: datetime
    ) -> list[StoredWalletCluster]:
        eligible = [
            stored
            for stored in self._versions.get(token_address, [])
            if stored.cluster.as_of <= as_of
        ]
        return sorted(eligible, key=lambda stored: stored.version, reverse=True)

    async def live(self, as_of: datetime) -> list[StoredWalletCluster]:
        live: list[StoredWalletCluster] = []
        for token_address in sorted(self._versions):
            current = await self.current(token_address, as_of)
            if current is not None and current.cluster.status == "ACTIVE":
                live.append(current)
        return live


# Fixed column list shared by every activity statement; never built from input.
_ACTIVITY_COLUMNS = (
    "event_id, wallet_address, token_address, movement_type, quantity, sol_amount, "
    "notional_usd, wallet_score, score_as_of, signature, slot, chain_time, observed_at, "
    "commitment, eligible_for_decisions, evidence, coverage"
)

_VERSION_COLUMNS = (
    "token_address, version, as_of, status, superseded_by_version, configuration_id, "
    "configuration_version, cluster, created_at"
)


class PostgresWalletClusterStore:
    """PostgreSQL source of truth for Cluster activity and versions."""

    def __init__(self, engine: AsyncEngine) -> None:
        self._engine = engine

    async def record_activity(
        self, activity: ClusterActivity
    ) -> RecordClusterActivityResult:
        key = _idempotency_key(activity)
        async with self._engine.begin() as connection:
            await connection.execute(
                text("SELECT pg_advisory_xact_lock(hashtext(:key))"), {"key": key}
            )
            existing = await connection.execute(
                text(
                    f"""
                    SELECT {_ACTIVITY_COLUMNS}
                    FROM smart_wallet_cluster_activities
                    WHERE idempotency_key = :idempotency_key
                    """
                ),
                {"idempotency_key": key},
            )
            row = existing.mappings().one_or_none()
            if row is not None:
                recorded = self._activity_from_row(row)
                if recorded != activity:
                    raise ValueError("conflicting recorded cluster activity")
                return RecordClusterActivityResult(created=False, activity=recorded)
            inserted = await connection.execute(
                text(
                    f"""
                    INSERT INTO smart_wallet_cluster_activities (
                        idempotency_key, event_id, wallet_address, token_address, movement_type,
                        quantity, sol_amount, notional_usd, wallet_score, score_as_of, signature,
                        slot, chain_time, observed_at, commitment, eligible_for_decisions,
                        evidence, coverage
                    ) VALUES (
                        :idempotency_key, :event_id, :wallet_address, :token_address,
                        :movement_type, :quantity, :sol_amount, :notional_usd, :wallet_score,
                        :score_as_of, :signature, :slot, :chain_time, :observed_at, :commitment,
                        :eligible_for_decisions, CAST(:evidence AS JSONB),
                        CAST(:coverage AS JSONB)
                    )
                    RETURNING {_ACTIVITY_COLUMNS}
                    """
                ),
                {
                    "idempotency_key": key,
                    "event_id": activity.event_id,
                    "wallet_address": activity.wallet_address,
                    "token_address": activity.token_address,
                    "movement_type": activity.movement_type,
                    "quantity": activity.quantity,
                    "sol_amount": activity.sol_amount,
                    "notional_usd": activity.notional_usd,
                    "wallet_score": activity.wallet_score,
                    "score_as_of": activity.score_as_of,
                    "signature": activity.signature,
                    "slot": activity.slot,
                    "chain_time": activity.chain_time,
                    "observed_at": activity.observed_at,
                    "commitment": activity.commitment,
                    "eligible_for_decisions": activity.eligible_for_decisions,
                    "evidence": json.dumps(list(activity.evidence)),
                    "coverage": _json_document(activity.coverage),
                },
            )
            return RecordClusterActivityResult(
                created=True, activity=self._activity_from_row(inserted.mappings().one())
            )

    async def activity(self, token_address: str, as_of: datetime) -> list[ClusterActivity]:
        async with self._engine.connect() as connection:
            result = await connection.execute(
                text(
                    f"""
                    SELECT {_ACTIVITY_COLUMNS}
                    FROM smart_wallet_cluster_activities
                    WHERE token_address = :token_address AND observed_at <= :as_of
                    ORDER BY chain_time, slot, signature, wallet_address
                    """
                ),
                {"token_address": token_address, "as_of": as_of},
            )
            return [self._activity_from_row(row) for row in result.mappings()]

    async def tokens(self) -> list[str]:
        async with self._engine.connect() as connection:
            result = await connection.execute(
                text(
                    """
                    SELECT DISTINCT token_address
                    FROM smart_wallet_cluster_activities
                    ORDER BY token_address
                    """
                )
            )
            return [str(row["token_address"]) for row in result.mappings()]

    async def record(self, cluster: WalletCluster) -> RecordWalletClusterResult:
        async with self._engine.begin() as connection:
            await connection.execute(
                text("SELECT pg_advisory_xact_lock(hashtext(:token_address))"),
                {"token_address": cluster.token_address},
            )
            latest = await connection.execute(
                text(
                    f"""
                    SELECT {_VERSION_COLUMNS}
                    FROM smart_wallet_cluster_versions
                    WHERE token_address = :token_address
                    ORDER BY version DESC
                    LIMIT 1
                    """
                ),
                {"token_address": cluster.token_address},
            )
            row = latest.mappings().one_or_none()
            if row is not None:
                existing = self._stored_from_row(row)
                if (
                    _material_key(existing.cluster) == _material_key(cluster)
                    and existing.cluster.status == cluster.status
                ):
                    return RecordWalletClusterResult(
                        created=False,
                        version=existing.version,
                        created_at=existing.created_at,
                        cluster=existing.cluster,
                    )
            next_version = await connection.scalar(
                text(
                    """
                    SELECT COALESCE(MAX(version), 0) + 1
                    FROM smart_wallet_cluster_versions
                    WHERE token_address = :token_address
                    """
                ),
                {"token_address": cluster.token_address},
            )
            inserted = await connection.execute(
                text(
                    f"""
                    INSERT INTO smart_wallet_cluster_versions (
                        token_address, version, as_of, status, superseded_by_version,
                        configuration_id, configuration_version, cluster
                    ) VALUES (
                        :token_address, :version, :as_of, :status, :superseded_by_version,
                        CAST(:configuration_id AS UUID), :configuration_version,
                        CAST(:cluster AS JSONB)
                    )
                    RETURNING {_VERSION_COLUMNS}
                    """
                ),
                {
                    "token_address": cluster.token_address,
                    "version": int(next_version or 1),
                    "as_of": cluster.as_of,
                    "status": cluster.status,
                    "superseded_by_version": cluster.superseded_by_version,
                    "configuration_id": cluster.configuration_id,
                    "configuration_version": cluster.configuration_version,
                    "cluster": _json_document(cluster),
                },
            )
            inserted_row = inserted.mappings().one()
            return RecordWalletClusterResult(
                created=True,
                version=int(inserted_row["version"]),
                created_at=inserted_row["created_at"],
                cluster=cluster,
            )

    async def transition_status(
        self,
        token_address: str,
        version: int,
        status: ClusterStatus,
        status_reason: str,
        superseded_by_version: Optional[int] = None,
    ) -> StoredWalletCluster:
        async with self._engine.begin() as connection:
            await connection.execute(
                text("SELECT pg_advisory_xact_lock(hashtext(:token_address))"),
                {"token_address": token_address},
            )
            current = await connection.execute(
                text(
                    f"""
                    SELECT {_VERSION_COLUMNS}
                    FROM smart_wallet_cluster_versions
                    WHERE token_address = :token_address AND version = :version
                    """
                ),
                {"token_address": token_address, "version": version},
            )
            row = current.mappings().one()
            stored = self._stored_from_row(row)
            updated_cluster = stored.cluster.model_copy(
                update={
                    "status": status,
                    "status_reason": status_reason,
                    "superseded_by_version": superseded_by_version,
                }
            )
            updated = await connection.execute(
                text(
                    f"""
                    UPDATE smart_wallet_cluster_versions
                    SET status = :status,
                        superseded_by_version = :superseded_by_version,
                        cluster = CAST(:cluster AS JSONB)
                    WHERE token_address = :token_address AND version = :version
                    RETURNING {_VERSION_COLUMNS}
                    """
                ),
                {
                    "status": status,
                    "superseded_by_version": superseded_by_version,
                    "cluster": _json_document(updated_cluster),
                    "token_address": token_address,
                    "version": version,
                },
            )
            return self._stored_from_row(updated.mappings().one())

    async def current(
        self, token_address: str, as_of: datetime
    ) -> Optional[StoredWalletCluster]:
        async with self._engine.connect() as connection:
            result = await connection.execute(
                text(
                    f"""
                    SELECT {_VERSION_COLUMNS}
                    FROM smart_wallet_cluster_versions
                    WHERE token_address = :token_address AND as_of <= :as_of
                    ORDER BY version DESC
                    LIMIT 1
                    """
                ),
                {"token_address": token_address, "as_of": as_of},
            )
            row = result.mappings().one_or_none()
        return None if row is None else self._stored_from_row(row)

    async def history(
        self, token_address: str, as_of: datetime
    ) -> list[StoredWalletCluster]:
        async with self._engine.connect() as connection:
            result = await connection.execute(
                text(
                    f"""
                    SELECT {_VERSION_COLUMNS}
                    FROM smart_wallet_cluster_versions
                    WHERE token_address = :token_address AND as_of <= :as_of
                    ORDER BY version DESC
                    """
                ),
                {"token_address": token_address, "as_of": as_of},
            )
            return [self._stored_from_row(row) for row in result.mappings()]

    async def live(self, as_of: datetime) -> list[StoredWalletCluster]:
        async with self._engine.connect() as connection:
            result = await connection.execute(
                text(
                    f"""
                    SELECT {_VERSION_COLUMNS}
                    FROM smart_wallet_cluster_versions AS versions
                    JOIN (
                        SELECT token_address, MAX(version) AS version
                        FROM smart_wallet_cluster_versions
                        WHERE as_of <= :as_of
                        GROUP BY token_address
                    ) AS latest
                      ON latest.token_address = versions.token_address
                     AND latest.version = versions.version
                    WHERE versions.status = 'ACTIVE'
                    ORDER BY versions.token_address
                    """
                ),
                {"as_of": as_of},
            )
            return [self._stored_from_row(row) for row in result.mappings()]

    @staticmethod
    def _activity_from_row(row: RowMapping) -> ClusterActivity:
        return ClusterActivity(
            event_id=str(row["event_id"]),
            wallet_address=str(row["wallet_address"]),
            token_address=str(row["token_address"]),
            movement_type=row["movement_type"],
            quantity=float(row["quantity"]),
            sol_amount=float(row["sol_amount"]),
            notional_usd=None if row["notional_usd"] is None else float(row["notional_usd"]),
            wallet_score=None if row["wallet_score"] is None else float(row["wallet_score"]),
            score_as_of=row["score_as_of"],
            signature=str(row["signature"]),
            slot=int(row["slot"]),
            chain_time=row["chain_time"],
            observed_at=row["observed_at"],
            commitment=row["commitment"],
            eligible_for_decisions=bool(row["eligible_for_decisions"]),
            evidence=[str(item) for item in _json_value(row["evidence"])],
            coverage=RealtimeCoverage.model_validate(_json_value(row["coverage"])),
        )

    @staticmethod
    def _stored_from_row(row: RowMapping) -> StoredWalletCluster:
        return StoredWalletCluster(
            token_address=str(row["token_address"]),
            version=int(row["version"]),
            created_at=row["created_at"],
            cluster=WalletCluster.model_validate(_json_value(row["cluster"])),
        )
