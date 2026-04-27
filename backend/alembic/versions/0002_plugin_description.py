"""add plugin description

Revision ID: 0002_plugin_description
Revises: 0001_baseline
Create Date: 2026-04-27

"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0002_plugin_description"
down_revision: Union[str, None] = "0001_baseline"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "plugins",
        sa.Column("description", sa.String(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("plugins", "description")
