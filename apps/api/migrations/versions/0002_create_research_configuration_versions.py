"""Create immutable research configuration versions.

Revision ID: 0002
Revises: 0001
"""

from collections.abc import Sequence
from typing import Optional, Union
from uuid import UUID

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0002"
down_revision: Optional[str] = "0001"
branch_labels: Optional[Union[str, Sequence[str]]] = None
depends_on: Optional[Union[str, Sequence[str]]] = None

DEFAULT_CONFIGURATION = {
    "token": {
        "launch_sources": [
            "PUMP_FUN",
            "PUMP_SWAP",
            "RAYDIUM_LAUNCHLAB",
            "METEORA_DBC",
            "JUPITER_STUDIO",
        ],
        "require_pool": True,
        "minimum_liquidity_usd": 10_000.0,
        "minimum_market_cap_usd": 25_000.0,
        "minimum_24h_volume_usd": 10_000.0,
        "winner_initial_market_cap_min_usd": 10_000.0,
        "winner_initial_market_cap_max_usd": 500_000.0,
        "winner_peak_market_cap_min_usd": 1_000_000.0,
        "entry_market_cap_buckets_usd": [
            50_000.0,
            100_000.0,
            250_000.0,
            500_000.0,
        ],
    },
    "wallet": {
        "minimum_score": 80.0,
        "minimum_trades": 20,
        "copyability_delays_ms": [500, 1000, 2000, 3000, 5000, 10000],
        "copyability_sizes_sol": [0.1, 0.25, 0.5, 1.0, 2.0],
        "score_weights": {
            "profitability": 20.0,
            "consistency": 20.0,
            "copyability": 25.0,
            "risk_quality": 15.0,
            "entry_quality": 10.0,
            "history_quality": 10.0,
        },
    },
    "cluster": {
        "minimum_independent_wallets": 3,
        "window_seconds": 300,
        "minimum_average_wallet_score": 80.0,
    },
    "signal": {
        "watch_score": 60.0,
        "paper_buy_score": 80.0,
        "cooldown_seconds": 900,
        "score_weights": {
            "wallet_quality": 25.0,
            "independent_wallets": 20.0,
            "token_risk": 20.0,
            "liquidity": 10.0,
            "entry_quality": 10.0,
            "buy_velocity": 10.0,
            "market_confirmation": 5.0,
        },
    },
    "paper_trading": {
        "starting_balance_usd": 10_000.0,
        "sizing_mode": "PERCENT",
        "position_size_percent": 1.0,
        "position_size_sol": 0.5,
        "maximum_position_percent": 3.0,
        "maximum_open_positions": 10,
    },
    "risk": {
        "stop_loss_percent": 15.0,
        "take_profit_percent": 30.0,
        "partial_take_profits": [
            {"gain_percent": 25.0, "sell_percent": 25.0},
            {"gain_percent": 50.0, "sell_percent": 25.0},
            {"gain_percent": 100.0, "sell_percent": 25.0},
        ],
        "trailing_stop_percent": 15.0,
        "smart_wallet_sell_pressure_percent": 60.0,
        "liquidity_collapse_percent": 50.0,
        "holder_concentration_increase_percent": 10.0,
        "volume_collapse_percent": 70.0,
        "maximum_holding_seconds": 86_400,
    },
    "execution": {
        "latency_ms": 3000,
        "fallback_slippage_percent": 2.0,
        "venue_fee_percent": 0.25,
        "network_fee_sol": 0.000005,
        "priority_fee_sol": 0.0001,
        "failed_transaction_probability_percent": 1.0,
        "maximum_pool_participation_percent": 1.0,
    },
}


def upgrade() -> None:
    versions = op.create_table(
        "research_configuration_versions",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("version", sa.Integer(), nullable=False, unique=True),
        sa.Column("configuration", postgresql.JSONB(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.CheckConstraint("version >= 1", name="ck_configuration_version_positive"),
    )
    op.bulk_insert(
        versions,
        [
            {
                "id": UUID("00000000-0000-0000-0000-000000000001"),
                "version": 1,
                "configuration": DEFAULT_CONFIGURATION,
            }
        ],
    )
    op.execute(
        """
        CREATE FUNCTION reject_research_configuration_mutation()
        RETURNS trigger AS $$
        BEGIN
            RAISE EXCEPTION 'research configuration versions are immutable';
        END;
        $$ LANGUAGE plpgsql
        """
    )
    op.execute(
        """
        CREATE TRIGGER research_configuration_versions_immutable
        BEFORE UPDATE OR DELETE ON research_configuration_versions
        FOR EACH ROW EXECUTE FUNCTION reject_research_configuration_mutation()
        """
    )


def downgrade() -> None:
    op.drop_table("research_configuration_versions")
    op.execute("DROP FUNCTION reject_research_configuration_mutation()")
