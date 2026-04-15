"""Add fcm_token to users for push notifications

Revision ID: 0003_add_fcm_token
Revises: 0002_add_hashed_password
Create Date: 2026-04-15 10:00:00.000000

Adds fcm_token (nullable) to the users table.
Clients (Flutter) call PATCH /api/v1/users/me/device-token after login
to register their FCM device token. SNS uses this to address targeted
push notifications (reminder.fire events).
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision: str = "0003_add_fcm_token"
down_revision: str = "0002_add_hashed_password"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column("fcm_token", sa.String(512), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("users", "fcm_token")
