"""Recorded Wallet history normalization and point-in-time FIFO accounting.

This module intentionally has no provider I/O.  ``RecordedWalletHistorySource``
implements the public Wallet-history Adapter contract over canonical Helius
fixtures so reconstruction is deterministic and provider omissions remain
visible in the result.
"""

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime
from typing import Literal, Optional, Protocol

from pydantic import BaseModel, ConfigDict, Field, model_validator

from paper_trade.launch_events import _is_solana_public_key

WalletMovementType = Literal["BUY", "SELL", "TRANSFER_IN", "TRANSFER_OUT", "AIRDROP", "UNKNOWN"]


class WalletAccountingModel(BaseModel):
    """Base document for Wallet accounting public contracts."""

    model_config = ConfigDict(extra="forbid")


class WalletHistoryCoverage(WalletAccountingModel):
    """Coverage declared by the Wallet-history provider, including omissions."""

    provider: Literal["HELIUS"]
    requested_as_of: datetime
    as_of_start: datetime
    as_of_end: datetime
    complete: bool
    freshness_seconds: int = Field(ge=0)
    commitment: Literal["confirmed", "finalized"]
    unknown_fields: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_interval(self) -> "WalletHistoryCoverage":
        if self.as_of_end < self.as_of_start:
            raise ValueError("as_of_end must not be earlier than as_of_start")
        if not self.complete and not (self.unknown_fields or self.warnings):
            raise ValueError("incomplete coverage must declare unknown_fields or warnings")
        return self


class RecordedWalletMovement(WalletAccountingModel):
    """One provider-normalized SPL movement and its classification evidence."""

    token_address: str
    movement_type: WalletMovementType
    quantity: float = Field(gt=0)
    notional_usd: Optional[float] = Field(default=None, ge=0)
    venue: Optional[str] = None
    evidence: list[str] = Field(min_length=1)

    @model_validator(mode="after")
    def validate_trade_notional(self) -> "RecordedWalletMovement":
        if not _is_solana_public_key(self.token_address):
            raise ValueError("token_address must be a valid Solana public key")
        if self.movement_type in ("BUY", "SELL") and self.notional_usd is None:
            raise ValueError("BUY and SELL movements require notional_usd")
        if self.movement_type not in ("BUY", "SELL") and self.notional_usd is not None:
            raise ValueError("non-trade movements must not claim a notional_usd")
        return self


class WalletActivity(WalletAccountingModel):
    """A recorded Helius source transaction before it is applied to FIFO lots."""

    signature: str = Field(min_length=1)
    slot: int = Field(ge=0)
    chain_time: datetime
    observed_at: datetime
    succeeded: bool
    fee_usd: float = Field(ge=0)
    movements: list[RecordedWalletMovement] = Field(min_length=1)


class WalletHistory(WalletAccountingModel):
    """History returned from the public Adapter contract for a requested Wallet."""

    address: str
    activities: list[WalletActivity]
    coverage: WalletHistoryCoverage

    @model_validator(mode="after")
    def validate_address(self) -> "WalletHistory":
        if not _is_solana_public_key(self.address):
            raise ValueError("address must be a valid Solana public key")
        return self


class WalletHistorySource(Protocol):
    """Public Adapter contract for documented, recorded Wallet history."""

    async def wallet_history(self, address: str, as_of: datetime) -> WalletHistory:
        """Return source transactions at or before ``as_of`` in deterministic order."""


class RecordedWalletHistorySource:
    """Fixture-only Helius Adapter; it performs no network calls."""

    def __init__(
        self,
        pages: Sequence[Sequence[WalletActivity]],
        coverage: WalletHistoryCoverage,
    ) -> None:
        self._pages = [
            [WalletActivity.model_validate(activity.model_dump()) for activity in page]
            for page in pages
        ]
        self._coverage = WalletHistoryCoverage.model_validate(coverage.model_dump())

    async def wallet_history(self, address: str, as_of: datetime) -> WalletHistory:
        if not _is_solana_public_key(address):
            raise ValueError("address must be a valid Solana public key")
        unique: dict[str, WalletActivity] = {}
        for page in self._pages:
            for activity in page:
                if activity.chain_time > as_of:
                    continue
                existing = unique.get(activity.signature)
                if existing is not None and existing != activity:
                    raise ValueError("conflicting recorded Wallet activity")
                unique[activity.signature] = activity
        return WalletHistory(
            address=address,
            activities=sorted(
                unique.values(),
                key=lambda activity: (activity.chain_time, activity.slot, activity.signature),
            ),
            coverage=self._coverage.model_copy(update={"requested_as_of": as_of}),
        )


class WalletMarkPrice(WalletAccountingModel):
    """One recorded point-in-time mark, retained with provider provenance."""

    token_address: str
    price_usd: float = Field(gt=0)
    observed_at: datetime
    provider: Literal["DEXSCREENER", "GECKOTERMINAL", "JUPITER"]

    @model_validator(mode="after")
    def validate_address(self) -> "WalletMarkPrice":
        if not _is_solana_public_key(self.token_address):
            raise ValueError("token_address must be a valid Solana public key")
        return self


class WalletTrade(WalletAccountingModel):
    """An auditable normalized Wallet Trade derived from a source transaction."""

    trade_id: str
    signature: str
    slot: int
    chain_time: datetime
    observed_at: datetime
    token_address: str
    movement_type: WalletMovementType
    quantity: float
    notional_usd: Optional[float]
    fee_usd: float
    venue: Optional[str]
    succeeded: bool
    evidence: list[str]


class WalletLot(WalletAccountingModel):
    """A FIFO acquisition lot; zero basis denotes transfer-derived contamination."""

    lot_id: str
    token_address: str
    source_signature: str
    acquired_at: datetime
    initial_quantity: float
    remaining_quantity: float
    unit_cost_usd: float
    contaminated: bool
    contamination_reason: Optional[WalletMovementType] = None


class WalletHolding(WalletAccountingModel):
    token_address: str
    quantity: float
    contaminated_quantity: float
    clean_quantity: float
    cost_basis_usd: float
    mark_price_usd: Optional[float]


class WalletPnl(WalletAccountingModel):
    realized_usd: float
    unrealized_usd: Optional[float]
    total_usd: Optional[float]


class WalletPnlSummary(WalletAccountingModel):
    inclusive: WalletPnl
    clean: WalletPnl


class ContaminationEvidence(WalletAccountingModel):
    token_address: str
    source_signature: str
    quantity: float
    movement_type: Literal["TRANSFER_IN", "AIRDROP"]
    evidence: list[str]


class WalletAccounting(WalletAccountingModel):
    """Wallet detail/accounting response at one requested point in time."""

    address: str
    as_of: datetime
    source_transactions: list[WalletActivity]
    trades: list[WalletTrade]
    lots: list[WalletLot]
    holdings: list[WalletHolding]
    pnl: WalletPnlSummary
    contamination: list[ContaminationEvidence]
    failed_transactions: list[WalletActivity]
    unknown_movements: list[WalletTrade]
    coverage: list[WalletHistoryCoverage]
    mark_price_provenance: list[WalletMarkPrice]
    warnings: list[str]


class WalletAccountingStore(Protocol):
    """HTTP persistence seam for a Wallet accounting detail lookup."""

    async def accounting(self, address: str, as_of: datetime) -> WalletAccounting:
        """Return the requested Wallet's deterministic point-in-time accounting."""


@dataclass
class _LotBalance:
    lot: WalletLot


def _round(value: float) -> float:
    return round(value, 10)


class WalletAccountingService:
    """Reconstruct FIFO lots without turning transfers or unknowns into trades."""

    def __init__(
        self,
        history_source: WalletHistorySource,
        prices: Sequence[WalletMarkPrice],
    ) -> None:
        self._history_source = history_source
        self._prices = [WalletMarkPrice.model_validate(price.model_dump()) for price in prices]

    async def accounting(self, address: str, as_of: datetime) -> WalletAccounting:
        history = await self._history_source.wallet_history(address, as_of)
        lots: list[_LotBalance] = []
        trades: list[WalletTrade] = []
        contamination: list[ContaminationEvidence] = []
        unknown_movements: list[WalletTrade] = []
        warnings: list[str] = list(history.coverage.warnings)
        inclusive_realized = 0.0
        clean_realized = 0.0

        for activity in history.activities:
            trade_movements = [
                movement
                for movement in activity.movements
                if movement.movement_type in ("BUY", "SELL")
            ]
            allocated_fee = activity.fee_usd / len(trade_movements) if trade_movements else 0.0
            for index, movement in enumerate(activity.movements):
                trade = WalletTrade(
                    trade_id=f"{activity.signature}:{index}",
                    signature=activity.signature,
                    slot=activity.slot,
                    chain_time=activity.chain_time,
                    observed_at=activity.observed_at,
                    token_address=movement.token_address,
                    movement_type=movement.movement_type,
                    quantity=movement.quantity,
                    notional_usd=movement.notional_usd,
                    fee_usd=allocated_fee if movement in trade_movements else 0.0,
                    venue=movement.venue,
                    succeeded=activity.succeeded,
                    evidence=movement.evidence,
                )
                trades.append(trade)
                if not activity.succeeded:
                    continue
                if movement.movement_type == "BUY":
                    assert movement.notional_usd is not None
                    lots.append(
                        _LotBalance(
                            WalletLot(
                                lot_id=trade.trade_id,
                                token_address=movement.token_address,
                                source_signature=activity.signature,
                                acquired_at=activity.chain_time,
                                initial_quantity=movement.quantity,
                                remaining_quantity=movement.quantity,
                                unit_cost_usd=_round(
                                    (movement.notional_usd + allocated_fee) / movement.quantity
                                ),
                                contaminated=False,
                            )
                        )
                    )
                elif movement.movement_type in ("TRANSFER_IN", "AIRDROP"):
                    contamination_type: Literal["TRANSFER_IN", "AIRDROP"] = (
                        "TRANSFER_IN" if movement.movement_type == "TRANSFER_IN" else "AIRDROP"
                    )
                    lots.append(
                        _LotBalance(
                            WalletLot(
                                lot_id=trade.trade_id,
                                token_address=movement.token_address,
                                source_signature=activity.signature,
                                acquired_at=activity.chain_time,
                                initial_quantity=movement.quantity,
                                remaining_quantity=movement.quantity,
                                unit_cost_usd=0.0,
                                contaminated=True,
                                contamination_reason=contamination_type,
                            )
                        )
                    )
                    contamination.append(
                        ContaminationEvidence(
                            token_address=movement.token_address,
                            source_signature=activity.signature,
                            quantity=movement.quantity,
                            movement_type=contamination_type,
                            evidence=movement.evidence,
                        )
                    )
                elif movement.movement_type == "SELL":
                    assert movement.notional_usd is not None
                    consumed = self._consume(lots, movement.token_address, movement.quantity)
                    matched_quantity = sum(quantity for _, quantity in consumed)
                    if matched_quantity < movement.quantity:
                        warnings.append(
                            f"{activity.signature} sells {movement.quantity - matched_quantity:g} "
                            f"unmatched units of {movement.token_address}; no basis was inferred"
                        )
                    for balance, quantity in consumed:
                        proceeds = (
                            (movement.notional_usd - allocated_fee) * quantity / movement.quantity
                        )
                        pnl = proceeds - balance.lot.unit_cost_usd * quantity
                        inclusive_realized += pnl
                        if not balance.lot.contaminated:
                            clean_realized += pnl
                elif movement.movement_type == "TRANSFER_OUT":
                    unmatched = movement.quantity - sum(
                        quantity
                        for _, quantity in self._consume(
                            lots, movement.token_address, movement.quantity
                        )
                    )
                    if unmatched > 0:
                        warnings.append(
                            f"{activity.signature} transfers out {unmatched:g} unmatched units of "
                            f"{movement.token_address}; no basis was inferred"
                        )
                else:
                    unknown_movements.append(trade)

        active_lots = [balance.lot for balance in lots if balance.lot.remaining_quantity > 0]
        holdings, inclusive_unrealized, clean_unrealized, marks, mark_warnings = (
            self._mark_holdings(active_lots, as_of)
        )
        warnings.extend(mark_warnings)
        inclusive_unrealized_value = (
            _round(inclusive_unrealized) if inclusive_unrealized is not None else None
        )
        clean_unrealized_value = _round(clean_unrealized) if clean_unrealized is not None else None
        inclusive_realized = _round(inclusive_realized)
        clean_realized = _round(clean_realized)
        return WalletAccounting(
            address=address,
            as_of=as_of,
            source_transactions=history.activities,
            trades=trades,
            lots=[balance.lot for balance in lots],
            holdings=holdings,
            pnl=WalletPnlSummary(
                inclusive=WalletPnl(
                    realized_usd=inclusive_realized,
                    unrealized_usd=inclusive_unrealized_value,
                    total_usd=(
                        _round(inclusive_realized + inclusive_unrealized)
                        if inclusive_unrealized is not None
                        else None
                    ),
                ),
                clean=WalletPnl(
                    realized_usd=clean_realized,
                    unrealized_usd=clean_unrealized_value,
                    total_usd=(
                        _round(clean_realized + clean_unrealized)
                        if clean_unrealized is not None
                        else None
                    ),
                ),
            ),
            contamination=contamination,
            failed_transactions=[
                activity for activity in history.activities if not activity.succeeded
            ],
            unknown_movements=unknown_movements,
            coverage=[history.coverage],
            mark_price_provenance=marks,
            warnings=list(dict.fromkeys(warnings)),
        )

    @staticmethod
    def _consume(
        lots: list[_LotBalance], token_address: str, quantity: float
    ) -> list[tuple[_LotBalance, float]]:
        remaining = quantity
        consumed: list[tuple[_LotBalance, float]] = []
        for balance in lots:
            if balance.lot.token_address != token_address or remaining <= 0:
                continue
            available = balance.lot.remaining_quantity
            if available <= 0:
                continue
            used = min(available, remaining)
            balance.lot = balance.lot.model_copy(
                update={"remaining_quantity": _round(available - used)}
            )
            consumed.append((balance, used))
            remaining -= used
        return consumed

    def _mark_holdings(
        self, lots: Sequence[WalletLot], as_of: datetime
    ) -> tuple[
        list[WalletHolding], Optional[float], Optional[float], list[WalletMarkPrice], list[str]
    ]:
        token_addresses = sorted({lot.token_address for lot in lots})
        selected: dict[str, WalletMarkPrice] = {}
        for token_address in token_addresses:
            candidates = [
                price
                for price in self._prices
                if price.token_address == token_address and price.observed_at <= as_of
            ]
            if candidates:
                selected[token_address] = max(
                    candidates, key=lambda price: (price.observed_at, price.provider)
                )
        holdings: list[WalletHolding] = []
        inclusive_unrealized: Optional[float] = 0.0
        clean_unrealized: Optional[float] = 0.0
        warnings: list[str] = []
        for token_address in token_addresses:
            token_lots = [lot for lot in lots if lot.token_address == token_address]
            quantity = sum(lot.remaining_quantity for lot in token_lots)
            contaminated_quantity = sum(
                lot.remaining_quantity for lot in token_lots if lot.contaminated
            )
            clean_lots = [lot for lot in token_lots if not lot.contaminated]
            clean_quantity = sum(lot.remaining_quantity for lot in clean_lots)
            cost_basis = sum(lot.remaining_quantity * lot.unit_cost_usd for lot in token_lots)
            mark = selected.get(token_address)
            holdings.append(
                WalletHolding(
                    token_address=token_address,
                    quantity=_round(quantity),
                    contaminated_quantity=_round(contaminated_quantity),
                    clean_quantity=_round(clean_quantity),
                    cost_basis_usd=_round(cost_basis),
                    mark_price_usd=mark.price_usd if mark else None,
                )
            )
            if mark is None:
                inclusive_unrealized = None
                if clean_quantity > 0:
                    clean_unrealized = None
                warnings.append(
                    f"{token_address} mark price is UNKNOWN at the requested as-of time"
                )
                continue
            if inclusive_unrealized is not None:
                inclusive_unrealized += mark.price_usd * quantity - cost_basis
            if clean_unrealized is not None:
                clean_cost = sum(lot.remaining_quantity * lot.unit_cost_usd for lot in clean_lots)
                clean_unrealized += mark.price_usd * clean_quantity - clean_cost
        return (
            holdings,
            inclusive_unrealized,
            clean_unrealized,
            [selected[address] for address in sorted(selected)],
            warnings,
        )


class InMemoryWalletAccountingStore:
    """Deterministic Wallet-detail store used by HTTP and fixture tests."""

    def __init__(self, service: WalletAccountingService) -> None:
        self._service = service

    async def accounting(self, address: str, as_of: datetime) -> WalletAccounting:
        return await self._service.accounting(address, as_of)
