"""Persist qualifying Smart Wallet activity and Smart Wallet Cluster versions.

Revision ID: 0012
Revises: 0011
"""

from collections.abc import Sequence
from typing import Optional, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0012"
down_revision: Optional[str] = "0011"
branch_labels: Optional[Union[str, Sequence[str]]] = None
depends_on: Optional[Union[str, Sequence[str]]] = None


def upgrade() -> None:
    op.create_table(
        "smart_wallet_cluster_activities",
        sa.Column("idempotency_key", sa.Text(), nullable=False),
        sa.Column("event_id", sa.Text(), nullable=False),
        sa.Column("wallet_address", sa.Text(), nullable=False),
        sa.Column("token_address", sa.Text(), nullable=False),
        sa.Column("movement_type", sa.Text(), nullable=False),
        sa.Column("quantity", sa.Float(), nullable=False),
        sa.Column("sol_amount", sa.Float(), nullable=False),
        sa.Column("notional_usd", sa.Float(), nullable=True),
        sa.Column("wallet_score", sa.Float(), nullable=True),
        sa.Column("signature", sa.Text(), nullable=False),
        sa.Column("slot", sa.BigInteger(), nullable=False),
        sa.Column("chain_time", sa.DateTime(timezone=True), nullable=False),
        sa.Column("observed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("commitment", sa.Text(), nullable=False),
        sa.Column("eligible_for_decisions", sa.Boolean(), nullable=False),
        sa.Column("evidence", postgresql.JSONB(), nullable=False),
        sa.Column("coverage", postgresql.JSONB(), nullable=False),
        sa.PrimaryKeyConstraint("idempotency_key"),
    )
    op.create_index(
        "ix_smart_wallet_cluster_activities_token",
        "smart_wallet_cluster_activities",
        ["token_address", "chain_time"],
    )
    op.create_table(
        "smart_wallet_cluster_versions",
        sa.Column("token_address", sa.Text(), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("as_of", sa.DateTime(timezone=True), nullable=False),
        sa.Column("status", sa.Text(), nullable=False),
        sa.Column("superseded_by_version", sa.Integer(), nullable=True),
        sa.Column("configuration_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("configuration_version", sa.Integer(), nullable=False),
        sa.Column("cluster", postgresql.JSONB(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("token_address", "version"),
    )
    op.create_index(
        "ix_smart_wallet_cluster_versions_as_of",
        "smart_wallet_cluster_versions",
        ["token_address", "as_of"],
    )
    op.create_index(
        "ix_smart_wallet_cluster_versions_status",
        "smart_wallet_cluster_versions",
        ["status", "as_of"],
    )


def downgrade() -> None:
    op.drop_index("ix_smart_wallet_cluster_versions_status")
    op.drop_index("ix_smart_wallet_cluster_versions_as_of")
    op.drop_table("smart_wallet_cluster_versions")
    op.drop_index("ix_smart_wallet_cluster_activities_token")
    op.drop_table("smart_wallet_cluster_activities")
