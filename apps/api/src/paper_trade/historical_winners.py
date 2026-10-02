"""Recorded historical-winner discovery without entry-time lookahead.

A cohort snapshots its winner qualification from the immutable research
configuration before the recorded early-buyer Adapter is consulted.  Early
buyer evaluation only receives facts available at its chain-time as-of; winner
peaks, rug outcomes, and Wallet quality are deliberately outside that context.
"""

from collections.abc import Sequence
from datetime import datetime
from typing import Literal, Optional, Protocol

from pydantic import BaseModel, ConfigDict, Field, model_validator

from paper_trade.launch_events import _is_solana_public_key
from paper_trade.market_state import (
    MarketObservation,
    MarketProviderCoverage,
    MarketStateStore,
)
from paper_trade.research_configuration import VersionedResearchConfiguration
from paper_trade.tokens import TokenRecord, TokenStore
from paper_trade.wallet_accounting import WalletHistoryCoverage, WalletMovementType

UNKNOWN = "UNKNOWN"


class HistoricalWinnerModel(BaseModel):
    """Base public contract for recorded historical-winner discovery."""

    model_config = ConfigDict(extra="forbid")


class RecordedEarlyBuyerTransaction(HistoricalWinnerModel):
    """One normalized, recorded movement belonging to a potential early buyer."""

    wallet_address: str
    signature: str = Field(min_length=1)
    movement_index: int = Field(ge=0)
    slot: int = Field(ge=0)
    chain_time: datetime
    observed_at: datetime
    succeeded: bool
    token_address: str
    movement_type: WalletMovementType
    quantity: float = Field(gt=0)
    notional_usd: Optional[float] = Field(default=None, ge=0)
    venue: Optional[str] = None
    evidence: list[str] = Field(min_length=1)

    @model_validator(mode="after")
    def validate_addresses_and_trade_notional(self) -> "RecordedEarlyBuyerTransaction":
        if not _is_solana_public_key(self.wallet_address):
            raise ValueError("wallet_address must be a valid Solana public key")
        if not _is_solana_public_key(self.token_address):
            raise ValueError("token_address must be a valid Solana public key")
        return self


class TokenEarlyBuyerHistory(HistoricalWinnerModel):
    """Recorded Adapter result, including coverage rather than invented facts."""

    token_address: str
    transactions: list[RecordedEarlyBuyerTransaction]
    coverage: WalletHistoryCoverage

    @model_validator(mode="after")
    def validate_token_address(self) -> "TokenEarlyBuyerHistory":
        if not _is_solana_public_key(self.token_address):
            raise ValueError("token_address must be a valid Solana public key")
        if any(
            transaction.token_address != self.token_address for transaction in self.transactions
        ):
            raise ValueError("early-buyer transaction token_address must match the requested Token")
        return self


class EarlyBuyerSource(Protocol):
    """Public fixture-only Adapter contract for Token early-buyer history."""

    async def early_buyers(self, token_address: str, as_of: datetime) -> TokenEarlyBuyerHistory:
        """Return deterministic normalized movements at or before ``as_of``."""


class RecordedEarlyBuyerSource:
    """Canonical fixture Adapter.  It makes no network calls."""

    def __init__(
        self,
        pages: Sequence[Sequence[RecordedEarlyBuyerTransaction]],
        coverage: WalletHistoryCoverage,
    ) -> None:
        self._pages = [
            [
                RecordedEarlyBuyerTransaction.model_validate(transaction.model_dump())
                for transaction in page
            ]
            for page in pages
        ]
        self._coverage = WalletHistoryCoverage.model_validate(coverage.model_dump())

    async def early_buyers(self, token_address: str, as_of: datetime) -> TokenEarlyBuyerHistory:
        if not _is_solana_public_key(token_address):
            raise ValueError("token_address must be a valid Solana public key")
        unique: dict[tuple[str, str, int], RecordedEarlyBuyerTransaction] = {}
        for page in self._pages:
            for transaction in page:
                if transaction.token_address != token_address or transaction.chain_time > as_of:
                    continue
                key = (
                    transaction.wallet_address,
                    transaction.signature,
                    transaction.movement_index,
                )
                existing = unique.get(key)
                if existing is not None and existing != transaction:
                    raise ValueError("conflicting recorded early-buyer transaction")
                unique[key] = transaction
        return TokenEarlyBuyerHistory(
            token_address=token_address,
            transactions=sorted(
                unique.values(),
                key=lambda transaction: (
                    transaction.chain_time,
                    transaction.slot,
                    transaction.signature,
                    transaction.movement_index,
                    transaction.wallet_address,
                ),
            ),
            coverage=self._coverage.model_copy(update={"requested_as_of": as_of}),
        )


class HistoricalWinnerCohortRequest(HistoricalWinnerModel):
    """The fixed creation window and qualification cutoff for one cohort run."""

    cohort_id: str = Field(min_length=1)
    created_from: datetime
    created_to: datetime
    qualification_as_of: datetime

    @model_validator(mode="after")
    def validate_boundaries(self) -> "HistoricalWinnerCohortRequest":
        if self.created_to < self.created_from:
            raise ValueError("created_to must not be earlier than created_from")
        if self.qualification_as_of < self.created_to:
            raise ValueError("qualification_as_of must not be earlier than created_to")
        return self


class DiscoveryCriterion(HistoricalWinnerModel):
    criterion: str
    observed: str
    threshold: str
    passed: bool


class HistoricalWinner(HistoricalWinnerModel):
    """A qualification snapshot made before its buyers are read."""

    token_address: str
    token_symbol: str
    created_at: datetime
    initial_market_cap_usd: Optional[float] = Field(default=None, ge=0)
    initial_market_cap_observed_at: Optional[datetime] = None
    peak_market_cap_usd: Optional[float] = Field(default=None, ge=0)
    peak_market_cap_observed_at: Optional[datetime] = None
    qualified: bool
    qualifying_facts: list[DiscoveryCriterion]


UnavailableHistoricalFact = Literal[
    "future_peak_market_cap_usd", "future_rug_status", "future_wallet_quality"
]


def _unavailable_historical_facts() -> list[UnavailableHistoricalFact]:
    return [
        "future_peak_market_cap_usd",
        "future_rug_status",
        "future_wallet_quality",
    ]


class EntryEvaluationBoundary(HistoricalWinnerModel):
    """Facts intentionally unavailable when a historical entry is evaluated."""

    as_of: datetime
    unavailable_facts: list[UnavailableHistoricalFact] = Field(
        default_factory=_unavailable_historical_facts
    )


class EarlyBuyerRecord(HistoricalWinnerModel):
    wallet_address: str
    token_address: str
    chain_time: datetime
    amount_tokens: float
    amount_usd: Optional[float] = Field(default=None, ge=0)
    price_usd: Optional[float] = Field(default=None, gt=0)
    market_cap_usd: Optional[float] = Field(default=None, ge=0)
    liquidity_usd: Optional[float] = Field(default=None, ge=0)
    token_age_seconds: float = Field(ge=0)
    entry_market_cap_bucket: str
    venue: Optional[str] = None
    signature: str
    coverage: WalletHistoryCoverage
    market_coverage: Optional[MarketProviderCoverage] = None
    entry_evaluation: EntryEvaluationBoundary
    warnings: list[str] = Field(default_factory=list)


class CandidateWallet(HistoricalWinnerModel):
    wallet_address: str
    passed: bool
    evidence: list[DiscoveryCriterion]


class HistoricalWinnerDiscovery(HistoricalWinnerModel):
    cohort: HistoricalWinnerCohortRequest
    configuration_id: str
    configuration_version: int
    winners: list[HistoricalWinner]
    early_buyers: list[EarlyBuyerRecord]
    candidate_wallets: list[CandidateWallet]


class HistoricalWinnerDiscoveryStore(Protocol):
    async def save(self, discovery: HistoricalWinnerDiscovery) -> HistoricalWinnerDiscovery:
        """Persist an immutable cohort result, rejecting conflicting reruns."""

    async def latest(self) -> Optional[HistoricalWinnerDiscovery]:
        """Return the most recently saved cohort result."""


class InMemoryHistoricalWinnerDiscoveryStore:
    """Deterministic persistence boundary used by HTTP tests."""

    def __init__(self) -> None:
        self._discoveries: dict[str, HistoricalWinnerDiscovery] = {}
        self._order: list[str] = []

    async def save(self, discovery: HistoricalWinnerDiscovery) -> HistoricalWinnerDiscovery:
        existing = self._discoveries.get(discovery.cohort.cohort_id)
        if existing is not None:
            if existing != discovery:
                raise ValueError("historical winner cohort is immutable")
            return existing
        copy = HistoricalWinnerDiscovery.model_validate(discovery.model_dump())
        self._discoveries[copy.cohort.cohort_id] = copy
        self._order.append(copy.cohort.cohort_id)
        return copy

    async def latest(self) -> Optional[HistoricalWinnerDiscovery]:
        if not self._order:
            return None
        return self._discoveries[self._order[-1]]


class HistoricalWinnerDiscoveryService:
    """Qualify winners first, then evaluate only recorded entry-time facts."""

    def __init__(
        self,
        token_store: TokenStore,
        market_state_store: MarketStateStore,
        early_buyer_source: EarlyBuyerSource,
    ) -> None:
        self._token_store = token_store
        self._market_state_store = market_state_store
        self._early_buyer_source = early_buyer_source

    async def discover(
        self,
        cohort: HistoricalWinnerCohortRequest,
        configuration: VersionedResearchConfiguration,
    ) -> HistoricalWinnerDiscovery:
        # This loop deliberately completes the cohort before reading buyer history.
        winners = await self._qualify_winners(cohort, configuration)
        qualified_winners = [winner for winner in winners if winner.qualified]
        early_buyers: list[EarlyBuyerRecord] = []
        candidates: dict[str, list[DiscoveryCriterion]] = {}
        for winner in qualified_winners:
            history = await self._early_buyer_source.early_buyers(
                winner.token_address, cohort.qualification_as_of
            )
            token = await self._token_store.get(winner.token_address)
            if token is None:
                continue
            records, evidence = await self._evaluate_early_buyers(
                token, history, configuration, cohort.qualification_as_of
            )
            early_buyers.extend(records)
            for wallet_address, wallet_evidence in evidence.items():
                candidates.setdefault(wallet_address, []).extend(wallet_evidence)
        return HistoricalWinnerDiscovery(
            cohort=cohort,
            configuration_id=str(configuration.id),
            configuration_version=configuration.version,
            winners=winners,
            early_buyers=early_buyers,
            candidate_wallets=[
                CandidateWallet(
                    wallet_address=wallet_address,
                    passed=any(item.passed for item in evidence),
                    evidence=evidence,
                )
                for wallet_address, evidence in sorted(candidates.items())
            ],
        )

    async def _qualify_winners(
        self,
        cohort: HistoricalWinnerCohortRequest,
        configuration: VersionedResearchConfiguration,
    ) -> list[HistoricalWinner]:
        winners: list[HistoricalWinner] = []
        for token in await self._token_store.list():
            if not (cohort.created_from <= token.created_at <= cohort.created_to):
                continue
            observations = await self._market_state_store.observations(
                token.address, cohort.qualification_as_of
            )
            initial = _initial_market_cap(observations, token.created_at)
            peak = _peak_market_cap(observations)
            initial_value = initial.market_cap_usd if initial is not None else None
            peak_value = peak.market_cap_usd if peak is not None else None
            settings = configuration.configuration.token
            criteria = [
                DiscoveryCriterion(
                    criterion="initial_market_cap_usd",
                    observed=_display(initial_value),
                    threshold=(
                        f">= {settings.winner_initial_market_cap_min_usd:g} and "
                        f"<= {settings.winner_initial_market_cap_max_usd:g}"
                    ),
                    passed=(
                        initial_value is not None
                        and settings.winner_initial_market_cap_min_usd
                        <= initial_value
                        <= settings.winner_initial_market_cap_max_usd
                    ),
                ),
                DiscoveryCriterion(
                    criterion="peak_market_cap_usd",
                    observed=_display(peak_value),
                    threshold=f">= {settings.winner_peak_market_cap_min_usd:g}",
                    passed=(
                        peak_value is not None
                        and peak_value >= settings.winner_peak_market_cap_min_usd
                    ),
                ),
            ]
            winners.append(
                HistoricalWinner(
                    token_address=token.address,
                    token_symbol=token.symbol,
                    created_at=token.created_at,
                    initial_market_cap_usd=initial_value,
                    initial_market_cap_observed_at=initial.observed_at if initial else None,
                    peak_market_cap_usd=peak_value,
                    peak_market_cap_observed_at=peak.observed_at if peak else None,
                    qualified=all(criterion.passed for criterion in criteria),
                    qualifying_facts=criteria,
                )
            )
        return sorted(winners, key=lambda winner: (winner.created_at, winner.token_address))

    async def _evaluate_early_buyers(
        self,
        token: TokenRecord,
        history: TokenEarlyBuyerHistory,
        configuration: VersionedResearchConfiguration,
        qualification_as_of: datetime,
    ) -> tuple[list[EarlyBuyerRecord], dict[str, list[DiscoveryCriterion]]]:
        records: list[EarlyBuyerRecord] = []
        candidates: dict[str, list[DiscoveryCriterion]] = {}
        for transaction in history.transactions:
            is_buy = transaction.movement_type == "BUY" and transaction.succeeded
            candidates.setdefault(transaction.wallet_address, []).append(
                DiscoveryCriterion(
                    criterion="successful_buy",
                    observed=(
                        "BUY" if transaction.movement_type == "BUY" else transaction.movement_type
                    )
                    + (" succeeded" if transaction.succeeded else " failed"),
                    threshold="successful BUY",
                    passed=is_buy,
                )
            )
            if not is_buy:
                continue
            # The entry lookup cannot see observations after the chain-time of this buy.
            observations = await self._market_state_store.observations(
                token.address, transaction.chain_time
            )
            market = _latest_observation(observations)
            market_cap = market.market_cap_usd if market else None
            liquidity = market.liquidity_usd if market else None
            amount_usd = transaction.notional_usd
            price = amount_usd / transaction.quantity if amount_usd is not None else None
            warnings = list(history.coverage.warnings)
            if market is None:
                warnings.append("Market observation is UNKNOWN at the entry as-of time")
            else:
                warnings.extend(market.coverage.warnings)
                if not market.coverage.complete:
                    warnings.append(f"{market.coverage.provider} coverage is incomplete")
                warnings.extend(
                    f"{field} is UNKNOWN at the entry as-of time"
                    for field in market.coverage.unknown_fields
                )
            if price is None:
                warnings.append("price_usd is UNKNOWN at the entry as-of time")
            if market_cap is None:
                warnings.append("market_cap_usd is UNKNOWN at the entry as-of time")
            if liquidity is None:
                warnings.append("liquidity_usd is UNKNOWN at the entry as-of time")
            records.append(
                EarlyBuyerRecord(
                    wallet_address=transaction.wallet_address,
                    token_address=token.address,
                    chain_time=transaction.chain_time,
                    amount_tokens=transaction.quantity,
                    amount_usd=amount_usd,
                    price_usd=price,
                    market_cap_usd=market_cap,
                    liquidity_usd=liquidity,
                    token_age_seconds=(transaction.chain_time - token.created_at).total_seconds(),
                    entry_market_cap_bucket=_entry_bucket(
                        market_cap, configuration.configuration.token.entry_market_cap_buckets_usd
                    ),
                    venue=transaction.venue,
                    signature=transaction.signature,
                    coverage=history.coverage,
                    market_coverage=market.coverage if market else None,
                    entry_evaluation=EntryEvaluationBoundary(as_of=transaction.chain_time),
                    warnings=list(dict.fromkeys(warnings)),
                )
            )
        return records, candidates


def _initial_market_cap(
    observations: Sequence[MarketObservation], created_at: datetime
) -> Optional[MarketObservation]:
    candidates = [
        observation
        for observation in observations
        if observation.observed_at >= created_at and observation.market_cap_usd is not None
    ]
    return min(candidates, key=lambda observation: observation.observed_at) if candidates else None


def _peak_market_cap(observations: Sequence[MarketObservation]) -> Optional[MarketObservation]:
    candidates = [
        observation for observation in observations if observation.market_cap_usd is not None
    ]
    return (
        max(candidates, key=lambda observation: float(observation.market_cap_usd or 0))
        if candidates
        else None
    )


def _latest_observation(observations: Sequence[MarketObservation]) -> Optional[MarketObservation]:
    return (
        max(observations, key=lambda observation: observation.observed_at) if observations else None
    )


def _entry_bucket(market_cap_usd: Optional[float], buckets: Sequence[float]) -> str:
    if market_cap_usd is None:
        return UNKNOWN
    for ceiling in buckets:
        if market_cap_usd <= ceiling:
            return f"<= {ceiling:g}"
    return f"> {buckets[-1]:g}"


def _display(value: Optional[float]) -> str:
    return UNKNOWN if value is None else f"{value:g}"
