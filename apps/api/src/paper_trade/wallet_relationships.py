"""Evidence-backed Wallet relationships and Contributing-independent Wallet counts.

Relationships are derived from recorded Wallet activity and recorded funding
evidence.  They are behavioral observations only: every relationship carries its
evidence, confidence, coverage, and as-of time, and no relationship claims shared
ownership, control, or wrongdoing.  Missing evidence is reported as UNKNOWN and
never treated as proof that two Wallets are independent or related.
"""

import json
from collections.abc import Callable, Sequence
from datetime import datetime, timezone
from typing import Any, Literal, Optional, Protocol

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator
from sqlalchemy import text
from sqlalchemy.engine import RowMapping
from sqlalchemy.ext.asyncio import AsyncEngine

from paper_trade.launch_events import _is_solana_public_key
from paper_trade.research_configuration import (
    ClusterSettings,
    RelationshipConfidence,
    ResearchConfigurationStore,
    VersionedResearchConfiguration,
)
from paper_trade.wallet_accounting import (
    RecordedWalletMovement,
    WalletAccounting,
    WalletAccountingStore,
    WalletTrade,
)

RelationshipEvidenceType = Literal[
    "COMMON_FUNDING",
    "INTER_WALLET_TRANSFER",
    "SYNCHRONIZED_TRADES",
    "TRANSACTION_PATTERN_SIMILARITY",
    "SHARED_TOKEN_HISTORY",
]
_EVIDENCE_ORDER: tuple[RelationshipEvidenceType, ...] = (
    "COMMON_FUNDING",
    "INTER_WALLET_TRANSFER",
    "SYNCHRONIZED_TRADES",
    "TRANSACTION_PATTERN_SIMILARITY",
    "SHARED_TOKEN_HISTORY",
)
_DIRECT_EVIDENCE_TYPES: tuple[RelationshipEvidenceType, ...] = (
    "COMMON_FUNDING",
    "INTER_WALLET_TRANSFER",
)
_CONFIDENCE_RANK: dict[RelationshipConfidence, int] = {"LOW": 0, "MEDIUM": 1, "HIGH": 2}


class WalletRelationshipModel(BaseModel):
    """Base document for Wallet relationship public contracts."""

    model_config = ConfigDict(extra="forbid")


class RelationshipCoverage(WalletRelationshipModel):
    """One evidence source used to judge a relationship, including its gaps."""

    source: str = Field(min_length=1)
    complete: bool
    unknown_fields: list[str] = Field(default_factory=list)


class WalletRelationshipEvidence(WalletRelationshipModel):
    """One behavioral evidence type observed between two Wallets."""

    evidence_type: RelationshipEvidenceType
    wording: str = Field(min_length=1)
    evidence: list[str] = Field(min_length=1)
    observed_at: datetime
    confidence: RelationshipConfidence


class WalletRelationship(WalletRelationshipModel):
    """One evidence-backed relationship between two Wallets."""

    wallets: list[str] = Field(min_length=2, max_length=2)
    confidence: RelationshipConfidence
    as_of: datetime
    wording: str = Field(min_length=1)
    evidence: list[WalletRelationshipEvidence] = Field(min_length=1)
    coverage: list[RelationshipCoverage] = Field(min_length=1)
    unknowns: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)

    @field_validator("wallets")
    @classmethod
    def validate_wallets(cls, wallets: list[str]) -> list[str]:
        for wallet in wallets:
            if not _is_solana_public_key(wallet):
                raise ValueError("wallets must be valid Solana public keys")
        if wallets[0] == wallets[1]:
            raise ValueError("a relationship requires two distinct Wallets")
        if wallets != sorted(wallets):
            raise ValueError("relationship wallets must be sorted")
        return wallets


class WalletFundingEvidence(WalletRelationshipModel):
    """One recorded funding movement from a source address to a Wallet."""

    wallet_address: str
    funder_address: str
    signature: str = Field(min_length=1)
    funded_at: datetime
    amount_sol: float = Field(gt=0)
    evidence: list[str] = Field(min_length=1)

    @field_validator("wallet_address", "funder_address")
    @classmethod
    def validate_solana_public_key(cls, value: str) -> str:
        if not _is_solana_public_key(value):
            raise ValueError("must be a valid Solana public key")
        return value

    @model_validator(mode="after")
    def validate_distinct_addresses(self) -> "WalletFundingEvidence":
        if self.wallet_address == self.funder_address:
            raise ValueError("a Wallet cannot fund itself")
        return self


class WalletFundingCoverage(WalletRelationshipModel):
    """Coverage declared by the recorded Wallet funding source."""

    provider: str = Field(min_length=1)
    requested_as_of: datetime
    as_of_start: datetime
    as_of_end: datetime
    complete: bool
    unknown_fields: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_interval(self) -> "WalletFundingCoverage":
        if self.as_of_end < self.as_of_start:
            raise ValueError("as_of_end must not be earlier than as_of_start")
        if not self.complete and not (self.unknown_fields or self.warnings):
            raise ValueError("incomplete coverage must declare unknown_fields or warnings")
        return self


class WalletFundingResult(WalletRelationshipModel):
    funding: list[WalletFundingEvidence]
    coverage: WalletFundingCoverage


class WalletFundingSource(Protocol):
    """Replaceable Adapter contract for recorded Wallet funding evidence."""

    async def funding(self, addresses: Sequence[str], as_of: datetime) -> WalletFundingResult:
        """Return funding evidence no later than ``as_of`` for the requested Wallets."""


class RecordedWalletFundingSource:
    """Fixture-only funding Adapter; it performs no network calls."""

    def __init__(
        self, funding: Sequence[WalletFundingEvidence], coverage: WalletFundingCoverage
    ) -> None:
        self._funding = [
            WalletFundingEvidence.model_validate(item.model_dump()) for item in funding
        ]
        self._coverage = WalletFundingCoverage.model_validate(coverage.model_dump())

    async def funding(self, addresses: Sequence[str], as_of: datetime) -> WalletFundingResult:
        requested = set(addresses)
        selected = [
            item
            for item in self._funding
            if item.wallet_address in requested and item.funded_at <= as_of
        ]
        return WalletFundingResult(
            funding=sorted(
                selected,
                key=lambda item: (item.wallet_address, item.funded_at, item.signature),
            ),
            coverage=self._coverage.model_copy(update={"requested_as_of": as_of}),
        )


class ContributingIndependentGroup(WalletRelationshipModel):
    """One collapsed group of Wallets that are not contributing-independent."""

    wallets: list[str] = Field(min_length=1)
    representative: str
    reason: str = Field(min_length=1)


class ContributingIndependentCount(WalletRelationshipModel):
    """Raw Wallet count alongside the collapsed Contributing-independent count."""

    raw_wallet_count: int = Field(ge=0)
    contributing_independent_wallet_count: int = Field(ge=0)
    groups: list[ContributingIndependentGroup]
    as_of: datetime
    configuration_id: str
    configuration_version: int = Field(ge=1)
    confidence_threshold: RelationshipConfidence
    evidence: list[str] = Field(min_length=1)
    unknowns: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_counts(self) -> "ContributingIndependentCount":
        if self.contributing_independent_wallet_count > self.raw_wallet_count:
            raise ValueError(
                "the Contributing-independent count must not exceed the raw Wallet count"
            )
        if self.contributing_independent_wallet_count != len(self.groups):
            raise ValueError(
                "the Contributing-independent count must equal the number of collapsed groups"
            )
        if self.raw_wallet_count != sum(len(group.wallets) for group in self.groups):
            raise ValueError("the raw Wallet count must equal the wallets across every group")
        return self


class WalletRelationships(WalletRelationshipModel):
    """Related Wallets for one Wallet, with its Contributing-independent count."""

    address: str
    as_of: datetime
    configuration_id: str
    configuration_version: int = Field(ge=1)
    relationships: list[WalletRelationship]
    contributing_independent: ContributingIndependentCount
    coverage: list[RelationshipCoverage] = Field(min_length=1)
    unknowns: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)

    @field_validator("address")
    @classmethod
    def validate_address(cls, value: str) -> str:
        if not _is_solana_public_key(value):
            raise ValueError("address must be a valid Solana public key")
        return value


class WalletRelationshipAnalysisResult(WalletRelationshipModel):
    """Observable idempotency outcome of one recorded relationship analysis."""

    created: bool
    version: int = Field(ge=1)
    created_at: datetime
    analysis: WalletRelationships


class WalletRelationshipStore(Protocol):
    """Durable persistence seam for recorded relationship analyses."""

    async def record(self, analysis: WalletRelationships) -> WalletRelationshipAnalysisResult:
        """Persist a new analysis version, or return the identical existing version."""

    async def latest(self, address: str, as_of: datetime) -> Optional[WalletRelationships]:
        """Return the latest recorded analysis computed at or before ``as_of``."""


def _json_document(document: WalletRelationshipModel) -> str:
    return json.dumps(document.model_dump(mode="json"), sort_keys=True, separators=(",", ":"))


def _json_value(value: Any) -> Any:
    return json.loads(value) if isinstance(value, str) else value


def _round(value: float) -> float:
    return round(value, 4)


def _funding_by_wallet(
    funding: WalletFundingResult,
) -> dict[str, list[WalletFundingEvidence]]:
    grouped: dict[str, list[WalletFundingEvidence]] = {}
    for item in funding.funding:
        grouped.setdefault(item.wallet_address, []).append(item)
    return grouped


def _common_funding(
    left: str,
    right: str,
    grouped: dict[str, list[WalletFundingEvidence]],
) -> Optional[WalletRelationshipEvidence]:
    matches: list[tuple[WalletFundingEvidence, WalletFundingEvidence]] = []
    for first in grouped.get(left, []):
        for second in grouped.get(right, []):
            if first.funder_address == second.funder_address:
                matches.append((first, second))
    if not matches:
        return None
    matches.sort(key=lambda pair: (pair[0].funded_at, pair[0].signature, pair[1].signature))
    observed_at = max(max(first.funded_at, second.funded_at) for first, second in matches)
    return WalletRelationshipEvidence(
        evidence_type="COMMON_FUNDING",
        wording=(
            "Both Wallets received recorded funding from the same source address; shared funding "
            "is behavioral evidence and does not establish common ownership or control."
        ),
        evidence=[
            (
                f"{first.signature} funded {first.wallet_address} with {first.amount_sol:g} SOL "
                f"from {first.funder_address}, and {second.signature} funded "
                f"{second.wallet_address} from the same source."
            )
            for first, second in matches[:3]
        ],
        observed_at=observed_at,
        confidence="HIGH",
    )


def _transfers_between(
    outgoing: Sequence[RecordedWalletMovement], incoming: Sequence[RecordedWalletMovement]
) -> list[tuple[RecordedWalletMovement, RecordedWalletMovement]]:
    matched: list[tuple[RecordedWalletMovement, RecordedWalletMovement]] = []
    for source in outgoing:
        if source.movement_type != "TRANSFER_OUT":
            continue
        for target in incoming:
            if target.movement_type != "TRANSFER_IN":
                continue
            if source.token_address == target.token_address and source.quantity == target.quantity:
                matched.append((source, target))
    return matched


def _inter_wallet_transfer(
    subject: WalletAccounting, peer: WalletAccounting
) -> Optional[WalletRelationshipEvidence]:
    subject_activities = {activity.signature: activity for activity in subject.source_transactions}
    peer_activities = {activity.signature: activity for activity in peer.source_transactions}
    matches: list[tuple[str, str, str, str, float, datetime]] = []
    for signature in sorted(set(subject_activities) & set(peer_activities)):
        subject_activity = subject_activities[signature]
        peer_activity = peer_activities[signature]
        observed_at = max(subject_activity.chain_time, peer_activity.chain_time)
        for sender, receiver in (
            (subject.address, peer.address),
            (peer.address, subject.address),
        ):
            outgoing = (
                subject_activity.movements if sender == subject.address else peer_activity.movements
            )
            incoming = (
                peer_activity.movements if sender == subject.address else subject_activity.movements
            )
            for source, _ in _transfers_between(outgoing, incoming):
                matches.append(
                    (
                        signature,
                        sender,
                        receiver,
                        source.token_address,
                        source.quantity,
                        observed_at,
                    )
                )
    if not matches:
        return None
    matches.sort(key=lambda match: (match[5], match[0], match[1]))
    return WalletRelationshipEvidence(
        evidence_type="INTER_WALLET_TRANSFER",
        wording=(
            "Recorded transactions moved Tokens directly between the two Wallets; a recorded "
            "transfer is behavioral evidence and does not establish common ownership or intent."
        ),
        evidence=[
            (
                f"{signature} records {quantity:g} units of {token} leaving {sender} and arriving "
                f"at {receiver}; the movement is recorded for both Wallets."
            )
            for signature, sender, receiver, token, quantity, _ in matches[:3]
        ],
        observed_at=max(match[5] for match in matches),
        confidence="HIGH",
    )


def _buys_by_token(accounting: WalletAccounting) -> dict[str, list[WalletTrade]]:
    grouped: dict[str, list[WalletTrade]] = {}
    for trade in accounting.trades:
        if trade.succeeded and trade.movement_type == "BUY":
            grouped.setdefault(trade.token_address, []).append(trade)
    for trades in grouped.values():
        trades.sort(key=lambda trade: (trade.chain_time, trade.slot, trade.signature))
    return grouped


def _synchronized_trades(
    subject: WalletAccounting, peer: WalletAccounting, window_seconds: int
) -> Optional[WalletRelationshipEvidence]:
    subject_buys = _buys_by_token(subject)
    peer_buys = _buys_by_token(peer)
    matches: list[tuple[str, WalletTrade, WalletTrade, float]] = []
    for token in sorted(set(subject_buys) & set(peer_buys)):
        for first in subject_buys[token]:
            for second in peer_buys[token]:
                delta = abs((first.chain_time - second.chain_time).total_seconds())
                if delta <= window_seconds:
                    matches.append((token, first, second, delta))
    if not matches:
        return None
    matches.sort(key=lambda match: (match[0], match[1].chain_time, match[2].chain_time))
    return WalletRelationshipEvidence(
        evidence_type="SYNCHRONIZED_TRADES",
        wording=(
            "Both Wallets bought the same Token inside the configured window; synchronized timing "
            "is behavioral evidence and does not establish coordination."
        ),
        evidence=[
            (
                f"{subject.address} bought {token} at {first.chain_time.isoformat()} and "
                f"{peer.address} bought {token} at {second.chain_time.isoformat()}, {delta:g} "
                f"seconds apart within the configured {window_seconds} second window."
            )
            for token, first, second, delta in matches[:3]
        ],
        observed_at=max(max(match[1].chain_time, match[2].chain_time) for match in matches),
        confidence="MEDIUM",
    )


def _traded_tokens(accounting: WalletAccounting) -> set[str]:
    return {
        trade.token_address
        for trade in accounting.trades
        if trade.succeeded and trade.movement_type in ("BUY", "SELL")
    }


def _buy_sequence(accounting: WalletAccounting) -> list[str]:
    first_buy: dict[str, datetime] = {}
    for trade in accounting.trades:
        if not trade.succeeded or trade.movement_type != "BUY":
            continue
        current = first_buy.get(trade.token_address)
        if current is None or trade.chain_time < current:
            first_buy[trade.token_address] = trade.chain_time
    return [
        token for token, _ in sorted(first_buy.items(), key=lambda item: (item[1], item[0]))
    ]


def _longest_common_subsequence(left: Sequence[str], right: Sequence[str]) -> int:
    previous = [0] * (len(right) + 1)
    for token in left:
        current = [0]
        for index, other in enumerate(right, start=1):
            if token == other:
                current.append(previous[index - 1] + 1)
            else:
                current.append(max(previous[index], current[index - 1]))
        previous = current
    return previous[-1]


def _latest_trade_time(*accountings: WalletAccounting) -> datetime:
    times = [
        trade.chain_time
        for accounting in accountings
        for trade in accounting.trades
        if trade.succeeded
    ]
    if times:
        return max(times)
    return max(accounting.as_of for accounting in accountings)


def _shared_token_history(
    subject: WalletAccounting, peer: WalletAccounting, minimum_percent: float
) -> Optional[WalletRelationshipEvidence]:
    left = _traded_tokens(subject)
    right = _traded_tokens(peer)
    union = left | right
    if not union:
        return None
    shared = left & right
    overlap = _round(100 * len(shared) / len(union))
    if overlap < minimum_percent:
        return None
    return WalletRelationshipEvidence(
        evidence_type="SHARED_TOKEN_HISTORY",
        wording=(
            "Both Wallets traded an overlapping set of Tokens above the configured threshold; "
            "shared Token history is behavioral overlap and does not establish common control."
        ),
        evidence=[
            (
                f"{len(shared)} of {len(union)} traded Tokens are shared between {subject.address} "
                f"and {peer.address}, a {overlap:g}% overlap against the configured "
                f"{minimum_percent:g}% threshold."
            )
        ],
        observed_at=_latest_trade_time(subject, peer),
        confidence="LOW",
    )


def _transaction_pattern_similarity(
    subject: WalletAccounting, peer: WalletAccounting, minimum_percent: float
) -> Optional[WalletRelationshipEvidence]:
    left = _buy_sequence(subject)
    right = _buy_sequence(peer)
    if not left or not right:
        return None
    matched = _longest_common_subsequence(left, right)
    similarity = _round(100 * matched / max(len(left), len(right)))
    if similarity < minimum_percent:
        return None
    return WalletRelationshipEvidence(
        evidence_type="TRANSACTION_PATTERN_SIMILARITY",
        wording=(
            "The recorded buy order of the two Wallets matches above the configured threshold; "
            "matching order is behavioral similarity and does not establish common control."
        ),
        evidence=[
            (
                f"{matched} of {max(len(left), len(right))} ordered Token entries match between "
                f"{subject.address} ({len(left)} Tokens) and {peer.address} ({len(right)} Tokens), "
                f"a {similarity:g}% ordered-pattern similarity against the configured "
                f"{minimum_percent:g}% threshold."
            )
        ],
        observed_at=_latest_trade_time(subject, peer),
        confidence="MEDIUM",
    )


def _relationship_confidence(
    evidence_types: Sequence[RelationshipEvidenceType],
) -> RelationshipConfidence:
    direct = [item for item in evidence_types if item in _DIRECT_EVIDENCE_TYPES]
    behavioral = [item for item in evidence_types if item not in _DIRECT_EVIDENCE_TYPES]
    if len(direct) >= 2 or (direct and behavioral):
        return "HIGH"
    if direct:
        return "MEDIUM"
    if len(behavioral) >= 2:
        return "MEDIUM"
    return "LOW"


def _pair_coverage(
    subject: WalletAccounting, peer: WalletAccounting, funding: WalletFundingCoverage
) -> list[RelationshipCoverage]:
    selected: dict[str, RelationshipCoverage] = {}
    for accounting in (subject, peer):
        for coverage in accounting.coverage:
            candidate = RelationshipCoverage(
                source=coverage.provider,
                complete=coverage.complete,
                unknown_fields=list(coverage.unknown_fields),
            )
            existing = selected.get(candidate.source)
            if existing is None or (existing.complete and not candidate.complete):
                selected[candidate.source] = candidate
    selected[funding.provider] = RelationshipCoverage(
        source=funding.provider,
        complete=funding.complete,
        unknown_fields=list(funding.unknown_fields),
    )
    return [selected[source] for source in sorted(selected)]


def _overall_coverage(
    accountings: Sequence[WalletAccounting], funding: WalletFundingCoverage
) -> list[RelationshipCoverage]:
    selected: dict[str, RelationshipCoverage] = {}
    for accounting in accountings:
        for coverage in accounting.coverage:
            candidate = RelationshipCoverage(
                source=coverage.provider,
                complete=coverage.complete,
                unknown_fields=list(coverage.unknown_fields),
            )
            existing = selected.get(candidate.source)
            if existing is None or (existing.complete and not candidate.complete):
                selected[candidate.source] = candidate
    selected[funding.provider] = RelationshipCoverage(
        source=funding.provider,
        complete=funding.complete,
        unknown_fields=list(funding.unknown_fields),
    )
    return [selected[source] for source in sorted(selected)]


def _funding_unknown(
    funding: WalletFundingResult, subject: str, peer: str
) -> str:
    if funding.coverage.complete:
        return (
            f"COMMON_FUNDING: no recorded funding source is shared by {subject} and {peer}."
        )
    return (
        "COMMON_FUNDING: recorded funding evidence is unavailable, so common funding between "
        f"{subject} and {peer} is UNKNOWN."
    )


def _relationship(
    subject: WalletAccounting,
    peer: WalletAccounting,
    funding: WalletFundingResult,
    settings: ClusterSettings,
    as_of: datetime,
) -> Optional[WalletRelationship]:
    evidence: list[WalletRelationshipEvidence] = []
    grouped = _funding_by_wallet(funding)
    common = _common_funding(subject.address, peer.address, grouped)
    if common is not None:
        evidence.append(common)
    transfer = _inter_wallet_transfer(subject, peer)
    if transfer is not None:
        evidence.append(transfer)
    synchronized = _synchronized_trades(
        subject, peer, settings.synchronized_trade_window_seconds
    )
    if synchronized is not None:
        evidence.append(synchronized)
    pattern = _transaction_pattern_similarity(
        subject, peer, settings.transaction_pattern_similarity_minimum_percent
    )
    if pattern is not None:
        evidence.append(pattern)
    shared = _shared_token_history(
        subject, peer, settings.shared_token_history_minimum_percent
    )
    if shared is not None:
        evidence.append(shared)
    if not evidence:
        return None
    evidence.sort(key=lambda item: _EVIDENCE_ORDER.index(item.evidence_type))
    confidence = _relationship_confidence([item.evidence_type for item in evidence])
    unknowns = (
        []
        if common is not None
        else [_funding_unknown(funding, subject.address, peer.address)]
    )
    return WalletRelationship(
        wallets=sorted((subject.address, peer.address)),
        confidence=confidence,
        as_of=as_of,
        wording=(
            f"Recorded activity shows {len(evidence)} behavioral evidence type(s) between "
            f"{subject.address} and {peer.address}: "
            f"{', '.join(item.evidence_type for item in evidence)}. This describes observable "
            "patterns only and does not establish shared ownership, control, or intent."
        ),
        evidence=evidence,
        coverage=_pair_coverage(subject, peer, funding.coverage),
        unknowns=unknowns,
        warnings=list(dict.fromkeys([*subject.warnings, *peer.warnings])),
    )


def _collapse(
    wallets: Sequence[str],
    relationships: Sequence[WalletRelationship],
    threshold: RelationshipConfidence,
    *,
    as_of: datetime,
    configuration_id: str,
    configuration_version: int,
    unknowns: Sequence[str],
) -> ContributingIndependentCount:
    unique = sorted(set(wallets))
    parent = {wallet: wallet for wallet in unique}

    def find(wallet: str) -> str:
        root = wallet
        while parent[root] != root:
            root = parent[root]
        while parent[wallet] != root:
            parent[wallet], wallet = root, parent[wallet]
        return root

    for relationship in relationships:
        if _CONFIDENCE_RANK[relationship.confidence] < _CONFIDENCE_RANK[threshold]:
            continue
        left, right = relationship.wallets
        if left not in parent or right not in parent:
            continue
        left_root, right_root = find(left), find(right)
        if left_root != right_root:
            parent[right_root] = left_root

    grouped: dict[str, list[str]] = {}
    for wallet in unique:
        grouped.setdefault(find(wallet), []).append(wallet)
    groups = [
        ContributingIndependentGroup(
            wallets=sorted(members),
            representative=sorted(members)[0],
            reason=(
                (
                    "These Wallets are connected by at least one recorded relationship at or above "
                    f"the configured {threshold} confidence threshold."
                )
                if len(members) > 1
                else (
                    "No recorded relationship reached the configured "
                    f"{threshold} confidence threshold."
                )
            ),
        )
        for members in sorted(grouped.values(), key=lambda members: members[0])
    ]
    evidence = [
        (
            f"{len(unique)} recorded Wallet(s) collapse to {len(groups)} Contributing-independent "
            f"Wallet(s) at or above the {threshold} confidence threshold."
        )
    ]
    evidence.extend(
        "Collapsed group: " + ", ".join(group.wallets)
        for group in groups
        if len(group.wallets) > 1
    )
    if not unique:
        evidence = ["No Wallets were supplied for the Contributing-independent calculation."]
    return ContributingIndependentCount(
        raw_wallet_count=len(unique),
        contributing_independent_wallet_count=len(groups),
        groups=groups,
        as_of=as_of,
        configuration_id=configuration_id,
        configuration_version=configuration_version,
        confidence_threshold=threshold,
        evidence=evidence,
        unknowns=list(dict.fromkeys(unknowns)),
    )


class WalletRelationshipService:
    """Derive related Wallets and collapse them into a Contributing-independent count."""

    def __init__(
        self,
        accounting_store: WalletAccountingStore,
        funding_source: Optional[WalletFundingSource],
        configuration_store: ResearchConfigurationStore,
        relationship_store: WalletRelationshipStore,
    ) -> None:
        self._accounting_store = accounting_store
        self._funding_source = funding_source
        self._configuration_store = configuration_store
        self._relationship_store = relationship_store

    async def relationships(self, address: str, as_of: datetime) -> WalletRelationships:
        configuration = await self._configuration_store.get_active()
        return await self._relationships(address, as_of, configuration)

    async def analyze(self, address: str, as_of: datetime) -> WalletRelationshipAnalysisResult:
        configuration = await self._configuration_store.get_active()
        analysis = await self._relationships(address, as_of, configuration)
        return await self._relationship_store.record(analysis)

    async def latest(self, address: str, as_of: datetime) -> Optional[WalletRelationships]:
        return await self._relationship_store.latest(address, as_of)

    async def contributing_independent(
        self, wallets: Sequence[str], as_of: datetime
    ) -> ContributingIndependentCount:
        configuration = await self._configuration_store.get_active()
        accountings, skipped, _ = await self._load(wallets, as_of)
        funding = await self._funding(list(wallets), as_of)
        relationships = self._pairwise(list(accountings.values()), funding, configuration, as_of)
        return _collapse(
            list(accountings),
            relationships,
            configuration.configuration.cluster.relationship_confidence_threshold,
            as_of=as_of,
            configuration_id=str(configuration.id),
            configuration_version=configuration.version,
            unknowns=_unknowns(funding, skipped),
        )

    async def _relationships(
        self,
        address: str,
        as_of: datetime,
        configuration: VersionedResearchConfiguration,
    ) -> WalletRelationships:
        settings = configuration.configuration.cluster
        subject_accountings, _, subject_warnings = await self._load([address], as_of)
        if address not in subject_accountings:
            raise KeyError(address)
        subject = subject_accountings[address]
        peers = [
            wallet
            for wallet in await self._accounting_store.list_wallets()
            if wallet != address
        ]
        peer_accountings, skipped, peer_warnings = await self._load(peers, as_of)
        considered = {address: subject, **peer_accountings}
        funding = await self._funding(list(considered), as_of)
        relationships = [
            relationship
            for relationship in self._pairwise(
                list(considered.values()), funding, configuration, as_of
            )
            if address in relationship.wallets
        ]
        unknowns = _unknowns(funding, skipped)
        neighbourhood = [address] + [
            wallet
            for relationship in relationships
            for wallet in relationship.wallets
            if wallet != address
        ]
        return WalletRelationships(
            address=address,
            as_of=as_of,
            configuration_id=str(configuration.id),
            configuration_version=configuration.version,
            relationships=relationships,
            contributing_independent=_collapse(
                neighbourhood,
                relationships,
                settings.relationship_confidence_threshold,
                as_of=as_of,
                configuration_id=str(configuration.id),
                configuration_version=configuration.version,
                unknowns=unknowns,
            ),
            coverage=_overall_coverage(list(considered.values()), funding.coverage),
            unknowns=unknowns,
            warnings=list(
                dict.fromkeys(
                    [
                        *subject_warnings,
                        *peer_warnings,
                        *funding.coverage.warnings,
                    ]
                )
            ),
        )

    def _pairwise(
        self,
        accountings: Sequence[WalletAccounting],
        funding: WalletFundingResult,
        configuration: VersionedResearchConfiguration,
        as_of: datetime,
    ) -> list[WalletRelationship]:
        settings = configuration.configuration.cluster
        ordered = sorted(accountings, key=lambda accounting: accounting.address)
        relationships: list[WalletRelationship] = []
        for index, subject in enumerate(ordered):
            for peer in ordered[index + 1 :]:
                relationship = _relationship(subject, peer, funding, settings, as_of)
                if relationship is not None:
                    relationships.append(relationship)
        return relationships

    async def _load(
        self, wallets: Sequence[str], as_of: datetime
    ) -> tuple[dict[str, WalletAccounting], list[str], list[str]]:
        accountings: dict[str, WalletAccounting] = {}
        skipped: list[str] = []
        warnings: list[str] = []
        for wallet in sorted(set(wallets)):
            try:
                accounting = await self._accounting_store.accounting(wallet, as_of)
            except KeyError:
                skipped.append(wallet)
                continue
            accountings[wallet] = accounting
            warnings.extend(accounting.warnings)
        return accountings, skipped, list(dict.fromkeys(warnings))

    async def _funding(self, addresses: Sequence[str], as_of: datetime) -> WalletFundingResult:
        if self._funding_source is None:
            return WalletFundingResult(
                funding=[],
                coverage=WalletFundingCoverage(
                    provider="UNCONFIGURED_WALLET_FUNDING",
                    requested_as_of=as_of,
                    as_of_start=as_of,
                    as_of_end=as_of,
                    complete=False,
                    unknown_fields=["funder_address"],
                    warnings=[
                        "No recorded Wallet funding source is configured, so common funding is "
                        "UNKNOWN."
                    ],
                ),
            )
        return await self._funding_source.funding(addresses, as_of)


def _unknowns(funding: WalletFundingResult, skipped: Sequence[str]) -> list[str]:
    unknowns: list[str] = []
    if not funding.coverage.complete:
        unknowns.append(
            "COMMON_FUNDING: recorded funding evidence is unavailable, so common funding is "
            "UNKNOWN."
        )
    unknowns.extend(
        f"{wallet} has no recorded Wallet history at the requested as-of time."
        for wallet in skipped
    )
    return list(dict.fromkeys(unknowns))


class InMemoryWalletRelationshipStore:
    """Deterministic relationship-analysis store used by HTTP tests."""

    def __init__(
        self, *, now: Callable[[], datetime] = lambda: datetime.now(timezone.utc)
    ) -> None:
        self._now = now
        self._versions: dict[str, list[WalletRelationshipAnalysisResult]] = {}

    async def record(self, analysis: WalletRelationships) -> WalletRelationshipAnalysisResult:
        versions = self._versions.setdefault(analysis.address, [])
        if versions and versions[-1].analysis == analysis:
            return versions[-1].model_copy(update={"created": False})
        version = WalletRelationshipAnalysisResult(
            created=True,
            version=len(versions) + 1,
            created_at=self._now(),
            analysis=analysis,
        )
        versions.append(version)
        return version

    async def latest(self, address: str, as_of: datetime) -> Optional[WalletRelationships]:
        eligible = [
            version
            for version in self._versions.get(address, [])
            if version.analysis.as_of <= as_of
        ]
        if not eligible:
            return None
        return max(eligible, key=lambda version: version.version).analysis


class PostgresWalletRelationshipStore:
    """PostgreSQL source of truth for recorded relationship analyses."""

    def __init__(self, engine: AsyncEngine) -> None:
        self._engine = engine

    async def record(self, analysis: WalletRelationships) -> WalletRelationshipAnalysisResult:
        async with self._engine.begin() as connection:
            await connection.execute(
                text("SELECT pg_advisory_xact_lock(hashtext(:address))"),
                {"address": analysis.address},
            )
            latest = await connection.execute(
                text(
                    """
                    SELECT version, created_at, analysis
                    FROM wallet_relationship_analyses
                    WHERE wallet_address = :wallet_address
                    ORDER BY version DESC
                    LIMIT 1
                    """
                ),
                {"wallet_address": analysis.address},
            )
            row = latest.mappings().one_or_none()
            if row is not None and self._analysis_from_row(row) == analysis:
                return WalletRelationshipAnalysisResult(
                    created=False,
                    version=int(row["version"]),
                    created_at=row["created_at"],
                    analysis=analysis,
                )
            next_version = await connection.scalar(
                text(
                    """
                    SELECT COALESCE(MAX(version), 0) + 1
                    FROM wallet_relationship_analyses
                    WHERE wallet_address = :wallet_address
                    """
                ),
                {"wallet_address": analysis.address},
            )
            inserted = await connection.execute(
                text(
                    """
                    INSERT INTO wallet_relationship_analyses (
                        wallet_address, version, as_of, configuration_id,
                        configuration_version, analysis
                    ) VALUES (
                        :wallet_address, :version, :as_of, CAST(:configuration_id AS UUID),
                        :configuration_version, CAST(:analysis AS JSONB)
                    )
                    RETURNING version, created_at
                    """
                ),
                {
                    "wallet_address": analysis.address,
                    "version": int(next_version or 1),
                    "as_of": analysis.as_of,
                    "configuration_id": analysis.configuration_id,
                    "configuration_version": analysis.configuration_version,
                    "analysis": _json_document(analysis),
                },
            )
            inserted_row = inserted.mappings().one()
            return WalletRelationshipAnalysisResult(
                created=True,
                version=int(inserted_row["version"]),
                created_at=inserted_row["created_at"],
                analysis=analysis,
            )

    async def latest(self, address: str, as_of: datetime) -> Optional[WalletRelationships]:
        async with self._engine.connect() as connection:
            result = await connection.execute(
                text(
                    """
                    SELECT version, created_at, analysis
                    FROM wallet_relationship_analyses
                    WHERE wallet_address = :wallet_address AND as_of <= :as_of
                    ORDER BY as_of DESC, version DESC
                    LIMIT 1
                    """
                ),
                {"wallet_address": address, "as_of": as_of},
            )
            row = result.mappings().one_or_none()
        return None if row is None else self._analysis_from_row(row)

    @staticmethod
    def _analysis_from_row(row: RowMapping) -> WalletRelationships:
        return WalletRelationships.model_validate(_json_value(row["analysis"]))
