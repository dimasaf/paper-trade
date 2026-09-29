"""Token universe: registration from launch events, classification, and lifecycle.

A recorded launch event is processed into one classified Token. Classification
reads the active versioned research configuration and records per-criterion
pass/fail evidence together with the configuration `id` and `version` used.
Lifecycle transitions are stored as evidence rather than only a current status.
"""

import json
from collections.abc import Sequence
from datetime import datetime
from typing import Any, Literal, Optional, Protocol
from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import text
from sqlalchemy.engine import RowMapping
from sqlalchemy.ext.asyncio import AsyncConnection, AsyncEngine

from paper_trade.launch_events import (
    UNKNOWN,
    LaunchEvent,
    LaunchProgramEvidence,
    LaunchSource,
    LifecycleState,
    ProviderCoverage,
)
from paper_trade.research_configuration import (
    ResearchConfigurationStore,
    VersionedResearchConfiguration,
)


class TokenModel(BaseModel):
    """Base for Token documents exchanged over HTTP; unknown fields are rejected."""

    model_config = ConfigDict(extra="forbid")


class ClassificationCriterion(TokenModel):
    """One configured classification rule with its observed value and outcome."""

    criterion: str
    threshold: str
    observed: str
    passed: bool


class Classification(TokenModel):
    """The active configuration used and every pass/fail classification outcome."""

    configuration_id: UUID
    configuration_version: int
    passed: bool
    criteria: list[ClassificationCriterion]


class LifecycleTransition(TokenModel):
    """A recorded lifecycle change with the event that asserted it."""

    state: LifecycleState
    observed_at: datetime
    source_event_id: str
    reason: str = ""
    evidence: list[LaunchProgramEvidence] = Field(default_factory=list)


class TokenRecord(TokenModel):
    """A classified Token with provenance, lifecycle evidence, and coverage."""

    address: str
    name: str
    symbol: str
    creator: str
    created_at: datetime
    observed_at: datetime
    launch_platform: LaunchSource
    lifecycle_state: LifecycleState
    lifecycle_transitions: list[LifecycleTransition]
    classification: Classification
    coverage: list[ProviderCoverage]


class TokenRegistration(TokenModel):
    """A classified Token to persist idempotently from one confirmed launch event."""

    address: str
    name: str
    symbol: str
    creator: str
    created_at: datetime
    observed_at: datetime
    launch_platform: LaunchSource
    lifecycle_state: LifecycleState
    source_event_id: str
    evidence: list[LaunchProgramEvidence]
    classification: Classification
    coverage: ProviderCoverage


class StoredRegistration(TokenModel):
    """Result of persisting a registration; `created` distinguishes a replay."""

    created: bool
    token: TokenRecord


class TokenRegistrationOutcome(TokenModel):
    """Observable result of processing one launch event."""

    status: Literal["created", "existing", "rejected"]
    reason: str = ""
    token: Optional[TokenRecord] = None


class RegisterTokenRequest(TokenModel):
    """HTTP request body for registering a Token from a recorded launch event."""

    event: LaunchEvent


class TokenStore(Protocol):
    """Persistence contract for the durable Token universe."""

    async def register(self, registration: TokenRegistration) -> StoredRegistration:
        """Idempotently persist one classified Token and return its record."""

    async def get(self, address: str) -> Optional[TokenRecord]:
        """Return one Token by address, or `None` when it is not registered."""

    async def list(self) -> list[TokenRecord]:
        """Return every registered Token in registration order."""


def latest_lifecycle_state(transitions: Sequence[LifecycleTransition]) -> LifecycleState:
    """Return the state of the most recently observed transition."""

    latest = transitions[0]
    for transition in transitions[1:]:
        if transition.observed_at >= latest.observed_at:
            latest = transition
    return latest.state


def classify_launch_event(
    event: LaunchEvent,
    configuration: VersionedResearchConfiguration,
) -> Classification:
    """Evaluate the configured Token rules against one recorded launch event."""

    settings = configuration.configuration.token
    criteria = [
        ClassificationCriterion(
            criterion="launch_source",
            threshold=", ".join(settings.launch_sources),
            observed=event.launch_platform,
            passed=event.launch_platform in settings.launch_sources,
        ),
        ClassificationCriterion(
            criterion="pool",
            threshold="required" if settings.require_pool else "not required",
            observed=_observed_pool(event.has_pool),
            passed=(not settings.require_pool) or event.has_pool is True,
        ),
        _minimum_criterion("liquidity_usd", event.liquidity_usd, settings.minimum_liquidity_usd),
        _minimum_criterion("market_cap_usd", event.market_cap_usd, settings.minimum_market_cap_usd),
        _minimum_criterion("volume_24h_usd", event.volume_24h_usd, settings.minimum_24h_volume_usd),
    ]
    return Classification(
        configuration_id=configuration.id,
        configuration_version=configuration.version,
        passed=all(criterion.passed for criterion in criteria),
        criteria=criteria,
    )


def _observed_pool(has_pool: Optional[bool]) -> str:
    if has_pool is None:
        return UNKNOWN
    return "present" if has_pool else "absent"


def _minimum_criterion(
    criterion: str,
    observed: Optional[float],
    minimum: float,
) -> ClassificationCriterion:
    return ClassificationCriterion(
        criterion=criterion,
        threshold=f">= {minimum:g}",
        observed=UNKNOWN if observed is None else f"{observed:g}",
        passed=observed is not None and observed >= minimum,
    )


class TokenRegistrationService:
    """Deep module that turns a recorded launch event into a classified Token."""

    def __init__(
        self,
        *,
        store: TokenStore,
        configuration_store: ResearchConfigurationStore,
    ) -> None:
        self._store = store
        self._configuration_store = configuration_store

    async def register_launch_event(self, event: LaunchEvent) -> TokenRegistrationOutcome:
        if event.coverage.commitment != "confirmed":
            return TokenRegistrationOutcome(
                status="rejected",
                reason="Only confirmed launch events can create or transition a Token (ADR-0002)",
            )
        configuration = await self._configuration_store.get_active()
        registration = TokenRegistration(
            address=event.address,
            name=event.name,
            symbol=event.symbol,
            creator=event.creator,
            created_at=event.created_at,
            observed_at=event.observed_at,
            launch_platform=event.launch_platform,
            lifecycle_state=event.lifecycle_state,
            source_event_id=event.event_id,
            evidence=event.evidence,
            classification=classify_launch_event(event, configuration),
            coverage=event.coverage,
        )
        stored = await self._store.register(registration)
        return TokenRegistrationOutcome(
            status="created" if stored.created else "existing",
            token=stored.token,
        )


def _transition_from(registration: TokenRegistration) -> LifecycleTransition:
    return LifecycleTransition(
        state=registration.lifecycle_state,
        observed_at=registration.observed_at,
        source_event_id=registration.source_event_id,
        reason="launch event registered",
        evidence=registration.evidence,
    )


class InMemoryTokenStore:
    """Database-boundary Adapter for deterministic HTTP and provider tests."""

    def __init__(self) -> None:
        self._tokens: dict[str, TokenRecord] = {}

    async def register(self, registration: TokenRegistration) -> StoredRegistration:
        existing = self._tokens.get(registration.address)
        if existing is None:
            record = TokenRecord(
                address=registration.address,
                name=registration.name,
                symbol=registration.symbol,
                creator=registration.creator,
                created_at=registration.created_at,
                observed_at=registration.observed_at,
                launch_platform=registration.launch_platform,
                lifecycle_state=registration.lifecycle_state,
                lifecycle_transitions=[_transition_from(registration)],
                classification=registration.classification,
                coverage=[registration.coverage],
            )
            self._tokens[registration.address] = record
            return StoredRegistration(created=True, token=record)

        if any(
            transition.source_event_id == registration.source_event_id
            for transition in existing.lifecycle_transitions
        ):
            return StoredRegistration(created=False, token=existing)

        transitions = [*existing.lifecycle_transitions, _transition_from(registration)]
        coverage = [*existing.coverage, registration.coverage]
        record = existing.model_copy(
            update={
                "lifecycle_state": latest_lifecycle_state(transitions),
                "lifecycle_transitions": transitions,
                "classification": registration.classification,
                "coverage": coverage,
            }
        )
        self._tokens[registration.address] = record
        return StoredRegistration(created=False, token=record)

    async def get(self, address: str) -> Optional[TokenRecord]:
        return self._tokens.get(address)

    async def list(self) -> list[TokenRecord]:
        return list(self._tokens.values())


class PostgresTokenStore:
    """PostgreSQL Adapter for the durable Token universe."""

    def __init__(self, engine: AsyncEngine) -> None:
        self._engine = engine

    async def register(self, registration: TokenRegistration) -> StoredRegistration:
        async with self._engine.begin() as connection:
            await connection.execute(
                text("SELECT pg_advisory_xact_lock(hashtext(:address))"),
                {"address": registration.address},
            )
            existing = await connection.execute(
                text("SELECT id FROM tokens WHERE address = :address"),
                {"address": registration.address},
            )
            row = existing.mappings().one_or_none()
            created = row is None
            if row is None:
                token_id = uuid4()
                await connection.execute(
                    text(
                        """
                        INSERT INTO tokens (
                            id, address, name, symbol, creator, created_at, observed_at,
                            launch_platform, lifecycle_state, classification, source_event_id
                        ) VALUES (
                            CAST(:id AS UUID), :address, :name, :symbol, :creator, :created_at,
                            :observed_at, :launch_platform, :lifecycle_state,
                            CAST(:classification AS JSONB), :source_event_id
                        )
                        """
                    ),
                    {
                        "id": str(token_id),
                        "address": registration.address,
                        "name": registration.name,
                        "symbol": registration.symbol,
                        "creator": registration.creator,
                        "created_at": registration.created_at,
                        "observed_at": registration.observed_at,
                        "launch_platform": registration.launch_platform,
                        "lifecycle_state": registration.lifecycle_state,
                        "classification": _dump_json(registration.classification),
                        "source_event_id": registration.source_event_id,
                    },
                )
            else:
                token_id = UUID(str(row["id"]))

            transition_recorded = await self._record_transition(connection, token_id, registration)
            await self._record_coverage(connection, token_id, registration)
            if created or transition_recorded:
                await connection.execute(
                    text(
                        """
                        UPDATE tokens
                        SET classification = CAST(:classification AS JSONB)
                        WHERE id = CAST(:id AS UUID)
                        """
                    ),
                    {
                        "id": str(token_id),
                        "classification": _dump_json(registration.classification),
                    },
                )
            await connection.execute(
                text(
                    """
                    UPDATE tokens
                    SET lifecycle_state = (
                        SELECT state
                        FROM token_lifecycle_transitions
                        WHERE token_id = tokens.id
                        ORDER BY observed_at DESC, sequence DESC
                        LIMIT 1
                    )
                    WHERE id = CAST(:id AS UUID)
                    """
                ),
                {"id": str(token_id)},
            )

        token = await self.get(registration.address)
        if token is None:
            raise RuntimeError("Token registration did not persist")
        return StoredRegistration(created=created, token=token)

    async def get(self, address: str) -> Optional[TokenRecord]:
        async with self._engine.connect() as connection:
            result = await connection.execute(
                text(
                    """
                    SELECT id, address, name, symbol, creator, created_at, observed_at,
                           launch_platform, lifecycle_state, classification
                    FROM tokens
                    WHERE address = :address
                    """
                ),
                {"address": address},
            )
            row = result.mappings().one_or_none()
            if row is None:
                return None
            return await self._record_from_row(connection, row)

    async def list(self) -> list[TokenRecord]:
        async with self._engine.connect() as connection:
            result = await connection.execute(
                text(
                    """
                    SELECT id, address, name, symbol, creator, created_at, observed_at,
                           launch_platform, lifecycle_state, classification
                    FROM tokens
                    ORDER BY registered_at, address
                    """
                )
            )
            return [await self._record_from_row(connection, row) for row in result.mappings()]

    async def _record_transition(
        self,
        connection: AsyncConnection,
        token_id: UUID,
        registration: TokenRegistration,
    ) -> bool:
        result = await connection.execute(
            text(
                """
                INSERT INTO token_lifecycle_transitions (
                    id, token_id, state, observed_at, source_event_id, reason, evidence
                ) VALUES (
                    CAST(:id AS UUID), CAST(:token_id AS UUID), :state, :observed_at,
                    :source_event_id, :reason, CAST(:evidence AS JSONB)
                )
                ON CONFLICT (token_id, source_event_id) DO NOTHING
                RETURNING id
                """
            ),
            {
                "id": str(uuid4()),
                "token_id": str(token_id),
                "state": registration.lifecycle_state,
                "observed_at": registration.observed_at,
                "source_event_id": registration.source_event_id,
                "reason": "launch event registered",
                "evidence": _dump_json_list(registration.evidence),
            },
        )
        return result.scalar_one_or_none() is not None

    async def _record_coverage(
        self,
        connection: AsyncConnection,
        token_id: UUID,
        registration: TokenRegistration,
    ) -> None:
        coverage = registration.coverage
        await connection.execute(
            text(
                """
                INSERT INTO token_provider_coverage (
                    id, token_id, provider, as_of_start, as_of_end, complete,
                    commitment, freshness_seconds, signature, slot, normalization_version,
                    unknown_fields, warnings, source_event_id
                ) VALUES (
                    CAST(:id AS UUID), CAST(:token_id AS UUID), :provider, :as_of_start,
                    :as_of_end, :complete, :commitment, :freshness_seconds, :signature,
                    :slot, :normalization_version, CAST(:unknown_fields AS JSONB),
                    CAST(:warnings AS JSONB), :source_event_id
                )
                ON CONFLICT (token_id, source_event_id) DO NOTHING
                """
            ),
            {
                "id": str(uuid4()),
                "token_id": str(token_id),
                "provider": coverage.provider,
                "as_of_start": coverage.as_of_start,
                "as_of_end": coverage.as_of_end,
                "complete": coverage.complete,
                "commitment": coverage.commitment,
                "freshness_seconds": coverage.freshness_seconds,
                "signature": coverage.signature,
                "slot": coverage.slot,
                "normalization_version": coverage.normalization_version,
                "unknown_fields": json.dumps(coverage.unknown_fields),
                "warnings": json.dumps(coverage.warnings),
                "source_event_id": registration.source_event_id,
            },
        )

    async def _record_from_row(self, connection: AsyncConnection, row: RowMapping) -> TokenRecord:
        token_id = UUID(str(row["id"]))
        transitions = await connection.execute(
            text(
                """
                SELECT state, observed_at, source_event_id, reason, evidence
                FROM token_lifecycle_transitions
                WHERE token_id = CAST(:token_id AS UUID)
                ORDER BY observed_at, sequence
                """
            ),
            {"token_id": str(token_id)},
        )
        coverage = await connection.execute(
            text(
                """
                SELECT provider, as_of_start, as_of_end, complete, commitment,
                       freshness_seconds, signature, slot, normalization_version,
                       unknown_fields, warnings
                FROM token_provider_coverage
                WHERE token_id = CAST(:token_id AS UUID)
                ORDER BY as_of_start, provider, source_event_id
                """
            ),
            {"token_id": str(token_id)},
        )
        return TokenRecord(
            address=row["address"],
            name=row["name"],
            symbol=row["symbol"],
            creator=row["creator"],
            created_at=row["created_at"],
            observed_at=row["observed_at"],
            launch_platform=row["launch_platform"],
            lifecycle_state=row["lifecycle_state"],
            lifecycle_transitions=[
                LifecycleTransition(
                    state=transition["state"],
                    observed_at=transition["observed_at"],
                    source_event_id=transition["source_event_id"],
                    reason=transition["reason"],
                    evidence=[
                        LaunchProgramEvidence.model_validate(item)
                        for item in _load_json(transition["evidence"])
                    ],
                )
                for transition in transitions.mappings()
            ],
            classification=Classification.model_validate(_load_json(row["classification"])),
            coverage=[
                ProviderCoverage(
                    provider=item["provider"],
                    as_of_start=item["as_of_start"],
                    as_of_end=item["as_of_end"],
                    complete=item["complete"],
                    commitment=item["commitment"],
                    freshness_seconds=item["freshness_seconds"],
                    signature=item["signature"],
                    slot=item["slot"],
                    normalization_version=item["normalization_version"],
                    unknown_fields=list(_load_json(item["unknown_fields"])),
                    warnings=list(_load_json(item["warnings"])),
                )
                for item in coverage.mappings()
            ],
        )


def _dump_json(document: BaseModel) -> str:
    return json.dumps(document.model_dump(mode="json"))


def _dump_json_list(documents: Sequence[BaseModel]) -> str:
    return json.dumps([document.model_dump(mode="json") for document in documents])


def _load_json(value: object) -> Any:
    if isinstance(value, str):
        return json.loads(value)
    return value
