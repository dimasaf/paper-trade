"""Persist recorded Wallet accounting facts.

Revision ID: 0007
Revises: 0006
"""

from collections.abc import Sequence
from typing import Optional, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0007"
down_revision: Optional[str] = "0006"
branch_labels: Optional[Union[str, Sequence[str]]] = None
depends_on: Optional[Union[str, Sequence[str]]] = None


def upgrade() -> None:
    op.create_table(
        "wallet_accounting_activities",
        sa.Column("wallet_address", sa.Text(), nullable=False),
        sa.Column("signature", sa.Text(), nullable=False),
        sa.Column("chain_time", sa.DateTime(timezone=True), nullable=False),
        sa.Column("observed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("activity", postgresql.JSONB(), nullable=False),
        sa.PrimaryKeyConstraint("wallet_address", "signature"),
    )
    op.create_index(
        "ix_wallet_accounting_activities_as_of",
        "wallet_accounting_activities",
        ["wallet_address", "chain_time", "observed_at"],
    )
    op.create_table(
        "wallet_accounting_coverages",
        sa.Column("wallet_address", sa.Text(), nullable=False),
        sa.Column("coverage_key", sa.Text(), nullable=False),
        sa.Column("as_of_start", sa.DateTime(timezone=True), nullable=False),
        sa.Column("coverage", postgresql.JSONB(), nullable=False),
        sa.PrimaryKeyConstraint("wallet_address", "coverage_key"),
    )
    op.create_index(
        "ix_wallet_accounting_coverages_as_of",
        "wallet_accounting_coverages",
        ["wallet_address", "as_of_start"],
    )
    op.create_table(
        "wallet_accounting_mark_prices",
        sa.Column("token_address", sa.Text(), nullable=False),
        sa.Column("observed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("provider", sa.Text(), nullable=False),
        sa.Column("price_usd", sa.Numeric(), nullable=False),
        sa.PrimaryKeyConstraint("token_address", "observed_at", "provider"),
    )
    op.create_index(
        "ix_wallet_accounting_mark_prices_as_of",
        "wallet_accounting_mark_prices",
        ["token_address", "observed_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_wallet_accounting_mark_prices_as_of")
    op.drop_table("wallet_accounting_mark_prices")
    op.drop_index("ix_wallet_accounting_coverages_as_of")
    op.drop_table("wallet_accounting_coverages")
    op.drop_index("ix_wallet_accounting_activities_as_of")
    op.drop_table("wallet_accounting_activities")
