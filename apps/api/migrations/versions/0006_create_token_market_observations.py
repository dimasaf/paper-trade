"""Persist point-in-time Token market observations.

Revision ID: 0006
Revises: 0005
"""

from collections.abc import Sequence
from typing import Optional, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0006"
down_revision: Optional[str] = "0005"
branch_labels: Optional[Union[str, Sequence[str]]] = None
depends_on: Optional[Union[str, Sequence[str]]] = None


def upgrade() -> None:
    op.create_table(
        "token_market_observations",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "token_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("tokens.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("observation_id", sa.Text(), nullable=False),
        sa.Column("observed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("price_usd", sa.Numeric(), nullable=True),
        sa.Column("supply", sa.Numeric(), nullable=True),
        sa.Column("market_cap_usd", sa.Numeric(), nullable=True),
        sa.Column("liquidity_usd", sa.Numeric(), nullable=True),
        sa.Column("volume_24h_usd", sa.Numeric(), nullable=True),
        sa.Column("pools", postgresql.JSONB(), nullable=False),
        sa.Column("coverage", postgresql.JSONB(), nullable=False),
        sa.UniqueConstraint("token_id", "observation_id"),
    )
    op.create_index(
        "ix_token_market_observations_token_observed_at",
        "token_market_observations",
        ["token_id", "observed_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_token_market_observations_token_observed_at")
    op.drop_table("token_market_observations")
