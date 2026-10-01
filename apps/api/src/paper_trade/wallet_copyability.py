"""Deterministic Wallet Copyability calculations over recorded pool evidence."""

from collections import defaultdict, deque
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Literal, Optional, Protocol

from pydantic import Field, model_validator

from paper_trade.launch_events import _is_solana_public_key
from paper_trade.market_state import MarketStateStore
from paper_trade.research_configuration import (
    ExecutionSettings,
    ResearchConfigurationStore,
    WalletSettings,
)
from paper_trade.wallet_accounting import (
    WalletAccountingModel,
    WalletAccountingStore,
    WalletTrade,
)

PoolModel = Literal["CONSTANT_PRODUCT", "DLMM", "CONCENTRATED", "UNKNOWN"]


class CopyabilityPoolCoverage(WalletAccountingModel):
    """Declared coverage for recorded market-pool snapshots."""

    provider: Literal["RECORDED_MARKET_POOL", "STORED_MARKET_STATE"]
    requested_as_of: datetime
    as_of_start: datetime
    as_of_end: datetime
    complete: bool
    freshness_seconds: int = Field(ge=0)
    unknown_fields: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_interval(self) -> "CopyabilityPoolCoverage":
        if self.as_of_end < self.as_of_start:
            raise ValueError("as_of_end must not be earlier than as_of_start")
        if not self.complete and not (self.unknown_fields or self.warnings):
            raise ValueError("incomplete coverage must declare unknown_fields or warnings")
        return self


class RecordedMarketPool(WalletAccountingModel):
    """One point-in-time pool snapshot with an explicit execution model."""

    token_address: str
    pool_address: str
    venue: str = Field(min_length=1)
    pool_model: PoolModel
    observed_at: datetime
    price_usd: float = Field(gt=0)
    sol_usd_price: float = Field(gt=0)
    liquidity_usd: Optional[float] = Field(default=None, ge=0)
    sol_reserve: Optional[float] = Field(default=None, gt=0)
    token_reserve: Optional[float] = Field(default=None, gt=0)
    evidence: list[str] = Field(min_length=1)

    @model_validator(mode="after")
    def validate_reserves(self) -> "RecordedMarketPool":
        if not _is_solana_public_key(self.token_address):
            raise ValueError("token_address must be a valid Solana public key")
        if not _is_solana_public_key(self.pool_address):
            raise ValueError("pool_address must be a valid Solana public key")
        if (self.sol_reserve is None) != (self.token_reserve is None):
            raise ValueError("sol_reserve and token_reserve must be supplied together")
        return self


class CopyabilityMarketPoolResult(WalletAccountingModel):
    pools: list[RecordedMarketPool]
    coverage: CopyabilityPoolCoverage


class CopyabilityMarketPoolSource(Protocol):
    """Recorded point-in-time pool evidence available to Copyability calculations."""

    async def market_pools(
        self, token_addresses: Sequence[str], as_of: datetime
    ) -> CopyabilityMarketPoolResult:
        """Return deterministic recorded snapshots, never provider I/O."""


class RecordedCopyabilityMarketPoolSource:
    """Fixture-only pool source for deterministic calculation and HTTP tests."""

    def __init__(
        self, pools: Sequence[RecordedMarketPool], coverage: CopyabilityPoolCoverage
    ) -> None:
        self._pools = [RecordedMarketPool.model_validate(pool.model_dump()) for pool in pools]
        self._coverage = CopyabilityPoolCoverage.model_validate(coverage.model_dump())

    async def market_pools(
        self, token_addresses: Sequence[str], as_of: datetime
    ) -> CopyabilityMarketPoolResult:
        requested = set(token_addresses)
        return CopyabilityMarketPoolResult(
            pools=sorted(
                [
                    pool
                    for pool in self._pools
                    if pool.token_address in requested and pool.observed_at <= as_of
                ],
                key=lambda pool: (pool.token_address, pool.observed_at, pool.pool_address),
            ),
            coverage=self._coverage.model_copy(update={"requested_as_of": as_of}),
        )


class StoredCopyabilityMarketPoolSource:
    """Adapts persisted market snapshots without blending provider observations."""

    def __init__(self, store: MarketStateStore) -> None:
        self._store = store

    async def market_pools(
        self, token_addresses: Sequence[str], as_of: datetime
    ) -> CopyabilityMarketPoolResult:
        observations = []
        for address in sorted(token_addresses):
            observations.extend(await self._store.observations(address, as_of))
        pools = [
            RecordedMarketPool(
                token_address=observation.address,
                pool_address=pool.address,
                venue=pool.venue,
                pool_model=pool.pool_model,
                observed_at=observation.observed_at,
                price_usd=observation.price_usd,
                sol_usd_price=pool.sol_usd_price,
                liquidity_usd=observation.liquidity_usd,
                sol_reserve=pool.sol_reserve,
                token_reserve=pool.token_reserve,
                evidence=[f"stored {observation.coverage.provider} {observation.observation_id}"],
            )
            for observation in observations
            if observation.price_usd is not None
            for pool in observation.pools
            if pool.sol_usd_price is not None
        ]
        coverages = [observation.coverage for observation in observations]
        unknown_fields = sorted(
            {field for coverage in coverages for field in coverage.unknown_fields}
            | ({"market_pool_state"} if not pools else set())
            | (
                {"pool_reserves"}
                if pools and not any(pool.sol_reserve for pool in pools)
                else set()
            )
            | (
                {"pool_model"}
                if pools and any(pool.pool_model == "UNKNOWN" for pool in pools)
                else set()
            )
        )
        return CopyabilityMarketPoolResult(
            pools=pools,
            coverage=CopyabilityPoolCoverage(
                provider="STORED_MARKET_STATE",
                requested_as_of=as_of,
                as_of_start=min((coverage.as_of_start for coverage in coverages), default=as_of),
                as_of_end=max((coverage.as_of_end for coverage in coverages), default=as_of),
                complete=(
                    bool(coverages)
                    and all(coverage.complete for coverage in coverages)
                    and bool(pools)
                    and all(pool.pool_model != "UNKNOWN" for pool in pools)
                ),
                freshness_seconds=min(
                    (coverage.freshness_seconds for coverage in coverages), default=0
                ),
                unknown_fields=unknown_fields,
                warnings=[warning for coverage in coverages for warning in coverage.warnings]
                or (["No recorded pool state is available."] if not pools else []),
            ),
        )


class CopyabilityPoolSelection(WalletAccountingModel):
    """Selected delayed snapshot, including why a state is unavailable."""

    side: Literal["BUY", "SELL"]
    requested_at: datetime
    pool_address: Optional[str] = None
    venue: Optional[str] = None
    pool_model: Optional[PoolModel] = None
    snapshot_at: Optional[datetime] = None
    source_evidence: list[str] = Field(default_factory=list)
    status: Literal["SELECTED", "UNKNOWN", "STALE"]
    warning: Optional[str] = None


class CopyabilityScenarioCoverage(WalletAccountingModel):
    """Coverage of one token and follower delay/size scenario."""

    token_address: str
    entry_requested_at: datetime
    exit_requested_at: datetime
    complete: bool
    unknown_fields: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)


class CopyabilityFill(WalletAccountingModel):
    side: Literal["BUY", "SELL"]
    requested_at: datetime
    filled_at: datetime
    model: Literal["CONSTANT_PRODUCT", "FIXED_SLIPPAGE"]
    confidence: Literal["HIGH", "LOW"]
    price_usd: float = Field(gt=0)
    quantity: float = Field(gt=0)
    sol_amount: float = Field(gt=0)
    liquidity_usd: Optional[float] = Field(default=None, ge=0)
    price_impact_percent: Optional[float] = Field(default=None, ge=0)
    slippage_percent: float = Field(ge=0)
    venue_fee_sol: float = Field(ge=0)
    network_and_priority_fee_sol: float = Field(ge=0)
    pool_address: Optional[str] = None
    venue: Optional[str] = None
    snapshot_at: Optional[datetime] = None
    source_evidence: list[str] = Field(default_factory=list)
    fallback_assumptions: list[str] = Field(default_factory=list)


class CopyabilityOutcome(WalletAccountingModel):
    token_address: str
    leader_entry_signature: str
    leader_exit_signature: str
    follower_delay_ms: int = Field(gt=0)
    follower_size_sol: float = Field(gt=0)
    leader_roi_percent: float
    follower_roi_percent: Optional[float]
    copy_decay_percent: Optional[float]
    status: Literal["FILLED", "REJECTED"]
    entry_fill: Optional[CopyabilityFill] = None
    exit_fill: Optional[CopyabilityFill] = None
    pool_selections: list[CopyabilityPoolSelection] = Field(default_factory=list)
    coverage: CopyabilityScenarioCoverage
    warnings: list[str] = Field(default_factory=list)


class WalletCopyability(WalletAccountingModel):
    address: str
    as_of: datetime
    configuration_version: Optional[int] = None
    delays_ms: list[int]
    follower_sizes_sol: list[float]
    outcomes: list[CopyabilityOutcome]
    coverage: CopyabilityPoolCoverage
    warnings: list[str]


class WalletCopyabilityStore(Protocol):
    async def copyability(self, address: str, as_of: datetime) -> WalletCopyability:
        """Return point-in-time leader/follower outcome simulations."""


@dataclass
class _LeaderClose:
    token_address: str
    entry: WalletTrade
    exit: WalletTrade
    quantity: float
    cost_usd: float
    proceeds_usd: float


@dataclass
class _Lot:
    trade: WalletTrade
    quantity: float


class WalletCopyabilityService:
    """Compare clean FIFO leader closes against configured follower executions."""

    def __init__(
        self,
        accounting_store: WalletAccountingStore,
        market_pool_source: CopyabilityMarketPoolSource,
        configuration_store: Optional[ResearchConfigurationStore] = None,
    ) -> None:
        self._accounting_store = accounting_store
        self._market_pool_source = market_pool_source
        self._configuration_store = configuration_store

    async def copyability(self, address: str, as_of: datetime) -> WalletCopyability:
        wallet_settings = WalletSettings()
        execution_settings = ExecutionSettings()
        configuration_version: Optional[int] = None
        if self._configuration_store is not None:
            configuration = await self._configuration_store.get_active()
            wallet_settings = configuration.configuration.wallet
            execution_settings = configuration.configuration.execution
            configuration_version = configuration.version
        accounting = await self._accounting_store.accounting(address, as_of)
        closes = self._closes(accounting.trades)
        pool_result = await self._market_pool_source.market_pools(
            sorted({close.token_address for close in closes}), as_of
        )
        warnings = list(dict.fromkeys(accounting.warnings + pool_result.coverage.warnings))
        if not pool_result.coverage.complete:
            warnings.append("Recorded market-pool coverage is incomplete.")
        outcomes = [
            self._outcome(close, delay, size, pool_result, execution_settings)
            for close in closes
            for delay in wallet_settings.copyability_delays_ms
            for size in wallet_settings.copyability_sizes_sol
        ]
        return WalletCopyability(
            address=address,
            as_of=as_of,
            configuration_version=configuration_version,
            delays_ms=wallet_settings.copyability_delays_ms,
            follower_sizes_sol=wallet_settings.copyability_sizes_sol,
            outcomes=outcomes,
            coverage=pool_result.coverage,
            warnings=list(dict.fromkeys(warnings)),
        )

    @staticmethod
    def _closes(trades: Sequence[WalletTrade]) -> list[_LeaderClose]:
        lots: dict[str, deque[_Lot]] = defaultdict(deque)
        closes: list[_LeaderClose] = []
        for trade in sorted(trades, key=lambda item: (item.chain_time, item.slot, item.trade_id)):
            if not trade.succeeded:
                continue
            if trade.movement_type == "BUY":
                lots[trade.token_address].append(_Lot(trade, trade.quantity))
            elif trade.movement_type == "SELL":
                assert trade.notional_usd is not None
                remaining = trade.quantity
                while remaining > 0 and lots[trade.token_address]:
                    lot = lots[trade.token_address][0]
                    used = min(remaining, lot.quantity)
                    lot.quantity -= used
                    remaining -= used
                    assert lot.trade.notional_usd is not None
                    cost = (lot.trade.notional_usd + lot.trade.fee_usd) * used / lot.trade.quantity
                    proceeds = (trade.notional_usd - trade.fee_usd) * used / trade.quantity
                    closes.append(
                        _LeaderClose(trade.token_address, lot.trade, trade, used, cost, proceeds)
                    )
                    if lot.quantity <= 0:
                        lots[trade.token_address].popleft()
        return closes

    def _outcome(
        self,
        close: _LeaderClose,
        delay_ms: int,
        size_sol: float,
        pool_result: CopyabilityMarketPoolResult,
        execution: ExecutionSettings,
    ) -> CopyabilityOutcome:
        entry_requested = close.entry.chain_time + timedelta(milliseconds=delay_ms)
        exit_requested = close.exit.chain_time + timedelta(milliseconds=delay_ms)
        leader_roi = (close.proceeds_usd - close.cost_usd) / close.cost_usd * 100
        pools = [pool for pool in pool_result.pools if pool.token_address == close.token_address]
        entry, entry_selection = self._select_pool(
            pools, close.entry.venue, entry_requested, "BUY", pool_result.coverage
        )
        exit, exit_selection = self._select_pool(
            pools,
            close.exit.venue,
            exit_requested,
            "SELL",
            pool_result.coverage,
        )
        coverage = self._scenario_coverage(
            close.token_address,
            entry_requested,
            exit_requested,
            entry_selection,
            exit_selection,
            pool_result.coverage,
        )
        selections = [entry_selection, exit_selection]
        if entry is not None and entry.sol_reserve is None:
            coverage = self._coverage_with_unknowns(coverage, "entry_pool_reserves")
        if exit is not None and exit.sol_reserve is None:
            coverage = self._coverage_with_unknowns(coverage, "exit_pool_reserves")
        if entry is not None and entry.pool_model == "UNKNOWN":
            coverage = self._coverage_with_unknowns(coverage, "entry_pool_model")
        if exit is not None and exit.pool_model == "UNKNOWN":
            coverage = self._coverage_with_unknowns(coverage, "exit_pool_model")
        if entry is None or exit is None:
            return self._rejected(
                close,
                delay_ms,
                size_sol,
                leader_roi,
                coverage,
                selections,
                "Market pool state is UNKNOWN or stale at the delayed follower entry or exit.",
            )
        if entry.pool_model == "CONSTANT_PRODUCT" and exit.pool_model == "CONSTANT_PRODUCT":
            if entry.sol_reserve is not None and exit.sol_reserve is not None:
                return self._constant_product_outcome(
                    close,
                    delay_ms,
                    size_sol,
                    leader_roi,
                    entry_requested,
                    exit_requested,
                    entry,
                    exit,
                    execution,
                    coverage,
                    selections,
                )
        return self._fallback_outcome(
            close,
            delay_ms,
            size_sol,
            leader_roi,
            entry_requested,
            exit_requested,
            entry,
            exit,
            execution,
            coverage,
            selections,
        )

    @staticmethod
    def _select_pool(
        pools: Sequence[RecordedMarketPool],
        leader_venue: Optional[str],
        requested_at: datetime,
        side: Literal["BUY", "SELL"],
        coverage: CopyabilityPoolCoverage,
    ) -> tuple[Optional[RecordedMarketPool], CopyabilityPoolSelection]:
        if leader_venue is None:
            return None, CopyabilityPoolSelection(
                side=side,
                requested_at=requested_at,
                status="UNKNOWN",
                warning="Leader venue is UNKNOWN; no follower pool can be selected.",
            )
        pool = next(
            (
                item
                for item in pools
                if item.venue == leader_venue and item.observed_at >= requested_at
            ),
            None,
        )
        if pool is None:
            return None, CopyabilityPoolSelection(
                side=side,
                requested_at=requested_at,
                venue=leader_venue,
                status="UNKNOWN",
                warning=f"No {leader_venue} pool snapshot exists after the delayed request.",
            )
        selection = CopyabilityPoolSelection(
            side=side,
            requested_at=requested_at,
            pool_address=pool.pool_address,
            venue=pool.venue,
            pool_model=pool.pool_model,
            snapshot_at=pool.observed_at,
            source_evidence=pool.evidence,
            status="SELECTED",
        )
        age = (pool.observed_at - requested_at).total_seconds()
        if (
            age > coverage.freshness_seconds
            or pool.observed_at < coverage.as_of_start
            or pool.observed_at > coverage.as_of_end
        ):
            return None, selection.model_copy(
                update={
                    "status": "STALE",
                    "warning": (
                        f"Selected {pool.venue} snapshot is stale for the delayed request "
                        f"({age:g}s; limit {coverage.freshness_seconds}s)."
                    ),
                }
            )
        return pool, selection

    @staticmethod
    def _scenario_coverage(
        token_address: str,
        entry_requested: datetime,
        exit_requested: datetime,
        entry: CopyabilityPoolSelection,
        exit: CopyabilityPoolSelection,
        coverage: CopyabilityPoolCoverage,
    ) -> CopyabilityScenarioCoverage:
        unknown_fields = set(coverage.unknown_fields)
        warnings = list(coverage.warnings)
        for name, selection in (("entry", entry), ("exit", exit)):
            if selection.status == "UNKNOWN":
                unknown_fields.add(f"{name}_pool_snapshot")
            elif selection.status == "STALE":
                unknown_fields.add(f"{name}_pool_snapshot_stale")
            if selection.warning:
                warnings.append(selection.warning)
        return CopyabilityScenarioCoverage(
            token_address=token_address,
            entry_requested_at=entry_requested,
            exit_requested_at=exit_requested,
            complete=coverage.complete and not unknown_fields,
            unknown_fields=sorted(unknown_fields),
            warnings=list(dict.fromkeys(warnings)),
        )

    @staticmethod
    def _coverage_with_unknowns(
        coverage: CopyabilityScenarioCoverage, *unknown_fields: str
    ) -> CopyabilityScenarioCoverage:
        return coverage.model_copy(
            update={
                "complete": False,
                "unknown_fields": sorted(set(coverage.unknown_fields) | set(unknown_fields)),
            }
        )

    @staticmethod
    def _rejected(
        close: _LeaderClose,
        delay_ms: int,
        size_sol: float,
        leader_roi: float,
        coverage: CopyabilityScenarioCoverage,
        selections: list[CopyabilityPoolSelection],
        warning: str,
    ) -> CopyabilityOutcome:
        return CopyabilityOutcome(
            token_address=close.token_address,
            leader_entry_signature=close.entry.signature,
            leader_exit_signature=close.exit.signature,
            follower_delay_ms=delay_ms,
            follower_size_sol=size_sol,
            leader_roi_percent=round(leader_roi, 10),
            follower_roi_percent=None,
            copy_decay_percent=None,
            status="REJECTED",
            pool_selections=selections,
            coverage=coverage,
            warnings=[warning],
        )

    @staticmethod
    def _constant_product_outcome(
        close: _LeaderClose,
        delay_ms: int,
        size_sol: float,
        leader_roi: float,
        entry_requested: datetime,
        exit_requested: datetime,
        entry: RecordedMarketPool,
        exit: RecordedMarketPool,
        execution: ExecutionSettings,
        coverage: CopyabilityScenarioCoverage,
        selections: list[CopyabilityPoolSelection],
    ) -> CopyabilityOutcome:
        assert entry.sol_reserve is not None and entry.token_reserve is not None
        assert exit.sol_reserve is not None and exit.token_reserve is not None
        fixed_fees = execution.network_fee_sol + execution.priority_fee_sol
        maximum_entry_input = entry.sol_reserve * execution.maximum_pool_participation_percent / 100
        if size_sol <= fixed_fees:
            return WalletCopyabilityService._rejected(
                close,
                delay_ms,
                size_sol,
                leader_roi,
                coverage,
                selections,
                "Follower size cannot cover configured network and priority fees.",
            )
        if size_sol > maximum_entry_input:
            return WalletCopyabilityService._rejected(
                close,
                delay_ms,
                size_sol,
                leader_roi,
                coverage,
                selections,
                "Follower entry exceeds the "
                f"{execution.maximum_pool_participation_percent:g}% pool participation limit.",
            )
        entry_input = size_sol - fixed_fees
        entry_after_fee = entry_input * (1 - execution.venue_fee_percent / 100)
        quantity = entry.token_reserve * entry_after_fee / (entry.sol_reserve + entry_after_fee)
        maximum_exit_input = exit.token_reserve * execution.maximum_pool_participation_percent / 100
        if quantity > maximum_exit_input:
            return WalletCopyabilityService._rejected(
                close,
                delay_ms,
                size_sol,
                leader_roi,
                coverage,
                selections,
                "Follower exit exceeds the "
                f"{execution.maximum_pool_participation_percent:g}% pool participation limit.",
            )
        entry_price_sol = entry_input / quantity
        entry_impact = (entry_price_sol / (entry.sol_reserve / entry.token_reserve) - 1) * 100
        exit_after_fee = quantity * (1 - execution.venue_fee_percent / 100)
        gross_exit_sol = exit.sol_reserve * exit_after_fee / (exit.token_reserve + exit_after_fee)
        received_sol = gross_exit_sol - fixed_fees
        if received_sol <= 0:
            return WalletCopyabilityService._rejected(
                close,
                delay_ms,
                size_sol,
                leader_roi,
                coverage,
                selections,
                "Follower exit cannot cover configured network and priority fees.",
            )
        exit_price_sol = received_sol / quantity
        exit_impact = (1 - exit_price_sol / (exit.sol_reserve / exit.token_reserve)) * 100
        follower_roi = (received_sol - size_sol) / size_sol * 100
        confidence: Literal["HIGH", "LOW"] = "HIGH" if coverage.complete else "LOW"
        return CopyabilityOutcome(
            token_address=close.token_address,
            leader_entry_signature=close.entry.signature,
            leader_exit_signature=close.exit.signature,
            follower_delay_ms=delay_ms,
            follower_size_sol=size_sol,
            leader_roi_percent=round(leader_roi, 10),
            follower_roi_percent=round(follower_roi, 10),
            copy_decay_percent=round(leader_roi - follower_roi, 10),
            status="FILLED",
            pool_selections=selections,
            coverage=coverage,
            entry_fill=CopyabilityFill(
                side="BUY",
                requested_at=entry_requested,
                filled_at=entry.observed_at,
                snapshot_at=entry.observed_at,
                model="CONSTANT_PRODUCT",
                confidence=confidence,
                price_usd=entry_price_sol * entry.sol_usd_price,
                quantity=quantity,
                sol_amount=size_sol,
                liquidity_usd=entry.liquidity_usd,
                price_impact_percent=entry_impact,
                slippage_percent=entry_impact,
                venue_fee_sol=entry_input - entry_after_fee,
                network_and_priority_fee_sol=fixed_fees,
                pool_address=entry.pool_address,
                venue=entry.venue,
                source_evidence=entry.evidence,
            ),
            exit_fill=CopyabilityFill(
                side="SELL",
                requested_at=exit_requested,
                filled_at=exit.observed_at,
                snapshot_at=exit.observed_at,
                model="CONSTANT_PRODUCT",
                confidence=confidence,
                price_usd=exit_price_sol * exit.sol_usd_price,
                quantity=quantity,
                sol_amount=received_sol,
                liquidity_usd=exit.liquidity_usd,
                price_impact_percent=exit_impact,
                slippage_percent=exit_impact,
                venue_fee_sol=quantity - exit_after_fee,
                network_and_priority_fee_sol=fixed_fees,
                pool_address=exit.pool_address,
                venue=exit.venue,
                source_evidence=exit.evidence,
            ),
            warnings=[] if coverage.complete else ["Recorded market-pool coverage is incomplete."],
        )

    @staticmethod
    def _fallback_outcome(
        close: _LeaderClose,
        delay_ms: int,
        size_sol: float,
        leader_roi: float,
        entry_requested: datetime,
        exit_requested: datetime,
        entry: RecordedMarketPool,
        exit: RecordedMarketPool,
        execution: ExecutionSettings,
        coverage: CopyabilityScenarioCoverage,
        selections: list[CopyabilityPoolSelection],
    ) -> CopyabilityOutcome:
        fixed_fees = execution.network_fee_sol + execution.priority_fee_sol
        if size_sol <= fixed_fees:
            return WalletCopyabilityService._rejected(
                close,
                delay_ms,
                size_sol,
                leader_roi,
                coverage,
                selections,
                "Follower size cannot cover configured network and priority fees.",
            )
        if entry.liquidity_usd is None or exit.liquidity_usd is None:
            coverage = WalletCopyabilityService._coverage_with_unknowns(
                coverage,
                *(
                    name
                    for name, pool in (("entry_liquidity", entry), ("exit_liquidity", exit))
                    if pool.liquidity_usd is None
                ),
            )
            return WalletCopyabilityService._rejected(
                close,
                delay_ms,
                size_sol,
                leader_roi,
                coverage,
                selections,
                "Fixed-slippage fallback sizing is unsupported without entry and exit liquidity.",
            )
        participation = execution.maximum_pool_participation_percent / 100
        entry_limit = entry.liquidity_usd / entry.sol_usd_price * participation
        if size_sol > entry_limit:
            return WalletCopyabilityService._rejected(
                close,
                delay_ms,
                size_sol,
                leader_roi,
                coverage,
                selections,
                "Follower entry exceeds the "
                f"{execution.maximum_pool_participation_percent:g}% liquidity participation limit.",
            )
        slippage = execution.fallback_slippage_percent / 100
        entry_input = size_sol - fixed_fees
        entry_after_fee = entry_input * (1 - execution.venue_fee_percent / 100)
        quantity = entry_after_fee * entry.sol_usd_price / (entry.price_usd * (1 + slippage))
        gross_exit = quantity * exit.price_usd * (1 - slippage) / exit.sol_usd_price
        exit_limit = exit.liquidity_usd / exit.sol_usd_price * participation
        if gross_exit > exit_limit:
            return WalletCopyabilityService._rejected(
                close,
                delay_ms,
                size_sol,
                leader_roi,
                coverage,
                selections,
                "Follower exit exceeds the "
                f"{execution.maximum_pool_participation_percent:g}% liquidity participation limit.",
            )
        exit_fee = gross_exit * execution.venue_fee_percent / 100
        received = gross_exit - exit_fee - fixed_fees
        if received <= 0:
            return WalletCopyabilityService._rejected(
                close,
                delay_ms,
                size_sol,
                leader_roi,
                coverage,
                selections,
                "Follower exit cannot cover configured network, priority, and venue fees.",
            )
        follower_roi = (received - size_sol) / size_sol * 100
        assumptions = [
            f"Fixed slippage of {execution.fallback_slippage_percent:g}% was applied.",
            f"Venue fee of {execution.venue_fee_percent:g}% was charged on entry and exit.",
            "Liquidity participation is limited using recorded USD liquidity.",
        ]
        unsupported_models = sorted(
            {pool.pool_model for pool in (entry, exit) if pool.pool_model != "CONSTANT_PRODUCT"}
        )
        warning = (
            "Pool reserves are UNKNOWN; fixed-slippage fallback was used."
            if not unsupported_models
            else (
                f"Unsupported pool model {', '.join(unsupported_models)}; "
                "fixed-slippage fallback was used."
            )
        )
        return CopyabilityOutcome(
            token_address=close.token_address,
            leader_entry_signature=close.entry.signature,
            leader_exit_signature=close.exit.signature,
            follower_delay_ms=delay_ms,
            follower_size_sol=size_sol,
            leader_roi_percent=round(leader_roi, 10),
            follower_roi_percent=round(follower_roi, 10),
            copy_decay_percent=round(leader_roi - follower_roi, 10),
            status="FILLED",
            pool_selections=selections,
            coverage=coverage,
            entry_fill=CopyabilityFill(
                side="BUY",
                requested_at=entry_requested,
                filled_at=entry.observed_at,
                snapshot_at=entry.observed_at,
                model="FIXED_SLIPPAGE",
                confidence="LOW",
                price_usd=entry.price_usd * (1 + slippage),
                quantity=quantity,
                sol_amount=size_sol,
                liquidity_usd=entry.liquidity_usd,
                slippage_percent=execution.fallback_slippage_percent,
                venue_fee_sol=entry_input - entry_after_fee,
                network_and_priority_fee_sol=fixed_fees,
                pool_address=entry.pool_address,
                venue=entry.venue,
                source_evidence=entry.evidence,
                fallback_assumptions=assumptions,
            ),
            exit_fill=CopyabilityFill(
                side="SELL",
                requested_at=exit_requested,
                filled_at=exit.observed_at,
                snapshot_at=exit.observed_at,
                model="FIXED_SLIPPAGE",
                confidence="LOW",
                price_usd=exit.price_usd * (1 - slippage),
                quantity=quantity,
                sol_amount=received,
                liquidity_usd=exit.liquidity_usd,
                slippage_percent=execution.fallback_slippage_percent,
                venue_fee_sol=exit_fee,
                network_and_priority_fee_sol=fixed_fees,
                pool_address=exit.pool_address,
                venue=exit.venue,
                source_evidence=exit.evidence,
                fallback_assumptions=assumptions,
            ),
            warnings=list(dict.fromkeys([warning, *coverage.warnings])),
        )
