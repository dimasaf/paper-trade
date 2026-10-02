"""Persist confirmed realtime Wallet events and their tracking runs.

Revision ID: 0010
Revises: 0009
"""

from collections.abc import Sequence
from typing import Optional, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0010"
down_revision: Optional[str] = "0009"
branch_labels: Optional[Union[str, Sequence[str]]] = None
depends_on: Optional[Union[str, Sequence[str]]] = None


def upgrade() -> None:
    op.create_table(
        "realtime_wallet_events",
        sa.Column("idempotency_key", sa.Text(), nullable=False),
        sa.Column("event_id", sa.Text(), nullable=False),
        sa.Column("wallet_address", sa.Text(), nullable=False),
        sa.Column("token_address", sa.Text(), nullable=False),
        sa.Column("movement_type", sa.Text(), nullable=False),
        sa.Column("quantity", sa.Float(), nullable=False),
        sa.Column("notional_usd", sa.Float(), nullable=True),
        sa.Column("price_usd", sa.Float(), nullable=True),
        sa.Column("venue", sa.Text(), nullable=True),
        sa.Column("signature", sa.Text(), nullable=False),
        sa.Column("slot", sa.BigInteger(), nullable=False),
        sa.Column("chain_time", sa.DateTime(timezone=True), nullable=False),
        sa.Column("observed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("received_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("commitment", sa.Text(), nullable=False),
        sa.Column("wallet_score", sa.Float(), nullable=True),
        sa.Column("score_as_of", sa.DateTime(timezone=True), nullable=False),
        sa.Column("eligible_for_decisions", sa.Boolean(), nullable=False),
        sa.Column("evidence", postgresql.JSONB(), nullable=False),
        sa.Column("coverage", postgresql.JSONB(), nullable=False),
        sa.Column("warnings", postgresql.JSONB(), nullable=False),
        sa.PrimaryKeyConstraint("idempotency_key"),
    )
    op.create_index(
        "ix_realtime_wallet_events_as_of",
        "realtime_wallet_events",
        ["wallet_address", "chain_time"],
    )
    op.create_table(
        "realtime_tracking_runs",
        sa.Column("run_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("as_of", sa.DateTime(timezone=True), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("subscribed_wallets", postgresql.JSONB(), nullable=False),
        sa.Column("received", sa.Integer(), nullable=False),
        sa.Column("recorded", sa.Integer(), nullable=False),
        sa.Column("duplicates", sa.Integer(), nullable=False),
        sa.Column("processed_only", sa.Integer(), nullable=False),
        sa.Column("skipped_unsubscribed", sa.Integer(), nullable=False),
        sa.Column("reconnects", sa.Integer(), nullable=False),
        sa.Column("max_lag_seconds", sa.Float(), nullable=True),
        sa.Column("processing_latency_seconds", sa.Float(), nullable=False),
        sa.Column("warnings", postgresql.JSONB(), nullable=False),
        sa.PrimaryKeyConstraint("run_id"),
    )
    op.create_index(
        "ix_realtime_tracking_runs_started_at",
        "realtime_tracking_runs",
        ["started_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_realtime_tracking_runs_started_at")
    op.drop_table("realtime_tracking_runs")
    op.drop_index("ix_realtime_wallet_events_as_of")
    op.drop_table("realtime_wallet_events")
