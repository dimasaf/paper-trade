"""Confirmed real-time Wallet tracking through a replaceable RealtimeSource.

Only Wallets currently in the ``SMART_WALLET`` Registry state are subscribed.
Activity is normalized into the same movement forms as historical Wallet
activity, and signature/slot idempotency keeps reconnects, webhook retries, and
replays from duplicating events.  ``processed`` commitment is recorded as
observed activity but can never trigger a downstream decision under ADR-0002.

The ``RealtimeSource`` port returns recorded subscription batches, so a future
RPC WebSocket or Geyser gRPC transport can replace the recorded fixture Adapter
without touching this module.  The tracker, not the source, enforces which
Wallets are subscribed, so a webhook-style source that over-delivers activity
cannot smuggle an untracked Wallet into the live feed.
"""

import json
from collections.abc import Callable, Sequence
from datetime import datetime, timezone
from typing import Any, Optional, Protocol
from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator
from sqlalchemy import text
from sqlalchemy.engine import RowMapping
from sqlalchemy.ext.asyncio import AsyncEngine

from paper_trade.launch_events import Commitment, _is_solana_public_key
from paper_trade.wallet_accounting import WalletMovementType

_TRADE_MOVEMENTS: tuple[WalletMovementType, ...] = ("BUY", "SELL")


class RealtimeModel(BaseModel):
    """Base document for realtime tracking public contracts."""

    model_config = ConfigDict(extra="forbid")


class RealtimeCoverage(RealtimeModel):
    """Coverage metadata retained with every recorded realtime observation."""

    provider: str = Field(min_length=1)
    as_of_start: datetime
    as_of_end: datetime
    complete: bool
    commitment: Commitment
    freshness_seconds: int = Field(ge=0)
    normalization_version: str = Field(min_length=1)
    unknown_fields: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_interval(self) -> "RealtimeCoverage":
        if self.as_of_end < self.as_of_start:
            raise ValueError("as_of_end must not be earlier than as_of_start")
        if not self.complete and not (self.unknown_fields or self.warnings):
            raise ValueError("incomplete coverage must declare unknown_fields or warnings")
        return self


class RealtimeActivity(RealtimeModel):
    """One recorded Wallet movement observed from a RealtimeSource subscription."""

    event_id: str = Field(min_length=1)
    wallet_address: str
    token_address: str
    movement_type: WalletMovementType
    quantity: float = Field(gt=0)
    notional_usd: Optional[float] = Field(default=None, ge=0)
    venue: Optional[str] = None
    signature: str = Field(min_length=1)
    slot: int = Field(ge=0)
    chain_time: datetime
    observed_at: datetime
    evidence: list[str] = Field(min_length=1)
    coverage: RealtimeCoverage

    @field_validator("wallet_address", "token_address")
    @classmethod
    def validate_solana_public_key(cls, value: str) -> str:
        if not _is_solana_public_key(value):
            raise ValueError("must be a valid Solana public key")
        return value

    @model_validator(mode="after")
    def validate_movement_valuation(self) -> "RealtimeActivity":
        if self.observed_at < self.chain_time:
            raise ValueError("observed_at must not be earlier than chain_time")
        if self.movement_type in _TRADE_MOVEMENTS:
            if self.notional_usd is None and "notional_usd" not in self.coverage.unknown_fields:
                raise ValueError(
                    "a BUY or SELL without a valuation must declare notional_usd unknown"
                )
        elif self.notional_usd is not None:
            raise ValueError("non-trade movements must not claim a notional_usd")
        for field in self.coverage.unknown_fields:
            if field == "notional_usd" and self.notional_usd is not None:
                raise ValueError("notional_usd is declared unknown but carries a valuation")
            if field != "notional_usd":
                raise ValueError(f"{field} is not a realtime activity field")
        return self


class RealtimeBatch(RealtimeModel):
    """One subscription batch; ``reconnected`` marks a re-established stream."""

    connection_id: str = Field(min_length=1)
    connected_at: datetime
    reconnected: bool
    activity: list[RealtimeActivity]


class SmartWalletSubscription(RealtimeModel):
    """One Wallet currently in the SMART_WALLET Registry state."""

    address: str
    score: Optional[float] = Field(default=None, ge=0, le=100)
    as_of: datetime

    @field_validator("address")
    @classmethod
    def validate_solana_public_key(cls, value: str) -> str:
        if not _is_solana_public_key(value):
            raise ValueError("must be a valid Solana public key")
        return value


class RealtimeSource(Protocol):
    """Replaceable Adapter contract for confirmed Wallet activity."""

    async def subscribe(self, wallets: Sequence[str]) -> Sequence[RealtimeBatch]:
        """Return recorded subscription batches for the requested Wallets.

        A recorded or webhook Adapter may return activity for Wallets beyond the
        requested set; the tracker enforces the subscription before it stores or
        publishes anything.
        """


class SmartWalletSource(Protocol):
    """Adapter contract for the Wallets currently accepted into ``SMART_WALLET``."""

    async def smart_wallets(self, as_of: datetime) -> list[SmartWalletSubscription]:
        """Return every Wallet currently in the SMART_WALLET Registry state."""


class RealtimeWalletEvent(RealtimeModel):
    """A normalized, idempotent Wallet event ready for the live feed."""

    idempotency_key: str = Field(min_length=1)
    event_id: str = Field(min_length=1)
    wallet_address: str
    token_address: str
    movement_type: WalletMovementType
    quantity: float
    notional_usd: Optional[float]
    price_usd: Optional[float]
    venue: Optional[str]
    signature: str
    slot: int
    chain_time: datetime
    observed_at: datetime
    received_at: datetime
    commitment: Commitment
    wallet_score: Optional[float]
    score_as_of: datetime
    eligible_for_decisions: bool
    evidence: list[str]
    coverage: RealtimeCoverage
    warnings: list[str]


class RecordRealtimeEventResult(RealtimeModel):
    """Observable idempotency outcome of one realtime event persistence."""

    created: bool
    event: RealtimeWalletEvent


class RealtimeTrackingRun(RealtimeModel):
    """One tracking poll with the counters that make it observable."""

    run_id: str = Field(min_length=1)
    as_of: datetime
    started_at: datetime
    completed_at: datetime
    subscribed_wallets: list[str]
    received: int = Field(ge=0)
    recorded: int = Field(ge=0)
    duplicates: int = Field(ge=0)
    processed_only: int = Field(ge=0)
    skipped_unsubscribed: int = Field(ge=0)
    reconnects: int = Field(ge=0)
    max_lag_seconds: Optional[float] = Field(default=None, ge=0)
    processing_latency_seconds: float = Field(ge=0)
    warnings: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_counters(self) -> "RealtimeTrackingRun":
        if self.received != self.recorded + self.duplicates + self.skipped_unsubscribed:
            raise ValueError(
                "received must equal recorded, duplicate, and skipped-unsubscribed activity"
            )
        if self.processed_only > self.recorded:
            raise ValueError("processed-only activity must not exceed recorded activity")
        if self.completed_at < self.started_at:
            raise ValueError("completed_at must not be earlier than started_at")
        return self


class RealtimeTrackingStatus(RealtimeModel):
    """Aggregate observability for reconnects, lag, duplicates, and throughput."""

    as_of: datetime
    subscribed_wallets: list[str]
    stored_events: int = Field(ge=0)
    decision_events: int = Field(ge=0)
    received: int = Field(default=0, ge=0)
    recorded: int = Field(default=0, ge=0)
    duplicates: int = Field(default=0, ge=0)
    processed_only: int = Field(default=0, ge=0)
    skipped_unsubscribed: int = Field(default=0, ge=0)
    reconnects: int = Field(default=0, ge=0)
    max_lag_seconds: Optional[float] = Field(default=None, ge=0)
    processing_latency_seconds: Optional[float] = Field(default=None, ge=0)
    last_run_at: Optional[datetime] = None
    warnings: list[str] = Field(default_factory=list)


class RealtimeTrackingStore(Protocol):
    """Durable persistence seam for normalized events and tracking runs."""

    async def record_event(self, event: RealtimeWalletEvent) -> RecordRealtimeEventResult:
        """Persist an event unless its signature/slot key is already recorded."""

    async def record_run(self, run: RealtimeTrackingRun) -> RealtimeTrackingRun:
        """Persist one observability run."""

    async def events(self) -> list[RealtimeWalletEvent]:
        """Return every normalized event in recorded order."""

    async def latest_run(self) -> Optional[RealtimeTrackingRun]:
        """Return the most recently started tracking run."""


class RecordedRealtimeSource:
    """Deterministic RealtimeSource over recorded batches; performs no network I/O."""

    def __init__(self, batches: Sequence[RealtimeBatch]) -> None:
        self._batches = [RealtimeBatch.model_validate(batch.model_dump()) for batch in batches]

    async def subscribe(self, wallets: Sequence[str]) -> Sequence[RealtimeBatch]:
        return sorted(self._batches, key=lambda batch: (batch.connected_at, batch.connection_id))


def _idempotency_key(activity: RealtimeActivity) -> str:
    return ":".join(
        (
            activity.signature,
            str(activity.slot),
            activity.wallet_address,
            activity.token_address,
            activity.movement_type,
        )
    )


def _conflicts(existing: RealtimeWalletEvent, event: RealtimeWalletEvent) -> bool:
    return (
        existing.wallet_address != event.wallet_address
        or existing.token_address != event.token_address
        or existing.movement_type != event.movement_type
        or existing.quantity != event.quantity
        or existing.notional_usd != event.notional_usd
    )


def _normalize(
    activity: RealtimeActivity,
    subscription: SmartWalletSubscription,
    received_at: datetime,
) -> RealtimeWalletEvent:
    price_usd: Optional[float] = None
    if activity.notional_usd is not None:
        price_usd = activity.notional_usd / activity.quantity
    eligible = activity.coverage.commitment == "confirmed"
    warnings = list(activity.coverage.warnings)
    if not eligible:
        warnings.append(
            "Processed commitment is recorded for observation only and cannot trigger a "
            "downstream decision."
        )
    return RealtimeWalletEvent(
        idempotency_key=_idempotency_key(activity),
        event_id=activity.event_id,
        wallet_address=activity.wallet_address,
        token_address=activity.token_address,
        movement_type=activity.movement_type,
        quantity=activity.quantity,
        notional_usd=activity.notional_usd,
        price_usd=price_usd,
        venue=activity.venue,
        signature=activity.signature,
        slot=activity.slot,
        chain_time=activity.chain_time,
        observed_at=activity.observed_at,
        received_at=received_at,
        commitment=activity.coverage.commitment,
        wallet_score=subscription.score,
        score_as_of=subscription.as_of,
        eligible_for_decisions=eligible,
        evidence=list(activity.evidence),
        coverage=activity.coverage,
        warnings=warnings,
    )


class RealtimeTrackingService:
    """Subscribe the SMART_WALLET Registry state and record confirmed activity."""

    def __init__(
        self,
        realtime_source: RealtimeSource,
        smart_wallet_source: SmartWalletSource,
        store: RealtimeTrackingStore,
        *,
        now: Callable[[], datetime] = lambda: datetime.now(timezone.utc),
        id_factory: Callable[[], UUID] = uuid4,
    ) -> None:
        self._realtime_source = realtime_source
        self._smart_wallet_source = smart_wallet_source
        self._store = store
        self._now = now
        self._id_factory = id_factory

    async def poll(self, as_of: datetime) -> RealtimeTrackingRun:
        started_at = self._now()
        subscriptions = await self._smart_wallet_source.smart_wallets(as_of)
        by_address = {subscription.address: subscription for subscription in subscriptions}
        batches = await self._realtime_source.subscribe(list(by_address))

        received = 0
        recorded = 0
        duplicates = 0
        processed_only = 0
        skipped = 0
        reconnects = 0
        lags: list[float] = []
        warnings: list[str] = []

        for batch in batches:
            if batch.reconnected:
                reconnects += 1
            for activity in batch.activity:
                received += 1
                lags.append((activity.observed_at - activity.chain_time).total_seconds())
                subscription = by_address.get(activity.wallet_address)
                if subscription is None:
                    skipped += 1
                    continue
                event = _normalize(activity, subscription, started_at)
                result = await self._store.record_event(event)
                warnings.extend(event.warnings)
                if result.created:
                    recorded += 1
                    if not event.eligible_for_decisions:
                        processed_only += 1
                else:
                    duplicates += 1

        completed_at = self._now()
        run = RealtimeTrackingRun(
            run_id=str(self._id_factory()),
            as_of=as_of,
            started_at=started_at,
            completed_at=completed_at,
            subscribed_wallets=sorted(by_address),
            received=received,
            recorded=recorded,
            duplicates=duplicates,
            processed_only=processed_only,
            skipped_unsubscribed=skipped,
            reconnects=reconnects,
            max_lag_seconds=max(lags) if lags else None,
            processing_latency_seconds=(completed_at - started_at).total_seconds(),
            warnings=list(dict.fromkeys(warnings)),
        )
        return await self._store.record_run(run)

    async def feed(self, limit: int) -> list[RealtimeWalletEvent]:
        events = await self._store.events()
        return list(reversed(events))[:limit]

    async def decision_events(self) -> list[RealtimeWalletEvent]:
        return [
            event for event in await self._store.events() if event.eligible_for_decisions
        ]

    async def status(self) -> RealtimeTrackingStatus:
        events = await self._store.events()
        run = await self._store.latest_run()
        if run is None:
            return RealtimeTrackingStatus(
                as_of=self._now(),
                subscribed_wallets=[],
                stored_events=len(events),
                decision_events=sum(1 for event in events if event.eligible_for_decisions),
            )
        return RealtimeTrackingStatus(
            as_of=self._now(),
            subscribed_wallets=list(run.subscribed_wallets),
            stored_events=len(events),
            decision_events=sum(1 for event in events if event.eligible_for_decisions),
            received=run.received,
            recorded=run.recorded,
            duplicates=run.duplicates,
            processed_only=run.processed_only,
            skipped_unsubscribed=run.skipped_unsubscribed,
            reconnects=run.reconnects,
            max_lag_seconds=run.max_lag_seconds,
            processing_latency_seconds=run.processing_latency_seconds,
            last_run_at=run.completed_at,
            warnings=list(run.warnings),
        )


class InMemoryRealtimeTrackingStore:
    """Deterministic event and run store used by HTTP tests."""

    def __init__(self) -> None:
        self._events: dict[str, RealtimeWalletEvent] = {}
        self._order: list[str] = []
        self._runs: dict[str, RealtimeTrackingRun] = {}
        self._run_order: list[str] = []

    async def record_event(self, event: RealtimeWalletEvent) -> RecordRealtimeEventResult:
        existing = self._events.get(event.idempotency_key)
        if existing is not None:
            if _conflicts(existing, event):
                raise ValueError("conflicting recorded realtime activity")
            return RecordRealtimeEventResult(created=False, event=existing)
        self._events[event.idempotency_key] = event
        self._order.append(event.idempotency_key)
        return RecordRealtimeEventResult(created=True, event=event)

    async def record_run(self, run: RealtimeTrackingRun) -> RealtimeTrackingRun:
        self._runs[run.run_id] = run
        self._run_order.append(run.run_id)
        return run

    async def events(self) -> list[RealtimeWalletEvent]:
        return [self._events[key] for key in self._order]

    async def latest_run(self) -> Optional[RealtimeTrackingRun]:
        if not self._run_order:
            return None
        return self._runs[self._run_order[-1]]


def _json_document(document: RealtimeModel) -> str:
    return json.dumps(document.model_dump(mode="json"), sort_keys=True, separators=(",", ":"))


def _json_value(value: Any) -> Any:
    return json.loads(value) if isinstance(value, str) else value


# Fixed column list shared by every event statement; never built from input.
_EVENT_COLUMNS = (
    "idempotency_key, event_id, wallet_address, token_address, movement_type, quantity, "
    "notional_usd, price_usd, venue, signature, slot, chain_time, observed_at, received_at, "
    "commitment, wallet_score, score_as_of, eligible_for_decisions, evidence, coverage, warnings"
)

_RUN_COLUMNS = (
    "run_id, as_of, started_at, completed_at, subscribed_wallets, received, recorded, "
    "duplicates, processed_only, skipped_unsubscribed, reconnects, max_lag_seconds, "
    "processing_latency_seconds, warnings"
)


class PostgresRealtimeTrackingStore:
    """PostgreSQL source of truth for normalized realtime events and runs."""

    def __init__(self, engine: AsyncEngine) -> None:
        self._engine = engine

    async def record_event(self, event: RealtimeWalletEvent) -> RecordRealtimeEventResult:
        async with self._engine.begin() as connection:
            await connection.execute(
                text("SELECT pg_advisory_xact_lock(hashtext(:key))"),
                {"key": event.idempotency_key},
            )
            existing = await connection.execute(
                text(
                    f"""
                    SELECT {_EVENT_COLUMNS}
                    FROM realtime_wallet_events
                    WHERE idempotency_key = :idempotency_key
                    """
                ),
                {"idempotency_key": event.idempotency_key},
            )
            row = existing.mappings().one_or_none()
            if row is not None:
                recorded = self._event_from_row(row)
                if _conflicts(recorded, event):
                    raise ValueError("conflicting recorded realtime activity")
                return RecordRealtimeEventResult(created=False, event=recorded)
            inserted = await connection.execute(
                text(
                    f"""
                    INSERT INTO realtime_wallet_events (
                        idempotency_key, event_id, wallet_address, token_address, movement_type,
                        quantity, notional_usd, price_usd, venue, signature, slot, chain_time,
                        observed_at, received_at, commitment, wallet_score, score_as_of,
                        eligible_for_decisions, evidence, coverage, warnings
                    ) VALUES (
                        :idempotency_key, :event_id, :wallet_address, :token_address,
                        :movement_type, :quantity, :notional_usd, :price_usd, :venue, :signature,
                        :slot, :chain_time, :observed_at, :received_at, :commitment,
                        :wallet_score, :score_as_of, :eligible_for_decisions,
                        CAST(:evidence AS JSONB), CAST(:coverage AS JSONB),
                        CAST(:warnings AS JSONB)
                    )
                    RETURNING {_EVENT_COLUMNS}
                    """
                ),
                {
                    "idempotency_key": event.idempotency_key,
                    "event_id": event.event_id,
                    "wallet_address": event.wallet_address,
                    "token_address": event.token_address,
                    "movement_type": event.movement_type,
                    "quantity": event.quantity,
                    "notional_usd": event.notional_usd,
                    "price_usd": event.price_usd,
                    "venue": event.venue,
                    "signature": event.signature,
                    "slot": event.slot,
                    "chain_time": event.chain_time,
                    "observed_at": event.observed_at,
                    "received_at": event.received_at,
                    "commitment": event.commitment,
                    "wallet_score": event.wallet_score,
                    "score_as_of": event.score_as_of,
                    "eligible_for_decisions": event.eligible_for_decisions,
                    "evidence": json.dumps(list(event.evidence)),
                    "coverage": _json_document(event.coverage),
                    "warnings": json.dumps(list(event.warnings)),
                },
            )
            return RecordRealtimeEventResult(
                created=True, event=self._event_from_row(inserted.mappings().one())
            )

    async def record_run(self, run: RealtimeTrackingRun) -> RealtimeTrackingRun:
        async with self._engine.begin() as connection:
            inserted = await connection.execute(
                text(
                    f"""
                    INSERT INTO realtime_tracking_runs (
                        run_id, as_of, started_at, completed_at, subscribed_wallets, received,
                        recorded, duplicates, processed_only, skipped_unsubscribed, reconnects,
                        max_lag_seconds, processing_latency_seconds, warnings
                    ) VALUES (
                        CAST(:run_id AS UUID), :as_of, :started_at, :completed_at,
                        CAST(:subscribed_wallets AS JSONB), :received, :recorded, :duplicates,
                        :processed_only, :skipped_unsubscribed, :reconnects, :max_lag_seconds,
                        :processing_latency_seconds, CAST(:warnings AS JSONB)
                    )
                    RETURNING {_RUN_COLUMNS}
                    """
                ),
                {
                    "run_id": run.run_id,
                    "as_of": run.as_of,
                    "started_at": run.started_at,
                    "completed_at": run.completed_at,
                    "subscribed_wallets": json.dumps(list(run.subscribed_wallets)),
                    "received": run.received,
                    "recorded": run.recorded,
                    "duplicates": run.duplicates,
                    "processed_only": run.processed_only,
                    "skipped_unsubscribed": run.skipped_unsubscribed,
                    "reconnects": run.reconnects,
                    "max_lag_seconds": run.max_lag_seconds,
                    "processing_latency_seconds": run.processing_latency_seconds,
                    "warnings": json.dumps(list(run.warnings)),
                },
            )
            return self._run_from_row(inserted.mappings().one())

    async def events(self) -> list[RealtimeWalletEvent]:
        async with self._engine.connect() as connection:
            result = await connection.execute(
                text(
                    f"""
                    SELECT {_EVENT_COLUMNS}
                    FROM realtime_wallet_events
                    ORDER BY received_at, idempotency_key
                    """
                )
            )
            return [self._event_from_row(row) for row in result.mappings()]

    async def latest_run(self) -> Optional[RealtimeTrackingRun]:
        async with self._engine.connect() as connection:
            result = await connection.execute(
                text(
                    f"""
                    SELECT {_RUN_COLUMNS}
                    FROM realtime_tracking_runs
                    ORDER BY started_at DESC, run_id DESC
                    LIMIT 1
                    """
                )
            )
            row = result.mappings().one_or_none()
        return None if row is None else self._run_from_row(row)

    @staticmethod
    def _event_from_row(row: RowMapping) -> RealtimeWalletEvent:
        return RealtimeWalletEvent(
            idempotency_key=str(row["idempotency_key"]),
            event_id=str(row["event_id"]),
            wallet_address=str(row["wallet_address"]),
            token_address=str(row["token_address"]),
            movement_type=row["movement_type"],
            quantity=float(row["quantity"]),
            notional_usd=None if row["notional_usd"] is None else float(row["notional_usd"]),
            price_usd=None if row["price_usd"] is None else float(row["price_usd"]),
            venue=None if row["venue"] is None else str(row["venue"]),
            signature=str(row["signature"]),
            slot=int(row["slot"]),
            chain_time=row["chain_time"],
            observed_at=row["observed_at"],
            received_at=row["received_at"],
            commitment=row["commitment"],
            wallet_score=None if row["wallet_score"] is None else float(row["wallet_score"]),
            score_as_of=row["score_as_of"],
            eligible_for_decisions=bool(row["eligible_for_decisions"]),
            evidence=[str(item) for item in _json_value(row["evidence"])],
            coverage=RealtimeCoverage.model_validate(_json_value(row["coverage"])),
            warnings=[str(item) for item in _json_value(row["warnings"])],
        )

    @staticmethod
    def _run_from_row(row: RowMapping) -> RealtimeTrackingRun:
        return RealtimeTrackingRun(
            run_id=str(row["run_id"]),
            as_of=row["as_of"],
            started_at=row["started_at"],
            completed_at=row["completed_at"],
            subscribed_wallets=[str(item) for item in _json_value(row["subscribed_wallets"])],
            received=int(row["received"]),
            recorded=int(row["recorded"]),
            duplicates=int(row["duplicates"]),
            processed_only=int(row["processed_only"]),
            skipped_unsubscribed=int(row["skipped_unsubscribed"]),
            reconnects=int(row["reconnects"]),
            max_lag_seconds=(
                None if row["max_lag_seconds"] is None else float(row["max_lag_seconds"])
            ),
            processing_latency_seconds=float(row["processing_latency_seconds"]),
            warnings=[str(item) for item in _json_value(row["warnings"])],
        )
