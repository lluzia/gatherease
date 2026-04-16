"""Initial schema — all 12 GatherEase tables

Revision ID: 0001_initial_schema
Revises:
Create Date: 2026-05-20 09:00:00.000000
"""

from __future__ import annotations

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
from sqlalchemy.dialects.postgresql import UUID

from alembic import op

revision: str = "0001_initial_schema"
down_revision: str | None = None
branch_labels: str | None = None
depends_on: str | None = None

# ---------------------------------------------------------------------------
# Two sets of enum objects:
#
# *_enum        — used for .create() / .drop() only. Has create_type=True
#                 (default) so the type gets created in the DB.
#
# *_col         — used inside op.create_table() columns. Has create_type=False
#                 so SQLAlchemy does NOT fire a second CREATE TYPE event when
#                 the table is being built.
# ---------------------------------------------------------------------------

# For explicit create/drop
rsvp_status_enum = postgresql.ENUM(
    "accepted", "declined", "maybe", "pending", name="rsvp_status"
)
dish_category_enum = postgresql.ENUM(
    "starter", "main", "side", "dessert", "drink", "other", name="dish_category"
)
budget_entry_type_enum = postgresql.ENUM(
    "host", "participant", name="budget_entry_type"
)
reminder_type_enum = postgresql.ENUM("push", "email", "both", name="reminder_type")

# For column definitions — postgresql.ENUM with create_type=False
# sa.Enum ignores create_type; only postgresql.ENUM honours it
rsvp_status_col = postgresql.ENUM(
    "accepted", "declined", "maybe", "pending", name="rsvp_status", create_type=False
)
dish_category_col = postgresql.ENUM(
    "starter",
    "main",
    "side",
    "dessert",
    "drink",
    "other",
    name="dish_category",
    create_type=False,
)
budget_entry_type_col = postgresql.ENUM(
    "host", "participant", name="budget_entry_type", create_type=False
)
reminder_type_col = postgresql.ENUM(
    "push", "email", "both", name="reminder_type", create_type=False
)


def upgrade() -> None:
    bind = op.get_bind()

    # Create enum types once — checkfirst=True is a safety net
    rsvp_status_enum.create(bind, checkfirst=True)
    dish_category_enum.create(bind, checkfirst=True)
    budget_entry_type_enum.create(bind, checkfirst=True)
    reminder_type_enum.create(bind, checkfirst=True)

    # ── 1. users ──────────────────────────────────────────────────────────
    op.create_table(
        "users",
        sa.Column(
            "id",
            UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("cognito_sub", sa.String(128), nullable=False),
        sa.Column("email", sa.String(320), nullable=False),
        sa.Column("full_name", sa.String(255), nullable=True),
        sa.Column("avatar_url", sa.Text, nullable=True),
        sa.Column(
            "preferred_language", sa.String(5), nullable=False, server_default="en"
        ),
        sa.Column("is_active", sa.Boolean, nullable=False, server_default="true"),
        sa.Column("is_premium", sa.Boolean, nullable=False, server_default="false"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )
    op.create_index("ix_users_cognito_sub", "users", ["cognito_sub"], unique=True)
    op.create_index("ix_users_email", "users", ["email"], unique=True)

    # ── 2. gatherings ─────────────────────────────────────────────────────
    op.create_table(
        "gatherings",
        sa.Column(
            "id",
            UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column(
            "host_id",
            UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("description", sa.Text, nullable=True),
        sa.Column("location", sa.String(500), nullable=True),
        sa.Column("event_date", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "guest_count_estimate", sa.Integer, nullable=False, server_default="0"
        ),
        sa.Column("invite_token", sa.String(128), nullable=True),
        sa.Column("show_menu", sa.Boolean, nullable=False, server_default="true"),
        sa.Column("show_location", sa.Boolean, nullable=False, server_default="true"),
        sa.Column(
            "show_shopping_list", sa.Boolean, nullable=False, server_default="false"
        ),
        sa.Column(
            "show_prep_tasks", sa.Boolean, nullable=False, server_default="false"
        ),
        sa.Column("is_archived", sa.Boolean, nullable=False, server_default="false"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )
    op.create_index("ix_gatherings_host_id", "gatherings", ["host_id"])
    op.create_index("ix_gatherings_event_date", "gatherings", ["event_date"])
    op.create_index(
        "ix_gatherings_invite_token", "gatherings", ["invite_token"], unique=True
    )

    # ── 3. guest_rsvps — uses rsvp_status_col (create_type=False) ─────────
    op.create_table(
        "guest_rsvps",
        sa.Column(
            "id",
            UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column(
            "gathering_id",
            UUID(as_uuid=True),
            sa.ForeignKey("gatherings.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("guest_name", sa.String(255), nullable=False),
        sa.Column("guest_email", sa.String(320), nullable=True),
        sa.Column("status", rsvp_status_col, nullable=False, server_default="pending"),
        sa.Column("message", sa.Text, nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )
    op.create_index("ix_guest_rsvps_gathering_id", "guest_rsvps", ["gathering_id"])
    op.create_index("ix_guest_rsvps_status", "guest_rsvps", ["status"])

    # ── 4. menus ──────────────────────────────────────────────────────────
    op.create_table(
        "menus",
        sa.Column(
            "id",
            UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column(
            "gathering_id",
            UUID(as_uuid=True),
            sa.ForeignKey("gatherings.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("name", sa.String(255), nullable=False, server_default="Menu"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )
    op.create_index("ix_menus_gathering_id", "menus", ["gathering_id"])

    # ── 5. dishes — uses dish_category_col (create_type=False) ────────────
    op.create_table(
        "dishes",
        sa.Column(
            "id",
            UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column(
            "menu_id",
            UUID(as_uuid=True),
            sa.ForeignKey("menus.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column(
            "category", dish_category_col, nullable=False, server_default="other"
        ),
        sa.Column("assigned_to", sa.String(255), nullable=True),
        sa.Column(
            "is_host_prepared", sa.Boolean, nullable=False, server_default="true"
        ),
        sa.Column("servings", sa.Integer, nullable=False, server_default="4"),
        sa.Column("sort_order", sa.Integer, nullable=False, server_default="0"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )
    op.create_index("ix_dishes_menu_id", "dishes", ["menu_id"])
    op.create_index("ix_dishes_category", "dishes", ["category"])

    # ── 6. recipes ────────────────────────────────────────────────────────
    op.create_table(
        "recipes",
        sa.Column(
            "id",
            UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column(
            "dish_id",
            UUID(as_uuid=True),
            sa.ForeignKey("dishes.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("instructions", sa.Text, nullable=True),
        sa.Column("photo_url", sa.Text, nullable=True),
        sa.Column("ingredients", postgresql.JSONB, nullable=True, server_default="[]"),
        sa.Column("base_servings", sa.Integer, nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )
    op.create_index("ix_recipes_dish_id", "recipes", ["dish_id"], unique=True)

    # ── 7. shopping_items ─────────────────────────────────────────────────
    op.create_table(
        "shopping_items",
        sa.Column(
            "id",
            UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column(
            "gathering_id",
            UUID(as_uuid=True),
            sa.ForeignKey("gatherings.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "dish_id",
            UUID(as_uuid=True),
            sa.ForeignKey("dishes.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("quantity", sa.Numeric(10, 3), nullable=True),
        sa.Column("unit", sa.String(50), nullable=True),
        sa.Column("assigned_to", sa.String(255), nullable=True),
        sa.Column("is_purchased", sa.Boolean, nullable=False, server_default="false"),
        sa.Column(
            "is_auto_generated", sa.Boolean, nullable=False, server_default="false"
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )
    op.create_index(
        "ix_shopping_items_gathering_id", "shopping_items", ["gathering_id"]
    )
    op.create_index("ix_shopping_items_dish_id", "shopping_items", ["dish_id"])
    op.create_index(
        "ix_shopping_items_is_purchased", "shopping_items", ["is_purchased"]
    )

    # ── 8. prep_tasks ─────────────────────────────────────────────────────
    op.create_table(
        "prep_tasks",
        sa.Column(
            "id",
            UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column(
            "gathering_id",
            UUID(as_uuid=True),
            sa.ForeignKey("gatherings.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("title", sa.String(255), nullable=False),
        sa.Column("description", sa.Text, nullable=True),
        sa.Column("assigned_to", sa.String(255), nullable=True),
        sa.Column("due_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("is_completed", sa.Boolean, nullable=False, server_default="false"),
        sa.Column("sort_order", sa.Integer, nullable=False, server_default="0"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )
    op.create_index("ix_prep_tasks_gathering_id", "prep_tasks", ["gathering_id"])
    op.create_index("ix_prep_tasks_due_at", "prep_tasks", ["due_at"])
    op.create_index("ix_prep_tasks_is_completed", "prep_tasks", ["is_completed"])

    # ── 9. budgets ────────────────────────────────────────────────────────
    op.create_table(
        "budgets",
        sa.Column(
            "id",
            UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column(
            "gathering_id",
            UUID(as_uuid=True),
            sa.ForeignKey("gatherings.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("currency", sa.String(3), nullable=False, server_default="EUR"),
        sa.Column("host_budget_limit", sa.Numeric(12, 2), nullable=True),
        sa.Column("participant_target", sa.Numeric(12, 2), nullable=True),
        sa.Column("version", sa.Integer, nullable=False, server_default="1"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )
    op.create_index("ix_budgets_gathering_id", "budgets", ["gathering_id"], unique=True)

    # ── 10. budget_entries — uses budget_entry_type_col (create_type=False)
    op.create_table(
        "budget_entries",
        sa.Column(
            "id",
            UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column(
            "budget_id",
            UUID(as_uuid=True),
            sa.ForeignKey("budgets.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("entry_type", budget_entry_type_col, nullable=False),
        sa.Column("description", sa.String(500), nullable=False),
        sa.Column("amount", sa.Numeric(12, 2), nullable=False),
        sa.Column("paid_by", sa.String(255), nullable=True),
        sa.Column("notes", sa.Text, nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )
    op.create_index("ix_budget_entries_budget_id", "budget_entries", ["budget_id"])
    op.create_index("ix_budget_entries_entry_type", "budget_entries", ["entry_type"])

    # ── 11. reminders — uses reminder_type_col (create_type=False) ────────
    op.create_table(
        "reminders",
        sa.Column(
            "id",
            UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column(
            "gathering_id",
            UUID(as_uuid=True),
            sa.ForeignKey("gatherings.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("title", sa.String(255), nullable=False),
        sa.Column("body", sa.Text, nullable=True),
        sa.Column(
            "reminder_type", reminder_type_col, nullable=False, server_default="push"
        ),
        sa.Column("scheduled_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("is_sent", sa.Boolean, nullable=False, server_default="false"),
        sa.Column("sent_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )
    op.create_index("ix_reminders_gathering_id", "reminders", ["gathering_id"])
    op.create_index("ix_reminders_scheduled_at", "reminders", ["scheduled_at"])
    op.create_index("ix_reminders_is_sent", "reminders", ["is_sent"])

    # ── updated_at trigger ────────────────────────────────────────────────
    op.execute("""
        CREATE OR REPLACE FUNCTION set_updated_at()
        RETURNS TRIGGER AS $$
        BEGIN
            NEW.updated_at = NOW();
            RETURN NEW;
        END;
        $$ LANGUAGE plpgsql;
    """)

    for table in [
        "users",
        "gatherings",
        "guest_rsvps",
        "menus",
        "dishes",
        "recipes",
        "shopping_items",
        "prep_tasks",
        "budgets",
        "budget_entries",
        "reminders",
    ]:
        op.execute(f"""
            CREATE TRIGGER trg_{table}_updated_at
            BEFORE UPDATE ON {table}
            FOR EACH ROW EXECUTE FUNCTION set_updated_at();
        """)


def downgrade() -> None:
    tables = [
        "reminders",
        "budget_entries",
        "budgets",
        "prep_tasks",
        "shopping_items",
        "recipes",
        "dishes",
        "menus",
        "guest_rsvps",
        "gatherings",
        "users",
    ]
    bind = op.get_bind()
    for table in tables:
        op.execute(f"DROP TRIGGER IF EXISTS trg_{table}_updated_at ON {table}")
        op.drop_table(table)

    op.execute("DROP FUNCTION IF EXISTS set_updated_at")
    reminder_type_enum.drop(bind, checkfirst=True)
    budget_entry_type_enum.drop(bind, checkfirst=True)
    dish_category_enum.drop(bind, checkfirst=True)
    rsvp_status_enum.drop(bind, checkfirst=True)
