"""Add hashed_password to users for local auth mode

Revision ID: 0002_add_hashed_password
Revises: 0001_initial_schema
Create Date: 2026-04-11 09:00:00.000000

Adds a nullable hashed_password column to the users table.
Used only in LOCAL_AUTH=true mode (development).
In production with Cognito, this column stays NULL.
"""

from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision: str = "0002_add_hashed_password"
down_revision: str = "0001_initial_schema"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column("hashed_password", sa.String(255), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("users", "hashed_password")
