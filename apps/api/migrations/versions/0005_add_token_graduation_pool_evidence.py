"""Retain graduation-pool evidence with Token lifecycle transitions.

Revision ID: 0005
Revises: 0004_launch_evidence
"""

from collections.abc import Sequence
from typing import Optional, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0005"
down_revision: Optional[str] = "0004_launch_evidence"
branch_labels: Optional[Union[str, Sequence[str]]] = None
depends_on: Optional[Union[str, Sequence[str]]] = None


def upgrade() -> None:
    op.add_column(
        "token_lifecycle_transitions",
        sa.Column("graduation_pool_address", sa.Text(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("token_lifecycle_transitions", "graduation_pool_address")
