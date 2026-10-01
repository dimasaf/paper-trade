"""Point-in-time Token market observations from documented, recorded providers.

The adapter deliberately consumes recorded provider responses.  It makes no
network request and keeps one provider's timestamped observation intact: callers
can select a fallback observation, but never receive fields silently blended
across providers or observation times.
"""

import json
from collections.abc import Sequence
from datetime import datetime
from typing import Any, Literal, Optional, Protocol
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field, model_validator
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine

from paper_trade.launch_events import _is_solana_public_key

UNKNOWN = "UNKNOWN"

MarketProvider = Literal["DEXSCREENER", "GECKOTERMINAL", "JUPITER"]
DOCUMENTED_MARKET_FALLBACK_ORDER: tuple[MarketProvider, ...] = (
    "DEXSCREENER",
    "GECKOTERMINAL",
    "JUPITER",
)


class MarketStateModel(BaseModel):
    """Base market-state document; unexpected provider fields are rejected."""

    model_config = ConfigDict(extra="forbid")


class MarketProviderCoverage(MarketStateModel):
    """Provider coverage for one observation, including explicit unknown facts."""

    provider: MarketProvider
    requested_as_of: datetime
    as_of_start: datetime
    as_of_end: datetime
    complete: bool
    freshness_seconds: int = Field(ge=0)
    unknown_fields: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_interval(self) -> "MarketProviderCoverage":
        if self.as_of_end < self.as_of_start:
            raise ValueError("as_of_end must not be earlier than as_of_start")
        if not self.complete and not (self.unknown_fields or self.warnings):
            raise ValueError("incomplete coverage must declare unknown_fields or warnings")
        return self


class MarketPool(MarketStateModel):
    """A pool reported by the same provider observation as the market facts."""

    address: str
    venue: str = Field(min_length=1)
    sol_usd_price: Optional[float] = Field(default=None, gt=0)
    sol_reserve: Optional[float] = Field(default=None, gt=0)
    token_reserve: Optional[float] = Field(default=None, gt=0)

    @model_validator(mode="after")
    def validate_reserves(self) -> "MarketPool":
        if (self.sol_reserve is None) != (self.token_reserve is None):
            raise ValueError("sol_reserve and token_reserve must be supplied together")
        return self

    @model_validator(mode="after")
    def validate_address(self) -> "MarketPool":
        if not _is_solana_public_key(self.address):
            raise ValueError("address must be a valid Solana public key")
        return self


class MarketObservation(MarketStateModel):
    """One provider-native market snapshot, never a field-by-field merge."""

    observation_id: str = Field(min_length=1)
    address: str = Field(min_length=1)
    observed_at: datetime
    price_usd: Optional[float] = Field(default=None, gt=0)
    supply: Optional[float] = Field(default=None, gt=0)
    market_cap_usd: Optional[float] = Field(default=None, ge=0)
    liquidity_usd: Optional[float] = Field(default=None, ge=0)
    volume_24h_usd: Optional[float] = Field(default=None, ge=0)
    pools: list[MarketPool] = Field(default_factory=list)
    coverage: MarketProviderCoverage

    @model_validator(mode="after")
    def validate_unknown_fields(self) -> "MarketObservation":
        if not _is_solana_public_key(self.address):
            raise ValueError("address must be a valid Solana public key")
        allowed = {
            "price_usd",
            "supply",
            "market_cap_usd",
            "liquidity_usd",
            "volume_24h_usd",
            "pools",
        }
        for field in self.coverage.unknown_fields:
            if field not in allowed:
                raise ValueError(f"unknown_fields contains unsupported market field {field!r}")
            value = getattr(self, field)
            if value not in (None, []):
                raise ValueError(f"{field} is declared unknown but carries {value!r}")
        return self


class MarketPeak(MarketStateModel):
    """A maximum derived from a persisted observation, with its provenance."""

    value_usd: float = Field(ge=0)
    observed_at: datetime
    observation_id: str
    provider: MarketProvider


class MarketPeaks(MarketStateModel):
    """Peak facts derived from stored market observations, never vendor claims."""

    market_cap_usd: Optional[MarketPeak] = None
    liquidity_usd: Optional[MarketPeak] = None


class TokenMarketState(MarketStateModel):
    """The selected current observation and all point-in-time evidence used."""

    address: str
    as_of: datetime
    current: Optional[MarketObservation] = None
    observations: list[MarketObservation] = Field(default_factory=list)
    peaks: MarketPeaks
    coverage: list[MarketProviderCoverage] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)


class MarketDataSource(Protocol):
    """Public Adapter contract for documented provider market responses."""

    async def market_observations(
        self, address: str, as_of: datetime
    ) -> Sequence[MarketObservation]:
        """Return all recorded pages through `as_of` in deterministic order."""


class RecordedMarketDataSource:
    """Deterministic provider Adapter over recorded pages; it performs no I/O."""

    def __init__(self, pages: Sequence[Sequence[MarketObservation]]) -> None:
        self._pages = [
            [MarketObservation.model_validate(observation.model_dump()) for observation in page]
            for page in pages
        ]

    async def market_observations(
        self, address: str, as_of: datetime
    ) -> Sequence[MarketObservation]:
        unique: dict[str, MarketObservation] = {}
        for page in self._pages:
            for observation in page:
                if observation.address != address or observation.observed_at > as_of:
                    continue
                prior = unique.get(observation.observation_id)
                if prior is not None and prior != observation:
                    raise ValueError("conflicting recorded market observation")
                unique[observation.observation_id] = observation
        return sorted(
            unique.values(),
            key=lambda observation: (
                observation.observed_at,
                observation.coverage.provider,
                observation.observation_id,
            ),
        )


class MarketStateStore(Protocol):
    """Durable observation store; observation ids make recorded retries idempotent."""

    async def record(self, observation: MarketObservation) -> bool:
        """Persist one observation and return whether this recording is new."""

    async def observations(self, address: str, as_of: datetime) -> list[MarketObservation]:
        """Return stored observations at or before the requested point in time."""


class InMemoryMarketStateStore:
    """Deterministic persistence Adapter used by HTTP and recorded provider tests."""

    def __init__(self) -> None:
        self._observations: dict[tuple[str, str], MarketObservation] = {}

    async def record(self, observation: MarketObservation) -> bool:
        key = (observation.address, observation.observation_id)
        existing = self._observations.get(key)
        if existing is not None:
            if existing != observation:
                raise ValueError("conflicting recorded market observation")
            return False
        self._observations[key] = observation
        return True

    async def observations(self, address: str, as_of: datetime) -> list[MarketObservation]:
        return sorted(
            [
                observation
                for (record_address, _), observation in self._observations.items()
                if record_address == address and observation.observed_at <= as_of
            ],
            key=lambda observation: (
                observation.observed_at,
                observation.coverage.provider,
                observation.observation_id,
            ),
        )


class PostgresMarketStateStore:
    """PostgreSQL Adapter for point-in-time market observations."""

    def __init__(self, engine: AsyncEngine) -> None:
        self._engine = engine

    async def record(self, observation: MarketObservation) -> bool:
        async with self._engine.begin() as connection:
            result = await connection.execute(
                text(
                    """
                    INSERT INTO token_market_observations (
                        id, token_id, observation_id, observed_at, price_usd, supply,
                        market_cap_usd, liquidity_usd, volume_24h_usd, pools, coverage
                    )
                    SELECT
                        CAST(:id AS UUID), id, :observation_id, :observed_at, :price_usd,
                        :supply, :market_cap_usd, :liquidity_usd, :volume_24h_usd,
                        CAST(:pools AS JSONB), CAST(:coverage AS JSONB)
                    FROM tokens
                    WHERE address = :address
                    ON CONFLICT (token_id, observation_id) DO NOTHING
                    RETURNING id
                    """
                ),
                {
                    "id": str(uuid4()),
                    "address": observation.address,
                    "observation_id": observation.observation_id,
                    "observed_at": observation.observed_at,
                    "price_usd": observation.price_usd,
                    "supply": observation.supply,
                    "market_cap_usd": observation.market_cap_usd,
                    "liquidity_usd": observation.liquidity_usd,
                    "volume_24h_usd": observation.volume_24h_usd,
                    "pools": _dump_json_list(observation.pools),
                    "coverage": _dump_json(observation.coverage),
                },
            )
            return result.scalar_one_or_none() is not None

    async def observations(self, address: str, as_of: datetime) -> list[MarketObservation]:
        async with self._engine.connect() as connection:
            result = await connection.execute(
                text(
                    """
                    SELECT observation.observation_id, observation.observed_at,
                           observation.price_usd, observation.supply,
                           observation.market_cap_usd, observation.liquidity_usd,
                           observation.volume_24h_usd, observation.pools, observation.coverage
                    FROM token_market_observations observation
                    JOIN tokens token ON token.id = observation.token_id
                    WHERE token.address = :address AND observation.observed_at <= :as_of
                    ORDER BY observation.observed_at, observation.coverage ->> 'provider',
                             observation.observation_id
                    """
                ),
                {"address": address, "as_of": as_of},
            )
            return [
                MarketObservation(
                    observation_id=row["observation_id"],
                    address=address,
                    observed_at=row["observed_at"],
                    price_usd=row["price_usd"],
                    supply=row["supply"],
                    market_cap_usd=row["market_cap_usd"],
                    liquidity_usd=row["liquidity_usd"],
                    volume_24h_usd=row["volume_24h_usd"],
                    pools=[MarketPool.model_validate(pool) for pool in _load_json(row["pools"])],
                    coverage=MarketProviderCoverage.model_validate(_load_json(row["coverage"])),
                )
                for row in result.mappings()
            ]


def _dump_json(document: BaseModel) -> str:
    return document.model_dump_json()


def _dump_json_list(documents: Sequence[BaseModel]) -> str:
    return json.dumps([document.model_dump(mode="json") for document in documents])


def _load_json(value: object) -> Any:
    return json.loads(value) if isinstance(value, str) else value


class TokenMarketStateService:
    """Records observations and derives current state and peaks at one as-of time."""

    def __init__(self, store: MarketStateStore) -> None:
        self._store = store

    async def record_from(self, source: MarketDataSource, address: str, as_of: datetime) -> int:
        """Record the complete deterministic source result, including incomplete coverage."""

        observations = await source.market_observations(address, as_of)
        return sum([await self._store.record(observation) for observation in observations])

    async def state(self, address: str, as_of: datetime) -> TokenMarketState:
        observations = await self._store.observations(address, as_of)
        current, selection_warnings = _select_current(observations, as_of)
        coverage = [observation.coverage for observation in observations]
        warnings = [*selection_warnings]
        for entry in coverage:
            warnings.extend(entry.warnings)
            if not entry.complete:
                warnings.append(f"{entry.provider} coverage is incomplete")
            warnings.extend(f"{field} is UNKNOWN" for field in entry.unknown_fields)
        if not observations:
            warnings.append("Market state is UNKNOWN because no observation is recorded")
        return TokenMarketState(
            address=address,
            as_of=as_of,
            current=current,
            observations=observations,
            peaks=MarketPeaks(
                market_cap_usd=_peak_for(observations, "market_cap_usd"),
                liquidity_usd=_peak_for(observations, "liquidity_usd"),
            ),
            coverage=coverage,
            warnings=list(dict.fromkeys(warnings)),
        )


def _select_current(
    observations: Sequence[MarketObservation], as_of: datetime
) -> tuple[Optional[MarketObservation], list[str]]:
    warnings: list[str] = []
    for provider in DOCUMENTED_MARKET_FALLBACK_ORDER:
        candidates = [
            observation
            for observation in observations
            if observation.coverage.provider == provider
            and observation.price_usd is not None
            and (as_of - observation.observed_at).total_seconds()
            <= observation.coverage.freshness_seconds
        ]
        if candidates:
            return max(candidates, key=lambda observation: observation.observed_at), warnings
        if any(observation.coverage.provider == provider for observation in observations):
            warnings.append(f"{provider} observation is stale at the requested as-of time")
    return None, warnings


def _peak_for(
    observations: Sequence[MarketObservation], field: Literal["market_cap_usd", "liquidity_usd"]
) -> Optional[MarketPeak]:
    candidates = [
        observation for observation in observations if getattr(observation, field) is not None
    ]
    if not candidates:
        return None
    peak = max(candidates, key=lambda observation: float(getattr(observation, field)))
    value = getattr(peak, field)
    if value is None:
        return None
    return MarketPeak(
        value_usd=value,
        observed_at=peak.observed_at,
        observation_id=peak.observation_id,
        provider=peak.coverage.provider,
    )
