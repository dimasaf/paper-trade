"""retain documented launch-program evidence with lifecycle transitions

Revision ID: 0004_add_launch_program_evidence
Revises: 0003_create_token_universe
Create Date: 2026-09-28
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0004_add_launch_program_evidence"
down_revision = "0003_create_token_universe"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "token_lifecycle_transitions",
        sa.Column(
            "evidence",
            postgresql.JSONB(),
            nullable=False,
            server_default=sa.text("'[]'::jsonb"),
        ),
    )


def downgrade() -> None:
    op.drop_column("token_lifecycle_transitions", "evidence")
