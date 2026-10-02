"""Persist evidence-backed Wallet relationship analyses.

Revision ID: 0011
Revises: 0010
"""

from collections.abc import Sequence
from typing import Optional, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0011"
down_revision: Optional[str] = "0010"
branch_labels: Optional[Union[str, Sequence[str]]] = None
depends_on: Optional[Union[str, Sequence[str]]] = None


def upgrade() -> None:
    op.create_table(
        "wallet_relationship_analyses",
        sa.Column("wallet_address", sa.Text(), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("as_of", sa.DateTime(timezone=True), nullable=False),
        sa.Column("configuration_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("configuration_version", sa.Integer(), nullable=False),
        sa.Column("analysis", postgresql.JSONB(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("wallet_address", "version"),
    )
    op.create_index(
        "ix_wallet_relationship_analyses_as_of",
        "wallet_relationship_analyses",
        ["wallet_address", "as_of"],
    )


def downgrade() -> None:
    op.drop_index("ix_wallet_relationship_analyses_as_of")
    op.drop_table("wallet_relationship_analyses")
