"""Versioned assumptions used by research and Paper Trading modules."""

import json
from datetime import datetime, timezone
from typing import Annotated, Callable, Literal, Optional, Protocol
from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator
from sqlalchemy import text
from sqlalchemy.engine import RowMapping
from sqlalchemy.ext.asyncio import AsyncEngine


class ConfigurationModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


LaunchSource = Literal[
    "PUMP_FUN",
    "PUMP_SWAP",
    "RAYDIUM_LAUNCHLAB",
    "METEORA_DBC",
    "JUPITER_STUDIO",
]
PositiveInteger = Annotated[int, Field(gt=0)]
PositiveNumber = Annotated[float, Field(gt=0)]


def default_launch_sources() -> list[LaunchSource]:
    return [
        "PUMP_FUN",
        "PUMP_SWAP",
        "RAYDIUM_LAUNCHLAB",
        "METEORA_DBC",
        "JUPITER_STUDIO",
    ]


class TokenSettings(ConfigurationModel):
    launch_sources: list[LaunchSource] = Field(
        default_factory=default_launch_sources,
        min_length=1,
    )
    require_pool: bool = True
    minimum_liquidity_usd: float = Field(default=10_000, ge=0)
    minimum_market_cap_usd: float = Field(default=25_000, ge=0)
    minimum_24h_volume_usd: float = Field(default=10_000, ge=0)
    winner_initial_market_cap_min_usd: float = Field(default=10_000, ge=0)
    winner_initial_market_cap_max_usd: float = Field(default=500_000, gt=0)
    winner_peak_market_cap_min_usd: float = Field(default=1_000_000, gt=0)
    entry_market_cap_buckets_usd: list[PositiveNumber] = Field(
        default_factory=lambda: [50_000.0, 100_000.0, 250_000.0, 500_000.0],
        min_length=1,
    )

    @field_validator("launch_sources")
    @classmethod
    def validate_launch_sources(cls, sources: list[LaunchSource]) -> list[LaunchSource]:
        if len(sources) != len(set(sources)):
            raise ValueError("launch_sources must not contain duplicates")
        return sources

    @field_validator("entry_market_cap_buckets_usd")
    @classmethod
    def validate_entry_market_cap_buckets(cls, buckets: list[float]) -> list[float]:
        if any(left >= right for left, right in zip(buckets, buckets[1:])):
            raise ValueError("entry_market_cap_buckets_usd must be strictly increasing")
        return buckets

    @model_validator(mode="after")
    def validate_winner_market_cap_range(self) -> "TokenSettings":
        if self.winner_initial_market_cap_min_usd >= self.winner_initial_market_cap_max_usd:
            raise ValueError(
                "winner_initial_market_cap_min_usd must be lower than "
                "winner_initial_market_cap_max_usd"
            )
        return self


class WalletScoreWeights(ConfigurationModel):
    profitability: float = Field(default=20, ge=0, le=100)
    consistency: float = Field(default=20, ge=0, le=100)
    copyability: float = Field(default=25, ge=0, le=100)
    risk_quality: float = Field(default=15, ge=0, le=100)
    entry_quality: float = Field(default=10, ge=0, le=100)
    history_quality: float = Field(default=10, ge=0, le=100)

    @model_validator(mode="after")
    def validate_total(self) -> "WalletScoreWeights":
        total = sum(
            (
                self.profitability,
                self.consistency,
                self.copyability,
                self.risk_quality,
                self.entry_quality,
                self.history_quality,
            )
        )
        if abs(total - 100) > 0.000001:
            raise ValueError("wallet score weights must total 100")
        return self


class WalletSettings(ConfigurationModel):
    minimum_score: float = Field(default=80, ge=0, le=100)
    minimum_trades: int = Field(default=20, ge=1)
    suspension_score: float = Field(default=45, ge=0, le=100)
    rejection_score: float = Field(default=20, ge=0, le=100)
    profitability_roi_target_percent: float = Field(default=50, gt=0)
    risk_flag_penalty: float = Field(default=10, ge=0, le=100)
    copyability_delays_ms: list[PositiveInteger] = Field(
        default_factory=lambda: [500, 1000, 2000, 3000, 5000, 10000],
        min_length=1,
    )
    copyability_sizes_sol: list[PositiveNumber] = Field(
        default_factory=lambda: [0.1, 0.25, 0.5, 1.0, 2.0],
        min_length=1,
    )
    score_weights: WalletScoreWeights = Field(default_factory=WalletScoreWeights)

    @field_validator("copyability_delays_ms")
    @classmethod
    def validate_copyability_delays(cls, delays: list[int]) -> list[int]:
        if any(left >= right for left, right in zip(delays, delays[1:])):
            raise ValueError("copyability_delays_ms must be strictly increasing")
        return delays

    @field_validator("copyability_sizes_sol")
    @classmethod
    def validate_copyability_sizes(cls, sizes: list[float]) -> list[float]:
        if len(sizes) != len(set(sizes)):
            raise ValueError("copyability_sizes_sol must not contain duplicates")
        if sizes != sorted(sizes):
            raise ValueError("copyability_sizes_sol must be increasing")
        return sizes

    @model_validator(mode="after")
    def validate_score_thresholds(self) -> "WalletSettings":
        if not (self.rejection_score <= self.suspension_score <= self.minimum_score):
            raise ValueError(
                "wallet score thresholds must not decrease: rejection_score <= "
                "suspension_score <= minimum_score"
            )
        return self


RelationshipConfidence = Literal["LOW", "MEDIUM", "HIGH"]


class ClusterSettings(ConfigurationModel):
    minimum_contributing_independent_wallets: int = Field(default=3, ge=2)
    window_seconds: int = Field(default=300, ge=1)
    minimum_average_wallet_score: float = Field(default=80, ge=0, le=100)
    relationship_confidence_threshold: RelationshipConfidence = "MEDIUM"
    synchronized_trade_window_seconds: int = Field(default=300, ge=1)
    shared_token_history_minimum_percent: float = Field(default=50, gt=0, le=100)
    transaction_pattern_similarity_minimum_percent: float = Field(default=60, gt=0, le=100)


class SignalScoreWeights(ConfigurationModel):
    wallet_quality: float = Field(default=25, ge=0, le=100)
    contributing_independent_wallets: float = Field(default=20, ge=0, le=100)
    token_risk: float = Field(default=20, ge=0, le=100)
    liquidity: float = Field(default=10, ge=0, le=100)
    entry_quality: float = Field(default=10, ge=0, le=100)
    buy_velocity: float = Field(default=10, ge=0, le=100)
    market_confirmation: float = Field(default=5, ge=0, le=100)

    @model_validator(mode="after")
    def validate_total(self) -> "SignalScoreWeights":
        total = sum(
            (
                self.wallet_quality,
                self.contributing_independent_wallets,
                self.token_risk,
                self.liquidity,
                self.entry_quality,
                self.buy_velocity,
                self.market_confirmation,
            )
        )
        if abs(total - 100) > 0.000001:
            raise ValueError("signal score weights must total 100")
        return self


class SignalSettings(ConfigurationModel):
    watch_score: float = Field(default=60, ge=0, le=100)
    paper_buy_score: float = Field(default=80, ge=0, le=100)
    cooldown_seconds: int = Field(default=900, ge=0)
    score_weights: SignalScoreWeights = Field(default_factory=SignalScoreWeights)

    @model_validator(mode="after")
    def validate_decision_thresholds(self) -> "SignalSettings":
        if self.watch_score >= self.paper_buy_score:
            raise ValueError("watch_score must be lower than paper_buy_score")
        return self


class PaperTradingSettings(ConfigurationModel):
    starting_balance_usd: float = Field(default=10_000, gt=0)
    sizing_mode: Literal["PERCENT", "SOL"] = "PERCENT"
    position_size_percent: float = Field(default=1, gt=0, le=100)
    position_size_sol: float = Field(default=0.5, gt=0)
    maximum_position_percent: float = Field(default=3, gt=0, le=100)
    maximum_open_positions: int = Field(default=10, ge=1)

    @model_validator(mode="after")
    def validate_position_range(self) -> "PaperTradingSettings":
        if self.position_size_percent > self.maximum_position_percent:
            raise ValueError("position_size_percent must not exceed maximum_position_percent")
        return self


class PartialTakeProfit(ConfigurationModel):
    gain_percent: float = Field(gt=0)
    sell_percent: float = Field(gt=0, le=100)


class RiskSettings(ConfigurationModel):
    stop_loss_percent: float = Field(default=15, gt=0, le=100)
    take_profit_percent: float = Field(default=30, gt=0)
    partial_take_profits: list[PartialTakeProfit] = Field(
        default_factory=lambda: [
            PartialTakeProfit(gain_percent=25, sell_percent=25),
            PartialTakeProfit(gain_percent=50, sell_percent=25),
            PartialTakeProfit(gain_percent=100, sell_percent=25),
        ],
        min_length=1,
    )
    trailing_stop_percent: float = Field(default=15, gt=0, le=100)
    smart_wallet_sell_pressure_percent: float = Field(default=60, ge=0, le=100)
    liquidity_collapse_percent: float = Field(default=50, ge=0, le=100)
    holder_concentration_increase_percent: float = Field(default=10, ge=0, le=100)
    volume_collapse_percent: float = Field(default=70, ge=0, le=100)
    maximum_holding_seconds: int = Field(default=86_400, ge=1)

    @model_validator(mode="after")
    def validate_partial_exits(self) -> "RiskSettings":
        gains = [rule.gain_percent for rule in self.partial_take_profits]
        if any(left >= right for left, right in zip(gains, gains[1:])):
            raise ValueError("partial take-profit gains must be strictly increasing")
        if sum(rule.sell_percent for rule in self.partial_take_profits) > 100:
            raise ValueError("partial take-profit sell percentages must not exceed 100")
        return self


class ExecutionSettings(ConfigurationModel):
    latency_ms: int = Field(default=3000, ge=0)
    fallback_slippage_percent: float = Field(default=2, ge=0, le=100)
    venue_fee_percent: float = Field(default=0.25, ge=0, le=100)
    network_fee_sol: float = Field(default=0.000005, ge=0)
    priority_fee_sol: float = Field(default=0.0001, ge=0)
    failed_transaction_probability_percent: float = Field(default=1, ge=0, le=100)
    maximum_pool_participation_percent: float = Field(default=1, gt=0, le=100)


class ResearchConfiguration(ConfigurationModel):
    token: TokenSettings = Field(default_factory=TokenSettings)
    wallet: WalletSettings = Field(default_factory=WalletSettings)
    cluster: ClusterSettings = Field(default_factory=ClusterSettings)
    signal: SignalSettings = Field(default_factory=SignalSettings)
    paper_trading: PaperTradingSettings = Field(default_factory=PaperTradingSettings)
    risk: RiskSettings = Field(default_factory=RiskSettings)
    execution: ExecutionSettings = Field(default_factory=ExecutionSettings)


class VersionedResearchConfiguration(ConfigurationModel):
    id: UUID
    version: int = Field(ge=1)
    created_at: datetime
    configuration: ResearchConfiguration


class CreateResearchConfiguration(ConfigurationModel):
    configuration: ResearchConfiguration


class ResearchConfigurationStore(Protocol):
    async def get_active(self) -> VersionedResearchConfiguration:
        """Return the highest immutable configuration version."""

    async def list_versions(self) -> list[VersionedResearchConfiguration]:
        """Return every immutable version, newest first."""

    async def get_version(self, version: int) -> Optional[VersionedResearchConfiguration]:
        """Return one immutable version when it exists."""

    async def create(self, configuration: ResearchConfiguration) -> VersionedResearchConfiguration:
        """Persist and activate a new immutable version."""


class PostgresResearchConfigurationStore:
    """PostgreSQL Adapter for immutable research configuration versions."""

    def __init__(self, engine: AsyncEngine) -> None:
        self._engine = engine

    async def get_active(self) -> VersionedResearchConfiguration:
        async with self._engine.connect() as connection:
            result = await connection.execute(
                text(
                    """
                    SELECT id, version, created_at, configuration
                    FROM research_configuration_versions
                    ORDER BY version DESC
                    LIMIT 1
                    """
                )
            )
            return self._from_row(result.mappings().one())

    async def list_versions(self) -> list[VersionedResearchConfiguration]:
        async with self._engine.connect() as connection:
            result = await connection.execute(
                text(
                    """
                    SELECT id, version, created_at, configuration
                    FROM research_configuration_versions
                    ORDER BY version DESC
                    """
                )
            )
            return [self._from_row(row) for row in result.mappings()]

    async def get_version(self, version: int) -> Optional[VersionedResearchConfiguration]:
        async with self._engine.connect() as connection:
            result = await connection.execute(
                text(
                    """
                    SELECT id, version, created_at, configuration
                    FROM research_configuration_versions
                    WHERE version = :version
                    """
                ),
                {"version": version},
            )
            row = result.mappings().one_or_none()
            return self._from_row(row) if row is not None else None

    async def create(self, configuration: ResearchConfiguration) -> VersionedResearchConfiguration:
        identifier = uuid4()
        document = json.dumps(configuration.model_dump(mode="json"))
        async with self._engine.begin() as connection:
            await connection.execute(text("SELECT pg_advisory_xact_lock(1847362910)"))
            next_version = await connection.scalar(
                text("SELECT COALESCE(MAX(version), 0) + 1 FROM research_configuration_versions")
            )
            result = await connection.execute(
                text(
                    """
                    INSERT INTO research_configuration_versions
                        (id, version, configuration)
                    VALUES
                        (CAST(:id AS UUID), :version, CAST(:configuration AS JSONB))
                    RETURNING id, version, created_at, configuration
                    """
                ),
                {
                    "id": str(identifier),
                    "version": int(next_version or 1),
                    "configuration": document,
                },
            )
            return self._from_row(result.mappings().one())

    @staticmethod
    def _from_row(row: RowMapping) -> VersionedResearchConfiguration:
        configuration = row["configuration"]
        if isinstance(configuration, str):
            configuration = json.loads(configuration)
        return VersionedResearchConfiguration(
            id=UUID(str(row["id"])),
            version=int(row["version"]),
            created_at=row["created_at"],
            configuration=ResearchConfiguration.model_validate(configuration),
        )


class InMemoryResearchConfigurationStore:
    """Database-boundary Adapter for deterministic HTTP tests."""

    def __init__(
        self,
        *,
        now: Callable[[], datetime] = lambda: datetime.now(timezone.utc),
        id_factory: Callable[[], UUID] = uuid4,
    ) -> None:
        self._now = now
        self._id_factory = id_factory
        self._versions = [
            VersionedResearchConfiguration(
                id=id_factory(),
                version=1,
                created_at=now(),
                configuration=ResearchConfiguration(),
            )
        ]

    async def get_active(self) -> VersionedResearchConfiguration:
        return self._versions[-1]

    async def list_versions(self) -> list[VersionedResearchConfiguration]:
        return list(reversed(self._versions))

    async def get_version(self, version: int) -> Optional[VersionedResearchConfiguration]:
        return next((item for item in self._versions if item.version == version), None)

    async def create(self, configuration: ResearchConfiguration) -> VersionedResearchConfiguration:
        version = VersionedResearchConfiguration(
            id=self._id_factory(),
            version=self._versions[-1].version + 1,
            created_at=self._now(),
            configuration=configuration.model_copy(deep=True),
        )
        self._versions.append(version)
        return version
