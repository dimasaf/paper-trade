"""Persist Smart Wallet Score versions and Registry transitions.

Revision ID: 0008
Revises: 0007
"""

from collections.abc import Sequence
from typing import Optional, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0008"
down_revision: Optional[str] = "0007"
branch_labels: Optional[Union[str, Sequence[str]]] = None
depends_on: Optional[Union[str, Sequence[str]]] = None


def upgrade() -> None:
    op.create_table(
        "wallet_score_versions",
        sa.Column("wallet_address", sa.Text(), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("as_of", sa.DateTime(timezone=True), nullable=False),
        sa.Column("configuration_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("configuration_version", sa.Integer(), nullable=False),
        sa.Column("score", postgresql.JSONB(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("wallet_address", "version"),
    )
    op.create_index(
        "ix_wallet_score_versions_as_of",
        "wallet_score_versions",
        ["wallet_address", "as_of"],
    )
    op.create_table(
        "wallet_registry_transitions",
        sa.Column("wallet_address", sa.Text(), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("from_state", sa.Text(), nullable=False),
        sa.Column("to_state", sa.Text(), nullable=False),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column("evidence", postgresql.JSONB(), nullable=False),
        sa.Column("as_of", sa.DateTime(timezone=True), nullable=False),
        sa.Column("configuration_version", sa.Integer(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("wallet_address", "version"),
    )
    op.create_index(
        "ix_wallet_registry_transitions_as_of",
        "wallet_registry_transitions",
        ["wallet_address", "as_of"],
    )


def downgrade() -> None:
    op.drop_index("ix_wallet_registry_transitions_as_of")
    op.drop_table("wallet_registry_transitions")
    op.drop_index("ix_wallet_score_versions_as_of")
    op.drop_table("wallet_score_versions")
