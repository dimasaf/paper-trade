"""Create the Token universe, lifecycle transitions, and provider coverage.

Revision ID: 0003
Revises: 0002
"""

from collections.abc import Sequence
from typing import Optional, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0003"
down_revision: Optional[str] = "0002"
branch_labels: Optional[Union[str, Sequence[str]]] = None
depends_on: Optional[Union[str, Sequence[str]]] = None

LIFECYCLE_STATES = ("NEW", "ACTIVE", "MIGRATED", "ILLIQUID", "DEAD", "SUSPICIOUS")
LAUNCH_SOURCES = ("PUMP_FUN", "PUMP_SWAP", "RAYDIUM_LAUNCHLAB", "METEORA_DBC", "JUPITER_STUDIO")
COMMITMENTS = ("confirmed", "processed")

LIFECYCLE_STATE_CHECK = "lifecycle_state IN ({})".format(
    ", ".join(f"'{state}'" for state in LIFECYCLE_STATES)
)
LAUNCH_PLATFORM_CHECK = "launch_platform IN ({})".format(
    ", ".join(f"'{source}'" for source in LAUNCH_SOURCES)
)
TRANSITION_STATE_CHECK = "state IN ({})".format(
    ", ".join(f"'{state}'" for state in LIFECYCLE_STATES)
)
COMMITMENT_CHECK = "commitment IN ({})".format(
    ", ".join(f"'{commitment}'" for commitment in COMMITMENTS)
)


def upgrade() -> None:
    op.create_table(
        "tokens",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("address", sa.Text(), nullable=False, unique=True),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("symbol", sa.Text(), nullable=False),
        sa.Column("creator", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("observed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("launch_platform", sa.String(length=32), nullable=False),
        sa.Column("lifecycle_state", sa.String(length=16), nullable=False),
        sa.Column("classification", postgresql.JSONB(), nullable=False),
        sa.Column("source_event_id", sa.Text(), nullable=False),
        sa.Column(
            "registered_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.CheckConstraint("address <> ''", name="ck_token_address_present"),
        sa.CheckConstraint(LIFECYCLE_STATE_CHECK, name="ck_token_lifecycle_state"),
        sa.CheckConstraint(LAUNCH_PLATFORM_CHECK, name="ck_token_launch_platform"),
    )
    op.create_table(
        "token_lifecycle_transitions",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("token_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("state", sa.String(length=16), nullable=False),
        sa.Column("observed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("source_event_id", sa.Text(), nullable=False),
        sa.Column("reason", sa.Text(), nullable=False, server_default=sa.text("''")),
        sa.Column("sequence", sa.BigInteger(), sa.Identity(), nullable=False),
        sa.Column(
            "recorded_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.ForeignKeyConstraint(
            ["token_id"],
            ["tokens.id"],
            name="fk_token_lifecycle_transition_token",
            ondelete="CASCADE",
        ),
        sa.UniqueConstraint(
            "token_id", "source_event_id", name="uq_token_lifecycle_transition_event"
        ),
        sa.CheckConstraint(TRANSITION_STATE_CHECK, name="ck_token_lifecycle_transition_state"),
    )
    op.create_index(
        "ix_token_lifecycle_transitions_token",
        "token_lifecycle_transitions",
        ["token_id", "observed_at"],
    )
    op.create_table(
        "token_provider_coverage",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("token_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("provider", sa.Text(), nullable=False),
        sa.Column("as_of_start", sa.DateTime(timezone=True), nullable=False),
        sa.Column("as_of_end", sa.DateTime(timezone=True), nullable=False),
        sa.Column("complete", sa.Boolean(), nullable=False),
        sa.Column("commitment", sa.String(length=16), nullable=False),
        sa.Column(
            "unknown_fields",
            postgresql.JSONB(),
            nullable=False,
            server_default=sa.text("'[]'::jsonb"),
        ),
        sa.Column(
            "warnings",
            postgresql.JSONB(),
            nullable=False,
            server_default=sa.text("'[]'::jsonb"),
        ),
        sa.Column("source_event_id", sa.Text(), nullable=False),
        sa.Column(
            "recorded_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.ForeignKeyConstraint(
            ["token_id"],
            ["tokens.id"],
            name="fk_token_provider_coverage_token",
            ondelete="CASCADE",
        ),
        sa.UniqueConstraint("token_id", "source_event_id", name="uq_token_provider_coverage_event"),
        sa.CheckConstraint("as_of_start <= as_of_end", name="ck_token_provider_coverage_interval"),
        sa.CheckConstraint(COMMITMENT_CHECK, name="ck_token_provider_coverage_commitment"),
    )
    op.create_index("ix_token_provider_coverage_token", "token_provider_coverage", ["token_id"])


def downgrade() -> None:
    op.drop_index("ix_token_provider_coverage_token", table_name="token_provider_coverage")
    op.drop_table("token_provider_coverage")
    op.drop_index("ix_token_lifecycle_transitions_token", table_name="token_lifecycle_transitions")
    op.drop_table("token_lifecycle_transitions")
    op.drop_table("tokens")
