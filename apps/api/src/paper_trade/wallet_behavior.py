"""Point-in-time Wallet behavior metrics derived from recorded accounting evidence.

The module only consumes the Wallet accounting seam and recorded market evidence.
It never calls a provider: missing market facts stay UNKNOWN rather than being
inferred from a later outcome.
"""

from collections import defaultdict, deque
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from statistics import median
from typing import Literal, Optional, Protocol

from pydantic import Field, model_validator

from paper_trade.market_state import MarketStateStore
from paper_trade.wallet_accounting import (
    WalletAccounting,
    WalletAccountingModel,
    WalletAccountingStore,
    WalletHistoryCoverage,
    WalletTrade,
)

BehaviorPeriod = Literal["24H", "7D", "30D", "90D", "ALL_TIME"]
BehaviorClassificationName = Literal["EARLY_BUYER", "SCALPER", "MULTI_TOKEN_TRADER"]
BehaviorFlagName = Literal[
    "INCOMPLETE_HISTORY_COVERAGE",
    "TRANSFER_DERIVED_INVENTORY",
    "UNCLASSIFIED_ACTIVITY",
    "RAPID_TOKEN_ENTRY",
]


class WalletMarketEvidence(WalletAccountingModel):
    """Recorded point-in-time market facts used only for behavior description."""

    token_address: str
    observed_at: datetime
    token_created_at: Optional[datetime] = None
    entry_market_cap_usd: Optional[float] = Field(default=None, ge=0)
    entry_liquidity_usd: Optional[float] = Field(default=None, ge=0)
    rugged: Optional[bool] = None
    dead: Optional[bool] = None
    migration_succeeded: Optional[bool] = None
    evidence: list[str] = Field(min_length=1)


class MarketEvidenceCoverage(WalletAccountingModel):
    """Coverage declaration for the fixture-only market-evidence Adapter."""

    provider: Literal["RECORDED_MARKET_EVIDENCE"]
    requested_as_of: datetime
    as_of_start: datetime
    as_of_end: datetime
    complete: bool
    unknown_fields: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_interval(self) -> "MarketEvidenceCoverage":
        if self.as_of_end < self.as_of_start:
            raise ValueError("as_of_end must not be earlier than as_of_start")
        if not self.complete and not (self.unknown_fields or self.warnings):
            raise ValueError("incomplete coverage must declare unknown_fields or warnings")
        return self


class WalletMarketEvidenceResult(WalletAccountingModel):
    evidence: list[WalletMarketEvidence]
    coverage: MarketEvidenceCoverage


class MarketEvidenceSource(Protocol):
    """Public Adapter contract for recorded, point-in-time market evidence."""

    async def market_evidence(
        self, token_addresses: Sequence[str], as_of: datetime
    ) -> WalletMarketEvidenceResult:
        """Return only evidence observed no later than the requested as-of time."""


class StoredMarketEvidenceSource:
    """Adapt persisted point-in-time Token market observations into behavior evidence."""

    def __init__(self, store: MarketStateStore) -> None:
        self._store = store

    async def market_evidence(
        self, token_addresses: Sequence[str], as_of: datetime
    ) -> WalletMarketEvidenceResult:
        evidence: list[WalletMarketEvidence] = []
        coverage_warnings: list[str] = []
        for address in sorted(token_addresses):
            observations = await self._store.observations(address, as_of)
            if not observations:
                coverage_warnings.append(
                    f"{address} has no stored market observation at the requested as-of time"
                )
                continue
            for observation in observations:
                evidence.append(
                    WalletMarketEvidence(
                        token_address=address,
                        observed_at=observation.observed_at,
                        entry_market_cap_usd=observation.market_cap_usd,
                        entry_liquidity_usd=observation.liquidity_usd,
                        evidence=[
                            f"stored {observation.coverage.provider} observation "
                            f"{observation.observation_id}"
                        ],
                    )
                )
        return WalletMarketEvidenceResult(
            evidence=evidence,
            coverage=MarketEvidenceCoverage(
                provider="RECORDED_MARKET_EVIDENCE",
                requested_as_of=as_of,
                as_of_start=as_of,
                as_of_end=as_of,
                complete=False,
                unknown_fields=[
                    "token_created_at",
                    "rugged",
                    "dead",
                    "migration_succeeded",
                ],
                warnings=coverage_warnings
                or ["Stored market observations omit behavioral lifecycle evidence."],
            ),
        )


class RecordedMarketEvidenceSource:
    """Fixture-only market-evidence Adapter; it performs no network calls."""

    def __init__(
        self, evidence: Sequence[WalletMarketEvidence], coverage: MarketEvidenceCoverage
    ) -> None:
        self._evidence = [
            WalletMarketEvidence.model_validate(item.model_dump()) for item in evidence
        ]
        self._coverage = MarketEvidenceCoverage.model_validate(coverage.model_dump())

    async def market_evidence(
        self, token_addresses: Sequence[str], as_of: datetime
    ) -> WalletMarketEvidenceResult:
        requested = set(token_addresses)
        selected = [
            item
            for item in self._evidence
            if item.token_address in requested and item.observed_at <= as_of
        ]
        return WalletMarketEvidenceResult(
            evidence=sorted(selected, key=lambda item: (item.token_address, item.observed_at)),
            coverage=self._coverage.model_copy(update={"requested_as_of": as_of}),
        )


class Distribution(WalletAccountingModel):
    count: int
    average: Optional[float]
    median: Optional[float]
    minimum: Optional[float]
    maximum: Optional[float]


class ProfitConcentration(WalletAccountingModel):
    top_one_percent: Optional[float]
    top_three_percent: Optional[float]
    top_five_percent: Optional[float]


class ConsistencyMetrics(WalletAccountingModel):
    profit_concentration: ProfitConcentration
    profitable_days: int
    profitable_weeks: int
    profitable_months: int


class MemeMetrics(WalletAccountingModel):
    """Token-specific metrics; null means the recorded evidence cannot establish it."""

    entry_count: int
    early_entry_rate_percent: Optional[float]
    creation_to_entry_latency_seconds: Distribution
    entry_market_cap_usd: Distribution
    entry_liquidity_usd: Distribution
    sub_100k_entry_rate_percent: Optional[float]
    sub_500k_entry_rate_percent: Optional[float]
    rug_exposure_rate_percent: Optional[float]
    dead_token_exposure_rate_percent: Optional[float]
    migration_success_rate_percent: Optional[float]
    token_activity_per_active_day: Optional[float]


class WalletBehaviorWindow(WalletAccountingModel):
    period: BehaviorPeriod
    starts_at: Optional[datetime]
    as_of: datetime
    definition: str
    realized_pnl_usd: float
    unrealized_pnl_usd: Optional[float]
    total_pnl_usd: Optional[float]
    roi_percent: Optional[float]
    win_rate_percent: Optional[float]
    trade_count: int
    winning_tokens: int
    losing_tokens: int
    average_win_usd: Optional[float]
    median_win_usd: Optional[float]
    average_loss_usd: Optional[float]
    median_loss_usd: Optional[float]
    profit_factor: Optional[float]
    max_drawdown_usd: float
    largest_win_usd: Optional[float]
    largest_loss_usd: Optional[float]
    position_size_usd: Distribution
    holding_time_seconds: Distribution
    consistency: ConsistencyMetrics
    meme: MemeMetrics
    unknowns: list[str] = Field(default_factory=list)


class WalletBehaviorClassification(WalletAccountingModel):
    name: BehaviorClassificationName
    description: str
    evidence: list[str] = Field(min_length=1)
    score_effect: Literal["NONE"] = "NONE"


class BehaviorFlagCoverage(WalletAccountingModel):
    source: str
    complete: bool
    unknown_fields: list[str] = Field(default_factory=list)


class WalletBehaviorFlag(WalletAccountingModel):
    name: BehaviorFlagName
    wording: str
    evidence: list[str] = Field(min_length=1)
    confidence: Literal["LOW", "MEDIUM", "HIGH"]
    coverage: list[BehaviorFlagCoverage] = Field(min_length=1)


class WalletBehavior(WalletAccountingModel):
    """Public calculation contract for a Wallet's evidence-backed behavior."""

    address: str
    as_of: datetime
    metric_definitions: list[str]
    windows: list[WalletBehaviorWindow]
    classifications: list[WalletBehaviorClassification]
    flags: list[WalletBehaviorFlag]
    coverage: list[BehaviorFlagCoverage]
    warnings: list[str]


class WalletBehaviorStore(Protocol):
    """HTTP persistence seam for a Wallet behavior detail lookup."""

    async def behavior(self, address: str, as_of: datetime) -> WalletBehavior:
        """Return the requested Wallet's deterministic point-in-time behavior."""


@dataclass
class _Lot:
    token_address: str
    acquired_at: datetime
    quantity: float
    unit_cost_usd: float
    contaminated: bool


@dataclass
class _Close:
    token_address: str
    closed_at: datetime
    acquired_at: datetime
    quantity: float
    pnl_usd: float
    cost_usd: float


def _round(value: float) -> float:
    return round(value, 10)


def _distribution(values: Sequence[float]) -> Distribution:
    if not values:
        return Distribution(count=0, average=None, median=None, minimum=None, maximum=None)
    return Distribution(
        count=len(values),
        average=_round(sum(values) / len(values)),
        median=_round(float(median(values))),
        minimum=_round(min(values)),
        maximum=_round(max(values)),
    )


def _window_start(period: BehaviorPeriod, as_of: datetime) -> Optional[datetime]:
    durations = {
        "24H": timedelta(hours=24),
        "7D": timedelta(days=7),
        "30D": timedelta(days=30),
        "90D": timedelta(days=90),
    }
    duration = durations.get(period)
    return as_of - duration if duration else None


class WalletBehaviorService:
    """Calculate clean, point-in-time Wallet behavior without assigning a score."""

    def __init__(
        self, accounting_store: WalletAccountingStore, market_evidence_source: MarketEvidenceSource
    ) -> None:
        self._accounting_store = accounting_store
        self._market_evidence_source = market_evidence_source

    async def behavior(self, address: str, as_of: datetime) -> WalletBehavior:
        accounting = await self._accounting_store.accounting(address, as_of)
        token_addresses = sorted(
            {trade.token_address for trade in accounting.trades if trade.succeeded}
        )
        market = await self._market_evidence_source.market_evidence(token_addresses, as_of)
        closes, open_lots, position_sizes, entries = self._reconstruct(accounting)
        evidence_by_token = self._entry_evidence(market.evidence, entries)
        coverage = self._coverage(accounting.coverage, market.coverage)
        windows = [
            self._window(
                period,
                as_of,
                closes,
                open_lots,
                position_sizes,
                entries,
                accounting,
                evidence_by_token,
            )
            for period in ("24H", "7D", "30D", "90D", "ALL_TIME")
        ]
        warnings = list(dict.fromkeys(accounting.warnings + market.coverage.warnings))
        return WalletBehavior(
            address=address,
            as_of=as_of,
            metric_definitions=[
                "Windows include realized clean PnL on exits in the period and clean open-lot PnL for lots entered in the period, marked at the requested as-of time.",
                "ROI is clean PnL divided by the clean cost basis of included exits and open lots; it is UNKNOWN when no included cost basis exists.",
                "Win rate, profit factor, drawdown, concentration, and profitable periods use realized clean FIFO exits only.",
                "Early entry means a recorded buy within one hour of a recorded token creation time. Classifications are descriptive and have no score effect.",
            ],
            windows=windows,
            classifications=self._classifications(windows[-1]),
            flags=self._flags(accounting, market.coverage, evidence_by_token, entries, coverage),
            coverage=coverage,
            warnings=warnings,
        )

    @staticmethod
    def _reconstruct(
        accounting: WalletAccounting,
    ) -> tuple[list[_Close], list[_Lot], list[tuple[datetime, float]], dict[str, datetime]]:
        lots: dict[str, deque[_Lot]] = defaultdict(deque)
        closes: list[_Close] = []
        position_sizes: list[tuple[datetime, float]] = []
        entries: dict[str, datetime] = {}
        activities = sorted(
            accounting.source_transactions,
            key=lambda item: (item.chain_time, item.slot, item.signature),
        )
        for activity in activities:
            trade_movements = [m for m in activity.movements if m.movement_type in ("BUY", "SELL")]
            allocated_fee = activity.fee_usd / len(trade_movements) if trade_movements else 0.0
            if not activity.succeeded:
                continue
            for movement in activity.movements:
                if movement.movement_type == "BUY":
                    assert movement.notional_usd is not None
                    unit_cost = (movement.notional_usd + allocated_fee) / movement.quantity
                    lots[movement.token_address].append(
                        _Lot(
                            movement.token_address,
                            activity.chain_time,
                            movement.quantity,
                            unit_cost,
                            False,
                        )
                    )
                    position_sizes.append(
                        (activity.chain_time, movement.notional_usd + allocated_fee)
                    )
                    entries.setdefault(movement.token_address, activity.chain_time)
                elif movement.movement_type in ("TRANSFER_IN", "AIRDROP"):
                    lots[movement.token_address].append(
                        _Lot(
                            movement.token_address,
                            activity.chain_time,
                            movement.quantity,
                            0.0,
                            True,
                        )
                    )
                elif movement.movement_type in ("SELL", "TRANSFER_OUT"):
                    remaining = movement.quantity
                    proceeds_per_unit = 0.0
                    if movement.movement_type == "SELL":
                        assert movement.notional_usd is not None
                        proceeds_per_unit = (
                            movement.notional_usd - allocated_fee
                        ) / movement.quantity
                    while remaining > 0 and lots[movement.token_address]:
                        lot = lots[movement.token_address][0]
                        used = min(remaining, lot.quantity)
                        lot.quantity -= used
                        remaining -= used
                        if movement.movement_type == "SELL" and not lot.contaminated:
                            cost = lot.unit_cost_usd * used
                            closes.append(
                                _Close(
                                    lot.token_address,
                                    activity.chain_time,
                                    lot.acquired_at,
                                    used,
                                    proceeds_per_unit * used - cost,
                                    cost,
                                )
                            )
                        if lot.quantity <= 0:
                            lots[movement.token_address].popleft()
        return (
            closes,
            [lot for token_lots in lots.values() for lot in token_lots if not lot.contaminated],
            position_sizes,
            entries,
        )

    @staticmethod
    def _entry_evidence(
        evidence: Sequence[WalletMarketEvidence], entries: dict[str, datetime]
    ) -> dict[str, WalletMarketEvidence]:
        """Select market facts that existed at or before each Wallet's entry."""
        selected: dict[str, WalletMarketEvidence] = {}
        for item in evidence:
            entered_at = entries.get(item.token_address)
            if entered_at is None or item.observed_at > entered_at:
                continue
            current = selected.get(item.token_address)
            if current is None or item.observed_at > current.observed_at:
                selected[item.token_address] = item
        return selected

    @staticmethod
    def _coverage(
        accounting_coverage: Sequence[WalletHistoryCoverage],
        market_coverage: MarketEvidenceCoverage,
    ) -> list[BehaviorFlagCoverage]:
        return [
            *[
                BehaviorFlagCoverage(
                    source=item.provider,
                    complete=item.complete,
                    unknown_fields=item.unknown_fields,
                )
                for item in accounting_coverage
            ],
            BehaviorFlagCoverage(
                source=market_coverage.provider,
                complete=market_coverage.complete,
                unknown_fields=market_coverage.unknown_fields,
            ),
        ]

    def _window(
        self,
        period: BehaviorPeriod,
        as_of: datetime,
        closes: Sequence[_Close],
        open_lots: Sequence[_Lot],
        position_sizes: Sequence[tuple[datetime, float]],
        entries: dict[str, datetime],
        accounting: WalletAccounting,
        evidence_by_token: dict[str, WalletMarketEvidence],
    ) -> WalletBehaviorWindow:
        starts_at = _window_start(period, as_of)
        includes = lambda value: starts_at is None or value >= starts_at
        selected_closes = [close for close in closes if includes(close.closed_at)]
        selected_open_lots = [lot for lot in open_lots if includes(lot.acquired_at)]
        pnl_values = [close.pnl_usd for close in selected_closes]
        realized = sum(pnl_values)
        marks = {holding.token_address: holding.mark_price_usd for holding in accounting.holdings}
        unknowns: list[str] = []
        unrealized: Optional[float] = 0.0
        for lot in selected_open_lots:
            mark = marks.get(lot.token_address)
            if mark is None:
                unrealized = None
                unknowns.append(
                    f"{lot.token_address} mark price is UNKNOWN at the requested as-of time"
                )
                continue
            if unrealized is not None:
                unrealized += lot.quantity * (mark - lot.unit_cost_usd)
        total = realized + unrealized if unrealized is not None else None
        basis = sum(close.cost_usd for close in selected_closes) + sum(
            lot.quantity * lot.unit_cost_usd for lot in selected_open_lots
        )
        wins = [value for value in pnl_values if value > 0]
        losses = [value for value in pnl_values if value < 0]
        grouped: dict[str, float] = defaultdict(float)
        for close in selected_closes:
            grouped[close.token_address] += close.pnl_usd
        gross_profit = sum(wins)
        concentration = self._concentration(grouped)
        cumulative = 0.0
        peak = 0.0
        drawdown = 0.0
        for close in sorted(selected_closes, key=lambda item: item.closed_at):
            cumulative += close.pnl_usd
            peak = max(peak, cumulative)
            drawdown = max(drawdown, peak - cumulative)
        selected_entries = {
            token: entered_at for token, entered_at in entries.items() if includes(entered_at)
        }
        return WalletBehaviorWindow(
            period=period,
            starts_at=starts_at,
            as_of=as_of,
            definition="Clean FIFO metrics; only facts available at the requested as-of time are included.",
            realized_pnl_usd=_round(realized),
            unrealized_pnl_usd=_round(unrealized) if unrealized is not None else None,
            total_pnl_usd=_round(total) if total is not None else None,
            roi_percent=_round(total / basis * 100) if total is not None and basis > 0 else None,
            win_rate_percent=_round(len(wins) / (len(wins) + len(losses)) * 100)
            if wins or losses
            else None,
            trade_count=len(selected_closes),
            winning_tokens=sum(1 for value in grouped.values() if value > 0),
            losing_tokens=sum(1 for value in grouped.values() if value < 0),
            average_win_usd=_round(sum(wins) / len(wins)) if wins else None,
            median_win_usd=_round(float(median(wins))) if wins else None,
            average_loss_usd=_round(sum(losses) / len(losses)) if losses else None,
            median_loss_usd=_round(float(median(losses))) if losses else None,
            profit_factor=_round(gross_profit / abs(sum(losses))) if losses else None,
            max_drawdown_usd=_round(drawdown),
            largest_win_usd=_round(max(wins)) if wins else None,
            largest_loss_usd=_round(min(losses)) if losses else None,
            position_size_usd=_distribution(
                [size for entered_at, size in position_sizes if includes(entered_at)]
            ),
            holding_time_seconds=_distribution(
                [(close.closed_at - close.acquired_at).total_seconds() for close in selected_closes]
            ),
            consistency=ConsistencyMetrics(
                profit_concentration=concentration,
                profitable_days=self._profitable_periods(selected_closes, "day"),
                profitable_weeks=self._profitable_periods(selected_closes, "week"),
                profitable_months=self._profitable_periods(selected_closes, "month"),
            ),
            meme=self._meme(selected_entries, evidence_by_token),
            unknowns=unknowns,
        )

    @staticmethod
    def _concentration(grouped: dict[str, float]) -> ProfitConcentration:
        profits = sorted((value for value in grouped.values() if value > 0), reverse=True)
        total = sum(profits)

        def top(count: int) -> Optional[float]:
            return _round(sum(profits[:count]) / total * 100) if total > 0 else None

        return ProfitConcentration(
            top_one_percent=top(1), top_three_percent=top(3), top_five_percent=top(5)
        )

    @staticmethod
    def _profitable_periods(closes: Sequence[_Close], granularity: str) -> int:
        totals: dict[object, float] = defaultdict(float)
        for close in closes:
            timestamp = close.closed_at.astimezone(timezone.utc)
            if granularity == "day":
                key: object = timestamp.date()
            elif granularity == "week":
                year, week, _ = timestamp.isocalendar()
                key = (year, week)
            else:
                key = (timestamp.year, timestamp.month)
            totals[key] += close.pnl_usd
        return sum(1 for total in totals.values() if total > 0)

    @staticmethod
    def _meme(
        entries: dict[str, datetime], evidence_by_token: dict[str, WalletMarketEvidence]
    ) -> MemeMetrics:
        evidence = [
            (token, entered_at, evidence_by_token.get(token))
            for token, entered_at in entries.items()
        ]
        latencies = [
            (entered_at - item.token_created_at).total_seconds()
            for _, entered_at, item in evidence
            if item is not None
            and item.token_created_at is not None
            and entered_at >= item.token_created_at
        ]
        market_caps = [
            item.entry_market_cap_usd
            for _, _, item in evidence
            if item and item.entry_market_cap_usd is not None
        ]
        liquidity = [
            item.entry_liquidity_usd
            for _, _, item in evidence
            if item and item.entry_liquidity_usd is not None
        ]
        known_rug = [item.rugged for _, _, item in evidence if item and item.rugged is not None]
        known_dead = [item.dead for _, _, item in evidence if item and item.dead is not None]
        known_migration = [
            item.migration_succeeded
            for _, _, item in evidence
            if item and item.migration_succeeded is not None
        ]
        days = {entered_at.astimezone(timezone.utc).date() for entered_at in entries.values()}
        return MemeMetrics(
            entry_count=len(entries),
            early_entry_rate_percent=_round(
                sum(value <= 3600 for value in latencies) / len(latencies) * 100
            )
            if latencies
            else None,
            creation_to_entry_latency_seconds=_distribution(latencies),
            entry_market_cap_usd=_distribution(market_caps),
            entry_liquidity_usd=_distribution(liquidity),
            sub_100k_entry_rate_percent=_round(
                sum(value < 100_000 for value in market_caps) / len(market_caps) * 100
            )
            if market_caps
            else None,
            sub_500k_entry_rate_percent=_round(
                sum(value < 500_000 for value in market_caps) / len(market_caps) * 100
            )
            if market_caps
            else None,
            rug_exposure_rate_percent=_round(sum(known_rug) / len(known_rug) * 100)
            if known_rug
            else None,
            dead_token_exposure_rate_percent=_round(sum(known_dead) / len(known_dead) * 100)
            if known_dead
            else None,
            migration_success_rate_percent=_round(sum(known_migration) / len(known_migration) * 100)
            if known_migration
            else None,
            token_activity_per_active_day=_round(len(entries) / len(days)) if days else None,
        )

    @staticmethod
    def _classifications(all_time: WalletBehaviorWindow) -> list[WalletBehaviorClassification]:
        classifications: list[WalletBehaviorClassification] = []
        if (
            all_time.meme.early_entry_rate_percent is not None
            and all_time.meme.early_entry_rate_percent >= 50
        ):
            classifications.append(
                WalletBehaviorClassification(
                    name="EARLY_BUYER",
                    description="Describes recorded entries within one hour of token creation; it does not indicate quality or score the Wallet.",
                    evidence=[
                        f"{all_time.meme.early_entry_rate_percent:g}% of entries with recorded creation times were within one hour."
                    ],
                )
            )
        holding_median = all_time.holding_time_seconds.median
        if holding_median is not None and holding_median <= 3600:
            classifications.append(
                WalletBehaviorClassification(
                    name="SCALPER",
                    description="Describes a median recorded holding time of one hour or less; it does not indicate quality or score the Wallet.",
                    evidence=[f"Median recorded holding time was {holding_median:g} seconds."],
                )
            )
        if all_time.meme.entry_count >= 3:
            classifications.append(
                WalletBehaviorClassification(
                    name="MULTI_TOKEN_TRADER",
                    description="Describes activity across at least three Tokens; it does not indicate quality or score the Wallet.",
                    evidence=[f"Recorded entries cover {all_time.meme.entry_count} Tokens."],
                )
            )
        return classifications

    @staticmethod
    def _flags(
        accounting: WalletAccounting,
        market_coverage: MarketEvidenceCoverage,
        evidence_by_token: dict[str, WalletMarketEvidence],
        entries: dict[str, datetime],
        coverage: list[BehaviorFlagCoverage],
    ) -> list[WalletBehaviorFlag]:
        flags: list[WalletBehaviorFlag] = []
        incomplete = [item for item in coverage if not item.complete]
        if incomplete:
            flags.append(
                WalletBehaviorFlag(
                    name="INCOMPLETE_HISTORY_COVERAGE",
                    wording="Recorded coverage is incomplete, so this behavior summary may omit earlier activity; this is not a finding about the Wallet.",
                    evidence=[field for item in incomplete for field in item.unknown_fields]
                    or ["One or more recorded sources declared incomplete coverage."],
                    confidence="HIGH",
                    coverage=incomplete,
                )
            )
        if accounting.contamination:
            flags.append(
                WalletBehaviorFlag(
                    name="TRANSFER_DERIVED_INVENTORY",
                    wording="Transfer-derived inventory is present and is excluded from clean behavior metrics; it does not establish the source or intent of the transfer.",
                    evidence=[
                        f"{item.movement_type} {item.quantity:g} units in {item.source_signature}."
                        for item in accounting.contamination
                    ],
                    confidence="HIGH",
                    coverage=coverage,
                )
            )
        if accounting.unknown_movements:
            flags.append(
                WalletBehaviorFlag(
                    name="UNCLASSIFIED_ACTIVITY",
                    wording="Some recorded activity remains unclassified and is not treated as a trade; additional evidence would be needed to interpret it.",
                    evidence=[
                        f"{item.signature}: {item.evidence[0]}"
                        for item in accounting.unknown_movements
                    ],
                    confidence="HIGH",
                    coverage=coverage,
                )
            )
        rapid = [
            (token, entered_at, evidence_by_token[token])
            for token, entered_at in entries.items()
            if token in evidence_by_token
            and evidence_by_token[token].token_created_at is not None
            and 0 <= (entered_at - evidence_by_token[token].token_created_at).total_seconds() <= 60
        ]
        if rapid:
            flags.append(
                WalletBehaviorFlag(
                    name="RAPID_TOKEN_ENTRY",
                    wording="A recorded entry occurred within one minute of token creation; this timing can warrant review and does not identify intent, ownership, or wrongdoing.",
                    evidence=[
                        f"{token}: entry {int((entered_at - item.token_created_at).total_seconds())} seconds after recorded creation; {item.evidence[0]}"
                        for token, entered_at, item in rapid
                        if item.token_created_at is not None
                    ],
                    confidence="MEDIUM" if not market_coverage.complete else "HIGH",
                    coverage=coverage,
                )
            )
        return flags


class InMemoryWalletBehaviorStore:
    """Test/store adapter retaining no behavior result beyond its deterministic inputs."""

    def __init__(self, service: WalletBehaviorService) -> None:
        self._service = service

    async def behavior(self, address: str, as_of: datetime) -> WalletBehavior:
        return await self._service.behavior(address, as_of)
