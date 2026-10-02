"""Explainable Discovery funnel from analyzed Tokens to Registry-accepted Wallets.

A run fixes its cohort and configuration version before any evidence is read.
Its first stage qualifies Tokens from the cohort; every later stage applies one
gate to the Wallets the previous stage included.  Every subject that does not
continue carries a machine-readable code, a human-readable message, the
configuration version, and the as-of time that decided it.  A subject whose
recorded evidence cannot establish a gate is reported as UNKNOWN instead of
being counted as a failure, and partial provider coverage stays visible on the
member rather than disappearing.

Each Wallet gate after the candidate pool reads one explainable Smart Wallet
Score component and passes the Wallet when that component is known and at or
above its neutral midpoint.  Those components are normalized against versioned
configuration, so the gates move with the configuration version recorded on the
run.
"""

import json
from collections.abc import Callable, Sequence
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Literal, Optional, Protocol
from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict, Field, model_validator
from sqlalchemy import text
from sqlalchemy.engine import RowMapping
from sqlalchemy.ext.asyncio import AsyncEngine

from paper_trade.historical_winners import (
    DiscoveryCriterion,
    EarlyBuyerRecord,
    HistoricalWinner,
    HistoricalWinnerCohortRequest,
    HistoricalWinnerDiscovery,
)
from paper_trade.research_configuration import (
    ResearchConfigurationStore,
    VersionedResearchConfiguration,
)
from paper_trade.wallet_scoring import (
    ScoreComponent,
    ScoreComponentName,
    WalletScore,
    WalletScoreResult,
)

FunnelStageName = Literal[
    "TOKENS_ANALYZED",
    "WALLETS_FOUND",
    "CANDIDATES",
    "PROFITABLE",
    "CONSISTENT",
    "COPYABLE",
    "SMART_WALLET",
]
FunnelStageSubject = Literal["TOKEN", "WALLET"]
FunnelOutcome = Literal["INCLUDED", "EXCLUDED", "UNKNOWN"]
FunnelRunStatus = Literal["RUNNING", "COMPLETED", "FAILED"]
FunnelReasonCode = Literal[
    "RECORDED_WINNER_ACTIVITY",
    "INITIAL_MARKET_CAP_IN_RANGE",
    "INITIAL_MARKET_CAP_OUT_OF_RANGE",
    "INITIAL_MARKET_CAP_UNKNOWN",
    "PEAK_MARKET_CAP_AT_OR_ABOVE_MINIMUM",
    "PEAK_MARKET_CAP_BELOW_MINIMUM",
    "PEAK_MARKET_CAP_UNKNOWN",
    "TOKEN_CRITERION_UNRECOGNIZED",
    "SUCCESSFUL_ENTRY",
    "ENTRY_TRANSACTION_FAILED",
    "ENTRY_NOT_A_BUY",
    "ENTRY_MOVEMENT_UNKNOWN",
    "ENTRY_EVIDENCE_UNRECOGNIZED",
    "NO_RECORDED_ACCOUNTING",
    "CLEAN_PROFITABILITY_AT_OR_ABOVE_MIDPOINT",
    "CLEAN_PROFITABILITY_BELOW_MIDPOINT",
    "PROFITABILITY_UNKNOWN",
    "CONSISTENCY_AT_OR_ABOVE_MIDPOINT",
    "CONSISTENCY_BELOW_MIDPOINT",
    "CONSISTENCY_UNKNOWN",
    "COPYABILITY_AT_OR_ABOVE_MIDPOINT",
    "COPYABILITY_BELOW_MIDPOINT",
    "COPYABILITY_UNKNOWN",
    "REGISTRY_SMART_WALLET",
    "REGISTRY_NOT_SMART_WALLET",
    "SMART_WALLET_BLOCKED_BY_UNKNOWN_EVIDENCE",
]

FUNNEL_STAGE_ORDER: tuple[FunnelStageName, ...] = (
    "TOKENS_ANALYZED",
    "WALLETS_FOUND",
    "CANDIDATES",
    "PROFITABLE",
    "CONSISTENT",
    "COPYABLE",
    "SMART_WALLET",
)
_STAGE_SUBJECTS: dict[FunnelStageName, FunnelStageSubject] = {
    "TOKENS_ANALYZED": "TOKEN",
    "WALLETS_FOUND": "WALLET",
    "CANDIDATES": "WALLET",
    "PROFITABLE": "WALLET",
    "CONSISTENT": "WALLET",
    "COPYABLE": "WALLET",
    "SMART_WALLET": "WALLET",
}
_STAGE_COMPONENTS: dict[FunnelStageName, ScoreComponentName] = {
    "PROFITABLE": "profitability",
    "CONSISTENT": "consistency",
    "COPYABLE": "copyability",
}
_GATE_CODES: dict[
    FunnelStageName, tuple[FunnelReasonCode, FunnelReasonCode, FunnelReasonCode]
] = {
    "PROFITABLE": (
        "CLEAN_PROFITABILITY_AT_OR_ABOVE_MIDPOINT",
        "CLEAN_PROFITABILITY_BELOW_MIDPOINT",
        "PROFITABILITY_UNKNOWN",
    ),
    "CONSISTENT": (
        "CONSISTENCY_AT_OR_ABOVE_MIDPOINT",
        "CONSISTENCY_BELOW_MIDPOINT",
        "CONSISTENCY_UNKNOWN",
    ),
    "COPYABLE": (
        "COPYABILITY_AT_OR_ABOVE_MIDPOINT",
        "COPYABILITY_BELOW_MIDPOINT",
        "COPYABILITY_UNKNOWN",
    ),
}
_TOKEN_CRITERIA: dict[str, tuple[FunnelReasonCode, FunnelReasonCode, FunnelReasonCode]] = {
    "initial_market_cap_usd": (
        "INITIAL_MARKET_CAP_IN_RANGE",
        "INITIAL_MARKET_CAP_OUT_OF_RANGE",
        "INITIAL_MARKET_CAP_UNKNOWN",
    ),
    "peak_market_cap_usd": (
        "PEAK_MARKET_CAP_AT_OR_ABOVE_MINIMUM",
        "PEAK_MARKET_CAP_BELOW_MINIMUM",
        "PEAK_MARKET_CAP_UNKNOWN",
    ),
}
_MOVEMENT_TYPES: tuple[str, ...] = (
    "BUY",
    "SELL",
    "TRANSFER_IN",
    "TRANSFER_OUT",
    "AIRDROP",
    "UNKNOWN",
)
# A 0-100 Score component passes its funnel gate at its neutral midpoint.
# Components are normalized against versioned configuration, so the midpoint
# moves with the configuration version recorded on the run.
COMPONENT_GATE_MIDPOINT = 50.0


class DiscoveryFunnelModel(BaseModel):
    """Base public contract for the Discovery funnel."""

    model_config = ConfigDict(extra="forbid")


class DiscoveryFunnelRequest(DiscoveryFunnelModel):
    """A fixed cohort plus the as-of time used by every Wallet-stage gate."""

    cohort: HistoricalWinnerCohortRequest
    as_of: datetime

    @model_validator(mode="after")
    def validate_as_of(self) -> "DiscoveryFunnelRequest":
        if self.as_of < self.cohort.qualification_as_of:
            raise ValueError("as_of must not be earlier than cohort.qualification_as_of")
        return self


class FunnelReason(DiscoveryFunnelModel):
    """One machine-readable and human-readable funnel decision."""

    code: FunnelReasonCode
    outcome: FunnelOutcome
    message: str = Field(min_length=1)
    observed: Optional[str] = None
    threshold: Optional[str] = None
    configuration_version: int = Field(ge=1)
    as_of: datetime


class FunnelCoverage(DiscoveryFunnelModel):
    """One evidence source read for a funnel member, including declared gaps."""

    source: str = Field(min_length=1)
    complete: bool
    unknown_fields: list[str] = Field(default_factory=list)


class FunnelMember(DiscoveryFunnelModel):
    """One Token or Wallet inside a stage, with its gate decision and reasons."""

    subject: str = Field(min_length=1)
    outcome: FunnelOutcome
    reasons: list[FunnelReason] = Field(min_length=1)
    evidence: list[str] = Field(default_factory=list)
    coverage: list[FunnelCoverage] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_decisive_reason(self) -> "FunnelMember":
        if not any(reason.outcome == self.outcome for reason in self.reasons):
            raise ValueError("member reasons must include one that matches the member outcome")
        return self


class FunnelStage(DiscoveryFunnelModel):
    """One funnel gate over the subjects the previous stage included."""

    name: FunnelStageName
    subject: FunnelStageSubject
    as_of: datetime
    configuration_version: int = Field(ge=1)
    evaluated: int = Field(ge=0)
    included: int = Field(ge=0)
    excluded: int = Field(ge=0)
    unknown: int = Field(ge=0)
    members: list[FunnelMember]

    @model_validator(mode="after")
    def validate_counts_and_reasons(self) -> "FunnelStage":
        if self.subject != _STAGE_SUBJECTS[self.name]:
            raise ValueError(f"{self.name} must contain {_STAGE_SUBJECTS[self.name]} subjects")
        if self.evaluated != len(self.members):
            raise ValueError("evaluated must count every member of the stage")
        if self.included + self.excluded + self.unknown != self.evaluated:
            raise ValueError("included, excluded, and unknown must sum to evaluated")
        for outcome, declared in (
            ("INCLUDED", self.included),
            ("EXCLUDED", self.excluded),
            ("UNKNOWN", self.unknown),
        ):
            if declared != sum(1 for member in self.members if member.outcome == outcome):
                raise ValueError(f"{outcome.lower()} must count its members")
        for member in self.members:
            for reason in member.reasons:
                if reason.configuration_version != self.configuration_version:
                    raise ValueError("reason configuration_version must match its stage")
                if reason.as_of != self.as_of:
                    raise ValueError("reason as_of must match its stage")
        return self


class DiscoveryFunnelRun(DiscoveryFunnelModel):
    """One funnel run in its current state, with its stages when completed."""

    run_id: str = Field(min_length=1)
    cohort: HistoricalWinnerCohortRequest
    as_of: datetime
    configuration_id: str = Field(min_length=1)
    configuration_version: int = Field(ge=1)
    status: FunnelRunStatus
    started_at: datetime
    completed_at: Optional[datetime] = None
    error: Optional[str] = None
    stages: list[FunnelStage] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_lifecycle_and_chain(self) -> "DiscoveryFunnelRun":
        names = [stage.name for stage in self.stages]
        if self.status == "RUNNING":
            if self.completed_at is not None:
                raise ValueError("a running funnel must not record completed_at")
            if self.error is not None:
                raise ValueError("a running funnel must not record an error")
        elif self.completed_at is None:
            raise ValueError("a finished funnel must record completed_at")
        if self.status == "COMPLETED":
            if names != list(FUNNEL_STAGE_ORDER):
                raise ValueError("a completed funnel must hold every stage in order")
            if self.error is not None:
                raise ValueError("a completed funnel must not record an error")
        elif self.stages:
            raise ValueError("only a completed funnel holds stages")
        if self.status == "FAILED" and not self.error:
            raise ValueError("a failed funnel must record its error")
        for previous, stage in zip(self.stages, self.stages[1:]):
            if previous.subject != stage.subject:
                continue
            if stage.evaluated != previous.included:
                raise ValueError(
                    f"{stage.name} must evaluate every Wallet included by {previous.name}"
                )
        return self


class HistoricalWinnerSource(Protocol):
    """Adapter contract for the recorded winner discovery a run freezes."""

    async def discover(
        self,
        cohort: HistoricalWinnerCohortRequest,
        configuration: VersionedResearchConfiguration,
    ) -> HistoricalWinnerDiscovery:
        """Qualify the cohort and evaluate its recorded early buyers."""


class WalletScoreSource(Protocol):
    """Adapter contract for the explainable Smart Wallet Score a run reads."""

    async def score(self, address: str, as_of: datetime) -> WalletScoreResult:
        """Score one Wallet at ``as_of``, raising ``KeyError`` when unrecorded."""


class DiscoveryFunnelStore(Protocol):
    """Durable persistence seam for funnel runs and their stages."""

    async def start_run(
        self,
        request: DiscoveryFunnelRequest,
        configuration: VersionedResearchConfiguration,
    ) -> DiscoveryFunnelRun:
        """Persist a RUNNING run before any cohort evidence is read."""

    async def complete_run(
        self,
        run_id: str,
        stages: Sequence[FunnelStage],
        warnings: Sequence[str],
    ) -> DiscoveryFunnelRun:
        """Record a run COMPLETED with its immutable stages."""

    async def fail_run(self, run_id: str, error: str) -> DiscoveryFunnelRun:
        """Record a run FAILED with its human-readable error."""

    async def latest(self) -> Optional[DiscoveryFunnelRun]:
        """Return the most recently started run, in whatever state it holds."""


class DiscoveryFunnelRunError(RuntimeError):
    """Raised after a failed run has already been recorded with FAILED state."""


@dataclass
class _WalletEvidence:
    address: str
    records: list[EarlyBuyerRecord] = field(default_factory=list)
    criteria: list[DiscoveryCriterion] = field(default_factory=list)


def _json_value(value: Any) -> Any:
    return json.loads(value) if isinstance(value, str) else value


def _reason(
    code: FunnelReasonCode,
    outcome: FunnelOutcome,
    message: str,
    *,
    configuration_version: int,
    as_of: datetime,
    observed: Optional[str] = None,
    threshold: Optional[str] = None,
) -> FunnelReason:
    return FunnelReason(
        code=code,
        outcome=outcome,
        message=message,
        observed=observed,
        threshold=threshold,
        configuration_version=configuration_version,
        as_of=as_of,
    )


def _token_reason(
    criterion: DiscoveryCriterion, configuration_version: int, as_of: datetime
) -> FunnelReason:
    codes = _TOKEN_CRITERIA.get(criterion.criterion)
    if codes is None:
        return _reason(
            "TOKEN_CRITERION_UNRECOGNIZED",
            "UNKNOWN",
            (
                f"The recorded cohort fact {criterion.criterion} is not a recognized winner "
                "criterion, so this Token cannot be judged."
            ),
            configuration_version=configuration_version,
            as_of=as_of,
            observed=criterion.observed,
            threshold=criterion.threshold,
        )
    included_code, excluded_code, unknown_code = codes
    if criterion.observed == "UNKNOWN":
        return _reason(
            unknown_code,
            "UNKNOWN",
            (
                f"{criterion.criterion} is UNKNOWN at the qualification as-of time, so this "
                "Token cannot be judged against the configured winner rule."
            ),
            configuration_version=configuration_version,
            as_of=as_of,
            observed=criterion.observed,
            threshold=criterion.threshold,
        )
    return _reason(
        included_code if criterion.passed else excluded_code,
        "INCLUDED" if criterion.passed else "EXCLUDED",
        (
            f"{criterion.criterion} {criterion.observed} against the configured winner rule "
            f"{criterion.threshold}."
        ),
        configuration_version=configuration_version,
        as_of=as_of,
        observed=criterion.observed,
        threshold=criterion.threshold,
    )


def _entry_reason(
    criterion: DiscoveryCriterion, configuration_version: int, as_of: datetime
) -> FunnelReason:
    if criterion.criterion != "successful_buy":
        return _reason(
            "ENTRY_EVIDENCE_UNRECOGNIZED",
            "UNKNOWN",
            (
                f"The recorded entry fact {criterion.criterion} is not a recognized candidate "
                "criterion, so this Wallet entry cannot be judged."
            ),
            configuration_version=configuration_version,
            as_of=as_of,
            observed=criterion.observed,
            threshold=criterion.threshold,
        )
    if criterion.passed:
        return _reason(
            "SUCCESSFUL_ENTRY",
            "INCLUDED",
            (
                f"A recorded {criterion.observed} entry on a qualified historical winner Token "
                "passes the configured candidate rule."
            ),
            configuration_version=configuration_version,
            as_of=as_of,
            observed=criterion.observed,
            threshold=criterion.threshold,
        )
    movement, _, status = criterion.observed.partition(" ")
    code: FunnelReasonCode
    outcome: FunnelOutcome
    if movement not in _MOVEMENT_TYPES or status not in ("succeeded", "failed"):
        code, outcome = "ENTRY_EVIDENCE_UNRECOGNIZED", "UNKNOWN"
        message = (
            f"The recorded entry evidence {criterion.observed} is not a recognized Wallet "
            "movement, so this Wallet entry cannot be judged."
        )
    elif movement == "UNKNOWN":
        code, outcome = "ENTRY_MOVEMENT_UNKNOWN", "UNKNOWN"
        message = (
            "Every recorded movement for this Wallet is UNKNOWN, so a successful entry cannot "
            "be established."
        )
    elif movement == "BUY":
        code, outcome = "ENTRY_TRANSACTION_FAILED", "EXCLUDED"
        message = "The recorded BUY failed, so it is not a candidate entry."
    else:
        code, outcome = "ENTRY_NOT_A_BUY", "EXCLUDED"
        message = f"The recorded {movement} movement is not a BUY, so it is not a candidate entry."
    return _reason(
        code,
        outcome,
        message,
        configuration_version=configuration_version,
        as_of=as_of,
        observed=criterion.observed,
        threshold=criterion.threshold,
    )


def _entry_evidence(wallet: _WalletEvidence) -> list[str]:
    return [
        (
            f"Recorded early buy {record.signature} at {record.chain_time.isoformat()} in "
            f"{record.venue or 'UNKNOWN venue'}."
        )
        for record in wallet.records
    ]


def _entry_warnings(wallet: _WalletEvidence) -> list[str]:
    return list(
        dict.fromkeys(warning for record in wallet.records for warning in record.warnings)
    )


def _entry_coverage(wallet: _WalletEvidence) -> list[FunnelCoverage]:
    selected: dict[str, FunnelCoverage] = {}
    for record in wallet.records:
        selected.setdefault(
            record.coverage.provider,
            FunnelCoverage(
                source=record.coverage.provider,
                complete=record.coverage.complete,
                unknown_fields=list(record.coverage.unknown_fields),
            ),
        )
    return [selected[provider] for provider in sorted(selected)]


def _score_coverage(score: WalletScore) -> list[FunnelCoverage]:
    return [
        FunnelCoverage(
            source=item.source,
            complete=item.complete,
            unknown_fields=list(item.unknown_fields),
        )
        for item in score.coverage
    ]


def _component(score: WalletScore, name: ScoreComponentName) -> ScoreComponent:
    component = next((item for item in score.components if item.name == name), None)
    if component is None:
        raise ValueError(f"Wallet score is missing the {name} component")
    return component


def _component_reason(
    component: ScoreComponent,
    codes: tuple[FunnelReasonCode, FunnelReasonCode, FunnelReasonCode],
    configuration_version: int,
    as_of: datetime,
) -> FunnelReason:
    included_code, excluded_code, unknown_code = codes
    threshold = f">= {COMPONENT_GATE_MIDPOINT:g}"
    if component.score is None:
        detail = "; ".join(component.unknowns) or component.reasons[0]
        return _reason(
            unknown_code,
            "UNKNOWN",
            f"{component.name} is UNKNOWN: {detail}",
            configuration_version=configuration_version,
            as_of=as_of,
            threshold=threshold,
        )
    passed = component.score >= COMPONENT_GATE_MIDPOINT
    return _reason(
        included_code if passed else excluded_code,
        "INCLUDED" if passed else "EXCLUDED",
        component.reasons[0],
        configuration_version=configuration_version,
        as_of=as_of,
        observed=f"{component.score:g}",
        threshold=threshold,
    )


def _any_evidence_outcome(reasons: Sequence[FunnelReason]) -> FunnelOutcome:
    """The candidate gate needs one recorded successful entry, not every movement."""
    if any(reason.outcome == "INCLUDED" for reason in reasons):
        return "INCLUDED"
    if all(reason.outcome == "UNKNOWN" for reason in reasons):
        return "UNKNOWN"
    return "EXCLUDED"


def _all_criteria_outcome(reasons: Sequence[FunnelReason]) -> FunnelOutcome:
    """The winner gate needs every frozen cohort fact; one failure is decisive."""
    if any(reason.outcome == "EXCLUDED" for reason in reasons):
        return "EXCLUDED"
    return "UNKNOWN"


def _wallet_evidence(discovery: HistoricalWinnerDiscovery) -> dict[str, _WalletEvidence]:
    evidence: dict[str, _WalletEvidence] = {}

    def entry_for(address: str) -> _WalletEvidence:
        return evidence.setdefault(address, _WalletEvidence(address=address))

    for candidate in discovery.candidate_wallets:
        entry_for(candidate.wallet_address).criteria.extend(candidate.evidence)
    for record in discovery.early_buyers:
        entry_for(record.wallet_address).records.append(record)
    return {address: evidence[address] for address in sorted(evidence)}


def _included(stage: FunnelStage) -> list[str]:
    return [member.subject for member in stage.members if member.outcome == "INCLUDED"]


def _stage(
    name: FunnelStageName,
    members: Sequence[FunnelMember],
    configuration_version: int,
    as_of: datetime,
) -> FunnelStage:
    return FunnelStage(
        name=name,
        subject=_STAGE_SUBJECTS[name],
        as_of=as_of,
        configuration_version=configuration_version,
        evaluated=len(members),
        included=sum(1 for member in members if member.outcome == "INCLUDED"),
        excluded=sum(1 for member in members if member.outcome == "EXCLUDED"),
        unknown=sum(1 for member in members if member.outcome == "UNKNOWN"),
        members=list(members),
    )


class DiscoveryFunnelService:
    """Compose recorded discovery, Wallet scoring, and the funnel gates."""

    def __init__(
        self,
        discovery_source: HistoricalWinnerSource,
        wallet_score_source: WalletScoreSource,
        funnel_store: DiscoveryFunnelStore,
        configuration_store: ResearchConfigurationStore,
    ) -> None:
        self._discovery_source = discovery_source
        self._wallet_score_source = wallet_score_source
        self._funnel_store = funnel_store
        self._configuration_store = configuration_store

    async def run(self, request: DiscoveryFunnelRequest) -> DiscoveryFunnelRun:
        configuration = await self._configuration_store.get_active()
        run = await self._funnel_store.start_run(request, configuration)
        try:
            stages, warnings = await self._build_stages(request, configuration)
        except Exception as error:  # the run boundary records every failure as FAILED
            message = f"{type(error).__name__}: {error}"
            await self._funnel_store.fail_run(run.run_id, message)
            raise DiscoveryFunnelRunError(message) from error
        return await self._funnel_store.complete_run(run.run_id, stages, warnings)

    async def _build_stages(
        self,
        request: DiscoveryFunnelRequest,
        configuration: VersionedResearchConfiguration,
    ) -> tuple[list[FunnelStage], list[str]]:
        discovery = await self._discovery_source.discover(request.cohort, configuration)
        version = configuration.version
        qualification_as_of = request.cohort.qualification_as_of
        score_as_of = request.as_of
        evidence = _wallet_evidence(discovery)

        token_stage = _stage(
            "TOKENS_ANALYZED",
            [
                _token_member(winner, version, qualification_as_of)
                for winner in discovery.winners
            ],
            version,
            qualification_as_of,
        )
        found_stage = _stage(
            "WALLETS_FOUND",
            [_found_member(wallet, version, qualification_as_of) for wallet in evidence.values()],
            version,
            qualification_as_of,
        )
        candidates_stage = _stage(
            "CANDIDATES",
            [
                _candidate_member(wallet, version, qualification_as_of)
                for wallet in evidence.values()
            ],
            version,
            qualification_as_of,
        )
        stages = [token_stage, found_stage, candidates_stage]

        scores, unrecorded = await self._score(_included(candidates_stage), score_as_of)
        for name in ("PROFITABLE", "CONSISTENT", "COPYABLE"):
            stages.append(
                _stage(
                    name,
                    [
                        _component_member(
                            subject, name, scores, unrecorded, version, score_as_of
                        )
                        for subject in _included(stages[-1])
                    ],
                    version,
                    score_as_of,
                )
            )
        stages.append(
            _stage(
                "SMART_WALLET",
                [
                    _smart_wallet_member(
                        subject, scores, unrecorded, version, score_as_of
                    )
                    for subject in _included(stages[-1])
                ],
                version,
                score_as_of,
            )
        )

        warnings = list(
            dict.fromkeys(
                warning
                for stage in stages
                for member in stage.members
                for warning in member.warnings
            )
        )
        return stages, warnings

    async def _score(
        self, addresses: Sequence[str], as_of: datetime
    ) -> tuple[dict[str, WalletScore], dict[str, str]]:
        scores: dict[str, WalletScore] = {}
        unrecorded: dict[str, str] = {}
        for address in addresses:
            try:
                result = await self._wallet_score_source.score(address, as_of)
            except KeyError:
                unrecorded[address] = (
                    "No Wallet accounting history is recorded at the as-of time, so this Wallet "
                    "cannot be judged yet."
                )
                continue
            scores[address] = result.score
        return scores, unrecorded


def _token_member(
    winner: HistoricalWinner, configuration_version: int, as_of: datetime
) -> FunnelMember:
    reasons = [
        _token_reason(criterion, configuration_version, as_of)
        for criterion in winner.qualifying_facts
    ]
    if not reasons:
        reasons = [
            _reason(
                "TOKEN_CRITERION_UNRECOGNIZED",
                "UNKNOWN",
                "The cohort recorded no winner criterion for this Token, so it cannot be judged.",
                configuration_version=configuration_version,
                as_of=as_of,
            )
        ]
    return FunnelMember(
        subject=winner.token_address,
        outcome="INCLUDED" if winner.qualified else _all_criteria_outcome(reasons),
        reasons=reasons,
        evidence=[
            (
                f"{winner.token_symbol} created {winner.created_at.isoformat()} with initial "
                f"market cap {winner.initial_market_cap_usd} and peak market cap "
                f"{winner.peak_market_cap_usd}."
            )
        ],
    )


def _found_member(
    wallet: _WalletEvidence, configuration_version: int, as_of: datetime
) -> FunnelMember:
    observations = ", ".join(criterion.observed for criterion in wallet.criteria) or "UNKNOWN"
    return FunnelMember(
        subject=wallet.address,
        outcome="INCLUDED",
        reasons=[
            _reason(
                "RECORDED_WINNER_ACTIVITY",
                "INCLUDED",
                (
                    "Recorded activity on a qualified historical winner Token was found for this "
                    f"Wallet: {observations}."
                ),
                configuration_version=configuration_version,
                as_of=as_of,
                observed=observations,
                threshold="recorded movement on a qualified winner Token",
            )
        ],
        evidence=_entry_evidence(wallet),
        coverage=_entry_coverage(wallet),
        warnings=_entry_warnings(wallet),
    )


def _candidate_member(
    wallet: _WalletEvidence, configuration_version: int, as_of: datetime
) -> FunnelMember:
    reasons = [
        _entry_reason(criterion, configuration_version, as_of) for criterion in wallet.criteria
    ]
    if not reasons:
        reasons = [
            _reason(
                "ENTRY_EVIDENCE_UNRECOGNIZED",
                "UNKNOWN",
                (
                    "No recorded entry evidence exists for this Wallet, so its entry cannot be "
                    "judged."
                ),
                configuration_version=configuration_version,
                as_of=as_of,
            )
        ]
    return FunnelMember(
        subject=wallet.address,
        outcome=_any_evidence_outcome(reasons),
        reasons=reasons,
        evidence=_entry_evidence(wallet),
        coverage=_entry_coverage(wallet),
        warnings=_entry_warnings(wallet),
    )


def _unrecorded_member(
    subject: str, message: str, configuration_version: int, as_of: datetime
) -> FunnelMember:
    return FunnelMember(
        subject=subject,
        outcome="UNKNOWN",
        reasons=[
            _reason(
                "NO_RECORDED_ACCOUNTING",
                "UNKNOWN",
                message,
                configuration_version=configuration_version,
                as_of=as_of,
            )
        ],
        warnings=[message],
    )


def _component_member(
    subject: str,
    name: FunnelStageName,
    scores: dict[str, WalletScore],
    unrecorded: dict[str, str],
    configuration_version: int,
    as_of: datetime,
) -> FunnelMember:
    if subject in unrecorded:
        return _unrecorded_member(subject, unrecorded[subject], configuration_version, as_of)
    score = scores[subject]
    component = _component(score, _STAGE_COMPONENTS[name])
    reason = _component_reason(component, _GATE_CODES[name], configuration_version, as_of)
    return FunnelMember(
        subject=subject,
        outcome=reason.outcome,
        reasons=[reason],
        evidence=list(component.evidence),
        coverage=_score_coverage(score),
        warnings=list(score.warnings),
    )


def _smart_wallet_member(
    subject: str,
    scores: dict[str, WalletScore],
    unrecorded: dict[str, str],
    configuration_version: int,
    as_of: datetime,
) -> FunnelMember:
    if subject in unrecorded:
        return _unrecorded_member(subject, unrecorded[subject], configuration_version, as_of)
    score = scores[subject]
    recommendation = " ".join(score.reasons[1:]) or score.reasons[0]
    if score.recommended_state == "SMART_WALLET":
        reason = _reason(
            "REGISTRY_SMART_WALLET",
            "INCLUDED",
            recommendation,
            configuration_version=configuration_version,
            as_of=as_of,
            observed=score.recommended_state,
            threshold="SMART_WALLET",
        )
    else:
        blockers = [
            *score.unknowns,
            *[
                f"Coverage from {item.source} is incomplete."
                for item in score.coverage
                if not item.complete
            ],
        ]
        if blockers:
            reason = _reason(
                "SMART_WALLET_BLOCKED_BY_UNKNOWN_EVIDENCE",
                "UNKNOWN",
                "The Registry cannot confirm SMART_WALLET: " + "; ".join(blockers),
                configuration_version=configuration_version,
                as_of=as_of,
                observed=score.recommended_state,
                threshold="SMART_WALLET",
            )
        else:
            reason = _reason(
                "REGISTRY_NOT_SMART_WALLET",
                "EXCLUDED",
                recommendation,
                configuration_version=configuration_version,
                as_of=as_of,
                observed=score.recommended_state,
                threshold="SMART_WALLET",
            )
    return FunnelMember(
        subject=subject,
        outcome=reason.outcome,
        reasons=[reason],
        evidence=list(score.evidence),
        coverage=_score_coverage(score),
        warnings=list(score.warnings),
    )


class InMemoryDiscoveryFunnelStore:
    """Deterministic run store used by HTTP tests."""

    def __init__(
        self,
        *,
        now: Callable[[], datetime] = lambda: datetime.now(timezone.utc),
        id_factory: Callable[[], UUID] = uuid4,
    ) -> None:
        self._now = now
        self._id_factory = id_factory
        self._runs: dict[str, DiscoveryFunnelRun] = {}
        self._order: list[str] = []

    async def start_run(
        self,
        request: DiscoveryFunnelRequest,
        configuration: VersionedResearchConfiguration,
    ) -> DiscoveryFunnelRun:
        run = DiscoveryFunnelRun(
            run_id=str(self._id_factory()),
            cohort=request.cohort,
            as_of=request.as_of,
            configuration_id=str(configuration.id),
            configuration_version=configuration.version,
            status="RUNNING",
            started_at=self._now(),
        )
        self._runs[run.run_id] = run
        self._order.append(run.run_id)
        return run

    async def complete_run(
        self,
        run_id: str,
        stages: Sequence[FunnelStage],
        warnings: Sequence[str],
    ) -> DiscoveryFunnelRun:
        run = self._runs[run_id]
        completed = DiscoveryFunnelRun.model_validate(
            {
                **run.model_dump(),
                "status": "COMPLETED",
                "completed_at": self._now(),
                "stages": [stage.model_dump() for stage in stages],
                "warnings": list(warnings),
            }
        )
        self._runs[run_id] = completed
        return completed

    async def fail_run(self, run_id: str, error: str) -> DiscoveryFunnelRun:
        run = self._runs[run_id]
        failed = DiscoveryFunnelRun.model_validate(
            {
                **run.model_dump(),
                "status": "FAILED",
                "completed_at": self._now(),
                "error": error,
                "stages": [],
                "warnings": [],
            }
        )
        self._runs[run_id] = failed
        return failed

    async def latest(self) -> Optional[DiscoveryFunnelRun]:
        if not self._order:
            return None
        return self._runs[self._order[-1]]


# Fixed column list shared by every funnel-run statement; never built from input.
_RUN_COLUMNS = (
    "run_id, cohort, as_of, configuration_id, configuration_version, status, error, "
    "stages, warnings, started_at, completed_at"
)


class PostgresDiscoveryFunnelStore:
    """PostgreSQL source of truth for funnel runs and their stages."""

    def __init__(self, engine: AsyncEngine) -> None:
        self._engine = engine

    async def start_run(
        self,
        request: DiscoveryFunnelRequest,
        configuration: VersionedResearchConfiguration,
    ) -> DiscoveryFunnelRun:
        async with self._engine.begin() as connection:
            result = await connection.execute(
                text(
                    f"""
                    INSERT INTO discovery_funnel_runs (
                        run_id, cohort, as_of, configuration_id, configuration_version,
                        status, stages, warnings
                    ) VALUES (
                        CAST(:run_id AS UUID), CAST(:cohort AS JSONB), :as_of,
                        CAST(:configuration_id AS UUID), :configuration_version,
                        'RUNNING', CAST(:stages AS JSONB), CAST(:warnings AS JSONB)
                    )
                    RETURNING {_RUN_COLUMNS}
                    """
                ),
                {
                    "run_id": str(uuid4()),
                    "cohort": json.dumps(request.cohort.model_dump(mode="json")),
                    "as_of": request.as_of,
                    "configuration_id": str(configuration.id),
                    "configuration_version": configuration.version,
                    "stages": "[]",
                    "warnings": "[]",
                },
            )
            return self._from_row(result.mappings().one())

    async def complete_run(
        self,
        run_id: str,
        stages: Sequence[FunnelStage],
        warnings: Sequence[str],
    ) -> DiscoveryFunnelRun:
        async with self._engine.begin() as connection:
            result = await connection.execute(
                text(
                    f"""
                    UPDATE discovery_funnel_runs
                    SET status = 'COMPLETED',
                        stages = CAST(:stages AS JSONB),
                        warnings = CAST(:warnings AS JSONB),
                        error = NULL,
                        completed_at = now()
                    WHERE run_id = CAST(:run_id AS UUID)
                    RETURNING {_RUN_COLUMNS}
                    """
                ),
                {
                    "run_id": run_id,
                    "stages": json.dumps([stage.model_dump(mode="json") for stage in stages]),
                    "warnings": json.dumps(list(warnings)),
                },
            )
            return self._from_row(result.mappings().one())

    async def fail_run(self, run_id: str, error: str) -> DiscoveryFunnelRun:
        async with self._engine.begin() as connection:
            result = await connection.execute(
                text(
                    f"""
                    UPDATE discovery_funnel_runs
                    SET status = 'FAILED',
                        error = :error,
                        stages = CAST('[]' AS JSONB),
                        warnings = CAST('[]' AS JSONB),
                        completed_at = now()
                    WHERE run_id = CAST(:run_id AS UUID)
                    RETURNING {_RUN_COLUMNS}
                    """
                ),
                {"run_id": run_id, "error": error},
            )
            return self._from_row(result.mappings().one())

    async def latest(self) -> Optional[DiscoveryFunnelRun]:
        async with self._engine.connect() as connection:
            result = await connection.execute(
                text(
                    f"""
                    SELECT {_RUN_COLUMNS}
                    FROM discovery_funnel_runs
                    ORDER BY started_at DESC, run_id DESC
                    LIMIT 1
                    """
                )
            )
            row = result.mappings().one_or_none()
        return None if row is None else self._from_row(row)

    @staticmethod
    def _from_row(row: RowMapping) -> DiscoveryFunnelRun:
        return DiscoveryFunnelRun(
            run_id=str(row["run_id"]),
            cohort=HistoricalWinnerCohortRequest.model_validate(_json_value(row["cohort"])),
            as_of=row["as_of"],
            configuration_id=str(row["configuration_id"]),
            configuration_version=int(row["configuration_version"]),
            status=row["status"],
            started_at=row["started_at"],
            completed_at=row["completed_at"],
            error=row["error"],
            stages=[FunnelStage.model_validate(stage) for stage in _json_value(row["stages"])],
            warnings=[str(warning) for warning in _json_value(row["warnings"])],
        )
